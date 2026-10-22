#pragma once

#include "CoreMinimal.h"
#include "MoviePipelineImageSequenceOutput.h"
#include "FutsalMoviePipelinePNGOutput.generated.h"

/** 只输出单相机 FinalImage PNG；其它消费者继续接收原始完整合并帧。 */
UCLASS(meta=(DisplayName="Futsal FinalImage PNG"))
class FUTSALMOT_API UFutsalMoviePipelinePNGOutput : public UMoviePipelineImageSequenceOutputBase
{
	GENERATED_BODY()

public:
	UFutsalMoviePipelinePNGOutput();
	virtual bool IsAlphaAllowed() const override { return bWriteAlpha; }
	virtual void OnReceiveImageDataImpl(FMoviePipelineMergerOutputFrame* InMergedOutputFrame) override;
	virtual void UpdateTelemetry(FMoviePipelineShotRenderTelemetry* InTelemetry) const override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "PNG")
	bool bWriteAlpha = true;

	/** 仅复制一个精确 FinalImage 的像素；失败时不更改输入或输出。 */
	static bool BuildFinalImageFrame(
		const FMoviePipelineMergerOutputFrame& Input,
		FMoviePipelineMergerOutputFrame& Output,
		FString& OutError);

#if WITH_EDITOR
	virtual FText GetDisplayText() const override
	{
		return NSLOCTEXT("FutsalMOT", "FinalImagePNGOutput", "Futsal FinalImage PNG");
	}
#endif
};
