#include "JerseyNumberUVLibrary.h"
#include "CoreGlobals.h"

#include "Components/SkeletalMeshComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Engine/Texture.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Misc/Paths.h"
#include "Materials/MaterialInterface.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameters.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	const FName MaskFollowerName(TEXT("JerseyNumberUVMask"));
	const FName MaskFollowerTag(TEXT("FutsalMOTNumberUVPreview"));
	const FName PreviewActorTag(TEXT("FutsalMOTNumberUVTransientStage"));
	const FName PreviewMeshName(TEXT("JerseyNumberUVPreviewMesh"));
	bool IsPreviewMesh(USkeletalMeshComponent* Mesh)
	{
		return IsValid(Mesh) && IsValid(Mesh->GetOwner()) && Mesh->GetFName() == PreviewMeshName
			&& Mesh->GetOwner()->ActorHasTag(PreviewActorTag) && Mesh->GetOwner()->HasAnyFlags(RF_Transient);
	}
	bool IsUnitValue(const float Value)
	{
		return FMath::IsFinite(Value) && Value >= 0.0f && Value <= 1.0f;
	}

	bool HasNames(const TArray<FMaterialParameterInfo>& Actual, const TArray<FName>& Expected)
	{
		for (const FName Name : Expected)
		{
			if (!Actual.ContainsByPredicate([Name](const FMaterialParameterInfo& Info)
				{ return Info.Name == Name && Info.Association == EMaterialParameterAssociation::GlobalParameter; }))
			{
				return false;
			}
		}
		return true;
	}
}

bool UJerseyNumberUVLibrary::ValidateNumberParameters(
	const FJerseyNumberUVParameters& Parameters, FString& OutError)
{
	OutError.Reset();
	if (Parameters.Number < 1 || Parameters.Number > 99)
	{
		OutError = TEXT("球衣号码必须在 1..99 范围内");
		return false;
	}
	if (Parameters.EntityMaskID < 32 || Parameters.EntityMaskID > 41)
	{
		OutError = TEXT("号码实体 mask ID 必须在 32..41 范围内");
		return false;
	}
	const FLinearColor Rect = Parameters.UVRect;
	if (!IsUnitValue(Rect.R) || !IsUnitValue(Rect.G) || !IsUnitValue(Rect.B) || !IsUnitValue(Rect.A)
		|| Rect.R >= Rect.B || Rect.G >= Rect.A)
	{
		OutError = TEXT("号码 UV 矩形必须位于 0..1 且具有正宽高");
		return false;
	}
	const FLinearColor Ink = Parameters.InkColor;
	if (!IsUnitValue(Ink.R) || !IsUnitValue(Ink.G) || !IsUnitValue(Ink.B) || !IsUnitValue(Ink.A))
	{
		OutError = TEXT("号码颜色必须为 0..1 有限数值");
		return false;
	}
	return true;
}

int32 UJerseyNumberUVLibrary::FindUniqueJerseySlotFromNames(const TArray<FName>& SlotNames)
{
	const FName JerseySlot(TEXT("\u6750\u8d28"));
	int32 Found = INDEX_NONE;
	for (int32 Index = 0; Index < SlotNames.Num(); ++Index)
	{
		if (SlotNames[Index] == JerseySlot)
		{
			if (Found != INDEX_NONE)
			{
				return INDEX_NONE;
			}
			Found = Index;
		}
	}
	return Found;
}

int32 UJerseyNumberUVLibrary::FindUniqueJerseySlot(USkeletalMeshComponent* VisualMesh)
{
	return IsValid(VisualMesh) ? FindUniqueJerseySlotFromNames(VisualMesh->GetMaterialSlotNames()) : INDEX_NONE;
}

UMaterialInstanceDynamic* UJerseyNumberUVLibrary::CreateNumberMaterial(
	UMaterialInterface* ParentMaterial,
	UTexture* NumberAtlas,
	UObject* RuntimeOuter,
	const FJerseyNumberUVParameters& Parameters,
	FString& OutError)
{
	if (!ValidateNumberParameters(Parameters, OutError))
	{
		return nullptr;
	}
	if (!IsValid(ParentMaterial) || !IsValid(NumberAtlas) || !IsValid(RuntimeOuter))
	{
		OutError = TEXT("号码母材质、图集和运行时 Outer 必须有效");
		return nullptr;
	}
	TArray<FMaterialParameterInfo> Scalars, Vectors, Textures;
	TArray<FGuid> ParameterIDs;
	ParentMaterial->GetAllScalarParameterInfo(Scalars, ParameterIDs);
	ParameterIDs.Reset();
	ParentMaterial->GetAllVectorParameterInfo(Vectors, ParameterIDs);
	ParameterIDs.Reset();
	ParentMaterial->GetAllTextureParameterInfo(Textures, ParameterIDs);
	if (!HasNames(Scalars, { TEXT("NumberIndex"), TEXT("NumberEnabled"), TEXT("NumberMaskMode"), TEXT("NumberMaskID") })
		|| !HasNames(Vectors, { TEXT("NumberUVRect"), TEXT("NumberUVTransform"), TEXT("NumberInkColor") })
		|| !HasNames(Textures, { TEXT("NumberAtlas") }))
	{
		OutError = TEXT("号码母材质缺少已定义的全局 scalar/vector/texture 参数");
		return nullptr;
	}
	UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(ParentMaterial, RuntimeOuter);
	if (!IsValid(Material))
	{
		OutError = TEXT("创建号码动态材质失败");
		return nullptr;
	}
	Material->SetScalarParameterValue(TEXT("NumberIndex"), Parameters.Number - 1);
	Material->SetScalarParameterValue(TEXT("NumberEnabled"), 1.0f);
	Material->SetScalarParameterValue(TEXT("NumberMaskMode"), 0.0f);
	Material->SetScalarParameterValue(TEXT("NumberMaskID"), Parameters.EntityMaskID);
	Material->SetVectorParameterValue(TEXT("NumberUVRect"), Parameters.UVRect);
	Material->SetVectorParameterValue(TEXT("NumberUVTransform"),
		FLinearColor(Parameters.bFlipU ? 1.0f : 0.0f, Parameters.bFlipV ? 1.0f : 0.0f, 0.0f, 0.0f));
	Material->SetVectorParameterValue(TEXT("NumberInkColor"), Parameters.InkColor);
	Material->SetTextureParameterValue(TEXT("NumberAtlas"), NumberAtlas);
	return Material;
}

USkeletalMeshComponent* UJerseyNumberUVLibrary::CreateNumberMaskFollower(
	USkeletalMeshComponent* VisualMesh,
	UMaterialInterface* MaskedNumberMaterial,
	UMaterialInterface* EmptyMaskedMaterial,
	int32 EntityMaskID,
	FString& OutError)
{
	OutError.Reset();
	if (!IsValid(VisualMesh) || !VisualMesh->IsRegistered() || !IsValid(VisualMesh->GetOwner()) || !VisualMesh->GetWorld()
		|| !IsValid(VisualMesh->GetSkeletalMeshAsset()) || VisualMesh->IsTemplate())
	{
		OutError = TEXT("号码代理要求已注册球员实例、有效 World 和 SkeletalMesh");
		return nullptr;
	}
	if (EntityMaskID < 32 || EntityMaskID > 41 || !IsValid(MaskedNumberMaterial) || !IsValid(EmptyMaskedMaterial)
		|| MaskedNumberMaterial->GetBlendMode() != BLEND_Masked || EmptyMaskedMaterial->GetBlendMode() != BLEND_Masked)
	{
		OutError = TEXT("号码代理要求 32..41 的 ID 及两个已验收的 masked 材质");
		return nullptr;
	}
	const int32 JerseyIndex = FindUniqueJerseySlot(VisualMesh);
	AActor* Owner = VisualMesh->GetOwner();
	TArray<USkeletalMeshComponent*> ExistingComponents;
	Owner->GetComponents(ExistingComponents);
	const bool HasActiveFollower = ExistingComponents.ContainsByPredicate(
		[](const USkeletalMeshComponent* Component)
		{ return IsValid(Component) && Component->IsRegistered() && Component->ComponentTags.Contains(MaskFollowerTag); });
	if (JerseyIndex == INDEX_NONE || HasActiveFollower)
	{
		OutError = TEXT("球衣 slot 不唯一或号码代理名称已占用，拒绝覆盖");
		return nullptr;
	}
	// 已销毁组件的 UObject 名称可保留到 GC；新事务不依赖 GC 时机，也不复用旧对象。
	const FName UniqueName = MakeUniqueObjectName(Owner, USkeletalMeshComponent::StaticClass(), MaskFollowerName);
	USkeletalMeshComponent* Follower = NewObject<USkeletalMeshComponent>(Owner, UniqueName, RF_Transient);
	if (!IsValid(Follower))
	{
		OutError = TEXT("创建号码蒙皮组件失败");
		return nullptr;
	}
	// 此组件从主网格读取同一帧骨骼与 LOD，不使用背部平面近似曲面。
	Follower->ComponentTags.Add(MaskFollowerTag);
	Owner->AddInstanceComponent(Follower);
	Follower->SetupAttachment(VisualMesh);
	Follower->SetRelativeTransform(FTransform::Identity);
	Follower->SetSkeletalMeshAsset(VisualMesh->GetSkeletalMeshAsset());
	Follower->SetLeaderPoseComponent(VisualMesh, true, false);
	Follower->bSyncAttachParentLOD = true;
	Follower->SetForcedLOD(VisualMesh->GetForcedLOD());
	Follower->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Follower->SetGenerateOverlapEvents(false);
	Follower->SetCastShadow(false);
	Follower->SetVisibleInRayTracing(false);
	Follower->SetRenderInMainPass(false);
	Follower->SetRenderInDepthPass(false);
	Follower->SetRenderCustomDepth(true);
	Follower->SetCustomDepthStencilValue(EntityMaskID);
	for (int32 Index = 0; Index < VisualMesh->GetNumMaterials(); ++Index)
	{
		Follower->SetMaterial(Index, Index == JerseyIndex ? MaskedNumberMaterial : EmptyMaskedMaterial);
	}
	Follower->RegisterComponentWithWorld(VisualMesh->GetWorld());
	if (!Follower->IsRegistered() || Follower->GetAttachParent() != VisualMesh
		|| Follower->GetSkeletalMeshAsset() != VisualMesh->GetSkeletalMeshAsset())
	{
		Owner->RemoveInstanceComponent(Follower);
		Follower->DestroyComponent();
		OutError = TEXT("号码代理注册或网格绑定回读失败，已删除新组件");
		return nullptr;
	}
	return Follower;
}

bool UJerseyNumberUVLibrary::DestroyNumberMaskFollower(
	USkeletalMeshComponent* Follower,
	USkeletalMeshComponent* ExpectedVisualMesh,
	FString& OutError)
{
	OutError.Reset();
	if (!IsValid(Follower) || !IsValid(ExpectedVisualMesh) || !IsValid(Follower->GetOwner())
		|| Follower == ExpectedVisualMesh || Follower->GetOwner() != ExpectedVisualMesh->GetOwner()
		|| !Follower->GetName().StartsWith(MaskFollowerName.ToString()) || !Follower->ComponentTags.Contains(MaskFollowerTag)
		|| Follower->GetAttachParent() != ExpectedVisualMesh)
	{
		OutError = TEXT("号码代理身份或父组件不匹配，拒绝删除并保留恢复证据");
		return false;
	}
	Follower->GetOwner()->RemoveInstanceComponent(Follower);
	Follower->SetLeaderPoseComponent(nullptr, true, false);
	Follower->DestroyComponent();
	return !Follower->IsRegistered();
}

USkeletalMeshComponent* UJerseyNumberUVLibrary::CreateNumberPreviewMesh(
	USkeletalMeshComponent* SourceMesh, UMaterialInterface* NumberMaterial,
	const FTransform& WorldTransform, FString& OutError)
{
	OutError.Reset();
	const int32 JerseyIndex = FindUniqueJerseySlot(SourceMesh);
	if (!IsValid(SourceMesh) || !SourceMesh->IsRegistered() || !SourceMesh->GetWorld()
		|| !IsValid(SourceMesh->GetSkeletalMeshAsset()) || SourceMesh->IsTemplate()
		|| JerseyIndex == INDEX_NONE || !IsValid(NumberMaterial) || WorldTransform.ContainsNaN())
	{
		OutError = TEXT("近景测试要求已注册源网格、唯一球衣 slot、有效材质和有限变换");
		return nullptr;
	}
	FActorSpawnParameters Spawn;
	Spawn.ObjectFlags = RF_Transient;
	Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* Owner = SourceMesh->GetWorld()->SpawnActor<AActor>(AActor::StaticClass(), WorldTransform, Spawn);
	if (!IsValid(Owner))
	{
		OutError = TEXT("创建 transient 测试 Actor 失败");
		return nullptr;
	}
	Owner->Tags.Add(PreviewActorTag);
	USkeletalMeshComponent* Mesh = NewObject<USkeletalMeshComponent>(Owner, PreviewMeshName, RF_Transient);
	Owner->SetRootComponent(Mesh);
	Owner->AddInstanceComponent(Mesh);
	Mesh->SetSkeletalMeshAsset(SourceMesh->GetSkeletalMeshAsset());
	Mesh->SetWorldTransform(WorldTransform);
	Mesh->SetLeaderPoseComponent(SourceMesh, true, false);
	Mesh->SetForcedLOD(SourceMesh->GetForcedLOD());
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetRenderCustomDepth(false);
	Mesh->SetVisibleInRayTracing(false);
	for (int32 Index = 0; Index < SourceMesh->GetNumMaterials(); ++Index)
	{
		Mesh->SetMaterial(Index, Index == JerseyIndex ? NumberMaterial : SourceMesh->GetMaterial(Index));
	}
	Mesh->RegisterComponentWithWorld(SourceMesh->GetWorld());
	if (!Mesh->IsRegistered())
	{
		Owner->Destroy();
		OutError = TEXT("近景测试网格注册失败，已销毁新 Actor");
		return nullptr;
	}
	return Mesh;
}

UStaticMeshComponent* UJerseyNumberUVLibrary::CreateNumberPreviewOccluder(
	USkeletalMeshComponent* PreviewMesh, UStaticMesh* OccluderMesh,
	const FTransform& WorldTransform, FString& OutError)
{
	OutError.Reset();
	if (!IsPreviewMesh(PreviewMesh) || !IsValid(OccluderMesh) || WorldTransform.ContainsNaN())
	{
		OutError = TEXT("遮挡测试只能使用此接口创建的临时球员 Owner");
		return nullptr;
	}
	AActor* Owner = PreviewMesh->GetOwner();
	UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(Owner, NAME_None, RF_Transient);
	Owner->AddInstanceComponent(Mesh);
	Mesh->SetupAttachment(PreviewMesh);
	Mesh->SetStaticMesh(OccluderMesh);
	Mesh->SetWorldTransform(WorldTransform);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetRenderCustomDepth(false);
	Mesh->RegisterComponentWithWorld(PreviewMesh->GetWorld());
	if (!Mesh->IsRegistered())
	{
		Owner->RemoveInstanceComponent(Mesh);
		Mesh->DestroyComponent();
		OutError = TEXT("遮挡测试组件注册失败");
		return nullptr;
	}
	return Mesh;
}

bool UJerseyNumberUVLibrary::CaptureNumberPreviewPair(
	USkeletalMeshComponent* PreviewMesh, UMaterialInterface* NumberPostProcess,
	const FTransform& CameraTransform, int32 Width, int32 Height, float HorizontalFOV,
	const FString& OutputDirectory, const FString& CaseName,
	int64& OutEngineFrame, FString& OutError)
{
	OutError.Reset();
	OutEngineFrame = -1;
	const IConsoleVariable* CustomDepth = IConsoleManager::Get().FindConsoleVariable(TEXT("r.CustomDepth"));
	if (!IsPreviewMesh(PreviewMesh) || !PreviewMesh->IsRegistered() || !IsValid(NumberPostProcess)
		|| !NumberPostProcess->GetMaterial() || NumberPostProcess->GetMaterial()->MaterialDomain != MD_PostProcess
		|| !CustomDepth || CustomDepth->GetInt() != 3
		|| Width < 64 || Width > 2048 || Height < 64 || Height > 2048
		|| !FMath::IsFinite(HorizontalFOV) || HorizontalFOV < 5.0f || HorizontalFOV > 120.0f
		|| CameraTransform.ContainsNaN() || !FPaths::IsRelative(CaseName)
		|| CaseName.IsEmpty() || CaseName.Contains(TEXT("/")) || CaseName.Contains(TEXT("\\")) || CaseName.Contains(TEXT("..")))
	{
		OutError = TEXT("捕获输入无效；要求临时球员、后处理域、r.CustomDepth=3、合法尺寸和文件名");
		return false;
	}
	const FString RGBPath = FPaths::Combine(OutputDirectory, CaseName + TEXT("_rgb.png"));
	const FString MaskPath = FPaths::Combine(OutputDirectory, CaseName + TEXT("_mask.png"));
	const FString AllowedRoot = TEXT("G:/FutsalMOT_Dataset/test");
	if (!FPaths::IsUnderDirectory(FPaths::ConvertRelativePathToFull(OutputDirectory), AllowedRoot)
		|| IFileManager::Get().FileExists(*RGBPath) || IFileManager::Get().FileExists(*MaskPath)
		|| !IFileManager::Get().MakeDirectory(*OutputDirectory, true))
	{
		OutError = TEXT("捕获输出已存在或目录不可创建，拒绝覆盖");
		return false;
	}
	AActor* Owner = PreviewMesh->GetOwner();
	USceneCaptureComponent2D* Capture = NewObject<USceneCaptureComponent2D>(Owner, NAME_None, RF_Transient);
	Capture->bCaptureEveryFrame = false;
	Capture->bCaptureOnMovement = false;
	// 单次捕获也必须持有 ViewState，否则引擎会跳过号码后处理 blendable。
	Capture->bAlwaysPersistRenderingState = true;
	Capture->CaptureSource = SCS_FinalColorLDR;
	Capture->FOVAngle = HorizontalFOV;
	Capture->ShowFlags.SetTemporalAA(false);
	Capture->ShowFlags.SetAntiAliasing(false);
	Capture->ShowFlags.SetMotionBlur(false);
	Capture->ShowFlags.SetDepthOfField(false);
	Capture->PostProcessSettings.bOverride_MotionBlurAmount = true;
	Capture->PostProcessSettings.MotionBlurAmount = 0.0f;
	Capture->PostProcessSettings.bOverride_VignetteIntensity = true;
	Capture->PostProcessSettings.VignetteIntensity = 0.0f;
	Capture->SetWorldTransform(CameraTransform);
	Capture->RegisterComponentWithWorld(PreviewMesh->GetWorld());
	UTextureRenderTarget2D* Target = UKismetRenderingLibrary::CreateRenderTarget2D(
		Owner, Width, Height, RTF_RGBA8, FLinearColor::Black, false, false);
	if (!Capture->IsRegistered() || !IsValid(Target))
	{
		Capture->DestroyComponent();
		OutError = TEXT("创建同步捕获组件或 RenderTarget 失败");
		return false;
	}
	Target->TargetGamma = 2.2f;
	Capture->TextureTarget = Target;
	const uint64 FrameBefore = GFrameCounter;
	const uint32 PoseBefore = PreviewMesh->GetBoneTransformRevisionNumber();
	// 同一次游戏线程调用中完成两次捕获和同步读回，中间不推进动画或 Sequence。
	Capture->CaptureScene();
	UKismetRenderingLibrary::ExportRenderTarget(Owner, Target, OutputDirectory, CaseName + TEXT("_rgb.png"));
	Target->TargetGamma = 1.0f;
	Capture->AddOrUpdateBlendable(NumberPostProcess, 1.0f);
	Capture->CaptureScene();
	UKismetRenderingLibrary::ExportRenderTarget(Owner, Target, OutputDirectory, CaseName + TEXT("_mask.png"));
	const bool bStable = FrameBefore == GFrameCounter && PoseBefore == PreviewMesh->GetBoneTransformRevisionNumber();
	Capture->TextureTarget = nullptr;
	UKismetRenderingLibrary::ReleaseRenderTarget2D(Target);
	Capture->DestroyComponent();
	if (!bStable || IFileManager::Get().FileSize(*RGBPath) <= 0 || IFileManager::Get().FileSize(*MaskPath) <= 0)
	{
		OutError = TEXT("捕获期间帧/姿态变化或输出缺失；保留输出用于失败诊断，不授予验收");
		return false;
	}
	OutEngineFrame = static_cast<int64>(FrameBefore);
	return true;
}

bool UJerseyNumberUVLibrary::DestroyNumberPreviewMesh(USkeletalMeshComponent* PreviewMesh, FString& OutError)
{
	OutError.Reset();
	if (!IsPreviewMesh(PreviewMesh))
	{
		OutError = TEXT("临时球员身份不匹配，拒绝销毁 Actor");
		return false;
	}
	PreviewMesh->SetLeaderPoseComponent(nullptr, true, false);
	return PreviewMesh->GetOwner()->Destroy();
}
