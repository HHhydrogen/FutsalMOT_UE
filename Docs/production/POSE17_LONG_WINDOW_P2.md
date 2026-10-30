# 300帧蓝/红棕配对P2候选

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

本入口尚未在UE执行，没有动态或正式Pose验收。CPU前缀及映射来自`long_window_inputs_a02`，a01作为已生成历史保留。1048为GRF绝对帧[0,300)，1102为[20,320)，各300帧/10FPS；导入前缀分别0–299、0–319，不重基源时间。四原机位各3840×2160，固定10人/七模型roster，蓝/红棕仅地板变化，配对不是独立运动样本。

`ue/pose17_long_window_contract.py`独立验证全部新字段、来源SHA、窗口、角色和地板。共同`pose17_smoke_runner`只增加新契约分支：严格通过后允许300帧；旧普通3–30帧和旧120帧白名单/行为保持。native `diagnostic_scope`仍为已验joint GPU-render/CPU-LBS；新long契约和source_scope不把旧bool当扩容开关。每camera新pass为300×10=3000条，低于C++4096容量；四job各自独立pass，不修改C++。

MCP执行文件`ue/pose17_long_window_p2.py`，默认`FUTSAL_POSE17_LONG_ACTION=preflight_sources`。默认manifest路径`Saved/Pose17Development/long_window_inputs_a02/prepared_manifest.json`，锁定SHA `1b0e458a24c81a181e122d25c4e01ce8ece59aafc425fbb7d10464f6f15ff693`；显式其他输入必须同时给`FUTSAL_POSE17_LONG_PREPARED_MANIFEST`与对应SHA，且只许项目Saved/Pose17Development子目录。每次仍严格验证新contract，不因输入SHA字符串存在而允许任意帧数/模型。

全部GPU研究结束、root确认UE可安全启动后才执行。各动作相互独立，不隐式进入下一步：

1. `preflight_sources`只读Level/PIE/MRQ/dirty、15Actor/四机位身份、原地图/Sequence SHA及新源包不存在。`prepare_sources`复用原`import_grf_episode.create_sequence`，只建8个全新源Sequence到`/Game/FutsalMOT/Development/Pose17/long_interaction_floor_30s_a01/seed_XXXXXXXX/`；replace_existing=false、open/API smoke均关闭。保存后核对前后场景和canonical字节不变；失败留partial，不覆盖或自动猜重试。收据为manifest同目录`P2_sources_prepare.json`。
2. 用`FUTSAL_POSE17_LONG_ATTEMPT`选择a02根四个计划中的精确attempt。`preflight_capture`只读；`prepare_capture`复制独立Sequence并建transient queue，保持ready=false。源Sequence不改，地图不保存。`configure_depth`复用旧pilot已实测配方，仅开启WorldDepth高精度无损EXR、AA none/单采样，逐job读回并写`additional_depth_config.json`；此时尚不称深度编码或动态对齐通过。
3. `floor_preflight`复用既有唯一地板slot事务只读验证；`floor_apply`仅在自有queue已准备后应用对应蓝/红棕，记录原slot/非地板场景及恢复journal，不保存地图。此后才将本长窗session ready设true。`submit`重新验证真实floor状态并显式提交，异步返回，不能称渲染或数据通过。
4. 真正完成后独立`postflight`；`floor_restore`恢复原地板槽，不保存地图；`release`只在地板原slot已恢复且共同runner全部门禁通过时释放自有会话。每个配对新attempt重复这一流程，不改已完成120帧产物。

不自动启动UE/MRQ、不取消或结束进程、不创建训练准入、不改canonical/旧数据。RGB/mask/native同期、运动连续性、实际地板配对/头点和深度证据仍由root首次真实执行后验收；CPU测试及静态源存在不能替代该门槛。未知可见性继续unknown，不能升级成正式COCO visibility或MRQ_sync=true。
