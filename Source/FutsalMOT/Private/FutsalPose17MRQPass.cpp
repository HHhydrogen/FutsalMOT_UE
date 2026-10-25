#include "FutsalPose17MRQPass.h"

#include "CoreGlobals.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimInstance.h"
#include "CineCameraActor.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "MoviePipeline.h"
#include "Camera/CameraTypes.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "JsonObjectConverter.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include <initializer_list>

namespace
{
const TCHAR* CalibrationAssets[] = {
	TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_004/Mesh/MPFB_Player_004.MPFB_Player_004"),
	TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_005/Mesh/MPFB_Player_005.MPFB_Player_005"),
	TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_006/Mesh/MPFB_Player_006.MPFB_Player_006"),
	TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_007/Mesh/MPFB_Player_007.MPFB_Player_007"),
	TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_008/Mesh/MPFB_Player_008.MPFB_Player_008"),
	TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_009/Mesh/MPFB_Player_009.MPFB_Player_009")};

bool IsCalibrationAsset(const FString& Path)
{
	for (const TCHAR* Allowed : CalibrationAssets) if (Path==Allowed) return true;
	return false;
}

const TCHAR* OriginalVisualAsset = TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003.MPFB_Player_003");
const TCHAR* JointEntities[] = {TEXT("L0"),TEXT("L1"),TEXT("L2"),TEXT("L3"),TEXT("L4"),TEXT("R0"),TEXT("R1"),TEXT("R2"),TEXT("R3"),TEXT("R4")};
const int32 JointPlayerIds[] = {3,4,5,6,7,8,9,3,4,5};

const TCHAR* JointExpectedAsset(const FString& Entity)
{
	for (int32 Index=0; Index<10; ++Index)
		if (Entity==JointEntities[Index]) return JointPlayerIds[Index]==3 ? OriginalVisualAsset : CalibrationAssets[JointPlayerIds[Index]-4];
	return nullptr;
}

TSharedRef<FJsonObject> ExplicitTransformJSON(const FTransform& Transform)
{
	TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
	const FVector Translation = Transform.GetTranslation(), Scale = Transform.GetScale3D();
	const FQuat Rotation = Transform.GetRotation();
	auto Numbers = [](std::initializer_list<double> Values)
	{
		TArray<TSharedPtr<FJsonValue>> Output;
		for (double Value : Values) Output.Add(MakeShared<FJsonValueNumber>(Value));
		return Output;
	};
	Result->SetArrayField(TEXT("translation_cm"), Numbers({Translation.X, Translation.Y, Translation.Z}));
	Result->SetArrayField(TEXT("rotation_xyzw"), Numbers({Rotation.X, Rotation.Y, Rotation.Z, Rotation.W}));
	Result->SetArrayField(TEXT("scale_xyz"), Numbers({Scale.X, Scale.Y, Scale.Z}));
	return Result;
}

USkeletalMeshComponent* FindExactTarget(UWorld* World, const FFutsalPose17MRQTarget& Target, FString& Error)
{
	AActor* Actor = nullptr;
	int32 ActorCount = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
		if (It->GetFName() == Target.ActorObjectName) { Actor = *It; ++ActorCount; }
	if (ActorCount != 1) { Error = TEXT("当前 MRQ World 中未找到唯一精确 Actor"); return nullptr; }
	USkeletalMeshComponent* Mesh = nullptr;
	int32 Count = 0;
	TInlineComponentArray<USkeletalMeshComponent*> Components(Actor);
	for (USkeletalMeshComponent* Component : Components)
		if (Component->GetFName() == Target.ComponentObjectName) { Mesh = Component; ++Count; }
	if (Count != 1) { Error = TEXT("目标 Actor 没有唯一显式 VisualMesh"); return nullptr; }
	return Mesh;
}
}

void UFutsalPose17MRQPass::SetupForPipelineImpl(UMoviePipeline* InPipeline)
{
	CameraSetupError.Reset(); PreviousCameraStates.Reset(); bCameraStateRestored = false;
	PreviousVisualStates.Reset(); VisualOverrideEvidence.Reset(); RestoreErrors.Reset(); bStreamingStateRestartRequired = false;
	PreviousKitStates.Reset(); SeededKitEvidence.Reset();
	GPUPreparedEngineFrame = -1;
	TSet<FName> SeenCameras;
	if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE || DiagnosticCameraObjectNames.IsEmpty())
	{
		CameraSetupError = TEXT("诊断pass需要PIE世界及显式相机对象名，在pipeline计时初始化前设置motionblur=0"); return;
	}
	const bool bCombinedGPUOverride = bUseGpuRenderCpuLbsForDiagnostic && bAllowPIEVisualMeshOverride
		&& DiagnosticScope == TEXT("pose17_gpu_render_cpu_lbs_character_calibration");
	const bool bJointGPUOverride = bUseGpuRenderCpuLbsForDiagnostic && bAllowPIEVisualMeshOverride && bAllowJointPose17Diagnostic
		&& DiagnosticScope == TEXT("pose17_gpu_render_cpu_lbs_joint_diagnostic");
	const bool bAnyGPUOverride = bCombinedGPUOverride || bJointGPUOverride;
	bool bValidKitFingerprint = SeededAppearanceFingerprint.Len() == 64
		&& SeededAppearanceFingerprint == SeededAppearanceFingerprint.ToLower();
	for (TCHAR Character : SeededAppearanceFingerprint) bValidKitFingerprint &= FChar::IsHexDigit(Character);
	if ((bApplySeededKitForDiagnostic && (!bJointGPUOverride || !bValidKitFingerprint))
		|| (!bApplySeededKitForDiagnostic && !SeededAppearanceFingerprint.IsEmpty()))
	{
		CameraSetupError = TEXT("原seed服装仅限显式joint GPU/LBS opt-in及原appearance fingerprint"); return;
	}
	const bool bInvalidGPUConfig = (!bAnyGPUOverride && DiagnosticScope != TEXT("pose17_gpu_render_cpu_lbs")) || bPrepareCPUForDiagnostic
		|| !bHideDriverForDiagnostic || (bAllowPIEVisualMeshOverride && !bAnyGPUOverride)
		|| MinimumGpuLbsWarmupFrames < 8 || MinimumGpuLbsWarmupFrames > 120
		|| (bAnyGPUOverride && (MinimumOverrideWarmupFrames != MinimumGpuLbsWarmupFrames || Targets.Num()!=(bJointGPUOverride ? 10 : 1)));
	if ((bAllowJointPose17Diagnostic && !bJointGPUOverride) || (bUseGpuRenderCpuLbsForDiagnostic && bInvalidGPUConfig))
	{
		CameraSetupError = TEXT("GPU/LBS要求明确独立或角色组合scope/CPU关闭/隐藏driver及匹配8..120warmup"); return;
	}
	for (FName CameraName : DiagnosticCameraObjectNames)
	{
		if (CameraName.IsNone() || SeenCameras.Contains(CameraName)) { CameraSetupError = TEXT("诊断相机名不能为空或重复"); return; }
		SeenCameras.Add(CameraName);
		AActor* CameraActor = nullptr;
		int32 Count = 0;
		for (TActorIterator<AActor> It(GetWorld()); It; ++It)
			if (It->GetFName() == CameraName) { CameraActor = *It; ++Count; }
		UCameraComponent* Camera = Count == 1 ? CameraActor->FindComponentByClass<UCameraComponent>() : nullptr;
		if (!Camera) { CameraSetupError = TEXT("无法唯一解析显式PIE相机"); return; }
		FFutsalPose17CameraState& Previous = PreviousCameraStates.AddDefaulted_GetRef();
		Previous.Component = Camera; Previous.PostProcess = Camera->PostProcessSettings;
		Previous.BlendWeight = Camera->PostProcessBlendWeight;
	}
	// 所有相机及所有目标先只读通过，之后才开始任何PIE override/相机mutation。
	if (Targets.IsEmpty() || MaxRecords < 1 || MaxRecords > 4096)
	{
		CameraSetupError = TEXT("诊断目标为空或记录上限非法"); return;
	}
	TSet<FString> Entities, Bindings;
	int32 OverrideCount = 0;
	for (const auto& Target : Targets)
	{
		const FString Binding = Target.ActorObjectName.ToString() + TEXT(":") + Target.ComponentObjectName.ToString();
		if (Target.EntityID.IsEmpty() || Entities.Contains(Target.EntityID) || Bindings.Contains(Binding)
			|| Target.ActorObjectName.IsNone() || Target.ComponentObjectName.IsNone())
		{
			CameraSetupError = TEXT("目标缺少唯一实体/精确组件绑定"); return;
		}
		Entities.Add(Target.EntityID); Bindings.Add(Binding);
		USkeletalMeshComponent* Mesh = FindExactTarget(GetWorld(), Target, CameraSetupError);
		if (!Mesh) return;
		FFutsalPose17MeshIdentity CurrentIdentity;
		if (!UFutsalPose17Library::DescribeVisualMesh(Mesh, CurrentIdentity, CameraSetupError)) return;
		if (bUseGpuRenderCpuLbsForDiagnostic && (!UFutsalPose17Library::ValidateGPUVisualLBS(Mesh, CameraSetupError)
			|| (Target.DiagnosticVisualMeshOverride && !bAnyGPUOverride)))
		{
			if (CameraSetupError.IsEmpty()) CameraSetupError = TEXT("GPU/LBS mesh override必须使用明确角色组合scope"); return;
		}
		if (bPrepareCPUForDiagnostic)
		{
			FFutsalPose17CPUState CurrentCPUState;
			if (!UFutsalPose17Library::GetVisualSamplingState(Mesh, CurrentCPUState, CameraSetupError)) return;
		}
		USkeletalMesh* Asset = Target.DiagnosticVisualMeshOverride ? Target.DiagnosticVisualMeshOverride.Get() : Mesh->GetSkeletalMeshAsset();
		if (bApplySeededKitForDiagnostic)
		{
			if (!UFutsalPose17KitLibrary::ValidateSeededKitAssets(Target.SeededJerseyMaterial, Target.SeededShortsMaterial,
				Target.SeededKitSetID, CameraSetupError)) return;
			TArray<FName> MaterialSlots;
			for (const auto& Material : Asset->GetMaterials()) MaterialSlots.Add(Material.MaterialSlotName);
			int32 JerseySlot = INDEX_NONE, ShortsSlot = INDEX_NONE;
			if (!UFutsalPose17KitLibrary::ResolveSemanticKitSlots(MaterialSlots, JerseySlot, ShortsSlot, CameraSetupError)) return;
		}
		else if (Target.SeededJerseyMaterial || Target.SeededShortsMaterial || !Target.SeededKitSetID.IsEmpty())
		{
			CameraSetupError = TEXT("服装字段存在但没有原seed服装opt-in，拒绝静默忽略"); return;
		}
		if (bJointGPUOverride)
		{
			const TCHAR* ExpectedAsset = JointExpectedAsset(Target.EntityID);
			if (!ExpectedAsset || Target.ComponentObjectName!=TEXT("MPFBVisual") || Target.ExpectedIdentity.AssetPath!=ExpectedAsset
				|| Asset->GetPathName()!=ExpectedAsset || (!IsCalibrationAsset(Mesh->GetSkeletalMeshAsset()->GetPathName()) && Mesh->GetSkeletalMeshAsset()->GetPathName()!=OriginalVisualAsset)
				|| ((FString(ExpectedAsset)==OriginalVisualAsset) == (Target.DiagnosticVisualMeshOverride!=nullptr)))
			{
				CameraSetupError = TEXT("联合诊断必须十个固定实体/生产网格/manifest精确绑定；003不override，其他八个必须override"); return;
			}
			// 同mesh的003目标也必须只读通过共享骨架/AnimBP/material门禁；此调用不执行切换。
			if (!UFutsalPose17Library::ValidateDiagnosticVisualOverride(Mesh, Asset, Target.ExpectedIdentity, CameraSetupError)) return;
		}
		if (!UFutsalPose17Library::ValidatePose17AssetBinding(Asset, Target.ExpectedIdentity, Target.HeadAnchors,
			Target.ManifestSHA256, CameraSetupError)) return;
		if (Target.DiagnosticVisualMeshOverride)
		{
			++OverrideCount;
			if (!bAllowPIEVisualMeshOverride || (!bAnyGPUOverride && DiagnosticScope != TEXT("pose17_character_calibration"))
				|| (!bAnyGPUOverride && !bPrepareCPUForDiagnostic) || !bHideDriverForDiagnostic
				|| MinimumOverrideWarmupFrames < 8 || MinimumOverrideWarmupFrames > 120)
			{
				CameraSetupError = TEXT("新角色override仅允许明确逐角色PIE校准scope/opt-in/CPU/driver及8..120帧warmup"); return;
			}
			if (!UFutsalPose17Library::ValidateDiagnosticVisualOverride(Mesh, Asset, Target.ExpectedIdentity, CameraSetupError)) return;
			if (bCombinedGPUOverride && (!IsCalibrationAsset(Asset->GetPathName())
				|| Mesh->GetSkeletalMeshAsset()->GetPathName()!=TEXT("/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003.MPFB_Player_003")))
			{
				CameraSetupError = TEXT("GPU/LBS角色组合仅允许精确原003到单白名单004..009资产"); return;
			}
		}
	}
	if ((bAllowPIEVisualMeshOverride && OverrideCount != (bJointGPUOverride ? 8 : 1)) || OverrideCount > (bJointGPUOverride ? 8 : 1)
		|| (DiagnosticScope == TEXT("pose17_gpu_render_cpu_lbs_character_calibration") && !bCombinedGPUOverride)
		|| (DiagnosticScope == TEXT("pose17_gpu_render_cpu_lbs_joint_diagnostic") && !bJointGPUOverride))
	{
		CameraSetupError = TEXT("当前阶段仅允许一次一个角色override，不自动批量切换"); return;
	}
	for (const auto& Target : Targets)
	{
		if (!Target.DiagnosticVisualMeshOverride) continue;
		USkeletalMeshComponent* Mesh = FindExactTarget(GetWorld(), Target, CameraSetupError);
		FFutsalPose17VisualMeshState Previous;
		FFutsalPose17VisualOverrideEvidence Evidence;
		const bool bApplied = Mesh && UFutsalPose17Library::ApplyDiagnosticVisualOverride(Mesh, Target.DiagnosticVisualMeshOverride,
			Target.ExpectedIdentity, Previous, Evidence, CameraSetupError);
		// 即使apply后续读回失败也保存快照和partial证据，必须尝试恢复。
		if (Previous.bMutationStarted) PreviousVisualStates.Add(Previous);
		VisualOverrideEvidence.Add(Evidence);
		if (!bApplied) { RestoreVisualOverrides(); return; }
		if (bAnyGPUOverride)
		{
			auto& AppliedEvidence = VisualOverrideEvidence.Last();
			AppliedEvidence.bGpuLbsValidationAttempted = true;
			AppliedEvidence.bGpuLbsValidationSucceeded = UFutsalPose17Library::ValidateGPUVisualLBS(Mesh,
				AppliedEvidence.GpuLbsValidationError, &AppliedEvidence.GpuLbsEligibilityAfterOverride);
			if (!AppliedEvidence.bGpuLbsValidationSucceeded)
			{
				CameraSetupError = AppliedEvidence.GpuLbsValidationError;
				RestoreVisualOverrides(); return;
			}
		}
	}
	// 模型override会清空材质；必须全部完成后再套服装，且先于GPU/LBS准备与预热。
	if (bApplySeededKitForDiagnostic)
	{
		for (const auto& Target : Targets)
		{
			USkeletalMeshComponent* Mesh = FindExactTarget(GetWorld(), Target, CameraSetupError);
			FFutsalPose17KitState Previous;
			FFutsalPose17KitEvidence Evidence;
			const bool bApplied = UFutsalPose17KitLibrary::ApplySeededKit(Mesh, Target.SeededJerseyMaterial,
				Target.SeededShortsMaterial, Target.SeededKitSetID, SeededAppearanceFingerprint, Previous, Evidence, CameraSetupError);
			if (Previous.bMutationStarted) PreviousKitStates.Add(Previous);
			if (bApplied) Evidence.bGpuLbsEligibleAfterKit = UFutsalPose17Library::ValidateGPUVisualLBS(Mesh, CameraSetupError);
			SeededKitEvidence.Add(Evidence);
			if (!bApplied || !Evidence.bGpuLbsEligibleAfterKit) { RestoreVisualOverrides(); return; }
		}
	}
	for (const auto& Previous : PreviousCameraStates)
	{
		Previous.Component->PostProcessSettings.bOverride_MotionBlurAmount = true;
		Previous.Component->PostProcessSettings.MotionBlurAmount = 0;
		Previous.Component->PostProcessBlendWeight = 1;
	}
}

void UFutsalPose17MRQPass::TeardownForPipelineImpl(UMoviePipeline* InPipeline)
{
	// Setup失败/没有进入shot时同样需要恢复自有partial状态并写失败收据。
	if (!PreparedMeshes.IsEmpty() || !PreparedGPUMeshes.IsEmpty() || !PreviousVisualStates.IsEmpty()
		|| !PreviousKitStates.IsEmpty() || !PreviousDriverStates.IsEmpty()) TeardownImpl();
	bCameraStateRestored = true;
	for (const auto& Previous : PreviousCameraStates)
	{
		if (!IsValid(Previous.Component)) { bCameraStateRestored = false; RestoreErrors.Add(TEXT("PIE相机已销毁，无法核验恢复")); continue; }
		Previous.Component->PostProcessSettings = Previous.PostProcess;
		Previous.Component->PostProcessBlendWeight = Previous.BlendWeight;
	}
	PreviousCameraStates.Reset();
	PersistNativeReceipt();
}

void UFutsalPose17MRQPass::PersistNativeReceipt()
{
	ReceiptWriteError.Reset();
	const FString AllowedRoot = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Pose17Development/smoke"));
	const FString Filename = FPaths::ConvertRelativePathToFull(DiagnosticReceiptFile);
	if (DiagnosticReceiptFile.IsEmpty() || !FPaths::IsUnderDirectory(Filename, AllowedRoot)
		|| IFileManager::Get().FileExists(*Filename) || !IFileManager::Get().DirectoryExists(*FPaths::GetPath(Filename)))
	{
		ReceiptWriteError = TEXT("native收据路径越界、不存在父目录或已存在，拒绝覆盖");
		UE_LOG(LogTemp, Error, TEXT("Pose17 receipt: %s"), *ReceiptWriteError); return;
	}
	TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
	Object->SetStringField(TEXT("schema"), TEXT("futsalmot_pose17_native_receipt_v1"));
	Object->SetStringField(TEXT("lifecycle_stage"), TEXT("pipeline_teardown_before_PIE_cleanup"));
	Object->SetStringField(TEXT("setup_error"), SetupError);
	Object->SetBoolField(TEXT("camera_state_restored"), bCameraStateRestored);
	Object->SetBoolField(TEXT("streaming_state_restart_required"), bStreamingStateRestartRequired);
	Object->SetBoolField(TEXT("record_limit_reached"), bRecordLimitReached);
	Object->SetBoolField(TEXT("MRQ_sync_verified"), false);
	Object->SetBoolField(TEXT("visual_mesh_override_requested"), bAllowPIEVisualMeshOverride);
	Object->SetStringField(TEXT("diagnostic_scope"), DiagnosticScope);
	Object->SetStringField(TEXT("pipeline_setup_error"), CameraSetupError);
	Object->SetStringField(TEXT("pose_sampling_path"), bUseGpuRenderCpuLbsForDiagnostic ? TEXT("gpu_render_cpu_lbs") : TEXT("cpu_skin_cache"));
	Object->SetBoolField(TEXT("gpu_lbs_diagnostic_requested"), bUseGpuRenderCpuLbsForDiagnostic);
	Object->SetNumberField(TEXT("gpu_lbs_prepared_engine_frame"), GPUPreparedEngineFrame);
	TArray<TSharedPtr<FJsonValue>> Overrides;
	for (const auto& Evidence : VisualOverrideEvidence)
		Overrides.Add(MakeShared<FJsonValueObject>(FJsonObjectConverter::UStructToJsonObject(Evidence)));
	Object->SetArrayField(TEXT("visual_mesh_overrides"), Overrides);
	Object->SetBoolField(TEXT("seeded_kit_requested"), bApplySeededKitForDiagnostic);
	Object->SetStringField(TEXT("seeded_appearance_fingerprint"), SeededAppearanceFingerprint);
	TArray<TSharedPtr<FJsonValue>> Kits;
	for (const auto& Evidence : SeededKitEvidence)
		Kits.Add(MakeShared<FJsonValueObject>(FJsonObjectConverter::UStructToJsonObject(Evidence)));
	Object->SetArrayField(TEXT("seeded_kit_bindings"), Kits);
	TArray<TSharedPtr<FJsonValue>> Errors, Rows;
	for (const FString& Error : RestoreErrors) Errors.Add(MakeShared<FJsonValueString>(Error));
	for (const auto& Record : Records)
	{
		TSharedPtr<FJsonObject> Row = FJsonObjectConverter::UStructToJsonObject(Record);
		if (!Row.IsValid()) { ReceiptWriteError = TEXT("native记录UStruct序列化失败"); break; }
		// 显式编码FTransform，避免UStruct ExportText/注册converter差异让CPU工具猜格式。
		Row->SetStringField(TEXT("worldTransformEncoding"), TEXT("ue_transform_translation_cm_quat_xyzw_scale_xyz_v1"));
		Row->SetObjectField(TEXT("actorWorldTransformUECm"), ExplicitTransformJSON(Record.ActorWorldTransformUECm));
		Row->SetObjectField(TEXT("visualWorldTransformUECm"), ExplicitTransformJSON(Record.VisualWorldTransformUECm));
		TSharedPtr<FJsonObject> Sample = Row->GetObjectField(TEXT("sample"));
		TArray<TSharedPtr<FJsonValue>> BoneTransforms;
		for (const auto& Transform : Record.Sample.BoneSpaceBaseTransformsUECm)
			BoneTransforms.Add(MakeShared<FJsonValueObject>(ExplicitTransformJSON(Transform)));
		Sample->SetArrayField(TEXT("boneSpaceBaseTransformsUECm"), BoneTransforms);
		Rows.Add(MakeShared<FJsonValueObject>(Row));
	}
	Object->SetArrayField(TEXT("restore_errors"), Errors);
	Object->SetArrayField(TEXT("records"), Rows);
	FString Text;
	if (!ReceiptWriteError.IsEmpty() || !FJsonSerializer::Serialize(Object, TJsonWriterFactory<>::Create(&Text))
		|| !FFileHelper::SaveStringToFile(Text, *Filename, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
			&IFileManager::Get(), FILEWRITE_NoReplaceExisting))
	{
		if (ReceiptWriteError.IsEmpty()) ReceiptWriteError = TEXT("native收据写入失败");
		UE_LOG(LogTemp, Error, TEXT("Pose17 receipt: %s"), *ReceiptWriteError);
	}
}

void UFutsalPose17MRQPass::SetupImpl(const MoviePipeline::FMoviePipelineRenderPassInitSettings& InPassInitSettings)
{
	Records.Reset(); SetupError.Reset(); bRecordLimitReached = false;
	PreparedMeshes.Reset(); PreviousCPUStates.Reset(); PreviousDriverStates.Reset();
	PreparedGPUMeshes.Reset(); PreviousGPULODStates.Reset();
	if (!CameraSetupError.IsEmpty()) { SetupError = CameraSetupError; return; }
	if (Targets.IsEmpty() || MaxRecords < 1 || MaxRecords > 4096)
	{
		SetupError = TEXT("诊断 pass 必须显式配置目标和1..4096条记录上限"); return;
	}
	TSet<FString> Entities;
	TSet<FString> ComponentBindings;
	for (const auto& Target : Targets)
	{
		if (Target.EntityID.IsEmpty() || Entities.Contains(Target.EntityID)
			|| Target.ActorObjectName.IsNone() || Target.ComponentObjectName.IsNone())
		{
			SetupError = TEXT("目标缺少唯一实体或精确 Actor/Component 对象名"); return;
		}
		Entities.Add(Target.EntityID);
		const FString Binding = Target.ActorObjectName.ToString() + TEXT(":") + Target.ComponentObjectName.ToString();
		if (ComponentBindings.Contains(Binding)) { SetupError = TEXT("两个实体不能绑定同一实际组件"); return; }
		ComponentBindings.Add(Binding);
	}
	if (!bPrepareCPUForDiagnostic && !bHideDriverForDiagnostic) return;
	if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE)
	{
		SetupError = TEXT("诊断CPU准备/隐藏driver仅允许PIE实例"); return;
	}
	for (const auto& Target : Targets)
	{
		USkeletalMeshComponent* Mesh = FindExactTarget(GetWorld(), Target, SetupError);
		if (!Mesh) { TeardownImpl(); return; }
		if (bHideDriverForDiagnostic)
		{
			TInlineComponentArray<USkeletalMeshComponent*> Components(Mesh->GetOwner());
			for (USkeletalMeshComponent* Driver : Components)
			{
				if (Driver != Mesh && Driver->GetFName() == TEXT("CharacterMesh0"))
				{
					FFutsalPose17DriverState& Previous = PreviousDriverStates.AddDefaulted_GetRef();
					Previous.Component = Driver; Previous.bVisible = Driver->IsVisible();
					Previous.bHiddenInGame = Driver->bHiddenInGame;
					Previous.AnimationTickOption = static_cast<uint8>(Driver->VisibilityBasedAnimTickOption);
					Driver->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
					Driver->SetVisibility(false, false); Driver->SetHiddenInGame(true, false);
				}
			}
		}
		if (bPrepareCPUForDiagnostic)
		{
			FFutsalPose17CPUState Previous;
			if (!UFutsalPose17Library::PrepareVisualCPUSampling(Mesh, Previous, SetupError)) { TeardownImpl(); return; }
			PreparedMeshes.Add(Mesh); PreviousCPUStates.Add(Previous);
		}
		if (bUseGpuRenderCpuLbsForDiagnostic)
		{
			FFutsalPose17CPUState Previous;
			if (!UFutsalPose17Library::PrepareGPUVisualLBS(Mesh, Previous, SetupError)) { TeardownImpl(); return; }
			PreparedGPUMeshes.Add(Mesh); PreviousGPULODStates.Add(Previous);
		}
	}
	if (bUseGpuRenderCpuLbsForDiagnostic) GPUPreparedEngineFrame = static_cast<int64>(GFrameCounter);
}

void UFutsalPose17MRQPass::OnFrameStartImpl()
{
	FrameMeshes.Reset(); FramePoseRevisions.Reset(); FrameCacheError.Reset(); CacheFenceEngineFrame = -1;
	if (!SetupError.IsEmpty() || Records.Num() >= MaxRecords || !GetWorld() || !GetPipeline()) return;
	const auto& State = GetPipeline()->GetOutputState();
	if (State.bDiscardRenderResult || State.bSkipRendering || State.OutputFrameNumber < 0) return;
	for (const auto& Previous : PreviousVisualStates)
	{
		USkeletalMeshComponent* Mesh = Previous.Component;
		// 原默认材质已在模型override时严格核验。服装事务会合法新增两个override，
		// 此处改为逐slot核对其快照/球衣/短裤；其他材质、mesh及动画仍必须全部匹配。
		bool bMaterialsStable = IsValid(Mesh) && Mesh->GetNumOverrideMaterials() == 0;
		if (bApplySeededKitForDiagnostic)
		{
			const auto* KitState = PreviousKitStates.FindByPredicate([Mesh](const auto& Row) { return Row.Component == Mesh; });
			FString KitError;
			bMaterialsStable = KitState && UFutsalPose17KitLibrary::VerifySeededKit(*KitState, KitError);
			if (!bMaterialsStable) { FrameCacheError = KitError.IsEmpty() ? TEXT("预热后缺少精确服装事务") : KitError; return; }
		}
		if (!IsValid(Mesh) || Mesh->GetSkeletalMeshAsset() != Previous.AppliedMesh
			|| Mesh->GetAnimClass() != Previous.AnimationClass || Mesh->GetAnimInstance() != Previous.AnimationInstance
			|| Mesh->LeaderPoseComponent != Previous.Leader || Mesh->GetAttachParent() != Previous.AttachParent.Get()
			|| !bMaterialsStable)
		{
			FrameCacheError = TEXT("角色override后的mesh/共享动画/材质绑定在warmup后发生变化"); return;
		}
	}
	TArray<USkeletalMeshComponent*> Meshes;
	for (const auto& Target : Targets)
	{
		USkeletalMeshComponent* Mesh = FindExactTarget(GetWorld(), Target, FrameCacheError);
		if (!Mesh) return;
		Meshes.Add(Mesh); FrameMeshes.Add(Mesh);
	}
	// UE5.8 RenderFrame 先逐pass调用全部OnFrameStart，再进入所有RenderSample。
	// 在这里完成cache更新，避免metadata pass排在RGB pass之后才发送新骨骼数据。
	const bool bSynchronized = bUseGpuRenderCpuLbsForDiagnostic
		? UFutsalPose17Library::SynchronizeGPUVisualLBS(Meshes, FrameCacheError)
		: UFutsalPose17Library::SynchronizeVisualCPUCaches(Meshes, FrameCacheError);
	if (!bSynchronized) return;
	CacheFenceEngineFrame = static_cast<int64>(GFrameCounter);
	for (USkeletalMeshComponent* Mesh : Meshes) FramePoseRevisions.Add(Mesh->GetBoneTransformRevisionNumber());
}

void UFutsalPose17MRQPass::TeardownImpl()
{
	for (int32 Index = PreparedGPUMeshes.Num()-1; Index >= 0; --Index)
	{
		FString Error;
		if (!UFutsalPose17Library::RestoreGPUVisualLBS(PreparedGPUMeshes[Index], PreviousGPULODStates[Index], Error)) RestoreErrors.Add(Error);
		if (!IsValid(PreparedGPUMeshes[Index]) || !PreparedGPUMeshes[Index]->GetSkeletalMeshAsset()
			|| PreparedGPUMeshes[Index]->GetSkeletalMeshAsset()->IsStreamable() != PreviousGPULODStates[Index].bAssetWasStreamable)
			bStreamingStateRestartRequired = true;
	}
	for (int32 Index = PreparedMeshes.Num() - 1; Index >= 0; --Index)
	{
		bool bStreamingMatched = false;
		FString Error;
		if (!UFutsalPose17Library::RestoreVisualCPUSampling(PreparedMeshes[Index], PreviousCPUStates[Index], bStreamingMatched, Error))
			RestoreErrors.Add(Error);
		if (!bStreamingMatched) bStreamingStateRestartRequired = true;
	}
	// CPU恢复以新mesh身份为约束，必须先完成，再恢复旧mesh及原override材质。
	RestoreVisualOverrides();
	for (const auto& Previous : PreviousDriverStates)
	{
		if (!IsValid(Previous.Component)) { RestoreErrors.Add(TEXT("PIE driver已销毁，不能核验逐组件恢复")); continue; }
		Previous.Component->VisibilityBasedAnimTickOption = static_cast<EVisibilityBasedAnimTickOption>(Previous.AnimationTickOption);
		Previous.Component->SetVisibility(Previous.bVisible, false);
		Previous.Component->SetHiddenInGame(Previous.bHiddenInGame, false);
		if (Previous.Component->IsVisible() != Previous.bVisible || Previous.Component->bHiddenInGame != Previous.bHiddenInGame
			|| static_cast<uint8>(Previous.Component->VisibilityBasedAnimTickOption) != Previous.AnimationTickOption)
			RestoreErrors.Add(TEXT("PIE driver恢复后读回不一致"));
	}
	PreparedMeshes.Reset(); PreviousCPUStates.Reset(); PreviousDriverStates.Reset();
	PreparedGPUMeshes.Reset(); PreviousGPULODStates.Reset();
	FrameMeshes.Reset(); FramePoseRevisions.Reset(); CacheFenceEngineFrame = -1;
}

void UFutsalPose17MRQPass::RestoreVisualOverrides()
{
	RestoreSeededKits();
	for (int32 Index = PreviousVisualStates.Num()-1; Index >= 0; --Index)
	{
		FString Error;
		const FString Path = PreviousVisualStates[Index].Component ? PreviousVisualStates[Index].Component->GetPathName() : TEXT("");
		FFutsalPose17VisualOverrideEvidence* Evidence = VisualOverrideEvidence.FindByPredicate(
			[&Path](const FFutsalPose17VisualOverrideEvidence& Row) { return Row.ComponentPath == Path; });
		if (!Evidence) { RestoreErrors.Add(TEXT("角色override缺少对应恢复证据")); continue; }
		if (!UFutsalPose17Library::RestoreDiagnosticVisualOverride(PreviousVisualStates[Index], *Evidence, Error)) RestoreErrors.Add(Error);
		if (!Evidence->bStreamingStateMatched) bStreamingStateRestartRequired = true;
	}
	PreviousVisualStates.Reset();
}

void UFutsalPose17MRQPass::RestoreSeededKits()
{
	for (int32 Index = PreviousKitStates.Num()-1; Index >= 0; --Index)
	{
		const auto& Previous = PreviousKitStates[Index];
		const FString Path = Previous.Component ? Previous.Component->GetPathName() : TEXT("");
		auto* Evidence = SeededKitEvidence.FindByPredicate([&Path](const auto& Row) { return Row.ComponentPath == Path; });
		FString Error;
		if (!Evidence || !UFutsalPose17KitLibrary::RestoreSeededKit(Previous, *Evidence, Error))
			RestoreErrors.Add(Evidence ? Error : TEXT("服装恢复缺少对应真实apply证据"));
	}
	PreviousKitStates.Reset();
}

void UFutsalPose17MRQPass::RenderSample_GameThreadImpl(const FMoviePipelineRenderPassMetrics& State)
{
	if (!SetupError.IsEmpty() || State.bDiscardResult || State.OutputState.bSkipRendering || State.OutputState.OutputFrameNumber < 0) return;
	if (!GetWorld()) { SetupError = TEXT("MRQ pass 没有有效 World，拒绝猜测当前 Editor 世界"); return; }
	FString CacheError = FrameCacheError;
	if (CacheError.IsEmpty() && (CacheFenceEngineFrame != static_cast<int64>(GFrameCounter) || FramePoseRevisions.Num() != Targets.Num()))
		CacheError = TEXT("当前MRQ sample没有本引擎帧pre-pass CPUcache fence证据");
	for (int32 Index = 0; Index < FramePoseRevisions.Num() && CacheError.IsEmpty(); ++Index)
		if (!IsValid(FrameMeshes[Index]) || FramePoseRevisions[Index] != FrameMeshes[Index]->GetBoneTransformRevisionNumber())
			CacheError = TEXT("pre-pass fence与采样之间Pose revision变化");
	for (const auto& Target : Targets)
	{
		if (Records.Num() >= MaxRecords) { bRecordLimitReached = true; return; }
		FFutsalPose17MRQRecord& Record = Records.AddDefaulted_GetRef();
		Record.EntityID = Target.EntityID;
		if (bApplySeededKitForDiagnostic)
		{
			USkeletalMeshComponent* Mesh = FindExactTarget(GetWorld(), Target, SetupError);
			const auto* Previous = PreviousKitStates.FindByPredicate([Mesh](const auto& Row) { return Row.Component == Mesh; });
			FString KitError;
			Record.bSeededKitReadbackSucceeded = Previous && UFutsalPose17KitLibrary::VerifySeededKit(*Previous, KitError);
			if (!Record.bSeededKitReadbackSucceeded)
			{
				SetupError = KitError.IsEmpty() ? TEXT("实际输出帧缺少原seed服装状态") : KitError;
				Record.Error = SetupError; return;
			}
		}
		Record.OutputFrame = State.OutputState.OutputFrameNumber;
		Record.SequenceSourceFrame = State.OutputState.SourceFrameNumber;
		Record.ShotIndex = State.OutputState.ShotIndex;
		Record.CameraIndex = State.OutputState.CameraIndex;
		Record.CameraName = State.OutputState.CameraName;
		Record.TemporalSampleIndex = State.TemporalSampleIndex;
		Record.SpatialSampleIndex = State.SpatialSampleIndex;
		Record.HookEngineFrame = static_cast<int64>(GFrameCounter);
		Record.MRQWorldSeconds = State.OutputState.TimeData.WorldSeconds;
		Record.TemporalSampleCount = State.TemporalSampleCount;
		Record.SpatialSampleCount = State.SpatialSampleCount;
		Record.MotionBlurFraction = State.OutputState.TimeData.MotionBlurFraction;
		Record.bCacheFenceCompletedThisEngineFrame = CacheError.IsEmpty();
		Record.PoseFenceMethod = bUseGpuRenderCpuLbsForDiagnostic ? TEXT("gpu_dynamic_data_endframe_tasks_finished_render_commands_flush")
			: TEXT("cpu_skin_cache_dynamic_data_render_commands_flush");
		Record.bEndFrameUpdateTasksFinished = bUseGpuRenderCpuLbsForDiagnostic && CacheError.IsEmpty();
		Record.CameraWorldLocationM = State.FrameInfo.CurrViewLocation * 0.01;
		const FRotationMatrix CameraRotation(State.FrameInfo.CurrViewRotation);
		Record.CameraForward = CameraRotation.GetScaledAxis(EAxis::X);
		Record.CameraRight = CameraRotation.GetScaledAxis(EAxis::Y);
		Record.CameraUp = CameraRotation.GetScaledAxis(EAxis::Z);
		Record.ProjectionJitter = State.ProjectionMatrixJitterAmount;
		Record.ImageSize = State.BackbufferSize;
		if (PreviousCameraStates.Num() == 1 && IsValid(PreviousCameraStates[0].Component))
		{
			FMinimalViewInfo View;
			PreviousCameraStates[0].Component->GetCameraView(0, View);
			Record.CameraHorizontalFOVDegrees = View.FOV;
			Record.CameraAspectRatio = View.AspectRatio;
			Record.bCameraConstrainAspectRatio = View.bConstrainAspectRatio;
			Record.CameraAspectRatioAxisConstraint = FString::FromInt(static_cast<int32>(View.AspectRatioAxisConstraint.Get(EAspectRatioAxisConstraint::AspectRatio_MaintainXFOV)));
			Record.OffCenterProjectionOffset = View.OffCenterProjectionOffset;
			if (const ACineCameraActor* CineCamera = Cast<ACineCameraActor>(PreviousCameraStates[0].Component->GetOwner()))
			{
				Record.bCineCameraLookAtStateObserved = true;
				Record.bCineCameraLookAtEnabled = CineCamera->LookatTrackingSettings.bEnableLookAtTracking;
			}
		}
		if (!CacheError.IsEmpty()) { Record.Error = CacheError; continue; }
		if (State.TemporalSampleCount != 1 || State.SpatialSampleCount != 1 || State.TileCounts != FIntPoint(1, 1)
			|| !FMath::IsNearlyZero(State.OutputState.TimeData.MotionBlurFraction))
		{
			Record.Error = TEXT("当前最小诊断仅允许 temporal=1/spatial=1/tile=1/motionblur=0"); continue;
		}
		USkeletalMeshComponent* Mesh = FindExactTarget(GetWorld(), Target, Record.Error);
		if (!Mesh) continue;
		Record.ActorWorldTransformUECm = Mesh->GetOwner()->GetActorTransform();
		Record.VisualWorldTransformUECm = Mesh->GetComponentTransform();
		if (bUseGpuRenderCpuLbsForDiagnostic)
		{
			Record.GpuLbsWarmupEngineFramesObserved = static_cast<int64>(GFrameCounter)-GPUPreparedEngineFrame;
			if (GPUPreparedEngineFrame < 0 || Record.GpuLbsWarmupEngineFramesObserved < MinimumGpuLbsWarmupFrames)
			{
				Record.Error = TEXT("新GPU/LBS实际warmup未达到预注册门槛"); continue;
			}
		}
		if (Target.DiagnosticVisualMeshOverride)
		{
			const auto* Evidence = VisualOverrideEvidence.FindByPredicate([&Mesh](const FFutsalPose17VisualOverrideEvidence& Row)
				{ return Row.ComponentPath == Mesh->GetPathName(); });
			if (!Evidence || !Evidence->bApplySucceeded) { Record.Error = TEXT("缺少已成功角色override证据"); continue; }
			Record.OverrideWarmupEngineFramesObserved = static_cast<int64>(GFrameCounter)-Evidence->AppliedEngineFrame;
			if (Record.OverrideWarmupEngineFramesObserved < MinimumOverrideWarmupFrames)
			{
				Record.Error = TEXT("新mesh没有达到显式最小warmup引擎帧数，拒绝当作已稳定Pose"); continue;
			}
		}
		// 不允许昂贵接口隐式重评动画；CPU 缓存未准备即记录失败。
		Record.bSampleSucceeded = bUseGpuRenderCpuLbsForDiagnostic
			? UFutsalPose17Library::SampleVisualPose17GPULBS(Mesh, Target.ExpectedIdentity, Target.HeadAnchors, Target.ManifestSHA256, Record.Sample, Record.Error)
			: UFutsalPose17Library::SampleVisualPose17(Mesh, Target.ExpectedIdentity, Target.HeadAnchors, Target.ManifestSHA256, false, Record.Sample, Record.Error);
		// 这里的 State 是真实 MRQ SampleState，但尚未与落盘 RGB/mask 验证对应。
		Record.Sample.bMRQSynchronizationVerified = false;
	}
}
