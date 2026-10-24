# 位置监督控制协议与历史兼容证据

当前v4是同1000更新、两臂同序3000真实曝光，R3S1额外1000S，分域criterion和固定α=1/3；显式COCO sigma、cv4-only、共享检测与BN固定、FP32实际EMA，评last1000。旧v2的17×2 uniform sigma与toy官方FP16保存仅为历史，不作现在正式训练入口。下列原文中的命令/候选状态均按其历史版本理解，不能直接重跑或覆盖原预算。当前结果见[POSE_V4_RESULTS.md](POSE_V4_RESULTS.md)。

## 历史来源：POSE_LOCATION_V3_CANDIDATE.md

## 显式COCO sigma与Pose分支更新候选

本轮只新增候选模块及CPU测试，不修改正在运行或已冻结的v2 loss、Trainer、协议、数据或检查点，也不启动下一轮GPU训练。

### 已确认的loss语义差异

本机Ultralytics8.4.60的`v8PoseLoss.__init__`仅在`kpt_shape==[17,3]`时采用COCO17 `OKS_SIGMA`；位置头改成[17,2]后，原v2桥接落入`ones(17)/17`。实际只读CPU加载官方与derived初始化已确认：原鼻.026、眼.025、肩.079、髋.107等，v2全部约.05882353，均为float32。因此相对COCO预训练，脸部误差容差变宽、部分肢体变窄。这是确定差异，不能单凭它解释全部开发AP下降。

首个纯R开发结果相对预训练由keypoint AP .491896降至.288049，bbox AP .530914降至.500820；已有报告显示条件L2由11.04px至15.86px。纯R不含S，不能归因合成。既有曝光记录loss均有限、visibility始终0；actual/EMA更新1000。只读checkpoint检查确认EMA87个BN全eval且所有state有限；BN相对初始化有实际统计漂移，并非已发现BN忘记切eval。EMA/评价路径与真实数据几何另有独立核对，仍须把遗忘、小样本适配、学习率和BN变化当作待检验因素。

### 独立v3位置loss

`src/grf_ue_bridge/pose_location_supervision_v3.py`提供`coco_sigma_location_loss_class()`。它继续复用已验独立17bool `location_valid`打包、上游目标分配、bbox/cls/dfl与位置归一化，但显式将COCO17 sigma安装到KeypointLoss。没有visibility输出/BCE；真实v0仍只屏蔽位置，人物框保留；v1/v2位置均有效，不把S unknown变成visible。

CPU测试直接与原上游17×3 `v8PoseLoss.calculate_keypoints_loss`实算比较，剥离visibility BCE后，位置loss和xy梯度逐值相同；全缺点人物及无效点梯度为0。另用完整随机toy PoseModel的原始3输出头和exactXY头前向/分配/loss/反向对照，检测加位置loss及物理输出梯度在指定float容差内一致。测试没有复制一份期望公式作为唯一证据。

原v2仍保留uniform sigma且原结果完整保留，不能把新v3模块偷偷替换进旧run。

### Pose-only候选核心

`src/grf_ue_bridge/pose_only_calibration_v3.py`提供`configure_pose_only(model)`，原地配置实际exactXY模型并返回guard：

- 只允许Pose cv4分支参数训练，冻结共享backbone/neck和检测分支。
- 整体eval模式下仍保留autograd，固定所有BN running mean/var/count；Pose分支BN affine参数可训练。
- 物理51通道中的未输出visibility行梯度屏蔽并检查值不变；候选优化器须weight_decay=0，避免行级梯度屏蔽被权重衰减绕过。
- `guard.assert_unchanged()`核对冻结参数、BN统计及visibility物理行；`guard.enforce_eval_mode()`用于外层曾调用train后的显式恢复；`guard.close()`移除自有梯度hook。

调用方不能随后任意`model.train()`而声称BN固定，也不能包`no_grad()`切断Pose学习。没有Pose前景时，后续正式循环须明确处理零梯度更新及预算，不自动改成删框或丢样本。此文件不是新Trainer，也没有替root冻结lr、更新步数或选择结果。

单步CPU随机toy集成已验证：位置loss/梯度非零、Pose输出发生变化，同时原始box logits、class logits和解码检测前五通道逐值相同，所有冻结参数/BN及未输出物理行不变。该结果证明此独立CPU构建能隔离检测器，不替代未来真实图/GPU配对或MOT收益。

### 后续写盘候选

旧首R共350.29秒，其中checkpoint约228.33秒；缓存预热仅3.09秒且无淘汰，不能将本次主要开销归因图像缓存。下一独立Trainer可每50步、最终和明确安全暂停保存完整model/EMA/optimizer/RNG，逐步保留曝光和事务；正常暂停须保存当前完整数学状态。硬崩溃时若实际曝光更新超出last，必须将该尝试标失败，不能从旧last重放后宣称相同实际更新预算。该策略只是下一候选建议，本模块没有改活跃写盘频率。

### 最小CPU验证

研究Python运行`tests/test_pose_location_supervision_v3.py`与`tests/test_pose_only_calibration_v3.py`，本次4项通过。研究环境若没有pytest，可仅借用P1已安装的纯Python pytest，不安装/升级Torch或P1 Python；测试强制CUDA不可见，仅用64×64随机toy，不读取真实dev图片或封存test。


## 历史来源：POSE17_XY_TRAINER_CPU_SMOKE.md

## 位置头完整Trainer CPU兼容小样

`tools/smoke_pose_xy_trainer_cpu.py`只验证本机Ultralytics 8.4.60、Torch 2.6.0的单进程CPU兼容性。它从已核验SHA的官方`yolo11n-pose.pt`开始，走`pose_xy_trainer_class()`的严格迁移、实际数据加载器、损失、SGD、验证器、checkpoint保存和官方resume API。它不是研究训练入口。

### 输入与固定边界

工具在全新输出目录中自画4张128×128、明确写有`TOY CPU FIXTURE`的图片，train/val各2张，使用单类39列YOLO位置标签，即bbox与17×2坐标。训练和验证夹具可以相同；这里没有泛化评估。它不读取v1媒体、MRQ诊断帧、真实数据或封存测试集。所有fixture文件SHA记录在收据中。

必须显式CPU，`CUDA_VISIBLE_DEVICES=-1`、workers=0、amp=false、plots=false、compile=false。禁用网络集成和无图场景的字体检查，并以socket连接拦截器阻止网络；尝试记录留在收据中。使用batch=2、nbs=2、单线程、SGD、lr0=0.001、momentum=0.9、weight_decay=0、关闭warmup和增强。未覆盖AdamW、GPU/AMP、DDP或完整研究数据性能。

### 何谓通过

声明2个epoch，但首次在epoch0保存后停止，因此恰好1次优化器更新；随后以epoch0的未剥离checkpoint调用真正的`resume`，从epoch1开始，再完成1次更新。首次及续载后均断言：

- 三尺度隐藏容量和最终物理卷积输出保持51，暴露的关键点输出是17×2。
- 位置输出行梯度非零、参数实际变化；visibility行梯度为零，且在零weight decay下不变化。
- visibility BCE安装一旦调用便失败的哨兵；实际`kobj_loss=0`。
- 所有参数有限，完整Trainer验证、final_eval正常返回。
- 续载前，优化器全部保存tensor与加载后tensor逐项比较；允许官方保存FP16到优化器dtype的明确转换，EMA更新计数同时恢复。

当前本机首次收据位于`Saved/ResearchDiagnostics/pose_xy_trainer_cpu_a01/receipt.json`。279个SGD momentum tensor恢复相等，EMA更新计数1→2，首次/续载位置参数变化量均大于零，网络尝试为空。运行日志为同级`pose_xy_trainer_cpu_a01.log`。配置可直接读取该目录`trainer_run/args.yaml`；续载会复用同一run目录，首阶段未剥离checkpoint也保留了其原始train_args。

### 保存/续载限制

官方8.4.60 `save_model()`保存EMA半精度模型和FP16优化器状态；`final_eval()`会从last/best剥离优化器。工具因此在`on_model_save`时保留`initial_one_update_unstripped.pt`与`resume_one_update_unstripped.pt`，不会从已strip的文件声称恢复了状态。源官方checkpoint不修改，输出目录必须不存在。

这一结果证明该环境的续载API和下一步计算兼容，不证明中断与不中断训练轨迹逐位一致。EMA/FP16量化与随机状态恢复均可能影响轨迹，正式对照应固定相同初始化、优化器、更新预算及中断策略。日志中的toy AP没有研究意义，不能据其声称模型进步。

17×2使用本机默认位置损失的uniform sigma（1/17），并非17×3标准COCO sigma配置。真实与真实加合成两臂必须使用相同17×2损失配置；保留预训练网络容量不代表自动保留COCO损失定义。未知可见性仍然未知，不训练visibility head，也不能将位置标签称为COCO v1/v2可见性标签。

### 运行

```powershell
D:/projects/FutsalMOT/.venv/Scripts/python.exe -X utf8 tools/smoke_pose_xy_trainer_cpu.py --output D:/projects/FutsalMOT_UEDataset/Saved/ResearchDiagnostics/pose_xy_trainer_cpu_a02
```

完整兼容小样已经实际运行，不需要为文档检查重复运行；仅修改计算或续载路径后再开新attempt。夹具契约测试`tests/test_pose_xy_trainer_smoke_contract.py`不启动训练。
