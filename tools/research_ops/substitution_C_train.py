"""C4000R新训练入口：同基础3000R，额外1000R，独立全过程记录。"""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/performance'))
from ordered_prefetch import OrderedPrefetch
from recorded_association_loop import train as recorded_train
from training_journal import write_new
import substitution_C_runtime as rt

def train(config,fold,seed,method,output):
    clock=time.perf_counter();c,n,b,pools,table,plan,norm,adapter,a=rt.job(config,fold,seed,method)
    proof=rt.read(c['numeric_validation_receipt_path'])
    rt.require(proof['status']=='complete_C_two_methods_actual_loop_equal' and proof['protocol_sha256']==rt.sha(config)
        and proof['actual_diagnostic_optimizer_updates']==4 and proof['all_equal'],'先通过C实际循环数值门禁')
    import torch
    rt.require(torch.__version__=='2.6.0+cu124' and torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>1024**3,'冻结GPU环境/余量不同')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output=rt.storage().physical_child(output,rt.EXP);rt.require(not output.exists(),'已有C run/partial，不重放')
    model,cache,get=rt.model_and_cache(n,b,pools,norm,adapter,seed,method);model.to('cuda:0')
    initial=b.model_sha(model);rt.require(initial==a['binding']['initialization_sha256'],'C初始权重不等于A/B')
    opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    extra=dict(schema='substitution_C_method_state_v1',method=method,normalizer=norm.state(),adapter=adapter.state() if method=='gated' else None,actual_dtype='float32')
    binding=dict(protocol_sha256=rt.sha(config),fold=fold,seed=seed,method=method,regime='C4000R',initialization_sha256=initial,
        R_window_UID_chain_sha256=hashlib.sha256(rt.canonical([x['window_uid'] for x in table['real']]).encode()).hexdigest(),
        extra_R_UID_chain_sha256=hashlib.sha256(rt.canonical([x['window_uid'] for x in plan['extra_R']]).encode()).hexdigest(),
        method_state_sha256=hashlib.sha256(rt.canonical(extra).encode()).hexdigest(),base_R=c['folds'][fold],extra_R=c['extra_R_complete'],analysis_plan=c['analysis_plan'])
    spec=dict(schema='full_training_record_spec_v2_real_groups',updates=1000,R_per_update=4,S_per_update=0,
        base_R_per_update=3,extra_R_per_update=1,extra_R_alpha=1/3,checkpoint_interval=50,test116187_sealed=True,
        binding=binding,runtime=dict(device='cuda:0',device_name=torch.cuda.get_device_name(0),torch_version=torch.__version__,python_version=sys.version,
            prefetch=2,amp=False,CUBLAS_WORKSPACE_CONFIG=os.environ.get('CUBLAS_WORKSPACE_CONFIG'),environment=c['environment']))
    with OrderedPrefetch(rt.batch_loader(table,plan,get),range(1000),capacity=2,resource=cache) as prefetch:
        done=recorded_train(output,spec,model,opt,prefetch,n.domain_loss,checkpoint_extra=extra)
    count=done.get('actual_updates',done.get('completed_updates'))
    receipt=dict(schema='substitution_C4000R_run_v1',status=done['status'],binding=binding,completed_updates=count,
        real_window_exposures=4*count,base_R_window_exposures=3*count,extra_R_window_exposures=count,synthetic_window_exposures=0,
        checkpoint=rt.read(output/'last_checkpoint.json'),full_training_record=rt.sha(output/'training_complete.json') if count==1000 else None,
        actual_dtype='float32',amp=False,prefetch=prefetch.stats,cache_peak_bytes=cache.peak,wall_seconds=time.perf_counter()-clock,
        trainable_parameters=sum(p.numel() for p in model.parameters()),optimizer_replay=0,extra_R_not_equal_images_or_FLOPs=True)
    write_new(output/'run_receipt.json',receipt);return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--fold',choices=rt.FOLDS,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--method',choices=rt.METHODS,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args();os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if a.execute:print(rt.canonical(train(a.config,a.fold,a.seed,a.method,a.output)))
    else:rt.job(a.config,a.fold,a.seed,a.method);print(rt.canonical(dict(status='readonly_C4000R_preflight',new_updates=0)))
