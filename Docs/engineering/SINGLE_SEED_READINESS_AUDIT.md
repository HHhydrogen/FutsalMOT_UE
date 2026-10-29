# 单seed生成：试样渲染前功能核对

> 最新核对（2026-10-29）：七项基础功能已接通，4K、8/8写出、按机位独立UE及六机位各30帧的渲染/导出通过，3001帧源已采集。完整比赛尚未生成；以下新增清单是当前待办，后面的实施前审计仅作历史记录。已验参数见[固化说明](../production/SINGLE_SEED_BASELINE_V1.md)。

## 当前剩余工作：完整单seed验收前

1. **补齐分机位入口的容量门禁。** `python/ue/single_seed_capture.py`有1TiB预算与100GiB余量检查，但新`single_seed_partition_capture.py`没有调用；控制器只检查内存，底层存储策略仅保底80GiB。配置值存在不等于新入口已执行。下一次完整运行前先统一接线。
2. **让临时媒体生命周期覆盖完整导出。** `render_episode.py`在单机位MRQ结束即把整个test attempt标为complete并开始24小时计时，`single_seed_export.py`后处理期间没有保持active。应在全部机位、导出验证和EXR清理闭合后才开始成功保留计时；失败保留明确诊断期限。否则长时间等待/后处理可能撞上定时清理。
3. **建立新attempt和源码绑定，再完成长样。** 本次提交整理已改变源码绑定，不能接跑旧a09或改写其收据。3001帧源可显式登记来源/SHA后复用，但公共prepare CLI尚无复用参数；默认会重新采源。现有完整入口要求同一新attempt的短样成功收据，随后运行1048的C5/C1/C2/C3/C4/P02全部3001帧。只做必要的一次流程检查，不重做整套球衣/天气/相机预览。
4. **一次完整导出与现有validator验收，交付代表帧并停下。** 预期18,006组RGB/人物mask/号码mask、180,060个人物记录、2,160,720个body12点、54,032个seed目录文件；收齐恢复、正常退出和清理收据，提供少量号码/bbox/body12叠加图供用户验收。上述数量是预期，不是已生成结果。

容量依据：旧6byte/px估算完整6机位约834.55GiB；按a09实测EXR 6,671,222,958字节与导出3,001,729,547字节线性外推约901.16GiB，尚未包含全部重复文件，且长序列压缩率会变化。每机位释放UE减少内存积累，当前实现仍在全机位消费后统一清理EXR，因此不降低整seed磁盘峰值；下一次启动前应核实接近1TiB的峰值预算和另留100GiB的余量，不能将旧估算当作峰值保证。

现有恢复边界：可跳过已有正常退出收据的机位；未闭合的机位保留现场停止，不支持机位内逐帧续跑或半导出自动续跑。没有必要因此另造完整导出器。Pose visibility继续unknown=0、号码readable未认证为false，是明确能力边界，不追加物理遮挡/OCR模块。

## 单seed通过后才执行的总数据集待办

| 顺序 | 尚未完成的交付 | 对照原设计 |
| --- | --- | --- |
| 1 | 冻结正式dataset版本、确切seed清单、train/dev分配、各seed帧数与机位、容量、短样范围及失败规则；1048诊断数据不自动进入正式dev | 第5、6、10节 |
| 2 | 根dataset manifest与共享schema封装，绑定代码/配置/协议/schema SHA、精确文件数量和容量上限 | 第3、7.2节 |
| 3 | 多seed调度和失败汇总，正式raw进入`_work/<attempt>/raw`、候选导出进入`_staging/<attempt>` | 第7.1节 |
| 4 | 从冻结manifest核唯一文件树、seed整场split隔离、各机位完整性及全局SHA；生成排序checksums和无循环root fingerprint | 第7.2、7.3节 |
| 5 | 同卷发布新版本、不可变归档、README及总Gate报告；通过后停止，不自动进入训练 | 第8、9节 |

需要统一两处旧提案：原设计第76行/契约第44行“不同seed相机集合一致”已被用户确认的“五必选＋随机1–2局部”替代，应按各seed事前清单校验6–7机位；原root schema已有`seeds[].camera_ids`可复用。另外旧root schema缺预期文件数和容量上限字段，正式封装时补齐闭合schema及validator。这些属于总数据集阶段，不扩大本轮提交或启动批量生产。

本次核对只读取设计、源码和小收据，未新增渲染、测试、媒体扫描或训练；两项运行接线缺口明确后置到下一次完整长样启动前，不将其描述为已修复。

## 历史：实施前功能审计

日期：2026-10-29。结论：**视觉方案已确认，完整单seed生成和新契约导出尚未完成；暂不提交试样MRQ。** 用户已确认十五套球衣全部纳入随机。本次核对不新增渲染、轨迹采集、训练或媒体审计；新采集代码仍为未验草稿。

## 对照依据

- 原方案：`D:/projects/FutsalMOT_SyntheticDatasetResearch/Docs/DATASET_GENERATION_FINAL_DESIGN_V1.md`第3–7节、同项目`Docs/DATASET_CONTRACT_V1.md`和`schemas/v1/`。
- 当前工程：任务状态中的单seed六项交付，以及已确认的草地、相机、号码和十五套球衣方案。
- 原方案“不同seed相机集合一致”已被后续用户要求替代：每seed固定C5/C1/C2/C3/C4，再从P01–P04选1–2个，合计6–7个；校验以本次事前选择为准。原源工程审计中的“仅P01”“号码未固化”“五套球衣”已不是当前缺口。
- 本阶段仅完成一个seed。正式全量seed/split、根dataset manifest、全局checksums/root fingerprint、正式发布继续后置。

## 已完成且可复用

| 项目 | 当前状态 |
| --- | --- |
| 十五套球衣 | P1/P2支持01–15，球衣短裤同Set；十个新增号码材质已保存。359项针对检查通过，1048实际选中13/03/04/11并完成apply/restore。 |
| 草地 | GreenV2 a02已确认：UV60、Normal Flatness 0.90、条带±18%、深/标准/浅增益0.60/1.00/1.50；新生成仅用绿色，序列内固定。 |
| 相机 | 用户手调九机位已同步`python/configs/camera_rig_v2.json`并确认，五个必选加随机1–2个局部。当前几何有静态预览；旧六机位MRQ使用手调前几何，不能替代本次动态证据。 |
| 号码 | 已确认字体、UV矩形`[0.125,0.15,0.405,0.45]`、下移位置及按球衣黑白墨色。号码值/身份/mask/bbox方法可复用；v2字体和十五套完整组合尚未跑新MRQ。 |
| 统一随机 | `seeded_episode.py`调用既有算法和独立namespace。天气、指定或随机草地等仍取决于实际profile，总开关不等于所有组件都已配置。 |
| 生成底层 | 串行MRQ、Object-ID转实例mask、线性EXR转号码ID、mask tight bbox、apply/restore及EXR精确清理已有方法，本次需整合。 |

## 试样渲染前必须补齐

| 顺序 | 缺项 | 实际源码核对 | 完成条件 |
| --- | --- | --- | --- |
| 1 | 完整episode终止接线 | 原runner在done后reset；刚加的`stop_on_done`未被`task_export.run_export`传入，配置/meta仍按预设num_steps处理。无本次完整源和终止收据。 | 首次终止即结束，记录真实终止原因/末帧done/实际帧数；step/time连续，不拼接、不补帧；达到保护上限不能称比赛完成。 |
| 2 | 单seed运行清单 | 现有预览/smoke借用旧轨迹或少量帧，无本次完整episode及全部组件、schema/代码/配置SHA绑定协议；3000帧/402组旧草案不是本次冻结值。 | 事前明确root seed、模拟时长/上限、FPS/尺寸、采样路径、产物开关、选定机位、短样区间、容量和生命周期；采源终止后绑定实际帧数再启动MRQ。 |
| 3 | body12和逐帧相机native采样 | 新`FutsalBody12MRQPass`及`body12_capture.py`仍为草稿。首次构建失败：当前AActor无`GetComponentsByClass`。render还误用`info['camera']`，实际job键为`cam_id`。 | 修正编译/接线并确认反射API；采实际MPFBVisual十二点和MRQ相机状态，绑定source/output frame与十人，完成native恢复收据。 |
| 4 | 新权威帧标注 | 旧mask后处理多处写`truncated=False`、`visibility=None`；新schema要求布尔和枚举。号码只有“输入已是新schema”时的扁平分支，readable/view仅默认false/unknown；native草稿只有world12，尚无最终像素点。 | 新记录每帧十人，写ID/team/role/号码、双mask ID、tight bbox、像素body12和实际camera_state。明确截断/出画、朝向/可读性规则；未证明的Pose遮挡保持0。 |
| 5 | 精简seed导出器 | 当前入口仍输出旧episode布局、旧camera metadata及provenance/可选MOT/YOLO；未发现新seed_manifest和米制trajectory_record生成器。 | 输出`seed_<8位hex>/`下唯一seed_manifest、共享trajectory及各选定camera的RGB/双mask/annotations/camera.json；不复制旧调试/派生标签；协议、源码、配置和收据通过SHA绑定。 |
| 6 | 新契约validator | 旧validator服务旧格式，不能覆盖新闭合schema及精简文件树；未发现新单seedvalidator。 | 从冻结清单构造唯一文件集，校验闭合schema、连续帧/时间、十人映射、图像通道/尺寸/值域、双tight bbox、号码与所属实例、Pose顺序/坐标、相机状态和全部来源绑定。 |
| 7 | 全流程调度和结束收据 | 新采集、旧后处理和预览入口尚未组成完整seed流程；native消费和EXR退休未在新入口闭合。 | 接通采源→绑定清单→序列/采样→串行MRQ→标注/导出→单seed校验→恢复/正常退出→EXR清理→验收包；失败保留原证据及明确期限。 |

以上均属于单seed阶段，不能推迟到总数据集导出。

## 需要在实现中明确的语义

- body12取可见MPFBVisual的实际骨骼原点，顺序沿用`pose_bones.py`；隐藏driver的旧BurnIn不替代此证据，不把历史17点改名为12点成品。
- 未证明的Pose遮挡是unknown；图像外/相机后方点须明确坐标有效性。号码mask非零不直接推出人可读。
- tight bbox在图像内不代表人物未截断。新truncated不能沿用旧默认false，导出器和validator须采用同一明确判定依据。
- 原seed schema只有train/dev、没有diagnostic；本次诊断标识及与正式split隔离的表达须在运行协议明确，测试产物不自动成为正式开发集。
- 测试媒体仅`G:/FutsalMOT_Dataset/test/<attempt>/`，raw/export分开；Saved只留小元数据/native/日志。成功媒体沿用24小时清理，完成收据写明人工验收有效期。

## 执行顺序与当前状态

先补输入/协议，再补采样/适配/导出/校验和调度；新增功能只做必要针对检查，复用旧方法，不逐模型补拍、不扩大为402组测试。静态功能和编译接通后才提交一次覆盖本seed全部机位的短样；通过后执行完整episode，完成后停下验收。

本轮新轨迹、MRQ提交、RGB/EXR/mask/Pose媒体、训练/推理/追踪/评价均0。此前为新增C++类在clean/idle门禁通过后正常退出UE，当前未重开；已有DLL仍在，但新增类尚未编译通过。未创建G盘attempt、未改旧数据；源码是本机未验WIP。核对及构建失败小收据：`Saved/SingleSeed/readiness_a01/`。
