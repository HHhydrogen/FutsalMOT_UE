"""汇总源 UV/UE slot 证据并输出待验收的单人号码位置，不开启正式号码功能。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "ue"))
from jersey_number_uv_contract import SOURCE_JERSEY_UV_TOPOLOGY, atlas_cell, validate_calibration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root
    probe = json.loads((root / "source_probe.json").read_text(encoding="utf-8"))
    ue = json.loads((root / "ue_slot_probe.json").read_text(encoding="utf-8"))
    assert not ue["dirty"]
    source_meshes = []
    for player in probe["players"]:
        matches = [mesh for mesh in player["meshes"] if mesh["polygons"] == 1034]
        assert len(matches) == 1
        mesh = matches[0]
        assert mesh["uv_topology_sha256"] == SOURCE_JERSEY_UV_TOPOLOGY
        assert [island["face_count"] for island in mesh["islands"]] == [646, 388]
        source_meshes.append((player, mesh))
    assert [player["player_id"] for player, _ in source_meshes] == list(range(3, 10))
    rows = []
    for item in ue["players"]:
        assert item["slots"].count("材质") == 1
        rows.append({"player_id": item["player_id"], "mesh": item["mesh"],
                     "jersey_slot_name": "材质", "jersey_slot_index": item["slots"].index("材质"),
                     "source_uv_topology_sha256": SOURCE_JERSEY_UV_TOPOLOGY})
    # Legacy FBX importer 本机源码将 V 转换为 1-V；此处只是原型起点。
    calibration = {
        "schema": "futsalmot_jersey_number_uv_calibration", "version": 1,
        "source_uv_topology_sha256": SOURCE_JERSEY_UV_TOPOLOGY,
        "source_uv_rect": [0.16, 0.56, 0.37, 0.76],
        "ue_uv_rect": [0.16, 0.24, 0.37, 0.44], "flip_u": True, "flip_v": True,
        "placement_status": "PROPOSED_NOT_UE_VERIFIED",
        "source_evidence": "source_probe.json", "ue_slot_evidence": "ue_slot_probe.json",
        "ue_mesh_uv_verified": False, "back_visible_verified": False,
        "front_empty_verified": False, "animation_verified": False,
        "occlusion_verified": False, "paired_mask_verified": False,
        "camera": "", "sequence": "", "frame_index": None,
        "mesh": rows[0]["mesh"], "evidence_rgb": "", "evidence_number_mask": "",
        "players": rows,
    }
    calibration["remaining_gate_errors"] = validate_calibration(calibration)
    assert calibration["remaining_gate_errors"]
    (root / "calibration_proposed.json").write_text(json.dumps(calibration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    image = Image.new("RGB", (1024, 1024), (25, 25, 30))
    draw = ImageDraw.Draw(image)
    mesh = source_meshes[0][1]
    back_ids = set(mesh["islands"][1]["polygon_indices"])
    for poly in mesh["uv_polygons"]:
        points = [(u * 1024, (1.0 - v) * 1024) for u, v in poly["uv"]]
        draw.line(points + points[:1], fill=(55, 170, 180) if poly["polygon_index"] in back_ids else (140, 70, 70), width=1)
    atlas = Image.open(root / "atlas_v1/jersey_numbers_01_99.png").convert("RGBA")
    cell = atlas.width // 16
    column, row = atlas_cell(37)
    tile = atlas.crop((column * cell, row * cell, (column + 1) * cell, (row + 1) * cell))
    tile = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    u0, v0, u1, v1 = calibration["ue_uv_rect"]
    box = [round(u0 * 1024), round(v0 * 1024), round(u1 * 1024), round(v1 * 1024)]
    tile = tile.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    image.paste(tile, (box[0], box[1]), tile)
    draw.rectangle(box, outline=(245, 210, 40), width=2)
    draw.text((600, 30), "BACK UV: cyan; FRONT UV: red", fill="white")
    draw.text((600, 50), "Number 37: proposed calibration", fill="white")
    draw.text((600, 70), "CPU source UV evidence only", fill="white")
    draw.text((600, 90), "UE visibility/mask gates: NOT PASSED", fill=(255, 170, 90))
    image.save(root / "source_uv_number37_proposal.png")
    print("JERSEY_UV_CALIBRATION_PREPARED " + json.dumps({"matching_sources": 7, "ue_slot_indices": [x["jersey_slot_index"] for x in rows], "production_enabled": False}))


if __name__ == "__main__":
    main()
