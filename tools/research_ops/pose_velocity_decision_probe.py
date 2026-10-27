"""18单元新T分支—决策接口零更新候选；复用原共同状态，不生成自由轨迹。"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]
R = Path('D:/projects/FutsalMOT_Research')
EXP = R / 'pose/pose_velocity_decision_a01'
FOLDS = ('game4', 'game6', 'game9')
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
EXTERNAL = ('v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
GROUPS = ('T_RS', 'T_shuffle_RS')
SEED = 20261024
BRANCHES = ('own_base', 'original_q', 'q1')
OUTCOMES = ('known_correct', 'known_wrong', 'unknown', 'unmatched')
PARAMETERS = dict(seed=SEED, pool='balanced', source_trace_units=9, model_units=6, scoring_units=18,
    optimizer_updates=0, GPU=False, new_detector_or_Pose_inference=False, new_free_tracking=False,
    branches=list(BRANCHES), inference_shape_shuffle=False, quality_gate='original_unshuffled_raw',
    near_motion='original_frozen_reference_train_R_q25_not_new_T_near',
    source_states='original_strong_motion_common_states', history='actual_past_UIDs_only',
    scoring='separate_all_gated_and_original_enabled_batches_FP32_CPU',
    reference_cost='unchanged_recorded_actual_old_motion_cost', q1='mechanism_proxy_not_a_tracking_policy',
    GT='source_validation_reads_original_registry_plus_posthoc_only_never_score_inputs_or_filter',
    source_validation_GT_registry_read=True, score_inputs_GT_free=True,
    manual_quality_policy='optional120_manual_quality_not_adopted_labels_unavailable',
    manual_keypoint_GT_required_for_execution=False, max_resident_source_sequences=1)
PARAMETERS.update(score_workers=2, numeric_threads=1, max_inflight_source_tasks=2,
    dispatch_min_available_RAM_gib=8., dispatch_min_commit_gib=6., dispatch_poll_seconds=1., dispatch_pause_timeout_seconds=600.,
    source_dispatch='original9_order', source_collect='frozen18_matrix_order',
    worker_lifetime='persistent_independent_CPU_processes', resource_pressure='pause_new_dispatch_never_kill_applications')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def physical(value):
    import stat
    path = Path(value)
    require(path.is_absolute(), '来源/输出必须绝对路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(
        r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts), '实际DResearch来源越界或最终测试未封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '拒绝junction或其他重解析点')
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path'])
    require(path.is_file() and sha(path) == value['sha256'], '冻结来源改变：'+str(path))
    return path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, physical(path))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_new(path, value):
    path = physical(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def selected_sources(jobs):
    """固定首seed/平衡池/每fold三场；不看本轮或原结果筛模型。"""
    require(len(jobs) == len({j['job_id'] for j in jobs}) == 54 and all(j['kind'] == 'common_state' for j in jobs),
            '原来源必须完整54共同状态，不能伪造新scope')
    selected = {}
    for job in jobs:
        o = job['original']
        if o['seed'] == SEED and o['pool'] == 'balanced':
            key = (o['fold'], o['sequence'])
            require(key not in selected, '同fold/比赛原trace重复')
            selected[key] = job
    expected = {(fold, sequence) for fold in FOLDS for sequence in
                [next(s for s, f in OLD.items() if f == fold)] + list(EXTERNAL)}
    require(set(selected) == expected, '固定9份trace缺项/增加，不按收益挑选')
    return [selected[fold, seq] for fold in FOLDS for seq in
            [next(s for s, f in OLD.items() if f == fold)] + list(EXTERNAL)]


def matrix(jobs):
    result = []
    for source in selected_sources(jobs):
        o = source['original']
        for group in GROUPS:
            job = dict(source_job_id=source['job_id'], fold=o['fold'], seed=SEED, pool='balanced',
                       sequence=o['sequence'], group=group)
            job['job_id'] = hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
            result.append(job)
    require(len(result) == len({j['job_id'] for j in result}) == 18, '固定18评分单元必须完整')
    return result


def validate_event(event):
    """保留合法空评分事件；没有新logit时不借旧logit补造。"""
    n, m = len(event['history_UIDs']), len(event['candidate_UIDs'])
    require(n > 0 and m > 0 and event['GT_read'] is False and event['stage'] in (0, 1) and type(event['frame_number']) is int
            and len(event['track_ids']) == n and len(set(event['track_ids'])) == n
            and len(set(event['candidate_UIDs'])) == m, '原事件身份/stage/GT边界不符')
    for key in ('bbox_cost', 'reference_cost', 'motion_gate', 'enabled'):
        require(len(event[key]) == n and all(len(row) == m for row in event[key]), '原矩阵维度不同：'+key)
    for key in ('bbox_cost', 'reference_cost'):
        require(all(type(v) in (int, float) and math.isfinite(v) for row in event[key] for v in row), '原代价非有限')
    require(all(len(event[k]) == n for k in ('active_rows', 'enough_history', 'lost_gap')), '原行门禁维度不同')
    locations = [tuple(p) for p in event['scored_locations']]
    expected = [(i, j) for i in range(n) if event['enough_history'][i] for j in range(m) if event['motion_gate'][i][j]]
    require(locations == expected and len(set(locations)) == len(locations), '原all-gated评分位置改变')
    require(all(not event['enabled'][i][j] or (event['active_rows'][i] and (i, j) in locations)
                for i in range(n) for j in range(m)), '原enabled越过已验门禁')
    return locations, [p for p in locations if event['enabled'][p[0]][p[1]]]


def build_inputs(event, index, adapter, public):
    """唯一数值输入边界；该函数没有labels或GT参数。"""
    locations, native = validate_event(event); vectors = []
    for i, j in locations:
        history = [public(index[uid]) for uid in event['history_UIDs'][i]]
        candidate = public(index[event['candidate_UIDs'][j]])
        require(len(history) == 3 and all(a['timestamp_sec'] < b['timestamp_sec'] for a, b in zip(history, history[1:]))
                and history[-1]['timestamp_sec'] < candidate['timestamp_sec'], '必须三个严格过去的真实历史')
        vector = list(adapter.transform_pair(history, candidate))
        require(len(vector) == 195 and all(type(v) in (float, int) and math.isfinite(v) for v in vector)
                and 0 <= vector[-1] <= 1, '新T输入必须原195维/质量gate/有限数值')
        vectors.append(vector)
    by_location = {location: vector for location, vector in zip(locations, vectors)}
    return locations, vectors, native, [by_location[p] for p in native]


def branch_scores(model, vectors, torch):
    """仅取新完成T权重；q=0时仍记录未门控残差，不做除q反推。"""
    empty = dict(base=[], raw_head=[], residual=[], q=[], gated_residual=[],
                 logits={name: [] for name in BRANCHES}, full_forward_equal_original_q=True,
                 input_195_sha256=hashlib.sha256(canonical(vectors).encode()).hexdigest())
    if not vectors:
        return empty
    require(getattr(model, 'variant', None) == 'gated'
            and all(p.device.type == 'cpu' and p.dtype == torch.float32 for p in model.parameters()),
            '只准原gated结构的新T CPU权重，不加载旧logit或GPU')
    x = torch.tensor(vectors, dtype=torch.float32, device='cpu')
    with torch.no_grad():
        motion = torch.cat([x[:, :24], torch.zeros_like(x[:, 24:194])], dim=1)
        base = model.base(motion).reshape(-1)
        head = model.residual(x[:, 24:194]).reshape(-1)
        delta = .5*torch.tanh(head); q = x[:, 194]
        logits = dict(own_base=base, original_q=base+q*delta, q1=base+delta)
        actual = model(x).reshape(-1)
    require(torch.equal(actual, logits['original_q']), '分支拆解不逐值等于同批原完整forward，先停数值准入')
    values = dict(base=base.tolist(), raw_head=head.tolist(), residual=delta.tolist(), q=q.tolist(),
                  gated_residual=(q*delta).tolist(), logits={k: v.tolist() for k, v in logits.items()},
                  full_forward_equal_original_q=True, input_195_sha256=empty['input_195_sha256'])
    require(all(math.isfinite(v) for key in ('base', 'raw_head', 'residual', 'q', 'gated_residual') for v in values[key]),
            '新T分支数值非有限')
    return values


def assignment_record(cost, threshold, linear_assignment):
    matches, rows, columns = linear_assignment(cost, thresh=threshold)
    matches = [[int(i), int(j)] for i, j in matches]
    rows, columns = [int(i) for i in rows], [int(j) for j in columns]
    n, m = cost.shape
    require(len({i for i, _ in matches}) == len({j for _, j in matches}) == len(matches)
            and len(set(rows)) == len(rows) and len(set(columns)) == len(columns)
            and set(rows) | {i for i, _ in matches} == set(range(n))
            and set(columns) | {j for _, j in matches} == set(range(m))
            and not set(rows) & {i for i, _ in matches} and not set(columns) & {j for _, j in matches},
            '完整分配/未匹配行列账本不符')
    return dict(matches=matches, unmatched_rows=rows, unmatched_columns=columns)


def costs_and_assignments(event, locations, scores, geo, np, torch, linear_assignment):
    """原choose_cost及原linear_assignment纯函数；不反馈到历史。"""
    view = dict(event, scored_locations=[list(p) for p in locations], logits=scores['logits'])
    result = {}
    for name in BRANCHES:
        cost, threshold = geo.choose_cost(view, name, np, torch)
        result[name] = dict(cost=cost.tolist(), threshold=threshold,
                           assignment=assignment_record(cost, threshold, linear_assignment))
    return result


def score_event(event, index, model, adapter, geo, np, torch, linear_assignment):
    """评分阶段无GT；all-gated影子批与enabled原生批保持分开。"""
    locations, vectors, native, enabled_vectors = build_inputs(event, index, adapter, geo.public)
    all_scores = branch_scores(model, vectors, torch)
    native_scores = branch_scores(model, enabled_vectors, torch)
    all_cost = costs_and_assignments(event, locations, all_scores, geo, np, torch, linear_assignment)
    native_cost = costs_and_assignments(event, native, native_scores, geo, np, torch, linear_assignment)
    indices = {p: k for k, p in enumerate(locations)}
    numeric = {}
    for name in BRANCHES:
        a, b = np.asarray(all_cost[name]['cost'], dtype=np.float32), np.asarray(native_cost[name]['cost'], dtype=np.float32)
        numeric[name] = dict(maximum_all_gated_vs_enabled_cost_delta=float(np.max(np.abs(a-b))) if a.size else 0.,
            assignments_equal=all_cost[name]['assignment'] == native_cost[name]['assignment'],
            maximum_enabled_logit_delta=max((abs(all_scores['logits'][name][indices[p]]-native_scores['logits'][name][k])
                                             for k, p in enumerate(native)), default=0.))
    threshold = .8 if event['stage'] == 0 else .7
    reference = np.asarray(event['reference_cost'], dtype=np.float32)
    return dict(all_gated=dict(locations=[list(p) for p in locations], **all_scores, decisions=all_cost),
        enabled_native=dict(locations=[list(p) for p in native], **native_scores, decisions=native_cost),
        batch_numeric_comparison=numeric,
        reference=dict(recorded_actual_old_motion_cost=deepcopy(event['reference_cost']),
            assignment=assignment_record(reference, threshold, linear_assignment), threshold=threshold,
            origin='original_trace_recorded_actual_reference_cost_not_new_T_tracking'),
        fixed_state_native_cost_authority='direct_enabled_batch_new_T_counterfactual_not_recorded_new_T_free_tracking',
        q1_is_mechanism_proxy=True, GT_used_for_scoring=False)


def decision_outcome(query, column, candidate_uids, labels, geo):
    if column is None:
        return 'unmatched'
    if query is None:
        return 'unknown'
    value = geo.label(query, labels[candidate_uids[column]])
    return 'unknown' if value is None else 'known_correct' if value == 1 else 'known_wrong'


def empty_transitions():
    return {a: {b: 0 for b in OUTCOMES} for a in OUTCOMES}


def posthoc_rows(event, scored, labels, GT, all_raw, geo, calibration):
    """所有GT访问只在评分完成后；复用原identity/label/IoU，不筛输入。"""
    assignments = {name: dict(scored['enabled_native']['decisions'][name]['assignment']['matches']) for name in BRANCHES}
    locations = [tuple(p) for p in scored['all_gated']['locations']]
    rows = []
    for i, history in enumerate(event['history_UIDs']):
        query, status = geo.identity(history, labels)
        target = next((t for t in GT.get(event['frame_number'], []) if t['gt_id'] == query), None) if query is not None else None
        values = {j: geo.label(query, labels[u]) if query is not None else None for j, u in enumerate(event['candidate_UIDs'])}
        local = {j: k for k, (row, j) in enumerate(locations) if row == i}
        positive = [j for j in local if values[j] == 1]; negative = [j for j in local if values[j] == 0]
        outcomes = {name: decision_outcome(query, assignments[name].get(i), event['candidate_UIDs'], labels, geo) for name in BRANCHES}
        row = dict(row_index=i, track_id=event['track_ids'][i], history_status=status,
            trusted_current_GT_present=target is not None, active=bool(event['active_rows'][i]),
            enough_history=bool(event['enough_history'][i]), lost_gap=bool(event['lost_gap'][i]),
            scored_pairs=len(local), known_positive_scored_pairs=len(positive), known_negative_scored_pairs=len(negative),
            unknown_scored_pairs=sum(values[j] is None for j in local), outcomes=outcomes,
            assignments={name: assignments[name].get(i) for name in BRANCHES},
            original_reference_near_motion=None, margins={name: None for name in BRANCHES},
            diagnostic_quality_gate_all_positive_zero=None)
        if query is None:
            row['source_stop'] = status
        elif target is None:
            row['source_stop'] = 'current_GT_absent'
        else:
            raw_positive = [d for d in all_raw if labels[d['uid']]['state'] == 'matched' and labels[d['uid']]['gt_id'] == query]
            stage_positive = [j for j, value in values.items() if value == 1]
            if not raw_positive:
                row['source_stop'] = 'raw_match_ambiguous' if any(geo.iou(d['bbox_xywh_px'], target['bbox_xywh_px']) >= .5 for d in all_raw) else 'no_any_raw_IoU05'
            elif not stage_positive: row['source_stop'] = 'positive_raw_not_in_this_stage'
            elif not event['enough_history'][i]: row['source_stop'] = 'history_fewer3'
            elif not positive: row['source_stop'] = 'positive_rejected_motion_gate'
            elif not negative: row['source_stop'] = 'no_known_negative_in_gate'
            else: row['source_stop'] = 'both_known_classes_in_motion_gate'
        if positive and negative:
            for name in BRANCHES:
                logits = scored['all_gated']['logits'][name]
                row['margins'][name] = max(logits[local[j]] for j in positive)-max(logits[local[j]] for j in negative)
            row['diagnostic_quality_gate_all_positive_zero'] = all(scored['all_gated']['q'][local[j]] == 0 for j in positive)
        if len(local) >= 2:
            # 只引用原报告校准与原参考logit，绝不把此条件称新T近motion。
            original_locations = {tuple(p): k for k, p in enumerate(event['scored_locations'])}
            original = sorted((event['logits']['motion'][original_locations[i, j]] for j in local), reverse=True)
            row['original_reference_near_motion'] = original[0]-original[1] <= calibration['near_motion_gap']
        rows.append(row)
    return rows


def add_counts(counts, transitions, event, scored, rows):
    counts['stage_events'] += 1; counts['stage_rows'] += len(rows)
    counts['all_gated_edges'] += len(scored['all_gated']['locations'])
    counts['actual_enabled_edges'] += len(scored['enabled_native']['locations'])
    counts['empty_scored_events'] += not scored['all_gated']['locations']
    for row in rows:
        counts['history/'+row['history_status']] += 1; counts['source_stop/'+row['source_stop']] += 1
        counts['trusted_current_GT_present_rows'] += row['trusted_current_GT_present']
        counts['active_rows'] += row['active']; counts['unknown_scored_pairs'] += row['unknown_scored_pairs']
        both = row['known_positive_scored_pairs'] > 0 and row['known_negative_scored_pairs'] > 0
        counts['enough_history_rows'] += row['enough_history']
        counts['both_known_classes_rows'] += both
        counts['reference_near_motion_rows'] += row['original_reference_near_motion'] is True
        counts['active_both_known_rows'] += row['active'] and both
        counts['active_reference_near_both_known_rows'] += row['active'] and both and row['original_reference_near_motion'] is True
        counts['positive_quality_gate_all_zero_rows'] += row['diagnostic_quality_gate_all_positive_zero'] is True
        for target, reference in (('original_q', 'own_base'), ('q1', 'own_base'), ('q1', 'original_q')):
            name = target+'_vs_'+reference
            for subset in ('all_rows', 'trusted_current_GT_present'):
                if subset == 'trusted_current_GT_present' and not row['trusted_current_GT_present']:
                    continue
                transitions[name][subset][row['outcomes'][reference]][row['outcomes'][target]] += 1
            a, b = row['margins'][target], row['margins'][reference]
            if a is not None:
                counts[name+'/ranking_corrects'] += a > 0 and b <= 0
                counts[name+'/ranking_breaks'] += a <= 0 and b > 0
                counts[name+'/ranking_tie_target'] += a == 0
                for subset, enabled in (('active', row['active']), ('active_reference_near',
                        row['active'] and row['original_reference_near_motion'] is True)):
                    if enabled:
                        counts[name+'/'+subset+'_ranking_corrects'] += a > 0 and b <= 0
                        counts[name+'/'+subset+'_ranking_breaks'] += a <= 0 and b > 0
    for name, value in scored['batch_numeric_comparison'].items():
        counts[name+'/all_gated_enabled_assignment_different_events'] += not value['assignments_equal']


def validate_config(config):
    cfg = read(config)
    require(cfg.get('schema') == 'pose_velocity_decision_probe_protocol_v1' and cfg.get('approved_by') == 'root'
            and cfg.get('diagnostic_authorized') is True and cfg.get('training_authorized') is False
            and cfg.get('free_tracking_authorized') is False and cfg.get('test_sealed') is True
            and cfg.get('parameters') == PARAMETERS and Path(cfg['bundle']) == ROOT and ROOT.parent == R/'code',
            '独立18单元冻结准入/测试封存缺失')
    for entry in read(checked(cfg['bundle_manifest']))['files']:
        require(sha(ROOT/entry['path']) == entry['sha256'], '新候选执行源码改变')
    info_done = read(checked(cfg['source_information_complete']))
    require(info_done['status'] == 'complete_zero_update_numeric_Pose_information_chain_manual_quality_pending'
            and info_done['config'] == cfg['source_information_protocol'] and info_done['report'] == cfg['source_information_report']
            and info_done['producer_processes_absent'] is True, '原54信息链未闭合或来源不同')
    checked(info_done['independent_verification'])
    source_cfg = read(checked(cfg['source_information_protocol'])); old_bundle = physical(source_cfg['bundle'])
    for item in read(checked(source_cfg['bundle_manifest']))['files']:
        require(sha(old_bundle/item['path']) == item['sha256'], '原信息链数值源码改变')
    sys.path.insert(0, str(old_bundle/'tools/research_ops'))
    geo = load('pose_information_geometry', old_bundle/'tools/research_ops/pose_information_geometry.py')
    information = load('velocity_probe_original_information_chain', old_bundle/'tools/research_ops/pose_information_chain.py')
    source_cfg2, core, dep, prepared, control, source_jobs = information.context(checked(cfg['source_information_protocol']))
    require(source_cfg2 == source_cfg and cfg['matrix'] == matrix(source_jobs), '源54范围或固定18矩阵不同')
    info_report = read(checked(cfg['source_information_report']))
    require(info_report['status'] == 'complete54_information_chain_zero_updates_not_new_tracking_or_training'
            and info_report['config'] == cfg['source_information_protocol'] and info_report['source_units'] == 54, '原校准/报告未完成')
    bounded = read(checked(cfg['bounded_complete']))
    require(bounded['status'] == 'complete27_training513_tracking_all_paired_intervals_and_independent_exit_verified'
            and bounded['producer_processes_absent'] is True and bounded['final_test_read'] is False, '新T完整训练/追踪未闭合')
    training_done = read(checked(bounded['training_complete']))
    require(training_done['protocol'] == cfg['learning_protocol'], '新T与完成根协议不对应')
    learning_cfg = read(checked(cfg['learning_protocol'])); learning_bundle = physical(learning_cfg['bundle'])
    for entry in read(checked(learning_cfg['bundle_manifest']))['files']:
        require(sha(learning_bundle/entry['path']) == entry['sha256'], '新T实际学习源码改变')
    learning = load('velocity_probe_actual_learning_runtime', learning_bundle/'tools/research_ops/pose_velocity_learning_runtime.py')
    learning.validate_protocol(checked(cfg['learning_protocol']))
    require(learning_cfg['source_training_protocol'] == dep[2]['training_protocol'], '新T与原共同状态不是相同v10来源')
    expected_models = {(fold, group) for fold in FOLDS for group in GROUPS}
    runs = cfg['model_runs']
    require(len(runs) == 6 and {(r['fold'], r['group']) for r in runs} == expected_models
            and all(r['seed'] == SEED for r in runs), '六个新T首seed模型来源不齐/重复')
    for model in runs:
        require(physical(model['run']) == checked(model['training_receipt']).parent, '模型run与独立收据路径不同')
        receipt = read(model['training_receipt']['path']); binding = receipt['binding']
        require(receipt['status'] == 'complete' and receipt['completed_updates'] == 1000
                and binding['protocol_sha256'] == cfg['learning_protocol']['sha256']
                and all(binding[k] == model[k] for k in ('fold', 'seed', 'group')), '不能借旧Pose权重冒充新T')
        actual_last = read(physical(model['run'])/'last_checkpoint.json')
        require({k: actual_last[k] for k in ('path', 'sha256')} == model['last_checkpoint'], '模型last来源不是该run的实际最终检查点')
        checked(model['last_checkpoint'])
    return cfg, information, geo, core, dep, prepared, control, source_jobs, info_report, learning


def plan(config, output):
    cfg, _, _, _, _, _, control, jobs, report, _ = validate_config(config)
    output = physical(output); require(EXP in output.parents and not output.exists(), '新诊断输出越界/已有partial')
    details = {d['job']['job_id']: d for d in report['details']}
    for source in selected_sources(jobs):
        entry = details[source['job_id']]
        receipt = read(checked(entry['receipt']))
        require(receipt['status'] == 'complete' and receipt['job'] == source and receipt['GT_read'] is False
                and receipt['trace'] == entry['trace'] and checked(entry['receipt']) == control/'runs'/source['job_id']/'tracking/receipt.json',
                '原trace收据/源job不同')
    return cfg, dict(status='readonly18_new_T_decision_probe_plan_no_model_loaded', trace_units=9,
        model_units=6, scoring_units=18, new_optimizer_updates=0, new_free_tracking=False,
        new_detector_or_Pose_inference=False, GPU=False, manual_keypoint_GT_available=False,
        source_validation_GT_registry_read=True, GT_annotations_loaded=True, GT_used_for_scoring=False,
        manual_quality_policy='optional120_manual_quality_not_adopted_labels_unavailable',
        manual_keypoint_GT_required_for_execution=False, test_read=False)


def validate_GT_access(value, no_posthoc=False):
    """曾解析来源endpoint_GT与模型是否使用GT分开，不能以public输入冒称进程GT未载。"""
    fields = ('source_validation_GT_registry_read', 'GT_annotations_loaded', 'posthoc_GT_labels_loaded',
              'current_source_posthoc_GT_loaded', 'GT_used_for_scoring', 'GT_free_inputs')
    require(all(k in value for k in fields)
            and value['source_validation_GT_registry_read'] is True and value['GT_annotations_loaded'] is True
            and value['GT_used_for_scoring'] is False and value['GT_free_inputs'] is True
            and type(value['posthoc_GT_labels_loaded']) is bool and type(value['current_source_posthoc_GT_loaded']) is bool
            and (not value['current_source_posthoc_GT_loaded'] or value['posthoc_GT_labels_loaded']),
            '来源验证已经解析GT registry，不能误报GT未载或默许评分使用GT')
    if no_posthoc:
        require(value['posthoc_GT_labels_loaded'] is False and value['current_source_posthoc_GT_loaded'] is False,
                '数值评分门禁只准来源registry验证，不准额外加载后验labels/GT文件')


def gt_access_metadata(context):
    value = dict(source_validation_GT_registry_read=context.source_validation_GT_registry_read,
        GT_annotations_loaded=context.GT_annotations_loaded, posthoc_GT_labels_loaded=context.posthoc_GT_labels_loaded,
        current_source_posthoc_GT_loaded=context.current_source_posthoc_GT_loaded,
        GT_used_for_scoring=False, GT_free_inputs=True)
    validate_GT_access(value)
    return value


def numeric_admission(cfg, config):
    proof = read(physical(cfg['numeric_validation_receipt_path']))
    require(proof['status'] == 'complete_velocity_decision_probe_actual_CPU_numeric_admission'
            and proof['protocol_sha256'] == sha(config) and proof['probe_source_sha256'] == sha(__file__)
            and proof['full_forward_equal_original_q'] is True and proof['all_gated_and_enabled_batches_separate'] is True
            and proof['costs_use_original_choose_cost'] is True and proof['GT_free_inputs'] is True
            and proof['actual_optimizer_updates'] == 0 and proof['test_read'] is False,
            '先完成实际新权重/两批形状/原代价接口的CPU数值准入，不能拿夹具当真实验证')
    validate_GT_access(proof, no_posthoc=True)
    score2 = proof['score2_numeric_admission']
    validate_GT_access(score2, no_posthoc=True)
    require(proof['score2_actual_CPU_spawn_verified'] is True
            and score2['status'] == 'complete_actual_serial_vs_two_spawn_score_workers_exact'
            and score2['workers_exited'] is True and score2['numeric_threads'] == 1
            and len(score2['worker_pids']) == len(set(score2['worker_pids'])) == 2
            and all(type(pid) is int and pid > 0 for pid in score2['worker_pids']),
            '必须真实串行/score2逐值一致并已退出，不能借tracker2+1或串行proof替代')
    return ref(cfg['numeric_validation_receipt_path'])


def process_gate():
    command = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
               "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], check=True,
        capture_output=True, text=True, encoding='utf-8', errors='strict')
    records = json.loads(result.stdout) if result.stdout.strip() else []; records = [records] if isinstance(records, dict) else records
    by_id = {p['ProcessId']: p for p in records}; own = {os.getpid()}; current = by_id.get(os.getpid())
    needle = str(Path(__file__).resolve()).replace('/', '\\').lower()
    def tail(record):
        text = (record.get('CommandLine') or '').replace('"', '').replace('/', '\\').lower()
        return text[text.index(needle):] if needle in text else None
    for _ in range(8):
        parent = by_id.get(current['ParentProcessId']) if current else None
        if parent is None or tail(current) is None or tail(parent) != tail(current) or parent['ProcessId'] in own:
            break
        own.add(parent['ProcessId']); current = parent
    pattern = re.compile(r'(?:^|[\\/\s"\x27])(?:pose_velocity_decision_probe|pose_velocity_learning_(?:control|train)|'
        r'pose_velocity_tracking_(?:control|jobs|analysis)|substitution_tracking_(?:control|jobs)|'
        r'substitution_validation_predictions|v10_(?:train|tracking_control|training_control))[.]py(?=$|[\s"\x27])', re.I)
    blocked = [p for p in records if p['ProcessId'] not in own and ((p.get('Name') or '').lower().startswith('unrealeditor')
               or pattern.search(p.get('CommandLine') or ''))]
    require(not blocked, '相关生产者/重复诊断/UE仍在：'+canonical(blocked))
    return dict(own_launcher_chain=sorted(own), related_producers_absent=True)


class ScoreWorkerContext:
    """一个独立CPU进程的常驻执行闭包；六模型懒缓存、至多一个源序列。"""
    def __init__(self, config, config_sha256):
        require(sha(config) == config_sha256, 'worker冻结配置SHA不同')
        import torch
        torch.set_num_threads(1)
        require(torch.get_num_threads() == 1 and not torch.cuda.is_initialized(), 'score worker必须Torch1/未初始化CUDA')
        context = validate_config(config)
        self.cfg, _, self.geo, self.core, self.dep, self.prepared, _, self.source_jobs, self.info_report, self.learning = context
        self.config = physical(config); self.protocol_sha256 = config_sha256
        self.selected = {j['job_id']: j for j in selected_sources(self.source_jobs)}
        self.reference_details = {d['job']['job_id']: d for d in self.info_report['details']}
        self.models = {}; self.source_cache = None; self.event_cache = None
        # 既有context -> 原v10.validate_config已解析含endpoint_GT的来源registry。
        self.source_validation_GT_registry_read = True; self.GT_annotations_loaded = True
        self.posthoc_GT_labels_loaded = False; self.current_source_posthoc_GT_loaded = False

    def model_for(self, source_job_id, group):
        require(source_job_id in self.selected and group in GROUPS, 'worker只接受冻结9源/两组模型')
        source = self.selected[source_job_id]; fold = source['original']['fold']; key = (fold, group)
        if key not in self.models:
            model_source = next(r for r in self.cfg['model_runs'] if (r['fold'], r['group']) == key)
            _, _, model, adapter, binding = self.learning.complete_model(checked(self.cfg['learning_protocol']), model_source['run'])
            require(binding['fold'] == fold and binding['group'] == group and binding['seed'] == SEED, '常驻新T加载身份不同')
            model.eval(); self.models[key] = model, adapter, binding
        return self.models[key]

    def raw_source(self, sequence):
        if self.source_cache is None or self.source_cache['sequence'] != sequence:
            # 先释放旧源再加载新源，不瞬间同时保留两个完整源。
            self.source_cache = None; self.event_cache = None; self.current_source_posthoc_GT_loaded = False
            source = self.prepared['sources'][sequence]
            frames = self.core.rows(checked(source['source']['cache']))
            index = {d['uid']: d for frame in frames for d in frame['detections']}
            require(len(index) == sum(len(f['detections']) for f in frames), '共享原预测UID重复')
            self.source_cache = dict(sequence=sequence, frames=frames, index=index, posthoc=None)
        return self.source_cache

    def posthoc_source(self, sequence):
        source = self.raw_source(sequence)
        if source['posthoc'] is None:
            _, rt, old, _, _, _, _, _ = self.dep
            labels = read(checked(self.prepared['sources'][sequence]['labels']))['labels']
            GT, _ = rt.load_gt(old['sources'][sequence])
            source['posthoc'] = labels, GT
            self.posthoc_GT_labels_loaded = True; self.current_source_posthoc_GT_loaded = True
        return source['posthoc']

    def event_at(self, source_job_id, event_number):
        require(source_job_id in self.selected and type(event_number) is int and event_number >= 0, '诊断事件必须显式原序号')
        sequence = self.selected[source_job_id]['original']['sequence']; self.raw_source(sequence)
        key = source_job_id, event_number
        if self.event_cache is not None and self.event_cache[0] == key:
            return self.event_cache[1]
        with gzip.open(checked(self.reference_details[source_job_id]['trace']), 'rt', encoding='utf-8') as stream:
            for number, line in enumerate(stream):
                if number == event_number:
                    value = json.loads(line); self.event_cache = key, value; return value
        raise ValueError('原trace没有该事件序号')

    def score_one_event(self, source_job_id, event_number, group):
        """此入口不额外载后验labels/GT；来源验证链此前已经解析endpoint_GT。"""
        import numpy as np
        import torch
        from ultralytics.trackers.utils.matching import linear_assignment
        event = self.event_at(source_job_id, event_number)
        source_job = self.selected[source_job_id]; source = self.raw_source(source_job['original']['sequence'])
        model, adapter, _ = self.model_for(source_job_id, group)
        scored = score_event(event, source['index'], model, adapter, self.geo, np, torch, linear_assignment)
        require(scored['GT_used_for_scoring'] is False, '评分不得使用来源registry或后验GT')
        return dict(source_job_id=source_job_id, event_number=event_number, group=group, scored=scored,
            worker_pid=os.getpid(), numeric_threads=torch.get_num_threads(),
            **gt_access_metadata(self),
            CUDA_initialized=torch.cuda.is_initialized(),
            new_optimizer_updates=0, new_free_tracking=False, test_read=False)

    def score_source_task(self, source_job_id, output, diagnostic_event_limit=None):
        """同一trace的两模型和事件次序不变；不写父进程state/report。"""
        import numpy as np
        import torch
        from ultralytics.trackers.utils.matching import linear_assignment
        require(source_job_id in self.selected and (diagnostic_event_limit is None or
                type(diagnostic_event_limit) is int and 1 <= diagnostic_event_limit <= 4), '只接受冻结源或独立小前缀门禁')
        output = physical(output); require(EXP in output.parents and output.is_dir(), '父进程须先建立独立输出目录')
        source_job = self.selected[source_job_id]; o = source_job['original']; sequence = o['sequence']; fold = o['fold']
        source = self.raw_source(sequence); frames, index = source['frames'], source['index']
        jobs = [j for j in self.cfg['matrix'] if j['source_job_id'] == source_job_id]
        require(len(jobs) == 2 and [j['group'] for j in jobs] == list(GROUPS), '一源任务必须保持两模型原序')
        detail = self.reference_details[source_job_id]; trace = checked(detail['trace'])
        calibration_key = '/'.join(map(str, (fold, SEED, 'balanced')))
        calibration = self.info_report['calibrations'][calibration_key]
        streams = {}; summaries = {}; signatures = defaultdict(set); completed = []
        try:
            for job in jobs:
                self.model_for(source_job_id, job['group'])
                folder = output/'units'/job['job_id']; folder.parent.mkdir(exist_ok=True)
                folder.mkdir()  # 已有partial必须失败，绝不覆盖或重试。
                streams[job['job_id']] = gzip.open(folder/'events.jsonl.gz', 'xt', encoding='utf-8')
                summaries[job['job_id']] = dict(counts=Counter(), transitions={name: {subset: empty_transitions() for subset in
                    ('all_rows', 'trusted_current_GT_present')} for name in
                    ('original_q_vs_own_base', 'q1_vs_own_base', 'q1_vs_original_q')}, maximum_cost_delta={name: 0. for name in BRANCHES})
            with gzip.open(trace, 'rt', encoding='utf-8') as stream:
                for event_number, line in enumerate(stream):
                    if diagnostic_event_limit is not None and event_number >= diagnostic_event_limit:
                        break
                    event = json.loads(line); frame = frames[event['frame_number']-1]
                    require(frame['frame_number'] == event['frame_number'], '源帧与原trace不对应')
                    for job in jobs:
                        model, adapter, _ = self.models[fold, job['group']]
                        scored = score_event(event, index, model, adapter, self.geo, np, torch, linear_assignment)
                        labels, GT = self.posthoc_source(sequence)
                        rows = posthoc_rows(event, scored, labels, GT, frame['detections'], self.geo, calibration)
                        summary = summaries[job['job_id']]
                        add_counts(summary['counts'], summary['transitions'], event, scored, rows)
                        for name in BRANCHES:
                            summary['maximum_cost_delta'][name] = max(summary['maximum_cost_delta'][name],
                                scored['batch_numeric_comparison'][name]['maximum_all_gated_vs_enabled_cost_delta'])
                        signature = hashlib.sha256(canonical([sequence, event['frame_number'], event['stage'],
                            event['history_UIDs'], event['candidate_UIDs']]).encode()).hexdigest()
                        signatures[job['job_id']].add(signature)
                        original = {k: deepcopy(event[k]) for k in ('frame_number', 'stage', 'track_ids', 'history_UIDs',
                            'candidate_UIDs', 'bbox_cost', 'motion_gate', 'enabled', 'active_rows', 'enough_history', 'lost_gap', 'chosen_raw_UID')}
                        record = dict(job=job, source_event_number=event_number, state_signature=signature,
                            original_state=original, new_T=scored, posthoc_rows=rows, new_optimizer_updates=0,
                            new_free_tracking=False, GT_used_only_for_source_validation_and_posthoc=True,
                            **gt_access_metadata(self), test_read=False)
                        streams[job['job_id']].write(canonical(record)+'\n')
        finally:
            for stream in streams.values(): stream.close()
        for job in jobs:
            unit = summaries[job['job_id']]; counts = dict(unit['counts']); path = output/'units'/job['job_id']/'summary.json'
            for transitions in unit['transitions'].values():
                require(sum(sum(row.values()) for row in transitions['all_rows'].values()) == counts.get('stage_rows', 0)
                        and sum(sum(row.values()) for row in transitions['trusted_current_GT_present'].values())
                        == counts.get('trusted_current_GT_present_rows', 0), '四类完整转移表分母不齐')
            result = dict(status='complete_new_T_fixed_state_probe_unit_not_free_tracking' if diagnostic_event_limit is None
                else 'diagnostic_prefix_only_not_formal_source_unit', job=job, trace=detail['trace'], source_receipt=detail['receipt'],
                model_binding=self.models[fold, job['group']][2], calibration_key=calibration_key,
                calibration_source=self.cfg['source_information_report'], counts=counts, transitions=unit['transitions'],
                maximum_all_gated_enabled_cost_delta=unit['maximum_cost_delta'],
                unique_stage_state_signatures=len(signatures[job['job_id']]), events=ref(path.parent/'events.jsonl.gz'),
                score_worker_pid=os.getpid(), numeric_threads=torch.get_num_threads(),
                diagnostic_event_limit=diagnostic_event_limit, new_optimizer_updates=0, new_free_tracking=False,
                **gt_access_metadata(self), test_read=False)
            write_new(path, result); completed.append(dict(job=job, summary=ref(path)))
        return dict(status='source_complete' if diagnostic_event_limit is None else 'diagnostic_source_prefix_complete',
            source_job_id=source_job_id, units=completed, worker_pid=os.getpid(), numeric_threads=torch.get_num_threads(),
            max_resident_source_sequences=1, cached_models=len(self.models),
            new_optimizer_updates=0, new_free_tracking=False, **gt_access_metadata(self), test_read=False)


_SCORE_WORKER = None


def initialize_score_worker(config_path, config_sha256):
    """供正式常驻worker及独立spawn数值验证共同调用；不启动GPU或优化器。"""
    global _SCORE_WORKER
    _SCORE_WORKER = ScoreWorkerContext(config_path, config_sha256)
    return _SCORE_WORKER


def score_worker_event(source_job_id, event_number, group):
    require(_SCORE_WORKER is not None, '先初始化独立score worker')
    return _SCORE_WORKER.score_one_event(source_job_id, event_number, group)


def memory_snapshot():
    """实际物理RAM和系统commit，禁止用working set替代提交余量。"""
    import ctypes
    from ctypes import wintypes
    class PerformanceInformation(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in (
            'CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable',
            'SystemCache', 'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize')] + [
            (name, wintypes.DWORD) for name in ('HandleCount', 'ProcessCount', 'ThreadCount')]
    value = PerformanceInformation(); value.cb = ctypes.sizeof(value)
    api = ctypes.WinDLL('psapi', use_last_error=True).GetPerformanceInfo
    api.argtypes = [ctypes.POINTER(PerformanceInformation), wintypes.DWORD]; api.restype = wintypes.BOOL
    require(api(ctypes.byref(value), value.cb), '无法读取真实RAM/commit，不猜测后派发')
    return dict(available_RAM_gib=value.PhysicalAvailable*value.PageSize/1024**3,
        commit_headroom_gib=(value.CommitLimit-value.CommitTotal)*value.PageSize/1024**3,
        observed_utc=datetime.now(timezone.utc).isoformat(), source='Win32_GetPerformanceInfo_actual_pages')


def dispatch_allowed(snapshot):
    require(all(type(snapshot[k]) in (int, float) and math.isfinite(snapshot[k]) for k in
                ('available_RAM_gib', 'commit_headroom_gib')), '必须实际RAM和commit读数')
    return snapshot['available_RAM_gib'] >= PARAMETERS['dispatch_min_available_RAM_gib'] and \
        snapshot['commit_headroom_gib'] >= PARAMETERS['dispatch_min_commit_gib']


class OrderedSourceResults:
    """原9源顺序派发/18顺序收集；乱序完成暂存，失败不重试。"""
    def __init__(self, expected_units):
        self.expected = expected_units; self.next_dispatch = 0; self.next_collect = 0
        self.issued = set(); self.finished = set(); self.buffer = {}; self.failed = False; self.stopped = False

    def issue(self, index):
        require(not self.failed and not self.stopped and index == self.next_dispatch
                and 0 <= index < len(self.expected) and index not in self.issued
                and len(self.issued-self.finished) < PARAMETERS['max_inflight_source_tasks'], '派发顺序/有界并发/禁止重试边界改变')
        self.issued.add(index); self.next_dispatch += 1

    def accept(self, index, result):
        require(index in self.issued and index not in self.finished
                and [u['job']['job_id'] for u in result['units']] == self.expected[index], '重复/错误源任务或两模型顺序不同')
        self.finished.add(index); self.buffer[index] = result; ready = []
        while self.next_collect in self.buffer:
            ready.append(self.buffer.pop(self.next_collect)); self.next_collect += 1
        return ready

    def fail(self, index):
        require(index in self.issued and index not in self.finished, '未知或重复失败任务')
        self.failed = True; self.finished.add(index)


class ScoreWorkerPool:
    """JSONL传输的两个独立常驻进程；没有kill/terminate或自动重试路径。"""
    def __init__(self, config, output, config_sha256):
        self.config, self.output, self.sha = physical(config), physical(output), config_sha256
        self.token = uuid.uuid4().hex; self.processes = []; self.stderr_streams = []; self.protocol_streams = []; self.exits = []

    def start(self):
        require(self.output.is_dir() and not (self.output/'workers').exists()
                and not (self.output/'score_worker_authorization.json').exists(), '已有worker/未知partial，禁止覆盖')
        (self.output/'workers').mkdir()
        write_new(self.output/'score_worker_authorization.json', dict(parent_pid=os.getpid(), run_token=self.token,
            protocol=ref(self.config), score_workers=2, numeric_threads=1, output=str(self.output)))
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='-1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
            OPENBLAS_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', PYTHONUTF8='0', PYTHONIOENCODING='utf-8')
        for worker in range(2):
            stderr = (self.output/'workers'/f'worker{worker}.process.stderr.log').open('x', encoding='utf-8')
            self.stderr_streams.append(stderr)
            self.protocol_streams.append((self.output/'workers'/f'worker{worker}.protocol.jsonl').open('x', encoding='utf-8'))
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--score-worker', str(worker),
                '--config', str(self.config), '--output', str(self.output), '--config-sha256', self.sha,
                '--parent-pid', str(os.getpid()), '--run-token', self.token]
            self.processes.append(subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                text=True, encoding='utf-8', errors='strict', bufsize=1, env=env))
        ready = [self.receive(i) for i in range(2)]
        for value in ready: validate_GT_access(value, no_posthoc=True)
        require(all(r['status'] == 'worker_ready' and r['worker_index'] == i and r['numeric_threads'] == 1
                    and r['CUDA_initialized'] is False for i, r in enumerate(ready)), '两score worker未真实就绪')
        require(len({r['worker_pid'] for r in ready}) == 2, '必须两个实际独立CPU worker')
        return ready

    def receive(self, worker):
        line = self.processes[worker].stdout.readline()
        require(bool(line), 'score worker异常退出，保留stderr/partial，不重试')
        self.protocol_streams[worker].write(line); self.protocol_streams[worker].flush()
        return json.loads(line)

    def source(self, worker, index, source_job_id):
        p = self.processes[worker]
        p.stdin.write(canonical(dict(action='source', source_index=index, source_job_id=source_job_id))+'\n'); p.stdin.flush()
        value = self.receive(worker)
        require(value.get('source_index') == index and value.get('source_job_id') == source_job_id, 'worker返回错误源身份：'+canonical(value))
        require(value['status'] == 'source_complete', 'score源任务失败保留，不重试：'+canonical(value))
        return value

    def close(self):
        # 正在计算的源先结束，再读stop；不强杀自己的或用户的应用。
        if self.exits: return self.exits
        for p in self.processes:
            if p.poll() is None:
                try: p.stdin.write(canonical(dict(action='stop'))+'\n'); p.stdin.flush()
                except (BrokenPipeError, OSError): pass
        for i, p in enumerate(self.processes):
            if p.stdin:
                try: p.stdin.close()
                except (BrokenPipeError, OSError): pass
            tail = p.stdout.read() if p.stdout else ''
            self.protocol_streams[i].write(tail); self.protocol_streams[i].flush()
            code = p.wait()
            if p.stdout: p.stdout.close()
            self.exits.append(dict(worker_index=i, launcher_pid=p.pid, exit_code=code,
                                   protocol_tail=tail, process_exited=p.poll() is not None))
        for stream in self.stderr_streams: stream.close()
        for stream in self.protocol_streams: stream.close()
        return self.exits


def worker_main(config, output, config_sha256, worker, parent_pid, token):
    """worker只写自身日志和unit产物；全局state/report由父进程独占。"""
    output = physical(output); transport = sys.stdout
    def emit(value): transport.write(canonical(value)+'\n'); transport.flush()
    authorization = read(output/'score_worker_authorization.json')
    require(worker in (0, 1) and authorization['parent_pid'] == parent_pid and authorization['run_token'] == token
            and authorization['protocol'] == ref(config) and authorization['output'] == str(output)
            and sha(config) == config_sha256, 'worker必须来自本次独立父控制器')
    try:
        with (output/'workers'/f'worker{worker}.init.stdout.log').open('x', encoding='utf-8') as out, \
                (output/'workers'/f'worker{worker}.init.stderr.log').open('x', encoding='utf-8') as err:
            with redirect_stdout(out), redirect_stderr(err):
                context = initialize_score_worker(config, config_sha256)
        import torch
        emit(dict(status='worker_ready', worker_index=worker, worker_pid=os.getpid(),
                  numeric_threads=torch.get_num_threads(), CUDA_initialized=torch.cuda.is_initialized(),
                  **gt_access_metadata(context)))
        for line in sys.stdin:
            task = json.loads(line)
            if task['action'] == 'stop':
                emit(dict(status='worker_stopped', worker_index=worker, worker_pid=os.getpid())); return 0
            require(task['action'] == 'source' and type(task['source_index']) is int, '未知worker任务')
            index, source_job_id = task['source_index'], task['source_job_id']
            require(0 <= index < 9 and source_job_id == selected_sources(context.source_jobs)[index]['job_id'], '源派发位置不同')
            logs = output/'source_logs'; logs.mkdir(exist_ok=True)
            try:
                with (logs/f'{index:02d}_{source_job_id}.stdout.log').open('x', encoding='utf-8') as out, \
                        (logs/f'{index:02d}_{source_job_id}.stderr.log').open('x', encoding='utf-8') as err:
                    with redirect_stdout(out), redirect_stderr(err):
                        result = context.score_source_task(source_job_id, output)
                emit(dict(result, source_index=index))
            except BaseException as error:
                failure = dict(status='source_failed_preserved_no_retry', source_index=index, source_job_id=source_job_id,
                    worker_pid=os.getpid(), error=repr(error), traceback=traceback.format_exc(), new_optimizer_updates=0)
                path = output/'source_failures'/f'{index:02d}.json'; write_new(path, failure)
                emit(dict(failure, failure_receipt=ref(path))); return 1
    except BaseException as error:
        emit(dict(status='worker_failed_preserved_no_retry', worker_index=worker, error=repr(error), traceback=traceback.format_exc()))
        return 1
    return 0


def execute(config, output, config_sha256):
    require(config_sha256 is not None and sha(config) == config_sha256, '--execute必须显式匹配新冻结配置SHA')
    cfg, flight = plan(config, output); admission = numeric_admission(cfg, config); processes = process_gate()
    sources = list(dict.fromkeys(j['source_job_id'] for j in cfg['matrix']))
    expected = [[j['job_id'] for j in cfg['matrix'] if j['source_job_id'] == source] for source in sources]
    require(len(sources) == 9 and all(len(jobs) == 2 for jobs in expected), '固定9源/18单元范围不变')
    output = physical(output); output.mkdir(parents=True)
    write_new(output/'preflight.json', dict(flight, numeric_admission=admission, processes=processes))
    state = dict(status='starting2_persistent_CPU_score_workers', protocol_sha256=config_sha256,
        completed_units=[], completed_sources=[], dispatched_sources=[], finished_out_of_order=[], active=[],
        optimizer_updates=0, test_read=False, score_workers=2, numeric_threads=1,
        source_validation_GT_registry_read=True, GT_annotations_loaded=True, worker_GT_metadata={})
    def save():
        state['updated_utc'] = datetime.now(timezone.utc).isoformat()
        target = output/'state.json'; temporary = output/'state.tmp'
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8'); temporary.replace(target)
    save(); ordered = OrderedSourceResults(expected); pool = ScoreWorkerPool(config, output, config_sha256)
    futures = {}; details = []; paused_since = None; failure = None
    def resources_ready():
        nonlocal paused_since
        snapshot = memory_snapshot(); state['last_resource_sample'] = snapshot
        if dispatch_allowed(snapshot): paused_since = None; return True
        if paused_since is None: paused_since = time.monotonic()
        state['status'] = 'paused_new_dispatch_low_actual_RAM_or_commit'; state['dispatch_pause_seconds'] = time.monotonic()-paused_since
        save(); require(time.monotonic()-paused_since <= PARAMETERS['dispatch_pause_timeout_seconds'],
                        '实际RAM/commit不足持续超时，停止新派发并保留partial，不kill或重试')
        return False
    try:
        while not resources_ready():
            if (output/'STOP').exists(): ordered.stopped = True; break
            time.sleep(PARAMETERS['dispatch_poll_seconds'])
        if not ordered.stopped:
            state['workers'] = pool.start(); save()
            idle = [0, 1]
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix='score_process_IO_only') as transport:
                while futures or (ordered.next_dispatch < len(sources) and not ordered.failed and not ordered.stopped):
                    if (output/'STOP').exists(): ordered.stopped = True
                    while idle and ordered.next_dispatch < len(sources) and not ordered.failed and not ordered.stopped:
                        if not resources_ready(): break
                        index = ordered.next_dispatch; ordered.issue(index); worker = idle.pop(0)
                        future = transport.submit(pool.source, worker, index, sources[index]); futures[future] = (worker, index)
                        state['dispatched_sources'].append(dict(source_index=index, source_job_id=sources[index], worker_index=worker))
                    state['active'] = [dict(worker_index=w, source_index=i, source_job_id=sources[i]) for w, i in futures.values()]
                    if paused_since is None: state['status'] = 'running2_persistent_CPU_score_workers'
                    save()
                    if not futures:
                        time.sleep(PARAMETERS['dispatch_poll_seconds']); continue
                    done, _ = wait(list(futures), timeout=PARAMETERS['dispatch_poll_seconds'], return_when=FIRST_COMPLETED)
                    for future in sorted(done, key=lambda f: futures[f][1]):
                        worker, index = futures.pop(future); idle.append(worker); idle.sort()
                        try:
                            result = future.result()
                            validate_GT_access(result)
                            state['worker_GT_metadata'][str(worker)] = {k: result[k] for k in (
                                'source_validation_GT_registry_read', 'GT_annotations_loaded', 'posthoc_GT_labels_loaded',
                                'current_source_posthoc_GT_loaded', 'GT_used_for_scoring', 'GT_free_inputs')}
                            for unit in result['units']:
                                value = read(checked(unit['summary']))
                                validate_GT_access(value)
                                require(value['status'] == 'complete_new_T_fixed_state_probe_unit_not_free_tracking'
                                        and value['job'] == unit['job'] and value['numeric_threads'] == 1,
                                        'worker实际unit收据不完整或线程改变')
                            for ready in ordered.accept(index, result):
                                state['completed_sources'].append(ready['source_job_id'])
                                details.extend(u['summary'] for u in ready['units'])
                                state['completed_units'].extend(u['job']['job_id'] for u in ready['units'])
                        except BaseException as error:
                            if index not in ordered.finished: ordered.fail(index)
                            else: ordered.failed = True
                            failure = error
                            state['failure_source'] = dict(source_index=index, source_job_id=sources[index], error=repr(error))
                        state['finished_out_of_order'] = [dict(source_index=i, source_job_id=v['source_job_id'], units=v['units'])
                                                         for i, v in sorted(ordered.buffer.items())]
                        save()
        exits = pool.close(); state['worker_exits'] = exits; state['active'] = []; save()
        if failure is not None: raise failure
        if ordered.stopped:
            state['status'] = 'stopped_at_user_source_boundary_no_replay'; save(); return dict(status=state['status'], new_optimizer_updates=0)
        require(len(details) == 18 and state['completed_units'] == [j['job_id'] for j in cfg['matrix']]
                and len(exits) == 2 and all(p['exit_code'] == 0 and p['process_exited'] for p in exits)
                and all(s.closed for s in pool.stderr_streams+pool.protocol_streams), '18有序收集/两worker实际退出/日志闭合未齐')
        worker_exit_gate = process_gate()  # 同时核实际解释器/launcher身份已退，不能只看wait包装器。
        report = dict(schema='pose_velocity_decision_probe_complete_v1',
            status='complete18_new_T_fixed_state_decision_probe_zero_updates_not_free_tracking',
            protocol=ref(config), parameters=PARAMETERS, source_trace_units=9, model_units=6, scoring_units=18,
            units=details, source_information_report=cfg['source_information_report'], bounded_complete=cfg['bounded_complete'],
            numeric_admission=admission, score_workers=state['workers'], score_worker_exits=exits,
            worker_actual_process_exit_gate=worker_exit_gate,
            all_worker_logs_closed=True, parent_exclusive_state_and_report=True,
            new_optimizer_updates=0, new_detector_or_Pose_inference=False, new_free_tracking=False,
            inference_shape_shuffle=False, GT_used_only_for_source_validation_and_posthoc=True,
            source_validation_GT_registry_read=True, GT_annotations_loaded=True, GT_used_for_scoring=False, GT_free_inputs=True,
            parent_posthoc_GT_labels_loaded=False, score_worker_GT_metadata=state['worker_GT_metadata'],
            test_read=False, manual_keypoint_GT_complete=False,
            manual_quality_policy='optional120_manual_quality_not_adopted_labels_unavailable',
            manual_keypoint_GT_required_for_execution=False,
            formal_equivalence_or_noninferiority=False,
            limitations=['first predetermined seed; all five sources are observed development',
                'only original recorded nonempty-stage states, not an all-video-event denominator',
                'fixed strong-motion histories/candidates; q1 is a mechanism proxy, not a free policy or AssA gain',
                'all-gated and native batches separate; known/unknown/unmatched and negative results retained',
                'reference-near uses original trainR calibration; repeated rows/signatures are not independent matches',
                'source validation parsed original endpoint_GT; this is not a GT-unloaded process claim',
                'model scoring uses only public prediction fields; labels/GT are loaded separately only for posthoc explanation',
                'optional120_manual_quality_not_adopted_labels_unavailable; not an execution prerequisite',
                'score2 parity is separate from tracker2+1 performance evidence'])
        write_new(output/'report.json', report)
        state.update(status=report['status'], report=ref(output/'report.json')); save()
        return dict(status=report['status'], scoring_units=18, score_workers=2, new_optimizer_updates=0, new_free_tracking=False)
    except BaseException as error:
        if not pool.exits: state['worker_exits'] = pool.close()
        state['uncollected_active_at_failure'] = deepcopy(state['active'])
        state.update(status='failed_preserved_no_replay', error=repr(error), traceback=traceback.format_exc(), active=[]); save(); raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path); parser.add_argument('--output', type=Path)
    parser.add_argument('--config-sha256'); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--score-worker', type=int, choices=(0, 1))
    parser.add_argument('--parent-pid', type=int); parser.add_argument('--run-token')
    args = parser.parse_args(); os.environ.update(CUDA_VISIBLE_DEVICES='-1', YOLO_AUTOINSTALL='false')
    if args.score_worker is not None:
        require(not args.execute and args.config is not None and args.output is not None
                and args.config_sha256 and args.parent_pid and args.run_token, 'worker必须由本次父控制器完整授权')
        sys.exit(worker_main(args.config, args.output, args.config_sha256, args.score_worker, args.parent_pid, args.run_token))
    elif args.config is None or args.output is None:
        require(not args.execute and args.config is None and args.output is None, '实际计划/执行必须同时给config和output')
        result = dict(status='candidate_contract_only_not_frozen_or_executed', schema='pose_velocity_decision_probe_protocol_v1',
            parameters=PARAMETERS, required_references=['source_information_complete', 'source_information_protocol',
                'source_information_report', 'bounded_complete', 'learning_protocol', 'model_runs', 'numeric_validation_receipt_path'],
            numeric_admission_status='complete_velocity_decision_probe_actual_CPU_numeric_admission',
            new_optimizer_updates=0, test_read=False)
    elif args.execute:
        result = execute(args.config, args.output, args.config_sha256)
    else:
        if args.config_sha256 is not None: require(sha(args.config) == args.config_sha256, '计划配置SHA不同')
        result = plan(args.config, args.output)[1]
    print(canonical(result))
