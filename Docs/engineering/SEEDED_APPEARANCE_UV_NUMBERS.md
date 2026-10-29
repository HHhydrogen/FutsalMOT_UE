# 完整随机外观下的 UV 球衣号码与数字标注

2026-10-29。旧版`back_size115_down002_v1`已验收并提交，保留历史。用户现已确认下列v2字体/尺寸/下移及配色；新生成入口显式加载`number_typography_v2.json`，旧配置省略字段时的历史默认不改。随后已按用户要求扩充[十五套球衣目录](SEEDED_KIT_CATALOG_15.md)，新增06–15也使用已确认号码及对应墨色；未发布正式新数据。

## 最新号码候选：窄高粗体、下移和对比墨色

入口`python/configs/number_typography_v2.json`，作为新task的`ue.uv_numbering`使用。完整随机外观仍由原appearance v1决定；号码随机分配、十人身份及32–41 mask ID不变。新图集只由显式`atlas_id`启用，未配置的新旧task继续原Atlas及原计划字节；旧输出不回填新参数。

| 参数 | 当前候选绝对值 |
| --- | --- |
| print_profile | back_din_tall_down002_v2 |
| 字体 | Bahnschrift Bold Condensed；本机bahnschrift.ttf，Weight=700、Width=75 |
| UV矩形 | [0.125,0.15,0.405,0.45]；宽0.28、高0.30、中心[0.265,0.30] |
| 尺寸/位置 | 相比v1矩形宽增加15.94%、高增加30.43%；相对此前v2候选中心V=0.32再减0.02，源网格约下移2.25cm |
| Atlas | 16×8格，4096×2048；格256px、padding24px、最终字体241px；1–99 |
| 资源 | /Game/FutsalMOT/Characters/MPFB/Materials/JerseyNumbersUV_v2/T_NumberAtlas_BahnschriftBoldCondensed_v2 |
| 墨色规则 | kit_contrast_v2：Set_02白/Set_05黄使用[0,0,0]；Set_01绿/Set_03黑/Set_04红使用[1,1,1] |

字体为[微软Bahnschrift](https://learn.microsoft.com/en-us/typography/font-list/bahnschrift)的粗体窄体轴实例；TTF文件仅本机读取，不分发。字体SHA及可变轴写入图集记录，新图集PNG SHA为`47b0de2ac7d4bb6c607225c508ab792ba090d6bfee2615854fac144d26046f19`。颜色只修改NumberInkColor，不重新选择球衣。RGB与蒙皮号码代理使用同一Atlas/UV/号码参数，墨色不改变号码mask ID。

原图近景中92由旧Arial版150×103px变为新版157×164px。相比下移前新版[304,291,463,456]，当前位置bbox=[305,307,462,471]；栅格化和背部曲面可使宽高变化1–2px，不将UV比例冒充每张图固定像素比例。

实际预览复用1048源step300、visual1708221217及原完整随机model/skin/kit。先对92/89/7分别捕获旧Arial与新字体同姿态近景，再依最新要求下移并用同一个随机L1角色的临时克隆展示五套实际球衣材质。五套配色是显式诊断覆盖，不是伪造同一seed抽中了全部球衣；实际roster未改。每次原生RGB/mask配对内部游戏帧及骨骼版本不变；768×768、HFOV35°、距目标180cm。有效mask严格只有0及33/39/41对应ID，最终五套mask与5条预览bbox均已生成。

本轮首次直接检查33 passed/0.67s；新增下移/墨色后仅检查改动计划1 passed/0.17s。发生并保留的负结果：首次L1的两个mask仍是彩色输出，被拒绝且仅补拍L1成功；一次恢复调用漏了独立MCP上下文的import，NameError后只补import恢复成功，未重拍。白套装首张Beauty为灰格，原mask虽合法也不用于最终配色图；读取白父材质skeletal/morph=true和统计231条像素指令后仅补拍白套装成功。辅助预览入口现复用已验get_statistics等待材质编译；首次就绪的具体底层原因未宣称根治。

原生近景调用共14次RGB/mask配对（其中上述3组不作最终有效配对）及2张已确认机位静态图；无新MRQ、EXR、正式Pose或完整episode。各事务最后已恢复外观/号码/球/地板，克隆和临时捕获对象销毁，dirty=[]，UE保持打开，已确认相机不变。正式新字体的MRQ连通检查在外观确认后进行，旧字体10帧成功不替代此项。

当前验收图与小证据：

- `G:/FutsalMOT_Dataset/test/number_typography_color_down_a03/review_final/number_colors_and_lower_position.png`：使用已成功白套装补拍的最终五色/下移图；早期review含灰格，仅诊断。
- 同目录`white_jersey_black_number_bbox.png`与`number_color_position_annotations.json`：白衣黑字框及5条实际预览标注。
- `Saved/JerseyNumberUV/number_typography_v2_a01/{atlas.json,import_complete.json,first_l1_mask_rejected.json,preview_number_annotations.json}`。
- `Saved/CameraRigV2/number_typography_v2_a01`、`number_typography_v2_l1_a02`、`number_typography_color_down_a03`、`number_typography_white_a04`：各次真实清单、近景和恢复收据。

媒体仅G盘test，成功按24小时规则清理；原始小收据保留Saved。旧默认矩形、旧Atlas、已冻结数据及旧墨色逻辑均保留。

## 使用入口

### 统一每场seed配置入口（2026-10-29）

第1项GreenV2 a02已获用户确认。第2项在既有task的`ue`块增加显式开关：

```json
"seeded_episode": {"enabled": true}
```

完整appearance目录、`uv_numbering`及`environment`继续使用原配置；无需重新填写另一套目录或子seed。P1 resolver按原规则解析天气seed/preset，`task export`随后调用共享`grf_ue_bridge.seeded_episode.prepare_episode_recipe`统一生成并绑定：

| 清单部分 | 现有算法及行为 |
| --- | --- |
| randomness | 原meta中的root/GRF/Python/NumPy/ue_visual子seed；不重新派生或重设全局随机状态 |
| appearance | 原`build_appearance_manifest`；模型、肤色、球衣/短裤排名不变 |
| numbers | 原UV `build_plan`及号码namespace；已固化印花大小/位置不变 |
| weather | 原`build_environment_manifest`；自动preset及显式environment_seed覆盖规则不变 |
| floor | 第1项已确认的GreenV2三档，复用floor独立namespace，每场固定，不选择蓝/红棕 |

统一清单位于运行中间目录`provenance/seeded_episode.json`，记录选中结果和输入指纹。旧消费者所需`appearance.json`、`environment.json`、`number_uv.json`仍保留，增加`floor.json`；加载时逐项核对它们与统一清单及当前输入一致。它们属于当前运行中间协议，后续单seed正式导出再按新schema合并，当前未启动总数据集导出。

已有轨迹可用以下入口准备清单，不重跑GRF：

```powershell
python/.venv/Scripts/python.exe python/tools/prepare_seeded_episode.py --resolved-task <resolved.json绝对路径>
```

未配置或未启用`seeded_episode`的旧task继续原路径，不增加统一清单、不改旧选择结果。可显式设`floor_enabled=false`做单因素诊断；配对检查可用`floor_id`指定三档之一，其余配置与结果保持独立。号码纯契约和plan提取到共享src模块，原UE导入路径保留兼容入口，没有另造号码算法。

P2 `run_task`在修改场景前验证统一清单；地板、天气、原appearance及UV号码复用现有事务组合。成功或失败均按号码/外观→地板→天气恢复；P1后处理要求地板清单匹配且恢复收据结束。新地板仅调整材质槽，不保存地图或修改历史材质。用户已确认本项并要求开始第3项，[随机局部相机与五个固定机位](SEEDED_CAMERA_RIG_V2.md)现已接入此统一清单，等待机位验收。

验证：统一入口、号码旧协议、旧导出和共同回调的针对检查通过；实际1048复用既有10步小轨迹，仅做一次UE联合apply，选中`overcast_soft_v1`及`grass_dark_v2`，十人模型/肤色/kit/号码与固化版实体分配完全相同（18/92/86/96/99/55/21/89/63/7）。首次检查脚本错误传入自定义restore状态，实际API拒绝；随后仅按原快照用`no_render`恢复，未再次apply或启动MRQ。外观/天气/地板恢复读回通过，dirty/PIE/MRQ为空后正常退出。失败及恢复分别留档，不把首次检查写成一次干净成功。

小收据：`Saved/SeededEpisode/seeded_episode_s1048_apply_a01/preparation_receipt.json`、`application_check.json`及`invalid_restore_status_failure/`；实际日志`Saved/Pose17Development/editor_seeded_episode_apply_a01.log`。本项新渲染、训练、模型推理和评价均0。完整单seed生成与总数据集发布仍未执行。

### 原UV号码直接入口

保留现有 `ue.appearance` v1 完整目录与seed算法，在同一个task的 `ue` 块增加：

```json
"uv_numbering": {
  "enabled": true,
  "uv_rect": [0.14425, 0.205, 0.38575, 0.435],
  "flip_u": true,
  "flip_v": true
}
```

原模型、肤色、球衣/短裤分配继续由原manifest决定。UV号码通过独立的既有jersey_number命名空间派生；不会把所有球衣替换成Set_01。五套新派生材质位于 `/Game/FutsalMOT/Characters/MPFB/Materials/JerseyNumbersUV_v1`，各自复制对应原球衣图，只在BaseColor末端混入号码，其余输入保留。

用户人工查看标注图后要求数字稍大：默认印花矩形宽高各增大15%，从`[0.16,0.24,0.37,0.44]`改为`[0.14425,0.225,0.38575,0.455]`，UV中心仍为`[0.265,0.34]`。RGB与号码mask共享该矩形；旧配置和已生成输出保持原数值。

随后用户明确确认15%尺寸，要求位置稍下移。当前默认profile固定为`back_size115_down002_v1`，矩形为`[0.14425,0.205,0.38575,0.435]`：宽0.2415、高0.23均不变，中心从[0.265,0.34]变为[0.265,0.32]。源球衣背片520个UV/位置样本给出UE V对Z约+1.12684m/UV，故V减0.02对应向下约2.25cm；这是源网格近似，不冒充动画每帧统一物理距离。共享参数登记在`jersey_number_uv_contract.py`，RGB与mask使用同一矩形。

下移版`number_uv_size115_down_s1048_a01`同源同机位一次10帧MRQ及后处理成功；100人物记录、40条号码可见、769号码像素全部归属正确实例，号码validator通过。89帧4 bbox由[645,161,655,169]变为[645,163,655,170]；92帧10由[676,149,685,156]变为[676,151,685,157]，图像中均体现向下微移。原始栅格化使可见tight bbox尺寸有1px变化，不代表UV缩放改变。对比图在该test attempt的`review_number_annotations/number_position_before_after.png`。自动外观恢复和正常quit完成，10份临时EXR共104,725,083字节在全部消费完成后精确删除，PNG/标注按24小时规则保留。

尺寸版`number_uv_size115_s1048_a01`已用同源1048的[0,10)、同CineCam_01、相同随机模型/肤色/kit完成一次10帧渲染；MRQ一个job与两路输出记录均success，号码与外观自动恢复。P1生成10RGB/10实例mask/10号码mask、100人物记录，其中41条号码可见、825号码像素，全部归属对应实例；bbox/号码validator通过。原图离散像素框不保证每边恰好增15%：89在帧4从8×6变为10×8，92在帧10从9×6变为9×7。前后对比与新验收图保存在该test attempt的`review_number_annotations/`。这是用户明确要求的尺寸修订，未继续原初样失败后的自动探索；原版记录保留。UE已正常退出，全部EXR消费者结束后按清单退休临时EXR，PNG/标注按24小时test规则清理。

印花颜色固定由kit决定：白球衣Set_02用黑色，其余四套用白色。此规则只改变号码Ink，不改变随机kit排名。当前真实1048短样未抽中Set_02，黑色分支只做参数检查，不声称已渲染覆盖。

`run_task.py`在原外观apply后调用`episode_number_uv.py`，逐人绑定当前mesh对应的号码材质和同网格蒙皮follower；先恢复号码，再恢复原外观。原decal v2路径继续保持原状态，不借旧decal收据证明新UV事务。

UV模式要求实例来源为Object-ID：RGB、Object-ID与额外NumberMask在同一个MRQ job输出，避免分开job的动画采样偏差。`MoviePipelinePostProcessPass`在UE5.8是结构体，挂到DeferredPass的`additional_post_process_materials`，不是MoviePipelineSetting类。

## 数字数据

P1从同帧multilayer EXR的`FinalImageNumberMask.R/G/B`生成单通道uint8 `number_mask/000001.png`。0是背景，32–41是十人的号码像素身份；号码值仍是1–99，二者不同。拒绝使用经过sRGB编码和8bit抖动的预览PNG直接作为ID。

三个线性通道必须一致且有限；乘255后与最近整数的误差不超过1/16 ID（覆盖此值域HALF量化），且只接受0、32–41，不把混合像素任意吸附到合法ID。可见数字bbox由最终mask计算为像素半开XYXY；不可见时保留号码值，bbox=null、像素数0。

既有task数据写原嵌套`jersey_number.value/bbox_xyxy/visible_pixel_count`；若输入帧已经是新`futsalmot_frame_annotation` schema，则写扁平`jersey_number`整数、`number_mask_id`、`jersey_number_visible`及`jersey_number_bbox_xyxy`。新完整数据集的body12、逐帧相机状态和seed/root manifest适配仍按独立设计推进，当前旧task短样不冒充完整新schema成品。

P1后处理在UV启用时校验原appearance输入绑定、读取`provenance/number_uv.json`并导出号码mask；现有号码validator已支持这种v1外观+UV清单组合。下游OCR号码字符串、MOT/YOLO等按权威标注派生，不增加第二份权威号码表。

## 本轮真实结果与失败

沿用root seed1048、ue_visual_seed1708221217的原随机外观，取源[0,10)，CineCam_01，1920×1080、10FPS，原绿色。十人实际模型为7/5/8/4/4/8/4/8/6/3，肤色为07/02/07/04/05/05/06/05/06/08；四类kit仍为左外场03、右外场04、左门将05、右门将01。号码依次18/92/86/96/99/55/21/89/63/7。

产出10 RGB、10实例mask、10单通道号码mask、100条人物号码记录；39条具有可见号码像素。10帧共599个号码像素，全部落在对应球员实例mask内；数字bbox与像素一致，现有号码validator通过。实际看过首帧，随机黑/红球衣、门将服装及背部白号码共同存在。该短样覆盖实际抽中的组合，不声称所有9肤色×7模型×5kit组合均经过渲染。

初样a01号码job在配置阶段失败：旧代码错误地把PostProcessPass作为Setting类。a02首次apply在渲染前遇到已销毁follower的UObject名称仍占用，已改为检查活动代理并为新组件分配唯一名称，正常退出UE后用UE5.8编译成功；新DLL SHA为`5a7eda00c3cfc89d713b7a941114845b4098e994e0a898bd6ba32c1e94add4b6`。

a02真实MRQ一个job完成10帧，归档器没有识别自动追加的相机名，原始render_summary保持failed并保留。修正后直接消费已有EXR/PNG完成后处理，没有第三次渲染。另修复失败报告中camera.schedule_error含本机路径导致恢复报告无法序列化的问题。两轮外观均按首次快照恢复，最终dirty为空、PIE/MRQ退出、UE正常关闭。

本轮未训练、未运行模型评价、未读封存测试、未修改旧冻结数据。整体新数据集仍未准入；新collector的代码修正已对已有帧发现结果核对，不把这次后处理修复写成原MRQ收据成功。

## 临时目录、清理与证据

按用户最新要求，临时媒体统一在`G:/FutsalMOT_Dataset/test/<attempt>/raw`。a01/a02已从原_work路径同卷移入test，历史收据路径保留并以`_test_lifecycle.json.relocated_from`解释。

a02所有EXR消费者结束后，已按精确10项清单删除104,714,404字节EXR；不再保留其原深度/Cryptomatte。其RGB、两种mask和标注保留24小时；a01失败诊断最多7天。每天04:00（Asia/Shanghai）的原生自动任务执行`tools/ue_ops/cleanup_test_render.ps1 -Apply`，仅清理带明确到期收据、已停止、无junction的test子目录。正常清理保持安静。项目Saved仅保留必要小型配置、日志和关键收据。

关键入口：

- `Saved/JerseyNumberUV/number_uv_random_s1048_a02/postprocess_complete.json`
- `Saved/JerseyNumberUV/number_uv_random_s1048_a02/exr_cleanup_complete.json`
- `Saved/JerseyNumberUV/number_runtime_build_a01.log`
- `Saved/Pose17Development/editor_number_uv_random_a01.log`和`editor_number_uv_random_a02.log`
- `G:/FutsalMOT_Dataset/test/number_uv_random_s1048_a02/raw/number_uv_random_s1048_a02/CineCam_01/annotations.jsonl`（临时，到期清理）

本轮运行字段缺项与限制：没有完整比赛新清单、没有所有机位与所有外观组合的生产验收；短样未完成新数据集body12/逐帧相机状态全契约适配。下一步以这些实际缺项准备有限生产，不重复已有单人近景或展开额外性能测试。
