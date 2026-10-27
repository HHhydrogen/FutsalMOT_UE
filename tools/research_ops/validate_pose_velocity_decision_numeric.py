"""新T决策探针的真实CPU数值准入；默认只读，夹具不能签实际通过。"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import sys
import traceback

R = Path('D:/projects/FutsalMOT_Research')
STATUS = 'complete_velocity_decision_probe_actual_CPU_numeric_admission'
FIELDS = ('uid', 'bbox_xywh_px', 'score', 'xy_px', 'geometry_valid', 'timestamp_sec', 'image_wh')
SCORE_FIELDS = ('base', 'raw_head', 'residual', 'q', 'gated_residual', 'logits',
                'full_forward_equal_original_q', 'input_195_sha256')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def physical(value):
    import re
    import stat
    path = Path(os.path.abspath(value))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(
        r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts), '实际研究根/测试封存越界')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            v = part.lstat()
            require(not stat.S_ISLNK(v.st_mode) and not getattr(v, 'st_file_attributes', 0) & 0x400, '不跟随junction')
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(physical(path).read_bytes()).hexdigest()
def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(reference):
    path = physical(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '来源SHA改变：'+str(path))
    return path


def implementation_ref(function):
    """第三方数值源码只读绑定，可在现有venv中，不复制环境或读取测试数据。"""
    import stat
    path = Path(os.path.abspath(function.__code__.co_filename))
    require(path.suffix == '.py' and all(p.lower() != 'test' for p in path.parts), '原分配实现必须实际Python源码')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            v = part.lstat()
            require(not stat.S_ISLNK(v.st_mode) and not getattr(v, 'st_file_attributes', 0) & 0x400, '数值源码不跟随junction')
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def load_probe(config):
    cfg = read(config); bundle = physical(cfg['bundle'])
    require(bundle.parent == R/'code', '只加载实际冻结probe bundle')
    manifest = read(checked(cfg['bundle_manifest']))
    path = bundle/'tools/research_ops/pose_velocity_decision_probe.py'
    entry = next((e for e in manifest['files'] if e['path'] == 'tools/research_ops/pose_velocity_decision_probe.py'), None)
    require(entry is not None and sha(path) == entry['sha256'], 'probe源码未绑定或已改变')
    spec = importlib.util.spec_from_file_location('velocity_decision_actual_numeric_target', path)
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value; spec.loader.exec_module(value)
    return value


def manual_inputs(event, index, adapter):
    """独立于probe.build_inputs实现白名单与原行/候选顺序。"""
    locations, vectors = [], []
    for i, enough in enumerate(event['enough_history']):
        if not enough: continue
        for j, gated in enumerate(event['motion_gate'][i]):
            if not gated: continue
            history = [{k: deepcopy(index[uid][k]) for k in FIELDS} for uid in event['history_UIDs'][i]]
            candidate = {k: deepcopy(index[event['candidate_UIDs'][j]][k]) for k in FIELDS}
            require(len(history) == 3 and all(a['timestamp_sec'] < b['timestamp_sec'] for a, b in zip(history, history[1:]))
                    and history[-1]['timestamp_sec'] < candidate['timestamp_sec'], '只准原实际过去历史')
            locations.append((i, j)); vectors.append(list(adapter.transform_pair(history, candidate)))
    native = [p for p in locations if event['enabled'][p[0]][p[1]]]
    by = dict(zip(locations, vectors))
    return locations, vectors, native, [by[p] for p in native]


class PublicAdapter:
    """在实际adapter调用处拒绝任何身份/标签/GT字段。"""
    def __init__(self, source): self.source = source; self.calls = 0
    def transform_pair(self, history, candidate):
        require(all(set(r) == set(FIELDS) for r in history+[candidate]), '实际模型输入不是GT-free白名单')
        self.calls += 1
        return self.source.transform_pair(history, candidate)


def manual_scores(model, vectors, torch, branches):
    """按原二维forward直接拆解，不调用probe.branch_scores也不除q。"""
    result = dict(base=[], raw_head=[], residual=[], q=[], gated_residual=[], logits={k: [] for k in branches},
                  full_forward_equal_original_q=True, input_195_sha256=digest(vectors))
    if not vectors: return result
    require(getattr(model, 'variant', None) == 'gated' and hasattr(model, 'base') and hasattr(model, 'residual'),
            '实际模型必须是原base/residual双分支gated，不猜pose_head')
    x = torch.tensor(vectors, dtype=torch.float32, device='cpu')
    with torch.no_grad():
        motion = torch.cat((x[:, :24], torch.zeros_like(x[:, 24:194])), dim=1)
        base = model.base(motion); head = model.residual(x[:, 24:194])
        residual = .5*torch.tanh(head); q = x[:, 194:195]; gated = q*residual
        original = base+gated
        require(torch.equal(model(x), original), '手写原二维分支不等于完整forward')
        def values(v): return v.reshape(-1).tolist()
        result.update(base=values(base), raw_head=values(head), residual=values(residual), q=values(q),
                      gated_residual=values(gated), logits=dict(own_base=values(base), original_q=values(original), q1=values(base+residual)))
    return result


def compare_scores(expected, actual):
    require(set(expected) == set(actual) == set(SCORE_FIELDS), '完整分支字段缺失/增加')
    for key in SCORE_FIELDS:
        require(expected[key] == actual[key], '手写/探针分支逐值不一致：'+key)


def verify_q0(original, zero):
    require(zero['raw_head'] == original['raw_head'] and zero['residual'] == original['residual']
            and all(x == 0. for x in zero['q']) and all(x == 0. for x in zero['gated_residual'])
            and zero['logits']['original_q'] == zero['logits']['own_base'], 'q0丢失raw残差或除q反推')
    return dict(raw_residual_preserved=True, gate_override_numeric_boundary_not_observed_quality=True,
                nonzero_raw_residual_pairs=sum(x != 0. for x in zero['residual']))


def manual_decisions(event, locations, scores, geo, np, torch, assignment, branches):
    result = {}
    for branch in branches:
        view = dict(event, scored_locations=[list(p) for p in locations], logits=scores['logits'])
        cost, threshold = geo.choose_cost(view, branch, np, torch)
        matches, rows, columns = assignment(cost, thresh=threshold)
        result[branch] = dict(cost=cost.tolist(), threshold=threshold,
            assignment=dict(matches=[[int(i), int(j)] for i, j in matches], unmatched_rows=[int(i) for i in rows],
                            unmatched_columns=[int(j) for j in columns]))
    return result


def verify_event(probe, event, index, model, adapter, geo, np, torch, assignment):
    original_event = digest(event); guarded = PublicAdapter(adapter)
    expected_inputs = manual_inputs(event, index, guarded)
    actual_inputs = probe.build_inputs(event, index, guarded, geo.public)
    require(expected_inputs == actual_inputs, '两批实际白名单输入/评分顺序不同')
    observed = probe.score_event(event, index, model, guarded, geo, np, torch, assignment)
    for key, locations, vectors in (('all_gated', expected_inputs[0], expected_inputs[1]),
                                     ('enabled_native', expected_inputs[2], expected_inputs[3])):
        expected = manual_scores(model, vectors, torch, probe.BRANCHES)
        actual = {name: observed[key][name] for name in SCORE_FIELDS}
        compare_scores(expected, actual)
        decisions = manual_decisions(event, locations, expected, geo, np, torch, assignment, probe.BRANCHES)
        require(observed[key]['decisions'] == decisions, '原choose_cost/原linear_assignment不一致')
    reference = np.asarray(event['reference_cost'], dtype=np.float32)
    matches, rows, columns = assignment(reference, thresh=.8 if event['stage'] == 0 else .7)
    expected_reference = dict(matches=[[int(i), int(j)] for i, j in matches],
        unmatched_rows=[int(i) for i in rows], unmatched_columns=[int(j) for j in columns])
    require(observed['reference']['assignment'] == expected_reference and digest(event) == original_event
            and observed['GT_used_for_scoring'] is False, '原实际参考分配/只读事件或GT边界不同')
    return observed, dict(all_gated_pairs=len(expected_inputs[0]), enabled_pairs=len(expected_inputs[2]),
        public_adapter_calls=guarded.calls, full_forward_equal_original_q=True,
        all_gated_and_enabled_batches_separate=True, costs_and_assignments_equal=True,
        batch_numeric_comparison=observed['batch_numeric_comparison'], event_sha256=original_event)


def empty_boundary(event):
    empty = deepcopy(event)
    n, m = len(empty['history_UIDs']), len(empty['candidate_UIDs'])
    empty.update(enough_history=[False]*n, active_rows=[False]*n, scored_locations=[], enabled=[[False]*m for _ in range(n)])
    return empty


def model_state(model):
    value = hashlib.sha256()
    for key, tensor in sorted(model.state_dict().items()):
        value.update(canonical([key, str(tensor.dtype), list(tensor.shape)]).encode())
        value.update(tensor.detach().cpu().numpy().tobytes())
    return value.hexdigest()


def rng_state(np, torch):
    state = np.random.get_state()
    return dict(python=digest(random.getstate()), numpy=digest([state[0], state[1].tolist(), *state[2:]]),
                torch_CPU=hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest(),
                CUDA_initialized=torch.cuda.is_initialized())


def first_actual_state(probe, path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for number, line in enumerate(stream):
            event = json.loads(line); all_locations, native = probe.validate_event(event)
            if all_locations and native: return number, event
    raise ValueError('原实际trace没有同时非空all-gated/native状态，不能用夹具冒充准入')


def context_model_state(context):
    return {str(key): dict(model=model_state(model), adapter=digest(adapter.state()))
            for key, (model, adapter, _) in context.models.items()}


def verify_scoring_GT_metadata(result):
    """来源验证已解析旧GT账本；与后验标签加载及模型是否使用GT分别记账。"""
    require(result['source_validation_GT_registry_read'] is True and result['GT_annotations_loaded'] is True
            and result['posthoc_GT_labels_loaded'] is False and result['current_source_posthoc_GT_loaded'] is False
            and result['GT_used_for_scoring'] is False and result['GT_free_inputs'] is True
            and result['scored']['GT_used_for_scoring'] is False,
            'GT来源读取/后验加载/数值输入使用三个边界被混写')


def _spawn_score_entry(config_path, config_sha256, task, connection, start_event):
    """独立实际spawn入口只调用最终probe的数值worker API，不接GT/旧logit。"""
    try:
        os.environ.update(CUDA_VISIBLE_DEVICES='-1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                          OPENBLAS_NUM_THREADS='1', YOLO_AUTOINSTALL='false')
        require(sha(config_path) == config_sha256, 'spawn中的协议SHA改变')
        probe = load_probe(config_path)
        context = probe.initialize_score_worker(config_path, config_sha256)
        import numpy as np
        import torch
        connection.send(dict(status='ready', pid=os.getpid()))
        start_event.wait()
        warm = probe.score_worker_event(task['source_job_id'], task['event_number'], task['group'])
        before = context_model_state(context); before_rng = rng_state(np, torch)
        actual = probe.score_worker_event(task['source_job_id'], task['event_number'], task['group'])
        after = context_model_state(context); after_rng = rng_state(np, torch)
        require(before == after and before_rng == after_rng and not torch.cuda.is_initialized(),
                '实际score worker修改模型/adapter/RNG或初始化CUDA')
        verify_scoring_GT_metadata(warm); verify_scoring_GT_metadata(actual)
        require(warm['scored'] == actual['scored'] and actual['CUDA_initialized'] is False and actual['numeric_threads'] == 1,
                '实际score worker冷热不一致、初始化CUDA或使用非固定线程')
        connection.send(dict(status='complete', result=actual, pid=os.getpid(),
            parameters_buffers_adapters_unchanged=True, RNG_unchanged=True, CUDA_initialized=False,
            source_validation_GT_registry_read=True, GT_annotations_loaded=True,
            posthoc_GT_labels_loaded=False, current_source_posthoc_GT_loaded=False,
            GT_used_for_scoring=False, GT_free_inputs=True, cold_warm_scored_equal=True,
            source=ref(probe.__file__), actual_score_calls=2))
    except BaseException:
        connection.send(dict(status='failed_preserved_no_replay', pid=os.getpid(), traceback=traceback.format_exc()))
    finally:
        connection.close()


def verify_spawn_messages(messages, serial, task, parent_pid):
    require(len(messages) == 2 and len({m.get('pid') for m in messages}) == 2
            and all(m.get('pid') != parent_pid for m in messages), '必须两个真实独立spawn worker而非串行夹具')
    for message in messages:
        require(message.get('status') == 'complete', '实际score2 worker失败：'+str(message))
        result = message['result']
        verify_scoring_GT_metadata(result)
        require(all(result[k] == task[k] for k in ('source_job_id', 'event_number', 'group'))
                and result['scored'] == serial
                and result['CUDA_initialized'] is False and result['numeric_threads'] == 1,
                'serial/score2实际输入SHA、分支、代价或分配不逐值相同')
        require(message['parameters_buffers_adapters_unchanged'] is True and message['RNG_unchanged'] is True
                and message['cold_warm_scored_equal'] is True, '常驻worker状态未证不变')


def spawn_admission(config, config_sha256, task, serial):
    context = mp.get_context('spawn'); processes = []; parents = []; messages = []; ready = []
    start_event = context.Event()
    try:
        for _ in range(2):
            parent, child = context.Pipe(duplex=False)
            process = context.Process(target=_spawn_score_entry, args=(str(config), config_sha256, task, child, start_event))
            process.start(); child.close(); processes.append(process); parents.append(parent)
        for pipe in parents:
            try: ready.append(pipe.recv())
            except EOFError: ready.append(dict(status='failed_initialization_EOF_no_replay'))
        start_event.set()
        # 先接收全部回执再检查；一侧失败也让另一侧正常落盘/退出，不遗留阻塞send。
        for pipe, initialized in zip(parents, ready):
            if initialized.get('status') != 'ready': messages.append(initialized)
            else:
                try: messages.append(pipe.recv())
                except EOFError: messages.append(dict(status='failed_worker_EOF_no_replay'))
    finally:
        start_event.set()
        for pipe in parents: pipe.close()
        for process in processes: process.join(timeout=30)
    require(len(processes) == 2 and all(not p.is_alive() and p.exitcode == 0 for p in processes),
            'score2实际worker未正常退出，不能签数值准入')
    verify_spawn_messages(messages, serial, task, os.getpid())
    return dict(status='complete_actual_serial_vs_two_spawn_score_workers_exact', task=task,
        worker_pids=[p.pid for p in processes], workers_exited=True, numeric_threads=1,
        both_workers_ready_before_scoring=True,
        actual_diagnostic_score_calls=4, input_branch_cost_assignment_equal=True,
        workers=[{k: v for k, v in m.items() if k != 'result'} for m in messages],
        source_validation_GT_registry_read=True, GT_annotations_loaded=True,
        posthoc_GT_labels_loaded=False, current_source_posthoc_GT_loaded=False,
        GT_used_for_scoring=False, GT_free_inputs=True,
        CUDA_initialized=False, optimizer_updates=0)


def execute(config, output, config_sha256):
    config, output = physical(config), physical(output)
    require(config_sha256 is not None and sha(config) == config_sha256, '实际执行需显式新配置SHA')
    require(Path(__file__).resolve().parents[2].parent == R/'code', '实际准入只能执行安装后的独立SHA源码')
    probe = load_probe(config)
    cfg, _ = probe.plan(config, output.parent/'_numeric_plan_unused_target')
    require(output == physical(cfg['numeric_validation_receipt_path']) and not output.exists()
            and not output.with_suffix('.intent.json').exists() and not output.with_suffix('.failed.json').exists(),
            '必须新独占准入输出，partial不覆盖/重放')
    output.parent.mkdir(parents=True, exist_ok=True)
    intent = output.with_suffix('.intent.json'); failed = output.with_suffix('.failed.json')
    with intent.open('x', encoding='utf-8') as stream:
        stream.write(canonical(dict(status='started_actual_CPU_numeric_admission_not_complete', protocol=ref(config),
                                   validator=ref(__file__), optimizer_updates=0, test_read=False))+'\n')
    try:
        import numpy as np
        import torch
        from ultralytics.trackers.utils.matching import linear_assignment
        torch.set_num_threads(1)
        require(not torch.cuda.is_initialized(), 'CPU准入不准初始化CUDA')
        _, _, geo, core, dep, prepared, control, source_jobs, report, learning = probe.validate_config(config)
        sources = probe.selected_sources(source_jobs); detail_by_id = {x['job']['job_id']: x for x in report['details']}
        model_sources = {(x['fold'], x['group']): x for x in cfg['model_runs']}
        models = {}; baselines = {}; units = []; trace_refs = []; q0_done = set(); empty_done = False
        spawn_task = spawn_serial = None
        # 构建模型只用新完整load_model身份；评分前快照包含所有参数/buffers/adapter。
        for key, source in model_sources.items():
            _, _, model, adapter, binding = learning.complete_model(checked(cfg['learning_protocol']), source['run'])
            require(all(binding[k] == source[k] for k in ('fold', 'seed', 'group')), '真实新模型身份不同')
            model.eval(); models[key] = model, adapter, binding
            baselines[key] = dict(model=model_state(model), adapter=digest(adapter.state()))
        before_rng = rng_state(np, torch); require(before_rng['CUDA_initialized'] is False, '模型加载初始化了CUDA')
        for source_job in sources:
            o = source_job['original']; seq, fold = o['sequence'], o['fold']
            detail = detail_by_id[source_job['job_id']]; trace = checked(detail['trace'])
            source_frames = core.rows(checked(prepared['sources'][seq]['source']['cache']))
            index = {d['uid']: d for f in source_frames for d in f['detections']}
            require(len(index) == sum(len(f['detections']) for f in source_frames), '原预测UID重复')
            number, event = first_actual_state(probe, trace)
            trace_refs.append(dict(source_job=source_job, trace=detail['trace'], receipt=detail['receipt'],
                                   raw_cache=prepared['sources'][seq]['source']['cache'], chosen_event_number=number))
            for group in probe.GROUPS:
                key = fold, group; model, adapter, binding = models[key]
                observed, evidence = verify_event(probe, event, index, model, adapter, geo, np, torch, linear_assignment)
                if spawn_task is None:
                    spawn_task = dict(source_job_id=source_job['job_id'], event_number=number, group=group)
                    spawn_serial = deepcopy(observed)
                q0_proof = None
                if key not in q0_done:
                    vectors = probe.build_inputs(event, index, PublicAdapter(adapter), geo.public)[1]
                    zero = [row[:-1]+[0.] for row in vectors]
                    expected = manual_scores(model, zero, torch, probe.BRANCHES)
                    actual = probe.branch_scores(model, zero, torch); compare_scores(expected, actual)
                    q0_proof = verify_q0(observed['all_gated'], actual)
                    q0_done.add(key)
                if not empty_done:
                    empty, _ = verify_event(probe, empty_boundary(event), {}, model, adapter, geo, np, torch, linear_assignment)
                    require(not empty['all_gated']['base'] and not empty['enabled_native']['base'], '空评分填回旧logit')
                    empty_done = True
                require(model_state(model) == baselines[key]['model'] and digest(adapter.state()) == baselines[key]['adapter'],
                        '实际评分修改参数/buffer/adapter')
                units.append(dict(fold=fold, group=group, sequence=seq, binding=binding,
                                  trace=detail['trace'], event_number=number, evidence=evidence, q0=q0_proof))
            del index, source_frames
        score2 = spawn_admission(config, config_sha256, spawn_task, spawn_serial)
        after_rng = rng_state(np, torch)
        require(before_rng == after_rng and not torch.cuda.is_initialized(), 'CPU评分改变RNG或初始化CUDA')
        require(len(units) == 18 and len(trace_refs) == 9 and len(models) == len(q0_done) == 6 and empty_done,
                '真实6模型/9trace/18状态双批路径及边界未齐')
        for key, (model, adapter, _) in models.items():
            require(model_state(model) == baselines[key]['model'] and digest(adapter.state()) == baselines[key]['adapter'], '终态权重发生改变')
        result = dict(schema='velocity_decision_actual_CPU_numeric_admission_v1', status=STATUS,
            verified_UTC=datetime.now(timezone.utc).isoformat(), protocol=ref(config), protocol_sha256=config_sha256,
            probe_source=ref(probe.__file__), probe_source_sha256=sha(probe.__file__), validator=ref(__file__),
            actual_models=cfg['model_runs'], actual_model_count=6, source_traces=trace_refs, actual_trace_count=9,
            actual_nonempty_model_trace_checks=18, units=units, full_forward_equal_original_q=True,
            all_gated_and_enabled_batches_separate=True, costs_use_original_choose_cost=True,
            original_assignment_function=implementation_ref(linear_assignment),
            original_choose_cost_source=ref(geo.__file__),
            source_validation_GT_registry_read=True, GT_annotations_loaded=True,
            posthoc_GT_labels_loaded=False, current_source_posthoc_GT_loaded=False, GT_used_for_scoring=False,
            GT_free_inputs=True, q0_raw_residual_preserved=True, empty_scored_event_retained=True,
            parameters_buffers_adapters_unchanged=True, RNG_unchanged=True, RNG_before=before_rng, RNG_after=after_rng,
            CUDA_initialized=False, actual_optimizer_updates=0, new_free_tracking=False,
            score2_actual_CPU_spawn_verified=True, score2_numeric_admission=score2,
            new_detector_or_Pose_inference=False, test_read=False,
            limitations=['each batch compared with independent same-batch manual forward; all/native equality is not presumed',
                         'q0 and empty controls are numerical boundaries derived from actual inputs, not observed event statistics',
                         'source validation parsed the original endpoint_GT registry; scoring uses prediction-only public inputs',
                         'posthoc label/GT-file lookup is not called by this numeric scoring entry; loaded is not used'])
        with output.open('x', encoding='utf-8') as stream: stream.write(canonical(result)+'\n')
        return dict(status=STATUS, actual_models=6, source_traces=9, actual_checks=18, actual_optimizer_updates=0)
    except BaseException as error:
        with failed.open('x', encoding='utf-8') as stream:
            stream.write(canonical(dict(status='failed_actual_numeric_admission_preserved_no_replay', error=repr(error),
                traceback=traceback.format_exc(), protocol=ref(config), actual_optimizer_updates=0, test_read=False))+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'output'): parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--config-sha256'); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', YOLO_AUTOINSTALL='false')
    if args.execute: result = execute(args.config, args.output, args.config_sha256)
    else:
        probe = load_probe(args.config); cfg, _ = probe.plan(args.config, args.output.parent/'_numeric_plan_unused_target')
        result = dict(status='readonly_actual_CPU_numeric_admission_plan_no_model_loaded', actual_optimizer_updates=0,
            model_sources=len(cfg['model_runs']), trace_sources=9, output=str(args.output), test_read=False)
    print(canonical(result))
