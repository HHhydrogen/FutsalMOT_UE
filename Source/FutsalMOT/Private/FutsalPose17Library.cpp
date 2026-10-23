#include "FutsalPose17Library.h"
#include "CoreGlobals.h"

#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimInstance.h"
#include "Animation/Skeleton.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInterface.h"
#include "HAL/IConsoleManager.h"
#include "LODSyncInterface.h"
#include "RenderingThread.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/PositionVertexBuffer.h"
#include "Rendering/SkinWeightVertexBuffer.h"
#include "RHIGlobals.h"
#include "RawIndexBuffer.h"
#include "SkeletalRenderPublic.h"
THIRD_PARTY_INCLUDES_START
#include <openssl/sha.h>
THIRD_PARTY_INCLUDES_END

namespace
{
const TCHAR* PointNames[] = { TEXT("nose"), TEXT("left_eye"), TEXT("right_eye"), TEXT("left_ear"), TEXT("right_ear"),
	TEXT("left_shoulder"), TEXT("right_shoulder"), TEXT("left_elbow"), TEXT("right_elbow"), TEXT("left_wrist"), TEXT("right_wrist"),
	TEXT("left_hip"), TEXT("right_hip"), TEXT("left_knee"), TEXT("right_knee"), TEXT("left_ankle"), TEXT("right_ankle") };
const TCHAR* LimbBones[] = { TEXT("upperarm_l"), TEXT("upperarm_r"), TEXT("lowerarm_l"), TEXT("lowerarm_r"),
	TEXT("hand_l"), TEXT("hand_r"), TEXT("thigh_l"), TEXT("thigh_r"), TEXT("calf_l"), TEXT("calf_r"), TEXT("foot_l"), TEXT("foot_r") };

void AppendU32LE(TArray<uint8>& Bytes, uint32 Value)
{
	for (int32 Shift = 0; Shift < 32; Shift += 8) Bytes.Add(static_cast<uint8>(Value >> Shift));
}

bool HashBytes(const TArray<uint8>& Bytes, FString& OutHash)
{
	uint8 Digest[SHA256_DIGEST_LENGTH];
	if (!SHA256(Bytes.GetData(), static_cast<size_t>(Bytes.Num()), Digest)) return false;
	OutHash = BytesToHex(Digest, SHA256_DIGEST_LENGTH).ToLower();
	return true;
}

bool IsExplicitVisibleMesh(USkeletalMeshComponent* Mesh, FString& Error)
{
	if (!IsInGameThread() || !IsValid(Mesh) || !Mesh->IsRegistered() || !Mesh->GetSkeletalMeshAsset()
		|| !Mesh->IsVisible() || Mesh->bHiddenInGame || !IsValid(Mesh->GetOwner()) || Mesh->GetOwner()->IsHidden()
		|| Mesh->GetFName() == TEXT("CharacterMesh0"))
	{
		Error = TEXT("须显式提供已注册且可见的实际角色 VisualMesh；拒绝隐藏驱动底模及非游戏线程");
		return false;
	}
	return true;
}

bool ReadAssetTopology(USkeletalMesh* Asset, FFutsalPose17MeshIdentity& Identity, TArray<uint32>& Indices, FString& Error)
{
	if (!IsInGameThread() || !IsValid(Asset)) { Error = TEXT("只读资产拓扑需要有效 SkeletalMesh 和游戏线程"); return false; }
	const FSkeletalMeshRenderData* Render = Asset->GetResourceForRendering();
	if (!Render || !Render->LODRenderData.IsValidIndex(0))
	{
		Error = TEXT("实际网格未加载 LOD0 RenderData"); return false;
	}
	const FSkeletalMeshLODRenderData& LOD = Render->LODRenderData[0];
	const FPositionVertexBuffer& Positions = LOD.StaticVertexBuffers.PositionVertexBuffer;
	if (!Positions.GetVertexData() || Positions.GetNumVertices() == 0 || !LOD.MultiSizeIndexContainer.IsIndexBufferValid())
	{
		Error = TEXT("LOD0 缺少可读取的 CPU 参考顶点或 IndexBuffer"); return false;
	}
	if (LOD.MultiSizeIndexContainer.GetIndexBuffer()->GetResourceDataSize() <= 0)
	{
		Error = TEXT("LOD0 CPU 三角索引已释放，不调用可能断言的索引读取 API"); return false;
	}
	LOD.MultiSizeIndexContainer.GetIndexBuffer(Indices);
	if (Indices.IsEmpty() || Indices.Num() % 3 != 0)
	{
		Error = TEXT("LOD0 三角索引为空或不完整"); return false;
	}
	TArray<uint8> TopologyBytes, GeometryBytes;
	TopologyBytes.Reserve(Indices.Num() * 4);
	GeometryBytes.Reserve(Positions.GetNumVertices() * 12);
	for (uint32 Index : Indices)
	{
		if (Index >= Positions.GetNumVertices()) { Error = TEXT("LOD0 三角顶点越界"); return false; }
		AppendU32LE(TopologyBytes, Index);
	}
	for (uint32 Index = 0; Index < Positions.GetNumVertices(); ++Index)
	{
		const FVector3f Position = Positions.VertexPosition(Index);
		if (Position.ContainsNaN()) { Error = TEXT("参考顶点包含非有限值"); return false; }
		for (int32 Axis = 0; Axis < 3; ++Axis)
		{
			const float Value = Position[Axis];
			uint32 Bits; FMemory::Memcpy(&Bits, &Value, sizeof(Bits));
			AppendU32LE(GeometryBytes, Bits);
		}
	}
	Identity = FFutsalPose17MeshIdentity();
	Identity.AssetPath = Asset->GetPathName();
	Identity.VertexCount = static_cast<int32>(Positions.GetNumVertices());
	if (!HashBytes(TopologyBytes, Identity.TopologySHA256) || !HashBytes(GeometryBytes, Identity.GeometrySHA256))
	{
		Error = TEXT("平台 SHA256 计算失败"); return false;
	}
	return true;
}

bool ReadTopology(USkeletalMeshComponent* Mesh, FFutsalPose17MeshIdentity& Identity, TArray<uint32>& Indices, FString& Error)
{
	return IsExplicitVisibleMesh(Mesh, Error) && ReadAssetTopology(Mesh->GetSkeletalMeshAsset(), Identity, Indices, Error);
}

bool SameIdentity(const FFutsalPose17MeshIdentity& A, const FFutsalPose17MeshIdentity& B)
{
	return A.AssetPath == B.AssetPath && A.LOD == B.LOD && A.VertexCount == B.VertexCount
		&& A.SignatureScheme == B.SignatureScheme && A.TopologySHA256 == B.TopologySHA256
		&& A.GeometrySHA256 == B.GeometrySHA256;
}

bool CheckNoLODOverride(FString& Error)
{
	const IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("r.SkeletalMeshForceLOD"));
	if (!Variable || Variable->GetInt() != -1)
	{
		Error = TEXT("诊断要求 r.SkeletalMeshForceLOD=-1，不能把全局 override 当作组件原始 LOD"); return false;
	}
	return true;
}

bool SameMorphCurves(const TMap<FName, float>& A, const TMap<FName, float>& B)
{
	if (A.Num() != B.Num()) return false;
	for (const auto& Entry : A)
	{
		const float* Value = B.Find(Entry.Key);
		if (!Value || *Value != Entry.Value) return false;
	}
	return true;
}

bool ReadPoseBasis(USkeletalMeshComponent* Mesh, FFutsalPose17Sample& Sample, TArray<FMatrix44f>& Matrices, FString& Error)
{
	const USkinnedMeshComponent* Base = Mesh->GetBaseComponent();
	if (!Base || !Base->GetSkinnedAsset()) { Error = TEXT("当前实际骨pose来源无效"); return false; }
	const auto& Transforms = Base->GetComponentSpaceTransforms();
	const FReferenceSkeleton& Skeleton = Base->GetSkinnedAsset()->GetRefSkeleton();
	if (Transforms.Num() != Skeleton.GetNum()) { Error = TEXT("实际组件空间骨pose尚未完整评估"); return false; }
	Sample.BoneSpaceBaseComponentPath = Base->GetPathName();
	Sample.BoneSpaceBaseTransformsUECm = Transforms;
	Sample.BonePoseTransformEncoding = TEXT("ue_transform_translation_cm_quat_xyzw_scale_xyz_v1");
	for (int32 Index = 0; Index < Skeleton.GetNum(); ++Index)
	{
		if (Transforms[Index].ContainsNaN()) { Error = TEXT("实际骨pose包含非有限值"); return false; }
		Sample.BoneSpaceBaseNames.Add(Skeleton.GetBoneName(Index));
	}
	Mesh->GetCurrentRefToLocalMatrices(Matrices, 0);
	if (Matrices.Num() != Mesh->GetSkeletalMeshAsset()->GetRefSkeleton().GetNum())
	{
		Error = TEXT("LOD0实际RefToLocal矩阵数量不符"); return false;
	}
	TArray<uint8> Bytes;
	for (const FMatrix44f& Matrix : Matrices)
		for (int32 Row = 0; Row < 4; ++Row)
			for (int32 Column = 0; Column < 4; ++Column)
			{
				const float Value = Matrix.M[Row][Column];
				if (!FMath::IsFinite(Value)) { Error = TEXT("RefToLocal矩阵非有限"); return false; }
				uint32 Bits; FMemory::Memcpy(&Bits, &Value, sizeof(Bits)); AppendU32LE(Bytes, Bits);
			}
	Sample.bRenderCPUEnabledAtRead = Mesh->GetCPUSkinningEnabled();
	Sample.bRenderStaticAtRead = Mesh->bRenderStatic;
	Sample.PredictedLODAtRead = Mesh->GetPredictedLODLevel();
	Sample.RefToLocalSignatureScheme = TEXT("ue_ref_to_local_rowmajor_f32_le_v1");
	return HashBytes(Bytes, Sample.RefToLocalMatricesSHA256);
}
}

bool UFutsalPose17Library::ValidateGPUVisualLBS(USkeletalMeshComponent* VisualMesh, FString& OutError,
	FFutsalPose17GPULBSEligibility* OutEligibility)
{
	OutError.Reset();
	FFutsalPose17GPULBSEligibility Eligibility;
	if (OutEligibility) *OutEligibility = Eligibility;
	if (!IsExplicitVisibleMesh(VisualMesh, OutError) || !CheckNoLODOverride(OutError)) return false;
	if (!VisualMesh->GetWorld()) { OutError = TEXT("GPU/LBS实际组件没有World"); return false; }
	const USkeletalMeshComponent* Leader = Cast<USkeletalMeshComponent>(VisualMesh->LeaderPoseComponent.Get());
	Eligibility.bChecksExecuted = true;
	Eligibility.bPIEWorld = VisualMesh->GetWorld() && VisualMesh->GetWorld()->WorldType == EWorldType::PIE;
	Eligibility.bRenderCPUEnabled = VisualMesh->GetCPUSkinningEnabled(); Eligibility.bRenderStatic = VisualMesh->bRenderStatic;
	Eligibility.bHasNaniteData = VisualMesh->HasValidNaniteData();
	Eligibility.bParallelEvaluationRunning = VisualMesh->IsRunningParallelEvaluation();
	Eligibility.bLeaderParallelEvaluationRunning = Leader && Leader->IsRunningParallelEvaluation();
	for (float Weight : VisualMesh->MorphTargetWeights)
		if (!FMath::IsFinite(Weight) || FMath::Abs(Weight) > 1.e-8f)
		{ ++Eligibility.ActiveMorphWeightCount; Eligibility.bNonFiniteMorphWeights |= !FMath::IsFinite(Weight); }
	for (const auto& Curve : VisualMesh->GetMorphTargetCurves())
		if (!FMath::IsFinite(Curve.Value) || FMath::Abs(Curve.Value) > 1.e-8f)
		{ ++Eligibility.ManualMorphCurveCount; Eligibility.bNonFiniteMorphWeights |= !FMath::IsFinite(Curve.Value); }
	for (const auto& Sets : VisualMesh->GetExternalMorphSetsArray())
		Eligibility.ExternalMorphSetCount += Sets.Num();
	Eligibility.ClothSimulationCount = VisualMesh->GetClothingSimulationInstances().Num();
	// UE5.8公开HasMeshDeformer直接查询有效集合，覆盖component/asset/project fallback。
	// 引擎当前有效集合仅支持0或1个（SkinnedMeshComponent.cpp:GetActiveMeshDeformers），不是用实例数猜资产数。
	Eligibility.MeshDeformerAssetCount = VisualMesh->HasMeshDeformer() ? 1 : 0;
	Eligibility.MeshDeformerInstanceCount = VisualMesh->GetMeshDeformerInstances().DeformerInstances.Num();
	const auto* Render = VisualMesh->GetSkeletalMeshAsset()->GetResourceForRendering();
	if (!Render || !Render->LODRenderData.IsValidIndex(0))
	{
		if (OutEligibility) *OutEligibility = Eligibility; OutError = TEXT("GPU/LBS缺少实际LOD0"); return false;
	}
	const auto& LOD = Render->LODRenderData[0];
	Eligibility.ReferenceVertexCount = LOD.GetNumVertices(); Eligibility.bLod0HasClothData = LOD.HasClothData();
	for (const auto& Section : LOD.RenderSections) Eligibility.Lod0ClothSectionCount += Section.HasClothingData() ? 1 : 0;
	const FSkinWeightVertexBuffer* Weights = VisualMesh->GetSkinWeightBuffer(0);
	if (Weights)
	{
		Eligibility.WeightVertexCount = Weights->GetNumVertices(); Eligibility.MaxBoneInfluences = Weights->GetMaxBoneInfluences();
		Eligibility.bVariableInfluenceWeights = Weights->GetDataVertexBuffer()->GetVariableBonesPerVertex();
		Eligibility.bWeightsReadable = Weights->GetDataVertexBuffer()->GetWeightData() != nullptr;
	}
	const EShaderPlatform Platform = GetFeatureLevelShaderPlatform(VisualMesh->GetWorld()->GetFeatureLevel());
	for (int32 Slot = 0; Slot < VisualMesh->GetNumMaterials(); ++Slot)
	{
		const UMaterialInterface* Material = VisualMesh->GetMaterial(Slot);
		if (!Material) ++Eligibility.NullMaterialSlotCount;
		else if (Material->IsUsingWorldPositionOffset_Concurrent(Platform)) ++Eligibility.MaterialWPOSlotCount;
	}
	// Overlay也可能单独改变渲染位置，不能只检查基础slot。
	const UMaterialInterface* Overlay = VisualMesh->GetOverlayMaterial();
	if (Overlay && Overlay->IsUsingWorldPositionOffset_Concurrent(Platform)) ++Eligibility.MaterialWPOSlotCount;
	Eligibility.bEligible = Eligibility.bPIEWorld && !Eligibility.bRenderCPUEnabled && !Eligibility.bRenderStatic
		&& !Eligibility.bHasNaniteData && !Eligibility.bParallelEvaluationRunning && !Eligibility.bLeaderParallelEvaluationRunning
		&& Eligibility.ActiveMorphWeightCount == 0 && Eligibility.ManualMorphCurveCount == 0 && Eligibility.ExternalMorphSetCount == 0
		&& Eligibility.ClothSimulationCount == 0 && Eligibility.Lod0ClothSectionCount == 0 && !Eligibility.bLod0HasClothData
		&& Eligibility.MeshDeformerAssetCount == 0 && Eligibility.MeshDeformerInstanceCount == 0
		&& Eligibility.MaterialWPOSlotCount == 0 && Eligibility.NullMaterialSlotCount == 0 && !Eligibility.bNonFiniteMorphWeights
		&& Eligibility.bWeightsReadable && !Eligibility.bVariableInfluenceWeights && Eligibility.MaxBoneInfluences > 0 && Eligibility.ReferenceVertexCount > 0
		&& Eligibility.WeightVertexCount == Eligibility.ReferenceVertexCount && LOD.StaticVertexBuffers.PositionVertexBuffer.GetVertexData();
	if (OutEligibility) *OutEligibility = Eligibility;
	if (!Eligibility.bEligible) OutError = TEXT("GPU/LBS只读门禁拒绝：检查原生eligibility实际计数/布尔；不关闭morph/cloth/deformer/WPO来伪装支持");
	return Eligibility.bEligible;
}

bool UFutsalPose17Library::PrepareGPUVisualLBS(USkeletalMeshComponent* VisualMesh, FFutsalPose17CPUState& OutPreviousState, FString& OutError)
{
	if (!ValidateGPUVisualLBS(VisualMesh, OutError) || !GetVisualSamplingState(VisualMesh, OutPreviousState, OutError)) return false;
	VisualMesh->SetForcedLOD(1); // 只锁LOD0，绝不切CPU render或调用重评顶点接口。
	return true;
}

bool UFutsalPose17Library::RestoreGPUVisualLBS(USkeletalMeshComponent* VisualMesh, const FFutsalPose17CPUState& PreviousState, FString& OutError)
{
	OutError.Reset();
	if (!IsInGameThread() || !IsValid(VisualMesh) || !VisualMesh->GetWorld() || VisualMesh->GetWorld()->WorldType != EWorldType::PIE
		|| VisualMesh->GetPathName() != PreviousState.ComponentPath || !VisualMesh->GetSkeletalMeshAsset()
		|| VisualMesh->GetSkeletalMeshAsset()->GetPathName() != PreviousState.AssetPath || PreviousState.bCPUEnabled
		|| VisualMesh->GetCPUSkinningEnabled() || !CheckNoLODOverride(OutError))
	{
		if (OutError.IsEmpty()) OutError = TEXT("GPU/LBS恢复要求同PIE组件/mesh且CPU始终关闭"); return false;
	}
	ILODSyncInterface* LOD = Cast<ILODSyncInterface>(VisualMesh);
	if (!LOD) { OutError = TEXT("GPU/LBS恢复缺少公开LOD接口"); return false; }
	LOD->SetForceRenderedLOD(PreviousState.ForceRenderedLOD); LOD->SetForceStreamedLOD(PreviousState.ForceStreamedLOD);
	if (LOD->GetForceRenderedLOD() != PreviousState.ForceRenderedLOD || LOD->GetForceStreamedLOD() != PreviousState.ForceStreamedLOD)
	{
		OutError = TEXT("GPU/LBS LOD恢复读回不同"); return false;
	}
	return true;
}

bool UFutsalPose17Library::SynchronizeGPUVisualLBS(const TArray<USkeletalMeshComponent*>& VisualMeshes, FString& OutError)
{
	OutError.Reset();
	if (VisualMeshes.IsEmpty()) { OutError = TEXT("GPU/LBS不能同步空目标集合"); return false; }
	UWorld* World = nullptr;
	TArray<uint32> Revisions;
	const int64 Frame = static_cast<int64>(GFrameCounter);
	for (USkeletalMeshComponent* Mesh : VisualMeshes)
	{
		if (!ValidateGPUVisualLBS(Mesh, OutError)) return false;
		if ((World && World != Mesh->GetWorld()) || Mesh->GetPredictedLODLevel() != 0)
		{
			OutError = TEXT("GPU/LBS同步必须同一PIE World及实际LOD0"); return false;
		}
		World = Mesh->GetWorld(); Revisions.Add(Mesh->GetBoneTransformRevisionNumber()); Mesh->MarkRenderDynamicDataDirty();
	}
	// 排空已存在及本次end-frame异步任务，再等待RT/RHI；不重评动画、不切VF。
	World->FinishAsyncSendAllEndOfFrameUpdates(); World->SendAllEndOfFrameUpdates();
	World->FinishAsyncSendAllEndOfFrameUpdates(); FlushRenderingCommands();
	for (int32 Index = 0; Index < VisualMeshes.Num(); ++Index)
		if (Frame != static_cast<int64>(GFrameCounter) || Revisions[Index] != VisualMeshes[Index]->GetBoneTransformRevisionNumber()
			|| VisualMeshes[Index]->GetCPUSkinningEnabled())
		{
			OutError = TEXT("GPU/LBS提交fence期间引擎帧/Pose/实际GPU模式变化"); return false;
		}
	return true;
}

bool UFutsalPose17Library::SampleVisualPose17GPULBS(USkeletalMeshComponent* VisualMesh,
	const FFutsalPose17MeshIdentity& ExpectedIdentity, const TArray<FFutsalPose17SurfaceAnchor>& HeadAnchors,
	const FString& ManifestSHA256, FFutsalPose17Sample& OutSample, FString& OutError)
{
	OutSample = FFutsalPose17Sample(); OutError.Reset();
	if (!ValidateGPUVisualLBS(VisualMesh, OutError, &OutSample.GpuLbsEligibility)) return false;
	if (VisualMesh->GetPredictedLODLevel() != 0) { OutError = TEXT("GPU/LBS采样不是实际LOD0"); return false; }
	if (!ValidatePose17AssetBinding(VisualMesh->GetSkeletalMeshAsset(), ExpectedIdentity, HeadAnchors, ManifestSHA256, OutError)) return false;
	OutSample.MeshIdentity = ExpectedIdentity; OutSample.ComponentPath = VisualMesh->GetPathName(); OutSample.ManifestSHA256 = ManifestSHA256;
	OutSample.SamplingMethod = TEXT("gpu_render_component_pose_cpu_lbs_no_morph_cloth_deformer_wpo_diagnostic");
	OutSample.EngineFrameBefore = static_cast<int64>(GFrameCounter); OutSample.PoseRevisionBefore = VisualMesh->GetBoneTransformRevisionNumber();
	const FTransform ComponentTransform = VisualMesh->GetComponentTransform();
	TArray<FMatrix44f> Matrices;
	if (!ReadPoseBasis(VisualMesh, OutSample, Matrices, OutError)) return false;
	const auto& LOD = VisualMesh->GetSkeletalMeshAsset()->GetResourceForRendering()->LODRenderData[0];
	const FSkinWeightVertexBuffer* Weights = VisualMesh->GetSkinWeightBuffer(0);
	TArray<uint8> WeightBytes;
	WeightBytes.Append(Weights->GetDataVertexBuffer()->GetWeightData(), Weights->GetDataVertexBuffer()->GetVertexDataSize());
	if (!HashBytes(WeightBytes, OutSample.SkinWeightDataSHA256)) { OutError = TEXT("实际skin weight签名失败"); return false; }
	OutSample.SkinWeightSignatureScheme = TEXT("ue_component_lod0_fixed_skinweight_raw_v1");
	TArray<FVector3f> Positions;
	// 公开引擎API仅按实际参考点/skin weights/当前RefToLocal计算坐标，不切换渲染MeshObject或VF。
	USkinnedMeshComponent::ComputeSkinnedPositions(VisualMesh, Positions, Matrices, LOD, *Weights);
	if (Positions.Num() != ExpectedIdentity.VertexCount) { OutError = TEXT("GPU/LBS输出顶点数不同"); return false; }
	for (const auto& Anchor : HeadAnchors)
	{
		FVector Position;
		if (!InterpolateTriangle(FVector(Positions[Anchor.TriangleVertices.X]), FVector(Positions[Anchor.TriangleVertices.Y]),
			FVector(Positions[Anchor.TriangleVertices.Z]), Anchor.Barycentric, Position, OutError)) return false;
		OutSample.WorldPointsM.Add(ComponentTransform.TransformPosition(Position)*.01);
	}
	for (const TCHAR* BoneName : LimbBones)
	{
		const int32 Bone = VisualMesh->GetBoneIndex(FName(BoneName));
		if (Bone == INDEX_NONE) { OutError = TEXT("GPU/LBS实际骨骼缺失"); return false; }
		OutSample.WorldPointsM.Add(VisualMesh->GetBoneTransform(Bone).GetLocation()*.01);
	}
	for (const TCHAR* Name : PointNames) OutSample.KeypointNames.Add(FName(Name));
	OutSample.WorldTimeSeconds = VisualMesh->GetWorld()->GetTimeSeconds();
	OutSample.EngineFrameAfter = static_cast<int64>(GFrameCounter); OutSample.PoseRevisionAfter = VisualMesh->GetBoneTransformRevisionNumber();
	OutSample.bLocalReadStable = OutSample.EngineFrameBefore == OutSample.EngineFrameAfter
		&& OutSample.PoseRevisionBefore == OutSample.PoseRevisionAfter && ComponentTransform.Equals(VisualMesh->GetComponentTransform(),0)
		&& VisualMesh->GetSkinWeightBuffer(0) == Weights && !VisualMesh->GetCPUSkinningEnabled();
	for (const FVector& Point : OutSample.WorldPointsM)
		if (Point.ContainsNaN()) { OutError = TEXT("GPU/LBS世界点非有限"); return false; }
	if (!OutSample.bLocalReadStable) { OutError = TEXT("GPU/LBS读取期间pose/frame/weights/render mode变化"); return false; }
	OutSample.bMRQSynchronizationVerified = false;
	return true;
}

bool UFutsalPose17Library::ValidatePose17AssetBinding(USkeletalMesh* Asset, const FFutsalPose17MeshIdentity& ExpectedIdentity,
	const TArray<FFutsalPose17SurfaceAnchor>& HeadAnchors, const FString& ManifestSHA256, FString& OutError)
{
	OutError.Reset();
	FFutsalPose17MeshIdentity Actual;
	TArray<uint32> Indices;
	if (!ReadAssetTopology(Asset, Actual, Indices, OutError)) return false;
	if (!SameIdentity(Actual, ExpectedIdentity) || ManifestSHA256.Len() != 64 || HeadAnchors.Num() != 5)
	{
		OutError = TEXT("资产预检要求精确LOD0身份、五头点及manifest SHA256"); return false;
	}
	for (TCHAR Character : ManifestSHA256)
		if (!FChar::IsHexDigit(Character)) { OutError = TEXT("manifest SHA256非法"); return false; }
	const FPositionVertexBuffer& Positions = Asset->GetResourceForRendering()->LODRenderData[0].StaticVertexBuffers.PositionVertexBuffer;
	for (int32 Point = 0; Point < 5; ++Point)
	{
		const auto& Anchor = HeadAnchors[Point];
		if (Anchor.Keypoint != FName(PointNames[Point]) || Anchor.SemanticEvidenceRef.IsEmpty()
			|| Anchor.TriangleVertices.GetMin() < 0 || Anchor.TriangleVertices.GetMax() >= Actual.VertexCount)
		{
			OutError = TEXT("资产预检头锚点顺序/证据/顶点编号非法"); return false;
		}
		bool bFound = false;
		for (int32 Index = 0; Index < Indices.Num(); Index += 3)
			if (Indices[Index] == static_cast<uint32>(Anchor.TriangleVertices.X)
				&& Indices[Index+1] == static_cast<uint32>(Anchor.TriangleVertices.Y)
				&& Indices[Index+2] == static_cast<uint32>(Anchor.TriangleVertices.Z)) { bFound = true; break; }
		FVector Position;
		if (!bFound) { OutError = TEXT("资产预检头锚点不是该网格有序三角"); return false; }
		if (!InterpolateTriangle(FVector(Positions.VertexPosition(Anchor.TriangleVertices.X)),
			FVector(Positions.VertexPosition(Anchor.TriangleVertices.Y)), FVector(Positions.VertexPosition(Anchor.TriangleVertices.Z)),
			Anchor.Barycentric, Position, OutError)) return false;
	}
	for (const TCHAR* Bone : LimbBones)
		if (Asset->GetRefSkeleton().FindBoneIndex(FName(Bone)) == INDEX_NONE)
		{
			OutError = FString::Printf(TEXT("资产预检缺少实际骨骼%s"), Bone); return false;
		}
	return true;
}

bool UFutsalPose17Library::GetVisualSamplingState(USkeletalMeshComponent* VisualMesh,
	FFutsalPose17CPUState& OutState, FString& OutError)
{
	OutState = FFutsalPose17CPUState(); OutError.Reset();
	if (!IsExplicitVisibleMesh(VisualMesh, OutError) || !CheckNoLODOverride(OutError)) return false;
	// 与引擎 LODSyncComponent 相同，经公开 ILODSyncInterface 调用私有 override。
	const ILODSyncInterface* LODInterface = Cast<ILODSyncInterface>(VisualMesh);
	if (!LODInterface) { OutError = TEXT("实际网格未实现公开 ILODSyncInterface"); return false; }
	OutState.ComponentPath = VisualMesh->GetPathName();
	OutState.AssetPath = VisualMesh->GetSkeletalMeshAsset()->GetPathName();
	OutState.bCPUEnabled = VisualMesh->GetCPUSkinningEnabled();
	OutState.ForceRenderedLOD = LODInterface->GetForceRenderedLOD();
	OutState.ForceStreamedLOD = LODInterface->GetForceStreamedLOD();
	OutState.bAssetWasStreamable = VisualMesh->GetSkeletalMeshAsset()->IsStreamable();
	return true;
}

bool UFutsalPose17Library::ValidateDiagnosticVisualOverride(USkeletalMeshComponent* VisualMesh,
	USkeletalMesh* NewMesh, const FFutsalPose17MeshIdentity& ExpectedIdentity, FString& OutError)
{
	OutError.Reset();
	if (!IsExplicitVisibleMesh(VisualMesh, OutError) || !CheckNoLODOverride(OutError)) return false;
	if (!VisualMesh->GetWorld() || VisualMesh->GetWorld()->WorldType != EWorldType::PIE
		|| VisualMesh->GetFName() != TEXT("MPFBVisual") || !IsValid(NewMesh)
		|| VisualMesh->GetCPUSkinningEnabled() || VisualMesh->IsSimulatingPhysics()
		|| VisualMesh->IsRunningParallelEvaluation())
	{
		OutError = TEXT("角色mesh切换只允许PIE MPFBVisual、有效新mesh及未开始CPU/物理/并行动画的诊断准备阶段"); return false;
	}
	USkeletalMesh* Original = VisualMesh->GetSkeletalMeshAsset();
	const USkeletalMeshComponent* Leader = Cast<USkeletalMeshComponent>(VisualMesh->LeaderPoseComponent.Get());
	if (Leader && Leader->IsRunningParallelEvaluation())
	{
		OutError = TEXT("角色切换前Leader仍有并行动画，不在事务里猜测跨组件评估完成"); return false;
	}
	bool bProductionCharacter = false;
	for (int32 Character = 3; Character <= 9; ++Character)
		bProductionCharacter |= NewMesh->GetName() == FString::Printf(TEXT("MPFB_Player_%03d"), Character);
	if (!bProductionCharacter) { OutError = TEXT("本轮逐角色校准仅允许生产集MPFB Player_003至009"); return false; }
	if (!Original->GetSkeleton() || Original->GetSkeleton() != NewMesh->GetSkeleton()
		|| Original->GetSkeleton()->GetFName() != TEXT("SKEL_MPFB_Base"))
	{
		OutError = TEXT("新旧角色必须共享同一SKEL_MPFB_Base资产，不能只按骨名假定兼容"); return false;
	}
	if (Original->GetPostProcessAnimBlueprint() != NewMesh->GetPostProcessAnimBlueprint())
	{
		OutError = TEXT("新旧mesh的post-process动画类不同，当前事务不支持重建另一动画体系"); return false;
	}
	UClass* AnimationClass = VisualMesh->GetAnimClass();
	if (VisualMesh->GetAnimationMode() != EAnimationMode::AnimationBlueprint || !AnimationClass
		|| AnimationClass->GetFName() != TEXT("ABP_MPFB_RuntimeRetarget_C")
		|| !VisualMesh->GetAnimInstance() || VisualMesh->GetAnimInstance()->GetClass() != AnimationClass)
	{
		OutError = TEXT("只允许已初始化的共享ABP_MPFB_RuntimeRetarget，不切换动画类或重建retarget来源"); return false;
	}
	if (VisualMesh->GetOverlayMaterial() || VisualMesh->MaterialSlotsOverlayMaterial.ContainsByPredicate(
		[](const TObjectPtr<UMaterialInterface>& Material) { return Material != nullptr; }))
	{
		OutError = TEXT("存在额外overlay材质，当前角色校准不擅自移除或沿用未知覆盖层"); return false;
	}
	FFutsalPose17MeshIdentity Actual;
	TArray<uint32> Indices;
	if (!ReadAssetTopology(NewMesh, Actual, Indices, OutError)) return false;
	if (!SameIdentity(Actual, ExpectedIdentity))
	{
		OutError = TEXT("override新资产的真实LOD0身份与其manifest不符，禁止套用原角色身份"); return false;
	}
	if (NewMesh->GetMaterials().IsEmpty()) { OutError = TEXT("新角色没有自身材质slots"); return false; }
	for (const FSkeletalMaterial& Material : NewMesh->GetMaterials())
		if (!Material.MaterialInterface) { OutError = TEXT("新角色自身材质slot为空，不沿用旧角色UV材质"); return false; }
	return true;
}

bool UFutsalPose17Library::ApplyDiagnosticVisualOverride(USkeletalMeshComponent* VisualMesh, USkeletalMesh* NewMesh,
	const FFutsalPose17MeshIdentity& ExpectedIdentity, FFutsalPose17VisualMeshState& OutPrevious,
	FFutsalPose17VisualOverrideEvidence& OutEvidence, FString& OutError)
{
	OutPrevious = FFutsalPose17VisualMeshState(); OutEvidence = FFutsalPose17VisualOverrideEvidence();
	if (!ValidateDiagnosticVisualOverride(VisualMesh, NewMesh, ExpectedIdentity, OutError))
	{
		OutEvidence.ApplyError = OutError; return false;
	}
	OutPrevious.Component = VisualMesh;
	OutPrevious.OriginalMesh = VisualMesh->GetSkeletalMeshAsset(); OutPrevious.AppliedMesh = NewMesh;
	OutPrevious.OverrideMaterials = VisualMesh->OverrideMaterials; // 只读快照；恢复走公开SetMaterial。
	OutPrevious.AnimationClass = VisualMesh->GetAnimClass(); OutPrevious.AnimationInstance = VisualMesh->GetAnimInstance();
	OutPrevious.PostProcessInstance = VisualMesh->GetPostProcessInstance();
	OutPrevious.AnimationMode = static_cast<uint8>(VisualMesh->GetAnimationMode());
	OutPrevious.Leader = VisualMesh->LeaderPoseComponent; OutPrevious.AttachParent = VisualMesh->GetAttachParent();
	OutPrevious.TickOption = static_cast<uint8>(VisualMesh->VisibilityBasedAnimTickOption);
	OutPrevious.MorphCurves = VisualMesh->GetMorphTargetCurves();
	OutPrevious.bOriginalStreamable = OutPrevious.OriginalMesh->IsStreamable();
	OutPrevious.bAppliedStreamable = NewMesh->IsStreamable();
	OutEvidence.ComponentPath = VisualMesh->GetPathName();
	OutEvidence.OriginalAssetPath = OutPrevious.OriginalMesh->GetPathName(); OutEvidence.AppliedAssetPath = NewMesh->GetPathName();
	OutEvidence.SharedSkeletonPath = NewMesh->GetSkeleton()->GetPathName();
	OutEvidence.AnimationClassPath = OutPrevious.AnimationClass->GetPathName();
	OutEvidence.OriginalAnimationInstancePath = OutPrevious.AnimationInstance->GetPathName();
	OutEvidence.bIdentityVerified = true;
	for (UMaterialInterface* Material : OutPrevious.OverrideMaterials)
		OutEvidence.OriginalOverrideMaterialPaths.Add(Material ? Material->GetPathName() : TEXT(""));
	for (const FSkeletalMaterial& Material : NewMesh->GetMaterials())
		OutEvidence.AppliedAssetMaterialPaths.Add(Material.MaterialInterface->GetPathName());
	OutPrevious.bMutationStarted = true;
	// 引擎SetSkeletalMesh(false)保留共享骨架的动画实例；它仍会重建mesh资源及清空morph，故逐项记录/恢复。
	VisualMesh->SetSkeletalMesh(NewMesh, false);
	VisualMesh->EmptyOverrideMaterials();
	OutEvidence.AppliedEngineFrame = static_cast<int64>(GFrameCounter);
	OutEvidence.bAnimationBindingPreserved = VisualMesh->GetAnimClass() == OutPrevious.AnimationClass
		&& VisualMesh->GetAnimInstance() == OutPrevious.AnimationInstance
		&& VisualMesh->GetPostProcessInstance() == OutPrevious.PostProcessInstance
		&& static_cast<uint8>(VisualMesh->GetAnimationMode()) == OutPrevious.AnimationMode
		&& VisualMesh->LeaderPoseComponent == OutPrevious.Leader && VisualMesh->GetAttachParent() == OutPrevious.AttachParent.Get()
		&& static_cast<uint8>(VisualMesh->VisibilityBasedAnimTickOption) == OutPrevious.TickOption;
	OutEvidence.bNewAssetMaterialsVerified = VisualMesh->GetNumOverrideMaterials() == 0
		&& VisualMesh->GetNumMaterials() == NewMesh->GetMaterials().Num();
	for (int32 Index = 0; Index < NewMesh->GetMaterials().Num(); ++Index)
		OutEvidence.bNewAssetMaterialsVerified &= VisualMesh->GetMaterial(Index) == NewMesh->GetMaterials()[Index].MaterialInterface;
	OutEvidence.bApplySucceeded = VisualMesh->GetSkeletalMeshAsset() == NewMesh
		&& OutEvidence.bAnimationBindingPreserved && OutEvidence.bNewAssetMaterialsVerified;
	if (!OutEvidence.bApplySucceeded)
	{
		OutError = TEXT("PIE mesh切换后共享动画实例/材质读回不一致；必须恢复并保留partial失败收据");
		OutEvidence.ApplyError = OutError;
	}
	return OutEvidence.bApplySucceeded;
}

bool UFutsalPose17Library::RestoreDiagnosticVisualOverride(const FFutsalPose17VisualMeshState& Previous,
	FFutsalPose17VisualOverrideEvidence& InOutEvidence, FString& OutError)
{
	OutError.Reset(); InOutEvidence.bRestoreAttempted = true;
	USkeletalMeshComponent* Mesh = Previous.Component;
	if (!IsInGameThread() || !IsValid(Mesh) || !Previous.bMutationStarted || !IsValid(Previous.OriginalMesh)
		|| !Mesh->GetWorld() || Mesh->GetWorld()->WorldType != EWorldType::PIE || Mesh->GetPathName() != InOutEvidence.ComponentPath
		|| Mesh->GetSkeletalMeshAsset() != Previous.AppliedMesh || Mesh->GetCPUSkinningEnabled())
	{
		OutError = TEXT("mesh恢复要求同一PIE组件/已应用资产且CPU状态已先恢复，不能猜测Editor实例或覆盖未知mesh");
		InOutEvidence.RestoreError = OutError; return false;
	}
	Mesh->SetSkeletalMesh(Previous.OriginalMesh, false);
	Mesh->EmptyOverrideMaterials();
	for (int32 Index = 0; Index < Previous.OverrideMaterials.Num(); ++Index)
		Mesh->SetMaterial(Index, Previous.OverrideMaterials[Index]);
	Mesh->ClearMorphTargets();
	for (const auto& Morph : Previous.MorphCurves) Mesh->SetMorphTarget(Morph.Key, Morph.Value, false);
	bool bMatched = Mesh->GetSkeletalMeshAsset() == Previous.OriginalMesh
		&& Mesh->OverrideMaterials == Previous.OverrideMaterials && Mesh->GetAnimClass() == Previous.AnimationClass
		&& Mesh->GetAnimInstance() == Previous.AnimationInstance && Mesh->GetPostProcessInstance() == Previous.PostProcessInstance
		&& static_cast<uint8>(Mesh->GetAnimationMode()) == Previous.AnimationMode
		&& Mesh->LeaderPoseComponent == Previous.Leader && Mesh->GetAttachParent() == Previous.AttachParent.Get()
		&& static_cast<uint8>(Mesh->VisibilityBasedAnimTickOption) == Previous.TickOption
		&& SameMorphCurves(Mesh->GetMorphTargetCurves(), Previous.MorphCurves);
	InOutEvidence.bStreamingStateMatched = Previous.OriginalMesh->IsStreamable() == Previous.bOriginalStreamable
		&& Previous.AppliedMesh->IsStreamable() == Previous.bAppliedStreamable;
	InOutEvidence.bRestoreSucceeded = bMatched;
	if (!bMatched) { OutError = TEXT("PIE原mesh/override材质/动画/morph恢复后读回不一致"); InOutEvidence.RestoreError = OutError; }
	return bMatched;
}

bool UFutsalPose17Library::PrepareVisualCPUSampling(USkeletalMeshComponent* VisualMesh,
	FFutsalPose17CPUState& OutPreviousState, FString& OutError)
{
	if (!GetVisualSamplingState(VisualMesh, OutPreviousState, OutError)) return false;
	if (!VisualMesh->GetWorld() || VisualMesh->GetWorld()->WorldType != EWorldType::PIE
		|| !VisualMesh->GetSkeletalMeshAsset()->GetResourceForRendering())
	{
		OutError = TEXT("CPU 采样预备只允许已加载渲染资源的 PIE 实例，禁止修改 Editor 原组件"); return false;
	}
	VisualMesh->SetForcedLOD(1); // 旧接口 1-based，强制真实 LOD0。
	VisualMesh->SetCPUSkinningEnabled(true, true);
	return true;
}

bool UFutsalPose17Library::RestoreVisualCPUSampling(USkeletalMeshComponent* VisualMesh,
	const FFutsalPose17CPUState& PreviousState, bool& bOutStreamingStateMatched, FString& OutError)
{
	bOutStreamingStateMatched = false; OutError.Reset();
	if (!IsInGameThread() || !IsValid(VisualMesh) || !VisualMesh->GetSkeletalMeshAsset() || !VisualMesh->GetWorld()
		|| VisualMesh->GetWorld()->WorldType != EWorldType::PIE || VisualMesh->GetPathName() != PreviousState.ComponentPath
		|| VisualMesh->GetSkeletalMeshAsset()->GetPathName() != PreviousState.AssetPath || !CheckNoLODOverride(OutError))
	{
		if (OutError.IsEmpty()) OutError = TEXT("恢复必须匹配原 PIE 组件及资产，不猜测新实例"); return false;
	}
	ILODSyncInterface* LODInterface = Cast<ILODSyncInterface>(VisualMesh);
	if (!LODInterface) { OutError = TEXT("恢复网格未实现公开 ILODSyncInterface"); return false; }
	VisualMesh->SetCPUSkinningEnabled(PreviousState.bCPUEnabled, true);
	// 接口为0-based，-1恢复自动选择；不得套用 SetForcedLOD 的1-based约定。
	LODInterface->SetForceRenderedLOD(PreviousState.ForceRenderedLOD);
	LODInterface->SetForceStreamedLOD(PreviousState.ForceStreamedLOD);
	if (VisualMesh->GetCPUSkinningEnabled() != PreviousState.bCPUEnabled
		|| LODInterface->GetForceRenderedLOD() != PreviousState.ForceRenderedLOD
		|| LODInterface->GetForceStreamedLOD() != PreviousState.ForceStreamedLOD)
	{
		OutError = TEXT("PIE组件CPU/LOD恢复后读回不一致"); return false;
	}
	bOutStreamingStateMatched = VisualMesh->GetSkeletalMeshAsset()->IsStreamable() == PreviousState.bAssetWasStreamable;
	// 不擅自 LinkStreaming：同资产可能仍被其他 CPU skin 组件使用。
	return true;
}

bool UFutsalPose17Library::SynchronizeVisualCPUCaches(const TArray<USkeletalMeshComponent*>& VisualMeshes, FString& OutError)
{
	OutError.Reset();
	if (VisualMeshes.IsEmpty()) { OutError = TEXT("没有明确的采样网格"); return false; }
	UWorld* World = nullptr;
	for (USkeletalMeshComponent* Mesh : VisualMeshes)
	{
		if (!IsExplicitVisibleMesh(Mesh, OutError)) return false;
		const USkeletalMeshComponent* Leader = Cast<USkeletalMeshComponent>(Mesh->LeaderPoseComponent.Get());
		if (!Mesh->GetWorld() || Mesh->GetWorld()->WorldType != EWorldType::PIE || (World && World != Mesh->GetWorld())
			|| !Mesh->GetCPUSkinningEnabled() || Mesh->GetPredictedLODLevel() != 0 || Mesh->IsRunningParallelEvaluation()
			|| (Leader && Leader->IsRunningParallelEvaluation()))
		{
			OutError = TEXT("缓存同步要求同一 PIE 世界、LOD0 CPU skin、已结束并行动画；不重评动画"); return false;
		}
		World = Mesh->GetWorld();
	}
	const uint64 EngineFrame = GFrameCounter;
	TArray<uint32> Revisions;
	for (USkeletalMeshComponent* Mesh : VisualMeshes)
	{
		Revisions.Add(Mesh->GetBoneTransformRevisionNumber());
		Mesh->MarkRenderDynamicDataDirty();
	}
	// 正常组件 end-of-frame 路径发送实际当前骨骼/形变动态数据。
	World->SendAllEndOfFrameUpdates();
	// UE5.8 此接口 StopRecording 所有 render command pipes 并发 fence 到 RT/RHI。
	FlushRenderingCommands();
	for (int32 Index = 0; Index < VisualMeshes.Num(); ++Index)
	{
		if (Revisions[Index] != VisualMeshes[Index]->GetBoneTransformRevisionNumber() || EngineFrame != GFrameCounter)
		{
			OutError = TEXT("动态数据提交/fence期间帧或骨变换revision变化，拒绝采样"); return false;
		}
	}
	return true;
}

bool UFutsalPose17Library::InterpolateTriangle(const FVector& A, const FVector& B, const FVector& C,
	const FVector& Weights, FVector& OutPoint, FString& OutError)
{
	OutError.Reset(); OutPoint = FVector::ZeroVector;
	if (A.ContainsNaN() || B.ContainsNaN() || C.ContainsNaN() || Weights.ContainsNaN()
		|| Weights.GetMin() < 0 || Weights.GetMax() > 1 || FMath::Abs(Weights.X + Weights.Y + Weights.Z - 1.0) > 1.e-8
		|| FVector::CrossProduct(B - A, C - A).SizeSquared() <= SMALL_NUMBER)
	{
		OutError = TEXT("三角形退化、权重非法或包含非有限值"); return false;
	}
	OutPoint = A * Weights.X + B * Weights.Y + C * Weights.Z;
	return !OutPoint.ContainsNaN();
}

bool UFutsalPose17Library::DescribeVisualMesh(USkeletalMeshComponent* VisualMesh,
	FFutsalPose17MeshIdentity& OutIdentity, FString& OutError)
{
	OutError.Reset(); OutIdentity = FFutsalPose17MeshIdentity();
	TArray<uint32> Indices;
	return ReadTopology(VisualMesh, OutIdentity, Indices, OutError);
}

bool UFutsalPose17Library::ReadVisualReferenceGeometry(USkeletalMeshComponent* VisualMesh,
	TArray<FVector>& OutReferencePositionsCm, TArray<FIntVector>& OutTriangles,
	FFutsalPose17MeshIdentity& OutIdentity, FString& OutError)
{
	OutReferencePositionsCm.Reset(); OutTriangles.Reset(); OutError.Reset();
	if (!IsExplicitVisibleMesh(VisualMesh, OutError)) return false;
	return ReadAssetReferenceGeometry(VisualMesh->GetSkeletalMeshAsset(), OutReferencePositionsCm, OutTriangles, OutIdentity, OutError);
}

bool UFutsalPose17Library::ReadAssetReferenceGeometry(USkeletalMesh* Asset,
	TArray<FVector>& OutReferencePositionsCm, TArray<FIntVector>& OutTriangles,
	FFutsalPose17MeshIdentity& OutIdentity, FString& OutError)
{
	OutReferencePositionsCm.Reset(); OutTriangles.Reset(); OutError.Reset(); OutIdentity = FFutsalPose17MeshIdentity();
	TArray<uint32> Indices;
	if (!ReadAssetTopology(Asset, OutIdentity, Indices, OutError)) return false;
	const auto& Positions = Asset->GetResourceForRendering()->LODRenderData[0].StaticVertexBuffers.PositionVertexBuffer;
	OutReferencePositionsCm.Reserve(OutIdentity.VertexCount);
	for (int32 Index = 0; Index < OutIdentity.VertexCount; ++Index)
		OutReferencePositionsCm.Add(FVector(Positions.VertexPosition(Index)));
	for (int32 Index = 0; Index < Indices.Num(); Index += 3)
		OutTriangles.Add(FIntVector(Indices[Index], Indices[Index + 1], Indices[Index + 2]));
	return true;
}

bool UFutsalPose17Library::SampleVisualPose17(USkeletalMeshComponent* VisualMesh,
	const FFutsalPose17MeshIdentity& ExpectedIdentity, const TArray<FFutsalPose17SurfaceAnchor>& HeadAnchors,
	const FString& ManifestSHA256, bool bAllowSlowDiagnosticSnapshot, FFutsalPose17Sample& OutSample, FString& OutError)
{
	OutError.Reset(); OutSample = FFutsalPose17Sample();
	TArray<uint32> Indices;
	if (!ReadTopology(VisualMesh, OutSample.MeshIdentity, Indices, OutError)) return false;
	const USkeletalMeshComponent* Leader = Cast<USkeletalMeshComponent>(VisualMesh->LeaderPoseComponent.Get());
	if (VisualMesh->IsRunningParallelEvaluation() || (Leader && Leader->IsRunningParallelEvaluation()))
	{
		OutError = TEXT("当前实际网格或 LeaderPose 仍有并行动画任务，不在标注调用中刷新或等待动画"); return false;
	}
	if (!SameIdentity(ExpectedIdentity, OutSample.MeshIdentity) || ManifestSHA256.Len() != 64 || HeadAnchors.Num() != 5)
	{
		OutError = TEXT("需要已签名的当前 UE LOD0 身份、manifest SHA256 与五个头部锚点"); return false;
	}
	for (TCHAR Character : ManifestSHA256)
	{
		if (!FChar::IsHexDigit(Character)) { OutError = TEXT("manifest SHA256 必须为64位十六进制"); return false; }
	}
	for (int32 Point = 0; Point < 5; ++Point)
	{
		const FFutsalPose17SurfaceAnchor& Anchor = HeadAnchors[Point];
		if (Anchor.Keypoint != FName(PointNames[Point]) || Anchor.SemanticEvidenceRef.IsEmpty()
			|| Anchor.TriangleVertices.GetMin() < 0 || Anchor.TriangleVertices.GetMax() >= OutSample.MeshIdentity.VertexCount)
		{
			OutError = TEXT("头部锚点顺序、语义证据或 UE 顶点编号不合法"); return false;
		}
		bool bFound = false;
		for (int32 Index = 0; Index < Indices.Num(); Index += 3)
		{
			// 只接受有序真实三角；映射方应保留 IndexBuffer 顶点次序。
			if (Indices[Index] == static_cast<uint32>(Anchor.TriangleVertices.X)
				&& Indices[Index + 1] == static_cast<uint32>(Anchor.TriangleVertices.Y)
				&& Indices[Index + 2] == static_cast<uint32>(Anchor.TriangleVertices.Z)) { bFound = true; break; }
		}
		if (!bFound) { OutError = TEXT("锚点不是该 LOD0 的有序真实三角形"); return false; }
	}
	OutSample.ComponentPath = VisualMesh->GetPathName();
	OutSample.ManifestSHA256 = ManifestSHA256;
	OutSample.EngineFrameBefore = static_cast<int64>(GFrameCounter);
	OutSample.PoseRevisionBefore = VisualMesh->GetBoneTransformRevisionNumber();
	TArray<FFinalSkinVertex> Vertices;
	if (bAllowSlowDiagnosticSnapshot)
	{
		OutSample.SamplingMethod = TEXT("diagnostic_get_cpu_skinned_vertices_may_refresh_pose");
		VisualMesh->GetCPUSkinnedVertices(Vertices, 0);
	}
	else
	{
		OutSample.SamplingMethod = TEXT("existing_cpu_skin_cache_unverified_render_sample");
		if (!VisualMesh->GetCPUSkinningEnabled() || VisualMesh->GetPredictedLODLevel() != 0)
		{
			OutError = TEXT("没有已启用的 LOD0 CPU skin 缓存；默认不切换蒙皮或重评动画"); return false;
		}
		VisualMesh->GetCPUSkinnedCachedFinalVertices(Vertices);
	}
	if (Vertices.Num() != OutSample.MeshIdentity.VertexCount)
	{
		OutError = TEXT("形变顶点数量与签名 LOD0 不符"); return false;
	}
	const uint32 ReadRevision = VisualMesh->GetBoneTransformRevisionNumber();
	const FTransform ComponentTransform = VisualMesh->GetComponentTransform();
	for (int32 Point = 0; Point < 5; ++Point)
	{
		const auto& Anchor = HeadAnchors[Point];
		const FIntVector Triangle = Anchor.TriangleVertices;
		FVector Position;
		if (!InterpolateTriangle(FVector(Vertices[Triangle.X].Position), FVector(Vertices[Triangle.Y].Position),
			FVector(Vertices[Triangle.Z].Position), Anchor.Barycentric, Position, OutError)) return false;
		OutSample.WorldPointsM.Add(ComponentTransform.TransformPosition(Position) * 0.01);
	}
	for (int32 Point = 0; Point < 12; ++Point)
	{
		const int32 Bone = VisualMesh->GetBoneIndex(FName(LimbBones[Point]));
		if (Bone == INDEX_NONE) { OutError = FString::Printf(TEXT("实际 VisualMesh 缺少骨骼 %s"), LimbBones[Point]); return false; }
		OutSample.WorldPointsM.Add(VisualMesh->GetBoneTransform(Bone).GetLocation() * 0.01);
	}
	for (const TCHAR* Name : PointNames) OutSample.KeypointNames.Add(FName(Name));
	OutSample.WorldTimeSeconds = VisualMesh->GetWorld() ? VisualMesh->GetWorld()->GetTimeSeconds() : 0;
	// 旧路径同样记录实际状态，不能让新增bool默认false冒充CPU render关闭。
	OutSample.bRenderCPUEnabledAtRead = VisualMesh->GetCPUSkinningEnabled();
	OutSample.bRenderStaticAtRead = VisualMesh->bRenderStatic;
	OutSample.PredictedLODAtRead = VisualMesh->GetPredictedLODLevel();
	OutSample.EngineFrameAfter = static_cast<int64>(GFrameCounter);
	OutSample.PoseRevisionAfter = VisualMesh->GetBoneTransformRevisionNumber();
	OutSample.bLocalReadStable = OutSample.EngineFrameBefore == OutSample.EngineFrameAfter
		&& ReadRevision == OutSample.PoseRevisionAfter && ComponentTransform.Equals(VisualMesh->GetComponentTransform(), 0.0);
	for (const FVector& Point : OutSample.WorldPointsM)
		if (Point.ContainsNaN()) { OutError = TEXT("形变世界点包含非有限值"); return false; }
	if (!OutSample.bLocalReadStable) { OutError = TEXT("采样期间帧、姿态或组件变换变化"); return false; }
	// 本地读取稳定不能代替 MRQ 动画评估、相机和 RGB/mask 同步证明。
	OutSample.bMRQSynchronizationVerified = false;
	return true;
}
