"""513完整矩阵、720配对与三个比赛面板，不能省略负结果或虚构独立比赛数。"""
from copy import deepcopy
import unittest
import pose_velocity_tracking_analysis as analysis
from pose_velocity_tracking_control import process_gate, adapter_gate


class Tests(unittest.TestCase):
    def fixture(self):
        panels = dict(original_heldout=['H4', 'H6', 'H9'], old_external=['E1', 'E2'],
                      seven_observed=['V'+str(i) for i in range(7)])
        jobs = []; records = []; baselines = []
        heldout = dict(zip(analysis.FOLDS, panels['original_heldout']))
        def add(kind, group, fold, seed, on, seq):
            job = dict(kind=kind, group=group, fold=fold, seed=seed, pose_enabled=on, sequence=seq,
                job_id=f'{kind}/{group}/{fold}/{seed}/{on}/{seq}')
            jobs.append(job)
            value = (1. if group == 'T_RS' and on else 2. if group == 'T_R' else 3.)
            records.append(dict(job=job, metrics={m: value for m in analysis.METRICS},
                group=group, source_origin='actual_new_tracking',
                recovery=dict(total_events=10, same_prediction_ID_recovered=4, recovery_rate=.4),
                report=dict(path='actual', sha256='actualSHA')))
        for fold in analysis.FOLDS:
            for seed in analysis.SEEDS:
                for group, on in [('T_R', True), ('T_RS', True), ('T_RS', False),
                                  ('T_shuffle_RS', True), ('T_shuffle_RS', False)]:
                    for seq in [heldout[fold]]+panels['old_external']+panels['seven_observed']:
                        add('new', group, fold, seed, on, seq)
        for fold in analysis.FOLDS:
            for seed in analysis.SEEDS:
                for seq in panels['seven_observed']:
                    add('reference', 'same_capacity_motion_RS', fold, seed, False, seq)
                for baseline in analysis.BASELINES:
                    seqs = [heldout[fold]]+panels['old_external']
                    if baseline != 'same_capacity_motion_RS': seqs += panels['seven_observed']
                    for seq in seqs:
                        baselines.append(dict(group=baseline, job=dict(fold=fold, seed=seed, sequence=seq,
                            job_id=f'old/{baseline}/{fold}/{seed}/{seq}'),
                            metrics={m: 4. for m in analysis.METRICS}, source_origin='historical_readonly_new_updates0',
                            recovery=dict(total_events=10, same_prediction_ID_recovered=5, recovery_rate=.5),
                            report=dict(path='old', sha256='oldSHA')))
        return records, baselines, jobs, panels

    def test_all513_and720_pairs_negative_cells_retained(self):
        records, refs, jobs, panels = self.fixture()
        cells, baselines = analysis.paired_cells(records, refs, jobs, panels)
        self.assertEqual(len(records), 513); self.assertEqual(len(baselines), 270)
        self.assertEqual(len(cells), 8); self.assertEqual(sum(map(len, cells.values())), 720)
        self.assertEqual({r['delta_pp']['AssA'] for r in cells['T_RS_minus_T_R']}, {-1.})

    def test_missing_baseline_or_actual_job_not_silently_omitted(self):
        records, refs, jobs, panels = self.fixture()
        for bad_records, bad_refs in ((records[:-1], refs), (records, refs[:-1]), (records+[records[0]], refs)):
            with self.assertRaises(ValueError): analysis.paired_cells(bad_records, bad_refs, jobs, panels)

    def test_match_first_means_then_three_panels_separate(self):
        records, refs, jobs, panels = self.fixture(); cells, _ = analysis.paired_cells(records, refs, jobs, panels)
        seen = []
        def described(values):
            seen.append(values); return dict(n=len(values), match_values=values)
        result = analysis.intervals(cells['T_RS_minus_T_R'], panels, described)
        self.assertEqual([result[p]['AssA']['n'] for p in analysis.PANELS], [3, 2, 7])
        self.assertEqual(len(seen), 15)
        self.assertTrue(all(v == -1. for values in seen for v in values.values()))
        changed = deepcopy(panels); changed['seven_observed'][0] = 'E1'
        with self.assertRaises(ValueError): analysis.validate_panels(changed)

    def test_process_gate_exact_script_and_only_own_launcher_chain(self):
        script = 'D:/code/tools/pose_velocity_tracking_control.py'
        records = [dict(ProcessId=1, ParentProcessId=2, Name='python.exe', CommandLine='python '+script+' --config X'),
            dict(ProcessId=2, ParentProcessId=99, Name='python.exe', CommandLine='otherpython '+script+' --config X'),
            dict(ProcessId=7, ParentProcessId=99, Name='python.exe', CommandLine='python D:/code/verify_pose_velocity_learning_train.py')]
        self.assertEqual(process_gate(records, 1, script), [1, 2])
        for name, command in [('python.exe', 'python D:/code/pose_velocity_learning_train.py'),
                              ('UnrealEditor.exe', 'project')]:
            with self.assertRaises(ValueError):
                process_gate(records+[dict(ProcessId=8, ParentProcessId=99, Name=name, CommandLine=command)], 1, script)

    def test_first_adapter_must_have_actual_calls_not_only_AST(self):
        receipt = dict(schema='bounded_velocity513_free_tracking_v1', status='complete',
            job=dict(kind='new'), pose_enabled=True, inference_shape_shuffle=False,
            evaluation_GT_annotations_loaded=False, scope_adapter=dict(
                tracker_numeric_AST_unchanged_outside_scope_and_input=True,
                original_AST_sha256='x', reverse_restored_AST_sha256='x'),
            input_adapter_audit=dict(adapter_transform_pair_calls=1, feature_calls=1,
                observed_feature_dims=[195], all_finite=True, actual_feature_checks_performed=True))
        adapter_gate(receipt)
        receipt['input_adapter_audit']['adapter_transform_pair_calls'] = 0
        with self.assertRaises(ValueError): adapter_gate(receipt)

    def test_full_gap_denominator_negative_results_and_zero_events_null(self):
        records, refs, jobs, panels = self.fixture()
        cells, _ = analysis.paired_cells(records, refs, jobs, panels)
        paired = cells['T_RS_on_minus_original_gated_RS']
        self.assertEqual(len(paired), 90)
        self.assertAlmostEqual(paired[0]['gap']['delta_recovery_rate_pp'], -10.)
        summary = analysis.gap_intervals(paired, panels,
            lambda values: dict(n_independent_matches=len(values), mean_delta_pp=sum(values.values())/len(values)))
        self.assertEqual([summary[p]['n_independent_matches'] for p in analysis.PANELS], [3, 2, 7])
        a = dict(recovery=dict(total_events=0, same_prediction_ID_recovered=0, recovery_rate=None),
                 report=dict(path='a', sha256='s'))
        self.assertIsNone(analysis.gap_pair(a, a)['delta_recovery_rate_pp'])
        a['recovery']['recovery_rate'] = 0.
        with self.assertRaises(ValueError): analysis.gap_pair(a, a)

    def test_history_reference_cannot_relabel_C_pureR_or_hard_pool(self):
        _, _, _, panels = self.fixture()
        cfg = dict(source_tracking_config=dict(sha256='five'),
                   source_seven_tracking_config=dict(sha256='seven'), panels=panels)
        old_job = dict(kind='new_RS', method='motion', pool='balanced', sequence='E1', fold='game4', seed=20261024)
        report = dict(job=old_job, protocol_sha256='five', DO_PREPROC=False,
                      predictions_GT_filtered=False, test_read=False)
        entry = dict(group='strong_motion_RS', job=old_job)
        analysis.reference_semantics(entry, report, cfg)
        for change in (dict(pool='hard_enriched'), dict(kind='reference_R')):
            bad = dict(report, job=dict(old_job, **change))
            with self.assertRaises(ValueError):
                analysis.reference_semantics(dict(entry, job=bad['job']), bad, cfg)
        seven_job = dict(kind='learned', group='B', method='gated', sequence='V0', fold='game4', seed=20261024)
        seven = dict(report, job=seven_job, protocol_sha256='seven')
        seven_entry = dict(group='original_gated_RS', job=seven_job)
        analysis.reference_semantics(seven_entry, seven, cfg)
        bad = dict(seven, job=dict(seven_job, group='C'))
        with self.assertRaises(ValueError):
            analysis.reference_semantics(dict(seven_entry, job=bad['job']), bad, cfg)


if __name__ == '__main__':
    unittest.main()
