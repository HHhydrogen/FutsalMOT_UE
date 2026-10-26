"""绿色A/B真实last1000自由追踪；固定原检测/Pose缓存，不读取GT。"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from green_kit_runtime import EXPERIMENT, checked, complete_model, physical_output, read, require, rows, sha


def execute(config, run, output):
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', YOLO_AUTOINSTALL='false',
                      YOLO_CONFIG_DIR=str(EXPERIMENT/'_runtime/ultralytics'))
    cfg, numeric, model, adapter, binding = complete_model(config, run)
    import torch
    from grf_ue_bridge.learned_association_tracker_v8 import tracker_class
    torch.set_num_threads(1)
    old = read(checked(cfg['v9_protocol'])); source_cfg = read(checked(old['source_config']))
    source = next(s for s in source_cfg['sources'] if s['domain'] == 'real' and s['game'] == binding['fold'])
    frames = rows(checked(source['cache'])); require(len(frames) == 750, '固定750帧')
    tracker = tracker_class()(mode='learned', model=model, normalizer=adapter, use_pose=True,
                              pose_source_sha256=old['pose_checkpoint_sha256'], fixed_detection_sha256=source['cache']['sha256'])
    text = []
    for frame in frames:
        for row in tracker.update_frame(frame):
            x1, y1, x2, y2, identity, score = row[:6]
            text.append(','.join(map(str, [frame['frame_number'], int(identity), float(x1), float(y1),
                                          float(x2-x1), float(y2-y1), float(score), -1, -1, -1])))
    output = physical_output(output)
    require(EXPERIMENT in output.parents and not output.exists(), '全新绿色tracking输出')
    output.mkdir(parents=True); (output/'data').mkdir()
    mot = output/'data'/(source['sequence']+'.txt'); mot.write_text('\n'.join(text)+'\n', encoding='utf-8')
    value = dict(schema='green_kit_gated_tracking_v1', status='complete', protocol_sha256=sha(config),
                 binding=binding, fold=binding['fold'], sequence=source['sequence'], mode='green_kit_gated',
                 frames=750, tracked_rows=len(text), mot_sha256=sha(mot), cache=source['cache'],
                 trained_checkpoint=dict(path=str(Path(run)/'last.pt'), sha256=sha(Path(run)/'last.pt')),
                 audit=tracker.audit, GT_read=False, GPU_used=False, test_read=False)
    (output/'receipt.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'run', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    print(json.dumps(execute(args.config, args.run, args.output) if args.execute else
                     dict(status='readonly_green_tracking_plan', GT_read=False, GPU_used=False), ensure_ascii=False))
