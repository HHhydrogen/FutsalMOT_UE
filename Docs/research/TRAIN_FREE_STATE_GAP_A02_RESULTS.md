# 训练候选与自由状态诊断：完整结果a02

本轮12项观察/后验、独立终验和实际退出均已闭合。新增优化更新0，图像推理0。**没有合格四分支事件，不能估计历史修复或Kalman修复的效果；没有新AssA/HOTA/IDF1成绩。**

## 绝对条件与实际预算

原强motion R/RS，194→64→32→1 ReLU/FP32，后170个标准化Pose通道置0；原权重、初始化及normalizer保持。本轮6模型为三fold×R/RS、seed20261024；每fold只用另外两原train片段，各750帧。12任务9000逻辑帧，2250唯一源帧。原模型各1000更新、每步3R共3000R，RS另每步1S共1000S；AdamW学习率0.001、weight_decay0.0001、loss mean(3R)+mean(1S)/3、last1000非EMA无best。这些是历史训练条件，本诊断没有追加更新。

追踪阈值high0.25/low0.1/new0.25、buffer30，高/低/未确认分配阈值0.8/0.5/0.7，fuse_score=True；候选dt≤1.2秒、面积比0.25至4、中心归一距离≤2、模型概率门槛0.5。全部raw保留，GT只独立后验，不进正常追踪。

独立核验27000个stage（含空分配）、180118个track-stage行、原三fold各1000自然训练池窗口。stage行、候选pair和窗口均不是独立图像或比赛。

## 自由状态绝对计数

| fold | 组 | stage窗口 | 历史1/2/3条 | 候选中位数 | gap=1帧窗口 | learned active | 无正候选窗口 | 全unknown窗口 |
|---|---|---:|---|---:|---:|---:|---:|---:|
| game4 | R | 27401 | 4121/2076/21204 | 15 | 20804 | 4958 | 13437 | 10900 |
| game4 | RS | 27266 | 4590/2032/20644 | 15 | 20814 | 4330 | 13150 | 10566 |
| game6 | R | 29979 | 4706/2475/22798 | 16 | 23003 | 5186 | 15694 | 13209 |
| game6 | RS | 29800 | 4620/2523/22657 | 16 | 23007 | 5023 | 15563 | 13086 |
| game9 | R | 32846 | 5256/3217/24373 | 16 | 24353 | 5909 | 17632 | 14729 |
| game9 | RS | 32826 | 5654/3321/23851 | 16 | 24371 | 5512 | 17450 | 14521 |

原自然训练池每fold1000窗口、全部历史3条，query gap=1/5/10/20/30帧各200；三fold候选pair总量4072/3215/3973，无正候选窗口105/109/120，未知pair919/609/1038。这只是未增广自然池结构，不是所有实际SGD张量。自由状态表涵盖所有三stage，不能把这些总体计数直接当实际learned前向曝光；全unknown也不能直接当混合身份历史。

## 首错与四分支负结果

登记235个首次可观察切换记录，231个此前已有unknown观测、4个标为trusted switch；最终eligible=0/selected=0。原先计划original/history_only/motion_only/both各错误帧+后30帧，实际prefix=0、四支推进=0，45个配对描述及CI均无可估计值（null），不能写差值0或“无影响”。排除原因重叠：
- first_error_status_unknown_prior_observation：231
- pre_error_history_not_trusted_anchor_consistent：202
- correct_current_raw_not_mutual_unique：143
- pre_error_history_fewer_than3：34
- anchor_GT_absent：17
- fewer_than30_future_source_frames：10
- prior_trusted_identity_conflict：8

## 能支持什么、下一步只改什么

这些结果支持检验训练窗口来源与自由状态分布差异，不能认定它是总体错误主因，不能确定历史/Kalman哪一个更重要。下一项仅选择**R训练窗口来源对齐**作为待验证假设：固定R-only teacher，各fold允许两train来源各500个唯一可靠窗口为目标，共1000；R/RS共用R池，RS的原1000平衡S不改。候选、时间间隔及历史取自同一自由状态来源包，不能把结果解释成其中某个子成分的单独因果效果。unknown/混合历史不按末GT强标，池不足不复制填满。先审计资格及原schema，尚未生成正式池或启动训练。

未来18臂=R/RS×三fold×seed20261024/25/26，各1000更新、每步3R累计3000R，RS另1S累计1000S；模型、normalizer、初始化、AdamW0.001/weight_decay0.0001、FP32、loss及last1000保持上述绝对值。R UID内容变化，不能称与旧组完全同曝光；原S采样序不变。CPU/实际CUDA一步逐值、完整记录及首完整1000检查点门禁通过后才执行后续。

## 完整记录、失败与限制

a01异常前最后RAM139603968字节、commit282320896字节，终止原因未确证；旧5观察/2后验和3partial不覆盖。a04完整750流式后验准入峰RSS176013312字节、407.30906秒；a02明确继承3750帧，仅补5250成功帧，旧partial真实推进未知另列。不能宣称物理重试为0。a02三worker正常close/join/exit0，独立终验于2026-10-28 19:21通过，终验进程已退。

只涉及三个已见train比赛/首seed；几何双向唯一IoU≥0.5只是可信代理，不是完整身份真值。未评价新AssA/HOTA/IDF1，不能声称追踪提升/Pose增益/合成等效真实或五人制泛化。全部原始日志、排除/unknown/失败/负项与null保留；SNMOT116/187和test继续封存。

## 原始证据

- [完成根](D:/projects/FutsalMOT_Research/pose/state_gap_diagnosis_a01/complete_root_a02.json)
- [独立终验](D:/projects/FutsalMOT_Research/pose/state_gap_diagnosis_a01/final_verification_a02/receipt.json)
- [绝对计数及全部单位来源](D:/projects/FutsalMOT_Research/pose/state_gap_diagnosis_a01/closed_summary_a02.json)
- [唯一因素选择](D:/projects/FutsalMOT_Research/pose/state_gap_diagnosis_a01/one_factor_decision_a02.json)
- [事前协议](TRAIN_FREE_STATE_GAP_A01.md)

补充独立核查：4条非unknown trusted切换实际均为SNMOT097第245帧在game4/game9×R/RS的重复观测；均仅2条历史、正确raw非唯一、learned_active=false。不能视为4个独立物理错误或学习分支失败。原自然池候选中位数各fold均3、query gap中位10帧；自由R/RS全stage候选中位均15、gap中位1帧，不能据此把全stage统计当实际模型评分分布。
