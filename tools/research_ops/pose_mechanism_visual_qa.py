"""固定规则抽取五场姿态质控图；只读已有预测，不把视觉复核冒充关键点真值。"""
import argparse
import hashlib
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import pose_mechanism_core as core

SEED = 20261027
CATEGORIES = ('small_trusted', 'larger_trusted', 'overlap_trusted', 'sparse_trusted')
EDGES = ((5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12),
         (11, 12), (11, 13), (13, 15), (12, 14), (14, 16))


def iou(a, b):
    x = max(0., min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]))
    y = max(0., min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    return x*y / max(1e-9, a[2]*a[3]+b[2]*b[3]-x*y)


def select(frames, labels):
    """不使用模型分数/追踪结果/视觉判断选样，按固定SHA次序抽取。"""
    groups = {k: [] for k in CATEGORIES}
    for frame in frames:
        for det in frame['detections']:
            if labels[det['uid']]['state'] != 'matched':
                continue
            limbs = sum(det['geometry_valid'][5:])
            overlap = max((iou(det['bbox_xywh_px'], x['bbox_xywh_px'])
                           for x in frame['detections'] if x['uid'] != det['uid']), default=0.)
            h = det['bbox_xywh_px'][3]
            item = dict(uid=det['uid'], frame_index=frame['frame_index'], frame_number=frame['frame_number'],
                        geometry_limbs=limbs, height_px=h, raw_max_IoU=overlap,
                        detector_score=det['score'], record=det)
            categories = []
            if limbs >= 6:
                categories.append('small_trusted' if h < 80 else 'larger_trusted')
                if overlap >= .1: categories.append('overlap_trusted')
            else: categories.append('sparse_trusted')
            for category in categories: groups[category].append(item)
    used = set(); result = []
    for category in CATEGORIES:
        ordered = sorted(groups[category], key=lambda d: hashlib.sha256(f"{SEED}|{category}|{d['uid']}".encode()).hexdigest())
        picked = next((d for d in ordered if d['uid'] not in used), None)
        if picked is None:
            result.append(dict(category=category, available=False))
        else:
            used.add(picked['uid']); result.append(dict(category=category, available=True, **picked))
    return result


def render(item, image, source):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
    tile = Image.new('RGB', (570, 420), '#eeeeee'); draw = ImageDraw.Draw(tile)
    draw.text((8, 6), item['category'], fill='black', font=font)
    if not item['available']:
        draw.text((8, 35), 'No eligible sample', fill='black', font=font); return tile
    det = item['record']; x, y, w, h = det['bbox_xywh_px']; iw, ih = image.size
    box = (max(0, math.floor(x-.3*w)), max(0, math.floor(y-.15*h)),
           min(iw, math.ceil(x+1.3*w)), min(ih, math.ceil(y+1.15*h)))
    crop = image.crop(box).convert('RGB'); overlay = crop.copy(); d = ImageDraw.Draw(overlay)
    xy = [(p[0]-box[0], p[1]-box[1]) for p in det['xy_px']]; valid = det['geometry_valid']
    line = max(1, round(crop.height/220)); radius = max(1, round(crop.height/100))
    for a, b in EDGES:
        if valid[a] and valid[b]: d.line([xy[a], xy[b]], fill='#00ffff', width=line)
    for j, (a, b) in enumerate(xy):
        if valid[j]: d.ellipse((a-radius,b-radius,a+radius,b+radius), fill='#ff2050')
    for k, im in enumerate((crop, overlay)):
        im.thumbnail((270, 305), Image.Resampling.LANCZOS)
        tile.paste(im, (k*285+(285-im.width)//2, 65+(305-im.height)//2))
    draw.text((8, 30), f"{item['uid']}  h={h:.1f}px limbs={item['geometry_limbs']}/12", fill='black', font=font)
    draw.text((8, 380), 'Raw crop | Predicted geometry-valid joints only', fill='black', font=font)
    return tile


def execute(inputs, output):
    from PIL import Image, ImageDraw, ImageFont
    prepared = core.read(inputs); core.require(prepared['status']=='complete_raw_inputs_labels_and_shape_swaps_no_inference', '库存未完成')
    storage = core.load('qa_storage', core.ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    real_config = core.read(Path('D:/projects/FutsalMOT_Research/pose/learned_association_v8/prediction_frozen_real_a01/config.json'))
    real_manifest = core.read(core.checked(real_config['real_manifest']))
    images = {s['sequence_id']: {f['frame_number']: f for f in s['frames']} for s in real_manifest['sequences']}
    output = storage.physical_child(output, core.V); core.require(not output.exists(), '新QA输出，partial不覆盖')
    output.mkdir(parents=True)
    manifest = dict(schema='pose_mechanism_visual_QA_v1', status='contact_sheets_ready_pending_root_visual_review',
                    inputs=core.ref(inputs), source_code=core.ref(__file__), seed=SEED,
                    selection='fixed_80px_scale_raw_IoU01_and_6limb_strata_minSHA_no_result_selection',
                    inference=False, optimizer_updates=0, keypoint_GT_available=False,
                    human_annotation_provided=False, test_read=False, real_frame_manifest=real_config['real_manifest'], sheets=[], samples=[])
    for seq, refs in prepared['sources'].items():
        source = refs['source']; frames = core.rows(core.checked(source['cache']))
        labels = core.read(core.checked(refs['labels']))['labels']; items = select(frames, labels)
        canvas = Image.new('RGB', (1140, 880), 'white'); draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
        draw.text((12, 8), seq+' | fixed cached Pose | visual review, not keypoint accuracy', fill='black', font=font)
        for k, item in enumerate(items):
            if item['available']:
                if seq.startswith('SNMOT-'):
                    frame = images[seq][item['frame_number']]
                    core.require(frame['frame_index']==item['frame_index'], '源帧零/一基对应不一致')
                    path = Path(frame['image_file'])
                else:
                    path = Path(source['image_root'])/seq/'img1'/f"{item['frame_number']:06d}.jpg"
                core.safe(path); core.require(path.is_file(), 'QA源图缺失')
                with Image.open(path) as image:
                    core.require(image.size==tuple(item['record']['image_wh']), '源图尺寸不匹配')
                    tile = render(item, image, source)
                item['image_path'] = str(path)
            else: tile = render(item, None, source)
            canvas.paste(tile, ((k%2)*570, 40+(k//2)*420))
            manifest['samples'].append(dict(sequence=seq, **{a:b for a,b in item.items() if a!='record'}))
        p = output/(seq+'_QA.jpg'); canvas.save(p, quality=94); manifest['sheets'].append(core.ref(p))
    with (output/'manifest.json').open('x', encoding='utf-8') as stream: stream.write(core.canonical(manifest)+'\n')
    return dict(status=manifest['status'], sheets=len(manifest['sheets']), selected=sum(x['available'] for x in manifest['samples']), optimizer_updates=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs', type=Path, required=True);p.add_argument('--output', type=Path, required=True)
    p.add_argument('--execute', action='store_true');a=p.parse_args()
    print(core.canonical(execute(a.inputs,a.output) if a.execute else dict(status='readonly_visual_QA_plan')))
