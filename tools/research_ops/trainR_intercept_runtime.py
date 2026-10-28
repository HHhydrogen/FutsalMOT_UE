"""固定1000原始真实窗的一维截距校准；无增广、无SGD、不读取验证或测试。"""
from copy import deepcopy
import hashlib
import json
import math
import struct


WINDOWS = 1000
TOLERANCE = 1e-10
MAX_ITERATIONS = 200
PARAMETERS = dict(clean_R_unique_windows=WINDOWS, window_weighting='equal_all1000_including_empty_known_zero_contribution',
    known_pair_weighting='equal_within_each_window', unknown_fit=False, augmentation=False,
    fit_dtype='float64_from_original_FP32_logits', apply_dtype='float32_scalar_buffer',
    objective='window_equal_stable_binary_cross_entropy', tolerance=TOLERANCE, max_bisection_iterations=MAX_ITERATIONS,
    max_bracket_doublings=MAX_ITERATIONS, bracket='symmetric_plus_minus1_then_double_both_sides',
    stopping='exact_zero_derivative_or_absolute_beta_bracket_width_at_most_tolerance',
    derivative_tolerance_used_for_stopping=False, beta_sign_restricted=False, new_optimizer_updates=0,
    empty_known_window_objective_and_gradient=0, normalization_denominator=WINDOWS,
    source_window_exposures='1000_unique_clean_R_not_original_3000_repeated_exposure_table',
    alias_rule='apply_beta32_exactly_zero_only_no_nearzero_threshold')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def float32(value):
    require(type(value) in (int, float) and math.isfinite(value), '截距与原logit必须有限数值')
    try:
        result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError('数值不能表示为有限FP32') from error
    require(math.isfinite(result), 'FP32数值非有限')
    return result


def sigmoid64(value):
    require(math.isfinite(value), 'sigmoid输入必须有限')
    if value >= 0:
        return 1./(1.+math.exp(-value))
    exponential = math.exp(value)
    return exponential/(1.+exponential)


def bce64(value, label):
    """稳定softplus表达，避免极端logit的exp溢出或log(0)。"""
    require(label in (0, 1) and math.isfinite(value), 'BCE标签或输入无效')
    return (max(value, 0.) if label == 0 else max(-value, 0.)) + math.log1p(math.exp(-abs(value)))


def residual64(value, label):
    # 正例用-sigmoid(-z)，不做1-sigmoid(z)的大数消减。
    return sigmoid64(value) if label == 0 else -sigmoid64(-value)


def prepare_windows(windows):
    require(isinstance(windows, (list, tuple)) and len(windows) == WINDOWS, '每模型必须固定恰1000个唯一clean R窗')
    require(all(type(window.get('window_uid')) is str and window['window_uid'] for window in windows)
        and len({window['window_uid'] for window in windows}) == WINDOWS, '不能复制UID填额或缺失原窗口身份')
    result = []
    totals = dict(windows=WINDOWS, supervised_window_count=0, empty_known_window_count=0,
        all_pair_count=0, known_pair_count=0, unknown_pair_count=0, positive_pair_count=0, negative_pair_count=0)
    for window in windows:
        logits, labels = window['logits'], window['labels']
        require(isinstance(logits, (list, tuple)) and isinstance(labels, (list, tuple)) and len(logits) == len(labels),
                '原logits/标签必须同序、同长度')
        require(all(float32(value) == value for value in logits), '输入必须原FP32逐值logit，不重新评分或改精度来源')
        require(all(label is None or (type(label) is int and label in (0, 1)) for label in labels),
                '标签只能原0/1/None，unknown不补负例')
        known = [index for index, label in enumerate(labels) if label is not None]
        item = dict(window_uid=window['window_uid'], logits=[float(value) for value in logits], labels=list(labels),
            known_pair_indices=known, all_pairs=len(labels), known_pairs=len(known), unknown_pairs=len(labels)-len(known),
            objective_window_weight=1./WINDOWS, known_pair_weight_within_window=1./len(known) if known else None,
            empty_known_contributes_exact_zero=not bool(known))
        if 'candidate_UIDs' in window:
            require(len(window['candidate_UIDs']) == len(labels), '候选UID同序映射长度不同')
            item['candidate_UIDs'] = deepcopy(window['candidate_UIDs'])
        result.append(item)
        totals['supervised_window_count'] += bool(known)
        totals['empty_known_window_count'] += not bool(known)
        totals['all_pair_count'] += len(labels)
        totals['known_pair_count'] += len(known)
        totals['unknown_pair_count'] += len(labels)-len(known)
        totals['positive_pair_count'] += sum(label == 1 for label in labels)
        totals['negative_pair_count'] += sum(label == 0 for label in labels)
    return result, totals


def objective(windows, beta):
    require(math.isfinite(beta), '拟合截距必须有限')
    losses, gradients = [], []
    for window in windows:
        known = window['known_pair_indices']
        if not known:
            losses.append(0.)
            gradients.append(0.)
            continue
        losses.append(math.fsum(bce64(window['logits'][index]+beta, window['labels'][index]) for index in known)/len(known))
        gradients.append(math.fsum(residual64(window['logits'][index]+beta, window['labels'][index]) for index in known)/len(known))
    return dict(NLL=math.fsum(losses)/WINDOWS, derivative=math.fsum(gradients)/WINDOWS)


def apply_intercept_fp32(logits, beta32):
    beta32 = float32(beta32)
    # 零截距保留原值，包括负零；真实forward也直接返回原tensor。
    return list(logits) if beta32 == 0. else [float32(float32(value)+beta32) for value in logits]


def rank_audit(windows, beta32):
    comparisons = collapsed = reversals = changed_windows = 0
    for window in windows:
        original = sorted(set(window['logits']))
        shifted = apply_intercept_fp32(original, beta32)
        current = 0
        for left, right in zip(shifted, shifted[1:]):
            comparisons += 1
            reversals += int(left > right)
            current += int(left == right)
        collapsed += current
        changed_windows += current > 0
    require(reversals == 0, '有限FP32常数相加不应反转顺序；发现则停止')
    return dict(scope='adjacent_distinct_original_logits_within_each_window_all_pairs_including_unknown',
        adjacent_distinct_input_comparisons=comparisons, order_reversals=reversals,
        adjacent_distinct_logits_collapsed_to_FP32_ties=collapsed, windows_with_new_FP32_ties=changed_windows,
        mathematical_constant_shift_preserves_ranking=True, finite_precision_can_create_new_ties=True,
        strict_rank_equality_claim=False)


def descriptive_metrics(windows, beta, *, apply32=False):
    nll, brier, acceptance_known, acceptance_all = [], [], [], []
    supervised = sum(bool(window['known_pair_indices']) for window in windows)
    for window in windows:
        values = apply_intercept_fp32(window['logits'], beta) if apply32 else [value+beta for value in window['logits']]
        probabilities = [sigmoid64(value) for value in values]
        known = window['known_pair_indices']
        if known:
            nll.append(math.fsum(bce64(values[index], window['labels'][index]) for index in known)/len(known))
            brier.append(math.fsum(residual64(values[index], window['labels'][index])**2 for index in known)/len(known))
            acceptance_known.append(sum(probabilities[index] >= .5 for index in known)/len(known))
        else:
            nll.append(0.)
            brier.append(0.)
            acceptance_known.append(0.)
        acceptance_all.append(sum(value >= .5 for value in probabilities)/len(probabilities) if probabilities else 0.)
    return dict(NLL=math.fsum(nll)/WINDOWS, Brier=math.fsum(brier)/WINDOWS,
        probability_acceptance_known_pairs_window_equal=math.fsum(acceptance_known)/WINDOWS,
        probability_acceptance_all_pairs_window_equal=math.fsum(acceptance_all)/WINDOWS,
        known_supervised_window_NLL_description=math.fsum(nll)/supervised if supervised else None,
        known_supervised_window_Brier_description=math.fsum(brier)/supervised if supervised else None,
        denominator_all_windows=WINDOWS, supervised_window_count=supervised,
        arithmetic='FP64_metrics_after_FP32_logit_addition' if apply32 else 'FP64_original_logits_plus_beta64',
        acceptance_rule='sigmoid64(z)>=0.5_descriptive_only_not_actual_Torch_FP32_tracker_decision',
        actual_Torch_probability_or_cost_gate_verified=False)


def fit_intercept(windows):
    """确定的一维稳定BCE求根；空known窗仍在固定1000分母内贡献0。"""
    prepared, totals = prepare_windows(windows)
    before = descriptive_metrics(prepared, 0.)
    result = dict(schema='trainR_intercept_fit_v1', parameters=deepcopy(PARAMETERS), totals=totals,
        input_windows=prepared, input_sha256=hashlib.sha256(canonical(prepared).encode()).hexdigest(),
        before=before, beta64=None, apply_beta32=None, after_fit64=None,
        after_projected_beta32_sum64=None, after_apply32=None,
        bracket_trace=[], bisection_trace=[], actual_Torch_numeric_admission_required=True,
        optimizer_updates=0, new_model_training=False, validation_or_test_inputs_used=False,
        fitting_objective_improvement_is_tracking_effectiveness_evidence=False,
        source_weights_or_normalizer_or_features_changed=False)
    if not totals['known_pair_count']:
        result.update(status='unidentifiable_no_known_pairs', finite_minimizer=False, limiting_beta='all_values_undetermined')
        return result
    if not totals['positive_pair_count'] or not totals['negative_pair_count']:
        result.update(status='unidentifiable_single_class_no_finite_intercept', finite_minimizer=False,
            limiting_beta='positive_infinity' if totals['positive_pair_count'] else 'negative_infinity')
        return result
    zero = objective(prepared, 0.)
    beta = 0. if zero['derivative'] == 0. else None
    reason = 'exact_zero_derivative_at_zero' if beta is not None else None
    lower, upper = -1., 1.
    if beta is None:
        for expansion in range(MAX_ITERATIONS+1):
            lo, hi = objective(prepared, lower), objective(prepared, upper)
            result['bracket_trace'].append(dict(iteration=expansion, lower=lower, upper=upper,
                derivative_lower=lo['derivative'], derivative_upper=hi['derivative']))
            if lo['derivative'] == 0.:
                beta, reason = lower, 'exact_zero_derivative_at_bracket_endpoint'
                break
            if hi['derivative'] == 0.:
                beta, reason = upper, 'exact_zero_derivative_at_bracket_endpoint'
                break
            if lo['derivative'] < 0. < hi['derivative']:
                break
            if expansion == MAX_ITERATIONS:
                result.update(status='numeric_unresolved_bracket_not_found', finite_minimizer=None)
                return result
            lower *= 2.
            upper *= 2.
        else:
            result.update(status='numeric_unresolved_bracket_not_found', finite_minimizer=None)
            return result
    if beta is None:
        for iteration in range(MAX_ITERATIONS):
            midpoint = lower+(upper-lower)/2.
            value = objective(prepared, midpoint)
            result['bisection_trace'].append(dict(iteration=iteration, lower=lower, upper=upper,
                midpoint=midpoint, derivative=value['derivative'], NLL=value['NLL']))
            if value['derivative'] == 0.:
                beta, reason = midpoint, 'exact_zero_derivative_in_bisection'
                break
            if upper-lower <= TOLERANCE:
                beta, reason = midpoint, 'absolute_beta_bracket_width_tolerance'
                break
            if midpoint == lower or midpoint == upper:
                result.update(status='numeric_unresolved_float64_resolution', finite_minimizer=None,
                    unresolved_bracket=dict(lower=lower, upper=upper))
                return result
            if value['derivative'] < 0.:
                lower = midpoint
            else:
                upper = midpoint
        else:
            result.update(status='numeric_unresolved_bisection_iteration_limit', finite_minimizer=None)
            return result
    try:
        deployed = float32(beta)
        projected = descriptive_metrics(prepared, deployed)
        projected['arithmetic'] = 'FP64_original_logits_plus_projected_beta32_without_FP32_addition'
        after_apply = descriptive_metrics(prepared, deployed, apply32=True)
        ranks = rank_audit(prepared, deployed)
    except ValueError as error:
        result.update(status='numeric_unresolved_FP32_application', finite_minimizer=True,
            beta64=beta, application_error=str(error), after_fit64=descriptive_metrics(prepared, beta))
        return result
    result.update(status='complete_finite_trainR_intercept_fit_not_tracking_effect', finite_minimizer=True,
        beta64=beta, apply_beta32=deployed, stopping_reason=reason, derivative_at_solution=objective(prepared, beta)['derivative'],
        final_bracket=dict(lower=lower, upper=upper, width=upper-lower),
        after_fit64=descriptive_metrics(prepared, beta), after_projected_beta32_sum64=projected,
        after_apply32=after_apply, apply32_rank_audit=ranks,
        NLL_numeric_drift=dict(beta32_projection_vs_beta64=projected['NLL']-descriptive_metrics(prepared, beta)['NLL'],
            FP32_addition_vs_projected_beta32_sum64=after_apply['NLL']-projected['NLL'],
            FP32_addition_vs_beta64=after_apply['NLL']-descriptive_metrics(prepared, beta)['NLL']),
        original_prediction_alias_necessary_zero_condition=deployed == 0., original_prediction_alias_authorized=False,
        alias_requires_source_and_forward_identity_proof=True, alias_comparison='exact_FP32_zero_no_epsilon',
        objective_delta=descriptive_metrics(prepared, beta)['NLL']-before['NLL'])
    return result


def wrap_intercept(model, beta32, torch):
    """只包装原模型forward；外部仍使用原feature/normalizer/gate/生命周期。"""
    beta32 = float32(beta32)
    parameters = list(model.parameters())
    require(parameters and all(parameter.dtype == torch.float32 for parameter in parameters), '原强motion必须实际FP32参数模型')
    for parameter in parameters:
        parameter.requires_grad_(False)
    model.eval()

    class InterceptOnly(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.base = model
            self.register_buffer('intercept_beta32', torch.tensor(beta32, dtype=torch.float32, device=parameters[0].device))
            self._exact_zero_offset = beta32 == 0.
            self.eval()

        def train(self, mode=True):
            # 该包装只供冻结推理，不允许误切回训练模式。
            super().train(False)
            self.base.eval()
            return self

        def forward(self, x):
            with torch.no_grad():
                values = self.base(x)
                return values if self._exact_zero_offset else values+self.intercept_beta32

    return InterceptOnly()
