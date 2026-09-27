# C++ FutsalPlayerBase Motion Contract Design

## Goal

Introduce a small C++ foundation for the canonical Futsal player so an agent can maintain the motion-source contract in code, while existing Blueprint animation assets and the GRF-to-UE dataset pipeline remain operational.

## Project Context

- Unreal Engine version: 5.8.
- Project: `FustalMOT_UEDataset.uproject`.
- The project currently has no `Source/` directory or C++ game module.
- Canonical Character Blueprint: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase`.
- Canonical AnimBP: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase`.
- Canonical skeletal mesh: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Mesh/SKM_FutsalPlayerBase`.
- Existing locomotion BlendSpace and animation assets remain Blueprint/content assets in this phase.
- BASE-2I baseline commits are already pushed: inner `9fe6a7c0dd84b0fccb613b5736d5d3f746e927d3`, outer `6b35696fb82220074bc13bf4d82be1edbc77b135`.

## Core Product Invariant

This project is a UE-based five-a-side football machine-vision dataset generator. An external trajectory generator determines player positions and facing. UE imports those trajectories, produces plausible skeletal animation, and renders synchronized multi-view, multi-target data.

The trajectory is authoritative:

- Sequencer transform tracks determine Actor world position and facing.
- CharacterMovement and animation must not move, correct, or otherwise alter that authoritative trajectory.
- Motion speed is an animation input describing the trajectory, not an alternate world-motion command.
- The animation system's purpose is plausible visual motion for already-determined trajectories, not player-control gameplay.

## Phase-One Scope

Add a runtime C++ module and a C++ Character base class, `AFutsalPlayerBase`, derived from `ACharacter`. The existing `BP_FutsalPlayerBase` will be reparented to this native base while preserving its Blueprint-authored defaults and component setup. Existing Court actors must remain instances of the canonical Blueprint class and retain their labels, tags, transforms, skeletal mesh, and AnimBP.

The C++ base owns only raw CharacterMovement and explicit external-motion inputs:

- `ExternalMotionActive`: Boolean, default `false`, editable by Sequencer.
- `ExternalMotionSpeedMps`: Float, default `0.0`, editable by Sequencer.
- A Blueprint-readable raw CharacterMovement horizontal speed in m/s (derived from CharacterMovement velocity only).

The final effective-speed selection remains in `ABP_FutsalPlayerBase` for phase one:

1. Meaningful CharacterMovement horizontal speed supplies normal CharacterMovement motion.
2. If CharacterMovement is effectively stationary and `ExternalMotionActive` is true, the AnimBP uses `ExternalMotionSpeedMps`.
3. Otherwise, the AnimBP retains its existing Auto Motion transform-difference speed fallback.
4. If Auto Motion is disabled, preserve the existing canonical `BPI_FutsalPlayerBaseAnimation` fallback.

The C++ class will not set Actor transforms from the external motion properties. It will not drive root motion or CharacterMovement from trajectory speed.

## Blueprint and Animation Boundary

The existing `ABP_FutsalPlayerBase`, AnimGraph, state machines, BlendSpace samples, animation sequences, ControlRig, and IsFalling behavior remain intact. The smallest required AnimBP data-flow change is limited to speed-source selection: cache/read the owning `AFutsalPlayerBase` raw CharacterMovement speed and exact-name external properties, preserve CharacterMovement priority, select external speed when active, and otherwise retain Auto Motion and the canonical explicit fallback.

Direction continues to use the existing trajectory-derived Effective Velocity and Actor rotation. The new speed property controls magnitude only. ShouldMove semantics already repaired for external motion remain unchanged. Jump/Fall/Land and other state-machine behavior are not redesigned.

## Dataset Pipeline Boundary

The inner Python repository remains the official P1/P2 interchange and trajectory import implementation. `PlayerMotionTracker.params["speed_mps"]` is the authoritative per-frame speed source. The official `create_sequence()` writer creates `ExternalMotionActive` and `ExternalMotionSpeedMps` property tracks for all ten canonical player bindings and no such player property tracks for the ball. The speed values must come from the same tracker result already used for facing/yaw.

No trajectory coordinates, timestamps, world conversion, labels, actor mapping, or camera configuration change in phase one. Existing JSONL remains the boundary between the P1 Python 3.9 environment and UE Editor Python.

## C++ Module and Build Integration

Add one runtime module named `FutsalMOT` under `Source/FutsalMOT/` and register it in the `.uproject` with the standard UE 5.8 runtime module rules. The project will require generation of Visual Studio project files and an Editor target build after introducing the first native module. No editor-only dependency is added to the runtime Character class.

Use these exact reflected property identifiers; do not prefix/rename the bool to `bExternalMotionActive`:

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Animation|External Motion")
bool ExternalMotionActive = false;

UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Animation|External Motion", meta=(ClampMin="0.0"))
float ExternalMotionSpeedMps = 0.0f;
```

Preserve explicit defaults in the constructor and verify the native CDO reports false/zero after compile. Do not add a C++ effective-speed getter or motion-source selector in phase one. The only native motion getter is the raw CharacterMovement horizontal speed; final source selection belongs to the AnimBP.

## Compatibility and Migration Strategy

The existing Blueprint asset path remains canonical. It currently owns Blueprint variables named `ExternalMotionActive` and `ExternalMotionSpeedMps`, which collide with the new inherited reflected properties. Before reparenting, snapshot each Blueprint-owned variable's exact identifier, type, default value, category, instance-editable state, Sequencer exposure flag and any other set flags. Remove the Blueprint-owned declarations first, verify both names are absent, then reparent and compile. Never permit UE automatic suffix renaming such as `_0` or `_1`. Verify the inherited native properties retain the exact reflected names, defaults, category and `Interp` visibility. Treat this as a transaction: retain a recoverable copy/snapshot before mutation; on any failure, do not save a partially migrated asset, restore the original parent/declarations/defaults from the snapshot, compile and verify the restored Blueprint, then stop. Reparenting must preserve its other variables, components, mesh and AnimBP assignments. Do not recreate Court actors or change possessable identity. Before any migration, record and compare actor labels, tags, GUIDs, transforms, components, and Sequence binding class metadata.

The C++ source becomes the stable agent-editable owner for runtime motion state. Blueprint-authored presentation remains in the existing assets during this phase. Later phases may migrate AnimBP update logic, pose recorder helpers, or editor automation to C++, each as separate reviewed increments.

## Validation and Acceptance

Phase one is accepted only when:

- The UE 5.8 Editor target compiles with the new runtime module.
- `AFutsalPlayerBase` and the reparented `BP_FutsalPlayerBase` compile.
- Existing Court actors remain ten canonical Blueprint instances with their original labels/tags/transforms and component bindings.
- Existing Sequence possessable bindings continue resolving to those same live actors.
- Official smoke `run_task.py --mode sequence` succeeds and contains Transform, `ExternalMotionActive`, and `ExternalMotionSpeedMps` tracks for all ten players, plus the existing Ball track.
- For representative frames, tracker speed equals the generated Sequence speed key within float tolerance, and effective animation speed in cm/s equals m/s multiplied by 100.
- External speed does not change Actor transform or CharacterMovement velocity.
- A moving and stationary player are checked during actual sequential playback; moving locomotion and stationary Idle are evaluated. Visual cadence is recorded as a separate human-reviewed result where automation cannot judge it.
- Existing Python tests pass with `.futsalmot/local.json` isolated from test path discovery, and that ignored file is restored.
- No protected `UNREAL_RIG.uasset`, retired runtime assets, BlendSpace samples, or trajectory code are changed.
- No unrelated existing workspace modifications are included in either repository's commit.

## Out of Scope

- Full-project C++ rewrite.
- Rewriting AnimGraph/state machines or deleting the AnimBP.
- Modifying animation assets, BlendSpace axes/samples, or Play Rate.
- Moving Actor transforms through C++ or CharacterMovement based on the speed property.
- Replacing Sequencer or the Python dataset import pipeline.
- Retired runtime asset deletion.
- Any changes to the protected `UNREAL_RIG.uasset`.
- Commit/push of implementation work without explicit user confirmation after review and validation.
