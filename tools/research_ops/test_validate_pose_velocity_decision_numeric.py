"""数值准入候选的纯CPU合同夹具；不签实际模型准入，不导入Torch。"""
from copy import deepcopy
import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_pose_velocity_decision_numeric as numeric
import pose_velocity_decision_probe as probe


BRANCHES = ('own_base', 'original_q', 'q1')


def record(uid, time):
    return dict(uid=uid, bbox_xywh_px=[1., 2., 3., 4.], score=.8, xy_px=[[1., 2.]]*17,
                geometry_valid=[True]*17, timestamp_sec=time, image_wh=[100, 100],
                GT_identity='不得输入', GT_Pose='不得输入')


def event():
    return dict(history_UIDs=[['a', 'b', 'c'], ['a', 'b', 'c']], candidate_UIDs=['p', 'n'],
        enough_history=[True, False], motion_gate=[[True, True], [True, False]],
        enabled=[[False, True], [False, False]], active_rows=[True, False], scored_locations=[[0, 0], [0, 1]])


class NumericAdmissionContractTests(unittest.TestCase):
    def test_manual_public_input_preserves_native_subset_order_and_rejects_GT(self):
        source = {uid: record(uid, time) for uid, time in [('a', 0.), ('b', .1), ('c', .2), ('p', .3), ('n', .3)]}
        class Adapter:
            def transform_pair(self, history, candidate):
                self_last = candidate['uid']
                return [1. if self_last == 'p' else 2.]*194+[.5]
        guarded = numeric.PublicAdapter(Adapter())
        locations, vectors, native, subset = numeric.manual_inputs(event(), source, guarded)
        self.assertEqual(locations, [(0, 0), (0, 1)]); self.assertEqual(native, [(0, 1)])
        self.assertEqual(subset, [vectors[1]]); self.assertEqual(guarded.calls, 2)
        with self.assertRaises(ValueError): guarded.transform_pair([source['a']], source['p'])
        source['c']['timestamp_sec'] = .3
        with self.assertRaises(ValueError): numeric.manual_inputs(event(), source, guarded)

    def test_empty_boundary_returns_empty_scores_without_model_or_old_fill(self):
        original = event(); empty = numeric.empty_boundary(original)
        self.assertEqual(original, event()); self.assertEqual(empty['scored_locations'], [])
        self.assertEqual(numeric.manual_inputs(empty, {}, None), ([], [], [], []))
        values = numeric.manual_scores(None, [], None, BRANCHES)
        self.assertEqual(values['logits'], {key: [] for key in BRANCHES})
        self.assertEqual(values['raw_head'], []); self.assertTrue(values['full_forward_equal_original_q'])

    def test_exact_all_fields_comparison_rejects_missing_or_numeric_change(self):
        expected = numeric.manual_scores(None, [], None, BRANCHES)
        numeric.compare_scores(expected, deepcopy(expected))
        broken = deepcopy(expected); broken.pop('raw_head')
        with self.assertRaises(ValueError): numeric.compare_scores(expected, broken)
        broken = deepcopy(expected); broken['input_195_sha256'] = 'unbound'
        with self.assertRaises(ValueError): numeric.compare_scores(expected, broken)

    def test_q0_retains_raw_nonzero_residual_not_division_or_zero_fill(self):
        original = dict(raw_head=[.8], residual=[.3], q=[.5], gated_residual=[.15],
                        logits=dict(own_base=[.2], original_q=[.35], q1=[.5]))
        zero = deepcopy(original); zero.update(q=[0.], gated_residual=[0.])
        zero['logits']['original_q'] = [.2]
        evidence = numeric.verify_q0(original, zero)
        self.assertEqual(evidence['nonzero_raw_residual_pairs'], 1)
        self.assertTrue(evidence['gate_override_numeric_boundary_not_observed_quality'])
        zero['residual'] = [0.]
        with self.assertRaises(ValueError): numeric.verify_q0(original, zero)

    def test_original_assignment_is_called_directly_with_every_branch(self):
        calls = []
        class Cost:
            def tolist(self): return [[.25]]
        class Geo:
            def choose_cost(self, e, branch, np, torch):
                calls.append(('cost', branch, e['scored_locations'])); return Cost(), .8
        def assignment(cost, thresh):
            calls.append(('assign', thresh)); return [[0, 0]], [], []
        scores = dict(logits={b: [.2] for b in BRANCHES})
        result = numeric.manual_decisions(event(), [(0, 1)], scores, Geo(), None, None, assignment, BRANCHES)
        self.assertEqual(len(calls), 6)
        self.assertEqual([x[1] for x in calls[::2]], list(BRANCHES))
        self.assertEqual(result['q1']['assignment'], dict(matches=[[0, 0]], unmatched_rows=[], unmatched_columns=[]))

    def test_score2_gate_rejects_same_PID_GT_or_scored_difference(self):
        task = dict(source_job_id='frozen_trace_fixture', event_number=0, group='T_RS')
        serial = dict(all_gated={'input_195_sha256': 'same', 'decisions': 'fixture'}, enabled_native={'logits': []},
                      GT_used_for_scoring=False)
        messages = [dict(status='complete', pid=pid, result=dict(task, scored=deepcopy(serial),
            source_validation_GT_registry_read=True, GT_annotations_loaded=True,
            posthoc_GT_labels_loaded=False, current_source_posthoc_GT_loaded=False,
            GT_used_for_scoring=False, GT_free_inputs=True, CUDA_initialized=False, numeric_threads=1),
            parameters_buffers_adapters_unchanged=True, RNG_unchanged=True, cold_warm_scored_equal=True) for pid in (11, 12)]
        numeric.verify_spawn_messages(messages, serial, task, 99)
        bad = deepcopy(messages); bad[1]['pid'] = 11
        with self.assertRaises(ValueError): numeric.verify_spawn_messages(bad, serial, task, 99)
        bad = deepcopy(messages); bad[1]['result']['GT_annotations_loaded'] = False
        with self.assertRaises(ValueError): numeric.verify_spawn_messages(bad, serial, task, 99)
        bad = deepcopy(messages); bad[1]['result']['scored']['all_gated']['input_195_sha256'] = 'different'
        with self.assertRaises(ValueError): numeric.verify_spawn_messages(bad, serial, task, 99)
        for field, value in (('posthoc_GT_labels_loaded', True), ('GT_used_for_scoring', True), ('GT_free_inputs', False)):
            bad = deepcopy(messages); bad[1]['result'][field] = value
            with self.assertRaises(ValueError): numeric.verify_spawn_messages(bad, serial, task, 99)
        bad = deepcopy(messages); bad[1]['result']['scored']['GT_used_for_scoring'] = True
        with self.assertRaises(ValueError): numeric.verify_spawn_messages(bad, serial, task, 99)

    def test_real_proof_builders_include_all_six_GT_fields_without_fixture_defaults(self):
        # 直接检查实际返回字典的构造AST，避免夹具默认字段掩盖真实proof漏写。
        fields = ('source_validation_GT_registry_read', 'GT_annotations_loaded', 'posthoc_GT_labels_loaded',
                  'current_source_posthoc_GT_loaded', 'GT_used_for_scoring', 'GT_free_inputs')
        cases = ((numeric.execute, 'schema', 'velocity_decision_actual_CPU_numeric_admission_v1'),
                 (numeric.spawn_admission, 'status', 'complete_actual_serial_vs_two_spawn_score_workers_exact'),
                 (numeric._spawn_score_entry, 'status', 'complete'))
        for function, marker, expected in cases:
            tree = ast.parse(inspect.getsource(function))
            candidates = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'dict'
                and any(k.arg == marker and isinstance(k.value, ast.Constant) and k.value.value == expected for k in node.keywords)]
            self.assertEqual(len(candidates), 1)
            actual = {k.arg: ast.literal_eval(k.value) for k in candidates[0].keywords if k.arg in fields}
            self.assertEqual(set(actual), set(fields))
            probe.validate_GT_access(actual, no_posthoc=True)
            for field in fields:
                missing = dict(actual); missing.pop(field)
                with self.assertRaises(ValueError): probe.validate_GT_access(missing, no_posthoc=True)


if __name__ == '__main__':
    unittest.main()
