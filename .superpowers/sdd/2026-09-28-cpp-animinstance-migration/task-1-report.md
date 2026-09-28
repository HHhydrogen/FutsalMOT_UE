# Task 1: ABP Asset Transaction Baseline

Status: COMPLETE WITH CONCERNS; retry established a disk backup duplicate and verified structural parity.

## Scope and safety

- Followed Task 1 only from `Docs/superpowers/plans/2026-09-28-cpp-animinstance-migration.md` and its design document.
- No canonical ABP, Character Blueprint, Map, Sequence, or `UNREAL_RIG` was modified by this task. No duplicate/copy was created because the required source-state and structure checks could not be established.
- No files were staged, committed, or pushed. The only file written by this task is this report.

## Repository boundary snapshot

Commands:

```powershell
git status --short --branch
git submodule status
git diff --cached --name-only
git diff --stat -- Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset
git diff --numstat -- Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset
git -C Content/FutsalMOT/code status --short --branch
git -C Content/FutsalMOT/code rev-parse HEAD
```

Results:

- Outer checkout is `refactor/character-architecture`, ahead of `origin/refactor/character-architecture` by 1, not the branch described in the repository guidance.
- Outer repository already contains extensive staged changes, unstaged deletions/modifications, and untracked paths. Existing staged changes include `BP_FutsalPlayerBase.uasset`, `L_FutsalCourt.umap`, and `LS_Cam_01.uasset`. These were left untouched.
- Canonical ABP is unstaged-modified. Git reports the indexed object size as 523,582 bytes and worktree object size as 526,994 bytes (3,412 bytes difference), not a 994-byte size difference. Binary diff cannot expose its semantic content. No reset or restore was attempted.
- Inner repository is clean on `main...origin/main`; HEAD is `9fe6a7c0dd84b0fccb613b5736d5d3f746e927d3`; submodule status reports the same commit.

## Unreal Editor diagnostics

Tooling used:

- `unreal_list_toolsets`
- `unreal_describe_toolset` for `futsalmot_tools.FutsalMOTTools` and `editor_toolset.toolsets.asset.AssetTools`
- `unreal_call_tool` using `editor_toolset.toolsets.scene.SceneTools.get_current_level`
- `unreal_call_tool` using AssetTools `is_dirty`, `get_dependencies`, `get_asset_tags`, and `find_assets`
- `futsalmot_tools.FutsalMOTTools.run_python_code` in the real Editor Python environment

Current level returned `/Temp/Untitled_0`, not `/Game/FutsalMOT/Maps/L_FutsalCourt`. The ABP backup folder search returned no existing `ABP_FutsalPlayerBase` asset under `/Game/FutsalMOT/Intermediate/CppMigrationBackup/`.

The single-purpose Python diagnostic loaded `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase` successfully as `/Script/Engine.AnimBlueprint`. It established the loaded object path but not that the Editor had been restarted and loaded the current on-disk package after restart. The asset tool reported `is_dirty=false`.

The attempted Python property reads for `parent_class`, `new_variables`, `function_graphs`, `ubergraph_pages`, `animation_graphs`, and `last_compiled_status` each raised “Failed to find property” on `AnimBlueprint`. Therefore no reliable Python baseline was obtained for member variables, graph names/paths/counts, state-machine/transition counts, or compile status. No inferred property names or substitute APIs were used.

Asset registry tags for the ABP returned:

- Generated class: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.ABP_FutsalPlayerBase_C`
- ParentClass and NativeParentClass: `/Script/Engine.AnimInstance`
- Implemented interface graph: `GetMotionSpeedMps`
- Target skeleton: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Skeleton/SK_FutsalPlayerBase`

ABP dependency listing returned:

- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BPI_FutsalPlayerBaseAnimation`
- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Skeleton/SK_FutsalPlayerBase`
- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/BlendSpaces/BS_FutsalPlayerBase_Locomotion`
- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/A_FutsalPlayerBase_MM_Idle`
- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/A_FutsalPlayerBase_MM_Fall_Loop`
- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/A_FutsalPlayerBase_MM_Jump`
- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/A_FutsalPlayerBase_MM_Land`
- `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ControlRig/CR_FutsalPlayerBase_FootIK`
- Engine dependencies: AnimGraph, AnimGraphRuntime, ControlRig, and ControlRigDeveloper.

Canonical Character Blueprint asset tags show:

- ParentClass and NativeParentClass are `/Script/FutsalMOT.FutsalPlayerBase`.
- Generated class is `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase_C`.
- FiB metadata contains the canonical ABP reference `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase`.
- Full actor component/default metadata and current Court actor snapshots were not collected because the active level is the temporary empty level.

Sequence dependency listing identifies `/Game/FutsalMOT/Maps/L_FutsalCourt`, `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase`, and `/Game/FutsalMOT/Blueprints/BP_FutsalBall`, along with CinematicCamera, MovieSceneTracks, MovieScene, and LevelSequence modules. It does not expose binding count or property track names; those remain unverified.

## Backup and verification

- Backup path intended by Task 1: a unique asset below `/Game/FutsalMOT/Intermediate/CppMigrationBackup/`.
- First attempt actual backup path: none; no asset was duplicated.
- First attempt canonical-versus-backup parity: not run because no backup or readable variable/graph baseline was available. See retry results below for the completed backup and parity verification.
- First attempt called no duplicate API and introduced no asset/package side effect.

## Retry after blocker ruling (2026-09-28)

The original findings above are retained as the first attempt record. The controller loaded the canonical level before this retry.

### Current Editor state and canonical ABP

- `SceneTools.get_current_level` now returns `/Game/FutsalMOT/Maps/L_FutsalCourt`.
- `AssetTools.is_dirty` for canonical ABP returns `false`; `AssetTools.get_asset_tags` reports GeneratedClass `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.ABP_FutsalPlayerBase_C`, ParentClass/NativeParentClass `/Script/Engine.AnimInstance`, and the expected target skeleton.
- Real Editor Python `unreal.load_asset` returned the canonical asset path and `/Script/Engine.AnimBlueprint` class. `BlueprintEditorLibrary.get_blueprint_parent_class`, `list_member_variable_names(blueprint, False)`, `list_graph_names`, and `list_graphs` all succeeded. The parent is `/Script/Engine.AnimInstance`.
- The 18 Blueprint-owned member variables are `Character`, `MovementComponent`, `Velocity`, `GroundSpeed`, `Direction`, `ShouldMove`, `IsFalling`, `MotionSpeedMps`, `Previous Location`, `Auto Motion Speed Mps`, `Speed Initialized`, `Use Auto Motion Speed`, `Effective Motion Speed Mps`, `Auto Motion Velocity`, `Effective Velocity`, `Auto Facing Yaw Deg`, `CurrentAnimationClass`, and `Velocity_0`.
- There are 19 editable graph entries. Main graph names: `AnimGraph`, `EventGraph`, `GetMotionSpeedMps`; nested graph names include state machines `Locomotion` and `Main States`, states `Idle`, `Walk / Run`, `Locomotion`, `Jump`, `Fall Loop`, `Land`, and eight `Transition` graphs. Graph paths and classes were captured from `list_graphs`; two state-machine graphs and eight transition graphs were observed. See the successful Python output in the UE log for the full paths.
- Canonical ABP remains not dirty. Its indexed/worktree size difference remains 3,412 bytes as recorded above; the worktree package was not reset or overwritten.

### Court and Sequence read-only baseline

- Real Editor Python enumerated exactly 10 actors whose generated class is canonical `BP_FutsalPlayerBase`: labels `Player_L0`, `Player_L1`, `Player_L2`, `Player_L3`, `Player_L4`, `Player_R0`, `Player_R1`, `Player_R2`, `Player_R3`, `Player_R4`.
- Each reports mesh `/Game/FutsalMOT/Characters/FutsalPlayerBase/Mesh/SKM_FutsalPlayerBase.SKM_FutsalPlayerBase`. Per-actor object names, translations, quaternion rotations, and scale were captured in the successful Python diagnostic. The player poses include the lineup at Z=90 and observed transform placements at ground-level / midfield positions; no actor was changed.
- `LS_Cam_01` has 12 readable bindings: the 10 named players, `Ball_01`, and `CineCam_01`. Each player has `MovieScene3DTransformTrack` (`变换`), `MovieSceneBoolTrack` (`ExternalMotionActive`), and `MovieSceneFloatTrack` (`ExternalMotionSpeedMps`), each with a section. Ball and camera have Transform tracks. No sequence mutation was performed.

### Recovery duplicate

- Before duplication, `AssetTools.find_assets` returned no matching asset in `/Game/FutsalMOT/Intermediate/CppMigrationBackup/`; the selected timestamp-suffixed target was also explicitly checked absent.
- Canonical was loaded via `unreal.load_asset`; `unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name, package_path, original_object)` returned a new `AnimBlueprint` object. The duplicate was saved using `unreal.EditorAssetLibrary.save_asset(backup_path, False)` only; canonical was not saved.
- Unique backup: `/Game/FutsalMOT/Intermediate/CppMigrationBackup/ABP_FutsalPlayerBase_CppMigrationBaseline_20260928_114854`.
- Post-save `AssetTools.is_dirty` reports `false`; `AssetTools.get_asset_tags` resolves its own GeneratedClass and ParentClass `/Script/Engine.AnimInstance`. Filesystem `Get-Item` confirmed a `.uasset` exists at `Content/FutsalMOT/Intermediate/CppMigrationBackup/ABP_FutsalPlayerBase_CppMigrationBaseline_20260928_114854.uasset`.
- Re-read parity before save: canonical and backup both class `/Script/Engine.AnimBlueprint`; parent equal; all 18 member variable names equal in order; all 19 graph names equal in order; all graph name/class pairs equal in order. After save, backup loaded successfully from the asset path and remained not dirty. This verifies structural/class parity; it does not compare every graph node payload or compile status.

### Retry concerns and limits

1. The known binary difference is still 3,412 bytes and its semantic cause is unresolved. The duplicate was made from the loaded canonical object with `is_dirty=false`; no disk overwrite of canonical occurred.
2. `BlueprintEditorLibrary` graph/member reads worked, but no reliable AnimBlueprint compile-status property was exposed; compile status is unverified.
3. Sequence binding names and track classes/names/sections were readable; actor resolution IDs and channel/key payloads were not reliably serialized by the attempted diagnostic, and no claims about key values are made.
4. An attempted backup-only `save_asset` emitted UE warnings about unresolved real properties on the duplicate generated class, but returned and the resulting backup exists on disk, reports not dirty, and asset-registry tags and subsequent loading resolve correctly. Inspect/compile the backup in Editor if stronger package validation is required before any later mutation.
5. Outer workspace's existing staged/unstaged changes and modified `UNREAL_RIG.uasset` remain untouched; no stage, commit, or push occurred.

## Initial attempt blockers and recommendation (superseded by retry where noted)

1. The active Editor level is `/Temp/Untitled_0`; Court actors and Sequence bindings cannot be baselined in this session.
2. The required post-restart/current-disk-load condition for duplicating the canonical ABP is unproven.
3. UE Python property access did not expose the AnimBlueprint parent/variables/graphs/compile status. Asset registry metadata only partially describes the asset and is insufficient for safe parity validation.
4. The actual binary size delta is 3,412 bytes; its meaning is unresolved. Preserve this worktree version unchanged.
5. The workspace already has broad staged and unstaged changes, including staged Character/Map/Sequence changes and a modified `UNREAL_RIG.uasset`; none were altered here.

These initial blockers were addressed for the retry by loading the Court level and using BlueprintEditorLibrary. Remaining concerns are listed under “Retry concerns and limits”; the 3,412-byte difference and compile/key-payload questions remain unresolved.

## Review finding fix round (2026-09-28)

Scope was limited to Editor/process diagnostics, canonical package reload, and backup-only compilation/inspection. No C++ implementation was performed; no canonical ABP, Court, Sequence, or `UNREAL_RIG` was intentionally edited, and no stage/commit/push was performed.

### Editor process and canonical disk reload evidence

- PowerShell command: `Get-CimInstance Win32_Process -Filter "name = 'UnrealEditor.exe'" | Select-Object ProcessId,CreationDate,ExecutablePath,CommandLine`.
- Active process: PID `27504`, CreationDate `2026-09-28 10:10:11`, executable `E:\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe`. The editor was not closed/restarted because it is an active user Editor session; the safe API reload route was used instead.
- UE 5.8 Python API inspection confirmed `EditorLoadingAndSavingUtils.reload_packages(packages, interaction_mode)` exists and `ReloadPackagesInteractionMode.ASSUME_NEGATIVE` is available. The canonical package was not reported dirty immediately before reload by the prior AssetTools check. Reload call returned `(True, Text(""))`; subsequent `unreal.load_asset` returned canonical path `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.ABP_FutsalPlayerBase` with class `/Script/Engine.AnimBlueprint`.
- This reload evidence establishes the package reload call succeeded, but does not prove that bytes were re-read from the filesystem: the object was still loaded through dependent references and `load_asset` resolves already-loaded objects. No direct package byte hash was captured before/after reload. The 3,412-byte worktree difference was not reset, copied over, or intentionally saved.

### Backup-only compile and logs

- Compiled only `/Game/FutsalMOT/Intermediate/CppMigrationBackup/ABP_FutsalPlayerBase_CppMigrationBaseline_20260928_114854` through `unreal.BlueprintEditorLibrary.compile_blueprint(backup)`; return value was `True`.
- `LogBlueprint` query matching `CppMigrationBaseline|ABP_FutsalPlayerBase|warning|Warning|error|Error` returned the backup compile line `[2026.09.28-03.48.54:198] LogBlueprint: Compiling Blueprint '/Game/FutsalMOT/Intermediate/CppMigrationBackup/ABP_FutsalPlayerBase_CppMigrationBaseline_20260928_114854...'` and no matching warning/error lines for that backup compile.
- `LogKismet` and `LogAnimGraph` queries returned “Log category ... not found” in this Editor build. `LogKismetCompiler` was also not registered. Therefore there is no category-specific evidence for those categories; the available `LogBlueprint` query found no backup-specific warnings/errors.
- UE emitted property-read warnings during the earlier backup save/compile workflow saying generated-class “real” properties `Character` and `MovementComponent` could not be read. These are recorded as Editor warnings, not compile errors. Compile-only returned success. No save call was made in this fix round.

### Variable names, pin types, and mapping limit

- `BlueprintEditorLibrary.list_member_variable_names(ABP, False)` returned the same 18 names recorded in the retry section. `get_member_variable_type(ABP, name).export_text()` returned useful pin-type declarations. Confirmed type categories:
  - Objects: `Character` is `/Script/Engine.Character`; `MovementComponent` is `/Script/Engine.CharacterMovementComponent`.
  - Vector structs: `Velocity`, `Previous Location`, `Auto Motion Velocity`, `Effective Velocity`, `Velocity_0` are `/Script/CoreUObject.Vector`.
  - `GroundSpeed`, `Direction`, `MotionSpeedMps`, `Auto Motion Speed Mps`, `Effective Motion Speed Mps`, `Auto Facing Yaw Deg` are `real`/`double`.
  - `ShouldMove`, `IsFalling`, `Speed Initialized`, `Use Auto Motion Speed` are `bool`; `CurrentAnimationClass` is `int`.
- The returned member-name strings preserve display-style spacing. API output did not expose a separate internal FName for entries such as `Previous Location`, `Auto Motion Speed Mps`, or `Speed Initialized`. Do not assume a no-space FName (for example `PreviousLocation`) from presentation text.
- Attempted generated-class reflection with `find_property_by_name` and `get_editor_property` was unavailable/failed: the Python-wrapped `AnimBlueprintGeneratedClass` exposes neither `find_property_by_name` nor the user-defined fields through `get_editor_property`. `EdGraphPinType` exposes `export_text`, but its reflected fields are not individually exposed in this environment.
- Consequently, exact internal FNames and per-node variable-reference mapping from the spaced Blueprint display names to candidate native C++ identifiers are **BLOCKED / UNCONFIRMED**. In particular, no evidence currently confirms whether graph nodes resolve `Previous Location` to a C++ property named `PreviousLocation`, nor corresponding Auto Motion Speed Mps / Speed Initialized identifiers or external-motion fields. Graph node names and graph structures are known, but node pin references were not decoded in this fix round. Do not infer or use guessed mappings for the migration gate.

### Canonical/backup post-check and repository state

- Re-read after backup compile: canonical and backup both `/Script/Engine.AnimBlueprint`, parent `/Script/Engine.AnimInstance`, 18 member names, and 19 graph entries. Their ordered `(graph name, graph class)` signatures were identical. The entries include two `AnimationStateMachineGraph` graphs and eight `AnimationTransitionGraph` graphs.
- Canonical dirty check after reload/compile attempt: UE `AssetTools.is_dirty` had returned `false` before prior operations; a final concise Python dirty-state read failed because `EditorAssetLibrary.is_dirty` does not exist in the Python API. No `AssetTools.is_dirty` final call was made after reload. Thus post-operation canonical not-dirty status remains unverified by the final check; canonical reload returned success and no canonical save was called in this fix round.
- Final repository check commands: `git status --short --branch`, `git diff --cached --name-only`, `git diff --stat -- Content/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.uasset`, `git status --short -- Content/FutsalMOT/Intermediate/CppMigrationBackup .superpowers/sdd/2026-09-28-cpp-animinstance-migration/task-1-report.md`, and inner `git -C Content/FutsalMOT/code status --short --branch`.
- The pre-existing staged name list remains the same as first recorded: BP, Court Map, Sequence, audit, project file, and existing C++ checkpoint files. Canonical ABP remains unstaged-modified and diff stat remains indexed 523,582 bytes to worktree 526,994 bytes. Inner repository remains clean at the previously recorded commit. Report remains untracked; backup is an ignored UE intermediate asset. The pre-existing `UNREAL_RIG.uasset` modification remains present. No paths were staged by this fix round.

### Remaining review concerns

1. Process restart was avoided to preserve the active user Editor. The supported reload API reported success, but a direct disk reread/hash proof is unavailable; current-source freshness is not fully established.
2. Backup Blueprint compile returned true, but native `LogKismet`/`LogAnimGraph` categories are absent and prior generated-class property-read warnings remain. Full visual/node-level compile validation is not claimed.
3. Exact internal FName and Blueprint graph-node to native C++ variable name mappings, especially the spaced names and external variables, remain a migration blocker. Resolve with a UE API that exposes `FBPVariableDescription.VarName` and variable-get/set node references, or a controlled editor inspection, before implementing/reparenting.
4. A final post-reload canonical dirty-state check through AssetTools and a filesystem hash/size confirmation were not obtained in this fix round. No canonical save was issued.

## Final evidence attempt (2026-09-28)

Status: BLOCKED for exact internal FName and node-binding transcription; no implementation or canonical asset mutation was performed.

### Read-only APIs attempted

- `futsalmot_tools.FutsalMOTTools.run_python_code` in the real UE 5.8 Editor Python environment.
- `unreal.BlueprintEditorLibrary.list_graphs(ABP)` returned all 19 graph objects. The graph objects expose `get_graph_nodes_of_class`, but their `Nodes` property is protected and cannot be read through `get_editor_property`.
- `unreal.BlueprintEditorLibrary.list_member_variable_names(ABP, False)` continued to return the 18 presentation/display names recorded above.
- `AnimBlueprint.get_editor_property('NewVariables')` was attempted. UE reported that `NewVariables` is protected; lowercase `new_variables` is not a readable property. `parent_class`, `function_graphs`, `ubergraph_pages`, `animation_graphs`, and `graphs` likewise were not readable properties.
- The loaded `AnimBlueprintGeneratedClass` exposes no readable property collection through `get_editor_property`; candidate `properties`, `Property`, `new_variables`, and `NewVariables` paths failed.
- `get_graph_nodes_of_class` was attempted for `EdGraphNode`, `K2Node_VariableGet`, `K2Node_VariableSet`, `K2Node_CallFunction`, and `AnimGraphNode_BlendSpacePlayer`. The first four returned zero nodes through the public wrapper. The BlendSpace query returned one node in the `Walk / Run` state graph, but its pins were not serializable because the wrapped pin object has no `get_name` method. This does not provide EventGraph variable references.
- `BlueprintTools` exposes graph DSL read/write, but no separate read-only variable-description or node-binding API. Graph DSL was not written or used to reconstruct anything.
- `ObjectTools.list_properties`/`get_properties` are object reflection helpers, but do not expose the protected `FBPVariableDescription` array or the inaccessible graph `Nodes` array. No write-capable ObjectTools or BlueprintTools operation was called.
- Slate inspection was available, but no Editor UI was opened or changed during this attempt; the API probes did not establish an exact FName, so no UI transcription was fabricated.

### Confirmed evidence

- The canonical asset is `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase` and remains parented to `/Script/Engine.AnimInstance`.
- The Blueprint-owned display names remain exactly: `Character`, `MovementComponent`, `Velocity`, `GroundSpeed`, `Direction`, `ShouldMove`, `IsFalling`, `MotionSpeedMps`, `Previous Location`, `Auto Motion Speed Mps`, `Speed Initialized`, `Use Auto Motion Speed`, `Effective Motion Speed Mps`, `Auto Motion Velocity`, `Effective Velocity`, `Auto Facing Yaw Deg`, `CurrentAnimationClass`, and `Velocity_0`.
- The public graph enumeration remains 19 entries, including `AnimGraph`, `EventGraph`, `GetMotionSpeedMps`, state machines `Locomotion` and `Main States`, their state graphs, and eight transition graphs. This confirms graph identity only, not variable pin bindings.
- The final UE log diagnostic recorded: `BlueprintEditorLibrary.list_graphs returned 19 graphs; AnimBlueprint NewVariables protected; generated-class property reflection unavailable; EventGraph public node enumeration returned zero variable get/set/call nodes; exact FName and node bindings remain unresolved.`

### Exact requested fields and binding result

| Display name | Exact `FBPVariableDescription.VarName` | EventGraph/AnimGraph node binding |
|---|---|---|
| `Previous Location` | BLOCKED | BLOCKED |
| `Auto Motion Speed Mps` | BLOCKED | BLOCKED |
| `Speed Initialized` | BLOCKED | BLOCKED |
| `MotionSpeedMps` | BLOCKED | BLOCKED |
| `Effective Motion Speed Mps` | BLOCKED | BLOCKED |
| `Auto Motion Velocity` | BLOCKED | BLOCKED |
| `Effective Velocity` | BLOCKED | BLOCKED |
| `Velocity` | BLOCKED | BLOCKED |
| `GroundSpeed` | BLOCKED | BLOCKED |
| `Direction` | BLOCKED | BLOCKED |
| `ShouldMove` | BLOCKED | BLOCKED |
| `IsFalling` | BLOCKED | BLOCKED |

The display strings must not be treated as internal FNames. In particular, this evidence does not prove that `Previous Location` maps to `PreviousLocation`, nor establish the corresponding no-space identifiers for the other spaced names. It also does not prove whether any graph node resolves to a Blueprint-owned field, an inherited native field, a temporary autogenerated field, or a suffixed collision name.

### Conclusion and minimum unblock evidence

Task 1 remains **BLOCKED** for the requested exact FName/node-binding evidence. No safe basis exists to choose native C++ reflected identifiers, remove colliding Blueprint variables, or claim that the EventGraph/AnimGraph bindings will survive reparenting. The canonical ABP, backup, C++ implementation files, and other implementation assets were not modified by this attempt; no stage, commit, or push was performed.

The minimum user-provided Editor evidence to unblock this narrow gate is a read-only capture from the canonical ABP opened in the Blueprint Editor showing, for each requested field: (1) the My Blueprint variable entry or Details panel field that displays the underlying variable name/FName, including any autogenerated suffix, and (2) the EventGraph/AnimGraph node Details panel or pin tooltip for every reference to that field. A single screenshot is insufficient if references are off-screen; the capture must include the variable identifier and enough graph context to associate each get/set/property-access node with its graph. An Editor-side Python/C++ diagnostic that directly serializes `FBPVariableDescription.VarName` and each variable-reference node's member/property name would satisfy the same requirement without screenshots.
