# FutsalPlayer AnimInstance C++ Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move canonical `ABP_FutsalPlayerBase` initialization and animation-data update behavior into a native `UFutsalPlayerAnimInstance`, while keeping its AnimGraph, state machines, BlendSpace, animation sequences, and FootIK ControlRig as existing assets.

**Architecture:** Add a native AnimInstance that owns the transcribed motion inputs and updates the variables consumed by the existing Blueprint pose/state-machine graphs. Reparent the canonical AnimBP only after building a recoverable copy of its current disk version and verifying a local asset diff; preserve graph topology and asset references, and stop without saving if UE cannot make the focused parent/variable migration safely.

**Tech Stack:** Unreal Engine 5.8, C++ runtime module `FutsalMOT`, Unreal Editor Python/MCP for asset inspection and compile/save, UE native automation tests, official inner-repository smoke-sequence exporter.

**Spec:** `Docs/superpowers/specs/2026-09-28-cpp-animinstance-migration-design.md`

## Global Constraints

- Sequencer Transform tracks are the sole authority for Actor world position and facing.
- External motion speed is animation magnitude metadata and never changes Actor Transform, CharacterMovement velocity, or Root Motion.
- Preserve the transcribed legacy speed selector and overlay `ExternalMotionSpeedMps` only when `ExternalMotionActive`; do not add CharacterMovement speed priority.
- Preserve the recorded `ShouldMove` acceleration wiring semantics, Direction source/clamp, `IsFalling` source, and `Velocity.Z > 100.0` Jump threshold.
- Do not edit either state machine, transition graphs, cached-pose topology, `BS_FutsalPlayerBase_Locomotion`, animation sequences, Slot, FootIK ControlRig, samples, axes, or playback rates.
- Do not modify `UNREAL_RIG.uasset`, delete retired assets, modify the inner Python repository, commit, or push.
- Keep the pre-existing staged migration checkpoint and unrelated unstaged/deleted/untracked files separate; stage no implementation files in this plan.
- The current canonical ABP disk file has a pre-existing 994-byte worktree difference. Inspect and preserve that exact version; never reset it or replace it from Git.
- Use only Unreal MCP native tools or `FutsalMOTTools.run_python_file` / `run_python_code` in the real Editor Python environment. Never use the restricted ProgrammaticToolset for `unreal` Python.

---

## File Structure

- `Source/FutsalMOT/Public/FutsalPlayerAnimInstance.h`: reflected animation data contract and native AnimInstance declaration.
- `Source/FutsalMOT/Private/FutsalPlayerAnimInstance.cpp`: owner caching, initialization, and ordered per-frame computation.
- `Source/FutsalMOT/Private/Tests/FutsalPlayerAnimInstanceTests.cpp`: native math, source selection, edge-case, and state-input contract tests.
- `Source/FutsalMOT/FutsalMOT.Build.cs`: add only required runtime module dependencies if the implementation needs them.
- `Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset`: focused AnimInstance parent/variable/EventGraph migration only, after transaction gate.
- `Docs/Architecture/FUTSAL_HUMAN_UE_IMPORT_AUDIT.md`: append observed implementation and validation outcomes after they occur.
- `Docs/superpowers/specs/2026-09-28-cpp-animinstance-migration-design.md`: approved behavior/asset contract; edit only if user-approved design changes.

No test-only helper is added to production files. Native computation should be structured so pure calculations can be exercised without constructing a rendered scene, while the actual update method remains the single production path calling those calculations.

## Task 1: Establish the ABP Asset Transaction Baseline

**Files:**
- Read only: `Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset`
- Read only: `Content/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.uasset`
- Read only: `Content/FutsalMOT/Maps/L_FutsalCourt.umap`
- Read only: `Content/FutsalMOT/Sequences/LS_Cam_01.uasset`

- [ ] **Step 1: Record repository boundaries before Editor asset inspection**

Run from the outer repository:

```powershell
git status --short --branch
git diff --cached --name-only
git diff -- Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset
git -C Content/FutsalMOT/code status --short --branch
```

Expected: the pre-existing ABP binary difference remains unstaged; inner repository is unchanged. Do not stage or reset any path.

- [ ] **Step 2: Read and preserve the current ABP through UE Editor**

Using a single-purpose real Unreal Python diagnostic, read and log:

```python
{
    "asset_path": "/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase",
    "parent_class": "...",
    "member_variables": ["..."],
    "graph_names": ["..."],
    "graph_paths": ["..."],
    "compile_status": "..."
}
```

Create a recoverable UE asset duplicate from the currently loaded disk asset under `/Game/FutsalMOT/Intermediate/CppMigrationBackup/` using a unique migration suffix. Do not use `git checkout`, file copying over the asset, or an asset duplicate made from a stale in-memory state without first establishing the on-disk asset was loaded after Editor restart.

- [ ] **Step 3: Record graph and binding invariants**

Record in diagnostic output the two state-machine graph paths, state names, transition graph count, AnimGraph references to `BS_FutsalPlayerBase_Locomotion`, idle/jump/fall/land sequences, cached pose names, DefaultSlot, and FootIK ControlRig reference. Also record the canonical Character Blueprint AnimClass and current Court actor count/labels/transform snapshots plus Sequence player binding count and property track names.

- [ ] **Step 4: Verify the backup and baseline before code work**

Load both canonical ABP and backup and compare parent, member variable names, graph names, and class. Confirm the backup has the same ABP structure as the current loaded source. Stop if the two differ or if the current 994-byte difference appears to be a malformed/partially serialized asset. Do not proceed on an unverified recovery copy.

## Task 2: Define Native AnimInstance Behavior With Failing Tests

**Files:**
- Create: `Source/FutsalMOT/Private/Tests/FutsalPlayerAnimInstanceTests.cpp`
- Modify: `Source/FutsalMOT/FutsalMOT.Build.cs` only if test compilation needs an existing UE runtime dependency

**Interfaces:**
- This task defines the pure computation contracts to be implemented in Task 3. Keep exported reflected names aligned with the approved spec and manually transcribed Blueprint variable identifiers wherever existing AnimGraph nodes bind by name.

- [ ] **Step 1: Add a focused automation test for Auto Motion XY velocity**

Test that `(300, 400, 900)` cm/s transform delta over `1.0` second produces XY velocity `(300, 400, 0)` cm/s and speed `5.0` m/s; test that arbitrary Z displacement does not contribute to horizontal speed.

- [ ] **Step 2: Add tests for the update initialization and DeltaTime boundary contract**

Cover the first uninitialized update setting PreviousLocation to current Actor location, AutoMotionVelocity to zero, and SpeedInitialized true without asserting a write to AutoMotionSpeedMps. Cover `DeltaTimeX == 0.0001` as no transform-delta update and `DeltaTimeX > 0.0001` as an update.

- [ ] **Step 3: Add tests for legacy/external effective speed and units**

Test both `UseAutoMotionSpeed` choices through the legacy selector; test external inactive passthrough; test external active override including zero speed; test `GroundSpeed == EffectiveMotionSpeedMps * 100`.

- [ ] **Step 4: Add tests for direction selection and Clamp**

Test CalculateDirection-equivalent output from EffectiveVelocity and Actor yaw; when OrientRotationToMovement is false preserve raw direction; when true clamp only to `[-45, +45]`. Do not source direction from external speed.

- [ ] **Step 5: Add tests for ShouldMove transcription semantics**

Use one acceleration input for both terms, but implement the test as a pure helper call and assert the recorded expression exactly:

```cpp
ShouldMove = (GroundSpeed > 0.01f)
	&& ((Acceleration != FVector::ZeroVector)
		|| !(Acceleration.Size2D() > 0.01f));
```

Test zero acceleration, finite nonzero acceleration, the `GroundSpeed == 0.01f` threshold, and above-threshold speed. Do not simplify the Boolean expression in production code.

- [ ] **Step 6: Build and run the tests to verify RED**

With Unreal Editor closed and Live Coding inactive, run:

```powershell
& 'E:\UE_5.8\Engine\Build\BatchFiles\Build.bat' FutsalMOTEditor Win64 Development '-Project=D:\projects\FutsalMOT_UEDataset\FustalMOT_UEDataset.uproject' -WaitMutex
```

Expected: compilation fails because the new native AnimInstance API is not yet implemented. Confirm failure is limited to the expected missing declarations/functions, not toolchain or UHT setup.

## Task 3: Implement `UFutsalPlayerAnimInstance`

**Files:**
- Create: `Source/FutsalMOT/Public/FutsalPlayerAnimInstance.h`
- Create: `Source/FutsalMOT/Private/FutsalPlayerAnimInstance.cpp`
- Create: `Source/FutsalMOT/Private/Tests/FutsalPlayerAnimInstanceTests.cpp`

**Interfaces:**
- `UFutsalPlayerAnimInstance : UAnimInstance` with `NativeInitializeAnimation()` and `NativeUpdateAnimation(float DeltaSeconds)` overrides.
- Read-only cached owner references: `ACharacter* Character`, `UCharacterMovementComponent* MovementComponent`, optional `AFutsalPlayerBase* FutsalPlayer` when cast succeeds.
- Blueprint-read-only variables required by existing state/pose graphs retain exact reflected identifiers: `Velocity`, `GroundSpeed`, `Direction`, `ShouldMove`, `IsFalling`, `MotionSpeedMps`, `PreviousLocation`, `AutoMotionSpeedMps`, `SpeedInitialized`, `UseAutoMotionSpeed`, `EffectiveMotionSpeedMps`, `AutoMotionVelocity`, `EffectiveVelocity`, and `AutoFacingYawDeg` only where the live reference baseline shows they are consumed.
- Pure helpers expose testable calculations for Auto Motion delta, legacy/external speed selection, Direction selection, and ShouldMove without changing the Blueprint contract. The production `NativeUpdateAnimation` passes the actual single `MovementComponent->GetCurrentAcceleration()` value to the ShouldMove helper.

- [ ] **Step 1: Implement declarations and reflected defaults**

Add the subclass header with generated include last. Preserve required Blueprint-bound identifiers exactly. Keep `UseAutoMotionSpeed` default consistent with the verified current ABP instance/default readback, not a guessed default. Keep `MotionSpeedMps` fallback zero unless the verified asset data establishes otherwise.

- [ ] **Step 2: Implement owner cache and initialization**

In `NativeInitializeAnimation`, call the parent implementation, obtain `TryGetPawnOwner()`/owning actor using a UE 5.8 API verified in this project, cast to generic `ACharacter`, get CharacterMovement, optionally cast to `AFutsalPlayerBase`, set PreviousLocation from Actor location, and explicitly set SpeedInitialized true. Handle invalid owner/component without dereferencing it.

- [ ] **Step 3: Implement ordered motion calculation**

In `NativeUpdateAnimation`, call the parent then preserve the recorded logical order:

1. Auto Motion update gated by SpeedInitialized and `DeltaSeconds > 0.0001f`.
2. MotionSpeedMps legacy fallback value, EffectiveVelocity, Velocity, effective speed selection, and GroundSpeed.
3. Direction from EffectiveVelocity and Actor rotation with the recorded orient-rotation Clamp behavior.
4. ShouldMove using the exact recorded acceleration expression.
5. IsFalling from CharacterMovement.

Maintain the verified detail that the nonpositive/small DeltaSeconds branch has no transform-delta update and the uninitialized recovery branch does not write AutoMotionSpeedMps. Update AutoFacingYawDeg only under the recorded effective-speed `> 0.3 m/s` condition.

- [ ] **Step 4: Layer external speed over, not inside, direction selection**

Compute `LegacySpeed = UseAutoMotionSpeed ? AutoMotionSpeedMps : MotionSpeedMps`, then pass that to `AFutsalPlayerBase::SelectEffectiveMotionSpeedMps(FutsalPlayer && FutsalPlayer->ExternalMotionActive, FutsalPlayer ? FutsalPlayer->ExternalMotionSpeedMps : 0.0f, LegacySpeed)`. EffectiveVelocity remains independently selected from AutoMotionVelocity versus MovementComponent.Velocity.

- [ ] **Step 5: Run the focused native tests to verify GREEN**

Run the Editor target build; launch UE Editor; discover and run all `FutsalMOT.Character.*` automation tests. Expected: new AnimInstance tests and previous Character tests pass. Inspect LogBlueprint/LogAnimation/LogCompile for new errors.

## Task 4: Prove the Current ABP Difference Is Recoverable Before Mutation

**Files:**
- Read only until explicit gate: `Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset`
- Existing recovery duplicate under `/Game/FutsalMOT/Intermediate/CppMigrationBackup/`

- [ ] **Step 1: Compare the staged/HEAD ABP, current disk ABP, and verified UE backup**

Treat Git binary size/hash differences as evidence only; do not restore the Git version. Compare the in-Editor current disk asset to the backup created in Task 1 and read any available UE asset package/save status. Confirm the 994-byte delta did not change required parent class, graph structure, variables, or asset references relative to the captured baseline.

- [ ] **Step 2: Re-read exact current graph/variable state through UE Editor**

Record current graph names, member variables, parent class, generated class, compile status, and references. Use human-reviewed transcription for graph topology where MCP DSL is empty. Confirm current owner of each colliding variable and all Blueprint defaults/categories/Sequencer exposure flags visible in UE.

- [ ] **Step 3: Apply the asset mutation gate**

Proceed only if the backup is verified and the current ABP compiles. If either check fails or the 994-byte worktree difference cannot be safely explained/recovered, stop before any ABP mutation and report the manual asset gate. No destructive restoration is authorized by this plan.

## Task 5: Reparent the Canonical ABP With a Focused Asset Change

**Files:**
- Modify through UE Editor only: `Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset`
- Read only: `Content/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.uasset`
- Read only: `Content/FutsalMOT/Maps/L_FutsalCourt.umap`
- Read only: `Content/FutsalMOT/Sequences/LS_Cam_01.uasset`

**Interfaces:**
- AnimBP parent class becomes the compiled `UFutsalPlayerAnimInstance` generated class.
- Existing AnimGraph continues to bind to inherited native variables with exact existing names.

- [ ] **Step 1: Identify only truly colliding Blueprint-owned variables**

Compare each ABP Blueprint variable to the native AnimInstance reflected properties and graph references. Remove only a BP-owned declaration when it directly collides with a native inherited name; retain unrelated, ambiguous, or unreferenced-but-not-proven-dead variables including `CurrentAnimationClass` and `Velocity_0`.

- [ ] **Step 2: Reparent and compile without editing graph topology**

Use the UE Blueprint Editor API to set the AnimBP parent to the compiled native AnimInstance class. Do not call `write_graph_dsl`, replace the EventGraph wholesale, recreate nodes, alter graph links, edit state machines, or alter pose assets.

- [ ] **Step 3: Retire only EventGraph update work after native bindings compile**

First compile the reparented asset with the EventGraph intact to reveal binding issues. Then remove only the initialization/update event graph work and data-computation nodes whose behavior is now owned by C++. Preserve any event/function nodes proven necessary by current references; do not remove `GetMotionSpeedMps` until its graph references are proven disconnected and the zero stub contract remains represented by the C++ legacy fallback.

- [ ] **Step 4: Compile and save, then independently reload/read back**

Compile the ABP and save only after no errors. Unload/reload the asset through Editor APIs and verify parent class, inherited variables, graph names, state-machine topology, BlendSpace/sequence/ControlRig references, and no variable suffixes. If any check fails, restore the Task 1 duplicate in UE, verify restoration, and stop.

## Task 6: Validate Canonical Character, Court, and Sequencer Compatibility

**Files:**
- Read/compile only: `Content/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.uasset`
- Read only: `Content/FutsalMOT/Maps/L_FutsalCourt.umap`
- Read only: `Content/FutsalMOT/Sequences/LS_Cam_01.uasset`

- [ ] **Step 1: Compile the canonical Character Blueprint**

Compile `BP_FutsalPlayerBase` and verify its parent remains `/Script/FutsalMOT.FutsalPlayerBase`, its mesh remains `SKM_FutsalPlayerBase`, and its AnimClass still points to the canonical ABP path.

- [ ] **Step 2: Compare Court actor identity and transform baseline**

Verify ten canonical player actors remain, with the same labels, tags, actor identities/possessable resolution, transforms, meshes, and components as Task 1. Do not save the map unless UE marks it dirty due to an unintended migration side effect; stop and inspect rather than accepting a map rewrite.

- [ ] **Step 3: Validate Sequence bindings and external motion tracks**

Verify all ten player bindings retain Transform, `ExternalMotionActive`, and `ExternalMotionSpeedMps`; Ball and camera tracks/bindings remain unchanged. Compare representative tracker speed keys against sequence float keys; do not modify the inner repo or regenerate sequence unless a migration-specific issue requires it.

- [ ] **Step 4: Verify protected and unrelated workspace state**

Recompute the protected `UNREAL_RIG.uasset` SHA-256 and compare against `DF49F074715CF3C5791FE37DA63ACF96A1C0E1060CC6A2D27CCB09442246436D`. Inspect `git status` for only expected new C++/test/docs changes plus already known unrelated statuses; do not stage implementation files.

## Task 7: Runtime Motion and State-Machine Acceptance

**Files:**
- Read-only runtime validation against canonical ABP, Court, and smoke Sequence.

- [ ] **Step 1: Validate stationary ground playback**

During sequential playback, sample an actually stationary player. Confirm `IsFalling=false`, GroundSpeed is below the recorded `0.01 cm/s` ShouldMove threshold, ShouldMove is false, locomotion sub-state is Idle, and Actor Transform remains the Sequence value.

- [ ] **Step 2: Validate external-speed ground playback**

Sample a moving player while CharacterMovement is stationary and `ExternalMotionActive=true`. Confirm selected m/s equals `ExternalMotionSpeedMps`, GroundSpeed equals m/s times 100, Velocity/EffectiveVelocity/Direction still use the recorded motion-vector path, and record the actual `GetCurrentAcceleration()` plus ShouldMove result. Do not assert ShouldMove is true merely because GroundSpeed is positive: the human transcription wires CharacterMovement acceleration into both Boolean terms, so if Sequence-driven motion leaves acceleration zero the retained logic can keep the Locomotion sub-state Idle. Do not redesign that behavior in this migration; report it as an observed limitation for a separately approved change. Confirm the player does not enter Jump/Fall/Land during ground Sequence playback.

- [ ] **Step 3: Validate Auto Motion and legacy fallback paths**

With external motion inactive, test `UseAutoMotionSpeed=true` uses transform-delta AutoMotionSpeedMps and false preserves MotionSpeedMps (currently a zero stub). Verify low/equal DeltaSeconds does not introduce a new movement update.

- [ ] **Step 4: Validate airborne state inputs against the retained Blueprint machine**

Using a controlled test actor/runtime setup that does not alter the production Court or Sequence, verify `IsFalling && Velocity.Z > 100` selects Jump, other falling selects Fall Loop, Jump auto sequence completion goes to Fall Loop, `!IsFalling` returns through Land, and Land completion follows the current asset's retained rule. Do not alter state transition graphs to improve the result.

- [ ] **Step 5: Record human visual acceptance**

Inspect Idle cadence, BlendSpace locomotion cadence, direction response, jump/fall/land motion, and FootIK visually in UE Editor/PIE or Sequencer. Record only observed outcomes; do not tune PlayRate or samples within this migration.

## Task 8: Update Audit and Final Repository Review

**Files:**
- Modify: `Docs/Architecture/FUTSAL_HUMAN_UE_IMPORT_AUDIT.md`
- Read: all changed source/assets and repository statuses

- [ ] **Step 1: Append actual migration and verification results**

Record AnimInstance class/path, exact preserved variable names, C++ test names/count, UBT result, BP/ABP compile results, Court/Sequence checks, runtime variable samples, visual checks, any blocked manual gate, and the known Land→Locomotion ambiguity. Do not mark unrun checks as PASS.

- [ ] **Step 2: Review staged and unstaged changes independently**

Run:

```powershell
git status --short --branch
git diff --check
git diff --stat
git diff --cached --stat
git -C Content/FutsalMOT/code status --short --branch
```

Confirm implementation files remain unstaged, the pre-existing stage list is unchanged, inner repository remains untouched, and unrelated deleted/untracked files are preserved.

- [ ] **Step 3: Report implementation without committing**

Summarize completed code and asset work, tests/build/Editor outcomes, any remaining visual or manual gate, exact paths changed, and repository status. Do not commit or push without separate explicit user authorization.

## Spec Coverage Self-Review

- Native AnimInstance initialization/update, data contract, tests, speed/direction/ShouldMove/Falling semantics: Tasks 2-3.
- Existing ABP preservation and protected handling of current 994-byte difference: Tasks 1, 4-5.
- Existing state machines, BlendSpace, animation sequences, ControlRig and land transition ambiguity: Tasks 1, 5, 7.
- Character/Court/Sequence identity and pipeline contract: Task 6.
- Runtime trajectory ownership, stationary/moving/airborne acceptance, visual review: Task 7.
- Audit documentation, dual repository/staging safety, no automatic commit/push: Task 8.

## Plan Self-Review

- Placeholder scan: no TBD/TODO or unspecified implementation steps. Any asset backup or mutation failure has an explicit stop/restore path.
- Type consistency: `UFutsalPlayerAnimInstance`, `NativeInitializeAnimation`, `NativeUpdateAnimation`, and `AFutsalPlayerBase::SelectEffectiveMotionSpeedMps` use the same names as the approved spec and current C++ API.
- Scope check: the plan covers the single approved AnimInstance migration subsystem; it explicitly excludes rewriting state machines or pose assets.
- Asset safety: current ABP is backed up from the current loaded disk asset, and the pre-existing binary difference is never overwritten from Git.
