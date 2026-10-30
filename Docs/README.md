# 技术文档索引

新数据生成只使用当前single_seed管线：4K、10FPS、8/8写出、按机位独立UE。当前授权与实际阶段以[根README](../README.md)、[AGENTS](../AGENTS.md)和[任务状态](../TASK_STATUS_AND_NEXT_STEPS.md)为准。完整单seed本轮暂不执行。

## 当前生成与导出

- [单seed固化入口](production/SINGLE_SEED_BASELINE_V1.md)：唯一配置、命令、分机位执行与导出顺序。
- [当前待办与原设计差距](engineering/SINGLE_SEED_READINESS_AUDIT.md)：单seed完整验收前与总数据集阶段的边界。
- [32GB主机4K渲染策略](operations/RENDER_POLICY_4K_32GB.md)：8/8实测、内存门槛、正常退出与证据限制。
- [数据契约](engineering/DATA_CONTRACT.md)：seed目录、RGB/双mask、号码、body12、相机和轨迹。
- [验证与限制](engineering/VALIDATION_AND_LIMITATIONS.md)：当前真实短样证据、未完成内容和标注能力边界。
- [存储规范](operations/STORAGE_POLICY.md)：G盘媒体、完整attempt生命周期及EXR清理。
- [运行与维护](operations/RUNNING_AND_MAINTENANCE.md)、[目录与环境边界](engineering/REPOSITORY_LAYOUT.md)。

## 已确认配置与UE维护

- [机位方案](engineering/SEEDED_CAMERA_RIG_V2.md)：五个必选与随机1–2个局部机位。
- [十五套球衣](engineering/SEEDED_KIT_CATALOG_15.md)、[号码显示与同步标注](engineering/SEEDED_APPEARANCE_UV_NUMBERS.md)。
- [GreenV2草地](engineering/GREEN_FLOOR_VARIATION.md)、[独立地板随机流](engineering/FLOOR_DIVERSITY.md)。
- [天气视觉v2](engineering/WEATHER_LIGHTING_VISUAL_V2.md)、[光照应用与恢复](engineering/WEATHER_LIGHTING_SYSTEM.md)。
- [完整Unreal MCP工作流](operations/UNREAL_MCP_WORKFLOW.md)、[Python作用域](engineering/PYTHON_EXECUTION_SCOPE.md)。
- [MPFB角色生产SOP](production/MPFB_PLAYER_PRODUCTION_SOP.md)、[资产目录](production/UE_ASSET_LAYOUT.md)、[资产基线](production/UE_ASSET_BASELINE.md)。
- [GPU渲染/CPU-LBS来源](engineering/POSE17_GPU_RENDER_CPU_LBS.md)：共享实现的历史验证依据，不是另一个生成入口。

## 研究记录与历史

- [训练历史总览](research/TRAINING_HISTORY.md)：完整结果、失败和零更新诊断；不因文档存在自动启动研究。
- [研究协议](research/RESEARCH_PROTOCOL.md)、[论文计划](research/CVPR_2027_PAPER_PLAN.md)。
- [训练全过程记录](operations/TRAINING_RECORDS.md)、[训练性能规则](operations/TRAINING_PERFORMANCE.md)。
- 其余research、Pose17诊断和历史运维记录保留解释原数据与原实验，不能作为新生成准入或重新选择参数的入口。旧冻结协议、数据与收据不改写。

旧无号码生产、活跃窗口、Pose17导出操作手册和号码优先冻结草案已从当前文档移除，不保留本地archive副本。已提交历史可从[清理前Git版本](https://github.com/HHhydrogen/FutsalMOT_UE/tree/a2f488a506266242b4e5223609774a8d6f87b56a/Docs)追溯；当前配置及后续授权优先。
