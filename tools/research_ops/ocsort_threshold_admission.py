"""det_thresh .6→.25独立零更新准入；旧默认只作小夹具回归，不重跑十二场。"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ocsort_threshold_runtime as threshold

old = threshold.frozen_module('ocsort_threshold_original_admission', threshold.SOURCE_ADMISSION)
R = old.R
EXP = R/'pose/ocsort_threshold025_a01'
PREFIXES = old.PREFIXES
SEQUENCES = old.SEQUENCES
PARAMETERS = dict(deepcopy(old.PARAMETERS),
    fixture='float32_strict025_boundary_and_old06_unchanged_empty_crossing_missing_solver_GT_Pose_pollution',
    single_factor='only_det_thresh_0.6_to_0.25', old06_regression_scope='small_fixture_only_not12_clips')
STATUS = 'complete_official_threshold025_literal96_ABA_two_spawn_exact_GT_guard_and_exit_verified'
require, canonical, checked, ref, sha = old.require, old.canonical, old.checked, old.ref, old.sha
physical, read, write_new = old.physical, old.read, old.write_new
public_frame, prefix_frames = old.public_frame, old.prefix_frames
literal_reference, compare_outputs = old.literal_reference, old.compare_outputs
GTGuard, GTReadBlocked = old.GTGuard, old.GTReadBlocked
numeric_threads, start_worker, receive, close_worker = old.numeric_threads, old.start_worker, old.receive, old.close_worker


def validate_config(path):
    path = physical(path)
    cfg = read(path)
    require(cfg['schema'] == 'official_ocsort_threshold025_admission_config_v1' and cfg['approved_by'] == 'root'
        and cfg['diagnostic_authorized'] is True and cfg['test_sealed'] is True, '需要root独立冻结.25准入')
    require(set(cfg['sources']) == set(SEQUENCES) and cfg['admission_parameters'] == PARAMETERS,
            '原十二来源/96帧准入矩阵不得改变')
    require(cfg['source_runtime'] == threshold.SOURCE_RUNTIME and cfg['source_admission'] == threshold.SOURCE_ADMISSION,
            '只能复用原2865已闭合适配/准入源码')
    runtime = old.load_runtime(cfg['runtime'])
    require(cfg['parameters'] == runtime.PARAMETERS == threshold.PARAMETERS
        and runtime.SOURCE_RUNTIME == threshold.SOURCE_RUNTIME, '只允许det_thresh .25单因素')
    runtime.single_factor_contract()
    runtime.inspect_source_contract(cfg['official_manifest'])
    checked(cfg['dependency_manifest'])
    require(isinstance(cfg['protected_GT_paths'], list) and cfg['protected_GT_paths'], 'GT保护路径不能空')
    for protected in cfg['protected_GT_paths']:
        physical(protected)
    for _, sequence, count in PREFIXES:
        source = cfg['sources'][sequence]
        require(source['frames'] >= count and source['cache']['sha256'], '原实际缓存不足固定48帧')
        physical(source['cache']['path'])
    require(checked(cfg['admission_source']) == Path(__file__).resolve(), '执行入口不是新冻结准入源码')
    return cfg, runtime


def float32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def boundary_frames():
    """事前固定FP32相邻值；不按真实结果选择检测或阈值。"""
    threshold_bits = struct.unpack('<I', struct.pack('<f', .25))[0]
    below = struct.unpack('<f', struct.pack('<I', threshold_bits-1))[0]
    above = struct.unpack('<f', struct.pack('<I', threshold_bits+1))[0]
    rows = [([10, 10, 20, 40], below), ([60, 10, 20, 40], float32(.25)),
            ([110, 10, 20, 40], above), ([160, 10, 20, 40], float32(.6))]
    values = []
    for index in range(4):
        detections = [] if index == 1 else (rows if index == 0 else [([110, 10, 20, 40], .9)])
        values.append(dict(sequence='artificial_threshold025_boundary', width=400, height=240, fps=25,
            frame_index=index, frame_number=index+1, timestamp_sec=index/25, endpoint_GT='must_not_be_read',
            detections=[dict(bbox_xywh_px=box, score=score, xy_px='must_not_be_read',
                GT_identity='must_not_be_read', geometry_valid=False) for box, score in detections]))
    return values


def artificial_gate(runtime, official, parameters):
    before_parameters = deepcopy(runtime._original.PARAMETERS)
    before_source = threshold.sha(threshold.SOURCE_RUNTIME['path'])
    # 原.6夹具走原冻结函数本身，不能以新wrapper模拟旧方法充数。
    original_regression = old.artificial_gate(runtime._original, official, runtime.ORIGINAL_PARAMETERS)
    frames = boundary_frames()
    before = canonical(frames)
    clean = [public_frame(frame) for frame in frames]
    reference = literal_reference(clean, official, parameters)
    actual = runtime.track_frames(clean, official, parameters)
    comparison = compare_outputs(actual, reference)
    observed_x = [float(row[0]) for row in actual['raw_outputs'][0]]
    require(sorted(observed_x) == [110., 160.], 'FP32 .25严格边界改变：等值/下邻值必须排除，上邻值与.6必须保留')
    require(actual['audit']['empty_input_frames'] == 1 and canonical(frames) == before,
            '空检测每帧推进或污染输入白名单边界改变')
    require(before_parameters == runtime._original.PARAMETERS == runtime.ORIGINAL_PARAMETERS
        and before_source == threshold.sha(threshold.SOURCE_RUNTIME['path']) == threshold.SOURCE_RUNTIME['sha256'],
        '旧.6参数或源码被新单因素准入修改')
    return dict(comparison=comparison, float32_threshold=float32(.25),
        float32_equal025_excluded=True, float32_predecessor025_excluded=True,
        float32_successor025_accepted=True, score_equal06_accepted_under025=True,
        empty_frames=1, GT_Pose_pollution_whitelist_only=True, source_fixture_unchanged=True,
        old06_regression=original_regression, old06_parameters_unchanged=True, old06_source_bytes_unchanged=True,
        old06_regression_is_fixture_only_not12_clip_rerun=True,
        Kalman_internal_dtypes=reference['Kalman_dtypes'], single_factor_contract=runtime.single_factor_contract())


def proof_fields(fixture, contract):
    """只有实际边界与旧.6小夹具均完成时，才生成正式控制器要求的准入字段。"""
    require(contract['changed_parameters'] == {'det_thresh': dict(before=.6, after=.25)}
        and contract['copied_function_AST_identical'] is True
        and contract['original_module_globals_modified'] is False, '单因素来源证据不完整')
    required = ('float32_equal025_excluded', 'float32_predecessor025_excluded',
        'float32_successor025_accepted', 'score_equal06_accepted_under025',
        'old06_parameters_unchanged', 'old06_source_bytes_unchanged',
        'old06_regression_is_fixture_only_not12_clip_rerun')
    require(all(fixture[key] is True for key in required)
        and fixture['Kalman_internal_dtypes'] == ['float64'], '实际.25边界/旧.6未改证据未齐')
    for comparison in (fixture['comparison'], fixture['old06_regression']['comparison']):
        require(all(comparison[key] is True for key in ('original_ID_MOT_equal', 'all_frame_counts_equal',
            'per_frame_raw_outputs_exact')), '原ID/全部输出必须逐值一致')
    return dict(single_factor_parameters_verified=True,
        threshold025_boundary=dict(passed=True, float32_threshold=fixture['float32_threshold'],
            equal_excluded=True, predecessor_excluded=True, successor_accepted=True,
            equal06_accepted=True, comparison=fixture['comparison']),
        old06_fixture_exact=dict(passed=True, scope='original16_frame_fixture_only_not12_clip_rerun',
            parameters_unchanged=True, source_bytes_unchanged=True, proof=fixture['old06_regression']))


def execute(cfg, runtime, output, config_ref):
    output = physical(output)
    require(EXP in output.parents and not output.exists(), '仅新.25实验根准入目录，partial/成功不覆盖')
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
        parallel = []
        for index in range(2):
            worker = start_worker(cfg, output, 'spawn_A_'+str(index))
            parallel.append(worker)
            workers.append(worker)
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
                '常驻与两并发spawn必须实际独立PID')
        require(all(originals[key] == canonical(value) for key, value in frames.items()), '父进程原输入被改变')
        source_closure = {key: dict(cache=cfg['sources'][seq]['cache'], SHA_unchanged=bool(
            checked(cfg['sources'][seq]['cache']))) for key, seq, _ in PREFIXES}
        report = dict(schema='official_ocsort_threshold025_admission_receipt_v1', status=STATUS,
            config=config_ref, parameters=PARAMETERS, effective_parameters=runtime.parameters(),
            single_factor_contract=runtime.single_factor_contract(),
            source_prefixes={key: cfg['sources'][seq]['cache'] for key, seq, _ in PREFIXES},
            literal_vs_adapter=comparisons, literal_internal_Kalman_dtypes={key: value['Kalman_dtypes'] for key, value in references.items()},
            artificial_fixture=fixture, persistent_ABA=aba, persistent_worker=permanent_close,
            independent_spawn_A=spawn_results, parent_GT_guard=guard.evidence(), numeric_pools=pools,
            official_backend=official.metadata, parent_source_input_unchanged=True, all_workers_joined_exited=True,
            original_prediction_cache_closure=source_closure, logs=[ref(path) for path in sorted(output.glob('*.log'))],
            unique_source_frames=96, repeated_diagnostic_frame_consumptions=96+96+144+96+32+8,
            TrackEval_runs=0, optimizer_updates=0, performance_speedup_claim=False, test_read=False,
            wall_seconds=time.perf_counter()-started,
            limitations=['仅原两个48帧前缀和人工边界准入，不是十二片段完整评价或收益证据。',
                'det_thresh .25是用户事前授权单因素，不是官方CLI默认，也未与ByteTrack内部政策完全对齐。',
                '原.6只运行既有16帧边界小夹具，原十二场成品与源码不变。',
                'Python open guard不是操作系统沙箱；输入原JSON可含Pose，进入原core前按白名单剥离。'])
        report.update(proof_fields(fixture, report['single_factor_contract']))
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
    require(not output.exists(), '已存在准入partial/成品，不覆盖')
    if not args.execute:
        print(canonical(dict(status='read_only_threshold025_plan_not_executed', parameters=PARAMETERS, output=str(output))))
        return
    require(args.config_sha256 and sha(args.config) == args.config_sha256, 'execute必须绑定冻结config SHA')
    result = execute(cfg, runtime, output, ref(args.config))
    print(canonical(dict(status=result['status'], receipt=str(output/'receipt.json'))))


if __name__ == '__main__':
    main()
