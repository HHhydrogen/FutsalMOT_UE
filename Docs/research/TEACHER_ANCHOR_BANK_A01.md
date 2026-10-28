# 已选3000R窗口的目标身份锚定交叉核查a01

2026-10-28。用户已授权依据完整证据继续。前一[决策机会核查](DECISION_OPPORTUNITY_A01_RESULTS.md)发现13319行当前历史与首次stage可信3历史anchor不同，但那是全部重复状态行，不能据此认定实际选中3000R窗含相同比例或存在错标签。下一项仅量化这个缺口，不训练Pose、调门槛或改变历史写入。

## 冻结范围

只读已验state_aligned_training_a01/inputs_complete_root_a01.json所绑定三个既有R池，每fold game4/game6/game9各1000唯一窗口，两允许训练源各500；合计3000。原teacher为R-only、seed20261024，六个fold×允许sequence unit。原stage=high_score、三条可靠历史、known≥1、whole-high-stage候选（并非exact-enabled-subset）。窗口顺序、所有UID、pair标签和原预算逐条核对，不重建池、不重新匹配GT或筛窗。

仅从已独立终验的decision_opportunity_a01十二unit中选六个R teacher新账本，各完整流式读一遍；RS只读小unit收据，不打开其ledger。按(source_job_id,frame_number,stage,row_index,track_id)与原metadata精确join，history_UIDs/query_GT_id/candidate_UIDs/pair_labels须逐值相同，不能仅按帧或近似bbox匹配。

每窗保存早期stage可信anchor、当前query、anchor_drift=true/false/null、是否无positive、all/known/positive/negative/unknown pair、实际首停及local/Pose支持机会旗标。漂移仅是已验几何身份代理的分离，不证明人为身份标签错误；null保留。全部3000条输出CSV/JSONL，按fold、fold×source和source列绝对计数，来源率先平均同源两fold再三source等权。该固定总体交叉核查不重新估计性能区间或AssA；前轮84个条件区间原样留存。

新优化更新/模型前向/追踪/solver/TrackEval/图像推理均0，优化器、batch、输入图像尺寸、训练步数均不适用，不打开模型、原frames、GT/cache或媒体。单进程流式扫描六个新R账本，仅保留3000小metadata/结果，不物化旧完整日志。不触碰原训练/追踪冻结源码和权重。SNMOT116/187/test始终封存。

完成后只依据实际选中窗口结果决定下一因素：如存在目标身份代理偏离，只能立明确身份锚定资格的候选数据实验；如不存在则排除此项解释，转查无正例/实际可达候选与监督目标的差异。不能把资格筛选与loss、模型容量、S比例、历史/Kalman同时改变，不能根据12开发成绩调比例。主模型维持原未校准strongmotion_RS，本轮无新训练和部署替换。
