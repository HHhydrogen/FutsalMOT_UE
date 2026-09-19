# PHASE3A_ANIMATION_OWNERSHIP_AUDIT — Animation Ownership Audit

- 执行时间：2026-09-16
- 基线：branch `refactor/character-architecture` @ `64ca7ff6811838bc6ad8b2a33c75b67c2ebc0c51`（tag `phase2b-input-closed-loop` == HEAD ✅）
- `INPUT_LAYER_STATUS = COMPLETE`（Phase 2B.2）
- 性质：**READ-ONLY AUDIT** —— 本阶段**未修改、未创建、未重命名、未移动、未删除任何资产**，未 Fix Redirectors / Consolidate，未保存任何资产
- 唯一写入：本报告文件

---

## 0. 结论速览

| 问题 | 结论 |
|---|---|
| 谁在用哪套动画 | 左队 `Player_L0..L4` → `UNREAL_RIG` + `ABP_FutsalPlayer_Soccer`（**实例覆盖**）；右队 `Player_R0..R4` → `SKM_Quinn_Simple` + `ABP_FutsalPlayer`（**继承类默认**） |
| AnimBP → CharacterBP 循环依赖根因 | **两个 ABP 各有一个 `Cast To BP_ThirdPersonCharacter`**，在 `BlueprintInitializeAnimation` 里把 OwningActor 强转后存入变量 `Character` |
| `*_Soccer` 是什么 | **batch-retarget 后烘焙的资产**（源 = Epic Unarmed 的 20 条 clip）；**不是** soccer 专属动作 |
| SoccerSource 的 7 条 `LS_*_InPlace` | **soccer 专属源动画**（backpedal / defense jog / sprint / GK shuffle / pivot90），在 `SK_Mannequin` 上，**0 引用、完全未接线** |
| ControlRig 骨骼错配 | `ABP_FutsalPlayer_Soccer`（target = `UNREAL_RIG_Skeleton`）引用了为 `SK_Mannequin` 编写的 `CR_Mannequin_FootIK` |
| `ABP_SoccerPlayer` / `BP_SoccerPlayer` | 均为 **EXPERIMENTAL_STUB**，0 level instance / 0 生产使用 |
| 动画侧 Epic 边界 | 6 类共 20 个 FutsalMOT 资产仍依赖 Epic（详见第 9 节） |

---

## 1. Current Character → AnimBP matrix

（默认值来自 CDO；实例值来自 L_FutsalCourt 中的实际 Actor，逐项与 CDO 比较）

| Actor / Class | Class Default Mesh | Instance Mesh | Class Default AnimBP | Instance AnimBP | Skeleton |
|---|---|---|---|---|---|
| `BP_ThirdPersonCharacter` (CDO) | `SKM_Quinn_Simple` | — | `ABP_FutsalPlayer_C` | — | `SK_Mannequin` |
| `BP_ThirdPersonCharacter_Soccer` (CDO) | `UNREAL_RIG` | — | `ABP_FutsalPlayer_Soccer_C` | — | `UNREAL_RIG_Skeleton` |
| `BP_SoccerPlayer` (CDO) | `UNREAL_RIG` | — | `ABP_SoccerPlayer_C` | — | `UNREAL_RIG_Skeleton` |
| `BP_FutsalCharacterBase` (CDO) | **None** | — | **None** | — | — |
| **`Player_L0`** | `SKM_Quinn_Simple` | `UNREAL_RIG` → **INSTANCE OVERRIDE** | `ABP_FutsalPlayer_C` | `ABP_FutsalPlayer_Soccer_C` → **INSTANCE OVERRIDE** | `UNREAL_RIG_Skeleton` |
| **`Player_L1`** | 同上 | `UNREAL_RIG` → **INSTANCE OVERRIDE** | 同上 | `ABP_FutsalPlayer_Soccer_C` → **INSTANCE OVERRIDE** | `UNREAL_RIG_Skeleton` |
| **`Player_L2`** | 同上 | 同上 | 同上 | 同上 | `UNREAL_RIG_Skeleton` |
| **`Player_L3`** | 同上 | 同上 | 同上 | 同上 | `UNREAL_RIG_Skeleton` |
| **`Player_L4`** | 同上 | 同上 | 同上 | 同上 | `UNREAL_RIG_Skeleton` |
| **`Player_R0`** | `SKM_Quinn_Simple` | `SKM_Quinn_Simple` → **INHERITED** | `ABP_FutsalPlayer_C` | `ABP_FutsalPlayer_C` → **INHERITED** | `SK_Mannequin` |
| **`Player_R1..R4`** | 同上 | 同上（INHERITED） | 同上 | 同上（INHERITED） | `SK_Mannequin` |

- Actor 类：10 个 Player 全部是 **`BP_ThirdPersonCharacter_C`**（不是 `BP_SoccerPlayer_C`，也不是 `BP_ThirdPersonCharacter_Soccer_C`）
- Mesh 组件名 `CharacterMesh0`；组件相对变换（0,0,-89 / 0,270,0 / 1,1,1）全部 **INHERITED**
- 材质：无任何组件级 override（`override_materials` 为空/全 None）
- ⇒ **左右两队走的是两套完全不同的视觉 + 动画链路**，且左队靠"实例覆盖"实现，与类默认不一致

---

## 2. AnimBP comparison

### 2.1 基本信息

| 项 | `ABP_FutsalPlayer` | `ABP_FutsalPlayer_Soccer` |
|---|---|---|
| Path | `/Game/FutsalMOT/Animation/ABP_FutsalPlayer` | `/Game/FutsalMOT/Animation/SoccerPlayer/ABP_FutsalPlayer_Soccer` |
| Target Skeleton | **`SK_Mannequin`**（Epic） | **`UNREAL_RIG_Skeleton`** |
| Referencers | `BP_ThirdPersonCharacter` | `BP_ThirdPersonCharacter_Soccer` + 5 个 L_FutsalCourt external actor 包 |
| AnimGraph 结构 | `AnimGraph` → `SM0 "Locomotion"`{`AnimStateNode_1 Idle`, `AnimStateNode_2 Walk / Run`} + `SM1 "Main States"`{`AnimStateNode_0 Locomotion`, `AnimStateNode_1 Jump`, `AnimStateNode_2 Fall Loop`, `AnimStateNode_3 Land`} | **完全相同的图名/状态名/Transition 编号** |
| Transition 数 | Locomotion 2 + Main States 8（`AnimStateTransitionNode_0/1/3/5/6/7`…） | **相同编号集合** |
| EventGraph 节点数 | 92（Phase 1 实测） | **相同的 92 节点结构** |

### 2.2 Variables（**两者 17 项完全一致**）

`Character`, `MovementComponent`, `Velocity`, `GroundSpeed`, `Direction`, `ShouldMove`, `IsFalling`, `MotionSpeedMps`, `Previous Location`, `Auto Motion Speed Mps`, `Speed Initialized`, `Use Auto Motion Speed`, `Effective Motion Speed Mps`, `Auto Motion Velocity`, `Effective Velocity`, `Auto Facing Yaw Deg`, `CurrentAnimationClass`

- `list_variables` 返回的**名称集合逐项相同**（Phase 1 / Phase 2A 两次实测一致）
- **类型 / 默认值：UNKNOWN** —— `UBlueprint::NewVariables`（`var_type` / `default_value`）在 UE 5.8 已移入未暴露的 `UBlueprintEditorOnlyData`，Python 与 MCP 均不可读（详见第 12 节）

### 2.3 直接资产引用（来自 Asset Registry，硬/软依赖）

| | `ABP_FutsalPlayer` | `ABP_FutsalPlayer_Soccer` |
|---|---|---|
| BlendSpace | `BS_Futsal_Locomotion` | `BS_Futsal_Locomotion_Soccer` |
| Skeleton | `SK_Mannequin` | `UNREAL_RIG_Skeleton` |
| Mesh | — | `UNREAL_RIG` |
| AnimSequence | `MM_Idle`, `MM_Jump`, `MM_Land`, `MM_Fall_Loop` | `MM_Idle_Soccer`, `MM_Jump_Soccer`, `MM_Land_Soccer`, `MM_Fall_Loop_Soccer` |
| ControlRig | **`CR_Mannequin_FootIK`** | **`CR_Mannequin_FootIK`** |
| CharacterBP | **`BP_ThirdPersonCharacter`** | **`BP_ThirdPersonCharacter`** |
| /Script | AnimGraph, AnimGraphRuntime, ControlRig, ControlRigDeveloper | AnimGraph, AnimGraphRuntime, ControlRigDeveloper |

### 2.4 结论：`ABP_FutsalPlayer_Soccer` 是什么？

**答：是"逻辑克隆 + 换 Skeleton + 换动画资产"，并且证据充分。**

依据（全部来自实测）：
1. **Variables 名称集合完全相同**（17/17）
2. **AnimGraph 状态机名、State 名、Transition 节点编号集合完全相同**（`Locomotion{Idle, Walk / Run}` + `Main States{Locomotion, Jump, Fall Loop, Land}`）
3. **EventGraph 节点数相同（92）**，且关键子链逐节点一致（见第 3 节：`Event_1 → DynamicCast_2 → VariableSet_1`，节点名、`index_id`、位置 (x,y) 全部相同）
4. **差异恰为两处**：`target_skeleton`（`SK_Mannequin` → `UNREAL_RIG_Skeleton`）与全部动画资产（Epic Unarmed → `*_Soccer`）
5. **例外**：`CR_Mannequin_FootIK` **两套都引用同一个**（未随 skeleton 替换）——见第 7 节

---

## 3. Circular dependency root cause（`ABP → BP_ThirdPersonCharacter`）

### 3.1 精确来源

两个 ABP 的 EventGraph 中各存在**唯一一个 Cast 节点**：

```
节点:  K2Node_DynamicCast_2
type:  工具|Casting|CastToBP_ThirdPersonCharacter     ← Cast To BP_ThirdPersonCharacter
Graph: EventGraph
位置:  (x=-960, y=-640)   （两个 ABP 位置相同）
```

完整链路（节点级 `get_node_infos` 证据）：

```
[K2Node_Event_1]  type_id = 添加事件|事件BlueprintInitializeAnimation
      │ then (输出 index 1)
      ▼
[K2Node_DynamicCast_2]  type_id = 工具|Casting|CastToBP_ThirdPersonCharacter
      │  Object  ◀── [K2Node_CallFunction_4]  type_id = 动画|GetOwningActor  (self 未连接)
      │  then    ──▶ Set Character.execute
      │  AsBP Third Person Character (输出 index 2) ──▶ Set Character.Character (输入 index 1)
      │  CastFailed ──▶ （未连接，悬空）
      ▼
[K2Node_VariableSet_1]  type_id = |SetCharacter
      变量名        = Character
      变量类型      = BP ThirdPersonCharacter 对象引用
      │ then ──▶ [K2Node_VariableSet_2] …
      │ Output_Get ──▶ [K2Node_VariableGet_2]
```

⇒ **DEPENDENCY EDGE（唯一来源）**：
```
ABP_FutsalPlayer            ──Cast To BP_ThirdPersonCharacter──▶ BP_ThirdPersonCharacter
ABP_FutsalPlayer_Soccer     ──Cast To BP_ThirdPersonCharacter──▶ BP_ThirdPersonCharacter
```
即：**在 `BlueprintInitializeAnimation` 中，把 `GetOwningActor()` 强转为 `BP_ThirdPersonCharacter` 并缓存进 ABP 变量 `Character`**。

### 3.2 下游读取

| 项 | 结果 |
|---|---|
| `CastFailed` 是否处理 | ❌ **未连接** → 若 OwningActor 不是该 BP，`Character` 保持 null，后续读取静默失效 |
| `Character` 变量被谁读取 | `K2Node_VariableGet_2`（读变量本身）→ 后续节点链（EventGraph 92 节点） |
| **`MotionSpeedMps`** | ABP **自身也有**同名变量；`find_nodes(title="AnimationClassId")` 返回 **`[]`** → ABP 图内无该名节点；`MotionSpeedMps` 是否为 ABP 自算 or 从 `Character` 读入 → **UNKNOWN**（需逐节点核对，见第 12/13 节） |
| **`AnimationClassId`** | 该变量定义在 **Character BP**（`BP_ThirdPersonCharacter` / `BP_FutsalCharacterBase` 各有 `AnimationClassId: int = 0`）；ABP 图内 `find_nodes` **无同名节点** ⇒ **当前无法证明 ABP 读取了它**（可能仅由 CharacterBP 自己使用，或通过 `Character` 变量间接读取）→ **UNKNOWN** |

> 结论：**循环依赖（CharBP ↔ ABP）的唯一技术原因是这个 Cast**，而不是变量名。`MotionSpeedMps` / `AnimationClassId` 是否经由该通道进入 AnimBP，**证据不足，标为 UNKNOWN，不猜**。

---

## 4. Source Animation Library

### 4.1 A. `SOURCE_CANONICAL_CANDIDATE`（target = `SK_Mannequin`）

| 组 | 资产 | 数量 | Referencers |
|---|---|---|---|
| Epic Unarmed（被真正使用） | `MM_Idle`、`MM_Jump`、`MM_Land`、`MM_Fall_Loop`、`MF_Unarmed_{Jog,Walk}_{Fwd,Bwd,Left,Right,Fwd_Left,Fwd_Right,Bwd_Left,Bwd_Right}` | 20（去重 17+3） | `BS_Futsal_Locomotion` / `ABP_FutsalPlayer` |
| Futsal 自有 BlendSpace | `/Game/FutsalMOT/Animation/BS_Futsal_Locomotion` | 1 | `ABP_FutsalPlayer` |
| **Futsal 自有 soccer 源动画** | `/Game/FutsalMOT/Animation/SoccerSource/LS_*_InPlace` | **7** | **0（未接线）** |

### 4.2 B. `RETARGETED_REAL_PLAYER`（target = `UNREAL_RIG_Skeleton`）

| 组 | 资产 | 数量 |
|---|---|---|
| BlendSpace | `BS_Futsal_Locomotion_Soccer` | 1 |
| 重定向后动画 | `MM_{Idle,Jump,Land,Fall_Loop}_Soccer` + `MF_Unarmed_{Jog,Walk}_*_Soccer` | 21 |

### 4.3 完整资产清单（本节汇总）

```
SOURCE (SK_Mannequin)                     RETARGETED (UNREAL_RIG_Skeleton)
──────────────────────────                ──────────────────────────────────
Epic Unarmed ×20  ──┐                     MM_Idle_Soccer
                    │                     MM_Jump_Soccer
BS_Futsal_Locomotion┘                     MM_Land_Soccer
  ↑ 引用 Epic Unarmed ×17                 MM_Fall_Loop_Soccer
                                          MF_Unarmed_Jog_*_Soccer  ×8
SoccerSource/LS_*_InPlace ×7              MF_Unarmed_Walk_*_Soccer ×8
  （0 引用，未接线）                       BS_Futsal_Locomotion_Soccer
                                            ↑ 引用上述 17 条
                                          ABP_FutsalPlayer_Soccer 引用其中 4 条 + BS
```

---

## 5. Retargeted Animation Library

全部 21 条 `*_Soccer` 的实测属性（节选关键项）：

| Asset | Skeleton | sequence_length (s) | rate_scale | enable_root_motion | force_root_lock |
|---|---|---|---|---|---|
| `MM_Idle_Soccer` | `UNREAL_RIG_Skeleton` | 7.5667 | 1.0 | False | False |
| `MM_Jump_Soccer` | 同上 | 0.8667 | 1.0 | False | True |
| `MM_Land_Soccer` | 同上 | 0.8667 | 1.0 | False | True |
| `MM_Fall_Loop_Soccer` | 同上 | 3.0 | 1.0 | False | True |
| `MF_Unarmed_Jog_Fwd_Soccer` | 同上 | 1.7667 | 1.0 | **True** | True |
| `MF_Unarmed_Walk_Fwd_Soccer` | 同上 | 1.5 | 1.0 | **True** | True |

- 命名与 Epic Unarmed 一一对应（`MM_Idle`→`MM_Idle_Soccer`、`MF_Unarmed_Jog_Fwd`→`MF_Unarmed_Jog_Fwd_Soccer` …）
- 20 条 Epic clip 全部有对应 `*_Soccer`（`MM_Idle` 同时被 BS 与 SM 使用，故 17+4=21 个文件）
- ⇒ **`*_Soccer` 是 Epic Unarmed clip 的 retarget 烘焙副本**，**不是** soccer 专属动作，也**不是**由 `SoccerSource/LS_*` 生成的

---

## 6. Retarget Pipeline

### 6.1 资产实测

| 资产 | Class | 关键实测 |
|---|---|---|
| `IKR_Quinn` | IKRigDefinition | `preview_skeletal_mesh = SKM_Quinn_Simple`；deps = `SKM_Quinn_Simple` + `/Script/IKRig` |
| `IKR_SoccerPlayer` | IKRigDefinition | `preview_skeletal_mesh = UNREAL_RIG`；deps = `UNREAL_RIG` + `/Script/IKRig` |
| `RTG_Quinn_To_SoccerPlayer` | IKRetargeter | deps = `SKM_Quinn_Simple` + `IKR_Quinn` + `IKR_SoccerPlayer` + `UNREAL_RIG` + `/Script/IKRig`；**refs = `[]`** |

`RTG` 暴露了 `chain_map` / `chain_settings` / `root_settings` / `current_retarget_pose` / `retarget_poses` / `has_source_ik_rig` / `has_target_ik_rig`，但**具体 chain mapping / retarget pose / global settings 的取值无法通过 Python 读出 → UNKNOWN**（见第 12 节）。

### 6.2 链路（由依赖证明方向）

```
SOURCE ANIMATION         Epic Unarmed（SK_Mannequin）
        ↓
SOURCE SKELETON          SK_Mannequin
        ↓
SOURCE IK RIG            IKR_Quinn            （preview mesh = SKM_Quinn_Simple）
        ↓
IK RETARGETER            RTG_Quinn_To_SoccerPlayer
        ↓
TARGET IK RIG            IKR_SoccerPlayer     （preview mesh = UNREAL_RIG）
        ↓
TARGET SKELETON          UNREAL_RIG_Skeleton
        ↓
*_Soccer（21 条烘焙资产）
```

### 6.3 回答任务书两个问题

**`*_Soccer` 属于哪一类？ → A. batch-retarget 后烘焙资产。**
证据：(a) `*_Soccer` 是独立的 `AnimSequence` 资产，各自有 `skeleton = UNREAL_RIG_Skeleton`；(b) 名字与 Epic 源一一对应；(c) `RTG` 的 refs = 0（没有任何运行时资产引用它，说明它只在编辑器里用于生成结果）；(d) `ABP_FutsalPlayer_Soccer` / `BS_Futsal_Locomotion_Soccer` 引用的是烘焙产物，**不是** RTG。

**`RTG` 的 0 referencers 是否等于废弃？ → 不是。**
它的 0 refs 只说明**运行时无引用**；它是 `*_Soccer` 的**唯一可追溯生成来源**（编辑器期工具）。删除它 = 永久失去重生成能力。**不得据此判定可删。**

---

## 7. ControlRig / FootIK findings

| 项 | 实测 |
|---|---|
| 资产 | `/Game/Characters/Mannequins/Rigs/CR_Mannequin_FootIK`（`ControlRigBlueprint`） |
| `preview_skeletal_mesh` | **`SKM_Manny_Simple`** |
| 依赖 | `SKM_Manny_Simple`、**`SK_Mannequin`**、`/ControlRig/*`、`/Script/PBIK`、`/Script/RigVM*`、`/Script/UnrealEd` |
| Referencers | `ABP_Unarmed`（Epic）、**`ABP_FutsalPlayer`**、**`ABP_FutsalPlayer_Soccer`** |

逐项回答：

| # | 问题 | 结论 |
|---|---|---|
| 1 | 该 ControlRig 节点是否实际处于执行路径中 | **UNKNOWN** —— MCP/Python 无法读取 AnimGraph 的节点连线语义（只能拿节点类型/名称），**需要人工截图确认** |
| 2 | 是否有 Compile Warning | **UNKNOWN**（同上，需读 AnimGraph 编译结果面板） |
| 3 | 骨骼映射是否兼容 `UNREAL_RIG_Skeleton` | **判定为「不兼容隐患」**：该 CR 的 preview mesh 是 `SKM_Manny_Simple`、依赖 `SK_Mannequin`，而 `ABP_FutsalPlayer_Soccer` 的 target 是 `UNREAL_RIG_Skeleton`。CR 为 Mannequin 骨骼编写，未随 skeleton 替换而替换 → **存在骨骼不匹配风险**（是否为无害残留由第 1 项决定） |
| 4 | 是否只是从源 AnimBP 复制过来的残留 | **高度可疑但未证实**：两套 ABP 的其他差异都随 skeleton 替换了（Skeleton、全部动画资产），**唯独这个 CR 完全没换** → 与"逻辑克隆"的其余模式不一致 |

**未修改、未删除**。需要人工提供的截图见第 13 节。

---

## 8. ABP_SoccerPlayer / BP_SoccerPlayer status

| 项 | `ABP_SoccerPlayer` | `BP_SoccerPlayer` |
|---|---|---|
| Path | `/Game/FutsalMOT/Characters/FutsalPlayer/ABP_SoccerPlayer` | `/Game/FutsalMOT/Characters/FutsalPlayer/BP_SoccerPlayer` |
| Class | AnimBlueprint | Blueprint |
| Target Skeleton | `UNREAL_RIG_Skeleton` | — |
| Dependencies | **仅** `UNREAL_RIG_Skeleton` + `/Script/AnimGraph`（无任何动画资产、无 BlendSpace、无 StateMachine 引用） | `ABP_SoccerPlayer`、`UNREAL_RIG`、`MI_Player_TShirt_Test`、**`/DatasmithContent/Materials/Water/MI_Pool_01`**、`/Script/NavigationSystem` |
| AnimGraph | 仅 `AnimGraph` + `EventGraph`，**无 StateMachine**（Phase 1/2A 实测） | — |
| Variables | **0 个**（Phase 2A 实测） | `JerseyMaterial`（1 个） |
| Referencers | `BP_SoccerPlayer` 一个 | **`[]`（0）** |
| Level instances | 0 | **0**（L_FutsalCourt 中无该类 Actor） |

**判定：两者均为 `EXPERIMENTAL_STUB`（未完成实验分支）**，非 ACTIVE_ASSET。
⚠ 另注：`BP_SoccerPlayer` 携带一条**与角色完全无关的依赖** `/DatasmatchContent/Materials/Water/MI_Pool_01`（疑似遗留材质引用），仅记录，不处理。

**未删除。**

---

## 9. Epic dependency boundary（模板污染边界）

从 FutsalMOT 动画侧向外扫描，仍引用 Epic 的资产**共 20 个**：

| 类 | 资产 | Epic 依赖 | 分类 |
|---|---|---|---|
| AnimBlueprint | `ABP_FutsalPlayer` | `SK_Mannequin`、`CR_Mannequin_FootIK`、`MM_Idle/MM_Jump/MM_Land/MM_Fall_Loop`、`BP_ThirdPersonCharacter` | **必须替代** |
| AnimBlueprint | `ABP_FutsalPlayer_Soccer` | `CR_Mannequin_FootIK`、`BP_ThirdPersonCharacter` | **必须替代** |
| BlendSpace | `BS_Futsal_Locomotion` | 17 条 Epic Unarmed clip + `SK_Mannequin` | **必须替代** |
| AnimSequence ×7 | `SoccerSource/LS_*_InPlace` | `SK_Mannequin` | **必须替代**（若要保留这批源动画） |
| IKRigDefinition | `IKR_Quinn` | `SKM_Quinn_Simple` | **必须替代** |
| IKRetargeter | `RTG_Quinn_To_SoccerPlayer` | `SKM_Quinn_Simple` | **必须替代** |
| LevelSequence ×6 | `LS_Cam_01/02/03/04/Main/P01` | `BP_ThirdPersonCharacter`（possessable 绑定的 Actor 类） | **必须替代**（属 Level Actor 迁移问题，非动画层） |

**无需进入动画层**：`/Game/Input/**` —— 动画侧**零命中** ✅（Input 层已在 Phase 2A/2B 解耦完成）。

边界图：

```
FutsalMOT 动画侧                          Epic 模板侧
────────────────────                      ─────────────────────────────
ABP_FutsalPlayer ──────────────┐
  ├─ CR_Mannequin_FootIK ──────┤
  ├─ MM_Idle/Jump/Land/Fall ───┤
  └─ BP_ThirdPersonCharacter ──┤
BS_Futsal_Locomotion ──────────┤         /Game/Characters/Mannequins/**
  └─ 17 Epic Unarmed clip ─────┼──────▶    ├─ Meshes/SK_Mannequin
ABP_FutsalPlayer_Soccer ───────┤            ├─ Meshes/SKM_Quinn_Simple
  ├─ CR_Mannequin_FootIK ──────┤            ├─ Rigs/CR_Mannequin_FootIK
  └─ BP_ThirdPersonCharacter ──┤            └─ Anims/Unarmed/**
SoccerSource/LS_*_InPlace ×7 ──┤
IKR_Quinn ────────────────────┤         /Game/ThirdPerson/**
RTG_Quinn_To_SoccerPlayer ────┤──────▶    └─ Blueprints/BP_ThirdPersonCharacter
LS_Cam_* ×6 ──────────────────┘
```

---

## 10. Canonical Source options（只评估，不创建）

### Strategy A — LOW RISK（推荐先做）

Futsal 自有：Character BP、AnimBP、BlendSpace、Animation assets；**暂时继续使用 `SK_Mannequin` Skeleton**。

| 优点 | 缺点 | 依赖影响 |
|---|---|---|
| 不需要重建 Skeleton，**不动 114 个 `SK_Mannequin` 引用者** | 仍依赖 Epic `SK_Mannequin` 资产 | 消除 `BP_ThirdPersonCharacter` 与 `CR_Mannequin_FootIK` 依赖；`SK_Mannequin` 依赖保留 |

### Strategy B — FULL OWNERSHIP（后做）

最后建立 `SK_FutsalSource` 并迁移全部 source animation。

| 优点 | 风险 | 引用影响 |
|---|---|---|
| 完全摆脱 Epic `SK_Mannequin` | **Skeleton 换归属需重挂全部 source 动画**，波及 114 个引用者 | 高：`SK_Mannequin` 是 114 个资产的共享骨架，处理不当会大面积损坏 |

### 推荐执行顺序

```
1) Strategy A：解耦 AnimBP→CharacterBP（消除 Cast）       ← 低风险、可回滚
2) Strategy A：Futsal 自有 AnimBP/BS/源动画库落地（仍用 SK_Mannequin）
3) 行为对比（同一轨迹，逐帧）
4) Strategy B：建立 SK_FutsalSource 并迁移 source animation
5) 真人目标侧：重跑 RTG → 重新烘焙 *_Soccer
```

**本阶段不创建任何上述资产。**

---

## 11. Animation communication redesign（只设计）

### 11.1 当前 ABP 的 17 个变量分类

| 变量 | 分类 | 说明 |
|---|---|---|
| `Character`（类型 = `BP ThirdPersonCharacter 对象引用`） | **必须从 Character 提供 → 但应改为泛型** | 这是唯一造成硬依赖的项；只需 `GetOwningActor() → Cast To Character`（`ACharacter`，引擎基类）即可 |
| `MovementComponent` | **可 AnimBP 自算** | `Character.CharacterMovement` 或 `GetOwningActor() → GetComponentByClass(CharacterMovementComponent)` |
| `Velocity`, `GroundSpeed`, `Direction`, `ShouldMove`, `IsFalling` | **可 AnimBP 自算** | 全部来自 `CharacterMovement` / `ACharacter`，无需项目类 |
| `Previous Location` | AnimBP 内部状态 | 自算 |
| `MotionSpeedMps` | **可能冗余** | ABP 已有同名变量；是否与 CharacterBP 的 `MotionSpeedMps` 重复 → UNKNOWN（见第 3.2 节） |
| `Auto Motion Speed Mps`, `Speed Initialized`, `Use Auto Motion Speed`, `Effective Motion Speed Mps`, `Auto Motion Velocity`, `Effective Velocity`, `Auto Facing Yaw Deg`, `CurrentAnimationClass` | **AnimBP 自算（已在 ABP 内）** | 属"自动运动速度 / 朝向"逻辑，已在 AnimBP 的 92 节点 EventGraph 中实现 |

⇒ **真正跨边界的只有 `Character` 与 `MovementComponent`，且两者都可用引擎基类 + 组件接口获得，不需要项目专属 BP。**

### 11.2 候选机制

| 方案 | 评价 |
|---|---|
| **A. `TryGetPawnOwner` / `GetOwningActor` → `Cast To Character` → `CharacterMovement` → AnimBP 自算** | **推荐**。改动最小（只把 Cast 目标从 `BP_ThirdPersonCharacter` 换成 `Character`），零接口资产，零运行时开销，且立刻切断循环依赖 |
| B. Blueprint Interface `BPI_FutsalAnimationSource` | 适合"未来要跨多种 Pawn"的场景；但引入新接口资产 + 需在 CharacterBP 实现 + AnimBP 每次 `BlueprintUpdateAnimation` 走接口调用（有开销） |
| C. AnimInstance 接口 / Linked Anim Layer | 适合"同一 Character 多套动画层"；对当前"单一 locomotion 逻辑 + 多 skeleton"的问题**不是最优**（真正的问题是 Skeleton，不是 Layer） |
| D. 其它（Anim Node 直读 Owning Component / `Property Access`） | `Property Access` 仍会引用具体类 → 不能解决依赖 |

**本阶段只设计，不实施。**

---

## 12. UNKNOWN items

| # | UNKNOWN | 原因 | 影响 |
|---|---|---|---|
| U1 | 两个 StateMachine 的 **Transition 条件表达式** | MCP 只能读节点类型/名称，不能读表达式语义 | 无法评估"解耦 Cast 后行为是否等价" |
| U2 | ABP **变量类型与默认值** | `UBlueprint::NewVariables` 在 5.8 移入未暴露的 `BlueprintEditorOnlyData` | 无法给出变量类型表 |
| U3 | ABP 通过 `Character` 变量**读取了哪些成员**（尤其 `MotionSpeedMps` / `AnimationClassId`） | 需逐节点核对 92 节点图；`find_nodes("AnimationClassId")` = `[]` | 决定解耦方案是否完整 |
| U4 | `CR_Mannequin_FootIK` 是否在实际执行路径 / 是否有 Warning | AnimGraph 节点连线语义不可读 | 决定是否需替换/移除 |
| U5 | AnimGraph 中 **BlendSpace / Sequence / ControlRig / CachedPose / Layer 节点的确切组成** | 同上 | 影响 `ABP_FutsalSource` 的重建工作量评估 |
| U6 | `RTG_Quinn_To_SoccerPlayer` 的 **chain map / retarget pose / global settings / root settings** | 属性未暴露 | 无法评估重定向质量与可否自动化重跑 |
| U7 | `SoccerSource/LS_*_InPlace` 的**来源**（哪次导入/mocap） | 无 provenance 元数据可读 | 无法确认是否可丢弃 |
| U8 | `*_Soccer` 是否由 `RTG_Quinn_To_SoccerPlayer` 实际生成 | RTG refs=0 只能证明"运行时未用"，生成动作本身不可追溯 | 影响 Strategy B 的可行性 |

> 以上均**未用猜测填充**。

---

## 13. Manual screenshots required

| # | 截图 | 目的 |
|---|---|---|
| S1 | `ABP_FutsalPlayer` **AnimGraph 全展开** | 确认 SM0/SM1 的 State/Transition 组成与节点类型（补 U5） |
| S2 | S1 中 `Locomotion` 的 2 条 Transition 条件 | 补 U1 |
| S3 | S1 中 `Main States` 的 8 条 Transition 条件 | 补 U1 |
| S4 | `ABP_FutsalPlayer` **EventGraph 全展开** | 确认 `Character` 变量下游读取（补 U3），特别是是否读 `AnimationClassId` / `MotionSpeedMps` |
| S5 | `ABP_FutsalPlayer_Soccer` **AnimGraph 全展开** | 与 S1 逐节点比对（验证"逻辑克隆"结论） |
| S6 | `ABP_FutsalPlayer_Soccer` AnimGraph 中 **ControlRig 节点区域** | 确认 `CR_Mannequin_FootIK` 是否在执行路径、是否报错（补 U4） |
| S7 | `ABP_FutsalPlayer` 变量面板（含类型/默认值） | 补 U2 |
| S8 | `RTG_Quinn_To_SoccerPlayer` 打开后的 Chain Mapping 面板 | 补 U6 |
| S9 | `SoccerSource/LS_Backpedal_InPlace` 等 7 条的资产详情 | 补 U7 |

---

## 14. Proposed Phase 3B

**范围最小、可回滚。明确不做"一次性合并两个 AnimBP"。**

### Phase 3B — Inputs
- `ABP_FutsalPlayer`（只读）
- 本报告第 3 节的 Cast 链路证据
- `BP_ThirdPersonCharacter`（只读，用于确认其提供的成员）

### Phase 3B — Operations
1. **新建**（不复制）`/Game/FutsalMOT/Animation/Source/ABP_FutsalSource`，Target Skeleton = **`SK_Mannequin`**（Strategy A）
2. 把 `ABP_FutsalPlayer` 的 EventGraph/AnimGraph 逻辑**迁移**到新 ABP —— 与原 ABP 等效（同一 skeleton）
3. **唯一行为性改动**：把 `Cast To BP_ThirdPersonCharacter` 换成 **`Cast To Character`**（`/Script/Engine.Character`），从而**切断 `ABP → BP_ThirdPersonCharacter`**
4. 在新 ABP 中把 `Character` 变量类型改为 `Character`（引擎基类）
5. Compile + Save；依赖审计（非 Script 依赖不得含 `/Game/ThirdPerson/**`）
6. **不做**任何 Level Actor / Skeleton / 真人侧改动

### Phase 3B — Do Not Touch
`L_FutsalCourt`、`Player_L0~R4`、任何 Level Sequence、`BP_ThirdPersonCharacter(_Soccer)`、`BP_SoccerPlayer`、`ABP_FutsalPlayer(_Soccer)`、`ABP_SoccerPlayer`、任何 Skeleton/SkeletalMesh、`CR_Mannequin_FootIK`、IKR/RTG、`*_Soccer`、SoccerSource、Input 层、Epic 模板资产。

### Phase 3B — Validation
1. 新 ABP 编译 0 Error / 0 Warning
2. 依赖表：无 `/Game/ThirdPerson/**`、无 `BP_ThirdPersonCharacter`
3. **行为对比**：把测试关卡中的 `Player_FutsalBase_Test` 临时指向新 ABP，用同一条已知轨迹（如 Phase 1.5 的 PIE 方式）核对 `MOVE_WALKING` / 速度 / 落地行为与 `ABP_FutsalPlayer` 一致
4. 人工 PIE 目视对比（`ABP_FutsalPlayer` vs `ABP_FutsalSource`）

### Phase 3B — Rollback
删除新 ABP 即可；现有 `ABP_FutsalPlayer` / 关卡绑定**完全不动**（新 ABP 在验证前不被任何资产引用）。

> 顺序原则：**先建独立 Source ABP → 先解 `ABP → BP_ThirdPersonCharacter` → 再做行为对比 → 最后才考虑真人目标 AnimBP。**

---

## 15. DO NOT TOUCH list

在引用关系完全确认前**不得删除、移动、重命名或修改**：

1. `ABP_FutsalPlayer` —— 右队 5 个 Actor 的实际 AnimBP（类默认）
2. `ABP_FutsalPlayer_Soccer` —— 左队 5 个 Actor 的实际 AnimBP（实例覆盖），且被 5 个 L_FutsalCourt external actor 包引用
3. `BS_Futsal_Locomotion` / `BS_Futsal_Locomotion_Soccer`
4. `/Game/Characters/Mannequins/Meshes/SK_Mannequin` —— **114 个引用者**
5. `/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple` —— 右队 + `IKR_Quinn` + `RTG`
6. `/Game/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG` —— 27 个引用者（含 5 个 L_FutsalCourt external actor）
7. `/Game/FutsalMOT/Characters/FutsalPlayer/Skeleton/UNREAL_RIG_Skeleton` —— 24 个引用者
8. `/Game/Characters/Mannequins/Rigs/CR_Mannequin_FootIK` —— 被两个 Futsal ABP 引用（含潜在的骨骼错配）
9. `IKR_Quinn` / `IKR_SoccerPlayer` / **`RTG_Quinn_To_SoccerPlayer`** —— RTG 虽 0 refs，但它是 `*_Soccer` 的**唯一可追溯生成来源**
10. `SoccerSource/LS_*_InPlace` ×7 —— 0 refs 但属**未接线的 Futsal 自有 soccer 源动画**，不得因 0 refs 判定可删
11. `ABP_SoccerPlayer` / `BP_SoccerPlayer` —— 含手工成果的实验分支
12. 全部 6 条 `LS_Cam_*` Level Sequence 及其 possessable 绑定
13. Epic 模板资产（`/Game/Characters/Mannequins/**`、`/Game/ThirdPerson/**`）

---

## 附：本阶段自查

- 未修改任何 Blueprint / AnimBP / AnimSequence / BlendSpace / Skeleton / SkeletalMesh / ControlRig / IK Rig / IK Retargeter ✅
- 未修改 `L_FutsalCourt` / `Player_L0~R4` / Level Sequence / `BP_NoPawnGameMode` / Input 层 ✅
- 未 Rename / Move / Duplicate / Delete 任何资产 ✅
- 未 Fix Up Redirectors / 未 Consolidate / 未自动保存 ✅
- 仅执行 Asset Registry 查询、Blueprint 只读内省、Unreal Python 只读查询、Git 只读查询，并生成本报告 ✅

**Phase 3A 完成，停止。未执行 Phase 3B，未创建任何动画资产，未进入 Skeleton migration。**
