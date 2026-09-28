# FutsalPlayerBase 闭包与项目减重设计

## 目标

将现役 `FutsalPlayerBase` 角色运行所需的项目自有资产集中到 `/Game/FutsalMOT/Characters/FutsalPlayerBase/`，使用统一的 FutsalPlayerBase 命名，形成可解释的角色闭包；同时对整个 UE 项目做引用、软路径、配置和目录扫描，删除已确认废弃且没有有效引用的项目内容。UE Mannequins 模板系统及其贴图、材质、网格、骨架、动画和 Control Rig 资源全部保留。

## 当前闭包范围

根资产：

- `BP_FutsalPlayerBase`
- `BP_FutsalPlayerControllerBase`
- `ABP_FutsalPlayerBase`
- `BPI_FutsalPlayerBaseAnimation`
- C++ `AFutsalPlayerBase` / `UFutsalPlayerAnimInstance`

项目自有运行依赖：

- `BS_FutsalPlayerBase_Locomotion`
- Idle、Jump、Fall、Land 及 16 个 Walk/Jog locomotion 序列
- `CR_FutsalPlayerBase_FootIK`
- `IKR_FutsalPlayerBase`
- `SK_FutsalPlayerBase`
- `SKM_FutsalPlayerBase`
- `PHYS_FutsalPlayerBase`
- FutsalPlayerBase 材质、材质实例和贴图
- `IA_Futsal_*`、`IMC_Futsal_*`、`BPI_FutsalTouchInterface`

共享保留依赖：

- `/Game/Characters/Mannequins/**` 全目录保留，不移动、不复制、不重命名、不删除。
- 球场、球、相机、Pose/MRQ 和正式 Sequence 不属于角色闭包，不移动到角色目录。
- `Intermediate/CppMigrationBackup/**` 暂作为迁移证据保留，除非后续单独确认删除。

## 目标目录与命名

角色目录目标结构：

```text
/Game/FutsalMOT/Characters/FutsalPlayerBase/
  Animation/
    ABP_FutsalPlayerBase
    BlendSpaces/BS_FutsalPlayerBase_Locomotion
    ControlRig/CR_FutsalPlayerBase_FootIK
    Retarget/IKR_FutsalPlayerBase
    Sequences/A_FutsalPlayerBase_*
  Blueprints/
    BP_FutsalPlayerBase
    BP_FutsalPlayerControllerBase
    BPI_FutsalPlayerBaseAnimation
    Input/
      IA_FutsalPlayerBase_*
      IMC_FutsalPlayerBase_*
      BPI_FutsalPlayerBaseTouchInterface
  Mesh/
    SKM_FutsalPlayerBase
    PHYS_FutsalPlayerBase
  Skeleton/SK_FutsalPlayerBase
  Materials/M_FutsalPlayerBase_* and MI_FutsalPlayerBase_*
  Textures/T_FutsalPlayerBase_*
```

迁移规则：

- 资产路径通过 UE AssetTools move/rename 更新，禁止文件系统移动 `.uasset`。
- 输入资产在闭包内统一使用 `FutsalPlayerBase` 前缀；同时修复蓝图引用、配置引用和测试夹具中的生产期望值。
- 已有 `FutsalPlayerBase` 前缀的动画、网格、骨架、材质和贴图保留名称，只调整目录或补足缺失的规范前缀。
- UE Mannequins 资产保留原路径和原名称。
- Sequence 名称先按上一阶段方案去掉 `_Canonical`，恢复为 `LS_Cam_02`、`LS_Cam_03`、`LS_Cam_04`、`LS_Cam_Main`、`LS_Cam_P01`；Sequence 不移动到角色目录，避免混淆相机/数据管线职责。

## 全项目减重规则

删除候选必须同时满足：

1. 不在 `/Game/Characters/Mannequins/**`。
2. 不在现役 FutsalPlayerBase 闭包、正式地图、正式 Sequence、Python runtime 配置或插件入口中。
3. Asset Registry 无项目内硬引用、软引用、管理引用或搜索名称引用。
4. 文本配置、Python、Blueprint/Sequence 资产反向扫描没有路径或名称引用。
5. 删除后可以通过 UE AssetTools 删除，并能在删除后重新加载和验证正式资产。

明确保留：

- UE Mannequins 模板全目录及其依赖。
- 当前 FutsalPlayerBase 角色闭包。
- `/Game/FutsalMOT/Maps/L_FutsalCourt`、正式球场材质和几何。
- 所有当前生产 Sequence，包括新命名的五条 Sequence 与 `LS_Cam_01`。
- 当前 Pose/MRQ 运行链中仍被引用的资产。
- 仍被配置、代码或插件引用的公共资产，即使目录名看起来旧。

## 执行顺序

1. 恢复/加载 `L_FutsalCourt`，确认所有保护资产和工作区状态。
2. 生成现役闭包 manifest，记录依赖、引用、dirty 状态和目标路径。
3. 用 UE AssetTools 迁移输入资产及其它跨目录项目自有闭包资产，按目标命名更新引用。
4. 将五条 `_Canonical` Sequence 重命名为正式名称，确认内容、绑定、相机内外参和 Python mapping 保持一致；删除 `LS_Cam_Long_30s`（用户已确认它是旧测试 Sequence）。
5. 对迁移后的角色、AnimBP、Sequence、地图执行加载、编译和引用验证。
6. 对整个 `/Game` 生成删除候选，逐项排除共享/模板/软引用/配置引用，形成最终删除清单。
7. 通过 UE AssetTools 删除最终清单中的废弃资产；每次删除后重新查询引用。
8. 运行 Python 测试、task validate/resolve、UE 编译和日志检查，审查外层和内层 Git diff。

## 停止条件

- UE Editor 未加载 `L_FutsalCourt` 或 Asset Registry 状态不稳定。
- 移动/重命名后任何资产出现丢失引用、dirty 扩散或加载失败。
- 当前 AnimBP、角色蓝图、Sequence 或地图编译失败。
- 任何模板资产、贴图、材质、网格、骨架或物理资产进入删除候选。
- 删除候选仍有未解释的项目内引用或软路径引用。
- Python 配置/测试与新路径不一致。

## 验收标准

- 项目自有 FutsalPlayerBase 运行闭包集中在目标目录，输入资产也在该目录下并使用规范名称。
- UE Mannequins 模板目录保持完整且路径未改变。
- 五条正式 Sequence 使用无 `_Canonical` 后缀的正式名称，十名球员绑定当前 `BP_FutsalPlayerBase_C`，相机内外参不变。
- `LS_Cam_Long_30s` 删除后没有配置、代码或 Asset Registry 引用残留。
- 角色蓝图、AnimBP、正式地图和所有保留 Sequence 可加载并编译。
- Python 默认测试通过，所有修改后的 task 配置可 validate/resolve；两个 Git 仓库边界保持正确。
