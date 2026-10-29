#if WITH_DEV_AUTOMATION_TESTS

#include "JerseyNumberUVLibrary.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Misc/AutomationTest.h"
#include "UObject/UObjectGlobals.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FJerseyNumberUVParameterValidationTest,
	"FutsalMOT.JerseyNumberUV.RejectsInvalidInputs",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FJerseyNumberUVParameterValidationTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	FJerseyNumberUVParameters Input;
	FString Error;
	for (int32 Number = 1; Number <= 99; ++Number)
	{
		Input.Number = Number;
		TestTrue(TEXT("合法号码范围"), UJerseyNumberUVLibrary::ValidateNumberParameters(Input, Error));
	}
	Input.Number = 0;
	TestFalse(TEXT("拒绝零号码"), UJerseyNumberUVLibrary::ValidateNumberParameters(Input, Error));
	Input.Number = 17;
	Input.EntityMaskID = 42;
	TestFalse(TEXT("拒绝其它实体 ID"), UJerseyNumberUVLibrary::ValidateNumberParameters(Input, Error));
	Input.EntityMaskID = 32;
	Input.UVRect.B = Input.UVRect.R;
	TestFalse(TEXT("拒绝退化矩形"), UJerseyNumberUVLibrary::ValidateNumberParameters(Input, Error));
	Input.UVRect = FLinearColor(0.1f, 0.2f, 0.3f, 0.4f);
	Input.UVRect.R = std::numeric_limits<float>::quiet_NaN();
	TestFalse(TEXT("拒绝 NaN"), UJerseyNumberUVLibrary::ValidateNumberParameters(Input, Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FJerseyNumberUVSemanticSlotTest,
	"FutsalMOT.JerseyNumberUV.UsesSemanticSlotRatherThanFixedIndex",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FJerseyNumberUVSemanticSlotTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	const FName Jersey(TEXT("\u6750\u8d28"));
	TestEqual(TEXT("Player_004 球衣位于索引 2"),
		UJerseyNumberUVLibrary::FindUniqueJerseySlotFromNames({ TEXT("Human_body"), TEXT("Human_eyebrow001"), Jersey }), 2);
	TestEqual(TEXT("Player_003 球衣位于索引 3"),
		UJerseyNumberUVLibrary::FindUniqueJerseySlotFromNames({ TEXT("Human_body"), TEXT("Human_afro01"), TEXT("Human_eyebrow001"), Jersey }), 3);
	TestEqual(TEXT("拒绝重复球衣 slot"),
		UJerseyNumberUVLibrary::FindUniqueJerseySlotFromNames({ Jersey, Jersey }), INDEX_NONE);
	TestEqual(TEXT("拒绝缺失球衣 slot"),
		UJerseyNumberUVLibrary::FindUniqueJerseySlotFromNames({ TEXT("Human_body") }), INDEX_NONE);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FJerseyNumberUVPreviewIsolationTest,
	"FutsalMOT.JerseyNumberUV.RejectsUnownedPreviewLifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FJerseyNumberUVPreviewIsolationTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	FString Error;
	TestNull(TEXT("无源网格不能创建临时球员"),
		UJerseyNumberUVLibrary::CreateNumberPreviewMesh(nullptr, nullptr, FTransform::Identity, Error));
	TestTrue(TEXT("创建失败提供错误原因"), !Error.IsEmpty());
	TestNull(TEXT("无源网格不能创建号码代理"),
		UJerseyNumberUVLibrary::CreateNumberMaskFollower(nullptr, nullptr, nullptr, 32, Error));
	USkeletalMeshComponent* Unrelated = NewObject<USkeletalMeshComponent>(GetTransientPackage());
	TestFalse(TEXT("不删除不属于测试接口的组件"),
		UJerseyNumberUVLibrary::DestroyNumberPreviewMesh(Unrelated, Error));
	TestFalse(TEXT("不删除身份不匹配的代理"),
		UJerseyNumberUVLibrary::DestroyNumberMaskFollower(Unrelated, Unrelated, Error));
	TestTrue(TEXT("拒绝销毁后无关组件仍有效"), IsValid(Unrelated));
	int64 Frame = 123;
	TestFalse(TEXT("无测试 Owner 时拒绝捕获并且不写文件"),
		UJerseyNumberUVLibrary::CaptureNumberPreviewPair(Unrelated, nullptr, FTransform::Identity,
			512, 512, 35.0f, TEXT(""), TEXT("back"), Frame, Error));
	TestEqual(TEXT("失败不提供伪造帧索引"), Frame, int64(-1));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FJerseyNumberUVPersistentViewStateTest,
	"FutsalMOT.JerseyNumberUV.SingleCaptureNeedsPersistentViewState",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FJerseyNumberUVPersistentViewStateTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	USceneCaptureComponent2D* Capture = NewObject<USceneCaptureComponent2D>(GetTransientPackage());
	Capture->bCaptureEveryFrame = false;
	Capture->bAlwaysPersistRenderingState = false;
	TestTrue(TEXT("无持久状态时单次捕获没有 ViewState，不能应用后处理材质"), Capture->GetViewState(0) == nullptr);
	Capture->bAlwaysPersistRenderingState = true;
	TestTrue(TEXT("启用持久状态后单次捕获能够分配 ViewState"), Capture->GetViewState(0) != nullptr);
	Capture->bAlwaysPersistRenderingState = false;
	TestTrue(TEXT("测试结束释放持久 ViewState"), Capture->GetViewState(0) == nullptr);
	return true;
}

#endif
