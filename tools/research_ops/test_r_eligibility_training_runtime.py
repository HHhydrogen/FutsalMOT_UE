"""训练适配候选的纯合同夹具；不打开实际来源、不导入Torch或执行优化。"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import r_eligibility_training_runtime as rt
import r_candidate_eligibility_method as method
from test_r_candidate_eligibility_method import fixture


def config():
    return dict(schema='r_candidate_eligibility_recorded_training_protocol_v1', training_matrix=rt.expected_matrix(), parameters=deepcopy(rt.PARAMETERS),
        approved_by='root', training_authorized=True, tracking_authorized=False, test116187_sealed=True,
        source_training_protocol=dict(path=str(rt.SOURCE_PROTOCOL), sha256=rt.SOURCE_PROTOCOL_SHA),
        source_training_complete_root=dict(path=str(rt.SOURCE_COMPLETE_ROOT), sha256=rt.SOURCE_COMPLETE_ROOT_SHA),
        source_training_audit=dict(path=str(rt.SOURCE_AUDIT), sha256=rt.SOURCE_AUDIT_SHA),
        mask_inputs={f: dict(path='fixture/'+f, sha256='a'*64) for f in rt.FOLDS}, selected_R_bank_root=dict(path='original-bank', sha256='b'*64))


def pure_batch():
    bindings = {}; cached = []; rr = []
    for index in range(3):
        window, side = fixture('w'+str(index)); bound = method.bind_window_mask(window, side); bindings[bound['window_uid']] = bound
        cached.append(dict(window_uid=bound['window_uid'], x=object(), labels=object(), candidate_pairs=3, known_pairs=2))
        rr.append(dict(window_uid=bound['window_uid'], candidate_pairs=3, labelled_pairs=2, epoch=0))
    synthetic = [dict(window_uid='s0', x=object(), labels=object(), candidate_pairs=2, known_pairs=2)]
    return dict(index=0, r=rr, s=[dict(window_uid='s0', candidate_pairs=2, labelled_pairs=2)], real=cached, synthetic=synthetic), bindings


class PureContracts(unittest.TestCase):
    def test_fixed_matrix_only_R_objective_and_explicit_source_identity(self):
        cfg = config(); rt.validate_matrix(cfg); self.assertEqual(len(cfg['training_matrix']), 18)
        self.assertEqual(rt.EXPERIMENT.name, 'r_candidate_eligibility_a01')
        self.assertEqual(cfg['parameters']['lr'], .001); self.assertFalse(cfg['parameters']['epoch_augmentation'])
        for change in (lambda x: x['parameters'].update(R_per_step=2), lambda x: x['parameters'].update(S_alpha=1.),
                       lambda x: x['parameters'].update(epoch_augmentation=True), lambda x: x.update(training_authorized=False),
                       lambda x: x['source_training_protocol'].update(sha256='0'*64), lambda x: x['mask_inputs'].pop('game4')):
            bad = deepcopy(cfg); change(bad)
            with self.assertRaises(ValueError): rt.validate_matrix(bad)

    def test_1000_unique_bindings_exact_match_and_all_empty_fold_rejected(self):
        pool = {}; sidecars = []
        for index in range(1000):
            window, side = fixture('w'+str(index)); pool[window['window_uid']] = window; sidecars.append(side)
        result = rt.bind_sidecars(pool, sidecars); self.assertEqual(len(result), 1000)
        self.assertEqual(result, rt.bind_sidecars(pool, sidecars, supplied_bindings=list(result.values())))
        bad = deepcopy(sidecars); bad[1] = deepcopy(bad[0])
        with self.assertRaises(ValueError): rt.bind_sidecars(pool, bad)
        supplied = deepcopy(list(result.values())); supplied[0]['known_labels'][0] = 0
        with self.assertRaises(ValueError): rt.bind_sidecars(pool, sidecars, supplied_bindings=supplied)
        for side in sidecars: side.update(active=False, enabled=[False]*3, scoring_eligible=[False]*3)
        with self.assertRaises(ValueError): rt.bind_sidecars(pool, sidecars)

    def test_batch_attaches_new_binding_without_overwriting_cache_or_S(self):
        batch, bindings = pure_batch(); result = rt.attach_bindings(batch, bindings)
        self.assertIsNot(result['real'], batch['real']); self.assertIs(result['synthetic'], batch['synthetic'])
        self.assertIs(result['r'], batch['r']); self.assertIs(result['s'], batch['s'])
        for old, new in zip(batch['real'], result['real']):
            self.assertNotIn('eligibility_binding', old); self.assertIs(old['x'], new['x']); self.assertIs(old['labels'], new['labels'])
            self.assertEqual(old['candidate_pairs'], new['candidate_pairs']); self.assertEqual(old['known_pairs'], new['known_pairs'])
            self.assertIs(new['eligibility_binding'], bindings[old['window_uid']])
        bad = dict(batch, real=[dict(batch['real'][0], known_pairs=1), *batch['real'][1:]])
        with self.assertRaises(ValueError): rt.attach_bindings(bad, bindings)

    def test_both_domain_interfaces_keep_original_S_and_masked_R_tuple(self):
        raw, bindings = pure_batch(); batch = rt.attach_bindings(raw, bindings); calls = []
        ctx = dict(eligibility_bindings=bindings, numeric=SimpleNamespace(domain_loss=lambda model, windows: calls.append((model, windows)) or 'S-original'))
        with patch.object(method, 'masked_real_domain_BCE', lambda model, windows, masks: ('R-mask', dict(mask_objects=masks))) as _:
            loss, accounting = rt.r_loss(ctx, 'model', batch['real'])
        self.assertEqual(loss, 'R-mask'); self.assertEqual(len(accounting['mask_objects']), 3)
        self.assertEqual(rt.s_loss(ctx, 'model', batch['synthetic']), 'S-original')
        self.assertIs(calls[0][1], raw['synthetic'])

    def test_batched_source_exposure_order_delegation_and_model_initialization(self):
        raw, bindings = pure_batch(); calls = []
        old = SimpleNamespace(batches=lambda ctx, regime, limit: calls.append(('batches', regime, limit)) or iter([raw]),
            batch=lambda ctx, index, regime: calls.append(('batch', index, regime)) or raw,
            new_model=lambda ctx, seed, device: calls.append(('new_model', seed, device)) or 'original-model')
        ctx = dict(eligibility_oldrt=old, eligibility_bindings=bindings, regime='RS')
        self.assertEqual(list(rt.batches(ctx, limit=1))[0]['r'], raw['r'])
        self.assertEqual(rt.batch(ctx, 0)['s'], raw['s'])
        self.assertEqual(rt.new_model(ctx, seed=20261024, device='cpu'), 'original-model')
        self.assertEqual(calls, [('batches', 'RS', 1), ('batch', 0, 'RS'), ('new_model', 20261024, 'cpu')])

    def test_independent_extra_spec_and_model_id_not_CE_or_static_control_claim(self):
        cfg = config(); original_extra = dict(schema='old-schema', normalizer=dict(mean=[1.], scale=[2.]), use_pose=False, epoch_augmentation=False)
        original_spec = dict(binding=dict(initialization_sha256='i'*64), runtime=dict(actual_dtype='float32'))
        ctx = dict(eligibility_cfg=cfg, eligibility_protocol_sha256='p'*64, fold='game4', seed=20261024, regime='RS',
            eligibility_oldrt=SimpleNamespace(extra=lambda c: original_extra, spec=lambda *args, **kwargs: original_spec))
        with patch.object(rt, 'sha', lambda path: 'e'*64):
            extra = rt.extra(ctx); spec = rt.spec(ctx, 'model')
        self.assertEqual(extra['schema'], 'r_candidate_eligibility_strongmotion_method_state_v1')
        self.assertEqual(extra['normalizer'], original_extra['normalizer'])
        self.assertIn('conditional_on_fresh_CPU_CUDA', extra['matched_control_reuse_status'])
        self.assertEqual(extra['record_extension_schema'], 'R_candidate_scoring_eligibility_record_extension_v1')
        self.assertEqual(spec['binding']['record_extension_schema'], extra['record_extension_schema'])
        self.assertEqual(spec['runtime']['record_extension_schema'], extra['record_extension_schema'])
        self.assertEqual(spec['binding']['mask_input_sha256'], cfg['mask_inputs']['game4']['sha256'])
        self.assertEqual(spec['binding']['method_state_sha256'], rt.digest(extra))
        self.assertNotIn('R_objective', original_spec['binding']); self.assertEqual(original_extra['schema'], 'old-schema')
        mid = rt.model_id('p'*64, 'game4', 20261024, 'R')
        self.assertEqual(len(mid), 24); self.assertNotEqual(mid, rt.model_id('q'*64, 'game4', 20261024, 'R'))

    def test_formal_admission_requires_future_root_numeric20_and_independent_inputs(self):
        config_path = Path('D:/projects/FutsalMOT_Research/fixture/protocol.json'); cfg = dict(learning_admission_root_path='future-root.json')
        root = dict(status='complete_R_candidate_eligibility_training_numeric_full_record_admission', approved_by='root',
            protocol=dict(path=str(config_path), sha256='p'*64), formal_optimizer_updates=0, actual_CPU_and_CUDA_numeric_verified=True,
            full_record_contract_verified=True, matched_control_reuse_verified=True, test_read=False,
            numeric_validation=dict(kind='numeric'), input_validation=dict(kind='inputs'))
        numeric = dict(status='complete_R_candidate_eligibility_CPU_CUDA_full_record_numeric_admission', protocol_sha256='p'*64,
            all_groups_equal=True, matched_control_reuse_numerical_compatibility_verified=True, formal_optimizer_updates=0,
            actual_diagnostic_optimizer_updates=20, diagnostic_R_windows=60, diagnostic_S_windows=8, test_read=False)
        inputs = dict(status='complete3000_R_candidate_eligibility_inputs_sources_masks_bindings_and_exposures_independently_verified',
            windows=3000, R_window_exposures_shared_once=27000, original_pool_order_labels_UIDs_and_known_projection_exact=True,
            pre_probability_mask_not_chosen_by_labels=True, original_R_S_order_references_unchanged=True, GT_coordinates_read=False, test_read=False)
        with patch.object(rt, 'read', lambda p: root), patch.object(rt, 'read_ref', lambda v: numeric if v['kind'] == 'numeric' else inputs), \
             patch.object(rt, 'sha', lambda p: 'p'*64), patch.object(rt, 'checked', lambda v: Path(v['path'])), patch.object(rt, 'physical', lambda p: Path(p)):
            self.assertEqual(rt.validate_training_admission(config_path, cfg), root)
            numeric['actual_diagnostic_optimizer_updates'] = 8
            with self.assertRaises(ValueError): rt.validate_training_admission(config_path, cfg)
            numeric['actual_diagnostic_optimizer_updates'] = 20; root['matched_control_reuse_verified'] = False
            with self.assertRaises(ValueError): rt.validate_training_admission(config_path, cfg)
            root['matched_control_reuse_verified'] = True; inputs['windows'] = 1000
            with self.assertRaises(ValueError): rt.validate_training_admission(config_path, cfg)


if __name__ == '__main__': unittest.main()
