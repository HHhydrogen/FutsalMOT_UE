"""官方OC-SORT十二开发片段独立终验；不重跑算法、TrackEval、GT或预测缓存。"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
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

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/ocsort_cached12_a01'
DONE = 'complete12_official_ocsort_cached_tracking_metrics_and_paired_analysis'
STATUS = 'complete12_official_ocsort_outputs_metrics_36_pairs_45_metric_9_gap_intervals_and_exit_verified'
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
BASELINES = ('PT_bbox', 'strong_motion_RS', 'T_RS')
PANELS = ('original_heldout', 'old_external', 'seven_observed')
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
FOLDS = ('game4', 'game6', 'game9'); SEEDS = (20261024, 20261025, 20261026)
COMMIT = '8462e7e729a93ccd3bd995c0a79a890336cb3a0b'
PARAMETERS = dict(det_thresh=.6, max_age=30, min_hits=3, iou_threshold=.3, delta_t=3,
                  asso_func='iou', inertia=.2, use_byte=False)
ALGORITHM = {
    'trackers/ocsort_tracker/ocsort.py': '122cc1c27d3321eac0debdf3ba782b76d189e1ac878256b8291ffeb4314fa979',
    'trackers/ocsort_tracker/association.py': 'c009a78eaa1c35c1d61217506255051ba882a7b99f9505cdec64da474ff0fbd7',
    'trackers/ocsort_tracker/kalmanfilter.py': '165a2d5243f2b874e37d3a3ae8112402f5c53ddfb6eb6e2cddda3311c3a2cded'}


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(path):
    path = Path(path); require(path.is_absolute(), '终验必须使用绝对路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
        for p in path.parts), '仅物理研究根，最终测试继续封存')
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            info = p.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): digest.update(block)
    return digest.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path']); require(path.is_file() and sha(path) == value['sha256'], '来源SHA变化：'+str(path))
    return path


def checked_dependency(value):
    """研究根外只核验两个既有库入口；不放开其他读写路径。"""
    path = Path(os.path.abspath(value['path']))
    if R in path.parents: return checked(value)
    allowed = {Path('D:/projects/FutsalMOT/.venv/Lib/site-packages')/name/'__init__.py' for name in ('numpy', 'scipy')}
    require(path in allowed, '外部依赖仅允许已冻结NumPy/SciPy入口只读')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不经junction读取外部依赖')
    require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == value['sha256'], '外部固定依赖SHA不同')
    return path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode; sys.dont_write_bytecode = True
    try: spec.loader.exec_module(value)
    finally: sys.dont_write_bytecode = previous
    return value


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def norm(path): return os.path.normcase(os.path.abspath(os.fsdecode(path)))


@contextmanager
def no_raw_reads(config):
    """只防止本次终验意外打开旧大缓存、标签坐标或媒体，不把声明当独立重数GT。"""
    paths = set(config.get('protected_GT_paths', []))
    for source in config['sources'].values():
        for key in ('cache', 'gt', 'gt_reference', 'gameinfo', 'seqinfo', 'seqinfo_reference'):
            if key in source: paths.add(source[key]['path'])
    paths.update(b['registry']['path'] for b in config['registries'].values())
    protected = {norm(p) for p in paths}; evidence = dict(active=True, blocked_open_attempts=0)
    def audit(event, args):
        if event != 'open' or not evidence['active'] or not args or not isinstance(args[0], (str, bytes, os.PathLike)): return
        path = os.fsdecode(args[0])
        if norm(path) in protected or Path(path).suffix.lower() in ('.jpg', '.jpeg', '.png', '.exr', '.mp4', '.avi'):
            evidence['blocked_open_attempts'] += 1
            raise PermissionError('终验不读取GT坐标、原预测缓存或媒体：'+path)
    sys.addaudithook(audit)
    try: yield evidence
    finally: evidence['active'] = False


def same(actual, expected, where='value'):
    """1e-8仅序列化核对，绝不是性能等效界限。"""
    if isinstance(expected, bool) or expected is None:
        require(actual is expected, where+'布尔/null不同')
    elif isinstance(expected, (int, float)):
        require(type(actual) in (int, float) and math.isfinite(actual) and abs(actual-expected) <= 1e-8, where+'数值不同')
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), where+'字段不同')
        for key in expected: same(actual[key], expected[key], where+'.'+key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), where+'长度不同')
        for i, (a, b) in enumerate(zip(actual, expected)): same(a, b, where+f'[{i}]')
    else: require(actual == expected, where+'不同')


def is_producer(command):
    return bool(re.search(r'(?:^|[\\/\s\"\x27])(?:ocsort_cached_(?:control|admission)|'
        r'pose_velocity_(?:decision_probe|tracking_control|learning_train)|substitution_validation_predictions)'
        r'[.]py(?=$|[\s\"\x27])', command or '', re.I))


def blocked_processes(records, state):
    """具名源码与真实spawn父身份/创建时段；不能凭历史PID拒绝无关进程。"""
    start = datetime.fromisoformat(state['created_utc'].replace('Z', '+00:00'))
    parent = state['parent_pid']; blocked = []
    for row in records:
        command = row.get('CommandLine') or ''; name = (row.get('Name') or '').lower()
        named = name.startswith('unrealeditor') or is_producer(command)
        spawned = False
        if 'spawn_main' in command and re.search(r'\bparent_pid\s*=\s*'+str(parent)+r'\b', command):
            created = row.get('CreationUtc')
            require(created, '相关spawn缺少实际创建时间，不能凭旧PID猜退出')
            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
            spawned = start-timedelta(seconds=2) <= created <= datetime.now(timezone.utc)+timedelta(seconds=2)
        if named or spawned: blocked.append(row)
    return blocked


def processes_absent(state):
    command = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='CreationUtc';e={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], check=True,
        capture_output=True, text=True, encoding='utf-8', errors='strict')
    records = json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(records, dict): records = [records]
    blocked = blocked_processes(records, state)
    require(not blocked, '相关生产者/UE尚在，不强杀或按旧PID猜退出：'+canonical(blocked))
    return dict(actual_CIM_checked=True, related_producers_absent=True,
        script_basename_and_spawn_parent_creation_checked=True, unrelated_reused_historical_PID_not_rejected=True)


def native_to_mot(native, mot, frames, frame_counts):
    """逐帧含空帧、逐行含原ID/顺序/全部框，不以GT过滤或重编号。"""
    require(type(frames) is int and frames > 0 and len(frame_counts) == frames, '完整帧分母缺失')
    total = 0; max_id = 0; ids = set(); empty = 0
    with physical(native).open(encoding='utf-8-sig') as source, physical(mot).open(encoding='utf-8-sig') as target:
        for index in range(frames):
            line = source.readline(); require(bool(line.strip()), 'native空检测帧也必须有记录')
            value = json.loads(line)
            require(set(value) == {'frame_number', 'rows'} and type(value['frame_number']) is int
                and value['frame_number'] == index+1 and isinstance(value['rows'], list), 'native帧顺序/字段不同')
            rows = value['rows']; require(type(frame_counts[index]) is int and len(rows) == frame_counts[index], '帧输出行数不同')
            if not rows: empty += 1
            seen = set()
            for row in rows:
                require(isinstance(row, list) and len(row) == 5 and all(type(v) in (int, float) and math.isfinite(v) for v in row), 'native原生五列非法')
                x1, y1, x2, y2, identity = map(float, row)
                require(identity.is_integer() and identity > 0 and identity not in seen and x2 > x1 and y2 > y1, 'native原ID/几何非法')
                seen.add(identity); ids.add(int(identity)); max_id = max(max_id, int(identity))
                expected = ','.join(map(str, [index+1, int(identity), x1, y1, x2-x1, y2-y1, 1, -1, -1, -1]))
                require(target.readline().rstrip('\r\n') == expected, 'MOT未原样保留native行/ID/顺序/恒1分数')
                total += 1
        require(source.read() == '' and target.read() == '', '完整native/MOT末尾有额外帧或预测')
    return dict(frames=frames, tracked_rows=total, maximum_native_ID=max_id, returned_IDs=len(ids),
        empty_output_frames=empty, original_IDs_and_order_preserved=True, no_row_filter_or_renumber=True)


def check_tracking(receipt, cfg, sequence, protocol_sha, official):
    source = cfg['sources'][sequence]; audit = receipt['audit']; backend = receipt['official_source']
    require(receipt['schema'] == 'official_ocsort_cached12_tracking_v1' and receipt['status'] == 'complete'
        and receipt['protocol_sha256'] == protocol_sha and receipt['sequence'] == sequence
        and receipt['frames'] == source['frames'] and receipt['source_cache'] == source['cache']
        and receipt['parameters'] == cfg['parameters'] == PARAMETERS
        and receipt['new_optimizer_updates'] == 0 and receipt['test_read'] is False, '原协议/缓存/参数/帧来源不同')
    require(all(receipt[k] is False for k in ('evaluation_GT_annotations_loaded', 'GT_used_for_tracking', 'tracker_input_has_Pose')), 'track混入GT或Pose')
    guard = receipt['GT_guard']
    require(guard['python_open_audit_installed'] is True and guard['blocked_open_attempts'] == 0
        and guard['GT_annotations_opened'] is False and guard['protected_paths'] == len(set(cfg['protected_GT_paths'])), 'track GT隔离证据不完整')
    require(backend['schema'] == 'official_ocsort_cached_backend_v1' and backend['manifest'] == cfg['official_manifest']
        and backend['commit'] == COMMIT and backend['repository'] == 'https://github.com/noahcao/OC_SORT'
        and backend['source_root'] == official['source_root'] and backend['loaded_algorithm_files'] == ALGORITHM
        and backend['constructor_arguments'] == list(PARAMETERS)
        and backend['constructor_defaults'] == {k: v for k, v in PARAMETERS.items() if k != 'det_thresh'}
        and backend['det_thresh_source'] == 'official_CLI_track_thresh_default_0.6'
        and backend['numerical_source_modified'] is False, '官方core来源或默认参数改变')
    require(backend['actual_assignment_backend'] == 'lap.lapjv' and backend['scipy_assignment_fallback_allowed'] is False
        and backend['native_Kalman_precision'] == 'original_float64_matrices_and_operations_not_cast_to_FP32'
        and backend['update_entry'] == 'OCSort.update_not_update_public'
        and backend['input'] == 'new_numpy_float32_N5_xyxy_score'
        and backend['score_export'] == 'MOT_constant_1_not_detection_confidence'
        and backend['no_demo_min_area_or_aspect_filter'] is True and backend['full_demo_pipeline_reproduction'] is False
        and backend['paper2023_byte_reproduction'] is False, '不能替换求解器/精度或冒称完整demo/paper复现')
    require(backend['dependency_versions'] == dict(numpy='2.2.6', scipy='1.15.3', filterpy='1.4.5',
        **{'filterpy.stats': None, 'filterpy.common': None, 'lap': '0.5.13'}), '实际依赖版本不同')
    for value in list(backend['dependency_sources'].values())+[backend['assignment_binary_source']]: checked_dependency(value)
    required_true = ('all_raw_detections_passed_to_core', 'img_info_equals_img_size', 'original_IDs_preserved', 'static_kalman_matrices_unchanged')
    required_false = ('outside_core_filtering', 'native_output_score_available', 'MOT_score_is_detection_confidence',
        'posthoc_ID_renumbering', 'model_GT_or_Pose_input', 'GT_read', 'Pose_fields_read', 'GPU_used', 'test_read')
    require(all(audit[k] is True for k in required_true) and all(audit[k] is False for k in required_false)
        and audit['update_calls'] == source['frames'] and audit['input_dtype'] == 'float32'
        and audit['input_columns'] == 'xyxy+score_N5_no_class_multiplication' and audit['scale'] == 1
        and audit['MOT_score_constant'] == 1 and audit['ID_before'] == 0 and audit['new_optimizer_updates'] == 0, '原全部检测/调用/精度/ID重置守卫不完整')
    counts = audit['raw_detection_counts']
    require(len(counts) == source['frames'] and all(type(v) is int and v >= 0 for v in counts)
        and sum(counts) == audit['raw_detections'] == source['counts']['raw_detections']
        and audit['empty_input_frames'] == sum(v == 0 for v in counts)
        and re.fullmatch('[0-9a-f]{64}', audit['input_chain_sha256']), '原检测分母/空帧/输入链不完整')
    require(receipt['mot_sha256'] == receipt['mot']['sha256'], 'MOT重复SHA不同')
    result = native_to_mot(checked(receipt['native_outputs']), checked(receipt['mot']), source['frames'], receipt['frame_counts'])
    require(result['tracked_rows'] == receipt['tracked_rows'] == sum(receipt['frame_counts'])
        and type(audit['ID_counter_after']) is int and audit['ID_counter_after'] >= result['maximum_native_ID'], '实际输出/原全局ID计数不同')
    return result


def gap_values(recovery):
    n = recovery['total_events']; success = recovery.get('same_prediction_ID_recovered', 0); rate = recovery['recovery_rate']
    require(type(n) is int and type(success) is int and 0 <= success <= n, '全事件分母/成功数非法')
    require((rate is None and success == 0) if n == 0 else
        (type(rate) in (float, int) and math.isfinite(rate) and abs(rate-success/n) <= 1e-12), '零事件必须null，非零率与原分母不同')
    return n, success, rate


def check_metric(report, tracking, cfg, sequence, protocol_sha, gap_count, id0_present, actual_ids=None):
    source = cfg['sources'][sequence]; n = source['frames']; count = tracking['tracked_rows']; gt = cfg['expected_GT_rows'][sequence]
    require(report['schema'] == 'official_ocsort_cached12_evaluation_v1' and report['status'] == 'complete'
        and report['sequence'] == sequence and report['frames'] == n and report['protocol_sha256'] == protocol_sha
        and report['source_cache'] == source['cache'] and report['GT_rows'] == gt
        and report.get('fold') is None and report.get('seed') is None
        and report['new_optimizer_updates'] == 0 and report['test_read'] is False, '实际OC评价/GT总数/缓存不同')
    require(report['DO_PREPROC'] is False and report['predictions_GT_filtered'] is False
        and report['GT_ID0_original'] is True and report['GT_used_only_for_metric'] is True, '原ID0/全预测/GT边界不完整')
    id0 = report['actual_ID0_rows']; require(type(id0) is int and 0 <= id0 <= gt, '实际评价ID0计数非法')
    if id0_present is not None: require((id0 > 0) is id0_present, '公开原来源ID0存在口径不同')
    raw = report['raw_results']; require(set(raw) == {sequence, 'COMBINED_SEQ'} and set(report['summary']) == set(raw), '单序列和COMBINED评价缺失/多序列混入')
    for name in (sequence, 'COMBINED_SEQ'):
        values = raw[name]['pedestrian']; counts = values['Count']
        require(counts['Dets'] == count and counts['GT_Dets'] == gt and counts['IDs'] >= 0 and counts['GT_IDs'] >= 0, 'TrackEval Count预测/GT行数不同')
        if actual_ids is not None: require(counts['IDs'] == actual_ids, '全部原生ID数与TrackEval Count不同')
        if name == sequence: require(counts['Frames'] == n, '原单序列帧数不同')
        elif 'Frames' in counts: require(counts['Frames'] == n, 'COMBINED若有Frames必须原值，不强加不存在字段')
        fractions = {}
        for group, keys in [('HOTA', ('HOTA', 'AssA', 'DetA')), ('Identity', ('IDF1',)), ('CLEAR', ('MOTA',))]:
            for key in keys:
                value = values[group][key]
                if isinstance(value, list): require(bool(value), 'TrackEval空阈值数组'); value = mean(value)
                require(type(value) in (float, int) and math.isfinite(value), '原评价非有限不能忽略负结果')
                fractions[key] = value
        same(report['summary'][name]['metrics_fraction'], fractions, '原fraction摘要')
        same(report['summary'][name]['metrics_percent'], {k: 100*v for k, v in fractions.items()}, '原percent摘要')
        require(report['summary'][name]['IDSW_count'] == values['CLEAR']['IDSW'], '原IDSW摘要不同')
    same(report['metrics_percent'], report['summary'][sequence]['metrics_percent'])
    overall = report['recovery']['overall']; require(gap_values(overall)[0] == gap_count, '必须全部事前登记gap，不筛成功端点')
    outcome = ('same_prediction_ID_recovered', 'ambiguous_endpoint', 'different_prediction_ID', 'missing_prediction_endpoint')
    # 原Counter只序列化实际出现的键，未出现结局按原Counter语义为0。
    require(all(type(overall.get(k, 0)) is int and 0 <= overall.get(k, 0) <= gap_count for k in outcome)
        and sum(overall.get(k, 0) for k in outcome) == gap_count, '原全事件互斥结局不闭合')
    details = report['recovery']['events']
    require(len(details) == len({v['event_uid'] for v in details}) == gap_count
        and all(v['reason'] in outcome for v in details), '全部事件明细分母/UID/结局缺失或重复')
    reasons = Counter(v['reason'] for v in details)
    require(all(reasons[k] == overall.get(k, 0) for k in outcome), '原逐事件明细与汇总结局不同')
    for field, state in [('events_with_missing_endpoint', 'missing'), ('events_with_ambiguous_endpoint', 'ambiguous')]:
        require(overall.get(field, 0) == sum(state in v['endpoint_states'] for v in details), '原端点歧义/缺失辅助计数不同')
    strata = report['recovery']['strata']
    require(set(strata) == {'2-4', '5-9', '10-29'} and sum(v['total_events'] for v in strata.values()) == gap_count, '原gap长度分层分母不齐')
    for value in strata.values(): gap_values(value)
    require(all(sum(v.get(k, 0) for v in strata.values()) == overall.get(k, 0) for k in outcome), '原gap分层结局未闭合')
    binding = cfg['registries']['seven' if sequence in cfg['panels']['seven_observed'] else 'old_five']
    require(report['registry'] == binding['registry'], 'gap来源引用不同')
    return dict(sequence=sequence, frames=n, GT_rows=gt, actual_ID0_rows=id0,
        original_public_ID0_presence=id0_present, ID0_independently_recounted_in_terminal_verifier=False,
        gap_events=gap_count, metrics=report['metrics_percent'])


def check_workers(state, cfg, tracking, metrics, control):
    ready = state['workers']; exits = state['worker_exits']
    require(len(ready) == len(exits) == 3 and Counter(v['kind'] for v in ready) == dict(track=2, metric=1)
        and Counter(v['kind'] for v in exits) == dict(track=2, metric=1), '必须完整2track+1metric常驻池')
    identities = {v['worker_pid']: v for v in ready}; require(len(identities) == 3, '三个worker不能重复PID')
    require({v['worker_pid'] for v in exits} == set(identities), '实际join退出清单不同')
    used_track = Counter(t['worker_pid'] for t in tracking); used_metric = Counter(t['worker_pid'] for t in metrics)
    for item in exits:
        pid = item['worker_pid']; kind = item['kind']; evidence = item['close_evidence']; identity = identities[pid]
        require(identity['status'] == 'ready' and identity['kind'] == kind and identity['parent_pid'] == state['parent_pid']
            and datetime.fromisoformat(identity['created_utc']) >= datetime.fromisoformat(state['created_utc'])
            and item['launcher_pid'] == pid and item['exit_code'] == 0 and item['process_exited'] is True
            and evidence['status'] == 'closed' and evidence['worker_pid'] == pid, '常驻worker握手/闭包/exit0未齐')
        require(evidence['jobs'] == (used_track[pid] if kind == 'track' else used_metric[pid]), 'worker完整任务数不同')
        if kind == 'track':
            require(evidence['cache_entries_after'] == 0 and 0 < evidence['max_counted_cache_bytes'] <= cfg['worker_profile']['cache_limit_bytes']
                and evidence['counted_cache_is_JSON_bytes_not_RSS'] is True
                and evidence['GT_guard']['blocked_open_attempts'] == 0
                and evidence['GT_guard']['GT_annotations_opened'] is False
                and evidence['GT_guard']['python_open_audit_installed'] is True, 'track实际缓存/GT关闭证据不足')
        else:
            require(evidence['GT_isolated_to_metric_worker'] is True and evidence['source_closure_verified'] is True
                and set(evidence['GT_sequences_loaded']) == set(cfg['sources']) and len(evidence['GT_sequences_loaded']) == 12
                and evidence['registry_count'] == 2, 'metric全部GT/两个事件来源关闭未齐')
    require(set(used_track) <= {p for p, v in identities.items() if v['kind'] == 'track'}
        and set(used_metric) == {p for p, v in identities.items() if v['kind'] == 'metric'}
        and sum(used_track.values()) == sum(used_metric.values()) == 12, '结果worker身份/全部任务不一致')
    logs = [physical(control/'logs'/name) for name in ('track_0.log', 'track_1.log', 'metric_0.log')]
    require(all(p.is_file() for p in logs), '三个实际worker日志缺失')
    return dict(workers=3, track_jobs=12, metric_jobs=12, all_joined_exit0=True, logs=[ref(p) for p in logs], worker_exits=exits)


def pair_rows(oc, references, panels):
    """独立重新平均来源：每场一次OC，训练单元仅用于场内均值。"""
    require(len(oc) == 12 and len({v['sequence'] for v in oc}) == 12 and len(references) == 192, '12/192原评价矩阵缺失')
    targets = {v['sequence']: v for v in oc}; grouped = defaultdict(list); result = []
    for item in references: grouped[item['baseline'], item['sequence']].append(item)
    for baseline in BASELINES:
        for panel in PANELS:
            for sequence in panels[panel]:
                group = grouped[baseline, sequence]; target = targets[sequence]
                expected = {(None, None)} if baseline == 'PT_bbox' else {
                    (fold, seed) for fold in ((OLD[sequence],) if sequence in OLD else FOLDS) for seed in SEEDS}
                require(len(group) == len(expected) and {(v['fold'], v['seed']) for v in group} == expected, '缺项/重复参照不能复制OC充seed')
                avg = {k: mean(v['metrics'][k] for v in group) for k in METRICS}
                denominator, success, rate = gap_values(target['recovery']); gaps = [gap_values(v['recovery']) for v in group]
                require(all(g[0] == denominator for g in gaps), '配对必须同全部注册gap分母')
                reference_rate = mean(g[2] for g in gaps) if denominator else None
                result.append(dict(baseline=baseline, panel=panel, sequence=sequence, OC_evaluations=1, reference_training_cells=len(group),
                    delta_pp={k: target['metrics'][k]-avg[k] for k in METRICS}, OC_report=target['report'], reference_reports=[v['report'] for v in group],
                    gap=dict(total_registered_events=denominator, OC_success=success, OC_rate=rate,
                        reference_mean_success=mean(g[1] for g in gaps), reference_mean_rate=reference_rate,
                        delta_recovery_rate_pp=100*(rate-reference_rate) if denominator else None)))
    require(len(result) == 36, '完整36比赛配对未齐'); return result


def expected_intervals(pairs, panels, interval):
    metric = {}; gaps = {}
    for baseline in BASELINES:
        metric[baseline] = {}; gaps[baseline] = {}
        for panel in PANELS:
            rows = [v for v in pairs if v['baseline'] == baseline and v['panel'] == panel]
            require([v['sequence'] for v in rows] == panels[panel], '比赛等权区间顺序不同')
            metric[baseline][panel] = {k: interval({v['sequence']: v['delta_pp'][k] for v in rows}) for k in METRICS}
            values = {v['sequence']: v['gap']['delta_recovery_rate_pp'] for v in rows if v['gap']['delta_recovery_rate_pp'] is not None}
            missing = [v['sequence'] for v in rows if v['gap']['delta_recovery_rate_pp'] is None]
            description = interval(values) if len(values) >= 2 else dict(n_independent_matches=len(values), match_deltas_pp=values,
                mean_delta_pp=mean(values.values()) if values else None, Student_t_95CI=None, percentile_match_bootstrap_95CI=None,
                leave_one_match_out_mean=None, status='fewer_than_two_matches_with_events_no_interval')
            gaps[baseline][panel] = dict(description, zero_event_matches_retained_null=missing,
                outcome='all_registered_trusted_detection_gap_proxy_not_physical_occlusion')
    return metric, gaps


def check_csv(reference, expected):
    with checked(reference).open(encoding='utf-8-sig', newline='') as stream: actual = list(csv.DictReader(stream))
    require(len(actual) == len(expected), 'CSV完整行数不同，不能删除负项')
    for a, b in zip(actual, expected):
        require(set(a) == set(b), 'CSV字段改变')
        for key, value in b.items():
            if value is None: require(a[key] == '', 'CSV null必须保留空单元')
            elif isinstance(value, (int, float)): same(float(a[key]), value, 'CSV.'+key)
            elif isinstance(value, (dict, list)): same(json.loads(a[key]), value, 'CSV.'+key)
            else: require(a[key] == value, 'CSV来源/标识不同：'+key)


def check_analysis(report, cfg_path, cfg, manifest, analysis):
    require(report['schema'] == 'ocsort_cached12_paired_analysis_protocol_v1'
        and report['status'] == 'complete12_official_ocsort_cached_paired_analysis' and report['protocol'] == ref(cfg_path)
        and report['OC_evaluations'] == 12 and report['reference_cells'] == 192 and report['paired_matches'] == 36
        and report['metric_interval_descriptions'] == 45 and report['separate_gap_interval_descriptions'] == 9
        and report['comparison_direction'] == 'OCSORT_minus_reference' and report['primary_reference'] == 'strong_motion_RS'
        and report['secondary_reference'] == 'T_RS' and report['context_reference'] == 'PT_bbox'
        and report['primary_metric'] == 'AssA' and report['panels'] == cfg['panels'], '三面板/主参照/配对与区间数不同')
    require(report['all_negative_results_preserved'] is True and report['formal_equivalence_or_noninferiority'] is False
        and report['performance_margin'] is None and report['new_optimizer_updates'] == 0
        and report['model_loaded'] is False and report['TrackEval_rerun'] is False and report['test_read'] is False, '描述边界/负结果保留声明不同')
    refs, inventory = analysis.inventory(cfg)
    oc = analysis.load_evaluations(cfg_path, cfg, manifest)
    pairs = pair_rows(oc, refs, cfg['panels'])
    require(report['source_inventory'] == inventory and report['all_OC_reports'] == [v['report'] for v in oc]
        and report['all_reference_reports'] == [v['report'] for v in refs] and report['interval_source'] == cfg['interval_source'], '全部来源清单不同')
    check_csv(report['all_OC_results'], [dict(sequence=v['sequence'], **v['metrics'], gap_events=v['recovery']['total_events'],
        gap_success=v['recovery']['same_prediction_ID_recovered'], gap_rate=v['recovery']['recovery_rate'],
        report_path=v['report']['path'], report_sha256=v['report']['sha256']) for v in oc])
    check_csv(report['all_reference_cells'], [dict(**{k: v[k] for k in ('baseline', 'sequence', 'fold', 'seed')}, **v['metrics'],
        gap_events=v['recovery']['total_events'], gap_success=v['recovery']['same_prediction_ID_recovered'],
        gap_rate=v['recovery']['recovery_rate'], report_path=v['report']['path'], report_sha256=v['report']['sha256']) for v in refs])
    check_csv(report['all_paired_matches'], [dict(**{k: v[k] for k in ('baseline', 'panel', 'sequence', 'OC_evaluations', 'reference_training_cells')},
        **v['delta_pp'], OC_report=v['OC_report'], reference_reports=v['reference_reports']) for v in pairs])
    check_csv(report['all_paired_gaps'], [dict(**{k: v[k] for k in ('baseline', 'panel', 'sequence', 'reference_training_cells')}, **v['gap']) for v in pairs])
    interval_path = checked(cfg['interval_source']); require(interval_path.name == 'substitution_paired_analysis.py', '不能更换预登记区间函数')
    interval = module('independent_ocsort_original_descriptive_intervals', interval_path).effect_intervals
    metrics, gaps = expected_intervals(pairs, cfg['panels'], interval)
    same(report['metric_comparisons'], metrics, '全部45描述区间'); same(report['gap_comparisons'], gaps, '另9gap描述')
    return dict(OC_rows=12, reference_rows=192, paired_match_rows=36, paired_gap_rows=36,
        metric_intervals=45, separate_gap_descriptions=9, negative_metric_cells=sum(v < 0 for p in pairs for v in p['delta_pp'].values()),
        negative_gap_matches=sum(p['gap']['delta_recovery_rate_pp'] is not None and p['gap']['delta_recovery_rate_pp'] < 0 for p in pairs),
        all_pairs_recomputed_from_actual_report_sources=True, intervals_recomputed_without_TrackEval=True,
        CSVs={key: report[key] for key in ('all_OC_results', 'all_reference_cells', 'all_paired_matches', 'all_paired_gaps')})


def metadata(cfg):
    require(cfg['schema'] == 'official_ocsort_cached12_protocol_v1' and cfg['approved_by'] == 'root'
        and cfg['tracking_authorized'] is True and cfg['test_sealed'] is True and cfg['new_optimizer_updates'] == 0
        and cfg['formal_equivalence_or_noninferiority'] is False and cfg['parameters'] == PARAMETERS, '正式来源/参数/测试边界未冻结')
    require(set(cfg['panels']) == set(PANELS) and [len(cfg['panels'][p]) for p in PANELS] == [3, 2, 7]
        and set(cfg['panels']['original_heldout']) == set(OLD)
        and cfg['sequence_order'] == [s for p in PANELS for s in cfg['panels'][p]]
        and len(cfg['sequence_order']) == len(set(cfg['sequence_order'])) == 12
        and set(cfg['sources']) == set(cfg['sequence_order'])
        and sum(v['frames'] for v in cfg['sources'].values()) == 8165, '只能原3/2/7开发面板与8165全帧')
    require(cfg['worker_profile'] == dict(track_workers=2, metric_workers=1, numeric_threads=1,
        cache_limit_bytes=134217728, cache_max_sequences=2, reserve_RAM_bytes=8589934592,
        reserve_commit_bytes=6442450944, startup_estimate_bytes=268435456), '只能已冻结2+1/有界缓存与线程协议')
    old = read(checked(cfg['source_velocity_protocol']))
    require(cfg['sources'] == old['sources'] and cfg['panels'] == old['panels'] and cfg['registries'] == old['registries'], '12缓存/原gap来源不能替换')
    bundle = physical(cfg['bundle'])
    require(bundle.parent == R/'code', '只允许不可变源码bundle')
    for item in read(checked(cfg['bundle_manifest']))['files']: require(sha(bundle/item['path']) == item['sha256'], '正式源码bytes变化')
    official = read(checked(cfg['official_manifest']))
    require(official['schema'] == 'official_ocsort_source_manifest_v1' and official['status'] == 'complete_minimal_official_source_not_tracking'
        and official['commit'] == COMMIT and official['repository'] == 'https://github.com/noahcao/OC_SORT', '官方原始来源不同')
    entries = {v['path']: v for v in official['files']}
    require(len(official['files']) == len(entries) == 8 and all(entries[k]['sha256'] == v for k, v in ALGORITHM.items()), '官方最小8文件/3算法来源不完整')
    for item in entries.values():
        path = physical(Path(official['source_root'])/item['path'])
        require(path.stat().st_size == item['size'] and sha(path) == item['sha256'], '官方原始源码发生变化')
    dependency = read(checked(cfg['dependency_manifest']))
    for item in dependency['files']: checked_dependency(item)
    counts = {}; id0 = {}; gt_counts = {}
    for binding in cfg['registries'].values():
        public = read(checked(binding['receipt']))
        require(public['registry'] == binding['registry'] and public['contains_GT_coordinates'] is False
            and public['test_read'] is False and public['tracking_results_read'] is False
            and public['sources'] == {s: cfg['sources'][s] for s in public['sources']}, '只可读取同源无GT坐标公开收据')
        current = public.get('sequence_event_counts', public.get('event_counts'))
        require(isinstance(current, dict) and sum(current.values()) == public['event_count'] and not set(current) & set(counts), '原全事件公开分母不齐/重复')
        counts.update(current); gt_counts.update(public['GT_row_counts']); id0.update(public.get('GT_ID0_present', {}))
    require(set(counts) == set(cfg['sources']) and sum(counts.values()) == 3690 and gt_counts == cfg['expected_GT_rows'], '原3690全事件/GT总行分母不同')
    for seq, value in cfg.get('expected_ID0_present', {}).items():
        if value is not None: require(id0.get(seq) is value, '冻结ID0存在声明应来自原公开收据')
    return official, counts, {s: id0.get(s) for s in cfg['sources']}


def check_admission(state, cfg, config):
    path = physical(cfg['admission_receipt_path']); require(state['admission'] == ref(path), '正式状态未绑定实际数值准入')
    proof = read(path); admission = read(checked(proof['config']))
    require(proof['schema'] == 'official_ocsort_cached_admission_receipt_v1'
        and proof['status'] == 'complete_official_literal96_frames_ABA_two_spawn_exact_GT_guard_and_exit_verified'
        and admission['formal_protocol'] == ref(config) and admission['official_manifest'] == cfg['official_manifest']
        and admission['dependency_manifest'] == cfg['dependency_manifest'] and admission['parameters'] == cfg['parameters']
        and admission['sources'] == cfg['sources']
        and admission['runtime'] == ref(Path(cfg['bundle'])/'tools/research_ops/ocsort_cached_runtime.py')
        and proof['parameters'] == admission['admission_parameters'] and proof['unique_source_frames'] == 96
        and proof['all_workers_joined_exited'] is True and proof['optimizer_updates'] == 0
        and proof['TrackEval_runs'] == 0 and proof['test_read'] is False, '对应冻结源码/同缓存的96帧准入未完整')
    comparisons = list(proof['literal_vs_adapter'].values())+[v['comparison'] for v in proof['persistent_ABA']]+[v['comparison'] for v in proof['independent_spawn_A']]
    require(set(proof['literal_vs_adapter']) == {'A', 'B'} and len(proof['persistent_ABA']) == 3
        and len(proof['independent_spawn_A']) == 2 and len(comparisons) == 7
        and all(v['original_ID_MOT_equal'] is True and v['all_frame_counts_equal'] is True
            and v['per_frame_raw_outputs_exact'] is True and v['frames'] == 48 for v in comparisons)
        and proof['parent_source_input_unchanged'] is True
        and proof['source_prefixes'] == {k: cfg['sources'][s]['cache'] for k, s in [('A', 'SNMOT-060'), ('B', 'v_2QhNRucNC7E_c017')]}, 'literal/ABA/双spawn实际逐值对照未齐')
    closures = [proof['persistent_worker']]+[v['closure'] for v in proof['independent_spawn_A']]
    require(len({v['pid'] for v in closures}) == 3 and all(v['kind'] == 'closed' and v['joined'] is True
        and v['exitcode'] == 0 and v['actual_PID_absent_after_join'] is True and v['active_trackers'] == 0 for v in closures), '实际准入worker退出未齐')
    guards = [proof['parent_GT_guard']]+[v['GT_guard'] for v in closures]
    require(all(v['GT_Python_open_guard'] is True and v['self_test_blocked_opens'] > 0
        and v['algorithm_blocked_GT_opens'] == 0 and v['algorithm_GT_read'] is False for v in guards), '准入GT保护自检或实际边界缺失')
    return dict(receipt=ref(path), literal_ABA_spawn_comparisons=7, unique_source_frames=96, actual_workers_joined_exit0=3)


def verify(config, control, output):
    config, control, output = physical(config), physical(control), physical(output)
    require(EXP in output.parents and output.parent != control and control not in output.parents
        and not output.parent.exists(), '终验必须独立新attempt，已有intent/partial不覆盖')
    cfg = read(config); state = read(control/'state.json')
    require(control == physical(cfg['output_root']), '实际控制目录与协议不同')
    output.parent.mkdir(parents=True)
    write_new(output.parent/'intent.json', dict(config=ref(config), control=str(control), state=ref(control/'state.json'),
        new_optimizer_updates=0, GT_or_cache_or_media_read=False, test_read=False))
    try:
        require(state['status'] == DONE and state['protocol'] == ref(config) and not state['active']
            and state['actual_frames'] == 8165 and state['actual_clips'] == 12 and state['new_optimizer_updates'] == 0
            and state['test_read'] is False and state['new_detector_or_Pose_inference'] is False
            and state['GT_only_metric_process'] is True, '实际12任务/分析/退出终态未齐')
        exit_gate = processes_absent(state)
        with no_raw_reads(cfg) as guard:
            official, gaps, id0 = metadata(cfg); admission = check_admission(state, cfg, config)
            require(state['actual_exit_gate']['actual_CIM_checked'] is True and state['actual_exit_gate']['related_producers_absent'] is True,
                '原控制器三个worker关闭后的实际退出门禁缺失')
            manifest_path = control/'evaluation_manifest.json'; manifest = read(manifest_path)
            require(manifest['schema'] == 'official_ocsort_cached12_evaluation_manifest_v1'
                and manifest['status'] == 'complete12_official_ocsort_cached_evaluations' and manifest['protocol'] == ref(config)
                and [v['sequence'] for v in manifest['evaluations']] == cfg['sequence_order'], '完成评价清单不等原12顺序')
            track_entries = state['completed_tracking']; metric_entries = state['completed_metrics']
            require(len(track_entries) == len(metric_entries) == 12
                and {v['sequence'] for v in track_entries} == {v['sequence'] for v in metric_entries} == set(cfg['sources']), '完整12追踪/评价清单缺项重复')
            tracking = {}; metrics = {}; checks = []; outputs = {}
            for item in track_entries:
                seq = item['sequence']; path = checked(item['receipt'])
                require(path == control/'runs'/seq/'tracking/receipt.json' and physical(item['tracking']) == path.parent, '追踪输出路径不匹配')
                body = read(path); result = check_tracking(body, cfg, seq, sha(config), official)
                tracking[seq] = body; outputs[seq] = result; checks.append(dict(sequence=seq, tracking_receipt=item['receipt'], output=result))
            declared = {v['sequence']: v['report'] for v in manifest['evaluations']}
            for item in metric_entries:
                seq = item['sequence']; path = checked(item['report'])
                require(item['report'] == declared[seq] and path == control/'runs'/seq/'metric/report.json', '实际metric来源不同')
                body = read(path)
                require(body['tracking_receipt'] == ref(control/'runs'/seq/'tracking/receipt.json'), '实际metric未绑定对应全部MOT')
                result = check_metric(body, tracking[seq], cfg, seq, sha(config), gaps[seq], id0[seq], outputs[seq]['returned_IDs']); metrics[seq] = body
                for path, expected in body['numerical_source_sha256'].items():
                    require(sha(path) == expected, '实际TrackEval数值源码SHA变化')
                next(v for v in checks if v['sequence'] == seq)['evaluation'] = dict(item['report'], **result)
            workers = check_workers(state, cfg, list(tracking.values()), list(metrics.values()), control)
            gate = read(control/'first_two_actual_adapter_gate.json')
            require(gate['status'] == 'complete_two_actual_OC_core_and_TrackEval_count_gates' and gate['test_read'] is False
                and [v['sequence'] for v in gate['checks']] == cfg['gate_sequences'], '首两场真实门禁缺失')
            for item in gate['checks']:
                report = metrics[item['sequence']]
                require(item['report'] == declared[item['sequence']] and all(item[k] == report[k] for k in ('frames', 'GT_rows', 'actual_ID0_rows')), '首两场门禁不是实际评价')
            analysis_path = checked(state['analysis_report']); require(analysis_path == control/'analysis_a01/report.json', '实际分析路径不同')
            analysis = module('frozen_ocsort_result_source_inventory_only', Path(cfg['bundle'])/'tools/research_ops/ocsort_cached_analysis.py')
            analysis_check = check_analysis(read(analysis_path), config, cfg, manifest, analysis)
            require(guard['blocked_open_attempts'] == 0, '终验意外尝试读取受保护来源')
        # 所有流式文件读完后再次核验真实进程，避免把仍存活的控制器当完成。
        final_exit = processes_absent(state)
        receipt = dict(status=STATUS, schema='official_ocsort_cached12_independent_verification_v1', config=ref(config),
            state=ref(control/'state.json'), evaluations=ref(manifest_path), analysis=state['analysis_report'],
            actual_clips=12, actual_frames=8165, registered_gap_events=3690, checks=checks, workers=workers, admission=admission,
            analysis_verification=analysis_check, initial_exit=exit_gate, final_exit=final_exit,
            producer_processes_absent=True, new_optimizer_updates=0, model_loaded=False, TrackEval_rerun=False,
            old_prediction_cache_rehashed=False, GT_coordinates_or_media_read=False,
            protected_open_attempts=guard['blocked_open_attempts'], ID0_independently_recounted=False,
            ID0_evidence='original_loader_bytes_and_original_GT_total_counts_plus_available_public_presence_receipts',
            numerical_serialization_tolerance_pp=1e-8, tolerance_is_not_performance_margin=True,
            all_negative_results_preserved=True, formal_equivalence_or_noninferiority=False, test_read=False)
        write_new(output, receipt); return receipt
    except BaseException as error:
        write_new(output.parent/'failed.json', dict(status='failed_independent_verification_partial_preserved_no_replay',
            error=repr(error), traceback=traceback.format_exc(), source_records_modified=False,
            new_optimizer_updates=0, model_loaded=False, TrackEval_rerun=False, test_read=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.config, args.control, args.output)
    print(canonical({k: result[k] for k in ('status', 'actual_clips', 'actual_frames', 'registered_gap_events', 'new_optimizer_updates')}))
