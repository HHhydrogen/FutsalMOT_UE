# Pose 数据集地板因子 v1

状态：四种材质已保存，参数读回与实际球场静态切换/恢复通过；尚未接入正式批量生产或通过MRQ配对验收。已有八组正式数据不变。地板变化是控制域差异的实验因素，不单独作为论文算法创新。

## 素材与参数

使用内置imagegen生成中性灰细纹原图，未程序编辑。可分发源位于`SourceAssets/Floors/V1/T_FloorNeutral_Albedo_v1.png`，同目录`source_receipt.json`记录生成方式、完整提示词与SHA；Saved保留本机历史。它是灰色聚氨酯运动地面细纹基底，不带标线、阴影、人物或场景透视；平铺接缝仍需MRQ验证，不能仅凭提示词声称无缝。

四组线性 RGB：蓝 `[0.075,0.19,0.31]`，青绿 `[0.075,0.25,0.22]`，红棕 `[0.31,0.115,0.075]`，中性灰 `[0.24,0.25,0.27]`。共同roughness=0.72、metallic=0，低强度纹理调制0.04；计划采用2米纹理周期，当前真实UV物理尺度尚未实现或验证。四个独立材质实例共用一个基底贴图。

材质计算：`BaseColor = FloorTint * (1 + 0.04 * (clamp(TextureSample.r, 0, 2*N)/N - 1))`，其中 `N=0.21404114048223255` 是 sRGB 中灰 0.5 的线性值。贴图按 sRGB 导入；Tint 值是线性值。此公式避免直接将中灰贴图乘到地板颜色上导致整体变暗，并限制调制不超过 ±4%。所有变体使用相同纹理/粗糙度，第一轮只研究背景颜色因素。

## 可复现与配对

纯 Python 入口 `src/grf_ue_bridge/floor_diversity.py`，不调用或修改 Python 全局 RNG。SHA256 命名空间 `futsalmot:floor:v1` 与天气/角色/GRF 独立；变体选择只取 seed 与目录 fingerprint。修改天气/相机/角色不得改变该 seed 的地板选择。

调用 `build_floor_manifest(seed, trajectory_sha256=..., frozen_context_sha256=..., texture_sha256=...)`。三个 SHA 必须来自真实冻结输入，不能用占位字符生成正式 manifest。context 摘要应覆盖轨迹以外所有固定条件：相机、动画采样、天气、角色外观及导出配置。manifest 含完整参数、贴图 SHA、目录 SHA、选择 SHA 与 fingerprint。

`paired_floor_manifests` 对同一运动和 context 枚举四个地板变体，共享 pairing_key。配对组必须同 split，不能把同一运动的不同地板放入训练和验证。主训练按 seed 随机地板；少量配对组用于因果诊断。最初八个 seed 未必均匀覆盖四颜色，不能把哈希均匀分布当成小样本保证；需要均衡时应提前冻结分层名单并如实记录 override。

`application_status=planned_not_applied` 始终表示本模块仅给出计划；UE 的真实 application receipt 必须另写，不得把选择器输出当成成功变更场地。

## UE 导入与安全门禁

可分发入口是内层`ue/create_floor_assets_v1.py`（[使用说明](../Content/FutsalMOT/code/docs/FLOOR_DIVERSITY.md)）：直接创建世界XY/200cm图，不依赖下文历史Saved收据。六个目标已全部存在时只读验收，不覆盖；部分存在拒绝隐式补齐；目标不存在且显式apply才创建。脚本不更换地图绑定。下文build/resume/preview属于本机开发历史，未作为阶段发布接口。

1. 等 GPU 训练停止，按 AGENTS 执行 UE/MCP 重连与只读场景检查。主 agent 本次 MCP 确认正式地板 Actor label `SM_FutsalCourt_Floor`，component `StaticMeshComponent0`，mesh `/Engine/BasicShapes/Cube.Cube`，唯一 slot `WorldGridMaterial`，当前材质 `/Game/FutsalMOT/Materials/MI_Futsal_Field_Grass_Matte_v1.MI_Futsal_Field_Grass_Matte_v1`。每次执行脚本仍须重新核验，不以本文代替新鲜状态。
2. 查询场地 Actor 的 StaticMesh、各 slot 名称、材质 class/path、UV 和标线表达方式。`M_MPFB_TestFloor` 是测试资产，不能直接当正式场地主材质。若标线与底色烘焙在同一个贴图，必须先拆解线层，不能用无标线纹理覆盖线。
3. 保存只涉及地板槽的原始绑定快照，经 UE API 新建独立目录 `/Game/FutsalMOT/Environment/Floors/V1/`，导入贴图、参数化材质和四个实例。不得从文件系统写 uasset，不复制/改变当前正式场地资产来掩盖缺少引用诊断。
4. 优先 runtime MID 只替换确认后的地板 slot，不改白色标线、球门、人物及采样。2 米周期必须由世界坐标或经实测的场地 UV 计算，不能凭经验硬编码 UV tiling。
5. 选择固定 seed/camera/frame 在四颜色与高低光照下作小样；核对可见标线、地板曝光、反射、贴图接缝、Pose/Mask 一致性和没有范围外 dirty 包。保存同一帧多模态图像与 application receipt。完成前不得向正式批量配置启用。

## 验证

2026-10-23 单测 `tests/test_floor_diversity.py`：16 passed。覆盖相同 seed 稳定、全局 RNG 不变、上下文不影响地板选择、配对只改变地板、返回值不污染目录、输入 SHA/seed/ID 拒绝及候选覆盖，另验证 UE 预览与生产 manifest 的 seed 选择一致。这些测试不证明 UE 材质效果或平铺无缝。

最终生成提示词保存在 `Saved/FloorDiversity/v1/source_receipt.json`，含图片原路径、项目副本路径与文件 SHA。Saved 是本地生成物，未提交 Git；将来需要发布生成器时应把纹理移入正式可分发源资产目录并固定许可证与来源说明。

独立UE资产创建入口：`ue/build_floor_diversity_v1.py`。默认只读preflight，apply才创建资产；目标存在则拒绝覆盖，失败保留部分资产及明确失败收据。首次创建器只接入未核实的mesh UV，成功记录为`created_not_applied`。后续世界XY升级已实际执行并保存，见下节；场景渲染验收依然独立。

真实 UE 调试发现两处接口差异，保留首次失败及 a02 收据，不覆盖已有资产：`ConnectMaterialExpressions` 使用缩短输入名 `UVs` 和空名，而非 `Coordinates`/`Input`；本机 UE5.8 `MaterialEditingLibrary.cpp` 的 scalar/vector 实例 setter 成功更新后仍恒返回 false（局部 bResult 从未置 true），因此必须检查实际参数读回，不能把 bool 当作失败。a03 入口 `ue/resume_floor_instances_a03.py` 在只读参数诊断确认后，从完整母材质及已正确写入蓝色 Tint 的实例继续，只新增缺失的三个实例，不重建原图。a03 执行与渲染验收状态以其真实收据为准。

## 世界坐标周期升级

主 agent 已通过真实 UE 执行 a03，六个新资产已保存，四实例参数读回正确且 dirty 列表为空；原地图地板仍未替换。材质缩略图仅证明材质球着色，不能证明球场上的周期、接缝或标线。

`ue/upgrade_floor_world_xy_v1.py` 默认只读 preflight，锁定 a03 收据 SHA `595eb9bee6e9509421049593f6805b30e69fa80160cdde108c73a39b5bebff4d`，要求 clean 包、原地板绑定、六个资产的反向引用均限制在本次目录的显式名单。apply 环境变量 `FUTSALMOT_FLOOR_WORLD_XY_APPLY=1` 才增加四个节点：绝对 WorldPosition（排除 shader offset）、RG ComponentMask、默认 200.0 的 `FloorTileSizeCM` 参数、Divide。公式 `UV = AbsoluteWorldPosition_NoShaderOffsets.xy / FloorTileSizeCM`；UE 世界单位是厘米，因此世界 X 或 Y 移动 200 cm 恰好改变对应纹理坐标 1。不使用相机相对坐标，因此四相机观察同一世界点的地板纹理一致。贴图 Wrap，采样不依赖地板网格 UV、缩放或原点。此方法仅面向水平 XY 场地，不声称支持倾斜表面或三平面投影。

旧 UV 节点和 `FloorUVScale` 参数保留但断开，不删除旧节点。升级只修改新母材质及四新实例的周期参数，不操作原地图、原草地材质、纹理源或已发布数据；a03 收据原样归档，升级另写独立收据。CPU 已验证 200 cm 对应 1 UV、Z 不影响 XY 及负坐标；实际周期和贴图接缝仍需绑定独立预览场景后渲染验证，不能由图连接和数学公式替代。

主 agent 已实际执行世界 XY 升级，`Saved/FloorDiversity/v1/ue_world_xy_v1_report.json` 状态为 `world_xy_graph_saved_not_applied`，SHA256 `414c0e129faaec5bfeb565ebdaf2c57c1c28a1803e9901c94fc83f54401d6f17`。四实例周期读回 200 cm，原地图未绑定。此状态是实际材质图与参数验收，尚不是球场图像验收。

## 临时单槽预览与 seed 接入

`ue/preview_floor_diversity_v1.py` 默认 `FUTSALMOT_FLOOR_PREVIEW_ACTION=preflight`，只读核验正式地板、独立白色标线 mesh 槽、新材质父级与 2m 参数。`FUTSALMOT_FLOOR_PREVIEW_CAMERA` 指定同一相机 label（默认 `CineCam_01`），脚本不切换或修改相机。`FUTSALMOT_FLOOR_PREVIEW_SEED` 默认 1021，通过纯函数 `select_floor_id` 选择，与生产 `build_floor_manifest` 完全一致；显式 `FUTSALMOT_FLOOR_PREVIEW_ID` 可以枚举四颜色。预览只记录 `seeded_preview`，不伪造生产轨迹/context SHA，也不声称正式任务已自动启用地板功能。

执行步骤：指定 `FUTSALMOT_FLOOR_PREVIEW_SESSION`（默认 `floor_preview_v1`）后，`FUTSALMOT_FLOOR_PREVIEW_APPLY=1` 且 ACTION=apply 才临时修改唯一地板槽。先写 `_state.json` 意图，成功后更新 state 与 `_steps.jsonl`；第一次必须原材质且 clean。相机、Actor 位置旋转缩放、非地板材质及灯光属性形成上下文指纹；下一颜色 apply 要求指纹未变。root 在同机位采图并记录相机/静态帧身份，最后 ACTION=restore 恢复原槽，不保存地图。若外部改变了非地板状态，restore 仅恢复本任务材质槽并如实记录 `non_floor_context_changed`，不替用户回滚其他操作。

脚本仅调用一次 `component.set_material(0, target)` 作为 UE mutation，不调用 save_map、save_asset、不启 MRQ。异常后使用同 session state 检查最近意图及当前材料，禁止覆盖未知材质状态；报告不将地图内存恢复等同于 shader、像素或生产数据验收。多相机、四颜色的真实球场截图仍由主 agent 通过 MCP 获取和多模态核验。

本次主agent已实际执行升级，`Saved/FloorDiversity/v1/ue_world_xy_v1_report.json`状态为`world_xy_graph_saved_not_applied`，四节点及四实例200cm参数读回、六资产前后SHA已记录；地图绑定未变。材质球缩略图已检查四种颜色可加载，首张蓝色在异步shader未就绪时显示棋盘，独立a02重取后正常；不将首张当作成功图或删去该记录。
