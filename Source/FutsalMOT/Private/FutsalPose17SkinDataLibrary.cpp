#include "FutsalPose17SkinDataLibrary.h"

#include "CoreGlobals.h"
#include "Engine/SkeletalMesh.h"
#include "Materials/MaterialInterface.h"
#include "Misc/Base64.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkinWeightVertexBuffer.h"
#include "RHIShaderPlatform.h"
THIRD_PARTY_INCLUDES_START
#include <openssl/sha.h>
THIRD_PARTY_INCLUDES_END

namespace
{
bool HashSkinBytes(const TArray<uint8>& Bytes, FString& OutHash)
{
	uint8 Digest[SHA256_DIGEST_LENGTH];
	if (Bytes.IsEmpty() || !SHA256(Bytes.GetData(), static_cast<size_t>(Bytes.Num()), Digest)) return false;
	OutHash = BytesToHex(Digest, SHA256_DIGEST_LENGTH).ToLower();
	return true;
}

bool IsSHA256(const FString& Value)
{
	if (Value.Len() != 64) return false;
	for (const TCHAR C : Value)
		if (!((C >= '0' && C <= '9') || (C >= 'a' && C <= 'f'))) return false;
	return true;
}

bool SameSkinIdentity(const FFutsalPose17MeshIdentity& A, const FFutsalPose17MeshIdentity& B)
{
	return A.AssetPath == B.AssetPath && A.SignatureScheme == B.SignatureScheme && A.LOD == B.LOD
		&& A.VertexCount == B.VertexCount && A.TopologySHA256 == B.TopologySHA256 && A.GeometrySHA256 == B.GeometrySHA256;
}

bool AppendMatrixBytes(const FMatrix44f& Matrix, TArray<uint8>& Bytes, TArray<float>& Values)
{
	for (int32 Row = 0; Row < 4; ++Row)
		for (int32 Column = 0; Column < 4; ++Column)
		{
			const float Value = Matrix.M[Row][Column];
			if (!FMath::IsFinite(Value)) return false;
			Values.Add(Value);
			uint32 Bits; FMemory::Memcpy(&Bits, &Value, sizeof(Bits));
			for (int32 Shift = 0; Shift < 32; Shift += 8) Bytes.Add(static_cast<uint8>(Bits >> Shift));
		}
	return true;
}
}

bool UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(const TArray<int32>& BoneMap, int32 SkeletonBoneCount,
	const TArray<int32>& LocalIndices, const TArray<int32>& RawWeightsU16,
	TArray<int32>& OutGlobalIndices, TArray<float>& OutNormalizedWeights, FString& OutError)
{
	OutGlobalIndices.Reset(); OutNormalizedWeights.Reset(); OutError.Reset();
	if (SkeletonBoneCount <= 0 || LocalIndices.IsEmpty() || LocalIndices.Num() != RawWeightsU16.Num())
	{ OutError = TEXT("固定影响槽位为空或长度不同"); return false; }
	int64 WeightSum = 0;
	for (int32 Index = 0; Index < LocalIndices.Num(); ++Index)
	{
		const int32 Local = LocalIndices[Index], Raw = RawWeightsU16[Index];
		if (!BoneMap.IsValidIndex(Local) || BoneMap[Local] < 0 || BoneMap[Local] >= SkeletonBoneCount || Raw < 0 || Raw > 65535)
		{ OutError = TEXT("section局部骨/全局骨或实际u16权重越界"); return false; }
		WeightSum += Raw;
	}
	if (WeightSum == 0) { OutError = TEXT("顶点全部影响权重为零"); return false; }
	for (int32 Index = 0; Index < LocalIndices.Num(); ++Index)
	{
		OutGlobalIndices.Add(BoneMap[LocalIndices[Index]]);
		// 与UE5.8 GetTypedSkinnedVertexPosition使用相同float32常量，不重新归一化。
		OutNormalizedWeights.Add(static_cast<float>(RawWeightsU16[Index]) * (1.0f / 65535.0f));
	}
	return true;
}

bool UFutsalPose17SkinDataLibrary::ReadAssetBaseSkinData(USkeletalMesh* Asset,
	const FFutsalPose17MeshIdentity& ExpectedIdentity, const FString& ExpectedHistoricalSkinWeightSHA256,
	FFutsalPose17SkinData& OutData, FString& OutError)
{
	OutData = FFutsalPose17SkinData(); OutError.Reset();
	if (!IsInGameThread() || !IsValid(Asset) || !IsSHA256(ExpectedHistoricalSkinWeightSHA256))
	{ OutError = TEXT("只读导出需要游戏线程、显式实际资产和历史native小写SHA256"); return false; }
#if !PLATFORM_LITTLE_ENDIAN
	OutError = TEXT("当前raw权重方案只支持已验证的小端UE平台"); return false;
#endif
	FFutsalPose17SkinData Data;
	Data.EngineFrameBefore = static_cast<int64>(GFrameCounter);
	Data.ExpectedHistoricalSkinWeightSHA256 = ExpectedHistoricalSkinWeightSHA256;
	TArray<FVector> ReferencePositions;
	TArray<FIntVector> Triangles;
	if (!UFutsalPose17Library::ReadAssetReferenceGeometry(Asset, ReferencePositions, Triangles, Data.MeshIdentity, OutError)) return false;
	if (!SameSkinIdentity(Data.MeshIdentity, ExpectedIdentity))
	{ OutError = TEXT("实际LOD0 mesh身份不匹配，不能跨角色复用权重"); return false; }
	Data.AssetMorphTargetCount = Asset->GetMorphTargets().Num();
	const FSkeletalMeshRenderData* Render = Asset->GetResourceForRendering();
	if (!Render || !Render->LODRenderData.IsValidIndex(0)) { OutError = TEXT("LOD0 RenderData不可读"); return false; }
	if (Render->HasValidNaniteData() || Data.AssetMorphTargetCount != 0
		|| Asset->GetDefaultMeshDeformer() || Asset->GetTargetMeshDeformers())
	{ OutError = TEXT("只读基础导出拒绝Nanite、资产morph或deformer配置；不会修改资产以绕过"); return false; }
	Data.MaterialShaderPlatform = FString::FromInt(static_cast<int32>(GMaxRHIShaderPlatform));
	if (GMaxRHIShaderPlatform == SP_NumPlatforms)
	{ OutError = TEXT("没有有效当前RHI材质平台，不能推定无WPO"); return false; }
	Data.AssetMaterialCount = Asset->GetMaterials().Num();
	if (Data.AssetMaterialCount == 0) { OutError = TEXT("资产缺实际材质slot"); return false; }
	for (const FSkeletalMaterial& Slot : Asset->GetMaterials())
		if (!Slot.MaterialInterface || Slot.MaterialInterface->IsUsingWorldPositionOffset_Concurrent(GMaxRHIShaderPlatform))
		{ OutError = TEXT("资产材质缺失或使用WPO，超出本只读基础蒙皮范围"); return false; }
	const FSkeletalMeshLODRenderData& LOD = Render->LODRenderData[0];
	if (LOD.HasClothData()) { OutError = TEXT("资产LOD0含cloth数据"); return false; }
	// 只读取导入基础buffer；GetSkinWeightVertexBuffer可能返回默认profile override，不混淆来源。
	const FSkinWeightVertexBuffer& Weights = LOD.SkinWeightVertexBuffer;
	const FSkinWeightDataVertexBuffer* Buffer = Weights.GetDataVertexBuffer();
	if (!Buffer || !Buffer->GetWeightData() || Buffer->GetVariableBonesPerVertex()
		|| Buffer->GetVertexDataSize() == 0 || Buffer->GetVertexDataSize() > MAX_int32
		|| Weights.GetNumVertices() != static_cast<uint32>(Data.MeshIdentity.VertexCount)
		|| Weights.GetMaxBoneInfluences() == 0 || Weights.GetMaxBoneInfluences() > MAX_int32)
	{ OutError = TEXT("基础权重CPU数据不可读、变长影响或顶点数不符；不触发CPU模式/资源重建"); return false; }
	TArray<uint8> RawWeights;
	RawWeights.Append(Buffer->GetWeightData(), static_cast<int32>(Buffer->GetVertexDataSize()));
	if (!HashSkinBytes(RawWeights, Data.SkinWeightDataSHA256) || Data.SkinWeightDataSHA256 != ExpectedHistoricalSkinWeightSHA256)
	{ OutError = TEXT("资产基础权重SHA与历史component实际有效权重不同；拒绝推定profile/override等价"); return false; }
	Data.bHistoricalNativeWeightSHA256Matched = true;
	Data.RawWeightDataBase64 = FBase64::Encode(RawWeights);
	Data.RawWeightDataByteCount = RawWeights.Num();
	Data.BoneIndexByteSize = static_cast<int32>(Weights.GetBoneIndexByteSize());
	Data.BoneWeightByteSize = static_cast<int32>(Weights.GetBoneWeightByteSize());
	Data.ConstantVertexStrideBytes = static_cast<int32>(Weights.GetConstantInfluencesVertexStride());
	Data.ConstantWeightsOffsetBytes = static_cast<int32>(Weights.GetConstantInfluencesBoneWeightsOffset());
	Data.MaxBoneInfluences = static_cast<int32>(Weights.GetMaxBoneInfluences());
	Data.RawWeightToFloatMultiplier = 1.0f / 65535.0f;
	if ((Data.BoneIndexByteSize != 1 && Data.BoneIndexByteSize != 2)
		|| (Data.BoneWeightByteSize != 1 && Data.BoneWeightByteSize != 2)
		|| static_cast<uint64>(Data.ConstantVertexStrideBytes) * Weights.GetNumVertices() != static_cast<uint64>(RawWeights.Num())
		|| Data.ConstantVertexStrideBytes != (Data.BoneIndexByteSize + Data.BoneWeightByteSize) * Data.MaxBoneInfluences
		|| Data.ConstantWeightsOffsetBytes != Data.BoneIndexByteSize * Data.MaxBoneInfluences)
	{ OutError = TEXT("固定权重布局与实际buffer字节数不一致"); return false; }
	const FReferenceSkeleton& Skeleton = Asset->GetRefSkeleton();
	const TArray<FMatrix44f>& Inverses = Asset->GetRefBasesInvMatrix();
	const TArray<FTransform>& RefLocals = Skeleton.GetRefBonePose();
	if (Skeleton.GetNum() == 0 || Inverses.Num() != Skeleton.GetNum() || RefLocals.Num() != Skeleton.GetNum())
	{ OutError = TEXT("实际参考骨/逆绑定矩阵数量不一致"); return false; }
	TArray<uint8> InverseBytes;
	TSet<FName> BoneNames;
	for (int32 Index = 0; Index < Skeleton.GetNum(); ++Index)
	{
		FFutsalPose17SkinBone Bone;
		Bone.Name = Skeleton.GetBoneName(Index); Bone.ParentIndex = Skeleton.GetParentIndex(Index);
		if (Bone.Name.IsNone() || BoneNames.Contains(Bone.Name) || Bone.ParentIndex < INDEX_NONE || Bone.ParentIndex >= Index || RefLocals[Index].ContainsNaN())
		{ OutError = TEXT("参考骨名、parent或局部Transform无效"); return false; }
		BoneNames.Add(Bone.Name);
		const FVector Translation = RefLocals[Index].GetTranslation(), Scale = RefLocals[Index].GetScale3D();
		const FQuat Rotation = RefLocals[Index].GetRotation();
		Bone.ReferenceLocalTranslationCm = {Translation.X, Translation.Y, Translation.Z};
		Bone.ReferenceLocalRotationXyzw = {Rotation.X, Rotation.Y, Rotation.Z, Rotation.W};
		Bone.ReferenceLocalScaleXyz = {Scale.X, Scale.Y, Scale.Z};
		if (!AppendMatrixBytes(Inverses[Index], InverseBytes, Bone.InverseReferenceRowMajorF32))
		{ OutError = TEXT("逆参考矩阵存在非有限float32"); return false; }
		Data.Bones.Add(MoveTemp(Bone));
	}
	if (!HashSkinBytes(InverseBytes, Data.InverseReferenceMatricesSHA256))
	{ OutError = TEXT("逆参考矩阵SHA失败"); return false; }
	Data.InverseReferenceMatricesBase64 = FBase64::Encode(InverseBytes);
	for (FBoneIndexType Index : LOD.ActiveBoneIndices)
	{
		if (Index >= Skeleton.GetNum()) { OutError = TEXT("实际LOD活跃骨越界"); return false; }
		Data.ActiveBoneIndices.Add(static_cast<int32>(Index));
	}
	Data.Vertices.SetNum(Data.MeshIdentity.VertexCount);
	TArray<bool> Visited;
	Visited.Init(false, Data.MeshIdentity.VertexCount);
	for (int32 SectionIndex = 0; SectionIndex < LOD.RenderSections.Num(); ++SectionIndex)
	{
		const FSkelMeshRenderSection& Section = LOD.RenderSections[SectionIndex];
		if (Section.bDisabled || Section.HasClothingData() || Section.NumVertices == 0 || Section.NumTriangles == 0 || Section.BaseIndex % 3 != 0
			|| static_cast<uint64>(Section.BaseVertexIndex) + Section.NumVertices > static_cast<uint64>(Data.MeshIdentity.VertexCount)
			|| static_cast<uint64>(Section.BaseIndex) + static_cast<uint64>(Section.NumTriangles) * 3 > static_cast<uint64>(Triangles.Num()) * 3
			|| Section.MaterialIndex >= Data.AssetMaterialCount)
		{ OutError = TEXT("section禁用、cloth、为空或实际顶点/拓扑/材质范围越界"); return false; }
		FFutsalPose17SkinSection OutSection;
		OutSection.SectionIndex = SectionIndex; OutSection.BaseVertexIndex = static_cast<int32>(Section.BaseVertexIndex);
		OutSection.VertexCount = static_cast<int32>(Section.NumVertices); OutSection.BaseIndex = static_cast<int32>(Section.BaseIndex);
		OutSection.TriangleCount = static_cast<int32>(Section.NumTriangles); OutSection.MaterialIndex = Section.MaterialIndex;
		OutSection.bDisabled = Section.bDisabled; OutSection.bUnifiedBoneMap = Section.bUnifiedBoneMap;
		for (uint32 LocalTriangle = 0; LocalTriangle < Section.NumTriangles; ++LocalTriangle)
		{
			const FIntVector& Triangle = Triangles[Section.BaseIndex / 3 + LocalTriangle];
			for (int32 Axis = 0; Axis < 3; ++Axis)
				if (Triangle[Axis] < static_cast<int32>(Section.BaseVertexIndex)
					|| static_cast<uint64>(Triangle[Axis]) >= static_cast<uint64>(Section.BaseVertexIndex) + Section.NumVertices)
				{ OutError = TEXT("section实际三角引用其他section顶点，拒绝猜测骨调色板"); return false; }
		}
		for (FBoneIndexType Index : Section.BoneMap)
		{
			if (Index >= Skeleton.GetNum()) { OutError = TEXT("section BoneMap全局骨越界"); return false; }
			OutSection.BoneMap.Add(static_cast<int32>(Index));
		}
		for (uint32 LocalVertex = 0; LocalVertex < Section.NumVertices; ++LocalVertex)
		{
			const uint32 Vertex = Section.BaseVertexIndex + LocalVertex;
			if (Visited[Vertex]) { OutError = TEXT("section顶点范围重叠"); return false; }
			Visited[Vertex] = true;
			FFutsalPose17SkinVertex& OutVertex = Data.Vertices[Vertex];
			OutVertex.VertexIndex = static_cast<int32>(Vertex); OutVertex.SectionIndex = SectionIndex;
			for (uint32 Influence = 0; Influence < Weights.GetMaxBoneInfluences(); ++Influence)
			{
				const uint32 LocalBone = Weights.GetBoneIndex(Vertex, Influence);
				if (LocalBone > MAX_int32) { OutError = TEXT("section局部骨索引超过int32"); return false; }
				OutVertex.SectionLocalBoneIndices.Add(static_cast<int32>(LocalBone));
				OutVertex.RawWeightsU16.Add(static_cast<int32>(Weights.GetBoneWeight(Vertex, Influence)));
			}
			if (!ResolveSectionInfluences(OutSection.BoneMap, Skeleton.GetNum(), OutVertex.SectionLocalBoneIndices,
				OutVertex.RawWeightsU16, OutVertex.GlobalBoneIndices, OutVertex.NormalizedWeights, OutError)) return false;
		}
		Data.Sections.Add(MoveTemp(OutSection));
	}
	if (Data.Sections.IsEmpty() || Visited.Contains(false)) { OutError = TEXT("section未完整覆盖实际LOD0顶点"); return false; }
	Data.EngineFrameAfter = static_cast<int64>(GFrameCounter);
	TArray<uint8> FinalRaw;
	if (Asset->GetResourceForRendering() != Render || !Buffer->GetWeightData() || Buffer->GetVertexDataSize() != static_cast<uint32>(RawWeights.Num()))
	{ OutError = TEXT("读取期间实际RenderData/权重buffer改变"); return false; }
	FinalRaw.Append(Buffer->GetWeightData(), RawWeights.Num());
	Data.bLocalReadStable = Data.EngineFrameBefore == Data.EngineFrameAfter && FinalRaw == RawWeights;
	if (!Data.bLocalReadStable) { OutError = TEXT("读取期间引擎帧或基础权重字节改变"); return false; }
	Data.bReadSucceeded = true;
	OutData = MoveTemp(Data);
	return true;
}
