# SDD ledger — plan: Docs/superpowers/plans/2026-09-28-cpp-animinstance-migration.md

## Preflight scan

| Item | Shared files/interfaces | Finding | Ruling |
|---|---|---|---|
| Task 1 -> Task 2 | ABP baseline -> native test contract | Baseline must establish current names/defaults before tests bind them. | Execute Task 1 first; no ABP mutation. |
| Task 2 -> Task 3 | `FutsalPlayerAnimInstance` math/test API | Tests intentionally reference APIs implemented in Task 3. | RED build is required before implementation. |
| Task 3 -> Task 5 | Native reflected names -> ABP inherited bindings | Exact names must remain stable; parent switch depends on compiled class. | Stop on any collision/suffix or compile error. |
| Task 4 -> Task 5 | ABP backup -> ABP mutation | Asset mutation is destructive/reversible only through verified UE duplicate. | No mutation without backup parity and compile gate. |
| Task 5 -> Task 6 | ABP parent/AnimClass -> Character/Court | Character and Sequence identity depend on canonical ABP path remaining stable. | Validate before any map/sequence save. |
| Task 6 -> Task 7 | Sequence tracks/actor state -> runtime checks | Runtime samples must use unchanged bindings and transform authority. | Treat transform/track changes as a stop condition. |
| Task 7 -> Task 8 | Validation results -> audit | Audit must report only observed PASS/BLOCKED results. | No claims for unrun visual checks. |

| Task | Internal consistency | Finding |
|---|---|---|
| 1 | Consistent | Read-only baseline and backup gate precede code/asset mutation. |
| 2 | Consistent | Tests intentionally fail before Task 3; pure helper contracts are explicit. |
| 3 | Consistent | Native update publishes exact variables consumed by retained graphs. |
| 4 | Consistent | Current 994-byte ABP difference is preserved and gated. |
| 5 | Consistent | Focused parent/variable/EventGraph migration excludes graph topology edits. |
| 6 | Consistent | Character/Court/Sequence checks are read/compile validation only. |
| 7 | Consistent | Runtime acceptance records actual acceleration-dependent ShouldMove behavior. |
| 8 | Consistent | Audit and status review occur without staging/commit/push. |

## Rulings

- Ruling: Do not create commits during delegated execution — repository instructions require explicit user confirmation before commit/push, which overrides the generic plan template. Agents must leave changes in the shared worktree and report exact diffs.
- Ruling: Do not create a second worktree — the live UE Editor/MCP session and user-approved shared workspace are required for asset verification; delegated agents operate sequentially in this workspace.
- Ruling: Do not begin Tasks 2-3 until exact Blueprint internal variable names and graph-node bindings are evidenced — the current API only exposes display-style names with spaces, and guessing native property names could cause inherited-property collisions or stale node bindings. Cost if wrong: ABP reparenting could silently bind the wrong variables or create suffixed properties, invalidating the migration.

Task 1: complete for introspection gate (no commit; temporary Editor diagnostic removed). Read-only C++ diagnostic established exact `FBPVariableDescription::VarName` values, variable-node/function-node bindings, complete nested graph inventory, canonical/backup structural signature match, and canonical/backup dirty state NO. The previous source-freshness limitation remains documented: package reload was used instead of a full Editor restart; no asset was saved.

- Ruling: Treat the C++ diagnostic's `FBPVariableDescription::VarName` output as the naming authority — all ABP-owned animation variables use their exact spaced names (`Previous Location`, `Auto Motion Speed Mps`, `Speed Initialized`, etc.). Cost if wrong: later native property declarations would bind incorrectly; the diagnostic directly reads the engine struct and node references, so this is lower risk than display-name inference.
- Ruling: Do not use `FBPVariableDescription::DefaultValue` as the ABP default authority — all returned strings are empty, so defaults are stored elsewhere. Preserve the known CDO/default evidence from prior UE checks and verify native defaults independently.

Task 2: pending — exact spaced Blueprint variable names and node bindings are now available from Saved/CppMigrationDiagnostics; native reflected properties must use those exact names or an explicit compatibility strategy.

- Ruling: The review claim that spaced FNames remain unverified is incorrect. The temporary C++ diagnostic directly enumerated `FBPVariableDescription::VarName` and `FMemberReference::GetMemberName()` for canonical and backup; both reported the same exact spaced names, and the output recorded `VARIABLE_AND_GRAPH_NODE_SIGNATURE_MATCH=YES`. The bridge allowlist uses those exact names. Cost if wrong: generated-class lookup could still differ at runtime, so canonical generated-class lookup remains an explicit later ABP gate.

Task 2/3: complete after review fix round; Editor target build succeeded and 11/11 AnimInstance+Character tests passed, review clean with one Important residual deferred: canonical `Use Auto Motion Speed` default remains unreadable through current Python API. Before ABP save, preserve/read that BP-owned exact FName from the current AnimBlueprint generated-class CDO and use it to initialize the native selector; if that read cannot be verified, stop before asset save.

- Ruling: Use the read-only C++ Editor CDO result as the canonical default authority: exact property `Use Auto Motion Speed`, Bool, default `true`; canonical package remained not dirty. Cost if wrong: selector fallback behavior could change after BP variable removal; the CDO query used the exact generated-class FName and made no asset changes.
- Temporary CDO diagnostic module was removed from Source/Target/.uproject after use. Task 2/3 implementation remains uncommitted and unstaged beyond pre-existing staged versions of shared files.

Task 2/3: complete (UBT succeeded; 11/11 tests passed; scoped review PASS/PASS with canonical ABP integration explicitly pending).

Task 4: in progress — canonical/backup structural checks, both clean in Editor, canonical still has preserved 3,412-byte Git worktree difference. No ABP mutation authorized until current-source backup and topology/reference parity are reconfirmed.

Task 4: partial / manual gate. UE 5.8 source order is proven: NativeUpdateAnimation -> BlueprintUpdateAnimation -> NativeThreadSafeUpdateAnimation -> BlueprintThreadSafeUpdateAnimation -> AnimGraph proxy Update/evaluation. Existing EventGraph remains an active later writer, so DOUBLE_WRITER_RISK=YES. Transient duplicate parent change compiled BS_UP_TO_DATE, all 14 reflection bridge properties resolved, transient CDO bridge write/readback passed, canonical dirty before/after NO. Transient runtime EventGraph comparison was not run because no valid SkeletalMeshComponent-backed AnimInstance could be constructed without a crash; canonical ABP was not changed or saved. Required next step: controlled GUI/local editor retirement of only legacy initialization/update writer nodes, with all state machines and AnimGraph untouched; do not reparent/save canonical until that gate is performed and verified.

Task 4 final: PARTIAL — canonical reparent/save/reload completed and structural gates passed; runtime Court/Sequence values remained zero in the available editor sampling path despite Sequence setting ExternalMotionActive and a nonzero external speed during middle-frame transient evaluation. State-machine/BlendSpace live acceptance is therefore not claimed. Temporary Editor verifier removed; no stage/commit/push.

Task 4R: BLOCKED/PARTIAL — real SkeletalMeshComponent-backed AnimInstances were observed executing `NativeUpdateAnimation` continuously with `componentOuter=CharacterMesh0`; final formal PIE/game-world identity and Player_R0 same-frame external-speed readback were not established. Continuous Sequencer/PIE sampling showed external active/nonzero values at some evaluation points, but the same native diagnostic sample for Player_R0 remained zero; do not classify as successful animation consumer validation. Temporary runtime probes removed; canonical ABP, Map, Sequence clean; no stage/commit/push.

Task 4R-2: BLOCKED — PIE was started and native updates ran on real SkeletalMeshComponent-backed instances; however, a deterministic same-PIE-world `LS_Cam_01` SequencePlayer-to-Player_R0 binding identity and sustained nonzero Player_R0 speed series were not obtained. Editor/transient sampling showed `ExternalMotionActive=true` and nonzero Sequence speed at some evaluations, while same-frame Player_R0 native values stayed zero; no failure classification A-F can be asserted without the required world/object identity trace. Formal state-machine/BlendSpace consumer validation is not claimed. Runtime probes removed; ABP parent/status/18 vars/19 graphs remain persisted and clean; no stage/commit/push.

## Manual FootIK A/B Result

- The canonical AnimGraph ControlRig node was temporarily set to `Alpha=0.0`; no AnimGraph links, state machines, BlendSpace, ControlRig asset, Sequence, Map, or rig asset were changed.
- Human visual acceptance on `LS_Cam_Long_30s`, Player_R0 window frames 68-147: foot motion returned to normal and the prior foot-sticking/sliding symptom disappeared.
- Ruling: FootIK ground-trace/PBIK output is the confirmed primary cause of the abnormal lower-body result under Sequencer-authoritative Actor motion. Cost if wrong: disabling FootIK removes intended ground adaptation; the current state is accepted for this phase because the human visual check confirms the required animation behavior.
- Temporary diagnostic module/probes were removed. Canonical ABP remains compiled and clean after the A/B save; no staging, commit, or push.
