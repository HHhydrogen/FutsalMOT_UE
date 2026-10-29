# 当前任务与下一步

更新：2026-10-29。历史过程见Git及对应运行收据；本页不保留过期PID流水。

## 当前：R候选资格mask完整单因素已闭合，继续保留原strongmotion_RS

[完整结果与全部区间](Docs/research/R_CANDIDATE_ELIGIBILITY_A01_RESULTS.md)；[绝对参数/执行与失败记录](Docs/research/R_CANDIDATE_ELIGIBILITY_EXECUTION_A01.md)。18臂18000更新/54000R/9000S、357新读+首21继承覆盖378检查点、180追踪/评价、540新旧来源/450指标与450gap配对、75指标/15gap描述区间和独立终验均已真实闭合，训练/worker/controller/launcher/auditor/verifier全部实际退出。原116/187/test继续封存，无活动研究训练或追踪后台。

新RS在12场各比赛fold/seed平均AssA全部低于原strongmotion_RS。原三场绝对31.864158→27.369318，差−4.494840点/t95[-7.179558,-1.810123]；旧两场40.115976→38.255093，差−1.860883/[-11.670083,7.948317]；七场30.212884→27.773657，差−2.439227/[-4.336799,-0.541654]。同来源aligned-RS控制的三面板差−0.516406/+1.074445/−0.081950，t95全跨0，没有稳定mask改善。七场组内RS比R有正增量，不能替代主参照比较或证明Pose收益；全部正/负/零/null与bootstrap/LOO完整保留。

正式科学协议d5880b07/训练八文件98293655、追踪协议a5bd1186/四文件62e9c969不改。已知输入/控制器/核查器失败保留且不重放成功项；最终独立a02用fe028359单文件，flat计划及实际spawn父子身份修正15合同通过。完成根675d0752、训练根894ac390、预算b4d206ee、最终收据d3c15166、分析b6469841，根目录DResearch/pose/r_candidate_eligibility_a01。

下一步先核对已有MOT/native/公开后验/gap的标签可靠性、正确候选可达性及内部状态记录缺口；缺失不补造，候选资格诊断不当错误标签或历史/KF因果证据。另签有界诊断和结果前决策协议后只选一个新因素，本轮不自动加训或改默认部署配置。主参照继续原未校准strongmotion_RS；18新模型保留负结果。每轮结束即时历史/精确提交推送/汇报，无每日历史定时任务，整论文目标未取消。

## 下一步与尚未解决的问题

- 研究主线仍是固定检测下合成Pose相关监督对身份关联的边际作用；本轮为motion训练资格对齐验证，未证明Pose收益，也没有解决整条论文主线。
- 先登记现有MOT/native/公开后验/gap能回答哪些问题，再冻结有边界的零更新诊断。未知标签、正确候选缺失、内部历史缺失分别保留；不把低分或终局错误直接归因为标签错误/Kalman传播。
- 根据完整诊断只选一个下一因素，重新列绝对参数/输入/有效监督/预算/结果前分析与必要准入。原strongmotion_RS始终保留；本轮未安排新训练、检测Pose推理或渲染，不自动扩大模型/合成数据/轮数。
- Pose算法监督如需实施，须单独约束可靠身份锚点/unknown处理和split隔离，不把自身预测ID当GT。原120样本人工Pose项目已归档，不等待该项、不报PCK/OKS。

## 固定工作边界

- 116/187/test封存；12来源均为已观察开发，原3/旧2/七场分面板，不称新盲测/官方排名/SOTA/泛化或合成等效。
- DResearch保存真实输入/最小SHA代码/模型/完整记录；G媒体只引用，Saved只放小本机收据，不复制4K/环境或重建备份，不重放旧迁移/清理/成功训练审计。
- 每阶段和失败即时更新训练历史、精确中文提交推送和汇报，无每日定时历史维护。单master、不add-A/force/跳hooks，不混Saved/模型/媒体/号码资产WIP。
- 原八组冻结数据、绿色/球衣版本及未完成号码WIP继续保留。UE保持关闭，取消的专门渲染/EXR导出加速不恢复，不结束用户应用或改pagefile。

## 历史与证据入口

旧版本启动/恢复流水由Git和对应研究文档保留，不能作为今天重复执行的指令。

- [训练历史总览](Docs/research/TRAINING_HISTORY.md)：逐轮动机/绝对参数/数据split/结果/失败与原始证据。
- [R候选资格mask完整结果](Docs/research/R_CANDIDATE_ELIGIBILITY_A01_RESULTS.md)：本轮六方法/75+15区间/全部负结果。
- [资格与弱标签诊断](Docs/research/STATE_LABEL_ALIGNMENT_A01_RESULTS.md)：零更新诊断，不是因果收益证明。
- [R集合监督结果](Docs/research/R_SET_SUPERVISION_A01_RESULTS.md)及[自由状态R来源验证](Docs/research/STATE_ALIGNED_R_TRAINING_A01_RESULTS.md)。
- [历史状态传播诊断](Docs/research/TRAIN_FREE_STATE_GAP_A02_RESULTS.md)：零eligible、四支0、45区间null，不放宽规则或重跑。
- [全过程记录](Docs/operations/TRAINING_RECORDS.md)、[性能边界](Docs/operations/TRAINING_PERFORMANCE.md)、[存储规则](Docs/operations/STORAGE_POLICY.md)与[文档索引](Docs/README.md)。
