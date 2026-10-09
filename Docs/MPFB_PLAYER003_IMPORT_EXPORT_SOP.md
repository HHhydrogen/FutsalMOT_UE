# MPFB Player_003 导入导出 SOP

本文档固化 Player_003 当前已经验证的 Blender → FBX → Unreal Engine 流程。后续 Agent 处理 Player_003 时，必须以当前 Blender 源文件和本 SOP 为准，不得直接复用历史中间 FBX。

## 权威资产

### Blender 源文件

```text
D:\projects\FutsalMOT_blender\characters\Player_003\MPFB_Player_003.blend
```

源文件约束：

- Scene Units：`METRIC / METERS / 1.0`。
- 原始 `Human` 对象 scale：`1,1,1`。
- 原始 `Human.rig` 对象 scale：`1,1,1`。
- 原始 `Human.rig`：53 根骨骼，根层级为 `Root -> pelvis`。
- 源文件只保留米制数据；不要把厘米转换直接写回源对象。
- 导出完成后不要保存临时 Export Copy 对源文件造成的任何变更。

### Blender 自动导出脚本

```text
tools/export_player003_sop.py
```

标准输出：

```text
D:\projects\FutsalMOT_blender\characters\Player_003\export\MPFB_Player_003_SOP.fbx
```

导出前后的临时集合名：

```text
Player003_ExportCopy
```

该集合必须在 FBX 写出后删除。

### UE 正式资产

```text
/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003
```

正式资产必须复用：

```text
/Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base
/Game/FutsalMOT/Characters/MPFB/Core/Retarget/IKR_MPFB_Base
/Game/FutsalMOT/Characters/MPFB/Core/Retarget/RTG_FutsalPlayerBase_To_MPFB
/Game/FutsalMOT/Characters/MPFB/Core/Retarget/ABP_MPFB_RuntimeRetarget
```

## 已知问题与根因

### 1. Human body 多出一层衣服

源 `Human` 网格不是可以直接无条件导出的原始顶点集合。它包含两个决定可见外观的 Mask modifier：

```text
Hide helpers
Delete.shoes06
```

正确的手动 Legacy FBX 中，`Human` 的导出结果约为：

```text
11,134 vertices
11,114 polygons
```

旧自动导出脚本使用：

```python
use_mesh_modifiers=False
```

于是导出了未经过 Mask modifier 评估的 `Human` 数据：

```text
19,158 vertices
18,486 polygons
```

这会把本应被隐藏的服装/辅助几何保留在 `Human_body` 槽位中，再与独立的 jersey/shorts 网格重叠，表现为角色多穿了一层衣服。

当前脚本必须使用：

```python
use_mesh_modifiers=True
use_mesh_modifiers_render=True
```

不要通过删除源 modifier、隐藏独立服装对象或修改材质槽来掩盖这个问题。正确修复是在 FBX 导出时评估源 modifier。

### 2. 裤子向上偏移

源裤子对象：

```text
Human.futsalmot_shorts_male_v2
```

源对象的局部位置：

```text
location.z = -0.067081 m
```

手动正常 FBX 的父级 Armature object scale 为 `1.0`，所以该局部位移保持为 `-0.067081 m`。

Player_002 兼容的厘米结构要求：

```text
Mesh data × 100
Armature data × 100
Armature object scale = 0.01
```

如果只把 Armature object scale 改为 `0.01`，却保留裤子的局部位置为 `-0.067081`，UE/FBX 层级会把该局部位置再次缩小 100 倍，裤子会向上移动约 `6.6 cm`。

因此脚本必须对所有直接挂在 `Human.rig` 下的 Mesh 子对象补偿局部位置：

```python
obj.location = src.location / EXPORT_ARMATURE_OBJECT_SCALE
```

对于 Player_003 裤子，这会把导出副本位置转换为约：

```text
-6.7081 cm
```

导入后世界位置才与正常手动 FBX 一致。

## 正确 Export Copy 结构

导出脚本必须执行以下顺序：

1. 从原始 `Human`、`Human.rig` 和所有当前可见子 Mesh 创建独立副本。
2. 将每个副本 Mesh 的 Armature modifier 重定向到副本 Armature。
3. 保留副本 Mesh 的源对象层级。
4. 在副本 Armature scale 设为 `0.01` 前，对直接子 Mesh 的局部位置执行父级缩放补偿。
5. 对副本 Mesh data 执行 `×100`。
6. 对副本 Shape Keys 执行 `×100`。
7. 对副本 Armature data 执行 `×100`。
8. 设置副本 Armature object scale 为 `0.01`。
9. 用 FBX 导出器评估 Mesh modifiers。
10. 只选择副本 Armature 和副本 Mesh 导出。
11. 导出后删除整个 `Player003_ExportCopy` 集合。

关键导出参数：

```python
global_scale=1.0
apply_unit_scale=False
apply_scale_options='FBX_SCALE_NONE'
use_space_transform=True
bake_space_transform=False
add_leaf_bones=False
bake_anim=False
path_mode='COPY'
embed_textures=True
use_mesh_modifiers=True
use_mesh_modifiers_render=True
axis_forward='-Z'
axis_up='Y'
```

不要使用：

```python
use_mesh_modifiers=False
```

也不要用 FBX `global_scale=0.01` 代替数据转换。项目的兼容性依赖 Player_002 已验证的“厘米数据 + Armature object scale 0.01”结构。

## 导出前门禁

自动导出脚本必须在写 FBX 前检查：

```text
源 BODY 高度约 1.69455 m
Export Copy BODY 世界高度约 169.455 cm
Export Copy pelvis head Z 约 93.8268 cm
Export Copy Armature object scale = 0.01
Export Copy bones = 53
所有导出 Mesh Armature modifier 指向 Human_rig
```

如果任一门禁失败，停止导出，不生成可用于 UE 的 FBX。

## UE 导入流程

1. 使用 UE Legacy FBX Importer。
2. 导入为 Skeletal Mesh。
3. 显式复用：

   ```text
   /Game/FutsalMOT/Characters/MPFB/Core/Skeleton/SKEL_MPFB_Base
   ```

4. Import Animations：关闭。
5. Import Uniform Scale：`1.0`。
6. 不创建 Player_003 专属 Skeleton。
7. 不使用 Actor Scale 修正高度。
8. 不使用猜测的 Import Scale 修正高度。
9. 正式材质必须按导出 FBX 的 7 个 Material Slot 绑定：

   ```text
   Human_body
   Human_afro01
   Human_eyebrow001
   材质
   Human_futsalmot_shorts_male_v2_005
   Human_low-poly
   Human_shoes06
   ```

## UE 导入后门禁

导入后的网格必须满足：

```text
Skeleton = SKEL_MPFB_Base
骨骼数量 = 54（包含 Human_rig wrapper）
Bounds 高度约 179 cm
Human body 顶点约 17,813
Human body + 服装总三角形约 30,732
```

导入到 Runtime 测试关卡后：

```text
AnimBP = ABP_MPFB_RuntimeRetarget_C
Root scale = 1,1,1
pelvis Z 约 90 cm
head Z 约 150 到 190 cm
foot Z 接近地面
裤子世界位置与 Legacy FBX 对齐
```

## Runtime 验证

测试关卡：

```text
/Game/FutsalMOT/Tests/MPFB_Runtime/Maps/L_MPFB_RuntimeTest
```

测试角色：

```text
MPFBTest_RuntimeRetargetCharacter
```

可见网格组件：

```text
MPFBVisual
```

Runtime 验证必须确认：

- `MPFBVisual` 使用正式 Player_003 网格。
- Anim Class 为 `ABP_MPFB_RuntimeRetarget_C`。
- 骨骼 scale 全为 `1`。
- head、pelvis、thigh、calf、foot 坐标有限且高度合理。
- 裤子没有整体向上偏移。
- Runtime Pose 采集时明确采样可见 Player_003 网格，而不是测试角色中第一个基础 `CharacterMesh0`。

## 数据集接入边界

正式地图 `/Game/FutsalMOT/Maps/L_FutsalCourt` 当前 10 个 Player Actor 仍使用 `BP_FutsalPlayerBase` 的基础 `CharacterMesh0`。Player_003 验证通过不等于正式地图已批量换装。

如果要让数据集使用 Player_003，必须明确完成其中一种配置：

1. 为 Player_003 创建正式角色 Blueprint，并让 Actor mapping 指向该角色；或
2. 在导入/生成数据集的目标 Actor 上明确替换唯一可见 SkeletalMeshComponent；或
3. 修改 Pose/几何标注采样逻辑，明确指定 Player_003 可见组件。

不要因为资产存在就自动批量替换正式地图中的 10 个球员。

## 历史回退资产

当前保留以下回退资产：

```text
/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003_Legacy_Broken
/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003_PreVisualFix
/Game/FutsalMOT/Characters/MPFB/Players/Player_003/MPFB_Player_003_PrePantsFix
```

它们用于回溯和比较，不应作为新的导出源，也不应继续被新 Runtime 测试引用。

## 禁止事项

- 不要直接把 Blender 源对象转换成厘米并保存覆盖源文件。
- 不要关闭 `Human` 的 Mask modifier 后自动导出。
- 不要用文件管理器移动或重命名 `.uasset`。
- 不要用 Actor Scale 修复骨骼或裤子偏移。
- 不要用 `global_scale=0.01` 盲目补偿 FBX 单位。
- 不要在正式地图上未经确认批量替换 10 个球员。
- 不要把 Legacy Broken、PreVisualFix 或 PrePantsFix 当作后续导出输入。
- 不要在两个独立 Git 仓库之间混合提交。
