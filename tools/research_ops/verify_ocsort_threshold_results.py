"""OC .6→.25单因素独立终验：只核新输出、旧来源与配对区间，不重跑算法。"""
import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
from statistics import mean
import stat
import subprocess
import sys
import traceback

R = Path('D:/projects/FutsalMOT_Research'); EXP = R/'pose/ocsort_threshold025_a01'
DONE = 'complete12_OC025_single_factor_tracking_metrics_and_paired_analysis'
STATUS = 'complete12_OC025_single_factor_outputs48_pairs60_metric12_gap_intervals_and_exit_verified'
PARAMETERS = dict(det_thresh=.25, max_age=30, min_hits=3, iou_threshold=.3, delta_t=3, asso_func='iou', inertia=.2, use_byte=False)
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
PANELS = ('original_heldout', 'old_external', 'seven_observed')
BASELINES = ('OC06', 'strong_motion_RS', 'T_RS', 'PT_bbox')
PAIR_ORDER = ('OC06', 'PT_bbox', 'strong_motion_RS', 'T_RS')


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(path):
    path = Path(path); require(path.is_absolute(), '独立终验必须绝对路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts), '仅研究物理根且最终测试封存')
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            info = p.lstat(); require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): digest.update(block)
    return digest.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path']); require(path.is_file() and sha(path) == value['sha256'], '来源或结果SHA变化：'+str(path)); return path


def module(name, reference):
    spec = importlib.util.spec_from_file_location(name, checked(reference)); value = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try: sys.dont_write_bytecode = True; spec.loader.exec_module(value)
    finally: sys.dont_write_bytecode = previous
    return value


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream: stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def one_factor(old, new):
    require(old == dict(PARAMETERS, det_thresh=.6) and new == PARAMETERS
        and {k: (old[k], new[k]) for k in old if old[k] != new[k]} == {'det_thresh': (.6, .25)},
        '只能改变原core det_thresh .6→.25，含byteFalse的其他参数完全不变')


def source_contract(old, new):
    one_factor(old['parameters'], new['parameters'])
    for key in ('sources', 'panels', 'registries', 'official_manifest', 'dependency_manifest', 'worker_profile',
        'protected_GT_paths', 'sequence_order', 'gate_sequences', 'source_velocity_protocol', 'source_velocity_analysis',
        'old_five_analysis', 'ABC_analysis', 'interval_source', 'expected_GT_rows', 'expected_ID0_present'):
        require(new[key] == old[key], '除阈值外来源/曝光/评价/数值政策改变：'+key)
    require(len(new['sources']) == 12 and sum(v['frames'] for v in new['sources'].values()) == 8165, '原12/8165完整范围改变')


def copied_function_contract(old_cfg, cfg):
    def entry(config, name):
        files = read(checked(config['bundle_manifest']))['files']; found = [v for v in files if v['path'] == 'tools/research_ops/'+name]
        require(len(found) == 1, '必要冻结源码清单缺失：'+name)
        value = dict(path=str(Path(config['bundle'])/found[0]['path']), sha256=found[0]['sha256']); checked(value); return value
    original = entry(old_cfg, 'ocsort_cached_runtime.py'); admission = entry(old_cfg, 'ocsort_cached_admission.py')
    current = entry(cfg, 'ocsort_threshold_runtime.py')
    def function(reference):
        tree = ast.parse(checked(reference).read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_track_frames_impl']
        require(len(nodes) == 1, '唯一原始数值函数缺失'); return ast.dump(nodes[0], include_attributes=False)
    a, b = function(original), function(current); require(a == b, '独立namespace外原适配函数AST必须逐值相同')
    return dict(source_runtime=original, source_admission=admission, source_manifest=old_cfg['bundle_manifest'],
        changed_parameters=dict(det_thresh=dict(before=.6, after=.25)), copied_function='_track_frames_impl',
        copied_function_AST_identical=True, copied_function_AST_sha256=hashlib.sha256(b.encode()).hexdigest(),
        original_module_globals_modified=False, original_source_bytes_modified=False, old_official_default_det_thresh=.6,
        effective_det_thresh=.25, official_default_claim=False, upstream_association_or_Kalman_modified=False)


def backend_contract(backend, cfg, contract):
    require(backend['manifest'] == cfg['official_manifest'] and backend['effective_parameters'] == PARAMETERS
        and backend['parameter_override'] == 'predeclared_single_factor_det_thresh_0.6_to_0.25_not_official_default'
        and backend['single_factor_override'] == dict(parameter='det_thresh', before=.6, after=.25, predeclared=True, official_default=False)
        and backend['single_factor_contract'] == contract, '实际backend不是原core的事前单参数覆盖')
    require(backend['det_thresh_source'] == 'official_CLI_track_thresh_default_0.6'
        and backend['commit'] == '8462e7e729a93ccd3bd995c0a79a890336cb3a0b'
        and backend['numerical_source_modified'] is False and backend['actual_assignment_backend'] == 'lap.lapjv'
        and backend['scipy_assignment_fallback_allowed'] is False and backend['no_demo_min_area_or_aspect_filter'] is True
        and backend['full_demo_pipeline_reproduction'] is False and backend['paper2023_byte_reproduction'] is False
        and backend['native_Kalman_precision'] == 'original_float64_matrices_and_operations_not_cast_to_FP32',
        '原官方core/默认来源/精度/输出政策改变或冒称官方默认')


def check_tracking(body, cfg, seq, protocol_sha, contract, base):
    """新.25显式期望；只复用原native→MOT纯核查，不改任何旧module globals。"""
    source = cfg['sources'][seq]; a = body['audit']; backend = body['official_source']
    require(body['schema'] == 'official_ocsort_cached12_tracking_v1' and body['status'] == 'complete'
        and body['sequence'] == seq and body['protocol_sha256'] == protocol_sha and body['source_cache'] == source['cache']
        and body['frames'] == source['frames'] and body['parameters'] == PARAMETERS
        and body['new_optimizer_updates'] == 0 and body['test_read'] is False, '新实际追踪参数/完整缓存不同')
    require(all(body[k] is False for k in ('evaluation_GT_annotations_loaded', 'GT_used_for_tracking', 'tracker_input_has_Pose')), '模型/GT混入原检测core')
    guard = body['GT_guard']; require(guard['python_open_audit_installed'] is True and guard['blocked_open_attempts'] == 0
        and guard['GT_annotations_opened'] is False and guard['protected_paths'] == len(set(cfg['protected_GT_paths'])), '实际track GT隔离不完整')
    backend_contract(backend, cfg, contract)
    require(backend['loaded_algorithm_files'] == base.ALGORITHM and backend['constructor_arguments'] == list(PARAMETERS)
        and backend['constructor_defaults'] == {k: v for k, v in PARAMETERS.items() if k != 'det_thresh'}
        and backend['input'] == 'new_numpy_float32_N5_xyxy_score' and backend['update_entry'] == 'OCSort.update_not_update_public'
        and backend['score_export'] == 'MOT_constant_1_not_detection_confidence', '原官方三算法/输入/原ID输出语义不同')
    for value in list(backend['dependency_sources'].values())+[backend['assignment_binary_source']]: base.checked_dependency(value)
    require(all(a[k] is True for k in ('all_raw_detections_passed_to_core', 'img_info_equals_img_size', 'original_IDs_preserved', 'static_kalman_matrices_unchanged'))
        and all(a[k] is False for k in ('outside_core_filtering', 'native_output_score_available', 'MOT_score_is_detection_confidence',
            'posthoc_ID_renumbering', 'model_GT_or_Pose_input', 'GT_read', 'Pose_fields_read', 'GPU_used', 'test_read'))
        and a['update_calls'] == source['frames'] and a['input_dtype'] == 'float32'
        and a['input_columns'] == 'xyxy+score_N5_no_class_multiplication' and a['scale'] == 1
        and a['MOT_score_constant'] == 1 and a['ID_before'] == 0 and a['new_optimizer_updates'] == 0, '单因素之外调用/输出/精度政策不同')
    raw = a['raw_detection_counts']; require(len(raw) == source['frames'] and all(type(v) is int and v >= 0 for v in raw)
        and sum(raw) == a['raw_detections'] == source['counts']['raw_detections']
        and a['empty_input_frames'] == sum(v == 0 for v in raw) and re.fullmatch('[0-9a-f]{64}', a['input_chain_sha256']), '全部原检测/空帧/输入链分母不同')
    require(body['mot_sha256'] == body['mot']['sha256'], 'MOT绑定不同')
    result = base.native_to_mot(checked(body['native_outputs']), checked(body['mot']), source['frames'], body['frame_counts'])
    require(result['tracked_rows'] == body['tracked_rows'] == sum(body['frame_counts'])
        and a['ID_counter_after'] >= result['maximum_native_ID'], '新025完整原ID/输出数不同')
    return result


def check_admission(state, cfg, config, contract):
    path = physical(cfg['admission_receipt_path']); require(state['admission'] == ref(path), '真实新准入未绑定')
    proof = read(path); admitted = read(checked(proof['config']))
    require(proof['schema'] == 'official_ocsort_threshold025_admission_receipt_v1'
        and proof['status'] == 'complete_official_threshold025_literal96_ABA_two_spawn_exact_GT_guard_and_exit_verified'
        and admitted['formal_protocol'] == ref(config) and admitted['parameters'] == cfg['parameters']
        and admitted['official_manifest'] == cfg['official_manifest'] and admitted['dependency_manifest'] == cfg['dependency_manifest']
        and admitted['sources'] == cfg['sources'] and proof['parameters'] == admitted['admission_parameters']
        and admitted['runtime'] == ref(Path(cfg['bundle'])/'tools/research_ops/ocsort_threshold_runtime.py')
        and admitted['admission_source'] == ref(Path(cfg['bundle'])/'tools/research_ops/ocsort_threshold_admission.py')
        and admitted['source_runtime'] == contract['source_runtime'] and admitted['source_admission'] == contract['source_admission']
        and proof['effective_parameters'] == PARAMETERS and proof['single_factor_contract'] == contract
        and proof['unique_source_frames'] == 96 and proof['all_workers_joined_exited'] is True
        and proof['optimizer_updates'] == proof['TrackEval_runs'] == 0 and proof['test_read'] is False, '新.25实际96帧/来源/单因素准入未完整')
    require(proof['source_prefixes'] == {k: cfg['sources'][s]['cache'] for k, s in [('A', 'SNMOT-060'), ('B', 'v_2QhNRucNC7E_c017')]}
        and proof['literal_internal_Kalman_dtypes'] == dict(A=['float64'], B=['float64'])
        and proof['single_factor_parameters_verified'] is True and proof['threshold025_boundary']['passed'] is True
        and proof['old06_fixture_exact']['passed'] is True
        and proof['old06_fixture_exact']['scope'] == 'original16_frame_fixture_only_not12_clip_rerun'
        and proof['old06_fixture_exact']['parameters_unchanged'] is True and proof['old06_fixture_exact']['source_bytes_unchanged'] is True,
        '实际固定前缀/FP64/严格阈值边界/旧16帧回归证据不同')
    backend_contract(proof['official_backend'], cfg, contract)
    fixture = proof['artificial_fixture']
    require(all(fixture[k] is True for k in ('float32_equal025_excluded', 'float32_predecessor025_excluded',
        'float32_successor025_accepted', 'score_equal06_accepted_under025', 'GT_Pose_pollution_whitelist_only',
        'source_fixture_unchanged', 'old06_parameters_unchanged', 'old06_source_bytes_unchanged', 'old06_regression_is_fixture_only_not12_clip_rerun'))
        and fixture['single_factor_contract'] == contract, 'FP32严格>.25边界或旧.6未改回归未实证')
    comparisons = list(proof['literal_vs_adapter'].values())+[v['comparison'] for v in proof['persistent_ABA']]+[v['comparison'] for v in proof['independent_spawn_A']]
    require(set(proof['literal_vs_adapter']) == {'A', 'B'} and len(proof['persistent_ABA']) == 3 and len(proof['independent_spawn_A']) == 2
        and len(comparisons) == 7 and all(v['original_ID_MOT_equal'] is True and v['all_frame_counts_equal'] is True
        and v['per_frame_raw_outputs_exact'] is True and v['frames'] == 48 for v in comparisons)
        and proof['parent_source_input_unchanged'] is True, 'literal/ABA/双spawn原输出逐值准入缺失')
    closures = [proof['persistent_worker']]+[v['closure'] for v in proof['independent_spawn_A']]
    require(len({v['pid'] for v in closures}) == 3 and all(v['kind'] == 'closed' and v['joined'] is True and v['exitcode'] == 0
        and v['actual_PID_absent_after_join'] is True and v['active_trackers'] == 0 for v in closures), '准入三个真实worker退出不完整')
    guards = [proof['parent_GT_guard']]+[v['GT_guard'] for v in closures]
    require(all(v['GT_Python_open_guard'] is True and v['self_test_blocked_opens'] > 0
        and v['algorithm_blocked_GT_opens'] == 0 and v['algorithm_GT_read'] is False for v in guards), '准入GT隔离自检缺失')
    return ref(path)


def paired_rows(target, old06, references, panels, base):
    require(len(target) == len(old06) == 12 and len(references) == 192, '新旧OC各12/上下文192缺失')
    new = {r['sequence']: r for r in target}; old = {r['sequence']: r for r in old06}; grouped = defaultdict(list)
    require(len(new) == len(old) == 12 and set(new) == set(old) == {s for p in PANELS for s in panels[p]}, 'OC每场一次，不复制训练seed')
    for row in references: grouped[row['baseline'], row['sequence']].append(row)
    result = []
    for baseline in PAIR_ORDER:
        for panel in PANELS:
            for seq in panels[panel]:
                a = new[seq]; group = [old[seq]] if baseline == 'OC06' else grouped[baseline, seq]
                expected = {(None, None)} if baseline in ('OC06', 'PT_bbox') else {
                    (fold, seed) for fold in ((base.OLD[seq],) if seq in base.OLD else base.FOLDS) for seed in base.SEEDS}
                require(len(group) == len(expected) and {(r.get('fold'), r.get('seed')) for r in group} == expected, '不能缺项/重复/挑训练单元')
                require(a.get('fold') is None and a.get('seed') is None, '新OC无训练foldseed')
                n, success, rate = base.gap_values(a['recovery']); gap = [base.gap_values(r['recovery']) for r in group]
                require(all(v[0] == n for v in gap), '新旧必须全部原注册gap分母')
                avg_rate = mean(v[2] for v in gap) if n else None
                result.append(dict(baseline=baseline, panel=panel, sequence=seq, OC025_evaluations=1,
                    reference_cells=len(group), reference_has_training_panel=baseline in ('strong_motion_RS', 'T_RS'),
                    delta={k: a['metrics'][k]-mean(r['metrics'][k] for r in group) for k in METRICS},
                    OC025_report=a['report'], reference_reports=[r['report'] for r in group],
                    gap=dict(total_registered_events=n, OC_success=success, OC_rate=rate,
                        reference_mean_success=mean(v[1] for v in gap), reference_mean_rate=avg_rate,
                        delta_recovery_rate_pp=100*(rate-avg_rate) if n else None)))
    require(len(result) == 48, '必须全部48比赛配对'); return result


def intervals(rows, panels, fn):
    metrics, gaps = {}, {}
    for baseline in BASELINES:
        metrics[baseline] = {}; gaps[baseline] = {}
        for panel in PANELS:
            selected = [v for v in rows if v['baseline'] == baseline and v['panel'] == panel]
            require([v['sequence'] for v in selected] == panels[panel], '3/2/7比赛等权顺序不同')
            metrics[baseline][panel] = {k: fn({v['sequence']: v['delta'][k] for v in selected}) for k in METRICS}
            values = {v['sequence']: v['gap']['delta_recovery_rate_pp'] for v in selected if v['gap']['delta_recovery_rate_pp'] is not None}
            missing = [v['sequence'] for v in selected if v['gap']['delta_recovery_rate_pp'] is None]
            description = fn(values) if len(values) >= 2 else dict(n_independent_matches=len(values), match_deltas_pp=values,
                mean_delta_pp=mean(values.values()) if values else None, Student_t_95CI=None, percentile_match_bootstrap_95CI=None,
                leave_one_match_out_mean=None, status='fewer_than_two_matches_with_events_no_interval')
            gaps[baseline][panel] = dict(description, zero_event_matches_retained_null=missing,
                outcome='all_registered_trusted_detection_gap_proxy_not_physical_occlusion')
    return metrics, gaps


def check_csv(reference, expected, base):
    with checked(reference).open(encoding='utf-8-sig', newline='') as stream: values = list(csv.DictReader(stream))
    require(len(values) == len(expected), '全部CSV行数不同，不能删除负结果')
    for a, b in zip(values, expected):
        require(set(a) == set(b), 'CSV完整字段不同')
        for key, value in b.items():
            if isinstance(value, bool): require(a[key] == str(value), 'OC无训练面板，布尔字段不同')
            elif value is None: require(a[key] == '', '零分母null不能填0')
            elif isinstance(value, (int, float)): base.same(float(a[key]), value, 'CSV.'+key)
            elif isinstance(value, (dict, list)): base.same(json.loads(a[key]), value, 'CSV.'+key)
            else: require(a[key] == value, '原来源/标识不同：'+key)


def source_records(analysis, old_cfg, previous, complete):
    values = analysis.csv_rows(previous['all_OC_results']); require(len(values) == 12 and len({v['sequence'] for v in values}) == 12, '旧OC06完整12来源缺失')
    result = []
    for row in values:
        seq = row['sequence']; reference = dict(path=row['report_path'], sha256=row['report_sha256']); body = read(checked(reference))
        require(body['protocol_sha256'] == complete['protocol']['sha256'] and body['sequence'] == seq and body['source_cache'] == old_cfg['sources'][seq]['cache']
            and body['frames'] == old_cfg['sources'][seq]['frames'] and body.get('fold') is None and body.get('seed') is None, '旧OC不能换成新阈值或复制seed')
        metrics = analysis.report_values(body, seq); require(metrics == {k: float(row[k]) for k in METRICS}, '旧OC06原CSV与实际评价不同')
        receipt = read(checked(body['tracking_receipt'])); require(receipt['parameters'] == old_cfg['parameters']
            and receipt['protocol_sha256'] == complete['protocol']['sha256'], '旧OC06必须真实.6原追踪结果')
        result.append(dict(sequence=seq, fold=None, seed=None, metrics=metrics, recovery=body['recovery']['overall'], report=reference))
    return result


def check_analysis(report, cfg, path, manifest, old_cfg, complete, base):
    require(report['schema'] == 'ocsort_threshold025_paired_analysis_v1'
        and report['status'] == 'complete12_OC025_single_threshold_all_results48_pairs60_metric12_gap_intervals'
        and report['protocol'] == ref(path) and report['old06_complete'] == cfg['old06_complete']
        and report['source_old_OC_analysis'] == cfg['source_old_OC_analysis'] and report['source_analysis'] == cfg['source_analysis']
        and report['comparison_direction'] == 'OC025_minus_reference' and report['primary_reference'] == 'OC06'
        and report['context_references'] == ['strong_motion_RS', 'T_RS', 'PT_bbox']
        and report['only_parameter_change'] == dict(name='det_thresh', old=.6, new=.25)
        and report['official_default_threshold'] is False and report['other_parameters_unchanged'] is True
        and report['use_byte'] is False and report['primary_metric'] == 'AssA' and report['panels'] == cfg['panels'], '主比较/单因素/完整分析协议不同')
    for key, value in dict(source_frames=8165, OC025_evaluations=12, OC06_evaluations=12, context_reference_cells=192,
        paired_matches=48, registered_gap_events=3690, primary_metric_interval_descriptions=15, primary_gap_interval_descriptions=3,
        context_metric_interval_descriptions=45, context_gap_interval_descriptions=9, metric_interval_descriptions=60, separate_gap_interval_descriptions=12).items():
        require(report[key] == value, '完整结果/区间计数不同：'+key)
    require(report['all_negative_results_preserved'] is True and report['formal_equivalence_or_noninferiority'] is False
        and report['performance_margin'] is None and report['new_optimizer_updates'] == 0 and report['test_read'] is False
        and all(report[k] is False for k in ('model_loaded', 'old_tracking_rerun', 'TrackEval_rerun', 'cache_or_GT_read')), '只能全部负结果保留的描述性区间')
    require(report['statistical_policy'] == dict(confidence=.95, Student_t_df='panel_match_N_minus_1', bootstrap_resamples=10000,
        bootstrap_seed=20261027, leave_one_match_out=True, multiple_comparison_adjustment=False), '事前统计策略不可更换')
    analysis = module('original_OC_inventory_pure_functions', cfg['source_analysis']); refs, inventory = analysis.inventory(old_cfg)
    old = source_records(analysis, old_cfg, read(checked(cfg['source_old_OC_analysis'])), complete)
    target = analysis.load_evaluations(path, cfg, manifest); rows = paired_rows(target, old, refs, cfg['panels'], base)
    require(report['source_inventory'] == inventory and report['all_OC025_reports'] == [r['report'] for r in target]
        and report['all_OC06_reports'] == [r['report'] for r in old] and report['all_context_reference_reports'] == [r['report'] for r in refs], '全部来源清单缺失/重复')
    def record_rows(records, contextual=False):
        result = []
        for r in records:
            n, success, rate = base.gap_values(r['recovery'])
            result.append(dict(**({k: r[k] for k in ('baseline', 'fold', 'seed')} if contextual else {}), sequence=r['sequence'],
                **r['metrics'], gap_events=n, gap_success=success, gap_rate=rate, report_path=r['report']['path'], report_sha256=r['report']['sha256']))
        return result
    check_csv(report['all_OC025_results'], record_rows(target), base); check_csv(report['all_OC06_results'], record_rows(old), base)
    check_csv(report['all_context_reference_cells'], record_rows(refs, True), base)
    def head(r): return {k: r[k] for k in ('baseline', 'panel', 'sequence', 'OC025_evaluations', 'reference_cells', 'reference_has_training_panel')}
    check_csv(report['all_paired_matches'], [dict(**head(r), **r['delta'], OC025_report=r['OC025_report'], reference_reports=r['reference_reports']) for r in rows], base)
    check_csv(report['all_paired_gaps'], [dict(**head(r), **r['gap']) for r in rows], base)
    require(report['interval_source'] == cfg['interval_source'], '区间纯函数来源不同')
    fn = module('original_threshold_descriptive_interval_function', cfg['interval_source']).effect_intervals
    metrics, gaps = intervals(rows, cfg['panels'], fn); base.same(report['metric_comparisons'], metrics); base.same(report['gap_comparisons'], gaps)
    return dict(target=12, old06=12, contextual_cells=192, paired_matches=48, metric_intervals=60, gap_descriptions=12,
        negative_metric_differences=sum(v < 0 for r in rows for v in r['delta'].values()),
        negative_gap_differences=sum(r['gap']['delta_recovery_rate_pp'] is not None and r['gap']['delta_recovery_rate_pp'] < 0 for r in rows),
        all_negative_results_reconstructed=True, old06_tracking_rerun=False)


def processes_absent(state):
    query = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='CreationUtc';e={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    answer = subprocess.run(['powershell.exe', '-NoProfile', '-Command', query], capture_output=True, text=True, encoding='utf-8', check=True)
    rows = json.loads(answer.stdout) if answer.stdout.strip() else []; rows = [rows] if isinstance(rows, dict) else rows
    blocked = blocked_processes(rows, state); require(not blocked, '真实控制器/worker/UE仍在，不kill或按旧PID猜退出：'+canonical(blocked))
    return dict(actual_CIM_checked=True, producer_processes_absent=True, historical_PID_reuse_not_rejected=True)


def blocked_processes(rows, state):
    pattern = re.compile(r'(?:^|[\\/\s\"\x27])(?:ocsort_(?:threshold|cached)_(?:control|admission)|tracking_policy_ledger_control|pose_velocity_(?:tracking_control|learning_train))[.]py(?=$|[\s\"\x27])', re.I)
    result = []; start = datetime.fromisoformat(state['created_utc'].replace('Z', '+00:00'))
    for row in rows:
        command = row.get('CommandLine') or ''; spawned = False
        if 'spawn_main' in command and re.search(r'\bparent_pid\s*=\s*'+str(state['parent_pid'])+r'\b', command):
            value = row.get('CreationUtc'); require(value, '相关spawn缺实际创建时间，不能按历史PID拒绝')
            when = datetime.fromisoformat(value.replace('Z', '+00:00')); spawned = start-timedelta(seconds=2) <= when <= datetime.now(timezone.utc)+timedelta(seconds=2)
        if (row.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(command) or spawned: result.append(row)
    return result


def verify(config, control, output):
    config, control, output = physical(config), physical(control), physical(output); cfg = read(config)
    require(EXP in output.parents and control not in output.parents and output.parent != control and not output.parent.exists(), '必须新独立attempt，不覆盖已有partial')
    require(cfg['schema'] == 'ocsort_threshold025_protocol_v1' and cfg['approved_by'] == 'root' and cfg['test_sealed'] is True
        and cfg['tracking_authorized'] is True and cfg['new_optimizer_updates'] == 0 and cfg['formal_equivalence_or_noninferiority'] is False
        and control == physical(cfg['output_root']) and EXP in control.parents
        and physical(cfg['bundle']).parent == R/'code', '新.25独立正式协议/真实输出不同')
    state = read(control/'state.json'); output.parent.mkdir(parents=True)
    write_new(output.parent/'intent.json', dict(config=ref(config), state=ref(control/'state.json'), new_optimizer_updates=0, test_read=False))
    try:
        require(state['status'] == DONE and state['protocol'] == ref(config) and not state['active']
            and state['actual_frames'] == 8165 and state['actual_clips'] == 12 and state['new_optimizer_updates'] == 0
            and state['new_detector_or_Pose_inference'] is False and state['GT_only_metric_process'] is True and state['test_read'] is False, '完整12新追踪/分析终态未齐')
        base = module('frozen_OC_verification_pure_helpers', cfg['base_verifier']); initial_exit = processes_absent(state)
        with base.no_raw_reads(cfg) as guard:
            complete = read(checked(cfg['old06_complete'])); old_cfg = read(checked(complete['protocol']))
            require(complete['status'] == 'complete_official_OCSORT_cached12_admission_tracking_metrics_intervals_and_exit_verified'
                and complete['producer_processes_absent'] is True and complete['test_read'] is False
                and complete['analysis'] == cfg['source_old_OC_analysis'], '原.6完整闭合来源不同')
            checked(complete['independent_verification']); source_contract(old_cfg, cfg)
            ledger = read(checked(cfg['ledger_complete']))
            require(ledger['status'] == 'complete12_existing_sources114_MOT_policy_ledger_independent_verification_and_exit'
                and ledger['producer_processes_absent'] is True and ledger['test_read'] is False, '事前零更新政策诊断未真正闭合')
            original_backends = {}
            previous = read(checked(cfg['source_old_OC_analysis']))
            for reference in previous['all_OC_reports']:
                metric = read(checked(reference)); prior = read(checked(metric['tracking_receipt']))
                require(prior['parameters'] == old_cfg['parameters'] and prior['protocol_sha256'] == complete['protocol']['sha256'], '旧backend必须来自真正.6原收据')
                require(metric['sequence'] not in original_backends, '旧OC backend来源重复')
                original_backends[metric['sequence']] = prior['official_source']
            require(set(original_backends) == set(cfg['sources']), '原12 backend元数据未齐')
            for item in read(checked(cfg['bundle_manifest']))['files']: require(sha(Path(cfg['bundle'])/item['path']) == item['sha256'], '新冻结bundle bytes变化')
            contract = copied_function_contract(old_cfg, cfg); admission = check_admission(state, cfg, config, contract)
            gaps, id0 = {}, {}
            for binding in cfg['registries'].values():
                public = read(checked(binding['receipt'])); require(public['contains_GT_coordinates'] is False and public['registry'] == binding['registry'], '只能原无坐标公开分母')
                gaps.update(public.get('sequence_event_counts', public.get('event_counts'))); id0.update(public.get('GT_ID0_present', {}))
            require(sum(gaps.values()) == 3690, '原全部gap分母不同')
            manifest = read(control/'evaluation_manifest.json')
            require(manifest['schema'] == 'official_ocsort_cached12_evaluation_manifest_v1' and manifest['status'] == 'complete12_official_ocsort_cached_evaluations'
                and manifest['protocol'] == ref(config) and [v['sequence'] for v in manifest['evaluations']] == cfg['sequence_order'], '新12评价完成清单不同')
            require(len(state['completed_tracking']) == len(state['completed_metrics']) == 12
                and {v['sequence'] for v in state['completed_tracking']} == {v['sequence'] for v in state['completed_metrics']} == set(cfg['sources']), '12新输出/评价缺项或重复')
            tracks, metrics, outputs, checks = {}, {}, {}, []
            declared = {v['sequence']: v['report'] for v in manifest['evaluations']}
            for item in state['completed_tracking']:
                seq = item['sequence']; p = checked(item['receipt']); require(p == control/'runs'/seq/'tracking/receipt.json', '实际tracking路径不同')
                tracks[seq] = read(p); outputs[seq] = check_tracking(tracks[seq], cfg, seq, sha(config), contract, base)
                projected = {k: v for k, v in tracks[seq]['official_source'].items() if k not in
                    ('effective_parameters', 'parameter_override', 'single_factor_override', 'single_factor_contract')}
                require(projected == original_backends[seq], '新旧实际core/分配/依赖/精度元数据必须完全相同，只有显式阈值覆盖可新增')
            for item in state['completed_metrics']:
                seq = item['sequence']; p = checked(item['report']); require(item['report'] == declared[seq] and p == control/'runs'/seq/'metric/report.json', '实际metric路径不同')
                body = read(p); metrics[seq] = body
                require(body['tracking_receipt'] == ref(control/'runs'/seq/'tracking/receipt.json'), '评价未绑定新实际输出')
                result = base.check_metric(body, tracks[seq], cfg, seq, sha(config), gaps[seq], id0.get(seq), outputs[seq]['returned_IDs'])
                for path, expected in body['numerical_source_sha256'].items(): require(sha(path) == expected, '原TrackEval数值源码改变')
                checks.append(dict(sequence=seq, tracking_output=outputs[seq], metric=result, report=item['report']))
            workers = base.check_workers(state, cfg, list(tracks.values()), list(metrics.values()), control)
            require(state['actual_exit_gate']['actual_CIM_checked'] is True and state['actual_exit_gate']['related_producers_absent'] is True, '原控制器实际退出门禁未齐')
            gate = read(control/'first_two_actual_adapter_gate.json')
            require(gate['status'] == 'complete_two_actual_OC_core_and_TrackEval_count_gates' and gate['test_read'] is False
                and [v['sequence'] for v in gate['checks']] == cfg['gate_sequences'], '首两场真实门禁未齐')
            for item in gate['checks']:
                require(item['report'] == declared[item['sequence']] and all(item[k] == metrics[item['sequence']][k] for k in ('frames', 'GT_rows', 'actual_ID0_rows')), '首两场门禁非对应新实际评价')
            report_path = checked(state['analysis_report']); require(report_path == control/'analysis_a01/report.json', '新实际分析位置不同')
            analysis = check_analysis(read(report_path), cfg, config, manifest, old_cfg, complete, base)
            require(guard['blocked_open_attempts'] == 0, '终验意外尝试原cache/GT/媒体')
        final_exit = processes_absent(state)
        receipt = dict(schema='ocsort_threshold025_independent_verification_v1', status=STATUS, implementation=ref(__file__),
            protocol=ref(config), state=ref(control/'state.json'), old06_complete=cfg['old06_complete'], base_verifier=cfg['base_verifier'],
            ledger_complete=cfg['ledger_complete'],
            single_factor_contract=contract, admission=admission, checks=checks, workers=workers, analysis=analysis,
            actual_new_clips=12, actual_new_frames=8165, old06_clips_reused=12, old06_tracking_rerun=False, registered_gap_events=3690,
            paired_matches=48, metric_intervals=60, separate_gap_descriptions=12, initial_exit=initial_exit, final_exit=final_exit,
            producer_processes_absent=True, old_namespace_globals_modified=False, raw_cache_GT_or_media_read=False,
            new_optimizer_updates=0, model_or_tracker_or_TrackEval_rerun=False, all_negative_results_preserved=True,
            formal_equivalence_or_noninferiority=False, test_read=False)
        write_new(output, receipt); return receipt
    except BaseException as error:
        write_new(output.parent/'failed.json', dict(status='failed_OC025_verification_partial_preserved_no_replay', error=repr(error), traceback=traceback.format_exc(),
            source_records_modified=False, new_optimizer_updates=0, test_read=False)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); result = verify(args.config, args.control, args.output)
    print(canonical(dict(status=result['status'], actual_new_clips=12, actual_new_frames=8165, paired_matches=48, metric_intervals=60, gap_descriptions=12)))
