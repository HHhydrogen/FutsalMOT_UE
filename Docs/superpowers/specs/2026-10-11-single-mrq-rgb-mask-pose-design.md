# 单次 MRQ 同步 RGB、Mask 与 Runtime Pose 设计

## 目标

让 RGB、Object-ID Mask 和 Runtime Pose 在同一 MRQ job、同一输出帧求值中产生，消除当前 RGB Pose 与 Mask 分属不同 MRQ job 时无法证明为相同场景时刻的问题。保持现有 dataset JSON/JSONL 契约、相机帧映射、Instance-ID 映射和 P1 后处理入口不变。

本设计解决渲染会话间的姿态/时刻一致性，不预先断言当前 L1/L2 离群关键点的唯一根因。同步改造完成后，仍以 smoke 像素对照重新判断剩余偏移。

## 当前基线

- 正式入口为 `ue/run_task.py --mode full`，调用 `ue/render_episode.py` 提交异步 MRQ。
- RGB job 使用 Deferred pass、PNG output 和 `WBP_PoseMRQBurnInC4`；BurnIn `OnOutputFrameStarted` 调用 5 个 Recorder，写入 Runtime Pose SaveGame。
- Object-ID Mask 由另一个独立 MRQ job 使用 `MoviePipelineObjectIdRenderPass` 与 multilayer EXR output 渲染到 `render_mask/`。
- 两种 job 顺序执行，但各自独立评估 Sequence、PIE World 和 Retarget AnimGraph；帧号一致不能证明骨骼姿态和相机评估完全相同。
- P1 `cryptomatte.py` 当前优先从 EXR 的 `RGBA.R` 读取 ID。UE 5.8 multilayer EXR 将输出 pass 放进图层；当前独立 Object-ID EXR 的 `RGBA` 是 ID，但合并 RGB 后 `RGBA` 会变为 `FinalImage`，ID 层会改名为 `ActorHitProxyMask00` 等。
- `render_episode.py` 的现有文件归档、watchdog 和 `render_summary.json` 都以 job-kind（RGB 或 Mask）区分输入。

## 设计

### 单一 MRQ job 与 pass 配置

当 `render_rgb.enabled` 与 `instance_mask.enabled` 同时开启时，每个 Sequence 只创建一个 MRQ job。该 job 配置：

- 一个 PNG output setting 和标准 Deferred pass，提供 `FinalImage` RGB。
- 一个 multilayer EXR output setting 和 Object-ID render pass，提供 Cryptomatte 实体 ID。
- RGB 确定性 preset、空间/时间采样及 BurnIn Recorder 配置只应用一次。
- BurnIn `OnOutputFrameStarted` 每个输出帧只触发一次 5 个 Recorder，SaveGame 仍由 `pose-finalize` 按当前完整性门禁读取。

PNG 和 EXR output settings 共享一个 MRQ Output Directory。其 file name format 明确包含 `{render_pass}` 与 frame token，避免 PNG 多 pass 覆盖。输出临时落在现有 camera `render/` scratch 目录，完成后分别归档：

- `FinalImage` PNG 复制到 canonical `img1/{frame_index:06d}.png`，满足校准分辨率检查。
- `ActorHitProxyMask*` 不产生独立 EXR 文件；Object-ID multilayer EXR 以帧号复制到 `render_mask/{render_frame:06d}.exr`。
- BurnIn overlay、`ActorHitProxyMask*.png` 及其它非 FinalImage PNG 不进入 canonical RGB。
- 若 Object-ID pass 被配置但 EXR 中缺少有效 Cryptomatte manifest/ID 层，完成回调报告失败，不写成功 summary。

如果只启用 RGB，则保留目前单 RGB job 行为。如果启用 Mask 且 RGB 关闭，则保留目前独立 Mask job 行为，以免改变非目标配置的语义。Stencil `post_process_material` 路径继续使用其既有 PNG 结果，不伪装成 Object-ID EXR。

### 输出解析与兼容

扩展 render pass 文件解析，按明确 pass 标识选择 `FinalImage` 和 object-ID 输出，不再依赖“最长文件组”这一模糊规则。解析器必须覆盖 UE 实际文件名形式（例如 `FinalImage.000001.png`、`FinalImage000001.png`），只按尾部帧号分组，并容忍 BurnIn overlay 文件存在。

单 job multilayer EXR 的 Cryptomatte decoder 按以下契约读取：

1. 从 EXR header 读取全部 `cryptomatte/*/manifest`。
2. 枚举层和通道，优先寻找一个 float32 R 通道，其位模式中实际 ID 与 manifest hash 匹配；层名为 `RGBA` 或 `ActorHitProxyMask00` 均可。
3. 以 manifest 和每个候选通道的 float32 位模式精确匹配计分，选取命中实体最多的有效通道；平分或没有命中时抛出带候选层信息的明确错误。
4. 保持现有 mask 输出值 `0..11`、Actor Label manifest 映射、像素计数和 P1 CLI 不变。

旧的纯 Object-ID multilayer EXR 仍会命中原 `RGBA.R` 通道并保持可解码；新合并 EXR 使用经 manifest 匹配识别的专用 object-ID layer。

### 完成状态、watchdog 与清理

- Render info 从 `kind=rgb/mask` 两条独立记录改成一个 camera/job 记录，包含 RGB scratch、Mask scratch、canonical img1、render_mask 和 mask source。
- watchdog 必须同时确认所有 expected `FinalImage` PNG 与 object-ID EXR 帧存在；不能只检查 RGB，也不能因 overlay 文件数增长而提前收尾。
- finalize 分别统计 RGB 与 Mask 帧数；`render_summary.json` 继续写现有 `img1_frames`、`mask_frames`、`expected_frames`、`mask_source` 和整体 status 字段。
- RGB zero-waste 仅删除已成功复制的 `FinalImage` PNG 和 BurnIn overlay PNG；不删除 EXR，也不删除尚未归档的其它 pass 文件。
- `render/` 与 `render_mask/` 保持现有下游目录结构，因此 P1 Cryptomatte、postprocess、audit、manifest 和 cleanup 的路径接口无需迁移。

### 异常处理

- 同一 job 配置的 PNG、EXR、Deferred、Object-ID pass 任一必要设置失败时，不提交部分配置 job。
- 目标 pass 或 frame 缺失导致帧数不完整时，`render_summary.status` 必须是 `partial` 或 `failed`，不得标记 success。
- Cryptomatte 层无法匹配 manifest 时由 P1 decoder 失败并报告文件路径、header manifest 和候选层统计；不静默退回 RGB FinalImage。
- Mask disabled、RGB disabled 或 stencil-PNG fallback 沿用其各自既有路径。

## 影响范围

预计修改：

- `Content/FutsalMOT/code/ue/render_episode.py`：job 配置、输出分流、帧存在检查、归档和 summary。
- `Content/FutsalMOT/code/src/grf_ue_bridge/cryptomatte.py`：manifest 驱动的 EXR ID 通道识别。
- `Content/FutsalMOT/code/tests/test_cryptomatte.py` 与新增/扩展 render 纯函数测试：旧式与合并 multilayer EXR、pass 文件名解析、帧分组和错误门禁。
- 权威说明 `Content/FutsalMOT/code/README.md`、`docs/DATA_CONTRACT.md`、`docs/VALIDATION_AND_LIMITATIONS.md` 中相关现行描述。

UE/P1 双仓边界保持不变：Python 和文档属于内层 submodule；只有当前 Editor 运行产生并保存的资产实际发生变化时才涉及外层。未授权提交或推送。

## 验收

### 静态与单元验证

- P1 定向 Cryptomatte 和 MRQ 文件解析测试通过；测试覆盖独立旧 EXR、新的多层 EXR、manifest 精确匹配、缺失层、歧义候选和 FinalImage/BurnIn overlay 筛选。
- 完整 `uv run pytest` 通过。
- 内层 `git diff --check` 通过；分别检查外层和内层 Git 状态，不暂存无关用户改动。

### UE smoke 验证

在正式地图 `/Game/FutsalMOT/Maps/L_FutsalCourt` 上运行现有 10 帧单相机 Player_003 smoke：

- 每相机仅一个包含 PNG、EXR、Deferred、Object-ID 和 Pose BurnIn 的 MRQ job。
- 每帧 exactly one `FinalImage` PNG 与一张多层 Object-ID EXR，文件名帧号集合完全相同，帧数为 10。
- `render_summary.status=success`、每相机 RGB/Mask 都为 10/10；P1 从合并 EXR 生成 mask 并通过完整 `validate-annotations` 与 `validate-pose`。
- `pose_session.capture_complete=true`、10 帧 × 10 actor × 13 骨骼采样结构完整。
- 重新计算每个 Pose 点到其对应实体 Mask 像素的最近距离，逐角色和逐帧报告平均值/最大值；检查 L1/L2 的离群帧是否仍存在，且原本贴合的角色没有回归。
- 运行 `task postprocess` 和 `task audit --validation-level full`；结果 `ValidationResult.passed=true`。此结论与像素对齐度分开记录，结构验证通过不代替几何对齐验收。

在 smoke 全部通过前，不启动 900 帧四相机 production，不运行 cleanup apply，不提交或推送。
