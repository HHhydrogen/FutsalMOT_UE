# 原版绿色草地的有限变化

## 2026-10-29：细草纹与三档绿色，a02已获用户确认

用户已确认a02：UV=60、Normal Flatness=0.90、条带±18%、深/标准/浅线性增益0.60/1.00/1.50，作为后续新生成的绿色目录。以下a01/a02实施过程保留历史；第2项统一入口现已接入该目录，见[统一每场配置](SEEDED_APPEARANCE_UV_NUMBERS.md#统一每场seed配置入口2026-10-29)。

最新a02：用户认为a01条带及三档深浅差距过小，要求加强。保留UV=60与Flatness=0.90，将条带对比由±5%改为±18%（系数0.82/1.18），深/标准/浅增益由0.85/1.00/1.15改为0.60/1.00/1.50。三档真实UE参数读回通过，新增3张同位置/旋转/FOV的干净detail截图，与a01标准截图复用对照，未重新渲染旧版；针对新目录的1项检查通过。a02媒体在`G:/FutsalMOT_Dataset/test/grass_detail_v2_a02/review/grass_review_overview.png`，24小时清理；小收据`Saved/FloorDiversity/green_v2/revision_a02/complete.json`，日志`Saved/Pose17Development/editor_green_texture_v2_a02.log`。原槽恢复、dirty/PIE/MRQ为空、UE正常退出，继续等待第1项人工验收，未推进第2项。下文a01初版数值保留为修改历史，不作为当前参数。

用户要求后续弃用蓝色、红棕色地板，改用不同深浅绿色，并减小过大、过强的草纹。本次为用户五项任务中的第1项；完成后停下等待人工验收，第2项随机系统整合、第3项全部相机调整及单seed生成尚未执行。下文GreenV1为历史方案，当前新候选以本节GreenV2为准。

真实UE中读取原图确认：BaseColor/Normal/ORM共享UV×15，FlattenNormal的Flatness为0.70，世界坐标深浅条带为0.85/1.15。创建`/Game/FutsalMOT/Environment/Floors/GreenV2/M_GrassDetail_v2`，复用原草地母图与贴图，暴露以下实例参数：

| 参数 | 原版 | 新版 | 作用 |
| --- | --- | --- | --- |
| GrassUVTiling | 15 | 60 | 草纹在同一表面方向缩到原来的1/4；BaseColor、Normal和ORM保持同尺度 |
| GrassNormalFlatness | 0.70 | 0.90 | 减弱草纹凹凸，复用原FlattenNormal函数 |
| GrassStripeContrast | ±0.15 | ±0.05 | 条带系数改为0.95/1.05，保留方向与4米周期 |
| GreenAlbedoGain | 原实例1.00 | 深0.85 / 标准1.00 / 浅1.15 | 三通道等比例，仅改变深浅，不引入蓝/红棕候选 |

新实例为`MI_grass_dark_v2`、`MI_grass_standard_v2`、`MI_grass_light_v2`。`python/src/grf_ue_bridge/grass_detail.py::grass_recipe`提供新绿色候选入口，复用既有`futsalmot:floor:v1`独立选择算法，每场固定。历史`floor_diversity.CATALOG`及GreenV1不改字节含义；旧默认选择器为历史兼容保留，新生成通过新入口选择三档绿色。统一运行入口的接线属于待验收后的第2项，当前不声称旧task已自动切换。

真实材质创建/参数读回通过；5项针对检查通过（旧GreenV1兼容及新目录的独立seed、顺序稳定、拒绝蓝/红棕）。八张干净验收截图为原版及三档新版各两视角，来自实际Editor Game View，同相机位置/旋转/FOV；这是静态材质视觉检查，未执行MRQ或生成Pose/实例/号码GT，不替代单seed端到端验收。最初截图出现编辑辅助图标，显式Game View后重新获取；初次overview位置被场馆结构遮挡，排除在对比外，未改任何生产相机。

媒体只在`G:/FutsalMOT_Dataset/test/grass_detail_v2_a01/`，`review/grass_review_overview.png`为三档总览，`review/grass_texture_before_after.png`为原像素裁剪，均仅排版/裁剪，不锐化或改色；按既有24小时test收据清理。小证据位于`Saved/FloorDiversity/green_v2/creation_complete.json`、`preview_state.json`和日志`Saved/Pose17Development/editor_green_texture_v2_a01.log`。原母材质SHA未变，原地板槽已恢复，dirty/PIE/MRQ为空，UE已正常退出。新资产已保存，未发布数据、未提交Git，当前等待用户视觉确认。

## 以下为2026-10-26的GreenV1历史方案

2026-10-26，按用户最新要求调整后续数据方向：主训练数据以原版绿色草地为基底，使用合理的色调和明暗变化；蓝/红版本保留作已有诊断，不再作为下一轮主训练数据。不覆盖旧数据、冻结协议或失败收据。

## 真实材质核验

通过真实UE MCP只读确认规范地图、idle及clean后，当前地板槽绑定为`/Game/FutsalMOT/Materials/MI_Futsal_Field_Grass_Matte_v1`，父材质为`M_Futsal_Field_Grass`。材质包含原有ArtificialTurf的BaseColor、Normal、ORM贴图和世界坐标图节点。实例只有一个名为`Param`的标量，当前值约0.08，没有vector颜色参数。不能把该标量猜作颜色深浅，也不能对不存在的颜色参数调用setter后声称应用成功。

实际小收据位于`Saved/FloorDiversity/green_v1/original_material_inspection.json`。本次仅查询，不创建或修改资产，查询前后dirty为空。原绿色确实保留，旧蓝/红采集只临时换槽并恢复，不是原材质丢失。

## 第一轮范围

以原实例作为原绿色基线；新增独立派生材质时，复制原父材质的图，仅在BaseColor最终输入前增加线性RGB乘数，保留原贴图、法线、UV、几何、粗糙度及其余输入链。原资产与地图绑定不保存修改。候选目录如下，尚未通过实际渲染验收：

| 候选 | 线性BaseColor增益R/G/B | 意图 |
| --- | --- | --- |
| 原绿色 | 1/1/1 | 直接使用原实例 |
| 稍浅 | 1.10/1.10/1.10 | 小幅变亮 |
| 稍深 | 0.90/0.90/0.90 | 小幅变暗 |
| 稍暖 | 1.06/1/0.96 | 小幅暖绿偏移 |
| 稍冷 | 0.96/1/1.06 | 小幅冷绿偏移 |

这些增益不是屏幕RGB或HSV百分比，也不保证经过灯光和tone-map后感知均匀。先做原绿与候选边界短样，查看实际场地和球员对比度，再冻结范围；不依据追踪结果挑颜色。“深浅”只涉及外观，不改变地面高度、WPO或标签位置。

真实UE资产阶段已完成：`python/ue/create_green_floor_v1.py`在全新`/Game/FutsalMOT/Environment/Floors/GreenV1`创建一个复制父图和五个实例（含gain=1的identity，仅作派生链基线）。原图节点/输入连接保留，新增两个BaseColor节点，其他已暴露输出保持；所有实例的增益及原标量Param逐项读回通过。五份原材质/贴图文件SHA保持，未改地图绑定，保存后dirty为空。创建及本次正常退出证据为`Saved/FloorDiversity/green_v1/green_asset_creation_complete.json`和`material_shutdown_observed.json`。UE5.8 Python未暴露PixelDepthOffset枚举，未伪造该逐输出API检查；完整原图通过UE复制，代码不改非BaseColor连接。当前还没有绿色短样的视觉/采样验收，不能据参数通过直接启动完整批次或训练。

纹理、磨损、条带和粗糙度作为后续独立因素；第一轮不同时随机它们或灯光，避免无法判断收益来源。保留原草地纹理，而非给旧蓝色平面简单换一个RGB色块。小幅变化是面向当前绿场真实开发数据的合理假设，尚未证明追踪提升。

## 复现和配对

`grf_ue_bridge.green_floor`登记独立版本的有限目录，调用既有`floor_diversity.select_floor_id`；其选择算法、独立namespace及旧默认目录结果保持不变，只新增显式目录参数。目录SHA参与选择，清单记录材质来源SHA、实际检查收据SHA、运动和冻结上下文；不创建第二套RNG，不消耗运动、天气或球衣随机流。

序列内固定一个地板配置，同运动、同相机A/B的地板必须相同，同组保持同split。球衣继续使用原seed系统：A默认/B原清单，固定roster和肤色。新绿色采集使用独立attempt、G盘独立数据版本和新准入；旧blue计划的`floor_id`及原bytes保持，不使用旧蓝RGB冒充绿场。候选清单的`runtime_authorized=false`，不能直接提交MRQ。

## 资源与采集顺序

旧a03已完成1048的A/B四机位共8个单位，2400RGB/mask、24000人物Pose；a04尝试下一UE与6CPU导出重叠，1102_B/Cam01实际commit低于6GiB后正常取消并恢复、退出。1102_A/Cam01的CPU导出随后独立完成300RGB/mask、3000Pose并清除300EXR。旧parent仍为failed，不补写成完整成功，也不重启旧控制器。已完成蓝色内容保留为诊断。

重叠方案没有通过资源验收，不能因瞬时CPU/GPU利用率低继续加队列。用户随后明确取消专门的渲染/导出加速任务；不再把解码优化或并行基准作为实验前置，不接入性能候选。沿用已验单机位300帧串行流程：正常退出UE后后处理并清EXR，再启动下一单位。EXR消费者全部结束即精确退休，失败媒体登记诊断用途和期限；安全门禁不属于已取消的加速任务。

随后执行绿色材质创建/读回/恢复及短样；通过后才完整绿色球衣配对。所有渲染、导出、发布和本次UE正常退出闭合后，另冻结训练。每臂仍1000实际更新、相同3000R窗口同序，混合额外1000S同序及同pair，使用预取，比较混合−纯R、混合−motion_RS和预训练，并保留每fold/seed负结果。原v9 S框、UID、标签若无法与新图严格对应，先建立一致输入，不能隐式挪用。1102不训练或选色；最终116/187及test包继续封存。unknown及源diagnostic/MRQ限制不升级。
