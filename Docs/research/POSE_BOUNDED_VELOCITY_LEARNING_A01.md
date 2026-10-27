# 有界变化编码单因素学习验证

更新：2026-10-27。用户授权先完成实际训练数值及完整记录准入，再开展匹配训练和自由追踪。此前[CPU合同](POSE_BOUNDED_VELOCITY_CPU_A01.md)不等训练或收益；本阶段独立输出到`D:/projects/FutsalMOT_Research/pose/pose_velocity_learning_a01`。测试SNMOT116/187及test包继续封存。

## 当前实际阶段

27臂已全部真实完成并退出。独立`postrun_audit_a02/actual_budget.json`实际读回567份完整模型/优化器/RNG，验证27000更新、81000R/18000S、R all/known pair 304020/234738、S 92574/50382，同初始化/曝光顺序/全部逐步loss-LR-梯度/链通过，重放0；6诊断更新另计。完成根`training_complete_root_a01.json` SHA为`6b97afe66bc25d23f709c0527b1dc62b697896b4bff7d1241eb259b09b3cca2c`。此为训练/记录完成，不是Pose增量结论。

`paper_training_archive_a01`也已真实导出27000行原始`steps.csv`、27臂`runs.csv`和全部日志/检查点来源索引。root另逐行核对原loss、空S的显式null、完整R/S UID-epoch与SHA链、总pair及cache原字段，`complete.json` SHA为`cea1e171e068bb749667f1170056e9fe1d49a4b3f32e5932a0b37ec98be05451`。导出器最小bundle为`code/6ef382f17fb52faed05534083d230be0e7c701940ffe3663225f3e936d64f786`，4项CPU检查通过；不加载权重/图片、不读追踪指标、不平滑、0新增更新，原567检查点仍留原目录。

首次独立审计a01对资源关闭有错误假设：原`OrderedPrefetch.close`只join生产线程并释放lease，不调用缓存自身close，所以全部原`intervention.closed=false`如实保留。27份预取收据均closed=true/worker_alive=false、loaded=yielded=1000，实际run进程均退出；独立a02改为在这些证据全部成立时确认资源退出，仍拒绝缺失证据，9项回归通过。原失败intent/failed、`postrun_audit_diagnosis_a01.json`、旧审计bundle2e360…全部保留，未改训练、权重、原字段或冻结80e源码。a02独立审计bundle为`code/12789a9c8f1ad00a6bbb42b4f74682e78cf40a49d27c389cf9eec5127a17f655`。

14:29:25+08通过真实只读预飞后唯一启动的513项CPU追踪/评价/分析，已在16:14:59+08全部结束，实际控制器、子任务及launcher退出。协议`tracking_frozen_a01/config.json` SHA为`ac89537c28668959729ea8d1930ca79c8f3ceff2da98c93bd54940467ebfd16d`，六文件bundle为`code/923a3931504debfbf9a85f8b4333637a1d200d4bae565a48bf61a0f89c19ea1a`，原字节不变。首新adapter7719次实际调用/195维/AST及TrackEval门禁保留；没有重跑任务或按中期值改协议。

首次独立终验9beb实际失败，根因是检查器将旧五场公开收据的`event_counts`误按七场`sequence_event_counts`读取；原收据、ledger及结果正确保留。独立a02仅适配明确历史status/schema，拒绝未知或混合字段，新增回归先复现同一KeyError，随后8项检查通过。新单文件bundle`code/325f6f9bba5ff927c4d79f403a424ef7ab31929107e00a65b7bb709a3e362def`实际终验通过，核全513来源/MOT/GT计数、270参考、720指标及720断档配对、120指标区间及另24断档描述和真实退出；不重推理、TrackEval或预算。`final_verification_a02/receipt.json` SHA为`71597848f615666395c4ae593dd3488f13f48fe943f4ba8f5762c2ad2a464714`，a01失败收据和旧9beb保留。

[完整结果](POSE_BOUNDED_VELOCITY_LEARNING_A01_RESULTS.md)及根`complete_root_a01.json`已签，根SHA为`6b864d4a136e55744f2da8b3da73ae4dff8cbe6a1aa9c7acc1f6606d847001e6`。七场AssA新T_RS−强motion为−0.0582点，95%t区间[−0.2245,+0.1080]；对原gated−0.0500 [−0.2731,+0.1731]；自身开启−关闭+0.0106 [−0.0524,+0.0736]。额外S的+0.2643 [−0.2472,+0.7758]与真实形状−打乱+0.1164 [−0.0522,+0.2851]均保留不确定性；本轮未建立编码改善或Pose可靠增量，不称等效或所有Pose方法无效。全部负结果保留，测试封存，不重启27臂或513追踪。

训练前准入已真实通过：12项输入/协议/数值CPU检查、三fold×三seed共9张曝光表完整CPU核对，以及三组真实CUDA一步手写/记录循环逐值一致。0/1完整模型、优化器及Python/NumPy/TorchCPU/CUDA RNG均实际读回，6诊断更新/18R/4S另计，诊断权重不进入正式训练。9表最终已知pair打乱特征改变率R为94.986%–97.156%，S为87.031%–87.210%；回退及未变化全部保留，不用bank映射率替代实际覆盖。

学习协议SHA为`b5c47218debb3a77dbc3577dda439cffccd9d90f87aa667f65c11f10584ba6b2`，十文件最小bundle为`code/80e2aac068dad1ceb16b8d7acc9c69f03991df83ab873094935b8d09e2706005`，准入根`learning_admission_root_a01.json` SHA为`770fc4c67fbd42fbf1614db9628d49c88f30ec5320a2e0ea522414c0fe95d2c2`，实际环境SHA为`27cb67c561f253ea998009ed7f059abf01c62b56f0ff589304ccf30725ff7aed`。默认只读27臂预飞已通过，14:05:30+08唯一启动`control_a01`，启动不代表27臂完成；真实进度以state及Name/CommandLine为准。不得重复启动或热改冻结源码。

首个正式game4/20261024/T_R先完成1000次实际更新，控制器独立读回21份完整模型/优化器/RNG并核验步链和窗口预算，`first_run_end_to_end_gate.json`为`complete_first_formal1000_full_records21_verified`，重放0；其后才继续其余26臂。如今整批已经上述独立a02审计完成，仍不能将记录验收当收益。

原独立审计a01候选有6项CPU检查，实际失败及后续a02修复见上；新追踪输入适配3项CPU、runtime/jobs8项、control/分析7项、终验器6项均独立复核。新T关闭仅把末gate置0；历史motion_residual参考没有Pose分支，不将其误标为同一个gate0操作。静态检查不代替实际首adapter门禁或完整513验收。

## 研究问题与唯一表示改动

检验原预测Pose中显式历史变化是否比原历史均值更有用。保持194维输入和原gated网络20098个名义参数，只将17关节的34个历史均值通道改为身体框归一的历史速度，按允许基础trainR的99百分位尺度归一并限制每关节向量范数≤1，不乘目标时间间隔。最近点无效或不足两个有效历史点时速度为0，不升级mask。其余160个原始及标准化通道保持，原质量gate始终从未替换的原始特征计算。

34个新通道的标准化仅以各fold原1000个唯一基础R窗口的已知候选拟合，使用原std下限.05和标准化截断5；其余通道保留旧normalizer。T_R/T_RS/打乱组共享这份新normalizer，S及所有外部比赛不参与拟合。原速度界限为game4/6/9的13.7146302384、12.8278413777、13.6084333713，已在零更新阶段固定，不搜索分位数。

## 矩阵与真实预算

| 组别 | 每臂窗口曝光 | 新训练臂数 |
| --- | --- | ---: |
| T_R | 原3000R同序 | 9 |
| T_RS | 原3000R同序，另1000 balanced S同序 | 9 |
| T_shuffle_RS | 与T_RS相同，从首步打乱形状对应 | 9 |

三fold为game4/6/9，三seed为20261024/25/26。每臂1000实际更新，总27000更新、81000R/18000S窗口；窗口不是独立图像，也不等FLOPs。FP32、AdamW lr.001/wd.0001、mean(3R)+mean(S)/3、原无状态drop/jitter、预取2、256MiB缓存、4096观测缓存和last1000保持，不挑best/EMA/seed/比例。

原强motion、原gated及同名义容量motion_residual的R/RS参考只读来源复用，新增更新0。九份v10 balanced motion_residual_RS已具有同R/S顺序、池、初始化和1000步预算；其有效输入只读前24个运动通道且gate为1，新34个Pose通道不影响该输入。结合本轮前24逐值守卫和原数值循环准入，可复用该参考，无需再加9臂。名义参数相同不等有效统计容量相同；历史缺失的中间RNG/梯度等仍明确缺失。

打乱控制用允许训练池内同实际帧、尺度格、精确有效mask的预测供体，按固定SHA选择，不读GT身份、不使用未来。必须先打乱完整形状，再重新生成坐标、距离和速度；只打乱34个速度通道不能充当完整形状负控制。原motion、mask/覆盖和质量gate仍保持。无合适供体或边界不兼容就保留并登记，报告实际覆盖，不能宣称全部样本已打乱。该控制可能改变正则化和分布，不能仅因打乱组变差就推断真实Pose训练有益。

## 实际准入与全过程记录

独立bundle绑定新runtime、输入适配、训练、控制、数值入口、原候选、完整记录循环及原预取必要源码。原v9/v8模型、特征、扰动及损失从其真实冻结bundle显式导入，不复制旧runtime到新ROOT冒充历史身份。

正式前分别对三组真实首批做手写CUDA一步与实际记录循环逐值对照：首批特征/标签、总及分域loss、LR/梯度、模型、AdamW和Python/NumPy/TorchCPU/CUDA RNG全部相同，0/1检查点实际读回。手写及记录合计6诊断更新单列，诊断权重不进入正式训练。首个正式千步须再独立读回21份完整检查点、步链和实际预算，通过后才继续其余26臂。CPU测试通过不能替代这些实际准入。

所有臂留存逐步loss/LR/梯度/耗时、R/S UID/epoch/all及known pair、来源环境、初始化和曝光SHA链、0/每50/1000完整模型+优化器+全部RNG、stdout/stderr、失败及干预覆盖。已有/未知partial拒绝覆盖，超出last的数学更新不猜测重放；人工停止不自行重启。训练完再独立核对全部27臂567份检查点和实际预算，新增审计更新0。

## 追踪与论文口径

训练结束后独立冻结新checkpoint加载身份和自由追踪协议，不用旧v10身份冒充。每fold保留其对应原heldout、两场旧外部以及七场已观察资源开发比赛；全部raw预测共享、GT仅指标/登记，Pose GT不入特征、不筛预测。T_R开启、T_RS及T_shuffle_RS各开启/关闭Pose，9个匹配fold/seed共450项新表示追踪。来源检查发现同容量motion_residual_RS只在原五场有评价，七场A/B/C未包含这一架构；因此还需另做63项历史模型的七场CPU追踪参考，新增SGD为0，总实际追踪候选513项，不能伪造已完成参考或省略主要对照。强motion/原gated的完整90来源各复用，同容量原五场27来源与新增七场63分别记账。全部实际矩阵在执行前冻结。关闭使用各自训练得到的motion分支，不假称它们是同一个模型。

预登记报告T_RS−T_R、T_RS−原gated_RS/强motion_RS/同容量motion_RS、T_RS−打乱组，以及各自开−关和两组都关闭时差值。AssA主，HOTA/IDF1/DetA/MOTA及全注册断档proxy次，保留全部比赛/seed/fold/负结果。原两外部与七场分开描述；每场先均匹配fold/seed，再比赛等权并报告描述区间及小样本限制。三fold/seed不当独立比赛。已观察比赛不称新盲测，区间包含0不称等效，不补设非劣效界限。

只有真实T超过独立强motion/同容量且证据在完整追踪中支持，才讨论Pose增量；若仅打乱退化或共同状态排名变好，不宣称任务收益。若仍无增量，保留负结果并收缩结论，不自动扩大渲染或轮数。人工关键点真值复核仍待完成，不报告PCK/OKS或将几何有效率当准确率。
