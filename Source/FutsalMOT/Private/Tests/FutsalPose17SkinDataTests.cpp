#include "FutsalPose17SkinDataLibrary.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFutsalPose17SkinDataTest, "FutsalMOT.Pose17.SkinDataReadOnlyContract",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPose17SkinDataTest::RunTest(const FString& Parameters)
{
	FString Error;
	TArray<int32> Global;
	TArray<float> Weights;
	if (!TestTrue(TEXT("局部骨经实际section调色板映射"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{2, 0}, 3, {0, 1}, {32768, 32767}, Global, Weights, Error))) return false;
	TestTrue(TEXT("全局骨不是局部骨索引"), Global == TArray<int32>({2, 0}));
	TestEqual(TEXT("使用引擎u16浮点常量"), Weights[0], static_cast<float>(32768) * (1.0f / 65535.0f));
	if (!TestTrue(TEXT("零权重槽位保留顺序"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{2, 0}, 3, {0, 1}, {65535, 0}, Global, Weights, Error))) return false;
	TestEqual(TEXT("零权重仍有第二槽"), Global.Num(), 2);
	TestEqual(TEXT("零权重仍为零"), Weights[1], 0.f);
	if (!TestTrue(TEXT("不擅自重新归一化原权重"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{2, 0}, 3, {0, 1}, {1, 1}, Global, Weights, Error))) return false;
	TestEqual(TEXT("小权重不改为一半"), Weights[0], 1.0f / 65535.0f);
	TestFalse(TEXT("骨调色板越界拒绝"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{2, 0}, 3, {2}, {65535}, Global, Weights, Error));
	TestTrue(TEXT("失败不返回局部伪成功数据"), Global.IsEmpty() && Weights.IsEmpty());
	TestFalse(TEXT("零权重骨索引也不能越界"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{2, 0}, 3, {0, 2}, {65535, 0}, Global, Weights, Error));
	TestFalse(TEXT("骨调色板全局骨越界拒绝"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{3}, 3, {0}, {65535}, Global, Weights, Error));
	TestFalse(TEXT("全部零权重拒绝"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{0}, 1, {0}, {0}, Global, Weights, Error));
	TestFalse(TEXT("u16范围外拒绝"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{0}, 1, {0}, {65536}, Global, Weights, Error));
	TestFalse(TEXT("槽位长度不同拒绝"), UFutsalPose17SkinDataLibrary::ResolveSectionInfluences(
		{0}, 1, {0}, {}, Global, Weights, Error));
	FFutsalPose17MeshIdentity Identity;
	FFutsalPose17SkinData Data;
	Data.bReadSucceeded = true;
	Data.RawWeightDataBase64 = TEXT("旧结果不能残留");
	TestFalse(TEXT("空资产不创建替身component"), UFutsalPose17SkinDataLibrary::ReadAssetBaseSkinData(
		nullptr, Identity, TEXT("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), Data, Error));
	TestFalse(TEXT("失败不会自称读取成功"), Data.bReadSucceeded);
	TestTrue(TEXT("失败清空旧字节"), Data.RawWeightDataBase64.IsEmpty());
	TestFalse(TEXT("从不自称读取component有效权重"), Data.bComponentEffectiveWeightsRead);
	TestFalse(TEXT("从不自称动态重建通过"), Data.bDynamicSurfaceReconstructionVerified);
	return true;
}
#endif
