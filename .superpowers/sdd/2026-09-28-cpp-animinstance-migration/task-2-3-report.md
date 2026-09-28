# Task 2/3 AnimInstance implementation fix report

Date: 2026-09-28

## Scope

Revised only the native AnimInstance header/implementation and its automation tests. No ABP, Court, Sequence, or `UNREAL_RIG` asset was edited or saved. No staging, commit, or push was performed.

Inputs reviewed: `Docs/superpowers/specs/2026-09-28-cpp-animinstance-migration-design.md`, `Source/FutsalMOT/Public/FutsalPlayerAnimInstance.h`, `Source/FutsalMOT/Private/FutsalPlayerAnimInstance.cpp`, `Source/FutsalMOT/Private/Tests/FutsalPlayerAnimInstanceTests.cpp`, `Source/FutsalMOT/FutsalMOT.Build.cs`, and `.superpowers/sdd/2026-09-28-cpp-animinstance-migration/task-1-report.md`, including its C++ introspection findings and exact-name list.

## Changes

- Replaced ambiguous native reflected state with uniquely named `Native*` / `bNative*` fields. None of the native UPROPERTY identifiers collide with BP-owned animation variable names.
- Added an exact-FName reflection bridge for the 14 confirmed BP-owned variable names. It searches the AnimInstance generated class, validates property type, writes only matching properties, and logs a warning then skips missing/type-incompatible fields. No `DisplayName` metadata is used as a binding mechanism.
- Preserved full XYZ transform delta divided by DeltaSeconds; Auto Motion speed continues to use `Size2D() * 0.01`, so vertical displacement is available to the `Velocity.Z > 100` Jump input without affecting horizontal speed.
- NativeInitialize caches owner/component/location and leaves speed initialization false. First NativeUpdate takes a testable recovery path that records current location, publishes zero auto velocity, sets initialized, and leaves AutoMotionSpeedMps untouched. Small/non-finite DeltaSeconds do not update the delta state.
- Removed the per-frame assignment that zeroed MotionSpeedMps; its native fallback remains at its zero default and is preserved when selected.
- Added automation coverage for full-Z velocity/Jump threshold, exact bridge allowlist and safe misses, first-update behavior, Z-only acceleration, and external scalar/vector independence.
- The bridge helper is directly tested against a test UObject class: it writes the exact approved FName, rejects the no-space native alias, and leaves a type-incompatible property unchanged.

## Verification

- Requested UBT command was attempted: `Build.bat FutsalMOTEditor Win64 Development -Project=... -WaitMutex`.
- Result: **BLOCKED**, exit via `Unable to build while Live Coding is active`. The running Editor is an active user process; it was not closed or interrupted.
- Automation discovery succeeded against the currently loaded Editor binary, but it reports the pre-rebuild test inventory: 5 `FutsalMOT.AnimInstance.*` tests and 3 `FutsalMOT.Character.*` tests. Those 8 loaded-binary tests were run and passed (8 passed, 0 failed, 0 skipped). They do not include the modified source tests.
- Required source inventory after rebuild: 8 AnimInstance tests plus 3 Character tests, 11 total. Execution status for the modified source: **NOT RUN**, because current source cannot be compiled while Live Coding is active. The legacy test binary's 8/8 result is not evidence for the modified source.

## Remaining concerns

- Compilation and execution of the modified C++ and new tests remain unverified until an Editor-target build is possible with Live Coding inactive.
- Runtime generated-class property lookup/write remains unverified against the real reparented ABP; this change intentionally does not mutate or save that asset. Missing or mismatched properties will be logged and skipped.
- UE's current reflection behavior for exact spaced Blueprint-owned property names must be checked in the post-build automation/runtime pass before claiming ABP binding success.

## Test Translation Unit Repair and Final Verification (2026-09-28)

### Root cause and repair

- Read the UBT log at `C:\Users\20113\AppData\Local\UnrealBuildTool\Log.txt`. It identified only `FutsalPlayerAnimInstanceTests.cpp` as failing: `UCLASS()`/`GENERATED_BODY()` had no UHT-generated support in the cpp, and the nested `#if WITH_DEV_AUTOMATION_TESTS` blocks produced an unmatched preprocessor structure.
- Removed the cpp-local UCLASS fixture entirely. Bridge tests now use `UFutsalPlayerAnimInstance::StaticClass()` as a read-only real-class reflection surface and test the production bridge allowlist, exact names, no native aliases, and safe rejection of null/type-incompatible properties.
- Extracted `IsBlueprintBridgePropertyTypeCompatible` as a pure helper used by the production setter and directly covered by tests. It adds no runtime UObject type.
- The first 11-test run exposed an incorrect test assumption that BP-owned `Velocity` should already exist on the native class. Corrected this: it now asserts that native reflection does not contain the colliding name; the exact name remains in the approved bridge allowlist for a BP generated class.
- Removed the redundant nested preprocessor directive; the automation source has one matching `#if WITH_DEV_AUTOMATION_TESTS` / `#endif` pair.

### UBT

After checking `EditorLoadingAndSavingUtils.get_dirty_content_packages()` and `get_dirty_map_packages()` (both empty), the newly started Editor was normally asked to exit and confirmed absent before build.

Command:

```powershell
& 'E:\UE_5.8\Engine\Build\BatchFiles\Build.bat' FutsalMOTEditor Win64 Development '-Project=D:\projects\FutsalMOT_UEDataset\FustalMOT_UEDataset.uproject' -WaitMutex
```

Result: **Succeeded**, exit code 0. The final build compiled `FutsalPlayerAnimInstanceTests.cpp`, `Module.FutsalMOT.gen.cpp`, and `FutsalPlayerAnimInstance.cpp`, linked `UnrealEditor-FutsalMOT.lib` and `.dll`, and wrote `FutsalMOTEditor.target` metadata.

### Editor automation

- Restarted the project Editor, called `DiscoverTests(bForceRediscover=true)`, and found exactly 11 `FutsalMOT.*` tests: 8 AnimInstance plus 3 Character.
- Ran all 11 tests. Result: **11 passed, 0 failed, 0 skipped**. Every result state was `Success`, with no per-test errors or warnings.
- Covered full XYZ Auto Motion and Jump Z threshold, exact bridge names/alias rejection/type mismatch, first-update recovery and legacy value preservation, external scalar/vector independence, ShouldMove Z-only acceleration, DeltaTime threshold, presentation math, and all existing Character tests.

### Final scope check

- Only the AnimInstance header/cpp, AnimInstance automation test cpp, and this report were changed by this task.
- No ABP, Court, Sequence, or `UNREAL_RIG` asset was edited/saved. No staging, commit, or push was performed.
- Remaining concern: the bridge's exact spaced FName lookup/write against the actual canonical BP generated class is not runtime-verified because the ABP is intentionally untouched and still needs its separately gated reparenting/migration. Missing/incompatible properties remain non-fatal, warning-and-skip behavior.

## Coverage Follow-up (2026-09-28)

- Task 1 C++ introspection's `FBPVariableDescription::VarName` output is the authority for this bridge's exact property spellings. The bridge retains all 14 confirmed names, including `Previous Location`, `Auto Motion Speed Mps`, and the other spaced FNames; it rejects the unapproved `PreviousLocation` alias. No DisplayName-based reflection is used.
- Expanded `BridgeUsesExactBlueprintNames` to load the canonical ABP generated class, create a transient instance with a valid transient `USkeletalMeshComponent` outer, write/read back `FVector` through the real `Velocity` FProperty, verify the no-space alias cannot mutate `Previous Location`, and verify a FVector write to numeric `GroundSpeed` returns false and leaves its prior numeric value unchanged. No UCLASS test fixture or persistent asset/object was added.
- Added `UpdateMotionOutputs`, a small pure state helper now called by `NativeUpdateAnimation`. Tests demonstrate active external motion overrides only the scalar while `Velocity`/`EffectiveVelocity` remain the selected Auto Motion vector; the non-auto fallback path preserves nonzero `MotionSpeedMps` and its independently selected MovementComponent vector.
- Extended delta-state coverage for NaN DeltaTime (no mutation) and `DeltaSeconds > epsilon` (full XYZ velocity, XY-derived m/s speed, and PreviousLocation advancement).
- Added a near-zero but nonzero Z acceleration case. `ComputeShouldMove` remains unchanged and preserves exact Blueprint `Vector != Zero` semantics.
- A real generated-class bridge test caught and fixed vector property copying: the bridge now calls `CopyCompleteValue` with `ContainerPtrToValuePtr` output, rather than passing a value address as a container.

### Follow-up verification

- UBT required an Editor exit due to Live Coding. Before requesting normal exit, `get_dirty_content_packages()` and `get_dirty_map_packages()` both returned empty.
- The same Editor target build command above succeeded (exit code 0); final incremental build compiled and linked the changed AnimInstance module.
- Restarted Editor and force-discovered the tests. `FutsalMOT.*` total: 11 (8 AnimInstance and 3 Character). All 11 ran: **11 passed, 0 failed, 0 skipped**.
- `BridgeUsesExactBlueprintNames` passed with a warning intentionally produced by its incompatible-type case: `GroundSpeed` is numeric, so a FVector write was skipped as required. Test also verified the value was unchanged.
- No ABP/Court/Sequence/`UNREAL_RIG` changes, saves, staging, commits, or pushes were made.

Remaining concern: transient testing verifies exact generated-class lookup/write without mutating or saving the ABP. The production AnimInstance has not been installed as the canonical ABP parent in this task, so end-to-end graph consumption remains gated on the separately approved ABP migration.

## Scoped Important Findings Follow-up (2026-09-28)

- Canonical default probe was read-only. `BlueprintEditorLibrary.list_member_variable_names` confirmed `Use Auto Motion Speed`; `BlueprintEditorLibrary.get_blueprint_variable_default_value` is unavailable in this UE Python API. Loading `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.ABP_FutsalPlayerBase_C` succeeded, but its Python CDO wrapper could not resolve either exact spaced user variable name or a no-space guess. Therefore the canonical ABP CDO default is **BLOCKED / NOT RELIABLY READ**. Historical `True` values in `PHASE3C_RUNTIME_VALIDATION_REPORT.md` refer to retired `ABP_FutsalSource`, not this canonical ABP. No code default was changed and no asset was saved.
- Added a zero-valued active external speed selector case; active external zero correctly overrides a nonzero legacy scalar.
- Added production-used `CalculateDirectionFromVelocity` wrapper around `UKismetAnimationLibrary::CalculateDirection`. Tests calculate direction from a concrete EffectiveVelocity and Actor rotation, then separately verify orient-to-movement clamping.
- Added production-used `SelectIsFalling` helper and tests for absent MovementComponent, falling, and grounded cases.
- Exact FName bridge list and Task 1 `FBPVariableDescription::VarName` authority are unchanged.

### Verification results

- UBT Editor target build succeeded (exit code 0) after confirming dirty content/map package lists were empty and normally exiting the Editor. The build compiled `FutsalPlayerAnimInstanceTests.cpp`, `Module.FutsalMOT.gen.cpp`, and `FutsalPlayerAnimInstance.cpp`, linked the module, and wrote target metadata.
- Restarted Editor, force-discovered tests, and found 11 total: 8 AnimInstance and 3 Character. Ran all 11: **11 passed, 0 failed, 0 skipped**.
- `BridgeUsesExactBlueprintNames` emitted its expected warning when the incompatible FVector-to-numeric GroundSpeed write was skipped; the test passed after confirming the value remained unchanged.
- No ABP/Court/Sequence/`UNREAL_RIG` edits or saves; no staging, commit, or push.
