"""独立终验边界：矩阵/真实退出/完整CSV及比赛级区间，均为CPU夹具。"""
from copy import deepcopy
import unittest
from unittest.mock import patch

import verify_pose_velocity_tracking_results as verify
from substitution_paired_analysis import effect_intervals


class Verification(unittest.TestCase):
    def config(self):
        sources = {s: {} for s in set(verify.OLD) | set(verify.EXTERNAL) | set(verify.SEVEN)}
        return dict(sources=sources, tracking_matrix=verify.expected_matrix(sources))

    def test_full513_matrix_and_actual_terminal_required(self):
        cfg = self.config(); jobs = cfg['tracking_matrix']
        self.assertEqual(sum(j['kind'] == 'new' for j in jobs), 450)
        self.assertEqual(sum(j['kind'] == 'reference' for j in jobs), 63)
        state = dict(status='complete513_bounded_velocity_tracking_and_analysis', active=None,
            protocol_sha256='s', completed_tracking=[dict(job=j) for j in jobs])
        report = dict(status='complete513_all_results450_new63_reference_paired_intervals', protocol_sha256='s',
            tracking_jobs=513, new_representation_tracking_jobs=450, added_reference_tracking_jobs=63)
        verify.terminal_gate(cfg, state, report, 's')
        for key, value in [('completed_tracking', state['completed_tracking'][:-1]), ('active', dict(pid=7)),
                           ('status', 'complete513_wait_paired_analysis')]:
            bad = deepcopy(state); bad[key] = value
            with self.assertRaises(ValueError): verify.terminal_gate(cfg, bad, report, 's')
        bad = deepcopy(cfg); bad['tracking_matrix'][-1] = bad['tracking_matrix'][0]
        with self.assertRaises(ValueError): verify.terminal_gate(bad, state, report, 's')

    def test_actual_script_filename_and_launcher_exit_not_verify_self_match(self):
        own = [dict(ProcessId=1, Name='python.exe', CommandLine='python D:/code/verify_pose_velocity_tracking_results.py'),
               dict(ProcessId=2, Name='python.exe', CommandLine='python D:/code/verify_pose_velocity_learning_train.py')]
        verify.processes_absent(own)
        for command in ('python "D:/code/pose_velocity_tracking_control.py" --config X',
                        'python D:\\code\\pose_velocity_tracking_jobs.py --action metric',
                        'python D:/code/pose_velocity_tracking_analysis.py',
                        'python D:/code/pose_velocity_learning_train.py'):
            with self.assertRaises(ValueError):
                verify.processes_absent(own+[dict(ProcessId=3, Name='python.exe', CommandLine=command)])
        with self.assertRaises(ValueError): verify.processes_absent([dict(Name='UnrealEditor.exe', CommandLine='project')])

    def test_csv_rejects_missing_duplicate_wrong_negative_and_source(self):
        expected = {('negative',): dict(job_id='negative', AssA=-.5, source='old', gap=None)}
        rows = [dict(job_id='negative', AssA='-0.5', source='old', gap='')]
        verify.compare_csv(rows, expected, ('job_id',))
        for bad in ([], rows+rows, [dict(rows[0], AssA='.5')], [dict(rows[0], source='other')],
                    [dict(rows[0], gap='0')]):
            with self.assertRaises(ValueError): verify.compare_csv(bad, expected, ('job_id',))

    def test_intervals_independently_recomputed_for_three_separate_panel_sizes(self):
        for n in (2, 3, 7):
            deltas = {str(i): float(i)-n for i in range(n)}
            value = effect_intervals(deltas)
            verify.verify_interval(value, deltas, tuple(deltas))
            for field, replacement in [('n_independent_matches', 90), ('margin', .5),
                    ('formal_equivalence_or_noninferiority_test', True), ('mean_delta_pp', 30.),
                    ('Student_t_95CI', [0., 0.]), ('percentile_match_bootstrap_95CI', [0., 0.])]:
                bad = deepcopy(value); bad[field] = replacement
                with self.assertRaises(ValueError): verify.verify_interval(bad, deltas, tuple(deltas))

    def test_zero_event_gap_is_null_not_a_zero_effect_or_fake_interval(self):
        value = dict(n_independent_matches=1, match_deltas_pp={'a': -1.}, mean_delta_pp=-1.,
            Student_t_95CI=None, percentile_match_bootstrap_95CI=None, leave_one_match_out_mean=None,
            status='fewer_than_two_matches_with_registered_events_no_interval',
            formal_equivalence_or_noninferiority_test=False, margin=None,
            zero_event_matches_retained_null=['b'],
            outcome='all_registered_trusted_gap_recovery_rate_difference_pp_not_physical_occlusion')
        verify.verify_gap_interval(value, {'a': -1., 'b': None}, ('a', 'b'))
        verify.recovery(dict(total_events=0, same_prediction_ID_recovered=0, recovery_rate=None), 0)
        with self.assertRaises(ValueError): verify.recovery(dict(total_events=0, same_prediction_ID_recovered=0, recovery_rate=0.), 0)
        bad = deepcopy(value); bad['Student_t_95CI'] = [-2., 0.]
        with self.assertRaises(ValueError): verify.verify_gap_interval(bad, {'a': -1., 'b': None}, ('a', 'b'))

    def test_original_v10_receipt_fields_not_renamed_or_falsely_required(self):
        seq = 'SNMOT-060'; job = dict(sequence=seq)
        cfg = dict(sources={seq: dict(frames=750)}, registries=dict(old_five=dict(registry=dict(path='original', sha256='s'))))
        raw = dict(Count=dict(Dets=3, GT_Dets=4), HOTA={k: [.2, .4] for k in ('HOTA', 'AssA', 'DetA')},
                   Identity=dict(IDF1=.3), CLEAR=dict(MOTA=.3))
        percent = {k: 30. for k in verify.METRICS}
        report = dict(status='complete', job=job, DO_PREPROC=False, predictions_GT_filtered=False,
            GT_identity0_preserved=True, test_read=False, GT_rows=4, registry_sha256='s',
            recovery=dict(overall=dict(total_events=0, same_prediction_ID_recovered=0, recovery_rate=None)),
            summary={name: dict(metrics_percent=percent) for name in (seq, 'COMBINED_SEQ')},
            raw_results={name: dict(pedestrian=deepcopy(raw)) for name in (seq, 'COMBINED_SEQ')})
        report['raw_results'][seq]['pedestrian']['Count']['Frames'] = 750
        verify.verify_report(report, job, cfg, {seq: 0}, {seq: 4})
        bad = deepcopy(report); bad['registry_sha256'] = 'other'
        with self.assertRaises(ValueError): verify.verify_report(bad, job, cfg, {seq: 0}, {seq: 4})

    def registry_fixture(self):
        """保留实际old_five无schema/event_counts与seven独立schema的差异。"""
        cfg = dict(sources={}, registries={}); documents = {}; expected_refs = {}
        counts_by_panel = dict(old_five=dict(zip(tuple(verify.OLD)+verify.EXTERNAL, (363, 393, 200, 214, 183))),
            seven=dict(zip(verify.SEVEN, (293, 423, 351, 327, 375, 287, 281))))
        for panel, counts in counts_by_panel.items():
            sources = {}; gt_counts = {}
            for i, seq in enumerate(counts):
                gt_ref = dict(path='GT/'+seq, sha256='GT_SHA/'+seq)
                # 旧两个外部场真实使用gt_reference，旧三场与新七场使用gt。
                gt_key = 'gt_reference' if seq in verify.EXTERNAL else 'gt'
                sources[seq] = dict(sequence=seq, **{gt_key: gt_ref})
                expected_refs[gt_ref['path']] = deepcopy(gt_ref)
                gt_counts[seq] = 100+i
            cfg['sources'].update(deepcopy(sources))
            binding = dict(registry=dict(path=panel+'/ledger', sha256=panel+'_LEDGER_SHA'),
                           receipt=dict(path=panel+'/receipt', sha256=panel+'_RECEIPT_SHA'))
            cfg['registries'][panel] = binding
            for value in binding.values(): expected_refs[value['path']] = deepcopy(value)
            ledger = dict(sources=deepcopy(sources), event_count=sum(counts.values()),
                events=[dict(sequence=seq) for seq, n in counts.items() for _ in range(n)],
                tracking_results_read=False, test_read=False)
            public = dict(registry=deepcopy(binding['registry']), sources=deepcopy(sources),
                event_count=sum(counts.values()), GT_row_counts=gt_counts, contains_GT_coordinates=False,
                tracking_results_read=False, test_read=False)
            if panel == 'old_five':
                public.update(status='complete_old5_public_receipt_from_original_frozen_events',
                              event_counts=deepcopy(counts), events_rebuilt=False)
            else:
                public.update(schema='seven_match_gap_registration_receipt_without_GT_v1',
                    status='complete7_gap_registry_before_tracking', sequence_event_counts=deepcopy(counts))
            documents[binding['registry']['path']] = ledger
            documents[binding['receipt']['path']] = public
        return cfg, documents, expected_refs

    def run_registered_fixture(self, cfg, documents, expected_refs):
        def checked(value):
            if expected_refs.get(value['path']) != value: raise ValueError('fixture来源SHA改变')
            return value['path']
        with patch.object(verify, 'checked', side_effect=checked) as checks, \
                patch.object(verify, 'read', side_effect=lambda path: deepcopy(documents[path])):
            values = verify.registered_counts(cfg)
        return values, checks.call_args_list

    def test_actual_old_five_and_seven_receipt_schemas_keep_all_denominators(self):
        cfg, documents, expected_refs = self.registry_fixture()
        (totals, gt_rows), calls = self.run_registered_fixture(cfg, documents, expected_refs)
        self.assertEqual(sum(totals.values()), 3690)
        self.assertEqual(len(totals), 12); self.assertEqual(set(gt_rows), set(totals))
        checked_paths = {args.args[0]['path'] for args in calls}
        self.assertTrue({p for p in expected_refs if p.startswith('GT/')} <= checked_paths)

    def test_registry_schema_denominator_gt_counts_and_sha_errors_rejected(self):
        for mutation in ('unknown_schema', 'wrong_status', 'mixed_count_fields', 'missing_gt_counts',
                         'wrong_denominator', 'GT_coordinates', 'GT_source_SHA'):
            cfg, documents, expected_refs = self.registry_fixture()
            public = documents['old_five/receipt']
            if mutation == 'unknown_schema': public['schema'] = 'other'
            elif mutation == 'wrong_status': public['status'] = 'started'
            elif mutation == 'mixed_count_fields': public['sequence_event_counts'] = deepcopy(public['event_counts'])
            elif mutation == 'missing_gt_counts': public.pop('GT_row_counts')
            elif mutation == 'wrong_denominator': public['event_counts']['SNMOT-060'] -= 1
            elif mutation == 'GT_coordinates': public['contains_GT_coordinates'] = True
            else:
                for source in (public['sources'], documents['old_five/ledger']['sources'], cfg['sources']):
                    source['SNMOT-060']['gt']['sha256'] = 'changed'
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError): self.run_registered_fixture(cfg, documents, expected_refs)


if __name__ == '__main__':
    unittest.main()
