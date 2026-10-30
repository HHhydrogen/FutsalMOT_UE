# 验证与当前限制

新数据唯一入口为[单seed管线](../production/SINGLE_SEED_BASELINE_V1.md)，参数固定4K、10FPS、8/8写出与每机位独立UE。当前具体状态和下一步见[任务状态](../../TASK_STATUS_AND_NEXT_STEPS.md)，不以旧生产、Pose17候选或静态测试代替本次运行证据。

## 已有动态证据

a09已完成六机位各30帧，共180组RGB/人物mask/号码mask、1800个人物记录、905条可见号码、21600个body12点；六次恢复和正常退出通过，EXR已消费清理。完整3001帧×6机位尚未生成，短样结果不代表整场已经通过。后续代码或入口变更采用新attempt/源码绑定，原收据保留原值。

新功能仅做必要针对检查。CPU单元测试只证明纯代码行为，不能证明UE资产、材质保存恢复、动画、光照、相机或实际mask同步。默认pytest不运行真实GRF集成；P1固定Python3.9，UE脚本仅在真实UE5.8 Editor执行，研究Torch环境独立。

## 标注和运动边界

- 当前输出body12，不是COCO17。visibility保留unknown=0；号码readable未人工认证时为false，不能冒充物理遮挡或OCR真值。
- bbox是可见实例像素tight box，不是amodal人体框；不可见仍保留身份和轨迹。
- GRF运动由双方内置AI产生，按首次done结束完整episode；不再选择旧活跃窗口，也不补静止尾帧或拼接reset。
- 同seed所有机位和帧属于一个split；当前1048诊断不自动进入正式train/dev。随机局部机位按各seed冻结清单核对。
- 不同UE/GPU的RGB不保证逐字节一致；独立机位native world差异保留原值，不平均成exact。

## 执行、恢复和存储

每机位独立UE、串行派发，使用已确认GPU渲染/CPU-LBS；内存门槛与写出配置消费冻结协议。MRQ提交不等于成功，必须收齐实际帧集、恢复和正常退出收据。未知dirty包或活动MRQ不得强杀。

控制器可以跳过有正常退出收据的完整机位；未闭合的机位保留现场停止，不支持机位内逐帧续跑或半导出自动续跑。新attempt不能覆盖已有输出或套用旧成功收据。

媒体只写G盘独立test attempt。分机位入口已接入1TiB预算、100GiB最低余量和7byte/px估算；渲染、导出、验证及EXR清理期间保持活动，成功保留计时从最终闭合开始，UE停止未确认时保持attention_required。具体轮询与失败处理见[存储规范](../operations/STORAGE_POLICY.md)。这些接线已做代码检查，尚未执行真实长样。原深度/Cryptomatte删除后不能由RGB/mask恢复或声称仍保留遮挡证据。

## 历史数据与研究

旧v1_no_numbers_4k的8seed/20116对RGB-mask和Pose17位置试产保持原版本、原split与原证据；不改旧数据、不把12点重命名为17点，也不靠新代码补造历史采样。旧生成操作手册已移除，可经Git历史追溯。

单seed完整验收前不开始总数据集发布。任何数据生成通过都不等于证明模型收益；真实最终测试封存、研究曝光与全部负结果遵守根AGENTS及[训练历史](../research/TRAINING_HISTORY.md)。
