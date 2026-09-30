#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "MPFBInspectController.generated.h"

UCLASS(Blueprintable)
class FUTSALMOT_API AMPFBInspectController : public APlayerController
{
	GENERATED_BODY()

protected:
	virtual void BeginPlay() override;
};
