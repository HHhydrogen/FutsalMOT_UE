"""既有资格与弱标签的纯分类；不读文件、不评分、不改标签或执行假设mask。"""
from collections import Counter
import math
import random
from statistics import mean, stdev

SOURCE_FOLDS = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
FOLDS = ('game4', 'game6', 'game9')
THRESHOLDS = {'high_score': .8, 'low_score': .5, 'unconfirmed': .7}
B_CLASSES = ('1_query_history_or_fields_unknown', '2_unique_known_positive', '3_no_known_positive_with_unknown',
    '4_GT_absent_no_known_positive', '5_GT_present_no_trusted_raw', '6_trusted_raw_outside_stage_or_scoring', '7_unresolved')
PRIMARY_KEYS = ('contains_scoring_ineligible_known', 'contains_scoring_ineligible_positive',
    'no_known_positive_with_unknown', 'eligible_trusted_correct_without_known_positive')
LABEL_GROUPS = ('positive', 'known_negative', 'unknown')
PROBABILITY_STATUSES = ('not_applicable', 'scoring_eligibility_unknown', 'cost_missing', 'probability_rejected',
    'strict_cost_feasible', 'boundary_unknown', 'cost_above_threshold_unresolved')


def require(ok, message):
    if not ok: raise ValueError(message)


def bool_null(value, name):
    require(value is None or type(value) is bool, name+'必须bool/null'); return value


def any_three(values):
    if any(v is True for v in values): return True
    return None if any(v is None for v in values) else False


def scoring_eligible(stage, active, enabled):
    if stage == 'low_score' or active is False: return False
    if active is None: return False if enabled is False else None
    return enabled


def probability_status(eligible, cost, threshold):
    if eligible is False: return 'not_applicable'
    if eligible is None: return 'scoring_eligibility_unknown'
    if cost is None: return 'cost_missing'
    if cost == 1.: return 'probability_rejected'
    if cost < threshold: return 'strict_cost_feasible'
    if cost == threshold: return 'boundary_unknown'
    return 'cost_above_threshold_unresolved'


def classify_row(row, annotation=None, metadata=None):
    """逐原生行精确join；返回全行摘要与候选，调用方可只保存选中窗候选。"""
    job = row['job']; stage = row['stage']; require(stage in THRESHOLDS and row['threshold'] == THRESHOLDS[stage], '原stage门槛不同')
    history = row['history_UIDs']; require(isinstance(history, list) and len(history) <= 3 and len(set(history)) == len(history), '真实历史UID无效')
    source_candidates = row['pose_candidates']; uids = [c['uid'] for c in source_candidates]; labels = [c['label'] for c in source_candidates]
    require(len(uids) == len(set(uids)) and all(isinstance(v, str) for v in uids), 'candidate UID缺失/重复')
    require(all(v is None or type(v) is int and v in (0, 1) for v in labels) and labels.count(1) <= 1, '原标签必须0/1/null且正例至多1')
    counts = dict(all_pairs=len(labels), known_pairs=sum(v is not None for v in labels), positive_pairs=labels.count(1),
        known_negative_pairs=labels.count(0), unknown_pairs=labels.count(None))
    absolute = row['absolute_counts']
    require(absolute['candidates'] == counts['all_pairs'] and absolute['positive'] == counts['positive_pairs']
        and absolute['known_negative'] == counts['known_negative_pairs'] and absolute['unknown'] == counts['unknown_pairs'], '原候选分母不同')
    query = row['query_GT_id']; flags = row['flags']; active = bool_null(flags.get('learned_active'), 'learned_active')
    trusted = bool_null(flags.get('trusted_three_history'), 'trusted_three_history')
    unavailable = []; required_annotation = ('history_status', 'current_GT_present', 'raw_correct_UIDs', 'history_UIDs', 'candidate_UIDs', 'pair_labels', 'query_GT_id')
    if annotation is None:
        unavailable.append('annotation'); annotation_values = {}
    else:
        require(isinstance(annotation, dict), '后验行须字典'); annotation_values = annotation
        for key in required_annotation:
            if key not in annotation: unavailable.append('annotation.'+key)
        for key in ('frame_number', 'stage', 'row_index', 'track_id', 'history_UIDs', 'query_GT_id'):
            if key in annotation: require(annotation[key] == row[key], '后验坐标/历史/query不同：'+key)
        if 'candidate_UIDs' in annotation: require(annotation['candidate_UIDs'] == uids, '后验candidate UID顺序不同')
        if 'pair_labels' in annotation: require(annotation['pair_labels'] == labels, '后验pair标签不同')
        if 'history_count' in annotation: require(annotation['history_count'] == len(history), '后验历史数量不同')
    present = bool_null(annotation_values.get('current_GT_present'), 'current_GT_present')
    if present is None: unavailable.append('annotation.current_GT_present')
    raw = annotation_values.get('raw_correct_UIDs')
    if raw is not None:
        require(isinstance(raw, list) and len(set(raw)) == len(raw) and all(isinstance(v, str) for v in raw), '可信raw列表无效')
        require(absolute['correct_raw'] == len(raw), '原可信raw数量不同')
    else: unavailable.append('annotation.raw_correct_UIDs')
    if trusted is None: unavailable.append('flags.trusted_three_history')
    if active is None and stage != 'low_score': unavailable.append('flags.learned_active')
    anchor = row['earliest_stage_trusted3_anchor']; drift = None if anchor is None or query is None else str(anchor['gt_id']) != str(query)
    require(bool_null(flags.get('earliest_stage_trusted3_anchor_drift'), 'anchor_drift') == drift, 'anchor漂移摘要不同')
    if anchor is not None: require(type(anchor['frame_number']) is int and anchor['frame_number'] <= row['frame_number'], '不能使用未来anchor')
    if metadata is not None:
        coordinate = (job['job_id'], row['frame_number'], stage, row['row_index'], row['track_id'])
        require(coordinate == tuple(metadata[k] for k in ('source_job_id', 'candidate_frame_number', 'source_stage', 'source_row_index', 'source_track_id'))
            and metadata['fold'] == job['fold'] and metadata['sequence'] == job['sequence'] and metadata['teacher_model_id'] == job['model_id']
            and metadata['history_UIDs'] == history and metadata['query_GT_id'] == query and metadata['candidate_UIDs'] == uids
            and metadata['pair_labels'] == labels and metadata['anchor_drift'] == drift, '选中窗口metadata逐值join失败')
        require(job['regime'] == 'R' and job['seed'] == 20261024 and isinstance(metadata['window_uid'], str), '主表只允许首seed R teacher选中窗')
    candidates = []; K = counts['known_pairs']; group_counts = {g: Counter() for g in LABEL_GROUPS}
    probability_counts = {g: Counter() for g in LABEL_GROUPS}
    for index, candidate in enumerate(source_candidates):
        enabled = bool_null(candidate.get('enabled'), 'enabled'); cost = candidate.get('reference_cost')
        require(cost is None or type(cost) in (int, float) and math.isfinite(cost), '成本必须有限或显式缺失')
        if stage == 'low_score': require(enabled is None and active is not True, '低分stage不应有MLP mask')
        eligible = scoring_eligible(stage, active, enabled)
        if eligible is None: unavailable.append('candidate.'+str(index)+'.scoring_eligible')
        status = probability_status(eligible, cost, row['threshold']); label = candidate['label']
        group = 'unknown' if label is None else ('positive' if label == 1 else 'known_negative')
        eligibility_key = 'unknown' if eligible is None else ('eligible' if eligible else 'ineligible')
        group_counts[group][eligibility_key] += 1; probability_counts[group][status] += 1
        motion_gate = enabled if stage != 'low_score' and active is True else None
        motion_gate_missing = (None if motion_gate is not None else 'low_score_not_applicable' if stage == 'low_score' else
            'inactive_motion_gate_not_observed' if active is False else 'active_status_unknown' if active is None else 'enabled_missing')
        window_weight = 0. if label is None or K == 0 else 1./K
        candidates.append(dict(candidate_index=index, uid=candidate['uid'], label=label, label_group=group, enabled=enabled,
            motion_gate=motion_gate, motion_gate_missing_reason=motion_gate_missing,
            scoring_eligible=eligible, probability_status=status, reference_cost=cost, stage_threshold=row['threshold'],
            BCE_window_pair_weight=window_weight, BCE_R_step_pair_weight=window_weight/3,
            excluded_known_window_weight=window_weight if eligible is False else 0.,
            unresolved_known_window_weight=window_weight if eligible is None else 0.,
            hypothetical_scoring_mask=eligible, labels_changed=False, hypothetical_mask_executed=False))
    known_candidates = [c for c in candidates if c['label'] is not None]; positive_candidates = [c for c in candidates if c['label'] == 1]
    known_ineligible = any_three([None if c['scoring_eligible'] is None else not c['scoring_eligible'] for c in known_candidates])
    positive_ineligible = any_three([None if c['scoring_eligible'] is None else not c['scoring_eligible'] for c in positive_candidates])
    eligible_raw = None if raw is None else any_three([c['scoring_eligible'] for c in candidates if c['uid'] in raw])
    fourth = False if counts['positive_pairs'] else eligible_raw
    primary = dict(zip(PRIMARY_KEYS, (known_ineligible, positive_ineligible, counts['positive_pairs'] == 0 and counts['unknown_pairs'] > 0, fourth)))
    history_ok = len(history) == 3 and trusted is True and query is not None and annotation_values.get('history_status') == 'trusted_consistent_history'
    if not history_ok or unavailable: b_class = B_CLASSES[0]
    elif counts['positive_pairs'] == 1: b_class = B_CLASSES[1]
    elif counts['unknown_pairs'] > 0: b_class = B_CLASSES[2]
    elif present is False: b_class = B_CLASSES[3]
    elif not raw: b_class = B_CLASSES[4]
    elif not any(uid in uids for uid in raw) or eligible_raw is False: b_class = B_CLASSES[5]
    else: b_class = B_CLASSES[6]
    gap = row.get('actual_observation_gap_frames'); require(gap is None or type(gap) is int and gap > 0, 'gap必须正整数或null')
    gap_bin = 'unknown' if gap is None else ('1' if gap == 1 else '2_to5' if gap <= 5 else '6_to10' if gap <= 10 else '11_to30' if gap <= 30 else 'gt30')
    n = len(candidates); candidate_bin = '0' if n == 0 else '1' if n == 1 else '2_to4' if n <= 4 else '5_to8' if n <= 8 else '9_to16' if n <= 16 else 'gt16'
    group_counts['known'] = group_counts['positive']+group_counts['known_negative']
    group_counts['all'] = group_counts['known']+group_counts['unknown']
    probability_counts['known'] = probability_counts['positive']+probability_counts['known_negative']
    probability_counts['all'] = probability_counts['known']+probability_counts['unknown']
    summary = dict(schema='state_label_alignment_window_v1', job_id=job['job_id'], fold=job['fold'], sequence=job['sequence'],
        teacher_regime=job['regime'], teacher_seed=job['seed'], frame_number=row['frame_number'], stage=stage, row_index=row['row_index'], track_id=row['track_id'],
        is_selected_R_window=metadata is not None, window_uid=None if metadata is None else metadata['window_uid'],
        history_UIDs=list(history), query_GT_id=query, earliest_stage_trusted3_anchor=anchor, anchor_drift=drift,
        B_class=b_class, primary_flags=primary, unavailable_field=sorted(set(unavailable)), counts=counts,
        scoring_counts={g: {k: group_counts[g][k] for k in ('eligible', 'ineligible', 'unknown')} for g in ('all', 'known', *LABEL_GROUPS)},
        probability_counts={g: {k: probability_counts[g][k] for k in PROBABILITY_STATUSES} for g in ('all', 'known', *LABEL_GROUPS)},
        bce_weights=dict(known_K=K, window_known_mass=1. if K else 0., R_step_known_mass=1./3 if K else 0.,
            excluded_known_window_mass=sum(c['excluded_known_window_weight'] for c in candidates),
            excluded_known_R_step_mass=sum(c['excluded_known_window_weight'] for c in candidates)/3,
            unresolved_known_window_mass=sum(c['unresolved_known_window_weight'] for c in candidates),
            unresolved_known_R_step_mass=sum(c['unresolved_known_window_weight'] for c in candidates)/3,
            CE_pair_additive_decomposition_available=False),
        raw_correct_UIDs=raw, current_GT_present=present, history_bin=str(len(history)), gap_bin=gap_bin, candidate_bin=candidate_bin,
        overlap_flags=dict(known_positive_present=bool(positive_candidates), unknown_present=counts['unknown_pairs'] > 0,
            trusted_correct_raw_present=None if raw is None else bool(raw), trusted_correct_raw_unique=None if raw is None else len(raw) == 1,
            trusted_correct_raw_in_stage=None if raw is None else any(uid in uids for uid in raw), eligible_trusted_correct_raw=eligible_raw,
            no_scoring_eligible_candidate=not any(c['scoring_eligible'] is True for c in candidates) if not any(c['scoring_eligible'] is None for c in candidates) else None,
            positive_probability_rejected=any(c['probability_status'] == 'probability_rejected' for c in positive_candidates),
            anchor_drift_is_true_identity_error=False),
        source_labels_unchanged=True, hypothetical_mask_executed=False, new_optimizer_updates=0, new_model_forwards=0,
        new_tracking=0, new_solver_calls=0, new_TrackEval=0, GT_coordinates_read=False)
    return summary, candidates


def quantile(values, probability):
    position = (len(values)-1)*probability; lower = int(position); fraction = position-lower
    return values[lower]*(1-fraction)+values[min(lower+1, len(values)-1)]*fraction


def describe_sources(values):
    known = {k: v for k, v in values.items() if v is not None}; n = len(known)
    require(all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 100 for v in known.values()), '描述窗口率须有限0至100或null')
    result = dict(source_rates_pp=values, n_independent_sources=n, mean_rate_pp=mean(known.values()) if known else None,
        Student_t_95CI=None, percentile_match_bootstrap_95CI=None, leave_one_source_out_mean={},
        bootstrap_seed=20261029, bootstrap_repeats=10000, multiplicity_adjusted=False, performance_metric=False)
    if set(values) != set(SOURCE_FOLDS) or n != 3: return result
    xs = list(known.values()); m = mean(xs); half = 4.302652729749462*stdev(xs)/math.sqrt(3); rng = random.Random(20261029)
    draws = sorted(mean(xs[rng.randrange(3)] for _ in range(3)) for _ in range(10000))
    result.update(Student_t_95CI=[m-half, m+half], percentile_match_bootstrap_95CI=[quantile(draws, .025), quantile(draws, .975)],
        leave_one_source_out_mean={s: mean(v for other, v in known.items() if other != s) for s in known}, Student_t_degrees_of_freedom=2)
    return result


def summarize_selected(rows):
    """仅metadata精确join的3000选中R窗；free敏感性行不进入主分母。"""
    selected = [r for r in rows if r['is_selected_R_window']]
    require(len(selected) == 3000 and len({r['window_uid'] for r in selected}) == 3000, '主表须3000唯一选中R窗')
    cells = {}
    for fold in FOLDS:
        for sequence, heldout in SOURCE_FOLDS.items():
            if fold == heldout: continue
            group = [r for r in selected if r['fold'] == fold and r['sequence'] == sequence]
            require(len(group) == 500 and all(r['teacher_regime'] == 'R' and r['teacher_seed'] == 20261024 for r in group), '每fold两允许来源各500首seed R窗')
            cells[fold, sequence] = group
    primary = {}
    for key in PRIMARY_KEYS:
        source_rates = {}; cell_counts = {}
        for sequence, heldout in SOURCE_FOLDS.items():
            fold_rates = []
            for fold in FOLDS:
                if fold == heldout: continue
                group = cells[fold, sequence]; counts = Counter('null' if r['primary_flags'][key] is None else str(r['primary_flags'][key]).lower() for r in group)
                denominator = counts['true']+counts['false']; fold_rates.append(None if denominator == 0 else 100*counts['true']/denominator)
                cell_counts[fold+':'+sequence] = dict(true=counts['true'], false=counts['false'], null=counts['null'], total=500, identified_denominator=denominator)
            source_rates[sequence] = None if any(v is None for v in fold_rates) else mean(fold_rates)
        true_rows = [r for r in selected if r['primary_flags'][key] is True]
        primary[key] = dict(describe_sources(source_rates), fold_source_counts=cell_counts,
            absolute_window_counts=dict(true=len(true_rows), false=sum(r['primary_flags'][key] is False for r in selected),
                null=sum(r['primary_flags'][key] is None for r in selected), total=3000),
            supervision_weights_for_true_windows={name: sum(r['bce_weights'][name] for r in true_rows) for name in
                ('window_known_mass', 'R_step_known_mass', 'excluded_known_window_mass', 'excluded_known_R_step_mass',
                 'unresolved_known_window_mass', 'unresolved_known_R_step_mass')})
    return dict(schema='state_label_alignment_selected_summary_v1', selected_windows=3000, free_sensitivity_rows_excluded=len(rows)-3000,
        B_class_counts={k: sum(r['B_class'] == k for r in selected) for k in B_CLASSES},
        absolute_counts={k: sum(r['counts'][k] for r in selected) for k in ('all_pairs', 'known_pairs', 'positive_pairs', 'known_negative_pairs', 'unknown_pairs')},
        bce_weights={k: sum(r['bce_weights'][k] for r in selected) for k in ('window_known_mass', 'R_step_known_mass', 'excluded_known_window_mass',
            'excluded_known_R_step_mass', 'unresolved_known_window_mass', 'unresolved_known_R_step_mass')},
        four_primary_descriptions=primary, seed_fold_windows_are_not_independent_sources=True, performance_scores_computed=False,
        source_labels_unchanged=True, hypothetical_mask_executed=False, new_optimizer_updates=0, new_model_forwards=0)
