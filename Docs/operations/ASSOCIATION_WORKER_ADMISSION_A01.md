# 关联追踪常驻worker小规模准入

更新：2026-10-27。用户已授权后续工作及本机14600KF/4070Ti SUPER/32GB吞吐改善。原27臂与513项研究已经闭合，本阶段是独立性能准入，不重训、不重推图像感知，不把诊断产物加入论文效果统计。测试SNMOT116/187及test包继续封存。

## 固定工作量

仅从已闭合513矩阵事前固定下列六项完整序列；不截帧、筛检测、改阈值、改精度或事后改任务以取得提速。

| 项 | 原模型与设置 | fold/seed | 原序列 | 帧数 |
| --- | --- | --- | --- | ---: |
| A | T_RS，Pose开启 | game4/20261024 | SNMOT-060 | 750 |
| B | 与A同权重，Pose关闭 | game4/20261024 | SNMOT-060 | 750 |
| C | T_shuffle_RS，推理自然Pose开启 | game4/20261024 | v_2QhNRucNC7E_c017 | 450 |
| D | T_R，Pose开启 | game6/20261025 | v_G-vNjfx1GGc_c004 | 675 |
| E | 原motion_residual_RS，无Pose分支 | game9/20261026 | v_1yHWGw8DH4A_c029 | 725 |
| F | T_RS，Pose开启 | game9/20261026 | v_iIxMOsCGH58_c013 | 451 |

先在单个常驻track与独立metric进程中执行A→C→A，检验跨模型、序列和GT来源后的原ID输出与评价是否保持。再以六项相同工作量执行冷进程→2track+1metric→2track+1metric→冷进程的ABBA顺序。冷模式每项重新启动并正常关闭track和metric进程；并行模式复用原模型和只读缓存、每任务新轨迹与ID计数。所有模式使用同一数值候选，并逐项对照原513产物，不能拿删日志或不同预算当加速。

合计27次追踪与27次评价、17154个重复缓存帧处理，新增图像推理/优化更新均0；这些不是独立图像或新增研究比赛。每性能块六任务3801缓存帧。阶段预算固定，真实失败保留partial，不自动重试或重放成功项；任何恢复须新attempt及明确继承清单。

## 数据与数值门禁

原tracking config SHA为`ac89537c28668959729ea8d1930ca79c8f3ceff2da98c93bd54940467ebfd16d`。新bundle只包含常驻track候选和独立控制/metric源码，显式导入原923/f309/80e等冻结数值来源，不能复制旧runtime改变其ROOT。配置/输入/模型/adapter/执行源码均以完整SHA绑定缓存，不能仅凭mtime。

track进程初始化前安装文件访问审计，拒绝打开GT、gameinfo及含endpoint坐标的原ledger，连为SHA读取这些文件也不允许；仅打开无坐标公开收据。GT和endpoint账本只由独立metric进程持有。审计hook不能卸载，因此track进程不能改作metric。

每任务新建tracker、重置BaseTrack/STrack ID与轨迹/历史，保留自然预测Pose及全部bbox-only/未匹配框。模型eval/no_grad且CPU数值线程1，模型参数/buffer、adapter和缓存frame前后均不变。输入缓存不直接交给可变tracker；不事后重编号。原ID MOT字节、每帧计数、完整关联audit、输入门禁、模型来源、全部原TrackEval值/计数和全事件gap恢复必须逐项与原513结果相同，否则停止吞吐准入，不修改旧成功收据。

## 资源与记录

初始2track+1metric；每track保留frame缓存≤256MiB、模型张量缓存≤64MiB且最多2模型，Python对象/库瞬态仍以实测RSS为准。至少保留8GiB可用物理内存与6GiB commit余量；启动另计每worker1GiB保守空间，任务派发前动态核验。余量不足暂停派发，已有自有任务正常结束；60秒仍未恢复则保留失败，不结束用户应用、改pagefile或强杀。4+2尚不执行，须按实测峰值和下一负载再决定。

每worker独立日志、每次track/metric独占输出、PID与逐PID关闭握手、源码/缓存闭包及实际退出均保留。总耗时包括进程启动、来源验证、模型/输入准备、计算、完整输出、评价和正常关闭；1秒采样系统CPU/可用RAM/commit及本进程树RSS。此纯CPU协议GPU计算和自有VRAM分配为0，不能把其他应用整卡占用算作本任务。采样峰值不是分配器或内核profiler。

结果必须先通过等工作量数值一致性，再比较ABBA均值。即使未提速也保留全部记录，不承诺100%占用或把六任务小样本倍数外推到513/训练/GPU图像推理。恢复取消的渲染、EXR解码或导出加速不在本阶段范围。

## 当前状态

候选CPU合同准备中；此文档不代表真实模型门禁或性能已通过。实际配置、SHA bundle、原日志和准入结果另存DResearch/performance，Saved只保留小收据。
