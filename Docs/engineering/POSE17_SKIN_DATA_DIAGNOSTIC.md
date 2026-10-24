# Pose17基础蒙皮数据只读导出

新增独立`UFutsalPose17SkinDataLibrary`，不修改已发布的`FutsalPose17Library`或MRQ pass。已通过UE5.8构建、真实反射和`SkinDataReadOnlyContract`测试，七角色实际基础权重均与历史native SHA精确匹配、场景前后不变、dirty为空，输出`Saved/Pose17Development/asset_skin_data_a02`。首次构建误用private资产Nanite方法，已改为公开RenderData查询；失败日志保留。随后四机位400条历史RefToLocal SHA完全重建一致，200头锚点与native数值最大差0m，见内层`docs/POSE17_OFFLINE_LBS_DIAGNOSTIC.md`。这是几何数值重建证据，不是最终渲染表面、遮挡或正式数据准入。

## 入口和用途

`ReadAssetBaseSkinData(Asset, ExpectedIdentity, ExpectedHistoricalSkinWeightSHA256, OutData, OutError)`只读取已加载的显式SkeletalMesh。调用方从已有真实native行取精确mesh identity和实际skin-weight SHA；资产或SHA缺失、非小写64hex、身份不同直接拒绝。函数不读取文件、不写输出目录、不创建component/Actor、不切模式、不设置属性、不刷新Pose、不开PIE/MRQ、不保存或修改资产。返回值供真实UE调用方另行保存新JSON。

数据来源严格是`LODRenderData[0].SkinWeightVertexBuffer`导入基础buffer，不调用可能返回默认profile override的`LOD.GetSkinWeightVertexBuffer()`，也不把资产基础权重称为component实际effective权重。实际原始字节的SHA必须与历史native `skinWeightDataSHA256`精确一致；不同就失败，不能凭同名资产、相同顶点数、近似权重或放宽容差继续。成功仍记录`bComponentEffectiveWeightsRead=false`；它只证明本次基础字节与指定历史SHA相同。

## 输出契约

- `MeshIdentity`完整使用既有只读资产参考几何入口核验LOD0有序拓扑与float32参考几何SHA，与传入ExpectedIdentity逐字段相等；几何坐标本身继续引用已有同identity参考导出，不重复塞进本快照。
- `RawWeightDataBase64`是`GetDataVertexBuffer()->GetWeightData()`起始、`GetVertexDataSize()`长度的原字节，SHA方案与已发布采样相同`ue_component_lod0_fixed_skinweight_raw_v1`。不把lookup buffer或JSON字符串加入hash；变长影响拒绝，小端平台限定。另导出原长度、index/weight字节宽度、固定stride、weight offset、固定影响数。
- 逐顶点导出section索引、所有固定槽位的section局部骨、经实际`Section.BoneMap`映射后的全局骨、`GetBoneWeight()`返回的u16整数和float32归一化值。8-bit存储经引擎getter扩展为u16，不能把u16值误当raw存储字节。归一化与本机UE5.8采样源码相同：`float(raw_u16) * (1.0f/65535.0f)`，不按每点总和重新归一化、不丢零权重、不合并同骨。
- `Bones`按实际RefSkeleton有序导出骨名、parent、局部参考translation/rotation_xyzw/scale及资产`GetRefBasesInvMatrix()`真实16个float32值。逆矩阵同时有按骨序、每矩阵按行列序的小端float32原字节Base64和SHA，scheme为`ue_inverse_ref_pose_rowmajor_f32_le_v1`；不是当前RefToLocal。
- `Sections`包含实际BaseVertexIndex/NumVertices、BaseIndex/NumTriangles、material index、BoneMap及原disabled/unified标志；禁用/cloth/空或越界section、顶点区间重叠/未覆盖、三角跨section、骨调色板越界拒绝。另保存LOD.ActiveBoneIndices，供复现当前引擎矩阵填充逻辑使用。
- 读取前后同引擎帧、RenderData地址不变、基础权重字节完全相同后才输出成功；失败OutData回到空默认值，不能残留上一角色结果。这是静态本地读取稳定性，不是RGB/fence同步证据。

静态资产门禁另拒绝Nanite、任何资产morph target、默认/target mesh deformer配置、LOD0 cloth、空材质和当前RHI平台WPO材质。不创建component来关闭不支持状态。资产读取不能核查历史component的活跃morph、cloth模拟、deformer fallback、材质override/overlay或bone visibility/ref-pose override；这些仍需已有native每行完整eligibility和身份门禁，不能由这个静态快照替代。

## 已核对的本机引擎源码

`E:/UE_5.8/Engine/Source/Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h`定义基础buffer/getter及固定布局；`SkinnedMeshComponent.cpp`的`ComputeSkinnedPositions`和`GetTypedSkinnedVertexPosition`按section骨调色板解码并使用上述u16常量；`AnimationCore/Public/BoneWeights.h`定义`InvMaxRawBoneWeightFloat=1/65535`。`SkeletalMesh.h`公开`GetRefBasesInvMatrix`与参考骨接口。以上为本次只读源码核实，不是猜API，也不等同编译成功。

## 下一步真实闭环

1. 主agent安全重启/统一构建后执行`FutsalMOT.Pose17.SkinDataReadOnlyContract`；该small test只覆盖解码语义和拒绝空组件，不代表七资产通过。
2. 在真实UE一次逐七资产读取，分别传该角色历史native identity和唯一权重SHA。新文件保存到独立Saved目录；返回失败则保留错误，不创建临时component、修改现Actor或切profile补救。
3. CPU使用已落盘54个component-space骨Transform与本快照inverse reference、active bones复现UE实际RefToLocal的float32运算与填充，然后逐历史行精确重算`ue_ref_to_local_rowmajor_f32_le_v1` SHA。骨隐藏、ref-pose override、未活跃骨填充、矩阵运算舍入均可能使重建不符，不能用宽松数值容差绕过SHA。
4. 只有矩阵SHA一致，才用本快照实际权重与已有参考几何重建动态支持面并核验既有五表面锚点。未一致则后续采样需实际RefToLocal矩阵或支持顶点，本静态导出不伪造旧图几何同步。
5. 十二骨中心坐标保持不变；局部支持三角只用于可见性代理。先复用已渲染joint中间帧四EXR做候选，不再逐角色近景。骨中心Z、bbox、mask命中不成为遮挡真值，unknown不升级。

`bSceneOrAssetMutationPerformed=false`、`bDynamicSurfaceReconstructionVerified=false`是接口范围声明；真实UE调用还需前后场景/dirty/资源状态收据。API不会自动生成visibility、COCO标记或任何生产通过状态。
