# 当前任务与下一步

更新：2026-10-25。历史过程见Git及对应运行收据；本页不保留过期PID流水。

## 当前主线结果

- v4六训练/官方200张COCO开发评价及六臂固定检测真实追踪均完整结束，优化器重放0，test116/187未使用。
- 相同3000R曝光：混合臂平均AssA +0.26444035个百分点、HOTA +0.12183663、IDF1 +0.18911788；仅1/3训练seed为正，未达到登记的0.5点/至少2seed门槛。
- 混合臂与预训练Pose的追踪登记指标差为0。COCO AP均差仅+0.03878669点，两臂均低于预训练参考；不能宣称已证明稳定的合成收益。
- 权威训练收据为研究根`pose/poseonly_v4/recovery_cim_a01`，追踪为`pose/association_dev_a01/v4_association_path_a02`；原CIM/路径门禁失败attempt仍保留。完整结果见[结果说明](Docs/research/POSE_V4_RESULTS.md)。

## 本轮整理结果

1. D恢复迁移已完成：44,007文件约13.889GiB，保留97条正式Dataset引用；辅助小证据已归档、可再生夹具已清理，旧G盘Research/Workspace根已删除。原迁移完成收据已归档到`Saved/Maintenance/pose17_20261025/storage_receipts/restore_D_20261025_045844_4237/`，辅助收据位于`Saved/CodexMigration/workspace_aux_20261025/`，不重放。
2. 阶段1文档整理已推送`599e90b`。阶段2代码已移到`python/`，实验提到根`experiments/sim2real/`，P1运行数据位于`Saved/P1/`；没有兼容旧Content的junction。Python3.9环境已离线重装本项目editable，CLI和真实GRF同seed跨进程4步检查通过；路径/CLI/resolved-task针对CPU检查71项通过。Git仅按原blob改名并叠加本轮路径修改，保留未完成号码及其他WIP。
3. 阶段3已完成并推送`d4468e9`：60个足球/球门/看台资产通过真实MCP移到Environment，23处场景网格引用检查通过，17个仍有引用的旧重定向器保留，5个既有资产WIP字节未变。本轮Editor已正常退出。
4. 阶段4统一入口为`tools/run.ps1`、`tools/mcp_cli.py`；路径输出、P1实际配置校验/UE命令生成、独立研究帮助及MCP帮助已通过。37项一次性清单/入口已归档，运行收据回Saved，旧驱动放入`tools/legacy/`。

## 当前v5执行

- UE手动启动已修复：同DLL显式项目路径真实加载，最近项目自动恢复设置关闭，裸引擎启动不再触发缺模块且正常exit0；`1c2b331`已推送。当前保持UE关闭。
- [v5九臂协议](Docs/research/POSE_LONGPAIR_V5.md)已冻结在D研究根`pose/poseonly_v5/frozen_a01`，使用最终`candidate_a04`与不可变执行bundle。实际CPU完成3R+1S反向传播、验证更新及last1/曝光链/严格续跑闭环；24个参数有非零梯度，actual和EMA检测逐值不变，该验证更新不计正式预算。
- 纯真实、蓝合成、红棕合成各三训练seed，每臂1000更新、相同3000R同序，混合另1000S。官方200dev后执行固定检测真实身份关联，并分别报告相对R3与预训练的变化；不能以缓解微调退化宣称超过预训练。
- 启动与实际更新只认D研究根`pose/poseonly_v5/control_a01/driver_state.json`、曝光和事务；首次后台启动的UTF8/tasklist兼容错误发生在只读预飞，未创建正式训练目录或优化更新，原日志留在`_launch/a01`。不改冻结数值，采用原生子进程编码与UTF8日志继续。
- `_launch/a02`已实际启动唯一driver，完成共同预训练参考200dev评价，AP=0.4918960498，与历史口径一致；首个R3已实际超过297个优化更新。当前正式GPU训练运行中，保持UE关闭，不重复启动或变更绑定代码。全部九臂后接真实追踪；尚无v5合成收益结论。

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

执行已冻结v5，先得到全部九臂官方开发集结果，再用相同raw检测和lambda0.1进行真实关联。所有臂保持相同真实曝光及固定检测，合成额外计算单列；不通过继续筛比例/seed制造提升。当前训练输入仅1048，1102保留synthetic_dev，最终116/187继续封存。

未完成号码继续保留、不纳入当前数据或提交。每独立阶段报告真实完成证据；活动训练的started_not_committed不是失败，不重复启动驱动。
