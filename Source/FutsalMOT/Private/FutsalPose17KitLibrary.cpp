#include "FutsalPose17KitLibrary.h"

#include "Algo/AllOf.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreGlobals.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Materials/Material.h"

bool UFutsalPose17KitLibrary::ResolveSemanticKitSlots(const TArray<FName>& Names, int32& JerseySlot, int32& ShortsSlot, FString& Error)
{
	JerseySlot = ShortsSlot = INDEX_NONE; Error.Reset();
	for (int32 Index = 0; Index < Names.Num(); ++Index)
	{
		// 与episode_appearance的已验语义一致；不能猜成名为Jersey的slot。
		const bool bJersey = Names[Index] == TEXT("材质");
		const bool bShorts = Names[Index] == TEXT("Human_futsalmot_shorts_male_v2_005")
			|| Names[Index] == TEXT("Human_futsalmot_shorts_male_final");
		if ((bJersey && JerseySlot != INDEX_NONE) || (bShorts && ShortsSlot != INDEX_NONE))
		{ Error = TEXT("服装语义slot重复，拒绝按索引猜测"); return false; }
		if (bJersey) JerseySlot = Index;
		if (bShorts) ShortsSlot = Index;
	}
	if (JerseySlot == INDEX_NONE || ShortsSlot == INDEX_NONE)
	{ Error = TEXT("缺少已验球衣/短裤语义slot"); return false; }
	return true;
}

bool UFutsalPose17KitLibrary::ValidateSeededKitAssets(UMaterialInterface* Jersey, UMaterialInterface* Shorts, const FString& ID, FString& Error)
{
	Error.Reset();
	if (ID != TEXT("01") && ID != TEXT("02") && ID != TEXT("03") && ID != TEXT("04") && ID != TEXT("05"))
	{ Error = TEXT("仅接受原appearance v1的Set_01至05，不接号码或未准入扩展目录"); return false; }
	if (!IsValid(Jersey) || !IsValid(Shorts) || !Jersey->IsA<UMaterial>() || !Shorts->IsA<UMaterial>())
	{ Error = TEXT("原Set球衣/短裤必须为已载入的实际Material资产"); return false; }
	const FString Prefix = TEXT("/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_");
	if (Jersey->GetOutermost()->GetName() != Prefix + TEXT("Jersey_Set_") + ID
		|| Shorts->GetOutermost()->GetName() != Prefix + TEXT("Shorts_Set_") + ID)
	{ Error = TEXT("服装资产路径与原Set ID不匹配"); return false; }
	return true;
}

bool UFutsalPose17KitLibrary::VerifySeededKit(const FFutsalPose17KitState& Previous, FString& Error)
{
	Error.Reset();
	USkeletalMeshComponent* Mesh = Previous.Component;
	if (!Previous.bMutationStarted || !IsValid(Mesh) || Mesh->GetSkeletalMeshAsset() != Previous.Mesh
		|| Mesh->GetAnimClass() != Previous.AnimationClass || Mesh->GetAnimInstance() != Previous.AnimationInstance
		|| Mesh->GetNumMaterials() != Previous.ResolvedMaterials.Num())
	{ Error = TEXT("服装读回的实际组件、网格、动画或slot数量变化"); return false; }
	for (int32 Index = 0; Index < Previous.ResolvedMaterials.Num(); ++Index)
	{
		UMaterialInterface* Expected = Index == Previous.JerseySlot ? Previous.Jersey.Get()
			: Index == Previous.ShortsSlot ? Previous.Shorts.Get() : Previous.ResolvedMaterials[Index].Get();
		if (Mesh->GetMaterial(Index) != Expected)
		{ Error = TEXT("球衣/短裤或其他材质slot读回不一致"); return false; }
	}
	return true;
}

bool UFutsalPose17KitLibrary::ApplySeededKit(USkeletalMeshComponent* Mesh, UMaterialInterface* Jersey, UMaterialInterface* Shorts,
	const FString& ID, const FString& Fingerprint, FFutsalPose17KitState& Previous, FFutsalPose17KitEvidence& Evidence, FString& Error)
{
	Previous = FFutsalPose17KitState(); Evidence = FFutsalPose17KitEvidence(); Error.Reset();
	if (!IsValid(Mesh) || !Mesh->GetWorld() || Mesh->GetWorld()->WorldType != EWorldType::PIE
		|| Mesh->GetFName() != TEXT("MPFBVisual") || !Mesh->GetSkeletalMeshAsset())
	{ Error = TEXT("服装事务仅允许实际PIE MPFBVisual，不修改Editor组件或隐藏驱动"); return false; }
	if (Fingerprint.Len() != 64 || Fingerprint != Fingerprint.ToLower()
		|| !Algo::AllOf(Fingerprint, [](TCHAR C) { return FChar::IsHexDigit(C); }))
	{ Error = TEXT("必须绑定原appearance清单fingerprint"); return false; }
	if (!ValidateSeededKitAssets(Jersey, Shorts, ID, Error)) return false;
	TArray<FName> Names;
	for (const auto& Slot : Mesh->GetSkeletalMeshAsset()->GetMaterials()) Names.Add(Slot.MaterialSlotName);
	if (!ResolveSemanticKitSlots(Names, Previous.JerseySlot, Previous.ShortsSlot, Error)) return false;
	Previous.Component = Mesh; Previous.Mesh = Mesh->GetSkeletalMeshAsset();
	Previous.AnimationClass = Mesh->GetAnimClass(); Previous.AnimationInstance = Mesh->GetAnimInstance();
	Previous.OverrideMaterials = Mesh->OverrideMaterials; Previous.Jersey = Jersey; Previous.Shorts = Shorts;
	for (int32 Index = 0; Index < Mesh->GetNumMaterials(); ++Index) Previous.ResolvedMaterials.Add(Mesh->GetMaterial(Index));
	const FTransform Transform = Mesh->GetComponentTransform();
	Evidence.ComponentPath = Mesh->GetPathName(); Evidence.KitSetID = ID; Evidence.AppearanceFingerprint = Fingerprint;
	Evidence.JerseySlot = Previous.JerseySlot; Evidence.ShortsSlot = Previous.ShortsSlot;
	Evidence.JerseyMaterialPath = Jersey->GetPathName(); Evidence.ShortsMaterialPath = Shorts->GetPathName();
	Previous.bMutationStarted = true;
	Mesh->SetMaterial(Previous.JerseySlot, Jersey); Mesh->SetMaterial(Previous.ShortsSlot, Shorts);
	Evidence.AppliedEngineFrame = static_cast<int64>(GFrameCounter);
	Evidence.bMeshAnimationTransformPreserved = Mesh->GetSkeletalMeshAsset() == Previous.Mesh
		&& Mesh->GetAnimInstance() == Previous.AnimationInstance && Mesh->GetAnimClass() == Previous.AnimationClass
		&& Mesh->GetComponentTransform().Equals(Transform, 0);
	Evidence.bLiveReadbackSucceeded = VerifySeededKit(Previous, Error);
	Evidence.bOtherMaterialsPreserved = Evidence.bLiveReadbackSucceeded;
	Evidence.bApplySucceeded = Evidence.bLiveReadbackSucceeded && Evidence.bMeshAnimationTransformPreserved;
	if (!Evidence.bApplySucceeded && Error.IsEmpty()) Error = TEXT("服装应用后网格/动画/变换发生变化");
	Evidence.Error = Error;
	return Evidence.bApplySucceeded;
}

bool UFutsalPose17KitLibrary::RestoreSeededKit(const FFutsalPose17KitState& Previous, FFutsalPose17KitEvidence& Evidence, FString& Error)
{
	Evidence.bRestoreAttempted = true; Evidence.bRestoreSucceeded = false; Error.Reset();
	USkeletalMeshComponent* Mesh = Previous.Component;
	if (!Previous.bMutationStarted || !IsValid(Mesh) || Mesh->GetSkeletalMeshAsset() != Previous.Mesh)
	{ Error = TEXT("服装恢复必须在原角色恢复之前，且组件/网格身份仍匹配"); Evidence.Error = Error; return false; }
	Mesh->EmptyOverrideMaterials();
	for (int32 Index = 0; Index < Previous.OverrideMaterials.Num(); ++Index) Mesh->SetMaterial(Index, Previous.OverrideMaterials[Index]);
	bool bMatched = Mesh->OverrideMaterials == Previous.OverrideMaterials && Mesh->GetNumMaterials() == Previous.ResolvedMaterials.Num();
	for (int32 Index = 0; Index < Previous.ResolvedMaterials.Num(); ++Index)
		bMatched &= Mesh->GetMaterial(Index) == Previous.ResolvedMaterials[Index];
	Evidence.bRestoreSucceeded = bMatched;
	if (!bMatched) { Error = TEXT("服装恢复后的原override及全部材质slot读回不一致"); Evidence.Error = Error; }
	return bMatched;
}
