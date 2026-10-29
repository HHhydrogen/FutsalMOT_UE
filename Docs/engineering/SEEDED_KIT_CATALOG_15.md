# 球衣随机库扩展到十五套

2026-10-29。用户确认相机和新版号码后，要求将`/Game/FutsalMOT/Characters/MPFB/Textures`下未加入随机的球衣全部纳入。真实UE盘点为Set_01–15，均已有对应球衣/短裤Texture2D和基础Material；原随机候选只有01–05。

## 当前入口与兼容

- 完整外观目录：`python/configs/player_appearance_catalog_15kits.json`，catalog_id=`mpfb_players_003_009_kits15_v1`。
- 单机位诊断task示例：`python/configs/player_appearance_15kits_smoke_10frames_1cam.json`，包含已确认号码配置与标准GreenV2；这里只做模型/配置检查，未运行该示例的MRQ，不作为完整seed任务。
- 新预览准备入口默认读取十五套目录及`number_typography_v2.json`；正式新单seed入口同样应显式绑定这两个目录和已确认camera_rig。
- 原`mpfb_players_003_009_v1`五套及旧decal v2目录保留原严格集合。既有task/冻结recipe不改，Pose研究中显式五套协议也不替换。

P1、Pydantic配置与UE adapter使用同一个`kit_ids_for_catalog`识别5/15套。模型、肤色、球衣及号码继续原seed派生与hash排名；只扩大新目录的kit候选。每seed取排名前四个互异套装，依次分给左右外场及左右门将；同队外场共用套装，球衣/短裤按同一个Set配对。新候选可能改变新目录的kit选择，其他独立随机流不变；不另造抽样器或引入颜色筛选。

## 套装与号码颜色

使用已确认的Bahnschrift Bold Condensed、Weight700/Width75，UV=[0.125,0.15,0.405,0.45]及同一新Atlas。RGB/号码mask共用几何与采样参数，墨色只影响beauty，不改变32–41实体ID。原01–05的配色保持已确认值。

| Set | 贴图主要颜色/纹理 | 号码墨色 | 背部区域平均线性亮度 |
| --- | --- | --- | ---: |
| 01 | 绿 | 白 | 0.0788 |
| 02 | 白 | 黑 | 0.8132 |
| 03 | 黑 | 白 | 0.0135 |
| 04 | 红 | 白 | 0.1192 |
| 05 | 黄 | 黑 | 0.4474 |
| 06 | 蓝色斜纹 | 白 | 0.1255 |
| 07 | 红色折线纹 | 白 | 0.1403 |
| 08 | 深色蜂窝纹 | 白 | 0.0351 |
| 09 | 紫色几何纹 | 白 | 0.0997 |
| 10 | 白色细格纹 | 黑 | 0.7790 |
| 11 | 橙色线纹 | 黑 | 0.2528 |
| 12 | 黑金斜纹 | 白 | 0.0229 |
| 13 | 青蓝流线纹 | 黑 | 0.2041 |
| 14 | 白红斜纹 | 黑 | 0.5690 |
| 15 | 深蓝橙色纹 | 白 | 0.0374 |

上述亮度由UE原生导出的真实贴图，在号码背部UV矩形[0.125,0.15,0.405,0.45]取样，sRGB转线性后按0.2126R+0.7152G+0.0722B取均值，表中保留4位小数。新增颜色以0.179为黑白选择参考并查看实际图案，结果固定在`number_typography.KIT_INK`，不在运行中随天气/曝光跳变；纹理分区仍可能局部与墨色接近，未增加新的描边shader。

## 真实UE接线与检查

1. 核对30个基础材质分别引用本Set对应Jersey/Shorts贴图，均为Material；新增短裤skeletal=true、morph=false，与该次静态应用兼容，未擅改基础材质图。
2. 仅新建06–15的十个号码派生材质，位于既有`JerseyNumbersUV_v1`目录，HLSL/接口与旧五套相同；各自从本Set基础球衣复制，保留所有外观输入，启用skeletal/morph并保存。旧五套号码材质未覆盖。
3. 一次针对检查359 passed/3.24s，覆盖P1/P2/配置一致、旧五套兼容、其他随机分配、64个visual seed使十五套全部可达。
4. 实际复用1048源step300、visual1708221217，原十人model/skin/号码不变。新目录选中左外场13、右外场03、左门将04、右门将11，真实UE联合应用成功；新增套装已进入原随机链。
5. 新增06–15各一次768×768、HFOV35°、距目标180cm的原生同帧RGB/mask近景。为比较球衣与数字，近景克隆只更换球衣，短裤沿用source的Set13；它不是虚构的新roster或整套短裤渲染验收。十份mask严格只有0与33，均有非空号码bbox。另拍一张真实随机阵容C5主视图，实际阵容中的球衣/短裤按同Set应用。

本轮无新MRQ/EXR/Pose/训练、无完整seed或总数据集发布；静态穿着及mask证据不冒充新正式数据集准入。结束已恢复原外观/号码/球/地板，临时对象销毁、dirty=[]，UE保持打开，九个已确认机位不变。

初次只读盘点把UE Array直接交给json.dumps导致TypeError，无资产写入；改为普通list后成功。之后材质创建、应用、捕获与恢复未报错，不将初次查询写成首次无错。无需重复九个模型或旧五套的近景。

## 证据及生命周期

- `Saved/AppearanceCatalogExpansion/a01/{inventory.json,texture_export.json,asset_build_intent.json,assets_complete.json,number_preview_annotations.json}`。
- `Saved/JerseyNumberUV/catalog_expanded_06_15.json`。
- `Saved/CameraRigV2/kit_catalog_15_a01/`：统一seed、真实应用及恢复、各套近景记录。
- `G:/FutsalMOT_Dataset/test/kit_catalog_15_a01/source_textures/`：实际源贴图导出及总览。
- 同attempt的`raw/`、`review/`：新增球衣穿着、RGB/号码mask与标注。成功24小时清理，关键小收据保留Saved。

当前完成球衣库扩展，按逐项要求停下供用户检查；后续才继续完整单seed收口，不执行总数据集导出。
