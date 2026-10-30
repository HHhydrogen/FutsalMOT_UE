# 长边主视角、四角与随机局部机位

当前九机位参数已获用户确认并写入[`camera_rig_v2.json`](../../python/configs/camera_rig_v2.json)。后续新生成只消费single_seed冻结recipe，不投递旧simulation.camera模板或旧Sequence。

## 当前机位

所有机位3840×2160，传感器23.76×13.365mm，roll=0；位置单位米，旋转为UE Pitch/Yaw/Roll（度），静态焦距。C5高11.7m，已通过4K构图去除底部白边；不再采用旧10.5m/11.0m或1080p预览值。

| ID | 含义 | 位置X/Y/Z m | Pitch / Yaw ° | 焦距mm | Actor |
| --- | --- | --- | --- | ---: | --- |
| C5 | 必选，长边全场 | 0 / -19.7 / 11.7 | -30 / 90 | 8 | CineCam_Main |
| C1 | 必选，四角(+,+) | 24 / 14 / 9 | -33.288868796 / -135 | 13.5 | CineCam_01 |
| C2 | 必选，四角(-,+) | -24 / 14 / 9 | -33.288868796 / -45 | 13.5 | CineCam_02 |
| C3 | 必选，四角(-,-) | -24 / -14 / 9 | -33.288868796 / 45 | 13.5 | CineCam_03 |
| C4 | 必选，四角(+,-) | 24 / -14 / 9 | -33.288868796 / 135 | 13.5 | CineCam_04 |
| P01 | 候选，左半场侧视 | -11 / -18 / 8 | -21.526479721 / 90 | 18 | CineCam_P01 |
| P02 | 候选，右半场侧视 | 11 / -18 / 8 | -21.526479721 / 90 | 18 | CineCam_P02 |
| P03 | 候选，左球门后局部 | -26 / 0 / 7 | -18 / 0 | 22 | CineCam_P03 |
| P04 | 候选，右球门后局部 | 26 / 0 / 7 | -18 / 180 | 22 | CineCam_P04 |

精确浮点数以配置及实际native回读为准。主视角覆盖全场；四角和局部机位不承诺完整球员始终入画，截断/出画按[数据契约](DATA_CONTRACT.md)记录。

## 选择、执行与调整

`camera_rig.build_camera_plan`使用独立namespace `futsalmot:camera-rig:v2`决定额外数量1或2及P01–P04排名，不调用全局RNG。数量和排名只依赖seed与候选ID，修改位置/焦距不会重新抽取相机，但配置SHA会变化。

每seed必选C5/C1/C2/C3/C4，再加1–2个不重复局部机位。1048为C5/C1/C2/C3/C4/P02，2026102901为五必选加P02/P04。结果进入统一recipe的cameras组件；分机位执行只是调度拆分，最终集合仍必须等于完整冻结清单，不能漏掉机位。原设计“不同seed相机集合一致”已由用户此要求替代。

单seed入口自动读取配置并准备内部task。用户手调后须读取实际Actor并同步JSON，保存自有相机包；生成器不能仅依据Editor未保存内存。当前序列在新attempt独立目录生成，不覆盖旧LS_Cam_01–04或原运行收据。

## 验证依据

九机位静态方案已获确认；a09当前4K/8x8、C5高11.7m，六机位各30帧的真实RGB/双mask、body12和相机native导出通过。完整3001帧仍待运行，不以短样代替完整验收。

用户手调原值与同步回读在`Saved/CameraRigV2/manual_sync_a01`，最终主机位在`Saved/SingleSeed/main_camera_4k_a02`，当前动态短样在`Saved/SingleSeed/single_seed_s1048_4k_a09`。旧候选、失败及1080p预览只作为[历史记录](https://github.com/HHhydrogen/FutsalMOT_UE/blob/a2f488a506266242b4e5223609774a8d6f87b56a/Docs/engineering/SEEDED_CAMERA_RIG_V2.md)，不能据此重新生成旧配置。
