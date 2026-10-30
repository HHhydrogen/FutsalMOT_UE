# 数据存储与EXR生命周期

## 物理落点

| 内容 | 目录 | 规则 |
| --- | --- | --- |
| 当前临时测试RGB/EXR/mask | `G:/FutsalMOT_Dataset/test/<attempt>/raw` | 新attempt，不覆盖旧输出；导出在同attempt的export |
| 后续正式生成raw | `G:/FutsalMOT_Dataset/_work/<attempt>/raw` | 单seed验收通过后才实现批量发布流程 |
| 后续正式候选导出 | `G:/FutsalMOT_Dataset/_staging/<attempt>` | 验收后同卷发布到新版本 |
| 既有正式数据 | `G:/FutsalMOT_Dataset/<version>/...` | 原布局、split和来源不变；不覆盖或补造历史产物 |
| UE配置、日志、轨迹/native、校准和运行收据 | 项目`Saved/SingleSeed/<attempt>` | D盘只保留小文件与必要原始来源，不写渲染媒体 |
| 研究输入、模型、日志和结果 | `D:/projects/FutsalMOT_Research/pose/<experiment>/...` | 按协议与attempt隔离；图像引用G成品 |
| 研究执行源码 | `D:/projects/FutsalMOT_Research/code/<manifest_SHA>/` | 必要源码按SHA安装，不建第二个Git |

新生成只使用single_seed入口。容量与生命周期由该管线控制，不依赖旧生产driver中的默认值。物理路径核查不能跟随junction，也不能绕过G盘写删权限。

## 容量与活动状态

协议冻结媒体预算1TiB、最低剩余100GiB，`estimated_peak_bytes_per_pixel=7`。分机位准入已接入：按本次实际帧数、全seed选定机位及4K像素估算并存峰值，扣除该attempt现有用量后预留尚需空间，另留100GiB；短样只估算短样规模，不强制空出完整1TiB。运行每2秒检查空闲余量、每30秒统计媒体元数据用量；导出/验证也使用同一容量约束。

每机位独立UE能降低内存积累，但当前EXR统一在全机位消费后清理，因此整个seed的磁盘峰值仍需预算。7byte/px是明确估算参数，不能称为已证明的完整长序列峰值上界；完整3001帧暂未执行。

`_test_lifecycle.json`已接入整个attempt：采集、相机间等待、后处理、校验及EXR清理期间保持active，不因某个机位MRQ结束提前开始保留倒计时。仅在最终验证收据与EXR清理闭合后标记complete，登记成功完成时间并保留24小时；失败停下并保留明确用途及最长7天期限。UE尚未确认停止时使用attention_required并保持活动，避免清理器误删；不伪造成功或自动重放。

每日04:00的`tools/ue_ops/cleanup_test_render.ps1 -Apply`只处理已结束且到期的普通test子目录；跳过active、缺收据和包含reparse point的目录。正式数据、Saved协议/源码/轨迹/native和关键收据不在定时清理范围。

## EXR消费与清理

当前single_seed导出统一完成各机位EXR解码、双mask和标注，经过实际validator成功后按精确清单清理EXR，并记录真实数量/字节。任何仍在消费EXR的阶段都不得提前删除；不必等待不消费EXR的研究训练结束。失败收据保留原值，不把模板标为成功。

清理不跟随联接、不递归删除正式Dataset、不删除RGB、双mask、Pose/world、native、轨迹和校准。需要深度研究时须显式登记消费者、范围和保留期限；EXR退休后原深度/Cryptomatte已丢失，不能从RGB/mask或unknown位置标签声称仍有物理遮挡证据。

空间盘点只使用文件stat和运行收据，不为日常清理重读全部媒体或重新计算全量hash。Git只管理源码、资产和规范，不管理Saved、媒体、权重或虚拟环境。实际功能完成和准入状态以[任务状态](../../TASK_STATUS_AND_NEXT_STEPS.md)为准。
