# 300帧长窗口：既有GRF源输入准备

> 历史研究记录：仅解释原数据、协议与共享实现，不是当前生成操作手册。新数据只使用[当前single_seed入口](../production/SINGLE_SEED_BASELINE_V1.md)，不运行下文旧候选脚本或据此重建旧管线；历史源码及收据保持各自冻结版本。

本入口只准备CPU文本输入。它不运行GRF、不读取RGB/EXR、不启动UE/GPU，不改正式v1、原始1800步轨迹或旧120帧契约。当前状态为`CPU_inputs_ready_pending_new_P2_entry_and_dynamic_verification`；源、校准和计划均不能据此称为正式Pose数据或获准研究训练。

## 固定候选与帧身份

唯一候选为外层项目`Saved/ResearchDiagnostics/long_interaction_floor_candidate_a01/candidate_plan.json`，SHA256为`1ce9903a4afac203d931bb3d9c56cc8a3b2732a26345d9bd4cd6149c5da5c99e`。只使用其中两组所选窗口，不准备有重叠的ordinary比较窗口。

| seed | split | 输出相对帧 | 原GRF/Sequence绝对帧 | 导入前缀 | 输出相对帧150对应原帧 |
| --- | --- | --- | --- | --- | --- |
| 1048 | train | `[0,300)` | `[0,300)` | `[0,300)` | 150 |
| 1102 | synthetic_dev | `[0,300)` | `[20,320)` | `[0,320)` | 170 |

两组均为10FPS、名义30秒，首末采样时间差为29.9秒。导入保留从GRF第0步开始的上下文，1102不能把所选第20步重基为Sequence第0帧。`frame_mapping.jsonl`逐帧保存输出相对帧、Sequence绝对帧、原GRF帧/时间与原v1注释索引。

原v1的`annotations.frame_index`为一基，换算为：

```text
GRF source_step = clip.source_selection.source_step_range[0] + annotation.frame_index - 1
```

实际读取两组`clip.json`与每组首条annotation确认该约定；没有为输入准备重扫全部旧annotation或媒体。通用映射测试还覆盖原clip起点207的情况，不能将其他seed的v1局部0当作GRF0。

## 独立接口与输出

新文件：

- `ue/pose17_long_window_contract.py`：纯标准库契约与帧映射；导出`validate_long_window_contract`、`validate_floor_pair`、`source_prefix`。
- `tools/prepare_pose17_long_window_inputs.py`：核对候选/原始源/clip/七模型校准身份，生成独立前缀、映射及计划。
- `tests/test_pose17_long_window_inputs.py`：9项CPU测试，覆盖非零起点、重基/缺实体拒绝、来源SHA/split/尺寸门禁、地板配对、共享P2收据路径。

契约显式要求`long_window_contract=true`及精确`long_window`内容。新计划不得携带`location_pilot`或`location_pilot_contract`，包括值为false的字段。普通短诊断和旧120帧入口不能隐式接受300帧。native仍使用已存在的`pose17_gpu_render_cpu_lbs_joint_diagnostic`，每相机300帧×10人=3000条记录，小于现有4096上限。

固定10人顺序为`L0..L4,R0..R4`，角色依次为003/004/005/006/007/008/009/003/004/005。保留七角色精确资产路径、当前候选表面锚点身份及四个原相机绑定；不把静态候选升级为独立精度或遮挡验收。

真实交付位于外层`Saved/Pose17Development/long_window_inputs_a02/`：

```text
prepared_manifest.json
sources/seed_00001048/{meta.json,frames.jsonl,frame_mapping.jsonl,source_input.json}
sources/seed_00001102/{meta.json,frames.jsonl,frame_mapping.jsonl,source_input.json}
longpair_s00001048_sport_blue_v1_a01_gpu_lbs.json
longpair_s00001048_sport_terracotta_v1_a01_gpu_lbs.json
longpair_s00001102_sport_blue_v1_a01_gpu_lbs.json
longpair_s00001102_sport_terracotta_v1_a01_gpu_lbs.json
```

`source_input.prepared_prefix`逐个给出新meta、原字节前缀JSONL及映射文件的路径/SHA；`original_source`保留完整原始源身份。meta仅更改前缀`timing.num_steps`，不改变原始source身份或轨迹坐标。源JSONL原行字节复制，不裁剪球场边缘位置、补点或更改time/step。计划`source_motion.source_input`绑定该输入包；`source_build_receipt`指向本批目录下尚待P2产生的`P2_sources_prepare.json`，不能假装已经存在。

实际SHA256：

| 文件 | SHA256 |
| --- | --- |
| `prepared_manifest.json` | `1b0e458a24c81a181e122d25c4e01ce8ece59aafc425fbb7d10464f6f15ff693` |
| `sources/seed_00001048/source_input.json` | `0acdba9dc267cbe1de515a18e4c4ad7936e470cde0028c7e1e1687c7493d920b` |
| `sources/seed_00001102/source_input.json` | `ab1ce3ec1a72773c2d4e4dc7a640bfa556b6c29fda16bf4e2f59f5db0e986eeb` |

a01保留为初次CPU准备历史，其中计划曾引用每seed的旧P2收据位置；当前交付a02改为统一批次P2收据，未覆盖a01。两个floor变体共享每seed的同一输入SHA、相机、roster、时间和split，只允许地板ID与attempt不同；重复地板画面不算新增独立运动样本。

## 复现CPU准备

从内层仓库使用固定P1 Python3.9；输出必须是项目Saved下尚不存在的新目录：

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_pose17_long_window_inputs.py -v
& .\.venv\Scripts\python.exe tools/prepare_pose17_long_window_inputs.py --project D:/projects/FutsalMOT_UEDataset --candidate D:/projects/FutsalMOT_UEDataset/Saved/ResearchDiagnostics/long_interaction_floor_candidate_a01/candidate_plan.json --candidate-sha256 1ce9903a4afac203d931bb3d9c56cc8a3b2732a26345d9bd4cd6149c5da5c99e --output D:/projects/FutsalMOT_UEDataset/Saved/Pose17Development/long_window_inputs_NEW
```

输出包存在时拒绝覆盖；失败保留已写文件及`failure.json`。文件路径拒绝联接/符号链接，不跟随研究images联接。

## P2与后处理的最小接合边界

独立P2入口由`ue/pose17_long_window_p2.py`负责，读取本批`prepared_manifest`及SHA，不能硬编码a01目录。该入口需在真实UE中创建8个新Sequence，包为`/Game/FutsalMOT/Development/Pose17/long_interaction_floor_30s_a01/seed_XXXXXXXX/LS_Cam_01..04`，复用既有轨迹导入算法；保持原绝对帧，不覆盖120帧源资产。其统一收据记录真实创建/绑定/关键帧证据。

共享捕获runner、native收据校验、分析器及导出器分别需要识别独立long契约的严格300帧分支；不能把旧120布尔改为false绕过门禁。捕获前还需读取并冻结当次天气/曝光/灯光/动画与材质上下文，按已验单地板槽事务应用及恢复蓝/红棕，确保同seed两变体共享运动和其余上下文。P1没有伪造这些尚不存在的现场收据。

后续应保留每相机真实采样、相对/绝对帧和mesh/fence身份，验证300帧完整性；`review_frame_indices=[150]`仅为抽样总览。Pose世界点与投影可以用于仅位置监督准备，物理可见性仍为unknown，不写伪COCO v1/v2。正式训练输入及新R/RS实验需要独立准入，不接入当前已冻结120帧研究协议。

目标为2 seed×2 floor×4 camera×300=4800张RGB及同数mask、48000条人物Pose记录；这是待渲染目标，不是已完成数量。300帧捕获、配对动态上下文、MRQ同步和后处理尚未由本CPU准备验证。
