# UE故障分组与低成本防护（2026-10-23）

本次只读核对Saved/Pose17Development的Editor日志、Saved/Crashes的九份CrashContext及本机CrashReportClient日志，没有启动UE、渲染、训练或危险配置复现。日志中的时间为UTC；Windows文件修改时间可能随报告提交变化，不能作为实际崩溃时间。九份CrashContext对应七次fatal事件，其中两次Lumen故障各有ensure和assert两个报告，不能计成四次崩溃。

当前最需要处理的是Python退出阶段崩溃。它与已经绕开的CPU skin/Lumen渲染故障不同，不能因已成功出图就认为退出安全，也不能靠重新审计图像修复。

## 已实际落实的防护

本轮已在runner提交入口直接拒绝旧CPU渲染蒙皮路径，避免再进入已复现的Lumen缓冲故障。继续使用已通过的GPU渲染/CPU-LBS路径。PIE采样继续由native在cleanup前持久化，Python结束回调只消费文件。

MCP执行器已改为PRIVATE文件作用域、独立字面代码globals，并删除按最近mtime返回历史错误日志的回退。真实Editor通过两次文件隔离/显式会话保留及字面globals不泄漏检查；1042预备queue在热替换前后对象ID相同，未reload Toolset/UClass、未重启Editor。7项CPU合同测试通过。这是减少临时包装对象长持有的防护，尚未证明它根治退出AV；不为验证这一点中断当前试产。批次内保持同一Editor，完成全部渲染后正常收尾时观察退出终态。

四seed位置监督试产已实际启动，16个新源Sequence已创建，首组1042的四机位120帧4K渲染已完成并进入mask/Pose生成。故障处理没有再阻塞为重复近景或全像素审计。

## 一、正常退出请求后的Python崩溃：尚未修复

| UTC | Editor PID | 原日志 |
| --- | --- | --- |
| 03:13:19 | 25224 | editor_after_build-backup-2026.10.23-03.13.19.log |
| 06:45:43 | 16052 | editor_gpu_lbs_a01.log |
| 07:12:41 | 30812 | editor_gpu_override004_a01-backup-2026.10.23-07.12.41.log |
| 08:29:30 | 22000 | editor_gpu_joint_a01.log |

最近一次证据最完整：`Saved/Pose17Development/editor_gpu_joint_a01.log:8456`的重启门禁为dirty=[]、PIE=[]、MRQ=false、active_render_modules=[]；8458行是QUIT_EDITOR，8483行是Preparing to exit，8488行才出现读取地址0x0000006469757577的访问违规。调用栈前五项属于python311，随后两项PythonScriptPlugin。CrashContext为`Saved/Crashes/UECC-Windows-149E9494418536F260B59BB2F95BD477_0000/CrashContext.runtime-xml`，PID22000一致。

07:12和06:45两次也在明确QUIT_EDITOR、Preparing to exit之后失败。07:12前004会话已有owned_callbacks_removed=1、MRQ/PIE/dirty为空的release记录；08:29之前joint及两个floor会话均已有release记录。因此“这几次仍有活动MRQ”不受证据支持；“单纯忘了解绑本次executor callback”也不能作为已证根因。

本机引擎`PythonScriptPlugin.cpp:1453`的ShutdownPython依次重置RemoteExecution、恢复GIL、广播OnPythonShutdown、移除ticker及委托、清理Python模块和全局字典，最后1545行Py_Finalize。退出阶段加Python模块栈与这段生命周期相符，但现有栈仅模块名/地址，不能定位究竟是哪个Python对象、扩展模块、线程或UObject包装损坏，更不能断言一定停在Py_Finalize某一行。悬空回调、公开执行字典残留包装和解释器清理次序目前都是待验证假设。

进一步离线解析已把阶段缩窄：现有minidump配合实际DLL导出表及AMD64 unwind函数范围，确认栈中的`python311+0xcb211`属于`Py_FinalizeEx[0xcb180,0xcb28c)`，`+0xcb452`属于`PyGC_Collect[0xcb3e8,0xcb493)`。因此可明确定位为正常退出后的解释器finalize/GC，而不是活动MRQ。顶帧私有函数`+0xd8b06`读取`[rsi+0x18]`，RSI=0x646975755f，对应故障地址0x6469757577；具体损坏对象/引用链仍未知。本机缺匹配PDB和常用调试器，唯一DbgHelp离线会话未成功命名私有帧，未联网下载符号或危险重现。PRIVATE补丁仍只算降低风险，不能据这段证据称坏对象已经修复。

低成本防护：一次批次内复用已通过的Editor，避免为重复检查频繁quit/restart；每个完成会话只做现有release，按自己callable解绑并释放强引用。退出前做一次轻量Level/dirty/PIE/MRQ/自有会话检查，发一次正常退出请求；退出后读取进程终态和日志尾。Preparing to exit只证明开始退出，成功退出需确认无fatal和完整Exiting/关闭记录。即使渲染收据成功，退出AV也单独记录为shutdown失败，不把已成功产物重渲染。不要通过强杀、强制GC、清空其他任务委托或改关卡来掩盖问题。

下一次确有必要退出时再做狭窄诊断：只记录Python插件shutdown关键阶段/拥有者线程及本任务残留引用，不额外跑媒体审计；优先用已有minidump和匹配符号解析具体函数，避免为符号取证重现危险场景。本报告没有实现或宣称根治。

## 二、CPU skin渲染与Lumen uniform buffer冲突：已绕开，未修引擎

05:46:13 PID19344，日志`editor_player004_override_a01.log:5050`；05:57:54 PID31908，日志`editor_player004_override_a02-backup-2026.10.23-05.57.54.log:5110`。两次都是RHIUniformBufferUtilities.h:162：slot2实际绑定FViewUniformShaderParameters、shader预期LocalVF；GPU breadcrumb是MeshCardCapture/LumenSceneUpdate，后台渲染worker崩溃。

首例是Player004 override加CPU skin；第二例`smoke/player003_closeup_warmup_a06/failure_diagnosis.json`明确无mesh override，仅原003加8帧engine warmup也出现相同故障。这排除了“004模型替换是必要条件”，没有定位内部坏指针，更不证明模型本身损坏或是内存不足。

当前路线保留GPU渲染，只在CPU计算位置，即gpu_render_cpu_lbs；003 a07、004组合、十人joint和两个floor短样实际成功，支持在这些已测配置下规避原故障。不能把成功短样当作所有运动/全部长片段的稳定性证明。后续保持该路线、原warmup和GPU eligibility门禁；不再为逐角色近景验证反复进入旧CPU-render路径，不用关闭Lumen或随意改材质来碰运气。

## 三、PIE清理后Python延迟回调访问违规：已移出危险访问点

04:26:06 PID32268，`editor_cpu_sampling_a01.log:5067`附近，先Movie Pipeline completed，再BeginTearingDown、CleanupWorld、对象表压缩，随后PythonScriptPlugin/CoreUObject/MovieRenderPipelineEditor调用栈访问违规。它不是QUIT_EDITOR阶段，也不是LocalVF错误。

本机MoviePipelinePIEExecutor.cpp:523先缓存输出，536将ActiveMoviePipeline置空，539安排下一tick，550开始DelayedFinishNotification并广播job结果。对应旧收据`smoke/player003_mrq_a01/failure_diagnosis.json`怀疑在deferred Python job callback读取已销毁PIE pipeline。源码和时序支持生命周期风险，但缺符号栈，仍不能指认唯一被释放对象。

现有实现改为native pipeline teardown前持久化纯JSON收据，Python完成回调消费落盘结果；release只访问仍被session强持有的executor、不碰PIE Pipeline/Job，按自己的callback解绑。后续多次真实小样成功支持这一规避。保持此边界，不能为补读信息重新在job-finished回调反射Pipeline。

## 四、World泄漏：本次集合没有直接证据

本次扫描Saved/Pose17Development及Saved/Logs的日志，未找到World Memory Leaks、old world not cleaned、still referenced等门禁错误；九份CrashContext也不属于world泄漏断言。这不否认更早切图历史，只是不把项目AGENTS中记录的历史风险当成本次退出AV根因。

继续执行既有便宜防护即可：不为本批切图；必要切图用原生SceneTools.load_level，调用间不持有UWorld。不要为了“验证world是否泄漏”主动重新切图或全量GC。

## 五、旧abslog重新出现：旧Crash Reporter重启是强线索，非已证watcher

root只读进程快照确认：Editor26244于08:34:03 UTC创建，命令行复用editor_gpu_override004_a01.log，父PID30688已退出。root的launch_pose_editor.ps1使用新RunName skin_data_a01时因已有Editor正确拒绝，没有再启动；该脚本单次Start-Process且拒绝已有log/receipt，本身没有自动循环。

新增线索来自`C:/Users/20113/AppData/Local/CrashReportClient/Saved/Logs/CrashReportClient.log`：26行监控旧Editor30812；93–99行07:12:41收集C35A崩溃并以Interactive模式等待；746行起直到08:34:04才提交这个旧报告，759行之后08:34:07销毁Crash Reporter窗口，时间紧邻新Editor26244启动。旧报告携带旧abslog，支持“旧Crash Reporter提交/重启入口复用旧命令行”的解释。

但日志没有明确Restart事件，已消失父进程无法仅靠当前CIM确定可执行文件，不能断言是谁点击或哪个自动化触发。引擎WindowsPlatformCrashContext.cpp:643后说明CrashReportClient会自行respawn脱离Editor进程组，因此初始Started CrashReportClient(pid=31880)不等于最终报告进程PID；不能拿初始PID不等就排除该线索。项目脚本/配置搜索和当前进程快照没有发现可证的watcher，不能把MCP server启动簇认作Editor重启器。

低成本防护：保留crash报告后，将旧Crash Reporter窗口作为单独待处理项；需要重启时使用一次新RunName，启动前核对真实Editor PID/命令行/创建时间与本次DLL，不因日志文件名相同认作原进程。若出现意外Editor，先只读确认并利用可用clean实例，不再重复启动或强杀。以后可在正常启动收据中加父PID/创建时间，若原有Windows进程创建事件可用则只查30688/26244的单次事件；本报告没有开全机监控或修改配置。

## 收敛执行策略

把数据完整性与Editor退出健康分开：渲染成功依本次终态/原生收据/少量中心帧，退出成功依进程和日志尾。沿用已验GPU-LBS方法、批次内保持Editor、逐任务释放，减少重复审计和不必要重启。退出Python故障尚未根治，保留每次真实退出结果；不要承诺“正常quit肯定不会崩溃”。

机器可读证据索引：`Saved/Pose17Development/ue_crash_findings_20261023_a01.json`，包含日志及CrashContext SHA、行号、故障类别、ensure去重与未证假设，不包含媒体全量审计。Saved证据保持本机，不纳入Git。
