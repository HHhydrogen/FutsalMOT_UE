"""只读诊断球衣号码可见 mask 的 UE 能力和可行性门禁。

本文件的 ``build_render_contract_report`` 不依赖 Unreal，可在 P1 pytest 中验证。
UE 入口只读取当前 Editor 状态和类/API 能力；它不创建对象、不设置属性、不提交 MRQ、
不保存资产或地图。没有实际像素证据时，occlusion gate 保持 fail-closed。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Sequence


_FORMAL_MAP = "/Game/FutsalMOT/Maps/L_FutsalCourt"
_SCHEMA = "futsalmot_jersey_number_mask_diagnostic"
_VERSION = 1
_REQUIRED_LIFECYCLE_OPERATIONS = (
    "isolated_world_creation",
    "temporary_actor_cleanup",
    "stencil_mask_generation",
    "mrq_executor_terminal_callback",
    "mrq_output_cleanup",
)


def _is_true(mapping: Any, key: str) -> bool:
    return isinstance(mapping, Mapping) and mapping.get(key) is True


def _check_group(
    group_name: str,
    values: Any,
    required_keys: Sequence[str],
    errors: list,
) -> dict:
    """复制一组 JSON 数据，并要求每个门禁字段严格为 ``True``。"""
    if not isinstance(values, Mapping):
        errors.append(group_name)
        return {}
    result = dict(values)
    if any(not _is_true(values, key) for key in required_keys):
        errors.append(group_name)
    return result


def _validate_proxy_frame_readback(values: Mapping[str, Any], errors: list) -> dict:
    evidence = values.get("frame_readback")
    valid = (
        isinstance(evidence, Mapping)
        and evidence.get("probe_executed") is True
        and evidence.get("evidence_source") == "temporary_scene_capture_pixel_readback"
        and evidence.get("custom_depth_enabled") is True
        and type(evidence.get("stencil_value")) is int
        and type(evidence.get("readback_stencil_value")) is int
        and evidence.get("stencil_value") == evidence.get("readback_stencil_value")
        and type(evidence.get("stencil_pixel_count")) is int
        and evidence.get("stencil_pixel_count", 0) > 0
    )
    if not valid:
        errors.append("proxy_custom_depth_capabilities")
    return dict(evidence) if isinstance(evidence, Mapping) else {}


def _validate_synchronized_frames(values: Mapping[str, Any], errors: list) -> dict:
    evidence = values.get("synchronized_frame_evidence")
    rgb_frames = evidence.get("rgb_frame_ids") if isinstance(evidence, Mapping) else None
    mask_frames = evidence.get("mask_frame_ids") if isinstance(evidence, Mapping) else None
    valid = (
        isinstance(evidence, Mapping)
        and evidence.get("probe_executed") is True
        and evidence.get("evidence_source") == "temporary_mrq_output_files"
        and evidence.get("same_job") is True
        and isinstance(rgb_frames, list)
        and bool(rgb_frames)
        and rgb_frames == mask_frames
    )
    if not valid:
        errors.append("mrq_mask_output_capabilities")
    return dict(evidence) if isinstance(evidence, Mapping) else {}


def _validate_occlusion_evidence(values: Any, errors: list) -> dict:
    evidence = values if isinstance(values, Mapping) else {}
    counts = evidence.get("pixel_counts")
    valid_counts = (
        isinstance(counts, Mapping)
        and type(counts.get("front")) is int
        and type(counts.get("back")) is int
        and type(counts.get("occluded")) is int
        and counts.get("front", -1) == 0
        and counts.get("back", 0) > 0
        and counts.get("occluded", -1) == 0
    )
    valid = (
        evidence.get("probe_executed") is True
        and evidence.get("evidence_source") == "temporary_scene_capture_pixel_readback"
        and evidence.get("front_mask_empty") is True
        and evidence.get("back_mask_has_pixels") is True
        and evidence.get("occluded_pixels_hidden") is True
        and valid_counts
    )
    if not valid:
        errors.append("occlusion_probe")
    return dict(evidence)


def _validate_probe_lifecycle(values: Any, errors: list) -> dict:
    lifecycle = values if isinstance(values, Mapping) else {}
    result = {}
    for operation in _REQUIRED_LIFECYCLE_OPERATIONS:
        evidence = lifecycle.get(operation)
        verified = (
            isinstance(evidence, Mapping)
            and evidence.get("status") == "verified"
            and evidence.get("evidence_source") == "executed_probe"
            and isinstance(evidence.get("detail"), str)
            and bool(evidence.get("detail"))
        )
        result[operation] = dict(evidence) if isinstance(evidence, Mapping) else {
            "status": "unavailable",
            "evidence_source": "evidence_unavailable",
            "detail": "evidence unavailable",
        }
        if not verified:
            detail = result[operation].get("detail", "evidence unavailable")
            errors.append(
                "MANUAL_REQUIRED: {}: {}".format(operation, detail)
            )
    for operation, evidence in lifecycle.items():
        if operation not in result and isinstance(evidence, Mapping):
            result[operation] = dict(evidence)
    return result


def build_render_contract_report(
    current_level_path: Any,
    decal_component_capabilities: Any,
    proxy_custom_depth_capabilities: Any,
    mrq_mask_output_capabilities: Any,
    occlusion_probe: Any,
    errors: Sequence[str] = (),
    probe_lifecycle: Any = None,
) -> dict:
    """根据只读采集结果构建球衣号码 mask 可行性报告。

    API inventory 只描述可发现的类/接口，不作为帧证据。``ok`` 需要 proxy 像素
    readback、同一 MRQ job 的 RGB/mask 帧证据和带执行来源的遮挡像素计数全部通过。
    函数只返回 JSON 基础类型。
    """
    report_errors = []
    for error in errors:
        if isinstance(error, str) and error:
            report_errors.append(error)

    if current_level_path != _FORMAL_MAP:
        report_errors.append("current_level")

    decal = _check_group(
        "decal_component_capabilities",
        decal_component_capabilities,
        ("available", "back_placement", "material_parameter"),
        report_errors,
    )
    proxy_values = proxy_custom_depth_capabilities
    proxy_inventory = (
        proxy_values.get("api_inventory") if isinstance(proxy_values, Mapping) else None
    )
    proxy = _check_group(
        "proxy_custom_depth_capabilities",
        proxy_inventory,
        (
            "component_class_available",
            "custom_depth_property_api_available",
            "stencil_property_api_available",
        ),
        report_errors,
    )
    proxy["frame_readback"] = _validate_proxy_frame_readback(
        proxy_values if isinstance(proxy_values, Mapping) else {}, report_errors
    )

    mrq_values = mrq_mask_output_capabilities
    mrq_inventory = mrq_values.get("api_inventory") if isinstance(mrq_values, Mapping) else None
    mrq = _check_group(
        "mrq_mask_output_capabilities",
        mrq_inventory,
        ("mask_pass_class_available", "image_output_class_available"),
        report_errors,
    )
    mrq["synchronized_frame_evidence"] = _validate_synchronized_frames(
        mrq_values if isinstance(mrq_values, Mapping) else {}, report_errors
    )
    occlusion = _validate_occlusion_evidence(occlusion_probe, report_errors)
    lifecycle = _validate_probe_lifecycle(probe_lifecycle, report_errors)

    unique_errors = list(dict.fromkeys(report_errors))
    return {
        "schema": _SCHEMA,
        "version": _VERSION,
        "ok": not unique_errors,
        "current_level": current_level_path,
        "formal_map": _FORMAL_MAP,
        "decal_component_capabilities": decal,
        "proxy_custom_depth_capabilities": proxy,
        "mrq_mask_output_capabilities": mrq,
        "occlusion_probe": occlusion,
        "probe_lifecycle": lifecycle,
        "errors": unique_errors,
    }


def validate_v2_render_evidence(
    evidence: Any,
    number_mask_post_process_material: Any = None,
) -> dict:
    """验证 v2 MRQ 解锁所需的结构化真实证据。

    旧式 bool 和 /Game/ 路径只描述调用者的意图，不能证明当前 Editor、像素
    探针、MRQ 帧同步或材质 class。这里仅消费已经执行并序列化的证据，不访问
    Unreal，也不从路径推断资产存在性。
    """
    errors = []
    if not isinstance(evidence, Mapping):
        return {
            "ok": False,
            "errors": ["MANUAL_REQUIRED: v2 render evidence 缺失或不是对象"],
            "number_mask_post_process_material": None,
        }

    preflight = evidence.get("appearance_preflight")
    if not isinstance(preflight, Mapping):
        errors.append("MANUAL_REQUIRED: appearance_preflight evidence 缺失")
    else:
        if preflight.get("task7_preflight_can_start") is not True:
            errors.append("MANUAL_REQUIRED: task7_preflight_can_start 未验证为 true")
        if preflight.get("numbering_visual_gate") != "verified":
            errors.append("MANUAL_REQUIRED: numbering_visual_gate 未验证为 verified")

    diagnostic = evidence.get("diagnostic")
    if not isinstance(diagnostic, Mapping):
        errors.append("MANUAL_REQUIRED: jersey number diagnostic evidence 缺失")
        diagnostic = {}
    else:
        if diagnostic.get("schema") != _SCHEMA or diagnostic.get("version") != _VERSION:
            errors.append("MANUAL_REQUIRED: jersey number diagnostic schema/version 无效")
        if diagnostic.get("ok") is not True:
            errors.append("MANUAL_REQUIRED: 当前 jersey number diagnostic ok 不是 true")
        if diagnostic.get("current_level") != _FORMAL_MAP:
            errors.append("MANUAL_REQUIRED: diagnostic current_level 不是正式地图")

    _validate_proxy_frame_readback(
        diagnostic.get("proxy_custom_depth_capabilities", {}), errors
    )
    _validate_synchronized_frames(
        diagnostic.get("mrq_mask_output_capabilities", {}), errors
    )
    _validate_occlusion_evidence(diagnostic.get("occlusion_probe", {}), errors)
    _validate_probe_lifecycle(diagnostic.get("probe_lifecycle", {}), errors)

    material = evidence.get("number_mask_material")
    material_path = None
    material_valid = (
        isinstance(material, Mapping)
        and isinstance(material.get("path"), str)
        and material.get("exists") is True
        and material.get("actual_class") == "Material"
        and material.get("evidence_source") == "ue_asset_data"
    )
    if material_valid:
        material_path = material.get("path")
        if not material_path.startswith("/Game/"):
            material_valid = False
    if not material_valid:
        errors.append(
            "MANUAL_REQUIRED: number mask material 必须有 UE AssetData 的 exists=true/class=Material 证据"
        )
    elif (
        number_mask_post_process_material is not None
        and number_mask_post_process_material != material_path
    ):
        errors.append(
            "MANUAL_REQUIRED: number mask material path 与结构化 asset evidence 不一致"
        )

    return {
        "ok": not list(dict.fromkeys(errors)),
        "errors": list(dict.fromkeys(errors)),
        "number_mask_post_process_material": material_path,
    }


def _read_with_retry(
    operation: str,
    callback: Callable[[], Any],
    errors: list,
) -> Any:
    """最多重试一次只读调用；同一操作连续失败两次即标记人工门禁。"""
    failure_messages = []
    for _attempt in range(2):
        try:
            return callback()
        except Exception as exc:
            failure_messages.append("{}: {}: {}".format(operation, type(exc).__name__, exc))
    errors.extend(failure_messages)
    errors.append("MANUAL_REQUIRED: {} 连续失败两次".format(operation))
    return None


def _current_level_path(unreal_module: Any) -> Any:
    world = unreal_module.EditorLevelLibrary.get_editor_world()
    if world is None:
        return None
    path = world.get_path_name()
    return str(path).split(".", 1)[0]


def _decal_capabilities(unreal_module: Any) -> dict:
    decal_class = getattr(unreal_module, "DecalComponent", None)
    material_class = getattr(unreal_module, "MaterialInstanceDynamic", None)
    return {
        "available": decal_class is not None,
        "back_placement": bool(
            decal_class is not None
            and callable(getattr(decal_class, "set_relative_location", None))
            and callable(getattr(decal_class, "set_relative_rotation", None))
        ),
        "material_parameter": bool(
            material_class is not None
            and callable(getattr(material_class, "set_scalar_parameter_value", None))
        ),
        "component_class": getattr(decal_class, "__name__", None),
        "material_class": getattr(material_class, "__name__", None),
    }


def _level_actors(unreal_module: Any) -> list:
    subsystem_class = getattr(unreal_module, "EditorActorSubsystem", None)
    if subsystem_class is None:
        raise RuntimeError("EditorActorSubsystem 不存在")
    subsystem = unreal_module.get_editor_subsystem(subsystem_class)
    return list(subsystem.get_all_level_actors())


def _proxy_capabilities(unreal_module: Any) -> dict:
    mesh_class = getattr(unreal_module, "StaticMeshComponent", None)
    return {
        "api_inventory": {
            "component_class_available": mesh_class is not None,
            "custom_depth_property_api_available": bool(
                mesh_class is not None
                and callable(getattr(mesh_class, "get_editor_property", None))
            ),
            "stencil_property_api_available": bool(
                mesh_class is not None
                and callable(getattr(mesh_class, "get_editor_property", None))
            ),
            "expected_editor_properties": [
                "render_custom_depth",
                "custom_depth_stencil_value",
            ],
        },
        "frame_readback": {
            "probe_executed": False,
            "evidence_source": "evidence_unavailable",
            "blocker": "未在 disposable test world 中执行 Custom Depth/Stencil 帧读取",
        },
    }


def _mrq_capabilities(unreal_module: Any) -> dict:
    object_id_class = getattr(unreal_module, "MoviePipelineObjectIdRenderPass", None)
    post_process_class = getattr(unreal_module, "MoviePipelinePostProcessPass", None)
    exr_class = getattr(unreal_module, "MoviePipelineImageSequenceOutput_EXR", None)
    png_class = getattr(unreal_module, "MoviePipelineImageSequenceOutput_PNG", None)
    return {
        "api_inventory": {
            "mask_pass_class_available": (
                object_id_class is not None or post_process_class is not None
            ),
            "image_output_class_available": png_class is not None or exr_class is not None,
            "object_id_pass_class": object_id_class is not None,
            "post_process_pass_class": post_process_class is not None,
            "exr_output_class": exr_class is not None,
            "png_output_class": png_class is not None,
        },
        "synchronized_frame_evidence": {
            "probe_executed": False,
            "evidence_source": "evidence_unavailable",
            "same_job": False,
            "rgb_frame_ids": [],
            "mask_frame_ids": [],
            "blocker": "未在 disposable test world 中生成并配对检查 MRQ RGB/mask 帧",
        },
    }


def _probe_lifecycle(unreal_module: Any) -> dict:
    """记录隔离、捕获、MRQ 完成和清理能力的实际证据状态。"""
    actor_subsystem = getattr(unreal_module, "EditorActorSubsystem", None)
    world_class = getattr(unreal_module, "World", None)
    scene_capture_source = getattr(unreal_module, "SceneCaptureSource", None)
    render_library = getattr(unreal_module, "RenderingLibrary", None)
    queue_class = getattr(unreal_module, "MoviePipelineQueue", None)
    executor_class = getattr(unreal_module, "MoviePipelinePIEExecutor", None)
    asset_library = getattr(unreal_module, "EditorAssetLibrary", None)
    stencil_material_exists = False
    stencil_material_path = "/Game/FutsalMOT/Materials/M_StencilToID"
    if asset_library is not None:
        does_exist = getattr(asset_library, "does_asset_exist", None)
        if callable(does_exist):
            stencil_material_exists = bool(does_exist(stencil_material_path))

    world_members = set(dir(world_class)) if world_class is not None else set()
    subsystem_spawn = bool(
        actor_subsystem is not None
        and callable(getattr(actor_subsystem, "spawn_actor_from_class", None))
    )
    subsystem_destroy = bool(
        actor_subsystem is not None
        and callable(getattr(actor_subsystem, "destroy_actor", None))
    )
    capture_available = bool(
        getattr(unreal_module, "SceneCaptureComponent2D", None) is not None
        and callable(
            getattr(
                getattr(unreal_module, "SceneCaptureComponent2D", None),
                "capture_scene",
                None,
            )
        )
        and render_library is not None
        and callable(getattr(render_library, "read_render_target", None))
    )
    custom_stencil_capture_source = bool(
        scene_capture_source is not None
        and any("STENCIL" in name.upper() for name in dir(scene_capture_source))
    )
    queue_cleanup_api = bool(
        queue_class is not None
        and callable(getattr(queue_class, "delete_job", None))
        and callable(getattr(queue_class, "delete_all_jobs", None))
    )
    executor_members = set(dir(executor_class)) if executor_class is not None else set()
    terminal_delegates = {
        "on_executor_finished_delegate",
        "on_executor_errored_delegate",
    }.issubset(executor_members)

    return {
        "isolated_world_creation": {
            "status": "unavailable",
            "evidence_source": "api_inventory",
            "detail": (
                "World 无 spawn/create_world API；EditorActorSubsystem.spawn_actor_from_class "
                "的文档明确目标是 current level，不能隔离到 disposable world"
            ),
            "world_has_spawn_api": any("spawn" in name.lower() for name in world_members),
            "editor_subsystem_spawn_targets_current_level": subsystem_spawn,
        },
        "temporary_actor_cleanup": {
            "status": "available_unverified" if subsystem_destroy else "unavailable",
            "evidence_source": "api_inventory",
            "detail": (
                "destroy_actor 存在，但没有创建隔离 Actor；未验证可在不修改 formal map 的 world 中清理"
                if subsystem_destroy
                else "EditorActorSubsystem.destroy_actor 不可用"
            ),
            "destroy_api_available": subsystem_destroy,
            "spawn_api_available": subsystem_spawn,
        },
        "stencil_mask_generation": {
            "status": "unavailable",
            "evidence_source": "api_inventory",
            "detail": "实际 stencil 像素未读取；stencil-to-ID material 不存在，SceneCaptureSource 无 stencil source",
            "stencil_material_path": stencil_material_path,
            "stencil_material_exists": stencil_material_exists,
            "scene_capture_source_has_stencil": custom_stencil_capture_source,
            "scene_capture_rgb_readback_api_available": capture_available,
        },
        "mrq_executor_terminal_callback": {
            "status": "available_unverified" if terminal_delegates else "unavailable",
            "evidence_source": "api_inventory",
            "detail": (
                "terminal delegates are exposed, but no MRQ job was run to verify callback completion"
                if terminal_delegates
                else "required executor terminal delegates are unavailable"
            ),
            "terminal_delegates_available": terminal_delegates,
        },
        "mrq_output_cleanup": {
            "status": "available_unverified" if queue_cleanup_api else "unavailable",
            "evidence_source": "api_inventory",
            "detail": (
                "queue delete APIs exist, but no completed MRQ output was created and removed; "
                "filesystem output cleanup is unverified"
                if queue_cleanup_api
                else "MRQ queue delete APIs are unavailable"
            ),
            "queue_cleanup_api_available": queue_cleanup_api,
            "output_cleanup_executed": False,
        },
    }


def _collect_report(unreal_module: Any) -> dict:
    errors = []
    current_level = _read_with_retry(
        "current_level", lambda: _current_level_path(unreal_module), errors
    )
    decal = _read_with_retry(
        "decal_component_capabilities",
        lambda: _decal_capabilities(unreal_module),
        errors,
    )
    proxy = _read_with_retry(
        "proxy_custom_depth_capabilities",
        lambda: _proxy_capabilities(unreal_module),
        errors,
    )
    mrq = _read_with_retry(
        "mrq_mask_output_capabilities", lambda: _mrq_capabilities(unreal_module), errors
    )
    lifecycle = _read_with_retry(
        "probe_lifecycle", lambda: _probe_lifecycle(unreal_module), errors
    )

    # Editor spawn API 明确写入 current level；因此不在 formal map 上尝试临时 Actor。
    occlusion = {
        "front_mask_empty": False,
        "back_mask_has_pixels": False,
        "occluded_pixels_hidden": False,
        "probe_executed": False,
        "evidence_source": "evidence_unavailable",
        "pixel_counts": None,
        "blocker": (
            "EditorActorSubsystem.spawn_actor_from_class 目标为 current level，"
            "且当前没有已验证的 disposable world"
        ),
    }
    errors.append(
        "MANUAL_REQUIRED: disposable world 创建、stencil mask 生成和 MRQ 输出清理操作未验证"
    )

    return build_render_contract_report(
        current_level,
        decal or {},
        proxy or {},
        mrq or {},
        occlusion,
        errors=errors,
        probe_lifecycle=lifecycle or {},
    )


def main() -> dict:
    """在 Unreal Editor 中运行只读诊断并输出结构化 JSON。"""
    try:
        import unreal
    except Exception as exc:
        report = build_render_contract_report(
            None,
            {},
            {},
            {},
            {},
            errors=["unreal_import: {}: {}".format(type(exc).__name__, exc)],
        )
    else:
        try:
            report = _collect_report(unreal)
        except Exception as exc:
            report = build_render_contract_report(
                None,
                {},
                {},
                {},
                {},
                errors=["probe: {}: {}".format(type(exc).__name__, exc)],
            )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return report


if __name__ == "__main__":
    main()
