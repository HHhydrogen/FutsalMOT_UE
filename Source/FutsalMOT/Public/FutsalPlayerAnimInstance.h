#pragma once

#include "Animation/AnimInstance.h"
#include "CoreMinimal.h"
#include "FutsalPlayerAnimInstance.generated.h"

class AFutsalPlayerBase;
class ACharacter;
class FProperty;
class UCharacterMovementComponent;

struct FUTSALMOT_API FTransformDeltaResult
{
	FVector VelocityCmPerSecond = FVector::ZeroVector;
	float SpeedMps = 0.0f;
};

struct FUTSALMOT_API FNativeAnimMotionState
{
	FVector PreviousLocation = FVector::ZeroVector;
	FVector AutoMotionVelocity = FVector::ZeroVector;
	double AutoMotionSpeedMps = 0.0;
	double MotionSpeedMps = 0.0;
	bool bSpeedInitialized = false;
	bool bUseAutoMotionSpeed = true;
	bool bExternalMotionActive = false;
	double ExternalMotionSpeedMps = 0.0;
	FVector MovementVelocity = FVector::ZeroVector;
	double EffectiveMotionSpeedMps = 0.0;
	FVector EffectiveVelocity = FVector::ZeroVector;
	FVector Velocity = FVector::ZeroVector;
};

enum class ENativeAnimBridgeValueType : uint8
{
	Vector,
	Boolean,
	Number
};

UCLASS(Blueprintable)
class FUTSALMOT_API UFutsalPlayerAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	static constexpr float DeltaTimeEpsilonSeconds = 0.0001f;
	static constexpr float GroundSpeedThresholdCmPerSecond = 0.01f;
	static constexpr float AutoFacingSpeedThresholdMps = 0.3f;

	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	static FTransformDeltaResult ComputeAutoMotion(
		const FVector& CurrentLocation,
		const FVector& PreviousLocation,
		float DeltaSeconds);
	static void UpdateAutoMotionState(FNativeAnimMotionState& State, const FVector& CurrentLocation, float DeltaSeconds);
	static void UpdateMotionOutputs(FNativeAnimMotionState& State);
	static TArray<FName> GetBlueprintBridgePropertyNames();
	static FProperty* FindBlueprintBridgeProperty(const UClass* GeneratedClass, FName ExactPropertyName);
	static bool IsBlueprintBridgePropertyTypeCompatible(const FProperty* Property, ENativeAnimBridgeValueType ValueType);
	static bool WriteBlueprintBridgeValue(UObject* Object, FName ExactPropertyName, const FVector& Value);
	static bool WriteBlueprintBridgeValue(UObject* Object, FName ExactPropertyName, double Value);
	static bool WriteBlueprintBridgeValue(UObject* Object, FName ExactPropertyName, bool Value);
	static float SelectLegacySpeedMps(bool bUseAutoMotionSpeed, float AutoMotionSpeedMps, float MotionSpeedMps);
	static float SelectExternalSpeedMps(bool bExternalMotionActive, float ExternalMotionSpeedMps, float LegacySpeedMps);
	static float GroundSpeedCmPerSecond(float EffectiveMotionSpeedMps);
	static float CalculateDirectionFromVelocity(const FVector& EffectiveVelocity, const FRotator& ActorRotation);
	static float SelectDirection(float RawDirection, bool bHasValidDirection, bool bOrientRotationToMovement);
	static bool SelectIsFalling(bool bHasMovementComponent, bool bMovementComponentIsFalling);
	static bool ComputeShouldMove(float GroundSpeedCmPerSecond, const FVector& Acceleration);

protected:
	void PublishBlueprintProperties();

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	TObjectPtr<ACharacter> NativeCharacter = nullptr;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	TObjectPtr<UCharacterMovementComponent> NativeMovementComponent = nullptr;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	TObjectPtr<AFutsalPlayerBase> NativeFutsalPlayer = nullptr;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	FVector NativeVelocity = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	double NativeGroundSpeed = 0.0;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	double NativeDirection = 0.0;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	bool bNativeShouldMove = false;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	bool bNativeIsFalling = false;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	double NativeMotionSpeedMps = 0.0;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	FVector NativePreviousLocation = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	double NativeAutoMotionSpeedMps = 0.0;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	bool bNativeSpeedInitialized = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Animation|Native Motion")
	bool bNativeUseAutoMotionSpeed = true;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	double NativeEffectiveMotionSpeedMps = 0.0;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	FVector NativeAutoMotionVelocity = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	FVector NativeEffectiveVelocity = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category="Animation|Native Motion")
	double NativeAutoFacingYawDeg = 0.0;

};
