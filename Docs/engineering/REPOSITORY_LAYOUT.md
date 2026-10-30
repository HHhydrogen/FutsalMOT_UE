# 当前仓库目录与运行边界

仓库只有`D:/projects/FutsalMOT_UEDataset`一个Git根，分支master；Python不是submodule，不初始化嵌套Git。默认UE地图和项目文件名保持不变。

| 目录 | 职责 |
| --- | --- |
| `tools/dataset/` | 当前single_seed公开入口、分机位控制器与UE启动 |
| `python/configs/` | 当前4K/8x8单seed、相机、球衣、号码配置 |
| `python/src/grf_ue_bridge/` | 源轨迹、随机recipe、精简导出和校验；共享模块不是备用生成入口 |
| `python/ue/` | 真实UE5.8 Python内部适配、事务和MRQ |
| `python/schemas/single_seed_v1/` | 新seed导出唯一机器可读契约 |
| `Source/FutsalMOT/` | UE运行时C++与body12稳定采样接口 |
| `Plugins/FutsalMOTMCP/` | Editor原生MCP与项目脚本入口 |
| `Content/FutsalMOT/` | UE资产；移动/删除通过UE API |
| `experiments/sim2real/` | 独立Python3.10的研究训练、推理和评价 |
| `Docs/` | 当前规范和保留的历史研究证据 |
| `Saved/SingleSeed/` | 本机attempt协议、冻结源码、轨迹/native、日志及运行收据，不入Git |
| `Saved/P1/`、`Saved/ProjectStatus/` | 历史P1状态和项目运维收据，不是新生成入口 |

当前生成命令仅见[单seed固化说明](../production/SINGLE_SEED_BASELINE_V1.md)。P1使用`python/.venv`固定Python3.9，UE使用Editor内置Python；P1不能代替`import unreal`，UE不能导入NumPy/OpenEXR后处理依赖。`run_task.py`只供当前协议的内部适配，不手工构造旧task调用。

所有渲染媒体位于`G:/FutsalMOT_Dataset`，临时样本在`test/<attempt>`；研究输入、权重和结果位于`D:/projects/FutsalMOT_Research`，生成图像只引用G成品。不能通过junction把媒体写回D项目，也不重建旧GWorkspace/Research路径。

旧生产CLI、候选driver和操作文档不再是支持路径。既有研究与已发布数据保留原版本、来源与split；源码改变后新运行必须新协议，不以旧冻结收据替代新源码准入。历史迁移详情留在[单仓库迁移记录](../operations/SINGLE_REPOSITORY_MIGRATION_20261025.md)，不重放旧迁移。
