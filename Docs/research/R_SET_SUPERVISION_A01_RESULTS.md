# R候选集合监督a01：完整结果与解释

2026-10-29。180新追踪/评价、360历史参照、540绝对来源、450指标及450gap配对、75指标/15gap区间、独立终验与所有实际进程退出均已闭合。测试SNMOT116/187/test未读取。

本轮相对上一轮有小幅平均回升，但主AssA的t95与bootstrap区间在三面板全部包含0，不能宣布稳定提高。相对原strongmotion RS，12场比赛均值全部下降；原3与七场的t95区间全部为负，旧2场t区间跨0、bootstrap为负，两者均保留。保持原未校准strongmotion_RS为主参照，本轮权重保留且不替换主模型。

## 全部绝对成绩

每场先均匹配fold/seed，再比赛等权；不同面板不横比。分数为百分点。

| 方法 | 面板 | AssA | HOTA | IDF1 | DetA | MOTA |
|---|---|---:|---:|---:|---:|---:|
| 本轮R | 原3场 | 27.9655 | 39.5985 | 42.8349 | 56.5824 | 68.2347 |
| 本轮R | 旧外部2场 | 37.9251 | 48.7341 | 54.7331 | 62.8849 | 74.4900 |
| 本轮R | 七场 | 27.6385 | 38.9409 | 42.5721 | 55.5696 | 64.5840 |
| 本轮RS | 原3场 | 28.2647 | 39.8352 | 43.3154 | 56.6070 | 68.2454 |
| 本轮RS | 旧外部2场 | 38.7600 | 49.2866 | 55.8114 | 62.9199 | 74.5312 |
| 本轮RS | 七场 | 28.0828 | 39.2480 | 43.0868 | 55.5951 | 64.6597 |
| 上一轮R | 原3场 | 27.7659 | 39.4872 | 42.6768 | 56.6221 | 68.3125 |
| 上一轮R | 旧外部2场 | 37.8590 | 48.6455 | 54.9230 | 62.7983 | 74.4945 |
| 上一轮R | 七场 | 27.2240 | 38.6301 | 41.9959 | 55.5240 | 64.4648 |
| 上一轮RS | 原3场 | 27.8857 | 39.6047 | 43.0436 | 56.7615 | 68.5537 |
| 上一轮RS | 旧外部2场 | 37.1806 | 48.2675 | 54.6381 | 62.9198 | 74.5903 |
| 上一轮RS | 七场 | 27.8556 | 39.0667 | 43.0567 | 55.5586 | 64.6888 |
| 原strongmotion R | 原3场 | 30.9138 | 41.6749 | 46.5148 | 56.7928 | 68.4851 |
| 原strongmotion R | 旧外部2场 | 39.7281 | 49.9242 | 57.2890 | 62.9364 | 74.6287 |
| 原strongmotion R | 七场 | 29.9348 | 40.6961 | 44.9560 | 55.9675 | 65.3715 |
| 原strongmotion RS | 原3场 | 31.8642 | 42.2960 | 47.4776 | 56.6640 | 68.3121 |
| 原strongmotion RS | 旧外部2场 | 40.1160 | 50.2047 | 57.6972 | 63.0205 | 74.6707 |
| 原strongmotion RS | 七场 | 30.2129 | 40.8916 | 45.3909 | 55.9441 | 65.3558 |

## 全部配对差值与区间

差值为前者减后者，单位pp。75个区间未经多比较校正，不设等效/非劣效δ；CI含0不表示相同。t95自由度为2/1/6，bootstrap以比赛为单位10000次、seed20261028，另列逐场留一均值范围；各场原值与每fold/seed在原CSV完整保留。

| 比较 | 面板 | 指标 | 差值 | t95 CI | bootstrap95 CI | 逐场留一均值范围 |
|---|---|---|---:|---|---|---|
| newCE_RS_minus_alignedBCE_RS | 原3场 | AssA | +0.3790 | [-3.3138, +4.0719] | [-0.6609, +2.0817] | [-0.4723, +0.8990] |
| newCE_RS_minus_alignedBCE_RS | 原3场 | HOTA | +0.2304 | [-2.3916, +2.8524] | [-0.5282, +1.4358] | [-0.3723, +0.6097] |
| newCE_RS_minus_alignedBCE_RS | 原3场 | IDF1 | +0.2718 | [-3.4611, +4.0047] | [-0.7606, +1.9958] | [-0.5902, +0.7880] |
| newCE_RS_minus_alignedBCE_RS | 原3场 | DetA | -0.1546 | [-0.5594, +0.2503] | [-0.3195, +0.0063] | [-0.2350, -0.0721] |
| newCE_RS_minus_alignedBCE_RS | 原3场 | MOTA | -0.3082 | [-0.3705, -0.2460] | [-0.3228, -0.2793] | [-0.3227, -0.3009] |
| newCE_RS_minus_alignedBCE_RS | 旧外部2场 | AssA | +1.5793 | [-32.2071, +35.3657] | [-1.0797, +4.2384] | [-1.0797, +4.2384] |
| newCE_RS_minus_alignedBCE_RS | 旧外部2场 | HOTA | +1.0191 | [-21.1567, +23.1950] | [-0.7262, +2.7644] | [-0.7262, +2.7644] |
| newCE_RS_minus_alignedBCE_RS | 旧外部2场 | IDF1 | +1.1733 | [-27.8417, +30.1882] | [-1.1102, +3.4568] | [-1.1102, +3.4568] |
| newCE_RS_minus_alignedBCE_RS | 旧外部2场 | DetA | +0.0001 | [-0.5315, +0.5317] | [-0.0418, +0.0419] | [-0.0418, +0.0419] |
| newCE_RS_minus_alignedBCE_RS | 旧外部2场 | MOTA | -0.0591 | [-1.0353, +0.9172] | [-0.1359, +0.0178] | [-0.1359, +0.0178] |
| newCE_RS_minus_alignedBCE_RS | 七场 | AssA | +0.2271 | [-0.3392, +0.7935] | [-0.2234, +0.5556] | [+0.1451, +0.4433] |
| newCE_RS_minus_alignedBCE_RS | 七场 | HOTA | +0.1813 | [-0.2260, +0.5885] | [-0.1408, +0.4418] | [+0.1134, +0.3271] |
| newCE_RS_minus_alignedBCE_RS | 七场 | IDF1 | +0.0300 | [-1.1741, +1.2342] | [-0.9547, +0.8275] | [-0.2400, +0.4609] |
| newCE_RS_minus_alignedBCE_RS | 七场 | DetA | +0.0366 | [-0.1153, +0.1884] | [-0.0628, +0.1604] | [-0.0182, +0.0689] |
| newCE_RS_minus_alignedBCE_RS | 七场 | MOTA | -0.0290 | [-0.3825, +0.3245] | [-0.2987, +0.2249] | [-0.1233, +0.0733] |
| newCE_RS_minus_originalstrongmotion_RS | 原3场 | AssA | -3.5994 | [-6.8686, -0.3302] | [-4.6596, -2.1265] | [-4.3359, -3.0693] |
| newCE_RS_minus_originalstrongmotion_RS | 原3场 | HOTA | -2.4608 | [-4.6344, -0.2872] | [-3.1312, -1.4710] | [-2.9557, -2.1256] |
| newCE_RS_minus_originalstrongmotion_RS | 原3场 | IDF1 | -4.1623 | [-7.8436, -0.4809] | [-5.1595, -2.4594] | [-5.0137, -3.6636] |
| newCE_RS_minus_originalstrongmotion_RS | 原3场 | DetA | -0.0570 | [-0.4992, +0.3853] | [-0.1836, +0.1466] | [-0.1588, +0.0063] |
| newCE_RS_minus_originalstrongmotion_RS | 原3场 | MOTA | -0.0666 | [-0.9648, +0.8315] | [-0.4379, +0.2844] | [-0.2422, +0.1190] |
| newCE_RS_minus_originalstrongmotion_RS | 旧外部2场 | AssA | -1.3560 | [-17.9637, +15.2517] | [-2.6630, -0.0489] | [-2.6630, -0.0489] |
| newCE_RS_minus_originalstrongmotion_RS | 旧外部2场 | HOTA | -0.9181 | [-12.0777, +10.2415] | [-1.7964, -0.0398] | [-1.7964, -0.0398] |
| newCE_RS_minus_originalstrongmotion_RS | 旧外部2场 | IDF1 | -1.8858 | [-18.9478, +15.1763] | [-3.2286, -0.5430] | [-3.2286, -0.5430] |
| newCE_RS_minus_originalstrongmotion_RS | 旧外部2场 | DetA | -0.1006 | [-1.2570, +1.0559] | [-0.1916, -0.0096] | [-0.1916, -0.0096] |
| newCE_RS_minus_originalstrongmotion_RS | 旧外部2场 | MOTA | -0.1395 | [-0.8188, +0.5399] | [-0.1930, -0.0860] | [-0.1930, -0.0860] |
| newCE_RS_minus_originalstrongmotion_RS | 七场 | AssA | -2.1301 | [-4.0068, -0.2535] | [-3.5811, -0.8111] | [-2.4843, -1.5980] |
| newCE_RS_minus_originalstrongmotion_RS | 七场 | HOTA | -1.6436 | [-3.0123, -0.2750] | [-2.6894, -0.6835] | [-1.9024, -1.2755] |
| newCE_RS_minus_originalstrongmotion_RS | 七场 | IDF1 | -2.3041 | [-4.7727, +0.1644] | [-4.1671, -0.5676] | [-2.9310, -1.6327] |
| newCE_RS_minus_originalstrongmotion_RS | 七场 | DetA | -0.3490 | [-0.6562, -0.0418] | [-0.5764, -0.1293] | [-0.4269, -0.2586] |
| newCE_RS_minus_originalstrongmotion_RS | 七场 | MOTA | -0.6961 | [-1.0529, -0.3393] | [-0.9547, -0.4365] | [-0.7976, -0.5962] |
| newCE_R_minus_alignedBCE_R | 原3场 | AssA | +0.1996 | [-1.2013, +1.6005] | [-0.1713, +0.8486] | [-0.1249, +0.3851] |
| newCE_R_minus_alignedBCE_R | 原3场 | HOTA | +0.1114 | [-0.8670, +1.0897] | [-0.1655, +0.5623] | [-0.1141, +0.2498] |
| newCE_R_minus_alignedBCE_R | 原3场 | IDF1 | +0.1581 | [-1.8910, +2.2072] | [-0.7545, +0.8506] | [-0.1881, +0.6144] |
| newCE_R_minus_alignedBCE_R | 原3场 | DetA | -0.0397 | [-0.1176, +0.0381] | [-0.0723, -0.0098] | [-0.0547, -0.0235] |
| newCE_R_minus_alignedBCE_R | 原3场 | MOTA | -0.0778 | [-0.3381, +0.1825] | [-0.1658, +0.0381] | [-0.1357, -0.0338] |
| newCE_R_minus_alignedBCE_R | 旧外部2场 | AssA | +0.0661 | [-2.0577, +2.1900] | [-0.1010, +0.2333] | [-0.1010, +0.2333] |
| newCE_R_minus_alignedBCE_R | 旧外部2场 | HOTA | +0.0886 | [-1.8685, +2.0456] | [-0.0654, +0.2426] | [-0.0654, +0.2426] |
| newCE_R_minus_alignedBCE_R | 旧外部2场 | IDF1 | -0.1899 | [-2.1502, +1.7703] | [-0.3442, -0.0357] | [-0.3442, -0.0357] |
| newCE_R_minus_alignedBCE_R | 旧外部2场 | DetA | +0.0866 | [-0.7991, +0.9722] | [+0.0169, +0.1563] | [+0.0169, +0.1563] |
| newCE_R_minus_alignedBCE_R | 旧外部2场 | MOTA | -0.0045 | [-0.3738, +0.3649] | [-0.0336, +0.0246] | [-0.0336, +0.0246] |
| newCE_R_minus_alignedBCE_R | 七场 | AssA | +0.4145 | [+0.0611, +0.7679] | [+0.1597, +0.6729] | [+0.3219, +0.4931] |
| newCE_R_minus_alignedBCE_R | 七场 | HOTA | +0.3108 | [+0.0470, +0.5745] | [+0.1215, +0.5050] | [+0.2411, +0.3687] |
| newCE_R_minus_alignedBCE_R | 七场 | IDF1 | +0.5762 | [+0.1393, +1.0130] | [+0.2712, +0.9199] | [+0.4266, +0.6874] |
| newCE_R_minus_alignedBCE_R | 七场 | DetA | +0.0456 | [-0.0226, +0.1138] | [-0.0018, +0.0985] | [+0.0244, +0.0598] |
| newCE_R_minus_alignedBCE_R | 七场 | MOTA | +0.1192 | [-0.0812, +0.3196] | [-0.0208, +0.2763] | [+0.0573, +0.1582] |
| newCE_R_minus_originalstrongmotion_R | 原3场 | AssA | -2.9483 | [-8.2712, +2.3745] | [-4.7096, -0.5628] | [-4.1411, -2.0677] |
| newCE_R_minus_originalstrongmotion_R | 原3场 | HOTA | -2.0763 | [-5.7775, +1.6248] | [-3.3538, -0.4396] | [-2.8947, -1.4376] |
| newCE_R_minus_originalstrongmotion_R | 原3场 | IDF1 | -3.6799 | [-10.7570, +3.3973] | [-5.9725, -0.4904] | [-5.2746, -2.5336] |
| newCE_R_minus_originalstrongmotion_R | 原3场 | DetA | -0.2104 | [-0.5970, +0.1762] | [-0.3297, -0.0344] | [-0.2984, -0.1507] |
| newCE_R_minus_originalstrongmotion_R | 原3场 | MOTA | -0.2504 | [-1.0789, +0.5781] | [-0.5398, +0.1144] | [-0.4328, -0.1057] |
| newCE_R_minus_originalstrongmotion_R | 旧外部2场 | AssA | -1.8030 | [-8.6772, +5.0712] | [-2.3440, -1.2620] | [-2.3440, -1.2620] |
| newCE_R_minus_originalstrongmotion_R | 旧外部2场 | HOTA | -1.1901 | [-6.6540, +4.2738] | [-1.6202, -0.7601] | [-1.6202, -0.7601] |
| newCE_R_minus_originalstrongmotion_R | 旧外部2场 | IDF1 | -2.5560 | [-9.4056, +4.2936] | [-3.0950, -2.0169] | [-3.0950, -2.0169] |
| newCE_R_minus_originalstrongmotion_R | 旧外部2场 | DetA | -0.0515 | [-2.4162, +2.3132] | [-0.2376, +0.1346] | [-0.2376, +0.1346] |
| newCE_R_minus_originalstrongmotion_R | 旧外部2场 | MOTA | -0.1387 | [-0.5300, +0.2526] | [-0.1695, -0.1079] | [-0.1695, -0.1079] |
| newCE_R_minus_originalstrongmotion_R | 七场 | AssA | -2.2963 | [-4.5510, -0.0416] | [-4.1120, -0.8485] | [-2.7297, -1.4945] |
| newCE_R_minus_originalstrongmotion_R | 七场 | HOTA | -1.7552 | [-3.3527, -0.1577] | [-3.0390, -0.7174] | [-2.0552, -1.1984] |
| newCE_R_minus_originalstrongmotion_R | 七场 | IDF1 | -2.3839 | [-5.5759, +0.8081] | [-4.9371, -0.2807] | [-2.9828, -1.2782] |
| newCE_R_minus_originalstrongmotion_R | 七场 | DetA | -0.3979 | [-0.6705, -0.1253] | [-0.6109, -0.2117] | [-0.4522, -0.3096] |
| newCE_R_minus_originalstrongmotion_R | 七场 | MOTA | -0.7876 | [-1.2786, -0.2965] | [-1.1687, -0.4468] | [-0.9023, -0.6206] |
| synthetic_increment_loss_interaction | 原3场 | AssA | +0.1794 | [-4.3336, +4.6924] | [-1.1323, +2.2530] | [-0.8574, +0.8353] |
| synthetic_increment_loss_interaction | 原3场 | HOTA | +0.1191 | [-3.0934, +3.3315] | [-0.7786, +1.6013] | [-0.6221, +0.5679] |
| synthetic_increment_loss_interaction | 原3场 | IDF1 | +0.1137 | [-5.5607, +5.7881] | [-1.2703, +2.7502] | [-1.2046, +0.8057] |
| synthetic_increment_loss_interaction | 原3场 | DetA | -0.1148 | [-0.4419, +0.2123] | [-0.2472, +0.0161] | [-0.1803, -0.0486] |
| synthetic_increment_loss_interaction | 原3场 | MOTA | -0.2305 | [-0.5114, +0.0505] | [-0.3607, -0.1571] | [-0.2672, -0.1653] |
| synthetic_increment_loss_interaction | 旧外部2场 | AssA | +1.5132 | [-30.1493, +33.1758] | [-0.9787, +4.0051] | [-0.9787, +4.0051] |
| synthetic_increment_loss_interaction | 旧外部2场 | HOTA | +0.9305 | [-19.2883, +21.1494] | [-0.6607, +2.5218] | [-0.6607, +2.5218] |
| synthetic_increment_loss_interaction | 旧外部2场 | IDF1 | +1.3632 | [-25.6914, +28.4179] | [-0.7660, +3.4925] | [-0.7660, +3.4925] |
| synthetic_increment_loss_interaction | 旧外部2场 | DetA | -0.0865 | [-0.4405, +0.2675] | [-0.1144, -0.0586] | [-0.1144, -0.0586] |
| synthetic_increment_loss_interaction | 旧外部2场 | MOTA | -0.0546 | [-0.6615, +0.5523] | [-0.1024, -0.0068] | [-0.1024, -0.0068] |
| synthetic_increment_loss_interaction | 七场 | AssA | -0.1874 | [-1.0594, +0.6847] | [-0.8596, +0.3759] | [-0.3481, +0.1214] |
| synthetic_increment_loss_interaction | 七场 | HOTA | -0.1295 | [-0.7634, +0.5044] | [-0.6097, +0.2963] | [-0.2520, +0.0860] |
| synthetic_increment_loss_interaction | 七场 | IDF1 | -0.5461 | [-2.0681, +0.9759] | [-1.8374, +0.3835] | [-0.8406, +0.0343] |
| synthetic_increment_loss_interaction | 七场 | DetA | -0.0090 | [-0.1096, +0.0915] | [-0.0794, +0.0715] | [-0.0427, +0.0180] |
| synthetic_increment_loss_interaction | 七场 | MOTA | -0.1482 | [-0.4245, +0.1280] | [-0.3434, +0.0563] | [-0.2229, -0.0778] |

## 原因解释与可支持的结论

1. 同一新R池、曝光次序、标签、原模型/初始化/normalizer/AdamW和推理下，只将R的逐候选BCE换成集合CE。平均分回升符合“让同一窗的已知候选直接竞争”这一预期，但主区间全跨0、逐场仍混合正负，不能把它确认为稳定收益。
2. 仅改损失未恢复到原strongmotion水平，因此R损失形式不足以解释或消除上一轮退化。新R池仍是固定R-only teacher产生的自由状态，当前模型自由追踪会走出其他历史/候选状态；整高分stage并非精确enabled候选子集。状态分布差异仍是待检验假设，不能由本轮定位唯一原因。
3. 三池中1885/3000窗无known正例、256窗存在anchor偏离代理；unknown可能含真实目标，null监督只针对known集合，不能叫确认无人匹配，也不能把这256窗认定错标签。该弱标签/状态构成未随本轮改变，具体影响没有单独因果验证。
4. 绝对表中DetA变化相对小、AssA和IDF1相对原模型更低，问题主要表现在身份关联连续性，而非新增检测能力；不能因此宣布检测等效。历史错误会改变后续轨迹状态，但前轮严格oracle诊断eligible=0，本轮也未单独改history/Kalman，故不能声称已证实它们是主因。
5. 本轮只用motion，194维输入后170个Pose通道置0，未训练新的Pose监督；不能由本轮证明Pose有益或普遍无效。已有Pose实验未建立稳定增益，后续如考虑算法教师，应先确认可信可介入事件和标签质量，不能拿算法自身一致性充当真值。

建议继续使用原未校准strongmotion_RS作为研究主参照，保留本轮完整负结果。当前验证到此闭合，不自动扩模型/数据、搜阈值或继续新因素。若规划下一轮，应先以已有日志做有界的候选可达性/状态与标签资格核查，再依据证据决定一个因素。

## 证据与边界

- 完整原分析：[report.json](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_control_a01/analysis_a01/report.json)
- 独立终验：[receipt.json](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_final_verification_a01/receipt.json)
- 18臂正式18000更新/54000R9000S；R all-known764370/634320，S46287/25191；378完整检查点已独立核验，8诊断更新24R4S另计，未重放训练或旧评价。
- gap为原3690可信检测断档事件，非物理遮挡；15完整gap描述和全事件失败均保留原report.gap_comparisons及CSV。
- 12场均已观察开发，未进行新独立确认，不称盲测、泛化、SOTA、Pose或合成监督因果。
- [all_results_csv](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_control_a01/analysis_a01/all_results.csv) SHA 3ac30b12cdd753ada8ba32722ec70e092701a08e65126875c6a40777090ba725
- [all_paired_cells_csv](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_control_a01/analysis_a01/all_paired_cells.csv) SHA 25a93a4bc0695bebc8390d8149cebc91b4f74a864048021e2612b0a31cacbbe2
- [all_paired_gaps_csv](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_control_a01/analysis_a01/all_paired_gaps.csv) SHA d858ec9c4903e25787eceb664f56c93442fbab035c7a8d8c121776f1e4626a26
- [all_paired_matches_csv](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_control_a01/analysis_a01/all_paired_matches.csv) SHA b7a48c4cb3a9f20dcb574eb2b7630f99e1bbe02baefda7216c42aad45a1a1473
- [absolute_matches_csv](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_control_a01/analysis_a01/absolute_matches.csv) SHA 42648a7b774cb52ecd2980872612173e774c0abbb15aced47665a7b3e60bca4d
- [absolute_panels_csv](D:/projects/FutsalMOT_Research/pose/r_set_supervision_a01/tracking_control_a01/analysis_a01/absolute_panels.csv) SHA 21d34d249b645b13480464e220d95a40a9de438975df97d4dedd7a5202a46e61
