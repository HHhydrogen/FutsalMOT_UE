# 统一仓库目录与运行边界

代码迁移于2026-10-25完成。仓库仍只有根Git，项目文件名与默认地图不变。

| 目录 | 职责 |
| --- | --- |
| `Source/FutsalMOT/` | UE运行时C++与稳定采样接口 |
| `Plugins/FutsalMOTMCP/` | Editor原生MCP与受限项目脚本入口 |
| `Content/FutsalMOT/` | UE资产；不再存放Python工程 |
| `python/src/grf_ue_bridge/` | P1轨迹、标注和数据契约 |
| `python/ue/` | 仅真实UE Editor Python执行的P2脚本 |
| `python/configs/` | 可版本管理的配置和本机配置示例 |
| `python/tests/` | 针对CPU检查与显式GRF集成检查 |
| `experiments/sim2real/` | 独立Python3.10的训练、推理与评价 |
| `tools/` | 跨环境入口和运维源程序 |
| `Docs/` | 工程、生产、研究、运维文档 |
| `Saved/P1/` | P1本机状态、轨迹与临时产物，不入Git |
| `Saved/ProjectStatus/` | 当前整理进度与检查收据，不入Git |

成品数据位于`G:/FutsalMOT_Dataset`，研究输入、检查点和结果位于`D:/projects/FutsalMOT_Research`。G盘不保留UE工作区或Research根，旧位置不建立兼容反向联接。

## 运行

P1固定Python3.9，使用`python/.venv`。从项目根执行：

```powershell
uv run --project python grf-ue task validate python/configs/weather_seeded_smoke_3frames_4cam.json
uv run --project python grf-ue task ue-command python/configs/weather_seeded_smoke_3frames_4cam.json
```

本机配置默认读取`Saved/P1/.futsalmot/local.json`，示例为[local.example.json](../../python/configs/local.example.json)。CLI显式路径优先；独立task仓库保留自身`.futsalmot`，不因位于项目下而继承本机配置。

P2入口为[run_task.py](../../python/ue/run_task.py)，通过真实MCP执行；P1和研究Python均不能替代`import unreal`的Editor环境。研究脚本位于根`experiments/sim2real/`，保留独立Python3.10及Torch环境，不能向P1安装研究依赖。

## 迁移验证与历史

418个索引条目按原mode/blob改名，工作区中23个号码WIP文件保持字节不变；本轮修改独立叠加到原blob，未把其他未提交代码加入阶段成果。P1 editable已离线重装，Python仍3.9.25；真实GRF同seed跨进程4步检查通过，路径/CLI/resolved-task的71项针对CPU检查通过。

原实际v4源码在提交`9a5cbe9`中保持26/26个文件SHA一致。历史协议与运行收据不改写；移动代码和修订未来入口会改变源码身份，不能用旧准入直接重跑。

尚未完成的30秒WIP含旧attempt/GWorkspace门禁，本轮不放宽。下一轮30秒实验须先建立新布局的显式协议与入口；当前目录整理不代表新训练或遮挡标签准入。
