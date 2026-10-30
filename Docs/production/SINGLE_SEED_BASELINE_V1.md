# 已验单seed生成配置固化（2026-10-29）

当前唯一配置入口为`python/configs/single_seed_generation_v1.json`，保留a09实测的4K/8/8及视觉参数。旧生成入口和配置已退役，本轮补齐容量门禁及完整导出生命周期；完整比赛或正式数据发布尚未完成。用户要求本轮完成后提交GitHub并停止。

## 冻结值

| 项目 | 当前值 |
| --- | --- |
| 分辨率/时间 | 3840×2160，10 FPS，time_scale=1 |
| 示例源 | root_seed=1048，5_vs_5，game_duration=3000，上限4000，双方难度0.5；首次done停止、不reset；已有源实际3001帧 |
| 采样 | 空间1、时间1、AA关闭、motion blur0、warmup8 |
| 执行 | 每机位独立UE进程，串行；ImageWriteQueue.MaxConcurrency=8，MaxQueueSize=8 |
| 内存 | 入场物理8GiB/提交24GiB；运行低于物理2GiB或提交8GiB时正常取消并停止派发，每2秒采样 |
| 相机 | C5/C1/C2/C3/C4必选，加P01–P04独立seed选1–2个；1048选P02；C5高11.7m、8mm、Pitch -30° |
| 外观 | appearance v1独立seed算法，十五套球衣/短裤；号码v2含按球衣底色选择黑/白墨色 |
| 草地 | GreenV2 a02：平铺60、Normal Flatness0.90、条带±18%、深/标准/浅增益0.60/1.00/1.50 |
| 天气 | futsalmot_indoor_weather_visual_v2，八类参数见天气视觉文档 |
| 输出 | RGB、人物整数mask、号码整数mask、逐帧标注、body12、实际相机校准、同源轨迹、seed_manifest |
| 标注边界 | body12可见性unknown=0；号码readable未人工认证为false；号码像素错属阈值0 |
| 存储配置 | G:/FutsalMOT_Dataset/test独立attempt；预算1TiB、最低剩余100GiB；预估7byte/px；控制器、UE分机位入口和导出入口统一检查 |
| 生命周期 | MRQ后仍awaiting_export/active；导出、校验和EXR清理完成后开始24h成功保留；确认停止的失败保留最长7天，未确认UE停止保持attention_required/active |

相机、球衣和号码参数分别在`camera_rig_v2.json`、`player_appearance_catalog_15kits.json`、`number_typography_v2.json`。已确认的绿色材质、号码派生材质、字体图集及九个相机Actor随代码提交；试验Sequence按运行新建，不固化旧临时序列。C++ body12类随源代码提交，UE5.8需按项目正常构建；DLL及Saved收据不入Git。

## 从项目根执行

**当前完整单seed暂不执行。** 容量和生命周期接线已补齐并做轻量检查；下列命令供用户重新要求执行时使用，不表示已获本轮长样许可。旧`grf-ue task`只返回迁移提示；内部`run_task`拒绝非当前分机位/4K/10FPS/8/8/十五套球衣/号码v2/天气v2/body12配置。`--attempt`必须显式提供，内部基础模板为`single_seed_task_base.json`。

以下`single_seed_s1048_new01`仅为新attempt名称示例。准备阶段要求P1 Python3.9环境；渲染控制器通过真实Unreal MCP运行，需本机UE5.8、PowerShell7、G盘及既有插件环境。

```powershell
python/.venv/Scripts/python.exe tools/dataset/single_seed_task.py prepare --attempt single_seed_s1048_new01
python/.venv/Scripts/python.exe tools/dataset/single_seed_task.py freeze --attempt single_seed_s1048_new01
python/.venv/Scripts/python.exe tools/dataset/run_single_seed_partitions.py --attempt single_seed_s1048_new01 --short
python/.venv/Scripts/python.exe tools/dataset/single_seed_task.py export --attempt single_seed_s1048_new01 --short
# 短样通过后执行完整源；若中断，可用相同命令跳过已有成功退出收据的机位。
python/.venv/Scripts/python.exe tools/dataset/run_single_seed_partitions.py --attempt single_seed_s1048_new01
python/.venv/Scripts/python.exe tools/dataset/single_seed_task.py export --attempt single_seed_s1048_new01
```

先正常关闭已有Editor；控制器不会结束其他用户进程。部分输出但未闭合的机位保留现场，不盲目重放。启动脚本现为`tools/dataset/launch_single_seed_editor.ps1`，退出脚本为`python/ue/quit_single_seed_editor.py`，不再依赖Saved中的本机脚本。内存阈值直接消费协议中的绝对参数，PowerShell启动脚本纳入新运行源码快照。

冻结后不能修改源码、轨迹或DLL再接续旧attempt；提交整理改变源码绑定，旧a09及其收据保留历史原值，后续新运行另立协议。上述准备示例会采源；已有3001帧源仍保留Saved，可在另立协议时显式登记复用，不能改写旧冻结协议。

## 容量与结束时序

准入按实际帧数×本seed全部选定机位×3840×2160×7byte估算峰值，不能按正在启动的一个机位低估全seed。超过1TiB预算则拒绝；可用空间须覆盖预计尚未写出的部分并另留100GiB。7byte/px高于a09 EXR+导出约6.48byte/px的短样观测，但仍是估算；运行每2秒检查磁盘余量、每30秒只统计当前attempt文件元数据/去重硬链接，超限正常取消并停止派发。后处理在各机位边界及每64帧检查，防止外部磁盘占用变化。

1048的6×3001帧预计973.64GiB，另留100GiB；6×30帧短样预计9.73GiB，不预占完整比赛预算。7×3001帧约1135.92GiB，会被当前1TiB上限拒绝；将来若选中7机位长样，必须先另立容量方案，不能偷偷减少机位或放宽阈值。

生命周期收据原子写入。各机位MRQ与正常退出仅写awaiting_export；exporting/verifying及等待后处理都保持active且无过期时间。最终校验成功、EXR精确清理和成功收据落盘后才标complete。后处理异常标failed_stopped；渲染异常若未证明UE停止则保持attention_required，避免误清仍可能活动的数据。重复已完成verify不会刷新保留期限。

## 验证范围

真实a09六机位各30帧，180 RGB/人物mask/号码mask、1800人物记录、905可见号码、21600个body12点，554文件/3001729547字节；逐帧契约、号码像素归属、恢复和六次正常退出通过。180份EXR/6671222958字节已清理。Pose可见性及可读性仍按上表限制。

同C5/30帧1/1、2/2、8/8总耗时101.187/74.609/43.219秒；8/8六机位最低提交余量11.156GiB、物理空闲9.013GiB。完整3001帧分机位生成尚未执行，不以短样替代完整验收。完整结果与负结果见[渲染策略](../operations/RENDER_POLICY_4K_32GB.md)、[天气视觉版本](../engineering/WEATHER_LIGHTING_VISUAL_V2.md)和[训练/诊断历史](../research/TRAINING_HISTORY.md)。本次固化只做必要代码/配置检查，不重复渲染或媒体审计。
