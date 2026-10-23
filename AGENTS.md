# AGENTS.md

## 最新停止与存储约束（2026-10-23晚）

- 用户要求迁移完数据后结束今日任务；定时任务`futsalposetrack`已暂停。未经用户重新要求继续，不启动渲染、训练、恢复驱动或新研究开发。
- 今后所有数据实际写入G盘：正式数据`G:/FutsalMOT_Dataset`，研究输入/权重/检查点/结果`G:/FutsalMOT_Research`，UE与P1工作数据`G:/FutsalMOT_Workspace`。D盘只保留代码、UE资产与必需构建缓存；新代码先核验实际resolve路径，禁止默认回落D盘存数据。
- `D:/projects/FutsalMOT_Research`、项目`Saved`及P1数据目录保留为迁移后的兼容目录联接；清理/统计必须不跟随联接，不重复复制其G盘目标。迁移收据位于`G:/FutsalMOT_Workspace/migration_20261023`。
- MCP仍只执行项目根内的真实代码路径。Saved移到G后，不直接用`run_python_file`执行解析后位于G盘的Saved辅助脚本；恢复时将必需入口代码放到D盘项目`tools/`或`ue/`，从G读写数据，不扩大Toolset任意文件执行权限。旧Saved驱动不能直接重启。
- v3六臂训练和固定真实检测关联已全部结束，不重启旧驱动。30秒长窗首1048蓝a01因磁盘满失败，不能声称完成；失败记录保留。v4数学核心已验，完整Trainer仍为未测试草稿，不具备训练准入。

## 当前研究方向（2026-10-23）

- 用户最新执行偏好：以实现、导出和实验为主；已通过方法直接复用，只对新功能做一次必要测试/真实执行，后续seed自动检查帧/身份/失败状态。不重复逐模型近景、媒体hash、全量像素审计或无变化复查。
- 四seed位置监督试产已由`Saved/Pose17Development/run_location_pilot_a01.py`串行执行，状态看`location_pilot_driver_a01.json`，正常时不重复启动。显式120帧契约仅1042/1044/1048 train及1102 synthetic_dev，四机位4K；未知visibility与位置有效性分开，试产不冒充正式COCO可见性数据。v1不变、真实final test封存。
- 旧CPU渲染蒙皮路径已在submit前禁用，以免再次进入Lumen LocalVF/View崩溃。MCP文件PRIVATE/字面代码独立globals已在真实Editor热替换验证；显式sys.modules会话保留。退出期另有Py_FinalizeEx→PyGC_Collect崩溃，具体坏对象未定位；批次内复用Editor，不为复验频繁重启，正常收尾再观察退出终态。见`Docs/UE_CRASH_FINDINGS_20261023.md`。

- 用户最新加速要求：004通过后直接复用各模型，不反复逐角色校验。004组合GPU-LBS短诊断现已通过真实切换/三机位配对/头深度及独立目视，收据`Saved/Pose17Development/player004_gpu_lbs_dynamic_head_review_a02.json`。不再运行005–009逐角色三机位近景，改一次十人覆盖003–009的四机位联合小样；保留必要自动身份/骨架/manifest/同步/恢复门禁，抽样仅四张全员总览，不把抽样当全像素审计。

- 用户已将论文重心调整为COCO17姿态数据与姿态跟踪，执行路线见`Docs/POSE_RESEARCH_ROADMAP.md`。旧bbox试验保留证据，不自动继续扫描比例或重启已中断R5。
- v1八组没有Pose；新Pose17必须独立输出，不能把历史12点文件补名为17点或事后伪造同帧采样。
- 鼻眼耳需要绑定实际角色几何的校准。场景中隐藏驱动CharacterMesh0与可见MPFBVisual并存，必须核实实际渲染mesh后采样。
- 地板独立seed随机流，不扰动运动/天气/角色；同运动不同地板配对保持同split。地板颜色丰富度属于实验因素，不直接当作已证明的泛化收益。
- 真实UE采样和遮挡标签未验证前不得启用正式Pose17批量生产；CPU单测不替代MRQ同步和视觉验收。
- 当前诊断限制：`player004_closeup_a01`及无网格切换的`player003_closeup_warmup_a06`均在8帧预热/Lumen MeshCardCapture阶段出现LocalVF/View缓冲绑定崩溃，零有效帧。不要自动重复相同CPU渲染配置或把失败归因于004角色资产；默认旧CPU路径不具备正式批产准入。
- GPU-render/CPU-LBS已完成003/004近景及`joint_seed1048_a01_gpu_lbs`七模型十人四机位联合短动作诊断：真实GRF源100..109、40张4K RGB/40份EXR/400实体记录，采样、场景恢复及四张全员总览通过。收据`Saved/Pose17Development/joint_seed1048_a01_root_review.json`。这不是正式Pose批次；visibility保持unknown，长动作和关节遮挡证据尚待完成。独立重放机位世界点最大差4.274e-6m，导出保留各机位原始world，不平均或放宽严格共享去重。不再逐005–009重复近景，不套用旧CPU override回退。

## 当前批次与清理边界（2026-10-22）

- 无号码4K正式批次已完成8组、八天气、32相机序列，20116 RGB及同数mask。旧16/32组计划不再执行。
- 正式数据仅位于`G:/FutsalMOT_Dataset/v1_no_numbers_4k`，布局为`groups/seed_XXXXXXXX/cameras/`；读取group的clip引用，不硬编码`clips/clip_000`或父目录深度。
- 研究代码在内层`experiments/sim2real`，数据和GPU结果实际在`G:/FutsalMOT_Research`；旧D盘同名路径仅保留兼容联接。研究images目录联接到正式RGB，禁止递归跟随联接清理源数据。
- UE渲染与GPU训练串行；全部本轮完成、Editor安全退出后才能启动GPU实验。比较固定真实标注及更新预算的真实/真实加合成对照，不预设提升。
- AutoSave通过项目DefaultEditorPerProjectUserSettings和本机配置关闭；默认地图为L_FutsalCourt。
- 删除临时资产先核对引用，再通过UE API执行；不从文件系统删除uasset。删除Saved、缓存或数据根其他目录时先核验绝对边界，不跟随junction；保留生产轨迹、冻结代码、关键收据及未完成号码开发。
- 已结束持久生产会话可保留其自有dirty包，但后续操作必须匹配checkpoint且无范围外改动，不能将retained伪装成restored。
- 用户当前明确要求的提交/推送视为本轮授权，不重复索要确认；未授权时仍遵循下方默认限制。未完成号码实现与资产不纳入本轮提交。

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

### MPFB Player_N 生产 SOP

新增或维护 MPFB Player_N 时，必须先阅读并遵循 [MPFB Player Production SOP](Docs/MPFB_PLAYER_PRODUCTION_SOP.md)。该文档固化了已通过验收的 Player_002 流程：每个角色可独立使用身高、体型和外观设计，但所有角色共享 MPFB Core v1 的 `SKEL_MPFB_Base`、`IKR_MPFB_Base`、`RTG_FutsalPlayerBase_To_MPFB` 和 `ABP_MPFB_RuntimeRetarget`。

生产流程的固定边界是：源 Blender 使用 `METRIC / METERS / 1.0`；原始 Human/Rig 保持 `1,1,1`；只在临时 Export Copy 对 Mesh、Armature Data 和 Shape Keys 做厘米坐标转换；FBX wrapper 必须为 `Human_rig`；实际使用纹理必须显式复制到 `export/Textures/` 并在 UE 中单独导入。不要把 Player_002 的 Average 体型或固定身高当作后续角色的兼容性标准。

SOP 中标记为 `NOT VERIFIED` 的 UE Import Data 或 Blender Axis/Apply Transform 参数不得凭经验猜测；使用最后一次人工验证的导入预设。UE 5.8 同一类 Python/MCP API 连续失败两次后停止并转为 `MANUAL_REQUIRED`，不要继续尝试反射 API。

- **C++ 优先项目**：项目使用 Unreal Engine 5.8，已有 `Source/` runtime module、`AFutsalPlayerBase` 和 `UFutsalPlayerAnimInstance`。后续新增运行时逻辑、稳定的数据契约、跨 Blueprint 复用的行为和需要自动化测试的功能，优先使用 C++ 实现；只有在 C++、Python 或 MCP 无法覆盖，或功能明确属于资产编排/视觉配置时，才使用 Blueprint。AnimGraph、BlendSpace、状态机、Control Rig、材质参数和一次性资产配置仍可保留在资产侧。
- 启用的插件：ModelingToolsEditorMode、GameplayStateTree、MovieRenderPipeline、MoviePipelineMaskRenderPass、ModelContextProtocol、AllToolsets、FutsalMOTMCP。
- 当前资产地图及Editor/Game默认地图均为 `/Game/FutsalMOT/Maps/L_FutsalCourt`；执行UE任务前仍须显式核验当前Level。
- **地图切换与 UWorld 生命周期**：地图切换必须通过 Unreal MCP 原生 `SceneTools.load_level`。切勿在切图期间通过 `unreal.load_asset()` 或 `unreal.load_object()` 取得或保留 `UWorld`；UE 5.8 在该 World 引用仍存活时调用 `EditorLoadingAndSavingUtils.load_map()` 可能触发 `World Memory Leaks` 断言并崩溃。`load_level` 返回后，另发一个独立的只读调用核验当前 Level 和所需 Actor。若原生 `load_level` 不可用，停止并报告 `MANUAL_REQUIRED`，不得猜测 Python 切图回退方案。
- **episode appearance 前置门禁**：执行 apply 或 restore 前，必须先运行只读 appearance 诊断，并确认当前 Level 精确为 `/Game/FutsalMOT/Maps/L_FutsalCourt`、十名映射球员各自唯一且存在、Actor/资产 package clean、关键资产存在且 class 符合。诊断未通过或信息不完整时，不得开始外观 apply/restore、Task 7 mutation 或 MRQ。
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
- 保持本项目原有「双 Git 仓库」规则：
  - UE 资产 / `Plugins/` / `.uproject` / `.gitmodules` 等属于**外层 UE 仓库**；
  - `Content/FutsalMOT/code/` 的 Python 文件和内层 commit 属于**内层 Python 数据集仓库**；
  - 外层只更新 submodule gitlink，不要把两个仓库的 commit 混淆。

> For Unreal Engine tasks in this project, do not ask the user to manually run UE Python unless MCP automation has been attempted and an actual API/tooling limitation has been confirmed.
