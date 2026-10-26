# 当前任务与下一步

更新：2026-10-26。历史过程见Git及对应运行收据；本页不保留过期PID流水。

## 当前执行：Pose机制诊断与资源替代可行性

- 用户已授权按[后续方案](Docs/research/POSE_DIAGNOSIS_AND_REAL_DATA_SUBSTITUTION_PLAN.md)实施，[首轮执行](Docs/research/POSE_MECHANISM_A01.md)已完成五场raw/后验标签/无GT形状交换库存、20例固定抽样视觉复核及额外R窗口可行性核验。可见几何有效骨架仍有错位，视觉复核不是人工关键点GT或准确率。
- 162项CPU诊断及分析19:55已实际全部结束，CIM确认全部相关进程退出；54共同强motion状态MOT/audit均与原结果一致，108关闭/打乱Pose自由追踪全部评价。新增优化更新0，独立完成链`D:/projects/FutsalMOT_Research/pose/pose_mechanism_a01/diagnostics_complete_root_a01.json`及两份论文CSV已闭合，不重复启动。
- 外部两场关闭Pose相对原Pose AssA平衡−0.062989、困难−0.001038点，打乱为−0.060679/−0.069006；作用很小且seed不稳定。同状态可信困难子集只修正1行并破坏2行；固定gate/基分支下283个错误/并列行有270个超出当前残差幅度可修正范围。这不是总体错误率或完美Pose上界，未知历史单列保留。
- 三fold额外1000未用R窗口与基础池约92%源帧重叠，仅新增101–108个源帧，不能称新增图像/标注节省。官方train57段实际只属于原三场；061/098/154非重叠片段已登记为额外R输入候选2250帧，但尚未下载图像/GT、预测、建池或训练，不作独立验证比赛。
- [残差幅度探针](Docs/research/RESIDUAL_AMPLITUDE_PROBE_A01.md)108项追踪/评价/分析及实际退出已全部闭合，`complete_root_a01.json`和论文CSV核验通过，零新增优化。上限0.5→2.0后外部Pose AssA仅+0.056140/+0.007494点，原heldout−0.201368/−0.593648；同容量motion也有涨跌，不能将相对转正当Pose本身改善。不重复启动。
- 原54份trace的候选机会审查也已完成，只读行内代理、零新推理：可信未介入且足三历史/正负候选子集中，Pose与自己关闭分支没有新增排序翻转。不是新策略自由追踪或总体Pose无用证明；下一步核验表示/信息与训练期对照，不盲目同时放宽候选、gate和损失。
- 原固定的额外R三片段061/098/154已另冻结2250帧获取准入并启动，输出`D:/projects/FutsalMOT_Research/public/real_substitution_train_a01`，不提取/用det，不模型预测或训练。A/B/C仍须另冻结4000R资源控制及更多独立比赛/非劣效精度；这些片段不是新比赛，不重启旧采集/清理，测试封存。
- 当前下载仍在大范围网络读取，manifest只在真正完成/异常时落盘，实际Name/CommandLine优先，不能据没有JPEG/manifest自动重启。已设置本聊天阶段接续，健康静默；完整数据/共享预测/额外R输入闭合后汇报并移除跟进，不能提前声称C训练/等效完成。

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

数据价值另设资源替代问题：比较R3000、R3000+S1000、R3000+额外R1000。第三组明确为4000R的独立补充对照，不混入同3000R的Pose主实验；先核验额外R来源、独立比赛、可接受性能损失界限及样本精度，再冻结执行。当前表格只支持混合模型小幅平均补充收益，不能证明合成与真实监督等效；窗口曝光减少也不自动等于标注成本减少。

本次仅交付方案，没有新训练、渲染、下载或自动跟进。全部负结果和最终测试封存边界保留，不重启旧批或安排渲染/导出性能开发。

未完成号码继续保留、不纳入当前数据或提交。每独立阶段报告真实完成证据，历史started_not_committed不当作当前故障，不重复启动已结束驱动。
