# Player_003 Dataset Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the MPFB Player_003 visual profile to all ten existing `L_FutsalCourt` player actors, validate the complete RGB/Mask/Runtime Pose dataset path with a short smoke episode, then generate and audit a separate 900-frame four-camera production episode.

**Architecture:** Keep the existing `BP_FutsalPlayerBase_C` actor instances, labels, Pose tags, transforms, capsule components, actor mapping, and Sequence bindings. Add a pure-Python profile normalization layer in the dataset submodule and a UE-only `player_visuals.py` adapter that performs preflight, snapshots the current mesh/AnimBP state, applies Player_003, restores a snapshot, and writes sanitized provenance. Integrate the adapter into `ue/run_task.py` before Sequence/MRQ work, while leaving tasks without `player_visuals` unchanged.

**Tech Stack:** Unreal Engine 5.8 Python API, `FutsalMOTTools.run_python_file`, Python 3.9, Pydantic task models, pytest, GRF task workflows, Movie Render Queue, Object-ID pass, Runtime Pose Recorder, and existing P1 postprocess/audit/manifest commands.

**Spec:** `Docs/superpowers/specs/2026-10-09-player003-dataset-production-design.md`

## Global Constraints

- The formal map is `/Game/FutsalMOT/Maps/L_FutsalCourt`; load and verify it before any write.
- The ten existing actor labels remain `Player_L0..Player_L4` and `Player_R0..Player_R4`; the actor mapping and entity IDs remain unchanged.
- Player_003 mesh is `/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003`.
- Player_003 uses `/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base` and `/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget`.
- Only the scripted mesh and AnimBP fields may be restored by rollback; transforms, tags, component structure, and user edits are never reset by restore.
- The smoke task is a unique episode with one camera and approximately ten frames; the production task is a unique episode with 900 frames and four cameras.
- P1 code runs in Python 3.9; P2 code runs only in the real Unreal Editor Python environment.
- Use `FutsalMOTTools.run_python_file` for complete UE scripts and read Unreal logs after failures.
- Do not use `git add -A`, save-all, destructive cleanup, force-push, or automatic commit/push.
- Existing unrelated dirty files in both repositories must remain untouched.
- New comments, docstrings, and technical documentation use Simplified Chinese.

---

## File Map

### Inner Python repository: `Content/FutsalMOT/code/`

- Create `ue/player_visuals.py`: pure profile normalization plus UE Editor apply, restore, preflight, snapshot, and sanitized provenance helpers. Import `unreal` lazily inside UE-only functions.
- Modify `ue/run_task.py`: load and validate optional `ue.player_visuals`, apply/preflight on `full` and `sequence`, preflight-only on `render`, and write episode provenance before Sequence/MRQ work.
- Create `configs/player003_smoke_10frames_1cam.json`: unique smoke task with Player_003 assigned to all ten entities, RGB, Object-ID Mask, Runtime Pose, and validation outputs enabled.
- Create `configs/player003_production_900frames_30fps_4cam.json`: unique production task copied from the validated production contract with Player_003 profile assignment and a separate output episode.
- Create or modify `tests/test_player_visuals.py`: test profile expansion, validation, stable fingerprinting, sanitized provenance, invalid profile failures, and legacy no-profile compatibility without importing `unreal`.

### Outer UE repository: `D:\projects\FutsalMOT_UEDataset`

- Modify only the ten `L_FutsalCourt` External Actor packages actually changed by the apply script, plus any intentionally generated formal Sequence assets if the smoke run creates/replaces them.
- Do not modify the formal Player_003 asset, MPFB Core assets, shared AnimBP, or unrelated dirty assets.
- Runtime rollback JSON, resolved tasks, logs, and dataset outputs remain under ignored `.futsalmot/runtime/` or the configured dataset root.

## Interfaces

The implementation must expose these stable inner-module interfaces:

```python
def normalize_player_visuals(
    player_visuals: dict | None,
    *,
    entity_ids: tuple[str, ...] = DEFAULT_PLAYER_ENTITY_IDS,
) -> dict | None: ...

def player_visuals_fingerprint(normalized: dict | None) -> str | None: ...

def sanitized_player_visuals_provenance(normalized: dict | None) -> dict | None: ...

def preflight_player_visuals(
    normalized: dict,
    mapping: dict,
    *,
    expected_level: str = FORMAL_LEVEL,
) -> dict: ...

def apply_player_visuals(
    normalized: dict,
    mapping: dict,
    *,
    rollback_path: str,
) -> dict: ...

def restore_player_visuals(rollback_path: str) -> dict: ...
```

The pure functions must work in the P1 test process without `unreal`. UE functions may import `unreal` only when called inside the Editor and must return JSON-serializable dictionaries with `ok`, `errors`, `warnings`, and per-actor details.

---

### Task 1: Add the profile contract and pure tests

**Files:**
- Create: `Content/FutsalMOT/code/ue/player_visuals.py`
- Create: `Content/FutsalMOT/code/tests/test_player_visuals.py`

**Interfaces:**
- Consumes: optional `ue.player_visuals` dictionary from a resolved task and the fixed entity IDs `L0..L4`, `R0..R4`.
- Produces: `normalize_player_visuals`, `player_visuals_fingerprint`, and `sanitized_player_visuals_provenance` for later UE and `run_task.py` integration.

- [ ] **Step 1: Write failing pure-contract tests**

Add tests for these exact behaviors:

```python
def test_player003_profile_expands_to_all_ten_entities():
    normalized = normalize_player_visuals({
        "default_profile": "mpfb_player_003",
        "profiles": {"mpfb_player_003": {
            "mesh": "/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003",
            "anim_class": "/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget",
            "skeleton": "/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base",
        }},
        "entity_profiles": {},
    })
    assert set(normalized["entity_profiles"]) == {
        "L0", "L1", "L2", "L3", "L4", "R0", "R1", "R2", "R3", "R4",
    }
    assert all(v == "mpfb_player_003" for v in normalized["entity_profiles"].values())


def test_fingerprint_is_stable_and_does_not_include_machine_paths():
    normalized = normalize_player_visuals(player003_config())
    first = player_visuals_fingerprint(normalized)
    second = player_visuals_fingerprint(json.loads(json.dumps(normalized)))
    assert first == second
    assert "D:" not in json.dumps(sanitized_player_visuals_provenance(normalized))


def test_invalid_profile_reference_fails_fast():
    with pytest.raises(ValueError, match="不存在的 profile"):
        normalize_player_visuals({"default_profile": "missing", "profiles": {}, "entity_profiles": {}})


def test_missing_player_visuals_preserves_legacy_behavior():
    assert normalize_player_visuals(None) is None
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run from the inner repository:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_player_visuals.py -q
```

Expected: collection or assertion failure because the new module and interfaces do not exist yet.

- [ ] **Step 3: Implement the pure normalization layer**

Implement the following exact normalized shape:

```python
{
    "default_profile": "mpfb_player_003",
    "profiles": {
        "mpfb_player_003": {
            "mesh": "/Game/.../MPFB_Player_003",
            "anim_class": "/Game/.../ABP_MPFB_RuntimeRetarget",
            "skeleton": "/Game/.../SKEL_MPFB_Base",
        }
    },
    "entity_profiles": {"L0": "mpfb_player_003", "...": "mpfb_player_003"},
}
```

Require non-empty profile IDs and asset paths, require all entity mappings to reference defined profiles, fill omitted entity mappings from `default_profile`, and return `None` for a missing/empty `player_visuals`. Compute the fingerprint from canonical JSON with sorted keys and no absolute filesystem paths. The provenance function returns only profile IDs and `/Game/...` asset paths.

- [ ] **Step 4: Run the focused tests and verify pass**

Run the same command. Expected: all profile contract tests pass.

- [ ] **Step 5: Run the existing P1 config tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_task_config.py tests/test_task_resolver.py tests/test_ue_resolved_task.py -q
```

Expected: PASS. Record any local `.futsalmot/local.json` path-related failures separately; do not edit that ignored machine config.

### Task 2: Add UE preflight, apply, rollback, and restore

**Files:**
- Modify: `Content/FutsalMOT/code/ue/player_visuals.py`
- Create: `Content/FutsalMOT/code/ue/apply_player_visuals.py`
- Create: `Content/FutsalMOT/code/ue/restore_player_visuals.py`

**Interfaces:**
- Consumes: normalized profiles and the existing `actor_mapping.example.json` mapping.
- Produces: Editor scripts callable through `FutsalMOTTools.run_python_file`, plus JSON snapshots under `.futsalmot/runtime/`.

- [ ] **Step 1: Add a pure test for snapshot field scope**

Extend `tests/test_player_visuals.py` with a test that a serialized snapshot contains only actor identity, label, tags, transform record, component name, old mesh, old AnimBP, and old skeleton, and that restore payload generation contains only `skeletal_mesh` and `anim_class`.

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_player_visuals.py -q
```

Expected: FAIL because snapshot/restore serialization helpers are not implemented.

- [ ] **Step 3: Implement UE-safe actor discovery and preflight**

Inside `player_visuals.py`, use `unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()` and exact case-insensitive label matching for `Player_L0..Player_R4`; reject missing or duplicate labels. For each actor require exactly one `SkeletalMeshComponent` named `CharacterMesh0`, load the profile Mesh, AnimBP generated class, and Skeleton, and verify the Mesh skeleton path equals the profile skeleton. Verify the actor has its expected `PoseL*` or `PoseR*` tag. Include current transforms and capsule properties in the read-only result, but do not modify them.

Return:

```python
{
    "ok": True,
    "level": "/Game/FutsalMOT/Maps/L_FutsalCourt",
    "actors": [{"entity_id": "L0", "label": "Player_L0", ...}],
    "errors": [],
    "warnings": [],
}
```

Reject any current level other than the formal level. Do not use guessed reflection APIs; use only properties already confirmed in the running Editor, with small `try/except` blocks around individual reads.

- [ ] **Step 4: Implement snapshot and apply**

Before changes, serialize the current state for all ten actors to the specified rollback path. Apply only:

```python
component.set_skeletal_mesh_asset(target_mesh)
component.set_editor_property("anim_class", generated_anim_class)
```

Use `set_skeletal_mesh_asset` if available and fail with a structured error if it is not. Preserve the component relative transform and all actor data. Save only the ten changed actors with `EditorActorSubsystem.save_loaded_actors()` or the verified per-actor save method; report each save result. Do not call `save_dirty_packages` or save all assets.

- [ ] **Step 5: Implement restore and standalone Editor entry points**

`apply_player_visuals.py` must load a JSON file containing `resolved_task`, normalize `ue_profile.player_visuals`, load the mapping, run preflight, apply, save, and print one JSON result. `restore_player_visuals.py` must load the rollback JSON, verify the formal map and actor labels, restore only the old Mesh and AnimBP, save only those actors, and print one JSON result. Both scripts must exit cleanly with a structured failure and no partial silent success.

- [ ] **Step 6: Run pure tests and a read-only UE preflight**

Run the pure focused tests, then use `FutsalMOTTools.run_python_file` on the preflight/apply helper in `L_FutsalCourt` only after confirming the map is loaded. Expected: ten unique actors, Player_003 target assets load, shared Skeleton matches, all Pose tags exist, and no changes are saved by preflight.

### Task 3: Integrate profile application into `run_task.py` and provenance

**Files:**
- Modify: `Content/FutsalMOT/code/ue/run_task.py`
- Modify: `Content/FutsalMOT/code/ue/player_visuals.py`
- Modify: `Content/FutsalMOT/code/tests/test_player_visuals.py`

**Interfaces:**
- Consumes: `rt["ue_profile"].get("player_visuals")`, resolved actor mapping, and episode directory.
- Produces: deterministic preflight/apply behavior before Sequence/MRQ and `provenance/player-visuals.json`.

- [ ] **Step 1: Add integration-level pure tests**

Test that a resolved task with `player_visuals` produces sanitized provenance at:

```text
<episode>/provenance/player-visuals.json
```

and that a task with no `player_visuals` does not require any profile or asset loading. Test that invalid profile configuration fails before the code reaches Sequence/MRQ callbacks.

- [ ] **Step 2: Implement a small `run_task.py` profile hook**

After mapping validation and before `create_sequence`, add a helper with this behavior:

```python
normalized = normalize_player_visuals(ue_profile.get("player_visuals"))
if normalized is not None:
    if mode in ("full", "sequence"):
        apply_player_visuals(normalized, mapping, rollback_path=runtime_rollback_path)
    preflight_result = preflight_player_visuals(normalized, mapping)
    if not preflight_result["ok"]:
        return _fail("player_visuals preflight failed")
    write_player_visuals_provenance(episode_dir, normalized)
```

For `render`, do not apply or restore; only preflight the existing scene. For `full` and `sequence`, apply before Sequence creation. Run the preflight again after apply so the actual component state is verified. Make the hook a no-op for legacy tasks without `player_visuals`.

- [ ] **Step 3: Run pure tests and compile-check modified Python**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_player_visuals.py tests/test_task_config.py tests/test_task_resolver.py -q
.venv\Scripts\python.exe -m py_compile ue/player_visuals.py ue/apply_player_visuals.py ue/restore_player_visuals.py ue/run_task.py
```

Expected: PASS. `py_compile` must run in the Python 3.9 environment and must not import `unreal`.

### Task 4: Add smoke and production task configurations

**Files:**
- Create: `Content/FutsalMOT/code/configs/player003_smoke_10frames_1cam.json`
- Create: `Content/FutsalMOT/code/configs/player003_production_900frames_30fps_4cam.json`
- Modify: `Content/FutsalMOT/code/tests/test_player_visuals.py` only if shared config helpers are needed

**Interfaces:**
- Consumes: existing task schema and Player_003 profile contract.
- Produces: two unique executable task files with separate episode names and output roots.

- [ ] **Step 1: Write smoke configuration**

Use `schema=futsalmot_dataset_task`, version `2`, a unique `task_id=player003_smoke_10frames_1cam`, `num_steps=10`, `target_fps=10`, `playback_fps=30`, one `CineCam_01`/`LS_Cam_01` entry, `replace_existing=true`, RGB enabled at `1920x1080`, Object-ID Mask enabled, Runtime Pose enabled, MOT/YOLO outputs enabled, and `audit.expected_frames_per_camera=10`. Include:

```json
"player_visuals": {
  "default_profile": "mpfb_player_003",
  "profiles": {
    "mpfb_player_003": {
      "mesh": "/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003",
      "anim_class": "/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget",
      "skeleton": "/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base"
    }
  },
  "entity_profiles": {
    "L0": "mpfb_player_003", "L1": "mpfb_player_003", "L2": "mpfb_player_003", "L3": "mpfb_player_003", "L4": "mpfb_player_003",
    "R0": "mpfb_player_003", "R1": "mpfb_player_003", "R2": "mpfb_player_003", "R3": "mpfb_player_003", "R4": "mpfb_player_003"
  }
}
```

Use a new episode name under the configured dataset root; do not reuse `episode_pose_smoke` or any existing production directory.

- [ ] **Step 2: Write production configuration**

Copy the validated structure from `configs/production_900frames_30fps_4cam.json`: `num_steps=300`, `target_fps=30`, `playback_fps=30`, `trajectory_time_scale=2.0`, four cameras `CineCam_01..CineCam_04`, `expected_frames_per_camera=900`, Object-ID Mask and Runtime Pose enabled, and full P1 output formats. Use a new task ID, episode name, and dataset subdirectory; do not edit the existing production config.

- [ ] **Step 3: Validate both configs and inspect the resolved task**

Run from the inner repository:

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.cli task validate configs/player003_smoke_10frames_1cam.json
.venv\Scripts\python.exe -m grf_ue_bridge.cli task validate configs/player003_production_900frames_30fps_4cam.json
.venv\Scripts\python.exe -m grf_ue_bridge.cli task resolve configs/player003_smoke_10frames_1cam.json
```

Expected: both task validations pass, resolved `ue_profile.player_visuals` is preserved, and the resolved output paths are under the configured dataset root.

### Task 5: Apply Player_003 to the formal map and run smoke

**Files/Assets:**
- Modify: ten `L_FutsalCourt` External Actor packages found by exact labels.
- Create: ignored runtime rollback JSON and smoke resolved task/episode outputs.

**Interfaces:**
- Consumes: the smoke resolved task, Player_003 assets, formal map, and existing actor mapping.
- Produces: ten saved actors using Player_003 and an audited smoke episode.

- [ ] **Step 1: Capture a before-state report**

With `/Game/FutsalMOT/Maps/L_FutsalCourt` loaded, run a read-only diagnostic through `FutsalMOTTools.run_python_code` or the preflight script and save its JSON result under ignored `.futsalmot/runtime/player003/`. Record each actor's label, object name, tags, world transform, component relative transform, current Mesh, AnimBP, Skeleton, capsule radius/half-height, and package path. Confirm no non-player asset is in the write set.

- [ ] **Step 2: Apply the profile through the UE script**

Run `apply_player_visuals.py` with the smoke resolved task through `FutsalMOTTools.run_python_file`. Read `success/result/log`; require ten actors applied and saved, a rollback path, and no errors. If the call fails, read `LogPython`, `LogBlueprint`, and `LogModelContextProtocol` before one corrective retry. If the same operation fails a second time, stop as `MANUAL_REQUIRED`.

- [ ] **Step 3: Verify the applied scene before Sequence creation**

Run read-only diagnostics and verify for all ten actors:

```text
CharacterMesh0 mesh = MPFB_Player_003
mesh skeleton = SKEL_MPFB_Base
anim class = ABP_MPFB_RuntimeRetarget_C
labels unchanged
Pose tags unchanged
actor transforms unchanged
capsule components unchanged
```

Also verify the five C4 Pose Recorder actors remain present and the actor tags still identify all ten entities.

- [ ] **Step 4: Export the ten-frame trajectory and execute UE full smoke**

Run:

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.cli task export configs/player003_smoke_10frames_1cam.json
.venv\Scripts\python.exe -m grf_ue_bridge.cli validate D:\projects\FutsalMOT\<smoke_episode_name>
```

Then run the generated resolved task in UE via `FutsalMOTTools.run_python_file` with `C5_RUN_MODE=full`/the configured resolved task path. Do not block the Editor while MRQ runs.

- [ ] **Step 5: Finalize Runtime Pose and inspect MRQ output**

After `render_summary.json` reports success, run `run_task.py` again with `C5_RUN_MODE=pose-finalize`. Require `pose_session.capture_complete=true`, ten actor records per expected frame, and COCO17 output. Query Unreal logs for Python, Blueprint, MRQ, and recorder errors.

- [ ] **Step 6: Run P1 postprocess, validations, audit, and manifest**

Run:

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.cli task postprocess configs/player003_smoke_10frames_1cam.json
.venv\Scripts\python.exe -m grf_ue_bridge.cli task audit configs/player003_smoke_10frames_1cam.json --validation-level quick
.venv\Scripts\python.exe -m grf_ue_bridge.cli task manifest configs/player003_smoke_10frames_1cam.json
```

Require `ValidationResult.passed=true`, one camera, ten aligned RGB/mask/annotation frames, valid IDs `0..11`, and complete pose outputs. Keep transient outputs for diagnosis until the smoke passes; do not run cleanup apply.

- [ ] **Step 7: Perform visual acceptance**

Render or inspect the smoke RGB, mask, and pose overlay. Confirm no duplicate clothing, no pants displacement, no missing body/hair/shoes, no character floating/sinking, and keypoints remain on Player_003 body parts. Treat visual acceptance as a separate gate from static validation.

### Task 6: Generate and audit the formal 900-frame four-camera episode

**Files/Assets:**
- Modify: no new source files beyond the task configuration and runtime outputs.
- Create: ignored formal resolved task, episode output, audit, and manifest.

**Interfaces:**
- Consumes: successful Player_003 smoke gate, applied formal map state, and production task config.
- Produces: a separate 900-frame/four-camera Player_003 dataset episode with validated RGB, masks, labels, pose, audit, and manifest.

- [ ] **Step 1: Re-run static task validation and confirm the smoke gate**

Run production `task validate` and inspect the smoke audit JSON. Do not start production if smoke audit, pose capture, or visual acceptance failed.

- [ ] **Step 2: Export and validate the production trajectory**

Run:

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.cli task export configs/player003_production_900frames_30fps_4cam.json
.venv\Scripts\python.exe -m grf_ue_bridge.cli validate D:\projects\FutsalMOT\<production_episode_name>
```

Require 900 frame rows, fixed ten-player IDs, finite coordinates, and valid seed metadata.

- [ ] **Step 3: Run UE full production**

Use the generated resolved task and `run_task.py --mode full` in the current Editor. Confirm four cameras, four Sequences, 900-frame playback ranges, applied Player_003 visuals, and asynchronous MRQ submission. Wait for `render_summary.json` before any postprocess.

- [ ] **Step 4: Finalize Runtime Pose and run all P1 postprocess**

Run `pose-finalize` after MRQ completion, then run `task postprocess` with the production config. Require RGB, Object-ID mask, MOT, YOLO Detect/Segment, Runtime Pose, COCO17, and pose label frame sets to match 900 frames per camera where applicable.

- [ ] **Step 5: Run full audit and manifest verification**

Run:

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.cli task audit configs/player003_production_900frames_30fps_4cam.json --validation-level full
.venv\Scripts\python.exe -m grf_ue_bridge.cli task manifest configs/player003_production_900frames_30fps_4cam.json
.venv\Scripts\python.exe -m grf_ue_bridge.cli verify-manifest D:\projects\FutsalMOT\<production_root>
```

Require `passed=true`, four cameras, 900 aligned frames per camera, consistent ID mappings, valid calibration, complete render summary, complete Runtime Pose, and matching manifest checksums.

- [ ] **Step 6: Record final status without committing**

Report the exact smoke and production episode paths, audit/manifest results, modified External Actor packages, rollback path, inner repository status, outer repository status, and any residual warnings. Stop before commit/push until the user explicitly authorizes submission.

## Verification Matrix

| Gate | Evidence | Required result |
| --- | --- | --- |
| Pure profile contract | `tests/test_player_visuals.py` | PASS |
| Task schema | smoke and production `task validate` | PASS |
| Map preflight | UE JSON result | ten unique actors, valid MPFB assets |
| Applied scene | UE readback | Player_003 mesh, shared Skeleton, MPFB AnimBP on all ten |
| Smoke MRQ | `render_summary.json` and UE logs | success, expected frame counts, no relevant errors |
| Smoke pose | `pose_session.json` and COCO17 files | `capture_complete=true` |
| Smoke audit | audit JSON | `passed=true` |
| Visual smoke | RGB/mask/pose overlay | no geometry or keypoint defects |
| Production trajectory | episode validator | 900 valid frames |
| Production audit | full audit JSON | `passed=true` |
| Production manifest | `verify-manifest` | checksum match |

## Plan Self-Review

- Spec coverage: Profile normalization is Task 1; UE apply/restore/preflight is Task 2; `run_task.py` integration and provenance is Task 3; smoke/production configurations are Task 4; rollback and formal map application are Task 5; full production gates are Task 6.
- Placeholder scan: `<smoke_episode_name>` and `<production_episode_name>` in shell examples are runtime substitutions from the exact task JSON `episode_name`, not implementation placeholders; the executing agent must replace them with the values in the created config before running commands. No code task contains TODO/TBD or unspecified behavior.
- Type consistency: all later tasks consume `normalize_player_visuals` output and the exact interfaces defined above; UE scripts call the same resolved task and rollback JSON contracts.
- Repository boundary: all Python/config changes stay inside the inner submodule; only UE External Actor packages and generated UE assets can change in the outer repository. No cross-repository file copying is planned.
