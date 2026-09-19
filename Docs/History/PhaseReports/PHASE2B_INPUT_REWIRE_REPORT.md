# PHASE2B_INPUT_REWIRE_REPORT — Rewire Futsal Input + Create Futsal PlayerController

- 执行时间：2026-09-16
- 基线：branch `refactor/character-architecture` @ `d7f080c715a9940f25045c1fbcbcaf81335a7e50`（tag `phase2a-input-assets`）
- **结论：STEP 2 与 STEP 3 均因工具能力缺失而无法可靠执行 → 按规则停止。STEP 5–11 未执行。未 commit、未打 tag。**
- **没有产生任何净变更**（唯一的写入是一次已回滚的试点，见第 1 节）

---

## 0. 结论摘要（先读这里）

| STEP | 内容 | 结果 |
|---|---|---|
| 1 | Phase 2B 前快照 | ✅ **完成**（第 1/2/3 节） |
| 2 | 重指 EventGraph 的 4 个 IA 节点 | ❌ **受阻 —— `IA_NODE_REWIRE_NOT_RELIABLE`** |
| 3 | 替换 Implemented Interface | ❌ **受阻 —— `INTERFACE_REWIRE_REQUIRES_MANUAL_GRAPH_EDIT`** |
| 4 | Compile / Save / Dependency Audit | ⛔ 未执行（前置未达成） |
| 5–7 | 创建 `BP_FutsalPlayerControllerBase` 并实现 BeginPlay 注册 | ⛔ **未执行**（见下方理由） |
| 8–9 | 创建测试 GameMode / 配置测试地图 | ⛔ **未执行**（同上） |
| 10–11 | PIE 运行期所有权与真实 Input 事件验证 | ⛔ **未执行**（同上） |
| 12–13 | Touch 状态 / 生产隔离 | 部分：Touch = **DEFERRED**（第 12 节）；生产隔离已证明未被触碰（第 13 节） |
| 14–16 | Stage / Commit / Tag | ⛔ **未执行**（STEP 15 前置条件 3 与 4 无法满足） |

**为什么 STEP 5–11 也一并停止**：STEP 2 未完成时，`BP_FutsalCharacterBase` 仍监听旧 `IA_*`，而新 PC 只会注册映射到 `IA_Futsal_*` 的 `IMC_Futsal_*`。此时 STEP 11 要求的"W → IA_Futsal_Move → 位移"在构造上**必然失败**，STEP 10 的 Context 列表虽可验证但整个 Input 链路不可用。继续做 STEP 5–9 只会产出**无法验证、无法提交**的新资产，并留下更多 dirty 状态。故停止并上报告。

---

## 1. BP_FutsalCharacterBase dependencies BEFORE / AFTER

### BEFORE（本阶段开始时的实测值）

```
BP_FutsalCharacterBase
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

### 试点实验（STEP 2 可行性验证，**已回滚**）

我在**单个**节点上做了试点：对 `K2Node_EnhancedInputAction_1` 的 `InputAction` 输出 pin（`index_id = 9`）调用 MCP `set_pin_value`，把值改为 `/Game/FutsalMOT/Input/Actions/IA_Futsal_Move.IA_Futsal_Move`，然后 compile + save + 强制重扫登记表。

结果（**决定性**）：

| 检查 | 结果 |
|---|---|
| pin 值 | 已变为 `IA_Futsal_Move` ✅ |
| `compile` / `bp_status` | 成功 / `BS_UP_TO_DATE`（无 Error、无 Warning） |
| 保存 | true |
| **依赖表（重扫后）** | `[IA_Futsal_Move]` **与** `[IA_Move]` **同时存在** ❌ |
| **节点 `type_id`** | 仍为 `输入|EnhancedActionEvents|EnhancedInputActionIA_Move` ❌ |

⇒ **`set_pin_value` 只改了 pin 的 `DefaultObject`，没有改节点真正的 InputAction 属性。** 节点依旧监听 `IA_Move`，旧依赖无法消除。这正是任务书警告的"假成功"，因此**必须停止 STEP 2**。

回滚动作：把该 pin 值改回 `/Game/Input/Actions/IA_Move.IA_Move` → compile → save。

### AFTER（回滚后实测）

```
deps_after_revert = [
  /Game/Input/Actions/IA_Jump,
  /Game/Input/Actions/IA_Look,
  /Game/Input/Actions/IA_MouseLook,
  /Game/Input/Actions/IA_Move,
  /Game/Input/Touch/BPI_TouchInterface,
  /Script/ClothingSystemRuntimeNv,
  /Script/EnhancedInput,
  /Script/InputBlueprintNodes,
  /Script/NavigationSystem
]
has_futsal_ia_leftover = []          ← 无 IA_Futsal 残留
bp_status = BS_UP_TO_DATE
```

⇒ **语义上与 BEFORE 完全一致**，`/Game/Input/**` 依赖未消除（本阶段目标未达成）。

⚠ 唯一残留：`git diff --stat` 显示 `BP_FutsalCharacterBase.uasset` 为 `M`，`Bin 147961 -> 147953`（**-8 字节**）。这是"试点改动 + 回滚 + 两次重新保存"造成的**重新序列化痕迹**，不是语义变更（依赖表与编译状态均已证明与 HEAD 一致）。**我未使用 `git restore`/`git checkout`**；是否需要恢复到 HEAD 字节级一致，请你决定（见第 17 节）。

---

## 2. IA 节点 source → target table

任务书要求的 4 个映射（**未能应用**，供人工在编辑器中一次完成）：

| # | 节点 refPath | `InputAction` pin | 当前值（source） | 期望值（target） | 状态 |
|---|---|---|---|---|---|
| 1 | `...:EventGraph.K2Node_EnhancedInputAction_1` | `InputAction`, `EGPD_Output`, `index_id = 9` | `/Game/Input/Actions/IA_Move.IA_Move` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Move.IA_Futsal_Move` | ❌ 未应用（试点后已回滚） |
| 2 | `...:EventGraph.K2Node_EnhancedInputAction_4` | 同上 | `/Game/Input/Actions/IA_Look.IA_Look` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Look.IA_Futsal_Look` | ❌ 未应用 |
| 3 | `...:EventGraph.K2Node_EnhancedInputAction_7` | 同上 | `/Game/Input/Actions/IA_MouseLook.IA_MouseLook` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_MouseLook.IA_Futsal_MouseLook` | ❌ 未应用 |
| 4 | `...:EventGraph.K2Node_EnhancedInputAction_6` | 同上 | `/Game/Input/Actions/IA_Jump.IA_Jump` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Jump.IA_Futsal_Jump` | ❌ 未应用 |

（完整路径前缀：`/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.BP_FutsalCharacterBase`）

节点 `type_id`（含内嵌 action 名）：`EnhancedInputActionIA_Move` / `IA_Look` / `IA_MouseLook` / `IA_Jump`

### 已尝试并失败的途径（证据）

| 途径 | 结果 |
|---|---|
| Python `get_editor_property('input_action')` | ❌ `Failed to find property 'input_action'` — 该 UPROPERTY 未暴露给 Python |
| Python `dir(node)` | 41 个成员，**无任何 action/trigger 相关属性** |
| MCP `ObjectTools.list_properties` | ❌ 返回 `{"errorMsg": ...}`（K2Node 不支持） |
| MCP `ObjectTools.set_properties` | ❌ **"the following properties could not be set: input_action"** |
| MCP `set_pin_value`（pin `index_id=9`） | ⚠ 只改 pin 默认值 → **假成功**（依赖表新旧并存） |
| MCP `read_graph_dsl`（EventGraph） | ❌ 返回空字符串（EventGraph 不可 DSL 读取） |
| MCP `find_node_types("EnhancedInputAction")` | ❌ 返回 **`[]`** —— 该事件节点类型**不能**由调色板创建，故"删除旧节点+按类型新建"路线也不存在 |
| MCP `BlueprintTools` 全量工具名 | 无任何 InputAction/接口替换类工具 |

---

## 3. Implemented Interface BEFORE / AFTER

| | 值 |
|---|---|
| BEFORE | `BP_FutsalCharacterBase` implements **`/Game/Input/Touch/BPI_TouchInterface`** |
| AFTER | **未改变** —— 仍为 `BPI_TouchInterface`（STEP 3 受阻） |

**BEFORE 判定证据**：
1. 依赖表含 `/Game/Input/Touch/BPI_TouchInterface`
2. `BPI_TouchInterface` 的 referencers = `BP_FutsalCharacterBase`, `UI_TouchSimple`, `BP_ThirdPersonCharacter`
3. MCP `list_events(BP_FutsalCharacterBase)`：4 个接口事件 `bIsImplemented = true`
   （`Touch Jump Start` / `Touch Jump End` / `Primary Thumbstick` / `Secondary Thumbstick`）

### STEP 3 为何受阻（证据）

| 途径 | 结果 |
|---|---|
| Python `bp.get_editor_property('implemented_interfaces')` | ❌ `Failed to find property` |
| Python `dir(bp)` | 41 个成员，**无任何 interface/graph 相关属性** |
| Python `blueprint_editor_only_data` / `editor_only_data` | ❌ 均不可访问（UE5.8 中该数据在 `UBlueprintEditorOnlyData`，未暴露） |
| `unreal.BlueprintEditorLibrary` **全量 API** | 含 `add_event_override` / `add_function_override` / `reparent_blueprint` / `replace_variable_references` … **但没有任何 interface 增删函数**（无 implement/interface 相关） |
| `unreal` 模块 interface 类 | 只有 `BlueprintInterfaceFactory`、`AudioLinkBlueprintInterface` —— 均为资产工厂，不能改已有 BP 的接口列表 |
| `unreal.KismetEditorUtilities` | ❌ 不存在（`dir(unreal)` 无该名称） |
| MCP `BlueprintTools` 全量工具名 | ❌ 无 interface 增删工具 |

⇒ 按任务书要求报告 **`INTERFACE_REWIRE_REQUIRES_MANUAL_GRAPH_EDIT`**，且**未删除旧 BPI**。

---

## 4. 4 个 Touch interface event 的 preservation evidence

**无法提供。** 原因：STEP 3 在"能证明 4 个接口事件逻辑完整保留"之前就已停止（连"添加新接口"这一步都无法执行），因此没有发生任何接口变更，也就无从产生保留证据。

已知信息（保留在案的快照，供人工改完后比对）：

| 项 | 值 |
|---|---|
| 接口事件数量 | 4（`list_events` 中 `bIsImplemented = true`） |
| 所在位置 | `EventGraph` 内的 `K2Node_Event` 节点（EventGraph 共含 5 个 `K2Node_Event` + 4 个 `K2Node_EnhancedInputAction` + 6 个 `K2Node_CallFunction`） |
| **节点 GUID** | **不可读**（MCP/Python 均无 GUID 访问接口） |
| **下游连线/调用节点数量** | **未读取**（可用 `get_connected_subgraph` 在人工操作前补采） |

> 建议人工操作**前**先执行一次 `get_connected_subgraph(<4 个 K2Node_Event 节点>)` 存证，再改接口。

---

## 5. BP_FutsalPlayerControllerBase graph summary

**未创建。** `/Game/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase` **不存在**。

（子步骤 5/6 依赖 STEP 2 完成后才有意义，且无法验证，故未执行；这样避免了留下不可提交的孤立资产。）

---

## 6. PC dependencies

N/A（PC 未创建）。作为替代，记录**已确认可用的建图工具链**（供后续阶段使用）：
`BlueprintTools.add_event` / `create_node` / `connect_pins` / `set_pin_value` / `find_node_types` / `get_node_type_pins` + `write_graph_dsl`（含完整 DSL 语法文档，已通过 `get_graph_dsl_docs` 获取）。`BlueprintEditorLibrary.create_blueprint_asset_with_parent` 可用于创建指定父类的 BP。

---

## 7. Test GameMode runtime PlayerController class

N/A（测试 GameMode `GM_FutsalInputTest` 未创建；`L_FutsalCharacterBase_Test` 的 WorldSettings **未被修改**，仍为 `GameMode Override = None`）。

---

## 8. PIE runtime Context list

**未执行 PIE**。当前若进入 PIE，注册的将是 Epic 的 `IMC_Default` / `IMC_MouseLook`（若用 Epic PC）或**完全没有 IMC**（若用 `BP_NoPawnGameMode` → 原生 PC）。Phase 2A 已证：生产管线无 IMC 注册者。

---

## 9. IA_Futsal_Move actual event validation

**未执行**（不可验证，见第 0 节理由）。

---

## 10. IA_Futsal_Jump actual event validation

**未执行**（同上）。

---

## 11. Mouse Look validation

**未执行**（同上）。列为 `MANUAL_VALIDATION`。

---

## 12. Mobile Touch status

**`DEFERRED_MOBILE_TOUCH_UI`** —— 明确记录：

- 桌面 Enhanced Input：**未实现、未测试**（本阶段受阻）
- 移动端 Touch UI：**`DEFERRED`**（按决策 2 的 A-lite 方案；且本阶段连"接口替换"都未发生）
- `UI_TouchSimple` / `UI_Thumbstick` **未被复制、未被修改**
- `BP_FutsalCharacterBase` 仍实现旧的 `BPI_TouchInterface`

**不要把移动端 Touch 标记为已完成。**

---

## 13. L_FutsalCourt untouched proof

| 检查 | 结果 |
|---|---|
| `git status --short -- Content/__ExternalActors__ Content/__ExternalObjects__` | **干净（无内容变化）** |
| L_FutsalCourt 是否被打开/保存 | 编辑器当前世界仍是 `/Game/FutsalMOT/Maps/L_FutsalCourt.L_FutsalCourt`；**本阶段未调用任何 save** |
| `BP_NoPawnGameMode` | 未修改（未出现在 git status） |
| `Player_L0~R4` | 未修改（L_FutsalCourt 内，未触碰） |
| Level Sequences | 未修改 |
| `/Game/Input/**` 原始资产 | 未修改（git clean） |
| `/Game/ThirdPerson/**` | 未修改（git clean） |
| `UI_TouchSimple` / `UI_Thumbstick` | 未修改 |
| `DefaultEngine.ini` | 未修改 |
| Fix Up Redirectors / Consolidate / Global Replace | 均未执行 |

---

## 14. git staged list

**staged 为空。** 未执行任何 `git add`。

```
$ git status --short
 M Content/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.uasset
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset
?? PHASE1_6_STABILIZATION_REPORT.md
```

---

## 15. commit hash

**无。未 commit。** STEP 15 的前置条件中：

| 条件 | 状态 |
|---|---|
| 1. BP_FutsalCharacterBase compile clean | ✅（`BS_UP_TO_DATE`）——但这是"未改动"状态 |
| 2. BP_FutsalPlayerControllerBase compile clean | ❌ 资产不存在 |
| 3. Base BP 不再依赖 `/Game/Input/**` | ❌ **仍依赖 5 项** |
| 4. PlayerController 不依赖模板 Input | ❌ 资产不存在 |
| 5. 测试 GameMode runtime PC class 正确 | ❌ 未创建 |
| 6. L_FutsalCourt 未修改 | ✅ |
| 7. UNREAL_RIG 未 stage | ✅ |
| 8. 旧模板资产无修改 | ✅ |

⇒ 条件 2/3/4/5 不满足，**按规则不 commit**。

## 16. tag

**未创建** `phase2b-input-rewired`。已有 tag 均未被覆盖。

---

## 17. remaining dirty files

| 文件 | 状态 | 来源 / 处置建议 |
|---|---|---|
| `Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset` | ` M` | **EXTERNAL_UNRESOLVED_CHANGE**，全程未 add/restore/checkout/save/resave。保持隔离 |
| `Content/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.uasset` | ` M`（`Bin 147961 → 147953`，-8B） | **本阶段试点实验的重新序列化痕迹**。依赖表 / 编译状态已证明与 HEAD 语义一致。**未做 git restore**；如需字节级还原，需你确认（`git restore` 该文件） |
| `PHASE1_6_STABILIZATION_REPORT.md` | `??` | Phase 1.6 报告，仍未纳入任何提交（Phase 2A 的 STEP 11 白名单未包含它） |
| `PHASE2B_INPUT_REWIRE_REPORT.md` | `??` | 本报告 |

---

## 18. UNKNOWN / manual validation items

### 18.1 需要人工在 Unreal Editor 完成的最小工作（**推荐顺序**）

**M1 —— 重指 4 个 IA 节点（替代 STEP 2，约 1 分钟）**
1. 打开 `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`
2. 在 EventGraph 中找到 4 个 `EnhancedInputAction` 事件节点（其 `InputAction` 输出 pin 显示当前资产名）
3. 逐个把该节点上的 `Input Action` 下拉/引脚改成下表的新资产：

| 节点 | 当前 | 改为 |
|---|---|---|
| `K2Node_EnhancedInputAction_1` | `IA_Move` | `IA_Futsal_Move` |
| `K2Node_EnhancedInputAction_4` | `IA_Look` | `IA_Futsal_Look` |
| `K2Node_EnhancedInputAction_7` | `IA_MouseLook` | `IA_Futsal_MouseLook` |
| `K2Node_EnhancedInputAction_6` | `IA_Jump` | `IA_Futsal_Jump` |

4. Compile（应为 0 Error / 0 Warning）→ Save

**M2 —— 替换 Implemented Interface（替代 STEP 3）**
1. 先存证：对 EventGraph 里 4 个接口事件节点（`Touch Jump Start` / `Touch Jump End` / `Primary Thumbstick` / `Secondary Thumbstick`）分别截图，并记录其下游连线
2. Class Settings → Interfaces → **Add** → 选择 `BPI_FutsalTouchInterface`
3. 确认 4 个接口函数仍为 "已实现"（签名一致，编辑器通常自动匹配同名函数）
4. 确认 4 个接口事件节点的连线未丢失
5. 再从 Interfaces 列表 **Remove** `BPI_TouchInterface`
6. Compile → Save

**M3 —— 之后我可继续的自动化部分（STEP 5–11）**：创建 `BP_FutsalPlayerControllerBase`（含 BeginPlay 注册）、`GM_FutsalInputTest`、测试地图 WorldSettings、PIE 所有权/Context 验证、Input 注入尝试。

### 18.2 需要的截图（供你人工操作时核对）

| # | 截图 | 用途 |
|---|---|---|
| S1 | `BP_FutsalCharacterBase` EventGraph 中 4 个 `EnhancedInputAction` 节点区域 | 记录改前状态 |
| S2 | 同上，改后 | 证明 IA 已换成 `IA_Futsal_*` |
| S3 | Class Settings → Interfaces（改前） | 证明只有 `BPI_TouchInterface` |
| S4 | Class Settings → Interfaces（改后） | 证明为 `BPI_FutsalTouchInterface` |
| S5 | 4 个 Touch 接口事件节点 + 下游连线（改前/改后） | 保留证据（U4） |
| S6 | 内容浏览器 `/Game/FutsalMOT/Input/` | 记录 Phase 2A 资产 |
| S7 | 编译器结果面板 | 0 Error / 0 Warning |

### 18.3 结构性问题（本阶段暴露，建议在 Phase 2B 重试前先解决）

**`IA_NODE_REWIRE_NOT_RELIABLE` 的根因**：`UK2Node_EnhancedInputAction` 的 `InputAction` UPROPERTY **既未暴露给 Unreal Python，也不被 MCP `ObjectTools` 支持**，且其节点类型不出现在 `find_node_types` 中。这是当前工具链的**能力缺口**，不是用法问题。若希望后续阶段能自动化此类改写，需要在 `Plugins/FutsalMOTMCP` 中**新增一个专用 tool**（例如 `set_enhanced_input_action_node`：接收节点 refPath + IA refPath，内部调用 `UK2Node_EnhancedInputAction::SetInputAction` 并重建引脚），然后**完整重启 Unreal Editor** 使其生效。 —— 这属于插件开发，本次未执行。

### 18.4 仍需你决策/知悉

1. `BP_FutsalCharacterBase.uasset` 的 -8 字节 `M` 状态：**保持现状** 还是 **`git restore` 到 HEAD**？
2. 是否授权开发 18.3 所述的 MCP 新工具（可让后续阶段完全自动化 STEP 2/3）？
3. 是否按 M1/M2 人工完成后，再由我继续 STEP 5–11 与提交？

---

**Phase 2B 停止。未修改 L_FutsalCourt，未进入动画 Phase，未 commit，未 push。**
