"""自由状态R来源学习的独立方法身份；数值与完整记录复用原强motion。"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=Path('D:/projects/FutsalMOT_Research')
EXPERIMENT=RESEARCH/'pose/state_aligned_training_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
PARAMETERS=dict(updates=1000,R_per_step=3,S_per_RS_step=1,S_alpha=1/3,lr=.001,weight_decay=.0001,
    amp=False,prefetch=2,cache_bytes=268435456,checkpoint_interval=50,actual_dtype='float32',
    selection='last1000_no_best_not_EMA',network='194_64_32_1_ReLU_strongmotion',use_pose=False,epoch_augmentation=False)

def require(ok,message):
    if not ok:raise ValueError(message)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def rows(path):
    with Path(path).open(encoding='utf-8-sig') as stream:return [json.loads(line) for line in stream if line.strip()]
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def physical(path):
    path=Path(os.path.abspath(path))
    require(RESEARCH in path.parents and not any(p.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',p.lower()) for p in path.parts),'仅实际DResearch，测试封存')
    for p in (path,*path.parents):
        if p.exists() or p.is_symlink():require(not p.is_symlink() and not getattr(p.lstat(),'st_file_attributes',0)&0x400,'拒绝junction/符号链接')
    return path
def checked(reference):
    p=physical(reference['path']);require(p.is_file() and sha(p)==reference['sha256'],'来源SHA不同：'+str(p));return p
def write_new(path,value):
    from training_journal import write_new as write
    write(path,value)
def expected_matrix():return [dict(fold=f,seed=s,regime=g) for f in FOLDS for s in SEEDS for g in REGIMES]
def validate_matrix(cfg):
    require(cfg.get('schema')=='state_aligned_R_recorded_training_protocol_v1' and cfg.get('training_matrix')==expected_matrix()
        and cfg.get('parameters')==PARAMETERS and cfg.get('test116187_sealed') is True,'固定18臂/原强motion/预算/测试封存不同')
    require(cfg.get('approved_by')=='root' and cfg.get('training_authorized') is True and cfg.get('tracking_authorized') is False,'独立训练协议尚未签署')
def validate_protocol(config):
    cfg=read(config);validate_matrix(cfg)
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==RESEARCH/'code','必须从本轮冻结bundle执行')
    for item in read(checked(cfg['bundle_manifest']))['files']:
        require(sha(physical(ROOT/item['path']))==item['sha256'],'活动源码变化')
    return cfg
def prepare(config,fold,seed,regime):
    cfg=validate_protocol(config);require(dict(fold=fold,seed=seed,regime=regime) in cfg['training_matrix'],'未登记学习单元')
    from state_aligned_training_inputs import prepare_inputs
    ctx=prepare_inputs(config,fold,seed,regime)
    require(isinstance(ctx,dict) and ctx['cfg']==cfg and ctx['fold']==fold and ctx['seed']==seed and ctx['regime']==regime,'输入上下文来源/单元不同')
    ctx.update(config_path=Path(config),protocol_sha256=sha(config))
    # 输入来源模块载入原数值后可能前置旧工具目录；记录始终取新冻结闭包。
    sys.path[:0]=[str(ROOT/'tools/research_ops'),str(ROOT/'tools/performance')]
    ctx['cache']=ctx['base'].FeatureCache(ctx['pools'],ctx['normalizer'],False,limit=268435456)
    return ctx
def new_model(ctx,seed=None,device='cuda:0'):
    from grf_ue_bridge.learned_association_model_v8 import make_model
    seed=ctx['seed'] if seed is None else seed
    require(seed==ctx['seed'],'初始化seed与单元不同')
    model=make_model(seed).to(device)
    require(ctx['base'].model_sha(model)==ctx['reference']['binding']['initialization_sha256'],'原强motion初始化不同')
    require(sum(p.numel() for p in model.parameters())==14593 and all(p.requires_grad for p in model.parameters()),'网络容量/可训练层改变')
    return model
def extra(ctx):
    return dict(schema='state_aligned_strongmotion_method_state_v1',method='motion',regime=ctx['regime'],normalizer=ctx['normalizer'].state(),
        actual_dtype='float32',use_pose=False,epoch_augmentation=False,R_window_source='free_state_R_only_teacher_bank',
        source_training_protocol=ctx['cfg']['source_training_protocol'])
def spec(ctx,model,seed=None,regime=None,diagnostic=False):
    import torch
    seed=ctx['seed'] if seed is None else seed;regime=ctx['regime'] if regime is None else regime
    require(seed==ctx['seed'] and regime==ctx['regime'],'spec单元不同')
    binding=dict(protocol_sha256=ctx['protocol_sha256'],fold=ctx['fold'],seed=seed,regime=regime,method='motion',
        initialization_sha256=ctx['base'].model_sha(model),
        R_window_UID_chain_sha256=hashlib.sha256(canonical([r['window_uid'] for r in ctx['table']['real']]).encode()).hexdigest(),
        S_window_UID_chain_sha256=hashlib.sha256(canonical([r['window_uid'] for r in ctx['table']['synthetic']] if regime=='RS' else []).encode()).hexdigest(),
        method_state_sha256=hashlib.sha256(canonical(extra(ctx)).encode()).hexdigest(),source_training_protocol=ctx['cfg']['source_training_protocol'])
    if diagnostic:binding['diagnostic_only_one_update_not_formal_training']=True
    device=str(next(model.parameters()).device)
    return dict(schema='full_training_record_spec_v1',updates=1000,R_per_update=3,S_per_update=int(regime=='RS'),checkpoint_interval=50,
        test116187_sealed=True,binding=binding,runtime=dict(device=device,device_name=torch.cuda.get_device_name(0) if device.startswith('cuda') else 'CPU_numeric_diagnostic',
            python_version=sys.version,torch_version=torch.__version__,amp=False,prefetch=2,
            CUBLAS_WORKSPACE_CONFIG=os.environ.get('CUBLAS_WORKSPACE_CONFIG'),PYTHONUTF8=os.environ.get('PYTHONUTF8'),PYTHONIOENCODING=os.environ.get('PYTHONIOENCODING')))
def batch(ctx,index,regime=None):
    regime=ctx['regime'] if regime is None else regime;require(regime==ctx['regime'] and type(index) is int and 0<=index<1000,'步序/组别不同')
    rr=ctx['table']['real'][index*3:index*3+3];ss=ctx['table']['synthetic'][index:index+1] if regime=='RS' else []
    require(len(rr)==3 and len(ss)==int(regime=='RS'),'输入预算不足')
    get=ctx['cache'].get
    return dict(index=index,r=rr,s=ss,real=[get('real',r['window_uid']) for r in rr],synthetic=[get('synthetic',s['window_uid']) for s in ss])
def batches(ctx,regime=None,limit=1000):
    require(type(limit) is int and 1<=limit<=1000,'有界步数')
    for index in range(limit):yield batch(ctx,index,regime)
def validate_learning_admission(config,cfg):
    a=read(cfg['learning_admission_root_path']);n=read(checked(a['numeric_validation']));inputs=read(checked(a['input_contract']))
    protocol=dict(path=str(Path(config)),sha256=sha(config))
    require(a['status']=='complete_state_aligned_R_training_numeric_full_record_admission' and a['approved_by']=='root' and a['protocol']==protocol
        and a['formal_optimizer_updates']==0 and a['test_read'] is False,'缺本轮实际训练准入根')
    require(n['status']=='complete_R_RS_one_step_exact_full_records_verified' and n['protocol_sha256']==inputs['protocol_sha256']==protocol['sha256']
        and n['all_groups_equal'] is True and n['actual_diagnostic_optimizer_updates']==4
        and inputs['status']=='complete9_state_aligned_R_inputs_original_motion_numeric_verified','缺完整输入/两组CUDA数值及记录证据')
    return a
def validate_training_admission(config,cfg):return validate_learning_admission(config,cfg)
def audit_steps(logs,table,regime):
    require(regime in REGIMES and len(logs)==1000,'实际完整1000更新不足');chain='0'*64
    for i,entry in enumerate(logs):
        row=dict(entry);saved=row.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        require(chain==saved and row['actual_update']==i+1 and row['update_index']==i and row['R_windows']==3 and row['S_windows']==int(regime=='RS')
            and row['real']==table['real'][3*i:3*i+3] and row['synthetic']==(table['synthetic'][i:i+1] if regime=='RS' else []),'实际步链/窗口或域顺序不同')
        for domain,key in (('real','R'),('synthetic','S')):
            require(row[key+'_pairs']==sum(x['candidate_pairs'] for x in row[domain]) and row[key+'_known_pairs']==sum(x['labelled_pairs'] for x in row[domain]),'all/known pair记账不同')
        require(row['learning_rates']==[.001] and row['grad_l2']>=0 and row['step_wall_seconds']>=0,'缺逐步实测LR/梯度/耗时')
    return chain
def complete_model(config,run,all_checkpoints=False):
    import torch
    cfg=validate_protocol(config);run=physical(run);receipt=read(run/'run_receipt.json');binding=receipt['binding']
    require(receipt['schema']=='state_aligned_full_recorded_training_run_v1' and receipt['status']=='complete' and receipt['completed_updates']==1000
        and binding['protocol_sha256']==sha(config) and binding['method']=='motion','独立新R来源last1000身份不完整')
    unit={k:binding[k] for k in ('fold','seed','regime')};require(unit in cfg['training_matrix'],'单元不属18臂矩阵')
    ctx=prepare(config,**unit);logs=rows(run/'steps.jsonl');chain=audit_steps(logs,ctx['table'],binding['regime'])
    complete=read(run/'training_complete.json');last=read(run/'last_checkpoint.json');tx=read(run/'update_transaction.json')
    require(complete['schema']=='full_training_process_complete_v1' and complete['status']=='complete' and complete['actual_updates']==1000
        and complete['exposure_chain']==last['exposure_chain']==chain and complete['steps_sha256']==sha(run/'steps.jsonl')
        and len(complete['checkpoints'])==21 and {x['completed_updates'] for x in complete['checkpoints']}==set(range(0,1001,50))
        and complete['totals']['R_windows']==3000 and complete['totals']['S_windows']==1000*int(binding['regime']=='RS')
        and receipt['full_training_record']==sha(run/'training_complete.json'),'预算、完整21检查点或记录链不同')
    require(tx['status']=='committed' and tx['completed_updates']==1000 and tx['chain_sha256']==chain,'末次事务未提交')
    saved=None
    for point in complete['checkpoints'] if all_checkpoints else [last]:
        step=point['completed_updates'];require(Path(point['path'])==run/'checkpoints'/('step_%04d.pt'%step),'检查点路径不同')
        payload=torch.load(checked(point),map_location='cpu',weights_only=False)
        require(payload['schema']=='full_training_checkpoint_v1' and payload['binding']==binding and payload['completed_updates']==step
            and payload['exposure_chain']==('0'*64 if step==0 else logs[step-1]['chain_sha256'])
            and {'model','optimizer','rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda'}<=set(payload)
            and payload['rng_torch_cuda'] is not None and payload['optimizer']['param_groups'] and (step==0 or payload['optimizer']['state'])
            and payload['extra']==extra(ctx) and hashlib.sha256(canonical(payload['extra']).encode()).hexdigest()==binding['method_state_sha256']
            and all(v.dtype==torch.float32 for v in payload['model'].values()),'完整模型/优化器/RNG或独立方法状态不同')
        if step==0:
            initial=new_model(ctx,device='cpu')
            require(payload['model'].keys()==initial.state_dict().keys()
                and all(torch.equal(payload['model'][key],value) for key,value in initial.state_dict().items())
                and not payload['optimizer']['state'],'step0必须原初始化且AdamW尚无更新状态')
        if step==1000:saved=payload
    require(saved is not None,'末检查点未读回');model=new_model(ctx,device='cpu')
    require(ctx['base'].model_sha(model)==binding['initialization_sha256'],'原始初始化来源不同')
    model.load_state_dict(saved['model']);model.eval()
    return cfg,ctx['numeric'],model,ctx['normalizer'],binding
