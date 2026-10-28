"""截距纯估计器与冻结forward的针对CPU合同；不加载真实权重或运行研究任务。"""
from contextlib import nullcontext
from copy import deepcopy
import math
import struct
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trainR_intercept_runtime as runtime


def windows(positive=500, raw=0.):
    return [dict(window_uid='window_'+str(index), logits=[runtime.float32(raw)],
        labels=[1 if index < positive else 0]) for index in range(runtime.WINDOWS)]


class FixtureTensor:
    """仅检查调用/舍入接口，不冒充真实Torch前向数值准入。"""
    def __init__(self, value, *, dtype='float32', device='cpu'):
        self.value = deepcopy(value)
        self.dtype, self.device, self.requires_grad = dtype, device, False
    def __add__(self, other):
        return FixtureTensor(runtime.apply_intercept_fp32(self.value, other.value))


class FixtureParameter(FixtureTensor):
    def requires_grad_(self, value):
        self.requires_grad = value
        return self


class FixtureModule:
    def __init__(self):
        self.training = True
        self.buffers = {}
    def register_buffer(self, name, value):
        self.buffers[name] = value
        setattr(self, name, value)
    def parameters(self):
        return self.base.parameters() if hasattr(self, 'base') else iter(getattr(self, 'weights', []))
    def train(self, mode=True):
        self.training = mode
        if hasattr(self, 'base'):
            self.base.train(mode)
        return self
    def eval(self): return self.train(False)
    def __call__(self, x): return self.forward(x)


class FixtureModel(FixtureModule):
    def __init__(self):
        super().__init__()
        self.weights = [FixtureParameter([2., -3.])]
        self.calls = 0
        self.output = FixtureTensor([-0., 1., -1.])
    def forward(self, x):
        self.calls += 1
        return self.output


FIXTURE_TORCH = SimpleNamespace(nn=SimpleNamespace(Module=FixtureModule), float32='float32',
    tensor=lambda value, dtype, device: FixtureTensor(value, dtype=dtype, device=device), no_grad=nullcontext)


class InterceptContracts(unittest.TestCase):
    def test_positive_negative_and_exact_zero_intercept_unrestricted_sign(self):
        positive = runtime.fit_intercept(windows(positive=750))
        negative = runtime.fit_intercept(windows(positive=250))
        zero = runtime.fit_intercept(windows())
        self.assertAlmostEqual(positive['beta64'], math.log(3), delta=runtime.TOLERANCE)
        self.assertAlmostEqual(negative['beta64'], -math.log(3), delta=runtime.TOLERANCE)
        self.assertEqual(zero['beta64'], 0.)
        self.assertEqual(zero['stopping_reason'], 'exact_zero_derivative_at_zero')
        self.assertTrue(zero['original_prediction_alias_necessary_zero_condition'])
        self.assertFalse(zero['original_prediction_alias_authorized'])
        self.assertTrue(zero['alias_requires_source_and_forward_identity_proof'])
        self.assertLess(positive['after_fit64']['NLL'], positive['before']['NLL'])
        self.assertLess(negative['after_fit64']['NLL'], negative['before']['NLL'])
        self.assertFalse(positive['fitting_objective_improvement_is_tracking_effectiveness_evidence'])
        self.assertEqual(positive['optimizer_updates'], 0)

    def test_window_equal_weighting_direction_opposes_pair_pooling_and_keeps998_empty(self):
        data = [dict(window_uid='window_'+str(index), logits=[0.], labels=[None]) for index in range(runtime.WINDOWS)]
        data[0].update(logits=[0.]*10, labels=[1]*9+[0])
        data[1].update(logits=[0.], labels=[0])
        result = runtime.fit_intercept(data)
        expected = math.log(.45/.55)
        self.assertAlmostEqual(result['beta64'], expected, delta=runtime.TOLERANCE)
        self.assertLess(result['beta64'], 0.)
        self.assertGreater(math.log(9/2), 0.)
        self.assertEqual(result['totals']['supervised_window_count'], 2)
        self.assertEqual(result['totals']['empty_known_window_count'], 998)
        self.assertEqual(result['totals']['unknown_pair_count'], 998)
        self.assertEqual(len(result['input_windows']), 1000)
        self.assertEqual(result['before']['NLL'], 2*math.log(2)/1000)
        self.assertEqual(result['before']['denominator_all_windows'], 1000)
        self.assertAlmostEqual(result['before']['known_supervised_window_NLL_description'], math.log(2))
        self.assertTrue(all(window['empty_known_contributes_exact_zero'] for window in result['input_windows'][2:]))
        self.assertTrue(result['parameters']['unknown_fit'] is False)

    def test_single_class_and_all_unknown_have_no_finite_or_invented_beta(self):
        for data, limit in ((windows(1000), 'positive_infinity'), (windows(0), 'negative_infinity')):
            result = runtime.fit_intercept(data)
            self.assertEqual(result['status'], 'unidentifiable_single_class_no_finite_intercept')
            self.assertEqual(result['limiting_beta'], limit)
            self.assertIsNone(result['beta64'])
            self.assertIsNone(result['apply_beta32'])
            self.assertFalse(result['finite_minimizer'])
        data = windows()
        for window in data:
            window['labels'] = [None]
        result = runtime.fit_intercept(data)
        self.assertEqual(result['status'], 'unidentifiable_no_known_pairs')
        self.assertIsNone(result['beta64'])
        self.assertEqual(result['before']['NLL'], 0.)
        self.assertIsNone(result['before']['known_supervised_window_NLL_description'])

    def test_extreme_logits_stable_BCE_derivative_and_finite_large_intercept(self):
        self.assertEqual(runtime.bce64(1e6, 0), 1e6)
        self.assertEqual(runtime.bce64(-1e6, 1), 1e6)
        self.assertLess(runtime.residual64(40., 1), 0.)
        self.assertGreater(runtime.residual64(-40., 0), 0.)
        result = runtime.fit_intercept(windows(raw=1000.))
        self.assertEqual(result['beta64'], -1000.)
        self.assertTrue(math.isfinite(result['after_fit64']['NLL']))
        self.assertEqual(result['apply_beta32'], -1000.)
        self.assertEqual(result['after_projected_beta32_sum64']['NLL'], result['after_apply32']['NLL'])

    def test_projection_and_actual_FP32_addition_are_separate_from_fit64_and_Torch_acceptance(self):
        result = runtime.fit_intercept(windows(positive=750))
        self.assertEqual(result['apply_beta32'], runtime.float32(result['beta64']))
        self.assertIn('FP64_original_logits_plus_projected_beta32', result['after_projected_beta32_sum64']['arithmetic'])
        self.assertEqual(result['after_apply32']['arithmetic'], 'FP64_metrics_after_FP32_logit_addition')
        self.assertEqual(set(result['NLL_numeric_drift']), {'beta32_projection_vs_beta64',
            'FP32_addition_vs_projected_beta32_sum64', 'FP32_addition_vs_beta64'})
        self.assertFalse(result['after_apply32']['actual_Torch_probability_or_cost_gate_verified'])
        self.assertIn('not_actual_Torch_FP32', result['after_apply32']['acceptance_rule'])

    def test_constant_FP32_addition_has_no_order_reversal_but_can_create_ties(self):
        data = [dict(window_uid='window_'+str(index), logits=[-1., 0., 1.], labels=[0, None, 1])
                for index in range(runtime.WINDOWS)]
        prepared, _ = runtime.prepare_windows(data)
        result = runtime.rank_audit(prepared, runtime.float32(1e8))
        self.assertEqual(result['order_reversals'], 0)
        self.assertEqual(result['windows_with_new_FP32_ties'], 1000)
        self.assertEqual(result['adjacent_distinct_logits_collapsed_to_FP32_ties'], 2000)
        self.assertFalse(result['strict_rank_equality_claim'])

    def test_zero_wrapper_returns_same_tensor_nonzero_only_adds_buffer_weights_unchanged(self):
        model = FixtureModel()
        before = deepcopy(model.weights[0].value)
        original_parameters = list(model.parameters())
        zero = runtime.wrap_intercept(model, 0., FIXTURE_TORCH)
        output = zero(object())
        self.assertIs(output, model.output)
        self.assertEqual(struct.pack('<f', output.value[0]), struct.pack('<f', -0.))
        self.assertEqual(list(zero.parameters()), original_parameters)
        self.assertEqual(model.weights[0].value, before)
        self.assertTrue(all(not parameter.requires_grad for parameter in zero.parameters()))
        self.assertEqual(set(zero.buffers), {'intercept_beta32'})
        self.assertFalse(zero.training)
        self.assertFalse(model.training)
        zero.train(True)
        self.assertFalse(zero.training)
        self.assertFalse(model.training)
        shifted = runtime.wrap_intercept(model, runtime.float32(.25), FIXTURE_TORCH)
        self.assertEqual(shifted(object()).value, [.25, 1.25, -.75])
        self.assertEqual(model.weights[0].value, before)
        self.assertEqual(model.calls, 2)
        self.assertFalse(shifted.buffers['intercept_beta32'].requires_grad)

    def test_invalid_window_identity_FP32_label_and_count_rejected_no_silent_drop(self):
        data = windows()
        with self.assertRaises(ValueError):
            runtime.fit_intercept(data[:-1])
        duplicate = deepcopy(data)
        duplicate[1]['window_uid'] = duplicate[0]['window_uid']
        with self.assertRaises(ValueError):
            runtime.fit_intercept(duplicate)
        for logits, labels in (([.1], [1]), ([float('inf')], [0]), ([0.], [True]), ([0.], [2]), ([0.], [])):
            broken = deepcopy(data)
            broken[0].update(logits=logits, labels=labels)
            with self.assertRaises(ValueError):
                runtime.fit_intercept(broken)
        self.assertEqual(data, windows())


if __name__ == '__main__':
    unittest.main()
