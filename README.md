# FutsalMOT Unreal Engine 项目

基于 Unreal Engine 5.8 和 Google Research Football 生成五人制足球多目标追踪数据；包含UE资产、C++运行时和独立Python submodule。

## 当前数据集

无号码正式批次已完成：8个seed、八天气各一组、32个相机序列，原生3840×2160、10FPS，共20,116张RGB和同数实例mask，包含逐帧球员可见像素bbox。每机位连续414–952帧（41.4–95.2秒），不拼接或补静止尾段；8组保留原train归属。

正式根目录：`G:/FutsalMOT_Dataset/v1_no_numbers_4k`。每seed仅一个连续片段，已去掉clips/clip_000两层：

```text
groups/seed_XXXXXXXX/
  group.json
  clip.json
  trajectory.jsonl
  checksums.json
  cameras/CineCam_01/{view.json,annotations.jsonl,rgb/,mask/}
```

入口为dataset.json；group保存一次外观、天气和实体，clip保存连续时间窗及准入证据，标定和catalog通过shared共享。基准组full审计，其余组按明确授权为quick/basic；不能把全部组描述为像素审计通过。

## 工程与代码

- 正式地图和默认启动地图：`/Game/FutsalMOT/Maps/L_FutsalCourt`。
- C++：AFutsalPlayerBase、UFutsalPlayerAnimInstance及FinalImage PNG输出过滤。
- 动画蓝图负责AnimGraph、状态机和FootIK，新增运行时逻辑优先C++。
- P1固定Python3.9，导出轨迹及后处理；P2仅在真实UE Python执行，通过JSON/JSONL交换数据。
- 生产复用Editor/场景、逐机位释放executor，全部数据暂存于G盘并使用6进程CPU后处理。GPU训练与渲染串行。

入口：[Python README](Content/FutsalMOT/code/README.md)、[MPFB生产SOP](Docs/MPFB_PLAYER_PRODUCTION_SOP.md)、[任务状态](TASK_STATUS_AND_NEXT_STEPS.md)。UE任务优先Unreal MCP原生工具；完整Python文件使用FutsalMOTTools.run_python_file，不使用受限sandbox代替import unreal。

## 研究目的

当前主线为合成COCO17姿态监督对固定检测输入下身份关联的边际作用，详见[论文计划](Docs/CVPR_2027_PAPER_PLAN.md)。v3三训练seed的合成臂相对真实继续训练平均AssA提高0.5524点，但相对预训练仅提高0.0236点，尚不能确认跨比赛或真实五人制收益。最终测试保持封存。

研究输入、权重、检查点及结果统一位于`G:/FutsalMOT_Research`；UE/P1工作数据位于`G:/FutsalMOT_Workspace`，正式数据仍在`G:/FutsalMOT_Dataset`，均不入UE仓库。旧D盘数据路径仅通过目录联接兼容，D盘保留代码与UE资产。用户已要求结束今日任务，持续跟进暂停，等待明确继续。

2026-10-23迁移已完成，删除89.22GiB失败未发布媒体并保留诊断记录；项目在D盘的实际占用约4.575GiB，不含联接指向的G盘数据。搬迁收据位于`G:/FutsalMOT_Workspace/migration_20261023/end_day_receipt.json`。

号码系统未完成，本次数据和提交均不包含号码实现，保留为后续任务。

## Git与本机产物

外层master记录UE资产、配置、C++和内层gitlink；内层main独立记录Python。先推内层，再更新外层指针。首次克隆：

```powershell
git submodule update --init --recursive
```

不使用无选择的git add -A。约束见[AGENTS.md](AGENTS.md)。Saved、Intermediate、DerivedDataCache不提交；临时uasset必须通过UE API删除，不能按零引用清理共享角色/材质。默认关闭AutoSave，按Git维护保存后的代码和资产；生产来源、原始轨迹和关键回执仍保留本机归档。
