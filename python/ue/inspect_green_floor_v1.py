"""只读登记原版绿色草地的实际材质和参数；不创建、修改或保存资产。"""

import json
from pathlib import Path


def main():
    import unreal

    root = Path(unreal.Paths.project_dir())
    output = root / "Saved/FloorDiversity/green_v1/original_material_inspection.json"
    if output.exists():
        raise FileExistsError("只读收据已存在，不覆盖")
    dirty = [p.get_path_name() for p in
             list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) +
             list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    world = unreal.EditorLevelLibrary.get_editor_world()
    assert world.get_path_name().split(".")[0] == "/Game/FutsalMOT/Maps/L_FutsalCourt"
    assert not dirty and not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    floors = [a for a in unreal.EditorLevelLibrary.get_all_level_actors()
              if a.get_actor_label() == "SM_FutsalCourt_Floor"]
    assert len(floors) == 1
    components = [c for c in floors[0].get_components_by_class(unreal.StaticMeshComponent)
                  if c.get_name() == "StaticMeshComponent0"]
    assert len(components) == 1
    component = components[0]
    assert component.get_num_materials() == 1
    original = component.get_material(0)
    assert original.get_path_name() == (
        "/Game/FutsalMOT/Materials/MI_Futsal_Field_Grass_Matte_v1."
        "MI_Futsal_Field_Grass_Matte_v1")
    library = unreal.MaterialEditingLibrary
    result = {"status": "readonly_original_green_material_inspected", "mutation": False,
              "level": world.get_path_name(), "component": component.get_path_name(),
              "original_material": original.get_path_name(), "chain": [],
              "dirty_packages_before": dirty, "PIE": False, "MRQ": False}
    material = original
    for _ in range(8):
        item = {"path": material.get_path_name(), "class": material.get_class().get_name(),
                "scalar_names": [str(n) for n in library.get_scalar_parameter_names(material)],
                "vector_names": [str(n) for n in library.get_vector_parameter_names(material)],
                "texture_names": [str(n) for n in library.get_texture_parameter_names(material)]}
        if item["class"] == "MaterialInstanceConstant":
            item["scalars"] = {n: float(library.get_material_instance_scalar_parameter_value(material, n))
                               for n in item["scalar_names"]}
            item["vectors"] = {}
            for n in item["vector_names"]:
                color = library.get_material_instance_vector_parameter_value(material, n)
                item["vectors"][n] = [float(color.r), float(color.g), float(color.b), float(color.a)]
            item["textures"] = {}
            for n in item["texture_names"]:
                texture = library.get_material_instance_texture_parameter_value(material, n)
                item["textures"][n] = texture.get_path_name() if texture else None
            parent = material.get_editor_property("parent")
            item["parent"] = parent.get_path_name() if parent else None
        else:
            parent = None
            item["expressions"] = []
            for expression in library.get_material_expressions(material):
                node = {"class": expression.get_class().get_name(), "name": expression.get_name()}
                for prop in ("parameter_name", "texture", "default_value", "const_r", "const_g", "const_b"):
                    try:
                        value = expression.get_editor_property(prop)
                        node[prop] = value.get_path_name() if hasattr(value, "get_path_name") else str(value)
                    except Exception:
                        pass
                item["expressions"].append(node)
        result["chain"].append(item)
        if parent is None:
            break
        material = parent
    else:
        raise RuntimeError("材质父链超过界限")
    result["dirty_packages_after"] = [p.get_path_name() for p in
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) +
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert result["dirty_packages_after"] == dirty
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print("GREEN_FLOOR_INSPECTION " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
