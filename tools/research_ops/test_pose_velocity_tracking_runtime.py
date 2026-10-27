"""仅CPU夹具：513矩阵、来源不改写、退出准入、模型路由和输入计账。"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pose_velocity_tracking_runtime as rt
from pose_velocity_tracking_adapter import velocity_input
from pose_velocity_tracking_jobs import InputAuditProxy, input_metadata, instrument_input


def sources():
    return {s: dict(sequence=s, frames=750 if s in rt.OLD else 451,
                    cache=dict(path='fixture:' + s, sha256='1'*64), preserved={'original': True})
            for s in list(rt.OLD) + list(rt.EXTERNAL) + list(rt.SEVEN)}


def training_fixture():
    matrix = [dict(fold=f, seed=s, group=g) for f in rt.FOLDS for s in rt.SEEDS
              for g in ('T_R', 'T_RS', 'T_shuffle_RS')]
    refs = {key: dict(path=key, sha256=key) for key in ('protocol', 'done', 'budget', 'state')}
    cfg = dict(learning_protocol=refs['protocol'], learning_complete=refs['done'],
               learning_budget=refs['budget'], learning_controller_state=refs['state'])
    documents = dict(done=dict(status='complete27_bounded_velocity_training_budget_records_and_exit_verified',
        protocol=refs['protocol'], budget=refs['budget'], controller_state=refs['state'], training_processes_absent=True),
        budget=dict(status='complete27_bounded_velocity_actual_budget_full_records_and_exit_verified',
            protocol=refs['protocol'], control_state=refs['state'], training_processes_absent=True,
            complete_checkpoints_read_back=567, actual_totals=dict(updates=27000, R_windows=81000, S_windows=18000)),
        state=dict(status='complete27_bounded_velocity_training_wait_independent_audit_tracking', active=None,
                   protocol_sha256='protocol', completed_train=matrix))
    return cfg, documents, SimpleNamespace(expected_matrix=lambda: matrix)


class VelocityTrackingRuntimeTests(unittest.TestCase):
    def test_513_complete_new450_reference63_no_other_fold_or_pose_case(self):
        source = sources(); jobs = rt.tracking_matrix(source)
        self.assertEqual(Counter(j['kind'] for j in jobs), {'new': 450, 'reference': 63})
        self.assertEqual(len({j['job_id'] for j in jobs}), 513)
        self.assertEqual(jobs, rt.tracking_matrix(source))
        for job in jobs:
            self.assertNotIn(job['sequence'], [q for q, fold in rt.OLD.items() if fold != job['fold']])
            if job['kind'] == 'reference':
                self.assertIn(job['sequence'], rt.SEVEN)
                self.assertEqual((job['group'], job['pose_enabled']), ('same_capacity_motion_RS', False))
            else:
                self.assertIn((job['group'], job['pose_enabled']), rt.CASES)
        for fold in rt.FOLDS:
            for seed in rt.SEEDS:
                self.assertEqual(sum(j['kind'] == 'new' and j['fold'] == fold and j['seed'] == seed for j in jobs), 50)
        with self.assertRaises(ValueError): rt.tracking_matrix(dict(source, **{'SNMOT-116': {}}))

    def test_sources_keep_original_values_and_deepcopy(self):
        source = sources()
        old = dict(sources={q: source[q] for q in list(rt.OLD) + list(rt.EXTERNAL)})
        seven = dict(sources={q: source[q] for q in rt.SEVEN})
        before = deepcopy((old, seven))
        with patch.object(rt, '_source_configs', return_value=(old, seven)):
            result = rt.sources_from({})
        self.assertEqual(result, source)
        result['SNMOT-060']['preserved']['original'] = False
        self.assertEqual((old, seven), before)

    def test_tracking_registry_validation_reads_only_public_receipts(self):
        source = sources(); cfg = dict(registries={})
        old = dict(sources={q: source[q] for q in list(rt.OLD) + list(rt.EXTERNAL)}, registry={'path': 'private_old_GT'})
        seven = dict(sources={q: source[q] for q in rt.SEVEN}, registry={'path': 'private_seven_GT'})
        receipts = {}
        for key, value, count in (('old_five', old, 1353), ('seven', seven, 2337)):
            cfg['registries'][key] = dict(registry=value['registry'], receipt={'path': key})
            receipts[key] = dict(registry=value['registry'], sources=value['sources'], event_count=count,
                tracking_results_read=False, contains_GT_coordinates=False, test_read=False)
        def public_only(reference):
            self.assertNotIn(reference['path'], ('private_old_GT', 'private_seven_GT'))
            return reference['path']
        with patch.object(rt, '_source_configs', return_value=(old, seven)), \
             patch.object(rt, 'checked', side_effect=public_only), patch.object(rt, 'read', side_effect=lambda p: receipts[p]):
            rt.validate_registry_receipts(cfg)
            receipts['old_five']['contains_GT_coordinates'] = True
            with self.assertRaises(ValueError): rt.validate_registry_receipts(cfg)

    def test_learning_complete_requires_27_exit_budget_and_exact_matrix(self):
        cfg, docs, loader = training_fixture()
        with patch.object(rt, 'checked', side_effect=lambda r: r['path']), \
             patch.object(rt, 'read', side_effect=lambda p: docs[p]):
            rt.validate_learning_complete(cfg, loader)
            docs['state']['active'] = {'child_pid': 1}
            with self.assertRaises(ValueError): rt.validate_learning_complete(cfg, loader)
            docs['state']['active'] = None
            docs['budget']['training_processes_absent'] = False
            with self.assertRaises(ValueError): rt.validate_learning_complete(cfg, loader)

    def test_model_loader_new_identity_and_reference_seven_route(self):
        source = sources(); matrix = rt.tracking_matrix(source)
        job = next(j for j in matrix if j['kind'] == 'new' and j['group'] == 'T_RS')
        entry = dict(**{k: job[k] for k in ('fold', 'seed', 'group')}, path='/run', receipt_sha256='ok', complete_sha256='ok')
        cfg = dict(tracking_matrix=matrix, learning_protocol={'path': '/protocol', 'sha256': 'p'}, learning_controller_state={'path': 'state'})
        binding = dict(**{k: job[k] for k in ('fold', 'seed', 'group')}, protocol_sha256='p')
        calls = []
        loader = SimpleNamespace(complete_model=lambda config, run: (None, None, 'model', 'adapter', binding))
        dep = [dict(training_control='/old_control', training_protocol={'path': '/old_protocol'})] + [None]*7
        def reference_loader(config, run):
            calls.append((config, run))
            return None, None, 'old_model', 'old_adapter', dict(fold='game4', seed=20261024, method='motion_residual', pool='balanced')
        dep[3] = SimpleNamespace(complete_model=reference_loader)
        with patch.object(rt, 'checked', side_effect=lambda r: r['path']), patch.object(rt, 'sha', return_value='ok'), \
             patch.object(rt, 'read', return_value=dict(completed_train=[entry])):
            self.assertEqual(rt.load_model(cfg, dep, loader, job), ('model', 'adapter', binding, True))
            reference = next(j for j in matrix if j['kind'] == 'reference')
            result = rt.load_model(cfg, dep, loader, reference)
            self.assertEqual(result[:2], ('old_model', 'old_adapter'))
            self.assertFalse(result[-1]); self.assertIn('balanced/motion_residual/training', str(calls[0][1]).replace('\\', '/'))
            binding['group'] = 'T_shuffle_RS'
            with self.assertRaises(ValueError): rt.load_model(cfg, dep, loader, job)

    def test_actual_input_counter_observes_195_finite_and_off_gate(self):
        class Adapter:
            def transform_pair(self, history, candidate): return [float(i) for i in range(194)] + [.7]
        record = dict(uid='fixture', bbox_xywh_px=[0., 0., 1., 1.], score=.9,
            xy_px=[[0., 0.]]*17, geometry_valid=[True]*17, timestamp_sec=0., image_wh=[10, 10])
        audit = dict(adapter_transform_pair_calls=0, feature_calls=0, observed_feature_dims=[],
                     all_finite=True, pose_off_final_gate_zero=True, actual_feature_checks_performed=False)
        proxy = InputAuditProxy(Adapter(), audit); helper = instrument_input(velocity_input, audit)
        result = helper(proxy, [record], record, False)
        self.assertEqual(result[:194], [float(i) for i in range(194)])
        self.assertEqual(result[-1], 0.)
        self.assertEqual(audit['adapter_transform_pair_calls'], audit['feature_calls'])
        self.assertEqual(audit['observed_feature_dims'], [195]); self.assertTrue(audit['actual_feature_checks_performed'])
        with self.assertRaises(ValueError): instrument_input(lambda *a: [0.]*194+[float('inf')], audit)(proxy, [], record)

    def test_reference_metadata_does_not_claim_new_T_gate_zero(self):
        new, new_description = input_metadata('new')
        reference, old_description = input_metadata('reference')
        self.assertTrue(new['pose_off_final_gate_zero'])
        self.assertEqual(new_description, 'same195_input_only_final_quality_gate_zero_own_motion_base')
        self.assertIsNone(reference['pose_off_final_gate_zero'])
        self.assertFalse(reference['actual_feature_checks_performed'])
        self.assertEqual(reference['input_kind'], 'original_motion_residual_raw')
        self.assertEqual(old_description, 'not_applicable_original_motion_residual_has_no_Pose_branch')
        with self.assertRaises(ValueError): input_metadata('unknown')

    def test_final_test_paths_rejected(self):
        for path in ('D:/sealed/test/cache.json', 'D:/data/SNMOT-116/cache.json', 'D:/data/snmot_0187/cache.json'):
            with self.assertRaises(ValueError): rt.safe(path)


if __name__ == '__main__':
    unittest.main()
