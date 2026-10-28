# 有效决策机会核查：完整零更新结果

本轮支持保留原未校准strongmotion_RS，暂不直接启动Pose残差训练。可识别局部机会中确有预测Pose几何支持，但没有观察到“正负双方Pose支持充分、实际选择可信错误候选”的记录。大量历史身份不可识别或当前历史已偏离早期锚点，不能据此断言Pose全局无效或历史传播是主因。

12项既有训练域日志已完整核查并独立终验，所有生产/终验进程退出。新增SGD、模型前向、追踪、图像推理、solver、TrackEval均为0，没有新的AssA/HOTA/IDF1成绩。

## 绝对分母与主要发现

范围为原R/RS×三fold×seed20261024×每fold另两train来源，三源SNMOT060/097/151各750帧；9000既有逻辑帧、2250唯一源帧、27000三阶段、180118重复轨迹stage行。行、fold、R/RS重复不当独立比赛。

| 项目 | 绝对计数 | 含义 |
|---|---:|---|
| 全部stage行 | 180118 | 完整原日志分母 |
| 非可信3条历史 | 93560 | 包括短历史/unknown/混合，不能统一当学习模型错误 |
| 首停learned inactive | 73625 | 位于可信历史等前置条件之后，仍不由MLP作该次决策 |
| learned active联合计数 | 30918 | 与互斥首停不是相同口径 |
| 局部正负候选均enabled机会 | 3259 | 只对当前历史一致身份定义，不保证对应最初目标 |
| 双方Pose几何支持的机会 | 2835 | 末条历史共同身体点≥6且间隔1至30帧，不等准确率 |
| 上述机会中选择可信错误候选 | 0 | 固定训练域未观察到，不能称总体概率为0 |
| 上述机会中未匹配 | 21 | 全部仍为条件记录，不是21独立错误事件 |
| 上述机会中选择unknown | 4 | 不能算成功或失败 |
| 当前历史偏离首次stage可信3锚点 | 13319 | 重复状态行，不是13319独立ID切换 |
| anchor与当前query关系不可判定行 | 83985 | 缺早期anchor或当前query未知，不补造身份或使用未来锚点回填 |

局部机会的R/RS三源等权条件率分别为1.80959%与1.81368%；双方Pose结构支持机会为1.55427%与1.61091%。这些条件率以完整stage行为分母，不能解释为可提升AssA的百分比。21条未匹配机会在R/RS均只来自SNMOT097；没有跨三个来源的同类支持。

## 完整16类互斥首停

以下各类之和为180118；联合旗标不能与此表相加。原report的Counter省略了全0类别，独立终验只在全部unit和新账本逐行证实为0时补列，未改变原结果。

| 首停类别 | 行数 |
|---|---:|
| GT_presence_unknown | 0 |
| actual_correct | 3696 |
| actual_known_wrong_with_strict_correct | 2 |
| actual_unknown_with_strict_correct | 27 |
| actual_unmatched_with_strict_correct | 55 |
| correct_cost_above_threshold | 0 |
| correct_motion_gate_rejected | 43 |
| correct_not_enabled | 0 |
| correct_probability_rejected | 108 |
| correct_raw_not_in_stage | 1179 |
| cost_equality_unknown | 0 |
| current_GT_absent | 2310 |
| history_not_trusted_three | 93560 |
| learned_inactive | 73625 |
| low_score_bbox_only | 420 |
| trusted_correct_raw_absent | 5093 |

## 可以和不能得到的解释

正确候选可达且严格成本可行时，互斥首停中实际选择可信错误只有2行，unknown27行、未匹配55行；这些并不都满足Pose结构支持。正确候选概率门槛拒绝108行，motion gate拒绝43行，正确raw不在当前stage1179行。它们是带明确前置条件的描述，不是总体根因占比，更不能把局部成本更优当全局分配器错误。

这次发现更需要澄清的是监督目标：当前三条历史即使已经转而跟随另一人，也可能重新变得一致。用其当前身份定义“正候选”，会掩盖与最早可信目标的偏离。新R窗口曾按可靠当前历史选择，尚需逐窗核查这些实际被训练的窗口是否涉及该现象。现有13319漂移行不能直接推出选中3000窗含同样比例，更不能称已有错误标签。

因此下一项只做已选3000个R窗口与本轮账本的逐窗交叉核查：检查首次可信anchor、当前query、实际enabled/正候选及no-positive；不筛窗、不重建池、不改变训练，不直接加训Pose。这是对失败训练数据的可识别性检查，而非新的追踪成绩。若监督目标仍无法可靠识别，算法教师不能用自身一致性冒充真值；暂不进入大规模Pose训练。

Pose身体索引5–16共同有效点至少6，来自原geometry_valid与有限17点坐标，仅是预测几何支持。当前模型不使用Pose；这些支持计数不能衡量Pose的实际判别力，也不能证明所有其他Pose算法无效。旧Pose开关/打乱实验仍是当前“尚无稳定追踪增益”的直接证据。

## 完整84个条件率描述

R/RS分别每源先均两fold率，再三源等权；first_stop分母是全行，flags分母为该旗标非null行，null数量在原JSON完整保留。t95 df2/4.302652729749462；10000比赛bootstrap，Python MT19937 randrange，seed20261028，线性分位，逐源留一。缺任一源CI=null；未做多比较校正，无等效δ。

| 组 | 条件 | 三源均值% | 95%t | 95%bootstrap | 逐源留一范围 |
|---|---|---:|---|---|---|
| R | first_stop:GT_presence_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| R | first_stop:actual_correct | 2.01811 | [1.93731, 2.09891] | [1.99204, 2.05456] | [1.99988, 2.03115] |
| R | first_stop:actual_known_wrong_with_strict_correct | 0.00094 | [-0.00310, 0.00498] | [0.00000, 0.00281] | [0.00000, 0.00141] |
| R | first_stop:actual_unknown_with_strict_correct | 0.01396 | [0.00113, 0.02679] | [0.00992, 0.01978] | [0.01105, 0.01598] |
| R | first_stop:actual_unmatched_with_strict_correct | 0.02902 | [-0.02969, 0.08773] | [0.00565, 0.05292] | [0.01707, 0.04070] |
| R | first_stop:correct_cost_above_threshold | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| R | first_stop:correct_motion_gate_rejected | 0.03681 | [-0.04109, 0.11470] | [0.00284, 0.06465] | [0.02288, 0.05379] |
| R | first_stop:correct_not_enabled | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| R | first_stop:correct_probability_rejected | 0.07429 | [0.02533, 0.12325] | [0.05667, 0.09557] | [0.06365, 0.08310] |
| R | first_stop:correct_raw_not_in_stage | 0.67097 | [0.35287, 0.98907] | [0.55700, 0.80954] | [0.60168, 0.72795] |
| R | first_stop:cost_equality_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| R | first_stop:current_GT_absent | 1.37656 | [0.06941, 2.68371] | [0.79236, 1.81330] | [1.15819, 1.66866] |
| R | first_stop:history_not_trusted_three | 51.24050 | [39.06238, 63.41861] | [46.50041, 56.29042] | [48.71554, 53.61054] |
| R | first_stop:learned_inactive | 41.42498 | [29.32176, 53.52821] | [36.35250, 46.06855] | [39.10319, 43.96122] |
| R | first_stop:low_score_bbox_only | 0.23646 | [0.16795, 0.30496] | [0.20921, 0.26435] | [0.22251, 0.25008] |
| R | first_stop:trusted_correct_raw_absent | 2.87742 | [2.21888, 3.53595] | [2.58154, 3.09331] | [2.76947, 3.02536] |
| R | flags:actual_correct | 44.55571 | [32.36161, 56.74981] | [39.37242, 49.13388] | [42.26662, 47.14735] |
| R | flags:actual_known_wrong | 0.01874 | [-0.00639, 0.04386] | [0.00813, 0.02827] | [0.01397, 0.02404] |
| R | flags:actual_selection_unknown | 23.90832 | [15.41605, 32.40059] | [21.03022, 27.68708] | [22.01894, 25.34737] |
| R | flags:actual_unmatched | 31.51723 | [23.55367, 39.48079] | [27.85032, 33.78915] | [30.38127, 33.35069] |
| R | flags:cost_equality_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| R | flags:earliest_stage_trusted3_anchor_drift | 12.22553 | [-2.26848, 26.71954] | [5.52400, 16.17626] | [10.25017, 15.57630] |
| R | flags:known_wrong_cheaper_or_equal | 1.90699 | [0.29038, 3.52360] | [1.28665, 2.58443] | [1.56827, 2.21716] |
| R | flags:learned_active | 17.78178 | [16.96384, 18.59972] | [17.41775, 18.05880] | [17.64327, 17.96379] |
| R | flags:local_opportunity | 1.80959 | [1.54282, 2.07636] | [1.69374, 1.90582] | [1.76148, 1.86752] |
| R | flags:local_opportunity_pose_supported_actual_known_wrong | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| R | flags:local_opportunity_pose_supported_actual_noncorrect | 0.00989 | [-0.03266, 0.05244] | [0.00000, 0.02967] | [0.00000, 0.01483] |
| R | flags:local_opportunity_pose_supported_actual_unknown | 0.00271 | [-0.00895, 0.01437] | [0.00000, 0.00813] | [0.00000, 0.00407] |
| R | flags:local_opportunity_pose_supported_actual_unmatched | 0.00989 | [-0.03266, 0.05244] | [0.00000, 0.02967] | [0.00000, 0.01483] |
| R | flags:local_opportunity_pose_supported_both | 1.55427 | [1.13694, 1.97161] | [1.36299, 1.67789] | [1.49246, 1.64991] |
| R | flags:pose_gap_1_to30 | 98.77868 | [98.41544, 99.14193] | [98.64515, 98.93494] | [98.70056, 98.84545] |
| R | flags:pose_gap_outside_1_to30 | 1.22132 | [0.85807, 1.58456] | [1.06506, 1.35485] | [1.15455, 1.29944] |
| R | flags:pose_gap_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| R | flags:positive_enabled | 2.13631 | [1.97001, 2.30262] | [2.08937, 2.21297] | [2.09799, 2.15979] |
| R | flags:positive_motion_gate | 47.88113 | [36.47764, 59.28462] | [42.86441, 51.87181] | [45.88579, 50.38949] |
| R | flags:positive_owned_elsewhere | 2.33637 | [1.22840, 3.44434] | [1.82223, 2.61937] | [2.19487, 2.59344] |
| R | flags:raw_correct_in_other_stage | 3.51202 | [2.04539, 4.97865] | [2.99220, 4.15391] | [3.19107, 3.77193] |
| R | flags:raw_correct_owned_in_other_stage_other_track | 0.26307 | [0.02864, 0.49750] | [0.15435, 0.32379] | [0.23271, 0.31743] |
| R | flags:strict_cost_feasible | 44.85723 | [32.78514, 56.92932] | [39.71172, 49.36885] | [42.60142, 47.42998] |
| R | flags:trusted_three_history | 48.75950 | [36.58139, 60.93762] | [43.70958, 53.49959] | [46.38946, 51.28446] |
| R | flags:unknown_competition | 87.28724 | [64.84897, 109.72550] | [76.96854, 93.76247] | [84.04962, 92.44659] |
| R | flags:unknown_enabled_competition | 11.67629 | [8.12322, 15.22936] | [10.03288, 12.64002] | [11.19442, 12.49799] |
| RS | first_stop:GT_presence_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| RS | first_stop:actual_correct | 2.06971 | [1.26359, 2.87583] | [1.77840, 2.41947] | [1.89483, 2.21536] |
| RS | first_stop:actual_known_wrong_with_strict_correct | 0.00094 | [-0.00310, 0.00498] | [0.00000, 0.00282] | [0.00000, 0.00141] |
| RS | first_stop:actual_unknown_with_strict_correct | 0.01538 | [0.00296, 0.02779] | [0.00996, 0.01982] | [0.01316, 0.01808] |
| RS | first_stop:actual_unmatched_with_strict_correct | 0.03543 | [-0.03275, 0.10360] | [0.00567, 0.05973] | [0.02327, 0.05031] |
| RS | first_stop:correct_cost_above_threshold | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| RS | first_stop:correct_motion_gate_rejected | 0.01255 | [-0.02800, 0.05311] | [0.00000, 0.03101] | [0.00332, 0.01883] |
| RS | first_stop:correct_not_enabled | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| RS | first_stop:correct_probability_rejected | 0.04381 | [-0.05557, 0.14320] | [0.01635, 0.08972] | [0.02086, 0.05754] |
| RS | first_stop:correct_raw_not_in_stage | 0.64869 | [0.39184, 0.90555] | [0.54669, 0.75343] | [0.59632, 0.69969] |
| RS | first_stop:cost_equality_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| RS | first_stop:current_GT_absent | 1.22179 | [-0.55388, 2.99746] | [0.40508, 1.73347] | [0.96595, 1.63015] |
| RS | first_stop:history_not_trusted_three | 51.46696 | [39.19000, 63.74391] | [46.47994, 56.36297] | [49.01895, 53.96046] |
| RS | first_stop:learned_inactive | 41.51647 | [28.96028, 54.07266] | [36.40556, 46.51270] | [39.01836, 44.07193] |
| RS | first_stop:low_score_bbox_only | 0.23332 | [0.16460, 0.30204] | [0.20395, 0.25889] | [0.22054, 0.24800] |
| RS | first_stop:trusted_correct_raw_absent | 2.73494 | [2.30848, 3.16141] | [2.53883, 2.85806] | [2.67339, 2.83300] |
| RS | flags:actual_correct | 44.71298 | [32.28241, 57.14354] | [39.43106, 49.38267] | [42.37813, 47.35394] |
| RS | flags:actual_known_wrong | 0.02324 | [-0.00973, 0.05621] | [0.00818, 0.03321] | [0.01825, 0.03077] |
| RS | flags:actual_selection_unknown | 24.11973 | [15.75510, 32.48436] | [21.32170, 27.85678] | [22.25120, 25.51874] |
| RS | flags:actual_unmatched | 31.14406 | [23.11162, 39.17650] | [27.42845, 33.31989] | [30.05614, 33.00186] |
| RS | flags:cost_equality_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| RS | flags:earliest_stage_trusted3_anchor_drift | 14.67771 | [-0.82284, 30.17825] | [7.47306, 18.35067] | [12.84122, 18.28003] |
| RS | flags:known_wrong_cheaper_or_equal | 2.04914 | [0.17712, 3.92115] | [1.28785, 2.79478] | [1.67632, 2.42978] |
| RS | flags:learned_active | 16.49225 | [14.36768, 18.61683] | [15.61158, 17.31960] | [16.07858, 16.93259] |
| RS | flags:local_opportunity | 1.81368 | [0.95217, 2.67520] | [1.59851, 2.21376] | [1.61364, 1.92127] |
| RS | flags:local_opportunity_pose_supported_actual_known_wrong | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| RS | flags:local_opportunity_pose_supported_actual_noncorrect | 0.01328 | [-0.04387, 0.07044] | [0.00000, 0.03985] | [0.00000, 0.01993] |
| RS | flags:local_opportunity_pose_supported_actual_unknown | 0.00273 | [-0.00900, 0.01445] | [0.00000, 0.00818] | [0.00000, 0.00409] |
| RS | flags:local_opportunity_pose_supported_actual_unmatched | 0.01328 | [-0.04387, 0.07044] | [0.00000, 0.03985] | [0.00000, 0.01993] |
| RS | flags:local_opportunity_pose_supported_both | 1.61091 | [0.74675, 2.47508] | [1.38241, 2.01127] | [1.41074, 1.72517] |
| RS | flags:pose_gap_1_to30 | 98.78847 | [98.39883, 99.17811] | [98.65576, 98.96157] | [98.70192, 98.85483] |
| RS | flags:pose_gap_outside_1_to30 | 1.21153 | [0.82189, 1.60117] | [1.03843, 1.34424] | [1.14517, 1.29808] |
| RS | flags:pose_gap_unknown | 0.00000 | [0.00000, 0.00000] | [0.00000, 0.00000] | [0.00000, 0.00000] |
| RS | flags:positive_enabled | 2.16527 | [1.23697, 3.09356] | [1.85198, 2.57888] | [1.95846, 2.32191] |
| RS | flags:positive_motion_gate | 48.35424 | [36.67013, 60.03834] | [43.14330, 52.28536] | [46.38868, 50.95971] |
| RS | flags:positive_owned_elsewhere | 2.65455 | [1.09133, 4.21778] | [1.94193, 3.13386] | [2.41490, 3.01086] |
| RS | flags:raw_correct_in_other_stage | 3.53848 | [2.07441, 5.00256] | [3.02535, 4.18219] | [3.21663, 3.79505] |
| RS | flags:raw_correct_owned_in_other_stage_other_track | 0.29945 | [-0.00074, 0.59964] | [0.16762, 0.40497] | [0.24670, 0.36537] |
| RS | flags:strict_cost_feasible | 45.14468 | [32.82523, 57.46412] | [39.84997, 49.68111] | [42.87646, 47.79203] |
| RS | flags:trusted_three_history | 48.53304 | [36.25609, 60.81000] | [43.63703, 53.52006] | [46.03954, 50.98105] |
| RS | flags:unknown_competition | 87.12797 | [64.62029, 109.63564] | [76.78660, 93.67189] | [83.85600, 92.29865] |
| RS | flags:unknown_enabled_competition | 10.92878 | [7.69569, 14.16188] | [9.43179, 11.79200] | [10.49718, 11.67728] |

## 原参数、执行与证据

原模型194→64→32→1 ReLU/14593参数/FP32/后170Pose列置0；1000更新、每步3R累计3000R，RS另1S累计1000S，AdamW LR0.001 wd0.0001，mean(3R)+mean(S)/3，原初始化/normalizer、last1000非EMA无best、无epoch扰动。以上为来源条件，本核查不运行训练。

原追踪high0.25/low0.10/new0.25/buffer30/high0.80/low0.50/unconfirmed0.70/fuseTrue；dt≤1.2秒、面积0.25..4/中心≤2/概率0.50。enabled为已验旁观重算，reference_cost是真实最终solver输入；active行成本先置1，仅enabled写模型值，p<0.50也置1，inactive保留bbox，low纯bbox。cost严格小于门槛才标单边满足，等号保持未知；未调用solver或恢复缺失logit。

完整750准入39.7193秒、15178行成功产物直接继承；正式两worker只补11项并汇总，耗时260.482秒，不含准备、准入和终验。资源每在飞3GiB、RAM保留8GiB/commit6GiB，逐帧处理，不物化整750日志。没有新串行基准，不宣称加速倍数。

独立终验重计新账本/来源小引用/计数/全部区间及退出，未重新执行首停分类、原frames/posthoc join或任何模型。原始字节与既有失败均保留。样本只来自已见训练比赛首seed，不是独立泛化评价；SNMOT116/187及test包继续封存。

完成根：D:\projects\FutsalMOT_Research\pose\decision_opportunity_a01\complete_root_a01.json；独立终验：D:\projects\FutsalMOT_Research\pose\decision_opportunity_a01\final_verification_a01\receipt.json；全统计/全部12账本引用：D:\projects\FutsalMOT_Research\pose\decision_opportunity_a01\control_a01\report.json。
