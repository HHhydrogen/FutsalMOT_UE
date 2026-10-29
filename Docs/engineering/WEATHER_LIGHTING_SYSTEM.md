# 可复现天气光照系统

## 2026-10-29：单seed光照启用排查

结论：单seed的天气与十盏场馆灯已应用到真实MRQ，未发现“灯光未启用”的断线。只读Editor与实际PIE的114次采样均读到十灯8 EV、visible=true、hidden_in_game=false、affects_world=true；seed1048的`overcast_soft_v1`还应用了太阳强度1.456179、SkyLight强度2.017627、曝光补偿0.160108。结束恢复为原十灯5 EV，dirty/PIE/MRQ及自有回调均为空。

用完全相同的C5第10帧临时关闭十灯作隔离对照，场地区域`x=[400,1520), y=[420,740)`的RGB三通道均值由关灯8.0316变为原预设开灯20.2541（0–255编码值，非物理照度或线性亮度）。这证明灯组对实际输出有明显贡献。没有修改八档天气强度、曝光、灯位、相机、球衣、草地或号码参数，也未恢复已被中断的完整seed渲染。

此前人工确认的相机/号码静态预览没有应用新天气覆盖：`camera_rig_preview.start`给`_prepare_seeded_environment`传入的weather为None，只应用地板与外观。它们是几何/号码验收，不能作为当前阴天+深绿色随机场景的亮度基准。当前PostProcessVolume把曝光最小/最大值均固定为0，天气只覆盖曝光补偿；这是已存在的设置，本轮未调。画面偏暗与天气、深色地板和固定曝光组合有关，尚未量化各项独立贡献，不把“启用已验证”写成“亮度已获用户验收”。

必要检查仅一次原条件10帧×6机位与一次关灯10帧×C5；两次MRQ及全部事务恢复成功。诊断a01首次因Sequence路径复用在渲染前失败，第二次受已结束floor事务拒绝；新a02准备时曾因默认GBK读取UTF-8配置失败，补齐编码后实际渲染成功。失败均未产生MRQ图像，不删除原证据。70份诊断EXR（685239454字节）消费结束后按精确清单删除，RGB/native/配置与收据保留；诊断媒体成功保留24小时。

本机小证据：`Saved/SingleSeed/lighting_diagnostic_a02/{editor_applied.json,runtime_samples.json,exposure_baseline.json,on_off_pixel_comparison.json,diagnosis_complete.json,editor_restored.json}`及`Saved/SingleSeed/lighting_pair_off_a01/pair_complete.json`。对照图：`G:/FutsalMOT_Dataset/test/lighting_diagnostic_a02/review/C5_frame000010_lights_off_on.png`。本轮只排查，不改冻结协议或将诊断对照混入数据集。

## 原天气系统验收记录

更新：2026-10-21。天气代码属于 `Content/FutsalMOT/code` 子仓库；本层保存场馆灯及环境 Actor。正式地图为 `/Game/FutsalMOT/Maps/L_FutsalCourt`。

`configs/weather_seeded_smoke_3frames_4cam.json` 是短测试入口。省略 environment seed 时使用 `export.seed`；`preset=auto` 通过独立 SHA-256 命名空间选择八档天气，同 seed、catalog、资产和渲染配置可复现参数，不消费球员外观随机状态。

| 天气 | preset | 场馆十灯 EV |
| --- | --- | ---: |
| 晴天 | daylight_clear_v1 | 5 |
| 阴天 | overcast_soft_v1 | 8 |
| 暖傍晚 | warm_evening_v1 | 10 |
| 冷暮光 | cool_evening_v1 | 10 |
| 薄雾 | light_haze_v1 | 5 |
| 多云 | cloudy_variation_v1 | 8.5 |
| 清晨 | dawn_cool_v1 | 10 |
| 夜间场馆灯 | night_floodlit_v1 | 10 |

catalog revision 2 的 fingerprint 为 `48a095a31efd17443a82e255cc2175330d7df3321c09b1880821c2f8516285c2`。十个手动场馆灯实际为 SpotLight，仅修改 intensity/unit，保护位置、旋转、颜色、半径、锥角和阴影。夜间关闭太阳和 SkyLight。

八档各完成四机位 × 三帧、1920×1080、10 FPS 的真实 MRQ、全部 EXR 解码、annotation validator 和 full audit，共 96 RGB/96 mask；正式环境基线恢复，dirty packages 为空。提交前隔离号码开发内容的天气代码通过 1463 项默认测试（7 项 GRF 集成测试未运行），并再次完成四机位三帧 UE 回归及恢复。

本机证据：`Saved/EnvironmentPreviews/weather_20261021_r3/index.json`、`final_baseline.json`；额外提交前回归为 `Saved/AppearanceValidation/`。这些日志、图像、测试 Sequence 和数据集输出属于本机生成物，不作为必须提交的运行依赖。

本次仅完成短 episode。连续大量 MRQ 曾发生显存耗尽，尚未证明长批次稳定性；应串行渲染和后处理，异常后先恢复事务。跨 UE/GPU 不承诺 PNG 字节一致。参数与磁盘契约、运行入口和限制详见子仓库 README、`docs/DATA_CONTRACT.md`、`docs/VALIDATION_AND_LIMITATIONS.md`。
