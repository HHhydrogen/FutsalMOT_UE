# R候选集合监督a01（数值准入已过，正式训练待启动）

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
