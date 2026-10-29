"""保留五套随机球衣原图的 UV 号码材质；只创建独立派生资产。"""

import json
from pathlib import Path

from jersey_number_uv_build_preview import TEXTURE_PATH
from jersey_number_uv_shader import CUSTOM_INPUTS, UV_NUMBER_COLOR_HLSL
from jersey_number_uv_contract import material_parameters

DESTINATION = "/Game/FutsalMOT/Characters/MPFB/Materials/JerseyNumbersUV_v1"


def build_catalog(unreal):
    """每套从其自身原材质复制；不同套装绝不共用 Set_01 的外观输入。"""
    from diagnose_episode_environment import _runtime_state
    from episode_appearance import _dirty_package_paths
    runtime, errors = _runtime_state(unreal)
    if errors or runtime["play_session_active"] or runtime["mrq_state"] != "inactive":
        raise RuntimeError("材质创建要求空闲 Editor: {}".format(errors))
    if _dirty_package_paths(unreal):
        raise RuntimeError("存在未保存 package，先核对来源")
    atlas = unreal.load_asset(TEXTURE_PATH)
    if atlas is None:
        raise RuntimeError("缺少已验号码图集: " + TEXTURE_PATH)
    library = unreal.MaterialEditingLibrary
    defaults = material_parameters(37, "L0", [0.16, 0.24, 0.37, 0.44], flip_u=True, flip_v=True)
    record = {"schema": "futsalmot_uv_number_material_catalog_v1", "atlas": TEXTURE_PATH, "kits": {}}
    for number in range(1, 6):
        kit = "{:02d}".format(number)
        source = "/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_Jersey_Set_" + kit
        target = DESTINATION + "/M_Jersey_Set_" + kit + "_NumberUV_v1"
        if unreal.EditorAssetLibrary.does_asset_exist(target):
            raise RuntimeError("拒绝覆盖已有派生材质: " + target)
        material = unreal.EditorAssetLibrary.duplicate_asset(source, target)
        if material is None:
            raise RuntimeError("复制球衣失败: " + source)
        base = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
        output = library.get_material_property_input_node_output_name(material, unreal.MaterialProperty.MP_BASE_COLOR)
        if base is None:
            raise RuntimeError("原球衣缺少 BaseColor 输入: " + source)
        nodes = {"BaseColor": (base, output)}
        uv = library.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -1600, 200)
        uv.set_editor_property("coordinate_index", 0)
        nodes["UV"] = (uv, "")
        texture = library.create_material_expression(material, unreal.MaterialExpressionTextureObjectParameter, -1600, 400)
        texture.set_editor_property("parameter_name", "NumberAtlas")
        texture.set_editor_property("texture", atlas)
        texture.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        nodes["Atlas"] = (texture, "")
        for i, (name, pin) in enumerate((("NumberUVRect", "Rect"), ("NumberUVTransform", "Flips"), ("NumberInkColor", "Ink"))):
            node = library.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -1600, 600 + i * 180)
            node.set_editor_property("parameter_name", name)
            node.set_editor_property("default_value", unreal.LinearColor(*defaults[name]))
            nodes[pin] = (node, "RGBA")
        for i, name in enumerate(("NumberIndex", "NumberEnabled", "NumberMaskMode", "NumberMaskID")):
            node = library.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -1200, 600 + i * 180)
            node.set_editor_property("parameter_name", name)
            node.set_editor_property("default_value", float(defaults[name]))
            nodes[name] = (node, "")
        custom = library.create_material_expression(material, unreal.MaterialExpressionCustom, -600, 200)
        custom.set_editor_property("description", "保留原套装输入的背部 UV 号码")
        custom.set_editor_property("code", UV_NUMBER_COLOR_HLSL)
        custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT4)
        pins = []
        for name in CUSTOM_INPUTS:
            pin = unreal.CustomInput()
            pin.set_editor_property("input_name", name)
            pins.append(pin)
        custom.set_editor_property("inputs", pins)
        for name, (node, channel) in nodes.items():
            if not library.connect_material_expressions(node, channel, custom, name):
                raise RuntimeError("连接号码输入失败: " + name)
        if not library.connect_material_property(custom, "", unreal.MaterialProperty.MP_BASE_COLOR):
            raise RuntimeError("连接 BaseColor 失败")
        material.set_editor_property("used_with_skeletal_mesh", True)
        material.set_editor_property("used_with_morph_targets", True)
        library.recompile_material(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material):
            raise RuntimeError("保存派生球衣失败: " + target)
        record["kits"][kit] = {"source_material": source, "number_material": target}
    path = Path(unreal.Paths.project_dir()) / "Saved/JerseyNumberUV/catalog_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    import unreal
    print("NUMBER_UV_CATALOG " + json.dumps(build_catalog(unreal), ensure_ascii=False))
