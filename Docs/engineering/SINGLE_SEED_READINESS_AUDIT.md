# 单seed现行管线与剩余工作

更新：2026-10-29。对照原方案 `D:/projects/FutsalMOT_SyntheticDatasetResearch/Docs/DATASET_GENERATION_FINAL_DESIGN_V1.md`、同项目数据契约及schema；后续用户确认优先。历史七项实施前缺口已接通，不再保留旧待办表误导后续agent，过程可由Git追溯。

## 本轮已完成

- 只保留当前single_seed公开入口，移除旧task/production、C4/C5/Pose17/longpair生成驱动及旧配置。共享渲染、采源、解码和只读研究适配是内部依赖；旧CLI只给迁移提示，不能继续生成。
- README、AGENTS、Python入口和文档索引统一4K/10FPS/8/8、每机位独立UE，十五套球衣、号码v2、GreenV2与天气视觉v2。旧操作手册移除；研究证据和冻结来源保留并标明历史。
- 容量门禁已接入分机位控制器、真实UE入口及后处理。整seed预计峰值按7byte/px计算，预算1TiB、另留100GiB；启动前计入当前attempt用量，运行中继续检查余量及实际用量，不能只看一个机位。
- 临时媒体在rendering、awaiting_export、exporting、verifying保持active、无过期时间；最终校验/EXR清理/成功收据结束才开始24h保留。后处理失败记录停止和7天诊断期限；未证明UE停止时保留活动保护。收据原子更新，重复verify不刷新到期时间。
- 针对检查与原180帧真实短样证据分别登记于任务状态/训练历史；本轮没有UE、GRF、媒体扫描、渲染、训练或完整比赛执行。用户要求完成提交GitHub后停止。

## 剩余：用户重新要求完整单seed时

1. 新建attempt/协议，绑定整理后的源码和配置；可显式登记复用已有3001帧源，不能改写旧a09或将旧收据冒充新运行。公共prepare默认重新采源，未封装复用参数。
2. 满足同attempt短样门禁后，执行1048的C5/C1/C2/C3/C4/P02全部3001帧，再使用现有导出器和validator一次完整验收，不重做整套球衣/天气/机位预览。
3. 预期18,006组RGB/人物mask/号码mask、180,060个人物记录、2,160,720个body12点、54,032个seed目录文件；收齐恢复、正常退出和清理收据，给少量号码/bbox/body12叠加图，停下人工验收。这些数量仍是预期。

容量边界：6×3001帧新估算973.64GiB，另留100GiB；7×3001帧估算1135.92GiB，超过当前1TiB上限会被拒绝，须另立容量方案，不自动减机位。按a09 EXR+导出简单外推约901.16GiB不含全部重复文件，也不是峰值保证。每机位释放UE只降低内存积累，当前仍在全机位消费后统一清理EXR。

恢复边界：仅跳过已有正常退出收据的机位；未闭合机位保留现场停止，不支持机位内逐帧续跑或半导出自动续跑。Pose visibility仍unknown=0、号码readable未经人工认证为false，不擅自追加物理遮挡/OCR模块。

## 单seed通过后才执行的总数据集待办

| 顺序 | 尚未完成的交付 | 原设计依据 |
| --- | --- | --- |
| 1 | 冻结正式dataset版本、seed清单、train/dev、各seed帧数/机位、容量、短样范围和失败规则；1048诊断不自动进入正式dev | 第5、6、10节 |
| 2 | 根dataset manifest与共享schema封装，绑定代码/配置/协议/schema SHA、精确文件数及容量 | 第3、7.2节 |
| 3 | 多seed调度与失败汇总；raw在_work/<attempt>/raw，候选导出在_staging/<attempt> | 第7.1节 |
| 4 | 按冻结manifest核唯一文件树、整场seed的split隔离、机位完整性、全局SHA；生成排序checksums及无循环root fingerprint | 第7.2、7.3节 |
| 5 | 同卷发布新版本、不可变归档、README和总Gate报告；通过后停止，不自动训练 | 第8、9节 |

原设计“不同seed相机集合一致”已被用户确认的“五必选＋随机1–2局部”替代；root schema已有seeds[].camera_ids可复用，正式validator按每seed事前清单验证6–7机位。旧root schema尚缺预期文件数及容量上限字段，在总数据集阶段补齐。
