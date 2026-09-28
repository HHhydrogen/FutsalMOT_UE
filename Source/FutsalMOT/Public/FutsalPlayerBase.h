#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "FutsalPlayerBase.generated.h"

UCLASS(Blueprintable)
class FUTSALMOT_API AFutsalPlayerBase : public ACharacter
{
	GENERATED_BODY()

public:
	static constexpr float CharacterMovementSpeedEpsilonCmPerSecond = 0.01f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Animation|External Motion")
	bool ExternalMotionActive = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Animation|External Motion", meta=(ClampMin="0.0"))
	float ExternalMotionSpeedMps = 0.0f;

	UFUNCTION(BlueprintPure, Category="Animation|Motion")
	float GetCharacterMovementHorizontalSpeedMps() const;

	static float HorizontalSpeedMpsFromVelocity(const FVector& VelocityCmPerSecond);
	static float SelectEffectiveMotionSpeedMps(
		bool bIsExternalMotionActive,
		float ExternalSpeedMps,
		float LegacySelectorSpeedMps);
};
