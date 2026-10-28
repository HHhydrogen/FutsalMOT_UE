"""安装R集合监督训练的独立代码bundle、分析计划和绝对值协议；不启动训练。"""
import hashlib,json,os,shutil,stat
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[2]
RESEARCH=Path('D:/projects/FutsalMOT_Research')
EXPERIMENT=RESEARCH/'pose/r_set_supervision_a01'
SOURCE_PROTOCOL=RESEARCH/'pose/state_aligned_training_a01/training_frozen_a01/protocol.json'
SOURCE_COMPLETE=RESEARCH/'pose/state_aligned_training_a01/training_complete_root_a01.json'
SOURCE_AUDIT=RESEARCH/'pose/state_aligned_training_a01/postrun_audit_a01/actual_budget.json'
ANCHOR_ROOT=RESEARCH/'pose/teacher_anchor_bank_a01/complete_root_a01.json'
FILES=('tools/research_ops/candidate_set_supervision.py','tools/research_ops/set_supervision_recorded_loop.py',
       'tools/research_ops/set_supervision_training_runtime.py','tools/research_ops/set_supervision_train.py',
       'tools/research_ops/validate_r_set_supervision_numeric.py','tools/research_ops/control_r_set_supervision_training.py',
       'tools/research_ops/training_journal.py')
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
PARAMETERS=dict(updates=1000,R_per_step=3,S_per_RS_step=1,S_alpha=1/3,lr=.001,weight_decay=.0001,
    amp=False,prefetch=2,cache_bytes=268435456,checkpoint_interval=50,actual_dtype='float32',
    selection='last1000_no_best_not_EMA',network='194_64_32_1_ReLU_strongmotion',trainable_parameters=14593,
    use_pose=False,epoch_augmentation=False,R_objective='candidate_set_CE_fixed_no_match_logit_0',
    S_objective='original_known_pair_window_mean_BCE')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def ref(path):return dict(path=str(path).replace('\\','/'),sha256=sha(path))
def safe(path):
    p=Path(os.path.abspath(path))
    if RESEARCH not in p.parents:raise ValueError('只允许写DResearch')
    if any(x.lower()=='test' or 'snmot116' in x.lower() or 'snmot187' in x.lower() for x in p.parts):raise ValueError('测试封存')
    for q in (p,*p.parents):
        if q.exists() or q.is_symlink():
            info=q.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('禁止junction/符号链接')
    return p
def write_new(path,value):
    path=safe(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())
def digest_files(files):return hashlib.sha256(canonical(files).encode()).hexdigest()
def analysis_plan():
    return dict(schema='r_set_supervision_tracking_analysis_plan_v1',status='frozen_before_numeric_admission_and_training',
        test116187_sealed=True,optimizer_updates=0,new_tracking_jobs=180,reference_jobs_reused=180,
        training_matrix=[dict(fold=f,seed=s,regime=g) for f in FOLDS for s in SEEDS for g in REGIMES],
        sources_per_model=10,panels=[dict(name='original3',games=3,df=2),dict(name='external2',games=2,df=1),dict(name='seven',games=7,df=6)],
        comparison_families=5,comparisons=[
            'new_set_R_RS_minus_state_aligned_BCE_RS_primary',
            'new_set_R_minus_state_aligned_BCE_R',
            'new_set_R_RS_minus_original_strongmotion_RS',
            'new_set_R_minus_original_strongmotion_R',
            '(new_set_R_RS-new_set_R)-(aligned_BCE_RS-aligned_BCE_R)_interaction'],
        metrics=['AssA','HOTA','IDF1','DetA','MOTA'],primary_metric='AssA',metric_interval_count=75,
        paired_aggregation='mean_matching_fold_seed_within_game_then_equal_weight_games',
        bootstrap=dict(repeats=10000,seed=20261028,sampling_unit='game',rng='Python random.Random MT19937',
            sampling='with_replacement_randrange_panel_game_count',quantile='linear',leave_one_game_out=True),
        t_confidence=0.95,t_degrees_freedom=dict(original3=2,external2=1,seven=6),
        confidence_interpretation='uncorrected_descriptive_intervals_no_equivalence_delta_CI_crossing_zero_not_same',
        gap_ledger=dict(events=3690,reused_without_reregistration=True,tracker_receipt_has_no_GT_coordinates=True,
                        endpoint_GT_only_in_metric=True,empty_group='null',physical_occlusion_claim=False),
        track_parameters=dict(high=.25,low=.10,new=.25,buffer=30,high_match=.80,low_match=.50,
            unconfirmed=.70,fuse_score=True,max_dt_seconds=1.2,min_area_ratio=.25,max_area_ratio=4.,
            max_normalized_center_distance=2.,model_probability=.50,inference='original_sigmoid_threshold_0.50'),
        no_test_or_tuning=True,all_negative_zero_null_fold_seed_retained=True)
def install():
    freeze=EXPERIMENT/'training_frozen_a01';bundle_manifest_path=freeze/'bundle_manifest.json'
    config_path=freeze/'protocol.json';plan_path=freeze/'analysis_plan.json'
    if any(p.exists() for p in (config_path,bundle_manifest_path,plan_path)):
        raise FileExistsError('既有冻结协议/部分安装必须保留，另建新attempt')
    source=__import__('json').loads(SOURCE_PROTOCOL.read_text(encoding='utf-8-sig'))
    file_rows=[]
    for rel in FILES:
        source_file=PROJECT/rel
        if not source_file.is_file():raise FileNotFoundError(source_file)
        file_rows.append(dict(path=rel,sha256=sha(source_file)))
    bundle_hash=digest_files(file_rows);bundle=RESEARCH/'code'/bundle_hash
    if bundle.exists():
        for row in file_rows:
            target=safe(bundle/row['path'])
            if not target.is_file() or sha(target)!=row['sha256']:raise ValueError('已存在内容地址bundle不匹配')
    else:
        for row in file_rows:
            target=safe(bundle/row['path']);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(PROJECT/row['path'],target)
            if sha(target)!=row['sha256']:raise ValueError('bundle复制SHA不同')
    manifest=dict(schema='r_set_supervision_code_bundle_v1',files=file_rows,canonical_git_root=str(PROJECT),git_head='workspace_commit_recorded_after_freeze')
    write_new(bundle_manifest_path,manifest)
    plan=analysis_plan();write_new(plan_path,plan)
    source_ref=ref(SOURCE_PROTOCOL);complete_ref=ref(SOURCE_COMPLETE);audit_ref=ref(SOURCE_AUDIT);anchor_ref=ref(ANCHOR_ROOT)
    matrix=[dict(fold=f,seed=s,regime=g) for f in FOLDS for s in SEEDS for g in REGIMES]
    cfg=dict(schema='state_aligned_R_candidate_set_training_v1',approved_by='root',training_authorized=True,tracking_authorized=False,
        test116187_sealed=True,bundle=str(bundle).replace('\\','/'),bundle_manifest=ref(bundle_manifest_path),
        source_training_protocol=source_ref,source_training_complete_root=complete_ref,source_training_audit=audit_ref,
        teacher_anchor_complete_root=anchor_ref,selected_R_bank_root=source['input_root'],
        analysis_plan=ref(plan_path),numeric_admission=dict(path=str((EXPERIMENT/'numeric_admission_a01/receipt.json')).replace('\\','/')),
        training_matrix=matrix,parameters=PARAMETERS)
    write_new(config_path,cfg)
    return dict(status='frozen_R_set_training_protocol_and_analysis_plan_not_executed',bundle=str(bundle),
        bundle_sha256=bundle_hash,files=len(file_rows),manifest=ref(bundle_manifest_path),analysis_plan=ref(plan_path),
        protocol=ref(config_path),training_authorized=True,formal_optimizer_updates=0,numeric_admission_started=False,
        training_started=False,tracking_authorized=False,test_read=False)
if __name__=='__main__':print(canonical(install()))
