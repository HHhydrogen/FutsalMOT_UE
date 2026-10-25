# 当前任务与下一步

更新：2026-10-25。历史过程见Git及对应运行收据；本页不保留过期PID流水。

## 当前主线结果

- [v6固定raw检测框裁剪Pose对照](Docs/research/POSE_FIXED_CROP_V6.md)十模型已全部完成且实际进程退出：复用v5九个last EMA及预训练、零新正式训练更新、每臂相同3000R。覆盖从约24.3%升至77.95%，但十模型轨迹输出和指标完全相同；两种混合−R3及混合−同crop预训练均为0，未通过进步门槛。
- 全部crop模型AssA/HOTA/IDF1为71.5327/65.4676/81.2946%，IDSW25；相对原整帧预训练低0.5885/0.2596/0.4247点。针对检查确认前两帧训练模型与预训练关键点确实不同，当前关联器未把这些差异转成不同离散轨迹；不将覆盖增长当作准确率或合成收益。
- 真实GPU预取ABBA基准已完成：四次各64诊断更新，同步均25.426秒、预取均16.429秒，约1.55倍；最终模型/EMA/曝光链全部逐值一致。不是1000步完整训练速度承诺，256次诊断更新不计正式预算。代码及记录已推送`942a0b8`。
- v5九训练/官方200图开发评价及九臂固定检测真实追踪已全部结束，相关进程实际退出；9000次正式更新、27000R/6000S曝光，test116/187未使用。原定时跟进v5已按完成条件删除，不重启。
- 相同3000R曝光：蓝混合平均AssA +0.26444035个百分点、HOTA +0.12183663、IDF1 +0.18911788，仅1/3训练seed正；红混合三指标均差0，同为1/3正。均未通过登记的AssA+0.5点/至少2seed门槛。
- 蓝混合与预训练追踪登记指标及现存MOT文本相同；红混合平均AssA低0.26444035点。姿态AP均值蓝/红相对R3仅+0.0828/+0.0335点，全部低于预训练。尚未证明稳定合成收益或超过预训练。
- 有效Pose覆盖仅24.27%–24.32%，每臂5220/6901检测因第二套模型bbox不匹配回退；九臂仅两种MOT输出组合。下一轮优先检验接入覆盖和关联敏感度，再扩训练，不能把低覆盖断言为唯一因果。
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

v6完整分析及完成收据位于D研究根`pose/association_dev_a01/v6_crop/analysis_results_a01`和`milestone_complete_a01.json`。下一步优先区分真实姿态质量与关联器敏感度，并构建时序Pose关联，再决定新增训练/数据预算；不盲目重复相同九臂。新方案另冻结，保持同真实曝光并采用已实测预取，完整记录耗时。当前GPU及UE均无本轮活动任务，最终测试保持封存。

未完成号码继续保留、不纳入当前数据或提交。每独立阶段报告真实完成证据，历史started_not_committed不当作当前故障，不重复启动已结束驱动。
