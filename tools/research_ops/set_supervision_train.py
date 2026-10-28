"""单臂R候选集合监督训练；只由新冻结协议的控制器调用。"""
import argparse, os, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import set_supervision_training_runtime as rt

def run(config,output,fold,seed,regime,diagnostic_updates=None,device='cuda:0'):
    import torch
    from training_journal import write_new
    started=time.perf_counter();ctx=rt.prepare(config,fold,seed,regime)
    if diagnostic_updates is None:
        cfg=ctx['set_cfg'];admission=rt.read(Path(cfg['numeric_admission']['path']))
        rt.require(admission.get('status')=='complete_R_set_supervision_CPU_CUDA_full_record_numeric_admission'
            and admission.get('protocol_sha256')==rt.sha(config)
            and admission.get('formal_optimizer_updates')==0
            and admission.get('actual_diagnostic_optimizer_updates')==8
            and admission.get('all_groups_equal') is True and admission.get('test_read') is False,
            '缺本轮R集合监督CPU/CUDA数值及完整记录准入')
    else:rt.require(diagnostic_updates==1,'只允许显式单步诊断，不可缩短正式预算')
    rt.require(torch.__version__=='2.6.0+cu124' and torch.cuda.is_available(),'冻结Torch/CUDA数值环境不同')
    rt.require(device in ('cpu','cuda:0'),'设备只准CPU诊断或CUDA正式设备')
    rt.require(device=='cuda:0' or diagnostic_updates is not None,
        'CPU设备仅允许明示单步数值准入，正式训练必须CUDA')
    if device=='cuda:0':rt.require(torch.cuda.mem_get_info()[0]>2147483648,'GPU余量需大于2GiB')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output=rt.physical(output);rt.require(rt.EXPERIMENT in output.parents and not output.exists(),'输出必须为新独立R集合训练attempt')
    model=ctx['set_oldrt'].new_model(ctx,device=device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    spec=rt.spec(ctx,model,diagnostic=diagnostic_updates is not None);extra=rt.extra(ctx)
    from ordered_prefetch import OrderedPrefetch
    from set_supervision_recorded_loop import train as recorded
    count=1000 if diagnostic_updates is None else 1
    with OrderedPrefetch(lambda i:ctx['set_oldrt'].batch(ctx,i,regime),range(count),capacity=2,resource=ctx['cache']) as prefetch:
        complete=recorded(output,spec,model,optimizer,prefetch,rt.r_loss,
            lambda m,w:rt.s_loss(ctx,m,w),checkpoint_extra=extra,diagnostic_updates=diagnostic_updates)
    updates=complete.get('actual_updates',complete.get('completed_updates'))
    rt.require(complete['status'] in ('complete','safely_paused','diagnostic_only'),'未知训练终态，保留现场')
    receipt=dict(schema='r_set_supervision_full_recorded_training_run_v1',status=complete['status'],
        binding=spec['binding'],completed_updates=updates,real_window_exposures=3*updates,
        synthetic_window_exposures=updates*int(regime=='RS'),checkpoint=rt.read(output/'last_checkpoint.json'),
        full_training_record=rt.sha(output/'training_complete.json') if updates==1000 else None,
        prefetch=prefetch.stats,cache_peak_bytes=ctx['cache'].peak,wall_seconds=time.perf_counter()-started,
        trainable_parameters=sum(p.numel() for p in model.parameters()),optimizer_replay=0,
        amp=False,actual_dtype='float32',epoch_augmentation=False,formal=diagnostic_updates is None,
        test_read=False)
    write_new(output/'run_receipt.json',receipt)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--fold',choices=rt.FOLDS,required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--regime',choices=rt.REGIMES,required=True);p.add_argument('--diagnostic-updates',type=int)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if not a.execute:print(rt.canonical(dict(status='readonly_r_set_supervision_preflight',optimizer_updates=0,test_read=False)))
    else:print(rt.canonical(run(a.config,a.output,a.fold,a.seed,a.regime,a.diagnostic_updates)))
