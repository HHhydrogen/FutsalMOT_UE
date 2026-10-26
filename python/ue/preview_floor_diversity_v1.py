"""地板单槽临时预览事务；不保存地图、不改变角色/相机/灯光。"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
import build_floor_diversity_v1 as build
from grf_ue_bridge.floor_diversity import select_floor_id

WORLD_REPORT_SHA = "414c0e129faaec5bfeb565ebdaf2c57c1c28a1803e9901c94fc83f54401d6f17"
IMPORTED_ASSET_PROOF_VERSION = 1
LINE_MATERIAL = "/Game/FutsalMOT/Materials/M_CourtLine_White.M_CourtLine_White"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def atomic_json(path, value):
    """先落盘意图，再修改场景；异常可读取同一事务恢复。"""
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    import unreal
    action = os.environ.get("FUTSALMOT_FLOOR_PREVIEW_ACTION", "preflight")
    assert action in ("preflight", "apply", "restore", "status")
    apply = os.environ.get("FUTSALMOT_FLOOR_PREVIEW_APPLY") == "1"
    seed = int(os.environ.get("FUTSALMOT_FLOOR_PREVIEW_SEED", "1021"))
    floor_id = os.environ.get("FUTSALMOT_FLOOR_PREVIEW_ID") or select_floor_id(seed)
    assert floor_id in {v["id"] for v in build.CATALOG}
    token = os.environ.get("FUTSALMOT_FLOOR_PREVIEW_SESSION", "floor_preview_v1")
    assert token and len(token) <= 80 and all(c.isalnum() or c in "_-" for c in token)
    camera_label = os.environ.get("FUTSALMOT_FLOOR_PREVIEW_CAMERA", "CineCam_01")
    project = Path(unreal.Paths.project_dir()).resolve()
    evidence = project / "Saved/FloorDiversity/v1"
    world_bytes = (evidence / "ue_world_xy_v1_report.json").read_bytes()
    assert hashlib.sha256(world_bytes).hexdigest() == WORLD_REPORT_SHA
    assert json.loads(world_bytes)["status"] == "world_xy_graph_saved_not_applied"
    source_png = evidence / "T_FloorNeutral_Albedo_v1.png"
    if source_png.is_file():
        assert hashlib.sha256(source_png.read_bytes()).hexdigest() == build.SOURCE_SHA
    else:
        assert os.environ.get("FUTSALMOT_FLOOR_IMPORTED_ASSET_PROOF") == "pinned_imported_packages_v1", "源PNG已退休，须显式核验已导入package"
        from floor_imported_asset_proof import verify_imported_floor_asset_bytes
        binding_path = Path(os.environ["FUTSALMOT_FLOOR_IMPORTED_ASSET_BINDING"])
        assert project / "Saved/AppearancePlanning" in binding_path.parents
        verify_imported_floor_asset_bytes(project, json.loads(world_bytes), json.loads(binding_path.read_text(encoding="utf-8-sig")))
    world = unreal.EditorLevelLibrary.get_editor_world()
    assert world.get_path_name().split(".", 1)[0] == build.LEVEL
    actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    floors = [a for a in actors if a.get_actor_label() == "SM_FutsalCourt_Floor"]
    cameras = [a for a in actors if a.get_actor_label() == camera_label]
    assert len(floors) == len(cameras) == 1, "地板/相机 Actor 非唯一"
    components = [c for c in floors[0].get_components_by_class(unreal.StaticMeshComponent)
                  if c.get_name() == "StaticMeshComponent0"]
    assert len(components) == 1
    component = components[0]
    assert component.get_num_materials() == 1
    assert component.get_editor_property("static_mesh").get_path_name() == "/Engine/BasicShapes/Cube.Cube"
    assert [str(n) for n in component.get_material_slot_names()] == ["WorldGridMaterial"]
    library = unreal.MaterialEditingLibrary
    variants = {}
    for variant in build.CATALOG:
        p = build.DESTINATION + "/MI_" + variant["id"]
        material = unreal.load_asset(p)
        assert material and material.get_class().get_name() == "MaterialInstanceConstant"
        assert material.get_editor_property("parent").get_path_name() == build.MATERIAL_PATH + ".M_FloorTint_v1"
        assert abs(float(library.get_material_instance_scalar_parameter_value(material, "FloorTileSizeCM")) - 200) < 1e-6
        variants[variant["id"]] = material
    snapshot = []
    line_slots = []
    for actor in actors:
        location, rotation, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
        item = {"actor": actor.get_path_name(), "label": actor.get_actor_label(),
                "location": [location.x, location.y, location.z],
                "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
                "scale": [scale.x, scale.y, scale.z], "mesh_materials": [], "lights": []}
        for mesh in actor.get_components_by_class(unreal.MeshComponent):
            for slot in range(mesh.get_num_materials()):
                if mesh == component and slot == 0:
                    continue
                value = mesh.get_material(slot)
                path = value.get_path_name() if value else None
                binding = {"component": mesh.get_path_name(), "slot": slot, "material": path}
                item["mesh_materials"].append(binding)
                if path == LINE_MATERIAL:
                    line_slots.append(binding)
        for light in actor.get_components_by_class(unreal.LightComponent):
            color = light.get_editor_property("light_color")
            item["lights"].append({"component": light.get_path_name(),
                                   "intensity": float(light.get_editor_property("intensity")),
                                   "color": [color.r, color.g, color.b, color.a]})
        if actor == cameras[0]:
            camera_components = actor.get_components_by_class(unreal.CineCameraComponent)
            assert len(camera_components) == 1
            cine = camera_components[0]
            filmback = cine.get_editor_property("filmback")
            item["camera"] = {"focal_length": float(cine.get_editor_property("current_focal_length")),
                              "sensor_width": float(filmback.sensor_width),
                              "sensor_height": float(filmback.sensor_height)}
        snapshot.append(item)
    assert line_slots and all(b["component"] != component.get_path_name() for b in line_slots), "未确认独立白线组件"
    snapshot.sort(key=lambda row: row["actor"])
    snapshot_sha = digest(snapshot)
    dirty = [p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
             + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    current = component.get_material(0).get_path_name()
    state_path = evidence / (token + "_state.json")
    journal = evidence / (token + "_steps.jsonl")
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    report = {"action": action, "apply": apply, "session": token, "seed": seed,
              "floor_id": floor_id, "selection_mode": "explicit_preview" if os.environ.get("FUTSALMOT_FLOOR_PREVIEW_ID") else "seeded_preview",
              "current_floor": current, "non_floor_scene_sha256": snapshot_sha,
              "camera_label": camera_label, "camera_path": cameras[0].get_path_name(),
              "frame_context": "editor_static_no_sequence_frame_claim",
              "independent_white_line_slots": len(line_slots), "dirty_packages": dirty,
              "production_enabled": False, "visual_acceptance": False}
    if action in ("preflight", "status") or not apply:
        report["state"] = state
        print("FLOOR_PREVIEW_READONLY " + json.dumps(report))
        return report
    if state is None:
        assert action == "apply", "无当前session可恢复"
        assert current == build.CURRENT_FLOOR and not dirty, "首次预览要求原绑定及clean"
        state = {"version": 1, "session": token, "original_material": current,
                 "component": component.get_path_name(), "level": world.get_path_name(),
                 "initial_non_floor_scene_sha256": snapshot_sha,
                 "initial_snapshot": snapshot, "initial_white_line_slots": line_slots,
                 "camera_label": camera_label, "world_upgrade_sha256": WORLD_REPORT_SHA,
                 "step": 0, "status": "initialized", "expected_current_material": current}
    assert state["component"] == component.get_path_name() and state["level"] == world.get_path_name()
    owned_materials = {build.CURRENT_FLOOR} | {m.get_path_name() for m in variants.values()}
    assert current in owned_materials, "地板已被范围外操作修改"
    assert state["camera_label"] == camera_label
    expected = {state["expected_current_material"], state["original_material"]}
    if state["status"].endswith("_intent_persisted"):
        expected.add(state["target_material"])
    assert current in expected, "当前材质不匹配事务最近一步，拒绝覆盖未知改动"
    if action == "apply":
        assert set(dirty).issubset(set(state.get("owned_dirty_packages_after_step", []))), "发现新的未知 dirty 包"
        assert snapshot_sha == state["initial_non_floor_scene_sha256"], "相机/运动/灯光等已改变，拒绝混入对照"
        target = variants[floor_id]
    else:
        target = unreal.load_asset(state["original_material"])
        assert target is not None
    state["step"] += 1
    state["status"] = action + "_intent_persisted"
    state["before_material"] = current
    state["target_material"] = target.get_path_name()
    state["last_action"] = report
    atomic_json(state_path, state)
    # 唯一 UE mutation：指定地板组件的第零槽。绝不 save_map/save_asset。
    component.set_material(0, target)
    actual = component.get_material(0).get_path_name()
    assert actual == target.get_path_name()
    state["expected_current_material"] = actual
    state["status"] = "preview_active" if action == "apply" else "original_floor_slot_restored_not_saved"
    state["non_floor_context_changed"] = snapshot_sha != state["initial_non_floor_scene_sha256"]
    state["owned_dirty_packages_after_step"] = [p.get_path_name() for p in
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) +
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    atomic_json(state_path, state)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"step": state["step"], "status": state["status"],
                                 "before": current, "after": actual, "context": report}, ensure_ascii=False) + "\n")
    print("FLOOR_PREVIEW_STEP " + json.dumps({k: v for k, v in state.items() if k != "initial_snapshot"}))
    return state


if __name__ == "__main__":
    main()
