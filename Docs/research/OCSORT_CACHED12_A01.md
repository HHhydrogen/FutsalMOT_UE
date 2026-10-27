# 官方OC-SORT同缓存12开发片段对照

更新：2026-10-27。用户明确授权先冻结版本、参数与输入适配并完成准入，再执行现有12场开发片段。主智能体负责协议、论文口径和唯一执行；实现、数值合同及独立核查由子智能体分担。最终SNMOT116/187与test包始终封存，不获取新媒体、重推检测/Pose或训练。

## 回答的问题与范围

当前学习关联器与成熟纯运动追踪方法，在完全相同检测输入下有多大差异？这不是官方排行榜复现，也不直接回答换检测器、RGB外观模型或扩大训练的收益。内部“强motion”只是已完成研究的参照名，不预设它比官方OC-SORT强或弱。

只复用已完成有界变化513协议的12源、8165帧及两份结果前固定的3690可信检测断档事件。原三场留一、旧两场外部、已观察七场分别汇总；均属已观察开发，不能称新盲测。每个片段只产生一次正式OC结果，不制造训练fold/seed。准入的两个48帧前缀会按事前矩阵重复消费，明确另计，不当新样本、正式追踪或吞吐ABBA。

## 官方版本与参数

固定[官方仓库](https://github.com/noahcao/OC_SORT)提交[8462e7e729a93ccd3bd995c0a79a890336cb3a0b](https://github.com/noahcao/OC_SORT/tree/8462e7e729a93ccd3bd995c0a79a890336cb3a0b)，取官方三个算法文件的原字节及README、许可证、参数/使用说明。该仓库已于2026年重构，不能称CVPR2023原字节或历史论文成绩复现。引用位于实际DResearch/references/ocsort_official/<commit>；没有嵌套Git、环境复制或权重下载。

| 参数 | 冻结值 | 来源 |
| --- | --- | --- |
| det_thresh | 0.6 | 官方CLI track_thresh默认，构造器此参数必填 |
| max_age / min_hits | 30 / 3 | 官方构造默认 |
| iou_threshold / delta_t | 0.3 / 3 | 官方构造默认 |
| asso_func / inertia | iou / 0.2 | 官方构造默认 |
| use_byte | false | 官方默认，不按结果开启低分第二关联 |

保持上游内部严格阈值比较，包括score等于0.6的边界，不在适配层修正。保留core全部自然输出，不附加demo的面积/长宽比过滤；因此明确是官方固定版本core对照，不是完整benchmark/demo管线。

固定实际依赖NumPy2.2.6、SciPy1.15.3、lap0.5.13、FilterPy1.4.5。仅缺失的FilterPy实际添加到DResearch/runtime_dependencies，未改P1或升级原研究环境；源码、许可证和实际lap二进制另绑SHA。使用原生lap.lapjv，不静默回退SciPy。缓存适配输入为float32，原Kalman内部float64矩阵和运算不改，不能称整算法FP32。

## 输入和输出合同

- 原bbox xywh转新建NumPy N×5 `[x1,y1,x2,y2,score]`，原顺序不变；不传第六列class、不读Pose或GT作输入、不筛bbox-only。官方阈值属于其内部算法。
- img_info与img_size都设为该帧实际(H,W)，scale恰为1，不缩放或重解码图像。每帧含空检测均调用update，空数组为(0,5)，不用会提前返回的None。
- 原图一基帧号、缓存零基index及timestamp=index/25逐值验证。所有序列/game保持原名，帧范围和尺寸不改。
- 每job新建OCSort、全局ID归零，一进程不交错两活动tracker。保留官方输出ID；该core已输出id+1，不再次加一或事后重编号。
- 原core输出只有bbox与ID，无confidence。MOT score按事前合同写常数1，明确不是检测置信度；全部原生输出保留，异常非有限值报错，不能静默删行。
- 原预测JSON可含Pose字段，解析不等使用；送core前只重建尺寸、时序、bbox/score白名单。track进程禁止打开GT/gameinfo/完整endpoint账本；metric进程才读原GT，SportsMOT ID0合法、DO_PREPROC=False、全部未匹配预测保留。

## 准入与执行阶段

1. 针对合同检查官方源码SHA/签名、严格阈值/空帧、尺度1、原ID、全部输出、依赖拒绝和完整分析矩阵。
2. 实际固定SNMOT-060与Dortmund-Schalke各前48帧，用独立literal原生逐帧调用对照适配层的原ID MOT、逐帧native outputs和frame counts；另验空帧、交叉、缺失、阈值边界及lap歧义。保留原Kalman64位状态。
3. 实际常驻A→B→A与两个独立spawn的A，对照冷结果、原缓存未改、GT Python-open保护及真实close/join/exit。保护自检的故意拒绝单列，不冒称追踪器打开GT。准入不重跑TrackEval，不输出速度倍数。
4. 通过后以两个track、一个metric独立常驻进程执行。先SNMOT-060与Dortmund-Schalke两场完整追踪/评价，只以输入身份、GT/预测计数、ID0与评价口径作门禁，不以成绩决定继续；其两份成功正式结果直接保留，继续其余10场，不重跑。
5. 每worker数值线程1；每track worker的预测缓存至多两序列/128MiB，metric只允许缓存这12源GT和两份登记账本。预留可用RAM8GiB/commit6GiB，压力时暂停新派发，持续不足保留partial。不结束用户应用、不改pagefile、不为填满GPU而运行无关计算。记录完整起止、任务/帧吞吐、启动/计算/评价、采样进程树RSS/系统CPU/RAM/commit。该CPU算法不使用GPU，不借用旧2.19倍作为本轮速度证明。
6. 12正式结果、原始TrackEval/gap、所有日志和真实父子进程退出后再独立终验、报告及精确中文提交推送。失败保留partial和全部成功清单，先根因诊断；必要恢复另立attempt与继承，不热改冻结源码或隐式重放。

## 配对比较和论文口径

主参照strong_motion_RS，次参照T_RS开启Pose，PT_bbox提供上下文。旧已验结果只读复用，不重训、重推或重算评价。12个PT、90个强motion和90个T_RS共192原参照单元；每场先平均对应3或9个训练单元，然后OC每场唯一结果与之配对，共36个比赛比较。不能把OC复制为九个独立重复。

差值统一为OC−参照。AssA主，HOTA/IDF1/DetA/MOTA次；3/2/7面板比赛等权，95%t、10000次固定seed20261027比赛bootstrap及逐场留一敏感度，45个指标描述区间。gap另报36配对及9描述，不与指标混合，不称物理遮挡。原分母全留，零分母null，全部负结果/未知/未匹配保留。小样本、便利片段、固定训练面板及未经多重比较校正限制同时披露；不设等效/非劣效界限，不因CI跨0称相同，不合并12场寻找更有利结论。

若OC更好，只能先说明该固定配置下成熟运动追踪存在能力差距，不能直接归因某个组件或Pose无用。若学习关联器更好，也不等官方SOTA或合成增量；合成收益仍须R/RS匹配控制。后续单因素和新的确认比赛另立协议，测试继续封存。

本页为结果前协议。当前仍待实际准入和12场执行，实际状态以TASK及Saved/ProjectStatus与新控制器state为准。
