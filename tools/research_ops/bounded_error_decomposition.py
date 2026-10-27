"""原balanced27共同状态的有边界后验条件分解；不评分、不追踪、不重算TrackEval。"""
import ast
from collections import Counter, OrderedDict, defaultdict
import csv
import gzip
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys


FIRST_STOPS = ('history_unknown', 'mixed_trusted_history', 'current_GT_absent',
    'raw_geometry_ambiguous', 'no_raw_geometry_candidate', 'positive_raw_not_in_stage',
    'history_fewer_than3', 'row_not_intervened', 'positive_outside_effective_gate',
    'no_single_edge_feasible_positive', 'reference_stage_selected_correct',
    'unknown_competition_or_assignment', 'known_negative_cost_lower', 'minimum_cost_tie',
    'global_competition_or_solver_unmatched', 'unclassified_preserved')
OUTCOMES = ('same_trusted_GT', 'other_trusted_GT_or_far_unmatched', 'unknown_candidate', 'unmatched_stage')
ANCHOR_STATES = ('history_unknown', 'mixed_trusted_history', 'no_trusted3_anchor_yet',
    'trusted3_anchor_established_here', 'coherent_history_drift_from_first_trusted3_anchor',
    'coherent_history_agrees_first_trusted3_anchor')
ORIGINAL_FIELDS = ('frame_number', 'stage', 'track_ids', 'history_UIDs', 'candidate_UIDs', 'bbox_cost',
    'motion_gate', 'enabled', 'active_rows', 'enough_history', 'lost_gap', 'chosen_raw_UID')
_BACKENDS = {}
_PUBLIC = OrderedDict()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def safe(value):
    path = Path(os.path.abspath(value))
    require(not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
                    for part in path.parts), '最终测试继续封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            require(not part.is_symlink() and not getattr(part.lstat(), 'st_file_attributes', 0) & 0x400,
                    '不跟随junction或符号链接')
    return path


def sha(path):
    digest = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def ref(path):
    return dict(path=str(safe(path)), sha256=sha(path))


def checked(reference):
    path = safe(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '原来源SHA改变：'+str(path))
    return path


def read_ref(reference):
    return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def rows_ref(reference):
    with gzip.open(checked(reference), 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_new(path, value):
    with safe(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def f32(value):
    require(type(value) in (int, float) and math.isfinite(value), '成本必须有限数值')
    result = struct.unpack('<f', struct.pack('<f', value))[0]
    require(math.isfinite(result), 'FP32成本非有限')
    return result


def assignment_record(matches, rows, columns, n, m):
    result = dict(matches=[[int(a), int(b)] for a, b in matches],
        unmatched_rows=[int(a) for a in rows], unmatched_columns=[int(b) for b in columns])
    matched_rows = [a for a, _ in result['matches']]
    matched_columns = [b for _, b in result['matches']]
    require(len(matched_rows) == len(set(matched_rows)) and len(matched_columns) == len(set(matched_columns))
        and len(result['unmatched_rows']) == len(set(result['unmatched_rows']))
        and len(result['unmatched_columns']) == len(set(result['unmatched_columns']))
        and set(matched_rows) | set(result['unmatched_rows']) == set(range(n))
        and set(matched_columns) | set(result['unmatched_columns']) == set(range(m))
        and not set(matched_rows) & set(result['unmatched_rows'])
        and not set(matched_columns) & set(result['unmatched_columns']), '原分配必须覆盖所有行列且一对一')
    return result


class Numeric:
    """只抽取原matching单个纯函数；不导入Ultralytics、Torch或任何模型加载器。"""
    def __init__(self, config):
        self.config = config
        source = checked(config['matching_source'])
        tree = ast.parse(source.read_text(encoding='utf-8'))
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'linear_assignment']
        require(len(nodes) == 1 and config['function'] == 'linear_assignment', '原唯一分配函数缺失')
        digest = hashlib.sha256(ast.dump(nodes[0], include_attributes=False).encode()).hexdigest()
        require(digest == config['function_AST_sha256'], '原分配函数AST不同')
        for key in ('numpy_entry', 'lap_entry', 'lap_binary'):
            checked(config[key])
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            self.np = importlib.import_module('numpy')
            self.lap = importlib.import_module('lap')
        finally:
            sys.dont_write_bytecode = previous
        require(self.np.__version__ == config['numpy_version'] == '2.2.6'
            and self.lap.__version__ == config['lap_version'] == '0.5.13', '固定数值版本改变')
        require(safe(self.np.__file__) == safe(config['numpy_entry']['path'])
            and safe(self.lap.__file__) == safe(config['lap_entry']['path']), '实际导入入口非冻结来源')
        binary = importlib.import_module(self.lap.lapjv.__module__)
        require(safe(binary.__file__) == safe(config['lap_binary']['path']), '实际lap二进制来源改变')
        namespace = {'np': self.np, 'lap': self.lap, '__name__': 'bound_original_linear_assignment_only'}
        exec(compile(ast.Module(body=[nodes[0]], type_ignores=[]), str(source), 'exec'), namespace)
        self.solve = namespace['linear_assignment']
        self.edge_cache = OrderedDict()
        self.calls = 0

    def assignment(self, values, threshold):
        matrix = self.np.asarray(values, dtype=self.np.float32)
        require(matrix.ndim == 2 and self.np.isfinite(matrix).all(), '原FP32成本矩阵维度或有限性不同')
        before = matrix.tobytes()
        match, rows, columns = self.solve(matrix, thresh=threshold, use_lap=True)
        require(matrix.tobytes() == before, '原纯分配修改了输入成本')
        self.calls += 1
        return assignment_record(match, rows, columns, *matrix.shape)

    def feasible(self, value, threshold):
        value = f32(value)
        key = (struct.pack('<f', value), threshold)
        if key in self.edge_cache:
            answer = self.edge_cache.pop(key)
            self.edge_cache[key] = answer
            return answer
        answer = self.assignment([[value]], threshold)['matches'] == [[0, 0]]
        self.edge_cache[key] = answer
        if len(self.edge_cache) > 65536:
            self.edge_cache.popitem(last=False)
        return answer

    def closure(self):
        for key in ('matching_source', 'numpy_entry', 'lap_entry', 'lap_binary'):
            checked(self.config[key])
        return dict(numeric_sources_unchanged=True, assignment_calls=self.calls,
            single_edge_cache_entries=len(self.edge_cache), single_edge_cache_capacity=65536,
            model_or_Torch_or_tracker_loaded=False, optimizer_updates=0)


def backend(cfg):
    key = hashlib.sha256(canonical(cfg['numeric']).encode()).hexdigest()
    if key not in _BACKENDS:
        _BACKENDS[key] = Numeric(cfg['numeric'])
    return _BACKENDS[key]


def event_shape(event):
    require(event['stage'] in (0, 1) and type(event['frame_number']) is int and event['frame_number'] > 0,
            '仅原主高分/未确认高分stage，低分第二stage没有原trace')
    n, m = len(event['track_ids']), len(event['candidate_UIDs'])
    require(n > 0 and m > 0 and len(set(event['track_ids'])) == n and len(set(event['candidate_UIDs'])) == m,
            '原trace只记录非空成本矩阵，不能补造空行')
    for key in ('bbox_cost', 'reference_cost', 'motion_gate', 'enabled'):
        require(len(event[key]) == n and all(len(row) == m for row in event[key]), '原矩阵维度改变：'+key)
    require(all(len(event[key]) == n for key in ('history_UIDs', 'active_rows', 'enough_history', 'lost_gap', 'chosen_raw_UID')),
            '原行元数据维度不同')
    require(all(type(value) is bool for key in ('motion_gate', 'enabled') for row in event[key] for value in row)
        and all(type(value) is bool for key in ('active_rows', 'enough_history', 'lost_gap') for value in event[key]),
        '原gate/行标志必须bool')
    require(all(f32(value) == value for row in event['reference_cost'] for value in row), '原reference_cost不是原FP32逐值值')
    require(event['GT_read'] is False, '原评分trace有GT输入标志')
    return n, m


def reconstruct_event(event, numeric):
    event_shape(event)
    threshold = .8 if event['stage'] == 0 else .7
    return numeric.assignment(event['reference_cost'], threshold)


def verify_saved_assignments(cfg, output):
    """先复核九份既存reference.assignment；不调用原评分，不把夹具当实际门禁。"""
    output = safe(output)
    require(not output.exists() and safe(cfg['output_root']) in output.parents, '数值收据必须独占新文件')
    output.parent.mkdir(parents=True, exist_ok=True)
    numeric = backend(cfg)
    selected = [unit for unit in cfg['units'] if unit['stage_assignment_reference'] is not None]
    require(len(selected) == 9 and len({unit['unit_id'] for unit in selected}) == 9, '必须全部九份既存参考')
    details = []
    for unit in selected:
        reference = unit['stage_assignment_reference']
        require(reference['record_path'] == 'new_T.reference.assignment'
            and reference['source_event_index'] == 'source_event_number', '既存reference精确字段不同')
        saved = iter(rows_ref(reference['events']))
        count = row_count = 0
        for event_number, event in enumerate(rows_ref(unit['trace'])):
            record = next(saved, None)
            require(record is not None and record['source_event_number'] == event_number
                and record['original_state'] == {key: event[key] for key in ORIGINAL_FIELDS}, '原事件次序/完整状态不同')
            require(record['job']['source_job_id'] == unit['unit_id'] and record['job']['group'] == 'T_RS'
                and all(record['job'][key] == unit[key] for key in ('sequence', 'fold', 'seed', 'pool')),
                '既存参考必须对应本原trace的T_RS来源，不能借另一fold/seed充数')
            expected_signature = hashlib.sha256(canonical([unit['sequence'], event['frame_number'], event['stage'],
                event['history_UIDs'], event['candidate_UIDs']]).encode()).hexdigest()
            require(record['state_signature'] == expected_signature and record['test_read'] is False
                and record['new_optimizer_updates'] == 0 and record['new_free_tracking'] is False, '既存状态签名或预算不同')
            value = record['new_T']['reference']
            require(value['recorded_actual_old_motion_cost'] == event['reference_cost']
                and value['threshold'] == (.8 if event['stage'] == 0 else .7)
                and value['origin'] == 'original_trace_recorded_actual_reference_cost_not_new_T_tracking',
                '只能原强motion记录成本，不用新T/影子成本')
            require(reconstruct_event(event, numeric) == value['assignment'], '当前原纯solver与既存reference分配逐值不同')
            count += 1
            row_count += len(event['track_ids'])
        require(next(saved, None) is None and count == reference['expected_events'] == unit['expected_stage_calls']
            and row_count == unit['expected_stage_rows'], '九份参考必须逐事件完整，不能只选非空评分或有利行')
        details.append(dict(unit_id=unit['unit_id'], sequence=unit['sequence'], trace=unit['trace'],
            saved_reference=reference, events=count, stage_rows=row_count, exact_original_assignment=True))
    result = dict(schema='bounded_error_decomposition_numeric_admission_v1',
        status='complete9_saved_stage_assignments_original_FP32_solver_exact_no_model', passed=True,
        source_units=9, source_unit_ids=[unit['unit_id'] for unit in selected], details=details,
        event_count=sum(d['events'] for d in details), stage_rows=sum(d['stage_rows'] for d in details),
        numeric_sources=cfg['numeric'], matching_source_provenance='current_installed_snapshot_not_historical_file_SHA',
        saved_actual_reference_assignments_exact=True, single_edge_feasibility='same_original_solver_1x1_FP32_no_epsilon',
        closure=numeric.closure(), model_loads=0, new_scores=0, new_free_tracking=0, new_TrackEval_runs=0,
        optimizer_updates=0, original_GT_coordinate_files_opened=False,
        saved_GT_derived_posthoc_metadata_loaded=True, GT_used_for_assignment=False,
        test_read=False, implementation=ref(__file__))
    write_new(output, result)
    return result


def public_source(unit):
    """仅加载原标签ID与公共账本，不读媒体、预测缓存或GT坐标文件。"""
    key = canonical(dict(labels=unit['labels'], ledgers=unit['source_ledgers']))
    if key in _PUBLIC:
        result = _PUBLIC.pop(key)
        _PUBLIC[key] = result
        return result
    ledgers = unit['source_ledgers']
    summary = read_ref(ledgers['sequence_summary'])
    require(summary['status'] == 'complete_sequence_raw_output_posthoc_policy_ledger'
        and summary['sequence'] == unit['sequence'] and summary['source_cache'] == unit['source_cache'], '公共源账本身份不同')
    for name in ('raw_ledger', 'GT_opportunity_ledger', 'frame_ledger'):
        require(ledgers[name] == summary['artifacts'][name], '公共ledger未按完成summary精确绑定')
    label_file = read_ref(unit['labels'])
    require(label_file['GT_input_to_models'] is False, '只允许原GT后验标签文件')
    labels = label_file['labels']
    raw = {}
    positives = defaultdict(list)
    for record in rows_ref(ledgers['raw_ledger']):
        uid = record['uid']
        require(record['sequence'] == unit['sequence'] and uid not in raw and uid in labels, 'raw源/UID/标签映射不全')
        label = labels[uid]
        require(label['frame_number'] == record['frame_number'], '后验标签帧号不同')
        if label['state'] == 'matched':
            require(record['raw_to_GT']['state'] == 'mutual_unique'
                and record['raw_to_GT']['mutual_unique_id'] == label['gt_id'], '原trusted标签与公共几何代理不同')
            positives[(record['frame_number'], label['gt_id'])].append(uid)
        raw[uid] = record
    require(len(raw) == summary['source_counts']['raw_detections'] and set(raw) == set(labels), '完整raw/标签分母不符')
    GT = {}
    for record in rows_ref(ledgers['GT_opportunity_ledger']):
        coordinate = (record['frame_number'], record['gt_id'])
        require(record['sequence'] == unit['sequence'] and coordinate not in GT,
                '公共GT presence同帧身份重复或来源不同')
        GT[coordinate] = record
    require(len(GT) == summary['source_counts']['GT_rows'], '固定GT presence分母缺失')
    with checked(ledgers['frame_ledger']).open(encoding='utf-8', newline='') as stream:
        frame_rows = list(csv.DictReader(stream))
    require([int(r['frame_number']) for r in frame_rows] == list(range(1, summary['source_counts']['source_frames']+1))
        and sum(int(r['GT_rows']) for r in frame_rows) == len(GT), '公共全帧/GT presence计数不同')
    result = dict(labels=labels, raw=raw, positives=dict(positives), GT=GT,
        source_frames=summary['source_counts']['source_frames'], summary=summary)
    _PUBLIC[key] = result
    while len(_PUBLIC) > 2:
        _PUBLIC.popitem(last=False)
    return result


def history_status(history, labels):
    values = [labels.get(uid) for uid in history]
    if not values or any(value is None or value['state'] != 'matched' for value in values):
        return None, 'history_unknown'
    identities = {value['gt_id'] for value in values}
    return (next(iter(identities)), 'trusted_consistent_history') if len(identities) == 1 else (None, 'mixed_trusted_history')


def candidate_label(query, label):
    if label['state'].startswith('unknown'):
        return None
    return int(label['state'] == 'matched' and label['gt_id'] == query)


def anchor_condition(track_id, history, query, status, event, anchors):
    """首个可信三观测只作相对锚点，不声称整条轨迹GT身份或污染因果。"""
    established = False
    if track_id not in anchors and len(history) == 3 and status == 'trusted_consistent_history':
        anchors[track_id] = dict(gt_id=query, frame_number=event['frame_number'], stage=event['stage'], history_UIDs=list(history))
        established = True
    anchor = anchors.get(track_id)
    if status != 'trusted_consistent_history':
        state = status
    elif anchor is None:
        state = 'no_trusted3_anchor_yet'
    elif established:
        state = 'trusted3_anchor_established_here'
    elif query != anchor['gt_id']:
        state = 'coherent_history_drift_from_first_trusted3_anchor'
    else:
        state = 'coherent_history_agrees_first_trusted3_anchor'
    return dict(state=state, first_trusted3_anchor=anchor,
        interpretation='relative_posthoc_history_consistency_not_full_MOT_identity_or_causal_pollution')


def cutoff_boundary(value, cutoff):
    value = f32(value)
    return dict(cost=value, cutoff_python_float=cutoff, cutoff_float32=f32(cutoff),
        equal_float32_cutoff=value == f32(cutoff), equal_python_cutoff=value == cutoff,
        compared_to_python_cutoff='less' if value < cutoff else ('greater' if value > cutoff else 'equal'),
        epsilon_used=False)


def classify_row(event, row_index, source, assignment, numeric, anchors):
    history = event['history_UIDs'][row_index]
    labels = source['labels']
    require(all(uid in labels and uid in source['raw'] for uid in history+event['candidate_UIDs']), '原UID缺少公共来源/标签')
    query, status = history_status(history, labels)
    frame, track = event['frame_number'], event['track_ids'][row_index]
    history_frames = [labels[uid]['frame_number'] for uid in history]
    require(len(history) <= 3 and history_frames == sorted(set(history_frames))
        and all(value < frame for value in history_frames)
        and all(labels[uid]['frame_number'] == frame for uid in event['candidate_UIDs']),
        '原history必须严格过去，stage候选必须当前帧，不读未来')
    anchor = anchor_condition(track, history, query, status, event, anchors)
    present = query is not None and (frame, query) in source['GT']
    raw_positive = source['positives'].get((frame, query), []) if present else []
    geometry_candidates = source['GT'][(frame, query)]['candidate_raw_UIDs'] if present else []
    values = {j: candidate_label(query, labels[uid]) for j, uid in enumerate(event['candidate_UIDs'])} if present else {}
    positive = [j for j, value in values.items() if value == 1]
    negative = [j for j, value in values.items() if value == 0]
    unknown = [j for j, value in values.items() if value is None]
    active = event['active_rows'][row_index]
    effective_positive = [j for j in positive if not active or event['enabled'][row_index][j]]
    costs = event['reference_cost'][row_index]
    cutoff = .8 if event['stage'] == 0 else .7
    feasible = [j for j in effective_positive if numeric.feasible(costs[j], cutoff)] if present else []
    row_assignment = dict(assignment['matches']).get(row_index)
    column_owner = {j: i for i, j in assignment['matches']}
    selected_label = values.get(row_assignment) if present and row_assignment is not None else None
    if not present:
        native = None
    elif row_assignment is None:
        native = 'unmatched_stage'
    elif selected_label is None:
        native = 'unknown_candidate'
    else:
        native = 'same_trusted_GT' if selected_label else 'other_trusted_GT_or_far_unmatched'
    best_positive = min((costs[j] for j in feasible), default=None)
    best_negative = min((costs[j] for j in negative), default=None)
    best_unknown = min((costs[j] for j in unknown), default=None)
    unknown_competes = best_positive is not None and best_unknown is not None and best_unknown <= best_positive
    negative_lower = best_positive is not None and best_negative is not None and best_negative < best_positive
    tie = best_positive is not None and any(costs[j] == best_positive for j in negative+unknown)
    conditions = dict(history_all_trusted_consistent=status == 'trusted_consistent_history',
        mixed_trusted_history=status == 'mixed_trusted_history', current_GT_present=present,
        trusted_positive_raw_present=bool(raw_positive), any_raw_IoU05_to_query=bool(geometry_candidates),
        positive_in_native_stage=bool(positive), enough_history=event['enough_history'][row_index],
        row_intervened=active, positive_motion_gate=any(event['motion_gate'][row_index][j] for j in positive),
        positive_effectively_enabled=bool(effective_positive), positive_single_edge_feasible=bool(feasible),
        stage_selected_trusted_positive=native == 'same_trusted_GT', known_negative_strictly_lower_cost=negative_lower,
        unknown_cost_competes=unknown_competes, positive_negative_or_unknown_min_cost_tie=tie,
        correct_column_assigned_to_other_row=any(j in column_owner and column_owner[j] != row_index for j in feasible),
        coherent_history_drift_from_anchor=anchor['state'] == 'coherent_history_drift_from_first_trusted3_anchor')
    if status != 'trusted_consistent_history':
        first = status
    elif not present:
        first = 'current_GT_absent'
    elif not raw_positive:
        first = 'raw_geometry_ambiguous' if geometry_candidates else 'no_raw_geometry_candidate'
    elif not positive:
        first = 'positive_raw_not_in_stage'
    elif not event['enough_history'][row_index]:
        first = 'history_fewer_than3'
    elif not active:
        first = 'row_not_intervened'
    elif not effective_positive:
        first = 'positive_outside_effective_gate'
    elif not feasible:
        first = 'no_single_edge_feasible_positive'
    elif native == 'same_trusted_GT':
        first = 'reference_stage_selected_correct'
    elif native == 'unknown_candidate' or unknown_competes:
        first = 'unknown_competition_or_assignment'
    elif negative_lower:
        first = 'known_negative_cost_lower'
    elif tie:
        first = 'minimum_cost_tie'
    elif best_positive is not None:
        first = 'global_competition_or_solver_unmatched'
    else:
        first = 'unclassified_preserved'
    require(first in FIRST_STOPS, '首个未满足标签未登记')
    return dict(frame_number=frame, stage=event['stage'], row_index=row_index, track_id=track,
        history_UIDs=history, history_labels=[dict(uid=uid, **labels[uid]) for uid in history],
        history_status=status, query_GT_id=query, history_anchor=anchor,
        joint_conditions=conditions, first_stop=first, first_stop_is_cause=False,
        decision_path='learned_active' if active else 'bbox_nonintervened',
        native_stage_outcome=native, native_stage_outcome_denominator='trusted_consistent_history_and_current_GT_present',
        raw_positive_UIDs=raw_positive, raw_positive_scores_float32=[source['raw'][uid]['score_float32'] for uid in raw_positive],
        stage_candidate_UIDs=event['candidate_UIDs'], positive_columns=positive, known_negative_columns=negative,
        unknown_columns=unknown, effective_positive_columns=effective_positive, single_edge_feasible_positive_columns=feasible,
        reference_cost_row=costs, cutoff=cutoff,
        positive_cost_boundaries=[dict(column=j, **cutoff_boundary(costs[j], cutoff)) for j in positive],
        minimum_feasible_positive_cost=best_positive, minimum_known_negative_cost=best_negative, minimum_unknown_cost=best_unknown,
        reconstructed_stage_assignment_column=row_assignment,
        reconstructed_stage_assignment_UID=event['candidate_UIDs'][row_assignment] if row_assignment is not None else None,
        stage_assignment_source='original_recorded_FP32_reference_cost_original_pure_solver_no_new_scoring',
        frame_end_chosen_raw_UID=event['chosen_raw_UID'][row_index],
        frame_end_UID_is_stage_assignment=False, internal_lifecycle_or_low_score_stage='unknown_not_recorded_in_trace',
        GT_used_only_posthoc=True, optimizer_updates=0)


def analyze_unit(cfg, unit, output):
    require(unit in cfg['units'] and unit['pool'] == 'balanced' and cfg['test_sealed'] is True,
            '必须完整balanced27预登记单位，测试封存')
    receipt = read_ref(unit['receipt'])
    original_receipt = read_ref(unit['original_tracking_receipt'])
    require(receipt['status'] == original_receipt['status'] == 'complete' and receipt['trace'] == unit['trace']
        and receipt['job'] == unit['job'] and receipt['job']['reference_motion'] == original_receipt['job']
        and receipt['mot_sha256'] == original_receipt['mot_sha256'] and receipt['audit'] == original_receipt['audit'],
        '原common trace必须与实际强motion参考MOT/audit完全相同')
    admission = read_ref(cfg['numeric_admission'])
    require(admission['status'] == 'complete9_saved_stage_assignments_original_FP32_solver_exact_no_model'
        and admission['passed'] is True and admission['source_units'] == 9
        and admission['numeric_sources'] == cfg['numeric'], '先完成九份既存分配的独立数值准入')
    output = safe(output)
    require(not output.exists() and safe(cfg['output_root']) in output.parents, '单位输出必须独占新目录')
    output.mkdir(parents=True)
    write_new(output/'started.json', dict(status='started_not_committed', unit_id=unit['unit_id'],
        numeric_admission=cfg['numeric_admission'], trace=unit['trace'], optimizer_updates=0))
    try:
        source = public_source(unit)
        numeric = backend(cfg)
        anchors = {}
        first_counts = Counter({key: 0 for key in FIRST_STOPS})
        outcome_counts = Counter({key: 0 for key in OUTCOMES})
        joint_counts = Counter()
        anchor_counts = Counter({key: 0 for key in ANCHOR_STATES})
        paths = Counter(learned_active=0, bbox_nonintervened=0)
        stage_calls = stage_rows = native_rows = boundary_rows = known_active = 0
        target = output/'all_stage_rows.jsonl.gz'
        with target.open('xb') as file:
            with gzip.GzipFile(filename='', mode='wb', fileobj=file, mtime=0) as stream:
                previous = (0, -1)
                for event_number, event in enumerate(rows_ref(unit['trace'])):
                    n, _ = event_shape(event)
                    coordinate = (event['frame_number'], event['stage'])
                    require(coordinate > previous, '原stage事件必须按frame/stage唯一递增')
                    previous = coordinate
                    assignment = reconstruct_event(event, numeric)
                    for row_index in range(n):
                        record = classify_row(event, row_index, source, assignment, numeric, anchors)
                        record.update(unit_id=unit['unit_id'], sequence=unit['sequence'], fold=unit['fold'], seed=unit['seed'],
                            pool='balanced', source_event_number=event_number)
                        stream.write((canonical(record)+'\n').encode('utf-8'))
                        first_counts[record['first_stop']] += 1
                        joint_counts.update({key: int(value) for key, value in record['joint_conditions'].items()})
                        anchor_counts[record['history_anchor']['state']] += 1
                        paths[record['decision_path']] += 1
                        if record['native_stage_outcome'] is not None:
                            native_rows += 1
                            outcome_counts[record['native_stage_outcome']] += 1
                            known_active += int(record['joint_conditions']['row_intervened'])
                        boundary_rows += any(value['equal_float32_cutoff'] for value in record['positive_cost_boundaries'])
                    stage_calls += 1
                    stage_rows += n
        require(stage_calls == unit['expected_stage_calls'] and stage_rows == unit['expected_stage_rows']
            and sum(first_counts.values()) == stage_rows and sum(outcome_counts.values()) == native_rows,
            '全部原stage-row/事件或互斥分母不齐')
        row_artifact = dict(ref(target), rows=stage_rows)
        counts = dict(all_stage_rows=stage_rows, known_history_current_present=native_rows,
            known_active_current_present=known_active, positive_FP32_cutoff_boundary_rows=boundary_rows,
            **{'denominator/known_active_current_present_rows': known_active})
        for prefix, values in (('first_stop', first_counts), ('joint', joint_counts), ('anchor', anchor_counts),
                               ('native_outcome', outcome_counts), ('decision_path', paths)):
            counts.update({prefix+'/'+key: int(value) for key, value in values.items()})
        result = dict(schema='bounded_error_decomposition_unit_v1',
            status='complete_balanced_unit_all_stage_rows_posthoc_conditions_not_causes', unit_id=unit['unit_id'],
            sequence=unit['sequence'], fold=unit['fold'], seed=unit['seed'], pool='balanced',
            trace=unit['trace'], receipt=unit['receipt'], labels=unit['labels'], source_ledgers=unit['source_ledgers'],
            original_tracking_receipt=unit['original_tracking_receipt'], numeric_admission=cfg['numeric_admission'],
            events=stage_calls, stage_calls=stage_calls, stage_rows=stage_rows, counts=counts,
            artifacts=dict(row_ledger=row_artifact), first_stop_counts=dict(first_counts),
            joint_condition_counts=dict(joint_counts), decision_path_counts=dict(paths),
            native_stage_outcome_counts=dict(outcome_counts), native_stage_outcome_rows=native_rows,
            known_active_current_present_rows=known_active,
            history_anchor_condition_counts=dict(anchor_counts), first_trusted3_anchors=len(anchors),
            positive_FP32_cutoff_boundary_rows=boundary_rows,
            all_stage_rows=row_artifact, closure=numeric.closure(),
            denominator='all_original_recorded_nonempty_stage_rows_not_independent_matches_or_all_frames',
            source_reference_cost_is_authority=True, shadow_logits_used=False, GT_coordinate_files_opened=False,
            GT_posthoc_label_IDs_loaded=True, GT_used_only_posthoc=True, first_stop_is_cause=False,
            unrecorded_low_stage_empty_matrices_and_lifecycle='unknown_not_recorded',
            model_loads=0, new_scores=0, new_free_tracking=0, new_TrackEval_runs=0, optimizer_updates=0,
            cache_or_media_read=False, test_read=False, implementation=ref(__file__))
        write_new(output/'summary.json', result)
        return result
    except BaseException as error:
        write_new(output/'failure.json', dict(status='failed_partial_preserved_no_retry', error=repr(error),
            unit_id=unit['unit_id'], optimizer_updates=0, test_read=False))
        raise
