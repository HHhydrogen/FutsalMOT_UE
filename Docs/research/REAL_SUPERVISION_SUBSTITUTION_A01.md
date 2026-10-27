# 真实监督资源对照：七比赛与配对区间方案

更新：2026-10-27。用户选择“暂不设界限，只报告配对差值和置信区间”，覆盖此前以非劣效准入为前置的候选方案。本轮不设δ、不执行等效/非劣效检验、不输出“可替代/效果相当”通过标志。C十八臂训练/预算、七场4790输入/共享PT预测、392项自由追踪/区间分析及独立终验已全部闭合，实际生产者退出。[完整结果](REAL_SUPERVISION_SUBSTITUTION_A01_RESULTS.md)保留全部组/指标/负项；主motion的B−C AssA为+0.0024点，95%CI [−0.5608,+0.5657]，不能由均值接近或区间跨0宣称真实等效。

## 实际比赛范围

已从[SportsMOT官方仓库](https://github.com/MCG-NJU/SportsMOT)固定commit `b06cfb4aacb0bb16c5778ac4ddb0d70ec6835444`读取train/val各45段；90段归并为25个源视频。没有读取test清单、GT或媒体。标题已知足球源与未知运动源各取字典序首个官方片段作身份核验，9张首帧实际检查后排除两段排球，确定7个不同足球比赛。源视频ID/片段数本身不是独立比赛证明。

| 原split | 固定片段 | 实际比赛 | 首帧记分牌/时间 | 全片段帧数 |
| --- | --- | --- | --- | ---: |
| train | v_1yHWGw8DH4A_c029 | 莱比锡–拜仁，2017 | 31:47，2:1 | 725 |
| train | v_HdiyOtliFiw_c003 | 沃特福德–狼队，2018/19足总杯 | 76:19，0:2 | 775 |
| val | v_ITo3sCnpw_k_c007 | 热刺–阿森纳，2017-04-30 | 79:24，2:0 | 701 |
| val | v_dw7LOz17Omg_c053 | 拜仁–多特蒙德，德国杯，日期未核实 | 90:00+1:07，0:0 | 550 |
| train | v_gQNyhv8y0QY_c003 | 洪都拉斯–摩洛哥，2012奥运会 | 65:01，2:1 | 700 |
| val | v_i2_L4qquVg0_c006 | 利物浦–曼联，2015-03-22 | 83:03，1:2 | 888 |
| train | v_iIxMOsCGH58_c013 | 布莱顿–曼联，2020-06-30 | 49:31，0:3 | 451 |

共4790帧，25FPS、1280×720。比赛选择先于任何新模型评价；首帧球队/记分牌/场地与标题相互核验，已对照原三场匿名Swiss场景及已观察多特–沙尔克/诺维奇–伊普斯维奇。拜仁–多特的日期未知原样保留，不能猜成具体某届决赛。两段排球为`0kUtTtmLaJA`与`CW0mQbgYIF4`，未混入足球验证。

原train归属不改名为官方val，仅在本实验标记`external_validation_only`，不用于关联训练或标准化。每场仅一个短片段、来源便利抽样，不能称整场覆盖、随机总体样本、最终盲测或真实五人制泛化。旧五场完整保留为已观察开发参照，不并入新七场主汇总。最终116/187与test包封存。

## 比较与区间

主架构为强motion，gated为事前登记次架构；三fold×三seed均保留。A为基础3000R，B为3000R+1000平衡S，C为3000基础R+1000额外R，总4000R；各臂1000更新、FP32、同初始化/基础R表与标准化、预取2、last而非best。B/C额外组均按`mean(base3R)+mean(extra1)/3`聚合；pair/计算另记，不称等图像/等FLOPs。

分别报告B−A、C−A、B−C，每场先平均9个匹配fold/seed差值，然后七场等权。AssA为主指标，HOTA/IDF1/DetA/MOTA及同组gated−motion为次要描述；全部逐场、逐seed/fold和负结果保留。

- 主区间：七个比赛差值的双侧95%Student t区间，df=6；条件为固定训练模型面板，需说明比赛差值近似独立/正态假设。
- 敏感度：比赛层级百分位bootstrap，固定10000次、seed20261027，及逐场留一均值；不挑更有利的区间。
- 不把9个训练重复当9场比赛，不从帧/窗口增大n；不将区间覆盖0解释为等效。区间未校正多重比较，不用于挑优或事后宣称显著。

区间原理依[美国NIST均值区间公式](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm)。结果前曾只做精度敏感度：假设比赛差值SD为0.5/1/2点，七场95%t区间半宽约0.4624/0.9248/1.8497点，未把旧B−A波动冒充未来B−C方差或功效保证。实际结果现见完整报告；小样本和便利选片限制与区间同时保留。

## 数据获取与失败记录

公开传输镜像固定`Lekim89/sportsmot` revision `2993b47d4369fa70ea70afc8bc63b5964e556a81`；官方只核验split名字，没有官方像素SHA。首帧获取a01在完成一源后遇到TLS `URLError(FileNotFoundError)`，原目录/失败收据保留。独立a02明确继承成功首帧，按已有有界网络重试完成其余八源，不覆盖旧partial、不关闭TLS验证。

完整验证输入已独立冻结并通过实际只读预飞，唯一后台获取七场4790帧：复用七张首帧、新取4783张并首次解码，GT只用于评价，不筛预测。权威`D:/projects/FutsalMOT_Research/public/substitution_validation_a01/state.json`，完整manifest与实际进程退出前不能进入新共享预测。失败保留，不隐式重下成功内容。

随后a01实际在第414帧遇到JPEG解码截断并退出，419条已记账记录及17个解码后写入、尚未进入journal的文件全部保留。精确重取同URL的414帧时，237702字节、Content-Length一致且EOI完整，解码通过；支持瞬态输入传输问题，原坏响应未落盘，不能逐字节归因上游设备。没有开启坏图容忍或跳帧。

新a02显式继承437张成功图（419条原账本、17份首次补持久SHA、1张独立诊断成功的414图），只补4353张；不重哈已记账图或重复解码成功图。当前唯一权威改为`public/substitution_validation_a02/state.json`及新manifest，准入SHA `9f8c08b21b2dffd3728f644e7045e36d3abe7b62689d1f30f61b5dbc5da9b2c7`，bundle `code/fcead3726da4a40f149489cbda7c0d8742e405af3c1daeabf1eabcbca77a11e7`。JPEG校验纳入有界重试，失败原样保留，不改变七比赛/4790帧或分析。输入路径通过明确ledger引用旧成功目录/身份首帧/诊断414，不复制掩盖历史，不建别名。

研究根`D:/projects/FutsalMOT_Research/pose/real_substitution_a01`：

- `validation_frozen_a01/matches.json`，SHA `6ee812ba192f8ccc00818da31e9b8e88f7cd0e603a58e4af7c27b6256a5277c8`。
- `analysis_frozen_a01/plan.json`，SHA `afee40ca64dc44a12b5b4c684b313d02831ad0bdcbd5d5201c4f824ffabefc0c`。
- `precision_a01/report.json`，只读旧结果与假设方差的CPU精度报告，优化更新0。
- `validation_input_frozen_a01/config.json`，SHA `7e78354eae2249930466f291b12ba94cf19a6ccedbf795ab9c0b03431e5bb7f6`。

## C的完整记录与实际预算

`training_journal.py`增加独立`full_training_record_spec_v2_real_groups`，每步显式记录3基础R/1额外R、总4R/0S，两类真实loss和pair。检查点采用`full_training_checkpoint_v2_real_groups`，不借v10身份；0/每50/1000保存模型、优化器、完整RNG/曝光链。原v1三R/一S路径保留，旧D执行bundle字节未改。

新增独立`substitution_C_runtime.py`/`substitution_C_train.py`/`substitution_C_control.py`，4项预算/heldout/真实域检查和5项记账检查通过。两架构实际CUDA手写C更新与新记录循环的loss、全部模型和优化器状态逐值一致，完整v2检查点读回通过；4次诊断更新/16R窗口单列，不计正式训练。实际数值收据为`C_numeric_validation_a01/receipt.json`。额外R始终按原`real`处理/增强，基础与额外R的不同UID只合并到cache的real域，没有传入synthetic伪装来源。基础normalizer和quality_scale只读复用，不从额外R或新验证比赛拟合。

C所需2250帧共享预测/三fold额外R输入此前已完整验收，七比赛只作评价。因此C的数值验证和训练与当前CPU验证下载独立推进；待C结束、GPU身份退出且七比赛输入完整后才运行新共享PT预测，随后自由追踪。该执行调度不改变比赛、分析或训练因素，不等候新验证结果选择模型。

十八臂协议`C_training_frozen_a01/protocol.json` SHA `e57a5a40d53f0d6b20ed0d790703a24abbb602c14679d135e1a198d5f568733c`；八文件最小bundle为`code/de488c3d5ba533deed5ac96ac4b326579e9e6322333f91d581463fac17e22802`。实际十八组只读预飞已逐项核验A/B初始化、原R表、额外R和来源；权威`C_control_a01/driver_state.json`已终态`complete18_C_training_wait_independent_audit_tracking`、18齐全、active为空。首臂21份完整状态核验通过后串行完成其余17臂，无best/EMA或隐式partial重放。

独立单文件审计bundle `code/d8f3163b286e02d232092396bebc6d804f3c9c3781c743c1088afcc0ab28c61c`已实际CPU执行，`C_postrun_audit_a01/actual_budget.json`终态`complete18_C_actual_budget_full_records_and_exit_verified`。真实控制器/launcher/训练身份退出，18×21=378份模型、优化器、Python/NumPy/Torch CPU/CUDA RNG检查点全部读回；实际step0初始化、九组两架构UID顺序与all/known pair及18000步链/LR/loss/梯度齐全。实际累计：

| 类别 | 窗口曝光 | 全部候选pair | 已知标签pair |
| --- | ---: | ---: | ---: |
| 基础真实 | 54000 | 202680 | 156492 |
| 额外真实 | 18000 | 75456 | 51012 |
| C合计 | 72000 | 278136 | 207504 |
| 合成 | 0 | 0 | 0 |

正式18000次更新，4次诊断/16R单列，重放0。上述为累计曝光，包含跨fold/seed/架构重复，不是独立帧数或等计算量；训练已闭合不等效果验证已完成，不重启C。

A/B只有数值源码、初始化、输入/顺序与预算完全一致才引用；历史A缺失LR/梯度/RNG字段继续标缺失，不补造。共享PT入口/ledger契约5CPU检查及真实完整输入预飞通过，实际运行及完整效果见下文。全部阶段已按输入→预测→追踪顺序完成，没有由结果反改模型或分析。

## 七场输入完成与实际共享预测启动

2026-10-27七场4790帧已真实全部完成首次解码、GT/seqinfo及ledger核验，获取state/manifest均终态，实际producer与launcher退出。a02继承437张成功图、仅补4353张；失败a01/诊断414及原路径均保留，无跳帧/坏图容忍、无媒体重复hash或成功图重复解码。输入manifest SHA `a948c541523dd886df86acab3f3e2270a812df1bec35529c6ff62fffc47b966b`；`validation_inputs_complete_root_a02.json` SHA `c3de03b1f926095b289044441329b78676045b136016647c29af86266e485046`。七段GT行数依表顺序为9989/11518/9780/8829/7537/11900/7049，GT只供评价，不进入模型或筛预测。

共享预测已独立冻结`prediction_frozen_a01/config.json` SHA `89a789b668da0fbd8d69c00b21487110bc115c9734e2a824ce5cfed0668d0119`；必要五文件bundle `code/b8a8573fb45fb974b0754230a811de7efa76d9ab6eea2a0454d3809dcb66f6eb`。实际默认只读预飞7源/4790帧通过，11:29:41唯一后台启动，stdout已实际完成首场至少250帧，不能把启动当七源完整完成。权威输出`shared_predictions_a01/manifest.json`及`_launch_shared_prediction_a01`日志；完成须七源4790齐全、manifest终态`complete7_sources4790_frames_not_tracking_authorized`并确认实际GPU/launcher身份退出，再签完成根和断档登记/追踪准入。活动五文件和配置不热改、不重复启动。

原固定PT detector/cropPose、FP32和预取2直接复用，原图检测不GT过滤、所有bbox-only保留，旧R/S/PT缓存不重推，新增优化更新0。该共享预测现已完整结束，后续状态如下。

## 共享预测闭合与392项真实追踪

七场4790帧共享预测已实际完整结束，原GPU/launcher身份退出。独立单次stream核验全部预测JSON的帧顺序/时序/比赛身份、缓存SHA和实际计数通过，未重读图像；`prediction_complete_root_a01.json` SHA `76aa4417f32eec8d03f852d391ec36e87ecf1716b0ba9ad4bb5f633f4a63de81`。共90490个raw检测、63306个几何规则通过、27184个bbox-only；这是规则通过计数，不是准确率。旧R/S/PT不重推，不改共享缓存。

在任何本轮追踪结果前，冻结原v8双向唯一IoU端点规则实际登记2337个可信检测断档proxy：依七场顺序为293/423/351/327/375/287/281。`evaluation_inputs_a01/gap_registry.json` SHA `c05fc1f0ac2a39685afec25224f862d17b7103197994d09da002fc17a7cedf04`，无GT坐标的`gap_registry.receipt.json`供追踪读取；完整端点GT只由登记/评价读取。同一注册事件在不同模型下重复评价，不是2337个独立比赛或物理遮挡证据；全分母、无事件null规则保持。

实际追踪协议`tracking_frozen_a01/config.json` SHA `fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78`，必要五文件bundle `code/abf088088192e2a75442515c62a6171f509911df1547e368c4396cea4044f8e2`。完整392矩阵及来源只读预飞通过，11:38:39唯一后台启动；先14项PT真实评价门禁完整通过，再执行全部378学习模型任务和自动分析。`tracking_control_a01/driver_state.json`现已终态`complete392_tracking_and_paired_intervals`、392齐全/active为空，真实相关进程退出。纯CPU/Torch线程1，未新增训练或改阈值。

报告已终态`complete392_all_results_and_paired_intervals`。独立终验器`verify_substitution_tracking_results.py`从单文件bundle `code/0b3ee813ca965f1a20ac85a5ddbf649ecec0bb6fde04654666621717a7c370fd`实际执行通过，核对392来源/MOT/GT及全事件分母、1323配对行与105个t/bootstrap/逐场留一区间及完整CSV；`final_verification_a01/receipt.json`终态`complete392_sources_all_results_1323_pairs_105_intervals_and_exit_verified`。未重跑模型、TrackEval或C预算。数值序列化核验容差不是性能非劣效界限。全部原始模型、记录、指标及负结果保留。

[完整结果](REAL_SUPERVISION_SUBSTITUTION_A01_RESULTS.md)中主motion的AssA B−A为+0.2781 [−0.3068,+0.8629]点，C−A为+0.2756 [−0.5796,+1.1308]点，B−C为+0.0024 [−0.5608,+0.5657]点；次gated B−C为−0.0520 [−0.3855,+0.2814]点。所有主区间跨0，不能作等效或可靠提升结论。完成根`complete_root_a01.json` SHA `1fb5af28657d4c849a15b09231f8f03dd8153629e7fa0349e4f524116f321478`。本阶段已闭合，测试封存，研究主线仍有Pose机制、分布泛化与人工成本未决。

## 历史：等待输入期间的独立CPU准备

用户要求保持“输入→共享预测→追踪”的实际执行顺序。下载等待期间只构建后续入口，不提前评价新比赛，也不另训模型或增加渲染/导出性能工作。

- `substitution_tracking_runtime.py`、`substitution_tracking_jobs.py`和`substitution_tracking_control.py`在等待时构建：A/B/C×motion/gated×三fold×三seed×七比赛共378项，加PT bbox/static各七项，共392项。已有输出或partial拒绝覆盖/隐式恢复；当时尚未冻结/预飞，之后已按上述真实边界完成正式执行。
- 原冻结v10的单帧scope适配器、TrackEval纯函数与原v8断档规则直接引用，原关联数值/阈值/分配不改，sequence/game不取别名。新C独立v2加载，A/B沿原加载器，不把旧权重追加训练。
- 断档注册候选只读取共享raw检测与评价GT，在追踪结果前登记全部事件。无GT坐标的公开登记收据只存计数/来源引用，追踪进程只加载该收据；含端点GT坐标的完整账本只由登记/评价读取。GT ID0保留，DO_PREPROC=False，未匹配预测不丢弃，零事件恢复率保留null；这些不是物理遮挡标签。
- `substitution_tracking_analysis.py`已实现392项完整性门禁、全部原结果及配对单元CSV，缺一项不输出部分汇总。21类配对保留所有63个单元，再每场均9项、七场等权；主motion/次gated及B−A/C−A/B−C不改，PT差值另作次要描述，五指标区间均保留。不输出等效/非劣效标志或据区间选结果。

6项CPU针对检查通过，包含完整矩阵、配对单位、缺失/重复/非有限拒绝、合法ID0和实际launcher链。独立`model_loading_frozen_a02/config.json` SHA `e70e39f3bf5a5f2c6fbd631dda9694752dfb314f38846422471b9bf24057c2c0`，两文件bundle `code/4bd25a2f518a9a3323888669cc765c3db30de679235384ca8c952f050a0835df`实际CPU加载A/B/C各motion/gated共6个已有模型、核对原初始化及同架构相同推理适配器，并用原trainR特征作前向接口探针。`model_loading_diagnostic_a02/receipt.json`终态`complete6_ABC_model_loaders_CPU_adapters_verified`；优化更新0、新比赛处理帧0，不是新模型准确率或392项追踪验收。

首个CPU加载诊断a01因新封装给旧B加载器传入空配置，缺`training_protocol`而退出。新增回归先实际复现，再仅补传原训练协议引用，a02通过；a01旧bundle/目录和`failed_root_a01.json`保留，无训练更新或模型改写。冻结的C训练与活动下载源码均未修改。

本机`Saved/ResearchBuild/freeze_seven_match_prediction_a01.py`及后续追踪冻结助手已在真实输入/预测/退出边界实际依次执行，不再重跑。它们保留完整4790帧ledger、GT/seqinfo/物理路径、冻结源码和关键收据，不重复媒体hash或成功图解码。历史CPU准备与正式完整效果验证分别留证，不重启已完成实验。
