# 完整随机外观下的 UV 球衣号码与数字标注

2026-10-29。用户已人工验收并确认固化当前号码系统：放大15%、背部中心下移0.02 UV，profile为`back_size115_down002_v1`。已完成真实10帧短样的显示和标注导出；完整新数据集另行生成。

## 使用入口

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
