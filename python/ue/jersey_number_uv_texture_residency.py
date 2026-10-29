"""测试图集限时驻留：request/inspect/release 分开调用，不阻塞 Editor 主循环。"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jersey_number_uv_build_preview import TEXTURE_PATH
from jersey_number_uv_material_readiness import _dirty_packages

EXPECTED_DIMENSIONS = [2048, 1024]
MIN_CAPTURE_SECONDS = 15
ACTION_KEY = "FUTSALMOT_JERSEY_UV_RESIDENCY_ACTION"
SECONDS_KEY = "FUTSALMOT_JERSEY_UV_RESIDENCY_SECONDS"


def parse_probe_log(text, marker):
    """只读取当前唯一标记范围内的目标纹理，不回退到历史成功日志。"""
    begin = "LogPython: JERSEY_UV_TEXTURE_PROBE_BEGIN " + marker
    end = "LogPython: JERSEY_UV_TEXTURE_PROBE_END " + marker
    start = text.find(begin)
    finish = text.find(end, start + len(begin)) if start >= 0 else -1
    if start < 0 or finish < 0:
        raise ValueError("本次纹理诊断日志标记缺失或不完整")
    block = text[start + len(begin):finish]
    object_path = TEXTURE_PATH + "." + TEXTURE_PATH.rsplit("/", 1)[-1]
    header = "LogContentStreaming: Texture: Texture2D " + object_path
    lines = block.splitlines()
    matches = [index for index, line in enumerate(lines) if line.endswith(header)]
    if len(matches) != 1:
        raise ValueError("当前标记中没有唯一测试 atlas 日志")
    lines = lines[matches[0]:]
    for index, line in enumerate(lines[1:], 1):
        if "LogContentStreaming: Texture:" in line:
            lines = lines[:index]
            break
    block = "\n".join(lines)
    result = {"log_marker": marker, "texture_path": TEXTURE_PATH, "raw_probe_log": block}
    for label, field in (("Current", "current_dimensions"), ("Wanted", "wanted_dimensions")):
        match = re.search(label + r" size \[2D Mips\]:\s*(\d+)x(\d+)\s*\[(\d+)\]", block)
        if not match:
            raise ValueError("缺少 " + label + " 纹理尺寸")
        result[field] = [int(match[1]), int(match[2])]
        result[field + "_mips"] = int(match[3])
    remaining = re.search(r"Force all mips:\s*([0-9.]+) seconds left", block)
    result["force_seconds_remaining"] = float(remaining[1]) if remaining else None
    return result


def evaluate_residency(session, probe, *, editor_pid, now):
    """完整驻留、当前 PID、所属请求及到期预算必须同时满足。"""
    errors = []
    session = session if isinstance(session, dict) else {}
    if (session.get("state") != "requested" or session.get("editor_pid") != editor_pid
            or session.get("texture_path") != TEXTURE_PATH or not session.get("request_id")):
        errors.append("没有属于本次 Editor 的有效驻留请求")
    try:
        budget = (datetime.fromisoformat(session["expires_at_utc"]) - now).total_seconds()
        if budget < MIN_CAPTURE_SECONDS:
            errors.append("请求已到期或不足 15 秒捕获预算")
    except (KeyError, TypeError, ValueError):
        errors.append("请求到期时间无效")
    if probe.get("texture_path") != TEXTURE_PATH:
        errors.append("纹理身份不符")
    if probe.get("current_dimensions") != EXPECTED_DIMENSIONS or probe.get("wanted_dimensions") != EXPECTED_DIMENSIONS:
        errors.append("atlas 的当前/目标 mip 尚未达到完整 2048×1024")
    remaining = probe.get("force_seconds_remaining")
    if type(remaining) not in (int, float) or not math.isfinite(remaining) or remaining < MIN_CAPTURE_SECONDS:
        errors.append("引擎没有确认足够的限时驻留预算")
    return errors


def release_required(session, *, editor_pid, now):
    """到期后放弃请求所有权，避免旧记录撤销后来由其它调用发起的请求。"""
    if not (isinstance(session, dict) and session.get("state") == "requested"
            and session.get("editor_pid") == editor_pid and session.get("texture_path") == TEXTURE_PATH
            and session.get("request_id")):
        raise ValueError("拒绝释放未知、旧 PID 或非本脚本请求")
    return datetime.fromisoformat(session["expires_at_utc"]) > now


def _request_gate(unreal):
    import diagnose_episode_appearance as diagnostic
    from diagnose_episode_environment import _runtime_state

    mapping = json.loads(Path(__file__).with_name("actor_mapping.example.json").read_text(encoding="utf-8"))
    gate = diagnostic.collect_diagnostic(unreal, mapping)
    runtime, errors = _runtime_state(unreal)
    assert gate["task7_preflight_can_start"] and not gate["dirty_package_paths"], gate
    assert not errors and runtime["play_session_active"] is False and runtime["mrq_state"] == "inactive", runtime


def main():
    import unreal

    action = os.environ.get(ACTION_KEY, "inspect")
    assert action in ("request", "inspect", "release"), "驻留 action 只允许 request/inspect/release"
    project = Path(unreal.Paths.project_dir()).resolve()
    evidence = project / "Saved/JerseyNumberUV"
    evidence.mkdir(parents=True, exist_ok=True)
    session_path = evidence / "texture_residency_session.json"
    session = json.loads(session_path.read_text(encoding="utf-8")) if session_path.exists() else None
    now = datetime.now(timezone.utc)
    report = {"action": action, "captured_at_utc": now.isoformat(), "editor_pid": os.getpid(),
              "texture_path": TEXTURE_PATH, "production_enabled": False, "ready_for_poc": False,
              "dirty_before": _dirty_packages(unreal)}
    texture = unreal.load_asset(TEXTURE_PATH)
    assert texture is not None and texture.get_class().get_name() == "Texture2D", "测试 atlas class 不符"
    setter = getattr(texture, "set_force_mip_levels_to_be_resident", None)
    assert callable(setter), "MANUAL_REQUIRED: 缺少已验证的限时 mip 驻留接口"
    if action == "request":
        _request_gate(unreal)
        seconds = float(os.environ.get(SECONDS_KEY, "300"))
        assert math.isfinite(seconds) and 30 <= seconds <= 300, "请求只能为 30..300 秒，不允许无限延期"
        if session and session.get("state") == "requested" and session.get("editor_pid") == os.getpid():
            assert datetime.fromisoformat(session["expires_at_utc"]) <= now, "已有未到期请求；先释放，禁止自动续期"
        session = {"state": "requested", "request_id": uuid.uuid4().hex, "texture_path": TEXTURE_PATH,
                   "editor_pid": os.getpid(), "requested_at_utc": now.isoformat(), "requested_seconds": seconds,
                   "expires_at_utc": (now + timedelta(seconds=seconds)).isoformat()}
        setter(seconds, 0)
        try:
            session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        except BaseException:
            setter(0.0, 0)
            raise
        report["next_step"] = "返回 Editor 主循环后另行 inspect；不得在此调用中 sleep 或直接捕获"
    elif action == "release":
        if release_required(session, editor_pid=os.getpid(), now=now):
            # 只撤销仍属本脚本的运行时请求；不改/保存 texture 属性或生产材质。
            setter(0.0, 0)
            session.update(state="released", released_at_utc=now.isoformat())
        else:
            session.update(state="expired", ownership_expired_at_utc=now.isoformat())
        session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        marker = uuid.uuid4().hex
        log_path = project / "Saved/Logs/FustalMOT_UEDataset.log"
        offset = log_path.stat().st_size
        world = unreal.EditorLevelLibrary.get_editor_world()
        assert world is not None, "MANUAL_REQUIRED: console probe 必须有当前 Editor World 上下文"
        unreal.log("JERSEY_UV_TEXTURE_PROBE_BEGIN " + marker)
        unreal.SystemLibrary.execute_console_command(world, "InvestigateTexture T_NumberAtlas_UV_v1")
        unreal.log("JERSEY_UV_TEXTURE_PROBE_END " + marker)
        # FLUSHLOG 是本机 UEngine 原生命令；只刷新日志，不推进或等待渲染。
        unreal.SystemLibrary.execute_console_command(world, "FLUSHLOG")
        with log_path.open("rb") as stream:
            stream.seek(offset)
            text = stream.read().decode("utf-8", errors="replace")
        try:
            report["probe"] = parse_probe_log(text, marker)
            report["readiness_errors"] = evaluate_residency(session, report["probe"], editor_pid=os.getpid(), now=now)
        except ValueError as exc:
            report["readiness_errors"] = [str(exc)]
        report["ready_for_poc"] = not report["readiness_errors"]
    report["session"] = session
    report["dirty_after"] = _dirty_packages(unreal)
    if report["dirty_before"] or report["dirty_after"]:
        report["ready_for_poc"] = False
        report.setdefault("readiness_errors", []).append("dirty packages 未通过；不清除 dirty flag")
    output = evidence / "texture_residency_readiness.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("JERSEY_UV_TEXTURE_RESIDENCY " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
