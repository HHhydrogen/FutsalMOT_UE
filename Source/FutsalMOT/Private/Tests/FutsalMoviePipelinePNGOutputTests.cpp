#if WITH_DEV_AUTOMATION_TESTS

#include "FutsalMoviePipelinePNGOutput.h"
#include "ImagePixelData.h"
#include "Math/Float16Color.h"
#include "Misc/AutomationTest.h"

namespace
{
	template<typename PixelType>
	void AddPass(FMoviePipelineMergerOutputFrame& Frame, const FMoviePipelinePassIdentifier& Key,
		TArray64<PixelType>&& Pixels)
	{
		TSharedPtr<FImagePixelDataPayload, ESPMode::ThreadSafe> Payload =
			MakeShared<FImagePixelDataPayload, ESPMode::ThreadSafe>();
		Payload->PassIdentifier = Key;
		Payload->SampleState.OutputState = Frame.FrameOutputState;
		Frame.ExpectedRenderPasses.Add(Key);
		Frame.ImageOutputData.Add(Key,
			MakeUnique<TImagePixelData<PixelType>>(FIntPoint(2, 2), MoveTemp(Pixels), Payload));
	}

	TArray64<FColor> ColorPixels()
	{
		return { FColor(1, 2, 3, 4), FColor(254, 128, 0, 255),
			FColor(0, 255, 80, 0), FColor(50, 70, 90, 120) };
	}

	TArray64<FFloat16Color> HDRPixels()
	{
		return { FFloat16Color(FLinearColor(2.0f, 0.5f, 0.125f, 1.0f)),
			FFloat16Color(FLinearColor(0.0f, 4.0f, 0.25f, 0.5f)),
			FFloat16Color(FLinearColor(0.75f, 0.125f, 0.5f, 0.0f)),
			FFloat16Color(FLinearColor(1.0f, 1.5f, 3.0f, 1.0f)) };
	}

	void SetState(FMoviePipelineMergerOutputFrame& Frame)
	{
		Frame.FrameOutputState.OutputFrameNumber = 123;
		Frame.FrameOutputState.ShotIndex = 2;
		Frame.FrameOutputState.ShotOutputFrameNumber = 7;
		Frame.FrameOutputState.CameraName = TEXT("Camera_01");
		Frame.FrameOutputState.CameraNameOverride = TEXT("cam_01");
		Frame.FrameOutputState.ShotName = TEXT("shot_001");
		Frame.FrameOutputState.FileMetadata.Add(TEXT("cryptomatte/abc/name"), TEXT("ActorHitProxyMask"));
		Frame.FrameOutputState.FileMetadata.Add(TEXT("cryptomatte/abc/manifest"), TEXT("{\"Player_L0\":\"3f800001\"}"));
	}

	void AddAuxiliaryPasses(FMoviePipelineMergerOutputFrame& Frame)
	{
		for (int32 Index = 0; Index < 3; ++Index)
		{
			TArray64<FLinearColor> Pixels;
			for (int32 Pixel = 0; Pixel < 4; ++Pixel)
			{
				Pixels.Add(FLinearColor(1.0f + Index, 0.75f, 2.0f + Pixel, 0.25f));
			}
			AddPass(Frame, FMoviePipelinePassIdentifier(
				FString::Printf(TEXT("ActorHitProxyMask%02d"), Index)), MoveTemp(Pixels));
		}
		AddPass(Frame, FMoviePipelinePassIdentifier(TEXT("BurnInOverlay")), ColorPixels());
	}

	TArray<uint8> ReadBytes(const FImagePixelData& Pixels)
	{
		const void* Data = nullptr;
		int64 Length = 0;
		TArray<uint8> Bytes;
		if (Pixels.GetRawData(Data, Length))
		{
			Bytes.Append(static_cast<const uint8*>(Data), static_cast<int32>(Length));
		}
		return Bytes;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPNGPreservesSharedFrameTest,
	"FutsalMOT.PNGOutput.CopiesOnlyFinalImageAndPreservesSharedFrame",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPNGPreservesSharedFrameTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	FMoviePipelineMergerOutputFrame Source;
	SetState(Source);
	const FMoviePipelinePassIdentifier Final(TEXT("FinalImage"), TEXT("Camera_01"));
	AddPass(Source, Final, HDRPixels());
	AddAuxiliaryPasses(Source);
	const TArray<FMoviePipelinePassIdentifier> ExpectedBefore = Source.ExpectedRenderPasses;
	TMap<FMoviePipelinePassIdentifier, const FImagePixelData*> PointersBefore;
	TMap<FMoviePipelinePassIdentifier, TArray<uint8>> BytesBefore;
	for (const auto& Pass : Source.ImageOutputData)
	{
		PointersBefore.Add(Pass.Key, Pass.Value.Get());
		BytesBefore.Add(Pass.Key, ReadBytes(*Pass.Value));
	}
	FMoviePipelineMergerOutputFrame Filtered;
	FString Error;
	if (!TestTrue(TEXT("合法 HDR 帧可过滤"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Filtered, Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("只保留一个像素 pass"), Filtered.ImageOutputData.Num(), 1);
	TestTrue(TEXT("expected 只保留同一完整相机 key"),
		Filtered.ExpectedRenderPasses == TArray<FMoviePipelinePassIdentifier>{ Final });
	TestEqual(TEXT("输出帧号保持"), Filtered.FrameOutputState.OutputFrameNumber, 123);
	TestEqual(TEXT("shot 帧号保持"), Filtered.FrameOutputState.ShotOutputFrameNumber, 7);
	TestEqual(TEXT("shot 索引保持"), Filtered.FrameOutputState.ShotIndex, 2);
	TestEqual(TEXT("相机名称保持"), Filtered.FrameOutputState.CameraName, FString(TEXT("Camera_01")));
	TestEqual(TEXT("相机格式名称保持"), Filtered.FrameOutputState.CameraNameOverride, FString(TEXT("cam_01")));
	TestEqual(TEXT("manifest 完整保持"), Filtered.FrameOutputState.FileMetadata.FindRef(TEXT("cryptomatte/abc/manifest")),
		Source.FrameOutputState.FileMetadata.FindRef(TEXT("cryptomatte/abc/manifest")));
	const FImagePixelData& Copy = *Filtered.ImageOutputData.FindChecked(Final);
	TestTrue(TEXT("HDR 位深不发生量化"), Copy.GetType() == EImagePixelType::Float16 && Copy.GetBitDepth() == 16);
	TestTrue(TEXT("复制后像素逐字节一致"), ReadBytes(Copy) == BytesBefore.FindChecked(Final));
	TestTrue(TEXT("复制数据独立持有"), &Copy != Source.ImageOutputData.FindChecked(Final).Get());
	const void* CopyData = nullptr;
	const void* SourceData = nullptr;
	int64 CopySize = 0, SourceSize = 0;
	Copy.GetRawData(CopyData, CopySize);
	Source.ImageOutputData.FindChecked(Final)->GetRawData(SourceData, SourceSize);
	TestTrue(TEXT("底层像素 buffer 不共享"), CopyData != SourceData && CopySize == SourceSize);
	Filtered.FrameOutputState.FileMetadata.Add(TEXT("local_only"), TEXT("yes"));
	TestFalse(TEXT("局部 metadata 修改不影响源帧"), Source.FrameOutputState.FileMetadata.Contains(TEXT("local_only")));
	TestTrue(TEXT("源 expected pass 集合保持"), Source.ExpectedRenderPasses == ExpectedBefore);
	TestEqual(TEXT("源仍包含全部五个 pass"), Source.ImageOutputData.Num(), 5);
	for (const auto& Pass : Source.ImageOutputData)
	{
		TestTrue(TEXT("原始像素对象地址保持"), Pass.Value.Get() == PointersBefore.FindChecked(Pass.Key));
		TestTrue(TEXT("原始像素字节保持"), ReadBytes(*Pass.Value) == BytesBefore.FindChecked(Pass.Key));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPNGEightBitTest,
	"FutsalMOT.PNGOutput.PreservesEightBitPixelsAndCameraKey",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPNGEightBitTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	FMoviePipelineMergerOutputFrame Source, Filtered;
	SetState(Source);
	const FMoviePipelinePassIdentifier Final(TEXT("FinalImage"), TEXT("Camera_with_suffix_04"));
	AddPass(Source, Final, ColorPixels());
	FString Error;
	if (!TestTrue(TEXT("8bit 帧可过滤"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Filtered, Error)))
	{
		AddError(Error);
		return false;
	}
	TestTrue(TEXT("相机后缀保留在 CameraName，不拼入或截断 Name"), Filtered.ImageOutputData.Contains(Final));
	const auto& Pixels = Filtered.ImageOutputData.FindChecked(Final);
	TestTrue(TEXT("8bit 类型保持"), Pixels->GetType() == EImagePixelType::Color && Pixels->GetBitDepth() == 8);
	TestTrue(TEXT("8bit 字节完整保持"), ReadBytes(*Pixels) == ReadBytes(*Source.ImageOutputData.FindChecked(Final)));
	TestEqual(TEXT("payload 完整相机保持"), Pixels->GetPayload<FImagePixelDataPayload>()->PassIdentifier.CameraName,
		FString(TEXT("Camera_with_suffix_04")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPNGRejectsAmbiguityTest,
	"FutsalMOT.PNGOutput.RejectsMissingAmbiguousOrInconsistentFinalImage",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPNGRejectsAmbiguityTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	FString Error;
	FMoviePipelineMergerOutputFrame Source, Output;
	SetState(Source);
	Output.FrameOutputState.OutputFrameNumber = 999;
	AddPass(Source, FMoviePipelinePassIdentifier(TEXT("FinalImageCamera_01")), ColorPixels());
	TestFalse(TEXT("不把 FinalImage 前缀的后处理 pass 误当最终图"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Output, Error));
	TestTrue(TEXT("失败返回明确错误"), !Error.IsEmpty());
	TestEqual(TEXT("失败时输出状态不变"), Output.FrameOutputState.OutputFrameNumber, 999);
	const FMoviePipelinePassIdentifier First(TEXT("FinalImage"), TEXT("Camera_01"));
	AddPass(Source, First, ColorPixels());
	AddPass(Source, FMoviePipelinePassIdentifier(TEXT("FinalImage"), TEXT("Camera_02")), ColorPixels());
	TestFalse(TEXT("多相机最终图歧义时拒绝而非只取第一个"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Output, Error));
	Source.ImageOutputData.Remove(FMoviePipelinePassIdentifier(TEXT("FinalImage"), TEXT("Camera_02")));
	Source.ExpectedRenderPasses.Remove(FMoviePipelinePassIdentifier(TEXT("FinalImage"), TEXT("Camera_02")));
	auto* Payload = Source.ImageOutputData.FindChecked(First)->GetPayload<FImagePixelDataPayload>();
	Payload->PassIdentifier.CameraName = TEXT("wrong_camera");
	TestFalse(TEXT("payload 相机与 key 不一致时拒绝"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Output, Error));
	Payload->PassIdentifier = First;
	Payload->SampleState.OutputState.OutputFrameNumber++;
	TestFalse(TEXT("payload 帧号与 merged frame 不一致时拒绝"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Output, Error));
	Payload->SampleState.OutputState = Source.FrameOutputState;
	Source.ExpectedRenderPasses.Remove(First);
	TestFalse(TEXT("expected pass 缺失时拒绝"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Output, Error));
	Source.ExpectedRenderPasses.Add(First);
	Source.ImageOutputData.FindChecked(First).Reset();
	TestFalse(TEXT("FinalImage key 对应空像素时拒绝"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Output, Error));
	TestFalse(TEXT("拒绝原位修改共享输入帧"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Source, Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPNGRejectsCompositedOverlayTest,
	"FutsalMOT.PNGOutput.RejectsCompositedOverlayInsteadOfChangingRGB",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPNGRejectsCompositedOverlayTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	FMoviePipelineMergerOutputFrame Source, Output;
	SetState(Source);
	const FMoviePipelinePassIdentifier Final(TEXT("FinalImage"), TEXT("Camera_01"));
	const FMoviePipelinePassIdentifier Overlay(TEXT("BurnInOverlay"), TEXT("Camera_01"));
	AddPass(Source, Final, HDRPixels());
	AddPass(Source, Overlay, ColorPixels());
	Source.ImageOutputData.FindChecked(Overlay)->GetPayload<FImagePixelDataPayload>()->bCompositeToFinalImage = true;
	const TArray<uint8> FinalBefore = ReadBytes(*Source.ImageOutputData.FindChecked(Final));
	const TArray<uint8> OverlayBefore = ReadBytes(*Source.ImageOutputData.FindChecked(Overlay));
	Output.FrameOutputState.OutputFrameNumber = 999;
	FString Error;
	TestFalse(TEXT("不静默丢弃原本会合成到 RGB 的 overlay"),
		UFutsalMoviePipelinePNGOutput::BuildFinalImageFrame(Source, Output, Error));
	TestTrue(TEXT("明确指出合成输入不受支持"), Error.Contains(TEXT("合成")));
	TestEqual(TEXT("失败不产生输出"), Output.ImageOutputData.Num(), 0);
	TestEqual(TEXT("失败不改输出帧号"), Output.FrameOutputState.OutputFrameNumber, 999);
	TestTrue(TEXT("拒绝后保留全部原 pass"), Source.ImageOutputData.Num() == 2 && Source.ExpectedRenderPasses.Num() == 2);
	TestTrue(TEXT("源最终图像素不改"), ReadBytes(*Source.ImageOutputData.FindChecked(Final)) == FinalBefore);
	TestTrue(TEXT("源 overlay 像素不改"), ReadBytes(*Source.ImageOutputData.FindChecked(Overlay)) == OverlayBefore);
	TestTrue(TEXT("源合成 flag 不改"),
		Source.ImageOutputData.FindChecked(Overlay)->GetPayload<FImagePixelDataPayload>()->bCompositeToFinalImage);
	return true;
}

#endif
