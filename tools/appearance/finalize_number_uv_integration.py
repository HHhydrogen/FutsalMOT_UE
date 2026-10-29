"""仅消费已有同job EXR/RGB，导出实例mask、数字mask及数字bbox，不重渲染。"""

import json
import sys
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python/src"))
from grf_ue_bridge.number_mask_exr import export_number_masks
from grf_ue_bridge.cryptomatte import convert_render_mask_dir
from grf_ue_bridge.mask_annotator import annotate_masks_dir
from grf_ue_bridge.jersey_number_annotator import annotate_jersey_number_masks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", default="number_uv_size115_down_s1048_a01", choices=("number_uv_random_s1048_a02", "number_uv_size115_s1048_a01", "number_uv_size115_down_s1048_a01"))
    attempt = parser.parse_args().attempt
    test = Path("G:/FutsalMOT_Dataset/test") / attempt
    episode = test / "raw" / attempt
    local = ROOT / "Saved/JerseyNumberUV" / attempt
    camera = episode / "CineCam_01"
    plan = json.loads((local / "provenance/number_uv.json").read_text(encoding="utf-8"))
    public = episode / "provenance"
    public.mkdir(exist_ok=True)
    for name in ("appearance.json", "number_uv.json"):
        (public / name).write_bytes((local / "provenance" / name).read_bytes())
    mapping = json.loads((ROOT / "python/ue/actor_mapping.example.json").read_text(encoding="utf-8"))
    number = export_number_masks([camera])
    status, frames = convert_render_mask_dir(camera / "render_mask", mapping, camera / "mask", 10, 0.1, 10, workers=1)
    if status != "success" or len(frames) != 10:
        raise RuntimeError("实例EXR导出未完成: " + status)
    code = annotate_masks_dir(episode, formats="json", workers=1)
    if code:
        raise RuntimeError("实例bbox写入失败")
    errors = annotate_jersey_number_masks(episode, manifest=plan, cameras=[camera])
    if errors:
        raise RuntimeError(errors)
    annotations = [json.loads(line) for line in (camera / "annotations.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    number_objects = [obj for frame in annotations for obj in frame["objects"] if obj.get("entity_id") in mapping and obj.get("entity_id") != "BALL"]
    if len(annotations) != 10 or len(number_objects) != 100:
        raise RuntimeError("十帧/百人物标注不完整")
    summary = json.loads((episode / "render_summary.json").read_text(encoding="utf-8"))
    report = {"schema": "futsalmot_number_uv_integration_postprocess_v1", "status": "postprocess_complete",
              "attempt": attempt, "raw_mrq_summary_status": summary["status"],
              "rerendered": False, "rgb_frames": len(list((camera / "img1").glob("*.png"))),
              "instance_mask_frames": 10, "number_mask_frames": number["frames"],
              "number_objects": len(number_objects),
              "visible_number_objects": sum(obj["jersey_number"]["visible_pixel_count"] > 0 for obj in number_objects),
              "number_export": number, "render_source": "same_mrq_job_float_EXR",
              "original_failure_kept": summary["status"] == "failed", "production_admitted": False,
              "created_at_utc": datetime.now(timezone.utc).isoformat()}
    (local / "postprocess_complete.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lifecycle = json.loads((test / "_test_lifecycle.json").read_text(encoding="utf-8-sig"))
    lifecycle.update(state="complete", active=False,
                     finished_at_utc=datetime.now(timezone.utc).isoformat(),
                     expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                     purpose="号码集成10帧输出；关键收据保留Saved；临时媒体24小时后清理")
    (test / "_test_lifecycle.json").write_text(json.dumps(lifecycle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
