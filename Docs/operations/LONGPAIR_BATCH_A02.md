# 迁移后30秒配对唯一驱动

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

入口`run_longpair_batch_a02.py`只接管已提交的1048蓝a02。其后1048红棕、1102蓝、1102红棕按固定顺序执行。不会调用旧a01驱动，不重复首组prepare或submit。

状态根固定`G:/FutsalMOT_Workspace/UE/Saved/Pose17Development/resume_20261024_a02`。`driver_state.json`和`driver.lock`禁止第二驱动与隐式重放；异常保留partial、完整UE返回及CPU日志，不自动重试。先执行`--preflight`只读检查固定计划、真实Editor32360身份、首组状态、输出不覆盖及源代码绑定；正式启动由主agent负责。

所有工作数据实际写G盘。root当前冻结的导出guard只允许`G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01/_staging/<a02 attempt>`，故a02任务继续使用该stage根。原PNG/EXR和深度全部留在G Workspace，不重新归档复制、不删除。stage的RGB另复制以自包含，CPU Cryptomatte最多6进程、每EXR一次解码。

单组顺序：等待真实MRQ成功终态 → postflight → floor_restore → release → 独立300帧inspect → export。首组完成后才prepare下一组。未知visibility、诊断及未准入标记均保留。四组完成状态为`complete_four_diagnostic_stages_not_published_wait_root`；不自动发布、退出UE或启动训练。发布和安全退出后训练由主agent另行安排。

验证：`test_longpair_batch_a02.py`4项CPU测试通过，检查首组无提交权限、原计划只换a02、D盘回落/逃逸拒绝和失败会话不接管。实际`--preflight`已确认首组submitted_async和Editor32360，未执行MCP动作；此证据不代替四组真实渲染完成。
