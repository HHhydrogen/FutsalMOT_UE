# 训练全过程与论文证据

更新：2026-10-27。用户要求所有后续训练保留全过程，便于论文复核、曲线和表格。记录只是证据，不是新的数据/训练准入。

[有界变化完整结果](../research/POSE_BOUNDED_VELOCITY_LEARNING_A01_RESULTS.md)现已闭合27臂27000步、567完整检查点、原始CSV及513项自由追踪/评价。独立终验a02实际核全513原来源、270参考、720指标/720断档配对、120指标区间/另24断档描述与真实退出，未重算训练预算、模型或TrackEval。根`pose/pose_velocity_learning_a01/complete_root_a01.json` SHA为`6b864d4a136e55744f2da8b3da73ae4dff8cbe6a1aa9c7acc1f6606d847001e6`；原审计缓存关闭假设和原终验旧五场字段假设的失败证据保留，修复仅在独立a02中解释原格式。完整记录合格不等于Pose效果合格，全部负结果与测试封存边界保留。

[有界变化编码学习验证](../research/POSE_BOUNDED_VELOCITY_LEARNING_A01.md)现已实际通过三组CUDA手写/完整记录循环的一步逐值门禁：模型、AdamW、分域loss、梯度/LR及全部RNG相同，0/1检查点实际读回，6诊断更新18R/4S另计。独立新方法身份保存在`bounded_velocity_association_method_state_v1`，原gated初始化/1000步/3000R及RS另1000S不变；不伪装v10或复用诊断权重。

14:05:30+08唯一启动的27臂已全部结束，首千步21检查点门禁后才执行其余26臂，最终独立a02实际读回567份模型/优化器/全部RNG并验证27000步/81000R/18000S、完整UID/epoch/pair/初始化和链。R all/known为304020/234738，S为92574/50382，重放0；来源复用模型新增更新0、历史缺失仍缺失。全部逐步日志/干预覆盖/原stdout-stderr保留，不将记录合格称效果通过。

独立审计a01曾把缓存自身closed字段误当原预取器自动关闭resource；冻结预取代码只join线程/释放lease，原收据closed=false准确保留。a02只在prefetch真实closed/worker退出/1000完整消费及run实际进程退出同时成立时确认资源退出，并如实登记cache_explicit_close_called=false。旧失败及根因JSON保留，未重训、修改原字段或hot改执行bundle。后续513项追踪已唯一启动，所有模型/原始记录继续保留。

新27臂论文原始归档`pose/pose_velocity_learning_a01/paper_training_archive_a01`已完成27000步`steps.csv`、27行`runs.csv`与来源`complete.json`。完整JSON列保留每步原记录、R/S UID/epoch、全部与已知pair、loss/LR/梯度/耗时及曝光链；纯R的synthetic_loss明确写null。独立逐行检查27000条与实际预算一致，原cache字段false及a01失败来源均如实保存，无平滑/补造、0新增更新，不读新追踪指标，567检查点保留原处。

七比赛资源对照现已完整闭合：C18000步/378完整检查点及原始CSV归档保留，A/B只读复用新增更新0；392项自由追踪/评价、1323配对单元和105个描述区间已独立核对，实际进程退出。结果见[完整报告](../research/REAL_SUPERVISION_SUBSTITUTION_A01_RESULTS.md)。历史A缺LR/梯度/RNG/中间权重仍如实缺失；原训练审计和归档不重复执行。

2026-10-27资源对照新增独立候选`full_training_record_spec_v2_real_groups`：C每步3基础R+1额外R，明确总4000R/0S，不借S列计账。逐步增加基础/额外R loss、窗口和all/known pair；权重固定`mean(base3R)+mean(extra1R)/3`。检查点/完成schema为`full_training_checkpoint_v2_real_groups`/`full_training_process_complete_v2_real_groups`，其余完整RNG、0/50/1000与last规则保持。原v1路径保留，旧冻结bundle不改。

2026-10-27独立C入口增加4项数据/曝光检查，加上5项记账契约均通过。两架构真正调用新记录循环，与手写`mean(base3R)+mean(extra1R)/3`的CUDA更新逐值对照loss、全部权重和优化器；v2检查点实际读回通过，4诊断更新/16R窗口另计，收据为`real_substitution_a01/C_numeric_validation_a01/receipt.json`。C十八臂现已全部完成，首千步21份门禁后串行执行，其后独立审计真实读回全部378份检查点/优化器/RNG及18000步记录，核对72000R（54000基础/18000额外）与全部pair/初始化/曝光链并确认进程退出；`C_postrun_audit_a01/actual_budget.json`保存证据。效果追踪也已完成，但训练记录完整本身不等于模型收益成立。

记录循环新增显式`diagnostic_updates=1`，仅当binding声明`diagnostic_only_one_update_not_formal_training=True`时允许，返回`diagnostic_only`，不生成正式千步完成收据。正式路径仍固定1000步；人工SIGINT和真实输入提前结束继续分别处理，不借诊断开关缩短正式预算。

C的论文原始归档现已实际完成：`real_substitution_a01/paper_training_archive_a01`含全部18000步`steps.csv`、18臂`runs.csv`和来源`complete.json`，逐步保留基础/额外真实loss、LR/梯度、两类R UID/epoch/all及known pair与曝光链，无平滑、筛seed或补造。独立`export_substitution_training_records.py`只读取已验收日志与收据，不改权重/原始记录；378检查点仍在原run目录，新增训练更新0、新验证指标读取0。该归档不等追踪结果或合成替代结论。

## 新实验的强制记录

每次独立阶段闭合后还须更新[面向用户的训练历史](../research/TRAINING_HISTORY.md)。参数逐项写绝对数值及单位，禁止只写“同前/翻倍/固定比例”；R/S逐步与累计曝光分别列出。结果先列各方法的绝对成绩和明确评价面板，再列配对差值与区间，不跨不同检测输入/片段/划分比较。暂时无完整成绩时标明进行中/失败/待核，不从差值或近似平均反推成精确成绩。大矩阵完整原值继续保留原CSV，历史文档只作明确口径的汇总和解释。

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

## v10实际接入证据

`v10_train.py`和`v10_training_control.py`已在独立冻结bundle中实际接入。三方法CUDA一步原循环/记录循环的loss及全部权重逐值一致，6次诊断更新单独记录；`recording_numeric_validation_a01/receipt.json`保存模型、优化器、完整RNG读回证据。17:03启动的54臂正式矩阵中，首个1000步已完成，控制器独立读回0至1000每50步共21份完整检查点，验证模型身份、优化器、RNG、曝光链及末次已提交事务；`control_a01/first_run_end_to_end_gate.json`已通过，重放0。

实际环境快照`pose/multiseed_v10_a01/training_frozen_a01/environment_a01.json`含Python/NumPy/Torch/CUDA/CUDNN、设备、软件包版本和运行环境，并由启动收据绑定。全部54臂现已完成，独立`postrun_audit_a01/actual_budget.json`核验54000实际更新、1134份完整检查点及全54臂逐步字段/曝光/pair/初始化，相关训练进程退出。此证据仍不替代全部追踪评价与效果结论。

`export_v10_training_history.py`已从独立预算核验后的原日志导出`D:/projects/FutsalMOT_Research/pose/multiseed_v10_a01/paper_training_archive_a01`：`steps.csv`含全部54000步，`runs.csv`含全部54臂预算，六张分池/比赛损失图各保留PNG/PDF。每张图含三方法与全部三seed，细线为原值、粗线为向后50步均值，原始CSV不平滑。归档`complete.json`绑定每run原日志/完整记录/检查点来源，模型与原记录不改，未读取新比赛追踪结果，也没有新增优化更新；曲线下降不等追踪增量。
