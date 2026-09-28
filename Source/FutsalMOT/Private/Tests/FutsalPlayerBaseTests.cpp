#if WITH_DEV_AUTOMATION_TESTS

#include "FutsalPlayerBase.h"

#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerBaseHorizontalSpeedTest,
	"FutsalMOT.Character.HorizontalSpeedUsesXYAndMetersPerSecond",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerBaseHorizontalSpeedTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	TestEqual(
		TEXT("300 cm/s horizontal and arbitrary Z converts to 3 m/s"),
		AFutsalPlayerBase::HorizontalSpeedMpsFromVelocity(FVector(300.0, 0.0, 900.0)),
		3.0f);
	TestEqual(
		TEXT("Vertical velocity does not contribute to horizontal speed"),
		AFutsalPlayerBase::HorizontalSpeedMpsFromVelocity(FVector(0.0, 0.0, 600.0)),
		0.0f);
	TestEqual(
		TEXT("Velocity at the movement epsilon is treated as zero"),
		AFutsalPlayerBase::HorizontalSpeedMpsFromVelocity(
			FVector(AFutsalPlayerBase::CharacterMovementSpeedEpsilonCmPerSecond, 0.0, 0.0)),
		0.0f);
	TestEqual(
		TEXT("Diagonal XY velocity uses vector magnitude"),
		AFutsalPlayerBase::HorizontalSpeedMpsFromVelocity(FVector(300.0, 400.0, 50.0)),
		5.0f);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerBaseExternalMotionDefaultsTest,
	"FutsalMOT.Character.ExternalMotionDefaultsAreInactiveAndZero",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerBaseExternalMotionDefaultsTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	const AFutsalPlayerBase* Defaults = GetDefault<AFutsalPlayerBase>();
	TestFalse(TEXT("External motion is inactive by default"), Defaults->ExternalMotionActive);
	TestEqual(TEXT("External motion speed defaults to zero"), Defaults->ExternalMotionSpeedMps, 0.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FFutsalPlayerBaseEffectiveMotionSpeedSelectionTest,
	"FutsalMOT.Character.ExternalSpeedOverridesLegacySelectorOnlyWhenActive",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFutsalPlayerBaseEffectiveMotionSpeedSelectionTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	TestEqual(
		TEXT("Active external motion selects the Sequencer speed"),
		AFutsalPlayerBase::SelectEffectiveMotionSpeedMps(true, 1.75f, 2.5f),
		1.75f);
	TestEqual(
		TEXT("Inactive external motion preserves the legacy selector result"),
		AFutsalPlayerBase::SelectEffectiveMotionSpeedMps(false, 1.75f, 2.5f),
		2.5f);
	TestEqual(
		TEXT("Active external zero speed remains zero"),
		AFutsalPlayerBase::SelectEffectiveMotionSpeedMps(true, 0.0f, 2.5f),
		0.0f);

	return true;
}

#endif
