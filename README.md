# FutsalMOT UE

> Unreal Engine 5.8 场景与数据集生成前端，用于构建、回放和渲染 FutsalMOT 的合成足球场景。

`FutsalMOT_UE` 是 FutsalMOT 项目的 Unreal Engine 场景仓库。它提供足球场、球员、足球、相机、Level Sequence、材质和蓝图等 UE 资产，并作为数据集生成流水线的 Unreal Engine 运行环境。

本仓库本身主要负责：

- Unreal Engine 场景与资产管理
- 足球场及比赛环境
- 球员与足球 Actor
- Actor 与数据集实体 ID 的对应
- Level Sequence 回放
- CineCamera 相机
- Movie Render Queue（MRQ）渲染
- Object ID / Instance Mask 渲染基础设施
- 数据集生成所需的 UE 侧 Python 运行环境

而 GRF 轨迹生成、数据后处理、MOT / YOLO / Pose 标注、数据集审计等 Python 代码位于项目中的独立 Git 仓库 `HHhydrogen/FutsalMOT_Dataset`。

因此，本仓库与内层仓库应理解为两个协同工作的独立工程，而不是一个普通的 Git submodule 项目。

---

## 项目整体架构

```text
FutsalMOT_UE
│
│  Unreal Engine 5.8
│  场景 / Actor / Camera / Sequence / Render
│
└── Content/FutsalMOT/code/
        │
        │  独立 Git 仓库
        ▼
    FutsalMOT_Dataset
        │
        ├── Google Research Football
        ├── GRF 轨迹导出
        ├── JSONL 数据契约
        ├── UE 导入 / 控制
        ├── MRQ 渲染控制
        ├── Instance Mask
        ├── MOT / YOLO Detection / Segmentation
        ├── YOLO Pose
        └── Dataset Validation / Audit
```

概念上的完整流程：

```text
Google Research Football
        │
        ▼
   JSON / JSONL
        │
        ▼
Unreal Engine 5.8
        │
        ├── Actor Transform
        ├── Level Sequence
        ├── CineCamera
        │
        ▼
 Movie Render Queue
        │
        ├── RGB
        └── Object ID / Cryptomatte
                │
                ▼
         FutsalMOT_Dataset
                │
                ├── Instance Mask
                ├── Bounding Box
                ├── MOT
                ├── YOLO Detection
                ├── YOLO Segmentation
                └── YOLO Pose
```

---

# Unreal Engine 版本与项目类型

当前项目使用 **Unreal Engine 5.8**。

`.uproject` 中的 `EngineAssociation` 为 `5.8`。项目没有 `Source/` C++ 工程，主要以 UE Blueprint 和 `.uasset/.umap` 资产为核心。

当前启用的重要插件包括：

- `ModelingToolsEditorMode`
- `GameplayStateTree`
- `MovieRenderPipeline`
- `MoviePipelineMaskRenderPass`

其中后两个插件主要服务于数据集渲染流程。

---

# 外层仓库与内层仓库

这是使用本项目时最重要的 Git 约定。

## 外层仓库

```text
HHhydrogen/FutsalMOT_UE
```

用途：

- Unreal Engine 项目
- `.uproject`
- `Config/`
- `Content/`
- UE 蓝图
- UE 场景
- UE 材质
- UE Animation
- UE Sequence
- UE 相关资源

默认分支：

```text
master
```

## 内层仓库

```text
HHhydrogen/FutsalMOT_Dataset
```

实际路径：

```text
Content/FutsalMOT/code/
```

它是一个**完全独立的 Git 仓库**，默认分支为 `main`。

负责：

- GRF 轨迹生成
- P1 Python pipeline
- P2 UE Python pipeline
- JSONL 数据契约
- 标注后处理
- Instance Mask
- MOT / YOLO
- Pose
- Dataset Audit
- Dataset Manifest

外层仓库已经在 `.gitignore` 中明确忽略：

```text
Content/FutsalMOT/code/
```

因此外层 `git add -A` 不会把内层 Python 仓库作为外层仓库的一部分提交。

### Git 操作边界

**修改 UE 资产 → 在外层仓库提交。**

**修改 Python 数据集代码 → 进入 `Content/FutsalMOT/code/`，在内层仓库单独提交。**

不要混淆两个 Git 工作树。

---

# 仓库目录结构

```text
FutsalMOT_UE/
│
├── .gitignore
├── AGENTS.md
├── README.md
├── FustalMOT_UEDataset.uproject
│
├── Config/
│   ├── DefaultEditor.ini
│   ├── DefaultEditorPerProjectUserSettings.ini
│   ├── DefaultEngine.ini
│   ├── DefaultGame.ini
│   └── DefaultInput.ini
│
└── Content/
    ├── Characters/
    ├── FutsalMOT/
    ├── Input/
    ├── LevelPrototyping/
    ├── ThirdPerson/
    ├── __ExternalActors__/
    └── __ExternalObjects__/
```

与 FutsalMOT 数据生成最相关的核心目录：

```text
Content/FutsalMOT/
├── Animation/
├── Blueprints/
├── Football/
├── Maps/
├── Materials/
└── Sequences/
```

---

# FutsalMOT UE 内容结构

## `Animation/`

存放与球员角色及足球场景相关的动画资产。后续会进一步引入并整理足球运动员动作合集，使球员动作能够与轨迹驱动更自然地融合。

## `Blueprints/`

FutsalMOT 的核心蓝图目录。目前包含例如：

- `BP_FieldKeypoint.uasset`
- `BP_FutsalBall.uasset`
- `BP_NoPawnGameMode.uasset`
- `BP_SplineArcLine.uasset`
- `BP_SplineArcLine1.uasset`
- `BP_SplineCircleLine.uasset`

其中：

### `BP_FutsalBall`

用于场景中的足球 Actor。数据集导入时，球的位置来自 GRF episode，并通过 UE Sequence 进行回放。

### `BP_FieldKeypoint`

用于场地关键点相关表达，可用于场地标定、几何参考或后续计算机视觉相关流程。

### `BP_NoPawnGameMode`

项目默认 GameMode。项目不是传统意义上需要玩家进入和操控角色的足球游戏，因此使用 No Pawn GameMode 更符合数据生成场景。

## `Football/`

存放足球相关的几何、材质、网格或其它体育场景资源。这部分主要负责视觉资产层。

数据集流水线负责“球在哪里运动”，UE 资产负责“球长什么样”。

## `Maps/`

存放 Unreal Engine 关卡。

当前默认地图：

```text
/Game/FutsalMOT/Maps/L_Futsal_Demo.L_Futsal_Demo
```

该地图被设置为 Editor Startup Map 和 Game Default Map。

## `Materials/`

存放场景材质相关资产，包括场地、球员、足球及其它环境材质。正常 RGB 外观与 Instance ID 是两个不同的渲染层。

## `Sequences/`

存放 Level Sequence，是连接“外部轨迹”和“UE 可渲染时间轴”的核心资产层。

---

# 场景中的实体 ID

数据集层定义了固定实体 ID：

```text
L0
L1
L2
L3
L4

R0
R1
R2
R3
R4

BALL
```

Actor mapping 示例：

```json
{
  "L0": "Player_L0",
  "L1": "Player_L1",
  "L2": "Player_L2",
  "L3": "Player_L3",
  "L4": "Player_L4",
  "R0": "Player_R0",
  "R1": "Player_R1",
  "R2": "Player_R2",
  "R3": "Player_R3",
  "R4": "Player_R4",
  "BALL": "Ball_01"
}
```

因此 UE 场景必须保持：

```text
Player_L0 ... Player_L4
Player_R0 ... Player_R4
Ball_01
```

等 Actor 标识与数据集侧实体映射一致。

**不要随意重命名这些 Actor。** 这些标识会直接影响 Sequence、MOT track identity、Instance ID 以及后续 Pose / segmentation 标注。

---

# 默认 Game / Render 设置

当前 `DefaultEngine.ini` 已配置针对高质量场景和数据生成的图形功能，包括：

- Lumen
- Virtual Shadow Maps
- Ray Tracing
- Substrate
- Custom Depth
- DirectX 12
- Shader Model 6

因此本项目并不是面向低配硬件的普通 Demo。大规模数据生成还需要预留较大的磁盘空间用于 RGB、Mask、EXR 等中间和最终数据。

---

# 如何打开项目

## 1. 获取仓库

```bash
git clone https://github.com/HHhydrogen/FutsalMOT_UE.git
cd FutsalMOT_UE
```

## 2. 打开 Unreal 项目

使用 Unreal Engine 5.8 打开：

```text
FustalMOT_UEDataset.uproject
```

项目文件名中的 `Fustal` 是当前仓库实际采用的项目名拼写，使用时请保持原名。

## 3. 检查 Unreal Engine 版本

必须使用：

```text
Unreal Engine 5.8
```

不要直接使用其它 UE 主版本打开并保存项目资产，避免 `.uasset/.umap` 发生版本升级或兼容性问题。

---

# 推荐的开发顺序

如果只是检查 UE 场景：

```text
打开 .uproject
   ↓
加载 L_Futsal_Demo
   ↓
检查 Player_L*
检查 Player_R*
检查 Ball_01
检查 CineCamera
   ↓
运行 / Preview
```

如果需要进行真实数据集生成：

```text
FutsalMOT_Dataset
        ↓
创建 / 验证 Dataset Task
        ↓
GRF export
        ↓
resolved task
        ↓
UE run_task.py
        ↓
Level Sequence
        ↓
MRQ
        ↓
RGB / Object ID
        ↓
Dataset postprocess
```

完整的 GRF、Python、数据集、标注和审计说明请直接阅读内层仓库的 README 与文档。

---

# UE 侧数据生成原则

UE 在整个系统中主要承担：

1. 加载和保存场景
2. 提供球员 / 足球 Actor
3. 提供 Camera
4. 根据数据轨迹驱动 Actor
5. 生成 Level Sequence
6. 执行 MRQ 渲染
7. 产生 RGB
8. 产生 Object ID / Cryptomatte
9. 提供骨骼与其它 UE 侧几何信息

而 GRF 轨迹生成、Mask 后处理、bbox、MOT、YOLO 标签、Pose label、Dataset validation、manifest 等主要由内层仓库承担。

---

# Level Sequence

Level Sequence 是本项目连接：

```text
JSONL trajectory
        ↓
UE Actor
        ↓
Camera playback
        ↓
MRQ render
```

的重要桥梁。

这里的 Sequence 不应仅仅理解为“影视动画资产”，而应理解为**数据轨迹在 Unreal Engine 中的时间轴表达**。

它需要能够重复、稳定地播放相同轨迹，并供 Camera 捕获和 MRQ 渲染。

---

# Camera

数据集生成使用 CineCamera Actor。

Camera 不只是构图工具，同时是 GT 链路的一部分：

```text
World Position
      ↓
Camera Projection
      ↓
Pixel Coordinates
      ↓
Bounding Box / MOT / Pose
```

因此修改数据集 Camera 时，需要同步考虑 RGB、bbox、MOT、segmentation 和 pose 数据的一致性。

---

# Object ID / Instance Mask

正常 RGB：

```text
RGB Render
```

用于训练输入。

Object ID / Cryptomatte：

```text
Object ID Render
       ↓
Instance Mask
```

用于产生可见区域以及后续 bbox、Instance Segmentation、MOT visibility、Pose visibility 等信息。

因此 Object ID 渲染是整个数据集生产链路的重要基础设施。

---

# 后续工作 / Roadmap

当前外层 UE 仓库的主要后续方向，是继续完善场景真实性与球员动作表现，同时保持数据生成链路的稳定性、可重复性和标注一致性。

## 1. 完善场地与外围环境

当前场地已经具备基本的数据生成条件，但还需要从视觉与比赛环境完整度两方面继续完善。

### 1.1 地面与草地材质

计划为足球场地面加入更合适的草地 / 人造草材质：

- 选择符合室内五人制足球场景的草地贴图
- 完善 Base Color / Roughness / Normal 等材质参数
- 调整 UV 和纹理比例，减少大面积重复纹理
- 根据真实五人制足球场地特点调整颜色和磨损效果
- 在视觉质量与 MRQ 数据生成性能之间取得平衡

最终目标是让 RGB 数据具有更自然、稳定的场地纹理，同时维持适合计算机视觉数据集生成的渲染一致性。

### 1.2 球门及场地设施建模

后续计划补充完整的比赛设施，包括：

- 五人制足球球门
- 球门立柱与横梁
- 球网
- 场边广告牌或基础围挡
- 替补席等必要场景元素
- 其它适合室内五人制足球比赛的固定设施

这些模型既用于提升视觉真实感，也会形成更完整的比赛空间，为后续遮挡、场景理解和多目标跟踪研究提供更加丰富的环境。

### 1.3 场地外围环境

计划把当前相对简单的“单一比赛场地”逐步扩展为完整的室内五人制足球比赛空间，可能包括：

- 场地外围围栏
- 看台或观众区域
- 体育馆墙体 / 建筑结构
- 灯光设施
- 场地入口及基础环境结构
- 其它适合室内五人制足球的静态环境元素

外围环境优先采用**静态、可控、可重复渲染**的设计，避免过多动态元素影响渲染性能、遮挡关系以及 Ground Truth 的稳定性。

---

## 2. 完善球员动作

当前系统已经能够在 UE 中使用球员 Actor 表达数据集中的 10 名球员，并按照轨迹驱动其位置和方向。

下一阶段的重要工作，是进一步完善球员的动作表现，使球员不只是沿轨迹移动，而能够呈现更接近真实五人制足球比赛的运动状态。

### 2.1 引入足球运动员动作合集

项目已经在 Unreal Engine Fab 中购买足球运动员动作合集，后续计划将相关动画资产正式导入项目，并完成与当前球员角色的融合。

预计流程：

```text
Fab 足球运动员动作合集
        ↓
导入 Unreal Engine 项目
        ↓
检查 Skeleton / Retarget
        ↓
建立项目角色的动画映射
        ↓
筛选适合 FutsalMOT 的动作
        ↓
融入现有球员角色
```

重点检查：

- Skeleton 是否与当前球员角色兼容
- 是否需要 IK Retargeter / Retarget Pose
- 是否存在脚部滑动
- Root Motion 是否符合当前 Sequence 驱动方式
- 动作速度、方向是否与数据轨迹一致
- 不同动作之间的过渡是否自然

### 2.2 建立足球动作库

导入动作资产后不会直接全部使用，而是整理为适合 FutsalMOT 的动作库，例如：

- Idle
- Walk
- Jog
- Sprint
- Strafing
- Turning
- Stopping
- Acceleration
- Deceleration
- Backward Movement
- Ball Approach
- Kick
- Pass
- Shoot
- Defensive Movement
- 其它五人制足球相关动作

目标不是单纯增加动画数量，而是形成**可以和轨迹、速度、方向以及比赛状态对应起来的动作集合**。

### 2.3 动作与轨迹融合

当前数据驱动主要解决：

```text
球员在哪里
```

未来动画系统需要进一步解决：

```text
球员正在做什么
```

因此后续需要逐步形成：

```text
Trajectory
    +
Velocity
    +
Direction
    +
Game State
    ↓
Animation Selection
    ↓
Animation Blend
    ↓
Character Motion
```

例如：

- 低速移动 → Walk / Jog
- 高速移动 → Sprint
- 速度快速下降 → Stop
- 方向发生明显变化 → Turn
- 接近足球 → Ball Approach
- 比赛事件触发 → Kick / Pass / Shoot

### 2.4 动作融合与优化

Fab 动画导入后，需要进一步进行项目级优化，包括：

- Retarget 修正
- IK 修正
- 脚底贴地
- Root Motion / In-place 策略统一
- Animation BlendSpace
- 转向动画融合
- 速度与动画播放速率匹配
- 动作切换平滑化
- 减少脚步滑移
- 保证 Sequence / MRQ 渲染时动作稳定

尤其需要保证**相同轨迹、相同配置能够产生稳定且可重复的角色动作结果**。

### 2.5 与数据集 Ground Truth 的关系

角色动作的完善不能只考虑视觉表现，因为动画会直接影响：

- 身体姿态
- 3D 骨骼位置
- 2D Pose
- BBox
- Instance Mask
- 遮挡关系

因此动画系统改动后，需要与内层 `FutsalMOT_Dataset` 的 Pose / Annotation pipeline 一起验证：

```text
动画变化
   ↓
Skeleton Transform
   ↓
Pose Keypoints
   ↓
Projected Keypoints
   ↓
YOLO Pose
```

---

## 3. 建议开发优先级

```text
第一阶段
场地基础视觉完善
    ├── 草地 / 地面材质
    ├── 球门
    └── 基础外围环境

第二阶段
球员动作资产导入
    ├── Fab Animation Pack
    ├── Retarget
    ├── Skeleton / IK
    └── 基础动作库

第三阶段
动作与轨迹融合
    ├── Walk / Jog / Sprint
    ├── Turn / Stop
    ├── BlendSpace
    └── 速度驱动

第四阶段
足球行为动作
    ├── Kick
    ├── Pass
    ├── Shoot
    └── Ball Approach

第五阶段
数据集质量验证
    ├── RGB
    ├── Instance Mask
    ├── BBox / MOT
    └── YOLO Pose
```

最终目标是将当前的：

```text
“轨迹在 UE 中被正确回放”
```

进一步提升为：

```text
“完整的五人制足球比赛场景能够被稳定、可重复地生成和渲染”
```

并在保持 Ground Truth 可控、可验证的前提下，提高 RGB 数据的真实性以及球员动作的自然程度。

---

# Debug 与验证

开发过程中建议按下面的顺序排查：

### 第一层：Actor

确认：

```text
Player_L0 ... Player_L4
Player_R0 ... Player_R4
Ball_01
```

均存在且名称 / mapping 正确。

### 第二层：场景

确认：

- 球场尺寸
- 球门与外围环境
- 地面材质
- 球员初始位置
- 足球位置
- Camera

没有异常。

### 第三层：Sequence

播放 Sequence，检查：

- 球员是否正常移动
- 足球是否正常移动
- 球员朝向是否合理
- 球的滚动是否合理
- 第 0 帧是否正确

特别注意第 0 帧。MRQ 渲染依赖 Sequence 接管 Actor，因此首帧状态错误会直接造成数据集首帧 GT 错误。

---

# Git 规则

## 外层仓库只管理 UE 内容

由外层 Git 管理的主要内容包括：

```text
Config/
Content/
*.uproject
README.md
AGENTS.md
```

不应提交的 UE 生成物包括：

```text
Binaries/
DerivedDataCache/
Intermediate/
Saved/
Build/
.vs/
.vscode/
Logs/
```

## Fab 资产

`Content/Fab/` 当前被 `.gitignore` 忽略。

如果某个 Fab 资产真正成为项目的一部分，应在 Unreal Editor 内容浏览器中把资产移动到 `Content/Fab/` 之外，例如 `Content/FutsalMOT/`，让 Unreal Engine 自动修复引用。

**不要直接使用文件管理器剪切 `.uasset`。**

UE 资产之间存在引用关系，直接在文件系统中移动很容易造成引用断裂。

---

# 两个 Git 仓库的提交边界

## 修改 UE

例如：

```text
BP_FutsalBall.uasset
L_Futsal_Demo.umap
材质
Character
Sequence
Camera
Config
```

进入外层仓库提交：

```bash
git status
git add ...
git commit ...
git push
```

## 修改 Python

进入：

```text
Content/FutsalMOT/code/
```

然后使用内层仓库单独提交：

```bash
cd Content/FutsalMOT/code
git status
git add ...
git commit ...
git push
```

不要期待外层仓库自动包含 Python 修改。

---

# 不建议随意修改的内容

## Actor Identity

保持：

```text
L0-L4
R0-R4
BALL
```

以及对应 Actor 映射稳定。

## Camera 基础设置

相机修改会影响 Projection、BBox、MOT、Segmentation 和 Pose。

## Custom Depth / Rendering 设置

这些设置可能影响 Object ID / Mask / 后处理。

## Sequence 与关卡 Actor 的引用

不要仅为了整理目录或层级而删除、重命名正在被数据生成流程引用的资产。

---

# 常见问题

## 为什么项目没有 C++ Source？

因为当前项目主要采用：

```text
Blueprint
+
UE Python
```

而不是 C++ gameplay architecture，因此 `Content/` 中的 `.uasset/.umap` 是主要项目资产。

## Python 为什么不在外层仓库？

因为 `Content/FutsalMOT/code/` 本身就是独立 Git 仓库。这样可以把 UE binary assets 和 Python source code 分成两个生命周期不同的版本控制单元。

## 为什么没有把 Python 做成 Git submodule？

当前项目采用的是**嵌套独立 Git 仓库 + 外层 `.gitignore`** 的组织方式。外层仓库不记录一个 submodule commit，而是由开发环境同时持有两个独立仓库。

---

# 推荐的本地目录

建议保持：

```text
D:/projects/
└── FustalMOT_UEDataset/
    ├── FustalMOT_UEDataset.uproject
    ├── Config/
    ├── Content/
    │   └── FutsalMOT/
    │       └── code/          ← 独立 FutsalMOT_Dataset 仓库
    └── ...
```

如果内层 task 配置中的 `ue_project_root` 指向本项目，应始终指向包含 `.uproject` 的外层项目根目录，而不是 `Content/FutsalMOT/code/`。

---

# 项目与数据集仓库的职责划分

| 功能 | FutsalMOT_UE | FutsalMOT_Dataset |
|---|---:|---:|
| UE Project | ✅ | |
| UE Config | ✅ | |
| 场地 | ✅ | |
| 球员 Actor | ✅ | |
| 足球 Actor | ✅ | |
| Blueprint | ✅ | |
| Material | ✅ | |
| Level | ✅ | |
| Level Sequence | ✅ | |
| CineCamera | ✅ | |
| MRQ 环境 | ✅ | ✅ 控制 |
| GRF | | ✅ |
| JSONL Export | | ✅ |
| Dataset Task | | ✅ |
| Annotation | | ✅ |
| MOT | | ✅ |
| YOLO Det | | ✅ |
| YOLO Seg | | ✅ |
| YOLO Pose | | ✅ |
| Validation | | ✅ |
| Manifest / Audit | | ✅ |

---

# 适合什么用途

这个 Unreal 项目主要适用于：

- FutsalMOT 合成数据生成
- 足球多目标跟踪研究
- 足球运动目标检测
- Instance Segmentation
- 人体 Pose 数据生成
- 多摄像机数据集生成
- UE + GRF 仿真研究
- CV 数据集自动标注
- Unreal Engine 渲染与 Ground Truth 研究

它不是一个面向玩家发布的完整足球游戏项目，而更适合作为：

**可控、可复现、可自动标注的合成视觉数据生成场景。**

---

# 开发时最重要的原则

### 1. UE 与 Python 分开维护

UE 资产改外层 Git，Python 改内层 Git。

### 2. 不要破坏实体 ID

保持 `L0-L4`、`R0-R4`、`BALL` 以及对应 Actor 映射稳定。

### 3. 不要随意修改 Camera

Camera 是数据集 GT 链路的一部分，而不只是画面构图。

### 4. 不要绕开标准数据生成流程

优先使用：

```text
Dataset Task
    ↓
Resolved Task
    ↓
UE run_task.py
```

而不是在 UE Python Console 中临时写一套与标准 pipeline 无关的运动逻辑。

### 5. 不要提交 UE 生成物

避免提交 `Saved/`、`Intermediate/`、`DerivedDataCache/`、`Binaries/`、`Logs/` 等目录，以及不应进入 Git 的大型 Fab 资产。

---

# 进一步阅读

完整的数据生成、GRF、JSONL、标注、Pose、Mask 和审计说明请阅读内层仓库：

```text
Content/FutsalMOT/code/README.md
```

内层仓库还包含：

```text
configs/
src/grf_ue_bridge/
ue/
tests/
docs/
```

其中 `CLAUDE.md` 和内层 README 是 Python 数据集流水线的详细开发规范。

本 README 有意不复制这些内容，以避免 UE 项目文档与数据集 pipeline 文档出现两份相互矛盾的说明。

---

# 相关仓库

- Unreal Engine 场景仓库：`https://github.com/HHhydrogen/FutsalMOT_UE`
- 数据集 / GRF / Python 仓库：`https://github.com/HHhydrogen/FutsalMOT_Dataset`

---

# License

当前仓库没有声明明确的开源许可证。在没有明确 License 文件或授权说明之前，不应默认本项目可以自由用于商业发布、再分发或二次资产分发。

---

# Status

当前项目处于持续开发状态。

核心目标是建立稳定的：

```text
GRF trajectory
      ↓
UE replay
      ↓
UE rendering
      ↓
Computer Vision Ground Truth
```

生产链路，并逐步完善真实的五人制足球场景、球门、外围环境以及球员足球动作，使生成的数据在保持 Ground Truth 可控和可验证的同时，具备更高的视觉真实性与动作自然度。
