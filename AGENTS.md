# AGENTS.md

## 协作与版本管理

- 项目只有一个Git根：`D:/projects/FutsalMOT_UEDataset`，分支`master`，远端`HHhydrogen/FutsalMOT_UE`。Python目录不再是submodule，不初始化嵌套Git。
- 使用命令行Git精确暂存；不使用`git add -A`、force-push或跳过hooks。提交说明、注释及技术文档使用简体中文。
- 用户已授权四阶段仓库整理和已验阶段成果提交推送；不重复申请同一授权。号码WIP与其他无关改动保留且不混入提交。
- 用户主动删除融合备份，并明确授权删除补建副本；不再自动重建备份。旧历史在统一仓库可达，未提交内容仍是本机WIP。
- 以实现、导出和实验为主。已验方法直接复用，每个新功能做一次必要针对检查；不逐模型重复近景、不重复媒体hash/全像素审计、不为无变化反复报告。

## 当前入口

- 根README负责快速入口；[文档索引](Docs/README.md)负责技术说明；[任务状态](TASK_STATUS_AND_NEXT_STEPS.md)只记当前进度和下一步。
- Python代码位于`python/`，研究脚本位于根`experiments/sim2real/`。先读Python README及[数据契约](Docs/engineering/DATA_CONTRACT.md)、[验证限制](Docs/engineering/VALIDATION_AND_LIMITATIONS.md)。
- 工程规则集中在本文件；Python局部规则不重复Git、存储及运行状态。旧版本的流水和候选计划不覆盖当前状态。

## 存储与生命周期

- 所有渲染媒体（包括临时EXR/RGB/mask）仅写入`G:/FutsalMOT_Dataset`；新raw放`_work/<attempt>/raw`，导出放`_staging/<attempt>`，验收后同卷发布。禁止渲染写D Saved或直接覆盖成品。UE的配置、日志、轨迹、native及运行收据仍在项目原`Saved/`物理目录。
- EXR后处理成功且所有EXR消费结束后立即按精确清单清理，不等不消费EXR的GPU训练结束；未完成/失败任务只保留明确诊断期限与用途。保留RGB、实例mask、Pose/world、轨迹、校准及成功收据。深度研究若需保留，必须在收据中登记用途与范围，不能长期默认堆积。入口与规则见[存储规范](Docs/operations/STORAGE_POLICY.md)。
- 研究输入、不可变执行代码`code/<SHA>`、权重、检查点和结果位于实际`D:/projects/FutsalMOT_Research`。生成图像只引用G成品，不复制4K到研究目录；执行bundle只装必要源码，不另建Git或复制环境。
- D恢复迁移已完整结束，G盘旧Research/Workspace根已移除；不重放旧迁移驱动。P1运行数据位于`Saved/P1/`，运行收据位于`Saved/`，历史协议原路径通过独立relocation解释。
- 统计、复制和清理不跟随junction；不对DataSet目标递归删/搬。冻结协议、源码绑定、轨迹、native、校准和关键收据保留原bytes/SHA，另记relocation映射，不伪造历史路径可运行。
- G盘或D项目外写删按具体范围申请工具自动审批，不能通过junction绕过；拒绝时说明实际动作与原因。
- 23013份冗余媒体已删除638.191GiB，其中7961份EXR的深度/Cryptomatte不再保留；不能据已发布RGB/mask/Pose声称原EXR或物理遮挡证据仍存在。
- AutoSave在项目和本机配置均为False。Git只管理磁盘中的文件，不能恢复尚未保存的Editor内存。
- `Saved/`、`Intermediate/`、`DerivedDataCache/`、虚拟环境、权重和本机运行收据不提交Git。

## 研究与数据边界

- 论文主线为合成Pose相关监督在固定检测下对身份关联的边际作用，见[论文计划](Docs/research/CVPR_2027_PAPER_PLAN.md)。v5–v7位置微调/覆盖/静态时序未证明稳定增益；当前[v8](Docs/research/LEARNED_ASSOCIATION_V8.md)固定共享预训练Pose，单独学习困难候选身份连续性，采用三比赛留一开发和motion/pose×R/RS四单元。预算明确为同3000R窗口、混合另1000S，不冒充图像曝光。最终SNMOT116/187封存，不调测试集、不筛seed/best/比例，不预设提升。
- 用户已授权[v9](Docs/research/POSE_QUALITY_RESIDUAL_V9.md)：分析Pose拖累和外观域差，随后同3000R/额外1000S的质量残差、缺点/噪声消融，重点比较同容量motion分支及v8 motion_RS。主对照三seed，探索消融仅事前登记首seed，不根据结果挑seed或把探索当三seed结论。当前关联器没有RGB输入，颜色/纹理可分不等于拟真不足造成退化；新球衣/成像配对另立数据版本，不改冻结数据。运行状态以任务状态和Saved/ProjectStatus为准。
- 用户已授权下一轮[独立运动与困难事件v10](Docs/research/MULTISEED_HARD_ASSOCIATION_V10.md)：强motion_RS是主要参照，各组同3000R窗口、混合另1000S；新比赛须确认真实比赛身份不与已观察三场重复，不能把同场新clip称独立比赛。先完成来源/短样/完整采集与预测再冻结训练准入，最终116/187及test包封存。
- 所有后续训练遵守[全过程记录](Docs/operations/TRAINING_RECORDS.md)：逐步loss/LR/梯度、R/S UID/epoch/全部及已知pair、来源/环境/曝光链、0/每50/最终完整模型+优化器+RNG、原stdout/stderr、失败和全部评价必须保留在DResearch。历史缺失字段明确标缺失，不补造；检查点不用于挑best。记录工具通过不等新实验端到端训练通过。
- 用户2026-10-27对真实资源替代实验选择“暂不设界限，只报告配对差值和置信区间”。遵守[七比赛方案](Docs/research/REAL_SUPERVISION_SUBSTITUTION_A01.md)，不擅设非劣效/等效界限或通过标志。C为另立的4000R（3000基础R+1000额外R），不伪装S或混入同3000R的Pose结论；新C必须独立schema/实际数值与完整记录门禁。
- 球衣已有appearance v1的独立seed可复现系统；优先[接回原系统](Docs/engineering/POSE_SEEDED_KIT_INTEGRATION.md)，不再另造随机选择器。Pose固定roster只复用其Jersey/Shorts分配，不套原随机模型/肤色；native模型替换会清空材质，必须随后应用并读回。用户已授权v9闭合后开展同运动/相机配对，但CPU候选不等动态通过，不改当前冻结数据或接号码WIP。
- v1八组数据保持不变。Pose试产独立输出；不能将历史12点重命名成17点或事后伪造同帧采样。
- 鼻眼耳按实际渲染mesh校准；可见MPFBVisual与隐藏驱动mesh必须区分。unknown不冒充COCO visible，限定位置准入不等于正式遮挡监督。
- 独立机位world差异保留原值，不平均或用容差冒充逐值exact。地板随机流独立于运动/天气/外观，同运动配对保持同split。
- 用户最新要求后续主训练以原版绿色草地及小幅色调/明暗变化为主；蓝/红保留作诊断，不改旧冻结数据。按[绿色变体方案](Docs/engineering/GREEN_FLOOR_VARIATION.md)复用既有floor seed/catalog算法，序列内固定；纹理、粗糙度先独立研究。原实例无颜色参数，不能猜调`Param`或使用旧蓝RGB冒充绿场；新派生材质和短样必须真实读回验收。
- 用户2026-10-26已取消专门的渲染/导出加速任务；不再开发或接入解码优化、运行性能基准或尝试渲染/导出重叠。沿用已验串行单机位采集、正常退出、后处理及EXR清理，专注绿色/球衣配对和公平实验。现有训练预取继续使用，内存与存储安全门禁保留。
- UE渲染与GPU训练串行；本轮渲染、发布和本次安全退出真正完成后才训练。人工取消遵循最新用户要求，不当软件故障自行重启。
- 活动`started_not_committed`是正常事务；只有真实退出/报错才诊断。硬崩溃超过last的数学更新不猜测重放，不把PID复用误判为旧训练，绝不按旧PID盲目kill。
- 后续训练优先提高实际吞吐和硬件利用率：使用有界解码预取/缓存、控制CPU线程、减少不必要GPU同步；以端到端耗时验证，不仅看占用率。任何活动冻结实验不热改。AMP、批量、同卡并行或验证频率等变化另立明确协议，保持真实曝光公平及测试封存；额外GPU基准不能抢占当前任务。

## UE与MCP必须遵守

- UE5.8，默认地图`/Game/FutsalMOT/Maps/L_FutsalCourt`；实际操作前核验当前Level、PIE/MRQ和dirty包。
- 新增运行时行为、动画采样及稳定数据契约优先C++；适合资产表达的AnimGraph、Control Rig和材质配置不强行重写。
- UE操作先读[完整自动化工作流](Docs/operations/UNREAL_MCP_WORKFLOW.md)，优先真实Unreal MCP，先describe完整toolset再用短tool_name。完整脚本必须在真实UE Python执行，不用sandbox冒充`import unreal`。
- 切图只用原生SceneTools.load_level；切换期间不加载或保留UWorld引用。原生工具不可用或同类API连续失败两次时停止并报告具体限制，不猜测反射回退。
- appearance apply/restore前只读确认规范地图、十人唯一、资产class与package clean。资产移动/删除通过UE API，不从文件系统剪切或删除uasset。
- 重启/退出前核验dirty、PIE/MRQ、关键资产与自有回调。未知未保存改动或活动MRQ不得强杀；安全时自行正常quit、编译、启动、重连并用新鲜日志闭环。
- 旧CPU-render/Lumen蒙皮路径保持submit禁用，使用已验GPU-render/CPU-LBS。native在teardown前落盘，回调只读文件；MCP PRIVATE/独立globals保留，不reload Toolset UClass。
- 历史Py_FinalizeEx→PyGC_Collect退出崩溃具体坏对象仍未知；一次正常退出不称根治，不危险复现。
- 维护MPFB角色先读[生产SOP](Docs/production/MPFB_PLAYER_PRODUCTION_SOP.md)；未验证导入参数不凭经验猜测。Fab目录不提交，资产转入项目须通过UE内容工具修引用。
