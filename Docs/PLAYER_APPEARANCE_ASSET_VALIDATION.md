# 新服装资产验收

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
