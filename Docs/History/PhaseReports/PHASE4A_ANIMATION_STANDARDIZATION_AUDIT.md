# PHASE4A_ANIMATION_STANDARDIZATION_AUDIT — Animation Asset Cleanup & Quinn Standardization

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `ad11a5e8f771bbceebe2bbdc9afcd3acdb2e1c2e`（tag `phase3c-source-animbp-runtime`）
- 性质：**READ-ONLY AUDIT**。本阶段未修改、未创建、未重命名、未移动、未删除任何资产；未 Fix Redirectors / Consolidate；未 Save 任何已有资产；未 stage / commit / tag。
- 唯一写入：本报告文件。
- 引擎：UE 5.8。

核心目标架构决策（本审计据此评估）：

```
MASTER_ANIMATION_SKELETON = SK_Mannequin
MASTER_ANIMBP            = ABP_FutsalSource
MASTER_CHARACTER         = BP_FutsalCharacterBase
UNREAL_RIG_ROLE          = APPEARANCE_PROTOTYPE
```

---

## 0. 结论速览

| 问题 | 结论 |
|---|---|
| 主动画骨架 | `SK_Mannequin`（115 referencers），已由 `ABP_FutsalSource` 运行时验证 |
| 主动画蓝图 | `ABP_FutsalSource`（`BS_UP_TO_DATE`，已解除 `BP_ThirdPersonCharacter` 硬依赖，refs=`[Test map]`） |
| 主角色蓝图 | `BP_FutsalCharacterBase`（parent `Character`，Mesh/AnimClass 默认 None，依赖 `BPI_FutsalAnimationSource`） |
| **项目运行入口是否仍依赖 `BP_ThirdPersonCharacter`** | **是**。`L_FutsalCourt` 的 10 个 Player actor 类为 `BP_ThirdPersonCharacter_C`，另有 6 条 `LS_Cam_*` possessable 绑定 |
| `UNREAL_RIG` 定位 | Appearance Prototype（外观/球衣/体型实验）；不是动画根资产 |
| 未接线足球源动画 | `SoccerSource/LS_*_InPlace` × 7，**0 引用**（含“保留原因/未来接入方式”） |
| 骨架迁移 | `SKELETON_MIGRATION = NOT_STARTED` |

---

## 1. STEP 1 — Skeleton Ownership Matrix

共 2 个 Skeleton。

| Skeleton | 类别 | Referencers | 使用 Mesh | 使用 AnimBP | 使用 AnimSequence | 使用 Retargeter | 使用 IK Rig |
|---|---|---|---|---|---|---|---|
| `/Game/Characters/Mannequins/Meshes/SK_Mannequin` | **A. 主标准骨架** | **115** | `SKM_Quinn_Simple` | `ABP_Unarmed`, `ABP_FutsalPlayer`, `ABP_FutsalSource` | 全部 Epic Unarmed/Pistol/Rifle/… + Futsal `SoccerSource/LS_*` ×7（共 ~106） | （经 Mesh 间接，非直接） | （经 Mesh 间接，非直接） |
| `/Game/FutsalMOT/Characters/FutsalPlayer/Skeleton/UNREAL_RIG_Skeleton` | **B. 非标准骨架（Appearance Prototype）** | **24** | `UNREAL_RIG` | `ABP_FutsalPlayer_Soccer`, `ABP_SoccerPlayer` | `*_Soccer` ×20 | （经 Mesh 间接，非直接） | （经 Mesh 间接，非直接） |

补充（Skeleton 不直接引用 IK/RTG，链路经 Mesh）：
- `IKR_Quinn` 依赖 `SKM_Quinn_Simple`（= SK_Mannequin）；`IKR_SoccerPlayer` 依赖 `UNREAL_RIG`（= UNREAL_RIG_Skeleton）。
- `SK_Mannequin` 的 referencers 还包含：`BS_Futsal_Locomotion`、`BS_Idle_Walk_Run`、`CR_Mannequin_FootIK`、`CR_Mannequin_Procedural`、`AO_Pistol`、`AO_Rifle`、`MM_Pistol_Fire_Montage`。

---

## 2. STEP 2 — AnimBP Inventory

| AnimBP | Path | Target Skeleton | Variables | State Machines | Referencers | Mesh 兼容 | 关键依赖 | 分类 |
|---|---|---|---|---|---|---|---|---|
| `ABP_FutsalSource` | `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource` | **SK_Mannequin** | 17（Character, MotionSpeedMps, Use Auto Motion Speed, Effective Motion Speed Mps, …） | `Locomotion{Idle,Walk/Run}` + `Main States{Locomotion,Jump,Fall Loop,Land}` | `[Test map]` | `SKM_Quinn_Simple` ✅ | `BPI_FutsalAnimationSource`, `BS_Futsal_Locomotion`, `SK_Mannequin`, `CR_Mannequin_FootIK`, MM_*（**无** BP_ThirdPersonCharacter） | **KEEP （MASTER_ANIMBP）** |
| `ABP_FutsalPlayer` | `/Game/FutsalMOT/Animation/ABP_FutsalPlayer` | SK_Mannequin | 17（同上） | 同 `ABP_FutsalSource` | `[BP_ThirdPersonCharacter]` | `SKM_Quinn_Simple` ✅ | 同上 **+ `BP_ThirdPersonCharacter`** | **FUTURE_MIGRATION_CANDIDATE**（由 `ABP_FutsalSource` 取代） |
| `ABP_FutsalPlayer_Soccer` | `/Game/FutsalMOT/Animation/SoccerPlayer/ABP_FutsalPlayer_Soccer` | **UNREAL_RIG_Skeleton** | 17（同上） | 同 `ABP_FutsalSource` | `[BP_ThirdPersonCharacter_Soccer]` + 5×`L_FutsalCourt` external actor | `UNREAL_RIG` ✅ | `BP_ThirdPersonCharacter`, `BS_Futsal_Locomotion_Soccer`, `*_Soccer`, `CR_Mannequin_FootIK`（**骨架错配隐患**） | **EXPERIMENTAL** |
| `ABP_SoccerPlayer` | `/Game/FutsalMOT/Characters/FutsalPlayer/ABP_SoccerPlayer` | UNREAL_RIG_Skeleton | **0** | **无**（仅 AnimGraph+EventGraph） | `[BP_SoccerPlayer]` | — | `UNREAL_RIG_Skeleton`, `/Script/AnimGraph` | **EXPERIMENTAL （stub）** |
| `ABP_Unarmed` | `/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed` | SK_Mannequin | Epic | Epic | Epic | `SKM_Quinn_Simple`/`SKM_Manny_Simple` | `CR_Mannequin_FootIK` | LEGACY_EPIC_TEMPLATE |

- `ABP_FutsalPlayer` 与 `ABP_FutsalSource` 的 Variables / Graphs / StateMachine / Transition 名称集合逐项相同（Phase 3B 已证），唯一差异是 `MotionSpeedMps` 来源与 Cast 目标。
- `ABP_FutsalSource` 仅被测试地图引用；`ABP_FutsalPlayer` 被 `BP_ThirdPersonCharacter` 引用；`ABP_FutsalPlayer_Soccer` 被 `BP_ThirdPersonCharacter_Soccer` 与 5 个 `L_FutsalCourt` external actor 引用。

---

## 3. STEP 3 — Character Blueprint Inventory

| Blueprint | Parent Class | Mesh Default | AnimClass Default | Implemented Interface | 关键依赖 | Level Referencers |
|---|---|---|---|---|---|---|
| `BP_FutsalCharacterBase` | **`Character`** | **None** | **None** | `BPI_FutsalAnimationSource`、`BPI_FutsalTouchInterface` | `BPI_FutsalAnimationSource`、`IA_Futsal_*` | `//Game/FutsalMOT/Test/L_FutsalCharacterBase_Test` |
| `BP_ThirdPersonCharacter` | `Character` | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `BPI_TouchInterface` | `SKM_Quinn_Simple`, `ABP_FutsalPlayer`, `/Game/Input/*` | `ABP_FutsalPlayer`, `ABP_FutsalPlayer_Soccer`, 6×`LS_Cam_*`, `BP_ThirdPersonCharacter_Soccer`, `BP_ThirdPersonGameMode`, **10×`L_FutsalCourt` external actor** |
| `BP_ThirdPersonCharacter_Soccer` | `BP_ThirdPersonCharacter_C` | `UNREAL_RIG` | `ABP_FutsalPlayer_Soccer_C` | （继承） | `ABP_FutsalPlayer_Soccer`, `UNREAL_RIG`, `BP_ThirdPersonCharacter` | `[]` |
| `BP_SoccerPlayer` | `Character` | `UNREAL_RIG` | `ABP_SoccerPlayer_C` | — | `ABP_SoccerPlayer`, `UNREAL_RIG`, `MI_Player_TShirt_Test`, `/DatasmithContent/Materials/Water/MI_Pool_01` | `[]` |
| `BP_FutsalPlayerControllerBase` | `PlayerController` | — | — | — | `IMC_Futsal_Default`, `IMC_Futsal_MouseLook` | `GM_FutsalInputTest` |
| `GM_FutsalInputTest` | `GameModeBase` | — | — | — | `BP_FutsalPlayerControllerBase` | `L_FutsalCharacterBase_Test` |
| `BP_NoPawnGameMode` | `GameModeBase` | — | — | — | — | `L_FutsalCourt` |
| `BP_ThirdPersonGameMode` | `GameModeBase` | — | — | — | `BP_ThirdPersonCharacter`, `BP_ThirdPersonPlayerController` | `//Game/ThirdPerson/Lvl_ThirdPerson`（Epic 模板图） |

**重点确认 — 项目运行入口对 `BP_ThirdPersonCharacter` 的依赖：仍是（YES）。**

- `L_FutsalCourt` 中 10 个 Player actor（`Player_L0~L4`、`Player_R0~R4`）的 **Actor 类是 `BP_ThirdPersonCharacter_C`**（external actor 包）。
- 6 条 `LS_Cam_01/02/03/04/Main/P01` 的 possessable 绑定类为 `BP_ThirdPersonCharacter`。
- `L_FutsalCourt` 的 GameMode 为 `BP_NoPawnGameMode`（不依赖 ThirdPerson），但 Actor/Sequence 层仍依赖 `BP_ThirdPersonCharacter`。
- ⇒ 全面切换到 `BP_FutsalCharacterBase` 之前，运行入口依赖未完全解除。

---

## 4. STEP 4 — Animation Asset Ownership

### 4.1 BlendSpace

| 资产 | Skeleton | Referencers | 分类 |
|---|---|---|---|
| `/Game/FutsalMOT/Animation/BS_Futsal_Locomotion` | SK_Mannequin | `ABP_FutsalPlayer`, `ABP_FutsalSource` | **MASTER_ANIMATION_LIBRARY** |
| `/Game/FutsalMOT/Animation/SoccerPlayer/BS_Futsal_Locomotion_Soccer` | UNREAL_RIG_Skeleton | `ABP_FutsalPlayer_Soccer` | **UNREAL_RIG_EXPERIMENT** |
| `/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run` | SK_Mannequin | Epic `ABP_Unarmed` | LEGACY_EPIC_TEMPLATE |

### 4.2 AnimSequence

| 组 | 数量 | Skeleton | Referencers | 分类 |
|---|---|---|---|---|
| Epic Unarmed / Pistol / Rifle / Death / HitReact 等 | 97（`/Game/Characters/Mannequins/**`） | SK_Mannequin | Epic/模板 | LEGACY_EPIC_TEMPLATE |
| `SoccerPlayer/*_Soccer`（Idle/Jump/Land/Fall + Jog/Walk ×16） | 20 | UNREAL_RIG_Skeleton | `ABP_FutsalPlayer_Soccer`、`BS_Futsal_Locomotion_Soccer` | **UNREAL_RIG_EXPERIMENT** |
| `SoccerSource/LS_*_InPlace` | 7 | SK_Mannequin | **0** | **SOCCER_EXPERIMENT（未接线）** |

Futsal 自有 AnimSequence 合计 27（20 `*_Soccer` + 7 `LS_*`）。

### 4.3 未接线足球源动画（重点）

| 资产 | Skeleton | Referencers | 保留原因 | 未来接入方式（建议，不实施） |
|---|---|---|---|---|
| `LS_Backpedal_InPlace` | SK_Mannequin | 0 | 真实足球动作（backpedal），Epic Unarmed 无对应 | 作为 `BS_Futsal_Locomotion` 的额外象限/方向采样，或扩展为专用 BlendSpace |
| `LS_DefenseJog_F_InPlace` | SK_Mannequin | 0 | 防守 jog | 同上（防守段/位移状态） |
| `LS_DefenseSprintFast_InPlace` | SK_Mannequin | 0 | 快速防守冲刺 | 同上（高速段） |
| `LS_GoalkeeperShuffleL_InPlace` | SK_Mannequin | 0 | 门将横移（左） | 门将专用状态机/BlendSpace |
| `LS_GoalkeeperShuffleR_InPlace` | SK_Mannequin | 0 | 门将横移（右） | 门将专用状态机/BlendSpace |
| `LS_Pivot90L_InPlace` | SK_Mannequin | 0 | 90° 转身（左） | 转向/pivot 状态 |
| `LS_Pivot90R_InPlace` | SK_Mannequin | 0 | 90° 转身（右） | 转向/pivot 状态 |

- 全部位于 `SK_Mannequin`，与 MASTER skeleton 一致，**未来无需重定向**即可接入 `ABP_FutsalSource`。
- 0 引用**不代表可删**：属未接线的 Futsal 自有动作资产，应保留待接入。

### 4.4 Montage / AimOffset / ControlRig / IK

| 资产 | 类 | Referencers | 分类 |
|---|---|---|---|
| `MM_Pistol_Fire_Montage` | AnimMontage | Epic | LEGACY_EPIC_TEMPLATE |
| `AO_Pistol` / `AO_Rifle` | AimOffsetBlendSpace | Epic | LEGACY_EPIC_TEMPLATE |
| `CR_Mannequin_FootIK` | ControlRigBlueprint | `ABP_Unarmed`, `ABP_FutsalPlayer`, `ABP_FutsalPlayer_Soccer`, `ABP_FutsalSource` | **MASTER_ANIMATION_LIBRARY（FootIK）** |
| `CR_Mannequin_Procedural` | ControlRigBlueprint | `[]` | LEGACY_EPIC_TEMPLATE（未使用） |
| `CR_Mannequin_Body` | ControlRigBlueprint | Epic | LEGACY_EPIC_TEMPLATE |
| `IKR_Quinn` | IKRigDefinition | `RTG_Quinn_To_SoccerPlayer` | **MASTER_ANIMATION_LIBRARY（Retarget 源）** |
| `IKR_SoccerPlayer` | IKRigDefinition | `RTG_Quinn_To_SoccerPlayer` | UNREAL_RIG_EXPERIMENT |
| `RTG_Quinn_To_SoccerPlayer` | IKRetargeter | `[]` | UNREAL_RIG_EXPERIMENT（`*_Soccer` 唯一可追溯生成源） |

---

## 5. STEP 5 — Retarget Chain Audit

```
SOURCE ANIMATION     Epic Unarmed（SK_Mannequin）
        ↓
SOURCE SKELETON      SK_Mannequin  /  SKM_Quinn_Simple
        ↓
SOURCE IK RIG        IKR_Quinn          （preview_skeletal_mesh = SKM_Quinn_Simple）
        ↓
IK RETARGETER        RTG_Quinn_To_SoccerPlayer
        ↓
TARGET IK RIG        IKR_SoccerPlayer   （preview_skeletal_mesh = UNREAL_RIG）
        ↓
TARGET SKELETON      UNREAL_RIG_Skeleton
        ↓
TARGET MESH          UNREAL_RIG
        ↓
BAKED ASSETS         *_Soccer ×20 + BS_Futsal_Locomotion_Soccer
```

实测依赖：
- `IKR_Quinn` → `SKM_Quinn_Simple` + `/Script/IKRig`；refs = `[RTG_Quinn_To_SoccerPlayer]`
- `IKR_SoccerPlayer` → `UNREAL_RIG` + `/Script/IKRig`；refs = `[RTG_Quinn_To_SoccerPlayer]`
- `RTG_Quinn_To_SoccerPlayer` → `SKM_Quinn_Simple` + `IKR_Quinn` + `IKR_SoccerPlayer` + `UNREAL_RIG` + `/Script/IKRig`；**refs = `[]`**

判断（是否适合作为未来 Appearance Pipeline）：
- **方向正确**：`SK_Mannequin → UNREAL_RIG` 的 source→target 重定向链完整，`RTG` 是 `*_Soccer` 的**唯一可追溯生成来源**。
- **但当前目标骨架 `UNREAL_RIG_Skeleton` 不作为动画根**：若采用 `SK_Mannequin` 为 MASTER，则“Quinn → 未来球员 Mesh”的正确方向应改为 **以 `SK_Mannequin` 为 source、以各外观 Mesh 的骨架为 target** 的通用重定向链。
- 结论：可作为 **Appearance Pipeline 的原型**，但需要为“未来球员 Mesh”新增对应的 IKRig/RTG（**本阶段不创建、不修改**）。

---

## 6. STEP 6 — FootIK / ControlRig Audit

| 项 | `CR_Mannequin_FootIK` |
|---|---|
| Path | `/Game/Characters/Mannequins/Rigs/CR_Mannequin_FootIK` |
| Class | ControlRigBlueprint |
| Preview Mesh | `SKM_Manny_Simple` |
| 依赖 Skeleton | **`SK_Mannequin`**（+ `SKM_Manny_Simple`） |
| Referenced By | `ABP_Unarmed`、`ABP_FutsalPlayer`、**`ABP_FutsalSource`**、`ABP_FutsalPlayer_Soccer` |

兼容性判断：
- 对 **`ABP_FutsalSource` + `SK_Mannequin`**：**兼容**（该 CR 依赖 `SK_Mannequin`；Phase 3C 人工 PIE 未观察到可见 FootIK 异常）。
- 对 **`UNREAL_RIG` / `ABP_FutsalPlayer_Soccer`（UNREAL_RIG_Skeleton）**：**存在骨架错配风险**——CR 为 Mannequin 骨骼编写，未随 skeleton 替换；在 `ABP_FutsalPlayer_Soccer` 上属潜在风险残留。
- 是否实际在 AnimGraph 执行路径 / 是否有 Warning：Python/MCP 不可读 AnimGraph 连线语义，标 **UNKNOWN**（需目视/截图）。
- **未修复、未修改**。

---

## 7. STEP 7 — Final Architecture Proposal

```
                 Gameplay Layer
        ┌──────────────────────────────┐
        │     BP_FutsalCharacterBase   │  (parent: Character; Mesh/AnimClass 默认 None)
        └──────────────┬───────────────┘
                       │ implements
                       ▼
                 Animation Layer
        ┌──────────────────────────────┐
        │       ABP_FutsalSource       │  (Target Skeleton = SK_Mannequin)
        └──────────────┬───────────────┘
                       │ animates
                       ▼
                 Skeleton Layer
        ┌──────────────────────────────┐
        │        SK_Mannequin          │  (MASTER_ANIMATION_SKELETON)
        └──────────────┬───────────────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
        Quinn Mesh          Future Player Mesh
     (SKM_Quinn_Simple)   (Appearance variants)
                       ▲
                       │
                 Appearance Layer
        UNREAL_RIG = APPEARANCE_PROTOTYPE
        （球衣外观 / 球员体型 / 数据集丰富度实验）
        不负责：AnimBP ownership / Skeleton ownership / State Machine / Gameplay Animation Logic
```

要点：
- Gameplay 层只暴露 `BPI_FutsalAnimationSource`（`GetMotionSpeedMps`）；动画层不反向依赖具体 Character BP。
- Animation 层唯一权威 = `ABP_FutsalSource`（`SK_Mannequin` 目标）。
- Appearance 层通过“独立 Mesh + 各自骨架的重定向链”接入，不进入动画逻辑。
- `UNREAL_RIG` 明确为 **Appearance Prototype**，不是 Animation Master。

---

## 8. STEP 8 — Asset Decision Table

| Asset | Current Role | Decision | Reason |
|---|---|---|---|
| `/Game/Characters/Mannequins/Meshes/SK_Mannequin` | 主动画骨架 | **KEEP** | MASTER_ANIMATION_SKELETON；115 referencers；Phase 3C 运行期验证通过 |
| `/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple` | 主测试/验证 Mesh | **KEEP** | MASTER_ANIMATION_MESH；与 SK_Mannequin 配套，Phase 3C 使用 |
| `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource` | 主动画蓝图 | **KEEP** | MASTER_ANIMBP；已解除 `BP_ThirdPersonCharacter` 依赖并通过运行期验证 |
| `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase` | 主角色蓝图 | **KEEP** | MASTER_CHARACTER；实现 `BPI_FutsalAnimationSource`，Mesh/AnimClass 默认 None |
| `/Game/FutsalMOT/Animation/BS_Futsal_Locomotion` | 主动画 BlendSpace | **KEEP** | MASTER_ANIMATION_LIBRARY；被 `ABP_FutsalSource` 使用 |
| `/Game/Characters/Mannequins/Rigs/CR_Mannequin_FootIK` | 足部 IK | **KEEP** | 被 `ABP_FutsalSource` 引用；与 SK_Mannequin 兼容 |
| `/Game/FutsalMOT/Animation/Retarget/IKR_Quinn` | Retarget 源 Rig | **KEEP** | Appearance Pipeline 原型（source = Quinn/SK_Mannequin） |
| `/Game/FutsalMOT/Animation/ABP_FutsalPlayer` | 旧动画蓝图 | **FUTURE_MIGRATION_CANDIDATE** | 由 `ABP_FutsalSource` 取代；仍被 `BP_ThirdPersonCharacter` 引用，待运行入口迁移后处理 |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter` | 旧角色类 | **FUTURE_MIGRATION_CANDIDATE** | 仍被 `L_FutsalCourt` 10 actor + 6 `LS_Cam_*` 引用；迁移到 `BP_FutsalCharacterBase` 后可移除 |
| `/Game/FutsalMOT/Animation/SoccerPlayer/*_Soccer`（20） | UNREAL_RIG 重定向动画 | **EXPERIMENTAL** | UNREAL_RIG_EXPERIMENT；仅被 Soccer AnimBP/BS 使用 |
| `/Game/FutsalMOT/Animation/SoccerPlayer/ABP_FutsalPlayer_Soccer` | Soccer 动画蓝图 | **EXPERIMENTAL** | 目标 UNREAL_RIG_Skeleton；含 `CR_Mannequin_FootIK` 骨架错配隐患 |
| `/Game/FutsalMOT/Animation/SoccerPlayer/BS_Futsal_Locomotion_Soccer` | Soccer BlendSpace | **EXPERIMENTAL** | 仅被 Soccer AnimBP 使用 |
| `/Game/FutsalMOT/Characters/FutsalPlayer/ABP_SoccerPlayer` | 动画蓝图 stub | **EXPERIMENTAL** | 0 变量、无 StateMachine，仅 `BP_SoccerPlayer` 引用 |
| `/Game/FutsalMOT/Characters/FutsalPlayer/BP_SoccerPlayer` | 角色 stub | **EXPERIMENTAL** | 0 referencers；含无关 `MI_Pool_01` 依赖 |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter_Soccer` | 角色子类 | **EXPERIMENTAL** | 0 referencers |
| `/Game/FutsalMOT/Animation/SoccerSource/LS_*_InPlace`（7） | 真实足球源动画（未接线） | **EXPERIMENTAL** | 0 引用但为 Futsal 自有动作；位于 SK_Mannequin，未来可直接接入 `ABP_FutsalSource`/新 BlendSpace |
| `/Game/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG` | 外观原型 Mesh | **EXPERIMENTAL** | APPEARANCE_PROTOTYPE；不承担动画根资产 |
| `/Game/FutsalMOT/Characters/FutsalPlayer/Skeleton/UNREAL_RIG_Skeleton` | 外观原型骨架 | **EXPERIMENTAL** | 非标准骨架；24 referencers；不进主动画层 |
| `/Game/FutsalMOT/Animation/Retarget/IKR_SoccerPlayer` | Retarget 目标 Rig | **EXPERIMENTAL** | 目标 UNREAL_RIG；Appearance 实验 |
| `/Game/FutsalMOT/Animation/Retarget/RTG_Quinn_To_SoccerPlayer` | Retarget 链 | **EXPERIMENTAL** | `*_Soccer` 唯一可追溯生成源；保留以便再生成 |
| `/Game/Characters/Mannequins/Rigs/CR_Mannequin_Procedural` | 未使用 CR | **ARCHIVE** | 0 referencers；Epic 模板残留（仅建议归档，不删除） |
| `/Game/Characters/Mannequins/**` 其余（Pistol/Rifle/Death/HitReact/BS_Idle_Walk_Run/AO_*/MM_Pistol_Fire_Montage/ABP_Unarmed/SKM_Manny_Simple/CR_Mannequin_Body） | Epic 模板 | **ARCHIVE** | LEGACY_EPIC_TEMPLATE；多数未被 FutsalMOT 运行链路使用 |

> 决策仅使用 `KEEP` / `ARCHIVE` / `EXPERIMENTAL` / `FUTURE_MIGRATION_CANDIDATE`。**不删除任何资产。**

---

## 9. STEP 9 — Git Safety Check

- 本阶段未产生任何 `uasset` / `umap` 修改；唯一新增为 `PHASE4A_ANIMATION_STANDARDIZATION_AUDIT.md`。
- `git status --short`（详见 STEP 10）中所有 ` M` 项均为**本阶段之前既有**：
  - `UNREAL_RIG.uasset` = `EXTERNAL_UNRESOLVED_CHANGE`（全程未触碰）
  - `L_FutsalCourt.umap` + 5×external actor = `PREVIOUS_QUINN_PREVIEW_CHANGE`
  - `L_FutsalCharacterBase_Test.umap` = 已提交于 `ad11a5e`（现应为 clean）
- 无 Blueprint / Animation / Map 在本阶段被修改。未 stage / commit / tag。

---

## 10. STEP 10 — 完成输出

```
PHASE4A_ANIMATION_STANDARDIZATION_AUDIT = COMPLETE

MASTER_ANIMATION_SKELETON = SK_Mannequin
MASTER_ANIMBP = ABP_FutsalSource
MASTER_CHARACTER = BP_FutsalCharacterBase

UNREAL_RIG_ROLE = APPEARANCE_PROTOTYPE

SKELETON_MIGRATION = NOT_STARTED
ASSET_MODIFICATION = NONE
```

---

## 附：本阶段未做（自查）

- 未修改任何 Blueprint / AnimBP / Skeleton / Mesh / AnimClass / Retargeter / IK Rig / Control Rig / Level / Sequence ✅
- 未 Fix Redirectors / Consolidate / Rename / Move / Delete / Save 任何已有资产 ✅
- 未 stage / commit / tag；未 add/restore/checkout/save `UNREAL_RIG.uasset` ✅
- 仅执行 Asset Registry 查询、Blueprint 只读内省、Unreal Python 只读查询，并生成本报告 ✅
