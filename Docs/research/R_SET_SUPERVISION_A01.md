# R候选集合监督a01（训练已闭合，180追踪执行中）

方案制定于2026-10-28，2026-10-29完成真实CPU/CUDA数值准入。依据完整决策机会与3000实际R窗口交叉证据，本轮仅验证R损失。原未校准strongmotion_RS保持主参照；目前尚无新追踪成绩。

## 可证伪假设

已选3000R窗中无known positive窗口1885，known pair35240中正例1115；原损失对每窗known pair分别BCE再平均。同样的窗口数包含不同的正负竞争任务。拟仅将R窗损失改为“候选集合选择，含显式无匹配目标”，检验它能否改善该新窗口来源的自由追踪。它不是调概率门槛、搜索截距或修复所有历史漂移；也不能预设一定上升。无known positive不证明物理场景中真实无人可匹配：unknown候选仍可能对应真实目标，因此该方案只在当前可信标签集合内选择“候选”或“无匹配”。

候选logit为原模型对known pair的z_j。unknown仍不参与标签或损失，不当负例。无匹配logit固定为绝对值0，不新增可训练参数。若有唯一known正例j，R窗损失为 logsumexp(0,z_1,...,z_K)-z_j；若无known正例，损失为logsumexp(0,z_1,...,z_K)。多个known正例拒绝为协议不符，不能随意选一个。若窗内known数0，沿原记录合同明确零贡献并记账，不补造标签；现冻结R池每窗known≥1。该改变让R监督直接表达“选这个候选”或“没有匹配”，不删掉1885个无正例窗口。

## 绝对条件与对照

唯一因素是R损失函数。R原三池、每fold1000唯一/两允许来源各500、九张R曝光表及UID/epoch顺序保持，不筛除256个anchor偏离代理窗口、不补样、不重拟合normalizer。正负标签维持当前历史身份定义，anchor偏离仍是未解决限制，不能同时改变其资格。RS的原v10balanced1000S及其逐窗known-BCE平均损失、系数1/3原样保持。

拟18臂=R/RS×fold game4/game6/game9×seed20261024/20261025/20261026；194→64→32→1 ReLU、14593可训练参数、FP32，后170个标准化Pose列置0，原每seed初始化及原baseR normalizer，无epoch扰动。AdamW学习率0.001、weight_decay0.0001，每臂1000实际更新；每步3R窗、累计3000R，RS另1S/步、累计1000S。R loss为三个集合损失均值，RS加原S窗BCE均值/3。Last1000、非EMA、无best，0/每50/1000完整模型+AdamW+Python/NumPy/TorchCPU/CUDA RNG及全部逐步loss/LR/grad/UIDepoch/all-knownpair链/stdout-stderr/失败记录。

正式推理继续原sigmoid概率及阈值0.50，不将softmax分数替入tracking；原high0.25/low0.10/new0.25/buffer30/match0.80/lowassign0.50/unconfirmed0.70/fuseTrue、dt≤1.2/面积0.25..4/中心≤2、历史/Kalman及候选规则保持。如此可把本次干预限定为训练R目标，而非同时换推理归一化。

主要对照须为同一新R池的上一轮完整18臂；原strongmotion_R/RS同时列为性能参照，不能只证明超过失败版本就称整体能力上升。正式180新追踪及对照矩阵、绝对成绩主表与全部配对t/bootstrap/LOO必须在结果前另签冻结计划，原3/旧2/七场分别汇总，不混seed/训练窗为独立比赛，不设等效δ。

## 执行门禁（2026-10-29真实数值准入闭合）

本轮代码实现的9项小张量合同及8文件AST检查已通过。静态独立复核发现并修复了收据入口缺失、诊断计划4/8记账、pair与AdamW审计、正式CPU路径及追踪互斥问题；上述修复后的真实数值准入也已完成。

冻结协议：DResearch/pose/r_set_supervision_a01/training_frozen_a01/protocol.json，SHA 301eb84a90c47e0fbf7d869600f134ef46ca3a5d481d9029ad6d8a8161e7f0f7；7文件代码包code/a536124fccc3d82e4eb11054c720650ce7303c35f122a1d514907bb7473f46a5。结果前五族/三面板/五指标75描述区间计划已绑定；绝对条件及统计规则见[R集合监督分析](R_SET_SUPERVISION_ANALYSIS_A01.md)。

真实CPU/CUDA×R/RS四组手写与记录路径逐值核loss、梯度、更新后模型、AdamW、Python/NumPy/TorchCPU/CUDA RNG以及0/1步完整检查点，全部通过。实际诊断优化更新8（手写4+记录4）、R窗口曝光24、S窗口曝光4，均另计；准入收据numeric_admission_a01/receipt.json SHA b0b4ec17dbb0a713c92ec5826ef7ad26d6c6b83ed80cdf9988f272c9a4bae0c3。进程已实际退出。CPU与CUDA各自手写/记录相同，不要求两设备间梯度逐值相同。

首次只读预飞误用工作树入口，按不可变bundle保护拒绝，实际优化更新0、未创建准入目录；改用既有冻结bundle后预飞与数值准入通过，没有修改冻结文件。准备文档更新时曾误删协议说明前半，现从原提交恢复可证伪假设及全部绝对条件，补入本段真实状态。

当前正式18臂优化更新0、新追踪/TrackEval0，没有新AssA/HOTA/IDF1。下一步唯一控制器先执行首臂1000更新和21完整检查点门禁，只有成功才继续其余17臂，随后独立实际预算与退出审计，再另做180追踪准入。原未校准strongmotion_RS保持主参照。失败原样保留，不重放成功任务。SNMOT116/187/test封存。


## 正式训练首千步门禁与唯一启动（2026-10-29）

真实CPU/CUDA数值准入已闭合并随d041fef推送，唯一正式控制器已启动。首game4/seed20261024/R完成1000实际更新、3000R/S0，21完整检查点含原初始化、AdamW实际步数、全部RNG、方法状态及UID/epoch/all-known-pair链核查通过，随后才继续其余17臂。正式预算为18臂×1000=18000更新、54000R/9000S；当前只是首臂准入闭合，不称全18训练完成或追踪提高。

权威状态为DResearch/pose/r_set_supervision_a01/training_control_a01/driver_state.json；日志在control的logs与_launch_training_a01。固定7文件bundle a536124f、协议SHA301eb84a保持不可变。GPU训练使用prefetch2、256MiB特征缓存，数值线程1，保留RAM8GiB/commit6GiB/VRAM2GiB。18臂和真实退出后才运行独立预算审计，不重放旧实验或准入成功步骤；SNMOT116/187/test封存。


## R集合监督十八臂训练与独立实际预算闭合（2026-10-29）

十八臂各1000正式更新，实际累计18000更新、54000R/9000S；R all/known pair764370/634320，S46287/25191。独立只读审计逐条核全部18000步loss/LR/梯度/UID/epoch/all-known-pair链、378份完整模型/AdamW/PythonNumPyTorchCPU-CUDA RNG检查点、原step0初始化及normalizer、九组R/RS共R顺序及原S顺序，全部通过。8诊断更新/24R/4S另计，优化重放0。训练/controller/launcher/auditor均实际退出，原stdout/stderr与所有记录保持。

完成根training_complete_root_a01.json SHA56983403f0871cdf0a4ef07c14bbaf1a7258f2de4fee632caef0b35561946e86；独立postrun_audit_a01/actual_budget.json SHAb3e64595f799efd71f0c99522a0bacfd22e5beca539cafc6fa0f238f799fc0a0，成功status complete18_R_set_supervision_actual_budget_full_records_and_exit_verified。独立审计单文件bundle78544d14已实际执行成功，未调用训练runtime的audit_run代替自身重计。资源记录保留启动余量/缓存峰值和每run耗时，未部署完整CPU/GPU进程峰值采样器，不宣称本轮端到端提速。

新追踪/TrackEval0，没有新AssA/HOTA/IDF1。下阶段4文件独立追踪适配与双参照分析已有候选，实现检查共47项（审计9、loader15、worker7、control8、analysis8）通过；尚未冻结或实际cold/ABA/双spawn准入，不能称180追踪已执行。分析结果前五族/三面板/五指标75描述区间及另15gap区间保持；先列六方法绝对成绩，全部负结果/null/seed/fold保留。原strongmotion_RS仍为主参照，116/187/test封存。


## R集合监督追踪准入、首评价门禁与唯一启动（2026-10-29）

十八臂训练与独立预算已闭合。新R集合模型的CPU冷启动/ABA/双spawn数值准入实际96唯一源帧、336诊断消费，五次完整MOT/原生输出/审计比较一致，五worker及parent真实退出；收据tracking_numeric_a02/receipt.json SHA447343ec29064325aef8d587fb20cbec73886cc858f558c172ea367a19bd0035。新增优化更新0、图像推理0。a01安装阶段曾把同文件同SHA旧协议的正反斜杠引用当不同而拒绝，实际模型/帧0；旧partial保留，独立a02只继承旧报告原引用并验物理文件SHA，不改冻结4文件。

正式tracking_frozen_a01/config.json SHA2b16f8c7d7ffe9ef974825122abaeec17291fe606b7539ded2bf2e400f99aa9a，4文件bundle598df7569b5e4fb5dcbff1c84a8bd875c78d05ce449507723ab1292ef33d9d35。唯一后台2track+1metric常驻CPU、数值线程1、输入128MiB/最多2源、模型256MiB/最多3模型；保留RAM8GiB/commit6GiB。首R/RS两源完整TrackEval/GT计数/合法ID0/全预测保留门禁已通过，正在继续其余178项及自动五族分析。权威state位于tracking_control_a01/driver_state.json，日志_launch_tracking_a01与control/logs。不热改/重复启动，不提前按局部成绩选模型或阈值。

全部180新追踪+aligned180+原strongmotion180的绝对成绩、450指标配对与450gap配对、75指标/15gap描述区间待完整闭合/真实退出/独立终验后报告。新AssA/HOTA/IDF1尚未闭合，不称已提高。原3/旧2/七场分面板、先绝对成绩再差值/CI，全负/零/null/fold/seed保留，测试116/187/test封存。

### 独立追踪终验器已安装待用（2026-10-29）

终验单文件bundle code/b8a9ebe1436f0f13b6578786c0fcc6d3c4f21076d02e1723a9ea0aab9c99e994/tools/research_ops/verify_r_set_tracking.py，SHA2a266df89873d7876092a2f0ae47bb32b417a889fe5985850861bf4bbf27dd72。10项定向CPU夹具通过，独立核540来源/双baseline/全部MOT与GT计数/ID0/450配对/六CSV/75指标15gap区间和真实退出，不导入producer分析或重算模型/GT/TrackEval。实际终验尚未执行，只有全180、自动分析与真实进程退出后才可运行，输出另用tracking_final_verification_a01/receipt.json；未知partial/失败保留。当前估时只用完成清单与源帧元数据，未提前看局部成绩。


## R集合监督完整验证闭合（2026-10-29）

180新追踪与全部540来源/450配对/75指标15gap区间及独立终验已通过，所有生产/终验进程退出。本轮RS绝对AssA原3/旧2/七场为28.2647/38.7600/28.0828；上一轮RS27.8857/37.1806/27.8556；原strongmotion_RS31.8642/40.1160/30.2129。相对上一轮平均+.3790/+1.5793/+.2271，三面板t95与bootstrap全跨0，未建立稳定提高；相对原strongmotion−3.5994/−1.3560/−2.1301，12场比赛均值全负，原3/七场t95全负。完整六方法五指标绝对值和全部区间、逐场/seed/fold/负项见[完整结果](R_SET_SUPERVISION_A01_RESULTS.md)。保持原strongmotion_RS主参照，本轮权重留存不采用；损失改变不足以恢复原水平，状态/弱标签机制仍待验证，不称Pose因果。测试116/187/test封存，本轮收尾后停止实验跟进、不自动开新因素。
