"""仅在原R窗known BCE归约时应用原评分资格mask；不裁剪前向、不运行训练。"""
import hashlib
import json

SCHEMA = 'R_candidate_eligibility_masked_BCE_method_v1'
MASK_SCHEMA = 'R_candidate_eligibility_sidecar_v1'
RULE = 'original_pre_probability_stage_active_AND_enabled'
SOURCE_KEYS = ('source_job_id', 'candidate_frame_number', 'source_stage', 'source_row_index', 'source_track_id',
               'teacher_model_id', 'teacher_regime', 'teacher_seed', 'fold', 'sequence')


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value): return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def label_counts(labels, mask):
    result = dict(raw_candidate_pairs=len(labels), kept_candidate_pairs=sum(mask), excluded_candidate_pairs=len(labels)-sum(mask))
    groups = dict(known=lambda v: v is not None, positive=lambda v: v == 1, negative=lambda v: v == 0, unknown=lambda v: v is None)
    for name, predicate in groups.items():
        result['raw_'+name+'_pairs'] = sum(predicate(v) for v in labels)
        result['kept_'+name+'_pairs'] = sum(predicate(v) and keep for v, keep in zip(labels, mask))
        result['excluded_'+name+'_pairs'] = result['raw_'+name+'_pairs']-result['kept_'+name+'_pairs']
    result.update(raw_known_empty=int(result['raw_known_pairs'] == 0), effective_known_empty=int(result['kept_known_pairs'] == 0))
    return result


def bind_window_mask(window, sidecar):
    """mask仅由pre-probability stage/active/enabled决定；label只用于原known投影及记账。"""
    require(sidecar['schema'] == MASK_SCHEMA and sidecar['eligibility_rule'] == RULE
        and sidecar['eligibility_stage'] == 'pre_probability' and sidecar['labels_used_to_choose_mask'] is False,
        '只能原评分前资格，不能用概率或标签选择mask')
    metadata = window['aligned_bank_metadata']; history = [h['uid'] for h in window['history']]
    uids = [c['prediction']['uid'] for c in window['candidates']]
    require(window['window_uid'] == metadata['window_uid'] == sidecar['window_uid']
        and history == metadata['history_UIDs'] == sidecar['history_UIDs']
        and uids == metadata['candidate_UIDs'] == sidecar['candidate_UIDs']
        and all(metadata[k] == sidecar[k] for k in SOURCE_KEYS), 'mask侧表与原窗口UID/历史/候选或teacher坐标不同')
    require(len(uids) == len(set(uids)) and len(history) == len(set(history)) == 3, '原候选/三历史UID无效')
    active, enabled = sidecar['active'], sidecar['enabled']
    require(type(active) is bool and isinstance(enabled, list) and len(enabled) == len(uids)
        and all(type(v) is bool for v in enabled), '资格必须完整bool，不把未知改为False')
    require(sidecar['source_stage'] == 'high_score', '本轮只使用原选中high-score R池')
    require(metadata['teacher_regime'] == 'R' and metadata['teacher_seed'] == 20261024, '侧表只绑定原首seed R teacher，不能换teacher')
    require(active or not any(enabled), 'inactive原enabled应全False；不能猜单独motion gate')
    eligible = [active and value for value in enabled]
    if 'scoring_eligible' in sidecar: require(sidecar['scoring_eligible'] == eligible and all(type(v) is bool for v in sidecar['scoring_eligible']), '侧表评分资格不同')
    # 此行之后才读取label；不允许label参与上述mask构造。
    labels = [c['label'] for c in window['candidates']]
    require(labels == metadata['pair_labels'] and all(v is None or type(v) is int and v in (0, 1) for v in labels), '原label/unknown改变')
    known = [i for i, value in enumerate(labels) if value is not None]
    require(known, '原训练池须至少一个known；有效空窗允许但不补原all-unknown窗')
    body = dict(schema='R_candidate_eligibility_bound_window_v1', method_schema=SCHEMA, eligibility_rule=RULE,
        window_uid=window['window_uid'], history_UIDs=history, candidate_UIDs=uids, all_labels=labels,
        all_scoring_eligible=eligible, known_indices=known, known_candidate_UIDs=[uids[i] for i in known],
        known_labels=[labels[i] for i in known], known_scoring_eligible=[eligible[i] for i in known],
        source={k: sidecar[k] for k in SOURCE_KEYS}, sidecar_sha256=digest(sidecar),
        accounting=label_counts(labels, eligible), labels_changed=False, original_forward_known_order_preserved=True)
    return dict(body, binding_sha256=digest(body))


def checked_binding(binding):
    body = {k: v for k, v in binding.items() if k != 'binding_sha256'}
    require(binding['schema'] == 'R_candidate_eligibility_bound_window_v1' and binding['method_schema'] == SCHEMA
        and binding['binding_sha256'] == digest(body) and binding['eligibility_rule'] == RULE
        and binding['labels_changed'] is False and binding['original_forward_known_order_preserved'] is True, 'mask绑定被改变')
    labels, mask = binding['all_labels'], binding['all_scoring_eligible']
    require(len(labels) == len(mask) and all(type(v) is bool for v in mask)
        and binding['known_indices'] == [i for i, v in enumerate(labels) if v is not None]
        and binding['known_labels'] == [labels[i] for i in binding['known_indices']]
        and binding['known_scoring_eligible'] == [mask[i] for i in binding['known_indices']]
        and binding['known_candidate_UIDs'] == [binding['candidate_UIDs'][i] for i in binding['known_indices']]
        and binding['accounting'] == label_counts(labels, mask), '原known投影/资格/计数不一致')
    return binding


def masked_real_domain_BCE(model, windows, bindings):
    """三原R窗完整known拼接一次前向；仅unreduced BCE归约受mask影响。"""
    import torch
    from torch.nn import functional as F
    require(len(windows) == len(bindings) == 3, '每步必须原3R，不能因空有效窗重采样或跳窗')
    counts = []; masks = []; accounting = []; xs = []; ys = []
    for window, candidate_binding in zip(windows, bindings):
        binding = checked_binding(candidate_binding); x, y = window['x'], window['labels']
        require(window['window_uid'] == binding['window_uid'] and window['candidate_pairs'] == binding['accounting']['raw_candidate_pairs']
            and window['known_pairs'] == binding['accounting']['raw_known_pairs'], '原窗口曝光/全known预算改变')
        require(x.ndim == 2 and x.shape[1] == 194 and y.ndim == 1 and x.shape[0] == y.numel() == window['known_pairs'] > 0,
            '原known特征须K×194且不提前过滤mask')
        require(x.dtype == y.dtype == torch.float32 and bool(torch.isfinite(x).all()) and bool(torch.isfinite(y).all())
            and y.tolist() == binding['known_labels'], '有限FP32或known标签/原顺序不同')
        counts.append(y.numel()); masks.append(binding['known_scoring_eligible']); xs.append(x); ys.append(y)
        accounting.append(dict(window_uid=binding['window_uid'], binding_sha256=binding['binding_sha256'],
            sidecar_sha256=binding['sidecar_sha256'], source=binding['source'], known_scoring_eligible=list(binding['known_scoring_eligible']),
            known_candidate_UIDs=list(binding['known_candidate_UIDs']), known_labels=list(binding['known_labels']),
            **binding['accounting']))
    device = next(model.parameters()).device
    # 此两次cat与原domain_loss顺序相同；mask不改变前向batch大小或GEMM。
    x = torch.cat(xs).to(device); y = torch.cat(ys).to(device)
    logits = model(x).reshape(-1)
    require(logits.numel() == sum(counts) and logits.dtype == torch.float32 and bool(torch.isfinite(logits).all()), '原全known logit必须有限FP32')
    losses = F.binary_cross_entropy_with_logits(logits, y, reduction='none')
    parts = losses.split(counts); means = []
    for loss_part, mask in zip(parts, masks):
        if all(mask): means.append(loss_part.mean())  # 全true与原BCE相同归约，避免额外gather。
        elif any(mask):
            index = torch.tensor([i for i, keep in enumerate(mask) if keep], device=loss_part.device, dtype=torch.long)
            means.append(loss_part.index_select(0, index).mean())
        else: means.append((loss_part*0.).sum())  # 单项先乘零，避免有限单项求和溢出；不detach。
    loss = torch.stack(means).mean()
    totals = {key: sum(row[key] for row in accounting) for key in accounting[0] if key not in
        ('window_uid', 'binding_sha256', 'sidecar_sha256', 'source', 'known_scoring_eligible', 'known_candidate_UIDs', 'known_labels')}
    totals.update(R_scoring_eligible_unknown_pairs=totals['kept_unknown_pairs'], R_effective_unknown_pairs=0)
    return loss, dict(schema='R_candidate_eligibility_step_domain_accounting_v1', windows=accounting, totals=totals,
        real_window_count=3, domain_forward_calls=1, forwarded_known_pairs=sum(counts), original_known_order_preserved=True,
        original_labels_unchanged=True, empty_effective_windows_contribute_graph_zero=True, window_resampling=False,
        unknown_features_forwarded=False, unknown_labels_used_for_loss=False,
        known_mask_applied_after_unreduced_BCE=True, numeric_dtype='float32')


def step_loss(model, real_windows, real_bindings, synthetic_windows, original_domain_loss):
    """原3R平均，加原S逐窗known-BCE/3；此函数不反传、不创建优化器或step。"""
    require(len(synthetic_windows) in (0, 1), 'R无S，RS只能原1S')
    real, accounting = masked_real_domain_BCE(model, real_windows, real_bindings)
    synthetic = original_domain_loss(model, synthetic_windows) if synthetic_windows else None
    total = real if synthetic is None else real+synthetic/3
    return dict(loss=total, real_loss=real, synthetic_loss=synthetic, real_accounting=accounting,
        S_original_domain_loss_called=len(synthetic_windows), S_alpha=1/3, optimizer_step_executed=False,
        R_objective='original_known_pair_BCE_masked_after_full_known_forward_per_window_mean_then_mean3R',
        S_objective='unchanged_original_known_pair_BCE', empty_effective_R_windows_not_skipped=True)
