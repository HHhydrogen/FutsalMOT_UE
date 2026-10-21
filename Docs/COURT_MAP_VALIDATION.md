# 球场和球门地图改动验收

验收日期：2026-10-21；正式地图 `/Game/FutsalMOT/Maps/L_FutsalCourt`。

本次独立地图提交包含球场地图、matte 草地材质及其场地 Actor、白线/弧线/边界相关 Actor、球门框和球网、看台资产目录 `Staduim`、足球 Mesh/材质/Blueprint，以及对应 External Actors 和 External Objects。保留现有目录命名，不通过文件系统移动 UE 资产。

上述资产在真实 UE 中可加载，已通过 Game package 依赖闭包检查；新增依赖与项目内提交清单对应，不依赖忽略目录中的新 Fab 文件。场馆灯和天气代码由独立天气提交提供；服装资产由独立外观提交提供。

四个 CineCam 各渲染 3 帧、1920×1080、10 FPS，RGB/Object-ID 同 job；12 张 RGB、12 张 mask 全部解码，full audit 通过。四机位首帧已检查草地和边线、两端球门框与球网、看台、球员及足球，没有可见的缺失资产或材质棋盘格。该结果验证当前短渲染场景，不包含球门物理碰撞或完整足球比赛逻辑测试。

本机验收图：`Saved/AppearanceValidation/map_and_kits_four_cameras.png`。依赖记录：`Saved/WeatherPushReview/asset-dependencies.json`。最终正式地图保持加载，PIE/MRQ 已结束，未保存资产和地图列表为空。

未将此前修改的正式相机 Sequence、运行时测试地板材质、本地 Codex 设置和自动生成的测试 Sequence 混入此提交。号码功能暂不提交，保留为后续待办。
