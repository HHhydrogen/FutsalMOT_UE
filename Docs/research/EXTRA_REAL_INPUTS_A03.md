# 额外真实监督输入阶段验收

更新：2026-10-27。对应[资源替代方案](POSE_DIAGNOSIS_AND_REAL_DATA_SUBSTITUTION_PLAN.md)阶段3A的输入准备；获取、固定感知预测、三个窗口池、九张未来曝光计划及实际进程退出已闭合。新增优化更新和实际训练曝光均为0，C训练尚未准入，不能据本阶段声称真实等效或标注成本节省。

## 来源与获取

| 新train片段 | 原比赛 | 新片段比赛时间 | 对应基础片段时间 | 首次解码帧数 |
| --- | --- | --- | --- | ---: |
| SNMOT-061 | game4 | 上半场08:10–08:40 | SNMOT-060，00:00–00:30 | 750 |
| SNMOT-098 | game6 | 上半场08:00–08:30 | SNMOT-097，05:57–06:27 | 750 |
| SNMOT-154 | game9 | 上半场22:29–22:59 | SNMOT-151，00:36–01:06 | 750 |

共2250帧，1920×1080、25FPS，官方SoccerNet train固定revision `3777f456d908570e10b19e7354744640e77c351e`。三段属于原三场比赛的不同时间，不是新增独立比赛；同场球员身份也不能称新增独立球员。实际GT/gameinfo/seqinfo齐全，未提取或使用官方det，最终116/187及test包未访问。

a01及a02在第三源网络范围读取时失败：a02的180105721字节请求实际仅返回16518914字节，随后连接重置，远端设备原因未知。旧两份失败manifest、源码和日志保留；前两段1500帧不重下、不重哈或重解码。a03独立使用顺序4MiB范围和原三次有界读取器，完成154的750帧CRC与首次解码，不增加并发或修改渲染/导出路径。它只解决本次输入获取，不声明网络故障根治。

实际新汇总位于D研究根`public/real_substitution_train_a01/manifest_recovery_a03.json`，旧`manifest.json`/`manifest_recovery_a02.json`保持失败。获取根`pose/pose_mechanism_a01/extra_R_acquisition_complete_root_a03.json`核验2259项文件stat及9个小元数据SHA，获取实际身份已退出。

## 固定预训练感知

只对这三段新图执行共享PT检测与检测框裁剪Pose；旧R/S/PT缓存完全复用。检测640、conf=.1、IoU=.7、rect=True、FP32；Pose裁剪640、batch16，原几何门槛、预取2。PT Pose SHA为`c41fee957f91da4657f5b4f8822e22d53c6c527074c102e0a8c7490cf97736ec`，检测权重及原v10数值来源另由协议绑定。

| 来源 | 帧 | 全部raw检测 | 几何有效Pose | bbox-only |
| --- | ---: | ---: | ---: | ---: |
| 061 | 750 | 12986 | 8427 | 4559 |
| 098 | 750 | 9876 | 7528 | 2348 |
| 154 | 750 | 13698 | 8272 | 5426 |
| 合计 | 2250 | 36560 | 24227 | 12333 |

这些是输出覆盖计数，不是Pose准确率。GT不进入模型帧、不筛检测，缺Pose保留bbox-only，不回填旧Pose；像素仅来自实际新JPEG。JPEG一基与缓存零基显式对应，不虚构整场绝对帧号。三源manifest为`complete3_sources2250_frames_not_training_authorized`，独立根核验实际预测进程退出。

## 额外R窗口与预算

独立`extra_real_windows.py`只通过AST替换原v8载入器的一条序列scope白名单，其余数值AST、匹配标签、候选gate、三帧历史和时间间隔不变。每fold排除heldout，仅从另外两场各取500唯一窗口，五个原gap各100，按最小UID SHA事前选取；合格不足就失败，不复制填额。

| heldout | 唯一额外R窗口 | 所用源帧引用 | 观测UID | 全部pair | 已知pair | 未知pair |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| game4 | 1000 | 1326 | 6086 | 4503 | 2931 | 1572 |
| game6 | 1000 | 1340 | 6330 | 4730 | 3046 | 1684 |
| game9 | 1000 | 1348 | 5224 | 3343 | 2525 | 818 |

每fold与基础R的窗口UID、观测UID和源帧引用交集均为0；实际比赛时间区间不重叠。GT只生成身份/框标签与teacher-forced历史成员，不读取GT Pose作特征；未知候选保留。源帧引用不是独立比赛、人物或标注工时。

三个fold合计3000个窗口条目，跨fold全局仅1500个唯一窗口、2007个所用源帧引用，因为同一训练片段会被两个允许fold复用，不能当3000个独立样本。全部2250图输入保留，窗口选择不按Pose质量、模型损失或追踪结果挑选。

九张额外R曝光计划分别对应三fold×三seed；它们只读引用原基础3000R表及原normalizer/quality_scale，另列一次1000额外R，来源始终为real。**计划不是实际训练曝光**：未来C为4000R、1000更新的独立资源问题，B为3000R+1000S；当前两种新训练均未启动，不把相同窗口数称等图像或等FLOPs。

## 完成链与论文材料

研究根：`D:/projects/FutsalMOT_Research/pose/pose_mechanism_a01/extra_R_inputs_a01`。

- 预测准入：`prediction_frozen_a03/config.json`，SHA `945c554c2b3fc75ccc7bd4ec4ade92ce590778c4ed16f7d357d66708cc001050`。
- 预测完成：`prediction_complete_root_a03.json`，三源缓存/逐源收据及原stdout/stderr保留。
- 窗口准入：`windows_frozen_a03/config.json`，SHA `abbd7471b8cb26e1d39d927165d84b0760aa42f72b2897c3ff62e0f32889da3e`。
- 窗口结果：`extra_real_windows_a03/complete.json`、三份pool、九张曝光计划、`paper_input_inventory.csv`。
- 独立阶段根：`inputs_stage_complete_root_a03.json`，SHA `e8a695fd266590dc12b029e3db109527004db39b1a6e0d11c3ba463aca4bacfa`。

必要针对检查为恢复5项、预测入口6项、窗口4项；另执行真实获取、预测及建池预飞/完整运行/独立核对，不用CPU夹具冒充实际结果。无新训练，未来C仍必须沿用[全过程记录](../operations/TRAINING_RECORDS.md)，不能补造历史缺失字段或以中间检查点挑best。

## 下一步边界

先核验更多未观察过、比赛身份不同的公开train/val足球比赛，结果前冻结可用清单、比赛级精度/非劣效容许损失和分析。现有五场已观察开发数据与上述同场新片段不当新盲测，不读test补样本量。独立比赛不足或区间精度不足时结论保持未决。

随后为C的4000R及额外来源建立独立训练schema/完整记录准入，核对B/C的初始化、基础R顺序、损失聚合和数值源码；不符合复用条件就重立公平控制，不能追加旧权重。分别报告B−A补充、C−A补充、B−C替代及Pose−强motion增量，保留全部seed和负结果。当前没有真实等效、成本节省或Pose增量的新结论。
