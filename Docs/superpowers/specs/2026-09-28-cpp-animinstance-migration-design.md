# FutsalPlayer AnimInstance C++ 迁移设计

## 阶段目标

将规范动画蓝图 `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase` 中的初始化与逐帧动画数据更新逻辑迁移到原生 `UFutsalPlayerAnimInstance`。现有 AnimGraph、Locomotion 状态机、Main States 状态机及其转换图保留为最终 Pose 组装和状态求值层。本阶段完成后，EventGraph 不再拥有运动数据更新职责，C++ 发布的动画变量继续驱动现有蓝图状态机。

本阶段不把 BlendSpace、动画序列或 FootIK ControlRig 改写为 C++，不替换两套状态机，不改状态转换、不改动画资源引用。保留当前规范 ABP 资产路径，避免改变角色和 Sequencer 对现有资产的引用身份。

## 不变量

- Sequencer Transform 轨道是 Actor 世界位置和朝向的唯一权威来源。
- 动画实例只读取轨迹并计算动画输入，不修改 Actor Transform、CharacterMovement 速度或 Root Motion。
- `ExternalMotionSpeedMps` 是动画速度标量，不能作为 `EffectiveVelocity` 或方向输入。
- 当前经人工截图转录的旧行为是数据计算的基线；不得把新的 CharacterMovement 优先级描述为旧蓝图等价行为。
- 不修改 `BS_FutsalPlayerBase_Locomotion` 的资产、轴、27 个样本、动画片段或播放速率。
- 不修改 Idle、Jump、Fall、Land 动画序列，不修改 ControlRig、Slot、缓存 Pose 拓扑或状态机转换。
- 不删除任何退休资产，不修改受保护的 `UNREAL_RIG.uasset`。

## 架构与职责

### `AFutsalPlayerBase`

继续拥有 Sequencer 输入 `ExternalMotionActive`、`ExternalMotionSpeedMps` 和只读 CharacterMovement 水平速度辅助函数。保留已实现、已测试的 `SelectEffectiveMotionSpeedMps`：外部运动激活时返回外部速度，否则透传旧 Auto Motion/显式回退选择值。此选择逻辑不引入 CharacterMovement 优先级。

### `UFutsalPlayerAnimInstance`

新增原生 AnimInstance 子类，承担初始化缓存和与旧 EventGraph 对应的逐帧数据计算。缓存 Character/玩家引用和 CharacterMovement 引用，初始化上一帧位置及初始化状态；在每次更新中维持转录规定的 Then 0→Then 1→Then 2→Then 3 依赖次序，发布蓝图状态机继续使用的动画变量。

Character 缓存需兼容泛型 `ACharacter` 父类行为；只有当 Owner 是 `AFutsalPlayerBase` 时才读取外部运动属性。Owner 或 MovementComponent 无效时采用显式零值/安全默认值，并避免解引用空对象。

### 规范 AnimBP

`ABP_FutsalPlayerBase` 继续作为 AnimBP 资产和 Pose 组装图。将其父 AnimInstance 类切换到 `UFutsalPlayerAnimInstance`，删除/迁移与继承 C++ 动画属性重名的蓝图变量，并将 EventGraph 更新职责退役。AnimGraph、两套状态机、缓存 Pose、BlendSpace Player、动画 Sequence Player、Slot 和 FootIK ControlRig 保持原样。

当前 MCP 对该 AnimBP 的图表/DSL 读回不完整，禁止通过空 DSL 重建或整体覆写 EventGraph/AnimGraph。任何资产修改必须在 UE Editor 内由原生 API 执行，并在每次保存前后核对图表数量、状态机拓扑、资源引用和编译结果。若无法安全地做局部变量迁移或父类切换，则停在明确的手动 ABP 门槛，不保存部分迁移资产。

## 数据契约

原生 AnimInstance 至少发布以下与现有状态机及 Pose 图绑定的字段：

- `Velocity`：按人工转录选择 Auto Motion Velocity 或 MovementComponent.Velocity；主状态机 Jump 条件继续使用 `Velocity.Z > 100.0`。
- `GroundSpeed`：`EffectiveMotionSpeedMps * 100.0`，单位为 cm/s，供原 BlendSpace Speed 轴使用。
- `Direction`：由 `EffectiveVelocity` 和 Character Actor Rotation 经 `CalculateDirection` 得出；当 `OrientRotationToMovement` 为真时 Clamp 到 `[-45, 45]`，否则使用未 Clamp 值。
- `ShouldMove`：严格复现截图转录中两个子表达式都连接 `GetCurrentAcceleration()` 的历史逻辑；不把其中任何一路替换为 Velocity，不做布尔简化。
- `IsFalling`：来自 CharacterMovement。
- 外部速度、Auto Motion 速度/速度向量、有效速度/速度向量、上一帧位置、初始化标记及 Auto Facing Yaw（如经资产引用核验仍需保留）。

逐帧语义遵守人工转录：`DeltaTimeX > 0.0001` 时计算 Transform 差分速度并更新上一帧位置；小于等于阈值时不添加转录中没有的更新路径；未初始化路径设置当前位置、零 AutoMotionVelocity、标记初始化，但不凭空写 AutoMotionSpeedMps。旧速度选择先计算 `UseAutoMotionSpeed ? AutoMotionSpeedMps : MotionSpeedMps`，再由激活的外部运动速度覆盖。`GetMotionSpeedMps` 当前为零值 Stub，不把它当成外部速度生产器。

## 状态机及内容资产

以下继续由现有蓝图状态机执行，C++ 仅更新它们消费的数据：

- Locomotion：Idle 在 `ShouldMove` 时进入 Walk/Run；Walk/Run 在 `!ShouldMove` 时返回 Idle。
- Walk/Run 继续使用 `BS_FutsalPlayerBase_Locomotion`，Direction 和 GroundSpeed 输入不变。
- Main States 的 Locomotion 继续消费缓存 Pose `Locomotion`。
- To Falling 至 Jump 使用 `IsFalling && Velocity.Z > 100.0`；至 Fall Loop 使用 `IsFalling`。
- Jump 至 Fall Loop 保留 Automatic Rule Based on Sequence Player。
- To Land 至 Land 使用 `!IsFalling`。
- Land 至 Locomotion 的历史截图有自动序列完成规则与常量 False 重复转换两种竞争重建状态。由于本阶段不重写/整理状态机，不需据此推断或更改当前活动箭头；记录为既有资产的不确定项。
- Jump/Fall/Land 序列、Blend Duration/Curve、Conduit、Entry State 配置、DefaultSlot 和 FootIK 路径保持不变。

## 资产迁移策略

先保存规范 ABP 的可恢复副本，并记录父类、蓝图变量名/类型/默认值、EventGraph 与 AnimGraph 结构、状态机和转换图、Pose 节点资源引用及编译状态。当前 ABP 文件在工作区显示为 994 字节修改，视为既有用户/Editor 修改；不得重置、覆盖或将其纳入本次实现暂存。编辑前需检查它相对索引版本的差异并确认恢复副本包含当前磁盘版本。

先实现并编译 C++ AnimInstance、自动化测试和数据契约；再在同一 Editor 会话中将原规范 ABP 局部切换到新父类并接收继承变量，移除冗余 EventGraph 更新节点。逐项核对仍被状态机/BlendSpace 引用的变量。保留没有经证据证明可删除的 `CurrentAnimationClass`、`Velocity_0` 等历史字段，不能推断它们无用。局部编辑、编译或保存任一步失败时，不保存部分结果，恢复备份并停止。

在变量接线、父类切换和编译验证通过之前，不将 Court 角色的 AnimClass 改到其他资产，不改 Sequence 绑定。完成后规范 ABP 路径不变，角色仍通过原路径使用它。

## 验证与验收

### 自动化

- UE 5.8 Editor target 构建成功；原生 Character 与新 AnimInstance 测试通过。
- 覆盖初始化、无 Owner/无 MovementComponent、安全默认、DeltaTime 边界、XY 速度单位换算、有效速度源选择、ShouldMove 转录语义、方向 Clamp、Falling 读取和 `GroundSpeed = m/s * 100`。
- 验证外部速度不会修改 Actor Transform、CharacterMovement 速度或 Root Motion。
- 编译原生 AnimInstance、规范 BP Character 和规范 ABP；无新增 Blueprint/AnimGraph 编译错误或未解析变量。
- Python 数据集仓库保持不变；官方 smoke Sequence 的十个玩家仍含 Transform、`ExternalMotionActive`、`ExternalMotionSpeedMps` 轨道，球与相机绑定不变。

### 运行时

- 对静止、普通移动、ExternalMotionActive 移动及空中状态检查运行时动画变量。
- 地面 Sequence 运动保持 Locomotion 主状态；ShouldMove 在 Idle 与 Walk/Run 间按既有规则切换，不意外进入 Jump/Fall/Land。
- 用人工核验的历史规则观察 Jump、Fall Loop、Land 转换；Land 返回 Locomotion 沿用已保存的现有蓝图状态机行为，不在本阶段修正截图中的重复转换歧义。
- 对代表帧核对 tracker 速度、Sequence 外部速度、`GroundSpeed` cm/s、Velocity/Direction 和 Actor Transform。外部速度只改变动画幅度，不成为世界运动输入。
- 人工视觉检查静止 Idle、移动 BlendSpace Cadence、跳跃/跌落/着地及 FootIK 输出。不得以数据变量测试代替最终视觉检查。

### 源代码管理

- 修改只属于外层 UE 仓库，不进入内层 Python submodule。
- 不自动提交或推送；完成后先报告差异与验证结果，提交需用户单独明确确认。
- 不使用 `git add -A`；已有 staged 清单与本轮 unstaged C++ 变更分开保留。

## 已知限制与待确认门槛

- MCP/DSL 对规范 ABP 的图内容读回为空，不能作为图表迁移证据；依赖用户提供的两份截图转录与 UE Editor 资产核对。
- Land→Locomotion 活动重复转换的历史状态不确定。本阶段保留状态机，不更改该转换；若未来迁移状态机本身，需先在实时 UI 核验当前活动规则。
- 当前工作区 ABP 文件存在 994 字节差异，原因尚未由日志确定。必须先以当前文件建立独立备份并审阅差异；任何无法解释的结构损坏或编译错误都是停止门槛。
- 本阶段的“C++ 完全迁移”仅指 AnimBP EventGraph 的初始化和动画数据更新职责；AnimGraph/状态机/Pose 资产继续保留为蓝图，符合本阶段经确认的迁移边界。
