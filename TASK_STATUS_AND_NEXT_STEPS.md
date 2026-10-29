# 当前任务与下一步

更新：2026-10-29。历史过程见Git及对应运行收据；本页不保留过期PID流水。

## 当前：4K按机位拆分与8/8写出，六机位短样和汇总导出通过

用户已要求固化并提交GitHub。已整理[单seed固化入口](Docs/production/SINGLE_SEED_BASELINE_V1.md)，启动/退出不再依赖Saved脚本，50项针对检查通过；复用a09动态证据，不重复渲染。

主相机C5最终11.7m，已去除底部白边。1/1、2/2、8/8同30帧总耗时101.187/74.609/43.219秒；采用每机位新UE进程+8/8+内存余量门禁。a09的六机位各30帧均成功并正常退出、无门禁触发，最低commit余量11.156GiB/RAM9.013GiB；统一导出180 RGB/实例mask/号码mask、1800人物、905可见号码、21600点已通过；EXR已消费清理。最新策略见[32GB主机4K方案](Docs/operations/RENDER_POLICY_4K_32GB.md)。原22:00 OOM失败保留，a04六机位10帧修复短样已导出通过且正常退出，用户后续截图未对应新崩溃包。

完整3001帧单seed尚未启动，总数据集导出继续后置。下方旧阶段数据为历史记录，不覆盖当前4K/8写出/11.7m机位配置。

用户同时授权子代理只读对照原设计，已整理[当前剩余清单](Docs/engineering/SINGLE_SEED_READINESS_AUDIT.md)。下一步先补两项实际接线：分机位容量门禁（1TiB预算/100GiB余量）和覆盖完整后处理的test生命周期；再以新attempt/源码协议完成短样门禁、完整3001帧×6机位生成、一次导出及人工验收。当前只固化已验配置与待办，不启动长样。完整预期18,006组图像/双mask、180,060人物、2,160,720个body12点；尚未生成。正式seed/split、root manifest/schema、批量调度、全局checksums/fingerprint及发布均在单seed通过后执行。

## 当前：七项实现与单seed短样通过；光照启用排查完成，完整渲染尚未开始

用户已授权按顺序补齐七项、快速轻量审核，不再每项重复验收。完整episode终止、独立协议/源码绑定、body12/相机native、字段适配、精简seed导出、新schema/文件树核对、结束收据和EXR清理已接通。root1048首次done结束，共3001帧（step0–3000、300秒），没有终止后reset；本轮选C5/C1/C2/C3/C4/P02。新body12编译和真实UE短样通过：6×10帧，60 RGB/60实例mask/60号码mask、600人物记录、261条可见号码、7200个body12点；Pose可见性仍明确unknown=0、号码可读性未人工认证。精简导出194文件/207036095字节，短样EXR已清理。小收据`Saved/SingleSeed/single_seed_s1048_a01/{source_complete.json,protocol.json,short/verification_complete.json}`；短样媒体`G:/FutsalMOT_Dataset/test/single_seed_s1048_a01_short/export/seed_00000418`。

完整MRQ提交工具被用户中断，新鲜状态确认尚未开始。用户随后要求排查天气配套光照：已确认Editor/PIE十灯均为8 EV，开/关灯同帧对照显示场地区域RGB均值20.25/8.03，灯组实际参与渲染。此前相机/号码静态预览无天气覆盖，亮度不可直接对比；未擅自修改已确认参数，亮度本身未获新验收。详见[光照排查](Docs/engineering/WEATHER_LIGHTING_SYSTEM.md)。诊断70份EXR已按清单清理；UE保持打开、clean/idle、十灯恢复5 EV、临时回调已卸载。下一步仍为完整3001帧单seed渲染/导出/验收，总导出继续后置。

### 已确认：十五套球衣全部纳入随机

用户确认新版号码后要求纳入Textures目录中的全部球衣。真实库存15套及15条配对短裤均存在，已建立`python/configs/player_appearance_catalog_15kits.json`，新catalog_id=`mpfb_players_003_009_kits15_v1`；P1/P2/配置均支持十五套，旧五套目录及冻结任务保留。新增06–15十个号码派生材质已创建保存，按实际背部底色补墨色；新预览/示例task默认使用扩展目录与已确认号码。359项针对检查通过；实际1048选中13/03/04/11四套，联合apply/restore通过，新增10套各一份RGB/整数号码mask与bbox完成，另有真实C5阵容图。媒体在`G:/FutsalMOT_Dataset/test/kit_catalog_15_a01/`，小收据在`Saved/AppearanceCatalogExpansion/a01`及`Saved/CameraRigV2/kit_catalog_15_a01`。UE保持打开、dirty=[]、原场景恢复且已确认相机不变。详见[十五套入口/兼容与证据](Docs/engineering/SEEDED_KIT_CATALOG_15.md)。扩库结果已获用户确认；该段记录扩库结束时的Editor状态，当前单seed状态以本页顶部为准。

已确认的基础配置：GreenV2 a02、统一seed入口、九机位方案和号码v2。号码旧默认仅供历史任务兼容；新入口使用已确认字体/下移位置及十五套墨色。当前不再等待此前的相机或号码外观确认，详细历史见对应技术文档和训练历史。

后续顺序如下；用户最新要求七项功能连续完成，仅做轻量审核，完整单seed完成后停下验收：

1. 已验收：弃用新生成的蓝/红棕候选，调整绿色草地深浅与纹理，固定a02参数。
2. 已确认：统一seed配置入口，球员外观、号码、草地、天气集中生成/记录；独立namespace与既有算法保留。
3. 已确认：全部9机位已同步用户手调，五个必选+随机1–2个局部；新号码外观也已确认。
4. 完成下列单seed端到端生成功能和验收。
5. 单seed通过后，才执行总数据集导出、汇总校验与发布待办。

## 已完成：号码系统固化；单seed问题清单已整理

已确认profile `back_size115_down002_v1`：原印花宽高各放大15%，中心V减0.02（源网格约下移2.25cm）；RGB与号码mask共享参数，原model/skin/kit随机系统保持启用。最终同源同机位10帧MRQ与后处理success，100人物记录、40条号码可见、769号码像素全部归属正确实例；bbox/号码validator通过。用户已人工确认，并授权本次GitHub提交。详情见[实现与证据](Docs/engineering/SEEDED_APPEARANCE_UV_NUMBERS.md)。

UE已自动恢复、clean/idle后正常退出。临时媒体仅`G:/FutsalMOT_Dataset/test`，成功保留24小时、失败诊断最长7天，每天04:00按结束/到期收据清理；EXR消费者结束后均已按精确清单删除。项目Saved只保留小配置/日志/关键收据，不入Git。

号码系统已提交并推送GitHub master：`bc387aa95ba99b335dc4b5308fbaab2b3b934451`。临时Sequence与其他研究/配置WIP保留在本机。

用户2026-10-29调整执行顺序：**先完成单seed数据集生成功能并验收通过，之后再执行总数据集导出待办。** 本阶段先整理问题，不启动正式批量生成。旧402组诊断矩阵及8seed规模仍是未冻结草案，不据此追加测试。

### 单seed阶段的目标与边界

输入一个明确root seed和该次运行参数，生成一场完整有限模拟episode；该seed的各机位共享运动轨迹、身份、appearance和号码映射。输出一个符合新契约的seed目录：

```text
seed_<8位hex>/
  seed_manifest.json
  trajectory.jsonl
  <camera_id>/
    camera.json
    annotations.jsonl
    img1/000001.png ...
    mask/000001.png ...
    number_mask/000001.png ...
```

单seed不等于单机位：可以先用一个机位接通功能，最终须覆盖该seed事前指定的全部机位。少量帧只用于联调，不能代替完整episode验收。实验身份、split等必填字段只作本次诊断标识，不因此确定正式train/dev成员；诊断数据不自动转为正式数据。

### 单seed待解决问题（执行顺序）

| 顺序 | 问题及当前缺口 | 本阶段交付/通过条件 |
| --- | --- | --- |
| 1 | 完整episode输入：已有号码联调复用1048的10步窗口；3000步只是候选，旧生产还使用活跃窗口筛选 | 写明一个seed、模拟配置、终止条件、源步数/FPS和相机列表；核对真实终止及连续step/time，不截片冒充完整episode、不补帧或拼接重置 |
| 2 | 运行参数与外观绑定：完整随机appearance和号码已接通，绿色变体仍缺视觉验收 | 首个功能基线推荐原绿色、已固化号码、原model/skin/kit随机流；记录实际采样及相机/成像参数。绿色变体另补最小边界短样后才纳入支持范围，不把变体参数回读当画面通过 |
| 3 | 同帧Pose与相机：号码短样没有闭合新body12/逐帧camera state全契约 | 复用已验native/GPU-render CPU-LBS，Pose绑定本次可见mesh；输出固定12点、像素坐标、实际相机状态，建立MRQ帧与native/source step对应；未知遮挡不伪造visible |
| 4 | 权威帧标注：现有主要是旧格式，号码仅已有新格式写入分支 | 每帧保留十人，写齐新schema的ID/team/role、mask tight bbox、号码及body12；明确截断/人体可见性、号码朝向/可读性规则，不能直接沿用默认truncated=false，也不把未审阅号码标为可读 |
| 5 | 单seed导出：旧发布结构及provenance不能原样作为新成品 | 从运行中间产物生成上面的最简目录；轨迹转换成新schema及米制三维位置/速度，静态camera内参和profile SHA齐全；seed manifest绑定身份、协议、实际代码bundle与独立运行收据摘要，不混入YOLO/MOT/debug文件 |
| 6 | 单seed验收与结束：现有号码/bbox检查不能代表新seed完整验收 | 一次必要端到端检查：schema、精确帧/文件集合、十人映射、RGB/两mask/Pose/相机同步、bbox与mask一致；多机位共享同一源轨迹且保留原始采样差异。成功后完成恢复/正常退出、EXR消费者结束后的精确清理，留下单seed结果收据 |

实现时复用现有生成器、号码、外观、相机、Pose和后处理入口，只补接线与缺项；每个新增功能做必要针对检查，不逐模型重复近景、不开展渲染性能研究。单seed实际运行的seed/episode边界、机位、帧率/尺寸及资源预算需先形成明确附件；不默认采用旧草案数值。

临时渲染及单seed诊断导出均放`G:/FutsalMOT_Dataset/test/<attempt>/`，raw在`raw/`、候选seed目录在`export/`；实际写入前按具体范围申请工具自动审批。诊断媒体按既有test生命周期清理，关键小收据留项目Saved；本阶段不写正式版本目录。

### 单seed通过后才执行的总数据集待办

- 冻结完整seed清单、正式train/dev分配、全量帧数/机位集合和容量上限。
- 多seed批量调度、失败收据汇总及正式staging组织。
- 根`dataset_manifest.json`、共享schemas封装、全局`checksums.sha256`及`root_fingerprint`。
- 全数据集文件集合、seed/split隔离、容量及完整性正式验收。
- 正式版本同卷发布、不可变归档和总Gate报告。

以上只登记为后续事项；本阶段不实现或执行。总数据集导出必须等待单seed通过收据，不以号码系统通过替代。下游YOLO/MOT适配、训练与真实数据实验继续属于后续流程。

## 前一研究阶段：弱标签/可达性/历史暴露诊断已独立核查闭合，原strongmotion_RS保持主参照

[完整证据与下一步方案](Docs/research/RECORD_REUSE_DIAGNOSIS_A01_RESULTS.md)；[冻结有界协议](Docs/research/WEAK_LABEL_REACHABILITY_REUSE_A01.md)。本轮新增优化/R-S曝光/模型前向/图像推理/追踪推进/solver/GT坐标/TrackEval/渲染均0，producer/两个worker/verifier/launcher实际全退。原116/187/test封存，无本轮研究后台。

已复用540小metric及receipt、164844事件观察/3690原UID、82422配对；原6R单元3000窗/42465候选新交叉：693无正例且资格内unknown、455窗unknown成本可行、993空有效known，均不叫错标签证明。59案例槽/47窗，缺类不补。主gap比较maskRS−原RS改善754/退化1259，其中594为不同ID、585端点缺失、80歧义；这是fold/seed重复观察，不是独立比赛或物理遮挡。旧90CI原样引用不重算，无新模型成绩。

旧6RS固定12事件/6共享源描述组，全部priorunknown；12实际写入、36未来stage读取、14潜在资格stage，11连续exitoffset3/1断链null。仅证明wrong_uid暴露，不证明实际MLP或历史/KF因果。producer/独立checker各940旧前缀/372事件帧，预览1另列，新推进0。原235/eligible0/四支0/45null不改。

完成根dfd837da、独立核查e317b171、producer d83d8701；协议09ccd3cf/最小4文件f0c32a49，独立单文件34f466c3。原a01父stub误识别0数据任务失败及所有失败/缺失保留，只改执行门禁无成功任务重放。原三组正式180无逐帧native/history/KF/assignment，候选label子类型未存，不能拿SHA/聚合计数补造。

此前R资格mask18臂18000步/378检查点/180追踪及75+15区间仍完整闭合：新RS的12比赛均值全部低于原RS；[上轮绝对结果](Docs/research/R_CANDIDATE_ELIGIBILITY_A01_RESULTS.md)。主参照与默认部署配置本轮未改。

## 下一步与尚未解决的问题

- 研究主线仍是固定检测下合成Pose相关监督对身份关联的边际作用；本轮为motion训练资格对齐验证，未证明Pose收益，也没有解决整条论文主线。
- 下一协议优先独立后验去坐标事件索引（原3690UID→两端帧号/身份），单独冻结含GT原registry的读取/隔离范围；本轮未执行。再仅按主mask_RS对原RS的12来源×四转移×每类2最多96案例（aligned-RS仅作相同案例第三方法）、两端±5×三方法最多6336已有方法帧核对，固定seed20261024/原heldoutfold或game4，不挑seed或补满。
- 若内部状态仍缺，另签必要的小被动观测与plain/observer/coldABA/spawn数值准入，再据完整证据只选一个训练因素。原RS已有日志优先引用；两新模型×6train×固定前300最多3600推进仅候选上限，准入预算另冻，当前不执行，不从无snapshot中途续跑。
- Pose算法监督如需实施，须单独约束可靠身份锚点/unknown处理和split隔离，不把自身预测ID当GT。原120样本人工Pose项目已归档，不等待该项、不报PCK/OKS。

## 固定工作边界

- 116/187/test封存；12来源均为已观察开发，原3/旧2/七场分面板，不称新盲测/官方排名/SOTA/泛化或合成等效。
- DResearch保存真实输入/最小SHA代码/模型/完整记录；G媒体只引用，Saved只放小本机收据，不复制4K/环境或重建备份，不重放旧迁移/清理/成功训练审计。
- 每阶段和失败即时更新训练历史、精确中文提交推送和汇报，无每日定时历史维护。单master、不add-A/force/跳hooks，不混Saved/模型/媒体/号码资产WIP。
- 原八组冻结数据、绿色/球衣版本及未完成号码WIP继续保留。UE保持关闭，取消的专门渲染/EXR导出加速不恢复，不结束用户应用或改pagefile。

## 历史与证据入口

旧版本启动/恢复流水由Git和对应研究文档保留，不能作为今天重复执行的指令。

- [训练历史总览](Docs/research/TRAINING_HISTORY.md)：逐轮动机/绝对参数/数据split/结果/失败与原始证据。
- [R候选资格mask完整结果](Docs/research/R_CANDIDATE_ELIGIBILITY_A01_RESULTS.md)：本轮六方法/75+15区间/全部负结果。
- [资格与弱标签诊断](Docs/research/STATE_LABEL_ALIGNMENT_A01_RESULTS.md)：零更新诊断，不是因果收益证明。
- [R集合监督结果](Docs/research/R_SET_SUPERVISION_A01_RESULTS.md)及[自由状态R来源验证](Docs/research/STATE_ALIGNED_R_TRAINING_A01_RESULTS.md)。
- [历史状态传播诊断](Docs/research/TRAIN_FREE_STATE_GAP_A02_RESULTS.md)：零eligible、四支0、45区间null，不放宽规则或重跑。
- [全过程记录](Docs/operations/TRAINING_RECORDS.md)、[性能边界](Docs/operations/TRAINING_PERFORMANCE.md)、[存储规则](Docs/operations/STORAGE_POLICY.md)与[文档索引](Docs/README.md)。
