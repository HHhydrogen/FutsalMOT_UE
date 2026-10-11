# Player_003 数据集生产替换设计

## 目标

让正式场地 `L_FutsalCourt` 中的十名默认球员统一使用 MPFB Player_003，并通过现有 GRF → UE → RGB/Mask/Runtime Pose → P1 后处理和 Audit 链路验证其可用于数据集生产。保持现有实体身份、场地布局和数据契约；验证通过后允许将更多共享 MPFB Core Skeleton 的角色按实体分配，以扩展数据集外观多样性。

## 当前基线

- 正式地图：`/Game/FutsalMOT/Maps/L_FutsalCourt`。
- 十个现有 Character Actor 标签：`Player_L0..Player_L4`、`Player_R0..Player_R4`。
- 对应 Pose Actor Tags：`PoseL0..PoseL4`、`PoseR0..PoseR4`。
- Actor Mapping、轨迹实体 ID 和 Mask ID 保持现状；球 `Ball_01` 不变。
- 现有可见组件为 `CharacterMesh0`，默认网格为 `SKM_FutsalPlayerBase`，默认 AnimBP 为 `ABP_FutsalPlayerBase_C`。
- Player_003：`/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003`，共享 Skeleton 为 `/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base`。
- Player_003 Runtime AnimBP：`/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget`。
- 当前 Actor 胶囊 half-height 为 `88 cm`；Player_003 静态网格 bounds 高度约 `179 cm`。正式标注配置使用 Capsule bbox，因此网格替换不应隐式改变 bbox 来源或比例。
- 正式 UE 数据入口为内层 `ue/run_task.py --mode full`；MRQ 异步结束后按需运行 `--mode pose-finalize`。P1 执行 postprocess、audit 和 manifest。

## 方案

### 角色视觉 Profile

扩展现有单文件 task 的 `ue` 配置，增加可选 `player_visuals` 对象：

- `default_profile` 指定未显式映射实体时的角色 Profile。
- `profiles` 以稳定 ID 为键，描述 Skeletal Mesh、Runtime AnimBP 和预期共享 Skeleton 路径。
- `entity_profiles` 把 `L0..L4`、`R0..R4` 映射到 Profile ID。
- 首个 profile `mpfb_player_003` 指向正式 Player_003、`ABP_MPFB_RuntimeRetarget` 和 `SKEL_MPFB_Base`；初始十个实体全部指定该 profile。
- 缺少 `player_visuals` 时不改变现有任务行为；提供该配置但引用无效时 fail-fast，不静默回退。

后续增加角色只需新增 Profile 并调整 `entity_profiles`，不改变 Actor 标签、轨迹 ID、Sequence 结构或 Pose Recorder。

### UE 应用、恢复与 preflight

在内层 `ue/` 增加独立工具模块，提供三种明确模式：

- `apply`：只接受当前地图为 `L_FutsalCourt`；按现有 actor mapping 精确找到十个 Actor，先完整预检，再逐一修改 `CharacterMesh0` 的 Skeletal Mesh 和 Anim Class。保留 Actor 实例、名称、标签、Pose tags、Transform、胶囊体、其它组件、碰撞设置、网格相对变换和 Sequencer possessable 身份。修改前将原 mesh、anim class、skeleton 及关键身份字段写入 task runtime 目录的 rollback JSON；完成后保存受影响的 External Actor 包。
- `restore`：读取对应 rollback JSON，仅恢复脚本管理的 mesh/anim class 字段；不恢复或覆盖 Actor 的 Transform、标签、其它组件以及之后的用户编辑。恢复后保存 External Actor 包。
- `preflight`：只读验证地图、角色数量和唯一性、mapping 完整性、组件数量、指定 mesh/skeleton/AnimBP、Pose tags、capsule bbox 策略和 Runtime Pose Recorder actor/tag 覆盖。任何硬错误阻止 Sequence 创建或 MRQ 提交。

工具均输出结构化 JSON，包括修改/验证的 Actor、Profile、资产路径、保存状态、rollback 文件路径和错误列表。脚本不得猜测骨骼或 UE 属性；遇到不支持或不匹配的配置立即失败。

### `run_task.py` 集成与 provenance

- `full` 和 `render` 在提交 Sequence/MRQ 前读取 `ue_profile.player_visuals` 并执行 preflight。
- `full` 在创建 Sequence 前应用配置。`render` 只验证已应用的状态，不隐式改写场景，避免渲染既有数据时发生意外资产修改。
- `sequence` 模式可显式执行角色应用与 Sequence 创建；不执行渲染。
- 未配置 `player_visuals` 的旧任务保持兼容。
- episode 的 `provenance/` 写入去机器路径的角色 Profile 摘要：每个实体的 Profile ID、Mesh、Skeleton、AnimBP，以及角色配置 fingerprint。它不包含本地 rollback 路径或机器绝对路径。
- 角色 `preflight` 失败时，不创建/替换 Sequence、不提交 MRQ、不覆盖已有的有效输出。

## 数据生成阶段

### 阶段 A：Player_003 smoke

新增独立 task 配置，固定唯一 `task_id` 和新的 episode 名，避免复用或覆盖现有 smoke/production episode。使用 1 个已验证相机、10 帧、固定 seed、RGB、Object-ID Mask、Runtime Pose、MOT/YOLO Detect/Segment 和完整验证。执行顺序：

1. 静态校验 task 和路径，确认数据集 episode 输出目录不存在或为空。
2. 导出 GRF episode 并验证轨迹契约。
3. 在正式地图应用 Player_003 Profile，运行只读 preflight。
4. 在 UE 执行 `run_task.py --mode full`，保持 Editor tick 直至 MRQ 完成。
5. 检查 `render_summary.json`，确认 RGB、Object-ID EXR 和期望帧数齐全；运行 `--mode pose-finalize`，确认 5 个 Recorder slot 捕获完整。
6. 执行 P1 postprocess、annotation/Pose validate、quick audit 和 manifest。
7. 视觉检查 RGB、Mask/实例 ID、COCO17 overlay、角色边界和关键点与 Player_003 身体部位的一致性。

Smoke 通过门槛：所有必需帧/相机产物齐全；Mask 只含背景 `0` 与实体 `1..11`；MOT/YOLO/Pose frame 集合与 RGB 对齐；Runtime Pose session 完整；Audit `passed=true`；无 Python、Blueprint、MRQ 或 Recorder 错误。脸部点和可见性结果需以 overlay/验证数据人工检查，不因静态测试自动宣称准确。

### 阶段 B：正式 Player_003 episode

Smoke 通过后新增独立生产 task 配置，不覆盖现有 `production_900frames_30fps_4cam.json`。沿用已验证生产参数：900 帧、30 FPS、四个配置相机、固定 seed 和 mask/Pose 契约；使用独立 `task_id`、`episode_name` 和输出目录。执行完整 P1/P2/postprocess/audit/manifest 流程。只有 Audit 通过、manifest 可验证、四相机帧集合一致后，才将这次 Profile 视为生产验证成功。

## 回退、失败与数据保护

- 应用前检查正式地图与十个 Actor 的现状，记录原 Mesh、AnimBP、Skeleton、标签、Transform、组件相对变换和角色数；不重置任何现有用户修改。
- rollback 只恢复脚本管理的 Mesh 和 Anim Class；任何保存失败或部分应用失败都停止后续数据生成，并尝试仅恢复已变更 Actor 的上述字段。
- MRQ 是异步任务；提交后不阻塞 Editor 主线程，不在 MRQ 未结束时启动 postprocess 或下一次渲染。
- Smoke 或正式任务失败时保留完整日志和失败产物供诊断，不运行 `cleanup --apply`，不覆盖已通过 Audit 的 episode。
- 只有用户明确要求时才执行 Git commit/push。Python 改动先在内层仓库独立验证与提交；UE 资产如需提交，再分别审查外层工作区并确认 gitlink/资产范围。
- 当前工作区已有未提交 UE 改动。实施前逐项确认将触及的 External Actor/资产状态；只保存 Player Actor 实际修改包，不对其它 dirty 资产执行 save-all、清理或回滚。

## 测试与验收

- P1 单元测试覆盖 Profile schema/解析、实体到 Profile 展开、缺字段兼容、无效资产 fail-fast、canonical fingerprint 去路径和 provenance 输出。
- UE Python 测试/诊断覆盖 preflight 只读性、十个 Actor 精确匹配、共享 Skeleton 和 AnimBP 校验、rollback/restore 字段范围及保存结果。
- 当前正式地图中十个 Actor 的 mesh 都是 Player_003，Anim Class 都是 `ABP_MPFB_RuntimeRetarget_C`；十个 Actor 保持原标签、Pose tags、Transform、胶囊体和组件结构。
- smoke 和正式 episode 分别达到各自的产物、对齐、Pose、Mask、Audit 与 manifest 门槛。
- 多角色扩展验收以 Profile mapping 中至少两个角色能在不改 Actor/data contract 的条件下被 preflight 识别为目标；在实际导入更多角色前，不声称该扩展已完成。

## 停止条件

- 正式地图无法加载，或角色 mapping 不是唯一的十名球员。
- Player_003 Skeleton 与共享 MPFB Skeleton 不一致，Runtime AnimBP 无法用于该 Mesh，或 UE Blueprint/AnimBP 编译失败。
- Runtime Pose Recorder 找不到角色或骨骼映射不能满足其采样契约。
- UE 保存影响超出被授权的角色 External Actor 包，或 rollback 快照无法完整写出。
- Smoke 出现缺帧、无效 Mask ID、Runtime Pose 不完整、相机标定不匹配或 Audit failure。
- 同一 UE Python/MCP 操作连续失败两次；停止自动化并按项目 SOP 标记 `MANUAL_REQUIRED`。
