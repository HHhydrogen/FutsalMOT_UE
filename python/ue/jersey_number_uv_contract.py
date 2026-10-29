"""球衣 UV 号码原型的无引擎依赖契约，可在 P1/P2 分别读取。"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Mapping, Sequence, Tuple

UV_NUMBER_POLICY = "futsalmot_jersey_number_uv_v1"
# 用户2026-10-29确认15%放大尺寸，并要求背部中心稍下移。
DEFAULT_PRINT_PROFILE = "back_size115_down002_v1"
DEFAULT_UV_RECT = [0.14425, 0.205, 0.38575, 0.435]
ASSIGNMENT_POLICY = "futsalmot_appearance_v2"
ENTITY_IDS = tuple(["L{}".format(i) for i in range(5)] + ["R{}".format(i) for i in range(5)])
ATLAS_GRID = (16, 8)
SOURCE_JERSEY_UV_TOPOLOGY = "60d2f8d204b7cd8aec2a94775e9b6a584000e18a19ce8d122e7c0ab54675bf58"
MATERIAL_SCALARS = ("NumberIndex", "NumberEnabled", "NumberMaskMode", "NumberMaskID")
MATERIAL_VECTORS = ("NumberUVRect", "NumberUVTransform", "NumberInkColor")
MATERIAL_TEXTURES = ("NumberAtlas",)


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("{} 必须为 {}..{} 整数".format(name, minimum, maximum))
    return value


def assign_numbers(ue_visual_seed: int) -> Dict[str, int]:
    """沿用既有 v2 字节协议，仅复用号码分配，不启用 v2 贴花 apply。"""
    seed = _integer(ue_visual_seed, "ue_visual_seed", 0, 0x7fffffff)
    payload = "{}:{}:jersey_number".format(ASSIGNMENT_POLICY, seed)
    namespace = int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:4], "big") & 0x7fffffff
    assigned = {}
    used = set()
    for entity_id in ENTITY_IDS:
        def rank(number):
            text = "{}:rank:jersey_number:{}:{}:{}".format(ASSIGNMENT_POLICY, namespace, entity_id, number)
            return hashlib.sha256(text.encode("utf-8")).digest(), str(number)
        selected = next(number for number in sorted(range(1, 100), key=rank) if number not in used)
        assigned[entity_id] = selected
        used.add(selected)
    return assigned


def atlas_cell(number: int) -> Tuple[int, int]:
    """1..99 按从左到右、从上到下排列；16×8 支持二次幂图集尺寸。"""
    index = _integer(number, "number", 1, 99) - 1
    return index % ATLAS_GRID[0], index // ATLAS_GRID[0]


def validate_uv_rect(rect: Sequence[float]) -> Tuple[float, float, float, float]:
    """校验已在当前 UE Mesh 上校准的局部矩形，顺序为 u0,v0,u1,v1。"""
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        raise ValueError("NumberUVRect 必须含四个数值")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in rect):
        raise ValueError("NumberUVRect 必须是有限数值，不能使用 bool")
    u0, v0, u1, v1 = map(float, rect)
    if not 0 <= u0 < u1 <= 1 or not 0 <= v0 < v1 <= 1:
        raise ValueError("NumberUVRect 必须位于 0..1 且具有正宽高")
    return u0, v0, u1, v1


def map_uv_to_atlas(
    uv: Sequence[float], number: int, rect: Sequence[float],
    *, flip_u: bool = False, flip_v: bool = False,
) -> Tuple[float, float, bool]:
    """返回图集 UV 和矩形内标志；矩形外必须乘零，不能重复采样到前片。"""
    u0, v0, u1, v1 = validate_uv_rect(rect)
    if len(uv) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in uv):
        raise ValueError("uv 必须是两个有限数值")
    if type(flip_u) is not bool or type(flip_v) is not bool:
        raise ValueError("UV flip 标志必须是 bool")
    u, v = float(uv[0]), float(uv[1])
    local_u = (u - u0) / (u1 - u0)
    local_v = (v - v0) / (v1 - v0)
    inside = 0 <= local_u <= 1 and 0 <= local_v <= 1
    local_u = min(1.0, max(0.0, local_u))
    local_v = min(1.0, max(0.0, local_v))
    if flip_u:
        local_u = 1.0 - local_u
    if flip_v:
        local_v = 1.0 - local_v
    column, row = atlas_cell(number)
    return (column + local_u) / ATLAS_GRID[0], (row + local_v) / ATLAS_GRID[1], inside


def material_parameters(
    number: int, entity_id: str, rect: Sequence[float],
    *, flip_u: bool = False, flip_v: bool = False,
    ink_color: Sequence[float] = (1.0, 1.0, 1.0), mask_mode: bool = False,
) -> dict:
    """生成参数化球衣材质的确定性输入；不创建、修改或保存任何 UE 对象。"""
    atlas_cell(number)
    uv_rect = validate_uv_rect(rect)
    if entity_id not in ENTITY_IDS:
        raise ValueError("entity_id 必须属于固定十人 roster")
    if type(flip_u) is not bool or type(flip_v) is not bool or type(mask_mode) is not bool:
        raise ValueError("flip 与 mask_mode 必须是 bool")
    if len(ink_color) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in ink_color):
        raise ValueError("ink_color 必须含三个 0..1 有限数值")
    return {
        "NumberIndex": number - 1,
        "NumberEnabled": 1.0,
        "NumberMaskMode": float(mask_mode),
        "NumberMaskID": 32 + ENTITY_IDS.index(entity_id),
        "NumberUVRect": list(uv_rect),
        "NumberUVTransform": [float(flip_u), float(flip_v), 0.0, 0.0],
        "NumberInkColor": [float(x) for x in ink_color] + [1.0],
    }


def canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    """将图集、位置校准和版本信息绑定到同一稳定摘要。"""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_calibration(record: Mapping[str, Any]) -> list:
    """只有 UE 近景和 mask 遮挡验收证据齐全，才能批准进入正式渲染。"""
    errors = []
    if not isinstance(record, Mapping):
        return ["UV calibration 必须是对象"]
    try:
        validate_uv_rect(record.get("ue_uv_rect"))
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    for key in ("ue_mesh_uv_verified", "back_visible_verified", "front_empty_verified",
                "animation_verified", "occlusion_verified", "paired_mask_verified"):
        if record.get(key) is not True:
            errors.append("缺少 {} 验收".format(key))
    if record.get("source_uv_topology_sha256") != SOURCE_JERSEY_UV_TOPOLOGY:
        errors.append("源球衣 UV topology 摘要不匹配")
    for key in ("mesh", "camera", "sequence", "evidence_rgb", "evidence_number_mask"):
        if not isinstance(record.get(key), str) or not record[key]:
            errors.append("缺少 {} 证据定位".format(key))
    if type(record.get("frame_index")) is not int or record["frame_index"] < 1:
        errors.append("frame_index 必须为正整数")
    return errors
