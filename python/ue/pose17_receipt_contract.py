"""历史Pose17收据的只读校验；不提供UE准备、提交或渲染入口。"""

import hashlib

import json

import os

import sys

import types

from pathlib import Path

from pose17_calibration_assets import ORIGINAL_VISUAL_MESH, JOINT_VISUAL_IDS, calibration_visual_mesh, production_visual_mesh

from pose17_location_pilot_contract import validate_location_pilot_contract

from pose17_long_window_contract import validate_long_window_contract

from pose17_seeded_kit_contract import validate_seeded_kit_contract, assert_seeded_kit_receipt

from pose17_camera_scope import select_capture_cameras, make_capture_scope, session_cameras

_LEVEL = "/Game/FutsalMOT/Maps/L_FutsalCourt"

MEDIA_ROOT_CONTRACT_VERSION = 1

def validate_plan(plan):
    """计划只允许小样：原生4K、至少3帧/两个显式源序列，不改正式 v1。"""
    if plan.get("schema") != "futsalmot_pose17_smoke_plan_v1":
        raise ValueError("需要显式 Pose17 smoke plan schema")
    name = plan.get("attempt")
    if not isinstance(name, str) or not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
        raise ValueError("attempt 必须为安全独立目录名")
    start, count = plan.get("start_frame"), plan.get("frame_count")
    location_pilot = validate_location_pilot_contract(plan)
    long_window = validate_long_window_contract(plan)
    seeded_kit = validate_seeded_kit_contract(plan)
    if type(start) is not int or type(count) is not int or not (count in (3,300) if seeded_kit else count == 300 if long_window else count == 120 if location_pilot else 3 <= count <= 30):
        raise ValueError("需要明确起始帧与3..30个连续动态诊断帧")
    cameras = plan.get("cameras", [])
    if len(cameras) < 2 or len({item["camera_id"] for item in cameras}) != len(cameras):
        raise ValueError("至少两个不同机位")
    for camera in cameras:
        camera_id = camera.get("camera_id", "")
        if not camera_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in camera_id):
            raise ValueError("camera_id 必须为安全相对目录名")
        path = camera.get("source_sequence")
        if not isinstance(path, str) or not path.startswith("/Game/") or ".." in path or "\\" in path:
            raise ValueError("每机位须显式源Sequence，不猜测 canonical 安全")
        if not isinstance(camera.get("camera_actor_object_name"), str) or not camera["camera_actor_object_name"]:
            raise ValueError("每机位须显式PIE相机Actor对象名以准备零motionblur")
    if len({item["source_sequence"] for item in cameras}) != len(cameras):
        raise ValueError("每机位单独Sequence，禁止将同源Sequence伪装两个视角")
    if not plan.get("targets"):
        raise ValueError("必须显式绑定实体/Actor/实际 VisualMesh")
    sampling_path = plan.get("pose_sampling_path","cpu_skin_cache")
    overrides = [row for row in plan["targets"] if row.get("diagnostic_visual_mesh_override") is not None]
    combined = plan.get("diagnostic_scope") == "pose17_gpu_render_cpu_lbs_character_calibration"
    joint = plan.get("diagnostic_scope") == "pose17_gpu_render_cpu_lbs_joint_diagnostic"
    if sampling_path not in ("cpu_skin_cache","gpu_render_cpu_lbs"):
        raise ValueError("未知采样路径，禁止静默回退")
    if sampling_path == "gpu_render_cpu_lbs":
        if (plan.get("allow_gpu_render_cpu_lbs_diagnostic") is not True
                or plan.get("diagnostic_scope") not in ("pose17_gpu_render_cpu_lbs","pose17_gpu_render_cpu_lbs_character_calibration","pose17_gpu_render_cpu_lbs_joint_diagnostic")
                or plan.get("allow_pie_cpu_preparation") is not False or plan.get("allow_pie_driver_hide") is not True
                or (not combined and not joint and (plan.get("allow_pie_visual_mesh_override") or overrides))):
            raise ValueError("GPU-render/LBS需要明确opt-in/scope/CPU关闭/隐藏driver及独立角色组合授权")
        warmup = plan.get("gpu_lbs_warmup_frames")
        if type(warmup) is not int or not 8 <= warmup <= 120:
            raise ValueError("新GPU-render/LBS需要8..120帧warmup，不通过去掉预热规避问题")
    elif plan.get("allow_gpu_render_cpu_lbs_diagnostic"):
        raise ValueError("GPU/LBS授权与采样路径不一致")
    if overrides or plan.get("allow_pie_visual_mesh_override"):
        if (plan.get("allow_pie_visual_mesh_override") is not True or len(overrides) != (8 if joint else 1)
                or plan.get("diagnostic_scope") not in ("pose17_character_calibration","pose17_gpu_render_cpu_lbs_character_calibration","pose17_gpu_render_cpu_lbs_joint_diagnostic")
                or plan.get("allow_pie_cpu_preparation") is not (False if combined or joint else True) or plan.get("allow_pie_driver_hide") is not True):
            raise ValueError("角色override必须显式PIE诊断scope/opt-in/CPU/隐藏driver，当前仅一次一个角色")
        warmup = plan.get("override_warmup_frames")
        if type(warmup) is not int or not 8 <= warmup <= 120:
            raise ValueError("角色override需要明确8..120帧warmup")
        path = overrides[0]["diagnostic_visual_mesh_override"]
        if (not isinstance(path,str) or not path.startswith("/Game/FutsalMOT/Characters/MPFB/Players/Player_00")
                or ".." in path or "\\" in path or path.rsplit(".",1)[-1] not in {"MPFB_Player_%03d"%i for i in range(3,10)}):
            raise ValueError("本轮override仅允许显式生产Player003至009 SkeletalMesh对象路径")
        if overrides[0].get("component_object_name") != "MPFBVisual":
            raise ValueError("override必须绑定实际MPFBVisual，禁止驱动底模")
    if combined:
        expected_mesh = calibration_visual_mesh(plan.get("calibration_player_id"))
        if (sampling_path != "gpu_render_cpu_lbs" or plan.get("allow_gpu_render_cpu_lbs_diagnostic") is not True
                or plan.get("allow_pie_visual_mesh_override") is not True or len(overrides)!=1 or len(plan["targets"])!=1
                or overrides[0]["diagnostic_visual_mesh_override"] != expected_mesh
                or overrides[0].get("entity_id") != "L0"
                or plan.get("override_warmup_frames") != plan.get("gpu_lbs_warmup_frames")):
            raise ValueError("GPU/LBS角色组合仅单L0白名单004..009双opt-in，两个warmup字段必须相等")
    if joint:
        if (plan.get("allow_joint_pose17_diagnostic") is not True or sampling_path!="gpu_render_cpu_lbs"
                or plan.get("allow_pie_visual_mesh_override") is not True or len(overrides)!=8
                or plan.get("override_warmup_frames")!=plan.get("gpu_lbs_warmup_frames")
                or len(plan["targets"])!=10 or {row.get("entity_id") for row in plan["targets"]}!=set(JOINT_VISUAL_IDS)
                or len({row.get("actor_object_name") for row in plan["targets"]})!=10
                or len(cameras)!=4):
            raise ValueError("联合GPU诊断需要显式授权、十实体/四相机/八override及相同warmup")
        for row in plan["targets"]:
            player_id = row.get("calibration_player_id")
            if (type(player_id) is not int or player_id!=JOINT_VISUAL_IDS[row["entity_id"]]
                    or row.get("component_object_name")!="MPFBVisual"
                    or row.get("sequence_binding_name")!="Player_"+row["entity_id"]
                    or row.get("diagnostic_visual_mesh_override")!=(None if player_id==3 else production_visual_mesh(player_id))):
                raise ValueError("联合实体/角色ID/精确asset/显式Sequence绑定不符合固定映射")
    elif plan.get("allow_joint_pose17_diagnostic"):
        raise ValueError("联合opt-in不能套用其他scope")

def _assert_override_receipt(plan, receipt):
    """纯CPU契约：新角色必须提供真实身份、材质/动画保持及恢复收据。"""
    assert_seeded_kit_receipt(plan, receipt)
    targets = [row for row in plan["targets"] if row.get("diagnostic_visual_mesh_override")]
    if not targets:
        if receipt.get("visual_mesh_override_requested") or receipt.get("visual_mesh_overrides"):
            raise RuntimeError("未授权计划出现角色override")
        return
    if (receipt.get("visual_mesh_override_requested") is not True
            or receipt.get("diagnostic_scope") != plan.get("diagnostic_scope") or receipt.get("pipeline_setup_error")):
        raise RuntimeError("角色override native授权scope/setup门禁未通过")
    if plan.get("diagnostic_scope")=="pose17_gpu_render_cpu_lbs_character_calibration":
        player_id = plan.get("calibration_player_id")
        if targets[0]["diagnostic_visual_mesh_override"]!=calibration_visual_mesh(player_id):
            raise RuntimeError("角色override计划ID与精确资产白名单不一致")
    evidence = receipt.get("visual_mesh_overrides",[])
    if len(evidence) != len(targets):
        raise RuntimeError("角色override native事务数量不符")
    for target in targets:
        path = target["diagnostic_visual_mesh_override"]
        matching = [row for row in evidence if row.get("applied_asset_path")==path and
            (plan.get("diagnostic_scope")!="pose17_gpu_render_cpu_lbs_joint_diagnostic" or
             row.get("component_path","").endswith("."+target["actor_object_name"]+"."+target["component_object_name"]))]
        if len(matching) != 1:
            raise RuntimeError("角色override未提供对应新mesh事务")
        row = matching[0]
        for field in ("identity_verified","apply_succeeded","animation_binding_preserved","new_asset_materials_verified",
                      "restore_attempted","restore_succeeded"):
            if row.get(field) is not True:
                raise RuntimeError("角色override native证据失败: "+field)
        if row.get("apply_error") or row.get("restore_error"):
            raise RuntimeError("角色override native事务存在错误")
        samples = [r for r in receipt["records"] if r["entity_id"]==target["entity_id"]]
        if plan.get("pose_sampling_path") == "gpu_render_cpu_lbs":
            allowed_originals = {production_visual_mesh(i) for i in range(3,10)} if plan.get("diagnostic_scope")=="pose17_gpu_render_cpu_lbs_joint_diagnostic" else {ORIGINAL_VISUAL_MESH}
            if row.get("original_asset_path") not in allowed_originals:
                raise RuntimeError("角色override原mesh不是精确Player003")
            if (row.get("gpu_lbs_validation_attempted") is not True or row.get("gpu_lbs_validation_succeeded") is not True
                    or row.get("gpu_lbs_validation_error")):
                raise RuntimeError("角色override后没有实际GPU/LBS门禁成功证据")
            expected_vertices = samples[0].get("mesh_identity",{}).get("vertex_count") if samples else -1
            if type(expected_vertices) is not int: raise RuntimeError("角色override缺少新mesh实际顶点数")
            _assert_gpu_lbs_eligibility(row.get("gpu_lbs_eligibility_after_override",{}),expected_vertices)
            applied,prepared = row.get("applied_engine_frame"),receipt.get("gpu_lbs_prepared_engine_frame")
            if type(applied) is not int or type(prepared) is not int or applied<0 or prepared<applied:
                raise RuntimeError("角色apply/GPU prepare实际engine frame顺序不成立")
        if not samples or any(r["mesh_identity"]["asset_path"] != path
                or r.get("override_warmup_engine_frames_observed",-1)<plan["override_warmup_frames"] for r in samples):
            raise RuntimeError("角色override采样不是新mesh身份或实际warmup不足")
        if plan.get("pose_sampling_path") == "gpu_render_cpu_lbs":
            for sample in samples:
                elapsed = sample.get("override_warmup_engine_frames_observed")
                if (type(elapsed) is not int or elapsed!=sample["hook_engine_frame"]-applied
                        or elapsed<sample.get("gpu_lbs_warmup_engine_frames_observed",-1)):
                    raise RuntimeError("角色override与GPU prepare实际warmup关系不一致")

def _assert_gpu_lbs_eligibility(eligibility,vertex_count):
    """实际完整门禁快照；post-override可尚未绑定row，但不能缺任何检查。"""
    for field in ("checks_executed","eligible","pie_world","weights_readable"):
        if eligibility.get(field) is not True: raise RuntimeError("GPU/LBS实际门禁证据缺失: "+field)
    for field in ("render_cpu_enabled","render_static","has_nanite_data","parallel_evaluation_running",
                  "leader_parallel_evaluation_running","non_finite_morph_weights","lod0_has_cloth_data","variable_influence_weights"):
        if eligibility.get(field) is not False: raise RuntimeError("GPU/LBS不支持状态: "+field)
    for field in ("active_morph_weight_count","manual_morph_curve_count","external_morph_set_count","cloth_simulation_count",
                  "lod0_cloth_section_count","mesh_deformer_asset_count","mesh_deformer_instance_count","material_wpo_slot_count","null_material_slot_count"):
        if type(eligibility.get(field)) is not int or eligibility[field]!=0:
            raise RuntimeError("GPU/LBS不支持变形/材质计数: "+field)
    actual_count = eligibility.get("reference_vertex_count")
    if (type(actual_count) is not int or actual_count<=0
            or type(eligibility.get("weight_vertex_count")) is not int or eligibility["weight_vertex_count"]!=actual_count
            or (vertex_count is not None and (type(vertex_count) is not int or vertex_count!=actual_count))
            or type(eligibility.get("max_bone_influences")) is not int or eligibility["max_bone_influences"]<=0):
        raise RuntimeError("GPU/LBS实际weights元数据不一致")

def _assert_gpu_lbs_receipt(plan,receipt):
    """新路径独立成功契约；不能把CPU render/cached结果冒充GPU渲染的LBS诊断。"""
    if plan.get("pose_sampling_path","cpu_skin_cache") != "gpu_render_cpu_lbs":
        if receipt.get("gpu_lbs_diagnostic_requested"):
            raise RuntimeError("计划未授权GPU/LBS但native已启用")
        return
    if (receipt.get("pose_sampling_path") != "gpu_render_cpu_lbs" or receipt.get("gpu_lbs_diagnostic_requested") is not True
            or receipt.get("diagnostic_scope") != plan.get("diagnostic_scope") or receipt.get("pipeline_setup_error")):
        raise RuntimeError("GPU/LBS原生scope/路径/setup未通过")
    prepared = receipt.get("gpu_lbs_prepared_engine_frame")
    if type(prepared) is not int or prepared<0:
        raise RuntimeError("GPU/LBS缺少实际预备engine frame")
    if not receipt.get("records"):
        raise RuntimeError("GPU/LBS没有实际采样记录")
    for row in receipt["records"]:
        if (row.get("sample_succeeded") is not True or row.get("render_cpu_enabled_at_read") is not False
                or row.get("render_static_at_read") is not False or type(row.get("predicted_lod_at_read")) is not int or row["predicted_lod_at_read"] != 0
                or row.get("sampling_method") != "gpu_render_component_pose_cpu_lbs_no_morph_cloth_deformer_wpo_diagnostic"
                or row.get("pose_fence_method") != "gpu_dynamic_data_endframe_tasks_finished_render_commands_flush"
                or row.get("end_frame_update_tasks_finished") is not True):
            raise RuntimeError("GPU/LBS实际GPU模式/方法/LOD0/endframe fence证据失败")
        warmup = row.get("gpu_lbs_warmup_engine_frames_observed")
        if (type(warmup) is not int or type(row.get("hook_engine_frame")) is not int
                or warmup<plan["gpu_lbs_warmup_frames"] or warmup!=row["hook_engine_frame"]-prepared):
            raise RuntimeError("GPU/LBS实际warmup与预备/采样engine frame不一致")
        vertex_count = row.get("mesh_identity",{}).get("vertex_count")
        if type(vertex_count) is not int: raise RuntimeError("GPU/LBS记录缺少完整mesh顶点数")
        _assert_gpu_lbs_eligibility(row.get("gpu_lbs_eligibility",{}),vertex_count)
