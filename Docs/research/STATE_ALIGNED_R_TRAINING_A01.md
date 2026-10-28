# 自由状态R窗口来源：单因素验证a01

用户已授权依据完整诊断只选择一个因素。诊断结果与边界见[完整报告](TRAIN_FREE_STATE_GAP_A02_RESULTS.md)。本轮只替换R训练窗口来源；不同时修改候选门槛、历史写入、Kalman更新、模型容量或合成数据。

## 已完成输入阶段

8项CPU合同与真实六个R后验来源只读审计已通过。三个fold各1000唯一新R窗，允许两来源各500，全部原预测记录及标签逐条读回一致。输入根为DResearch/pose/state_aligned_training_a01/inputs_complete_root_a01.json，SHA `031e10a5a7cc078030747f901cc1bbe5bce8017542c524e38d47abf3e9d7d74c`。新输入不是新增图像/比赛，也不包含开发评价或封存测试。

| fold | 两允许来源可用唯一窗 | 选中窗 | all pair | known pair | positive | negative | unknown | 无positive窗口 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| game4 | SNMOT097:897、151:666 | 1000 | 13558 | 11500 | 435 | 11065 | 2058 | 565 |
| game6 | SNMOT060:944、151:706 | 1000 | 13167 | 10975 | 321 | 10654 | 2192 | 679 |
| game9 | SNMOT060:944、097:722 | 1000 | 15740 | 12765 | 359 | 12406 | 2975 | 641 |

teacher固定为原纯R强motion、同fold、seed20261024。只收高分stage、learned-active、三条严格过去且可信同身份历史、至少一个known pair；不要求每窗positive，不将unknown强标负例。不按成绩选窗，按源/帧/history UID/candidate UID固定排序、唯一去重，取各源前500。全部排除计数及未入选窗口描述保留在inputs_a01/audit.json。原full高分stage候选完整保留；后验缺逐candidate enabled掩码，因此不能称精确原模型评分子集。

只从既有预测cache重组uid/bbox/score/xy/geometry_valid/image_wh/timestamp七字段，不重新推理、匹配GT或补框。UID图像帧号一基、cache/index零基、time=index/25明确核验。新stratum明确free-state来源，gap_requested_sec=null、teacher_forced_history=False，不伪装成原五档gap采样。

## 下一步训练准入与绝对条件

训练现已按以下事前条件完成并独立验收，具体实际预算与证据见末尾最新闭合段。新18臂为R/RS×fold game4/game6/game9×seed20261024/20261025/20261026。模型194→64→32→1、ReLU、FP32，全部原强motion可训练线性层，标准化后170个Pose通道置0；不追加旧权重，使用每seed原初始化。normalizer仍仅引用原baseR，不在新池重拟合。源码核验更正：原v10强motion走v8 FeatureCache，仅原features→normalizer(use_pose=False)，没有按epoch施加扰动增广。本轮augmentation=none_original_strongmotion，不接T/gated的stateless both；只换R窗口来源。R曝光序使用原exposures SHA排序算法，S直接复制原v10表的synthetic列；新window UID与原五档gap身份明确区分。

每臂1000实际更新，AdamW学习率0.001、weight_decay0.0001；每步3R窗口，累计3000R。RS每步另1个原v10balanced S窗，累计1000S，S源及顺序不变；R和RS共用同fold新R来源及相同R采样顺序。R损失mean(3R)，RS损失mean(3R)+mean(1S)/3。每臂last1000，非EMA、无best选择；18臂总18000更新、54000R窗口次、9000S窗口次。这里batch以窗口计，动态候选pair数须逐步与累计实记；同窗口数不等pair/标签/FLOPs公平。

先独立冻结训练计划和最小源码，核原池/原无扰动特征194维、normalizer/初始化/固定S、全部UID顺序及known mask；CPU和真实CUDA一步手写/记录循环模型、AdamW、RNG逐值一致；首正式1000步全部21个完整检查点读回通过后才继续其余17臂。保留逐步loss/LR/grad、R/S UID/epoch/all-known pair及曝光链、stdout/stderr、0/每50/1000模型+优化器+Python/NumPy/TorchCPU/CUDA RNG，全部失败和负结果保留。性能复用已验有界预取/缓存，改变batch/AMP/前向数值须独立公平协议，不抢当前任务或少记录换速度。

训练完成与实际退出、预算终验后才冻结完整自由追踪矩阵。原3/旧2/七场三个已观察开发面板分别汇总，先各方法绝对AssA/HOTA/IDF1等，再配对差值/t95/固定比赛bootstrap/LOO，所有seed/fold/负项/null保留，不设等效δ、不以CI含0称相同。旧基线如来源/初始化/预算完全匹配才只读引用；不匹配必须明确新对照，不能假称单因素已闭合。

## 解释限制

本轮是窗口来源政策整体的验证，同时改变候选数量、query gap及类别分布，不能将可能差值单独归于其中一项。仅覆盖trusted三历史，不解决mixed/unknown/短历史的全部状态错位。标签是既有双向唯一IoU几何身份代理，未人工逐轨复核。原诊断eligible=0，不能借本轮假设声称history或Kalman因果已证实；实际追踪收益须等待全部匹配训练与评价。

每阶段结束自动更新训练历史并提交汇报。SNMOT116/187及test包持续封存，不读、不调。

## 当前训练阶段：准入与首正式千步通过

2026-10-28已完成21项输入/runtime/controller/数值CPU合同，另6项独立预算审计合同。原源码核验纠正：强motion没有按epoch扰动增广，明确none_original_strongmotion；不是T/gated的both。域loss为每窗known-pair BCE均值后窗口均值，不能改成pair加权均值。

实际CPU完整核九表及全部3000新R窗口/35240known-pair特征194维、原normalizer/后170零、九初始化/R顺序/原S顺序；CPU两组手写对原loss共4诊断更新12R/2S。实际CUDA两组手写对完整记录循环模型/AdamW/全部RNG/0和1检查点逐值一致，共4诊断更新12R/2S。合计8诊断更新24R/4S另计，不当正式训练。学习准入根SHA c56c9da4b15fe2d79790146987dcf248cd956bf121d4c03186d14bf3fc22f9bf。

协议training_frozen_a01/protocol.json SHA 2acc7642109c317b9ca694d3649a864c5553e177f20425d24726de1781c7d3c6，必要11文件bundle code/1f9a22471b51d11879ca6f20aa5449fc279bbfbba2835772469809af991ac983；不热改。正式18000更新/54000R/9000S的十八臂20:33:38唯一启动。首game4/seed20261024/R已实际1000更新/3000R/S0，21完整模型+AdamW+四RNG检查点读回通过，控制器才继续后续臂。首臂含准备/记录/检查点/读回24.6310秒，不外推全部阶段加速。当前训练仍在执行，不称十八臂/预算/追踪已完成，也没有新AssA/HOTA/IDF1。

权威state为DResearch/pose/state_aligned_training_a01/training_control_a01/driver_state.json，日志_launch_training_a01及training_control_a01/logs。独立审计已安装code/9609623d0cca265f971114fdf4417cb521f58255e755814b8582e5a6f353ff0a/tools/research_ops/audit_state_aligned_training.py，尚未真实执行；十八臂齐及实际parent/child/launcher全退后，才以--config绝对protocol --control绝对training_control_a01 --output绝对postrun_audit_a01/actual_budget.json --execute运行，CUDA_VISIBLE_DEVICES=-1。需核378完整checkpoint、18000步/全部UIDepoch/all-knownpair/原init/norm/S及真实退出；cache无显式close不伪造true，保留实际预取join和run退出证据。

冻结时计划原bytes快照training_frozen_a01/plan_snapshot.md SHA755851787d2e21cc8cbcf1e16b0b1d761a72f06588fbb35450ad74a8be4a20f6保留；本文件后续更新不改该快照或活动协议。下一阶段才冻结新18模型×每fold10来源=180自由追踪，原匹配基线只读引用，原3/旧2/七场分别报告，未通过加载/GT隔离/cold-ABA准入不执行。全部负结果保留，测试封存。

## 最新闭合：十八臂训练、独立预算及真实退出

2026-10-28十八臂均已完成，各1000实际更新。独立审计实际核18000步、378完整模型/AdamW/PythonNumPyTorchCPU-CUDA RNG检查点、step0原初始化、原normalizer、九组R/RS相同R顺序及原S顺序、逐步loss/LR/grad/UIDepoch/all-knownpair/链与全部实际退出。正式总量：54000R窗口次、9000S窗口次；R all/known pair764370/634320，S46287/25191。8诊断更新（CPU4、CUDA4）及24R/4S另计。重放0，原日志和所有权重/负结果保留。新自由追踪/TrackEval完成数仍0，没有新AssA/HOTA/IDF1。

训练完成根`pose/state_aligned_training_a01/training_complete_root_a01.json` SHA `62646594150716226b4cb90087731b8d2c76fb836bd22a3218a776031ebf5a33`；独立审计`postrun_audit_a01/actual_budget.json` SHA `d551bb377a8d33b6f454fa5f119723c06c085555c85c37c55b5080f53d671212`，status complete18_state_aligned_R_actual_budget_full_records_and_exit_verified。实际使用独立审计单文件bundle `code/710811cbb5a35744ce7d8ae376c11fb473d89446d7d823f17f8fe07348325f77`，将CPU与CUDA诊断全部另计；原960候选未执行且保留，不修改活动训练11文件或协议。

下一阶段使用[结果前追踪分析规则](STATE_ALIGNED_R_ANALYSIS_A01.md)：180新任务与匹配180旧基线来源，三原/旧二/七场分开。主要新RS−旧RS，另新R−旧R、新RS−新R及两者合成增量交互，五指标共60个未多比较校正描述区间；每场先均匹配seed/fold再比赛等权，t95自由度2/1/6、10000比赛bootstrap固定seed20261028/逐场留一。先绝对成绩再差值/CI；无δ/等效通过标志。候选加载runtime已做6CPU夹具检查，真实新模型加载/GT隔离/cold-ABA/spawn和完整worker/control冻结准入尚未执行，不能当180追踪已完成。测试116/187/test持续封存。

## 最新追踪阶段：独立新模型准入闭合与180项唯一启动

2026-10-28已实际完成新R来源模型的CPU加载、冷启动、A→B→A和双spawn数值准入：两源各48帧，共96唯一源帧、336诊断帧推进，五份完整MOT/原生逐帧/审计比较逐值一致，五worker均close/join/exit0且parent实际退出。原14593参数FP32 last1000、原baseR normalizer、170个Pose列置0、原tracker数值AST及GT坐标隔离均保持，不包装截距。准入不是性能提高证明，没有新增SGD或图像推理。

首次a01在加载训练runtime时因局部导入搜索路径缺少训练bundle工具目录失败，任何追踪帧尚未推进、成功payload为0。原code/827582、配置、failed及日志保留。按根因另立a02，仅在原complete_model调用域绑定原冻结训练输入模块并恢复sys.path，不改训练11文件/权重/记录；诊断收据tracking_numeric_diagnosis_a01/receipt.json SHA f449549e94bafa00185591e04589ba5f05692beaca8ad347ff1ece3acd2f0068。没有重跑已成功训练、预算审计、旧诊断或模型搜索。

实际成功数值收据tracking_numeric_a02/receipt.json SHA f41436086f66066179ef4e3fe6b10e00cad07567014286d3416be48fdeb53325；四文件追踪bundle code/53bf25ceef65e2f2fe8bf277da4e3a189e84c57430e3c297f31e8cb0d7219b47，正式tracking_frozen_a01/config.json SHA 5aa553b7d4d5734ee748e410157f5cf8ae0287e593bb04e75cbe816229a8411b。完整180矩阵与结果前60指标/12gap区间计划已冻结，原180基线仅读引用，所有负项/fold/seed/null保留。

已唯一后台启动tracking_control_a01/driver_state.json，2track+1独立metric常驻CPU进程，数值线程1，输入LRU128MiB最多2源、模型LRU256MiB最多3模型，物理RAM保留8GiB、commit保留6GiB。首R/RS两源完整追踪/GT计数/ID0/全预测门禁后才派其余178；控制器自动完整分析。活动源码/配置不热改，禁止第二控制器、手工散跑和重训。started不等完成，完整180/分析/全部进程退出后才实际运行独立终验；终验器单文件code/6dc4a6de9f91e1816a6fa730db081cfbd2ef4704ecba3cb24f38edd7cfd5d907。当前尚无完整新AssA/HOTA/IDF1结论，测试116/187/test继续封存。
