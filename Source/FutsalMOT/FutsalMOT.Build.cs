using UnrealBuildTool;

public class FutsalMOT : ModuleRules
{
	public FutsalMOT(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"CoreUObject",
				"Engine",
				"AnimGraphRuntime",
				"InputCore",
				"MovieRenderPipelineCore",
				"MovieRenderPipelineRenderPasses"
			});

		// Pose17 只在 .cpp 读取实际 LOD RenderData；公共反射头不暴露渲染类型。
		PrivateDependencyModuleNames.AddRange(new string[] { "RenderCore", "RHI", "Json", "JsonUtilities", "CinematicCamera" });
		// Windows 的 FGenericPlatformMisc SHA256 入口没有通用实现；使用引擎自带 OpenSSL。
		AddEngineThirdPartyPrivateStaticDependencies(Target, "OpenSSL");
	}
}
