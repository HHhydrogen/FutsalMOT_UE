# MPFB Runtime Retarget Test Level Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create an isolated Unreal test level with a free-flying inspection Pawn for observing `BP_FutsalPlayer_MPFB_Test` at runtime.

**Architecture:** All new assets live under `/Game/FutsalMOT/Tests/MPFB_Runtime/`. A `Pawn` with `FloatingPawnMovement` owns camera movement and input; a separate `PlayerController` configures game-only mouse input; a separate `GameMode` spawns only the inspector Pawn. The existing futsal character remains an unpossessed scene Actor.

**Tech Stack:** Unreal Engine 5.8, Unreal Editor Python, Blueprint assets, Enhanced Input, Engine Basic Shapes.

**Spec:** Approved design in the conversation dated 2026-09-29.

## Global Constraints

- Do not modify `FutsalPlayerBase`, `ABP_FutsalPlayerBase`, `IKR_FutsalPlayerBase`, `RTG_FutsalPlayerBase_To_MPFB_Base`, `ABP_MPFB_RuntimeRetarget`, or any formal map.
- Put every new asset under `/Game/FutsalMOT/Tests/MPFB_Runtime/`.
- Do not possess or add input, camera, or movement logic to `BP_FutsalPlayer_MPFB_Test`.
- Do not create the optional TestDriver because the existing public movement/action interface is not confirmed.
- Use real Unreal Python through `futsalmot_tools.FutsalMOTTools`, not the sandboxed programmatic tool.

---

### Task 1: Discover supported Unreal 5.8 asset APIs

**Files:**
- Create: `Content/FutsalMOT/Tests/MPFB_Runtime/create_mpfb_runtime_test.py`

- [ ] **Step 1: Query existing project assets and Unreal API availability**

Use a small `run_python_code` diagnostic to confirm the existing Blueprint path, `unreal.AssetToolsHelpers`, `unreal.EditorAssetLibrary`, Blueprint factory classes, Input Action/Mapping Context factories, and level creation APIs. Return structured JSON and stop on unsupported APIs instead of guessing.

- [ ] **Step 2: Record the confirmed API choices in the creation script**

The script must use explicit asset paths and helper functions for loading classes, creating folders, saving assets, and reporting failures. It must not edit any existing character or retarget asset.

### Task 2: Create isolated materials, input assets, Blueprints, and level

**Files:**
- Modify: `Content/FutsalMOT/Tests/MPFB_Runtime/create_mpfb_runtime_test.py`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/M_MPFB_TestFloor`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/IA_Move`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/IA_Look`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/IA_UpDown`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/IA_Speed`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/IMC_MPFB_Inspect`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/BP_MPFB_InspectPawn`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/BP_MPFB_InspectController`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/BP_MPFB_RuntimeTestGameMode`
- Create via Unreal Editor: `/Game/FutsalMOT/Tests/MPFB_Runtime/L_MPFB_RuntimeTest`

- [ ] **Step 1: Create the folder and simple floor material**

Create `M_MPFB_TestFloor` with a neutral light-gray base color and roughness between `0.7` and `0.9`. Use `/Engine/BasicShapes/Cube` for the floor, scaled to approximately `2000 x 2000 x 20 cm`, centered at `Z=0`.

- [ ] **Step 2: Create independent Enhanced Input assets**

Configure `IA_Move` as a 2D axis action, `IA_Look` as a 2D axis action, `IA_UpDown` as a float action, and `IA_Speed` as a boolean action. Configure `IMC_MPFB_Inspect` for WASD movement, mouse X/Y look, Q/E vertical movement, and Left Shift speed boost. Do not edit project-wide input mappings.

- [ ] **Step 3: Create the inspector Pawn Blueprint**

Create a Blueprint derived from `Pawn` with a Scene Root, child Camera, and `FloatingPawnMovement`. Configure movement speed to `1000 cm/s` and acceleration/deceleration so flight remains controllable. Implement BeginPlay mapping-context registration and Enhanced Input handlers for movement, world-Z movement, yaw, pitch, and Shift speed selection.

- [ ] **Step 4: Create the inspector Controller Blueprint**

Create a Blueprint derived from `PlayerController`. On BeginPlay set `Show Mouse Cursor` false and input mode to Game Only. Do not reference or possess `BP_FutsalPlayer_MPFB_Test`.

- [ ] **Step 5: Create the test GameMode Blueprint**

Create a Blueprint derived from `GameModeBase`, set Player Controller Class to `BP_MPFB_InspectController`, and Default Pawn Class to `BP_MPFB_InspectPawn`. Leave the futsal character out of all default-pawn settings.

- [ ] **Step 6: Create and populate the test level**

Create `L_MPFB_RuntimeTest`, add the floor, Directional Light with movable mobility and side/top rotation, movable Sky Light with real-time capture if supported, Sky Atmosphere, light Exponential Height Fog, Player Start, the existing `BP_FutsalPlayer_MPFB_Test` near `(0,0,100)`, and two thin neutral reference cubes aligned to X and Y. Set the level World Settings GameMode Override to `BP_MPFB_RuntimeTestGameMode`. Explicitly clear Auto Possess Player and Auto Receive Input on the placed futsal character if those properties are exposed.

### Task 3: Save and verify editor state

**Files:**
- Modify: `Content/FutsalMOT/Tests/MPFB_Runtime/create_mpfb_runtime_test.py`

- [ ] **Step 1: Save all created assets and the level**

Save only the new assets and `L_MPFB_RuntimeTest`. Return a JSON report listing every expected asset path and whether it exists after saving.

- [ ] **Step 2: Reload the new level and inspect actors**

Load `/Game/FutsalMOT/Tests/MPFB_Runtime/L_MPFB_RuntimeTest`, enumerate level actors, and verify the placed character class/name, Player Start, floor, lights, atmosphere/fog, reference markers, and absence of any character possession configuration.

- [ ] **Step 3: Start PIE and verify runtime ownership**

Start standard in-viewport PIE. Inspect the runtime player controller and pawn class, verify the possessed Pawn is `BP_MPFB_InspectPawn`, and verify no controller possesses `BP_FutsalPlayer_MPFB_Test`. Read `LogPython`, `LogBlueprint`, and relevant PIE logs for errors or warnings.

- [ ] **Step 4: Stop PIE and produce the final report**

Report asset paths, Enhanced Input usage, actual key bindings, default/boost speeds, character possession status, camera movement result, lighting/floor status, and current warnings/errors. Do not modify retarget or character assets in response to unrelated log noise.

## Verification Commands

- Use `futsalmot_tools.FutsalMOTTools.run_python_file` for the creation/validation script.
- Use `EditorToolset.EditorAppToolset.StartPIE` with `bSimulate=false` and `playMode=PlayMode_InViewPort`.
- Use `EditorToolset.EditorAppToolset.IsPIERunning` before and after runtime checks.
- Use `EditorToolset.LogsToolset` to read current `LogPython`, `LogBlueprint`, and PIE-related messages.
