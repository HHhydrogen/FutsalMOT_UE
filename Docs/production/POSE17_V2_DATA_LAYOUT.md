# Pose17 v2 小批联合输出方案

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

本文是下一阶段的**建议发布契约**，尚未接入生产 publisher，不代表新正式数据已生成或通过验收。依据现有 `pose17_export.py`、`pose17_location_export.py`、[平铺布局（历史）](https://github.com/HHhydrogen/FutsalMOT_UE/blob/a2f488a506266242b4e5223609774a8d6f87b56a/Docs/production/SEED_DATASET.md)和[位置监督说明](POSE17_LOCATION_ONLY_EXPORT.md)整理。当前 v1 的 8 组 RGB/mask 不含 Runtime Pose，不修改、不补造其 Pose。

近期目标是先得到少量独立 seed 的可追溯 RGB、实例 mask、世界 17 点和图像 17 点，并支持仅位置监督的对照实验；精确可见性作为独立验收目标。四视角复制的同一姿态不计为四份独立动作数据。号码不进入本阶段。

## 建议目录：保留单 seed 平铺

```text
v2_pose17_pilot_a01/                  # 独立新根，发布前保持 candidate
  dataset.json
  splits.json
  shared/
    pose17_schema.json               # 固定点序、单位、轴向、状态与来源定义
    generation_recipe.json           # 冻结代码/引擎/采样和渲染配置
    calibrations/<content_hash>.json # 相机常量；只在实际相同时共享
    characters/<identity_hash>.json  # 实际角色身份与通过验收的 landmark manifest
    policies/<content_hash>.json     # 过滤、框语义、深度/可见性及准入策略
  groups/seed_XXXXXXXX/
    group.json                      # seed/split、实体/外观/天气/地板、共享引用
    clip.json                       # 逻辑 clip_id、连续窗、时间基、各输出引用
    timeline.jsonl                  # 发布帧↔GRF帧↔Sequence帧↔时间，一帧一行
    trajectory.jsonl                # GRF根轨迹；不把它称为肢体姿态
    world17.jsonl                   # 每世界帧一行，十实体×17点，跨相机不重复
    checksums.json
    evidence/
      admission.json                # 准入结论及证据引用，不替代原始记录
      capture.jsonl                 # 实际机位/帧/实体采样与形变身份、时序证据
      alignment.json                # RGB/mask/投影/深度配对与量化验收结果
    cameras/CineCam_01/
      view.json                     # 标定/图像尺寸/媒体/深度约定等引用
      camera_samples.jsonl          # 仅实际动态相机需要：逐帧有效外参/投影证据
      annotations.jsonl             # 可见mask的bbox/area等现有语义
      image17.jsonl                 # 逐帧十实体的UV/深度/可见性；引用world帧
      depth_evidence.jsonl          # 深度文件或归档引用、编码、单位、配对身份
      rgb/000000.png
      mask/000000.png
      depth/000000.exr              # 仅选择发布稠密深度时存在
```

不恢复 `clips/clip_000/` 层级。`group.json.clips[].path` 仍指向 `clip.json`，逻辑 clip 身份保留；如以后同 seed 有多片段，再显式升级布局。所有引用为有明确基准的 POSIX 相对路径，禁止盘符和 `..`，不依赖父目录深度；root 共享引用相对数据集根，媒体和局部文件引用相对 `clip.json` 所在目录。若保留 v1 的 `view.calibration_ref`，继续按其现有 root-relative 约定解释，不能混用。

`dataset.json` 是唯一正式索引，记录 schema/version、`release_status`、精确组清单、独立组数、时间帧数、图像数和证据入口。`group.json` 只存一次实体映射和独立随机流 manifest；天气、地板等同一运动的配对变体记录共同 `motion_pair_id`，所有变体和机位归同 split。初始 pilot 不随机拆邻帧或机位，真实 final test 继续封存。

## 字段归属与无损适配

| 信息 | 唯一权威位置 | 各视角引用/派生 |
| --- | --- | --- |
| 角色与实体 | group 的 entity→character identity；shared 的资产/LOD/拓扑/landmark 身份 | 按 entity_id/track_id/mask_id 关联，不逐帧复制外观字典 |
| 时间 | timeline 的发布 frame_index、source_frame_index、sequence_frame_index、实际时间 | image17/capture 以 frame_index 关联；采样特有的 engine frame/时钟保留在 evidence |
| 世界姿态 | world17 的每实体 17×world_m 和来源/有效性 | image17 引用 world_frame_index，不复制 3D 数组 |
| 图像姿态 | image17 的每实体 17×uv_px、camera_forward_depth_m、状态/理由/证据 | COCO 和 YOLO 都是可重建视图 |
| 相机 | 实测不变参数的 shared calibration；变化参数的 camera_samples | 每帧引用有效标定/样本，不能由首帧推断全片静止 |
| 表面/遮挡证据 | capture、alignment、depth_evidence 及其所指的原始证据 | 每点引用证据，不内嵌相同大对象 |

这是发布层去重；现有 `futsalmot_pose17_capture_v2` bundle 暂保留其完整逐相机帧结构作为适配/校验输入。适配器先还原该契约再调用现有导出器，不直接更改 exporter 接口。现有 `build_coco` 已按 `(seed,clip,frame,entity)` 检查跨相机世界坐标和时间**精确一致**；新 publisher 也须先比较全部相机，再去重，不能选首相机覆盖冲突。若独立渲染机位产生不同姿态，先判失败并解决采样问题，不能平均坐标或静默放宽门槛。

v2 建议发布 `frame_index=0..N-1`、媒体 `%06d` 与其一致；v1 的媒体 1-based 不回写。timeline 显式保存源帧和 Sequence 帧，不把 MRQ output frame、shot frame、UWorld 时间互相替代。实际 `capture_id/render_sample_id` 为机位/帧的采样身份；跨视角共享的世界帧键另行声明，不强求不同机位有相同 engine frame。字符串相等只证明格式，不能自行证明同帧。

## 关键点、unknown 与训练有效性

固定 COCO17 点序与角色解剖左右；世界坐标为 `ue_left_handed_x_forward_y_right_z_up_m`，UE cm 只转换一次。像素采用明确标定约定，图内范围为 `[0,width)×[0,height)`，前向深度须大于零。五个头点必须来自该**实际角色**的已验收几何锚点，不能用头中心复制；身体十二点保留定义的关节中心，不能为提高 mask 命中率移动到任意表面。名称相同不等于已证明与真实 COCO 人工标注的解剖定义完全一致，须记录其偏差。

建议 publisher 增加两个派生标志，并保留输入坐标、失败原因及来源证据；这些标志不是当前 exporter 已实现字段：

- `world_location_valid`：世界点有限，来源、角色身份、当前形变和时间配对通过验收。失败时允许 `world_m=null`，不能填零或前帧值。
- `image_location_valid`：前项成立，实际投影配对通过，UV 有限且位于图内、前向深度为正。它表示可监督的位置，不表示表面可见；画外点可以保留原 UV，但该标志为 false。

可见性仍使用当前 `visible/occluded/outside/behind_camera/missing/unknown`。`unknown` 合法且可有有效 3D/2D；保留原因，例如 `surface_support_unverified`、`depth_edge_ambiguous`，不可通过 mask 邻域命中、骨中心射线或“深度文件存在”自动改成 visible。已知 visible/occluded 需要实际经过验收的方法及可解析的 evidence_ref；提供一个字符串不能代替验收。自遮挡/外遮挡可作为额外理由，不先改变现有枚举。

| 原始状态与位置 | 严格 COCO 视图 | 仅位置监督视图 |
| --- | --- | --- |
| visible/occluded 且证据通过 | v=2/v=1 | 坐标有效时可用 |
| unknown 且位置有效 | v=0，原坐标保留 sidecar | 可用位置；不训练 visibility |
| outside/behind_camera/missing 或位置未验收 | v=0，保留原值/原因 | 当前完整帧 [17,2] 导出排除 |

COCO v=0 会让常见训练器忽略该点的位置，不能为训练方便把 unknown 写成 v=1/v=2。当前可执行路线是 `pose17_location_export.py` 的 `[17,2]`、每行 39 列，仅在**整帧全部可见球员均完整标注、所有对象 17 点有限且图内**时导出；任一对象不合格则整帧排除，避免漏标背景。它的框是可见 mask 框与 17 点的 tight union，和正式可见 bbox 分开保留。未来若需要逐点 locvalid 和画外/局部遮挡监督，须另验收支持显式有效掩码的 trainer，不能把现有 39 列接口描述成已支持。

正式 bbox/area/segmentation 继续来自实例 mask 的半开 xywh/可见像素面积/RLE。完全遮挡的球员仍保留十实体 image17/world17 条目；其零面积不生成普通可见 mask COCO 实例。训练 union 框不是完整 amodal 框，OKS 面积选择也须在协议中固定并报告。过滤策略和各角色/关节/遮挡桶的排除率一同发布，不能只报告通过样本数。

## 深度与证据保留

深度是支持可见性研究的证据通道，不默认升级为精确真值。每帧登记与 RGB/mask/采样记录的绑定、真实通道名、编码/dtype、尺寸、单位、背景/无效值、相机前向 z 还是射线距离，以及从原始 pass 到米的转换。上述语义须对实际 shader/EXR 和数值做验证；未验证时明确 unknown，不猜 UE WorldDepth 一定是米或前向 z。

小批验收保留原始 EXR 和 native 收据。正式发布选择其一：发布稠密深度（给出完整帧集合及 hash），或仅将其作为可获取的不可变 QC 归档（清楚声明数据集不含稠密深度，列归档定位与 hash）。不能先删除唯一深度证据，再把一个成功布尔值当成可复核证据。manifest/收据生成一次 hash，正常恢复不反复扫描全部媒体。

## 小批落地与准入门槛

先完成一个短的**全场十实体**联合输出 pilot，再安排多个独立 seed；其作用是验证链路，不宣称论文收益。建议冻结以下逐项门禁，任何未通过项保留 candidate/diagnostic，不能靠改状态字段升级：

1. **来源和实际角色**：有真实 GRF seed/连续活动窗、冻结配置和代码引用。逐实体记录本次实际 VisualMesh 的资产路径、LOD、拓扑身份、manifest SHA 与运行时匹配；计划写了 Player004 或临时 override 成功不等于已覆盖全部角色。先逐个验收生产 Player003–009，再按本批实际使用的模型集合要求 100% 已验收，未通过角色不能进入正式批次。
2. **角色动态/几何**：各实际模型至少覆盖正面、两侧、遮挡与多个真实动画相位；核对五头点语义和身体点定义、角色内左右、服装/身体穿插。3 相机×3 帧仅是最小动态诊断，不代表完整步态、全部体型或全片验收；衣裤异常未定位时不能宣称角色视觉质量通过。
3. **联合帧集**：冻结 camera×frame 笛卡尔积精确一致，RGB/mask/Pose/depth证据无重复或缺帧，每帧十实体齐全（缺点用 null 和原因保留），3840×2160；合法 mask ID/排除非球员 ID 明确。计数分开报独立 seed、唯一时间帧、相机图像和对象数。
4. **实际配对**：读真实 MRQ/native/相机/形变时序与同帧媒体，不由文件名或回调成功推断同步；逐角色、逐关节做可视 overlay 与数值重投影，包含深度边缘和遮挡样例。先在计划冻结误差阈值、样本分层和失败率，再执行验收；纯 CPU 一致性和近景好看都不替代全场量化门禁。
5. **监督准入分层**：先分别给 `location_alignment_verified`、`complete_scene_player_annotation_verified` 及证据作结论，再决定是否允许位置训练；可见性未知可保留，但精确 visibility 尚未通过时不称完整 COCO 可见性数据。当前 exporter 还会拒绝 `MRQ_sync_verified=false` 或 diagnostic source，不能只删字段绕过限制。
6. **发布和实验**：新根、新 attempt、逐组准入收据与实际文件一致；失败不覆盖成功产物。完成全批渲染、安全退出 UE 后才进行 GPU 训练。真实-only/真实+合成按预注册问题固定相同的真实标注集合及更新预算，并明确报告真实曝光差异；若另控制真实曝光，须独立列出额外计算对照，不能声称同时控制了全部预算。先校验训练器/评测器，再以封存 test 之外的验证集选择方案；最终 test 不参与阈值、比例或角色选择。

当前没有宣称满足这些正式门禁。现有近景记录、CPU XY loss 验证、头点候选和表面支持候选可作开发证据，必须保持其真实 diagnostic 状态。需要接线的最小新增功能是发布层去重/引用适配器及其全场联合准入；先复用现有验证器，不为本建议重写生产链路。

## 独立最小适配器：仅 diagnostic/test

`src/grf_ue_bridge/pose17_group_layout.py` 提供纯内存 `build_group_layout(bundle)`、安全文件读取 `read_input(path)` 和新目录写入 `write_group_layout(bundle, output_dir)`，不接 UE 或现有 exporter。输入顶层明确为：

```json
{
  "schema": "futsalmot_pose17_group_layout_input_v1",
  "scope": "diagnostic",
  "seed": 42,
  "clip_id": "clip_000",
  "calibration_version": "rig_v1",
  "source_evidence_ref": "evidence/input_alignment.json",
  "expected_cameras": ["CineCam_01", "CineCam_02"],
  "expected_frame_indices": [0, 1],
  "frames": []
}
```

该示例仅说明顶层字段，空 frames 会拒绝。每个 frame 是已有 `futsalmot_pose17_capture_v2` 完整帧，另有与顶层一致的 `calibration_version`；每点须显式提供 `world_location_valid` 和图像 `location_valid` 两个 bool，后者为 true 还必须满足世界点有效、图内 UV 和有限正前向深度。保留 unknown，与 location_valid 无互相替换。输入必须覆盖冻结 camera×frame 集合与逐帧十实体，不填补缺失点或邻帧。跨机位的时间/源帧、世界坐标、实体/ID、世界来源及模型/manifest 身份须按规范 JSON **精确相等**；不使用 epsilon，不忽略 int/float 类型差异。不同机位允许不同标定引用，但版本须相同，同机位跨帧的标定引用/尺寸须恒定；动态标定暂不支持。

输出为单组的 `timeline.jsonl`、`world17.jsonl`、`cameras/<id>/{view.json,image17.jsonl}` 和 `diagnostic_layout.json`。图像帧有独立 diagnostic schema，不能再作为完整 capture 帧直接传入现有 exporter。只有通过完整输入检查后才创建目录；输出最后一层必须以 `diagnostic_` 或 `test_` 开头，已存在即拒绝。文件入口拒绝路径各级符号链接、Windows reparse/junction、硬链接输入和任何大小写的 `v1_no_numbers_4k` 路径；不复制或读取媒体，不生成生产准入、hash 或训练收据。写入中断保留部分目录，下一次使用新目录，不自动删除。

适配器只校验声明和数值一致性，不验证 `source_evidence_ref` 指向的实际 UE 证据，输出固定 `evidence_independently_verified_by_adapter=false`、`diagnostic_only_not_production_or_training`。它不生成 RGB、mask、depth，不补 world17 真值，不构成正式 publisher。玩具/路径契约测试见 `tests/test_pose17_group_layout.py`；后续接入真实数据前仍需上文全部联合准入。
