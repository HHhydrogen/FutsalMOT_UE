"""v10新54臂单臂训练：同3000R/1000S，完整记录循环，不追加旧权重。"""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).parent))
import v10_runtime as runtime


def train(config,fold,seed,pool,method,output):
    started=time.perf_counter()
    cfg,numeric,base,pools,table,normalizer,adapter,reference=runtime.validate_job(config,fold,seed,pool,method)
    verified=runtime.read(cfg['numeric_validation_receipt_path'])
    runtime.require(verified['status']=='complete_three_methods_one_step_equal_with_recording'
        and verified['protocol_sha256']==runtime.sha(config) and verified['actual_diagnostic_optimizer_updates']==6
        and verified['all_methods_equal'] is True,'先完成实际数值/记录诊断，不能拿CPU夹具当训练准入')
    import torch
    from ordered_prefetch import OrderedPrefetch
    from recorded_association_loop import train as recorded_train
    runtime.require(torch.__version__=='2.6.0+cu124','冻结Torch数值环境改变')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    runtime.require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>1024**3,'GPU余量不足')
    output=runtime.storage().physical_child(output,runtime.EXPERIMENT)
    runtime.require(not output.exists(),'已有run/partial，禁止隐式覆盖/重放')
    if method=='motion':
        from grf_ue_bridge.learned_association_model_v8 import make_model
        model=make_model(seed).to('cuda:0');cache=base.FeatureCache(pools,normalizer,False)
    else:model=numeric.make_model(seed,method).to('cuda:0');cache=numeric.Cache(pools,adapter,method,seed)
    initial=base.model_sha(model);base_initial=base.model_sha(model if method=='motion' else model.base)
    runtime.require(initial==reference['binding']['initialization_sha256'],'初始化必须与对应纯R参考一致')
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    binding=dict(protocol_sha256=runtime.sha(config),fold=fold,seed=seed,pool=pool,method=method,regime='RS',
        initialization_sha256=initial,motion_base_initialization_sha256=base_initial,
        R_window_UID_chain_sha256=hashlib.sha256(runtime.canonical([x['window_uid'] for x in table['real']]).encode()).hexdigest(),
        S_window_UID_chain_sha256=hashlib.sha256(runtime.canonical([x['window_uid'] for x in table['synthetic']]).encode()).hexdigest(),
        synthetic_pool=cfg['synthetic_pools'][pool],v9_protocol=cfg['v9_protocol'],pool_complete=cfg['pool_complete'])
    extra=dict(schema='v10_association_method_state_v1',method=method,normalizer=normalizer.state(),
               adapter=adapter.state() if method!='motion' else None,actual_dtype='float32')
    binding['method_state_sha256']=hashlib.sha256(runtime.canonical(extra).encode()).hexdigest()
    spec=dict(schema='full_training_record_spec_v1',updates=1000,R_per_update=3,S_per_update=1,checkpoint_interval=50,
        test116187_sealed=True,binding=binding,runtime=dict(device='cuda:0',device_name=torch.cuda.get_device_name(0),
            torch_version=torch.__version__,python_version=sys.version,prefetch=2,amp=False,
            CUBLAS_WORKSPACE_CONFIG=os.environ.get('CUBLAS_WORKSPACE_CONFIG'),PYTHONUTF8=os.environ.get('PYTHONUTF8'),
            PYTHONIOENCODING=os.environ.get('PYTHONIOENCODING')))
    def get(domain,row):
        return cache.get(domain,row['window_uid']) if method=='motion' else cache.get(domain,row)
    def load(index):
        real=table['real'][index*3:index*3+3];synthetic=table['synthetic'][index:index+1]
        return dict(index=index,r=real,s=synthetic,real=[get('real',r) for r in real],synthetic=[get('synthetic',s) for s in synthetic])
    with OrderedPrefetch(load,range(1000),capacity=2,resource=cache) as prefetch:
        complete=recorded_train(output,spec,model,optimizer,prefetch,numeric.domain_loss,checkpoint_extra=extra)
    count=complete.get('actual_updates',complete.get('completed_updates'))
    runtime.require(complete['status'] in ('complete','safely_paused'),'未知训练终态，保留现场')
    receipt=dict(schema='v10_full_recorded_training_run_v1',status=complete['status'],binding=binding,completed_updates=count,
        real_window_exposures=3*count,synthetic_window_exposures=count,actual_dtype='float32',amp=False,
        checkpoint=runtime.read(output/'last_checkpoint.json'),full_training_record=runtime.sha(output/'training_complete.json') if count==1000 else None,
        prefetch=prefetch.stats,cache_peak_bytes=cache.peak,wall_seconds=time.perf_counter()-started,
        trainable_parameters=sum(p.numel() for p in model.parameters()),optimizer_replay=0,extra_S_not_equal_FLOPs=True)
    from training_journal import write_new
    write_new(output/'run_receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--fold',choices=runtime.FOLDS,required=True);parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--pool',choices=runtime.REGIMES,required=True);parser.add_argument('--method',choices=runtime.METHODS,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args();os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if args.execute:print(runtime.canonical(train(args.config,args.fold,args.seed,args.pool,args.method,args.output)))
    else:
        runtime.validate_job(args.config,args.fold,args.seed,args.pool,args.method)
        print(runtime.canonical(dict(status='readonly_v10_training_preflight',new_updates=0,R_windows=3000,S_windows=1000)))
