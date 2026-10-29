"""task postprocess 的 appearance policy 回归测试。"""

from types import SimpleNamespace

import pytest

from grf_ue_bridge.appearance import build_appearance_manifest

from test_appearance import appearance_catalog_v2, appearance_meta


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("futsalmot_appearance_v1", False),
        ("futsalmot_appearance_v2", True),
    ],
)
def test_postprocess_passes_jersey_number_requirement_only_for_v2(
    monkeypatch, tmp_path, policy, expected
):
    from grf_ue_bridge.workflows import task_postprocess

    captured = {}

    def fake_annotate_masks_dir(*args, **kwargs):
        return 0

    def fake_validate_annotation_dir(*args, **kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(
        "grf_ue_bridge.mask_annotator.annotate_masks_dir",
        fake_annotate_masks_dir,
    )
    monkeypatch.setattr(
        "grf_ue_bridge.annotation_validator.validate_annotation_dir",
        fake_validate_annotation_dir,
    )
    monkeypatch.setattr(
        task_postprocess,
        "_annotate_jersey_numbers_if_v2",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        task_postprocess,
        "_validate_v2_appearance_binding",
        lambda *args, **kwargs: True,
    )

    resolved = SimpleNamespace(
        task_id="postprocess-test",
        dataset_episode_dir=str(tmp_path / "dataset"),
        trajectory_output=str(tmp_path / "trajectory"),
        actor_mapping=str(tmp_path / "mapping.json"),
        postprocess={
            "formats": [],
            "workers": 1,
            "chunk_size": 0,
            "validation_level": "quick",
            "yolo_pose": {"enabled": False},
            "debug": {"enabled": False},
        },
        ue_profile={"appearance": {"policy": policy}},
    )

    assert task_postprocess.run_postprocess(resolved, skip_cryptomatte=True) == 0
    assert captured.get("require_jersey_number_mask", False) is expected


@pytest.mark.parametrize("replacement", ["fingerprint", "catalog", "trajectory"])
def test_postprocess_rejects_replaced_v2_manifest_with_matching_policy(
    tmp_path, monkeypatch, replacement
):
    from grf_ue_bridge.workflows import task_postprocess

    trajectory = tmp_path / "episode"
    provenance = trajectory / "provenance"
    provenance.mkdir(parents=True)
    meta = appearance_meta()
    frames_path = trajectory / "frames.jsonl"
    frames_path.write_text('{"step": 0}\n', encoding="utf-8")
    manifest = build_appearance_manifest(meta, frames_path, appearance_catalog_v2())
    resolved_catalog = appearance_catalog_v2()
    if replacement == "fingerprint":
        manifest["fingerprint"] = "0" * 64
    elif replacement == "catalog":
        resolved_catalog["numbering"]["parameter"] = "ReplacedNumberIndex"
    else:
        frames_path.write_text('{"step": 1}\n', encoding="utf-8")
    (trajectory / "meta.json").write_text(
        __import__("json").dumps(meta), encoding="utf-8"
    )
    (provenance / "appearance.json").write_text(
        __import__("json").dumps(manifest), encoding="utf-8"
    )
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    resolved = SimpleNamespace(
        task_id="postprocess-v2-manifest-test",
        dataset_episode_dir=str(dataset),
        trajectory_output=str(trajectory),
        ue_profile={"appearance": resolved_catalog},
    )
    errors = []
    ok = task_postprocess._annotate_jersey_numbers_if_v2(
        dataset, trajectory, resolved, errors.append
    )

    assert ok is False
    assert errors


def test_postprocess_skip_annotate_still_rejects_replaced_v2_manifest(
    tmp_path,
):
    from grf_ue_bridge.workflows import task_postprocess

    trajectory = tmp_path / "episode"
    provenance = trajectory / "provenance"
    provenance.mkdir(parents=True)
    meta = appearance_meta()
    frames_path = trajectory / "frames.jsonl"
    frames_path.write_text('{"step": 0}\n', encoding="utf-8")
    manifest = build_appearance_manifest(meta, frames_path, appearance_catalog_v2())
    manifest["fingerprint"] = "0" * 64
    (trajectory / "meta.json").write_text(
        __import__("json").dumps(meta), encoding="utf-8"
    )
    (provenance / "appearance.json").write_text(
        __import__("json").dumps(manifest), encoding="utf-8"
    )

    resolved = SimpleNamespace(
        task_id="postprocess-v2-skip-annotate-test",
        dataset_episode_dir=str(tmp_path / "dataset"),
        trajectory_output=str(trajectory),
        actor_mapping=str(tmp_path / "mapping.json"),
        postprocess={
            "formats": [],
            "yolo_pose": {"enabled": False},
            "debug": {"enabled": False},
        },
        ue_profile={"appearance": appearance_catalog_v2()},
    )

    assert task_postprocess.run_postprocess(
        resolved,
        skip_cryptomatte=True,
        skip_annotate=True,
        skip_validate=True,
        skip_pose=True,
        skip_debug=True,
    ) == 1


def test_postprocess_skip_annotate_does_not_write_v2_number_annotations(
    tmp_path, monkeypatch
):
    from grf_ue_bridge.workflows import task_postprocess

    trajectory = tmp_path / "episode"
    provenance = trajectory / "provenance"
    provenance.mkdir(parents=True)
    meta = appearance_meta()
    frames_path = trajectory / "frames.jsonl"
    frames_path.write_text('{"step": 0}\n', encoding="utf-8")
    manifest = build_appearance_manifest(meta, frames_path, appearance_catalog_v2())
    (trajectory / "meta.json").write_text(
        __import__("json").dumps(meta), encoding="utf-8"
    )
    (provenance / "appearance.json").write_text(
        __import__("json").dumps(manifest), encoding="utf-8"
    )
    monkeypatch.setattr(
        task_postprocess,
        "_annotate_jersey_numbers_if_v2",
        lambda *args, **kwargs: pytest.fail("skip_annotate must not write number annotations"),
    )

    resolved = SimpleNamespace(
        task_id="postprocess-v2-skip-annotate-valid-test",
        dataset_episode_dir=str(tmp_path / "dataset"),
        trajectory_output=str(trajectory),
        actor_mapping=str(tmp_path / "mapping.json"),
        postprocess={
            "formats": [],
            "yolo_pose": {"enabled": False},
            "debug": {"enabled": False},
        },
        ue_profile={"appearance": appearance_catalog_v2()},
    )

    assert task_postprocess.run_postprocess(
        resolved,
        skip_cryptomatte=True,
        skip_annotate=True,
        skip_validate=True,
        skip_pose=True,
        skip_debug=True,
    ) == 0
