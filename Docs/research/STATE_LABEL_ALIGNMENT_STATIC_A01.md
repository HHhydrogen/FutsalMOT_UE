# 训练资格与弱标签诊断：静态字段审查a01

2026-10-29。本文件仅记录对既有源码、字段契约和新方案的静态审查建议。没有执行诊断、训练、模型前向、追踪、solver、TrackEval或旧审计，没有读取GT坐标、模型、媒体或封存测试，也没有产生新的分类计数或置信区间。实施范围以[有界方案](STATE_LABEL_ALIGNMENT_DIAGNOSIS_A01.md)及之后另签的输入/源码协议为准。

## 必须先明确的边界

1. `enabled` 在概率计算之前，不能与最终可分配性合并。原stage的inactive行没有模型评分，其bbox代价不是概率。
2. 机会派生账本保存逐候选`enabled`及最终代价，但没有保存逐候选motion gate、`current_GT_present`或完整`raw_correct_UIDs`。不能从派生账本臆造这些字段。
3. 同一teacher记录的历史、query、候选UID及逐项label严格相等时，资格内可信正候选必然是训练集合正例。第四主量是预期为0的一致性检查，不是独立收益指标。
4. 本轮九张曝光表对应27000条R窗口曝光映射；R与RS共享同一张R表。它不是18臂实际累计54000R曝光，也不是27000个独立窗口或比赛。

## 原执行时点和资格语义

原追踪器在`learned_association_tracker_v8.py`的`get_dists`中，先取得原BYTE代价，再计算motion gates、`lost_gap`和`enough_history`，随后调用`intervention_mask`。只有这之后才构造特征、执行模型sigmoid及`probability_to_cost`。

`intervention_mask`的原定义为：

- high-score阶段使用原代价门槛0.80，unconfirmed阶段使用0.70。
- `enough_history`要求原实际历史长度恰为3。
- `easy`要求非lost/gap、原bbox可行列恰为1且该列也仅被这一行占有；这里依据原含可选score融合的代价，不能改称纯IoU。
- `competition`依据motion gate的同行/同列候选竞争；行启用要求历史足够、非easy，且lost/gap或存在competition。
- active行的`enabled[i]`等于该行motion gates；inactive行的`enabled[i]`全False。`enabled`不读取模型概率、label、GT或最终分配。

motion gate固定使用实际历史与当前预测框的时间、面积及运动外推：实际间隔大于0且不超过1.2秒、面积比0.25至4、归一化中心距离不超过2；速度上限为历史末框高度的10倍/秒。它不是Pose质量门槛。

因此诊断A第二层可直接使用原`active AND enabled[j]`。inactive行已可确定评分资格为False，即使单独motion gate未知也不妨碍统计“不参加评分的known监督”。不能把inactive行中`enabled=False`进一步解释为运动门控拒绝。

low-score阶段原分配门槛0.50，只使用上游bbox/IoU路径，没有learned前向，原日志`gates/enabled=None`。第二层评分资格为False，第三层模型概率为`not_applicable`，不能作为MLP拒绝或错误。三阶段的真实分配结果均保持原日志值，不根据成本另运行分配器。

## 最终代价与概率边界

active行在写入模型值前整行置1.0，只对enabled格调用原模型；gate外不借bbox回退。inactive行保留原bbox代价。对active且enabled格，原sigmoid概率为p，stage门槛为T（0.80或0.70）：

- p小于0.50时最终代价为1.0，表示原概率拒绝。
- p不小于0.50时最终代价为`max(0,min(1,T+0.50-p))`。
- 最终代价严格小于T，只称“该单边严格满足代价门槛”，不保证全局分配或可纠正错误。
- 最终代价等于T时保留原边界unknown；原p等于0.50虽通过概率门槛，也不能据此替原solver判断等号分配行为。

`state_gap_rollout.Observer`在原分配函数入口包装中记录的`reference_cost`，才是原最终solver输入；`bbox_base_cost`不是同一语义。其重新计算的gates/enabled明确标为`gate_recomputed_for_logging_only`，是旁观字段，不可称额外执行的一次模型判断。

`decision_opportunity_core`的通用`strict_cost_feasible`旗标并未逐格限定active/enabled，且可覆盖原bbox行。新诊断第三层必须重新结合已存的`learned_active`及该候选`enabled`限制解释，不能直接把这个通用旗标当作“模型概率通过率”。

## 可复用字段与缺失处理

| 资料 | 已保留字段 | 本轮正确用途与限制 |
|---|---|---|
| 原Observer stage | rows/history、candidate_UIDs、逐格gates/enabled、active、最终reference_cost、真实assignments及门槛 | 是原完整记录口径；本轮优先复用派生产物，不为补齐字段重跑tracker |
| 机会账本逐行 | job及frame/stage/row/track、history_UIDs、query_GT_id、anchor、flags、逐候选uid/label/enabled/reference_cost | 足以核同记录评分资格及局部成本；没有逐格gates、GTpresence或完整正确raw清单 |
| 原后验`all_rows.jsonl.gz` | 同记录坐标、history_UIDs/history_status、query_GT_id、candidate_UIDs/pair_labels、current_GT_present、raw_correct_UIDs、selected_UID/column、正例gate/enabled聚合 | 可以严格join补B的公开后验标志；这些不是GT坐标，不重新计算IoU或读GT文件 |
| 已选R池metadata及teacher-anchor输出 | window_uid、source_job_id、source_stage/row/track、teacher身份、历史/query/逐候选UID和label、anchor关系 | 已有审计负责等值来源证明；本轮消费其完成收据及结果，不重新执行旧审计 |

派生账本里逐候选motion gate缺失时，建议单独输出`motion_gate=null`和`motion_gate_source=not_retained_in_derived_ledger`。原源码在active行确有`enabled==gate`的恒等关系，但如实施者使用该关系恢复位值，必须另标`derived_from_frozen_active_enabled_identity`，不能伪称直接记录；本轮无需恢复该位值即可判断评分资格。inactive行不能采用这一恢复方式；low-score的gate为`not_applicable`。

后验all_rows中的`positive_motion_gate`和`positive_effectively_enabled`是同行正例集合的聚合，不是所有候选的gate向量。不能将它复制到负例/unknown列，也不能用于恢复不存在的逐候选概率。

严格join主键应含source_job_id、frame_number、stage、row_index和track_id，并校验teacher fold/sequence/model/seed/regime、完整history_UIDs、query_GT_id、candidate_UIDs的顺序及每个pair_label。禁止最近帧或容差框配对。GTpresent仍只表示原后验所使用的选定GT标注范围内该query是否在场，不是人物物理消失证明。

## 四主量与恒等一致性

前三量可以直接由原输入、评分资格及unknown标记计算，先给唯一窗口计数，再给原曝光映射和权重，不推断追踪提升：

1. 含至少一个第二层不可达known pair的窗口。
2. 含至少一个第二层不可达known正例的窗口。
3. 无known正例且含unknown的窗口。

第四量“资格内存在可信正候选，但训练集合没有known正例”在严格同记录join下应为0：已选R窗保留整个原high-score stage；enabled只在这个stage的候选列中取子集；原池、metadata、机会行的逐候选label又被要求逐值相等。故该子集里有label=1，原全集里就必有label=1。

第四量必须保留为一致性断言，0不是方案成功或模型收益；非0首先是来源、join、label或定义不一致的故障，应保留证据并中止“同记录冲突”的解释。若改用earliest anchor重新定义正例、改query、改teacher或跨不同历史状态配对，就已改变诊断问题，不能借此制造非0。

同理，在“训练无known正例”且逐label一致的条件下，B第6类可由正确raw位于stage外解释；若正确raw就在同一stage，资格外并不会把它从整stage训练标签集合移除。不能将“同stage正例仅未enabled”说成该窗没有known正例。上述不可能组合应进入矛盾/来源检查，不当作新监督冲突数量。

## B七类的优先级和字段充分性

现有池metadata、机会账本与原后验all_rows合起来足以支持方案的七类；仅用teacher-anchor摘要或机会账本则不足以区分GT不在场、正确raw缺失和stage外。

实施时应固定以下细节：

- 第一类的“历史资格未知”指无法确定可靠三历史query或必需后验字段缺失，不是`active=False`。easy bbox行的query可以完全已知，不能把它们都归为目标未知。
- 第二类唯一known正例即使有unknown竞争也优先归入第二类；unknown与anchor旗标照常保留。多known正例不任选一个，应按协议异常或第7类矛盾留证，不能改标签。
- 第三类优先于后面的GTpresence解释。unknown保留None，不能当已知负例，也不能将该类命名为真实/物理no-match。
- 第四类仅依原`current_GT_present=False`描述标注范围内的目标不在场，不声明人物离开画面或检测一定正确。
- 第五类使用原可信几何raw对应代理；不存在可信raw不能自动等同没有检测，更不等同网络排序失败。
- 第六类按严格UID证据分别保留stage外和可评分资格外；受上述全集/子集恒等关系约束，不制造逻辑上不可能的no-positive原因。
- 第七类保留矛盾、缺乏解释及所有原始原因旗标；不因想凑完整类别而修标签。必需字段缺失应统一按第一类处理，并另列具体缺失原因。

这些条件说明的是可观察性和数据资格，既不证明原标签错误，也不证明可训练的mask一定改善自由追踪。

## BCE监督权重与曝光分母

K是一个原训练窗中已知标签候选数，不是全候选数。每个known pair在原R域的系数为`1/(3*K)`，因为每步先对各窗known BCE求均值，再对3个R窗求均值；unknown系数为0。若报告窗内相对质量，系数是`1/K`，应与每步系数分列，不把两者分别当两次曝光。

九张表是三fold乘三seed的R曝光表，各3000条，合27000条；R/RS共用同一R顺序。本诊断只映射一次这些共享表，不能乘2声称新增54000条独立诊断曝光。若另报告既有18臂训练累计R使用次数，才是54000，且必须标明它是R/RS两套训练的重复使用。S不属于这次R资格诊断的干预内容，原RS的S窗BCE系数1/3保持。

CE集合损失不具有上述逐pair可加的固定BCE权重，不能把BCE排除质量解释成CE损失占比。建议把“监督权重质量”明确写成“监督权重总量（mass）”，避免被误读为人工准确率或标签质量评分。

四个主描述量只用3000个实际R-only teacher窗口。三来源先均允许fold的窗口率，再源等权；seed曝光、窗口、fold、R/RS敏感性行不成为独立比赛。九张表只决定曝光权重，不扩大统计独立单位或把四个描述区间扩成择优搜索。

## 实施前的最小检查建议

只用纯fixture覆盖：active/enabled在概率前；inactive gate缺失但评分资格False；low-score不适用；active-enabled成本1、严格小于T、等于T分开；正例/unknown优先级；同记录第4主量恒为0；跨query/历史/候选顺序错位拒绝；每步`1/(3*K)`与九表27000映射。独立终验用另一实现检查这些不变量，不仅重新调用同一分类函数。

之后的小读取准入与完整扫描仍需另签输入清单、最小源码SHA和预算；不得因为本静态审查而启动模型、补轨迹或重读GT坐标。若字段缺失足以阻止四主量解释，应报告缺失并停止相应推论，不放宽join或借算法预测补真值。

参考源码：[原追踪器](../../python/src/grf_ue_bridge/learned_association_tracker_v8.py)、[概率到成本](../../python/src/grf_ue_bridge/learned_association_model_v8.py)、[原旁观器](../../tools/research_ops/state_gap_rollout.py)、[原后验字段](../../tools/research_ops/state_gap_analysis.py)、[机会派生账本](../../tools/research_ops/decision_opportunity_core.py)、[teacher-anchor等值检查](../../tools/research_ops/teacher_anchor_bank_audit.py)。实际执行必须绑定已验冻结版本，仓库链接只作审查入口。
