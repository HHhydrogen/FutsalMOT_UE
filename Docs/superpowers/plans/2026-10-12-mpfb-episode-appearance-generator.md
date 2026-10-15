# MPFB Episode Appearance Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a deterministic appearance manifest for each GRF episode and apply it temporarily in UE to produce consistent RGB, Instance-ID Mask, and Runtime Pose outputs using Player_003–009.

**Architecture:** P1 task export writes an episode manifest bound to the exact `frames.jsonl` bytes, using versioned SHA-256 appearance namespaces independent of GRF randomness. UE validates and transactionally applies the manifest to the ten mapped actors, then restores their prior visual state after synchronous work or the final asynchronous MRQ job. Audit requires a matching restored application report when seeded appearance is enabled.

**Tech Stack:** Python 3.9, Pydantic, pytest, GRF task workflow, JSON/JSONL, Unreal Engine 5.8 Editor Python, Unreal MCP, Skeletal Mesh components, Dynamic Material Instances, Movie Render Queue.

**Spec:** `Docs/MPFB_APPEARANCE_GENERATOR_DESIGN.md`

## Global Constraints

- P1 runs only in the Python 3.9 `uv` environment; P2 UE scripts run only in the real Unreal Editor Python environment.
- JSON/JSONL is the only interface between P1 and P2.
- Existing GRF `futsalmot_seed_v1` derivation, actor mapping, track IDs, mask IDs, shared Skeleton, and retarget contracts remain unchanged.
- Appearance policy is exactly `futsalmot_appearance_v1`; seed derivation and candidate ranking must match the spec byte-for-byte.
- Player models are Player_003–009 sampled with replacement; skins are the nine imported male skin textures sampled with replacement; four different kit Set IDs are selected from Set_01–05 and assigned in the fixed left-outfield, right-outfield, left-goalkeeper, right-goalkeeper order.
- Goalkeeper identity comes from `meta.entities.is_goalkeeper`; never infer it from entity index.
- UE must preflight all ten players before mutation. Any preflight or partial-apply failure blocks downstream Sequence/MRQ work.
- Randomized External Actor packages must not be saved. Apply/restore must preserve initially clean package state; dirty External Actors fail preflight.
- MRQ is asynchronous; do not block the Editor main thread with sleep/wait. Restore only after all jobs settle.
- Keep separate inner and outer repository boundaries. Do not run `git add -A`, commit, or push without explicit user confirmation.
- Preserve the existing untracked design document and this plan; do not remove or rewrite them.
- New inner-repository code comments, docstrings, and technical docs use Simplified Chinese.

## File Map

### Inner Python submodule: `Content/FutsalMOT/code/`

- Create `src/grf_ue_bridge/appearance.py`: pure seed derivation, catalog validation, deterministic selection, manifest construction, canonical fingerprints, atomic writing, and manifest validation helpers. It must not import Unreal.
- Modify `src/grf_ue_bridge/config/models.py`: define strict appearance catalog/task models and reject simultaneous seeded `ue.appearance` and legacy `ue.player_visuals` configuration.
- Modify `src/grf_ue_bridge/config/resolver.py`: validate appearance configuration and preserve the resolved appearance catalog for UE without changing current path-resolution behavior.
- Modify `src/grf_ue_bridge/workflows/task_export.py`: after trajectory export/provenance, read the emitted metadata, build the manifest, and atomically write `provenance/appearance.json` when seeded appearance is configured.
- Modify `src/grf_ue_bridge/cli.py`: make export resume detection require a valid appearance manifest when the task enables seeded appearance.
- Modify `src/grf_ue_bridge/dataset_manifest.py`: include appearance provenance in metadata/final/all checksum profiles.
- Modify `src/grf_ue_bridge/workflows/task_audit.py`: validate the appearance application report against manifest fingerprint and trajectory hash when appearance is enabled.
- Create `ue/episode_appearance.py`: pure manifest/catalog checks plus UE-only preflight, transaction apply, restore, and portable application-report operations. Import `unreal` only inside UE functions.
- Modify `ue/run_task.py`: validate/apply seeded appearance in supported modes, restore synchronously on all errors, and transfer restoration ownership to the MRQ completion callback for asynchronous render modes.
- Modify `ue/render_episode.py`: accept an explicit completion callback and invoke it exactly once for success, failure, cancellation, submission failure, disabled render, and no-job paths; keep the callback alive until completion.
- Create `tests/test_appearance.py`: pure unit tests for deterministic seeds, sampling, manifest construction, validation, hashing, and atomic output.
- Modify `tests/test_task_config.py`, `tests/test_task_resolver.py`, `tests/test_portable_config.py`, `tests/test_task_cli.py`, `tests/test_player_visuals.py`, and `tests/test_validation_contract.py` only for the specific config/export/run-task/audit compatibility boundaries they cover.
- Modify `docs/DATA_CONTRACT.md` and `docs/VALIDATION_AND_LIMITATIONS.md` in Simplified Chinese to document the manifest and validation rules.
- Create `configs/player_appearance_smoke_10frames_1cam.json`: a separate short episode task with the complete asset catalog and appearance enabled. Do not overwrite existing tasks or outputs.

### Outer UE repository: `D:\projects\FutsalMOT_UEDataset`

- Inspect `/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_Body`, the seven material slot semantics on Player_003–009, the nine skin Texture2D assets, five kit material pairs, and formal map dirty/save behavior through Unreal MCP.
- Modify `M_MPFB_Body` only if inspection proves there is no usable skin texture parameter. Preserve the existing texture as the default value and validate the graph and rendered result before proceeding.
- Do not save randomized External Actor changes. Runtime rollback files remain in the ignored `.futsalmot/runtime/<task_id>/` directory. Episode manifests/reports contain portable asset and actor identifiers, not local disk paths.
- Do not update the outer submodule gitlink unless the inner repository has an explicitly authorized, pushed commit; this plan does not include commits or pushes.

## Interfaces

The P1 pure module must expose these stable interfaces:

```python
def derive_appearance_seeds(ue_visual_seed: int) -> dict[str, int]: ...

def catalog_fingerprint(catalog: dict) -> str: ...

def build_appearance_manifest(
    meta: dict,
    frames_path: Path,
    catalog: dict,
) -> dict: ...

def validate_appearance_manifest(
    manifest: dict,
    *,
    meta: dict,
    frames_path: Path,
    catalog: dict,
) -> list[str]: ...

def write_appearance_manifest(episode_dir: Path, manifest: dict) -> Path: ...
```

`build_appearance_manifest` returns a JSON-compatible dict with `schema="futsalmot_episode_appearance"`, `version=1`, episode/seed/hash/catalog fields, `kit_classes`, ten `entities` records, and a canonical `fingerprint`. Entity records use `entity_id`, `team`, `is_goalkeeper`, `kit_class`, `player_id`, `mesh`, `skin_id`, `skin_texture`, `kit_set_id`, `jersey_material`, and `shorts_material`.

The UE runtime module must expose:

```python
def validate_appearance_inputs(manifest: dict, catalog: dict, meta: dict,
                                frames_path: Path) -> list[str]: ...

def preflight_episode_appearance(manifest: dict, catalog: dict,
                                 mapping: dict) -> dict: ...

def apply_episode_appearance(manifest: dict, catalog: dict, mapping: dict,
                             rollback_path: str, report_path: str) -> dict: ...

def restore_episode_appearance(rollback_path: str, report_path: str,
                               final_status: str) -> dict: ...
```

UE apply returns a JSON-compatible transaction handle with `ok`, `errors`, `warnings`, actor details, and a transaction ID. `render_sequences(..., on_complete=None)` invokes `on_complete(render_result)` exactly once after synchronous no-render/error paths or after asynchronous MRQ finalization. Existing callers without the callback retain existing behavior.

## Execution Tasks

### Task 1: Verify UE temporary-appearance feasibility

**Files:**
- No committed files. Use a temporary runtime diagnostic file only if needed; remove it after successful validation.

**Interfaces:**
- Consumes: formal map `/Game/FutsalMOT/Maps/L_FutsalCourt`, Player_003 mesh, `M_MPFB_Body`, existing MRQ workflow.
- Produces: verified report of Body texture parameter, semantic slots on all seven meshes, External Actor dirty-state behavior, and whether MRQ PIE sees an unsaved temporary Mesh/material override without saving randomized actors.

- [ ] **Step 1: Read-only inspect the current editor state and assets.** Use Unreal MCP native asset/scene queries first, then a small `FutsalMOTTools.run_python_code` diagnostic for exact material expressions/parameters and each mesh's `materials` slot names. Confirm current level and all ten actors. Do not change or save assets.
- [ ] **Step 2: Confirm all ten External Actor packages are clean.** Read package dirty state before any probe. If any is dirty, stop this task and report the actor/package; do not overwrite or clear user state.
- [ ] **Step 3: Probe a temporary unsaved visual override and short MRQ on an isolated smoke map or a reversible runtime-only test actor.** Snapshot component mesh/material state first, apply an existing MPFB mesh or a temporary material override, submit a one-frame MRQ through the existing executor, and restore in a `finally`/finished callback. Do not call save-level/save-asset. Verify MRQ output actually contains the override and the formal packages remain clean.
- [ ] **Step 4: Record the observed Body parameter name, exact material slot names/categories for Player_003–009, and MRQ unsaved-state result.** Query current UE Output Log categories after any error. If unsaved state is not visible to MRQ, stop before implementation and return to the user with the specific blocker; do not implement a save-randomize-restore workaround without renewed approval.
- [ ] **Step 5: If the Body material has no texture parameter, extend only the existing base-color texture connection with a parameter whose default is the current skin texture.** Use UE Editor APIs only after graph inspection; preserve all other nodes/connections. Compile/save the material asset, reload it, verify the parameter/default by readback, and render a short visual check before continuing. If the graph cannot be modified and verified safely, stop with the material path and exact limitation.

### Task 2: Add deterministic appearance core with failing tests

**Files:**
- Create: `Content/FutsalMOT/code/tests/test_appearance.py`
- Create: `Content/FutsalMOT/code/src/grf_ue_bridge/appearance.py`

**Interfaces:**
- Consumes: catalog dict, GRF `meta.json` dict, and `frames.jsonl` path.
- Produces: the five pure interfaces declared above. No Unreal import or global RNG use.

- [ ] **Step 1: Write seed-derivation tests against the approved byte protocol.** Test each namespace seed equals the first four SHA-256 bytes (unsigned big-endian) of `futsalmot_appearance_v1:<ue_visual_seed>:<namespace>`, masked by `0x7fffffff`; assert model/skin/kit namespace seeds are independently computed and stable across a subprocess.
- [ ] **Step 2: Write deterministic manifest tests using a fixture with ten entities and non-index goalkeeper roles.** Assert model and skin assignments are stable, repeats are allowed, kit Set IDs are distinct, Jersey/Shorts Set IDs match, teams and goalkeeper kit classes are correct, and the manifest trajectory hash is SHA-256 of exact file bytes.
- [ ] **Step 3: Write invalid-input tests.** Cover missing/duplicate player IDs, missing or multiple goalkeeper per team, wrong team metadata, invalid candidate counts/duplicate catalog IDs, malformed `/Game/` paths, unsupported policy, changed trajectory bytes, and bad manifest fingerprint.
- [ ] **Step 4: Run the focused test file and confirm expected failures.** Run `uv run pytest tests/test_appearance.py -q` from `Content/FutsalMOT/code`; expected failures are missing appearance functions.
- [ ] **Step 5: Implement canonical catalog normalization and fingerprinting.** Canonical JSON uses `ensure_ascii=False`, `sort_keys=True`, and separators `(',', ':')`; encode as UTF-8 before SHA-256. Validate exact catalog counts: 7 player profiles with IDs 3–9, 9 unique skins, and 5 unique kit Set IDs 01–05.
- [ ] **Step 6: Implement policy seeds and stable candidate ranking.** Use the exact strings in the spec. Candidate rank is `(digest_bytes, candidate_id)`; kit ranking uses entity ID `kit`; assign the first four kits in the fixed order.
- [ ] **Step 7: Implement manifest build, validation, fingerprint, and atomic write.** Use same-directory temporary file, UTF-8 JSON with stable key order/indentation plus one trailing newline, flush/close, then `Path.replace`. Do not leave a partial final file if validation/write fails.
- [ ] **Step 8: Run focused tests and then existing seed tests.** Run `uv run pytest tests/test_appearance.py tests/test_seeds.py -q`; expected: PASS and no changes to `futsalmot_seed_v1` behavior.

### Task 3: Integrate appearance catalog into task config and resolver

**Files:**
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/config/models.py`
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/config/resolver.py`
- Modify: `Content/FutsalMOT/code/tests/test_task_config.py`
- Modify: `Content/FutsalMOT/code/tests/test_task_resolver.py`

**Interfaces:**
- Consumes: optional `ue.appearance` catalog.
- Produces: parsed `UeProfile.appearance` data preserved as JSON-compatible `resolved.ue_profile["appearance"]`; invalid candidate contracts and simultaneous appearance/static visual configuration are reported by `task validate`.

- [ ] **Step 1: Add config tests for a complete valid catalog and legacy config.** Assert legacy tasks without `appearance` still parse; valid appearance survives resolve; `appearance` plus non-empty `player_visuals` fails; missing candidates, duplicate IDs, wrong Set IDs, or malformed paths fail with a clear validation message.
- [ ] **Step 2: Run only the new tests and confirm failure.** Run `uv run pytest tests/test_task_config.py -k appearance tests/test_task_resolver.py -k appearance -q`; expected: new appearance tests fail before model changes.
- [ ] **Step 3: Add strict nested Pydantic models.** Use model validators to require all 7 model IDs, 9 skin IDs, 5 kit IDs (`01`–`05`), unique IDs, non-empty `/Game/` paths, policy `futsalmot_appearance_v1`, catalog ID, and a non-empty verified Body texture parameter. Keep existing `UeProfile` `extra="allow"` compatibility while explicitly typing `appearance`.
- [ ] **Step 4: Preserve the validated catalog in resolved UE profile.** Confirm `model_dump()` retains all appearance catalog fields without changing `ue_profile` legacy keys or absolute path resolution.
- [ ] **Step 5: Run focused config/resolver tests and the existing suites.** Run `uv run pytest tests/test_task_config.py tests/test_task_resolver.py -q`; expected: PASS.

### Task 4: Generate appearance manifest during task export and support resume

**Files:**
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/workflows/task_export.py`
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/cli.py`
- Modify: `Content/FutsalMOT/code/tests/test_portable_config.py`
- Modify: `Content/FutsalMOT/code/tests/test_task_cli.py`

**Interfaces:**
- Consumes: resolved export profile, `resolved.ue_profile["appearance"]`, emitted `meta.json`, and emitted `frames.jsonl`.
- Produces: `provenance/appearance.json`; when appearance is configured, export returns success only after a valid manifest exists. Pipeline resume treats missing/invalid appearance manifest as retry.

- [ ] **Step 1: Add a task-export integration test with a fake GRF/exporter that writes valid meta and frames files.** Assert the manifest is created after normal task provenance and its episode/root/catalog/trajectory hashes match the exported files.
- [ ] **Step 2: Add export failure tests for bad roster metadata and a corrupted/missing `frames.jsonl`.** Assert export fails, no valid appearance manifest is left, and existing GRF provenance behavior without appearance is unchanged.
- [ ] **Step 3: Run the new export tests and confirm failure.** Run `uv run pytest tests/test_portable_config.py -k appearance tests/test_task_cli.py -k appearance -q`; expected: appearance workflow tests fail before integration.
- [ ] **Step 4: Call the pure generator after `export_episode` and `_write_provenance`.** Only when `resolved.ue_profile.appearance` exists, read the exact `meta.json`, call `build_appearance_manifest`, then `write_appearance_manifest`. Do not touch global random state or alter exporter seed parameters.
- [ ] **Step 5: Update export resume detection.** For a task with seeded appearance, `_step_is_complete(..., "export")` must validate appearance schema, fingerprint, catalog fingerprint, and current frame hash in addition to `meta.json` and `frames.jsonl`; a missing/stale manifest returns `retry`.
- [ ] **Step 6: Run focused export/CLI tests and the default P1 suite.** Run `uv run pytest tests/test_portable_config.py tests/test_task_cli.py -q`, then `uv run pytest`; expected: PASS, GRF integration remains skipped by default.

### Task 5: Include appearance artifacts in dataset checksums and audit

**Files:**
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/dataset_manifest.py`
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/workflows/task_audit.py`
- Modify: `Content/FutsalMOT/code/tests/test_validation_contract.py`
- Modify: `Content/FutsalMOT/code/tests/test_dataset_manifest.py`

**Interfaces:**
- Consumes: `provenance/appearance.json`, `provenance/appearance_application.json`, task appearance enabled state, and current `frames.jsonl`.
- Produces: metadata/final/all checksum coverage for appearance provenance and an audit check that requires a matching `restored` application report only for tasks with seeded appearance enabled.

- [ ] **Step 1: Write manifest-profile tests.** Assert `provenance/appearance.json` is included in metadata, final, and all profiles when present, and absent files do not create phantom checksum entries.
- [ ] **Step 2: Write audit tests for disabled, valid, stale, failed, and unrestored appearance reports.** Legacy tasks with no appearance remain skipped/passing; seeded appearance requires schema/version, matching manifest fingerprint, matching trajectory SHA-256, terminal render result when render is required, and state `restored`.
- [ ] **Step 3: Run the focused tests and confirm failure.** Run `uv run pytest tests/test_dataset_manifest.py tests/test_validation_contract.py -k appearance -q`; expected: new assertions fail before audit/checksum changes.
- [ ] **Step 4: Add the manifest to `_PROVENANCE_FILES` and implement a dedicated appearance audit check.** Do not infer requirement from residual files; use resolved task appearance config. Keep optional/skipped semantics for legacy tasks.
- [ ] **Step 5: Run focused audit/manifest suites and the full default P1 suite.** Run `uv run pytest tests/test_dataset_manifest.py tests/test_validation_contract.py -q`, then `uv run pytest`; expected: PASS.

### Task 6: Add pure UE manifest/application-report contracts

**Files:**
- Create: `Content/FutsalMOT/code/ue/episode_appearance.py`
- Create: or modify `Content/FutsalMOT/code/tests/test_episode_appearance.py`
- Modify: `Content/FutsalMOT/code/tests/test_player_visuals.py` only if shared JSON/report helpers are reused.

**Interfaces:**
- Consumes: validated P1 manifest, task catalog, `meta.json`, `frames.jsonl`, actor mapping.
- Produces: pure manifest validation, report serialization/atomic-write helpers, and lazy Unreal adapter functions from the Interfaces section.

- [ ] **Step 1: Add tests for P2-side manifest/catalog/hash validation without importing `unreal`.** Validate valid input and reject missing manifest, stale frame hash, catalog mismatch, entity mismatch, and invalid asset paths.
- [ ] **Step 2: Add tests for application report state transitions.** Permit `not_started -> preflight_failed`, `not_started -> applied -> rendering -> restored`, and failed terminal states; reject `restored` before every actor restore or with an MRQ job pending. Verify portable report fields contain no filesystem paths.
- [ ] **Step 3: Run the new tests and confirm failure.** Run `uv run pytest tests/test_episode_appearance.py -q`; expected: missing module/helpers.
- [ ] **Step 4: Implement pure validators and atomic application-report serialization.** Keep `unreal` imports inside UE-only functions. The rollback snapshot is machine-local under `.futsalmot/runtime/<task_id>/appearance-rollback.json`; never serialize that local path into episode provenance.
- [ ] **Step 5: Run focused tests and Python 3.9 compilation.** Run `uv run pytest tests/test_episode_appearance.py -q` and `uv run python -m compileall -q ue/episode_appearance.py`; expected: PASS without importing Unreal.

### Task 7: Implement UE preflight and reversible appearance application

**Files:**
- Modify: `Content/FutsalMOT/code/ue/episode_appearance.py`
- Modify: `Content/FutsalMOT/code/tests/test_episode_appearance.py` for pure snapshots/state helpers.
- Possible outer asset modification: `/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_Body`, only under Task 1's verified material-interface result.

**Interfaces:**
- Consumes: selected entity assignment, exact asset catalog, existing actor mapping, verified slot names and Body parameter from Task 1.
- Produces: all-ten-actor preflight result; transactional apply/restore; local rollback snapshot; portable report. No save of randomized External Actors.

- [ ] **Step 1: Implement read-only preflight in UE Python.** Check formal map, unique actor labels, clean actor packages, exact 10-entity set, asset classes, shared Skeleton/AnimBP compatibility, and exact verified material slot names. Load every asset before changing any actor.
- [ ] **Step 2: Run preflight through `FutsalMOTTools.run_python_file` in the current Editor.** Inspect `success/result/log`; if it fails, query relevant UE logs, correct only verified compatibility issues, and retry once per the project MCP rules.
- [ ] **Step 3: Implement a complete snapshot before mutation.** Include visual mesh, AnimBP, attachment/relative transform, per-slot material overrides, leader-pose and visibility/render flags if the adapter changes them, and original package dirty state. Snapshot all ten before applying any entity.
- [ ] **Step 4: Implement transactional application.** Apply selected mesh and shared AnimBP to the visible MPFB visual component; preserve private hair and non-target slots according to the verified semantic slot map; create per-actor Body MID and set the selected skin texture; apply selected Jersey/Shorts materials. Read back effective asset paths/slot values after each assignment.
- [ ] **Step 5: Implement all-roster rollback on any error.** Restore every actor from the original snapshot, verify every restored field, delete/clear only generated transient material instances, preserve package clean state, and fail if rollback cannot be proven.
- [ ] **Step 6: Execute a short apply/readback/restore validation through UE MCP.** Do not submit MRQ yet. Confirm all ten assignments and exact restored state, no package became dirty, and no actor asset save operation occurred. Query UE logs after any failure.

### Task 8: Integrate appearance transaction with `run_task.py`

**Files:**
- Modify: `Content/FutsalMOT/code/ue/run_task.py`
- Modify: `Content/FutsalMOT/code/ue/episode_appearance.py`
- Modify: `Content/FutsalMOT/code/tests/test_player_visuals.py` or create `tests/test_run_task_appearance.py`.

**Interfaces:**
- Consumes: resolved `ue_profile.appearance`, episode manifest, task ID, actor mapping, run mode.
- Produces: apply before any appearance-dependent sequence/annotation/render work; synchronous restoration for `sequence`/`annotations` and pre-MRQ errors; callback ownership transfer for `full`/`render`; no reapply in `pose-finalize`.

- [ ] **Step 1: Add source-level or factored pure orchestration tests.** Verify legacy no-appearance tasks retain behavior; `pose-finalize` skips appearance application; static `player_visuals` plus appearance is rejected; `sequence` and `annotations` restore on return/exception; `full`/`render` pass a completion callback.
- [ ] **Step 2: Add `episode_appearance` to the explicit UE module reload list.** Follow existing module cache handling and do not move UE code into the P1 environment.
- [ ] **Step 3: Validate manifest and run all-ten preflight before mutating.** The check must happen before `create_sequence`, `export_annotations`, pose prep, or render submission.
- [ ] **Step 4: Wrap synchronous mode work in guaranteed restore.** For `sequence` and `annotations`, use `try/finally`. For `full`/`render`, retain the transaction only after MRQ has successfully taken callback ownership; otherwise restore in the synchronous exception/no-render path.
- [ ] **Step 5: Write `prepared`/`applied` report before downstream work.** Include exact portable manifest fingerprint, trajectory hash, actor and asset/slot results, and no local machine paths. Runtime rollback path stays under ignored `.futsalmot/runtime/<task_id>/`.
- [ ] **Step 6: Run P1 tests that parse source contracts and compile UE Python files.** Run `uv run pytest tests/test_run_task_appearance.py tests/test_player_visuals.py -q` and `uv run python -m compileall -q ue/run_task.py ue/episode_appearance.py`; expected: PASS.

### Task 9: Connect transaction restore to asynchronous MRQ and remove unsafe save coupling

**Files:**
- Modify: `Content/FutsalMOT/code/ue/render_episode.py`
- Modify: `Content/FutsalMOT/code/ue/run_task.py`
- Modify: `Content/FutsalMOT/code/ue/episode_appearance.py`
- Modify: `Content/FutsalMOT/code/tests/test_render_episode.py` and `tests/test_run_task_appearance.py`.

**Interfaces:**
- `render_sequences(..., on_complete=None)` takes a callable receiving a JSON-compatible final render result.
- `_AsyncRenderPipeline` retains and invokes it exactly once after render summary finalization for success, executor error, cancellation, submission failure, and watchdog completion.
- Synchronous disabled/no-job/error branches invoke the callback before returning or raise only after guaranteed callback restoration.

- [ ] **Step 1: Add render callback tests using a fake pipeline/callback.** Verify each terminal route invokes once, duplicate delegate/watchdog signals remain idempotent, and old callers without callbacks behave unchanged.
- [ ] **Step 2: Run focused render tests and confirm failure.** Run `uv run pytest tests/test_render_episode.py -k callback -q`; expected: callback behavior is absent.
- [ ] **Step 3: Add optional completion callback storage to `_AsyncRenderPipeline`.** Invoke it from the single guarded `_finalize` path after `render_summary.json` is written, passing final status and camera results. Catch/report callback exceptions but leave application report in `restore_failed` when restore fails.
- [ ] **Step 4: Cover synchronous early returns and setup exceptions.** If render is disabled or no job exists, finalize the appearance transaction synchronously; if queue/executor/job setup throws before submit, restore immediately and record failed status.
- [ ] **Step 5: Remove the current save-randomized-actor risk.** Trace `_assign_custom_stencil`, first-frame spawn baking, and `_save_current_level()` calls. Rework ordering/path only after Task 1 proved MRQ reads the temporary appearance without saving it. Keep necessary frame/stencil persistence only when it serializes baseline visuals; verify the saved state excludes selected random mesh/material overrides. If this cannot be established without saving randomized External Actors, stop and return to the user instead of weakening the approved boundary.
- [ ] **Step 6: Write final application report only after actor restoration and all jobs terminal.** Report `restored` plus per-camera statuses on successful restoration; report `restore_failed` if any actor could not be proven restored; do not delete local rollback snapshot until restored is verified.
- [ ] **Step 7: Run focused render tests, then execute one short UE MCP MRQ success and one controlled failure/cancel case.** Confirm Editor continues ticking, report is terminal, all actors match baseline, External Actor packages remain clean, and render_summary is unchanged in meaning.

### Task 10: Add appearance audit requirements and recovery behavior

**Files:**
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/workflows/task_audit.py`
- Modify: `Content/FutsalMOT/code/src/grf_ue_bridge/workflows/artifact_cleanup.py` only if report validation is needed before cleanup.
- Modify: `Content/FutsalMOT/code/tests/test_validation_contract.py`

**Interfaces:**
- Consumes: enabled appearance config, `provenance/appearance.json`, `provenance/appearance_application.json`, current trajectory hash, and existing render summary.
- Produces: required passed/failed appearance audit check with legacy skip semantics; stale prepared report blocks new application and cleanup.

- [ ] **Step 1: Test task-audit combinations.** Appearance disabled yields `skipped`; seeded appearance without manifest fails; stale manifest/report fails; report states `applied`/`rendering`/`restore_failed` fail; matching `restored` report with all required cameras succeeds.
- [ ] **Step 2: Implement report/manifest/hash cross-checks.** Do not infer appearance requirement from files. Use task configuration, and keep the audit output in the existing canonical `checks`/errors/warnings shape.
- [ ] **Step 3: Block re-apply when a stale local `prepared` report/rollback exists.** Verify current actor state against the snapshot; recover only when a verified restore is possible. Never overwrite unresolved recovery evidence.
- [ ] **Step 4: Run focused audit, cleanup, and full default P1 tests.** Run `uv run pytest tests/test_validation_contract.py tests/test_artifact_cleanup.py -q`, then `uv run pytest`; expected: PASS.

### Task 11: Add smoke config and update authoritative inner docs

**Files:**
- Create: `Content/FutsalMOT/code/configs/player_appearance_smoke_10frames_1cam.json`
- Modify: `Content/FutsalMOT/code/docs/DATA_CONTRACT.md`
- Modify: `Content/FutsalMOT/code/docs/VALIDATION_AND_LIMITATIONS.md`
- Modify: `Content/FutsalMOT/code/README.md` if the recommended workflow needs the new flag/contract explained.

**Interfaces:**
- Consumes: verified full appearance catalog and current machine-local path conventions.
- Produces: an explicitly unique short smoke task, documented manifest schema, UE run modes, audit requirements, and current limitations.

- [ ] **Step 1: Create a unique smoke config by copying the closest current valid one without changing existing configs.** Use 10 frames, one camera, a unique task/episode name, seeded appearance, all 7/9/5 catalog entries, and the verified Body texture parameter. Preserve compatible pose/mask/render settings only if short smoke has been verified to support them.
- [ ] **Step 2: Document `provenance/appearance.json` fields and fingerprint/hash definitions in `docs/DATA_CONTRACT.md` in Simplified Chinese.** Include the exact random seed/ranking byte protocol and entity/kit selection rules.
- [ ] **Step 3: Document P1/P2 validation, async MRQ lifecycle, temporary apply/restore, dirty package gate, and known limitations in `docs/VALIDATION_AND_LIMITATIONS.md`.** Clearly distinguish automated tests from actual UE/material/visual validation.
- [ ] **Step 4: Run task validate/resolve and verify the smoke config is machine-compatible.** Run `uv run grf-ue task validate configs/player_appearance_smoke_10frames_1cam.json` and `uv run grf-ue task resolve ...`; expected: PASS on the configured machine, resolved output remains ignored.
- [ ] **Step 5: Run docs/config checks and the complete P1 suite.** Run `uv run pytest`, `git diff --check` in the inner repository, and confirm no generated runtime/output files entered Git status.

### Task 12: End-to-end UE smoke and final repository review

**Files:**
- No additional source files unless a verified failure requires a scoped fix.
- Outputs are under configured dataset root and ignored `.futsalmot/runtime/` only.

**Interfaces:**
- Consumes: smoke task, current formal map/actors/materials, P1 manifest generator, UE application transaction, MRQ callback, audit.
- Produces: one fully audited short episode with reproducible trajectory/appearance, RGB/Mask/Pose alignment as configured, and restored formal map/actor state.

- [ ] **Step 1: Run task validate, export twice into separate unique episode directories with the same seed/catalog, and compare trajectory and appearance fingerprints.** Require byte-identical `frames.jsonl` and assignment fingerprint; never overwrite production data.
- [ ] **Step 2: Run UE `run_task.py --mode full` through `FutsalMOTTools.run_python_file` using the generated resolved-task context.** Verify preflight, all ten applied assignments, async submission, and immediate return.
- [ ] **Step 3: Wait by non-blocking Editor tick/callback and inspect current logs and episode reports.** Require every camera job terminal, application state `restored`, all actors restored to baseline, no External Actor save, and RGB/Mask frame sets aligned.
- [ ] **Step 4: Run `pose-finalize` when enabled, then P1 postprocess/audit/manifest commands.** Require appearance audit and existing RGB/Mask/Pose checks to pass.
- [ ] **Step 5: Capture final status separately in both repositories.** Run `git status --short --branch` and `git diff --check` from outer and inner repositories; confirm generated data, logs, `.venv`, caches, and runtime snapshots are ignored.
- [ ] **Step 6: Review the exact staged-eligible file lists and stop before commit/push.** Do not commit or push until the user explicitly confirms each repository action.

## Self-Review Checklist

- Spec coverage: generation, independent seed namespaces, model/skin/kit sampling, goalkeeper metadata, episode manifest, trajectory binding, UE preflight, DMI/material handling, actor transaction, async MRQ completion, rollback/recovery, audit, and smoke verification each have a task.
- No sample relies on Python `hash()`, module-global RNG, assumed goalkeeper indices, guessed material parameters, or guessed material slot positions.
- Inner Python and outer UE assets remain separate repository ownership boundaries.
- The Task 1 feasibility gate blocks any path requiring randomized External Actor saves; no later task may waive that gate.
- Legacy tasks without appearance retain existing behavior; legacy static `player_visuals` cannot be combined with seeded appearance.
- All async terminal cases restore exactly once; audit does not treat a merely submitted or completed pipeline state as proof of appearance restoration.
- No plan task authorizes automatic commit or push.
