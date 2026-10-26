# 训练全过程与论文证据

更新：2026-10-26。用户要求所有后续训练保留全过程，便于论文复核、曲线和表格。记录只是证据，不是新的数据/训练准入。

## 新实验的强制记录

研究根为实际`D:/projects/FutsalMOT_Research`；代码在不可变`code/<SHA>`，每次run独立目录。生成媒体只引用G成品，不复制训练图或EXR。

| 文件 | 内容 |
| --- | --- |
| `run_manifest.json` | 事前协议/数据/划分/执行代码/初始化/曝光表SHA、方法/fold/seed、环境与设备、固定预算、测试封存声明 |
| `steps.jsonl` | 每次已提交更新的R/S窗口UID和epoch、窗口/全部pair/已知pair曝光、总loss/分域loss、实际各参数组LR、梯度L2、步耗时和连续SHA链 |
| `update_transaction.json` | 更新前intent和提交状态；硬崩溃或日志超出检查点时保留原状，不猜步重放 |
| `events.jsonl` | 开始、检查点、总耗时、正常结束、人工中止或异常；原stdout/stderr另由控制器永久保存 |
| `checkpoints/step_NNNN.pt`及同名JSON | 第0/50/100…1000步均保留：实际模型、完整优化器、来源绑定、已提交步数、曝光链、Python/NumPy/Torch CPU/CUDA随机状态、标准化及方法状态 |
| `last_checkpoint.json` | 最新已保存检查点的路径/SHA指针；不覆盖历史检查点，不选best |
| `training_complete.json` | 仅实际1000更新、3000R及RS额外1000S、全部定期检查点齐全时生成 |
| 评价目录及独立预算核对 | 全部比赛/fold/seed/对照指标、轨迹、断档事件分母、失败和负结果；实际窗口/pair/初始化及模型身份复核 |

`tools/research_ops/training_journal.py`提供严格新目录记录和真实Torch检查点保存；`recorded_association_loop.py`在原3R/1S、独立分域loss、FP32更新中接入。既有预取2继续使用。所有新臂一致记录，不修改活动或历史冻结bundle。新一轮控制器必须绑定这两文件、显式提供实际来源和环境，验收后才能训练；单独运行日志夹具不算正式训练。

逐步耗时包括当前步计算和记录；总训练耗时还包括等数据与保存检查点，二者不混称。GPU事件、利用率和峰值等未测量项不推算为实测。梯度范数仅记录，不新增裁剪。先保留原始CSV/JSONL，再生成带明确平滑范围的展示曲线；不平滑评价结果或隐藏下降项。窗口曝光不是独立图像数，RS额外S不等FLOPs或有效pair预算。

## 历史实验

已结束的v8/v9/绿色A/B都有原始逐步损失、R/S UID与pair曝光、最终权重/优化器、评价和预算收据。历史日志没有逐步实测LR、梯度范数、逐步耗时、完整随机状态或全部中间检查点，不能事后补造。固定协议的LR只标为“协议设定”，不能冒充逐步读取。

`tools/research_ops/export_green_training_history.py`默认只读，显式`--execute --plots`后从全部18臂原记录导出`steps.csv`、`runs.csv`、`tracking_metrics.csv`、`comparisons.csv`及PNG/PDF曲线；每步链核验与来源SHA同时保存，原日志不改。曲线展示50步向后均值，包含全部seed，原始18000步保留。新目录拒绝partial覆盖；不读取最终测试或重新推理/训练。

论文统计使用已登记终点和全部训练seed；最终模型固定第1000步。检查点保留便于审计与复现，不用于事后挑best或重新调参。
