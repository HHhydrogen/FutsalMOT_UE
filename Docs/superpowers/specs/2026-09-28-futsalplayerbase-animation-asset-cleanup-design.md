# FutsalPlayerBase 动画资产清理设计

## 目标

将项目保留为一条清晰的 FutsalPlayerBase 动画生产链：C++ `AFutsalPlayerBase` 与 `UFutsalPlayerAnimInstance`、规范 `BP_FutsalPlayerBase`/`ABP_FutsalPlayerBase`、当前 locomotion BlendSpace、Jump/Fall/Land/Idle 序列及当前 FootIK ControlRig。创建 canonical Sequence 替代仍绑定旧角色类的序列，验证 Python 入口适配后清理旧角色测试管线；保留 UE Mannequins 模板动画系统、贴图和建模资产。

## 已确认的运行事实

- 当前正式关卡是 `/Game/FutsalMOT/Maps/L_FutsalCourt`。
- 当前角色蓝图是 `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase`，动画蓝图是 `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase`。
- 当前 AnimBP 依赖 `BPI_FutsalPlayerBaseAnimation`、`BS_FutsalPlayerBase_Locomotion`、Idle/Jump/Fall/Land 序列和 `CR_FutsalPlayerBase_FootIK`。
- 正式 Court、`LS_Cam_01` 和保留的 `LS_Cam_Long_30s` 使用当前角色蓝图。
- `LS_Cam_02`、`LS_Cam_03`、`LS_Cam_04`、`LS_Cam_Main` 和 `LS_Cam_P01` 仍以旧 `BP_FutsalCharacterBase_C` 作为球员 possessable class。UE 5.8 当前 API 无法保证原位重绑保留 GUID/轨道；用户已批准创建新 Sequence 替换旧资产，保持相机内外参并验证 Python 适配。
- 旧动画链为 `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource`、`/Game/FutsalMOT/Animation/BS_Futsal_Locomotion` 和 `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource`，由旧角色蓝图/测试关卡引用。
- UE 模板资产位于 `/Game/Characters/Mannequins/**`，明确排除清理。

## 清理范围

在完成绑定迁移并验证后，删除旧测试管线资产：

- `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test`
- `/Game/FutsalMOT/Test/GM_FutsalInputTest`
- `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`
- `/Game/FutsalMOT/Characters/Base/BP_FutsalPlayerControllerBase`
- `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource`
- `/Game/FutsalMOT/Animation/BS_Futsal_Locomotion`
- `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource`
- `/Game/FutsalMOT/Input/**` 中只属于旧测试角色的动作、映射和 Touch Interface 资产

先创建以下并行替代资产，验证通过后再删除对应旧 Sequence：

- `/Game/FutsalMOT/Sequences/LS_Cam_02_Canonical`
- `/Game/FutsalMOT/Sequences/LS_Cam_03_Canonical`
- `/Game/FutsalMOT/Sequences/LS_Cam_04_Canonical`
- `/Game/FutsalMOT/Sequences/LS_Cam_Main_Canonical`
- `/Game/FutsalMOT/Sequences/LS_Cam_P01_Canonical`

不得删除或修改正式 `L_FutsalCourt`、任何 `LS_Cam_*` Sequence、当前 FutsalPlayerBase 动画/角色资产、Mannequins 模板、贴图、材质、网格、骨架或物理资产。`Intermediate/CppMigrationBackup/` 中的迁移备份不在此次范围内。

## 执行顺序与门禁

1. 记录所有 Sequence 当前绑定名称、GUID、possessable class、轨道摘要及 dirty 状态；确认目标资产未有未保存修改。
2. 以旧五条 Sequence 为只读基线，创建对应 `_Canonical` 资产，复制 Camera Cut、相机/球员/球员运动轨道、播放范围和帧率；球员绑定指向正式 Court 中当前角色。
3. 比较新旧相机 Actor、焦距、Filmback/传感器尺寸、分辨率、相机变换与关键帧、Camera Cut、播放范围/帧率、球轨道及球员轨道语义。
4. 扫描 Python task 配置和 UE Python 入口，将运行时 Sequence 路径切换到 `_Canonical`；运行 task validate/resolve 和实际 UE Sequence 读取/绑定诊断。
5. 所有新 Sequence、相机参数和 Python 适配验证通过后，才通过 Unreal AssetTools 删除五条旧 Sequence 及已批准的旧测试关卡/角色/动画/输入资产；不直接从文件系统删除 `.uasset`。
6. 重查当前 ABP 依赖、正式地图和保留序列引用；编译当前角色和 AnimBP，并执行适配后 Python 流程验证。
7. 检查 UE 日志并审查外层 Git diff，只保留本次 Sequence 替换、Python 路径适配及旧测试资产清理；不提交或推送。

## 风险与回退

新 Sequence 创建、迁移和删除均通过 UE Editor 资产 API 执行。任何相机参数差异、绑定解析失败、Python 入口不兼容、加载/编译错误、非目标资产 dirty，或引用图仍指向旧 Sequence/旧类时立即停止并保留旧资产。每个删除操作前再次核验路径在批准清单内；保留当前角色动画、模板内容、贴图/建模和 canonical Sequence。

## 验收标准

- 五条 `_Canonical` Sequence 的球员绑定均使用当前 `BP_FutsalPlayerBase_C`，绑定名和轨道语义与源 Sequence 对应。
- 五条 `_Canonical` Sequence 的相机内外参、Camera Cut、播放范围和帧率与源 Sequence 一致。
- Python 配置和 UE Python 入口已使用 canonical Sequence 路径，并通过适配测试。
- 正式 Court、`LS_Cam_01`、`LS_Cam_Long_30s` 的资产和绑定状态保持不变。
- 旧测试角色/动画/输入资产删除后，当前角色 AnimBP 与角色蓝图可加载并编译，当前动画依赖完整。
- `/Game/Characters/Mannequins/**`、贴图、材质、静态/骨骼网格、骨架和物理资产未被删除。
- Asset Registry 对已删除的旧动画链不再报告项目内有效引用；最终外层 Git diff 不包含内层 Python 文件或无关生成文件。
