"""绿色A/B固定窗口的Pose替换契约；不推理、不训练、不改变框/UID/标签。

历史UID中的blue保留为逻辑对应键，不代表新图像来源；实际绿色图像和模型
来源必须由外层预测manifest登记。旧窗口池不写回，缺新预测时直接拒绝。
"""
from copy import deepcopy
import hashlib
import json
import math

POSE_FIELDS = frozenset(("xy_px", "geometry_valid"))
RECORD_FIELDS = frozenset(("uid", "bbox_xywh_px", "score", "xy_px", "geometry_valid",
                           "image_wh", "timestamp_sec"))
SEQUENCES = frozenset("S1048_blue_CineCam_%02d" % n for n in range(1, 5))


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _records(window):
    yield from window["history"]
    yield from (row["prediction"] for row in window["candidates"])


def _non_pose(windows):
    result = deepcopy(windows)
    for window in result:
        for record in _records(window):
            for key in POSE_FIELDS:
                record.pop(key, None)
    return result


def replace_synthetic_pose(windows, new_observations):
    """只替换1000个既定S窗口的两项Pose字段，返回新池及未准入的契约收据。"""
    if len(windows) != 1000 or len({w["window_uid"] for w in windows}) != 1000:
        raise ValueError("必须是原1000唯一S窗口，不能筛选或复制补预算")
    if any(w["domain"] != "synthetic" or w["game"] != "synthetic1048"
           or w["sequence"] not in SEQUENCES or w["fps"] != 10 for w in windows):
        raise ValueError("S来源越界；1102及真实/test不能进入S池")
    seen = {}; changed = set()
    for window in windows:
        if not window["history"] or not window["candidates"]:
            raise ValueError("缺历史/候选，不能跳过窗口")
        for record in _records(window):
            if set(record) != RECORD_FIELDS:
                raise ValueError("旧预测记录字段不同，拒绝猜格式")
            uid = record["uid"]
            if uid in seen and seen[uid] != record:
                raise ValueError("同一旧UID有不同观测")
            seen[uid] = deepcopy(record)
    output = deepcopy(windows)
    for window in output:
        for record in _records(window):
            uid = record["uid"]
            if uid not in new_observations:
                raise ValueError("缺新Pose预测，禁止回填旧蓝Pose：" + uid)
            new = new_observations[uid]
            if any(new.get(k) != record[k] for k in RECORD_FIELDS - POSE_FIELDS):
                raise ValueError("新预测改变固定bbox/score/时间/图像尺寸/UID：" + uid)
            xy, valid = new["xy_px"], new["geometry_valid"]
            if (not isinstance(xy, list) or not isinstance(valid, list) or len(xy) != 17 or len(valid) != 17
                    or any(type(v) is not bool for v in valid)
                    or any(not isinstance(p, list) or len(p) != 2 or
                           any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in xy)):
                raise ValueError("新Pose不是有限COCO17坐标和17个几何有效位")
            if xy != seen[uid]["xy_px"] or valid != seen[uid]["geometry_valid"]:
                changed.add(uid)
            record.update(xy_px=deepcopy(xy), geometry_valid=list(valid))
    before, after = _sha(_non_pose(windows)), _sha(_non_pose(output))
    if before != after:
        raise ValueError("Pose之外的窗口/候选/标签/运动输入改变")
    receipt = dict(schema="green_kit_fixed_S_pose_replacement_v1", runtime_authorized=False,
                   unique_windows=1000, unique_observations=len(seen), changed_pose_observations=len(changed),
                   allowed_changed_record_fields=sorted(POSE_FIELDS), non_pose_sha256=before,
                   window_UID_order_sha256=_sha([w["window_uid"] for w in windows]),
                   candidate_pairs=sum(len(w["candidates"]) for w in windows),
                   known_pairs=sum(c["label"] is not None for w in windows for c in w["candidates"]),
                   old_pool_modified=False, old_pose_fallback=False, R_input_modified=False,
                   logical_UID_namespace_preserved=True, physical_visibility="unknown")
    return output, receipt
