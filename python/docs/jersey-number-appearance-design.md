# 可复现球员外观中的球衣号码设计

2026-10-29版本说明：本文保留旧decal v2候选设计；实际已人工验收并固化的实现是原appearance v1随机外观之上的UV印花与同网格蒙皮mask，入口见[当前实现](../../Docs/engineering/SEEDED_APPEARANCE_UV_NUMBERS.md)。旧decal apply/restore仍未启用，不能将本文候选机制当作当前生产路径。

## 1. 目标与范围

在现有 seeded episode appearance 流程中，为十名球员增加可复现的球衣号码，并在
数据集导出时记录背部号码的可见 bounding box。

本设计满足以下约束：

- 号码由 `ue_visual_seed` 确定性生成。
- 号码范围为 `1..99`，同一 episode 内十名球员不重复。
- 号码只显示在球衣背部。
- 号码跟随球员动画和 Actor 变换。
- 现有球员 RGB、Instance-ID Mask、MOT、YOLO Detect、YOLO Segment 和 Pose 契约保持兼容。
- 号码 bbox 表示实际可见号码像素，不把理论投影框当作可见框。
- apply/restore 结束后不向关卡保存本次随机号码组件或动态材质实例。

本次不把号码作为新的 MOT/YOLO 类别，也不改变球员的 `track_id`、`mask_id` 或检测 bbox。

## 2. 方案选择

### 2.1 推荐方案

使用一个共享号码图集、一个共享号码贴花材质，以及每名球员一个临时背部号码组件。
号码组件挂到 `MPFBVisual` 的共享骨骼 `spine_03`，动态材质实例通过 `NumberIndex`
选择图集中的号码。

当前已验证 Player_003 至 Player_009 使用共享的
`/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base`，并且网格都包含
`spine_03`，因此不需要为不同模型制作不同挂点资产。

当前五套球衣材质没有可用的 scalar、vector 或 texture 参数，不能只通过现有材质
参数写入号码。直接复制十套球衣材质也会扩大资产和 shader 维护范围，因此不采用。

### 2.2 可见号码 mask

UE `DecalComponent` 没有可直接用于独立 Custom Depth/Stencil 输出的
`render_custom_depth` / `custom_depth_stencil_value` 属性。因此号码贴花不能单独
提供可见像素 mask。

为了生成可见号码 bbox，增加与背部贴花使用相同变换和轮廓的辅助号码 mask 代理。
辅助代理只参与号码 mask 渲染，不参与 RGB 主图，也不替换现有球员几何或 Instance-ID
Mask。它使用独立的号码 stencil ID，并在相机遮挡关系下生成实际可见像素。

如果当前 UE 5.8 的代理 mask pass 无法可靠输出独立号码像素，流程必须在 apply/MRQ
之前 fail-closed；不能退化为把贴花矩形投影结果标记成可见号码框。

## 3. 数据契约

### 3.1 Appearance 版本

新增号码后使用 `futsalmot_appearance_v2`，manifest schema 名保持
`futsalmot_episode_appearance`，`version` 变为 `2`。v1 manifest 只读兼容，不由新流程
重新生成号码。

新增独立命名空间：

```json
"namespace_seeds": {
  "model": 0,
  "skin": 0,
  "kit": 0,
  "jersey_number": 0
}
```

现有 `model`、`skin`、`kit` 的 seed 和候选排名继续使用
`futsalmot_appearance_v1` 字节协议，保证相同 `ue_visual_seed` 下原有模型、皮肤、套装
分配逐项不变。仅新号码命名空间使用 v2 policy：

```text
SHA256(UTF8("futsalmot_appearance_v2:<ue_visual_seed>:jersey_number"))
```

取 digest 前四字节的大端无符号整数，并与 `0x7fffffff` 做按位与。

### 3.2 号码配置

catalog 和 manifest 都记录号码配置。路径必须是已导入、可由 UE 读取的 `/Game/` 资产
路径：

```json
"numbering": {
  "min": 1,
  "max": 99,
  "unique": true,
  "placement": "back",
  "bone": "spine_03",
  "atlas": "/Game/FutsalMOT/Characters/MPFB/Textures/JerseyNumbers/T_MPFB_JerseyNumbers_01_99",
  "decal_material": "/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_JerseyNumber_Decal",
  "parameter": "NumberIndex",
  "mask_proxy_mesh": "/Game/FutsalMOT/Characters/MPFB/Meshes/SM_MPFB_JerseyNumberMaskQuad",
  "mask_proxy_material": "/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_JerseyNumberMask",
  "mask_post_process_material": "/Game/FutsalMOT/Materials/M_StencilToID",
  "mask_stencil_start": 32
}
```

`NumberIndex` 的值为 `jersey_number - 1`。图集布局、数字描边和材质采样方式属于
UE 资产约束，但布局必须固定并纳入 catalog fingerprint；不能在不同运行中隐式改变。
mask proxy 使用同一图集和 `NumberIndex` 选择不透明数字轮廓；其 Custom Depth Stencil
值按实体固定为 `mask_stencil_start + entity_index`，其中 entity 顺序是
`L0..L4,R0..R4`。UE preflight 必须检查该范围未被当前正式地图中其它组件占用。

### 3.3 号码生成

固定实体顺序为 `L0..L4,R0..R4`。对每个实体和候选号码使用 v2 号码排名协议：

```text
SHA256(UTF8("futsalmot_appearance_v2:rank:jersey_number:<seed>:<entity_id>:<number>"))
```

按 digest 和号码字符串排序后，依次为十个实体选择尚未使用的号码。该算法保证：

- 同一 `ue_visual_seed`、同一 meta 和同一 catalog 得到相同结果。
- 不同 seed 可以改变号码。
- 同一 episode 内号码不重复。
- 号码不会依赖 Python `hash()`、进程随机状态或全局 RNG。

每个 manifest entity 增加：

```json
{
  "entity_id": "L0",
  "jersey_number": 37
}
```

### 3.4 可见号码 bbox

号码 bbox 写入现有 `annotations.jsonl` 的球员 object 内，不创建新的 object，不改变
球员的主 bbox：

```json
"jersey_number": {
  "value": 37,
  "placement": "back",
  "bbox_source": "visible_number_mask",
  "in_frame": true,
  "truncated": false,
  "visible_pixel_count": 214,
  "bbox_xyxy": [812.0, 244.0, 839.0, 278.0],
  "bbox_xywh": [812.0, 244.0, 27.0, 34.0]
}
```

号码完全不可见时：

```json
"jersey_number": {
  "value": 37,
  "placement": "back",
  "bbox_source": "visible_number_mask",
  "in_frame": false,
  "truncated": false,
  "visible_pixel_count": 0,
  "bbox_xyxy": null,
  "bbox_xywh": null
}
```

`value` 始终保留，bbox 字段只描述当前相机和当前帧中可见的号码像素。号码 bbox 不
进入现有 `gt/gt.txt`、`labels/det`、`labels/seg` 或 Pose 标签。

## 4. P1/P2 数据流

### 4.1 P1 导出与 manifest

`task export` 在轨迹成功写出后构建 appearance v2 manifest，并立即按当前
`meta.json`、`frames.jsonl` 和 catalog 重验。号码结果和号码配置参与 manifest fingerprint。

P1 只处理 JSON/JSONL，不导入 `unreal`，不创建或修改 UE Actor。

### 4.2 P2 appearance apply

在现有 appearance preflight 通过后：

1. 预加载号码图集、号码贴花材质和辅助 mask 代理所需资产。
2. 检查十名 Actor、`MPFBVisual`、`spine_03` 和所有号码资产。
3. 为每名 Actor 创建或复用唯一的 `JerseyNumberBack` 号码组件。
4. 组件挂到 `MPFBVisual` 的 `spine_03`。
5. 设置背部相对变换、贴花尺寸、材质实例和 `NumberIndex`。
6. 创建同变换的号码 mask 代理，并设置对应号码 mask ID。
7. 回读组件父级、挂点、材质、号码索引、可见性和渲染开关。
8. 任何一项失败都不提交 MRQ，并进入恢复流程。

号码组件和辅助代理均为临时事务状态，不保存为关卡资产。共享图集和材质只读加载，
不在运行中修改材质 graph 或纹理。

### 4.3 MRQ 与 mask

RGB、现有 Instance-ID Mask 和号码 mask 必须使用相同 Sequence、camera、分辨率、
播放帧率和目标帧映射。

建议的临时目录：

```text
<camera>/render_number_mask/
<camera>/number_mask/
```

`render_number_mask/` 保存 MRQ scratch 输出，`number_mask/` 保存与 canonical
`img1/` 对齐的号码 mask。号码 mask 的像素值编码 entity 的号码 mask ID，不复用球员
1..11 的 Instance-ID 值。

P1 后处理按号码 mask ID 统计每帧每名球员的非零像素，计算 pixel-tight bbox 并写入
`annotations.jsonl`。如果 mask 缺帧、分辨率不一致、号码 ID 冲突或 mask 解码失败，
对应 task audit 失败。

### 4.4 restore

rollback snapshot 升级为 v4，记录每名 Actor 的号码组件存在性、组件路径、父组件、
挂点、相对变换、贴花尺寸、材质和可见性。

- baseline 没有号码组件：restore 删除本次创建的 `JerseyNumberBack` 和号码 mask 代理。
- baseline 已有合法号码组件：restore 精确恢复原组件状态。
- 组件重复、类型不匹配、路径无法解析或 readback 不一致时保留 rollback 证据并失败。
- 恢复后重新检查十名 Actor、组件状态和 External Actor package dirty 状态。

异步 MRQ 在所有 camera job 到达终态前保持号码组件有效。所有 job 完成、失败或取消
后才执行 restore，并沿用现有 `appearance_application.json` 状态机。

## 5. application report 与审计

`appearance_application.json` 的每个 actor 增加：

```json
{
  "jersey_number": 37,
  "number_component": {
    "name": "JerseyNumberBack",
    "bone": "spine_03",
    "placement": "back",
    "apply_status": "applied",
    "restore_status": "not_started"
  }
}
```

Audit 增加以下检查：

- manifest v2 的十个号码完整、整数、范围合法且无重复。
- application report 的号码与 manifest 一致。
- apply/rendering 状态下十名号码组件均为 applied。
- restored 状态下十名号码组件均为 restored。
- `annotations.jsonl` 的号码值与 manifest 一致。
- `visible_pixel_count` 与号码 mask 像素数一致。
- 可见号码 bbox 与号码 mask 的 min/max 一致。
- bbox 位于图像边界内，宽高为正。
- RGB、号码 mask 和 annotations 的 frame 集合完全一致。
- 现有球员 Instance-ID Mask 的值域仍为背景 `0` 和实体 `1..11`。

## 6. 测试与验收

### 6.1 P1 纯 Python 测试

- v2 namespace seed 字节协议稳定。
- 同输入 manifest 完全相同。
- 十个号码范围为 `1..99` 且无重复。
- 不同 seed 可以改变号码。
- 号码配置和 entity 号码参与 fingerprint。
- manifest v1 只读兼容路径不会静默补号码。
- 非法范围、重复号码、缺失号码配置和非法 fingerprint fail-closed。
- 号码 bbox mask 统计的空帧、边界、紧框和分辨率错误均有测试。
- 现有 MOT/YOLO/Pose 重新派生不读取 `jersey_number`，保持旧输出不变。

### 6.2 UE Editor smoke

使用当前 10 帧、1 相机 appearance smoke：

1. 诊断门禁通过后 apply v2 appearance。
2. 验证十名球员各有一个背部号码组件。
3. 验证号码组件挂在 `spine_03`，不在胸前创建组件。
4. 渲染 RGB、现有 Instance-ID Mask 和号码 mask。
5. 验证正面镜头中号码可按遮挡规则为空。
6. 对背部可见帧验证号码 mask、bbox 和 RGB 号码位置一致。
7. 运行 postprocess、annotation validation 和 audit。
8. 完成异步 MRQ 后 restore，确认号码组件移除或恢复到 baseline。
9. 检查地图、External Actor 和共享资产 package 回到 baseline clean 状态。

### 6.3 视觉验收

必须人工确认以下内容：

- 数字贴合背部，没有明显悬空或穿透。
- 数字在跑动、转身和弯腰姿态下仍处在球衣背部。
- 号码没有出现在胸前或短裤上。
- 白字和描边在五套球衣颜色上均可识别。
- 可见号码 bbox 没有把整名球员或贴花投影矩形误当成号码框。

## 7. 版本与兼容策略

- 新 appearance 使用 v2；旧 appearance v1 保持只读验证和旧流程兼容。
- v1 task 不自动生成号码，也不要求号码 mask 或号码 bbox。
- v2 task 缺少号码资产、号码配置、号码 mask 或号码审计结果时失败。
- 不修改现有球员 `track_id`、`mask_id`、MOT/YOLO 类别和 Pose 点顺序。
- 不在 P1 引入 Unreal 依赖，不在 UE Python 导入 NumPy/OpenEXR/OpenCV。
- 资产创建和 UE 侧 material/decal/代理配置属于外层 UE 仓库；manifest、导出、后处理、
  验证和文档属于内层 Python 仓库。

## 8. 实现边界

实现按以下顺序进行：

1. 先实现 P1 v2 manifest、号码分配和纯 Python 契约测试。
2. 再创建共享号码图集、贴花材质和号码 mask 代理资产，并在 UE 中只读核验资产 class
   和参数。
3. 扩展 P2 appearance apply/restore/report，使号码组件纳入现有事务。
4. 扩展 MRQ 号码 mask 输出和 P1 bbox 后处理。
5. 更新数据契约、验证器、audit、smoke 配置和测试。
6. 通过 10 帧 smoke 完成真实 UE apply、MRQ、号码 bbox、restore 和视觉验收。

任何 UE 侧号码 mask API 在连续两次验证失败后停止自动尝试，并标记为
`MANUAL_REQUIRED`，不使用未经验证的反射 API 或文件系统资产替代方案。
