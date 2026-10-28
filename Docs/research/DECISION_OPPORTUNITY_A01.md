# 既有训练日志的有效决策机会核查a01

2026-10-28用户已授权按完整负结果继续。研究主参照恢复原未校准strongmotion_RS；本轮新R来源模型及失败记录保留，不追加训练、不按比赛挑模型、不回滚已验工程源码。此前Pose方法未证明稳定增益，本阶段不预设新的Pose监督一定有效。

## 零更新范围与来源

仅复用已独立闭合的state_gap_diagnosis_a01/control_a02所绑定12项observe/posthoc（含继承a01和750准入的原物理路径）：原strongmotion R/RS×fold game4/game6/game9×seed20261024×每fold另外两个允许训练片段。SNMOT060/097/151各750帧，合计9000既有逻辑帧、2250唯一源帧、27000三stage记录、180118轨迹stage行。这里是新后验读取预算，不新增追踪帧推进。

新优化更新、模型前向、图像推理、追踪、分配器求解、TrackEval均0。不加载权重，不读取GT坐标、原媒体或训练池；身份标签只读既有posthoc。所有源SHA/UID/行数与一基连续帧逐条绑定。先单worker完整750日志流式准入，成功产物直接继承，随后两worker只补其余11任务；每在飞预留3GiB，物理RAM留8GiB/commit留6GiB。逐帧join原frames与posthoc rows，不物化整750帧、不删除失败partial或重放成功任务。

原历史模型条件：194→64→32→1 ReLU、14593参数、FP32、标准化后170Pose通道置0，无epoch扰动；1000更新，每步3R共3000R，RS另1S共1000S；AdamW学习率0.001/weight_decay0.0001，mean(3R)+mean(S)/3，last1000非EMA不选best。以上只解释原来源，本轮不执行这些更新。

原追踪high0.25/low0.10/new0.25/buffer30/high-match0.80/low-match0.50/unconfirmed0.70/fuse_score=True；candidate dt≤1.2秒、面积比0.25..4、归一中心≤2、模型概率0.50。最终reference_cost是原solver实际输入；bbox_base_cost可能含分数融合，不能称纯IoU。原high/unconfirmed active行先置成本1.0，仅enabled列写模型成本，p<0.50也折叠为1.0；inactive保留原bbox代价，low_score纯bbox。enabled由已验旁观调用原门禁函数重算，不冒称原forward内部直接捕获。

## 全分母与不可识别项

完整保留三stage、空候选、短历史、unknown、混合身份和无正候选。逐行互斥首停：非可信3历史、GT在场未知、当前GT缺席、可信正确raw缺失、正确raw不在stage、low仅bbox或learned inactive、正确motion gate拒绝、正确enabled拒绝、正确概率门槛拒绝、成本等号未知、成本高于门槛、实际正确、存在严格可行正确边却未匹配/选unknown/选可信错误。完整0类也报告，联合旗标另列，不把所有未匹配称排序错误。

局部成本只比较实际最终矩阵，不恢复未保存的logit/概率，不跑solver。严格cost<threshold只是单边代价满足，不保证全局可行解；cost==threshold独立未知，不添加epsilon。正确列被同stage其他row占用、正确raw在其他stage出现/被其他track实际分配均按记录列出，不据此声称改某个成本就能纠错。

当前history-consistent query与首次stage可信3历史anchor并列。anchor按时间从过去首次建立，不用未来终态回填；若当前历史整体跟到别人，动态query的正候选不等原目标的正确候选。没有完整持久化UID→GT索引，漂移后原anchor候选无法恢复时须显式不可识别。anchor漂移只为代理状态，非全局IDSW或历史写入因果。

## Pose几何支持与机会交叉

只用原17点xy_px与geometry_valid，有限坐标不等准确或可见。预登记身体关节索引5至16，末条历史与候选共同有效点至少6，实际原观测间隔1至30帧。每候选保留0至12共同点直方图、三条历史各自共同点数、unknown/bbox-only/不足6点和gap未知/超界，不添加置信度阈值；不报告PCK/OKS。

局部机会定义为：可信3条同身份历史、原模型active、至少一个当前query正候选enabled，且至少一个可信负候选也enabled。交叉统计正负双方是否均满足上述Pose几何支持、实际正确/可信错误/未匹配/unknown、原成本可行性及anchor漂移。它只是已有错误里Pose可能介入的结构范围，不是Pose信息足够、可纠正上界或追踪增益。

## 事前统计与后续选择

每任务先列全部绝对计数和完整账本；first_stop以全stage行为分母，bool旗标以该字段非null行为分母，null计数同时保留。R和RS分别对每训练源先等权平均两fold条件率，再对三训练源等权。全部首停类别及全部布尔旗标都给描述区间，不挑显著项；95%t df2/临界4.302652729749462，Python MT19937 randrange比赛bootstrap10000次/seed20261028/线性分位及逐源留一。任何一源分母缺失则该项CI=null，不能把事件、fold、R/RS当独立比赛。所有区间未经多比较校正，无性能δ/等效判断，无新AssA/HOTA/IDF1。

完成独立来源/账本/计数/退出核查后才选下一因素。若机会主要被接受门槛或训练任务分布限制，先立对应唯一因素；若存在足够可识别的motion困难且Pose结构支持机会，只支持另立Pose辨别力诊断，不能仅凭覆盖率直接启动大规模训练。后续候选方案可冻结motion、只学Pose残差，但必须有同容量motion/关支路/打乱控制，并把算法教师只当辅助约束而非真值。此阶段不同时修改采样、loss、模型、历史、Kalman或S。

三源都是已见训练比赛，当前12场开发均已观察，不能称盲测、泛化、SOTA或Pose因果。SNMOT116/187及test包始终封存。每阶段即时更新训练历史、实际状态并精确中文提交推送；有真实故障保留原attempt，先根因再独立恢复。
