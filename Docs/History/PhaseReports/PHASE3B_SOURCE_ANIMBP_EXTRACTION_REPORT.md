# PHASE3B_SOURCE_ANIMBP_EXTRACTION_REPORT — Extract Decoupled Source AnimBP

- 执行时间：2026-09-16
- 基线：branch `refactor/character-architecture` @ `64ca7ff6811838bc6ad8b2a33c75b67c2ebc0c51`（`git rev-parse phase2b-input-closed-loop^{commit}` == HEAD ✅）
- 结果：**STEP 1–2 通过；STEP 3 受阻并停止。未 commit、未打 tag。**

---

## 0. 结论摘要

| STEP | 内容 | 结果 |
|---|---|---|
| 1 | 复核源 AnimBP | ✅ `BS_UP_TO_DATE`、target = `SK_Mannequin`、恰好 1 个 Cast |
| 2 | 创建 `ABP_FutsalSource`（duplicate） | ✅ 已创建并**显式保存**；原资产 byte-unmodified |
| 3 | 修改 `Character` 变量类型 | ❌ **BLOCKED —— 有节点因类型变化失效** |
| 4–8 | 替换 Cast / 节点验证 / 变量验证 / Compile / 结构等价 | ⛔ **未执行**（STEP 3 未通过） |
| 9–11 | 依赖 / referencer / 原资产未修改 | ✅（针对当前"已回退"状态） |
| 14–15 | stage / commit / tag | ⛔ **未执行**（未全部验证通过） |

**最重要的一条**：

```
PHASE3A_U3_RESOLUTION = RESOLVED   ← 不成立，必须撤销
实际证据：AnimBP 通过 Character 变量读取了 BP_ThirdPersonCharacter 的自定义变量 MotionSpeedMps
```

---

## 1. Baseline

| 项 | 值 |
|---|---|
| branch | `refactor/character-architecture` |
| HEAD | `64ca7ff6811838bc6ad8b2a33c75b67c2ebc0c51` |
| tag `phase2b-input-closed-loop^{commit}` | `64ca7ff6811838bc6ad8b2a33c75b67c2ebc0c51` == HEAD ✅ |
| 允许的 dirty | `M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset`（`EXTERNAL_UNRESOLVED_CHANGE`，全程未 add/restore/checkout/save/resave/modify）+ `?? PHASE3A_ANIMATION_OWNERSHIP_AUDIT.md` ✅ |

## 2. PHASE3A_U3_RESOLUTION

**用户人工结论**：`Character` 的下游全部只用引擎基类成员（`Get Character Movement`、`Get Actor Location` …），未发现 `Character → MotionSpeedMps` / `Character → AnimationClassId` / 自定义变量 / 自定义函数 ⇒ 可安全改类型。

**本轮实测反驳**（节点级证据，见第 4 节）：

| 节点 | 标题 | `self` 引脚 type_id | `self` 连接来源 |
|---|---|---|---|
| `EventGraph.K2Node_VariableGet_17` | `GetMotionSpeedMps` | **`BP Third Person Character 对象引用`** | `EventGraph.K2Node_VariableGet_0` |

⇒ **存在 `Character → MotionSpeedMps` 的读取**，而 `MotionSpeedMps` 是 `BP_ThirdPersonCharacter` 的自定义变量（`0.0f`），**`/Script/Engine.Character` 上不存在**。

```
PHASE3A_U3_RESOLUTION = REVOKED（原判 RESOLVED 不成立）
```

（`AnimationClassId` 一侧维持原判：`find_nodes(title="AnimationClassId")` 在 ABP 内返回 `[]`，未发现读取。）

---

## 3. Source / Target paths

| 角色 | Path | Class |
|---|---|---|
| Source | `/Game/FutsalMOT/Animation/ABP_FutsalPlayer` | AnimBlueprint |
| Target（新建） | `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource` | AnimBlueprint |

磁盘：`Content/FutsalMOT/Animation/Source/ABP_FutsalSource.uasset`（530,802 bytes）

## 4. Duplicate rationale

按 STEP 2 采用 **`duplicate_asset`（禁止从 `ABP_FutsalPlayer_Soccer` / `ABP_SoccerPlayer` 复制）**，以逐节点保留 EventGraph / AnimGraph / StateMachine / Transition / Variables / BlendSpace / Sequence / ControlRig 引用，保证行为等价。

实测结果：

| 项 | SRC | DST（复制后） |
|---|---|---|
| `BlueprintStatus` | `BS_UP_TO_DATE` | `BS_UP_TO_DATE` |
| `target_skeleton` | `SK_Mannequin` | `SK_Mannequin` |
| dependencies | 12 项（含 `BP_ThirdPersonCharacter`、`CR_Mannequin_FootIK`、`BS_Futsal_Locomotion`、4 条 Epic clip） | **与 SRC 完全一致** |
| referencers | `[BP_ThirdPersonCharacter]` | **`[]`** |

**Duplicate 后立即 `save_asset`（吸取 Phase 2A 的"只写内存不落盘"教训）。**
**原 `ABP_FutsalPlayer` 保持 byte-unmodified**（`git status` 显示其路径 clean）。

---

## 5. Character variable old/new type

| | 类型 |
|---|---|
| OLD（原值与当前值） | `BP_ThirdPersonCharacter Object Reference` |
| 目标 NEW（STEP 3 要求） | `/Script/Engine.Character Object Reference` |

**实现方式**：`unreal.BlueprintEditorLibrary.change_member_variable_type(blueprint, 'Character', new_type)`，其中 `new_type` 用 `EdGraphPinType.import_text(...)` 构造（`PinCategory="object"`, `PinSubCategoryObject="/Script/Engine.Character"`）。

- 调用**未抛异常**，属性类型**确实被改了**（编译错误信息原文："属性Character（属于角色 对象引用类型）" ⇒ 属性已变为 `角色/Character`）
- 但 **`EdGraphPinType` 的字段不能经 `get_editor_property` 读回**（`pin_category` 不可访问），因此只能用**编译结果 + 引用节点引脚**间接验证

## 6. Cast node old/new type_id

| | 值 |
|---|---|
| OLD（当前仍为此值） | `工具\|Casting\|CastToBP_ThirdPersonCharacter` |
| 目标 NEW | `工具\|Casting\|CastToCharacter` |

**STEP 4 未执行** ⇒ Cast 节点仍为 `CastToBP_ThirdPersonCharacter`。

## 7. InitializeAnimation connection proof

（STEP 1 复核，节点级）

```
[K2Node_Event_1]  添加事件|事件BlueprintInitializeAnimation
      │ then (EGPD_Output, index_id=1)
      ▼
[K2Node_DynamicCast_2]  工具|Casting|CastToBP_ThirdPersonCharacter     位置 (-960,-640)
      │ Object (EGPD_Input, index_id=1)  ◀── [K2Node_CallFunction_4] 动画|GetOwningActor (self 未连接)
      │ then   (EGPD_Output, 0)          ──▶ [K2Node_VariableSet_1] execute
      │ AsBP Third Person Character (EGPD_Output, 2) ──▶ [K2Node_VariableSet_1] Character
      │ CastFailed (EGPD_Output, 1)      ──▶ 未连接（与原版一致）
      ▼
[K2Node_VariableSet_1]  |SetCharacter   变量名 = Character
```

## 8. Compile result（STEP 3 的失败证据）

改类型后编译 `ABP_FutsalSource` → **`BlueprintStatus.BS_ERROR`**。`LogBlueprint` 错误原文（4 条）：

```
[编译器]编译器错误：和  Get  的 '角色 对象引用和BP Third Person Character 对象引用不兼容。'建立连接失败
[编译器]此蓝图（自身）并非是一个 BP_ThirdPersonCharacter_C，因此 ' Target ' 必须拥有一个连接。
[编译器]BP Third Person Character 对象引用类型的 Character 和属性Character（属于角色 对象引用类型）不匹配
[编译器]变量节点 Get MotionSpeedMps 使用一个无效的目标。它可能依赖于一个没有连接到执行链上且已被清除的节点。
```

### 失败节点清单（STEP 3 要求的"具体失效节点"）

| # | 节点 | 失效原因 |
|---|---|---|
| 1 | `K2Node_VariableSet_1` (`SetCharacter`) 的 `Character` 输入 | 引脚仍是 `BP Third Person Character 对象引用`，与新属性类型 `角色 对象引用` 不匹配 → 原连线被判为不可兼容 |
| 2 | `K2Node_VariableGet_2` (`GetCharacterMovement`) 的 `self` 输入 | 同上（`self` 来自 `VariableSet_1.Output_Get`） |
| 3 | **`K2Node_VariableGet_17` (`GetMotionSpeedMps`) 的 `self` 输入** | **根本原因**：它读的是 `Character.MotionSpeedMps`，而 `MotionSpeedMps` 只存在于 `BP_ThirdPersonCharacter`，`/Script/Engine.Character` 没有该成员 |

### 判定

**这不是工具缺陷，而是设计前提不成立。** `change_member_variable_type` 本身工作正常（属性已改），但 `Character` 变量上确实挂着一个 BP 专属成员读取；把类型降到引擎基类后该读取天然失效。

按 STEP 3 规则：**立即停止；未用临时 Cast 回补**（未创建任何 `Cast To BP_ThirdPersonCharacter` 修补节点、未加 Interface、未加 Property Access、未加 Debug 节点）。

### 已做的状态恢复（非"修补"，为防止留下损坏资产）

把 `ABP_FutsalSource` 的 `Character` 变量类型**回退**为 `BP_ThirdPersonCharacter`，重新编译 → **`BS_UP_TO_DATE`**，并 `save_asset`。
⇒ 该副本现为**健康、等价、0 referencer 的独立副本**，可安全作为 Phase 3B 重试的起点；也证明 `BS_ERROR` 完全由类型变更引起，而非复制本身。

---

## 9. Structural equivalence table

**STEP 8 未执行**（STEP 3 未通过）。当前 SRC 与 DST 的**可读**结构对比：

| 项 | SRC `ABP_FutsalPlayer` | DST `ABP_FutsalSource` | 等价 |
|---|---|---|---|
| Target Skeleton | `SK_Mannequin` | `SK_Mannequin` | ✅ |
| BlueprintStatus | `BS_UP_TO_DATE` | `BS_UP_TO_DATE` | ✅ |
| dependencies（12 项） | — | 与 SRC 逐项相同 | ✅ |
| `CR_Mannequin_FootIK` | 引用 | 引用（**未移除**，符合 STEP 8 要求） | ✅ |
| `BS_Futsal_Locomotion` | 引用 | 引用 | ✅ |
| AnimGraph / StateMachine / Transition 名称集合 | — | 未逐一比对（因 STEP 3 未通过） | UNKNOWN |
| Variables 名称集合 | 17 | 未逐一比对 | UNKNOWN |

## 10. Dependency before / after

| | dependencies |
|---|---|
| SRC `ABP_FutsalPlayer`（未改） | `MM_Idle`、`MM_Jump`、`MM_Land`、`MM_Fall_Loop`、`SK_Mannequin`、`CR_Mannequin_FootIK`、`BS_Futsal_Locomotion`、**`BP_ThirdPersonCharacter`**、`/Script/{AnimGraph,AnimGraphRuntime,ControlRig,ControlRigDeveloper}` |
| DST `ABP_FutsalSource`（类型已回退） | **与 SRC 完全相同**（仍含 `BP_ThirdPersonCharacter`） |

⇒ **`ABP → BP_ThirdPersonCharacter` 硬依赖尚未解除**（STEP 4/9 目标未达成）。

## 11. Referencer result

| 资产 | referencers |
|---|---|
| `ABP_FutsalSource` | **`[]`（0）** ✅ |
| `ABP_FutsalPlayer` | `[BP_ThirdPersonCharacter]`（未变） |

未被 `L_FutsalCourt` / `Player_L0~R4` / `BP_ThirdPersonCharacter(_Soccer)` / 任何 Sequence 引用 ✅ —— 新 ABP 保持孤立。

## 12. Production isolation proof

| 路径 | git 状态 |
|---|---|
| `Content/ThirdPerson` | **clean** |
| `Content/Characters/Mannequins` | **clean** |
| `Content/FutsalMOT/Maps` | **clean** |
| `Content/FutsalMOT/Sequences` | **clean** |
| `Content/Input` | **clean** |
| `Content/FutsalMOT/Animation/ABP_FutsalPlayer.uasset` | **clean（byte-unmodified）** |
| `Content/FutsalMOT/Animation/SoccerPlayer/` | **clean** |
| `Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset` | `M`（`EXTERNAL_UNRESOLVED_CHANGE`，未触碰） |

`git status --short`：
```
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset
?? Content/FutsalMOT/Animation/Source/
?? PHASE3A_ANIMATION_OWNERSHIP_AUDIT.md
```
`dirty_content = []`（无未保存改动）；无 staged；无 commit。

## 13. Remaining Epic dependencies

`ABP_FutsalSource` 当前仍包含（Strategy A 的预期项）：

```
/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle
/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Jump
/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Land
/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Fall_Loop
/Game/Characters/Mannequins/Meshes/SK_Mannequin
/Game/Characters/Mannequins/Rigs/CR_Mannequin_FootIK
/Game/FutsalMOT/Animation/BS_Futsal_Locomotion        （其内部仍依赖 17 条 Epic clip）
/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter  ← 待解除
```

本阶段**未尝试** FULL OWNERSHIP。

## 14. Deferred items

| 项 | 状态 |
|---|---|
| Source Skeleton ownership（`SK_FutsalSource`） | DEFERRED（Strategy B） |
| Source AnimSequence ownership | DEFERRED |
| Source BlendSpace ownership | DEFERRED |
| ControlRig ownership（`CR_Mannequin_FootIK`） | DEFERRED（本阶段明确不移除） |
| Soccer target AnimBP（`ABP_FutsalPlayer_Soccer`） | DEFERRED |
| Mobile Touch UI | `DEFERRED_MOBILE_TOUCH_UI` |

---

## 15. Proposed Phase 3B (retry) — 需你先决策

**阻塞点**：`Character.MotionSpeedMps` 是 `BP_ThirdPersonCharacter` 的自定义变量，ABP 正在读它。这不是"纯依赖清理"，而是**一次功能逻辑替换**，因此需要你选择语义。

| 方案 | 内容 | 评价 |
|---|---|---|
| **B1（推荐）** | `ABP_FutsalSource` 内**不再读** `Character.MotionSpeedMps`，改为由 ABP 自算（它已有自己的 `MotionSpeedMps` 与整套 "Auto Motion Speed / Effective Velocity" 逻辑，可直接用 `CharacterMovement.Velocity` 长度作为输入） | 语义最自然（ABP 已经有一套自动速度系统）；但属**行为变更**，需行为对比验证 |
| B2 | 在 `BP_FutsalCharacterBase` 上**保留** `MotionSpeedMps` 并提供给 ABP；ABP 的 Cast 目标改为 `/Script/Engine.Character` 后，再通过 **Interface**（`BPI_FutsalAnimationSource`）取该值 | 保持原语义（"由 Character 提供速度"），代价是新增接口资产 + Character 侧实现 |
| B3 | 保留 `Character` 为 `Character` 类型，但把 `Get MotionSpeedMps` 替换为 `Get Velocity → VSize` | 等价于 B1，改动面更小 |

### Phase 3B(retry) — Operations（待你选定 B1/B2/B3 后执行）
1. 复用已存在的 `ABP_FutsalSource`
2. 按所选方案改造 `MotionSpeedMps` 的来源（**唯一的逻辑改动点**）
3. `change_member_variable_type`：`Character` → `/Script/Engine.Character`
4. MCP `retarget_node_class`：`CastToBP_ThirdPersonCharacter` → `CastToCharacter`（`old = BP_ThirdPersonCharacter_C`，`new = /Script/Engine.Character`）
5. Compile（要求 `BS_UP_TO_DATE`、0 Error / 0 Warning）
6. 依赖审计：不得含 `/Game/ThirdPerson/**`
7. 行为对比（同轨迹，`ABP_FutsalPlayer` vs `ABP_FutsalSource`）

### Phase 3B(retry) — Do Not Touch
`L_FutsalCourt`、`L_FutsalCharacterBase_Test`、`Player_L0~R4`、任何 Sequence、`ABP_FutsalPlayer`、`ABP_FutsalPlayer_Soccer`、`ABP_SoccerPlayer`、`BP_ThirdPersonCharacter(_Soccer)`、`BP_SoccerPlayer`、`BP_FutsalCharacterBase`、`BP_FutsalPlayerControllerBase`、任何 Skeleton/SkeletalMesh/AnimSequence/BlendSpace/ControlRig/IKRig/IKRetargeter、任何 Input 资产、Epic 模板资产。

### Phase 3B(retry) — Rollback
`ABP_FutsalSource` 目前 0 referencer；删/改它不影响任何现有资产。原 `ABP_FutsalPlayer` 与本阶段前完全一致。

---

## 16. Phase 3C proposal（只设计，不执行）

Phase 3C 应在**独立测试环境**中验证：

```
BP_FutsalCharacterBase（或临时测试 Pawn）
  + SKM_Quinn_Simple（SK_Mannequin）
  + ABP_FutsalSource
```

验证项：`W` / `Space` / `Mouse` 输入 → Locomotion / Jump / Fall / Land 状态切换正常；ABP 变量（`MotionSpeedMps`、`Effective Velocity`、`Auto Facing Yaw Deg`、`CurrentAnimationLevel`）数值合理。

**本阶段未修改 `L_FutsalCharacterBase_Test`，未绑定新 ABP。**

---

## 17. Git checkpoint（STEP 14/15）

**未执行。** 因 STEP 3/4/8 未通过，按规则不 stage、不 commit、不打 tag。

```
$ git status --short
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset
?? Content/FutsalMOT/Animation/Source/
?? PHASE3A_ANIMATION_OWNERSHIP_AUDIT.md
```

---

## 附：本轮未做（自查）

- 未修改 `ABP_FutsalPlayer` / `ABP_FutsalPlayer_Soccer` / `ABP_SoccerPlayer` / `BP_ThirdPersonCharacter(_Soccer)` / `BP_SoccerPlayer` / `BP_FutsalCharacterBase` / `BP_FutsalPlayerControllerBase` ✅
- 未修改 `L_FutsalCourt` / `L_FutsalCharacterBase_Test` / 任何 Level Sequence / 任何 Skeleton / SkeletalMesh / AnimSequence / BlendSpace / ControlRig / IKRig / IKRetargeter / 任何 Input 资产 ✅
- 未 Rename / Move / Delete / Fix Redirectors / Consolidate / Global Replace ✅
- 未用临时 Cast / Interface / Property Access / Debug 节点修补 ✅
- 未 push ✅

**Phase 3B 受阻停止。未执行 Phase 3C。**

---

# Phase 3B Retry（决策 B2）—— STEP 2 完成，STEP 3 受阻

- 决策：**`B2_INTERFACE_SEMANTIC_PRESERVATION`**
- `PHASE3A_U3_RESOLUTION = REVOKED`（确认存在 `Character.MotionSpeedMps` 具体成员读取）
- **未采用 B1 / B3**，理由（用户裁定，本报告记录）：ABP 中为 `Use Auto Motion Speed ? Auto Motion Speed Mps : MotionSpeedMps` ⇒ `MotionSpeedMps` 是**独立于 Auto Motion Speed 的外部输入通道**，必须保留；且 `Velocity.Size()` 单位是 cm/s，不能当作 `MotionSpeedMps`。

## 1. 起点（STEP 1）

沿用既有健康副本 `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource`（**未再次 duplicate**）：`BS_UP_TO_DATE`、target = `SK_Mannequin`、deps 与源逐项一致、refs = `[]`。

## 2. STEP 2 完成 —— 最小动画数据接口

| 项 | 值 |
|---|---|
| Path | `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource` |
| Parent | `/Script/CoreUObject.Interface` |
| 函数（唯一） | **`GetMotionSpeedMps`** |
| 输入 | 无 |
| 输出 | `MotionSpeedMps : Float`（在 `K2Node_FunctionResult_0` 上，input index 1） |
| Pure | **未设置**（未找到可用的 Pure 切换 API）→ 按 STEP 2 允许项保持普通接口函数 |
| 未添加 | `AnimationClassId` / `Velocity` / `GroundSpeed` / `Direction` / `IsFalling` / `MovementComponent` —— 接口保持最小 |
| 状态 | **`BS_UP_TO_DATE`**，已保存；deps = `[]`；refs = `[]` |

## 3. STEP 3 受阻 —— 无法把接口加入 Implemented Interfaces

证据（与 Phase 2B 的同一 API 缺口一致）：

| 途径 | 结果 |
|---|---|
| `unreal.BlueprintEditorLibrary` **全量 API** | 只有 `add_event_override` / `add_function_override` / `reparent_blueprint` / `replace_variable_references` —— **没有任何 interface 增删函数** |
| `bp.get_editor_property('implemented_interfaces')` | ❌ `Failed to find property`（UE5.8 该数据在未暴露的 `UBlueprintEditorOnlyData`） |
| `dir(unreal)` 中 interface 相关类 | 仅 `AudioLinkBlueprintInterface`、`BlueprintInterfaceFactory`（资产工厂） |
| 实测 `BlueprintEditorLibrary.add_function_override(BP_FutsalCharacterBase, 'GetMotionSpeedMps')` | ❌ **返回 `null`**（接口不在 ImplementedInterfaces 中，无法建立 override） |
| MCP `BlueprintTools` 全量工具名 | 无 interface 增删工具 |

⇒ **STEP 4–6 未执行**（在接口尚未被任何 Character 实现时先改 ABP，只会留下"调用无人实现的消息"的半成品，且无法通过 STEP 8 的语义证明）；**STEP 15/16 未执行**（无 stage / 无 commit / 无 tag）。

## 4. 当前状态（全部可安全回滚）

| 资产 | 状态 |
|---|---|
| `BPI_FutsalAnimationSource` | 新建完成、`BS_UP_TO_DATE`、0 refs、0 deps |
| `ABP_FutsalSource` | 健康等价副本、`BS_UP_TO_DATE`、deps 仍含 `BP_ThirdPersonCharacter`（STEP 4/6 未做）、refs `[]` |
| `BP_FutsalCharacterBase` | **未修改**（`BS_UP_TO_DATE`、deps 仍仅 Input、git clean）—— STEP 3 的测试调用未产生任何改动 |
| `ABP_FutsalPlayer` / `ABP_FutsalPlayer_Soccer` / 生产资产 | 全部 clean |

```
$ git status --short
 M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset
?? Content/FutsalMOT/Animation/Interfaces/
?? Content/FutsalMOT/Animation/Source/
?? PHASE3A_ANIMATION_OWNERSHIP_AUDIT.md
?? PHASE3B_SOURCE_ANIMBP_EXTRACTION_REPORT.md
```

## 5. 需要你完成的最小人工步骤（仅 STEP 3）

1. 打开 `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`
2. **Class Settings → Interfaces → Add** → 选择 `BPI_FutsalAnimationSource`
3. 在新出现的 **`GetMotionSpeedMps`** 函数图中实现：`Return Node ← self.MotionSpeedMps`
   ⚠ **必须原样返回**——不得经过 `VSize` / `/100` / `Clamp` / `Scale` / 任何换算（STEP 11 的语义不变要求）
4. Compile → Save（要求 `BS_UP_TO_DATE`、0 Error / 0 Warning）
5. 确认原有 `Touch Jump Start/End`、`Primary/Secondary Thumbstick` 与 Input 依赖未被破坏

完成并告知后，我将继续：STEP 4（`Get Character → GetMotionSpeedMps` 具体成员读取 → `BPI_FutsalAnimationSource.GetMotionSpeedMps` 接口调用，禁止再次 Cast 到具体 BP）→ STEP 5（`Character` 类型 → `/Script/Engine.Character`）→ STEP 6（`CastToCharacter`）→ STEP 7–13 → STEP 15/16。

**Phase 3B Retry 停止于 STEP 3。未执行 Phase 3C。**

---

# Phase 3B Retry（B2）执行记录 —— STEP 3A 起，已完成

- 执行时间：2026-09-19
- 决策：`B2_INTERFACE_SEMANTIC_PRESERVATION`
- 结果：

```
PHASE3A_U3_RESOLUTION = REVOKED
B2_INTERFACE_SEMANTIC_PRESERVATION = IMPLEMENTED
MOTION_SPEED_SEMANTICS = PRESERVED
SOURCE_ANIMBP_EXTRACTION = COMPLETE
ANIMATION_DATA_INTERFACE = BPI_FutsalAnimationSource
ABP_THIRDPERSON_HARD_DEPENDENCY = REMOVED
RUNTIME_VALIDATION = DEFERRED_TO_PHASE3C
```

## STEP 3A — 验证人工实现（PASS）

| 项 | 证据 | 结果 |
|---|---|---|
| Asset Registry refresh | `AssetRegistry.scan_paths_synchronous(["/Game/FutsalMOT"], True, True)` | OK |
| `BP_FutsalCharacterBase` 编译 | `BlueprintStatus.BS_UP_TO_DATE`；`compile_blueprint(warnings_as_errors=True)` 无异常 | ✅ 0 Error / 0 Warning |
| Implemented `BPI_FutsalAnimationSource` | `list_functions(BP)` 含 `GetMotionSpeedMps`，描述为 `NSLOCTEXT("UObjectDisplayNames","BPI_FutsalAnimationSource_C:GetMotionSpeedMps",...)`；`list_graph_names` 含 `GetMotionSpeedMps` | ✅ |
| Implemented `BPI_FutsalTouchInterface` | EventGraph 含 4 个接口事件：`事件PrimaryThumbstick` / `事件SecondaryThumbstick` / `事件TouchJumpStart` / `事件TouchJumpEnd`（type_id `添加事件|触摸|...`） | ✅ |
| `GetMotionSpeedMps` 图结构 | 仅 3 节点：`K2Node_FunctionEntry_0.then → K2Node_FunctionResult_0.execute`，`K2Node_VariableGet_0(MotionSpeedMps) → K2Node_FunctionResult_0.MotionSpeedMps` | ✅ `self.MotionSpeedMps → Return`，无任何换算/中间节点 |
| 输入 / 触摸节点 | `IA_Futsal_Move` / `IA_Futsal_Look` / `IA_Futsal_MouseLook` / `IA_Futsal_Jump`（EnhancedInputAction）+ 4 个触摸事件 | ✅ 仍存在 |
| 变量 | `MotionSpeedMps`、`AnimationClassId` | ✅ |

接口资产 `BPI_FutsalAnimationSource.GetMotionSpeedMps`：无输入，输出 `MotionSpeedMps : Float`（`K2Node_FunctionResult_0` input index 1）。

## STEP 4 — 替换 concrete MotionSpeed 读取（PASS）

原节点 `EventGraph.K2Node_VariableGet_17`（`Get MotionSpeedMps`，`self` 类型 = `BP Third Person Character 对象引用`，来源 `K2Node_VariableGet_0`）已删除。

新建接口消息节点 `EventGraph.K2Node_Message_1`（type_id `类|BPIFutsalAnimationSource|GetMotionSpeedMps(消息)`），接线：

```
ExecutionSequence_0.then_1 ──▶ K2Node_Message_1.execute
K2Node_Message_1.then      ──▶ K2Node_VariableSet_0.execute      (Set MotionSpeedMps)
K2Node_VariableGet_32.Character (角色) ──▶ K2Node_Message_1.self
K2Node_Message_1.MotionSpeedMps (Float) ──▶ K2Node_VariableSet_0.MotionSpeedMps
```

接口函数未标记 Pure，故消息节点带 exec 引脚；已按原执行顺序插入 `ExecutionSequence_0.then_1` 与 `Set MotionSpeedMps` 之间，保持原语义。未使用 Cast / Property Access / fallback / debug。

## STEP 5 — Character 变量类型（PASS）

| | 类型 |
|---|---|
| OLD | `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C` |
| NEW | `/Script/Engine.Character` |

- 方式：`BlueprintEditorLibrary.get_object_reference_type(unreal.Character.static_class())` + `change_member_variable_type(bp, "Character", pt)`；`get_member_variable_type` 回读确认 `PinSubCategoryObject='/Script/Engine.Character'`。
- 剩余 `Character` 下游：`GetActorLocation` / `GetActorRotation`（`AActor`，self pin `Actor 对象引用`）、`GetCharacterMovement`（self pin `角色 对象引用`）、接口消息 `self`（`对象引用`）。**无 concrete BP member。**
- `find_nodes("AnimationClassId") = []`（仍无读取）。

### 类型变更造成的残留节点（已修复，供后续参考）

`change_member_variable_type` 只更新变量定义，**不重建既有 get/set 节点的缓存 PinType**，导致编译错误与残留 `BP_ThirdPersonCharacter` 依赖：

1. `K2Node_VariableSet_1`（原 `SetCharacter`）的 `Character`/`Output_Get` 引脚仍为旧类型 → 删除，重建为 `K2Node_VariableSet_19`（`变量|默认|设置Character`）并复原全部接线。
2. 5 个 `Character` getter（`K2Node_VariableGet_0/_9/_13/_15/_16`）输出引脚仍为旧类型 → 全部删除，重建为 `K2Node_VariableGet_32/_33/_34/_35/_36`（`变量|默认|获取Character`）。
   - `VariableGet_0` 原为 impure（带 `then`/`else`，`else` 未连接）；因编辑器 Python/MCP 无恢复 impure 的 API，重建为 pure，并改为 `Event_0.then → ExecutionSequence_0.execute` 直连（原 `else` 未使用，语义等价）。数据路径 `VariableGet_32.Character → Message_1.self` 不变。
   - 其余 4 个 getter 原本即 pure，接线逐一对回 `CallFunction_0/1/2/10.self`。
   - 该重建也是残留 `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter` 依赖被彻底清除的关键。

## STEP 6 — Cast → CastToCharacter（PASS）

```
BlueprintInitializeAnimation (Event_1).then
      ▼
GetOwningActor (CallFunction_4, self 未连接)
      ▼ Object
Cast To Character (DynamicCast_2, type_id 工具|Casting|CastToCharacter)
      │ As角色 (输出 index 2, 角色 对象引用) ──▶ SetCharacter (VariableSet_19).Character
      │ then (输出 0) ──▶ SetCharacter.execute
      │ CastFailed (输出 1) ──▶ 未连接
      ▼
SetCharacter (VariableSet_19) ──▶ VariableSet_2 ...
```

- `retarget_node_class(old=BP_ThirdPersonCharacter_C, new=/Script/Engine.Character)` 后旧的 `As BP Third Person Character` 引脚残留连线；已 break 并删除旧 `SetCharacter`，重建后接回 `As角色 → Character`。
- `find_nodes("Cast To Character") = [K2Node_DynamicCast_2]`；`find_nodes("BP Third Person Character") = []`。

## STEP 7 — Compile（PASS）

| 资产 | `warnings_as_errors=True` | 状态 |
|---|---|---|
| `ABP_FutsalSource` | 无异常 | `BS_UP_TO_DATE` |
| `BP_FutsalCharacterBase` | 无异常 | `BS_UP_TO_DATE` |
| `BPI_FutsalAnimationSource` | 无异常 | `BS_UP_TO_DATE` |

0 Error / 0 Warning。

## STEP 8 — Dependencies（PASS）

`ABP_FutsalSource` deps（Asset Registry，hard+soft）：

```
/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle
/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Jump
/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Land
/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Fall_Loop
/Game/Characters/Mannequins/Meshes/SK_Mannequin
/Game/Characters/Mannequins/Rigs/CR_Mannequin_FootIK
/Game/FutsalMOT/Animation/BS_Futsal_Locomotion
/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource   ← 新增（要求）
/Script/AnimGraph /Script/AnimGraphRuntime /Script/ControlRig /Script/ControlRigDeveloper
```

- ❌ 不再包含 `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`
- ❌ 不含 `BP_FutsalCharacterBase`
- ✅ 含 `BPI_FutsalAnimationSource`
- 允许保留：`SK_Mannequin`、`CR_Mannequin_FootIK`、`BS_Futsal_Locomotion`、Epic source AnimSequences、`/Script/**`

依赖方向：`ABP_FutsalSource → BPI_FutsalAnimationSource`（不是 → `BP_FutsalCharacterBase`）。

## STEP 9 — 节点级证明（PASS）

| 断言 | 结果 |
|---|---|
| 不存在 `CastToBP_ThirdPersonCharacter` | ✅ `find_nodes("BP Third Person Character") = []` |
| 存在 `CastToCharacter` | ✅ `K2Node_DynamicCast_2` |
| 不存在 TargetClass = `BP_ThirdPersonCharacter` 的 `GetMotionSpeedMps` | ✅ `MotionSpeedMps` 相关节点仅 ABP 自身变量节点 + 接口消息节点 |
| 存在 `BPI_FutsalAnimationSource.GetMotionSpeedMps` | ✅ `K2Node_Message_1` |
| 接口输出接回原 MotionSpeedMps 数据流 | ✅ `Message_1.MotionSpeedMps → Set MotionSpeedMps.MotionSpeedMps` |

## STEP 10 — Structural Equivalence（PASS）

`ABP_FutsalPlayer` vs `ABP_FutsalSource`：

| 项 | 结果 |
|---|---|
| Variables（17 + 继承） | **逐项相同** |
| Graphs（`AnimGraph` / `EventGraph` / `Locomotion{Idle,Walk / Run}` / `Main States{Locomotion,Jump,Fall Loop,Land}` / 8×`Transition`） | **逐项相同** |
| Target Skeleton | 均为 `SK_Mannequin` |
| Functions（`AnimGraph` / `BlueprintThreadSafeUpdateAnimation`） | 相同 |
| Dependencies | 唯一差异：`BP_ThirdPersonCharacter` → `BPI_FutsalAnimationSource` |
| Use Auto Motion Speed / Effective Motion Speed / Jump / Fall / Land | 未改动 |

允许的三项差异：Cast 类型、`Character` 变量类型、`MotionSpeedMps` 来源。唯一额外节点级差异：原 impure `Character` get 重建为 pure（原 `else` 未连接，语义等价，且是清除残留依赖所必需）。

## STEP 11 — Semantic Proof（PASS）

```
BP_FutsalCharacterBase.MotionSpeedMps (Float)
      ▼  BPI_FutsalAnimationSource.GetMotionSpeedMps()  ← 函数体：self.MotionSpeedMps → Return（无换算）
ABP_FutsalSource: Message_1.MotionSpeedMps (Float)
      ▼
Set MotionSpeedMps（ABP 自身变量）
      ▼
AnimGraph / Use Auto Motion Speed / Effective Motion Speed（未改动）
```

数值原样传递，无 `VSize` / `/100` / `Clamp` / `Scale` / `Select` / `Branch`。

```
MOTION_SPEED_SEMANTICS = PRESERVED
```

## STEP 12 — Referencer Isolation（PASS）

`ABP_FutsalSource` referencers = `[]`（0）。未绑定 `L_FutsalCourt` / `L_FutsalCharacterBase_Test` / `Player_L0~R4` / 任何生产 AnimClass。

## STEP 13 — Production Isolation（PASS）

| 路径 | git 状态 |
|---|---|
| `Content/ThirdPerson` | clean |
| `Content/Characters/Mannequins` | clean |
| `Content/FutsalMOT/Maps` | clean |
| `Content/FutsalMOT/Sequences` | clean |
| `Content/Input` | clean |
| `Content/FutsalMOT/Animation/ABP_FutsalPlayer.uasset` | clean（byte-unmodified） |
| `Content/FutsalMOT/Animation/SoccerPlayer/` | clean |
| `Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset` | `M`（`EXTERNAL_UNRESOLVED_CHANGE`，全程未触碰，不 stage） |

## STEP 14/15/16 — 记录 / Stage / Commit

- Staged（仅 5 项）：
  - `Content/FutsalMOT/Animation/Source/ABP_FutsalSource.uasset`
  - `Content/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource.uasset`
  - `Content/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.uasset`
  - `PHASE3A_ANIMATION_OWNERSHIP_AUDIT.md`
  - `PHASE3B_SOURCE_ANIMBP_EXTRACTION_REPORT.md`
- Commit message：`Decouple Futsal source animation data interface`
- annotated tag：`phase3b-source-animbp`
- 未 push。未执行 Phase 3C（运行期行为验证延后至 Phase 3C）。

```
SOURCE_ANIMBP_EXTRACTION = COMPLETE
ANIMATION_DATA_INTERFACE = BPI_FutsalAnimationSource
ABP_THIRDPERSON_HARD_DEPENDENCY = REMOVED
MOTION_SPEED_SEMANTICS = PRESERVED
RUNTIME_VALIDATION = DEFERRED_TO_PHASE3C
```

