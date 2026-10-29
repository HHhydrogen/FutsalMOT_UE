"""构建独立的蒙皮号码 alpha/深度测试材质；不换装球员或提交渲染。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jersey_number_uv_build_preview import DESTINATION, MATERIAL_PATH

MASKED_PATH = DESTINATION + "/M_NumberUV_Masked_Preview_v1"
EMPTY_PATH = DESTINATION + "/M_NumberUV_EmptyMasked_Preview_v1"
POST_PROCESS_PATH = DESTINATION + "/M_NumberUV_VisibleStencil_Preview_v1"

VISIBLE_STENCIL_HLSL = """
float ID = floor(Stencil.r + 0.5);
float Visible = (ID >= 32.0 && ID <= 41.0 && CustomDepth.r > 0.0
                 && CustomDepth.r <= SceneDepth.r + max(DepthToleranceCM, 0.0)) ? 1.0 : 0.0;
return (Visible * ID / 255.0).xxx;
""".strip()


def main(resume_completed_masked=False):
    import unreal
    import diagnose_episode_appearance as diagnostic

    evidence = Path(unreal.Paths.project_dir()).resolve() / "Saved/JerseyNumberUV"
    mapping = json.loads(Path(__file__).with_name("actor_mapping.example.json").read_text(encoding="utf-8"))
    gate = diagnostic.collect_diagnostic(unreal, mapping)
    assert gate["task7_preflight_can_start"], gate["errors"]
    assert not gate["dirty_package_paths"], gate["dirty_package_paths"]
    assert unreal.EditorAssetLibrary.does_asset_exist(MATERIAL_PATH), "先验收 UV beauty 测试母材质"
    targets = (MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH)
    for path in targets:
        if resume_completed_masked and path == MASKED_PATH:
            continue
        assert not unreal.EditorAssetLibrary.does_asset_exist(path), "拒绝覆盖: " + path
    apply = os.environ.get("FUTSALMOT_JERSEY_UV_MASK_BUILD_APPLY") == "1"
    report = {"apply": apply, "targets": targets, "production_enabled": False,
              "visual_acceptance": False, "depth_tolerance_cm": 0.2}
    if not apply:
        print("JERSEY_UV_MASK_PREVIEW_PLAN " + json.dumps(report))
        return
    library = unreal.MaterialEditingLibrary
    assert hasattr(unreal.BlendableLocation, "BL_SCENE_COLOR_AFTER_TONEMAPPING"), "MANUAL_REQUIRED: 后处理位置枚举"
    if resume_completed_masked:
        masked = unreal.load_asset(MASKED_PATH)
        alpha = library.get_material_property_input_node(masked, unreal.MaterialProperty.MP_OPACITY_MASK)
        assert masked.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_MASKED
        assert alpha is not None and alpha.get_class().get_name() == "MaterialExpressionComponentMask"
    else:
        masked = unreal.EditorAssetLibrary.duplicate_asset(MATERIAL_PATH, MASKED_PATH)
        custom = library.get_material_property_input_node(masked, unreal.MaterialProperty.MP_BASE_COLOR)
        assert custom.get_class().get_name() == "MaterialExpressionCustom", "源测试材质 graph 不符合契约"
        masked.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        masked.set_editor_property("used_with_skeletal_mesh", True)
        masked.set_editor_property("opacity_mask_clip_value", 0.5)
        alpha = library.create_material_expression(masked, unreal.MaterialExpressionComponentMask, -200, 500)
        for channel in ("r", "g", "b", "a"):
            alpha.set_editor_property(channel, channel == "a")
        # UE 5.8 的该节点只含一个无名输入；空字符串显式选择第一个输入。
        assert library.connect_material_expressions(custom, "", alpha, "")
        assert library.connect_material_property(alpha, "", unreal.MaterialProperty.MP_OPACITY_MASK)

    def create_material(path):
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            path.rsplit("/", 1)[-1], DESTINATION, None, unreal.MaterialFactoryNew())
        assert mat is not None
        return mat

    empty = create_material(EMPTY_PATH)
    empty.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    empty.set_editor_property("used_with_skeletal_mesh", True)
    zero = library.create_material_expression(empty, unreal.MaterialExpressionConstant)
    zero.set_editor_property("r", 0.0)
    assert library.connect_material_property(zero, "", unreal.MaterialProperty.MP_OPACITY_MASK)

    post = create_material(POST_PROCESS_PATH)
    post.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    post.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    pp_custom = library.create_material_expression(post, unreal.MaterialExpressionCustom)
    pp_custom.set_editor_property("code", VISIBLE_STENCIL_HLSL)
    pp_custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    names = ("SceneDepth", "CustomDepth", "Stencil", "DepthToleranceCM")
    inputs = []
    for name in names:
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", name)
        inputs.append(pin)
    pp_custom.set_editor_property("inputs", inputs)
    for name, enum_name in zip(names[:3], ("PPI_SCENE_DEPTH", "PPI_CUSTOM_DEPTH", "PPI_CUSTOM_STENCIL")):
        node = library.create_material_expression(post, unreal.MaterialExpressionSceneTexture)
        node.set_editor_property("scene_texture_id", getattr(unreal.SceneTextureId, enum_name))
        # SceneTexture 输出为 Color/Size/InvSize，颜色分量在 HLSL 中显式读取 .r。
        assert library.connect_material_expressions(node, "Color", pp_custom, name)
    tolerance = library.create_material_expression(post, unreal.MaterialExpressionScalarParameter)
    tolerance.set_editor_property("parameter_name", "DepthToleranceCM")
    tolerance.set_editor_property("default_value", 0.2)
    assert library.connect_material_expressions(tolerance, "", pp_custom, "DepthToleranceCM")
    assert library.connect_material_property(pp_custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    report["statistics"] = {}
    for path, mat in zip(targets, (masked, empty, post)):
        library.recompile_material(mat)
        stats = library.get_statistics(mat)
        report["statistics"][path] = {"pixel_shader_instructions": stats.get_editor_property("num_pixel_shader_instructions")}
        assert unreal.EditorAssetLibrary.save_loaded_asset(mat), path
    (evidence / "mask_preview_assets.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("JERSEY_UV_MASK_PREVIEW_CREATED " + json.dumps(report))


if __name__ == "__main__":
    main()
