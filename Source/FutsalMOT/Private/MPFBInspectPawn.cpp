#include "MPFBInspectPawn.h"

#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

AMPFBInspectPawn::AMPFBInspectPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	AutoPossessPlayer = EAutoReceiveInput::Disabled;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	RootComponent = SceneRoot;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(SceneRoot);
	Camera->bUsePawnControlRotation = true;

	FloatingMovement = CreateDefaultSubobject<UFloatingPawnMovement>(TEXT("FloatingPawnMovement"));
	FloatingMovement->UpdatedComponent = RootComponent;
	FloatingMovement->MaxSpeed = NormalSpeed;
	FloatingMovement->Acceleration = 4000.0f;
	FloatingMovement->Deceleration = 4000.0f;

	SetReplicates(false);
}

void AMPFBInspectPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const FRotator ControlRotation = Controller ? Controller->GetControlRotation() : FRotator::ZeroRotator;
	const FRotator YawRotation(0.0f, ControlRotation.Yaw, 0.0f);
	const FVector Forward = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X);
	const FVector Right = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y);

	if (!FMath::IsNearlyZero(ForwardInput))
	{
		AddMovementInput(Forward, ForwardInput);
	}
	if (!FMath::IsNearlyZero(RightInput))
	{
		AddMovementInput(Right, RightInput);
	}
	if (!FMath::IsNearlyZero(UpInput))
	{
		AddMovementInput(FVector::UpVector, UpInput);
	}

	if (FloatingMovement)
	{
		FloatingMovement->MaxSpeed = bFast ? FastSpeed : NormalSpeed;
	}
}

void AMPFBInspectPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	PlayerInputComponent->BindKey(EKeys::W, IE_Pressed, this, &AMPFBInspectPawn::ForwardPressed).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::W, IE_Released, this, &AMPFBInspectPawn::ForwardReleased).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::S, IE_Pressed, this, &AMPFBInspectPawn::BackwardPressed).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::S, IE_Released, this, &AMPFBInspectPawn::BackwardReleased).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::A, IE_Pressed, this, &AMPFBInspectPawn::LeftPressed).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::A, IE_Released, this, &AMPFBInspectPawn::LeftReleased).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::D, IE_Pressed, this, &AMPFBInspectPawn::RightPressed).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::D, IE_Released, this, &AMPFBInspectPawn::RightReleased).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::Q, IE_Pressed, this, &AMPFBInspectPawn::DownPressed).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::Q, IE_Released, this, &AMPFBInspectPawn::DownReleased).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::E, IE_Pressed, this, &AMPFBInspectPawn::UpPressed).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::E, IE_Released, this, &AMPFBInspectPawn::UpReleased).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::LeftShift, IE_Pressed, this, &AMPFBInspectPawn::SetFastPressed).bConsumeInput = false;
	PlayerInputComponent->BindKey(EKeys::LeftShift, IE_Released, this, &AMPFBInspectPawn::SetFastReleased).bConsumeInput = false;
	PlayerInputComponent->BindAxisKey(EKeys::MouseX, this, &AMPFBInspectPawn::LookYaw);
	PlayerInputComponent->BindAxisKey(EKeys::MouseY, this, &AMPFBInspectPawn::LookPitch);
}

void AMPFBInspectPawn::ForwardPressed()
{
	ForwardInput = 1.0f;
}

void AMPFBInspectPawn::ForwardReleased()
{
	ForwardInput = 0.0f;
}

void AMPFBInspectPawn::BackwardPressed()
{
	ForwardInput = -1.0f;
}

void AMPFBInspectPawn::BackwardReleased()
{
	ForwardInput = 0.0f;
}

void AMPFBInspectPawn::LeftPressed()
{
	RightInput = -1.0f;
}

void AMPFBInspectPawn::LeftReleased()
{
	RightInput = 0.0f;
}

void AMPFBInspectPawn::RightPressed()
{
	RightInput = 1.0f;
}

void AMPFBInspectPawn::RightReleased()
{
	RightInput = 0.0f;
}

void AMPFBInspectPawn::DownPressed()
{
	UpInput = -1.0f;
}

void AMPFBInspectPawn::DownReleased()
{
	UpInput = 0.0f;
}

void AMPFBInspectPawn::UpPressed()
{
	UpInput = 1.0f;
}

void AMPFBInspectPawn::UpReleased()
{
	UpInput = 0.0f;
}

void AMPFBInspectPawn::SetFastPressed()
{
	bFast = true;
}

void AMPFBInspectPawn::SetFastReleased()
{
	bFast = false;
}

void AMPFBInspectPawn::LookYaw(float Value)
{
	AddControllerYawInput(Value);
}

void AMPFBInspectPawn::LookPitch(float Value)
{
	AddControllerPitchInput(Value);
}
