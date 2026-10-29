"""UV 号码共享材质函数的 HLSL；仅定义源码，不访问引擎或创建资产。"""

UV_NUMBER_COLOR_HLSL = r"""
float2 Size = max(Rect.zw - Rect.xy, float2(0.000001, 0.000001));
float2 Local = (UV - Rect.xy) / Size;
float InRect = step(0.0, Local.x) * step(Local.x, 1.0)
             * step(0.0, Local.y) * step(Local.y, 1.0);
Local = lerp(saturate(Local), 1.0 - saturate(Local), saturate(Flips.xy));
float Index = clamp(floor(NumberIndex + 0.5), 0.0, 98.0);
float2 Cell = float2(fmod(Index, 16.0), floor(Index / 16.0));
float2 AtlasUV = (Cell + Local) / float2(16.0, 8.0);
float Alpha = saturate(Texture2DSample(Atlas, AtlasSampler, AtlasUV).a)
            * InRect * saturate(NumberEnabled);
float3 Beauty = lerp(BaseColor.rgb, Ink.rgb, Alpha);
float3 NumberID = (Alpha >= 0.5 ? 1.0 : 0.0) * (NumberMaskID / 255.0);
return float4(lerp(Beauty, NumberID, saturate(NumberMaskMode)), Alpha);
""".strip()

CUSTOM_INPUTS = (
    "BaseColor", "UV", "Atlas", "Rect", "Flips", "Ink",
    "NumberIndex", "NumberEnabled", "NumberMaskMode", "NumberMaskID",
)
