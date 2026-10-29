# 长边主视角、四角与随机局部机位 v2

2026-10-29。第1项绿色草地、第2项统一seed入口及本页九机位方案均已获用户确认。已同步用户手调参数并扩大P03/P04范围，当前相机不再调整；用户随后重开号码字体/大小/位置/配色修订，第4项完整单seed生成、第5项总数据集导出尚未执行。

## 当前机位

可编辑参数源为`python/configs/camera_rig_v2.json`。九个真实CineCamera已配置并保存到规范地图；C1–C4、C5、P01复用原Actor身份并更新参数，P02–P04新增。Sequence使用独立开发目录，不覆盖旧LS_Cam_01–04的本机WIP。

所有机位1920×1080，传感器23.76×13.365mm，roll=0；位置单位米、旋转为UE Pitch/Yaw/Roll（度），静态焦距。C5表示主视角，渲染顺序优先C5。

| ID | 含义 | 位置X/Y/Z m | Pitch / Yaw ° | 焦距mm | Actor |
| --- | --- | --- | --- | ---: | --- |
| C5 | 必选，长边全场 | 0 / -19.7 / 10.5 | -30 / 90 | 8 | CineCam_Main |
| C1 | 必选，四角(+,+) | 24 / 14 / 9 | -33.288868796 / -135 | 13.5 | CineCam_01 |
| C2 | 必选，四角(-,+) | -24 / 14 / 9 | -33.288868796 / -45 | 13.5 | CineCam_02 |
| C3 | 必选，四角(-,-) | -24 / -14 / 9 | -33.288868796 / 45 | 13.5 | CineCam_03 |
| C4 | 必选，四角(+,-) | 24 / -14 / 9 | -33.288868796 / 135 | 13.5 | CineCam_04 |
| P01 | 候选，左半场侧视 | -11 / -18 / 8 | -21.526479721 / 90 | 18 | CineCam_P01 |
| P02 | 候选，右半场侧视 | 11 / -18 / 8 | -21.526479721 / 90 | 18 | CineCam_P02 |
| P03 | 候选，左球门后局部 | -26 / 0 / 7 | -18 / 0 | 22 | CineCam_P03 |
| P04 | 候选，右球门后局部 | 26 / 0 / 7 | -18 / 180 | 22 | CineCam_P04 |

精确浮点值以JSON源及实际回读收据为准，表中角度作人读参考。球门后视角为该方向的局部观察，不承诺球门及整个人体均落入画面；出画/截断语义将在单seed完整标注阶段收口。

主视角以40×20米场地四角及两球门中心投影到图内且留至少8px为配置检查；当前真实静态图覆盖完整场线及两端球门，旧候选的MRQ证据单列下文。四角用于多方向覆盖，不将其各自声明为完整全场。部分机位的地面网格入画比例均小于85%，只是视锥范围统计，不是人体遮挡率。

## 用户手调同步及新版预览

`sync_camera_rig_from_editor.py`先读取并保存用户手调后的九个真实Actor状态；除P03/P04外的七机位未调用修改接口，逐字段核对保持原值。P03/P04按当前朝向水平后退2m（X从±24变为±26），高度7m，焦距24→22mm，Pitch约-26.94575→-18°。真实回读后保存对应外部Actor包，并将九机位的position/rotation/focal及视线参考target_m同步到JSON；保留所有旧attempt的冻结recipe。

4项机位针对检查通过（0.21s），含新主视角覆盖、局部范围及独立seed不变。新预览使用原1048的step300、已验证随机外观、固化UV号码、标准GreenV2，九个实际CineCamera各捕获一张1920×1080静态PNG。预览结束临时捕获对象销毁，外观/号码/球/地板恢复，dirty=[]，UE保持打开；本轮无新MRQ、EXR、mask/Pose采集或正式episode。

首批`camera_rig_manual_a01`在floor收据第二次原子替换时返回一次WinError5，地板回滚与恢复收据均成功、未拍图；未定位具体占用者，不声称修复了底层文件占用。保留失败小记录并登记诊断期限后，新批次`camera_rig_manual_a02`九张全部成功。未改地板事务代码或重复相机调整。

- 用户手调原值与同步回读：`Saved/CameraRigV2/manual_sync_a01/{before.json,previous_catalog.json,complete.json}`。
- 当前预览及恢复：`Saved/CameraRigV2/camera_rig_manual_a02/preview_complete.json`；失败记录：`camera_rig_manual_a01/failure.json`。
- 当前媒体：`G:/FutsalMOT_Dataset/test/camera_rig_manual_a02/{raw,review}/`，成功24小时到期清理；首批空媒体诊断最长7天。
- 同一Editor日志：`Saved/Pose17Development/editor_camera_manual_20261029_184032.log`。本轮保留Editor供继续手调，未退出。

## 接入统一seed入口

生成task时，将上述JSON目录作为对象填入`ue.seeded_episode.camera_rig`，同时保持`enabled=true`。其余appearance、号码、天气及草地配置保持原入口。共享`grf_ue_bridge.camera_rig.build_camera_plan`负责：

- 每seed必选C5、C1、C2、C3、C4。
- 用独立namespace `futsalmot:camera-rig:v2`分别确定额外数量1或2，以及P01–P04的排名；不调用全局RNG。
- 选择互不重复的局部机位，每seed总数6或7。数量与排名只依赖seed及候选ID，修改位置/焦距不会重新抽取相机；目录SHA仍随实际参数改变。
- 结果进入统一`seeded_episode.json.components.cameras`及`cameras.json`；P2在运行时验证并读取冻结结果，实际Sequence/MRQ列表来自该结果，拒绝用临时相机子集替代本seed完整选定列表。

示例：1048为C5+C1–C4+P02（6个），1102为C5+C1–C4+P03（6个），2026102901为C5+C1–C4+P02+P04（7个）。相机组件加入前后的model/skin/kit、号码、天气及草地结果逐项相同。

旧`simulation.camera`及其P01模板保留原代码路径，仅新rig显式配置进入新入口。当前实际Actor位置已按用户要求调整；旧任务如需复现旧机位，应使用其冻结的显式profile/Sequence，不能把当前地图默认机位当作旧几何。

用户若手调Actor，可以先在UE中调整对应CineCam；验收后将实际position/rotation/focal回填JSON并同步新task中的目录，保存并重建该新attempt的清单。运行时以task绑定的JSON为准，不能只改Editor内存而让生成器再写回旧值。

用户要求每seed随机局部机位，替代原设计中“所有seed具有相同camera集合”的约束。后续单seed及总数据集manifest应记录每seed实际集合；本阶段只完成运行清单，不提前实现总manifest或发布器。

## 初次候选真实验证（手调前历史）

123项直接相关检查通过（0.73s）：独立seed、必选5个、随机1–2个、无重复、6/7分支、调相机不改其他随机项、运行时消费清单及旧相机兼容。

静态预览复用root1048已有源step300，原完整随机外观、已固化UV号码、标准GreenV2开启，固定站位；CineCamera实际transform/FOV/filmback回读后，用SceneCapture2D捕获1920×1080。九张有效预览位于`G:/FutsalMOT_Dataset/test/camera_rig_v2_a01/raw/`；总览、四角和局部分图在`review/`。首次C5材质未就绪呈灰色，保留为`diagnostic_C5_initial.png`并排除；Editor tick后同机位重拍成功。捕获对象释放脚本误传两个参数，按UE实际单参数API修正并在同一事务继续清理，未重拍其他机位。号码/外观、球和地板均已恢复，临时捕获对象已销毁。

最短MRQ检查a01试图每机位1帧，在Sequence构建阶段因原运动轨道要求起止两个key而失败，未提交MRQ；仅保存自有未完成C5 Sequence供诊断。a02改为源[0,2)、10FPS、每机位2帧，选中C5/C1/C2/C3/C4/P02；真实6个MRQ job与12条RGB/号码输出记录全部success。P1产出12 RGB、12实例mask、12号码mask、120人物记录；各机位标定位置/焦距与计划一致。它是机位接线短样，不是完整episode、新body12或截断/遮挡正式准入。

全部EXR消费后按精确12项清单删除118246669字节，不保留原深度/Cryptomatte。MRQ终态后仅新P02相机被Editor标记dirty；核对实际参数仍等于配置后保存该自有包，clean/idle正常退出。退出门禁首次阻止退出期间CPU后处理已启动，但MRQ/GPU采集已结束；未开展渲染与导出重叠功能或训练。有效PNG与预览图均按test收据保留24小时，关键小收据独立保留Saved。

证据入口：

- `Saved/CameraRigV2/configuration_intent.json`及`configuration_complete.json`：九机位修改前参数和真实回读。
- `Saved/CameraRigV2/preview_s1048_a01/preview_complete.json`：静态捕获与恢复，10次含1张未就绪诊断，9张有效。
- `Saved/CameraRigV2/camera_rig_s1048_a02/postprocess_complete.json`及`exr_cleanup_complete.json`：六机位真实MRQ、导出与精确清理。
- `Saved/Pose17Development/editor_camera_rig_v2_a01.log`：本次启动、原失败、修复及正常退出日志。

本轮不训练、不读取真实或封存测试、不修改旧数据集，不发布正式版本。用户验收本项后，才继续完整单seed生成。
