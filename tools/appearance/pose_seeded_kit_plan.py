"""复用原appearance v1清单，为固定Pose角色准备服装绑定；不重新实现随机分配。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python/src"))
from grf_ue_bridge.appearance import validate_appearance_manifest


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def build_binding(manifest, meta, frames_path, catalog, pose_targets):
    if manifest.get("policy") != "futsalmot_appearance_v1" or manifest.get("version") != 1:
        raise ValueError("只复用已验无号码appearance v1，不接号码WIP")
    errors = validate_appearance_manifest(manifest, meta=meta, frames_path=Path(frames_path), catalog=catalog)
    if errors:
        raise ValueError("原外观清单校验失败：" + "; ".join(errors))
    expected = {side + str(i) for side in "LR" for i in range(5)}
    if (len(pose_targets) != 10 or {t["entity_id"] for t in pose_targets} != expected
            or len({t["actor_object_name"] for t in pose_targets}) != 10
            or any(t["component_object_name"] != "MPFBVisual" for t in pose_targets)):
        raise ValueError("须绑定十个唯一实体/Actor及实际MPFBVisual")
    targets = {t["entity_id"]: t for t in pose_targets}
    rows = []
    for entity in manifest["entities"]:
        target = targets[entity["entity_id"]]
        rows.append(dict(entity_id=entity["entity_id"], team=entity["team"],
            is_goalkeeper=entity["is_goalkeeper"], kit_class=entity["kit_class"],
            kit_set_id=entity["kit_set_id"], actor_object_name=target["actor_object_name"],
            component_object_name=target["component_object_name"],
            semantic_materials={"Jersey": entity["jersey_material"], "Shorts": entity["shorts_material"]}))
    result = dict(schema="futsalmot_pose_existing_seeded_kit_binding_candidate_v1",
        status="CPU_binding_only_not_UE_applied", source_appearance_fingerprint=manifest["fingerprint"],
        source_policy=manifest["policy"], root_seed=manifest["root_seed"],
        ue_visual_seed=manifest["ue_visual_seed"], original_full_trajectory_sha256=manifest["trajectory_sha256"],
        source_catalog_fingerprint=manifest["catalog_fingerprint"],
        kit_classes=deepcopy(manifest["kit_classes"]), entities=rows,
        pose_targets_fingerprint=fingerprint(pose_targets),
        preserves=["fixed_pose_mesh_roster", "skin", "animation", "head_calibration", "motion", "camera", "split"],
        no_new_random_assignment=True, sequence_constant=True, numbers_enabled=False,
        runtime_order=["native_visual_mesh_override", "apply_semantic_Jersey_Shorts_only",
            "readback_material_paths_and_actor_identity", "GPU_LBS_warmup", "MRQ"],
        requires_native_hook_after_material_reset=True, render_authorized=False,
        runtime_material_readback_verified=False, target_color_separation_verified=False,
        source_visibility_unchanged=True, test116187_read=False)
    result["fingerprint"] = fingerprint(result)
    return result


def from_source_input(path):
    path = Path(path)
    source = read(path)
    refs = source["original_source"]
    for key in ("meta", "frames"):
        if sha(refs[key]["path"]) != refs[key]["sha256"]:
            raise ValueError("原始运动输入发生变化：" + key)
    meta_path = Path(refs["meta"]["path"])
    manifest_path = meta_path.parent / "provenance/appearance.json"
    profile_path = meta_path.parent / "provenance/ue-profile.json"
    manifest, meta = read(manifest_path), read(meta_path)
    prefix = read(source["prepared_prefix"]["meta"]["path"])
    if (source["seed"] != manifest["root_seed"]
            or prefix["randomness"]["ue_visual_seed"] != manifest["ue_visual_seed"]):
        raise ValueError("Pose前缀和原外观seed不匹配")
    binding = build_binding(manifest, meta, refs["frames"]["path"],
                            read(profile_path)["appearance"], source["targets"])
    return dict(source_input=dict(path=str(path), sha256=sha(path)),
        original_appearance=dict(path=str(manifest_path), sha256=sha(manifest_path)),
        original_ue_profile=dict(path=str(profile_path), sha256=sha(profile_path)),
        split=source["split"], source_frame_range=source["selected_source_frame_range"], binding=binding)
