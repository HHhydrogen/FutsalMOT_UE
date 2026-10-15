# MPFB Episode Appearance Generator Design

## Status

Design approved in conversation on 2026-10-12. This document records the approved design for review before implementation planning. No implementation is included here.

## Purpose

Generate one reproducible visual identity assignment for every player in a GRF episode, then apply that assignment in Unreal Engine for the episode's annotations and renders.

The trajectory and appearance are bound together by the episode root seed and the SHA-256 of `frames.jsonl`. A repeated export with the same task inputs and asset catalog produces the same trajectory and appearance assignment. Appearance randomness uses separate namespaces and cannot alter the GRF random stream.

## Goals

- Use the existing GRF task export as the single-episode generation entry point.
- Assign one of Player_003–009 to each of the ten player entities, sampling with replacement.
- Independently assign one of the nine imported male skin textures to each player, sampling with replacement.
- Assign four different Jersey/Shorts Set IDs from Set_01–05 to left outfield, right outfield, left goalkeeper, and right goalkeeper kits.
- Keep a player's mesh, skin, and kit assignment fixed for the full episode and across all cameras.
- Persist the realized assignment and its source hashes with the episode; Unreal consumes this record and never re-rolls it.
- Apply appearance changes temporarily in the current Editor session, restore the prior actor state after work finishes, and do not save randomized External Actor packages.
- Preserve existing track IDs, mask IDs, actor mapping, shared Skeleton, and animation/retarget contracts.

## Non-Goals

- Dataset-level batch scheduling or automatic episode-count orchestration.
- Generating new meshes, hair, facial morphs, skin textures, jersey designs, or arbitrary RGB color values.
- Changing the GRF scenario, AI policy, trajectory sampling, or the existing `futsalmot_seed_v1` derivation.
- Replacing the legacy static `ue.player_visuals` configuration for existing tasks.
- Changing actor mapping, track IDs, mask IDs, camera configuration, or annotation semantics.
- Guaranteeing that independently sampled episodes have different appearances. Different seeds can legitimately select the same assets.

## Existing Project Contracts

- P1 runs in the Python 3.9 `uv` environment. P2 runs in Unreal Editor Python. JSON is the only supported interface between them.
- `task export` writes `meta.json`, `frames.jsonl`, and task provenance into the episode directory.
- `meta.entities` provides stable `L0..L4` and `R0..R4` IDs, team, role, and `is_goalkeeper` values. The appearance generator uses this metadata and does not assume that a goalkeeper is always entity index 4.
- `meta.randomness` already contains `root_seed` and `ue_visual_seed`. The latter is currently recorded but not consumed.
- Player_003–009 use `/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base` and the shared runtime retarget contract. Their hair mesh/material assets are player-specific.
- The shared MPFB library contains nine male skin Texture2D assets and five Jersey/Shorts material pairs. The imported player meshes retain seven material slots.
- `ue.player_visuals` currently assigns meshes by entity and writes a static profile provenance file. It does not randomize skin or kits and currently saves changed External Actor packages. The appearance path must replace that persistence behavior with a temporary application transaction.

## Approaches Considered

1. **Generate appearance during `task export` (selected).** P1 writes the trajectory and the exact appearance manifest together. P2 validates and applies that manifest. This keeps one episode task authoritative and makes the trajectory/appearance relationship auditable.
2. **Generate appearance with a separate prepare command.** This separates concerns but introduces another artifact that can be paired with the wrong task or trajectory.
3. **Randomize only in Unreal from a seed.** This hides the realized assignment from P1, complicates audit and recovery, and risks re-sampling on retry. It is not selected.

## Configuration and Asset Catalog

Add an optional `ue.appearance` block to the single task config. If omitted, the task retains current behavior. The first supported mode is `seeded`; it requires a complete explicit catalog. Existing `ue.player_visuals` remains valid for legacy static assignments. A task must not enable both `ue.appearance` and `ue.player_visuals` at once.

The catalog contains:

- Policy ID `futsalmot_appearance_v1`.
- Catalog ID/version, initially `mpfb_players_003_009_v1`.
- Seven player profiles, each containing player ID, Skeletal Mesh path, shared AnimBP path, shared Skeleton path, and the established visual component attachment/relative-transform contract.
- Nine `{skin_id, texture}` entries for the imported male skin Texture2D assets.
- Five `{set_id, jersey_material, shorts_material}` entries for the shared Set_01–05 materials.
- The Body texture parameter contract required to create a dynamic material instance. Its exact parameter name must be established by inspecting and validating `M_MPFB_Body`; implementation must not guess it.

The catalog is part of the task input and contributes to a canonical SHA-256 `catalog_fingerprint`. P1 validates schema, unique IDs, complete candidate counts, and `/Game/` paths. P1 cannot prove that Unreal assets exist or that material parameters and mesh slots are compatible; P2 performs those checks before mutating actors.

Example shape (paths abbreviated for readability):

```json
{
  "ue": {
    "appearance": {
      "mode": "seeded",
      "policy": "futsalmot_appearance_v1",
      "catalog_id": "mpfb_players_003_009_v1",
      "models": [
        {
          "player_id": 3,
          "mesh": "/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003",
          "anim_class": "/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget",
          "skeleton": "/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base"
        }
      ],
      "skins": [
        {
          "skin_id": "young-african-dark",
          "texture": "/Game/FutsalMOT/Characters/MPFB/Textures/Skins/Male/T_MPFB_Skin_Young_African_Dark"
        }
      ],
      "kits": [
        {
          "set_id": "01",
          "jersey_material": "/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_Jersey_Set_01",
          "shorts_material": "/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_Shorts_Set_01"
        }
      ],
      "body_texture_parameter": "<verified material interface>"
    }
  }
}
```

The example is illustrative, not a complete runnable catalog. A production task includes all seven models, all nine skins, all five kit pairs, and the verified Body texture parameter.

## Randomness and Reproducibility

GRF continues to use the existing `grf_game_engine_seed` derived by `futsalmot_seed_v1`. The appearance generator consumes the already-recorded `ue_visual_seed`; it does not call or mutate Python's global `random` or NumPy random state.

Appearance policy `futsalmot_appearance_v1` derives three independent integer seeds from `ue_visual_seed`. For namespace `N`, hash the UTF-8 bytes of `futsalmot_appearance_v1:<ue_visual_seed>:<N>` with SHA-256, read the first four digest bytes as an unsigned big-endian integer, then apply `& 0x7fffffff`. The seed derivation and selection algorithm are versioned parts of the data contract. Candidate selection uses stable SHA-256 ranking rather than Python's process-randomized `hash()` or a global RNG:

- For each entity and candidate, rank the candidate by the SHA-256 digest of the UTF-8 bytes of `futsalmot_appearance_v1:rank:<namespace>:<namespace_seed>:<entity_id>:<candidate_id>`. Select the candidate with the lexicographically smallest `(digest_bytes, candidate_id)` pair.
- Independently repeat the same process with the skin namespace and skin candidates.
- Rank each kit Set ID using the same format with namespace `kit` and entity ID `kit`; select the first four ranked IDs and assign them in a fixed class order: left outfield, right outfield, left goalkeeper, right goalkeeper. The four selected Set IDs are distinct, and Jersey/Shorts always use the same Set ID.

This produces stable results across processes and machines without relying on iteration order or Python RNG implementation details. The actual model, skin, and kit assignment is written to the manifest; P2 does not derive it again.

Within one episode, each entity's assignment is constant for every frame and camera. Across episodes, each task's root seed independently determines the assignments. Sampling is with replacement for player models and skin textures; repeated assets within an episode are expected and allowed.

## Episode Appearance Manifest

After `frames.jsonl` and `meta.json` are successfully written, `task export` creates `provenance/appearance.json` atomically. It records:

- Schema ID and manifest version.
- Episode ID, root seed, `ue_visual_seed`, appearance policy, and the three namespace seeds.
- Raw SHA-256 of the exact `frames.jsonl` bytes.
- Catalog ID/version and canonical catalog fingerprint.
- The fixed four-class kit-to-Set mapping.
- One record for each of the ten entities, containing entity ID, team, goalkeeper flag, kit class, selected player profile ID, selected mesh path, skin ID/texture path, and jersey/shorts material paths and Set ID.
- A canonical fingerprint over the manifest content excluding its own fingerprint field.

P1 validates that the entity set is exactly `L0..L4` and `R0..R4`, each team has exactly one goalkeeper, every entity has exactly one valid model and skin selection, the four kit Set IDs are distinct, and the trajectory hash matches the file being exported. Missing or ambiguous goalkeeper metadata is an export error when seeded appearance is enabled.

P1 writes to a temporary file in the same directory, flushes and closes it, then replaces `appearance.json`. A failed generation must not leave a partial manifest. Re-running an identical export is idempotent. Re-exporting a changed trajectory/config produces a new manifest bound to the new trajectory hash; P2 rejects any stale manifest or application report whose hash differs from current `frames.jsonl`.

## Data Flow

1. `task validate` validates the optional appearance configuration and candidate catalog structure.
2. `task export` runs GRF using the existing root seed and writes the episode as it does today.
3. P1 reads the new episode metadata, derives appearance namespace seeds, samples assignments, computes hashes, and writes `provenance/appearance.json`.
4. `task ue-command` continues to produce the UE invocation. No independent UE randomization step is added.
5. `run_task.py` loads and validates the appearance manifest against the current task, episode metadata, trajectory hash, and asset catalog before sequence/annotation/render work.
6. UE preflight resolves the ten actors through the existing actor mapping, validates the asset and material-slot contracts, and captures an in-memory rollback snapshot for all affected components.
7. UE applies all ten assignments as one transaction. Sequence creation, geometry annotation, RGB, Object-ID Mask, and Runtime Pose rendering observe the same appearance assignment.
8. On synchronous completion, failure, or asynchronous MRQ completion/failure, UE restores the original actor mesh, material overrides, animation/attachment state, and temporary material instances.
9. UE writes an application report containing manifest fingerprint, trajectory hash, per-entity applied assets/slots, operation status, render job status, and restoration status. Audit validates that report against the manifest before treating the rendered episode as appearance-complete.

## Unreal Application Contract

### Preflight

Before changing actors, P2 must verify:

- Current level is `/Game/FutsalMOT/Maps/L_FutsalCourt`.
- Every mapped player label resolves to exactly one actor and all ten expected IDs are present.
- The appearance manifest has exactly the ten expected entities and references the current trajectory hash and catalog fingerprint.
- Each selected mesh, AnimBP, Skeleton, texture, jersey material, and shorts material loads and has the expected Unreal class.
- Every selected player mesh uses the shared `SKEL_MPFB_Base`; the shared runtime AnimBP remains compatible.
- Material slot count and semantic slot names identify exactly one Body, Jersey, and Shorts slot and preserve the character-specific hair slot and other existing face/shoe slots. Do not infer slots from array position alone.
- The Body source material has the explicitly verified texture parameter, and the selected skin Texture2D can be assigned through that interface.
- All ten actors' relevant External Actor packages are clean before application. If any is already dirty, fail before mutation to avoid overwriting unrelated unsaved editor work.

Any failed check prevents all mutation and prevents Sequence/MRQ submission. The error names the entity, asset, slot, or contract that failed.

### Apply and Restore

- Build a full rollback snapshot before mutation, including the original visual mesh, animation class, attachment and relative transform, each material slot/override, and package dirty state.
- Change only the visible MPFB visual component. Preserve the locomotion driver, actor transform, Pose tags, capsule, actor mapping, Skeleton, and shared retarget system.
- Assign the selected mesh and player hair assets with that mesh's existing slot layout. Create an actor-local dynamic material instance for the Body slot and set the selected skin texture through the verified parameter. Assign the selected Jersey and Shorts materials to their semantic slots. Preserve other material slots.
- Do not create or save permanent combination materials. Dynamic instances and component overrides exist only for the current Editor session.
- If any assignment fails, restore every already-mutated actor and do not start downstream processing.
- Never call an asset save operation for randomized External Actors. Restore the original package dirty state after restoring component state. If UE 5.8 cannot restore the original clean state through a verified API, fail closed before using this workflow and resolve that editor API constraint first.
- Write `provenance/appearance_application.json` with a `prepared` state before submitting MRQ, then update it to `restored` only after every actor has been restored and all MRQ jobs have settled. This report contains portable UE asset/actor identifiers, not machine-local filesystem paths.

The transaction applies for `full`, `render`, and `annotations` modes for as long as the mode reads actor appearance or evaluates poses. For `sequence` mode, restore after sequence construction because the sequence stores motion bindings, not the randomized material state. `pose-finalize` consumes already-captured runtime data and does not reapply appearance.

### MRQ Lifecycle and Recovery

MRQ is asynchronous. The application transaction remains active until every submitted camera job has reached a terminal success/failure/cancel state. A non-blocking completion callback/watchdog restores appearance after the final job settles; the Editor main thread must continue ticking. Submission errors and synchronous exceptions restore immediately.

Before mutation, persist the rollback snapshot under the ignored local runtime directory `.futsalmot/runtime/<task_id>/appearance-rollback.json`; it is not episode provenance and is not included in dataset manifests. If the Editor process terminates before a callback can run, randomized state has not been intentionally saved, so reopening the map should load its saved baseline. A subsequent task invocation checks for a stale `prepared` application report, verifies that the current actor state matches the saved baseline, restores from the snapshot if necessary, and only then permits a new application. It must not silently overwrite an unresolved recovery record. If assets or actors needed for recovery are unavailable, stop with a recoverable error and retain the report/snapshot.

The report distinguishes `not_started`, `preflight_failed`, `applied`, `rendering`, `restored`, and `restore_failed`. It includes per-camera MRQ terminal status, manifest fingerprint, trajectory hash, and exact applied asset/slot paths. `restored` is required before the episode passes the appearance audit.

## Failure Behavior

- Invalid task catalog or seed metadata: P1 validation/export fails before writing a final appearance manifest.
- Invalid entity roster or goalkeeper metadata: P1 appearance generation fails; it does not guess a goalkeeper by index.
- Existing files with a different root seed or catalog: a newly requested export may regenerate trajectory and manifest together; P2 never accepts a manifest whose trajectory/catalog fingerprints do not match current inputs.
- Missing or changed Unreal assets, skeleton mismatch, unknown material slot, or missing Body texture parameter: preflight fails before actor mutation.
- Partial actor application: restore the full snapshot, record failure, and do not create/render the episode.
- MRQ failure/cancel: wait for terminal job state, restore all actors, record the MRQ failure and restoration result; the dataset audit fails.
- Restore failure: retain rollback snapshot and fail the run. Do not save or continue with another randomized appearance.
- Pre-existing dirty External Actor package: fail preflight without touching user changes.

## Validation and Acceptance

### P1 tests

- Same root seed, episode metadata, and catalog produce byte-stable manifest assignments and fingerprints across independent processes.
- Changing the appearance namespace input cannot affect GRF seed derivation or trajectory export. Tests verify stable outputs for fixed inputs without requiring every changed seed to produce a different sampled asset, since random collisions are valid.
- Model and skin are sampled independently and allow repeats.
- Four distinct kit Set IDs are selected and map to the fixed kit-class order; jersey and shorts use the same selected Set ID.
- Goalkeeper grouping follows `meta.entities.is_goalkeeper`, not a hard-coded entity index; missing, duplicate, or wrong-team goalkeeper metadata fails.
- Invalid/duplicate catalog IDs, incomplete asset pools, malformed paths, unsupported policy, and stale trajectory hashes fail validation.
- Legacy tasks without `ue.appearance` preserve current behavior; configs that combine seeded appearance and static `player_visuals` are rejected.

### UE Editor validation

- Use Unreal MCP to inspect the current map, ten actor mappings, seven material-slot semantics, shared Skeleton, exact selected assets, and `M_MPFB_Body` parameter before any write.
- Test apply/rollback on a short episode and verify all ten actors' effective mesh/material state before and after; verify no External Actor package is saved or left dirty when it was initially clean.
- Confirm a failure injected at a mid-roster entity restores the full roster and does not submit MRQ.
- Confirm asynchronous multi-camera success, failure, and cancellation all reach a terminal report and restore actors without blocking the Editor.
- Render a short Smoke episode and visually inspect that the four kit classes are distinguishable, skin/hair/model assignments are present, and RGB, Object-ID Mask, and Runtime Pose remain aligned.
- Confirm the episode appearance report's manifest and trajectory fingerprints match `provenance/appearance.json` and `frames.jsonl`; require restored state in Audit.

The short visual smoke is necessary because unit tests and asset-path checks cannot establish actual material parameter behavior, slot semantics, MRQ callback behavior, or final rendered appearance.

## Implementation Boundaries

- P1 implementation belongs to the inner `Content/FutsalMOT/code/` submodule and must follow its Python 3.9, JSON boundary, Chinese technical documentation, and test requirements.
- UE assets and Editor Python integration belong to the outer UE repository. Any material interface change must be validated in Unreal Editor and preserve the shared MPFB asset contracts.
- The UE task must use the configured Unreal MCP and real Editor Python workflow. No UE Python module is run from P1's `.venv`.
- The work is single-episode only. Dataset batch generation can be designed separately after the episode contract is validated.
- No commit or push is part of this design approval; each repository's changes require separate review and explicit user confirmation before committing or pushing.
