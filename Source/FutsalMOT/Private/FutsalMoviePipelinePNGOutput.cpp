#include "FutsalMoviePipelinePNGOutput.h"

#include "ImagePixelData.h"
#include "MoviePipeline.h"
#include "MoviePipelineTelemetry.h"

DEFINE_LOG_CATEGORY_STATIC(LogFutsalPNGOutput, Log, All);

UFutsalMoviePipelinePNGOutput::UFutsalMoviePipelinePNGOutput()
{
	// 原生 PNG 类为 MinimalAPI 且遥测方法未导出；使用已导出的图像输出基类。
	// 保持原生 PNG 的格式和 alpha 默认值，其余编码及 fence 仍由基类处理。
	OutputFormat = EImageFormat::PNG;
}

bool UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(
	const FMoviePipelineMergerOutputFrame& Input,
	FMoviePipelineMergerOutputFrame& Output,
	FString& OutError)
{
	OutError.Reset();
	if (&Input == &Output)
	{
		OutError = TEXT("PNG 过滤必须使用独立输出帧，拒绝修改共享合并帧");
		return false;
	}
	const FMoviePipelinePassIdentifier* SelectedKey = nullptr;
	const FImagePixelData* SelectedPixels = nullptr;
	int32 FinalImageCount = 0;
	for (const auto& Pass : Input.ImageOutputData)
	{
		if (Pass.Value)
		{
			const FImagePixelDataPayload* OtherPayload = Pass.Value->GetPayload<FImagePixelDataPayload>();
			if (OtherPayload && OtherPayload->bCompositeToFinalImage)
			{
				OutError = TEXT("PNG 过滤拒绝合成 overlay 输入，避免静默改变原生 FinalImage RGB");
				return false;
			}
		}
		// 相机属于 CameraName 字段；前缀匹配会误选 FinalImage 的后处理/分层 pass。
		if (Pass.Key.Name == TEXT("FinalImage"))
		{
			++FinalImageCount;
			SelectedKey = &Pass.Key;
			SelectedPixels = Pass.Value.Get();
		}
	}
	if (FinalImageCount != 1 || !SelectedPixels)
	{
		OutError = FString::Printf(TEXT("每帧必须恰有一个有效 FinalImage，实际数量为 %d"), FinalImageCount);
		return false;
	}
	int32 ExpectedFinalImageCount = 0;
	for (const FMoviePipelinePassIdentifier& Key : Input.ExpectedRenderPasses)
	{
		ExpectedFinalImageCount += Key.Name == TEXT("FinalImage") ? 1 : 0;
	}
	const FImagePixelDataPayload* Payload = SelectedPixels->GetPayload<FImagePixelDataPayload>();
	if (ExpectedFinalImageCount != 1 || !Input.ExpectedRenderPasses.Contains(*SelectedKey)
		|| !Payload || Payload->PassIdentifier != *SelectedKey || Payload->bCompositeToFinalImage
		|| Input.FrameOutputState.OutputFrameNumber < 0
		|| Payload->SampleState.OutputState.OutputFrameNumber != Input.FrameOutputState.OutputFrameNumber
		|| Payload->SampleState.OutputState.ShotIndex != Input.FrameOutputState.ShotIndex
		|| SelectedPixels->GetSize().X <= 0 || SelectedPixels->GetSize().Y <= 0
		|| !SelectedPixels->IsDataWellFormed())
	{
		OutError = TEXT("FinalImage 的 expected key、相机、payload、帧号、shot 或像素数据不一致");
		return false;
	}

	FMoviePipelineMergerOutputFrame Filtered;
	Filtered.FrameOutputState = Input.FrameOutputState;
	Filtered.ExpectedRenderPasses.Add(*SelectedKey);
	// 像素独立持有；payload 仅按引擎 CopyImageData 协议共享且保持只读。
	TUniquePtr<FImagePixelData> Pixels = SelectedPixels->CopyImageData();
	if (!Pixels || !Pixels->IsDataWellFormed() || Pixels->GetSize() != SelectedPixels->GetSize()
		|| Pixels->GetType() != SelectedPixels->GetType())
	{
		OutError = TEXT("FinalImage 像素复制失败，拒绝提交不完整 PNG 输出");
		return false;
	}
	Filtered.ImageOutputData.Add(*SelectedKey, MoveTemp(Pixels));
	Output = MoveTemp(Filtered);
	return true;
}

void UFutsalMoviePipelinePNGOutput::OnReceiveImageDataImpl(FMoviePipelineMergerOutputFrame* InMergedOutputFrame)
{
	FMoviePipelineMergerOutputFrame Filtered;
	FString Error;
	if (!InMergedOutputFrame || !BuildFinalImageFrame(*InMergedOutputFrame, Filtered, Error))
	{
		UE_LOG(LogFutsalPNGOutput, Error, TEXT("FinalImage PNG 输出失败：%s"),
			InMergedOutputFrame ? *Error : TEXT("合并帧为空"));
		if (UMoviePipeline* Pipeline = GetPipeline())
		{
			Pipeline->RequestShutdown(true);
		}
		return;
	}
	// 原生输出器保留文件名解析、色彩量化、异步写入及完成 fence 语义。
	Super::OnReceiveImageDataImpl(&Filtered);
}

void UFutsalMoviePipelinePNGOutput::UpdateTelemetry(FMoviePipelineShotRenderTelemetry* InTelemetry) const
{
	// 与原生 PNG 输出器保持相同遥测标记。
	if (InTelemetry)
	{
		InTelemetry->bUsesPNG = true;
	}
}
