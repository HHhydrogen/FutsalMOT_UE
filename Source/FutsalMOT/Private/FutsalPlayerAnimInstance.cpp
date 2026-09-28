#include "FutsalPlayerAnimInstance.h"

#include "FutsalPlayerBase.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "KismetAnimationLibrary.h"
#include "UObject/UnrealType.h"

namespace
{
	bool SetReflectedValue(UObject* Object, const FName PropertyName, const void* Value, const TCHAR* ExpectedType)
	{
		if (!Object)
		{
			return false;
		}

		FProperty* Property = Object->GetClass()->FindPropertyByName(PropertyName);
		if (!Property)
		{
			UE_LOG(LogTemp, Warning, TEXT("AnimInstance bridge property '%s' was not found on %s; skipping."), *PropertyName.ToString(), *Object->GetClass()->GetName());
			return false;
		}

		const ENativeAnimBridgeValueType ValueType = FCString::Strcmp(ExpectedType, TEXT("Vector")) == 0
			? ENativeAnimBridgeValueType::Vector
			: FCString::Strcmp(ExpectedType, TEXT("Bool")) == 0
				? ENativeAnimBridgeValueType::Boolean
				: ENativeAnimBridgeValueType::Number;
		const bool bTypeMatches = UFutsalPlayerAnimInstance::IsBlueprintBridgePropertyTypeCompatible(Property, ValueType);

		if (!bTypeMatches)
		{
			UE_LOG(LogTemp, Warning, TEXT("AnimInstance bridge property '%s' has an incompatible type; skipping."), *PropertyName.ToString());
			return false;
		}

		if (FStructProperty* VectorProperty = CastField<FStructProperty>(Property))
		{
			VectorProperty->CopyCompleteValue(VectorProperty->ContainerPtrToValuePtr<void>(Object), Value);
		}
		else if (FBoolProperty* BoolProperty = CastField<FBoolProperty>(Property))
		{
			BoolProperty->SetPropertyValue_InContainer(Object, *static_cast<const bool*>(Value));
		}
		else if (FFloatProperty* FloatProperty = CastField<FFloatProperty>(Property))
		{
			FloatProperty->SetPropertyValue_InContainer(Object, static_cast<float>(*static_cast<const double*>(Value)));
		}
		else if (FDoubleProperty* DoubleProperty = CastField<FDoubleProperty>(Property))
		{
			DoubleProperty->SetPropertyValue_InContainer(Object, *static_cast<const double*>(Value));
		}
		return true;
	}

}

void UFutsalPlayerAnimInstance::PublishBlueprintProperties()
{
	WriteBlueprintBridgeValue(this, TEXT("Velocity"), NativeVelocity);
	WriteBlueprintBridgeValue(this, TEXT("GroundSpeed"), NativeGroundSpeed);
	WriteBlueprintBridgeValue(this, TEXT("Direction"), NativeDirection);
	WriteBlueprintBridgeValue(this, TEXT("ShouldMove"), bNativeShouldMove);
	WriteBlueprintBridgeValue(this, TEXT("IsFalling"), bNativeIsFalling);
	WriteBlueprintBridgeValue(this, TEXT("MotionSpeedMps"), NativeMotionSpeedMps);
	WriteBlueprintBridgeValue(this, TEXT("Previous Location"), NativePreviousLocation);
	WriteBlueprintBridgeValue(this, TEXT("Auto Motion Speed Mps"), NativeAutoMotionSpeedMps);
	WriteBlueprintBridgeValue(this, TEXT("Speed Initialized"), bNativeSpeedInitialized);
	WriteBlueprintBridgeValue(this, TEXT("Use Auto Motion Speed"), bNativeUseAutoMotionSpeed);
	WriteBlueprintBridgeValue(this, TEXT("Effective Motion Speed Mps"), NativeEffectiveMotionSpeedMps);
	WriteBlueprintBridgeValue(this, TEXT("Auto Motion Velocity"), NativeAutoMotionVelocity);
	WriteBlueprintBridgeValue(this, TEXT("Effective Velocity"), NativeEffectiveVelocity);
	WriteBlueprintBridgeValue(this, TEXT("Auto Facing Yaw Deg"), NativeAutoFacingYawDeg);
}

FTransformDeltaResult UFutsalPlayerAnimInstance::ComputeAutoMotion(
	const FVector& CurrentLocation,
	const FVector& PreviousLocation,
	float DeltaSeconds)
{
	FTransformDeltaResult Result;
	if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= DeltaTimeEpsilonSeconds)
	{
		return Result;
	}

	Result.VelocityCmPerSecond = (CurrentLocation - PreviousLocation) / DeltaSeconds;
	Result.SpeedMps = Result.VelocityCmPerSecond.Size2D() * 0.01f;
	return Result;
}

void UFutsalPlayerAnimInstance::UpdateAutoMotionState(
	FNativeAnimMotionState& State,
	const FVector& CurrentLocation,
	float DeltaSeconds)
{
	if (!State.bSpeedInitialized)
	{
		State.PreviousLocation = CurrentLocation;
		State.AutoMotionVelocity = FVector::ZeroVector;
		State.bSpeedInitialized = true;
		return;
	}

	if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= DeltaTimeEpsilonSeconds)
	{
		return;
	}

	const FTransformDeltaResult AutoMotion = ComputeAutoMotion(CurrentLocation, State.PreviousLocation, DeltaSeconds);
	State.AutoMotionVelocity = AutoMotion.VelocityCmPerSecond;
	State.AutoMotionSpeedMps = AutoMotion.SpeedMps;
	State.PreviousLocation = CurrentLocation;
}

void UFutsalPlayerAnimInstance::UpdateMotionOutputs(FNativeAnimMotionState& State)
{
	const float LegacySpeed = SelectLegacySpeedMps(
		State.bUseAutoMotionSpeed,
		static_cast<float>(State.AutoMotionSpeedMps),
		static_cast<float>(State.MotionSpeedMps));
	State.EffectiveMotionSpeedMps = SelectExternalSpeedMps(
		State.bExternalMotionActive,
		static_cast<float>(State.ExternalMotionSpeedMps),
		LegacySpeed);
	State.EffectiveVelocity = State.bUseAutoMotionSpeed ? State.AutoMotionVelocity : State.MovementVelocity;
	State.Velocity = State.EffectiveVelocity;
}

TArray<FName> UFutsalPlayerAnimInstance::GetBlueprintBridgePropertyNames()
{
	return {
		TEXT("Velocity"), TEXT("GroundSpeed"), TEXT("Direction"), TEXT("ShouldMove"), TEXT("IsFalling"),
		TEXT("MotionSpeedMps"), TEXT("Previous Location"), TEXT("Auto Motion Speed Mps"), TEXT("Speed Initialized"),
		TEXT("Use Auto Motion Speed"), TEXT("Effective Motion Speed Mps"), TEXT("Auto Motion Velocity"),
		TEXT("Effective Velocity"), TEXT("Auto Facing Yaw Deg")
	};
}

FProperty* UFutsalPlayerAnimInstance::FindBlueprintBridgeProperty(const UClass* GeneratedClass, FName ExactPropertyName)
{
	if (!GeneratedClass || !GetBlueprintBridgePropertyNames().Contains(ExactPropertyName))
	{
		return nullptr;
	}
	return GeneratedClass->FindPropertyByName(ExactPropertyName);
}

bool UFutsalPlayerAnimInstance::IsBlueprintBridgePropertyTypeCompatible(
	const FProperty* Property,
	ENativeAnimBridgeValueType ValueType)
{
	if (ValueType == ENativeAnimBridgeValueType::Vector)
	{
		const FStructProperty* StructProperty = CastField<FStructProperty>(Property);
		return StructProperty && StructProperty->Struct == TBaseStructure<FVector>::Get();
	}
	if (ValueType == ENativeAnimBridgeValueType::Boolean)
	{
		return CastField<FBoolProperty>(Property) != nullptr;
	}
	return CastField<FFloatProperty>(Property) || CastField<FDoubleProperty>(Property);
}

bool UFutsalPlayerAnimInstance::WriteBlueprintBridgeValue(UObject* Object, FName ExactPropertyName, const FVector& Value)
{
	return GetBlueprintBridgePropertyNames().Contains(ExactPropertyName)
		&& SetReflectedValue(Object, ExactPropertyName, &Value, TEXT("Vector"));
}

bool UFutsalPlayerAnimInstance::WriteBlueprintBridgeValue(UObject* Object, FName ExactPropertyName, double Value)
{
	return GetBlueprintBridgePropertyNames().Contains(ExactPropertyName)
		&& SetReflectedValue(Object, ExactPropertyName, &Value, TEXT("Float"));
}

bool UFutsalPlayerAnimInstance::WriteBlueprintBridgeValue(UObject* Object, FName ExactPropertyName, bool Value)
{
	return GetBlueprintBridgePropertyNames().Contains(ExactPropertyName)
		&& SetReflectedValue(Object, ExactPropertyName, &Value, TEXT("Bool"));
}

float UFutsalPlayerAnimInstance::SelectLegacySpeedMps(bool bUseAutoMotionSpeed, float InAutoMotionSpeedMps, float InMotionSpeedMps)
{
	return bUseAutoMotionSpeed ? InAutoMotionSpeedMps : InMotionSpeedMps;
}

float UFutsalPlayerAnimInstance::SelectExternalSpeedMps(bool bExternalMotionActive, float InExternalMotionSpeedMps, float InLegacySpeedMps)
{
	return bExternalMotionActive ? InExternalMotionSpeedMps : InLegacySpeedMps;
}

float UFutsalPlayerAnimInstance::GroundSpeedCmPerSecond(float InEffectiveMotionSpeedMps)
{
	return InEffectiveMotionSpeedMps * 100.0f;
}

float UFutsalPlayerAnimInstance::CalculateDirectionFromVelocity(const FVector& EffectiveVelocity, const FRotator& ActorRotation)
{
	return UKismetAnimationLibrary::CalculateDirection(EffectiveVelocity, ActorRotation);
}

float UFutsalPlayerAnimInstance::SelectDirection(float RawDirection, bool bHasValidDirection, bool bOrientRotationToMovement)
{
	if (!bHasValidDirection)
	{
		return 0.0f;
	}
	return bOrientRotationToMovement ? FMath::Clamp(RawDirection, -45.0f, 45.0f) : RawDirection;
}

bool UFutsalPlayerAnimInstance::SelectIsFalling(bool bHasMovementComponent, bool bMovementComponentIsFalling)
{
	return bHasMovementComponent && bMovementComponentIsFalling;
}

bool UFutsalPlayerAnimInstance::ComputeShouldMove(float InGroundSpeedCmPerSecond, const FVector& Acceleration)
{
	return InGroundSpeedCmPerSecond > GroundSpeedThresholdCmPerSecond
		&& ((Acceleration != FVector::ZeroVector) || !(Acceleration.Size2D() > GroundSpeedThresholdCmPerSecond));
}

void UFutsalPlayerAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();

	NativeCharacter = Cast<ACharacter>(TryGetPawnOwner());
	NativeMovementComponent = NativeCharacter ? NativeCharacter->GetCharacterMovement() : nullptr;
	NativeFutsalPlayer = Cast<AFutsalPlayerBase>(NativeCharacter);
	NativePreviousLocation = NativeCharacter ? NativeCharacter->GetActorLocation() : FVector::ZeroVector;
	NativeAutoMotionVelocity = FVector::ZeroVector;
	bNativeSpeedInitialized = false;
	PublishBlueprintProperties();
}

void UFutsalPlayerAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);

	if (!NativeCharacter)
	{
		NativeCharacter = Cast<ACharacter>(TryGetPawnOwner());
	}
	if (!NativeMovementComponent && NativeCharacter)
	{
		NativeMovementComponent = NativeCharacter->GetCharacterMovement();
	}
	if (!NativeFutsalPlayer && NativeCharacter)
	{
		NativeFutsalPlayer = Cast<AFutsalPlayerBase>(NativeCharacter);
	}

	FNativeAnimMotionState MotionState;
	MotionState.PreviousLocation = NativePreviousLocation;
	MotionState.AutoMotionVelocity = NativeAutoMotionVelocity;
	MotionState.AutoMotionSpeedMps = NativeAutoMotionSpeedMps;
	MotionState.MotionSpeedMps = NativeMotionSpeedMps;
	MotionState.bSpeedInitialized = bNativeSpeedInitialized;
	MotionState.bUseAutoMotionSpeed = bNativeUseAutoMotionSpeed;
	MotionState.bExternalMotionActive = NativeFutsalPlayer && NativeFutsalPlayer->ExternalMotionActive;
	MotionState.ExternalMotionSpeedMps = NativeFutsalPlayer ? NativeFutsalPlayer->ExternalMotionSpeedMps : 0.0;
	MotionState.MovementVelocity = NativeMovementComponent ? NativeMovementComponent->Velocity : FVector::ZeroVector;
	UpdateAutoMotionState(MotionState, NativeCharacter ? NativeCharacter->GetActorLocation() : NativePreviousLocation, DeltaSeconds);
	NativePreviousLocation = MotionState.PreviousLocation;
	NativeAutoMotionVelocity = MotionState.AutoMotionVelocity;
	NativeAutoMotionSpeedMps = MotionState.AutoMotionSpeedMps;
	bNativeSpeedInitialized = MotionState.bSpeedInitialized;
	MotionState.AutoMotionSpeedMps = NativeAutoMotionSpeedMps;
	MotionState.AutoMotionVelocity = NativeAutoMotionVelocity;
	MotionState.MotionSpeedMps = NativeMotionSpeedMps;

	UpdateMotionOutputs(MotionState);
	NativeEffectiveMotionSpeedMps = MotionState.EffectiveMotionSpeedMps;
	NativeEffectiveVelocity = MotionState.EffectiveVelocity;
	NativeVelocity = MotionState.Velocity;
	NativeGroundSpeed = GroundSpeedCmPerSecond(static_cast<float>(NativeEffectiveMotionSpeedMps));

	const FRotator ActorRotation = NativeCharacter ? NativeCharacter->GetActorRotation() : FRotator::ZeroRotator;
	const float RawDirection = CalculateDirectionFromVelocity(NativeEffectiveVelocity, ActorRotation);
	const bool bOrientRotationToMovement = NativeMovementComponent && NativeMovementComponent->bOrientRotationToMovement;
	NativeDirection = SelectDirection(RawDirection, NativeEffectiveVelocity.SizeSquared2D() > SMALL_NUMBER, bOrientRotationToMovement);

	const FVector Acceleration = NativeMovementComponent ? NativeMovementComponent->GetCurrentAcceleration() : FVector::ZeroVector;
	bNativeShouldMove = ComputeShouldMove(static_cast<float>(NativeGroundSpeed), Acceleration);
	bNativeIsFalling = SelectIsFalling(NativeMovementComponent != nullptr,
		NativeMovementComponent && NativeMovementComponent->IsFalling());

	if (NativeEffectiveMotionSpeedMps > AutoFacingSpeedThresholdMps && !NativeEffectiveVelocity.IsNearlyZero())
	{
		NativeAutoFacingYawDeg = NativeEffectiveVelocity.ToOrientationRotator().Yaw;
	}

	PublishBlueprintProperties();
}
