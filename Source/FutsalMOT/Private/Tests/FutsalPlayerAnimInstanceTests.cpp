#if WITH_DEV_AUTOMATION_TESTS

#include "FutsalPlayerAnimInstance.h"

#include "Misc/AutomationTest.h"
#include "UObject/UnrealType.h"
#include "Components/SkeletalMeshComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstanceAutoMotionTest,
"FutsalMOT.AnimInstance.AutoMotionPreservesFullDeltaAndMetersPerSecond",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstanceAutoMotionTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	const FTransformDeltaResult Result = UFutsalPlayerAnimInstance::ComputeAutoMotion(
		FVector(300.0, 400.0, 900.0),
		FVector::ZeroVector,
		1.0f);

	TestEqual(TEXT("Auto motion preserves full velocity including Z"), Result.VelocityCmPerSecond, FVector(300.0, 400.0, 900.0));
	TestEqual(TEXT("Auto motion converts horizontal speed to m/s"), Result.SpeedMps, 5.0f);
	TestTrue(TEXT("Vertical velocity remains available to Jump input"), Result.VelocityCmPerSecond.Z > 100.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstanceDeltaTimeBoundaryTest,
	"FutsalMOT.AnimInstance.AutoMotionIgnoresSmallDeltaTime",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstanceDeltaTimeBoundaryTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	const FTransformDeltaResult Result = UFutsalPlayerAnimInstance::ComputeAutoMotion(
		FVector(100.0, 0.0, 0.0),
		FVector::ZeroVector,
		0.0001f);

	TestEqual(TEXT("Small delta time produces no auto velocity"), Result.VelocityCmPerSecond, FVector::ZeroVector);
	TestEqual(TEXT("Small delta time produces no auto speed"), Result.SpeedMps, 0.0f);
	const float NonFiniteDelta = std::numeric_limits<float>::quiet_NaN();
	const FTransformDeltaResult NonFiniteResult = UFutsalPlayerAnimInstance::ComputeAutoMotion(
		FVector(100.0, 0.0, 0.0), FVector::ZeroVector, NonFiniteDelta);
	TestEqual(TEXT("Non-finite delta time produces no auto velocity"), NonFiniteResult.VelocityCmPerSecond, FVector::ZeroVector);
	TestEqual(TEXT("Non-finite delta time produces no auto speed"), NonFiniteResult.SpeedMps, 0.0f);

	FNativeAnimMotionState State;
	State.bSpeedInitialized = true;
	State.PreviousLocation = FVector::ZeroVector;
	UFutsalPlayerAnimInstance::UpdateAutoMotionState(State, FVector(300.0, 400.0, 900.0), 1.0f);
	TestEqual(TEXT("Above-epsilon update stores full delta velocity"), State.AutoMotionVelocity, FVector(300.0, 400.0, 900.0));
	TestEqual(TEXT("Above-epsilon update stores XY speed"), State.AutoMotionSpeedMps, 5.0);
	TestEqual(TEXT("Above-epsilon update advances previous location"), State.PreviousLocation, FVector(300.0, 400.0, 900.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstanceSpeedSourceTest,
	"FutsalMOT.AnimInstance.ExternalSpeedOverridesLegacySelector",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstanceSpeedSourceTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	TestEqual(
		TEXT("Auto motion is selected when enabled"),
		UFutsalPlayerAnimInstance::SelectLegacySpeedMps(true, 2.5f, 0.0f),
		2.5f);
	TestEqual(
		TEXT("Motion speed fallback is selected when auto motion is disabled"),
		UFutsalPlayerAnimInstance::SelectLegacySpeedMps(false, 2.5f, 1.25f),
		1.25f);
	TestEqual(
		TEXT("External speed overrides the legacy result when active"),
		UFutsalPlayerAnimInstance::SelectExternalSpeedMps(true, 3.0f, 1.25f),
		3.0f);
	TestEqual(
		TEXT("Legacy result passes through when external motion is inactive"),
		UFutsalPlayerAnimInstance::SelectExternalSpeedMps(false, 3.0f, 1.25f),
		1.25f);
	TestEqual(
		TEXT("Active external motion with zero speed overrides legacy speed with zero"),
		UFutsalPlayerAnimInstance::SelectExternalSpeedMps(true, 0.0f, 1.25f),
		0.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstancePresentationMathTest,
	"FutsalMOT.AnimInstance.PresentationMathPreservesDirectionAndGroundSpeed",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstancePresentationMathTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	TestEqual(
		TEXT("GroundSpeed converts m/s to cm/s"),
		UFutsalPlayerAnimInstance::GroundSpeedCmPerSecond(1.75f),
		175.0f);
	TestEqual(
		TEXT("Unoriented direction preserves raw direction"),
		UFutsalPlayerAnimInstance::SelectDirection(90.0f, true, false),
		90.0f);
	TestEqual(
		TEXT("Oriented direction clamps to the historical range"),
		UFutsalPlayerAnimInstance::SelectDirection(90.0f, true, true),
		45.0f);
	const FRotator ActorRotation(0.0, 30.0, 0.0);
	const FVector EffectiveVelocity = ActorRotation.RotateVector(FVector(100.0, 0.0, 0.0));
	const float RawCalculatedDirection = UFutsalPlayerAnimInstance::CalculateDirectionFromVelocity(EffectiveVelocity, ActorRotation);
	TestEqual(TEXT("Direction calculation uses EffectiveVelocity relative to Actor rotation"), RawCalculatedDirection, 0.0f);
	TestEqual(
		TEXT("Calculated direction is then clamped when OrientRotationToMovement is enabled"),
		UFutsalPlayerAnimInstance::SelectDirection(80.0f, true, true),
		45.0f);
	TestFalse(TEXT("IsFalling is false without a MovementComponent"), UFutsalPlayerAnimInstance::SelectIsFalling(false, true));
	TestTrue(TEXT("IsFalling follows MovementComponent when present"), UFutsalPlayerAnimInstance::SelectIsFalling(true, true));
	TestFalse(TEXT("Grounded MovementComponent reports not falling"), UFutsalPlayerAnimInstance::SelectIsFalling(true, false));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstanceShouldMoveTest,
	"FutsalMOT.AnimInstance.ShouldMovePreservesAccelerationExpression",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstanceShouldMoveTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	TestFalse(
		TEXT("GroundSpeed at threshold does not move"),
		UFutsalPlayerAnimInstance::ComputeShouldMove(0.01f, FVector(100.0, 0.0, 0.0)));
	TestTrue(
		TEXT("Nonzero acceleration and moving ground speed moves"),
		UFutsalPlayerAnimInstance::ComputeShouldMove(1.0f, FVector(100.0, 0.0, 0.0)));
	TestTrue(
		TEXT("Zero acceleration retains the transcribed OR expression"),
		UFutsalPlayerAnimInstance::ComputeShouldMove(1.0f, FVector::ZeroVector));
	TestTrue(
		TEXT("Z-only acceleration takes the nonzero-vector OR branch"),
		UFutsalPlayerAnimInstance::ComputeShouldMove(1.0f, FVector(0.0, 0.0, 1.0)));
	TestTrue(
		TEXT("Near-zero but nonzero Z acceleration follows exact Vector != Zero semantics"),
		UFutsalPlayerAnimInstance::ComputeShouldMove(1.0f, FVector(0.0, 0.0, SMALL_NUMBER * 0.5)));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstanceBridgeNamesTest,
	"FutsalMOT.AnimInstance.BridgeUsesExactBlueprintNames",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstanceBridgeNamesTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	const TArray<FName> Names = UFutsalPlayerAnimInstance::GetBlueprintBridgePropertyNames();
	TestEqual(TEXT("Only confirmed BP-owned properties are bridged"), Names.Num(), 14);
	TestTrue(TEXT("Spaced Previous Location name is preserved"), Names.Contains(FName(TEXT("Previous Location"))));
	TestTrue(TEXT("Spaced Auto Motion Velocity name is preserved"), Names.Contains(FName(TEXT("Auto Motion Velocity"))));
	TestTrue(TEXT("Unspaced GroundSpeed name is preserved"), Names.Contains(FName(TEXT("GroundSpeed"))));
	TestFalse(TEXT("Native identifier is never used as a reflected alias"), Names.Contains(FName(TEXT("PreviousLocation"))));
	TestNull(TEXT("Unlisted native spelling is rejected before reflection lookup"),
		UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(UFutsalPlayerAnimInstance::StaticClass(), FName(TEXT("PreviousLocation"))));
	TestNull(TEXT("Missing exact BP property is safely skipped"),
		UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(UFutsalPlayerAnimInstance::StaticClass(), FName(TEXT("Previous Location"))));
	TestNull(TEXT("BP-owned Velocity remains absent from the native property set"),
		UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(UFutsalPlayerAnimInstance::StaticClass(), FName(TEXT("Velocity"))));
	TestNull(TEXT("Native class has no colliding PreviousLocation property"),
		UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(UFutsalPlayerAnimInstance::StaticClass(), FName(TEXT("PreviousLocation"))));
	FProperty* GroundSpeedProperty = UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(
		UFutsalPlayerAnimInstance::StaticClass(), FName(TEXT("GroundSpeed")));
	TestFalse(TEXT("Vector bridge rejects a numeric reflected property type"),
		UFutsalPlayerAnimInstance::IsBlueprintBridgePropertyTypeCompatible(GroundSpeedProperty, ENativeAnimBridgeValueType::Vector));
	TestFalse(TEXT("Number bridge safely rejects a missing property"),
		UFutsalPlayerAnimInstance::IsBlueprintBridgePropertyTypeCompatible(nullptr, ENativeAnimBridgeValueType::Number));
	const UClass* BlueprintClass = LoadClass<UObject>(nullptr,
		TEXT("/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.ABP_FutsalPlayerBase_C"));
	TestNotNull(TEXT("Canonical ABP generated class is available for transient bridge fixture"), BlueprintClass);
	if (BlueprintClass)
	{
		USkeletalMeshComponent* FixtureOuter = NewObject<USkeletalMeshComponent>(GetTransientPackage());
		UObject* TransientInstance = NewObject<UObject>(FixtureOuter, BlueprintClass);
		const FVector ExpectedVelocity(7.0, 8.0, 150.0);
		TestTrue(TEXT("Bridge writes FVector through exact BP-owned Velocity property"),
			UFutsalPlayerAnimInstance::WriteBlueprintBridgeValue(TransientInstance, FName(TEXT("Velocity")), ExpectedVelocity));
		FProperty* VelocityProperty = UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(BlueprintClass, FName(TEXT("Velocity")));
		TestNotNull(TEXT("Exact BP Velocity FName resolves on generated class"), VelocityProperty);
		if (FStructProperty* VelocityStruct = CastField<FStructProperty>(VelocityProperty))
		{
			const FVector* ActualVelocity = VelocityStruct->ContainerPtrToValuePtr<FVector>(TransientInstance);
			TestEqual(TEXT("Transient generated-class FVector property received value"), *ActualVelocity, ExpectedVelocity);
		}
		FProperty* PreviousLocationProperty = UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(BlueprintClass, FName(TEXT("Previous Location")));
		const FVector PreviousLocationBefore = PreviousLocationProperty
			? *PreviousLocationProperty->ContainerPtrToValuePtr<FVector>(TransientInstance)
			: FVector::ZeroVector;
		TestFalse(TEXT("Bridge rejects the no-space PreviousLocation alias"),
			UFutsalPlayerAnimInstance::WriteBlueprintBridgeValue(TransientInstance, FName(TEXT("PreviousLocation")), FVector(3.0, 4.0, 5.0)));
		if (PreviousLocationProperty)
		{
			TestEqual(TEXT("Rejected alias leaves exact spaced property unchanged"),
				*PreviousLocationProperty->ContainerPtrToValuePtr<FVector>(TransientInstance), PreviousLocationBefore);
		}
		FProperty* GroundSpeedGeneratedProperty = UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(BlueprintClass, FName(TEXT("GroundSpeed")));
		FNumericProperty* GroundSpeedNumericProperty = CastField<FNumericProperty>(GroundSpeedGeneratedProperty);
		const double GroundSpeedBefore = GroundSpeedNumericProperty
			? GroundSpeedNumericProperty->GetFloatingPointPropertyValue(GroundSpeedNumericProperty->ContainerPtrToValuePtr<void>(TransientInstance))
			: 0.0;
		const FVector BeforeMismatch(2.0, 3.0, 4.0);
		TestFalse(TEXT("FVector write rejects BP numeric GroundSpeed"),
			UFutsalPlayerAnimInstance::WriteBlueprintBridgeValue(TransientInstance, FName(TEXT("GroundSpeed")), BeforeMismatch));
		if (GroundSpeedNumericProperty && UFutsalPlayerAnimInstance::IsBlueprintBridgePropertyTypeCompatible(GroundSpeedGeneratedProperty, ENativeAnimBridgeValueType::Number))
		{
			TestEqual(TEXT("Type mismatch leaves generated-class GroundSpeed unchanged"),
				GroundSpeedNumericProperty->GetFloatingPointPropertyValue(GroundSpeedNumericProperty->ContainerPtrToValuePtr<void>(TransientInstance)), GroundSpeedBefore);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstanceExternalSpeedVectorIndependenceTest,
	"FutsalMOT.AnimInstance.ExternalSpeedDoesNotReplaceVelocity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstanceExternalSpeedVectorIndependenceTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	const FVector AutoVelocity(10.0, 20.0, 150.0);
	FNativeAnimMotionState State;
	State.bUseAutoMotionSpeed = true;
	State.MotionSpeedMps = 2.5;
	State.bExternalMotionActive = true;
	State.ExternalMotionSpeedMps = 4.0;
	State.AutoMotionVelocity = AutoVelocity;
	State.MovementVelocity = FVector(1.0, 2.0, 3.0);
	UFutsalPlayerAnimInstance::UpdateMotionOutputs(State);
	TestEqual(TEXT("External scalar overrides legacy speed"), State.EffectiveMotionSpeedMps, 4.0);
	TestEqual(TEXT("Velocity remains the independently selected auto vector"), State.EffectiveVelocity, AutoVelocity);
	TestEqual(TEXT("Native Velocity output follows effective vector"), State.Velocity, AutoVelocity);
	TestEqual(TEXT("Nonzero MotionSpeed fallback remains available"), UFutsalPlayerAnimInstance::SelectLegacySpeedMps(false, 0.0f, static_cast<float>(State.MotionSpeedMps)), 2.5f);
	TestTrue(TEXT("Independent vector keeps the Jump Z threshold"), State.Velocity.Z > 100.0);
	FNativeAnimMotionState FallbackState;
	FallbackState.bUseAutoMotionSpeed = false;
	FallbackState.MotionSpeedMps = 2.5;
	FallbackState.MovementVelocity = FVector(6.0, 7.0, 8.0);
	UFutsalPlayerAnimInstance::UpdateMotionOutputs(FallbackState);
	TestEqual(TEXT("Update output preserves nonzero legacy fallback speed"), FallbackState.EffectiveMotionSpeedMps, 2.5);
	TestEqual(TEXT("Fallback path independently retains MovementComponent velocity"), FallbackState.Velocity, FVector(6.0, 7.0, 8.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerAnimInstanceFirstUpdateTest,
	"FutsalMOT.AnimInstance.FirstUpdateInitializesWithoutOverwritingLegacySpeed",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerAnimInstanceFirstUpdateTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	FNativeAnimMotionState State;
	State.MotionSpeedMps = 2.25;
	State.AutoMotionSpeedMps = 7.5;
	UFutsalPlayerAnimInstance::UpdateAutoMotionState(State, FVector(12.0, 34.0, 56.0), 1.0f);
	TestTrue(TEXT("First update marks motion state initialized"), State.bSpeedInitialized);
	TestEqual(TEXT("First update records current location"), State.PreviousLocation, FVector(12.0, 34.0, 56.0));
	TestEqual(TEXT("First update publishes zero auto velocity"), State.AutoMotionVelocity, FVector::ZeroVector);
	TestEqual(TEXT("First update leaves AutoMotionSpeed untouched"), State.AutoMotionSpeedMps, 7.5);
	TestEqual(TEXT("Legacy motion speed is preserved"), State.MotionSpeedMps, 2.25);
	return true;
}

#endif
