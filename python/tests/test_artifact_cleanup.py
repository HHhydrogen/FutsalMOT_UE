"""Artifact cleanup 的球衣号码 v2 回归测试。"""

import json
from pathlib import Path

from grf_ue_bridge.workflows.artifact_cleanup import apply_cleanup, plan_cleanup


def _resolved(tmp_path, policy="futsalmot_appearance_v2"):
    return {
        "task_id": "jersey-cleanup-test",
        "repo_root": str(tmp_path),
        "ue_profile": {"appearance": {"policy": policy}},
        "postprocess": {"yolo_pose": {"enabled": False}},
    }


def _episode(tmp_path, application_state="restored", audit_passed=True):
    episode = tmp_path / "episode"
    camera = episode / "Camera_01"
    (camera / "number_mask").mkdir(parents=True)
    (camera / "render_number_mask").mkdir()
    (episode / "provenance").mkdir(parents=True)
    (episode / "audit").mkdir()
    (camera / "number_mask" / "000001.png").write_bytes(b"number")
    (camera / "render_number_mask" / "000001.png").write_bytes(b"render-number")
    (camera / "annotations.jsonl").write_text(
        json.dumps({
            "frame_index": 1,
            "objects": [{
                "entity_id": "L0",
                "jersey_number": {
                    "value": 17,
                    "bbox_source": "visible_number_mask",
                    "visible_pixel_count": 3,
                    "bbox_xyxy": [1, 1, 2, 2],
                    "bbox_xywh": [1, 1, 1, 1],
                },
            }],
        }) + "\n",
        encoding="utf-8",
    )
    (episode / "provenance" / "appearance_application.json").write_text(
        json.dumps({"state": application_state}), encoding="utf-8"
    )
    (episode / "audit" / "soak_audit_report.json").write_text(
        json.dumps({
            "passed": audit_passed,
            "exit_code": 0 if audit_passed else 1,
            "errors": [] if audit_passed else ["number audit failed"],
            "warnings": [],
            "checks": {},
        }),
        encoding="utf-8",
    )
    return episode, camera


def _write_v2_passing_audit(episode):
    (episode / "audit" / "soak_audit_report.json").write_text(
        json.dumps({
            "passed": True,
            "exit_code": 0,
            "errors": [],
            "warnings": [],
            "checks": {
                "jersey_number_mask": {
                    "status": "passed",
                    "required": True,
                }
            },
        }),
        encoding="utf-8",
    )


def test_apply_cleanup_blocks_v2_number_masks_until_appearance_restored(tmp_path):
    episode, camera = _episode(tmp_path, application_state="applied")

    planned = plan_cleanup(
        episode, ["Camera_01"], resolved=_resolved(tmp_path)
    )

    result = apply_cleanup(
        episode, ["Camera_01"], resolved=_resolved(tmp_path)
    )

    assert result["ok"] is False
    assert result["reason"] == "validation_gate_failed"
    assert planned["blocked_delete"] is True
    assert (camera / "number_mask" / "000001.png").exists()
    assert (camera / "render_number_mask" / "000001.png").exists()


def test_restored_v2_cleanup_dry_run_and_apply_preserve_canonical_numbers(tmp_path):
    episode, camera = _episode(tmp_path)
    _write_v2_passing_audit(episode)
    resolved = _resolved(tmp_path)
    expected = {
        str(camera / "number_mask" / "000001.png"),
        str(camera / "render_number_mask" / "000001.png"),
    }

    dry_run = plan_cleanup(episode, ["Camera_01"], resolved=resolved)

    assert dry_run["gate_ok"] is True
    assert expected.issubset(set(dry_run["would_delete"]))
    assert all(Path(path).exists() for path in expected)

    result = apply_cleanup(episode, ["Camera_01"], resolved=resolved)

    assert result["ok"] is True
    assert result["deleted_files"] == 2
    assert all(not Path(path).exists() for path in expected)
    annotation = json.loads((camera / "annotations.jsonl").read_text(encoding="utf-8"))
    assert annotation["objects"][0]["jersey_number"]["value"] == 17
    assert annotation["objects"][0]["jersey_number"]["bbox_xyxy"] == [1, 1, 2, 2]


def test_v2_cleanup_rejects_generic_passed_audit_without_required_number_check(tmp_path):
    episode, camera = _episode(tmp_path)

    result = apply_cleanup(episode, ["Camera_01"], resolved=_resolved(tmp_path))

    assert result["ok"] is False
    assert any("jersey_number_mask" in problem for problem in result["gate_problems"])
    assert (camera / "number_mask" / "000001.png").exists()


def test_legacy_policy_does_not_collect_residual_number_masks(tmp_path):
    episode, camera = _episode(tmp_path)

    report = plan_cleanup(
        episode,
        ["Camera_01"],
        resolved=_resolved(tmp_path, policy="futsalmot_appearance_v1"),
    )

    assert not any("number_mask" in path for path in report["would_delete"])
    assert (camera / "number_mask" / "000001.png").exists()


def test_environment_cleanup_blocks_unresolved_report_and_preserves_provenance(tmp_path):
    episode, camera = _episode(tmp_path, application_state="restored")
    resolved = _resolved(tmp_path, policy="futsalmot_appearance_v1")
    resolved["ue_profile"]["environment_profile"] = {
        "policy": "futsalmot_environment_v1_5",
        "catalog_id": "futsalmot_indoor_environment_v1_5",
        "environment_seed": 42,
        "preset": "daylight_clear_v1",
        "catalog_fingerprint": "a" * 64,
    }
    (episode / "provenance" / "environment.json").write_text(
        json.dumps({"schema": "futsalmot_episode_environment"}),
        encoding="utf-8",
    )
    (episode / "provenance" / "environment_application.json").write_text(
        json.dumps({"state": "rendering"}), encoding="utf-8"
    )

    result = apply_cleanup(episode, ["Camera_01"], resolved=resolved)

    assert result["ok"] is False
    assert any("environment" in problem for problem in result["gate_problems"])
    assert any("state actual='rendering'" in problem for problem in result["gate_problems"])
    assert (episode / "provenance" / "environment.json").exists()
    assert (camera / "number_mask" / "000001.png").exists()


def test_environment_cleanup_accepts_retired_local_report_with_restored_public(tmp_path):
    episode, _camera = _episode(tmp_path, application_state="restored")
    resolved = _resolved(tmp_path, policy="futsalmot_appearance_v1")
    resolved["ue_profile"]["environment_profile"] = {
        "policy": "futsalmot_environment_v1_5",
        "catalog_id": "futsalmot_indoor_environment_v1_5",
        "environment_seed": 42,
        "preset": "daylight_clear_v1",
        "catalog_fingerprint": "a" * 64,
    }
    (episode / "provenance" / "environment.json").write_text(
        json.dumps({"schema": "futsalmot_episode_environment"}), encoding="utf-8"
    )
    (episode / "provenance" / "environment_application.json").write_text(
        json.dumps({"state": "restored"}), encoding="utf-8"
    )

    result = apply_cleanup(episode, ["Camera_01"], resolved=resolved)

    assert not any("缺少本机 application report" in problem for problem in result["gate_problems"])