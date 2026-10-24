# Unreal Engine 项目自动化工作流

长期技术约定；运行进度见项目根任务状态。

## UE项目原则

### MPFB Player_N 生产 SOP

新增或维护 MPFB Player_N 时，必须先阅读并遵循 [MPFB Player Production SOP](../production/MPFB_PLAYER_PRODUCTION_SOP.md)。该文档固化了已通过验收的 Player_002 流程：每个角色可独立使用身高、体型和外观设计，但所有角色共享 MPFB Core v1 的 `SKEL_MPFB_Base`、`IKR_MPFB_Base`、`RTG_FutsalPlayerBase_To_MPFB` 和 `ABP_MPFB_RuntimeRetarget`。

生产流程的固定边界是：源 Blender 使用 `METRIC / METERS / 1.0`；原始 Human/Rig 保持 `1,1,1`；只在临时 Export Copy 对 Mesh、Armature Data 和 Shape Keys 做厘米坐标转换；FBX wrapper 必须为 `Human_rig`；实际使用纹理必须显式复制到 `export/Textures/` 并在 UE 中单独导入。不要把 Player_002 的 Average 体型或固定身高当作后续角色的兼容性标准。

SOP 中标记为 `NOT VERIFIED` 的 UE Import Data 或 Blender Axis/Apply Transform 参数不得凭经验猜测；使用最后一次人工验证的导入预设。UE 5.8 同一类 Python/MCP API 连续失败两次后停止并转为 `MANUAL_REQUIRED`，不要继续尝试反射 API。

- **C++ 优先项目**：项目使用 Unreal Engine 5.8，已有 `Source/` runtime module、`AFutsalPlayerBase` 和 `UFutsalPlayerAnimInstance`。后续新增运行时逻辑、稳定的数据契约、跨 Blueprint 复用的行为和需要自动化测试的功能，优先使用 C++ 实现；只有在 C++、Python 或 MCP 无法覆盖，或功能明确属于资产编排/视觉配置时，才使用 Blueprint。AnimGraph、BlendSpace、状态机、Control Rig、材质参数和一次性资产配置仍可保留在资产侧。
- 启用的插件：ModelingToolsEditorMode、GameplayStateTree、MovieRenderPipeline、MoviePipelineMaskRenderPass、ModelContextProtocol、AllToolsets、FutsalMOTMCP。
- 当前资产地图及Editor/Game默认地图均为 `/Game/FutsalMOT/Maps/L_FutsalCourt`；执行UE任务前仍须显式核验当前Level。
- **地图切换与 UWorld 生命周期**：地图切换必须通过 Unreal MCP 原生 `SceneTools.load_level`。切勿在切图期间通过 `unreal.load_asset()` 或 `unreal.load_object()` 取得或保留 `UWorld`；UE 5.8 在该 World 引用仍存活时调用 `EditorLoadingAndSavingUtils.load_map()` 可能触发 `World Memory Leaks` 断言并崩溃。`load_level` 返回后，另发一个独立的只读调用核验当前 Level 和所需 Actor。若原生 `load_level` 不可用，停止并报告 `MANUAL_REQUIRED`，不得猜测 Python 切图回退方案。
- **episode appearance 前置门禁**：执行 apply 或 restore 前，必须先运行只读 appearance 诊断，并确认当前 Level 精确为 `/Game/FutsalMOT/Maps/L_FutsalCourt`、十名映射球员各自唯一且存在、Actor/资产 package clean、关键资产存在且 class 符合。诊断未通过或信息不完整时，不得开始外观 apply/restore、Task 7 mutation 或 MRQ。
- **Fab 资产目录 `Content/Fab/` 被 gitignore 忽略**——不要在仓库里提交下载的资产；要把资产真正纳入项目，应在 UE 内容浏览器中移动到 Fab 之外（如 `Content/FutsalMOT/`），UE 会自动修引用。不要用文件资源管理器剪切（会断引用）。
- `Saved/`、`Intermediate/`、`DerivedDataCache/` 均为本地生成物，被忽略，不要提交。

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

### UE 自动重启与 MCP 重连

- 当 UE 5.8 因 C++ module、插件、Python Toolset 或 Editor 状态必须重启时，Agent 应优先自行完成重启闭环，不要默认要求用户手动关闭、重新打开或复制命令。
- 重启前必须只读检查当前 Level、PIE/Simulate 状态、MRQ 是否运行、dirty packages、打开的关键资产和未完成的 appearance rollback/application report。存在未保存用户改动、运行中的 MRQ 或无法确认的高风险状态时，停止并报告 `MANUAL_REQUIRED`，不得强制结束 Editor。
- 可安全重启时，按以下顺序执行：停止可停止的 PIE/MRQ 会话；关闭 Unreal Editor；使用当前项目绑定的 UE 5.8 工具链重新编译所需 target；从项目 `.uproject` 启动 Editor；等待项目插件和 `FutsalMOTMCP` 初始化；通过 MCP 重新连接并继续任务。
- 重启后的成功条件必须用新鲜状态核验：`FutsalMOT` module 在 UE 日志中成功加载；没有 `Incompatible or missing module`、`Still incompatible or missing module`、`different engine version` 或编译失败；MCP toolset 可列出；`FutsalMOTTools.run_python_code` 或 `run_python_file` 可执行；当前 Level、关键 Actor 和 dirty package 状态符合任务门禁。
- MCP 会话重启后可能需要等待并重试连接。重试期间读取新的 UE `LogModuleManager`、`LogPython`、`LogModelContextProtocol` 和相关构建日志；不得用历史日志替代本次启动证据。连接无法恢复或同一类启动/API 操作连续失败两次时，停止并报告 `MANUAL_REQUIRED`，不要继续猜测重连方式。
- 重启验证只证明 Editor/module/MCP 生命周期恢复，不等于地图、Blueprint、Sequence、资产、MRQ 或视觉契约已经通过；恢复后仍必须重新执行对应的只读诊断。

### 截图与多模态视觉验收

- UE 视觉验收应优先由 Agent 通过 Unreal MCP 获取当前视口或编辑器截图，并使用模型多模态能力检查；不要默认要求用户手工逐张查看或手动执行截图命令。
- 截图验收必须绑定明确的 Level、camera、Sequence、frame index、分辨率和渲染状态。对 RGB、Instance-ID mask、jersey-number mask 或 Pose overlay，优先获取同一 camera/frame 的配对截图或对应本地图像文件。
- 球衣号码至少检查：背面号码可见；正面号码为空；身体或其他 Actor 遮挡时号码 mask 正确消失；号码位置、朝向、缩放和背部贴合合理；号码跟随 `spine_03` 或等效共享骨骼运动；十名球员号码与 manifest 唯一且一致。
- 多模态截图只能证明可见的视觉现象，不能单独证明数据契约。必须同时读取 PNG/EXR 可用的像素统计、`annotations.jsonl`、`render_summary.json`、manifest、frame index 和 UE 日志，程序化核验 mask 非零像素、号码 bbox tight bounds、帧集合、分辨率以及 RGB/mask/pose 同步。
- 截图与像素/JSON/日志证据不一致、截图缺失、画面无法判断遮挡或帧身份、或截图接口失败时，验收保持 fail-closed；不得据此创建正式号码资产、执行 appearance mutation、提交正式 MRQ 或切换 v2 smoke config。
- 视觉验收通过后仍需重新执行 appearance preflight、资产 class/package clean、restore 和 MRQ 完整性检查。截图通过不替代 `task audit`、annotation validator、manifest 校验或 restore evidence。

### C++ 优先决策规则

- 新增运行时系统、Actor/Component 行为、动画数据采集、轨迹播放适配、状态同步、输入契约和可复用工具时，先设计 C++ API 和自动化测试边界，再决定是否需要 Blueprint 暴露属性或事件。
- 现有 Blueprint 只有在满足以下条件之一时才继续扩展：UE API 只通过 Blueprint 暴露；功能是 AnimGraph、BlendSpace、状态机、Control Rig、材质/镜头/Sequence 配置；或必须由设计资产直接编辑才能完成。
- 不要为了“纯 C++”重写已经稳定且适合资产表达的 Pose 组装图、状态机、动画资源引用、FootIK Control Rig 或相机关键帧。
- 当 C++ 与 Blueprint 都可实现时，优先 C++，并把 Blueprint 限制为数据配置、资产引用和必要的编辑器暴露层。
- C++ 改动必须先验证 module/build、反射属性名称、Blueprint parent/接口兼容性和现有资产引用；未经验证不得直接重设 canonical Blueprint parent 或删除旧变量。
- C++ 编译、UE Editor reload、Blueprint compile 和运行时验证是不同门槛；一个通过不代表其它门槛自动通过。

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

### UE MCP 使用细节与已验证限制

- **先描述再调用**：新工具必须先调用 `unreal_describe_toolset` 确认 schema。`toolset_name` 使用完整注册名，`tool_name` 使用 schema 中的短名；不要把显示名称中的模块前缀直接传给 `unreal_call_tool`。
- **资产路径和 UObject 引用分离**：`AssetTools.exists/find_assets/get_asset_class/get_asset_tags/get_dependencies/get_referencers` 接收字符串路径；需要对象引用的参数必须先 `load_asset`，再把返回的 `{ "refPath": ... }` 原样传递。不要手工构造 `refPath`。
- **地图状态先核验**：`SceneTools.get_current_level` 是只读首选。地图切换只使用原生 `SceneTools.load_level`；切换调用返回后，在独立调用中重新核验 `get_current_level` 和 Actor。禁止在切图过程中持有由 `unreal.load_asset()` / `unreal.load_object()` 获得的 `UWorld`，禁止用 `EditorLoadingAndSavingUtils.load_map()` 猜测回退。若原生加载不可用，停止并报告 `MANUAL_REQUIRED`。地图未加载并独立核验成功前不得修改关卡资产。
- **地图/Actor 外部包**：关卡中的 External Actors 会作为 `/Game/__ExternalActors__/...` 反向引用出现。角色 Blueprint、AnimBP、Mesh 或 Sequence 的 referencer 不能只看主 `.umap` 路径，必须同时检查 External Actors。
- **Sequencer 查询**：先 `find_assets` 查找 `LevelSequence`，再 `load_asset`。真实 UE Python 可读取 `seq.get_bindings()`、`binding.get_display_name()`、`binding.get_possessed_object_class()`、`binding.get_tracks()` 和播放范围。验证正式序列时，要求球员绑定数量、名称、class、相机绑定、Camera Cut、播放帧率/范围和关键轨道都通过。
- **Sequencer 重绑限制**：当前 UE 5.8 Python `SequencerBindingProxy` 暴露读取、添加轨道、移动绑定内容和删除绑定等能力，但没有可靠的“原位重绑现有 possessable 并保留 GUID/全部轨道”的通用接口。若需要更换绑定 class，优先复制新 Sequence、迁移轨道到当前 Actor、逐项对比相机/轨道后再替换旧资产；不得未经验证删除并重建绑定。
- **相机属性读取**：CineCamera 的 `current_focal_length`、`field_of_view`、`aspect_ratio` 可能无法由原生 ObjectTools 正确序列化。使用真实 UE Python 的 `get_editor_property` 读取；Filmback 通过 `filmback.sensor_width/sensor_height` 核对。相机位置/旋转、焦距、Filmback、分辨率和关键帧应分别记录。
- **AssetTools 删除限制**：`AssetTools.delete`、`EditorAssetLibrary.delete_asset` 或 `EditorAssetSubsystem.delete_loaded_asset` 返回 `false` 时，不得改用文件系统删除 `.uasset`。先检查 `can_edit_asset/is_checked_out/is_dirty/get_referencers`、打开的资产编辑器和 UE 日志；如果仍无法删除，保留资产并报告 Editor API 限制。
- **移动/重命名闭包**：项目自有资产必须通过 AssetTools move/rename，让 UE 更新引用；移动后重新查询新路径的 referencers、Blueprint/AnimBP 加载状态和代码/配置软路径。不要用文件管理器剪切 `.uasset`。
- **模板和共享资产保护**：`/Game/Characters/Mannequins/**`、贴图、材质、网格、骨架、物理资产和共享 Pose/MRQ 依赖不能因零引用统计而自动删除。全项目减重必须结合硬引用、软引用、管理引用、搜索名称和文本配置扫描。
- **真实 UE Python 与 sandbox 隔离**：`FutsalMOTTools.run_python_code/run_python_file` 才能执行 `import unreal`；`ProgrammaticToolset.execute_tool_script` 只用于组合 MCP 工具，禁止在其中运行项目 UE Python。
- **诊断脚本保持单一用途**：小型诊断输出结构化 JSON，并对单个属性/绑定使用 `try/except`。完整流程写入项目内 `.py` 文件后使用 `run_python_file`，不要把多步骤资产迁移塞进 `run_python_code`。
- **失败闭环**：任何 UE Python/MCP 调用失败，先读 `success/result/log`，再查询 `LogPython`、`LogBlueprint`、`LogMovieRenderPipeline`、`LogModelContextProtocol`；修复后重试。不要把第一次异常直接转交用户。
- **验证结果新鲜性**：声称编译、测试、资产存在、绑定正确或删除成功前，必须在当前状态重新执行对应命令/查询，并记录实际返回结果。历史日志只能作为背景，不能替代当前验证。
- **自定义日志路径**：通过`-abslog`启动Editor时，当前`FutsalMOTTools`失败返回的`log`可能仍摘取默认日志目录中的旧会话。失败后必须核对时间戳，优先使用原生`LogsToolset.GetLogEntries`的当前会话记录或本次启动收据中的明确abslog；不得按返回的历史异常反复修改已经修复的代码。

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
- UE资产、C++、插件及 `Content/FutsalMOT/code/` 统一由根Git管理；不重新建立submodule或嵌套Git。

> For Unreal Engine tasks in this project, do not ask the user to manually run UE Python unless MCP automation has been attempted and an actual API/tooling limitation has been confirmed.
