# 运行入口与日常维护

从项目根执行，先查看当前路径：

```powershell
./tools/run.ps1 paths
./tools/run.ps1 p1 task validate python/configs/weather_seeded_smoke_3frames_4cam.json
./tools/run.ps1 p1 task ue-command python/configs/weather_seeded_smoke_3frames_4cam.json
./tools/run.ps1 research experiments/sim2real/train_pose_location_separate_v4.py --help
./tools/run.ps1 mcp --help
```

P1固定`python/.venv`的Python3.9；研究仍使用独立Python3.10环境。本机研究解释器可在`Saved/Local/paths.json`设置，模板为[paths.example.json](../../Config/paths.example.json)。实际GPU研究运行前必须退出Editor；研究启动器会拒绝活动Editor，纯`--help`除外。它不会修改协议或自动生成新的训练准入。

P1本机配置为`Saved/P1/.futsalmot/local.json`，默认工作输出指向`Saved/Render/Tasks`；正式发布工具才将完整数据放到`G:/FutsalMOT_Dataset`。不要把成品数据、权重或实验输入复制回源码目录。

## MCP

UE运行时使用`tools/mcp_cli.py`或启动器的mcp模式。`--list`发现工具，`--describe <toolset>`读取schema；完整请求使用`--request Saved/<请求>.json --receipt Saved/<新返回>.json`，请求operation为`call`。每次调用先describe，写操作不自动重放；执行脚本仍限真实项目路径，没有放宽Toolset范围。

MCP请求与收据只允许实际位于本项目Saved，旧GWorkspace规则不再是当前入口。历史驱动在`tools/legacy/`，禁止因旧文档存在而直接重启。

## 清理与历史

- 原始执行证据保留在Saved和研究根；原清单/协议bytes不改写，目录变化另记映射。
- 本轮收尾将37项一次性清单/入口归档，逐个文件SHA核对，未删除源码或正式数据；收据为`Saved/ProjectStatus/phase4_archive.json`。
- Saved日志保留当前退出、失败定位与关键回执；只删除明确过期的日志、测试夹具和缓存。不沿junction递归清理，不对正式Dataset批量删除。
- UE资产只能通过UE API移动/删除；17个兼容重定向器仍有引用，不能当作空壳文件强删。
- AutoSave关闭；编辑器中重要修改需主动保存，再精确提交。Git不备份未保存内存。
- 单仓库master，一次提交已验成果；未完成号码、其他WIP、Saved、权重、虚拟环境和Fab缓存均不混入。
