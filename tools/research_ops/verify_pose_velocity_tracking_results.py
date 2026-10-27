"""独立终验513项来源、完整CSV及比赛配对区间；不推理、不重算TrackEval或训练预算。"""
import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
from statistics import mean, stdev
import subprocess
import sys

R = Path('D:/projects/FutsalMOT_Research')
EXP = R / 'pose/pose_velocity_learning_a01'
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
EXTERNAL = ('v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
SEVEN = ('v_1yHWGw8DH4A_c029', 'v_HdiyOtliFiw_c003', 'v_ITo3sCnpw_k_c007',
         'v_dw7LOz17Omg_c053', 'v_gQNyhv8y0QY_c003', 'v_i2_L4qquVg0_c006', 'v_iIxMOsCGH58_c013')
PANELS = ('original_heldout', 'old_external', 'seven_observed')
BASELINES = ('original_gated_RS', 'strong_motion_RS', 'same_capacity_motion_RS')
CASES = (('T_R', True), ('T_RS', True), ('T_RS', False), ('T_shuffle_RS', True), ('T_shuffle_RS', False))
CONTRASTS = (
    ('T_RS_minus_T_R', ('T_RS', True), ('T_R', True)),
    ('T_RS_minus_T_shuffle_RS', ('T_RS', True), ('T_shuffle_RS', True)),
    ('T_RS_on_minus_off', ('T_RS', True), ('T_RS', False)),
    ('T_shuffle_RS_on_minus_off', ('T_shuffle_RS', True), ('T_shuffle_RS', False)),
    ('T_RS_off_minus_T_shuffle_RS_off', ('T_RS', False), ('T_shuffle_RS', False)),
)
STATUS = 'complete513_sources450_new63_reference_all_pairs_intervals_and_exit_verified'
TOLERANCE_PP = 1e-8  # 仅核对数值序列化，不是性能非劣效或等效界限。


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def physical(path):
    """只访问实际DResearch；不借重解析点越界，也不读最终测试。"""
    import stat
    path = Path(path)
    require(path.is_absolute(), '三个入口及所有来源必须绝对路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(
        r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts), '实际研究来源越界或最终测试未封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '拒绝junction或其他重解析点')
    return path


def read(path):
    return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(physical(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path'])
    require(path.is_file() and sha(path) == value['sha256'], '冻结来源SHA改变：' + str(path))
    return path


def close(a, b):
    return type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and abs(a-b) <= TOLERANCE_PP


def expected_matrix(sources):
    """终验器独立构造450新T与63参考，不依赖分析器返回的任务数。"""
    require(set(sources) == set(OLD) | set(EXTERNAL) | set(SEVEN), '固定12场来源缺失/增加')
    result = []
    for fold in FOLDS:
        sequences = [s for s, f in OLD.items() if f == fold] + list(EXTERNAL) + list(SEVEN)
        for seed in SEEDS:
            for group, enabled in CASES:
                for sequence in sequences:
                    job = dict(kind='new', group=group, fold=fold, seed=seed, pose_enabled=enabled, sequence=sequence)
                    job['job_id'] = hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
                    result.append(job)
    for fold in FOLDS:
        for seed in SEEDS:
            for sequence in SEVEN:
                job = dict(kind='reference', group='same_capacity_motion_RS', fold=fold, seed=seed,
                           pose_enabled=False, sequence=sequence)
                job['job_id'] = hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
                result.append(job)
    require(len(result) == len({j['job_id'] for j in result}) == 513, '终验矩阵内部重复')
    return result


def terminal_gate(cfg, state, analysis, protocol_sha):
    expected = expected_matrix(cfg['sources'])
    require(cfg['tracking_matrix'] == expected and state['status'] == 'complete513_bounded_velocity_tracking_and_analysis'
            and state['active'] is None and state['protocol_sha256'] == protocol_sha
            and [x['job'] for x in state['completed_tracking']] == expected,
            '513真实终态/完整顺序/实际来源未齐，不得终验')
    require(analysis['status'] == 'complete513_all_results450_new63_reference_paired_intervals'
            and analysis['protocol_sha256'] == protocol_sha and analysis['tracking_jobs'] == 513
            and analysis['new_representation_tracking_jobs'] == 450 and analysis['added_reference_tracking_jobs'] == 63,
            '完整分析未完成，不把started或存活当完成')


def processes_absent(records):
    """完整文件名匹配包括launcher命令；verify自身或诊断长名称不误报。"""
    names = (r'pose_velocity_tracking_(?:control|jobs|analysis)', r'pose_velocity_learning_(?:train|control)',
             r'validate_pose_velocity_learning_numeric', r'v10_(?:train|training_control|tracking_control)',
             r'substitution_C_(?:train|control)', r'substitution_validation_predictions',
             r'substitution_tracking_(?:control|jobs|analysis)')
    pattern = re.compile(r'(?:^|[\\/\s"\x27])(?:' + '|'.join(names) + r')[.]py(?=$|[\s"\x27])', re.I)
    blocked = [p for p in records if (p.get('Name') or '').lower().startswith('unrealeditor')
               or pattern.search(p.get('CommandLine') or '')]
    require(not blocked, '相关controller/jobs/launcher/训练/UE尚未实际退出：' + canonical(blocked))
    return dict(producer_processes_absent=True, process_snapshot_entries=len(records), exact_script_name_match=True)


def process_snapshot():
    command = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
               "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], check=True,
        capture_output=True, text=True, encoding='utf-8', errors='strict')
    values = json.loads(result.stdout) if result.stdout.strip() else []
    return [values] if isinstance(values, dict) else values


def verify_interval(value, deltas, matches):
    """独立重算2/3/7场t、固定bootstrap和逐场留一；fold/seed从不当比赛。"""
    import numpy as np
    from scipy.stats import t
    matches = tuple(matches); n = len(matches)
    require(n >= 2 and len(set(matches)) == n and set(deltas) == set(matches), '区间比赛单位缺失/重复')
    x = [deltas[s] for s in matches]
    require(all(type(v) in (float, int) and math.isfinite(v) for v in x), '比赛均差非有限')
    avg, sd = mean(x), stdev(x)
    half = float(t.ppf(.975, n-1)) * sd / math.sqrt(n)
    require(type(value['n_independent_matches']) is int and value['n_independent_matches'] == n
            and value['margin'] is None and value['formal_equivalence_or_noninferiority_test'] is False
            and set(value['match_deltas_pp']) == set(matches) and set(value['leave_one_match_out_mean']) == set(matches)
            and len(value['Student_t_95CI']) == len(value['percentile_match_bootstrap_95CI']) == 2,
            '比赛N/区间/原无性能界限约束改变')
    require(close(value['mean_delta_pp'], avg) and close(value['match_sample_SD_pp'], sd)
            and all(close(a, b) for a, b in zip(value['Student_t_95CI'], [avg-half, avg+half])), '均差/Student t区间不符')
    array = np.asarray(x, dtype=float)
    draws = np.random.default_rng(20261027).integers(0, n, size=(10000, n))
    limits = np.quantile(array[draws].mean(axis=1), [.025, .975])
    require(all(close(a, float(b)) for a, b in zip(value['percentile_match_bootstrap_95CI'], limits))
            and all(close(value['match_deltas_pp'][s], deltas[s]) for s in matches)
            and all(close(value['leave_one_match_out_mean'][s], mean(x[:i]+x[i+1:])) for i, s in enumerate(matches)),
            '固定10000次bootstrap/比赛均差/逐场留一不符')


def verify_gap_interval(value, deltas, matches):
    """零事件场保留null；不足两场不伪造区间。"""
    available = {s: deltas[s] for s in matches if deltas[s] is not None}
    absent = [s for s in matches if deltas[s] is None]
    require(value['zero_event_matches_retained_null'] == absent
            and value['outcome'] == 'all_registered_trusted_gap_recovery_rate_difference_pp_not_physical_occlusion',
            '零事件场被删/填零或把gap冒充物理遮挡')
    if len(available) >= 2:
        verify_interval(value, available, tuple(available))
    else:
        require(value['status'] == 'fewer_than_two_matches_with_registered_events_no_interval'
                and value['n_independent_matches'] == len(available) and value['match_deltas_pp'] == available
                and (value['mean_delta_pp'] is None if not available else close(value['mean_delta_pp'], mean(available.values())))
                and value['Student_t_95CI'] is None and value['percentile_match_bootstrap_95CI'] is None
                and value['leave_one_match_out_mean'] is None and value['margin'] is None
                and value['formal_equivalence_or_noninferiority_test'] is False, '无事件/单场必须null区间，不能伪造精度')


def recovery(overall, denominator):
    total, success, rate = (overall[k] for k in ('total_events', 'same_prediction_ID_recovered', 'recovery_rate'))
    require(type(total) is type(success) is int and total == denominator and 0 <= success <= total, '原全gap事件分母/成功数不同')
    require((rate is None and success == 0) if not total else close(rate, success/total), 'gap恢复率或零事件null不同')
    return overall


def report_metrics(report, sequence):
    """只解析已生成的TrackEval数值，不运行TrackEval。"""
    metrics = report['summary'][sequence]['metrics_percent']
    require(all(type(metrics[k]) in (int, float) and math.isfinite(metrics[k]) for k in METRICS), '全部原指标必须有限')
    if 'metrics_percent' in report:
        require(all(close(metrics[k], report['metrics_percent'][k]) for k in METRICS), '顶层与序列指标不同')
    return {k: metrics[k] for k in METRICS}


def read_csv(path, fields):
    with physical(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == list(fields), 'CSV列名/顺序/重复列与完整合同不同：' + str(path))
        result = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in result), 'CSV行截断或额外列')
    return result


def compare_csv(rows, expected, identity):
    """按完整身份核每格原值，不能只核行数或忽略负差值。"""
    index = {}
    for row in rows:
        key = tuple(row[k] for k in identity)
        require(key not in index, 'CSV重复身份')
        index[key] = row
    require(set(index) == set(expected), 'CSV缺项/多项/错误模型或配对')
    for key, values in expected.items():
        row = index[key]
        require(set(row) == set(values), 'CSV字段集合不同')
        for name, value in values.items():
            actual = row[name]
            if type(value) in (float, int):
                require(close(float(actual), value), 'CSV实际数值/负结果被改写：' + name)
            else:
                require(actual == ('' if value is None else str(value)), 'CSV来源/分组/空值不同：' + name)


def mot_counts(path, frames):
    counts = [0]*frames; seen = set()
    for line in physical(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        values = line.split(',')
        require(len(values) == 10, '实际MOT列数改变')
        frame, identity = int(values[0]), int(values[1]); numbers = list(map(float, values[2:7]))
        require(1 <= frame <= frames and identity > 0 and (frame, identity) not in seen
                and all(math.isfinite(v) for v in numbers) and min(numbers[2:4]) > 0, 'MOT帧/身份/框无效或重复')
        seen.add((frame, identity)); counts[frame-1] += 1
    return counts


def load_runtime(cfg):
    bundle = physical(cfg['bundle']); require(bundle.parent == R/'code', '必须原冻结追踪bundle')
    for item in read(checked(cfg['bundle_manifest']))['files']:
        require(sha(bundle/item['path']) == item['sha256'], '原冻结追踪源码改变')
    sys.path.insert(0, str(bundle/'tools/research_ops'))
    spec = importlib.util.spec_from_file_location('pose_velocity_tracking_runtime', bundle/'tools/research_ops/pose_velocity_tracking_runtime.py')
    runtime = importlib.util.module_from_spec(spec); sys.modules[spec.name] = runtime; spec.loader.exec_module(runtime)
    return runtime


def registered_counts(cfg):
    totals = {}; gt_rows = {}
    for key, count in (('old_five', 1353), ('seven', 2337)):
        binding = cfg['registries'][key]; public = read(checked(binding['receipt']))
        registry = read(checked(binding['registry']))
        counts = Counter(event['sequence'] for event in registry['events'])
        require(public['contains_GT_coordinates'] is False and public['tracking_results_read'] is False
                and public['registry'] == binding['registry'] and public['event_count'] == len(registry['events']) == count
                and public['sources'] == registry['sources'] and not set(totals) & set(public['sources']), '原全事件ledger/公共receipt不符')
        require(public['sequence_event_counts'] == {s: counts[s] for s in public['sources']}, '全事件场分母不符')
        totals.update(public['sequence_event_counts']); gt_rows.update(public['GT_row_counts'])
    require(set(totals) == set(gt_rows) == set(cfg['sources']) and sum(totals.values()) == 3690, '12场3690事件/GT分母不齐')
    return totals, gt_rows


def verify_report(report, job, cfg, totals, gt_rows):
    seq = job['sequence']; frames = cfg['sources'][seq]['frames']
    require(report['status'] == 'complete' and report['job'] == job and report['DO_PREPROC'] is False
            and report['predictions_GT_filtered'] is False
            and report.get('GT_ID0_original', report.get('GT_identity0_preserved')) is True
            and report['test_read'] is False and report['GT_rows'] == gt_rows[seq], '评价GT/ID0/保留预测边界不同')
    registry = cfg['registries']['old_five' if seq in set(OLD)|set(EXTERNAL) else 'seven']['registry']
    # 原v10收据仅记registry_sha256；新513与原ABC收据保存完整ref，保持原字节解释。
    require(report['registry'] == registry if 'registry' in report else report['registry_sha256'] == registry['sha256'],
            '原结果前gap来源被替换')
    overall = recovery(report['recovery']['overall'], totals[seq])
    metrics = report_metrics(report, seq)
    require(set(report['raw_results']) == {seq, 'COMBINED_SEQ'}, 'TrackEval序列/COMBINED范围不同')
    for name, classes in report['raw_results'].items():
        value = classes['pedestrian']; count = value['Count']
        require(count['GT_Dets'] == gt_rows[seq] and (count.get('Frames', frames) == frames), 'TrackEval原GT行数/帧数不同')
        if name == seq:
            require(count['Frames'] == frames, '单序列缺实际帧数')
        raw = {k: mean(value['HOTA'][k]) if isinstance(value['HOTA'][k], list) else float(value['HOTA'][k]) for k in ('HOTA', 'AssA', 'DetA')}
        raw.update(IDF1=float(value['Identity']['IDF1']), MOTA=float(value['CLEAR']['MOTA']))
        require(all(close(100*raw[k], report['summary'][name]['metrics_percent'][k]) for k in METRICS), '摘要不是原TrackEval数值')
    return metrics, overall


def actual_results(cfg, state, control, protocol_sha, totals, gt_rows):
    results = []
    for entry in state['completed_tracking']:
        job = entry['job']; seq = job['sequence']; folder = control/'runs'/job['job_id']
        tr_path = folder/'tracking/receipt.json'; report_path = folder/'metric/report.json'
        tracking, report = read(tr_path), read(report_path)
        require(sha(report_path) == entry['report_sha256'] and tracking['schema'] == 'bounded_velocity513_free_tracking_v1'
                and report['schema'] == 'bounded_velocity513_trackeval_gap_v1'
                and tracking['status'] == 'complete' and tracking['job'] == report['job'] == job
                and tracking['protocol_sha256'] == report['protocol_sha256'] == protocol_sha
                and report['tracking_receipt_sha256'] == sha(tr_path)
                and tracking['cache'] == tracking['source_cache'] == report['source_cache'] == cfg['sources'][seq]['cache']
                and tracking['evaluation_GT_annotations_loaded'] is False and tracking['GT_used_for_tracking'] is False
                and tracking['inference_shape_shuffle'] is False and tracking['GPU_used'] is False and tracking['test_read'] is False
                and tracking['pose_enabled'] is job['pose_enabled'], '实际追踪/模型/缓存/自然Pose或GT边界不同')
        frames = cfg['sources'][seq]['frames']; mot = folder/'tracking/data'/(seq+'.txt')
        counts = mot_counts(mot, frames)
        require(sha(mot) == tracking['mot_sha256'] and tracking['frames'] == report['frames'] == frames
                and tracking['frame_counts'] == counts and tracking['tracked_rows'] == sum(counts), '实际MOT/帧/全部输出计数不同')
        for value in report['raw_results'].values():
            require(value['pedestrian']['Count']['Dets'] == sum(counts), 'TrackEval过滤/丢失预测')
        audit, ast = tracking['input_adapter_audit'], tracking['scope_adapter']
        binding = tracking['binding']
        require(binding['fold'] == job['fold'] and binding['seed'] == job['seed'], '实际模型fold/seed不同')
        if job['kind'] == 'new':
            require(binding['group'] == job['group'] and binding['protocol_sha256'] == cfg['learning_protocol']['sha256']
                    and tracking['pose_off'] == 'same195_input_only_final_quality_gate_zero_own_motion_base'
                    and ast['original_AST_sha256'] == ast['reverse_restored_AST_sha256']
                    and ast['tracker_numeric_AST_unchanged_outside_scope_and_input'] is True
                    and audit['input_kind'] == 'bounded_velocity_pair' and audit['all_finite'] is True
                    and audit['pose_off_final_gate_zero'] is True
                    and audit['feature_calls'] == audit['adapter_transform_pair_calls'], '新模型独立adapter/自身base关闭路径不同')
            require((audit['observed_feature_dims'] == [195] and audit['actual_feature_checks_performed'] is True)
                    if audit['feature_calls'] else (audit['observed_feature_dims'] == [] and audit['actual_feature_checks_performed'] is False),
                    '实际195维适配调用证据不同')
        else:
            require(binding['method'] == 'motion_residual' and binding['pool'] == 'balanced'
                    and tracking['pose_off'] == 'not_applicable_original_motion_residual_has_no_Pose_branch'
                    and audit['input_kind'] == 'original_motion_residual_raw' and audit['pose_off_final_gate_zero'] is None
                    and audit['feature_calls'] == audit['adapter_transform_pair_calls'] == 0
                    and audit['actual_feature_checks_performed'] is False, '旧同容量参考不能伪装新gate关闭模型')
        metrics, overall = verify_report(report, job, cfg, totals, gt_rows)
        results.append(dict(job=job, metrics=metrics, recovery=overall, report=ref(report_path), source_origin='actual_new_tracking'))
    return results


def historical_references(cfg, totals, gt_rows):
    result = []
    require(set(cfg['reference_reports']) == set(BASELINES), '三类历史来源不可遗漏')
    for baseline, expected_count, method in zip(BASELINES, (90, 90, 27), ('gated', 'motion', 'motion_residual')):
        entries = cfg['reference_reports'][baseline]; require(len(entries) == expected_count, '历史参照数90/90/27不符')
        for entry in entries:
            report = read(checked(entry['report'])); job = entry['job']; seq = job['sequence']
            require(entry['group'] == baseline and report['job'] == job and job['method'] == method, '历史标签/原模型method不同')
            if report['protocol_sha256'] == cfg['source_tracking_config']['sha256']:
                require(job['kind'] == 'new_RS' and job['pool'] == 'balanced' and seq in set(OLD)|set(EXTERNAL), '旧五场只能原balanced RS')
            else:
                require(report['protocol_sha256'] == cfg['source_seven_tracking_config']['sha256']
                        and baseline != 'same_capacity_motion_RS' and job['kind'] == 'learned'
                        and job['group'] == 'B' and seq in SEVEN, '七场只能原ABC B组，不得伪造同容量历史')
            metrics, overall = verify_report(report, job, cfg, totals, gt_rows)
            require(all(close(metrics[k], entry['metrics'][k]) for k in METRICS), '冻结历史指标不同于原报告')
            result.append(dict(group=baseline, job=job, metrics=metrics, recovery=overall,
                report=entry['report'], source_origin='historical_readonly_new_updates0'))
    return result


def expected_pairs(actual, historical, panels):
    require(set(panels) == set(PANELS) and set(panels['original_heldout']) == set(OLD)
            and set(panels['old_external']) == set(EXTERNAL) and set(panels['seven_observed']) == set(SEVEN)
            and [len(panels[p]) for p in PANELS] == [3, 2, 7], '三个比赛面板不能混并/换名')
    new = {}; references = {}
    for record in actual:
        j = record['job']
        if j['kind'] == 'new':
            key = (j['group'], j['pose_enabled'], j['fold'], j['seed'], j['sequence'])
            require(key not in new, '实际新模型重复'); new[key] = record
        else:
            record = dict(record, group='same_capacity_motion_RS')
            key = (record['group'], j['fold'], j['seed'], j['sequence'])
            require(key not in references, '补充参考重复'); references[key] = record
    # 保留与分析器相同的来源顺序，但配对数值由终验器独立构造。
    ordered_refs = list(historical) + [r for r in references.values()]
    references = {}
    for record in ordered_refs:
        j = record['job']; key = (record['group'], j['fold'], j['seed'], j['sequence'])
        require(key not in references, '历史与新参考重复'); references[key] = record
    units = [(f, s, seq) for f in FOLDS for s in SEEDS for seq in
             [next(m for m, fold in OLD.items() if fold == f)] + list(EXTERNAL) + list(SEVEN)]
    require(len(new) == 450 and len(references) == 270 and set(references) == {
        (baseline, f, s, seq) for baseline in BASELINES for f, s, seq in units}, '完整270参考身份不齐')
    pairs = []
    panel = {s: p for p in PANELS for s in panels[p]}
    def add(name, f, s, seq, target, reference):
        pairs.append(dict(comparison=name, panel=panel[seq], match=seq, fold=f, seed=s,
            target=target['job']['job_id'], reference=reference['job']['job_id'], t=target, r=reference))
    for f, s, seq in units:
        for name, t, r in CONTRASTS:
            add(name, f, s, seq, new[t[0], t[1], f, s, seq], new[r[0], r[1], f, s, seq])
        for baseline in BASELINES:
            add('T_RS_on_minus_'+baseline, f, s, seq, new['T_RS', True, f, s, seq], references[baseline, f, s, seq])
    require(len(pairs) == 720, '八族720配对不齐')
    return pairs, ordered_refs


def verify_csvs(analysis, report, actual, refs, pairs):
    raw_fields = ['job_id', 'kind', 'group', 'fold', 'seed', 'pose_enabled', 'sequence', *METRICS,
                  'gap_events', 'recovery_rate', 'report_path', 'report_sha256']
    base_fields = ['baseline', 'job_id', 'fold', 'seed', 'sequence', *METRICS, 'source_origin', 'report_path', 'report_sha256']
    pair_fields = ['comparison', 'panel', 'match', 'fold', 'seed', 'target', 'reference', *METRICS]
    gap_fields = ['comparison', 'panel', 'match', 'fold', 'seed', 'target', 'reference',
        'target_event_denominator', 'target_success', 'target_recovery_rate', 'reference_event_denominator',
        'reference_success', 'reference_recovery_rate', 'delta_recovery_rate_pp', 'target_report_path',
        'target_report_sha256', 'reference_report_path', 'reference_report_sha256']
    raw, baseline, numeric, gaps = {}, {}, {}, {}
    for record in actual:
        j = record['job']; g = record['recovery']
        raw[(j['job_id'],)] = dict({k: j[k] for k in raw_fields[:7]}, **record['metrics'],
            gap_events=g['total_events'], recovery_rate=g['recovery_rate'],
            report_path=record['report']['path'], report_sha256=record['report']['sha256'])
    for record in refs:
        j = record['job']
        baseline[(record['group'], j['fold'], str(j['seed']), j['sequence'])] = dict(baseline=record['group'],
            **{k: j[k] for k in ('job_id', 'fold', 'seed', 'sequence')}, **record['metrics'],
            source_origin=record['source_origin'], report_path=record['report']['path'], report_sha256=record['report']['sha256'])
    for pair in pairs:
        row = {k: pair[k] for k in pair_fields[:7]}; key = tuple(str(row[k]) for k in ('comparison', 'match', 'fold', 'seed'))
        t, r = pair['t'], pair['r']; a, b = t['recovery'], r['recovery']
        require(a['total_events'] == b['total_events'], '同场配对原事件分母不同')
        numeric[key] = dict(row, **{k: t['metrics'][k]-r['metrics'][k] for k in METRICS})
        gaps[key] = dict(row, target_event_denominator=a['total_events'], target_success=a['same_prediction_ID_recovered'],
            target_recovery_rate=a['recovery_rate'], reference_event_denominator=b['total_events'],
            reference_success=b['same_prediction_ID_recovered'], reference_recovery_rate=b['recovery_rate'],
            delta_recovery_rate_pp=100*(a['recovery_rate']-b['recovery_rate']) if a['total_events'] else None,
            target_report_path=t['report']['path'], target_report_sha256=t['report']['sha256'],
            reference_report_path=r['report']['path'], reference_report_sha256=r['report']['sha256'])
    for filename, field, expected, identity, binding in (
        ('all_results.csv', raw_fields, raw, ('job_id',), 'all_results_csv'),
        ('all_baseline_references.csv', base_fields, baseline, ('baseline', 'fold', 'seed', 'sequence'), 'all_baseline_references_csv'),
        ('all_paired_cells.csv', pair_fields, numeric, ('comparison', 'match', 'fold', 'seed'), 'all_paired_cells_csv'),
        ('all_paired_gaps.csv', gap_fields, gaps, ('comparison', 'match', 'fold', 'seed'), 'all_paired_gaps_csv')):
        require(checked(report[binding]) == analysis/filename, '分析CSV不是实际输出')
        compare_csv(read_csv(analysis/filename, field), expected, identity)
    require([len(x) for x in (raw, baseline, numeric, gaps)] == [513, 270, 720, 720], '四份完整CSV矩阵不足')
    return numeric, gaps


def verify_summaries(report, numeric, gaps, panels):
    names = {r['comparison'] for r in numeric.values()}
    require(len(names) == 8 and set(report['comparisons']) == set(report['gap_comparisons']) == names,
            '八个完整比较族不能省略或挑选')
    for name in names:
        require(set(report['comparisons'][name]) == set(report['gap_comparisons'][name]) == set(PANELS), '三个面板必须分别报告')
        for panel in PANELS:
            matches = panels[panel]
            selected = [r for r in numeric.values() if r['comparison'] == name and r['panel'] == panel]
            require(len(selected) == (9 if panel == 'original_heldout' else 18 if panel == 'old_external' else 63)
                    and set(report['comparisons'][name][panel]) == set(METRICS), '面板完整匹配训练单元/五指标缺失')
            for metric in METRICS:
                deltas = {m: mean(r[metric] for r in selected if r['match'] == m) for m in matches}
                verify_interval(report['comparisons'][name][panel][metric], deltas, matches)
            values = {}
            for m in matches:
                cells = [r['delta_recovery_rate_pp'] for r in gaps.values() if r['comparison'] == name and r['match'] == m]
                require(len(cells) == (3 if panel == 'original_heldout' else 9)
                        and (all(v is None for v in cells) or all(v is not None for v in cells)), '同场gap缺单元或伪造不同分母')
                values[m] = mean(cells) if cells[0] is not None else None
            verify_gap_interval(report['gap_comparisons'][name][panel], values, matches)


def execute(config, control, output):
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    config, control, output = (physical(p) for p in (config, control, output))
    require(EXP in control.parents and EXP in output.parents and not output.exists(), '终验控制器/输出越界或已有partial')
    cfg, state, report = read(config), read(control/'driver_state.json'), read(control/'analysis_a01/report.json')
    protocol_sha = sha(config); terminal_gate(cfg, state, report, protocol_sha)
    exit_proof = processes_absent(process_snapshot())  # 先实际终态与退出，后读取原来源/结果。
    rt = load_runtime(cfg); validated, _, _ = rt.validate_config(config)
    require(validated == cfg and state['analysis_report'] == ref(control/'analysis_a01/report.json'), '实际分析完成引用不同')
    totals, gt_rows = registered_counts(cfg)
    actual = actual_results(cfg, state, control, protocol_sha, totals, gt_rows)
    historical = historical_references(cfg, totals, gt_rows)
    pairs, references = expected_pairs(actual, historical, cfg['panels'])
    require(report['panels'] == cfg['panels'] and report['analysis_plan'] == cfg['analysis_plan']
            and report['primary_metric'] == 'AssA' and report['comparison_families'] == 8
            and report['paired_cells'] == report['paired_gap_cells'] == 720 and report['intervals'] == 120
            and report['separate_gap_interval_descriptions'] == 24 and report['historical_reference_reports_readonly'] == 207
            and report['new_training_updates_in_tracking'] == 0 and report['formal_equivalence_or_noninferiority'] is False
            and report['performance_margin'] is None and report['test_read'] is False
            and report['all_seeds_folds_unknowns_and_negative_results_retained'] is True
            and report['all_actual_reports'] == [r['report'] for r in actual]
            and report['all_reference_reports'] == [r['report'] for r in references], '分析身份/完整来源/无性能界限约束不同')
    numeric, gaps = verify_csvs(control/'analysis_a01', report, actual, references, pairs)
    verify_summaries(report, numeric, gaps, cfg['panels'])
    # 终验期间也不能另起相关生产者；只读核验不重跑模型或TrackEval。
    processes_absent(process_snapshot())
    result = dict(status=STATUS, config=ref(config), control_state=ref(control/'driver_state.json'),
        analysis=ref(control/'analysis_a01/report.json'), jobs=513, new_representation_tracking_jobs=450,
        added_reference_tracking_jobs=63, historical_reference_reports=207, baseline_csv_rows=270,
        paired_cells=720, paired_gap_cells=720, descriptive_metric_intervals=120, separate_gap_descriptions=24,
        registered_gap_events=3690, panel_independent_matches=dict(original_heldout=3, old_external=2, seven_observed=7),
        process_exit_verification=exit_proof, producer_processes_absent=True, all_negative_results_retained=True,
        new_optimizer_updates=0, models_or_media_recomputed=False, TrackEval_recomputed=False,
        numeric_serialization_tolerance_pp=TOLERANCE_PP, tolerance_is_not_performance_margin=True,
        formal_equivalence_or_noninferiority=False, test_read=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'control', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    value = execute(args.config, args.control, args.output)
    print(canonical({k: value[k] for k in ('status', 'jobs', 'paired_cells', 'paired_gap_cells', 'descriptive_metric_intervals')}))
