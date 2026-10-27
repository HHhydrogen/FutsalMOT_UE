"""OC阈值.6→.25单因素的独立配对描述；不重跑旧追踪、模型或TrackEval。"""
import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from statistics import mean
import re
import stat
import sys
import traceback

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/ocsort_threshold025_a01'
SOURCE_ANALYSIS_SHA = '2552b2b9ae59adfe529fe3a6ba9e4659ecf6beae8e3bc14bf9525b7bcafe5ea8'
INTERVAL_SHA = '7458aa01dc5396124ac40d51ac3a3ff9851ce2a8cb4e61e64f4e7d9b6b695e7e'
OLD_ROOT_SHA = '13f185e6260c7ecc2456af6e98a02684076be7b388d932754516ea96bc4d3796'
OLD_ANALYSIS_SHA = 'cfcaafc1e328dbedb4ba8e949ddc6a3f09508a22b760591ca38bf5dc027ef145'
PANELS = ('original_heldout', 'old_external', 'seven_observed')
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
CONTEXT = ('strong_motion_RS', 'T_RS', 'PT_bbox')
BASELINES = ('OC06', *CONTEXT)
STATUS = 'complete12_OC025_single_threshold_all_results48_pairs60_metric12_gap_intervals'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(value):
    path = Path(value)
    require(path.is_absolute(), '分析输入/输出必须绝对物理路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
        for part in path.parts), '只允许实际DResearch；最终测试继续封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '不跟随junction或符号链接')
    return path


def sha(path):
    return hashlib.sha256(physical(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def checked(reference):
    path = physical(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '原冻结元数据来源改变：' + str(path))
    return path


def read(path):
    return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def load_module(name, reference, required_sha):
    require(reference['sha256'] == required_sha, '必须复用指定冻结纯函数字节')
    path = checked(reference)
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(value)
    finally:
        sys.dont_write_bytecode = old
    return value


def one_factor(old, new):
    require(old.get('det_thresh') == .6 and new.get('det_thresh') == .25
            and set(old) == set(new) and {k: v for k, v in old.items() if k != 'det_thresh'} ==
            {k: v for k, v in new.items() if k != 'det_thresh'} and new.get('use_byte') is False,
            '唯一数值因素必须是det_thresh .6→.25；byte及其他原参数不变')


def validated_sources(config):
    require(config['schema'] == 'ocsort_threshold025_protocol_v1' and config['approved_by'] == 'root'
            and config['test_sealed'] is True and config['formal_equivalence_or_noninferiority'] is False,
            '必须独立阈值单因素root协议，测试封存且无等效判定')
    require(config['old06_complete']['sha256'] == OLD_ROOT_SHA
            and config['source_old_OC_analysis']['sha256'] == OLD_ANALYSIS_SHA, '原OC06完成链必须明确固定')
    complete = read(checked(config['old06_complete']))
    require(complete['status'] == 'complete_official_OCSORT_cached12_admission_tracking_metrics_intervals_and_exit_verified'
            and complete['producer_processes_absent'] is True and complete['test_read'] is False
            and complete['analysis'] == config['source_old_OC_analysis'], '原OC06未闭合或分析来源不同')
    old = read(checked(complete['protocol']))
    previous = read(checked(config['source_old_OC_analysis']))
    require(previous['status'] == 'complete12_official_ocsort_cached_paired_analysis'
            and previous['protocol'] == complete['protocol'], '原十二OC06完整分析身份不同')
    source = load_module('threshold025_original_frozen_analysis', config['source_analysis'], SOURCE_ANALYSIS_SHA)
    source.validate_config(old)
    one_factor(old['parameters'], config['parameters'])
    for key in ('sources', 'panels', 'registries', 'official_manifest', 'dependency_manifest', 'source_velocity_protocol',
                'source_velocity_analysis', 'old_five_analysis', 'ABC_analysis', 'interval_source'):
        require(config[key] == old[key], '阈值以外来源/数值政策不同：' + key)
    require(set(config['sources']) == set(source.panels_map(config['panels']))
            and sum(s['frames'] for s in config['sources'].values()) == 8165, '固定十二/8165来源不可增删')
    return source, complete, old, previous


def receipt_parameters(body, expected, source):
    receipt = source.read(source.checked(body['tracking_receipt']))
    require(receipt['schema'] == 'official_ocsort_cached12_tracking_v1' and receipt['status'] == 'complete'
            and receipt['sequence'] == body['sequence'] and receipt['parameters'] == expected
            and receipt['protocol_sha256'] == body['protocol_sha256'] and receipt['GT_used_for_tracking'] is False,
            '实际追踪收据参数/协议/身份不同，不能只核配置计划')
    require(receipt['frames'] == body['frames'] and receipt['source_cache'] == body['source_cache'], '实际追踪帧/原缓存不同')


def old_OC_records(previous, old, complete, source):
    rows = source.csv_rows(previous['all_OC_results'])
    require(len(rows) == 12 and len({row['sequence'] for row in rows}) == 12, '原OC06每源必须一次')
    records = []
    for row in rows:
        sequence = row['sequence']; require(sequence in old['sources'], '原OC06含范围外来源')
        reference = dict(path=row['report_path'], sha256=row['report_sha256'])
        body = source.read(source.checked(reference))
        require(body['schema'] == 'official_ocsort_cached12_evaluation_v1' and body['sequence'] == sequence
                and body['protocol_sha256'] == complete['protocol']['sha256']
                and body['frames'] == old['sources'][sequence]['frames'] and body['source_cache'] == old['sources'][sequence]['cache'],
                '原OC06不能换成新阈值或不同缓存评价')
        metrics = source.report_values(body, sequence)
        require(metrics == {key: float(row[key]) for key in METRICS}, '原CSV指标与实际原报告不同')
        record = dict(sequence=sequence, fold=None, seed=None, metrics=metrics, recovery=body['recovery']['overall'], report=reference)
        n, success, rate = source.gap_values(record)
        require(int(row['gap_events']) == n and int(row['gap_success']) == success
                and (rate == float(row['gap_rate']) if n else row['gap_rate'] == ''), '原CSV全gap分母/成功率不同')
        receipt_parameters(body, old['parameters'], source)
        records.append(record)
    require(sum(r['recovery']['total_events'] for r in records) == 3690, '原全事件分母必须3690')
    return records


def primary_matches(target, previous, panels, source):
    lookup = source.panels_map(panels)
    for group in (target, previous):
        require(len(group) == 12 and {row['sequence'] for row in group} == set(lookup)
                and all(row.get('fold') is None and row.get('seed') is None for row in group),
                'OC025/OC06均每源一次，无训练fold/seed，不可复制成90样本')
    new = {row['sequence']: row for row in target}; old = {row['sequence']: row for row in previous}
    result = []
    for panel in PANELS:
        for sequence in panels[panel]:
            a, b = new[sequence], old[sequence]
            require(all(type(row['metrics'][k]) in (int, float) and math.isfinite(row['metrics'][k])
                        for row in (a, b) for k in METRICS), '五指标缺失/非有限，不筛负结果')
            n, success, rate = source.gap_values(a); old_n, old_success, old_rate = source.gap_values(b)
            require(n == old_n, '单因素比较必须保留原全注册事件，不筛端点')
            result.append(dict(baseline='OC06', panel=panel, sequence=sequence,
                OC_evaluations=1, reference_training_cells=1, reference_has_training_panel=False,
                OC_metrics=a['metrics'], reference_mean_metrics=b['metrics'],
                delta_pp={k: a['metrics'][k]-b['metrics'][k] for k in METRICS},
                gap=dict(total_registered_events=n, OC_success=success, OC_rate=rate,
                    reference_mean_success=old_success, reference_mean_rate=old_rate,
                    delta_recovery_rate_pp=100*(rate-old_rate) if n else None),
                OC_report=a['report'], reference_reports=[b['report']]))
    return result


def paired_matches(target, old, references, panels, source):
    main = primary_matches(target, old, panels, source)
    context = source.paired_matches(target, references, panels)
    for row in context:
        row['reference_has_training_panel'] = row['baseline'] != 'PT_bbox'
    result = main + context
    require(len(result) == 48 and Counter(row['baseline'] for row in result) == {key: 12 for key in BASELINES},
            '必须保留主12及上下文36比赛对')
    return result


def describe_primary(rows, panels, interval_fn):
    metrics, gaps = {}, {}
    for panel in PANELS:
        group = [row for row in rows if row['baseline'] == 'OC06' and row['panel'] == panel]
        require(len(group) == len(panels[panel]) and {row['sequence'] for row in group} == set(panels[panel]), '主比较比赛缺项/重复')
        metrics[panel] = {key: interval_fn({row['sequence']: row['delta_pp'][key] for row in group}) for key in METRICS}
        values = {row['sequence']: row['gap']['delta_recovery_rate_pp'] for row in group if row['gap']['delta_recovery_rate_pp'] is not None}
        nulls = [row['sequence'] for row in group if row['gap']['delta_recovery_rate_pp'] is None]
        if len(values) >= 2:
            result = interval_fn(values)
        else:
            result = dict(n_independent_matches=len(values), match_deltas_pp=values,
                mean_delta_pp=mean(values.values()) if values else None, Student_t_95CI=None,
                percentile_match_bootstrap_95CI=None, leave_one_match_out_mean=None,
                status='fewer_than_two_matches_with_events_no_interval')
        gaps[panel] = dict(result, zero_event_matches_retained_null=nulls,
            outcome='all_registered_trusted_detection_gap_proxy_not_physical_occlusion')
    return metrics, gaps


def describe(rows, panels, source, interval_fn):
    primary, primary_gap = describe_primary(rows, panels, interval_fn)
    context_rows = [row for row in rows if row['baseline'] in CONTEXT]
    context, context_gap = source.describe(context_rows, panels, interval_fn)
    return dict(OC06=primary, **context), dict(OC06=primary_gap, **context_gap)


def analyze(config_path, evaluations, output, execute=False):
    config_path, output = physical(config_path), physical(output)
    config = read(config_path)
    require(EXP in output.parents and not output.exists(), '独立分析输出越界/已有partial，不覆盖')
    source, complete, old_config, old_analysis = validated_sources(config)
    references, inventory = source.inventory(old_config)
    old = old_OC_records(old_analysis, old_config, complete, source)
    target = source.load_evaluations(config_path, config, evaluations)
    for row in target:
        body = source.read(source.checked(row['report']))
        receipt_parameters(body, config['parameters'], source)
    rows = paired_matches(target, old, references, config['panels'], source)
    require(sum(row['recovery']['total_events'] for row in target) == 3690, '新OC也必须完整3690事件')
    if not execute:
        return dict(status='readonly12_OC025_single_threshold_analysis_not_executed', OC025_evaluations=12,
            OC06_evaluations=12, context_reference_cells=192, paired_matches=48,
            primary_metric_intervals=15, primary_gap_descriptions=3, total_metric_intervals=60,
            total_gap_descriptions=12, source_inventory=inventory, new_optimizer_updates=0, test_read=False)
    statistics = load_module('threshold025_original_frozen_effect_intervals', config['interval_source'], INTERVAL_SHA)
    metrics, gaps = describe(rows, config['panels'], source, statistics.effect_intervals)
    output.mkdir(parents=True)
    def csv_write(name, fields, values):
        with (output/name).open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(values)
    def records_csv(name, records, contextual=False):
        fields = (['baseline', 'fold', 'seed'] if contextual else []) + ['sequence', *METRICS,
            'gap_events', 'gap_success', 'gap_rate', 'report_path', 'report_sha256']
        values = []
        for row in records:
            n, success, rate = source.gap_values(row)
            values.append(dict(**({k: row[k] for k in ('baseline', 'fold', 'seed')} if contextual else {}),
                sequence=row['sequence'], **row['metrics'], gap_events=n, gap_success=success, gap_rate=rate,
                report_path=row['report']['path'], report_sha256=row['report']['sha256']))
        csv_write(name, fields, values)
    try:
        records_csv('all_OC025_results.csv', target)
        records_csv('all_OC06_results.csv', old)
        records_csv('all_context_reference_cells.csv', references, True)
        fields = ['baseline', 'panel', 'sequence', 'OC025_evaluations', 'reference_cells', 'reference_has_training_panel']
        csv_write('all_paired_matches.csv', fields + [*METRICS, 'OC025_report', 'reference_reports'],
            [dict(baseline=row['baseline'], panel=row['panel'], sequence=row['sequence'], OC025_evaluations=1,
                reference_cells=row['reference_training_cells'], reference_has_training_panel=row['reference_has_training_panel'],
                **row['delta_pp'], OC025_report=canonical(row['OC_report']), reference_reports=canonical(row['reference_reports'])) for row in rows])
        csv_write('all_paired_gaps.csv', fields + ['total_registered_events', 'OC_success', 'OC_rate',
            'reference_mean_success', 'reference_mean_rate', 'delta_recovery_rate_pp'],
            [dict(baseline=row['baseline'], panel=row['panel'], sequence=row['sequence'], OC025_evaluations=1,
                reference_cells=row['reference_training_cells'], reference_has_training_panel=row['reference_has_training_panel'],
                **row['gap']) for row in rows])
        report = dict(schema='ocsort_threshold025_paired_analysis_v1', status=STATUS, protocol=ref(config_path),
            old06_complete=config['old06_complete'], source_old_OC_analysis=config['source_old_OC_analysis'],
            source_analysis=config['source_analysis'], interval_source=config['interval_source'], source_inventory=inventory,
            comparison_direction='OC025_minus_reference', primary_reference='OC06', context_references=list(CONTEXT),
            only_parameter_change=dict(name='det_thresh', old=.6, new=.25), official_default_threshold=False,
            other_parameters_unchanged=True, use_byte=False, source_frames=8165, OC025_evaluations=12,
            OC06_evaluations=12, context_reference_cells=192, paired_matches=48, registered_gap_events=3690,
            primary_metric='AssA', panels=config['panels'], primary_metric_interval_descriptions=15,
            primary_gap_interval_descriptions=3, context_metric_interval_descriptions=45,
            context_gap_interval_descriptions=9, metric_interval_descriptions=60, separate_gap_interval_descriptions=12,
            metric_comparisons=metrics, gap_comparisons=gaps,
            all_OC025_results=ref(output/'all_OC025_results.csv'), all_OC06_results=ref(output/'all_OC06_results.csv'),
            all_context_reference_cells=ref(output/'all_context_reference_cells.csv'),
            all_paired_matches=ref(output/'all_paired_matches.csv'), all_paired_gaps=ref(output/'all_paired_gaps.csv'),
            all_OC025_reports=[row['report'] for row in target], all_OC06_reports=[row['report'] for row in old],
            all_context_reference_reports=[row['report'] for row in references], all_negative_results_preserved=True,
            statistical_policy=dict(confidence=.95, Student_t_df='panel_match_N_minus_1', bootstrap_resamples=10000,
                bootstrap_seed=20261027, leave_one_match_out=True, multiple_comparison_adjustment=False),
            formal_equivalence_or_noninferiority=False, performance_margin=None, model_loaded=False,
            old_tracking_rerun=False, TrackEval_rerun=False, cache_or_GT_read=False, new_optimizer_updates=0, test_read=False,
            limitations=['主比较仅检验固定OC core中det_thresh .6→.25的整体轨迹输出效应，不等于纯关联模块优势。',
                '新旧OC各源一次，无训练fold/seed；三个上下文参照先在比赛内均3或9个固定训练单元，再3/2/7分别等权。',
                '全部十二片段已观察，短便利选片；固定训练面板、比赛近似独立/正态、小样本及60指标加12gap多比较未校正。',
                '所有可信gap事件作分母，零事件保留null；proxy不等物理遮挡，不因区间跨0宣称等效。',
                '.25不是官方默认或结果后搜索最优；不据此证明Pose或合成增益、SOTA、人工成本或五人制泛化。'])
        with (output/'report.json').open('x', encoding='utf-8') as stream:
            stream.write(canonical(report)+'\n')
        return {key: report[key] for key in ('status', 'OC025_evaluations', 'OC06_evaluations',
            'context_reference_cells', 'paired_matches', 'metric_interval_descriptions', 'separate_gap_interval_descriptions')}
    except BaseException:
        with (output/'failed.json').open('x', encoding='utf-8') as stream:
            stream.write(canonical(dict(status='failed_threshold_analysis_partial_preserved', traceback=traceback.format_exc(),
                old_tracking_rerun=False, TrackEval_rerun=False, new_optimizer_updates=0, test_read=False))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'evaluations', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    print(canonical(analyze(args.config, args.evaluations, args.output, args.execute)))
