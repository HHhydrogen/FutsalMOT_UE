"""隔离且可撤销的冻结姿态号码近景捕获；默认只读，不改生产球员。"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from grf_ue_bridge.storage_policy import require_render_destination, record_test_render
from jersey_number_uv_build_mask_preview import MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH
from jersey_number_uv_build_preview import MATERIAL_PATH, TEXTURE_PATH
from jersey_number_uv_contract import UV_NUMBER_POLICY, assign_numbers
from jersey_number_uv_poc_contract import CASES, validate_poc_config


def _preview_actors(unreal):
    return [actor.get_path_name() for actor in unreal.EditorLevelLibrary.get_all_level_actors()
            if "FutsalMOTNumberUVTransientStage" in [str(tag) for tag in actor.get_editor_property("tags")]]


def _object_path(obj):
    return obj.get_path_name() if obj is not None else None


def _snapshot(mesh):
    """生产源只读快照，后续不得通过清除 dirty flag 掩盖差异。"""
    location, rotation, scale = mesh.get_world_location(), mesh.get_world_rotation(), mesh.get_world_scale()
    return {
        "component": mesh.get_path_name(), "mesh": _object_path(mesh.get_skeletal_mesh_asset()),
        "location": [location.x, location.y, location.z],
        "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
        "scale": [scale.x, scale.y, scale.z],
        "materials": [_object_path(mesh.get_material(i)) for i in range(mesh.get_num_materials())],
        "render_custom_depth": bool(mesh.get_editor_property("render_custom_depth")),
        "custom_depth_stencil_value": int(mesh.get_editor_property("custom_depth_stencil_value")),
    }


def _result(value, name):
    """新反射 API 的预期返回对象和 OutError；结构不符时立即停止。"""
    if not isinstance(value, tuple) or len(value) != 2:
        raise RuntimeError("MANUAL_REQUIRED: {} 反射返回结构未验证: {!r}".format(name, value))
    result, error = value
    if not result or error:
        raise RuntimeError("{}: {}".format(name, error))
    return result


def _bool_result(value, name):
    """PyGenUtil 会去掉 bool return：成功只返回 OutError，失败返回 None。"""
    if value != "":
        raise RuntimeError("{} 失败或反射结构不符: {!r}".format(name, value))


def _capture_result(value):
    """bool + int64& + FString& 在 Python 中为 (frame,error) 或 None。"""
    if not isinstance(value, tuple) or len(value) != 2:
        raise RuntimeError("MANUAL_REQUIRED: capture 失败或反射返回结构不符: {!r}".format(value))
    frame, error = value
    if type(frame) is not int or frame < 0 or error != "":
        raise RuntimeError("capture 返回无效帧或错误: {!r}".format(value))
    return frame


def main():
    import unreal
    import diagnose_episode_appearance as appearance_diagnostic
    from diagnose_episode_environment import _runtime_state

    config_path = os.environ.get("FUTSALMOT_JERSEY_UV_POC_CONFIG")
    assert config_path, "必须指定 FUTSALMOT_JERSEY_UV_POC_CONFIG，禁止凭默认坐标直接渲染"
    config = validate_poc_config(json.loads(Path(config_path).read_text(encoding="utf-8")))
    mapping = json.loads(Path(__file__).with_name("actor_mapping.example.json").read_text(encoding="utf-8"))
    gate = appearance_diagnostic.collect_diagnostic(unreal, mapping)
    runtime, runtime_errors = _runtime_state(unreal)
    assert gate["task7_preflight_can_start"] and not gate["dirty_package_paths"], gate
    assert not runtime_errors and runtime["play_session_active"] is False and runtime["mrq_state"] == "inactive", runtime
    assert not _preview_actors(unreal), "MANUAL_REQUIRED: 已有未恢复的临时号码测试 Actor"
    library = getattr(unreal, "JerseyNumberUVLibrary", None)
    methods = ("create_number_material", "create_number_mask_follower", "destroy_number_mask_follower",
               "create_number_preview_mesh", "create_number_preview_occluder", "capture_number_preview_pair",
               "destroy_number_preview_mesh")
    reflection = {name: callable(getattr(library, name, None)) for name in methods}
    assets = {path: unreal.EditorAssetLibrary.does_asset_exist(path)
              for path in (MATERIAL_PATH, TEXTURE_PATH, MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH)}
    apply = os.environ.get("FUTSALMOT_JERSEY_UV_POC_APPLY") == "1"
    plan = {"policy": UV_NUMBER_POLICY, "apply": apply, "config": config, "reflection": reflection,
            "assets": assets, "production_enabled": False, "capture_kind": "frozen_pose_scene_capture",
            "sequence_mrq_synchronization_verified": False, "visual_acceptance": False}
    if not apply:
        print("JERSEY_UV_POC_PLAN " + json.dumps(plan, ensure_ascii=False))
        return
    assert all(reflection.values()), "MANUAL_REQUIRED: 先编译并验证全部新增 C++ 反射接口"
    assert all(assets.values()), "独立 mask 材质尚未构建/回读"
    actors = [a for a in unreal.EditorLevelLibrary.get_all_level_actors()
              if a.get_actor_label() == mapping[config["entity_id"]]]
    assert len(actors) == 1
    sources = [c for c in actors[0].get_components_by_class(unreal.SkeletalMeshComponent)
               if [str(n) for n in c.get_material_slot_names()].count("材质") == 1]
    assert len(sources) == 1, "实际外观网格不唯一，拒绝选取第一个 SkeletalMeshComponent"
    source = sources[0]
    before = _snapshot(source)
    source_transform = unreal.Transform(location=source.get_world_location(), rotation=source.get_world_rotation(),
                                        scale=source.get_world_scale())
    location = source.get_world_location() + unreal.Vector(*config["translation_cm"])
    transform = unreal.Transform(location=location, rotation=source.get_world_rotation(), scale=source.get_world_scale())
    target = unreal.MathLibrary.transform_location(transform, unreal.Vector(*config["target_local_cm"]))
    back_axis = unreal.MathLibrary.transform_direction(source_transform, unreal.Vector(*config["back_axis_local"]))
    # 由水平单位背向量产生屏幕右向量；所有几何均为临时克隆，不改变源球员位置。
    right_axis = unreal.Vector(-back_axis.y, back_axis.x, 0.0)
    number = assign_numbers(config["ue_visual_seed"])[config["entity_id"]]
    parameters = unreal.JerseyNumberUVParameters()
    parameters.set_editor_property("number", number)
    parameters.set_editor_property("entity_mask_id", 32 + tuple(mapping).index(config["entity_id"]))
    parameters.set_editor_property("uv_rect", unreal.LinearColor(*config["ue_uv_rect"]))
    parameters.set_editor_property("ink_color", unreal.LinearColor(1, 1, 1, 1))
    parameters.set_editor_property("flip_u", config["flip_u"])
    parameters.set_editor_property("flip_v", config["flip_v"])
    atlas = unreal.load_asset(TEXTURE_PATH)
    # UObject 为抽象类；读取已存在的 transient package，不构造临时 UObject。
    outer = unreal.find_package("/Engine/Transient")
    assert outer is not None, "MANUAL_REQUIRED: transient package 不可访问"
    if config["beauty_variant"] == "source_control":
        # 只改变临时克隆的球衣母材质，姿态、相机及 mask 继续复用同一条路径。
        jersey_index = [str(slot) for slot in source.get_material_slot_names()].index("材质")
        beauty = source.get_material(jersey_index)
        assert beauty is not None, "源球衣材质不存在，不能进行对照"
    else:
        beauty = _result(library.create_number_material(unreal.load_asset(MATERIAL_PATH), atlas, outer, parameters), "beauty MID")
    masked = _result(library.create_number_material(unreal.load_asset(MASKED_PATH), atlas, outer, parameters), "mask MID")
    empty = unreal.load_asset(EMPTY_PATH)
    post = unreal.load_asset(POST_PROCESS_PATH)
    cube = unreal.load_asset("/Engine/BasicShapes/Cube")
    assert cube is not None
    root = Path("G:/FutsalMOT_Dataset/test")
    output = require_render_destination(root / ("number_uv_poc_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")) / "raw")
    output.mkdir(parents=True, exist_ok=False)
    record_test_render(output, "rendering")
    report = dict(plan, number=number, mask_id=32 + tuple(mapping).index(config["entity_id"]), source_before=before,
                  cases={}, restore_verified=False, source_unchanged=False, output_dir=str(output))
    preview = follower = None
    try:
        preview = _result(library.create_number_preview_mesh(source, beauty, transform), "创建临时球员")
        follower = _result(library.create_number_mask_follower(preview, masked, empty, report["mask_id"]), "创建蒙皮号码代理")
        back_camera = target + back_axis * config["distance_cm"]
        back_rotation = unreal.MathLibrary.find_look_at_rotation(back_camera, target)
        occluder_transform = unreal.Transform(location=target + back_axis * 45.0, rotation=back_rotation,
                                             scale=unreal.Vector(0.05, 0.70, 0.70))
        occluder = _result(library.create_number_preview_occluder(preview, cube, occluder_transform), "创建遮挡物")
        for name in CASES:
            occluder.set_visibility(name in ("partial_occlusion", "full_occlusion", "behind_occluder"), False)
            if name == "partial_occlusion":
                occluder.set_world_location(target + back_axis * 45.0 + right_axis * 35.0, False, False)
            elif name == "full_occlusion":
                occluder.set_world_location(target + back_axis * 45.0, False, False)
            elif name == "behind_occluder":
                occluder.set_world_location(target - back_axis * 45.0, False, False)
            camera = target - back_axis * config["distance_cm"] if name == "front" else back_camera
            rotation = unreal.MathLibrary.find_look_at_rotation(camera, target)
            camera_transform = unreal.Transform(location=camera, rotation=rotation, scale=unreal.Vector(1, 1, 1))
            result = library.capture_number_preview_pair(preview, post, camera_transform, config["width"], config["height"],
                                                        config["horizontal_fov"], str(output), name)
            engine_frame = _capture_result(result)
            report["cases"][name] = {"engine_frame": int(engine_frame), "same_game_frame": True,
                                     "camera_location_cm": [camera.x, camera.y, camera.z],
                                     "camera_rotation": str(rotation), "horizontal_fov": config["horizontal_fov"],
                                     "width": config["width"], "height": config["height"], "sequence": None,
                                     "rgb": name + "_rgb.png", "mask": name + "_mask.png"}
    except BaseException:
        report["error"] = traceback.format_exc()
        raise
    finally:
        cleanup_errors = []
        if follower is not None:
            try:
                _bool_result(library.destroy_number_mask_follower(follower, preview), "销毁号码代理")
            except BaseException as exc:
                cleanup_errors.append(str(exc))
        if preview is not None:
            try:
                _bool_result(library.destroy_number_preview_mesh(preview), "销毁临时球员")
            except BaseException as exc:
                cleanup_errors.append(str(exc))
        after = _snapshot(source)
        post_gate = appearance_diagnostic.collect_diagnostic(unreal, mapping)
        report["source_after"] = after
        report["source_unchanged"] = before == after
        report["cleanup_errors"] = cleanup_errors
        report["remaining_preview_actors"] = _preview_actors(unreal)
        report["dirty_package_paths_after"] = post_gate["dirty_package_paths"]
        report["restore_verified"] = (not cleanup_errors and before == after and not report["remaining_preview_actors"]
                                      and post_gate["task7_preflight_can_start"] and not post_gate["dirty_package_paths"])
        (output / "capture_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        record_test_render(output, "complete" if report["restore_verified"] and not report.get("error") else "failed_stopped")
        assert report["restore_verified"], "MANUAL_REQUIRED: PoC 恢复未通过，保留 capture_report.json"
    print("JERSEY_UV_POC_CAPTURED " + str(output / "capture_report.json"))


if __name__ == "__main__":
    main()
