# R候选资格mask：输入、真实数值准入与训练执行

更新：2026-10-29。科学方案见[唯一因素协议](R_CANDIDATE_ELIGIBILITY_MASK_A01.md)。本页记录实际执行，不改写旧冻结文件。

## 要验证的问题

旧诊断发现原R损失覆盖了推理资格外的known候选；这不等于标签错误，也不证明它是退化主因。本轮仅让R损失使用原概率判断前的active且enabled资格，验证监督范围对齐能否改善完整自由追踪。原未校准strongmotion_RS始终是主参照；已完成的aligned-BCE十八臂用于隔离mask这一因素。没有新Pose、RGB、人工标签或算法伪标签。

## 输入与绝对训练条件

三fold game4/game6/game9，各复用原1000唯一R窗、两允许train来源各500，来自SNMOT060/097/151；原pool、UID、历史、标签、顺序、九张曝光表、normalizer及初始化不变。3000窗含42465候选、35240known（1115正/34125负）、7225unknown。资格内known6153（1092正/5061负）、unknown2081；993窗有效known为空，2007窗非空。不复制或重采样填额，unknown不进监督，排除的23个known正例也完整留存。

模型194→64→32→1 ReLU、14593可训练参数、FP32，归一化后170个Pose列置0；输入为每窗候选×194特征，不读取图像。原known特征一次拼接前向，R逐候选BCE后只对资格内known求窗均值，再固定三个R窗均值；RS另加原S窗known-BCE均值的1/3。空R有效集合用带图零损失，保留零梯度、AdamW动量和weight decay更新，不跳更新。

18臂=R/RS×三fold×seed20261024/20261025/20261026。AdamW学习率0.001、weight_decay0.0001、betas(0.9,0.999)、eps1e-8、amsgrad=False；无AMP、EMA、best选择或epoch扰动增广。每臂1000更新，每步3R共3000R，RS每步另1S共1000S，S仍为原v10 balanced池。取last1000。预取2、输入缓存256MiB；完整逐步loss/LR/梯度/UID/epoch/all-known与有效pair链、原stdout/stderr、step0/每50/1000完整model/AdamW/Python/NumPy/Torch CPU/CUDA RNG均保存。

正式目标18000更新/54000R/9000S，原R all/known764370/634320、S46287/25191；有效R known110754=19656正+91098负、监督unknown0，有效非空36126/空17874窗。窗口曝光相同不等有效标签、pair或FLOPs相同。另列准入更新，不计正式预算。

## 已完成的真实门禁

输入a02生成成功，独立a04逐条来源/资格/曝光核查通过，完成根SHA `48e50a9acb3f0d8e0afffc49b6f070e6ab2467af01e660e31aeca672ec0c1ffb`，独立收据SHA `40988c1a5ff2d9327ba9740d8d48744c4e4d8e30ccc8ce06e56835ab2adb4009`。科学训练协议SHA `d5880b07e97e1252852c7c70ee5b1961b04f5825838063f8e84b462559388daf`，八文件bundle `98293655dd3bd73d96909bff820876495776c2bf4518a92826cc8eb54ecefe2c`。

真实CPU/CUDA十组共20诊断更新/60R/8S已完成：R/RS的全true原BCE兼容和实际mask独立手写对照，以及空窗且已有非零AdamW动量/weight decay的压力组。loss、每参数梯度、模型、AdamW和四类RNG逐值一致，完整step0/1记录读回。各设备内部的手写与记录路径逐值核验，不将CPU与CUDA彼此数值相同作为要求。数值收据SHA `bccf1069d205288b45db4aeaa380fc202f75815601e791265e076581f76f514a`，学习准入根SHA `7c8dd9a62aaf9877462469f5a48d614645d3326d1d6b210b9b155e3c39af3f87`。matched-control数值兼容已实证，不重跑这些成功组。

首game4/20261024/R完整1000 CUDA更新已完成，独立CPU核查21份完整检查点及1000步记录通过，收据SHA `28096dc3f43cd4fc2749d1da439c13a98a5e318e9a85070bac6c0239f7148b64`。其余17臂只在此门禁后启动，现已全18完成并经独立预算审计，尚无完整新自由追踪成绩。

## 失败与独立执行修正

输入P1缺psutil在读窗前失败；独立输入核查器先后因目录白名单callsite和既有字段名假设失败。旧配置、源码、failed和日志全部保留，只修核查器，不重建成功输入。

正式控制器a01在写预飞收据时调用不存在的runtime.write_new，训练子进程启动0、正式更新0、输出目录为空；异常现场保留。仅修执行控制器直接导入原journal写入函数，8项针对检查通过。另装单文件bundle `f5614469f2c6a8821eb0e111110ea6473f5f5ba389737a51ffd7ac01eca35e6a`，以独立执行声明SHA `ee28048855d78551c8b9855e35e44a4114494a0798b644652c6388b73442279d`绑定原科学协议和失败0更新证据，唯一启动training_control_a02。原八文件、模型、损失、参数和20步成功数值准入均未改变或重放。

## 后续闭合与评价

18臂齐及真实退出后，独立审计复用首21检查点成功证据，再逐份读其余357份，覆盖378份并核实际预算/全记录，不重训。之后新loader/常驻worker需真实cold、A→B→A、spawn及原tracker数值门禁，方可冻结执行180项自由追踪。原tracker绝对参数high0.25、low0.10、new0.25、buffer30、match0.80、lowassign0.50、unconfirmed0.70、fuse=True；dt≤1.2秒、面积比0.25至4、中心≤2、模型概率0.50不变。训练mask不追加到推理政策。

结果前analysis已冻结：新RS−原strongmotion_RS为主，另新RS−aligned_RS、新R−aligned_R、新RS−新R及合成增量交互。六方法各原3/旧2/七场面板先列绝对AssA/HOTA/IDF1/DetA/MOTA，再保留450匹配指标/450gap配对、75指标和15gap未校正描述区间；540仅为三组各180绝对来源数。每场先均匹配fold/seed，再比赛等权，t95自由度2/1/6、10000次MT19937比赛bootstrap seed20261029及LOO。全部负项/零/null/seed保留，不设等效界限、不以CI含0称相同；gap沿原3690事件分母，不称物理遮挡。

全部产物位于DResearch/pose/r_candidate_eligibility_a01；实际状态以training_control_a02/driver_state.json和之后的独立收据为准。RAM保留8GiB/commit6GiB/VRAM2GiB，不抢UE或用户应用。12来源均为已观察开发；SNMOT116/187/test封存，每阶段更新历史并汇报，完整追踪前不宣称改善或Pose收益。

## 十八臂预算闭合与正式追踪启动（2026-10-29）

独立审计实际成功，SHA `b4d206ee8d8d0f1e7f548273b3ab232f41bb2356fb3bfb110021b20b97908d52`；完成根SHA `894ac3902ac862b3fc12411f2c33fc110f96a6e56b9d3bebc3975456f6b26ef8`。18个训练子进程均exit0，18模型/18000更新/54000R/9000S、全步链/九R-RS同序、原init/norm/S、原始与八项有效监督计数均实核；357本次完整读回+首21独立继承覆盖378。R有效known110754、正19656、负91098、监督unknown0，资格unknown37458单列；523566known排除、17874空窗不冒称无效更新。训练/launcher/auditor真实全部退出，旧模型/审计未重放。

新独立tracking loader只读新last1000及原normalizer小JSON，不调用训练prepare/audit、不打开训练池/mask/标签；GTguard先装。真实96唯一源帧/336诊断消费cold、A→B→A、双spawn五比较的完整MOT/native/audit逐值一致，5worker与parent全退，收据SHA `b70164ae9601db84d97b767cefd1786c4987d0b263d71d8b5ba20c133a1760fd`。四文件bundle `62e9c969da9547077aac7a63d51657a8a09e3eeec80bd1c8d48817a2b19ae33a`不可变；正式180协议SHA `a5bd1186ef7ab2238b8a73c098c23476e1df581409ee1f5570fa962885a36456`已通过默认只读预飞，唯一正式CPU后台已启动。首R/RS两源完整TrackEval/原GT计数/ID0/全预测门禁已过，继续余178与自动分析。

2track+1metric、数值线程1，输入LRU128MiB最多2源、模型LRU256MiB最多3项，RAM8GiB/commit6GiB预留。180新追踪/评价，另外360原strongmotion/原aligned结果仅读引用；不等540项新评价。独立终验器已安装单文件bundle `636ec5c5b41fe3286cc85c8cc1981e20cd96c3ae7ca33940f85d2631eba1ee04`，只在180/自动分析/全部进程真实退出后执行，不重权重/模型/GT/TrackEval或训练预算。

新增runtime6、control8、analysis12、独立verifier13项纯fixture及必要字段聚焦检查通过；首次control测试cwd错误导致ModuleNotFoundError发生于实际fixture前，模型/帧/更新0，小失败收据Saved/ResearchBuild/r_eligibility_tracking_fixture_invocation_failed_a01.json保留，正确cwd检查后通过，没有安装库或改环境。当前不得读取局部成绩调参数，也不宣称新方法优于任何参照。
