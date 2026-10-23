#include "FutsalPose17Library.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFutsalPose17TriangleTest, "FutsalMOT.Pose17.SurfaceTriangle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPose17TriangleTest::RunTest(const FString& Parameters)
{
	FVector Point;
	FString Error;
	TestTrue(TEXT("合法表面插值"), UFutsalPose17Library::InterpolateTriangle(
		FVector(0, 0, 0), FVector(2, 0, 0), FVector(0, 2, 0), FVector(.5, .25, .25), Point, Error));
	TestTrue(TEXT("精确重心位置"), Point.Equals(FVector(.5, .5, 0), 1.e-12));
	TestFalse(TEXT("负权重拒绝"), UFutsalPose17Library::InterpolateTriangle(
		FVector::ZeroVector, FVector(2, 0, 0), FVector(0, 2, 0), FVector(1, -.1, .1), Point, Error));
	TestFalse(TEXT("非归一权重拒绝"), UFutsalPose17Library::InterpolateTriangle(
		FVector::ZeroVector, FVector(2, 0, 0), FVector(0, 2, 0), FVector(.5, .5, .5), Point, Error));
	TestFalse(TEXT("退化三角形拒绝"), UFutsalPose17Library::InterpolateTriangle(
		FVector::ZeroVector, FVector(1, 0, 0), FVector(2, 0, 0), FVector(.5, .25, .25), Point, Error));
	FFutsalPose17MeshIdentity Identity;
	TestFalse(TEXT("不自动猜测组件"), UFutsalPose17Library::DescribeVisualMesh(nullptr, Identity, Error));
	TArray<FVector> Positions;
	TArray<FIntVector> Triangles;
	TestFalse(TEXT("不猜测资产或临时spawn"), UFutsalPose17Library::ReadAssetReferenceGeometry(nullptr, Positions, Triangles, Identity, Error));
	FFutsalPose17CPUState CPUState;
	TestFalse(TEXT("不对空组件预备CPU"), UFutsalPose17Library::PrepareVisualCPUSampling(nullptr, CPUState, Error));
	TArray<USkeletalMeshComponent*> EmptyMeshes;
	TestFalse(TEXT("不把空采样集合当fence成功"), UFutsalPose17Library::SynchronizeVisualCPUCaches(EmptyMeshes, Error));
	TArray<FFutsalPose17SurfaceAnchor> EmptyAnchors;
	TestFalse(TEXT("角色切换前必须有真实资产锚点绑定"), UFutsalPose17Library::ValidatePose17AssetBinding(nullptr, Identity, EmptyAnchors, TEXT(""), Error));
	TestFalse(TEXT("角色切换拒绝空组件，不生成Editor替身"), UFutsalPose17Library::ValidateDiagnosticVisualOverride(nullptr, nullptr, Identity, Error));
	FFutsalPose17VisualMeshState Previous;
	FFutsalPose17VisualOverrideEvidence Evidence;
	TestFalse(TEXT("未应用的PIE角色事务不能伪恢复"), UFutsalPose17Library::RestoreDiagnosticVisualOverride(Previous, Evidence, Error));
	TestTrue(TEXT("恢复失败仍保留尝试证据"), Evidence.bRestoreAttempted);
	TestFalse(TEXT("未应用角色不能声称恢复成功"), Evidence.bRestoreSucceeded);
	FFutsalPose17GPULBSEligibility Eligibility;
	TestFalse(TEXT("GPU/LBS不猜测空实际mesh"), UFutsalPose17Library::ValidateGPUVisualLBS(nullptr, Error, &Eligibility));
	TestFalse(TEXT("空GPU/LBS不能冒充门禁已执行"), Eligibility.bChecksExecuted);
	TestFalse(TEXT("GPU/LBS空同步不算成功"), UFutsalPose17Library::SynchronizeGPUVisualLBS(EmptyMeshes, Error));
	FFutsalPose17Sample GpuSample;
	TestFalse(TEXT("GPU/LBS空组件不产生伪17点"), UFutsalPose17Library::SampleVisualPose17GPULBS(nullptr, Identity, EmptyAnchors, TEXT(""), GpuSample, Error));
	TestTrue(TEXT("失败GPU/LBS点集合为空"), GpuSample.WorldPointsM.IsEmpty());
	return true;
}
#endif
