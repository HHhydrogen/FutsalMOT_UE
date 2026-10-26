# 绿色草地与原seed球衣配对

2026-10-26。用户要求直接推进实验，取消渲染/导出加速开发及基准。当前复用已验GPU-render/CPU-LBS、原appearance v1球衣和串行采集，不引入新解码器、渲染/导出重叠或额外成像增强。

## 数据及短样

来源保持1048 train `[0,300)`、1102 synthetic_dev `[20,320)`，原GRF运动、四机位、固定七模型及肤色不变。A默认服装，B严格采用原seed manifest的Jersey/Shorts；不重新抽模型/肤色，不接号码WIP。绿色目录沿用原floor独立seed算法，1048选择稍冷绿，1102选择稍暖绿；A/B同seed同地板，每段固定。颜色增益和原草地纹理链见[绿色方案](../engineering/GREEN_FLOOR_VARIATION.md)。

主短样为两seed×A/B×四机位×3帧，48RGB/mask、480逐视角人物Pose。另在train1048 B上补其余四种绿色各四机位3帧，共48RGB/mask、480Pose，用于检查原绿及候选范围；不使用1102指标选色。合计96RGB/mask、960Pose，但仅两seed各3个源时间样本，不能称96个独立动作样本。

新契约与旧蓝契约隔离、原相机/roster/source验证共11项CPU检查通过；这不替代真实MRQ与看图。运行入口为`Saved/AppearancePlanning/green_seeded_kit_a01/control_short_a01/state.json`，短样准入绑定69项来源、源码和材质及原DLL。启动后不修改绑定文件。每个短样新鲜Editor，真实12线程/队列8读回，MRQ后恢复地板/角色/相机并释放回调，正常退出且确认本次日志和进程，再6CPU后处理并精确清EXR。所有媒体仅G；D研究目录只存消费索引/收据。

短样终态要求8项、96/96/960及96EXR退休，真实控制器退出；随后一次运行`tools/appearance/review_green_kit_short_a01.py`。它生成四机位A/B、四role和五绿色范围三张总览。root必须实际看图，另核对原native逐帧材质绑定、Pose输出、相机、同源world及恢复，才签`short_acceptance_root.json`。保留实际world差和mask差，不平均或冒称全像素exact；位置unknown不升级为物理可见性。当前运行不等根验收。

本次短样已完成上述实际运行和根看图验收。相机/world配对逐值一致、最大world差0；检查的中帧mask差0。B组1048外场黑/红、1102外场红/白，四role仍按原manifest分配。96份EXR共3883119675字节已精确退休，RGB/mask/Pose/world/原生及校准保留。所有短样UE/导出/控制器真实退出，根收据为`Saved/AppearancePlanning/green_seeded_kit_a01/short_acceptance_root.json`。

## 完整采集及发布

短样通过后才另签full准入：4个canonical计划拆成16个实际单机位单位，每单位300连续帧，目标4800RGB/mask、48000人物Pose；600源时间样本，两个服装版本和四机位不增加独立运动量。入口仍为`run_green_kit_serial_a01.py --stage full`，先只读预飞再明确执行。严格每单位UE退出→CPU后处理→EXR退休→下一单位；不重启旧蓝a02/a03/a04控制器或复用其媒体。

全部单位完成、EXR退休且所有UE及控制器实际退出后，才同G卷发布到独立`G:/FutsalMOT_Dataset/v3_pose17_green_seeded_kit_pair_a01`。发布保留原unit小索引和消费收据bytes，写intent、逐项rename journal、配对元数据与relocation，未知partial拒自动重放。旧蓝、v1及已冻结研究不改。源diagnostic/not_training/MRQ_syncfalse及unknown限制继续保留，发布不自动获得训练资格。

完整准入已实际冻结并通过只读预飞，首300帧单位已经提交。绿色专用发布工具为`tools/appearance/publish_green_kit_pair_a01.py`，默认只读，完整终态前拒绝；3项CPU夹具检查已过，尚未执行真实发布。它从manifest及真实capture_scope获取camera_id，不假造旧蓝控制器成功状态。world工程配对界限为1mm，仅作来源一致性的工程检查，仍分别报告实际exact与最大差，不是研究效用门槛。

## 之后的公平实验

新数据完成发布和实际安全退出UE后，另冻结预测/训练准入。主比较只改变服装经预测Pose进入关联器的输入：固定旧v9的S框、窗口UID和身份标签，同PT Pose模型与crop规则分别提取新A/B的Pose；R缓存完全不变。映射要依实际seed、源时间和相机核对，不能凭目录名伪造对应。若无法严格对应，先建立一致的新控制，不把不等输入的旧结果当公平基线。

独立预测候选为`tools/research_ops/green_kit_prediction_cache.py`。它只复用冻结的v8裁剪Pose数值函数，不运行检测器；先验证16单位/发布SHA/全部正常退出/EXR退休及实际无UE进程，再允许新D研究bundle和显式配置SHA执行。A/B每帧保留原检测框、score、UID及顺序，拒绝丢弃预测或回填旧Pose；只读新G成品，预取2，不写裁剪图。4项CPU门禁/固定框检查已通过；当前尚未安装执行bundle、签预测配置或运行新绿色GPU推理，不能称该入口已通过端到端验证。

渲染期间已独立构建`grf_ue_bridge.green_kit_pair_inputs.replace_synthetic_pose`：仅替换旧S记录的`xy_px/geometry_valid`，强制1000唯一窗口，框/score/时间/尺寸/UID、候选标签及顺序保持，缺新预测直接拒绝而不回填旧Pose；1102和test不能进入S池。5项CPU检查及真实旧池的零变化自检通过：1000窗口、5431唯一观测、4791候选pair、2758已知标签pair完整保留。自检仅用旧观测自身验证契约，没有新绿色预测或模型更新。历史UID含blue是逻辑对应键，不能冒充实际图像来源；绿色图片及模型身份必须另由预测manifest明确绑定。收据为`Saved/ResearchBuild/green_pose_pool_CPU_a01.json`，实际绿色A/B池尚未生成。

固定检测的帧对应另由`plan_green_frames`登记：缓存中的第一帧检测UID含`000001`（一基frame_number），图片却为`000000.png`（零基frame_index）；必须按显式帧字段映射，不能从UID猜文件名。3项CPU检查和真实旧四机位1200帧、13199检测的对应规则检查通过，A/B固定框链相同，旧Pose字段不传给新推理。该检查仅使用待发布组结构模板，没有验证新绿色文件存在或生成Pose；待真正发布后仍需绑定实际组/图片来源与模型。小收据为`Saved/ResearchBuild/green_frame_correspondence_CPU_a01.json`。

canonical gated A/B×3比赛留一×3训练seed，拟18个新RS；每臂1000实际更新、同3000R窗口同序、额外1000S同序同pair，使用已有预取2/FP32及last，不选best或追加旧权重训练。若执行18新RS，新增预算为18000更新、54000R及18000S窗口，不能称图像数或总标注量。纯R、motion_RS、PT只有完整数值源码、输入、初始化和预算相同时才引用旧结果，并在收据中明确“历史控制复用/新增更新0”。

分别报告B−A、混合−纯R、混合−motion_RS及预训练，保留每fold/seed、队内/跨队和负结果。当前关联器不读RGB；服装改变颜色和纹理，不能只归因颜色，也不是全图检测泛化实验。仅1048参与合成训练，1102不训练、不挑配色；一个合成运动seed不代表广泛动作或环境覆盖。既有v9 Pose尚未稳定超过强motion_RS，这一事实不因新数据更自然而改变。

最终SNMOT116/187与test包始终封存。三场已观察短开发比赛和三训练seed不构成新盲测、统计显著性或真实五人制泛化结论。噪声、真实曝光模糊、纹理与粗糙度都留给独立因素实验，不在本轮同时变化。
