"""候选集合监督真实CUDA一步准入：手写目标对比完整记录循环及0/1检查点。"""
import argparse,copy,hashlib,importlib,math,os,random,sys,traceback
from collections.abc import Mapping
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import set_supervision_training_runtime as rt

STATUS='complete_R_set_supervision_CPU_CUDA_full_record_numeric_admission'
RNG_KEYS=('rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda')
def tree_equal(a,b,torch,np):
    if torch.is_tensor(a) or torch.is_tensor(b):return torch.is_tensor(a) and torch.is_tensor(b) and a.dtype==b.dtype and tuple(a.shape)==tuple(b.shape) and torch.equal(a.detach().cpu(),b.detach().cpu())
    if isinstance(a,np.ndarray) or isinstance(b,np.ndarray):return isinstance(a,np.ndarray) and isinstance(b,np.ndarray) and a.dtype==b.dtype and a.shape==b.shape and np.array_equal(a,b)
    if isinstance(a,Mapping) or isinstance(b,Mapping):return isinstance(a,Mapping) and isinstance(b,Mapping) and a.keys()==b.keys() and all(tree_equal(a[k],b[k],torch,np) for k in a)
    if isinstance(a,(list,tuple)) or isinstance(b,(list,tuple)):return type(a) is type(b) and len(a)==len(b) and all(tree_equal(x,y,torch,np) for x,y in zip(a,b))
    if type(a) is not type(b):return False
    return a==b
def rng_snapshot(torch,np):return dict(rng_python=copy.deepcopy(random.getstate()),rng_numpy=copy.deepcopy(np.random.get_state()),rng_torch_cpu=torch.get_rng_state().clone(),rng_torch_cuda=[v.clone() for v in torch.cuda.get_rng_state_all()])
def restore_rng(state,torch,np):
    random.setstate(state['rng_python']);np.random.set_state(state['rng_numpy']);torch.set_rng_state(state['rng_torch_cpu']);torch.cuda.set_rng_state_all(state['rng_torch_cuda'])
def manual_r_loss(model,windows):
    """独立手写每窗集合softmax，固定null logit0，unknown已按冻结缓存排除。"""
    import torch
    counts=[window['labels'].numel() for window in windows]
    rt.require(counts and all(count>0 for count in counts),'手写R窗口不能为空')
    device=next(model.parameters()).device
    features=torch.cat([window['x'] for window in windows],dim=0).to(device=device,dtype=torch.float32)
    logits=model(features).reshape(-1);values=[];offset=0
    for window,count in zip(windows,counts):
        chunk=logits[offset:offset+count];offset+=count;labels=window['labels'].to(device=chunk.device)
        rt.require(bool(torch.isfinite(chunk).all()) and bool(((labels==0)|(labels==1)).all()),'手写R损失输入异常')
        positives=torch.nonzero(labels==1,as_tuple=False).reshape(-1);rt.require(positives.numel()<=1,'known正例多于一个')
        partition=torch.logsumexp(torch.cat((chunk.new_zeros(1),chunk)),dim=0)
        values.append(partition-(chunk[positives[0]] if positives.numel()==1 else chunk.new_zeros(())))
    rt.require(offset==logits.numel(),'手写集合logit切分不足')
    return torch.stack(values).mean()
def audit_checkpoint(path,step,binding,extra,model,opt,rng,chain,torch,np):
    side=rt.read(path.with_suffix('.json'));rt.require(Path(rt.checked(side))==path,'检查点sidecar来源/SHA不同')
    saved=torch.load(path,map_location='cpu',weights_only=False);eq=lambda a,b:tree_equal(a,b,torch,np)
    rt.require(saved['schema']=='full_training_checkpoint_v1' and saved['completed_updates']==step
        and eq(saved['binding'],binding) and eq(saved['extra'],extra) and saved['exposure_chain']==chain,
        '0/1检查点绑定/方法/曝光链不同')
    rt.require(eq(saved['model'],model) and eq(saved['optimizer'],opt),'完整模型/AdamW状态不逐值一致')
    rt.require(all(k in saved for k in RNG_KEYS) and saved['rng_torch_cuda'] is not None
        and eq({k:saved[k] for k in RNG_KEYS},rng),'Python/NumPy/Torch CPU/CUDA RNG状态不完整或不同')
    return dict(path=str(path),sha256=rt.sha(path),completed_updates=step,model_equal=True,optimizer_equal=True,all_RNG_equal=True)
def preflight(config,output,config_sha=None):
    cfg=rt.validate_protocol(config);output=rt.physical(output)
    rt.require(rt.EXPERIMENT in output.parents and not output.exists(),'数值准入必须写新目录且位于独立实验根')
    rt.require(Path(cfg['numeric_admission']['path'])==output/'receipt.json','准入收据必须绑定冻结输出路径')
    if config_sha is not None:rt.require(rt.sha(config)==config_sha,'配置SHA调用值不同')
    return cfg,dict(status='readonly_R_set_supervision_numeric_preflight',formal_optimizer_updates=0,
        diagnostic_optimizer_updates=8,groups=['R','RS'],devices=['cpu','cuda:0'],test_read=False)
def run(config,output,config_sha=None):
    cfg,flight=preflight(config,output,config_sha)
    import numpy as np,torch
    from training_journal import write_new
    from set_supervision_train import run as recorded_run
    rt.require(torch.__version__=='2.6.0+cu124' and torch.cuda.is_available(),'必须使用冻结研究CUDA/Torch环境')
    rt.require(torch.cuda.mem_get_info()[0]>2147483648,'CUDA需保留至少2GiB')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output.mkdir(parents=True);write_new(output/'preflight.json',flight)
    write_new(output/'started.json',dict(status='started_R_set_supervision_one_step_diagnostic_not_formal_training',
        protocol_sha256=rt.sha(config),formal_optimizer_updates=0,planned_diagnostic_optimizer_updates=8,
        manual_optimizer_updates=4,recorded_optimizer_updates=4,
        created_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid()))
    rows=[];manual_updates=0
    try:
        oldrt=rt.load_source_runtime(config)[1];fold,seed=rt.FOLDS[0],rt.SEEDS[0]
        shared_R=None;shared_init=None
        for device in ('cpu','cuda:0'):
          for regime in rt.REGIMES:
            random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            manual_ctx=rt.prepare(config,fold,seed,regime);logged_ctx=rt.prepare(config,fold,seed,regime)
            manual_batch=oldrt.batch(manual_ctx,0,regime);logged_batch=oldrt.batch(logged_ctx,0,regime)
            eq=lambda a,b:tree_equal(a,b,torch,np)
            rt.require(eq(manual_batch,logged_batch),'两独立首批R/S窗口、特征、标签、顺序不逐值相同')
            if shared_R is None:shared_R=copy.deepcopy((logged_batch['r'],logged_batch['real']))
            elif regime=='RS':rt.require(eq(shared_R,(logged_batch['r'],logged_batch['real'])),'R与RS实窗及194维特征不相同')
            manual=oldrt.new_model(manual_ctx,seed,device=device);model=oldrt.new_model(logged_ctx,seed,device=device)
            rt.require(eq(manual.state_dict(),model.state_dict()),'独立初始化不逐值一致')
            initial_model=copy.deepcopy(model.state_dict());init_sha=logged_ctx['base'].model_sha(model)
            if shared_init is None:shared_init=init_sha
            rt.require(init_sha==shared_init and sum(p.numel() for p in model.parameters())==14593,'原14593参数初始化不一致')
            manual_opt=torch.optim.AdamW(manual.parameters(),lr=.001,weight_decay=.0001)
            optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
            initial_optimizer=copy.deepcopy(optimizer.state_dict());spec=rt.spec(logged_ctx,model,diagnostic=True);extra=rt.extra(logged_ctx)
            rt.require(spec['schema']=='full_training_record_spec_v1' and spec['binding']['protocol_sha256']==rt.sha(config)
                and spec['R_per_update']==3 and spec['S_per_update']==int(regime=='RS')
                and spec['binding']['R_objective']=='candidate_set_CE_fixed_no_match_logit_0','训练记录schema/损失身份/曝光预算不符')
            begin_rng=rng_snapshot(torch,np);manual_opt.zero_grad(set_to_none=True)
            rloss=manual_r_loss(manual,manual_batch['real'])
            sloss=manual_ctx['numeric'].domain_loss(manual,manual_batch['synthetic']) if regime=='RS' else None
            total=rloss+sloss/3 if sloss is not None else rloss
            rt.require(bool(torch.isfinite(total)),'手写总loss非有限');total.backward()
            grads=[p.grad.detach().reshape(-1) for p in manual.parameters() if p.grad is not None]
            rt.require(grads and bool(torch.isfinite(torch.cat(grads)).all()),'手写梯度非有限')
            grad_l2=float(torch.linalg.vector_norm(torch.cat(grads)));manual_opt.step();manual_updates+=1
            expected_rng=rng_snapshot(torch,np);restore_rng(begin_rng,torch,np)
            run_dir=output/device.replace(':','_')/regime/'recorded'
            receipt=recorded_run(config,run_dir,fold,seed,regime,diagnostic_updates=1,device=device)
            logged=oldrt.rows(run_dir/'steps.jsonl');rt.require(len(logged)==1 and receipt['completed_updates']==1,'记录实现未恰好产生单诊断步')
            row=logged[0]
            rt.require(row['loss']==float(total.detach()) and row['real_loss']==float(rloss.detach())
                and row['synthetic_loss']==(float(sloss.detach()) if sloss is not None else None)
                and row['grad_l2']==grad_l2 and row['learning_rates']==[.001],
                '手写集合目标与训练记录loss/梯度/LR不逐值一致')
            saved=torch.load(run_dir/'checkpoints/step_0001.pt',map_location='cpu',weights_only=False)
            rt.require(eq(manual.state_dict(),saved['model']) and eq(manual_opt.state_dict(),saved['optimizer']),
                '手写更新与记录后模型/AdamW不逐值一致')
            rt.require(eq(expected_rng,rng_snapshot(torch,np)),'手写/记录完整RNG状态不逐值一致')
            for field,expected in [('R_pairs',sum(w['candidate_pairs'] for w in logged_batch['real'])),
                ('R_known_pairs',sum(w['known_pairs'] for w in logged_batch['real'])),
                ('S_pairs',sum(w['candidate_pairs'] for w in logged_batch['synthetic'])),
                ('S_known_pairs',sum(w['known_pairs'] for w in logged_batch['synthetic']))]:
                rt.require(row[field]==expected,'R/S全部与known pair记账不同')
            chain=hashlib.sha256(('0'*64+rt.canonical({k:v for k,v in row.items() if k!='chain_sha256'})).encode()).hexdigest()
            rt.require(row['chain_sha256']==chain,'训练记录链SHA不同')
            audits=[]
            for step,model_state,opt_state,rng,exposure_chain in ((0,initial_model,initial_optimizer,begin_rng,'0'*64),
                (1,manual.state_dict(),manual_opt.state_dict(),expected_rng,chain)):
                audits.append(audit_checkpoint(run_dir/f'checkpoints/step_{step:04d}.pt',step,spec['binding'],extra,
                    model_state,opt_state,rng,exposure_chain,torch,np))
            rows.append(dict(device=device,regime=regime,fold=fold,seed=seed,R_rows=3,S_rows=int(regime=='RS'),
                R_loss=float(rloss.detach()),S_loss=float(sloss.detach()) if sloss is not None else None,
                combined_loss=float(total.detach()),grad_l2=grad_l2,checkpoints=audits,record_sha256=rt.sha(run_dir/'steps.jsonl')))
        result=dict(status=STATUS,protocol_sha256=rt.sha(config),formal_optimizer_updates=0,
            actual_diagnostic_optimizer_updates=8,diagnostic_R_windows=24,diagnostic_S_windows=4,
            R_RS_same_R_batch_and_initialization=True,manual_vs_recorded_loss_gradient_parameters_AdamW_and_RNG_exact=True,
            CPU_and_CUDA_actual_model_steps_verified=True,full_step0_step1_checkpoints_verified=True,
            all_groups_equal=True,groups=rows,test_read=False,model_prediction=0,tracking=0)
        write_new(output/'receipt.json',result);return result
    except BaseException as error:
        write_new(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc(),
            manual_optimizer_updates_returned=manual_updates,formal_optimizer_updates=0,
            uncommitted_effects_not_guessed=True,protocol_sha256=rt.sha(config),test_read=False))
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--config-sha256');p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(rt.canonical(run(a.config,a.output,a.config_sha256) if a.execute else preflight(a.config,a.output,a.config_sha256)[1]))
