# PHASE2B_MANUAL_REWIRE_VERIFICATION — Manual Input Rewire Checkpoint

- 执行时间：2026-09-16
- 基线：branch `refactor/character-architecture` @ `d7f080c715a9940f25045c1fbcbcaf81335a7e50`
- 对象：`/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`
- 性质：**对用户人工完成的 Input Rewire 做只读验证并保存 checkpoint**
- 本阶段**未修改任何资产**（仅强制刷新 Asset Registry + 只读查询）

---

## 1. MANUAL_REWIRE_VERIFIED = TRUE

```
MANUAL_REWIRE_VERIFIED = TRUE
```

验证层次（四层独立证据）：**内存属性 + 磁盘登记表（`scan_paths_synchronous(force=True)`）+ 节点真实 `type_id` + 资产 referencers**。

---

## 2. IA source → target 表

| 源（旧模板资产） | 目标（Futsal owned） | 节点 | 结果 |
|---|---|---|---|
| `/Game/Input/Actions/IA_Move` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Move` | `EventGraph.K2Node_EnhancedInputAction_0` | ✅ |
| `/Game/Input/Actions/IA_Look` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Look` | `EventGraph.K2Node_EnhancedInputAction_2` | ✅ |
| `/Game/Input/Actions/IA_MouseLook` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_MouseLook` | `EventGraph.K2Node_EnhancedInputAction_3` | ✅ |
| `/Game/Input/Actions/IA_Jump` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Jump` | `EventGraph.K2Node_EnhancedInputAction_5` | ✅ |

接口替换：

| 源 | 目标 | 结果 |
|---|---|---|
| `/Game/Input/Touch/BPI_TouchInterface` | `/Game/FutsalMOT/Input/Touch/BPI_FutsalTouchInterface` | ✅ |

原资产**未被移动、改名或删除**（`/Game/Input/**` 保持原位，仍被 Epic 的 `BP_ThirdPersonCharacter` / `UI_TouchSimple` 使用）。

---

## 3. dependencies before / after

**BEFORE**（Phase 2B 起始，实测）

```
IA_Jump, IA_Look, IA_MouseLook, IA_Move          ← /Game/Input/Actions/*
BPI_TouchInterface                                ← /Game/Input/Touch/*
/Script/ClothingSystemRuntimeNv, /Script/EnhancedInput,
/Script/InputBlueprintNodes, /Script/NavigationSystem
```

**AFTER**（本阶段实测，共 9 项）

```
/Game/FutsalMOT/Input/Actions/IA_Futsal_Jump            ✅
/Game/FutsalMOT/Input/Actions/IA_Futsal_Look            ✅
/Game/FutsalMOT/Input/Actions/IA_Futsal_MouseLook       ✅
/Game/FutsalMOT/Input/Actions/IA_Futsal_Move            ✅
/Game/FutsalMOT/Input/Touch/BPI_FutsalTouchInterface    ✅
/Script/ClothingSystemRuntimeNv                         ✅
/Script/EnhancedInput                                   ✅
/Script/InputBlueprintNodes                             ✅
/Script/NavigationSystem                                ✅
```

| 检查 | 结果 |
|---|---|
| `new_deps_missing` | `[]` |
| `unexpected_non_script` | `[]` |
| `any_game_input_left` | `[]`（**已无任何 `/Game/Input/**` 依赖**） |
| `dirty_content` | `[]`（包已保存） |

---

## 4. old_deps_hits = []

```
old_deps_hits = []
```

| 旧依赖 | 状态 |
|---|---|
| `/Game/Input/Actions/IA_Move` | ✅ 已消失 |
| `/Game/Input/Actions/IA_Look` | ✅ 已消失 |
| `/Game/Input/Actions/IA_MouseLook` | ✅ 已消失 |
| `/Game/Input/Actions/IA_Jump` | ✅ 已消失 |
| `/Game/Input/Touch/BPI_TouchInterface` | ✅ 已消失 |

---

## 5. EnhancedInputAction type_id 验证

`BlueprintTools.get_node_infos` 的**节点级 `type_id`**（非 pin 默认值）：

| 节点 | `type_id` | `InputAction` pin 值 | 下游连线 |
|---|---|---|---|
| `K2Node_EnhancedInputAction_0` | `输入\|EnhancedActionEvents\|EnhancedInputActionIA_Futsal_Move` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Move.IA_Futsal_Move` | `Triggered → CallFunction_38` |
| `K2Node_EnhancedInputAction_2` | `输入\|EnhancedActionEvents\|EnhancedInputActionIA_Futsal_Look` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Look.IA_Futsal_Look` | `Triggered → CallFunction_41` |
| `K2Node_EnhancedInputAction_3` | `输入\|EnhancedActionEvents\|EnhancedInputActionIA_Futsal_MouseLook` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_MouseLook.IA_Futsal_MouseLook` | `Triggered → CallFunction_40` |
| `K2Node_EnhancedInputAction_5` | `输入\|EnhancedActionEvents\|EnhancedInputActionIA_Futsal_Jump` | `/Game/FutsalMOT/Input/Actions/IA_Futsal_Jump.IA_Futsal_Jump` | `Started → CallFunction_16`、`Completed → CallFunction_23` |

4/4 全部为 `EnhancedInputActionIA_Futsal_*`。下游 CallFunction 目标与重指前一致 ⇒ 连线未丢失。

EventGraph 组成：**4 × `K2Node_EnhancedInputAction` + 4 × `K2Node_Event` + 7 × `K2Node_CallFunction`**（与重指前完全一致）。

---

## 6. BPI referencer 验证

```
/Game/Input/Touch/BPI_TouchInterface         referencers = [UI_TouchSimple, BP_ThirdPersonCharacter]
/Game/FutsalMOT/Input/Touch/BPI_FutsalTouchInterface  referencers = [BP_FutsalCharacterBase]
```

- `BP_FutsalCharacterBase` **已从旧接口的 referencers 中移除** ✅
- `BPI_FutsalTouchInterface` **已被 BP_FutsalCharacterBase 实现** ✅

---

## 7. Touch 4 个事件状态

MCP `BlueprintTools.list_events`：

| 接口事件 | `bIsImplemented` |
|---|---|
| `Primary Thumbstick` | **true** ✅ |
| `Secondary Thumbstick` | **true** ✅ |
| `Touch Jump Start` | **true** ✅ |
| `Touch Jump End` | **true** ✅ |

⇒ 接口替换过程中 4 个接口事件的实现完整保留（其实现节点未被重建）。

---

## 8. Compile 状态

| 项 | 值 |
|---|---|
| `BlueprintStatus` | **`BS_UP_TO_DATE`**（3） |
| Error | **0** |
| Warning | **0** |
| 证据 | `LogBlueprint` 中 8 条 `Compiling Blueprint '...BP_FutsalCharacterBase'` 记录，**无任何 Error/Warning 行** |
| 保存状态 | `dirty_content = []`（已落盘） |

---

## 9. Git 状态

```
$ git branch --show-current
refactor/character-architecture

$ git rev-parse HEAD
d7f080c715a9940f25045c1fbcbcaf81335a7e50

$ git status --short
 M Content/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.uasset
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset
?? PHASE1_6_STABILIZATION_REPORT.md
?? PHASE2B_INPUT_REWIRE_REPORT.md
```

| 路径 | 状态 |
|---|---|
| `Content/Input` / `Content/ThirdPerson` / `Content/FutsalMOT/Maps` / `Blueprints` / `Animation` / `Sequences` / `Config` / `Test` | **全部 clean** |
| `BP_FutsalPlayerControllerBase` / `GM_FutsalInputTest` | 均**不存在**（未创建） |
| `Content/FutsalMOT/Characters/Base/` 内容 | 仅 `BP_FutsalCharacterBase.uasset` |

---

## 10. UNREAL_RIG = EXTERNAL_UNRESOLVED_CHANGE

```
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset
```

- 归类：**`EXTERNAL_UNRESOLVED_CHANGE`**
- 全程**未** `add` / `restore` / `checkout` / `save` / `resave`
- **不得纳入本次 checkpoint**（见下节 staged 清单）

---

## 附：本次 checkpoint 的 staged 清单

| 文件 | 说明 |
|---|---|
| `Content/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.uasset` | 人工重指结果（IA + 接口） |
| `PHASE2B_MANUAL_REWIRE_VERIFICATION.md` | 本报告 |
| `PHASE1_6_STABILIZATION_REPORT.md` | **`PREVIOUS_PHASE_REPORT`**（Phase 1.6 报告，补入） |

未 stage：`UNREAL_RIG.uasset`、`PHASE2B_INPUT_REWIRE_REPORT.md`（保留为未跟踪诊断报告）、任何其它资产。
