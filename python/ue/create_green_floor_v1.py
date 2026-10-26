"""独立派生绿色草地材质；只插入BaseColor乘数，不改原图或地图绑定。"""

import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from grf_ue_bridge.green_floor import GREEN_CATALOG, ORIGINAL_MATERIAL

DESTINATION = "/Game/FutsalMOT/Environment/Floors/GreenV1"
PARENT = "/Game/FutsalMOT/Materials/M_Futsal_Field_Grass"
PARAMETER = "GreenAlbedoGain"


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def main():
    import unreal

    project = Path(unreal.Paths.project_dir())
    evidence = project / "Saved/FloorDiversity/green_v1"
    apply = os.environ.get("FUTSALMOT_GREEN_CREATE") == "1"
    lib = unreal.MaterialEditingLibrary
    world = unreal.EditorLevelLibrary.get_editor_world()
    assert world.get_path_name().split(".")[0] == "/Game/FutsalMOT/Maps/L_FutsalCourt"
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    dirty = lambda: [p.get_path_name() for p in
                    list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) +
                    list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert not dirty(), "发现未知dirty，停止"
    assert not unreal.EditorAssetLibrary.does_directory_exist(DESTINATION), "已有目标目录，不覆盖或隐式重放"
    for api in ("get_material_property_input_node", "get_material_property_input_node_output_name",
                "get_material_expressions", "get_inputs_for_material_expression",
                "create_material_expression", "connect_material_expressions",
                "connect_material_property", "set_material_instance_parent",
                "set_material_instance_vector_parameter_value", "get_material_instance_vector_parameter_value",
                "set_material_instance_scalar_parameter_value", "get_material_instance_scalar_parameter_value",
                "recompile_material"):
        assert callable(getattr(lib, api, None)), api
    parent = unreal.load_asset(PARENT)
    original = unreal.load_asset(ORIGINAL_MATERIAL)
    assert parent and parent.get_class().get_name() == "Material"
    assert original and original.get_class().get_name() == "MaterialInstanceConstant"
    assert original.get_editor_property("parent") == parent
    floors = [a for a in unreal.EditorLevelLibrary.get_all_level_actors()
              if a.get_actor_label() == "SM_FutsalCourt_Floor"]
    assert len(floors) == 1
    components = [c for c in floors[0].get_components_by_class(unreal.StaticMeshComponent)
                  if c.get_name() == "StaticMeshComponent0"]
    assert len(components) == 1 and components[0].get_num_materials() == 1
    component = components[0]
    assert component.get_material(0) == original
    assert [str(n) for n in lib.get_vector_parameter_names(parent)] == []
    scalar_values = {str(n): float(lib.get_material_instance_scalar_parameter_value(original, n))
                     for n in lib.get_scalar_parameter_names(original)}
    assert set(scalar_values) == {"Param"} and abs(scalar_values["Param"] - .08) < 1e-6

    def graph(material):
        result = {}
        for node in lib.get_material_expressions(material):
            result[node.get_name()] = {"class": node.get_class().get_name(),
                                      "inputs": [n.get_name() if n else None for n in
                                                 lib.get_inputs_for_material_expression(material, node)]}
        return result

    def property_inputs(material):
        result = {}
        for enum in (unreal.MaterialProperty.MP_NORMAL, unreal.MaterialProperty.MP_ROUGHNESS,
                     unreal.MaterialProperty.MP_METALLIC, unreal.MaterialProperty.MP_SPECULAR,
                     unreal.MaterialProperty.MP_AMBIENT_OCCLUSION, unreal.MaterialProperty.MP_EMISSIVE_COLOR,
                     unreal.MaterialProperty.MP_OPACITY, unreal.MaterialProperty.MP_OPACITY_MASK,
                     unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET):
            node = lib.get_material_property_input_node(material, enum)
            result[str(enum)] = [node.get_name() if node else None,
                                 lib.get_material_property_input_node_output_name(material, enum)]
        return result

    source_graph = graph(parent)
    other_inputs = property_inputs(parent)
    source_paths = [PARENT, ORIGINAL_MATERIAL.split(".")[0]] + [
        "/Game/FutsalMOT/Materials/ArtificialTurf/T_pgbfwes0_4K_" + suffix for suffix in ("B", "N", "ORM")]
    source_files = [(project / "Content" / (path.removeprefix("/Game/") + ".uasset"))
                    for path in source_paths]
    source_sha = {str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_files}
    report = {"status": "readonly_green_asset_preflight_passed", "runtime_authorized": False,
              "source_material": ORIGINAL_MATERIAL, "source_sha256": source_sha,
              "non_BaseColor_inputs": other_inputs, "source_graph": source_graph,
              "copied_scalar_values": scalar_values, "destination": DESTINATION,
              "map_binding_changed": False, "original_assets_modified": False,
              "unavailable_individual_output_checks": ["MP_PIXEL_DEPTH_OFFSET_not_exposed_to_UE58_Python"],
              "variants": list(GREEN_CATALOG), "created_assets": []}
    if not apply:
        write_new(evidence / "green_asset_preflight.json", report)
        print("GREEN_MATERIAL_PREFLIGHT_PASSED")
        return
    assert not (evidence / "green_asset_creation_intent.json").exists(), "已有创建事务，不重放"
    write_new(evidence / "green_asset_creation_intent.json", report)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.duplicate_asset("M_GrassGain_v1", DESTINATION, parent)
    assert material and material.get_class().get_name() == "Material"
    report["created_assets"].append(material.get_path_name())
    assert graph(material) == source_graph
    assert property_inputs(material) == other_inputs
    base_node = lib.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    base_output = lib.get_material_property_input_node_output_name(material, unreal.MaterialProperty.MP_BASE_COLOR)
    assert base_node is not None
    gain = lib.create_material_expression(material, unreal.MaterialExpressionVectorParameter, 600, 0)
    gain.set_editor_property("parameter_name", PARAMETER)
    gain.set_editor_property("default_value", unreal.LinearColor(1, 1, 1, 1))
    multiply = lib.create_material_expression(material, unreal.MaterialExpressionMultiply, 800, 0)
    assert lib.connect_material_expressions(base_node, base_output, multiply, "A")
    assert lib.connect_material_expressions(gain, "", multiply, "B")
    assert lib.connect_material_property(multiply, "", unreal.MaterialProperty.MP_BASE_COLOR)
    actual_graph = graph(material)
    assert {name: actual_graph[name] for name in source_graph} == source_graph
    assert len(actual_graph) == len(source_graph) + 2
    assert property_inputs(material) == other_inputs
    assert lib.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR) == multiply
    lib.recompile_material(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material)

    report["readback"] = []
    # identity只作派生链基线验证；正式original变体仍直接使用原实例。
    for variant in list(GREEN_CATALOG):
        name = "MI_" + ("grass_identity_v1" if variant["id"] == "grass_original_v1" else variant["id"])
        instance = tools.create_asset(name, DESTINATION, unreal.MaterialInstanceConstant,
                                      unreal.MaterialInstanceConstantFactoryNew())
        assert instance is not None
        report["created_assets"].append(instance.get_path_name())
        lib.set_material_instance_parent(instance, material)
        for parameter, value in scalar_values.items():
            lib.set_material_instance_scalar_parameter_value(instance, parameter, value)
            actual = float(lib.get_material_instance_scalar_parameter_value(instance, parameter))
            assert abs(actual - value) < 1e-6
        values = variant["albedo_gain_linear"] + [1.0]
        lib.set_material_instance_vector_parameter_value(instance, PARAMETER, unreal.LinearColor(*values))
        color = lib.get_material_instance_vector_parameter_value(instance, PARAMETER)
        readback = [float(color.r), float(color.g), float(color.b), float(color.a)]
        assert all(abs(a - b) < 1e-6 for a, b in zip(values, readback))
        assert instance.get_editor_property("parent") == material
        assert unreal.EditorAssetLibrary.save_loaded_asset(instance)
        report["readback"].append({"id": variant["id"], "material": instance.get_path_name(),
                                   "gain": readback, "copied_scalars": scalar_values})
    assert component.get_material(0) == original
    assert graph(parent) == source_graph and property_inputs(parent) == other_inputs
    assert all(hashlib.sha256((project / relative).read_bytes()).hexdigest() == value
               for relative, value in source_sha.items())
    assert not dirty(), "自有保存后仍有dirty，保留证据不自动退出"
    report.update(status="green_assets_created_graph_and_parameters_verified_not_render_accepted",
                  preserved_original_graph=True, preserved_non_BaseColor_inputs=True,
                  dirty_packages_after=[], visual_acceptance=False)
    write_new(evidence / "green_asset_creation_complete.json", report)
    print("GREEN_MATERIAL_CREATED_PARAMETERS_READBACK_PASSED")


if __name__ == "__main__":
    main()
