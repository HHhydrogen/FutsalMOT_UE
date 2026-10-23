#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FutsalPose17Library.generated.h"

class USkeletalMeshComponent;
class USkeletalMesh;
class UAnimInstance;
class UMaterialInterface;
class USkinnedMeshComponent;
class USceneComponent;

/** UE 导入后 LOD0 的真实有序拓扑身份；不同于 Blender JSON hash。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17MeshIdentity
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString AssetPath;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString SignatureScheme = TEXT("ue_lod_le_u32_f32_v1");
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 LOD = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 VertexCount = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString TopologySHA256;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString GeometrySHA256;
};

/** 经 UE 拓扑映射及语义验收的一个头部表面锚点，不能传 Blender 顶点编号。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17SurfaceAnchor
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FName Keypoint;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FIntVector TriangleVertices = FIntVector(-1);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FVector Barycentric = FVector::ZeroVector;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FString SemanticEvidenceRef;
};

/** 新GPU/LBS路径的实际只读门禁快照；不从方法名推断功能已检查。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17GPULBSEligibility
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) bool bChecksExecuted = false;
	UPROPERTY(BlueprintReadOnly) bool bEligible = false;
	UPROPERTY(BlueprintReadOnly) bool bPIEWorld = false;
	UPROPERTY(BlueprintReadOnly) bool bRenderCPUEnabled = false;
	UPROPERTY(BlueprintReadOnly) bool bRenderStatic = false;
	UPROPERTY(BlueprintReadOnly) bool bHasNaniteData = false;
	UPROPERTY(BlueprintReadOnly) bool bParallelEvaluationRunning = false;
	UPROPERTY(BlueprintReadOnly) bool bLeaderParallelEvaluationRunning = false;
	UPROPERTY(BlueprintReadOnly) int32 ActiveMorphWeightCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 ManualMorphCurveCount = 0;
	UPROPERTY(BlueprintReadOnly) bool bNonFiniteMorphWeights = false;
	UPROPERTY(BlueprintReadOnly) int32 ExternalMorphSetCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 ClothSimulationCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 Lod0ClothSectionCount = 0;
	UPROPERTY(BlueprintReadOnly) bool bLod0HasClothData = false;
	UPROPERTY(BlueprintReadOnly) int32 MeshDeformerAssetCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 MeshDeformerInstanceCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 MaterialWPOSlotCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 NullMaterialSlotCount = 0;
	UPROPERTY(BlueprintReadOnly) bool bWeightsReadable = false;
	UPROPERTY(BlueprintReadOnly) bool bVariableInfluenceWeights = false;
	UPROPERTY(BlueprintReadOnly) int32 WeightVertexCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 ReferenceVertexCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 MaxBoneInfluences = 0;
};

/** 本地调用证据，不是 MRQ/RGB 同步证明。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17Sample
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") TArray<FName> KeypointNames;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") TArray<FVector> WorldPointsM;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FFutsalPose17MeshIdentity MeshIdentity;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString ComponentPath;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString ManifestSHA256;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString SamplingMethod;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int64 EngineFrameBefore = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int64 EngineFrameAfter = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int64 PoseRevisionBefore = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int64 PoseRevisionAfter = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") double WorldTimeSeconds = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bLocalReadStable = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bMRQSynchronizationVerified = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bRenderCPUEnabledAtRead = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bRenderStaticAtRead = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 PredictedLODAtRead = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString BoneSpaceBaseComponentPath;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") TArray<FName> BoneSpaceBaseNames;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") TArray<FTransform> BoneSpaceBaseTransformsUECm;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString RefToLocalMatricesSHA256;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString SkinWeightDataSHA256;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString RefToLocalSignatureScheme;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString SkinWeightSignatureScheme;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FFutsalPose17GPULBSEligibility GpuLbsEligibility;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString BonePoseTransformEncoding;
};

/** 仅恢复同一个 PIE 实例的组件配置；资产 streaming 另行核验。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17CPUState
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString ComponentPath;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString AssetPath;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bCPUEnabled = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 ForceRenderedLOD = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 ForceStreamedLOD = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bAssetWasStreamable = false;
};

/** 仅持有当前PIE会话的恢复快照；不得序列化成正式数据或跨Editor重用。 */
USTRUCT()
struct FUTSALMOT_API FFutsalPose17VisualMeshState
{
	GENERATED_BODY()
	UPROPERTY() TObjectPtr<USkeletalMeshComponent> Component = nullptr;
	UPROPERTY() TObjectPtr<USkeletalMesh> OriginalMesh = nullptr;
	UPROPERTY() TObjectPtr<USkeletalMesh> AppliedMesh = nullptr;
	UPROPERTY() TArray<TObjectPtr<UMaterialInterface>> OverrideMaterials;
	UPROPERTY() TObjectPtr<UClass> AnimationClass = nullptr;
	UPROPERTY() TObjectPtr<UAnimInstance> AnimationInstance = nullptr;
	UPROPERTY() TObjectPtr<UAnimInstance> PostProcessInstance = nullptr;
	UPROPERTY() TWeakObjectPtr<USkinnedMeshComponent> Leader;
	UPROPERTY() TWeakObjectPtr<USceneComponent> AttachParent;
	UPROPERTY() TMap<FName, float> MorphCurves;
	UPROPERTY() uint8 AnimationMode = 0;
	UPROPERTY() uint8 TickOption = 0;
	UPROPERTY() bool bMutationStarted = false;
	UPROPERTY() bool bOriginalStreamable = false;
	UPROPERTY() bool bAppliedStreamable = false;
};

/** 纯值收据；原生teardown写盘前清空上面的PIE UObject快照。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17VisualOverrideEvidence
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FString ComponentPath;
	UPROPERTY(BlueprintReadOnly) FString OriginalAssetPath;
	UPROPERTY(BlueprintReadOnly) FString AppliedAssetPath;
	UPROPERTY(BlueprintReadOnly) FString SharedSkeletonPath;
	UPROPERTY(BlueprintReadOnly) FString AnimationClassPath;
	UPROPERTY(BlueprintReadOnly) FString OriginalAnimationInstancePath;
	UPROPERTY(BlueprintReadOnly) TArray<FString> OriginalOverrideMaterialPaths;
	UPROPERTY(BlueprintReadOnly) TArray<FString> AppliedAssetMaterialPaths;
	UPROPERTY(BlueprintReadOnly) bool bIdentityVerified = false;
	UPROPERTY(BlueprintReadOnly) bool bApplySucceeded = false;
	UPROPERTY(BlueprintReadOnly) bool bAnimationBindingPreserved = false;
	UPROPERTY(BlueprintReadOnly) bool bNewAssetMaterialsVerified = false;
	UPROPERTY(BlueprintReadOnly) bool bRestoreAttempted = false;
	UPROPERTY(BlueprintReadOnly) bool bRestoreSucceeded = false;
	UPROPERTY(BlueprintReadOnly) bool bStreamingStateMatched = false;
	UPROPERTY(BlueprintReadOnly) int64 AppliedEngineFrame = -1;
	UPROPERTY(BlueprintReadOnly) FString ApplyError;
	UPROPERTY(BlueprintReadOnly) FString RestoreError;
	UPROPERTY(BlueprintReadOnly) bool bGpuLbsValidationAttempted = false;
	UPROPERTY(BlueprintReadOnly) bool bGpuLbsValidationSucceeded = false;
	UPROPERTY(BlueprintReadOnly) FFutsalPose17GPULBSEligibility GpuLbsEligibilityAfterOverride;
	UPROPERTY(BlueprintReadOnly) FString GpuLbsValidationError;
};

UCLASS()
class FUTSALMOT_API UFutsalPose17Library : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	/** 新诊断路径只读门禁；保持GPU实际渲染，拒绝morph/cloth/deformer/WPO及不可读weights。 */
	static bool ValidateGPUVisualLBS(USkeletalMeshComponent* VisualMesh, FString& OutError, FFutsalPose17GPULBSEligibility* OutEligibility = nullptr);
	static bool PrepareGPUVisualLBS(USkeletalMeshComponent* VisualMesh, FFutsalPose17CPUState& OutPreviousState, FString& OutError);
	static bool RestoreGPUVisualLBS(USkeletalMeshComponent* VisualMesh, const FFutsalPose17CPUState& PreviousState, FString& OutError);
	static bool SynchronizeGPUVisualLBS(const TArray<USkeletalMeshComponent*>& VisualMeshes, FString& OutError);
	/** 纯CPU坐标计算；不会开启CPU render skin、刷新动画或调用GetCPUSkinnedVertices。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool SampleVisualPose17GPULBS(USkeletalMeshComponent* VisualMesh,
		const FFutsalPose17MeshIdentity& ExpectedIdentity, const TArray<FFutsalPose17SurfaceAnchor>& HeadAnchors,
		const FString& ManifestSHA256, FFutsalPose17Sample& OutSample, FString& OutError);
	/** 无场景写入：预检manifest/有序真实三角/权重/12骨，供所有目标先验收再mutation。 */
	static bool ValidatePose17AssetBinding(USkeletalMesh* Asset, const FFutsalPose17MeshIdentity& ExpectedIdentity,
		const TArray<FFutsalPose17SurfaceAnchor>& HeadAnchors, const FString& ManifestSHA256, FString& OutError);
	/** 只读预检；实际PIE组件、新mesh共享精确骨架/AnimBP，身份为新mesh真实LOD0。 */
	static bool ValidateDiagnosticVisualOverride(USkeletalMeshComponent* VisualMesh, USkeletalMesh* NewMesh,
		const FFutsalPose17MeshIdentity& ExpectedIdentity, FString& OutError);
	/** 仅PIE显式诊断调用，切换新mesh自身材质，保留共享动画实例。 */
	static bool ApplyDiagnosticVisualOverride(USkeletalMeshComponent* VisualMesh, USkeletalMesh* NewMesh,
		const FFutsalPose17MeshIdentity& ExpectedIdentity, FFutsalPose17VisualMeshState& OutPrevious,
		FFutsalPose17VisualOverrideEvidence& OutEvidence, FString& OutError);
	/** 必须先恢复CPU状态再恢复mesh；逐项读回，不宣称streaming完全恢复。 */
	static bool RestoreDiagnosticVisualOverride(const FFutsalPose17VisualMeshState& Previous,
		FFutsalPose17VisualOverrideEvidence& InOutEvidence, FString& OutError);
	/** 只读当前组件 CPU/LOD/streaming 状态，不准备或刷新动画。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool GetVisualSamplingState(USkeletalMeshComponent* VisualMesh, FFutsalPose17CPUState& OutState, FString& OutError);

	/** 仅允许 PIE smoke 使用，单次 job 预备 CPU skin 与 LOD0，不保存资产。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool PrepareVisualCPUSampling(USkeletalMeshComponent* VisualMesh, FFutsalPose17CPUState& OutPreviousState, FString& OutError);

	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool RestoreVisualCPUSampling(USkeletalMeshComponent* VisualMesh, const FFutsalPose17CPUState& PreviousState,
		bool& bOutStreamingStateMatched, FString& OutError);

	/** 每 sample 一次：提交当前实际动态数据并等待渲染线程，不重新评估动画或切 CPU skin。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool SynchronizeVisualCPUCaches(const TArray<USkeletalMeshComponent*>& VisualMeshes, FString& OutError);
	/** 只读已加载 LOD0 身份；不计算动画或自动寻找 CharacterMesh0。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool DescribeVisualMesh(USkeletalMeshComponent* VisualMesh, FFutsalPose17MeshIdentity& OutIdentity, FString& OutError);

	/** 只读参考形状用于 UE 锚点映射；输出 component cm，绝不是当前动画世界点。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool ReadVisualReferenceGeometry(USkeletalMeshComponent* VisualMesh,
		TArray<FVector>& OutReferencePositionsCm, TArray<FIntVector>& OutTriangles,
		FFutsalPose17MeshIdentity& OutIdentity, FString& OutError);

	/** 只读资产 LOD0，用于批量角色锚点映射；不 spawn、不修改场景。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool ReadAssetReferenceGeometry(USkeletalMesh* Asset,
		TArray<FVector>& OutReferencePositionsCm, TArray<FIntVector>& OutTriangles,
		FFutsalPose17MeshIdentity& OutIdentity, FString& OutError);

	/** 默认只读已有 CPU skin 缓存。诊断开关会触发引擎重评姿态/切 skinning，不适作生产同步证据。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17")
	static bool SampleVisualPose17(USkeletalMeshComponent* VisualMesh,
		const FFutsalPose17MeshIdentity& ExpectedIdentity,
		const TArray<FFutsalPose17SurfaceAnchor>& HeadAnchors,
		const FString& ManifestSHA256, bool bAllowSlowDiagnosticSnapshot,
		FFutsalPose17Sample& OutSample, FString& OutError);

	/** 无 UObject 的插值原语，供自动化测试及后续 MRQ 原生采样复用。 */
	static bool InterpolateTriangle(const FVector& A, const FVector& B, const FVector& C,
		const FVector& Weights, FVector& OutPoint, FString& OutError);
};
