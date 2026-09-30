#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "MPFBInspectPawn.generated.h"

class UCameraComponent;
class UFloatingPawnMovement;

UCLASS(Blueprintable)
class FUTSALMOT_API AMPFBInspectPawn : public APawn
{
	GENERATED_BODY()

public:
	AMPFBInspectPawn();

	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Inspection")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Inspection")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Inspection")
	TObjectPtr<UFloatingPawnMovement> FloatingMovement;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Inspection|Movement")
	float NormalSpeed = 1000.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Inspection|Movement")
	float FastSpeed = 3000.0f;

private:
	void ForwardPressed();
	void ForwardReleased();
	void BackwardPressed();
	void BackwardReleased();
	void LeftPressed();
	void LeftReleased();
	void RightPressed();
	void RightReleased();
	void DownPressed();
	void DownReleased();
	void UpPressed();
	void UpReleased();
	void SetFastPressed();
	void SetFastReleased();
	void LookYaw(float Value);
	void LookPitch(float Value);

	float ForwardInput = 0.0f;
	float RightInput = 0.0f;
	float UpInput = 0.0f;
	bool bFast = false;
};
