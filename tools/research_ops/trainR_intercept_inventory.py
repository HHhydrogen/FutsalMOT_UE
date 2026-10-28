"""训练R截距校准的18冻结模型/原1000R池/180历史参照只读来源清单。"""
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import stat

R = Path('D:/projects/FutsalMOT_Research')
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
REGIMES = ('R', 'RS')
FIXED = dict(velocity='ac89537c28668959729ea8d1930ca79c8f3ceff2da98c93bd54940467ebfd16d',
    ABC='fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78',
    training='2a1fa8ecd0b48993289c859ec6e83c36bf987e9d7de9ccf44820c4a86f7be575',
    v10_analysis='7dc455b841ef9d7ff99256d350ab5e2f99fb844778e870d836bc2d41495b6b91',
    ABC_analysis='8e51e87de306fca7c4c9713f1afed7edb6ec5f97eaabc10af5b7ee7c3f6183fa')


def require(ok, text):
    if not ok:
        raise ValueError(text)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def safe(value):
    path = Path(value)
    require(path.is_absolute(), '必须绝对物理来源路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
            for p in path.parts), '只准实际研究根，最终测试封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不跟随junction或链接')
    return path


def data_ref(reference):
    """权重/窗口/缓存/GT/MOT等只保留已签引用；不读字节、不重哈。"""
    require(isinstance(reference, dict) and set(reference) >= {'path', 'sha256'}
            and re.fullmatch('[0-9a-f]{64}', reference['sha256']), '缺少已签数据引用')
    path = safe(reference['path']); require(path.is_file(), '已签来源不存在：'+str(path)); return path


def checked_metadata(reference):
    path = data_ref(reference)
    require(path.suffix in ('.json', '.csv') and path.name not in ('posthoc_GT_labels.json', 'gap_registry.json'), '清单不得打开权重/窗口/缓存/GT')
    content = path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == reference['sha256'], '小元数据/SHA改变：'+str(path))
    return path, content


def read(reference):
    _, content = checked_metadata(reference)
    return json.loads(content.decode('utf-8-sig'))


def csv_rows(reference):
    _, content = checked_metadata(reference)
    return list(csv.DictReader(content.decode('utf-8-sig').splitlines()))


def source_file(config, relative):
    manifest = read(config['bundle_manifest'])
    entries = [entry for entry in manifest['files'] if entry['path'] == relative]
    require(len(entries) == 1, '必须实际冻结源码清单入口：'+relative)
    path = safe(Path(config['bundle'])/relative)
    expected = entries[0]['sha256']
    require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected, '实际冻结源码改变')
    return dict(path=str(path), sha256=expected)


def model_id(regime, fold, seed):
    return hashlib.sha256(canonical([regime, fold, seed]).encode()).hexdigest()[:24]


def clean_folds(training, old8, c_protocol):
    receipt = read(old8['pairs_complete'])
    require(receipt['schema'] == 'v8_pairs_build_receipt_v1' and receipt['status'] == 'complete_candidate_not_training_authorized'
            and receipt['real_pool_unique_per_fold'] == 1000 and receipt['config_sha256'] == training['source_config']['sha256']
            and receipt['source_frames_per_fold'] == dict(real_train=1500, heldout=750), '原1000唯一R池构建证明不同')
    result = {}
    for fold in FOLDS:
        original, current = old8['folds'][fold], training['folds'][fold]
        require(all(current[key] == original[key] == c_protocol['folds'][fold][key] for key in ('real_pool', 'normalizer', 'exposures')),
                '三来源原R池/normalizer/3000曝表必须相同')
        require(set(current['exposures']) == {str(seed) for seed in SEEDS}, '全部三seed曝光来源不可缺失')
        for reference in [current['real_pool'], current['normalizer'], *current['exposures'].values()]:
            data_ref(reference)
        allowed = [game for game in FOLDS if game != fold]
        result[fold] = dict(heldout_game=fold, allowed_games=allowed,
            allowed_sequences=[sequence for sequence, game in OLD.items() if game in allowed],
            excluded_sequences=[sequence for sequence, game in OLD.items() if game == fold],
            clean_R_pool=deepcopy(current['real_pool']), normalizer=deepcopy(current['normalizer']),
            baseR_exposures=deepcopy(current['exposures']), pool_build_receipt=deepcopy(old8['pairs_complete']),
            declared_unique_windows=1000, calibration_order='original_pool_JSONL_order_once_not_3000_exposure_order',
            actual_pool_contents_validated=False, actual_UID_games_labels_validation_required_at_logit_extraction=True,
            synthetic_windows_for_calibration=0, validation_or_test_windows_for_calibration=0,
            augmentation='none_clean_original_window_features', objective='mean_over_all1000_windows_of_mean_known_pair_BCE;empty_known_window_zero')
    return result


def models_from(training_ref, training, old8, c_protocol, folds):
    require(c_protocol['source_v10_protocol'] == training_ref and c_protocol['reference_R']['motion'] == training['reference_R']['motion'],
            'ABC引用的A/B必须同一原R/RS来源')
    r_loader = dict(module=source_file(old8, 'tools/research_ops/v8_track.py'), function='load_complete',
        protocol=deepcopy(training['v8_protocol']), signature=['run', 'cfg', 'config_sha', 'fold'],
        return_contract='model,normalizer,binding', entry_schema='v8_learned_association_checkpoint')
    rs_loader = dict(module=source_file(training, 'tools/research_ops/v10_runtime.py'), function='complete_model',
        protocol=deepcopy(training_ref), signature=['config', 'run'],
        return_contract='cfg,numeric,model,adapter,binding', entry_schema='full_training_checkpoint_v1')
    models = []
    for regime in REGIMES:
        for fold in FOLDS:
            for seed in SEEDS:
                reference = (training['reference_R']['motion'] if regime == 'R' else c_protocol['reference_B']['motion'])[fold][str(seed)]
                receipt = read(reference['training_receipt']); checkpoint = deepcopy(reference['checkpoint']); data_ref(checkpoint)
                binding = receipt['binding']; run = safe(Path(reference['training_receipt']['path']).parent)
                require(receipt['status'] == 'complete' and receipt['completed_updates'] == 1000
                        and binding['fold'] == fold and binding['seed'] == seed
                        and receipt['real_window_exposures'] == 3000
                        and receipt['synthetic_window_exposures'] == (0 if regime == 'R' else 1000), '实际冻结模型来源/训练预算不同')
                if regime == 'R':
                    require(receipt['schema'] == 'v8_window_training_run' and binding['arm'] == 'motion_R'
                            and binding['protocol_sha256'] == training['v8_protocol']['sha256']
                            and binding['normalizer_sha256'] == folds[fold]['normalizer']['sha256']
                            and receipt['checkpoint_sha256'] == checkpoint['sha256'] and Path(checkpoint['path']).parent == run,
                            'R必须原强v8 motion_R last1000，不能伪装新schema')
                    loader = r_loader; complete = None
                else:
                    require(receipt['schema'] == 'v10_full_recorded_training_run_v1' and binding['regime'] == 'RS'
                            and binding['method'] == 'motion' and binding['pool'] == 'balanced'
                            and binding['protocol_sha256'] == training_ref['sha256'] and receipt['checkpoint'] == checkpoint
                            and Path(checkpoint['path']).parent.parent == run,
                            'RS必须原平衡池强motion last1000，不能换hard或追加权重')
                    loader = rs_loader; complete = deepcopy(reference['training_complete']); data_ref(complete)
                models.append(dict(model_id=model_id(regime,fold,seed), regime=regime, fold=fold, seed=seed,
                    architecture='original_strong_motion_v8', use_pose=False, checkpoint=checkpoint, checkpoint_bytes_read=False,
                    training_receipt=deepcopy(reference['training_receipt']), training_complete=complete,
                    run=str(run), binding=deepcopy(binding), loader=deepcopy(loader),
                    normalizer=deepcopy(folds[fold]['normalizer']), clean_R_pool=deepcopy(folds[fold]['clean_R_pool']),
                    baseR_exposure=deepcopy(folds[fold]['baseR_exposures'][str(seed)]), baseR_exposure_component='real',
                    historical_training_exposure_table=deepcopy(training['exposures']['balanced'][fold][str(seed)]) if regime=='RS' else
                        deepcopy(folds[fold]['baseR_exposures'][str(seed)]),
                    original_training_budget=dict(actual_updates=1000,R_window_exposures=3000,S_window_exposures=0 if regime=='R' else 1000),
                    historical_record_limit=reference.get('historical_recording_limit','full_v10_recorded_history_preserved'),
                    calibration=dict(extra_clean_R_window_evaluations=1000,unique_within_fold_pool=1000,
                        training_S_read=False, augmentation=False, optimizer_SGD_updates=0,
                        unknown_pairs='retain_logit_records_do_not_fit', empty_known_window='zero_contribution_keep1000_denominator'),
                    beta0_baseline_alias_authorized=False, beta0_alias_requires='exact_beta32_zero_and_identity_forward_numeric_proof'))
    lookup = {(m['regime'],m['fold'],m['seed']):m for m in models}
    require(len(models) == len(lookup) == 18, '冻结18模型不能缺失/重复')
    for fold in FOLDS:
        for seed in SEEDS:
            a,b=lookup['R',fold,seed],lookup['RS',fold,seed]
            require(a['binding']['initialization_sha256'] == b['binding']['initialization_sha256']
                    and a['binding']['R_window_UID_chain_sha256'] == b['binding']['R_window_UID_chain_sha256'], '原R/RS初始化/基础R同序身份不同')
    return models


def expected_baseline_cells(sources):
    return {(regime,sequence,fold,seed) for regime in REGIMES for sequence in sources
            for fold in ((OLD[sequence],) if sequence in OLD else FOLDS) for seed in SEEDS}


def baseline_record(regime, reference, expected_job, sequence, sources, protocols, model_lookup):
    body = read(reference); job = body['job']; seven = sequence in protocols['seven_sequences']
    require(body['status'] == 'complete' and body['DO_PREPROC'] is False and body['predictions_GT_filtered'] is False
            and body['test_read'] is False and job == expected_job and job['sequence'] == sequence
            and body['frames'] == sources[sequence]['frames'] and job['method'] == 'motion', '历史参照不是固定完整强motion评价')
    require(body['schema'] == ('seven_match_ABC_trackeval_gap_v1' if seven else 'v10_independent_trackeval_gap_v1')
            and body['protocol_sha256'] == protocols['ABC' if seven else 'v10']['sha256'], '参照原协议/schema身份不同')
    if seven:
        require(job['kind'] == 'learned' and job['group'] == ('A' if regime=='R' else 'B'), '七场只准A/B原R/RS，不借C/gated')
    else:
        require(job['kind'] == ('pure_R' if regime=='R' else 'new_RS')
                and (regime == 'R' or job['pool'] == 'balanced'), '旧五只准pureR或balancedRS')
    key = regime,job['fold'],job['seed']; require(key in model_lookup, '基线含未选fold/seed')
    model = model_lookup[key]
    metric_path = safe(reference['path'])
    receipt_ref = dict(path=str(metric_path.parent.parent/'tracking/receipt.json'),sha256=body['tracking_receipt_sha256'])
    receipt = read(receipt_ref)
    require(receipt['status'] == 'complete' and receipt['job'] == job and receipt['binding'] == model['binding']
            and receipt['protocol_sha256'] == protocols['ABC' if seven else 'v10']['sha256']
            and receipt['test_read'] is False and receipt['frames'] == sources[sequence]['frames'],
            '历史beta0来源不是该18模型的同缓存实物')
    if seven:
        require(receipt['schema'] == 'seven_match_ABC_free_tracking_v1'
                and receipt['GT_used_for_tracking'] is False and receipt['evaluation_GT_annotations_loaded'] is False,
                '七场历史schema/GT隔离证明不同')
        cache_binding = 'frozen_protocol_sources_not_legacy_receipt_field'
    else:
        require(receipt['schema'] == 'v10_independent_free_tracking_v1' and receipt['GT_read'] is False
                and receipt['cache'] == sources[sequence]['cache'], '旧五历史schema/直接缓存引用不同')
        cache_binding = 'original_tracking_receipt_cache_ref'
    require(isinstance(receipt['frame_counts'],list) and len(receipt['frame_counts']) == receipt['frames']
            and all(type(count) is int and count >= 0 for count in receipt['frame_counts'])
            and sum(receipt['frame_counts']) == receipt['tracked_rows'], '历史输出逐帧数/总行数不同')
    mot = dict(path=str(Path(receipt_ref['path']).parent/'data'/(sequence+'.txt')),sha256=receipt['mot_sha256']); data_ref(mot)
    return dict(regime=regime,sequence=sequence,fold=job['fold'],seed=job['seed'],model_id=model['model_id'],
        metric_report=deepcopy(reference), tracking_receipt=receipt_ref,mot=mot,frames=body['frames'],
        frame_counts=deepcopy(receipt['frame_counts']),tracked_rows=receipt['tracked_rows'],
        source_cache=deepcopy(sources[sequence]['cache']),source_cache_binding=cache_binding,new_tracking_or_optimizer_updates=0,
        alias='historical_reference_only_pending_beta32_zero_identity_forward_proof')


def baselines(velocity, old_analysis, ABC_analysis, sources, protocols, models):
    lookup={(m['regime'],m['fold'],m['seed']):m for m in models}; selected=[]
    require(old_analysis['status'] == 'complete_all253_tracking_comparisons'
            and old_analysis['protocol_sha256'] == protocols['v10']['sha256']
            and ABC_analysis['status'] == 'complete392_all_results_and_paired_intervals'
            and ABC_analysis['protocol_sha256'] == protocols['ABC']['sha256'], '原完整分析必须与追踪协议相同')
    for row in old_analysis['all_results']:
        job=row['job']
        if job['kind']=='pure_R' and job.get('method')=='motion':selected.append(('R',row['report'],job,job['sequence']))
    for row in csv_rows(ABC_analysis['all_results_csv']):
        if row['kind']=='learned' and row['group']=='A' and row['method']=='motion':
            reference=dict(path=row['report_path'],sha256=row['report_sha256']);body=read(reference)
            selected.append(('R',reference,body['job'],row['sequence']))
    refs=velocity['reference_reports']['strong_motion_RS'];require(len(refs)==90,'RS90原引用必须完整')
    for row in refs:selected.append(('RS',row['report'],row['job'],row['job']['sequence']))
    result=[baseline_record(regime,reference,job,sequence,sources,protocols,lookup) for regime,reference,job,sequence in selected]
    keys=[(r['regime'],r['sequence'],r['fold'],r['seed']) for r in result]
    require(len(result)==len(set(keys))==180 and set(keys)==expected_baseline_cells(sources)
            and Counter(r['regime'] for r in result)==Counter(R=90,RS=90), '原R90/RS90全十二来源不能缺失或重复')
    return result


def build_inventory(source_velocity_cfg_ref, ABC_cfg_ref, v10_training_ref, baseline_analysis_refs):
    require(source_velocity_cfg_ref['sha256']==FIXED['velocity'] and ABC_cfg_ref['sha256']==FIXED['ABC']
            and v10_training_ref['sha256']==FIXED['training'] and set(baseline_analysis_refs)=={'v10','ABC'}
            and baseline_analysis_refs['v10']['sha256']==FIXED['v10_analysis']
            and baseline_analysis_refs['ABC']['sha256']==FIXED['ABC_analysis'], '只允许明确已验来源，禁止隐式路径猜测')
    velocity,ABC,training=[read(reference) for reference in (source_velocity_cfg_ref,ABC_cfg_ref,v10_training_ref)]
    old_cfg=read(velocity['source_tracking_config']);old8=read(training['v8_protocol']);c_protocol=read(ABC['C_protocol'])
    require(velocity['source_seven_tracking_config']==ABC_cfg_ref and ABC['source_tracking_config']==velocity['source_tracking_config']
            and old_cfg['training_protocol']==v10_training_ref and training['schema']=='v10_recorded_association_training_v1'
            and training['test116187_sealed'] is True and ABC['test_sealed'] is True, '原v10/ABC/18模型训练链不一致')
    sources=velocity['sources'];panels=velocity['panels']
    require(sources==dict(old_cfg['sources'],**ABC['sources']) and len(sources)==12
            and [len(panels[k]) for k in ('original_heldout','old_external','seven_observed')]==[3,2,7], '原十二3/2/7验证范围不同')
    folds=clean_folds(training,old8,c_protocol)
    models=models_from(v10_training_ref,training,old8,c_protocol,folds)
    protocols=dict(v10=velocity['source_tracking_config'],ABC=ABC_cfg_ref,seven_sequences=panels['seven_observed'])
    references=baselines(velocity,read(baseline_analysis_refs['v10']),read(baseline_analysis_refs['ABC']),sources,protocols,models)
    return dict(schema='trainR_intercept_source_inventory_v1',status='complete18_model_refs3_cleanR_pools180_baseline_refs_no_weight_or_pool_loaded',
        source_refs=dict(velocity=deepcopy(source_velocity_cfg_ref),ABC=deepcopy(ABC_cfg_ref),training=deepcopy(v10_training_ref),
            baseline_analyses=deepcopy(baseline_analysis_refs)),sources=deepcopy(sources),panels=deepcopy(panels),folds=folds,models=models,
        baseline_units=references,feature_source=source_file(old8,'python/src/grf_ue_bridge/learned_association_features_v8.py'),
        feature_function='features',normalizer_source=source_file(old8,'python/src/grf_ue_bridge/learned_association_model_v8.py'),
        normalization='original_feature_normalizer_transform_use_pose_false',input_Pose_used=False,
        calibration_policy=dict(unique_windows_per_fold=1000,model_units=18,planned_model_window_evaluations=18000,
            cross_fold_unique_window_count_not_claimed=True,optimizer_SGD_updates=0,beta='one_trainR_only_intercept_per_frozen_model;sign_not_fixed',
            objective_denominator='all1000_windows;within_window_mean_known_pairs;empty_known_window_zero',
            unknown_pairs='preserve_not_fit',augmentation=False,source_S_windows=0,source_val_test_windows=0,
            additional_calibration_label_and_compute_budget=True,strict_same_total_window_exposure_claim=False,
            new_independent_real_data_claim=False,zero_supervision_claim=False),
        old_training_or_budget_audit_rerun=False,checkpoint_bytes_read=False,clean_pool_contents_read=False,
        cache_or_GT_annotations_read=False,model_loaded=False,new_optimizer_updates=0,test_read=False,
        validation_metric_values_used_for_calibration=False,beta0_baseline_alias_authorized=False,
        limitations=['1000唯一与允许训练域由原构建收据声明；首次实际logit提取须核全部UID/窗口/游戏/标签，清单不冒充已读池。',
            '18模型权重仅绑定引用，实际加载须用原入口核身份、normalizer及FP32；历史R缺失记录不补造。',
            '每模型额外复读1000原R，是额外计算/标签曝光，不等新增独立R，也不称严格同总窗口预算或零监督。',
            '历史R/RS90各全十二参照只来源复用；beta0别名需另证beta32精确0与identity forward，清单不自动放行。'])
