# UE 资产结构说明（Content/FutsalMOT）

> 本文件由 Housekeeping 后生成，供后续 Agent 理解项目 Content 布局，避免再次制造混乱。

## 目录结构（Housekeeping 后）

```
Content/FutsalMOT/
├─ Animation/                  # 球员动画资产
│  ├─ BS_Futsal_Locomotion / ABP_FutsalPlayer
│  ├─ SoccerSource/            # 动作捕捉源动画（Retarget 输入）
│  ├─ Retarget/                # IK Rig + 重定向（Quinn → SoccerPlayer）
│  └─ SoccerPlayer/            # 目标骨骼动画（MM_/MF_*，ABP/BS _Soccer）
├─ Blueprints/
│  ├─ Pose/                    # ★ 正式 Pose 管线资产（C4/C5 核心）
│  │  ├─ Recorder/             # 同步采样 Recorder（BP_PoseRecorderC4_G0..G4）
│  │  │  └─ BP_PoseRecorder_Legacy   # C2/C3 旧 Recorder（标记 Legacy，勿删）
│  │  ├─ MRQ/                  # MRQ BurnIn Widget（WBP_PoseMRQBurnInC4）
│  │  │  └─ WBP_PoseMRQBurnIn_Legacy # C2/C3 旧 BurnIn（标记 Legacy，勿删）
│  │  └─ SaveGame/             # SG_PoseCapture（UE→Python 传输桥）
│  ├─ BP_SplineCircleLine / BP_SplineArcLine*   # 球场线样条
│  ├─ BP_NoPawnGameMode        # 无 Pawn GameMode
│  ├─ BP_FutsalBall            # 球
│  └─ BP_FieldKeypoint         # 场地关键点
├─ Characters/FutsalPlayer/    # 球员角色（BP_SoccerPlayer、骨架、Mesh、材质、纹理）
├─ Football/                   # 球静态网格 + 材质
├─ Maps/                       # L_FutsalCourt（含 __ExternalActors__ World Partition）
├─ Materials/                  # 场地材质（草皮、白线、ArtificialTurf 贴图）
└─ Sequences/                  # LS_Cam_01..04（回放序列；LS_Cam_01 用于 Pose 渲染）
```

## 正式 Pose 核心资产（勿删、勿改内部逻辑）

| 资产 | 用途 | Python 引用路径 |
|------|------|----------------|
| `Blueprints/Pose/Recorder/BP_PoseRecorderC4_G0..G4` | 每相机 2 actor×13 骨同步采样 | `pose_render.py`/`c5_render.py` 的 `RECORDER_BPS` |
| `Blueprints/Pose/MRQ/WBP_PoseMRQBurnInC4` | MRQ 逐帧触发 CaptureOutputFrame | `BURN_IN_CLASS` |
| `Blueprints/Pose/SaveGame/SG_PoseCapture` | SaveGame 传输桥（capture_complete 等元数据） | `upgrade_recorder_c5.py`/`build_bp_recorder_c4.py` 的 `SG_PATH` |

数据流：`MRQ → WBP_PoseMRQBurnInC4 → BP_PoseRecorderC4_G0..G4 → SG_PoseCapture → Python（pose_capture_export.py 权威完整性 + pose_capture.jsonl/pose_session.json）`。

## Legacy 资产（标记，勿删）

- `Blueprints/Pose/Recorder/BP_PoseRecorder_Legacy`（C2/C3 旧 Recorder）
- `Blueprints/Pose/MRQ/WBP_PoseMRQBurnIn_Legacy`（C2/C3 旧 BurnIn）

旧构建脚本（`build_bp_recorder_c1/c2/c3.py`、`build_burnin*.py` 等）仍引用旧名 `BP_PoseRecorder`/`WBP_PoseMRQBurnIn`——若重新运行需自行更新路径；不建议再运行（已被 C4/C5 正式链路取代）。

## 不应删除的资产

- `Maps/L_FutsalCourt.umap` + `Content/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/**`（World Partition 数据；Level 内放置了 5 个 C4 Recorder Actor）
- `Sequences/LS_Cam_01.uasset`（Pose 渲染主序列）
- `Characters/`、`Animation/`、`Materials/`、`Football/` 全部业务资产
- `Blueprints/Pose/**` 正式 Pose 资产

## 临时数据目录

- `.futsalmot/`（`Content/FutsalMOT/code/.futsalmot/`，gitignored）：resolved task、运行日志、测试临时输出。**保留** `runtime/`（当前任务状态）；其余 `.log` 可清。
- `_futsalmot/`（gitignored）：临时渲染输出，**可安全清理**（本次 Housekeeping 已清空）。
- 外层 `Saved/Logs/*-backup-*.log`：UE 崩溃/调试日志，可清（本次已清）。

## 可安全清理的目录

- `Content/FutsalMOT/code/**/__pycache__/` + `*.pyc`（不含 `.venv/`）
- 任何 `*_render` / `*_smoke` 临时渲染目录（可重新生成）
- 未跟踪的实验/Probe 资产（删除前必须确认无引用）

## 待办（后续 UE 重启后处理）

- `Content/FutsalMOT/Blueprints/BP_PoseRecorderC4_G0..G4.uasset` 旧路径残留为 **Redirector**（0 引用），需在 UE 重启后删除（`EditorAssetLibrary.delete_asset`）以完成移动收尾。