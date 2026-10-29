"""R评分资格mask独立追踪身份与CPU末模型加载；禁止重新读取训练池/标签。"""
from copy import deepcopy
import hashlib,importlib.util,json,os,re,sys
from pathlib import Path
R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/r_candidate_eligibility_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
OLD={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
FIXED_ARGS=dict(track_high_thresh=.25,track_low_thresh=.1,new_track_thresh=.25,track_buffer=30,match_thresh=.8,fuse_score=True)
SCHEMA='R_candidate_eligibility_tracking_inventory_v1';ALIGNED_SCHEMA='state_aligned_strongmotion_tracking_inventory_v1'
OBJECTIVE='R_original_known_BCE_pre_probability_candidate_eligibility_mask_S_original_BCE_alpha_1_over_3'
PROTOCOL_SHA='d5880b07e97e1252852c7c70ee5b1961b04f5825838063f8e84b462559388daf'
PROTOCOL_PATH=EXP/'training_frozen_a01/protocol.json'
AUDIT_STATUS='complete18_R_candidate_eligibility_actual_budget_effective_supervision_full_records_and_exit_verified'
TRAINING_STATUS='complete18_R_candidate_eligibility_training_wait_independent_audit_tracking'
COMPLETE_STATUS='complete18_R_candidate_eligibility_training_and_independent_budget_verified'
FRAMEWORK_SHA='ac50e61744e44a22c04c4169feb63112f7f0350c75b5ad344e6aec1998d38fc3'
BASE_PATH=R/'code/53bf25ceef65e2f2fe8bf277da4e3a189e84c57430e3c297f31e8cb0d7219b47/tools/research_ops/state_aligned_tracking_runtime.py'
BASE_SHA='84fdf4233a2b1491dab294c4fbf9bea74ac4e487859f797c852fad072576bda2'
BASE_REFERENCE=dict(path=str(BASE_PATH),sha256=BASE_SHA)

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

def frozen_base():return module(BASE_REFERENCE,'eligibility_frozen_aligned_runtime')

class FrozenBase:
    def __getattr__(self,key):return getattr(frozen_base(),key)
base=FrozenBase()

def protocol_identity(protocol):
    require(Path(protocol['path'])==PROTOCOL_PATH and protocol['sha256']==PROTOCOL_SHA,'必须本轮已冻R资格mask监督协议')

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
    require(aligned_inventory['schema']==ALIGNED_SCHEMA and len(aligned)==len(original)==18,'两组18参照来源不足')
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
            fold=unit[0],seed=unit[1],regime=unit[2],method='motion',method_identity='R_candidate_eligibility_original_motion',
            training_objective=OBJECTIVE,method_schema='r_candidate_eligibility_strongmotion_method_state_v1',learning_protocol=deepcopy(protocol),run=str(run),
            training_receipt=dict(path=str(run/'run_receipt.json'),sha256=entry['receipt_sha256']),
            training_complete=dict(path=str(run/'training_complete.json'),sha256=entry['complete_sha256']),
            original_normalizer=deepcopy(o['normalizer']),expected_initialization_sha256=o['binding']['initialization_sha256'],
            use_pose=False,intercept_applied=False,output_transform='original_sigmoid_probability_cutoff_0.50'))
    return sorted(result,key=lambda x:(x['fold'],x['seed'],x['regime']))

def validate_jobs(cfg,inventory):
    require(cfg['source_state_aligned_runtime']==BASE_REFERENCE,'原已验runtime必须显式实际SHA绑定')
    checked(cfg['source_state_aligned_runtime'])
    protocol_identity(cfg['learning_protocol'])
    require(inventory['schema']==SCHEMA and inventory['sources']==cfg['sources'] and inventory['panels']==cfg['panels'],'本轮独立库存/源不同')
    require(cfg['jobs']==tracking_matrix(inventory['models'],cfg['sources'],cfg['panels']),'完整180矩阵不同')
    require(cfg['tracker_parameters']==FIXED_ARGS and cfg['test_sealed'] is True and cfg['new_optimizer_updates']==0,'追踪原参数/封存/零更新不同')
    require('calibrations' not in cfg and 'fit_complete' not in cfg,'不能混入截距拟合身份')
    return inventory['models']

def source_bindings(cfg):
    require(cfg['source_state_aligned_runtime']==BASE_REFERENCE,'原已验runtime未显式绑定')
    checked(cfg['source_state_aligned_runtime'])
    # 原source_bindings只读原inventory/velocity/v10/v9及worker纯函数；不调用其learning_loader或训练schema验证。
    result=base.source_bindings(cfg);aligned=read_ref(cfg['aligned_inventory']);original=result['inventory']
    require(aligned['schema']==ALIGNED_SCHEMA and aligned['sources']==original['sources']==cfg['sources']
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

def tracking_matrix(models,sources,panels):
    require(set(panels)=={'original_heldout','old_external','seven_observed'} and [len(panels[k]) for k in ('original_heldout','old_external','seven_observed')]==[3,2,7]
        and set(panels['original_heldout'])==set(OLD),'固定3/2/7面板，不能混比赛')
    require(set(sources)==set(sum((panels[k] for k in panels),[])) and len(sources)==12,'12来源完整且不重复')
    require(len(models)==18 and len({x['model_id'] for x in models})==18,'新18模型身份不完整')
    jobs=[]
    for spec in models:
        heldout=next(seq for seq,game in OLD.items() if game==spec['fold'])
        for sequence in [heldout]+panels['old_external']+panels['seven_observed']:
            row=dict(model_id=spec['model_id'],baseline_model_id=spec['baseline_model_id'],original_baseline_model_id=spec['original_baseline_model_id'],regime=spec['regime'],fold=spec['fold'],seed=spec['seed'],sequence=sequence)
            row['job_id']=digest(['R_candidate_eligibility_tracking_v1',row])[:24];jobs.append(row)
    require(len(jobs)==len({j['job_id'] for j in jobs})==180,'180逻辑任务必须唯一完整');return jobs


def training_closure(cfg):
    """仅核新训练已验小收据，绝不调用训练prepare/audit或重扫旧权重。"""
    protocol_identity(cfg['learning_protocol']); audit=read_ref(cfg['training_budget']); complete=read_ref(cfg['training_complete'])
    require(audit['schema']=='independent_R_candidate_eligibility18_budget_audit_v1' and audit['status']==AUDIT_STATUS
        and audit['protocol']==cfg['learning_protocol'] and audit['training_processes_absent'] is True
        and audit['complete_checkpoints_read_back']==378 and audit['complete_checkpoint_coverage']==378
        and audit['nine_paired_R_RS_exposures_equal'] is True and audit['original_normalizer_initialization_S_exposure_unchanged'] is True
        and audit['unknown_used_for_loss']==0 and audit['optimizer_replay']==audit['new_optimizer_updates']==0 and audit['test_read'] is False,
        '新资格训练完整预算/独立378覆盖/实际退出不足')
    require(all(audit['actual_totals'][k]==v for k,v in [('updates',18000),('R_windows',54000),('S_windows',9000)]),'原窗口更新预算不同')
    require(complete['schema']=='r_candidate_eligibility_training_complete_root_v1' and complete['status']==COMPLETE_STATUS
        and complete['protocol']==cfg['learning_protocol'] and complete['budget_audit']==cfg['training_budget']
        and complete['actual_training_and_audit_processes_absent'] is True and complete['test_read'] is False,'未来完成根尚未真实签署')
    state=read_ref(audit['control_state'])
    require(state['status']==TRAINING_STATUS and state['active'] is None and state['protocol_sha256']==PROTOCOL_SHA
        and len(state['completed_train'])==18,'真实18模型终态不足')
    return audit,state


def validate_checkpoint_metadata(cfg,spec,receipt,complete,point,saved,normalizer_state,learning):
    """纯元数据合同；mask ref只比较，不打开池、侧表或训练标签。"""
    run=safe(spec['run']); binding=receipt['binding']; extra=saved['extra']
    require(receipt['schema']=='R_candidate_eligibility_full_recorded_training_run_v1' and receipt['status']=='complete'
        and receipt['completed_updates']==1000 and receipt['formal'] is True and receipt['diagnostic_variant'] is None
        and receipt['actual_dtype']=='float32' and receipt['amp'] is False and receipt['epoch_augmentation'] is False,'只准本轮正式last1000，不准诊断或旧CE')
    require(complete['schema']=='full_training_process_complete_v1' and complete['status']=='complete' and complete['actual_updates']==1000
        and complete['exposure_chain']==point['exposure_chain']==saved['exposure_chain']
        and complete['totals']['R_windows']==3000 and complete['totals']['S_windows']==1000*int(spec['regime']=='RS'), '本run实际完整末1000来源不同')
    require(point['completed_updates']==1000 and safe(point['path'])==run/'checkpoints/step_1000.pt'
        and saved['schema']=='full_training_checkpoint_v1' and saved['completed_updates']==1000 and saved['binding']==binding,'仅新末检查点，不选best/EMA')
    require(binding['protocol_sha256']==PROTOCOL_SHA and binding['method']=='motion' and binding['R_objective']==OBJECTIVE
        and binding['initialization_sha256']==spec['expected_initialization_sha256'] and all(binding[k]==spec[k] for k in ('fold','seed','regime'))
        and binding['record_extension_schema']=='R_candidate_scoring_eligibility_record_extension_v1', '独立方法/初始化/单元绑定不同')
    mask=learning['mask_inputs'][spec['fold']]
    require(binding['mask_input_sha256']==mask['sha256'] and extra['eligibility_mask_input']==mask
        and extra['schema']==spec['method_schema']=='r_candidate_eligibility_strongmotion_method_state_v1' and extra['training_objective']==OBJECTIVE
        and extra['R_loss']=='original_unreduced_known_BCE_mask_then_window_mean_then_fixed_mean3R'
        and extra['S_loss']=='unchanged_original_known_pair_BCE_alpha_1_over_3'
        and extra['normalizer']==normalizer_state and extra['use_pose'] is False and extra['epoch_augmentation'] is False
        and extra['full_original_known_forward_preserved'] is True and binding['method_state_sha256']==digest(extra)
        and binding['R_objective_code_sha256']==extra['R_objective_code_sha256']
        and binding['recorded_loop_sha256']==extra['recorded_loop_sha256'], 'mask来源/新methodextra/原normalizer不同')
    require('numeric_only_variant' not in extra and 'numeric_only_override' not in extra, '正式模型不得含诊断mask覆盖')
    return binding


def original_model_sha(model):
    h=hashlib.sha256()
    for key,value in sorted(model.state_dict().items()):h.update(key.encode());h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def load_model(cfg,spec):
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='-1','追踪只允许CPU')
    _,state=training_closure(cfg); aligned=read_ref(cfg['aligned_inventory']); original=read_ref(cfg['source_inventory'])
    require(spec in model_specs(cfg['learning_protocol'],state,aligned,original),'新资格模型身份不同')
    learning=read_ref(cfg['learning_protocol']); receipt=read_ref(spec['training_receipt']); complete=read_ref(spec['training_complete'])
    run=safe(spec['run']); point=read_ref(ref(run/'last_checkpoint.json')); normalizer_state=read_ref(spec['original_normalizer'])
    require(receipt['full_training_record']==spec['training_complete']['sha256'],'run完成记录SHA不同')
    require(point['completed_updates']==1000 and safe(point['path'])==run/'checkpoints/step_1000.pt','只加载新last1000')
    import torch
    require(not torch.cuda.is_initialized(),'loader前不得初始化CUDA')
    saved=torch.load(checked(point),map_location='cpu',weights_only=False)
    binding=validate_checkpoint_metadata(cfg,spec,receipt,complete,point,saved,normalizer_state,learning)
    sources=source_bindings(cfg); v9=sources['v9']; helper=module(cfg['original_inputs_source'],'eligibility_original_import_scope')
    expected_model=source(v9,'python/src/grf_ue_bridge/learned_association_model_v8.py')
    expected_features=source(v9,'python/src/grf_ue_bridge/learned_association_features_v8.py')
    with helper.frozen_import_scope(safe(v9['bundle'])):
        from grf_ue_bridge import learned_association_model_v8 as model_module
        from grf_ue_bridge import learned_association_features_v8 as feature_module
        require(safe(model_module.__file__)==checked(expected_model) and safe(feature_module.__file__)==checked(expected_features),'原factory/normalizer模块闭包不同')
        model=model_module.make_model(spec['seed']).to('cpu'); normalizer=model_module.FeatureNormalizer.from_state(normalizer_state)
        require(original_model_sha(model)==spec['expected_initialization_sha256'],'原14593初始化不逐值一致')
        require(saved['model'].keys()==model.state_dict().keys() and all(torch.is_tensor(v) and v.device.type=='cpu'
            and v.dtype==torch.float32 and bool(torch.isfinite(v).all()) for v in saved['model'].values()),'新模型state必须全FP32 CPU有限值')
        model.load_state_dict(saved['model'],strict=True); model.eval()
    require(normalizer.state()==normalizer_state and sum(p.numel() for p in model.parameters())==14593
        and all(p.device.type=='cpu' and p.dtype==torch.float32 for p in model.parameters()) and not torch.cuda.is_initialized(),'原normalizer/14593 FP32/纯CPU约束不同')
    evidence=dict(schema='R_candidate_eligibility_model_loading_receipt_v1',model_id=spec['model_id'],baseline_model_id=spec['baseline_model_id'],
        original_baseline_model_id=spec['original_baseline_model_id'],training_objective=OBJECTIVE,method_schema=spec['method_schema'],learning_protocol=cfg['learning_protocol'],
        training_budget=cfg['training_budget'],training_complete=cfg['training_complete'],run_receipt=spec['training_receipt'],
        checkpoint=dict(path=point['path'],sha256=point['sha256'],completed_updates=1000),
        original_motion_forward=True,output_transform='sigmoid',probability_cutoff=.5,use_pose=False,Pose_columns_zeroed_after_normalization=170,
        initialization_equal_original=True,normalizer_equal_original=True,device='cpu',actual_dtype='float32',checkpoint_selection='last1000_not_EMA_no_best',
        training_prepare_or_audit_called=False,training_pool_or_mask_or_labels_opened=False,checkpoint_extra_metadata_parsed=True,
        inference_eligibility_mask_applied=False,intercept_applied=False,new_optimizer_updates=0,test_read=False)
    return dict(model=model,normalizer=normalizer,binding=binding,receipt=evidence)
