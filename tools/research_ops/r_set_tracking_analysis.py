"""R集合CE损失单因素的六条件绝对成绩及五族配对描述；不重评分。"""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean, stdev
import hashlib, math, os, random, re, stat
import sys

# 公式逐值复用已验统计约定；独立冻结，不导入旧活动framework或分析入口。
R = Path('D:/projects/FutsalMOT_Research')
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
PANELS = ('original_heldout', 'old_external', 'seven_observed')
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
BOOTSTRAP_SEED = 20261028
T95 = {2: 12.706204736432095, 3: 4.302652729749462, 7: 2.4469118511449692}
OLD_PROTOCOL_SHA = 'f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1'
SEVEN_PROTOCOL_SHA = 'fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78'
ALIGNED_STATUS = 'complete180_state_aligned_tracking_all360_results_and_paired_intervals'
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

def quantile(sorted_values, probability):
    position = (len(sorted_values)-1)*probability
    lower = int(position); fraction = position-lower
    return sorted_values[lower]*(1-fraction)+sorted_values[min(lower+1, len(sorted_values)-1)]*fraction

def write_csv(path, fields, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

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

CONDITIONS = ('newCE_R', 'newCE_RS', 'alignedBCE_R', 'alignedBCE_RS', 'originalstrongmotion_R', 'originalstrongmotion_RS')
COMPARISONS = ('newCE_RS_minus_alignedBCE_RS', 'newCE_R_minus_alignedBCE_R',
    'newCE_RS_minus_originalstrongmotion_RS', 'newCE_R_minus_originalstrongmotion_R', 'synthetic_increment_loss_interaction')
TERMS = ({'newCE_RS': 1, 'alignedBCE_RS': -1}, {'newCE_R': 1, 'alignedBCE_R': -1},
    {'newCE_RS': 1, 'originalstrongmotion_RS': -1}, {'newCE_R': 1, 'originalstrongmotion_R': -1},
    {'newCE_RS': 1, 'newCE_R': -1, 'alignedBCE_RS': -1, 'alignedBCE_R': 1})
STATUS = 'complete180_R_set_tracking_all540_results450_pairs75_metric15_gap_intervals'


def normalize(rows, panels, origin):
    indexed_records(rows, panels)
    result = []; model_units = {}; unit_models = {}
    for raw in rows:
        report = raw['report']
        require(isinstance(report, dict) and set(report) >= {'path', 'sha256'} and isinstance(report['path'], str)
            and re.fullmatch('[0-9a-f]{64}', report['sha256']), '绝对来源必须保留报告引用')
        unit = tuple(raw[k] for k in ('regime', 'fold', 'seed')); mid = raw['model_id']
        require(unit not in unit_models or unit_models[unit] == mid, '同训练单元在不同比赛换了模型')
        require(mid not in model_units or model_units[mid] == unit, '不同训练单元共用模型身份')
        unit_models[unit] = mid; model_units[mid] = unit
        row = dict(raw); row['condition'] = origin+'_'+raw['regime']; row['metrics'] = finite_metrics(raw['metrics'])
        row['gap'] = dict(raw['gap']); result.append(row)
    require(len(model_units) == 18 and len({r['report']['path'] for r in result}) == 180, '十八模型/180独立报告不能重复填矩阵')
    return result


def pair_records(new_ce, aligned_bce, original, panels):
    by_condition = {}
    for origin, rows in [('newCE', new_ce), ('alignedBCE', aligned_bce), ('originalstrongmotion', original)]:
        index = indexed_records(rows, panels)
        for regime in ('R', 'RS'): by_condition[origin+'_'+regime] = {(s, f, d): row for (r, s, f, d), row in index.items() if r == regime}
    new_index, aligned_index, original_index = [indexed_records(rows, panels) for rows in (new_ce, aligned_bce, original)]
    for key in new_index:
        new, aligned, old = new_index[key], aligned_index[key], original_index[key]
        require(new['baseline_model_id'] == aligned['model_id'] and new['original_baseline_model_id'] == old['model_id']
            and aligned['baseline_model_id'] == old['model_id'], '新CE→对齐BCE→原strongmotion模型身份须显式匹配')
    panels_by_source = panels_map(panels); output = []
    for key in sorted(by_condition['newCE_R']):
        sequence, fold, seed = key; six = {c: by_condition[c][key] for c in CONDITIONS}
        gaps = {c: gap_values(row['gap']) for c, row in six.items()}
        require(len({g[0] for g in gaps.values()}) == 1, '六条件必须同原全事件分母')
        total = gaps['newCE_R'][0]
        for family, terms in zip(COMPARISONS, TERMS):
            output.append(dict(comparison=family, panel=panels_by_source[sequence], sequence=sequence, fold=fold, seed=seed,
                delta_pp={m: sum(coef*six[c]['metrics'][m] for c, coef in terms.items()) for m in METRICS},
                total_registered_events=total, delta_recovery_rate_pp=None if total == 0 else 100*sum(coef*gaps[c][2] for c, coef in terms.items()),
                source_terms={c: dict(coefficient=coef, model_id=six[c]['model_id'], report=six[c]['report']) for c, coef in terms.items()},
                source_gap_terms={c: dict(total_events=gaps[c][0], same_prediction_ID_recovered=gaps[c][1], recovery_rate=gaps[c][2]) for c in terms}))
    require(len(output) == 450, '五比较须450完整单元')
    return output


def match_records(cells, panels):
    output = []
    for family in COMPARISONS:
        for sequence, panel in panels_map(panels).items():
            rows = [r for r in cells if r['comparison'] == family and r['sequence'] == sequence]
            expected = {(fold, seed) for fold in ((OLD[sequence],) if sequence in OLD else FOLDS) for seed in SEEDS}
            require(len(rows) == len(expected) and {(r['fold'], r['seed']) for r in rows} == expected, '比赛内匹配fold/seed缺失/重复')
            require(len({r['total_registered_events'] for r in rows}) == 1, '比赛内分母变化')
            output.append(dict(comparison=family, sequence=sequence, panel=panel, matched_training_cells=len(rows),
                delta_pp={m: mean(r['delta_pp'][m] for r in rows) for m in METRICS}, total_registered_events=rows[0]['total_registered_events'],
                delta_recovery_rate_pp=None if rows[0]['total_registered_events'] == 0 else mean(r['delta_recovery_rate_pp'] for r in rows)))
    return output


def absolute_results(rows, panels):
    matches, summaries = [], []
    for condition in CONDITIONS:
        for sequence, panel in panels_map(panels).items():
            group = [r for r in rows if r['condition'] == condition and r['sequence'] == sequence]
            gaps = [gap_values(r['gap']) for r in group]
            matches.append(dict(condition=condition, sequence=sequence, panel=panel, matched_training_cells=len(group),
                metrics={m: mean(r['metrics'][m] for r in group) for m in METRICS}, total_registered_events=gaps[0][0],
                gap_recovery_rate_pp=None if gaps[0][0] == 0 else 100*mean(g[2] for g in gaps)))
        for panel in PANELS:
            group = [r for r in matches if r['condition'] == condition and r['panel'] == panel]
            rates = [r['gap_recovery_rate_pp'] for r in group if r['gap_recovery_rate_pp'] is not None]
            summaries.append(dict(condition=condition, panel=panel, independent_matches=len(group),
                metrics={m: mean(r['metrics'][m] for r in group) for m in METRICS}, gap_recovery_rate_pp=mean(rates) if rates else None,
                gap_matches_with_events=len(rates), null_gap_matches=[r['sequence'] for r in group if r['gap_recovery_rate_pp'] is None]))
    return matches, summaries


def analyze_records(new_ce, aligned_bce, original_strongmotion, panels):
    """输入三套正规化180记录；不打开引用文件，不执行GT、模型或TrackEval。"""
    new = normalize(new_ce, panels, 'newCE'); aligned = normalize(aligned_bce, panels, 'alignedBCE'); original = normalize(original_strongmotion, panels, 'originalstrongmotion')
    all_rows = new+aligned+original
    require(len({r['report']['path'] for r in all_rows}) == 540, '新模型及两套参照不能共用报告路径冒充独立来源')
    denominators = [source_gap_denominators(rows, panels) for rows in (new, aligned, original)]
    require(denominators[0] == denominators[1] == denominators[2] and sum(denominators[0].values()) == 3690, '原3690全事件分母须六条件一致')
    cells = pair_records(new, aligned, original, panels); matches = match_records(cells, panels)
    absolute_matches, absolute_panels = absolute_results(all_rows, panels)
    metrics, gaps = {}, {}
    for family in COMPARISONS:
        metrics[family], gaps[family] = {}, {}
        for panel in PANELS:
            group = {r['sequence']: r for r in matches if r['comparison'] == family and r['panel'] == panel}
            require(set(group) == set(panels[panel]), '区间比赛缺失')
            metrics[family][panel] = {m: effect_intervals({s: group[s]['delta_pp'][m] for s in panels[panel]}) for m in METRICS}
            gaps[family][panel] = effect_intervals({s: group[s]['delta_recovery_rate_pp'] for s in panels[panel]})
    return dict(schema='R_set_tracking_paired_analysis_v1', status=STATUS, panels=panels, primary_comparison=COMPARISONS[0], primary_metric='AssA',
        new_tracking_evaluations=180, aligned_reference_evaluations=180, original_reference_evaluations=180, historical_reference_evaluations=360,
        all_results=540, paired_cells=450, paired_gap_cells=450, paired_matches=60, absolute_match_count=72, absolute_panel_count=18,
        metric_interval_descriptions=75, gap_interval_descriptions=15, records=all_rows, paired_cell_records=cells, paired_match_records=matches,
        absolute_matches=absolute_matches, absolute_panels=absolute_panels, comparisons=metrics, gap_comparisons=gaps,
        source_gap_event_denominators=denominators[0], gap_events_counted_once_per_source=3690, bootstrap_seed=20261028, bootstrap_resamples=10000,
        all_folds_seeds_negative_zero_and_null_results_retained=True, formal_equivalence_or_noninferiority=False, performance_margin=None,
        analysis_optimizer_updates=0, new_model_forwards=0, new_tracking=0, new_solver_calls=0, new_TrackEval=0, test_read=False,
        limitations=['三面板为原3/旧2/七场已观察开发范围，分别报告，不称盲测、泛化或SOTA。',
            '先同比赛匹配fold/seed均值，再比赛等权；75指标及15gap区间未经多比较校正。',
            'unknown从known集合CE排除，固定null仅表示无已知匹配，不等于真实无人可匹配。',
            '只归因于本轮完整R损失政策，既有窗口/标签/anchor资格不变；不拆分为某标签子类因果效果。',
            '原3690可信检测断档非物理遮挡；无事件保留null，CI跨零不证明相同。'])


def write_analysis(analysis, output, *, protocol=None, sources=None):
    """写出已算完整结果；输入引用的实物来源守卫由标准analyze封装负责。"""
    output = physical(output); require(R/'pose' in output.parents and not output.exists(), '仅研究pose新输出；partial/成功不覆盖')
    require(analysis['status'] == STATUS and len(analysis['records']) == 540 and len(analysis['paired_cell_records']) == 450
        and len(analysis['paired_match_records']) == 60 and len(analysis['absolute_matches']) == 72 and len(analysis['absolute_panels']) == 18, '完整分析矩阵尚未齐全')
    output.mkdir(parents=True); rows = analysis['records']; cells = analysis['paired_cell_records']; matches = analysis['paired_match_records']
    fields = ['condition', 'model_id', 'baseline_model_id', 'original_baseline_model_id', 'regime', 'sequence', 'fold', 'seed', *METRICS,
        'gap_events', 'gap_success', 'gap_rate', 'frames', 'report_path', 'report_sha256', 'tracking_receipt_path', 'tracking_receipt_sha256']
    raw = []
    for row in rows:
        total, success, rate = gap_values(row['gap']); receipt = row.get('tracking_receipt', {})
        raw.append(dict(**{k: row.get(k) for k in fields[:8]+['frames']}, **row['metrics'], gap_events=total, gap_success=success, gap_rate=rate,
            report_path=row['report']['path'], report_sha256=row['report']['sha256'], tracking_receipt_path=receipt.get('path'), tracking_receipt_sha256=receipt.get('sha256')))
    write_csv(output/'all_results.csv', fields, raw)
    pair_fields = ['comparison', 'panel', 'sequence', 'fold', 'seed']
    write_csv(output/'all_paired_cells.csv', pair_fields+[*METRICS, 'source_terms'],
        [dict(**{k: r[k] for k in pair_fields}, **r['delta_pp'], source_terms=canonical(r['source_terms'])) for r in cells])
    write_csv(output/'all_paired_gaps.csv', pair_fields+['total_registered_events', 'delta_recovery_rate_pp', 'source_gap_terms', 'source_terms'],
        [dict(**{k: r[k] for k in pair_fields+['total_registered_events', 'delta_recovery_rate_pp']}, source_gap_terms=canonical(r['source_gap_terms']), source_terms=canonical(r['source_terms'])) for r in cells])
    write_csv(output/'all_paired_matches.csv', ['comparison', 'panel', 'sequence', 'matched_training_cells', *METRICS, 'total_registered_events', 'delta_recovery_rate_pp'],
        [dict(**{k: r[k] for k in ('comparison', 'panel', 'sequence', 'matched_training_cells', 'total_registered_events', 'delta_recovery_rate_pp')}, **r['delta_pp']) for r in matches])
    for filename, group, extra in [('absolute_matches.csv', analysis['absolute_matches'], ['sequence', 'matched_training_cells', 'total_registered_events']),
                                  ('absolute_panels.csv', analysis['absolute_panels'], ['independent_matches', 'gap_matches_with_events', 'null_gap_matches'])]:
        write_csv(output/filename, ['condition', 'panel', *extra, *METRICS, 'gap_recovery_rate_pp'],
            [dict(**{k: canonical(r[k]) if isinstance(r[k], list) else r[k] for k in ['condition', 'panel', *extra, 'gap_recovery_rate_pp']}, **r['metrics']) for r in group])
    report = {k: v for k, v in analysis.items() if k not in ('records', 'paired_cell_records', 'paired_match_records')}
    report.update(protocol=protocol, sources=sources, all_actual_reports=[r['report'] for r in rows[:180]],
        all_aligned_reference_reports=[r['report'] for r in rows[180:360]], all_original_reference_reports=[r['report'] for r in rows[360:]])
    for name in ('all_results.csv', 'all_paired_cells.csv', 'all_paired_gaps.csv', 'all_paired_matches.csv', 'absolute_matches.csv', 'absolute_panels.csv'):
        report[name.replace('.csv', '_csv')] = ref(output/name)
    with (output/'report.json').open('x', encoding='utf-8') as stream: stream.write(canonical(report)+'\n')
    return {k: report[k] for k in ('status', 'new_tracking_evaluations', 'historical_reference_evaluations', 'all_results', 'paired_cells', 'paired_matches', 'metric_interval_descriptions', 'gap_interval_descriptions')}


def same_ref(left, right):
    return left['sha256'] == right['sha256'] and checked(left) == checked(right)


def load_metric_records(references, models, cfg, protocol, *, aligned=False, control=None):
    result = []; model_index = {m['model_id']: m for m in models}
    for reference in references:
        body = read(reference); job = body['job']; model = model_index[job['model_id']]; sequence = job['sequence']
        require(body['schema'] == ('state_aligned_tracking_metric_v1' if aligned else 'r_set_tracking_metric_v1') and body['status'] == 'complete'
            and body['protocol_sha256'] == protocol['sha256'] and body['baseline_model_id'] == model['baseline_model_id']
            and all(job[k] == model[k] for k in ('regime', 'fold', 'seed')) and body['source_cache'] == cfg['sources'][sequence]['cache']
            and body['frames'] == cfg['sources'][sequence]['frames'] and body['GT_rows'] == cfg['expected_GT_rows'][sequence]
            and all(body[k] is False for k in ('DO_PREPROC', 'predictions_GT_filtered', 'test_read', 'intercept_applied'))
            and body['GT_used_only_for_metric'] is True and body['GT_ID0_original'] is True and body['new_optimizer_updates'] == 0, '实际评价来源/范围/GT边界不同')
        require(same_ref(body['learning_protocol'], cfg['aligned_learning_protocol'] if aligned else cfg['learning_protocol']), '新/旧实际学习协议绑定不同')
        if not aligned:
            require(body['original_baseline_model_id'] == model['original_baseline_model_id'] and body['training_budget'] == cfg['training_budget'], '新双参照身份/预算不同')
            require(control in physical(reference['path']).parents, '本轮新评价须实际独立control产物')
        require(finite_metrics(body['metrics']) == finite_metrics(body['summary'][sequence]['metrics_percent']), '报告五绝对成绩不同于原TrackEval汇总')
        receipt = read(body['tracking_receipt'])
        require(receipt['schema'] == ('state_aligned_tracking_receipt_v1' if aligned else 'r_set_tracking_receipt_v1')
            and receipt['status'] == 'complete' and receipt['job'] == job and receipt['protocol_sha256'] == protocol['sha256']
            and receipt['model_id'] == model['model_id'] and receipt['baseline_model_id'] == model['baseline_model_id']
            and receipt['frames'] == body['frames'] and receipt['tracked_rows'] == body['tracked_rows']
            and receipt['source_cache'] == body['source_cache'] and receipt['prefix_frames'] is None and receipt['new_optimizer_updates'] == 0
            and all(receipt[k] is False for k in ('test_read', 'GT_used_for_tracking', 'evaluation_GT_coordinate_files_opened', 'GPU_used', 'alias_used', 'intercept_applied'))
            and all(receipt[k] is True for k in ('source_inputs_unchanged', 'original_model_state_unchanged', 'original_normalizer_unchanged', 'native_ordered_batch_forward_preserved')),
            '实际追踪收据模型/全帧/GT隔离不同')
        require(same_ref(receipt['learning_protocol'], body['learning_protocol']) and receipt['training_budget'] == body['training_budget'], 'metric与track训练来源不同')
        require(len(receipt['frame_counts']) == receipt['frames'] and all(type(n) is int and n >= 0 for n in receipt['frame_counts'])
            and sum(receipt['frame_counts']) == body['tracked_rows'], '原全帧输出计数不同')
        if not aligned: require(receipt['original_baseline_model_id'] == model['original_baseline_model_id'], '新追踪原参照身份不同')
        result.append(dict(**{k: job[k] for k in ('model_id', 'regime', 'sequence', 'fold', 'seed')}, baseline_model_id=model['baseline_model_id'],
            **({} if aligned else dict(original_baseline_model_id=model['original_baseline_model_id'])),
            metrics=finite_metrics(body['metrics']), gap=body['gap']['overall'], report=reference, tracking_receipt=body['tracking_receipt'], frames=body['frames']))
    indexed_records(result, cfg['panels']); return result


def analyze(config_path, control_root, output):
    """标准冻结控制器入口；只读新旧收据及历史原始评价，不打开其MOT/GT。"""
    protocol = ref(config_path); cfg = read(protocol); control = physical(control_root)
    require(cfg['schema'] == 'r_set_tracking_protocol_v1' and cfg['approved_by'] == 'root' and cfg['tracking_authorized'] is True
        and cfg['test_sealed'] is True and cfg['new_optimizer_updates'] == 0, '仅完整冻结新CE追踪分析')
    experiment = physical(cfg['output_root'])
    require(experiment in control.parents and experiment in physical(output).parents, '实际control及分析须属于本轮独立实验')
    inventory, aligned_inventory, source = read(cfg['inventory']), read(cfg['aligned_inventory']), read(cfg['source_inventory'])
    require(inventory['schema'] == 'R_candidate_set_supervision_tracking_inventory_v1'
        and aligned_inventory['schema'] == 'state_aligned_strongmotion_tracking_inventory_v1'
        and source['schema'] == 'trainR_intercept_source_inventory_v1'
        and all(inv['sources'] == cfg['sources'] and inv['panels'] == cfg['panels'] for inv in (inventory, aligned_inventory, source)), '三模型库存或固定源范围不同')
    read(cfg['learning_protocol']); budget, complete = read(cfg['training_budget']), read(cfg['training_complete'])
    require(budget['schema'] == 'independent_R_set_supervision18_budget_audit_v1'
        and budget['status'] == 'complete18_R_set_supervision_actual_budget_full_records_and_exit_verified'
        and same_ref(budget['protocol'], cfg['learning_protocol']) and budget['training_processes_absent'] is True
        and budget['complete_checkpoints_read_back'] == 378 and budget['nine_paired_R_RS_exposures_equal'] is True
        and budget['test_read'] is False and all(budget['actual_totals'][k] == v for k, v in [('updates', 18000), ('R_windows', 54000), ('S_windows', 9000)]),
        '新18臂实际完整预算/记录/退出尚未闭合')
    require(complete['schema'] == 'R_set_supervision_training_complete_root_v1'
        and complete['status'] == 'complete18_R_set_supervision_training_actual_budget_records_exit_verified_not_tracking_complete'
        and same_ref(complete['protocol'], cfg['learning_protocol']) and same_ref(complete['budget_audit'], cfg['training_budget'])
        and complete['actual_training_and_audit_processes_absent'] is True and complete['test_read'] is False, '实际训练完成根来源不同')
    aligned_analysis = read(cfg['aligned_analysis'])
    require(aligned_analysis['status'] == ALIGNED_STATUS and same_ref(aligned_analysis['inventory'], cfg['aligned_inventory'])
        and same_ref(aligned_analysis['protocol'], cfg['aligned_tracking_protocol']) and aligned_analysis['panels'] == cfg['panels'], '上轮完整180参照分析来源不同')
    manifest_ref = ref(control/'manifest.json'); manifest = read(manifest_ref)
    require(manifest['schema'] == 'r_set_tracking_manifest_v1' and manifest['status'] == 'complete180_R_set_tracking_and_evaluation'
        and manifest['config_sha256'] == protocol['sha256'] and len(manifest['reports']) == 180
        and [r['job'] for r in manifest['reports']] == cfg['jobs'], '本轮实际完整180矩阵尚未完成')
    original = baseline_records(source, {m['model_id']: m for m in source['models']})
    aligned = load_metric_records(aligned_analysis['all_actual_reports'], aligned_inventory['models'], cfg, cfg['aligned_tracking_protocol'], aligned=True)
    new = load_metric_records([r['report'] for r in manifest['reports']], inventory['models'], cfg, protocol, control=control)
    require([read(r['report'])['job'] for r in manifest['reports']] == cfg['jobs'], '新metric实际job与manifest不同')
    plan = read(cfg['analysis_plan'])
    require(plan['bootstrap']['seed'] == 20261028 and plan['bootstrap']['repeats'] == 10000
        and plan['metric_interval_count'] == 75 and plan['comparison_families'] == 5, '结果前统计计划不同')
    analysis = analyze_records(new, aligned, original, cfg['panels'])
    return write_analysis(analysis, output, protocol=protocol, sources=dict(inventory=cfg['inventory'], aligned_inventory=cfg['aligned_inventory'],
        source_inventory=cfg['source_inventory'], aligned_analysis=cfg['aligned_analysis'], formal_evaluation_manifest=manifest_ref, analysis_plan=cfg['analysis_plan'],
        aligned_learning_protocol=cfg['aligned_learning_protocol'], aligned_tracking_protocol=cfg['aligned_tracking_protocol'],
        learning_protocol=cfg['learning_protocol'], training_budget=cfg['training_budget'], training_complete=cfg['training_complete']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'): parser.add_argument('--'+key, required=True)
    args = parser.parse_args(); print(canonical(analyze(args.config, args.control, args.output)))
