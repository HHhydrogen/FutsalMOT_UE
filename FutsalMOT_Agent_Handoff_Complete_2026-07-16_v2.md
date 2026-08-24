# FutsalMOT Unreal Engine 合成数据集项目：Agent 完整交接文档

> **更新时间：2026-07-16**  
> **用途：** 将本文直接交给新的 AI Agent。Agent 必须先完整阅读，再修改任何代码。  
> **当前主线：** 路线 A——基于规则与事件的长时间五人制足球比赛回合生成。  
> **后续扩展：** 路线 D——Learning Agents / 强化学习 / 模仿学习；路线 E——Motion Matching。

---

## 0. 交接摘要

本项目正在构建一个基于 Unreal Engine 的五人制足球多视角合成数据集生成系统，服务于：

- 多视角目标检测；
- 多目标跟踪（MOT）；
- 跨相机身份关联；
- 球场坐标定位；
- 球员动作识别；
- 比赛事件检测；
- 持球权与球员交互关系建模。

当前已跑通或实现的主链路为：

```text
球场与固定相机
→ 外部 JSON 序列配置
→ 稀疏多关键帧轨迹
→ 轨迹验证
→ 离线平滑逐帧轨迹
→ 比赛事件配置
→ 事件语义验证
→ 事件编译为逐帧球员/足球轨迹
→ 逐帧 yaw、动作时间轴、足球状态和触球帧
→ Unreal Engine Sequencer
→ 多视角 RGB
→ tight bbox JSON / JSONL
→ YOLO / MOT
→ overlay 可视化
→ 完整性检查
```

当前最新阶段为 **A3.3b：根据 `action_timeline` 在 UE Sequencer 中创建分段动画 Section**。

A3.3b 的代码已经生成；动画资源扫描器 V2 已在用户的 UE 项目中成功运行。扫描确认：

```text
动画类资源总数：104
可直接放入 Sequencer 动画 Section：100
Idle 候选：11
Jog 候选：25
Dribble / Pass / Receive / Shot / Defend 专项动画：0
```

因此当前只能使用：

```text
Idle → MM_Idle
Jog  → MF_Unarmed_Jog_Fwd
其他动作 → 暂时降级为 Jog
```

**尚未完成的最近任务：**

1. 将已生成的 `action_animation_map_ready.json` 放入项目并重命名为 `action_animation_map.json`；
2. 在 UE 中运行 `01_ue_build_episode_from_config_A3_3B.py`；
3. 验证各球员的动画 Section、Transform/yaw、bbox 与 Camera Cuts；
4. 使用 Idle/Jog fallback 先完成 A3.3b 管线验收；
5. 完成事件级标注和批量长回合生成；
6. 足球专项动作可从 Unreal Fab 获取，但相关资产需要资金购买，必须先与导师讨论并获得预算决定，因此该项目前暂时搁置，不作为当前阻塞任务。

---

# 1. 项目基本信息

## 1.1 项目路径

Unreal Engine 项目根目录：

```text
D:/projects/FustalMOT_UEDataset
```

代码目录：

```text
D:/projects/FustalMOT_UEDataset/Content/FutsalMOT/code
```

数据输出目录：

```text
D:/projects/FustalMOT_UEDataset/Saved/FutsalMOT
```

## 1.2 球场坐标系统

UE 单位统一为厘米：

```text
1 m = 100 cm
```

标准五人制足球场：

```text
40 m × 20 m
```

世界坐标约定：

```text
球场中心：(0, 0, 0)
X：球场长边方向
Y：球场短边方向
Z：竖直方向

物理边界：
X ∈ [-2000, 2000] cm
Y ∈ [-1000, 1000] cm
```

轨迹安全验证通常使用留边范围：

```text
X ∈ [-1950, 1950] cm
Y ∈ [-950, 950] cm
```

## 1.3 固定相机

当前使用 4 个固定 CineCamera：

```text
cam_01 → CineCam_01
cam_02 → CineCam_02
cam_03 → CineCam_03
cam_04 → CineCam_04
```

图像分辨率：

```text
1920 × 1080
```

## 1.4 动态对象

```text
Player_01
Player_02
Player_03
Player_04
Ball_01
```

类别与 Track ID：

```text
player class_id = 0
ball   class_id = 1

Player_01 track_id = 1
Player_02 track_id = 2
Player_03 track_id = 3
Player_04 track_id = 4
Ball_01   track_id = 101
```

## 1.5 球场关键点

已确认球场关键点总数为 **41 个**，不是 45 个：

```text
kp  = 18
kpe = 6
kp1 = 4
kp2 = 4
kp3 = 9
总计 = 41
```

早期已完成：

- 41 个场地点世界坐标规范化；
- UE 中自动生成关键点 Actor；
- 4 个固定相机下的 2D 投影；
- overlay 检查；
- 相机参数导出。

---

# 2. 项目技术架构

## 2.1 当前核心分层

### 语义层

```text
episode_test_0001.json
```

描述：

- 球员；
- 初始位置；
- 球权；
- dribble；
- move；
- pass；
- receive；
- defend_follow；
- shot。

### 轨迹层

事件编译器将语义事件转换为：

```text
每个对象每帧的 loc
每个球员每帧的 yaw_deg
球员 action_timeline
足球 state_timeline
possession_timeline
event_frame_map
contact_frames
```

### Unreal Engine 渲染层

UE 脚本负责：

- 找到球员、足球、相机 Actor；
- 创建或更新 Level Sequence；
- 写入逐帧 Transform；
- 写入动画轨道和分段 Section；
- 自动扩展 Camera Cuts；
- 逐相机逐帧导出 2D bbox；
- 写 JSON / JSONL。

### Windows 后处理层

`02_win_overlay_convert_check.py` 负责：

- 读取标注元数据；
- 生成 bbox overlay；
- 转换 YOLO 标签；
- 转换 MOT 标签；
- 生成 manifest；
- 检查帧数、相机数、对象数和标签完整性。

## 2.2 关键设计原则

1. **UE 运动和标注必须读取同一份逐帧轨迹。**
2. 不依赖 UE 自动曲线插值作为标注真值。
3. 事件语义和轨迹数据分离。
4. 稀疏配置保留，逐帧配置由生成器产生。
5. 所有脚本使用版本化文件名，禁止直接覆盖稳定基线。
6. 所有生成过程应可复现，后续必须加入随机种子。
7. 警告和错误必须区分，不能用“看起来正常”代替验证。
8. 没有 UE 实际运行日志时，不得声称 UE 运行成功。

---

# 3. 已完成工作：按阶段整理

# 3.1 早期 UE 场景与短序列闭环

已完成：

- 标准五人制足球场；
- 41 个球场关键点；
- 4 个固定相机；
- 4 名球员；
- 1 个足球；
- Sequencer 控制对象轨迹；
- 多相机 RGB；
- 球场关键点投影；
- 球员/足球 bbox；
- YOLO/MOT；
- overlay；
- 完整性检查。

解决过的重要问题：

### Control Rig 覆盖动画

原问题：

```text
球员 Transform 在移动，但姿态不播放或仅滑行。
```

原因：

```text
CR_Mannequin_Body / Control Rig 轨道覆盖 Skeletal Animation Track。
```

解决：

- 删除或清理 Control Rig 轨道；
- 在球员 Mesh 上使用 Skeletal Animation Track；
- Transform Track 控制世界位置；
- Animation Track 控制动作。

稳定 Jog 资源：

```text
/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd
```

### 球员朝向

早期使用起点到终点的方向：

```text
yaw = atan2(dy, dx)
```

并保留：

```python
PLAYER_FORWARD_CORRECTION_DEG
```

用于修正模型前向轴。

### 足球 Transform

曾出现足球不移动或位置不正确，已通过统一写入足球 Transform Track 解决。

---

# 3.2 稳定基线：seq_test_0003

序列：

```text
seq_id = seq_test_0003
frame 0–9
30 fps
4 cameras
5 objects
```

规模：

```text
10 帧 × 4 相机 = 40 个相机帧记录
```

旧稳定 UE 脚本：

```text
01_ue_build_seq_and_export_annotations.py
```

作用：

- 硬编码相机；
- 硬编码对象；
- 硬编码起止轨迹；
- 创建 Sequencer；
- 导出 bbox。

该脚本只作为最基础回退基线，不再作为主开发文件。

---

# 3.3 A1：外部 JSON 配置驱动

完成内容：

```text
01_ue_build_from_config_and_export_annotations.py
configs/seq_test_0003.json
```

目标：

- 将 seq_id、时间轴、相机、对象、轨迹、类别、Track ID 等从脚本移出；
- UE 脚本从 JSON 读取；
- 保留原稳定脚本。

状态：

```text
用户确认成功
```

---

# 3.4 A1.5：通用 Windows 后处理

最终主脚本：

```text
02_win_overlay_convert_check.py
```

历史版本：

```text
02_win_overlay_convert_check_A1_5.py
```

完成内容：

- 自动读取 `seq_id`；
- 自动读取帧范围；
- 自动读取图像尺寸；
- 自动读取 camera IDs；
- 自动读取 object IDs；
- 自动读取 class_id_map；
- 自动读取 track_id_map；
- `expected_objects_per_record = len(OBJECT_IDS)`；
- MOT 帧号改为序列内相对帧号；
- 自动清理旧输出；
- 生成 overlay / YOLO / MOT / manifest；
- 完整性检查。

状态：

```text
用户确认成功
```

---

# 3.5 A2：多关键帧轨迹

序列：

```text
seq_id = seq_test_0004
frame 0–149
30 fps
5 秒
4 cameras
5 objects
```

配置：

```text
configs/seq_test_0004.json
```

每个对象由原来的：

```text
start / end
```

升级为：

```text
keyframes[]
```

典型控制帧：

```text
0, 30, 60, 90, 120, 149
```

对应脚本：

```text
01_ue_build_from_config_and_export_annotations_A2.py
```

版本标记：

```text
A2_MULTI_KEYFRAME_LINEAR_V1
```

解决的问题：

- 旧 A1 脚本仍读取 `objects.<id>.start` 导致报错；
- 使用独立版本名避免同名旧文件被误运行。

Camera Cuts 曾仍为 0–10，导致 MRQ 只渲染 10 帧。之后修复为自动扩展：

```text
[frame_start, frame_end + 1)
```

状态：

```text
用户完成 150 帧多关键帧序列并成功渲染
```

规模：

```text
150 帧 × 4 相机 = 600 张图 / 600 条相机帧记录
```

---

# 3.6 A2.2：tight bbox 修正

脚本：

```text
01_ue_build_from_config_and_export_annotations_A2_2.py
```

版本：

```text
A2_2_MULTI_KEYFRAME_SAFE_BBOX_CAMERA_CUT_V1
```

原问题：

- 仅投影骨骼中心点；
- 头顶、手臂、手、腿、鞋可能落在框外；
- 或使用简单 extent 后框偏松。

修正方式：

- 对每个重要骨骼定义人体轮廓近似半径；
- 将骨骼视为面向相机的圆形包络；
- 投影包络而不仅是骨骼中心；
- 增加手指、鞋、头部等骨骼；
- 支持固定 padding；
- 支持按框尺寸的自适应 padding；
- 支持 bone radius scale；
- 支持评估 Sequence 当前姿态；
- 自动修正 Camera Cuts。

bbox 来源：

```text
player：player_bone_envelope_2d
ball：manual_ball_radius
```

支持的主要参数：

```json
{
  "bbox_padding_px": "...",
  "bbox_adaptive_padding_ratio": "...",
  "bbox_bone_radius_scale": "...",
  "bbox_default_bone_radius_cm": "...",
  "bbox_evaluate_sequence_pose": true
}
```

用户已手动调节到“框合适”。

**重要：**

```text
Agent 不得擅自覆盖用户当前本地配置中的 bbox 参数。
本地正在使用的配置是 bbox 参数的最终事实来源。
```

---

# 3.7 A2.5a：轨迹合法性验证器

脚本：

```text
00_validate_trajectory_config.py
```

版本：

```text
A2_5A_TRAJECTORY_VALIDATOR_V1
```

检查内容：

- 时间轴；
- keyframe 类型；
- 关键帧严格递增；
- 重复帧；
- 首末覆盖；
- 球场边界；
- 轨迹段距离；
- 水平速度；
- 垂直速度；
- 相邻速度跳变；
- 转向角；
- 球员间最小距离；
- track/class ID；
- legacy start/end；
- PASS / WARNING / ERROR；
- 返回码。

输出：

```text
Saved/FutsalMOT/trajectory_reports/
├─ trajectory_report_<seq_id>.json
└─ trajectory_segments_<seq_id>.csv
```

默认阈值包含：

```text
player warning speed = 500 cm/s
player max speed = 750 cm/s
ball warning speed = 1800 cm/s
ball max speed = 3000 cm/s
```

`seq_test_0004` 测试结果：

```text
5 objects
25 segments
PASS
warnings = 0
errors = 0
```

---

# 3.8 A2.5b：离线平滑逐帧轨迹

脚本：

```text
00_generate_smoothed_trajectory.py
```

版本：

```text
A2_5B_PCHIP_DENSE_TRAJECTORY_V1
```

输入：

```text
configs/seq_test_0004.json
```

输出：

```text
configs/seq_test_0005.json
```

方法：

```text
shape-preserving cubic Hermite / PCHIP
```

设计：

- 保留所有原始控制点；
- 每帧生成一个 keyframe；
- 每个坐标分量在相邻控制点间避免普通三次曲线过冲；
- 输出对象仍设为 `interpolation = linear`；
- UE 和标注读取完全相同的逐帧坐标；
- 自动调用轨迹验证器。

`seq_test_0005`：

```text
frame 0–149
每个对象 150 keyframes
5 objects
745 segments
```

---

# 3.9 A3.1：比赛事件配置和事件验证器

事件配置：

```text
configs/events/episode_test_0001.json
```

事件验证器：

```text
00_validate_episode_config.py
```

版本：

```text
A3_1_EPISODE_VALIDATOR_V1
```

回合：

```text
episode_id = episode_test_0001
10 秒
30 fps
frame 0–299
4 players
1 ball
11 events
```

支持的事件：

```text
hold
move
dribble
pass
receive
defend_follow
shot
```

当前事件流程：

```text
Player_01 带球
Player_02 支援跑位
Player_03 跟防持球队员
Player_04 防守移动
Player_01 → Player_02 传球
Player_02 接球
Player_02 带球推进
Player_02 射门
射门后球员继续移动
```

重要事件帧：

```text
传球开始：frame 75
接球：frame 96
射门开始：frame 165
```

验证器检查：

- 时间范围；
- 秒到帧换算；
- Actor / from / to；
- 事件重叠；
- 传球和接球匹配；
- 持球权连续性；
- 射门者是否拥有球；
- 目标坐标；
- 初步速度；
- Track ID；
- PASS / WARNING / ERROR。

测试结果：

```text
PLAYERS = 4
EVENTS = 11
STATUS = PASS
warnings = 0
errors = 0
```

输出：

```text
Saved/FutsalMOT/episode_reports/
├─ episode_report_episode_test_0001.json
└─ episode_timeline_episode_test_0001.csv
```

---

# 3.10 A3.2：事件编译为逐帧轨迹

脚本：

```text
00_generate_episode_trajectories.py
```

版本：

```text
A3_2_EVENT_TO_DENSE_TRAJECTORY_V1
```

输入：

```text
configs/events/episode_test_0001.json
configs/seq_test_0005.json
```

输出：

```text
configs/generated/episode_test_0001.json
```

实现：

- `move`：平滑启停；
- `dribble`：球员移动，球位于脚前；
- `pass`：传球者脚前到接球者脚前；
- `receive`：切换球权；
- `shot`：到射门目标；
- `defend_follow`：动态追踪当前持球队员；
- `hold`；
- 每个对象生成 300 个逐帧关键帧；
- 保留基础渲染配置中的相机、动画、bbox 等设置；
- 自动调用事件验证器和轨迹验证器。

编译结果：

```text
Player_01 = 300 keyframes
Player_02 = 300 keyframes
Player_03 = 300 keyframes
Player_04 = 300 keyframes
Ball_01   = 300 keyframes
```

持球权：

```text
frame 0–74：Player_01 owned
frame 75–95：in_transit
frame 96–164：Player_02 owned
frame 165–299：shot
```

测试最大速度：

```text
Player_01：305.923 cm/s
Player_02：330.211 cm/s
Player_03：450.000 cm/s
Player_04：30.696 cm/s
Ball_01：2692.990 cm/s
```

均未超过最大限制。

轨迹规模：

```text
5 objects × 299 segments = 1495 segments
```

---

# 3.11 A3.3：逐帧 yaw、动作语义和足球状态

脚本：

```text
00_generate_episode_trajectories_A3_3.py
```

版本：

```text
A3_3_ACTION_YAW_BALL_SYNC_V1
```

输出：

```text
configs/generated/episode_test_0001_A3_3.json
```

新增内容：

## 每帧球员 yaw

```json
{
  "frame": 75,
  "loc": [-100.0, -80.0, 90.0],
  "yaw_deg": 17.842
}
```

规则：

- 普通移动朝运动方向；
- 低速时保持上一朝向；
- 最大转向速度限制；
- 传球前提前朝向接球者；
- 接球前面向来球；
- 射门前朝向射门目标；
- 防守者面向持球队员、足球或预期接球者。

## action_timeline

Player_01：

```text
0–69：dribble
70–95：pass
96–299：jog
```

Player_02：

```text
0–90：jog
91–96：receive
97–159：dribble
160–185：shot
186–299：jog
```

Player_03：

```text
0–164：defend
165–299：jog
```

Player_04：

```text
0–299：jog
```

## 足球 state_timeline

```text
0–74：controlled / Player_01
75–95：pass
96–164：controlled / Player_02
165–299：shot
```

## 触球帧

```text
frame 75：Player_01 pass contact
frame 96：Player_02 receive contact
frame 165：Player_02 shot contact
```

## 带球视觉扰动

足球带球阶段加入小幅：

- 前后变化；
- 左右变化；
- 上下轻微弹跳；
- 事件边界自动衰减到零。

A3.3 测试结果：

```text
seq_id = episode_test_0001_A3_3
frame 0–299
每个对象 300 keyframes
trajectory errors = 0
```

---

# 3.12 A3.3b：UE 动作动画 Section

代码包：

```text
A3_3B_action_animation_code.zip
```

主 UE 脚本：

```text
01_ue_build_episode_from_config_A3_3B.py
```

版本：

```text
A3_3B_ACTION_TIMELINE_ANIMATION_SECTIONS_V1
```

功能：

- 基于稳定 A2.2 UE 脚本；
- 读取 `episode_test_0001_A3_3.json`；
- 读取每个球员的 `action_timeline`；
- 合并相邻相同动作区间；
- 为每个 Mesh 创建一条 Skeletal Animation Track；
- 为不同动作创建连续 Section；
- 动画缺失时降级；
- 保留 Transform/yaw；
- 保留 safe bbox；
- 保留 Camera Cuts；
- 标注记录增加 `action` 和 `action_source_events`。

默认输入：

```text
configs/generated/episode_test_0001_A3_3.json
```

动画映射：

```text
configs/action_animation_map.json
```

动画资源扫描器：

```text
00_ue_list_action_animation_assets_V2.py
```

版本：

```text
A3_3B_ACTION_ANIMATION_ASSET_SCANNER_V2
```

V1 扫描器存在 SoftObjectPath 字符串问题，已废弃：

```text
00_ue_list_action_animation_assets.py
```

V2 已在用户 UE 中成功运行，结果：

```text
All animation-like assets = 104
Direct section compatible = 100
idle candidates = 11
jog candidates = 25
dribble/pass/receive/shot/defend = 0
```

确认可用 Idle：

```text
/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle
```

推荐 Jog：

```text
/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd
```

已生成可直接使用的映射：

```text
action_animation_map_ready.json
```

内容逻辑：

```text
idle → MM_Idle
jog → MF_Unarmed_Jog_Fwd
dribble/pass/receive/shot/defend → null
strict_action_assets = false
fallback_action = jog
```

**当前验证状态：**

```text
V2 动画扫描：用户 UE 实际验证成功
A3.3b 脚本：已生成并完成 Python 语法层检查
A3.3b 在用户 UE 中完整构建：尚未确认
专项足球动作：项目中尚不存在
```

---

# 4. 当前推荐目录结构

```text
D:/projects/FustalMOT_UEDataset/
├─ Content/
│  └─ FutsalMOT/
│     └─ code/
│        ├─ 00_validate_trajectory_config.py
│        ├─ 00_generate_smoothed_trajectory.py
│        ├─ 00_validate_episode_config.py
│        ├─ 00_generate_episode_trajectories.py
│        ├─ 00_generate_episode_trajectories_A3_3.py
│        ├─ 00_ue_list_action_animation_assets_V2.py
│        ├─ 01_ue_build_seq_and_export_annotations.py
│        ├─ 01_ue_build_from_config_and_export_annotations_A2_2.py
│        ├─ 01_ue_build_episode_from_config_A3_3B.py
│        ├─ 02_win_overlay_convert_check.py
│        └─ configs/
│           ├─ seq_test_0003.json
│           ├─ seq_test_0004.json
│           ├─ seq_test_0005.json
│           ├─ action_animation_map.json
│           ├─ events/
│           │  └─ episode_test_0001.json
│           └─ generated/
│              ├─ episode_test_0001.json
│              └─ episode_test_0001_A3_3.json
└─ Saved/
   └─ FutsalMOT/
      ├─ annotations/
      ├─ images_clean/
      ├─ overlay_objects_bbox_*/
      ├─ labels_yolo_clean/
      ├─ labels_mot_clean/
      ├─ trajectory_reports/
      ├─ episode_reports/
      └─ animation_assets/
```

---

# 5. 文件清单与使用优先级

## 5.1 当前应使用

| 文件 | 作用 | 状态 |
|---|---|---|
| `00_validate_trajectory_config.py` | 轨迹合法性检查 | 稳定 |
| `00_generate_smoothed_trajectory.py` | 稀疏轨迹转 PCHIP 逐帧轨迹 | 稳定 |
| `00_validate_episode_config.py` | 事件语义和球权检查 | 稳定 |
| `00_generate_episode_trajectories.py` | A3.2 事件转轨迹 | 稳定基线 |
| `00_generate_episode_trajectories_A3_3.py` | yaw/action/ball state/contact | 当前稳定生成器 |
| `00_ue_list_action_animation_assets_V2.py` | UE 动画资产扫描 | 当前使用 |
| `01_ue_build_from_config_and_export_annotations_A2_2.py` | 多关键帧、安全 bbox、Camera Cuts | 稳定基线 |
| `01_ue_build_episode_from_config_A3_3B.py` | 动作动画 Section | 当前待 UE 验证 |
| `02_win_overlay_convert_check.py` | overlay、YOLO、MOT、manifest、检查 | 稳定 |
| `action_animation_map.json` | 动作到 UE 动画资源映射 | 当前配置 |

## 5.2 保留但不要作为当前入口

```text
01_ue_build_seq_and_export_annotations.py
01_ue_build_from_config_and_export_annotations.py
01_ue_build_from_config_and_export_annotations_A2.py
02_win_overlay_convert_check_A1_5.py
00_ue_list_action_animation_assets.py
```

原因：

- 它们是旧基线或中间版本；
- 旧扫描器会输出 `<Struct 'SoftObjectPath' ...>`；
- 某些旧 UE 脚本仍读取 `start/end`；
- 当前主线已升级为事件驱动与动作时间轴。

---

# 6. 当前精确运行链路

## 6.1 重新生成事件回合

Windows PowerShell：

```powershell
cd D:\projects\FustalMOT_UEDataset\Content\FutsalMOT\code
```

### 1. 验证事件配置

```powershell
py 00_validate_episode_config.py `
  --config "D:\projects\FustalMOT_UEDataset\Content\FutsalMOT\code\configs\events\episode_test_0001.json"
```

要求：

```text
errors = 0
```

### 2. 生成 A3.2 逐帧轨迹

```powershell
py 00_generate_episode_trajectories.py `
  --config "D:\projects\FustalMOT_UEDataset\Content\FutsalMOT\code\configs\events\episode_test_0001.json"
```

### 3. 生成 A3.3 动作/yaw 版本

```powershell
py 00_generate_episode_trajectories_A3_3.py --recompile-base
```

输出：

```text
configs/generated/episode_test_0001_A3_3.json
```

### 4. 验证最终轨迹

```powershell
py 00_validate_trajectory_config.py `
  --config "D:\projects\FustalMOT_UEDataset\Content\FutsalMOT\code\configs\generated\episode_test_0001_A3_3.json"
```

要求：

```text
errors = 0
```

普通 WARNING 暂不作为失败。

## 6.2 UE 构建

在 UE Python 控制台运行：

```text
py "D:/projects/FustalMOT_UEDataset/Content/FutsalMOT/code/01_ue_build_episode_from_config_A3_3B.py"
```

期望：

```text
SEQ_ID = episode_test_0001_A3_3
FRAME_RANGE = 0..299
OBJECT_COUNT = 5
Records = 1200
Expected records = 1200
```

## 6.3 Sequencer 验收

重点区间：

```text
68–77：传球准备和触球
89–99：接球准备和接球
158–168：射门准备和触球
183–190：射门结束
```

检查：

- Camera Cuts 为 `[0, 300)`；
- 每个球员 Transform 有 300 帧；
- yaw 连续；
- Animation Track 中 Section 连续；
- 无 T Pose；
- 无空帧；
- 动画切换不破坏位置；
- bbox 仍 tight；
- 足球没有跳回旧持球者；
- frame 75、96、165 同步。

## 6.4 MRQ

只有 Sequencer 检查通过后执行。

```text
Start Frame = 0
End Frame = 299
1920 × 1080
PNG
Warm Up = 0
```

规模：

```text
300 帧 × 4 相机 = 1200 张图
```

## 6.5 后处理

```powershell
py 02_win_overlay_convert_check.py `
  --annotation "D:\projects\FustalMOT_UEDataset\Saved\FutsalMOT\annotations\objects_bbox_2d_clean_episode_test_0001_A3_3.json"
```

预期：

```text
records = 1200
yolo_files = 1200
expected_objects_per_record = 5
CHECK PASSED
ALL DONE
```

---

# 7. 当前已知问题和风险

## 7.1 足球专项动画暂缺，Fab 采购暂缓

当前项目内没有：

```text
dribble
pass
receive
shot
defend
```

相关 AnimSequence。

已确认可在 **Unreal Fab** 中寻找和下载足球专项动作资产，但合适的资产可能需要付费购买。该支出需要先与导师讨论，由导师决定是否提供预算。因此：

```text
足球专项动画采购与 Retarget：暂时搁置
当前不作为代码管线继续开发的阻塞项
未经导师同意，不购买付费 Fab 资产
```

当前处理策略：

- action_timeline 数据继续保留；
- Animation Section 继续按动作语义切分；
- Idle 使用 `MM_Idle`；
- Jog 使用 `MF_Unarmed_Jog_Fwd`；
- dribble/pass/receive/shot/defend 暂时 fallback 到 Jog；
- 先验证 Section、事件标签、球权、轨迹、bbox 和批处理链路；
- 等导师确认预算后，再恢复专项动作采购、导入和 Retarget。

结果限制：

- 当前可验证动作区段和标注逻辑；
- 视觉动作暂时不具备真实传球、接球、射门和防守姿态；
- fallback 数据不得表述为高真实感足球动作数据；
- 最终高质量动作数据集渲染应等待专项动画方案确定。

## 7.2 骨架兼容性

当前候选动画骨架：

```text
/Game/Characters/Mannequins/Meshes/SK_Mannequin.SK_Mannequin
```

后续导入足球动画时必须：

- 明确源骨架；
- 使用 IK Rig / IK Retargeter；
- 输出到当前球员使用骨架；
- 检查脚底、髋部、手臂和 Root；
- 禁止未经检查直接加入数据集。

## 7.3 Root Motion

外部足球动作可能带 Root Motion。

当前轨迹系统由 Transform Track 决定世界位移，因此建议第一版：

```text
使用 in-place 动画
或在 Sequencer 中忽略动画 Root Motion
```

否则会出现：

```text
轨迹位移 + 动画 Root Motion 双重移动
```

## 7.4 动画与触球帧对齐

仅把动作 Section 放在事件区间并不保证脚碰球。

必须新增：

- 每个动画的 contact normalized time；
- Section start offset；
- play rate；
- loop / hold 策略；
- pass/shot 使用哪只脚；
- receive 的第一触球时刻。

## 7.5 bbox 姿态评估

动作切换后人物四肢范围可能比 Jog 更大。

每引入一个新专项动画，必须重新检查：

- 头；
- 手；
- 鞋；
- 抬腿；
- 射门腿；
- 躯干后仰；
- 多相机 bbox。

## 7.6 动画压缩日志

首次 V2 扫描出现大量：

```text
LogAnimationCompression: Building compressed animation data
```

这是 UE 首次加载/缓存动画，当前不是故障。

## 7.7 当前 A3.3b UE 状态

必须诚实区分：

```text
脚本已生成 ≠ 用户 UE 已验证成功
```

当前只确认：

- V2 扫描器已成功；
- 资源路径正确；
- 项目缺少专项动画。

尚需用户或 Agent 提供：

- A3.3b 构建日志；
- Sequencer 截图；
- 动画 Section 检查结果；
- bbox overlay。

---

# 8. 后续工作规划

# Phase 0：冻结稳定基线

优先级：P0

任务：

1. 创建版本冻结目录：

```text
Content/FutsalMOT/code/_stable/
├─ A2_2/
├─ A2_5/
├─ A3_2/
└─ A3_3/
```

2. 保存：
   - 稳定脚本；
   - 配置；
   - 验证报告；
   - overlay 样例；
   - SHA256；
   - UE 版本；
   - 插件列表。

3. 建立：

```text
CHANGELOG.md
RUNBOOK.md
FILE_MANIFEST.json
```

验收：

- 任一稳定版本可重新运行；
- Agent 修改不会覆盖旧版本；
- 文件用途明确。

---

# Phase 1：完成 A3.3b UE 集成验证

优先级：P0，下一项立即执行

任务：

1. 将：

```text
action_animation_map_ready.json
```

复制为：

```text
configs/action_animation_map.json
```

2. 运行：

```text
01_ue_build_episode_from_config_A3_3B.py
```

3. 修复所有 UE Python API 或动画 Section 错误；
4. 检查 Player_01–04 动画轨道；
5. 检查 `Records = 1200`；
6. 检查输出标注中的：
   - `action`；
   - `action_source_events`；
   - `action_animation_resolution`。

7. 做一次 fallback-only 小规模 MRQ；
8. 运行后处理并检查 overlay。

验收：

```text
UE 无异常
无 T Pose
Animation Section 连续
Camera Cuts = [0, 300)
bbox 正确
annotations = 1200
02 CHECK PASSED
```

---

# Phase 2：足球专项动画引入与 Retarget（暂时搁置）

优先级：**HOLD，等待导师预算决定**

当前决策：

```text
可在 Unreal Fab 中获取足球专项动作
但合适资产可能需要付费
需先与导师讨论资金和采购许可
导师未确认前，不购买、不导入、不进入正式 Retarget
```

暂停期间保留的技术准备：

- 继续维护 `action_animation_map.json`；
- 继续使用 Idle/Jog fallback；
- 保留 `action_timeline`、`contact_frames` 和动画 Section；
- A3.3b fallback 管线仍需完成 UE 验收；
- A3.3c 事件级标注、A3.4 随机回合和 A4 批处理可以继续开发；
- 最终高真实感数据集生产暂缓，不应把 fallback 动作作为最终版本。

导师批准预算后再执行以下任务。

最低动画集合：

```text
idle
jog/run
dribble
short pass
receive/trap
shot
defensive shuffle
```

推荐附加：

```text
turn left/right
sprint
stop
backpedal
intercept
tackle
goalkeeper idle/save
```

恢复后的任务：

1. 在 Unreal Fab 中筛选合法可使用的足球动作资产；
2. 记录资产名称、价格、许可范围、动作数量和源骨架；
3. 将候选方案与预算提交导师决定；
4. 获得批准后购买并导入 UE；
5. 为源骨架和目标 SK_Mannequin 创建 IK Rig；
6. 创建 IK Retargeter；
7. 批量导出 Retargeted AnimSequence；
8. 统一命名：
   - `AS_Futsal_Idle`
   - `AS_Futsal_Jog`
   - `AS_Futsal_Dribble`
   - `AS_Futsal_Pass_R`
   - `AS_Futsal_Receive`
   - `AS_Futsal_Shot_R`
   - `AS_Futsal_Defend`
9. 检查骨架兼容性和 Root Motion；
10. 更新 `action_animation_map.json`。

恢复后的验收：

- 所有动作能加载；
- 无 fallback；
- 人体无严重扭曲；
- 脚底不明显滑动；
- 多相机中动作合理；
- 资产许可允许用于研究和合成数据集生成。

---

# Phase 3：动作与球接触帧精确同步

优先级：P0

新增动画元数据：

```json
{
  "pass": {
    "asset": "/Game/.../AS_Futsal_Pass_R",
    "contact_normalized_time": 0.62,
    "preferred_duration_frames": 26,
    "loop": false,
    "hold_last_pose": true
  }
}
```

任务：

- 根据 contact frame 反算 Section start；
- 自动设置 start offset；
- 自动计算 play rate；
- 传球脚和足球脚前偏移一致；
- 接球触球前球必须仍处飞行状态；
- 射门动作触球和球起飞同帧；
- 动作结束后平滑过渡 Jog/Idle。

验收：

```text
frame 75：传球脚接触球
frame 96：接球动作第一触球
frame 165：射门脚接触球
```

允许误差目标：

```text
≤ 1 frame
```

---

# Phase 4：A3.3c 事件级标注

优先级：P1

新增：

```text
annotations/events_<seq_id>.json
annotations/frame_states_<seq_id>.jsonl
```

事件标注字段：

```text
event_id
type
actor_track_id
target_track_id
start_frame
end_frame
contact_frame
team
result
```

逐帧状态：

```text
frame
active_events
player_actions
ball_state
possession_owner
pass_source
pass_target
contact_events
```

扩展对象标注：

```text
action
action_source_events
team_id
role
has_possession
distance_to_ball
```

扩展 `02_win_overlay_convert_check.py`：

- 检查事件帧范围；
- 检查 action_timeline 覆盖；
- 检查 possession 唯一性；
- 可选在 overlay 上画动作与球权文本；
- manifest 写入事件摘要。

验收：

- 轨迹、图像、bbox、动作、事件和球权对齐；
- 无事件越界；
- 触球帧一致；
- 可直接供动作识别/事件检测训练。

---

# Phase 5：A3.4 随机比赛回合生成器

优先级：P1

新增：

```text
00_generate_random_episode.py
```

核心设计：

```text
seed
template
team formation
start positions
event graph
constraints
output episode config
```

模板：

1. 单人带球射门；
2. 横传；
3. 斜传；
4. 二过一；
5. 回传；
6. 防守跟随；
7. 抢断；
8. 传球失败；
9. 射门偏出；
10. 射门进球。

必须新增事件：

```text
intercept
turnover
goal
out_of_bounds
restart
press
goalkeeper
```

约束：

- 球权唯一；
- 传球目标存在；
- 球员速度/加速度/转向受限；
- 球员碰撞避免；
- 目标不越界；
- 射门只在合法区域；
- 固定 seed 可复现；
- 失败时自动重采样。

验收：

- 批量生成至少 100 个 episode；
- 验证器 ERROR=0；
- 随机种子复现；
- 事件分布可统计。

---

# Phase 6：A4 长序列与批处理

优先级：P1

目标：

```text
30 秒
1 分钟
3–5 分钟
完整比赛
```

不能直接把一个 10 秒模板延长。需要：

- episode 拼接；
- 状态机；
- 球权传递；
- 球员体力/速度调节；
- 球出界和重新开球；
- 进球后重置；
- 阵型恢复；
- 防守/进攻转换。

建议架构：

```text
MatchState
├─ kickoff
├─ possession
├─ transition
├─ attack
├─ defense
├─ set_piece
├─ goal
└─ restart
```

新增批处理：

```text
03_batch_generate_dataset.py
```

功能：

- 批量生成配置；
- 验证；
- 调用 UE；
- 创建 MRQ jobs；
- 断点续跑；
- 每序列日志；
- 失败重试；
- 输出 manifest；
- 磁盘空间检查；
- 完整性汇总。

验收：

- 失败序列不影响其他序列；
- 可恢复；
- 每个序列可追踪 seed/config/log；
- 3–5 min 序列稳定生成。

---

# Phase 7：数据集域随机化与质量提升

优先级：P2

变量：

- 球员外观；
- 队服颜色；
- 号码；
- 身高体型；
- 球模型；
- 灯光；
- 时间；
- 地面材质；
- 场馆背景；
- 相机位置；
- 焦距；
- 曝光；
- 运动模糊；
- 遮挡；
- 镜头畸变；
- 图像噪声。

原则：

- clean 数据与增强数据分开；
- 相机畸变必须同步变换 2D 标注；
- 每个 sequence/camera 保存参数；
- 不允许仅变图像而不变标注。

---

# Phase 8：路线 D——Learning Agents / RL / 模仿学习

优先级：P3，当前不要提前实施

项目早期已有 Python / Google Research Football 轨迹原型背景，但当前 UE 主线是规则驱动。

未来可接入：

- UE Learning Agents；
- 强化学习；
- 模仿学习；
- 外部 GRF 轨迹；
- 多智能体策略；
- 从真实比赛或游戏轨迹学习。

使用原则：

```text
学习策略只提供高层动作/目标
轨迹验证器仍然保留
事件和球权仍然显式记录
UE 渲染与标注仍使用同一逐帧状态
```

先决条件：

- 路线 A 批处理稳定；
- 动作动画稳定；
- 长回合状态机稳定；
- 验证器可自动拒绝异常策略输出。

---

# Phase 9：路线 E——Motion Matching

优先级：P3

用途：

- 降低脚滑；
- 改善启动/停止；
- 改善急转弯；
- 改善进攻/防守切换；
- 提高连续长序列动画真实性。

建议：

- Pose Search Database；
- Motion Matching；
- 足球动作数据库；
- trajectory intent 作为查询特征；
- 与事件动作标签结合；
- 仍保留 contact frame metadata。

Motion Matching 不能替代：

- 事件逻辑；
- 球权；
- 轨迹安全验证；
- 标注同步。

---

# 9. 可写入论文的数据集亮点

当前和规划中的潜在创新点：

1. 基于 UE 的可控五人制足球多视角合成数据集；
2. 统一球场世界坐标与 41 个标准场地点；
3. 固定多相机几何和完整相机内外参；
4. RGB、球场关键点、球员/足球 bbox、YOLO、MOT 同步；
5. 基于姿态骨骼包络的 tight bbox；
6. 规则事件到逐帧轨迹的可解释编译；
7. 显式球权、传球关系、触球帧和动作时间轴；
8. 可控遮挡、视角和域随机化；
9. 支持检测、跟踪、动作、事件和交互多任务研究；
10. 可通过规则、GRF、RL/IL、Motion Matching 逐级提升运动质量；
11. 配置、seed、事件和轨迹可复现；
12. 多级自动验证闭环。

后续实验建议：

- synthetic-only；
- real-only；
- synthetic pretrain + real fine-tune；
- bbox 算法对比；
- 无动作同步 vs 有动作同步；
- 无域随机化 vs 有域随机化；
- rule-based vs learned trajectories；
- 短序列 vs 长序列；
- 单视角 vs 多视角；
- 不同遮挡强度。

---

# 10. 下一位 Agent 的第一项任务

Agent 接手后不要立即开发随机比赛或 RL。

按以下顺序执行：

## Step 1：核对当前本地文件

确认：

```text
configs/generated/episode_test_0001_A3_3.json
configs/action_animation_map.json
01_ue_build_episode_from_config_A3_3B.py
```

## Step 2：运行 A3.3b UE 构建

```text
py "D:/projects/FustalMOT_UEDataset/Content/FutsalMOT/code/01_ue_build_episode_from_config_A3_3B.py"
```

## Step 3：收集完整 UE 日志

必须检查：

```text
ANIM OK
ANIM FALLBACK
animation_sections
Records
Expected records
Traceback
Error
```

## Step 4：检查 Sequencer

要求用户提供：

- Player_01 动画轨道；
- Player_02 动画轨道；
- frame 75；
- frame 96；
- frame 165；
- Camera Cuts；
- 一张 bbox overlay。

## Step 5：修复 A3.3b

若有错误：

- 根据真实行号修复；
- 保留版本化文件；
- 生成完整可下载脚本；
- 不只给代码片段；
- 先做 Python syntax check；
- 不能声称 UE API 已验证，除非用户运行成功。

## Step 6：fallback-only 验收

即使没有专项动画，也要先证明：

```text
action_timeline → Section
Section 连续
标注 action 正确
bbox 不受影响
```

验收后不要自动进入付费动画采购或 Retarget。足球专项动作资产可从 Unreal Fab 获取，但需要资金，必须等待用户与导师讨论后的明确决定。

当前验收后的开发顺序为：

```text
A3.3c 事件级标注
→ A3.4 随机回合
→ A4 批量与长序列
→ 等待导师预算决定
→ 再恢复 Fab 动画采购与 Retarget
```

---

# 11. 对 Agent 的强制工作规范

1. **先读本交接文档。**
2. 不覆盖稳定脚本。
3. 新功能使用唯一版本名。
4. 每次给出完整代码文件。
5. 用户偏好直接下载代码，不要只描述。
6. Windows 脚本和 UE 脚本运行环境必须区分。
7. UE API 不确定时必须基于用户日志迭代。
8. 不重复引入已经解决的 `start/end` 旧格式。
9. 不让 Camera Cuts 回退为 10 或 150 帧。
10. 不破坏用户已调好的 bbox 参数。
11. 不让 UE 自动曲线与离线标注产生两套轨迹。
12. 每一步先验证，再进入下一步。
13. 所有输出必须保留：
    - seq_id；
    - config path；
    - version marker；
    - object count；
    - frame range；
    - expected records；
    - errors/warnings。
14. 长序列生成必须可复现、可中断、可续跑。
15. 没有真实执行证据时，明确写“未验证”。

---

# 12. 可直接粘贴给新 Agent 的开场指令

```text
你现在接手 FutsalMOT_UEDataset 项目。请先完整阅读随附的
《FutsalMOT Unreal Engine 合成数据集项目：Agent 完整交接文档》。

项目根目录：
D:/projects/FustalMOT_UEDataset

当前主线：
规则事件 → 逐帧轨迹 → yaw/action/ball state/contact →
UE Sequencer → RGB/bbox/YOLO/MOT/event labels。

当前最新阶段：
A3.3b，根据 action_timeline 创建 UE Skeletal Animation Sections。

已确认：
- episode_test_0001_A3_3.json 已生成；
- 4 名球员和足球各 300 帧；
- 轨迹 errors=0；
- 动画扫描器 V2 在 UE 成功；
- 共 104 个动画类资源，100 个可直接用于 Section；
- 有 Idle/Jog；
- 没有 dribble/pass/receive/shot/defend 专项动画。

当前第一任务：
1. 检查 configs/action_animation_map.json；
2. 运行 01_ue_build_episode_from_config_A3_3B.py；
3. 根据完整 UE 日志修复；
4. 验证动画 Section、Camera Cuts、1200 条标注和 bbox；
5. 使用 Idle/Jog fallback 完成管线验收；
6. 继续 A3.3c 事件级标注、A3.4 随机回合和 A4 批处理。

重要决策：
足球专项动作可以在 Unreal Fab 中下载，但合适资产可能需要付费，需与导师讨论预算后决定。目前该项暂时搁置。未经用户明确确认，不得购买、假设已购买或把 Retarget 设为当前阻塞任务。

工作要求：
- 不覆盖稳定代码；
- 使用版本化文件名；
- 输出完整可下载代码；
- 先验证再推进；
- 不得在没有 UE 实际日志时声称运行成功；
- 不要跳到 RL 或 Motion Matching，先完成路线 A。
```

---

# 13. 项目决策记录：Fab 足球动画资产

```text
决策日期：2026-07-16
决策状态：暂缓
决策事项：从 Unreal Fab 获取足球专项动作资产
原因：合适资产可能需要付费，需要与导师讨论资金和采购必要性
当前执行：继续使用 Idle/Jog fallback，推进非资产依赖的代码和标注工作
恢复条件：导师明确同意预算和采购方案
```

Agent 必须遵守：

- 不把 Fab 付费资产视为已具备资源；
- 不在未获确认时建议直接购买；
- 不因缺少专项动画停止 A3.3c、A3.4 和 A4 的代码开发；
- 不将 fallback 动作生成结果描述为最终高真实感数据集；
- 导师批准后，先做候选资产、价格、许可和骨架兼容性对比，再执行采购。

---

# 14. 当前最终状态判定

```text
A1 外部 JSON：完成
A1.5 通用后处理：完成
A2 多关键帧：完成
A2.2 tight bbox：完成并人工调参
A2.5a 轨迹验证：完成
A2.5b 平滑逐帧轨迹：完成
A3.1 事件配置和验证：完成
A3.2 事件转逐帧轨迹：完成
A3.3 yaw/action/ball state/contact：完成
A3.3b 动画 Section 代码：已生成
A3.3b UE 实际完整验收：待完成
专项足球动画：缺失；Fab 付费采购需与导师讨论，当前暂时搁置
足球动画 Retarget：暂停，等待预算决定
A3.3c 事件级最终标注：待开发
A3.4 随机回合生成：待开发
A4 3–5 分钟长序列：待开发
路线 D RL/IL：后续
路线 E Motion Matching：后续
```
