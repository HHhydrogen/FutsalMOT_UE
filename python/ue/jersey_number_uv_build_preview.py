"""为 UV 号码构建独立测试材质；默认仅检查并输出计划，不改正式资产。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jersey_number_uv_contract import UV_NUMBER_POLICY, material_parameters
from jersey_number_uv_shader import CUSTOM_INPUTS, UV_NUMBER_COLOR_HLSL

DESTINATION = "/Game/FutsalMOT/Tests/JerseyNumberUV"
TEXTURE_PATH = DESTINATION + "/T_NumberAtlas_UV_v1"
MATERIAL_PATH = DESTINATION + "/M_Jersey_Set_01_NumberUV_Preview_v1"
SOURCE_MATERIAL = "/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_Jersey_Set_01"


def main():
    import unreal
    import diagnose_episode_appearance as diagnostic

    project = Path(unreal.Paths.project_dir()).resolve()
    evidence = project / "Saved/JerseyNumberUV"
    source = evidence / "atlas_v1/jersey_numbers_01_99.png"
    atlas_record = json.loads((source.with_name("atlas.json")).read_text(encoding="utf-8"))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == atlas_record["png_sha256"]
    assert atlas_record["grid"] == [16, 8]
    mapping = json.loads(Path(__file__).with_name("actor_mapping.example.json").read_text(encoding="utf-8"))
    gate = diagnostic.collect_diagnostic(unreal, mapping)
    assert gate["task7_preflight_can_start"], gate["errors"]
    assert not gate["dirty_package_paths"], gate["dirty_package_paths"]
    apply = os.environ.get("FUTSALMOT_JERSEY_UV_BUILD_APPLY") == "1"
    plan = {"policy": UV_NUMBER_POLICY, "apply": apply, "source_material": SOURCE_MATERIAL,
            "atlas": TEXTURE_PATH, "preview_material": MATERIAL_PATH,
            "production_enabled": False, "acceptance": "NOT_UE_VISUALLY_VERIFIED"}
    for path in (TEXTURE_PATH, MATERIAL_PATH):
        assert not unreal.EditorAssetLibrary.does_asset_exist(path), "拒绝覆盖已有资产: " + path
    if not apply:
        print("JERSEY_UV_PREVIEW_PLAN " + json.dumps(plan))
        return
    library = unreal.MaterialEditingLibrary
    required = ("get_material_property_input_node", "get_material_property_input_node_output_name",
                "create_material_expression", "connect_material_expressions", "connect_material_property")
    assert all(callable(getattr(library, name, None)) for name in required), "MANUAL_REQUIRED: 缺少材质编排 API"
    assert hasattr(unreal, "MaterialExpressionCustom") and hasattr(unreal, "CustomInput"), "MANUAL_REQUIRED: 缺少 CustomExpression API"
    assert hasattr(unreal.MaterialSamplerType, "SAMPLERTYPE_MASKS"), "MANUAL_REQUIRED: Masks sampler enum 未暴露"
    # 全部修改限于新测试资产；不切换地图、不替换球员材质、不进入 MRQ。
    task = unreal.AssetImportTask()
    for key, value in {"filename": str(source), "destination_path": DESTINATION,
                       "destination_name": TEXTURE_PATH.rsplit("/", 1)[-1],
                       "automated": True, "replace_existing": False, "save": False}.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = unreal.load_asset(TEXTURE_PATH)
    assert texture is not None and texture.get_class().get_name() == "Texture2D"
    texture.set_editor_property("srgb", False)
    texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    material = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_MATERIAL, MATERIAL_PATH)
    assert material is not None and material.get_class().get_name() == "Material"
    base = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    assert base is not None, "源球衣缺少 BaseColor 输入，不猜测默认替代材质"
    output_name = library.get_material_property_input_node_output_name(material, unreal.MaterialProperty.MP_BASE_COLOR)
    defaults = material_parameters(37, "L0", [0.16, 0.24, 0.37, 0.44], flip_u=True, flip_v=True)
    nodes = {"BaseColor": (base, output_name)}
    uv = library.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -1600, 200)
    uv.set_editor_property("coordinate_index", 0)
    nodes["UV"] = (uv, "")
    atlas = library.create_material_expression(material, unreal.MaterialExpressionTextureObjectParameter, -1600, 400)
    atlas.set_editor_property("parameter_name", "NumberAtlas")
    atlas.set_editor_property("texture", texture)
    atlas.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    nodes["Atlas"] = (atlas, "")
    for index, (name, input_name) in enumerate((("NumberUVRect", "Rect"), ("NumberUVTransform", "Flips"), ("NumberInkColor", "Ink"))):
        node = library.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -1600, 600 + index * 180)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", unreal.LinearColor(*defaults[name]))
        # Rect 读取 alpha 中的 v1；VectorParameter 默认 RGB 输出会丢失第四分量。
        nodes[input_name] = (node, "RGBA")
    for index, name in enumerate(("NumberIndex", "NumberEnabled", "NumberMaskMode", "NumberMaskID")):
        node = library.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -1200, 600 + index * 180)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(defaults[name]))
        nodes[name] = (node, "")
    custom = library.create_material_expression(material, unreal.MaterialExpressionCustom, -600, 200)
    custom.set_editor_property("description", "UV 号码共享采样；尚未完成 UE 视觉验收")
    custom.set_editor_property("code", UV_NUMBER_COLOR_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    inputs = []
    for name in CUSTOM_INPUTS:
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", name)
        inputs.append(pin)
    custom.set_editor_property("inputs", inputs)
    for name in CUSTOM_INPUTS:
        node, output = nodes[name]
        assert library.connect_material_expressions(node, output, custom, name), name
    assert library.connect_material_property(custom, "", unreal.MaterialProperty.MP_BASE_COLOR)
    library.recompile_material(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(texture)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material)
    (evidence / "preview_assets.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print("JERSEY_UV_PREVIEW_ASSETS_CREATED " + json.dumps(plan))


if __name__ == "__main__":
    main()
