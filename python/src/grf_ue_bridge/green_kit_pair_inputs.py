"""绿色A/B固定窗口的Pose替换契约；不推理、不训练、不改变框/UID/标签。

历史UID中的blue保留为逻辑对应键，不代表新图像来源；实际绿色图像和模型
来源必须由外层预测manifest登记。旧窗口池不写回，缺新预测时直接拒绝。
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import PurePosixPath

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


def plan_green_frames(source, old_frames, green_group):
    """登记旧固定检测框到新绿图片的对应关系；不按检测UID推断图片序号。

    返回相对group目录的引用；外层必须在实际发布后验证文件/版本SHA，
    此函数本身不读图，不构成预测或训练准入。
    """
    if (source.get("domain") != "synthetic" or source.get("seed") != 1048
            or source.get("game") != "synthetic1048" or source.get("sequence") not in SEQUENCES
            or source.get("role") != "train" or source.get("fps") != 10
            or [source.get("first_frame"), source.get("last_frame")] != [0, 299]
            or [source.get("width"), source.get("height")] != [3840, 2160]):
        raise ValueError("旧固定检测来源不是1048四机位300帧")
    camera = source.get("camera")
    if (green_group.get("schema") != "futsalmot_pose17_green_seeded_kit_paired_group_v1"
            or green_group.get("seed") != 1048 or green_group.get("split") != "train"
            or green_group.get("variant") not in ("A", "B") or green_group.get("fps") != 10
            or green_group.get("source_frame_range") != [0, 300]
            or green_group.get("not_training") is not True or green_group.get("MRQ_sync_verified") is not False
            or set(green_group.get("cameras", {})) != {"CineCam_%02d" % n for n in range(1, 5)}
            or camera not in green_group["cameras"]):
        raise ValueError("新组不是独立绿色1048 A/B完整四机位")
    spec = green_group["cameras"][camera]
    prefix = spec.get("rgb_directory_ref", "")
    ref = PurePosixPath(prefix)
    if (not prefix or ref.is_absolute() or ".." in ref.parts or ":" in prefix or "\\" in prefix
            or spec.get("frames") != 300 or spec.get("record_layout") != "one_person_per_line"):
        raise ValueError("新绿色图像引用越界或实际帧数/布局不同")
    if len(old_frames) != 300:
        raise ValueError("旧检测源必须完整300帧")
    output = []; seen = set(); raw_signature = []
    for index, frame in enumerate(old_frames):
        if (frame.get("frame_index") != index or frame.get("frame_number") != index + 1
                or frame.get("sequence") != source["sequence"] or frame.get("sequence_id") != source["sequence"]
                or frame.get("domain") != "synthetic" or frame.get("game") != "synthetic1048"
                or frame.get("role") != "train" or frame.get("fps") != 10
                or [frame.get("width"), frame.get("height")] != [3840, 2160]
                or abs(frame.get("timestamp_sec", -1) - index / 10) > 1e-9):
            raise ValueError("源帧顺序/编号/时间改变，不按UID猜图片")
        detections = []
        for row in frame["detections"]:
            uid = row.get("uid")
            if (not isinstance(uid, str) or not uid or uid in seen or row.get("detection_id") != uid
                    or row.get("image_wh") != [3840, 2160] or row.get("timestamp_sec") != frame["timestamp_sec"]
                    or row.get("class_id") != 0):
                raise ValueError("检测UID/帧归属/尺寸/类别改变")
            seen.add(uid)
            # 仅传固定检测信息，绝不把旧蓝Pose传入新A/B推理或作缺失回填。
            detection = {key: deepcopy(row[key]) for key in
                         ("uid", "detection_id", "bbox_xywh_px", "score", "class_id")}
            detections.append(detection)
        raw_signature.append(dict(frame_index=index, frame_number=frame["frame_number"], detections=detections))
        output.append(dict(logical_sequence=source["sequence"], camera_id=camera, frame_index=index,
                           frame_number=frame["frame_number"], timestamp_sec=frame["timestamp_sec"],
                           new_image_ref=str(ref / ("%06d.png" % index)), old_image_file=frame.get("image_file"),
                           width=3840, height=2160, detections=detections))
    return output, dict(schema="green_fixed_detection_frame_correspondence_v1", runtime_authorized=False,
                        frames=300, raw_detections=len(seen), raw_detection_order_sha256=_sha(raw_signature),
                        image_index_from="explicit_frame_index_not_detection_UID", old_Pose_input_removed=True,
                        published_files_validated=False, GT_used_for_predictions=False)
