"""固定官方OC-SORT缓存适配的独立短样数值与常驻进程准入；不评价性能收益。"""
import argparse
import builtins
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import stat
import sys
import time
import traceback

R = Path('D:/projects/FutsalMOT_Research')
SEQUENCES = ('SNMOT-060', 'SNMOT-097', 'SNMOT-151', 'v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004',
    'v_1yHWGw8DH4A_c029', 'v_HdiyOtliFiw_c003', 'v_ITo3sCnpw_k_c007', 'v_dw7LOz17Omg_c053',
    'v_gQNyhv8y0QY_c003', 'v_i2_L4qquVg0_c006', 'v_iIxMOsCGH58_c013')
PREFIXES = (('A', 'SNMOT-060', 48), ('B', 'v_2QhNRucNC7E_c017', 48))
FRAME_KEYS = ('sequence', 'width', 'height', 'fps', 'frame_index', 'frame_number', 'timestamp_sec')
PARAMETERS = dict(source_prefixes=[dict(key=k, sequence=s, frames=n) for k, s, n in PREFIXES],
    unique_source_frames=96, numeric_threads=1, persistent_order=['A', 'B', 'A'], spawn_workers=2,
    input_dtype='float32', Kalman_internal_dtype='float64_original_not_recast',
    TrackEval_runs=0, optimizer_updates=0, new_detector_or_Pose_inference=False,
    output_comparison='exact_original_ID_MOT_frame_counts_and_per_frame_raw_outputs',
    fixture='empty_strict_threshold_crossing_missing_ambiguous_solver_and_GT_Pose_pollution',
    performance_speedup_claim=False, test_sealed=True)


def require(ok, text):
    if not ok:
        raise ValueError(text)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def physical(path, *, research=True):
    p = Path(path)
    require(p.is_absolute(), '固定来源和输出必须绝对路径')
    p = Path(os.path.abspath(p))
    require(not research or R in p.parents, '只允许实际DResearch独立来源/输出')
    require(not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
                    for part in p.parts), '最终测试继续封存')
    for item in (p, *p.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '不跟随junction或符号链接')
    return p


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def checked(value):
    p = physical(value['path'])
    require(p.is_file() and sha(p) == value['sha256'], '固定来源SHA改变：' + str(p))
    return p


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def load_runtime(runtime_ref):
    path = checked(runtime_ref)
    name = '_ocsort_admission_runtime_' + runtime_ref['sha256']
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous
    return sys.modules[name]


def validate_config(path):
    path = physical(path)
    cfg = read(path)
    require(cfg['schema'] == 'official_ocsort_cached_admission_config_v1'
            and cfg['approved_by'] == 'root' and cfg['diagnostic_authorized'] is True
            and cfg['test_sealed'] is True, '需要独立root冻结准入，不能代替正式十二场协议')
    require(set(cfg['sources']) == set(SEQUENCES), '原十二开发片段必须完整且不含测试')
    require(cfg['admission_parameters'] == PARAMETERS, '准入范围/数值线程/矩阵改变')
    runtime = load_runtime(cfg['runtime'])
    require(cfg['parameters'] == runtime.PARAMETERS, '必须事前固定原生OC-SORT参数')
    runtime.inspect_source_contract(cfg['official_manifest'])
    checked(cfg['dependency_manifest'])
    require(isinstance(cfg['protected_GT_paths'], list) and cfg['protected_GT_paths'], '必须明确GT物理保护范围')
    for protected in cfg['protected_GT_paths']:
        physical(protected)
    for _, sequence, count in PREFIXES:
        source = cfg['sources'][sequence]
        require(source['frames'] >= count and source['cache']['sha256'], '固定来源不足48帧或未绑定')
        physical(source['cache']['path'])
    if 'admission_source' in cfg:
        require(checked(cfg['admission_source']) == Path(__file__).resolve(), '执行入口不是冻结准入源码')
    return cfg, runtime


def public_frame(frame):
    """预测JSONL可含Pose；原core实际输入只来自此白名单，无后验标签。"""
    result = {key: deepcopy(frame[key]) for key in FRAME_KEYS}
    result['detections'] = [dict(bbox_xywh_px=deepcopy(det['bbox_xywh_px']), score=det['score'])
                            for det in frame['detections']]
    return result


def prefix_frames(source, sequence, count):
    path = checked(source['cache'])
    result = []
    with path.open('r', encoding='utf-8-sig') as stream:
        for index in range(count):
            line = stream.readline()
            require(bool(line.strip()), '冻结预测缓存短读或空行')
            value = json.loads(line)
            require(value['sequence'] == sequence and value['frame_index'] == index
                    and value['frame_number'] == index + 1, '源帧映射改变')
            result.append(public_frame(value))
    return result


class GTReadBlocked(PermissionError):
    pass


class GTGuard:
    """实证禁止Python open接触GT；保护自检的拒绝尝试与实际算法分开记。"""
    def __init__(self, protected):
        self.protected = {os.path.normcase(os.path.abspath(p)) for p in protected}
        self.denied = []
        self.allowed_reads = 0
        self.self_checks = 0

    def check(self, path, mode='r'):
        if isinstance(path, int):
            return
        try:
            value = os.path.normcase(os.path.abspath(os.fspath(path)))
        except TypeError:
            return
        name = Path(value).name.lower()
        blocked = value in self.protected or name in ('gt.txt', 'gameinfo.ini', 'gap_registry.json')
        if blocked:
            self.denied.append(value)
            raise GTReadBlocked('准入追踪进程禁止打开GT/endpoint账本：' + value)
        self.allowed_reads += 1

    @contextmanager
    def active(self):
        original = builtins.open, io.open, os.open, Path.open
        def builtin_open(path, *args, **kwargs):
            self.check(path, args[0] if args else kwargs.get('mode', 'r'))
            return original[0](path, *args, **kwargs)
        def io_open(path, *args, **kwargs):
            self.check(path, args[0] if args else kwargs.get('mode', 'r'))
            return original[1](path, *args, **kwargs)
        def os_open(path, *args, **kwargs):
            self.check(path)
            return original[2](path, *args, **kwargs)
        def path_open(path, *args, **kwargs):
            # Python3.10的pathlib._accessor缓存了原io.open；只改io.open拦不住Path.read_bytes。
            self.check(path, args[0] if args else kwargs.get('mode', 'r'))
            return original[3](path, *args, **kwargs)
        builtins.open, io.open, os.open = builtin_open, io_open, os_open
        Path.open = path_open
        try:
            yield self
        finally:
            builtins.open, io.open, os.open, Path.open = original

    def prove_blocked(self):
        require(self.protected, '保护范围不能为空')
        for opener in (builtins.open, io.open, os.open):
            try:
                if opener is os.open:
                    opener(next(iter(self.protected)), os.O_RDONLY)
                else:
                    opener(next(iter(self.protected)), 'rb')
            except GTReadBlocked:
                self.self_checks += 1
            else:
                raise ValueError('Python GT open保护未生效')

    def evidence(self):
        require(len(self.denied) == self.self_checks, '实际追踪曾尝试打开GT，不能声明未读')
        return dict(GT_Python_open_guard=True, self_test_blocked_opens=self.self_checks,
            algorithm_blocked_GT_opens=len(self.denied)-self.self_checks, algorithm_GT_read=False,
            protected_paths=len(self.protected), allowed_Python_opens=self.allowed_reads,
            limitation='Python_open_guard_not_OS_sandbox; cache_JSONL_may_parse_Pose_then_explicit_whitelist')


def configure_threads():
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'


@contextmanager
def numeric_threads():
    configure_threads()
    from threadpoolctl import threadpool_limits, threadpool_info
    with threadpool_limits(limits=1):
        pools = threadpool_info()
        require(all(pool['num_threads'] == 1 for pool in pools), '实际数值后端线程未受控')
        yield pools


def literal_reference(frames, official, parameters):
    """不调用runtime适配函数：从原字段逐帧直译官方N5接口及原ID输出。"""
    np = official.np
    tracker = official.OCSort(**deepcopy(parameters))
    require(tracker.frame_count == 0 and official.KalmanBoxTracker.count == 0, 'literal新序列ID未归零')
    lines, counts, arrays = [], [], []
    dtypes = set()
    for index, frame in enumerate(frames):
        rows = []
        for detection in frame['detections']:
            x, y, width, height = detection['bbox_xywh_px']
            rows.append([x, y, x + width, y + height, detection['score']])
        values = np.array(rows, dtype=np.float32).reshape((-1, 5))
        shape = (frame['height'], frame['width'])
        output = tracker.update(values, shape, shape)
        require(tracker.frame_count == index + 1, 'literal空帧未推进')
        arrays.append(output.tolist())
        counts.append(len(output))
        for track in tracker.trackers:
            dtypes.update(str(getattr(track.kf, field).dtype) for field in ('F', 'H', 'P', 'Q', 'R', 'x'))
        for row in output:
            x1, y1, x2, y2, identity = map(float, row)
            lines.append(','.join(map(str, [index + 1, int(identity), x1, y1, x2-x1, y2-y1, 1, -1, -1, -1])))
    require(dtypes == {'float64'}, '官方Kalman内部dtype被改变或夹具没有创建轨迹')
    return dict(mot_text='\n'.join(lines)+('\n' if lines else ''), frame_counts=counts, raw_outputs=arrays,
                frames=len(counts), tracked_rows=len(lines), Kalman_dtypes=sorted(dtypes))


def compare_outputs(actual, reference):
    for key in ('mot_text', 'frame_counts', 'raw_outputs', 'frames', 'tracked_rows'):
        require(canonical(actual[key]) == canonical(reference[key]), '数值/原ID输出不同：' + key)
    require(len(actual['raw_outputs']) == actual['frames'] and len(actual['frame_counts']) == actual['frames']
            and sum(actual['frame_counts']) == actual['tracked_rows'], '完整原帧/输出数不一致')
    return dict(original_ID_MOT_equal=True, all_frame_counts_equal=True, per_frame_raw_outputs_exact=True,
                frames=actual['frames'], tracked_rows=actual['tracked_rows'],
                mot_sha256=hashlib.sha256(actual['mot_text'].encode()).hexdigest(),
                raw_outputs_sha256=hashlib.sha256(canonical(actual['raw_outputs']).encode()).hexdigest())


def synthetic_frames():
    result = []
    for index in range(16):
        if index in (3, 4, 10):
            rows = []
        else:
            rows = [([10 + index*2, 10, 20, 40], .9), ([50 - index*2, 10, 20, 40], .85)]
        if index == 0:
            rows += [([100, 10, 20, 40], .6), ([130, 10, 20, 40], .2), ([160, 10, 20, 40], .6001)]
        result.append(dict(sequence='artificial_contract_fixture', width=400, height=240, fps=25,
            frame_index=index, frame_number=index+1, timestamp_sec=index/25,
            detections=[dict(bbox_xywh_px=box, score=score, GT_identity='must_not_be_read',
                             xy_px={'invalid': 'Pose_pollution'}, geometry_valid='must_not_be_read')
                        for box, score in rows], endpoint_GT='must_not_be_read'))
    return result


def artificial_gate(runtime, official, parameters):
    frames = synthetic_frames()
    original = canonical(frames)
    clean = [public_frame(f) for f in frames]
    literal = literal_reference(clean, official, parameters)
    actual = runtime.track_frames(clean, official, parameters)
    comparison = compare_outputs(actual, literal)
    require(canonical(frames) == original and actual['audit']['empty_input_frames'] == 3, '空帧/污染来源被改变')
    high = [row for row in literal['raw_outputs'][0] if row[0] >= 90]
    require(len(high) == 1 and high[0][0] == 160, 'strict .6/low/high边界改变')
    import lap
    old, calls = lap.lapjv, []
    def counted(*args, **kwargs):
        calls.append(True)
        return old(*args, **kwargs)
    lap.lapjv = counted
    try:
        assignment = official.module.linear_assignment(official.np.array([[0., 0.], [0., 0.]]))
    finally:
        lap.lapjv = old
    require(calls and assignment.shape == (2, 2), '必须实际触发已固定lap歧义分配后端，不能只走唯一IoU快路')
    return dict(comparison=comparison, empty_frames=3, score_equal_threshold_excluded=True,
        low_score_excluded_without_byte=True, high_score_passed=True, crossing_and_missing_frames=True,
        lap_ambiguous_solver_actual_calls=len(calls), GT_Pose_pollution_whitelist_only=True,
        source_fixture_unchanged=True, Kalman_internal_dtypes=literal['Kalman_dtypes'])


def resident_worker(connection, cfg, log_prefix):
    """每进程一次加载官方模块；每job才新建一个tracker，不同时交错多个实例。"""
    configure_threads()
    stdout = Path(log_prefix + '.stdout.log')
    stderr = Path(log_prefix + '.stderr.log')
    guard = GTGuard(cfg['protected_GT_paths'])
    try:
        with stdout.open('x', encoding='utf-8') as out, stderr.open('x', encoding='utf-8') as err:
            with redirect_stdout(out), redirect_stderr(err), guard.active():
                guard.prove_blocked()
                runtime = load_runtime(cfg['runtime'])
                official = runtime.load_official(cfg['official_manifest'])
                with numeric_threads() as pools:
                    connection.send(dict(kind='ready', pid=os.getpid(), numeric_pools=pools))
                    jobs = []
                    while True:
                        request = connection.recv()
                        if request['kind'] == 'close':
                            connection.send(dict(kind='closed', pid=os.getpid(), jobs=jobs,
                                                 GT_guard=guard.evidence(), active_trackers=0))
                            return
                        require(request['kind'] == 'track', '未知准入worker请求')
                        before = canonical(request['frames'])
                        result = runtime.track_frames(request['frames'], official, cfg['parameters'],
                                                      input_reference=request['input_reference'])
                        require(before == canonical(request['frames']), '常驻worker原输入被修改')
                        jobs.append(request['job'])
                        connection.send(dict(kind='result', job=request['job'], pid=os.getpid(), payload=result,
                            source_input_unchanged=True, GT_guard=guard.evidence()))
    except BaseException:
        error = traceback.format_exc()
        try:
            connection.send(dict(kind='failed', pid=os.getpid(), traceback=error))
        except (BrokenPipeError, EOFError, OSError):
            pass
        try:
            with stderr.open('a', encoding='utf-8') as stream:
                stream.write(error)
        except OSError:
            pass
        raise
    finally:
        connection.close()


def receive(connection, kind, timeout=180.):
    require(connection.poll(timeout), '准入worker超时；保留partial，不自动重试')
    value = connection.recv()
    require(value.get('kind') == kind, '准入worker失败/协议不同：' + canonical(value))
    return value


def start_worker(cfg, output, name):
    context = mp.get_context('spawn')
    parent, child = context.Pipe(duplex=True)
    process = context.Process(target=resident_worker, args=(child, cfg, str(output/name)), name=name)
    process.start()
    child.close()
    try:
        ready = receive(parent, 'ready')
        require(ready['pid'] == process.pid, 'worker ready不是实际spawn PID')
        return dict(process=process, connection=parent, ready=ready)
    except BaseException:
        if process.is_alive():
            try:
                parent.send(dict(kind='close'))
            except (BrokenPipeError, EOFError, OSError):
                pass
        process.join(30.)
        parent.close()
        raise


def close_worker(worker):
    connection, process = worker['connection'], worker['process']
    connection.send(dict(kind='close'))
    closure = receive(connection, 'closed')
    process.join(30.)
    require(not process.is_alive() and process.exitcode == 0 and closure['pid'] == process.pid,
            '准入worker没有真实close/join/exit0')
    connection.close()
    return dict(**closure, exitcode=process.exitcode, joined=True, actual_PID_absent_after_join=True)


def execute(cfg, runtime, output, config_ref):
    output = physical(output)
    require(not output.exists(), '未知partial/成功准入目录拒绝覆盖或隐式重放')
    output.mkdir(parents=True)
    started = time.perf_counter()
    write_new(output/'started.json', dict(status='started_not_committed', config=config_ref, pid=os.getpid(),
        parameters=PARAMETERS, test_sealed=True, timestamp=datetime.now(timezone.utc).isoformat()))
    workers = []
    try:
        frames = {key: prefix_frames(cfg['sources'][sequence], sequence, count) for key, sequence, count in PREFIXES}
        originals = {key: canonical(value) for key, value in frames.items()}
        guard = GTGuard(cfg['protected_GT_paths'])
        with guard.active():
            guard.prove_blocked()
            official = runtime.load_official(cfg['official_manifest'])
            with numeric_threads() as pools:
                references = {key: literal_reference(value, official, cfg['parameters']) for key, value in frames.items()}
                comparisons = {key: compare_outputs(runtime.track_frames(value, official, cfg['parameters']), references[key])
                               for key, value in frames.items()}
                fixture = artificial_gate(runtime, official, cfg['parameters'])
        permanent = start_worker(cfg, output, 'persistent_ABA')
        workers.append(permanent)
        aba = []
        for ordinal, key in enumerate(('A', 'B', 'A')):
            sequence = next(seq for k, seq, _ in PREFIXES if k == key)
            permanent['connection'].send(dict(kind='track', job=str(ordinal)+key, frames=frames[key],
                input_reference=cfg['sources'][sequence]['cache']))
            reply = receive(permanent['connection'], 'result')
            aba.append(dict(job=reply['job'], comparison=compare_outputs(reply['payload'], references[key]),
                            source_input_unchanged=reply['source_input_unchanged']))
        permanent_close = close_worker(permanent)
        parallel = [start_worker(cfg, output, 'spawn_A_'+str(index)) for index in range(2)]
        workers.extend(parallel)
        for index, worker in enumerate(parallel):
            worker['connection'].send(dict(kind='track', job='spawn_A_'+str(index), frames=frames['A'],
                input_reference=cfg['sources']['SNMOT-060']['cache']))
        spawn_results = []
        for worker in parallel:
            reply = receive(worker['connection'], 'result')
            comparison = compare_outputs(reply['payload'], references['A'])
            spawn_results.append(dict(comparison=comparison, closure=close_worker(worker),
                                      source_input_unchanged=reply['source_input_unchanged']))
        require(len({permanent_close['pid'], *[v['closure']['pid'] for v in spawn_results]}) == 3,
                '常驻与两并发spawn必须为实际独立PID')
        require(all(originals[k] == canonical(v) for k, v in frames.items()), '父进程原输入被改变')
        source_closure = {key: dict(cache=cfg['sources'][seq]['cache'], SHA_unchanged=bool(
            checked(cfg['sources'][seq]['cache']))) for key, seq, _ in PREFIXES}
        report = dict(schema='official_ocsort_cached_admission_receipt_v1',
            status='complete_official_literal96_frames_ABA_two_spawn_exact_GT_guard_and_exit_verified',
            config=config_ref, parameters=PARAMETERS, source_prefixes={key: cfg['sources'][seq]['cache'] for key, seq, _ in PREFIXES},
            literal_vs_adapter=comparisons, literal_internal_Kalman_dtypes={k: v['Kalman_dtypes'] for k, v in references.items()},
            artificial_fixture=fixture, persistent_ABA=aba, persistent_worker=permanent_close,
            independent_spawn_A=spawn_results, parent_GT_guard=guard.evidence(), numeric_pools=pools,
            official_backend=official.metadata, parent_source_input_unchanged=True, all_workers_joined_exited=True,
            original_prediction_cache_closure=source_closure,
            logs=[ref(p) for p in sorted(output.glob('*.log'))], unique_source_frames=96,
            repeated_diagnostic_frame_consumptions=96+96+144+96+32,
            TrackEval_runs=0, optimizer_updates=0, performance_speedup_claim=False, test_read=False,
            wall_seconds=time.perf_counter()-started,
            limitations=['仅两个固定48帧前缀及人工边界夹具，不是十二片段完整评价或速度ABBA。',
                '来源JSONL原可含Pose；适配白名单只把bbox/score和帧尺寸交给官方core。',
                'GT保护自检故意触发拒绝，单列；Python open guard不是操作系统沙箱。',
                '同缓存官方固定2026版本core，不是CVPR2023原字节或官方完整demo成绩。'])
        write_new(output/'receipt.json', report)
        return report
    except BaseException:
        for worker in workers:
            process = worker['process']
            if process.is_alive():
                try:
                    worker['connection'].send(dict(kind='close'))
                except (BrokenPipeError, EOFError, OSError):
                    pass
                process.join(10.)
        write_new(output/'failed.json', dict(status='failed_partial_not_replayed', config=config_ref,
            traceback=traceback.format_exc(), workers=[dict(pid=w['process'].pid, alive=w['process'].is_alive(),
                exitcode=w['process'].exitcode) for w in workers], optimizer_updates=0, test_read=False))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256')
    parser.add_argument('--output', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    cfg, runtime = validate_config(args.config)
    output = physical(args.output)
    require(not output.exists(), '已存在准入partial或成功输出，不覆盖')
    if not args.execute:
        print(canonical(dict(status='read_only_plan_not_executed', parameters=PARAMETERS, output=str(output))))
        return
    require(args.config_sha256 and sha(args.config) == args.config_sha256, 'execute必须明确绑定冻结config SHA')
    result = execute(cfg, runtime, output, ref(args.config))
    print(canonical(dict(status=result['status'], receipt=str(output/'receipt.json'))))


if __name__ == '__main__':
    main()
