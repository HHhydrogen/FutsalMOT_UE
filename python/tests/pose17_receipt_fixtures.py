"""历史Pose17收据测试的纯数据fixture；没有采集或渲染入口。"""

def plan():
    return {"schema": "futsalmot_pose17_smoke_plan_v1", "attempt": "a01", "start_frame": 10,
            "frame_count": 3, "cameras": [{"camera_id": "CineCam_01", "source_sequence": "/Game/Test/First", "camera_actor_object_name": "CameraOne"},
                                         {"camera_id": "CineCam_02", "source_sequence": "/Game/Test/Second", "camera_actor_object_name": "CameraTwo"}],
            "targets": [{"actor_object_name": "ActualActor", "component_object_name": "MPFBVisual"}]}

def finished_session(tmp_path):
    data = plan()
    data["targets"][0]["entity_id"] = "L0"
    state = {"status":"rendered_requires_RGB_mask_pose_alignment_acceptance", "executor_success":True,
        "errors":[],"ready_to_render":False,"editor_restore_probe_pending":False,
        "editor_scene_state_matched":True,"editor_mesh_state_matched":True,"streaming_restart_required":False,
        "completed_jobs":[{"job":c["camera_id"],"sampling_passed":True,"restore_passed":True} for c in data["cameras"]]}
    return {"attempt":tmp_path,"plan":data,"state":state}

def editor_report():
    return {"level":runner._LEVEL+".L_FutsalCourt","players":[],"mrq_running":False,"pie_worlds":[],"dirty_packages":[]}

def override_plan():
    data = plan()
    data.update(allow_pie_visual_mesh_override=True,diagnostic_scope="pose17_character_calibration",
        allow_pie_cpu_preparation=True,allow_pie_driver_hide=True,override_warmup_frames=8)
    data["targets"][0].update(entity_id="L0",
        diagnostic_visual_mesh_override="/Game/FutsalMOT/Characters/MPFB/Players/Player_004/Mesh/MPFB_Player_004.MPFB_Player_004")
    return data

def override_receipt():
    data = override_plan()
    path = data["targets"][0]["diagnostic_visual_mesh_override"]
    return {"visual_mesh_override_requested":True,"diagnostic_scope":"pose17_character_calibration","pipeline_setup_error":"",
        "visual_mesh_overrides":[dict(applied_asset_path=path,identity_verified=True,apply_succeeded=True,
            animation_binding_preserved=True,new_asset_materials_verified=True,restore_attempted=True,restore_succeeded=True,
            apply_error="",restore_error="")],
        "records":[{"entity_id":"L0","mesh_identity":{"asset_path":path},"override_warmup_engine_frames_observed":10}]}

def gpu_lbs_plan():
    """纯CPU契约例；不代表任何UE捕获。"""
    data = plan()
    data.update(pose_sampling_path="gpu_render_cpu_lbs",allow_gpu_render_cpu_lbs_diagnostic=True,
        diagnostic_scope="pose17_gpu_render_cpu_lbs",allow_pie_cpu_preparation=False,
        allow_pie_driver_hide=True,gpu_lbs_warmup_frames=8)
    return data

def gpu_lbs_receipt():
    """明确toy，检查native收据门禁失败路径。"""
    eligibility = dict.fromkeys(("checks_executed","eligible","pie_world","weights_readable"),True)
    eligibility.update(dict.fromkeys(("render_cpu_enabled","render_static","has_nanite_data","parallel_evaluation_running",
        "leader_parallel_evaluation_running","non_finite_morph_weights","lod0_has_cloth_data","variable_influence_weights"),False))
    eligibility.update(dict.fromkeys(("active_morph_weight_count","manual_morph_curve_count","external_morph_set_count",
        "cloth_simulation_count","lod0_cloth_section_count","mesh_deformer_asset_count","mesh_deformer_instance_count",
        "material_wpo_slot_count","null_material_slot_count"),0))
    eligibility.update(weight_vertex_count=12,reference_vertex_count=12,max_bone_influences=4)
    return {"pose_sampling_path":"gpu_render_cpu_lbs","gpu_lbs_diagnostic_requested":True,
        "diagnostic_scope":"pose17_gpu_render_cpu_lbs","pipeline_setup_error":"","gpu_lbs_prepared_engine_frame":100,
        "records":[dict(sample_succeeded=True,render_cpu_enabled_at_read=False,render_static_at_read=False,
            predicted_lod_at_read=0,sampling_method="gpu_render_component_pose_cpu_lbs_no_morph_cloth_deformer_wpo_diagnostic",
            pose_fence_method="gpu_dynamic_data_endframe_tasks_finished_render_commands_flush",
            end_frame_update_tasks_finished=True,gpu_lbs_warmup_engine_frames_observed=8,hook_engine_frame=108,
            mesh_identity={"vertex_count":12},gpu_lbs_eligibility=eligibility)]}

def gpu_override_plan():
    data = gpu_lbs_plan()
    data.update(allow_pie_visual_mesh_override=True,diagnostic_scope="pose17_gpu_render_cpu_lbs_character_calibration",
        override_warmup_frames=8,calibration_player_id=4)
    data["targets"][0].update(entity_id="L0",component_object_name="MPFBVisual",
        diagnostic_visual_mesh_override=override_plan()["targets"][0]["diagnostic_visual_mesh_override"])
    return data
