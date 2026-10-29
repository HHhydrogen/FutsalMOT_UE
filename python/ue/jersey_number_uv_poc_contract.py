"""冻结姿态号码近景 PoC 的纯数据契约；不替代正式 MRQ 验收。"""

from __future__ import annotations

import math

CASES = ("back", "front", "partial_occlusion", "full_occlusion", "behind_occluder")


def validate_poc_config(record):
    """在任何 UE 修改前拒绝缺项、非有限坐标及过大的短诊断任务。"""
    from jersey_number_uv_contract import material_parameters

    if not isinstance(record, dict):
        raise ValueError("PoC 配置必须是 JSON 对象")
    if record.get("entity_id") not in ("L0", "L1", "L2", "L3", "L4", "R0", "R1", "R2", "R3", "R4"):
        raise ValueError("entity_id 不属于固定 roster")
    if type(record.get("ue_visual_seed")) is not int or not 0 <= record["ue_visual_seed"] <= 0x7fffffff:
        raise ValueError("ue_visual_seed 必须为 0..2^31-1 整数")
    variant = record.get("beauty_variant", "number_uv")
    if variant not in ("number_uv", "source_control"):
        raise ValueError("beauty_variant 必须为 number_uv 或 source_control")
    for key in ("translation_cm", "back_axis_local", "target_local_cm"):
        value = record.get(key)
        if not isinstance(value, list) or len(value) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
            raise ValueError(key + " 必须含三个有限数值")
    axis = record["back_axis_local"]
    if abs(axis[2]) > 0.0001 or abs(sum(x*x for x in axis) - 1) > 0.0001:
        raise ValueError("back_axis_local 必须为水平单位向量；方向仍需 UE 视觉核对")
    for key in ("width", "height"):
        if type(record.get(key)) is not int or not 64 <= record[key] <= 2048:
            raise ValueError(key + " 必须为 64..2048 整数")
    for key, minimum, maximum in (("horizontal_fov", 5, 120), ("distance_cm", 100, 500)):
        value = record.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(key + " 超出近景诊断范围")
    material_parameters(37, record["entity_id"], record.get("ue_uv_rect"),
                        flip_u=record.get("flip_u"), flip_v=record.get("flip_v"))
    return dict(record, beauty_variant=variant)


def evaluate_poc_pixels(record):
    """只评价程序化捕获/像素门槛；美观、方向、动作和 MRQ 证据仍需单独验证。"""
    errors = []
    cases = record.get("cases", {})
    if set(cases) != set(CASES):
        errors.append("近景 case 集合不完整")
    if record.get("source_unchanged") is not True or record.get("restore_verified") is not True:
        errors.append("生产源状态或临时对象恢复未通过")
    for name in CASES:
        case = cases.get(name, {})
        if case.get("same_game_frame") is not True or type(case.get("engine_frame")) is not int:
            errors.append(name + " 缺少同一游戏帧双捕获证据")
        if case.get("rgb_dimensions") != case.get("mask_dimensions") or not case.get("rgb_dimensions"):
            errors.append(name + " RGB/mask 尺寸不一致")
        if case.get("unexpected_color_pixels") != 0:
            errors.append(name + " mask 含非零/实体 ID 以外的颜色")
        if type(case.get("number_pixels")) is not int or case.get("number_pixels", -1) < 0:
            errors.append(name + " 缺少像素统计")
    back = cases.get("back", {}).get("number_pixels", 0)
    partial = cases.get("partial_occlusion", {}).get("number_pixels", 0)
    if back < 64:
        errors.append("背面有效号码像素少于 64")
    if not 0 < partial < back:
        errors.append("部分遮挡未保留较少的可见号码像素")
    if cases.get("front", {}).get("number_pixels") != 0:
        errors.append("正面号码未完全消失")
    if cases.get("full_occlusion", {}).get("number_pixels") != 0:
        errors.append("完整遮挡时号码未完全消失")
    if cases.get("behind_occluder", {}).get("number_pixels") != back:
        errors.append("位于号码之后的遮挡物改变了可见号码")
    return errors
