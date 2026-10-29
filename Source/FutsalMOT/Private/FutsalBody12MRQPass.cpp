#include "FutsalBody12MRQPass.h"
#include "CoreGlobals.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "CineCameraComponent.h"
#include "MoviePipeline.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"

namespace
{
const TCHAR* Bones[] = {TEXT("upperarm_l"),TEXT("upperarm_r"),TEXT("lowerarm_l"),TEXT("lowerarm_r"),
	TEXT("hand_l"),TEXT("hand_r"),TEXT("thigh_l"),TEXT("thigh_r"),TEXT("calf_l"),TEXT("calf_r"),TEXT("foot_l"),TEXT("foot_r")};
TArray<TSharedPtr<FJsonValue>> Vec(const FVector& V)
{
	return {MakeShared<FJsonValueNumber>(V.X),MakeShared<FJsonValueNumber>(V.Y),MakeShared<FJsonValueNumber>(V.Z)};
}
FString Encode(const TSharedRef<FJsonObject>& Object)
{
	FString Text;
	FJsonSerializer::Serialize(Object,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));
	return Text;
}
}

void UFutsalBody12MRQPass::SetupForPipelineImpl(UMoviePipeline* InPipeline)
{
	CaptureError.Reset(); WrittenFrames=0; bRestored=false;
	FString Root=FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()/TEXT("SingleSeed"));
	FString Path=FPaths::ConvertRelativePathToFull(MetadataFile);
	FPaths::NormalizeDirectoryName(Root); FPaths::NormalizeFilename(Path);
	if (!GetWorld() || GetWorld()->WorldType!=EWorldType::PIE || Targets.Num()!=10 || ExpectedFrames<1
		|| !FPaths::IsUnderDirectory(Path,Root) || FPaths::GetExtension(Path)!=TEXT("jsonl")
		|| IFileManager::Get().FileExists(*Path) || IFileManager::Get().FileExists(*(Path+TEXT(".complete.json"))))
	{
		CaptureError=TEXT("Body12需要PIE、十个目标、正帧数和Saved/SingleSeed内全新JSONL"); return;
	}
	MetadataFile=Path;
	TSet<FString> Entities, Bindings;
	for (const auto& Target:Targets)
	{
		AActor* Actor=nullptr; int32 Count=0;
		for (TActorIterator<AActor> It(GetWorld());It;++It)
			if (It->GetFName()==Target.ActorObjectName) {Actor=*It;++Count;}
		USkeletalMeshComponent* Mesh=nullptr; int32 MeshCount=0;
		if (Count==1)
		{
			TInlineComponentArray<USkeletalMeshComponent*> Components(Actor);
			for (USkeletalMeshComponent* Candidate:Components)
				if (Candidate->GetFName()==Target.ComponentObjectName) {Mesh=Candidate;++MeshCount;}
		}
		const FString Binding=Target.ActorObjectName.ToString()+TEXT(":")+Target.ComponentObjectName.ToString();
		if (!Mesh || MeshCount!=1 || Target.ComponentObjectName!=TEXT("MPFBVisual")
			|| Entities.Contains(Target.EntityID) || Bindings.Contains(Binding)
			|| !Mesh->GetSkeletalMeshAsset() || Mesh->GetSkeletalMeshAsset()->GetPathName()!=Target.ExpectedIdentity.AssetPath)
		{
			CaptureError=TEXT("Body12实际可见网格/实体绑定不符");return;
		}
		Entities.Add(Target.EntityID); Bindings.Add(Binding);
		for (const TCHAR* Bone:Bones)
			if (Mesh->GetBoneIndex(FName(Bone))==INDEX_NONE) {CaptureError=TEXT("Body12缺少实际骨骼");return;}
		Meshes.Add(Mesh);
	}
	int32 CameraCount=0;
	for (TActorIterator<AActor> It(GetWorld());It;++It)
		if (It->GetFName()==CameraObjectName) {Camera=It->FindComponentByClass<UCameraComponent>();++CameraCount;}
	if (CameraCount!=1 || !Camera) {CaptureError=TEXT("Body12相机不唯一");return;}
	PreviousPostProcess=Camera->PostProcessSettings; PreviousBlend=Camera->PostProcessBlendWeight;
	Camera->PostProcessSettings.bOverride_MotionBlurAmount=true; Camera->PostProcessSettings.MotionBlurAmount=0;
	Camera->PostProcessBlendWeight=1; bCameraPrepared=true;
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);
	if (!FFileHelper::SaveStringToFile(TEXT(""),*Path,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
		CaptureError=TEXT("Body12无法创建元数据文件");
}

void UFutsalBody12MRQPass::SetupImpl(const MoviePipeline::FMoviePipelineRenderPassInitSettings& Init)
{
	if (!CaptureError.IsEmpty()) return;
	for (USkeletalMeshComponent* Mesh:Meshes)
	{
		TInlineComponentArray<USkeletalMeshComponent*> Components(Mesh->GetOwner());
		for (auto* Driver:Components)
			if (Driver!=Mesh && Driver->GetFName()==TEXT("CharacterMesh0"))
			{
				auto& Saved=PreviousDrivers.AddDefaulted_GetRef(); Saved.Component=Driver;
				Saved.bVisible=Driver->IsVisible(); Saved.bHiddenInGame=Driver->bHiddenInGame;
				Saved.AnimationTickOption=static_cast<uint8>(Driver->VisibilityBasedAnimTickOption);
				Driver->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
				Driver->SetVisibility(false,false);Driver->SetHiddenInGame(true,false);
			}
		FFutsalPose17CPUState Saved;
		if (!UFutsalPose17Library::PrepareGPUVisualLBS(Mesh,Saved,CaptureError)) return;
		PreviousLOD.Add(Saved);
	}
}

void UFutsalBody12MRQPass::OnFrameStartImpl()
{
	FenceFrame=-1;Revisions.Reset();
	if (!CaptureError.IsEmpty() || !GetPipeline()) return;
	const auto& State=GetPipeline()->GetOutputState();
	if (State.bDiscardRenderResult || State.bSkipRendering || State.OutputFrameNumber<0) return;
	TArray<USkeletalMeshComponent*> Raw;
	for (USkeletalMeshComponent* Mesh:Meshes) Raw.Add(Mesh);
	if (!UFutsalPose17Library::SynchronizeGPUVisualLBS(Raw,CaptureError)) return;
	FenceFrame=static_cast<int64>(GFrameCounter);
	for (USkeletalMeshComponent* Mesh:Meshes) Revisions.Add(Mesh->GetBoneTransformRevisionNumber());
}

void UFutsalBody12MRQPass::RenderSample_GameThreadImpl(const FMoviePipelineRenderPassMetrics& State)
{
	if (!CaptureError.IsEmpty() || State.bDiscardResult || State.OutputState.bSkipRendering || State.OutputState.OutputFrameNumber<0) return;
	if (State.TemporalSampleCount!=1 || State.SpatialSampleCount!=1 || State.TileCounts!=FIntPoint(1,1)
		|| !FMath::IsNearlyZero(State.OutputState.TimeData.MotionBlurFraction)
		|| FenceFrame!=static_cast<int64>(GFrameCounter) || Revisions.Num()!=10 || !Camera
		|| WrittenFrames>=ExpectedFrames)
	{
		CaptureError=TEXT("Body12 MRQ采样/同步/帧数不符");return;
	}
	auto Frame=MakeShared<FJsonObject>();
	Frame->SetStringField(TEXT("schema"),TEXT("futsalmot_body12_native_frame_v1"));
	Frame->SetNumberField(TEXT("output_frame"),State.OutputState.OutputFrameNumber);
	Frame->SetNumberField(TEXT("source_frame"),State.OutputState.SourceFrameNumber);
	Frame->SetNumberField(TEXT("engine_frame"),static_cast<double>(GFrameCounter));
	Frame->SetStringField(TEXT("sampling_method"),TEXT("gpu_render_visible_mesh_bone_origins_endframe_fence_v1"));
	Frame->SetNumberField(TEXT("width"),State.BackbufferSize.X); Frame->SetNumberField(TEXT("height"),State.BackbufferSize.Y);
	Frame->SetArrayField(TEXT("camera_position_m"),Vec(State.FrameInfo.CurrViewLocation*.01));
	const FRotator Rotation=State.FrameInfo.CurrViewRotation;
	Frame->SetArrayField(TEXT("camera_rotation_deg"),Vec(FVector(Rotation.Pitch,Rotation.Yaw,Rotation.Roll)));
	FMinimalViewInfo View;Camera->GetCameraView(0,View);
	Frame->SetNumberField(TEXT("horizontal_fov_deg"),View.FOV);
	const auto* Cine=Cast<UCineCameraComponent>(Camera);
	Frame->SetNumberField(TEXT("focal_length_mm"),Cine ? Cine->CurrentFocalLength : 0);
	Frame->SetArrayField(TEXT("projection_jitter"),{MakeShared<FJsonValueNumber>(State.ProjectionMatrixJitterAmount.X),MakeShared<FJsonValueNumber>(State.ProjectionMatrixJitterAmount.Y)});
	TArray<TSharedPtr<FJsonValue>> Players;
	for (int32 Index=0;Index<Meshes.Num();++Index)
	{
		USkeletalMeshComponent* Mesh=Meshes[Index];
		if (!IsValid(Mesh) || Mesh->GetBoneTransformRevisionNumber()!=Revisions[Index]
			|| Mesh->GetSkeletalMeshAsset()->GetPathName()!=Targets[Index].ExpectedIdentity.AssetPath || Mesh->GetCPUSkinningEnabled())
		{
			CaptureError=TEXT("Body12读取期间可见mesh/Pose/GPU模式变化");return;
		}
		auto Player=MakeShared<FJsonObject>();
		Player->SetStringField(TEXT("entity_id"),Targets[Index].EntityID);
		Player->SetStringField(TEXT("mesh_asset"),Mesh->GetSkeletalMeshAsset()->GetPathName());
		Player->SetNumberField(TEXT("pose_revision"),Revisions[Index]);
		TArray<TSharedPtr<FJsonValue>> Points;
		for (const TCHAR* Bone:Bones)
		{
			const FVector Point=Mesh->GetBoneTransform(Mesh->GetBoneIndex(FName(Bone))).GetLocation()*.01;
			if (Point.ContainsNaN()) {CaptureError=TEXT("Body12出现非有限世界坐标");return;}
			auto Vector=MakeShared<FJsonValueArray>(Vec(Point));Points.Add(Vector);
		}
		Player->SetArrayField(TEXT("world_m"),Points);
		Player->SetArrayField(TEXT("bounds_center_m"),Vec(Mesh->Bounds.Origin*.01));
		Player->SetArrayField(TEXT("bounds_extent_m"),Vec(Mesh->Bounds.BoxExtent*.01));
		Player->SetArrayField(TEXT("back_normal_world"),Vec(-Mesh->GetOwner()->GetActorForwardVector()));
		Players.Add(MakeShared<FJsonValueObject>(Player));
	}
	Frame->SetArrayField(TEXT("players"),Players);
	if (!FFileHelper::SaveStringToFile(Encode(Frame)+TEXT("\n"),*MetadataFile,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append))
	{
		CaptureError=TEXT("Body12逐帧落盘失败");return;
	}
	++WrittenFrames;
}

void UFutsalBody12MRQPass::TeardownImpl()
{
	if (bRestored) return;
	TArray<TSharedPtr<FJsonValue>> Errors;
	for (int32 Index=PreviousLOD.Num()-1;Index>=0;--Index)
	{
		FString Error;
		if (!UFutsalPose17Library::RestoreGPUVisualLBS(Meshes[Index],PreviousLOD[Index],Error)) Errors.Add(MakeShared<FJsonValueString>(Error));
	}
	for (const auto& Saved:PreviousDrivers)
	{
		if (!IsValid(Saved.Component)) {Errors.Add(MakeShared<FJsonValueString>(TEXT("Body12 driver提前销毁")));continue;}
		Saved.Component->VisibilityBasedAnimTickOption=static_cast<EVisibilityBasedAnimTickOption>(Saved.AnimationTickOption);
		Saved.Component->SetVisibility(Saved.bVisible,false);Saved.Component->SetHiddenInGame(Saved.bHiddenInGame,false);
	}
	if (bCameraPrepared && IsValid(Camera)) {Camera->PostProcessSettings=PreviousPostProcess;Camera->PostProcessBlendWeight=PreviousBlend;}
	auto Receipt=MakeShared<FJsonObject>();
	Receipt->SetStringField(TEXT("schema"),TEXT("futsalmot_body12_native_complete_v1"));
	Receipt->SetStringField(TEXT("capture_error"),CaptureError);
	Receipt->SetNumberField(TEXT("written_frames"),WrittenFrames);Receipt->SetNumberField(TEXT("expected_frames"),ExpectedFrames);
	Receipt->SetArrayField(TEXT("restore_errors"),Errors);
	Receipt->SetBoolField(TEXT("success"),CaptureError.IsEmpty() && WrittenFrames==ExpectedFrames && Errors.IsEmpty());
	if (!MetadataFile.IsEmpty()) FFileHelper::SaveStringToFile(Encode(Receipt),*(MetadataFile+TEXT(".complete.json")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	Meshes.Reset();PreviousLOD.Reset();PreviousDrivers.Reset();Camera=nullptr;bRestored=true;
}
