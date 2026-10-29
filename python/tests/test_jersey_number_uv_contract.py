"""验证 UV 印花输入、既有号码协议兼容性和校准门禁。"""

import random

import pytest

from grf_ue_bridge.appearance import _assign_jersey_numbers, derive_jersey_number_seed
from jersey_number_uv_contract import (
    SOURCE_JERSEY_UV_TOPOLOGY, assign_numbers, atlas_cell, canonical_fingerprint,
    map_uv_to_atlas, material_parameters, validate_calibration, validate_uv_rect,
)


@pytest.mark.parametrize("seed", [0, 42, 47, 1001, 0x7fffffff])
def test_assignment_preserves_existing_number_byte_protocol_without_rng(seed):
    before = random.getstate()
    result = assign_numbers(seed)
    assert result == _assign_jersey_numbers(derive_jersey_number_seed(seed))
    assert len(result) == len(set(result.values())) == 10
    assert all(1 <= number <= 99 for number in result.values())
    assert random.getstate() == before


@pytest.mark.parametrize("bad", [True, -1, 2**31, 1.0, "42"])
def test_seed_rejects_ambiguous_values(bad):
    with pytest.raises(ValueError):
        assign_numbers(bad)


def test_many_seeds_change_combinations_and_cover_number_range():
    results = [assign_numbers(seed) for seed in range(128)]
    assert len({tuple(result.values()) for result in results}) == 128
    assert {value for result in results for value in result.values()} == set(range(1, 100))


def test_cell_layout_is_unique_and_leaves_last_cell_unused():
    cells = [atlas_cell(number) for number in range(1, 100)]
    assert len(set(cells)) == 99
    assert cells[0] == (0, 0)
    assert cells[9] == (9, 0)
    assert cells[10] == (10, 0)
    assert cells[15] == (15, 0)
    assert cells[16] == (0, 1)
    assert cells[-1] == (2, 6)
    assert (15, 7) not in cells


@pytest.mark.parametrize("bad", [0, 100, True, 17.0, "17"])
def test_invalid_number_never_reaches_material(bad):
    with pytest.raises(ValueError):
        atlas_cell(bad)


@pytest.mark.parametrize("bad", [None, [0, 0, 0, 1], [0, 0, 1, 2], [0, 0, float("nan"), 1], [False, 0, 1, 1]])
def test_invalid_or_degenerate_rect_is_rejected(bad):
    with pytest.raises(ValueError):
        validate_uv_rect(bad)


def test_outside_uv_never_activates_number_and_flips_keep_same_cell():
    rect = [0.15, 0.65, 0.35, 0.85]
    u, v, inside = map_uv_to_atlas([0.2, 0.2], 37, rect)
    assert inside is False
    assert (u, v) == pytest.approx((4.25 / 16, 2 / 8))
    assert map_uv_to_atlas([0.15, 0.65], 37, rect) == pytest.approx((4 / 16, 2 / 8, True))
    assert map_uv_to_atlas([0.15, 0.65], 37, rect, flip_u=True, flip_v=True) == pytest.approx((5 / 16, 3 / 8, True))


def test_render_and_mask_use_identical_number_and_uv_inputs():
    kwargs = dict(number=37, entity_id="R4", rect=[0.15, 0.65, 0.35, 0.85], flip_v=True)
    rgb = material_parameters(**kwargs)
    mask = material_parameters(**kwargs, mask_mode=True)
    assert rgb["NumberIndex"] == mask["NumberIndex"] == 36
    assert rgb["NumberMaskID"] == mask["NumberMaskID"] == 41
    assert rgb["NumberUVRect"] == mask["NumberUVRect"]
    assert rgb["NumberUVTransform"] == mask["NumberUVTransform"]
    assert rgb["NumberMaskMode"] == 0
    assert mask["NumberMaskMode"] == 1


def _accepted_calibration():
    return {
        "ue_uv_rect": [0.15, 0.65, 0.35, 0.85],
        "source_uv_topology_sha256": SOURCE_JERSEY_UV_TOPOLOGY,
        "ue_mesh_uv_verified": True, "back_visible_verified": True,
        "front_empty_verified": True, "animation_verified": True,
        "occlusion_verified": True, "paired_mask_verified": True,
        "mesh": "/Game/Test/Mesh", "camera": "TestBackCamera",
        "sequence": "/Game/Test/Sequence", "frame_index": 1,
        "evidence_rgb": "test/rgb.png", "evidence_number_mask": "test/mask.png",
    }


def test_source_uv_evidence_alone_cannot_enable_production():
    assert validate_calibration({"source_uv_topology_sha256": SOURCE_JERSEY_UV_TOPOLOGY})
    accepted = _accepted_calibration()
    assert validate_calibration(accepted) == []
    accepted["paired_mask_verified"] = False
    assert validate_calibration(accepted) == ["缺少 paired_mask_verified 验收"]


def test_contract_fingerprint_is_order_independent_and_binds_position():
    assert canonical_fingerprint({"b": 2, "a": 1}) == canonical_fingerprint({"a": 1, "b": 2})
    before = _accepted_calibration()
    after = dict(before, ue_uv_rect=[0.15, 0.66, 0.35, 0.85])
    assert canonical_fingerprint(before) != canonical_fingerprint(after)
