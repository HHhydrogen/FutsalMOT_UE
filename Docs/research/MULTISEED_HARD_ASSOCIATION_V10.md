# v10：独立运动、困难事件与未观察比赛

更新：2026-10-26。用户已授权本阶段；本文是结果出现前的数据/实验意图，**不是UE运行或GPU训练准入**。先完成新源短样、完整采集和预测，再冻结执行协议。旧v8/v9/绿色A/B保持原字节，不重启。

## 已知结论与问题

绿色球衣B在三个已观察开发比赛中，相对纯R的AssA宏均增加1.1078个百分点，相对预训练bbox追踪增加5.6404点；仍低于强motion_RS 0.2279点。当前学习的是固定预训练感知下的关联器，不是Pose头精度提升。支持有限合成身份监督作用，不能认为合成样本与真实样本等价：尚未做额外1000真实窗口对照，且RS比R有额外计算和pair监督。

本阶段重点：新增运动及困难样本后，**gated Pose能否在强motion_RS之上带来登记增量**；同时报告RS−R和RS−PT。更自然的图像或更多seed不是成功标准。

## 数据阶段

既有1048绿色B保持只读；新增1042、1044、1131三个原GRF运动seed，每seed独立300连续帧、四相机、原生4K/10FPS，计划新增3600RGB/mask及36000逐视角人物Pose。新增seed曾用于早期位置试产，不称全项目从未使用；它们相对于本轮此前只用1048的身份监督提供独立运动。机位与人物不计作独立episode。1102仍为synthetic_dev，不训练、不按模型结果挑配色。

`tools/research_ops/v10_motion_sources.py`只读原1800帧源和v1活跃范围，以固定几何规则选一段，不根据模型成败筛选。CPU已选1042 `[152,452)`、1044 `[383,683)`、1131 `[565,865)`；分别有9、5、6个根轨迹交叉proxy事件。这不是图像交叉、实际检测断档或物理遮挡的数量。

选择规则：父活跃范围内所有300连续帧，至少4名外场速度≥0.5m/s覆盖80%、低运动连续≤3秒、至少4人跨度≥1.5m、速度≤12m/s；3秒原源邻域至少4人跨度≥1m的连续不足≤3秒。根轨迹距离≤1.5m且前后各0.2秒相对位移向量内积<0记交叉proxy，同pair间隔≥1秒。按proxy数、近距离pair帧数、较早起点依次排序。阈值不是比赛语义真值。

CPU收据在`Saved/ResearchBuild/v10_motion_sources_a01/manifest.json`。前缀保留原0至end历史，不把所选段重基为0；原full trajectory/meta/appearance SHA、旧活跃范围、七模型标定、固定相机均保留。仅复用原appearance v1 Jersey/Shorts分配，不新增随机器或重抽模型/肤色，不接号码WIP。绿色使用既有独立floor seed/catalog，序列固定。

独立v10契约、计划、建源和串行入口已实现：`prepare_multiseed_v10.py`、`pose17_multiseed_v10_contract.py`、`pose17_multiseed_v10_sources.py`、`run_multiseed_v10_serial.py`。旧服装共用门禁提取为参数化内部函数，旧入口仍固定原两seed；v10通过独立schema、完整源SHA、非零源时间和新package显式路由，不伪装旧身份。3项v10检查与3项旧绿色契约回归通过，三个实际源的0至end原字节、十球员/球三维坐标、时间及标定已核验。

真实UE已创建并保存12个全新源Sequence，范围分别为`[0,452)`、`[0,683)`、`[0,865)`，捕获仍为登记的300帧子窗。`Saved/AppearancePlanning/multiseed_v10_a01/P2_sources_prepare.json`记录每轴关键帧、速度轨道、CameraCut和资产SHA，原地图/canonical Sequence/15Actor不变；建源Editor本次14:33:23正常Exiting/closed并确认进程退出。此证据只证明源已构建，不等动态短样验收。

三seed×四cam×3帧短样已真实完成，共36RGB/mask/360人物Pose。根agent已逐一查看三张四机位及四角色总览：1042外场白/红、1044黑/红、1131黄/红，门将按原四role独立分配，草地分别冷绿/深绿/暖绿。原生逐帧材质读回、mesh、相机、地板与角色恢复通过；36EXR共1454751354字节消费后退休，最后UE本次14:42:02正常退出，控制器及消费者均已退出。`Saved/AppearancePlanning/multiseed_v10_a01/short_acceptance_root.json`保存限定用途的根验收；视觉检查不等Pose准确率或物理可见性验证。

短样的独立机位world并非全都逐值一致：1042最大差0.0171毫米，1044为7.0251毫米，1131为0。1044差异局限于源帧383–385的R0关节姿态：actor/visual根变换、warmup计数及帧内采样版本相同，但bone/refToLocal不同；具体成因未证实。将差异投到实际相机，最大约1.2334像素。保留各机位原值，不平均、不改写为exact。当前准入仅用于逐视角身份/实例框监督，关联器不输入投影GT Pose，也不融合跨机位3D；不能据此声称同步多视角Pose真值。完整数据发布需如实汇总该差异，不套用旧A/B工程阈值伪装配对一致。

完整阶段为12个单机位单位，共3600RGB/mask/36000Pose。分阶段准入由`freeze_multiseed_v10.py`默认只读、显式冻结，消费上述根短样验收。沿用已验串行采集→本次正常quit→6CPU后处理→精确退休EXR，12线程/队列8不变；禁止渲染/导出加速工作。媒体只在G Dataset独立版本，D Saved只元数据。短样通过不等完整采集或训练完成，完整批仍按实际state和收据判定。

完整批于14:54:56唯一启动，权威状态为`Saved/AppearancePlanning/multiseed_v10_a01/control_full_a01/state.json`。独立发布工具`tools/appearance/publish_multiseed_v10.py`通过4项纯CPU元数据夹具：十二单位同卷移动和原索引字节保留、非exact world如实报告、活动控制器拒绝、world篡改在移动前拒绝、未知partial不重放。只能在十二单位全部完成、每次正常退出/EXR退休且真实控制器退出后，先运行默认只读计划，再显式`--publish`，目标为`G:/FutsalMOT_Dataset/v4_pose17_multiseed_green_a01`。发布对每seed四条world流各读一次，保留所有机位原值、实际view及来源SHA；不重读巨大的原生明细、不审计媒体像素、不复制4K。intent/逐项移动journal/complete及独立relocation保留历史来源路径，发布仍不等训练准入。

上述完整阶段现已真实闭合：12单位3600RGB/mask及36000人物Pose，3600EXR共144520931344字节已退休，最后UE于15:59:36正常Exiting/closed，采集控制器及所有UE实际退出。默认只读发布计划通过后，十二stage已同G卷移动到目标；dataset SHA `1b7386b4275b3101a1a4a4a9e68d360b618b29d72db0dc66873ebdab36a3e251`与`_publication_a01/complete.json`一致。单次四流比较在三个完整运动各3000记录/机位均逐值exact/max0；短样差异原记录及未知成因不撤回，也不据此声称根治或物理可见性。`full_acceptance_root.json`绑定发布/来源/退出/清理，source900时间样本不按四机位扩成独立运动。

## 公平窗口与方法对照

共享预测的CPU来源契约`tools/research_ops/v10_prediction_inputs.py`通过4项针对检查，CPU阶段实际读取既有1048绿色B组及两场val的6源/2325帧索引，并检查首尾图片存在；该检查未解码或运行模型。完整目标是四seed×四cam的4800合成帧，加1125验证帧，共18源5925帧。每个绿色来源均重新运行同一冻结PT原图检测，旧1048蓝框缓存不复用。新序列UID命名不带旧blue；`frame_index`零基、`frame_number`一基、PNG零基、JPEG一基分别明确，原运动源帧与源时间另存，不能以本地序列时间覆盖源偏移。进入模型的帧元数据不含GT身份/框/Pose，合成标签和真实GT引用只供预测完成后的身份标签或评价。CPU收据为`Saved/ResearchBuild/v10_prediction_inputs_CPU_a01.json`，本轮实际完整来源预飞和GPU状态见下。

独立模型执行入口`tools/research_ops/v10_prediction_cache.py`另有5项CPU检查通过：完整十二单位/源限制门禁、实际进程身份/PID复用、原检测截边与顺序、缺Pose拒绝且无效Pose保留、显式配置SHA不符时拒绝。它绑定原v8检测参数及冻结裁剪Pose函数/预取字节，先独占新输出再加载模型，异常保留partial和失败收据；不回填旧Pose、不按GT筛检测。配置必须在本次完整发布和UE实际退出后冻结，绑定新旧成品/发布/最终采集、新比赛下载/解码/独立身份验收及原PT数值来源，默认只读预飞后再显式`--execute --config-sha256`。CPU收据为`Saved/ResearchBuild/v10_prediction_cache_CPU_a01.json`，实际准入和执行状态见下；CPU通过不等最终预测或训练完成。

实际发布后已将必要5文件安装到D研究执行bundle `3f8566583ff07e60665c60fd4ec28cd03e5e8633796c9da8ad83e997fe09bc92`，原数值裁剪/Pose与OrderedPrefetch复制自旧冻结bundle，字节SHA不变。新配置`pose/multiseed_v10_a01/prediction_frozen_a01/config.json` SHA `6293539cdd8dfc35b6f3459f6ae27c2bc5fa067a9fda6b547b9d4efe69cd8833`绑定新旧成品、真实采集/发布、两场val身份/解码链和原PT来源。18源/5925帧默认只读预飞已实际通过，16:09:05唯一启动GPU共享预测并已越过首机位50帧；输出`shared_inputs_a01`及原stdout/stderr保持独立。只有最终manifest为`complete_18_sources_not_training_authorized`且实际进程退出才算预测完成；当前不等新窗口池或训练完成，优化器更新仍为0。

计划两个新S采样池：四运动seed平衡采样；同源下增加交叉/实际检测断档的困难采样。每池1000唯一窗口、每seed250，实际标签/pair另计。先从固定预测与GT标签登记事件，再冻结具体配额；不足时如实报告，不能复制UID填额、把请求的时间间隔称检测缺失，或按下游分数补样。受控历史缺点若采用则另标干预，不冒称自然遮挡。

结果前采样规则已实现为独立CPU候选`v10_synthetic_windows.py`，4项针对检查通过，尚未实际构建新池。两池每seed250，均按原四camera×五gap的20格分配12/13个窗口，保持机位/间隔配额相同。平衡组每格取最小窗口SHA；困难组每格按“自然检测缺失proxy→图像实例框重叠proxy→候选数→最小SHA”排序。自然缺失要求连续有效实例GT中间2–29帧没有任何IoU≥0.5的raw框，端点有检测；GT匹配冲突不冒称检测消失。重叠指查询/另一身份的可见实例框IoU≥0.1，不能当物理遮挡真值。所有事件为独立账本，选择后仍报告实际事件数量。困难事件不足时，在同格按登记顺序取其余合格窗口并如实报告，合格窗口本身不足配额就失败；不复制UID、不按Pose质量/训练损失/追踪分数挑样。沿用原v8唯一IoU身份标签、运动候选门槛和窗口定义；源GT只取身份/实例框，不输入GT Pose，val从不入训练。根CPU收据为`Saved/ResearchBuild/v10_synthetic_windows_CPU_a01.json`，实际完整预测后再冻结构建准入。

每池分别训练强v8 motion、v9同名义参数motion_residual、v9 gated Pose。三原开发fold×三训练seed×三方法×两池，计划54个新RS，每臂1000实际更新、完全相同3000R窗口同序、另1000S；FP32 AdamW lr0.001/wd0.0001、独立meanR+meanS/3、预取2、last1000，不选best。总计划54000更新/162000R/54000S窗口，不是独立图像数或等计算预算。

纯R和单1048 S参考仅在数值源码、输入、初始化、标准化及曝光表完整一致时只读复用并登记新增更新0；未证明一致就建立新的公平控制，不能追加旧权重冒充同预算。两个采样池各自的motion与Pose必须共享S UID/标签/顺序。主结论同时看gated_RS−强motion_RS、gated_RS−同容量motion_RS、RS−R和RS−PT；不只展示胜过较弱参考的结果。

## 新比赛验证

SoccerNet当前官方train的57条序列只有game4/6/9，三场均已观察；同场换片段不算独立比赛。候选使用[SportsMOT官方val](https://github.com/MCG-NJU/SportsMOT)，遵循其非商业研究许可，仅作开发验证，不增加R训练预算。先登记未观察源视频及实际比赛身份，核对旧三场无重叠，再提共享固定PT检测/Pose；最后测试集及test包仍不读取。

公共传输镜像Lekim89/sportsmot已固定revision `2993b47d4369fa70ea70afc8bc63b5964e556a81`，45条val名称与官方清单完全一致；这不是官方像素SHA证明。选择规则在看新图/模型结果前登记：标题明确足球、不同比赛的源视频按ID排序取前两场，再取该源在val中最早clip。少于300帧拒绝，最多前750帧，不重复补帧。已固定并看过两张首帧及旧三场对照：`v_2QhNRucNC7E_c017`为2015/16 Dortmund–Schalke，450帧，首帧记分牌16:26/0:0；`v_G-vNjfx1GGc_c004`为2015 Norwich–Ipswich附加赛，675帧，首帧77:23/3:1。源标题、记分牌和场地/球队服装与原三场不同；原SoccerNet球队名匿名，不补造其精确球队名称。

1125帧已完整下载，实际下载进程退出；逐帧真实JPEG解码为1280×720 RGB，25FPS元数据及GT9列/帧号/唯一身份/正框宽高检查通过。两段分别6622/8137条GT，21/20个身份，均存在合法ID0；不删ID0、不裁剪标注、不按GT过滤预测。`D:/projects/FutsalMOT_Research/public/sportsmot_val_v10_a01/identity_receipt.json`保存结果前身份核验，`decode_validation_a01.json`保存实际输入验收；固定`download_config.json` SHA为`f71492e133c087324a54cddae16304b3005b15433f731f75403dded473668092`。仍未预测或评价，真实训练曝光新增0，不读test。SportsMOT仅标球员，后续评价适配不伪造SoccerNet gameinfo。

新比赛是后续未调参开发验证，不叫最终盲测。原三场留一仍完整报告为次要开发证据。新两场主门槛沿用AssA均差≥0.5点、至少2/3训练seed正、两场比赛均差均非负、HOTA均差≥0、IDF1下降≤0.5点；若最终可核验比赛数改变，必须在预测/结果前另签协议。三fold或训练seed不计作独立比赛，不能直接声称真实五人制泛化。

## 全过程记录与阶段完成

全部新训练接入[训练全过程规范](../operations/TRAINING_RECORDS.md)，保留每步loss/LR/梯度/真实及合成UID与pair、0/每50/最终模型+优化器+完整RNG、环境、日志、全部评价及负结果。记录代码也纳入执行bundle和准入SHA。下述实际接入验证和首正式1000步已闭合，不能将它们替代全部54臂及追踪验收。

## 共享预测、窗口与完整记录训练的实际状态

18源5925帧预测已全部完成、实际进程退出，manifest SHA为`63d9e38e436f7749a25fbe69665b5fd912385fbf6d4ae5cfe2bc0cd46cee503d`。4800合成图共有54875个raw框、26474个几何规则通过；1125验证图共有19090个raw框、14346个几何规则通过。这些是覆盖统计，不是准确率，GT不参与检测/Pose推理或预测筛选。两场新比赛预测已完成，尚无追踪评价结果。

两池已按事前规则真实构建，`pools_a01/complete.json`及根收据`Saved/ResearchBuild/v10_pools_complete_root_a01.json`已核对1000唯一UID、四seed各250及80格12/13配额。balanced/hard_enriched的自然gap窗口分别0/26、实例框重叠窗口205/996、全部pair为5143/11845、已知pair为2799/3236；全部874个自然检测缺失proxy事件另存，包含未选事件。池间监督pair预算不相等，同池三方法使用完全相同UID/标签/顺序；不将困难构成变化当模型收益。

独立七文件训练bundle为`D:/projects/FutsalMOT_Research/code/3fe69befcd6c1aa3a552a55626c47b47c68af139409e77796893eb813ed5f02a`，新协议`training_frozen_a01/protocol.json` SHA为`2a1fa8ecd0b48993289c859ec6e83c36bf987e9d7de9ccf44820c4a86f7be575`。`v10_runtime.py`只读加载原冻结v9/v8数值，R池/标准化/质量尺度及3000R曝光表逐值复用，独立新身份不伪装v9。54臂从新初始化训练，不追加旧权重；27个纯R参考的来源/初始化/预算另绑定，历史记录缺项如实保留。

正式前对强motion、同容量motion_residual及gated各执行原循环和记录循环的同一3R+1S CUDA更新，loss和所有模型张量逐值一致，完整优化器/RNG检查点读回通过。6次诊断更新另记，不计入54臂预算。正式唯一控制器17:03启动，首个正式1000步已通过独立加载及21份定期完整检查点逐项核验，`control_a01/first_run_end_to_end_gate.json`为`complete_first_formal1000_records_verified`，优化器重放0。

固定54矩阵现已全部完成，`control_a01/driver_state.json`为`complete_54_recorded_train_wait_independent_tracking`，实际训练进程已退出。独立`postrun_audit_a01/actual_budget.json`逐步核对54000更新/162000R/54000S窗口、1134份完整模型/优化器/RNG/曝光链，同池三方法S顺序及all/known pair一致，跨池原R与初始化一致。实际R all/known pair为608040/469476，S为458676/162945；6次诊断更新另计。首臂或全部训练闭合不代表追踪收益。

逐步loss/Rloss/Sloss/LR/gradL2/耗时、真实及合成UID/epoch/all及known pair、链、每50步完整状态、环境和原stdout/stderr实际保存在D研究目录。训练原协议/源码/数据保留，后续追踪只读，不追加更新。

论文训练归档`paper_training_archive_a01`已实际导出全部54000步CSV、54臂预算CSV及六图的PNG/PDF，展示原损失和向后50步均值、保留全部seed；`complete.json`绑定原run来源。它不平滑评价结果、不挑检查点，损失曲线不替代追踪效果。

## 五比赛真实自由追踪的独立准入

`tracking_frozen_a01/config.json` SHA为`f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1`，独立七文件bundle为`f3098416f1d5d8063de9d2ffcaaea70e5e23e481a6b5ec96868a16acc7349ab7`。真实默认只读预飞后，17:33:28唯一启动`v10_tracking_control.py`，CPU执行/GPU禁用。完整矩阵253项：五场×PT_bbox/PT_static_pose共10参考；54个新RS各评价一个原heldout及两新比赛共162项；27个纯R模型同样各三场共81项。纯R实际加载原v8/v9完成模型/初始化/预算，来源引用新增更新0，历史记录缺失不补造。

原tracker冻结SHA为`7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688`。新适配只以AST替换一条三比赛/750帧域守卫，显式准入真实五比赛及450/675/750帧；实际sequence/game原值不变，其余整棵数值AST保持相同。原750帧上PT_bbox、PT_static_pose和learned三个模式的全部输出及audit逐值相同，`tracking_numeric_validation_a01/receipt.json`为CPU实际证据，不读取新比赛追踪结果。原低分stage、候选、门槛和代价不变。

`evaluation_inputs_a01/gap_registry.json`在新比赛追踪结果前已实际登记1353个可信断档事件，其中旧三场956、新两场397。采用原v8双向唯一IoU≥0.5可信端点、连续有效GT、缺2–29帧/端点间距≤30；可信匹配缺失可以包含raw歧义，与合成池“无任何raw框”874事件的自然缺失规则不同。全部注册事件作各序列分母，缺预测/歧义/换ID均计失败；不是物理遮挡恢复。

新SportsMOT直接保留合法GT ID0，无伪造gameinfo；原三场仍按player/goalkeeper mark1口径，TrackEval1.3.0和`DO_PREPROC=False`保持，全部预测行保留。6项针对CPU检查含真实ID0/额外未匹配框夹具和单序列/COMBINED Count边界。先完成五场10项PT真实评价门禁再继续学习臂；10项现已通过，模型增量仍待全253项分析。终态必须`complete253_tracking_and_analysis`、253齐全、真实分析complete及控制器身份退出，不以进程存活/无报错冒充完成。

阶段依次报告：源/预算与新比赛登记；UE短样；完整采集/EXR退休/正常退出；共享预测/窗口；训练与实际预算；全部真实追踪与主比较。新数据或新场景没有收益也完整保留，不调测试、不挑seed/阈值/比例，不自动续训。
