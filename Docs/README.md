# 技术文档索引

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
- [v9训练前诊断](research/POSE_V9_DIAGNOSIS.md)和[质量残差协议](research/POSE_QUALITY_RESIDUAL_V9.md)：缺点/噪声、自由状态和有限外观域差，继而同R预算检验Pose是否超过强motion参考；主三seed、探索事前首seed，已启动唯一新流程。
- [原Pose路线历史](research/POSE_PIPELINE_HISTORY.md)保存原阶段独有决策，不能当作今天的恢复命令。

## operations：维护与历史

- [UE与MCP工作流](operations/UNREAL_MCP_WORKFLOW.md)：资产API、dirty、切图和安全重启约定。
- [统一运行与维护](operations/RUNNING_AND_MAINTENANCE.md)：本机路径、启动器和历史入口边界。
- [严格存储与EXR清理](operations/STORAGE_POLICY.md)：G盘媒体边界、D研究执行bundle及成功后定向清理。
- [后续训练性能](operations/TRAINING_PERFORMANCE.md)：实际吞吐观察、有界预取、硬件余量及新协议边界。
- [根目录文件用途](operations/ROOT_FILES.md)：必须保留的入口、旧OpenCode配置和可再生IDE索引。
- [UE手动启动修复](operations/UE_STARTUP_REPAIR_20261025.md)：最近项目自动恢复导致的模块搜索问题与明确项目启动入口。
- [单仓库迁移记录](operations/SINGLE_REPOSITORY_MIGRATION_20261025.md)。原双仓库/备份建议为历史，不授权补建用户已删除的备份。
- [UE崩溃调查](operations/UE_CRASH_FINDINGS_20261023.md)：一次正常退出不等于历史GC崩溃已根治。
- 本机执行候选、清理清单和历史交接说明同样放在operations，是否已验证/执行以各正文和真实收据为准。

未完成号码两份设计文档仍受保护，保留在原开发目录，不因本次文档整理提交号码实现或资产。P1 Python3.9、研究Python3.10及UE Python环境继续隔离。final116/187封存。
