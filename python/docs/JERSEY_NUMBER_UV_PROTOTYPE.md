# 球衣 UV 号码原型

2026-10-29固化更新：历史证据原路径保留；新的近景捕获已改为`G:/FutsalMOT_Dataset/test/number_uv_poc_<timestamp>/raw`，不再写项目Saved。当前正式使用入口见[随机外观UV号码](../../Docs/engineering/SEEDED_APPEARANCE_UV_NUMBERS.md)，默认采用用户确认的15%尺寸及微下移profile。本文其余内容为原型阶段历史，不能覆盖当前实现状态。

更新：2026-10-21。此原型与正在导出的无号码数据批次隔离，未切换正式 appearance policy，未修改已有号码开发代码和生产配置。

## 目标与最小实现路径

1. 复用既有号码分配字节协议：`ue_visual_seed` 经独立 SHA-256 命名空间，为固定 `L0..L4,R0..R4` 分配 1–99 的十个不重复号码。不会使用 Python `hash()` 或改变全局 RNG，也不会改变模型/肤色/套装随机分配。
2. 号码作为球衣材质中的 UV 印花，混合 BaseColor，保留原球衣法线、粗糙度及其它图输入；相同球衣网格自然带动印花变形。无需在背部悬挂平面或用投影体近似衣物表面。
3. 以真正的可见号码像素生成整组号码 bbox（如 `37` 共用一个框）。完全不可见时保留号码值，像素数量为零，bbox 为 null。沿用现有 P1 `jersey_number_annotator.py` 的 pixel-tight 半开边界契约。

## 本次获得的新证据

`tools/jersey_number_uv_source_probe.py` 已使用本机 Blender 5.1.1 后台打开七个源 `.blend`，禁用自动脚本、不进行渲染、不保存源文件。Player_003–009 的球衣均为 `futsalmot_jersey_male_flare_v1.002`，1034 个面，UV/拓扑摘要完全一致：

```text
60d2f8d204b7cd8aec2a94775e9b6a584000e18a19ce8d122e7c0ab54675bf58
```

七个球衣均有两个 UV 岛：646 面前片、388 面背片。此语义来自之前人工确认的 `D:/projects/FutsalMOT_blender/asset_staging/_diagnostics/kit_uv_semantics_v4/uv_semantics.csv`，本次重新计算面数和拓扑与之匹配。背片源 UV 约为 U=`0.0001..0.5305`、V=`0.5075..0.9999`。本结论来自实际源网格，不根据共享 Skeleton 推断 UV。

实际 UE 七模型的球衣 slot 名均为 `材质`，但索引不同：

| 模型 | UE 球衣 slot 索引 |
| --- | ---: |
| Player_003 | 3 |
| Player_004–008 | 2 |
| Player_009 | 3 |

两次真实 UE 只读查询均成功，结束时 dirty packages 为空。当前 `SkeletalMesh` 和 `SkeletalMeshEditorSubsystem` 未提供可直接使用的 UV 查询方法；没有继续猜测反射 API。

Legacy FBX importer 的本机源码 `Engine/Source/Editor/UnrealEd/Private/Fbx/FbxSkeletalMeshImport.cpp` 将 V 写为 `1-sourceV`。结合源 UV 和几何位置，单人原型暂用源矩形 `[0.16,0.56,0.37,0.76]`、预测 UE 矩形 `[0.16,0.24,0.37,0.44]`，以及 U/V 翻转。它们仅为待验收起点；导入结果、文字方向、实际位置、身体动作和遮挡尚未通过 UE 视觉检查。

本机证据保存在外层 `Saved/JerseyNumberUV/`：`source_probe.json`、`ue_slot_probe.json`、`calibration_proposed.json`、`source_uv_number37_proposal.png`。CPU UV 图不是 UE RGB 验收图。

## 新增独立代码

- `ue/jersey_number_uv_contract.py`：标准库限定的分配、16×8 图集索引、UV 映射、材质参数和校准报告结构校验。
- `src/grf_ue_bridge/jersey_number_uv_assets.py`：P1 Pillow 图集生成，记录字体摘要、Pillow 版本、PNG/像素摘要和布局。只读字体，不复制字体文件；输出路径已存在则拒绝覆盖。
- `ue/jersey_number_uv_shader.py`：共享 UV 采样 HLSL，矩形外强制无号码，RGB 与号码 ID 模式复用相同图集、位置和翻转。
- `ue/jersey_number_uv_build_preview.py`：构建独立测试材质的准备脚本；默认只读检查并输出计划。只有环境变量 `FUTSALMOT_JERSEY_UV_BUILD_APPLY=1` 才创建 `/Game/FutsalMOT/Tests/JerseyNumberUV/` 下的新测试资产。任何目标路径已存在均拒绝覆盖。复制 Set_01 母材质，不修改原材质，不给球员换装，不提交 MRQ。
- `tools/jersey_number_uv_source_probe.py`、`tools/jersey_number_uv_prepare_calibration.py`：源 UV 诊断、七模型匹配与待验收位置准备。
- `ue/jersey_number_uv_build_mask_preview.py`：构建测试专用 masked alpha、全透明 masked 和可见 stencil 后处理材质；默认只读，需单独 `FUTSALMOT_JERSEY_UV_MASK_BUILD_APPLY=1` 才创建新测试资产。
- `ue/jersey_number_uv_poc.py`：可撤销的冻结姿态近景编排，默认只读。只创建 transient 球员克隆和遮挡物，不给生产球员换装、不保存地图、不提交 MRQ。
- `ue/jersey_number_uv_poc_contract.py`、`tools/jersey_number_uv_validate_poc.py`：短诊断配置门禁、实际 RGB/mask 像素校验和半开边界 tight bbox。颜色必须精确为背景 0 或实体 ID；不猜测色调映射后的 ID。
- `ue/jersey_number_uv_material_readiness.py`：下次空闲窗口对测试材质记录 SkeletalMesh/morph usage、shader 编译统计和纹理依赖，不替换材质、不保存资产。

外层新增 C++ `UJerseyNumberUVLibrary`：参数校验、按名称唯一查询球衣 slot、创建独立 MID，以及完整蒙皮 mask follower 的创建/移除。近景接口还包括 transient 球员克隆、临时遮挡物、同一游戏线程调用内的 RGB/mask 双捕获、身份受限的销毁。它不替换生产组件材质、不保存关卡；捕获拒绝覆盖且限定在 `Saved/JerseyNumberUV/`。C++ 是运行时复用边界；母材质 graph、纹理和一次性测试资产编排仍由 UE Python 负责。现有生产 apply/restore 事务未改动。

图集为 16×8 格，每格 128 像素、12 像素透明边距，尺寸 2048×1024；1–99 顺序排列，其余格为空。使用二次幂尺寸便于后续 UE mip/纹理处理。PNG alpha 存数字轮廓，RGB 为白色；实际号码颜色由材质参数给出。当前本机图集 PNG SHA-256：`04c2b149ce6c3743940e17135de87a08e9656c97e26a0b4298cd8d193ea95041`。

## 验证入口与当前状态

P1 固定 Python 3.9：

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest tests/test_jersey_number_uv_contract.py tests/test_jersey_number_uv_assets.py -q
.venv/Scripts/python.exe -X utf8 -m grf_ue_bridge.jersey_number_uv_assets --font C:/Windows/Fonts/arialbd.ttf --output D:/projects/FutsalMOT_UEDataset/Saved/JerseyNumberUV/atlas_v1
```

本次 32 项 Python 测试通过，包括与旧号码协议逐项一致、无 RNG 副作用、128 个 seed 的号码组合/覆盖、合法范围、UV clipping/翻转、RGB/ID 参数一致、图集逐格 alpha 边界、空白尾格和重复生成摘要一致。UE 脚本只能在真实 UE Python 中运行，不能在 P1 `.venv` 执行。

UE 测试资产已在主线程授予的空闲窗口中构建并保存：`/Game/FutsalMOT/Tests/JerseyNumberUV/T_NumberAtlas_UV_v1` 和 `M_Jersey_Set_01_NumberUV_Preview_v1`。首次 shader 编译发现 VectorParameter 默认 RGB 输出会丢失 UVRect 的第四分量；已依据引擎源码改为显式 RGBA 连线并重新编译。当前完整回读四个 scalar、三个 vector、一个 texture 参数，实际纹理依赖为 Set_01 原纹理和号码图集，pixel shader instruction count 为 231，dirty packages 为空；修复后没有新增 shader 错误。证据为 `Saved/JerseyNumberUV/preview_asset_readback.json`。没有修改或换装正式 Actor、材质和地图，没有正式 RGB/号码 mask 对图。

C++ 初版编译及三项测试通过后，主线程又实际编译了持久 ViewState 补丁，日志 `Saved/PaperPilot/20261021_4k/jersey_persistent_viewstate_build.log` 为 `Result: Succeeded`；新 Editor 启动后反射类可用。2026-10-21 14:29:59–14:30:00 UTC，原生 AutomationToolset 实际执行 `RejectsInvalidInputs`、`RejectsUnownedPreviewLifecycle`、`SingleCaptureNeedsPersistentViewState`、`UsesSemanticSlotRatherThanFixedIndex`，四项全部 Success，零错误/警告；轮转日志 `Saved/Logs/FustalMOT_UEDataset-backup-2026.10.21-15.24.19.log` 留有各项 Test Completed 记录。

这些证据证明当前补丁可编译、反射可用及四项 C++ 测试通过。第二轮近景只有整数 ID/遮挡结构通过，第三轮通过限时图集高 mip 驻留得到清晰号码与完整 mask；目前仅覆盖一名球员的冻结姿态，正式数据继续关闭号码。

新旧 Python 相关测试当前合计 119 项通过，其中 UV/图集测试为 32 项，近景配置及证据测试为 18 项，包括数值快照回归。测试使用已知像素，只证明校验逻辑，不能证明 UE 捕获成功。

## 首轮真实近景结果：未通过

独立 masked、empty masked、可见 stencil 后处理测试材质均已创建、编译并回读：pixel shader instruction counts 分别为 231、186、91，材质类型和输入正确。编排时发现的 ComponentMask 无名输入与 SceneTexture 的 Color 输出已通过实际 pin 查询修正，未修改生产材质。

`Saved/JerseyNumberUV/poc/20261021T133202_094888Z/` 实际生成五组 512×512 RGB/mask，全部 engine_frame=2846，号码分配为 seed42/L0=94。但像素和视觉检查失败：mask 仍是 RGB，含大量非零/32 颜色；候选 back/front 方向相反；背部球衣表现为灰色棋盘，号码不可辨。因此不能生成合格 bbox、授予视觉通过或启用生产号码。

号码后处理未应用已有明确的本机引擎源码证据：旧 helper 关闭 `bCaptureEveryFrame` 后，`bAlwaysPersistRenderingState` 仍为构造默认 false；`SceneCaptureComponent.cpp:407–432` 不会分配 ViewState，而 `Material.cpp:2091–2093` 在无 View.State 时跳过后处理 blendable。经主线程授权增加的 `bAlwaysPersistRenderingState=true` 已实际编译，分配/释放 ViewState 的新增测试已通过；第二轮捕获已输出纯零/32 mask。

灰棋盘的原因尚未确定。当前新会话日志在捕获时明确记录 EmptyMasked 首次需要 SkeletalMesh usage，但没有 beauty 材质缺 usage、shader 编译错误或 LogSkeletalMesh usage 警告。不能把 EmptyMasked 的日志当成 beauty 出错证据。引擎的 skeletal usage、PSO precache 和未完成 shader map 均可能触发默认材质，需要下一窗口记录实际 usage/readiness 并对照原材质与 UV 材质后再确定。

首轮恢复报告保留失败历史：源 Vector/Rotator 的 repr 含临时 `0x` 地址，造成伪差异；另有 EmptyMasked 首次 usage 自动变更使新测试材质 dirty。临时 follower/clone 均精确销毁，未留下测试 Actor。随后只保存该新测试材质，独立 `post_poc_restore_recheck.json` 记录数值快照、正确地图、十人唯一、appearance preflight=true、dirty=[]、PIE/MRQ inactive、残留测试 Actor=[]。没有清 dirty flag 或保存生产资产/地图。代码快照已改为数值列表并补回归测试。

第二轮配置为 `Saved/JerseyNumberUV/poc_config_direction_v2_proposed.json`，仅将背向改为 `[0,-1,0]`，仍标记未校准；首轮原配置和失败输出保留。

## 第二轮真实近景：结构通过，视觉失败

`Saved/JerseyNumberUV/poc/20261021T233426_963759Z/` 的五组 512×512 配对全部为 engine_frame=5539、seed42/L0=94、ID32。`capture_report.json` 数值快照一致、`restore_verified=true`、cleanup errors/临时 Actor/dirty 均为空。P1 实际读取 PNG 得到 `pixel_gate_passed=true`：背面 479 像素、bbox `[235,227,269,257]`；部分遮挡 68 像素；正面及完整遮挡均为零；遮挡物位于后方时 mask 与背面逐像素相同。mask 只有零和 32，没有混色。

RGB 视觉检查仍失败：灰棋盘消失，但背面印花为模糊白块，“94”不可辨认；mask 为小三角形，未呈现完整数字轮廓。结构 gate 只证明同步、ID 颜色、遮挡数量及 tight bounds，不证明数字形状正确。不得据此启用生产号码。

本次捕获前的只读 `material_readiness.json` 为 2026-10-21 23:33:41 UTC、Editor PID19392，五材质前置条件通过，dirty 前后为空。原始 Set_01、beauty、Masked 均 `SkeletalMesh=true/MorphTargets=false`；shader instructions 依次为 193、231、231，Empty 为 186，PP 为 91。主线程在本次日志未发现 material/shader 错误。重启后的实验必须取得新 PID/时间的 readiness，不能沿用此报告。

CPU 定位已将首要假设缩小到图集低 mip：源 PNG 中号码 94 alpha 为正确轮廓、单格覆盖率 21.425%，bbox `[14,29,115,98]`；其 RGB 整格纯白，数字形状完全依赖 alpha。将图集 BOX 下采样到 mip5，即整图 64×32、每号码 4×4 texel，再按共享 UV rect/flips 和同一相机软件投影，会得到与实际相似的模糊白块/小三角形。投影 mip0 为清晰 94、2812 个阈值像素；mip5 为 635 像素、bbox `[234,224,264,258]`，与真实 mask 的 IoU 为 0.703，而 mip0 仅为 0.125。证据为 `Saved/JerseyNumberUV/number94_mip_cpu_comparison.png`、`number94_source_projection_mip0_cpu.png`、`number94_source_projection_mip5_cpu.png` 和 `number94_source_projection_mip_cpu.json`。该推断使用源几何、预测 FBX 坐标和 BOX mip，不能冒充 UE 当前驻留 mip 的直接证据。

下一次只改变测试 atlas 的 mip 驻留，保持 seed/UV/shader/camera/遮挡/DepthTolerance 全部不变：先通过现有 console 工具运行 `InvestigateTexture T_NumberAtlas_UV_v1`，读取本次 `LogContentStreaming` 的 Current/Wanted size；若 Current 为 64×32，将直接支持低 mip 假设。`StreamableRenderAsset.h:180` 将 `SetForceMipLevelsToBeResident` 暴露为 BlueprintCallable；先最小验证 Python 暴露，再仅请求该测试图集限时驻留。请求返回 Editor 主循环后，重新读取 Current size；高 mip 未实际驻留时不得开始新捕获，不得在同一阻塞 Python 调用里靠 sleep 等待。`StreamableRenderAsset.cpp:283–296` 只更新运行时到期时间和 cinematic flag，不保存资产。驻留到期或清除请求后重新核对 dirty 和运行状态。无需修改全局纹理流送开关、正式材质或 UV 标定。

## 第三轮真实近景：限时驻留消除白块

主线程只改变一项：对测试 atlas 调用已实际验证的 `set_force_mip_levels_to_be_resident(300.0, 0)`，调用结束后释放 Editor 主线程，使用同一配置再次捕获。`Saved/JerseyNumberUV/poc/20261021T233849_130305Z/` 五组均为 engine_frame=8347、512×512、seed42/L0=94。RGB 背面“94”清晰且贴合球衣，正面没有号码；部分遮挡保留右侧“4”，完整遮挡不露出号码。mask 背面 2808 像素、bbox `[212,208,302,269]`，与 CPU mip0 投影的 2812 像素相近；部分遮挡 1279 像素，正面及完整遮挡为零，背后遮挡物的 mask 与背面逐像素相同。`pixel_gate_passed=true`、源数值快照一致、`restore_verified=true`，临时 Actor、cleanup errors、dirty 均为空。

真实 `LogContentStreaming` 在 2026-10-21 23:39:14 UTC 记录 atlas 为 DXT5、Current/Wanted 均 2048×1024 `[12]`、限时驻留剩 268 秒；23:39:28 UTC 再次记录相同完整尺寸。console 调用必须传当前 `EditorLevelLibrary.get_editor_world()`；`execute_console_command(None, ...)` 本次没有输出且不报错，不能当作查询成功。单变量实验确认高 mip 驻留可消除白块；第二轮失败捕获当时的实际 resident mip 编号未直接记录，mip5 仍是 CPU 最佳匹配推断。

本轮只证明 Player_003/L0、seed42、一个冻结姿态的印花及五个遮挡 case。没有证明动画跟随、morph/cloth/LOD、多颜色/七模型/十名球员、Sequence/MRQ/Object-ID 共存与恢复。`production_enabled`、全局标定 flags 和正式 v2 config 继续保持关闭。

### 测试图集驻留生命周期

`ue/jersey_number_uv_texture_residency.py` 只处理固定 `/Game/FutsalMOT/Tests/JerseyNumberUV/T_NumberAtlas_UV_v1`，不修改 `NeverStream`、mip 生成设置、shader、全局纹理流送或生产资产。默认 `inspect` 为只读检查。通过环境变量 `FUTSALMOT_JERSEY_UV_RESIDENCY_ACTION` 指定 `request/inspect/release`；`FUTSALMOT_JERSEY_UV_RESIDENCY_SECONDS` 默认为 300，范围限制为 30..300 秒。

1. 先通过 MCP `run_python_file` 执行 `Saved/JerseyNumberUV/residency_request.py`：fresh appearance/runtime/package 门禁通过后才请求驻留，记录 request ID、Editor PID 和到期时间到 `texture_residency_session.json`；已有同 PID 未到期请求时拒绝自动续期。
2. 请求调用结束，返回 Editor 主循环；另发独立 `run_python_file` 执行 `Saved/JerseyNumberUV/residency_inspect.py`。它用唯一日志 marker、当前 Editor World、`InvestigateTexture` 和本机原生 `FLUSHLOG` 获取本次证据；只接受当前 marker 中唯一目标 atlas 的 Current/Wanted 尺寸。只有尺寸均 2048×1024、请求 PID/ID 有效、会话与引擎都至少剩 15 秒、dirty 前后为空时，`texture_residency_readiness.json` 才给出 `ready_for_poc=true`。没有新日志、日志未刷新、低 mip、到期或重启旧会话均保持 false。
3. readiness 为 true 后，在剩余预算内执行现有 PoC，仍要求其 fresh appearance/runtime 诊断和 finally 清理。不要在 request 调用里紧接 capture，也不要在 Editor 主线程中 sleep/poll；未就绪时由外层调度等待并独立 inspect，不能无限续期。
4. 捕获/失败清理结束后，执行 `Saved/JerseyNumberUV/residency_release.py`。只释放同 PID、同纹理且未过期的本脚本请求；已过期只记录 expired，不再次清除运行时状态，以免旧会话误清后来请求。未知请求、手工请求和重启旧 PID 均拒绝释放。即使外层调度中断，限时请求也最多 300 秒后到期。
5. 独立确认无测试 Actor、生产源快照一致、dirty 和 PIE/MRQ 状态正确后释放 UE/GPU 窗口，再开始 GPU 训练。

这些 wrapper 使用 `try/finally` 恢复临时环境变量。生命周期脚本及 11 项日志/所有权/超时门禁测试目前只完成 CPU 验证，尚待主线程在新 Editor 中执行 request→inspect→release 自动闭环；第三轮的成功驻留是主线程直接调用已验证 API，不等同于新编排脚本已在 UE 通过。相关七个 Python 测试文件本次合计 110 项通过，覆盖纯数据契约、图集、配对像素、bbox、材质前置条件和驻留协议。

## 可见号码 mask 的下一步

优先验证“同网格蒙皮 mask 代理”：复制相同完整 SkeletalMesh、使用相同骨架姿态/LOD/变换，仅在球衣 slot 使用共享 UV alpha 的 masked 材质，其余 slot 对 CustomDepth 完全透明。代理不进入 RGB/main pass、不投阴影，仅向 CustomDepth/Stencil 写入 32–41。原始球员和球门等照常写 SceneDepth；后处理必须比较号码 CustomDepth 与 SceneDepth，只接受真正未被遮挡的数字像素。

该路线避免平面代理和球衣曲面不一致，也有机会在同一个 MRQ job 输出 RGB、现有 Object-ID 和额外号码通道。当前只是候选设计，尚未证明：蒙皮 follower 的姿态/LOD 完全同步、原始组件 CustomDepth 的冲突处理、SceneDepth 容差、ID 颜色精度、Object-ID 不受隐藏代理影响，以及 MRQ 导出/恢复生命周期。应先用一人短 Sequence 验证，不能直接接入正式批次。

已核对的 UE 5.8 C++ 边界：`Actor.h` 中 `AddComponentByClass` 标记 `ScriptNoExport`，`AddInstanceComponent` 没有 UFUNCTION；不通过猜测 Python 动态组件 API 绕过。上述 C++ helper 已编译，首轮临时代理创建/销毁没有残留；完整渲染生命周期尚未验收。`USkinnedMeshComponent::SetLeaderPoseComponent` 会将 Leader 链重定向到根 Leader；因此克隆和号码 follower 可读同一源姿态，实际骨骼、LOD、morph/cloth 一致性仍需渲染证据。

## 下一空闲窗口的近景 PoC

持久 ViewState 补丁的编译、重启/反射校验和四项 automation tests 已通过。下一空闲窗口先执行 fresh 诊断并检查测试材质 readiness，再重新捕获五组近景；不复用旧失败图授予通过。近景 JSON 必须显式给出坐标，示例仅为未校准起点：

```json
{
  "entity_id": "L0", "ue_visual_seed": 42,
  "translation_cm": [0, 0, 3000],
  "back_axis_local": [0, -1, 0], "target_local_cm": [0, 0, 130],
  "width": 512, "height": 512, "horizontal_fov": 35, "distance_cm": 180,
  "ue_uv_rect": [0.16, 0.24, 0.37, 0.44], "flip_u": true, "flip_v": true
}
```

执行时严格串行安排 UE 渲染与 GPU 训练。完成当前数据集 MRQ、恢复和完整性核验后，才能使用号码 PoC 的短渲染窗口；号码捕获结束且 Editor 状态恢复后才能开始训练。

下一次五组配对使用以下门禁和顺序：

1. 通过 MCP 原生查询确认当前 Level 精确为 `/Game/FutsalMOT/Maps/L_FutsalCourt`。fresh appearance 诊断要求十名映射球员各自唯一、关键资产 class 正确、所有相关 package clean；PIE/Simulate 和 MRQ 均 inactive，不存在 `FutsalMOTNumberUVTransientStage` 测试 Actor。
2. 通过 `FutsalMOTTools.run_python_file` 执行 `D:/projects/FutsalMOT_UEDataset/Content/FutsalMOT/code/ue/jersey_number_uv_material_readiness.py`。报告包含本次 UTC 时间、Editor PID、原始 Set_01 与四个测试材质的对照。只有 `capture_preconditions_ok=true`、domain/blend/Material class 正确、蒙皮 usage 为布尔 true、shader 指令统计大于零、原球衣贴图与 atlas 依赖齐备、dirty 前后为空时才继续。活动 morph/cloth/deformer 的额外 usage 仍需实际绘制路径确认，不能只因未使用的 morph permutation 为 false 就自动改材质。
3. 读取本次调用时间之后的 `LogMaterial`、`LogShaderCompilers`、`LogSkeletalMesh` 和 `LogPython`。shader compile 错误、usage 警告或 readiness 缺项都应停止捕获并保留报告；不自动设置 usage、保存资产或重新构建正式球衣。
4. 显式指定 `FUTSALMOT_JERSEY_UV_POC_CONFIG=D:/projects/FutsalMOT_UEDataset/Saved/JerseyNumberUV/poc_config_direction_v2_proposed.json`，`FUTSALMOT_JERSEY_UV_POC_APPLY` 移除或设为 `0`，用 `run_python_file` 执行现有 `ue/jersey_number_uv_poc.py` dry-run；全部反射接口和五项测试资产必须存在。`Saved/JerseyNumberUV/poc_dryrun.py` 和 `poc_authorized.py` 已由主线程改为 `direction_v2`；调用前仍须回读实际路径，旧配置和失败输出继续保留。
5. 相同配置设 `FUTSALMOT_JERSEY_UV_POC_APPLY=1`，再次执行同一脚本。它固定按 `back → front → partial_occlusion → full_occlusion → behind_occluder` 捕获，每组输出 512×512 RGB/mask，seed 42、L0 预期号码 94、实体 ID 32；输出必须是新的时间戳目录，不覆盖首轮结果。
6. 对本次 `capture_report.json` 执行下方 P1 像素 validator，并由模型检查配对图：背面号码清晰、正面无号码、部分遮挡只保留可见数字、完整遮挡为零、遮挡物在数字后方时不改变 mask。新 mask 若仍含 RGB/非整数 ID 颜色，或 RGB 球衣仍为棋盘，不得进入生产。
7. `restore_verified=true`、源数值快照相同、临时 Actor 为空、dirty 为空后，再独立执行 fresh appearance/runtime 查询；脚本 finally 内的报告不能替代独立的恢复确认。确认 PIE/MRQ inactive 后释放 UE/GPU 窗口。

`get_statistics()` 在本机 `MaterialEditingLibrary.cpp:2116` 中会提交未完成的 shader jobs 并 `FinishCompilation()`，但没有返回 shader map/PSO 成功布尔值；非零指令统计只是前置证据。引擎 `SkeletalMeshSceneProxy.cpp:221–255` 的 usage 失败会回退默认材质，`:1597–1647` 还存在活动 morph 的 usage 回退。PSO fallback 也有源码分支，但 `PSOPrecache.cpp:139–151` 的组件 precache 和 `:169` 的延迟创建要求 `!GIsEditor`，因此普通 Editor 冻结姿态 PoC 中不应优先认定 PSO 是根因。首轮只有 EmptyMasked 的 SkeletalMesh usage 日志，不能据此解释 beauty 棋盘。

若修复 ViewState 后的新捕获仍有 beauty 棋盘，可复用同一 PoC，在另一份 JSON 中仅添加 `"beauty_variant": "source_control"` 进行受控比较；默认值是 `"number_uv"`。`source_control` 只让临时克隆的球衣 slot 使用原球员的原材质，其它姿态、相机、号码 mask 和清理流程一致。如果源材质正常而 UV 材质棋盘，问题范围缩小到号码母材质或其 shader；如果两者都棋盘，应先查通用克隆/蒙皮绘制路径。该对照的 RGB 本来没有号码，不能将 mask 通过解释为号码外观验收。此分支目前只有 CPU 契约测试，尚未在 UE 执行。

通过 `FUTSALMOT_JERSEY_UV_POC_CONFIG` 指定 JSON；只有 `FUTSALMOT_JERSEY_UV_POC_APPLY=1` 才捕获。脚本核验 fresh map/appearance/PIE/MRQ/dirty 状态、资产和新增反射接口，再建立孤立测试球员。它依次捕获 `back`、`front`、`partial_occlusion`、`full_occlusion`、`behind_occluder`，每个 case 的 RGB/mask 在同一 C++ 游戏线程调用内完成，校验 GFrameCounter 和骨骼 revision 未变化。报告记录相机、分辨率、engine frame、源快照、清理及 dirty 状态；finally 清理仅由本接口创建的临时对象，不清 dirty flag、不保存关卡。

此阶段的 `sequence=null`、`capture_kind=frozen_pose_scene_capture`：它只证明当前冻结姿态的配对关系，不等于正式 Sequence/动画/MRQ 同步通过。前后/遮挡图的方向、印花大小、美观和贴合还需模型视觉检查；CPU 校验不会自动设置这些 flags。

实际捕获后在 P1 执行：

```powershell
.venv/Scripts/python.exe -X utf8 tools/jersey_number_uv_validate_poc.py <Saved/JerseyNumberUV/poc/本次目录/capture_report.json>
```

它输出 `pixel_report.json`，核对同 case 文件、尺寸、SHA-256、实体像素数、零/ID 颜色、tight bbox，以及前面/完整遮挡为零、部分遮挡减少、遮挡物位于背后时像素不变。任何失败保持 `production_enabled=false`。第二轮只有像素结构门槛通过，第三轮已得到冻结姿态的清晰号码和正确 tight bbox，仍未完成生产入口的动画/MRQ 验收。

若同 job 路线不成立，再评估保留全部遮挡几何的独立无光照号码 pass；必须证明与 RGB 的相机、帧索引和实际姿态同步。不得用理论 UV 矩形投影冒充可见号码 bbox，不得隐藏身体/球门来人为消除遮挡。

## 接入生产前的门槛

1. 空闲 Editor 中 fresh appearance/map/package 诊断通过，再构建新的测试资产并检查 shader 日志。
2. 单人背部号码清晰、方向正确、大小自然；正面没有号码；转身、弯腰和手臂遮挡时号码随球衣变形。
3. 同 camera/Sequence/frame/resolution 的 RGB 与号码 mask 配对检查；程序核对真实可见像素、tight bbox、遮挡零像素和编号映射。
4. 依次扩到七个模型、各类套装颜色、十人唯一号码和多个 seed，再验证碰撞/失败/取消的恢复路径。
5. C++ module/build、反射 API 和 automation tests 通过。正式 adapter/camera/MRQ/manifest/annotation/audit 接口接通后再次完整回归。

当前 `calibration_proposed.json` 的所有 UE 视觉验收 flags 均为 false。结构校验只说明报告字段齐备，不能代替实际截图、像素、日志和恢复证据。现阶段首批数据继续不启用号码，避免阻塞合成数据效用实验。
