# COCO17顺序的仅位置监督准备

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

新增独立模块 `src/grf_ue_bridge/pose17_location_export.py`，不修改现有 `pose17_export.py` 或COCO可见性约定。目标是利用真实17点世界/投影坐标进行定位监督，visibility未知时也不丢失已验证的位置；**不生成COCO v1/v2，不称完整COCO可见性数据**。

## 本机真实Ultralytics CPU验证

2026-10-23在Ultralytics8.4.60实际执行39列标签读取、`Pose(nc=1,kpt_shape=(17,2))`头部前向及实际位置loss/梯度，全部仅CPU，未下载模型或启动训练。结果：

- 标签为5+17×2=39列；模型仅预测xy，head输出 `[1,34,336]`，没有逐点visibility预测。
- loader会在内部把xy标签追加坐标有效mask，shape变为 `[1,17,3]`；这只是坐标有效性，不是把unknown说成可见。
- 实际 `calculate_keypoints_loss` 返回有限位置loss=1且梯度非零，keypoint objectness loss=0；用禁止调用的sentinel验证visibility loss没有执行。

源码位置：本机研究环境 `ultralytics/data/utils.py::verify_image_label`、`ultralytics/nn/modules/head.py::Pose`、`ultralytics/utils/loss.py::v8PoseLoss.calculate_keypoints_loss`。证据在外层 `Saved/ResearchDiagnostics/ultralytics_pose17_xy_cpu_a01/receipt.json`；脚本 `verify_ultralytics_pose17_xy_cpu.py`。这是组件兼容验证，尚未证明完整Trainer、真实数据增强/验证器或跨域提升。

## 输入与排除

输入bundle含 `frames`，沿用真实v2 capture字段与固定COCO17顺序，额外要求每个对象的 `bbox_visible_xywh`、`visible_mask_area`。每帧通过原 `validate_capture`；world/UV必须有限、17点全部有效且在画内。unknown保留原始坐标和状态，已知occluded同样保留amodal位置。

训练准备还需显式 `complete_scene_player_annotation_verified=true`、`scene_annotation_coverage_ref`，以及 `location_alignment_verified=true`、`location_alignment_evidence_ref`。这些是调用方声明，不能代替实际覆盖/配对验收；当前diagnostic输入即使强行填训练split仍拒绝。有 `MRQ_sync_verified=false` 或diagnostic source_scope时不能进入训练准备。

训练bbox定义是 **可见mask紧框与17点投影范围的tight union**，不用可见小片段框裁掉已知但遮挡的肢体。它不是完整amodal人体框，也不是直接复用正式bbox。sidecar同时保留原可见bbox及新训练bbox和明确policy。初始异常过滤：至少2px宽/4px高的Pose范围、union框占图面积≤0.5、union面积与原可见框面积比≤16；这些是准备过滤规则，研究开始前要冻结并报告各类排除比例，尤其不能隐藏它可能减少严重遮挡样本的选择偏差。

如果某个对象有缺点/越界/非法bbox，默认**整张多目标YOLO帧排除**，避免其他可见球员被静默删标签而成为未标注背景。对象失败原因与帧排除原因分别统计；sidecar仍保留原对象和点。不能只导出L0目标却将另外9名球员当背景用于正式训练。

split_plan显式将整个seed/group映射到train/val/test；同seed不同clip/相机不能跨split，同帧不能重复。不会随机拆相邻帧或相机。同组多个clip/机位仍只算一个独立组。最终真实测试集的116/187等不参与本工具验证或选型。

## 输出与命令

```powershell
.venv/Scripts/python.exe -m grf_ue_bridge.pose17_location_export <capture_bundle.json> <group_split_plan.json> <全新独立输出目录>
```

split_plan示例：`{"seed_00000042":"train","seed_00000043":"val"}`。输出目录必须不存在，且不能包含 `v1_no_numbers_4k`，不覆盖原正式数据。

默认media-mode=none，只准备labels/sidecar和报告；YAML的train/val/test为空，runnable_training_dataset=false。显式 `--media-mode hardlink` 才在独立images目录创建NTFS硬链接；不同卷不静默拷贝，若需跨卷明确指定copy。媒体会先核对PNG头与尺寸，不声称完整像素审计。已有输出/部分失败输出不可复用，另建新attempt。

```text
新输出/
  labels/<split>/<group>/<clip>/<camera>/<frame>.txt
  images/<split>/<group>/<clip>/<camera>/<frame>.png  # 显式hardlink/copy时
  dataset_location_only.yaml                       # kpt_shape: [17,2]
  location_sidecar.json                            # 原world/UV/unknown/来源/拒绝理由
  preparation_report.json
```

所有训练行39列，第一列player class0，不含v。数据命名、图像与标签相对结构配对满足Ultralytics查找规则；未启动训练，也不因为目录可读取就宣称数据准入或论文效果已通过。

## 已实际读取a02诊断

CLI支持 `--alignment-diagnostic`：读取已有a02 alignment report，强制diagnostic split和非训练集标记，原unknown保留；seed=0只是诊断容器占位，group_id明确 `diagnostic_player003_mrq_a02`，不把它冒充正式GRF seed。

实际输入 `Saved/Pose17Development/smoke/player003_mrq_a02_alignment_a03/report.json`，输出 `Saved/ResearchDiagnostics/pose17_location_a02_prepare_a01`。两个相机各3帧、共6个L0对象，已准备6份39列标签及sidecar；not_training_dataset=true、runnable_training_dataset=false、media-mode=none。它只有三个时间点、一个诊断组且只采L0，**绝不是可用于论文训练的三帧数据集**。

## 下一步实验接入

先完成真实动态MRQ位置对齐与全场球员覆盖验收，再生成含多个独立seed的Pose数据，不修改当前v1。固定group split和筛选规则后做真实-only/真实+合成定位对照，匹配真实曝光与总更新预算，至少三个训练seed；未知可见性不作为visibility预测目标。

模型须明确使用[17,2]头，不能把39列数据交给仍为[17,3]的head后解释为无visibility训练。若用预训练[17,3]权重迁移，需单独设计并验证xy输出通道映射，避免整层重置造成对照混杂。真实验证集若含v标记，用独立评测适配器定义有效/遮挡子集，并先验证评测器不会把模型缺少confidence误当零分；未做这些验证前不汇报Pose AP提升。

本模块的CPU测试证明标签数学、unknown保留、组隔离、覆盖/对齐门禁、bbox规则和目录配对，不替代完整Trainer实验。当前真实最终测试集继续封存。
