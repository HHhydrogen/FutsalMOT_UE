"""R窗口来源单因素的完整配对分析；只读小收据，不加载模型、缓存或GT。"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import stat
from statistics import mean, stdev

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/state_aligned_training_a01'
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
PANELS = ('original_heldout', 'old_external', 'seven_observed')
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
CONDITIONS = ('new_R', 'new_RS', 'old_R', 'old_RS')
COMPARISONS = ('new_RS_minus_old_RS', 'new_R_minus_old_R', 'new_RS_minus_new_R', 'synthetic_increment_interaction')
TERMS = ({'new_RS': 1, 'old_RS': -1}, {'new_R': 1, 'old_R': -1},
         {'new_RS': 1, 'new_R': -1}, {'new_RS': 1, 'new_R': -1, 'old_RS': -1, 'old_R': 1})
OLD_PROTOCOL_SHA = 'f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1'
SEVEN_PROTOCOL_SHA = 'fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78'
STATUS = 'complete180_state_aligned_tracking_all360_results_and_paired_intervals'
BOOTSTRAP_SEED = 20261028
T95 = {2: 12.706204736432095, 3: 4.302652729749462, 7: 2.4469118511449692}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(value):
    path = Path(value)
    require(path.is_absolute(), '仅准绝对物理路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
        for part in path.parts), '仅DResearch；最终测试保持封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不跟随链接或junction')
    return path


def sha(path):
    return hashlib.sha256(physical(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def checked(reference):
    require(isinstance(reference, dict) and set(reference) >= {'path', 'sha256'}
        and re.fullmatch('[0-9a-f]{64}', reference['sha256']), '缺SHA来源引用')
    path = physical(reference['path'])
    require(path.suffix in ('.json', '.csv') and path.name not in ('gap_registry.json', 'posthoc_GT_labels.json'),
        '只读报告元数据；不读模型、MOT、缓存、训练池或GT坐标')
    require(path.is_file() and sha(path) == reference['sha256'], '分析来源SHA改变：'+str(path))
    return path


def read(reference):
    return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), '指标必须为有限实数')
    return value


def finite_metrics(values):
    require(isinstance(values, dict) and set(METRICS) <= set(values), '五项绝对指标不可缺失')
    return {key: finite(values[key]) for key in METRICS}


def panels_map(panels):
    require(set(panels) == set(PANELS) and [len(panels[k]) for k in PANELS] == [3, 2, 7], '固定原3/旧2/七场分别汇总')
    result = {sequence: panel for panel in PANELS for sequence in panels[panel]}
    require(len(result) == sum(map(len, panels.values())) == 12 and set(panels['original_heldout']) == set(OLD), '比赛面板重复或缺失')
    return result


def expected_cells(panels):
    return {(regime, sequence, fold, seed) for regime in ('R', 'RS') for sequence in panels_map(panels)
        for fold in ((OLD[sequence],) if sequence in OLD else FOLDS) for seed in SEEDS}


def cell_key(row):
    return tuple(row[key] for key in ('regime', 'sequence', 'fold', 'seed'))


def gap_values(overall):
    total, success, rate = (overall[key] for key in ('total_events', 'same_prediction_ID_recovered', 'recovery_rate'))
    require(type(total) is int and type(success) is int and 0 <= success <= total, '全事件gap分母或成功数无效')
    require((rate is None and success == 0) if total == 0 else
        (type(rate) in (int, float) and math.isfinite(rate) and abs(rate-success/total) <= 1e-12), '零事件必须null；成功率须保留完整事件分母')
    return total, success, rate


def indexed_records(rows, panels):
    result = {}
    for row in rows:
        key = cell_key(row)
        require(key not in result, '重复训练单元，不准重复填满矩阵')
        finite_metrics(row['metrics']); gap_values(row['gap'])
        result[key] = row
    require(len(rows) == 180 and set(result) == expected_cells(panels), '须齐全180个同比赛/fold/seed单元后分析')
    return result


def source_gap_denominators(rows, panels):
    result = {}
    for sequence in panels_map(panels):
        values = {gap_values(row['gap'])[0] for row in rows if row['sequence'] == sequence}
        require(len(values) == 1, '同源gap分母不能随模型/seed/fold改变')
        result[sequence] = values.pop()
    return result


def paired_cells(target, baseline, panels):
    new, old = indexed_records(target, panels), indexed_records(baseline, panels)
    for key in new:
        require(new[key]['baseline_model_id'] == old[key]['model_id'], '新模型必须显式匹配原参照身份')
    result = []
    for sequence, fold, seed in sorted((s, f, d) for r, s, f, d in new if r == 'R'):
        quartet = {condition: (new if condition.startswith('new_') else old)[condition.split('_')[1], sequence, fold, seed]
            for condition in CONDITIONS}
        gaps = {key: gap_values(row['gap']) for key, row in quartet.items()}
        require(len({v[0] for v in gaps.values()}) == 1, '四条件须用相同原事件分母')
        total = gaps['new_R'][0]
        for comparison, terms in zip(COMPARISONS, TERMS):
            result.append(dict(comparison=comparison, panel=panels_map(panels)[sequence], sequence=sequence, fold=fold, seed=seed,
                delta_pp={m: sum(coef*quartet[c]['metrics'][m] for c, coef in terms.items()) for m in METRICS},
                total_registered_events=total,
                delta_recovery_rate_pp=None if total == 0 else 100*sum(coef*gaps[c][2] for c, coef in terms.items()),
                source_gap_terms={c: dict(total_events=gaps[c][0], same_prediction_ID_recovered=gaps[c][1], recovery_rate=gaps[c][2]) for c in terms},
                source_terms={c: dict(coefficient=coef, model_id=quartet[c]['model_id'], report=quartet[c]['report']) for c, coef in terms.items()}))
    require(len(result) == 360, '四比较须360配对单元')
    return result


def paired_matches(cells, panels):
    result = []
    for comparison in COMPARISONS:
        for sequence, panel in panels_map(panels).items():
            rows = [r for r in cells if r['comparison'] == comparison and r['sequence'] == sequence]
            expected = {(f, s) for f in ((OLD[sequence],) if sequence in OLD else FOLDS) for s in SEEDS}
            require(len(rows) == len(expected) and {(r['fold'], r['seed']) for r in rows} == expected, '比赛内匹配单元不可丢失/重复')
            require(len({r['total_registered_events'] for r in rows}) == 1, '比赛事件分母不同')
            result.append(dict(comparison=comparison, panel=panel, sequence=sequence, matched_training_cells=len(rows),
                delta_pp={m: mean(r['delta_pp'][m] for r in rows) for m in METRICS},
                total_registered_events=rows[0]['total_registered_events'],
                delta_recovery_rate_pp=None if rows[0]['total_registered_events'] == 0 else mean(r['delta_recovery_rate_pp'] for r in rows)))
    return result


def absolute_results(target, baseline, panels):
    """绝对成绩先按每场均匹配训练单元，再按比赛等权，不从差值倒算。"""
    indexed_records(target, panels); indexed_records(baseline, panels)
    matches, summaries = [], []
    for condition in CONDITIONS:
        origin = target if condition.startswith('new_') else baseline
        for sequence, panel in panels_map(panels).items():
            rows = [r for r in origin if r['regime'] == condition.split('_')[1] and r['sequence'] == sequence]
            gaps = [gap_values(r['gap']) for r in rows]
            matches.append(dict(condition=condition, panel=panel, sequence=sequence, matched_training_cells=len(rows),
                metrics={m: mean(r['metrics'][m] for r in rows) for m in METRICS}, total_registered_events=gaps[0][0],
                gap_recovery_rate_pp=None if gaps[0][0] == 0 else 100*mean(g[2] for g in gaps)))
        for panel in PANELS:
            rows = [r for r in matches if r['condition'] == condition and r['panel'] == panel]
            values = [r['gap_recovery_rate_pp'] for r in rows if r['gap_recovery_rate_pp'] is not None]
            summaries.append(dict(condition=condition, panel=panel, independent_matches=len(rows),
                metrics={m: mean(r['metrics'][m] for r in rows) for m in METRICS},
                gap_recovery_rate_pp=mean(values) if values else None, gap_matches_with_events=len(values),
                null_gap_matches=[r['sequence'] for r in rows if r['gap_recovery_rate_pp'] is None]))
    return matches, summaries


def quantile(sorted_values, probability):
    position = (len(sorted_values)-1)*probability
    lower = int(position); fraction = position-lower
    return sorted_values[lower]*(1-fraction)+sorted_values[min(lower+1, len(sorted_values)-1)]*fraction


def effect_intervals(match_deltas):
    """固定10000次比赛bootstrap；Python MT19937及线性分位点显式登记。"""
    observed = {k: finite(v) for k, v in match_deltas.items() if v is not None}
    values = list(observed.values()); n = len(values)
    result = dict(n_independent_matches=n, match_deltas_pp=match_deltas, mean_delta_pp=mean(values) if values else None,
        null_matches=[k for k, v in match_deltas.items() if v is None], match_sample_SD_pp=None,
        Student_t_95CI=None, percentile_match_bootstrap_95CI=None, leave_one_match_out_mean=None,
        bootstrap_seed=BOOTSTRAP_SEED, bootstrap_resamples=10000,
        bootstrap_algorithm='Python_random_MT19937_randrange_match_resampling_linear_quantile',
        formal_equivalence_or_noninferiority_test=False, margin=None)
    # 缺事件源保留null，不改变已登记3/2/7的独立比赛分母来形成区间。
    if len(observed) != len(match_deltas) or n < 2:
        result['interval_status'] = 'null_missing_event_matches_or_fewer_than_two'; return result
    require(n in T95, '区间仅适用事前3/2/7比赛面板')
    avg = mean(values); sd = stdev(values); half = T95[n]*sd/math.sqrt(n)
    rng = random.Random(BOOTSTRAP_SEED)
    draws = sorted(mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(10000))
    result.update(match_sample_SD_pp=sd, Student_t_95CI=[avg-half, avg+half],
        percentile_match_bootstrap_95CI=[quantile(draws, .025), quantile(draws, .975)],
        leave_one_match_out_mean={k: mean(v for key, v in observed.items() if key != k) for k in observed},
        interval_status='descriptive_uncorrected', Student_t_degrees_of_freedom=n-1, Student_t_critical_975=T95[n])
    return result


def describe(matches, panels):
    metrics, gaps = {}, {}
    for comparison in COMPARISONS:
        metrics[comparison], gaps[comparison] = {}, {}
        for panel in PANELS:
            rows = {r['sequence']: r for r in matches if r['comparison'] == comparison and r['panel'] == panel}
            require(set(rows) == set(panels[panel]), '描述区间缺比赛')
            metrics[comparison][panel] = {m: effect_intervals({s: rows[s]['delta_pp'][m] for s in panels[panel]}) for m in METRICS}
            gaps[comparison][panel] = effect_intervals({s: rows[s]['delta_recovery_rate_pp'] for s in panels[panel]})
    return metrics, gaps


def validate_config(path):
    reference = ref(path); cfg = read(reference)
    require(cfg['schema'] == 'state_aligned_tracking_protocol_v1' and cfg['approved_by'] == 'root'
        and cfg['tracking_authorized'] is True and cfg['test_sealed'] is True and cfg['new_optimizer_updates'] == 0,
        '须独立冻结零新增SGD追踪协议')
    require(physical(cfg['output_root']) == EXP and 'calibrations' not in cfg and 'fit_complete' not in cfg, '新模型不得伪装截距身份')
    inventory, source = read(cfg['inventory']), read(cfg['source_inventory'])
    require(inventory['schema'] == 'state_aligned_strongmotion_tracking_inventory_v1'
        and source['schema'] == 'trainR_intercept_source_inventory_v1'
        and source['status'] == 'complete18_model_refs3_cleanR_pools180_baseline_refs_no_weight_or_pool_loaded', '新/原库存身份错误')
    require(cfg['sources'] == inventory['sources'] == source['sources'] and cfg['panels'] == inventory['panels'] == source['panels'], '源或面板发生变化')
    panels_map(cfg['panels'])
    models = {m['model_id']: m for m in inventory['models']}; old_models = {m['model_id']: m for m in source['models']}
    expected = {(r, f, s) for r in ('R', 'RS') for f in FOLDS for s in SEEDS}
    require(len(models) == len(inventory['models']) == len(old_models) == 18
        and {(m['regime'], m['fold'], m['seed']) for m in models.values()} == expected, '新十八模型矩阵缺失或重复')
    for m in models.values():
        old = old_models[m['baseline_model_id']]
        require(all(m[k] == old[k] for k in ('regime', 'fold', 'seed')) and m['learning_protocol'] == cfg['learning_protocol'], '新旧模型匹配/训练协议不同')
    jobs = cfg['jobs']
    require(len(jobs) == 180 and len({j['job_id'] for j in jobs}) == 180 and {cell_key(j) for j in jobs} == expected_cells(cfg['panels']), '新追踪矩阵不完整')
    for j in jobs:
        m = models[j['model_id']]
        require(all(j[k] == m[k] for k in ('regime', 'fold', 'seed', 'baseline_model_id')), '任务不是登记模型')
    training = read(cfg['training_complete']); budget = read(cfg['training_budget'])
    require(training['schema'] == 'state_aligned_training_complete_root_v1'
        and training['status'] == 'complete18_state_aligned_training_actual_budget_records_exit_verified_not_tracking_complete'
        and training['budget_audit'] == cfg['training_budget'] and training['protocol'] == cfg['learning_protocol']
        and training['actual_training_and_audit_processes_absent'] is True and training['test_read'] is False,
        '训练完成根必须绑定本轮实际预算/协议与真实退出')
    require(budget['schema'] == 'independent_state_aligned18_budget_audit_v1'
        and budget['status'] == 'complete18_state_aligned_R_actual_budget_full_records_and_exit_verified'
        and budget['protocol'] == cfg['learning_protocol'] and budget['training_processes_absent'] is True
        and budget['complete_checkpoints_read_back'] == 378 and budget['nine_paired_R_RS_exposures_equal'] is True
        and budget['test_read'] is False
        and all(budget['actual_totals'][key] == count for key, count in [('updates', 18000), ('R_windows', 54000), ('S_windows', 9000)]),
        '须真实十八训练完整预算与退出审计，不重审检查点')
    return reference, cfg, inventory, source, models, old_models, training


def baseline_records(source, models):
    rows = []
    for entry in source['baseline_units']:
        model = models[entry['model_id']]; sequence = entry['sequence']; body = read(entry['metric_report']); job = body['job']
        seven = sequence in source['panels']['seven_observed']
        require(body['status'] == 'complete' and body['schema'] == ('seven_match_ABC_trackeval_gap_v1' if seven else 'v10_independent_trackeval_gap_v1')
            and body['protocol_sha256'] == (SEVEN_PROTOCOL_SHA if seven else OLD_PROTOCOL_SHA)
            and all(body[k] is False for k in ('DO_PREPROC', 'predictions_GT_filtered', 'test_read'))
            and all(job[k] == entry[k] == model[k] for k in ('fold', 'seed')) and entry['regime'] == model['regime']
            and job['sequence'] == sequence and job['method'] == 'motion' and body['frames'] == source['sources'][sequence]['frames'], '原180参照真实来源或评价范围错误')
        require((job['kind'] == 'learned' and job['group'] == ('A' if entry['regime'] == 'R' else 'B')) if seven else
            (job['kind'] == ('pure_R' if entry['regime'] == 'R' else 'new_RS') and (entry['regime'] == 'R' or job['pool'] == 'balanced')), '原参照仅原纯R/平衡RS')
        checked(entry['tracking_receipt'])
        require(body['tracking_receipt_sha256'] == entry['tracking_receipt']['sha256'], '参照追踪收据SHA不同')
        rows.append(dict(**{k: entry[k] for k in ('model_id', 'regime', 'sequence', 'fold', 'seed')},
            condition='old_'+entry['regime'], metrics=finite_metrics(body['summary'][sequence]['metrics_percent']),
            gap=body['recovery']['overall'], report=entry['metric_report'], tracking_receipt=entry['tracking_receipt'], frames=body['frames'], source_origin='historical_readonly'))
    indexed_records(rows, source['panels'])
    require(len({r['report']['path'] for r in rows}) == 180, '原参照报告重复')
    require(sum(source_gap_denominators(rows, source['panels']).values()) == 3690, '原全源gap分母须3690')
    return rows


def target_records(cfg_ref, cfg, control, models, baseline):
    manifest_ref = ref(control/'manifest.json'); manifest = read(manifest_ref)
    require(manifest['schema'] == 'state_aligned_tracking_manifest_v1'
        and manifest['status'] == 'complete180_state_aligned_tracking_and_evaluation'
        and manifest['config_sha256'] == cfg_ref['sha256'] and len(manifest['reports']) == 180
        and [r['job'] for r in manifest['reports']] == cfg['jobs'], '正式180追踪/评价尚不完整')
    rows = []; old_paths = {r['report']['path'] for r in baseline}
    for entry in manifest['reports']:
        job, reference = entry['job'], entry['report']; model = models[job['model_id']]; body = read(reference)
        require(control in physical(reference['path']).parents and reference['path'] not in old_paths, '新评价须为独立实际追踪产物')
        require(body['schema'] == 'state_aligned_tracking_metric_v1' and body['status'] == 'complete'
            and body['job'] == job and body['protocol_sha256'] == cfg_ref['sha256'] and body['baseline_model_id'] == model['baseline_model_id']
            and body['learning_protocol'] == cfg['learning_protocol'] and body['training_budget'] == cfg['training_budget']
            and body['source_cache'] == cfg['sources'][job['sequence']]['cache']
            and body['frames'] == cfg['sources'][job['sequence']]['frames']
            and all(body[k] is False for k in ('DO_PREPROC', 'predictions_GT_filtered', 'test_read', 'intercept_applied'))
            and body['GT_used_only_for_metric'] is True and body['GT_ID0_original'] is True and body['new_optimizer_updates'] == 0,
            '新报告模型/缓存/零截距/GT评价边界不同')
        require(type(body['GT_rows']) is int and body['GT_rows'] == cfg['expected_GT_rows'][job['sequence']] > 0
            and type(body['tracked_rows']) is int and body['tracked_rows'] >= 0, 'GT/全输出分母不同')
        require(finite_metrics(body['metrics']) == finite_metrics(body['summary'][job['sequence']]['metrics_percent']), '五绝对指标须与实际汇总逐值相同')
        receipt = read(body['tracking_receipt'])
        require(receipt['schema'] == 'state_aligned_tracking_receipt_v1' and receipt['status'] == 'complete'
            and receipt['job'] == job and receipt['protocol_sha256'] == cfg_ref['sha256'] and receipt['model_id'] == job['model_id']
            and receipt['baseline_model_id'] == model['baseline_model_id'] and receipt['learning_protocol'] == cfg['learning_protocol']
            and receipt['training_budget'] == cfg['training_budget'] and receipt['source_cache'] == body['source_cache']
            and all(receipt[k] is False for k in ('test_read', 'GT_used_for_tracking', 'evaluation_GT_coordinate_files_opened', 'GPU_used', 'alias_used', 'intercept_applied'))
            and receipt['prefix_frames'] is None and receipt['new_optimizer_updates'] == 0
            and all(receipt[k] is True for k in ('source_inputs_unchanged', 'original_model_state_unchanged', 'original_normalizer_unchanged', 'native_ordered_batch_forward_preserved'))
            and receipt['frames'] == body['frames'] and receipt['tracked_rows'] == body['tracked_rows'], '实际追踪收据来源/数值/GT隔离不同')
        require(isinstance(receipt['frame_counts'], list) and len(receipt['frame_counts']) == body['frames']
            and all(type(n) is int and n >= 0 for n in receipt['frame_counts']) and sum(receipt['frame_counts']) == body['tracked_rows'], '全帧输出计数不符')
        rows.append(dict(**{k: job[k] for k in ('model_id', 'baseline_model_id', 'regime', 'sequence', 'fold', 'seed')},
            condition='new_'+job['regime'], metrics=finite_metrics(body['metrics']), gap=body['gap']['overall'], report=reference,
            tracking_receipt=body['tracking_receipt'], frames=body['frames'], source_origin='new_actual_tracking'))
    indexed_records(rows, cfg['panels'])
    require(len({r['report']['path'] for r in rows}) == 180, '新报告不能重复填矩阵')
    require(source_gap_denominators(rows, cfg['panels']) == source_gap_denominators(baseline, cfg['panels']), '新评价改变全事件分母')
    return rows, manifest_ref


def write_csv(path, fields, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def analyze(config, control, output):
    cfg_ref, cfg, inventory, source, models, old_models, training = validate_config(config)
    control, output = physical(control), physical(output)
    require(EXP in control.parents and EXP in output.parents and not output.exists(), '独立分析只准新路径，partial不覆盖')
    baseline = baseline_records(source, old_models)
    target, manifest = target_records(cfg_ref, cfg, control, models, baseline)
    cells = paired_cells(target, baseline, cfg['panels']); matches = paired_matches(cells, cfg['panels'])
    absolute_matches, absolute_panels = absolute_results(target, baseline, cfg['panels'])
    intervals, gap_intervals = describe(matches, cfg['panels'])
    output.mkdir(parents=True)
    fields = ['condition', 'model_id', 'baseline_model_id', 'regime', 'sequence', 'fold', 'seed', *METRICS,
        'gap_events', 'gap_success', 'gap_rate', 'frames', 'source_origin', 'report_path', 'report_sha256', 'tracking_receipt_path', 'tracking_receipt_sha256']
    raw = []
    for row in target+baseline:
        total, success, rate = gap_values(row['gap'])
        raw.append(dict(**{k: row[k] for k in ('condition', 'model_id', 'regime', 'sequence', 'fold', 'seed', 'frames', 'source_origin')},
            baseline_model_id=row.get('baseline_model_id'), **row['metrics'], gap_events=total, gap_success=success, gap_rate=rate,
            report_path=row['report']['path'], report_sha256=row['report']['sha256'],
            tracking_receipt_path=row['tracking_receipt']['path'], tracking_receipt_sha256=row['tracking_receipt']['sha256']))
    write_csv(output/'all_results.csv', fields, raw)
    pair_fields = ['comparison', 'panel', 'sequence', 'fold', 'seed']
    write_csv(output/'all_paired_cells.csv', pair_fields+[*METRICS, 'source_terms'],
        [dict(**{k: r[k] for k in pair_fields}, **r['delta_pp'], source_terms=canonical(r['source_terms'])) for r in cells])
    write_csv(output/'all_paired_gaps.csv', pair_fields+['total_registered_events', 'delta_recovery_rate_pp', 'source_gap_terms', 'source_terms'],
        [dict(**{k: r[k] for k in pair_fields+['total_registered_events', 'delta_recovery_rate_pp']},
            source_gap_terms=canonical(r['source_gap_terms']), source_terms=canonical(r['source_terms'])) for r in cells])
    write_csv(output/'all_paired_matches.csv', ['comparison', 'panel', 'sequence', 'matched_training_cells', *METRICS, 'total_registered_events', 'delta_recovery_rate_pp'],
        [dict(**{k: r[k] for k in ('comparison', 'panel', 'sequence', 'matched_training_cells', 'total_registered_events', 'delta_recovery_rate_pp')}, **r['delta_pp']) for r in matches])
    for filename, rows, extra in [('absolute_matches.csv', absolute_matches, ['sequence', 'matched_training_cells', 'total_registered_events']),
                                  ('absolute_panels.csv', absolute_panels, ['independent_matches', 'gap_matches_with_events', 'null_gap_matches'])]:
        write_csv(output/filename, ['condition', 'panel', *extra, *METRICS, 'gap_recovery_rate_pp'],
            [dict(**{k: canonical(r[k]) if isinstance(r[k], list) else r[k] for k in ['condition', 'panel', *extra, 'gap_recovery_rate_pp']}, **r['metrics']) for r in rows])
    report = dict(schema='state_aligned_tracking_paired_analysis_v1', status=STATUS, protocol=cfg_ref,
        inventory=cfg['inventory'], source_inventory=cfg['source_inventory'], training_complete=cfg['training_complete'], training_budget=cfg['training_budget'],
        formal_evaluation_manifest=manifest, panels=cfg['panels'], absolute_matches=absolute_matches, absolute_panels=absolute_panels,
        comparisons=intervals, gap_comparisons=gap_intervals, primary_comparison=COMPARISONS[0], primary_metric='AssA',
        new_tracking_evaluations=180, historical_reference_evaluations=180, all_results=360, paired_cells=360, paired_gap_cells=360,
        paired_matches=48, metric_interval_descriptions=60, gap_interval_descriptions=12,
        source_gap_event_denominators=source_gap_denominators(baseline, cfg['panels']), gap_events_counted_once_per_source=3690,
        all_actual_reports=[r['report'] for r in target], all_reference_reports=[r['report'] for r in baseline],
        all_folds_seeds_negative_zero_and_null_results_retained=True, formal_equivalence_or_noninferiority=False, performance_margin=None,
        bootstrap_seed=BOOTSTRAP_SEED, bootstrap_resamples=10000, analysis_optimizer_updates=0, test_read=False,
        limitations=['三面板均已观察开发，原3/旧2/七场分列；不作为盲测、泛化或学界排名。',
            '先均同比赛内匹配fold/seed，再比赛等权；训练单元不是独立比赛。',
            '60指标及12gap描述区间未经多比较校正；跨零不能证明等效。',
            'R窗口内容改变，不称原R曝光、pair、标签或FLOPs相同；不推出Pose或合成数据的独立因果作用。',
            'gap沿用全3690注册事件，仅是可信检测断档代理，不是物理遮挡；无事件保留null。'])
    for filename in ('all_results.csv', 'all_paired_cells.csv', 'all_paired_gaps.csv', 'all_paired_matches.csv', 'absolute_matches.csv', 'absolute_panels.csv'):
        report[filename.replace('.csv', '_csv')] = ref(output/filename)
    with (output/'report.json').open('x', encoding='utf-8') as stream: stream.write(canonical(report)+'\n')
    return dict(status=STATUS, new_tracking_evaluations=180, historical_reference_evaluations=180, paired_cells=360,
        paired_matches=48, metric_interval_descriptions=60, gap_interval_descriptions=12)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); print(canonical(analyze(args.config, args.control, args.output)))
