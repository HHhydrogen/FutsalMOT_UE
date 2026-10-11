# G 盘数据根目录与 12 点 Pose 契约设计

## 目标

将 FutsalMOT 数据集默认生成根目录统一为 `G:\FutsalMOT_Dataset`，把本次生成的 `episode_player003_smoke_10f` 从 `D:\projects\FutsalMOT` 迁移到 G 盘，并把最终 Pose 训练/可视化契约改为 12 个实际骨骼肢体关键点，不再生成面部关键点。

## 路径策略

- `.futsalmot/local.json` 的 `paths.dataset_root` 固定为 `G:/FutsalMOT_Dataset`。
- `.futsalmot/local.json` 的 `paths.ue_project_root` 保持 `D:/projects/FutsalMOT_UEDataset`。
- 只迁移 `D:\projects\FutsalMOT\episode_player003_smoke_10f` 至 `G:\FutsalMOT_Dataset\episode_player003_smoke_10f`；不移动 D 盘其他 episode、`.venv`、源码或 UE 项目。
- 后续 task resolve/export/postprocess/audit/manifest 由 local runtime 配置写入 G 盘。
- 配置不含 `head_offsets_cm`；`bone_overrides` 只接受 12 个肢体点名称。

## Pose 数据分层

### 原始 Runtime Pose

`pose_capture.jsonl` 保持原始 recorder schema、13 bones/actor/frame 完整性和 `pose_session.json` 统计，包含 `head`。它仅是 raw 骨骼证据，不向最终关键点数组输出 head 或面部点。

### 最终 Pose

最终 `coco17_3d.jsonl`、`coco17_2d.jsonl`、`pose_keypoints.jsonl`、`labels_pose/*.txt`、`yolo_pose/labels/` 与 `futsal_pose.yaml` 使用相同的 12 点 limb-only schema。保留 `coco17_*.jsonl` 文件路径作为兼容文件名；每行包含 `keypoint_names` 和 12 点数组，metadata schema 标明 12 点，不称其为 COCO17。

关键点顺序固定为：

```text
left_shoulder, right_shoulder,
left_elbow, right_elbow,
left_wrist, right_wrist,
left_hip, right_hip,
left_knee, right_knee,
left_ankle, right_ankle
```

YOLO Pose 每行 41 字段（5 bbox/class + 12×3）；`kpt_shape=[12,3]`；flip index 为 `[1,0,3,2,5,4,7,6,9,8,11,10]`。可视化只连接肢体点，不绘制 face dots 或 nose-shoulder midpoint。

删除 face keypoint names、head offset 常量/数学函数与配置字段。Legacy `pose_export.py` 和历史 C3/C4 JSONL builder/overlay 也不再生成脸部点，避免导入已删除函数失败；原始 recorder 的 head capture 节点不变。

## 代码边界

- `ue/pose_bones.py` 是最终 12 点顺序、flip index、skeleton edges 和 limb bone candidate 的唯一来源。
- 正式 `ue/build_coco17.py` 从 13 骨 raw rows 中解析 12 个 limb bones；缺失任一 limb point 的 actor-frame fail task，不写成功的完整 12 点数据。
- `ue/run_task.py` bridge 只接受 12 点数组并写 12 点 metadata。
- P1 `pose_annotator.py`、`pose_validator.py`、YAML 与 overlays 全部使用 12 点常量，不含固定 17/56 数值或 face 专用分支。
- `task_audit` 继续要求 `pose_capture.jsonl=10×frames×13`，同时要求最终 3D、2D、visible 数组每条恰好 12 点；报告的 total keypoints 为 rows×12。
- task manifest 的 `pose_schema` 声明 `limb_pose_3d/2d (12 keypoints, meters/pixels)`。
- 已有 G/D 盘旧 17 点 artifact 仅在当前 smoke regenerate 时被覆盖；不会批量改写其它历史 episode。

## 验收

1. 目标 G episode 移动完成后，D 盘对应 source 不存在；episode RGB、mask、raw Pose、audit 等文件在 G 盘可读。
2. 12 点测试覆盖点序、左右翻转、41 字段、可见性索引、overlay、YAML `[12,3]` 和 12 点 audit；17 点最终数组被 audit 拒绝。
3. raw `pose_capture.jsonl` 保持 1300 rows，`pose_session.capture_complete=true`；final 3D/2D/pose_keypoints 数组全为 12 点。
4. G 盘重新运行 task postprocess、validate-pose、full audit，并生成新 debug overlays。
5. P1 非 portable-config 全量测试通过。若完整 pytest 的 portable-config 测试受 local config 覆盖环境变量影响，分别记录，不改变 resolver 语义。
6. 不运行 cleanup apply、不启动 900 帧 production、不提交/推送，除非另获授权。
