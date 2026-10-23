#pragma once

#include "CoreMinimal.h"
#include "FutsalPose17Library.h"
#include "MoviePipelineRenderPass.h"
#include "Camera/CameraComponent.h"
#include "FutsalPose17MRQPass.generated.h"

/** 显式 PIE 实例绑定；名字为 UObject 名，不是包含匹配的 Actor label。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17MRQTarget
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FString EntityID;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FName ActorObjectName;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FName ComponentObjectName;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FFutsalPose17MeshIdentity ExpectedIdentity;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") TArray<FFutsalPose17SurfaceAnchor> HeadAnchors;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FString ManifestSHA256;
	/** 默认空；仅显式PIE逐角色校准可给定新角色mesh，不修改资产或Editor组件。 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") TObjectPtr<USkeletalMesh> DiagnosticVisualMeshOverride = nullptr;
};

USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17MRQRecord
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString EntityID;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 OutputFrame = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 SequenceSourceFrame = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 ShotIndex = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 CameraIndex = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString CameraName;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 TemporalSampleIndex = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 SpatialSampleIndex = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int64 HookEngineFrame = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") double MRQWorldSeconds = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 TemporalSampleCount = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int32 SpatialSampleCount = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") float MotionBlurFraction = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bCacheFenceCompletedThisEngineFrame = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString PoseFenceMethod;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bEndFrameUpdateTasksFinished = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FVector CameraWorldLocationM = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FVector CameraForward = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FVector CameraRight = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FVector CameraUp = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") float CameraHorizontalFOVDegrees = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") float CameraAspectRatio = 0;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bCameraConstrainAspectRatio = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString CameraAspectRatioAxisConstraint;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FVector2D OffCenterProjectionOffset = FVector2D::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FVector2D ProjectionJitter = FVector2D::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FIntPoint ImageSize = FIntPoint::ZeroValue;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FTransform ActorWorldTransformUECm;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FTransform VisualWorldTransformUECm;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bCineCameraLookAtStateObserved = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bCineCameraLookAtEnabled = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int64 OverrideWarmupEngineFramesObserved = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") int64 GpuLbsWarmupEngineFramesObserved = -1;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") bool bSampleSucceeded = false;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FString Error;
	UPROPERTY(BlueprintReadOnly, Category="FutsalMOT|Pose17") FFutsalPose17Sample Sample;
};

USTRUCT()
struct FFutsalPose17DriverState
{
	GENERATED_BODY()
	UPROPERTY() TObjectPtr<USkeletalMeshComponent> Component = nullptr;
	UPROPERTY() bool bVisible = false;
	UPROPERTY() bool bHiddenInGame = false;
	UPROPERTY() uint8 AnimationTickOption = 0;
};

USTRUCT()
struct FFutsalPose17CameraState
{
	GENERATED_BODY()
	UPROPERTY() TObjectPtr<UCameraComponent> Component = nullptr;
	UPROPERTY() FPostProcessSettings PostProcess;
	UPROPERTY() float BlendWeight = 0;
};

/** 元数据诊断 pass，不输出图像、不声明 RGB/mask 配对成功，不修改现有 Recorder。 */
UCLASS(BlueprintType, meta=(DisplayName="Futsal Pose17 Diagnostic Samples"))
class FUTSALMOT_API UFutsalPose17MRQPass : public UMoviePipelineRenderPass
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") TArray<FFutsalPose17MRQTarget> Targets;
	/** 明确 opt-in，且只在 PIE 实例生效；不修改 Editor 原组件。 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") bool bPrepareCPUForDiagnostic = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") bool bHideDriverForDiagnostic = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") bool bAllowPIEVisualMeshOverride = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") bool bAllowJointPose17Diagnostic = false;
	/** 新opt-in：实际渲染保持GPU，只在CPU按真实pose/weights计算坐标。 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") bool bUseGpuRenderCpuLbsForDiagnostic = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17", meta=(ClampMin="8", ClampMax="120")) int32 MinimumGpuLbsWarmupFrames = 8;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FString DiagnosticScope;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17", meta=(ClampMin="8", ClampMax="120")) int32 MinimumOverrideWarmupFrames = 8;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") TArray<FName> DiagnosticCameraObjectNames;
	/** 会话自有绝对文件，必须位于Saved/Pose17Development/smoke且不存在。 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17") FString DiagnosticReceiptFile;
	UPROPERTY(BlueprintReadOnly, Transient, Category="FutsalMOT|Pose17") FString ReceiptWriteError;
	/** 达到上限保留已采样记录，停止本 pass 采样，不取消或假装完成 MRQ。 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Pose17", meta=(ClampMin="1", ClampMax="4096")) int32 MaxRecords = 64;
	UPROPERTY(BlueprintReadOnly, Transient, Category="FutsalMOT|Pose17") TArray<FFutsalPose17MRQRecord> Records;
	UPROPERTY(BlueprintReadOnly, Transient, Category="FutsalMOT|Pose17") bool bRecordLimitReached = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="FutsalMOT|Pose17") FString SetupError;
	UPROPERTY(BlueprintReadOnly, Transient, Category="FutsalMOT|Pose17") TArray<FString> RestoreErrors;
	UPROPERTY(BlueprintReadOnly, Transient, Category="FutsalMOT|Pose17") bool bStreamingStateRestartRequired = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="FutsalMOT|Pose17") bool bCameraStateRestored = false;
protected:
	virtual void SetupForPipelineImpl(UMoviePipeline* InPipeline) override;
	virtual void TeardownForPipelineImpl(UMoviePipeline* InPipeline) override;
	virtual void SetupImpl(const MoviePipeline::FMoviePipelineRenderPassInitSettings& InPassInitSettings) override;
	virtual void RenderSample_GameThreadImpl(const FMoviePipelineRenderPassMetrics& InSampleState) override;
	virtual void OnFrameStartImpl() override;
	virtual void TeardownImpl() override;
	virtual bool IsValidOnShots() const override { return false; }
	virtual bool IsValidOnPrimary() const override { return true; }
private:
	UPROPERTY(Transient) TArray<TObjectPtr<USkeletalMeshComponent>> PreparedMeshes;
	UPROPERTY(Transient) TArray<FFutsalPose17CPUState> PreviousCPUStates;
	UPROPERTY(Transient) TArray<TObjectPtr<USkeletalMeshComponent>> PreparedGPUMeshes;
	UPROPERTY(Transient) TArray<FFutsalPose17CPUState> PreviousGPULODStates;
	UPROPERTY(Transient) TArray<FFutsalPose17DriverState> PreviousDriverStates;
	UPROPERTY(Transient) TArray<FFutsalPose17CameraState> PreviousCameraStates;
	UPROPERTY(Transient) TArray<TObjectPtr<USkeletalMeshComponent>> FrameMeshes;
	UPROPERTY(Transient) TArray<FFutsalPose17VisualMeshState> PreviousVisualStates;
	UPROPERTY(Transient) TArray<FFutsalPose17VisualOverrideEvidence> VisualOverrideEvidence;
	TArray<uint32> FramePoseRevisions;
	FString FrameCacheError;
	int64 CacheFenceEngineFrame = -1;
	int64 GPUPreparedEngineFrame = -1;
	FString CameraSetupError;
	void PersistNativeReceipt();
	void RestoreVisualOverrides();
};
