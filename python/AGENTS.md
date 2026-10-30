# Python组件约定

Git、存储、研究封存和UE生命周期遵循项目根[AGENTS](../AGENTS.md)，本文件只补充组件规则。

## 当前入口

- 先读[Python README](README.md)、[单seed基线](../Docs/production/SINGLE_SEED_BASELINE_V1.md)、[数据契约](../Docs/engineering/DATA_CONTRACT.md)和[验证边界](../Docs/engineering/VALIDATION_AND_LIMITATIONS.md)。
- 新数据集只由项目根`tools/dataset/single_seed_task.py`准备/冻结/导出/验证，`tools/dataset/run_single_seed_partitions.py`控制采集。配置为`configs/single_seed_generation_v1.json`，固定4K、10 FPS、8/8及每机位独立UE。
- 不调用旧`grf-ue task/production`、旧批量或smoke启动器，不绕过控制器直接运行`ue/run_task.py`。保留的底层模块是当前管线依赖，不构成可自由组装旧配置的公开入口。
- 最新任务停点见根任务状态；当前不执行完整3001帧单seed，也不自动开展总数据集发布。

## 环境与协议

- P1固定Python3.9，虚拟环境为本目录`.venv`；不升级至3.10、不安装研究Torch依赖。
- P2只在真实UE5.8 Editor Python运行。P1不能替代`import unreal`；UE不导入依赖NumPy、OpenEXR、OpenCV的P1后处理模块。
- P1与P2通过JSON/JSONL和渲染文件交换数据，不共享环境。独立研究脚本在根`experiments/sim2real`，使用Python3.10。
- 源轨迹首次done后停止；同seed所有机位共享完整运动、身份与随机分配。MRQ提交不等于完成，逐机位恢复及正常退出后才能继续。
- 冻结协议绑定源码、配置、轨迹、schema和DLL。改源码后另立attempt；不改历史SHA、不伪造旧收据可用于当前代码。只有成功闭合机位可跳过，未闭合现场不能覆盖。

## 验证边界

- 默认pytest跳过真实GRF集成；显式`-m grf_integration`才执行原生引擎。针对测试从`python/`目录运行，只覆盖本次变更所需范围。
- CPU通过不代表资产、MRQ、可见性或动态Pose已验收。历史12点与Pose17独立；unknown不改为visible，位置监督不冒充物理遮挡监督。
- 字段和文件树从冻结manifest/schema生成，不从磁盘现状学习新结构；读取旧成品按其原manifest，不将旧发布布局接回新生成流程。