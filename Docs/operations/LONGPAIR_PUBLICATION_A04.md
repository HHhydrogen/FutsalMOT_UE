# 四stage同卷发布候选

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

入口`publish_longpair_pilot_a04.py`默认只读规划，显式`--publish`才执行。当前工具仅通过CPU夹具，尚未执行真实发布。全部路径实际G盘；必须等q8 driver和coordinator完整结束且各自PID已退出。四个stage小`dataset.json`SHA及数量、必要variant/group元数据、原native成功释放证据都须与真实完成清单匹配。

根`G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01`下只移动以下四个目录；以下路径均相对根：

| 原目录 | 目标目录 |
| --- | --- |
| `_staging/longpair_s00001048_sport_blue_v1_a04_gpu_lbs/groups/seed_00001048/variants/sport_blue_v1` | `groups/seed_00001048/variants/sport_blue_v1` |
| `_staging/longpair_s00001048_sport_terracotta_v1_a04_gpu_lbs/groups/seed_00001048/variants/sport_terracotta_v1` | `groups/seed_00001048/variants/sport_terracotta_v1` |
| `_staging/longpair_s00001102_sport_blue_v1_a04_gpu_lbs/groups/seed_00001102/variants/sport_blue_v1` | `groups/seed_00001102/variants/sport_blue_v1` |
| `_staging/longpair_s00001102_sport_terracotta_v1_a04_gpu_lbs/groups/seed_00001102/variants/sport_terracotta_v1` | `groups/seed_00001102/variants/sport_terracotta_v1` |

目录包含RGB、mask、Pose2D、逐相机原始world、camera帧标定和variant provenance（包括既有alignment副本）；整个目录同卷rename，不复制或重新编码媒体，不读取alignment大报告。原stage小dataset/group/timeline/source_provenance及校准快照继续保留，dataset原SHA不变；旧stage的variant引用已迁移，映射由发布intent及逐项完成收据明确记录，不能继续把原stage当作完整目录。

新增目标为根`dataset.json`、`splits.json`、两个`groups/seed_*/group.json`和共享timeline/source_provenance、根`calibration/<SHA>.json`及`_publication_a04/`。同seed timeline逐字节一致才共享；共同P1/P2/校准来源一致，floor_restore来源则逐variant保留。校准小JSON先逐字节及SHA精确一致才共享七份；只复制小元数据，不复制大媒体。每相机world文件不平均、不容差去重，不改任何数值。

一次流式读取同seed/同camera蓝红棕的world、Pose2D和camera JSONL，验证各300帧、十实体身份、源帧和时间映射、17点有限世界位置及unknown。源轨迹证据来自同一冻结GRF source_input和timeline。收据报告精确相同与否、非exact点数和最大世界点差；tiny差不会被改成exact或拒绝为已知跨重放数值噪声，也不冒称像素一致/遮挡真值或正式同步验收。不扫描媒体像素或媒体SHA。

写盘顺序为发布intent → 一次metadata pair收据 → 共享小元数据 → 每项move intent/rename/complete → splits和根索引 → 最终complete收据。任何未知partial、目标已存在或失败均拒绝自动覆盖/重放。使用者须同时确认`_publication_a04/complete.json`和根索引SHA；仅看到部分根目录或根索引不是完成。

发布仍是独立位置研究候选：4800对4K RGB/mask、48000逐视角人物Pose、两个seed各300源时间样本、16相机序列。1048 train，1102 synthetic_dev；同运动的两地板同split。`not_training=true`、`training_authorized=false`、`formal_pose_release=false`、`MRQ_sync_verified=false`和unknown全部保留。发布不授权训练；UE安全退出和v4新准入仍由root单独执行。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& E:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe -X utf8 D:/projects/FutsalMOT_UEDataset/tools/pose17_ops/publish_longpair_pilot_a04.py
# 全部完成并由root确认后，一次执行：
& E:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe -X utf8 D:/projects/FutsalMOT_UEDataset/tools/pose17_ops/publish_longpair_pilot_a04.py --publish
```

4项G盘纯文本fixture测试通过，覆盖原小索引保留、目录移动、半途rename失败保留且拒绝重放、活动协调器/被改小索引拒绝、tiny世界点差异如实报告。不是实际渲染或发布通过证据。
