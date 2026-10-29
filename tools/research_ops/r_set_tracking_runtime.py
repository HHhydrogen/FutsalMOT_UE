"""R集合监督独立追踪身份；只读真实训练闭合后CPU加载，不运行追踪。"""
from copy import deepcopy
from contextlib import contextmanager
import os
import hashlib
import importlib.util
from pathlib import Path
import sys

BASE_PATH=Path('D:/projects/FutsalMOT_Research/code/53bf25ceef65e2f2fe8bf277da4e3a189e84c57430e3c297f31e8cb0d7219b47/tools/research_ops/state_aligned_tracking_runtime.py')
BASE_SHA='84fdf4233a2b1491dab294c4fbf9bea74ac4e487859f797c852fad072576bda2'
BASE_REFERENCE=dict(path=str(BASE_PATH),sha256=BASE_SHA)

def frozen_base():
    """原runtime只按实际绝对位置和SHA导入，不借ROOT同名模块。"""
    for item in (BASE_PATH,*BASE_PATH.parents):
        if item.exists() or item.is_symlink():
            if item.is_symlink() or getattr(item.lstat(),'st_file_attributes',0)&0x400:raise ValueError('原runtime不能经链接/junction')
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('原冻结runtime SHA不同')
    key='r_set_frozen_state_aligned_runtime_'+BASE_SHA
    if key not in sys.modules:
        spec=importlib.util.spec_from_file_location(key,BASE_PATH);value=importlib.util.module_from_spec(spec);sys.modules[key]=value
        previous=sys.dont_write_bytecode
        try:sys.dont_write_bytecode=True;spec.loader.exec_module(value)
        finally:sys.dont_write_bytecode=previous
    if Path(sys.modules[key].__file__)!=BASE_PATH:raise ValueError('原runtime缓存实际路径不同')
    return sys.modules[key]

base=frozen_base()

R=base.R;EXP=R/'pose/r_set_supervision_a01'
FOLDS=base.FOLDS;SEEDS=base.SEEDS;REGIMES=base.REGIMES;OLD=base.OLD;FIXED_ARGS=base.FIXED_ARGS
SCHEMA='R_candidate_set_supervision_tracking_inventory_v1'
OBJECTIVE='R_candidate_set_CE_fixed_null_logit0_S_original_BCE_alpha_1_over_3'
PROTOCOL_SHA='301eb84a90c47e0fbf7d869600f134ef46ca3a5d481d9029ad6d8a8161e7f0f7'
PROTOCOL_PATH=EXP/'training_frozen_a01/protocol.json'
AUDIT_STATUS='complete18_R_set_supervision_actual_budget_full_records_and_exit_verified'
TRAINING_STATUS='complete18_R_set_supervision_training_wait_independent_audit'
COMPLETE_STATUS='complete18_R_set_supervision_training_actual_budget_records_exit_verified_not_tracking_complete'
FRAMEWORK_SHA=base.FRAMEWORK_SHA
require,canonical,digest,safe,sha,checked,read_ref,ref,module,source=(getattr(base,k) for k in ('require','canonical','digest','safe','sha','checked','read_ref','ref','module','source'))

def protocol_identity(protocol):
    require(Path(protocol['path'])==PROTOCOL_PATH and protocol['sha256']==PROTOCOL_SHA,'必须本轮已冻R集合监督协议')

def model_id(protocol,fold,seed,regime):
    protocol_identity(protocol);require(fold in FOLDS and seed in SEEDS and regime in REGIMES,'固定18单元')
    return digest([SCHEMA,protocol['sha256'],fold,seed,regime])[:24]

def model_specs(protocol,completed_state,aligned_inventory,original_inventory):
    protocol_identity(protocol)
    require(completed_state['status']==TRAINING_STATUS and completed_state['active'] is None
        and completed_state['protocol_sha256']==protocol['sha256'],'真实18训练终态不足')
    entries=completed_state['completed_train'];expected={(f,s,g) for f in FOLDS for s in SEEDS for g in REGIMES}
    require(len(entries)==18 and {(e['fold'],e['seed'],e['regime']) for e in entries}==expected,'18完成单元缺失或重复')
    aligned=aligned_inventory['models'];original=original_inventory['models']
    require(aligned_inventory['schema']==base.SCHEMA and len(aligned)==len(original)==18,'两组18参照来源不足')
    result=[]
    for entry in entries:
        unit=tuple(entry[k] for k in ('fold','seed','regime'))
        a=[m for m in aligned if tuple(m[k] for k in ('fold','seed','regime'))==unit]
        o=[m for m in original if tuple(m[k] for k in ('fold','seed','regime'))==unit]
        require(len(a)==len(o)==1,'两参照单元匹配不唯一');a,o=a[0],o[0]
        require(a['baseline_model_id']==o['model_id'] and a['original_normalizer']==o['normalizer']
            and a['expected_initialization_sha256']==o['binding']['initialization_sha256'],'两参照原初始化/normalizer关系不同')
        identifier=model_id(protocol,*unit);require(identifier not in (a['model_id'],o['model_id']),'新权重不得借旧身份')
        run=safe(entry['path'])
        result.append(dict(model_id=identifier,baseline_model_id=a['model_id'],original_baseline_model_id=o['model_id'],
            fold=unit[0],seed=unit[1],regime=unit[2],method='motion',method_identity='R_candidate_set_supervision_original_motion',
            training_objective=OBJECTIVE,learning_protocol=deepcopy(protocol),run=str(run),
            training_receipt=dict(path=str(run/'run_receipt.json'),sha256=entry['receipt_sha256']),
            training_complete=dict(path=str(run/'training_complete.json'),sha256=entry['complete_sha256']),
            original_normalizer=deepcopy(o['normalizer']),expected_initialization_sha256=o['binding']['initialization_sha256'],
            use_pose=False,intercept_applied=False,output_transform='original_sigmoid_probability_cutoff_0.50'))
    return sorted(result,key=lambda x:(x['fold'],x['seed'],x['regime']))

def tracking_matrix(models,sources,panels):
    rows=base.tracking_matrix(models,sources,panels)
    by_id={m['model_id']:m for m in models}
    for job in rows:
        job['original_baseline_model_id']=by_id[job['model_id']]['original_baseline_model_id']
        job['job_id']=digest(['R_candidate_set_supervision_tracking_v1',{k:v for k,v in job.items() if k!='job_id'}])[:24]
    require(len({j['job_id'] for j in rows})==180,'完整180任务ID不唯一');return rows

def validate_jobs(cfg,inventory):
    require(cfg['source_state_aligned_runtime']==BASE_REFERENCE,'原已验runtime必须显式实际SHA绑定')
    checked(cfg['source_state_aligned_runtime'])
    protocol_identity(cfg['learning_protocol'])
    require(inventory['schema']==SCHEMA and inventory['sources']==cfg['sources'] and inventory['panels']==cfg['panels'],'本轮独立库存/源不同')
    require(cfg['jobs']==tracking_matrix(inventory['models'],cfg['sources'],cfg['panels']),'完整180矩阵不同')
    require(cfg['tracker_parameters']==FIXED_ARGS and cfg['test_sealed'] is True and cfg['new_optimizer_updates']==0,'追踪原参数/封存/零更新不同')
    require('calibrations' not in cfg and 'fit_complete' not in cfg,'不能混入截距拟合身份')
    return inventory['models']

def training_closure(cfg):
    protocol_identity(cfg['learning_protocol']);audit=read_ref(cfg['training_budget']);complete=read_ref(cfg['training_complete'])
    require(audit['status']==AUDIT_STATUS and audit['protocol']==cfg['learning_protocol']
        and audit['training_processes_absent'] is True and audit['complete_checkpoints_read_back']==378
        and audit['nine_paired_R_RS_exposures_equal'] is True,'实际18训练预算/退出审计不足')
    totals=audit['actual_totals'];require(totals['updates']==18000 and totals['R_windows']==54000 and totals['S_windows']==9000,'真实总预算不同')
    require(complete['status']==COMPLETE_STATUS and complete['test_read'] is False
        and complete['budget_audit']==cfg['training_budget'] and complete['protocol']==cfg['learning_protocol']
        and complete['actual_training_and_audit_processes_absent'] is True,'实际训练完成根未闭合或来源不同')
    state=read_ref(audit['control_state'])
    require(state['status']==TRAINING_STATUS and state['active'] is None and len(state['completed_train'])==18,'训练状态不完整')
    return audit,state

def learning_loader(cfg):
    protocol_identity(cfg['learning_protocol']);protocol=read_ref(cfg['learning_protocol'])
    loader=module(source(protocol,'tools/research_ops/set_supervision_training_runtime.py'),'R_set_complete_loader')
    loader.validate_protocol(checked(cfg['learning_protocol']));return loader

@contextmanager
def learning_import_scope(cfg):
    """新监督与原输入闭包同时绑定；恢复完整sys.path，不接受同名模块污染。"""
    protocol=read_ref(cfg['learning_protocol']);original=read_ref(protocol['source_training_protocol'])
    expected={'set_supervision_training_runtime':source(protocol,'tools/research_ops/set_supervision_training_runtime.py'),
        'candidate_set_supervision':source(protocol,'tools/research_ops/candidate_set_supervision.py'),
        'state_aligned_training_inputs':source(original,'tools/research_ops/state_aligned_training_inputs.py')}
    def verify():
        for name,reference in expected.items():
            loaded=sys.modules.get(name)
            if loaded is not None:require(safe(loaded.__file__)==checked(reference),'训练局部模块缓存来自错误闭包：'+name)
    verify();previous=list(sys.path)
    try:
        sys.path[:0]=[str(safe(protocol['bundle'])/'tools/research_ops'),str(safe(original['bundle'])/'tools/research_ops'),str(safe(original['bundle'])/'tools/performance')]
        yield
        verify()
    finally:sys.path[:]=previous

def load_model(cfg,spec):
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='-1','追踪只准CPU')
    _,state=training_closure(cfg);aligned=read_ref(cfg['aligned_inventory']);original=read_ref(cfg['source_inventory'])
    require(spec in model_specs(cfg['learning_protocol'],state,aligned,original),'R集合模型身份不同')
    receipt=read_ref(spec['training_receipt']);read_ref(spec['training_complete'])
    require(receipt['schema']=='r_set_supervision_full_recorded_training_run_v1' and receipt['status']=='complete'
        and receipt['completed_updates']==1000 and receipt['epoch_augmentation'] is False
        and receipt['actual_dtype']=='float32' and receipt['amp'] is False,'独立R集合训练run身份不足')
    import torch
    require(not torch.cuda.is_initialized(),'加载前不得初始化CUDA')
    with learning_import_scope(cfg):
        loader=learning_loader(cfg);protocol=checked(cfg['learning_protocol']);run=safe(spec['run'])
        loader.audit_run(protocol,run,all_checkpoints=False)
        ctx=loader.prepare(protocol,spec['fold'],spec['seed'],spec['regime'])
        model=ctx['set_oldrt'].new_model(ctx,device='cpu');normalizer=ctx['normalizer']
        point=loader.read(run/'last_checkpoint.json')
        require(point['completed_updates']==1000 and Path(point['path'])==run/'checkpoints/step_1000.pt','仅末1000检查点')
        saved=torch.load(checked(point),map_location='cpu',weights_only=False)
        require(saved['schema']=='full_training_checkpoint_v1' and saved['binding']==receipt['binding']
            and saved['completed_updates']==1000 and saved['extra']==loader.extra(ctx)
            and saved['extra']['training_objective']==OBJECTIVE
            and saved['binding']['R_objective']=='candidate_set_CE_fixed_no_match_logit_0'
            and saved['binding']['method_state_sha256']==digest(saved['extra']),'新方法状态/记录绑定不同')
        require(saved['model'].keys()==model.state_dict().keys(),'模型参数结构不同')
        model.load_state_dict(saved['model']);model.eval();binding=saved['binding']
    require(binding['protocol_sha256']==cfg['learning_protocol']['sha256'] and binding['method']=='motion'
        and binding['initialization_sha256']==spec['expected_initialization_sha256']
        and all(binding[k]==spec[k] for k in ('fold','seed','regime')),'新监督/初始化单元身份不同')
    require(normalizer.state()==read_ref(spec['original_normalizer']),'不得重拟合normalizer')
    require(not torch.cuda.is_initialized() and sum(p.numel() for p in model.parameters())==14593
        and all(p.device.type=='cpu' and p.dtype==torch.float32 for p in model.parameters()) and not model.training,'只准原14593 FP32 CPU motion模型')
    evidence=dict(schema='R_candidate_set_model_loading_receipt_v1',model_id=spec['model_id'],baseline_model_id=spec['baseline_model_id'],
        original_baseline_model_id=spec['original_baseline_model_id'],training_objective=OBJECTIVE,learning_protocol=cfg['learning_protocol'],
        training_budget=cfg['training_budget'],training_complete=cfg['training_complete'],run_receipt=spec['training_receipt'],
        original_motion_forward=True,output_transform='sigmoid',probability_cutoff=.5,use_pose=False,Pose_columns_zeroed_after_normalization=170,
        initialization_equal_original=True,normalizer_equal_original=True,device='cpu',actual_dtype='float32',checkpoint='last1000_not_EMA_no_best',
        intercept_applied=False,new_optimizer_updates=0,test_read=False)
    return dict(model=model,normalizer=normalizer,binding=binding,receipt=evidence)

def source_bindings(cfg):
    require(cfg['source_state_aligned_runtime']==BASE_REFERENCE,'原已验runtime未显式绑定')
    checked(cfg['source_state_aligned_runtime'])
    # 原source_bindings只读原inventory/velocity/v10/v9及worker纯函数；不调用其learning_loader或训练schema验证。
    result=base.source_bindings(cfg);aligned=read_ref(cfg['aligned_inventory']);original=result['inventory']
    require(aligned['schema']==base.SCHEMA and aligned['sources']==original['sources']==cfg['sources']
        and aligned['panels']==original['panels']==cfg['panels'],'两参照必须原12源/3面板')
    require(len(original['baseline_units'])==180,'原uncalibrated强motion参照必须180来源')
    expected_jobs={tuple(j[k] for k in ('regime','sequence','fold','seed')):j for j in base.tracking_matrix(aligned['models'],cfg['sources'],cfg['panels'])}
    expected=set(expected_jobs)
    manifest=read_ref(cfg['aligned_tracking_manifest'])
    aligned_protocol=read_ref(cfg['aligned_tracking_protocol'])
    require(manifest['config_sha256']==cfg['aligned_tracking_protocol']['sha256']
        and aligned_protocol['inventory']==cfg['aligned_inventory'],'aligned参照输出/库存协议绑定不同')
    analysis=read_ref(cfg['aligned_analysis'])
    require(analysis['status']=='complete180_state_aligned_tracking_all360_results_and_paired_intervals'
        and analysis['protocol']==cfg['aligned_tracking_protocol'] and analysis['inventory']==cfg['aligned_inventory']
        and analysis['source_inventory']==cfg['source_inventory'] and analysis['panels']==cfg['panels']
        and analysis['formal_evaluation_manifest']==cfg['aligned_tracking_manifest'] and analysis['test_read'] is False
        and analysis['new_tracking_evaluations']==180,'aligned完整分析/参照/manifest闭包不同')
    actual_reports=analysis['all_actual_reports'];expected_reports=[row['report'] for row in manifest['reports']]
    require(len(actual_reports)==180 and len({digest(r) for r in actual_reports})==180
        and {digest(r) for r in actual_reports}=={digest(r) for r in expected_reports},'aligned分析报告不是同一完整180来源')
    require(manifest['status']=='complete180_state_aligned_tracking_and_evaluation' and len(manifest['tracking'])==len(manifest['reports'])==180,'上轮aligned180未真实闭合')
    for key in ('tracking','reports'):
        cells=[tuple(row['job'][k] for k in ('regime','sequence','fold','seed')) for row in manifest[key]]
        require(len(set(cells))==180 and set(cells)==expected,'aligned参照180单元不完整')
        require(all(row['job']==expected_jobs[cell] for row,cell in zip(manifest[key],cells)),'aligned参照任务/模型身份与库存不同')
    original_cells=[tuple(row[k] for k in ('regime','sequence','fold','seed')) for row in original['baseline_units']]
    require(len(set(original_cells))==180 and set(original_cells)==expected,'原strongmotion参照180单元不完整')
    by_unit={(m['regime'],m['fold'],m['seed']):m['model_id'] for m in original['models']}
    require(all(row['model_id']==by_unit[row['regime'],row['fold'],row['seed']] for row in original['baseline_units']),'原参照身份与单元不同')
    result.update(aligned_inventory=aligned,aligned_tracking_manifest=manifest,aligned_analysis=analysis)
    return result
