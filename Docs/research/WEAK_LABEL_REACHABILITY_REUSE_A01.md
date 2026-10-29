# 弱标签、正确候选可达与历史暴露：既有记录有界诊断a01

2026-10-29。原未校准strongmotion_RS保持主参照。先完成记录证据与下一步方案，不新增训练、模型前向、图像推理、追踪推进、solver、TrackEval、GT坐标读取或渲染；SNMOT116/187/test持续封存。

## 为什么还需诊断

R资格mask完整验证没有超越原RS，12场比赛平均AssA均下降。资格外监督占比83.528252%是覆盖差异，不是错标签率或已证主因。下一步要区分标签不确定、正确候选不可达和错误写入历史后的潜在暴露，不能继续凭总体成绩更换loss或加训。

## 阶段一：已核实的记录边界

三组正式180输出（原strongmotion、aligned-BCE、mask）保留MOT、frame_counts及聚合audit；没有持久化逐帧native/history/Kalman/assignment。新mask和aligned有native_output_frames_sha256，也不能据SHA恢复逐帧内容。新模型的这些内部字段必须记not_retained，不能将原teacher状态标签移植到新轨迹上。

540个既有metric报告保留逐gap事件event_uid、reason、endpoint_states及起止prediction_ID。原模型字段为recovery.events，新两组为gap.events。event_uid是SHA，不含可解析时序；公共registry receipt不提供事件帧表，完整registry含GT坐标，本轮不打开。可以按UID匹配端点恢复/退化，不能从UID定位前后MOT帧或宣称历史传播因果。

原标签由几何代理产生：双向唯一IoU≥0.5为matched，有冲突或IoU在[0.1,0.5)为unknown，全部IoU<0.1为unmatched；query/history不可靠时不强标。已派生候选只存0/1/null，逐候选negative/unknown子原因没有保留，不能用source_label_counts聚合值回填，也不以成本猜标签。本轮不改标签。

## 阶段二：三个事前固定的有界读取轴

| 轴 | 输入及最大读取 | 新增描述 | 明确不回答 |
|---|---|---|---|
| 训练弱标签与可达性 | 原6个R fold-source单元、3000 selected_windows、42465 selected_candidates；单元500窗/最多8000候选 | 无正例且资格内unknown、unknown严格成本可行、正例拒绝共现、空有效known、anchor漂移与可达层交叉 | 不能把unknown/无正例/anchor代理称错标签；不是新模型状态 |
| 三组端点转移 | 540登记小metric报告；最多199260事件观察、99630事件配对，独立事件UID总3690 | 新RS−原RS、新RS−alignedRS、新R−alignedR三族：恢复保持/改善/退化/持续失败及四原因转移 | 不是物理遮挡或真实历史传播；端点missing/ambiguous不是训练负标签 |
| 旧原RS历史暴露 | 6个RS旧日志，每unit按(frame_number,track_id,event_id)固定首2个既有switch，最多12事件；流式最多4500旧前缀帧记录、372错误帧及后30目标帧 | actual生命周期写入→wrong UID留在history→未来stage读取→原规则重算资格→挤出/lost/removed/源尾删失 | 只证明记录/潜在暴露，不证明导致新错配或Kalman主因；不是新mask模型 |

gap四原因严格为same_prediction_ID_recovered、different_prediction_ID、missing_prediction_endpoint、ambiguous_endpoint。恢复仅第一个；两边失败原因相同仍是持续失败。每单元/事件精确按UID配对，不按预测ID数值跨模型匹配；保留改善与退化，不按有利结果筛选。不同fold/seed的事件重复不能充作独立比赛。

训练案例固定6单元×五类×每类2窗，最多60槽位：正例概率拒绝、known负例严格成本可行、unknown严格成本可行、无正例且unknown、唯一正例可行控制。每类按(frame,stage,row,track,windowUID)排序，空类不补满，同窗多标签保留但展示去重。严格成本可行不等于已被分配；资格active/enabled来自原旁观规则重算，不等于每格实际执行MLP。

历史轴保留235原switch/231 priorunknown/4 trusted重复描述，旧eligible0、四分支0和45区间null原样引用，不放宽原oracle规则。首2条可含unknown，不称‘第一次真实错误’，缺失/断链/截尾显式记录。全部其他未选事件仍由源文件引用保留。

## 执行与验收

只装最小SHA源码，输出DResearch/pose/record_reuse_diagnosis_a01。CPU数值线程1，最多2独立只读worker（窗口与gap并行，历史顺序流式），物理RAM保留8589934592字节、commit6442450944字节，每在飞预留3221225472字节；不足缩为1或等待，不结束用户应用、不改pagefile。禁止读取权重、媒体、GT目录/完整registry和封存测试，不运行旧诊断或训练预算审计，不重扫180118旧逐stage行来重算已完成分类。

新统计仅整数描述、固定案例与证据缺失表，不新增追踪成绩、CI或p值；原75指标/15gap区间从已终验报告原样引用，不重算、不挑区间。三个轴由独立核查器核来源SHA、分母、UID配对、unknown/失败保留、上界与零更新边界。完成且实际worker/producer/verifier退出后才写结果报告和下一步方案，每阶段更新TRAINING_HISTORY/TASK及精确提交推送。

独立核查需要第二次有界I/O，另计最多4500旧前缀帧/372事件帧核对（producer与verifier合计最多9000旧job帧读取、744事件帧检查，新增追踪帧仍为0）。来源压缩字节SHA读取另列source_bytes_hashed，不冒充仅目标帧I/O，也不读取媒体。每个原帧日志文件最多512MiB；只流式解码一完整帧，不物化整750帧日志。

## 结果前决策约束

本轮不直接选训练因素。若现有资料不能区分标签子类型或新模型内部历史，下一步优先提出独立、极小、被动观测的补记录协议，明确原算法输出一致准入及绝对帧数；本轮不执行该观测。若可靠证据足以定位单一问题，再单独冻结一个因素，保留原RS及全部负结果，不能同时更改窗口、标签、loss、门槛、history/Kalman或Pose监督。

## 已闭合来源

- R资格mask完成根675d07528839ff34d39013a419db35f12dc2560bc4fa4457341a88bf490f52f7；完整分析b646984183bd90a652ac3d813a27db76950d67499f74607702f7c74145971310，540结果CSV绑定全部来源。
- 资格与弱标签完成根c140edaf7004f139de55a0edf265069ef73f98c63c454b434405ece00dddf8f9；只读其已派生六单元，不重建输入或标签。
- 旧state-gap完成根ad2eed7e78f5551e38c8db0c29a903348af2b5c6765e89b30c4f18f139a9804b；只读原6RS有界帧前缀与235事件描述，不重跑追踪/oracle。
