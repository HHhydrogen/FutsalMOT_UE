# R候选评分资格mask：唯一因素候选a01

2026-10-29。承接[已独立闭合的资格/弱标签诊断](STATE_LABEL_ALIGNMENT_A01_RESULTS.md)。此文登记下一项实现与准入条件，不表示正式训练或新自由追踪已执行。测试SNMOT116/187/test继续封存，原未校准strongmotion_RS保持研究主参照。

## 只改变的因素

同一3000R窗口、原UID顺序、history、候选、原0/1/null标签、九曝光表及R/RS配对保持。对每窗原known候选按原顺序拼接，每step三个R窗仍合并为一次前向，逐pair BCE仍先用原`reduction=none`计算；只在loss归约时选取原R teacher概率前评分资格为true的known候选，再在该窗内求均值。三个窗口始终等权平均，不改为只平均非空窗。

全部known都无资格时，使用原loss片段的带图零，所有参与参数须得到实际zero grad而非None；不重采样、不跳窗口或优化器step。AdamW的动量、weight decay及1000次更新仍照常执行。此规则同时改变有效监督及其窗内重新归一权重，不能宣称同有效标签/梯度/FLOPs预算。

mask仅由原stage、active、enabled决定，不读取label选mask，不由概率或损失选mask。正式侧表须逐值绑定原window UID、teacher模型/首seed20261024、fold/sequence、源job/frame/stage/row/trackID、history UID和全部candidate UID；missing/unknown资格不得猜False。当前已登记的是候选清单，还须由新输入冻结器输出并独立核验完整来源侧表，不热改原清单或池。

S仍直接使用原known-pair BCE窗均值及系数1/3。不合并无known正例+unknown整窗过滤、anchor代理过滤、CE/null logit、其他loss系数、history/Kalman/候选推理政策、Pose算法伪标签或新增合成数据。

## 明确绝对配置与数据预算

| 项目 | 事前配置 |
|---|---|
| 输入/网络 | 每pair194维，原baseR normalizer后170个Pose列置0；194→64→32→1，两个ReLU，14593个全部可训练参数，标量logit；无RGB图像输入、无epoch扰动增广 |
| 数值 | FP32，AMP关闭，无编译、EMA或checkpoint best筛选 |
| 优化器 | AdamW，LR0.001，weight_decay0.0001，betas(0.9,0.999)，eps0.00000001，amsgrad=False、maximize=False、foreach=None、capturable=False、differentiable=False、fused=None；已读本机Torch2.6.0原构造默认，正式准入核实际param groups |
| 矩阵 | R/RS×game4/game6/game9×seed20261024/20261025/20261026，共18新臂；不挑seed/fold |
| 每臂 | 初始化用原对应seed，1000次更新；每step3R，累计3000R调度；RS每step另1原v10balancedS、累计1000S，R无S；loss=mean(3个R窗mask-BCE)+S-BCE/3 |
| 全18调度 | 18000更新、54000R窗次、9000S窗次；原R all/known pair计数764370/634320，原S46287/25191保持调度记账；尚非实际新训练 |
| 新有效监督预期 | 三fold唯一有效known2618/1277/2258；每臂三遍为7854/3831/6774。全18有效known110754=正19656+负91098，非空R窗次36126、空17874；unknown不参与loss。不得以这些有效计数覆盖原all/known字段 |
| 预取/缓存 | 原prefetch2/256MiB；复用已有有界缓存；不为该因素裁剪原known前向batch或另改并行数值 |
| 检查点 | step0、50、100、150、200、250、300、350、400、450、500、550、600、650、700、750、800、850、900、950、1000，共21份/臂；完整模型、AdamW、Python/NumPy/TorchCPU/TorchCUDA RNG；只用last1000 |
| 推理绝对门槛 | high0.25、low0.10、new0.25、buffer30、match0.80、lowassign0.50、unconfirmed0.70、fuseTrue；原dt1.2秒、面积比0.25至4、中心2、概率0.50及冻结源码数值边界不改 |

以上预算是候选协议预期；新训练执行前须另冻最小SHA bundle及JSON数值协议，不能直接在旧训练脚本/配置热改。每step原loss/LR/grad/UID/epoch/all-known pair链及完整checkpoint/stdout/stderr/失败继续保存，并新增逐窗/逐步effective known/positive/negative/unknown、排除known、空窗、mask UID/SHA链。旧Journal要求原known>0，不能把effective0写进旧known字段或用旧审计schema伪装通过。

## matched-control与准入

原aligned-BCE十八臂作为条件matched-control候选；其原训练协议SHA `2acc7642109c317b9ca694d3649a864c5553e177f20425d24726de1781c7d3c6`、训练完成根SHA `62646594150716226b4cb90087731b8d2c76fb836bd22a3218a776031ebf5a33`、独立预算SHA `d551bb377a8d33b6f454fa5f119723c06c085555c85c37c55b5080f53d671212`均已闭合。这里仅引用完成证据，不重跑旧训练/权重审计。R集合CE模型不是该因素的唯一变量控制。

静态兼容只说明可能复用控制。真实训练准入必须先过：

1. 新3000侧表与原池metadata/history/UID/label精确对应，mask与已独立核验的候选资格逐值一致；输出每fold有效/空预算，拒绝partial/混teacher/未知mask，不重建池或改变曝光。
2. 全true mask在CPU及真实CUDA上与原BCE同一次前向的loss、全部参数梯度、一步模型/AdamW/RNG逐值相同，验证控制的数值兼容；不能仅比较平均loss或用模型前向次数相同代替。
3. 真实mask与独立手写窗口目标在CPU/CUDA逐值核对，包括三R全空时zero-grad与AdamW动量/weight decay、S原函数及1/3系数不变。玩具CPU fixture不替代实际输入/初始化的一步准入。
4. 先完整一个1000更新单元与21检查点/全部新记录及真实退出验收，才启动其余17；诊断更新另记，不混正式18000。首单元产物直接继承，不重训。

任何字段/数值不匹配先根因核查，保留失败另attempt，不修改旧冻结代码/结果或自动扩大到36新臂。若控制不能逐值匹配，另立明示等预算控制协议，再执行完整配对。

## 正式评价口径

新18模型各10允许开发来源，共180自由追踪任务；复用原180 aligned-BCE及原180 strongmotion来源，结果前另冻实际matrix/分析。全部12场均已观察开发，原3/旧2/七场三个面板分开，先各方法绝对AssA/HOTA/IDF1/DetA/MOTA，再比赛内均匹配fold/seed后的配对差值。主目标新RS−原strongmotion_RS；因素作用新RS−alignedRS；另新R−alignedR、新RS−新R及相对aligned的合成增量交互，5族×3面板×5指标=75未校正描述区间，gap另15。t95按独立比赛数df2/1/6；bootstrap10000次、seed20261029、Python MT19937 randrange/线性分位；逐场留一、所有负项/zero/null/fold/seed留存。实际追踪协议签字前不启动新追踪。

本因素只涉及强motion关联器，不是新Pose能力验证。不以CI含0称相同，不设等效/非劣效δ，不因对退化版略高就称追踪提高，不将weaklabel代理当人工真值或合成数据因果。

## 当前真实实现与检查状态

候选方法、独立训练适配及记录扩展已实现为三个新文件，未修改原journal、旧冻结runtime、原池或完成结果。逐步mask accounting、known候选UID/原标签、侧表/绑定双SHA以及有效/排除/空监督计数进入原曝光哈希链；原R/S all/known字段保持原值。推理loader、正式train/controller/独立新预算审计及新JSON训练执行协议尚未冻结，不得直接启动训练。

已过25项针对合同：方法4项metadata+4项真实Torch合成CPU损失/梯度+1项损失至真实记录扩展的内存集成、runtime6项、记录loop10项。loop的1000次optimizer接口和21检查点夹具使用纯内存stub，不是真实更新或checkpoint。全true loss/梯度/CPU RNG、空窗zero grad、partial手写BCE、原S/3及完整已知batch一次前向已在合成CPU模型上核查；尚未验证真实R/S输入、实际原初始化、AdamW一步状态或CUDA，所以不是正式训练准入。

合成CPU a01完成后，为补known UID/label记账字段并将空集零定义明确为`(loss_part*0).sum()`，保存旧成功a01，另执行a02必要检查；随后新增一项跨模块集成。累计17次玩具模型前向、86个玩具candidate tensor行，真实R/S数据窗口0、optimizer更新0、CUDA0、追踪/TrackEval0。全部成功/源码SHA/日志保留Saved/ResearchBuild/R_eligibility_CPU_fixtures_a01、a02及R_eligibility_CPU_integration_a01，不用当前17次前向覆盖此前诊断阶段的0前向预算。

下一门禁仍为三fold1000完整侧表及独立核验、签新训练JSON与最小SHA bundle、真实CPU/CUDA一步和记录数值准入、首完整1000更新及21 checkpoint门禁；这些尚未执行。尚无本因素新训练模型或追踪成绩，不建立提升结论。
