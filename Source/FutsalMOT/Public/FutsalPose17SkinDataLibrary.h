#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FutsalPose17Library.h"
#include "FutsalPose17SkinDataLibrary.generated.h"

/** 参考骨信息；逆参考矩阵采用UE行主序float32，局部参考姿态不冒充当前姿态。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17SkinBone
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FName Name;
	UPROPERTY(BlueprintReadOnly) int32 ParentIndex = INDEX_NONE;
	UPROPERTY(BlueprintReadOnly) TArray<double> ReferenceLocalTranslationCm;
	UPROPERTY(BlueprintReadOnly) TArray<double> ReferenceLocalRotationXyzw;
	UPROPERTY(BlueprintReadOnly) TArray<double> ReferenceLocalScaleXyz;
	UPROPERTY(BlueprintReadOnly) TArray<float> InverseReferenceRowMajorF32;
};

/** 实际LOD0 section的骨调色板与有序拓扑范围。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17SkinSection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) int32 SectionIndex = INDEX_NONE;
	UPROPERTY(BlueprintReadOnly) int32 BaseVertexIndex = 0;
	UPROPERTY(BlueprintReadOnly) int32 VertexCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 BaseIndex = 0;
	UPROPERTY(BlueprintReadOnly) int32 TriangleCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 MaterialIndex = 0;
	UPROPERTY(BlueprintReadOnly) bool bDisabled = false;
	UPROPERTY(BlueprintReadOnly) bool bUnifiedBoneMap = false;
	UPROPERTY(BlueprintReadOnly) TArray<int32> BoneMap;
};

/** 每顶点固定槽位均保留，包括零权重；不重新归一化或合并骨影响。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17SkinVertex
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) int32 VertexIndex = INDEX_NONE;
	UPROPERTY(BlueprintReadOnly) int32 SectionIndex = INDEX_NONE;
	UPROPERTY(BlueprintReadOnly) TArray<int32> SectionLocalBoneIndices;
	UPROPERTY(BlueprintReadOnly) TArray<int32> GlobalBoneIndices;
	UPROPERTY(BlueprintReadOnly) TArray<int32> RawWeightsU16;
	UPROPERTY(BlueprintReadOnly) TArray<float> NormalizedWeights;
};

/** 资产基础权重只读快照；只有SHA匹配时才能对应某个历史component采样。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17SkinData
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FString Schema = TEXT("futsalmot_pose17_asset_base_skin_data_v1");
	UPROPERTY(BlueprintReadOnly) bool bReadSucceeded = false;
	UPROPERTY(BlueprintReadOnly) bool bSceneOrAssetMutationPerformed = false;
	UPROPERTY(BlueprintReadOnly) bool bComponentEffectiveWeightsRead = false;
	UPROPERTY(BlueprintReadOnly) bool bHistoricalNativeWeightSHA256Matched = false;
	UPROPERTY(BlueprintReadOnly) bool bDynamicSurfaceReconstructionVerified = false;
	UPROPERTY(BlueprintReadOnly) FFutsalPose17MeshIdentity MeshIdentity;
	UPROPERTY(BlueprintReadOnly) FString WeightSource = TEXT("asset_lod0_imported_base_skin_weight_buffer");
	UPROPERTY(BlueprintReadOnly) FString SkinWeightSignatureScheme = TEXT("ue_component_lod0_fixed_skinweight_raw_v1");
	UPROPERTY(BlueprintReadOnly) FString SkinWeightDataSHA256;
	UPROPERTY(BlueprintReadOnly) FString ExpectedHistoricalSkinWeightSHA256;
	UPROPERTY(BlueprintReadOnly) FString RawWeightDataBase64;
	UPROPERTY(BlueprintReadOnly) int32 RawWeightDataByteCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 BoneIndexByteSize = 0;
	UPROPERTY(BlueprintReadOnly) int32 BoneWeightByteSize = 0;
	UPROPERTY(BlueprintReadOnly) int32 ConstantVertexStrideBytes = 0;
	UPROPERTY(BlueprintReadOnly) int32 ConstantWeightsOffsetBytes = 0;
	UPROPERTY(BlueprintReadOnly) int32 MaxBoneInfluences = 0;
	UPROPERTY(BlueprintReadOnly) int32 MaxRawBoneWeight = 65535;
	UPROPERTY(BlueprintReadOnly) float RawWeightToFloatMultiplier = 0.f;
	UPROPERTY(BlueprintReadOnly) FString InverseReferenceSignatureScheme = TEXT("ue_inverse_ref_pose_rowmajor_f32_le_v1");
	UPROPERTY(BlueprintReadOnly) FString InverseReferenceMatricesBase64;
	UPROPERTY(BlueprintReadOnly) FString InverseReferenceMatricesSHA256;
	UPROPERTY(BlueprintReadOnly) TArray<FFutsalPose17SkinBone> Bones;
	UPROPERTY(BlueprintReadOnly) TArray<int32> ActiveBoneIndices;
	UPROPERTY(BlueprintReadOnly) TArray<FFutsalPose17SkinSection> Sections;
	UPROPERTY(BlueprintReadOnly) TArray<FFutsalPose17SkinVertex> Vertices;
	UPROPERTY(BlueprintReadOnly) int64 EngineFrameBefore = -1;
	UPROPERTY(BlueprintReadOnly) int64 EngineFrameAfter = -1;
	UPROPERTY(BlueprintReadOnly) bool bLocalReadStable = false;
	UPROPERTY(BlueprintReadOnly) int32 AssetMorphTargetCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 AssetMaterialCount = 0;
	UPROPERTY(BlueprintReadOnly) FString MaterialShaderPlatform;
};

/** 独立静态资产读者，不创建component、不切CPU模式、不刷新Pose或调用MRQ。 */
UCLASS()
class FUTSALMOT_API UFutsalPose17SkinDataLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	/** 精确匹配已有native identity/weights SHA；基础buffer不同即拒绝，不能推定实际override。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17|Diagnostic")
	static bool ReadAssetBaseSkinData(USkeletalMesh* Asset, const FFutsalPose17MeshIdentity& ExpectedIdentity,
		const FString& ExpectedHistoricalSkinWeightSHA256, FFutsalPose17SkinData& OutData, FString& OutError);

	/** 与实际UE GetBoneWeight / 65535及section.BoneMap同语义；用于小型无场景反例测试。 */
	static bool ResolveSectionInfluences(const TArray<int32>& BoneMap, int32 SkeletonBoneCount,
		const TArray<int32>& LocalIndices, const TArray<int32>& RawWeightsU16,
		TArray<int32>& OutGlobalIndices, TArray<float>& OutNormalizedWeights, FString& OutError);
};
