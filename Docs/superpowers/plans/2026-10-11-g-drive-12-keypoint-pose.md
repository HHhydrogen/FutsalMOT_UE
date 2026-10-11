# G 盘数据根目录与 12 点 Pose 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 将生成数据根目录切到 `G:\FutsalMOT_Dataset`，并把最终 Pose 标注改为 12 个肢体点，同时保留含 head 的 13 骨 raw capture。

**Architecture:** machine-local runtime 配置决定 dataset 根目录；只迁移本次 smoke episode。`pose_bones.py` 定义 limb-only 12 点最终 schema；runtime raw Recorder 继续 capture 13 bones。P2 builder、P1 bridge、annotator、validator、audit、manifest 与 overlay 共用 12 点契约。

**Tech Stack:** Python 3.9、pytest、NumPy、Pillow、Unreal Engine 5.8 Python、现有 GRF-UE task workflow。

**Spec:** `Docs/superpowers/specs/2026-10-11-g-drive-12-keypoint-pose-design.md`

## Global Constraints

- `dataset_root=G:/FutsalMOT_Dataset`；`ue_project_root=D:/projects/FutsalMOT_UEDataset`。
- 只迁移本次生成的 `episode_player003_smoke_10f`，不得触碰 D 盘其他 episode。
- raw recorder 保持 13 bones；最终 keypoint arrays 只允许 12 limb points。
- YOLO Pose 每行 41 字段；YAML `kpt_shape: [12, 3]`。
- 内层改动在 submodule 完成；不得自动 commit/push，不运行 `git add -A`。
- P1 在 Python 3.9 venv；P2 仅在真实 Unreal Editor Python 运行。

---

### Task 1: 切换 G 盘根目录并迁移 smoke episode

**Files/Paths:**
- Modify ignored: `Content/FutsalMOT/code/.futsalmot/local.json`
- Move: `D:\projects\FutsalMOT\episode_player003_smoke_10f` -> `G:\FutsalMOT_Dataset\episode_player003_smoke_10f`

**Interfaces:**
- `task resolve configs/player003_smoke_10frames_1cam.json` 返回 G 盘 trajectory/output 路径。
- UE project root 保持 D 盘项目路径。

- [ ] **Step 1: Assert exact move preconditions**

```powershell
Test-Path -LiteralPath 'G:\FutsalMOT_Dataset'
Test-Path -LiteralPath 'G:\FutsalMOT_Dataset\episode_player003_smoke_10f'
Test-Path -LiteralPath 'D:\projects\FutsalMOT\episode_player003_smoke_10f'
```

Require: G root exists, G destination absent, D source exists.

- [ ] **Step 2: Update only local dataset root**

Write `.futsalmot/local.json` as:

```json
{"paths":{"dataset_root":"G:/FutsalMOT_Dataset","ue_project_root":"D:/projects/FutsalMOT_UEDataset"}}
```

- [ ] **Step 3: Move the single smoke episode and verify source/destination**

Move only the episode directory; require source absent and G destination has `meta.json`, `frames.jsonl`, `pose_capture.jsonl`, `pose_session.json`, `CineCam_01/img1/`, `CineCam_01/mask/`, and `audit/soak_audit_report.json`.

- [ ] **Step 4: Resolve smoke task and assert G path**

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.cli task resolve configs/player003_smoke_10frames_1cam.json
```

Expected resolved `dataset_root=G:\FutsalMOT_Dataset`, episode path under G, and UE root under D.

---

### Task 2: Define limb-only Pose constants with TDD

**Files:**
- Modify: `ue/pose_bones.py`
- Modify: `tests/test_pose_bones.py`
- Modify: `src/grf_ue_bridge/config/models.py`

**Interfaces:**
- `POSE_KEYPOINT_NAMES`: ordered list of 12 limb names.
- `NUM_POSE_KEYPOINTS=12`, `POSE_FLIP_IDX=[1,0,3,2,5,4,7,6,9,8,11,10]`, `POSE_FIELDS=41`, `YOLO_POSE_FIELDS=41`.
- `normalize_world_keypoints(limb_positions)` returns a list of 12 coordinates/placeholders.

- [ ] **Step 1: Write assertions for 12-point order, flip, field count and normalization**
- [ ] **Step 2: Run `python -m pytest tests/test_pose_bones.py -q`; confirm failure before implementation**
- [ ] **Step 3: Replace formal 17-point and face-offset code with 12 limb constants and normalization**
- [ ] **Step 4: Validate `bone_overrides` against limb names; remove `head_offsets_cm` model field/validation**
- [ ] **Step 5: Re-run pose-bones tests; require all pass**

Implementation details:

```python
POSE_KEYPOINT_NAMES = [
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
```

Remove `FACE_KEYPOINT_NAMES`, `HEAD_OFFSET_CM`, `apply_head_offsets`, and face-only quaternion helpers from the final Pose mapping module. Keep raw recorder `head` capture in recorder assets/source.

---

### Task 3: Convert Runtime Pose builder and bridge; preserve raw 13-bone gate

**Files:**
- Modify: `ue/build_coco17.py`
- Modify: `ue/run_task.py`
- Modify: `src/grf_ue_bridge/workflows/task_audit.py`
- Modify: `tests/test_validation_contract.py`

**Interfaces:**
- Builder reads 13 raw bone records, maps 12 limbs, ignores raw head for final arrays.
- Bridge writes 12-element `keypoints_world` and exact 12-point `keypoint_names` metadata.
- Audit requires raw rows `10 * frames * 13`, final point arrays 12, final total `rows * 12`.

- [ ] **Step 1: Add audit tests: 17-point final arrays fail; 12-point arrays with complete 13-bone raw rows pass**
- [ ] **Step 2: Run the two new audit tests and confirm intended red result for current behavior**
- [ ] **Step 3: Change runtime builder to output 12 limbs and ignore head offsets**
- [ ] **Step 4: Change `run_task.py` bridge length/name/schema metadata to 12**
- [ ] **Step 5: Change audit final arrays and total count to 12 while retaining raw expected 13**
- [ ] **Step 6: Run `tests/test_validation_contract.py` focused tests**

Audit must reject wrong `keypoints_3d_m`, `keypoints_2d_px`, or `visible` lengths, not merely multiply row count by 12.

---

### Task 4: Update P1 annotator, validator, overlays and legacy final-pose entry points

**Files:**
- Modify: `src/grf_ue_bridge/pose_annotator.py`
- Modify: `src/grf_ue_bridge/pose_validator.py`
- Modify: `src/grf_ue_bridge/cli.py`
- Modify: `ue/pose_export.py`
- Modify: `ue/build_coco17_c3.py`, `ue/build_coco17_c4.py`
- Modify: `ue/pose_overlay_coco17.py`, `ue/overlay_coco17_c3.py`, `ue/overlay_coco17_c4.py`, `ue/c4_overlay_check.py`
- Modify: `src/grf_ue_bridge/workflows/task_postprocess.py`, `workflows/artifact_cleanup.py`
- Modify tests: `tests/test_pose_annotator.py`, `tests/test_pose_validator.py`, `tests/test_debug.py`

**Interfaces:**
- P1 projection/visibility consumes exactly 12 points.
- Serializer and validator enforce 41 fields.
- YOLO YAML reports 12 keypoints and 12 flip indices.
- Debug overlays only draw the 12 limb skeleton edges; no face color or midpoint logic.

- [ ] **Step 1: Update synthetic pose fixtures to the exact 12 point order and index assertions**
- [ ] **Step 2: Run pose annotator/validator tests and confirm red failures on current 17-point checks**
- [ ] **Step 3: Replace annotator and validator lengths/names/edges with 12-point constants**
- [ ] **Step 4: Remove face midpoint overlay behavior and obsolete `draw_midpoint` argument**
- [ ] **Step 5: Update legacy exporter/builders/overlays to 12 points so no module imports removed face constants**
- [ ] **Step 6: Update CLI help, postprocess status text and manifest `pose_schema`**
- [ ] **Step 7: Run all pose/debug/audit focused tests**

---

### Task 5: Update task JSON and authoritative docs

**Files:**
- Modify all `configs/*.json` containing `postprocess.yolo_pose.head_offsets_cm`.
- Modify: `README.md`, `docs/DATA_CONTRACT.md`, `docs/VALIDATION_AND_LIMITATIONS.md`, `AGENTS.md` only for formal Pose terminology if needed.

**Interfaces:**
- New task schema has no face offset field.
- Docs distinguish raw 13-bone capture from 12-point final label contract.

- [ ] **Step 1: Remove only `head_offsets_cm` keys from task JSON and preserve valid commas**
- [ ] **Step 2: Parse every touched task JSON with Python `json.loads`**
- [ ] **Step 3: Update docs for 12 names, 41 fields, YAML `[12,3]`, flip indices and raw head retention**
- [ ] **Step 4: Search formal source/config/docs for remaining face-point generation references**

---

### Task 6: Regenerate G-drive smoke artifacts and verify end-to-end

**Files:**
- Runtime outputs under `G:\FutsalMOT_Dataset\episode_player003_smoke_10f` only.

**Interfaces:**
- Raw capture remains 1300 rows / 13 bones per actor-frame.
- Final arrays contain 12 points; labels are 41 fields.

- [ ] **Step 1: Validate task and confirm resolved episode path is G drive**
- [ ] **Step 2: Verify moved RGB/Mask/raw capture and audit inputs exist on G; verify D source is absent**
- [ ] **Step 3: Run UE pose-finalize using resolved task from `.futsalmot/runtime/player003_smoke_10frames_1cam/resolved-task.json`**
- [ ] **Step 4: Assert raw capture 1300 rows, 3D 100 actor-frame rows, each final keypoint array length 12, and 2D visibility arrays length 12**
- [ ] **Step 5: Run task postprocess; assert all labels have 41 fields and YAML declares 12 points**
- [ ] **Step 6: Rebuild debug overlay; inspect images on G and verify no face dots/face links are drawn**
- [ ] **Step 7: Run full audit and non-portable P1 suite; report full pytest portable-config failures if local config precedence still causes them**
- [ ] **Step 8: Verify inner/outer Git status; preserve unrelated edits and stop before commit/push**
