# 单次 MRQ 同步 RGB、Mask 与 Runtime Pose 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将每个相机的 RGB、Object-ID Mask 和 Runtime Pose 合并到同一个 MRQ job 中求值，并使 P1 能从合并后的 multilayer EXR 中准确选择 Cryptomatte ID 层。

**Architecture:** `render_episode.py` 为 Object-ID mask task 创建一个包含 Deferred、PNG、EXR、Object-ID pass 和 Pose BurnIn 的单一 job。临时文件统一写到 camera `render/`，完成回调从 `FinalImage` PNG 归档 RGB、从 EXR 归档 `render_mask/`，继续使用现有 `img1/`、`render_mask/`、`pose_capture.jsonl` 和 P1 后处理契约。`cryptomatte.py` 根据 manifest hash 命中数量选择 ID 层，兼容旧的独立 Object-ID EXR 与新的 RGB+Object-ID 合并 EXR。

**Tech Stack:** Unreal Engine 5.8 Python/MRQ、Python 3.9、OpenEXR、NumPy、Pillow、pytest、现有 GRF-UE task workflow。

**Spec:** `Docs/superpowers/specs/2026-10-11-single-mrq-rgb-mask-pose-design.md`

## Global Constraints

- P1 代码运行在 Python 3.9 `.venv`；P2 代码只在 Unreal Editor Python 中运行。
- 当前正式地图为 `/Game/FutsalMOT/Maps/L_FutsalCourt`；完整 UE 文件使用 `FutsalMOTTools.run_python_file`。
- 保持 `img1/`、`render_mask/`、`mask/`、`pose_capture.jsonl`、`pose_session.json` 和 `render_summary.json` 的现有下游契约。
- 旧配置仅 RGB、仅 Mask、或 stencil PNG fallback 必须保持可用；本次目标配置是 RGB + Object-ID Mask + Runtime Pose。
- 只修改内层 Python 仓库代码、测试、权威文档和本次规格/计划；不修改无关 UE 资产，不使用 `git add -A`。
- 不自动 commit 或 push；验证结束前保留工作树供用户审阅。
- 新增注释、文档字符串和技术文档使用简体中文。

---

### Task 1: 为 Cryptomatte 多层 ID 选择建立失败测试

**Files:**
- Modify: `Content/FutsalMOT/code/tests/test_cryptomatte.py`
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/cryptomatte.py` only after the failing tests are observed

**Interfaces:**
- Consumes: manifest `{actor_label: hex_id}` and candidate layer arrays `{layer_name: float32(H,W,4)}`.
- Produces: an internal/public helper returning the selected float32 `(H,W)` ID channel and layer name, with a `ValueError` when no candidate or an ambiguous zero-match set exists.

- [ ] **Step 1: Add the failing candidate-layer tests**

Extend `tests/test_cryptomatte.py` with NumPy-backed tests using exact uint32 bit patterns:

```python
import numpy as np

from grf_ue_bridge.cryptomatte import select_cryptomatte_id_channel


def _id_float(hex_id):
    return np.array([int(hex_id, 16)], dtype=np.uint32).view(np.float32)[0]


def test_selects_object_id_layer_when_rgba_is_final_image():
    player = _id_float("1f21a2e4")
    layers = {
        "RGBA": np.zeros((1, 2, 4), dtype=np.float32),
        "ActorHitProxyMask00": np.array([[[player, 0, 0, 0], [0, 0, 0, 0]]], dtype=np.float32),
        "ActorHitProxyMask01": np.zeros((1, 2, 4), dtype=np.float32),
    }
    selected, name = select_cryptomatte_id_channel({"Player_L0": "1f21a2e4"}, layers)
    assert name == "ActorHitProxyMask00"
    assert selected.shape == (1, 2)
    assert selected[0, 0].view(np.uint32) == np.uint32(int("1f21a2e4", 16))


def test_legacy_rgba_layer_remains_supported():
    player = _id_float("1f21a2e4")
    layers = {"RGBA": np.array([[[player, 0, 0, 0]]], dtype=np.float32)}
    selected, name = select_cryptomatte_id_channel({"Player_L0": "1f21a2e4"}, layers)
    assert name == "RGBA"
    assert selected.shape == (1, 1)


def test_no_manifest_match_fails_with_candidate_names():
    with pytest.raises(ValueError, match="ActorHitProxyMask00"):
        select_cryptomatte_id_channel(
            {"Player_L0": "1f21a2e4"},
            {"RGBA": np.zeros((1, 1, 4), dtype=np.float32),
             "ActorHitProxyMask00": np.zeros((1, 1, 4), dtype=np.float32)},
        )
```

The tests must also retain the existing `hex_id_to_float` and mapping tests.

- [ ] **Step 2: Run the focused tests and verify failure**

Run from `Content/FutsalMOT/code`:

```powershell
uv run pytest tests/test_cryptomatte.py -q
```

Expected: collection failure because `select_cryptomatte_id_channel` does not exist yet.

- [ ] **Step 3: Implement the minimal manifest-driven selector**

In `src/grf_ue_bridge/cryptomatte.py`, add:

```python
def select_cryptomatte_id_channel(
    manifest: dict,
    layers: dict,
) -> Tuple[np.ndarray, str]:
    """按 manifest 精确匹配选择 Cryptomatte float32 ID R 通道。"""
```

Implementation requirements:

1. Convert all valid manifest hex values to `np.uint32` targets.
2. For each layer, accept `(H,W,4)` and `(H,W,1)` arrays; use channel 0 and view its float32 values as uint32 bits.
3. Count pixels whose bit pattern is in target bits. Ignore non-finite/unsupported arrays.
4. Select the candidate with the highest positive count. Prefer `RGBA` only when its count ties with another candidate, preserving old EXR behavior deterministically.
5. If all candidates have zero matches, raise `ValueError` containing the manifest target count and candidate layer names.
6. Return a contiguous float32 `(H,W)` array and the selected layer name.

Update `load_cryptomatte()` to call the helper instead of hard-coding `RGBA`, while retaining the existing fallback for OpenEXR layer objects and its `(manifest, ids)` return shape.

- [ ] **Step 4: Run the focused tests and verify pass**

```powershell
uv run pytest tests/test_cryptomatte.py -q
```

Expected: all focused Cryptomatte tests pass.

---

### Task 2: Add pure render-pass grouping helpers and tests

**Files:**
- Modify: `Content/FutsalMOT/code/tests/test_render_episode.py` if present, otherwise create it under `tests/`
- Modify: `Content/FutsalMOT/code/ue/render_episode.py`

**Interfaces:**
- Consumes: a scratch render directory containing `FinalImage.*.png`, optional BurnIn PNGs, and `*.exr` files.
- Produces: deterministic `find_final_image_files()`, `find_object_id_files()`, and `copy_object_id_frames()` behavior used by the MRQ finalizer.

- [ ] **Step 1: Inspect existing render tests and add failing pass-group tests**

Add tests for the exact filename behavior without importing `unreal`:

```python
def test_find_final_image_files_ignores_burnin_overlay(tmp_path):
    (tmp_path / "FinalImage.000000.png").touch()
    (tmp_path / "BurnInOverlay.000000.png").touch()
    (tmp_path / "FinalImage.000001.png").touch()
    result = find_final_image_files(tmp_path)
    assert sorted(result) == [0, 1]
    assert result[0].name == "FinalImage.000000.png"


def test_find_object_id_files_uses_only_exr(tmp_path):
    (tmp_path / "FinalImage.000000.png").touch()
    (tmp_path / "000000.exr").touch()
    (tmp_path / "ActorHitProxyMask.000000.png").touch()
    result = find_object_id_files(tmp_path)
    assert sorted(result) == [0]
    assert result[0].suffix == ".exr"
```

Use the repository's existing test import convention for `ue/render_episode.py`; if no test module exists, add `tests/test_render_episode.py` with only pure helper imports.

- [ ] **Step 2: Run the focused test and verify failure**

```powershell
uv run pytest tests/test_render_episode.py -q
```

Expected: failure because the explicit helpers do not exist.

- [ ] **Step 3: Implement deterministic pass helpers**

In `ue/render_episode.py`:

- Add `find_final_image_files(render_dir: Path) -> Dict[int, Path]` that scans PNGs, recognizes prefixes beginning with `FinalImage` or exactly `Final`, and never falls back to BurnIn overlay when a FinalImage group exists.
- Keep `find_rendered_frame_numbers()` as a compatibility wrapper over the final-image helper for RGB-only jobs.
- Add `find_object_id_files(render_dir: Path) -> Dict[int, Path]` that scans only EXR files and returns the frame number parsed from the trailing numeric token. It must reject duplicate frame numbers with a clear exception rather than silently choose one.
- Add `copy_object_id_frames(render_mask_dir: Path, source_dir: Path, keep_indices: Sequence[int]) -> int` that copies the selected EXR files to `render_mask/{render_frame:06d}.exr`, creates the directory, and returns the number copied.
- Keep `copy_mask_frames()` unchanged for PNG stencil fallback and legacy independent mask directories.

- [ ] **Step 4: Run pure render helper tests**

```powershell
uv run pytest tests/test_render_episode.py -q
```

Expected: PASS.

---

### Task 3: Build one MRQ job for RGB, Object-ID EXR and Pose

**Files:**
- Modify: `Content/FutsalMOT/code/ue/render_episode.py`
- Modify: `Content/FutsalMOT/code/tests/test_render_episode.py` with pure configuration tests where practical

**Interfaces:**
- Consumes: `sequences_cfg`, `annotation_cfg`, `mask_source`, `preset`, `cv_gt`, existing `_build_mrq_job()` and `_build_mask_job()` conventions.
- Produces: `_build_combined_mrq_job()` and a single `kind="combined"` pipeline record for Object-ID configurations.

- [ ] **Step 1: Add a pure configuration contract test**

Add a testable helper or a fake-config test proving combined configuration requests these settings exactly:

```text
MoviePipelineOutputSetting
MoviePipelineImageSequenceOutput_PNG
MoviePipelineImageSequenceOutput_EXR or MoviePipelineImageSequenceOutput_OpenEXR
MoviePipelineDeferredPassBase
MoviePipelineObjectIdRenderPass
MoviePipelineBurnInSetting when pose is enabled
```

The test must also assert the output file name format contains `{render_pass}` and `{frame_number}`.

- [ ] **Step 2: Implement `_build_combined_mrq_job()`**

Add a builder next to `_build_mrq_job()` with this signature:

```python
def _build_combined_mrq_job(
    queue,
    seq_asset_path: str,
    map_path: str,
    render_dir: Path,
    image_width: int,
    image_height: int,
    frame_rate: int,
    file_name_format: str,
    zero_pad: int,
    mask_source: str,
    post_process_material: str = None,
    preset=None,
    cv_gt=None,
):
```

Implementation:

1. Allocate one `MoviePipelineExecutorJob`, assign Sequence and map.
2. Set `MoviePipelineOutputSetting.output_directory` to `render_dir` and `file_name_format` to `"{render_pass}." + file_name_format` so PNG pass names are explicit. EXR writer intentionally ignores `{render_pass}` and keeps all render passes as named layers in one EXR.
3. Add PNG output, EXR output with `multilayer=True`, Deferred pass, and `MoviePipelineObjectIdRenderPass` configured with `ACTOR` or `ACTOR_WITH_HIERARCHY` as current code does.
4. For `mask_source="post_process_material"`, do not use combined Object-ID mode; route to existing separate fallback path.
5. Call `_apply_mrq_preset(config, preset, cv_gt, is_mask=False)` once so BurnIn and RGB deterministic settings are applied once. Add the same console-variable overrides currently used for RGB.
6. Set job configuration through `_set_job_config()` and raise on failure.

- [ ] **Step 3: Change `render_sequences()` job construction**

For `mask_enabled and mask_source == "object_id_pass"`, create one info record per camera:

```python
{
    "name": seq_name,
    "cam_id": cam_id,
    "seq_asset_path": seq_asset_path,
    "cam_out": cam_out,
    "render_dir": cam_out / "render",
    "render_mask_dir": cam_out / "render_mask",
    "img1_dir": cam_out / "img1",
    "kind": "combined",
    "mask_source": "object_id_pass",
    "preset": preset,
    "cv_gt": cv_gt,
}
```

Do not append a second mask job for this mode. Keep the current two-job construction for RGB-only and stencil PNG fallback until the combined path passes smoke.

- [ ] **Step 4: Update `_AsyncRenderPipeline.start()` dispatch**

Add an explicit `kind == "combined"` branch that calls `_build_combined_mrq_job()`. Keep existing `mask` and RGB branches unchanged for compatibility.

- [ ] **Step 5: Update completion detection and finalization**

For `kind == "combined"`:

- `_all_keep_frames_present()` requires `find_final_image_files(render_dir)` and `find_object_id_files(render_dir)` to both contain every `keep_indices` frame.
- `_copy_and_finalize()` copies RGB with `copy_rendered_frames()`, copies EXRs with `copy_object_id_frames(render_mask_dir, render_dir, keep_indices)`, records `img1_frames`, `mask_frames`, `mask_source="object_id_exr"`, and marks the camera successful only when both counts equal expected.
- Zero-waste removes only PNG files in the scratch render directory after RGB copy; EXR source files remain in `render/` only until copied, then the canonical copy in `render_mask/` is authoritative.
- `_total_render_files()` must count PNG and EXR as before.
- `per_camera` must contain exactly one camera entry, not separate RGB and mask entries.

Retain existing behavior for `kind == "rgb"` and `kind == "mask"`.

- [ ] **Step 6: Run pure tests and compile-check**

```powershell
uv run pytest tests/test_render_episode.py tests/test_cryptomatte.py -q
uv run python -m py_compile ue/render_episode.py src/grf_ue_bridge/cryptomatte.py
```

Expected: PASS without importing `unreal` in the P1 process.

---

### Task 4: Update Cryptomatte tests, docs and static validation

**Files:**
- Modify: `Content/FutsalMOT/code/tests/test_cryptomatte.py`
- Modify: `Content/FutsalMOT/code/README.md`
- Modify: `Content/FutsalMOT/code/docs/DATA_CONTRACT.md`
- Modify: `Content/FutsalMOT/code/docs/VALIDATION_AND_LIMITATIONS.md`

**Interfaces:**
- Consumes: combined MRQ and decoder behavior from Tasks 1-3.
- Produces: authoritative documentation describing one-job output and manifest-selected EXR ID layers.

- [ ] **Step 1: Add a decoder regression fixture test**

Extend the Cryptomatte tests with two candidate layers containing one known Player hash and assert the selector chooses the layer with the greater manifest hit count. Include a negative test where only FinalImage-like data exists and require `ValueError`.

- [ ] **Step 2: Update authoritative documentation**

Update `README.md` to state that RGB, Object-ID EXR and Runtime Pose use one MRQ job for Object-ID tasks, while stencil fallback and legacy RGB-only paths remain separate.

Update `DATA_CONTRACT.md`:

- `render/` may contain `FinalImage*.png` scratch files and temporary multilayer EXR before finalize.
- `render_mask/*.exr` is the canonical Object-ID EXR archive after finalize.
- A combined EXR may store RGB `RGBA` and Object-ID layers such as `ActorHitProxyMask00`; P1 selects the ID layer by manifest matching.
- Runtime Pose sampling occurs in the same MRQ job as the Object-ID output for the formal path.

Update `VALIDATION_AND_LIMITATIONS.md`:

- Audit must check both RGB and Object-ID frame sets for combined jobs.
- Static tests cannot prove final pixel alignment; smoke overlay and nearest-mask distance remain required.
- The combined job reduces cross-job timing variance but does not assert that every AnimGraph/Retarget pose is geometrically correct.

- [ ] **Step 3: Run all P1 tests and diff checks**

```powershell
uv run pytest
git diff --check
```

Expected: PASS; no files outside the planned inner-repo files are changed by this task.

---

### Task 5: Run UE smoke and quantify alignment

**Files:**
- No new source file required; use current resolved smoke task and `run_task.py` entry points.
- Runtime outputs remain under configured dataset root and `.futsalmot/`; do not add generated outputs to Git.

**Interfaces:**
- Consumes: current `configs/player003_smoke_10frames_1cam.json`, formal map, current Recorder Blueprints, and Tasks 1-4 code.
- Produces: one-job `render_summary.json`, pose session, canonical RGB/EXR/Mask/Pose outputs, full validation report, and alignment metrics.

- [ ] **Step 1: Re-run static task validation and resolve**

```powershell
uv run grf-ue task validate configs/player003_smoke_10frames_1cam.json
uv run grf-ue task resolve configs/player003_smoke_10frames_1cam.json
```

Expected: PASS and the resolved task still points to `episode_player003_smoke_10f`.

- [ ] **Step 2: Load and verify the formal map through Unreal MCP**

Use the already verified Scene tool to load `/Game/FutsalMOT/Maps/L_FutsalCourt`, then query `get_current_level`. Use `FutsalMOTTools.run_python_code` only for a small read-only check that `LS_Cam_01`, all ten Player labels, `DatasetPoseSource` tags, and the five Recorder assets exist.

- [ ] **Step 3: Run the smoke full mode through real UE Python**

Execute the generated resolved-task command with `C5_RUN_MODE=full` using `FutsalMOTTools.run_python_file` on `ue/run_task.py`. Read the returned `success/result/log`; do not run a second render while this MRQ is active.

- [ ] **Step 4: Verify the one-job output before pose finalize**

Read current UE logs for `LogPython`, `LogMovieRenderPipeline`, and `LogModelContextProtocol`. Inspect the smoke camera directory and require:

```text
render_summary.status == "success"
render/ contains FinalImage PNG frames and temporary/archived EXR source frames
render_mask/ contains 10 EXR frames
render_summary cameras[CineCam_01].img1_frames == 10
render_summary cameras[CineCam_01].mask_frames == 10
render_summary cameras[CineCam_01].mask_source == "object_id_exr"
```

- [ ] **Step 5: Run pose-finalize and P1 postprocess**

Run the real UE `pose-finalize` command, then:

```powershell
uv run grf-ue task postprocess configs/player003_smoke_10frames_1cam.json
uv run grf-ue task audit configs/player003_smoke_10frames_1cam.json --validation-level full
```

Expected: `pose_session.capture_complete=true`, 1300 raw samples, `validate-annotations` and `validate-pose` pass inside postprocess, and audit `ValidationResult.passed=true`.

- [ ] **Step 6: Compute and record pixel alignment metrics**

Use a UTF-8 Python 3.9 diagnostic outside the UE process to project `pose_keypoints.jsonl` with `camera.json`, measure nearest distance to each object mask, and report per entity:

```text
frame_count, mean_distance_px, p95_distance_px, max_distance_px,
face_mean_distance_px, limb_mean_distance_px, outlier_frames
```

Compare the new metrics against the prior smoke baseline: L1 frame 1 mean/max `17.7/30.5 px`, L2 `1.3/5.3 px`, L3 `2.2/12.3 px`, and the other actors below approximately `1 px` mean. Do not claim the issue fixed solely from structural validators.

- [ ] **Step 7: Inspect final Git state without committing**

Run:

```powershell
git -C D:\projects\FutsalMOT_UEDataset status --short --branch
git -C D:\projects\FutsalMOT_UEDataset\Content\FutsalMOT\code status --short --branch
```

Report only intended inner-repo source/test/doc/spec/plan changes and existing unrelated dirty files separately. Stop before commit/push.
