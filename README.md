# FutsalMOT / FutsalPoseTrack

使用Unreal Engine 5.8和Google Research Football生成五人制足球时序数据，并研究合成姿态监督对真实身份关联的作用。UE资产、C++、Python和实验代码统一由本仓库管理。

## 从这里开始

- [从第一次训练到现在](Docs/research/TRAINING_HISTORY.md)：面向用户的持续训练历史，说明每版训练什么、为什么、用了哪些数据、绝对参数/成绩和结论边界。

- [文档索引](Docs/README.md)：工程契约、生产、研究与运维说明。
- [当前任务](TASK_STATUS_AND_NEXT_STEPS.md)：实际阶段与下一步，不以历史命令代替当前状态。
- [Agent规则](AGENTS.md)：Git、存储、UE生命周期及研究边界。
- [Python入口](python/README.md)：轨迹、后处理和UE Python脚本的统一入口。
- [运行与维护](Docs/operations/RUNNING_AND_MAINTENANCE.md)：项目根的统一启动器与本机配置。

## 代码和环境

| 内容 | 当前入口 | 执行环境 |
| --- | --- | --- |
| UE运行时 | Source/FutsalMOT | C++ / UE5.8 |
| UE插件与MCP | Plugins/FutsalMOTMCP | 真实Editor Python |
| 轨迹与后处理 | python/src | 固定Python3.9的P1环境 |
| 渲染脚本 | python/ue | UE Python，不能在P1执行 |
| 训练与评价 | experiments | 独立研究Python3.10 |

P1与UE之间通过JSON/JSONL交换数据；UE不导入NumPy/OpenEXR依赖的P1模块。GPU训练与UE渲染串行。默认地图保持`/Game/FutsalMOT/Maps/L_FutsalCourt`，资产移动通过UE API修引用。

目录已按文档、Python/实验、UE资产和运行入口分层。号码WIP保留且不纳入成果提交；旧环境路径仍有17个兼容重定向器，见[资产目录](Docs/production/UE_ASSET_LAYOUT.md)。

## 数据集

正式数据集根为`G:/FutsalMOT_Dataset`：

| 版本 | 数量 | 限制 |
| --- | --- | --- |
| v1_no_numbers_4k | 8seed、32相机序列、20116对4K RGB/mask | 有bbox，无Pose，保留原train归属 |
| v2_pose17_location_pilot_a01 | 1920对4K、19200逐视角人物Pose | 480源时间样本，限定位置研究候选 |
| v2_pose17_longpair_pilot_a01 | 4800对4K、48000逐视角人物Pose | 600源时间样本，16条30秒相机序列 |

均为原生3840×2160、10FPS。按seed/manifest解析，不硬编码旧clips/clip_000层级。v2保留逐机位world、unknown及原诊断标记，不冒充正式可见性或遮挡标签；地板配对world约0.068mm差异保留原值，不称exact。

UE配置、轨迹与收据位于本项目Saved物理目录；渲染媒体（含临时EXR）统一写G盘数据集根的`_work/_staging`，成功消费后清理EXR。研究执行源码按SHA安装到实际`D:/projects/FutsalMOT_Research/code`，输入/权重/结果同在D研究根；生成图像只引用G成品。见[严格存储规则](Docs/operations/STORAGE_POLICY.md)。Saved、缓存、虚拟环境、媒体、模型权重不入Git；AutoSave关闭。

## 研究

主问题是固定真实检测输入时，合成Pose监督能否改善身份连续性。[本轮v4](Docs/research/POSE_V4_RESULTS.md)在相同真实曝光下AssA均差+0.2644个百分点、仅1/3训练seed提高，未达到登记门槛；混合臂未超过预训练关联结果。全部负结果保留，不以格式、4K、四机位或地板变化单独宣称创新。最终SNMOT116/187保持封存。

[v5配对对照](Docs/research/POSE_LONGPAIR_V5.md)使用30秒数据的固定虚拟裁剪，比较纯真实、加蓝地板合成、加红棕地板合成；真实曝光保持相同，并独立比较共同预训练参考。[九臂结果](Docs/research/POSE_V5_RESULTS.md)蓝相对R3平均AssA仅+0.2644点、1/3训练seed提高，红均差0，未过门槛或超过预训练。[v6](Docs/research/POSE_FIXED_CROP_V6.md)提升Pose接入覆盖、[v7](Docs/research/POSE_QUALITY_TEMPORAL_V7.md)检验质量/敏感度/短时预测后，轨迹仍无改善。

[v8完整结果](Docs/research/LEARNED_ASSOCIATION_V8_RESULTS.md)已完成36臂、三比赛留一开发及实际预算核对：同3000R窗口、混合另1000S，pose_RS相对pose_R AssA+2.8034点、相对预训练ByteTrack+1.4727点，通过事前门槛；但仍低于motion_RS 4.3956点，不能将合成身份监督增益全部归于Pose。窗口不等于图像曝光、956个检测断档proxy不等于物理遮挡；测试116/187继续封存。

[v9完整结果](Docs/research/POSE_V9_RESULTS.md)已闭合78臂及实际预算：gated混合较纯真实AssA+0.8867点，但较同名义参数运动组仅+0.1459点、较原v8 motion_RS仍−0.4491点，未通过Pose增量门槛。原数据与测试集保持冻结；下一步[接回已有seed球衣系统](Docs/engineering/POSE_SEEDED_KIT_INTEGRATION.md)，验证同运动/相机服装配对，而非另造随机系统。

## Git

```powershell
git clone https://github.com/HHhydrogen/FutsalMOT_UE.git
```

唯一master保留原UE和Python提交历史；新clone无需submodule初始化。在Python目录运行Git也定位本项目根。精确选择已验文件，一次commit/push，不add-A或force；迁移经过见[单仓库记录](Docs/operations/SINGLE_REPOSITORY_MIGRATION_20261025.md)。用户已主动删除备份，不自动重建。
