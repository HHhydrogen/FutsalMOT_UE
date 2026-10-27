# 常驻关联worker实际准入结果

更新：2026-10-27。[事前方案](ASSOCIATION_WORKER_ADMISSION_A01.md)固定六完整任务，实际warm A→C→A及ABBA已全部完成，实际controller/launcher/worker正常退出。正式优化更新与图像检测/Pose推理均0，测试继续封存。

| 同一六任务工作量 | 第一次 | 第二次 | 平均 |
| --- | ---: | ---: | ---: |
| 每job新进程、串行track后metric | 104.5054秒 | 103.9833秒 | 104.2444秒 |
| 2track+1metric常驻池 | 47.4161秒 | 47.6258秒 | 47.5210秒 |

ABBA均值吞吐比为**2.19365倍**，端到端耗时下降**54.4139%**。包含启动、来源验证、模型/输入准备、计算、完整MOT/日志/评价、闭包核验与正常退出，不是仅MLP前向时间。“新进程”不表示操作系统磁盘缓存已冷却；ABBA不能消除缓存、时钟和其他应用影响。

warm3任务50.2795秒只作顺序与输出门禁，不混入模式均值。总27次完整追踪、27次评价、17154个重复缓存帧处理；32个worker均有close握手、闭包证据和实际join/exit0，未重新执行513整轮或修改论文结果。

全部27任务的原ID MOT字节、逐帧计数、完整关联audit、来源/输入门禁，以及全部原始TrackEval数值/GT与预测计数、全事件gap恢复，均逐项与原513产物一致。模型/adapter/frame缓存未变，每任务轨迹和全局ID归零，没有事后重编号。bbox-only/未匹配框、合法ID0及DO_PREPROC=False保留，无GT筛预测。

track进程在原来源准入前安装Python open审计，禁止GT/gameinfo/endpoint账本访问，连为SHA全读也被禁止；实际无受保护文件打开企图。只有metric进程持有GT及原事件账本。退出复核输入/模型/执行源码SHA，缓存峰值未超限。9项CPU合同和真实A→C→A已先通过；主智能体另核27任务数值、32个退出和ABBA统计，不重跑模型或TrackEval。根闭合助手曾在核查前因str/Path入口类型失败，Saved保留该失败，修正未改benchmark输出。

1秒采样本进程树RSS峰值1.2756GiB，最低可用物理内存14.0258GiB、commit余量27.2891GiB，均超过8GiB/6GiB保留规则。系统CPU采样峰值53.6%，包含其他应用，不冒充本任务平均占用或核心profiler。此纯CPU协议CUDA禁用，自有GPU计算/VRAM分配0；没有通过占满GPU、删记录、少更新或改数值提速。

适用的同类追踪/评价优先复用2track+1metric、每进程数值线程1及有界缓存；来源/loader、输入负载或数值后端有实质变化时补必要小门禁。4+2尚未执行，新T共同状态score2也是另一个后端，须独立验证。六任务小样本不能承诺513、训练或GPU图像推理都有2.19倍；采用依据是同工作量总耗时和数值/资源门禁，不是CPU占用100%。

完整来源：

- 配置：`D:/projects/FutsalMOT_Research/performance/association_workers_frozen_a01/config.json`，SHA `c95f7b4e5a6f5e9094ffd020a26c86b31030acd81ef17df6f10955f123512809`。
- 必要两文件bundle：`D:/projects/FutsalMOT_Research/code/7c72bfaf32d3ee7a252624bd7c13d779f0894c414efc468e97882fd0844db9d2`。
- [实际报告](D:/projects/FutsalMOT_Research/performance/association_workers_a01/report.json)，SHA `8a533ffaf45fc9de35e65c37520851e51b654ded7359b1f7be32e09272833186`。
- [独立根核验](D:/projects/FutsalMOT_Research/performance/association_workers_a01/complete_root_a01.json)。逐worker日志、27份MOT/评价、5个profile_complete及硬件采样均留原处。
