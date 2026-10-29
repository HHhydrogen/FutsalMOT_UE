#pragma once

#include "CoreMinimal.h"
#include "FutsalPose17MRQPass.h"
#include "FutsalBody12MRQPass.generated.h"

/** 完整episode逐帧元数据；沿用GPU同步方法，十二点仅取实际可见网格的骨骼原点。 */
UCLASS(BlueprintType, meta=(DisplayName="Futsal Body12 Frame Metadata"))
class FUTSALMOT_API UFutsalBody12MRQPass : public UMoviePipelineRenderPass
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FFutsalPose17MRQTarget> Targets;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FName CameraObjectName;
	/** 只允许Saved/SingleSeed下的新文件；JSONL逐帧落盘，不积压整个episode。 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString MetadataFile;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 ExpectedFrames = 0;
	UPROPERTY(BlueprintReadOnly, Transient) FString CaptureError;
protected:
	virtual void SetupForPipelineImpl(UMoviePipeline* InPipeline) override;
	virtual void SetupImpl(const MoviePipeline::FMoviePipelineRenderPassInitSettings& InPassInitSettings) override;
	virtual void OnFrameStartImpl() override;
	virtual void RenderSample_GameThreadImpl(const FMoviePipelineRenderPassMetrics& State) override;
	virtual void TeardownImpl() override;
	virtual bool IsValidOnShots() const override { return false; }
	virtual bool IsValidOnPrimary() const override { return true; }
private:
	UPROPERTY(Transient) TArray<TObjectPtr<USkeletalMeshComponent>> Meshes;
	UPROPERTY(Transient) TArray<FFutsalPose17CPUState> PreviousLOD;
	UPROPERTY(Transient) TArray<FFutsalPose17DriverState> PreviousDrivers;
	UPROPERTY(Transient) TObjectPtr<UCameraComponent> Camera = nullptr;
	FPostProcessSettings PreviousPostProcess;
	float PreviousBlend = 0;
	TArray<uint32> Revisions;
	int64 FenceFrame = -1;
	int32 WrittenFrames = 0;
	bool bCameraPrepared = false;
	bool bRestored = false;
};
