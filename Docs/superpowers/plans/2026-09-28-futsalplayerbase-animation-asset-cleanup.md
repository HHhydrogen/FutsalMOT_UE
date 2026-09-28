# FutsalPlayerBase Animation Asset Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create canonical replacement sequences using the current FutsalPlayerBase class and unchanged camera parameters, adapt Python sequence paths, then remove only the obsolete project-owned character test pipeline while preserving UE mannequin templates, visual assets, and canonical animation assets.

**Architecture:** Use the running UE 5.8 Editor and Unreal Python/Sequencer APIs for all asset reads and writes. Capture a before-state manifest, create five `_Canonical` sequences from the legacy source data, assign current player bindings, compare camera and track semantics, adapt Python paths, and delete old assets only after all checks pass.

**Tech Stack:** Unreal Engine 5.8 Editor, Unreal MCP AssetTools/Sequencer tools, project `FutsalMOTTools.run_python_file` for focused UE Python diagnostics, Git.

**Spec:** `Docs/superpowers/specs/2026-09-28-futsalplayerbase-animation-asset-cleanup-design.md`

## Global Constraints

- Create `/Game/FutsalMOT/Sequences/LS_Cam_02_Canonical`, `LS_Cam_03_Canonical`, `LS_Cam_04_Canonical`, `LS_Cam_Main_Canonical`, and `LS_Cam_P01_Canonical` before deleting the legacy counterparts.
- Preserve all camera parameters, Camera Cut, playback range/rate, ball tracks and player track semantics; delete only the five legacy Sequence assets after replacement validation passes.
- Bind every new player to the same-label actor in `/Game/FutsalMOT/Maps/L_FutsalCourt`, with exact class `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase_C`.
- Never delete or otherwise modify `/Game/Characters/Mannequins/**`, textures, materials, meshes, skeletons, physics assets, canonical FutsalPlayerBase character/animation assets, formal Court, `LS_Cam_01`, `LS_Cam_Long_30s`, or `Intermediate/CppMigrationBackup/**`.
- Perform all `.uasset`/`.umap` changes through Unreal Editor APIs; never delete asset files directly from the filesystem.
- Stop before deletion if binding GUIDs/names/tracks change, target actors do not match, any protected asset becomes dirty, or compile/load/log checks fail.
- Do not commit or push as part of this plan.

---

### Task 1: Capture Baseline and Checkpoint State

**Files:**
- Create temporary diagnostic output under `Saved/AnimationCleanup/` only if needed; do not add it to Git.
- Read: `/Game/FutsalMOT/Maps/L_FutsalCourt`
- Read: `/Game/FutsalMOT/Sequences/LS_Cam_01`, `LS_Cam_02`, `LS_Cam_03`, `LS_Cam_04`, `LS_Cam_Main`, `LS_Cam_P01`, `LS_Cam_Long_30s`

**Interfaces:**
- Input: loaded UE Editor and AssetTools/Sequencer access.
- Output: JSON baseline per sequence: asset path, dirty flag, binding display name, binding GUID, possessed class, track names/types/counts; Court actor labels/classes; protected assets' dirty flags.

- [ ] **Step 1: Verify repository state and active editor level**

Run `git status --short --branch` in the outer repository and `git -C Content/FutsalMOT/code status --short --branch`. Confirm both worktrees are clean, the submodule is at the recorded commit, and current level is `/Game/FutsalMOT/Maps/L_FutsalCourt`. Stop if there are unrelated modifications or a different level is active.

- [ ] **Step 2: Capture every sequence binding and track summary through read-only UE Python**

Use `FutsalMOTTools.run_python_code` for a focused read-only query. Load the seven sequence assets; for each binding capture display name, `get_id()` converted to canonical GUID text if supported, `get_possessed_object_class().get_path_name()`, and each track's class/name plus section count. Capture each sequence `AssetTools.is_dirty` value. Catch errors per binding and per property; do not save assets.

- [ ] **Step 3: Capture target Court player actor identity**

Read `/Game/FutsalMOT/Maps/L_FutsalCourt` and enumerate `Player_L0..Player_L4` and `Player_R0..Player_R4`. Record actor label, object name, generated class path and stable actor identity where available. Require exactly one same-label `BP_FutsalPlayerBase_C` actor for every player binding to be migrated.

- [ ] **Step 4: Establish an API-only dry run for one binding**

Inspect the UE 5.8 Sequencer API exposed by this editor for possessable rebinding. Confirm a supported operation can change the binding's possessed object/class to the target same-label Court actor without deleting/recreating the binding. Do not execute the mutation during this step. If no API can preserve the existing binding identity, stop and report the tooling limitation.

### Task 2: Create Canonical Replacement Sequences

**Files:**
- Create through UE Editor only: five `_Canonical` Sequence assets listed in Global Constraints.
- Read-only source: corresponding five legacy Sequence assets.

**Interfaces:**
- Consumes: Task 1 baseline and exact binding-to-Court-actor label map.
- Produces: five `_Canonical` Sequence assets resolving player bindings to canonical `BP_FutsalPlayerBase_C` actors.

- [ ] **Step 1: Build an explicit replacement list from baseline**

For each legacy sequence, record bindings, track/section counts, camera parameters, Camera Cut and playback settings. Require a unique same-label Court target of exact canonical class for every player name. Do not alter the legacy source assets.

- [ ] **Step 2: Duplicate each legacy sequence to its `_Canonical` path**

Use UE AssetTools duplicate to create the `_Canonical` asset. Confirm the source remains unchanged and the duplicate loads successfully.

- [ ] **Step 3: Replace player bindings in each duplicate**

Assign each player binding in the duplicate to the same-label current Court actor while retaining the copied track data. Keep camera Actor/Camera Cut, ball, playback settings and all non-player tracks unchanged.

- [ ] **Step 4: Save only the five new canonical sequences**

Before saving, confirm only the five new canonical sequences are dirty. Save exactly those five paths. If any source sequence, Court map, protected asset or unrelated asset is dirty, stop and report it.

- [ ] **Step 5: Compare camera parameters and resolve canonical bindings**

Compare source and canonical snapshots. Require identical camera class/name, focal length/FOV, filmback/sensor dimensions, resolution, transform channels/keys, Camera Cut, display/tick rate, playback range, ball tracks and player track semantics. Resolve each canonical player binding to the same-label Court actor and evaluate a representative frame read-only.

### Task 3: Prove the Deletion Set Is Isolated

**Files:**
- Read-only Asset Registry queries for the approved legacy assets.
- No files modified in this task.

**Interfaces:**
- Consumes: successfully created, saved and compared canonical sequences from Task 2.
- Produces: exact remaining referencer report for each approved deletion path.

- [ ] **Step 1: Scan Python and UE references to legacy Sequence paths**

Search the inner repository with `git grep -n` for each legacy Sequence path and basename. Inspect task configs, UE Python, mapping files and generated command logic. Replace runtime/config references that must use canonical Sequence paths.

- [ ] **Step 2: Re-query referencers for all approved legacy paths**

Query AssetTools referencers for the five legacy Sequences, legacy test map, test GameMode, old character, old controller, old AnimBP, old locomotion BlendSpace, old animation interface, and each asset under `/Game/FutsalMOT/Input/**`. Confirm no canonical Sequence, protected asset or retained formal map depends on a deletion candidate.

- [ ] **Step 3: Verify canonical animation dependency closure**

Query dependencies of `ABP_FutsalPlayerBase`, `BP_FutsalPlayerBase`, `L_FutsalCourt`, and all seven retained sequences. Require every current dependency to exist. Confirm the mannequin assets remain present and are not candidates for deletion even when referenced by canonical animation assets.

- [ ] **Step 4: Stop on any unresolved project-owned referencer**

If a deletion candidate is referenced by any retained sequence, Court actor, canonical character/AnimBP, or unknown non-test asset, do not delete it. Report the referencing paths and request a revised cleanup decision.

### Task 4: Delete Approved Legacy Test Pipeline Assets

**Files:**
- Delete through UE AssetTools only: `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test`
- Delete through UE AssetTools only: `/Game/FutsalMOT/Test/GM_FutsalInputTest`
- Delete through UE AssetTools only: `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`
- Delete through UE AssetTools only: `/Game/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase`
- Delete through UE AssetTools only: `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource`
- Delete through UE AssetTools only: `/Game/FutsalMOT/Animation/BS_Futsal_Locomotion`
- Delete through UE AssetTools only: `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource`
- Delete through UE AssetTools only: assets under `/Game/FutsalMOT/Input/**` confirmed to belong exclusively to the retired test pipeline.

**Interfaces:**
- Consumes: Task 3 zero-retained-referencer report.
- Produces: absence of approved legacy assets in Asset Registry with canonical system and protected content untouched.

- [ ] **Step 1: Freeze and verify exact deletion paths**

Construct an exact path list from the approved scope and current Asset Registry. Exclude anything under `/Game/Characters/Mannequins/**`, textures, materials, meshes, skeletons, physics assets, canonical FutsalPlayerBase paths, all sequence/map paths outside the specifically approved test map, and `/Game/FutsalMOT/Intermediate/CppMigrationBackup/**`. Stop if any path does not exactly match the approved scope.

- [ ] **Step 2: Delete only the obsolete test and legacy animation assets**

Call AssetTools.delete one asset path at a time in dependency order: old test map and test GameMode; old character and controller; old AnimBP, locomotion BlendSpace, and interface; then exclusively-owned input assets. Check each return value. Do not delete folders wholesale.

- [ ] **Step 3: Verify deleted paths and protected paths**

Use AssetTools.exists/find_assets to assert all approved paths are absent and canonical animation assets, every `LS_Cam_*` sequence, `L_FutsalCourt`, mannequin assets, and all visual assets are still present. Query referencers for the canonical AnimBP dependencies.

### Task 5: Compile, Revalidate, and Review Git Changes

**Files:**
- Read/compile through UE Editor: canonical `BP_FutsalPlayerBase` and `ABP_FutsalPlayerBase`.
- Inspect outer repository diff; do not modify the inner Python repository.

**Interfaces:**
- Consumes: cleaned Asset Registry and migrated sequences.
- Produces: final validation record and a scoped, uncommitted outer Git diff.

- [ ] **Step 1: Compile canonical character and AnimBP**

Compile `BP_FutsalPlayerBase` and `ABP_FutsalPlayerBase` through supported UE Editor API. Require successful compile results and no new Blueprint errors in `LogBlueprint`.

- [ ] **Step 2: Verify all retained sequence classes and identities**

Re-run the binding manifest for all seven sequences. Require only canonical FutsalPlayerBase class for every player binding, unchanged names/GUIDs/tracks, and unchanged paths. Confirm `L_FutsalCourt` still contains ten canonical player actors and its current level/actor state was not saved or altered by the cleanup.

- [ ] **Step 3: Inspect UE logs**

Read relevant `LogPython`, `LogBlueprint`, `LogSequencer`, and `LogModelContextProtocol` messages. Resolve any cleanup-related error before claiming completion; if a failure is not safely reversible, stop and report exact paths and log evidence.

- [ ] **Step 4: Review Git status and diff**

Run `git status --short --branch`, `git diff --check`, and `git diff --stat` in the outer repository, plus inner `git -C Content/FutsalMOT/code status --short --branch`. Confirm only intended UE asset deletions/sequence changes/redirectors appear, no template or visual assets are deleted, and the inner repository remains unchanged. Do not stage, commit, or push.

## Stop Conditions

- Any target Sequence binding cannot be rebound while preserving its GUID and track data.
- A same-label canonical player actor is missing or non-unique.
- `LS_Cam_01`, `LS_Cam_Long_30s`, `L_FutsalCourt`, or protected assets become dirty or change unexpectedly.
- Any retained asset references a legacy deletion candidate after migration.
- A canonical Blueprint compile fails or UE logs show new migration-related errors.
- The actual Asset Registry paths differ from the exact approved list.
