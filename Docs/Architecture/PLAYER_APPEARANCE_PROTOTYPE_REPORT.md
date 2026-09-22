# PLAYER_APPEARANCE_PROTOTYPE_REPORT — Phase 5B.2 Quinn Appearance Prototype

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `c5d1b42f833f7969c77aed15022b6e6f396fc656`（tag `phase5-project-cleanup`）
- 性质：在**隔离 Prototype** 中验证运行期外观参数化。未修改 `/Game/Characters/Mannequins/**`、`SKM_Quinn_Simple`、`SK_Mannequin`、`M_Mannequin`、`MI_Quinn_01/02`、`T_Quinn_*`、`BP_FutsalCharacterBase`、`ABP_FutsalSource`、`L_FutsalCourt`、`LS_Cam_*`、生产 Input、任何 Skeleton/IK/Retarget/ControlRig。未提交、未 stage。
- **未修改生产地图 `L_FutsalCourt`**。

---

## 1. 已创建的资产

| 资产 | Path | 说明 |
|---|---|---|
| `M_FutsalSkin_Master` | `/Game/FutsalMOT/Appearance/Materials/Skin/` | BaseColor = Lerp(BaseTexture.RGB, BaseTexture.RGB×SkinTint, SkinTintStrength)；NormalTexture→Normal；MRATexture R/G/B→Metallic/Roughness/AO；参数 `BaseTexture/NormalTexture/MRATexture/SkinTint/SkinTintStrength` |
| `MI_FutsalSkin_Quinn` | 同上 | parent `M_FutsalSkin_Master`；贴图 = `T_Quinn_01_D/N/MRA` |
| `M_FutsalKit_Master` | `/Game/FutsalMOT/Appearance/Materials/Kits/` | BaseColor = Lerp(BaseTexture.RGB, Desaturation(BaseTexture.RGB,1)×KitColor, KitTintStrength)；参数 `BaseTexture/NormalTexture/MRATexture/KitColor/KitTintStrength` |
| `MI_FutsalKit_Quinn` | 同上 | parent `M_FutsalKit_Master`；贴图 = `T_Quinn_02_D/N/MRA` |
| `T_FutsalNumberAtlas` | `/Game/FutsalMOT/Appearance/Textures/Numbers/` | 1000×128 单行 **10 cells**（0–9 等宽，白字透明底），**AtlasColumns=10, AtlasRows=1**，digit d → cell index d |
| `M_FutsalNumber_Master` | `/Game/FutsalMOT/Appearance/Materials/Numbers/` | **Masked**；参数 `NumberAtlas/Digit(0–9)/NumberColor`；UV = ((TexCoord.U+Digit)×0.1, TexCoord.V)；Emissive=atlas.RGB×NumberColor；OpacityMask=atlas.A |
| `BP_FutsalAppearancePrototype` | `/Game/FutsalMOT/Appearance/Prototype/` | parent `BP_FutsalCharacterBase_C`；无新增 Tick 逻辑 |
| `L_FutsalAppearancePrototype_Test` | `/Game/FutsalMOT/Test/Appearance/` | 只放置 1 个 `BP_FutsalAppearancePrototype` |

### Prototype 组件（SCS，BP 内）

| 组件 | 类型 | Mesh | 附着 | 说明 |
|---|---|---|---|---|
| `FrontTens` / `FrontOnes` / `BackTens` / `BackOnes` | StaticMeshComponent | `/Engine/BasicShapes/Plane` | `CharacterMesh0`（**组件级**，非骨骼 Socket） | cast_shadow=false；材质 = `M_FutsalNumber_Master` |

### Prototype 变量（BP）

`AppearanceId(Name)`, `SkinToneId(int)`, `KitId(Name)`, `JerseyNumber(int)`, `SkinTint/KitColor/NumberColor(LinearColor)`, `SkinMID/KitMID/FrontTensMID/FrontOnesMID/BackTensMID/BackOnesMID(MaterialInstanceDynamic)`。

---

## 2. 已证明（自动运行期验证，PIE）

运行期在 Prototype actor 上创建 MID 并切参数，**参数实际改变并回读一致**：

| Case | SkinTone | SkinTint（回读） | Kit | KitColor（回读） | Number | Tens | Ones | Front/Back Tens | Front/Back Ones |
|---|---|---|---|---|---|---|---|---|---|
| A | LIGHT | [1.0, 0.8, 0.65] | RED | [0.85, 0.06, 0.06] | 7 | 0 | 7 | 0.0 / 0.0（tens） | 7.0 / 7.0 |
| B | MEDIUM | [0.72, 0.5, 0.38] | BLUE | [0.05, 0.16, 0.75] | 10 | 1 | 0 | 1.0 / 1.0 | 0.0 / 0.0 |
| C | DARK | [0.38, 0.24, 0.17] | RED | [0.85, 0.06, 0.06] | 23 | 2 | 3 | 2.0 / 2.0 | 3.0 / 3.0 |

- `SKIN_TINT_PROTOTYPE`：MID 的 `SkinTint` 参数三档实测改变 ✅
- `WHOLE_KIT_COLOR_PROTOTYPE`：同一 `KitMID` 改 `KitColor`（RED/BLUE）实测改变，**未新建材质资产** ✅（仅整体单色，非分区）
- `JERSEY_NUMBER_ATLAS_PROTOTYPE`：`Digit` = Tens/Ones 计算正确（7→0/7、10→1/0、23→2/3），四个号码面片参数一致 ✅；**无每号码一个材质/贴图**（仅运行期 MID）
- `ANIMATION_REGRESSION`：材料切换后 AnimInstance 仍为 `ABP_FutsalSource_C`，Mesh/Skeleton 未重置 ✅（Idle 状态下评估；未在本次驱动 W/Space）
- `METADATA_READBACK`：`SkinToneId` / `KitId` / `JerseyNumber` / `AppearanceId` 可由 Python/MCP 从同一 actor 读取；视觉参数与 metadata 同源 ✅

> MRA 通道映射假设：`MRATexture.R→Metallic / G→Roughness / B→AmbientOcclusion`（未读 `M_Mannequin` 图内连线，属假设）。

---

## 3. 尚未实现（不要描述为完整系统）

| 项 | 状态 | 说明 |
|---|---|---|
| `APPLY_APPEARANCE_BP_FUNCTION` | **NOT_IMPLEMENTED** | BP 已建 `ApplyAppearance` 空函数图，但**未生成节点逻辑**；本次切参数由运行期（Python MID）驱动，等价操作未固化为 BP 函数 |
| `MULTI_REGION_KIT_COLOR` | NOT_IMPLEMENTED | Quinn 服装槽无 shirt/shorts/socks/shoes 分区 mask |
| `PRIMARY_SECONDARY_MASK` | NOT_IMPLEMENTED | 仅整体 `KitColor` |
| `SHORTS_COLOR_INDEPENDENT` | NOT_IMPLEMENTED | — |
| `SOCK_COLOR_INDEPENDENT` | NOT_IMPLEMENTED | — |
| `PRODUCTION_APPEARANCE_CONFIG` | NOT_IMPLEMENTED | 未接入 `BP_FutsalCharacterBase` / 数据集 metadata 管线 |
| `NEW_PLAYER_MODEL_PIPELINE` | NOT_STARTED | — |
| 号码面片骨骼附着 | PARTIAL | `attach_socket_name` 属性不可通过当前 Python/MCP 设置；面片附着到 **CharacterMesh0 组件**并按胸部高度偏移，随角色整体运动，**不随躯干骨骼弯曲** |
| 数字视觉/镜像/Z-fighting | 人工验收 | 面片相对变换为临时值，需人工调整 |

---

## 4. Git 变更（未 stage）

新增/修改限于：`Content/FutsalMOT/Appearance/**`、`Content/FutsalMOT/Test/Appearance/**`、本报告；另有既有 `M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset`（`EXTERNAL_UNRESOLVED_CHANGE`，未触碰）。

---

## 5. 输出

```
PHASE5B2_APPEARANCE_PROTOTYPE = IMPLEMENTED
SKIN_SWITCHING = PASS
WHOLE_KIT_COLOR_SWITCHING = PASS
JERSEY_NUMBER_SWITCHING = PASS
ANIMATION_REGRESSION = PASS
METADATA_READBACK = PASS
MANUAL_VISUAL_VALIDATION = REQUIRED
MULTI_REGION_KIT_SYSTEM = NOT_IMPLEMENTED
PRODUCTION_INTEGRATION = NOT_STARTED
```

### 人工视觉验收清单（STEP 16，未自动判定）

1. LIGHT/MEDIUM/DARK 肤色肉眼可区分
2. 皮肤纹理细节仍存在
3. RED/BLUE 球衣肉眼可区分
4. 球衣不是纯色塑料块
5. 号码 7 正确
6. 号码 10 正确
7. 号码 23 正确
8. Front number 未镜像
9. Back number 未镜像
10. 号码随 Idle/Move/Jump 正常跟随
11. 无严重 Z-fighting
12. 无明显号码穿入身体
13. 无 T-pose

在人工确认前不 commit。

---

---

# Phase 5B.2a — Appearance Prototype Visual & Logic Closure

- 执行时间：2026-09-19
- 基线：`c5d1b42f833f7969c77aed15022b6e6f396fc656`
- 目标：把 Prototype 收敛为「自己 ApplyAppearance，不依赖 Python 切外观」。

## STEP 1 — 复核（PASS）

- `BP_FutsalAppearancePrototype` Parent = `BP_FutsalCharacterBase_C`。
- 变量齐备：`AppearanceId / SkinToneId / KitId / JerseyNumber / SkinTint / KitColor / NumberColor / SkinMID / KitMID / FrontTensMID / FrontOnesMID / BackTensMID / BackOnesMID`。
- 图：`ApplyAppearance`（空）、`EventGraph`、`UserConstructionScript`。
- 实例（Test Map）CharacterMesh0 = `SKM_Quinn_Simple` + `ABP_FutsalSource_C`。

## STEP 2/4 — ApplyAppearance BP 逻辑（**FAIL — 未实现**）

- 已建 `ApplyAppearance` 函数图，但**未能可靠自动生成节点逻辑**：
  - 本工程节点 `type_id` 为本地化中文（如 `渲染|材质|CreateDynamicMaterialInstance`、`渲染|SetVisibility`）；
  - MID 的 `Set Vector/Scalar Parameter Value` 节点 `type_id` 与 **MaterialParameterCollection** 变体同名（`渲染|材质|SetVectorParameterValue`），`get_node_type_pins` 解析到集合变体，需 `declaring_class` 消歧；在无交互验证的情况下不可靠。
  - 按任务「若工具无法可靠构造则停止继续自动修补」的精神，**停止**，未强行拼接。
- 结论：`APPLY_APPEARANCE_BP_FUNCTION = FAIL`（Prototype 仍不能自行 ApplyAppearance；上个阶段的切换由运行期 Python 驱动）。
- `BeginPlay → ApplyAppearance` **未添加**（依赖失败的函数图）。

## STEP 3 — MID 生命周期（FAIL — 未在 BP 固化）

- 因函数图未实现，BP 级「只在无效时创建 MID / 复用」未固化：`MID_REUSE = FAIL`。
- 上个阶段运行期验证路径为每次 `create_dynamic_material_instance`（未复用），仅用于参数证明。

## STEP 5 — 号码附着（COMPONENT_LEVEL_PROTOTYPE_ONLY）

- 4 个号码面片附着到 **`CharacterMesh0` 组件**；`attach_socket_name` 无法经当前 Python/MCP 设置；`get_attach_parent()` 回读为 None（附着关系未能证实）。
- 未修改 `SK_Mannequin`。`NUMBER_ATTACHMENT = COMPONENT_LEVEL_PROTOTYPE_ONLY`。

## STEP 6 — 号码面片 Transform（已记录，临时值）

| 组件 | Relative Location | Relative Rotation (pitch,yaw,roll) | Relative Scale |
|---|---|---|---|
| FrontTens | (17, -6, 130) | (90, 90, 0) | (0.18, 0.24, 1.0) |
| FrontOnes | (17, 6, 130) | (90, 90, 0) | (0.18, 0.24, 1.0) |
| BackTens | (-17, 6, 130) | (-90, 90, 0) | (0.18, 0.24, 1.0) |
| BackOnes | (-17, -6, 130) | (-90, 90, 0) | (0.18, 0.24, 1.0) |

> 均为临时值，观感需人工验收。

## STEP 7 — MRA 安全处理（PASS）

- `M_Mannequin` 图内连线不可读，无法可靠确认 R/G/B 通道 ⇒ **不继续假设**。
- 已在 Prototype 两个 master（`M_FutsalSkin_Master` / `M_FutsalKit_Master`）中断开 MRA→M/R/AO 掩膜，改用常量：
  - `Metallic = 0.0`、`Roughness = 0.5`、`AmbientOcclusion = 1.0`；BaseColor + Normal 保持。
- `PROTOTYPE_MRA_MAPPING = DEFERRED`。未修改 Epic 材质。

## STEP 8/9 — 无 Python 自动应用测试（BLOCKED）

- 因 `ApplyAppearance` 未实现，无法在不使用 Python `set_*_parameter_value` 的前提下切换外观 ⇒ **未执行**。
- 动画绑定回归沿用上阶段结论：切换材质后 `AnimInstance = ABP_FutsalSource_C`，Mesh/Skeleton/AnimClass 未重置 ⇒ `ANIMATION_REGRESSION = PASS`（但「Prototype 自驱切换」未验证）。

## STEP 10 — Manual Visual Gate

仍 `REQUIRED`（见 §5 清单）；人工确认前不 commit。

## STEP 11 — 最终状态

```
APPLY_APPEARANCE_BP_FUNCTION = FAIL
MID_REUSE = FAIL
SINGLE_DIGIT_VISIBILITY = FAIL
NUMBER_ATTACHMENT = COMPONENT_LEVEL_PROTOTYPE_ONLY
ANIMATION_REGRESSION = PASS
PROTOTYPE_MRA_MAPPING = DEFERRED
MANUAL_VISUAL_VALIDATION = REQUIRED
```

> 诚实说明：本阶段**未**把 Phase 5B.2 收敛为 Prototype 自驱；切换仍依赖运行期 Python。未继续自动修补 BP 节点。

---

# Phase 5B.2b — Blueprint ApplyAppearance Graph Recovery

- 执行时间：2026-09-19
- 基线：`c5d1b42f833f7969c77aed15022b6e6f396fc656`

## 关键工具突破

发现 `unreal.ToolsetRegistry.execute_tool(toolset_name, tool_name, json_input)` —— 可在**单个真实 UE Python 脚本内**同步调用 MCP Toolset 工具（BlueprintTools 的 `create_node`/`connect_pins`/`find_nodes` 等），返回值取 `.value`（JSON 字符串）。这允许脚本化构图，无需人工逐节点点击。

## STEP 1 — 节点消歧（部分完成）

| 目标 | 结论 |
|---|---|
| `create_node(..., declaring_class=...)` | 可消歧：传入 `declaring_class=/Script/Engine.MaterialInstanceDynamic` 时，`type_id="渲染|材质|SetVectorParameterValue"` 创建为 **`K2Node_CallFunction`**（非 MaterialParameterCollection） |
| 该节点实际引脚 | `self` = **材质动态实例 对象引用（MaterialInstanceDynamic）**；`ParameterName` = 命名；`Value` = 线性颜色（LinearColor）✅ |
| `write_graph_dsl` | **不可用**：它把 `渲染|材质|SetVectorParameterValue` 解析为 **MaterialParameterCollection** 变体（pins: Collection/ParameterName/ParameterValue），且要求顶层 `event`/`fn` 包装；无法消歧 |
| 变量节点 | `变量|默认|获取X` / `变量|默认|设置X` 可枚举（SkinMID/KitMID/四 NumberMID/SkinTint/KitColor/NumberColor/JerseyNumber） |
| `SetScalarParameterValue` | 同样需 `declaring_class=MaterialInstanceDynamic`（同名多变体） |
| `CreateDynamicMaterialInstance` | `渲染|材质|CreateDynamicMaterialInstance`（需 `declaring_class` 消歧至 MeshComponent 变体） |
| 组件 Getter（CharacterMesh0 / FrontTens…） | **未找到可创建节点类型**（`find_node_types` 为空；`create_node("变量|默认|获取Mesh")` 报 does not exist） |
| Event `BeginPlay` | 未定位到可创建 event type id |
| `Divide/Modulo/GreaterEqual (Integer)` | 未定位（`find_node_types` 未返回整型变体） |

## 结果

- 单节点验证成功：`MID_SET_VECTOR_NODE = VERIFIED`（已创建→检查→删除）。
- 但组件 Getter / BeginPlay / 整型算术等 type id 未定位，**未能构造完整的 `InitializeAppearanceMaterials` / `ApplyAppearance` 图**。
- 已清理测试节点，`BP_FutsalAppearancePrototype` 重新编译为 `BS_UP_TO_DATE` 并已保存（未残留半成品节点）。
- 未修改父类、Epic 资产、生产地图。

```
PHASE5B2B_BP_GRAPH_RECOVERY = PARTIAL
APPLY_APPEARANCE_BP_FUNCTION = FAIL
INITIALIZE_APPEARANCE_MATERIALS = FAIL
MID_SET_VECTOR_NODE = VERIFIED
MID_SET_SCALAR_NODE = NOT_VERIFIED（未单独验证）
MID_REUSE = FAIL
SINGLE_DIGIT_VISIBILITY = FAIL
NO_PYTHON_MATERIAL_PARAMETER_WRITE = FAIL
NUMBER_ATTACHMENT = COMPONENT_LEVEL_PROTOTYPE_ONLY
ANIMATION_REGRESSION = PASS
MANUAL_VISUAL_VALIDATION = REQUIRED
```

---

# Phase 5B.2c — Blueprint Node Discovery & Self-Driven Appearance Closure

- 执行时间：2026-09-19
- 基线：`c5d1b42f833f7969c77aed15022b6e6f396fc656`
- 方法：`unreal.ToolsetRegistry.execute_tool` 驱动 `find_node_types` / `create_node(declaring_class)` / `get_node_infos` / `delete_node`，逐候选 创建→检查引脚→删除。

## STEP 1 — Component Getter Discovery → **FAIL**

| 候选 | 结果 |
|---|---|
| `变量|默认|获取CharacterMesh0` | **does not exist**（无法创建） |
| `变量|默认|获取FrontTens` | 未成功（`find_node_types("Front"/"Tens")` 为空） |
| `变量|默认|获取SkinMID`（对照） | 变量 getter 存在（非组件） |

- **组件 Getter（inherited `CharacterMesh0` 与自有 `FrontTens/FrontOnes/BackTens/BackOnes`）无法通过可创建的节点 type id 获得** ⇒ `CHARACTER_MESH_GETTER = FAIL`、`NUMBER_COMPONENT_GETTERS = FAIL`。
- 未找到 `create_variable_get`/`get_variable_node` 等专用能力。

## STEP 2 — Engine Function Discovery → 未完成

- `CreateDynamicMaterialInstance` / `GetMaterialIndex` 使用猜测 declaring_class（`/Script/Engine.PrimitiveComponent`、`/Script/Engine.MeshComponent`）时 **does not exist**（declaring_class 必须精确匹配实际 UFunction 声明类，未定位） ⇒ `CREATE_DMI_NODE = NOT_VERIFIED`、`GET_MATERIAL_INDEX_NODE = NOT_VERIFIED`。
- `SetVisibility`（declaring `/Script/Engine.SceneComponent`）、MID `SetScalarParameterValue`（declaring `/Script/Engine.MaterialInstanceDynamic`）的候选创建结果因脚本在组件 Getter/CreateDMI 失败处提前中止而**未取回** ⇒ `SET_VISIBILITY_NODE = NOT_VERIFIED`、`MID_SET_SCALAR_NODE = NOT_VERIFIED`。
- 已确认（5B.2b）：`MID_SET_VECTOR_NODE = VERIFIED`。

## STEP 3 — Integer Math → **FAIL**

- `KismetMathLibrary` 的 `Divide_IntInt` / `Percent_IntInt` / `Less_IntInt` 及 `find_node_types("IntInt"/"Divide"/"Modulo"/"GreaterEqual")` **均未返回整型变体** ⇒ `INT_DIVIDE_NODE = FAIL`、`INT_MODULO_NODE = FAIL`、`INT_COMPARE_NODE = FAIL`。
- `JERSEY_NUMBER_CLAMP = DEFERRED`（未实现）。

## STEP 4 — BeginPlay → **FAIL**

- `find_node_types("BeginPlay"/"ReceiveBeginPlay"/"事件")` 未返回可创建 event type id ⇒ `BEGINPLAY_EVENT_NODE = FAIL`。
- 未改用 Construction Script（未偷换语义）。

## 结果：BLUEPRINT_AUTOMATION_LIMIT_REACHED = TRUE

按 STEP 16：**Component Getter 与关键引擎函数（CreateDMI/GetMaterialIndex/整型算术/BeginPlay）无法可靠构造**，停止第 4 轮猜节点。

### 清理

- 删除本阶段所有临时/半成品节点；`InitializeAppearanceMaterials`/`ApplyAppearance` 未生成逻辑。
- `ApplyAppearance` 仅保留 `K2Node_FunctionEntry_0`。
- 清理了 child `EventGraph` 中 3 个残留 `K2Node_Event_*`（工厂生成的空事件节点；父类事件不受影响）。
- `BP_FutsalAppearancePrototype` 重新编译 = **`BS_UP_TO_DATE`**，0 Error / 0 Warning，已保存。

```
PHASE5B2C_SELF_DRIVEN_APPEARANCE = PARTIAL
BLUEPRINT_AUTOMATION_LIMIT_REACHED = TRUE
COMPONENT_GETTERS = FAIL
BEGINPLAY_EVENT = FAIL
INTEGER_MATH = FAIL
MID_SET_VECTOR_NODE = VERIFIED
MID_SET_SCALAR_NODE = NOT_VERIFIED
CREATE_DMI_NODE = NOT_VERIFIED
GET_MATERIAL_INDEX_NODE = NOT_VERIFIED
SET_VISIBILITY_NODE = NOT_VERIFIED
INITIALIZE_APPEARANCE_MATERIALS = FAIL
APPLY_APPEARANCE_BP_FUNCTION = FAIL
GRAPH_TYPE_SAFETY = N/A（未构图）
NO_PYTHON_MATERIAL_PARAMETER_WRITE = FAIL
MID_REUSE = FAIL
SINGLE_DIGIT_VISIBILITY = FAIL
ANIMATION_REGRESSION = PASS
JERSEY_NUMBER_CLAMP = DEFERRED
NUMBER_ATTACHMENT = COMPONENT_LEVEL_PROTOTYPE_ONLY
PROTOTYPE_MRA_MAPPING = DEFERRED
```

**结论**：本 Prototype 无法在当前纯 Blueprint 自动化工具下自驱。下一方案应改为**极薄的 native Appearance helper**（如 `UFutsalAppearanceComponent`/`UFutsalAppearanceLibrary`）替代无限搜索本地化 Blueprint node type。

## 附：已知偏差

- `ApplyAppearance` BP 函数图未生成（见 Phase 5B.2a §STEP 2）。
- 号码面片附着于网格组件而非骨骼 Socket（`attach_socket_name` 不可设置）。
- MRA 通道映射为假设。
- 号码面片相对变换/朝向为临时值。
- `JerseyNumber < 10` 时 Tens 面片隐藏逻辑尚未固化为 BP 函数（本次未隐藏，仅参数为 0）。

---

---

# Phase 5B.2e — Appearance Manual Visual Acceptance Scene

- 执行时间：2026-09-21
- 基线：branch `refactor/character-architecture`
- 性质：**手动视觉验收场景搭建**。不自动构造 Blueprint 节点；未修改 `BP_FutsalCharacterBase` / `ABP_FutsalSource` / `SKM_Quinn_Simple` / `SK_Mannequin` / `/Game/Characters/Mannequins/**` / `L_FutsalCourt` / `LS_Cam_*`。未 stage / commit / tag / push；未触碰 `UNREAL_RIG.uasset`。

## STEP 1 — 静态 Blueprint 校验（只读，PASS）

- 编译：`BlueprintEditorLibrary.compile_blueprint` → `status = BS_UP_TO_DATE`，0 Error。
- 函数：`InitializeAppearanceMaterials`（已实现）、`ApplyAppearance`（已实现）。
- EventGraph 连线（`find_nodes` + `get_node_infos` 只读）：

```
Event BeginPlay → Parent: BeginPlay → InitializeAppearanceMaterials → ApplyAppearance
```

- Parent = `BP_FutsalCharacterBase_C`；图：`UserConstructionScript` / `ApplyAppearance` / `InitializeAppearanceMaterials` / `EventGraph`。

## STEP 2 — Tint Strength

- `MI_FutsalSkin_Quinn`：原本**未启用** `SkinTintStrength` override；已启用并设为 `1.0`（原有效值继承 master 亦为 1.0）。
- `MI_FutsalKit_Quinn`：`KitTintStrength` 同样启用并设 `1.0`。
- 仅修改这两个 Prototype MI；未修改 Epic `MI_Quinn_*` / `M_Mannequin`。

## STEP 3–6 / 12 — 验收场景（仅修改 Test Map）

| Actor（`VSA_` 为 test-only） | 说明 |
|---|---|
| `VSA_Floor` | Engine Cube，scale (12,8,0.2) → 1200×800×20 cm，顶面 z=0，BlockAll 碰撞 |
| `VSA_Backdrop` | Engine Cube 中性灰背墙 50×1400×600，位于角色后方 |
| `VSA_KeyLight` / `VSA_FillLight` / `VSA_RimLight` | 白色 DirectionalLight（Movable；Key 投影，Fill/Rim 无投影） |
| `VSA_SkyLight` | Movable，白色，intensity 1.0 |
| `VSA_PlayerStart` | (650, 0, 150)，yaw 180 |
| `VSA_Camera` | (650, 0, 175)，pitch -5 / yaw 180 |

- Editor viewport 已保存至 (650,0,175) / pitch -5, yaw 180（可由用户直接查看 A/B/C）。
- WorldSettings `default_game_mode` 覆盖为引擎 `GameModeBase`（原地图无覆盖，全局为 `BP_NoPawnGameMode`：Play 无 pawn）；使其在 PlayerStart 生成 DefaultPawn 便于 Play 观察。**未创建任何新 Blueprint 控制器**。

## STEP 7–11 — 三个 Visual Test Case

三个 `BP_FutsalAppearancePrototype` 实例并排（rotation 相同，scale 1）：

| Label | Y | AppearanceId | SkinToneId | KitId | SkinTint | KitColor | NumberColor | JerseyNumber |
|---|---|---|---|---|---|---|---|---|
| `Appearance_CASE_A` | -180 | case_light_red_07 | 0 | kit_red | (1.0,0.8,0.65,1) | (0.85,0.06,0.06,1) | white | 7 |
| `Appearance_CASE_B` | 0 | case_medium_blue_10 | 1 | kit_blue | (0.72,0.5,0.38,1) | (0.05,0.16,0.75,1) | white | 10 |
| `Appearance_CASE_C` | 180 | case_dark_red_23 | 2 | kit_red | (0.38,0.24,0.17,1) | (0.85,0.06,0.06,1) | white | 23 |

- 未新建任何 Material Instance 资产；三例共享 `M_FutsalSkin_Master / MI_FutsalSkin_Quinn / M_FutsalKit_Master / MI_FutsalKit_Quinn / M_FutsalNumber_Master`，变化仅来自运行期 MID 参数。
- **必要使能改动**：Prototype 的 7 个外观变量原本**未勾选 Instance Editable**，无法写入逐实例值；已用 `BlueprintTools.set_variable_instance_editable` 将 `AppearanceId/SkinToneId/KitId/JerseyNumber/SkinTint/KitColor/NumberColor` 设为 instance-editable，随后编译 `BS_UP_TO_DATE` 并保存。**未新增/删除任何节点**。

## 关键发现 — Prototype 缺少默认 Mesh / AnimBP（已在实例修复）

- `BP_FutsalAppearancePrototype` 的 CDO 与新建实例的 `CharacterMesh0` 均**无 SkeletalMesh、无 AnimClass**（上一阶段的 `SKM_Quinn_Simple + ABP_FutsalSource` 只存在于旧 Map 实例的 instance override，非 BP 默认）。
- 后果：`InitializeAppearanceMaterials` 中的 `CreateDynamicMaterialInstance(GetMesh, GetMaterialIndex("Quinn_02"), MI_FutsalKit_Quinn)` 与 Skin 路径无法生成 MID → `SkinMID/KitMID` 回读为 `null`。
- 已在 Test Map 的三个实例补 `SKM_Quinn_Simple` + `ABP_FutsalSource_C`（`SKM_Quinn_Simple` 槽名 `Quinn_01/Quinn_02`）；未修改任何 Mesh/Skeleton/BP 资产。**BP 默认仍未改动**——正式化时应在 Prototype 默认中固化 Mesh/AnimBP。

## STEP 13 — 号码面片

四个面片（`FrontTens/FrontOnes/BackTens/BackOnes`）组件级相对变换（三实例一致，保持现状未改）：

| 组件 | Rel Location | Rot (roll,pitch,yaw) | Scale |
|---|---|---|---|
| FrontTens | (17, -6, 130) | (0, 90, 90) | (0.18, 0.24, 1.0) |
| FrontOnes | (17, 6, 130) | (0, 90, 90) | (0.18, 0.24, 1.0) |
| BackTens | (-17, 6, 130) | (0, -90, 90) | (0.18, 0.24, 1.0) |
| BackOnes | (-17, -6, 130) | (0, -90, 90) | (0.18, 0.24, 1.0) |

- 为临时占位值，未做视觉判断。`NUMBER_ATTACHMENT = COMPONENT_LEVEL_PROTOTYPE_ONLY`。

## STEP 14–15 — 运行期验证（只读）

PIE 多次采样回读：

| Case | Mesh | Anim | z | falling | SkinMID / SkinTint / Strength | KitMID / KitColor / Strength | Digits Tens/Ones | Tens visible |
|---|---|---|---|---|---|---|---|---|
| A | SKM_Quinn_Simple | ABP_FutsalSource_C | 92.2 | false | ✅ / (1.0,0.8,0.65) / 1.0 | ✅ / (0.85,0.06,0.06) / 1.0 | 0 / 7 | false |
| B | SKM_Quinn_Simple | ABP_FutsalSource_C | 92.2 | false | ✅ / (0.72,0.5,0.38) / 1.0 | ✅ / (0.05,0.16,0.75) / 1.0 | 1 / 0 | true |
| C | SKM_Quinn_Simple | ABP_FutsalSource_C | 92.2 | false | ✅ / (0.38,0.24,0.17) / 1.0 | ✅ / (0.85,0.06,0.06) / 1.0 | 2 / 3 | true |

- 三实例均存在、未掉落（连续采样 z 稳定 92.2，`is_falling=false`）。
- 4 个 Number MID 均存在，`Digit` 正确，`NumberColor` 白色。
- 验证脚本**只读**（`get_vector_parameter_value` / `get_scalar_parameter_value` / 属性读取）；未从 Python 调用 `SetVectorParameterValue`/`SetScalarParameterValue`/`CreateDynamicMaterialInstance`——所有 MID 均由 BP `BeginPlay` 逻辑创建。

## STEP 18 — 输出

```
MANUAL_BP_GRAPH = IMPLEMENTED
BP_COMPILE = PASS
FLOOR_COLLISION = PASS
NEUTRAL_LIGHTING = READY
CASE_A_RUNTIME = PASS
CASE_B_RUNTIME = PASS
CASE_C_RUNTIME = PASS
NO_PYTHON_MATERIAL_PARAMETER_WRITE = PASS
ANIMATION_BINDING = PASS
NUMBER_ATTACHMENT = COMPONENT_LEVEL_PROTOTYPE_ONLY
MANUAL_VISUAL_VALIDATION = WAITING_FOR_USER
APPEARANCE_VISUAL_TEST_STAGE = READY
```

### 待人工肉眼判断（未自动判定）

在 `L_FutsalAppearancePrototype_Test`（Simulate 或 Play）中观察 A/B/C 三人：

- A. 肤色：三档是否明显不同 / 是否仍有纹理明暗 / 有无发灰发白过黑
- B. 球衣：A 红、B 蓝、C 红 / 是否仍有纹理而非纯色塑料
- C. 号码：A 只显示 7（非 07）、B 显示 10、C 显示 23 / 前后方向是否正确
- D. 几何：号码是否严重悬空 / 穿身 / Z-fighting
- E. 动画：是否正常 Idle / 有无 T-pose / 有无掉穿地面

用户回答 PASS 或指出具体问题项。人工确认前不 commit。

---

---

# Phase 5B.2e.1 — 仅修复验收场景（Lighting / Exposure / Number Plane）

- 执行时间：2026-09-21
- 范围：**只改 Test Map 的灯光/曝光与 Prototype 号码面片变换**。未修改 `InitializeAppearanceMaterials` / `ApplyAppearance` / `EventGraph`；未修改 Skin/Kit/Number 材质逻辑、JerseyNumber 计算、MID 创建逻辑；未修改 `BP_FutsalCharacterBase` / `ABP_FutsalSource` / `L_FutsalCourt` / `UNREAL_RIG.uasset`。未 commit。

## STEP 1 — Lighting（DIRECTIONAL_LIGHT_CONFLICT = FIXED）

- 原先存在 3 个 `DirectionalLight`（`VSA_KeyLight` / `VSA_FillLight` / `VSA_RimLight`，priority 全为 0）→ ForwardShadingPriority 冲突并以叠加方式过亮。
- 处理：**删除** `VSA_FillLight`、`VSA_RimLight`。场景仅保留：
  - `VSA_KeyLight`：唯一 DirectionalLight（Movable，白色，intensity 3.14，`cast_shadows=True`，`forward_shading_priority=1`）。
  - `VSA_SkyLight`：SkyLight（Movable，白色，intensity 1.0）。
- 无任何彩色灯。

## STEP 2 — Exposure（OVEREXPOSURE = FIXED）

- 新增 `VSA_PostProcess`（`PostProcessVolume`）：`Unbound=True`，`priority=1`，`settings`：
  - `auto_exposure_method = AEM_MANUAL`
  - `auto_exposure_bias = 2.0`
  - `auto_exposure_apply_physical_camera_exposure = False`
  - `bloom_intensity = 0.0`
- 目的：关闭会随画面自适应而把角色推成纯白的自动曝光，改用固定手动曝光。
- 客观校验：经 `EditorAppToolset.CaptureEditorImage` 截图并做像素统计，中心区域 **pctNearWhite = 0%（无过曝纯白）**，maxLuminance ≈ 0.90–0.95。
- 诚实说明：本会话无法做**逐角色**颜色像素判定——`CaptureViewport` 会阻塞、`CaptureEditorImage` 输出为「编辑器窗口级」且分辨率/坐标无法与 3D 视口精确对齐。因此 LIGHT/MEDIUM/DARK 与 RED/BLUE 的最终可区分性仍由用户肉眼确认。

## STEP 4–5 — Number Plane

- 根因：原 rotation `(pitch=90, yaw=90, roll=0)` 使面片世界法线指向 **±Y（侧向）**、纹理 U 轴朝下 —— 从正面相机看接近侧边，呈现细条状 artifact。
- `M_FutsalNumber_Master` 的 `two_sided = False`（单面）。
- 修正后（组件级，三实例一致；已回读世界轴验证）：

| 组件 | Rel Location | Rel Rot (pitch,yaw,roll) | Scale | 法线 N | 向上 V | U |
|---|---|---|---|---|---|---|
| FrontTens | (18, 10, 130) | (0, 90, 90) | (0.18, 0.24, 1.0) | +X | +Z | +Y |
| FrontOnes | (18, -10, 130) | (0, 90, 90) | (0.18, 0.24, 1.0) | +X | +Z | +Y |
| BackTens | (-18, -10, 130) | (0, -90, 90) | (0.18, 0.24, 1.0) | -X | +Z | -Y |
| BackOnes | (-18, 10, 130) | (0, -90, 90) | (0.18, 0.24, 1.0) | -X | +Z | -Y |

- 正面法线朝相机（+X）故可见；因单面材质无法同时满足「朝相机 + 不镜像」，正面数字**可能为水平镜像**，需用户确认方向。背面朝 -X，从背后可见。
- 未修改 Digit 逻辑 / 材质图 / 可见性逻辑 / Skeleton / Socket；`NUMBER_ATTACHMENT = COMPONENT_LEVEL_PROTOTYPE_ONLY`。

## STEP 6 — Runtime Recheck

- 三实例存在；z = 92.2、`is_falling=False`（连续采样）；`mesh = SKM_Quinn_Simple`、`anim = ABP_FutsalSource_C`。
- `SkinMID` / `KitMID` / 4 个 Number MID 均由 BP 创建；`SkinTintStrength=KitTintStrength=1.0`。
- Digits：A 0/7（Tens 隐藏）、B 1/0、C 2/3；`NumberColor` 白。
- 验证脚本只读，未从 Python 写 MID 参数。

## 输出

```
VISUAL_STAGE_LIGHTING = READY
OVEREXPOSURE = FIXED
DIRECTIONAL_LIGHT_CONFLICT = FIXED
FRONT_NUMBER_VISUAL = READY
BACK_NUMBER_VISUAL = READY
FLOOR_COLLISION = PASS
MANUAL_VISUAL_VALIDATION = WAITING_FOR_USER
```

> 请再次进入 `L_FutsalAppearancePrototype_Test`（Simulate 或 Play）肉眼确认：A/B/C 肤色可区分、RED/BLUE 可区分、正面号码可读（并确认是否镜像）。人工确认前不 commit。

---

---

# Phase 5B.2f — Instance Override Fix

- 执行时间：2026-09-21
- 范围：**仅修复 Test Map 三实例对号码组件 Transform 的 instance override**，使「修改 BP 默认后实例跟随」。未修改号码算法 / Digit 逻辑 / 材质 / MID / 动画 / 生产资产。未 commit。

## STEP 2 — Blueprint 默认 Transform

> 说明：`BP` 的 CDO 不包含 SCS 号码组件，且 `simple_construction_script` property 在本工程 Python 中不可读。改以**新生成一个临时实例**（无 override）读取真实 Class Default。

| 组件 | Rel Loc | Rel Rot (p,y,r) | Rel Scale |
|---|---|---|---|
| FrontTens | (17, -6, 130) | (90, 90, 0) | (0.18, 0.24, 1.0) |
| **FrontOnes** | (17, 6, 130) | **(90, 0, 0)** ← 用户手工修改 | (0.18, 0.24, 1.0) |
| BackTens | (-17, 6, 130) | (-90, 90, 0) | (0.18, 0.24, 1.0) |
| BackOnes | (-17, -6, 130) | (-90, 90, 0) | (0.18, 0.24, 1.0) |

## STEP 3/4 — Root Cause

- 修复前三个实例的四个号码组件**完全相同**，但与 BP 默认不一致（旧值来自 Phase 5B.2e.1 写入的 instance override）。
- `ROOT_CAUSE = INSTANCE_COMPONENT_TRANSFORM_OVERRIDE`，`INSTANCE_COMPONENT_OVERRIDE = TRUE`。

## 修复前 → 修复后（三实例一致）

| 组件 | 修复前 (Loc / Rot) | 修复后 = BP Default (Loc / Rot) |
|---|---|---|
| FrontTens | (18, 10, 130) / (0, 90, 90) | (17, -6, 130) / (90, 90, 0) |
| FrontOnes | (18, -10, 130) / (0, 90, 90) | (17, 6, 130) / (90, 0, 0) |
| BackTens | (-18, -10, 130) / (0, -90, 90) | (-17, 6, 130) / (-90, 90, 0) |
| BackOnes | (-18, 10, 130) / (0, -90, 90) | (-17, -6, 130) / (-90, 90, 0) |

## STEP 5/6 — 修复策略

1. 先尝试 `ObjectTools.reset_properties`（等价「Reset to Default」）。**探测证明其在本工程无效**：对 mesh 的 `skeletal_mesh` override 调用后值仍为 `SKM_Quinn_Simple`，未回退到默认 `None` ⇒ 无法用它清除 override flag。
2. 最终采用「**删除并重新生成三个实例**」：新实例不含任何组件 override ⇒ 真正重新继承 BP 默认；随后精确写回：
   - Actor 级外观：`AppearanceId / SkinToneId / KitId / JerseyNumber / SkinTint / KitColor / NumberColor`
   - `Mesh = SKM_Quinn_Simple`、`AnimClass = ABP_FutsalSource_C`
3. 四个号码组件未做任何实例修改 ⇒ 无 override ⇒ 未来修改 BP 默认会自动跟随。

## STEP 7/8 — 保留项

- A/B/C 外观实例值完整保留（A: light/red/7、B: medium/blue/10、C: dark/red/23）。
- Mesh / AnimClass instance override 保留（Prototype CDO 默认仍为空，属既有状态，未改动）。

## STEP 10 — Runtime 验证（PIE）

- 三实例四个号码组件变换均等于 BP 默认（0 mismatch），`FrontOnes` rot = (90, 0, 0) 实际生效。
- 三人不掉落；`AnimInstance = ABP_FutsalSource_C`；SkinMID/KitMID/4×NumberMID 与外观值正常。

## STEP 11 — Reload 验证

- `LevelEditorSubsystem.load_level` 重新加载 Test Map 后：三实例仍与 BP 默认一致（allMatch = True），外观值保留。

## 输出

```
INSTANCE_COMPONENT_OVERRIDE = TRUE
INSTANCE_OVERRIDE_FIX = PASS
FRONT_ONES_DEFAULT_PROPAGATION = PASS
ALL_NUMBER_COMPONENT_TRANSFORMS_SYNCED = PASS
APPEARANCE_INSTANCE_VALUES_PRESERVED = PASS
MESH_ANIM_OVERRIDES_PRESERVED = PASS
ANIMATION_REGRESSION = PASS
INSTANCE_OVERRIDE_CLEARED = PASS
MANUAL_NUMBER_VISUAL_VALIDATION = REQUIRED
```

> 现在可以继续手动调整 `BP_FutsalAppearancePrototype` 的号码组件默认 Transform，Test Map 三实例会自动跟随。

---

---

# Phase 5B.2g — Manual Number Placement Freeze

- 执行时间：2026-09-21
- 前提：用户已在编辑器手工把号码 Plane 调到正确位置，正面肉眼结果 **A = 7 / B = 10 / C = 23** 已人工确认。
- 性质：**只读记录 + 验证**。**未修改任何号码 Plane 的 Location / Rotation / Scale**；未修改 BP 图 / 材质 / 号码逻辑 / 生产资产。未 commit。

## STEP 2 — 最终 Blueprint 号码 Plane Transform（用户手工值）

```
NUMBER_PLANE_TRANSFORM_SOURCE = USER_MANUAL_APPROVED
```

| 组件 | Relative Location | Relative Rotation (p, y, r) | Relative Scale |
|---|---|---|---|
| FrontTens | (-5, 15, 130) | (0, 0, 90) | (0.18, 0.24, 1.0) |
| FrontOnes | (5, 15, 130) | (0, -360, 90) | (0.18, 0.24, 1.0) |
| BackTens | (5, -15, 130) | (0, 540, 90) | (0.18, 0.24, 1.0) |
| BackOnes | (-5, -15, 130) | (0, 180, 90) | (0.18, 0.24, 1.0) |

> 用户输入原值保留；yaw `-360 / 540` 与 `0 / 180` 等价，未做归一化。

## STEP 3 — Test Map 实例继承

- A/B/C × 4 组件 = **12 组实例值全部 == BP Default**。
- `NUMBER_COMPONENT_INSTANCE_MISMATCH_COUNT = 0`
- 说明：Phase 5B.2f 已用「重建实例」清除号码组件 override，因此本次用户手工修改的 BP 默认**成功传播到三个实例**。

## STEP 4 — Appearance Instance Values（保留）

| Case | AppearanceId | SkinToneId | KitId | JerseyNumber | SkinTint | KitColor | NumberColor |
|---|---|---|---|---|---|---|---|
| A | case_light_red_07 | 0 | kit_red | 7 | (1.0,0.8,0.65,1) | (0.85,0.06,0.06,1) | (1,1,1,1) |
| B | case_medium_blue_10 | 1 | kit_blue | 10 | (0.72,0.5,0.38,1) | (0.05,0.16,0.75,1) | (1,1,1,1) |
| C | case_dark_red_23 | 2 | kit_red | 23 | (0.38,0.24,0.17,1) | (0.85,0.06,0.06,1) | (1,1,1,1) |

`APPEARANCE_INSTANCE_VALUES_PRESERVED = PASS`

## STEP 5 — Mesh / Animation Override（保留）

- 三实例 `Mesh = SKM_Quinn_Simple`、`AnimClass = ABP_FutsalSource_C`，未清除。
- `MESH_ANIM_OVERRIDES_PRESERVED = PASS`

## STEP 6 — Runtime（PIE，只读）

| Case | JerseyNumber | Tens 可见 | Digits Tens/Ones | SkinMID | KitMID | 4×NumberMID |
|---|---|---|---|---|---|---|
| A | 7 | false | 0 / 7 | ✅ | ✅ | ✅ |
| B | 10 | true | 1 / 0 | ✅ | ✅ | ✅ |
| C | 23 | true | 2 / 3 | ✅ | ✅ | ✅ |

`NUMBER_RUNTIME_LOGIC = PASS`；`NO_PYTHON_MATERIAL_PARAMETER_WRITE = PASS`（全程只读）。

## STEP 7 — 正面结果（用户已人工确认）

```
FRONT_NUMBER_VISUAL = USER_APPROVED
NUMBER_ATLAS_UV = PASS
DIGIT_SELECTION = PASS
SINGLE_DIGIT_VISIBILITY = PASS
FRONT_NUMBER_ORIENTATION = PASS
FRONT_NUMBER_PLACEMENT = PASS
```

## STEP 8 — 背面验收准备

- 仅移动 **Editor viewport camera** 到角色背面：位置 `(-650, 0, 175)`、旋转 `pitch=-5, yaw=0, roll=0`（在 -X 侧朝 +X 看，可同时看到 A/B/C 背面）。
- **未修改任何 Actor / Component Transform**（尤其 BackTens / BackOnes）。
- 待用户肉眼确认：A 背面 = 7、B 背面 = 10、C 背面 = 23；且非镜像 / 非倒置 / Tens-Ones 顺序正确 / 大致位于背部合理区域 / 无严重悬空 / 无严重穿模 / 无严重 Z-fighting。
- `BACK_NUMBER_VISUAL = USER_APPROVED`（用户 2026-09-21 背面视角肉眼验收通过：A=7 / B=10 / C=23）

## STEP 9 — Regression

- `FLOOR_COLLISION = PASS`（三人 z=92.2 稳定，`is_falling=false`）。
- `ANIMATION_REGRESSION = PASS`（`AnimInstance = ABP_FutsalSource_C`，无 T-pose / Mesh / AnimClass reset）。

## STEP 10/11 — Prototype 局限（保留）

- `NUMBER_SURFACE_INTEGRATION = PROTOTYPE_ONLY`。当前为浮动 **StaticMesh Plane**，**不代表生产号码方案，非 production-ready**。
- `PRODUCTION_NUMBER_SYSTEM = DEDICATED_JERSEY_UV + NUMBER_ATLAS`。正式模型要求：球衣拥有 dedicated number UV / number region；背部 UV 不镜像；Number Atlas 在球衣材质内采样；号码随 Skeletal Mesh / clothing deformation；不再依赖浮动 Static Plane。
- `MULTI_REGION_KIT_SYSTEM = NOT_IMPLEMENTED`；Quinn 仅证明 `WHOLE_KIT_COLOR_SWITCHING`。正式模型未来要求 `M_Skin / M_Shirt / M_Shorts / M_Socks / M_Shoes` 或对应可靠 mask。
- `PRODUCTION_INTEGRATION = NOT_STARTED`

## 输出

```
PHASE5B2G_MANUAL_NUMBER_PLACEMENT_FREEZE = COMPLETE
NUMBER_COMPONENT_INSTANCE_MISMATCH_COUNT = 0
APPEARANCE_INSTANCE_VALUES_PRESERVED = PASS
MESH_ANIM_OVERRIDES_PRESERVED = PASS
NUMBER_ATLAS_UV = PASS
DIGIT_SELECTION = PASS
SINGLE_DIGIT_VISIBILITY = PASS
FRONT_NUMBER_VISUAL = USER_APPROVED
BACK_NUMBER_VISUAL = USER_APPROVED
NUMBER_SURFACE_INTEGRATION = PROTOTYPE_ONLY
FLOOR_COLLISION = PASS
ANIMATION_REGRESSION = PASS
MANUAL_VISUAL_VALIDATION = USER_APPROVED (FRONT + BACK)
MANUAL_BP_GRAPH = IMPLEMENTED
INITIALIZE_APPEARANCE_MATERIALS = PASS
APPLY_APPEARANCE_BP_FUNCTION = PASS
NO_PYTHON_MATERIAL_PARAMETER_WRITE = PASS
PRODUCTION_NUMBER_SYSTEM = DEDICATED_JERSEY_UV + NUMBER_ATLAS
MULTI_REGION_KIT_SYSTEM = NOT_IMPLEMENTED
PRODUCTION_INTEGRATION = NOT_STARTED
```

> 正面与背面均已由用户肉眼验收通过（`FRONT_NUMBER_VISUAL = BACK_NUMBER_VISUAL = USER_APPROVED`）。`MANUAL_VISUAL_VALIDATION = USER_APPROVED (FRONT + BACK)`。人工验收已完成，是否 commit 由用户决定；在此之前不 stage / 不 commit。
