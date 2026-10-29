"""球衣号码 mask 标注的纯 Python 契约测试。"""

import json

import numpy as np
import pytest
from PIL import Image

from grf_ue_bridge.jersey_number_annotator import annotate_jersey_number_masks
from annotation_exporter import build_object_annotation


ENTITY_IDS = tuple(
    [f"L{index}" for index in range(5)]
    + [f"R{index}" for index in range(5)]
)


def _manifest(policy="futsalmot_appearance_v2"):
    manifest = {
        "schema": "futsalmot_episode_appearance",
        "version": 2 if policy.endswith("_v2") else 1,
        "policy": policy,
        "numbering": {"mask_stencil_start": 32},
        "entities": [
            {"entity_id": entity_id, "jersey_number": index + 1}
            for index, entity_id in enumerate(ENTITY_IDS)
        ],
    }
    return manifest


def _object(entity_id, index):
    player = entity_id != "BALL"
    return {
        "entity_id": entity_id,
        "track_id": index + 1,
        "mask_id": index + 1,
        "bbox_xyxy": [float(index), 1.0, float(index + 2), 4.0],
        "bbox_xywh": [float(index), 1.0, 2.0, 3.0],
        "raw_bbox_xyxy": [float(index), 1.0, float(index + 2), 4.0],
        "in_frame": True,
        "class": "player" if player else "ball",
    }


def _camera_fixture(tmp_path, frame_indices=(1,), width=8, height=6):
    camera = tmp_path / "CineCam_01"
    camera.mkdir()
    (camera / "camera.json").write_text(
        json.dumps({"image_width": width, "image_height": height}),
        encoding="utf-8",
    )
    frames = []
    for frame_index in frame_indices:
        frames.append(
            {
                "frame_index": frame_index,
                "objects": [_object(entity_id, index) for index, entity_id in enumerate(ENTITY_IDS)]
                + [_object("BALL", 10)],
            }
        )
    (camera / "annotations.jsonl").write_text(
        "".join(json.dumps(frame) + "\n" for frame in frames),
        encoding="utf-8",
    )
    (camera / "number_mask").mkdir()
    return camera, frames


def _write_mask(camera, frame_index, pixels, size=(8, 6)):
    array = np.zeros((size[1], size[0]), dtype=np.uint8)
    for x, y, value in pixels:
        array[y, x] = value
    Image.fromarray(array).save(
        camera / "number_mask" / f"{frame_index:06d}.png"
    )


def _read_annotations(camera):
    return [
        json.loads(line)
        for line in (camera / "annotations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_annotates_pixel_tight_union_and_preserves_player_bbox(tmp_path):
    camera, _ = _camera_fixture(tmp_path)
    _write_mask(
        camera,
        1,
        [
            (0, 0, 32),
            (2, 2, 32),
            (3, 2, 32),
            (6, 4, 33),
            (7, 5, 33),
        ],
    )
    primary_bbox = [0.0, 1.0, 2.0, 4.0]
    manifest = _manifest()

    errors = annotate_jersey_number_masks(tmp_path, manifest=manifest, cameras=[camera])

    assert errors == []
    objects = {obj["entity_id"]: obj for obj in _read_annotations(camera)[0]["objects"]}
    assert objects["L0"]["jersey_number"] == {
        "value": 1,
        "placement": "back",
        "bbox_source": "visible_number_mask",
        "in_frame": True,
        "truncated": False,
        "visible_pixel_count": 3,
        "bbox_xyxy": [0.0, 0.0, 4.0, 3.0],
        "bbox_xywh": [0.0, 0.0, 4.0, 3.0],
    }
    assert objects["L1"]["jersey_number"]["visible_pixel_count"] == 2
    assert objects["L1"]["jersey_number"]["bbox_xyxy"] == [6.0, 4.0, 8.0, 6.0]
    assert objects["L0"]["bbox_xyxy"] == primary_bbox
    assert objects["L0"]["track_id"] == 1
    assert objects["L0"]["mask_id"] == 1
    assert "jersey_number" not in objects["BALL"]


def test_empty_number_mask_keeps_manifest_value_and_null_visible_bbox(tmp_path):
    camera, _ = _camera_fixture(tmp_path)
    _write_mask(camera, 1, [(1, 1, 32)])

    errors = annotate_jersey_number_masks(tmp_path, manifest=_manifest(), cameras=[camera])

    assert errors == []
    objects = {obj["entity_id"]: obj for obj in _read_annotations(camera)[0]["objects"]}
    assert objects["L1"]["jersey_number"] == {
        "value": 2,
        "placement": "back",
        "bbox_source": "visible_number_mask",
        "in_frame": False,
        "truncated": False,
        "visible_pixel_count": 0,
        "bbox_xyxy": None,
        "bbox_xywh": None,
    }


def test_rejects_unmapped_nonzero_number_mask_id_without_rewriting(tmp_path):
    camera, _ = _camera_fixture(tmp_path)
    _write_mask(camera, 1, [(0, 0, 42)])
    annotations_path = camera / "annotations.jsonl"
    before = annotations_path.read_bytes()

    errors = annotate_jersey_number_masks(tmp_path, manifest=_manifest(), cameras=[camera])

    assert errors
    assert any("42" in error for error in errors)
    assert annotations_path.read_bytes() == before


def test_rejects_number_mask_resolution_mismatch_without_rewriting(tmp_path):
    camera, _ = _camera_fixture(tmp_path)
    _write_mask(camera, 1, [(0, 0, 32)], size=(7, 6))
    annotations_path = camera / "annotations.jsonl"
    before = annotations_path.read_bytes()

    errors = annotate_jersey_number_masks(tmp_path, manifest=_manifest(), cameras=[camera])

    assert errors
    assert any("分辨率" in error or "resolution" in error.lower() for error in errors)
    assert annotations_path.read_bytes() == before


def test_rejects_missing_number_mask_frame_without_rewriting(tmp_path):
    camera, _ = _camera_fixture(tmp_path, frame_indices=(1, 2))
    _write_mask(camera, 1, [])
    annotations_path = camera / "annotations.jsonl"
    before = annotations_path.read_bytes()

    errors = annotate_jersey_number_masks(tmp_path, manifest=_manifest(), cameras=[camera])

    assert errors
    assert any("000002.png" in error for error in errors)
    assert annotations_path.read_bytes() == before


@pytest.mark.parametrize("bad_number", [0, 100, True, 1.5])
def test_rejects_invalid_manifest_number(tmp_path, bad_number):
    camera, _ = _camera_fixture(tmp_path)
    _write_mask(camera, 1, [])
    manifest = _manifest()
    manifest["entities"][0]["jersey_number"] = bad_number

    errors = annotate_jersey_number_masks(tmp_path, manifest=manifest, cameras=[camera])

    assert errors
    assert any("jersey_number" in error for error in errors)


def test_explicit_jersey_annotator_rejects_v1_manifest(tmp_path):
    camera, _ = _camera_fixture(tmp_path)
    _write_mask(camera, 1, [])
    before = (camera / "annotations.jsonl").read_bytes()

    errors = annotate_jersey_number_masks(
        tmp_path,
        manifest={"policy": "futsalmot_appearance_v1"},
        cameras=[camera],
    )

    assert errors
    assert any("appearance v2" in error for error in errors)
    assert (camera / "annotations.jsonl").read_bytes() == before


@pytest.mark.parametrize("jersey_number", [None, 37])
def test_ue_annotation_exporter_adds_only_v2_number_initial_state(
    monkeypatch, jersey_number
):
    import annotation_exporter

    class Location:
        x = 100.0
        y = 200.0
        z = 0.0

    class Actor:
        def get_actor_location(self):
            return Location()

    monkeypatch.setattr(annotation_exporter, "get_world_bounds", lambda _actor: ((100, 200, 0), (1, 1, 1)))
    monkeypatch.setattr(annotation_exporter, "world_bbox_corners", lambda *_args: [])
    monkeypatch.setattr(annotation_exporter, "project_box_corners_to_image_xyxy", lambda *_args: (1, 1, 3, 4))

    result = build_object_annotation(
        "L0",
        Actor(),
        {},
        None,
        None,
        8,
        6,
        jersey_number=jersey_number,
    )

    if jersey_number is None:
        assert "jersey_number" not in result
    else:
        assert result["jersey_number"] == {
            "value": 37,
            "placement": "back",
            "bbox_source": "visible_number_mask",
            "in_frame": False,
            "truncated": False,
            "visible_pixel_count": 0,
            "bbox_xyxy": None,
            "bbox_xywh": None,
        }


def _exporter_manifest(tmp_path, *, policy="futsalmot_appearance_v2", version=2):
    manifest = {
        "schema": "futsalmot_episode_appearance",
        "version": version,
        "policy": policy,
        "numbering": {"mask_stencil_start": 32},
        "entities": [
            {"entity_id": entity_id, "jersey_number": index + 1}
            for index, entity_id in enumerate(ENTITY_IDS)
        ],
    }
    provenance = tmp_path / "provenance"
    provenance.mkdir(exist_ok=True)
    (provenance / "appearance.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_exporter_ignores_stray_v2_manifest_when_resolved_catalog_is_v1(
    tmp_path, monkeypatch
):
    import annotation_exporter

    _exporter_manifest(tmp_path)
    result = annotation_exporter._load_jersey_numbers(
        tmp_path, resolved_appearance_policy="futsalmot_appearance_v1"
    )
    class Location:
        x = 100.0
        y = 200.0
        z = 0.0

    class Actor:
        def get_actor_location(self):
            return Location()

    monkeypatch.setattr(annotation_exporter, "get_world_bounds", lambda _actor: ((100, 200, 0), (1, 1, 1)))
    monkeypatch.setattr(annotation_exporter, "world_bbox_corners", lambda *_args: [])
    monkeypatch.setattr(annotation_exporter, "project_box_corners_to_image_xyxy", lambda *_args: (1, 1, 3, 4))
    player = annotation_exporter.build_object_annotation(
        "L0", Actor(), {}, None, None, 8, 6, jersey_number=result.get("L0")
    )

    assert result == {}
    assert "jersey_number" not in player


@pytest.mark.parametrize("manifest_policy,write_manifest", [
    ("futsalmot_appearance_v1", True),
    ("futsalmot_appearance_v2_bad_version", True),
    (None, False),
])
def test_exporter_v2_policy_rejects_v1_or_missing_manifest(
    tmp_path, manifest_policy, write_manifest
):
    import annotation_exporter

    if write_manifest:
        policy = (
            "futsalmot_appearance_v2"
            if manifest_policy == "futsalmot_appearance_v2_bad_version"
            else manifest_policy
        )
        _exporter_manifest(tmp_path, policy=policy, version=1)

    with pytest.raises(ValueError, match="appearance v2"):
        annotation_exporter._load_jersey_numbers(
            tmp_path, resolved_appearance_policy="futsalmot_appearance_v2"
        )
