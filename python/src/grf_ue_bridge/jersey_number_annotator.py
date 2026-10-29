"""从球衣号码 mask 生成 v2 annotations.jsonl 中的号码 bbox。"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UE_DIR = _REPO_ROOT / "ue"
if str(_UE_DIR) not in sys.path:
    sys.path.insert(0, str(_UE_DIR))

from dataset_export import write_jsonl_atomic  # noqa: E402
from instance_mask import compute_instance_stats, load_mask_array  # noqa: E402

ENTITY_IDS = tuple(
    [f"L{index}" for index in range(5)]
    + [f"R{index}" for index in range(5)]
)
APPEARANCE_POLICY_V2 = "futsalmot_appearance_v2"
MASK_STENCIL_START = 32


def _empty_number(value: int) -> Dict[str, Any]:
    return {
        "value": value,
        "placement": "back",
        "bbox_source": "visible_number_mask",
        "in_frame": False,
        "truncated": False,
        "visible_pixel_count": 0,
        "bbox_xyxy": None,
        "bbox_xywh": None,
    }


def _number_from_stats(value: int, bbox: Tuple[int, int, int, int], count: int) -> Dict[str, Any]:
    xmin, ymin, xmax, ymax = (float(value) for value in bbox)
    return {
        "value": value,
        "placement": "back",
        "bbox_source": "visible_number_mask",
        "in_frame": True,
        "truncated": False,
        "visible_pixel_count": count,
        "bbox_xyxy": [xmin, ymin, xmax, ymax],
        "bbox_xywh": [xmin, ymin, xmax - xmin, ymax - ymin],
    }


def _validate_manifest(manifest: Mapping[str, Any]) -> Tuple[Dict[str, int], List[str]]:
    errors: List[str] = []
    if manifest.get("schema") == "futsalmot_episode_uv_numbers_v1":
        from jersey_number_uv_contract import canonical_fingerprint, assign_numbers
        payload = dict(manifest)
        fingerprint = payload.pop("fingerprint", None)
        if fingerprint != canonical_fingerprint(payload):
            return {}, ["UV号码清单fingerprint不匹配"]
        expected = assign_numbers(manifest["ue_visual_seed"])
        rows = manifest.get("entities", [])
        if [row.get("entity_id") for row in rows] != list(ENTITY_IDS):
            return {}, ["UV号码清单十人顺序不完整"]
        for i, row in enumerate(rows):
            if row.get("jersey_number") != expected[row["entity_id"]] or row.get("number_mask_id") != 32 + i:
                errors.append("UV号码清单号码/ID不匹配: " + row["entity_id"])
        return expected, errors
    if not isinstance(manifest, Mapping):
        return {}, ["球衣号码 manifest 必须是对象"]
    if manifest.get("policy") != APPEARANCE_POLICY_V2:
        return {}, ["球衣号码标注要求 appearance v2 manifest"]
    if manifest.get("schema") != "futsalmot_episode_appearance":
        errors.append("球衣号码 manifest schema 无效")
    if type(manifest.get("version")) is not int or manifest.get("version") != 2:
        errors.append("球衣号码 manifest version 必须为 2")
    numbering = manifest.get("numbering")
    if (
        not isinstance(numbering, Mapping)
        or type(numbering.get("mask_stencil_start")) is not int
        or numbering.get("mask_stencil_start") != MASK_STENCIL_START
    ):
        errors.append("球衣号码 manifest numbering.mask_stencil_start 必须为 32")

    entities = manifest.get("entities")
    values: Dict[str, int] = {}
    if not isinstance(entities, list) or len(entities) != len(ENTITY_IDS):
        errors.append("球衣号码 manifest entities 必须完整包含十名球员")
        return values, errors
    for index, expected_id in enumerate(ENTITY_IDS):
        entity = entities[index]
        if not isinstance(entity, Mapping) or entity.get("entity_id") != expected_id:
            errors.append("球衣号码 manifest entities 必须按固定 L0..L4,R0..R4 顺序排列")
            continue
        value = entity.get("jersey_number")
        if type(value) is not int or not 1 <= value <= 99:
            errors.append(f"manifest {expected_id}.jersey_number 必须是 1..99 整数")
            continue
        values[expected_id] = value
    if len(values) == len(ENTITY_IDS) and len(set(values.values())) != len(ENTITY_IDS):
        errors.append("manifest jersey_number 必须互不重复")
    return values, list(dict.fromkeys(errors))


def _read_annotation_frames(camera: Path) -> List[dict]:
    path = camera / "annotations.jsonl"
    if not path.is_file():
        raise ValueError(f"{camera.name} 缺少 annotations.jsonl")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _camera_size(camera: Path) -> Tuple[int, int]:
    data = json.loads((camera / "camera.json").read_text(encoding="utf-8"))
    width = int(data.get("image_width", 0) or data.get("intrinsics", {}).get("width", 0))
    height = int(data.get("image_height", 0) or data.get("intrinsics", {}).get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError(f"{camera.name} camera.json 图像尺寸非法")
    return width, height


def _annotate_camera(camera: Path, numbers: Mapping[str, int]) -> List[dict]:
    width, height = _camera_size(camera)
    frames = _read_annotation_frames(camera)
    mask_dir = camera / "number_mask"
    if not mask_dir.is_dir():
        raise ValueError(f"{camera.name} 缺少 number_mask/")

    annotated: List[dict] = []
    valid_mask_ids = set(range(MASK_STENCIL_START, MASK_STENCIL_START + len(ENTITY_IDS)))
    for frame in frames:
        frame_index = int(frame.get("frame_index", 0))
        mask_path = mask_dir / f"{frame_index:06d}.png"
        if not mask_path.is_file():
            raise ValueError(f"{camera.name} 缺少号码 mask: {mask_path.name}")
        mask = load_mask_array(mask_path, "r")
        if tuple(mask.shape) != (height, width):
            raise ValueError(
                f"{camera.name} frame {frame_index} 号码 mask 分辨率 {mask.shape[1]}x{mask.shape[0]} "
                f"与 camera.json {width}x{height} 不一致"
            )
        nonzero_ids = {int(value) for value in set(mask[mask != 0].tolist())}
        invalid_ids = sorted(nonzero_ids - valid_mask_ids)
        if invalid_ids:
            raise ValueError(
                f"{camera.name} frame {frame_index} 号码 mask 含非法 mask ID: {invalid_ids}"
            )

        stats = compute_instance_stats(mask, max_mask_id=MASK_STENCIL_START + len(ENTITY_IDS) - 1)
        by_id = {}
        for index, entity_id in enumerate(ENTITY_IDS):
            mask_id = MASK_STENCIL_START + index
            instance = stats.get(mask_id)
            by_id[entity_id] = _empty_number(numbers[entity_id]) if instance is None else (
                _number_from_stats(numbers[entity_id], instance.bbox_xyxy, instance.pixel_count)
            )

        updated = copy.deepcopy(frame)
        for obj in updated.get("objects", []):
            entity_id = obj.get("entity_id")
            if entity_id in by_id:
                number = by_id[entity_id]
                if updated.get("schema") == "futsalmot_frame_annotation":
                    obj.update(jersey_number=number["value"],
                               number_mask_id=MASK_STENCIL_START + ENTITY_IDS.index(entity_id),
                               jersey_number_visible=number["visible_pixel_count"] > 0,
                               jersey_number_bbox_xyxy=number["bbox_xyxy"])
                    obj.setdefault("jersey_number_readable", False)
                    obj.setdefault("jersey_number_view", "unknown")
                else:
                    obj["jersey_number"] = number
        annotated.append(updated)
    return annotated


def annotate_jersey_number_masks(
    episode_dir: Path,
    *,
    manifest: Mapping[str, Any],
    cameras: Sequence[Path],
) -> List[str]:
    """按号码 mask 可见像素更新 v2 annotations.jsonl，返回结构化错误列表。"""
    del episode_dir
    if not isinstance(manifest, Mapping):
        return ["球衣号码 manifest 必须是对象"]
    numbers, errors = _validate_manifest(manifest)
    if errors:
        return errors
    if not cameras:
        return ["appearance v2 球衣号码标注没有 camera 目录"]

    prepared: List[Tuple[Path, List[dict]]] = []
    for camera in cameras:
        try:
            prepared.append((Path(camera), _annotate_camera(Path(camera), numbers)))
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OverflowError,
            json.JSONDecodeError,
        ) as exc:
            errors.append(f"{Path(camera).name}: {exc}")
    if errors:
        return errors

    for camera, frames in prepared:
        try:
            write_jsonl_atomic(camera / "annotations.jsonl", frames)
        except OSError as exc:
            errors.append(f"{camera.name}: annotations.jsonl 原子写入失败: {exc}")
            break
    return errors
