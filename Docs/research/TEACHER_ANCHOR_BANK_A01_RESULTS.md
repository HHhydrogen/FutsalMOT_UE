# 实际3000R窗口与目标身份锚定：完整交叉结果

本轮不重新训练。原未校准strongmotion_RS保持主参照，退化版本保留。已对3000个实际选中R窗口及六个R teacher新账本逐窗精确join，并由独立实现核三池前后SHA、UID/标签/历史/目标query/坐标、全部CSV和分组计数。

## 绝对结果

| fold | 唯一窗 | anchor偏离代理 | 未偏离 | 不可判定 | 无positive窗 | all pair | known pair | 正例pair |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| game4 | 1000 | 19 | 981 | 0 | 565 | 13558 | 11500 | 435 |
| game6 | 1000 | 125 | 875 | 0 | 679 | 13167 | 10975 | 321 |
| game9 | 1000 | 112 | 888 | 0 | 641 | 15740 | 12765 | 359 |
| 合计 | 3000 | 256 | 2744 | 0 | 1885 | 42465 | 35240 | 1115 |

256/3000=8.5333%的窗口当前历史身份与首次stage可信三历史anchor不同；1885/3000=62.8333%的窗口无正候选，known pair中正例1115、可信负例34125，另unknown7225。它们是实际已选窗口的绝对构成，不是独立比赛泛化率，也不是本轮新性能。

256个偏离只说明几何身份代理发生分离，早期anchor本身也不是完整人工身份真值，不能改写为“256个错标签”，更不能仅据此删掉它们。1885无正例也是合法的“无匹配”监督，不能直接当坏数据。

选中窗的既有首停：

| 首停 | 窗数 |
|---|---:|
| actual_correct | 1021 |
| actual_known_wrong_with_strict_correct | 1 |
| actual_unknown_with_strict_correct | 3 |
| actual_unmatched_with_strict_correct | 19 |
| correct_motion_gate_rejected | 23 |
| correct_probability_rejected | 48 |
| correct_raw_not_in_stage | 335 |
| current_GT_absent | 808 |
| trusted_correct_raw_absent | 742 |

3000窗中950个具备当前query正负候选均enabled的局部机会，811个同时满足双方预测Pose几何支持。后者可信错选0、未匹配8、unknown0，8条均在game4的SNMOT097；仍不能据此承诺Pose排序训练会提升。这与前轮完整日志2835条结构支持机会中的0可信错选/21未匹配/4unknown相符，但分母不同，不能跨表直接当性能比较。

## 据此只选择一个下一因素

优先检验R监督目标：从每窗known-pair独立BCE均值，改为含固定无匹配logit0的候选集合选择损失。保持3000窗和九R曝光表、所有标签、原S及其BCE/系数1/3、初始化/normalizer/14593参数/FP32/1000更新预算和追踪推理阈值0.50不变；不同时过滤256个窗口、重建池或接Pose/历史/Kalman新规则。

理由是监督任务的可检验差异，而不是已证明损失函数造成退化：候选较多且多数窗口无正例，集合监督明确区分“选哪个候选”和“当前无匹配”。它仍可能失败，必须同时比较同一新R池上一轮模型及原strongmotion参照，超过退化版本也不能自动称整体能力提高。

具体已选方案见[R候选集合监督计划](R_SET_SUPERVISION_A01.md)。已实现集合损失候选并通过6项真实CPU小张量手写loss/梯度与边界合同；新SGD/模型加载/训练0。完整记录schema、CPU/CUDA一步逐值与首1000步准入尚未通过，因此未启动新18臂或新追踪。

## 范围与证据

三fold各1000原唯一窗、两允许train来源各500；R-only teacher seed20261024、原high stage/可信3历史/known≥1/whole-high-stage，不冒充exact-enabled-subset。仅读三池metadata、六R新ledger及机会小元数据，RS ledger未打开，未读旧frames/GT/cache/权重/媒体。窗口顺序、原池/标签全部保持，新增SGD、模型前向、追踪、solver、TrackEval、图像推理均0。

这是固定已选总体的交叉核查，不估计新AssA或性能区间；前轮84条件区间完整保留。数据来自已观察训练比赛，不称独立泛化、Pose准确率或历史因果。最终116/187及test包封存。

完成根：D:\projects\FutsalMOT_Research\pose\teacher_anchor_bank_a01\complete_root_a01.json；独立核查：D:\projects\FutsalMOT_Research\pose\teacher_anchor_bank_a01\final_verification_a01\receipt.json；完整分fold/source计数：D:\projects\FutsalMOT_Research\pose\teacher_anchor_bank_a01\analysis_a01\report.json；3000行CSV：D:\projects\FutsalMOT_Research\pose\teacher_anchor_bank_a01\analysis_a01\windows.csv；逐窗JSONL：D:\projects\FutsalMOT_Research\pose\teacher_anchor_bank_a01\analysis_a01\windows.jsonl。
