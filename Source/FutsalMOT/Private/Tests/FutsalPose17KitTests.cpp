#include "FutsalPose17KitLibrary.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFutsalPose17KitContractTest, "FutsalMOT.Pose17.SeededKitContract",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPose17KitContractTest::RunTest(const FString& Parameters)
{
	int32 Jersey = INDEX_NONE, Shorts = INDEX_NONE;
	FString Error;
	TestTrue(TEXT("复用已验语义slot，不依赖索引顺序"), UFutsalPose17KitLibrary::ResolveSemanticKitSlots(
		{TEXT("Human_body"), TEXT("Human_futsalmot_shorts_male_final"), TEXT("材质")}, Jersey, Shorts, Error));
	TestEqual(TEXT("球衣实际索引"), Jersey, 2); TestEqual(TEXT("短裤实际索引"), Shorts, 1);
	TestFalse(TEXT("拒绝重复球衣语义"), UFutsalPose17KitLibrary::ResolveSemanticKitSlots(
		{TEXT("材质"), TEXT("材质"), TEXT("Human_futsalmot_shorts_male_final")}, Jersey, Shorts, Error));
	TestFalse(TEXT("拒绝猜测英文Jersey slot"), UFutsalPose17KitLibrary::ResolveSemanticKitSlots(
		{TEXT("Jersey"), TEXT("Shorts")}, Jersey, Shorts, Error));
	TestFalse(TEXT("不凭Set ID伪造已加载材质"), UFutsalPose17KitLibrary::ValidateSeededKitAssets(nullptr, nullptr, TEXT("03"), Error));
	TestFalse(TEXT("不自动准入Set06扩展目录"), UFutsalPose17KitLibrary::ValidateSeededKitAssets(nullptr, nullptr, TEXT("06"), Error));
	FFutsalPose17KitState Previous;
	FFutsalPose17KitEvidence Evidence;
	TestFalse(TEXT("无真实PIE组件不apply"), UFutsalPose17KitLibrary::ApplySeededKit(nullptr, nullptr, nullptr, TEXT("03"), TEXT(""), Previous, Evidence, Error));
	TestFalse(TEXT("失败不能声称已mutation"), Previous.bMutationStarted);
	TestFalse(TEXT("未应用不能声称读回成功"), UFutsalPose17KitLibrary::VerifySeededKit(Previous, Error));
	TestFalse(TEXT("未应用不能声称恢复"), UFutsalPose17KitLibrary::RestoreSeededKit(Previous, Evidence, Error));
	TestTrue(TEXT("恢复失败保留尝试证据"), Evidence.bRestoreAttempted);
	return true;
}
#endif
