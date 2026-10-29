"""只读记录号码材质和原始材质对照；统计可等待编译，不改资产或 Actor。"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jersey_number_uv_build_preview import MATERIAL_PATH, SOURCE_MATERIAL, TEXTURE_PATH
from jersey_number_uv_build_mask_preview import MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH

SOURCE_TEXTURE = "/Game/FutsalMOT/Characters/MPFB/Textures/T_MPFB_Jersey_Set_01"
MATERIAL_PATHS = (SOURCE_MATERIAL, MATERIAL_PATH, MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH)


def evaluate_material_readiness(record):
    """拒绝缺失的绘制前置证据；通过也不证明 shader map、PSO 或像素正确。"""
    errors = []
    if record.get("dirty_packages_before") != [] or record.get("dirty_packages") != []:
        errors.append("存在 dirty packages，不能进入隔离捕获")
    for path in MATERIAL_PATHS:
        values = record.get("materials", {}).get(path)
        if not isinstance(values, dict):
            errors.append(path + " 缺少只读结果")
            continue
        if values.get("class") != "Material" or values.get("errors") != []:
            errors.append(path + " 资产 class 或诊断调用未通过")
        for key in ("domain_matches_expected", "blend_matches_expected"):
            if values.get(key) is not True:
                errors.append(path + " " + key + " 未通过")
        if path != POST_PROCESS_PATH and values.get("used_with_skeletal_mesh") is not True:
            errors.append(path + " 未声明 SkeletalMesh usage；不自动修改 usage")
        if values.get("dirty_before") is not False or values.get("dirty_after") is not False:
            errors.append(path + " 诊断前后 package 状态不干净")
        count = values.get("pixel_shader_instructions")
        if type(count) is not int or count <= 0:
            errors.append(path + " 没有有效 shader 指令统计，需检查本次编译日志")
        expected = [] if path in (EMPTY_PATH, POST_PROCESS_PATH) else [SOURCE_TEXTURE]
        if path in (MATERIAL_PATH, MASKED_PATH):
            expected.append(TEXTURE_PATH)
        actual = values.get("used_textures")
        if not isinstance(actual, list) or any(not isinstance(item, str) for item in actual):
            errors.append(path + " 缺少纹理依赖结果")
        else:
            packages = {item.split(".", 1)[0] for item in actual}
            for texture in expected:
                if texture not in packages:
                    errors.append(path + " 缺少已编译纹理依赖 " + texture)
    return errors


def _dirty_packages(unreal):
    return sorted(p.get_path_name() for p in (
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())))


def collect_material_readiness(unreal):
    """单个属性失败时保留其它材质证据，不调用 set/recompile/save。"""
    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(), "editor_pid": os.getpid(),
        "production_enabled": False, "visual_acceptance": False, "draw_readiness_verified": False,
        "compile_policy": "get_statistics may submit jobs and FinishCompilation; inspect current UE logs",
        "morph_policy": "仅记录 usage；活动 morph/cloth、shader map 与 PSO 仍需实际绘制证据",
        "dirty_packages_before": _dirty_packages(unreal), "materials": {},
    }
    library = unreal.MaterialEditingLibrary
    for path in MATERIAL_PATHS:
        values = {"errors": [], "dirty_before": path in _dirty_packages(unreal)}
        report["materials"][path] = values
        try:
            material = unreal.load_asset(path)
            values["class"] = material.get_class().get_name() if material is not None else None
            if values["class"] != "Material":
                raise ValueError("资产不存在或 class 不是 Material")
        except Exception as exc:
            values["errors"].append("load: " + str(exc))
            continue
        for key in ("used_with_skeletal_mesh", "used_with_morph_targets", "material_domain", "blend_mode", "blendable_location"):
            try:
                value = material.get_editor_property(key)
                values[key] = bool(value) if key.startswith("used_with_") else str(value)
                if key == "material_domain":
                    expected = unreal.MaterialDomain.MD_POST_PROCESS if path == POST_PROCESS_PATH else unreal.MaterialDomain.MD_SURFACE
                    values["domain_matches_expected"] = value == expected
                elif key == "blend_mode":
                    expected = unreal.BlendMode.BLEND_MASKED if path in (MASKED_PATH, EMPTY_PATH) else unreal.BlendMode.BLEND_OPAQUE
                    values["blend_matches_expected"] = value == expected
            except Exception as exc:
                values["errors"].append(key + ": " + str(exc))
        try:
            # 本机源码会 SubmitCompileJobs/FinishCompilation；该统计不等于实际绘制验收。
            stats = library.get_statistics(material)
            values["pixel_shader_instructions"] = stats.get_editor_property("num_pixel_shader_instructions")
        except Exception as exc:
            values["errors"].append("statistics: " + str(exc))
        try:
            values["used_textures"] = [t.get_path_name() for t in library.get_material_used_textures(material)]
        except Exception as exc:
            values["errors"].append("used_textures: " + str(exc))
        values["dirty_after"] = path in _dirty_packages(unreal)
    report["dirty_packages"] = _dirty_packages(unreal)
    report["capture_precondition_errors"] = evaluate_material_readiness(report)
    report["capture_preconditions_ok"] = not report["capture_precondition_errors"]
    return report


def main():
    import unreal

    report = collect_material_readiness(unreal)
    output = Path(unreal.Paths.project_dir()) / "Saved/JerseyNumberUV/material_readiness.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("JERSEY_UV_MATERIAL_READINESS " + json.dumps(report, ensure_ascii=False))
    assert report["capture_preconditions_ok"], "前置材质证据未通过；报告已保留，不自动修改材质"


if __name__ == "__main__":
    main()
