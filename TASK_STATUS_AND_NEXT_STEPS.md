# 当前任务与下一步

更新：2026-10-28。历史过程见Git及对应运行收据；本页不保留过期PID流水。

## 当前：制定训练/自由状态资格与弱标签的有界诊断方案

原未校准strongmotion_RS继续为主参照。R集合监督完整结果已闭合且未建立整体提升；新方案见Docs/research/STATE_LABEL_ALIGNMENT_DIAGNOSIS_A01.md。仅规划复用3000R窗/42465pair、九曝光表及180118既有机会账本，新增优化/模型前向/追踪/GT坐标/TrackEval均0。重点补训练监督与推理资格的逐候选交叉、无known正例与unknown/可达性/身份代理的交叉，不重复旧诊断或当坏数据删窗。完整诊断及独立核查后按事前次序最多选一个因素，证据不足则不训练；尚未选定执行因素，未实际新扫描。测试116/187/test封存，每阶段即时历史/精确push。

## 本轮诊断已闭合：训练候选与自由状态差异

独立终验于2026-10-28 19:21完成且实际退出，12观察/12后验、9000逻辑帧/2250唯一源帧、27000stage/180118stage-row及3000自然池窗口全部核验。优化更新0、图像推理0，无新AssA/HOTA/IDF1。完整结果见[诊断结果](Docs/research/TRAIN_FREE_STATE_GAP_A02_RESULTS.md)（根目录入口使用Docs/research/路径）。完成根DResearch/pose/state_gap_diagnosis_a01/complete_root_a02.json SHA ad2eed7e78f5551e38c8db0c29a903348af2b5c6765e89b30c4f18f139a9804b。

原自然池每fold1000、历史3条、query gap1/5/10/20/30各200，候选数中位3、gap中位10帧。自由R六任务90226 stage-row、候选中位15、gap中位1，history1/2/3为14083/7768/68375；RS相应89892行、14864/7876/67152。全stage与自然池不是同分母，不能直接称全部实际SGD/learned评分分布；不据此认定因果主瓶颈。

235切换记录中231此前unknown；另外4条实为同一SNMOT097第245帧在game4/game9×R/RS的重复观测，均仅2条历史、正确raw非唯一、learned_active=false，不能当4独立错误或学习分支错误。eligible0、四分支/前缀推进0，45配对区间全部null，不写效果0或history/KF无影响。旧中断及partial、a04恢复、全部负项原样保留。

下一项仅选择R训练窗口来源对齐作为待验证假设。先审计R-only teacher高分learned-active且可信3条同身份历史的窗口、固定排序/去重，各fold允许两源各500唯一共1000为目标；全高分stage候选保留，不冒称精确评分掩码，unknown仍None，不要求每窗正例，池不足不填重复。R/RS共R源，RS原v10balanced1000S保持。新18臂三fold三seed20261024/25/26×R/RS：194→64→32→1 FP32强motion、原normalizer/init、AdamW学习率0.001/weight_decay0.0001、1000更新，每步3R总3000R，RS另1S总1000S，mean3R+meanS/3、last1000非EMA无best。来源改变同时改变候选/gap等，窗口数公平不等pair/标签/FLOPs公平；先冻结池/schema/完整记录、CPU及实际CUDA一步和首完整1000门禁。目前仅候选实现，未生成正式新池、未训练。测试116/187/test持续封存。

历史恢复过程：

2026-10-28异常更正：旧控制器与worker已实际退出，原state停在10:29:47，完成5项750帧观察及2项后验，不能再按文字状态称运行中。最后可用RAM139603968字节、commit余量282320896字节；未取得确证终止原因或退出码，不断言Windows主动终止。旧源码、state、成功与partial原样保留；异常收据为DResearch/pose/state_gap_diagnosis_a01/interruption_a01/receipt.json（SHA be17115bb93061888ae7790e4b07864a282b017f0c1f249eab07c3d12fea0f8e）。

已定位整750帧日志read_rows物化、后验深拷贝及全部候选行同时驻留，以及门禁未预留在飞峰值的风险。流式候选保留全部原字段、行、事件和负结果；60项针对合同通过，含旧实现字段一致、流式释放、恢复拒绝partial及独立终验。一次误用无Torch的P1通配符检查导致6项旧Torch夹具导入失败，未安装Torch或改旧算法；随后正确限定变更模块的60项检查全部通过。

恢复尚未执行：下一步独立安装新最小bundle并进行完整750帧实际后验内存准入，产物直接继承，不重做已成功后验。准入通过后另签a02协议，明确继承旧5观察/2后验，补7观察及缺失后验；2track+1posthoc、每在飞任务预留3221225472字节，物理RAM保留8589934592字节、commit保留6442450944字节。逻辑首遍仍9000帧（3750继承+5250新成功）；旧3partial真实推进未知另列，不能写重试0。原数值、来源和事件/统计边界保持；独立终验也改逐帧核查，旧eceddf版本不执行。当前新增SGD0、图像推理0、未选择单因素、无新AssA成绩，测试封存。

- 用户已授权[本轮绝对参数与边界](Docs/research/TRAIN_FREE_STATE_GAP_A01.md)。原强motion R/RS、seed20261024、三fold各两允许train片段共12任务/9000逻辑帧；模型优化更新0、检测/Pose图像预测0。先完成GT隔离的全三stage/空分配/生命周期日志及真实原输出、常驻、快照准入，再执行完整诊断；不提前选择训练因素。
- 对最多20/fold、60总的严格首次可观测可信切换，固定后30帧四分支局部oracle。只修history写入、Kalman mean/cov或两者，GT框不入正常追踪；所有未知/排除/负结果保留，事件不是独立比赛。训练池只比较自然teacher-forced结构，不冒称完整增广SGD分布。
- 44项CPU合同及真实两模型/96唯一帧的原输出/旁观/ABA/多spawn/纯状态续跑准入已完成，全部准入worker实际退出。a01入口来源失败0帧，a02收据字段冲突192帧保留，a03显式继承原96帧并新增1200，诊断合计1392帧、SGD0。固定四任务2+1耗时47.9498472秒、4+2耗时39.3693776秒，正式采用4track+2posthoc；不外推整轮速度。
- 历史10:12:58启动已中断，以下是原准入启动记录，不能代表当前进程活跃。配置SHA `61b135aa0ecd82b47a988d0b4a682cfeebcb0925c77f257a9a70c80ce063f05a`，四文件bundle `072551a74d0fc44e908163bb800d1c314dfd20ecd2072c869e74d38b2fed15ec`不热改。完整诊断未闭合、没有新成绩或因素选择。实际进度`pose/state_gap_diagnosis_a01/control_a01/driver_state.json`，正常活动不重启。

- 新增[从第一次训练到现在的历史总览](Docs/research/TRAINING_HISTORY.md)：从bbox B1–B5、Pose P2–P7、关联P8–P10、绿色A/B、额外真实C、有界速度T至18标量校准，逐轮解释对象/目的/数据split、绝对参数与成绩、负结果/中断/缺失。R3额外扩框探索与旧参考单列，B5不完整不伪称完成；约72/40/30的AssA来自不同面板，不能横比。按用户最新要求，每轮结束后由主智能体自动补充历史，与阶段提交推送及汇报一并完成；失败和中断即时登记。已取消每日09:00定时维护，无需用户逐轮提醒。未来实验参数明确数值，结果先列绝对成绩、再保留配对差值/CI，测试持续封存。本文档维护没有新增模型训练或评价。

## 最新闭合：训练R截距单因素

- 按[固定方案](Docs/research/TRAINR_INTERCEPT_CALIBRATION_A01.md)及[完整结果](Docs/research/TRAINR_INTERCEPT_CALIBRATION_A01_RESULTS.md)，一次有界错误分解后只验证原强motion R/RS十八模型的一维logit偏置。63项CPU合同、六真实模型/384诊断窗口次、十八拟合及全记录独立核查、96源帧/528诊断消费冷启动/常驻/双spawn准入和180正式自由追踪均已真实完成，全部父子/launcher退出。原权重、特征、候选、原stage批次、门槛与历史不改，SGD0。
- 新增18000clean R模型窗口次/67560all pair/52164known/15396unknown为额外有标签标量拟合预算，不称零监督、严格同总曝光或新独立样本。完整逐窗logit/UID/未知/二分迭代/FP32/原模型引用/RNG与stdout/stderr保留；原180基线只读引用，不重跑，原感知/媒体/渲染0。
- 当前证据未建立整体追踪提升：七场R校准−原R AssA−0.1329点[−0.3900,+0.1242]（2正5负），RS校准−原RS+0.0525[−0.2650,+0.3700]（4正3负）；HOTA−0.0850/+0.0337、IDF1−0.1196/+0.1032，主区间同跨0。原三场RS−0.5797且三场均值全负；旧两场R/RS−0.0022/+0.1101且区间宽。全部下降保留，不因CI含0称无效/等效。
- 七场校准差值交互+0.1854，主t区间[−0.0183,+0.3891]，bootstrap[+0.0371,+0.3393]均披露，不挑bootstrap宣称合成作用；原三场交互为负。当前强motion试验也不是Pose增益。原3690gap分母保持，270指标/270gap配对、36比赛汇总、45指标/9gap描述全部独立核查，含360新旧原结果/全部seed/fold/null/留一。
- 完成根SHA `b80ce600397b3b61e7c17edc9bc6d0a27bda75204650bd43bf4853d5c5f05d5c`；正式配置SHA `e1fb9d52a0af24755cf87bbd6770907450888714849688a48fa4a03e2732819a`、五文件bundle `bdebba859b76a003e8fcf344704a15a4e82c66862bae6e9fa88b62d18f94e3c0`不改。2track+1metric控制至完整分析952.9619秒，采样RSS峰1.4265GiB、最低可用RAM16.7238GiB；不含准备/拟合/准入/终验，不当新串行提速。状态为`complete180_trainR_intercept_tracking_and_paired_analysis`，独立终验`complete180_trainR_intercept_sources360_results270_pairs45_metric9_gap_intervals_and_exit_verified`，无需重跑。
- 维持原主参照，校准版完整归档，不继续搜β或挑seed/符号。下一研究候选优先澄清训练候选与自由状态差异、历史传播条件，需另立协议，不由本轮直接推导应扩大模型或大批补采。原3/旧2/七场全为已观察开发，确认性泛化须另锁新train/val；测试116/187及test包始终封存，UE保持关闭。本轮闭合不冒称整研究主线完成。

## 最新闭合：一次有边界的错误条件分解

- 按[事前范围](Docs/research/BOUNDED_ERROR_DECOMPOSITION_A01.md)与[完整结果](Docs/research/BOUNDED_ERROR_DECOMPOSITION_A01_RESULTS.md)，只复用已有27份平衡RS内部trace，24863个stage、320752行全部保留；新七场缺63份内部trace明确unknown，不补跑。18CPU合同、真实9份原FP32分配逐值准入、两个后验worker及8合同/独立终验均通过，真实进程退出；新模型评分/SGD/自由追踪/TrackEval/媒体均0，测试封存。
- 可判断且当前正确身份仍在场的12506行中，289行无单边可接受正确候选，明确已知错误候选代价更低仅4行；门外63、全局竞争或未匹配72、未知41也完整保留。所有条件及112个比赛等权描述区间不是因果归因或总体错误率。历史unknown131447行、连贯历史相对首次可信锚漂移19828行不等于IDSW，不能据此直接改历史保护。
- 完成根SHA `1bcab93ec9f498a67bb6d00333e069e7af26bd9ec5757654f62c10d528c82382`，独立终验SHA `f54cf77280da82b5beef780be1a06093440eb19e5fb69219d862bdee697c14f1`。两个worker控制至全汇总28.7038秒，采样RSS峰0.4082GiB，不含准备/终验，不当新串行提速。
- 唯一后续因素为训练R上的一维logit截距校准，现已完成十八拟合并进入独立180自由追踪，实际进度见本页开头。额外18000校准窗口监督计算另列；不以本分解认定总体主瓶颈，不同时改模型容量/外观/历史。

## 已闭合：OC-SORT门槛0.6→0.25单因素

- 用户明确授权后，按[固定协议](Docs/research/OCSORT_THRESHOLD025_A01.md)完成17CPU合同、真实96帧literal/ABA/双spawn及严格FP32边界/旧0.6小夹具准入，再唯一新增12片段8165帧自由追踪/TrackEval和自动配对，7合同/独立终验全部通过，真实父子/launcher退出。只有det_thresh改0.25；原core字节、byteFalse、全部其余参数/输入/输出/评价和3690gap分母保持，旧0.6十二场未重跑，SGD/感知/媒体0，测试封存。
- [完整结果](Docs/research/OCSORT_THRESHOLD025_A01_RESULTS.md)：七场新025−旧06 AssA−2.4149点[−9.4286,+4.5988]（2正5负），HOTA+7.4114[+1.5670,+13.2558]，DetA+24.6309[+19.8829,+29.3790]，MOTA+28.5998[+23.0693,+34.1303]。原三场/旧两场AssA均差+1.2984/−3.0315且区间宽，不能概括完全无收益或稳定关联提升。全部48指标/48gap比赛配对、60指标区间和12gap描述、bootstrap/逐场留一、负结果完整保留。
- 七场025−强motion AssA−6.3062[−10.8828,−1.7297]，HOTA−3.8140[−7.1821,−0.4458]，DetA却反高+2.4885[+2.1259,+2.8511]。低阈值明显改善覆盖但不足解释全部身份差距；仍不是纯关联器/Pose/合成因果或SOTA证明。所有区间未多比较校正，仅描述，12片段均已观察开发。
- 正式配置`pose/ocsort_threshold025_a01/frozen_a01/config.json` SHA `6bdaa864f1fa565449f560312439551d2cc361f06f87a9213610e6db4ec3966b`；四文件bundle `0f29fe8698fa0545cfe6b42332894a834b20c405b4fa8450f26e47560fbe0b03`。独立终验SHA `c30596b9211c803d96d6650032a3cfb3a42a3986759ae42745b300129a610857`。2track各6+1metric12正常exit0，控制至分析22.5166秒、RSS采样峰0.7507GiB、最低可用RAM12.3095GiB；不含冻结/准入/终验，不当视频FPS或新串行提速。
- 该单因素阶段已完成，不再扫门槛或自动改生命周期/加训/扩数据。下一候选围绕剩余身份分配与历史更新的具体错误证据，或独立成熟外观参考；确认泛化另锁新train/val身份，最终测试继续封存。

## 最新闭合：十二片段零更新分数与输出政策账本

- 按用户“按规划进行下一步”完成[固定口径](Docs/research/TRACKING_POLICY_LEDGER_A01.md)和[完整结果](Docs/research/TRACKING_POLICY_LEDGER_A01_RESULTS.md)。19CPU合同/真实NumPy FP32边界、两个后验worker实际12源114条MOT全量分析及8合同/独立终验通过，真实进程退出。8165唯一源帧/149245 raw/113020 GT机会、76315逻辑单元帧、936212原发出行和15924可观测ID片段完整留存；新SGD/模型/追踪/TrackEval/媒体均0，测试封存。
- 七场GT人物帧的任一`>0.6`几何候选覆盖比赛均值52.1307%，`>0.25`为88.4358%，新增36.3051点；原三场/旧两场新增26.8833/24.1705点。这个候选机会不是DetA或新追踪收益。新增分数段仍约44%–46%无候选或歧义，不将其全当有用，也不将无候选直接称绝对误检。
- 七场OC实际每帧发出6.1275框，强motion训练单元先场内均值后比赛均值13.0318；输出覆盖差异明确，但MOT不能还原出生/确认/lost/抑制原因，全部unknown。原ByteTracker当前源码只有本次快照，历史逐文件SHA缺失不补造。不能把之前整体领先当孤立关联、Pose或合成优势。
- 配置`pose/tracking_policy_ledger_a01/frozen_a01/config.json` SHA `14dc1c193cd0149ff821530e29deacc043be048c4d403a3b516ef3fc7ce5ab97`，三文件bundle `70a399c65ff8cf7f2ef7090a0739ab161ff5b59b338c419f54e0c6c1238645f7`；独立终验SHA `aaa5c2bd2161dbb9c0e2ec5e2c8dcf4ac9ff44e984035c2c2169cf88eff45226`。两个worker各6源/join/exit0，53.719秒仅控制器至全汇总、不含准备/终验；RSS采样峰0.1959GiB，不是新串行提速证明。
- 下一优先单因素候选是OC `det_thresh0.6→0.25`，其余含byteFalse完全不变；先另冻协议和实际准入，再一次同12已观察开发片段自由追踪/配对区间。尚未执行该候选，不搜索阈值，不马上扩数据或加训；独立确认另锁来源身份，最终测试继续封存。

## 最新闭合：官方OC-SORT同缓存12开发片段

- 按用户新授权完成[版本/参数/输入协议](Docs/research/OCSORT_CACHED12_A01.md)及[全部结果](Docs/research/OCSORT_CACHED12_A01_RESULTS.md)。官方commit固定`8462e7e729a93ccd3bd995c0a79a890336cb3a0b`，三个算法文件原字节；默认det_thresh0.6/byteFalse，输入float32 N5/scale1，原Kalman64位/自然ID/全部core输出，MOTscore常数1。不是2023原字节或官方完整demo成绩。
- 29CPU合同、真实96帧literal/常驻ABA/双spawn及正常退出通过；随后2track+1metric只正式执行12片段一次，共8165帧。两场实际计数门禁后继续10场，3690原gap分母、ID0、DO_PREPROC=False和全部未匹配预测保留。12评价/192历史参照/36配对、45指标区间及9gap描述独立终验通过，真实父子进程退出，SGD/新感知/媒体0，测试封存。
- OC−强motion的AssA：原三场−5.9277点[−7.7113,−4.1442]，旧两场−7.0567[−67.1174,+53.0039]，七场−3.8914[−11.8842,+4.1015]；七场OC有2场更好、5场更差，全部保留。仅说明该固定配置下样本均值，不能称稳定超过OC-SORT/SOTA或Pose/合成因果。七场OC DetA另低22.1424点，内部阈值/确认/输出政策不同，不能当孤立关联模块比较。
- 正式控制器记录24.3629秒（不含前置准备/准入/终验及退出尾部），采样进程树RSS峰0.7357GiB、最低可用RAM11.9787GiB；没有新串行提速证明。a01只读依赖路径误拒及a02缺threadpoolctl的真实失败均保留，独立a03补最小依赖/只读边界，算法参数不变，正式成功重放0。
- 完成根`pose/ocsort_cached12_a01/complete_root_a01.json` SHA `13f185e6260c7ecc2456af6e98a02684076be7b388d932754516ea96bc4d3796`；实际正式配置`frozen_a03/config.json` SHA `832b41501e7eeddfe27cabb4b8ad5fa873a8ab03ca9e14bb78005486de2cbd79`。下一建议先做零更新score分层/阈值保留和轨迹输出差异账本，再决定单因素；不据12场搜索阈值或自动训练、扩数据。

## 已闭合：18项零更新诊断与常驻吞吐

- 用户授权继续后，已完成[常驻worker真实性能准入](Docs/operations/ASSOCIATION_WORKER_ADMISSION_A01_RESULTS.md)：六完整任务ABBA，串行104.2444秒→2track+1metric的47.5210秒，实测2.19365倍/耗时−54.4139%。27次完整追踪与评价的原ID/MOT/完整audit/全部指标/gap均与原结果一致，32个worker正常退出，最低可用RAM14.0258GiB。该小样本不外推为训练或513全轮倍数；新SGD/感知推理0，不重跑性能阶段。
- [120样本盲人工输入](Docs/research/POSE_MANUAL_QUALITY_INPUTS_A01.md)已实际生成及pending验收，随后按用户弃用意向移出必做流程，不再等待人员。120人/2040点仍为0人工、0复核，不报准确率；原索引/空模板/工具归档保留，不删图或记录。Codex内置浏览器拒绝file://自动预览，页面未完成浏览器视觉验收，限制不绕过。
- [18项新T接口完整结果](Docs/research/POSE_DECISION_INTERFACE_A02_RESULTS.md)已闭合：24CPU合同、实际6模型/9trace/18状态及score2数值准入、18完整评分、真实父子/launcher退出和独立终验通过。9原trace的8281事件、两模型16562评分事件/214334行、完整16格转移及全部负结果保留；新增优化/自由追踪/感知推理0。a01来源验证读取endpoint_GT却误报未读的失败保留，独立a02仅改声明/合同、16数值AST未变，不重放正式任务。配置SHA `9797db9d6f527c35ed508e003bd5d7e503dc8cd13f99b2274b91a059137d70ff`，完成根`pose/pose_velocity_decision_a01/complete_root_a02.json` SHA `d684f0b62316173833314443933e4afd47246f259de29b8250b4910dfadc2f1a`。
- T_RS原q相对own-base的可信正确分配修复/破坏均0/0；q1原三场0/13、旧两场跨fold1/6，不支持直接放宽quality gate或搜系数。这只覆盖首seed/非空stage/固定历史，不是新AssA或关键点准确率。下一项优先准备同一批开发比赛和raw检测缓存下的成熟追踪器参考，冻结版本/参数与适用数值吞吐准入后再执行；尚未开展该基线或新训练，测试继续封存。
- 整体成绩口径：系统相对七场PT bbox参考24.1163的AssA已有提升（强motion_RS30.2129），但这包含真实训练与整个关联器，不能归于Pose或合成。最新编码相对原Pose：原三场31.7289→31.3831、旧两场40.0743→40.1277、七场30.2046→30.1547，没有整体继续上升；七场HOTA/IDF1也略降。测试继续封存。

## 已闭合：七比赛真实资源对照

- [后续方案](Docs/research/POSE_DIAGNOSIS_AND_REAL_DATA_SUBSTITUTION_PLAN.md)已授权实施。162项机制与108项幅度CPU探针/机会审查及退出已完成，优化更新0，不重跑。关闭/打乱Pose影响很小，调大残差外部仅微升且原heldout下降；不能由此证明训练期Pose作用或必须加外部算法。
- [额外真实输入阶段](Docs/research/EXTRA_REAL_INPUTS_A03.md)已全部闭合：061/098/154三段2250帧获取/CRC/首次解码、共享固定PT检测/Pose、三fold各1000唯一额外R窗口、九张未来曝光计划及独立核验/进程退出完成。旧两次网络失败原样保留，成功1500帧未重复下载，旧R/S/PT未重推，不重启获取/预测/建池。
- 每fold排除heldout，两允许比赛各500；与基础R的窗口/观测/源帧引用交集均0，比赛时间不重叠。三fold条目共3000，但全局仅1500唯一窗口/2007源帧引用，不冒充独立样本或新比赛。三段仍属于原game4/6/9，标注工时未测。
- 额外R输入及C十八臂训练现已全部完成，真实训练/控制器/launcher已退出。基础3000R表、标准化和质量尺度不变；C另立4000R资源问题，不能混入同3000R的Pose主比较。额外R输入根为D研究根`pose/pose_mechanism_a01/extra_R_inputs_a01/inputs_stage_complete_root_a03.json`，原缓存、窗口和论文输入CSV保留。UE/GPU与本轮CPU追踪均已结束，无活动实验任务。
- 用户2026-10-27选择只报告配对差值和置信区间，不设非劣效/等效界限，不再为界限重复确认。[七比赛方案](Docs/research/REAL_SUPERVISION_SUBSTITUTION_A01.md)已固定7个未评估足球比赛、4790帧和比赛等权95%t区间/bootstrap敏感度，旧五场只作已观察开发参照，不当新盲测。
- 七场输入a02已完整4790帧/GT/seqinfo/首次解码与实际退出，`validation_inputs_complete_root_a02.json` SHA `c3de03b1f926095b289044441329b78676045b136016647c29af86266e485046`。原a01失败保留，a02继承437成功图只补4353，完整manifest SHA `a948c541523dd886df86acab3f3e2270a812df1bec35529c6ff62fffc47b966b`；不重下、重哈或重解码成功图。测试封存。
- C终态`complete18_C_training_wait_independent_audit_tracking`、18/18且active为空，独立`C_postrun_audit_a01/actual_budget.json`已真实核验18000更新/54000基础R/18000额外R/S0、378份完整检查点读回、step0初始化/九组两方法顺序/实际pair/LR/梯度及进程退出。R all/known为278136/207504，4诊断更新另计，重放0。协议SHA `e57a5a40d53f0d6b20ed0d790703a24abbb602c14679d135e1a198d5f568733c`及八文件bundle不改、不重启训练。
- 新七场PT检测/cropPose已全部4790帧完整并实际GPU/launcher退出，`prediction_complete_root_a01.json` SHA `76aa4417f32eec8d03f852d391ec36e87ecf1716b0ba9ad4bb5f633f4a63de81`。90490 raw/63306几何通过/27184 bbox-only仅规则计数；单次stream独立核验缓存/时序/计数，不重推或重哈媒体。原配置SHA `89a789b668da0fbd8d69c00b21487110bc115c9734e2a824ce5cfed0668d0119`及五文件bundle保留，不重启预测。
- 追踪结果前已实际固定2337可信检测断档proxy（非物理遮挡），`evaluation_inputs_a01/gap_registry.json` SHA `c05fc1f0ac2a39685afec25224f862d17b7103197994d09da002fc17a7cedf04`。无GT坐标的公开receipt供tracker读，完整endpoint_GT仅评价读，GT ID0保留、DO_PREPROC=False，全分母/零分母null。
- 392项自由追踪/TrackEval/自动区间分析已全部结束，state为`complete392_tracking_and_paired_intervals`、active为空，真实控制器/子进程/launcher退出。协议SHA `fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78`及五文件bundle不改、不重启。独立终验器已实际核对392来源/MOT/GT计数、1323配对单元及105个t/bootstrap/逐场留一区间，终态`complete392_sources_all_results_1323_pairs_105_intervals_and_exit_verified`；没有重训、重推缓存、重算TrackEval或重复C预算。
- [七比赛完整结果](Docs/research/REAL_SUPERVISION_SUBSTITUTION_A01_RESULTS.md)：主motion的AssA B−A为+0.2781点，95%CI [−0.3068,+0.8629]；C−A为+0.2756 [−0.5796,+1.1308]；B−C为+0.0024 [−0.5608,+0.5657]。次gated的B−C为−0.0520 [−0.3855,+0.2814]。B组gated−motion为−0.0082 [−0.1881,+0.1716]；不据区间跨0称等效、可靠Pose增量或节省人工成本。
- 完成根`pose/real_substitution_a01/complete_root_a01.json` SHA `1fb5af28657d4c849a15b09231f8f03dd8153629e7fa0349e4f524116f321478`，全部392原指标/1323配对CSV、105区间/敏感度、18,000步C记录和378完整检查点保留。该阶段已完成，Pose机制和跨分布效用仍未解决；不自动扩大渲染/加训，测试继续封存。下一步基于完整报告讨论单因素机制或独立数据验证，不由局部正值选择方案。

## 最新闭合：有界27臂与513项追踪完成，未证实强motion之外增量

- 用户最新要求后续训练/推理充分使用14600KF/4070Ti SUPER/32GB，已更新[性能准入规则](Docs/operations/TRAINING_PERFORMANCE.md)。本轮513已闭合且冻结字节不变；下一新执行先做独立track/metric常驻池2+1→按实际内存评估4+2、有界模型/输入缓存及训练传输/同步准入，验证冷启动与A→B→A完整输出和同工作量总耗时。尚未运行新性能基准或承诺加速倍数，不重跑本轮、不恢复取消的渲染/导出优化。

- 有界变化27臂/27000更新/81000R/18000S、567完整检查点、原始27000步归档均已实际验收，重放0。513追踪/TrackEval/自动分析已于16:14:59+08完整结束并实际退出，450新T+63同容量七场缺失参考，新增SGD0。独立终验a02核全513来源、270参考、720指标和720断档配对、120指标区间/另24断档描述通过；根`pose/pose_velocity_learning_a01/complete_root_a01.json` SHA `6b864d4a136e55744f2da8b3da73ae4dff8cbe6a1aa9c7acc1f6606d847001e6`。a01预算缓存关闭假设及a01终验旧五场字段假设的真实失败均保留，独立修复未改训练/追踪/原收据；不重训、重推或重算评价。
- [有界变化完整结果](Docs/research/POSE_BOUNDED_VELOCITY_LEARNING_A01_RESULTS.md)：七场AssA T_RS−强motion为−0.0582点[−0.2245,+0.1080]，对原gated−0.0500[−0.2731,+0.1731]，自身开启−关闭+0.0106[−0.0524,+0.0736]。额外S+0.2643[−0.2472,+0.7758]及真实形状−打乱+0.1164[−0.0522,+0.2851]仍不精确，不能替代主要负结果或证明Pose训练净收益。原三场/旧两场/七场分别报告，全部seed/fold/负结果留存，不称等效或Pose普遍无用。
- 用户已授权实施[Pose利用验证方案](Docs/research/POSE_UTILIZATION_NEXT_A01.md)。[零更新信息链](Docs/research/POSE_INFORMATION_CHAIN_A01_RESULTS.md)完整54单元/641785行、79465状态行签名及独立终验/进程退出已完成，0优化、无新自由追踪/检测/Pose推理。全部未知与负结果保存，120个质量复核索引已固定但人工关键点真值/复核仍未完成，不报告PCK或OKS。
- 近motion且实际介入的外部条件行中，平衡池均值正排65/127、线性外推54/127；困难池65/139、53/139，不能当独立事件或AssA。原外推候选实际三fold1000R/11260pair输入合同已通过，只改34通道并保持原gate；若直接重算gate会连带改变8208pair，因此显式分离。暂不启动原27–36臂，转向有界历史变化编码CPU合同；没有新训练或渲染。
- a01空评分读取失败、a02影子全批/实际enabled批FP32 sigmoid差异失败均原样保留，完成0单元；a03使用原实际代价为权威，49744事件的影子motion分配与实际分配全部一致，代价最大微差1.788e−7不冒充逐值exact。初版独立终验器自匹配问题有单独失败记录和完整文件名回归，未重跑已完成54实验。完成根`pose/pose_information_a01/complete_root_a03.json` SHA `b118b555c232fbb2c763dbf137e27c319a89a4b0e0bec357622947d0368ad90b`。
- [有界变化编码CPU合同](Docs/research/POSE_BOUNDED_VELOCITY_CPU_A01.md)、实际CUDA数值与完整记录准入、首千步21检查点、27臂训练及513追踪均已依序闭合。主智能体把握协议/实际进程，子智能体独立实现与审查，全部记录和失败保留；不把合同或记录通过称收益。
- 下一科学步骤先补固定120样本人工关键点质量证据，并复用既有信息链，仅针对尚未回答的输入误差或新T到决策接口机会设计一个有限干预；不自动再开27臂、加轮数或扩大渲染。有质量短缺才改输入/补数据，有可信线索但未利用才验证一个门控/关联因素。新确认比赛先锁定train/val身份，最终测试继续封存。
- 若证据指向真实Pose误差、raw/候选缺失或困难事件分布不足，再针对具体短缺补数据。七场现在是已观察开发范围；新确认比赛先核验并锁定train/val身份，不能用116/187或test补数。资源等效和人工成本仍不作通过判定。

## v10已完成与当前状态

- 用户已授权[独立运动/困难事件v10](Docs/research/MULTISEED_HARD_ASSOCIATION_V10.md)，以强motion_RS为主要参照，全部同3000R窗口和已有预取，最终测试封存。此前“仅方案不自动执行”已由新授权覆盖，但旧批仍不重启。
- v10完整12单位已实际全部结束并发布`G:/FutsalMOT_Dataset/v4_pose17_multiseed_green_a01`：3600RGB/mask、36000人物Pose、900源时间样本，3600EXR共144520931344字节已退休；最后UE本次15:59:36正常退出，采集控制器与全部UE已不存在。root dataset SHA为`1b7386b4275b3101a1a4a4a9e68d360b618b29d72db0dc66873ebdab36a3e251`，与发布complete一致。本完整批world逐值相同/max0，短样7.0251毫米差异的历史及未知根因保留，不升级物理可见性或同步声明。根收据`Saved/AppearancePlanning/multiseed_v10_a01/full_acceptance_root.json`。
- 共享预测18源/5925帧已实际全部完成且进程退出：4800合成帧54875个raw检测，1125验证帧19090个raw检测，几何规则通过数分别26474/14346，不是准确率。权威`shared_inputs_a01/manifest.json`及根收据`Saved/ResearchBuild/v10_prediction_complete_root_a01.json`已闭合；不重复预测，R缓存不改，测试封存。
- 两个S池已实际构建并独立核对：balanced/hard_enriched各1000唯一窗口，四运动seed各250、80格配额相同。自然检测缺失窗口0/26，实例框重叠窗口205/996；已知pair分别2799/3236，不能声称池间等pair或等计算。全部874个合成自然缺失proxy事件保留独立账本，不当物理遮挡。根收据`Saved/ResearchBuild/v10_pools_complete_root_a01.json`。
- 54臂完整记录训练已全部结束、相关进程实际退出，独立核对54000更新/162000R/54000S窗口及1134份模型/优化器/完整RNG检查点全部通过。实际R all/known pair为608040/469476，S为458676/162945；同池三方法及跨池原R顺序/初始化一致，6诊断更新另计，重放0。`postrun_audit_a01/actual_budget.json`为完整预算，原训练协议/源码不再运行或改写。
- 253项CPU自由追踪/评价及自动分析18:05:04已全部结束，真实CIM确认控制器、子进程和UE退出；终态`complete253_tracking_and_analysis`。最终独立核验全部253项MOT/评价来源、50组配对及事前分母通过，`final_verification_a01/receipt.json`为完成链。不再启动本轮训练、追踪或采集。
- [v10完整结果](Docs/research/POSE_V10_RESULTS.md)：两新比赛上gated−强motion_RS AssA为balanced −0.0417点、hard +0.2110点，均未过登记+0.5点联合门槛。困难池2/3 seed及两场均值为正，仍有6/18单元下降；困难池gated绝对分数还低于balanced 0.0639点。不能把相对motion转正说成困难采样令Pose变强。
- 同3000R下gated混合−纯R AssA为+0.2567/+0.1927点，相对PT bbox为+5.9712/+5.9073点，但未证明Pose可靠增量、合成等价真实或物理遮挡恢复。完整54,000步、1,134份完整检查点、全部253项评价与论文CSV/PNG/PDF已保存，全部负结果和最终测试封存边界保留。
- 新比赛扩域仅替换原tracker一条帧域AST守卫，实际sequence/game不改名，其余数值AST相同；原750帧PT bbox/static/learned三个模式逐输出及audit完全一致。6项CPU检查覆盖真实TrackEval合法ID0、未匹配预测保留及汇总Count边界。五场可信断档proxy结果前登记1353事件（旧956、新397），与合成874个“无任何raw框”事件定义不同，不称物理遮挡；所有事件为评价分母。
- 三个新增运动1042 `[152,452)`、1044 `[383,683)`、1131 `[565,865)`的36RGB/mask/360Pose短样已实际完成并根视觉验收，原seed球衣逐帧读回/恢复通过，36EXR共1454751354字节已退休，所有相关进程退出。根验收`Saved/AppearancePlanning/multiseed_v10_a01/short_acceptance_root.json`。1044的R0跨机位关节world最大差7.0251毫米（投影最大1.2334像素），根变换相同、具体成因未证；原值保留，限定逐视角身份研究，不称同步多视角Pose真值。完整12单位沿用串行正常退出/导出/清EXR；终态以`control_full_a01/state.json`为准，目标3600RGB/mask/36000Pose，不把短样通过当整批完成。源轨迹proxy9/5/6不冒称真实图像交叉或物理遮挡。
- 新比赛不能只换原game4/6/9片段。SportsMOT事前固定Dortmund–Schalke450帧及Norwich–Ipswich675帧，实际身份已与旧三场核验；1125帧输入/解码/GT/共享预测及全部评价均已完整结束，ID0保留，无新增R训练曝光。当前两场已成为开发验证，不称最终盲测，最终测试未读。
- 用户要求所有后续训练全过程留存。[记录规范](Docs/operations/TRAINING_RECORDS.md)已真正接入v10逐步loss/Rloss/Sloss、LR、梯度范数、耗时、R/S UID/epoch/all及known pair/曝光链，0/每50/1000完整模型+优化器+Python/NumPy/TorchCPU/CUDA RNG及原stdout/stderr。首正式1000步端到端验收通过，收据`control_a01/first_run_end_to_end_gate.json`；硬崩溃超last不猜步重放。绿色旧18臂的历史缺失字段仍明确缺失，不补造。

## 当前主线结果

- 绿色短样已根验收：8组96RGB/mask、960人物Pose（48主A/B+48颜色检查，6源时间样本），三张总览已实际查看，原seed两队/门将配色及原草地纹理正确。相机和world配对逐值一致、最大差0，检查的中帧mask差0，不冒称全部RGB像素/物理可见性。96EXR共3883119675字节已精确退休，所有短样UE/导出/控制器真实退出。验收为`Saved/AppearancePlanning/green_seeded_kit_a01/short_acceptance_root.json`。
- 完整绿色配对16单位已全部完成并同G卷发布：`G:/FutsalMOT_Dataset/v3_pose17_green_seeded_kit_pair_a01`，4800RGB/mask、48000人物Pose、600源时间样本。4800EXR消费后全部退休，所有采集UE及控制器已退出；最后一次UE日志2026-10-26 11:50:12正常Exiting/closed。单次world与实际相机元数据比较逐值一致、最大差0，不冒称RGB全像素或物理可见性。发布dataset SHA为`fe640d58252cf621106afa819e8952f99cb5bc57269643a5545ecc15c4db96fb`，根收据为`Saved/AppearancePlanning/green_seeded_kit_a01/full_acceptance_root.json`；不重启完整采集或重复发布。
- 新A/B固定框Pose预测已完整结束且进程退出：2400帧，A/B各13199个相同检测、1000窗口/5431观测，非Pose窗口SHA一致；R缓存未变。几何有效检测A6998/B7000只是规则通过数，不是准确率或训练收益。manifest为研究根`pose/green_seeded_kit_pair_a01/predictions_a01/manifest.json`，根收据为`Saved/ResearchBuild/green_prediction_complete_root_a01.json`。
- [绿色球衣18臂完整结果](Docs/research/GREEN_SEEDED_KIT_RESULTS_A01.md)已闭合：18训练/18追踪/分析、实际进程退出及独立预算核对全部通过，18000实际更新/54000R/18000S窗口，9组A/B初始化/UID顺序及全部/已知pair一致。B−纯R AssA/HOTA/IDF1为+1.1078/+0.7291/+1.1740点，B−PT bbox为+5.6404/+4.1638/+6.6677点；但B−强motion_RS为−0.2279/−0.1582/−0.1829点，B−A为−0.0102/−0.0121/−0.0789点。球衣额外收益和Pose超越运动均未证明；B−纯R仍有3/9单元下降，B−PT有1/9下降，不报全情形稳超。模型为固定PT感知下新学身份关联器，不是新Pose头准确率提升。测试封存，不重启本轮或自动加训。
- 队内/跨队独立CPU诊断也已完成：4791合成固定候选中同身份833、同队负775、跨队负1150、未知2033全部保留；几何覆盖未一致提高，共同有效点A/B差约0.77–0.90像素。这不是实际追踪分队收益或Pose准确率。全结果及局限以前述完整报告为准。
- 旧失败蓝批的625份EXR已在绿色发布且所有UE退出后按精确清单退休55136216798字节；625份RGB及native/轨迹/校准/失败收据保留，不虚构旧后处理成功。完成收据为`Saved/StoragePolicy/failed_blue_full_a02_retirement_a01/completion_receipt.json`，不重放删除。
- 最新指令：取消专门的渲染/导出加速开发和性能基准，已有未接入候选保留为停止使用的WIP，不作为实验前置。直接推进绿色材质短样、原seed球衣同运动/相机完整配对和同3000R预算对照。采用已验串行单机位采集→正常退出→后处理→精确清EXR；训练继续用已有预取，测试封存。
- 最新方向按用户要求转为[原版绿色及有限变化](Docs/engineering/GREEN_FLOOR_VARIATION.md)，蓝/红保留诊断，不继续旧蓝批作为下一轮主训练。原实例仅`Param`标量、无颜色vector；已通过真实UE在全新GreenV1创建复制父图和五个实例，增益/原标量逐项读回、原图及非BaseColor连接保留、源文件SHA不变、无材质编译报错，未改地图且正常退出。下一步实际绿色短样验收，再完整采集；材质参数通过不等视觉/采样通过。颜色与纹理/粗糙度不同时变，沿用原floor seed算法，序列内固定。
- a03已完成1048 A/B四机位共8单位：2400RGB/mask、24000Pose，均正常UE退出并精确清EXR。a04尝试渲染与6CPU导出重叠，1102_B/Cam01再次触发真实commit低于6GiB保护，正常取消/恢复/退出，parent为`failed_preserved_no_replay`，不重启。1102_A/Cam01导出工人随后独立完成300RGB/mask/3000Pose及300EXR退休；parent仍记录8项，不伪造整批完成。并行加速方向已按用户要求终止。入口为`Saved/AppearancePlanning/seeded_kit_capture_a04/control_a01/state.json`及其独立工人完成收据。
- 用户新增模糊/噪声和吞吐要求，已形成[成像退化与吞吐计划](Docs/research/IMAGING_REALISM_AND_THROUGHPUT.md)：当前球衣实验不混入增强；后续独立2×2噪声/模糊代理、真实相机模糊另立曝光GT契约。PNG低压缩级别组件实测像素不变、约1.55倍，仅是编码组件，不是整条导出/训练加速结论；新导出记录阶段耗时，训练保持同3000R、预取及测试封存。

- 原seed球衣a02短样已真实验收：两seed×A/B×四机位×3帧，48RGB/48mask/480人物Pose；服装原生应用/逐帧读回/恢复与会话释放通过，根agent已看配色及四机位并列图。同源world逐值相同；8对中帧mask中一对差61像素，其余0。48份EXR已精确清理约3.992GiB，原生/校准/收据保留。当前实际有15套服装资产，旧v1抽样目录仅Set01–05，不能称项目只有5套。短样验收继续复用；完整新绿版本另立来源及采集准入，不重启失败a02/a03/a04；测试集封存。入口和限制见[接回方案](Docs/engineering/POSE_SEEDED_KIT_INTEGRATION.md)。

- [v9完整78臂结果](Docs/research/POSE_V9_RESULTS.md)和实际进程退出/独立预算核对已全部结束：78000实际更新、234000R/39000S窗口，所有同fold/seed的R顺序/pair/初始化及各RS的S一致。主结论维持混合−纯R AssA+0.8867、对同名义参数motion仅+0.1459、对原v8 motion−0.4491点，Pose增量未达门槛；探索仅预登记首seed，drop相对同seed运动+0.6077点不能冒充三seed稳定收益。完整完成链为D研究根`pose/pose_quality_v9/milestone_complete_a01.json`；不重启v9。现在转入原seed球衣native接回及A/B，尚未宣称UE动态修复或新数据通过。
- [v9主54臂阶段结果](Docs/research/POSE_V9_MAIN54_STAGE.md)为历史中期报告；随后全部78项及实际预算核对已结束，完整结论以前述最终结果为准，不再等待或重启探索臂。
- 用户要求复用已有seed球衣系统。原1048/1102的四类Set分配和独立seed算法保留，Pose固定模型/肤色不随原manifest重抽，不接号码WIP。native材质钩子及一次短样现已通过，原v9/资产不改；此前独立配色选择器已撤回。
- [v9只读诊断](Docs/research/POSE_V9_DIAGNOSIS.md)已完成：90项固定模型窗口报告、三场自由motion参考逐字节复现、144个同尺度人物crop域探针。缺点敏感度高于小抖动；颜色和成像域差明显，抽样两队球衣统计高度相似，但不能据此归因拟真不足或称关联器直接学颜色。源GT Pose仅用于合成投影诊断，不进入训练。
- [v9质量残差对照](Docs/research/POSE_QUALITY_RESIDUAL_V9.md)主54及探索24已按原冻结矩阵完整结束，预取2和观测缓存真实闭合，训练收据累计约2081秒；诊断10次更新不计正式预算。完整结果和实际预算已另收尾，保留原冻结源码与全部失败/负结果，不重启控制器。
- [v8完整结果](Docs/research/LEARNED_ASSOCIATION_V8_RESULTS.md)已收尾：36训练、42追踪/评价、实际进程退出及独立窗口/pair预算核对全部完成。36000更新、108000R/18000S窗口曝光，所有九个四组的实际R顺序/已知pair/初始化相同，两RS的S相同。预取真实闭合；全部训练约852秒。
- 同真实预算pose_RS−pose_R宏均AssA/HOTA/IDF1为+2.8034/+2.1881/+2.9859点，达到事前门槛；相对预训练ByteTrack为+1.4727/+1.1678/+1.8433点。三个seed和比赛均差正，九单元8正1负，game9第三seed AssA−2.0417点；pose_RS仍在game9比赛均值低于预训练。
- 关键限制：motion_RS最强，pose_RS相对它AssA低4.3956点；motion_RS−motion_R为+1.6816点。因此当前支持合成身份连续性监督的开发增益，尚不能称Pose特征优于运动线索。断档proxy恢复pose_R40.2371%→pose_RS45.3626%，仍低于motion_RS48.6053%。最终116/187封存，不自动开始新训练。
- [v8可学习困难候选关联](Docs/research/LEARNED_ASSOCIATION_V8.md)的共享输入与协议已完成：1048蓝四机位1200帧、真实game4/6/9各750帧预测均完成；补1800张真实train图、复用450张原图引用，约352MiB下载块已精确清理。三折各1000唯一R窗口、共享1000唯一S窗口及956个检测断档proxy事件已在看学习结果前固定。
- v8采用game4/6/9留一比赛三折、三seed、motion/pose×R/RS四臂，已全部完成。每臂1000更新、同3000R窗口同序，混合额外1000S；窗口和pair曝光分开记，不冒充原图预算。4次单步诊断独立记录、0正式预算。a01在零正式更新时遇到TrackEval COMBINED计数无Frames字段，a02最小修复，旧失败证据保留，优化重放0。权威终态和完成链为D研究根`pose/learned_association_v8/milestone_complete_a01.json`，不重启控制器。
- [v7姿态质量、敏感度与时序关联](Docs/research/POSE_QUALITY_TEMPORAL_V7.md)三阶段已全部结束。COCO200开发图514人已知框诊断：肢体OKS预训练0.705400、R3均0.698685、蓝/红混合0.699315/0.699546；混合仅微升R3，整体17点未改善且均低于预训练。本轮复用既有权重、0新正式更新，逐臂仍为3000R；有界预取实际用于十模型质量推理准备。
- 成本敏感度900事件精确复现原静态MOT及lambda0；5605个非空候选行仅175个竞争（3.12%）。九模型改变成本但未改变排序或阈值可用性。历史3观测、最多3帧OLS时序对照十模型完整完成，实际使用4448–4449候选对，最终轨迹仍与v6相同；混合−R3/时序预训练均差0，未达到门槛或超过原预训练。最终116/187封存，相关进程已退出。
- [v6固定raw检测框裁剪Pose对照](Docs/research/POSE_FIXED_CROP_V6.md)十模型已全部完成且实际进程退出：复用v5九个last EMA及预训练、零新正式训练更新、每臂相同3000R。覆盖从约24.3%升至77.95%，但十模型轨迹输出和指标完全相同；两种混合−R3及混合−同crop预训练均为0，未通过进步门槛。
- 全部crop模型AssA/HOTA/IDF1为71.5327/65.4676/81.2946%，IDSW25；相对原整帧预训练低0.5885/0.2596/0.4247点。针对检查确认前两帧训练模型与预训练关键点确实不同，当前关联器未把这些差异转成不同离散轨迹；不将覆盖增长当作准确率或合成收益。
- 真实GPU预取ABBA基准已完成：四次各64诊断更新，同步均25.426秒、预取均16.429秒，约1.55倍；最终模型/EMA/曝光链全部逐值一致。不是1000步完整训练速度承诺，256次诊断更新不计正式预算。代码及记录已推送`942a0b8`。
- v5九训练/官方200图开发评价及九臂固定检测真实追踪已全部结束，相关进程实际退出；9000次正式更新、27000R/6000S曝光，test116/187未使用。原定时跟进v5已按完成条件删除，不重启。
- 相同3000R曝光：蓝混合平均AssA +0.26444035个百分点、HOTA +0.12183663、IDF1 +0.18911788，仅1/3训练seed正；红混合三指标均差0，同为1/3正。均未通过登记的AssA+0.5点/至少2seed门槛。
- 蓝混合与预训练追踪登记指标及现存MOT文本相同；红混合平均AssA低0.26444035点。姿态AP均值蓝/红相对R3仅+0.0828/+0.0335点，全部低于预训练。尚未证明稳定合成收益或超过预训练。
- v5有效Pose覆盖仅24.27%–24.32%，每臂5220/6901检测因第二套模型bbox不匹配回退；九臂仅两种MOT输出组合。该线索已由v6覆盖提升和v7质量/敏感度实验继续检验，不能把低覆盖断言为唯一因果。
- 权威收据为研究根`pose/poseonly_v5/milestone_complete_a01.json`及`pose/association_dev_a01/v5_association_a01/complete_analysis_a01.json`，完整正负结果见[v5结果](Docs/research/POSE_V5_RESULTS.md)。[v4历史结果](Docs/research/POSE_V4_RESULTS.md)及原失败attempt保留，不重启。

## 本轮整理结果

1. D恢复迁移已完成：44,007文件约13.889GiB，保留97条正式Dataset引用；辅助小证据已归档、可再生夹具已清理，旧G盘Research/Workspace根已删除。原迁移完成收据已归档到`Saved/Maintenance/pose17_20261025/storage_receipts/restore_D_20261025_045844_4237/`，辅助收据位于`Saved/CodexMigration/workspace_aux_20261025/`，不重放。
2. 阶段1文档整理已推送`599e90b`。阶段2代码已移到`python/`，实验提到根`experiments/sim2real/`，P1运行数据位于`Saved/P1/`；没有兼容旧Content的junction。Python3.9环境已离线重装本项目editable，CLI和真实GRF同seed跨进程4步检查通过；路径/CLI/resolved-task针对CPU检查71项通过。Git仅按原blob改名并叠加本轮路径修改，保留未完成号码及其他WIP。
3. 阶段3已完成并推送`d4468e9`：60个足球/球门/看台资产通过真实MCP移到Environment，23处场景网格引用检查通过，17个仍有引用的旧重定向器保留，5个既有资产WIP字节未变。本轮Editor已正常退出。
4. 阶段4统一入口为`tools/run.ps1`、`tools/mcp_cli.py`；路径输出、P1实际配置校验/UE命令生成、独立研究帮助及MCP帮助已通过。37项一次性清单/入口已归档，运行收据回Saved，旧驱动放入`tools/legacy/`。

## 本轮v5验收

- UE手动启动已修复：同DLL显式项目路径真实加载，最近项目自动恢复设置关闭，裸引擎启动不再触发缺模块且正常exit0；`1c2b331`已推送。当前保持UE关闭。
- [v5九臂](Docs/research/POSE_LONGPAIR_V5.md)训练及官方200图姿态开发评价完整结束：各1000实际更新、同3000R同序，混合另1000S，共9000更新、27000R及6000S。权威终态为D研究根`pose/poseonly_v5/control_a01/driver_state.json`，完整姿态分析为`analysis/complete_pose_a01.json`；CPU验证更新不计正式预算。
- 三seed平均姿态AP：R3为47.0578%、蓝混合47.1406%、红混合47.0912%；蓝/红相对R3仅+0.0828/+0.0335个百分点，第三seed两混合臂均下降。全部低于共同预训练49.1896%，不能宣称超过预训练或真实追踪已有收益。详细正负结果见[v5结果](Docs/research/POSE_V5_RESULTS.md)。
- 唯一交接器已自动完成`pose/association_dev_a01/v5_association_a01`九臂真实Pose附件→关联→TrackEval，两比较完整保留。当前无研究训练/追踪/UE进程；不重启训练、交接器或旧关联。测试116/187继续封存。
- 后续性能规则及预取候选已推送`9601d63`，实际ABBA GPU基准及结果已推送`942a0b8`。六项CPU、两PNG等价及四次64步GPU模型/EMA/曝光链等价通过；未热改v5。本次有限GPU基准显示1.55倍，后续完整新训练优先接入有界预取并记录真实端到端耗时。

## 数据与存储

- v1：`G:/FutsalMOT_Dataset/v1_no_numbers_4k`，8seed、32相机序列、20116对原生4K RGB/mask，保持不变。
- 位置试产：`v2_pose17_location_pilot_a01`，1920对4K/19200逐视角人物Pose，480源时间样本。
- 30秒配对：`v2_pose17_longpair_pilot_a01`，4800对4K/48000人物Pose，600源时间样本、2seed×2floor×4cam×300帧，16条30秒序列。world最大配对差约0.068mm，不是exact；unknown/diagnostic/not_training/MRQ_syncfalse保留。
- 冗余raw历史清理已完整成功638.191GiB；本次另按精确清单退休旧1042的480份EXR、39.460GiB，正式RGB/mask/Pose/world保持，原EXR深度不再保留。收据：`Saved/StoragePolicy/legacy1042_exr_retirement_transaction_a01.jsonl`。14份旧日志/tmp已删，AutoSave关闭。不重复清理或重做媒体审计。
- 所有渲染媒体包括临时EXR只写G数据集根`_work/_staging`及正式版本，14处MRQ输出目录设置已加入物理路径/联接/80GiB余量检查，P1默认已改G；路径定向3项及清理夹具通过。EXR消费结束即清理，不等只用RGB的训练。Saved元数据和研究工作留D，研究执行代码为`DResearch/code/<SHA>`，不复制4K到D。详见[严格存储规则](Docs/operations/STORAGE_POLICY.md)。

## 四阶段整理验收

1. Docs分类、统一索引、清除重复/过时入口，README/AGENTS/本页各司其职；号码文档WIP保留。
2. `python/`负责P1包及UE Python，根`experiments/`负责研究；统一stdlib路径helper、包名和环境隔离不变。原实际v4源码已在`9a5cbe9`固化，26/26源SHA一致；新布局不自动获得旧冻结协议准入。
3. GPU任务结束后通过真实UE整理资产并修引用；保留项目文件名和默认地图，不按Tests/Development文件夹名直接删除共享生产资产。
4. 固化稳定入口/本机路径配置及小检查；运行收据、临时清单离开源码目录，精确提交各阶段成果。

## 后续研究

v8/v9、绿色球衣及v10现均已闭合。用户要求的[后续方案](Docs/research/POSE_DIAGNOSIS_AND_REAL_DATA_SUBSTITUTION_PLAN.md)已制定：先开展固定权重的全错误/同候选诊断与Pose关闭/打乱消融，0优化更新、不开UE，再根据证据选择定向补采或方法修复。

数据价值另设资源对照：比较R3000、R3000+S1000、R3000+额外R1000。第三组明确为4000R的独立补充对照，不混入同3000R的Pose主实验。用户已选择不设可接受损失界限，只报告七比赛配对差值和置信区间。当前历史表格只支持混合模型小幅平均补充收益，不能证明合成与真实监督等效；窗口曝光减少也不自动等于标注成本减少。

当前C训练/实际预算已闭合，新验证输入下载仍继续，既有自动跟进接续；全部负结果和最终测试封存边界保留，不重启旧批或安排渲染/导出性能开发。

未完成号码继续保留、不纳入当前数据或提交。每独立阶段报告真实完成证据，历史started_not_committed不当作当前故障，不重复启动已结束驱动。

### 流式完整准入与a02恢复（2026-10-28 15:22）

完整750帧后验已实际完成，worker close/join/exit0，峰RSS176013312字节，最低可用RAM21456093184字节、commit余量36667961344字节，耗时407.30906秒。准入产物直接继承，新模型前向/追踪/优化更新均0；不将此耗时当并行整体加速。准入根`numeric_admission_a04/receipt.json` SHA `99d28cac4d8cf19726a554546cec3a0a46b83479fc6eab69ec6ab593ab232476`。

另签恢复配置`tracking_frozen_a02/config.json` SHA `a6ae5884ac3536ee092876cc1fcab7e378d21d184882ef6ad5af62664117e03c`，四文件bundle `f4836bf41e099d0203609dbb7a04dca32d8ad9741e3b39e53352d74b688f9ba5`。实际只读预飞通过，15:22:32唯一后台启动；controller与2track+1posthoc真实身份已核。权威新状态为`control_a02/driver_state.json`，初始5观察/3后验（旧2+准入1）；旧a01原样封存。不得重复启动/热改。完整诊断及单因素尚未完成，未生成新AssA。独立流式终验已安装`code/dc88c3bf9caee0e8aa56367601c698a020dc185e45eb71e356c0c886c83205d3/tools/research_ops/verify_state_gap_diagnosis.py`，待全诊断及真实退出后才运行新配置/新control，输出另用`final_verification_a02/receipt.json`。

## 最新输入阶段：自由状态R窗口来源a01

按[新验证协议](Docs/research/STATE_ALIGNED_R_TRAINING_A01.md)完成8CPU合同、真实六R后验来源资格/唯一性审计，以及三fold各1000新R窗原记录/标签读回。game4/6/9各允许两来源各500，无复制填额；all pair13558/13167/15740，known11500/10975/12765，positive435/321/359，unknown2058/2192/2975，无positive窗口565/679/641。原S、normalizer、旧池不改；新SGD/图像预测/追踪均0，尚未训练准入。输入根SHA031e10a5a7cc078030747f901cc1bbe5bce8017542c524e38d47abf3e9d7d74c。下一步仅训练数值/完整记录准入，18臂每1000更新、3000R，RS另1000S；模型/优化器/seed/损失及全部限制见绝对协议。不能称pair/FLOPs公平或状态问题已解决。

## 当前训练阶段：准入与首正式千步通过

2026-10-28已完成21项输入/runtime/controller/数值CPU合同，另6项独立预算审计合同。原源码核验纠正：强motion没有按epoch扰动增广，明确none_original_strongmotion；不是T/gated的both。域loss为每窗known-pair BCE均值后窗口均值，不能改成pair加权均值。

实际CPU完整核九表及全部3000新R窗口/35240known-pair特征194维、原normalizer/后170零、九初始化/R顺序/原S顺序；CPU两组手写对原loss共4诊断更新12R/2S。实际CUDA两组手写对完整记录循环模型/AdamW/全部RNG/0和1检查点逐值一致，共4诊断更新12R/2S。合计8诊断更新24R/4S另计，不当正式训练。学习准入根SHA c56c9da4b15fe2d79790146987dcf248cd956bf121d4c03186d14bf3fc22f9bf。

协议training_frozen_a01/protocol.json SHA 2acc7642109c317b9ca694d3649a864c5553e177f20425d24726de1781c7d3c6，必要11文件bundle code/1f9a22471b51d11879ca6f20aa5449fc279bbfbba2835772469809af991ac983；不热改。正式18000更新/54000R/9000S的十八臂20:33:38唯一启动。首game4/seed20261024/R已实际1000更新/3000R/S0，21完整模型+AdamW+四RNG检查点读回通过，控制器才继续后续臂。首臂含准备/记录/检查点/读回24.6310秒，不外推全部阶段加速。当前训练仍在执行，不称十八臂/预算/追踪已完成，也没有新AssA/HOTA/IDF1。

权威state为DResearch/pose/state_aligned_training_a01/training_control_a01/driver_state.json，日志_launch_training_a01及training_control_a01/logs。独立审计已安装code/9609623d0cca265f971114fdf4417cb521f58255e755814b8582e5a6f353ff0a/tools/research_ops/audit_state_aligned_training.py，尚未真实执行；十八臂齐及实际parent/child/launcher全退后，才以--config绝对protocol --control绝对training_control_a01 --output绝对postrun_audit_a01/actual_budget.json --execute运行，CUDA_VISIBLE_DEVICES=-1。需核378完整checkpoint、18000步/全部UIDepoch/all-knownpair/原init/norm/S及真实退出；cache无显式close不伪造true，保留实际预取join和run退出证据。

冻结时计划原bytes快照training_frozen_a01/plan_snapshot.md SHA755851787d2e21cc8cbcf1e16b0b1d761a72f06588fbb35450ad74a8be4a20f6保留；本文件后续更新不改该快照或活动协议。下一阶段才冻结新18模型×每fold10来源=180自由追踪，原匹配基线只读引用，原3/旧2/七场分别报告，未通过加载/GT隔离/cold-ABA准入不执行。全部负结果保留，测试封存。

## 最新闭合：十八臂训练、独立预算及真实退出

2026-10-28十八臂均已完成，各1000实际更新。独立审计实际核18000步、378完整模型/AdamW/PythonNumPyTorchCPU-CUDA RNG检查点、step0原初始化、原normalizer、九组R/RS相同R顺序及原S顺序、逐步loss/LR/grad/UIDepoch/all-knownpair/链与全部实际退出。正式总量：54000R窗口次、9000S窗口次；R all/known pair764370/634320，S46287/25191。8诊断更新（CPU4、CUDA4）及24R/4S另计。重放0，原日志和所有权重/负结果保留。新自由追踪/TrackEval完成数仍0，没有新AssA/HOTA/IDF1。

训练完成根`pose/state_aligned_training_a01/training_complete_root_a01.json` SHA `62646594150716226b4cb90087731b8d2c76fb836bd22a3218a776031ebf5a33`；独立审计`postrun_audit_a01/actual_budget.json` SHA `d551bb377a8d33b6f454fa5f119723c06c085555c85c37c55b5080f53d671212`，status complete18_state_aligned_R_actual_budget_full_records_and_exit_verified。实际使用独立审计单文件bundle `code/710811cbb5a35744ce7d8ae376c11fb473d89446d7d823f17f8fe07348325f77`，将CPU与CUDA诊断全部另计；原960候选未执行且保留，不修改活动训练11文件或协议。

下一阶段使用[结果前追踪分析规则](Docs/research/STATE_ALIGNED_R_ANALYSIS_A01.md)：180新任务与匹配180旧基线来源，三原/旧二/七场分开。主要新RS−旧RS，另新R−旧R、新RS−新R及两者合成增量交互，五指标共60个未多比较校正描述区间；每场先均匹配seed/fold再比赛等权，t95自由度2/1/6、10000比赛bootstrap固定seed20261028/逐场留一。先绝对成绩再差值/CI；无δ/等效通过标志。候选加载runtime已做6CPU夹具检查，真实新模型加载/GT隔离/cold-ABA/spawn和完整worker/control冻结准入尚未执行，不能当180追踪已完成。测试116/187/test持续封存。

### 最新阶段：180自由状态R来源追踪已准入并唯一启动

2026-10-28 21:09:02唯一后台，cold/ABA/双spawn实际96唯一帧/336诊断推进及五worker退出通过；首R/RS两源完整metric/GT/ID0门禁已过，2track+1metric继续余178并自动分析。权威state为DResearch/pose/state_aligned_training_a01/tracking_control_a01/driver_state.json，配置SHA5aa553b7d4d5734ee748e410157f5cf8ae0287e593bb04e75cbe816229a8411b，冻结四文件bundle53bf25ce。a01加载导入失败0帧已保留，a02独立修复成功；不重训/重审计/重启第二controller。先等180/分析/真实全部退出，再执行独立终验code/6dc4a6de的verify_state_aligned_tracking.py，--config绝对tracking_frozen_a01/config.json --control绝对tracking_control_a01 --output绝对tracking_final_verification_a01/receipt.json --execute。新AssA结论尚未闭合，每轮即时历史已更新，测试封存。

### 最新闭合：自由状态R来源单因素完整负结果

18臂训练/180项新追踪/完整配对区间/独立终验a02及实际退出已闭合。主新RS绝对AssA原3/旧2/七场为27.8857/37.1806/27.8556，原RS31.8642/40.1160/30.2129；没有提高，12场比赛均值均下降。纯R也下降，不能归因S；具体R政策退化不等于所有状态对齐训练无效。完整绝对成绩、60+12区间和失败证据见Docs/research/STATE_ALIGNED_R_TRAINING_A01_RESULTS.md。禁止重训/重审计/重放180；本轮结果不采用替换原参照，不自动继续搜参数或新因素。历史即时更新，测试继续封存。本轮收尾精确push后删除实验跟进，不重建已删除的每日history automation。

### 最新执行：既有训练日志的零更新决策机会核查

用户已授权继续。原未校准strongmotion_RS保持主参照；新来源退化模型保留不采用。decision_opportunity_a01首750/15178行流式准入及worker退出已闭合，成功产物直接继承，正式12仅补11。权威DResearch/pose/decision_opportunity_a01/control_a01/driver_state.json；cfg SHAa5aefc8559e23cae1d4fc12606969aad2748a08c872567016561dd05ba4ea504，两文件bundle df6ed0dd99e452ae8b22b3d6380d8a4d1a86d1776ec39dc4678991b91eb5dfd6，不热改/重复执行。先核全180118行/84描述区间和退出，再独立终验，随后依据完整机会证据仅选一个因素；尚无新AssA或Pose可纠错结论，测试封存。


### 最新闭合：决策机会核查独立终验通过

完整12/180118行/84区间及退出已闭合，模型/训练/新追踪均0。3259局部机会中2835双方Pose结构支持，可信错选0/未匹配21/unknown4，21只在SNMOT097；不能支持直接Pose训练或宣称总体无效。anchor漂移13319重复状态行，不能直接当训练池错标签。下一项仅交叉核已训练3000R窗的目标身份锚定和实际正候选/介入边界，不改模型/池/阈值。原strongmotion_RS保持主参照，测试封存。详见Docs/research/DECISION_OPPORTUNITY_A01_RESULTS.md。

### 最新闭合：3000实际R窗口交叉核查与下一目标

3000窗/六R账本/原三池不变及全部UID/标签/CSV汇总独立核验通过；anchor偏离代理256（不能称错标签），无known正例1885（不等于真实场景确认无匹配）。无新增训练/模型/追踪，原strongmotion_RS保留。下一因素只改R损失为候选集合CE加固定无匹配logit0；原池/标签/S/初始化/模型/预算和推理阈值不变，不能同时过滤窗口。集合损失已通过7个小张量CPU合同；极大有限FP32空known求和溢出已修复并验证。完整训练记录、真实CPU/CUDA一步对照、独立终验及首1000训练准入尚未完成，不称已开训。见Docs/research/R_SET_SUPERVISION_A01.md，测试封存。

### 最新闭合：3000个训练R窗口锚点审计及集合损失候选核查

3000个实际R窗逐条连接六个R teacher账本及原窗口池；三fold每个1000唯一窗。早期anchor偏离代理256/3000、无known正例1885/3000，保留全部窗口及标签。前者不是错标签，后者不能证明物理场景中无人可匹配，因为unknown仍可能含真实目标。950窗具局部当前身份正负候选机会、其中811窗有双方Pose几何支持；受支持可信错选0，未匹配8且均为SNMOT097/game4重复观测。这些是固定日志构成，不是新追踪成绩或因果证明。

只选择R监督目标这一因素：known pair BCE均值改为带固定no-match logit0的集合选择loss；S BCE/系数1/3、3000窗来源及次序、全部标签、194→64→32→1 ReLU/14593参数/FP32、原normalizer/init、AdamW学习率0.001/weight_decay0.0001、每臂1000更新/每步3R（3000R）/RS额外1000S、sigmoid推理阈值0.50等保持。候选代码曾有空known极大有限FP32求和溢出，独立复核后用“先逐项乘零再求和”修复；7项针对性CPU合同现通过。审计/实现耗时和前向不代表训练成绩；新SGD/模型/追踪/TrackEval均0、正式准入未完成。下一步先冻结独立方法/记录bundle和数值准入，CPU及真实CUDA一步逐值通过后才评估首1000训练；原强motion_RS维持主参照，测试116/187/test封存。


## 正式训练首千步门禁与唯一启动（2026-10-29）

真实CPU/CUDA数值准入已闭合并随d041fef推送，唯一正式控制器已启动。首game4/seed20261024/R完成1000实际更新、3000R/S0，21完整检查点含原初始化、AdamW实际步数、全部RNG、方法状态及UID/epoch/all-known-pair链核查通过，随后才继续其余17臂。正式预算为18臂×1000=18000更新、54000R/9000S；当前只是首臂准入闭合，不称全18训练完成或追踪提高。

权威状态为DResearch/pose/r_set_supervision_a01/training_control_a01/driver_state.json；日志在control的logs与_launch_training_a01。固定7文件bundle a536124f、协议SHA301eb84a保持不可变。GPU训练使用prefetch2、256MiB特征缓存，数值线程1，保留RAM8GiB/commit6GiB/VRAM2GiB。18臂和真实退出后才运行独立预算审计，不重放旧实验或准入成功步骤；SNMOT116/187/test封存。
