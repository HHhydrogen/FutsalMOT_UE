# 可复现地板随机流

当前使用[GreenV2 a02](GREEN_FLOOR_VARIATION.md)深/标准/浅三档，选择由single_seed统一recipe驱动。旧四色地板仅保留为已发布历史数据的解释，不是新生成候选。

标准库`floor_diversity.py`的独立floor namespace与稳定hash选择算法继续复用；`grass_detail.py`提供当前绿色目录。相同seed和catalog得到相同结果，不改变Python全局RNG或运动、天气、外观、号码与机位的随机分配。每场地板固定。

统一recipe记录真实轨迹、配置、所选floor ID及参数，UE通过当前事务临时换槽，生成结束恢复；计划清单不能当作实际应用成功收据。底层历史catalog存在是为理解旧数据和共享算法，不允许以旧task绕过当前入口重新采集。

需要配对研究时必须另立明确协议，保持运动、相机、角色、天气与采样不变，同一运动的变体必须同split；普通小批seed不保证颜色数量均衡。地板变化本身不证明任何训练收益。

真实GreenV2参数与视觉确认、联合MRQ证据见[草地说明](GREEN_FLOOR_VARIATION.md)。旧中性纹理/四色材质创建与诊断历史可从[Git历史](https://github.com/HHhydrogen/FutsalMOT_UE/blob/a2f488a506266242b4e5223609774a8d6f87b56a/Docs/engineering/FLOOR_DIVERSITY.md)读取，不再维护独立创建/生产命令。
