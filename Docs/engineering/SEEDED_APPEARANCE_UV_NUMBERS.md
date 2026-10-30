# 完整随机外观下的球衣号码与同步标注

当前使用用户已确认的号码v2与十五套球衣，唯一生成入口为[single_seed](../production/SINGLE_SEED_BASELINE_V1.md)。不再提供旧UV矩形、五套球衣task或单机位smoke的独立调用说明；旧数据与已冻结收据保持原值。

## 固定参数

| 参数 | 当前值 |
| --- | --- |
| 配置 | `python/configs/number_typography_v2.json` |
| print_profile | back_din_tall_down002_v2 |
| 字体 | Bahnschrift Bold Condensed；Weight=700、Width=75 |
| UV矩形 | [0.125,0.15,0.405,0.45]；宽0.28、高0.30、中心[0.265,0.30] |
| Atlas | 16×8格、4096×2048；格256px、padding24px、字体241px；号码1–99 |
| 图集资产 | `/Game/FutsalMOT/Characters/MPFB/Materials/JerseyNumbersUV_v2/T_NumberAtlas_BahnschriftBoldCondensed_v2` |
| 黑字套装 | 02、05、10、11、13、14 |
| 白字套装 | 01、03、04、06、07、08、09、12、15 |
| 号码mask | 0背景，32–41对应十名球员；墨色不影响实体ID |

字体仅由本机字体文件生成图集，不分发TTF。原球衣BaseColor末端混入号码，其余贴图/法线/粗糙度保留；RGB与号码代理共用图集、UV、号码分配和动画。尺寸/位置由UV参数确定，不把UV比例当作所有机位固定像素字号。

## 统一每场seed配置入口（2026-10-29）

`single_seed_task.py prepare/freeze`从当前配置生成统一recipe，调用原算法和独立namespace，不另造随机器：

| 组件 | 行为 |
| --- | --- |
| 运动 | 原root/GRF/Python/NumPy子seed，完整episode首次done停止 |
| 外观 | 原appearance v1分配模型、肤色与十五套球衣/短裤 |
| 号码 | 独立jersey_number随机流；同seed十人身份与号码固定 |
| 天气 | weather_visual_v2八档，原独立选择算法 |
| 地板 | GreenV2深/标准/浅三档，原floor独立namespace，序列内固定 |
| 相机 | C5/C1/C2/C3/C4加P01–P04中的1–2个，事前写入同一recipe |

中间`provenance/seeded_episode.json`绑定选择结果与输入指纹；appearance/environment/number_uv/floor清单供当前事务内部消费，不是备用公开生成接口。P2先验证来源，再应用各事务，完成后恢复；不能跳过当前single_seed协议手工提交旧resolved task。

## 输出与证据

当前导出为同步RGB、人物mask、号码mask及逐帧数字身份/可见性/bbox。号码非零像素必须属于对应人物，错属阈值0；可读性未人工认证仍为false，完整规则见[数据契约](DATA_CONTRACT.md)。

用户已验收字体、下移位置、黑白配色及十五套扩库。a09六机位各30帧真实动态导出已通过：180组图像/双mask、905条可见号码、恢复与正常退出闭合。完整3001帧尚未运行，不重复全套静态预览来代替整场验收。

静态预览和失败恢复的小收据保留于`Saved/JerseyNumberUV`、`Saved/AppearanceCatalogExpansion`、`Saved/SeededEpisode`、`Saved/CameraRigV2`；a09在`Saved/SingleSeed/single_seed_s1048_4k_a09`。临时媒体仅G盘test并按生命周期清理。完整历史含旧参数与负结果见[清理前实现记录](https://github.com/HHhydrogen/FutsalMOT_UE/blob/a2f488a506266242b4e5223609774a8d6f87b56a/Docs/engineering/SEEDED_APPEARANCE_UV_NUMBERS.md)及[训练/诊断历史](../research/TRAINING_HISTORY.md)。
