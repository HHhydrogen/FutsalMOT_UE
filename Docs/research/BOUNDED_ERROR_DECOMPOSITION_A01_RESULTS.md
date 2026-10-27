# 一次有边界的身份关联错误条件分解结果

2026-10-27。按[固定范围](BOUNDED_ERROR_DECOMPOSITION_A01.md)完成18CPU合同、9份已保存分配的8281事件逐值准入、27份完整后验账本、8合同与独立全量终验。两个worker、控制器和launcher实际退出；模型加载/新评分、SGD、自由追踪、TrackEval、新媒体和测试读取均0。

## 覆盖范围及本次新增内容

12源90个原强motion单元中，旧五场balanced27份共同状态trace与原job/MOT SHA/audit精确对应：原三场各3seed，旧两场各3fold×3seed。新七场63份没有内部trace，本轮全部保留unknown，只引用其已有输出后验和评价，不为补齐日志重放。hard27不混入。

固定24863个非空高分stage调用、320752条重复状态行。stage0是主高分关联，stage1是未确认关联；低分第二关联、空矩阵、完整出生/确认/lost/删除未记录。行数不是视频帧数、独立人物数或错误事件数。

没有重复原54信息链或18新T模型评分。本次新增的是基于实际reference_cost重建原stage分配，与原候选/gate、单边可行性、排序/并列/全局占列的联合条件，以及每track首次trusted3历史anchor后的相对漂移。9份原保存reference逐事件相同，证明当前绑定的原FP32 solver复核一致；不将本次installed matching源码快照倒签成历史逐文件SHA。

## 全部首个未满足条件

顺序标签按事前协议，不是根因；分母是每个原单元的全部已记录stage-row，先单元率、再比赛内平均、最后原三场/旧两场分别比赛等权。方括号为95%t区间，单位也是百分点，不是性能差值。

| 观察标签 | 全27重复行计数 | 原三场条件率 | 旧两场条件率 |
| --- | ---: | --- | --- |
| current_GT_absent | 7915 | 1.9431% [1.1810, 2.7052] | 2.7904% [-6.4305, 12.0112] |
| global_competition_or_solver_unmatched | 72 | 0.0397% [-0.0490, 0.1284] | 0.0120% [-0.1254, 0.1493] |
| history_fewer_than3 | 17197 | 5.2463% [2.4868, 8.0057] | 5.4699% [-11.3038, 22.2435] |
| history_unknown | 131447 | 41.4996% [28.8163, 54.1829] | 40.4379% [4.4656, 76.4102] |
| known_negative_cost_lower | 4 | 0.0000% [0.0000, 0.0000] | 0.0023% [-0.0267, 0.0313] |
| minimum_cost_tie | 0 | 0.0000% [0.0000, 0.0000] | 0.0000% [0.0000, 0.0000] |
| mixed_trusted_history | 69 | 0.0327% [-0.0236, 0.0889] | 0.0136% [-0.1595, 0.1867] |
| no_raw_geometry_candidate | 4870 | 1.8858% [0.5549, 3.2167] | 1.2795% [-0.5448, 3.1038] |
| no_single_edge_feasible_positive | 289 | 0.0702% [-0.0759, 0.2163] | 0.1069% [-0.5998, 0.8136] |
| positive_outside_effective_gate | 63 | 0.0495% [-0.1313, 0.2303] | 0.0040% [-0.0463, 0.0542] |
| positive_raw_not_in_stage | 4893 | 1.5880% [0.3432, 2.8329] | 1.4885% [1.2236, 1.7534] |
| raw_geometry_ambiguous | 9935 | 2.8921% [1.6108, 4.1733] | 3.2295% [-1.0309, 7.4899] |
| reference_stage_selected_correct | 6471 | 2.1081% [1.7049, 2.5112] | 1.9604% [-0.5599, 4.4806] |
| row_not_intervened | 137486 | 42.6278% [29.8238, 55.4318] | 43.1952% [-5.9590, 92.3494] |
| unclassified_preserved | 0 | 0.0000% [0.0000, 0.0000] | 0.0000% [0.0000, 0.0000] |
| unknown_competition_or_assignment | 41 | 0.0172% [0.0080, 0.0264] | 0.0101% [-0.1059, 0.1261] |

全部首停计数之和为320752，联合标志和原成本另行保留。history_unknown为131447行（全记录40.98%），row_not_intervened为137486行；不能把这些未知或bbox政策行统称MLP排序错误。

## 已知active/current-present条件下的有限证据

分母共12506个重复记录行，指模型介入且当前历史一致身份在该帧GT中存在；并不代表所有关联错误。下表仍先比赛内平均训练单元，再比赛等权，不把12506行当独立样本。

| 条件 | 全27记录计数 | 原三场条件率 | 旧两场条件率 |
| --- | ---: | --- | --- |
| positive_outside_effective_gate | 63 | 1.2594% [-3.3915, 5.9103] | 0.0872% [-1.0205, 1.1949] |
| no_single_edge_feasible_positive | 289 | 1.7478% [-1.8996, 5.3952] | 2.6259% [-11.6229, 16.8747] |
| known_negative_cost_lower | 4 | 0.0000% [0.0000, 0.0000] | 0.0567% [-0.6643, 0.7778] |
| minimum_cost_tie | 0 | 0.0000% [0.0000, 0.0000] | 0.0000% [0.0000, 0.0000] |
| global_competition_or_solver_unmatched | 72 | 0.9815% [-1.1740, 3.1370] | 0.3546% [-3.7913, 4.5006] |
| unknown_competition_or_assignment | 41 | 0.4234% [0.1934, 0.6534] | 0.2433% [-2.4863, 2.9729] |
| reference_stage_selected_correct | 6471 | 51.5674% [46.4907, 56.6441] | 51.7676% [46.0111, 57.5240] |

正确候选成本未通过原solver单边可行性有289行，占该条件分母2.31%、全记录约0.090%；已知负例成本更低只有4行。这个局部证据更适合一个小的接受尺度检验，尚不支持立即扩大MLP或改变竞争训练，也不说明排序问题在未知行不存在。单边可行性由原1×1 solver实测，FP32 cutoff边界保留，不用正logit或epsilon替代。

global_competition_or_solver_unmatched的72行不是72个已确认全局竞争根因；只有同时记录正确列被其他行占用时，才有该占列证据。表中七项不覆盖全部先前条件，不能加成100%或当因果错误占比。

## 当前历史身份与整条轨迹身份不同

native结果只在当前历史一致且该GT当前存在时定义：延续该历史GT 147682行、其他可信GT/远离GT的未匹配检测94行、未知候选7866行、未分配25679行。这里的“延续正确”不是整条MOT轨迹ID正确，不能将94行换算为总体错误率或IDSW。

相对每track首次可信三观测anchor，19828行已变成另一个一致历史身份；混合历史为69行。19828是重复状态行，不是独立ID切换数，也不证明历史更新导致错误；首次anchor不是TrackEval的全局最优身份映射。一条轨迹漂移后仍可能连续跟随另一人，因此“当前历史一致”会掩盖部分长期身份问题。该限制不足以直接启动历史保护算法。

lost_gap原字段完整保留在原trace，并由新账本unit.trace/source_event_number/row_index精确追溯；不重复复制到新row，也没有新增lost_gap分层区间。执行前的storage clarification独立保存，未修改已冻结方案字节、成本或分类代码。

## 唯一后续因素与停止边界

选择一个小而可证伪的trainR-only截距校准测试：每个原strongmotion R/RS模型只拟合一个β，允许正或负；固定原训练R窗口和权重，不用验证集选方向、β或门槛。特征、原模型权重、候选/gate、历史、生命周期、Pose与原概率接受阈值不变。新增标量拟合有监督，SGD为0，不叫无监督或零训练。

选择理由仅是可识别条件中成本可行性问题比已知排序更明显，且该测试成本低、可证伪；不是已找到主要瓶颈，不预期必然上涨。更大MLP、相对排序训练、历史保护和外观因素均不同时推进。

每模型固定1000个原clean baseR唯一窗口一次，窗等权/窗内known pair等权，unknown与空known窗完整保留、空窗对目标贡献0且分母仍1000。额外18000次R窗口复读和pair计算另计，不称严格同总训练曝光或新增独立真实数据。β拟合前后NLL/Brier只作拟合诊断；训练R目标降低不等独立效用。

β0只在原forward身份/数值门禁通过后来源复用；βR自由追踪独立推进自己的候选与历史，不能把固定状态评分当AssA。若β32精确0才可别名原成品，不设近零性能阈值或据验证成绩回退。βR−0的R/RS及交互差分按固定3/2/7开发面板保留全部负结果和区间；测试继续封存。该唯一因素另冻协议后执行，不在本账本中伪造已验证。

## 统计、资源与完整来源

共112个条件率描述区间，t95(df=n−1)主、10000次比赛bootstrap(seed20261027)、逐场留一完整保留；未经多比较校正。全局计数只是记录分母，CI不按row或fold/seed独立抽样。零观察的退化[0,0]只描述固定面板未观察到差异，不证明总体概率为零。条件标签均不是性能差值、因果比例或等效检验，新七场内部条件没有数值/区间。

两个后验worker复用已验生命周期与资源函数；控制器至全汇总28.7038秒，采样进程树RSS峰0.4082GiB，最低可用RAM14.3191GiB。仅此后验阶段计时，不含准备/数值准入/终验与退出尾部，不当新串行提速或视频FPS。

实际九份数值、27份账本及独立终验均首attempt通过，成功重放0；全部原trace/MOT/模型和先前失败不改。独立终验只核已有trace/新账本/计数与区间，不再求solver，不开原cache/GT坐标/标签文件或模型。数值准入整读的旧score events含GT派生后验metadata，已明确loaded=true，但不用于分配输入；没有误报整个进程从未加载GT派生信息。

- [正式配置](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/frozen_a01/config.json)，SHA `6b54e99e4971bf3540a29085220941884e607ff9cdcc2a714bcbfb70f906f56d`。
- [9份数值准入](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/numeric_admission_a01/receipt.json)，SHA `13324d9f47341ef9cf6056dfe5337d00c43f9b58721f7ad954241e0d83577996`。
- [完整来源盘点](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/inventory_a01/manifest.json)，SHA `e946ccd0545ca835ed73e66d79c494e6caa0174ca0b286e0f07315bbe56ebf8e`。
- [完整分析](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/analysis_a01/report.json)，SHA `a8c9d467e9b0239486d86be6198ea80867ab9f0663132ff7b863f4e039ccb137`。
- [独立终验](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/final_verification_a01/receipt.json)，SHA `f54cf77280da82b5beef780be1a06093440eb19e5fb69219d862bdee697c14f1`。
- [lost_gap存储说明](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/scope_clarification_a01.json)，SHA `4c97b607c2382b5b3abe52682fc374402ed299b168fb0e1322d4638ea153ac61`。
- [27单元全部计数](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/analysis_a01/all_units.csv)。
- [五场全部条件率](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/analysis_a01/all_match_condition_rates.csv)。
- [90单元内部覆盖与63未知](D:/projects/FutsalMOT_Research/pose/bounded_error_decomposition_a01/analysis_a01/all90_internal_coverage.csv)。
- 全部320752条逐行联合条件、原实际成本、锚点/未知状态和源事件键保存在analysis_a01/units/<原unit_id>/all_stage_rows.jsonl.gz；源代码/原stdout与stderr、worker退出、既有分配对照及全部负结果留存DResearch。
