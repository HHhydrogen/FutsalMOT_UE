# 300帧长窗：独立配对与候选导出

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

本入口只处理`long_window_contract=true`的两seed、两地板、四机位300帧捕获。它不修改旧3/10/120帧分析器、导出器或研究协议，也不将300帧计划伪装成旧计划。仍使用`pose17_gpu_render_cpu_lbs_joint_diagnostic`底层native采样；300帧×10人=每相机3000条记录。

实现文件：

- `src/grf_ue_bridge/tools/pose17_long_window_postprocess.py`：消费原生nested收据、冻结plan/manifest、P1源输入、P2建源及地板事务；构建独立长窗采样上下文，复用已验逐行GPU/LBS、fence、实际权重/mesh及override证据。
- `src/grf_ue_bridge/tools/inspect_pose17_long_window.py`：全部1200份EXR仅一次公开header读取，检查相机/绝对源帧/相对帧/原生记录，投影逐相机世界点；不重复解码mask或生成全量预览。
- `src/grf_ue_bridge/tools/export_pose17_long_window.py`：直接复用既有Cryptomatte解码、tight bbox及最多6进程处理；每份EXR解码一次，输出mask及17点位置候选。
- `tests/test_pose17_long_window_postprocess.py`：纯CPU文本与虚拟媒体夹具；不是实际UE/GPU/EXR验证。

## 必须先存在的真实收据

输入attempt沿用`Saved/Pose17Development/smoke/<attempt>/`：`plan.json`、`state.json`、`preflight.json`、`editor_after.json`、十份`<entity>_landmark_snapshot.json`及四份`<camera>_native_pose_restore_receipt.json`。每相机3000条完整且唯一`(output_frame,entity_id)`；绝对源帧必须等于`start_frame+output_frame`，不能仅有“采样成功”布尔。

`state.plan_sha256`必须精确对应当前plan。原native identity、manifest SHA、实际骨/RefToLocal/权重签名、LOD0、same-frame/fence、无morph/cloth/deformer/WPO及八个逐组件override/恢复证据继续执行，缺一个记录即拒绝。逐相机世界点原值保留；跨相机微小差异只报告，不平均、不共享或容差合并。

P1 `source_motion.source_input`的路径/SHA须对应新输入包和其中300条映射。统一`P2_sources_prepare.json`必须是实际八个新源Sequence成功保存、scene preserved的收据，其SHA同时绑定队列state和P1批次SHA。其`dynamic_verified=false`保持原义，不能改成已通过动态验收。

地板apply快照来自`state.long_window_floor_transaction`；还须读取`Saved/FloorDiversity/v1/<attempt>_state.json`中实际`original_floor_slot_restored_not_saved`状态。要求session、唯一组件、level、原材质、非地板上下文SHA一致、无范围外上下文变化。未恢复或材质ID不符时不导出成功候选。

配对报告不是免检凭证。导出重新检查原native/world/source和报告标定，按原生FOV/尺寸及外参约定拒绝被改变的内参/外参，再检查媒体帧集合和路径。EXR身份仍依赖真实header，不从计划伪造。

## 实际调用

在内层仓库、带`src`及`ue`路径的现有CPU后处理Python环境中执行；需要原流程已存在的NumPy/Pillow/OpenEXR，不在UE Python中运行。以下首组路径仅为命令示例，必须在真实300帧收尾后调用，不能把未产生的路径视作成功：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='D:/projects/FutsalMOT_UEDataset/Content/FutsalMOT/code/src;D:/projects/FutsalMOT_UEDataset/Content/FutsalMOT/code/ue'
& ./.venv/Scripts/python.exe -m grf_ue_bridge.tools.inspect_pose17_long_window G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/smoke/longpair_s00001048_sport_blue_v1_a02_gpu_lbs G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/longpair_analysis_a01/longpair_s00001048_sport_blue_v1_a02_gpu_lbs
& ./.venv/Scripts/python.exe -m grf_ue_bridge.tools.export_pose17_long_window G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/smoke/longpair_s00001048_sport_blue_v1_a02_gpu_lbs G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/longpair_analysis_a01/longpair_s00001048_sport_blue_v1_a02_gpu_lbs/report.json G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01/_staging/longpair_s00001048_sport_blue_v1_a02_gpu_lbs --copy-rgb --workers 6
```

迁移后所有实际数据必须在G盘：Saved为精确目录联接`D:/projects/FutsalMOT_UEDataset/Saved`→`G:/FutsalMOT_Workspace/UE/Saved`。独立300帧入口支持该D逻辑路径和同一G实际路径；读取前核验精确目标，并拒绝嵌套或其他联接、父目录逃逸和D盘回落。路径在内存中规范为D逻辑Saved以兼容原native JSON身份；实际读写仍是G盘。旧120帧guard不改。逐attempt直接写统一G根`G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01/_staging/<plan.attempt>`，或已迁移Saved内全新`diagnostic_long_*`候选目录；拒绝已有partial覆盖。工具不移动原始渲染、不删除媒体。

推荐`--copy-rgb`使G stage自包含RGB。默认省空间模式只保留明确的Saved RGB外部引用，此模式不能在原始RGB迁移后直接当成自包含发布。原始EXR深度/crypto如需移至统一G根`_provenance/raw/<attempt>`，由root另行记录迁移映射及原始身份；本入口不擅自删除可用于后续visibility研究的EXR。

## 标准stage布局与统一发布

```text
_staging/<attempt>/
  dataset.json                         # candidate stage，未发布/未准入
  calibration/<manifest_sha>.json       # 七个mesh候选，按SHA去重
  groups/seed_XXXXXXXX/
    group.json
    timeline.jsonl                     # 300条；同seed两地板发布时共享
    source_provenance.json              # P1/P2引用，不复制1800步原GRF
    variants/<floor_id>/
      variant.json
      provenance/                      # 实际plan/state/native/配对收据
      cameras/CineCam_01..04/
        rgb/000000.png                 # --copy-rgb时存在
        mask/000000.png
        pose3d_world.jsonl              # 每相机300行×10人，保留其原始world
        pose2d.jsonl
        camera_frames.jsonl            # 每帧真实标定，不假设长窗相机静止
```

`landmark_manifest_ref`以`/calibration/<sha>.json`表示stage根相对引用，不是主机绝对路径。最终统一发布由root在四个stage完成后合并同seed的两个variant、共享timeline/source以及同SHA七manifest；不能把两个地板版本算作两个独立运动seed。本入口的`published_to_G=false`表示尚未统一发布，即使stage文件物理位于G盘。

每attempt期望1200 RGB、1200 mask、12000人物Pose记录；四attempt总计4800对图像及48000人物记录。这些是数量契约，只有真实解码全部完成才写`dataset.json`成功收据。失败仅写`export_failed.json`并保留partial，不伪造成功、不覆盖重试。

## 位置与可见性边界

3D保留原生17点；2D由实际每帧相机投影。`location_valid`只表示有限、正深度、画内投影；`projection_state`单列`unknown/outside/behind_camera`等投影结果。物理`visibility_state`始终17个`unknown`，`visibility_method=not_measured`。画内有效、实例mask命中、tight bbox或非零面积均不能升级为可见/遮挡真值。

stage继续为`diagnostic_only=true`、`not_training=true`，`training_authorized/production_accepted/formal_pose_release/MRQ_sync_verified=false`。它不冒充标准COCO可见性标注，不因已有位置而自动训练。有限位置监督准入须由root在真实渲染、配对、数量及组划分收据后另签；不得修改原诊断标志冒充通过，也不得并入当前已冻结120帧v3研究源。

## CPU验证范围

完整夹具模拟四相机、每相机3000份nested native记录与1200份header/导出mask任务，实际走normalizer、原native事务校验、逐行采样证据、配对和导出结构；虚拟媒体使用明确`CPU_FIXTURE_NOT_*`字节并由测试替换媒体读取/解码函数。它验证程序接线，不能证明真实EXR通道或GPU时序。

反例覆盖旧scope仍拒绝300、缺帧、错误源/相对帧、fence、mesh、权重、override恢复、被改变的报告内外参、标准G根/attempt边界和拒绝覆盖。运行：

```powershell
& ./.venv/Scripts/python.exe -m pytest tests/test_pose17_long_window_postprocess.py -q -p no:cacheprovider --basetemp=G:/FutsalMOT_Workspace/tests/long_window_postprocess_new_attempt
```
