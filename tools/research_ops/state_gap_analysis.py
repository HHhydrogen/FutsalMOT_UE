"""训练域自由状态的独立后验诊断；不评分、不更新、不将GT框传入追踪。"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
import random
import statistics


SCHEMA = 'trainR_free_state_posthoc_v1'
BRANCHES = ('original', 'history_only', 'motion_only', 'both')
LABEL_STATES = ('matched', 'unknown_conflict', 'unknown_low_overlap', 'unmatched')
LIMITATIONS = (
    '仅首seed训练域轨迹；模型见过这些比赛，不是独立泛化评价',
    '可信匹配是双向唯一IoU>=0.5的几何代理，非完整轨迹身份真值或TrackEval分配',
    '首次只指可观察且此前无未知遮蔽的可信身份切换，不等于全局IDSW或首次真实错误',
    '四分支是局部GT辅助oracle，正确raw可能已经分给其他轨迹；不是可部署全局重新分配',
    '事件、模型和fold重复共享比赛；事件配对不作为独立比赛的确认性置信区间',
    '没有合格事件/全未知/剩余不足30帧均原样保留，不复制或补齐配额',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def iou_xywh(a, b):
    require(len(a) == len(b) == 4 and all(type(v) in (int, float) and math.isfinite(v) for v in (*a, *b)),
        '框必须是四个有限绝对像素数值')
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    require(min(aw, ah, bw, bh) > 0, '框宽高必须为正')
    intersection = max(0., min(ax+aw, bx+bw)-max(ax, bx))*max(0., min(ay+ah, by+bh)-max(ay, by))
    return intersection/(aw*ah+bw*bh-intersection)


def match_labels(detections, gt):
    """与原v8训练标签规则相同；ID0合法，歧义不伪造为负例。"""
    uids = [d['uid'] for d in detections]
    identities = [str(g['gt_id']) for g in gt]
    require(len(set(uids)) == len(uids) and len(set(identities)) == len(identities), '同帧UID或GT身份重复')
    overlaps = [[iou_xywh(d['bbox_xywh_px'], g['bbox_xywh_px']) for g in gt] for d in detections]
    edges = [[j for j, value in enumerate(row) if value >= .5] for row in overlaps]
    degree = Counter(j for row in edges for j in row)
    labels = {}
    for detection, row, values in zip(detections, edges, overlaps):
        if len(row) == 1 and degree[row[0]] == 1:
            state, identity = 'matched', identities[row[0]]
        elif row:
            state, identity = 'unknown_conflict', None
        elif any(value >= .1 for value in values):
            state, identity = 'unknown_low_overlap', None
        else:
            state, identity = 'unmatched', None
        labels[detection['uid']] = dict(state=state, gt_id=identity)
    return labels


def build_label_index(raw_frames, gt_by_frame):
    """只在后验进程调用；返回原raw引用，不输出GT坐标。"""
    labels, raw, positives = {}, {}, defaultdict(list)
    frame_rows, state_counts, gt_presence = [], Counter(), set()
    numbers = []
    for frame in raw_frames:
        number = frame['frame_number']
        require(type(number) is int and number > 0 and number not in numbers, 'raw帧号必须唯一一基正整数')
        numbers.append(number)
        gt = gt_by_frame.get(number, [])
        frame_labels = match_labels(frame['detections'], gt)
        for g in gt:
            gt_presence.add((number, str(g['gt_id'])))
        for detection in frame['detections']:
            uid = detection['uid']
            require(uid not in labels, 'UID跨帧重复')
            label = dict(frame_labels[uid], frame_number=number)
            labels[uid], raw[uid] = label, deepcopy(detection)
            raw[uid]['_diagnostic_frame_number'] = number
            state_counts[label['state']] += 1
            if label['state'] == 'matched':
                positives[(number, label['gt_id'])].append(uid)
        frame_rows.append(dict(frame_number=number, raw_count=len(frame['detections']), GT_count=len(gt),
            label_counts=dict(Counter(value['state'] for value in frame_labels.values()))))
    require(numbers == sorted(numbers), 'raw帧必须严格递增')
    return dict(labels=labels, raw=raw, positives=dict(positives), GT_presence=gt_presence,
        frame_rows=frame_rows, counts=dict(frames=len(numbers), raw=len(raw), GT_rows=len(gt_presence),
            **{key: state_counts[key] for key in LABEL_STATES}), GT_coordinates_in_result=False)


def history_status(history_uids, labels):
    values = [labels.get(uid) for uid in history_uids]
    if not values or any(value is None or value['state'] != 'matched' for value in values):
        return dict(state='history_unknown', gt_id=None)
    identities = {str(value['gt_id']) for value in values}
    if len(identities) != 1:
        return dict(state='mixed_trusted_history', gt_id=None)
    return dict(state='trusted_consistent_history', gt_id=next(iter(identities)))


def candidate_label(query, label):
    if query is None or label is None or label['state'].startswith('unknown'):
        return None
    return int(label['state'] == 'matched' and str(label['gt_id']) == str(query))


def _hist_uids(row):
    if 'history_UIDs' in row:
        return list(row['history_UIDs'])
    return [record['uid'] for record in row.get('history', [])]


def _flat_tracks(value):
    if isinstance(value, list):
        return deepcopy(value)
    require(isinstance(value, dict) and set(value) == {'tracked_stracks', 'lost_stracks', 'removed_stracks'},
        '真实状态须保留tracked/lost/removed三列表')
    result = []
    for name in ('tracked_stracks', 'lost_stracks', 'removed_stracks'):
        result.extend(dict(deepcopy(track), list_membership=name) for track in value[name])
    return result


def normalize_rollout_frame(frame):
    """真实Observer日志一对一转换；stage分配来自assignments，绝不用帧末UID猜测。"""
    if frame.get('_state_gap_normalized') is True:
        return deepcopy(frame)
    result = deepcopy(frame)
    result['_state_gap_normalized'] = True
    result['tracks_before'] = _flat_tracks(frame.get('tracks_before', []))
    result['tracks_after'] = _flat_tracks(frame.get('tracks_after', []))
    result['stages'] = []
    for original in frame.get('stages', []):
        stage = deepcopy(original)
        if 'rows' in original:
            require(len(original['rows']) == len(original['track_ids']), '原Observer stage rows缺失')
            stage['history_UIDs'] = [_hist_uids(row) for row in original['rows']]
        if 'assignments' in original:
            stage['assignment'] = dict(matches=deepcopy(original['assignments']),
                unmatched_rows=deepcopy(original.get('unmatched_track_rows', [])),
                unmatched_columns=deepcopy(original.get('unmatched_detection_columns', [])))
        if 'active' in original: stage['active_rows'] = deepcopy(original['active'])
        if 'gates' in original: stage['motion_gate'] = deepcopy(original['gates'])
        result['stages'].append(stage)
    result['observations'] = deepcopy(frame.get('observations', []))
    lifecycle = []
    for event in frame.get('lifecycle', []):
        item = deepcopy(event)
        item['event'] = event.get('operation', event.get('event'))
        lifecycle.append(item)
        if 'operation' in event and event['operation'] in ('activate', 'update', 're_activate'):
            after = event['after']
            record = after.get('record')
            require(record is not None and type(record['uid']) is str, '原实际写入生命周期缺raw record')
            result['observations'].append(dict(track_id=after['track_id'], uid=record['uid'],
                event=event['operation'], before=deepcopy(event['before']), after=deepcopy(after)))
    result['lifecycle'] = lifecycle
    require(len({item['track_id'] for item in result['observations']}) == len(result['observations']),
        '每帧同轨迹实际测量写入重复，拒绝猜测最终一次')
    return result


def _window_summary(history, candidate_uids, pair_labels, labels, current_frame, stage, active=None, lost_gap=None):
    require(len(candidate_uids) == len(pair_labels) and all(value is None or type(value) is int and value in (0, 1)
        for value in pair_labels), '候选标签只能0/1/None且长度一致')
    numbers = [labels[uid]['frame_number'] for uid in history if uid in labels]
    gap = None if len(numbers) != len(history) or not history else current_frame-numbers[-1]
    consecutive = None if len(numbers) != len(history) or not history else all(b-a == 1 for a, b in zip(numbers, numbers[1:]))
    known = sum(value is not None for value in pair_labels)
    return dict(history_count=len(history), history_frames=numbers, history_consecutive=consecutive,
        actual_observation_gap_frames=gap, actual_observation_gap_seconds=None if gap is None else gap/25.,
        candidate_count=len(candidate_uids), positive=sum(value == 1 for value in pair_labels),
        known_negative=sum(value == 0 for value in pair_labels), unknown=len(pair_labels)-known,
        no_positive=not any(value == 1 for value in pair_labels), all_unknown=bool(pair_labels) and known == 0,
        empty=not candidate_uids, stage=stage, learned_active=active, lost_gap=lost_gap)


class WindowAccumulator:
    """只累计原绝对分母及直方图；不持有候选行或完整轨迹。"""
    def __init__(self):
        self.counts = Counter({key: 0 for key in ('windows', 'candidate_count', 'positive', 'known_negative', 'unknown',
            'no_positive_windows', 'all_unknown_windows', 'empty_windows', 'nonconsecutive_history_windows',
            'history_consecutiveness_unknown_windows', 'learned_active_windows', 'lost_gap_windows')})
        self.hist, self.candidate, self.gaps, self.stages = Counter(), Counter(), Counter(), Counter()

    def add(self, row):
        counts = self.counts
        counts['windows'] += 1
        for key in ('candidate_count', 'positive', 'known_negative', 'unknown'):
            counts[key] += row[key]
        for key in ('no_positive', 'all_unknown', 'empty'):
            counts[key+'_windows'] += int(row[key])
        counts['nonconsecutive_history_windows'] += int(row['history_consecutive'] is False)
        counts['history_consecutiveness_unknown_windows'] += int(row['history_consecutive'] is None)
        counts['learned_active_windows'] += int(row.get('learned_active') is True)
        counts['lost_gap_windows'] += int(row.get('lost_gap') is True)
        self.hist[str(row['history_count'])] += 1
        self.candidate[str(row['candidate_count'])] += 1
        self.gaps[str(row['actual_observation_gap_frames'])] += 1
        self.stages[str(row['stage'])] += 1

    def result(self):
        return dict(absolute_counts=dict(self.counts), history_count_histogram=dict(self.hist),
            candidate_count_histogram=dict(self.candidate), gap_frames_histogram=dict(self.gaps),
            stage_windows=dict(self.stages), windows_are_not_independent_images=True)


def aggregate_window_rows(rows):
    accumulator = WindowAccumulator()
    for row in rows:
        accumulator.add(row)
    return accumulator.result()


def summarize_clean_windows(windows, labels=None):
    """原1000池原行绝对分布；不要求窗含正例，不把unknown计负例。"""
    labels = labels or {}
    rows, seen = [], set()
    for window in windows:
        uid = window['window_uid']
        require(uid not in seen, 'clean窗口UID重复')
        seen.add(uid)
        history = _hist_uids(window)
        if 'candidates' in window:
            candidate_uids = [candidate['prediction']['uid'] for candidate in window['candidates']]
            pair_labels = [candidate['label'] for candidate in window['candidates']]
        else:
            candidate_uids, pair_labels = list(window['candidate_UIDs']), list(window['labels'])
        current = window['candidate_frame_number']
        local_labels = dict(labels)
        if not all(h in local_labels for h in history) and 'history_frame_indices' in window:
            for h, index in zip(history, window['history_frame_indices']):
                local_labels[h] = dict(frame_number=index+1)
        row = _window_summary(history, candidate_uids, pair_labels, local_labels, current, 'clean_training_pool')
        row.update(window_uid=uid, sequence=window['sequence'], history_UIDs=history, candidate_UIDs=candidate_uids,
            pair_labels=pair_labels, teacher_forced_history=True)
        rows.append(row)
    return dict(schema=SCHEMA, rows=rows, summary=aggregate_window_rows(rows), optimizer_updates=0,
        input_scope='unaugmented_teacher_forced_pool_structure_not_all_actual_SGD_tensors')


def annotate_stage(stage, source, metadata):
    """输入每个原生分配stage，含0×N/N×0；不重跑solver或以帧末UID替代stage分配。"""
    tracks, candidates = stage['track_ids'], stage['candidate_UIDs']
    histories = stage['history_UIDs']
    require(len(histories) == len(tracks) and len(set(tracks)) == len(tracks)
        and len(set(candidates)) == len(candidates), 'stage行列/历史不一致')
    assignment = stage['assignment']
    matches = assignment['matches'] if isinstance(assignment, dict) else assignment
    selected = dict(matches)
    require(len(selected) == len(matches) and len({pair[1] for pair in matches}) == len(matches)
        and all(0 <= i < len(tracks) and 0 <= j < len(candidates) for i, j in matches), 'stage实际分配必须一对一且不越界')
    labels, rows = source['labels'], []
    number = stage['frame_number']
    for index, track in enumerate(tracks):
        history = list(histories[index])
        require(all(uid in labels and labels[uid]['frame_number'] < number for uid in history)
            and all(uid in labels and labels[uid]['frame_number'] == number for uid in candidates), '历史必须过去，候选必须当前')
        status = history_status(history, labels)
        query = status['gt_id']
        pair_labels = [candidate_label(query, labels[uid]) for uid in candidates]
        row = _window_summary(history, candidates, pair_labels, labels, number, stage['stage'],
            (stage.get('active_rows') or [None]*len(tracks))[index], (stage.get('lost_gap') or [None]*len(tracks))[index])
        positive = [j for j, value in enumerate(pair_labels) if value == 1]
        gates = stage.get('motion_gate')
        enabled = stage.get('enabled')
        chosen = candidates[selected[index]] if index in selected else None
        row.update(metadata, frame_number=number, track_id=track, row_index=index, history_UIDs=history,
            history_status=status['state'], query_GT_id=query, candidate_UIDs=list(candidates), pair_labels=pair_labels,
            selected_UID=chosen, selected_column=selected.get(index),
            raw_correct_UIDs=list(source['positives'].get((number, query), [])),
            current_GT_present=(number, query) in source['GT_presence'] if query is not None else None,
            positive_in_stage=bool(positive), positive_motion_gate=None if gates is None else any(gates[index][j] for j in positive),
            positive_effectively_enabled=None if enabled is None else any(enabled[index][j] for j in positive),
            selected_label=None if chosen is None else candidate_label(query, labels[chosen]),
            condition_is_cause=False)
        row['learned_inactive_reason'] = None if row['learned_active'] is True else (
            'low_score_bbox_only' if stage['stage'] == 'low_score' else
            ('history_fewer_than3' if len(history) != 3 else 'easy_bbox_or_no_competition_not_separately_inferred'))
        rows.append(row)
    return dict(rows=rows, empty_stage_record=dict(metadata, frame_number=number, stage=stage['stage'],
        track_rows=len(tracks), candidate_columns=len(candidates), empty_matrix=not tracks or not candidates,
        actual_matches=len(matches)), new_solver_calls=0)


def annotate_rollout(frame_records, source, metadata, *, row_sink=None, retain_rows=True):
    """逐帧消费；正式日志可逐行落盘，汇总不保留全部候选行。"""
    rows, stages, lifecycle = [], [], Counter()
    accumulator, total_frames = WindowAccumulator(), 0
    for original in frame_records:
        total_frames += 1
        frame = normalize_rollout_frame(original)
        for stage in frame['stages']:
            bound_stage = dict(stage, frame_number=frame['frame_number'])
            result = annotate_stage(bound_stage, source, metadata)
            for row in result['rows']:
                accumulator.add(row)
                if row_sink is not None: row_sink(row)
                if retain_rows: rows.append(row)
            stages.append(result['empty_stage_record'])
        for event in frame.get('lifecycle', []):
            lifecycle[event['event']] += 1
            if event['event'] == 'activate': lifecycle['birth'] += 1
            if event['event'] == 'update' and event.get('before', {}).get('is_activated') is False \
                and event.get('after', {}).get('is_activated') is True:
                lifecycle['confirmation_by_actual_update'] += 1
    return dict(schema=SCHEMA, rows=rows, stage_records=stages, lifecycle_counts=dict(lifecycle),
        summary=accumulator.result(), total_frames=total_frames, new_solver_calls=0,
        evaluation='train_domain_conditional_diagnosis_not_heldout_tracking_score')


def select_first_errors(frame_records, source, metadata):
    """每track首个可观察trusted切换；此前unknown不默认正确，严格资格拒绝。"""
    labels, states, records = source['labels'], {}, []
    final_frame = max((row['frame_number'] for row in source['frame_rows']), default=0)
    for expected_number, original in enumerate(frame_records, 1):
        require(original['frame_number'] == expected_number,
            '首错诊断必须从第一帧完整连续处理，不能截取已知好历史')
        frame = normalize_rollout_frame(original)
        number = frame['frame_number']
        before = {track['track_id']: track for track in frame.get('tracks_before', [])}
        # 仅实际测量写入；未匹配/lost不伪造新观测。
        for observation in frame.get('observations', []):
            track, uid = observation['track_id'], observation['uid']
            require(uid in labels and labels[uid]['frame_number'] == number, '实际写入必须当前rawUID')
            label = labels[uid]
            state = states.setdefault(track, dict(anchor=None, prior_unknown=False, prior_wrong=False, observation_count=0,
                seen_trusted_ids=set(), emitted_switch=False))
            current = observation.get('before', before.get(track, {}))
            history = _hist_uids(current)
            require(len(history) <= 3 and all(uid in labels and labels[uid]['frame_number'] < number for uid in history)
                and [labels[uid]['frame_number'] for uid in history] == sorted({labels[uid]['frame_number'] for uid in history}),
                '真实历史必须最多3条严格过去原raw，不能读当前/未来或重复帧')
            hstatus = history_status(history, labels)
            if state['anchor'] is None and len(history) == 3 and hstatus['state'] == 'trusted_consistent_history':
                anchor = hstatus['gt_id']
                state['anchor'] = anchor
                state['prior_wrong'] = any(value != anchor for value in state['seen_trusted_ids'])
                state['anchor_history_UIDs'] = list(history)
            anchor = state['anchor']
            is_wrong = anchor is not None and label['state'] == 'matched' and str(label['gt_id']) != anchor
            if is_wrong and not state['emitted_switch']:
                correct = list(source['positives'].get((number, anchor), []))
                reasons = []
                if state['prior_unknown']: reasons.append('first_error_status_unknown_prior_observation')
                if state['prior_wrong']: reasons.append('prior_trusted_identity_conflict')
                if len(history) != 3: reasons.append('pre_error_history_fewer_than3')
                if hstatus['state'] != 'trusted_consistent_history' or hstatus['gt_id'] != anchor:
                    reasons.append('pre_error_history_not_trusted_anchor_consistent')
                if (number, anchor) not in source['GT_presence']: reasons.append('anchor_GT_absent')
                if len(correct) != 1: reasons.append('correct_current_raw_not_mutual_unique')
                if observation.get('event') not in ('update', 're_activate'):
                    reasons.append('not_existing_track_measurement_update')
                if final_frame-number < 30: reasons.append('fewer_than30_future_source_frames')
                initialized = {candidate for stage in frame.get('stages', []) for candidate in stage['candidate_UIDs']}
                if len(correct) == 1 and correct[0] not in initialized:
                    reasons.append('correct_raw_not_initialized_by_original_score_policy')
                tracked_after = [row for row in frame.get('tracks_after', []) if row['track_id'] == track
                    and row.get('list_membership') == 'tracked_stracks']
                if len(tracked_after) != 1:
                    reasons.append('target_not_unique_tracked_after_wrong_frame')
                decisions, correct_owners = [], []
                for stage in frame.get('stages', []):
                    assignment = stage['assignment']
                    matches = assignment['matches'] if isinstance(assignment, dict) else assignment
                    for i, j in matches:
                        assigned = stage['candidate_UIDs'][j]
                        if len(correct) == 1 and assigned == correct[0]:
                            correct_owners.append(dict(stage=stage['stage'], track_id=stage['track_ids'][i]))
                        if stage['track_ids'][i] == track and assigned == uid:
                            positive_column = stage['candidate_UIDs'].index(correct[0]) if len(correct) == 1 \
                                and correct[0] in stage['candidate_UIDs'] else None
                            enabled, gates, costs = stage.get('enabled'), stage.get('motion_gate'), stage.get('reference_cost')
                            decisions.append(dict(stage=stage['stage'], row_index=i, wrong_column=j,
                                correct_column=positive_column, correct_in_same_stage=positive_column is not None,
                                learned_active=(stage.get('active_rows') or [None]*len(stage['track_ids']))[i],
                                correct_motion_gate=None if gates is None or positive_column is None else gates[i][positive_column],
                                correct_effectively_enabled=None if enabled is None or positive_column is None else enabled[i][positive_column],
                                native_wrong_cost=None if costs is None else costs[i][j],
                                native_correct_cost=None if costs is None or positive_column is None else costs[i][positive_column],
                                threshold=stage.get('threshold')))
                if len(decisions) != 1:
                    reasons.append('actual_wrong_assignment_stage_not_unique')
                payload = dict(metadata, frame_number=number, frame_index=number-1, track_id=track,
                    wrong_uid=uid, correct_uid=correct[0] if len(correct) == 1 else None, anchor_GT_id=anchor,
                    pre_error_history_UIDs=history, prior_unknown=state['prior_unknown'], prior_wrong=state['prior_wrong'],
                    first_error_status='unknown' if state['prior_unknown'] else 'first_observed_trusted_switch',
                    candidate_eligible=not reasons, exclusion_reasons=reasons, lifecycle_event=observation.get('event'),
                    intervention_timing='after_original_wrong_frame_update_before_next_frame',
                    definition='first_observed_trusted_switch_not_global_IDSW', correct_raw_may_belong_to_another_track=True)
                payload['available_future_source_frames'] = final_frame-number
                payload['actual_wrong_assignment'] = decisions[0] if len(decisions) == 1 else None
                payload['correct_current_raw_assigned_tracks'] = correct_owners
                payload['event_id'] = hashlib.sha256(canonical([metadata['job_id'], number, track, uid]).encode()).hexdigest()
                records.append(payload)
                state['emitted_switch'] = True
            if label['state'] != 'matched': state['prior_unknown'] = True
            else:
                state['seen_trusted_ids'].add(str(label['gt_id']))
                if anchor is not None and str(label['gt_id']) != anchor: state['prior_wrong'] = True
            state['observation_count'] += 1
    # 未建立可信anchor或没有观察到trusted switch的轨迹也保留，不能从分母消失。
    terminals = []
    for track, state in states.items():
        terminals.append(dict(metadata, track_id=track, observations=state['observation_count'],
            anchor_GT_id=state['anchor'], prior_unknown=state['prior_unknown'], prior_wrong=state['prior_wrong'],
            observed_switch=state['emitted_switch'], terminal_reason='observed_switch' if state['emitted_switch'] else
                ('no_trusted3_anchor' if state['anchor'] is None else 'no_observed_trusted_switch')))
    return dict(schema=SCHEMA, events=records, tracks=terminals, limitations=list(LIMITATIONS))


def select_bounded_events(events, cap_per_fold=20, folds=('game4', 'game6', 'game9')):
    require(type(cap_per_fold) is int and cap_per_fold == 20 and tuple(folds) == ('game4', 'game6', 'game9'),
        '冻结三fold每fold20上限，不按结果改配额')
    require(len({event['event_id'] for event in events}) == len(events), '事件ID重复')
    ordered = sorted(events, key=lambda row: (row['fold'], row['sequence'], row['frame_number'],
        row['regime'], row['model_id'], row['track_id'], row['event_id']))
    counts, output = Counter(), []
    for event in ordered:
        require(event['fold'] in folds and event['regime'] in ('R', 'RS') and event['seed'] == 20261024,
            '只准首seed R/RS三fold')
        row = deepcopy(event)
        row['selected'] = bool(row['candidate_eligible'] and counts[row['fold']] < cap_per_fold)
        row['selection_reason'] = 'fixed_order_selected' if row['selected'] else (
            'ineligible_preserved' if not row['candidate_eligible'] else 'fold_cap_reached_preserved')
        if row['selected']: counts[row['fold']] += 1
        output.append(row)
    return dict(schema=SCHEMA, events=output, selected=[row for row in output if row['selected']],
        absolute_counts=dict(total_first_observed_switches=len(output), eligible=sum(row['candidate_eligible'] for row in output),
            selected=sum(counts.values()), **{fold: counts[fold] for fold in folds}),
        selected_regime_counts=dict(Counter(row['regime'] for row in output if row['selected'])),
        cap_per_fold=20, maximum_total=60, quota_filled_by_duplication=False,
        order='fold,sequence,frame_number,regime,model_id,track_id,event_id', limitations=list(LIMITATIONS))


def oracle_plan(event, source):
    require(event.get('selected') is True and event['candidate_eligible'] is True, '只能执行固定排序入选可信事件')
    wrong, correct, number = event['wrong_uid'], event['correct_uid'], event['frame_number']
    require(wrong != correct and all(uid in source['raw'] for uid in (wrong, correct))
        and all(source['labels'][uid]['frame_number'] == number for uid in (wrong, correct)), '两测量必须同帧真实raw')
    require(source['labels'][correct]['state'] == source['labels'][wrong]['state'] == 'matched'
        and source['labels'][correct]['gt_id'] == event['anchor_GT_id']
        and source['labels'][wrong]['gt_id'] != event['anchor_GT_id'], '正确/错误资格必须来自独立后验可信标签')
    # 追踪重放输入刻意不含anchor或GT框；raw读取器按冻结UID加载原预测。
    return dict(event_id=event['event_id'], frame_number=number, track_id=event['track_id'],
        wrong_uid=wrong, correct_uid=correct, replay_frames_after_event=30, branches=list(BRANCHES),
        history_rule='replace_only_newly_written_wrong_raw_by_same_frame_correct_raw_keep_length',
        motion_rule='original_KF_update_correct_raw_xyah_from_saved_predicted_mean_cov_replace_mean_cov_only',
        unchanged_fields=['record', 'score', 'lifecycle', 'global_ID', 'other_tracks', 'output_on_error_frame'],
        GT_coordinates_in_plan=False, future_information_used=False, deployable=False)


def branch_outcomes(frame_records, source, track_id, anchor_gt_id, error_frame, horizon=30):
    require(horizon == 30, '固定后续30帧')
    frames = [normalize_rollout_frame(row) for row in frame_records if error_frame < row['frame_number'] <= error_frame+horizon]
    require([row['frame_number'] for row in frames] == list(range(error_frame+1, error_frame+1+len(frames))),
        '后续分支必须连续，不跳未知帧')
    result, counts, lifecycle_counts = [], Counter(), Counter()
    for row in frames:
        writes = [item for item in row.get('observations', []) if item['track_id'] == track_id]
        require(len(writes) <= 1, '同帧同轨迹不可重复写入测量')
        uid = writes[0]['uid'] if writes else None
        label = source['labels'].get(uid) if uid is not None else None
        if uid is None: outcome = 'unmatched_or_no_measurement'
        elif label is None or label['state'] != 'matched': outcome = 'unknown_measurement'
        elif str(label['gt_id']) == str(anchor_gt_id): outcome = 'same_trusted_anchor'
        else: outcome = 'other_trusted_identity'
        counts[outcome] += 1
        states = [track for track in row.get('tracks_after', []) if track['track_id'] == track_id]
        memberships = sorted({track.get('list_membership', 'unspecified') for track in states})
        state_names = sorted({str(track.get('state', 'unknown')) for track in states})
        state = '+'.join(memberships) if memberships else 'absent'
        lifecycle_counts[state] += 1
        result.append(dict(frame_number=row['frame_number'], uid=uid, outcome=outcome, lifecycle_memberships=memberships,
            lifecycle_states=state_names, is_activated_values=sorted({bool(track['is_activated']) for track in states
                if 'is_activated' in track})))
    first_recovery = next((row['frame_number']-error_frame for row in result if row['outcome'] == 'same_trusted_anchor'), None)
    # unknown和无写入不是正确或错误，恢复前时长右删失显式记录。
    return dict(rows=result, absolute_counts={key: counts[key] for key in (
        'same_trusted_anchor', 'other_trusted_identity', 'unknown_measurement', 'unmatched_or_no_measurement')},
        observed_frames=len(frames), requested_frames=30, source_end_truncated=len(frames) < 30,
        first_trusted_recovery_offset_frames=first_recovery,
        no_trusted_recovery_observed=first_recovery is None,
        recovery_time_right_censored=first_recovery is None, error_frame_in_counts=False,
        lifecycle_frame_counts=dict(lifecycle_counts))


def summarize_branches(event_records):
    totals = {branch: Counter() for branch in BRANCHES}
    paired, groups, event_ids, model_counts = [], defaultdict(list), set(), Counter()
    for event in event_records:
        require(event['event_id'] not in event_ids and set(event['branches']) == set(BRANCHES), '事件重复或四支缺失')
        event_ids.add(event['event_id'])
        model_counts[(event['model_id'], event['sequence'])] += 1
        branches = event['branches']
        require(branches['original'].get('exact_original_reproduction') is True, '原支未逐值复现，拒绝传播分析')
        frame_numbers = [[row['frame_number'] for row in branches[branch]['rows']] for branch in BRANCHES]
        require(all(value == frame_numbers[0] for value in frame_numbers), '四支必须同起止帧，不能跳未知')
        for branch in BRANCHES:
            value = branches[branch]
            actual_counts = Counter(row['outcome'] for row in value['rows'])
            require(value['observed_frames'] == len(value['rows']) == 30 and value['source_end_truncated'] is False
                and sum(value['absolute_counts'].values()) == 30
                and all(actual_counts[key] == count for key, count in value['absolute_counts'].items()),
                '正式入选事件必须完整30帧且计数逐行一致')
            totals[branch].update(branches[branch]['absolute_counts'])
            totals[branch]['observed_frames'] += branches[branch]['observed_frames']
            totals[branch]['events'] += 1
            totals[branch]['no_recovery_events'] += int(branches[branch]['no_trusted_recovery_observed'])
        for branch in BRANCHES[1:]:
            base, value = branches['original'], branches[branch]
            row = {key: event[key] for key in ('event_id', 'fold', 'sequence', 'regime', 'model_id', 'track_id', 'frame_number')}
            row.update(branch=branch, original=deepcopy(base['absolute_counts']), intervention=deepcopy(value['absolute_counts']),
                paired_count_difference={key: value['absolute_counts'][key]-base['absolute_counts'][key]
                    for key in base['absolute_counts']},
                original_first_recovery=base['first_trusted_recovery_offset_frames'],
                intervention_first_recovery=value['first_trusted_recovery_offset_frames'])
            paired.append(row); groups[(event['fold'], event['sequence'], event['regime'])].append(row)
    return dict(schema=SCHEMA, event_count=len(event_ids), absolute_branch_totals={branch: dict(totals[branch]) for branch in BRANCHES},
        paired_events=paired, group_counts=[dict(fold=key[0], sequence=key[1], regime=key[2], paired_comparisons=len(value))
            for key, value in sorted(groups.items())], confidence_intervals=None,
        per_model_event_counts=[dict(model_id=key[0], sequence=key[1], events=count) for key, count in sorted(model_counts.items())],
        source_level_descriptions=source_level_descriptions(event_records),
        CI_status='no_event_independent_CI_source_level_descriptive_intervals_separate',
        performance_pass_flag=None, new_optimizer_updates=0, limitations=list(LIMITATIONS))


def _percentile(values, q):
    ordered = sorted(values)
    position = (len(ordered)-1)*q
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper]-ordered[lower])*(position-lower)


def source_intervals(values, sources=('SNMOT-060', 'SNMOT-097', 'SNMOT-151')):
    """先每源均事件，再三源等权；源缺失则不伪造df2/比赛样本。"""
    require(set(values).issubset(sources) and all(math.isfinite(value) for value in values.values()), '只准原三train源有限均值')
    missing = [source for source in sources if source not in values]
    if missing:
        return dict(source_means=dict(values), confidence_intervals=None,
            CI_status='missing_selected_events_in_source_not_filled', missing_sources=missing,
            observed_source_count=len(values), descriptive_only=True)
    x = [values[source] for source in sources]
    mean = statistics.mean(x)
    se = statistics.stdev(x)/math.sqrt(3)
    rng = random.Random(20261028)
    draws = [sum(x[rng.randrange(3)] for _ in range(3))/3 for _ in range(10000)]
    return dict(source_means=dict(values), mean=mean, source_count=3,
        confidence_intervals=dict(t95=[mean-4.30265272975*se, mean+4.30265272975*se], df=2,
            bootstrap95=[_percentile(draws, .025), _percentile(draws, .975)], bootstrap_resamples=10000,
            bootstrap_seed=20261028), leave_one_source_out={source: statistics.mean([value for index, value in enumerate(x)
                if sources[index] != source]) for source in sources}, descriptive_only=True,
        inference_scope='selected_events_fixed_first_seed_train_models_convenience_three_matches_not_random_population',
        performance_pass_flag=None)


def source_level_descriptions(event_records):
    """四支绝对数、三种局部修复相对原支差值，全部负差及缺源保留。"""
    sources = ('SNMOT-060', 'SNMOT-097', 'SNMOT-151')
    metrics = ('same_trusted_anchor', 'other_trusted_identity', 'unknown_measurement', 'unmatched_or_no_measurement',
        'no_trusted_recovery_event')
    summaries = []
    for scope in ('all_selected', 'R', 'RS'):
        selected = [event for event in event_records if scope == 'all_selected' or event['regime'] == scope]
        by_source = {source: [event for event in selected if event['sequence'] == source] for source in sources}
        absolute, paired = [], []
        for metric in metrics:
            means = {}
            for branch in BRANCHES:
                branch_means = {}
                for source, rows in by_source.items():
                    if rows:
                        branch_means[source] = statistics.mean(float(row['branches'][branch]['no_trusted_recovery_observed'])
                            if metric == 'no_trusted_recovery_event' else row['branches'][branch]['absolute_counts'][metric]
                            for row in rows)
                means[branch] = branch_means
                absolute.append(dict(metric=metric, branch=branch, source_means=branch_means,
                    equal_source_mean=statistics.mean(branch_means.values()) if len(branch_means) == 3 else None,
                    unit='event_indicator' if metric == 'no_trusted_recovery_event' else 'frames_per_30_frame_event'))
            for branch in BRANCHES[1:]:
                delta = {source: means[branch][source]-means['original'][source] for source in means['original']}
                paired.append(dict(metric=metric, comparison=branch+'-original', **source_intervals(delta, sources)))
        summaries.append(dict(scope=scope, event_count=len(selected), source_event_counts={source: len(rows)
            for source, rows in by_source.items()}, absolute_four_branches=absolute, paired_descriptions=paired,
            event_means_within_source=True, source_equal_weight=True,
            selected_events_are_not_independent_matches=True, multiplicity_adjusted=False,
            all_selected_scope_is_cap_selected_R_RS_mixture=scope == 'all_selected'))
    return summaries
