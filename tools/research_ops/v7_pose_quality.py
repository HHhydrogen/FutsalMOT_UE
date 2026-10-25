"""v7已知人物框条件下的COCO位置质量诊断；不是检测AP或足球GT评价。"""
import argparse
from collections import OrderedDict
import gc
import hashlib
import json
import math
from pathlib import Path
import sys
import time

RESEARCH = Path('D:/projects/FutsalMOT_Research')
LIMBS = tuple(range(5, 17))
SIGMAS = [value/10 for value in (.26, .25, .25, .35, .35, .79, .79, .72, .72,
                               .62, .62, 1.07, 1.07, .87, .87, .89, .89)]


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok, message):
    if not ok: raise ValueError(message)


def quality(annotation, prediction, sigmas=SIGMAS):
    """未预测点计零分；GT的v仅用于评价分组，不成为预测可见性。"""
    area = float(annotation['area'])
    require(math.isfinite(area) and area > 0, 'GT面积无效')
    values = []
    for joint in range(17):
        x, y, visible = annotation['keypoints'][joint*3:joint*3+3]
        if visible == 0: continue
        point = None if prediction is None else prediction[joint]
        valid = point is not None and len(point) == 2 and all(math.isfinite(v) for v in point)
        squared = (point[0]-x)**2+(point[1]-y)**2 if valid else math.inf
        values.append(dict(joint=joint, GT_v=visible, finite_prediction=valid,
                           normalized_error=math.sqrt(squared/area),
                           oks=math.exp(-squared/(2*(2*sigmas[joint])**2*area))))
    require(values, '只评价有已标注关节点的人物')
    return values


def aggregate(rows):
    result = {}
    groups = dict(all=lambda p: True, limbs=lambda p: p['joint'] in LIMBS,
                  GT_v1=lambda p: p['GT_v'] == 1, GT_v2=lambda p: p['GT_v'] == 2)
    for name, predicate in groups.items():
        points = [p for row in rows for p in row['points'] if predicate(p)]
        persons = [[p for p in row['points'] if predicate(p)] for row in rows]
        persons = [p for p in persons if p]
        result[name] = dict(labeled_joints=len(points), persons=len(persons),
            finite_prediction_fraction=sum(p['finite_prediction'] for p in points)/len(points) if points else None,
            mean_person_OKS=sum(sum(p['oks'] for p in values)/len(values) for values in persons)/len(persons) if persons else None,
            PCK_sqrt_segmentation_area={str(threshold): sum(p['normalized_error'] <= threshold for p in points)/len(points) if points else None for threshold in (.05, .1, .2)})
    return result


def load_context(config_path):
    config = read(config_path)
    bundle = Path(config['bundle']).resolve()
    require(Path(__file__).resolve() == bundle/'tools/research_ops/v7_pose_quality.py' and bundle.parent == RESEARCH/'code', '仅从不可变D研究代码执行')
    for entry in config['code_files']:
        require(sha(bundle/entry['path']) == entry['sha256'], '质量诊断源码变化')
    reference = Path(config['v6_protocol']['path'])
    require(sha(reference) == config['v6_protocol']['sha256'], '原v6模型准入变化')
    sys.path.insert(0, str(Path(read(reference)['v6_bundle'])/'tools/research_ops'))
    from v6_crop_runtime import load, model
    previous, _, base, legacy, core = load(reference)
    legacy.training_complete(base.config, require_absent=True)
    require(read(config['v6_complete']['path'])['status'] == 'complete_ten_models_and_analysis', 'v6尚未完整结束')
    source = config['dev_manifest']
    require(sha(source['path']) == source['sha256'], '原公开200dev来源变化')
    manifest = read(source['path']); gt = read(manifest['ground_truth']['path'])
    require(sha(manifest['ground_truth']['path']) == manifest['ground_truth']['sha256'], '公开GT来源变化')
    require(len(manifest['image_ids']) == 200 and manifest['role'] == 'public_pose_development_only_not_final_test', '只允许既有公开200dev')
    images = {int(row['image_id']): row for row in manifest['images']}
    annotations = sorted([a for a in gt['annotations'] if a.get('num_keypoints', 0) > 0 and not a.get('iscrowd', 0)], key=lambda a: (a['image_id'], a['id']))
    require(len(annotations) == config['persons'] == 514 and all(a['image_id'] in images for a in annotations), '固定514人物清单变化')
    return config, bundle, previous, base, core, model, annotations, images


class Loader:
    """预取线程独占有界原图LRU，消费者只拿uint8裁剪和变换。"""
    def __init__(self, annotations, images, core):
        self.annotations, self.images, self.core = annotations, images, core
        self.cache = OrderedDict(); self.bytes = 0

    def __call__(self, index):
        import cv2
        import numpy as np
        annotation = self.annotations[index]; entry = self.images[annotation['image_id']]
        image_id = annotation['image_id']
        if image_id in self.cache:
            image = self.cache.pop(image_id); self.cache[image_id] = image
        else:
            path = Path(entry['path']).resolve()
            require(RESEARCH in path.parents and 'val2017' in path.parts, '质量诊断不读取其他媒体域')
            image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            require(image is not None and image.shape[:2] == (entry['height'], entry['width']), '媒体无法解码或尺寸变化')
            while self.cache and self.bytes+image.nbytes > 64*1024**2:
                _, old = self.cache.popitem(last=False); self.bytes -= old.nbytes
            if image.nbytes <= 64*1024**2:
                self.cache[image_id] = image; self.bytes += image.nbytes
        x, y, w, h = map(float, annotation['bbox']); width, height = entry['width'], entry['height']
        left, top = max(0., x), max(0., y); right, bottom = min(float(width), x+w), min(float(height), y+h)
        require(right > left and bottom > top, 'GT框无图像交集')
        box = [left, top, right-left, bottom-top]
        geometry = self.core.crop_geometry(box, (width, height)); a, b, cw, ch = geometry['crop_xywh']
        from grf_ue_bridge.pose_location_dataset_v2 import letterbox_geometry
        pad = letterbox_geometry(cw, ch, 640)
        resized = cv2.resize(image[b:b+ch, a:a+cw], pad['resize_wh'], interpolation=cv2.INTER_LINEAR)
        padded = cv2.copyMakeBorder(resized, pad['top'], pad['bottom'], pad['left'], pad['right'], cv2.BORDER_CONSTANT, value=(114, 114, 114))
        return dict(annotation=annotation, box=box, geometry=geometry,
                    tensor=np.ascontiguousarray(padded[:, :, ::-1].transpose(2, 0, 1)),
                    GT_box_clipped=box != annotation['bbox'])


def choose(predictions, box, core):
    x, y, w, h = box; cx, cy = x+w/2, y+h/2
    ranked = []
    for prediction in predictions:
        overlap = core.original.bbox_iou(box, prediction['bbox_xywh_px'])
        if overlap < .3: continue
        a, b, pw, ph = prediction['bbox_xywh_px']
        distance = ((a+pw/2-cx)/w)**2+((b+ph/2-cy)/h)**2
        ranked.append(((-overlap, distance, -prediction['score']), prediction))
    ranked.sort(key=lambda p: p[0])
    return None if not ranked or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]) else ranked[0][1]['xy_px']


def execute(config_path):
    config, bundle, previous, base, core, load_model, annotations, images = load_context(config_path)
    require(config['approved_by'] == 'root' and config['execution_authorized'], '未签本轮质量诊断')
    output = Path(config['output']).resolve()
    require(RESEARCH/'pose/pose_v7' in output.parents and not output.exists(), '仅全新D研究输出，保留partial')
    from v6_crop_runtime import configure_runtime
    configure_runtime()
    import cv2
    import numpy as np
    import torch
    from ultralytics.utils.metrics import OKS_SIGMA
    from ultralytics.utils.nms import non_max_suppression
    sys.path.insert(0, str(bundle/'tools/performance'))
    from ordered_prefetch import OrderedPrefetch
    require(np.allclose(np.asarray(SIGMAS), OKS_SIGMA, rtol=0, atol=1e-8), 'COCO17 sigma语义与原评价链不同')
    # 原Ultralytics常量是float32；实际评价直接使用其精确值，不把float64字面量当同字节。
    sigmas = OKS_SIGMA.tolist()
    require(torch.cuda.mem_get_info()[0] >= 2*1024**3, 'GPU余量不足，保留现场不开始')
    torch.set_num_threads(4); cv2.setNumThreads(1)
    torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    output.mkdir(parents=True)
    def write(name, value):
        path = output/name
        with path.open('x', encoding='utf-8') as stream: json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    write('started.json', dict(status='quality_diagnostic_started', config_sha256=sha(config_path), new_training_updates=0))
    reports = {}
    for key in config['models']:
        start = time.perf_counter(); loaded, identity = load_model(previous, base, key); loaded = loaded.to('cuda:0').float().eval()
        require(all(not tensor.is_floating_point() or tensor.dtype == torch.float32 for tensor in loaded.state_dict().values()), '只用实际FP32')
        loader = Loader(annotations, images, core); rows = []; failures = 0
        def process(batch):
            nonlocal failures
            inputs = torch.from_numpy(np.stack([item['tensor'] for item in batch])).to('cuda:0').float()/255.
            with torch.inference_mode():
                predictions = non_max_suppression(loaded(inputs), conf_thres=.001, iou_thres=.7, classes=[0], agnostic=False, multi_label=False, max_det=100, nc=1, max_time_img=10.)
            for item, predicted in zip(batch, predictions):
                mapped = [core.inverse_prediction(row, item['geometry']) for row in predicted.detach().cpu().tolist()]
                selected = choose([row for row in mapped if row is not None], item['box'], core)
                failures += selected is None
                points = quality(item['annotation'], selected, sigmas)
                # 未匹配关节误差为无穷，持久化用null且OKS/PCK仍按零分计。
                rows.append(dict(annotation_id=item['annotation']['id'], image_id=item['annotation']['image_id'],
                                 GT_box_clipped=item['GT_box_clipped'], points=points, target_matched=selected is not None))
        stream = OrderedPrefetch(loader, range(len(annotations)), capacity=2, max_item_bytes=2*1024**2, measure_bytes=lambda item: item['tensor'].nbytes)
        with stream:
            batch = []
            for item in stream:
                batch.append(item)
                if len(batch) == 16: process(batch); batch = []
            if batch: process(batch)
        report = dict(checkpoint=identity, persons=len(rows), target_not_matched=failures,
                      GT_boxes_clipped=sum(row['GT_box_clipped'] for row in rows), metrics=aggregate(rows),
                      wall_seconds=time.perf_counter()-start, prefetch=stream.stats, prediction_visibility='unknown', sigma_source='ultralytics_OKS_SIGMA_float32_exact_values',
                      GT_crop_is_oracle_diagnostic=True, tracking_metrics=False, new_optimizer_updates=0)
        reports[key] = report
        write(key+'.json', report)
        del loaded, loader; gc.collect(); torch.cuda.empty_cache()
    paired = {}
    for floor in ('R3S_blue', 'R3S_terracotta'):
        values = []
        for seed in (20261024, 20261025, 20261026):
            m, r, p = reports[f'{floor}_seed{seed}']['metrics'], reports[f'R3_seed{seed}']['metrics'], reports['pretrained']['metrics']
            values.append(dict(seed=seed, limb_OKS_minus_R3=m['limbs']['mean_person_OKS']-r['limbs']['mean_person_OKS'],
                               limb_OKS_minus_pretrained=m['limbs']['mean_person_OKS']-p['limbs']['mean_person_OKS'],
                               all_OKS_minus_R3=m['all']['mean_person_OKS']-r['all']['mean_person_OKS'],
                               all_OKS_minus_pretrained=m['all']['mean_person_OKS']-p['all']['mean_person_OKS']))
        paired[floor] = dict(by_seed=values, means={name: sum(row[name] for row in values)/3 for name in values[0] if name != 'seed'})
    write('summary.json', dict(schema='futsalmot_v7_oracle_crop_pose_quality_v1', status='complete_all_ten_models', models=reports, paired=paired,
                              scope='fixed_original_200_COCO_dev_514_GT_person_crops_not_end_to_end_AP_or_soccer_pose_GT',
                              new_formal_training_updates=0, final116187_read=False, GT_used_for_tracking=False,
                              config_sha256=sha(config_path), limits=['COCO_pretraining_overlap_disclosed', 'existing_noncrowd_subset_bias', 'unknown_predicted_visibility', 'oracle_box_diagnostic_only']))
    print(json.dumps(dict(status='complete_all_ten_models', output=str(output), paired=paired)))


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config', type=Path, required=True); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    if args.execute: execute(args.config)
    else:
        config, _, _, _, _, _, annotations, _ = load_context(args.config)
        print(json.dumps(dict(status='readonly_quality_ready', persons=len(annotations), models=len(config['models']), optimizer_updates=0)))


if __name__ == '__main__': main()
