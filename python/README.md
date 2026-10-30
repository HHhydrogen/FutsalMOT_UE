# FutsalMOT数据集Python代码

本目录属于统一UE仓库，Git根为项目根、分支`master`；不初始化submodule或嵌套Git。

## 唯一生成管线

新生成统一采用[单seed配置](configs/single_seed_generation_v1.json)：4K、10 FPS、写出8/8、每机位独立UE，五个必选加随机1–2个局部机位。十五套球衣、号码v2、GreenV2与天气视觉v2使用既有独立seed分配。

从**项目根**使用以下入口，操作步骤及精确参数见[单seed基线](../Docs/production/SINGLE_SEED_BASELINE_V1.md)：

| 阶段 | 入口与作用 |
| --- | --- |
| 准备/冻结 | `python/.venv/Scripts/python.exe tools/dataset/single_seed_task.py prepare`或`freeze`，显式指定新`--attempt` |
| 采集 | `python/.venv/Scripts/python.exe tools/dataset/run_single_seed_partitions.py --attempt <名称>`；短样加`--short` |
| 导出/验证 | `python/.venv/Scripts/python.exe tools/dataset/single_seed_task.py export`或`verify`，指定相同`--attempt`与短样范围 |

新协议绑定当前源码、配置、轨迹、schema和DLL。修改源码后必须新建协议，不能接跑旧冻结attempt或修改旧成功收据。完整采集必须先满足同attempt的短样门禁；已正常退出的机位可跳过，部分输出不盲目重放。

**当前用户要求暂不运行完整单seed。** 六机位180帧短样已验证；完整3001帧、总数据集批量发布尚未执行。最新实施状态见[任务状态](../TASK_STATUS_AND_NEXT_STEPS.md)。

旧`grf-ue task/production`命令不再执行生成，也不会自动转成新配置；旧smoke、活跃窗口及Pose17生产启动器不再作为新生成入口。`ue/run_task.py`是当前分机位任务的内部实现，不能直接运行任意resolved JSON。

## 环境与输出

- P1固定Python3.9，环境`python/.venv`；不要升级到3.10或安装研究Torch依赖。
- P2仅在真实UE5.8 Editor Python执行，由控制器通过Unreal MCP调用；P1不能替代`import unreal`。
- P1与UE通过JSON/JSONL及媒体交换数据，UE不导入NumPy/OpenEXR/OpenCV后处理依赖。
- 研究代码位于`experiments/sim2real`，使用独立Python3.10环境；渲染与GPU训练串行。

临时媒体位于`G:/FutsalMOT_Dataset/test/<attempt>/raw`和`export`。项目Saved只保存配置、日志、轨迹/native、协议与收据；媒体、虚拟环境和缓存不入Git。

权威导出结构为`seed_<8位hex>/seed_manifest.json`、共享`trajectory.jsonl`及各机位的`camera.json`、`annotations.jsonl`、`img1/`、`mask/`、`number_mask/`。每帧保留十人，body12可见性未知为0、号码可读性未经认证为false。历史Pose17数据不重命名成body12；旧成品只按其原manifest读取。

## 开发与检查

先读[组件规则](AGENTS.md)、[数据契约](../Docs/engineering/DATA_CONTRACT.md)、[验证边界](../Docs/engineering/VALIDATION_AND_LIMITATIONS.md)和[存储规则](../Docs/operations/STORAGE_POLICY.md)。

针对测试从`python/`目录执行`.venv/Scripts/python.exe -m pytest <相关测试文件>`。默认跳过真实GRF集成；仅在需要且获准时使用`-m grf_integration`。静态检查不代表MRQ动态通过，不重复整套媒体审计或无变化的长渲染。历史研究过程见[训练历史](../Docs/research/TRAINING_HISTORY.md)，不从旧实验手册恢复已退役的生成入口。