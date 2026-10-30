# 当前任务与下一步

更新：2026-10-29。本页只记当前状态；过去的实现过程、失败和实验结果见[训练历史](Docs/research/TRAINING_HISTORY.md)及Git。

## 当前任务

用户要求并行移除老旧生成管线与过时操作文档，更新README/AGENTS，随后实现分机位容量门禁和覆盖完整导出的临时媒体生命周期。**本轮不启动完整单seed渲染，不启动总数据集批量生成或研究训练。**

新数据集唯一入口为`tools/dataset/single_seed_task.py`与`tools/dataset/run_single_seed_partitions.py`，配置为`python/configs/single_seed_generation_v1.json`。旧task/production、旧批量脚本和旧smoke配置退出新生成流程；共用底层模块保留为内部依赖，历史冻结数据、收据和研究WIP不改。

本轮实现已完成，针对检查共430项通过（核心243项＋兼容187项，16条既有绝对路径弃用警告），Python/PowerShell语法及现行文档链接检查通过。精确移除230个旧代码/配置/对应测试和8份旧生成文档；保留共享实现及历史证据。用户要求提交GitHub后停止，不推进后续任务。

1. 分机位控制器、真实UE入口及后处理已统一执行1TiB预算与100GiB余量检查；新增7byte/px估算，按整seed实际帧数/全部机位预算。运行每2秒查余量、30秒查当前attempt元数据用量，超限正常取消并停止派发。6×3001帧估算973.64GiB，7×3001帧超过当前上限须另立容量方案。
2. 采集、等待后处理、导出/验证/EXR清理均保持活动；最终完成才开始24小时成功保留计时。后处理失败记录failed_stopped及最长7天诊断期限；未证明UE停止则保持attention_required活动保护；重复verify不重置完成期限。

本轮无新增UE/GRF/渲染、媒体扫描、训练或评价。历史a09只作为原180帧动态证据，不当作本次新源码真实长样验证。后处理加速仅作解释，没有接入新并行策略或运行性能实验。

## 已有基线与证据

- 已固化并推送`a2f488a506266242b4e5223609774a8d6f87b56a`：4K、10 FPS、写出8/8、每机位独立UE、同源轨迹及精简seed导出。
- 相机固定C5/C1/C2/C3/C4，加P01–P04随机1–2个；C5高11.7m、8mm。GreenV2 a02、十五套球衣、号码v2及天气视觉v2均已确认。
- a09六机位各30帧全部正常退出，导出180组RGB/人物mask/号码mask、1800个人物记录、905条可见号码、21600个body12点；554文件，180份EXR消费后已清理。
- 8/8六机位短样最低提交余量11.156GiB、物理空闲9.013GiB。短样不能替代完整3001帧运行证据。
- body12 visibility保持unknown=0，号码readable未经人工认证为false；不声称已提供物理遮挡或OCR可读性监督。

详见[单seed基线](Docs/production/SINGLE_SEED_BASELINE_V1.md)、[渲染策略](Docs/operations/RENDER_POLICY_4K_32GB.md)与[当前缺项核对](Docs/engineering/SINGLE_SEED_READINESS_AUDIT.md)。

## 本轮之后

待用户继续完整单seed任务后，使用新attempt与源码协议；旧3001帧源可登记来源/SHA后复用，旧a09协议不改写。满足同attempt短样门禁后，运行1048的6机位×3001帧，统一导出和验证，预期18,006组图像/双mask、180,060个人物记录、2,160,720个body12点；这些完整结果尚未生成。完成后提供少量号码/bbox/body12叠加图，停下供用户验收。

单seed验收通过后才执行正式seed/split冻结、根manifest/schema、批量调度、全局checksums/root fingerprint、总验收与同卷发布。正式相机校验按每seed事前冻结的6–7机位清单，不再要求所有seed相机集合相同。

## 不变的研究边界

原八组及Pose研究数据、全部结果和负结果保持原版本。最终SNMOT116/187/test封存；当前生成整理不授权训练、重推理、追踪、TrackEval或真实数据split选择。研究进度和原始证据见[训练历史](Docs/research/TRAINING_HISTORY.md)；旧研究流水不是恢复生成管线的操作命令。

Saved只留小元数据、轨迹/native、日志和收据，渲染媒体只在G盘，研究数据与最小执行代码在DResearch；不重放迁移或重建备份。协作、UE与存储约束以[AGENTS.md](AGENTS.md)为准。
