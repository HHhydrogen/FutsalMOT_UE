# PHASE1_REPORT — 创建 BP_FutsalCharacterBase

- 执行时间：2026-09-16
- 执行范围：**仅创建** `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`
- 状态：**已完成，等待用户审核。未进入 Phase 2。**
- Git checkpoint：外层仓库 annotated tag `refactor-phase1-create-futsal-base` → `c185d4d`

---

## 1. Created

```
/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase
磁盘：Content/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.uasset  (147338 bytes)
```

外层 git 状态：`?? Content/FutsalMOT/Characters/Base/`（新增未跟踪目录）
**无任何已有资产被修改**（30 分钟内被写入的 .uasset 只有本文件）。

---

## 2. 创建方法（重要，请审核是否认可）

采用 **资产复制 → 清空默认值**，而不是"空 Blueprint 重新搭图"：

| 步骤 | 操作 | 结果 |
|---|---|---|
| 1 | `EditorAssetLibrary.make_directory('/Game/FutsalMOT/Characters/Base')` | ok |
| 2 | `EditorAssetLibrary.duplicate_asset(BP_ThirdPersonCharacter → BP_FutsalCharacterBase)` | ok |
| 3 | `modify(True)` + `skinned_asset=None` + `anim_class=None` | ok |
| 4 | `EditorAssetLibrary.save_asset(..., OnlyIfIsDirty=False)` | ok |

**理由**：本仓库的 MCP/Python 只能读取 Blueprint 的**节点类型与结构**，**无法读取节点的语义/连线逻辑**（上一轮审计已确认；`read_graph_dsl` 对 EventGraph 返回空）。因此"复制 Move/Aim 逻辑并保持功能一致、不自动优化"**只能**通过复制资产本身实现；若改成新建空 BP 逐个重搭，必然改变行为，直接违反"不要改变输入行为"。

复制的结果：**Parent 仍是 `/Script/Engine.Character`**（源 BP 的 Parent 本来就是 Character，不是 BP_ThirdPersonCharacter），满足"不要继承 BP_ThirdPersonCharacter"。

---

## 3. 验证输出（要求的 7 项）

### 3.1 Blueprint 路径
`/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`

### 3.2 Parent Class
`/Script/Engine.Character`  （原生 `ACharacter`，非 BP_ThirdPersonCharacter）
证据：MCP `BlueprintTools.get_parent` → `{"refPath":"/Script/Engine.Character"}`

### 3.3 Components 列表
MCP `ActorTools.get_components`（作用对象：本 BP 的 CDO `Default__BP_FutsalCharacterBase_C`）：

| # | 组件对象 | 类 | 来源 | 变量名 |
|---|---|---|---|---|
| 1 | `CollisionCylinder` | CapsuleComponent | `ACharacter` 原生 | `CapsuleComponent` ✅ |
| 2 | `Arrow` | ArrowComponent | `ACharacter` 原生 | （原生，无变量） |
| 3 | `CharMoveComp` | CharacterMovementComponent | `ACharacter` 原生 | `CharacterMovement` ✅ |
| 4 | `CharacterMesh0` | SkeletalMeshComponent | `ACharacter` 原生 | `Mesh` ⚠ |
| 5 | `SpringArmComponent_0__A9892D03` | SpringArmComponent | Blueprint SCS 模板 | 实例上为 `CameraBoom` ✅ |
| 6 | `CameraComponent_0__CCE3C0B4` | CameraComponent | Blueprint SCS 模板 | 实例上为 `FollowCamera` ✅ |

补充：
- SCS 子对象总数 = **8**（与源 BP 相同）。实例运行期还会出现 `CameraProxyMeshComponent`（静态网格 `/Engine/EditorMeshes/MatineeCam_SM`，引擎自带）与 `DrawFrustumComponent`，二者是 `UCameraComponent` 的引擎内部子对象，**未新增也未删除**。
- ⚠ **`CharacterMesh` 这个名字无法满足**：`Mesh` 是 `ACharacter` 的**原生组件**，对象名固定为 `CharacterMesh0`、变量名固定为 `Mesh`，引擎不允许重命名原生组件。按"不修改 Mesh"要求，本次保持原样。这是规格与引擎现实的冲突，**只报告，未处理**。

### 3.4 Variables 列表

MCP `BlueprintTools.list_variables` → `["MotionSpeedMps", "AnimationClassId"]`

| 变量 | 类型 | 默认值 | 分类 | 处置 |
|---|---|---|---|---|
| `MotionSpeedMps` | float | `0.0` | A. 通用 Character（运动速度，Futsal 链路在用） | **已迁移** |
| `AnimationClassId` | int | `0` | A. 通用 Character（动画分支选择） | **已迁移** |

**迁移表结论**：
- A. 通用 Character 变量：2 个，全部迁移。
- B. Futsal 相关变量（Ball / Team / Player / Pose / Soccer 相关）：**该 BP 上不存在** → 无可迁移项。
- C. Epic 模板专用变量（Debug / Template / Demo 相关）：**该 BP 上不存在** → 无剔除项。
- 说明：规格举例中的 `Speed` / `Direction` 属于 **AnimBP** 的变量（`ABP_FutsalPlayer` 的 17 个变量），**不在 Character BP 上**，本阶段不涉及。

### 3.5 Functions 列表

MCP `BlueprintTools.list_graphs`：

| 图 | 类型 | 处置 |
|---|---|---|
| `UserConstructionScript` | Construction Script | 已迁移（**内容为空**，仅 `K2Node_FunctionEntry`，无 Mesh/Material/Anim 设置 → 无需清理） |
| `Move` | 函数图（6× CallFunction + Knot） | **已迁移（原样保留）** |
| `Aim` | 函数图（2× CallFunction + Knot） | **已迁移（原样保留）** |
| `EventGraph` | 事件图（7× EnhancedInputAction + 5× Event + 9× CallFunction） | **已迁移（原样保留）** |

- 源 BP 的已实现事件仅有 `Touch Jump Start/End`、`Primary/Secondary Thumbstick`（Epic 模板自带的移动端触控事件），无自定义事件。
- 规格重点中的 `Look` / `Jump`：**不是独立函数图**，它们是 `EventGraph` 内的 `IA_Look` / `IA_Jump` 输入事件节点，已随 EventGraph 一并保留。
- **未做任何"自动优化"，未改动任何输入行为。**

### 3.6 当前依赖

`BP_FutsalCharacterBase` 的依赖（MCP 强制重扫登记表后）：

```
BP_FutsalCharacterBase
    |
    dependencies
    ├── /Game/Input/Actions/IA_Jump
    ├── /Game/Input/Actions/IA_Look
    ├── /Game/Input/Actions/IA_MouseLook
    ├── /Game/Input/Actions/IA_Move
    ├── /Game/Input/Touch/BPI_TouchInterface
    ├── /Script/ClothingSystemRuntimeNv
    ├── /Script/EnhancedInput
    ├── /Script/InputBlueprintNodes
    └── /Script/NavigationSystem
```

referencers：`[]`（暂无任何资产引用它）

### 3.7 禁止引用确认

| 检查项 | 结果 |
|---|---|
| 引用 `/Game/Characters/Mannequins` | **无** ✅ |
| 引用 `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter` | **无** ✅ |
| 引用 `/Game/FutsalMOT/Animation/ABP_FutsalPlayer`（额外检查） | **无** ✅ |

三层独立证据：
1. **内存属性**：CDO 的 `Mesh.skinned_asset = null`、`Mesh.skeletal_mesh = null`、`Mesh.anim_class = null`（`animation_mode` 保持类默认 `ANIMATION_BLUEPRINT`，未改动）。
2. **资产登记表**：强制 `scan_paths_synchronous(force=True)` 后 `get_dependencies` 中 `forbidden = []`。
3. **落盘二进制**：对保存后的 `.uasset` 做 ASCII+UTF16LE 字符串扫描 —— `SKM_Quinn_Simple`、`SKM_Manny`、`SK_Mannequin`、`ABP_FutsalPlayer`、`BP_ThirdPersonCharacter`、`UNREAL_RIG` 出现次数全部为 **0**；仅剩 `IA_Move`(4) 与 `BPI_TouchInterface`(6)。

> 过程中发现并修正了一个真实缺陷：UE 5.8 中 `SkeletalMeshComponent.skeletal_mesh` 是**已弃用的别名**，真正序列化的是 `skinned_asset`。第一次只清了别名，落盘后引用仍在（登记表 + 二进制均能查到）；补设 `skinned_asset=None` 并保存后引用才真正消失。此结论已用"重扫登记表 + 二进制扫描"验证，不是推测。

---

## 4. Migrated / Not Migrated

### Migrated
- **Components**：CapsuleComponent、Mesh（`CharacterMesh0`）、CameraBoom（SpringArmComponent）、FollowCamera（CameraComponent）、CharacterMovement、Arrow（原生）
- **Variables**：`MotionSpeedMps` (float)、`AnimationClassId` (int)
- **Functions**：`Move`、`Aim`、`EventGraph`（含 Look/Jump 输入事件）、`UserConstructionScript`（空）

### Not Migrated
- **Mesh（资产）**：未绑定显式 SkeletalMesh（`skinned_asset = None`）
- **Skeleton**：未引用任何 Skeleton（随 Mesh 清空而消失）
- **AnimBP**：未引用任何 Animation Blueprint（`anim_class = None`）
- **Level Actor**：未创建、未修改任何关卡 Actor（L_FutsalCourt 未被触碰）
- **Sequence**：未创建、未修改任何 Level Sequence

### Not Copied（按规格主动排除）
- `SKM_Quinn_Simple`（已清空，二进制验证为 0 引用）
- 任何 Animation Blueprint
- Construction Script 中的 Mesh / Material / Animation 设置（原本就没有）

---

## 5. Input 依赖记录（按规格"只记录，不修改"）

| Input 资产 | 位置 | 是否在 `/Game/ThirdPerson/` | 处置 |
|---|---|---|---|
| `IA_Move` | `/Game/Input/Actions/` | 否 | 已随 EventGraph 带入依赖，**未修改** |
| `IA_Look` | `/Game/Input/Actions/` | 否 | 同上 |
| `IA_MouseLook` | `/Game/Input/Actions/` | 否 | 同上 |
| `IA_Jump` | `/Game/Input/Actions/` | 否 | 同上 |
| `BPI_TouchInterface` | `/Game/Input/Touch/` | 否 | 同上 |

Input Action 均位于 `/Game/Input/`，**不在 `/Game/ThirdPerson/` 下**，因此按规格不属于"不要复制"的情形。Input 系统重构留待后续阶段。

---

## 6. 未违反的最高规则（自查）

1. L_FutsalCourt 未修改 ✅
2. Player_L0~Player_R4 未修改 ✅
3. 任何 Level Sequence 未修改 ✅
4. BP_ThirdPersonCharacter 未修改 ✅
5. BP_ThirdPersonCharacter_Soccer 未修改 ✅
6. ABP_FutsalPlayer 未修改 ✅
7. ABP_FutsalPlayer_Soccer 未修改 ✅
8. Mesh 未修改 ✅
9. Skeleton 未修改 ✅
10. Animation Blueprint 未修改 ✅
11. 未删除任何资产 ✅
12. 未移动任何已有资产 ✅
13. 未执行 Fix Redirectors ✅

（依据：外层 `git status` 仅新增 `Content/FutsalMOT/Characters/Base/`；近 30 分钟内被写入的 `.uasset` 只有新文件本身。）

---

## 7. Risks

| # | 风险 | 说明 | 建议 |
|---|---|---|---|
| R1 | **`CharacterMesh` 命名无法达成** | `ACharacter::Mesh` 是原生组件，对象名 `CharacterMesh0`、变量名 `Mesh`，引擎不允许重命名 | 接受现状，或改为给子类新增自定义 Mesh 组件（需另立 Phase 决策） |
| R2 | **复制法携带 EventGraph 的 Input 依赖** | 新 BP 仍依赖 `/Game/Input/Actions/*` + `BPI_TouchInterface`。这是"保持输入行为一致"的代价 | Phase 2+ 若要做 Input 解耦，需在 AnimBP/Character 之间引入接口，而非删节点 |
| R3 | **新 BP 与源 BP 存在隐式行为耦合** | `AnimationClassId` / `MotionSpeedMps` 的写入方（EventGraph/Aim/Move）语义未逐节点核对（工具读不到） | 上线前用同 seed 轨迹做 PIE 行为对比 |
| R4 | **SCS 组件变量名未在本 BP 实例上直接验证** | MCP/Python 均无法读取 SCS 的 `VariableName`；`CameraBoom`/`FollowCamera` 的证据来自**源 BP 的关卡实例**（本 BP 是逐字节复制的产物）。CDO 上读 `CameraBoom`/`FollowCamera` 返回 `None`（引擎行为，非缺陷） | 如需硬证据：在**独立测试关卡**（非 L_FutsalCourt）拖入本 BP 后截图核对 |
| R5 | **新 BP 尚未编译/未在任何关卡验证** | 本次未调用 `compile_blueprint`，也未实例化 | 若审核通过，建议在一个临时测试关卡做一次实例化冒烟 |
| R6 | **资产未提交** | 新文件处于 untracked 状态 | 等你确认后再决定是否提交 |
| R7 | **登记表缓存时序** | `get_dependencies` 曾一度返回陈旧数据，需 `scan_paths_synchronous(force=True)` 才刷新 | 后续 Phase 校验依赖时一律强制重扫 |

---

## 8. 需要你决定的事项

1. 是否认可 **R2 的复制法**（保留 EventGraph/Input 依赖），还是要求改为"空 BP + 手工重搭"（会改变输入行为，与"保持功能一致"冲突）？
2. `CharacterMesh` 命名冲突（R1）如何取舍？
3. 是否把 `Content/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.uasset` 提交入库？
4. R4 需要一个**临时测试关卡**来硬验证 SCS 组件——是否授权创建（不会触碰 L_FutsalCourt）？

**未进入 Phase 2。等待用户审核。**
