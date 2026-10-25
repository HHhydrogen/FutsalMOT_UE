#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FutsalPose17KitLibrary.generated.h"

class USkeletalMeshComponent;
class USkeletalMesh;
class UMaterialInterface;
class UAnimInstance;

/** 只记录PIE服装事务，不重新分配模型/肤色或修改资产。 */
USTRUCT()
struct FFutsalPose17KitState
{
	GENERATED_BODY()
	UPROPERTY() TObjectPtr<USkeletalMeshComponent> Component = nullptr;
	UPROPERTY() TObjectPtr<USkeletalMesh> Mesh = nullptr;
	UPROPERTY() TObjectPtr<UAnimInstance> AnimationInstance = nullptr;
	UPROPERTY() TObjectPtr<UClass> AnimationClass = nullptr;
	UPROPERTY() TArray<TObjectPtr<UMaterialInterface>> OverrideMaterials;
	UPROPERTY() TArray<TObjectPtr<UMaterialInterface>> ResolvedMaterials;
	UPROPERTY() TObjectPtr<UMaterialInterface> Jersey = nullptr;
	UPROPERTY() TObjectPtr<UMaterialInterface> Shorts = nullptr;
	UPROPERTY() bool bMutationStarted = false;
	int32 JerseySlot = INDEX_NONE;
	int32 ShortsSlot = INDEX_NONE;
};

USTRUCT(BlueprintType)
struct FUTSALMOT_API FFutsalPose17KitEvidence
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FString ComponentPath;
	UPROPERTY(BlueprintReadOnly) FString KitSetID;
	UPROPERTY(BlueprintReadOnly) FString AppearanceFingerprint;
	UPROPERTY(BlueprintReadOnly) FString JerseyMaterialPath;
	UPROPERTY(BlueprintReadOnly) FString ShortsMaterialPath;
	UPROPERTY(BlueprintReadOnly) int32 JerseySlot = INDEX_NONE;
	UPROPERTY(BlueprintReadOnly) int32 ShortsSlot = INDEX_NONE;
	UPROPERTY(BlueprintReadOnly) int64 AppliedEngineFrame = -1;
	UPROPERTY(BlueprintReadOnly) bool bApplySucceeded = false;
	UPROPERTY(BlueprintReadOnly) bool bOtherMaterialsPreserved = false;
	UPROPERTY(BlueprintReadOnly) bool bMeshAnimationTransformPreserved = false;
	UPROPERTY(BlueprintReadOnly) bool bLiveReadbackSucceeded = false;
	UPROPERTY(BlueprintReadOnly) bool bGpuLbsEligibleAfterKit = false;
	UPROPERTY(BlueprintReadOnly) bool bRestoreAttempted = false;
	UPROPERTY(BlueprintReadOnly) bool bRestoreSucceeded = false;
	UPROPERTY(BlueprintReadOnly) FString Error;
};

/** 接回现有appearance v1选定的Set；此类不创建新的随机流或号码功能。 */
UCLASS()
class FUTSALMOT_API UFutsalPose17KitLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17|Kit")
	static bool ResolveSemanticKitSlots(const TArray<FName>& SlotNames, int32& JerseySlot, int32& ShortsSlot, FString& Error);
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Pose17|Kit")
	static bool ValidateSeededKitAssets(UMaterialInterface* Jersey, UMaterialInterface* Shorts, const FString& KitSetID, FString& Error);
	static bool ApplySeededKit(USkeletalMeshComponent* Mesh, UMaterialInterface* Jersey, UMaterialInterface* Shorts,
		const FString& KitSetID, const FString& AppearanceFingerprint, FFutsalPose17KitState& Previous,
		FFutsalPose17KitEvidence& Evidence, FString& Error);
	static bool VerifySeededKit(const FFutsalPose17KitState& Previous, FString& Error);
	static bool RestoreSeededKit(const FFutsalPose17KitState& Previous, FFutsalPose17KitEvidence& Evidence, FString& Error);
};
