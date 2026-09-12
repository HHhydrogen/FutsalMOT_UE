# AGENTS.md

## 仓库结构：两个独立 Git 仓库，外层通过 submodule 链接内层

本项目包含两个独立 Git 仓库，版本历史和提交边界完全分离。外层通过 Git submodule 记录内层仓库的 commit，不把内层 Python 文件复制进外层索引：

1. **外层 UE 项目**（本目录 `D:\projects\FustalMOT_UEDataset`）— git 远程 `git@github.com:HHhydrogen/FutsalMOT_UE.git`，分支 `master`。
2. **内层 Python 数据集代码** `Content/FutsalMOT/code/` — submodule 指向自己的仓库 `git@github.com:HHhydrogen/FutsalMOT_Dataset.git`，分支 `main`。

外层索引只记录 `Content/FutsalMOT/code/` 的 gitlink 和 `.gitmodules` 配置；外层 `git add -A` 不会把内层 Python 文件逐个加入外层。改 Python 代码必须进入 `Content/FutsalMOT/code/` 在内层仓库单独提交；内层 commit 完成后，再在外层更新 submodule 指针。

首次克隆外层仓库后初始化内层仓库：

```powershell
git submodule update --init --recursive
```

检查两个仓库时必须分别执行 `git status`。外层显示的是 submodule 指针状态，内层显示的是 Python 文件状态。

### Submodule 提交与推送顺序

修改内层代码、配置或文档时，必须先完成并推送内层仓库，再提交外层 gitlink：

```powershell
# 1. 在内层仓库检查、测试、提交并推送
git -C Content/FutsalMOT/code status --short --branch
git -C Content/FutsalMOT/code add <仅限本次内层改动>
git -C Content/FutsalMOT/code diff --cached --stat
git -C Content/FutsalMOT/code commit -m "<简体中文提交说明>"
git -C Content/FutsalMOT/code push origin main

# 2. 回到外层仓库记录已经在远程存在的子仓库 commit
git add Content/FutsalMOT/code
git diff --cached --submodule=short -- Content/FutsalMOT/code
git commit -m "<简体中文提交说明>"
git push origin master
```

必须遵守以下顺序：

- 子仓库 push 失败时停止，不得让外层提交或推送一个远程不可取得的 gitlink。
- 外层只提交 mode `160000` 的 `Content/FutsalMOT/code` gitlink，不要把内层文件复制到外层，也不要从外层使用 `git add -f` 强行加入内层文件。
- 外层更新指针前确认内层 `git rev-parse HEAD` 是刚刚推送成功的 commit；用 `git diff --cached --submodule=short` 检查指针变化。
- 两个仓库都可能有未提交改动。不要使用无选择的 `git add -A`；分别检查 `git status --short`，只暂存本次目标文件。
- 外层 clone 后使用 `git submodule update --init --recursive`；也可以使用 `git clone --recurse-submodules <外层仓库地址>`。拉取外层新指针后再次执行该命令。
- `git submodule status` 前缀为 `-` 表示未初始化，`+` 表示工作区 commit 与外层记录不一致；外层提交前应消除意外的 `+`，或明确确认要更新指针。
- 禁止 force-push、跳过 hooks 或把外层 commit 与内层 commit 混写。推送被拒绝时先 fetch 并按实际分支历史处理，不得用强制推送覆盖远程历史。

## 内层 Python 仓库：先读当前技术文档

`Content/FutsalMOT/code/README.md` 是 Python 数据集代码仓库的入口说明；`Content/FutsalMOT/code/docs/DATA_CONTRACT.md` 记录数据格式，`Content/FutsalMOT/code/docs/VALIDATION_AND_LIMITATIONS.md` 记录验证入口和当前限制。进入该目录工作前应先阅读这些文档。要点：

- 推荐入口是 dataset task 单 config（`configs/*.json` 含机器路径并直接入库）：
  ```powershell
  uv run grf-ue task validate configs/pose_smoke_3frames_1cam.json
  uv run grf-ue task export configs/pose_smoke_3frames_1cam.json
  uv run pytest                  # 默认跳过 GRF 集成
  uv run pytest -m grf_integration -q   # 真实 GRF 集成测试
  ```
- **环境隔离**：P1 导出在 Python `.venv`（Python 3.9 固定，勿升级）；P2 导入/渲染脚本在 Unreal Editor Python 内运行，**绝不在 .venv 中运行**，且绝不 import numpy 依赖的模块。JSONL 是两环境唯一接口。
- 当前权威技术文档：`README.md`、`docs/DATA_CONTRACT.md`、`docs/VALIDATION_AND_LIMITATIONS.md`；不再使用 `CLAUDE.md`、`configs/README.md`、`ue/README.md` 或 `docs/` 下的历史设计子目录。
- 提交规范（内层）：未经用户明确确认，不得自动提交或推送；commit message、代码注释、文档字符串和技术文档使用简体中文。

## 外层 UE 项目（本层工作）

- **纯蓝图项目**：无 `Source/`（无 C++），引擎 `5.8`（见 `.uproject`）。改动基本是 `.uasset`/`.umap` 二进制资产，git diff 无法阅读内容。
- 启用的插件：ModelingToolsEditorMode、GameplayStateTree、MovieRenderPipeline、MoviePipelineMaskRenderPass、ModelContextProtocol、AllToolsets、FutsalMOTMCP。
- 当前资产地图为 `/Game/FutsalMOT/Maps/L_FutsalCourt`；`Config/DefaultEngine.ini` 仍将 Editor/Game 默认地图指向不存在的 `L_Futsal_Demo`，执行 UE 任务前必须显式核验当前 Level 和地图配置。
- **Fab 资产目录 `Content/Fab/` 被 gitignore 忽略**——不要在仓库里提交下载的资产；要把资产真正纳入项目，应在 UE 内容浏览器中移动到 Fab 之外（如 `Content/FutsalMOT/`），UE 会自动修引用。不要用文件资源管理器剪切（会断引用）。
- `Saved/`、`Intermediate/`、`DerivedDataCache/` 均为本地生成物，被忽略，不要提交。

## git 约定（整个仓库都遵循）

- **未经用户明确确认，不得自动 commit/push**：每次提交或推送前先询问用户并等待明确确认。
- **commit message 使用简体中文**。
- 外层仓库当前分支 `master`，内层为 `main`。

## Unreal Engine MCP Automation Workflow

**目标**：后续所有 Agent 在处理本项目 UE5.8 相关任务时，**优先通过已配置好的 Unreal MCP 自动操作 Unreal Editor**，而不是要求用户手动回 UE 执行 Python、查日志或读取 Actor 状态。

### 已验证事实

- 当前项目使用 **Unreal Engine 5.8**（见 `.uproject`）。
- 官方 **Unreal MCP** 已启用并运行在本机 UE Editor 中；OpenCode 已通过项目级 MCP 配置（`.mcp.json`）成功连接。
- 已验证可通过 Unreal MCP：
  - 列出 toolsets；
  - 查询当前 Level；
  - 查找 Actor；
  - 读取 Actor Transform；
  - 读取 Actor Components；
  - 读取 UE Output Log。
- 项目已新增自定义 MCP Toolset：**`futsalmot_tools.FutsalMOTTools`**，已验证提供：
  - `run_python_code`
  - `run_python_file`
- 这两个工具运行在**真实 Unreal Python 环境**，可正常 `import unreal`，**不是** `ProgrammaticToolset.execute_tool_script` 的受限 Python sandbox。
- 已验证：
  - `run_python_code` 能执行真实 UE Python（`unreal.log` 正常写日志）；
  - `run_python_file` 能执行项目内 Python 文件，例如 `Content/FutsalMOT/code/ue/*.py`。
- UE 日志可通过 Unreal MCP 的 **Logs Toolset** 查询，重点类别：`LogPython`、`LogBlueprint`、`LogMovieRenderPipeline`、`LogModelContextProtocol`。

### Agent 行为规范

### Unreal MCP 调用规范（已验证）

以下规则用于避免 MCP 工具路由和 Unreal Python API 兼容性错误：

- **工具名必须使用注册后的短名称**。`unreal_describe_toolset` 返回的 schema 中可能显示带模块前缀的描述名，但 `unreal_call_tool` 的 `tool_name` 使用短名称。例如：`IsPIERunning`、`get_current_level`、`find_actors`、`get_actor_transform`、`get_components`、`find_assets`、`load_asset`、`get_properties`、`run_python_code`、`run_python_file`。不要把 `EditorToolset.EditorAppToolset.IsPIERunning`、`editor_toolset.toolsets.scene.SceneTools.get_current_level` 或 `futsalmot_tools.FutsalMOTTools.run_python_code` 作为 `tool_name` 传入。
- `toolset_name` 仍使用 `unreal_list_toolsets` / `unreal_describe_toolset` 返回的完整名称，例如 `EditorToolset.EditorAppToolset`、`editor_toolset.toolsets.scene.SceneTools`、`editor_toolset.toolsets.asset.AssetTools`、`editor_toolset.toolsets.object.ObjectTools`、`futsalmot_tools.FutsalMOTTools`。
- 调用新工具前，先用 `unreal_describe_toolset` 确认该 toolset 的 schema；实际调用时区分 `toolset_name`（完整名）和 `tool_name`（短名）。
- **资产路径不是 UObject 引用**。`/Game/FutsalMOT/Sequences/LS_Cam_01` 这样的字符串可用于 `AssetTools.exists`、`find_assets`、`get_asset_class` 和 `load_asset`，但不能直接作为需要对象引用的参数（例如 Sequencer 的 `sequence`）。先调用 `load_asset`，再把返回的 `{ "refPath": "..." }` 对象原样传给后续工具；不要手工把普通资产路径包装成 `refPath` 来冒充已解析对象。
- **Sequencer 查询流程**：先用 `find_assets` 查找序列，再用 `load_asset` 取得 `LevelSequence` 对象引用，最后将该引用传给 Sequencer 工具。若只需确认绑定名称，也可在真实 Unreal Python 中加载序列并读取 `seq.get_bindings()`；绑定显示名可通过 `binding.get_display_name()` 读取。
- **Actor 查询流程**：使用 `SceneTools.find_actors` 按名称/标签查找，返回的 Actor `{ "refPath": "..." }` 可直接传给 `ActorTools.get_actor_transform`、`get_components` 和 `ObjectTools.get_class`。`find_actors.name` 对应 Actor label 的包含匹配；如果需要精确核对规范对象名，应使用真实 Unreal Python 对 `get_name()` 和 `get_actor_label()` 分别比较。
- **CineCamera 属性读取**：当前 UE 5.8 MCP 原生 `ObjectTools.get_properties` 可能无法序列化 `CineCameraComponent` 的 `current_focal_length`、`field_of_view` 和 `aspect_ratio`，即使属性存在。需要这些字段时，优先使用 `FutsalMOTTools.run_python_code` 的小型诊断，通过 `component.get_editor_property("current_focal_length")`、`component.get_editor_property("filmback")` 和 `component.get_editor_property("field_of_view")` 读取；传感器尺寸从 `filmback.sensor_width` / `sensor_height` 读取。
- **UE 5.8 Python API 兼容性**：本项目已验证 `unreal.EditorLevelLibrary.get_editor_world()` 和 `get_all_level_actors()` 可用但会产生弃用警告。不要未经验证地假设 `unreal.UnrealEditorSubsystem` 等 Subsystem 类型名在当前环境可用；切换 API 前先用 `run_python_code` 做最小存在性检查。失败时优先回退到已验证 API，不要把 API 名称猜测混入大型脚本。
- Python 诊断脚本应保持小而单一用途，并对单个属性/绑定查询使用 `try/except`，避免一个兼容性问题导致整段验证结果丢失。输出结构化 JSON，便于读取 `returnValue.log`。
- 只读验证不得调用 `add_to_scene_from_*`、`remove_from_scene`、`set_actor_transform`、`set_properties`、`save_assets`、`delete`、`move`、`duplicate` 或其他写操作工具。

**UE 任务默认执行顺序**：对任何 Unreal Engine 相关开发、调试、验证任务，默认按以下闭环执行：

```
修改代码 → 通过 FutsalMOTTools.run_python_file 在当前 UE Editor 执行
→ 读取返回结果 → 通过 Unreal MCP 读取相关 UE Logs
→ 自动分析错误 → 修改代码 → 重新执行
```

**不要默认让用户**（只要 Unreal MCP 已提供对应能力，就应由 Agent 自己调用）：

- 手动打开 Python 控制台；
- 手动执行 `.py`；
- 手动复制 Output Log；
- 手动查询 Actor / 查看 Transform / 确认组件。

**什么时候使用 `run_python_file`**：已有或新建的是完整 UE Python 文件（如 `Content/FutsalMOT/code/ue/build_*.py`、`read_*.py`、`export_*.py`、`render_*.py`），默认使用 `FutsalMOTTools.run_python_file`，**不要让用户复制代码到 UE Python Console**。

**什么时候使用 `run_python_code`**：仅用于小型诊断和快速状态查询，例如 `import unreal`、查询一个对象、打印一个属性、验证某个 API 是否存在、输出一条 UE log。**不要把大型多步骤逻辑塞进 `run_python_code`**。

**什么时候使用 Unreal MCP 原生工具**：如果只是查询 Editor 状态，优先使用 Unreal MCP 原生 Toolset（Level 查询、Actor 查找、Transform、Components、Asset 查询、Logs、Sequencer / AutomationTest 等），而不是写 Python。

**原则**：
- 已有 MCP 原生 Tool → **优先原生 Tool**；
- 需要真实 Unreal Python → **`FutsalMOTTools`**；
- **禁止误用 `ProgrammaticToolset`**。

### 禁止误用 ProgrammaticToolset

`ProgrammaticToolset.execute_tool_script` 是**受限 sandbox**，不能替代真实 Unreal Python。它适合组合 MCP Tools，但**不要**用它执行依赖 `import unreal` 的项目 UE Python 脚本。

### 自动诊断要求

当 `run_python_file` 或 `run_python_code` 失败时：

1. 先读取工具返回的 `success/result/log`；
2. 再读取相关 UE Output Log；
3. 优先自行定位：Python exception、Blueprint compile error、Movie Render Pipeline error、MCP error；
4. 自动修复并重试。

**不要在第一次报错后立即把问题转交给用户。**

### 只有这些情况才要求用户手动操作 UE

- 新插件 / 新 Python Toolset 必须**完整重启 Unreal Editor**；
- API 没有 Blueprint / Python / MCP 暴露；
- 必须进行视觉人工验收（例如最终 RGB / Pose overlay 是否美观、是否肉眼对齐）；
- 必须点击某个无法自动化的 Editor UI；
- 操作存在较高破坏风险，需要用户确认。

如果只是普通脚本执行或读取日志，**不属于人工操作范围**。

### 当前 MCP 基础设施位置

记录：`Plugins/FutsalMOTMCP/`，其中至少包括：

- `Content/Python/init_unreal.py`
- `Content/Python/futsalmot_tools.py`

**不要随意删除或重构该插件。** 若修改 `futsalmot_tools.py` 后新代码没有生效，要意识到 Unreal Python 模块可能已经缓存；必要时明确要求**完整重启 UE**，而不是反复调用 `RefreshTools` 假设模块已热重载。

### Git 注意事项

- **不要提交** `__pycache__/`、`*.pyc`（已在根 `.gitignore` 补充忽略）。
- 保持本项目原有「双 Git 仓库」规则：
  - UE 资产 / `Plugins/` / `.uproject` / `.gitmodules` 等属于**外层 UE 仓库**；
  - `Content/FutsalMOT/code/` 的 Python 文件和内层 commit 属于**内层 Python 数据集仓库**；
  - 外层只更新 submodule gitlink，不要把两个仓库的 commit 混淆。

> For Unreal Engine tasks in this project, do not ask the user to manually run UE Python unless MCP automation has been attempted and an actual API/tooling limitation has been confirmed.
