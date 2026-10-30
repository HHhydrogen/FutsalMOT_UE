# 当前单seed数据契约

2026-10-29。新数据生成统一使用[single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)。本文件描述当前精简导出；旧无号码v1、Pose17位置试产及其group/clip目录只属于历史数据，不能据旧格式配置新任务。

## 权威定义与目录

机器可读定义位于[`python/schemas/single_seed_v1`](../../python/schemas/single_seed_v1/)，包括seed manifest、逐帧标注、轨迹、相机metadata/state和body12点序。运行清单由[`single_seed_generation_v1.json`](../../python/configs/single_seed_generation_v1.json)准备并冻结；实际协议、源码快照、原轨迹、native和收据保留在`Saved/SingleSeed/<attempt>`。外观、天气、地板、号码与机位使用同一recipe记录各自独立随机流。

```text
seed_<8位hex>/
  seed_manifest.json
  trajectory.jsonl
  <camera_id>/
    camera.json
    annotations.jsonl
    img1/000001.png ...
    mask/000001.png ...
    number_mask/000001.png ...
```

没有额外groups/clips/cameras父层级；MOT/YOLO等派生标签不是本目录中的第二份权威标注。正式多seed根manifest、split与发布仍待单seed完整验收后实现。当前诊断协议的`diagnostic_only=true`及schema中`split=dev`不代表已经进入正式dev集。

## 帧、身份与像素

- RGB为3840×2160三通道PNG，10FPS；文件及`frame_index`从1开始，`source_step`从0开始，时间为`source_step / fps`。完整源首次done停止，不reset、补帧或按运动活跃窗口截取。
- 每个camera的每帧固定保留十名球员，实体为L0–L4/R0–R4；ID、球队、角色、号码与双mask ID由seed manifest唯一映射。不可见球员也保留记录。
- 人物mask为单通道uint8：0背景，1–10分别对应十人。号码mask为单通道uint8：0背景，32–41对应十人整块号码印花，不是OCR逐数字字符分割。
- 人物bbox与号码bbox均为对应mask的非零像素tight box，半开XYXY `[x1,y1,x2,y2]`；没有可见像素时为null。号码非零像素须属于同一球员实例，错属阈值为0。
- `annotations.jsonl`是bbox、身份、号码、Pose及逐帧相机状态的唯一权威记录；mask提供同步像素监督。

## 号码、Pose和可见性

`jersey_number_visible`表示当前号码mask有非零像素；`jersey_number_readable`未人工认证时为false，不能从有mask直接推断人可读或OCR识别成功。`jersey_number_view`由背部方向与相机方向的点积阈值±0.5区分back/front/side。

Pose固定为`futsal_body12_v1`：左右shoulder、elbow、wrist、hip、knee、ankle，按schema定义交替排列十二点。采样来自实际可见MPFBVisual，world/native在项目Saved保留；导出点为相机投影像素坐标，相机后方点为null，画面外点不强行裁到边界。visibility枚举为0 unknown/invalid、1 occluded、2 visible；当前未建立物理遮挡证据，全部保留0。

人物有实例像素时visibility为visible；投影bounds完全出画时为out_of_frame；其他无像素情况为unknown，不擅自判定occluded。`truncated`由动画mesh bounds投影与画面相交且伸出边界判定，不由tight box边缘反推amodal人体。

## 相机、轨迹与来源

每seed固定C5/C1/C2/C3/C4，再从P01–P04独立选择1–2个；实际camera集合必须等于该seed事前冻结清单，不要求不同seed的随机局部机位一致。

`camera.json`包含UE actor/Sequence、宽高、焦距/FOV、像素内参与profile SHA；逐帧实际位置（米）、旋转（UE pitch/yaw/roll，度）、焦距和FOV位于annotation的`camera_state`。共享`trajectory.jsonl`以米和米每秒记录十人位置、速度、队伍、角色、active及连续step/time；不能用逐机位骨骼差异平均值替换原始来源。

`seed_manifest.generation`绑定protocol、code bundle、attempt与capture receipt SHA。代码、DLL、配置或轨迹改变后必须新建attempt/协议，不修改旧冻结协议来恢复运行。校验器从冻结清单构造唯一文件集，核对闭合schema、帧数/ID、双mask/bbox、相机、Pose及来源绑定；校验失败不能通过放宽字段或忽略额外文件发布。

旧内部`meta.json`、`frames.jsonl`、provenance和resolved task仍供当前底层模块交换数据，它们属于运行输入/收据，不是公开生成入口或新seed导出布局。历史契约可从[清理前Git版本](https://github.com/HHhydrogen/FutsalMOT_UE/blob/a2f488a506266242b4e5223609774a8d6f87b56a/Docs/engineering/DATA_CONTRACT.md)追溯。
