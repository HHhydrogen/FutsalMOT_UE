# 真实监督资源对照：七比赛与配对区间方案

更新：2026-10-27。用户选择“暂不设界限，只报告配对差值和置信区间”，覆盖此前以非劣效准入为前置的候选方案。本轮不设δ、不执行等效/非劣效检验、不输出“可替代/效果相当”通过标志。当前完成比赛身份与分析预登记，完整验证输入正在获取；C尚未训练。

## 实际比赛范围

已从[SportsMOT官方仓库](https://github.com/MCG-NJU/SportsMOT)固定commit `b06cfb4aacb0bb16c5778ac4ddb0d70ec6835444`读取train/val各45段；90段归并为25个源视频。没有读取test清单、GT或媒体。标题已知足球源与未知运动源各取字典序首个官方片段作身份核验，9张首帧实际检查后排除两段排球，确定7个不同足球比赛。源视频ID/片段数本身不是独立比赛证明。

| 原split | 固定片段 | 实际比赛 | 首帧记分牌/时间 | 全片段帧数 |
| --- | --- | --- | --- | ---: |
| train | v_1yHWGw8DH4A_c029 | 莱比锡–拜仁，2017 | 31:47，2:1 | 725 |
| train | v_HdiyOtliFiw_c003 | 沃特福德–狼队，2018/19足总杯 | 76:19，0:2 | 775 |
| val | v_ITo3sCnpw_k_c007 | 热刺–阿森纳，2017-04-30 | 79:24，2:0 | 701 |
| val | v_dw7LOz17Omg_c053 | 拜仁–多特蒙德，德国杯，日期未核实 | 90:00+1:07，0:0 | 550 |
| train | v_gQNyhv8y0QY_c003 | 洪都拉斯–摩洛哥，2012奥运会 | 65:01，2:1 | 700 |
| val | v_i2_L4qquVg0_c006 | 利物浦–曼联，2015-03-22 | 83:03，1:2 | 888 |
| train | v_iIxMOsCGH58_c013 | 布莱顿–曼联，2020-06-30 | 49:31，0:3 | 451 |

共4790帧，25FPS、1280×720。比赛选择先于任何新模型评价；首帧球队/记分牌/场地与标题相互核验，已对照原三场匿名Swiss场景及已观察多特–沙尔克/诺维奇–伊普斯维奇。拜仁–多特的日期未知原样保留，不能猜成具体某届决赛。两段排球为`0kUtTtmLaJA`与`CW0mQbgYIF4`，未混入足球验证。

原train归属不改名为官方val，仅在本实验标记`external_validation_only`，不用于关联训练或标准化。每场仅一个短片段、来源便利抽样，不能称整场覆盖、随机总体样本、最终盲测或真实五人制泛化。旧五场完整保留为已观察开发参照，不并入新七场主汇总。最终116/187与test包封存。

## 比较与区间

主架构为强motion，gated为事前登记次架构；三fold×三seed均保留。A为基础3000R，B为3000R+1000平衡S，C为3000基础R+1000额外R，总4000R；各臂1000更新、FP32、同初始化/基础R表与标准化、预取2、last而非best。B/C额外组均按`mean(base3R)+mean(extra1)/3`聚合；pair/计算另记，不称等图像/等FLOPs。

分别报告B−A、C−A、B−C，每场先平均9个匹配fold/seed差值，然后七场等权。AssA为主指标，HOTA/IDF1/DetA/MOTA及同组gated−motion为次要描述；全部逐场、逐seed/fold和负结果保留。

- 主区间：七个比赛差值的双侧95%Student t区间，df=6；条件为固定训练模型面板，需说明比赛差值近似独立/正态假设。
- 敏感度：比赛层级百分位bootstrap，固定10000次、seed20261027，及逐场留一均值；不挑更有利的区间。
- 不把9个训练重复当9场比赛，不从帧/窗口增大n；不将区间覆盖0解释为等效。区间未校正多重比较，不用于挑优或事后宣称显著。

区间原理依[美国NIST均值区间公式](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm)。新C尚无结果，旧B−A的比赛波动不是未来B−C方差；只做敏感度：假设比赛差值SD为0.5/1/2点，七场95%t区间半宽约0.4624/0.9248/1.8497点。该表不是预计收益、功效保证或新性能结论。小样本和便利选片的限制必须与区间同时报告。

## 数据获取与失败记录

公开传输镜像固定`Lekim89/sportsmot` revision `2993b47d4369fa70ea70afc8bc63b5964e556a81`；官方只核验split名字，没有官方像素SHA。首帧获取a01在完成一源后遇到TLS `URLError(FileNotFoundError)`，原目录/失败收据保留。独立a02明确继承成功首帧，按已有有界网络重试完成其余八源，不覆盖旧partial、不关闭TLS验证。

完整验证输入已独立冻结并通过实际只读预飞，唯一后台获取七场4790帧：复用七张首帧、新取4783张并首次解码，GT只用于评价，不筛预测。权威`D:/projects/FutsalMOT_Research/public/substitution_validation_a01/state.json`，完整manifest与实际进程退出前不能进入新共享预测。失败保留，不隐式重下成功内容。

随后a01实际在第414帧遇到JPEG解码截断并退出，419条已记账记录及17个解码后写入、尚未进入journal的文件全部保留。精确重取同URL的414帧时，237702字节、Content-Length一致且EOI完整，解码通过；支持瞬态输入传输问题，原坏响应未落盘，不能逐字节归因上游设备。没有开启坏图容忍或跳帧。

新a02显式继承437张成功图（419条原账本、17份首次补持久SHA、1张独立诊断成功的414图），只补4353张；不重哈已记账图或重复解码成功图。当前唯一权威改为`public/substitution_validation_a02/state.json`及新manifest，准入SHA `9f8c08b21b2dffd3728f644e7045e36d3abe7b62689d1f30f61b5dbc5da9b2c7`，bundle `code/fcead3726da4a40f149489cbda7c0d8742e405af3c1daeabf1eabcbca77a11e7`。JPEG校验纳入有界重试，失败原样保留，不改变七比赛/4790帧或分析。输入路径通过明确ledger引用旧成功目录/身份首帧/诊断414，不复制掩盖历史，不建别名。

研究根`D:/projects/FutsalMOT_Research/pose/real_substitution_a01`：

- `validation_frozen_a01/matches.json`，SHA `6ee812ba192f8ccc00818da31e9b8e88f7cd0e603a58e4af7c27b6256a5277c8`。
- `analysis_frozen_a01/plan.json`，SHA `afee40ca64dc44a12b5b4c684b313d02831ad0bdcbd5d5201c4f824ffabefc0c`。
- `precision_a01/report.json`，只读旧结果与假设方差的CPU精度报告，优化更新0。
- `validation_input_frozen_a01/config.json`，SHA `7e78354eae2249930466f291b12ba94cf19a6ccedbf795ab9c0b03431e5bb7f6`。

## C的完整记录准备及下一步

`training_journal.py`增加独立`full_training_record_spec_v2_real_groups`，每步显式记录3基础R/1额外R、总4R/0S，两类真实loss和pair。检查点采用`full_training_checkpoint_v2_real_groups`，不借v10身份；0/每50/1000保存模型、优化器、完整RNG/曝光链。原v1三R/一S路径保留，旧D执行bundle字节未改。

现仅5项CPU记账契约通过，尚未完成新C的实际GPU数值对照、独立加载器、18臂控制器或1000步记录门禁，不能把候选当训练完成。额外R应按原`real`处理/增强，缓存可合并基础和额外R的不同UID，不能传入`synthetic`伪装来源。基础normalizer和quality_scale只读复用，不从额外R或新验证比赛拟合。

后续顺序为完整验证输入验收→相同PT感知共享预测→新C协议/真实单步数值与记录核验→18个C新模型（18000更新、54000基础R+18000额外R、S0）→完整A/B/C及PT自由追踪→预算核对/配对区间报告。A/B只有数值源码、初始化、输入/顺序与预算完全一致才引用；历史A缺失LR/梯度/RNG字段继续标缺失，不补造。若复用条件不成立，先重立公平控制，不追加旧权重。所有阶段向用户汇报，正常等待静默。
