# AGENTS.md

## 仓库结构：两个互相独立的 git 仓库

本项目是**两个嵌套的独立 git 仓库**，版本控制完全分离：

1. **外层 UE 项目**（本目录 `D:\projects\FustalMOT_UEDataset`）— git 远程 `git@github.com:HHhydrogen/FutsalMOT_UE.git`，分支 `master`。
2. **内层 Python 数据集代码** `Content/FutsalMOT/code/` — **它是自己的 git 仓库**，有自己的远程 `git@github.com:HHhydrogen/FutsalMOT_Dataset.git`，分支 `main`。

`.gitignore` 已把 `Content/FutsalMOT/code/` 整目录忽略——**在外层仓库 `git add -A` 永远不会包含 Python 代码**。改 Python 代码必须 `cd` 进 `Content/FutsalMOT/code/` 单独提交/推送。

## 内层 Python 仓库：先读它的 CLAUDE.md

`Content/FutsalMOT/code/CLAUDE.md` 是 Python 代码库的权威指南（架构、命令、约定），**在该目录工作前必读**。要点：

- 推荐入口是 dataset task 单 config（`configs/*.json` 含机器路径并直接入库）：
  ```powershell
  uv run grf-ue task validate configs/pose_smoke_3frames_1cam.json
  uv run grf-ue task export configs/pose_smoke_3frames_1cam.json
  uv run pytest                  # 默认跳过 GRF 集成
  uv run pytest -m grf_integration -q   # 真实 GRF 集成测试
  ```
- **环境隔离**：P1 导出在 Python `.venv`（Python 3.9 固定，勿升级）；P2 导入/渲染脚本在 Unreal Editor Python 内运行，**绝不在 .venv 中运行**，且绝不 import numpy 依赖的模块。JSONL 是两环境唯一接口。
- 提交规范（内层）：绝不自动提交、commit/注释/文档用简体中文。

## 外层 UE 项目（本层工作）

- **纯蓝图项目**：无 `Source/`（无 C++），引擎 `5.8`（见 `.uproject`）。改动基本是 `.uasset`/`.umap` 二进制资产，git diff 无法阅读内容。
- 启用的插件：ModelingToolsEditorMode、GameplayStateTree、MovieRenderPipeline、MoviePipelineMaskRenderPass（MRQ 渲染管线相关）。
- **Fab 资产目录 `Content/Fab/` 被 gitignore 忽略**——不要在仓库里提交下载的资产；要把资产真正纳入项目，应在 UE 内容浏览器中移动到 Fab 之外（如 `Content/FutsalMOT/`），UE 会自动修引用。不要用文件资源管理器剪切（会断引用）。
- `Saved/`、`Intermediate/`、`DerivedDataCache/` 均为本地生成物，被忽略，不要提交。

## git 约定（整个仓库都遵循）

- **绝不自动 commit/push**：每次提交前先询问用户并等待明确确认。
- **commit message 使用简体中文**。
- 外层仓库当前分支 `master`，内层为 `main`。
