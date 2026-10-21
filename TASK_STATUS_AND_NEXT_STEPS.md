# FutsalMOT 当前任务情况与后续计划

更新时间：2026-10-21

## 当前目标与结果

已实现可按 seed 复现的天气光照系统，形成八档完成短 episode 验收的状态。天气 seed 默认取 `export.seed`；`preset="auto"` 用独立 SHA-256 命名空间选择天气，显式 preset 仍可用。天气微变化不消费球员随机系统或轨迹的全局随机状态。

正式地图：`/Game/FutsalMOT/Maps/L_FutsalCourt`。实际场馆补光是十个持久化 SpotLight（`SpotLight`、`SpotLight2..10`），另有一个太阳 DirectionalLight。只修改十灯的 intensity/unit，保留手动位置、旋转、颜色、半径、锥角和阴影。

| preset | 十灯 EV | 四机位场地平均亮度范围 | 球员暗像素最大占比 |
| --- | ---: | ---: | ---: |
| `daylight_clear_v1` | 5 | 49.9–83.7 | 9.46% |
| `overcast_soft_v1` | 8 | 38.3–47.5 | 4.85% |
| `warm_evening_v1` | 10 | 64.9–65.2 | 0.90% |
| `cool_evening_v1` | 10 | 65.8–66.1 | 0.62% |
| `light_haze_v1` | 5 | 41.6–73.5 | 12.76% |
| `cloudy_variation_v1` | 8.5 | 51.6–55.6 | 3.61% |
| `dawn_cool_v1` | 10 | 67.3–67.6 | 0.46% |
| `night_floodlit_v1` | 10 | 66.4–66.8 | 0.83% |

暖傍晚、冷暮光的太阳基准 pitch 已降到 -10°/-8°；新增清晨为 -6°。夜间太阳与 SkyLight intensity 始终为零，由场馆灯照明。阴天、多云降低直射太阳并提高补光，解决初始 5 EV 方案的背光剪影。白平衡按实际 MRQ 颜色校准，暖/冷/清晨分别为 8000/5000/5600 K。

## 可复现与运行入口

- catalog revision：2；fingerprint：`48a095a31efd17443a82e255cc2175330d7df3321c09b1880821c2f8516285c2`。
- 示例：`Content/FutsalMOT/code/configs/weather_seeded_smoke_3frames_4cam.json`，设置 auto 且省略 environment seed，seed 42 选择 cloudy、47 选择 night。
- P1 使用固定 Python 3.9；P2 在 UE 5.8 内执行 `ue/run_task.py`，诊断不再 import P1 包。
- manifest 记录具体 preset、最终参数、namespace seed、轨迹和 catalog 指纹；P2 应用后回读并自动恢复。复现以相同版本、资产、地图基线和渲染设置为前提，不承诺跨 UE/GPU 的 PNG 字节一致。
- 参数表和选择字节协议见 `Content/FutsalMOT/code/docs/DATA_CONTRACT.md`；当前验收详情见 `docs/VALIDATION_AND_LIMITATIONS.md` 末尾。

## 本轮实际验收

- 八档 × 四相机 × 三帧，1920×1080、10 FPS，共 96 RGB、96 mask。
- P1 validate/export、双只读诊断、UE apply/readback/MRQ/restore、后处理、annotation validator 和 full audit 全部通过。
- 最终正式 Level，PIE/MRQ inactive，dirty packages 为空；六类环境参数和十灯手动布局/属性与开始前一致，十灯恢复 5 EV；无本轮 rollback 遗留。
- 天气独立提交版本默认测试：1463 passed、7 deselected；原六个 portable-config 失败已修复测试隔离，未更改生产路径优先级。
- 该 smoke 不启用 appearance v2/号码/Pose，不替代这些系统的联合验收。

最终数据根目录：`G:/FutsalMOT_Dataset/weather_validation_20261021_r3/`。验收 episode 清单：`Saved/EnvironmentPreviews/weather_20261021_r3/index.json`，cool evening 使用 `_r3_retry2`。每个 episode 的 audit、environment manifest、application report 和 render summary 均保留。对比图和汇总在同一 Saved 目录的 `weather_overview.png`、`weather_all_cameras.png` 和 `verification_summary.json`；所有本机验证脚本、日志和图片均为生成物。

## 失败记录与当前限制

首轮发现 evening 白平衡冷暖反向、多云 5 EV 下球员暗部接近剪影，均已校准并重验。连续大量 MRQ 导致旧 Editor 会话 D3D12 显存耗尽；另有 P1 内存错误和一张不可解码 EXR。失败结果保留但排除出成功清单。Editor 重启后已核验 module/MCP/地图，通过正式事务恢复中断快照，再以独立输出重渲染冷暮光并完成解码/audit。后续采用 MRQ 与单 worker 后处理串行执行。

当前只完成 seed 42 的八档短 smoke 和多 seed 纯参数测试，尚未证明长时连续 MRQ 的显存稳定性。旧 `env_presets/`、r1/r2 和失败的 r3 尝试不能作为当前 catalog 的验收结果。晴天与薄雾仍保留不同机位的明显阴影差异，不能把整幅平均亮度当作每名球员均匀照明保证。

## 后续顺序

1. 扩展代表性 seed、球员外观、运动位置和遮挡，做天气与 appearance/Pose 的联合短 episode 验收。
2. 验证长时 MRQ 显存曲线与分批策略；发生异常时先核对并恢复事务证据，再决定是否重启，不覆盖未知状态。
3. 明确 production seed/preset 清单、每 episode 帧数/相机、fingerprint、MRQ/postprocess/audit/restore/cleanup 策略。
4. 上述通过后再启动 900 帧生产批次；当前未启动，未执行 cleanup --apply。

## 新服装和地图资产验收（2026-10-21）

Set_06–15 的 20 个服装材质与 20 个 Texture2D 已通过 class、纹理依赖、sRGB 和 UE 加载检查。十名共享骨架球员分别临时绑定一套新服装，四机位各 3 帧 MRQ、12 张 RGB/12 张 mask 解码、逐人可见像素检查及 full audit 通过；随后材质和环境基线恢复，最终 dirty packages 为空。验收图位于 `Saved/AppearanceValidation/`，详情见 `Docs/PLAYER_APPEARANCE_ASSET_VALIDATION.md`。正式随机目录仍为 Set_01–05；新资产扩充候选目录需要单独维护版本契约。

球场草地、白线、球门球网、看台和足球相关场景资产通过四机位实际渲染检查；提交包含对应 External Actors/External Objects，详情见 `Docs/COURT_MAP_VALIDATION.md`。

## 号码功能待办（暂不提交）

号码尚未成功实现，保留现有未提交开发代码，暂不提交号码资产、号码 mask 或 appearance v2。后续需完成背部贴合、骨骼跟随、正面无号码、身体/其它 Actor 遮挡、唯一号码清单、RGB/mask/frame 同步及 apply/restore 生命周期验收，再考虑切换正式配置。

## Git 状态

已获用户明确授权：天气系统及必需依赖、新球员外观资产、球场球门等地图改动分别提交并推送；号码功能排除。内层天气代码先推送，再由外层天气提交记录 gitlink；外观和地图使用各自独立的外层提交。本地 Codex 配置、未完成号码代码和未纳入范围的测试 Sequence 保留在工作区。提交 hash 以 Git 历史为准。
