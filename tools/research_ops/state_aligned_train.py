"""新R来源单臂完整训练：原强motion数学，独立身份与逐步记录。"""
import argparse
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).parent))
import state_aligned_training_runtime as rt

def run(config,output,fold,seed,regime,diagnostic_updates=None):
    import torch
    started=time.perf_counter();ctx=rt.prepare(config,fold,seed,regime)
    if diagnostic_updates is None:rt.validate_learning_admission(config,ctx['cfg'])
    else:rt.require(diagnostic_updates==1,'仅显式一步诊断，不允许缩减正式训练')
    rt.require(torch.__version__=='2.6.0+cu124' and torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>2147483648,'GPU/Torch环境或2GiB余量不符')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output=rt.physical(output);rt.require(rt.EXPERIMENT in output.parents and not output.exists(),'独立新run/partial拒绝覆盖')
    model=rt.new_model(ctx);optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    spec=rt.spec(ctx,model,diagnostic=diagnostic_updates is not None);extra=rt.extra(ctx)
    from ordered_prefetch import OrderedPrefetch
    from recorded_association_loop import train as recorded
    with OrderedPrefetch(lambda i:rt.batch(ctx,i),range(1000 if diagnostic_updates is None else 1),capacity=2,resource=ctx['cache']) as prefetch:
        complete=recorded(output,spec,model,optimizer,prefetch,ctx['numeric'].domain_loss,checkpoint_extra=extra,diagnostic_updates=diagnostic_updates)
    count=complete.get('actual_updates',complete.get('completed_updates'))
    rt.require(complete['status'] in ('complete','safely_paused','diagnostic_only'),'未知终态，保留现场')
    receipt=dict(schema='state_aligned_full_recorded_training_run_v1',status=complete['status'],binding=spec['binding'],completed_updates=count,
        real_window_exposures=3*count,synthetic_window_exposures=count*int(regime=='RS'),checkpoint=rt.read(output/'last_checkpoint.json'),
        full_training_record=rt.sha(output/'training_complete.json') if count==1000 else None,prefetch=prefetch.stats,cache_peak_bytes=ctx['cache'].peak,
        wall_seconds=time.perf_counter()-started,trainable_parameters=sum(p.numel() for p in model.parameters()),optimizer_replay=0,
        amp=False,actual_dtype='float32',epoch_augmentation=False,extra_S_not_equal_FLOPs=True)
    rt.write_new(output/'run_receipt.json',receipt);return receipt

def train(config,fold,seed,regime,output):return run(config,output,fold,seed,regime)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--fold',choices=rt.FOLDS,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--regime',choices=rt.REGIMES,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args();os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if a.execute:print(rt.canonical(run(a.config,a.output,a.fold,a.seed,a.regime)))
    else:rt.prepare(a.config,a.fold,a.seed,a.regime);print(rt.canonical(dict(status='readonly_state_aligned_training_preflight',optimizer_updates=0,test_read=False)))
