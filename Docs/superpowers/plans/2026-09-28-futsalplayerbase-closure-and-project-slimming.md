# FutsalPlayerBase Closure And Project Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the active FutsalPlayerBase dependency closure into one conventionally named folder, replace canonical sequence names, remove the obsolete long test sequence, and safely slim the rest of the UE project without touching UE mannequin templates or shared visual assets.

**Architecture:** Build a dependency manifest from Asset Registry plus repository text references. Migrate only project-owned closure assets through UE AssetTools, validate every dependent Blueprint/Sequence/configuration after each migration group, then delete only assets proven to have no protected or runtime references. Treat mannequin content and shared scene/Pose assets as explicit protected roots.

**Tech Stack:** Unreal Engine 5.8 Editor, Unreal MCP AssetTools/Sequencer/FutsalMOTTools, Python 3.9 `uv` environment, Git.

**Spec:** `Docs/superpowers/specs/2026-09-28-futsalplayerbase-closure-and-project-slimming-design.md`

## Global Constraints

- All UE asset moves, renames, saves, and deletes use Unreal Editor APIs; never manipulate `.uasset` files directly.
- Preserve `/Game/Characters/Mannequins/**` exactly; do not delete, move, copy, or rename it.
- Preserve current character visual assets, formal map, ball/court assets, Pose/MRQ assets with active references, and all production Sequence assets except the explicitly approved `LS_Cam_Long_30s` deletion.
- Existing uncommitted changes from the previous Sequence replacement remain in scope and must not be reverted.
- Keep the Python submodule boundary; inner Python changes are committed separately from outer UE asset changes.
- Stop on unresolved references, compile errors, dirty-state expansion, or unexpected changes to protected assets.

---

### Task 1: Load the Project and Capture Closure Baseline

**Files:**
- Read: `/Game/FutsalMOT/Maps/L_FutsalCourt`
- Read: active FutsalPlayerBase roots listed in the spec.
- Create temporary manifest only under `Saved/AnimationCleanup/`; do not commit it.

- [ ] Verify outer and inner Git status, preserve existing changes, and confirm the target branch/worktree.
- [ ] Load `/Game/FutsalMOT/Maps/L_FutsalCourt` in the Editor; stop if the world is unavailable.
- [ ] Record dirty state for the map, current character blueprints/AnimBP, all canonical sequences, protected mannequin roots, and migration backups.
- [ ] Recursively query Asset Registry dependencies/referencers for the character, controller, AnimBP, input assets, mesh, skeleton, physics, materials, textures, BlendSpace, animation sequences, FootIK, and interface.
- [ ] Scan Python/config/C++ text for all old and new Sequence paths, character paths, input paths, and legacy names.
- [ ] Produce a baseline manifest containing exact source path, target path, class, dependency list, referencer list, and protection category.

### Task 2: Migrate Project-Owned Character Closure

**Files:**
- Move/rename through UE AssetTools: `/Game/FutsalMOT/Input/Actions/IA_Futsal_*`.
- Move/rename through UE AssetTools: `/Game/FutsalMOT/Input/Mappings/IMC_Futsal_*`.
- Move/rename through UE AssetTools: `/Game/FutsalMOT/Input/Touch/BPI_FutsalTouchInterface`.
- Move/rename through UE AssetTools only where the manifest proves they are project-owned closure assets.

- [ ] Create target `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/Input/` if absent.
- [ ] Move each input action and mapping to the target folder using names `IA_FutsalPlayerBase_*` and `IMC_FutsalPlayerBase_*`; rename Touch Interface to `BPI_FutsalPlayerBaseTouchInterface`.
- [ ] Move any remaining project-owned closure asset outside the target folder into its appropriate `Animation`, `Blueprints`, `Mesh`, `Skeleton`, `Materials`, or `Textures` subfolder; exclude Mannequins and shared assets.
- [ ] Save only moved/renamed assets and automatically updated referencers.
- [ ] Re-query all root dependencies and assert no old input path or old closure path remains in active Blueprint/AnimBP references.

### Task 3: Replace Sequence Names and Remove Long Test Sequence

**Files:**
- Rename through UE AssetTools: `LS_Cam_02_Canonical` -> `LS_Cam_02`.
- Rename through UE AssetTools: `LS_Cam_03_Canonical` -> `LS_Cam_03`.
- Rename through UE AssetTools: `LS_Cam_04_Canonical` -> `LS_Cam_04`.
- Rename through UE AssetTools: `LS_Cam_Main_Canonical` -> `LS_Cam_Main`.
- Rename through UE AssetTools: `LS_Cam_P01_Canonical` -> `LS_Cam_P01`.
- Delete through UE AssetTools: `/Game/FutsalMOT/Sequences/LS_Cam_Long_30s`.

- [ ] Confirm each target formal Sequence path is absent before rename and each source canonical Sequence is loaded and clean.
- [ ] Rename one Sequence at a time and verify its binding count, ten canonical player classes, camera class, Camera Cut, playback range/rate, and camera tracks remain unchanged.
- [ ] Update all production JSON configs and test expectations from `_Canonical` names to formal names; retain only intentional historical strings in non-runtime records.
- [ ] Run text search and Asset Registry referencer search for `LS_Cam_*_Canonical` and `LS_Cam_Long_30s`; stop on any runtime reference.
- [ ] Delete `LS_Cam_Long_30s` only after confirming no config, code, map, or Sequence references it.

### Task 4: Generate and Review Whole-Project Slimming Candidates

**Files:**
- Read all `/Game` Asset Registry assets and referencers.
- Read repository text/config references.
- No deletes until the candidate report passes review.

- [ ] Enumerate assets with zero project referencers, but exclude all mannequin assets, engine/plugin assets, current closure assets, formal map/Sequence/court/ball/Pose roots, migration backups, and assets referenced through configuration/text paths.
- [ ] Group candidates by project-owned legacy/test/intermediate/archive directories and identify duplicate or superseded assets by class/name/reference graph.
- [ ] For every candidate, check hard, soft, searchable-name, management and text/config references.
- [ ] Produce a deletion table: exact path, asset class, reason, referencers, protected dependencies, and deletion decision.
- [ ] Stop and report any candidate whose safety cannot be established; do not use “zero referencers” alone as deletion proof.

### Task 5: Delete Approved Project-Only Waste

**Files:**
- Delete only exact paths approved by Task 4 through UE AssetTools.

- [ ] Recheck every candidate path exists and still has no protected/runtime referencers.
- [ ] Delete one asset at a time; do not delete folders wholesale.
- [ ] After each group, query Asset Registry for deleted paths and root dependencies.
- [ ] Assert no protected Mannequins, current character assets, visual assets, map, production sequences, or active Pose/MRQ assets were deleted.

### Task 6: Validate Runtime and Repository Boundaries

**Files:**
- Validate canonical character/AnimBP, formal sequences, map, and updated inner configs/tests.

- [ ] Compile `BP_FutsalPlayerBase` and `ABP_FutsalPlayerBase`; inspect `LogBlueprint` for new errors/warnings.
- [ ] Load formal `LS_Cam_01`, `LS_Cam_02`, `LS_Cam_03`, `LS_Cam_04`, `LS_Cam_Main`, and `LS_Cam_P01`; verify ten canonical player bindings and unchanged camera parameters.
- [ ] Run inner Python `uv` tests with ignored `.futsalmot/local.json` temporarily removed, then restore it unchanged.
- [ ] Run `task validate` and `task resolve` for the updated multi-camera smoke configuration.
- [ ] Search for old closure paths, `_Canonical`, `LS_Cam_Long_30s`, legacy animation names, and deleted asset paths.
- [ ] Run `git diff --check`, inspect outer asset diff and inner Python diff separately, and confirm no generated files or inner Python files entered the outer index.
- [ ] Do not commit or push until final diff review and user confirmation.

## Stop Conditions

- Current level cannot be loaded or Asset Registry does not resolve roots.
- Any move/rename causes active asset load failure or references outside the expected update set.
- Any mannequin, visual, map, production Sequence, or active Pose/MRQ asset is dirty or changed unexpectedly.
- Any old path remains in runtime config/code after migration.
- Any delete candidate has unresolved hard/soft/text/config/reference evidence.
- Python tests, task validation, Blueprint compile, or Sequence verification fails.
