# FutsalMOT / FutsalPoseTrack

使用Unreal Engine 5.8和Google Research Football生成五人制足球时序数据。UE资产、C++、Python与研究代码由本仓库统一管理。

## 当前数据集生成入口

新生成统一使用single_seed管线：**3840×2160、10 FPS、写出并发8/等待队列8、每机位独立UE进程并串行执行**。五个必选机位加随机1–2个局部机位，共6–7个；复用已确认的GreenV2草地、十五套球衣、号码v2和天气视觉v2。

| 工作 | 唯一入口 |
| --- | --- |
| 准备源轨迹、冻结协议、导出与验证 | `tools/dataset/single_seed_task.py` |
| 按机位采集、恢复与正常退出 | `tools/dataset/run_single_seed_partitions.py` |
| 生成参数 | `python/configs/single_seed_generation_v1.json` |
| 完整操作说明 | [单seed基线](Docs/production/SINGLE_SEED_BASELINE_V1.md) |

旧`grf-ue task/production`、旧批量脚本、旧smoke配置和直接调用`python/ue/run_task.py`不再作为生成入口。底层共享库仍服务当前管线，不能绕过冻结协议执行旧配置。

已验证六机位各30帧，共180帧RGB/人物mask/号码mask及同步标注；**完整3001帧单seed尚未执行**。当前只清理旧入口并补齐容量检查、完整导出生命周期，用户要求暂不启动完整单seed。具体进度见[任务状态](TASK_STATUS_AND_NEXT_STEPS.md)。

## 文档与规则

- [文档索引](Docs/README.md)：现行生成、工程、运维和研究资料。
- [AGENTS.md](AGENTS.md)与[Python说明](python/README.md)：执行入口和协作规则。
- [数据契约](Docs/engineering/DATA_CONTRACT.md)与[验证边界](Docs/engineering/VALIDATION_AND_LIMITATIONS.md)：body12、号码及精简seed目录。
- [4K渲染策略](Docs/operations/RENDER_POLICY_4K_32GB.md)：本机8/8与分机位实测。
- [后续工作](Docs/engineering/SINGLE_SEED_READINESS_AUDIT.md)：完整单seed验收和后置的总数据集发布。

## 代码与存储

| 内容 | 位置与环境 |
| --- | --- |
| UE运行时与插件 | `Source/FutsalMOT`、`Plugins/FutsalMOTMCP`，UE5.8 |
| 轨迹与后处理 | `python/src`，P1固定Python3.9、`python/.venv` |
| UE内部执行 | `python/ue`，真实Editor Python；由分机位控制器调用 |
| 独立研究 | `experiments/sim2real`，Python3.10环境 |

P1与UE通过JSON/JSONL交换数据，不共用环境。默认地图为`/Game/FutsalMOT/Maps/L_FutsalCourt`；UE渲染与GPU训练串行。

临时渲染媒体只写`G:/FutsalMOT_Dataset/test/<attempt>/`；Saved保留配置、日志、轨迹/native和小收据。正式多seed输出在单seed验收后再建设，使用G盘`_work/_staging`与同卷发布。EXR在所有消费者完成后按清单清理，成功媒体的24小时保留从全流程结束计时；活动任务不能自动清理。详见[存储规则](Docs/operations/STORAGE_POLICY.md)。

已有v1与Pose17研究数据保持原版本，不转换成新body12数据，也不依据历史文档重跑旧生成管线。研究输入、最小SHA代码、权重和结果位于`D:/projects/FutsalMOT_Research`；G盘图像只引用、不复制。

## 研究与版本管理

论文研究问题和完整历史分别见[论文计划](Docs/research/CVPR_2027_PAPER_PLAN.md)、[训练历史](Docs/research/TRAINING_HISTORY.md)。最终SNMOT116/187/test封存；本轮不自动开始训练或选择真实split。旧实验结果与负结果保留，但不作为今天的生成入口。

唯一Git根为本项目，分支`master`，远端`HHhydrogen/FutsalMOT_UE`；无需submodule。使用精确暂存，不`git add -A`、force-push或跳过hooks。Saved、媒体、缓存、环境和权重不入Git，无关WIP保留；删除的旧操作手册和入口通过Git历史追溯，不另建可运行备份。