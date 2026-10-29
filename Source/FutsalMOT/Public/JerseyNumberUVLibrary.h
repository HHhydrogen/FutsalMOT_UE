#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "JerseyNumberUVLibrary.generated.h"

class USkeletalMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UTexture;
class AActor;
class UStaticMesh;
class UStaticMeshComponent;

/** 球衣号码的独立输入；只包含确定性材质参数，不修改 Actor 或随机状态。 */
USTRUCT(BlueprintType)
struct FUTSALMOT_API FJerseyNumberUVParameters
{

	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Jersey Number")
	int32 Number = 1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Jersey Number")
	int32 EntityMaskID = 32;

	/** R/G/B/A 分别为 u0/v0/u1/v1，必须来自当前网格的 UE 视觉校准。 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Jersey Number")
	FLinearColor UVRect = FLinearColor(0.0f, 0.0f, 1.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Jersey Number")
	FLinearColor InkColor = FLinearColor::White;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Jersey Number")
	bool bFlipU = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FutsalMOT|Jersey Number")
	bool bFlipV = false;
};

/** 最小运行时接口；正式 apply/restore 与号码通道仍由验证后的事务管理。 */
UCLASS()
class FUTSALMOT_API UJerseyNumberUVLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintPure, Category="FutsalMOT|Jersey Number")
	static bool ValidateNumberParameters(const FJerseyNumberUVParameters& Parameters, FString& OutError);

	/** 按实测语义名称查询，拒绝缺失或重复 slot；不能假设索引固定为 3。 */
	UFUNCTION(BlueprintPure, Category="FutsalMOT|Jersey Number")
	static int32 FindUniqueJerseySlot(USkeletalMeshComponent* VisualMesh);

	/** 仅构建独立 MID，保留母材质的布料属性，不设置组件材质或保存资产。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Jersey Number")
	static UMaterialInstanceDynamic* CreateNumberMaterial(
		UMaterialInterface* ParentMaterial,
		UTexture* NumberAtlas,
		UObject* RuntimeOuter,
		const FJerseyNumberUVParameters& Parameters,
		FString& OutError);

	/** 创建同网格蒙皮的号码 CustomDepth 代理；调用方必须先记录恢复快照。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Jersey Number")
	static USkeletalMeshComponent* CreateNumberMaskFollower(
		USkeletalMeshComponent* VisualMesh,
		UMaterialInterface* MaskedNumberMaterial,
		UMaterialInterface* EmptyMaskedMaterial,
		int32 EntityMaskID,
		FString& OutError);

	/** 只删除本接口创建且仍绑定到预期球员的组件，不清理 package dirty flag。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Jersey Number")
	static bool DestroyNumberMaskFollower(
		USkeletalMeshComponent* Follower,
		USkeletalMeshComponent* ExpectedVisualMesh,
		FString& OutError);

	/** 创建只用于近景诊断的 transient 球员，读取源姿态但不修改源 Actor。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Jersey Number|Preview")
	static USkeletalMeshComponent* CreateNumberPreviewMesh(
		USkeletalMeshComponent* SourceMesh, UMaterialInterface* NumberMaterial,
		const FTransform& WorldTransform, FString& OutError);

	/** 在测试球员 Owner 上创建临时遮挡几何；不隐藏任何生产遮挡物。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Jersey Number|Preview")
	static UStaticMeshComponent* CreateNumberPreviewOccluder(
		USkeletalMeshComponent* PreviewMesh, UStaticMesh* OccluderMesh,
		const FTransform& WorldTransform, FString& OutError);

	/** 当前冻结姿态的一次同步捕获；不代表 Sequence/MRQ 帧同步已验收。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Jersey Number|Preview")
	static bool CaptureNumberPreviewPair(
		USkeletalMeshComponent* PreviewMesh, UMaterialInterface* NumberPostProcess,
		const FTransform& CameraTransform, int32 Width, int32 Height, float HorizontalFOV,
		const FString& OutputDirectory, const FString& CaseName,
		int64& OutEngineFrame, FString& OutError);

	/** 仅删除此接口建立且带身份标签的测试 Owner 和其所有测试组件。 */
	UFUNCTION(BlueprintCallable, Category="FutsalMOT|Jersey Number|Preview")
	static bool DestroyNumberPreviewMesh(USkeletalMeshComponent* PreviewMesh, FString& OutError);

	static int32 FindUniqueJerseySlotFromNames(const TArray<FName>& SlotNames);
};
