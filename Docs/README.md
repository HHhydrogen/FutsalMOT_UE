- [自由状态R窗口来源验证](research/STATE_ALIGNED_R_TRAINING_A01.md)：三fold各1000唯一R输入已闭合，下一步训练数值与完整记录准入；新训练尚未启动，测试封存。
# 技术文档索引

- [训练候选与自由状态、历史传播有界诊断](research/TRAIN_FREE_STATE_GAP_A01.md)：首seed强motion R/RS的12训练域rollout，完整三阶段/生命周期和最多60事件的30帧四分支oracle；[完整结果](research/TRAIN_FREE_STATE_GAP_A02_RESULTS.md)已闭合12观察/后验和独立终验，零合格oracle事件，未估计历史/KF效果；下一项仅准备R窗口来源对齐，非新增模型成绩，最终测试封存。

- [模型训练历史总览](research/TRAINING_HISTORY.md)：从最初bbox迁移到Pose微调、身份关联、真实资源对照和截距校准，按版本解释训练对象、动机、数据split、绝对预算/成绩与局限；完成阶段持续更新，失败和零更新诊断单列。

- [训练R截距单因素](research/TRAINR_INTERCEPT_CALIBRATION_A01.md)与[完整结果](research/TRAINR_INTERCEPT_CALIBRATION_A01_RESULTS.md)：18拟合/180正式追踪/360来源、270指标270gap配对与45+9描述独立终验全部闭合。七场R/RS AssA变化−0.1329/+0.0525点，主CI均跨0，未建立整体改善；额外18000R监督计算另列，全部负结果保留，测试封存。

- [一次有边界的错误条件分解](research/BOUNDED_ERROR_DECOMPOSITION_A01.md)及[完整结果](research/BOUNDED_ERROR_DECOMPOSITION_A01_RESULTS.md)：复用27原trace/320752行，63缺失内部来源保留unknown；真实分配准入、全部条件与112描述区间及独立终验已闭合，新增评分/追踪/SGD均0。其后唯一训练R截距校准已独立完成，结果见上方对应入口；不将条件计数当因果或性能增量，测试封存。

项目当前状态与执行授权以[根README](../README.md)、[AGENTS](../AGENTS.md)及[任务状态](../TASK_STATUS_AND_NEXT_STEPS.md)为入口。本目录按工程、生产、研究、运维集中技术说明；历史验收、候选和本机结果不能替代当前准入。

以下主要入口来自已跟踪文档的整理基线；实际是否已提交或推送以Git commit为准。正文中的历史命令、G/D旧路径和收据按当时版本理解，不能据此自动重启旧任务。未提交草稿移入分类目录不等于远端已交付。

## engineering：契约与实现

- [数据契约](engineering/DATA_CONTRACT.md)与[验证和限制](engineering/VALIDATION_AND_LIMITATIONS.md)。
- [统一仓库目录](engineering/REPOSITORY_LAYOUT.md)：Python、实验、Saved与研究环境的当前边界。
- [GPU渲染/CPU-LBS](engineering/POSE17_GPU_RENDER_CPU_LBS.md)、[离线蒙皮诊断](engineering/POSE17_OFFLINE_LBS_DIAGNOSTIC.md)及[头部标定来源](engineering/POSE17_HEAD_SURFACE_CALIBRATION.md)。
- [天气光照系统](engineering/WEATHER_LIGHTING_SYSTEM.md)与[地板随机流](engineering/FLOOR_DIVERSITY.md)。
- [Pose接回原seed球衣系统](engineering/POSE_SEEDED_KIT_INTEGRATION.md)：复用appearance v1清单；定位独立Pose入口未应用及native清空材质的断点，v9后按同运动/相机验证。
- [MCP Python执行范围](engineering/PYTHON_EXECUTION_SCOPE.md)：保持项目内执行边界，不为路径迁移放宽权限。

## production：批次、资产与输出

- [v1八组生产记录](production/PRODUCTION_V1.md)、[按seed的数据集结构](production/SEED_DATASET.md)、[连续活跃窗口](production/ACTIVE_TRAJECTORY_QC.md)。
- [位置试产源序列](production/POSE17_LOCATION_PILOT_SOURCES.md)；位置有效性与可见性分别处理，unknown不升级为COCO visible。
- [MPFB生产SOP](production/MPFB_PLAYER_PRODUCTION_SOP.md)与[UE资产历史短渲染基线](production/UE_ASSET_BASELINE.md)。短样通过不等于所有长批/姿态/物理碰撞已验。
- [UE资产目录](production/UE_ASSET_LAYOUT.md)：环境分类及保留重定向器的兼容边界。

## research：论文问题与控制

- [CVPR论文计划](research/CVPR_2027_PAPER_PLAN.md)。
- [控制协议与历史兼容证据](research/POSE_CONTROL_PROTOCOL.md)、[COCO公开开发评价口径](research/POSE_COCO_EVALUATION.md)。
- [固定检测Pose附件](research/POSE_FIXED_DETECTION_ATTACHMENT.md)、[关联评价细节](research/POSE_ASSOCIATION_TRACKEVAL.md)及[交互窗口候选](research/INTERACTION_WINDOW_CANDIDATE.md)。
- [本轮v4真实结果](research/POSE_V4_RESULTS.md)：本次根据已结束元数据新增；同真实曝光平均AssA仅+0.26444035pp、1/3 seed为正，未过登记门槛；混合臂未超过预训练关联结果。不预设合成收益。
- [30秒数据后续实验](research/LONGPAIR_NEXT_EXPERIMENT.md)：先尺度/附件覆盖，再做同运动地板控制；当前执行口径见[v5协议](research/POSE_LONGPAIR_V5.md)。
- [v5完整结果](research/POSE_V5_RESULTS.md)：九臂训练及真实追踪完整结束，蓝相对R3平均AssA仅+0.2644点、1/3 seed为正，红均差0；均未过登记门槛或超过预训练。含低姿态覆盖线索及下一轮方案。
- [v6固定框裁剪Pose](research/POSE_FIXED_CROP_V6.md)：十模型完整结束，覆盖升至77.95%但全部轨迹相同，混合相对R3和同crop预训练均无提升；含实际权重/预测差异证据和下一轮约束。
- [v7质量与时序关联](research/POSE_QUALITY_TEMPORAL_V7.md)：已知框定位质量、同PT状态成本敏感度及独立短时Pose预测协议；区分几何覆盖、定位精度和关联决策。
- [v8协议](research/LEARNED_ASSOCIATION_V8.md)和[完整结果](research/LEARNED_ASSOCIATION_V8_RESULTS.md)：36臂三比赛留一开发，合成Pose组较纯真实AssA+2.8034点、较预训练ByteTrack+1.4727点，但低于motion_RS 4.3956点；实际窗口/pair预算通过，保留全部负结果。
- [v9训练前诊断](research/POSE_V9_DIAGNOSIS.md)和[质量残差协议](research/POSE_QUALITY_RESIDUAL_V9.md)：缺点/噪声、自由状态和有限外观域差；主三seed、探索事前首seed，已全部结束。
- [v9主54臂阶段结果](research/POSE_V9_MAIN54_STAGE.md)为历史中期报告，后续探索和实际预算均已闭合，以完整结果为准。
- [v9完整结果](research/POSE_V9_RESULTS.md)：78臂及实际预算已闭合；混合−纯R AssA+0.8867点，但对同名义参数motion仅+0.1459、对强motion−0.4491点，未过Pose增量门槛。
- [绿色草地/原seed球衣配对](research/GREEN_SEEDED_KIT_PAIR_A01.md)和[18臂完整结果](research/GREEN_SEEDED_KIT_RESULTS_A01.md)：采集、固定框预测、训练/追踪和实际预算均闭合；B−纯R AssA+1.1078、B−PT bbox+5.6404点，B−强motion−0.2279、B−A−0.0102点，保留全部负结果，测试封存。
- [独立运动与困难关联v10协议](research/MULTISEED_HARD_ASSOCIATION_V10.md)和[完整结果](research/POSE_V10_RESULTS.md)：54训练/253项五比赛评价及全过程预算已闭合；两新比赛gated−强motion AssA平衡−0.0417、困难+0.2110点，均未过登记门槛。同3000R混合较纯R小幅提高，不能称Pose可靠增量或合成等价真实，全部负结果保留。
- [Pose诊断与合成替代真实监督方案](research/POSE_DIAGNOSIS_AND_REAL_DATA_SUBSTITUTION_PLAN.md)及[首轮执行](research/POSE_MECHANISM_A01.md)：162项固定权重CPU诊断、20例视觉复核/额外R可行性/57段元数据及进程退出均已完成，新增优化更新0。Pose分支实际作用很小，下一步先单因素验证利用机制；资源替代另立预算与准入，不把均值接近或新窗口UID当真实等效/标注节省。
- [残差幅度单因素探针](research/RESIDUAL_AMPLITUDE_PROBE_A01.md)：108项CPU对照/分析/实际退出及CSV已闭合，外部Pose仅微变、原heldout下降；区分训练期补充、Pose推理及一般幅度作用，不声称改大幅度解决问题。
- [额外真实输入验收](research/EXTRA_REAL_INPUTS_A03.md)：2250新时间片帧、共享PT预测、三fold各1000窗口及9张未来曝光计划已闭合，新增优化0。全局1500唯一窗口/2007源帧引用，非新增比赛；后续七比赛与无界限区间方案另立，C的4000R尚未训练，测试封存。
- [七比赛真实资源对照方案](research/REAL_SUPERVISION_SUBSTITUTION_A01.md)及[完整结果](research/REAL_SUPERVISION_SUBSTITUTION_A01_RESULTS.md)：七场4790输入/共享预测、C18臂18000更新/完整记录、392项自由追踪及1323配对/105区间独立终验全部闭合。主motion B−C AssA +0.0024点，95%CI [−0.5608,+0.5657]；仅报告差值/区间，不据均值接近称等效，测试封存。
- [七比赛后的Pose利用方案](research/POSE_UTILIZATION_NEXT_A01.md)与[实际零更新结果](research/POSE_INFORMATION_CHAIN_A01_RESULTS.md)：54份共同状态/641785行及独立终验已完成，全部未知/负结果保留。简单外推在近motion条件代理上未优于均值，暂不直接启动27–36臂；推进有界变化编码CPU合同，测试封存。七场AssA约30而非旧两场约40，评价范围不能混用，人工Pose质量真值仍未完成。
- [有界变化编码CPU验收](research/POSE_BOUNDED_VELOCITY_CPU_A01.md)：三个实际基础R池/11260pair已核对34列、原gate与单位范数，0模型/优化/外部输入；其后训练/追踪已独立闭合，合同本身不代表收益。
- [原Pose路线历史](research/POSE_PIPELINE_HISTORY.md)保存原阶段独有决策，不能当作今天的恢复命令。

## operations：维护与历史

- [UE与MCP工作流](operations/UNREAL_MCP_WORKFLOW.md)：资产API、dirty、切图和安全重启约定。
- [统一运行与维护](operations/RUNNING_AND_MAINTENANCE.md)：本机路径、启动器和历史入口边界。
- [严格存储与EXR清理](operations/STORAGE_POLICY.md)：G盘媒体边界、D研究执行bundle及成功后定向清理。
- [后续训练性能](operations/TRAINING_PERFORMANCE.md)：实际吞吐观察、有界预取、硬件余量及新协议边界。
- [训练全过程与论文证据](operations/TRAINING_RECORDS.md)：每步曝光/损失、定期完整检查点、历史缺失字段及论文CSV/曲线。
- [根目录文件用途](operations/ROOT_FILES.md)：必须保留的入口、旧OpenCode配置和可再生IDE索引。
- [UE手动启动修复](operations/UE_STARTUP_REPAIR_20261025.md)：最近项目自动恢复导致的模块搜索问题与明确项目启动入口。
- [单仓库迁移记录](operations/SINGLE_REPOSITORY_MIGRATION_20261025.md)。原双仓库/备份建议为历史，不授权补建用户已删除的备份。
- [UE崩溃调查](operations/UE_CRASH_FINDINGS_20261023.md)：一次正常退出不等于历史GC崩溃已根治。
- 本机执行候选、清理清单和历史交接说明同样放在operations，是否已验证/执行以各正文和真实收据为准。

未完成号码两份设计文档仍受保护，保留在原开发目录，不因本次文档整理提交号码实现或资产。P1 Python3.9、研究Python3.10及UE Python环境继续隔离。final116/187封存。

- [有界变化编码单因素学习验证](research/POSE_BOUNDED_VELOCITY_LEARNING_A01.md)与[完整结果](research/POSE_BOUNDED_VELOCITY_LEARNING_A01_RESULTS.md)：27臂27000更新/567完整检查点、513追踪、720指标/720断档配对与120+24描述均已独立终验。七场相对强motion AssA−0.0582点[−0.2245,+0.1080]，未建立可靠编码增量；全部负结果/失败保留，测试封存。
- [新T决策接口零更新方案](research/POSE_DECISION_INTERFACE_A01.md)与[18项完整结果](research/POSE_DECISION_INTERFACE_A02_RESULTS.md)：实际数值/score2、全部事件与独立终验已完成，0更新。当前原q无可信正确分配转移，q1多为破坏，不支持直接放宽质量gate；下一步准备同缓存成熟追踪器对照，代理不当AssA收益。
- [120样本盲人工质量输入](research/POSE_MANUAL_QUALITY_INPUTS_A01.md)：空模板与契约已完成，随后本轮不采用，不再等待人员。原索引/工具归档，实际人工GT0，未报PCK/OKS。
- [官方OC-SORT同缓存12片段协议](research/OCSORT_CACHED12_A01.md)与[全部结果](research/OCSORT_CACHED12_A01_RESULTS.md)：96帧真实准入、12/8165帧追踪/评价、36配对/45指标及9gap描述和独立终验已完成。OC−强motion七场AssA−3.8914点[−11.8842,+4.1015]，原三场/旧两场也均差负；全部负结果和失败保留，不当SOTA或Pose/合成因果结论，测试继续封存。
- [零更新分数与输出政策账本](research/TRACKING_POLICY_LEDGER_A01.md)及[完整结果](research/TRACKING_POLICY_LEDGER_A01_RESULTS.md)：12唯一源/114旧输出/936212发出行全量终验、进程退出；七场GT几何候选覆盖从`>0.6`的52.1307%到`>0.25`的88.4358%，仅候选机会而非收益。内部状态unknown，下一候选只改单一OC门槛，尚未执行，不扩数据或加训。
- [OC门槛0.6→0.25单因素协议](research/OCSORT_THRESHOLD025_A01.md)及[完整结果](research/OCSORT_THRESHOLD025_A01_RESULTS.md)：真实准入/12新追踪/48配对/60指标和12gap描述及独立终验已闭合，旧0.6只读复用。七场AssA均差−2.4149[−9.4286,+4.5988]，HOTA+7.4114[+1.5670,+13.2558]，覆盖改善未形成稳定AssA增量；不继续搜索门槛，全部负结果保留，测试封存。
- [常驻关联worker实测](operations/ASSOCIATION_WORKER_ADMISSION_A01_RESULTS.md)：六完整任务、原ID/指标一致，2track+1metric相对新进程串行实测2.19365倍；仅该工作量/后端，不冒充模型成绩或整轮训练倍数。
