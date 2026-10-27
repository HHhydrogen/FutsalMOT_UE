"""有界变化编码的独立学习身份；旧数值/数据只读引用，不伪装v10方法。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=Path('D:/projects/FutsalMOT_Research')
EXPERIMENT=RESEARCH/'pose/pose_velocity_learning_a01'
FOLDS=('game4','game6','game9')
SEEDS=(20261024,20261025,20261026)
GROUPS=('T_R','T_RS','T_shuffle_RS')
PARAMETERS=dict(updates=1000,R_per_step=3,S_per_RS_step=1,S_alpha=1/3,lr=.001,weight_decay=.0001,
    amp=False,prefetch=2,cache_bytes=268435456,observation_cache=4096,checkpoint_interval=50,
    actual_dtype='float32',selection='last1000_no_best_not_EMA',network='original_gated',delta_logit_bound=.5)

def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def rows(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x]
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def checked(ref):
    path=physical(ref['path']);require(path.is_file() and sha(path)==ref['sha256'],'来源SHA改变：'+str(path));return path
def physical(path):
    import stat
    import re
    path=Path(os.path.abspath(path))
    require(RESEARCH in path.parents,'仅允许实际DResearch物理来源/输出')
    require(not any(part.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',part.lower()) for part in path.parts),
        '最终测试来源继续封存')
    for part in (path,*path.parents):
        if part.exists() or part.is_symlink():
            s=part.lstat();require(not stat.S_ISLNK(s.st_mode) and not getattr(s,'st_file_attributes',0)&0x400,'拒绝重解析点')
    return path
def write_new(path,value):
    from training_journal import write_new as write
    write(path,value)
def expected_matrix():return [dict(fold=f,seed=s,group=g) for f in FOLDS for s in SEEDS for g in GROUPS]
def validate_matrix(cfg):
    require(cfg.get('schema')=='bounded_velocity_recorded_training_protocol_v1' and cfg.get('training_matrix')==expected_matrix()
        and cfg.get('parameters')==PARAMETERS and cfg.get('test116187_sealed') is True,'固定27臂/预算/测试封存')
    require(cfg.get('approved_by')=='root' and cfg.get('training_authorized') is True and cfg.get('tracking_authorized') is False,
        '独立学习准入未签署')

def load_source(cfg):
    source_path=checked(cfg['source_training_protocol']);source=read(source_path)
    require(source_path==RESEARCH/'pose/multiseed_v10_a01/training_frozen_a01/protocol.json','只读复用原v10来源')
    oldroot=Path(source['bundle'])
    for item in read(checked(source['bundle_manifest']))['files']:
        require(sha(oldroot/item['path'])==item['sha256'],'原来源执行闭包改变')
    spec=importlib.util.spec_from_file_location('velocity_source_v10_runtime',oldroot/'tools/research_ops/v10_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    numeric,base,_=module.load_numeric(source)
    # 原数值导入会前置旧工具目录；记录与新方法始终取当前不可变bundle。
    sys.path[:0]=[str(ROOT/'tools/research_ops'),str(ROOT/'tools/performance')]
    return source,module,numeric,base

def validate_protocol(config):
    cfg=read(config);validate_matrix(cfg)
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==RESEARCH/'code','只从独立冻结bundle执行')
    for item in read(checked(cfg['bundle_manifest']))['files']:
        require(sha(physical(ROOT/item['path']))==item['sha256'],'有界变化执行源码改变')
    contract=read(checked(cfg['bounded_CPU_contract']))
    require(contract['status']=='complete_three_base_R_bounded_velocity_CPU_contract_candidate_not_trained','缺实际CPU合同')
    return cfg

def validate_learning_admission(config,cfg):
    admission=read(cfg['learning_admission_root_path'])
    require(admission['status']=='complete_bounded_velocity_training_numeric_full_record_admission'
        and admission['approved_by']=='root' and admission['protocol']==dict(path=str(Path(config)),sha256=sha(config))
        and admission['formal_optimizer_updates']==0 and admission['test_read'] is False,'缺独立实际学习准入根')
    cpu=read(checked(admission['input_contract']));numeric=read(checked(admission['numeric_validation']))
    require(cpu['status']=='complete9_matched_bounded_velocity_inputs_shuffle_coverage_CPU_verified'
        and cpu['protocol_sha256']==numeric['protocol_sha256']==sha(config) and numeric['all_groups_equal'] is True
        and numeric['status']=='complete_three_groups_one_step_exact_full_records_verified','实际输入/数值/记录来源不同')
    return admission

def prepare(config,fold,seed,group):
    cfg=validate_protocol(config);require(dict(fold=fold,seed=seed,group=group) in cfg['training_matrix'],'未登记训练单元')
    source,old,numeric,base=load_source(cfg)
    refs=source['folds'][fold]
    real=rows(checked(refs['real_pool']));synthetic=rows(checked(source['synthetic_pools']['balanced']))
    table=read(checked(source['exposures']['balanced'][fold][str(seed)]))
    original=read(checked(refs['exposures'][str(seed)]))
    pools=old.validate_exposures(real,synthetic,table,original,fold)
    from pose_velocity_learning_inputs import Adapter,LearningCache
    artifact=read(checked(cfg['adapters'][fold]))
    require(artifact['base_R_pool']==refs['real_pool'] and artifact['old_normalizer']==refs['normalizer']
        and artifact['quality_scale']==refs['quality_scale'] and artifact['fit_external_or_S'] is False,'标准化只允许原基础R')
    adapter=Adapter.from_state(artifact['adapter'],numeric)
    reference=read(checked(source['reference_R']['gated'][fold][str(seed)]['training_receipt']))
    require(reference['status']=='complete' and reference['completed_updates']==1000
        and reference['real_window_exposures']==3000 and reference['synthetic_window_exposures']==0,'原R参考身份/预算不符')
    r_chain=hashlib.sha256(canonical([r['window_uid'] for r in table['real']]).encode()).hexdigest()
    require(r_chain==reference['binding']['R_window_UID_chain_sha256'],'原3000R顺序改变')
    cache=LearningCache(numeric,pools,adapter,seed,shuffle=group=='T_shuffle_RS')
    return dict(cfg=cfg,numeric=numeric,base=base,pools=pools,table=table,adapter=adapter,cache=cache,reference=reference,
        config_path=Path(config),protocol_sha256=sha(config),fold=fold,seed=seed,group=group)

def new_model(ctx,seed):
    model=ctx['numeric'].make_model(seed,'gated').to('cuda:0')
    require(ctx['base'].model_sha(model)==ctx['reference']['binding']['initialization_sha256'],'原gated初始化改变')
    require(sum(p.numel() for p in model.parameters())==20098,'名义网络容量改变')
    return model

def extra(ctx):
    return dict(schema='bounded_velocity_association_method_state_v1',group=ctx['group'],adapter=ctx['adapter'].state(),
        network='original_gated',actual_dtype='float32',original_quality_gate=True)

def spec(ctx,model,seed,group,diagnostic=False):
    import torch
    binding=dict(protocol_sha256=ctx['protocol_sha256'],fold=ctx['fold'],seed=seed,group=group,
        initialization_sha256=ctx['base'].model_sha(model),motion_base_initialization_sha256=ctx['base'].model_sha(model.base),
        R_window_UID_chain_sha256=hashlib.sha256(canonical([r['window_uid'] for r in ctx['table']['real']]).encode()).hexdigest(),
        S_window_UID_chain_sha256=hashlib.sha256(canonical([r['window_uid'] for r in ctx['table']['synthetic']] if group!='T_R' else []).encode()).hexdigest(),
        method_state_sha256=hashlib.sha256(canonical(extra(ctx)).encode()).hexdigest(),source_training_protocol=ctx['cfg']['source_training_protocol'])
    if diagnostic:binding['diagnostic_only_one_update_not_formal_training']=True
    return dict(schema='full_training_record_spec_v1',updates=1000,R_per_update=3,S_per_update=int(group!='T_R'),
        checkpoint_interval=50,test116187_sealed=True,binding=binding,runtime=dict(device='cuda:0',device_name=torch.cuda.get_device_name(0),
            python_version=sys.version,torch_version=torch.__version__,amp=False,prefetch=2,
            CUBLAS_WORKSPACE_CONFIG=os.environ.get('CUBLAS_WORKSPACE_CONFIG'),PYTHONUTF8=os.environ.get('PYTHONUTF8'),
            PYTHONIOENCODING=os.environ.get('PYTHONIOENCODING')))

def batch(ctx,index,group):
    rr=ctx['table']['real'][3*index:3*index+3];ss=ctx['table']['synthetic'][index:index+1] if group!='T_R' else []
    return dict(index=index,r=rr,s=ss,real=[ctx['cache'].get('real',r) for r in rr],synthetic=[ctx['cache'].get('synthetic',s) for s in ss])
def batches(ctx,group,limit=1000):
    for index in range(limit):yield batch(ctx,index,group)

def audit_steps(logs,table,group):
    require(len(logs)==1000,'实际1000更新不足');chain='0'*64
    for index,entry in enumerate(logs):
        row=dict(entry);saved=row.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        require(chain==saved and row['actual_update']==index+1 and row['update_index']==index
            and row['real']==table['real'][3*index:3*index+3] and row['R_windows']==3
            and row['synthetic']==(table['synthetic'][index:index+1] if group!='T_R' else [])
            and row['S_windows']==int(group!='T_R'),'实际窗口顺序/更新链不符')
        for domain,key in (('real','R'),('synthetic','S')):
            require(row[key+'_pairs']==sum(x['candidate_pairs'] for x in row[domain])
                and row[key+'_known_pairs']==sum(x['labelled_pairs'] for x in row[domain]),'all/known pair记账不符')
        require(row['learning_rates']==[.001] and row['grad_l2']>=0 and row['step_wall_seconds']>=0,'缺实测LR/梯度/耗时')
    return chain

def complete_model(config,run,all_checkpoints=False):
    import torch
    cfg=validate_protocol(config);run=physical(run);receipt=read(run/'run_receipt.json');binding=receipt['binding']
    require(receipt['schema']=='bounded_velocity_full_recorded_training_run_v1' and receipt['status']=='complete'
        and binding['protocol_sha256']==sha(config) and receipt['completed_updates']==1000,'独立last1000身份未完成')
    job={k:binding[k] for k in ('fold','seed','group')};require(job in cfg['training_matrix'],'未登记模型')
    source=read(checked(cfg['source_training_protocol']));table=read(checked(source['exposures']['balanced'][binding['fold']][str(binding['seed'])]))
    logs=rows(run/'steps.jsonl');chain=audit_steps(logs,table,binding['group']);complete=read(run/'training_complete.json');last=read(run/'last_checkpoint.json')
    require(complete['status']=='complete' and complete['actual_updates']==1000 and complete['exposure_chain']==last['exposure_chain']==chain
        and complete['steps_sha256']==sha(run/'steps.jsonl') and len(complete['checkpoints'])==21
        and {c['completed_updates'] for c in complete['checkpoints']}==set(range(0,1001,50))
        and complete['totals']['R_windows']==3000 and complete['totals']['S_windows']==1000*int(binding['group']!='T_R')
        and receipt['full_training_record']==sha(run/'training_complete.json'),'实际预算/完整记录不足')
    transaction=read(run/'update_transaction.json');require(transaction['status']=='committed'
        and transaction['completed_updates']==1000 and transaction['chain_sha256']==chain,'末更新未提交')
    saved=None
    for point in complete['checkpoints'] if all_checkpoints else [last]:
        require(Path(point['path'])==run/'checkpoints'/('step_%04d.pt'%point['completed_updates']),'检查点路径不同')
        payload=torch.load(checked(point),map_location='cpu',weights_only=False);step=point['completed_updates']
        require(payload['schema']=='full_training_checkpoint_v1' and payload['binding']==binding and payload['completed_updates']==step
            and payload['exposure_chain']==('0'*64 if step==0 else logs[step-1]['chain_sha256'])
            and all(k in payload for k in ('model','optimizer','rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda'))
            and payload['rng_torch_cuda'] is not None and payload['optimizer']['param_groups']
            and (not step or payload['optimizer']['state']) and payload['extra']['schema']=='bounded_velocity_association_method_state_v1'
            and hashlib.sha256(canonical(payload['extra']).encode()).hexdigest()==binding['method_state_sha256'],'模型/优化器/完整RNG或方法身份不符')
        if step==1000:saved=payload
    _,_,numeric,base=load_source(cfg)
    from pose_velocity_learning_inputs import Adapter
    adapter=Adapter.from_state(saved['extra']['adapter'],numeric);model=numeric.make_model(binding['seed'],'gated')
    require(base.model_sha(model)==binding['initialization_sha256'],'检查点初始化来源不同')
    model.load_state_dict(saved['model']);model.eval()
    return cfg,numeric,model,adapter,binding
