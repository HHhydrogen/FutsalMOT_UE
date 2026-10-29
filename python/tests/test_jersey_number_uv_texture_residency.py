"""以真实日志格式验证限时驻留门禁；不执行 UE 或 GPU。"""

from datetime import datetime, timedelta, timezone

import pytest

from jersey_number_uv_build_preview import TEXTURE_PATH
from jersey_number_uv_texture_residency import evaluate_residency, parse_probe_log, release_required


def _log(width=2048, height=1024, seconds=268.0, marker="test-unique"):
    return "\n".join([
        "LogPython: JERSEY_UV_TEXTURE_PROBE_BEGIN " + marker,
        "LogContentStreaming: Texture: Texture2D " + TEXTURE_PATH + ".T_NumberAtlas_UV_v1",
        "LogContentStreaming:   Format:          DXT5",
        "LogContentStreaming:   Force all mips:  {} seconds left".format(seconds),
        "LogContentStreaming:   Current size [2D Mips]: {}x{} [12]".format(width, height),
        "LogContentStreaming:   Wanted size [2D Mips]:  2048x1024 [12]",
        "LogPython: JERSEY_UV_TEXTURE_PROBE_END " + marker,
    ])


def _session(now):
    return {"state": "requested", "editor_pid": 123, "texture_path": TEXTURE_PATH,
            "request_id": "owned", "expires_at_utc": (now + timedelta(seconds=280)).isoformat()}


def test_current_marker_and_full_resolution_allow_only_owned_unexpired_request():
    now = datetime.now(timezone.utc)
    probe = parse_probe_log(_log(), "test-unique")
    assert probe["current_dimensions"] == [2048, 1024]
    assert probe["force_seconds_remaining"] == 268
    assert evaluate_residency(_session(now), probe, editor_pid=123, now=now) == []


@pytest.mark.parametrize("text,marker", [
    (_log(), "different-probe"),
    (_log().replace("JERSEY_UV_TEXTURE_PROBE_END", "incomplete"), "test-unique"),
    (_log().replace(TEXTURE_PATH, "/Game/AnotherAtlas"), "test-unique"),
    (_log().replace("Current size [2D Mips]", "Unknown size"), "test-unique"),
])
def test_stale_partial_or_wrong_texture_log_cannot_be_readiness_evidence(text, marker):
    with pytest.raises(ValueError):
        parse_probe_log(text, marker)


def test_low_mip_zero_force_or_near_expiry_does_not_become_ready():
    now = datetime.now(timezone.utc)
    for text in (_log(64, 32), _log(seconds=0), _log(seconds=5)):
        assert evaluate_residency(_session(now), parse_probe_log(text, "test-unique"), editor_pid=123, now=now)
    expired = _session(now)
    expired["expires_at_utc"] = (now - timedelta(seconds=1)).isoformat()
    assert evaluate_residency(expired, parse_probe_log(_log(), "test-unique"), editor_pid=123, now=now)


@pytest.mark.parametrize("field,value", [("editor_pid", 99), ("state", "released"),
                                        ("texture_path", "/Game/ProductionTexture"),
                                        ("expires_at_utc", "invalid")])
def test_restart_released_or_foreign_request_fails_closed(field, value):
    now = datetime.now(timezone.utc)
    session = _session(now)
    session[field] = value
    assert evaluate_residency(session, parse_probe_log(_log(), "test-unique"), editor_pid=123, now=now)


def test_release_never_clears_a_request_after_its_ownership_deadline_or_editor_restart():
    now = datetime.now(timezone.utc)
    session = _session(now)
    assert release_required(session, editor_pid=123, now=now)
    session["expires_at_utc"] = (now - timedelta(seconds=1)).isoformat()
    assert release_required(session, editor_pid=123, now=now) is False
    with pytest.raises(ValueError):
        release_required(session, editor_pid=456, now=now)
