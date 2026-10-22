# FutsalMOT 当前任务

更新：2026-10-22

## 已完成

- 正式无号码4K批次8seed、八天气、32个相机序列，20,116 RGB及同数mask，含逐帧bbox。
- 10FPS、每机位连续414–952帧；8组保持原train归属。原16/32组目标终止，持续跟进已删除。
- 正式目录G:/FutsalMOT_Dataset/v1_no_numbers_4k平铺为groups/seed_XXXXXXXX/cameras/，去掉clips/clip_000，修正引用及文本SHA，媒体未复制或重编码。
- 生产调度器结束；Editor核对自有checkpoint后正常退出。164个无外部引用的临时Sequence通过UE API删除。
- UE AutoSave关闭，默认地图指向正式球场。G盘旧staging/work/速度试验、过时文档及UE可再生缓存已清理；关键生产来源和未完成号码开发保留。
- 基准full，其余quick/basic如实保留，不声称全部逐帧像素审计。

## 正在推进

本轮发布包括数据结构、生产优化、研究入口和文档更新，排除未完成号码实现。内层main先测试并push，再更新外层gitlink推master。独立无号码发布树1710项Python测试通过；干净UE工程构建成功，4项PNG输出自动化测试通过。

GPU实验明确检验“合成数据能否在固定真实标注和计算预算下，提高真实足球的检测与多目标追踪”。A预训练、B仅真实、C真实加合成，统一GPU和检测/追踪协议，最终test保留。

研究目录D:/projects/FutsalMOT_Research。B已完成，C用300真实＋300合成，600样本/epoch、5epochs、750次更新；保留全部旧结果，不预设收益。图像从正式G盘引用，不重复复制4K数据。

GPU执行入口为内层experiments/sim2real/run_serial_pilot.ps1的Gpu阶段；实时输出及启动凭证保存在研究目录comparison，不把启动描述为已经取得增益结论。600张C训练图像的派生标签路径已按实际Ultralytics读入规则核验。

## 后续

1. 完成同设备A/B/C检测、ByteTrack和TrackEval，报告正负变化与小样本限制。
2. 扩大比赛数、训练seed、数据规模及天气/外观消融。
3. 继续号码贴合、遮挡、RGB/mask/bbox同步验收；本次不提交号码代码或资产。
4. 有真实五人制标注后再验证目标场景收益。

入口：[README](README.md)、[Python README](Content/FutsalMOT/code/README.md)、[研究协议](Docs/RESEARCH_PROTOCOL.md)。本机证据位于Saved/Production、Saved/DatasetMaintenance和Saved/Archives，不纳入Git。
