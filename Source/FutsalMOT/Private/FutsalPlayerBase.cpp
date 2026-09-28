#include "FutsalPlayerBase.h"

#include "GameFramework/CharacterMovementComponent.h"

float AFutsalPlayerBase::GetCharacterMovementHorizontalSpeedMps() const
{
	const UCharacterMovementComponent* Movement = GetCharacterMovement();
	return Movement
		? HorizontalSpeedMpsFromVelocity(Movement->Velocity)
		: 0.0f;
}

float AFutsalPlayerBase::HorizontalSpeedMpsFromVelocity(
	const FVector& VelocityCmPerSecond)
{
	const FVector HorizontalVelocity(VelocityCmPerSecond.X, VelocityCmPerSecond.Y, 0.0f);
	const float HorizontalSpeedCmPerSecond = HorizontalVelocity.Size();
	if (!FMath::IsFinite(HorizontalSpeedCmPerSecond)
		|| HorizontalSpeedCmPerSecond <= CharacterMovementSpeedEpsilonCmPerSecond)
	{
		return 0.0f;
	}

	return HorizontalSpeedCmPerSecond * 0.01f;
}

float AFutsalPlayerBase::SelectEffectiveMotionSpeedMps(
	bool bIsExternalMotionActive,
	float ExternalSpeedMps,
	float LegacySelectorSpeedMps)
{
	return bIsExternalMotionActive ? ExternalSpeedMps : LegacySelectorSpeedMps;
}
