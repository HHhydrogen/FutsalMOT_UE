# COCO公开开发评价口径与独立身份链

当前v4使用独立coco_pose_dev_eval_v4与CLI，核新schema、同3000真实曝光、last1000实际FP32 EMA及新准入，同时直接复用下列原数值链；不伪装v3，也不改变原200个公开dev ID、置信度、GT area或后处理。下文完整保留v2/v3历史技术细节，命令是历史来源，不保证在目录/存储迁移后可直接重跑。旧收据SHA不重写。

## 历史来源：POSE_COCO_DEV_EVALUATION.md

## 固定COCO开发集的位置头评价

入口为`experiments/sim2real/evaluate_coco_pose_location.py`，计算代码为`src/grf_ue_bridge/coco_pose_dev_eval.py`。只接受当前协议SHA、准备收据链和精确200个`val2017` ID；读取原始关键点标注子集，不把训练用`location_valid`伪写成COCO v。它不签署训练准入、不冻结候选协议、不读取SNMOT116/187或任何test目录。

当前准备目录是`D:/projects/FutsalMOT_Research/pose/coco2017_location_a01`。原候选协议仍保留候选状态；预训练参考可以直接绑定该候选。正式last评价必须绑定单独的root冻结协议及实际SHA，沿`root_freeze.candidate_protocol.{path,sha256}`核验原候选，再核验COCO准备收据中原候选SHA；**不重写旧准备收据成冻结SHA**。冻结协议需`training_authorized=true`、`root_freeze.approved_by='root'`，且real_selection/data_root/initialization/paired_training_candidate/arms/development_evaluation_candidate与原候选一致。可新增S、采样表与准入收据绑定，但不能借冻结步骤更换dev IDs或对照预算。报告分别记录实际冻结协议SHA与原候选SHA，不把二者混用。

### 指标与置信度

主指标由官方`pycocotools.COCOeval(iouType='keypoints')`计算，输出AP、AP50、AP75、APM、APL及对应AR，标准OKS sigma与`maxDets=20`保持官方默认。官方`-1`保留，表示该面积组无适用目标，不改为0。没有pycocotools时异常退出并写失败记录，绝不仿算AP。研究Python3.10现有pycocotools2.0.11；CPU数值夹具已真实调用官方实现，完美预测AP=1、空预测AP=0只证明夹具与入口，不是实际模型结果。

模型只有17×2坐标输出。每个预测人的检测分数统一复制到17个点的结果第三列，作为固定的预测分数载体；**不是可见性v，也不是校准过的独立关节置信度**。不读取GT v来生成预测，不使用旧物理51通道中未训练的visibility行。官方评价只用GT v>0的位置计算OKS。真实`num_keypoints=0`人物继续保留，其关键点ignore行为由官方实现决定，检测框辅助评价仍计入这些人。输入COCO关键点area保持原值；bbox辅助评价若有准备阶段严格join的instances area，使用独立GT拷贝恢复该area，不修改关键点评价。

辅助指标包括官方bbox AP/AR、按检测分数排序且bbox IoU≥0.5贪心一对一配对后的像素L2、按原COCO关键点area平方根归一化误差、PCK，以及全部GT人物框/有标注点的匹配覆盖率、全缺点人数和尺度分布。位置误差是匹配条件下的统计，必须与漏检人数及覆盖率共同阅读；不能靠漏掉难例得到看似更低的误差。bbox评价使用同一最多20个预测，虽COCO bbox AR100参数保留，实际输入仍受20上限约束。

本开发子集只有200张且整图排除了crowd，不能当作完整COCO val或独立最终测试。初始化已经COCO预训练，结果属于固定子集上的继续训练。Pose AP包含检测质量变化；不能据此宣称AssA、HOTA或足球追踪提升。

### 固定推理与模型选择

默认CPU，只有显式`--device cuda:0`才请求GPU，并先只读检查Windows没有UnrealEditor进程。调用者负责在渲染完整结束和Editor安全退出后安排GPU。无自动设备选择、下载、AutoBackend、fuse、TTA、AMP或half。每张图只读一次并核对准备收据SHA/尺寸；只打开精确val图片，不读train图像。

输入为与训练一致的640中心LetterBox，OpenCV双线性缩放、整数padding、填充值114、RGB/255。NMS采用本机Ultralytics8.4.60，confidence=0.001、IoU=0.7、单类、每图最多20人。预测框回原图后截断；关键点保留有限的画外amodal坐标，不截成边界点，也不改变unknown状态。这一固定策略用于全部训练arm和预训练参考，不额外挑阈值。

正式对照只读`last.pt`中的实际FP32 EMA PoseModel。必须是完成的1000步，并核验`completed_updates`、`planned_updates`、`ema_updates`、协议与采样表SHA、arm/seed、曝光链及完成运行收据的完整bindings。要求实际保留51通道卷积再索引xy的严格适配，不从YAML重建34通道塔。`torch.load(weights_only=False)`只在实际文件SHA等于调用者明确钉住的可信本地checkpoint后执行；不能用SHA替代对文件来源的信任。预训练参考只接受协议中的官方或已绑定的严格xy权重SHA，并统一转换成同一xy输出策略。

### 命令

在内层目录使用现有研究环境；以下变量值由固定文件/收据填入，不自行选择best或更换dev ID。

```powershell
$researchPython = 'D:/projects/FutsalMOT/.venv/Scripts/python.exe'
$protocolPath = 'experiments/sim2real/pose_location_coco_candidate_protocol.json'
$protocolSha = 'b2946b58b8e2b10510f185815018e698cee25b705433590494ae3913f7d15c33'

## 预训练参考：同一17xy输出、相同分数策略；显式CPU。
& $researchPython experiments/sim2real/evaluate_coco_pose_location.py `
  --protocol $protocolPath --protocol-sha256 $protocolSha `
  --checkpoint D:/projects/FutsalMOT_Research/weights/yolo11n-pose_xy_location_exact_a01.pt `
  --checkpoint-sha256 c41fee957f91da4657f5b4f8822e22d53c6c527074c102e0a8c7490cf97736ec `
  --checkpoint-role pretrained_reference --device cpu --output <全新评价目录>

## R/RS25：使用Research下实际frozen协议和它的SHA；不得沿用候选SHA。
## run_receipt与last必须完成同一1000步，采样表SHA从冻结收据取得。
& $researchPython experiments/sim2real/evaluate_coco_pose_location.py `
  --protocol D:/projects/FutsalMOT_Research/pose/coco2017_location_a01/frozen_protocol_a01.json `
  --protocol-sha256 <冻结协议实际SHA> `
  --checkpoint <本arm目录>/last.pt --checkpoint-sha256 <last实际SHA> `
  --run-receipt <本arm目录>/run_receipt.json --run-receipt-sha256 <运行收据SHA> `
  --schedule-manifest-sha256 <冻结采样表清单SHA> --device cpu --output <全新评价目录>
```

输出`predictions.json`、`predictions_receipt.json`、`report.json`和官方原始统计日志。全部200张必须记录processed ID，包括零检测图。缓存重评使用`--predictions`、`--prediction-receipt`及`--prediction-receipt-sha256`，仍重验完整开发集绑定、预测文件SHA、固定后处理和点分数策略。该模式验证收据一致性，不能鉴别有人伪造了整个预测及收据；公开结果仍应保留首次推理的checkpoint和日志。

所有输出要求全新目录，失败保留`failure.json`。CPU测试：

```powershell
$env:PYTHONPATH = 'src'
& $researchPython -m unittest discover -s tests -p test_coco_pose_dev_eval.py -v
```

测试仅使用数值夹具和自绘小图；没有读取实际dev图像、真实test、运行真实模型GPU或宣称研究AP。它覆盖元数据篡改/ID泄漏、缺失零检测图、伪可见性、完成预算门禁、奇数LetterBox、真实CPU NMS布局和官方COCOeval的完美/空预测。


## 历史来源：POSE_COCO_DEV_EVALUATION_V3.md

## 独立v3 Pose-only开发评价

入口`experiments/sim2real/evaluate_coco_pose_location_v3.py`，身份适配模块`src/grf_ue_bridge/coco_pose_dev_eval_v3.py`。它不修改旧`coco_pose_dev_eval.py`、旧CLI、Trainer或协议。推理、17xy评分策略、LetterBox、NMS、官方COCOeval与辅助位置计算直接调用旧实现，并将旧数值文件SHA锁为`c5f2cf886cd6549385b82504e0a5cdfab2fa16242a1ba8315fb984daef84e7ee`。旧实现变化时拒绝执行，不能把协议版本变化变成评价计算变化。

### 身份链

v3使用独立schema：协议`futsalmot_pose_location_poseonly_protocol_v3`、准入`futsalmot_pose_location_poseonly_admission_v3`、checkpoint`futsalmot_pose_location_poseonly_checkpoint_v3`、运行收据`futsalmot_pose_location_poseonly_run_v3`。原v2文件不能直接作为v3输入。必须用新协议实际SHA，不伪装成旧SHA。

验证链为：新冻结协议及root准入 → `source_v2_protocol/source_v2_admission`实际文件SHA → 旧冻结协议 → 原候选与COCO准备收据 → 相同的200张公开val ID和GT。R/S JSONL及各seed的原共享采样表也核验实际SHA，源码清单与准入一致。初始化及R/RS曝光预算保留原值，v3新`paired_training`与policy另行验证（1000更新、640、SGD lr1e-4、cv4-only、BN固定、显式COCO sigma、FP32 EMA）。这不声称学习率、冻结及sigma是单一因素实验。

这里只读取所需JSON/JSONL、源码和已选checkpoint，不打开图片来验证身份。所有图片推理仍由显式checkpoint评价命令触发。封存test边界、整图crowd排除偏差、公开dev不能作最终测试等限制沿用旧入口。

### 最终模型门禁

只接受实际`last.pt`的EMA，完成更新、计划更新和EMA计数均为1000，并与完整运行收据的策略、arm/seed、实际曝光数、初始化状态和曝光链匹配。检查标准bindings与`v3_`别名都指新协议/准入/Trainer，`source_v2_bindings`及R/S/采样表仍精确指原来源。

v3 checkpoint的choice为`last_actual_FP32_EMA_no_best`，完成run的choice为`last1000_actual_FP32_EMA_no_best`，分别按真实writer验证。`actual_ema_fp32=true`之外，还在任何`.float()`转换之前检查实际EMA全部浮点state确为FP32；实际头需保留物理51通道并严格索引为17×2。不能把FP16先转FP32后声称原EMA就是FP32。不重建YAML、不挑best、不读取GT来选择预测。

可用`--checkpoint-role pretrained_reference`在同一v3开发绑定下评价原官方严格xy初始化，数值策略完全相同。历史v2预训练报告的GT/数值相同并不等于其收据自动变成v3；缓存收据必须有正确v3schema与新身份链。

### 命令与输出

```powershell
& D:/projects/FutsalMOT/.venv/Scripts/python.exe experiments/sim2real/evaluate_coco_pose_location_v3.py `
  --protocol <独立v3冻结协议.json> --protocol-sha256 <新协议SHA> `
  --admission <root新v3准入.json> --admission-sha256 <新准入SHA> `
  --checkpoint <本arm>/last.pt --checkpoint-sha256 <last实际SHA> `
  --run-receipt <本arm>/run_receipt.json --run-receipt-sha256 <完成收据SHA> `
  --device cpu --output <全新v3评价目录>
```

默认CPU，GPU仍需显式cuda:0且通过旧推理函数的UE串行门禁；不得在其他GPU作业并行时擅自启动。输出独立v3 predictions receipt/report及官方日志，原始关键点第三列仍统一广播person预测分数，不是物理visibility或独立关节confidence。主指标AP/AR与辅助bbox、覆盖率、位置误差完全复用旧函数，不改GT v/area或点顺序。

CPU夹具验证新旧协议拒绝、来源SHA篡改、预算/别名/实际FP16拒绝、同一夹具的官方评价数字逐值相同。没有真实v3 checkpoint/开发图像推理或GPU结果，本文件不授权训练。
