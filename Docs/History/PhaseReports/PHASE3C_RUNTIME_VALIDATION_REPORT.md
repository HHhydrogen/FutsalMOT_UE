# PHASE3C_RUNTIME_VALIDATION_REPORT — ABP_FutsalSource 运行期验证

- 执行时间：2026-09-19
- 基线 branch：`refactor/character-architecture` @ `f870f3b919feb92e574071e2c7b254a961207997`
- 性质：**测试隔离运行期验证**。仅修改测试地图实例；未改 Blueprint Class Defaults；未改 `L_FutsalCourt` / `Player_L0~R4` / `ABP_FutsalPlayer` / `ABP_FutsalPlayer_Soccer` / `UNREAL_RIG` / ControlRig；未 commit、未 stage。
- 执行环境：真实 Unreal Editor 5.8（PID 33244，MCP `FutsalMOTTools.run_python_code`）。进入本阶段时编辑器处于 PIE，已 `StopPIE` 后操作。

---

## 1. Test map

| 项 | 值 |
|---|---|
| Path | `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test` |
| 类型 | 普通 Level（**非** World Partition；package = `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test`） |
| Deps | `SKM_Quinn_Simple`、`BP_FutsalCharacterBase`、`GM_FutsalInputTest`、`/Engine/BasicShapes/Cube`、`/Engine/EngineMaterials/WorldGridMaterial`、`/Script/NavigationSystem` |
| Referencers | `[]` |
| 关卡内容 | `TestFloor`(StaticMeshActor)、`TestPlayerStart`(PlayerStart)、`TestLight`(DirectionalLight)、`Player_FutsalBase_Test`(BP_FutsalCharacterBase_C) |

## 2. Test actor configuration

| 项 | Before（STEP 1） | After（STEP 2 绑定 + reload） |
|---|---|---|
| Actor | `Player_FutsalBase_Test` | `Player_FutsalBase_Test` |
| Class | `BP_FutsalCharacterBase_C` | `BP_FutsalCharacterBase_C`（未改） |
| Component | `CharacterMesh0` | `CharacterMesh0` |
| Mesh | `SKM_Quinn_Simple` | `SKM_Quinn_Simple` |
| Skeleton | `SK_Mannequin` | `SK_Mannequin` |
| AnimClass | `None` | **`ABP_FutsalSource_C`** |

- Blueprint Class Defaults（`BP_FutsalCharacterBase` CDO）：`Mesh = None`、`AnimClass = None`，**未被修改**；`BP_FutsalCharacterBase.uasset` git clean。
- STEP 3 PIE 校验：GameWorld = `UEDPIE_0_L_FutsalCharacterBase_Test`；Pawn = `BP_FutsalCharacterBase_C_0`（label `Player_FutsalBase_Test`）；Mesh = `SKM_Quinn_Simple`；**AnimInstance = `ABP_FutsalSource_C`** ✅

## 3. AnimClass binding

| 步骤 | 结果 |
|---|---|
| 绑定方式 | 仅实例属性 `CharacterMesh0.animClass = /Game/FutsalMOT/Animation/Source/ABP_FutsalSource.ABP_FutsalSource_C`（MCP `ObjectTools.set_properties`） |
| 保存 | `LevelEditorSubsystem.save_current_level() = True`；`L_FutsalCharacterBase_Test.umap` 已写盘（mtime 15:15:55） |
| 重新加载验证 | AnimClass 仍为 `ABP_FutsalSource_C` ✅ |
| 类默认 | 未修改（仍 None）✅ |

## 4. Locomotion result

驱动方式：运行期每 tick 调用 `BP_FutsalCharacterBase.Move(1.0, 0.0)`（等价于 Enhanced Input `IA_Futsal_Move` 触发的处理器），持续约 3s。

| 变量 | 静止 | 行走中 |
|---|---|---|
| `MotionSpeedMps`（Character 提供的接口通道） | 0.0 | **0.0** |
| `Use Auto Motion Speed` | True | True |
| `Auto Motion Speed Mps` | 0.0 | **6.000000067** |
| `Effective Motion Speed Mps` | 0.0 | **6.000000067** |
| `GroundSpeed` | 0.0 | **600.0** (cm/s) |
| `ShouldMove` | False | **True** |
| `IsFalling` | False | False |
| Pawn velocity | (0,0,0) | **(0, 600, 0)** cm/s |
| `Auto Motion Velocity` / `Effective Velocity` | (0,0,0) | **(0, 600, 0)** |

- **Idle → Walk 已触发**：`ShouldMove=False→True`，`Effective Motion Speed Mps 0→6.0`。
- **BlendSpace 输入 `Effective Motion Speed Mps` 由 0→6.0 连续变化**（BlendSpace 实际播放状态无法用 Python 直接读取，标为 INFERRED_ACTIVE；但驱动量已确认变化）。`Use Auto Motion Speed=True` ⇒ BlendSpace 使用 Auto 速度通道。
- `MotionSpeedMps` 保持 0：本测试通过直接调用 `Move` 驱动，未走 `IA_Futsal_Move` 的 Enhanced Input 触发，且 `Move` 本身不写 `MotionSpeedMps`；该项由 `Use Auto Motion Speed=True` 旁路。

## 5. Jump / Fall / Land result

驱动方式：运行期调用 `ACharacter::Jump`，采样 `IsFalling` 与高度 z。

单次跳（字符层）：

| t(s) | vz (cm/s) | IsFalling | z(cm) | 阶段 |
|---|---|---|---|---|
| 0.33 | 0 | false | 92.2 | 站立 |
| 0.67 | +173.3 | **true** | 204.4 | 起跳/上升 |
| 1.00 | -153.3 | **true** | 207.7 | 顶点 |
| 1.33 | -480.0 | **true** | 102.1 | 下落 |
| 1.67 | 0 | **false** | 92.2 | 落地 |

- 连续 5 次跳跃循环（间隔 ~2.2s）均稳定复现 `Jump(true) → Fall → Land(false)`。
- AnimInstance 层 `IsFalling` 同步切换（`ABP_FutsalSource.IsFalling` true↔false），跳跃期间 `Effective Motion Speed Mps=0`（无水平输入）。
- ⇒ Jump/Fall/Land 状态驱动正常 ✅

## 6. Direction result

驱动方式：`Move(1.0, 1.0)`（W+D）约 1.2s。

| t(s) | vel x | vel y | `Direction` | `Effective Motion Speed Mps` | IsFalling |
|---|---|---|---|---|---|
| 1.00 | 377 | 377 | **0.0** | 3.16 | false |
| 1.33 | 424 | 424 | **0.0** | 6.0 | false |
| 1.66 | 424 | 424 | **0.0** | 6.0 | false |
| 2.00 | 0 | 0 | 0.0 | 2.27 | false |

- 斜向输入产生对角速度 (424,424)（合成 600 cm/s = 6 m/s）。
- `Direction` 始终 ≈ **0.0**：角色使用 **自动朝向移动方向**（`bOrientRotationToMovement` 风格），因此速度相对角色本体系恒为“前向”，**未观察到 Strafe 分支**。这是角色运动模式决定的行为，非 ABP 缺陷。
- W+D 合成速度与 W 单键一致（6 m/s），方向混合正确。

## 7. Input result

| 项 | 结果 |
|---|---|
| Enhanced Input 处理器函数 | `Move`(IA_Futsal_Move / PrimaryThumbstick 共用)、`Aim`(IA_Futsal_Look / IA_Futsal_MouseLook / SecondaryThumbstick 共用)、`Jump`(IA_Futsal_Jump / TouchJumpStart)、`StopJumping`(IA_Futsal_Jump Completed / TouchJumpEnd) —— 运行期直接调用 `Move`/`Jump` 均生效 ✅ |
| 节点级绑定 | `EnhancedInputActionIA_Futsal_Move/Look/MouseLook/Jump` 节点及其连线在 Phase 3A/3B 已核验存在且未改动 |
| 原始按键注入 | **未能执行**：Python 无法取得 `EnhancedInputLocalPlayerSubsystem`（`APlayerController.Player` 受保护；无 `SubsystemBlueprintLibrary`），故未做真实 W/Space/Mouse 按键注入。以处理器函数运行期调用来替代验证（`MOVE_CALL_EXECUTES`、`JUMP_CALL_EXECUTES`）。 |
| 未添加 Debug 节点 | ✅ 未添加任何 Debug 节点 |

## 8. MotionSpeed semantics

- `BP_FutsalCharacterBase.GetMotionSpeedMps()` 返回 `self.MotionSpeedMps`（Phase 3A 已证：`self.MotionSpeedMps → Return`，无换算）。
- 运行期：`ABP_FutsalSource.MotionSpeedMps = 0.0`（Character 通道未被驱动），`Use Auto Motion Speed = True` ⇒ `Effective Motion Speed Mps = Auto Motion Speed Mps`。
- 语义链完整、数值无换算；接口通道存在但当前被 Auto 通道旁路。

```
MOTION_SPEED_SEMANTICS = PRESERVED
```

## 9. FootIK result

| 项 | 结果 |
|---|---|
| `CR_Mannequin_FootIK` 依赖 | `ABP_FutsalSource` deps 含 `/Game/Characters/Mannequins/Rigs/CR_Mannequin_FootIK`、`/Script/ControlRig`、`/Script/ControlRigDeveloper` |
| 运行期报错/警告 | 本次 PIE 日志**未发现** `LogControlRig`/FootIK 相关 Error/Warning |
| 是否正常执行 | **UNKNOWN**（AnimGraph 中 ControlRig 节点是否在实际执行路径无法用 Python/MCP 读取） |
| pose 是否异常 | **UNKNOWN**（需人工目视/截图，或后续在真实索具与 IK 目标下验证） |
| 是否修改 ControlRig | ✅ 未修改 |

## 10. Known issues

1. **Key 注入不可用**：本环境 Python 无法获取 `EnhancedInputLocalPlayerSubsystem`，无法注入真实 W/Space/Mouse；改用直接调用 `Move`/`Aim`/`Jump` 处理器函数验证（等价逻辑，但不覆盖按键→Action 映射本身）。
2. **`MotionSpeedMps` 恒为 0**：测试仅经 `Move` 驱动，未走 Enhanced Input 触发；且 `Use Auto Motion Speed=True` 使该通道被旁路。若需验证接口通道数值传递，应在 `Use Auto Motion Speed=False` 或写入 `MotionSpeedMps` 的路径下测试（本阶段不允许改类默认，故未做）。
3. **采样频率低（~3 Hz）**：Slate post-tick 回调在编辑器空闲时约 3 次/秒，跳跃/方向瞬态采样较稀疏，仅能覆盖关键帧。
4. **测试地面过小**：持续前进会跑出 `TestFloor` 并坠入虚空（曾观测 vz 终速 -4000）；方向测试改用限时短冲（1.2s）规避。
5. **Strafe 未出现**：角色自动朝向移动方向，`Direction≈0`；如需验证 Strafe/BlendSpace 左右分支，需要角色使用“朝向相机/控制器”而非朝向移动的模式，或注入绕 Y 轴分量并冻结朝向。
6. **FootIK 无法自动判定**：见第 9 节。
7. **AnimGraph 播放状态不可读**：BlendSpace/StateMachine 当前播放状态无法由 Python 读取，只能由驱动量（ShouldMove/Effective Motion Speed/IsFalling）推断。

## 11. Next phase recommendation

1. **人工目视验收（建议下一步）**：在 `L_FutsalCharacterBase_Test` 用 PIE 手动按 W / Space / W+A / W+D，确认 Idle→Walk/Run、Jump/Fall/Land 视觉正确、无 T-pose、无 FootIK 异常。
2. **接口通道补测**：在**测试实例**上临时设 `Use Auto Motion Speed=False`（仅实例、不改类默认），或将 `IA_Futsal_Move` 的值写入 `MotionSpeedMps`，验证 `BP_FutsalCharacterBase.MotionSpeedMps → BPI → ABP` 数值原样传递。
3. **脚部 IK 专项**：在 `CR_Mannequin_FootIK` 与 `SK_Mannequin` 上确认 ControlRig 在 AnimGraph 执行路径且无骨骼错配警告；必要时截图。
4. **回滚/收尾**：本阶段测试改动仅 `L_FutsalCharacterBase_Test.umap`（实例 AnimClass）与既有 `L_FutsalCourt`+external actor 改动；均未 commit。若 Phase 3C 通过，建议在**测试实例**上切换到 `ABP_FutsalSource` 的生产绑定方案前，先决定 `L_FutsalCourt` pending 改动的去留。
5. **仍不做 Skeleton migration**。

---

## 附：本阶段未做（自查）

- 未修改 `BP_FutsalCharacterBase` 类默认 / 任何 Blueprint Class Defaults ✅
- 未修改 `L_FutsalCourt`、`Player_L0~R4` ✅（其改动为本阶段之前既有状态，未再触碰）
- 未修改 `ABP_FutsalPlayer` / `ABP_FutsalPlayer_Soccer` / `BP_ThirdPersonCharacter` / `UNREAL_RIG` / ControlRig / IK / AnimSequence / BlendSpace ✅
- 未添加 Debug 节点；未 Rename/Move/Delete/Consolidate/Fix Redirectors ✅
- 未 commit、未 stage ✅
- 已 `StopPIE` 并注销 `register_slate_post_tick_callback` 回调 ✅

---

# Phase 3C.1 — INTERFACE_RUNTIME_PROOF（MotionSpeed 接口运行期数值证明）

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `f870f3b919feb92e574071e2c7b254a961207997`
- 性质：PIE 运行期临时设置（**未保存**）；未修改任何资产默认值；未 stage / commit / tag / push。

## STEP 1 — 当前状态复核（PASS）

| 资产 | BlueprintStatus | 关键依赖 |
|---|---|---|
| `ABP_FutsalSource` | BS_UP_TO_DATE | `BPI_FutsalAnimationSource`、`BS_Futsal_Locomotion`、`SK_Mannequin`、`CR_Mannequin_FootIK`、MM_* |
| `BP_FutsalCharacterBase` | BS_UP_TO_DATE | `BPI_FutsalAnimationSource`、`BPI_FutsalTouchInterface`、`IA_Futsal_*` |
| `BPI_FutsalAnimationSource` | BS_UP_TO_DATE | deps=[] |

- 依赖方向：`ABP_FutsalSource → BPI_FutsalAnimationSource` ✅；`BP_FutsalCharacterBase → BPI_FutsalAnimationSource` ✅；**无** `ABP_FutsalSource → BP_FutsalCharacterBase`；**无** `ABP_FutsalSource → BP_ThirdPersonCharacter` ✅
- Test actor：Mesh `SKM_Quinn_Simple`、AnimClass `ABP_FutsalSource_C` ✅

## STEP 2 — PIE transient interface test

| 变量 | 实测 |
|---|---|
| `Character.MotionSpeedMps`（PIE 临时设为 2.5） | **2.5** |
| `ABP_FutsalSource.MotionSpeedMps` | **2.5** ✅ |
| `ABP_FutsalSource.Use Auto Motion Speed` | **True**（只读：`CPF_DisableEditOnInstance`） |
| `ABP_FutsalSource.Auto Motion Speed Mps`（静止） | 0.0 |
| `ABP_FutsalSource.Effective Motion Speed Mps` | 0.0（UseAuto=True ⇒ 跟随 Auto） |

- **接口链运行期证明（PASS）**：
  ```
  Character.MotionSpeedMps = 2.5
        ▼  BPI_FutsalAnimationSource.GetMotionSpeedMps
  ABP_FutsalSource.MotionSpeedMps = 2.5
  ```
  数值原样传递（无换算）；`Character → BPI → ABP` 三段均在运行期实测一致。
- **`Effective Motion Speed Mps = 2.5` 未能成立**：`Use Auto Motion Speed` 在实例上不可写（引擎 flag `CPF_DisableEditOnInstance`；Python `set_editor_property`、`BlueprintEditorLibrary.set_editor_property`、MCP `ObjectTools.set_properties` 三路均返回 "cannot be edited on instances"，且无 `Set` 反射函数）。因此无法把 Select 切到 external 分支。**未做任何资产修改来强行切换。**

## STEP 3 — Auto path regression

运行期持续 `Move(1.0, 0.0)`，同时把 `Character.MotionSpeedMps` 恒设为 2.5：

| t(s) | ABP.MotionSpeedMps | UseAuto | Auto Motion Speed Mps | Effective Motion Speed Mps |
|---|---|---|---|---|
| 0.33 | 2.5 | true | 0.0 | 0.0 |
| 0.66 | 2.5 | true | 2.86 | 2.86 |
| 1.00 | 2.5 | true | 5.96 | 5.96 |
| 1.33→8.0 | 2.5 | true | 6.00 | 6.00 |

- `Effective Motion Speed Mps` 随移动速度变化（0→2.86→5.96→6.0），**且始终等于 Auto，不等于 external 2.5**。
- ⇒ Select 的 `UseAuto = True → Auto Motion Speed Mps` 分支**运行期成立** ✅

## STEP 4 — 退出 PIE 与持久化检查（PASS）

重新加载 `L_FutsalCharacterBase_Test` 后：

| 对象 | 值 | 判定 |
|---|---|---|
| Test actor Mesh / AnimClass | `SKM_Quinn_Simple` / `ABP_FutsalSource_C` | 仅保留 Phase 3C 的实例绑定（预期） |
| Test actor `MotionSpeedMps` | **0.0** | 临时 2.5 未保存 ✅ |
| `BP_FutsalCharacterBase` CDO `MotionSpeedMps` / `AnimClass` | `0.0` / `None` | 未修改 ✅ |
| `ABP_FutsalSource` CDO `Use Auto Motion Speed` / `MotionSpeedMps` | `True` / `0.0` | 未修改 ✅ |

## 结论

```
MOTION_SPEED_INTERFACE_RUNTIME = PASS
DUAL_SPEED_PATH_SEMANTICS = PARTIAL
```

- `MOTION_SPEED_INTERFACE_RUNTIME = PASS`：`Character.MotionSpeedMps → BPI_FutsalAnimationSource.GetMotionSpeedMps → ABP_FutsalSource.MotionSpeedMps` 运行期数值一致（2.5）。
- `DUAL_SPEED_PATH_SEMANTICS = PARTIAL`：
  - `UseAuto = True → Auto Motion Speed Mps` 分支：**运行期 PASS**（external 通道存在 2.5 时，Effective 仍取 Auto 6.0）。
  - `UseAuto = False → external MotionSpeedMps` 分支：**未能取得运行期证据**——`Use Auto Motion Speed` 为 `CPF_DisableEditOnInstance`，运行期不可写；该 Select 的静态存在性已在 Phase 3A/3B 证明。此为工具/引擎限制，**非**接口或语义缺陷。
- 建议：若必须取得 external 分支的运行期证据，可在一份**允许修改的临时副本 ABP**（复制后改 `Use Auto Motion Speed` 的实例可编辑性）中测试；不在本阶段执行。

---

# Phase 3C Final — MANUAL_VISUAL_VALIDATION

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `f870f3b919feb92e574071e2c7b254a961207997`
- 用户已完成最终人工 PIE 视觉验收，确认全部通过。

| 人工检查项 | 结果 |
|---|---|
| Idle 姿势正常 | PASS |
| W locomotion 正常 | PASS |
| 无 T-pose | PASS |
| Jump → Fall → Land 视觉连续 | PASS |
| W+A / W+D 对角移动无明显爆跳 | PASS |
| Mouse 相机正常 | PASS |
| 肉眼可见双脚穿地 / 异常抽搐 | NONE |
| 肉眼可见 FootIK 异常 | NONE |

```
MANUAL_VISUAL_VALIDATION = PASS
```

## 保留的自动证明结论（未篡改）

```
MOTION_SPEED_INTERFACE_RUNTIME = PASS
DUAL_SPEED_PATH_SEMANTICS = PARTIAL
```

- `UseAuto = True → Auto Motion Speed Mps` 分支 = **PASS**（运行期）。
- `UseAuto = False → external MotionSpeedMps` 分支：由于 `Use Auto Motion Speed` 属性为 `CPF_DisableEditOnInstance`，无法在 runtime instance 上翻转，故**未取得 Select false branch 的直接运行期证据**。此为工具/引擎限制，**非**已知语义缺陷。**不得改写为 FULL PASS。**

## Phase 3C 最终结论

```
SOURCE_ANIMBP_RUNTIME_VALIDATION = PASS
```

理由：`ABP_FutsalSource` 已在独立测试角色（`Player_FutsalBase_Test`，`SKM_Quinn_Simple` / `SK_Mannequin`）上完成：

- Runtime AnimInstance binding（`ABP_FutsalSource_C`）
- Locomotion（Idle → Walk，Effective Motion Speed 0 → 6.0）
- Jump / Fall / Land（`IsFalling` 切换、z 92 → 207 → 92）
- Direction（对角输入合成速度，自动朝向移动方向）
- MotionSpeed interface transfer（`Character.MotionSpeedMps 2.5 → ABP.MotionSpeedMps 2.5`）
- Auto speed path（UseAuto=True 时 Effective 跟随 Auto）
- Manual visual validation（人工 PIE 全部 PASS）

`SKELETON_MIGRATION = NOT_STARTED`。
