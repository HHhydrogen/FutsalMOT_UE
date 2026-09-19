# PHASE4C_LEGACY_CHAIN_AUDIT — 旧 Epic ThirdPerson 链路残留审计

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `de611502964937e16f92fa06d28f86be0c28a33c`（tag `phase4b2-production-migration`）
- 性质：**READ-ONLY AUDIT**。未删除/移动/重命名/修改任何资产；未 Save；未 stage / commit / tag。唯一写入：本报告。
- 架构基线：
  ```
  MASTER_CHARACTER          = BP_FutsalCharacterBase
  MASTER_ANIMBP             = ABP_FutsalSource
  MASTER_ANIMATION_SKELETON = SK_Mannequin
  ```

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| `BP_ThirdPersonCharacter` 是否仍被生产依赖 | **否**。Phase 4B2 后 `L_FutsalCourt` / 6 条序列 / 10 个 Player actor 均不再引用它 |
| `L_FutsalCourt` 对 `/Game/ThirdPerson` 依赖 | **无** |
| `L_FutsalCourt` 对 `/Game/Input` 依赖 | **无**（生产输入为 `/Game/FutsalMOT/Input/*`） |
| `ABP_FutsalPlayer` 是否仍被生产使用 | **否**（仅被 `BP_ThirdPersonCharacter` 引用） |
| 旧链路性质 | 全部为 **Epic 模板 + Futsal 实验/遗留**，非生产运行链路 |
| 本阶段 | `LEGACY_CLEANUP = NOT_STARTED` |

---

## 1. STEP 1 — `BP_ThirdPersonCharacter` referencers

`/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`（class Blueprint，Epic 模板角色类）

| Referencer | 类型 | 是否生产依赖 | 分类 |
|---|---|---|---|
| `/Game/FutsalMOT/Animation/ABP_FutsalPlayer` | Futsal 遗留 AnimBP | 否（该 ABP 本身已非生产） | **ARCHIVE_CANDIDATE** |
| `/Game/FutsalMOT/Animation/SoccerPlayer/ABP_FutsalPlayer_Soccer` | Futsal 实验 AnimBP | 否 | **EXPERIMENTAL / ARCHIVE_CANDIDATE** |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter_Soccer` | Epic 子类（0 refs） | 否 | **ARCHIVE_CANDIDATE** |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode` | Epic GameMode（仅 `Lvl_ThirdPerson`） | 否 | **ARCHIVE_CANDIDATE** |

- **已解除**的旧 referencers（Phase 4B2 结果）：6×`LS_Cam_*`、10×`L_FutsalCourt` external actor、`BP_ThirdPersonCharacter` 直接引用。
- 其自身 deps：`SKM_Quinn_Simple`、`ABP_FutsalPlayer`、`/Game/Input/Actions/IA_*`、`/Game/Input/Touch/BPI_TouchInterface`。
- ⇒ **`BP_ThirdPersonCharacter` 已是纯遗留节点，无生产路径依赖。**

---

## 2. STEP 2 — `ABP_FutsalPlayer`

`/Game/FutsalMOT/Animation/ABP_FutsalPlayer`

| 项 | 值 |
|---|---|
| Target Skeleton | `SK_Mannequin` |
| Referencers | `[ /Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter ]` |
| Dependencies | `MM_Idle`、`MM_Jump`、`MM_Land`、`MM_Fall_Loop`、`SK_Mannequin`、`CR_Mannequin_FootIK`、`BS_Futsal_Locomotion`、**`BP_ThirdPersonCharacter`** |
| 变量/图 | 与 `ABP_FutsalSource` 逐项相同（17 变量、Locomotion/Main States 状态机） |

**判断**：仍被任何生产资产使用？**否**。唯一 referencer 是 `BP_ThirdPersonCharacter`（本身非生产）；`L_FutsalCourt` 已改用 `ABP_FutsalSource`。
→ 分类：**ARCHIVE_CANDIDATE**（由 `ABP_FutsalSource` 取代）。

---

## 3. STEP 3 — `ABP_FutsalPlayer_Soccer` / UNREAL_RIG 依赖链

`/Game/FutsalMOT/Animation/SoccerPlayer/ABP_FutsalPlayer_Soccer` — **保持 EXPERIMENTAL**

| 项 | 值 |
|---|---|
| Target Skeleton | `UNREAL_RIG_Skeleton` |
| Referencers | `[ /Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter_Soccer ]` |
| Dependencies | `CR_Mannequin_FootIK`、`BS_Futsal_Locomotion_Soccer`、`MM_{Idle,Jump,Land,Fall_Loop}_Soccer`、**`UNREAL_RIG`**、**`UNREAL_RIG_Skeleton`**、**`BP_ThirdPersonCharacter`** |

UNREAL_RIG 依赖链：

```
ABP_FutsalPlayer_Soccer (Target = UNREAL_RIG_Skeleton)
   ├─ UNREAL_RIG (Mesh)
   ├─ UNREAL_RIG_Skeleton
   ├─ BS_Futsal_Locomotion_Soccer ──> *_Soccer ×17
   ├─ MM_{Idle,Jump,Land,Fall_Loop}_Soccer
   ├─ CR_Mannequin_FootIK   ← 为 SK_Mannequin 编写（骨架错配隐患）
   └─ BP_ThirdPersonCharacter (依赖，待解)
```

- 相关实验资产：`ABP_SoccerPlayer`（0 变量、无状态机，refs=`[BP_SoccerPlayer]`）、`BP_SoccerPlayer`（refs=`[]`，含无关 `MI_Pool_01`）、`BP_ThirdPersonCharacter_Soccer`（refs=`[]`）。
- **未修改**。分类：**EXPERIMENTAL**。

---

## 4. STEP 4 — 旧 Input 链（`/Game/Input`、`/Game/ThirdPerson`）

### 4.1 `/Game/Input`

| 资产 | Referencers | 生产引用 |
|---|---|---|
| `Actions/IA_Move` | `IMC_Default`, `BP_ThirdPersonCharacter` | 无 |
| `Actions/IA_Look` | `IMC_Default`, `BP_ThirdPersonCharacter` | 无 |
| `Actions/IA_MouseLook` | `IMC_MouseLook`, `BP_ThirdPersonCharacter` | 无 |
| `Actions/IA_Jump` | `IMC_Default`, `BP_ThirdPersonCharacter` | 无 |
| `IMC_Default` | `BP_ThirdPersonPlayerController` | 无 |
| `IMC_MouseLook` | `BP_ThirdPersonPlayerController` | 无 |
| `Touch/BPI_TouchInterface` | `UI_TouchSimple`, `BP_ThirdPersonCharacter` | 无 |
| `Touch/UI_Thumbstick` | `UI_TouchSimple` | 无 |
| `Touch/UI_TouchSimple` | `BP_ThirdPersonPlayerController` | 无 |

### 4.2 `/Game/ThirdPerson`

| 资产 | Referencers | 生产引用 |
|---|---|---|
| `Blueprints/BP_ThirdPersonCharacter` | `ABP_FutsalPlayer`, `ABP_FutsalPlayer_Soccer`, `BP_ThirdPersonCharacter_Soccer`, `BP_ThirdPersonGameMode` | 无 |
| `Blueprints/BP_ThirdPersonCharacter_Soccer` | `[]` | 无 |
| `Blueprints/BP_ThirdPersonGameMode` | `Lvl_ThirdPerson` | 无 |
| `Blueprints/BP_ThirdPersonPlayerController` | `BP_ThirdPersonGameMode` | 无 |
| `Lvl_ThirdPerson`（Epic 地图 + external actors） | Epic 外部 actor | 无 |
| `MI_ThirdPersonColWay` | ThirdPerson 地图 external actors | 无 |

### 4.3 生产根依赖核验（关键）

| 生产根 | `/Game/ThirdPerson` deps | `/Game/Input` deps | 实际依赖 |
|---|---|---|---|
| `L_FutsalCourt` | **0** | **0** | — |
| `BP_FutsalCharacterBase` | **0** | **0** | `IA_Futsal_*`、`BPI_FutsalTouchInterface`（Futsal 输入） |
| `BP_FutsalPlayerControllerBase` | **0** | **0** | `IMC_Futsal_Default`、`IMC_Futsal_MouseLook` |
| `GM_FutsalInputTest` | **0** | **0** | — |
| `L_FutsalCharacterBase_Test` | **0** | **0** | `ABP_FutsalSource` |

⇒ **生产角色链路与旧 Epic Input / ThirdPerson 完全解耦。**

---

## 5. STEP 5 — Legacy Asset Matrix

| Asset | Current Role | Referencers | Decision | Reason |
|---|---|---|---|---|
| `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase` | 主角色类（MASTER_CHARACTER） | `L_FutsalCharacterBase_Test` | **KEEP** | 生产主类 |
| `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource` | 主动画蓝图（MASTER_ANIMBP） | `L_FutsalCharacterBase_Test`、`L_FutsalCourt` external actors | **KEEP** | 生产主 AnimBP |
| `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource` | 动画数据接口 | `BP_FutsalCharacterBase`、`ABP_FutsalSource` | **KEEP** | 生产解耦接口 |
| `/Game/Characters/Mannequins/Meshes/SK_Mannequin` | 主动画骨架 | 115 | **KEEP** | MASTER_ANIMATION_SKELETON |
| `/Game/FutsalMOT/Animation/BS_Futsal_Locomotion` | 主动画 BlendSpace | `ABP_FutsalSource`、`ABP_FutsalPlayer` | **KEEP** | 生产动画库 |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter` | Epic 模板角色类（遗留） | `ABP_FutsalPlayer`、`ABP_FutsalPlayer_Soccer`、`BP_ThirdPersonCharacter_Soccer`、`BP_ThirdPersonGameMode` | **ARCHIVE** | 无生产依赖；仅遗留链引用 |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode` | Epic GameMode | `Lvl_ThirdPerson` | **ARCHIVE** | Epic 模板，非 Futsal 生产 |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController` | Epic PlayerController | `BP_ThirdPersonGameMode` | **ARCHIVE** | Epic 模板 |
| `/Game/ThirdPerson/Lvl_ThirdPerson` | Epic 模板地图（+external actors） | Epic external actors | **ARCHIVE** | Epic 模板，非生产地图 |
| `/Game/FutsalMOT/Animation/ABP_FutsalPlayer` | Futsal 遗留 AnimBP | `BP_ThirdPersonCharacter` | **ARCHIVE** | 由 `ABP_FutsalSource` 取代 |
| `/Game/FutsalMOT/Animation/SoccerPlayer/ABP_FutsalPlayer_Soccer` | UNREAL_RIG 实验 AnimBP | `BP_ThirdPersonCharacter_Soccer` | **EXPERIMENTAL** | 目标骨架非标准；保留实验 |
| `/Game/FutsalMOT/Characters/FutsalPlayer/ABP_SoccerPlayer` | 动画蓝图 stub | `BP_SoccerPlayer` | **EXPERIMENTAL** | 0 变量/无状态机 |
| `/Game/FutsalMOT/Characters/FutsalPlayer/BP_SoccerPlayer` | 角色 stub | `[]` | **EXPERIMENTAL** | 0 refs；含无关 `MI_Pool_01` 依赖 |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter_Soccer` | Epic 子类 | `[]` | **EXPERIMENTAL** | 0 refs，实验残留 |
| `/Game/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG` | Appearance Prototype Mesh | `ABP_FutsalPlayer_Soccer`、`BP_SoccerPlayer` 等 | **EXPERIMENTAL** | Appearance 层，非动画根 |
| `/Game/FutsalMOT/Characters/FutsalPlayer/Skeleton/UNREAL_RIG_Skeleton` | Appearance Prototype 骨架 | `ABP_FutsalPlayer_Soccer`、`ABP_SoccerPlayer`、`*_Soccer` | **EXPERIMENTAL** | 非标准骨架 |
| `/Game/FutsalMOT/Animation/SoccerPlayer/*_Soccer`（20） | UNREAL_RIG 重定向动画 | Soccer AnimBP/BS | **EXPERIMENTAL** | UNREAL_RIG 实验 |
| `/Game/Input/**`（Actions/IMC/Touch） | Epic 模板输入 | `BP_ThirdPersonCharacter`、`BP_ThirdPersonPlayerController` | **ARCHIVE** | 生产无引用 |
| `/Game/ThirdPerson/MI_ThirdPersonColWay` 等模板材质 | Epic 模板材质 | ThirdPerson 地图 external actors | **ARCHIVE** | Epic 模板 |

> Decision 仅使用 `KEEP` / `ARCHIVE` / `EXPERIMENTAL` / `FUTURE_MIGRATION_CANDIDATE`。**未删除任何资产。**
> 迁移建议（未来阶段，不在本阶段执行）：`ABP_FutsalPlayer` 与 `BP_ThirdPersonCharacter` 的剩余双向引用可一并归档；`ABP_FutsalPlayer_Soccer` 的 `BP_ThirdPersonCharacter` 依赖需在未来实验转正时解耦。

---

## 6. STEP 6 — Git

- 本阶段无 `uasset` / `umap` 修改；唯一新增为 `PHASE4C_LEGACY_CHAIN_AUDIT.md`。
- 未 stage / commit / tag。

```
LEGACY_CLEANUP = NOT_STARTED
```

---

## 附：本阶段未做（自查）

- 未删除 / 移动 / 重命名 / 修改任何资产 ✅
- 未 Fix Redirectors / Consolidate / Save ✅
- 未 stage / commit / tag ✅
- 仅执行 Asset Registry 只读查询与只读内省，并生成本报告 ✅
