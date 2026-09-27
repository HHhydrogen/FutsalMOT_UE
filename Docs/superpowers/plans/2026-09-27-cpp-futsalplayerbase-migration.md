# C++ FutsalPlayerBase Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a C++ runtime Character motion contract beneath the existing canonical FutsalPlayerBase Blueprint while preserving trajectory-owned transforms and existing visual animation assets.

**Architecture:** Add one UE 5.8 runtime module and `AFutsalPlayerBase : ACharacter`. Transactionally migrate the two same-named motion variables currently declared by `BP_FutsalPlayerBase` to inherited native properties before reparenting the existing Blueprint. C++ exposes raw CharacterMovement speed and explicit external inputs only; final CharacterMovement/explicit/AutoMotion/canonical-fallback selection remains in the AnimBP.

**Tech Stack:** Unreal Engine 5.8, Unreal Build Tool, Visual Studio 2022 toolchain selected by UE 5.8, Unreal Editor Blueprint/Sequencer APIs, existing Python 3.9 dataset repository and UE Editor Python importer.

**Spec:** `Docs/superpowers/specs/2026-09-27-cpp-futsalplayerbase-design.md`

## Global Constraints

- Trajectory transforms remain the sole authority for Actor world position and facing.
- `ExternalMotionSpeedMps` is animation metadata; C++ must not move the Actor, drive CharacterMovement, or enable root motion from that speed.
- Exact reflected property identifiers are `ExternalMotionActive` (default `false`) and `ExternalMotionSpeedMps` (default `0.0`); do not rename the Boolean to `bExternalMotionActive`. Both are Sequencer `Interp` properties.
- `AFutsalPlayerBase` exposes raw CharacterMovement horizontal speed and raw external properties. It does not own a no-argument final effective-speed getter that includes AnimBP AutoMotion/canonical fallback values.
- AnimBP motion priority is CharacterMovement horizontal speed, active explicit external speed, existing AnimBP auto-transform fallback, then the preserved canonical fallback.
- Preserve the existing `BP_FutsalPlayerBase` asset path, Court actor identity/labels/tags/GUIDs/transforms, Mesh, AnimBP, BlendSpace, animation assets, ControlRig, and Sequence possessables.
- Do not modify `Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset` or delete retired assets.
- Keep the inner Python 3.9 and outer Unreal project repositories separate; commit Python changes in the inner repo first, push inner before updating the outer gitlink.
- Never stage unrelated pre-existing changes. Outer workspace currently has pre-existing asset deletions, untracked external actors, `UNREAL_RIG` modification, and other uncommitted state; preserve them.
- Recovery baseline before migration: outer `6b35696fb82220074bc13bf4d82be1edbc77b135`, inner `9fe6a7c0dd84b0fccb613b5736d5d3f746e927d3`; both commits were pushed and each branch HEAD matched its upstream at preflight.
- Do not commit/push migration implementation until the user explicitly confirms after validation.

---

### Task 1: Reconfirm Recovery Point and Capture Actor/Sequence Identity

**Files:**
- Read only: outer UE repo and inner Python repo Git state.
- Read only: `L_FutsalCourt`, `BP_FutsalPlayerBase`, `ABP_FutsalPlayerBase`, `LS_Cam_01` through Unreal MCP.
- Modify: none.

**Interfaces:**
- Consumes: pushed baseline commits and current UE Editor session.
- Produces: recorded baseline hashes; ten actor labels, GUIDs, transforms, component mesh/AnimClass; current Sequence binding names/classes/GUIDs; protected rig hash.

- [ ] **Step 1: Verify both repository rollback commits and staged state**

Run from outer repo:

```powershell
git rev-parse HEAD
git rev-parse '@{u}'
git diff --cached --name-only
git status --short --branch
```

Run from inner repo:

```powershell
git -C Content/FutsalMOT/code rev-parse HEAD
git -C Content/FutsalMOT/code rev-parse '@{u}'
git -C Content/FutsalMOT/code diff --cached --name-only
git -C Content/FutsalMOT/code status --short --branch
```

Expected baseline HEADs are the values in Global Constraints. If either upstream moved or HEAD differs, stop and inspect history before migration. Record existing unstaged/untracked paths; do not clean, restore, or stage them.

- [ ] **Step 2: Capture the protected asset SHA-256**

Run:

```powershell
Get-FileHash -Algorithm SHA256 Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset
```

Record the hash and do not open/save/resave this asset in the Editor.

- [ ] **Step 3: Capture canonical Court actor and binding identity**

Use read-only `FutsalMOTTools.run_python_code` to enumerate `L_FutsalCourt` actors with labels beginning `Player_`, and record each actor's `get_name()`, label, `actor_guid`, transform, class, SkeletalMeshComponent mesh and AnimClass. Read `/Game/FutsalMOT/Sequences/LS_Cam_01` bindings and record display name, possessed object class, and binding GUID where exposed.

Expected: ten `BP_FutsalPlayerBase_C` players; all canonical meshes/AnimBPs; ten player possessables plus ball/camera. If any actor identity or Sequence metadata cannot be read, stop before reparenting and request a GUI snapshot rather than recreate actors.

### Task 2: Create the Runtime Module and Build Targets

**Files:**
- Create: `Source/FutsalMOT/FutsalMOT.Build.cs`.
- Create: `Source/FutsalMOT/Public/FutsalMOT.h`.
- Create: `Source/FutsalMOT/Private/FutsalMOT.cpp`.
- Create: `Source/FutsalMOT.Target.cs`.
- Create: `Source/FutsalMOTEditor.Target.cs`.
- Modify: `FustalMOT_UEDataset.uproject` module registration only.

**Interfaces:**
- Consumes: UE 5.8 Core, CoreUObject, and Engine; phase one adds no input handling.
- Produces: runtime module `FutsalMOT`, game/editor targets, module startup/shutdown entry points.

- [ ] **Step 1: Add the failing build-structure check**

Add a lightweight repository test or validation script asserting the `.uproject` module entry and expected source/target files exist. Before implementation, run it and confirm failure due to missing `FutsalMOT` module.

- [ ] **Step 2: Add the minimal runtime module and targets**

Create `FutsalMOT.Build.cs` with `PCHUsage = UseExplicitOrSharedPCHs`, `DefaultBuildSettings = BuildSettingsVersion.V5`, `IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8`, and public dependencies `Core`, `CoreUObject`, `Engine`. Create `FutsalMOT.Target.cs` and `FutsalMOTEditor.Target.cs` with `TargetType.Game` and `TargetType.Editor`, respectively; both set `DefaultBuildSettings = BuildSettingsVersion.V5`, `IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8`, and add `FutsalMOT` to `ExtraModuleNames`. Add `.uproject` module object `Name=FutsalMOT`, `Type=Runtime`, `LoadingPhase=Default`. Implement empty `StartupModule()` and `ShutdownModule()` methods.

- [ ] **Step 3: Verify module metadata and compile an empty module**

First verify the installed executables exist at `E:/UE_5.8/Engine/Build/BatchFiles/GenerateProjectFiles.bat` and `E:/UE_5.8/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe`. Run `GenerateProjectFiles.bat -project="D:/projects/FutsalMOT_UEDataset/FustalMOT_UEDataset.uproject" -game -engine -2022`. Then run `UnrealBuildTool.exe FustalMOT_UEDatasetEditor Win64 Development -Project="D:/projects/FutsalMOT_UEDataset/FustalMOT_UEDataset.uproject" -WaitMutex`. Expected: UBT compiles the new module and Editor target; content packages remain untouched.

### Task 3: Implement the Native Character Contract with Unit-Level Tests

**Files:**
- Create: `Source/FutsalMOT/Public/FutsalPlayerBase.h`.
- Create: `Source/FutsalMOT/Private/FutsalPlayerBase.cpp`.
- Create: a focused automation test file under `Source/FutsalMOT/Private/Tests/` for raw speed conversion and trajectory non-mutation.

**Interfaces:**
- Consumes: `ACharacter`, `UCharacterMovementComponent`, UE reflection, module from Task 2.
- Produces: `AFutsalPlayerBase`, exact reflected properties `ExternalMotionActive` and `ExternalMotionSpeedMps`, and a raw `GetCharacterMovementHorizontalSpeedMps()` accessor only.

- [ ] **Step 1: Write failing automation tests for raw CharacterMovement data**

Test raw native calculations only: horizontal CharacterMovement velocity converts cm/s to m/s, ignores Z, and treats values below the declared epsilon as zero. Do not test final effective source selection in C++; that selection belongs to the AnimBP. Verify reflected exact names/defaults and transform/velocity non-mutation in the UE Blueprint/Sequence integration gates in Tasks 4 and 6.

Run the focused UE automation test and confirm it fails because the native class/helper is not yet implemented.

- [ ] **Step 2: Add reflected properties and Blueprint-readable accessors**

Declare:

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Animation|External Motion")
bool ExternalMotionActive = false;

UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Animation|External Motion", meta=(ClampMin="0.0"))
float ExternalMotionSpeedMps = 0.0f;
```

Expose only a read-only Blueprint function for raw CharacterMovement horizontal speed in m/s. Do not expose an effective animation speed/source getter that takes no explicit AutoMotion/canonical inputs. The native class must not write Actor transform, call `SetActorLocation`, drive `AddMovementInput`, alter velocity, or enable root motion.

- [ ] **Step 3: Implement and test the raw speed conversion helper**

Implement only raw CharacterMovement horizontal speed conversion and validity. Use a named epsilon of `0.01 cm/s`; do not use vertical velocity as locomotion speed. Keep explicit external properties raw and Sequencer-writable. Final effective speed remains AnimBP-owned.

- [ ] **Step 4: Build and run native automation tests**

Build `FutsalMOTEditor Win64 Development` and run the focused automation group. Expected: raw horizontal speed conversion and zero/near-zero handling pass. Reflected property defaults and non-mutation are checked after Blueprint migration in Task 4.

### Task 4: Migrate Colliding Blueprint Variables and Reparent Transactionally

**Files:**
- Modify through Unreal Editor API: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase` only.
- Modify/save: no Court map or actor package unless Blueprint reparenting explicitly dirties dependent packages; if it does, inspect and report before saving.

**Interfaces:**
- Consumes: compiled native class `/Script/FutsalMOT.FutsalPlayerBase`.
- Produces: existing canonical Blueprint path with parent `AFutsalPlayerBase`, same generated Blueprint class name, exact inherited properties, and all unrelated variables/components/defaults preserved.

- [ ] **Step 1: Record a transactional snapshot of both colliding declarations**

Use Blueprint variable introspection to record each exact name `ExternalMotionActive` and `ExternalMotionSpeedMps`: variable type, default, category, Instance Editable, Expose to Cinematics/Interp, and all other set flags. Also record every other variable, parent, component tree, mesh, AnimClass, interfaces, construction-script graph count, dirty state, and saved package hash. Before removal, create and verify a recoverable duplicate package at an unused ignored/local migration-backup path using the UE asset duplication API; verify the backup retains its original parent and both variables. Abort if metadata/default cannot be read, the backup cannot be created/verified, unsaved external edits are present, or the canonical Blueprint differs from its recorded baseline.

- [ ] **Step 2: Remove only the two colliding Blueprint-owned declarations**

Remove only the two Blueprint member declarations using the supported variable removal API. Verify the Blueprint variable list contains neither name and all unrelated declarations match the snapshot. Do not compile or save yet.

- [ ] **Step 3: Reparent only after both names are free**

Use `BlueprintTools.set_parent` or `unreal.BlueprintEditorLibrary.reparent_blueprint` with exact native class `/Script/FutsalMOT.FutsalPlayerBase`. Compile, then verify inherited reflected names are exactly `ExternalMotionActive` and `ExternalMotionSpeedMps`, with no automatic suffix names. Verify CDO defaults false/zero, category and Interp/Expose-to-Cinematics metadata, every unrelated Blueprint variable, components, mesh, AnimClass and interfaces. Do not recreate Court actors or replace their canonical Blueprint asset path.

- [ ] **Step 4: Roll back transaction on any failed verification**

If variable removal, reparent, compile, exact-name, metadata, defaults, components, or unrelated variables fail verification, do not save the partial canonical package. Restore it from the verified local backup using the Editor asset restore/replace workflow only after confirming the canonical package is the transaction's modified target; compile and re-read the original parent and both declarations. If the Editor cannot restore the full package reliably, stop and leave the backup untouched for manual recovery. Keep the backup until acceptance and user approval. Do not use broad Git restore/checkout commands.

- [ ] **Step 5: Save only after the transaction verifies**

Save only `BP_FutsalPlayerBase`. Compare all ten live Court actor labels/GUIDs/transforms/components and Sequence binding identities with Task 1. Inspect dependent package dirty state individually; do not save maps/actors unless a change is proven necessary and user-approved. Rebuild the Editor target and compile Character and AnimBP.

### Task 5: Connect the Existing AnimBP to the Native Speed Contract

**Files:**
- Modify through UE Blueprint editor graph API or GUI: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase`.

**Interfaces:**
- Consumes: native `AFutsalPlayerBase` raw CharacterMovement speed and exact external properties from Task 3.
- Produces: AnimBP-owned effective speed selector consumed by existing GroundSpeed conversion; no changes to the repaired ShouldMove graph.

- [ ] **Step 1: Add a failing graph-level inspection check**

Read the EventGraph nodes and pins. Confirm the prior implementation has no `ExternalMotionActive` read and no `ExternalMotionSpeedMps` read. Record existing `GroundSpeed`, `Direction`, `ShouldMove`, `IsFalling`, `Use Auto Motion Speed`, and BPI fallback node references before edits.

- [ ] **Step 2: Add only the explicit external-speed selection branch**

Cache the owning `AFutsalPlayerBase` reference in Initialize Animation, not on every update. Read raw CharacterMovement horizontal speed and exact inherited properties `ExternalMotionActive` and `ExternalMotionSpeedMps`. In the existing selector, give active explicit external motion priority over Auto Motion fallback. Do not call a native no-argument effective-speed getter; keep final source selection and canonical fallback in the AnimBP.

- [ ] **Step 3: Verify protected animation dataflow**

Graph inspection must show:

```text
CharacterMovement speed -> priority branch
ExternalMotionActive && CharacterMovement inactive -> ExternalMotionSpeedMps
otherwise Use Auto Motion Speed -> existing Auto Motion Speed Mps
otherwise -> existing BPI_FutsalPlayerBaseAnimation fallback
GroundSpeed = Effective Motion Speed Mps * 100
Direction = existing Effective Velocity + Actor Rotation path
IsFalling = CharacterMovement
```

Confirm the `ShouldMove` node/inputs and both locomotion transition graphs are unchanged. Compile/save only the AnimBP. If exact node/pin inspection or safe local graph mutation is unavailable, stop at `MANUAL_ABP_EXTERNAL_SPEED_GATE_REQUIRED` with a GUI-ready connection list; do not use full graph DSL replacement.

### Task 6: Validate Sequence Track Binding and Numeric Contract

**Files:**
- Read/execute: `Content/FutsalMOT/code/ue/import_grf_episode.py` through official `run_task.py`.
- Read only: resolved smoke task, exported episode, `LS_Cam_01`.

**Interfaces:**
- Consumes: inner BASE-2I commit `9fe6a7c` and smoke resolved task.
- Produces: regenerated official sequence and source-versus-key comparison for every Player_R0 smoke frame.

- [ ] **Step 1: Verify active Court and canonical player identity**

Read the Editor World. Require `/Game/FutsalMOT/Maps/L_FutsalCourt` and exactly ten `Player_L0..L4`, `Player_R0..R4` instances of `BP_FutsalPlayerBase_C`.

- [ ] **Step 2: Run the official short sequence task**

Set `C5_RESOLVED_TASK` to `Content/FutsalMOT/code/.futsalmot/runtime/pose_smoke_3frames_1cam/resolved-task.json`, `C5_RUN_MODE=sequence`, and execute `ue/run_task.py` in UE Editor Python. Verify all 11 expected labels resolve.

- [ ] **Step 3: Inspect all generated property tracks**

Read `LS_Cam_01` bindings. Each of ten player bindings must have one Transform track, one Bool property path exactly `ExternalMotionActive`, and one Float property path exactly `ExternalMotionSpeedMps`. Bool values must remain true across the sequence range. Ball must have no player external-motion properties. Fail sequence validation if any track/property path is absent or duplicated.

- [ ] **Step 4: Compare every Player_R0 tracker speed to the Float key**

Replay `PlayerMotionTracker.update()` over `episode_pose_smoke/frames.jsonl` using the same meta goalkeeper set and the same time fallback as the writer. Read Float-channel key frame/value pairs. Match each frame index and require absolute speed delta <= `1e-6` m/s. Also verify `speed_mps` equals the 2D norm of `velocity_mps` within `1e-6` m/s.

### Task 7: Validate Animation Inputs, Transform Authority, and Fallback

**Files:**
- Read/execute: Court and `LS_Cam_01` in the live UE session.
- Modify: none unless a test shows a concrete defect; any new graph fix requires a reviewed follow-up.

**Interfaces:**
- Consumes: compiled native Character, reparented Blueprint, updated ABP, generated smoke Sequence.
- Produces: measured motion source, effective speed, GroundSpeed, ShouldMove, direction, active locomotion evidence, and transform-authority result.

- [ ] **Step 1: Capture sequential Player_R0 runtime values**

During actual sequential evaluation capture `ExternalMotionActive`, `ExternalMotionSpeedMps`, CharacterMovement horizontal speed, effective source/speed, Auto fallback speed, GroundSpeed, ShouldMove, Direction, and IsFalling for all three smoke frames. Expected: explicit speed selected where active, GroundSpeed is m/s × 100, and raw CharacterMovement remains allowed to be zero.

- [ ] **Step 2: Prove trajectory authority**

Capture Actor transforms immediately before/after evaluating the same Sequence frames. Confirm transform values equal the generated transform tracks and are not changed by CharacterMovement or the new C++ speed contract.

- [ ] **Step 3: Check one normal CharacterMovement source**

If a safe existing PIE/controller test setup exists, verify non-zero CharacterMovement velocity wins over external property tracks. Do not change level actors or add input assets just for this optional regression. Otherwise report `NORMAL_CHARACTER_MOVEMENT_SOURCE = NOT_TESTED`.

- [ ] **Step 4: Record the manual visual cadence gate**

Inspect a visibly moving and stationary player in the open Sequence. Moving must leave Idle and animate; stationary must remain Idle. Record animation cadence separately; do not tune BlendSpace or Play Rate in phase one.

### Task 8: Final Regression, Dependency Audit, and Migration Checkpoint

**Files:**
- Read/execute: both repos, build output, Blueprint dependency closure, Sequence.
- Modify: architecture audit documentation after passing evidence is collected.

**Interfaces:**
- Consumes: outputs from Tasks 1–7.
- Produces: validated phase report and a clean, scoped migration checkpoint ready for explicit commit approval.

- [ ] **Step 1: Run isolated inner Python tests and restore local config**

Move ignored `.futsalmot/local.json` to a unique temporary sibling, run `& '.\.venv\Scripts\python.exe' -m pytest`, then restore it in a `finally` block. Require all tests pass and verify original file exists while temp file does not.

- [ ] **Step 2: Audit canonical dependency closure**

Inspect Character and AnimBP direct/transitive project content dependencies. Require zero dependencies on `BP_FutsalCharacterBase`, `ABP_FutsalSource`, `BPI_FutsalAnimationSource`, `BS_Futsal_Locomotion`, Mannequin, and ThirdPerson. Confirm new native dependency is only `/Script/FutsalMOT` and engine modules.

- [ ] **Step 3: Compare protected asset and workspace state**

Recompute `UNREAL_RIG.uasset` SHA-256 and compare with Task 1. Run separate outer/inner `git status --short --branch`; do not stage unrelated changes. Verify generated user assets are only the intended Character/AnimBP/Sequence package changes and any unavoidable actor packages were reviewed individually.

- [ ] **Step 4: Append migration audit results**

Append C++ module/class, reparent, defaults, sequence property track/numeric comparison, transform authority, visual gate, builds/tests, dependency closure, and remaining expansion steps to `Docs/Architecture/FUTSAL_HUMAN_UE_IMPORT_AUDIT.md`. Distinguish verified, unverified, and manual results.

- [ ] **Step 5: Stop before implementation commit**

Show separate outer/inner diffs and statuses and request explicit approval before committing migration changes. Do not delete retired assets.
