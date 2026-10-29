"""准备一次完整随机外观+UV号码集成短样；原轨迹和旧manifest只读。"""

import json
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python/src"))
sys.path.insert(0, str(ROOT / "python/ue"))
from grf_ue_bridge.appearance import build_appearance_manifest
from jersey_number_uv_contract import DEFAULT_UV_RECT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", nargs="?", default="a01", choices=("a01", "a02"))
    parser.add_argument("--profile", default="size115down", choices=("integration", "size115", "size115down"))
    args = parser.parse_args()
    revision = args.revision
    prefixes = {"integration": "number_uv_random_s1048_", "size115": "number_uv_size115_s1048_", "size115down": "number_uv_size115_down_s1048_"}
    attempt = prefixes[args.profile] + revision
    local = ROOT / "Saved/JerseyNumberUV" / attempt
    local.mkdir(parents=True, exist_ok=False)
    source = ROOT / "Saved/Production/v1_no_numbers_4k/sources/source_s00001048"
    meta = json.loads((source / "meta.json").read_text(encoding="utf-8"))
    meta["episode_id"] = attempt
    meta["timing"]["num_steps"] = 10
    frames = (source / "frames.jsonl").read_text(encoding="utf-8").splitlines()[:10]
    (local / "frames.jsonl").write_text("\n".join(frames) + "\n", encoding="utf-8")
    (local / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    profile = json.loads((source / "provenance/ue-profile.json").read_text(encoding="utf-8"))
    profile.pop("environment_profile", None)
    profile.pop("camera_mapping", None)
    namespace = {"integration": "RandomIntegration", "size115": "Size115_", "size115down": "Size115Down_"}[args.profile]
    profile["sequence_package_path"] = "/Game/FutsalMOT/Development/JerseyNumberV1/" + namespace + revision.upper()
    profile["sequences"] = [{"name": "LS_Number_C1", "camera_actor": "CineCam_01"}]
    profile["replace_existing"] = False
    rect = {"integration": [0.16, 0.24, 0.37, 0.44], "size115": [0.14425, 0.225, 0.38575, 0.455], "size115down": list(DEFAULT_UV_RECT)}[args.profile]
    profile["uv_numbering"] = {"enabled": True, "uv_rect": rect, "flip_u": True, "flip_v": True}
    ann = profile["annotation_export"]
    ann.update(image_width=1920, image_height=1080, cameras=["CineCam_01"],
               frame_start=0, frame_end=10, export_mot=False, export_internal_jsonl=True)
    ann["render_rgb"].update(output_resolution_x=1920, output_resolution_y=1080, frame_rate=10)
    manifest = build_appearance_manifest(meta, local / "frames.jsonl", profile["appearance"])
    provenance = local / "provenance"
    provenance.mkdir()
    (provenance / "appearance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    resolved = {"schema": "futsalmot_resolved_task", "version": 1,
                "task_id": attempt, "episode_name": attempt,
                "repo_root": str(ROOT / "python"), "ue_project_root": str(ROOT),
                "dataset_root": "G:/FutsalMOT_Dataset/test/" + attempt + "/raw",
                "trajectory_output": str(local),
                "actor_mapping": str(ROOT / "python/ue/actor_mapping.example.json"),
                "ue_profile": profile,
                "export_profile": {"num_steps": 10, "playback_fps": 10, "target_fps": 10},
                "postprocess": {"workers": 1, "validation_level": "full"}}
    (local / "resolved.json").write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"attempt": attempt, "resolved": str(local / "resolved.json"),
                      "random_entities": [{k: row[k] for k in ("entity_id", "player_id", "skin_id", "kit_set_id")} for row in manifest["entities"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
