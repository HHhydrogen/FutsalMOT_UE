"""球衣号码可见 mask 可行性门禁的纯 Python 契约测试。"""

import json

import pytest

from diagnose_jersey_number_mask import (
    _read_with_retry,
    build_render_contract_report,
    validate_v2_render_evidence,
)


def _valid_report_inputs():
    return {
        "current_level_path": "/Game/FutsalMOT/Maps/L_FutsalCourt",
        "decal_component_capabilities": {
            "available": True,
            "back_placement": True,
            "material_parameter": True,
        },
        "proxy_custom_depth_capabilities": {
            "api_inventory": {
                "component_class_available": True,
                "custom_depth_property_api_available": True,
                "stencil_property_api_available": True,
            },
            "frame_readback": {
                "probe_executed": True,
                "evidence_source": "temporary_scene_capture_pixel_readback",
                "custom_depth_enabled": True,
                "stencil_value": 37,
                "readback_stencil_value": 37,
                "stencil_pixel_count": 64,
            },
        },
        "mrq_mask_output_capabilities": {
            "api_inventory": {
                "mask_pass_class_available": True,
                "image_output_class_available": True,
            },
            "synchronized_frame_evidence": {
                "probe_executed": True,
                "evidence_source": "temporary_mrq_output_files",
                "same_job": True,
                "rgb_frame_ids": ["000000"],
                "mask_frame_ids": ["000000"],
            },
        },
        "occlusion_probe": {
            "front_mask_empty": True,
            "back_mask_has_pixels": True,
            "occluded_pixels_hidden": True,
            "probe_executed": True,
            "evidence_source": "temporary_scene_capture_pixel_readback",
            "pixel_counts": {"front": 0, "back": 100, "occluded": 0},
        },
        "probe_lifecycle": {
            operation: {
                "status": "verified",
                "evidence_source": "executed_probe",
                "detail": "verified and cleaned",
            }
            for operation in (
                "isolated_world_creation",
                "temporary_actor_cleanup",
                "stencil_mask_generation",
                "mrq_executor_terminal_callback",
                "mrq_output_cleanup",
            )
        },
    }


def _valid_v2_render_evidence(material_path="/Game/FutsalMOT/Materials/M_StencilToID"):
    return {
        "appearance_preflight": {
            "task7_preflight_can_start": True,
            "numbering_visual_gate": "verified",
        },
        "diagnostic": build_render_contract_report(**_valid_report_inputs()),
        "number_mask_material": {
            "path": material_path,
            "exists": True,
            "actual_class": "Material",
            "evidence_source": "ue_asset_data",
        },
    }


def test_missing_proxy_mask_capability_blocks_contract():
    inputs = _valid_report_inputs()
    inputs["proxy_custom_depth_capabilities"]["api_inventory"][
        "component_class_available"
    ] = False

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "proxy_custom_depth_capabilities" in report["errors"]


def test_unsynchronized_mask_pass_blocks_contract():
    inputs = _valid_report_inputs()
    inputs["mrq_mask_output_capabilities"]["synchronized_frame_evidence"][
        "mask_frame_ids"
    ] = ["000001"]

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "mrq_mask_output_capabilities" in report["errors"]


def test_failed_occlusion_probe_blocks_contract():
    inputs = _valid_report_inputs()
    inputs["occlusion_probe"]["occluded_pixels_hidden"] = False

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "occlusion_probe" in report["errors"]


def test_complete_evidence_passes_and_is_json_serializable():
    report = build_render_contract_report(**_valid_report_inputs())

    assert report["ok"] is True
    assert report["errors"] == []
    assert json.loads(json.dumps(report, sort_keys=True)) == report


def test_boolean_occlusion_claims_without_executed_provenance_are_rejected():
    inputs = _valid_report_inputs()
    inputs["occlusion_probe"]["probe_executed"] = False
    inputs["occlusion_probe"]["evidence_source"] = "not_executed_read_only_probe"

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "occlusion_probe" in report["errors"]


def test_proxy_api_inventory_without_frame_readback_is_rejected():
    inputs = _valid_report_inputs()
    inputs["proxy_custom_depth_capabilities"].pop("frame_readback")

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "proxy_custom_depth_capabilities" in report["errors"]


def test_mrq_api_inventory_without_synchronized_frames_is_rejected():
    inputs = _valid_report_inputs()
    inputs["mrq_mask_output_capabilities"].pop("synchronized_frame_evidence")

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "mrq_mask_output_capabilities" in report["errors"]


def test_repeated_read_failure_returns_manual_required_after_two_attempts():
    attempts = []
    errors = []

    def fail():
        attempts.append("attempt")
        raise RuntimeError("unavailable")

    result = _read_with_retry("pixel_readback", fail, errors)

    assert result is None
    assert len(attempts) == 2
    assert errors[-1] == "MANUAL_REQUIRED: pixel_readback 连续失败两次"


def test_missing_probe_lifecycle_operation_is_reported_and_blocks_gate():
    inputs = _valid_report_inputs()
    inputs["probe_lifecycle"].pop("isolated_world_creation")

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "MANUAL_REQUIRED: isolated_world_creation: evidence unavailable" in report[
        "errors"
    ]


def test_api_inventory_is_not_probe_lifecycle_verification():
    inputs = _valid_report_inputs()
    inputs["probe_lifecycle"]["mrq_executor_terminal_callback"] = {
        "status": "available_inventory_only",
        "evidence_source": "api_inventory",
        "detail": "delegate symbol exists",
    }

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "MANUAL_REQUIRED: mrq_executor_terminal_callback: delegate symbol exists" in report[
        "errors"
    ]


@pytest.mark.parametrize(
    "operation",
    (
        "isolated_world_creation",
        "temporary_actor_cleanup",
        "stencil_mask_generation",
        "mrq_executor_terminal_callback",
        "mrq_output_cleanup",
    ),
)
def test_each_lifecycle_operation_requires_executed_evidence(operation):
    inputs = _valid_report_inputs()
    inputs["probe_lifecycle"][operation] = {
        "status": "available_unverified",
        "evidence_source": "api_inventory",
        "detail": "API symbol exists",
    }

    report = build_render_contract_report(**inputs)

    assert report["ok"] is False
    assert "MANUAL_REQUIRED: {}: API symbol exists".format(operation) in report["errors"]


def test_complete_v2_render_evidence_passes_pure_validator():
    evidence = _valid_v2_render_evidence()

    result = validate_v2_render_evidence(
        evidence,
        "/Game/FutsalMOT/Materials/M_StencilToID",
    )

    assert result == {
        "ok": True,
        "errors": [],
        "number_mask_post_process_material": (
            "/Game/FutsalMOT/Materials/M_StencilToID"
        ),
    }


@pytest.mark.parametrize("exists, actual_class", [(False, "Material"), (True, "Texture2D")])
def test_v2_render_evidence_rejects_missing_or_wrong_material_class(exists, actual_class):
    evidence = _valid_v2_render_evidence()
    evidence["number_mask_material"]["exists"] = exists
    evidence["number_mask_material"]["actual_class"] = actual_class

    result = validate_v2_render_evidence(evidence)

    assert result["ok"] is False
    assert any("class=Material" in error for error in result["errors"])


def test_v2_render_evidence_rejects_material_path_mismatch():
    evidence = _valid_v2_render_evidence()

    result = validate_v2_render_evidence(
        evidence,
        "/Game/FutsalMOT/Materials/M_OtherNumberMask",
    )

    assert result["ok"] is False
    assert any("path 与结构化 asset evidence 不一致" in error for error in result["errors"])
