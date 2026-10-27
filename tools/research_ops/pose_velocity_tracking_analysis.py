"""450个新表示追踪及63个补充参考的完整配对描述；不设性能通过或等效门槛。"""
import argparse
from collections import defaultdict
import csv
import importlib
import math
from pathlib import Path
from statistics import mean
import sys

sys.path.insert(0, str(Path(__file__).parent))
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
GROUPS = ('T_R', 'T_RS', 'T_shuffle_RS')
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
BASELINES = ('original_gated_RS', 'strong_motion_RS', 'same_capacity_motion_RS')
PANELS = ('original_heldout', 'old_external', 'seven_observed')
STATUS = 'complete513_all_results450_new63_reference_paired_intervals'
NEW_CONTRASTS = (
    ('T_RS_minus_T_R', ('T_RS', True), ('T_R', True)),
    ('T_RS_minus_T_shuffle_RS', ('T_RS', True), ('T_shuffle_RS', True)),
    ('T_RS_on_minus_off', ('T_RS', True), ('T_RS', False)),
    ('T_shuffle_RS_on_minus_off', ('T_shuffle_RS', True), ('T_shuffle_RS', False)),
    ('T_RS_off_minus_T_shuffle_RS_off', ('T_RS', False), ('T_shuffle_RS', False)),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite_metrics(metrics):
    require(set(METRICS) <= set(metrics)
            and all(type(metrics[k]) in (float, int) and math.isfinite(metrics[k]) for k in METRICS),
            '全部五指标必须实际有限，不能跳过负结果')
    return {k: metrics[k] for k in METRICS}


def validate_panels(panels):
    require(set(panels) == set(PANELS)
            and [len(panels[k]) for k in PANELS] == [3, 2, 7], '固定三个比赛面板3/2/7不可混并')
    flat = [s for key in PANELS for s in panels[key]]
    require(len(flat) == len(set(flat)) == 12, '面板之间比赛重复或缺失')
    return {seq: panel for panel in PANELS for seq in panels[panel]}


def gap_pair(target, reference):
    """全注册事件作同一分母；无事件只能null，不能填零假造恢复表现。"""
    result = {}
    for label, record in (('target', target), ('reference', reference)):
        gap = record['recovery']; total = gap['total_events']; success = gap['same_prediction_ID_recovered']
        rate = gap['recovery_rate']
        require(type(total) is int and type(success) is int and 0 <= success <= total,
                '可信gap原事件分母或成功计数不完整')
        require((rate is None and success == 0) if total == 0 else
                (type(rate) in (float, int) and math.isfinite(rate)
                 and abs(rate-success/total) <= 1e-12), 'gap率不等于原全事件分母，零事件不能填零')
        result.update({label+'_event_denominator': total, label+'_success': success,
                       label+'_recovery_rate': rate})
    require(result['target_event_denominator'] == result['reference_event_denominator'],
            '同场配对不能筛选不同gap事件分母')
    result['delta_recovery_rate_pp'] = (100*(result['target_recovery_rate']-result['reference_recovery_rate'])
        if result['target_event_denominator'] else None)
    result['target_report_path'] = target['report']['path']
    result['target_report_sha256'] = target['report']['sha256']
    result['reference_report_path'] = reference['report']['path']
    result['reference_report_sha256'] = reference['report']['sha256']
    return result


def paired_cells(records, baseline_records, expected, panels):
    """所有同fold/seed/比赛配对都保留；历史参考必须实际来源齐全。"""
    panel_by_match = validate_panels(panels)
    require(len(expected) == 513 and len({j['job_id'] for j in expected}) == 513,
            '正式矩阵应为450新T加63参考，不混成450全部完成')
    indexed = {}
    for record in records:
        job = record['job']; key = job['job_id']
        require(key not in indexed, '重复实际追踪单元')
        finite_metrics(record['metrics']); indexed[key] = record
    require(set(indexed) == {j['job_id'] for j in expected}
            and all(indexed[j['job_id']]['job'] == j for j in expected), '513实际任务缺项/多项/身份不符')
    new = {}; added_references = []
    for job in expected:
        record = indexed[job['job_id']]
        if job['kind'] == 'new':
            require(job['group'] in GROUPS and type(job['pose_enabled']) is bool
                    and (job['group'] != 'T_R' or job['pose_enabled']), '未登记新T训练/推理条件')
            key = (job['group'], job['pose_enabled'], job['fold'], job['seed'], job['sequence'])
            require(key not in new, '新T配对身份重复'); new[key] = record
        else:
            require(job['kind'] == 'reference' and job['group'] == 'same_capacity_motion_RS'
                    and job['pose_enabled'] is False and job['sequence'] in panels['seven_observed'],
                    '新参考任务不是事前缺失的63个同容量motion七场')
            added_references.append(dict(record, group='same_capacity_motion_RS'))
    require(len(new) == 450 and len(added_references) == 63, '新T450/新增参考63数量不符')
    target = {(f, s, seq): record for (g, on, f, s, seq), record in new.items() if g == 'T_RS' and on}
    require(len(target) == 90 and {k[2] for k in target} == set(panel_by_match), '九训练单元各10比赛来源不齐')
    for seq, panel in panel_by_match.items():
        cells = {(f, s) for f, s, m in target if m == seq}
        require({s for _, s in cells} == set(SEEDS)
                and ((len(cells) == 3 and len({f for f, _ in cells}) == 1) if panel == 'original_heldout'
                     else cells == {(f, s) for f in FOLDS for s in SEEDS}),
                '留出比赛只能相应fold，外部比赛须全部九个训练单元')
    refs = {}
    for record in list(baseline_records)+added_references:
        job = record['job']; baseline = record['group']; finite_metrics(record['metrics'])
        require(baseline in BASELINES, '未知历史参照，不能替代强motion')
        key = (baseline, job['fold'], job['seed'], job['sequence'])
        require(key not in refs, '历史与新参考重复计算'); refs[key] = record
    require(set(refs) == {(baseline, f, s, seq) for baseline in BASELINES for f, s, seq in target},
            '三类90单元参照不齐，不得静默省去强motion或同容量比较')
    comparisons = {}
    def pair(name, targets, references):
        rows = []
        for fold, seed, seq in sorted(target):
            t = targets(fold, seed, seq); r = references(fold, seed, seq)
            rows.append(dict(fold=fold, seed=seed, match=seq, panel=panel_by_match[seq],
                target=t['job']['job_id'], reference=r['job']['job_id'],
                delta_pp={k: t['metrics'][k]-r['metrics'][k] for k in METRICS}, gap=gap_pair(t, r)))
        comparisons[name] = rows
    for name, (tg, ton), (rg, ron) in NEW_CONTRASTS:
        pair(name, lambda f, s, m, g=tg, on=ton: new[g, on, f, s, m],
             lambda f, s, m, g=rg, on=ron: new[g, on, f, s, m])
    for baseline in BASELINES:
        pair('T_RS_on_minus_'+baseline, lambda f, s, m: target[f, s, m],
             lambda f, s, m, g=baseline: refs[g, f, s, m])
    require(len(comparisons) == 8 and sum(len(v) for v in comparisons.values()) == 720,
            '全部八比较族/720配对单元不足')
    return comparisons, list(refs.values())


def intervals(cells, panels, interval_fn=None):
    validate_panels(panels)
    require(len(cells) == len({(p['fold'], p['seed'], p['match']) for p in cells}) == 90,
            '配对单元重复或缺失')
    if interval_fn is None:
        from substitution_paired_analysis import effect_intervals
        interval_fn = effect_intervals
    summaries = {}
    for panel in PANELS:
        selected = [p for p in cells if p['panel'] == panel]
        expected = 9 if panel == 'original_heldout' else 18 if panel == 'old_external' else 63
        require(len(selected) == expected and {p['match'] for p in selected} == set(panels[panel]),
                '不能把训练fold/seed当比赛或省略负单元')
        summaries[panel] = {metric: interval_fn({seq: mean(
            p['delta_pp'][metric] for p in selected if p['match'] == seq) for seq in panels[panel]})
            for metric in METRICS}
    return summaries


def gap_intervals(cells, panels, interval_fn=None):
    validate_panels(panels)
    if interval_fn is None:
        from substitution_paired_analysis import effect_intervals
        interval_fn = effect_intervals
    summaries = {}
    for panel in PANELS:
        values, unavailable = {}, []
        for seq in panels[panel]:
            rows = [p['gap']['delta_recovery_rate_pp'] for p in cells if p['match'] == seq]
            require(len(rows) == (3 if panel == 'original_heldout' else 9), 'gap配对训练单元不完整')
            require(all(v is None for v in rows) or all(v is not None for v in rows),
                    '同场不同训练单元不能变更gap分母')
            if rows[0] is None:
                unavailable.append(seq)
            else:
                values[seq] = mean(rows)
        if len(values) >= 2:
            summary = interval_fn(values)
        else:
            summary = dict(n_independent_matches=len(values), match_deltas_pp=values,
                mean_delta_pp=mean(values.values()) if values else None,
                Student_t_95CI=None, percentile_match_bootstrap_95CI=None,
                leave_one_match_out_mean=None,
                status='fewer_than_two_matches_with_registered_events_no_interval',
                formal_equivalence_or_noninferiority_test=False, margin=None)
        summaries[panel] = dict(summary, zero_event_matches_retained_null=unavailable,
            outcome='all_registered_trusted_gap_recovery_rate_difference_pp_not_physical_occlusion')
    return summaries


def report_metrics(report, sequence):
    require(report['status'] == 'complete', '引用的实际评价未完成')
    result = finite_metrics(report['summary'][sequence]['metrics_percent'])
    if 'metrics_percent' in report:
        require(finite_metrics(report['metrics_percent']) == result, '实际报告顶层/序列指标不一致')
    return result


def reference_semantics(entry, report, cfg):
    """基线标签必须对应实际原模型，不能把纯R、C或困难池报告换标签。"""
    baseline, declared = entry['group'], entry['job']
    expected_method = dict(original_gated_RS='gated', strong_motion_RS='motion',
                           same_capacity_motion_RS='motion_residual')[baseline]
    job = report['job']; sequence = declared['sequence']
    require(job == declared and job['method'] == expected_method
            and report['DO_PREPROC'] is False and report['predictions_GT_filtered'] is False
            and report['test_read'] is False and report.get('sequence', sequence) == sequence,
            '历史参照标签、原job或GT评价边界不符')
    protocol = report['protocol_sha256']
    if protocol == cfg['source_tracking_config']['sha256']:
        require(job['kind'] == 'new_RS' and job['pool'] == 'balanced'
                and sequence in cfg['panels']['original_heldout']+cfg['panels']['old_external'],
                '原五场只可引用原v10 balanced RS，不能换成纯R/困难池')
    elif protocol == cfg['source_seven_tracking_config']['sha256']:
        require(baseline != 'same_capacity_motion_RS' and job['kind'] == 'learned'
                and job['group'] == 'B' and expected_method in ('motion', 'gated')
                and sequence in cfg['panels']['seven_observed'],
                'ABC七场只可引用B balanced RS，C/A或同容量参考不可冒充')
    else:
        raise ValueError('历史参照不是原冻结五场/七场追踪协议')


def source_references(cfg, rt):
    require(set(cfg['reference_reports']) == set(BASELINES), '完整三类历史参照未冻结')
    records = []
    expected_counts = dict(original_gated_RS=90, strong_motion_RS=90, same_capacity_motion_RS=27)
    for baseline in BASELINES:
        entries = cfg['reference_reports'][baseline]
        require(len(entries) == expected_counts[baseline], '历史参照范围应90/90/27，七场同容量缺口须实际追踪')
        for entry in entries:
            require(entry['group'] == baseline, '历史模型身份未明确登记')
            job = entry['job']; report_path = rt.checked(entry['report']); report = rt.read(report_path)
            reference_semantics(entry, report, cfg)
            metrics = report_metrics(report, job['sequence'])
            require(metrics == finite_metrics(entry['metrics']), '冻结指标不等于来源原报告')
            if 'job' in report:
                require(all(report['job'].get(k) == job[k] for k in ('fold', 'seed', 'sequence')),
                        '原报告真实fold/seed/sequence身份不符')
            records.append(dict(group=baseline, job=job, metrics=metrics, recovery=report['recovery']['overall'],
                report=entry['report'], source_origin='historical_readonly_new_updates0'))
    return records


def write_csv(path, fields, rows):
    with Path(path).open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow(row)


def analyze(config, control, output):
    rt = importlib.import_module('pose_velocity_tracking_runtime')
    cfg, dep, _ = rt.validate_config(config)
    import substitution_paired_analysis as statistics_module
    old_seven = rt.read(rt.checked(cfg['source_seven_tracking_config']))
    require(rt.sha(Path(statistics_module.__file__)) == rt.sha(
        Path(old_seven['bundle'])/'tools/research_ops/substitution_paired_analysis.py'),
        '配对区间函数必须与原已冻结来源字节一致')
    control = dep[3].storage().physical_child(control, rt.EXP)
    output = dep[3].storage().physical_child(output, rt.EXP)
    state = rt.read(control/'driver_state.json'); expected = cfg['tracking_matrix']
    require(len(expected) == 513 and len(state['completed_tracking']) == 513
            and [x['job'] for x in state['completed_tracking']] == expected
            and state['protocol_sha256'] == rt.sha(config), '实际513矩阵未齐不能汇总')
    records = []
    for entry in state['completed_tracking']:
        job = entry['job']; path = control/'runs'/job['job_id']/'metric/report.json'
        report = rt.read(path)
        require(rt.sha(path) == entry['report_sha256'] and report['job'] == job
                and report['protocol_sha256'] == rt.sha(config)
                and report['schema'] == 'bounded_velocity513_trackeval_gap_v1'
                and report['DO_PREPROC'] is False and report['predictions_GT_filtered'] is False
                and report['test_read'] is False, '原评价来源/模型/协议或GT边界变化')
        records.append(dict(job=job, metrics=report_metrics(report, job['sequence']),
            recovery=report['recovery']['overall'], report=rt.ref(path), source_origin='actual_new_tracking'))
    source = source_references(cfg, rt)
    comparisons, all_refs = paired_cells(records, source, expected, cfg['panels'])
    summaries = {name: intervals(cells, cfg['panels']) for name, cells in comparisons.items()}
    gap_summaries = {name: gap_intervals(cells, cfg['panels']) for name, cells in comparisons.items()}
    require(not output.exists(), '已有分析或partial，不覆盖/隐式重放')
    output.mkdir(parents=True)
    fields = ['job_id', 'kind', 'group', 'fold', 'seed', 'pose_enabled', 'sequence', *METRICS,
              'gap_events', 'recovery_rate', 'report_path', 'report_sha256']
    write_csv(output/'all_results.csv', fields, [dict(
        {k: record['job'][k] for k in ('job_id', 'kind', 'group', 'fold', 'seed', 'pose_enabled', 'sequence')},
        **record['metrics'], gap_events=record['recovery']['total_events'],
        recovery_rate=record['recovery']['recovery_rate'],
        report_path=record['report']['path'], report_sha256=record['report']['sha256']) for record in records])
    write_csv(output/'all_baseline_references.csv',
        ['baseline', 'job_id', 'fold', 'seed', 'sequence', *METRICS, 'source_origin', 'report_path', 'report_sha256'],
        [dict(baseline=r['group'], job_id=r['job']['job_id'], fold=r['job']['fold'], seed=r['job']['seed'],
            sequence=r['job']['sequence'], **r['metrics'], source_origin=r['source_origin'],
            report_path=r['report']['path'], report_sha256=r['report']['sha256']) for r in all_refs])
    write_csv(output/'all_paired_cells.csv',
        ['comparison', 'panel', 'match', 'fold', 'seed', 'target', 'reference', *METRICS],
        [dict(comparison=name, **{k: v for k, v in row.items() if k not in ('delta_pp', 'gap')}, **row['delta_pp'])
         for name, cells in comparisons.items() for row in cells])
    gap_fields = ['target_event_denominator', 'target_success', 'target_recovery_rate',
        'reference_event_denominator', 'reference_success', 'reference_recovery_rate',
        'delta_recovery_rate_pp', 'target_report_path', 'target_report_sha256',
        'reference_report_path', 'reference_report_sha256']
    write_csv(output/'all_paired_gaps.csv',
        ['comparison', 'panel', 'match', 'fold', 'seed', 'target', 'reference', *gap_fields],
        [dict(comparison=name, **{k: v for k, v in row.items() if k not in ('delta_pp', 'gap')}, **row['gap'])
         for name, cells in comparisons.items() for row in cells])
    report = dict(schema='bounded_velocity513_complete_paired_intervals_v1', status=STATUS,
        protocol_sha256=rt.sha(config), analysis_plan=cfg['analysis_plan'],
        tracking_jobs=513, new_representation_tracking_jobs=450, added_reference_tracking_jobs=63,
        historical_reference_reports_readonly=207, new_training_updates_in_tracking=0,
        comparisons=summaries, panels=cfg['panels'], primary_metric='AssA',
        comparison_families=8, paired_cells=720, intervals=120,
        gap_comparisons=gap_summaries, paired_gap_cells=720, separate_gap_interval_descriptions=24,
        all_results_csv=rt.ref(output/'all_results.csv'), all_baseline_references_csv=rt.ref(output/'all_baseline_references.csv'),
        all_paired_cells_csv=rt.ref(output/'all_paired_cells.csv'),
        all_paired_gaps_csv=rt.ref(output/'all_paired_gaps.csv'),
        all_actual_reports=[r['report'] for r in records], all_reference_reports=[r['report'] for r in all_refs],
        all_seeds_folds_unknowns_and_negative_results_retained=True,
        formal_equivalence_or_noninferiority=False, performance_margin=None, test_read=False,
        limitations=['all three panels are already observed development matches; no final test inference',
            'per match first average matched training cells, then matches equally; fold/seed are not matches',
            'three panels reported separately; never combine3/2/7 into a single precision claim',
            'conditional fixed training panel; short convenience clips; approximate match independence/normality',
            '120 metric and24 separate gap descriptions unadjusted; no significance selection or equivalence from interval crossing0',
            'shared fixed detections, GT only labels/evaluation; gap proxy is not physical occlusion',
            'on-off compares each model own learned motion branch; shuffled training may also change regularization',
            'historical same-capacity motion required63 new evaluations, not63 new training runs'])
    with (output/'report.json').open('x', encoding='utf-8') as stream:
        stream.write(rt.canonical(report)+'\n')
    return dict(status=STATUS, tracking_jobs=513, new_representation_tracking_jobs=450,
                added_reference_tracking_jobs=63, paired_cells=720, intervals=120,
                paired_gap_cells=720, separate_gap_interval_descriptions=24)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    rt = importlib.import_module('pose_velocity_tracking_runtime')
    print(rt.canonical(analyze(args.config, args.control, args.output)))
