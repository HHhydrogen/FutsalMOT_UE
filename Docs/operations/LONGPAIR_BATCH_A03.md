# a03内存保护驱动

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

`run_longpair_batch_a03.py`取代未启动的a02驱动。固定读取`G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/editor_longpair_resume_20261024_a03_launch.json`并绑定实际PID。首组1048蓝a03只接管已提交MRQ，后续三组才prepare/submit。四组输出均为独立a03；原输入包仍`long_window_inputs_a02`，schema沿P2为a02且显式`attempt_number=3`。

每10秒使用正式生产相同的Windows `GetPerformanceInfo`记录commit headroom至本轮G目录`memory.jsonl`和driver state。低于6GiB时核对精确自有plan与当前MRQ，通过MCP `cancel_memory_guard`仅取消本会话executor，记录为程序内存保护并停止。取消返回失败或未知也不重放，不强杀Editor、不改活动ImageWriteQueue线程池。真正采集使用主agent启动时显式配置的12线程/8队列。

其他边界沿a02：raw原地留G、不重拷删除；独立300帧inspect/export，6进程CPU，每EXR一次解码；stage沿冻结唯一标准G根`v2_pose17_longpair_pilot_a01/_staging/<a03>`；四stage完成即等待主agent发布和安全退出，不自行训练。

5项CPU测试通过。实际构建期间读到commit headroom约1.18GiB，已立即告知主agent；这不是正式渲染通过或driver启动证据。启动前须由主agent处理当前自有会话，避免把低内存取消误称人工取消或自动反复重渲染。
