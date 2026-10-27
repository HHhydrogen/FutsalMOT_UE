"""独立有界变化编码单臂：原3000R、RS另1000S，完整记录，不恢复partial。"""
import argparse
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).parent))
import pose_velocity_learning_runtime as rt

def train(config,fold,seed,group,output):
    import torch
    started=time.perf_counter();ctx=rt.prepare(config,fold,seed,group)
    rt.validate_learning_admission(config,ctx['cfg'])
    proof=rt.read(ctx['cfg']['numeric_validation_receipt_path'])
    rt.require(proof['status']=='complete_three_groups_one_step_exact_full_records_verified'
        and proof['protocol_sha256']==rt.sha(config) and proof['all_groups_equal'] is True
        and proof['actual_diagnostic_optimizer_updates']==6,'真实数值与记录准入未通过')
    rt.require(torch.__version__=='2.6.0+cu124' and torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>1024**3,'GPU/Torch环境或余量不符')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output=rt.physical(output);rt.require(rt.EXPERIMENT in output.parents and not output.exists(),'已有run/partial或目录越界')
    model=rt.new_model(ctx,seed);optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    spec=rt.spec(ctx,model,seed,group);extra=rt.extra(ctx)
    from ordered_prefetch import OrderedPrefetch
    from recorded_association_loop import train as recorded
    with OrderedPrefetch(lambda i:rt.batch(ctx,i,group),range(1000),capacity=2,resource=ctx['cache']) as prefetch:
        complete=recorded(output,spec,model,optimizer,prefetch,ctx['numeric'].domain_loss,checkpoint_extra=extra)
    count=complete.get('actual_updates',complete.get('completed_updates'))
    rt.require(complete['status'] in ('complete','safely_paused'),'未知训练状态，保留现场')
    receipt=dict(schema='bounded_velocity_full_recorded_training_run_v1',status=complete['status'],binding=spec['binding'],
        completed_updates=count,real_window_exposures=3*count,synthetic_window_exposures=count*int(group!='T_R'),
        checkpoint=rt.read(output/'last_checkpoint.json'),full_training_record=rt.sha(output/'training_complete.json') if count==1000 else None,
        prefetch=prefetch.stats,cache_peak_bytes=ctx['cache'].peak,intervention=ctx['cache'].stats,
        wall_seconds=time.perf_counter()-started,trainable_parameters=sum(p.numel() for p in model.parameters()),
        optimizer_replay=0,amp=False,actual_dtype='float32',extra_S_not_equal_FLOPs=True)
    rt.write_new(output/'run_receipt.json',receipt)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--fold',choices=rt.FOLDS,required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--group',choices=rt.GROUPS,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if a.execute:print(rt.canonical(train(a.config,a.fold,a.seed,a.group,a.output)))
    else:
        rt.prepare(a.config,a.fold,a.seed,a.group)
        print(rt.canonical(dict(status='readonly_bounded_velocity_run_preflight',optimizer_updates=0,test_read=False)))
