# 训练资格与弱标签有界诊断：完整结果a01

2026-10-29。全量只读诊断、独立分类/权重/区间终验和实际进程退出均已闭合。新增优化更新、模型前向、图像推理、追踪推进、solver、GT坐标读取、TrackEval及渲染均为0；测试116/187/test继续封存。原未校准strongmotion_RS仍为研究主参照。本轮没有新的AssA/HOTA/IDF1成绩。

## 结论与通俗解释

新R池保留了整个高分stage，训练对其中所有known pair求BCE；原推理只有通过候选资格的格才进入MLP。3000窗全部含评分资格外的known监督：总35240个known中29087个在资格外，其中29064个是负例、23个是正例。按原每窗known-BCE的1/K权重计算，资格外质量2505.847563/3000=83.528252%。

通俗说，训练花了大部分逐窗监督权重去区分推理根本不会交给学习分支比较的对象，真正会遇到的困难候选只占剩余部分。这是精确可定位的训练/推理覆盖差异，支持单独验证候选资格mask；它仍不能证明这是此前退化的主要原因，更不能保证mask后就能胜过原strongmotion_RS。

同时1547窗没有known正例且含unknown，不能把它们理解为目标真的不匹配。未知不是错负例证明；256个历史anchor偏离代理也不自动等于错标签。本轮没有删窗、改标签、引入算法伪标签或新Pose监督。

## 绝对分母与分类

原3000唯一R窗/42465候选：known35240=正1115+负34125，unknown7225。每fold1000、两允许train来源各500；原九张R曝光表27000条只做权重映射，不冒称18臂实际54000R或27000独立窗。既有12账本9000逻辑帧/2250唯一源帧/27000stage/180118行，与既有公开后验的同180118行逐条join；不是360236个独立状态。

| 互斥主类 | 窗口数 |
|---|---:|
| 1_query_history_or_fields_unknown | 0 |
| 2_unique_known_positive | 1115 |
| 3_no_known_positive_with_unknown | 1547 |
| 4_GT_absent_no_known_positive | 191 |
| 5_GT_present_no_trusted_raw | 69 |
| 6_trusted_raw_outside_stage_or_scoring | 78 |
| 7_unresolved | 0 |

主类1、7均0只说明本次来源字段能对上，不能说明标签是真实人工GT。主类6的78窗在相同标签严格join下对应可信raw不在原候选stage；不声称网络把本来在评分资格内的正例漏标。

| 候选标签 | 全部 | 评分资格内 | 资格外 | 资格未知 |
|---|---:|---:|---:|---:|
| known正例 | 1115 | 1092 | 23 | 0 |
| known负例 | 34125 | 5061 | 29064 | 0 |
| unknown | 7225 | 2081 | 5144 | 0 |

| fold | 窗口 | mask后有known窗 | 无known窗 | 剩余known pair | 剩余正例 | 剩余负例 |
|---|---:|---:|---:|---:|---:|---:|
| game4 | 1000 | 709 | 291 | 2618 | 433 | 2185 |
| game6 | 1000 | 557 | 443 | 1277 | 304 | 973 |
| game9 | 1000 | 741 | 259 | 2258 | 355 | 1903 |

合计2007窗仍有known监督、993窗没有known监督，其中846窗没有任何可评分候选；三fold均保留非空known监督及正例。不能复制/重采样空窗凑预算；这些是待验证mask的预期有效监督数，不是实际新增训练。

## 四项事前描述区间

单位为窗口比例的百分点；每源先均两允许fold，再三源等权。t95使用df2；bootstrap为Python MT19937、10000次、seed20261029、线性分位；不校正多比较，LOO全保留。t区间不事后截断0至100。它们是三个已观察train比赛的描述，绝非追踪提升区间。

| 主量 | 绝对窗数/3000 | 三源等权比例 | t95 | bootstrap95 |
|---|---:|---:|---|---|
| contains_scoring_ineligible_known | 3000 | 100.000000 | [100.000000, 100.000000] | [100.000000, 100.000000] |
| contains_scoring_ineligible_positive | 23 | 0.766667 | [-1.130625, 2.663958] | [0.100000, 1.600000] |
| eligible_trusted_correct_without_known_positive | 0 | 0.000000 | [0.000000, 0.000000] | [0.000000, 0.000000] |
| no_known_positive_with_unknown | 1547 | 51.566667 | [17.669032, 85.464301] | [40.200000, 66.700000] |

第四项是预期为0的恒等一致性检查，0区间不代表方法正确/性能相同/无弱标签问题。100%同样只限本次实际观察，不表达总体确定性。

| 主量 | SNMOT060 | SNMOT097 | SNMOT151 | 留一060 | 留一097 | 留一151 |
|---|---:|---:|---:|---:|---:|---:|
| contains_scoring_ineligible_known | 100.000000 | 100.000000 | 100.000000 | 100.000000 | 100.000000 | 100.000000 |
| contains_scoring_ineligible_positive | 0.100000 | 0.600000 | 1.600000 | 1.100000 | 0.850000 | 0.350000 |
| eligible_trusted_correct_without_known_positive | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| no_known_positive_with_unknown | 66.700000 | 47.800000 | 40.200000 | 44.000000 | 53.450000 | 57.250000 |

完整六fold-source单元、每seed表权重、所有正/负/unknown/边界、history/gap/candidate固定分箱与逐行证据均在report和unit输出；R/RS全自由账本仅独立敏感性表，未混入主3000窗口分母。

## 原模型概率层：仅对active且enabled解释

| 标签组 | 严格cost可行 | 概率拒绝 | 等门槛未知 | 不适用 | 资格/成本缺失或未解冲突 |
|---|---:|---:|---:|---:|---:|
| positive | 1044 | 48 | 0 | 23 | 0 |
| known_negative | 77 | 4984 | 0 | 29064 | 0 |
| unknown | 680 | 1401 | 0 | 5144 | 0 |

未启用学习分支及低分stage的bbox成本不当作概率；inactive行丢失的独立motion gate仍记null，不从enabled=false反推。成本等于门槛不调用solver猜匹配。当前CE模型完整内部状态缺失仍缺失，本轮没有新rollout。

## 唯一下一因素及边界

按事前工程顺序，只登记R候选评分资格mask为下一验证因素。动机为全部3000窗中可定位且原权重占比高的覆盖差异；不是根据12场成绩挑规则，也不把描述区间显著性作为选型门槛。无known正例+unknown整窗过滤、anchor过滤、CE/null项、history/Kalman政策、Pose算法监督、合成数据扩充均不与此项合并。

待另签训练协议：每R窗只对原known且mask=true的候选求BCE均值；分母为剩余known数量K有效，空集返回带图零梯度，仍按原顺序消费窗口并执行1000次AdamW更新，不重采样/跳步。每步3R等权平均，RS再加原1S的known-BCE/3。仍对原known集合按原顺序做前向，不通过剪前向另引入批量数值变化。有效监督减少及重新归一后的权重变化必须逐步记录，不能称有效标签/梯度预算相同。

matched-control使用此前完整闭合的aligned-BCE十八臂，正式目标仍为原未校准strongmotion_RS。是否能只读复用控制须先完整静态/数值/记录准入确认；否则另立配对控制预算，不能暗增到36臂。本轮仅生成候选mask清单/决策，不代表训练准入或新SGD已经执行。

后续框架：194→64→32→1 ReLU/14593全部可训练参数，FP32、后170个normalizedPose列置0、无图像输入、无epoch扰动增广；原normalizer和每seed初始化；AdamW LR0.001/wd0.0001；R/RS×game4/game6/game9×seed20261024/25/26共18臂，1000更新、每步3R总3000R，RS每步1S总1000S，S系数1/3；prefetch2/256MiB；0/每50/1000完整模型/优化器/四RNG，last1000、非EMA、不挑best。推理high0.25/low0.10/new0.25/buffer30/match0.80/lowassign0.50/unconfirmed0.70/fuseTrue、dt≤1.2秒/面积比0.25至4/中心≤2/概率0.50保持。CPU/真实CUDA一步及首完整1000更新门禁在训练剩余臂之前。

原门控的代码边界也保留：拒绝`dt>1.2+1e-9`秒，面积比须在`0.25-1e-12`至`4+1e-12`内，拒绝归一化中心距离`>2+1e-12`；这是原数值边界，不另设性能δ。候选mask来自同一R teacher在概率前的资格，不能冒充当前CE模型的自由状态。

## 实际执行、失败保留与证据

最小producer两文件bundle `ed3a279291692550d3fa1541ac4ab2ae1bc4c656935796371bfe8fe69b4ee75d`；单文件独立verifier bundle `d31c90eb4437fccbc88878d0a9d33bc3ae8e55da9bbfe0c726955733bf40a4ef`。一unit准入15178行/500窗/7963候选完成并独立验证后继承，正式两个CPU worker补11项；所有worker join/exit0，真实CIM确认producer和终验均退出。正式控制器端到端16.672758秒（含准备/记录/汇总；另有准入和独立核查，不冒称整个研究或旧任务提速），worker峰RSS29495296字节。

纯fixture：core8项、controller11项、独立核查11项通过。独立核查夹具新增续行时曾在真实终验前发生SyntaxError；原候选与失败收据保存在Saved/ResearchBuild/state_label_fixture_failure_a01.py及.json，定位缺少续行后修正，11项重新通过。实际数据准入/全量/终验均未失败，无实验重放；没有改旧训练、权重、原日志或标签。

- [完成根](D:/projects/FutsalMOT_Research/pose/state_label_alignment_diagnosis_a01/complete_root_a01.json) SHA `c140edaf7004f139de55a0edf265069ef73f98c63c454b434405ece00dddf8f9`。
- [完整报告](D:/projects/FutsalMOT_Research/pose/state_label_alignment_diagnosis_a01/control_a01/report.json) SHA `dfd66bafc70daf8a1b3be9b336e97626004a795ac786b49a3efb9c16f7303aa1`。
- [独立终验](D:/projects/FutsalMOT_Research/pose/state_label_alignment_diagnosis_a01/final_verification_a01/receipt.json) SHA `fbd60aa04c6058dc3b95cc0f837a2be0e9fe6a38cf48b9a8593145dbec85b590`。
- [唯一因素决策](D:/projects/FutsalMOT_Research/pose/state_label_alignment_diagnosis_a01/one_factor_candidate_a01/decision.json)。
- [3000候选mask清单](D:/projects/FutsalMOT_Research/pose/state_label_alignment_diagnosis_a01/one_factor_candidate_a01/candidate_scoring_masks.jsonl)：尚待训练协议/数值/完整记录准入，不直接作为已训练成果。
- [静态字段审查](STATE_LABEL_ALIGNMENT_STATIC_A01.md)、[事前有界方案](STATE_LABEL_ALIGNMENT_DIAGNOSIS_A01.md)。
