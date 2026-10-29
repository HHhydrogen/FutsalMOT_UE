"""新单臂入口与20步准入的纯元数据合同；不加载实际输入或执行SGD。"""
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import r_eligibility_train as train
import validate_r_eligibility_numeric as gate
import r_eligibility_training_runtime as rt
import r_candidate_eligibility_method as method
from test_r_candidate_eligibility_method import fixture


def bound_context():
    bindings = {}
    for i in range(4):
        window, side = fixture('w'+str(i)); bindings[window['window_uid']] = method.bind_window_mask(window, side)
    return dict(table=dict(real=[dict(window_uid='w'+str(i)) for i in range(4)], synthetic=[dict(window_uid='S-untouched')]),
        eligibility_bindings=bindings, diagnostic_only_mask_override_authorized=True)


class EntryContracts(unittest.TestCase):
    def test_fixed20_updates60_R8_S_no_hidden_warmup(self):
        plan = train.numeric_plan(); cases = gate.cases()
        self.assertEqual(len(cases), 10); self.assertEqual(2*len(cases), plan['diagnostic_optimizer_updates'])
        self.assertEqual(sum(6 for _ in cases), plan['diagnostic_R_windows'])
        self.assertEqual(sum(2*(x['regime'] == 'RS') for x in cases), plan['diagnostic_S_windows'])
        self.assertEqual(plan['empty_stress_optimizer_state'], dict(step=7, exp_avg=.125, exp_avg_sq=.25))
        self.assertEqual({x['regime'] for x in cases if x['variant'] == 'empty_stress'}, {'R'})
        self.assertEqual(plan['formal_optimizer_updates'], 0)

    def test_formal_cuda_actualmask_only_and_diagnostic_finite_plan(self):
        cfg = dict(numeric_plan=train.numeric_plan())
        train.validate_request(cfg, None, 'cuda:0', 'actual_mask')
        for device, variant, count, capture in [('cpu', 'actual_mask', None, None), ('cuda:0', 'alltrue_original_BCE', None, None),
                ('cuda:0', 'actual_mask', None, {}), ('cpu', 'actual_mask', 2, None)]:
            with self.assertRaises(ValueError): train.validate_request(cfg, count, device, variant, capture)
        bad = deepcopy(cfg); bad['numeric_plan']['diagnostic_optimizer_updates'] = 8
        with self.assertRaises(ValueError): train.validate_request(bad, 1, 'cpu', 'actual_mask')

    def test_diagnostic_override_explicit_virtual_source_original_labels_order_unchanged(self):
        for variant, expected in [('alltrue_original_BCE', True), ('empty_stress', False)]:
            ctx = bound_context(); original = deepcopy(ctx); definitions = train.prepare_variant(ctx, variant)
            self.assertEqual(len(definitions), 3); self.assertEqual(ctx['table'], original['table'])
            self.assertEqual(ctx['eligibility_bindings']['w3'], original['eligibility_bindings']['w3'])
            for i in range(3):
                b = ctx['eligibility_bindings']['w'+str(i)]; old = original['eligibility_bindings']['w'+str(i)]
                self.assertEqual(b['all_scoring_eligible'], [expected]*3)
                self.assertEqual(b['known_labels'], old['known_labels']); self.assertEqual(b['known_candidate_UIDs'], old['known_candidate_UIDs'])
                self.assertEqual(b['numeric_only_override']['original_sidecar_sha256'], old['sidecar_sha256'])
                self.assertFalse(b['numeric_only_override']['source_files_changed']); method.checked_binding(b)
        ctx = bound_context(); before = deepcopy(ctx)
        self.assertEqual(train.prepare_variant(ctx, 'actual_mask'), []); self.assertEqual(ctx, before)
        ctx['diagnostic_only_mask_override_authorized'] = False
        with self.assertRaises(ValueError): train.prepare_variant(ctx, 'empty_stress')

    def test_nonzero_moment_fixture_constructs_state_without_step(self):
        class FakeTorch:
            float32 = 'float32'
            tensor = staticmethod(lambda value, dtype: ('scalar', value, dtype))
            full_like = staticmethod(lambda parameter, value: ('like', parameter, value))
        optimizer = SimpleNamespace(state={}, param_groups=[dict(params=['p0', 'p1'], lr=.001, weight_decay=.0001, amsgrad=False)])
        train.initialize_empty_stress_optimizer(optimizer, FakeTorch)
        self.assertEqual(optimizer.state['p0']['step'], ('scalar', 7., 'float32'))
        self.assertEqual(optimizer.state['p1']['exp_avg'], ('like', 'p1', .125))
        self.assertEqual(optimizer.state['p1']['exp_avg_sq'], ('like', 'p1', .25))
        with self.assertRaises(ValueError): train.initialize_empty_stress_optimizer(optimizer, FakeTorch)

    def test_effective_counts_independent_of_candidate_method_totals(self):
        ctx = bound_context(); batch = dict(real=[dict(eligibility_binding=ctx['eligibility_bindings']['w'+str(i)]) for i in range(3)])
        counts = gate.expected_effective_counts(batch)
        self.assertEqual(counts['R_effective_known_pairs'], 3); self.assertEqual(counts['R_effective_positive_pairs'], 3)
        self.assertEqual(counts['R_effective_negative_pairs'], 0); self.assertEqual(counts['R_masked_out_known_pairs'], 3)
        self.assertEqual(counts['R_scoring_eligible_unknown_pairs'], 3); self.assertEqual(counts['R_effective_unknown_pairs'], 0)

    def test_preflight_accepts_future_path_without_self_referential_receipt_SHA(self):
        with tempfile.TemporaryDirectory() as temp:
            exp = Path(temp); output = exp/'new-attempt'
            cfg = dict(numeric_plan=train.numeric_plan(), numeric_admission=dict(path=str(output/'receipt.json')))
            with patch.object(rt, 'validate_protocol', lambda p: cfg), patch.object(rt, 'physical', lambda p: Path(p)), patch.object(rt, 'EXPERIMENT', exp), patch.object(rt, 'sha', lambda p: 'a'*64):
                _, preflight = gate.preflight(exp/'protocol.json', output, 'a'*64)
                self.assertEqual(preflight['diagnostic_optimizer_updates'], 20)
                self.assertFalse(output.exists())
                with self.assertRaises(ValueError): gate.preflight(exp/'protocol.json', output, 'b'*64)

    def test_formal_numeric_gate_requires_new_learningroot_and_budget(self):
        receipt = dict(status=train.NUMERIC_STATUS, protocol_sha256='p'*64, formal_optimizer_updates=0,
            actual_diagnostic_optimizer_updates=20, diagnostic_R_windows=60, diagnostic_S_windows=8,
            all_groups_equal=True, actual_CPU_and_CUDA_numeric_verified=True, full_record_contract_verified=True, test_read=False)
        root = dict(numeric_validation=dict(path='future-receipt', sha256='a'*64)); calls = []
        with patch.object(rt, 'validate_training_admission', lambda p, cfg: calls.append((p, cfg)) or root), \
             patch.object(rt, 'read_ref', lambda reference: receipt), patch.object(rt, 'sha', lambda p: 'p'*64):
            self.assertEqual(train.check_numeric_admission('config', {}), receipt)
            self.assertEqual(len(calls), 1)
            receipt['actual_diagnostic_optimizer_updates'] = 8
            with self.assertRaises(ValueError): train.check_numeric_admission('config', {})

    def test_each_successful_group_proof_is_durable_without_final_receipt_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)/'actual_mask/cpu/RS/recorded'; run.mkdir(parents=True)
            (run/'run_receipt.json').write_text('{"status":"diagnostic_only"}', encoding='utf-8')
            (run/'steps.jsonl').write_text('{"step":1}\n', encoding='utf-8')
            case = dict(variant='actual_mask', device='cpu', regime='RS')
            group = dict(manual_updates=1, recorded_updates=1, R_windows=6, S_windows=2, per_parameter_gradients_exact=True,
                all_RNG_exact=True, loss_model_AdamW_exact=True, checkpoints=[dict(completed_updates=0), dict(completed_updates=1)])
            def writer(path, value):
                with path.open('x', encoding='utf-8') as stream: stream.write(rt.canonical(value))
            with patch.object(rt, 'physical', lambda p: Path(p)):
                reference = gate.persist_group_audit('p'*64, case, group, run, writer)
                proof = json.loads(Path(reference['path']).read_text(encoding='utf-8'))
                self.assertEqual(reference['sha256'], rt.sha(Path(reference['path'])))
                self.assertEqual(proof['actual_diagnostic_optimizer_updates'], 2)
                self.assertEqual(proof['diagnostic_R_windows'], 6); self.assertEqual(proof['diagnostic_S_windows'], 2)
                self.assertTrue(all(proof['checks'].values())); self.assertFalse(proof['automatic_resume_or_replay'])
                self.assertEqual(proof['record_steps']['sha256'], rt.sha(run/'steps.jsonl'))
                self.assertFalse((Path(temp)/'receipt.json').exists())
                with self.assertRaises(FileExistsError): gate.persist_group_audit('p'*64, case, group, run, writer)
                partial = deepcopy(group); partial['per_parameter_gradients_exact'] = False
                with self.assertRaises(ValueError): gate.persist_group_audit('p'*64, case, partial, run, writer)


if __name__ == '__main__': unittest.main()
