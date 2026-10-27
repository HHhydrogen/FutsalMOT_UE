# 十二开发片段零更新政策账本结果

2026-10-27。按[事前协议](TRACKING_POLICY_LEDGER_A01.md)实际完成；19项盘点/数值/调度CPU合同及真实NumPy2 FP32边界通过，独立终验器8项回归和真实全量终验通过。没有新增训练、模型推理、自由追踪或TrackEval，原成绩未改变；最终116/187及test包继续封存。

## 实际范围与完整保留

原三场、旧两场和已观察七场共12唯一缓存、8165帧、149245 raw框及113020 GT人物帧标注行。只读原OC12/PT bbox12/强motion_RS90共114份MOT，对应76315个逻辑单元帧（包含无输出帧），936212条原发出记录和15924个可观测ID发出片段；训练单元不是独立比赛。原GT/raw源分母每源只计一次，不乘114或90。

每源实际生成raw账本、GT机会账本、输出账本、逐帧CSV及发出轨迹CSV。所有无候选、双向歧义、空输出帧、负结果和无法还原的状态保留。父汇总完整12源/114单元/36方法×比赛/9面板行。后验GT仅沿用原纯加载器的已登记标注口径，SportsMOT ID0保留；不向追踪或模型提供GT。

## 高门槛排除了哪些几何机会

每个GT人物帧以同帧连续坐标IoU≥0.5检查是否存在任一raw候选。下表先逐场计算比例，再按比赛等权；不是把所有GT行当独立比赛，也不是新DetA、准确率或收益。

| 面板 | GT人物帧总数 | 任一`>0.6`候选 | 任一`>0.25`候选 | 新增几何机会 | 新增机会行数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原三场 | 31659 | 61.0205% | 87.9038% | +26.8833点 | 8681 |
| 旧两场 | 14759 | 67.2586% | 91.4292% | +24.1705点 | 3532 |
| 已观察七场 | 66602 | 52.1307% | 88.4358% | +36.3051点 | 23893 |

例如，七场里不少已标注的人在某帧只有0.25至0.6的检测框，默认OC门槛不会把这些框作为高分候选。账本支持“有效检测保留是重要的待检验差异”，但不证明门槛解释全部成绩差距，更不能把新增机会直接当恢复了正确身份。

完整七桶raw计数：低于0.1为0、等于0.1为0、(0.1,0.25)为30532、等于0.25为0、(0.25,0.6)为49039、等于0.6为0、高于0.6为69674。FP32等号边界虽然本轮计数为0，协议和真实NumPy准入仍显式保留；OC严格`>`和ByteTracker的`>=0.25`不混写。

新增分数段并非全部可靠。以下以每场该分数段raw框为分母，分别计算raw↔GT双向唯一关系后比赛等权：

| 面板 | (0.25,0.6)原框总数 | 双向唯一几何对应 | 无IoU≥0.5候选 | 多候选或反向冲突 |
| --- | ---: | ---: | ---: | ---: |
| 原三场 | 12176 | 55.3996% | 22.4745% | 22.1259% |
| 旧两场 | 4735 | 56.6268% | 15.2090% | 28.1642% |
| 已观察七场 | 32128 | 53.8809% | 18.8340% | 27.2851% |

约44%至46%的该段raw框仍存在无候选或歧义，不能宣称全部有用；“无候选”也不能直接认定绝对误检。原标注范围、定位偏差和重叠都会影响这个代理。GT只给后验标签，不帮助反向挑选raw或消歧。

## 现有输出覆盖差异

强motion先在每场平均其全部匹配fold/seed，再按比赛等权。左侧为实际MOT每源帧平均发出框数，右侧为输出↔GT双向唯一几何对应数除以GT人物帧数；二者都是后验描述，右侧不是TrackEval DetA。

| 面板 | 方法 | 每帧发出框数 | 输出与GT双向唯一几何比例 |
| --- | --- | ---: | ---: |
| 原三场 | OC默认 | 7.8364 | 50.9356% |
| 原三场 | PT bbox | 13.2858 | 79.8376% |
| 原三场 | 强motion_RS | 13.7013 | 81.2532% |
| 旧两场 | OC默认 | 8.3548 | 57.2441% |
| 旧两场 | PT bbox | 12.4904 | 82.8845% |
| 旧两场 | 强motion_RS | 12.9093 | 84.7145% |
| 七场 | OC默认 | 6.1275 | 39.5719% |
| 七场 | PT bbox | 12.3727 | 74.2162% |
| 七场 | 强motion_RS | 13.0318 | 76.6117% |

例如布莱顿片段，OC实际发出2272条，强motion九训练单元均值6392条。这个差异与已有DetA差距一致地提示覆盖不同，但不能把多发框自动当好结果，也不能由MOT断言每个未发出框究竟被哪条内部规则压掉。

## 确认与生命周期能还原多少

官方冻结core的静态规则是当前帧更新且连续命中满足min_hits，或处于最初min_hits帧；默认`byte=False`。现有冻结learned tracker的高分/新建门槛为0.25、低分0.1、buffer30；原ByteTracker静态快照显示首帧和后续确认、低分维持及激活后发出规则不同。

MOT没有保存每帧内部状态，因此出生、确认、lost、删除和抑制原因全部`unknown_from_MOT`。首次发出不叫出生，同ID断后再发出不叫物理遮挡恢复。输出↔raw分数仅在独立双向唯一几何邻近时记录代理，无法据此恢复内部绑定。当前ByteTracker源码SHA为`05545b07876311937097fdd61a47cfba7dc09fd3695fd35603eb61be09c0b40d`，只是本次安装快照；未找到旧实验逐文件SHA绑定，不能补造历史冻结证据。

## 论文含义与下一单因素

本阶段增强的是对照解释和可复核性，没有提高模型AssA。可以写：同raw缓存条件下，官方默认core与现有方法存在明显的候选保留/输出覆盖差异；在本开发范围，大量GT几何机会位于默认0.6门槛以下。不能把此前整体领先直接当作孤立关联能力、Pose或合成监督的优势，更不能称超过学界SOTA。

下一优先项应为独立登记OC唯一`det_thresh:0.6→0.25`，而非马上扩充数据集或加训练轮数。0.25来自此前已固定的对照门槛，不是扫描本12场后选best；官方版本、N5/FP32输入、全部帧、max_age/min_hits/IoU/delta_t/inertia、`byte=False`、原ID及输出规则均保持。先做新配置的输入/数值准入，再在同12开发片段一次自由追踪/评价，与原OC0.6进行配对，保留3/2/7分面板、全部负值、AssA主和HOTA/IDF1/DetA/MOTA次及原gap分母，沿用比赛等权t95/固定bootstrap/逐场留一。它是已观察开发范围的机制消融，不是新盲测；后续独立确认另锁来源身份，测试不解封。

本账本配置不启动这个候选，也未把它记为已完成。若降阈值后DetA恢复而AssA仍弱，再定位关联/确认因素；若错误明显增加，报告该负结果，不继续搜索门槛。若整体差距显著收窄，应相应收缩“模型领先”措辞。只有明确的数据缺口证据出现，才定向补数据。

## 实际执行、终验及来源

两个独立后验worker各处理6源，正常join/exit0。控制器至全汇总53.7190秒，采样进程树RSS峰0.1959GiB、最低可用RAM13.3102GiB、commit余量25.4618GiB；不含前置冻结、独立终验和退出尾部，不是视频端到端FPS或新串行提速证明。没有加载Torch/Ultralytics/FilterPy/TrackEval模型模块，没有新图片/感知缓存或GPU工作。

独立终验逐行核原MOT/账本、FP32七桶、完整候选图、113020机会分母、36/9汇总及真实CIM退出；不再读原缓存、GT坐标或媒体，不重几何坐标匹配，不重算TrackEval。终态为`complete12_sources114_MOT36_summaries_all_policy_ledgers_and_exit_verified`。实际新数据执行/终验均首attempt通过，无成功重放；冻结前发现的两个metric收据schema差异和失败join路径已补合同，测试调用曾因工作目录造成一次导入失败，改为从脚本目录运行后19项通过，没有运行失败的研究任务。

- [冻结配置](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/frozen_a01/config.json)，SHA `14dc1c193cd0149ff821530e29deacc043be048c4d403a3b516ef3fc7ce5ab97`，三文件bundle `70a399c65ff8cf7f2ef7090a0739ab161ff5b59b338c419f54e0c6c1238645f7`。
- [来源盘点](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/inventory_a01/manifest.json)，SHA `889a5a96e10dbbb9401481a19366c01395a158f3293ee47eef154ea38bc976b1`；没有读取GT或预测缓存。
- [完整分析报告](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/analysis_a01/report.json)，SHA `9e5be02c126c614f89bf17ea493baafa7762d1ff993d62e0174bd978c36e6ddf`。
- [12源CSV](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/analysis_a01/source_summary.csv)、[114原单元CSV](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/analysis_a01/all_units.csv)、[36方法比赛CSV](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/analysis_a01/method_sequence_summary.csv)、[9面板CSV](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/analysis_a01/panel_summary.csv)，完整五账本位于各`sequences/<原sequence>/`。
- [独立终验](D:/projects/FutsalMOT_Research/pose/tracking_policy_ledger_a01/final_verification_a01/receipt.json)，SHA `aaa5c2bd2161dbb9c0e2ec5e2c8dcf4ac9ff44e984035c2c2169cf88eff45226`，终验单文件bundle `ab8a6ce11cf853bd36cdbd326ed24731febdc3bc4f2471ea1d95e9166a80beec`。
