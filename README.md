# FutsalMOT Unreal Engine 项目

本仓库是 FutsalMOT 合成多目标跟踪数据集的 Unreal Engine 资产仓库（UE 5.8）。数据生成代码位于 `Content/FutsalMOT/code/` 下的独立 Git 仓库。

## 入口索引

| 主题 | 文档 |
| --- | --- |
| 项目架构（Master 定义、生产/输入/动画/序列/外观链） | `Docs/Architecture/PROJECT_ARCHITECTURE.md` |
| 资产目录树与分类（PRODUCTION / TEMPLATE_BASELINE / EXPERIMENTAL / ARCHIVE） | `Docs/Architecture/ASSET_STRUCTURE.md` |
| Phase 5A 整理报告 | `Docs/Architecture/PROJECT_CLEANUP_REPORT.md` |
| 历史阶段报告（Phase 1–4） | `Docs/History/PhaseReports/` |
| 数据管线与数据格式 | `Content/FutsalMOT/code/README.md`、`Content/FutsalMOT/code/docs/DATA_CONTRACT.md`、`Content/FutsalMOT/code/docs/VALIDATION_AND_LIMITATIONS.md` |

## 当前生产架构（摘要）

```
MASTER_CHARACTER          = /Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase
MASTER_ANIMBP             = /Game/FutsalMOT/Animation/Source/ABP_FutsalSource
MASTER_ANIMATION_SKELETON = /Game/Characters/Mannequins/Meshes/SK_Mannequin
MASTER_PREVIEW_MESH       = /Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple
UNREAL_RIG_ROLE           = APPEARANCE_PROTOTYPE
```

```
L_FutsalCourt
  └─ 10× Player actor（类 = BP_FutsalCharacterBase_C，Mesh = SKM_Quinn_Simple，AnimClass = ABP_FutsalSource_C）
       └─ BP_FutsalCharacterBase → BPI_FutsalAnimationSource → ABP_FutsalSource → SK_Mannequin
```

生产依赖已不含 `/Game/ThirdPerson/**`、`/Game/Input/**`、`ABP_FutsalPlayer`、`BP_ThirdPersonCharacter`。

## 仓库边界

| 仓库 | 根目录 | 负责内容 | 当前 Git 边界 |
| --- | --- | --- | --- |
| UE 仓库 | `D:/projects/FutsalMOT_UEDataset` | `.uproject`、`Config/`、插件、UE 内容资产和内层 submodule 指针 | 只记录 gitlink，不逐文件跟踪内层内容 |
| Python 仓库 | `Content/FutsalMOT/code/` | GRF 导出、任务配置、UE Python、标注后处理和测试 | 独立仓库，需进入该目录单独操作 |

外层仓库当前没有 `Source/`、C++、`Build.cs` 或 `Target.cs`，项目实现边界是 Blueprint 和内容资产。`Saved/`、`Intermediate/`、`DerivedDataCache/`、`Content/Fab/` 不属于提交内容；Fab 资产若纳入项目，应在 UE 内容浏览器中移到 `Content/Fab/` 之外。

首次克隆外层仓库后执行 `git submodule update --init --recursive`。外层 commit 只更新 `Content/FutsalMOT/code` 的 gitlink；内层代码、配置和文档的提交必须先在内层仓库完成。

## UE 工程配置

工程文件 `FustalMOT_UEDataset.uproject` 声明 `EngineAssociation = 5.8`，启用插件：`ModelingToolsEditorMode`、`GameplayStateTree`、`MovieRenderPipeline`、`MoviePipelineMaskRenderPass`、`ModelContextProtocol`、`AllToolsets`、`FutsalMOTMCP`。

`Config/DefaultEngine.ini` 设置 DX12/SM6/Lumen/虚拟阴影/Ray Tracing/Substrate 与 `r.CustomDepth=3`，并开启 Python 远程执行。默认 GameMode 为 `/Game/FutsalMOT/Blueprints/BP_NoPawnGameMode.BP_NoPawnGameMode_C`。

### 地图配置漂移（未修复）

`Config/DefaultEngine.ini` 的 `EditorStartupMap` / `GameDefaultMap` 仍指向 `/Game/FutsalMOT/Maps/L_Futsal_Demo`，但仓库实际跟踪的正式地图是 `/Game/FutsalMOT/Maps/L_FutsalCourt`，且不存在 `L_Futsal_Demo.umap`。运行正式流程前必须在工程设置中确认地图。

## MCP 与 Unreal Python

`.mcp.json`、`opencode.json`、`.vscode/mcp.json` 将 MCP 服务配置为 `http://127.0.0.1:8000/mcp`。本地插件 `Plugins/FutsalMOTMCP`（无 C++ 模块）通过 `Content/Python/init_unreal.py` 注册 `FutsalMOTTools`：

- `run_python_file(path)`：在真实 Unreal Python 环境执行项目根目录内的脚本。
- `run_python_code(code)`：执行小型诊断代码。

执行环境是 UE Editor Python，不是 P1 虚拟环境，也不是受限 sandbox。插件加载状态与 MCP 在线状态必须在实际 Editor 中检查。

## 运行入口

正式数据管线由内层 Python 仓库驱动（`Content/FutsalMOT/code/src/grf_ue_bridge/cli.py`、`Content/FutsalMOT/code/ue/run_task.py`）。P1 用 `uv run grf-ue task ...`，P2 在 UE Editor Python 中执行 `ue/run_task.py`。具体命令与校验限制以 Python 仓库文档为准。

## 静态检查的边界

`.uasset` / `.umap` 为二进制，文件存在或文本配置不能证明：关卡内 Actor 与绑定、组件与 Mesh/AnimClass、Level Sequence possessable/Camera Cut、MRQ RGB/Object-ID 输出与像素对齐。这些必须在 UE Editor 中验收。

## 分别提交

修改 UE 资产、`Config/`、`Plugins/`、`.uproject`、`.gitmodules` 时检查外层 Git 状态；修改 Python 代码、任务配置或内层文档时进入 `Content/FutsalMOT/code/` 检查内层 Git 状态。外层 `git add -A` 只记录内层仓库 gitlink。
