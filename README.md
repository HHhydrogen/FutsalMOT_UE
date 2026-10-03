# FutsalMOT Unreal Engine 项目

本仓库是 FutsalMOT 合成多目标跟踪数据集的 Unreal Engine 5.8 项目，包含 UE 资产、C++ runtime module、插件和 Python 数据集代码 submodule。

## 当前项目

- 正式地图：`/Game/FutsalMOT/Maps/L_FutsalCourt`。
- 玩家角色：`BP_FutsalPlayerBase`，父类为 C++ `AFutsalPlayerBase`。
- 规范动画蓝图：`ABP_FutsalPlayerBase`，native parent 为 `UFutsalPlayerAnimInstance`。
- 动画蓝图继续负责 AnimGraph、Locomotion/Main States 状态机、动画资源和 FootIK ControlRig；C++ AnimInstance 负责初始化及逐帧动画数据更新。
- 已完成人工 FootIK Alpha=0 对照验收，确认 FootIK 地面追踪/PBIK 是 Sequencer 驱动位移下下肢异常的主要来源；当前结果作为本阶段验收状态保留。

## MPFB Player_N 生产流程

后续 MPFB Player_N 角色的 Blender、FBX、UE Skeleton、材质、纹理和 Runtime Smoke Test 应遵循 [MPFB Player Production SOP](Docs/MPFB_PLAYER_PRODUCTION_SOP.md)。该 SOP 以 Player_002 成功生产提交 `1ceadab` 为参考，固定共享 MPFB Core v1 Skeleton/Retarget/AnimBP，允许每个角色独立选择身高、体型、皮肤、发型、衣服和鞋子。

关键约束：源人物使用 `METRIC / METERS / 1.0`，仅临时 Export Copy 做 meter-to-centimeter 数据转换；UE 角色共享 `/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base` 和 `/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget`，不为单个 Player 创建独立 Skeleton、IK Rig、Retargeter 或 Runtime AnimBP。

动画相关资产路径：

```text
/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase
/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase
/Game/FutsalMOT/Maps/L_FutsalCourt
```

## 仓库边界

| 仓库 | 负责内容 | Git 边界 |
| --- | --- | --- |
| 外层 UE 仓库 | `.uproject`、`Config/`、`Plugins/`、`Source/`、UE 内容资产和内层 gitlink | 只记录 `Content/FutsalMOT/code/` 的 submodule commit，不逐文件跟踪内层内容 |
| 内层 Python 仓库 | GRF 导出、task 配置、UE Python、标注后处理和测试 | 位于 `Content/FutsalMOT/code/`，拥有独立历史和远端 |

修改 Python 代码、配置或文档时，先在内层仓库单独提交并推送，再由外层仓库更新 gitlink。首次克隆后运行 `git submodule update --init --recursive`。

## 数据管线

内层仓库的入口为 [Python 数据集 README](Content/FutsalMOT/code/README.md)。P1 使用 Python 3.9 与 `uv` 导出轨迹及执行后处理；P2 在 Unreal Editor 的 Python 环境导入轨迹、创建 Level Sequence 并提交渲染。完整数据格式见 `Content/FutsalMOT/code/docs/DATA_CONTRACT.md`，测试、验收和已知限制见 `Content/FutsalMOT/code/docs/VALIDATION_AND_LIMITATIONS.md`。

常用命令：

```powershell
cd Content/FutsalMOT/code
uv run grf-ue task validate configs/pose_smoke_3frames_1cam.json
uv run grf-ue task export configs/pose_smoke_3frames_1cam.json
uv run pytest
```

UE 阶段的完整入口和参数由 `uv run grf-ue task ue-command <config.json>` 生成；`ue/run_task.py` 必须在真实 Unreal Editor Python 环境运行，不能在项目 `.venv` 中运行。

## Unreal Editor 自动化

插件 `Plugins/FutsalMOTMCP` 注册了 `FutsalMOTTools.run_python_file` 和 `run_python_code`，分别用于在真实 UE Python 环境执行项目脚本和短诊断。Editor 状态、资产和运行日志优先通过项目配置的 Unreal MCP 查询。

`.uasset` 与 `.umap` 是二进制文件。文件级检查不能替代 Editor 中对 Blueprint 编译、关卡 Actor、Sequence 绑定、MRQ 输出及 RGB/Mask/Pose 对齐的验证。

## 工程配置

项目使用 Unreal Engine 5.8，启用 ModelingToolsEditorMode、GameplayStateTree、MovieRenderPipeline、MoviePipelineMaskRenderPass、ModelContextProtocol、AllToolsets 和 FutsalMOTMCP 插件。当前正式地图为 `L_FutsalCourt`；`Config/DefaultEngine.ini` 中默认地图仍指向不存在的 `L_Futsal_Demo`，启动或运行流程前应在 Editor 中确认当前地图。

`Saved/`、`Intermediate/`、`DerivedDataCache/` 和 `Content/Fab/` 属于本地生成或 Fab 资产目录，不作为常规提交内容。若要纳入 Fab 资产，应在 UE 内容浏览器中移至 `Content/Fab/` 之外以保留引用。
