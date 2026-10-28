"""训练域状态差异诊断的独立终验；只核本轮记录，不读GT、模型或原缓存。"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import random
import statistics
import subprocess
import traceback

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/state_gap_diagnosis_a01'
STATUS = 'complete12_train_rollouts_bounded_oracle_all_records_and_exit_verified'
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
FOLDS = ('game4', 'game6', 'game9')
BRANCHES = ('original', 'history_only', 'motion_only', 'both')
PLAN_KEYS = {'event_id', 'frame_number', 'track_id', 'wrong_uid', 'correct_uid'}
OUTCOMES = ('same_trusted_anchor', 'other_trusted_identity', 'unknown_measurement', 'unmatched_or_no_measurement')
RECOVERY_SOURCE_KEYS = ('inventory', 'sources', 'jobs', 'inputs_source', 'original_tracking_source', 'track_guard_source',
    'worker_support', 'source_velocity_protocol', 'tracker_parameters', 'diagnostic_parameters', 'analysis_parameters', 'worker_service')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def physical(value, *, child=None):
    p = Path(value)
    require(p.is_absolute(), '终验只接受绝对物理路径')
    p = Path(os.path.abspath(p))
    require(R in p.parents and not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower()) for part in p.parts), '测试继续封存')
    if child is not None:
        require(Path(child) in p.parents, '终验输出必须属于本轮新目录')
    for current in (p, *p.parents):
        if current.exists() or current.is_symlink():
            require(not current.is_symlink() and not getattr(current.lstat(), 'st_file_attributes', 0)&0x400, '禁止junction或符号链接')
    return p


def file_sha(path):
    h = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def reference(path):
    return dict(path=str(physical(path)), sha256=file_sha(path))


class DiskRowsView:
    """可重复迭代的只读磁盘视图；每次仅解码一行，完整消费时核对行数和gzip尾部。"""
    def __init__(self, path, *, expected_rows=None):
        self.path = Path(path)
        require(expected_rows is None or type(expected_rows) is int and expected_rows >= 0, '压缩记录行数声明无效')
        self.expected_rows = expected_rows

    def __iter__(self):
        count = 0
        with gzip.open(self.path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():
                    continue
                value = json.loads(line); count += 1
                yield value
        require(self.expected_rows is None or count == self.expected_rows, '压缩记录行数不同')
        if self.expected_rows is None:
            self.expected_rows = count

    def __len__(self):
        if self.expected_rows is None:
            for _ in self:
                pass
        return self.expected_rows

    def __getitem__(self, index):
        require(type(index) is int, '磁盘日志只允许按单个帧索引读取，禁止整段物化')
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        for number, value in enumerate(self):
            if number == index:
                return value
        raise IndexError(index)


def read_reference(value):
    """终验数据读取仅本轮新记录；禁止借嵌套ref重新打开GT/权重/旧cache。"""
    require(isinstance(value, dict) and set(value)>={'path', 'sha256'} and re.fullmatch('[0-9a-f]{64}', value['sha256']), '完整来源引用缺失')
    p = physical(value['path'], child=EXP)
    require(file_sha(p) == value['sha256'], '新记录SHA变化：'+str(p))
    if p.name.endswith('.jsonl.gz'):
        return DiskRowsView(p, expected_rows=value.get('rows'))
    require(p.suffix == '.json', '终验只读取新JSON/压缩JSONL记录')
    return json.loads(p.read_text(encoding='utf-8-sig'))


def proof(value):
    require(value.get('evaluation_GT_coordinate_files_opened') is False and value.get('models_unchanged') is True
        and value.get('inputs_unchanged') is True and value.get('optimizer_updates') == 0 and value.get('test_read') is False,
        '正常追踪GT隔离/权重/输入/零更新证据不完整')
    guard = value.get('GT_guard', {})
    require(guard.get('python_open_audit_installed') is True and guard.get('blocked_open_attempts') == 0
        and guard.get('GT_annotations_opened') is False, 'GT读取保护曾触发或未安装')


def stage_check(stage, number):
    require(stage['frame_number'] == number and stage['stage'] in ('high_score', 'low_score', 'unconfirmed'), 'stage帧号/名称不同')
    tracks, candidates = stage['track_ids'], stage['candidate_UIDs']
    require(len(tracks) == len(set(tracks)) and len(candidates) == len(set(candidates)) and len(stage['rows']) == len(tracks), '原stage行列UID重复/丢失')
    require(stage['cost_shape'] == [len(tracks), len(candidates)], '包括空矩阵的shape不符')
    threshold = {'high_score': .8, 'low_score': .5, 'unconfirmed': .7}[stage['stage']]
    require(stage['threshold'] == threshold and stage['native_ordered_batch_forward_preserved'] is True, '原三stage门槛/前向批次改变')
    matches = stage['assignments']
    require(len({pair[0] for pair in matches}) == len({pair[1] for pair in matches}) == len(matches)
        and all(len(pair) == 2 and 0 <= pair[0] < len(tracks) and 0 <= pair[1] < len(candidates) for pair in matches), '原分配不再是一对一或越界')
    require(set(stage['unmatched_track_rows']) == set(range(len(tracks)))-{pair[0] for pair in matches}
        and set(stage['unmatched_detection_columns']) == set(range(len(candidates)))-{pair[1] for pair in matches}, '分配后未匹配行列被丢弃')


def logs_check(rows, *, first=1, count=750):
    require(len(rows) == count and [row['frame_number'] for row in rows] == list(range(first, first+count)), '必须完整连续帧，包括空检测')
    states, natives, counts = [], [], []
    for row in rows:
        require(row['frame_index'] == row['frame_number']-1 and len(row['stages']) == 3
            and [stage['stage'] for stage in row['stages']] == ['high_score', 'low_score', 'unconfirmed'], '帧索引或原三stage记录不完整')
        for stage in row['stages']:
            stage_check(stage, row['frame_number'])
        require(set(row['tracks_before']) == set(row['tracks_after']) == {'tracked_stracks', 'lost_stracks', 'removed_stracks'}, '生命周期列表不完整')
        require(re.fullmatch('[0-9a-f]{64}', row['full_state_sha256']) is not None, '完整动态状态指纹缺失')
        states.append(row['full_state_sha256']); natives.append(digest(row['native_output'])); counts.append(len(row['native_output']))
    return states, natives, counts


def _refs(value):
    """报告统一使用job_id→ref，拒绝缺项/重复项。"""
    require(isinstance(value, dict), '报告来源必须job_id到完整ref的映射')
    return value


def same(actual, expected):
    if type(expected) in (int, float):
        require(type(actual) in (int, float) and math.isfinite(actual) and abs(actual-expected) <= 1e-10*max(1., abs(expected)), '新记录描述数值不同（此容差不是性能界限）')
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) >= set(expected), '重建描述字段缺失')
        for key, value in expected.items(): same(actual[key], value)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), '重建描述顺序/长度不同')
        for a, b in zip(actual, expected): same(a, b)
    else: require(actual == expected and type(actual) is type(expected), '重建描述声明不符')


def interval(values):
    sources = tuple(OLD)
    if set(values) != set(sources):
        return dict(source_means=values, confidence_intervals=None, CI_status='missing_selected_events_in_source_not_filled',
            missing_sources=[s for s in sources if s not in values], observed_source_count=len(values), descriptive_only=True)
    x = [values[s] for s in sources]; mean = statistics.mean(x); se = statistics.stdev(x)/math.sqrt(3)
    rng = random.Random(20261028)
    draws = sorted(sum(x[rng.randrange(3)] for _ in range(3))/3 for _ in range(10000))
    def percentile(q):
        index = 9999*q; lower = math.floor(index); upper = math.ceil(index)
        return draws[lower]+(draws[upper]-draws[lower])*(index-lower)
    return dict(source_means=values, mean=mean, source_count=3, confidence_intervals=dict(
        t95=[mean-4.30265272975*se, mean+4.30265272975*se], df=2,
        bootstrap95=[percentile(.025), percentile(.975)], bootstrap_resamples=10000, bootstrap_seed=20261028),
        leave_one_source_out={s: statistics.mean(value for key, value in values.items() if key != s) for s in sources},
        descriptive_only=True, performance_pass_flag=None)


def branch_summary_check(summary, records):
    totals = {name: Counter() for name in BRANCHES}; paired = []
    for event in records:
        for name in BRANCHES:
            branch = event['branches'][name]
            counts = Counter(row['outcome'] for row in branch['rows'])
            require(set(counts) <= set(OUTCOMES), '未知分支outcome被隐式归类')
            same(branch['absolute_counts'], {key: counts[key] for key in OUTCOMES})
            require(branch['observed_frames'] == branch['requested_frames'] == len(branch['rows']) == 30
                and branch['source_end_truncated'] is False, '必须保留完整30未来帧')
            offset = next((row['frame_number']-event['frame_number'] for row in branch['rows'] if row['outcome'] == 'same_trusted_anchor'), None)
            require(branch['first_trusted_recovery_offset_frames'] == offset and branch['no_trusted_recovery_observed'] is (offset is None)
                and branch['recovery_time_right_censored'] is (offset is None), '未知/无写入不能冒充恢复或伪造恢复时长')
            totals[name].update(branch['absolute_counts']); totals[name]['observed_frames'] += 30
            totals[name]['events'] += 1; totals[name]['no_recovery_events'] += int(offset is None)
        for name in BRANCHES[1:]:
            base, value = event['branches']['original'], event['branches'][name]
            row = {key: event[key] for key in ('event_id', 'fold', 'sequence', 'regime', 'model_id', 'track_id', 'frame_number')}
            row.update(branch=name, original=base['absolute_counts'], intervention=value['absolute_counts'],
                paired_count_difference={key: value['absolute_counts'][key]-base['absolute_counts'][key] for key in OUTCOMES},
                original_first_recovery=base['first_trusted_recovery_offset_frames'], intervention_first_recovery=value['first_trusted_recovery_offset_frames'])
            paired.append(row)
    require(summary['event_count'] == len(records) and summary['performance_pass_flag'] is None
        and summary['new_optimizer_updates'] == 0 and summary['confidence_intervals'] is None, '事件不能当独立比赛作性能通过判定')
    same(summary['absolute_branch_totals'], {name: dict(counts) for name, counts in totals.items()})
    pair_key = lambda value: (value['event_id'], value['branch'])
    same(sorted(summary['paired_events'], key=pair_key), sorted(paired, key=pair_key))
    descriptions = summary['source_level_descriptions']
    require([row['scope'] for row in descriptions] == ['all_selected', 'R', 'RS'], '全部混合及R/RS描述缺失')
    for scope in descriptions:
        selected = [row for row in records if scope['scope'] == 'all_selected' or row['regime'] == scope['scope']]
        same(scope['source_event_counts'], {s: sum(row['sequence'] == s for row in selected) for s in OLD})
        require(scope['event_count'] == len(selected) and scope['event_means_within_source'] is True and scope['source_equal_weight'] is True
            and scope['selected_events_are_not_independent_matches'] is True and scope['multiplicity_adjusted'] is False, '比赛聚类或多重比较声明不同')
        absolute, paired_descriptions = [], []
        for metric in (*OUTCOMES, 'no_trusted_recovery_event'):
            means = {}
            for name in BRANCHES:
                values = {}
                for source in OLD:
                    rows = [row for row in selected if row['sequence'] == source]
                    if rows:
                        values[source] = statistics.mean(float(row['branches'][name]['no_trusted_recovery_observed']) if metric == 'no_trusted_recovery_event'
                            else row['branches'][name]['absolute_counts'][metric] for row in rows)
                means[name] = values
                absolute.append(dict(metric=metric, branch=name, source_means=values,
                    equal_source_mean=statistics.mean(values.values()) if len(values) == 3 else None,
                    unit='event_indicator' if metric == 'no_trusted_recovery_event' else 'frames_per_30_frame_event'))
            for name in BRANCHES[1:]:
                delta = {source: means[name][source]-means['original'][source] for source in means['original']}
                paired_descriptions.append(dict(metric=metric, comparison=name+'-original', **interval(delta)))
        same(scope['absolute_four_branches'], absolute); same(scope['paired_descriptions'], paired_descriptions)
    return paired


def recovery_check(cfg, state, report, readref):
    """独立核旧成功来源、完整750流式准入与异常预算；不将旧进程冒充正常退出。"""
    recovery = cfg.get('recovery')
    if not recovery:
        require(not state.get('recovery') and not report.get('recovery'), '未授权恢复来源被注入')
        return None
    require(state.get('recovery') == report.get('recovery') == recovery and report.get('protocol') is not None,
        '恢复配置/状态/报告的完整来源不同')
    old, interrupted = readref(recovery['source_protocol']), readref(recovery['source_state'])
    failure = readref(recovery['interruption'])
    require(all(cfg[key] == old[key] for key in RECOVERY_SOURCE_KEYS) and cfg['numeric_admission'] == old['numeric_admission'],
        '恢复改变原模型/来源/矩阵/数值与统计')
    require(interrupted['protocol'] == recovery['source_protocol'] and failure['source_state'] == recovery['source_state']
        and failure['actual_research_controller_and_spawn_processes_absent'] is True
        and failure['actual_exit_codes'] is None and failure['partial_actual_frame_advances'] is None,
        '旧失联进程/partial退出码或实际推进数被补造')
    observes, annotations = recovery['inherit_observe'], recovery['inherit_posthoc']
    require(observes == interrupted['observe'] and annotations == interrupted['posthoc'] and len(observes) == 5
        and len(annotations) == 2 and set(annotations) <= set(observes), '只允许继承旧五观察/二后验成功收据')
    missing = [job['job_id'] for job in cfg['jobs'] if job['job_id'] not in observes]
    require(recovery['restart_incomplete_jobs_explicit'] == missing and len(missing) == 7,
        '七项缺失观察未明确登记或重复执行已成功观察')
    require(all(report['observe'][key] == value for key, value in observes.items())
        and all(report['posthoc'][key] == value for key, value in annotations.items()), '恢复成功来源被替换')
    admission = readref(recovery['streaming_admission'])
    require(admission['status'] == 'complete_streamed750_posthoc_and_bounded_memory_gate'
        and admission['bundle'] == cfg['bundle'] and admission['bundle_manifest'] == cfg['bundle_manifest']
        and admission['worker_exited'] is True and type(admission['exit_code']) is int and admission['exit_code'] == 0
        and admission['peak_worker_RSS_bytes'] <= 3221225472 and admission['minimum_available_RAM_bytes'] >= 8589934592
        and admission['minimum_commit_headroom_bytes'] >= 6442450944, '实际750流式/内存/退出准入未闭合')
    job = admission['job_id']
    require(job in observes and job not in annotations and report['posthoc'][job] == admission['posthoc'],
        '完整750流式准入必须继承且不能重做旧成功后验')
    require(cfg['worker_profile']['track_workers'] == 2 and cfg['worker_profile']['posthoc_workers'] == 1
        and cfg['in_flight_estimate_bytes'] == 3221225472, '恢复的2track/1posthoc或3GiB在飞预留变化')
    expected = dict(inherited_complete_first_pass_frame_advances=3750, new_successful_first_pass_frame_advances=5250,
        interrupted_partial_actual_frame_advances=None, interrupted_partial_count=3, partial_preserved=True,
        logical_budget_includes_inherited_success=True, physical_retry_work_not_claimed_zero=True, interruption=recovery['interruption'])
    require(report['budget'].get('execution_attempt_budget') == state['budget'].get('execution_attempt_budget') == expected,
        '旧partial未知推进与继承/新执行预算未完整独立披露')
    return dict(old=old, observes=observes, old_protocol=recovery['source_protocol'])


def verify_records(cfg, state, report, readref):
    """纯函数；readref可由只读SHA验证器或内存测试夹具提供。"""
    require(cfg.get('schema') == 'state_gap_diagnosis_protocol_v1' and cfg.get('approved_by') == 'root'
        and cfg.get('test_sealed') is True and cfg.get('optimizer_updates') == 0 and cfg.get('new_image_predictions') == 0, '独立零更新诊断协议不符')
    jobs = cfg['jobs']; jobmap = {job['job_id']: job for job in jobs}
    cells = {(j['regime'], j['fold'], j['seed'], j['sequence']) for j in jobs}
    expected = {(regime, fold, 20261024, sequence) for regime in ('R', 'RS') for fold in FOLDS for sequence, game in OLD.items() if game != fold}
    require(len(jobmap) == len(jobs) == len(cells) == 12 and cells == expected and set(cfg['sources']) == set(OLD)
        and all(source['frames'] == 750 for source in cfg['sources'].values()), '必须完整首seed R/RS三fold各两训练源，不能读留出或验证比赛')
    require(cfg.get('phase') == 'formal' and cfg.get('execute_authorized') is True
        and cfg['tracker_parameters'] == dict(track_high_thresh=.25, track_low_thresh=.1, new_track_thresh=.25, track_buffer=30, match_thresh=.8, fuse_score=True), '正式准入或绝对数值参数改变')
    require(state.get('status') == 'complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed' and not state.get('active'), '全部实际任务及分析尚未终态')
    require(report.get('status') == 'complete12_train_rollouts_and_bounded_state_propagation_diagnosis'
        and report.get('test_read') is False and report['budget'].get('optimizer_updates') == 0
        and report.get('all_negative_and_unknown_preserved') is True and report.get('independent_factor_validation_started') is False
        and report.get('performance_scores_not_computed') is True, '报告未完整保留负项/unknown或零更新边界')
    observes, annotations = _refs(report['observe']), _refs(report['posthoc'])
    require(state['observe'] == observes and state['posthoc'] == annotations, '状态与报告来源映射不同')
    require(set(observes) == set(annotations) == set(jobmap), '12原追踪/后验来源缺失')
    recovery = recovery_check(cfg, state, report, readref)
    fingerprints, stage_count, row_count, annotation_events, event_frame_evidence = {}, 0, 0, [], {}
    for key, job in jobmap.items():
        receipt = readref(observes[key])
        require(receipt['schema'] == 'state_gap_observe_receipt_v1' and receipt['status'] == 'complete'
            and receipt['job'] == job and receipt['frames'] == 750 and receipt['frames_log']['rows'] == 750
            and receipt['source_cache'] == cfg['sources'][job['sequence']]['cache'] and receipt['observer_enabled'] is True, '原完整rollout身份/预算不符')
        if report.get('protocol') is not None:
            expected_protocol = recovery['old_protocol'] if recovery and key in recovery['observes'] else report['protocol']
            require(receipt.get('protocol') == expected_protocol, '观察收据旧/新实际协议来源不同')
        proof(receipt)
        logs = readref(receipt['frames_log']); states, natives, counts = logs_check(logs)
        require(receipt['frame_counts'] == counts and receipt['native_sha256'] == digest([row['native_output'] for row in logs])
            and receipt['state_sequence_sha256'] == digest(states), '原输出/逐帧状态摘要不符')
        fingerprints[key] = dict(states=states, natives=natives)
        stage_count += sum(len(row['stages']) for row in logs)
        job_rows = sum(len(stage['track_ids']) for row in logs for stage in row['stages']); row_count += job_rows
        annotation = readref(annotations[key]); rows = readref(annotation['all_rows'])
        require(annotation['job'] == job and annotation['observe'] == observes[key] and annotation['total_frames'] == 750
            and annotation['new_solver_calls'] == 0 and len(rows) == annotation['all_rows']['rows']
            and len(rows) == job_rows == annotation['summary']['absolute_counts'].get('windows', 0), '后验行/全部负项分母不符')
        require(all(row['job_id'] == key and row['sequence'] == job['sequence'] and row['condition_is_cause'] is False
            and len(row['candidate_UIDs']) == len(row['pair_labels']) and all(value is None or type(value) is int and value in (0, 1) for value in row['pair_labels']) for row in rows), '未知标签被伪造或后验行来源不同')
        annotation_events.extend(annotation['events']['events'])
        for event in annotation['events']['events']:
            require(1 <= event['frame_number'] <= 750, '首次切换帧号越界')
            frame = logs[event['frame_number']-1]
            event_frame_evidence[event['event_id']] = dict(
                initialized={uid for stage in frame['stages'] for uid in stage['candidate_UIDs']},
                measurements=[item for item in frame['lifecycle'] if item['operation'] in ('update', 're_activate')],
                tracked_after=frame['tracks_after']['tracked_stracks'])
    require(set(report['clean_pool_structures']) == set(FOLDS), '原三fold自然观测候选结构缺失')
    clean_windows = 0
    for fold, structure in report['clean_pool_structures'].items():
        rows = readref(structure['rows'])
        require(len(rows) == structure['rows']['rows'] == 1000 and len({row['window_uid'] for row in rows}) == 1000
            and all(row['sequence'] in OLD and OLD[row['sequence']] != fold and row['teacher_forced_history'] is True for row in rows)
            and structure['summary']['absolute_counts']['windows'] == 1000, '自然观测训练池结构/UID/排除heldout不同')
        clean_windows += len(rows)
    require(state['selected_events'] == report['selection'], '固定全事件清单来源不同')
    selected = readref(report['selection']); all_events = selected['events']; chosen = selected['selected']
    require(len({event['event_id'] for event in all_events}) == len(all_events) and len({event['event_id'] for event in chosen}) == len(chosen)
        and len(chosen) <= 60 and all(event['selected'] and event['candidate_eligible'] and not event['exclusion_reasons'] for event in chosen), '事件重复/超额/不合格事件被执行')
    require({row['event_id'] for row in chosen} == {row['event_id'] for row in all_events if row['selected']}, '入选清单与全排除记录不一致')
    require(len(annotation_events) == len(all_events) and len({event['event_id'] for event in annotation_events}) == len(all_events), '原后验全部首错/排除记录有丢失或重复')
    originals = {event['event_id']: event for event in annotation_events}
    for event in all_events:
        original = originals.get(event['event_id'])
        require(original is not None and all(event.get(key) == value for key, value in original.items()), '固定筛选更改原始后验事件')
        if event['selected']:
            evidence = event_frame_evidence[event['event_id']]
            writes = [item for item in evidence['measurements'] if item['track_id'] == event['track_id'] and item['after']['record']['uid'] == event['wrong_uid']]
            after = [track for track in evidence['tracked_after'] if track['track_id'] == event['track_id']]
            require(event['available_future_source_frames'] >= 30 and event['correct_uid'] in evidence['initialized']
                and len(writes) == len(after) == 1 and after[0]['record']['uid'] == event['wrong_uid']
                and writes[0]['before']['history_UIDs'] == event['pre_error_history_UIDs']
                and len(event['pre_error_history_UIDs']) == 3, '实际首次错写/同帧correct初始化/可修目标证据不符')
    order = lambda row: (row['fold'], row['sequence'], row['frame_number'], row['regime'], row['model_id'], row['track_id'], row['event_id'])
    counts, expected_selected = Counter(), []
    for event in sorted(all_events, key=order):
        require(event['job_id'] in jobmap and all(event[field] == jobmap[event['job_id']][field] for field in ('fold', 'sequence', 'regime', 'model_id', 'seed')), '事件模型/训练来源不同')
        take = event['candidate_eligible'] and counts[event['fold']] < 20
        require(event['selected'] is bool(take), '未使用固定排序/fold20上限或挑选有利事件')
        if take:
            counts[event['fold']] += 1; expected_selected.append(event['event_id'])
    require([row['event_id'] for row in chosen] == expected_selected and all(value <= 20 for value in counts.values()), '入选事件顺序/上限不同')
    eventmap = {event['event_id']: event for event in chosen}
    byjob = Counter(event['job_id'] for event in chosen)
    plans, replays, summaries = map(_refs, (report['plans'], report['replay'], report['branch_posthoc']))
    require(state['plans'] == plans and state['replay'] == replays and state['branch_posthoc'] == summaries, '状态与分支来源映射不同')
    require(set(plans) == set(replays) == set(summaries) == set(byjob), '有事件任务的计划/四分支/后验来源缺失')
    prefix_frames, branch_advances, paired_events, all_branch_records = 0, 0, 0, []
    for key in byjob:
        plan_body = readref(plans[key]); values = plan_body['plans']; planmap = {p['event_id']: p for p in values}
        expected_ids = {event['event_id'] for event in chosen if event['job_id'] == key}
        require(len(planmap) == len(values) == byjob[key] and set(planmap) == expected_ids and all(set(p) == PLAN_KEYS for p in values), 'replay计划含GT标签/坐标或事件不完整')
        for event_id, value in planmap.items():
            event = eventmap[event_id]
            require(all(value[field] == event[field] for field in PLAN_KEYS), '五字段计划与后验原事件不同')
        replay = readref(replays[key]); proof(replay)
        maximum = max(p['frame_number'] for p in values)
        require(replay['schema'] == 'state_gap_replay_receipt_v1' and replay['status'] == 'complete' and replay['job'] == jobmap[key]
            and replay['plans'] == plans[key] and replay['original_observe'] == observes[key] and replay['prefix_frames'] == maximum
            and replay['branch_frame_advances'] == len(values)*124 and replay['future_branch_frames'] == len(values)*120, '重建/四支预算或来源不符')
        if report.get('protocol') is not None:
            require(replay.get('protocol') == report['protocol'], '新四分支必须绑定恢复后的实际协议')
        prefix = readref(replay['prefix'])
        require(len(prefix) == maximum and [row['frame_number'] for row in prefix] == list(range(1, maximum+1))
            and [row['full_state_sha256'] for row in prefix] == fingerprints[key]['states'][:maximum]
            and [row['native_sha256'] for row in prefix] == fingerprints[key]['natives'][:maximum], '完整前缀未精确复现原状态/ID/输出')
        events = replay['events']; require(len(events) == len(values) and {event['event_id'] for event in events} == expected_ids, '四支实际事件缺失/重复')
        for item in events:
            plan = planmap[item['event_id']]; number = plan['frame_number']
            snap = readref(item['snapshot']); require(snap['schema'] == 'state_gap_portable_snapshot_v1', '独立快照缺失')
            require(set(item['branches']) == set(BRANCHES), '不能只保留有效分支')
            for name, value in item['branches'].items():
                branch = readref(value); log = readref(branch['frames_log'])
                states, natives, _ = logs_check(log, first=number, count=31)
                require(branch['schema'] == 'state_gap_oracle_replay_v1' and branch['branch'] == name and branch['plan'] == plan
                    and branch['future_frames'] == 30 and branch['new_optimizer_updates'] == 0
                    and branch['not_deployable_or_main_tracking_score'] is True, '分支身份/完整30帧或oracle口径不同')
                intervention = branch['intervention']; expected_fields = {'original': [], 'history_only': ['history'], 'motion_only': ['mean', 'covariance'], 'both': ['history', 'mean', 'covariance']}[name]
                require(intervention['branch'] == name and intervention['allowed_fields'] == expected_fields
                    and set(intervention['actual_changed_fields']) <= set(expected_fields) and intervention['non_target_fields_unchanged'] is True
                    and intervention['GT_coordinates_used'] is False and intervention['local_oracle_not_global_reassignment'] is True, '修复越权/GT框代替预测框')
                if name == 'original':
                    require(branch['original_branch_exact_checked'] is True and not intervention['actual_changed_fields']
                        and states == fingerprints[key]['states'][number-1:number+30]
                        and natives == fingerprints[key]['natives'][number-1:number+30]
                        and branch['full_state_sha256'] == states, '原分支没有完整逐帧精确复现')
        summary = readref(summaries[key]); records = summary['event_records']
        require(summary['status'] == 'complete' and summary['job'] == jobmap[key] and summary['replay'] == replays[key]
            and len(records) == len(values) and {event['event_id'] for event in records} == expected_ids, '后验四支summary缺项')
        for event in records:
            require(set(event['branches']) == set(BRANCHES), '后验丢弃失败分支')
            for name, branch in event['branches'].items():
                require(branch['observed_frames'] == branch['requested_frames'] == 30 and branch['source_end_truncated'] is False
                    and sum(branch['absolute_counts'].values()) == 30 and len(branch['rows']) == 30, '四支unknown/lost/错误分母不同')
                if name == 'original': require(branch['exact_original_reproduction'] is True, '后验原支精确复现凭据缺失')
            paired_events += 3
        branch_summary_check(summary['summary'], records)
        all_branch_records.extend(records)
        prefix_frames += maximum; branch_advances += len(values)*124
    total = 9000+prefix_frames+branch_advances
    require(prefix_frames <= 9000 and branch_advances <= 7440 and total <= 25440, '本轮逻辑帧预算越界')
    expected_budget = dict(first_pass_frame_advances=9000, prefix_frame_advances=prefix_frames, branch_frame_advances=branch_advances,
        total_formal_frame_advances=total, selected_events=len(chosen), optimizer_updates=0, new_image_predictions=0)
    require(all(report['budget'].get(k) == v for k, v in expected_budget.items()) and report['budget'] == state['budget'], '最终报告预算不同')
    require(report['budget']['numeric_admission'] == cfg['numeric_admission'], '数值准入消费必须另列')
    numeric = readref(cfg['numeric_admission'])
    require(numeric['status'] == 'complete_real_observer_original_ABA_spawn_snapshot_resource_admission' and numeric['all_workers_exited'] is True
        and numeric['selected_worker_profile'] == (recovery['old']['worker_profile'] if recovery else cfg['worker_profile']) and numeric['diagnostic_frame_advances'] > 0
        and numeric['optimizer_updates'] == numeric['new_image_predictions'] == 0 and numeric['test_read'] is False, '真实数值/进程/硬件准入未闭合')
    require(report['worker_exits'] == state['worker_exits'] and len(state['worker_exits']) == cfg['worker_profile']['track_workers']+cfg['worker_profile']['posthoc_workers']
        and all(item.get('process_exited') is True and item.get('exit_code') == 0 and item.get('joined') is True for item in state['worker_exits']), '每个实际worker未正常close/join/exit0')
    branch_summary_check(report['oracle_summary'], all_branch_records)
    return dict(status=STATUS, jobs=12, unique_source_matches=3, source_unique_frames=2250,
        observed_stage_records=stage_count, observed_track_stage_rows=row_count, selected_events=len(chosen),
        oracle_paired_events=paired_events, clean_natural_pool_windows=clean_windows, budget=expected_budget,
        numeric_diagnostic_frame_advances_separate=numeric['diagnostic_frame_advances'], GT_or_weights_or_cache_read=False,
        new_model_forward_or_tracking_or_TrackEval_runs=0, test_read=False)


def process_snapshot():
    script = "Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(python|pythonw|powershell|pwsh)\\.exe$'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    values = json.loads(result.stdout.strip() or '[]')
    return values if isinstance(values, list) else [values]


def absent(snapshot, state=None):
    own = os.getpid(); names = ('state_gap_control.py', 'state_gap_diagnosis_control.py')
    found = [row for row in snapshot if row.get('ProcessId') != own and row.get('Name', '').lower() in ('python.exe', 'pythonw.exe', 'powershell.exe', 'pwsh.exe')
        and any(name in (row.get('CommandLine') or '') for name in names)
        and str(EXP).replace('\\', '/').lower() in (row.get('CommandLine') or '').replace('\\', '/').lower()]
    # spawn命令不携带配置路径，必须同时匹配已记录worker PID、父控制器及实际命令身份。
    state = state or {}
    worker_ids = {item.get('worker_pid') for item in state.get('workers', [])}
    for row in snapshot:
        command = row.get('CommandLine') or ''
        if row.get('ProcessId') in worker_ids and row.get('ParentProcessId') == state.get('controller_pid') and 'multiprocessing.spawn' in command and row.get('Name', '').lower() in ('python.exe', 'pythonw.exe'):
            found.append(row)
    require(not found, '本轮实际控制器/worker/launcher身份仍在，不能签终态')
    return dict(matching_actual_processes=found, observer_processes_absent=True, checked_own_verifier_pid=own)


def write_new(path, value):
    p = physical(path, child=EXP); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def verify(config, control, output):
    config, control, output = map(physical, (config, control, output))
    require(EXP in output.parents and not output.parent.exists(), '独立终验不能覆盖unknown partial或历史成功')
    cfg = read_reference(reference(config)); require(control == physical(cfg['control_root']) and control.parent == EXP and re.fullmatch(r'control_a\d{2}', control.name), '只能验本轮明确控制attempt目录')
    state_ref, report_ref = reference(control/'driver_state.json'), reference(control/'analysis_a01/report.json')
    state, report = read_reference(state_ref), read_reference(report_ref)
    require(state['protocol'] == report['protocol'] == reference(config) and state['analysis'] == report_ref, '最终协议/分析/状态来源绑定不同')
    output.parent.mkdir(parents=True)
    write_new(output.parent/'intent.json', dict(status='started_not_committed', protocol=reference(config), implementation=reference(__file__), new_model_forward_calls=0, test_read=False))
    try:
        initial = absent(process_snapshot(), state)
        result = verify_records(cfg, state, report, read_reference)
        workers = state.get('worker_exits', [])
        require(workers and all(item.get('joined') is True and item.get('exit_code') == 0 and item.get('process_exited') is True for item in workers), '必须保留每个实际worker关闭/join/exit0证据')
        result.update(schema='state_gap_independent_verification_v1', protocol=reference(config), implementation=reference(__file__),
            state=state_ref, report=report_ref, initial_exit=initial, final_exit=absent(process_snapshot(), state),
            producer_processes_absent=True, workers=workers, verified_utc=datetime.now(timezone.utc).isoformat())
        write_new(output, result); return result
    except BaseException as error:
        write_new(output.parent/'failed.json', dict(status='failed_state_gap_independent_verification_partial_preserved', error=repr(error), traceback=traceback.format_exc(), new_model_forward_calls=0, test_read=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'control', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    if args.execute:
        value = verify(args.config, args.control, args.output)
        print(canonical(dict(status=value['status'], jobs=value['jobs'], selected_events=value['selected_events'], budget=value['budget'])))
    else:
        print(canonical(dict(status='readonly_state_gap_verifier_not_executed', new_model_forward_calls=0, test_read=False)))
