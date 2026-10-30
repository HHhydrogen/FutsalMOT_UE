# Pose管线接回原seed球衣系统

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

2026年10月25日。用户明确要求复用原有可复现外观系统；[v9现已完整闭合](../research/POSE_V9_RESULTS.md)，转入此接回阶段。原冻结代码和数据仍不改，UE与后续GPU训练继续串行。

## 已有实现及断点

原系统已经实现，不需要再造随机配色器：

- `python/src/grf_ue_bridge/appearance.py`的`build_appearance_manifest`使用`meta.randomness.ue_visual_seed`，独立派生model/skin/kit随机流。旧版v1目录限定Set_01–05，从中确定性选择四个不同Set，分别分配双方外场球员及双方守门员；序列内不重抽。**这不是现有资产总数：当前已有Set_01–15，真实UE已确认15套共60份球衣/短裤材质及贴图资产存在。**
- 标准`python/ue/run_task.py`准备、应用并恢复`provenance/appearance.json`，`episode_appearance.py`通过Jersey/Shorts语义slot绑定材质并读回。
- 1048原清单实际为左外场03、右外场04、左门将05、右门将01；1102为左外场04、右外场02、左门将03、右门将05。两份原清单、visual seed和轨迹摘要均存在，原系统未失效。
- Pose长窗入口`python/ue/pose17_long_window_p2.py`调用独立`pose17_smoke_runner.prepare/submit`，并未走标准appearance事务。其scope本就记为固定roster、不是原天气/外观复现。
- `Source/FutsalMOT/Private/FutsalPose17Library.cpp`的角色override在`SetSkeletalMesh`之后调用`EmptyOverrideMaterials`，并核验新网格默认材质。因而仅在Editor先套球衣也会被PIE校准模型替换清掉。

这是Pose专用路径遗漏了服装接入，不能据此说项目没有seed外观系统，或把v1正式八组数据也判成单色。此前独立配色选择器候选已撤回，不留第二套seed算法。

## 接回方式

保留原appearance v1清单和算法，新增的只是固定Pose角色到原服装清单的桥接。

`tools/appearance/pose_seeded_kit_plan.py`调用原`validate_appearance_manifest`，用原meta、完整轨迹和原ue-profile重验已有清单，不改写原fingerprint或把完整轨迹摘要换成300帧前缀。之后按实体ID提取Jersey/Shorts材质路径，绑定当前十个MPFBVisual。**不采用原manifest中随机的模型或肤色**，以免破坏七模型固定roster、头点标定及当前配对的单因素约束；不接号码v2 WIP。

实际UE阶段必须在native角色override清空材质之后、GPU-LBS预热和正式输出之前应用服装，并记录engine frame、实体/组件身份、语义slot与材质路径读回。不能只在Editor apply一次，不能把CPU清单当作已修复动态渲染。原native的默认材质核验应保留在override步骤；服装步骤另有应用/读回/恢复证据，不删除原门禁来放行。

生命周期：只读确认地图、十实体、资产class及dirty → 原角色override → 仅Jersey/Shorts绑定 → 原角色/骨架/动画及服装读回 → 预热 → MRQ → native落盘 → 服装恢复 → 原角色恢复 → dirty/引用释放。优先C++生命周期钩子，复用已有语义slot、snapshot/restore规则；不在逐帧Python回调中持有新的UWorld/材质对象。

本轮只读CPU桥接已经消费1048/1102真实输入，原四类Set分配完全保留；四项针对检查通过：原分配/输入不变、篡改轨迹或kit拒绝、错误/重复实体拒绝、号码scope拒绝。运行清单在`Saved/AppearancePlanning/seeded_kit_recovery_a01/plan.json`，状态明确为未在UE应用，不能称渲染通过。

## 真实短样验收

2026-10-25已在新DLL `328d5557d03f6e27676a4673dcf3851084bc4633cc91f4546e1bb870abec1046`完成a02两个seed、A/B、四机位各3帧：48张4K RGB、48张实例mask、480条人物Pose，全部保留unknown、diagnostic/not_training及MRQ_syncfalse。实际UE原生契约测试1项通过；四个MRQ均正常完成、材质/相机/角色恢复和自有会话释放通过。B在native模型override之后、GPU预热之前应用球衣，并在实际输出帧逐人读回；没有通过删除旧材质检查放行。

根agent查看过四机位并列图及四角色裁剪：1048外场左黑03/右红04、门将左黄05/右绿01；1102外场左红04/右白02、门将左黑03/右黄05。同源A/B的17点world在此短样逐值相同；8对中帧mask中7对逐像素相同，1048/CineCam_01有61个差异像素，不声称全像素完全一致。正式收据为`Saved/AppearancePlanning/seeded_kit_capture_a02/short_acceptance_root.json`，原图/总览在G数据集的`_staging/`，不入Git。

首版a01被旧OnFrameStart的“必须零材质override”检查拒绝：球衣实际apply/restore成功，但尚未进入Pose采样，并非已有权重损坏。修正为逐slot核对授权服装及其他材质，继续检查mesh/动画/附着和原默认材质；正常退出Editor后编译，新a02全部重渲染，不混用旧失败样本。失败收据保留。

48份EXR已在全部后处理/消费结束后精确退休，释放4,286,219,059字节。清理门禁另修复了Windows保留已退出进程句柄的误拒：实际`GetExitCodeProcess`仍拒绝活动/活动PID重用及未知状态；真实活动与已退出持有句柄两种条件的针对检查通过。原清理清单SHA、不可重放journal及边界检查不变。

此验收只覆盖短样，不等于300帧整批或后续训练已完成。短样最低commit余量约7.1GiB；整批采用明确12线程/队列8，并在每个变体完成恢复/释放后正常退出UE再做6CPU导出，以回收PIE/Lumen缓存。新变体启动和MRQ提交仍执行资源门禁，活动余量低于6GiB只正常取消自有MRQ，不强杀或改pagefile。

## v9结束后的配对验证

先完成v9的78训练/追踪、完整分析、独立实际预算核对和相关进程退出；随后才启动UE。用户已授权此后续，不重复索取同一授权。

第一步用原v1目录中的Set_01–05接回1048/1102原seed分配。Set_06–15同样是已有资产，无须重建；扩展抽样目录时另立版本并保留原v1兼容性，继续复用同一seed算法，不使用号码WIP。四个不同Set ID不等于实际颜色已经足够可区分，短样检查双方和门将的配色、纹理及语义slot，不能把资产存在当作渲染已通过。

同运动、同相机A/B：

| 组 | 服装 | 其余内容 |
| --- | --- | --- |
| A | Pose当前默认服装基线，重新渲染 | 固定同一模型/肤色、运动、相机、地板、天气、灯光及MRQ配置 |
| B | 接回原seed球衣/短裤清单 | 与A相同，只有服装绑定不同 |

1048仍train、源[0,300)；1102仍synthetic_dev、源[20,320)。各四机位、300帧、10FPS、原生4K，同seed所有版本和机位保持同split。首先两个seed各A/B×四机位×3帧，共48张一次性短样，覆盖两seed实际使用的Set_01–05及各角色；通过后才完成两seed的A/B共4800对RGB/mask及48000逐视角人物Pose。短样不是重新逐模型近景审核。

A必须与B用同一新执行版本重渲染，不能把历史RGB直接当新实验基线。实际微小world差异保留并如实报告，不平均、不用容差伪造exact。原v1、120帧试产、30秒地板配对及v9输入保持原样。此A/B把颜色和服装纹理作为一个既有系统恢复因子，不单独宣称颜色或纹理的因果贡献；有必要时再用原系统的材质变体做分因素配对。

## 后续训练与判断

主实验固定旧v9的S候选框、窗口UID、身份标签及相机/源帧对应，所有A/B在同一框上提取同预训练模型的Pose，R预测缓存完全复用。这样服装只经预测Pose进入关联特征，不因新增/消失检测改变主实验的S监督pair预算；这是固定旧检测框的条件结论，不是端到端检测泛化结论。全图检测响应只能另报次要结果，不替换主输入或按GT匹配过滤预测。

每臂仍1000实际更新、同3000R窗口同序，混合另1000S同序及相同已知pair标签；使用有界预取2，相同初始化、数值精度和last评价。预定canonical v9 gated在A/B各三fold×三seed，共18个新RS训练；只有数值代码、R输入、初始化和预算绑定完全相同时，才复用v9纯R及motion参考，避免重训数学上相同的组，否则另立公平完整对照。训练协议/准入须在真实发布、安全退出及预测来源绑定后单独冻结。

分别报告B−A服装恢复作用、B−纯真实的合成边际、B−motion_RS的Pose增量，以及两预训练参考。保留每比赛/seed及负结果；固定旧检测不直接输入RGB，不把颜色更丰富自动当作关联收益。增加队内/跨队困难候选分层，检查收益是否仅来自队间容易区分，而非同队身份连续性。1102只作合成开发，不用于训练、筛配色或挑最好结果；最终116/187及test包继续封存。

## 存储与清理

新媒体只在`G:/FutsalMOT_Dataset/_work/<attempt>/raw`、`_staging/<attempt>`及独立`v3_pose17_seeded_kit_pair_a01`成品，旧版本不覆盖。Saved只放清单、轨迹/native和小收据，训练代码/模型/结果只放D研究根。每个变体后处理和所有EXR消费者结束后立即按清单清理EXR，保留RGB/mask/Pose/world/校准与成功收据；不积压到训练结束。UE与GPU训练串行，不结束用户游戏、不改pagefile，沿用真实commit余量和自有MRQ安全取消门禁。
