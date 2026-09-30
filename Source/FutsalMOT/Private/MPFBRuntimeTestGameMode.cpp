#include "MPFBRuntimeTestGameMode.h"

#include "MPFBInspectController.h"
#include "MPFBInspectPawn.h"

AMPFBRuntimeTestGameMode::AMPFBRuntimeTestGameMode()
{
	PlayerControllerClass = AMPFBInspectController::StaticClass();
	DefaultPawnClass = AMPFBInspectPawn::StaticClass();
}
