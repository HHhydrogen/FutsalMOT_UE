# 天气灯组应用与恢复

当前single_seed采用[天气视觉v2](WEATHER_LIGHTING_VISUAL_V2.md)，配置由统一recipe绑定；旧weather smoke、旧catalog和子仓库命令不是新生成入口。正式地图为`/Game/FutsalMOT/Maps/L_FutsalCourt`，代码位于本仓库python目录。

## 配套灯组参与渲染的证据

2026-10-29对“光照未启用”的隔离检查确认：Editor/PIE十个场馆SpotLight在overcast条件下均为8EV，事务实际启用并写入回读收据。同一C5第10帧临时关闭十灯后，场地区域RGB均值由开灯20.2541降至关灯8.0316（0–255编码值，非物理照度或线性亮度），说明灯组参与真实渲染。后续天气视觉v2进一步调整了八档环境与光照，最新绝对参数只以v2目录为准。

该隔离检查使用60帧原条件及10帧关灯对照，MRQ和全部事务恢复成功；70份EXR消费后精确清理。前置失败包括Sequence路径冲突、已结束floor事务拒绝和GBK读取配置失败，均保留小收据，不能称首次无错。

小证据在`Saved/SingleSeed/lighting_diagnostic_a02`及`Saved/SingleSeed/lighting_pair_off_a01`。完整参数、指纹、天气视觉调整与4K证据见[视觉v2](WEATHER_LIGHTING_VISUAL_V2.md)；原2026-10-21八天气验收和旧参数在[Git历史](https://github.com/HHhydrogen/FutsalMOT_UE/blob/a2f488a506266242b4e5223609774a8d6f87b56a/Docs/engineering/WEATHER_LIGHTING_SYSTEM.md)。

## 当前运行契约

天气通过独立seed选择，不改变外观/号码/地板/运动随机流。当前事务应用环境Actor和十灯后回读实际参数；渲染完成后恢复原值，正常退出需真实终态及恢复证据。静态SceneCapture或未预热Editor画面不替代MRQ天气曝光验证。

新运行一律4K、按机位独立UE和8/8写出；不得通过旧天气示例绕过single_seed的完整协议、内存/容量与生命周期控制。短样不代表任意长序列或后台负载永不崩溃，完整比赛目前尚未执行。
