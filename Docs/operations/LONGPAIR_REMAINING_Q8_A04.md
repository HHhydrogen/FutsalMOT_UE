# 首组后安全提高容量并接续三组

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

旧`run_longpair_batch_a04.py`、P2、wrapper和导出器源码保持不变。root已将旧12/4预飞收据原bytes备份，另留`queue_handoff_request.json`并仅追加授权交接字段；旧驱动完成首stage后下一UE动作之前会在既有source SHA门禁自然拒绝退出。CPU不中断，错误保留。

新文件：

- `coordinate_queue8_a04.py`：等待旧小状态与PID自然退出，最多2小时、10秒一次；允许终态先落盘而PID仍在退栈的短暂间隔，以及短时JSON解码失败。然后验证交接，单次MCP执行idle改队列脚本，实际新driver预飞成功才唯一启动。
- `adjust_idle_queue8_a04.py`：只在首stage小索引SHA及1200对/12000人物、首session_release/内存last_release一致，旧PID已退出、规范地图、MRQ/PIE/dirty为空时，调用已验CVar接口将容量4改8；不写线程数。实际读回12/8后在新RUN记录调整和只读预飞收据。
- `run_longpair_remaining_q8_a04.py`：仅从原计划`plans[1:]`生成剩余3组。先验旧source绑定唯一差异恰旧queue授权追加字段、原备份SHA精确一致、旧错误恰source门禁、成功恰首组。继承首stage记录但不重新分析/解码/导出它。剩余任务必须尚不存在。

新RUN为`G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/resume_20261024_a04_q8`，旧a04 `action_request.json`仍是唯一wrapper请求入口；旧驱动退出后才交给新driver。新状态保存原driver错误及交接证据，全部日志和临时文件写G，raw不重拷或删除。仍是16GiB提交门禁、6GiB自有MRQ取消保护、6进程单次EXR解码、unknown与诊断限制。

主agent完成一次代码核对后，可后台运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& E:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe -X utf8 D:/projects/FutsalMOT_UEDataset/tools/pose17_ops/coordinate_queue8_a04.py
```

不要同时手动运行协调器、改队列脚本和新driver。若分开操作，改队列脚本必须经真实MCP `run_python_file`执行；队列实际收据生成后，才可运行`run_longpair_remaining_q8_a04.py --preflight`。任何未知写结果、非预期旧错误或额外source变化均停止保留，不自动重试、不关UE、不训练。

4项CPU文本夹具通过，覆盖唯一授权交接、旧PID仍活动、额外source变化、错误或partial首组、剩余任务已开始及16/6GiB阈值。UE脚本与协调器只做语法解析；这不是实际队列调整或剩余渲染通过证据。
