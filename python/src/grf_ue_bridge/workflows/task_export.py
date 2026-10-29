"""task 工作流：导出轨迹 + 写 provenance（复用 run_episode/export_episode）。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

from grf_ue_bridge.config import models as m
from grf_ue_bridge.config import resolver as _resolver


def _write_provenance(resolved: m.ResolvedTask, traj: Path) -> None:
    """按 task 写 episode 级 provenance（可移植，无本机路径）。"""
    prov = traj / "provenance"
    prov.mkdir(parents=True, exist_ok=True)

    src = Path(resolved.source_task_file)
    if src.is_file():
        shutil.copy2(src, prov / "task.json")

    (prov / "resolved-task.sanitized.json").write_text(
        json.dumps(_resolver.sanitize_resolved_task(resolved), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (prov / "export-profile.json").write_text(
        json.dumps(resolved.export_profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (prov / "ue-profile.json").write_text(
        json.dumps(resolved.ue_profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    mp = Path(resolved.actor_mapping)
    if mp.is_file():
        shutil.copy2(mp, prov / "actor-mapping.json")
    lock = Path(resolved.repo_root) / "external_sources.lock.json"
    if lock.is_file():
        shutil.copy2(lock, prov / "external_sources.lock.json")


def run_export(
    resolved: m.ResolvedTask, *, print_fn: Callable[[str], None] = print
) -> int:
    """执行导出（复用现有 run_episode/export_episode，不复制 exporter 实现）。"""
    from grf_ue_bridge.config.models import ExportConfig
    from grf_ue_bridge.exporter import compute_source_steps, export_episode
    from grf_ue_bridge.grf_runner import run_episode

    export_cfg = ExportConfig(**resolved.export_profile)
    if export_cfg.stop_on_done and (export_cfg.target_fps not in (0,10) or export_cfg.trajectory_time_scale != 1):
        raise ValueError('完整episode入口要求原生10FPS且time_scale=1，不重采样源比赛')
    from grf_ue_bridge.storage_policy import require_dataset_workspace
    require_dataset_workspace(resolved.dataset_root).mkdir(parents=True, exist_ok=True)
    traj = Path(resolved.trajectory_output)
    appearance_catalog = (resolved.ue_profile or {}).get("appearance")
    environment_profile = (resolved.ue_profile or {}).get("environment_profile")
    from grf_ue_bridge.seeded_episode import enabled, prepare_episode_recipe
    unified = enabled(resolved.ue_profile or {})
    unified_path = traj / "provenance" / "seeded_episode.json"
    if unified and unified_path.exists():
        raise ValueError("统一随机任务已存在；使用新attempt，不覆盖当前轨迹")
    appearance_manifest_path = traj / "provenance" / "appearance.json"
    environment_manifest_path = traj / "provenance" / "environment.json"
    if appearance_catalog is not None:
        appearance_manifest_path.unlink(missing_ok=True)
    if environment_profile is not None:
        environment_manifest_path.unlink(missing_ok=True)

    grf_steps = compute_source_steps(export_cfg)
    print_fn(f"Export task: {resolved.task_id}  episode={resolved.episode_name}")
    print_fn(
        f"  root seed: {export_cfg.seed}  scenario: {export_cfg.scenario}  "
        f"GRF steps: {grf_steps} (dataset steps: {export_cfg.num_steps} "
        f"× time_scale {export_cfg.trajectory_time_scale})"
    )
    print_fn(f"  trajectory output: {traj}")

    try:
        result = run_episode(
            scenario=export_cfg.scenario,
            seed=export_cfg.seed,
            num_steps=grf_steps,
            render=export_cfg.render,
            game_duration=export_cfg.game_duration,
            left_team_difficulty=export_cfg.left_team_difficulty,
            right_team_difficulty=export_cfg.right_team_difficulty,
            number_of_left_players_agent_controls=export_cfg.number_of_left_players_agent_controls,
            number_of_right_players_agent_controls=export_cfg.number_of_right_players_agent_controls,
            **({'stop_on_done':True} if export_cfg.stop_on_done else {}),
        )
        if export_cfg.stop_on_done:
            termination = {'schema':'futsalmot_episode_termination_v1',
                'status':'complete' if result.snapshots and result.snapshots[-1].done else 'step_limit_reached',
                'root_seed':export_cfg.seed,'requested_step_limit':grf_steps,
                'actual_frames':len(result.snapshots),'reset_after_terminal':False,
                'terminal_steps':[s.step for s in result.snapshots if s.done],
                'steps_left_first':result.snapshots[0].observation['steps_left'] if result.snapshots else None,
                'steps_left_last':result.snapshots[-1].observation['steps_left'] if result.snapshots else None,
                'score':list(result.score)}
            traj.mkdir(parents=True,exist_ok=True)
            (traj/'termination.json').write_text(json.dumps(termination,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            if termination['status']!='complete':
                raise ValueError('源episode未真实结束；保护上限不能作为完整比赛')
            export_cfg = export_cfg.model_copy(update={'num_steps':len(result.snapshots)})
        export_episode(export_cfg, result, traj)
        if export_cfg.stop_on_done:
            # 完整源可以放Saved的source目录，episode身份仍使用实际task名。
            meta_path=traj/'meta.json'
            meta_record=json.loads(meta_path.read_text(encoding='utf-8'))
            meta_record['episode_id']=resolved.episode_name
            meta_path.write_text(json.dumps(meta_record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        _write_provenance(resolved, traj)
    except Exception:
        if appearance_catalog is not None:
            appearance_manifest_path.unlink(missing_ok=True)
        if environment_profile is not None:
            environment_manifest_path.unlink(missing_ok=True)
        raise

    if appearance_catalog is not None or environment_profile is not None or unified:
        from grf_ue_bridge.validator import validate_episode

        if validate_episode(traj) != 0:
            if appearance_catalog is not None:
                appearance_manifest_path.unlink(missing_ok=True)
            if environment_profile is not None:
                environment_manifest_path.unlink(missing_ok=True)
            raise ValueError(f"episode inputs are invalid: {traj}")
        meta_path = traj / "meta.json"
        frames_path = traj / "frames.jsonl"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if unified:
        recipe = prepare_episode_recipe(traj, resolved.ue_profile)
        print_fn(f"Seeded episode prepared: {recipe['fingerprint']}")
        print_fn(f"Provenance written: {traj / 'provenance'}")
        return 0

    if appearance_catalog is not None:
        try:
            from grf_ue_bridge.appearance import (
                build_appearance_manifest,
                validate_appearance_manifest,
                write_appearance_manifest,
            )

            manifest = build_appearance_manifest(meta, frames_path, appearance_catalog)
            if manifest.get("policy") != appearance_catalog.get("policy"):
                raise ValueError(
                    "生成的 appearance manifest policy 与 catalog policy 不一致"
                )
            write_appearance_manifest(traj, manifest)
            written_manifest = json.loads(
                appearance_manifest_path.read_text(encoding="utf-8")
            )
            errors = validate_appearance_manifest(
                written_manifest,
                meta=meta,
                frames_path=frames_path,
                catalog=appearance_catalog,
            )
            if errors:
                raise ValueError(
                    "生成的 appearance manifest 校验失败: " + "; ".join(errors)
                )
        except Exception:
            appearance_manifest_path.unlink(missing_ok=True)
            raise

    if environment_profile is not None:
        try:
            from grf_ue_bridge.environment import (
                build_environment_manifest,
                validate_environment_manifest,
                write_environment_manifest,
            )

            manifest = build_environment_manifest(meta, frames_path, environment_profile)
            write_environment_manifest(traj, manifest)
            written_manifest = json.loads(
                environment_manifest_path.read_text(encoding="utf-8")
            )
            errors = validate_environment_manifest(
                written_manifest,
                meta=meta,
                frames_path=frames_path,
                profile=environment_profile,
            )
            if errors:
                raise ValueError(
                    "生成的 environment manifest 校验失败: " + "; ".join(errors)
                )
        except Exception:
            environment_manifest_path.unlink(missing_ok=True)
            raise

    print_fn(f"Provenance written: {traj / 'provenance'}")
    return 0
