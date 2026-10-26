# v10完整结果：独立运动、困难采样与两场新比赛

更新：2026-10-26。54臂训练、253项自由追踪/评价、完整分析及实际进程退出已全部闭合。**Pose增量主门槛未达到**：平衡池gated−强motion_RS AssA为−0.0417点，困难池为+0.2110点，低于事前+0.5点。混合相对纯真实有小幅平均收益，不能据此声称合成等价真实样本或Pose已可靠超越运动。

## 真实协议与完成证据

- 新增三个原运动seed的3600对4K RGB/mask、36000逐视角人物Pose已发布到`G:/FutsalMOT_Dataset/v4_pose17_multiseed_green_a01`；另引用既有1048绿色B，共四运动。新增3600EXR/144520931344字节消费后已退休，UE正常退出。不重放采集或清理。
- 两个S池各1000唯一窗口、每运动250，四机位×五gap配额相同。balanced/hard_enriched自然缺失窗口0/26、框重叠窗口205/996；已知pair2799/3236，不是池间等pair或等计算。所有方法在同池共享S UID、标签和顺序。
- 强motion、同容量motion_residual、gated × 两池 × 三原比赛留一 × 三训练seed，共54个新RS；各1000更新、同3000R窗口同序、另1000S，FP32 AdamW lr.001/wd.0001、meanR+meanS/3、预取2、last1000，不选best。纯R来源只读复用，没有追加旧模型更新。
- 54训练独立核对54000更新/162000R/54000S窗口，实际R all/known pair608040/469476，S458676/162945；1134份完整模型/优化器/RNG检查点及全部逐步记录通过。6次诊断更新另计，优化器重放0。
- 253项评价包含10种比赛/PT参考组合、162个新RS模型-比赛组合和81个纯R模型-比赛组合；所有预测行保留、GT只指标/身份标签，GT Pose不入特征。新SportsMOT合法ID0原值保留，不伪造SoccerNet gameinfo，TrackEval1.3.0、DO_PREPROC=False。
- 最终state为`complete253_tracking_and_analysis`，分析含完整253项/50组配对；真实CIM确认相关控制器、子进程和UE全部退出。独立最终核验检查原MOT、评价SHA、GT一致性、每个配对差值/比赛和seed均值、全部分母及主门槛，无重训或重评。

## 两场新比赛：Pose相对强基线

两场是本轮开始前未观察过的开发验证：Dortmund–Schalke450帧、Norwich–Ipswich675帧，均25FPS。主结果两场等权，每场平均全部三fold×三seed；18个模型-比赛单元不是18场比赛。指标为百分点差值。

| 采样池 | gated−强motion_RS AssA | HOTA | IDF1 | AssA正训练seed | AssA负单元 | 事前联合门槛 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| balanced | -0.0417 | -0.0353 | +0.0503 | 1/3 | 8/18 | 未通过 |
| hard_enriched | +0.2110 | +0.1313 | +0.1041 | 2/3 | 6/18 | 未通过 |

事前门槛保持AssA均差≥0.5点、至少2/3训练seed为正、两新比赛均差非负、HOTA均差≥0、IDF1下降≤0.5点。困难池仅AssA幅度未达标；平衡池还未满足HOTA、seed和比赛方向条件。不修改门槛将小正值改称成功。

| 采样池 | seed 20261024 | 20261025 | 20261026 | Dortmund–Schalke均差 | Norwich–Ipswich均差 |
| --- | ---: | ---: | ---: | ---: | ---: |
| balanced | +0.0334 | -0.0006 | -0.1579 | -0.1627 | +0.0793 |
| hard_enriched | +0.1052 | -0.1681 | +0.6958 | +0.1878 | +0.2342 |

## 新比赛上的完整主要参照

| 比较 | ΔAssA | ΔHOTA | ΔIDF1 | AssA负单元 |
| --- | ---: | ---: | ---: | --- |
| balanced: gated−motion_residual | -0.2197 | -0.1477 | -0.1687 | 11/18 |
| balanced: gated−R | +0.2567 | +0.1925 | +0.3824 | 5/18 |
| balanced: gated−PT_bbox | +5.9712 | +4.2433 | +7.7047 | 0/18 |
| balanced: gated−PT_static_pose | +5.9239 | +4.2099 | +7.7335 | 0/18 |
| hard_enriched: gated−motion_residual | +0.1564 | +0.1012 | +0.0947 | 7/18 |
| hard_enriched: gated−R | +0.1927 | +0.1606 | +0.2073 | 6/18 |
| hard_enriched: gated−PT_bbox | +5.9073 | +4.2114 | +7.5297 | 0/18 |
| hard_enriched: gated−PT_static_pose | +5.8599 | +4.1780 | +7.5585 | 0/18 |

PT_bbox是固定预训练检测下的原ByteTrack参考，PT_static_pose额外使用固定PT Pose的静态成本；不是新训练Pose头的精度。高于PT约6点包含真实关联训练的作用，不能全部归于合成数据；同3000R的纯R比较仅约+0.19至+0.26点，且存在下降单元。

| 方法与采样池 | ΔAssA，相对本方法纯R | ΔHOTA | ΔIDF1 | AssA负单元 |
| --- | ---: | ---: | ---: | --- |
| balanced/motion | +0.3878 | +0.2805 | +0.4081 | 6/18 |
| balanced/motion_residual | +0.5681 | +0.3902 | +0.6409 | 6/18 |
| balanced/gated | +0.2567 | +0.1925 | +0.3824 | 5/18 |
| hard_enriched/motion | +0.0712 | +0.0820 | +0.1794 | 6/18 |
| hard_enriched/motion_residual | +0.1281 | +0.1094 | +0.2025 | 6/18 |
| hard_enriched/gated | +0.1927 | +0.1606 | +0.2073 | 6/18 |

## 新比赛绝对指标与困难采样的边界

| 模型 | AssA % | HOTA % | IDF1 % |
| --- | ---: | ---: | ---: |
| PT_bbox | 34.1030 | 45.9262 | 50.0427 |
| PT_static_pose | 34.1504 | 45.9596 | 50.0139 |
| balanced/motion | 40.1160 | 50.2047 | 57.6972 |
| balanced/motion_residual | 40.2939 | 50.3172 | 57.9162 |
| balanced/gated | 40.0743 | 50.1695 | 57.7475 |
| hard_enriched/motion | 39.7994 | 50.0062 | 57.4684 |
| hard_enriched/motion_residual | 39.8539 | 50.0364 | 57.4778 |
| hard_enriched/gated | 40.0103 | 50.1376 | 57.5725 |
| R/motion | 39.7281 | 49.9242 | 57.2890 |
| R/motion_residual | 39.7258 | 49.9269 | 57.2753 |
| R/gated | 39.8176 | 49.9770 | 57.3651 |

| hard_enriched−balanced | ΔAssA | ΔHOTA | ΔIDF1 | AssA负单元 |
| --- | ---: | ---: | ---: | --- |
| motion | -0.3166 | -0.1985 | -0.2288 | 12/18 |
| motion_residual | -0.4400 | -0.2808 | -0.4384 | 11/18 |
| gated | -0.0639 | -0.0319 | -0.1750 | 9/18 |

困难池的gated绝对AssA反而较平衡池低0.0639点；它相对强motion转正，同时伴随motion下降0.3166点。不能由相对差值转正推断困难采样提高了Pose本身。不同池已知pair预算不同，困难事件、框重叠与候选数共同变化，也不能单归因于某一种遮挡因素。

## 原三比赛留一：完整保留次要证据

| 比较 | ΔAssA | ΔHOTA | ΔIDF1 | AssA负单元 |
| --- | ---: | ---: | ---: | --- |
| balanced: gated−motion | -0.1352 | -0.0944 | -0.1450 | 4/9 |
| balanced: gated−motion_residual | -0.0180 | -0.0079 | +0.0059 | 4/9 |
| balanced: gated−R | +0.4693 | +0.2970 | +0.2845 | 4/9 |
| balanced: gated−PT_bbox | +5.0018 | +3.7317 | +5.7782 | 0/9 |
| balanced: gated−PT_static_pose | +5.1129 | +3.8271 | +5.8182 | 0/9 |
| hard_enriched: gated−motion | -0.0286 | -0.0105 | +0.0378 | 6/9 |
| hard_enriched: gated−motion_residual | +0.3106 | +0.2259 | +0.1767 | 4/9 |
| hard_enriched: gated−R | +0.6244 | +0.4437 | +0.2565 | 4/9 |
| hard_enriched: gated−PT_bbox | +5.1569 | +3.8784 | +5.7502 | 0/9 |
| hard_enriched: gated−PT_static_pose | +5.2680 | +3.9738 | +5.7902 | 0/9 |

原三场均已多轮观察，不能替代新比赛验证。其gated−强motion两池仍为负，不以混合−R的正值掩盖这一点。全部其他方法、各fold/seed/比赛细节及负单元在原分析中保留。

## 检测断档proxy恢复

新两场结果前注册214+183=397个可信断档事件。下表将397个相同事件在九个训练模型上的恢复次数汇总；这是同一事件集的模型重复，不是3573个独立事件。PT只运行一次两场。旧三场另有956事件，分母不与合成874个自然缺失事件账本混用。

| 模型 | 成功/全部模型-事件观察 | 事件加权恢复率 % |
| --- | ---: | ---: |
| PT_bbox | 164/397 | 41.3098 |
| PT_static_pose | 165/397 | 41.5617 |
| balanced/motion | 1668/3573 | 46.6835 |
| balanced/motion_residual | 1673/3573 | 46.8234 |
| balanced/gated | 1667/3573 | 46.6555 |
| hard_enriched/motion | 1672/3573 | 46.7954 |
| hard_enriched/motion_residual | 1668/3573 | 46.6835 |
| hard_enriched/gated | 1662/3573 | 46.5155 |
| R/motion | 1663/3573 | 46.5435 |
| R/motion_residual | 1658/3573 | 46.4036 |
| R/gated | 1661/3573 | 46.4875 |

困难池gated恢复率46.5155%，低于同池强motion的46.7954%；平衡池46.6555%也略低于强motion的46.6835%。本轮没有证明Pose增加断档恢复能力。规则是双向唯一IoU≥0.5的可信检测端点、连续有效GT、缺2–29帧、端点间距≤30；可包括raw歧义，不是物理遮挡真值。所有注册事件为分母，缺预测、歧义和换ID均计失败。

## 记录、局限与下一步

- 完整54,000步loss/Rloss/Sloss/LR/梯度/耗时/R与S UID/epoch/all及known pair/链、1,134份模型+优化器+完整RNG、环境、原stdout/stderr、全部评价均在实际D研究根。论文`paper_training_archive_a01`有原始步CSV、预算CSV及六图各PNG/PDF；50步均值仅用于展示，不选best。
- RS额外1000S带来额外计算和监督，未做等额额外真实窗口替代对照，不能称合成等价真实。当前关联器不读RGB，不能用颜色/纹理的自然程度解释下游因果；固定PT预测Pose与身份窗口是本轮实际输入。
- 两新比赛是短开发片段，三fold/seed不是独立比赛重复，未证明统计显著或真实五人制泛化。最终SNMOT116/187及test包始终封存。
- visibility仍unknown，source的diagnostic/not_training/MRQ_syncfalse限制保留；独立研究准入不升级物理可见性或同步多视角真值。短样1044 R0曾有7.0251毫米差异，完整批world逐值一致不证明具体成因已解决。
- 下一阶段建议先在固定权重/输入上诊断Pose残差对正确和错误困难候选的实际影响、门控触发覆盖及身份错误来源，再决定是否另立方法或数据干预。当前数据规模扩充和困难采样尚未证明可靠Pose增量，不自动续训、挑阈值/比例或重渲染。

关键结果位于`D:/projects/FutsalMOT_Research/pose/multiseed_v10_a01`：

| 文件 | 作用 |
| --- | --- |
| `tracking_control_a01/analysis_a01/report.json` | 全253项及50组比较/全部seed和负结果 |
| `tracking_control_a01/analysis_a01/all_tracking_metrics.csv` | 全部逐模型-比赛指标 |
| `postrun_audit_a01/actual_budget.json` | 真实训练与完整检查点独立核验 |
| `final_verification_a01/receipt.json` | 最终253项/MOT/评价/配对/分母/实际退出闭合 |
| `paper_training_archive_a01/complete.json` | 全训练CSV/曲线及原run来源索引 |
| `evaluation_inputs_a01/gap_registry.json` | 结果前1353个可信断档事件与来源 |
