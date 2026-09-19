# PROJECT_ARCHITECTURE — FutsalMOT UE 项目架构

- 更新时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `de611502964937e16f92fa06d28f86be0c28a33c`（tag `phase4b2-production-migration`）
- 本文件是项目长期架构说明。历史阶段报告见 `Docs/History/PhaseReports/`。

## 0. Master 定义

```
MASTER_CHARACTER          = /Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase
MASTER_ANIMBP             = /Game/FutsalMOT/Animation/Source/ABP_FutsalSource
MASTER_ANIMATION_SKELETON = /Game/Characters/Mannequins/Meshes/SK_Mannequin
MASTER_PREVIEW_MESH       = /Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple
UNREAL_RIG_ROLE           = APPEARANCE_PROTOTYPE
```

- **Gameplay 层**：`BP_FutsalCharacterBase`（parent `Character`；Mesh/AnimClass 默认 None，由实例或 Appearance 层提供）。
- **Animation 层**：`ABP_FutsalSource`（Target Skeleton `SK_Mannequin`；通过 `BPI_FutsalAnimationSource` 取速度，不反向依赖具体 Character BP）。
- **Skeleton 层**：`SK_Mannequin`。
- **Appearance 层**：不同 Mesh 变体（Quinn 及未来球员 Mesh），经各自骨架/重定向链接入，不进入动画逻辑。

## 1. Production Chain

```
L_FutsalCourt（10 个 Player actor，类 = BP_FutsalCharacterBase_C，来自 __ExternalActors__）
   └─ 每个 actor：Mesh = SKM_Quinn_Simple，AnimClass = ABP_FutsalSource_C（实例属性，非 CDO）
        └─ Character 实现 BPI_FutsalAnimationSource.GetMotionSpeedMps → ABP_FutsalSource
```

- 生产依赖不含 `/Game/ThirdPerson/**`、`/Game/Input/**`、`ABP_FutsalPlayer`、`BP_ThirdPersonCharacter`（Phase 4B2/4C 已验证）。

## 2. Input Chain

```
BP_FutsalPlayerControllerBase（IMC_Futsal_Default / IMC_Futsal_MouseLook）
   └─ BP_FutsalCharacterBase（IA_Futsal_Move / Look / MouseLook / Jump，BPI_FutsalTouchInterface）
```

- 生产输入全部位于 `/Game/FutsalMOT/Input/**`。
- `/Game/Input/**`（Epic 模板输入）已退出生产，仅由 Epic ThirdPerson 遗留链引用（TEMPLATE_BASELINE）。

## 3. Animation Chain

```
SK_Mannequin
   ├─ BS_Futsal_Locomotion（Epic Unarmed 采样 + SK_Mannequin）
   ├─ MM_{Idle,Jump,Land,Fall_Loop}（Epic Unarmed）
   ├─ CR_Mannequin_FootIK（ControlRig，依赖 SK_Mannequin）
   └─ ABP_FutsalSource（Locomotion / Main States 状态机）
        ▲ BPI_FutsalAnimationSource.GetMotionSpeedMps ← BP_FutsalCharacterBase.MotionSpeedMps
```

- 速度双路径语义：`Use Auto Motion Speed ? Auto Motion Speed Mps : MotionSpeedMps`（详见 Phase 3C 报告）。

## 4. Sequence / Data Pipeline

- 生产序列：`/Game/FutsalMOT/Sequences/LS_Cam_01..04 / LS_Cam_Main / LS_Cam_P01`，possess 全部 10 个 Player（类 = `BP_FutsalCharacterBase_C`）+ `Ball_01` + `CineCam_*`。
- Pose 管线 BP：`/Game/FutsalMOT/Blueprints/Pose/**`（Recorder C4_G0..G4 / Legacy、MRQ BurnIn Widget、SaveGame）。
- 数据生成由内层 Python 仓库驱动：`Content/FutsalMOT/code/`（P1 `uv run grf-ue task ...`；P2 `ue/run_task.py`）。

## 5. Appearance Variant Strategy

- 策略：动画逻辑固定在 `SK_Mannequin` + `ABP_FutsalSource`；外观（体型/球衣）以独立 Mesh 变体 + 各自骨架的重定向链接入。
- `UNREAL_RIG` / `UNREAL_RIG_Skeleton` = **APPEARANCE_PROTOTYPE**：只承担外观实验，不承担 AnimBP/Skeleton ownership、State Machine 或 Gameplay 动画逻辑。
- 重定向原型：`IKR_Quinn` → `RTG_Quinn_To_SoccerPlayer` → `IKR_SoccerPlayer` → `UNREAL_RIG`（RTG 仍为已烘焙 `*_Soccer` 的唯一可追溯生成来源）。
- 未接线足球源动画：`/Game/FutsalMOT/Animation/SoccerSource/LS_*_InPlace` ×7（`SK_Mannequin`，0 refs，未来可直接接入动画层）。

## 6. Template Baseline

以下保留作为 UE ThirdPerson Template / Quinn compatibility reference，**不删除、不移动、不修改**：

- `/Game/ThirdPerson/**`（含 `BP_ThirdPersonCharacter`、`BP_ThirdPersonGameMode`、`BP_ThirdPersonPlayerController`、`BP_ThirdPersonCharacter_Soccer`、`Lvl_ThirdPerson`）
- `/Game/Input/**`（`IA_*`、`IMC_*`、Touch UI/Interface）
- `/Game/Characters/Mannequins/**`（`SK_Mannequin`、`SKM_Quinn_Simple`、`SKM_Manny_Simple`、Epic Anim 库、`CR_Mannequin_*`、`ABP_Unarmed`）

> 注意：`SK_Mannequin` / `SKM_Quinn_Simple` / `CR_Mannequin_FootIK` 同时是 Futsal 生产动画链的依赖，属“模板目录中的生产依赖”。

## 7. Test Assets

- `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test` + `/Game/FutsalMOT/Test/GM_FutsalInputTest`：Phase 3C 运行期验证用隔离地图与 GameMode。
- 测试角色 `Player_FutsalBase_Test`：`BP_FutsalCharacterBase_C` + `SKM_Quinn_Simple` + `ABP_FutsalSource_C`。

## 8. Legacy / Experimental

- **ARCHIVE**（退出生产、保留历史）：`ABP_FutsalPlayer`（仍留在原位，见 cleanup 报告）、`/Game/FutsalMOT/_Archive/**`。
- **EXPERIMENTAL**：UNREAL_RIG Appearance 链（`ABP_FutsalPlayer_Soccer`、`BS_Futsal_Locomotion_Soccer`、`*_Soccer`、`IKR_SoccerPlayer`、`RTG_Quinn_To_SoccerPlayer`）、`ABP_SoccerPlayer` / `BP_SoccerPlayer`、`BP_ThirdPersonCharacter_Soccer`、0 引用材质变体。
- 迁移建议（未执行）：待 Appearance Pipeline 定稿后，再解耦 `ABP_FutsalPlayer` / `ABP_FutsalPlayer_Soccer` 对 `BP_ThirdPersonCharacter` 的引用。

## 9. 相关文档

- `Docs/Architecture/ASSET_STRUCTURE.md`：最终资产目录树与分类。
- `Docs/Architecture/PROJECT_CLEANUP_REPORT.md`：Phase 5A 整理报告。
- `Docs/History/PhaseReports/`：Phase 1–4 历史报告。
- `Content/FutsalMOT/code/README.md`、`docs/DATA_CONTRACT.md`、`docs/VALIDATION_AND_LIMITATIONS.md`：数据管线与数据格式。
