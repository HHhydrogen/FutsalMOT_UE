# MPFB Player Production SOP

## Scope

This SOP is the repeatable production path for `Player_N` characters generated with MPFB, prepared in Blender, imported into Unreal Engine, and connected to the shared MPFB Core v1 runtime.

The reference implementation is Player_002, finalized in outer-repository commit `1ceadab` (`Finalize Player_002 production character`). The formal Player_002 assets use the shared Core Skeleton and shared runtime retarget pipeline.

This document describes the final working pipeline. It does not require repeating the Player_002 compatibility and differential audits for every new player unless an actual failure appears.

## Fixed Technical Contract

- Blender source generation workflow: `METRIC / METERS`, `scale_length = 1.0`.
- Original `Human` and `Human.rig` object scales: `1,1,1`.
- Rig type: MPFB Game Engine Rig.
- Internal Game Engine Rig: 53 bones.
- Root hierarchy contract: `Root -> pelvis`.
- Shared UE Skeleton: `/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base`.
- Shared IK Rig: `/Game/FutsalMOT/Characters/MPFB/Core/Retarget/IKR_MPFB_Base`.
- Shared Retargeter: `/Game/FutsalMOT/Characters/MPFB/Core/Retarget/RTG_FutsalPlayerBase_To_MPFB`.
- Shared runtime AnimBP: `/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget`.
- Shared baseline: `/Game/FutsalMOT/Characters/MPFB/Baseline/SK_MPFB_Baseline`.
- Player-specific production Skeleton, IK Rig, Retargeter, and runtime AnimBP are not created.
- The technical conversion is performed only on a temporary Export Copy; source objects and source data remain meter-native.

## Per-Player Design Variables

Each player may independently choose:

- Height and body proportions.
- Body/face parameters.
- Skin, eyes, eyebrows, hair, clothing, and shoes.
- The number of visible skinned meshes.
- The number and purpose of image textures.
- The material layout required by the selected appearance assets.
- Height presets such as Average, Tall, or Short when appropriate for the character design.

Player_002 used the Average preset. That is a character design choice, not a compatibility requirement. A player does not need to match Player_002 height or a fixed value such as 173 cm.

## Blender Workflow

1. Open the new `Player_N` source file.
2. Confirm Scene Units are `METRIC / METERS / 1.0`. If this is not true, stop and resolve the source setup before exporting.
3. Generate the character and complete all appearance choices on the original `Human`: skin, eyes, eyebrows, hair, clothes, shoes, and body/face parameters.
4. Keep the original `Human` and `Human.rig` as the authoritative source. Do not continue major appearance edits after creating an Export Copy unless the copy is regenerated.
5. Confirm the Game Engine Rig exists, has 53 internal bones, and has `Root` as the root bone with `pelvis` below it.
6. Confirm each visible skinned mesh has an Armature modifier targeting the current source rig, vertex groups, and non-zero weights.
7. Measure the BODY mesh using world-space vertex Z values. Use the BODY vertex range as the main scale check. Object Dimensions alone are not a reliable human-height measurement because evaluated modifiers and attached geometry can affect it.
8. Accept a reasonable adult human scale for the character design. Do not enforce a fixed height.

## Export Workflow

1. Create a temporary Export Copy containing one duplicated armature and all current visible meshes that must be exported. The mesh count is character-specific.
2. Duplicate mesh data and armature data for the Export Copy. Remap every Armature modifier to the Export Copy armature.
3. Preserve UVs, materials, vertex groups, weights, geometry, and Shape Keys.
4. Convert only the Export Copy data from meter-valued coordinates to centimeter-valued coordinates:
   - Mesh data: multiply by `100`.
   - Armature data: multiply by `100`.
   - Shape Key coordinates: multiply by `100` when Shape Keys exist.
   - Export Copy object scales remain `1,1,1`.
5. Verify the Export Copy BODY height is approximately `source BODY height * 100` in coordinate values. For Player_002, the source was about `1.69455` and the Export Copy was about `169.455`.
6. During export, ensure the armature wrapper maps to `Human_rig`. Internal bone names and hierarchy remain unchanged.
7. Export only the Export Copy armature and current Export Copy meshes. Do not include the original Human, original rig, camera, lights, or helpers.
8. Use the verified FBX behavior:
   - Global Scale: `1.0`.
   - Add Leaf Bones: off.
   - Bake Animation: off.
   - Path Mode: `COPY`.
   - Embed Textures: on.
   - Axis/Apply Transform details: `NOT VERIFIED` as a stable machine-readable import contract; use the last manually validated Unreal-compatible preset.
9. Explicitly copy only the image files actually used by the current Export Copy materials into:
   `D:\projects\FutsalMOT_blender\characters\Player_N\export\Textures\`.
10. Keep the FBX and texture directory together:
    - `export\MPFB_Player_N.fbx`
    - `export\Textures\...`
11. Restore all temporary wrapper names and remove the temporary Export Copy collection. Save the source file only after confirming the original objects still have scale `1,1,1`, no temporary names remain, and the source Scene Units are unchanged.

## UE Import Workflow

1. Create the formal directory:
   `/Game/FutsalMOT/Characters/MPFB/Players/Player_N/`
2. Prefer the stable layout:
   - `Mesh/`
   - `Materials/`
   - `Textures/`
3. Use the Legacy FBX Importer. UE 5.8 Interchange previously reported valid FBX sources as having no importable content in this project.
4. Import as Skeletal Mesh with Geometry and Skinning Weights.
5. Reuse the shared Skeleton:
   `/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base`
6. Import Animations: off.
7. Import Uniform Scale: `1.0`.
8. Do not use actor scale or guessed import scale to correct a character's design height.
9. Exact Import Data fields such as `Convert Scene`, `Convert Scene Unit`, and `Force Front X Axis` are `NOT VERIFIED` through the current UE 5.8 Python API. Use the last manually validated import preset and do not guess missing values.
10. Do not create a Player_N Skeleton. If the importer cannot reliably reuse the Core Skeleton, stop and use the manual Content Browser import workflow.

## Material Workflow

1. Do not rely on embedded FBX textures to create formal UE Texture2D assets.
2. Import the actual exported image files into:
   `/Game/FutsalMOT/Characters/MPFB/Players/Player_N/Textures/`
3. Create or update only the materials required by the current player in:
   `/Game/FutsalMOT/Characters/MPFB/Players/Player_N/Materials/`
4. Map each Skeletal Mesh Material Slot by its actual semantic section, not by directory order.
5. Connect source-equivalent textures only:
   - Base Color/Diffuse -> Base Color.
   - Normal -> Normal, with Normalmap compression and sRGB off.
   - AO/Mask -> its intended non-color input, with sRGB off.
6. Base Color/Diffuse textures use sRGB on.
7. Configure hair/eyebrow opacity only when the source material actually uses alpha. Do not infer transparency from the asset category.
8. Material count and texture count are per-player. Player_002 ended with 6 materials and 8 textures; Player_N may differ.
9. Keep unused legacy assets separate. Do not force-delete stale materials or textures when UE Asset API deletion fails.

## Runtime Smoke Test

1. Keep the shared runtime unchanged:
   `/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget`
2. Use the existing runtime test environment:
   `/Game/FutsalMOT/Tests/MPFB_Runtime/`
3. Replace only the test visual mesh when a test is needed. Keep the existing Animation Class and component Transform.
4. Run a light PIE smoke test only after formal Mesh, Skeleton, and Materials are ready:
   - Idle.
   - Forward.
   - Stop.
   - Reverse.
   - Turn.
5. Visually inspect body deformation, shoulders, armpits, hips, knees, ankles, clothes, hair, shoes, and materials.
6. Do not repeat full bone audits, reference-pose audits, retarget differential tests, or large animation sampling for every Player_N after the shared contract is established.
7. Do not alter the formal Foot IK system for a new player unless the same concrete foot problem is reproduced.

## Failure Handling

- If Scene Units are not `METRIC / METERS / 1.0`, stop before Export Copy creation.
- If BODY world-space height is clearly outside a reasonable human scale, stop and inspect MPFB generation parameters; do not rescale the source as a workaround.
- If the Game Engine Rig is not 53 bones or `Root -> pelvis` is wrong, stop. Do not rebuild or rename bones automatically.
- If an Export Copy mesh lacks a correct Armature modifier or real weights, stop before export.
- If the wrapper is not `Human_rig`, stop and correct only the temporary Export Copy armature object naming.
- If UE cannot reliably reuse `SKEL_MPFB_Base`, stop and use manual Legacy FBX Importer setup.
- If a UE 5.8 Python/MCP operation fails twice for the same operation, stop with `MANUAL_REQUIRED`; do not cycle through speculative reflection APIs.
- If a material graph cannot be edited safely, keep the asset unchanged and request manual material-editor work.

## Do Not Repeat

1. Do not generate MPFB in centimeters while leaving the Blender Scene declared as meters. This created ambiguous unit semantics.
2. Do not use FBX Global Scale `0.01` as a blind unit compensation.
3. Do not use UE Actor Scale or guessed Import Scale to fix character height.
4. Do not treat `Human` Object Dimensions Z as the sole true human-height measurement.
5. Do not make Player_002's Average preset a universal height or compatibility requirement.
6. Do not require every Player_N to be 173 cm.
7. Do not create a Player-specific IKR, Retargeter, or runtime AnimBP.
8. Do not depend on FBX embedded textures to create formal UE Texture2D assets.
9. Do not keep trying UE 5.8 reflection APIs after two failures of the same operation.
10. Do not repeat complete Skeleton/Retarget audits for every player without an actual compatibility symptom.

## Player_N Checklist

- [ ] MPFB source uses `METRIC / METERS / 1.0`.
- [ ] Character design is complete on the original Human.
- [ ] BODY world-space vertex height is a reasonable human scale for this design.
- [ ] Game Engine Rig exists; 53 bones; `Root -> pelvis`.
- [ ] Every exported mesh has the correct Armature modifier and weights.
- [ ] Export Copy contains one armature and all current visible meshes.
- [ ] Export Copy data and Shape Keys are multiplied by `100`; object scales remain `1,1,1`.
- [ ] Export Copy height is approximately source height times `100`.
- [ ] FBX wrapper is `Human_rig`; no extra leaf bones; no animation.
- [ ] Only Export Copy objects are selected for export.
- [ ] Actual used images are copied to `export/Textures/`.
- [ ] FBX uses Global Scale `1.0`, Path Mode `COPY`, Embed Textures on.
- [ ] UE uses Legacy FBX Importer, Skeletal Mesh, Geometry and Skinning Weights.
- [ ] UE reuses `SKEL_MPFB_Base`; no Player_N Skeleton is created.
- [ ] Formal Player_N textures and materials are created from actual source usage.
- [ ] Material Slots are bound by semantic section.
- [ ] Shared `ABP_MPFB_RuntimeRetarget` remains unchanged.
- [ ] Light Runtime Smoke Test passes: Idle, Forward, Stop, Reverse, Turn.
- [ ] Freeze the Player_N assets and request explicit approval before Git commit/push.

## Known Follow-up Risk

Pose GT logic may select the first SkeletalMeshComponent instead of the visible MPFBVisual component. This is a separate system issue and is not part of Player_N import or material setup.
