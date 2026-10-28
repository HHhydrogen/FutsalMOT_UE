"""新R来源模型追踪的独立身份及只读加载；不施加截距，不执行追踪。"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/state_aligned_training_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
OLD={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
FIXED_ARGS=dict(track_high_thresh=.25,track_low_thresh=.1,new_track_thresh=.25,track_buffer=30,match_thresh=.8,fuse_score=True)
SCHEMA='state_aligned_strongmotion_tracking_inventory_v1'
FRAMEWORK_SHA='ac50e61744e44a22c04c4169feb63112f7f0350c75b5ad344e6aec1998d38fc3'
AUDIT_STATUS='complete18_state_aligned_R_actual_budget_full_records_and_exit_verified'

def require(ok,message):
    if not ok:raise ValueError(message)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def safe(value):
    p=Path(os.path.abspath(value));require(R in p.parents,'只准物理DResearch来源')
    require(not any(v.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',v.lower()) for v in p.parts),'测试继续封存')
    for q in (p,*p.parents):
        if q.exists() or q.is_symlink():require(not q.is_symlink() and not getattr(q.lstat(),'st_file_attributes',0)&0x400,'不跟随链接/junction')
    return p
def sha(p):
    h=hashlib.sha256()
    with safe(p).open('rb') as f:
        for x in iter(lambda:f.read(1048576),b''):h.update(x)
    return h.hexdigest()
def checked(reference):
    require(isinstance(reference,dict) and set(reference)>={'path','sha256'},'来源引用不足')
    p=safe(reference['path']);require(sha(p)==reference['sha256'],'来源SHA变化：'+str(p));return p
def read_ref(reference):return json.loads(checked(reference).read_text(encoding='utf-8-sig'))
def ref(p):return dict(path=str(safe(p)),sha256=sha(p))
def module(reference,name):
    p=checked(reference);key=name+'_'+reference['sha256']
    if key not in sys.modules:
        spec=importlib.util.spec_from_file_location(key,p);m=importlib.util.module_from_spec(spec);sys.modules[key]=m
        previous=sys.dont_write_bytecode
        try:sys.dont_write_bytecode=True;spec.loader.exec_module(m)
        finally:sys.dont_write_bytecode=previous
    require(safe(sys.modules[key].__file__)==p,'模块缓存物理来源不同');return sys.modules[key]
def source(config,relative):
    manifest=read_ref(config['bundle_manifest']);items=[x for x in manifest['files'] if x['path']==relative]
    require(len(items)==1 and safe(config['bundle']).parent==R/'code','执行源码未绑定')
    value=dict(path=str(safe(config['bundle'])/relative),sha256=items[0]['sha256']);checked(value);return value

def model_id(protocol,fold,seed,regime):
    require(fold in FOLDS and seed in SEEDS and regime in REGIMES,'只准18登记单元')
    return digest([SCHEMA,protocol['sha256'],fold,seed,regime])[:24]

def model_specs(protocol,completed_state,baseline_inventory):
    """从真实18完成映射构建新身份，基线模型ID另列，不能复用为新权重ID。"""
    require(completed_state['status']=='complete18_state_aligned_training_wait_independent_audit_tracking'
        and completed_state['active'] is None and completed_state['protocol_sha256']==protocol['sha256'],'完整18训练终态不足')
    entries=completed_state['completed_train'];expected={(f,s,g) for f in FOLDS for s in SEEDS for g in REGIMES}
    require(len(entries)==18 and {(x['fold'],x['seed'],x['regime']) for x in entries}==expected,'真实18完成清单缺失或重复')
    originals=baseline_inventory['models'];require(len(originals)==18,'原180参照模型应18个')
    models=[]
    for entry in entries:
        fold,seed,regime=(entry[k] for k in ('fold','seed','regime'));run=safe(entry['path'])
        old=[x for x in originals if (x['fold'],x['seed'],x['regime'])==(fold,seed,regime)]
        require(len(old)==1,'旧参照fold/seed/regime匹配不唯一')
        identifier=model_id(protocol,fold,seed,regime);require(identifier!=old[0]['model_id'],'新权重不能伪装旧model_id')
        models.append(dict(model_id=identifier,baseline_model_id=old[0]['model_id'],fold=fold,seed=seed,regime=regime,
            method='motion',method_schema='state_aligned_strongmotion_method_state_v1',learning_protocol=deepcopy(protocol),
            run=str(run),training_receipt=dict(path=str(run/'run_receipt.json'),sha256=entry['receipt_sha256']),
            training_complete=dict(path=str(run/'training_complete.json'),sha256=entry['complete_sha256']),
            original_normalizer=deepcopy(old[0]['normalizer']),expected_initialization_sha256=old[0]['binding']['initialization_sha256'],
            use_pose=False,intercept_applied=False,method_identity='new_R_window_source_original_strongmotion'))
    return sorted(models,key=lambda x:(x['fold'],x['seed'],x['regime']))

def tracking_matrix(models,sources,panels):
    require(set(panels)=={'original_heldout','old_external','seven_observed'} and [len(panels[k]) for k in ('original_heldout','old_external','seven_observed')]==[3,2,7]
        and set(panels['original_heldout'])==set(OLD),'固定3/2/7面板，不能混比赛')
    require(set(sources)==set(sum((panels[k] for k in panels),[])) and len(sources)==12,'12来源完整且不重复')
    require(len(models)==18 and len({x['model_id'] for x in models})==18,'新18模型身份不完整')
    jobs=[]
    for spec in models:
        heldout=next(seq for seq,game in OLD.items() if game==spec['fold'])
        for sequence in [heldout]+panels['old_external']+panels['seven_observed']:
            row=dict(model_id=spec['model_id'],baseline_model_id=spec['baseline_model_id'],regime=spec['regime'],fold=spec['fold'],seed=spec['seed'],sequence=sequence)
            row['job_id']=digest(['state_aligned_new_tracking_v1',row])[:24];jobs.append(row)
    require(len(jobs)==len({j['job_id'] for j in jobs})==180,'180逻辑任务必须唯一完整');return jobs

def validate_jobs(cfg,inventory):
    require(inventory['schema']==SCHEMA and inventory['sources']==cfg['sources'] and inventory['panels']==cfg['panels'],'新模型库存来源不同')
    require(cfg['jobs']==tracking_matrix(inventory['models'],cfg['sources'],cfg['panels']),'完整180矩阵不同或按结果挑选')
    require(cfg['tracker_parameters']==FIXED_ARGS and cfg['test_sealed'] is True and cfg['new_optimizer_updates']==0,'原数值/测试封存/零更新不同')
    require('calibrations' not in cfg and 'fit_complete' not in cfg,'本轮不允许截距来源混入')
    return inventory['models']

def training_closure(cfg):
    """只读完成元数据；实际模型加载前必须独立18000更新审计及退出全齐。"""
    audit=read_ref(cfg['training_budget']);protocol=cfg['learning_protocol'];state=read_ref(audit['control_state'])
    require(audit['status']==AUDIT_STATUS and audit['protocol']==protocol and audit['training_processes_absent'] is True
        and audit['complete_checkpoints_read_back']==378 and audit['nine_paired_R_RS_exposures_equal'] is True,'完整训练预算/退出审计不足')
    totals=audit['actual_totals'];require(totals['updates']==18000 and totals['R_windows']==54000 and totals['S_windows']==9000,'实际训练总预算不同')
    require(state['status']=='complete18_state_aligned_training_wait_independent_audit_tracking' and state['active'] is None
        and len(state['completed_train'])==18,'实际训练状态不完整')
    return audit,state

def learning_loader(cfg):
    protocol=read_ref(cfg['learning_protocol']);reference=source(protocol,'tools/research_ops/state_aligned_training_runtime.py')
    loader=module(reference,'aligned_completed_training_loader');loader.validate_protocol(checked(cfg['learning_protocol']))
    return loader

def load_model(cfg,spec):
    """独立v1完整记录加载器，不包装β，不借旧模型schema。只在CPU专用进程调用。"""
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='-1','追踪加载只准CPU')
    audit,state=training_closure(cfg);baseline=read_ref(cfg['source_inventory'])
    expected=model_specs(cfg['learning_protocol'],state,baseline)
    require(spec in expected and spec['intercept_applied'] is False and spec['use_pose'] is False,'新模型身份或无截距约束不同')
    receipt=read_ref(spec['training_receipt']);read_ref(spec['training_complete'])
    require(receipt['schema']=='state_aligned_full_recorded_training_run_v1' and receipt['status']=='complete'
        and receipt['completed_updates']==1000 and receipt['epoch_augmentation'] is False,'完整独立run身份不足')
    loader=learning_loader(cfg);_,numeric,model,normalizer,binding=loader.complete_model(checked(cfg['learning_protocol']),safe(spec['run']),all_checkpoints=False)
    require(binding==receipt['binding'] and binding['initialization_sha256']==spec['expected_initialization_sha256']
        and all(binding[k]==spec[k] for k in ('fold','seed','regime')) and binding['method']=='motion','新last1000/原初始化身份不符')
    original=read_ref(spec['original_normalizer']);require(normalizer.state()==original,'新模型不得重拟合原baseR标准化')
    import torch
    require(not torch.cuda.is_initialized() and all(p.device.type=='cpu' and p.dtype==torch.float32 for p in model.parameters()),'不得初始化CUDA或改变FP32')
    require(sum(p.numel() for p in model.parameters())==14593 and not model.training,'原强motion容量/推理状态不同')
    evidence=dict(schema='state_aligned_model_loading_receipt_v1',model_id=spec['model_id'],baseline_model_id=spec['baseline_model_id'],
        method_schema=spec['method_schema'],learning_protocol=cfg['learning_protocol'],training_budget=cfg['training_budget'],
        run_receipt=spec['training_receipt'],initialization_equal_original=True,normalizer_equal_original=True,
        checkpoint='last1000_not_EMA_no_best',device='cpu',actual_dtype='float32',use_pose=False,Pose_columns_zeroed_after_normalization=170,
        intercept_applied=False,new_optimizer_updates=0,test_read=False)
    return dict(model=model,normalizer=normalizer,binding=binding,receipt=evidence)

def source_bindings(cfg):
    """原数值/GT纯函数来源只读引用，不调用原截距Bindings或旧18源预飞。"""
    inventory=read_ref(cfg['source_inventory']);velocity=read_ref(cfg['source_velocity_protocol'])
    require(inventory['sources']==velocity['sources']==cfg['sources'] and inventory['panels']==velocity['panels']==cfg['panels']
        and velocity['registries']==cfg['registries'],'必须原12源/3面板/3690事件来源')
    require(cfg['source_worker_framework']['sha256']==FRAMEWORK_SHA,'已验截距worker来源不同')
    old=read_ref(velocity['source_tracking_config']);seven=read_ref(velocity['source_seven_tracking_config']);training=read_ref(old['training_protocol']);v9=read_ref(training['v9_protocol'])
    old_rt=module(source(old,'tools/research_ops/v10_tracking_runtime.py'),'aligned_original_scope_runtime')
    return dict(inventory=inventory,velocity=velocity,old=old,seven_cfg=seven,training=training,v9=v9,old_rt=old_rt,
        seven_ref=source(seven,'tools/research_ops/substitution_tracking_runtime.py'),
        worker_framework=module(cfg['source_worker_framework'],'aligned_original_worker_framework'),
        metric_source=source(old,'tools/research_ops/v10_metric.py'),gap_source=source(v9,'tools/research_ops/v8_gap_recovery.py'))
