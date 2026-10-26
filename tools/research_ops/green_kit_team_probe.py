"""合成固定候选的队内/跨队分层Pose诊断；不等于真实追踪或关键点准确率。"""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

R = Path('D:/projects/FutsalMOT_Research/pose/green_seeded_kit_pair_a01')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(ref):
    path = Path(ref['path']); require(sha(path) == ref['sha256'], '绑定变化')
    return path


def rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def category(query, owner, label):
    if label is None:
        return 'unknown_label_retained'
    require(type(label) is int and label in (0, 1), '非法固定标签')
    if owner['state'] == 'unmatched':
        require(label == 0, '未匹配不能是正例')
        return 'unmatched_negative'
    require(owner['state'] == 'matched', '未知身份不可伪造负例')
    same = query == owner['gt_id']; require(label == int(same), '固定身份标签不同')
    if same:
        return 'same_identity_positive'
    # 原GRF实体ID的队侧约定，不按球衣颜色/图像内容猜队伍。
    a, b = re.fullmatch(r'([LR])\d+', query), re.fullmatch(r'([LR])\d+', owner['gt_id'])
    if not a or not b:
        return 'unresolved_team_negative'
    return 'same_team_negative' if a[1] == b[1] else 'cross_team_negative'


def accumulate(counter, a, b):
    counter['candidate_pair_occurrences'] += 1
    counter['A_geometry_valid_pair_occurrences'] += int(sum(a['geometry_valid'][5:]) >= 6)
    counter['B_geometry_valid_pair_occurrences'] += int(sum(b['geometry_valid'][5:]) >= 6)
    for j in range(5, 17):
        if a['geometry_valid'][j] and b['geometry_valid'][j]:
            delta = math.dist(a['xy_px'][j], b['xy_px'][j])
            counter['common_valid_limb_point_occurrences'] += 1
            counter['AB_point_delta_px_sum'] += delta
            counter['AB_point_delta_bbox_height_sum'] += delta/a['bbox_xywh_px'][3]


def summarize(counter):
    output = dict(counter); count = counter['candidate_pair_occurrences']; points = counter['common_valid_limb_point_occurrences']
    for appearance in 'AB':
        output[appearance+'_geometry_valid_fraction'] = counter[appearance+'_geometry_valid_pair_occurrences']/count if count else None
    output['AB_mean_common_point_delta_px'] = counter['AB_point_delta_px_sum']/points if points else None
    output['AB_mean_common_point_delta_bbox_height'] = counter['AB_point_delta_bbox_height_sum']/points if points else None
    return output


def execute(prediction_path, output):
    prediction = read(prediction_path)
    require(prediction['status'] == 'complete_AB_predictions_fixed_boxes_not_training_authorized', 'A/B预测未闭合')
    old = read(bound(prediction['v9_protocol'])); source_config_path = bound(old['source_config']); source_cfg = read(source_config_path)
    builder = Path(__file__).with_name('v8_pairs.py')
    spec = importlib.util.spec_from_file_location('green_team_original_matching', builder)
    matching = importlib.util.module_from_spec(spec); spec.loader.exec_module(matching)
    labels = {}
    for source in source_cfg['sources']:
        if source['domain'] != 'synthetic':
            continue
        require(source['seed'] == 1048 and source['role'] == 'train', '只分层原1048 S候选，不读dev/test')
        frames, _ = matching.load_source(source)
        labels[source['sequence']] = {i: f['labels'] for i, f in frames.items()}
    require(len(labels) == 4, '四机位来源未齐')
    original = rows(bound(prediction['historical_synthetic_pool']))
    pools = {v: rows(bound(prediction['synthetic_pools'][v]['pool'])) for v in 'AB'}
    require(len(original) == len(pools['A']) == len(pools['B']) == 1000, '窗口数不同')
    strata = defaultdict(lambda: defaultdict(float)); by_camera = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for old_w, a, b in zip(original, pools['A'], pools['B']):
        require(old_w['window_uid'] == a['window_uid'] == b['window_uid'], '窗口顺序不同')
        require(len(old_w['candidates']) == len(a['candidates']) == len(b['candidates']), '候选缺失')
        owners = labels[old_w['sequence']][old_w['candidate_frame_index']]
        for c, ca, cb in zip(old_w['candidates'], a['candidates'], b['candidates']):
            uid = c['prediction']['uid']
            require(uid == ca['prediction']['uid'] == cb['prediction']['uid'] and c['label'] == ca['label'] == cb['label'],
                    '检测或标签改变')
            kind = category(old_w['supervision']['query_gt_id'], owners[uid], c['label'])
            accumulate(strata[kind], ca['prediction'], cb['prediction'])
            accumulate(by_camera[old_w['sequence']][kind], ca['prediction'], cb['prediction'])
    require(sum(c['candidate_pair_occurrences'] for c in strata.values()) == 4791, '固定4791候选分母改变')
    storage_path = Path(__file__).resolve().parents[2]/'python/src/grf_ue_bridge/storage_policy.py'
    spec = importlib.util.spec_from_file_location('green_team_physical_storage', storage_path)
    storage = importlib.util.module_from_spec(spec); spec.loader.exec_module(storage)
    output = storage.physical_child(output, R); require(not output.exists(), '全新小诊断输出，不覆盖')
    output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(schema='green_kit_synthetic_fixed_candidate_team_pose_diagnostic_v1', status='complete',
        scope='1048 synthetic training fixed-window candidate occurrences, not heldout tracking results',
        prediction_manifest=dict(path=str(prediction_path), sha256=sha(prediction_path)),
        source_config=dict(path=str(source_config_path), sha256=sha(source_config_path)),
        matching_source=dict(path=str(builder), sha256=sha(builder)), total_candidate_pair_occurrences=4791,
        strata={k: summarize(v) for k, v in strata.items()},
        per_camera={camera: {k: summarize(v) for k, v in groups.items()} for camera, groups in by_camera.items()},
        GT_identity_bbox_used_for_stratification_only=True, GT_Pose_used=False, labels_or_training_modified=False,
        new_optimizer_updates=0, GPU_used=False, test116187_read=False,
        limitations=['geometry validity and A/B point difference are not accuracy',
                     'candidate occurrences overlap observations and are not independent players',
                     'no real tracking within-team/cross-team gain is inferred from this synthetic diagnostic'])
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prediction-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    result = execute(args.prediction_manifest, args.output) if args.execute else dict(status='readonly_team_probe_plan', GPU_used=False)
    print(json.dumps(dict(status=result['status'], strata=result.get('strata')), ensure_ascii=False))
