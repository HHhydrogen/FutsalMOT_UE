# 当前任务与下一步

更新：2026-10-29。历史过程见Git及对应运行收据；本页不保留过期PID流水。

## 当前：弱标签/可达性/历史暴露诊断已独立核查闭合，原strongmotion_RS保持主参照

[完整证据与下一步方案](Docs/research/RECORD_REUSE_DIAGNOSIS_A01_RESULTS.md)；[冻结有界协议](Docs/research/WEAK_LABEL_REACHABILITY_REUSE_A01.md)。本轮新增优化/R-S曝光/模型前向/图像推理/追踪推进/solver/GT坐标/TrackEval/渲染均0，producer/两个worker/verifier/launcher实际全退。原116/187/test封存，无本轮研究后台。

已复用540小metric及receipt、164844事件观察/3690原UID、82422配对；原6R单元3000窗/42465候选新交叉：693无正例且资格内unknown、455窗unknown成本可行、993空有效known，均不叫错标签证明。59案例槽/47窗，缺类不补。主gap比较maskRS−原RS改善754/退化1259，其中594为不同ID、585端点缺失、80歧义；这是fold/seed重复观察，不是独立比赛或物理遮挡。旧90CI原样引用不重算，无新模型成绩。

旧6RS固定12事件/6共享源描述组，全部priorunknown；12实际写入、36未来stage读取、14潜在资格stage，11连续exitoffset3/1断链null。仅证明wrong_uid暴露，不证明实际MLP或历史/KF因果。producer/独立checker各940旧前缀/372事件帧，预览1另列，新推进0。原235/eligible0/四支0/45null不改。

完成根dfd837da、独立核查e317b171、producer d83d8701；协议09ccd3cf/最小4文件f0c32a49，独立单文件34f466c3。原a01父stub误识别0数据任务失败及所有失败/缺失保留，只改执行门禁无成功任务重放。原三组正式180无逐帧native/history/KF/assignment，候选label子类型未存，不能拿SHA/聚合计数补造。

此前R资格mask18臂18000步/378检查点/180追踪及75+15区间仍完整闭合：新RS的12比赛均值全部低于原RS；[上轮绝对结果](Docs/research/R_CANDIDATE_ELIGIBILITY_A01_RESULTS.md)。主参照与默认部署配置本轮未改。

## 下一步与尚未解决的问题

- 研究主线仍是固定检测下合成Pose相关监督对身份关联的边际作用；本轮为motion训练资格对齐验证，未证明Pose收益，也没有解决整条论文主线。
- 下一协议优先独立后验去坐标事件索引（原3690UID→两端帧号/身份），单独冻结含GT原registry的读取/隔离范围；本轮未执行。再仅按主mask_RS对原RS的12来源×四转移×每类2最多96案例（aligned-RS仅作相同案例第三方法）、两端±5×三方法最多6336已有方法帧核对，固定seed20261024/原heldoutfold或game4，不挑seed或补满。
- 若内部状态仍缺，另签必要的小被动观测与plain/observer/coldABA/spawn数值准入，再据完整证据只选一个训练因素。原RS已有日志优先引用；两新模型×6train×固定前300最多3600推进仅候选上限，准入预算另冻，当前不执行，不从无snapshot中途续跑。
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
