"""训练R截距校准的完整配对描述；不重评分、不读预测/GT坐标、不作性能通过判定。"""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
from statistics import mean
import stat
import sys

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/trainR_intercept_calibration_a01'
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
PANELS = ('original_heldout', 'old_external', 'seven_observed')
REGIMES = ('R', 'RS')
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
COMPARISONS = ('R_beta_minus_zero', 'RS_beta_minus_zero', 'RS_minus_R_calibration_interaction')
INTERVAL_SHA = '7458aa01dc5396124ac40d51ac3a3ff9851ce2a8cb4e61e64f4e7d9b6b695e7e'
OLD_PROTOCOL_SHA = 'f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1'
SEVEN_PROTOCOL_SHA = 'fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78'
STATUS = 'complete180_trainR_intercept_results180_baselines270_pairs45_metric9_gap_descriptions'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(value):
    path = Path(value)
    require(path.is_absolute(), '输入/输出须绝对物理路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
        for part in path.parts), '仅实际DResearch；最终测试继续封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                '不跟随junction或链接')
    return path


def sha(path):
    return hashlib.sha256(physical(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def checked(reference):
    require(isinstance(reference, dict) and set(reference) >= {'path', 'sha256'}
        and re.fullmatch('[0-9a-f]{64}', reference['sha256']), '缺已签来源引用')
    path = physical(reference['path'])
    require(path.suffix in ('.json', '.csv', '.py') and path.name not in ('gap_registry.json', 'posthoc_GT_labels.json'),
        '分析只读报告/源码元数据，不打开MOT、cache、池、权重或GT坐标账本')
    require(path.is_file() and sha(path) == reference['sha256'], '来源元数据/SHA改变：'+str(path))
    return path


def read(reference):
    return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def finite(value, message='指标必须有限实数'):
    require(type(value) in (int, float) and math.isfinite(value), message)
    return value


def finite_metrics(values):
    require(isinstance(values, dict) and set(METRICS) <= set(values), '全部五指标不可缺失')
    return {key: finite(values[key]) for key in METRICS}


def panels_map(panels):
    require(set(panels) == set(PANELS) and [len(panels[key]) for key in PANELS] == [3, 2, 7], '固定3/2/7分别报告')
    result = {sequence: panel for panel in PANELS for sequence in panels[panel]}
    require(len(result) == sum(map(len, panels.values())) == 12 and set(panels['original_heldout']) == set(OLD),
        '比赛面板重复/缺失，不能把fold/seed当比赛')
    return result


def expected_cells(panels):
    return {(regime, sequence, fold, seed) for regime in REGIMES for sequence in panels_map(panels)
        for fold in ((OLD[sequence],) if sequence in OLD else FOLDS) for seed in SEEDS}


def cell_key(record):
    return tuple(record[key] for key in ('regime', 'sequence', 'fold', 'seed'))


def gap_values(overall):
    total, success, rate = (overall[key] for key in ('total_events', 'same_prediction_ID_recovered', 'recovery_rate'))
    require(type(total) is int and type(success) is int and 0 <= success <= total, '全注册gap分母/成功数无效')
    require((rate is None and success == 0) if total == 0 else
        (type(rate) in (int, float) and math.isfinite(rate) and abs(rate-success/total) <= 1e-12),
        '原全事件分母不变，零事件率必须null')
    return total, success, rate


def indexed_records(records, panels, origin):
    result = {}
    for record in records:
        key = cell_key(record)
        require(key not in result, origin+'重复单元')
        finite_metrics(record['metrics']); gap_values(record['gap'])
        result[key] = record
    require(len(records) == 180 and set(result) == expected_cells(panels), origin+'必须180个完整同fold/seed/比赛单元')
    return result


def source_gap_denominators(records, panels):
    result = {}
    for sequence in panels_map(panels):
        totals = {gap_values(row['gap'])[0] for row in records if row['sequence'] == sequence}
        require(len(totals) == 1, '同场原全注册事件不应随R/RS或训练面板变化')
        result[sequence] = totals.pop()
    return result


def paired_cells(target, baseline, panels):
    """单元先配对，交互为同fold/seed四项差值，不混成独立训练重复。"""
    panel_by_match = panels_map(panels)
    new, old = indexed_records(target, panels, '校准'), indexed_records(baseline, panels, '原参照')
    for key in new:
        require(new[key]['model_id'] == old[key]['model_id'], '原模型身份必须严格配对')
    result = {key: [] for key in COMPARISONS}
    base_cells = sorted((sequence, fold, seed) for regime, sequence, fold, seed in new if regime == 'R')
    for sequence, fold, seed in base_cells:
        quartet = {regime+'_'+condition: (new if condition == 'beta' else old)[regime, sequence, fold, seed]
            for regime in REGIMES for condition in ('beta', 'zero')}
        all_gaps = {key: gap_values(row['gap']) for key, row in quartet.items()}
        require(len({value[0] for value in all_gaps.values()}) == 1, '四项交互必须同原全事件分母')
        denominator = next(iter(all_gaps.values()))[0]
        deltas = {regime: {metric: quartet[regime+'_beta']['metrics'][metric]-quartet[regime+'_zero']['metrics'][metric]
            for metric in METRICS} for regime in REGIMES}
        gap_deltas = {regime: 100*(all_gaps[regime+'_beta'][2]-all_gaps[regime+'_zero'][2]) if denominator else None
            for regime in REGIMES}
        for name in COMPARISONS:
            interaction = name == COMPARISONS[2]
            regime = None if interaction else ('R' if name == COMPARISONS[0] else 'RS')
            terms = dict(quartet) if interaction else {key: quartet[key] for key in (regime+'_beta', regime+'_zero')}
            result[name].append(dict(comparison=name, panel=panel_by_match[sequence], sequence=sequence, fold=fold, seed=seed,
                delta_pp={metric: deltas['RS'][metric]-deltas['R'][metric] if interaction else deltas[regime][metric] for metric in METRICS},
                gap=dict(total_registered_events=denominator,
                    delta_recovery_rate_pp=(gap_deltas['RS']-gap_deltas['R'] if interaction else gap_deltas[regime]) if denominator else None,
                    terms={key: dict(total_events=all_gaps[key][0], success=all_gaps[key][1], rate=all_gaps[key][2]) for key in terms}),
                source_terms={key: dict(model_id=row['model_id'], report=row['report']) for key, row in terms.items()}))
    require(len(base_cells) == 90 and all(len(rows) == 90 for rows in result.values()), '三比较必须各90配对单元')
    return result


def paired_matches(cells, panels):
    result = []
    for name in COMPARISONS:
        rows = cells[name]
        require(len(rows) == len({(r['sequence'], r['fold'], r['seed']) for r in rows}) == 90, '配对单元缺失/重复')
        for panel in PANELS:
            for sequence in panels[panel]:
                selected = [r for r in rows if r['sequence'] == sequence]
                expected = {(OLD[sequence], seed) for seed in SEEDS} if sequence in OLD else {(fold, seed) for fold in FOLDS for seed in SEEDS}
                require({(r['fold'], r['seed']) for r in selected} == expected
                    and all(r['panel'] == panel for r in selected), '每比赛先均全部匹配训练单元，不能省略负项')
                require(len({r['gap']['total_registered_events'] for r in selected}) == 1, '同场原gap分母不应随模型变化')
                denominator = selected[0]['gap']['total_registered_events']
                gap = mean(r['gap']['delta_recovery_rate_pp'] for r in selected) if denominator else None
                result.append(dict(comparison=name, panel=panel, sequence=sequence, matched_training_cells=len(selected),
                    delta_pp={metric: mean(r['delta_pp'][metric] for r in selected) for metric in METRICS},
                    total_registered_events=denominator, delta_recovery_rate_pp=gap))
    require(len(result) == 36, '必须三比较各十二比赛')
    return result


def describe(matches, panels, interval_fn):
    metrics, gaps = {}, {}
    for name in COMPARISONS:
        metrics[name], gaps[name] = {}, {}
        for panel in PANELS:
            rows = [row for row in matches if row['comparison'] == name and row['panel'] == panel]
            require(len(rows) == len(panels[panel]) and {r['sequence'] for r in rows} == set(panels[panel]), '描述比赛缺失/重复')
            metrics[name][panel] = {metric: interval_fn({r['sequence']: r['delta_pp'][metric] for r in rows}) for metric in METRICS}
            values = {r['sequence']: r['delta_recovery_rate_pp'] for r in rows if r['delta_recovery_rate_pp'] is not None}
            nulls = [r['sequence'] for r in rows if r['delta_recovery_rate_pp'] is None]
            if len(values) >= 2:
                summary = interval_fn(values)
            else:
                summary = dict(n_independent_matches=len(values), match_deltas_pp=values,
                    mean_delta_pp=mean(values.values()) if values else None, Student_t_95CI=None,
                    percentile_match_bootstrap_95CI=None, leave_one_match_out_mean=None,
                    formal_equivalence_or_noninferiority_test=False, margin=None,
                    status='fewer_than_two_matches_with_registered_events_no_interval')
            gaps[name][panel] = dict(summary, zero_event_matches_retained_null=nulls,
                outcome='all_registered_trusted_detection_gap_proxy_not_physical_occlusion')
    return metrics, gaps


def interval_module(reference):
    require(reference['sha256'] == INTERVAL_SHA, '只能复用已冻结比赛配对区间纯函数字节')
    path = checked(reference)
    spec = importlib.util.spec_from_file_location('_trainR_intercept_frozen_intervals', path)
    module = importlib.util.module_from_spec(spec)
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module


def validate_config(config_path):
    config_path = physical(config_path); cfg_ref = ref(config_path); cfg = read(cfg_ref)
    require(cfg['schema'] == 'trainR_intercept_tracking_protocol_v1' and cfg['approved_by'] == 'root'
        and cfg['test_sealed'] is True and cfg['formal_equivalence_or_noninferiority'] is False
        and cfg['alias_enabled'] is False, '必须独立已签截距协议；测试封存、无等效判定、本轮不启alias')
    inventory = read(cfg['inventory'])
    require(inventory['schema'] == 'trainR_intercept_source_inventory_v1'
        and inventory['status'] == 'complete18_model_refs3_cleanR_pools180_baseline_refs_no_weight_or_pool_loaded'
        and cfg['sources'] == inventory['sources'] and cfg['panels'] == inventory['panels'], '来源清单/十二面板不同')
    panels_map(cfg['panels'])
    require(len(cfg['sources']) == 12 and set(cfg['sources']) == set(panels_map(cfg['panels'])), '固定十二输入不可变')
    models = {m['model_id']: m for m in inventory['models']}
    require(len(inventory['models']) == len(models) == 18 and {(m['regime'], m['fold'], m['seed']) for m in models.values()}
        == {(r, f, s) for r in REGIMES for f in FOLDS for s in SEEDS}, '十八原模型完整身份不能缺失')
    cells = []
    for job in cfg['jobs']:
        require(set(job) == {'job_id', 'model_id', 'regime', 'sequence', 'fold', 'seed'} and job['model_id'] in models,
            '正式job精确字段/模型来源不符')
        model = models[job['model_id']]
        require(all(job[key] == model[key] for key in ('regime', 'fold', 'seed')), 'job不能换训练面板或R/RS模型')
        cells.append(cell_key(job))
    require(len(cfg['jobs']) == len({j['job_id'] for j in cfg['jobs']}) == len(set(cells)) == 180
        and set(cells) == expected_cells(cfg['panels']), '正式180矩阵缺失/重复/范围外')
    require(cfg['interval_source']['sha256'] == INTERVAL_SHA, '描述区间纯函数来源不同')
    return cfg_ref, cfg, inventory, models


def fit_records(cfg, inventory, models):
    complete = read(cfg['fit_complete'])
    require(complete['schema'] == 'trainR_intercept_fit_complete_v1'
        and complete['status'] == 'complete18_trainR_only_scalar_calibrations_full_records_and_exit_verified'
        and complete['fit_processes_absent'] is True and complete['calibrations'] == cfg['calibrations']
        and complete['model_order'] == [m['model_id'] for m in inventory['models']]
        and set(cfg['calibrations']) == set(models), '十八实际拟合/退出完整链不同')
    totals = complete['totals']
    require(totals['models'] == 18 and totals['clean_R_model_window_evaluations'] == 18000
        and totals['optimizer_updates'] == 0, '拟合额外1000R每模型/18000R计算预算应另列，无SGD')
    result = []
    for model in inventory['models']:
        mid = model['model_id']; reference = cfg['calibrations'][mid]; fit = read(reference)
        require(fit['schema'] == 'trainR_intercept_fit_v1'
            and fit['status'] == 'complete_finite_trainR_intercept_fit_not_tracking_effect'
            and fit['finite_minimizer'] is True and fit['model_spec'] == model
            and all(fit[key] == model[key] for key in ('model_id', 'regime', 'fold', 'seed'))
            and fit['optimizer_updates'] == 0 and fit['new_model_training'] is False
            and fit['validation_or_test_inputs_used'] is False
            and fit['source_weights_or_normalizer_or_features_changed'] is False
            and fit['fitting_objective_improvement_is_tracking_effectiveness_evidence'] is False,
            '校准拟合来源/零SGD/训练域边界不同，不能冒充独立跟踪效果')
        pair = fit['totals']
        require(pair['windows'] == 1000 and all(type(pair[k]) is int and pair[k] >= 0
            for k in ('all_pair_count', 'known_pair_count', 'unknown_pair_count'))
            and pair['all_pair_count'] == pair['known_pair_count']+pair['unknown_pair_count'], '完整R拟合分母/unknown账本不同')
        result.append(dict(model_id=mid, regime=model['regime'], fold=model['fold'], seed=model['seed'], fit=reference,
            beta64=finite(fit['beta64']), apply_beta32=finite(fit['apply_beta32']),
            windows=1000, all_pair_count=pair['all_pair_count'], known_pair_count=pair['known_pair_count'],
            unknown_pair_count=pair['unknown_pair_count'], optimizer_updates=0,
            before_NLL=finite(fit['before']['NLL']), after_fit64_NLL=finite(fit['after_fit64']['NLL']),
            after_apply32_NLL=finite(fit['after_apply32']['NLL']),
            NLL_fit_is_independent_tracking_effectiveness_evidence=False))
    require(all(sum(row[key] for row in result) == totals[key] for key in ('all_pair_count', 'known_pair_count', 'unknown_pair_count')),
        '十八拟合全pair/known/unknown总预算不同')
    return result


def baseline_records(inventory, models):
    result = []
    for entry in inventory['baseline_units']:
        model = models[entry['model_id']]; sequence = entry['sequence']; body = read(entry['metric_report'])
        seven = sequence in inventory['panels']['seven_observed']; job = body['job']
        require(body['status'] == 'complete' and body['schema'] == ('seven_match_ABC_trackeval_gap_v1' if seven else 'v10_independent_trackeval_gap_v1')
            and body['protocol_sha256'] == (SEVEN_PROTOCOL_SHA if seven else OLD_PROTOCOL_SHA)
            and body['DO_PREPROC'] is False and body['predictions_GT_filtered'] is False and body['test_read'] is False
            and all(job[key] == entry[key] == model[key] for key in ('fold', 'seed'))
            and entry['regime'] == model['regime'] and job['sequence'] == sequence and job['method'] == 'motion'
            and body['frames'] == inventory['sources'][sequence]['frames'], '历史180参照真实评价/模型/范围/GT边界不同')
        if seven:
            require(job['kind'] == 'learned' and job['group'] == ('A' if entry['regime'] == 'R' else 'B'), '七场只准A纯R/B平衡RS')
        else:
            require(job['kind'] == ('pure_R' if entry['regime'] == 'R' else 'new_RS')
                and (entry['regime'] == 'R' or job['pool'] == 'balanced'), '旧五只准原R或平衡RS')
        require(body['tracking_receipt_sha256'] == entry['tracking_receipt']['sha256'], '基线收据不是来源清单实物')
        result.append(dict(**{key: entry[key] for key in ('model_id', 'regime', 'sequence', 'fold', 'seed')},
            condition='historical_beta_zero_reference', metrics=finite_metrics(body['summary'][sequence]['metrics_percent']),
            gap=body['recovery']['overall'], report=entry['metric_report'], tracking_receipt=entry['tracking_receipt'],
            frames=body['frames'], source_origin='historical_readonly_no_new_tracking', alias_used=False))
    indexed_records(result, inventory['panels'], '历史参照')
    require(sum(source_gap_denominators(result, inventory['panels']).values()) == 3690, '固定十二源全注册gap事件应3690，按源只计一次')
    return result


def target_records(cfg_ref, cfg, control, models, fits, baseline):
    manifest_ref = ref(control/'manifest.json'); manifest = read(manifest_ref)
    require(manifest['schema'] == 'trainR_intercept_tracking_manifest_v1'
        and manifest['status'] == 'complete180_trainR_intercept_tracking_and_evaluation'
        and manifest['config_sha256'] == cfg_ref['sha256'] and len(manifest['reports']) == 180
        and [entry['job'] for entry in manifest['reports']] == cfg['jobs'], '180正式评价矩阵未完整，不能分析局部或重排来源')
    fit_lookup = {row['model_id']: row for row in fits}
    baseline_paths = {row['report']['path'] for row in baseline}
    result = []
    for entry in manifest['reports']:
        job, reference = entry['job'], entry['report']; model = models[job['model_id']]; body = read(reference)
        require(reference['path'] not in baseline_paths and control in physical(reference['path']).parents,
            '本轮即使beta32精确零也须全新180追踪，不把历史引用冒充新评价')
        require(body['schema'] == 'trainR_intercept_tracking_metric_v1' and body['status'] == 'complete'
            and body['job'] == job and body['protocol_sha256'] == cfg_ref['sha256']
            and body['DO_PREPROC'] is False and body['predictions_GT_filtered'] is False and body['test_read'] is False
            and body['frames'] == cfg['sources'][job['sequence']]['frames']
            and type(body['GT_rows']) is int and body['GT_rows'] == cfg['expected_GT_rows'][job['sequence']] > 0
            and type(body['tracked_rows']) is int and body['tracked_rows'] >= 0, '新评价schema/范围/原全预测或GT边界不同')
        require(finite_metrics(body['metrics']) == finite_metrics(body['summary'][job['sequence']]['metrics_percent']),
            '新五指标必须与原实际TrackEval序列汇总逐值相同')
        receipt = read(body['tracking_receipt'])
        require(receipt['schema'] == 'trainR_intercept_tracking_receipt_v1' and receipt['status'] == 'complete'
            and receipt['job'] == job and receipt['protocol_sha256'] == cfg_ref['sha256']
            and receipt['model_id'] == job['model_id'] and receipt['binding'] == model['binding']
            and receipt['fit'] == cfg['calibrations'][job['model_id']]
            and finite(receipt['beta32']) == fit_lookup[job['model_id']]['apply_beta32']
            and receipt['GT_used_for_tracking'] is False and receipt['test_read'] is False
            and receipt['evaluation_GT_coordinate_files_opened'] is False and receipt['alias_used'] is False
            and receipt['diagnostic_beta0'] is False and receipt['prefix_frames'] is None
            and receipt['source_inputs_unchanged'] is True and receipt['original_model_state_unchanged'] is True
            and receipt['original_normalizer_unchanged'] is True and receipt['native_ordered_batch_forward_preserved'] is True
            and receipt['GPU_used'] is False and receipt['new_optimizer_updates'] == 0
            and receipt['source_cache'] == cfg['sources'][job['sequence']]['cache']
            and receipt['frames'] == body['frames'] and receipt['tracked_rows'] == body['tracked_rows'],
            '实际追踪收据模型/固定beta32/输入来源/GT隔离不同')
        require(isinstance(receipt['frame_counts'], list) and len(receipt['frame_counts']) == receipt['frames']
            and all(type(count) is int and count >= 0 for count in receipt['frame_counts'])
            and sum(receipt['frame_counts']) == receipt['tracked_rows'], '新追踪全帧输出计数不同')
        require(body['source_cache'] == receipt['source_cache'] and body['fit'] == receipt['fit']
            and body['beta32'] == receipt['beta32'], '新评价不能换缓存、拟合或beta32')
        result.append(dict(**{key: job[key] for key in ('model_id', 'regime', 'sequence', 'fold', 'seed')},
            condition='calibrated_beta32', metrics=finite_metrics(body['metrics']), gap=body['gap']['overall'],
            report=reference, tracking_receipt=body['tracking_receipt'], frames=body['frames'],
            source_origin='new_actual_tracking_even_when_beta32_exact_zero', alias_used=False))
    require(len({row['report']['path'] for row in result}) == 180, '新报告不能重复路径填充')
    indexed_records(result, cfg['panels'], '校准')
    require(source_gap_denominators(result, cfg['panels']) == source_gap_denominators(baseline, cfg['panels']),
        '校准不能改变原源级全事件分母')
    return result, manifest_ref


def write_csv(path, fields, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def analyze(cfg, control_root, output):
    cfg_ref, config, inventory, models = validate_config(cfg)
    control, output = physical(control_root), physical(output)
    require(EXP in control.parents and EXP in output.parents and not output.exists(), '独立实验分析范围/已有partial，禁止覆盖')
    fits = fit_records(config, inventory, models)
    baseline = baseline_records(inventory, models)
    target, manifest = target_records(cfg_ref, config, control, models, fits, baseline)
    cells = paired_cells(target, baseline, config['panels']); matches = paired_matches(cells, config['panels'])
    statistics = interval_module(config['interval_source'])
    metric_intervals, gap_intervals = describe(matches, config['panels'], statistics.effect_intervals)
    output.mkdir(parents=True)
    fields = ['condition', 'model_id', 'regime', 'sequence', 'fold', 'seed', *METRICS,
        'gap_events', 'gap_success', 'gap_rate', 'frames', 'source_origin', 'alias_used', 'report_path', 'report_sha256',
        'tracking_receipt_path', 'tracking_receipt_sha256']
    raw = []
    for row in target+baseline:
        total, success, rate = gap_values(row['gap'])
        raw.append(dict(**{key: row[key] for key in ('condition', 'model_id', 'regime', 'sequence', 'fold', 'seed', 'frames', 'source_origin', 'alias_used')},
            **row['metrics'], gap_events=total, gap_success=success, gap_rate=rate,
            report_path=row['report']['path'], report_sha256=row['report']['sha256'],
            tracking_receipt_path=row['tracking_receipt']['path'], tracking_receipt_sha256=row['tracking_receipt']['sha256']))
    write_csv(output/'all_results.csv', fields, raw)
    pair_fields = ['comparison', 'panel', 'sequence', 'fold', 'seed']
    paired = [row for name in COMPARISONS for row in cells[name]]
    write_csv(output/'all_paired_cells.csv', pair_fields+[*METRICS, 'source_terms'],
        [dict(**{key: row[key] for key in pair_fields}, **row['delta_pp'], source_terms=canonical(row['source_terms'])) for row in paired])
    write_csv(output/'all_paired_gaps.csv', pair_fields+['total_registered_events', 'delta_recovery_rate_pp', 'source_gap_terms', 'source_terms'],
        [dict(**{key: row[key] for key in pair_fields}, total_registered_events=row['gap']['total_registered_events'],
            delta_recovery_rate_pp=row['gap']['delta_recovery_rate_pp'], source_gap_terms=canonical(row['gap']['terms']),
            source_terms=canonical(row['source_terms'])) for row in paired])
    write_csv(output/'all_paired_matches.csv', ['comparison', 'panel', 'sequence', 'matched_training_cells', *METRICS,
        'total_registered_events', 'delta_recovery_rate_pp'],
        [dict(**{key: row[key] for key in ('comparison', 'panel', 'sequence', 'matched_training_cells', 'total_registered_events', 'delta_recovery_rate_pp')},
            **row['delta_pp']) for row in matches])
    fit_fields = ['model_id', 'regime', 'fold', 'seed', 'beta64', 'apply_beta32', 'windows', 'all_pair_count', 'known_pair_count',
        'unknown_pair_count', 'optimizer_updates', 'before_NLL', 'after_fit64_NLL', 'after_apply32_NLL',
        'NLL_fit_is_independent_tracking_effectiveness_evidence', 'fit_path', 'fit_sha256']
    write_csv(output/'fit_records18.csv', fit_fields, [dict(**{key: row[key] for key in fit_fields if key not in ('fit_path', 'fit_sha256')},
        fit_path=row['fit']['path'], fit_sha256=row['fit']['sha256']) for row in fits])
    report = dict(schema='trainR_intercept_complete_paired_intervals_v1', status=STATUS, protocol=cfg_ref,
        inventory=config['inventory'], fit_complete=config['fit_complete'], formal_evaluation_manifest=manifest,
        interval_source=config['interval_source'], comparisons=metric_intervals, gap_comparisons=gap_intervals,
        panels=config['panels'], primary_comparisons=list(COMPARISONS[:2]), secondary_comparison=COMPARISONS[2], primary_metric='AssA',
        new_tracking_evaluations=180, historical_reference_evaluations=180, paired_cells=270, paired_gap_cells=270,
        paired_matches=36, metric_interval_descriptions=45, gap_interval_descriptions=9,
        source_gap_event_denominators=source_gap_denominators(baseline, config['panels']),
        gap_events_counted_once_per_source=sum(source_gap_denominators(baseline, config['panels']).values()),
        fit_models=18, extra_clean_R_model_window_evaluations=18000, fit_optimizer_updates=0,
        fit_pair_budget={key: sum(row[key] for row in fits) for key in ('all_pair_count', 'known_pair_count', 'unknown_pair_count')},
        fitting_NLL_improvement_is_tracking_effectiveness_evidence=False, historical_alias_used=False,
        all_results_csv=ref(output/'all_results.csv'), all_paired_cells_csv=ref(output/'all_paired_cells.csv'),
        all_paired_gaps_csv=ref(output/'all_paired_gaps.csv'), all_paired_matches_csv=ref(output/'all_paired_matches.csv'),
        fit_records_csv=ref(output/'fit_records18.csv'), all_actual_reports=[row['report'] for row in target],
        all_reference_reports=[row['report'] for row in baseline], all_fit_records=[row['fit'] for row in fits],
        all_folds_seeds_negative_zero_and_null_results_retained=True, formal_equivalence_or_noninferiority=False,
        performance_margin=None, test_read=False, analysis_optimizer_updates=0,
        limitations=['三面板均为已观察开发片段，3/2/7分别报告，不合并成一个总体精度结论。',
            '先按同比赛内匹配fold/seed平均，再比赛等权；训练单元不是独立比赛。',
            '45指标和9gap区间未经多比较校正，仅描述；不挑有利区间，不以跨0证明等效。',
            '区间条件于固定训练面板；便利短片、小样本及比赛近似独立/正态假设限制保留。',
            '拟合额外每模型复读1000原R，合计18000R模型窗口计算/标签曝光；无SGD不等零监督或严格同总曝光。',
            '训练NLL属于拟合目标描述，不是独立跟踪效果证明；全部beta符号及负结果保留。',
            '截距仅改变原logit常数项，不能据此证明机制主因、Pose增量或合成等价真实。',
            '全注册可信检测断档作分母，零事件保留null；此proxy不是物理遮挡恢复。',
            '本轮全部180校准单元实际新追踪，即使beta32精确0也不借历史结果冒充新输出。'])
    with (output/'report.json').open('x', encoding='utf-8') as stream:
        stream.write(canonical(report)+'\n')
    return dict(status=STATUS, new_tracking_evaluations=180, historical_reference_evaluations=180,
        paired_cells=270, paired_matches=36, metric_interval_descriptions=45, gap_interval_descriptions=9)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    print(canonical(analyze(args.config, args.control, args.output)))
