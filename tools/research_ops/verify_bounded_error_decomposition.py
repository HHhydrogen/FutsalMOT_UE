"""有限错误条件账本独立终验；不再求解分配、不读取GT坐标/缓存/模型。"""
import argparse
import ast
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import traceback

R = Path('D:/projects/FutsalMOT_Research'); EXP = R/'pose/bounded_error_decomposition_a01'
PANELS = ('original_heldout', 'old_external')
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
EXTERNAL = ('v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
FOLDS = ('game4', 'game6', 'game9'); SEEDS = (20261024, 20261025, 20261026)
FIRST_STOPS = ('history_unknown', 'mixed_trusted_history', 'current_GT_absent', 'raw_geometry_ambiguous',
    'no_raw_geometry_candidate', 'positive_raw_not_in_stage', 'history_fewer_than3', 'row_not_intervened',
    'positive_outside_effective_gate', 'no_single_edge_feasible_positive', 'reference_stage_selected_correct',
    'unknown_competition_or_assignment', 'known_negative_cost_lower', 'minimum_cost_tie',
    'global_competition_or_solver_unmatched', 'unclassified_preserved')
OUTCOMES = ('same_trusted_GT', 'other_trusted_GT_or_far_unmatched', 'unknown_candidate', 'unmatched_stage')
ANCHOR_STATES = ('history_unknown', 'mixed_trusted_history', 'no_trusted3_anchor_yet', 'trusted3_anchor_established_here',
    'coherent_history_drift_from_first_trusted3_anchor', 'coherent_history_agrees_first_trusted3_anchor')
STATUS = 'complete27_traces320752_rows_all_conditions_anchors_intervals_and_exit_verified'


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(path):
    path = Path(path); require(path.is_absolute(), '独立终验必须绝对路径'); path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts), '研究物理根越界或测试未封存')
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            info = p.lstat(); require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return path


def sha(path):
    digest = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for value in iter(lambda: stream.read(1048576), b''): digest.update(value)
    return digest.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path']); require(path.is_file() and sha(path) == value['sha256'], '原来源或新结果SHA改变：'+str(path)); return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def rows(reference):
    with gzip.open(checked(reference), 'rt', encoding='utf-8') as stream:
        for line in stream:
            require(bool(line.strip()), '完整账本不能以空行替代事件'); yield json.loads(line)


def f32(value):
    require(type(value) in (int, float) and math.isfinite(value), '原FP32成本必须有限')
    return struct.unpack('<f', struct.pack('<f', value))[0]


def history_identity(record):
    labels = record['history_labels']; history = record['history_UIDs']
    require([v['uid'] for v in labels] == history and len(history) <= 3, '原历史UID/标签身份或长度不同')
    if not labels or any(v['state'] != 'matched' for v in labels): return None, 'history_unknown'
    identities = {v['gt_id'] for v in labels}
    return (next(iter(identities)), 'trusted_consistent_history') if len(identities) == 1 else (None, 'mixed_trusted_history')


def check_anchor(record, anchors):
    query, status = history_identity(record); track = record['track_id']; frame = record['frame_number']; stage = record['stage']
    require(record['query_GT_id'] == query and record['history_status'] == status, '当前历史一致标签被误称全轨迹ID')
    created = False
    if track not in anchors and len(record['history_UIDs']) == 3 and status == 'trusted_consistent_history':
        anchors[track] = dict(gt_id=query, frame_number=frame, stage=stage, history_UIDs=record['history_UIDs']); created = True
    anchor = anchors.get(track)
    state = (status if status != 'trusted_consistent_history' else 'no_trusted3_anchor_yet' if anchor is None else
        'trusted3_anchor_established_here' if created else 'coherent_history_drift_from_first_trusted3_anchor' if query != anchor['gt_id'] else
        'coherent_history_agrees_first_trusted3_anchor')
    require(record['history_anchor'] == dict(state=state, first_trusted3_anchor=anchor,
        interpretation='relative_posthoc_history_consistency_not_full_MOT_identity_or_causal_pollution'), 'anchor不是本unit本轨迹最早trusted3，或冒称因果污染')
    return state


def expected_first(record):
    c = record['joint_conditions']; status = record['history_status']
    if status != 'trusted_consistent_history': return status
    if not c['current_GT_present']: return 'current_GT_absent'
    if not c['trusted_positive_raw_present']: return 'raw_geometry_ambiguous' if c['any_raw_IoU05_to_query'] else 'no_raw_geometry_candidate'
    if not c['positive_in_native_stage']: return 'positive_raw_not_in_stage'
    if not c['enough_history']: return 'history_fewer_than3'
    if not c['row_intervened']: return 'row_not_intervened'
    if not c['positive_effectively_enabled']: return 'positive_outside_effective_gate'
    if not c['positive_single_edge_feasible']: return 'no_single_edge_feasible_positive'
    if c['stage_selected_trusted_positive']: return 'reference_stage_selected_correct'
    if record['native_stage_outcome'] == 'unknown_candidate' or c['unknown_cost_competes']: return 'unknown_competition_or_assignment'
    if c['known_negative_strictly_lower_cost']: return 'known_negative_cost_lower'
    if c['positive_negative_or_unknown_min_cost_tie']: return 'minimum_cost_tie'
    if record['minimum_feasible_positive_cost'] is not None: return 'global_competition_or_solver_unmatched'
    return 'unclassified_preserved'


def validate_event_records(event, records, unit, event_number, anchors):
    n, m = len(event['track_ids']), len(event['candidate_UIDs'])
    require(n > 0 and m > 0 and len(records) == n and len(set(event['track_ids'])) == n and len(set(event['candidate_UIDs'])) == m, '全部原非空stage行/列分母不同')
    require(event['GT_read'] is False and len(event['lost_gap']) == n and all(type(v) is bool for v in event['lost_gap']), '原GT-free trace和lost_gap源字段必须保留，不能从MOT补造')
    chosen = [r['reconstructed_stage_assignment_column'] for r in records if r['reconstructed_stage_assignment_column'] is not None]
    require(len(chosen) == len(set(chosen)) and all(type(c) is int and 0 <= c < m for c in chosen), '阶段分配必须一对一，不能把帧末UID当本stage选择')
    owners = {r['reconstructed_stage_assignment_column']: i for i, r in enumerate(records) if r['reconstructed_stage_assignment_column'] is not None}
    for i, record in enumerate(records):
        require(all(record[k] == unit[k] for k in ('unit_id', 'sequence', 'fold', 'seed')) and record['pool'] == 'balanced'
            and record['source_event_number'] == event_number and record['row_index'] == i
            and record['frame_number'] == event['frame_number'] and record['stage'] == event['stage']
            and record['track_id'] == event['track_ids'][i] and record['history_UIDs'] == event['history_UIDs'][i]
            and record['stage_candidate_UIDs'] == event['candidate_UIDs'] and record['reference_cost_row'] == event['reference_cost'][i],
            '每一原row/UID/实际reference_cost必须原序保留')
        costs = record['reference_cost_row']; require(len(costs) == m and all(f32(v) == v for v in costs), '实际成本不是原FP32值')
        cutoff = .8 if record['stage'] == 0 else .7
        require(record['cutoff'] == cutoff and record['stage_assignment_source'] == 'original_recorded_FP32_reference_cost_original_pure_solver_no_new_scoring'
            and record['frame_end_chosen_raw_UID'] == event['chosen_raw_UID'][i] and record['frame_end_UID_is_stage_assignment'] is False
            and record['internal_lifecycle_or_low_score_stage'] == 'unknown_not_recorded_in_trace'
            and record['first_stop_is_cause'] is False and record['GT_used_only_posthoc'] is True and record['optimizer_updates'] == 0, 'GT/分配重建/未记录边界改变')
        state = check_anchor(record, anchors); c = record['joint_conditions']; require(all(type(v) is bool for v in c.values()), '联合条件必须真布尔而非筛样标签')
        present = c['current_GT_present']; require(not present or record['query_GT_id'] is not None, '未知历史不能构造当前GT身份')
        positive, negative, unknown = [record[k] for k in ('positive_columns', 'known_negative_columns', 'unknown_columns')]
        all_columns = positive+negative+unknown
        require(all(type(v) is int and 0 <= v < m for v in all_columns) and len(all_columns) == len(set(all_columns))
            and (set(all_columns) == set(range(m)) if present else not all_columns), '正/负/unknown必须完整且互斥，未在当前GT时不伪造标签')
        effective = [j for j in positive if not event['active_rows'][i] or event['enabled'][i][j]]
        feasible = record['single_edge_feasible_positive_columns']
        require(record['effective_positive_columns'] == effective and len(feasible) == len(set(feasible))
            and set(feasible) <= set(effective), '有效gate或已记原solver单边可行列不是正确子集')
        # 单边可行性不在终验重求：保存准入与producer数值闭包，核其完整列/实际成本用途。
        best = min((costs[j] for j in feasible), default=None); neg = min((costs[j] for j in negative), default=None); unk = min((costs[j] for j in unknown), default=None)
        require(record['minimum_feasible_positive_cost'] == best and record['minimum_known_negative_cost'] == neg
            and record['minimum_unknown_cost'] == unk, '最低实际代价不能用影子logit替代')
        selected = record['reconstructed_stage_assignment_column']
        expected_outcome = (None if not present else 'unmatched_stage' if selected is None else 'same_trusted_GT' if selected in positive else
            'unknown_candidate' if selected in unknown else 'other_trusted_GT_or_far_unmatched')
        require(record['reconstructed_stage_assignment_UID'] == (event['candidate_UIDs'][selected] if selected is not None else None)
            and record['native_stage_outcome'] == expected_outcome and record['native_stage_outcome_denominator'] == 'trusted_consistent_history_and_current_GT_present', '原stage输出的所有正确/负/unknown/未匹配不可删改')
        expected = dict(history_all_trusted_consistent=record['history_status'] == 'trusted_consistent_history',
            mixed_trusted_history=record['history_status'] == 'mixed_trusted_history', current_GT_present=present,
            trusted_positive_raw_present=bool(record['raw_positive_UIDs']), any_raw_IoU05_to_query=c['any_raw_IoU05_to_query'],
            positive_in_native_stage=bool(positive), enough_history=event['enough_history'][i], row_intervened=event['active_rows'][i],
            positive_motion_gate=any(event['motion_gate'][i][j] for j in positive), positive_effectively_enabled=bool(effective),
            positive_single_edge_feasible=bool(feasible), stage_selected_trusted_positive=expected_outcome == 'same_trusted_GT',
            known_negative_strictly_lower_cost=best is not None and neg is not None and neg < best,
            unknown_cost_competes=best is not None and unk is not None and unk <= best,
            positive_negative_or_unknown_min_cost_tie=best is not None and any(costs[j] == best for j in negative+unknown),
            correct_column_assigned_to_other_row=any(j in owners and owners[j] != i for j in feasible),
            coherent_history_drift_from_anchor=state == 'coherent_history_drift_from_first_trusted3_anchor')
        require(c == expected and record['decision_path'] == ('learned_active' if c['row_intervened'] else 'bbox_nonintervened'), '联合/active/bbox条件分层与原实际状态不同')
        boundaries = [dict(column=j, cost=f32(costs[j]), cutoff_python_float=cutoff, cutoff_float32=f32(cutoff),
            equal_float32_cutoff=f32(costs[j]) == f32(cutoff), equal_python_cutoff=f32(costs[j]) == cutoff,
            compared_to_python_cutoff='less' if costs[j] < cutoff else 'greater' if costs[j] > cutoff else 'equal', epsilon_used=False) for j in positive]
        require(record['positive_cost_boundaries'] == boundaries and record['first_stop'] == expected_first(record)
            and record['first_stop'] in FIRST_STOPS, '原FP32边界/事前首停顺序不一致或自加epsilon')


def validate_coverage(inventory):
    require(inventory['schema'] == 'bounded_error_decomposition_inventory_v1'
        and inventory['status'] == 'complete_metadata_inventory27_existing_trace63_missing_no_cache_GT_model_or_tracking', '必须已验原来源盘点')
    units, missing = inventory['units'], inventory['missing_trace_units']; key = lambda v: (v['sequence'], v['fold'], v['seed'])
    expected = {(seq, fold, seed) for fold in FOLDS for seed in SEEDS for seq in (next(s for s, f in OLD.items() if f == fold), *EXTERNAL)}
    require(len(units) == 27 and {key(u) for u in units} == expected and len({u['unit_id'] for u in units}) == 27
        and all(u['pool'] == 'balanced' for u in units) and sum(u['expected_stage_rows'] for u in units) == 320752
        and sum(u['expected_stage_calls'] for u in units) == 24863 and sum(u['stage_assignment_reference'] is not None for u in units) == 9,
        '完整balanced27/24863非空stage/320752row/首seed9参考不可筛选')
    require(len(inventory['sources']) == 12 and len(inventory['strong_units']) == 90 and len(missing) == 63
        and len({key(u) for u in missing}) == 63 and not ({key(u) for u in units} & {key(u) for u in missing})
        and {key(u) for u in units+missing} == {key(u) for u in inventory['strong_units']}
        and all(u['sequence'] in inventory['panels']['seven_observed'] and u['internal_candidate_or_score_or_lifecycle'] == 'unknown' for u in missing),
        '新七场63无trace必须unknown，不得补跑或从MOT捏造内部状态')


def verify_unit(cfg, unit, summary_path):
    summary = read(summary_path)
    require(summary['schema'] == 'bounded_error_decomposition_unit_v1'
        and summary['status'] == 'complete_balanced_unit_all_stage_rows_posthoc_conditions_not_causes'
        and all(summary[k] == unit[k] for k in ('unit_id', 'sequence', 'fold', 'seed', 'pool', 'trace', 'receipt', 'labels', 'source_ledgers', 'original_tracking_receipt'))
        and summary['numeric_admission'] == cfg['numeric_admission'], '原unit/数据/实际数值准入来源不同')
    require(summary['source_reference_cost_is_authority'] is True and summary['shadow_logits_used'] is False
        and summary['GT_coordinate_files_opened'] is False and summary['GT_posthoc_label_IDs_loaded'] is True
        and summary['GT_used_only_posthoc'] is True and summary['first_stop_is_cause'] is False
        and summary['unrecorded_low_stage_empty_matrices_and_lifecycle'] == 'unknown_not_recorded'
        and all(summary[k] == 0 for k in ('model_loads', 'new_scores', 'new_free_tracking', 'new_TrackEval_runs', 'optimizer_updates'))
        and summary['cache_or_media_read'] is False and summary['test_read'] is False, '只能有界后验观察条件，不是因果或新追踪')
    saved = iter(rows(summary['all_stage_rows'])); anchors = {}; seen = set(); first = Counter({k: 0 for k in FIRST_STOPS})
    outcomes = Counter({k: 0 for k in OUTCOMES}); joint = Counter(); states = Counter({k: 0 for k in ANCHOR_STATES})
    paths = Counter(learned_active=0, bbox_nonintervened=0); calls = nrows = native = boundary = known_active = 0
    previous = (0, -1)
    try:
        for event_number, event in enumerate(rows(unit['trace'])):
            coordinate = event['frame_number'], event['stage']; require(coordinate > previous, '原事件顺序必须frame/stage唯一递增'); previous = coordinate
            records = []
            for _ in event['track_ids']:
                value = next(saved, None); require(value is not None, '完整stage-row缺失'); records.append(value)
            validate_event_records(event, records, unit, event_number, anchors)
            for record in records:
                key = unit['trace']['sha256'], record['frame_number'], record['stage'], record['track_id']; require(key not in seen, '同一原状态不能复制充样本'); seen.add(key)
                first[record['first_stop']] += 1; joint.update({k: int(v) for k, v in record['joint_conditions'].items()})
                states[record['history_anchor']['state']] += 1; paths[record['decision_path']] += 1
                if record['native_stage_outcome'] is not None:
                    native += 1; outcomes[record['native_stage_outcome']] += 1; known_active += int(record['joint_conditions']['row_intervened'])
                boundary += any(v['equal_float32_cutoff'] for v in record['positive_cost_boundaries'])
            calls += 1; nrows += len(records)
        require(next(saved, None) is None, '原范围外还有额外条件行')
    finally: saved.close()
    require(calls == unit['expected_stage_calls'] == summary['stage_calls'] and nrows == unit['expected_stage_rows'] == summary['stage_rows'] == summary['all_stage_rows']['rows']
        and sum(first.values()) == nrows and summary['first_stop_counts'] == dict(first) and summary['joint_condition_counts'] == dict(joint)
        and summary['native_stage_outcome_counts'] == dict(outcomes) and summary['native_stage_outcome_rows'] == native
        and summary['history_anchor_condition_counts'] == dict(states) and summary['first_trusted3_anchors'] == len(anchors)
        and summary['decision_path_counts'] == dict(paths) and summary['positive_FP32_cutoff_boundary_rows'] == boundary, '全部计数/unknown/首停/anchor分母不闭合')
    counts = dict(all_stage_rows=nrows, known_history_current_present=native, known_active_current_present=known_active,
        positive_FP32_cutoff_boundary_rows=boundary, **{'denominator/known_active_current_present_rows': known_active})
    for prefix, values in [('first_stop', first), ('joint', joint), ('anchor', states), ('native_outcome', outcomes), ('decision_path', paths)]:
        counts.update({prefix+'/'+key: value for key, value in values.items()})
    require(summary['events'] == calls and summary['counts'] == counts and summary['known_active_current_present_rows'] == known_active
        and summary['artifacts']['row_ledger'] == summary['all_stage_rows'], '原完整counts平铺/事件及账本别名不同')
    require(summary['closure']['numeric_sources_unchanged'] is True and summary['closure']['model_or_Torch_or_tracker_loaded'] is False
        and summary['closure']['optimizer_updates'] == 0 and summary['closure']['single_edge_cache_capacity'] == 65536
        and 0 <= summary['closure']['single_edge_cache_entries'] <= 65536, 'producer原数值来源/有界缓存闭包缺失')
    return dict(unit_id=unit['unit_id'], summary=ref(summary_path), stage_calls=calls, stage_rows=nrows,
        all_rows_and_joint_first_stop_unknown_anchor_counts_verified=True, assignment_or_edge_solver_rerun=False)


def same(actual, expected):
    if isinstance(expected, bool) or expected is None: require(actual is expected, '布尔/null统计边界不同')
    elif isinstance(expected, (int, float)):
        require(type(actual) in (int, float) and math.isfinite(actual) and abs(actual-expected) <= 1e-8, '数值序列化核对不同；1e-8不是性能界限')
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), '完整统计字段不同')
        for key, value in expected.items(): same(actual[key], value)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), '完整来源/统计数组长度不同')
        for a, b in zip(actual, expected): same(a, b)
    else: require(actual == expected, '来源标识/统计声明不同')


def condition_tables(cfg, summaries, inventory, interval):
    keys = sorted({k for value in summaries.values() for k in value['counts']}); unit_rows = []; rates = {}
    leaves = ('positive_outside_effective_gate', 'no_single_edge_feasible_positive', 'known_negative_cost_lower',
        'minimum_cost_tie', 'global_competition_or_solver_unmatched', 'unknown_competition_or_assignment', 'reference_stage_selected_correct')
    for uid in cfg['unit_order']:
        value = summaries[uid]; count = value['counts']; rates[uid] = {}
        for key in keys:
            if key.startswith('denominator/'): continue
            denominator = value['native_stage_outcome_rows'] if key.startswith('native_outcome/') else value['stage_rows']
            rates[uid][key] = 100*count.get(key, 0)/denominator if denominator else None
        for leaf in leaves:
            n = value['known_active_current_present_rows']
            rates[uid]['active_current_present/'+leaf] = 100*count.get('first_stop/'+leaf, 0)/n if n else None
        unit_rows.append(dict(unit_id=uid, sequence=value['sequence'], fold=value['fold'], seed=value['seed'], events=value['events'],
            stage_rows=value['stage_rows'], known_active_current_present_rows=value['known_active_current_present_rows'],
            native_stage_outcome_rows=value['native_stage_outcome_rows'], **{key: count.get(key, 0) for key in keys}))
    rate_keys = sorted(next(iter(rates.values()))); match_rows = []; descriptions = {}
    for panel in PANELS:
        for seq in cfg['panels'][panel]:
            units = [v for v in cfg['units'] if v['sequence'] == seq]
            for key in rate_keys:
                values = [rates[v['unit_id']][key] for v in units]; valid = [v for v in values if v is not None]
                match_rows.append(dict(panel=panel, sequence=seq, condition=key, total_training_units=len(values),
                    units_with_denominator=len(valid), rate_pp=sum(valid)/len(valid) if valid else None,
                    zero_denominator_units_preserved=len(values)-len(valid)))
    for panel in PANELS:
        descriptions[panel] = {}
        for key in rate_keys:
            values = {r['sequence']: r['rate_pp'] for r in match_rows if r['panel'] == panel and r['condition'] == key and r['rate_pp'] is not None}
            description = interval(values) if len(values) >= 2 else dict(n_independent_matches=len(values), mean_delta_pp=next(iter(values.values()), None),
                Student_t_95CI=None, percentile_match_bootstrap_95CI=None, leave_one_match_out_mean={})
            descriptions[panel][key] = dict(description, statistic='observed_condition_rate_pp_not_performance_delta_or_causal_error_fraction',
                zero_denominator_matches_retained_null=[s for s in cfg['panels'][panel] if s not in values])
    original_ids = {v['original_unit_id'] for v in cfg['units']}
    coverage = [dict(sequence=u['sequence'], fold=u['fold'], seed=u['seed'], unit_id=u['unit_id'],
        internal_trace='available_balanced_old_five' if u['unit_id'] in original_ids else 'unknown_not_recorded') for u in inventory['strong_units']]
    return unit_rows, match_rows, coverage, descriptions


def check_csv(reference, expected):
    with checked(reference).open(encoding='utf-8-sig', newline='') as stream: actual = list(csv.DictReader(stream))
    require(len(actual) == reference['rows'] == len(expected), '完整CSV行数不同，不能删unknown/负值/零分母')
    for a, b in zip(actual, expected):
        require(set(a) == set(b), 'CSV字段不同')
        for key, value in b.items():
            if value is None: require(a[key] == '', '零分母必须null，不填0')
            elif isinstance(value, (int, float)): same(float(a[key]), value)
            else: require(a[key] == value, 'CSV身份或条件名不同')


@contextmanager
def no_raw_GT_cache_or_models(inventory):
    paths = {os.path.normcase(os.path.abspath(source[key]['path'])) for source in inventory['sources'].values()
        for key in ('cache', 'gt', 'gt_reference', 'gameinfo', 'seqinfo', 'seqinfo_reference') if key in source}
    paths.update(os.path.normcase(os.path.abspath(u['labels']['path'])) for u in inventory['units'])
    evidence = dict(active=True, blocked_open_attempts=0)
    def audit(event, args):
        if event != 'open' or not evidence['active'] or not args or not isinstance(args[0], (str, bytes, os.PathLike)): return
        path = os.fsdecode(args[0])
        if os.path.normcase(os.path.abspath(path)) in paths or Path(path).suffix.lower() in ('.jpg', '.jpeg', '.png', '.exr', '.mp4', '.avi', '.pt', '.pth'):
            evidence['blocked_open_attempts'] += 1; raise PermissionError('终验不重读原GT坐标/标签/缓存/媒体/权重')
    sys.addaudithook(audit)
    try: yield evidence
    finally: evidence['active'] = False


def numeric_proof(cfg):
    proof = read(checked(cfg['numeric_admission'])); selected = [u for u in cfg['units'] if u['stage_assignment_reference'] is not None]
    require(proof['schema'] == 'bounded_error_decomposition_numeric_admission_v1'
        and proof['status'] == 'complete9_saved_stage_assignments_original_FP32_solver_exact_no_model' and proof['passed'] is True
        and proof['source_units'] == 9 and proof['numeric_sources'] == cfg['numeric']
        and proof['source_unit_ids'] == [u['unit_id'] for u in selected] and len(proof['details']) == 9
        and proof['event_count'] == sum(u['expected_stage_calls'] for u in selected)
        and proof['stage_rows'] == sum(u['expected_stage_rows'] for u in selected)
        and proof['saved_actual_reference_assignments_exact'] is True
        and proof['matching_source_provenance'] == 'current_installed_snapshot_not_historical_file_SHA'
        and proof['single_edge_feasibility'] == 'same_original_solver_1x1_FP32_no_epsilon', '既存九份实际分配准入来源/完整分母不同')
    require(proof['original_GT_coordinate_files_opened'] is False and proof['saved_GT_derived_posthoc_metadata_loaded'] is True
        and proof['GT_used_for_assignment'] is False and proof['test_read'] is False
        and all(proof[k] == 0 for k in ('model_loads', 'new_scores', 'new_free_tracking', 'new_TrackEval_runs', 'optimizer_updates')),
        '数值准入确实加载既存GT派生metadata，但不能用于分配/评分')
    by_id = {u['unit_id']: u for u in selected}
    require({v['unit_id'] for v in proof['details']} == set(by_id), '九份准入不可重复或省略')
    for value in proof['details']:
        unit = by_id[value['unit_id']]
        require(value['trace'] == unit['trace'] and value['saved_reference'] == unit['stage_assignment_reference']
            and value['events'] == unit['expected_stage_calls'] and value['stage_rows'] == unit['expected_stage_rows']
            and value['exact_original_assignment'] is True, '九份准入必须同原trace/同保存分配')
    require(proof['closure']['numeric_sources_unchanged'] is True and proof['closure']['model_or_Torch_or_tracker_loaded'] is False
        and proof['closure']['optimizer_updates'] == 0, '原纯solver数值来源闭包缺失')
    return dict(receipt=cfg['numeric_admission'], units=9, events=proof['event_count'], stage_rows=proof['stage_rows'],
        saved_GT_derived_posthoc_metadata_loaded=True, original_GT_coordinates_loaded=False,
        GT_used_for_assignment=False, assignment_solver_reexecuted_by_terminal=False)


def blocked_processes(records, state):
    pattern = re.compile(r'(?:^|[\\/\s\"\x27])(?:bounded_error_control|ocsort_(?:threshold|cached)_(?:control|admission)|'
        r'pose_velocity_(?:learning_train|tracking_control|decision_probe))[.]py(?=$|[\s\"\x27])', re.I)
    result = []; start = datetime.fromisoformat(state['created_utc'].replace('Z', '+00:00'))
    for row in records:
        command = row.get('CommandLine') or ''; spawn = False
        if 'spawn_main' in command and re.search(r'\bparent_pid\s*=\s*'+str(state['parent_pid'])+r'\b', command):
            value = row.get('CreationUtc'); require(value, '相关spawn缺创建时间，不按旧PID猜退出')
            when = datetime.fromisoformat(value.replace('Z', '+00:00')); spawn = start-timedelta(seconds=2) <= when <= datetime.now(timezone.utc)+timedelta(seconds=2)
        if (row.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(command) or spawn: result.append(row)
    return result


def processes_absent(state):
    query = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='CreationUtc';e={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    answer = subprocess.run(['powershell.exe', '-NoProfile', '-Command', query], check=True, capture_output=True, text=True, encoding='utf-8')
    records = json.loads(answer.stdout) if answer.stdout.strip() else []; records = [records] if isinstance(records, dict) else records
    require(not blocked_processes(records, state), '真实相关控制器/worker或UE仍存在，不强杀或盲用历史PID')
    return dict(actual_CIM_checked=True, producer_processes_absent=True, historical_PID_reuse_not_rejected=True)


def worker_closure(state, control):
    ready, exits = state['workers'], state['worker_exits']; counts = Counter(v['worker_pid'] for v in state['completed'])
    require(len(ready) == len(exits) == len({v['worker_pid'] for v in ready}) == 2
        and {v['worker_pid'] for v in ready} == {v['worker_pid'] for v in exits}
        and set(counts) <= {v['worker_pid'] for v in ready} and sum(counts.values()) == 27, '两个worker/全部27任务实际归属不同')
    require(all(v['status'] == 'ready' for v in ready), 'worker实际就绪未齐')
    for value in exits:
        require(value['status'] == 'closed' and value['jobs'] == counts[value['worker_pid']] and value['GT_loaded_only_posthoc'] is True
            and value['model_tracker_TrackEval_modules_loaded'] == [] and value['joined'] is True
            and value['process_exited'] is True and value['exit_code'] == 0, 'worker实际关闭/join/exit0或GT后验边界未齐')
    logs = [physical(control/'logs'/f'analysis_{i}.log') for i in range(2)]
    require(all(p.is_file() for p in logs), '两个真实worker日志缺失')
    return dict(workers=2, completed_units=27, all_joined_exit0=True, closures=exits, logs=[ref(p) for p in logs])


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream: stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def verify(config, control, output):
    config, control, output = physical(config), physical(control), physical(output); cfg = read(config)
    require(EXP in output.parents and control not in output.parents and output.parent != control and not output.parent.exists(), '独立新attempt，不覆盖已有intent或partial')
    require(cfg['schema'] == 'bounded_error_decomposition_protocol_v1' and cfg['approved_by'] == 'root'
        and cfg['phase'] == 'formal' and cfg['execute_authorized'] is True and cfg['test_sealed'] is True
        and physical(cfg['output_root']) == EXP and control == physical(cfg['analysis_root'])
        and cfg['condition_labels_are_causes'] is False and cfg['new_seven_internal_states'] == 'unknown_not_recorded'
        and all(cfg[k] == 0 for k in ('optimizer_updates', 'new_scores', 'new_free_tracking', 'new_TrackEval_runs')), '只允许完整有边界零更新观察条件协议')
    state = read(control/'state.json'); output.parent.mkdir(parents=True)
    write_new(output.parent/'intent.json', dict(protocol=ref(config), state=ref(control/'state.json'), optimizer_updates=0, new_scores=0, test_read=False))
    try:
        require(state['status'] == 'complete27_existing_traces_bounded_error_conditions_and_intervals_workers_exited'
            and state['protocol'] == ref(config) and not state['active'] and len(state['completed']) == 27
            and all(state[k] == 0 for k in ('optimizer_updates', 'new_scores', 'new_free_tracking', 'new_TrackEval_runs')) and state['test_read'] is False,
            '真实27/汇总/退出终态未齐')
        initial_exit = processes_absent(state); inventory = read(checked(cfg['inventory'])); validate_coverage(inventory)
        require(cfg['units'] == inventory['units'] and cfg['panels'] == inventory['panels'] and cfg['source_ledgers'] == inventory['source_ledgers']
            and cfg['unit_order'] == [u['unit_id'] for u in cfg['units']], '不可重选seed/来源/诊断范围')
        with no_raw_GT_cache_or_models(inventory) as guard:
            bundle = physical(cfg['bundle']); require(bundle.parent == R/'code', '只能执行最小冻结来源')
            files = read(checked(cfg['bundle_manifest']))['files']
            for value in files: require(sha(bundle/value['path']) == value['sha256'], '活动冻结源码改变')
            core = [v for v in files if v['path'] == 'tools/research_ops/bounded_error_decomposition.py']; require(len(core) == 1, 'core来源未绑定')
            core_ref = dict(path=str(bundle/core[0]['path']), sha256=core[0]['sha256'])
            admission = numeric_proof(cfg); by_id = {u['unit_id']: u for u in cfg['units']}; summaries = {}; checks = []
            require({v['unit_id'] for v in state['completed']} == set(by_id), '完整27完成项缺失/重复')
            for value in state['completed']:
                uid = value['unit_id']; path = checked(value['summary'])
                require(value['status'] == 'complete' and path == control/'units'/uid/'summary.json', '实际unit完成路径不同')
                summaries[uid] = read(path); require(summaries[uid]['implementation'] == core_ref, '不是冻结core产生的条件账本')
                checks.append(verify_unit(cfg, by_id[uid], path))
            require(sum(v['stage_calls'] for v in checks) == 24863 and sum(v['stage_rows'] for v in checks) == 320752, '全量原事件/row分母未闭合')
            workers = worker_closure(state, control)
            require(state['actual_exit_gate']['actual_CIM_checked'] is True and state['actual_exit_gate']['related_producers_absent'] is True, '原控制器实际worker退出门禁缺失')
            report_path = checked(state['report']); require(report_path == control/'report.json', '根统计报告路径不同'); report = read(report_path)
            counts = dict(trace_units=27, missing_trace_units=63, source_matches_with_internal_trace=5, source_matches_total=12, stage_calls=24863, stage_rows=320752)
            require(report['schema'] == 'bounded_error_decomposition_report_v1' and report['status'] == 'complete27_bounded_conditions_all_rows_intervals63_missing_preserved'
                and report['protocol'] == ref(config) and report['inventory'] == cfg['inventory'] and report['numeric_admission'] == cfg['numeric_admission']
                and report['counts'] == counts and report['unit_summaries'] == [ref(control/'units'/uid/'summary.json') for uid in cfg['unit_order']]
                and report['first_stop_is_cause'] is False and report['all_negative_unknown_and_zero_denominators_retained'] is True
                and report['seven_observed_internal_conditions'] == 'unknown_not_recorded_no_interval'
                and report['unrecorded_low_stage_empty_and_lifecycle'] == 'unknown' and report['all_video_event_denominator'] is False
                and report['GT_only_posthoc'] is True and report['factor_selected_by_this_code'] is False
                and report['previous_12_output_evidence'] == cfg['previous_12_output_evidence']
                and report['formal_equivalence_or_noninferiority'] is False and report['performance_margin'] is None
                and all(report[k] == 0 for k in ('optimizer_updates', 'new_scores', 'new_free_tracking', 'new_TrackEval_runs')) and report['test_read'] is False, '根报告缺失/因果或泛化/预算边界被改写')
            interval_path = checked(cfg['interval_source']); require(interval_path.name == 'substitution_paired_analysis.py', '必须原比赛t/固定bootstrap/LOO纯函数')
            spec = importlib.util.spec_from_file_location('bounded_terminal_original_intervals', interval_path); stats = importlib.util.module_from_spec(spec)
            previous = sys.dont_write_bytecode
            try: sys.dont_write_bytecode = True; spec.loader.exec_module(stats)
            finally: sys.dont_write_bytecode = previous
            units, matches, coverage, descriptions = condition_tables(cfg, summaries, inventory, stats.effect_intervals)
            for name, data in [('all_units', units), ('all_match_condition_rates', matches), ('all_internal_coverage', coverage)]: check_csv(report[name], data)
            same(report['condition_intervals'], descriptions); require(guard['blocked_open_attempts'] == 0, '终验意外尝试GT/缓存/标签/权重/媒体')
        final_exit = processes_absent(state)
        receipt = dict(schema='bounded_error_decomposition_independent_verification_v1', status=STATUS, implementation=ref(__file__), protocol=ref(config),
            state=ref(control/'state.json'), report=state['report'], inventory=cfg['inventory'], numeric_admission=admission,
            counts=counts, unit_checks=checks, workers=workers, match_condition_rows=len(matches), interval_descriptions=sum(len(v) for v in descriptions.values()),
            all_counts_CSVs_and_condition_intervals_reconstructed=True, first_stop_is_cause=False, history_anchor_is_global_GT_or_cause=False,
            initial_exit=initial_exit, final_exit=final_exit, producer_processes_absent=True, original_GT_coordinate_cache_labels_media_or_weights_opened=False,
            saved_GT_derived_posthoc_row_metadata_loaded=True, posthoc_candidate_GT_partitions_source_bound_not_relabelled=True,
            lost_gap_storage='source_trace_event_row_reference_not_duplicated_in_new_ledger',
            original_assignment_or_single_edge_solver_rerun=False, model_tracker_or_TrackEval_loaded=False,
            optimizer_updates=0, new_scores=0, new_free_tracking=0, new_TrackEval_runs=0, factor_selected=False,
            all_unknown_and_zero_denominators_retained=True, seven_internal_conditions='unknown_not_recorded_no_interval', test_read=False)
        write_new(output, receipt); return receipt
    except BaseException as error:
        write_new(output.parent/'failed.json', dict(status='failed_bounded_verification_partial_preserved_no_replay', error=repr(error), traceback=traceback.format_exc(),
            source_records_modified=False, optimizer_updates=0, new_scores=0, test_read=False)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); result = verify(args.config, args.control, args.output)
    print(canonical(dict(status=result['status'], counts=result['counts'], interval_descriptions=result['interval_descriptions'], optimizer_updates=0)))
