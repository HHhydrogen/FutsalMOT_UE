"""task 工作流：后处理（cryptomatte → annotate → 可选 validate）。

按 task 参数顺序调用现有命令，非自动门禁；支持跳过单阶段便于局部重跑。
"""

from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Mapping
from typing import Callable

from grf_ue_bridge.config import models as m
from grf_ue_bridge.task_requirements import resolve_task_requirements


def _annotate_jersey_numbers_if_v2(
    dataset: Path,
    trajectory: Path,
    resolved: m.ResolvedTask,
    print_fn: Callable[[str], None],
    *,
    binding_validated: bool = False,
) -> bool:
    if not binding_validated and not _validate_v2_appearance_binding(
        trajectory, resolved, print_fn
    ):
        return False
    appearance = (getattr(resolved, "ue_profile", {}) or {}).get("appearance") or {}
    uv = ((getattr(resolved, "ue_profile", {}) or {}).get("uv_numbering") or {}).get("enabled")
    if appearance.get("policy") != "futsalmot_appearance_v2" and not uv:
        return True
    manifest_path = trajectory / "provenance" / "appearance.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        from grf_ue_bridge.jersey_number_annotator import annotate_jersey_number_masks
        if uv:
            plan = json.loads((trajectory / "provenance" / "number_uv.json").read_text(encoding="utf-8"))
            if plan.get("appearance_fingerprint") != manifest.get("fingerprint"):
                raise ValueError("UV号码清单与原appearance不匹配")
            public = dataset / "provenance"
            public.mkdir(parents=True, exist_ok=True)
            from dataset_export import write_json_atomic
            write_json_atomic(public / "appearance.json", manifest)
            write_json_atomic(public / "number_uv.json", plan)
            manifest = plan
        cameras = sorted(d.parent for d in dataset.rglob("camera.json")) if dataset.is_dir() else []
        if uv:
            from grf_ue_bridge.number_mask_exr import export_number_masks
            timing = json.loads((trajectory / "meta.json").read_text(encoding="utf-8"))["timing"]
            export_number_masks(cameras, source_step_seconds=timing.get("source_step_seconds", 0.1),
                                playback_fps=timing.get("playback_fps", 10))
        errors = annotate_jersey_number_masks(dataset, manifest=manifest, cameras=cameras)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"无法读取球衣号码 manifest: {exc}"]
    if errors:
        for error in errors:
            print_fn(f"ERROR jersey-number: {error}")
        return False
    print_fn(f"jersey-number annotate 完成（{len(cameras)} camera）")
    return True


def _validate_v2_appearance_binding(
    trajectory: Path,
    resolved: m.ResolvedTask,
    print_fn: Callable[[str], None],
) -> bool:
    """在所有 v2 postprocess 成功路径前校验 manifest 输入绑定。"""
    appearance = (getattr(resolved, "ue_profile", {}) or {}).get("appearance") or {}
    uv = ((getattr(resolved, "ue_profile", {}) or {}).get("uv_numbering") or {}).get("enabled")
    if appearance.get("policy") != "futsalmot_appearance_v2" and not uv:
        return True
    manifest_path = trajectory / "provenance" / "appearance.json"
    errors = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        meta = json.loads((trajectory / "meta.json").read_text(encoding="utf-8"))
        frames_path = trajectory / "frames.jsonl"
        if not frames_path.is_file():
            raise ValueError(f"缺少当前 frames.jsonl: {frames_path}")
        catalog = appearance
        if hasattr(catalog, "model_dump"):
            catalog = catalog.model_dump(exclude_none=True)
        if not isinstance(catalog, Mapping):
            raise ValueError("resolved appearance catalog 必须是对象")
        from grf_ue_bridge.appearance import validate_appearance_manifest

        manifest_errors = validate_appearance_manifest(
            manifest,
            meta=meta,
            frames_path=frames_path,
            catalog=catalog,
        )
        if manifest_errors:
            raise ValueError("; ".join(manifest_errors))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"无法读取球衣号码 manifest: {exc}"]
    if errors:
        for error in errors:
            print_fn(f"ERROR jersey-number: {error}")
        return False
    return True


def _cryptomatte_camera(
    cam: Path,
    mapping_dict: dict,
    num_steps: int,
    step_sec: float,
    fps: int,
    pp: dict,
    print_fn: Callable[[str], None],
) -> bool:
    from grf_ue_bridge.cryptomatte import convert_render_mask_dir

    rmask = cam / "render_mask"
    mdir = cam / "mask"
    if not rmask.exists():
        print_fn(f"  SKIP {cam.name}: 无 render_mask/")
        return True
    status, per = convert_render_mask_dir(
        rmask, mapping_dict, mdir, num_steps, step_sec, fps,
        png_compress_level=pp.get("png_compress_level", 1),
        workers=pp.get("workers", 4),
        chunk_size=pp.get("chunk_size", 0),
    )
    print_fn(f"  [{status.upper()}] {cam.name}: {len(per)} 帧 mask 已生成")
    return status == "success"


def run_postprocess(
    resolved: m.ResolvedTask,
    *,
    skip_cryptomatte: bool = False,
    skip_annotate: bool = False,
    skip_validate: bool = False,
    skip_pose: bool = False,
    skip_debug: bool = False,
    print_fn: Callable[[str], None] = print,
) -> int:
    """按 resolved task 执行后处理，返回退出码（0=成功）。"""
    pp = resolved.postprocess
    requirements = resolve_task_requirements(resolved)
    dataset = Path(resolved.dataset_episode_dir)
    traj = Path(resolved.trajectory_output)
    from grf_ue_bridge.seeded_episode import enabled, load_episode_recipe
    if enabled(resolved.ue_profile or {}):
        recipe = load_episode_recipe(traj,resolved.ue_profile)
        if 'floor' in recipe['components']:
            floor_report = json.loads((traj/'provenance/floor_application.json').read_text(encoding='utf-8'))
            if floor_report.get('state') != 'restored' or floor_report.get('recipe') != recipe['components']['floor']:
                raise ValueError('统一随机地板未完成匹配的应用/恢复，拒绝后处理')
    mapping = Path(resolved.actor_mapping)

    yolo_pose = pp.get("yolo_pose") or {}
    pose_enabled = requirements.requires_pose
    debug_cfg = pp.get("debug") or {}
    debug_enabled = bool(debug_cfg.get("enabled", False))

    print_fn(f"Postprocess task: {resolved.task_id}")
    print_fn(f"  dataset: {dataset}")
    print_fn(f"  yolo_pose enabled: {pose_enabled}")
    print_fn(f"  debug enabled: {debug_enabled}")
    if not requirements.requires_mot:
        print_fn(
            "  MOT requirement disabled: missing gt/gt.txt will be skipped; "
            "an existing MOT file will still be validated"
        )

    # v2 的 manifest/catalog/fingerprint/trajectory 绑定是整个 workflow 的
    # 成功前置条件；skip_annotate 只跳过号码 annotation 写入，不能跳过该 gate。
    if not _validate_v2_appearance_binding(traj, resolved, print_fn):
        return 1

    # 1) Cryptomatte EXR → mask
    if not skip_cryptomatte:
        # 先 import cryptomatte（会补 ue/ 到 sys.path），再导入 dataset_export
        from grf_ue_bridge.cryptomatte import convert_render_mask_dir  # noqa: F401
        from dataset_export import load_episode, load_mapping  # noqa: E402

        if not traj.is_dir() or not (traj / "meta.json").is_file():
            print_fn(f"ERROR: trajectory 输出不存在（先运行 task export）: {traj}", )
            return 1
        meta, _ = load_episode(traj)
        num_steps = int(meta["timing"]["num_steps"])
        step_sec = float(meta["timing"]["source_step_seconds"])
        fps = int(meta["timing"].get("playback_fps", 30))
        mapping_dict = load_mapping(mapping)

        cams = sorted(d.parent for d in dataset.rglob("camera.json")) if dataset.is_dir() else []
        if not cams:
            print_fn(f"ERROR: 数据集目录下没有 camera 子目录: {dataset}")
            return 1
        total_ok = 0
        for cam in cams:
            if _cryptomatte_camera(cam, mapping_dict, num_steps, step_sec, fps, pp, print_fn):
                total_ok += 1
        print_fn(f"cryptomatte-to-mask 完成（{total_ok}/{len(cams)} camera）")
        if total_ok == 0:
            return 1

    # 2) annotate-masks
    if not skip_annotate:
        from grf_ue_bridge.mask_annotator import annotate_masks_dir

        formats = ",".join(pp.get("formats") or ["all"]) or "all"
        rc = annotate_masks_dir(
            dataset,
            include_ball=pp.get("include_ball", True),
            workers=pp.get("workers", 4),
            chunk_size=pp.get("chunk_size", 50),
            formats=formats,
            clean_stale=pp.get("clean_stale", True),
        )
        print_fn(f"annotate-masks 完成（exit={rc}）")
        if rc != 0:
            return rc

        if not _annotate_jersey_numbers_if_v2(
            dataset,
            traj,
            resolved,
            print_fn,
            binding_validated=True,
        ):
            return 1

    # 3) 可选 validate-annotations
    if not skip_validate:
        from grf_ue_bridge.annotation_validator import validate_annotation_dir

        level = pp.get("validation_level", "full")
        validation_kwargs = {
            "workers": pp.get("workers", 4),
            "validation_level": level,
            "require_mot": requirements.requires_mot,
            "require_mask": requirements.requires_instance_mask,
            "require_yolo_det": requirements.requires_yolo_det,
            "require_yolo_seg": requirements.requires_yolo_seg,
        }
        appearance = (getattr(resolved, "ue_profile", {}) or {}).get("appearance") or {}
        if appearance.get("policy") == "futsalmot_appearance_v2" or ((getattr(resolved, "ue_profile", {}) or {}).get("uv_numbering") or {}).get("enabled"):
            validation_kwargs["require_jersey_number_mask"] = True
        rc = validate_annotation_dir(
            dataset,
            **validation_kwargs,
        )
        print_fn(f"validate-annotations({level}) 完成（exit={rc}）")
        if rc != 0:
            return rc

    # 4) 可选 YOLO Pose（postprocess.yolo_pose.enabled）
    if pose_enabled and skip_pose:
        print_fn("required step skipped: Runtime Pose is required by task")
        return 1
    if pose_enabled:
        from grf_ue_bridge.pose_annotator import annotate_pose_dir

        print_fn("annotate-pose（YOLO Pose 12 点肢体关键点）...")
        rc = annotate_pose_dir(
            dataset,
            pose_cfg=yolo_pose,
            workers=pp.get("workers", 4),
            write_yaml=bool(yolo_pose.get("write_dataset_yaml", True)),
        )
        print_fn(f"annotate-pose 完成（exit={rc}）")
        if rc != 0:
            return rc
        from grf_ue_bridge.pose_validator import validate_pose_dir

        rc = validate_pose_dir(
            dataset,
            workers=pp.get("workers", 4),
            validation_level=pp.get("validation_level", "full"),
            visibility_neighborhood_radius=int(yolo_pose.get("visibility_neighborhood_radius", 2)),
        )
        print_fn(f"validate-pose 完成（exit={rc}）")
        if rc != 0:
            return rc

    # 5) 可选 debug 全量可视化（postprocess.debug.enabled）：bbox / 彩色 mask / pose + 视频
    if debug_enabled and not skip_debug:
        from grf_ue_bridge.debug import debug_annotations_dir

        print_fn("debug 可视化（bbox / 彩色 mask / pose 关节点 + 三套视频）...")
        rc = debug_annotations_dir(dataset, cfg=debug_cfg, print_fn=print_fn)
        print_fn(f"debug 可视化完成（exit={rc}）")
        if rc != 0:
            return rc

    return 0
