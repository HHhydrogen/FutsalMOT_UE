# FutsalMOT 当前任务

更新：2026-10-23

### 最新联合阶段

最新执行：四seed×120帧×4相机已全部完成，实际产出1920张4K RGB、1920张实例mask、19200条人物Pose记录，驱动已正常结束，不再启动采集。完成收据为`Saved/Pose17Development/location_pilot_capture_complete_a01.json`。前三组1042/1044/1048为train、1102为synthetic_dev；固定蓝地板与七模型roster，不冒称复现原seed天气/外观。源仍保留diagnostic/not_training、unknown及MRQ_sync_verified=false；下一步通过独立限定位置监督入口接入研究，不能改源标志绕过。

四组均已释放自有回调，地板槽恢复且非地板状态不变、dirty为空。本轮Editor26244在09:54UTC正常quit后出现Exiting和Log file closed，进程已消失，没有新fatal；收据`location_pilot_shutdown_a01.json`。这证明本次退出通过，不证明历史Python GC根因已修复。UE保持关闭，研究代码和协议准备完成后串行GPU训练。

四组已复制到独立`G:/FutsalMOT_Dataset/v2_pose17_location_pilot_a01`，3968文件、18,812,362,393字节；不重编码或复扫媒体hash，原诊断标志保留。当前v1八组不变，新目录是位置研究试产，不宣称完整正式遮挡Pose发布。

真实COCO位置监督子集已完成：1000张train、200张公开pose-dev，分别3184/729人物框、25417/5439有效点，全缺点人物框保留。精确采样表、独立研究Trainer和官方COCO评价入口已经接通，新鲜36项定向CPU检查通过。root限定位置准入与协议已冻结，协议SHA为`577f3d1e1233ce7df5d110279d7dda5af186ef2fa573b7860c761caf8a779e07`。唯一后台`run_location_control_a01.py`已启动，权威状态`Saved/Pose17Development/location_control_driver_a01.json`；先评预训练参考，再串行三seed的R/RS25各1000更新与固定dev200评价，不重复启动。

官方checkpoint已经COCO预训练，实验是有限子集继续训练，不是总共只用1000真实标注。R为4000真实曝光，RS25为3000真实加1000合成曝光，独立真实ID和实际更新相同、真实曝光不同。同640 LetterBox后真实框高中位138.27px、选中S为27.33px；S每图有效点170、R25.417，25%合成图像不是25%位置监督量。这些数字已预先记录，不据此重新筛选；COCO AP仅姿态代理，真实足球固定检测的Pose辅助AssA/HOTA仍需后续独立对照。尚无本轮训练提升结论。

已新增七模型基础蒙皮真实导出、400条历史矩阵SHA精确离线重建和480个十二关节支持候选；所有visibility仍unknown。已落实旧CPU渲染submit禁用、MCP PRIVATE作用域/新鲜错误日志防护。故障归为两次CPU-skin/Lumen、一次PIE后悬空回调、四次Python退出GC；退出AV具体对象仍未定位，不称根治。定时任务以构建性产出优先，复用已验方法、减少重复审查。后续段落属于历史证据，不能覆盖本段四组完成和Editor已关闭状态。

004已完成真实网格切换、三近景RGB/头点深度及恢复验收。按用户加速要求取消005–009逐角色近景复验，已直接完成`joint_seed1048_a01_gpu_lbs`：七模型十球员、真实GRF源100..109、四机位各10帧4K，共40RGB/40EXR/400实体采样，队列34.510秒。原生身份/骨架/fence/恢复和帧相机配对通过，主agent仅看四张源105全员叠图。十实体均有去平移后的姿态变化。

独立机位重放的世界点最大差4.274e-6m；不平均或伪装严格相同，v2诊断导出保留每机位原world。visibility仍unknown，MRQ_sync_verified=false，未升级正式Pose/训练准入。当前继续完整mask/bbox导出与蓝/红棕地板配对；v1不变、最终test116/187封存、不重启旧R5。最新收据`Saved/Pose17Development/joint_seed1048_a01_root_review.json`；以下带旧时间和“下一步”的段落为历史证据，不能覆盖本段当前状态。

本阶段后续已完成：独立`Saved/Pose17Development/diagnostic_pose17_export_a01`含40RGB/40实例mask/400人物Pose2D与每机位原始world，6800点仍unknown，全部world与native逐值一致。蓝色/红棕各四机位×3帧配对也已完成：相同机位/源帧2040对world点精确一致，源101四mask差0像素，相机标定一致；主agent已看四机位并列图，地板变化清楚、白线保留。原地板恢复、非地板状态不变、dirty为空。收据`Saved/floor_pair_root_metrics_a01.json`及独立root目视收据；这不证明泛化收益，也不升级unknown。内层本阶段472项CPU回归通过，Git提交`88dec26`已推送；未完成号码和Saved媒体排除。下一阶段是关节遮挡证据与多seed位置监督试产准入，之后再冻结真实对照协议。

### 当前执行补充（2026-10-23 14:00）

最新：`player003_closeup_a07_gpu_lbs`已真实完成三机位×3帧原生4K，保持GPU蒙皮、Lumen skeletal cards=1及8帧预热，14.825秒完成队列；所有采样/恢复、独立Editor postflight与会话释放通过。相同源帧跨相机世界点差0m，正面鼻眼9点最大残差0.1292mm，两侧近耳6点最大0.0912mm。固定5mm下22个表面候选、11个自身较近表面候选、12个边界unknown，最终仍全部unknown。三机位frame1原图/头点及全身裁图已独立检查，未见此前腰髋破碎，但新旧warmup/骨姿态不同，不能当同pose CPU/GPU A/B或完整衣裤修复。源0→1姿态相同，1→2去平移变化0.03699m，长动作门槛仍待完成。收据`Saved/Pose17Development/player003_gpu_lbs_dynamic_head_review_a07.json`；Editor16052保留且clean/released/noMRQ，下一项为GPU-LBS与004 PIE override组合，新构建前不调用开发中的新scope。

Player003近景动态头点方法已通过独立三视图复核：正面鼻/双眼9点深度残差最大0.327mm，两侧近耳6点最大0.056mm；其余边界及遮挡候选仍保留unknown，不是正式可见性标注。证据见`Saved/Pose17Development/player003_dynamic_head_review_a04.json`。衣裤腰髋出现不规则露肤区域，外观质量未通过；实际衣裤材质为OPAQUE且源纹理alpha全1，尚需同姿态CPU/GPU蒙皮A/B定位。

Player004仅PIE网格切换代码已构建成功、原生测试1 passed、针对CPU回归73 passed，但首次`player004_closeup_a01`在8帧预热末尾发生RHI错误（Lumen MeshCardCapture期望LocalVF缓冲却收到View缓冲）。Editor19344自然退出、无有效RGB/EXR或恢复收据，失败已封存，不能视为角色004验收通过；当前正在调查渲染状态生命周期，下一次必须用新attempt。

随后`player003_closeup_warmup_a06`保留原003且不切网格，只设同样8帧预热，也复现LocalVF/View错误，Editor31908自然退出且零有效帧。因此004切网格不是必要条件，不能将失败归咎于角色004；CPU渲染与Lumen缓存仍是源码和反证支持的待验证原因。接下来用显式新opt-in保持GPU渲染，CPU只按当前骨变换/实际权重计算位置；新计划`player003_closeup_a07_gpu_lbs.json`已准备，仍须新构建和真实RGB/depth证明，不能直接批产。

训练准备阶段已发布：内层`1a94717`、外层`a82a17e`。保留COCO预训练容量的17×2位置头通过11项针对测试；自绘toy CPU Trainer执行首次及续载各一次更新并核对279个优化器状态张量。没有GPU研究训练、真实收益结论或封存测试集读取。实际逐点location_valid加载器与固定检测Pose关联接口继续独立开发，候选实验参数未冻结。

后续缺点监督工程阶段也已发布：内层`a7d99b8`、外层`e60d561`，真实语义夹具部分/全缺点人物与synthetic unknown经实际JSONL图像加载、LetterBox、loss、SGD更新和resume通过，主agent新鲜28项测试通过；这是toy CPU兼容收据，不是研究效果。世界17点按时间去重的独立诊断适配器及关联导出69项CPU回归通过，尚未正式发布或迁移媒体。论文计划现已统一为FutsalPoseTrack主线，旧R5保持中断。

以下12:30记录作为已完成历史保留；实时状态以`Saved/Pose17Development/progress.json`及最新attempt为准。

### 历史执行记录（2026-10-23 12:30）

后续修复已通过真实运行：`player003_mrq_a02`两机位×3帧4K已完整输出，原生Pose采样/恢复及独立Editor postflight均通过；配对工具逐帧核对实际EXR相机/源帧/CPU fence，两机位世界点差0m，姿态去平移变化0.081m、0.143m。相关CPU回归69 passed。新增float32深度层两个机位共424个平面像素标定R为前向Z厘米，最大误差2.84mm。仍待近景头部语义、动态表面深度和关节可见性验收，不启用正式Pose批量生产。当前Editor30108保持打开、dirty空、MRQ结束，无GPU训练。运动覆盖阶段另已推送内层`2bcd18a`、外层`29ac753`。

四地板材质、可分发纹理源、独立seed颜色因子及只读UE验收入口已完成阶段发布：内层`d72c1b7`、外层`401bdf3`均已推送。19项针对CPU测试通过，真实UE已有资产读回及静态场景切换/恢复通过；尚未证明MRQ地板配对或泛化收益。

动态Pose诊断`Saved/Pose17Development/smoke/player003_mrq_a01`首机位输出3帧3840×2160 RGB和Object-ID EXR，但PIE结束后的延迟Python回调访问pipeline导致Editor崩溃，Pose收据未保存，不能视为通过。引擎源码确认该回调在PIE清理后一tick执行；正在把采样与恢复收据改为C++ pipeline生命周期内落盘，Python回调只读取文件。失败attempt与媒体保留，下一次使用独立attempt；v1未变，GPU训练未启动。实际EXR无深度通道，可见性仍为unknown，后续需独立深度/表面证据。

## 当前研究主线

本聊天持续跟进已启用（id=futsalposetrack），按独立功能验收节点汇报，不重复报告未完成状态。七个实际生产角色003–009已完成各自源形态/FBX/UE静态映射候选，主agent独立核验7mesh/35锚点的三角、重心、身份及SHA；动态/可见性仍未验。四地板颜色已在正式球场临时切换、同相机姿势预览并恢复原槽，非地板Actor/材质/灯光上下文未变、dirty为空；仅静态预览，不是严格MRQ配对或生产准入。证据见Saved/Pose17Development/root_landmark_integrity_a01.json及Saved/FloorDiversity/v1/scene_preview_a02。

用户已明确将重心转为Pose数据和姿态跟踪。主计划见[Pose研究路线](Docs/POSE_RESEARCH_ROADMAP.md)：逐mesh校准COCO17头部点，统一3D/2D Pose、mask及持续身份，研究密集交互中的遮挡与身份恢复，地板/光照作为独立可控因素。

10月23日核查旧R5 PID30956已不存在、状态末次停在seed20261025添加合成训练中；没有完整六模型结论。历史产物保留，不自动重启旧bbox参数搜索。下文第五轮启动记录是历史，不能据此认为当前仍在训练。

已通过真实MCP核实正式Level；角色存在隐藏驱动mesh和实际MPFBVisual两套组件，Pose采样必须绑定实际可见模型。Pose17、头部锚点、几何对应、旧Pose兼容及地板随机化针对回归98 passed。新增C++采样接口与独立MRQ pass均构建并反射加载成功，当前C++测试1 passed；Player_003已完成静态源/FBX/UE映射与一次真实17点诊断采样，动态、遮挡和RGB/mask同步尚待验证。四个地板实例已创建保存、参数读回和缩略图核验，世界XY/200cm纹理图已保存，尚未应用到地图。新Pose17批次尚未输出，不覆盖已有v1。当前Editor保持打开，dirty为空、MRQ未运行；GPU训练未启动。

## 已完成

- 正式无号码4K批次8seed、八天气、32个相机序列，20,116 RGB及同数mask，含逐帧bbox。
- 10FPS、每机位连续414–952帧；8组保持原train归属。原16/32组目标终止，持续跟进已删除。
- 正式目录G:/FutsalMOT_Dataset/v1_no_numbers_4k平铺为groups/seed_XXXXXXXX/cameras/，去掉clips/clip_000，修正引用及文本SHA，媒体未复制或重编码。
- 生产调度器结束；Editor核对自有checkpoint后正常退出。164个无外部引用的临时Sequence通过UE API删除。
- UE AutoSave关闭，默认地图指向正式球场。G盘旧staging/work/速度试验、过时文档及UE可再生缓存已清理；关键生产来源和未完成号码开发保留。
- 基准full，其余quick/basic如实保留，不声称全部逐帧像素审计。

## 已完成的代码发布与GPU试验

本轮数据结构、生产优化、研究入口和文档已推送：内层main为63b197c，外层master为120c55b，排除未完成号码实现。独立无号码发布树1710项Python测试通过；干净UE工程构建成功，4项PNG输出自动化测试通过。

GPU实验明确检验“合成数据能否在固定真实标注和计算预算下，提高真实足球的检测与多目标追踪”。A预训练、B仅真实、C真实加合成，统一GPU和检测/追踪协议，最终test保留。

研究目录D:/projects/FutsalMOT_Research。B已完成，C用300真实＋300合成，600样本/epoch、5epochs、750次更新；保留全部旧结果，不预设收益。图像从正式G盘引用，不重复复制4K数据。

GPU执行入口为内层experiments/sim2real/run_serial_pilot.ps1的Gpu阶段；实时输出及启动凭证保存在研究目录comparison，不把启动描述为已经取得增益结论。600张C训练图像的派生标签路径已按实际Ultralytics读入规则核验。

A/B/C同GPU检测、ByteTrack和TrackEval已完成。C首次训练在第1轮后被Windows重启中断，System事件1074与日志终点一致；未完成运行已封存在研究目录runs/incomplete_attempts。最终C使用冻结输入及原始预训练权重，完整执行750次更新，不接续残缺预算。研究目录comparison/gpu_production8_retry_state.json终态complete；旧comparison摘要已归档history/pre_production8。

C相对B：AP50–95下降4.29个百分点、HOTA下降1.57个百分点；AP50上升1.20个百分点、IDF1上升0.19个百分点，IDSW由5降为2。不能声称整体提升或统计显著性。详细结果及证据边界见[首轮试验结果](Docs/PRODUCTION8_PILOT_RESULTS.md)。该首轮已结束，后续GPU研究正在继续；最终test未使用，UE保持关闭。

## 历史GPU研究（完整保留，当前主线已转Pose）

- 全部300张选中合成训练图的框转换与正式可见框一致，最大归一化误差约5e-9。训练框形状、重叠、真实曝光及裁判误检存在域差异，不能归因于简单坐标bug。
- 第二轮比例/框五臂已完成。25%扩展框使HOTA/IDF1提高但AP下降，未通过预定整体门槛；全部失败臂保留在D:/projects/FutsalMOT_Research/round2。
- 第三轮三seed已完成：相对阶段纯真实平均AP +0.08pp、HOTA +0.35pp，HOTA仅1/3正向；未通过登记门槛。排除发现seed后的两seed也没有确认整体收益，不能只报告发现seed的67.61/77.33。
- SNMOT-152/153额外开发验证及16模型统一评估已完成。相对阶段真实，候选三seed平均AP +1.21pp但HOTA −1.22pp；局部身份收益没有推广。与151同比赛9，不能冒充跨比赛验证，test116/187继续封存。
- 第四轮及九模型联合450帧评估均已完成。添加合成相对等810更新真实控制，原151平均AP −1.499pp/HOTA −1.038pp；联合450帧AP −0.096pp/HOTA −0.240pp。primary及secondary均失败，不宣称整体进步，全部结果保留。
- 第五轮已按失败条件显式登记并启动：同一person保留头内比较head_real810/head_additive810，固定seed20261024/25/26、每模型360＋450＝810更新，六模型完整运行后统一450帧验证。换头本身的收益不能归因于合成数据，64到80通道也存在容量变化。
- 活动状态：研究目录round5/driver_state.json，日志comparison/round5_run.log（启动driver PID30956，以实际状态为准）；同一串行入口在六模型结束后执行round5_combined_eval，日志comparison/round5_combined_run.log，勿重复启动。前轮round2/3/4及其联合评估均已complete，UE保持关闭。新研究代码尚未另行Git提交，号码开发仍排除。
- 新增round5/round4/round2针对回归56 passed。CPU person助手另有前向、SGD及EMA磁盘加载证据；这些不能替代完整GPU训练或收益验证。

当前完整诊断与负结果见[迁移诊断及消融](Docs/TRANSFER_DIAGNOSIS_AND_ABLATIONS.md)。论文目标为2026年11月投稿CVPR 2027；最近邻论文、候选贡献、证据缺口及官方截止日期见[论文定位与计划](Docs/CVPR_2027_PAPER_PLAN.md)。现有八天气与八seed绑定，不能独立归因天气作用；当前多视角是数据属性，尚无融合效用评测。

## 后续

1. 完成实际角色COCO17锚点的源形态、UE LOD0及动画映射；先小样验证RGB/mask/Pose时序与可见性。
2. 冻结独立Pose17试产批次与配对视觉因素，研究姿态质量和遮挡后的身份恢复，见Pose路线文档。
3. 固定真实Pose标注与计算预算后再检验合成监督效用，最终test继续封存；不自动重启旧检测器搜索。
4. 号码开发作为独立未完成事项保留，不纳入当前Pose已完成贡献或提交。

入口：[README](README.md)、[Python README](Content/FutsalMOT/code/README.md)、[研究协议](Docs/RESEARCH_PROTOCOL.md)。本机证据位于Saved/Production、Saved/DatasetMaintenance和Saved/Archives，不纳入Git。
