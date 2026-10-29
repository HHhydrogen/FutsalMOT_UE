"""MRQ completion callback 的生命周期测试。"""

import json
import sys
from types import SimpleNamespace

import pytest

from diagnose_jersey_number_mask import build_render_contract_report
from ue import render_episode


def _valid_v2_render_evidence(material_path="/Game/FutsalMOT/Materials/M_NumberMask"):
    return {
        "appearance_preflight": {
            "task7_preflight_can_start": True,
            "numbering_visual_gate": "verified",
        },
        "diagnostic": build_render_contract_report(
            current_level_path="/Game/FutsalMOT/Maps/L_FutsalCourt",
            decal_component_capabilities={
                "available": True,
                "back_placement": True,
                "material_parameter": True,
            },
            proxy_custom_depth_capabilities={
                "api_inventory": {
                    "component_class_available": True,
                    "custom_depth_property_api_available": True,
                    "stencil_property_api_available": True,
                },
                "frame_readback": {
                    "probe_executed": True,
                    "evidence_source": "temporary_scene_capture_pixel_readback",
                    "custom_depth_enabled": True,
                    "stencil_value": 37,
                    "readback_stencil_value": 37,
                    "stencil_pixel_count": 64,
                },
            },
            mrq_mask_output_capabilities={
                "api_inventory": {
                    "mask_pass_class_available": True,
                    "image_output_class_available": True,
                },
                "synchronized_frame_evidence": {
                    "probe_executed": True,
                    "evidence_source": "temporary_mrq_output_files",
                    "same_job": True,
                    "rgb_frame_ids": ["000000"],
                    "mask_frame_ids": ["000000"],
                },
            },
            occlusion_probe={
                "front_mask_empty": True,
                "back_mask_has_pixels": True,
                "occluded_pixels_hidden": True,
                "probe_executed": True,
                "evidence_source": "temporary_scene_capture_pixel_readback",
                "pixel_counts": {"front": 0, "back": 100, "occluded": 0},
            },
            probe_lifecycle={
                operation: {
                    "status": "verified",
                    "evidence_source": "executed_probe",
                    "detail": "verified and cleaned",
                }
                for operation in (
                    "isolated_world_creation",
                    "temporary_actor_cleanup",
                    "stencil_mask_generation",
                    "mrq_executor_terminal_callback",
                    "mrq_output_cleanup",
                )
            },
        ),
        "number_mask_material": {
            "path": material_path,
            "exists": True,
            "actual_class": "Material",
            "evidence_source": "ue_asset_data",
        },
    }


def _pipeline(tmp_path, callback, jobs=None):
    return render_episode._AsyncRenderPipeline(
        jobs or [], "episode_callback", tmp_path, [0, 3], on_complete=callback
    )


@pytest.mark.parametrize(
    ("status", "camera_status"),
    [
        ("success", "success"),
        ("failed", "failed"),
        ("cancelled", "cancelled"),
    ],
)
def test_terminal_finalize_calls_callback_once_after_summary(
    tmp_path, status, camera_status
):
    calls = []
    pipeline = _pipeline(
        tmp_path,
        lambda result: calls.append(
            (result, json.loads(pipeline.summary_path().read_text(encoding="utf-8")))
        ),
        [{"name": "Seq_CamA", "cam_id": "CamA", "kind": "rgb"}],
    )

    pipeline._finalize(
        failed=status == "failed",
        status=status,
        per_camera={
            "CamA": {
                "ok": camera_status == "success",
                "expected_frames": 2,
                "img1_frames": 2,
            }
        },
        reason="terminal test",
    )
    pipeline._finalize(failed=True, status="failed", reason="duplicate signal")

    assert len(calls) == 1
    result, summary = calls[0]
    assert summary["status"] == status
    assert result["status"] == status
    assert result["cameras"]["CamA"]["img1_frames"] == 2
    assert result["jobs"] == [
        {"camera_id": "CamA", "job_name": "Seq_CamA", "status": camera_status}
    ]
    json.dumps(result, allow_nan=False)


def test_terminal_job_statuses_use_each_jobs_camera_output_counts(tmp_path):
    calls = []
    jobs = [
        {"name": "Seq_CamA", "cam_id": "CamA", "kind": "rgb"},
        {"name": "Seq_CamA_MASK", "cam_id": "CamA", "kind": "mask"},
    ]
    pipeline = _pipeline(tmp_path, calls.append, jobs)

    pipeline._finalize(
        failed=False,
        status="partial",
        per_camera={
            "CamA": {
                "ok": False,
                "expected_frames": 3,
                "img1_frames": 3,
                "mask_frames": 2,
            }
        },
    )

    assert calls[0]["jobs"] == [
        {"camera_id": "CamA", "job_name": "Seq_CamA", "status": "success"},
        {"camera_id": "CamA", "job_name": "Seq_CamA_MASK", "status": "failed"},
    ]


def test_finished_executor_success_uses_terminal_callback(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    monkeypatch.setattr(
        pipeline,
        "_copy_and_finalize",
        lambda: pipeline._finalize(
            failed=False,
            status="success",
            per_camera={
                "CamA": {"ok": True, "expected_frames": 2, "img1_frames": 2}
            },
        ),
    )

    pipeline._on_finished(SimpleNamespace(), True)

    assert len(calls) == 1
    assert calls[0]["status"] == "success"


def test_finished_executor_error_uses_terminal_callback(tmp_path):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)

    pipeline._on_finished(SimpleNamespace(), False)

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"


def test_fatal_executor_error_finalizes_callback_once(tmp_path):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)

    pipeline._on_errored(SimpleNamespace(), object(), True, ["fatal"])
    pipeline._on_finished(SimpleNamespace(), False)

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["mrq_errors"] == ["fatal"]


def test_fatal_error_waits_for_executor_terminal_signal(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    pipeline.executor = SimpleNamespace()
    monkeypatch.setattr(pipeline, "_executor_rendering", lambda: False)
    monkeypatch.setattr(pipeline, "_all_keep_frames_present", lambda: False)
    monkeypatch.setattr(pipeline, "_total_render_files", lambda: 0)
    ticks = []
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 12,
            unregister_slate_post_tick_callback=lambda _handle: None,
        ),
    )

    pipeline._on_errored(SimpleNamespace(), object(), True, ["fatal"])

    assert calls == []
    assert pipeline.finished is False
    pipeline._start_completion_watchdog()
    assert ticks[0](0.016) is False
    assert calls[0]["status"] == "failed"


def test_finished_cancelled_executor_reports_cancelled(tmp_path):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    executor = SimpleNamespace(is_cancelled=lambda: True)

    pipeline._on_finished(executor, False)

    assert len(calls) == 1
    assert calls[0]["status"] == "cancelled"


def test_watchdog_completion_calls_callback_once(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    pipeline.executor = SimpleNamespace()
    monkeypatch.setattr(pipeline, "_executor_rendering", lambda: False)
    monkeypatch.setattr(pipeline, "_all_keep_frames_present", lambda: True)
    monkeypatch.setattr(pipeline, "_total_render_files", lambda: 2)
    monkeypatch.setattr(
        pipeline,
        "_copy_and_finalize",
        lambda: pipeline._finalize(
            failed=False,
            status="success",
            per_camera={"CamA": {"ok": True}},
        ),
    )
    ticks = []
    fake_unreal = SimpleNamespace(
        register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 7,
        unregister_slate_post_tick_callback=lambda _handle: None,
    )
    monkeypatch.setitem(sys.modules, "unreal", fake_unreal)

    pipeline._start_completion_watchdog()
    assert ticks[0](0.016) is False
    pipeline._finalize(failed=True, status="failed")

    assert len(calls) == 1
    assert calls[0]["status"] == "success"


def test_watchdog_cancellation_calls_callback_with_cancelled_terminal_status(
    tmp_path, monkeypatch
):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    pipeline.executor = SimpleNamespace(is_cancelled=lambda: True)
    monkeypatch.setattr(pipeline, "_executor_rendering", lambda: False)
    monkeypatch.setattr(pipeline, "_all_keep_frames_present", lambda: False)
    monkeypatch.setattr(pipeline, "_total_render_files", lambda: 0)
    ticks = []
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 8,
            unregister_slate_post_tick_callback=lambda _handle: None,
        ),
    )

    pipeline._start_completion_watchdog()

    assert ticks[0](0.016) is False
    assert len(calls) == 1
    assert calls[0]["status"] == "cancelled"


def test_watchdog_cancellation_finalizes_when_rendering_state_is_unavailable(
    tmp_path, monkeypatch
):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    pipeline.executor = SimpleNamespace(is_cancelled=lambda: True)
    monkeypatch.setattr(pipeline, "_executor_rendering", lambda: None)
    monkeypatch.setattr(pipeline, "_all_keep_frames_present", lambda: False)
    monkeypatch.setattr(pipeline, "_total_render_files", lambda: 0)
    ticks = []
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 10,
            unregister_slate_post_tick_callback=lambda _handle: None,
        ),
    )

    pipeline._start_completion_watchdog()

    assert ticks[0](0.016) is False
    assert calls[0]["status"] == "cancelled"


def test_watchdog_reports_cancelled_before_output_inspection(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    pipeline.executor = SimpleNamespace(is_cancelled=lambda: True)
    monkeypatch.setattr(
        pipeline,
        "_executor_rendering",
        lambda: (_ for _ in ()).throw(RuntimeError("executor state unavailable")),
    )
    monkeypatch.setattr(
        pipeline,
        "_all_keep_frames_present",
        lambda: (_ for _ in ()).throw(RuntimeError("output scan unavailable")),
    )
    ticks = []
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 13,
            unregister_slate_post_tick_callback=lambda _handle: None,
        ),
    )

    pipeline._start_completion_watchdog()

    assert ticks[0](0.016) is False
    assert calls[0]["status"] == "cancelled"


def test_watchdog_inspection_exception_finalizes_as_failed(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    pipeline.executor = SimpleNamespace()
    monkeypatch.setattr(pipeline, "_executor_rendering", lambda: False)
    monkeypatch.setattr(
        pipeline,
        "_all_keep_frames_present",
        lambda: (_ for _ in ()).throw(ValueError("ambiguous output")),
    )
    ticks = []
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 11,
            unregister_slate_post_tick_callback=lambda _handle: None,
        ),
    )

    pipeline._start_completion_watchdog()

    assert ticks[0](0.016) is False
    assert len(calls) == 1
    assert calls[0]["status"] == "failed"


def test_watchdog_finalizes_executor_error_after_executor_stops(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    pipeline.executor = SimpleNamespace()
    pipeline._on_errored(SimpleNamespace(), object(), False, ["executor failed"])
    monkeypatch.setattr(pipeline, "_executor_rendering", lambda: False)
    monkeypatch.setattr(pipeline, "_all_keep_frames_present", lambda: False)
    monkeypatch.setattr(pipeline, "_total_render_files", lambda: 0)
    ticks = []
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 9,
            unregister_slate_post_tick_callback=lambda _handle: None,
        ),
    )

    pipeline._start_completion_watchdog()

    assert ticks[0](0.016) is False
    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["mrq_errors"] == ["executor failed"]


def test_submission_failure_finalizes_before_return(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(
        tmp_path,
        lambda result: calls.append(
            (result, pipeline.summary_path().is_file())
        ),
        [{
            "name": "Seq_CamA",
            "cam_id": "CamA",
            "kind": "rgb",
            "seq_asset_path": "/Game/Sequences/Seq_CamA",
            "render_dir": tmp_path / "render",
            "img1_dir": tmp_path / "img1",
        }],
    )
    monkeypatch.setattr(render_episode, "_clear_queue", lambda _queue: None)
    monkeypatch.setattr(render_episode, "_build_mrq_job", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(render_episode, "_submit_render", lambda *_args: False)

    transferred = pipeline.start(
        object(), object(), SimpleNamespace(), "/Game/Map", 64, 64, 30, "{frame_number}", 6
    )

    assert transferred is False
    assert len(calls) == 1
    assert calls[0][1] is True
    assert calls[0][0]["status"] == "failed"
    assert calls[0][0]["jobs"] == [
        {"camera_id": "CamA", "job_name": "Seq_CamA", "status": "failed"}
    ]
    assert calls[0][0]["cameras"] == {}


@pytest.mark.parametrize("watchdog_registration", ["missing", "raises"])
def test_start_does_not_submit_without_any_completion_source(
    tmp_path, monkeypatch, watchdog_registration
):
    calls = []
    delegate = SimpleNamespace(add_callable=lambda _callback: None)
    executor = SimpleNamespace(on_executor_finished_delegate=delegate)
    unreal_module = SimpleNamespace()
    if watchdog_registration == "raises":
        unreal_module.register_slate_post_tick_callback = lambda _callback: (
            _ for _ in ()
        ).throw(RuntimeError("watchdog unavailable"))
    monkeypatch.setitem(sys.modules, "unreal", unreal_module)
    pipeline = _pipeline(
        tmp_path,
        calls.append,
        [{
            "name": "Seq_CamA",
            "cam_id": "CamA",
            "kind": "rgb",
            "seq_asset_path": "/Game/Sequences/Seq_CamA",
            "render_dir": tmp_path / "render",
            "img1_dir": tmp_path / "img1",
        }],
    )
    submitted = []
    monkeypatch.setattr(render_episode, "_clear_queue", lambda _queue: None)
    monkeypatch.setattr(render_episode, "_build_mrq_job", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        render_episode, "_submit_render", lambda *_args: submitted.append(True) or True
    )
    delegate.add_callable = lambda _callback: (_ for _ in ()).throw(
        RuntimeError("finished delegate unavailable")
    )

    transferred = pipeline.start(
        object(), object(), executor, "/Game/Map", 64, 64, 30, "{frame_number}", 6
    )

    assert transferred is False
    assert submitted == []
    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert "completion" in calls[0]["reason"].lower()


def test_start_returns_no_ownership_when_submit_finishes_synchronously(
    tmp_path, monkeypatch
):
    calls = []
    ticks = []

    class Delegate:
        def add_callable(self, callback):
            self.callback = callback

    delegate = Delegate()
    executor = SimpleNamespace(on_executor_finished_delegate=delegate)
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            register_slate_post_tick_callback=lambda callback: ticks.append(callback) or 3,
            unregister_slate_post_tick_callback=lambda _handle: None,
        ),
    )
    pipeline = _pipeline(
        tmp_path,
        calls.append,
        [{
            "name": "Seq_CamA",
            "cam_id": "CamA",
            "kind": "rgb",
            "seq_asset_path": "/Game/Sequences/Seq_CamA",
            "render_dir": tmp_path / "render",
            "img1_dir": tmp_path / "img1",
        }],
    )
    monkeypatch.setattr(render_episode, "_clear_queue", lambda _queue: None)
    monkeypatch.setattr(render_episode, "_build_mrq_job", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        pipeline,
        "_copy_and_finalize",
        lambda: pipeline._finalize(failed=False, status="success"),
    )

    def submit(_subsystem, _executor):
        delegate.callback(executor, True)
        return True

    monkeypatch.setattr(render_episode, "_submit_render", submit)

    transferred = pipeline.start(
        object(), object(), executor, "/Game/Map", 64, 64, 30, "{frame_number}", 6
    )

    assert transferred is False
    assert ticks == []
    assert len(calls) == 1
    assert calls[0]["status"] == "success"


def test_summary_write_failure_still_calls_callback_once_with_failed_result(
    tmp_path, monkeypatch, capsys
):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    monkeypatch.setattr(
        render_episode,
        "write_json_atomic",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )

    pipeline._finalize(failed=False, status="success")
    pipeline._finalize(failed=True, status="failed", reason="duplicate")

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert "disk full" in calls[0]["reason"]
    assert calls[0]["summary_write_error"] == "OSError: disk full"
    assert "disk full" in capsys.readouterr().out


def test_v2_summary_write_failure_forces_appearance_restore_not_ready(
    tmp_path, monkeypatch
):
    calls = []
    number_job = {
        "name": "Seq_CamA_NUMBER_MASK",
        "cam_id": "CamA",
        "kind": "jersey_number_mask",
        "target_indices": [0, 3],
        "number_mask_source": "custom_depth_stencil_png",
    }
    pipeline = render_episode._AsyncRenderPipeline(
        [number_job],
        "episode_v2",
        tmp_path,
        [0, 3],
        on_complete=calls.append,
        require_number_mask_jobs=True,
    )
    monkeypatch.setattr(
        render_episode,
        "write_json_atomic",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )

    pipeline._finalize(
        failed=False,
        status="success",
        per_camera={
            "CamA": {
                "ok": True,
                "expected_frames": 2,
                "number_mask_frames": 2,
            }
        },
    )

    assert calls[0]["status"] == "failed"
    assert calls[0]["appearance_restore_ready"] is False


def test_summary_write_failure_removes_stale_summary_and_marks_terminal_invalid(
    tmp_path, monkeypatch
):
    calls = []
    pipeline = render_episode._AsyncRenderPipeline(
        [],
        "episode_v2",
        tmp_path,
        [0, 3],
        on_complete=calls.append,
        require_number_mask_jobs=True,
    )
    summary_path = pipeline.summary_path()
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(
        json.dumps({"status": "success", "appearance_restore_ready": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        render_episode,
        "write_json_atomic",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )

    pipeline._finalize(failed=False, status="success")

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["appearance_restore_ready"] is False
    assert calls[0]["summary_invalidated"] is True
    assert not summary_path.exists()


def test_setup_exception_finalizes_callback_before_reraising(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(tmp_path, calls.append)
    monkeypatch.setattr(
        render_episode,
        "_clear_queue",
        lambda _queue: (_ for _ in ()).throw(RuntimeError("queue setup failed")),
    )

    with pytest.raises(RuntimeError, match="queue setup failed"):
        pipeline.start(
            object(), object(), SimpleNamespace(), "/Game/Map", 64, 64, 30,
            "{frame_number}", 6,
        )

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert (pipeline.summary_path()).is_file()


def test_setup_exception_reports_failed_camera_details_for_known_jobs(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(
        tmp_path,
        calls.append,
        [
            {"name": "Seq_CamA", "cam_id": "CamA", "kind": "rgb"},
            {"name": "Seq_CamB", "cam_id": "CamB", "kind": "rgb"},
        ],
    )
    monkeypatch.setattr(
        render_episode,
        "_clear_queue",
        lambda _queue: (_ for _ in ()).throw(RuntimeError("queue setup failed")),
    )

    with pytest.raises(RuntimeError, match="queue setup failed"):
        pipeline.start(
            object(), object(), SimpleNamespace(), "/Game/Map", 64, 64, 30,
            "{frame_number}", 6,
        )

    assert calls[0]["cameras"] == {}


def test_v1_setup_failure_preserves_legacy_empty_camera_map(tmp_path, monkeypatch):
    calls = []
    pipeline = _pipeline(
        tmp_path,
        calls.append,
        [{"name": "Seq_CamA", "cam_id": "CamA", "kind": "rgb"}],
    )
    monkeypatch.setattr(
        render_episode,
        "_clear_queue",
        lambda _queue: (_ for _ in ()).throw(RuntimeError("legacy queue failure")),
    )

    with pytest.raises(RuntimeError, match="legacy queue failure"):
        pipeline.start(
            object(), object(), SimpleNamespace(), "/Game/Map", 64, 64, 30,
            "{frame_number}", 6,
        )

    assert calls[0]["status"] == "failed"
    assert calls[0]["cameras"] == {}


def test_public_setup_exception_calls_callback_before_reraising(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                does_asset_exist=lambda _path: True,
            )
        ),
    )
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode,
        "resolve_output_resolution",
        lambda _cfg: (_ for _ in ()).throw(ValueError("bad resolution")),
    )
    calls = []

    with pytest.raises(ValueError, match="bad resolution"):
        render_episode.render_sequences(
            [], {"render_rgb": {"enabled": True}}, "/Game/Sequences", tmp_path,
            tmp_path / "output", on_complete=calls.append,
        )

    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert (
        tmp_path / "output" / tmp_path.name / "render_summary.json"
    ).is_file()


def test_v2_active_render_rejection_marks_restore_not_ready(tmp_path, monkeypatch):
    active = _pipeline(tmp_path, lambda _result: None)
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", active)
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    callbacks = []

    result = render_episode.render_sequences(
        [],
        {"render_rgb": {"enabled": True}},
        "/Game/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
    )

    assert result["terminal_result"]["status"] == "failed"
    assert result["terminal_result"]["appearance_restore_ready"] is False
    assert callbacks == [result["terminal_result"]]


def test_v2_active_render_rejection_persists_all_number_mask_plans(
    tmp_path, monkeypatch
):
    active = _pipeline(tmp_path, lambda _result: None)
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", active)
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {
                "episode_id": "episode_v2",
                "timing": {"source_step_seconds": 0.1},
            },
            [{"step": 0}, {"step": 1}],
        ),
    )
    monkeypatch.setattr(render_episode, "resolve_output_resolution", lambda _cfg: (640, 360))
    callbacks = []

    result = render_episode.render_sequences(
        [
            {"name": "LS_Cam_01", "camera_actor": "CineCam_01"},
            {"name": "LS_Cam_02", "camera_actor": "CineCam_02"},
        ],
        {"render_rgb": {"enabled": True, "frame_rate": 30}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
    )

    terminal = result["terminal_result"]
    number_jobs = [job for job in terminal["jobs"] if job["kind"] == "jersey_number_mask"]
    assert [job["camera_id"] for job in number_jobs] == [
        "CineCam_01", "CineCam_02"
    ]
    assert all(job["status"] == "failed" for job in number_jobs)
    assert all(job["schedule_error"] == "已有 MRQ 渲染正在进行，拒绝并发提交" for job in number_jobs)
    assert terminal["appearance_restore_ready"] is False
    summary = json.loads(
        (tmp_path / "output" / "episode_v2" / "render_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert [
        job["camera_id"] for job in summary["jobs"]
        if job["kind"] == "jersey_number_mask"
    ] == ["CineCam_01", "CineCam_02"]
    assert all(
        job["status"] == "failed"
        for job in summary["jobs"]
        if job["kind"] == "jersey_number_mask"
    )
    assert callbacks == [terminal]


def test_v2_outer_render_exception_marks_restore_not_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {"episode_id": "episode_v2", "timing": {"source_step_seconds": 0.1}},
            [{"step": 0}],
        ),
    )
    monkeypatch.setattr(
        render_episode,
        "resolve_output_resolution",
        lambda _cfg: (_ for _ in ()).throw(ValueError("bad v2 resolution")),
    )
    callbacks = []

    with pytest.raises(ValueError, match="bad v2 resolution"):
        render_episode.render_sequences(
            [],
            {"render_rgb": {"enabled": True}},
            "/Game/Sequences",
            tmp_path,
            tmp_path / "output",
            on_complete=callbacks.append,
            appearance_active=True,
            appearance_policy="futsalmot_appearance_v2",
        )

    assert len(callbacks) == 1
    assert callbacks[0]["status"] == "failed"
    assert callbacks[0]["appearance_restore_ready"] is False


def test_v2_outer_setup_exception_persists_all_created_number_mask_plans(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {
                "episode_id": "episode_v2",
                "timing": {"source_step_seconds": 0.1},
            },
            [{"step": 0}, {"step": 1}],
        ),
    )
    monkeypatch.setattr(render_episode, "resolve_output_resolution", lambda _cfg: (640, 360))
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode,
        "_apply_cv_gt_camera_post_process",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("camera setup failed")),
    )
    callbacks = []

    with pytest.raises(RuntimeError, match="camera setup failed"):
        render_episode.render_sequences(
            [
                {"name": "LS_Cam_01", "camera_actor": "CineCam_01"},
                {"name": "LS_Cam_02", "camera_actor": "CineCam_02"},
            ],
            {"render_rgb": {"enabled": True, "frame_rate": 30}},
            "/Game/FutsalMOT/Sequences",
            tmp_path,
            tmp_path / "output",
            on_complete=callbacks.append,
            appearance_active=True,
            appearance_policy="futsalmot_appearance_v2",
            appearance_visibility_gate_verified=True,
            number_mask_post_process_material="/Game/FutsalMOT/Materials/M_NumberMask",
            appearance_render_evidence=_valid_v2_render_evidence(),
        )

    terminal = callbacks[0]
    number_jobs = [job for job in terminal["jobs"] if job["kind"] == "jersey_number_mask"]
    assert [job["camera_id"] for job in number_jobs] == [
        "CineCam_01", "CineCam_02"
    ]
    assert all(job["status"] == "failed" for job in number_jobs)
    assert all(job["schedule_error"].startswith("render setup failed:") for job in number_jobs)
    assert terminal["appearance_restore_ready"] is False
    summary = json.loads(
        (tmp_path / "output" / "episode_v2" / "render_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert [
        job["camera_id"] for job in summary["jobs"]
        if job["kind"] == "jersey_number_mask"
    ] == ["CineCam_01", "CineCam_02"]
    assert all(
        job["status"] == "failed"
        for job in summary["jobs"]
        if job["kind"] == "jersey_number_mask"
    )


def test_v2_planning_exception_persists_all_intended_number_mask_failures(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(
        render_episode,
        "_plan_v2_number_mask_jobs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("bad v2 planning input")
        ),
    )
    callbacks = []

    with pytest.raises(ValueError, match="bad v2 planning input"):
        render_episode.render_sequences(
            [
                {"name": "LS_Cam_01", "camera_actor": "CineCam_01"},
                {"name": "LS_Cam_02", "camera_actor": "CineCam_02"},
            ],
            {"render_rgb": {"enabled": True, "frame_rate": 30}},
            "/Game/FutsalMOT/Sequences",
            tmp_path,
            tmp_path / "output",
            on_complete=callbacks.append,
            appearance_active=True,
            appearance_policy="futsalmot_appearance_v2",
        )

    assert len(callbacks) == 1
    terminal = callbacks[0]
    number_jobs = [
        job for job in terminal["jobs"] if job["kind"] == "jersey_number_mask"
    ]
    assert [job["camera_id"] for job in number_jobs] == [
        "CineCam_01", "CineCam_02"
    ]
    assert all(job["status"] == "failed" for job in number_jobs)
    assert all(
        job["schedule_error"].startswith("render setup failed: ValueError:")
        for job in number_jobs
    )
    assert terminal["appearance_restore_ready"] is False
    assert set(terminal["cameras"]) == {"CineCam_01", "CineCam_02"}
    assert all(
        camera["ok"] is False for camera in terminal["cameras"].values()
    )
    summary = json.loads(
        (tmp_path / "output" / tmp_path.name / "render_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert [
        job["camera_id"] for job in summary["jobs"]
        if job["kind"] == "jersey_number_mask"
    ] == ["CineCam_01", "CineCam_02"]
    assert summary["appearance_restore_ready"] is False
    assert set(summary["cameras"]) == {"CineCam_01", "CineCam_02"}


def test_callback_exception_does_not_break_render_finalization(tmp_path, capsys):
    def broken_callback(_result):
        raise RuntimeError("appearance restore failed")

    pipeline = _pipeline(tmp_path, broken_callback)

    pipeline._finalize(failed=False, status="success")

    assert pipeline.finished is True
    assert pipeline.summary_path().is_file()
    assert "appearance restore failed" in capsys.readouterr().out


def test_disabled_render_calls_callback_synchronously_and_preserves_old_callers(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    calls = []

    result = render_episode.render_sequences(
        [], {"render_rgb": {"enabled": False}}, "/Game/Sequences", tmp_path,
        tmp_path / "output", on_complete=calls.append,
    )
    old_result = render_episode.render_sequences(
        [], {"render_rgb": {"enabled": False}}, "/Game/Sequences", tmp_path,
        tmp_path / "output",
    )

    assert result["callback_ownership_transferred"] is False
    assert result["terminal_result"]["status"] == "skipped"
    assert calls == [result["terminal_result"]]
    assert old_result is None
    summary = json.loads(
        (tmp_path / "output" / tmp_path.name / "render_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "skipped"


def test_empty_sequence_list_calls_callback_synchronously(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: ({"episode_id": "episode_callback", "timing": {"source_step_seconds": 0.1}}, []),
    )
    monkeypatch.setattr(render_episode, "resolve_output_resolution", lambda _cfg: (64, 64))
    monkeypatch.setattr(render_episode, "_apply_cv_gt_camera_post_process", lambda *_args: None)
    calls = []

    result = render_episode.render_sequences(
        [], {"render_rgb": {"enabled": True}}, "/Game/Sequences", tmp_path,
        tmp_path / "output", on_complete=calls.append,
    )

    assert result["callback_ownership_transferred"] is False
    assert calls == [result["terminal_result"]]
    assert result["terminal_result"]["status"] == "skipped"


def test_appearance_first_frame_actor_bake_is_temporary_and_never_saves(monkeypatch):
    calls = []
    monkeypatch.setattr(render_episode, "load_mapping", lambda _path: {"L0": "Player_L0"})
    monkeypatch.setattr(render_episode, "find_all_actors", lambda _mapping: {"L0": object()})
    monkeypatch.setattr(render_episode, "gk_entity_ids_from_meta", lambda _meta: set())
    monkeypatch.setattr(
        render_episode,
        "apply_preview_frame",
        lambda *_args, **_kwargs: calls.append("bake"),
    )
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: calls.append("save"))

    baked = render_episode._bake_first_frame_for_render(
        {"timing": {}}, [{"step": 0}], "mapping.json", appearance_active=True
    )

    assert baked is True
    assert calls == ["bake"]


def test_appearance_first_frame_bake_excludes_ball_from_transaction_mutation(monkeypatch):
    player = object()
    ball = object()
    captured = {}
    monkeypatch.setattr(
        render_episode,
        "load_mapping",
        lambda _path: {"L0": "Player_L0", "BALL": "Ball_01"},
    )
    monkeypatch.setattr(
        render_episode,
        "find_all_actors",
        lambda _mapping: {"L0": player, "BALL": ball},
    )
    monkeypatch.setattr(render_episode, "gk_entity_ids_from_meta", lambda _meta: set())
    monkeypatch.setattr(
        render_episode,
        "apply_preview_frame",
        lambda actors, *_args, **_kwargs: captured.update(actors),
    )
    monkeypatch.setattr(
        render_episode, "_save_current_level", lambda: pytest.fail("must not save")
    )

    baked = render_episode._bake_first_frame_for_render(
        {"timing": {}}, [{"step": 0}], "mapping.json", appearance_active=True
    )

    assert baked is True
    assert captured == {"L0": player}


def test_appearance_first_frame_bake_without_players_returns_false(monkeypatch):
    monkeypatch.setattr(
        render_episode,
        "load_mapping",
        lambda _path: {"BALL": "Ball_01"},
    )
    monkeypatch.setattr(
        render_episode, "find_all_actors", lambda _mapping: {"BALL": object()}
    )
    monkeypatch.setattr(
        render_episode,
        "apply_preview_frame",
        lambda *_args, **_kwargs: pytest.fail("no actor should be baked"),
    )

    assert render_episode._bake_first_frame_for_render(
        {"timing": {}}, [{"step": 0}], "mapping.json", appearance_active=True
    ) is False


def test_appearance_first_frame_bake_does_not_swallow_actor_mutation_error(monkeypatch):
    monkeypatch.setattr(render_episode, "load_mapping", lambda _path: {"L0": "Player_L0"})
    monkeypatch.setattr(render_episode, "find_all_actors", lambda _mapping: {"L0": object()})
    monkeypatch.setattr(render_episode, "gk_entity_ids_from_meta", lambda _meta: set())
    monkeypatch.setattr(
        render_episode,
        "apply_preview_frame",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("actor mutation failed")),
    )
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: pytest.fail("must not save"))

    with pytest.raises(RuntimeError, match="actor mutation failed"):
        render_episode._bake_first_frame_for_render(
            {"timing": {}}, [{"step": 0}], "mapping.json", appearance_active=True
        )


def test_appearance_without_mapping_needs_no_first_frame_bake():
    assert render_episode._bake_first_frame_for_render(
        {"timing": {}}, [{"step": 0}], None, appearance_active=True
    ) is False


def test_completion_callback_alone_preserves_legacy_camera_save(monkeypatch):
    calls = []
    monkeypatch.setattr(
        render_episode,
        "camera_post_process_overrides",
        lambda *_args: {"post_process_blend_weight": 1.0},
    )
    monkeypatch.setattr(render_episode, "find_actor", lambda _name: object())
    monkeypatch.setattr(
        render_episode,
        "_set_config_overrides",
        lambda *_args: None,
    )
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: calls.append("save"))
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            CineCameraComponent=object,
            PostProcessSettings=lambda: SimpleNamespace(set_editor_property=lambda *_args: None),
        ),
    )
    camera = SimpleNamespace(
        get_components_by_class=lambda _class: [
            SimpleNamespace(
                get_editor_property=lambda _name: None,
                set_editor_property=lambda *_args: None,
            )
        ]
    )
    monkeypatch.setattr(render_episode, "find_actor", lambda _name: camera)

    render_episode._apply_cv_gt_camera_post_process(
        [{"name": "Seq_CamA", "camera_actor": "CamA"}],
        object(),
        object(),
    )

    assert calls == ["save"]


def test_unsaved_camera_override_path_does_not_mutate_camera(monkeypatch):
    calls = []
    monkeypatch.setattr(
        render_episode,
        "camera_post_process_overrides",
        lambda *_args: {"post_process_blend_weight": 1.0},
    )
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            CineCameraComponent=object,
            PostProcessSettings=lambda: SimpleNamespace(
                set_editor_property=lambda *_args: calls.append("set")
            ),
        ),
    )
    monkeypatch.setattr(
        render_episode,
        "find_actor",
        lambda _name: SimpleNamespace(
            get_components_by_class=lambda _class: [
                SimpleNamespace(
                    get_editor_property=lambda _name: None,
                    set_editor_property=lambda *_args: calls.append("set"),
                )
            ]
        ),
    )
    monkeypatch.setattr(render_episode, "_set_config_overrides", lambda *_args: None)
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: calls.append("save"))

    render_episode._apply_cv_gt_camera_post_process(
        [{"name": "Seq_CamA", "camera_actor": "CamA"}],
        object(),
        object(),
        save_level=False,
    )

    assert calls == ["set", "set"]


def test_non_appearance_keeps_first_frame_bake_and_save(monkeypatch):
    calls = []
    monkeypatch.setattr(render_episode, "load_mapping", lambda _path: {"L0": "Player_L0"})
    monkeypatch.setattr(render_episode, "find_all_actors", lambda _mapping: {"L0": object()})
    monkeypatch.setattr(render_episode, "gk_entity_ids_from_meta", lambda _meta: set())
    monkeypatch.setattr(
        render_episode,
        "apply_preview_frame",
        lambda *_args, **_kwargs: calls.append("bake"),
    )
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: calls.append("save"))

    baked = render_episode._bake_first_frame_for_render(
        {"timing": {}}, [{"step": 0}], "mapping.json", appearance_active=False
    )

    assert baked is True
    assert calls == ["bake", "save"]


def test_appearance_rejects_save_dependent_stencil_path_before_actor_mutation(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(render_episode, "load_mapping", lambda _path: calls.append("load"))
    monkeypatch.setattr(render_episode, "find_all_actors", lambda _mapping: calls.append("find"))
    monkeypatch.setattr(render_episode, "_assign_custom_stencil", lambda _actors: calls.append("stencil"))
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: calls.append("save"))

    with pytest.raises(RuntimeError, match="appearance.*stencil.*保存"):
        render_episode._prepare_stencil_for_render("mapping.json", appearance_active=True)

    assert calls == []


def test_non_appearance_stencil_path_retains_assignment_and_save(tmp_path, monkeypatch):
    calls = []
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(render_episode, "_ensure_custom_depth_stencil_enabled", lambda: calls.append("enable"))
    monkeypatch.setattr(render_episode, "load_mapping", lambda _path: {"L0": "Player_L0"})
    monkeypatch.setattr(render_episode, "find_all_actors", lambda _mapping: {"L0": object()})
    monkeypatch.setattr(render_episode, "_assign_custom_stencil", lambda _actors: calls.append("stencil"))
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: calls.append("save"))

    render_episode._prepare_stencil_for_render(str(mapping_path), appearance_active=False)

    assert calls == ["enable", "stencil", "save"]


def test_v1_appearance_does_not_plan_jersey_number_jobs(tmp_path):
    plans = render_episode.plan_jersey_number_mask_jobs(
        [{"name": "LS_Cam_01", "camera_actor": "CineCam_01"}],
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        1920,
        1080,
        30,
        [0, 3, 6],
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v1",
    )

    assert plans == []


def test_v2_appearance_plans_one_number_mask_job_per_camera(tmp_path):
    plans = render_episode.plan_jersey_number_mask_jobs(
        [
            {"name": "LS_Cam_01", "camera_actor": "CineCam_01"},
            {"name": "LS_Cam_02", "camera_actor": "CineCam_02"},
        ],
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        1920,
        1080,
        30,
        [0, 3, 6],
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
    )

    assert len(plans) == 2
    assert [plan["kind"] for plan in plans] == [
        "jersey_number_mask",
        "jersey_number_mask",
    ]
    assert [plan["cam_id"] for plan in plans] == ["CineCam_01", "CineCam_02"]
    assert plans[0]["name"] == "LS_Cam_01_NUMBER_MASK"
    assert plans[0]["seq_asset_path"] == "/Game/FutsalMOT/Sequences/LS_Cam_01"
    assert plans[0]["render_dir"] == tmp_path / "CineCam_01" / "render_number_mask"
    assert plans[0]["number_mask_dir"] == tmp_path / "CineCam_01" / "number_mask"
    assert plans[0]["output_resolution"] == (1920, 1080)
    assert plans[0]["frame_rate"] == 30
    assert plans[0]["frame_range"] == "sequence_playback"
    assert plans[0]["target_indices"] == [0, 3, 6]


def test_number_mask_files_map_unordered_render_frames_to_rgb_annotation_indices(tmp_path):
    render_dir = tmp_path / "render_number_mask"
    render_dir.mkdir()
    (render_dir / "NumberMask000006.png").write_bytes(b"frame-6")
    (render_dir / "NumberMask000000.png").write_bytes(b"frame-0")
    (render_dir / "NumberMask000003.png").write_bytes(b"frame-3")

    rendered = render_episode.find_jersey_number_mask_files(render_dir)
    archived = render_episode.archive_jersey_number_mask_frames(
        render_dir, tmp_path / "number_mask", [0, 3, 6]
    )

    assert sorted(rendered) == [0, 3, 6]
    assert archived == 3
    assert (tmp_path / "number_mask" / "000001.png").read_bytes() == b"frame-0"
    assert (tmp_path / "number_mask" / "000002.png").read_bytes() == b"frame-3"
    assert (tmp_path / "number_mask" / "000003.png").read_bytes() == b"frame-6"


def test_number_mask_missing_target_keeps_pipeline_camera_and_job_unsuccessful(tmp_path):
    rgb_dir = tmp_path / "rgb"
    number_dir = tmp_path / "render_number_mask"
    rgb_dir.mkdir()
    number_dir.mkdir()
    (rgb_dir / "FinalImage000000.png").write_bytes(b"rgb-0")
    (rgb_dir / "FinalImage000003.png").write_bytes(b"rgb-3")
    (number_dir / "NumberMask000000.png").write_bytes(b"number-0")
    calls = []
    pipeline = _pipeline(
        tmp_path,
        calls.append,
        [
            {
                "name": "LS_Cam_01",
                "cam_id": "CineCam_01",
                "kind": "rgb",
                "render_dir": rgb_dir,
                "img1_dir": tmp_path / "img1",
                "cam_out": tmp_path,
            },
            {
                "name": "LS_Cam_01_NUMBER_MASK",
                "cam_id": "CineCam_01",
                "kind": "jersey_number_mask",
                "render_dir": number_dir,
                "number_mask_dir": tmp_path / "number_mask",
            },
        ],
    )

    assert pipeline._all_keep_frames_present() is False
    pipeline._copy_and_finalize()

    assert calls[0]["status"] != "success"
    assert calls[0]["cameras"]["CineCam_01"]["ok"] is False
    assert calls[0]["cameras"]["CineCam_01"]["number_mask_frames"] == 1
    number_job = calls[0]["jobs"][1]
    assert number_job["kind"] == "jersey_number_mask"
    assert number_job["status"] == "failed"
    assert number_job["number_mask_frames"] == 1
    assert calls[0]["appearance_restore_ready"] is False


def test_duplicate_number_mask_frame_paths_fail_closed_at_terminal_job_and_camera(
    tmp_path,
):
    rgb_dir = tmp_path / "rgb"
    number_dir = tmp_path / "render_number_mask"
    rgb_dir.mkdir()
    (number_dir / "pass_a").mkdir(parents=True)
    (number_dir / "pass_b").mkdir(parents=True)
    for frame in (0, 3):
        (rgb_dir / f"FinalImage{frame:06d}.png").write_bytes(b"rgb")
    (number_dir / "pass_a" / "NumberMask000000.png").write_bytes(b"a")
    (number_dir / "pass_b" / "NumberMask000000.png").write_bytes(b"b")
    (number_dir / "pass_a" / "NumberMask000003.png").write_bytes(b"number")
    calls = []
    pipeline = _pipeline(
        tmp_path,
        calls.append,
        [
            {
                "name": "LS_Cam_01",
                "cam_id": "CineCam_01",
                "kind": "rgb",
                "render_dir": rgb_dir,
                "img1_dir": tmp_path / "img1",
                "cam_out": tmp_path,
            },
            {
                "name": "LS_Cam_01_NUMBER_MASK",
                "cam_id": "CineCam_01",
                "kind": "jersey_number_mask",
                "render_dir": number_dir,
                "number_mask_dir": tmp_path / "number_mask",
                "target_indices": [0, 3],
            },
        ],
    )

    assert pipeline._all_keep_frames_present() is False
    pipeline._copy_and_finalize()

    terminal = calls[0]
    number_job = terminal["jobs"][1]
    assert terminal["status"] == "failed"
    assert terminal["cameras"]["CineCam_01"]["ok"] is False
    assert "duplicate" in terminal["cameras"]["CineCam_01"]["schedule_error"].lower()
    assert number_job["status"] == "failed"
    assert "duplicate" in number_job["schedule_error"].lower()
    assert terminal["appearance_restore_ready"] is False


def test_complete_number_mask_is_recorded_in_camera_and_job_result(tmp_path):
    rgb_dir = tmp_path / "rgb"
    number_dir = tmp_path / "render_number_mask"
    rgb_dir.mkdir()
    number_dir.mkdir()
    for frame in (0, 3):
        (rgb_dir / "FinalImage{:06d}.png".format(frame)).write_bytes(b"rgb")
        (number_dir / "NumberMask{:06d}.png".format(frame)).write_bytes(b"number")
    calls = []
    pipeline = _pipeline(
        tmp_path,
        calls.append,
        [
            {
                "name": "LS_Cam_01",
                "cam_id": "CineCam_01",
                "kind": "rgb",
                "render_dir": rgb_dir,
                "img1_dir": tmp_path / "img1",
                "cam_out": tmp_path,
            },
            {
                "name": "LS_Cam_01_NUMBER_MASK",
                "cam_id": "CineCam_01",
                "kind": "jersey_number_mask",
                "render_dir": number_dir,
                "number_mask_dir": tmp_path / "number_mask",
            },
        ],
    )

    assert pipeline._all_keep_frames_present() is True
    pipeline._copy_and_finalize()

    camera = calls[0]["cameras"]["CineCam_01"]
    number_job = calls[0]["jobs"][1]
    assert calls[0]["status"] == "success"
    assert camera["number_mask_frames"] == 2
    assert camera["number_mask_source"] == "custom_depth_stencil_png"
    assert number_job["status"] == "success"
    assert number_job["number_mask_frames"] == 2
    assert number_job["number_mask_source"] == "custom_depth_stencil_png"


def test_v2_default_visibility_gate_returns_plans_without_queue_access(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(
        render_episode, "resolve_output_resolution", lambda _cfg: (1920, 1080)
    )
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {
                "episode_id": "episode_v2",
                "timing": {"source_step_seconds": 0.1},
            },
            [{"step": 0}, {"step": 1}],
        ),
    )
    monkeypatch.setattr(
        render_episode,
        "_mrq_subsystem",
        lambda: pytest.fail("closed visibility gate must not access MRQ subsystem"),
    )
    callbacks = []

    result = render_episode.render_sequences(
        [{"name": "LS_Cam_01", "camera_actor": "CineCam_01"}],
        {"render_rgb": {"enabled": True, "frame_rate": 30}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
    )

    assert result["callback_ownership_transferred"] is False
    assert result["terminal_result"]["reason"].startswith("MANUAL_REQUIRED:")
    assert result["terminal_result"]["appearance_restore_ready"] is False
    assert result["number_mask_plans"][0]["render_dir"] == (
        tmp_path / "output" / "episode_v2" / "CineCam_01" / "render_number_mask"
    )
    assert callbacks == [result["terminal_result"]]


def test_v2_bool_and_material_path_only_call_is_rejected_before_mrq_submission(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                does_asset_exist=lambda _path: True,
            )
        ),
    )
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode,
        "_apply_cv_gt_camera_post_process",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {
                "episode_id": "episode_v2",
                "timing": {"source_step_seconds": 0.1},
            },
            [{"step": 0}],
        ),
    )
    monkeypatch.setattr(
        render_episode,
        "_mrq_subsystem",
        lambda: pytest.fail("v2 evidence gate must reject before MRQ access"),
    )
    callbacks = []

    result = render_episode.render_sequences(
        [{"name": "LS_Cam_01", "camera_actor": "CineCam_01"}],
        {
            "render_rgb": {
                "enabled": True,
                "output_resolution_x": 64,
                "output_resolution_y": 64,
            }
        },
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
        appearance_visibility_gate_verified=True,
        number_mask_post_process_material="/Game/FutsalMOT/Materials/M_NumberMask",
    )

    assert result["terminal_result"]["status"] == "failed"
    assert result["terminal_result"]["reason"].startswith("MANUAL_REQUIRED:")
    assert result["terminal_result"]["appearance_restore_ready"] is False
    assert callbacks == [result["terminal_result"]]


def test_verified_v2_gate_routes_each_camera_plan_through_mask_job_builder(
    tmp_path, monkeypatch
):
    class Delegate:
        def add_callable(self, callback):
            self.callback = callback

    queue = object()
    executor = SimpleNamespace(
        on_executor_finished_delegate=Delegate(),
        on_executor_errored_delegate=Delegate(),
    )
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                does_asset_exist=lambda _path: True,
            )
        ),
    )
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode, "resolve_output_resolution", lambda _cfg: (1920, 1080)
    )
    monkeypatch.setattr(render_episode, "_get_current_map_path", lambda: "/Game/Maps/Test")
    monkeypatch.setattr(render_episode, "_mrq_subsystem", lambda: object())
    monkeypatch.setattr(render_episode, "_mrq_get_queue", lambda _subsystem: queue)
    monkeypatch.setattr(render_episode, "_mrq_executor", lambda: executor)
    monkeypatch.setattr(render_episode, "_clear_queue", lambda _queue: None)
    monkeypatch.setattr(
        render_episode,
        "_apply_cv_gt_camera_post_process",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        render_episode,
        "_bake_first_frame_for_render",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {
                "episode_id": "episode_v2",
                "timing": {"source_step_seconds": 0.1},
            },
            [{"step": 0}, {"step": 1}],
        ),
    )
    builder_calls = []
    monkeypatch.setattr(
        render_episode,
        "_build_mrq_job",
        lambda *_args, **_kwargs: object(),
    )

    def build_mask_job(*args, **kwargs):
        builder_calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(render_episode, "_build_mask_job", build_mask_job)
    monkeypatch.setattr(render_episode, "_submit_render", lambda *_args: True)
    callbacks = []

    result = render_episode.render_sequences(
        [
            {"name": "LS_Cam_01", "camera_actor": "CineCam_01"},
            {"name": "LS_Cam_02", "camera_actor": "CineCam_02"},
        ],
        {"render_rgb": {"enabled": True, "frame_rate": 30}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
        appearance_visibility_gate_verified=True,
        number_mask_post_process_material="/Game/FutsalMOT/Materials/M_NumberMask",
        appearance_render_evidence=_valid_v2_render_evidence(),
    )

    assert result["callback_ownership_transferred"] is True
    pipeline = render_episode._ACTIVE_RENDER
    number_jobs = [job for job in pipeline.jobs if job["kind"] == "jersey_number_mask"]
    assert [job["cam_id"] for job in number_jobs] == ["CineCam_01", "CineCam_02"]
    assert [job["target_indices"] for job in number_jobs] == [[0, 3], [0, 3]]
    assert len(builder_calls) == 2
    for (args, kwargs), sequence_name, camera_id in zip(
        builder_calls,
        ("LS_Cam_01", "LS_Cam_02"),
        ("CineCam_01", "CineCam_02"),
    ):
        assert args[1] == "/Game/FutsalMOT/Sequences/" + sequence_name
        assert args[3] == (
            tmp_path / "output" / "episode_v2" / camera_id / "render_number_mask"
        )
        assert args[4:7] == (1920, 1080, 30)
        assert kwargs["mask_source"] == "post_process_material"
        assert kwargs["post_process_material"] == "/Game/FutsalMOT/Materials/M_NumberMask"


def test_v2_mask_plan_without_accepted_rgb_job_is_terminally_failed(
    tmp_path, monkeypatch
):
    class Delegate:
        def add_callable(self, callback):
            self.callback = callback

    queue = object()
    executor = SimpleNamespace(
        on_executor_finished_delegate=Delegate(),
        on_executor_errored_delegate=Delegate(),
    )
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                does_asset_exist=lambda path: "LS_Cam_02" not in path,
            )
        ),
    )
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode, "resolve_output_resolution", lambda _cfg: (640, 360)
    )
    monkeypatch.setattr(render_episode, "_get_current_map_path", lambda: "/Game/Maps/Test")
    monkeypatch.setattr(render_episode, "_mrq_subsystem", lambda: object())
    monkeypatch.setattr(render_episode, "_mrq_get_queue", lambda _subsystem: queue)
    monkeypatch.setattr(render_episode, "_mrq_executor", lambda: executor)
    monkeypatch.setattr(render_episode, "_clear_queue", lambda _queue: None)
    monkeypatch.setattr(
        render_episode,
        "_apply_cv_gt_camera_post_process",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        render_episode,
        "_bake_first_frame_for_render",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {
                "episode_id": "episode_v2",
                "timing": {"source_step_seconds": 0.1},
            },
            [{"step": 0}],
        ),
    )
    monkeypatch.setattr(render_episode, "_build_mrq_job", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(render_episode, "_build_mask_job", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(render_episode, "_submit_render", lambda *_args: True)
    callbacks = []

    result = render_episode.render_sequences(
        [
            {"name": "LS_Cam_01", "camera_actor": "CineCam_01"},
            {"name": "LS_Cam_02", "camera_actor": "CineCam_02"},
        ],
        {"render_rgb": {"enabled": True, "frame_rate": 30}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
        appearance_visibility_gate_verified=True,
        number_mask_post_process_material="/Game/FutsalMOT/Materials/M_NumberMask",
        appearance_render_evidence=_valid_v2_render_evidence(),
    )

    pipeline = render_episode._ACTIVE_RENDER
    assert [
        job["cam_id"] for job in pipeline.jobs
        if job.get("kind") == "jersey_number_mask"
    ] == ["CineCam_01"]
    assert [
        job["cam_id"] for job in pipeline.requested_jobs
        if job.get("kind") == "jersey_number_mask"
    ] == ["CineCam_01", "CineCam_02"]

    pipeline._copy_and_finalize()

    terminal = callbacks[0]
    number_jobs = [job for job in terminal["jobs"] if job.get("kind") == "jersey_number_mask"]
    assert [job["camera_id"] for job in number_jobs] == ["CineCam_01", "CineCam_02"]
    omitted_job = number_jobs[1]
    assert omitted_job["status"] == "failed"
    assert omitted_job["schedule_error"] == "camera has no accepted RGB job"
    assert terminal["cameras"]["CineCam_02"]["ok"] is False
    assert terminal["appearance_restore_ready"] is False
    summary = json.loads(
        pipeline.summary_path().read_text(encoding="utf-8")
    )
    assert summary["status"] != "success"
    assert summary["cameras"]["CineCam_02"]["ok"] is False
    assert summary["cameras"]["CineCam_02"]["schedule_error"] == (
        "camera has no accepted RGB job"
    )


def test_v2_all_rgb_sequences_filtered_fails_number_mask_jobs(
    tmp_path, monkeypatch
):
    class Delegate:
        def add_callable(self, callback):
            self.callback = callback

    queue = object()
    executor = SimpleNamespace(
        on_executor_finished_delegate=Delegate(),
        on_executor_errored_delegate=Delegate(),
    )
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                does_asset_exist=lambda _path: False,
            )
        ),
    )
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode, "resolve_output_resolution", lambda _cfg: (640, 360)
    )
    monkeypatch.setattr(render_episode, "_apply_cv_gt_camera_post_process", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {
                "episode_id": "episode_v2",
                "timing": {"source_step_seconds": 0.1},
            },
            [{"step": 0}, {"step": 1}],
        ),
    )
    monkeypatch.setattr(render_episode, "_mrq_subsystem", lambda: pytest.fail("不应访问 MRQ"))
    callbacks = []

    result = render_episode.render_sequences(
        [
            {"name": "LS_Cam_01", "camera_actor": "CineCam_01"},
            {"name": "LS_Cam_02", "camera_actor": "CineCam_02"},
        ],
        {"render_rgb": {"enabled": True, "frame_rate": 30}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
        appearance_visibility_gate_verified=True,
        number_mask_post_process_material="/Game/FutsalMOT/Materials/M_NumberMask",
        appearance_render_evidence=_valid_v2_render_evidence(),
    )

    terminal = result["terminal_result"]
    number_jobs = [
        job for job in terminal["jobs"] if job["kind"] == "jersey_number_mask"
    ]
    assert terminal["status"] == "failed"
    assert [job["camera_id"] for job in number_jobs] == [
        "CineCam_01", "CineCam_02"
    ]
    assert all(job["status"] == "failed" for job in number_jobs)
    assert all(
        job["schedule_error"] == "camera has no accepted RGB job"
        for job in number_jobs
    )
    assert all(job["target_indices"] == [0, 3] for job in number_jobs)
    assert all(job["output_resolution"] == [640, 360] for job in number_jobs)
    assert all(
        terminal["cameras"][camera_id]["schedule_error"]
        == "camera has no accepted RGB job"
        for camera_id in ("CineCam_01", "CineCam_02")
    )
    assert terminal["appearance_restore_ready"] is False
    assert callbacks == [terminal]
    summary = json.loads(
        (tmp_path / "output" / "episode_v2" / "render_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "failed"
    assert all(
        job["status"] == "failed"
        for job in summary["jobs"]
        if job["kind"] == "jersey_number_mask"
    )


def test_v2_mask_builder_exception_reaches_terminal_job_and_camera(
    tmp_path, monkeypatch
):
    class Delegate:
        def add_callable(self, callback):
            self.callback = callback

    executor = SimpleNamespace(
        on_executor_finished_delegate=Delegate(),
        on_executor_errored_delegate=Delegate(),
    )
    calls = []
    rgb_dir = tmp_path / "rgb"
    number_dir = tmp_path / "render_number_mask"
    rgb_dir.mkdir()
    number_dir.mkdir()
    rgb_job = {
        "name": "LS_Cam_01",
        "cam_id": "CineCam_01",
        "kind": "rgb",
        "seq_asset_path": "/Game/FutsalMOT/Sequences/LS_Cam_01",
        "render_dir": rgb_dir,
        "img1_dir": tmp_path / "img1",
        "cam_out": tmp_path,
    }
    number_job = {
        "name": "LS_Cam_01_NUMBER_MASK",
        "cam_id": "CineCam_01",
        "kind": "jersey_number_mask",
        "seq_asset_path": "/Game/FutsalMOT/Sequences/LS_Cam_01",
        "render_dir": number_dir,
        "number_mask_dir": tmp_path / "number_mask",
        "target_indices": [0, 3],
        "output_resolution": (640, 360),
        "post_process_material": "/Game/FutsalMOT/Materials/M_NumberMask",
    }
    pipeline = render_episode._AsyncRenderPipeline(
        [rgb_job, number_job],
        "episode_v2",
        tmp_path,
        [0, 3],
        on_complete=calls.append,
        require_number_mask_jobs=True,
    )
    monkeypatch.setattr(render_episode, "_clear_queue", lambda _queue: None)
    monkeypatch.setattr(render_episode, "_build_mrq_job", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        render_episode,
        "_build_mask_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("号码材质构建失败")
        ),
    )
    monkeypatch.setattr(pipeline, "_start_completion_watchdog", lambda: False)
    monkeypatch.setattr(render_episode, "_submit_render", lambda *_args: False)

    assert pipeline.start(
        object(), object(), executor, "/Game/Map", 640, 360, 30,
        "{frame_number}", 6,
    ) is False

    terminal = calls[0]
    terminal_number_job = next(
        job for job in terminal["jobs"]
        if job.get("kind") == "jersey_number_mask"
    )
    assert terminal_number_job["status"] == "failed"
    assert "号码材质构建失败" in terminal_number_job["schedule_error"]
    assert "号码材质构建失败" in terminal["cameras"]["CineCam_01"]["schedule_error"]
    assert terminal["appearance_restore_ready"] is False


def test_empty_v2_pipeline_marks_appearance_restore_not_ready(tmp_path):
    pipeline = render_episode._AsyncRenderPipeline(
        [], "episode_v2", tmp_path, [], require_number_mask_jobs=True
    )

    pipeline._finalize(failed=False, status="skipped", reason="no jobs")

    assert pipeline.terminal_result["status"] == "skipped"
    assert pipeline.terminal_result["jobs"] == []
    assert pipeline.terminal_result["appearance_restore_ready"] is False


def test_v1_partial_pipeline_keeps_legacy_terminal_contract(tmp_path):
    pipeline = render_episode._AsyncRenderPipeline(
        [], "episode_v1", tmp_path, []
    )

    pipeline._finalize(failed=False, status="partial", reason="legacy partial")

    assert pipeline.terminal_result["status"] == "partial"
    assert "appearance_restore_ready" not in pipeline.terminal_result


def test_active_environment_gate_fails_before_mrq_and_writes_summary(
    tmp_path, monkeypatch
):
    """未确认 environment preflight 时必须在 MRQ 访问前写入失败终态。"""
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {"episode_id": "episode_environment", "timing": {"source_step_seconds": 0.1}},
            [{"step": 0}],
        ),
    )
    monkeypatch.setattr(
        render_episode,
        "_mrq_subsystem",
        lambda: pytest.fail("environment gate 失败时不得访问 MRQ"),
    )
    callbacks = []

    result = render_episode.render_sequences(
        [{"name": "LS_Cam_01", "camera_actor": "CineCam_01"}],
        {"render_rgb": {"enabled": True}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        environment_active=True,
        environment_policy="futsalmot_environment_v1_5",
        environment_manifest_fingerprint="a" * 64,
        environment_preset="indoor_default",
        environment_preflight_verified=False,
        environment_transaction_state="applied",
    )

    terminal = result["terminal_result"]
    summary = json.loads(
        (tmp_path / "output" / "episode_environment" / "render_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert terminal["status"] == "failed"
    assert "MANUAL_REQUIRED" in terminal["reason"]
    assert terminal["environment_restore_ready"] is False
    assert summary["environment_restore_ready"] is False
    assert callbacks == [terminal]


@pytest.mark.parametrize(
    ("fingerprint", "preset"),
    [("", "indoor_default"), ("a" * 64, "")],
)
def test_active_environment_gate_rejects_missing_metadata_before_mrq(
    tmp_path, monkeypatch, fingerprint, preset
):
    """environment 指纹或 preset 缺失时必须保持 fail-closed。"""
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setitem(sys.modules, "unreal", SimpleNamespace())
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {"episode_id": "episode_environment", "timing": {"source_step_seconds": 0.1}},
            [{"step": 0}],
        ),
    )
    monkeypatch.setattr(
        render_episode,
        "_mrq_subsystem",
        lambda: pytest.fail("invalid environment metadata must not access MRQ"),
    )
    callbacks = []

    result = render_episode.render_sequences(
        [{"name": "LS_Cam_01", "camera_actor": "CineCam_01"}],
        {"render_rgb": {"enabled": True}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        environment_active=True,
        environment_policy="futsalmot_environment_v1_5",
        environment_manifest_fingerprint=fingerprint,
        environment_preset=preset,
        environment_preflight_verified=True,
        environment_transaction_state="rendering",
    )

    assert result["terminal_result"]["status"] == "failed"
    assert "MANUAL_REQUIRED" in result["terminal_result"]["reason"]
    assert callbacks == [result["terminal_result"]]


def test_active_environment_metadata_reaches_terminal_and_summary_after_finalize(tmp_path):
    """active environment 的便携 metadata 必须在终态摘要和 job 中一致。"""
    callbacks = []
    pipeline = render_episode._AsyncRenderPipeline(
        [{"name": "Seq_CamA", "cam_id": "CamA", "kind": "rgb"}],
        "episode_environment",
        tmp_path,
        [0, 3],
        on_complete=lambda result: callbacks.append(
            (result, json.loads(pipeline.summary_path().read_text(encoding="utf-8")))
        ),
        environment_active=True,
        environment_policy="futsalmot_environment_v1_5",
        environment_manifest_fingerprint="b" * 64,
        environment_preset="indoor_default",
        environment_preflight_verified=True,
        environment_transaction_state="rendering",
    )

    pipeline._finalize(
        failed=False,
        status="success",
        per_camera={"CamA": {"ok": True, "expected_frames": 2, "img1_frames": 2}},
    )

    terminal, summary = callbacks[0]
    for value in (terminal, summary, terminal["jobs"][0], summary["jobs"][0]):
        assert value["environment_policy"] == "futsalmot_environment_v1_5"
        assert value["environment_manifest_fingerprint"] == "b" * 64
        assert value["environment_preset"] == "indoor_default"
    assert terminal["environment_restore_ready"] is True
    assert summary["environment_restore_ready"] is True
    assert summary["cameras"]["CamA"]["environment_policy"] == (
        "futsalmot_environment_v1_5"
    )


def test_async_environment_callback_observes_summary_before_restore_handoff(tmp_path):
    """异步终态 callback 只能在 summary 落盘和 restore readiness 计算后触发。"""
    observations = []
    pipeline = render_episode._AsyncRenderPipeline(
        [],
        "episode_environment",
        tmp_path,
        [],
        on_complete=lambda result: observations.append(
            (result["environment_restore_ready"], pipeline.summary_path().is_file())
        ),
        environment_active=True,
        environment_policy="futsalmot_environment_v1_5",
        environment_manifest_fingerprint="c" * 64,
        environment_preset="indoor_default",
        environment_preflight_verified=True,
        environment_transaction_state="rendering",
    )

    pipeline._finalize(failed=False, status="success")

    assert observations == [(True, True)]


def test_v2_low_level_bool_and_material_path_cannot_unlock_mrq(
    tmp_path, monkeypatch
):
    """低层 v2 入口必须拒绝没有结构化真实证据的旧式解锁参数。"""
    monkeypatch.setitem(
        sys.modules,
        "unreal",
        SimpleNamespace(
            EditorAssetLibrary=SimpleNamespace(
                does_asset_exist=lambda _path: True,
            )
        ),
    )
    monkeypatch.setattr(render_episode, "_ACTIVE_RENDER", None)
    monkeypatch.setattr(
        render_episode,
        "load_episode",
        lambda _path: (
            {"episode_id": "episode_v2", "timing": {"source_step_seconds": 0.1}},
            [{"step": 0}],
        ),
    )
    monkeypatch.setattr(render_episode, "resolve_output_resolution", lambda _cfg: (64, 64))
    monkeypatch.setattr(render_episode, "resolve_preset", lambda _cfg: (None, None))
    monkeypatch.setattr(
        render_episode,
        "_apply_cv_gt_camera_post_process",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        render_episode,
        "_mrq_subsystem",
        lambda: pytest.fail("旧式 bool/path 参数不得触达 MRQ"),
    )
    callbacks = []

    result = render_episode.render_sequences(
        [{"name": "LS_Cam_01", "camera_actor": "CineCam_01"}],
        {"render_rgb": {"enabled": True}},
        "/Game/FutsalMOT/Sequences",
        tmp_path,
        tmp_path / "output",
        on_complete=callbacks.append,
        appearance_active=True,
        appearance_policy="futsalmot_appearance_v2",
        appearance_visibility_gate_verified=True,
        number_mask_post_process_material="/Game/FutsalMOT/Materials/M_NumberMask",
    )

    assert result["terminal_result"]["status"] == "failed"
    assert result["terminal_result"]["reason"].startswith("MANUAL_REQUIRED:")
    assert result["terminal_result"]["appearance_restore_ready"] is False
    assert callbacks == [result["terminal_result"]]


def test_environment_active_render_never_saves_level_for_setup():
    assert render_episode._should_save_level(False, False) is True
    assert render_episode._should_save_level(True, False) is False
    assert render_episode._should_save_level(False, True) is False
    assert render_episode._should_save_level(True, True) is False


def test_bake_first_frame_skips_level_save_during_environment(monkeypatch):
    calls = []
    monkeypatch.setattr(render_episode, "_save_current_level", lambda: calls.append("save"))
    monkeypatch.setattr(render_episode, "load_mapping", lambda path: {"L0": "Player_L0"})
    monkeypatch.setattr(render_episode, "find_all_actors", lambda mapping: {"L0": object()})
    monkeypatch.setattr(render_episode, "gk_entity_ids_from_meta", lambda meta: [])
    monkeypatch.setattr(render_episode, "apply_preview_frame", lambda *a, **k: None)

    saved = render_episode._bake_first_frame_for_render(
        {"gk_entity_ids": []},
        [{"step": 0}],
        "mapping.json",
        environment_active=True,
    )

    assert saved is True
    assert calls == []

    render_episode._bake_first_frame_for_render(
        {"gk_entity_ids": []},
        [{"step": 0}],
        "mapping.json",
        appearance_active=False,
        environment_active=False,
    )
    assert calls == ["save"]