# 当前运行入口与维护

所有新数据生成统一从项目根调用`tools/dataset/single_seed_task.py`和`tools/dataset/run_single_seed_partitions.py`；参数与完整顺序见[单seed固化说明](../production/SINGLE_SEED_BASELINE_V1.md)。旧grf-ue task、旧生产driver、活跃窗口与Pose17试产不是当前可用生成入口。

```powershell
python/.venv/Scripts/python.exe tools/dataset/single_seed_task.py --help
python/.venv/Scripts/python.exe tools/dataset/run_single_seed_partitions.py --help
./tools/run.ps1 paths
./tools/run.ps1 mcp --help
```

本轮已清理旧入口并接通容量与生命周期控制，用户要求完整单seed暂不运行。纯代码检查不替代真实长样；不得因为文档列出后续命令而自动开始采集、渲染或训练。

P1固定`python/.venv`的Python3.9；UE运行UE5.8 Editor Python，研究环境独立Python3.10。当前生成器自行准备冻结协议与resolved配置；`run_task.py`只作为内部UE适配层，不手工投递旧JSON绕过当前入口。

UE配置、轨迹/native和收据在`Saved/SingleSeed/<attempt>`；RGB/EXR/mask在`G:/FutsalMOT_Dataset/test/<attempt>`。Saved、环境、媒体和权重不入Git，不把数据复制回源码目录。更改代码或DLL后使用新attempt，不改旧冻结协议。

## MCP与退出

UE操作遵守[完整MCP工作流](UNREAL_MCP_WORKFLOW.md)：先describe真实toolset，短tool_name调用；先核对地图、PIE/MRQ和dirty。完整脚本在真实UE Python执行，不能在P1或sandbox冒充`import unreal`。

分机位控制器使用正式启动/退出脚本；未知未保存改动或活动MRQ不强杀。正常退出需新鲜日志闭环。MCP请求与小收据保留项目Saved，历史脚本和日志不作为自动重启授权。

## 清理与历史

临时媒体按[存储规范](STORAGE_POLICY.md)精确清理；活动任务、失败现场和关键源码/协议/轨迹收据不误删，不跟随junction。UE资产通过Editor API移动/删除，不能从文件系统删除uasset。AutoSave关闭，重要Editor修改先保存。

当前源码只有根Git、master；精确暂存相关已验改动，保留无关WIP。旧生成文档和入口由Git历史追溯，不再维护可误调用的本地旧管线副本。研究已发布数据与冻结实验仍使用其原版本和独立环境。
