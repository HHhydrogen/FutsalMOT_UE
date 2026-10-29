"""材质只读前置证据必须完整，不能把统计数量当作实际绘制成功。"""

from copy import deepcopy

import pytest

from jersey_number_uv_build_mask_preview import EMPTY_PATH, MASKED_PATH, POST_PROCESS_PATH
from jersey_number_uv_build_preview import MATERIAL_PATH, SOURCE_MATERIAL, TEXTURE_PATH
from jersey_number_uv_material_readiness import evaluate_material_readiness


SOURCE_TEXTURE = "/Game/FutsalMOT/Characters/MPFB/Textures/T_MPFB_Jersey_Set_01"


def _record():
    materials = {}
    for path in (SOURCE_MATERIAL, MATERIAL_PATH, MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH):
        textures = [] if path in (EMPTY_PATH, POST_PROCESS_PATH) else [SOURCE_TEXTURE + ".T_MPFB_Jersey_Set_01"]
        if path in (MATERIAL_PATH, MASKED_PATH):
            textures.append(TEXTURE_PATH + ".T_NumberAtlas_UV_v1")
        materials[path] = {
            "class": "Material", "errors": [], "domain_matches_expected": True,
            "blend_matches_expected": True, "used_with_skeletal_mesh": path != POST_PROCESS_PATH,
            "used_with_morph_targets": False, "pixel_shader_instructions": 200,
            "used_textures": textures, "dirty_before": False, "dirty_after": False,
        }
    return {"materials": materials, "dirty_packages_before": [], "dirty_packages": []}


def test_readiness_accepts_complete_prerequisites_without_requiring_unused_morph_permutation():
    assert evaluate_material_readiness(_record()) == []


@pytest.mark.parametrize("field,value", [
    ("class", "MaterialInstanceConstant"), ("errors", ["compile statistics unavailable"]),
    ("domain_matches_expected", False), ("blend_matches_expected", False),
    ("used_with_skeletal_mesh", False), ("used_with_skeletal_mesh", "False"),
    ("pixel_shader_instructions", 0), ("pixel_shader_instructions", True),
    ("dirty_before", True), ("dirty_after", True),
])
def test_preview_missing_or_ambiguous_prerequisites_block_capture(field, value):
    record = _record()
    record["materials"][MATERIAL_PATH][field] = value
    errors = evaluate_material_readiness(record)
    assert errors and any(MATERIAL_PATH in error for error in errors)


def test_missing_atlas_or_source_texture_blocks_preview_even_with_nonzero_statistics():
    for missing in (TEXTURE_PATH, SOURCE_TEXTURE):
        record = _record()
        record["materials"][MATERIAL_PATH]["used_textures"] = [
            path for path in record["materials"][MATERIAL_PATH]["used_textures"]
            if path.split(".", 1)[0] != missing
        ]
        assert any(missing in error for error in evaluate_material_readiness(record))


def test_missing_material_and_global_dirty_state_fail_closed_without_changing_report():
    record = _record()
    del record["materials"][EMPTY_PATH]
    record["dirty_packages"] = ["/Game/UserUnsavedMaterial"]
    before = deepcopy(record)
    assert len(evaluate_material_readiness(record)) >= 2
    assert record == before
