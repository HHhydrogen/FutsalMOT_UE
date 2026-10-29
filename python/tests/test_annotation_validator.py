"""标注验证器的测试。"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from grf_ue_bridge.annotation_validator import (
    validate_annotation_dir,
    validate_jersey_number_record,
)

_UE_DIR = Path(__file__).resolve().parents[1] / "ue"
if str(_UE_DIR) not in sys.path:
    sys.path.insert(0, str(_UE_DIR))


def _player_obj(entity, track, in_frame=True, xywh=None):
    """构造一个合法的 player object（in_frame=False 时 bbox 为 None）。"""
    xyxy = None
    if xywh is not None:
        xyxy = [xywh[0], xywh[1], xywh[0] + xywh[2], xywh[1] + xywh[3]]
    return {
        "entity_id": entity,
        "track_id": track,
        "class": "player",
        "team": "left",
        "role": None,
        "is_goalkeeper": False,
        "world_position": [0.0, 0.0, 0.0],
        "in_frame": in_frame,
        "truncated": False,
        "visibility": None,
        "raw_bbox_xywh": xywh,
        "raw_bbox_xyxy": xyxy,
        "bbox_xywh": xywh,
        "bbox_xyxy": xyxy,
    }


def _write_camera(dir_path: Path, objects_by_frame, width=1920, height=1080, mot=True):
    """写一个合法的 camera 子目录。"""
    (dir_path / "gt").mkdir(parents=True, exist_ok=True)
    cam = {
        "camera_id": dir_path.name,
        "image_width": width,
        "image_height": height,
        "intrinsics": {
            "width": width, "height": height,
            "fx": 1000.0, "fy": 1000.0, "cx": width / 2, "cy": height / 2,
        },
        "extrinsics": {
            "world_location_m": [0.0, 0.0, 0.0],
            "forward": [1.0, 0.0, 0.0],
            "right": [0.0, 1.0, 0.0],
            "up": [0.0, 0.0, 1.0],
        },
    }
    (dir_path / "camera.json").write_text(json.dumps(cam), encoding="utf-8")

    with open(dir_path / "annotations.jsonl", "w", encoding="utf-8") as f:
        for fi, objs in enumerate(objects_by_frame, start=1):
            f.write(json.dumps({
                "episode_id": "episode_0001",
                "camera_id": dir_path.name,
                "frame_index": fi,
                "source_step": fi - 1,
                "time_seconds": (fi - 1) * 0.1,
                "objects": objs,
            }) + "\n")

    (dir_path / "seqinfo.ini").write_text("[Sequence]\nname=x\n", encoding="utf-8")

    if mot:
        lines = []
        for fi, objs in enumerate(objects_by_frame, start=1):
            for o in objs:
                if o.get("in_frame") and o.get("bbox_xywh") is not None:
                    x, y, w, h = o["bbox_xywh"]
                    lines.append(
                        f"{fi},{o['track_id']},{int(x)},{int(y)},{int(w)},{int(h)},1,1,1.00"
                    )
        (dir_path / "gt" / "gt.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestAnnotationValidator:
    def test_valid_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cam_dir = root / "Camera_01"
            frames = [
                [_player_obj("L0", 1, True, [10.0, 10.0, 50.0, 80.0]),
                 _player_obj("L1", 2, True, [100.0, 100.0, 40.0, 60.0])],
                [_player_obj("L0", 1, True, [11.0, 11.0, 50.0, 80.0]),
                 _player_obj("L1", 2, True, [101.0, 101.0, 40.0, 60.0])],
            ]
            _write_camera(cam_dir, frames)
            assert validate_annotation_dir(root) == 0

    def test_track_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cam_dir = root / "Camera_01"
            # 同一个 entity L0 在第 2 帧换了 track
            frames = [
                [_player_obj("L0", 1, True, [10.0, 10.0, 50.0, 80.0])],
                [_player_obj("L0", 2, True, [11.0, 11.0, 50.0, 80.0])],
            ]
            _write_camera(cam_dir, frames)
            assert validate_annotation_dir(root) == 1

    def test_out_of_bounds_bbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cam_dir = root / "Camera_01"
            # x=2000 超出图像宽 1920
            frames = [[_player_obj("L0", 1, True, [2000.0, 10.0, 50.0, 80.0])]]
            _write_camera(cam_dir, frames)
            assert validate_annotation_dir(root) == 1

    def test_negative_width_bbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cam_dir = root / "Camera_01"
            frames = [[_player_obj("L0", 1, True, [10.0, 10.0, -5.0, 80.0])]]
            _write_camera(cam_dir, frames)
            assert validate_annotation_dir(root) == 1

    def test_invalid_mot_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cam_dir = root / "Camera_01"
            frames = [[_player_obj("L0", 1, True, [10.0, 10.0, 50.0, 80.0])]]
            _write_camera(cam_dir, frames, mot=True)
            (cam_dir / "gt" / "gt.txt").write_text(
                "bad line without commas\n", encoding="utf-8"
            )
            assert validate_annotation_dir(root) == 1

    def test_missing_camera_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Camera_01").mkdir(parents=True)
            assert validate_annotation_dir(root) == 1

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert validate_annotation_dir(Path(tmp)) == 1


def _write_v2_number_fixture(root: Path, frames=2):
    camera = root / "Camera_01"
    entity_ids = [f"L{i}" for i in range(5)] + [f"R{i}" for i in range(5)]
    _write_camera(
        camera,
        [[
            _player_obj(entity_id, index + 1, True, [0.0, 0.0, 3.0, 3.0])
            for index, entity_id in enumerate(entity_ids)
        ] for _ in range(frames)],
        width=4,
        height=4,
        mot=False,
    )
    manifest_entities = [
        {"entity_id": entity_id, "jersey_number": index + 1}
        for index, entity_id in enumerate(
            [f"L{i}" for i in range(5)] + [f"R{i}" for i in range(5)]
        )
    ]
    provenance = root / "provenance"
    provenance.mkdir(exist_ok=True)
    (provenance / "appearance.json").write_text(json.dumps({
        "schema": "futsalmot_episode_appearance",
        "version": 2,
        "policy": "futsalmot_appearance_v2",
        "numbering": {"mask_stencil_start": 32},
        "entities": manifest_entities,
    }), encoding="utf-8")
    number_dir = camera / "number_mask"
    number_dir.mkdir()
    for frame_index in range(1, frames + 1):
        pixels = np.zeros((4, 4), dtype=np.uint8)
        pixels[1:3, 1:3] = 32
        Image.fromarray(pixels).save(number_dir / f"{frame_index:06d}.png")
    annotation_path = camera / "annotations.jsonl"
    rows = [json.loads(line) for line in annotation_path.read_text(encoding="utf-8").splitlines()]
    for frame in rows:
        for index, obj in enumerate(frame["objects"]):
            visible = index == 0
            obj["jersey_number"] = {
                "value": index + 1,
                "placement": "back",
                "bbox_source": "visible_number_mask",
                "in_frame": visible,
                "truncated": False,
                "visible_pixel_count": 4 if visible else 0,
                "bbox_xyxy": [1.0, 1.0, 3.0, 3.0] if visible else None,
                "bbox_xywh": [1.0, 1.0, 2.0, 2.0] if visible else None,
            }
    annotation_path.write_text(
        "".join(json.dumps(frame) + "\n" for frame in rows), encoding="utf-8"
    )
    return camera


def test_v2_validator_rejects_illegal_number_mask_id_with_entity_context(tmp_path, capsys):
    camera = _write_v2_number_fixture(tmp_path)
    pixels = np.zeros((4, 4), dtype=np.uint8)
    pixels[1, 1] = 99
    Image.fromarray(pixels).save(camera / "number_mask" / "000001.png")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "Camera_01" in output and "frame 1" in output and "99" in output


def test_v2_validator_rejects_duplicate_manifest_jersey_numbers(tmp_path, capsys):
    _write_v2_number_fixture(tmp_path, frames=1)
    manifest_path = tmp_path / "provenance" / "appearance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entities"][1]["jersey_number"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "Camera_01" in output and "L0" in output and "L1" in output
    assert "1" in output and "冲突" in output


def test_v2_validator_rejects_duplicate_entity_id_in_annotation_frame(tmp_path, capsys):
    camera = _write_v2_number_fixture(tmp_path, frames=1)
    annotation_path = camera / "annotations.jsonl"
    frame = json.loads(annotation_path.read_text(encoding="utf-8"))
    frame["objects"].append(dict(frame["objects"][0]))
    annotation_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "Camera_01" in output and "frame 1" in output and "entity L0" in output
    assert "appears more than once" in output


def test_v2_validator_rejects_duplicate_manifest_entity_ids_with_actual_ids(tmp_path, capsys):
    _write_v2_number_fixture(tmp_path, frames=1)
    manifest_path = tmp_path / "provenance" / "appearance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entities"][1]["entity_id"] = "L0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "duplicate" in output.lower() or "重复" in output
    assert "L0" in output and "actual" in output


def test_v2_validator_rejects_extra_manifest_entity_id_with_actual_ids(tmp_path, capsys):
    _write_v2_number_fixture(tmp_path, frames=1)
    manifest_path = tmp_path / "provenance" / "appearance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entities"][0]["entity_id"] = "BALL"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "BALL" in output and "actual" in output


@pytest.mark.parametrize("malformed_id", [["L0"], {"id": "L0"}])
def test_v2_validator_reports_malformed_manifest_entity_id_without_unhashable_error(
    tmp_path, capsys, malformed_id
):
    _write_v2_number_fixture(tmp_path, frames=1)
    manifest_path = tmp_path / "provenance" / "appearance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entities"][0]["entity_id"] = malformed_id
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "actual" in output
    assert repr(malformed_id) in output
    assert "unhashable" not in output.lower()


def test_v2_validator_compares_annotation_number_to_manifest(tmp_path, capsys):
    camera = _write_v2_number_fixture(tmp_path, frames=1)
    annotation_path = camera / "annotations.jsonl"
    frame = json.loads(annotation_path.read_text(encoding="utf-8"))
    frame["objects"][0]["jersey_number"]["value"] = 7
    annotation_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "Camera_01" in output and "frame 1" in output and "L0" in output
    assert "7" in output and "1" in output


def test_v2_validator_compares_number_bbox_to_mask_min_max(tmp_path, capsys):
    camera = _write_v2_number_fixture(tmp_path, frames=1)
    annotation_path = camera / "annotations.jsonl"
    frame = json.loads(annotation_path.read_text(encoding="utf-8"))
    frame["objects"][0]["jersey_number"]["bbox_xyxy"] = [0, 0, 1, 1]
    annotation_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "Camera_01" in output and "frame 1" in output and "L0" in output
    assert "[1.0, 1.0, 3.0, 3.0]" in output and "[0, 0, 1, 1]" in output


def test_v2_validator_requires_number_mask_for_every_annotation_frame(tmp_path, capsys):
    camera = _write_v2_number_fixture(tmp_path, frames=2)
    (camera / "number_mask" / "000002.png").unlink()

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "Camera_01" in output and "frame 2" in output


def test_v1_annotation_validation_does_not_require_number_fields_or_masks(tmp_path):
    camera = tmp_path / "Camera_01"
    _write_camera(
        camera,
        [[_player_obj("L0", 1, True, [1.0, 1.0, 2.0, 2.0])]],
        mot=False,
    )

    assert validate_annotation_dir(tmp_path, require_mot=False) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value", True),
        ("value", 1.0),
        ("value", "1"),
        ("placement", 1),
        ("bbox_source", "geometry"),
        ("in_frame", 1),
        ("truncated", 0),
        ("visible_pixel_count", True),
        ("visible_pixel_count", 4.0),
        ("visible_pixel_count", "4"),
        ("bbox_xyxy", [1.0, 1.0, 3.0]),
        ("bbox_xyxy", [1.0, 1.0, 3.0, "3"]),
        ("bbox_xywh", [1.0, 1.0, 2.0, False]),
    ],
)
def test_v2_validator_rejects_non_strict_nested_jersey_number_types(
    tmp_path, capsys, field, value
):
    camera = _write_v2_number_fixture(tmp_path, frames=1)
    annotation_path = camera / "annotations.jsonl"
    frame = json.loads(annotation_path.read_text(encoding="utf-8"))
    frame["objects"][0]["jersey_number"][field] = value
    annotation_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "Camera_01" in output and "frame 1" in output and "L0" in output


@pytest.mark.parametrize(
    "missing_field",
    [
        "value",
        "placement",
        "bbox_source",
        "in_frame",
        "truncated",
        "visible_pixel_count",
        "bbox_xyxy",
        "bbox_xywh",
    ],
)
def test_v2_validator_rejects_missing_nested_jersey_number_fields(missing_field):
    record = {
        "value": 7,
        "placement": "back",
        "bbox_source": "visible_number_mask",
        "in_frame": False,
        "truncated": False,
        "visible_pixel_count": 0,
        "bbox_xyxy": None,
        "bbox_xywh": None,
    }
    del record[missing_field]

    errors = validate_jersey_number_record(
        record,
        label="[Camera_01] frame 1 entity L0",
        expected_value=7,
    )

    assert errors
    assert missing_field in errors[0]


@pytest.mark.parametrize(
    "record",
    [
        {
            "value": 7,
            "placement": "back",
            "bbox_source": "visible_number_mask",
            "in_frame": True,
            "truncated": False,
            "visible_pixel_count": 4,
            "bbox_xyxy": [1.0, 1.0, 3.0, 3.0],
            "bbox_xywh": [1.0, 1.0, 2.0, 2.0],
        },
        {
            "value": 7,
            "placement": "back",
            "bbox_source": "visible_number_mask",
            "in_frame": False,
            "truncated": False,
            "visible_pixel_count": 0,
            "bbox_xyxy": None,
            "bbox_xywh": None,
        },
    ],
)
def test_v2_validator_accepts_complete_visible_and_invisible_number_records(record):
    assert validate_jersey_number_record(
        record,
        label="[Camera_01] frame 1 entity L0",
        expected_value=7,
    ) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record.update({"in_frame": True, "visible_pixel_count": 0,
                                      "bbox_xyxy": None, "bbox_xywh": None}),
        lambda record: record.update({"in_frame": False, "visible_pixel_count": 4}),
        lambda record: record.update({"in_frame": False, "bbox_xyxy": [1.0, 1.0, 3.0, 3.0],
                                      "bbox_xywh": [1.0, 1.0, 2.0, 2.0]}),
    ],
)
def test_v2_validator_rejects_invalid_nested_jersey_number_semantics(
    tmp_path, capsys, mutate
):
    camera = _write_v2_number_fixture(tmp_path, frames=1)
    annotation_path = camera / "annotations.jsonl"
    frame = json.loads(annotation_path.read_text(encoding="utf-8"))
    mutate(frame["objects"][0]["jersey_number"])
    annotation_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")

    result = validate_annotation_dir(
        tmp_path, require_mot=False, require_jersey_number_mask=True
    )

    assert result == 1
    assert "Camera_01" in capsys.readouterr().out
