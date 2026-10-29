"""Task audit 的球衣号码 v2 回归测试。"""

import json
import sys
from pathlib import Path

from PIL import Image
import pytest

_UE_DIR = Path(__file__).resolve().parents[1] / "ue"
if str(_UE_DIR) not in sys.path:
    sys.path.insert(0, str(_UE_DIR))

from episode_appearance import create_application_report
from grf_ue_bridge.appearance import build_appearance_manifest
from grf_ue_bridge.environment import (
    ENVIRONMENT_CATALOG_ID,
    build_environment_manifest,
    build_environment_parameters,
    derive_environment_namespace_seed,
    environment_catalog_fingerprint,
)
from grf_ue_bridge.workflows.task_audit import (
    _check_v2_render_summary_jobs,
    check_appearance,
    check_camera,
    check_environment,
    main as audit_main,
)
import episode_environment


def _catalog_v2():
    catalog = {
        "mode": "seeded",
        "policy": "futsalmot_appearance_v2",
        "catalog_id": "mpfb_players_003_009_v2",
        "body_texture_parameter": "SkinTexture",
        "models": [
            {
                "player_id": index,
                "mesh": f"/Game/Players/Player_{index:03d}",
                "anim_class": "/Game/Characters/ABP_Player",
                "skeleton": "/Game/Characters/SKEL_Player",
            }
            for index in range(3, 10)
        ],
        "skins": [
            {"skin_id": f"skin-{index:02d}", "texture": f"/Game/Skins/T_Skin_{index:02d}"}
            for index in range(1, 10)
        ],
        "kits": [
            {
                "set_id": f"{index:02d}",
                "jersey_material": f"/Game/Kits/M_Jersey_{index:02d}",
                "shorts_material": f"/Game/Kits/M_Shorts_{index:02d}",
            }
            for index in range(1, 6)
        ],
        "numbering": {
            "min": 1,
            "max": 99,
            "unique": True,
            "placement": "back",
            "bone": "spine_03",
            "atlas": "/Game/Numbers/T_Atlas",
            "decal_material": "/Game/Numbers/M_Decal",
            "parameter": "NumberIndex",
            "mask_proxy_mesh": "/Game/Numbers/SM_Proxy",
            "mask_proxy_material": "/Game/Numbers/M_Mask",
            "mask_post_process_material": "/Game/Numbers/M_PostProcess",
            "mask_stencil_start": 32,
        },
    }
    return catalog


def _appearance_v2_files(root: Path):
    entity_ids = [f"L{index}" for index in range(5)] + [f"R{index}" for index in range(5)]
    meta = {
        "schema": "grf_ue_episode",
        "version": 1,
        "episode_id": root.name,
        "source": {"seed": 42},
        "randomness": {"root_seed": 42, "ue_visual_seed": 1001},
        "entities": [
            {
                "id": entity_id,
                "team": "left" if entity_id.startswith("L") else "right",
                "is_goalkeeper": entity_id in {"L2", "R1"},
            }
            for entity_id in entity_ids
        ],
    }
    frames_path = root / "frames.jsonl"
    frames_path.write_text('{"step":0}\n', encoding="utf-8")
    manifest = build_appearance_manifest(meta, frames_path, _catalog_v2())
    provenance = root / "provenance"
    provenance.mkdir(parents=True)
    (root / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (provenance / "appearance.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = create_application_report(
        manifest, {entity_id: f"Player_{entity_id}" for entity_id in entity_ids}
    )
    report["actors"][0]["jersey_number"] = 98
    report["state"] = "applied"
    report["mrq_jobs"] = [{
        "camera_id": "Camera_01",
        "kind": "jersey_number_mask",
        "status": "failed",
        "number_mask_frames": 1,
    }]
    report["render_result"] = {
        "status": "partial",
        "jobs": report["mrq_jobs"],
        "cameras": {"Camera_01": {"ok": False, "number_mask_frames": 2}},
    }
    (provenance / "appearance_application.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    return manifest, report


def test_audit_requires_complete_number_mask_frame_set(tmp_path):
    camera = tmp_path / "Camera_01"
    (camera / "img1").mkdir(parents=True)
    (camera / "number_mask").mkdir()
    (camera / "img1" / "000001.png").write_bytes(b"rgb")
    (camera / "img1" / "000002.png").write_bytes(b"rgb")
    Image.new("L", (4, 4), 0).save(camera / "number_mask" / "000001.png")
    (camera / "annotations.jsonl").write_text(
        '{"frame_index":1,"objects":[]}\n{"frame_index":2,"objects":[]}\n',
        encoding="utf-8",
    )
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 4,
        "image_height": 4,
        "intrinsics": {"width": 4, "height": 4, "fx": 2, "fy": 2, "cx": 2, "cy": 2},
        "extrinsics": {"world_location_m": [0, 0, 0], "forward": [1, 0, 0], "right": [0, 1, 0], "up": [0, 0, 1]},
    }), encoding="utf-8")
    errors = []

    state = check_camera(
        camera,
        expected_frames=2,
        keep_indices=[0, 1],
        errors=errors,
        warns=[],
        mask_enabled=False,
        render_required=False,
        number_mask_required=True,
    )

    assert state["number_mask_complete"] is False
    assert any("Camera_01" in error and "frame 2" in error for error in errors)


def test_audit_requires_complete_number_mask_render_job(tmp_path):
    _appearance_v2_files(tmp_path)
    (tmp_path / "render_summary.json").write_text(json.dumps({
        "status": "success",
        "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
        "jobs": [{
            "camera_id": "Camera_01",
            "kind": "jersey_number_mask",
            "status": "failed",
            "number_mask_frames": 1,
        }],
    }), encoding="utf-8")
    provenance = tmp_path / "provenance" / "appearance_application.json"
    application = json.loads(provenance.read_text(encoding="utf-8"))
    application["mrq_jobs"] = [{
        "camera_id": "Camera_01", "kind": "jersey_number_mask",
        "status": "failed", "number_mask_frames": 1,
    }]
    application["render_result"] = {
        "status": "partial",
        "jobs": application["mrq_jobs"],
        "cameras": {"Camera_01": {"ok": False, "number_mask_frames": 2}},
    }
    application["state"] = "restored"
    for actor in application.get("actors", []):
        if isinstance(actor, dict):
            actor["apply_status"] = "applied"
            actor["restore_status"] = "restored"
            actor["jersey_number"] = next(
                entity["jersey_number"]
                for entity in json.loads(
                    (tmp_path / "provenance" / "appearance.json").read_text(encoding="utf-8")
                )["entities"]
                if entity["entity_id"] == actor["entity_id"]
            )
    application["render_result"]["jobs"] = application["mrq_jobs"]
    provenance.write_text(json.dumps(application), encoding="utf-8")
    errors = []

    state = check_appearance(
        tmp_path,
        errors,
        render_required=True,
        appearance_catalog=_catalog_v2(),
        expected_camera_ids=["Camera_01"],
        expected_frames_per_camera=2,
        render_summary={
            "status": "success",
            "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
            "jobs": [{
                "camera_id": "Camera_01",
                "kind": "jersey_number_mask",
                "status": "failed",
                "number_mask_frames": 1,
            }],
        },
    )

    assert state["ok"] is False
    assert any(
        "Camera_01" in error and "frame *" in error and "entity *" in error
        and "actual=1" in error and "expected=2" in error
        for error in errors
    )


def _valid_v2_render_summary_job(*, frames=2, source="custom_depth_stencil_png"):
    return {
        "camera_id": "Camera_01",
        "kind": "jersey_number_mask",
        "status": "success",
        "number_mask_frames": frames,
        "number_mask_source": source,
        "target_indices": [0, 1],
        "output_resolution": [4, 4],
    }


def _make_valid_v2_application_report(root: Path):
    application_path = root / "provenance" / "appearance_application.json"
    application = json.loads(application_path.read_text(encoding="utf-8"))
    manifest = json.loads(
        (root / "provenance" / "appearance.json").read_text(encoding="utf-8")
    )
    job = _valid_v2_render_summary_job()
    application["state"] = "restored"
    application["mrq_jobs"] = [job]
    application["render_result"] = {
        "status": "success",
        "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
        "jobs": [job],
    }
    numbers = {
        entity["entity_id"]: entity["jersey_number"]
        for entity in manifest["entities"]
    }
    for actor in application.get("actors", []):
        actor["apply_status"] = "applied"
        actor["restore_status"] = "restored"
        actor["jersey_number"] = numbers[actor["entity_id"]]
        component = actor["number_component"]
        component["apply_status"] = "applied"
        component["restore_status"] = "restored"
        component["attachment_status"] = "verified"
        component["readback"] = {
            "stencil_value": 32 + [
                entity["entity_id"] for entity in manifest["entities"]
            ].index(actor["entity_id"]),
            "attach_parent": "MPFBVisual",
            "attach_bone": "spine_03",
            "number_index": actor["jersey_number"] - 1,
            "placement": "back",
            "decal_component_name": "JerseyNumberBack",
            "mask_proxy_component_name": "JerseyNumberMaskProxy",
            "decal_exists": True,
            "mask_proxy_exists": True,
            "decal_component_path": "/Game/Test/JerseyNumberBack",
            "mask_proxy_component_path": "/Game/Test/JerseyNumberMaskProxy",
        }
    application_path.write_text(json.dumps(application), encoding="utf-8")


def test_audit_requires_render_summary_number_job_contract(tmp_path):
    _appearance_v2_files(tmp_path)
    _make_valid_v2_application_report(tmp_path)
    errors = []
    summary = {
        "status": "success",
        "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
        "jobs": [
            {"camera_id": "Camera_01", "kind": "combined", "status": "success"},
            _valid_v2_render_summary_job(),
        ],
    }

    state = check_appearance(
        tmp_path,
        errors,
        render_required=True,
        appearance_catalog=_catalog_v2(),
        expected_camera_ids=["Camera_01"],
        render_summary=summary,
        expected_frames_per_camera=2,
        expected_render_frame_indices=[0, 1],
        expected_resolution=[4, 4],
    )

    assert state["ok"] is True
    assert errors == []


@pytest.mark.parametrize(
    "mutate, expected_text",
    [
        (lambda job: job.update({"status": "failed"}), "status actual='failed'"),
        (lambda job: job.update({"number_mask_source": "wrong_source"}), "source"),
        (lambda job: job.update({"number_mask_frames": 1}), "frames actual=1, expected=2"),
        (lambda job: job.update({"target_indices": [0]}), "target frame set"),
    ],
)
def test_audit_rejects_invalid_render_summary_number_job_contract(
    tmp_path, mutate, expected_text
):
    _appearance_v2_files(tmp_path)
    errors = []
    job = _valid_v2_render_summary_job()
    mutate(job)
    summary = {
        "status": "success",
        "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
        "jobs": [job],
    }

    state = check_appearance(
        tmp_path,
        errors,
        render_required=True,
        appearance_catalog=_catalog_v2(),
        expected_camera_ids=["Camera_01"],
        render_summary=summary,
        expected_frames_per_camera=2,
        expected_render_frame_indices=[0, 1],
        expected_resolution=[4, 4],
    )

    assert state["ok"] is False
    assert any(expected_text in error for error in errors)


def test_audit_uses_task_expected_frame_count_over_application_camera_count(tmp_path):
    _appearance_v2_files(tmp_path)
    _make_valid_v2_application_report(tmp_path)
    errors = []
    summary = {
        "status": "success",
        "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
        "jobs": [_valid_v2_render_summary_job()],
    }
    application_path = tmp_path / "provenance" / "appearance_application.json"
    application = json.loads(application_path.read_text(encoding="utf-8"))
    application["state"] = "restored"
    application["render_result"] = {
        "status": "success",
        "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2, "expected_frames": 99}},
        "jobs": [_valid_v2_render_summary_job()],
    }
    application["mrq_jobs"] = [_valid_v2_render_summary_job()]
    application_path.write_text(json.dumps(application), encoding="utf-8")

    check_appearance(
        tmp_path,
        errors,
        render_required=True,
        appearance_catalog=_catalog_v2(),
        expected_camera_ids=["Camera_01"],
        render_summary=summary,
        expected_frames_per_camera=2,
        expected_render_frame_indices=[0, 1],
        expected_resolution=[4, 4],
    )

    assert not any("expected=99" in error for error in errors)
    assert not any("expected=99" in error for error in errors)


@pytest.mark.parametrize(
    "mutate, expected_text",
    [
        (lambda job: job.update({"camera_id": "Camera_02"}), "camera actual"),
        (lambda job: job.update({"kind": "rgb"}), "actual=0, expected=1"),
        (lambda job: job.update({"target_indices": [0]}), "frame set"),
        (lambda job: job.update({"output_resolution": [8, 4]}), "resolution"),
    ],
)
def test_audit_rejects_render_summary_number_job_identity_and_shape(
    tmp_path, mutate, expected_text
):
    _appearance_v2_files(tmp_path)
    job = _valid_v2_render_summary_job()
    mutate(job)
    errors = []

    state = check_appearance(
        tmp_path,
        errors,
        render_required=True,
        appearance_catalog=_catalog_v2(),
        expected_camera_ids=["Camera_01"],
        render_summary={
            "status": "success",
            "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
            "jobs": [job],
        },
        expected_frames_per_camera=2,
        expected_render_frame_indices=[0, 1],
        expected_resolution=[4, 4],
    )

    assert state["ok"] is False
    assert any(expected_text in error for error in errors)


def test_audit_rejects_duplicate_or_missing_render_summary_number_jobs(tmp_path):
    _appearance_v2_files(tmp_path)
    errors = []
    job = _valid_v2_render_summary_job()
    summary = {
        "status": "success",
        "cameras": {"Camera_01": {"ok": True, "number_mask_frames": 2}},
        "jobs": [job, dict(job)],
    }

    state = check_appearance(
        tmp_path,
        errors,
        render_required=True,
        appearance_catalog=_catalog_v2(),
        expected_camera_ids=["Camera_01"],
        render_summary=summary,
        expected_frames_per_camera=2,
        expected_render_frame_indices=[0, 1],
        expected_resolution=[4, 4],
    )

    assert state["ok"] is False
    assert any("actual=2, expected=1" in error for error in errors)


def test_audit_compares_v2_application_number_with_manifest(tmp_path):
    manifest, report = _appearance_v2_files(tmp_path)
    errors = []

    state = check_appearance(
        tmp_path,
        errors,
        render_required=False,
        appearance_catalog=_catalog_v2(),
    )

    assert state["required"] is True
    assert any(
        "L0" in error and "98" in error and str(manifest["entities"][0]["jersey_number"]) in error
        for error in errors
    )
    assert report["actors"][0]["jersey_number"] == 98


def test_residual_number_masks_do_not_enable_legacy_audit(tmp_path):
    camera = tmp_path / "Camera_01"
    (camera / "number_mask").mkdir(parents=True)
    Image.new("L", (2, 2), 0).save(camera / "number_mask" / "000001.png")
    (camera / "annotations.jsonl").write_text(
        '{"frame_index":1,"objects":[]}\n', encoding="utf-8"
    )
    errors = []

    state = check_camera(
        camera,
        expected_frames=1,
        keep_indices=[0],
        errors=errors,
        warns=[],
        mask_enabled=False,
        render_required=False,
    )

    assert state["number_mask_required"] is False
    assert state["number_mask_complete"] is False
    assert not any("number mask" in error.lower() for error in errors)


def test_audit_main_does_not_enable_v2_from_residual_number_files(tmp_path):
    camera = tmp_path / "Camera_01"
    (camera / "img1").mkdir(parents=True)
    (camera / "number_mask").mkdir()
    (camera / "img1" / "000001.png").write_bytes(b"rgb")
    Image.new("L", (2, 2), 0).save(camera / "number_mask" / "000001.png")
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 2,
        "image_height": 2,
        "intrinsics": {"width": 2, "height": 2, "fx": 1, "fy": 1, "cx": 1, "cy": 1},
        "extrinsics": {"world_location_m": [0, 0, 1], "forward": [1, 0, 0], "right": [0, 1, 0], "up": [0, 0, 1]},
    }), encoding="utf-8")
    (camera / "annotations.jsonl").write_text(
        '{"frame_index":1,"source_step":0,"time_seconds":0,"episode_id":"legacy","objects":[]}\n',
        encoding="utf-8",
    )

    exit_code = audit_main([
        "--input", str(tmp_path),
        "--expected-cameras", "1",
        "--expected-frames-per-camera", "1",
        "--validation-level", "none",
        "--render-required", "false",
        "--mask-enabled", "false",
        "--mot-required", "false",
        "--pose-required", "false",
    ])
    report = json.loads(
        (tmp_path / "audit" / "soak_audit_report.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert report["requirements"]["jersey_number_mask"] is False
    assert report["checks"]["jersey_number_mask"]["status"] == "skipped"


def _environment_profile():
    return {
        "mode": "seeded",
        "policy": episode_environment.ENVIRONMENT_POLICY,
        "catalog_id": ENVIRONMENT_CATALOG_ID,
        "environment_seed": 42,
        "preset": "daylight_clear_v1",
        "catalog_fingerprint": environment_catalog_fingerprint(),
    }


def _environment_fixture(tmp_path, *, report_state="restored"):
    trajectory = tmp_path / "trajectory"
    dataset = tmp_path / "dataset"
    provenance = trajectory / "provenance"
    provenance.mkdir(parents=True)
    dataset.mkdir()
    meta = {"episode_id": "environment-audit"}
    frames = trajectory / "frames.jsonl"
    frames.write_text('{"step":0}\n', encoding="utf-8")
    (trajectory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    profile = _environment_profile()
    manifest = build_environment_manifest(meta, frames, profile)
    (provenance / "environment.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    actors = [
        {
            "actor_label": label,
            "actor_path": "/Game/FutsalMOT/Maps/L_FutsalCourt.{}".format(label),
            "class": class_name,
            "package_path": "/Game/__ExternalActors__/{}".format(label),
            "apply_status": "not_started",
            "restore_status": "not_started",
        }
        for label, class_name in episode_environment.ACTOR_CLASSES.items()
    ]
    report = episode_environment.build_environment_application_report(
        manifest, "env_tx_001", report_state, actors, [], []
    )
    (provenance / "environment_application.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    return trajectory, dataset, profile, manifest


def test_audit_rejects_environment_manifest_trajectory_mismatch(tmp_path):
    trajectory, dataset, profile, _manifest = _environment_fixture(tmp_path)
    (trajectory / "frames.jsonl").write_text('{"step":1}\n', encoding="utf-8")
    errors = []

    state = check_environment(
        trajectory,
        dataset,
        errors,
        environment_profile=profile,
        render_required=False,
    )

    assert state["ok"] is False
    assert any("trajectory" in error or "environment" in error for error in errors)


def test_audit_rejects_environment_render_metadata_drift(tmp_path):
    trajectory, dataset, profile, manifest = _environment_fixture(tmp_path)
    (dataset / "render_summary.json").write_text(
        json.dumps({
            "status": "success",
            "cameras": {"Camera_01": {"ok": True}},
            "environment_policy": profile["policy"],
            "environment_manifest_fingerprint": "f" * 64,
            "environment_preset": manifest["preset"],
            "environment_restore_ready": True,
        }),
        encoding="utf-8",
    )
    errors = []

    state = check_environment(
        trajectory,
        dataset,
        errors,
        environment_profile=profile,
        render_required=True,
    )

    assert state["ok"] is False
    assert any("render_summary" in error for error in errors)


def test_audit_skips_environment_checks_when_only_residual_files_exist(tmp_path):
    trajectory, dataset, _profile, _manifest = _environment_fixture(tmp_path)
    errors = []

    state = check_environment(
        trajectory,
        dataset,
        errors,
        environment_profile=None,
        render_required=False,
    )

    assert state == {"ok": True, "required": False, "enabled": False, "skipped": True}
    assert errors == []


def test_cleanup_audit_validates_canonical_jersey_record_without_transient_masks(
    tmp_path,
):
    camera = tmp_path / "Camera_01"
    camera.mkdir(parents=True)
    (camera / "annotations.jsonl").write_text(
        json.dumps({
            "frame_index": 1,
            "objects": [{
                "entity_id": "L0",
                "jersey_number": {
                    "value": 17,
                    "placement": "back",
                    "bbox_source": "visible_number_mask",
                    "in_frame": True,
                    "truncated": False,
                    "visible_pixel_count": 0,
                    "bbox_xyxy": None,
                    "bbox_xywh": None,
                },
            }],
        }) + "\n",
        encoding="utf-8",
    )
    errors = []

    state = check_camera(
        camera,
        expected_frames=1,
        keep_indices=[0],
        errors=errors,
        warns=[],
        mask_enabled=False,
        render_required=False,
        number_mask_required=True,
        jersey_numbers={"L0": 17},
        number_masks_cleaned=True,
    )

    assert state["number_mask_complete"] is True
    assert state["number_mask_ok"] is False
    assert any("visible_pixel_count" in error for error in errors)


def test_duplicate_jersey_values_are_reported_with_entity_and_value(tmp_path):
    camera = tmp_path / "Camera_01"
    (camera / "number_mask").mkdir(parents=True)
    pixels = __import__("numpy").zeros((2, 2), dtype="uint8")
    pixels[0, 0] = 32
    Image.fromarray(pixels).save(camera / "number_mask" / "000001.png")
    (camera / "annotations.jsonl").write_text(
        json.dumps({"frame_index": 1, "objects": [
            {"entity_id": "L0", "jersey_number": {"value": 7}},
            {"entity_id": "L1", "jersey_number": {"value": 7}},
        ]}) + "\n",
        encoding="utf-8",
    )
    errors = []

    check_camera(
        camera,
        expected_frames=1,
        keep_indices=[0],
        errors=errors,
        warns=[],
        mask_enabled=False,
        render_required=False,
        number_mask_required=True,
        jersey_numbers={"L0": 7, "L1": 7},
    )

    assert any(
        "Camera_01" in error and "frame 1" in error and "L0" in error
        and "L1" in error and "actual=7" in error
        for error in errors
    )


def test_audit_compares_number_pixel_bbox_and_pixel_count(tmp_path):
    manifest, _report = _appearance_v2_files(tmp_path)
    camera = tmp_path / "Camera_01"
    (camera / "img1").mkdir(parents=True)
    (camera / "number_mask").mkdir()
    (camera / "render_number_mask").mkdir()
    (camera / "img1" / "000001.png").write_bytes(b"rgb")
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 4,
        "image_height": 4,
        "intrinsics": {"width": 4, "height": 4, "fx": 2, "fy": 2, "cx": 2, "cy": 2},
        "extrinsics": {"world_location_m": [0, 0, 1], "forward": [1, 0, 0], "right": [0, 1, 0], "up": [0, 0, 1]},
    }), encoding="utf-8")
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 4,
        "image_height": 4,
        "intrinsics": {"width": 4, "height": 4, "fx": 2, "fy": 2, "cx": 2, "cy": 2},
        "extrinsics": {"world_location_m": [0, 0, 1], "forward": [1, 0, 0], "right": [0, 1, 0], "up": [0, 0, 1]},
    }), encoding="utf-8")
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 4,
        "image_height": 4,
        "intrinsics": {"width": 4, "height": 4, "fx": 2, "fy": 2, "cx": 2, "cy": 2},
        "extrinsics": {"world_location_m": [0, 0, 1], "forward": [1, 0, 0], "right": [0, 1, 0], "up": [0, 0, 1]},
    }), encoding="utf-8")
    Image.new("L", (4, 4), 0).save(camera / "render_number_mask" / "000000.png")
    pixels = __import__("numpy").zeros((4, 4), dtype="uint8")
    pixels[1, 1] = 32
    Image.fromarray(pixels).save(camera / "number_mask" / "000001.png")
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 4,
        "image_height": 4,
        "intrinsics": {"width": 4, "height": 4, "fx": 2, "fy": 2, "cx": 2, "cy": 2},
        "extrinsics": {"world_location_m": [0, 0, 1], "forward": [1, 0, 0], "right": [0, 1, 0], "up": [0, 0, 1]},
    }), encoding="utf-8")
    objects = []
    for index, entity in enumerate(manifest["entities"]):
        objects.append({
            "entity_id": entity["entity_id"],
            "jersey_number": {
                "value": entity["jersey_number"],
                "visible_pixel_count": 2 if index == 0 else 0,
                "bbox_xyxy": [0, 0, 1, 1] if index == 0 else None,
                "bbox_xywh": [0, 0, 1, 1] if index == 0 else None,
            },
        })
    (camera / "annotations.jsonl").write_text(
        json.dumps({"frame_index": 1, "objects": objects}) + "\n", encoding="utf-8"
    )
    errors = []

    state = check_camera(
        camera,
        expected_frames=1,
        keep_indices=[0],
        errors=errors,
        warns=[],
        mask_enabled=False,
        render_required=False,
        number_mask_required=True,
        jersey_numbers={
            entity["entity_id"]: entity["jersey_number"]
            for entity in manifest["entities"]
        },
    )

    assert state["number_mask_ok"] is False
    assert any(
        "Camera_01" in error and "frame 1" in error and "entity L0" in error
        and "actual=2" in error and "mask=1" in error
        for error in errors
    )


def test_v2_audit_rejects_duplicate_annotation_entities_without_annotation_validation(
    tmp_path,
):
    manifest, _report = _appearance_v2_files(tmp_path)
    camera = tmp_path / "Camera_01"
    (camera / "img1").mkdir(parents=True)
    (camera / "number_mask").mkdir()
    (camera / "render_number_mask").mkdir()
    (camera / "img1" / "000001.png").write_bytes(b"rgb")
    Image.new("L", (4, 4), 0).save(camera / "number_mask" / "000001.png")
    Image.new("L", (4, 4), 0).save(camera / "render_number_mask" / "000000.png")
    (camera / "annotations.jsonl").write_text(
        json.dumps({"frame_index": 1, "objects": [
            {"entity_id": "L0", "jersey_number": {"value": manifest["entities"][0]["jersey_number"]}},
            {"entity_id": "L0", "jersey_number": {"value": manifest["entities"][0]["jersey_number"]}},
        ]}) + "\n",
        encoding="utf-8",
    )
    errors = []

    state = check_camera(
        camera,
        expected_frames=1,
        keep_indices=[0],
        errors=errors,
        warns=[],
        mask_enabled=False,
        render_required=False,
        number_mask_required=True,
        jersey_numbers={
            entity["entity_id"]: entity["jersey_number"]
            for entity in manifest["entities"]
        },
    )

    assert state["ok"] is False
    assert any(
        "Camera_01" in error and "frame 1" in error
        and "L0" in error and "duplicate" in error.lower()
        for error in errors
    )


def test_v2_audit_uses_exact_pixel_bbox_bounds(tmp_path):
    manifest, _report = _appearance_v2_files(tmp_path)
    camera = tmp_path / "Camera_01"
    (camera / "img1").mkdir(parents=True)
    (camera / "number_mask").mkdir()
    (camera / "render_number_mask").mkdir()
    (camera / "img1" / "000001.png").write_bytes(b"rgb")
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 4,
        "image_height": 4,
        "intrinsics": {"width": 4, "height": 4, "fx": 2, "fy": 2, "cx": 2, "cy": 2},
        "extrinsics": {"world_location_m": [0, 0, 1], "forward": [1, 0, 0], "right": [0, 1, 0], "up": [0, 0, 1]},
    }), encoding="utf-8")
    pixels = __import__("numpy").zeros((4, 4), dtype="uint8")
    pixels[1, 1] = 32
    Image.fromarray(pixels).save(camera / "number_mask" / "000001.png")
    Image.new("L", (4, 4), 0).save(camera / "render_number_mask" / "000000.png")
    objects = []
    for index, entity in enumerate(manifest["entities"]):
        objects.append({
            "entity_id": entity["entity_id"],
            "jersey_number": {
                "value": entity["jersey_number"],
                "visible_pixel_count": 1 if index == 0 else 0,
                "bbox_xyxy": [1, 1, 2.4, 2] if index == 0 else None,
                "bbox_xywh": [1, 1, 1.4, 1] if index == 0 else None,
            },
        })
    (camera / "annotations.jsonl").write_text(
        json.dumps({"frame_index": 1, "objects": objects}) + "\n", encoding="utf-8"
    )
    errors = []

    check_camera(
        camera,
        expected_frames=1,
        keep_indices=[0],
        errors=errors,
        warns=[],
        mask_enabled=False,
        render_required=False,
        number_mask_required=True,
        jersey_numbers={
            entity["entity_id"]: entity["jersey_number"]
            for entity in manifest["entities"]
        },
    )

    assert any("bbox_xyxy" in error and "2.4" in error for error in errors)
    assert any(
        "entity L0" in error and "bbox_xyxy actual=[1, 1, 2.4, 2]" in error
        and "mask min/max=[1, 1, 2, 2]" in error
        for error in errors
    )


@pytest.mark.parametrize("malformed_id", [["L0"], {"id": "L0"}])
def test_audit_rejects_unhashable_annotation_entity_id_fail_closed(
    tmp_path, malformed_id
):
    camera = tmp_path / "Camera_01"
    (camera / "img1").mkdir(parents=True)
    (camera / "img1" / "000001.png").write_bytes(b"rgb")
    (camera / "camera.json").write_text(json.dumps({
        "image_width": 2,
        "image_height": 2,
        "intrinsics": {"width": 2, "height": 2, "fx": 1, "fy": 1, "cx": 1, "cy": 1},
        "extrinsics": {
            "world_location_m": [0, 0, 1],
            "forward": [1, 0, 0],
            "right": [0, 1, 0],
            "up": [0, 0, 1],
        },
    }), encoding="utf-8")
    (camera / "annotations.jsonl").write_text(json.dumps({
        "frame_index": 1,
        "source_step": 0,
        "time_seconds": 0,
        "episode_id": "legacy",
        "objects": [{"entity_id": malformed_id, "track_id": 1, "mask_id": 1}],
    }) + "\n", encoding="utf-8")

    exit_code = audit_main([
        "--input", str(tmp_path),
        "--expected-cameras", "1",
        "--expected-frames-per-camera", "1",
        "--validation-level", "none",
        "--render-required", "false",
        "--mask-enabled", "false",
        "--mot-required", "false",
        "--pose-required", "false",
    ])
    report = json.loads(
        (tmp_path / "audit" / "soak_audit_report.json").read_text(encoding="utf-8")
    )

    assert exit_code == 1
    assert any(repr(malformed_id) in error for error in report["errors"])
    assert not any("unhashable" in error.lower() for error in report["errors"])


@pytest.mark.parametrize("malformed_id", [["L0"], {"id": "L0"}])
def test_audit_reports_unhashable_manifest_entity_id_fail_closed(
    tmp_path, malformed_id
):
    _appearance_v2_files(tmp_path)
    manifest_path = tmp_path / "provenance" / "appearance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entities"][0]["entity_id"] = malformed_id
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = []

    state = check_appearance(
        tmp_path,
        errors,
        render_required=False,
        appearance_catalog=_catalog_v2(),
    )

    assert state["ok"] is False
    assert any(repr(malformed_id) in error for error in errors)
    assert not any("unhashable" in error.lower() for error in errors)


@pytest.mark.parametrize(
    "field, value, expected_frames, expected_indices, expected_text",
    [
        ("number_mask_frames", 2.0, 2, [0, 1], "frames 类型非法"),
        ("number_mask_frames", True, 1, [0], "frames 类型非法"),
        ("target_indices", [0.0], 1, [0], "target frame set 类型非法"),
        ("target_indices", [False], 1, [0], "target frame set 类型非法"),
        ("output_resolution", [4.0, 4.0], 2, [0, 1], "resolution 类型非法"),
    ],
)
def test_audit_rejects_non_strict_v2_render_summary_json_types(
    field, value, expected_frames, expected_indices, expected_text
):
    job = _valid_v2_render_summary_job(frames=expected_frames)
    job[field] = value
    errors = []

    _check_v2_render_summary_jobs(
        {"jobs": [job]},
        ["Camera_01"],
        expected_frames,
        expected_indices,
        [4, 4],
        errors,
    )

    assert any(expected_text in error and repr(value) in error for error in errors)
