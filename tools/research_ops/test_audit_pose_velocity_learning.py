"""实际预算审计必须拒绝矩阵缺项、伪造曝光和生产者未退出。"""
from copy import deepcopy
import hashlib
import unittest

import audit_pose_velocity_learning as audit


class Tests(unittest.TestCase):
    def test_full_matrix_no_missing_or_duplicate(self):
        rows = [dict(job, path='run'+str(i)) for i, job in enumerate(audit.matrix())]
        cfg = dict(training_matrix=audit.matrix())
        state = dict(status='complete27_bounded_velocity_training_wait_independent_audit_tracking',
                     active=None, completed_train=rows)
        audit.validate_state(state, cfg)
        for changed in (rows[:-1], rows[:-1]+[rows[0]]):
            with self.assertRaises(ValueError):
                audit.validate_state(dict(state, completed_train=changed), cfg)
        with self.assertRaises(ValueError):
            audit.validate_state(dict(state, active={'pid': 123}), cfg)

    def test_exact_producer_names_no_auditor_or_PID_reuse_false_positive(self):
        values = [dict(ProcessId=1, Name='python.exe', CommandLine='python D:/tools/pose_velocity_learning_train.py --execute'),
            dict(ProcessId=2, Name='python.exe', CommandLine='python "D:\\tools\\pose_velocity_learning_control.py" --execute'),
            dict(ProcessId=3, Name='python.exe', CommandLine='python D:/tools/audit_pose_velocity_learning.py'),
            dict(ProcessId=4, Name='python.exe', CommandLine='python D:/tools/verify_pose_velocity_learning_train.py'),
            dict(ProcessId=5, Name='UnrealEditor.exe', CommandLine='Editor project'),
            dict(ProcessId=6, Name='python.exe', CommandLine='python unrelated.py')]
        self.assertEqual([p['ProcessId'] for p in audit.blocked_processes(values)], [1, 2, 5])
        self.assertEqual(audit.blocked_processes([dict(ProcessId=1, Name='python.exe', CommandLine='python unrelated.py')]), [])

    def ledger(self, group):
        real = [dict(window_uid='R'+str(i), epoch=i//1000, candidate_pairs=3, labelled_pairs=2) for i in range(3000)]
        synthetic = [dict(window_uid='S'+str(i), epoch=0, candidate_pairs=5, labelled_pairs=1) for i in range(1000)]
        table = dict(real=real, synthetic=synthetic); logs = []
        for i in range(1000):
            mix = group != 'T_R'
            logs.append(dict(actual_update=i+1, update_index=i, real=real[i*3:i*3+3],
                synthetic=synthetic[i:i+1] if mix else [], R_windows=3, S_windows=int(mix),
                R_pairs=9, R_known_pairs=6, S_pairs=5*int(mix), S_known_pairs=int(mix),
                loss=.5 if mix else .4, real_loss=.4, synthetic_loss=.3 if mix else None,
                grad_l2=1., learning_rates=[.001], gradients_clipped=False, step_wall_seconds=.01))
        self.chain(logs)
        return logs, table

    def chain(self, rows):
        chain = '0'*64
        for row in rows:
            row.pop('chain_sha256', None)
            chain = hashlib.sha256((chain+audit.canonical(row)).encode()).hexdigest()
            row['chain_sha256'] = chain

    def test_actual_R_RS_and_all_known_pair_counts(self):
        for group in audit.GROUPS:
            logs, table = self.ledger(group); counts, _ = audit.count_run(logs, table, group)
            self.assertEqual(counts['R_windows'], 3000)
            self.assertEqual(counts['R_known_pairs'], 6000)
            self.assertEqual(counts['S_windows'], 0 if group == 'T_R' else 1000)
        logs, table = self.ledger('T_RS'); logs[999]['R_known_pairs'] = 9; self.chain(logs)
        with self.assertRaises(ValueError): audit.count_run(logs, table, 'T_RS')

    def test_rehashed_wrong_UID_missing_LR_or_hidden_S_refuses(self):
        for key, value in [('learning_rates', []), ('real', []), ('synthetic_loss', None)]:
            logs, table = self.ledger('T_RS'); logs[0][key] = value; self.chain(logs)
            with self.assertRaises(ValueError): audit.count_run(logs, table, 'T_RS')
        logs, table = self.ledger('T_R'); logs[0]['synthetic_loss'] = .1; self.chain(logs)
        with self.assertRaises(ValueError): audit.count_run(logs, table, 'T_R')

    def stats(self):
        return dict(augmentation='original_v9_both', original_gate_preserved=True,
            GT_donor_selection=False, future_donor_used=False, closed=True,
            observation_cache_limit=4096, feature_cache_limit_bytes=268435456,
            shuffle_unique_attempts=0, shuffle_reasons={},
            by_domain={domain: dict(known_pairs_materialized=0, pairs_with_changed_full_shape=0,
                pairs_with_changed_features=0, unchanged_pairs=0) for domain in ('real', 'synthetic')})

    def test_intervention_zero_coverage_preserved_and_changed_gate_refuses(self):
        stats = self.stats(); audit.validate_intervention(stats, 'T_RS')
        stats['shuffle_unique_attempts'] = 5
        stats['shuffle_reasons'] = {'augmented_mask_mismatch': 5}
        stats['shuffle_bank'] = dict(same_frame=True, exact_original_mask=True, GT_used=False,
            future_used=False, source_scope='all_observations_in_fixed_pools_not_complete_raw_frames',
            mapped_observations=4, observations=8)
        result = audit.validate_intervention(stats, 'T_shuffle_RS')
        self.assertEqual(result['reasons']['augmented_mask_mismatch'], 5)
        stats['original_gate_preserved'] = False
        with self.assertRaises(ValueError): audit.validate_intervention(stats, 'T_shuffle_RS')

    def test_only34_normalizer_columns_may_change(self):
        old = dict(mean=[0.]*194, std=[1.]*194, count=1000)
        new = deepcopy(old); new['mean'][audit.CHANGED[0]] = .2
        windows = [dict(domain='real', game='game6' if i < 500 else 'game9',
                        candidates=[dict(label=1)]) for i in range(1000)]
        state = dict(schema='bounded_pose_velocity_adapter_v1', feature_dim=195, model_variant='gated',
            changed_columns=list(audit.CHANGED), base_normalizer=old, normalizer=new,
            quality_scale=.03, velocity_clip=2., gate_source='original_unshuffled_after_same_v9_augmentation_raw',
            motion_and_mask_source='unchanged_target_prediction', normalizer_fit='known_label_clean_base_R_only',
            fit=dict(fit_scope='known_label_clean_base_R_only', windows=1000, known_pairs=1000, games=['game6', 'game9']))
        audit.validate_adapter(state, old, .03, 2., 'game4', windows)
        new['mean'][0] = .2
        with self.assertRaises(ValueError): audit.validate_adapter(state, old, .03, 2., 'game4', windows)

    def test_closed_false_without_complete_exit_evidence_refuses(self):
        stats = self.stats(); stats['closed'] = False
        with self.assertRaisesRegex(ValueError, '缓存未闭合'):
            audit.validate_intervention(stats, 'T_RS')

    def test_joined_prefetch_and_actual_process_exit_release_cache_without_explicit_close(self):
        stats = self.stats(); stats['closed'] = False
        prefetch = dict(loaded=1000, yielded=1000, closed=True, worker_alive=False)
        result = audit.validate_intervention(stats, 'T_RS', prefetch=prefetch,
            producer_processes_absent=True)
        self.assertFalse(result['cache_explicit_close_called'])
        self.assertEqual(result['closure_evidence'], 'producer_joined_and_run_process_exited')
        self.assertFalse(stats['closed'])

    def test_cache_false_any_missing_join_or_exit_evidence_still_refuses(self):
        stats = self.stats(); stats['closed'] = False
        prefetch = dict(loaded=1000, yielded=1000, closed=True, worker_alive=False)
        for changed in (dict(prefetch, loaded=999), dict(prefetch, yielded=999),
                        dict(prefetch, closed=False), dict(prefetch, worker_alive=True),
                        {k: v for k, v in prefetch.items() if k != 'loaded'}):
            with self.assertRaises(ValueError):
                audit.validate_intervention(stats, 'T_RS', prefetch=changed, producer_processes_absent=True)
        with self.assertRaises(ValueError):
            audit.validate_intervention(stats, 'T_RS', prefetch=prefetch, producer_processes_absent=False)
        stats['original_gate_preserved'] = False
        with self.assertRaises(ValueError):
            audit.validate_intervention(stats, 'T_RS', prefetch=prefetch, producer_processes_absent=True)


if __name__ == '__main__':
    unittest.main()
