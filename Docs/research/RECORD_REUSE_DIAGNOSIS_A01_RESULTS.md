# 弱标签、正确候选可达与历史暴露：既有记录诊断完整结果

2026-10-29。三个轴及独立核查已真实完成，producer、两个只读worker、verifier和启动器均已退出。原strongmotion_RS继续为主参照，最终116/187/test持续封存。本轮所有新优化更新、R/S训练曝光、模型前向、图像推理、追踪推进、solver、GT坐标读取、TrackEval和渲染均为0。

## 结论与通俗解释

现有证据不足以选择下一训练因素。标签记录中确有大量不确定候选，但尚没有逐pair标错证明；正确候选可达性只能在旧R teacher窗口中分层，不能移植成新模型的内部状态；旧历史中能看到wrong_uid被写入和再读取，但不能证明它造成后续错误。下一步优先补齐去坐标事件索引与固定案例后验映射，再决定必要的小范围被动日志，暂不加训。

新mask相对原RS的主比较仍保持上轮结论：12开发比赛的平均AssA全部较低。旧75指标/15gap区间完整引用，不重算、不筛选；[上轮完整绝对成绩及区间](R_CANDIDATE_ELIGIBILITY_A01_RESULTS.md)。本轮风险计数不是新AssA或性能CI，不能与比赛成绩混合。

## 已有记录实际覆盖与读取预算

| 项目 | 实际 | 事前上限/口径 |
|---|---:|---|
| 既有metric/追踪收据 | 540/540 | 540/540，原/对齐/mask三组×R/RS |
| 公开gap事件观察 | 164844 | 199260，含fold/seed重复 |
| 去重事件UID | 3690 | 原3690，未重登记 |
| 三族事件配对 | 82422 | 99630，非独立比赛/新事件 |
| R派生窗口/候选 | 3000/42465 | 3000/42465，6fold-source/3train来源 |
| 案例槽位/去重窗口 | 59/47 | 最多60，不补满 |
| 旧RS轨迹事件/共享源描述组 | 12/6 | 最多12事件，跨fold上下文不充独立物理事件 |
| producer旧前缀帧/事件帧 | 940/372 | ≤4500/372，均既有记录读取 |
| verifier独立旧前缀帧/事件帧 | 940/372 | 第二次有界I/O单列，新增推进0 |

另在冻结前只预览1条旧RS帧schema；与producer/verifier的940+940前缀读取分开，不称1881独立图像。压缩字节SHA读取另在原report.IO和独立收据source_bytes_hashed登记，没有媒体哈希或图像读取。

## 弱标签风险：只限原R首seed teacher的3000训练窗口

原标签为几何代理：双向唯一IoU≥0.5为matched，冲突或[0.1,0.5)为unknown，全部IoU<0.1为unmatched；query/history不可靠时保持null。已派生数据只有0/1/null，逐candidate negative/unknown子原因没有保留。下面是风险计数，不是错标签率；未删除、重标或移植标签。

| 风险 | 窗口数/3000 |
|---|---:|
| 无known正例且有资格内unknown | 693 |
| 有严格成本可行的unknown | 455 |
| known正例概率拒绝且unknown可行共现 | 0 |
| 资格内有效known为空 | 993 |
| anchor身份偏离代理 | 256 |

对应pair：资格内unknown2081，其中680严格成本可行；known负例77严格成本可行；known正例48概率拒绝。严格成本可行不等于实际分配，更不等于误匹配。1547个无known正例且含unknown是原全候选范围，693只取资格内unknown的新交叉，两个分母条件不同。

### 可信正确raw可达层

| 互斥可达层 | 窗口数 |
|---|---:|
| 当前query身份GT不在场代理 | 808 |
| 同帧无可信正确raw | 742 |
| 可信正确raw在同帧但不在该stage | 335 |
| stage内正确raw不在评分资格内 | 23 |
| 资格内正确raw被概率门槛拒绝 | 48 |
| 资格内正确raw严格成本可行 | 1044 |

本漏斗优先按当前GT在场代理→raw存在→stage→资格→成本分层，不重算旧B_class；808与旧B_class的191不是相同条件，前者也包含带unknown的窗口。742不等于确证检测漏框，335也不等于新模型漏评分。数据均来自旧teacher的query/history，不能与新mask的轨迹身份直接join而冒充真值。

案例固定6单元×五风险×每类2窗，按frame/stage/row/track/windowUID排序；实际59槽/47窗口，多标签保留、重复展示去重、缺类不补。逐候选标签与negative_subtype/unknown_subtype=not_retained，以及全部交叉/分箱保存在window_records.jsonl、window_summary.json、window_cases.json。

## gap端点配对：恢复保持、改善、退化与持续失败

| 比较 | 恢复保持 | 改善 | 退化 | 持续失败 | 合计 |
|---|---:|---:|---:|---:|---:|
| mask_RS 对 原strongmotion_RS | 11425 | 754 | 1259 | 14036 | 27474 |
| mask_RS 对 aligned-BCE_RS | 11719 | 460 | 680 | 14615 | 27474 |
| mask_R 对 aligned-BCE_R | 11542 | 422 | 595 | 14915 | 27474 |

每族27474是事件×fold/seed的匹配观察数；每族仍只有原3690个事件UID，不能按82422或27474当独立样本计算CI。结果是按同event_uid配对，不跨模型比较预测ID编号本身。两边同样失败仍是持续失败，不算恢复。

主比较的1259条退化观察中，594为原已恢复而新两端ID不同，585为新端点缺失，80为新端点歧义；754条改善中，403从不同ID恢复、208从缺失恢复、143从歧义恢复。缺失端点不能直接归因检测、Kalman或track生命周期；即使原检测缓存固定，输出框/激活/匹配状态仍可能改变。

### 全部四原因转移（旧参照→新mask）

| 比较 | 原因转移 | 观察数 |
|---|---|---:|
| mask_RS 对 原strongmotion_RS | 端点匹配歧义 → 端点匹配歧义 | 1029 |
| mask_RS 对 原strongmotion_RS | 端点匹配歧义 → 两端预测ID不同 | 54 |
| mask_RS 对 原strongmotion_RS | 端点匹配歧义 → 预测端点缺失 | 105 |
| mask_RS 对 原strongmotion_RS | 端点匹配歧义 → 同一预测ID恢复 | 143 |
| mask_RS 对 原strongmotion_RS | 两端预测ID不同 → 端点匹配歧义 | 30 |
| mask_RS 对 原strongmotion_RS | 两端预测ID不同 → 两端预测ID不同 | 1048 |
| mask_RS 对 原strongmotion_RS | 两端预测ID不同 → 预测端点缺失 | 120 |
| mask_RS 对 原strongmotion_RS | 两端预测ID不同 → 同一预测ID恢复 | 403 |
| mask_RS 对 原strongmotion_RS | 预测端点缺失 → 端点匹配歧义 | 71 |
| mask_RS 对 原strongmotion_RS | 预测端点缺失 → 两端预测ID不同 | 106 |
| mask_RS 对 原strongmotion_RS | 预测端点缺失 → 预测端点缺失 | 11473 |
| mask_RS 对 原strongmotion_RS | 预测端点缺失 → 同一预测ID恢复 | 208 |
| mask_RS 对 原strongmotion_RS | 同一预测ID恢复 → 端点匹配歧义 | 80 |
| mask_RS 对 原strongmotion_RS | 同一预测ID恢复 → 两端预测ID不同 | 594 |
| mask_RS 对 原strongmotion_RS | 同一预测ID恢复 → 预测端点缺失 | 585 |
| mask_RS 对 原strongmotion_RS | 同一预测ID恢复 → 同一预测ID恢复 | 11425 |
| mask_RS 对 aligned-BCE_RS | 端点匹配歧义 → 端点匹配歧义 | 1069 |
| mask_RS 对 aligned-BCE_RS | 端点匹配歧义 → 两端预测ID不同 | 15 |
| mask_RS 对 aligned-BCE_RS | 端点匹配歧义 → 预测端点缺失 | 44 |
| mask_RS 对 aligned-BCE_RS | 端点匹配歧义 → 同一预测ID恢复 | 53 |
| mask_RS 对 aligned-BCE_RS | 两端预测ID不同 → 端点匹配歧义 | 21 |
| mask_RS 对 aligned-BCE_RS | 两端预测ID不同 → 两端预测ID不同 | 1328 |
| mask_RS 对 aligned-BCE_RS | 两端预测ID不同 → 预测端点缺失 | 63 |
| mask_RS 对 aligned-BCE_RS | 两端预测ID不同 → 同一预测ID恢复 | 238 |
| mask_RS 对 aligned-BCE_RS | 预测端点缺失 → 端点匹配歧义 | 52 |
| mask_RS 对 aligned-BCE_RS | 预测端点缺失 → 两端预测ID不同 | 77 |
| mask_RS 对 aligned-BCE_RS | 预测端点缺失 → 预测端点缺失 | 11946 |
| mask_RS 对 aligned-BCE_RS | 预测端点缺失 → 同一预测ID恢复 | 169 |
| mask_RS 对 aligned-BCE_RS | 同一预测ID恢复 → 端点匹配歧义 | 68 |
| mask_RS 对 aligned-BCE_RS | 同一预测ID恢复 → 两端预测ID不同 | 382 |
| mask_RS 对 aligned-BCE_RS | 同一预测ID恢复 → 预测端点缺失 | 230 |
| mask_RS 对 aligned-BCE_RS | 同一预测ID恢复 → 同一预测ID恢复 | 11719 |
| mask_R 对 aligned-BCE_R | 端点匹配歧义 → 端点匹配歧义 | 1127 |
| mask_R 对 aligned-BCE_R | 端点匹配歧义 → 两端预测ID不同 | 36 |
| mask_R 对 aligned-BCE_R | 端点匹配歧义 → 预测端点缺失 | 37 |
| mask_R 对 aligned-BCE_R | 端点匹配歧义 → 同一预测ID恢复 | 34 |
| mask_R 对 aligned-BCE_R | 两端预测ID不同 → 端点匹配歧义 | 22 |
| mask_R 对 aligned-BCE_R | 两端预测ID不同 → 两端预测ID不同 | 1534 |
| mask_R 对 aligned-BCE_R | 两端预测ID不同 → 预测端点缺失 | 68 |
| mask_R 对 aligned-BCE_R | 两端预测ID不同 → 同一预测ID恢复 | 238 |
| mask_R 对 aligned-BCE_R | 预测端点缺失 → 端点匹配歧义 | 57 |
| mask_R 对 aligned-BCE_R | 预测端点缺失 → 两端预测ID不同 | 65 |
| mask_R 对 aligned-BCE_R | 预测端点缺失 → 预测端点缺失 | 11969 |
| mask_R 对 aligned-BCE_R | 预测端点缺失 → 同一预测ID恢复 | 150 |
| mask_R 对 aligned-BCE_R | 同一预测ID恢复 → 端点匹配歧义 | 48 |
| mask_R 对 aligned-BCE_R | 同一预测ID恢复 → 两端预测ID不同 | 343 |
| mask_R 对 aligned-BCE_R | 同一预测ID恢复 → 预测端点缺失 | 204 |
| mask_R 对 aligned-BCE_R | 同一预测ID恢复 → 同一预测ID恢复 | 11542 |

event_uid是不可解析SHA。公开记录无帧号/GTid/rawUID，不能将这1259条直接展开成MOT前后帧，也不能把missing/ambiguous当训练负例。540正式收据未引用完整native/history/KF/assignment，只有MOT/frame_counts/聚合audit及部分native SHA；完整内部状态记not_retained。

## 旧原RS历史暴露：实际写入、读取与潜在资格分层

只用原6RS train单元、seed20261024，逐单元固定首2条既有switch，全部12条prior_unknown=true。它们不是第一次真实错误证明，也不是新mask轨迹。12条wrong_uid均有actual生命周期写入证据；未来共有36次stage读取含该UID，14次stage具有旁观重算的潜在评分资格，涉及6个轨迹事件上下文。不能把14次资格当MLP实际调用，不能把重复上下文当独立比赛。

| 来源 | fold | 错误帧 | 历史含UID帧数 | 未来stage读取 | 潜在资格stage | 连续退出offset | 断链 |
|---|---|---:|---:|---:|---:|---:|---|
| SNMOT-060 | game6 | 17 | 3 | 3 | 0 | 3 | False |
| SNMOT-060 | game6 | 20 | 3 | 3 | 0 | 3 | False |
| SNMOT-097 | game9 | 20 | 1 | 2 | 0 | null | True |
| SNMOT-097 | game9 | 36 | 3 | 3 | 3 | 3 | False |
| SNMOT-151 | game4 | 225 | 3 | 3 | 3 | 3 | False |
| SNMOT-151 | game4 | 324 | 3 | 3 | 1 | 3 | False |
| SNMOT-151 | game6 | 225 | 3 | 3 | 3 | 3 | False |
| SNMOT-151 | game6 | 324 | 3 | 4 | 1 | 3 | False |
| SNMOT-060 | game9 | 17 | 3 | 3 | 0 | 3 | False |
| SNMOT-060 | game9 | 20 | 3 | 3 | 0 | 3 | False |
| SNMOT-097 | game4 | 20 | 3 | 3 | 0 | 3 | False |
| SNMOT-097 | game4 | 36 | 3 | 3 | 3 | 3 | False |

11个上下文能在错误帧后offset=3处首次连续确认history不含该UID，另1个因状态歧义断链，退出offset为null；不能把之后观察到absence补成确定连续退出。被挤出只限history，不代表Kalman影响消失或身份恢复。235原事件及排除字段完整保留，旧eligible0/四分支0/45区间null不变，没有执行修复oracle。

## 根据证据安排下一步：先补索引，后决定观测，不加训

1. **下一协议先做后验事件索引投影，保持零更新/零前向。** 将原3690事件的UID与sequence/两端帧号/身份标识形成单独去坐标索引，仅供离线后验诊断，不输入tracker或训练。原完整registry含GT坐标，这会扩展本轮明确未读的文件白名单，必须单独冻结来源与隔离规则；本轮未执行。不能从SHA猜帧或重登记事件，也不开放116/187/test。

2. **固定案例核对已有输出。** 索引齐备后仅按主比较mask_RS对原strongmotion_RS的12来源×四种恢复转移×每类2例，最多96槽；每源固定seed20261024，原三场用其heldout fold、其他来源固定game4，按event_uid排序且缺类不补。aligned-BCE_RS仅作为相同案例的第三方法，不从其他两族再抽96槽。对起止端点各前后5帧的已有MOT作三方法对照，上限96×2×11×3=6336方法帧引用，仍无新追踪/模型/TrackEval。保留改善和稳定控制；UID排序不叫时间首事件，四类定额案例也不是总体频率估计。这里仅拟定预算，实际清单与协议待另冻。

3. **缺内部证据再提出被动观测，而不是直接新训练。** 需要实际MLP调用点的输入UID、候选gate、native成本/assignment及history写入/移除和raw标签子状态。原RS已有train日志优先引用；如需比较两新模型，可另签两方法×6train单元×固定前300帧、最多3600逻辑推进的候选上界，原三来源最多900唯一源帧，不能叫新独立数据或12场泛化。必须先过plain/observer输出及ID逐值一致、cold/ABA/spawn准入，准入预算另列且未执行；不能从缺snapshot的中间帧直接恢复状态。进一步观测对象和实际清单需由前两步缺口决定，不自动补跑。

下一因素需等待可信标签子类型与实际自由评分/历史证据，当前不选择过滤unknown整窗、改CE/null、调整门槛、改history/Kalman或Pose伪标签。保留原strongmotion_RS和所有负结果；Pose连续监督另立协议，预测轨迹ID不充人工GT。

## 实际执行、失败与完整证据

阶段一纯检查为windows7/history14/gap5/driver3；a01启动在CIM误将venv同脚本父stub当第二producer，在创建输出/数据任务前退出，数据读取0。原d941 bundle/4ee3协议/日志与failed保留；只修精确同脚本启动父链识别，driver5检查通过，另签a02协议09ccd3cf127ad89ca76918b14f987cac1a2a58c4dd241b8aee645e1cc8a36e25、四文件f0c32a494ca3a08ad23558b0276cb6671c1816d4d7f35f11398a88ea164c65b8及control_a02输出，科学输入/规则/上界不改、无成功数据任务重放。

独立核查器12项纯fixture过；首次夹具遗漏window_uid已定位并保留小failed收据，只补合成fixture，真实核查前未读数据。真实核查安装单文件34f466c3f84f714a6809b10d4a84111ec93176ee054030b8ddac5319744208cb/source61330135，独立重新核对全部新整数结果及940旧前缀/372目标帧，未导入producer、模型或solver，也未重算旧90CI/旧oracle/训练预算。

producer端到端墙钟22.999462秒，windows/gap并行最多2只读CPU worker、history流式顺序；数值线程1、RAM8589934592/commit6442450944/每在飞3221225472字节预留。不外推旧实验加速。

研究输出：`D:\projects\FutsalMOT_Research\pose\record_reuse_diagnosis_a01`。
- 完成根：`dfd837dad25df8ef7edd2221dfe7ee4db5d4a8ae7936b8aaeb817d7502f5e391`。
- 独立终验：`e317b171765033acd56356dc75b33454decad0f737f3ebffe32358bb03cec99e`。
- producer报告：`d83d87010f611fa20c6edbdd829e66e888da861e0f6838d5153eeadaa0adbad3`。
- `window_summary.json`：`a12e3c76ed9ac7ddab18e9378f8eb2a76fd90d3f2101ce69f0ea0f570ee1ce63`。
- `window_records.jsonl`：`5efaee12bbea0c1cb6e1d00aaf3ddbe6410a30ab2baa33101351006fc28bff12`。
- `window_cases.json`：`5630ec254daf7a0c3557904c1b4bdd8a511cce62491c7943952d37f32c42dad5`。
- `gap_summary.json`：`fea3ca9f06beec368dbd4b6d4a6a449ed24b2290e9ebb3b682efaa792c2822ea`。
- `gap_pairs.jsonl`：`3a620059e1010f6f602c0df8d10c7eb12a9ee8d77072e6b8f6b9cdeb3838a59e`。
- `history.json`：`2fce8b1e7fca99a58ab17b86970594d4f7144139ee381157982452e49f671170`。
