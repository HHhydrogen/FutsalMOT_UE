# UE资产短渲染验收基线

以下为2026-10-21历史资产验收，不表示这些本机图片/临时episode今天仍保留。正式随机服装目录仅Set_01–05；Set_06–15加载/临时绑定短测不等于已纳入随机目录。原验收范围和历史收据说明完整保留如下。

## 历史来源：COURT_MAP_VALIDATION.md

## 球场和球门地图改动验收

验收日期：2026-10-21；正式地图 `/Game/FutsalMOT/Maps/L_FutsalCourt`。

本次独立地图提交包含球场地图、matte 草地材质及其场地 Actor、白线/弧线/边界相关 Actor、球门框和球网、看台资产目录 `Staduim`、足球 Mesh/材质/Blueprint，以及对应 External Actors 和 External Objects。保留现有目录命名，不通过文件系统移动 UE 资产。

上述资产在真实 UE 中可加载，已通过 Game package 依赖闭包检查；新增依赖与项目内提交清单对应，不依赖忽略目录中的新 Fab 文件。场馆灯和天气代码由独立天气提交提供；服装资产由独立外观提交提供。

四个 CineCam 各渲染 3 帧、1920×1080、10 FPS，RGB/Object-ID 同 job；12 张 RGB、12 张 mask 全部解码，full audit 通过。四机位首帧已检查草地和边线、两端球门框与球网、看台、球员及足球，没有可见的缺失资产或材质棋盘格。该结果验证当前短渲染场景，不包含球门物理碰撞或完整足球比赛逻辑测试。

本机验收图：`Saved/AppearanceValidation/map_and_kits_four_cameras.png`。依赖记录：`Saved/WeatherPushReview/asset-dependencies.json`。最终正式地图保持加载，PIE/MRQ 已结束，未保存资产和地图列表为空。

未将此前修改的正式相机 Sequence、运行时测试地板材质、本地 Codex 设置和自动生成的测试 Sequence 混入此提交。号码功能暂不提交，保留为后续待办。


## 历史来源：PLAYER_APPEARANCE_ASSET_VALIDATION.md

## 新服装资产验收

验收日期：2026-10-21；UE 5.8；正式地图 `/Game/FutsalMOT/Maps/L_FutsalCourt`。

本次独立资产提交包含 `Characters/MPFB/Materials/M_MPFB_{Jersey,Shorts}_Set_06..15` 的 20 个材质、对应 `Textures/T_MPFB_{Jersey,Shorts}_Set_06..15` 的 20 个 Texture2D，以及此前修改的 Shorts Set_02–05 材质和 Player_003 Mesh。没有新增角色骨架或改动共享动画管线。

已完成：

- 全部新增材质/纹理加载、class、纹理依赖及 sRGB 检查；材质实际使用的纹理与对应 Set 一致。
- 十名唯一球员的可见 MPFBVisual 均使用共享 `SKEL_MPFB_Base`，球衣和短裤按语义 slot 绑定；Player_003 Mesh 已在真实渲染使用。
- 十名球员分别临时绑定 Set_06–15，逐人 readback 与目标材质完全一致。
- 固定 seed 42、多云天气，四个 CineCam 各 3 帧，1920×1080、10 FPS；12 张 RGB、12 张 mask 全部解码，annotation validator 和 full audit 通过。
- 四机位首帧逐人 mask 非零像素、tight bbox 和服装裁剪图检查通过；可见蓝、红、灰黑、紫、白、橙、青等服装差异，没有缺失材质棋盘格。
- 测试结束后，十名球员完整 snapshot、override materials、环境参数及 package clean 状态恢复，最终只读 appearance preflight 通过。

本机证据位于 `Saved/AppearanceValidation/`：`asset_preflight.json`、`kit_application.json`、`kit_rollback.json`、`kit_restore.json`、`final_preflight.json`、`pixel_evidence.json`、`new_kits_contact_sheet.png`、`map_and_kits_four_cameras.png`。数据 episode 位于 `G:/FutsalMOT_Dataset/appearance_validation_20261021/episode_weather_candidate_new_kits_s42/`，保留 render summary、环境恢复报告和 full audit。

该测试验收服装资产加载、绑定和短渲染，不替代新角色 Idle/Forward/Stop/Reverse/Turn 完整生产 SOP，也不证明所有光照、姿态和长批次均通过。正式 appearance v1 的随机目录仍严格为 Set_01–05；Set_06–15 已保存为可用资产，扩充自动随机目录需要后续单独维护契约和版本。

号码尚未成功实现，暂不提交相关代码、资产或 appearance v2 开关。后续需验收背部贴合、骨骼跟随、正面无号码、遮挡、唯一号码清单、RGB/号码 mask 帧同步及 apply/restore 生命周期；见 `TASK_STATUS_AND_NEXT_STEPS.md`。
