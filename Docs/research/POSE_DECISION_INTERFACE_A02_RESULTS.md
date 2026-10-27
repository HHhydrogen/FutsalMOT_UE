# 新T分支到决策接口零更新完整结果

更新：2026-10-27。独立a02真实数值准入、18项完整评分及独立全记录终验均已完成，实际父控制器、两worker及launcher退出。新增优化、检测/Pose推理、自由追踪和TrackEval均为0，测试继续封存。

本轮没有找到支持直接放宽质量gate的新证据。在固定共同状态和当前首seed模型中，原q相对各自own-base没有产生可信正确分配的修复或破坏；q强制设为1后，T_RS原三场记录为0修复/13破坏，旧两场跨fold记录为1修复/6破坏。这个机制代理不能换算AssA，也不能证明全部Pose表示无用或关键点必然不准。

## 范围、数值和分母

- 固定seed20261024、balanced、三fold各原heldout和旧两外部：9原trace×T_RS/T_shuffle_RS两模型，共18单元、6个真实最终模型。自然Pose推理不shuffle，own-base/original-q/q1三分支均保留，q1不作为新正式追踪策略。
- 24CPU合同、实际6模型/9trace/18状态及串行对两个spawn worker逐值准入已通过。16个数值函数AST与a01完全一致，原q完整forward、195维输入、两种批路径、原代价/分配、q0及空边界均已实证；本次score2没有端到端串行速度对照，不借用track2+1的2.19倍。
- 单次流式独立终验核9份原trace的8281条原事件，对应两模型16562条评分事件、214334个stage行；完整16格转移、未知/混合历史/未匹配及全部负计数、输入身份和原顺序均通过。原trace仅记录非空stage，不代表所有视频帧/目标/空stage。
- 以下面板原三场为3单元/模型，旧两场为6单元/模型；外部每场在三fold共同历史中重复。原始计数作为记录分母，不能当成独立比赛或独立样本。近motion始终取原trainR校准，不新拟合阈值。

## 分面板完整计数

可信修复指在历史身份可信且当前GT存在的分母中，由错误/未知/未匹配变为known_correct；破坏是known_correct变为其余三类。排名计数仅取门内正负两类均已知的行，与全局分配计数不同。

| 模型 | 面板 | stage行 | 门内正负均已知 | 其中active | 原q排名修正/破坏 | 原q分配修复/破坏 | q1分配修复/破坏 |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| T_RS | 原三场留一 | 43813 | 15749 | 855 | 0/0 | 0/0 | 0/13 |
| T_shuffle_RS | 原三场留一 | 43813 | 15749 | 855 | 0/0 | 0/0 | 0/13 |
| T_RS | 旧两场外部 | 63354 | 23442 | 1153 | 1/0 | 0/0 | 1/6 |
| T_shuffle_RS | 旧两场外部 | 63354 | 23442 | 1153 | 0/0 | 0/0 | 1/5 |

## 全部18单元

| 模型 | fold | 比赛序列 | stage行 | 原q排名修正/破坏 | 原q可信分配修复/破坏 | q1可信分配修复/破坏 |
| --- | --- | --- | ---: | --- | --- | --- |
| T_RS | game4 | SNMOT-060 | 17261 | 0/0 | 0/0 | 0/2 |
| T_shuffle_RS | game4 | SNMOT-060 | 17261 | 0/0 | 0/0 | 0/1 |
| T_RS | game4 | v_2QhNRucNC7E_c017 | 9720 | 0/0 | 0/0 | 0/0 |
| T_shuffle_RS | game4 | v_2QhNRucNC7E_c017 | 9720 | 0/0 | 0/0 | 0/0 |
| T_RS | game4 | v_G-vNjfx1GGc_c004 | 11330 | 0/0 | 0/0 | 0/0 |
| T_shuffle_RS | game4 | v_G-vNjfx1GGc_c004 | 11330 | 0/0 | 0/0 | 0/0 |
| T_RS | game6 | SNMOT-097 | 14531 | 0/0 | 0/0 | 0/6 |
| T_shuffle_RS | game6 | SNMOT-097 | 14531 | 0/0 | 0/0 | 0/5 |
| T_RS | game6 | v_2QhNRucNC7E_c017 | 9863 | 0/0 | 0/0 | 0/0 |
| T_shuffle_RS | game6 | v_2QhNRucNC7E_c017 | 9863 | 0/0 | 0/0 | 0/0 |
| T_RS | game6 | v_G-vNjfx1GGc_c004 | 11188 | 0/0 | 0/0 | 1/1 |
| T_shuffle_RS | game6 | v_G-vNjfx1GGc_c004 | 11188 | 0/0 | 0/0 | 1/1 |
| T_RS | game9 | SNMOT-151 | 12021 | 0/0 | 0/0 | 0/5 |
| T_shuffle_RS | game9 | SNMOT-151 | 12021 | 0/0 | 0/0 | 0/7 |
| T_RS | game9 | v_2QhNRucNC7E_c017 | 9923 | 1/0 | 0/0 | 0/5 |
| T_shuffle_RS | game9 | v_2QhNRucNC7E_c017 | 9923 | 0/0 | 0/0 | 0/4 |
| T_RS | game9 | v_G-vNjfx1GGc_c004 | 11330 | 0/0 | 0/0 | 0/0 |
| T_shuffle_RS | game9 | v_G-vNjfx1GGc_c004 | 11330 | 0/0 | 0/0 | 0/0 |

## 保留的失败与GT边界

a01数值本身真实通过，但其来源验证实际解析了含endpoint_GT的registry，回执却误报进程没有加载GT；root拒绝其完整准入，原配置/代码/收据及metadata_review_root保留。独立a02只纠正声明和合同，重新真实数值准入后才开展本轮18评分，没有重放已完成正式单元。
a02如实标记来源验证读取GT账本；模型评分仅使用白名单预测字段，GT不作为输入、不筛候选。后验身份标签另读并明确记录，不能再称整个评分进程从未读过GT。终验不导入模型/Torch或GT标签，仅核已保存全记录和真实退出。
120个人工关键点样本本轮不采用，既有索引/空模板/工具归档保留。实际人工GT和独立复核均为0，不阻塞执行，也不报告这些样本的PCK/OKS或Pose准确率。

## 下一步的约束

现有证据不满足“有可修正线索而主要被q压住”的前提，因此不继续搜索残差系数、不直接开quality-gate新训练或重复513追踪。排名和全局转移都提示当前固定分支作用很小；这不区分信息噪声、训练学不到或表示容量等原因，不能据此自动补采或宣布数据无效。
下一项优先准备同一批已观察比赛、同一raw检测缓存、相同GT/ID0/全预测评价下的成熟追踪器参考，先固定算法版本、参数与数值/吞吐准入，再执行有限对照，区分检测输入与关联系统的短板。新增外观输入、检测器或训练容量各另立单因素协议，不把其收益归于Pose或合成。这里只登记方向，未执行成熟基线或新训练。12场均已观察，不能称新盲测，最终116/187与test包继续封存。

## 来源

- 冻结配置：`D:\projects\FutsalMOT_Research\pose\pose_velocity_decision_a01\frozen_a02\config.json`，SHA `9797db9d6f527c35ed508e003bd5d7e503dc8cd13f99b2274b91a059137d70ff`。
- 实际评分报告：`D:\projects\FutsalMOT_Research\pose\pose_velocity_decision_a01\diagnostic_a02\report.json`，SHA `d9a2d1624de56b489da4d5e236f05462efaa93b604f121739af6b8f91170de52`；18份summary与events.jsonl.gz完整保留。
- 独立终验：`D:\projects\FutsalMOT_Research\pose\pose_velocity_decision_a01\final_verification_a01\receipt.json`，SHA `ac9af80496979661446b6d9d9be604c7b05d779fab4141c57a74e02fcea8aedd`；原trace/事件/日志仅验一次，不重推模型。
- 学术定位和公开代表性结果见[论文计划](CVPR_2027_PAPER_PLAN.md)；当前内部分数不能与SportsMOT官方汇总直接排名。
