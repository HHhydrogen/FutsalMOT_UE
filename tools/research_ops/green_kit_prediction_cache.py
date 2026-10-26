"""绿色A/B固定旧检测框的独立预测入口；发布及UE退出前拒绝执行。

只复用已冻结的裁剪Pose数值函数，不运行检测器、不读取GT，不覆盖旧池。
此文件在采集期间只是CPU候选；必须在真实发布后另签配置、安装独立bundle。
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

RESEARCH = Path('D:/projects/FutsalMOT_Research')
DATASET = Path('G:/FutsalMOT_Dataset/v3_pose17_green_seeded_kit_pair_a01')
CAPTURE = Path('D:/projects/FutsalMOT_UEDataset/Saved/AppearancePlanning/green_seeded_kit_a01/control_full_a01/state.json')
POWERSHELL = 'C:/Users/20113/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(ref):
    path = Path(ref['path'])
    require(path.is_file() and sha(path) == ref['sha256'], '来源绑定变化：' + str(path))
    return path


def bind(path):
    return dict(path=str(path), sha256=sha(path))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def publication_gate(dataset, complete, capture):
    require(dataset.get('schema') == 'futsalmot_green_seeded_kit_pair_dataset_v1'
            and dataset.get('status') == 'diagnostic_pair_complete_not_training'
            and [dataset.get(k) for k in ('rgb_frames', 'mask_frames', 'person_pose')] == [4800, 4800, 48000]
            and dataset.get('not_training') is True and dataset.get('MRQ_sync_verified') is False,
            '完整绿色数据未真实发布，来源限制不能升级')
    require(complete.get('status') == 'published_green_16_units_metadata_pair_complete'
            and complete.get('all_source_UE_normal_exit') is True and complete.get('EXR_retired') == 4800,
            '发布/正常退出/EXR消费链未闭合')
    rows = capture.get('completed', [])
    require(capture.get('status') == 'complete_full_16_units_EXR_retired_wait_root_publication'
            and len(rows) == 16 and len({r['attempt'] for r in rows}) == 16
            and all(r.get('normal_UE_exit') is True and r.get('EXR_deleted') == 300
                    and [r.get(k) for k in ('rgb', 'mask', 'person_pose')] == [300, 300, 3000]
                    for r in rows), '16个真实采集单位未全部闭合')


def require_producers_absent(capture_pid):
    # 查询失败必须失败，不能伪造空进程表；PID复用按命令行识别。
    script = "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe' OR Name='python.exe'\" | Select-Object ProcessId,Name,CommandLine) | ConvertTo-Json -Compress"
    result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', script],
                            check=True, capture_output=True, text=True, encoding='utf-8')
    rows = json.loads(result.stdout.strip() or '[]')
    if isinstance(rows, dict):
        rows = [rows]
    require(not any(r['Name'].lower() == 'unrealeditor.exe' or
                    (r['ProcessId'] == capture_pid and 'run_green_kit_serial_a01.py' in (r['CommandLine'] or ''))
                    for r in rows), 'UE或绿色采集驱动仍在运行，不抢GPU')


def fixed_frame(plan, predictions, image, variant, model_sha, detector_sha):
    """新Pose必须完整对应旧框；不能借缺预测筛除困难检测或回填旧Pose。"""
    expected = plan['detections']
    require(len(predictions) == len(expected), '新Pose检测数量改变')
    for old, new in zip(expected, predictions):
        require(all(new.get(k) == old[k] for k in ('uid', 'detection_id', 'bbox_xywh_px', 'score', 'class_id')),
                '新Pose改变固定检测UID/框/分数/顺序')
        require(new.get('image_wh') == [plan['width'], plan['height']]
                and new.get('timestamp_sec') == plan['timestamp_sec']
                and len(new.get('xy_px', [])) == len(new.get('geometry_valid', [])) == 17
                and all(isinstance(p, list) and len(p) == 2 and
                        all(type(v) in (int, float) and math.isfinite(v) for v in p) for p in new['xy_px'])
                and all(type(v) is bool for v in new['geometry_valid'])
                and type(new.get('prediction_valid')) is bool
                and new.get('physical_visibility') == 'unknown', '新Pose格式/时间错误')
        new.update(model_sha256=model_sha, detector_sha256=detector_sha)
    return dict(schema='green_kit_fixed_bbox_prediction_frame_v1', sequence=plan['logical_sequence'],
                sequence_id=plan['logical_sequence'], game='synthetic1048', role='train', domain='synthetic',
                fps=10, frame_index=plan['frame_index'], frame_number=plan['frame_number'],
                timestamp_sec=plan['timestamp_sec'], width=plan['width'], height=plan['height'],
                image_file=str(image), green_variant=variant, detections=predictions,
                prediction_origin='new_green_image_same_PT_crop_fixed_historical_boxes',
                physical_visibility='unknown', GT_used_for_predictions=False)


def preflight(config_path):
    cfg = read(config_path)
    require(cfg.get('schema') == 'green_kit_fixed_bbox_prediction_config_v1'
            and cfg.get('approved_by') == 'root' and cfg.get('prediction_authorized') is True,
            '必须另签绿色预测准入，CPU候选不是授权')
    bundle = Path(cfg['bundle'])
    require(bundle.parent == RESEARCH / 'code' and Path(__file__).resolve() == bundle / 'tools/research_ops/green_kit_prediction_cache.py',
            '只能执行D研究目录独立冻结bundle')
    for entry in cfg['code_files']:
        relative = Path(entry['path'])
        require(not relative.is_absolute() and '..' not in relative.parts
                and sha(bundle / relative) == entry['sha256'], '预测代码绑定变化')
    required = {'tools/research_ops/green_kit_prediction_cache.py', 'tools/research_ops/v8_prediction_cache.py',
                'tools/performance/ordered_prefetch.py', 'python/src/grf_ue_bridge/green_kit_pair_inputs.py',
                'python/src/grf_ue_bridge/storage_policy.py'}
    require(required <= {r['path'] for r in cfg['code_files']}, '独立预测必要源码绑定不完整')
    storage = module('green_prediction_storage', bundle / 'python/src/grf_ue_bridge/storage_policy.py')
    storage.physical_child(bundle, RESEARCH / 'code')
    for entry in cfg['code_files']:
        storage.physical_child(bundle / entry['path'], bundle)
    dataset_path = storage.physical_child(bound(cfg['dataset']), DATASET)
    complete_path = storage.physical_child(bound(cfg['publication']), DATASET)
    require(dataset_path == DATASET / 'dataset.json' and complete_path == DATASET / '_publication_a01/complete.json'
            and bound(cfg['capture_state']) == CAPTURE, '只准本轮真实绿色发布及采集链')
    dataset, complete, capture = read(dataset_path), read(complete_path), read(CAPTURE)
    publication_gate(dataset, complete, capture)
    require(complete['dataset_sha256'] == cfg['dataset']['sha256']
            and dataset['source_control'] == cfg['capture_state'], '发布与最终采集SHA未闭合')
    require_producers_absent(capture['pid'])
    inputs = module('green_prediction_inputs', bundle / 'python/src/grf_ue_bridge/green_kit_pair_inputs.py')
    old_manifest = read(bound(cfg['source_manifest']))
    old_v9 = read(bound(cfg['v9_protocol']))
    require(Path(cfg['v9_protocol']['path']) == RESEARCH / 'pose/pose_quality_v9/frozen_a01/protocol.json'
            and cfg['synthetic_pool'] == old_v9['synthetic_pool'], '必须固定原v9 S池和来源')
    pair_input = read(bound(old_v9['source_config']))
    source_prediction = read(bound(cfg['source_prediction_config']))
    require(cfg['source_manifest'] in pair_input['prediction_manifests']
            and old_manifest['config_sha256'] == cfg['source_prediction_config']['sha256']
            and cfg['v6_protocol'] == source_prediction['v6_protocol'], '旧预测/窗口/裁剪来源链不一致')
    require(old_manifest['status'] == 'complete_registered_sources_not_training_authorized'
            and old_manifest['domain_scope'] == 'synthetic' and len(old_manifest['sources']) == 4
            and {r['sequence'] for r in old_manifest['sources']} == inputs.SEQUENCES,
            '不是原完整1048四机位检测缓存')
    output = storage.physical_child(cfg['output'], RESEARCH / 'pose/green_seeded_kit_pair_a01')
    require(not output.exists(), '保留已有/partial，不隐式重放')
    groups = {}; tasks = {}; proofs = {}
    for variant in 'AB':
        entry = dataset['groups']['1048/' + variant]
        path = storage.physical_child(DATASET / entry['group_ref'], DATASET)
        require(sha(path) == entry['sha256'], '真实发布组SHA改变')
        group = read(path); groups[variant] = dict(path=path, ref=bind(path), group=group)
        for source in old_manifest['sources']:
            with bound(source['cache']).open(encoding='utf-8') as stream:
                frames = [json.loads(line) for line in stream]
            plans, proof = inputs.plan_green_frames(source, frames, group)
            key = variant + '/' + source['camera']; tasks[key] = (source, plans)
            proofs[key] = proof
    require(all(proofs['A/' + c]['raw_detection_order_sha256'] == proofs['B/' + c]['raw_detection_order_sha256']
                for c in ('CineCam_%02d' % n for n in range(1, 5))), 'A/B固定检测不一致')
    with bound(cfg['synthetic_pool']).open(encoding='utf-8') as stream:
        windows = [json.loads(line) for line in stream]
    original = {r['uid']: r for w in windows for r in [*w['history'], *(c['prediction'] for c in w['candidates'])]}
    inputs.replace_synthetic_pose(windows, original)
    return cfg, bundle, inputs, storage, old_manifest, output, groups, tasks, proofs


def execute(config_path, expected_sha):
    require(sha(config_path) == expected_sha, '显式预测配置SHA不同')
    cfg, bundle, inputs, storage, old_manifest, output, groups, tasks, proofs = preflight(config_path)
    old_config = read(bound(cfg['v6_protocol']))
    sys.path.insert(0, str(Path(old_config['v6_bundle']) / 'tools/research_ops'))
    from v6_crop_runtime import load, configure_runtime, model
    old, _, base, legacy, core = load(Path(cfg['v6_protocol']['path']))
    legacy.training_complete(base.config, require_absent=True)
    configure_runtime()
    import cv2
    import numpy as np
    import torch
    import ultralytics
    require(torch.__version__ == '2.6.0+cu124' and ultralytics.__version__ == '8.4.60', '数值运行环境变化')
    torch.set_num_threads(4); cv2.setNumThreads(1)
    torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0] >= 2 * 1024**3, 'GPU余量不足')
    pose, identity = model(old, base, 'pretrained')
    require(identity['sha256'] == old_manifest['pose_checkpoint']['sha256'], 'PT Pose身份不同')
    pose = pose.to('cuda:0').float().eval()
    numeric = module('green_bound_crop_numeric', bundle / 'tools/research_ops/v8_prediction_cache.py')
    prefetch_module = module('green_bound_prefetch', bundle / 'tools/performance/ordered_prefetch.py')
    with bound(cfg['synthetic_pool']).open(encoding='utf-8') as stream:
        windows = [json.loads(line) for line in stream]
    needed = {r['uid'] for w in windows for r in [*w['history'], *(c['prediction'] for c in w['candidates'])]}
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'started.json', dict(status='started_not_complete', config_sha256=expected_sha,
                                     new_optimizer_updates=0, detector_inference=False))
    sources = []; pools = {}
    for variant in 'AB':
        observations = {}; folder = output / variant; folder.mkdir()
        for camera in ('CineCam_%02d' % n for n in range(1, 5)):
            source, plans = tasks[variant + '/' + camera]; counts = Counter()
            def loader(plan):
                path = storage.physical_child(groups[variant]['path'].parent / plan['new_image_ref'], DATASET)
                image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
                require(image is not None and image.shape[:2] == (2160, 3840), '真实绿色PNG解码/尺寸错误')
                return plan, path, image
            prefetch = prefetch_module.OrderedPrefetch(loader, plans, capacity=2, max_item_bytes=40 * 1024**2,
                                                       measure_bytes=lambda x: int(x[2].nbytes))
            partial = folder / (source['sequence'] + '.partial.jsonl')
            with partial.open('x', encoding='utf-8') as stream, prefetch:
                for plan, path, image in prefetch:
                    frame = dict(width=3840, height=2160, timestamp_sec=plan['timestamp_sec'], detections=plan['detections'])
                    predicted = numeric.pose_predictions(image, plan['detections'], frame, pose, core)
                    row = fixed_frame(plan, predicted, path, variant, identity['sha256'],
                                      old_manifest['detector']['sha256'])
                    stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
                    counts['frames'] += 1; counts['raw_detections'] += len(predicted)
                    for record in predicted:
                        counts['geometry_valid' if record['prediction_valid'] else 'bbox_only'] += 1
                        if record['uid'] in needed:
                            observations[record['uid']] = {k: record[k] for k in inputs.RECORD_FIELDS}
                    if counts['frames'] % 50 == 0:
                        stream.flush()
                        print(json.dumps(dict(variant=variant, camera=camera, frames=counts['frames'])), flush=True)
                stream.flush(); os.fsync(stream.fileno())
            target = folder / (source['sequence'] + '.jsonl'); partial.rename(target)
            record = dict(variant=variant, camera=camera, logical_sequence=source['sequence'],
                          published_group=groups[variant]['ref'], historical_fixed_cache=source['cache'],
                          cache=bind(target), counts=dict(counts), prefetch=prefetch.stats,
                          correspondence=proofs[variant + '/' + camera],
                          actual_source_validation=dict(published_group_SHA_verified=True,
                              decoded_PNG_frames=counts['frames'], width=3840, height=2160,
                              paths_checked_no_reparse=True, media_rehashed=False))
            sources.append(record); write(folder / (camera + '.complete.json'), record)
        replaced, proof = inputs.replace_synthetic_pose(windows, observations)
        pool = folder / 'synthetic_pool.jsonl'
        with pool.open('x', encoding='utf-8') as stream:
            for row in replaced:
                stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
            stream.flush(); os.fsync(stream.fileno())
        pools[variant] = dict(pool=bind(pool), replacement=proof)
    require(pools['A']['replacement']['non_pose_sha256'] == pools['B']['replacement']['non_pose_sha256'],
            'A/B窗口除Pose以外不一致')
    manifest = dict(schema='green_kit_fixed_bbox_prediction_manifest_v1',
                    status='complete_AB_predictions_fixed_boxes_not_training_authorized', sources=sources,
                    synthetic_pools=pools, config_sha256=expected_sha, dataset=cfg['dataset'],
                    publication=cfg['publication'], capture_state=cfg['capture_state'],
                    historical_source_manifest=cfg['source_manifest'], historical_synthetic_pool=cfg['synthetic_pool'],
                    v9_protocol=cfg['v9_protocol'], v6_protocol=cfg['v6_protocol'],
                    source_prediction_config=cfg['source_prediction_config'],
                    pose_checkpoint=identity, raw_detector_reinferred=False, R_cache_modified=False,
                    GT_used_for_predictions=False, final116187_read=False, new_optimizer_updates=0,
                    source_flags_retained=dict(diagnostic_only=True, not_training=True,
                                               MRQ_sync_verified=False, physical_visibility='unknown'))
    write(output / 'manifest.json', manifest)
    print(json.dumps(dict(status=manifest['status'], manifest=str(output / 'manifest.json'))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        execute(args.config, args.config_sha256)
    else:
        cfg, _, _, _, _, _, _, tasks, proofs = preflight(args.config)
        print(json.dumps(dict(status='readonly_green_fixed_bbox_prediction_preflight',
                              source_views=len(tasks), frames=sum(len(t[1]) for t in tasks.values()),
                              correspondence=proofs, GPU_inference=False, new_optimizer_updates=0)))
