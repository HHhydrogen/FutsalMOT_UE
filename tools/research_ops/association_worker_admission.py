"""独立小规模常驻worker准入：固定完整任务、原ID输出一致、真实端到端耗时。"""
import argparse
from collections import deque
from contextlib import redirect_stdout, redirect_stderr
import ctypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import sys
import threading
import time
import traceback

R = Path('D:/projects/FutsalMOT_Research')
BASE = R / 'performance/association_workers_a01'
SOURCE_SHA = 'ac89537c28668959729ea8d1930ca79c8f3ceff2da98c93bd54940467ebfd16d'


def require(ok, text):
    if not ok:
        raise ValueError(text)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def checked(value):
    p = Path(value['path'])
    require(sha(p) == value['sha256'], '固定来源SHA改变')
    return p


def physical(path, parent):
    p, parent = Path(path).absolute(), Path(parent).absolute()
    require(parent in p.parents, '输出必须在本次独立根下')
    for part in (p, *p.parents):
        if part.exists():
            require(not part.is_symlink() and not getattr(part.lstat(), 'st_file_attributes', 0) & 0x400,
                    '禁止junction或符号链接')
    return p


def write_new(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def load_source(source_ref):
    p = checked(source_ref)
    require(source_ref['sha256'] == SOURCE_SHA, '仅允许已闭合513的原协议')
    cfg = read(p)
    module_path = Path(cfg['bundle']) / 'tools/research_ops/pose_velocity_tracking_runtime.py'
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location('pose_velocity_tracking_runtime', module_path)
    rt = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = rt
    spec.loader.exec_module(rt)
    verified, dep, learning = rt.validate_config(p)
    require(verified == cfg, '原协议对象改变')
    return rt, cfg, dep, learning


class MetricWorker:
    """只有评价进程持有GT；数值直接调用原TrackEval及gap纯函数。"""
    def __init__(self, source_ref, output_root, worker_protocol_ref):
        started = time.perf_counter()
        self.rt, self.cfg, self.dep, _ = load_source(source_ref)
        self.source_ref = source_ref
        self.output_root = Path(output_root)
        self.protocol = worker_protocol_ref
        self.gt = {}
        self.registries = {}
        self.bindings = {}
        self.jobs = 0
        self.initialization_seconds = time.perf_counter() - started

    def run(self, job_id, tracking, output):
        started = time.perf_counter()
        rt, cfg, dep = self.rt, self.cfg, self.dep
        tracking = physical(tracking, self.output_root)
        output = physical(output, self.output_root)
        require(not output.exists(), '评价partial不覆盖或隐式重放')
        receipt = read(tracking / 'receipt.json')
        job = next(j for j in cfg['tracking_matrix'] if j['job_id'] == job_id)
        seq, source = job['sequence'], cfg['sources'][job['sequence']]
        require(receipt['job'] == job and receipt['cache'] == source['cache']
                and receipt['frames'] == source['frames'] and receipt['GT_used_for_tracking'] is False
                and receipt['evaluation_GT_annotations_loaded'] is False,
                '原任务/全部帧/追踪GT隔离不同')
        mot = tracking / 'data' / (seq + '.txt')
        require(sha(mot) == receipt['mot_sha256'], '实际MOT已改变')
        metric = dep[2]
        predictions, count = metric.prediction_rows(mot.read_text(encoding='utf-8'), source['frames'])
        require(count == receipt['tracked_rows'], '预测被丢弃或改写')
        if seq not in self.gt:
            _, values = rt.load_gt(cfg, dep, source)
            self.gt[seq] = values
            for key in ('gt', 'gt_reference', 'gameinfo'):
                if key in source:
                    self.bindings[str(checked(source[key]))] = source[key]['sha256']
        gt = self.gt[seq]
        output.mkdir(parents=True)
        raw, numeric_sha = metric.trackeval_numeric(source, gt, tracking, output)
        summary = {}
        for name, classes in raw.items():
            values = classes['pedestrian']
            metric.validate_count(name, values['Count'], count, len(gt), seq, source['frames'])
            fractions = {}
            for group, keys in [('HOTA', ('HOTA', 'AssA', 'DetA')), ('Identity', ('IDF1',)), ('CLEAR', ('MOTA',))]:
                for key in keys:
                    value = values[group][key]
                    fractions[key] = sum(value) / len(value) if isinstance(value, list) else float(value)
            summary[name] = dict(metrics_fraction=fractions,
                metrics_percent={key: 100 * value for key, value in fractions.items()},
                IDSW_count=int(values['CLEAR']['IDSW']))
        registry_ref = rt.registry_for_sequence(cfg, seq)['registry']
        if registry_ref['sha256'] not in self.registries:
            self.registries[registry_ref['sha256']] = read(checked(registry_ref))
            self.bindings[str(Path(registry_ref['path']))] = registry_ref['sha256']
        registry = self.registries[registry_ref['sha256']]
        require(registry['sources'] == {s: cfg['sources'][s] for s in registry['sources']}
                and registry['sequences'][seq]['cache'] == source['cache'], '原事件来源改变')
        events = [event for event in registry['events'] if event['sequence'] == seq]
        gap = rt.gap_numeric(cfg, dep)
        recovery = gap.evaluate_events(events, registry['sequences'][seq]['endpoint_GT'], predictions)
        require(recovery['overall']['total_events'] == len(events), '全事件分母被筛选')
        result = dict(schema='association_worker_admission_metric_v1', status='complete', job=job,
            source_tracking_protocol=self.source_ref, worker_protocol=self.protocol,
            origin='performance_admission_not_new_research_result', frames=source['frames'], summary=summary,
            raw_results=raw, recovery=recovery, registry=registry_ref, GT_rows=len(gt),
            tracking_receipt=ref(tracking / 'receipt.json'), DO_PREPROC=False, predictions_GT_filtered=False,
            GT_ID0_original=True, GT_used_only_for_metric=True, numerical_source_sha256=numeric_sha,
            optimizer_updates=0, test_read=False, metric_wall_seconds=time.perf_counter() - started)
        write_new(output / 'report.json', result)
        self.jobs += 1
        return dict(report=ref(output / 'report.json'), job_id=job_id)

    def close(self):
        for path, expected in self.bindings.items():
            require(sha(path) == expected, '评价缓存源在worker期间改变')
        require(sha(self.source_ref['path']) == self.source_ref['sha256'], '原协议改变')
        return dict(status='closed', jobs=self.jobs, GT_sequences_loaded=list(self.gt),
                    source_closure_verified=True, initialization_seconds=self.initialization_seconds,
                    GT_isolated_to_metric_worker=True, test_read=False)


def resource_snapshot():
    import psutil
    memory = psutil.virtual_memory()
    result = dict(available_RAM_bytes=memory.available, total_RAM_bytes=memory.total,
                  system_CPU_percent=psutil.cpu_percent())
    if os.name == 'nt':
        class Info(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong)] + [(name, ctypes.c_size_t) for name in (
                'CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable', 'SystemCache',
                'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize')] + [
                ('HandleCount', ctypes.c_ulong), ('ProcessCount', ctypes.c_ulong), ('ThreadCount', ctypes.c_ulong)]
        info = Info()
        info.cb = ctypes.sizeof(info)
        require(ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb), 'Windows commit读取失败')
        result.update(commit_available_bytes=(info.CommitLimit - info.CommitTotal) * info.PageSize,
                      committed_bytes=info.CommitTotal * info.PageSize, commit_limit_bytes=info.CommitLimit * info.PageSize)
    else:
        result['commit_available_bytes'] = memory.available
    return result


def enough_memory(snapshot, config, new_workers=0):
    return (snapshot['available_RAM_bytes'] >= config['reserve_RAM_bytes'] + new_workers * config['startup_estimate_bytes']
            and snapshot['commit_available_bytes'] >= config['reserve_commit_bytes'])


def validate_config(path):
    cfg = read(path)
    require(cfg.get('schema') == 'association_persistent_worker_admission_v1'
            and cfg.get('approved_by') == 'root' and cfg.get('execute_authorized') is True
            and cfg.get('diagnostic_only') is True and cfg.get('optimizer_updates') == 0
            and cfg.get('test_sealed') is True and Path(cfg['output_root']) == BASE,
            '独立小规模准入/输出/测试边界缺失')
    require(cfg['source_tracking_config']['sha256'] == SOURCE_SHA, '原来源协议不符')
    checked(cfg['source_tracking_config'])
    require(read(checked(cfg['source_complete_root']))['status'] ==
            'complete27_training513_tracking_all_paired_intervals_and_independent_exit_verified', '原513未闭合')
    bundle = Path(cfg['bundle'])
    manifest = read(checked(cfg['bundle_manifest']))
    require(bundle.parent == R / 'code' and Path(__file__).resolve() == bundle / 'tools/research_ops/association_worker_admission.py',
            '只允许独立SHA执行bundle')
    for value in manifest['files']:
        require(sha(bundle / value['path']) == value['sha256'], '新准入源码改变')
    source = read(cfg['source_tracking_config']['path'])
    require(len(cfg['tasks']) == 6 and len({j['job_id'] for j in cfg['tasks']}) == 6
            and all(j in source['tracking_matrix'] for j in cfg['tasks']), '必须固定六完整原任务')
    require(cfg['warm_job_order'] == [0, 2, 0] and cfg['profile_order'] == ['cold', 'pool21', 'pool21', 'cold'],
            '必须先冷及A→B→A、再固定同工作量ABBA')
    require(cfg['numeric_threads'] == 1 and cfg['track_workers'] == 2 and cfg['metric_workers'] == 1,
            '本轮仅固定2+1且每进程数值线程1')
    require(cfg['reserve_RAM_bytes'] >= 8 * 1024**3 and cfg['reserve_commit_bytes'] >= 6 * 1024**3,
            '必须保留物理/commit余量')
    return cfg


def worker_service(connection, kind, spec, log):
    try:
        started = time.perf_counter()
        os.environ.update(CUDA_VISIBLE_DEVICES='-1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        with Path(log).open('x', encoding='utf-8') as stream, redirect_stdout(stream), redirect_stderr(stream):
            if kind == 'track':
                from persistent_tracking_workers import PersistentTrackWorker
                worker = PersistentTrackWorker(spec['source_tracking_config'], spec['output_root'],
                    worker_protocol_ref=spec['worker_protocol_ref'],
                    frame_cache_bytes=spec['frame_cache_bytes'], model_cache_bytes=spec['model_cache_bytes'],
                    max_models=2)
            else:
                worker = MetricWorker(spec['source_tracking_config'], spec['output_root'], spec['worker_protocol_ref'])
            connection.send(dict(status='ready', pid=os.getpid(), initialization_seconds=time.perf_counter() - started))
            while True:
                task = connection.recv()
                if task['op'] == 'close':
                    connection.send(dict(status='closed', evidence=worker.close()))
                    break
                try:
                    if kind == 'track':
                        value = worker.run(task['job_id'], task['output'], worker_protocol_ref=spec['worker_protocol_ref'])
                    else:
                        value = worker.run(task['job_id'], task['tracking'], task['output'])
                    connection.send(dict(status='complete', value=value))
                except Exception:
                    traceback.print_exc()
                    connection.send(dict(status='failed', traceback=traceback.format_exc()))
                    break
    except Exception:
        try:
            connection.send(dict(status='failed', traceback=traceback.format_exc()))
        except (BrokenPipeError, EOFError):
            pass
    finally:
        connection.close()


class Service:
    def __init__(self, kind, spec, folder, number):
        self.kind = kind
        self.started = time.perf_counter()
        self.startup_evidence = None
        self.parent, child = mp.get_context('spawn').Pipe()
        self.process = mp.get_context('spawn').Process(target=worker_service,
            args=(child, kind, spec, str(folder / f'{kind}_{number}.log')))
        self.process.start()
        child.close()
        self.busy = None

    def receive(self):
        value = self.parent.recv()
        require(value['status'] != 'failed', value.get('traceback', 'worker失败'))
        if value['status'] == 'ready':
            self.startup_evidence = dict(value, launch_through_ready_seconds=time.perf_counter() - self.started)
        return value

    def close(self):
        started = time.perf_counter()
        if self.process.is_alive():
            self.parent.send(dict(op='close'))
            evidence = self.receive()
        else:
            raise RuntimeError('worker在明确close握手前退出，不能推测缓存闭包通过')
        self.process.join(timeout=30)
        require(not self.process.is_alive() and self.process.exitcode == 0, 'worker未正常退出，禁止强杀或自动重启')
        require(evidence['status'] == 'closed' and evidence['evidence']['status'] in
                ('closed', 'closed_worker_caches_verified'), '缓存或源码闭包核验失败，不能签正常完成')
        evidence.update(startup=self.startup_evidence, close_and_exit_seconds=time.perf_counter() - started,
                        actual_process_exited=True, exit_code=self.process.exitcode)
        self.parent.close()
        return evidence


def compare_track(path, original):
    a, b = read(Path(path) / 'receipt.json'), read(Path(original) / 'tracking/receipt.json')
    for key in ('job', 'frames', 'tracked_rows', 'frame_counts', 'mot_sha256', 'cache', 'binding', 'audit',
                'scope_adapter', 'input_adapter_audit', 'pose_enabled', 'inference_shape_shuffle', 'original_quality_gate'):
        require(a[key] == b[key], '冷/常驻原ID追踪不同：' + key)
    require((Path(path) / 'data' / (a['job']['sequence'] + '.txt')).read_bytes() ==
            (Path(original) / 'tracking/data' / (a['job']['sequence'] + '.txt')).read_bytes(), 'MOT原字节改变，禁止重编号掩盖')
    return dict(job_id=a['job']['job_id'], original_ID_MOT_equal=True, frame_counts_and_full_audit_equal=True)


def compare_metric(path, original):
    a, b = read(Path(path) / 'report.json'), read(Path(original) / 'metric/report.json')
    for key in ('job', 'frames', 'summary', 'raw_results', 'recovery', 'registry', 'GT_rows', 'DO_PREPROC',
                'predictions_GT_filtered', 'GT_ID0_original', 'numerical_source_sha256'):
        require(a[key] == b[key], '常驻评价/GT全分母不同：' + key)
    return dict(job_id=a['job']['job_id'], all_raw_metrics_counts_and_gap_equal=True)


class Monitor:
    def __init__(self, path):
        self.path = path
        self.stop = threading.Event()
        self.samples = []
        self.thread = threading.Thread(target=self.loop)

    def loop(self):
        import psutil
        root = psutil.Process()
        with self.path.open('x', encoding='utf-8') as stream:
            while not self.stop.is_set():
                value = resource_snapshot()
                processes = []
                for p in [root] + root.children(recursive=True):
                    try:
                        m = p.memory_info()
                        processes.append(dict(pid=p.pid, rss=m.rss, private=getattr(m, 'private', None)))
                    except psutil.Error:
                        pass
                value.update(utc=datetime.now(timezone.utc).isoformat(), processes=processes,
                             RSS_sum_bytes=sum(p['rss'] for p in processes))
                self.samples.append(value)
                stream.write(canonical(value) + '\n')
                stream.flush()
                self.stop.wait(1)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()


def run_profile(cfg, protocol_ref, folder, jobs, persistent, warm=False):
    folder.mkdir(parents=True)
    started = time.perf_counter()
    spec = dict(cfg, worker_protocol_ref=protocol_ref)
    services, closed, evidence = [], [], []
    # 原训练control与追踪control是并列目录，仅从已签完成根取实际追踪目录。
    original_root = Path(read(cfg['source_complete_root']['path'])['control_state']['path']).parent / 'runs'
    try:
        if not persistent:
            for i, job in enumerate(jobs):
                require(enough_memory(resource_snapshot(), cfg, 1), '资源门禁不足，未启动下一自有任务')
                track = Service('track', spec, folder, i)
                services.append(track)
                require(track.receive()['status'] == 'ready', 'track未就绪')
                out = folder / f'case_{i:02d}/tracking'
                track.parent.send(dict(op='track', job_id=job['job_id'], output=str(out)))
                require(track.receive()['status'] == 'complete', 'track未完成')
                evidence.append(compare_track(out, original_root / job['job_id']))
                closed.append(track.close()); services.remove(track)
                metric = Service('metric', spec, folder, i)
                services.append(metric)
                require(metric.receive()['status'] == 'ready', 'metric未就绪')
                mout = folder / f'case_{i:02d}/metric'
                metric.parent.send(dict(op='metric', job_id=job['job_id'], tracking=str(out), output=str(mout)))
                require(metric.receive()['status'] == 'complete', 'metric未完成')
                evidence.append(compare_metric(mout, original_root / job['job_id']))
                closed.append(metric.close()); services.remove(metric)
        else:
            ntrack, nmetric = (1, 1) if warm else (cfg['track_workers'], cfg['metric_workers'])
            require(enough_memory(resource_snapshot(), cfg, ntrack + nmetric), '资源不足，不启动常驻池')
            for kind, count in [('track', ntrack), ('metric', nmetric)]:
                for i in range(count):
                    service = Service(kind, spec, folder, i)
                    services.append(service)
            for service in services:
                require(service.receive()['status'] == 'ready', '常驻worker未就绪')
            pending = deque(enumerate(jobs)); metrics = deque(); finished = 0
            resource_wait_since = None
            while pending or metrics or any(s.busy for s in services):
                for service in services:
                    if service.busy:
                        continue
                    queue = pending if service.kind == 'track' else metrics
                    if not queue:
                        continue
                    if not enough_memory(resource_snapshot(), cfg):
                        resource_wait_since = resource_wait_since or time.perf_counter()
                        continue
                    resource_wait_since = None
                    i, job = queue.popleft()
                    task = dict(op=service.kind, job_id=job['job_id'],
                        output=str(folder / f'case_{i:02d}' / ('tracking' if service.kind == 'track' else 'metric')))
                    if service.kind == 'metric':
                        task['tracking'] = str(folder / f'case_{i:02d}/tracking')
                    service.parent.send(task)
                    service.busy = (i, job)
                    # warm先依序track A→B→A，再由独立metric依相同顺序评价。
                    if warm:
                        break
                busy = [s for s in services if s.busy]
                if not busy:
                    require(resource_wait_since is not None and time.perf_counter() - resource_wait_since < 60,
                            '资源余量等待60秒仍未恢复，保留现场，不隐式重放')
                    time.sleep(.2)
                    continue
                ready = wait([s.parent for s in busy], timeout=1)
                for service in busy:
                    if service.parent not in ready:
                        continue
                    message = service.receive()
                    require(message['status'] == 'complete', '常驻任务未完成')
                    i, job = service.busy
                    if service.kind == 'track':
                        evidence.append(compare_track(folder / f'case_{i:02d}/tracking', original_root / job['job_id']))
                        metrics.append((i, job))
                    else:
                        evidence.append(compare_metric(folder / f'case_{i:02d}/metric', original_root / job['job_id']))
                        finished += 1
                    service.busy = None
            require(finished == len(jobs), '相同工作量未完整评价')
            for service in services[:]:
                closed.append(service.close()); services.remove(service)
    finally:
        for service in services:
            try:
                if service.busy:
                    service.receive()
                    service.busy = None
                closed.append(service.close())
            except Exception:
                traceback.print_exc()
    result = dict(status='complete_same_work_and_exact_output', persistent=persistent, warm_order_gate=warm,
        job_ids=[j['job_id'] for j in jobs], jobs=len(jobs), wall_seconds=time.perf_counter() - started,
        source_equivalence=evidence, worker_close_evidence=closed, worker_processes_absent=True)
    write_new(folder / 'profile_complete.json', result)
    return result


def execute(config):
    cfg = validate_config(config)
    output = physical(cfg['output_root'], R / 'performance')
    require(not output.exists(), '已有准入或partial，先诊断，不覆盖')
    output.mkdir(parents=True)
    protocol_ref = ref(config)
    write_new(output / 'intent.json', dict(config=protocol_ref, status='started_small_performance_admission', test_read=False))
    with Monitor(output / 'hardware_samples.jsonl') as monitor:
        try:
            warm = run_profile(cfg, protocol_ref, output / 'warm_ABA_gate',
                               [cfg['tasks'][i] for i in cfg['warm_job_order']], True, True)
            profiles = [run_profile(cfg, protocol_ref, output / f'profile_{i}_{name}', cfg['tasks'], name != 'cold')
                        for i, name in enumerate(cfg['profile_order'])]
        except Exception:
            write_new(output / 'failed.json', dict(status='failed_preserved_no_implicit_replay', config=protocol_ref,
                traceback=traceback.format_exc(), optimizer_updates=0, test_read=False))
            raise
    cold = [p['wall_seconds'] for p in profiles if not p['persistent']]
    pool = [p['wall_seconds'] for p in profiles if p['persistent']]
    result = dict(status='complete_small_worker_equivalence_and_ABBA_throughput_admission', config=protocol_ref,
        complete_workload_jobs_per_profile=6, benchmark_profiles=4, diagnostic_warm_tasks=3,
        optimizer_updates=0, original_ID_MOT_full_audit_all_raw_metrics_and_gap_equal=True,
        cold_seconds=cold, pool21_seconds=pool, cold_mean_seconds=sum(cold) / 2,
        pool21_mean_seconds=sum(pool) / 2, observed_speedup=(sum(cold) / sum(pool)),
        adopted_profile='pool21' if sum(pool) < sum(cold) else 'cold_no_observed_speedup',
        peak_tree_RSS_bytes=max(s['RSS_sum_bytes'] for s in monitor.samples),
        sampled_peak_system_CPU_percent=max(s['system_CPU_percent'] for s in monitor.samples),
        minimum_available_RAM_bytes=min(s['available_RAM_bytes'] for s in monitor.samples),
        minimum_available_commit_bytes=min(s['commit_available_bytes'] for s in monitor.samples),
        hardware_samples=ref(output / 'hardware_samples.jsonl'),
        GPU_compute_used=False, own_GPU_allocations_bytes=0, test_read=False,
        source_scientific_results_modified=False, all_failures_retained=True,
        limits=['six fixed complete tasks; not513/full experiment acceleration',
                'same work persistent cache plus2track1metric compared to cold perjob processes',
                'ABBA reduces order effects; does not eliminate OS cache or clock effects',
                'system CPU/RAM includes other applications; process tree RSS is sampled not allocator profiler',
                '4+2 not executed; reassess actual memory and load before changing pool profile'])
    write_new(output / 'report.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    value = execute(args.config) if args.execute else dict(status='readonly_small_worker_plan', tasks=len(validate_config(args.config)['tasks']))
    print(canonical(value))
