# 可复现天气光照系统

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
