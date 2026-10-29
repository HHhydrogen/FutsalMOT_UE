"""用已知像素验证近景证据门槛，不能将本测试结果解释为 UE 视觉验收。"""

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

from jersey_number_uv_poc_contract import CASES, evaluate_poc_pixels, validate_poc_config
from jersey_number_uv_poc import _bool_result, _capture_result, _snapshot

_SPEC = importlib.util.spec_from_file_location(
    "jersey_uv_poc_validator", Path(__file__).resolve().parents[1] / "tools/jersey_number_uv_validate_poc.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _config():
    return {"entity_id": "L0", "ue_visual_seed": 42, "translation_cm": [0, 0, 3000],
            "back_axis_local": [0, 1, 0], "target_local_cm": [0, 0, 130],
            "width": 512, "height": 512, "horizontal_fov": 35, "distance_cm": 180,
            "ue_uv_rect": [0.16, 0.24, 0.37, 0.44], "flip_u": True, "flip_v": True}


def test_poc_config_validates_before_mutation():
    assert validate_poc_config(_config())["entity_id"] == "L0"


def test_source_beauty_control_is_explicit_and_defaults_to_number_uv():
    assert validate_poc_config(_config())["beauty_variant"] == "number_uv"
    config = _config()
    config["beauty_variant"] = "source_control"
    assert validate_poc_config(config)["beauty_variant"] == "source_control"
    for value in (True, "unknown", "", None):
        config["beauty_variant"] = value
        with pytest.raises(ValueError):
            validate_poc_config(config)


def test_python_bool_out_parameter_protocol_matches_engine_packer():
    _bool_result("", "cleanup")
    assert _capture_result((170, "")) == 170
    for value in (None, False, (True, ""), "error"):
        with pytest.raises(RuntimeError):
            _bool_result(value, "cleanup")
    for value in (None, (True, 170, ""), (True, ""), (170, "failure"), (-1, "")):
        with pytest.raises(RuntimeError):
            _capture_result(value)


def test_snapshot_compares_numeric_values_instead_of_struct_addresses():
    class Struct:
        sequence = 0

        def __init__(self):
            Struct.sequence += 1
            self.address = Struct.sequence
            self.x, self.y, self.z = 0.0, 0.0, -89.0
            self.pitch, self.yaw, self.roll = 0.0, -90.0, 0.0

        def __str__(self):
            return "<Struct at 0x{:x}>".format(self.address)

    class Object:
        def get_path_name(self):
            return "/Game/test"

    class Mesh(Object):
        def get_skeletal_mesh_asset(self):
            return Object()

        get_world_location = get_world_rotation = get_world_scale = lambda self: Struct()
        get_num_materials = lambda self: 1
        get_material = lambda self, index: Object()
        get_editor_property = lambda self, name: 0

    first, second = _snapshot(Mesh()), _snapshot(Mesh())
    assert first == second
    assert first["location"] == [0.0, 0.0, -89.0]
    assert first["rotation"] == [0.0, -90.0, 0.0]


@pytest.mark.parametrize("key,value", [
    ("width", True), ("height", 4096), ("back_axis_local", [0, 2, 0]),
    ("back_axis_local", [0, 0, 1]), ("translation_cm", [0, float("nan"), 0]),
    ("flip_u", 1), ("distance_cm", 10), ("ue_visual_seed", -1),
])
def test_poc_config_rejects_unsafe_or_ambiguous_values(key, value):
    config = _config()
    config[key] = value
    with pytest.raises(ValueError):
        validate_poc_config(config)


@pytest.fixture
def captured_fixture(tmp_path):
    record = {"mask_id": 32, "number": 37, "restore_verified": True, "source_unchanged": True, "cases": {}}
    for name in CASES:
        rgb = Image.new("RGB", (64, 64), (90, 100, 110))
        mask = Image.new("RGB", rgb.size)
        if name in ("back", "behind_occluder", "partial_occlusion"):
            # 10×10 完整印花；部分遮挡只剩左侧 4×10，bbox 使用半开边界。
            for y in range(11, 21):
                for x in range(7, 11 if name == "partial_occlusion" else 17):
                    mask.putpixel((x, y), (32, 32, 32))
        rgb.save(tmp_path / (name + "_rgb.png"))
        mask.save(tmp_path / (name + "_mask.png"))
        record["cases"][name] = {"engine_frame": 170, "same_game_frame": True, "width": 64, "height": 64,
                                  "rgb": name + "_rgb.png", "mask": name + "_mask.png"}
    path = tmp_path / "capture_report.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_actual_pixel_tight_bbox_and_occlusion_gate(captured_fixture):
    result = _MODULE.validate_capture(captured_fixture)
    assert result["pixel_gate_passed"], result["pixel_gate_errors"]
    assert result["cases"]["back"]["bbox_xyxy"] == [7, 11, 17, 21]
    assert result["cases"]["partial_occlusion"]["bbox_xyxy"] == [7, 11, 11, 21]
    assert result["cases"]["front"]["bbox_xyxy"] is None
    assert result["cases"]["full_occlusion"]["number_pixels"] == 0
    assert result["production_enabled"] is False
    assert result["visual_acceptance"] is False
    assert result["sequence_mrq_synchronization_verified"] is False


@pytest.mark.parametrize("case,color", [("back", (99, 99, 99)), ("front", (32, 32, 32)),
                                        ("full_occlusion", (32, 32, 32)), ("partial_occlusion", (0, 0, 0))])
def test_tonemapping_front_leak_and_missing_occlusion_fail_closed(captured_fixture, case, color):
    path = captured_fixture.parent / (case + "_mask.png")
    Image.new("RGB", (64, 64), color).save(path)
    result = _MODULE.validate_capture(captured_fixture)
    assert not result["pixel_gate_passed"]
    assert result["pixel_gate_errors"]


def test_missing_capture_and_bad_restoration_fail_closed(captured_fixture):
    record = json.loads(captured_fixture.read_text(encoding="utf-8"))
    record["restore_verified"] = False
    record["cases"]["back"]["same_game_frame"] = False
    captured_fixture.write_text(json.dumps(record), encoding="utf-8")
    (captured_fixture.parent / "front_mask.png").unlink()
    result = _MODULE.validate_capture(captured_fixture)
    assert not result["pixel_gate_passed"]
    assert len(result["pixel_gate_errors"]) >= 3


def test_evidence_path_cannot_be_replaced_with_another_case(captured_fixture):
    record = json.loads(captured_fixture.read_text(encoding="utf-8"))
    record["cases"]["front"]["mask"] = "full_occlusion_mask.png"
    captured_fixture.write_text(json.dumps(record), encoding="utf-8")
    result = _MODULE.validate_capture(captured_fixture)
    assert not result["pixel_gate_passed"]
    assert any("文件名与 case 身份不一致" in error for error in result["pixel_gate_errors"])
