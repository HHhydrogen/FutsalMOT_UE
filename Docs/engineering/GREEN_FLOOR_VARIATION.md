# GreenV2绿色草地

用户已确认a02参数，当前single_seed只选择深/标准/浅三档绿色。旧蓝、红棕、中性灰和GreenV1仅解释历史数据，不再提供新生成入口或旧材质创建命令。

| 参数 | 已确认值 | 作用 |
| --- | --- | --- |
| GrassUVTiling | 60 | 原草纹同方向尺度缩小到原来的1/4，BaseColor/Normal/ORM同步 |
| GrassNormalFlatness | 0.90 | 减弱细纹凹凸 |
| GrassStripeContrast | ±18%，系数0.82/1.18 | 保留原条带方向和4米周期，加强深浅差异 |
| GreenAlbedoGain | 深0.60、标准1.00、浅1.50 | 三通道等比例调节亮度 |

母材质为`/Game/FutsalMOT/Environment/Floors/GreenV2/M_GrassDetail_v2`，实例为`MI_grass_dark_v2`、`MI_grass_standard_v2`、`MI_grass_light_v2`。复用原草地贴图，不能猜调旧实例的Param来冒充新参数。

`grass_detail.grass_recipe`复用既有floor独立namespace；整场固定，不改变运动、外观、天气或号码随机流。由[统一recipe](SEEDED_APPEARANCE_UV_NUMBERS.md#统一每场seed配置入口2026-10-29)准备，当前入口按协议应用与恢复原地板槽，不修改历史材质或保存临时场景状态。

真实材质读回和a02三档静态预览已获用户确认；a09当前草地与全部外观/号码/天气联合30帧×6机位短样通过。root1048选择grass_dark_v2；其他seed按冻结recipe记录实际选择。不得要求各seed自动均衡或按图像效果挑seed。

小证据在`Saved/FloorDiversity/green_v2/{creation_complete.json,revision_a02/complete.json}`，联合短样在`Saved/SingleSeed/single_seed_s1048_4k_a09`。历史初稿及负结果保留[Git记录](https://github.com/HHhydrogen/FutsalMOT_UE/blob/a2f488a506266242b4e5223609774a8d6f87b56a/Docs/engineering/GREEN_FLOOR_VARIATION.md)；新运行只采用上述a02值。
