# a04独立新任务驱动候选

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

`run_longpair_batch_a04.py`不接管已取消的a02/a03。四个a04任务全部必须不存在，首组也由驱动完整preflight、prepare、depth、floor、submit。原始源Sequence可复用，失败媒体不可复用。代码不操作其他应用进程。

启动前由主agent完成：

1. 关闭或清理已知自有失败会话，确认没有活动MRQ和未知dirty；不得重启a02/a03驱动。
2. 启动a04 Editor，正常初始化MCP，准备`editor_longpair_resume_20261024_a04_launch.json`及`resume_20261024_a04/attempt_resume.json`。后者沿schema `pose17_longpair_attempt_resume_a02`，显式`attempt_number=4`，四个名字精确a01→a04。
3. root通过真实只读查询确认12线程/4队列，将结果写`resume_20261024_a04/write_queue_preflight.json`：`editor_pid`、`MaxConcurrency=12`、`MaxQueueSize=4`、`read_only=true`、`launch_receipt_sha256`。驱动只读并绑定该结果，不写CVar。
4. 系统提交内存余量至少16GiB；G盘至少100GiB可用。运行`--preflight`检查实际PID、G映射、源绑定、四新任务和stage不覆盖。由root决定正式启动，构建代理不启动。

状态、请求、完整MCP返回、CPU日志和临时目录都在G盘本轮目录。每次submit前重新读取`GetPerformanceInfo`，commit headroom不足16GiB就不提交；MRQ期间每10秒记录，低于6GiB仅调用自有`cancel_memory_guard`并停在程序保护状态，不强杀、不重放。未知取消结果同样停止。

raw媒体留G Workspace；成功后按postflight→floor_restore→release→inspect→export（6进程）顺序处理。stage仍位于冻结导出器唯一允许的`G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01/_staging/<a04>`。四stage完成即等待主agent，绝不自行GPU训练、发布或结束Editor。

5项纯CPU夹具通过，涵盖四组含首组完整提交序列、16/6GiB独立边界、12/4只读收据身份、仅改新attempt名、G盘原子写入和禁止D盘数据。尚无a04实际预飞、渲染或后处理通过证据。
