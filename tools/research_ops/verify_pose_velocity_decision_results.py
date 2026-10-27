"""18单元零更新决策探针的独立流式终验；不导入模型、Torch、GT标签或追踪器。"""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
import gzip
import hashlib
import io
from itertools import zip_longest
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import traceback

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/pose_velocity_decision_a01'
PROBE_SHA = '5d5791c170f836be9a1bd13e14c51ee1ddafa8f271fab3c50086b2db68eb0cef'
DONE = 'complete18_new_T_fixed_state_decision_probe_zero_updates_not_free_tracking'
STATUS = 'complete18_decision_sources_all_events_counts_transitions_and_actual_exit_verified'
FOLDS = ('game4', 'game6', 'game9')
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
EXTERNAL = ('v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
GROUPS = ('T_RS', 'T_shuffle_RS')
BRANCHES = ('own_base', 'original_q', 'q1')
OUTCOMES = ('known_correct', 'known_wrong', 'unknown', 'unmatched')
CONTRASTS = (('original_q', 'own_base'), ('q1', 'own_base'), ('q1', 'original_q'))
ORIGINAL_FIELDS = ('frame_number', 'stage', 'track_ids', 'history_UIDs', 'candidate_UIDs', 'bbox_cost',
    'motion_gate', 'enabled', 'active_rows', 'enough_history', 'lost_gap', 'chosen_raw_UID')


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(path):
    path = Path(path); require(path.is_absolute(), '终验来源/输出必须绝对路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
            for p in path.parts), '研究物理根越界或最终测试未封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            value = part.lstat()
            require(not stat.S_ISLNK(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): digest.update(block)
    return digest.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path']); require(path.is_file() and sha(path) == value['sha256'], '来源SHA改变：'+str(path))
    return path


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def is_producer(command):
    return bool(re.search(r'(?:^|[\\/\s\"\x27])(?:pose_velocity_decision_probe|validate_pose_velocity_decision_numeric)'
        r'[.]py(?=$|[\s\"\x27])', command or '', re.I))


def processes_absent():
    command = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
               "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    reply = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], check=True,
        capture_output=True, text=True, encoding='utf-8', errors='strict')
    values = json.loads(reply.stdout) if reply.stdout.strip() else []
    if isinstance(values, dict): values = [values]
    blocked = [p for p in values if (p.get('Name') or '').lower().startswith('unrealeditor') or is_producer(p.get('CommandLine'))]
    require(not blocked, '真正父控制器/worker/数值准入/UE仍在，不按旧PID判断退出：'+canonical(blocked))
    return dict(producer_processes_absent=True, source='actual_CIM_Name_and_complete_script_basename',
                historical_PID_reuse_not_blocked=True)


def gt_contract(value, posthoc=None):
    require(value['source_validation_GT_registry_read'] is True and value['GT_annotations_loaded'] is True
            and value['GT_used_for_scoring'] is False and value['GT_free_inputs'] is True,
            '来源验证确实读endpoint_GT，不能误报未载GT或默许评分使用GT')
    if posthoc is not None:
        require(value['posthoc_GT_labels_loaded'] is posthoc and value['current_source_posthoc_GT_loaded'] is posthoc,
                '来源registry与后验labels/GT加载范围未明确区分')


def expected_matrix(details):
    require(len(details) == 54 and len({d['job']['job_id'] for d in details}) == 54, '原完整54来源被筛选/重复')
    selected = {}
    for detail in details:
        job = detail['job']; require(job['kind'] == 'common_state', '原来源不是共同状态')
        old = job['original']
        if old['seed'] == 20261024 and old['pool'] == 'balanced':
            key = old['fold'], old['sequence']; require(key not in selected, '首seed平衡来源重复')
            selected[key] = detail
    order = [(fold, seq) for fold in FOLDS for seq in [next(s for s, f in OLD.items() if f == fold)]+list(EXTERNAL)]
    require(set(selected) == set(order), '固定9源范围不齐')
    jobs = []
    for key in order:
        source = selected[key]['job']
        for group in GROUPS:
            job = dict(source_job_id=source['job_id'], fold=key[0], seed=20261024, pool='balanced', sequence=key[1], group=group)
            job['job_id'] = hashlib.sha256(canonical(job).encode()).hexdigest()[:24]; jobs.append(job)
    return jobs, [selected[key] for key in order]


def f32(value): return struct.unpack('f', struct.pack('f', value))[0]


def assignment(value, n, m):
    matches, rows, columns = value['matches'], value['unmatched_rows'], value['unmatched_columns']
    require(all(isinstance(p, list) and len(p) == 2 and all(type(x) is int for x in p) for p in matches)
            and all(0 <= i < n and 0 <= j < m for i, j in matches)
            and all(type(i) is int and 0 <= i < n for i in rows)
            and all(type(j) is int and 0 <= j < m for j in columns), '分配索引越界/类型不符')
    used_r, used_c = {p[0] for p in matches}, {p[1] for p in matches}
    require(len(used_r) == len(used_c) == len(matches) and len(set(rows)) == len(rows)
            and len(set(columns)) == len(columns) and set(rows) | used_r == set(range(n))
            and set(columns) | used_c == set(range(m)) and not set(rows) & used_r
            and not set(columns) & used_c, '分配/未匹配完整分母丢失')


def event_scope(event):
    n, m = len(event['history_UIDs']), len(event['candidate_UIDs'])
    require(n > 0 and m > 0 and event['GT_read'] is False and event['stage'] in (0, 1), '原trace事件范围/GT边界不符')
    locations = [[i, j] for i in range(n) if event['enough_history'][i]
                 for j in range(m) if event['motion_gate'][i][j]]
    require(event['scored_locations'] == locations, '原all-gated位置顺序不同')
    native = [p for p in locations if event['enabled'][p[0]][p[1]]]
    return n, m, locations, native


def score_contract(scored, event, locations, n, m):
    require(scored['locations'] == locations and scored['full_forward_equal_original_q'] is True
            and re.fullmatch('[0-9a-f]{64}', scored['input_195_sha256']) is not None
            and set(scored['logits']) == set(scored['decisions']) == set(BRANCHES), '两批评分位置/分支/输入身份不同')
    for name in ('base', 'raw_head', 'residual', 'q', 'gated_residual'):
        require(len(scored[name]) == len(locations)
                and all(type(v) in (float, int) and math.isfinite(v) and f32(v) == v for v in scored[name]),
                'FP32分支全量数组缺项/非有限')
    for k in range(len(locations)):
        b, delta, q, gated = (scored[name][k] for name in ('base', 'residual', 'q', 'gated_residual'))
        require(0 <= q <= 1 and abs(delta) <= .5 and gated == f32(q*delta)
                and abs(delta-.5*math.tanh(scored['raw_head'][k])) <= 2e-7,
                '原q/rawhead/有界残差拆解或FP32序列化不一致')
        require(scored['logits']['own_base'][k] == b
                and scored['logits']['original_q'][k] == f32(b+gated)
                and scored['logits']['q1'][k] == f32(b+delta), '分支logit不是自身base/原q/q1公式')
    threshold = .8 if event['stage'] == 0 else .7
    scored_at = {tuple(p): k for k, p in enumerate(locations)}
    for branch in BRANCHES:
        logits = scored['logits'][branch]; decision = scored['decisions'][branch]
        require(len(logits) == len(locations) and all(math.isfinite(v) and f32(v) == v for v in logits)
                and decision['threshold'] == threshold, '完整logit/原stage阈值不同')
        cost = decision['cost']
        require(len(cost) == n and all(len(r) == m for r in cost), '代价矩阵尺寸丢失')
        for i in range(n):
            for j in range(m):
                value = cost[i][j]
                require(math.isfinite(value) and f32(value) == value, '代价非有限/非FP32')
                if not event['active_rows'][i]:
                    require(value == f32(event['bbox_cost'][i][j]), '非active行原bbox代价被改动')
                elif not event['enabled'][i][j]:
                    require(value == 1., '非enabled active边不能填新代价')
                else:
                    require((i, j) in scored_at and 0 <= value <= 1., 'enabled代价无对应本批logit')
                    if logits[scored_at[i, j]] < 0: require(value == 1., '负logit不能通过原概率门槛')
        assignment(decision['assignment'], n, m)


class UnitTally:
    """只从完整保存行独立累计所有零/负/未知/未匹配，不调用生产者计数函数。"""
    def __init__(self):
        self.counts = Counter(); self.signatures = set(); self.maximum = {k: 0. for k in BRANCHES}
        self.transitions = {a+'_vs_'+b: {s: {x: {y: 0 for y in OUTCOMES} for x in OUTCOMES}
            for s in ('all_rows', 'trusted_current_GT_present')} for a, b in CONTRASTS}

    def add(self, record, source, job, event_number, calibration):
        require(record['job'] == job and record['source_event_number'] == event_number
                and record['original_state'] == {k: source[k] for k in ORIGINAL_FIELDS}
                and record['new_optimizer_updates'] == 0 and record['new_free_tracking'] is False
                and record['test_read'] is False
                and record['GT_used_only_for_source_validation_and_posthoc'] is True, '事件原状态/全部序号或预算改变')
        gt_contract(record, posthoc=True)
        expected_signature = hashlib.sha256(canonical([job['sequence'], source['frame_number'], source['stage'],
            source['history_UIDs'], source['candidate_UIDs']]).encode()).hexdigest()
        require(record['state_signature'] == expected_signature, '原状态签名改变')
        self.signatures.add(expected_signature)
        n, m, locations, native = event_scope(source); scored = record['new_T']
        require(scored['GT_used_for_scoring'] is False and scored['q1_is_mechanism_proxy'] is True
                and scored['fixed_state_native_cost_authority'] == 'direct_enabled_batch_new_T_counterfactual_not_recorded_new_T_free_tracking',
                '固定状态代理不能冒充新自由追踪或GT评分')
        score_contract(scored['all_gated'], source, locations, n, m)
        score_contract(scored['enabled_native'], source, native, n, m)
        reference = scored['reference']
        require(reference['recorded_actual_old_motion_cost'] == source['reference_cost']
                and reference['threshold'] == (.8 if source['stage'] == 0 else .7)
                and reference['origin'] == 'original_trace_recorded_actual_reference_cost_not_new_T_tracking', '原实际参考cost被替换')
        assignment(reference['assignment'], n, m)
        row_assignments = {k: dict(scored['enabled_native']['decisions'][k]['assignment']['matches']) for k in BRANCHES}
        all_indices = {tuple(p): k for k, p in enumerate(locations)}
        for branch in BRANCHES:
            a = scored['all_gated']['decisions'][branch]; b = scored['enabled_native']['decisions'][branch]
            maximum = max((f32(abs(x-y)) for ra, rb in zip(a['cost'], b['cost']) for x, y in zip(ra, rb)), default=0.)
            logit_delta = max((abs(scored['all_gated']['logits'][branch][all_indices[tuple(p)]]
                -scored['enabled_native']['logits'][branch][i]) for i, p in enumerate(native)), default=0.)
            comparison = scored['batch_numeric_comparison'][branch]
            require(comparison == dict(maximum_all_gated_vs_enabled_cost_delta=maximum,
                assignments_equal=a['assignment'] == b['assignment'], maximum_enabled_logit_delta=logit_delta), '两批差异账本不等于保存的实际数组')
            self.maximum[branch] = max(self.maximum[branch], maximum)
            self.counts[branch+'/all_gated_enabled_assignment_different_events'] += not comparison['assignments_equal']
        rows = record['posthoc_rows']
        require(len(rows) == n and [r['row_index'] for r in rows] == list(range(n)), '完整原stage行分母丢失/重复')
        c = self.counts; c['stage_events'] += 1; c['stage_rows'] += n
        c['all_gated_edges'] += len(locations); c['actual_enabled_edges'] += len(native)
        c['empty_scored_events'] += not locations
        for i, row in enumerate(rows):
            local = [j for a, j in locations if a == i]
            require(row['track_id'] == source['track_ids'][i] and row['active'] is bool(source['active_rows'][i])
                    and row['enough_history'] is bool(source['enough_history'][i])
                    and row['lost_gap'] is bool(source['lost_gap'][i]) and row['scored_pairs'] == len(local)
                    and row['scored_pairs'] == sum(row[k] for k in ('known_positive_scored_pairs', 'known_negative_scored_pairs', 'unknown_scored_pairs'))
                    and row['assignments'] == {k: row_assignments[k].get(i) for k in BRANCHES}
                    and set(row['outcomes']) == set(BRANCHES) and all(v in OUTCOMES for v in row['outcomes'].values()),
                    '原track/门禁/已知未知pair或完整分配行不一致')
            for name in BRANCHES:
                require((row['assignments'][name] is None) == (row['outcomes'][name] == 'unmatched'), '未匹配不能折叠为未知/错误')
            near = None
            if len(local) >= 2:
                positions = {tuple(p): k for k, p in enumerate(source['scored_locations'])}
                values = sorted((source['logits']['motion'][positions[i, j]] for j in local), reverse=True)
                near = values[0]-values[1] <= calibration['near_motion_gap']
            require(row['original_reference_near_motion'] is near, '近motion不是原冻结参考阈值/原logit')
            both = row['known_positive_scored_pairs'] > 0 and row['known_negative_scored_pairs'] > 0
            require(set(row['margins']) == set(BRANCHES) and all(
                (type(v) in (float, int) and math.isfinite(v)) if both else v is None for v in row['margins'].values()), '排名代理缺少原已知正负分母')
            c['history/'+row['history_status']] += 1; c['source_stop/'+row['source_stop']] += 1
            for name, value in (('trusted_current_GT_present_rows', row['trusted_current_GT_present']),
                ('active_rows', row['active']), ('unknown_scored_pairs', row['unknown_scored_pairs']),
                ('enough_history_rows', row['enough_history']), ('both_known_classes_rows', both),
                ('reference_near_motion_rows', near is True), ('active_both_known_rows', row['active'] and both),
                ('active_reference_near_both_known_rows', row['active'] and both and near is True),
                ('positive_quality_gate_all_zero_rows', row['diagnostic_quality_gate_all_positive_zero'] is True)):
                c[name] += value
            for target, base in CONTRASTS:
                key = target+'_vs_'+base
                for subset in ('all_rows', 'trusted_current_GT_present'):
                    if subset == 'all_rows' or row['trusted_current_GT_present']:
                        self.transitions[key][subset][row['outcomes'][base]][row['outcomes'][target]] += 1
                a, b = row['margins'][target], row['margins'][base]
                if a is not None:
                    c[key+'/ranking_corrects'] += a > 0 and b <= 0
                    c[key+'/ranking_breaks'] += a <= 0 and b > 0
                    c[key+'/ranking_tie_target'] += a == 0
                    for subset, enabled in (('active', row['active']), ('active_reference_near', row['active'] and near is True)):
                        if enabled:
                            c[key+'/'+subset+'_ranking_corrects'] += a > 0 and b <= 0
                            c[key+'/'+subset+'_ranking_breaks'] += a <= 0 and b > 0

    def summary(self, summary):
        require(dict(self.counts) == summary['counts'] and self.transitions == summary['transitions']
                and self.maximum == summary['maximum_all_gated_enabled_cost_delta']
                and len(self.signatures) == summary['unique_stage_state_signatures'], '完整事件计数/所有16格转移/负结果汇总不符')


class DigestReader:
    def __init__(self, stream): self.stream = stream; self.digest = hashlib.sha256()
    def read(self, size=-1):
        value = self.stream.read(size); self.digest.update(value); return value


@contextmanager
def jsonl_gzip(reference):
    path = physical(reference['path'])
    with path.open('rb') as raw:
        tracked = DigestReader(raw)
        with gzip.GzipFile(fileobj=tracked, mode='rb') as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8') as text:
                def rows():
                    for line in text:
                        require(bool(line.strip()), 'JSONL不能以空行省略事件')
                        yield json.loads(line)
                yield rows()
        require(tracked.digest.hexdigest() == reference['sha256'], '完整gzip来源SHA改变：'+str(path))


def verify_pair(source_detail, jobs, summaries, calibration):
    tallies = [UnitTally(), UnitTally()]; missing = object(); events = row_count = 0
    with ExitStack() as stack:
        streams = [stack.enter_context(jsonl_gzip(source_detail['trace']))]
        streams += [stack.enter_context(jsonl_gzip(s['events'])) for s in summaries]
        for number, values in enumerate(zip_longest(*streams, fillvalue=missing)):
            require(all(v is not missing for v in values), '原trace与两组完整事件数不一致，不许截短/重复')
            original = values[0]; events += 1; row_count += len(original['history_UIDs'])
            for tally, record, job in zip(tallies, values[1:], jobs): tally.add(record, original, job, number, calibration)
    require(events == source_detail['counts']['stage_calls'] and row_count == source_detail['counts']['all_stage_rows'],
            '新诊断分母不等于原trace与信息链实际分母')
    for tally, summary in zip(tallies, summaries): tally.summary(summary)
    return dict(source_job_id=source_detail['job']['job_id'], original_trace=source_detail['trace'],
        actual_source_events=events, actual_source_stage_rows=row_count,
        groups=[dict(job=job, stage_events=t.counts['stage_events'], stage_rows=t.counts['stage_rows'],
            all_gated_edges=t.counts['all_gated_edges'], enabled_edges=t.counts['actual_enabled_edges'],
            unique_state_signatures=len(t.signatures), counts=t.counts) for job, t in zip(jobs, tallies)])


def verify_workers(output, cfg, state, report, selected):
    workers, exits = state['workers'], state['worker_exits']
    require(workers == report['score_workers'] and exits == report['score_worker_exits'] and len(workers) == len(exits) == 2
            and [w['worker_index'] for w in workers] == [0, 1]
            and len({w['worker_pid'] for w in workers}) == 2, '真实两worker就绪/退出来源不一致')
    dispatched = state['dispatched_sources']; source_ids = [d['job']['job_id'] for d in selected]
    require([d['source_index'] for d in dispatched] == list(range(9))
            and [d['source_job_id'] for d in dispatched] == source_ids, '原9源派发顺序改变/重复重试')
    dispatch_worker = {d['source_index']: d['worker_index'] for d in dispatched}; results = {}; logs = []
    authorization = read(output/'score_worker_authorization.json')
    require(authorization['protocol'] == ref(Path(cfg['_config_path'])) and authorization['score_workers'] == 2
            and authorization['numeric_threads'] == 1 and authorization['output'] == str(output), '本次父子授权不同')
    for i, (worker, exit_) in enumerate(zip(workers, exits)):
        gt_contract(worker, posthoc=False)
        require(worker['status'] == 'worker_ready' and worker['numeric_threads'] == 1 and worker['CUDA_initialized'] is False
                and exit_['worker_index'] == i and exit_['exit_code'] == 0 and exit_['process_exited'] is True,
                '实际CPU线程/worker正常退出未闭合')
        protocol = output/'workers'/f'worker{i}.protocol.jsonl'
        messages = [json.loads(line) for line in physical(protocol).read_text(encoding='utf-8').splitlines() if line.strip()]
        require(messages[0] == worker and messages[-1]['status'] == 'worker_stopped'
                and messages[-1]['worker_index'] == i and messages[-1]['worker_pid'] == worker['worker_pid'], 'worker协议日志缺真实ready/stop')
        tail = [json.loads(line) for line in exit_['protocol_tail'].splitlines() if line.strip()]
        require(tail and tail[-1] == messages[-1], '退出记录不是实际stop协议尾')
        for message in messages[1:-1]:
            require(message['status'] == 'source_complete' and message['numeric_threads'] == 1
                    and message['worker_pid'] == worker['worker_pid'] and message['max_resident_source_sequences'] == 1
                    and message['new_optimizer_updates'] == 0 and message['new_free_tracking'] is False,
                    'worker源任务失败、进程/线程/单源边界不符')
            gt_contract(message, posthoc=True)
            index = message['source_index']; require(type(index) is int and index not in results and 0 <= index < 9
                and message['source_job_id'] == source_ids[index] and dispatch_worker[index] == i, 'worker源重复/重试/错误派发')
            expected = [j for j in cfg['matrix'] if j['source_job_id'] == source_ids[index]]
            require([u['job'] for u in message['units']] == expected, '两组实际模型收集顺序不同')
            for unit in message['units']:
                require(unit['summary'] == ref(output/'units'/unit['job']['job_id']/'summary.json'), 'worker源summary不是实际产物')
            results[index] = message
        paths = [protocol, output/'workers'/f'worker{i}.process.stderr.log',
                 output/'workers'/f'worker{i}.init.stdout.log', output/'workers'/f'worker{i}.init.stderr.log']
        logs.extend(ref(p) for p in paths)
    require(set(results) == set(range(9)) and report['all_worker_logs_closed'] is True
            and report['parent_exclusive_state_and_report'] is True, '九源全部日志/父进程独占关闭未齐')
    for index, source in enumerate(source_ids):
        for suffix in ('stdout.log', 'stderr.log'):
            logs.append(ref(output/'source_logs'/f'{index:02d}_{source}.{suffix}'))
    return logs


def execute(config, output, receipt):
    config, output, receipt = map(physical, (config, output, receipt))
    require(EXP in output.parents and EXP in receipt.parents and output not in receipt.parents,
            '终验新收据不能覆盖原诊断目录')
    intent, failed = receipt.with_suffix('.intent.json'), receipt.with_suffix('.failed.json')
    require(not any(p.exists() for p in (receipt, intent, failed)), '已有终验/partial，不覆盖或隐式重放')
    cfg = read(config); bundle = physical(cfg['bundle'])
    require(cfg['schema'] == 'pose_velocity_decision_probe_protocol_v1' and cfg['test_sealed'] is True
            and cfg['training_authorized'] is False and cfg['free_tracking_authorized'] is False,
            '独立零更新/测试封存准入缺失')
    source_files = read(checked(cfg['bundle_manifest']))['files']
    for item in source_files: require(sha(bundle/item['path']) == item['sha256'], '实际冻结执行源码变化')
    require(sha(bundle/'tools/research_ops/pose_velocity_decision_probe.py') == PROBE_SHA, '不是已核查稳定probe字节')
    state_ref, report_ref = ref(output/'state.json'), ref(output/'report.json')
    state, report = read(state_ref['path']), read(report_ref['path'])
    require(state['status'] == report['status'] == DONE and state['active'] == [] and state['finished_out_of_order'] == []
            and state['report'] == report_ref and state['protocol_sha256'] == sha(config)
            and report['protocol'] == ref(config), '实际父控制器18完整终态/有序收集未齐')
    absent_before = processes_absent()
    information = read(checked(cfg['source_information_report']))
    require(information['status'] == 'complete54_information_chain_zero_updates_not_new_tracking_or_training'
            and information['config'] == cfg['source_information_protocol'] and information['source_units'] == 54,
            '原完整54报告来源不同')
    expected, selected = expected_matrix(information['details'])
    require(cfg['matrix'] == expected and state['completed_units'] == [j['job_id'] for j in expected]
            and state['completed_sources'] == [d['job']['job_id'] for d in selected] and len(report['units']) == 18,
            '9trace×2矩阵不齐、重复或重排')
    require(report['parameters'] == cfg['parameters'] and report['new_optimizer_updates'] == 0
            and report['new_free_tracking'] is False and report['new_detector_or_Pose_inference'] is False
            and report['test_read'] is False and report['manual_keypoint_GT_complete'] is False
            and report['manual_quality_policy'] == 'optional120_manual_quality_not_adopted_labels_unavailable'
            and report['manual_keypoint_GT_required_for_execution'] is False
            and report['GT_free_inputs'] is True and report['GT_used_for_scoring'] is False
            and report['source_validation_GT_registry_read'] is True and report['GT_annotations_loaded'] is True
            and report['parent_posthoc_GT_labels_loaded'] is False, '预算/GT声明/可选人工范围不同')
    proof = read(checked(report['numeric_admission']))
    require(proof['status'] == 'complete_velocity_decision_probe_actual_CPU_numeric_admission'
            and proof['protocol_sha256'] == sha(config) and proof['probe_source_sha256'] == PROBE_SHA
            and proof['actual_optimizer_updates'] == 0 and proof['score2_actual_CPU_spawn_verified'] is True,
            '实际CPU数值/score2准入来源不同')
    gt_contract(proof, posthoc=False); gt_contract(proof['score2_numeric_admission'], posthoc=False)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    write_new(intent, dict(status='started_readonly18_decision_terminal_verification', config=ref(config),
        producer_report=report_ref, new_optimizer_updates=0, test_read=False))
    try:
        checked_units = []
        for job, unit_ref in zip(expected, report['units']):
            require(unit_ref == ref(output/'units'/job['job_id']/'summary.json'), '完整报告未绑定实际18summary')
            summary = read(checked(unit_ref)); gt_contract(summary, posthoc=True)
            require(summary['status'] == 'complete_new_T_fixed_state_probe_unit_not_free_tracking' and summary['job'] == job
                    and summary['diagnostic_event_limit'] is None and summary['numeric_threads'] == 1
                    and summary['new_optimizer_updates'] == 0 and summary['new_free_tracking'] is False
                    and summary['test_read'] is False and summary['events']['path'] == str(output/'units'/job['job_id']/'events.jsonl.gz'),
                    '正式unit被替换为小前缀/错误组或来源不符')
            model = next(m for m in cfg['model_runs'] if (m['fold'], m['group']) == (job['fold'], job['group']))
            training = read(checked(model['training_receipt']))
            require(summary['model_binding'] == training['binding'], 'unit不是登记新T最终模型身份')
            checked_units.append(summary)
        rows = []
        for i, source in enumerate(selected):
            summaries = checked_units[2*i:2*i+2]; jobs = expected[2*i:2*i+2]
            for summary in summaries:
                require(summary['trace'] == source['trace'] and summary['source_receipt'] == source['receipt']
                        and summary['calibration_source'] == cfg['source_information_report']
                        and summary['calibration_key'] == '/'.join((jobs[0]['fold'], '20261024', 'balanced')),
                        '实际trace/收据/原trainR校准来源不同')
            source_receipt = read(checked(source['receipt']))
            require(source_receipt['GT_read'] is False and source_receipt['trace'] == source['trace'], '原trace来源收据不符')
            calibration = information['calibrations'][summaries[0]['calibration_key']]
            require(calibration['fit_scope'] == 'allowed_base_train_R_only_no_labels_no_external', '原near参考阈值不应重新拟合')
            rows.append(verify_pair(source, jobs, summaries, calibration))
        logs = verify_workers(output, dict(cfg, _config_path=str(config)), state, report, selected)
        require(ref(output/'state.json') == state_ref and ref(output/'report.json') == report_ref, '终验期间父终态/报告发生变化')
        absent_after = processes_absent()
        totals = Counter()
        for source in rows:
            for unit in source['groups']: totals.update(unit['counts'])
        result = dict(schema='independent18_velocity_decision_terminal_verification_v1', status=STATUS,
            config=ref(config), producer_state=state_ref, producer_report=report_ref,
            verifier=ref(Path(__file__).resolve()), numeric_admission=report['numeric_admission'],
            actual_source_traces=9, actual_new_model_units=6, actual_scoring_units=18,
            actual_source_events=sum(r['actual_source_events'] for r in rows),
            actual_scored_events=totals['stage_events'], actual_stage_rows=totals['stage_rows'],
            all_event_counts=dict(totals), source_details=rows, unit_summaries=report['units'], worker_logs=logs,
            complete_original_trace_denominators_preserved=True, all16_transition_cells_unknown_unmatched_and_negatives_verified=True,
            GT_used_for_scoring=False, source_validation_GT_registry_read=True,
            posthoc_GT_labels_not_recomputed_by_verifier=True, producer_processes_absent=True,
            actual_exit_before=absent_before, actual_exit_after=absent_after,
            model_or_assignment_inference_rerun=False, TrackEval_rerun=False, new_optimizer_updates=0,
            new_free_tracking=False, test_read=False, manual_quality_not_adopted=True,
            interpretation='fixed-state first-seed observed-development mechanism proxy; no new AssA/free-policy gain or human-GT accuracy',
            numeric_serialization_check_not_performance_margin=True)
        write_new(receipt, result)
        return {k: result[k] for k in ('status', 'actual_source_traces', 'actual_scoring_units', 'actual_scored_events', 'actual_stage_rows')}
    except BaseException as error:
        write_new(failed, dict(status='failed_terminal_verification_sources_preserved_no_replay', error=repr(error),
            traceback=traceback.format_exc(), new_optimizer_updates=0, test_read=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'output', 'receipt'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); print(canonical(execute(args.config, args.output, args.receipt)))
