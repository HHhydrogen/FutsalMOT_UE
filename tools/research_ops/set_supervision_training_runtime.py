"""R候选集合监督训练适配层；输入/模型沿用已冻自由状态R来源协议。"""
import hashlib, importlib.util, json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=Path('D:/projects/FutsalMOT_Research')
EXPERIMENT=RESEARCH/'pose/r_set_supervision_a01'
SOURCE_PROTOCOL=RESEARCH/'pose/state_aligned_training_a01/training_frozen_a01/protocol.json'
SOURCE_PROTOCOL_SHA='2acc7642109c317b9ca694d3649a864c5553e177f20425d24726de1781c7d3c6'
SOURCE_COMPLETE_ROOT=RESEARCH/'pose/state_aligned_training_a01/training_complete_root_a01.json'
SOURCE_COMPLETE_ROOT_SHA='62646594150716226b4cb90087731b8d2c76fb836bd22a3218a776031ebf5a33'
SOURCE_AUDIT=RESEARCH/'pose/state_aligned_training_a01/postrun_audit_a01/actual_budget.json'
SOURCE_AUDIT_SHA='d551bb377a8d33b6f454fa5f119723c06c085555c85c37c55b5080f53d671212'
TEACHER_COMPLETE_ROOT=RESEARCH/'pose/teacher_anchor_bank_a01/complete_root_a01.json'
TEACHER_COMPLETE_ROOT_SHA='2d3f6473a9497fc32aab50a2ad99333ac9216755b1798238b72e3087cdc99d02'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
PARAMETERS=dict(updates=1000,R_per_step=3,S_per_RS_step=1,S_alpha=1/3,lr=.001,weight_decay=.0001,
    amp=False,prefetch=2,cache_bytes=268435456,checkpoint_interval=50,actual_dtype='float32',
    selection='last1000_no_best_not_EMA',network='194_64_32_1_ReLU_strongmotion',trainable_parameters=14593,
    use_pose=False,epoch_augmentation=False,R_objective='candidate_set_CE_fixed_no_match_logit_0',
    S_objective='original_known_pair_window_mean_BCE')

def require(ok,message):
    if not ok:raise ValueError(message)
def write_new(path,value):
    from training_journal import write_new as write
    write(path,value)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def rows(path):
    with Path(path).open(encoding='utf-8-sig') as stream:return [json.loads(line) for line in stream if line.strip()]
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def physical(path):
    path=Path(os.path.abspath(path));require(RESEARCH in path.parents,'只允许实际DResearch路径')
    require(not any(part.lower()=='test' or 'snmot116' in part.lower() or 'snmot187' in part.lower() for part in path.parts),'测试继续封存')
    for item in (path,*path.parents):
        if item.exists():require(not item.is_symlink() and not getattr(item.lstat(),'st_file_attributes',0)&0x400,'禁止链接/junction')
    return path
def checked(ref):
    p=physical(ref['path']);require(p.is_file() and sha(p)==ref['sha256'],'冻结来源SHA变化：'+str(p));return p
def expected_matrix():return [dict(fold=f,seed=s,regime=g) for f in FOLDS for s in SEEDS for g in REGIMES]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
def validate_protocol(config):
    cfg=read(config)
    require(cfg.get('schema')=='state_aligned_R_candidate_set_training_v1' and cfg.get('training_matrix')==expected_matrix()
        and cfg.get('parameters')==PARAMETERS and cfg.get('test116187_sealed') is True,'候选集合监督训练矩阵/绝对参数/封存不同')
    require(cfg.get('approved_by')=='root' and cfg.get('training_authorized') is True and cfg.get('tracking_authorized') is False,
        '候选集合监督正式训练协议未冻结授权')
    require(Path(cfg['source_training_protocol']['path'])==SOURCE_PROTOCOL
        and cfg['source_training_protocol']['sha256']==SOURCE_PROTOCOL_SHA and sha(SOURCE_PROTOCOL)==SOURCE_PROTOCOL_SHA,
        '来源训练协议改变')
    require(Path(cfg['source_training_complete_root']['path'])==SOURCE_COMPLETE_ROOT
        and cfg['source_training_complete_root']['sha256']==SOURCE_COMPLETE_ROOT_SHA
        and Path(cfg['source_training_audit']['path'])==SOURCE_AUDIT
        and cfg['source_training_audit']['sha256']==SOURCE_AUDIT_SHA
        and Path(cfg['teacher_anchor_complete_root']['path'])==TEACHER_COMPLETE_ROOT
        and cfg['teacher_anchor_complete_root']['sha256']==TEACHER_COMPLETE_ROOT_SHA,
        '训练完成根/预算审计/anchor交叉审计来源未绑定已验凭据')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==RESEARCH/'code','必须由本轮不可变bundle执行')
    manifest=read(checked(cfg['bundle_manifest']))
    require(ROOT.name==hashlib.sha256(canonical(manifest['files']).encode()).hexdigest(),
        '本轮代码bundle目录名不符合内容地址')
    for entry in manifest['files']:
        require(sha(physical(ROOT/entry['path']))==entry['sha256'],'本轮执行bundle变更')
    plan=read(checked(cfg['analysis_plan']))
    require(plan.get('schema')=='r_set_supervision_tracking_analysis_plan_v1'
        and plan.get('status')=='frozen_before_numeric_admission_and_training'
        and plan.get('test116187_sealed') is True
        and plan.get('comparison_families')==5 and plan.get('metric_interval_count')==75,
        '结果前追踪评价计划未冻结或范围不同')
    root=read(checked(cfg['source_training_complete_root']))
    require(root.get('status')=='complete18_state_aligned_training_actual_budget_records_exit_verified_not_tracking_complete'
        and root.get('test_read') is False,
        '旧R来源模型训练完成根缺失或测试边界错误')
    audit=read(checked(cfg['source_training_audit']))
    require(audit.get('status')=='complete18_state_aligned_R_actual_budget_full_records_and_exit_verified'
        and audit.get('complete_checkpoints_read_back')==378 and audit.get('training_processes_absent') is True
        and audit.get('actual_totals',{}).get('updates')==18000
        and audit.get('actual_totals',{}).get('R_windows')==54000
        and audit.get('actual_totals',{}).get('S_windows')==9000,
        '旧R来源训练预算/退出独立审计不完整')
    source_cfg=read(SOURCE_PROTOCOL)
    bank=read(checked(cfg['selected_R_bank_root']))
    require(Path(cfg['selected_R_bank_root']['path'])==Path(source_cfg['input_root']['path'])
        and cfg['selected_R_bank_root']['sha256']==source_cfg['input_root']['sha256']
        and bank.get('status')=='complete3_fold1000_unique_original_prediction_R_banks_not_training_authorized'
        and bank.get('all_windows_roundtrip_exact') is True and bank.get('test_read') is False,
        '训练R窗口池来源/标签逐值审计不完整')
    anchor=read(checked(cfg['teacher_anchor_complete_root']))
    require(anchor.get('status')=='complete3000_selected_R_bank_anchor_crosscheck_independently_verified'
        and anchor.get('test_read') is False,'3000窗anchor审计未闭合')
    return cfg
def load_source_runtime(config):
    cfg=validate_protocol(config);source_path=checked(cfg['source_training_protocol']);source=read(source_path)
    oldroot=physical(source['bundle']);oldrt=module('r_set_original_state_aligned_runtime',oldroot/'tools/research_ops/state_aligned_training_runtime.py')
    sys.path[:0]=[str(ROOT/'tools/research_ops'),str(oldroot/'tools/research_ops'),str(oldroot/'tools/performance')]
    return cfg,oldrt
def prepare(config,fold,seed,regime):
    cfg,oldrt=load_source_runtime(config);require(dict(fold=fold,seed=seed,regime=regime) in cfg['training_matrix'],'未登记训练单元')
    ctx=oldrt.prepare(cfg['source_training_protocol']['path'],fold,seed,regime)
    ctx.update(set_cfg=cfg,set_config_path=Path(config),set_protocol_sha256=sha(config),set_oldrt=oldrt)
    return ctx
def spec(ctx,model,diagnostic=False):
    import hashlib
    value=ctx['set_oldrt'].spec(ctx,model,ctx['seed'],ctx['regime'],diagnostic=diagnostic)
    value['binding']['protocol_sha256']=ctx['set_protocol_sha256']
    value['binding']['source_training_protocol_sha256']=SOURCE_PROTOCOL_SHA
    value['binding']['R_objective']='candidate_set_CE_fixed_no_match_logit_0'
    value['binding']['R_objective_code_sha256']=sha(ROOT/'tools/research_ops/candidate_set_supervision.py')
    value['binding']['recorded_loop_sha256']=sha(ROOT/'tools/research_ops/set_supervision_recorded_loop.py')
    value['binding']['teacher_anchor_complete_root_sha256']=ctx['set_cfg']['teacher_anchor_complete_root']['sha256']
    value['binding']['analysis_plan_sha256']=ctx['set_cfg']['analysis_plan']['sha256']
    value['binding']['method_state_sha256']=hashlib.sha256(canonical(extra(ctx)).encode()).hexdigest()
    return value
def extra(ctx):
    value=ctx['set_oldrt'].extra(ctx)
    value.update(training_objective='R_candidate_set_CE_fixed_null_logit0_S_original_BCE_alpha_1_over_3',
        R_loss='logsumexp([0,known_logits])-unique_positive_logit_or_zero',
        unknown_policy='excluded_from_known_set_unknown_may_contain_true_target',null_logit=0.0,
        R_window_bank_sha256=ctx['set_cfg']['selected_R_bank_root']['sha256'],
        teacher_anchor_audit_sha256=ctx['set_cfg']['teacher_anchor_complete_root']['sha256'],
        tracking_analysis_plan_sha256=ctx['set_cfg']['analysis_plan']['sha256'])
    return value
def batches(ctx,limit=1000):return ctx['set_oldrt'].batches(ctx,ctx['regime'],limit)
def r_loss(model,windows):
    from candidate_set_supervision import real_domain_set_loss
    return real_domain_set_loss(model,windows)
def s_loss(ctx,model,windows):return ctx['numeric'].domain_loss(model,windows)

def audit_run(config,run,all_checkpoints=False):
    """本方法独立核验完整记录、方法状态、曝光链及21份检查点。"""
    import torch
    cfg=validate_protocol(config);run=physical(run);receipt=read(run/'run_receipt.json');binding=receipt['binding']
    require(receipt.get('schema')=='r_set_supervision_full_recorded_training_run_v1'
        and receipt.get('status')=='complete' and receipt.get('completed_updates')==1000
        and binding.get('protocol_sha256')==sha(config)
        and binding.get('R_objective')=='candidate_set_CE_fixed_no_match_logit_0',
        '候选集合监督完整训练身份/1000更新不同')
    unit={key:binding[key] for key in ('fold','seed','regime')};require(unit in cfg['training_matrix'],'run不属于固定18臂')
    ctx=prepare(config,**unit);logs=rows(run/'steps.jsonl');require(len(logs)==1000,'逐步训练记录不足1000')
    chain='0'*64
    totals=dict(R_windows=0,S_windows=0,R_pairs=0,S_pairs=0,R_known_pairs=0,S_known_pairs=0)
    for index,entry in enumerate(logs):
        row=dict(entry);saved=row.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        expected_r=ctx['table']['real'][index*3:index*3+3]
        expected_s=ctx['table']['synthetic'][index:index+1] if unit['regime']=='RS' else []
        require(chain==saved and row['actual_update']==index+1 and row['update_index']==index
            and row['R_windows']==3 and row['S_windows']==len(expected_s)
            and row['real']==expected_r and row['synthetic']==expected_s,
            '候选集合监督逐步记录链/R/S UID epoch pair顺序不同')
        expected_counts=dict(R_pairs=sum(x['candidate_pairs'] for x in expected_r),
            S_pairs=sum(x['candidate_pairs'] for x in expected_s),
            R_known_pairs=sum(x['labelled_pairs'] for x in expected_r),
            S_known_pairs=sum(x['labelled_pairs'] for x in expected_s))
        require(all(row.get(key)==value for key,value in expected_counts.items()),
            '候选集合监督逐步all/known pair与冻结来源不同')
        for key,value in dict(R_windows=3,S_windows=len(expected_s),**expected_counts).items():totals[key]+=value
        require(row['learning_rates']==[.001] and row['grad_l2']>=0 and row['step_wall_seconds']>=0,
            '逐步学习率/梯度/耗时不完整')
    complete=read(run/'training_complete.json');last=read(run/'last_checkpoint.json');tx=read(run/'update_transaction.json')
    require(complete.get('status')=='complete' and complete.get('actual_updates')==1000
        and complete.get('exposure_chain')==last.get('exposure_chain')==chain
        and complete.get('steps_sha256')==sha(run/'steps.jsonl') and len(complete['checkpoints'])==21
        and {x['completed_updates'] for x in complete['checkpoints']}==set(range(0,1001,50))
        and complete['totals']['R_windows']==3000
        and complete['totals']['S_windows']==1000*int(unit['regime']=='RS')
        and receipt.get('full_training_record')==sha(run/'training_complete.json'),
        '候选集合监督完整记录/曝光/21检查点索引不完整')
    expected_totals=dict(R_windows=3000,S_windows=1000*int(unit['regime']=='RS'),
        R_pairs=sum(x['candidate_pairs'] for x in ctx['table']['real']),
        S_pairs=sum(x['candidate_pairs'] for x in ctx['table']['synthetic']) if unit['regime']=='RS' else 0,
        R_known_pairs=sum(x['labelled_pairs'] for x in ctx['table']['real']),
        S_known_pairs=sum(x['labelled_pairs'] for x in ctx['table']['synthetic']) if unit['regime']=='RS' else 0)
    require(complete.get('totals')==totals==expected_totals,
        '训练完成账本pair/window总量与逐步来源重计不同')
    require(tx.get('status')=='committed' and tx.get('completed_updates')==1000
        and tx.get('chain_sha256')==chain,'最后更新事务未提交')
    points=complete['checkpoints'] if all_checkpoints else [last];saved_payload=None
    for point in points:
        step=point['completed_updates'];path=run/'checkpoints'/('step_%04d.pt'%step)
        require(Path(point['path'])==path,'检查点路径不符');payload=torch.load(checked(point),map_location='cpu',weights_only=False)
        expected_chain='0'*64 if step==0 else logs[step-1]['chain_sha256']
        extra_value=extra(ctx)
        require(payload.get('schema')=='full_training_checkpoint_v1' and payload.get('completed_updates')==step
            and payload.get('binding')==binding and payload.get('extra')==extra_value
            and payload.get('exposure_chain')==expected_chain
            and all(key in payload for key in ('model','optimizer','rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda'))
            and payload.get('rng_torch_cuda') is not None and all(value.dtype==torch.float32 for value in payload['model'].values()),
            '候选集合监督完整checkpoint对象/随机状态/方法状态不同')
        require(binding.get('method_state_sha256')==hashlib.sha256(canonical(extra_value).encode()).hexdigest(),
            '完整检查点方法状态SHA与绑定不同')
        optimizer_state=payload['optimizer'];groups=optimizer_state.get('param_groups',[]);states=optimizer_state.get('state',{})
        require(len(groups)==1 and groups[0].get('lr')==.001 and groups[0].get('weight_decay')==.0001
            and tuple(groups[0].get('betas',()))==(.9,.999) and groups[0].get('eps')==1e-8
            and groups[0].get('amsgrad') is False,'完整检查点AdamW超参数不同')
        parameter_ids=set(groups[0].get('params',[]))
        if step==0:require(not states,'step0 AdamW状态必须为空')
        else:
            require(bool(parameter_ids) and set(states)==parameter_ids,'更新后AdamW参数状态不完整')
            require(all(int(state['step'].item())==step and state['exp_avg'].dtype==torch.float32
                and state['exp_avg_sq'].dtype==torch.float32
                and tuple(state['exp_avg'].shape)==tuple(state['exp_avg_sq'].shape)
                for state in states.values()),'AdamW逐参数更新步数/FP32一阶二阶动量不同')
        if step==0:
            initial=ctx['set_oldrt'].new_model(ctx,device='cpu')
            require(payload['model'].keys()==initial.state_dict().keys()
                and all(torch.equal(payload['model'][key],value) for key,value in initial.state_dict().items())
                and not payload['optimizer']['state'],'step0不是原14593参数初始化')
        if step==1000:saved_payload=payload
    require(saved_payload is not None or not all_checkpoints,'未读末检查点')
    return dict(unit=unit,updates=1000,R_windows=3000,S_windows=1000*int(unit['regime']=='RS'),
        R_pairs=complete['totals']['R_pairs'],R_known_pairs=complete['totals']['R_known_pairs'],
        S_pairs=complete['totals']['S_pairs'],S_known_pairs=complete['totals']['S_known_pairs'],
        exposure_chain_sha256=chain,full_checkpoints_read=len(points))
