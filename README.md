# FutsalMOT Unreal Engine 项目

本仓库是 FutsalMOT 合成多目标跟踪数据集的 Unreal Engine 资产仓库。它提供 UE 5.8 场景、角色、动画、Level Sequence、Pose Recorder、Movie Render Queue 相关 Blueprint 和本地 MCP 插件。

数据生成代码位于 `Content/FutsalMOT/code/` 下的独立 Git 仓库。外层通过 `.gitmodules` 和 gitlink 引用内层 commit；两个仓库仍必须分别管理。

## 仓库边界

| 仓库 | 根目录 | 负责内容 | 当前 Git 边界 |
| --- | --- | --- | --- |
| UE 仓库 | `D:/projects/FustalMOT_UEDataset` | `.uproject`、`Config/`、插件、UE 内容资产和内层 submodule 指针 | 只记录 gitlink，不逐文件跟踪内层内容 |
| Python 仓库 | `Content/FutsalMOT/code/` | GRF 导出、任务配置、UE Python、标注后处理和测试 | 独立仓库，需进入该目录单独操作 |

外层仓库当前没有 `Source/`、C++、`Build.cs` 或 `Target.cs` 文件，项目实现边界是 Blueprint 和内容资产。`Saved/`、`Intermediate/`、`DerivedDataCache/`、`Content/Fab/` 等目录不属于提交内容；Fab 资产若要纳入项目，应在 UE 内容浏览器中移到 `Content/Fab/` 之外，不能直接用文件管理器移动。

首次克隆外层仓库后，使用 `git submodule update --init --recursive` 拉取内层仓库。外层 commit 只更新 `Content/FutsalMOT/code` 的 gitlink；内层代码、配置和文档的提交必须先在内层仓库完成。

端到端流程和数据格式见内层仓库的 `README.md`、`docs/DATA_CONTRACT.md` 和 `docs/VALIDATION_AND_LIMITATIONS.md`。

## UE 工程配置

工程文件 `FustalMOT_UEDataset.uproject` 声明 `EngineAssociation = 5.8`，当前启用的插件为：

- `ModelingToolsEditorMode`，仅 Editor 目标启用
- `GameplayStateTree`
- `MovieRenderPipeline`
- `MoviePipelineMaskRenderPass`
- `ModelContextProtocol`
- `AllToolsets`
- `FutsalMOTMCP`

`Config/DefaultEngine.ini` 设置了 DX12、SM6、Lumen、虚拟阴影、Ray Tracing、Substrate 和 `r.CustomDepth=3`，同时开启 Python 远程执行。默认 GameMode 为：

```text
/Game/FutsalMOT/Blueprints/BP_NoPawnGameMode.BP_NoPawnGameMode_C
```

### 当前地图配置漂移

`Config/DefaultEngine.ini` 的 `EditorStartupMap` 和 `GameDefaultMap` 仍指向：

```text
/Game/FutsalMOT/Maps/L_Futsal_Demo.L_Futsal_Demo
```

当前仓库实际跟踪的 Futsal 地图是：

```text
Content/FutsalMOT/Maps/L_FutsalCourt.umap
/Game/FutsalMOT/Maps/L_FutsalCourt
```

仓库中没有 `L_Futsal_Demo.umap`。因此不能把默认启动地图描述为可用的 Futsal 场景；运行正式流程前必须在配置或 UE 工程设置中确认使用哪一个正式地图。下面的资产表只能证明资产文件存在，不能证明某个地图实例中已经放置了对应 Actor。

`DefaultGame.ini`、`DefaultEditor.ini` 和 `DefaultEditorPerProjectUserSettings.ini` 仍包含 Third Person 模板名称或模板路径。这些字段不是 FutsalMOT 资产清单的权威来源。

## UE 资产

当前 FutsalMOT 内容目录中的主要资产如下。`.uasset` 和 `.umap` 是二进制文件，文件存在不等于 Blueprint 已编译或关卡运行验收通过。

| 功能 | 资产路径 |
| --- | --- |
| 关卡 | `/Game/FutsalMOT/Maps/L_FutsalCourt` |
| 球员角色 | `/Game/FutsalMOT/Characters/FutsalPlayer/BP_SoccerPlayer` |
| 球员骨架和网格 | `/Game/FutsalMOT/Characters/FutsalPlayer/Skeleton/UNREAL_RIG_Skeleton`、`Meshes/UNREAL_RIG` |
| 球 Actor | `/Game/FutsalMOT/Blueprints/BP_FutsalBall` |
| 球网格 | `/Game/FutsalMOT/Football/StaticMeshes/soccer_ball` |
| 默认 GameMode | `/Game/FutsalMOT/Blueprints/BP_NoPawnGameMode` |
| 场地点 | `/Game/FutsalMOT/Blueprints/BP_FieldKeypoint` |
| Pose Recorder 原型 | `/Game/FutsalMOT/Blueprints/BP_PoseRecorder_Proto` |
| C4 Pose Recorder | `/Game/FutsalMOT/Blueprints/Pose/Recorder/BP_PoseRecorderC4_G0` 至 `G4` |
| Legacy Pose Recorder | `/Game/FutsalMOT/Blueprints/Pose/Recorder/BP_PoseRecorder_Legacy` |
| C4 MRQ BurnIn | `/Game/FutsalMOT/Blueprints/Pose/MRQ/WBP_PoseMRQBurnInC4` |
| Legacy MRQ BurnIn | `/Game/FutsalMOT/Blueprints/Pose/MRQ/WBP_PoseMRQBurnIn_Legacy` |
| Pose SaveGame | `/Game/FutsalMOT/Blueprints/Pose/SaveGame/SG_PoseCapture` |
| Level Sequence | `/Game/FutsalMOT/Sequences/LS_Cam_01`、`LS_Cam_02`、`LS_Cam_03`、`LS_Cam_04` |
| Sequence 速度变体 | `LS_Cam_01_1p0`、`LS_Cam_01_1p5`、`LS_Cam_01_1p75`、`LS_Cam_01_2p0` |
| 动画 | `Animation/`、`Animation/SoccerPlayer/`、`Animation/SoccerSource/`、`Animation/Retarget/` |
| 材质和纹理 | `Materials/`、`Materials/ArtificialTurf/`、`Characters/FutsalPlayer/Materials/`、`Textures/` |

`L_FutsalCourt` 使用 UE 外部化内容布局，仓库中还存在对应的 `Content/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/` 和 `Content/__ExternalObjects__/FutsalMOT/Maps/L_FutsalCourt/` 文件。仅凭这些文件不能确认 Actor 标签、Transform、组件、相机参数或 Sequence binding。

## MCP 与 Unreal Python

外层仓库的 `.mcp.json`、`opencode.json` 和 `.vscode/mcp.json` 将 MCP 服务配置为本机地址：

```text
http://127.0.0.1:8000/mcp
```

本地插件 `Plugins/FutsalMOTMCP` 没有 C++ 模块，依赖 `ToolsetRegistry` 和 `PythonScriptPlugin`。`Content/Python/init_unreal.py` 注册 `FutsalMOTTools`，其实现位于 `Content/Python/futsalmot_tools.py`：

- `run_python_file(path)`：在真实 Unreal Python 环境执行项目根目录内的脚本；绝对路径或相对 UE 项目根的路径均可，但解析后不能越出项目根，且文件必须存在。
- `run_python_code(code)`：在真实 Unreal Python 环境执行非空代码，适合小型诊断。
- 两个工具返回 `success`、`path`、`result`、`log` 字段，其中 `success` 是字符串 `"true"` 或 `"false"`。

这里的执行环境是 UE Editor Python，不是 P1 Python 虚拟环境，也不是受限的组合工具 sandbox。插件是否已在当前 Editor 中加载、MCP 服务是否在线、脚本是否成功运行，都需要在实际 UE Editor 中检查，不能从资产目录静态推断。

## 运行入口

正式数据管线由内层 Python 仓库驱动。典型入口是：

```text
Content/FutsalMOT/code/src/grf_ue_bridge/cli.py
Content/FutsalMOT/code/ue/run_task.py
```

P1 使用 `uv run grf-ue task ...` 生成轨迹和后处理结果；P2 在 Unreal Editor Python 中执行 `ue/run_task.py`。`run_task.py` 读取 P1 解析出的 `resolved-task.json`，不再隐式读取 UE 项目根目录中的旧配置文件。具体命令、模式、输出格式和校验限制以 Python 仓库文档为准。

## 静态检查的边界

以下事实不能由本仓库的文本配置和二进制文件名证明，必须在 UE Editor 中验收：

- `L_FutsalCourt` 是否包含 `Player_L0` 至 `Player_L4`、`Player_R0` 至 `Player_R4`、`Ball_01` 和各相机 Actor。
- Actor 的真实标签、组件类型、Skeletal Mesh、Pose 标签和 Custom Depth 设置。
- C4 Recorder、BurnIn、SaveGame Blueprint 是否编译成功。
- Level Sequence 是否包含正确的 possessable binding、Transform 轨道和 Camera Cut。
- MRQ 是否生成完整 RGB 与 Object-ID Cryptomatte EXR，以及最终图像和姿态是否像素对齐。

不要把 `Content/FutsalMOT/code/ue/archive_c4_diag/` 中的诊断脚本当作正式入口。该目录仍含 Python 文件，所以不能因文档扁平化而删除；其中的脚本属于诊断或历史修复用途。

## 分别提交

修改 UE 资产、`Config/`、`Plugins/`、`.uproject` 或 `.gitmodules` 时，在外层仓库检查 Git 状态。修改 Python 代码、任务配置或内层文档时，进入 `Content/FutsalMOT/code/` 检查另一套 Git 状态。外层 `git add -A` 只会记录内层仓库的 gitlink，不会把内层 Python 文件逐个加入外层。
