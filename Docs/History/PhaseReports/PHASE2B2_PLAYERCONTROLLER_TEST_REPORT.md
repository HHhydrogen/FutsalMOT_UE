# PHASE2B2_PLAYERCONTROLLER_TEST_REPORT — Futsal PlayerController + Enhanced Input Loop

- 执行时间：2026-09-16
- 基线：branch `refactor/character-architecture` @ `8dd56fdf2a44fed762a5599b9075de512dca6419`（tag `phase2b-manual-rewire`）
- 结果：**STEP 1–7 自动通过；STEP 8/9 无法自动验证 → 判定 CASE B，未 commit。**

---

## 0. 结论摘要

| STEP | 内容 | 结果 |
|---|---|---|
| 1 | 再验证 Base BP | ✅ `BS_UP_TO_DATE`，依赖仅 Futsal IA + `BPI_FutsalTouchInterface`，无 `/Game/Input/**` |
| 2 | 创建 `BP_FutsalPlayerControllerBase` | ✅ 干净新建，父类 `/Script/Engine.PlayerController` |
| 3 | BeginPlay 注册链 | ✅ 图与 4 个参数完全符合规格 |
| 4 | Compile / Save / 依赖审计 | ✅ `BS_UP_TO_DATE`、0 Error / 0 Warning、非 Script 依赖仅 2 个 Futsal IMC |
| 5 | 创建 `GM_FutsalInputTest` + 持久化校验 | ✅ **真实磁盘 reload 后** `PlayerControllerClass` 仍正确、`DefaultPawnClass = None` |
| 6 | 配置测试地图 | ✅ reload 后 Override / Actor 类 / AutoPossessPlayer 均保持 |
| 7 | PIE 所有权验证 | ✅ GameMode / PC / Pawn 三类全部正确 |
| 8 | Runtime Mapping Contexts | ❌ 自动读取不可用（拿不到 subsystem 实例）→ **由人工 PIE 覆盖验证** |
| 9 | 真实 Enhanced Input 验证 | ✅ **`MANUAL_INPUT_VALIDATION = PASS`**（人工 PIE：W / Space / Mouse 全部成功）<br>自动注入仍为 `AUTOMATED_INPUT_INJECTION_UNAVAILABLE` |
| 10 | 自动输入（若支持） | ⛔ 未执行（自动注入不可用） |
| 11 | Touch 状态 | ✅ 记录为 `DEFERRED_MOBILE_TOUCH_UI` |
| 12 | 生产隔离验证 | ✅ 生产地图/GameMode/Player/Sequence 全未改动 |
| 14 | 判定 | **CASE B + 人工验证通过 → 允许 commit（STEP 15/16）** |

---

## 0.1 MANUAL PIE RESULT（人工验证结果 —— 非自动）

```
MANUAL_INPUT_VALIDATION = PASS
Enhanced Input closed loop = VERIFIED BY MANUAL PIE
```

| 操作 | 期望链路 | 结果 |
|---|---|---|
| **W** | `IMC_Futsal_Default` → `IA_Futsal_Move` → `BP_FutsalCharacterBase` → 角色前进 | **PASS** |
| **Space** | `IMC_Futsal_Default` → `IA_Futsal_Jump` → `BP_FutsalCharacterBase` → 起跳并落地 | **PASS** |
| **Mouse movement** | `IMC_Futsal_MouseLook` → `IA_Futsal_MouseLook` → 视角 / ControlRotation 变化 | **PASS** |

执行方式：**人工**在 Unreal Editor 中对 `L_FutsalCharacterBase_Test` 启动 PIE，实际按键与移动鼠标，由用户确认。

⚠ **重要区分**：本报告第 8–11 节的**自动**验证结论**仍然有效且未改变**：

```
AUTOMATED_INPUT_INJECTION_UNAVAILABLE
```

即：自动注入路径（`inject_input_for_action` / 物理键鼠事件）**不可用**，上述三个 PASS **来自人工 PIE**，不是自动验证结果，不得据此声称自动注入可用。

---

## 1. PlayerController Blueprint path / parent

| 项 | 值 |
|---|---|
| Path | `/Game/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase` |
| 创建方式 | **`BlueprintTools.create`（全新空 Blueprint）**——**未复制** `BP_ThirdPersonPlayerController` |
| Parent | `/Script/Engine.PlayerController`（原生，非 Epic PC） |
| 磁盘 | `Content/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase.uasset`（新建，未跟踪） |

---

## 2. BeginPlay graph summary

EventGraph 最终节点集（**无任何多余/调试节点**）：

| 节点 | type_id | 说明 |
|---|---|---|
| `K2Node_Event_2` | `添加事件\|事件BeginPlay` | `ReceiveBeginPlay` |
| `K2Node_GetSubsystem_1` | `本地玩家子系统\|获取EnhancedInputLocalPlayerSubsystem` | 输出 `ReturnValue`，**无输入引脚** |
| `K2Node_CallFunction_2` | `输入\|AddMappingContext` | 注册 `IMC_Futsal_Default` |
| `K2Node_CallFunction_3` | `输入\|AddMappingContext` | 注册 `IMC_Futsal_MouseLook` |

连线（逐条经 `get_node_infos` 复核）：

```
Event_2.then (输出 index 1)
    └──▶ CF_2.execute
CF_2.then
    └──▶ CF_3.execute
GetSubsystem_1.ReturnValue ──▶ CF_2.self
GetSubsystem_1.ReturnValue ──▶ CF_3.self
```

未实现 `ReceivePossess` / `ReceiveUnPossess` / `RemoveMappingContext` / `ClearAllMappings` / Touch Widget / 任何其它 Gameplay 逻辑 ✅

---

## 3. 两个 AddMappingContext 的参数

| 节点 | MappingContext | Priority | Options |
|---|---|---|---|
| `K2Node_CallFunction_2` | `/Game/FutsalMOT/Input/Mappings/IMC_Futsal_Default.IMC_Futsal_Default` | `0` | `(bIgnoreAllPressedKeysUntilRelease=True,bForceImmediately=False,bNotifyUserSettings=False)` |
| `K2Node_CallFunction_3` | `/Game/FutsalMOT/Input/Mappings/IMC_Futsal_MouseLook.IMC_Futsal_MouseLook` | `0` | 同上 |

与 Phase 2A 审计到的 Epic PC 两个 `AddMappingContext` 参数**逐字段等价** ✅

---

## 4. PlayerController dependencies

```
BP_FutsalPlayerControllerBase
    ├── /Game/FutsalMOT/Input/Mappings/IMC_Futsal_Default
    ├── /Game/FutsalMOT/Input/Mappings/IMC_Futsal_MouseLook
    └── /Script/EnhancedInput
```

| 检查 | 结果 |
|---|---|
| 非 Script 依赖 = 恰好 2 个 Futsal IMC | ✅ `unexpected_non_script = []` |
| `/Game/Input/**` | ✅ 无 |
| `/Game/ThirdPerson/**` | ✅ 无 |
| `BP_ThirdPersonPlayerController` | ✅ 无 |
| `UI_TouchSimple` / `UI_Thumbstick` | ✅ 无 |
| 任何 Mesh / Skeleton / Animation / AnimBP | ✅ 无 |
| Compile | ✅ `BS_UP_TO_DATE`（0 Error / 0 Warning） |

---

## 5. GM_FutsalInputTest persistence validation

- 路径：`/Game/FutsalMOT/Test/GM_FutsalInputTest`，Parent = `/Script/Engine.GameModeBase`（全新创建）

写入 → 保存 → **`EditorLoadingAndSavingUtils.reload_packages([UPackage])` 强制从磁盘重载** → 回读：

| 属性 | 重载后值 | 结论 |
|---|---|---|
| `PlayerControllerClass` | `/Game/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase.BP_FutsalPlayerControllerBase_C` | ✅ **已持久化** |
| `DefaultPawnClass` | `None` | ✅ 符合要求 |
| `BlueprintStatus` | `BS_UP_TO_DATE` | ✅ |

reload 返回值 `(True, Text(""))`，reload 前 `dirty_content = []`。
**未出现 `TEST_GAMEMODE_PC_CLASS_NOT_PERSISTED`。**

> 说明：Phase 1.5 的 F1（对 GM CDO 写 `DefaultPawnClass` 不落盘）在本次**未复现**——本次用全新创建的 BP + `set_editor_property` + `compile_blueprint` + `save_asset`，并用真实磁盘 reload 验证通过。首次尝试 `reload_packages([path])` 因参数类型错误（需 UPackage）而失败，已改用 `reload_packages([unreal.load_package(path)])` 重做。

---

## 6. Test map configuration

仅修改 `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test`：

| 项 | 修改前 | 修改后（并 reload 复核） |
|---|---|---|
| WorldSettings `default_game_mode` | `None` | **`GM_FutsalInputTest_C`** ✅ |
| `Player_FutsalBase_Test` class | `BP_FutsalCharacterBase_C` | **`BP_FutsalCharacterBase_C`** ✅ |
| `Player_FutsalBase_Test` AutoPossessPlayer | `Player0` | **`Player0`** ✅ |
| 关卡 Actor 总数 | 4 | **4**（**未创建第二个 Pawn**）✅ |
| 保存 | — | `save_current_level()` → `dirty_maps_after = []` ✅ |

---

## 7. PIE GameMode / PC / Pawn runtime classes

PIE world = `/Game/FutsalMOT/Test/UEDPIE_0_L_FutsalCharacterBase_Test`

| 项 | 实测 | 期望 | 结果 |
|---|---|---|---|
| GameMode class | `GM_FutsalInputTest_C` | `GM_FutsalInputTest_C` | ✅ |
| PlayerController class | `BP_FutsalPlayerControllerBase_C`（1 个，label `BP_FutsalPlayerControllerBase0`） | `BP_FutsalPlayerControllerBase_C` | ✅ |
| Pawn | `Player_FutsalBase_Test`，1 个（**无第二 Pawn**） | `Player_FutsalBase_Test` | ✅ |
| Pawn class | `BP_FutsalCharacterBase_C` | `BP_FutsalCharacterBase_C` | ✅ |
| Pawn 的 Controller | `BP_FutsalPlayerControllerBase_C` | — | ✅ |

`GameplayStatics.get_player_pawn(gw, 0)` 与 `get_player_controller(gw, 0)` 返回的类均正确。

---

## 8. Runtime Mapping Contexts

**❌ 无法自动读取 —— 工具能力缺口（本轮未使用任何 Blueprint 调试节点）。**

已穷尽的取实例途径（全部失败）：

| 途径 | 结果 |
|---|---|
| `unreal.EnhancedInputLocalPlayerSubsystem` 类与方法 | ✅ 类与方法**已暴露**（含 `has_mapping_context`、`inject_input_for_action`、`inject_input_vector_for_action`、`query_map_key_in_active_context_set`） |
| `pc.player` / `pc.local_player` | ❌ `Failed to find property` |
| `GameInstance.local_players` | ❌ `Failed to find property` |
| `unreal.SubsystemBlueprintLibrary` | ❌ 未暴露（`dir(unreal)` 中只有 `EditorSubsystemBlueprintLibrary`） |
| 全库扫描（`*Library` / `*Statics` / `*EnhancedInput*`）含 `subsystem` 方法的类 | ❌ **`{}`（零命中）** |
| `LocalPlayer.get_subsystem(cls)` | ❌ 不可达（拿不到 LocalPlayer） |

⇒ **Python/MCP 无法取得 `EnhancedInputLocalPlayerSubsystem` 实例**，因此无法调用 `has_mapping_context` 读出已注册上下文。按规则**未添加任何永久 Debug 节点**。

**间接证据（不能替代直接读取）**：运行期 PC 类为 `BP_FutsalPlayerControllerBase_C`（其 BeginPlay 已执行）；该 BP 的 BeginPlay 图中恰好包含 2 个参数正确的 `AddMappingContext`，且编译 `BS_UP_TO_DATE`。

**状态：自动 = `AUTOMATED_INPUT_INJECTION_UNAVAILABLE` ／ 人工 PIE = `MANUAL_INPUT_VALIDATION = PASS`（见第 0.1 节）**

---

## 9. IA_Futsal_Move validation

**❌ 未自动验证。** 理由见第 8 节（拿不到 subsystem → 无法 `inject_input_vector_for_action`；也无法用 `query_map_key_in_active_context_set` 证明 `W → IA_Futsal_Move` 在 active context set 中生效）。

**未使用** `AddMovementInput` 冒充 —— 按规则不做假通过。

**状态：自动 = `AUTOMATED_INPUT_INJECTION_UNAVAILABLE` ／ 人工 PIE = `MANUAL_INPUT_VALIDATION = PASS`（见第 0.1 节）**

## 10. IA_Futsal_Jump validation

**❌ 未自动验证**（同上）。**状态：自动 = `AUTOMATED_INPUT_INJECTION_UNAVAILABLE` ／ 人工 PIE = `MANUAL_INPUT_VALIDATION = PASS`（见第 0.1 节）**

## 11. MouseLook validation

**❌ 未自动验证**（同上）。**状态：自动 = `AUTOMATED_INPUT_INJECTION_UNAVAILABLE` ／ 人工 PIE = `MANUAL_INPUT_VALIDATION = PASS`（见第 0.1 节）**

---

## 12. Automated vs Manual validation distinction

| 项 | 自动验证 | 人工验证 |
|---|---|---|
| PC BP 存在 / 父类 / 编译 | ✅ | — |
| PC BeginPlay 图结构与 4 个参数 | ✅（节点级 `get_node_infos`） | — |
| PC 依赖隔离 | ✅ | — |
| GM 属性持久化 | ✅（磁盘 reload 后回读） | — |
| 测试地图配置 + reload | ✅ | — |
| PIE GameMode / PC / Pawn 所有权 | ✅ | — |
| **运行期已注册 Mapping Context 列表** | ❌ | **需要** |
| **W → IA_Futsal_Move → 位移** | ❌ | **需要** |
| **Space → IA_Futsal_Jump → 跳跃** | ❌ | **需要** |
| **Mouse2D → IA_Futsal_MouseLook → 视角** | ❌ | **需要** |

报告结论（自动部分，保持原样不变）：**`AUTOMATED_INPUT_INJECTION_UNAVAILABLE`**（既无真实键鼠注入 API，也无法取到 subsystem 以使用 Enhanced Input 注入）。

人工部分（本阶段最终结论）：**`MANUAL_INPUT_VALIDATION = PASS`**，**`Enhanced Input closed loop = VERIFIED BY MANUAL PIE`**。

### 最小人工验证步骤（1 次 PIE）—— **已执行，结果为 PASS**

1. 在编辑器中打开 `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test`
2. 点击 Play（PIE，视口模式）
3. 确认角色被玩家控制器占有（不是 AIController）
4. **按 `W`** → 角色应向前移动
5. **按 `Space`** → 角色应起跳，随后落地
6. **移动鼠标** → 视角/ControlRotation 应变化
7. （可选）在 PIE 中打开 `EnhancedInputLocalPlayerSubsystem` 观察已注册上下文，应为 `IMC_Futsal_Default` + `IMC_Futsal_MouseLook`，且**不含** `IMC_Default` / `IMC_MouseLook`
8. 把结果告诉我；确认通过后我再执行 STEP 15/16 的 stage + commit + tag

> **已完成**：用户人工 PIE 确认 W / Space / Mouse 全部生效 → **Input 行为链路（键 → IMC → IA → BP）已闭环**。
> 自动注入部分仍记为 `AUTOMATED_INPUT_INJECTION_UNAVAILABLE`，未伪称为自动验证。

---

## 13. Mobile Touch = DEFERRED

```
Mobile Touch UI = DEFERRED_MOBILE_TOUCH_UI
```

- `BPI_FutsalTouchInterface`：**已接入** `BP_FutsalCharacterBase` ✅（Phase 2B.1 已提交）
- `UI_TouchSimple` / `UI_Thumbstick`：**未迁移、未复制、未修改**
- `BP_FutsalPlayerControllerBase`：**不创建任何 Touch Widget**（其依赖表中无任何 Widget）
- 因此触控在 FutsalMOT 侧**仍然不可用**。

**不得把移动端支持标记为完成。**

---

## 14. Production isolation proof

| 检查项 | 结果 |
|---|---|
| `/Game/FutsalMOT/Maps/L_FutsalCourt` git 状态 | **clean**（external actors/objects 均无内容变化） |
| L_FutsalCourt WorldSettings `default_game_mode` | **`BP_NoPawnGameMode_C`**（原生产设置，未改）✅ |
| `BP_NoPawnGameMode` 的 `player_controller_class` | **`/Script/Engine.PlayerController`**（仍为原生，未改）✅ |
| `Player_L0~R4` | 100 个 Actor 全在，L_FutsalCourt 未被保存 ✅ |
| Level Sequence | 未修改（`Sequences/` clean） |
| `Content/Input` / `Content/ThirdPerson` | clean ✅ |
| Fix Up Redirectors / Consolidate / Global Replace | 均未执行 |
| 编辑器当前地图 | `/Game/FutsalMOT/Maps/L_FutsalCourt.L_FutsalCourt`（**只打开、未保存**，`dirty_maps = []`）✅ |

**本阶段完全未让生产地图改用新 PC。**

---

## 15. Remaining dirty files

```
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset      ← EXTERNAL_UNRESOLVED_CHANGE（隔离，未 add/restore/checkout/save/resave）
 M Content/FutsalMOT/Test/L_FutsalCharacterBase_Test.umap                  ← 本阶段有意修改（测试地图 WorldSettings）
?? Content/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase.uasset ← 本阶段新建
?? Content/FutsalMOT/Test/GM_FutsalInputTest.uasset                        ← 本阶段新建
?? PHASE2B_INPUT_REWIRE_REPORT.md                                          ← 上一阶段诊断报告（保留未跟踪）
```

（本报告 `PHASE2B2_PLAYERCONTROLLER_TEST_REPORT.md` 亦为未跟踪。）

---

## 16. Checkpoint（人工验证通过后执行）

人工 PIE 确认通过（`MANUAL_INPUT_VALIDATION = PASS`）后执行 STEP 15/16。

**staged（5 项）**：

| 文件 | 类型 |
|---|---|
| `Content/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase.uasset` | 本阶段新建 |
| `Content/FutsalMOT/Test/GM_FutsalInputTest.uasset` | 本阶段新建 |
| `Content/FutsalMOT/Test/L_FutsalCharacterBase_Test.umap` | 本阶段有意修改 |
| `PHASE2B2_PLAYERCONTROLLER_TEST_REPORT.md` | 本报告 |
| `PHASE2B_INPUT_REWIRE_REPORT.md` | **`DIAGNOSTIC_REPORT`**（Phase 2B 工具自动重连失败诊断报告，按许可补入） |

**未 stage**：`UNREAL_RIG.uasset`（`EXTERNAL_UNRESOLVED_CHANGE`）、任何生产地图、任何 production external actor/object、任何既有 ThirdPerson/Input 原始资产。

- commit message：`Add Futsal input controller test pipeline`
- annotated tag：`phase2b-input-closed-loop`
- 不 push

**Phase 2B.2 完成（`INPUT_LAYER_STATUS = COMPLETE`）。未进入 Animation Phase。**
