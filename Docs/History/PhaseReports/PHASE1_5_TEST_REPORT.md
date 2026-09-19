# PHASE1_5_TEST_REPORT — BP_FutsalCharacterBase 独立运行验证

- 执行时间：2026-09-16
- 验证对象：`/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`
- 结论：**实例化 ✅ / Components ✅ / Compile ✅ / 移动 ✅ / 跳跃 ✅ / CameraBoom ✅ / FollowCamera ✅ / 依赖 ✅**
- **未进入下一阶段。等待用户审核。**

---

## 1. 创建/新增资产（全部位于 FutsalMOT namespace）

| 资产 | 路径 | 说明 |
|---|---|---|
| 测试关卡 | `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test` | **新建空关卡**，未复制 L_FutsalCourt |
| 测试 GameMode | `/Game/FutsalMOT/Test/GM_FutsalCharacterBaseTest` | 为 PIE 提供可控角色而新增（见第 6 节 F1） |
| 测试场地 Actor | `TestFloor`、`TestPlayerStart`、`TestLight`、`Player_FutsalBase_Test` | 仅存在于测试关卡 |

磁盘：`Content/FutsalMOT/Test/`（2 个资产）。**L_FutsalCourt 内容未被修改**（见第 7 节）。

---

## 2. 实例化与 Components 验证

测试关卡中放置的实例 `Player_FutsalBase_Test`：

```
label      = Player_FutsalBase_Test
class      = BP_FutsalCharacterBase_C
class_path = /Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.BP_FutsalCharacterBase_C
location   = (500, 0, 200) → 落到 (500, 0, 92.2)   ← 受重力、站上地面
```

组件清单（编辑器 + PIE 双份取证）：

| 要求 | 组件对象 | 类 | 变量名 | 结果 |
|---|---|---|---|---|
| CapsuleComponent | `CollisionCylinder` | CapsuleComponent | `CapsuleComponent` | ✅ |
| CharacterMesh0 | `CharacterMesh0` | SkeletalMeshComponent | `Mesh` | ✅ |
| CameraBoom | `CameraBoom` | SpringArmComponent | `CameraBoom` | ✅ |
| FollowCamera | `FollowCamera` | CameraComponent | `FollowCamera` | ✅ |
| CharacterMovement | `CharMoveComp` | CharacterMovementComponent | `CharacterMovement` | ✅ |
| （附带） | `Arrow` | ArrowComponent | — | 原生 |
| （附带） | `CameraProxyMeshComponent_1` | CameraProxyMeshComponent | — | CameraComponent 引擎子对象 |
| （附带） | `DrawFrustumComponent_1` | DrawFrustumComponent | — | CameraComponent 引擎子对象 |
| （PIE 新增） | `PawnInputComponent0` | EnhancedInputComponent | — | 被占有后自动创建 ✅ |

Mesh 默认值：`skinned_asset = None`、`anim_class = None`、`animation_mode = ANIMATION_BLUEPRINT`（类默认，未改）
**这一步同时关闭了 Phase 1 的 R4 待办**：`CameraBoom` / `FollowCamera` 的变量名已在**本 BP 的实例上就地确认**。

---

## 3. Compile 结果

- 调用：MCP `BlueprintTools.compile_blueprint(BP_FutsalCharacterBase, warnings_as_errors=False)`
- 结果：`BlueprintStatus.BS_UP_TO_DATE` → **无 Compile Error，也无 Warning**
- UE 日志：`LogBlueprint: Compiling Blueprint '/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase'`，其后无任何 error/warning 行
- 已保存（`save_asset` = true）

---

## 4. PIE 结果

### 4.1 PIE 环境

```
PIE world   = /Game/FutsalMOT/Test/UEDPIE_0_L_FutsalCharacterBase_Test
pawn 数量   = 1        ← 只有我们的角色
pawn        = Player_FutsalBase_Test / BP_FutsalCharacterBase_C
controller  = PlayerController     ← 确实被玩家控制器占有（非 AIController）
```

### 4.2 静态状态（PIE 中读取）

| 项 | 值 |
|---|---|
| `CharacterMovement.movement_mode` | `MOVE_WALKING`（站立在地面） |
| `max_walk_speed` | `600.0` |
| `CameraBoom.target_arm_length` | `400.0` |
| `CameraBoom.use_pawn_control_rotation` | `True` |
| `MovementComponent.is_falling` | `False` |

### 4.3 移动 / 跳跃 / 相机（按 tick 采样，干净一轮）

| 指标 | 值 | 判定 |
|---|---|---|
| 起始位置 / 模式 | (500, 0, 92.2) / `MOVE_WALKING` | — |
| 行走 20 tick 后位置 | (4394.1, 0, **92.2**) | **贴地行走，Z 不变** ✅ |
| 行走时水平速度 | **600.0 cm/s**（= `max_walk_speed`） | **可以移动** ✅ |
| 行走后模式 | `MOVE_WALKING` | 未离地 ✅ |
| `can_jump()` | **true** | **可以跳跃** ✅ |
| 起跳前 Z | 92.2 | — |
| 跳跃最大 Z / 最大上升速度 | **207.7**（ΔZ = **115.5 cm**）/ **173.3 cm/s** | **可以跳跃** ✅ |
| 跳跃过程中 `is_falling` | **true** | 离地确证 ✅ |
| 结束位置 / 模式 | (4514.5, 0, 92.2) / `MOVE_WALKING` | 落地恢复行走 ✅ |
| 测试全程位移 | **+4014.5 cm**（X 方向） | ✅ |
| 相机位移（全程） | start_cam (100,0,100.6) → end_cam (4114.5,0,100.6) = **+4014.5 cm**，与角色完全一致 | **FollowCamera 工作** ✅ |
| 相机相对角色 X 偏移 | **-400.0 cm**（恒等于 Boom 臂长） | **CameraBoom 工作** ✅ |

PIE 期间无任何 `P15TICK_ERR`。回调已用 `P15R2_UNREG ok` 正常注销，**无残留 tick 回调**。

### 4.4 本轮第一遍 PIE 的失败（harness 问题，已如实记录）

第一遍 PIE 的完整轨迹（`P15MOVE`）：

```
tick  1: x=  643.0  z=     92.2  spd=  0.0  MOVE_WALKING    ← 在地面
tick 15: x= 3337.1  z=  -7170.9  spd=600.0  MOVE_FALLING    ← 已坠落到地下
tick 30: x= 6337.1  z= -27144.4  spd=600.0  MOVE_FALLING
tick 90: x=18337.1  z=-107144.5  spd=600.0  MOVE_FALLING
```

原因：**我搭的测试地板只有 20m×20m**，角色以 600cm/s 走出边缘后坠入虚空。这是 harness 尺寸错误，**不是 BP 缺陷**。
处理：把 `TestFloor` 放大到 200m×200m 并重跑 PIE，得到第 4.3 节的干净结果。（属测试场地修正，不涉及被禁止的资产。）

---

## 5. Dependency 结果

强制 `scan_paths_synchronous(force=True)` 后重新读取：

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

referencers: /Game/FutsalMOT/Test/GM_FutsalCharacterBaseTest,
             /Game/FutsalMOT/Test/L_FutsalCharacterBase_Test
```

| 检查项 | 结果 |
|---|---|
| `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter` | **无** ✅ |
| `/Game/Characters/Mannequins` | **无** ✅ |
| `ABP_FutsalPlayer` | **无** ✅ |
| `UNREAL_RIG`（额外检查） | **无** ✅ |

`forbidden_hits = []`

---

## 6. 失败/异常项（按"只报告，不自动修复"）

### F1 —— 测试 GameMode 的 `DefaultPawnClass` 写入未生效（**未修复**）

- 我对 `GM_FutsalCharacterBaseTest` 的 CDO 执行 `modify(True)` + `set_editor_property('default_pawn_class', BP_FutsalCharacterBase_C)`，同会话读回正确、`save_asset` 返回 true。
- 但 PIE 运行时该 GameMode 实例的 `DefaultPawnClass` 实际是 `/Script/Engine.DefaultPawn`，于是 PIE 生成的是 `DefaultPawn0` 且被 PlayerController 占有 —— 我们的角色没被控制。
- 与 Phase 1 里 `skinned_asset` 同类现象：**对该 BP CDO 的 `set_editor_property` 不能可靠地落到"类默认值"**（证据：GM CDO 现值正确，但运行时实例是引擎默认）。
- 规避方式（本次采用）：清掉测试关卡 WorldSettings 的 GameMode 覆盖，并给关卡中的实例设 `auto_possess_player = Player0` → PIE 单 Pawn、由 PlayerController 占有，验证成功。
- **`GM_FutsalCharacterBaseTest` 目前是一个"存在但 DefaultPawnClass 未生效"的资产**。是否保留、删除或改用其它方式提供默认 Pawn，请你决定。

### F2 —— 输入链路（EnhancedInput / IMC）未验证

- 测试 GameMode 的 PlayerController 是原生 `/Script/Engine.PlayerController`，**没有任何组件向 EnhancedInput 子系统注册 Input Mapping Context（IMC）**。
- 因此 `IA_Move` / `IA_Jump` 等 Input Action 在 PIE 中不会被触发；本轮的"移动/跳跃"是通过直接调用 `Pawn.AddMovementInput` / `Character.Jump` 验证的**能力**，不是**输入绑定**。
- 结论：`BP_FutsalCharacterBase` 目前**不具备自成体系的输入供给**（这与 Phase 1 报告的 R2 一致）。属 Input 阶段范围，本次不改。

### F3 —— 程序化截图未产生文件（**未修复**）

- 调用 `unreal.AutomationLibrary.take_high_res_screenshot(1280,720,...)` 两次（PIE 前 / 后），`Saved/Screenshots/` 下**没有生成任何新文件**（目录内只有一张 2026-08-17 的旧图，无 `P15SHOT_ERR` 异常输出）。
- 因此本报告无法附自动截图，改为第 7 节的人工截图清单。

### F4 —— 一个既有资产在无我方调用的情况下被写入（**需你确认**）

- `Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset` 现为 `M`，**大小 4558939 → 4558993 字节（+54 字节）**，文件 mtime `2026-09-16 16:39:09`。
- 同一时刻 `Content/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/3/9C/Y0JGOL8DGDZM92Y13253CG.uasset` 的 mtime 也被刷新，但**内容与 HEAD 完全一致（7734 字节无变化，git 不报修改）**。
- 我方在该时刻（UE 日志 08:39:09）**没有任何 MCP/UE 调用**（前后两次调用分别是 08:37:45 与 08:42:15），Phase 1.5 也**从未加载或保存过 `UNREAL_RIG`**。
- 该 +54 字节改动形态上像一次"重新保存"而非内容编辑。**请不要当作我的改动；也请确认是不是你在编辑器里做过保存（例如 Save All）。** 按规则我**没有**回滚它。

---

## 7. 截图清单（需人工采集）

自动截图失败（F3），请在编辑器中按下列清单截图存档：

| # | 场景 | 要点 |
|---|---|---|
| S1 | 内容浏览器 `/Game/FutsalMOT/Test/` | 显示 `L_FutsalCharacterBase_Test` 与 `GM_FutsalCharacterBaseTest` 两个资产 |
| S2 | 大纲（Outliner）+ 视口 | 测试关卡中的 `TestFloor` / `TestPlayerStart` / `TestLight` / `Player_FutsalBase_Test` |
| S3 | `Player_FutsalBase_Test` 的细节面板 → Components | 展开后能看到 `CapsuleComponent`、`CharacterMesh0`、`CameraBoom`、`FollowCamera`、`CharacterMovement` |
| S4 | 同上 → `Mesh` 组件展开 | `Skeletal Mesh = None`、`Anim Class = None` |
| S5 | `BP_FutsalCharacterBase` 蓝图的"类默认值"面板 → Components | 与 S3 同项，确认是**类默认**而非实例覆盖 |
| S6 | `BP_FutsalCharacterBase` 的`Move` / `Aim` 函数图 | 存档函数逻辑（工具读不到语义，只有你能目视确认） |
| S7 | PIE 运行中（起始静止） | 角色站在 `TestFloor` 上，FollowCamera 视角正常 |
| S8 | PIE 运行中（移动后） | 角色已沿 X 前进，相机跟随 |
| S9 | PIE 运行中（跳跃瞬间） | 角色离地，`is_falling` 阶段 |
| S10 | 编译结果 | `BP_FutsalCharacterBase` 的编译器结果面板无 Error/Warning |
| S11 | 关卡 World Settings | 确认 `GameMode Override` 已被清空（F1 的规避配置） |
| S12 | `Player_FutsalBase_Test` 细节面板 → Pawn | `Auto Possess Player = Player 0`（F1 的规避配置） |

---

## 8. 当前编辑器状态（需要你知道）

- **当前打开的关卡已切换到 `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test`**（不再是 L_FutsalCourt）。测试关卡已保存。
- 外层 git 未提交状态：
  ```
   M Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset   ← 见 F4，非我改动
  ?? Content/FutsalMOT/Characters/Base/
  ?? Content/FutsalMOT/Test/
  ?? PHASE1_REPORT.md
  ```
- `BP_FutsalCharacterBase` 状态：`BS_UP_TO_DATE`，已保存。
- 无残留 tick 回调。

---

## 9. 自查：Phase 1.5 禁止事项

| 禁止项 | 状态 |
|---|---|
| 修改 L_FutsalCourt | 未修改（只有 external actor 的 mtime 被刷新，字节数不变；见 F4） |
| 修改 Player_L0~Player_R4 | 未修改（在 L_FutsalCourt 中，未触碰） |
| 修改任何 Level Sequence | 未修改 |
| 修改 BP_ThirdPersonCharacter | 未修改 |
| 修改 BP_ThirdPersonCharacter_Soccer | 未修改 |
| 修改 ABP_FutsalPlayer | 未修改 |
| 修改 ABP_FutsalPlayer_Soccer | 未修改 |
| 修改任何 Skeleton | 未修改 |
| 修改任何 Animation Blueprint | 未修改 |

**唯一涉及既有资产的写入是 F4（UNREAL_RIG +54 字节），我方无对应该时刻的调用记录，已如实上报，未做任何回滚。**

---

## 10. 待你决定

1. F1：`GM_FutsalCharacterBaseTest` 保留 / 删除 / 改为其它默认 Pawn 方案？
2. F4：请确认 16:39:09 的两次写入是否来自你的编辑器操作。
3. 是否把 `BP_FutsalCharacterBase` / `Content/FutsalMOT/Test/` 提交入库？
4. 验证完成后，编辑器是否需要切回 `L_FutsalCourt`？
5. 是否进入 Phase 2（Input / 依赖解耦）？

**未进入下一阶段。**
