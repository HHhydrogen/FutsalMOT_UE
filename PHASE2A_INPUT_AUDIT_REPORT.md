# PHASE2A_INPUT_AUDIT_REPORT — Input Ownership Audit + Futsal Input Asset Extraction

- 执行时间：2026-09-16
- 基线：branch `refactor/character-architecture` @ `1ff121fe2a32cc4ae55c09fd5dcf195cf8928e41`（tag `phase1-approved`）
- 结论：**审计完成；Futsal-owned Input 资产已建立并落盘验证。未修改任何既有资产。未执行 Phase 2B。**

---

## 1. Current Input Architecture

```
生产管线 (FutsalMOT)                          Epic 模板管线
─────────────────────────                     ────────────────────────────────
L_FutsalCourt                                 Lvl_ThirdPerson
  WorldSettings: GameMode Override = None       WorldSettings: GameMode Override = None
  → GlobalDefaultGameMode                        → GlobalDefaultGameMode(未覆盖) —— 但该关卡
    = BP_NoPawnGameMode                            defaultGameMode = BP_ThirdPersonGameMode
       ├── player_controller_class
       │     = /Script/Engine.PlayerController      └── player_controller_class
       └── dependencies = []                              = BP_ThirdPersonPlayerController
                                                              │
      ✗ 不注册任何 IMC                                        │ ReceiveBeginPlay (已实现)
      ✗ IA_* 永不触发                                          │
                                                              ▼
                                            EnhancedInputLocalPlayerSubsystem
                                              (K2Node_GetSubsystem_0 / _2)
                                                              │
                                    ┌─────────────────────────┴─────────────────────────┐
                                    ▼                                                   ▼
                        AddMappingContext(IMC_Default, Priority=0)      AddMappingContext(IMC_MouseLook, Priority=0)
                        Options = bIgnoreAllPressedKeysUntilRelease=1    Options 同上
                                    │                                                   │
                            IMC_Default (12 mappings)                        IMC_MouseLook (1 mapping)
                            ├── IA_Move  ← W/S/A/D/Up/Down/Left/Right/Gamepad_Left2D    └── IA_MouseLook ← Mouse2D
                            ├── IA_Look  ← Gamepad_Right2D
                            └── IA_Jump  ← SpaceBar / Gamepad_FaceButton_Bottom
                                    │
                        BP_ThirdPersonCharacter  /  BP_FutsalCharacterBase
                        （EventGraph 内的 IA_* 绑定事件；本阶段未触碰）
                                    
触摸链路（仅 Epic PC 侧）
BP_ThirdPersonPlayerController ──▶ UI_TouchSimple ──▶ UI_Thumbstick
                                          └────────▶ BPI_TouchInterface
                                                          ▲ 实现方：
                                        BP_ThirdPersonCharacter / BP_FutsalCharacterBase
```

**关键结论**：生产管线（L_FutsalCourt + BP_NoPawnGameMode）**没有任何 IMC 注册者**，因此 `IA_*` 在该管线中永远不会触发。这从架构层面证实了 Phase 1.5 记录的 F2。Input 的所有权目前完全在 Epic 侧（`BP_ThirdPersonPlayerController`）。

---

## 2. IA_* Source Asset Table

| Asset | Class | Path | 位置归属 | Dependencies | Referencers |
|---|---|---|---|---|---|
| `IA_Move` | InputAction | `/Game/Input/Actions/IA_Move` | **`/Game/Input/`（非 ThirdPerson）** | `/Script/Engine`, `/Script/EnhancedInput` | `BP_FutsalCharacterBase`, `IMC_Default`, `BP_ThirdPersonCharacter` |
| `IA_Look` | InputAction | `/Game/Input/Actions/IA_Look` | 同上 | 同上 | `BP_FutsalCharacterBase`, `IMC_Default`, `BP_ThirdPersonCharacter` |
| `IA_MouseLook` | InputAction | `/Game/Input/Actions/IA_MouseLook` | 同上 | 同上 | `BP_FutsalCharacterBase`, `IMC_MouseLook`, `BP_ThirdPersonCharacter` |
| `IA_Jump` | InputAction | `/Game/Input/Actions/IA_Jump` | 同上 | 同上 | `BP_FutsalCharacterBase`, `IMC_Default`, `BP_ThirdPersonCharacter` |

**来源判定（基于路径 + referencers 证据，非猜测）**：
- 4 个 IA **不在** `/Game/ThirdPerson/` 下，而在 `/Game/Input/Actions/`。
- 但 `/Game/Input/{Actions,IMC_*,Touch/}` 这一整套布局（4 个 IA + `IMC_Default` + `IMC_MouseLook` + `BPI_TouchInterface` + `UI_Thumbstick` + `UI_TouchSimple`）**与 UE ThirdPerson 模板自带的 Input 资产集合完全一致**，且其唯一消费者是模板 BP（`BP_ThirdPersonCharacter` / `BP_ThirdPersonPlayerController`）。
- ⇒ 判定：**属于 Epic ThirdPerson 模板资产，但被放在共享的 `/Game/Input/` 目录**（不是 `/Game/ThirdPerson/`）。这一点很重要：Phase 1.6 的依赖白名单里"允许 `/Game/Input/**`"实际上把**模板 Input 资产**也放行了。

IA 自身参数（源）：

| IA | Value Type | consume_input | Triggers | Modifiers |
|---|---|---|---|---|
| IA_Move | `AXIS2D` | True | 无 | 无 |
| IA_Look | `AXIS2D` | True | 无 | 无 |
| IA_MouseLook | `AXIS2D` | True | 无 | 无 |
| IA_Jump | `BOOLEAN` | True | `InputTriggerPressed`, `InputTriggerReleased` | 无 |

---

## 3. IMC Asset + Key Mapping Table

### `/Game/Input/IMC_Default` — 12 mappings

| # | Action | Key | Modifiers | Triggers |
|---|---|---|---|---|
| 1 | IA_Jump | `SpaceBar` | — | — |
| 2 | IA_Jump | `Gamepad_FaceButton_Bottom` | — | — |
| 3 | IA_Move | `W` | `SwizzleAxis` | — |
| 4 | IA_Move | `S` | `SwizzleAxis`, `Negate` | — |
| 5 | IA_Move | `A` | `Negate` | — |
| 6 | IA_Move | `D` | — | — |
| 7 | IA_Move | `Up` | `SwizzleAxis` | — |
| 8 | IA_Move | `Down` | `SwizzleAxis`, `Negate` | — |
| 9 | IA_Move | `Right` | — | — |
| 10 | IA_Move | `Left` | `Negate` | — |
| 11 | IA_Move | `Gamepad_Left2D` | `DeadZone`, `Scalar` | — |
| 12 | IA_Look | `Gamepad_Right2D` | `DeadZone` | — |

### `/Game/Input/IMC_MouseLook` — 1 mapping

| # | Action | Key | Modifiers | Triggers |
|---|---|---|---|---|
| 1 | IA_MouseLook | `Mouse2D` | `Negate` | — |

**注意**：实际的 IMC 是 **2 个**（`IMC_Default` 负责 Move/Look/Jump，`IMC_MouseLook` 单独负责鼠标视角），而任务描述假设只有 1 个 IMC。
**决定**：新资产**保持 2 个 IMC 的真实结构**（`IMC_Futsal_Default` + `IMC_Futsal_MouseLook`），不合并。
理由：两个 IMC 是**分别以 Priority=0 注册**的独立上下文；合并会改变上下文的数量与优先级语义，违反"Priority 语义保持完全一致"。若你确认要合并为单个 `IMC_Futsal_Default`，请在 Phase 2B 前告知。

IMC 的 referencers：**两者都只有** `/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController`（含硬/软引用）。`L_FutsalCourt`、`BP_NoPawnGameMode`、任何其它关卡或蓝图**都不是** IMC 的 referencer ⇒ 可证明**项目中不存在其它 IMC 注册者，Level Blueprint 也没有注册 IMC**（关卡蓝图的引用会记录在 .umap 的 import 表中）。

---

## 4. Runtime AddMappingContext Owner

**唯一所有者：`/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController`**

节点级证据（MCP `get_node_infos`，`type_id = "输入|AddMappingContext"`）：

| 节点 | MappingContext | Priority | Options | self 来源 | 执行来源 |
|---|---|---|---|---|---|
| `EventGraph.K2Node_CallFunction_5` | `/Game/Input/IMC_Default.IMC_Default` | `0` | `(bIgnoreAllPressedKeysUntilRelease=True, bForceImmediately=False, bNotifyUserSettings=False)` | `K2Node_GetSubsystem_0` | `K2Node_ExecutionSequence_0` |
| `EventGraph.K2Node_CallFunction_15` | `/Game/Input/IMC_MouseLook.IMC_MouseLook` | `0` | 同上 | `K2Node_GetSubsystem_2` | `K2Node_Knot_2` |

触发时机（`list_events`）：`BP_ThirdPersonPlayerController` 仅实现 **`ReceiveBeginPlay`**；`ReceivePossess` / `ReceiveUnPossess` **未实现**（⇒ 换 Pawn 时不会重新注册 IMC）。

**Runtime Input Ownership（完整链）**：

```
GameMode
  └── BP_ThirdPersonGameMode            (仅被 Lvl_ThirdPerson 引用；生产管线未使用)
        └── PlayerController
              └── BP_ThirdPersonPlayerController   (BeginPlay)
                    ├── EnhancedInputLocalPlayerSubsystem.AddMappingContext(IMC_Default, 0)
                    ├── EnhancedInputLocalPlayerSubsystem.AddMappingContext(IMC_MouseLook, 0)
                    └── UI_TouchSimple (触摸 UI)
                          └── IMC_Default → IA_Move / IA_Look / IA_Jump
                          └── IMC_MouseLook → IA_MouseLook
                                └── Character EventGraph (IA_* 绑定事件)

生产管线：L_FutsalCourt → BP_NoPawnGameMode (PC = 原生 PlayerController, deps=[]) → ✗ 无 IMC
```

---

## 5. PlayerController / GameMode relationship

| 资产 | Class | player_controller_class | default_pawn_class | dependencies | referencers |
|---|---|---|---|---|---|
| `/Game/FutsalMOT/Blueprints/BP_NoPawnGameMode` | Blueprint | `/Script/Engine.PlayerController`（原生） | `null` | **`[]`** | `/Game/FutsalMOT/Maps/L_FutsalCourt` |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode` | Blueprint | `BP_ThirdPersonPlayerController` | `BP_ThirdPersonCharacter` | `BP_ThirdPersonCharacter`, `BP_ThirdPersonPlayerController`, `/Script/*` | `/Game/ThirdPerson/Lvl_ThirdPerson` |
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController` | Blueprint | — | — | `IMC_Default`, `IMC_MouseLook`, `UI_TouchSimple`, `/Script/EnhancedInput`, `/Script/UMG*` | `BP_ThirdPersonGameMode` |

⇒ **生产 GameMode 与 Epic GameMode 完全不共享 Controller**。FutsalMOT 生产管线目前没有自己的 PlayerController；`BP_FutsalCharacterBase` 被 `BP_NoPawnGameMode` 派生出的**原生 PlayerController** 占有 → 这正是 Input 失效的根因，也是 Phase 2B 要新增 `BP_FutsalPlayerControllerBase` 的理由。

---

## 6. BPI_TouchInterface ownership

| 项 | 值 |
|---|---|
| 路径 | `/Game/Input/Touch/BPI_TouchInterface` |
| Class | `Blueprint`（蓝图接口） |
| Dependencies | `/Script/BlueprintGraph`, `/Script/CoreUObject`, `/Script/Engine`（无资产依赖） |
| **Referencers** | **`BP_FutsalCharacterBase`**, `UI_TouchSimple`, `BP_ThirdPersonCharacter` |
| 接口函数（4） | `Primary Thumbstick`, `Secondary Thumbstick`, `Touch Jump Start`, `Touch Jump End` |
| 来源判定 | 位于 `/Game/Input/Touch/`，与 Epic ThirdPerson 模板的触摸资产集（`BPI_TouchInterface` + `UI_Thumbstick` + `UI_TouchSimple`）完全对应 ⇒ **Epic ThirdPerson 模板资产** |

**`BP_FutsalCharacterBase` 为什么依赖它**：Phase 1 用"复制 `BP_ThirdPersonCharacter`"的方式创建 Base BP，因此继承了它对 `BPI_TouchInterface` 的**接口实现**。实测证据（MCP `list_events` on `BP_FutsalCharacterBase`）：

```
Touch Jump End        bIsImplemented = true
Touch Jump Start      bIsImplemented = true
Secondary Thumbstick  bIsImplemented = true
Primary Thumbstick    bIsImplemented = true
```

即 Base BP 里有 4 个**接口事件节点**（移动端触控）。这是移动端触摸支持，与桌面键鼠无关。

**切断依赖时的建议（本阶段未执行任何方案）**：

| 方案 | 评价 | 建议 |
|---|---|---|
| **A. 复制到 FutsalMOT** | 保留移动端能力，代价是继续携带 4 个空/占位接口事件 | **推荐**：已按此创建 `BPI_FutsalTouchInterface`（副本），Phase 2B 只需把 Base BP 的接口实现重指到它 |
| B. 删除移动端触控支持 | 最干净，但会**删除 BP 图节点**，属于行为变更，且需确认项目永不做移动端 | 备选；需你显式批准 |
| C. 保持共享 | 依赖不解除，违背重构目标 | 否决 |

⚠ 另注：`UI_TouchSimple` 与 `UI_Thumbstick`（两个 WidgetBlueprint）目前**只被 Epic 的 `BP_ThirdPersonPlayerController` 引用**；生产管线完全没有触控 UI。因此即使保留 `BPI_FutsalTouchInterface`，若不移植 `UI_TouchSimple` 链路，触控在 FutsalMOT 侧仍然**不可用**。这点需要你在 Phase 2B 决策。

---

## 7. New Futsal Input Assets

全部位于 `/Game/FutsalMOT/Input/`，**均已 `save_asset` 落盘并二次确认**：

| Asset | Class | Path |
|---|---|---|
| `IA_Futsal_Move` | InputAction | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Move` |
| `IA_Futsal_Look` | InputAction | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Look` |
| `IA_Futsal_MouseLook` | InputAction | `/Game/FutsalMOT/Input/Actions/IA_Futsal_MouseLook` |
| `IA_Futsal_Jump` | InputAction | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Jump` |
| `IMC_Futsal_Default` | InputMappingContext | `/Game/FutsalMOT/Input/Mappings/IMC_Futsal_Default` |
| `IMC_Futsal_MouseLook` | InputMappingContext | `/Game/FutsalMOT/Input/Mappings/IMC_Futsal_MouseLook` |
| `BPI_FutsalTouchInterface` | Blueprint（接口） | `/Game/FutsalMOT/Input/Touch/BPI_FutsalTouchInterface` |

磁盘实测（`Content/FutsalMOT/Input/`）：

```
Actions\IA_Futsal_Jump.uasset            1715
Actions\IA_Futsal_Look.uasset            1405
Actions\IA_Futsal_MouseLook.uasset       1430
Actions\IA_Futsal_Move.uasset            1405
Mappings\IMC_Futsal_Default.uasset       8004
Mappings\IMC_Futsal_MouseLook.uasset     2714
Touch\BPI_FutsalTouchInterface.uasset   16831
```

原资产**未移动、未改名、未删除**（`/Game/Input/**` 全部保持原位）。

---

## 8. Source → Copy mapping

### IA 副本一致性（逐字段比对，`MATCH = true` ×4）

| Source | Copy | Value Type | consume_input | Triggers | Modifiers | MATCH |
|---|---|---|---|---|---|---|
| `IA_Move` | `IA_Futsal_Move` | AXIS2D | True | 无 | 无 | ✅ |
| `IA_Look` | `IA_Futsal_Look` | AXIS2D | True | 无 | 无 | ✅ |
| `IA_MouseLook` | `IA_Futsal_MouseLook` | AXIS2D | True | 无 | 无 | ✅ |
| `IA_Jump` | `IA_Futsal_Jump` | BOOLEAN | True | Pressed+Released | 无 | ✅ |

比对字段：`value_type`、`consume_input`、`trigger_when_paused`、`trigger_events_that_consume_legacy_keys`、`consumes_action_and_axis_mappings`、`triggers`、`modifiers`、`class`。

### IMC 副本 mapping 替换表

`IMC_Default` (12) → `IMC_Futsal_Default` (12)

| 源 Action | 新 Action | Key/Modifiers/Triggers |
|---|---|---|
| `IA_Jump` | `IA_Futsal_Jump` | 完全保持（2 条：SpaceBar / Gamepad_FaceButton_Bottom） |
| `IA_Move` | `IA_Futsal_Move` | 完全保持（9 条：W/S/A/D/Up/Down/Left/Right/Gamepad_Left2D） |
| `IA_Look` | `IA_Futsal_Look` | 完全保持（1 条：Gamepad_Right2D） |

`IMC_MouseLook` (1) → `IMC_Futsal_MouseLook` (1)

| 源 Action | 新 Action | Key/Modifiers/Triggers |
|---|---|---|
| `IA_MouseLook` | `IA_Futsal_MouseLook` | 完全保持（Mouse2D + Negate） |

**独立校验**：
- `IMC_key_mod_trig_equal` = **true**（两个副本的 `(Key, Modifiers, Triggers)` 元组集合与源逐条相等）
- `IMC_action_pairs` 明确只发生 Action 替换，无其它差异
- 登记表复验：`IMC_Futsal_Default` 的依赖 = `IA_Futsal_Jump/Look/Move` + `/Script/EnhancedInput`，**旧 `/Game/Input/Actions/IA_*` 已从依赖表中消失**（证明重指向真正落盘，而非仅内存）

### Touch 副本

| Source | Copy | 接口函数一致性 |
|---|---|---|
| `BPI_TouchInterface` | `BPI_FutsalTouchInterface` | ✅ 4/4 同名：`Primary Thumbstick`, `Secondary Thumbstick`, `Touch Jump Start`, `Touch Jump End` |

---

## 9. Dependency verification

新资产依赖（强制 `scan_paths_synchronous(force=True)` 后）：

```
IA_Futsal_Move       deps=[/Script/EnhancedInput]                       refs=[IMC_Futsal_Default]
IA_Futsal_Look       deps=[/Script/EnhancedInput]                       refs=[IMC_Futsal_Default]
IA_Futsal_MouseLook  deps=[/Script/EnhancedInput]                       refs=[IMC_Futsal_MouseLook]
IA_Futsal_Jump       deps=[/Script/EnhancedInput]                       refs=[IMC_Futsal_Default]
IMC_Futsal_Default   deps=[IA_Futsal_Jump, IA_Futsal_Look, IA_Futsal_Move, /Script/EnhancedInput]  refs=[]
IMC_Futsal_MouseLook deps=[IA_Futsal_MouseLook, /Script/EnhancedInput]  refs=[]
BPI_FutsalTouchInterface deps=[]  refs=[]   （见 UNKNOWN U4）
```

| 禁止依赖项 | 结果 |
|---|---|
| `/Game/ThirdPerson/**` | **0 命中** ✅ |
| `/Game/Characters/Mannequins/**` | **0 命中** ✅ |
| `/Game/FutsalMOT/Characters/FutsalPlayer/**` | **0 命中** ✅ |
| 任何 `Skeleton` / `SkeletalMesh` / `AnimSequence` / `AnimBlueprint` / `BlendSpace` / `UNREAL_RIG` | **0 命中** ✅ |

`forbidden = []`（全部 7 个资产）

**未修改的既有资产**：STEP 10 遵守——`BP_FutsalCharacterBase` 的 EventGraph **未触碰**，它仍然依赖旧 `/Game/Input/Actions/IA_*` 与 `BPI_TouchInterface`（这是 Phase 2B 的工作项）。未执行 Consolidate / Rename / Redirect / Replace References。

---

## 10. UNKNOWN items

| # | UNKNOWN | 说明 | 需要的截图/动作 |
|---|---|---|---|
| U1 | `UI_TouchSimple` → `BPI_TouchInterface` 的实际转发逻辑 | 图表语义不可通过 MCP 读取（只能拿节点类型） | `UI_TouchSimple` 的 EventGraph 截图 |
| U2 | `BP_FutsalCharacterBase` EventGraph 中每个 `IA_*` 绑定节点的逐节点连线 | 同上（语义不可读）。但 Phase 1.5 已用 PIE **实测**移动/跳跃能力为真 | `BP_FutsalCharacterBase` EventGraph 截图（Phase 2B 前建议存档） |
| U3 | per-mapping 的 `Player Mappable Key Settings` / `bIsPlayerMappable` 状态 | 未记录；不影响本次一致性（`Key/Modifiers/Triggers` 已逐条比对相等） | 若需要运行期重绑定，需人工确认 |
| U4 | 复制后的 `BPI_FutsalTouchInterface` 登记表 `deps` 为空数组，而源资产报 `/Script/BlueprintGraph`,`/Script/CoreUObject`,`/Script/Engine` | 属登记表信息差异；接口函数已比对 4/4 一致，功能无影响 | 无需处理，仅记录 |
| U5 | `BP_ThirdPersonPlayerController` 的 `AddMappingContext` 是否还有其它触发路径 | 已确认仅 `ReceiveBeginPlay` 被实现，但未逐节点回溯 ExecutionSequence 上游 | 需要时可截图 EventGraph |

---

## 11. Git commit hash

本报告与 Input 资产为**同一次提交**，因此报告文本无法在不改变该提交 hash 的前提下自引用该 hash。

- **解析方式**：`git rev-parse phase2a-input-assets`
- commit message：`Create Futsal-owned input assets`
- 实际 hash：见本阶段会话回复（下方"报告生成后实际值"）。

> 报告生成后实际值：由 tag `phase2a-input-assets` 解析得到（同一提交）。

---

## 12. Tag

`phase2a-input-assets`（annotated，指向第 11 节的 commit）。已有 tag `phase1-approved` / `refactor-phase1-create-futsal-base` **未被覆盖**。

---

## 13. Remaining dirty files

提交后 `git status --short`：

```
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset     ← EXTERNAL_UNRESOLVED_CHANGE（隔离，未提交）
?? PHASE1_6_STABILIZATION_REPORT.md                                       ← Phase 1.6 报告（按 STEP 11 白名单未纳入本次提交）
```

- `UNREAL_RIG.uasset`：全程未 `add` / `restore` / `checkout` / save / load-resave
- **本阶段未修改任何不在 `/Game/FutsalMOT/Input/` 的既有资产**（尚未提交前的 `git status` 只显示 `?? Content/FutsalMOT/Input/` + 上述两项）
- 未使用 `git add -A`；逐个显式路径 stage
- 未 push

---

## 14. Recommendation for Phase 2B

1. **重指 Base BP 的 Input 引用**：把 `BP_FutsalCharacterBase` 的 EventGraph 中 4 个 IA 引用从 `/Game/Input/Actions/IA_*` 换成 `/Game/FutsalMOT/Input/Actions/IA_Futsal_*`；并把接口实现从 `BPI_TouchInterface` 换成 `BPI_FutsalTouchInterface`（保持函数签名一致，节点无需重建）。
2. **新建 `BP_FutsalPlayerControllerBase`**（建议路径 `/Game/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase`）：
   - `BeginPlay` → `Get EnhancedInputLocalPlayerSubsystem` → `AddMappingContext(IMC_Futsal_Default, 0)` + `AddMappingContext(IMC_Futsal_MouseLook, 0)`
   - 建议**同时实现 `ReceivePossess`**（Epic 版没有），以便换 Pawn 时重新注册上下文
   - Options 建议与 Epic 保持一致（`bIgnoreAllPressedKeysUntilRelease=True`）以维持等价行为
3. **让生产 GameMode 使用新 PC**：在 `BP_NoPawnGameMode` 上设置 `player_controller_class = BP_FutsalPlayerControllerBase`。
   ⚠ 但注意：`BP_NoPawnGameMode` 是 `GlobalDefaultGameMode`，会同时影响其它关卡；确认影响面后再改。
   ⚠ 且该 GameMode 的 `default_pawn_class = null` —— 需要决定 PIE 中角色从何而来（Phase 1.5 的 F1 已证明对它写 `DefaultPawnClass` 不生效，需改用 MCP `ObjectTools.set_properties` 并**用"新建实例后读回"验证**）。
4. **决策项（需你先定）**：
   - 是否合并为单个 `IMC_Futsal_Default`（当前保持 2 个 IMC）；
   - 移动端触控方案 A/B/C（第 6 节）；
   - 是否需要把 `UI_TouchSimple` / `UI_Thumbstick` 也纳入 FutsalMOT namespace。
5. **验证方式**：复用 `L_FutsalCharacterBase_Test`，把实例的 `AutoPossessPlayer=Player0` 与新的 `BP_FutsalPlayerControllerBase` 组合，PIE 中确认 `IA_Futsal_*` 能触发移动/跳跃（这是 Phase 1.5 F2 的真正闭环）。

**Phase 2A 完成，停止。未执行 Phase 2B。**
