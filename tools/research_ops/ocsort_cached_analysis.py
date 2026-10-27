"""官方OC-SORT同缓存12开发片段的配对描述；每场一次OC，不复制为训练seed样本。"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from statistics import mean
import stat
import re
import traceback

R = Path('D:/projects/FutsalMOT_Research'); EXP = R/'pose/ocsort_cached12_a01'
FOLDS = ('game4', 'game6', 'game9'); SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
PANELS = ('original_heldout', 'old_external', 'seven_observed')
BASELINES = ('PT_bbox', 'strong_motion_RS', 'T_RS')
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
STATUS = 'complete12_official_ocsort_cached_paired_analysis'


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(path):
    path = Path(path); require(path.is_absolute(), '分析输入/输出必须绝对路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
        for p in path.parts), '仅允许实际研究根，最终测试封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            value = part.lstat()
            require(not stat.S_ISLNK(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def sha(path):
    value = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): value.update(block)
    return value.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path']); require(path.is_file() and sha(path) == value['sha256'], '来源SHA改变：'+str(path))
    return path


def csv_rows(reference):
    with checked(reference).open(encoding='utf-8-sig', newline='') as stream: return list(csv.DictReader(stream))


def panels_map(panels):
    require(set(panels) == set(PANELS) and [len(panels[k]) for k in PANELS] == [3, 2, 7], '三面板应为3/2/7比赛，不合并精度')
    lookup = {s: p for p in PANELS for s in panels[p]}
    require(len(lookup) == 12 and set(panels['original_heldout']) == set(OLD), '12开发片段缺项或面板重复')
    return lookup


def report_values(report, sequence):
    require(report['status'] == 'complete' and report['DO_PREPROC'] is False
            and report['predictions_GT_filtered'] is False and report['test_read'] is False,
            '必须完整评价、保留未匹配预测、GT仅指标且测试未读')
    values = report['summary'][sequence]['metrics_percent']
    require(set(METRICS) <= set(values)
            and all(type(values[k]) in (float, int) and math.isfinite(values[k]) for k in METRICS), '五指标缺失/非有限，不筛负结果')
    return {k: values[k] for k in METRICS}


def gap_values(record):
    value = record['recovery']; total, success, rate = (value[k] for k in ('total_events', 'same_prediction_ID_recovered', 'recovery_rate'))
    require(type(total) is int and type(success) is int and 0 <= success <= total,
            '可信断档事件分母/成功数不完整')
    require((rate is None and success == 0) if total == 0 else
            (type(rate) in (float, int) and math.isfinite(rate) and abs(rate-success/total) <= 1e-12),
            '原全事件恢复率不一致；零事件必须null')
    return total, success, rate


def allowed_cells(sequence):
    folds = (OLD[sequence],) if sequence in OLD else FOLDS
    return {(fold, seed) for fold in folds for seed in SEEDS}


def check_reference_record(record, baseline, sequence, vcfg, vsha):
    report = record['body']; job = report['job']
    require(job['sequence'] == sequence and report.get('sequence', sequence) == sequence
            and report['frames'] == vcfg['sources'][sequence]['frames'], '参照实际比赛/帧scope不同')
    old_sha = vcfg['source_tracking_config']['sha256']; seven_sha = vcfg['source_seven_tracking_config']['sha256']
    if baseline == 'PT_bbox':
        require(job['kind'] == 'PT' and job['mode'] == 'PT_bbox'
                and report['protocol_sha256'] == (old_sha if sequence not in vcfg['panels']['seven_observed'] else seven_sha),
                'PT上下文必须实际原PT_bbox，不能借static_pose或其他模型')
    elif baseline == 'strong_motion_RS':
        require(job['method'] == 'motion', '强motion参照不能换成同容量或Pose模型')
        if sequence in vcfg['panels']['seven_observed']:
            require(report['protocol_sha256'] == seven_sha and job['kind'] == 'learned' and job['group'] == 'B',
                    '七场强motion应为原ABC的B，不能用纯R/C')
        else:
            require(report['protocol_sha256'] == old_sha and job['kind'] == 'new_RS' and job['pool'] == 'balanced',
                    '旧五场强motion应为原balanced RS，不能用纯R/困难池')
    else:
        require(baseline == 'T_RS' and report['protocol_sha256'] == vsha
                and job['kind'] == 'new' and job['group'] == 'T_RS' and job['pose_enabled'] is True
                and report['schema'] == 'bounded_velocity513_trackeval_gap_v1'
                and report['source_cache'] == vcfg['sources'][sequence]['cache'],
                'T参照必须新T_RS开启Pose、原共享缓存，不能用off或shapecontrol')


def inventory(config):
    """只从已有报告/已绑定CSV取得12PT+90强motion+90真T，不执行旧评价。"""
    vcfg = read(checked(config['source_velocity_protocol'])); vanalysis = read(checked(config['source_velocity_analysis']))
    lookup = panels_map(vcfg['panels']); vsha = config['source_velocity_protocol']['sha256']
    require(vcfg['schema'] == 'bounded_velocity513_tracking_protocol_v1'
            and vanalysis['status'] == 'complete513_all_results450_new63_reference_paired_intervals'
            and vanalysis['protocol_sha256'] == vsha and config['sources'] == vcfg['sources']
            and config['panels'] == vcfg['panels'] and config['registries'] == vcfg['registries'],
            '原V完整结果/12共享来源/事件口径不同')
    old = read(checked(config['old_five_analysis'])); abc = read(checked(config['ABC_analysis']))
    require(old['status'] == 'complete_all253_tracking_comparisons'
            and old['protocol_sha256'] == vcfg['source_tracking_config']['sha256']
            and abc['status'] == 'complete392_all_results_and_paired_intervals'
            and abc['protocol_sha256'] == vcfg['source_seven_tracking_config']['sha256'], 'PT原5/7场完成分析来源不同')
    old_cfg = read(checked(vcfg['source_tracking_config'])); abc_cfg = read(checked(vcfg['source_seven_tracking_config']))
    require(dict(old_cfg['sources'], **abc_cfg['sources']) == vcfg['sources'], '全部参照与OC必须同一份源缓存元数据')
    selected = []
    for row in old['all_results']:
        if row['job']['kind'] == 'PT' and row['job']['mode'] == 'PT_bbox':
            selected.append(('PT_bbox', row['job']['sequence'], row['report'], row['metrics'], None, None))
    for row in csv_rows(abc['all_results_csv']):
        if row['kind'] == 'PT' and row['mode'] == 'PT_bbox':
            selected.append(('PT_bbox', row['sequence'], dict(path=row['report_path'], sha256=row['report_sha256']),
                {k: float(row[k]) for k in METRICS}, None, None))
    for row in csv_rows(vanalysis['all_baseline_references_csv']):
        if row['baseline'] == 'strong_motion_RS':
            selected.append(('strong_motion_RS', row['sequence'], dict(path=row['report_path'], sha256=row['report_sha256']),
                {k: float(row[k]) for k in METRICS}, row['fold'], int(row['seed'])))
    for row in csv_rows(vanalysis['all_results_csv']):
        if row['kind'] == 'new' and row['group'] == 'T_RS' and row['pose_enabled'] == 'True':
            selected.append(('T_RS', row['sequence'], dict(path=row['report_path'], sha256=row['report_sha256']),
                {k: float(row[k]) for k in METRICS}, row['fold'], int(row['seed'])))
    require(Counter(b for b, *_ in selected) == dict(PT_bbox=12, strong_motion_RS=90, T_RS=90), '12/90/90参照实物缺失，不复制补数')
    records = []; seen = set()
    for baseline, sequence, reference, declared, fold, seed in selected:
        require(sequence in lookup and (baseline, sequence, fold, seed) not in seen, '参照样本重复/范围不同')
        seen.add((baseline, sequence, fold, seed)); body = read(checked(reference))
        metrics = report_values(body, sequence)
        require(metrics == declared, '来源CSV/分析摘要不等于原完整TrackEval百分比')
        record = dict(baseline=baseline, sequence=sequence, fold=fold, seed=seed, metrics=metrics,
            recovery=body['recovery']['overall'], report=reference, body=body)
        check_reference_record(record, baseline, sequence, vcfg, vsha); gap_values(record)
        if baseline != 'PT_bbox':
            require((fold, seed) in allowed_cells(sequence)
                    and body['job']['fold'] == fold and body['job']['seed'] == seed, '原3仅对应fold，外部应九训练单元')
        records.append({k: v for k, v in record.items() if k != 'body'})
    return records, dict(source_velocity_protocol=config['source_velocity_protocol'],
        source_velocity_analysis=config['source_velocity_analysis'], old_five_analysis=config['old_five_analysis'],
        ABC_analysis=config['ABC_analysis'], old_sources=vcfg['source_tracking_config'], seven_sources=vcfg['source_seven_tracking_config'],
        baseline_counts=dict(Counter(r['baseline'] for r in records)), total_source_frames=sum(s['frames'] for s in vcfg['sources'].values()))


def paired_matches(oc_records, reference_records, panels):
    lookup = panels_map(panels)
    require(len(oc_records) == 12 and {r['sequence'] for r in oc_records} == set(lookup), 'OC必须每场一次完整12评价，不创建训练fold/seed')
    oc = {r['sequence']: r for r in oc_records}
    require(all(r.get('fold') is None and r.get('seed') is None for r in oc_records), 'OC无训练fold/seed，不可制造独立样本')
    refs = defaultdict(list)
    for row in reference_records:
        require(row['baseline'] in BASELINES and row['sequence'] in lookup, '未知参照或范围外比赛')
        refs[row['baseline'], row['sequence']].append(row)
    rows = []
    for baseline in BASELINES:
        for panel in PANELS:
            for sequence in panels[panel]:
                group = refs[baseline, sequence]
                expected = {(None, None)} if baseline == 'PT_bbox' else allowed_cells(sequence)
                require(len(group) == len(expected) and {(r['fold'], r['seed']) for r in group} == expected,
                        '参照训练面板缺项/重复，不能按好结果筛seed')
                target = oc[sequence]
                for record in [target]+group:
                    require(all(type(record['metrics'][k]) in (float, int) and math.isfinite(record['metrics'][k]) for k in METRICS),
                            '缺失/非有限指标不能被忽略')
                metric_mean = {k: mean(r['metrics'][k] for r in group) for k in METRICS}
                denominator, successes, rate = gap_values(target)
                gap = [gap_values(r) for r in group]
                require({n for n, _, _ in gap} == {denominator}, '原全注册gap分母不同，不允许筛端点比较')
                reference_rate = mean(v for _, _, v in gap) if denominator else None
                rows.append(dict(baseline=baseline, panel=panel, sequence=sequence,
                    OC_evaluations=1, reference_training_cells=len(group),
                    OC_metrics=target['metrics'], reference_mean_metrics=metric_mean,
                    delta_pp={k: target['metrics'][k]-metric_mean[k] for k in METRICS},
                    gap=dict(total_registered_events=denominator, OC_success=successes, OC_rate=rate,
                        reference_mean_success=mean(s for _, s, _ in gap), reference_mean_rate=reference_rate,
                        delta_recovery_rate_pp=100*(rate-reference_rate) if denominator else None),
                    OC_report=target['report'], reference_reports=[r['report'] for r in group]))
    require(len(rows) == 36, '应为3参照×12比赛的36配对，不是OC复制到90单元')
    return rows


def describe(rows, panels, interval_fn):
    lookup = panels_map(panels); metrics = {}; gaps = {}
    for baseline in BASELINES:
        metrics[baseline] = {}; gaps[baseline] = {}
        for panel in PANELS:
            group = [r for r in rows if r['baseline'] == baseline and r['panel'] == panel]
            require(len(group) == len(panels[panel]) and {r['sequence'] for r in group} == set(panels[panel]), '比赛配对缺失/重复')
            metrics[baseline][panel] = {k: interval_fn({r['sequence']: r['delta_pp'][k] for r in group}) for k in METRICS}
            available = {r['sequence']: r['gap']['delta_recovery_rate_pp'] for r in group if r['gap']['delta_recovery_rate_pp'] is not None}
            missing = [r['sequence'] for r in group if r['gap']['delta_recovery_rate_pp'] is None]
            if len(available) >= 2:
                result = interval_fn(available)
            else:
                result = dict(n_independent_matches=len(available), match_deltas_pp=available,
                    mean_delta_pp=mean(available.values()) if available else None,
                    Student_t_95CI=None, percentile_match_bootstrap_95CI=None,
                    leave_one_match_out_mean=None, status='fewer_than_two_matches_with_events_no_interval')
            gaps[baseline][panel] = dict(result, zero_event_matches_retained_null=missing,
                outcome='all_registered_trusted_detection_gap_proxy_not_physical_occlusion')
    return metrics, gaps


def load_evaluations(config_path, config, evaluations):
    manifest = read(evaluations) if isinstance(evaluations, (str, Path)) else evaluations
    require(manifest['schema'] == 'official_ocsort_cached12_evaluation_manifest_v1'
            and manifest['status'] == 'complete12_official_ocsort_cached_evaluations'
            and manifest['protocol'] == ref(config_path) and len(manifest['evaluations']) == 12,
            'OC十二场评价完成清单未齐或来源协议不同')
    lookup = panels_map(config['panels']); records = []
    require({r['sequence'] for r in manifest['evaluations']} == set(lookup), 'OC评价清单不能增删比赛')
    for item in manifest['evaluations']:
        sequence = item['sequence']; body = read(checked(item['report'])); source = config['sources'][sequence]
        require(body['schema'] == 'official_ocsort_cached12_evaluation_v1' and body['protocol_sha256'] == sha(config_path)
                and body['sequence'] == sequence and body['frames'] == source['frames']
                and body['source_cache'] == source['cache'] and body.get('fold') is None and body.get('seed') is None,
                '官方OC评价不是同一缓存/完整帧或混入训练fold/seed')
        record = dict(sequence=sequence, fold=None, seed=None, metrics=report_values(body, sequence),
                      recovery=body['recovery']['overall'], report=item['report'])
        gap_values(record); records.append(record)
    return records


def validate_config(config):
    require(config['schema'] == 'official_ocsort_cached12_protocol_v1' and config['approved_by'] == 'root'
            and config['test_sealed'] is True and config.get('formal_equivalence_or_noninferiority') is False,
            '官方同缓存12开发片段及测试封存/描述边界未冻结')
    require(set(config['sources']) == set(panels_map(config['panels'])), '12比赛源与三面板不对应')


def analyze(config_path, evaluations, output, execute=False):
    config_path, output = physical(config_path), physical(output); config = read(config_path); validate_config(config)
    require(EXP in output.parents and not output.exists(), '分析输出越界/已有partial，不覆盖')
    refs, sources = inventory(config); oc = load_evaluations(config_path, config, evaluations)
    rows = paired_matches(oc, refs, config['panels'])
    if not execute:
        return dict(status='readonly12_official_ocsort_paired_analysis_preflight', OC_evaluations=12,
            reference_cells=192, paired_matches=36, metric_intervals=45, separate_gap_descriptions=9,
            source_inventory=sources, new_optimizer_updates=0, model_loaded=False, test_read=False)
    interval_path = checked(config['interval_source'])
    require(interval_path.name == 'substitution_paired_analysis.py', '必须复用既有比赛t/固定bootstrap/LOO纯函数')
    spec = importlib.util.spec_from_file_location('official_ocsort_frozen_descriptive_intervals', interval_path)
    stats = importlib.util.module_from_spec(spec); spec.loader.exec_module(stats)
    metrics, gaps = describe(rows, config['panels'], stats.effect_intervals)
    output.mkdir(parents=True)
    def csv_write(name, fields, values):
        with (output/name).open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(values)
    try:
        csv_write('all_OC_results.csv', ['sequence', *METRICS, 'gap_events', 'gap_success', 'gap_rate', 'report_path', 'report_sha256'],
            [dict(sequence=r['sequence'], **r['metrics'], gap_events=r['recovery']['total_events'],
                gap_success=r['recovery']['same_prediction_ID_recovered'], gap_rate=r['recovery']['recovery_rate'],
                report_path=r['report']['path'], report_sha256=r['report']['sha256']) for r in oc])
        csv_write('all_reference_cells.csv', ['baseline', 'sequence', 'fold', 'seed', *METRICS, 'gap_events', 'gap_success', 'gap_rate', 'report_path', 'report_sha256'],
            [dict(**{k: r[k] for k in ('baseline', 'sequence', 'fold', 'seed')}, **r['metrics'],
                gap_events=r['recovery']['total_events'], gap_success=r['recovery']['same_prediction_ID_recovered'],
                gap_rate=r['recovery']['recovery_rate'], report_path=r['report']['path'], report_sha256=r['report']['sha256']) for r in refs])
        csv_write('all_paired_matches.csv', ['baseline', 'panel', 'sequence', 'OC_evaluations', 'reference_training_cells', *METRICS, 'OC_report', 'reference_reports'],
            [dict(**{k: r[k] for k in ('baseline', 'panel', 'sequence', 'OC_evaluations', 'reference_training_cells')},
                **r['delta_pp'], OC_report=canonical(r['OC_report']), reference_reports=canonical(r['reference_reports'])) for r in rows])
        csv_write('all_paired_gaps.csv', ['baseline', 'panel', 'sequence', 'reference_training_cells',
            'total_registered_events', 'OC_success', 'OC_rate', 'reference_mean_success', 'reference_mean_rate', 'delta_recovery_rate_pp'],
            [dict(**{k: r[k] for k in ('baseline', 'panel', 'sequence', 'reference_training_cells')}, **r['gap']) for r in rows])
        report = dict(schema='ocsort_cached12_paired_analysis_protocol_v1', status=STATUS,
            protocol=ref(config_path), OC_evaluations=12, reference_cells=192, paired_matches=36,
            comparison_direction='OCSORT_minus_reference', primary_reference='strong_motion_RS',
            secondary_reference='T_RS', context_reference='PT_bbox', primary_metric='AssA', panels=config['panels'],
            metric_comparisons=metrics, metric_interval_descriptions=45, gap_comparisons=gaps, separate_gap_interval_descriptions=9,
            source_inventory=sources, interval_source=config['interval_source'],
            all_OC_results=ref(output/'all_OC_results.csv'), all_reference_cells=ref(output/'all_reference_cells.csv'),
            all_paired_matches=ref(output/'all_paired_matches.csv'), all_paired_gaps=ref(output/'all_paired_gaps.csv'),
            all_OC_reports=[r['report'] for r in oc], all_reference_reports=[r['report'] for r in refs],
            all_negative_results_preserved=True, formal_equivalence_or_noninferiority=False, performance_margin=None,
            new_optimizer_updates=0, model_loaded=False, TrackEval_rerun=False, test_read=False,
            limitations=['one official OC evaluation per match; OC has no training fold/seed and is never replicated as9 independent observations',
                'references first average the fixed3 or9 matched training cells within each match; matches equally weighted in3/2/7 separate panels',
                'all12 are already observed short development clips, not final test, official full-benchmark ranking, or futsal generalization',
                'conditional fixed training panel; approximate independence/normality;45 metric plus9 gap descriptions unadjusted',
                'tracker-level comparison changes association mechanisms; OC versus T_RS cannot alone establish a Pose contribution',
                'full registered trusted-gap denominators, including ambiguous/missing endpoints; proxy not physical occlusion',
                'confidence interval containing0 is not equivalence; no performance threshold or best-seed selection'])
        with (output/'report.json').open('x', encoding='utf-8') as stream: stream.write(canonical(report)+'\n')
        return {k: report[k] for k in ('status', 'OC_evaluations', 'reference_cells', 'paired_matches', 'metric_interval_descriptions', 'separate_gap_interval_descriptions')}
    except BaseException as error:
        with (output/'failed.json').open('x', encoding='utf-8') as stream:
            stream.write(canonical(dict(status='failed_analysis_sources_preserved_no_replay', error=repr(error),
                traceback=traceback.format_exc(), new_optimizer_updates=0, test_read=False))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'evaluations', 'output'): parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    print(canonical(analyze(args.config, args.evaluations, args.output, args.execute)))
