"""创建独立地板纹理/母材质/实例；默认只读，不替换地图材质。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from grf_ue_bridge.floor_diversity import CATALOG

DESTINATION = "/Game/FutsalMOT/Environment/Floors/V1"
TEXTURE_PATH = DESTINATION + "/T_FloorNeutral_Albedo_v1"
MATERIAL_PATH = DESTINATION + "/M_FloorTint_v1"
SOURCE_SHA = "81bfaa6a9e0e826446649d251d638c8a6c11319c135173f7768b3a009f5166eb"
CURRENT_FLOOR = "/Game/FutsalMOT/Materials/MI_Futsal_Field_Grass_Matte_v1.MI_Futsal_Field_Grass_Matte_v1"
LEVEL = "/Game/FutsalMOT/Maps/L_FutsalCourt"
NEUTRAL_LINEAR = 0.21404114048223255  # sRGB 0.5 的线性值。


def texture_modulation(linear_sample, amplitude=0.04):
    """材质图对应的标量参考公式，供无 UE 的 CPU 验证。"""
    return 1.0 + amplitude * (min(2.0 * NEUTRAL_LINEAR, max(0.0, linear_sample)) / NEUTRAL_LINEAR - 1.0)


def main():
    import unreal

    project = Path(unreal.Paths.project_dir()).resolve()
    evidence = project / "Saved/FloorDiversity/v1"
    source = evidence / "T_FloorNeutral_Albedo_v1.png"
    report_path = evidence / "ue_build_report.json"
    apply = os.environ.get("FUTSALMOT_FLOOR_BUILD_APPLY") == "1"
    targets = [TEXTURE_PATH, MATERIAL_PATH] + [DESTINATION + "/MI_" + v["id"] for v in CATALOG]
    report = {"status": "preflight", "apply": apply, "targets": targets,
              "source_sha256": SOURCE_SHA, "scene_binding_changed": False,
              "production_enabled": False, "seamless_verified": False,
              "visual_acceptance": False, "created_assets": [],
              "world_alignment": {"implemented": False, "reserved_tile_size_cm": 200.0,
                                  "uv_scale": 1.0, "physical_uv_scale_verified": False}}

    def flush():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 此前不创建资产；所有必要 API 在第一次写操作前检查。
    library = unreal.MaterialEditingLibrary
    classes = ("MaterialFactoryNew", "MaterialInstanceConstantFactoryNew", "AssetImportTask",
               "MaterialExpressionTextureSampleParameter2D", "MaterialExpressionTextureCoordinate",
               "MaterialExpressionVectorParameter", "MaterialExpressionScalarParameter",
               "MaterialExpressionMultiply", "MaterialExpressionAdd", "MaterialExpressionClamp")
    methods = ("create_material_expression", "connect_material_expressions", "connect_material_property",
               "set_material_instance_parent", "set_material_instance_vector_parameter_value",
               "set_material_instance_scalar_parameter_value", "get_material_instance_vector_parameter_value",
               "get_material_instance_scalar_parameter_value", "recompile_material")
    assert all(hasattr(unreal, c) for c in classes), "MANUAL_REQUIRED: 缺少材质节点/Factory API"
    assert all(callable(getattr(library, m, None)) for m in methods), "MANUAL_REQUIRED: 缺少材质编排 API"
    assert hasattr(unreal.MaterialSamplerType, "SAMPLERTYPE_COLOR"), "缺少 Color sampler"
    assert hasattr(unreal.TextureAddress, "TA_WRAP"), "缺少 Wrap 枚举"
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    assert callable(getattr(tools, "create_asset", None)) and callable(getattr(tools, "import_asset_tasks", None))
    assetlib = unreal.EditorAssetLibrary
    for name in ("does_asset_exist", "does_directory_exist", "save_loaded_asset"):
        assert callable(getattr(assetlib, name, None)), "缺少资产 API: " + name
    assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA, "纹理源 SHA 不符"
    assert not assetlib.does_directory_exist(DESTINATION), "拒绝覆盖已有目标目录: " + DESTINATION
    for path in targets:
        assert not assetlib.does_asset_exist(path), "拒绝覆盖资产: " + path
    world = unreal.EditorLevelLibrary.get_editor_world()
    world_path = world.get_path_name()
    assert world_path.split(".", 1)[0] == LEVEL, world_path
    dirty = [p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
             + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert not dirty, "存在未知 dirty 包: " + repr(dirty)
    actors = [a for a in unreal.EditorLevelLibrary.get_all_level_actors()
              if a.get_actor_label() == "SM_FutsalCourt_Floor"]
    assert len(actors) == 1, "地板 Actor 非唯一"
    components = [c for c in actors[0].get_components_by_class(unreal.StaticMeshComponent)
                  if c.get_name() == "StaticMeshComponent0"]
    assert len(components) == 1
    component = components[0]
    assert component.get_num_materials() == 1
    assert component.get_material(0).get_path_name() == CURRENT_FLOOR
    assert component.get_editor_property("static_mesh").get_path_name() == "/Engine/BasicShapes/Cube.Cube"
    assert [str(n) for n in component.get_material_slot_names()] == ["WorldGridMaterial"]
    report["level"] = world_path
    report["original_floor_binding"] = CURRENT_FLOOR
    report["status"] = "preflight_passed_not_applied"
    if not apply:
        print("FLOOR_BUILD_PREFLIGHT " + json.dumps(report))
        return report

    # 只有 apply=true 才开始创建独立资产；发生异常保留部分资产及失败收据，禁止重跑覆盖。
    assert not report_path.exists(), "拒绝覆盖已有创建收据，请先审阅并明确新 attempt"
    try:
        task = unreal.AssetImportTask()
        for key, value in {"filename": str(source), "destination_path": DESTINATION,
                           "destination_name": TEXTURE_PATH.rsplit("/", 1)[-1],
                           "automated": True, "replace_existing": False, "save": False}.items():
            task.set_editor_property(key, value)
        tools.import_asset_tasks([task])
        texture = unreal.load_asset(TEXTURE_PATH)
        assert texture and texture.get_class().get_name() == "Texture2D"
        report["created_assets"].append(TEXTURE_PATH)
        texture.set_editor_property("srgb", True)
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
        assert assetlib.save_loaded_asset(texture)

        def create(path, factory):
            result = tools.create_asset(path.rsplit("/", 1)[-1], DESTINATION, None, factory)
            assert result is not None, path
            report["created_assets"].append(path)
            return result

        material = create(MATERIAL_PATH, unreal.MaterialFactoryNew())

        def node(cls, **properties):
            n = library.create_material_expression(material, getattr(unreal, cls))
            assert n is not None, cls
            for key, value in properties.items():
                n.set_editor_property(key, value)
            return n

        def link(a, output, b, pin):
            assert library.connect_material_expressions(a, output, b, pin), (output, pin)

        def scalar(name, value):
            return node("MaterialExpressionScalarParameter", parameter_name=name, default_value=float(value))

        uv = node("MaterialExpressionTextureCoordinate", coordinate_index=0)
        uv_scale = scalar("FloorUVScale", 1.0)
        uv_mul = node("MaterialExpressionMultiply")
        link(uv, "", uv_mul, "A")
        link(uv_scale, "", uv_mul, "B")
        sample = node("MaterialExpressionTextureSampleParameter2D", parameter_name="FloorNeutralTexture",
                      texture=texture, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
        link(uv_mul, "", sample, "UVs")
        # clamp(sample, 0, 2*neutral)/neutral - 1；中灰变为零，4% 调制有界。
        clamp = node("MaterialExpressionClamp", min_default=0.0, max_default=2.0 * NEUTRAL_LINEAR)
        link(sample, "R", clamp, "")
        normalize = node("MaterialExpressionMultiply", const_b=1.0 / NEUTRAL_LINEAR)
        link(clamp, "", normalize, "A")
        centered = node("MaterialExpressionAdd", const_b=-1.0)
        link(normalize, "", centered, "A")
        amp = scalar("FloorTextureAmplitude", 0.04)
        scaled = node("MaterialExpressionMultiply")
        link(centered, "", scaled, "A")
        link(amp, "", scaled, "B")
        unity = node("MaterialExpressionAdd", const_b=1.0)
        link(scaled, "", unity, "A")
        tint = node("MaterialExpressionVectorParameter", parameter_name="FloorTint",
                    default_value=unreal.LinearColor(*CATALOG[0]["base_color_linear"], 1.0))
        color = node("MaterialExpressionMultiply")
        link(unity, "", color, "A")
        link(tint, "RGB", color, "B")
        assert library.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
        for name, value, prop in (("FloorRoughness", 0.72, unreal.MaterialProperty.MP_ROUGHNESS),
                                  ("FloorMetallic", 0.0, unreal.MaterialProperty.MP_METALLIC)):
            assert library.connect_material_property(scalar(name, value), "", prop)
        library.recompile_material(material)
        assert assetlib.save_loaded_asset(material)
        for variant in CATALOG:
            instance = create(DESTINATION + "/MI_" + variant["id"], unreal.MaterialInstanceConstantFactoryNew())
            library.set_material_instance_parent(instance, material)
            # UE5.8 实现会成功设置/更新但恒返回false，必须读回验收。
            expected_tint = variant["base_color_linear"] + [1.0]
            library.set_material_instance_vector_parameter_value(
                instance, "FloorTint", unreal.LinearColor(*expected_tint))
            actual = library.get_material_instance_vector_parameter_value(instance, "FloorTint")
            assert all(abs(a - b) < 1e-6 for a, b in zip(
                [actual.r, actual.g, actual.b, actual.a], expected_tint))
            for name, value in (("FloorRoughness", 0.72), ("FloorMetallic", 0.0),
                                ("FloorTextureAmplitude", 0.04), ("FloorUVScale", 1.0)):
                library.set_material_instance_scalar_parameter_value(instance, name, value)
                assert abs(library.get_material_instance_scalar_parameter_value(instance, name) - value) < 1e-6
            assert assetlib.save_loaded_asset(instance)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA
        assert component.get_material(0).get_path_name() == CURRENT_FLOOR
        report["source_sha256_after_import"] = SOURCE_SHA
        report["srgb"] = bool(texture.get_editor_property("srgb"))
        report["status"] = "created_not_applied"
        flush()
    except Exception as exc:
        report["status"] = "failed_partial_assets_preserved"
        report["error"] = repr(exc)
        flush()
        raise
    print("FLOOR_BUILD_CREATED " + json.dumps(report))
    return report


if __name__ == "__main__":
    main()
