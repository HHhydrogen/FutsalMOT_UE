# AGENTS.md

## 当前任务与唯一生成入口

- 先读[根README](README.md)、[任务状态](TASK_STATUS_AND_NEXT_STEPS.md)、[单seed基线](Docs/production/SINGLE_SEED_BASELINE_V1.md)；技术资料见[文档索引](Docs/README.md)，Python局部规则见[python/AGENTS.md](python/AGENTS.md)。任务状态只保留当前进度，历史指令不覆盖最新用户要求。
- **新数据集只使用`tools/dataset/single_seed_task.py`和`tools/dataset/run_single_seed_partitions.py`，配置固定入口为`python/configs/single_seed_generation_v1.json`。** 前者准备/冻结/导出/验证，后者控制分机位采集。旧task/production、旧批量/活跃窗口/旧smoke脚本和1080p配置退出新生成流程；不从Git或Saved恢复旧入口来绕过当前配置。
- `python/ue/run_task.py`及保留的底层库只服务当前管线的内部调用，不直接提交任意resolved JSON。共享模块保留不等于保留第二条生成管线。
- 用户最新要求先清理旧入口/文档，再补容量门禁与完整导出生命周期，**完整3001帧单seed暂不执行**。新代码检查通过不自动授权长渲染；单seed人工验收后才进入正式多seed清单、split、总导出与发布。
- 当前基线为4K（3840×2160）、10 FPS、8/8写出、每机位独立UE串行。C5/C1/C2/C3/C4必选，加P01–P04独立seed选1–2个；每seed相机集合按其事前冻结清单验证，不要求不同seed完全相同。
- 草地用GreenV2 a02（UV60、Normal Flatness0.90、条带±18%、深/标准/浅增益0.60/1.00/1.50）；十五套球衣、号码v2/黑白墨色、天气视觉v2均已确认。不得回退旧蓝/红棕、旧号码默认或旧相机配置。统一随机入口复用原独立namespace与算法，不另造选择器。

## 协作与版本管理

- 唯一Git根`D:/projects/FutsalMOT_UEDataset`，分支`master`，远端`HHhydrogen/FutsalMOT_UE`；Python不是submodule，不初始化嵌套Git。
- 使用命令行精确暂存；不`git add -A`、force-push或跳过hooks。提交说明、注释与技术文档用简体中文。用户已授权的提交推送无需重复确认；已验号码/单seed基线已固化，无关研究WIP、临时Sequence与本机收据不混入。
- 用户已授权移除旧生成管线与过时操作文档。共享依赖、历史冻结证据和不相关WIP保留；不因文件名老旧而删除当前管线依赖。历史由Git追溯，不另建可运行archive或自动重建用户已删除的备份。
- 以实现、导出和实验为主，已验方法直接复用。新增功能只做必要针对检查，不逐模型重复近景、不重复媒体hash/全像素审计，不为无变化反复报告。

## 存储与生命周期

- 临时媒体只写`G:/FutsalMOT_Dataset/test/<attempt>/raw`及该attempt的`export`，不写D项目。UE配置、日志、轨迹/native、冻结协议和关键小收据仍在原`Saved/`物理目录。
- 单seed配置预算1TiB，最低剩余100GiB。容量准入与生命周期的实际实现状态见任务状态；不能仅因JSON存在阈值就声称入口已执行。采集、后处理、验证及EXR清理属于同一活动attempt，不能在每机位MRQ结束就开始整个attempt的清理倒计时。
- 成功媒体在全流程结束后保留24小时；失败诊断须写明用途且最长7天。每天04:00只清理生命周期收据标明已结束且过期的独立test attempt，不清理活动任务或正式数据，不跟随junction。
- EXR后处理成功且所有EXR消费者结束后立即按精确清单清理；保留RGB、整数mask、Pose/world、轨迹、标定和成功收据。深度/Cryptomatte若需保留，须登记具体用途/范围；历史已删EXR不能由RGB/mask倒推为仍有物理遮挡证据。
- 正式生成在单seed验收后建设：raw在G盘`_work/<attempt>/raw`，候选导出在`_staging/<attempt>`，验证后同卷发布新版本。禁止直接覆盖成品。完整规则见[存储规范](Docs/operations/STORAGE_POLICY.md)。
- D恢复迁移已结束，不重放旧迁移驱动。研究输入、最小不可变`code/<SHA>`、权重和结果位于实际`D:/projects/FutsalMOT_Research`；G媒体只引用，不复制4K或环境。冻结协议、源码、轨迹/native与收据保留原bytes/SHA，路径迁移另记relocation，不能伪造旧路径可运行。
- G盘或D项目外写删按具体范围申请工具自动审批，不通过junction绕过；拒绝须报告实际动作和原因。统计/复制/清理不跟随junction；不对DataSet目标递归删搬，Windows文件操作先核实绝对目标范围。
- AutoSave保持False。Git不能恢复未保存Editor内存。`Saved/`、`Intermediate/`、`DerivedDataCache/`、媒体、环境、权重和本机收据不提交Git。

## 数据、研究与证据边界

- 新seed输出遵循[数据契约](Docs/engineering/DATA_CONTRACT.md)与[验证限制](Docs/engineering/VALIDATION_AND_LIMITATIONS.md)：每帧十人，bbox来自实例mask，号码与所属人物像素同步；body12取实际可见MPFBVisual，不能用隐藏driver替代。
- Pose unknown不冒充visible，位置有效性不等于物理遮挡；号码非零像素不等于人可读。新body12、历史12点和Pose17保持各自schema，不改名转换历史数据；独立机位world差异保留原值，不平均或用容差称exact。同运动配对保持同split。
- 原v1八组及所有已冻结研究数据保持不变。最终SNMOT116/187/test封存，不调测试、不筛seed/best/比例，不将已观察比赛新clip称独立比赛。当前生成任务不自动授权真实数据下载、split选择或训练。
- 论文主线为固定检测下合成Pose相关监督对身份关联的边际作用，见[论文计划](Docs/research/CVPR_2027_PAPER_PLAN.md)。既有[v8](Docs/research/LEARNED_ASSOCIATION_V8.md)、[v9](Docs/research/POSE_QUALITY_RESIDUAL_V9.md)、[v10](Docs/research/MULTISEED_HARD_ASSOCIATION_V10.md)的预算、数据边界和负结果保持；旧计划不作为恢复已退役生成管线的命令。不能把颜色可分直接当作当前无RGB关联器退化的原因。
- 后续研究协议写完整绝对参数：模型/可训练层、优化器、LR、输入、batch、更新次数、每步及累计R/S、损失系数、seed、阈值和检查点终点。各方法/面板先列绝对AssA/HOTA/IDF1，再列配对差和CI；缺失明确标缺失，不从delta反推，不跨数据/检测/评价范围比较。
- 同3000R窗口、混合另1000S的协议不称图像曝光；[真实资源替代方案](Docs/research/REAL_SUPERVISION_SUBSTITUTION_A01.md)中额外1000R的C组必须独立schema和实际记录，不冒充同预算。用户未设非劣效/等效界限，不能自行补设通过标志。
- 遵守[全过程记录](Docs/operations/TRAINING_RECORDS.md)：逐步loss/LR/梯度、R/S UID/epoch/pair、来源/曝光、0/每50/最终模型+优化器+RNG、stdout/stderr和全部失败评价留DResearch。历史缺失不补造，不从检查点挑best。
- 每轮训练、校准、诊断或评价结束及失败/中断，由主智能体即时更新[训练历史](Docs/research/TRAINING_HISTORY.md)，作为阶段收尾和提交必做项。登记真实状态、对象/动机、数据来源/数量、绝对参数/预算/结果、全部负结果、局限和证据；零更新与未执行分列。自动跟进只读既有文档/小收据，有新增才更新，不重训/推理/评价/哈媒体或读封存测试。
- 已验吞吐策略按[训练性能规则](Docs/operations/TRAINING_PERFORMANCE.md)复用：有界并行/缓存、CPU线程与GPU同步以端到端耗时验证，保持曝光/损失/初始化/完整记录不变。AMP、前向合并、编译、同卡多臂或验证频率变化另立数值协议；不能热改活动冻结实验或用少更新/少记录称加速。
- UE渲染与GPU训练串行。本轮8/8渲染授权不恢复EXR解码优化、渲染导出重叠或GPU训练并行。人工取消不当作软件故障自行重启；`started_not_committed`是正常事务，真实退出/报错才诊断。硬崩溃后不猜测重放未持久更新，不按旧PID盲目kill。

## UE与MCP

- UE5.8，默认地图`/Game/FutsalMOT/Maps/L_FutsalCourt`。操作前读[完整自动化工作流](Docs/operations/UNREAL_MCP_WORKFLOW.md)，核当前Level、PIE/MRQ、dirty包；优先真实Unreal MCP，先describe完整toolset再用短tool_name。
- 完整脚本在真实UE Python执行，不以sandbox冒充`import unreal`。切图只用原生SceneTools.load_level，切换期间不持有UWorld引用；原生工具不可用或同类API连续失败两次时报告具体限制，不猜反射回退。
- appearance apply/restore前只读确认规范地图、十人唯一、资产class和package clean。uasset移动/删除用UE内容工具修引用，不从文件系统剪切删除；Fab目录不提交。
- 退出/重启前核dirty、PIE/MRQ、关键资产和自有回调。未知未保存改动或活动MRQ不得强杀；安全时正常quit、编译、启动、重连，用新鲜日志闭环。历史Py_FinalizeEx/PyGC_Collect坏对象仍未知，一次正常退出不称根治，不危险复现。
- 使用已验GPU-render/CPU-LBS；旧CPU-render/Lumen蒙皮submit保持禁用。native在teardown前落盘，回调只读文件；保留MCP PRIVATE/独立globals，不reload Toolset UClass。
- 新运行时行为、动画采样和稳定数据契约优先C++；AnimGraph、Control Rig和材质配置按资产职责处理。维护MPFB先读[生产SOP](Docs/production/MPFB_PLAYER_PRODUCTION_SOP.md)，不凭经验猜未验证导入参数。