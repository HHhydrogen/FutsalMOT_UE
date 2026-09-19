# PHASE4B1_PRODUCTION_MIGRATION_AUDIT — L_FutsalCourt 角色迁移审计

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `ad11a5e8f771bbceebe2bbdc9afcd3acdb2e1c2e`（tag `phase3c-source-animbp-runtime`）
- 性质：**READ-ONLY AUDIT**。未修改任何资产；未 stage / commit / tag；未 add/restore/checkout/save `UNREAL_RIG.uasset`。
- 目标架构基线：
  ```
  MASTER_CHARACTER          = BP_FutsalCharacterBase
  MASTER_ANIMBP             = ABP_FutsalSource
  MASTER_ANIMATION_SKELETON = SK_Mannequin
  ```
- 目标：评估将 `L_FutsalCourt` 从 `BP_ThirdPersonCharacter` 迁移到 `BP_FutsalCharacterBase` 的风险。**本阶段不执行迁移。**

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| 10 个 Player actor 当前类 | 全部 `BP_ThirdPersonCharacter_C` |
| 当前 Mesh / AnimClass | `SKM_Quinn_Simple` / `ABP_FutsalPlayer_C` |
| `BP_FutsalCharacterBase` 与 `BP_ThirdPersonCharacter` 结构差异 | 极小：同父类、同 8 组件、同变量、同函数/事件；Base 额外实现 `BPI_FutsalAnimationSource`（+`GetMotionSpeedMps`） |
| **主要迁移障碍** | 6 条 `LS_Cam_*` 的 possessable 绑定类 = `BP_ThirdPersonCharacter_C`；且 actor class 变更需处理实例 override 与绑定类 |
| 目标迁移后 AnimClass | `ABP_FutsalSource`（当前实例为 `ABP_FutsalPlayer_C`，需在迁移时一并改） |
| 推荐方案 | **方案 A（就地替换 Actor Class）** + 分步验证；方案 B 风险更高（重绑定 + 重复资产） |
| `PRODUCTION_MIGRATION` | `NOT_STARTED` |

---

## 1. STEP 1 — L_FutsalCourt Player Actor 扫描

关卡 `/Game/FutsalMOT/Maps/L_FutsalCourt`（World Partition，Player actor 存放在 `Content/__ExternalActors__/**`）。

| Actor | Class | Transform (loc / yaw) | Mesh | AnimClass | Tags | AutoPossess | Components |
|---|---|---|---|---|---|---|---|
| Player_L0 | `BP_ThirdPersonCharacter_C` | (0, 0, 0) / 0° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseL0]` | DISABLED | 8 |
| Player_L1 | `BP_ThirdPersonCharacter_C` | (0, 0, 0) / 0° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseL1]` | DISABLED | 8 |
| Player_L2 | `BP_ThirdPersonCharacter_C` | (0, 0, 0) / 0° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseL2]` | DISABLED | 8 |
| Player_L3 | `BP_ThirdPersonCharacter_C` | (0, 0, 0) / 0° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseL3]` | DISABLED | 8 |
| Player_L4 | `BP_ThirdPersonCharacter_C` | (0, 0, 0) / 0° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseL4]` | DISABLED | 8 |
| Player_R0 | `BP_ThirdPersonCharacter_C` | (2022.1, 0, 90) / 180° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseR0]` | DISABLED | 8 |
| Player_R1 | `BP_ThirdPersonCharacter_C` | (81, -91, 90) / 75.8° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseR1]` | DISABLED | 8 |
| Player_R2 | `BP_ThirdPersonCharacter_C` | (78.3, 88.5, 90) / -131.3° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseR2]` | DISABLED | 8 |
| Player_R3 | `BP_ThirdPersonCharacter_C` | (202.2, 228.7, 90) / -76.0° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseR3]` | DISABLED | 8 |
| Player_R4 | `BP_ThirdPersonCharacter_C` | (202.2, -228.7, 90) / -102.4° | `SKM_Quinn_Simple` | `ABP_FutsalPlayer_C` | `[PoseR4]` | DISABLED | 8 |

- 每组 8 个组件（类一致）：`CapsuleComponent`(`CollisionCylinder`)、`CharacterMovementComponent`(`CharMoveComp`)、`SkeletalMeshComponent`(`CharacterMesh0`)、`SpringArmComponent`(`CameraBoom`)、`CameraComponent`(`FollowCamera`)、`ArrowComponent`(`Arrow`)、`CameraProxyMeshComponent`、`DrawFrustumComponent`。
- Scale 均为 (1,1,1)。
- L0~L4 关卡内 transform 为 (0,0,0)、yaw 0（其实际位置由数据集预览/Sequence 逐帧设置）；R0~R4 有显式摆放 transform。
- 标签 `PoseL0..PoseR4` 为数据集 actor_id 映射用（`tag_players_c4.py`）。

---

## 2. STEP 2 — Blueprint 差异与 Migration Compatibility Matrix

### 2.1 结构对比

| 方面 | `BP_ThirdPersonCharacter` | `BP_FutsalCharacterBase` | 兼容 |
|---|---|---|---|
| Parent Class | `Character` | `Character` | ✅ 相同 |
| Components（8） | Capsule / CharacterMovement / SkeletalMesh / SpringArm / Camera / Arrow / CameraProxyMesh / DrawFrustum | 同 8 类（实例名后缀 `_0` vs `_2`，不影响） | ✅ 相同 |
| Variables | `MotionSpeedMps`, `AnimationClassId` | `MotionSpeedMps`, `AnimationClassId` | ✅ 相同 |
| 自定义函数 | `UserConstructionScript`, `Move`, `Aim`, `CanJumpInternal` | 同 4 个 **+ `GetMotionSpeedMps`** | ✅ 超集 |
| 事件（接口/父类） | 含 `Primary/Secondary Thumbstick`、`Touch Jump Start/End`、`Receive*` 等 | 同一集合 | ✅ 相同 |
| Implemented Interfaces | `BPI_TouchInterface`（`/Game/Input/Touch`） | `BPI_FutsalAnimationSource` + `BPI_FutsalTouchInterface` | ⚠️ 接口不同（Base 为 Futsal 版） |
| Input 依赖 | `/Game/Input/Actions/IA_Move/Look/MouseLook/Jump` + `/Game/Input/IMC_*` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_*` + `IMC_Futsal_*` | ⚠️ Input 动作/映射资产不同 |
| Animation 依赖 | `ABP_FutsalPlayer`（**再依赖 `BP_ThirdPersonCharacter`**） | `BPI_FutsalAnimationSource`（**无 Character BP 回依赖**） | ✅ Base 更解耦 |
| CDO Mesh 默认 | `SKM_Quinn_Simple` | `None` | ⚠️ 实例需保留 Mesh override |
| CDO AnimClass 默认 | `ABP_FutsalPlayer_C` | `None` | ⚠️ 实例需设 `ABP_FutsalSource` |
| CDO AutoPossess | DISABLED | DISABLED | ✅ 相同 |
| 关系 | — | **兄弟克隆**（非子类）；图谱/输入与 ThirdPerson 同构，另加接口 | — |

### 2.2 Migration Compatibility Matrix

| 维度 | 影响 | 风险 |
|---|---|---|
| Parent Class | 同为 `Character` → 类替换无继承断链 | 低 |
| Components | 组件类/名称一致 → 实例 override（Mesh、相对变换等）可按名迁移 | 低 |
| Variables | 同名同类型 → 引用/复制不受影响 | 低 |
| Functions | Base 为超集；`Move`/`Aim`/`CanJumpInternal` 同名 | 低 |
| Interfaces | Base 新增 `BPI_FutsalAnimationSource`；Epic `BPI_TouchInterface` 被 `BPI_FutsalTouchInterface` 取代 | 低（L_FutsalCourt 无输入诉求） |
| Input dependencies | ThirdPerson 用 Epic `IA_*`；Base 用 `IA_Futsal_*` | 低（生产关卡 GameMode = `BP_NoPawnGameMode`，无 possession；输入不参与渲染链路） |
| Animation dependencies | Base 通过接口取速度、`ABP_FutsalSource`；不再依赖 `BP_ThirdPersonCharacter` | **正收益** |
| Mesh override | 实例 Mesh override 应保留（同名 `CharacterMesh0`/`SkeletalMeshComponent`） | 中（需迁移后逐一核对） |
| AnimClass override | 实例当前 `ABP_FutsalPlayer_C`，目标 `ABP_FutsalSource` | 中（需显式改） |
| Actor Tags | 实例标签应保留 | 低 |
| Level Sequence binding | 6 条序列 possessable 绑定类 = `BP_ThirdPersonCharacter_C` | **中–高（见 STEP 3）** |
| External actor 包 | actor class 存储在 WP external actor 包中，类替换会改写 5 个已修改的 external actor 包 | 中 |
| Pose 管线 | 依赖 actor Tag + transform + SkeletalMesh；类替换后需回归（预览/pose 导出） | 中 |

---

## 3. STEP 3 — Level Sequence 审计

6 条序列均位于 `/Game/FutsalMOT/Sequences/`，每条都 possess 全部 10 个 Player（possessable binding），绑定类均为 `BP_ThirdPersonCharacter_C`；另含 `Ball_01`(`BP_FutsalBall_C`) 与 `CineCam_*`(`CineCameraActor`)。

| Sequence | Player 绑定数 | Player 绑定类 | 其他绑定 | deps 含 `BP_ThirdPersonCharacter` |
|---|---|---|---|---|
| `LS_Cam_01` | 10 | `BP_ThirdPersonCharacter_C` | Ball_01, CineCam_01 | ✅ |
| `LS_Cam_02` | 10 | `BP_ThirdPersonCharacter_C` | Ball_01, CineCam_02 | ✅ |
| `LS_Cam_03` | 10 | `BP_ThirdPersonCharacter_C` | Ball_01, CineCam_03 | ✅ |
| `LS_Cam_04` | 10 | `BP_ThirdPersonCharacter_C` | Ball_01, CineCam_04 | ✅ |
| `LS_Cam_Main` | 10 | `BP_ThirdPersonCharacter_C` | Ball_01, CineCam_Main, CameraComponent | ✅ |
| `LS_Cam_P01` | 10 | `BP_ThirdPersonCharacter_C` | Ball_01, CineCam_P01, CameraComponent | ✅ |

- 每条序列的公共 deps：`BP_FutsalBall`、`L_FutsalCourt`、**`BP_ThirdPersonCharacter`**、`/Script/CinematicCamera`、`/Script/LevelSequence`、`/Script/MovieScene`、`/Script/MovieSceneTracks`。
- **是否依赖 `BP_ThirdPersonCharacter` 类型：是**（possessable 绑定的 possessed class 与序列依赖均为该 BP）。
- 含义：替换 L_FutsalCourt 中 actor 类后，这些序列的 possessable 绑定类与实际 actor 类不再匹配；需要逐一更新绑定类（或在 Sequence 中保留 actor 绑定的“可替换”语义并验证）。这是迁移的主要耦合点。

---

## 4. STEP 4 — 迁移方案风险对比（不执行）

### 方案 A — 就地替换 Actor Class（10 个 Player：`BP_ThirdPersonCharacter_C` → `BP_FutsalCharacterBase_C`）

| 项 | 评估 |
|---|---|
| 优点 | 保留 actor GUID、Tags、Transform、关卡布局；sequence possessable 绑定按 GUID 仍指向同一 actor |
| 缺点/风险 | ① 6 条序列绑定类需同步更新/验证；② 5 个已修改 external actor 包会被再改写；③ Mesh/AnimClass 实例 override 需逐一核对（AnimClass 必须改为 `ABP_FutsalSource`）；④ 类替换属破坏性操作，需可回滚基线 |
| 总体风险 | **中**（可回滚、范围可控） |

### 方案 B — 复制新 Actor、保留旧 Actor

| 项 | 评估 |
|---|---|
| 优点 | 旧 actor 原样保留，可 A/B 对比、易回滚 |
| 缺点/风险 | ① 10 个 Player 在场景中重复，outliner 混乱；② **仍需**把 6 条序列的 possessable 绑定从旧 actor 改绑到新 actor（GUID 变更 → 全量重绑）；③ Tag 映射冲突（`PoseL0` 等重复）；④ external actor 包数量翻倍；⑤ 数据集 actor 查找（按 label/tag）可能歧义 |
| 总体风险 | **高** |

### 建议

- **优先方案 A（就地替换）**，在独立迁移阶段执行：先冻结基线 tag，再逐个 actor 替换 + 同步序列绑定 + 回归（skeleton/anim/mesh/pose/tag）。
- 迁移时一并把实例 AnimClass 设为 `ABP_FutsalSource_C`、Mesh 保持 `SKM_Quinn_Simple`。
- 迁移前须先解决 Phase 4A 记录的 `L_FutsalCourt` + 5 external actor 的 `PREVIOUS_QUINN_PREVIEW_CHANGE` 去留。
- **本阶段不执行任何替换。**

---

## 5. STEP 5 — 迁移后目标状态（定义，不实施）

| Actor | Class | Mesh | AnimClass |
|---|---|---|---|
| Player_L0~L4 | `BP_FutsalCharacterBase_C` | `SKM_Quinn_Simple` | `ABP_FutsalSource_C` |
| Player_R0~R4 | `BP_FutsalCharacterBase_C` | `SKM_Quinn_Simple` | `ABP_FutsalSource_C` |

- 保留：actor 名、Tags（`PoseL0..R4`）、Transform、AutoPossess=DISABLED、组件集合。
- 同步：6 条 `LS_Cam_*` possessable 绑定类更新为 `BP_FutsalCharacterBase_C`。
- 期望收益：运行入口不再依赖 `BP_ThirdPersonCharacter`；动画层统一为 `ABP_FutsalSource`（`SK_Mannequin`）。

**本阶段只定义目标，不修改任何资产。**

---

## 6. STEP 6 — Git 检查与完成输出

- 本阶段无 `uasset` / `umap` 修改；唯一新增为 `PHASE4B1_PRODUCTION_MIGRATION_AUDIT.md`。
- `git status --short` 中所有 ` M` 项均为**既有未提交改动**（详见输出）。
- 未 stage / commit / tag；未 add/restore/checkout/save `UNREAL_RIG.uasset`。

```
PHASE4B1_PRODUCTION_MIGRATION_AUDIT = COMPLETE
PRODUCTION_MIGRATION = NOT_STARTED
ASSET_MODIFICATION = NONE
```

---

## 附：本阶段未做（自查）

- 未修改任何 Blueprint / AnimBP / Skeleton / Mesh / AnimClass / Level / Sequence / Retargeter / IK / ControlRig ✅
- 未 Fix Redirectors / Consolidate / Rename / Move / Delete / Save 任何已有资产 ✅
- 未 stage / commit / tag；未触碰 `UNREAL_RIG.uasset` ✅
- 仅执行 Level/Actor 只读查询、Blueprint/Sequence 只读内省、Asset Registry 只读查询，并生成本报告 ✅
