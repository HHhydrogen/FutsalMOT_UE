"""v10独立共享原图检测与裁剪Pose；完整发布/UE退出后另签准入才可执行。"""
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
DATASET = Path('G:/FutsalMOT_Dataset')
NEW_DATA = DATASET / 'v4_pose17_multiseed_green_a01'
OLD_DATA = DATASET / 'v3_pose17_green_seeded_kit_pair_a01'
RUN = Path('D:/projects/FutsalMOT_UEDataset/Saved/AppearancePlanning/multiseed_v10_a01')
VAL = RESEARCH / 'public/sportsmot_val_v10_a01'
PWSH = 'C:/Users/20113/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'
POSE_SHA = 'c41fee957f91da4657f5b4f8822e22d53c6c527074c102e0a8c7490cf97736ec'
SOURCE_SHA = 'f30ec82c91c7f52e902deebfa8c924bffce649840eff2cc44600b4aa88ee93a2'


def require(ok, message):
    if not ok: raise ValueError(message)


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bind(path): return dict(path=str(path), sha256=sha(path))


def bound(ref):
    path = Path(ref['path']); require(path.is_file() and sha(path) == ref['sha256'], '来源SHA改变：' + str(path))
    return path


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush(); os.fsync(stream.fileno())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); sys.modules[name] = result
    spec.loader.exec_module(result); return result


def publication_gate(dataset, complete, capture):
    require(dataset.get('schema') == 'futsalmot_v10_multiseed_dataset_v1'
            and dataset.get('status') == 'diagnostic_complete_not_training'
            and [dataset.get(k) for k in ('rgb_frames', 'mask_frames', 'person_pose')] == [3600, 3600, 36000]
            and dataset.get('visibility') == 'unknown' and dataset.get('not_training') is True
            and dataset.get('MRQ_sync_verified') is False, 'v10完整数据未真实发布或来源限制升级')
    require(complete.get('status') == 'published_v10_12_units_metadata_complete'
            and complete.get('all_source_UE_normal_exit') is True and complete.get('EXR_retired') == 3600,
            '发布/正常退出/EXR链未闭合')
    rows = capture.get('completed', [])
    require(capture.get('schema') == 'futsalmot_multiseed_v10_serial_v1'
            and capture.get('status') == 'complete_full_12_units_EXR_retired_wait_root_publication'
            and len(rows) == len({r['attempt'] for r in rows}) == 12
            and all(r.get('normal_UE_exit') is True and r.get('EXR_deleted') == 300
                    and [r.get(k) for k in ('rgb', 'mask', 'person_pose')] == [300, 300, 3000] for r in rows),
            '十二个实际单位未完整退出/退休')


def validate_processes(rows):
    require(not any(r['Name'].lower() == 'unrealeditor.exe' or
                    (r['Name'].lower().startswith('python') and 'run_multiseed_v10_serial.py'
                     in (r['CommandLine'] or '').lower()) for r in rows), 'UE或采集控制器仍活动，不抢GPU')


def producers_absent():
    script = "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe' OR Name='python.exe'\" | Select-Object ProcessId,Name,CommandLine) | ConvertTo-Json -Compress"
    result = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', script], check=True,
                            capture_output=True, text=True, encoding='utf-8')
    rows = json.loads(result.stdout.strip() or '[]')
    validate_processes([rows] if isinstance(rows, dict) else rows)


def preflight(config_path):
    cfg = read(config_path); bundle = Path(cfg['bundle'])
    require(cfg.get('schema') == 'v10_shared_prediction_config_v1' and cfg.get('approved_by') == 'root'
            and cfg.get('prediction_authorized') is True and cfg.get('training_authorized') is False
            and cfg.get('test116187_sealed') is True, '缺独立v10预测准入')
    require(bundle.parent == RESEARCH/'code' and Path(__file__).resolve() == bundle/'tools/research_ops/v10_prediction_cache.py',
            '只能运行D研究目录独立冻结bundle')
    code = {entry['path']: entry for entry in cfg['code_files']}
    required = {'tools/research_ops/v10_prediction_cache.py', 'tools/research_ops/v10_prediction_inputs.py',
                'tools/research_ops/v8_prediction_cache.py', 'tools/performance/ordered_prefetch.py',
                'python/src/grf_ue_bridge/storage_policy.py'}
    require(required <= set(code) and len(code) == len(cfg['code_files']), '必要来源代码缺失或重复')
    for name, entry in code.items():
        relative = Path(name)
        require(not relative.is_absolute() and not relative.drive and '..' not in relative.parts
                and sha(bundle/relative) == entry['sha256'], '新执行源码绑定变化')
    storage = module('v10_prediction_storage', bundle/'python/src/grf_ue_bridge/storage_policy.py')
    storage.physical_child(bundle, RESEARCH/'code')
    for name in code: storage.physical_child(bundle/name, bundle)
    expected = {'dataset':NEW_DATA/'dataset.json', 'publication':NEW_DATA/'_publication_a01/complete.json',
                'capture_state':RUN/'control_full_a01/state.json', 'old_dataset':OLD_DATA/'dataset.json',
                'old_publication':OLD_DATA/'_publication_a01/complete.json',
                'external_initial':VAL/'initial_manifest.json', 'external_decode':VAL/'decode_validation_a01.json',
                'external_download':VAL/'download_a01/complete.json', 'external_identity':VAL/'identity_receipt.json'}
    values = {}
    for key, target in expected.items():
        path = bound(cfg[key]); require(path == target, '未登记的数据或val路径：' + key)
        storage.physical_child(path, DATASET if key in ('dataset','publication','old_dataset','old_publication')
                               else RESEARCH if key.startswith('external') else RUN)
        values[key] = read(path)
    dataset, complete, capture = (values[k] for k in ('dataset','publication','capture_state'))
    publication_gate(dataset, complete, capture)
    require(complete['dataset_sha256'] == cfg['dataset']['sha256'] and dataset['source_control'] == cfg['capture_state'],
            '发布/最终采集SHA不闭合')
    old, old_complete = values['old_dataset'], values['old_publication']
    require(old['schema'] == 'futsalmot_green_seeded_kit_pair_dataset_v1'
            and old['not_training'] is True and old['MRQ_sync_verified'] is False
            and old_complete['dataset_sha256'] == cfg['old_dataset']['sha256']
            and old_complete['status'] == 'published_green_16_units_metadata_pair_complete', '旧1048绿色成品来源不符')
    decoded, reviewed = values['external_decode'], values['external_identity']
    require(decoded['download_complete_sha256'] == cfg['external_download']['sha256']
            and decoded['source_identity'] == cfg['external_identity']
            and reviewed['initial_manifest'] == cfg['external_initial']
            and reviewed['no_overlap_with_observed_three_source_matches'] is True
            and reviewed['test_read'] is False, '新比赛来源/身份验收链不一致')
    source = read(bound(cfg['source_prediction_config']))
    require(cfg['source_prediction_config']['sha256'] == SOURCE_SHA
            and cfg['detector_checkpoint'] == source['detector_checkpoint']
            and cfg['v6_protocol'] == source['v6_protocol'] and cfg['pose_checkpoint_sha256'] == POSE_SHA,
            '原PT检测/Pose数值来源改变')
    bound(cfg['v6_protocol']); bound(cfg['detector_checkpoint'])
    for entry in source['code_files']:
        require(entry['path'] in code and code[entry['path']]['sha256'] == entry['sha256'], '冻结裁剪函数或预取不一致')
    inputs = module('v10_prediction_inputs_bound', bundle/'tools/research_ops/v10_prediction_inputs.py')
    groups = []
    for seed in sorted(inputs.WINDOWS):
        root = OLD_DATA if seed == 1048 else NEW_DATA
        entry = old['groups']['1048/B'] if seed == 1048 else dataset['groups'][str(seed)]
        path = storage.physical_child(root/entry['group_ref'], root)
        require(sha(path) == entry['sha256'], '发布组SHA改变')
        groups.append(dict(group=read(path), path=path))
    sources = inputs.assemble(groups, values['external_initial'], decoded, VAL)
    for source in sources:
        source['image_root'] = str(VAL if source['domain'] == 'real' else OLD_DATA if source['seed'] == 1048 else NEW_DATA)
        for frame in (source['frames'][0], source['frames'][-1]):
            require(storage.physical_child(frame['image_file'], source['image_root']).is_file(), '真实首尾源图缺失')
    output = storage.physical_child(cfg['output'], RESEARCH/'pose/multiseed_v10_a01')
    require(not output.exists(), '输出已存在或partial，不隐式覆盖/重播')
    producers_absent()
    return cfg, bundle, inputs, storage, sources, output


def raw_detections(rows, frame):
    """保留原v8原图检测的截边/退化框规则，不按GT过滤检测。"""
    result = []; degenerate = 0
    for values in rows:
        require(len(values) == 6 and all(math.isfinite(float(v)) for v in values), '检测输出非有限或列数错误')
        x,y,r,b,score,category = map(float, values)
        require(category == 0 and 0 <= score <= 1, '不是固定person检测')
        x=max(0.,x); y=max(0.,y); r=min(float(frame['width']),r); b=min(float(frame['height']),b)
        if r <= x or b <= y: degenerate += 1; continue
        index = len(result); uid = '%s:%06d:%06d' % (frame['sequence'],frame['frame_number'],index)
        result.append(dict(detection_id=uid, source_index=index, bbox_xywh_px=[x,y,r-x,b-y], score=score, class_id=0))
    return result, degenerate


def attach(frame, detections, predicted, pose_sha, detector_sha):
    require(len(detections) == len(predicted), 'Pose缺失，不能删检测或用旧缓存回填')
    for original, new in zip(detections, predicted):
        require(new['uid'] == new['detection_id'] == original['detection_id']
                and new['bbox_xywh_px'] == original['bbox_xywh_px'] and new['score'] == original['score']
                and new['class_id'] == 0 and type(new['prediction_valid']) is bool
                and len(new['xy_px']) == len(new['geometry_valid']) == 17
                and all(len(p) == 2 and all(math.isfinite(v) for v in p) for p in new['xy_px'])
                and all(type(v) is bool for v in new['geometry_valid']) and new['physical_visibility'] == 'unknown',
                'Pose改变固定原图检测或格式')
        new.update(model_sha256=pose_sha, detector_sha256=detector_sha)
    return dict(frame, detections=predicted, prediction_origin='v10_actual_same_PT_raw_detector_and_crop_pose',
                GT_used_for_predictions=False)


def execute(config_path, expected_sha):
    require(expected_sha and sha(config_path) == expected_sha, '显式新预测配置SHA不符')
    cfg, bundle, inputs, storage, sources, output = preflight(config_path)
    # 先独占保留本次输出，再加载模型，重复启动不能同时占用GPU或覆盖partial。
    output.mkdir(parents=True, exist_ok=False)
    write(output/'started.json', dict(status='started_not_complete', config_sha256=expected_sha,
         new_optimizer_updates=0, GT_used_for_predictions=False))
    try:
        old_cfg = read(bound(cfg['v6_protocol']))
        sys.path.insert(0,str(Path(old_cfg['v6_bundle'])/'tools/research_ops'))
        from v6_crop_runtime import load, configure_runtime, model
        old, _, base, legacy, core = load(Path(cfg['v6_protocol']['path']))
        legacy.training_complete(base.config, require_absent=True); configure_runtime()
        import cv2
        import numpy as np
        import torch
        import ultralytics
        from ultralytics import YOLO
        require(torch.__version__ == '2.6.0+cu124' and ultralytics.__version__ == '8.4.60', '数值环境变化')
        torch.set_num_threads(4); cv2.setNumThreads(1)
        torch.backends.cudnn.benchmark=False; torch.backends.cudnn.deterministic=True
        torch.use_deterministic_algorithms(True)
        require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0] >= 2*1024**3, 'GPU余量不足')
        detector = YOLO(str(bound(cfg['detector_checkpoint'])))
        pose, pose_identity = model(old,base,'pretrained')
        require(pose_identity['sha256'] == POSE_SHA, '独立PT Pose身份不符')
        pose=pose.to('cuda:0').float().eval()
        numeric=module('v10_frozen_crop_numeric',bundle/'tools/research_ops/v8_prediction_cache.py')
        prefetch_module=module('v10_frozen_prefetch',bundle/'tools/performance/ordered_prefetch.py')
        completed=[]
        for source in sources:
            sequence=source['sequence']; counts=Counter(); partial=output/(sequence+'.partial.jsonl')
            def loader(frame):
                path=storage.physical_child(frame['image_file'],source['image_root'])
                image=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
                require(image is not None and image.shape[:2] == (source['height'],source['width']), '实际源图解码或尺寸错误')
                return frame,image
            prefetch=prefetch_module.OrderedPrefetch(loader,source['frames'],capacity=2,max_item_bytes=40*1024**2,
                                                     measure_bytes=lambda x:int(x[1].nbytes))
            with partial.open('x',encoding='utf-8') as stream, prefetch:
                for record,image in prefetch:
                    frame=inputs.inference_frame(source,record)
                    output_rows=detector.predict(source=image,imgsz=640,conf=.1,iou=.7,classes=[0],max_det=300,
                        agnostic_nms=False,augment=False,half=False,rect=True,batch=1,device='cuda:0',verbose=False)[0]
                    detections,rejected=raw_detections(output_rows.boxes.data.detach().cpu().tolist(),frame)
                    frame['detections']=detections
                    predicted=numeric.pose_predictions(image,detections,frame,pose,core)
                    cached=attach(frame,detections,predicted,pose_identity['sha256'],cfg['detector_checkpoint']['sha256'])
                    stream.write(json.dumps(cached,separators=(',',':'),allow_nan=False)+'\n')
                    counts['frames']+=1; counts['raw_detections']+=len(predicted); counts['degenerate_model_boxes']+=rejected
                    for detection in predicted: counts['geometry_valid' if detection['prediction_valid'] else 'bbox_only']+=1
                    if counts['frames']%50 == 0:
                        stream.flush(); print(json.dumps(dict(sequence=sequence,frames=counts['frames'])),flush=True)
                stream.flush(); os.fsync(stream.fileno())
            require(counts['frames'] == len(source['frames']), '实际帧数不完整')
            target=output/(sequence+'.jsonl'); partial.rename(target)
            spec={k:v for k,v in source.items() if k != 'frames'}
            spec.update(cache=bind(target),counts=dict(counts),prefetch=prefetch.stats,GT_used_for_predictions=False,
                        actual_decoded_frames=counts['frames'],media_rehashed=False)
            completed.append(spec); write(output/(sequence+'.complete.json'),spec)
        require(len(completed) == 18 and sum(s['counts']['frames'] for s in completed) == 5925, '共享矩阵尚未完整')
        manifest=dict(schema='v10_shared_prediction_cache_manifest_v1',status='complete_18_sources_not_training_authorized',
            sources=completed,config_sha256=expected_sha,detector=cfg['detector_checkpoint'],pose_checkpoint=pose_identity,
            dataset=cfg['dataset'],publication=cfg['publication'],capture_state=cfg['capture_state'],old_dataset=cfg['old_dataset'],
            external_decode=cfg['external_decode'],external_identity=cfg['external_identity'],source_prediction_config=cfg['source_prediction_config'],
            synthetic_frames=4800,external_validation_frames=1125,all_raw_detections_new_same_pipeline=True,
            old_blue_boxes_reused=False,GT_used_for_predictions=False,final116187_read=False,new_optimizer_updates=0,
            source_flags_retained=dict(diagnostic_only=True,not_training=True,visibility='unknown',MRQ_sync_verified=False))
        write(output/'manifest.json',manifest)
        print(json.dumps(dict(status=manifest['status'],manifest=str(output/'manifest.json'))),flush=True)
    except BaseException as error:
        write(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(error),config_sha256=expected_sha))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--config-sha256');parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.execute: execute(args.config,args.config_sha256)
    else:
        *_,sources,output=preflight(args.config)
        print(json.dumps(dict(status='readonly_v10_prediction_preflight',sources=len(sources),
            frames=sum(len(s['frames']) for s in sources),output=str(output),GPU_inference=False,new_optimizer_updates=0)))
