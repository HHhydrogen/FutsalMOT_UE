# FutsalMOT / FutsalPoseTrack

使用Unreal Engine 5.8和Google Research Football生成五人制足球时序数据，并研究合成姿态监督对真实身份关联的作用。UE资产、C++、Python和实验代码统一由本仓库管理。

## 从这里开始

- [文档索引](Docs/README.md)：工程契约、生产、研究与运维说明。
- [当前任务](TASK_STATUS_AND_NEXT_STEPS.md)：实际阶段与下一步，不以历史命令代替当前状态。
- [Agent规则](AGENTS.md)：Git、存储、UE生命周期及研究边界。
- [Python入口](Content/FutsalMOT/code/README.md)：阶段2迁移完成前仍使用当前目录；不预先声称已在python/。

## 代码和环境

| 内容 | 当前入口 | 执行环境 |
| --- | --- | --- |
| UE运行时 | Source/FutsalMOT | C++ / UE5.8 |
| UE插件与MCP | Plugins/FutsalMOTMCP | 真实Editor Python |
| 轨迹与后处理 | Content/FutsalMOT/code/src | 固定Python3.9的P1环境 |
| 渲染脚本 | Content/FutsalMOT/code/ue | UE Python，不能在P1执行 |
| 训练与评价 | Content/FutsalMOT/code/experiments | 独立研究Python3.10 |

P1与UE之间通过JSON/JSONL交换数据；UE不导入NumPy/OpenEXR依赖的P1模块。GPU训练与UE渲染串行。默认地图保持`/Game/FutsalMOT/Maps/L_FutsalCourt`，资产移动通过UE API修引用。

用户已授权四阶段整理：文档/产物→Python与实验代码→UE资产→入口与规范固化。阶段完成情况以任务状态为准，号码WIP保留且不纳入成果提交。

## 数据集

正式数据集根为`G:/FutsalMOT_Dataset`：

| 版本 | 数量 | 限制 |
| --- | --- | --- |
| v1_no_numbers_4k | 8seed、32相机序列、20116对4K RGB/mask | 有bbox，无Pose，保留原train归属 |
| v2_pose17_location_pilot_a01 | 1920对4K、19200逐视角人物Pose | 480源时间样本，限定位置研究候选 |
| v2_pose17_longpair_pilot_a01 | 4800对4K、48000逐视角人物Pose | 600源时间样本，16条30秒相机序列 |

均为原生3840×2160、10FPS。按seed/manifest解析，不硬编码旧clips/clip_000层级。v2保留逐机位world、unknown及原诊断标记，不冒充正式可见性或遮挡标签；地板配对world约0.068mm差异保留原值，不称exact。

工作文件最终恢复到本项目原Saved物理目录；研究输入/权重/结果恢复到实际`D:/projects/FutsalMOT_Research`。数据迁移是否完整结束看当前收据。Saved、缓存、虚拟环境、媒体、模型权重不入Git；AutoSave关闭。

## 研究

主问题是固定真实检测输入时，合成Pose监督能否改善身份连续性。[本轮v4](Docs/research/POSE_V4_RESULTS.md)在相同真实曝光下AssA均差+0.2644个百分点、仅1/3训练seed提高，未达到登记门槛；混合臂未超过预训练关联结果。全部负结果保留，不以格式、4K、四机位或地板变化单独宣称创新。最终SNMOT116/187保持封存。

## Git

```powershell
git clone https://github.com/HHhydrogen/FutsalMOT_UE.git
```

唯一master保留原UE和Python提交历史；新clone无需submodule初始化。在Python目录运行Git也定位本项目根。精确选择已验文件，一次commit/push，不add-A或force；迁移经过见[单仓库记录](Docs/operations/SINGLE_REPOSITORY_MIGRATION_20261025.md)。用户已主动删除备份，不自动重建。
