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

- 生成完成的数据集仅保存在`G:/FutsalMOT_Dataset`。UE工作文件位于项目原`Saved/`物理目录；研究输入、权重、检查点和结果位于实际`D:/projects/FutsalMOT_Research`。
- D恢复迁移已完整结束，G盘旧Research/Workspace根已移除；不重放旧迁移驱动。P1运行数据位于`Saved/P1/`，运行收据位于`Saved/`，历史协议原路径通过独立relocation解释。
- 统计、复制和清理不跟随junction；不对DataSet目标递归删/搬。冻结协议、源码绑定、轨迹、native、校准和关键收据保留原bytes/SHA，另记relocation映射，不伪造历史路径可运行。
- G盘或D项目外写删按具体范围申请工具自动审批，不能通过junction绕过；拒绝时说明实际动作与原因。
- 23013份冗余媒体已删除638.191GiB，其中7961份EXR的深度/Cryptomatte不再保留；不能据已发布RGB/mask/Pose声称原EXR或物理遮挡证据仍存在。
- AutoSave在项目和本机配置均为False。Git只管理磁盘中的文件，不能恢复尚未保存的Editor内存。
- `Saved/`、`Intermediate/`、`DerivedDataCache/`、虚拟环境、权重和本机运行收据不提交Git。

## 研究与数据边界

- 当前主线为合成COCO17位置监督在固定检测下对身份关联的边际作用，见[论文计划](Docs/research/CVPR_2027_PAPER_PLAN.md)。最终SNMOT116/187封存，不调测试集、不筛seed/best/比例，不预设提升。
- v1八组数据保持不变。Pose试产独立输出；不能将历史12点重命名成17点或事后伪造同帧采样。
- 鼻眼耳按实际渲染mesh校准；可见MPFBVisual与隐藏驱动mesh必须区分。unknown不冒充COCO visible，限定位置准入不等于正式遮挡监督。
- 独立机位world差异保留原值，不平均或用容差冒充逐值exact。地板随机流独立于运动/天气/外观，同运动配对保持同split。
- UE渲染与GPU训练串行；本轮渲染、发布和本次安全退出真正完成后才训练。人工取消遵循最新用户要求，不当软件故障自行重启。
- 活动`started_not_committed`是正常事务；只有真实退出/报错才诊断。硬崩溃超过last的数学更新不猜测重放，不把PID复用误判为旧训练，绝不按旧PID盲目kill。

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
