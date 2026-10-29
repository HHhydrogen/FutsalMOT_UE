"""六条件、双参照身份及五族区间的纯fixture；不读取实际结果或实验。"""
from copy import deepcopy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import r_eligibility_tracking_analysis as a


def fixtures():
    panels = dict(original_heldout=list(a.OLD), old_external=['external0', 'external1'], seven_observed=['seven'+str(i) for i in range(7)])
    datasets = {origin: [] for origin in ('newMaskedBCE', 'alignedBCE', 'originalstrongmotion')}
    for regime, sequence, fold, seed in sorted(a.expected_cells(panels)):
        total = 0 if sequence == 'seven0' else (690 if sequence == 'seven6' else 300)
        for origin, rows in datasets.items():
            condition = origin+'_'+regime; unit = regime+'_'+fold+'_'+str(seed)
            mid = origin+'_'+unit; value = dict(newMaskedBCE_R=44, newMaskedBCE_RS=47, alignedBCE_R=40, alignedBCE_RS=42, originalstrongmotion_R=45, originalstrongmotion_RS=48)[condition]
            value += a.FOLDS.index(fold)+a.SEEDS.index(seed)
            success = 0 if total == 0 else dict(newMaskedBCE_R=40, newMaskedBCE_RS=50, alignedBCE_R=30, alignedBCE_RS=45, originalstrongmotion_R=40, originalstrongmotion_RS=55)[condition]
            row = dict(model_id=mid, regime=regime, sequence=sequence, fold=fold, seed=seed,
                metrics={m: value for m in a.METRICS}, gap=dict(total_events=total, same_prediction_ID_recovered=success, recovery_rate=None if total == 0 else success/total),
                report=dict(path='D:/projects/FutsalMOT_Research/fixture/'+mid+'/'+sequence+'.json', sha256='a'*64), frames=2)
            if origin == 'newMaskedBCE': row.update(baseline_model_id='alignedBCE_'+unit, original_baseline_model_id='originalstrongmotion_'+unit)
            if origin == 'alignedBCE': row.update(baseline_model_id='originalstrongmotion_'+unit)
            rows.append(row)
    return panels, datasets['newMaskedBCE'], datasets['alignedBCE'], datasets['originalstrongmotion']


class CompleteAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panels, cls.new, cls.aligned, cls.original = fixtures()
        cls.result = a.analyze_records(cls.new, cls.aligned, cls.original, cls.panels)

    def test_540_absolute_450_pairs_and_all_registered_statistics(self):
        result = self.result
        self.assertEqual((len(result['records']), len(result['paired_cell_records']), len(result['paired_match_records'])), (540, 450, 60))
        self.assertEqual((len(result['absolute_matches']), len(result['absolute_panels'])), (72, 18))
        self.assertEqual(sum(len(metrics) for family in result['comparisons'].values() for metrics in family.values()), 75)
        self.assertEqual(sum(len(family) for family in result['gap_comparisons'].values()), 15)
        for family, expected in zip(a.COMPARISONS, (-1, 5, 4, 3, 1)):
            self.assertEqual({r['delta_pp']['AssA'] for r in result['paired_cell_records'] if r['comparison'] == family}, {expected})
            self.assertEqual(result['comparisons'][family]['original_heldout']['AssA']['mean_delta_pp'], expected)
        self.assertEqual(result['gap_events_counted_once_per_source'], 3690)
        self.assertEqual({r['matched_training_cells'] for r in result['paired_match_records'] if r['panel'] == 'original_heldout'}, {3})
        self.assertEqual({r['matched_training_cells'] for r in result['paired_match_records'] if r['panel'] == 'seven_observed'}, {9})

    def test_six_conditions_absolute_values_not_reconstructed_from_delta(self):
        r = next(r for r in self.result['absolute_matches'] if r['condition'] == 'newMaskedBCE_R' and r['sequence'] == 'SNMOT-060')
        self.assertEqual(r['metrics']['AssA'], 45)
        self.assertEqual({r['condition'] for r in self.result['absolute_panels']}, set(a.CONDITIONS))
        for family in a.COMPARISONS:
            for panel, n in [('original_heldout', 3), ('old_external', 2), ('seven_observed', 7)]:
                stat = self.result['comparisons'][family][panel]['AssA']
                self.assertEqual(stat['n_independent_matches'], n); self.assertEqual(stat['Student_t_degrees_of_freedom'], n-1)
                self.assertEqual(stat['bootstrap_seed'], 20261029); self.assertEqual(stat['bootstrap_resamples'], 10000)

    def test_null_gap_never_zero_and_negative_results_preserved(self):
        for family in a.COMPARISONS:
            stat = self.result['gap_comparisons'][family]['seven_observed']
            self.assertEqual(stat['null_matches'], ['seven0']); self.assertIsNone(stat['Student_t_95CI'])
            self.assertIsNone(stat['percentile_match_bootstrap_95CI'])
            self.assertEqual(stat['n_independent_matches'], 6)
        negatives = [r for r in self.result['paired_cell_records'] if r['comparison'] == a.COMPARISONS[0]]
        self.assertTrue(all(r['delta_pp']['AssA'] == -1 for r in negatives))
        self.assertFalse(self.result['formal_equivalence_or_noninferiority']); self.assertIsNone(self.result['performance_margin'])

    def test_write_all_six_csvs_and_report_reject_existing_output(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(a, 'R', Path(temp)):
            out = Path(temp)/'pose/r_eligibility/analysis'
            answer = a.write_analysis(self.result, out, protocol={'fixture': True}, sources={'fixture': True})
            self.assertEqual(answer['status'], a.STATUS)
            for name, expected in [('all_results.csv', 540), ('all_paired_cells.csv', 450), ('all_paired_gaps.csv', 450),
                                   ('all_paired_matches.csv', 60), ('absolute_matches.csv', 72), ('absolute_panels.csv', 18)]:
                with (out/name).open(encoding='utf-8-sig', newline='') as stream: self.assertEqual(len(list(csv.DictReader(stream))), expected)
            report = json.loads((out/'report.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['all_actual_reports']), 180)
            self.assertEqual(len(report['all_aligned_reference_reports']), 180)
            self.assertEqual(len(report['all_original_reference_reports']), 180)
            self.assertNotIn('records', report)
            with self.assertRaises(ValueError): a.write_analysis(self.result, out)
            with self.assertRaises(ValueError): a.physical(Path(temp)/'test/forbidden.json')


class IdentityContracts(unittest.TestCase):
    def test_old_models_cannot_impersonate_new_mask_models(self):
        panels, new, aligned, original = fixtures()
        for row in new: row['model_id'] = row['original_baseline_model_id']
        with self.assertRaisesRegex(ValueError, '跨组复用'):
            a.analyze_records(new, aligned, original, panels)

    def test_t_bootstrap_loo_and_zero_do_not_imply_equivalence(self):
        stat = a.effect_intervals({'matchA': 1, 'matchB': 3})
        self.assertEqual(stat['mean_delta_pp'], 2)
        self.assertAlmostEqual(stat['Student_t_95CI'][0], 2-12.706204736432095)
        self.assertEqual(stat['percentile_match_bootstrap_95CI'], [1, 3])
        self.assertEqual(stat['leave_one_match_out_mean'], {'matchA': 3, 'matchB': 1})
        self.assertEqual(stat, a.effect_intervals({'matchA': 1, 'matchB': 3}))
        zero = a.effect_intervals({'a': 0, 'b': 0, 'c': 0})
        self.assertEqual(zero['Student_t_95CI'], [0, 0]); self.assertIsNone(zero['margin'])
        self.assertFalse(zero['formal_equivalence_or_noninferiority_test'])

    def test_incomplete_duplicate_nonfinite_and_transitive_mapping_refused(self):
        panels, new, aligned, original = fixtures()
        for bad in (new[:-1], new+[new[0]]):
            with self.assertRaises(ValueError): a.pair_records(bad, aligned, original, panels)
        for mutation in (lambda rows: rows[0].update(baseline_model_id='wrong'), lambda rows: rows[0].update(original_baseline_model_id='wrong'),
                         lambda rows: rows[0]['metrics'].update(HOTA=float('nan'))):
            bad = deepcopy(new); mutation(bad)
            with self.assertRaises(ValueError): a.pair_records(bad, aligned, original, panels)
        bad = deepcopy(aligned); bad[0]['baseline_model_id'] = 'other-original'
        with self.assertRaises(ValueError): a.pair_records(new, bad, original, panels)

    def test_model_identity_or_report_alias_across_matches_refused(self):
        panels, new, _, _ = fixtures()
        bad = deepcopy(new); bad[0]['model_id'] = 'same-unit-swapped-model'
        with self.assertRaises(ValueError): a.normalize(bad, panels, 'newMaskedBCE')
        bad = deepcopy(new); bad[1]['report'] = bad[0]['report']
        with self.assertRaises(ValueError): a.normalize(bad, panels, 'newMaskedBCE')

    def test_metadata_sha_and_same_file_path_guard(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(a, 'R', Path(temp)):
            path = Path(temp)/'source/report.json'; path.parent.mkdir(); path.write_text('{}', encoding='utf-8'); reference = a.ref(path)
            self.assertTrue(a.same_ref(reference, reference)); path.write_text('{"changed":true}', encoding='utf-8')
            with self.assertRaises(ValueError): a.read(reference)

    def test_match_mean_pairs_before_equal_match_mean(self):
        panels, new, aligned, original = fixtures()
        for row in new:
            if row['regime'] == 'RS' and row['sequence'] == 'external0' and row['fold'] == 'game4' and row['seed'] == a.SEEDS[0]: row['metrics']['AssA'] += 9
        cells = a.pair_records(new, aligned, original, panels); matches = a.match_records(cells, panels)
        main = [r for r in matches if r['comparison'] == a.COMPARISONS[0] and r['panel'] == 'old_external']
        self.assertEqual({r['sequence']: r['delta_pp']['AssA'] for r in main}, dict(external0=0, external1=-1))
        stat = a.effect_intervals({r['sequence']: r['delta_pp']['AssA'] for r in main})
        self.assertEqual(stat['mean_delta_pp'], -0.5); self.assertEqual(stat['n_independent_matches'], 2)


class PlanContracts(unittest.TestCase):
    def setUp(self):
        self.panels = fixtures()[0]
        self.plan = dict(schema='r_candidate_eligibility_tracking_analysis_plan_v1',
            status='frozen_before_numeric_admission_and_training', comparison_ids=list(a.COMPARISONS),
            comparison_families=5, metric_interval_count=75, gap_interval_count=15,
            bootstrap_seed=20261029, bootstrap_repeats=10000,
            bootstrap_algorithm='Python_MT19937_randrange_match_resampling_linear_quantiles', Student_t_df=[2, 1, 6],
            panels=dict(old_heldout=3, old_external=2, seven_observed=7), primary_metric='AssA',
            secondary_metrics=['HOTA', 'IDF1', 'DetA', 'MOTA'], main_reference='original_uncalibrated_strongmotion_RS',
            gap_event_ledger_total=3690, gap_is_physical_occlusion=False, equivalence_or_noninferiority_delta=None,
            best_model_selection=False, test116187_sealed=True, all12_are_observed_development=True,
            all_negative_zero_null_seed_fold_preserved=True, within_match_average_matched_fold_seed_then_equal_matches=True,
            unadjusted_descriptive_intervals=True, first_report_absolute_scores_for_all_methods_and_panels=True,
            leave_one_match_out=True, tracking_execution_requires_new_loader_numeric_full_record_admission=True)

    def test_exact_five_families_and_explicit_heldout_alias(self):
        before = deepcopy(self.plan)
        a.validate_analysis_plan(self.plan, self.panels)
        self.assertEqual(self.plan, before)
        self.assertEqual(a.COMPARISONS, ('new_RS_minus_original_strongmotion_RS', 'new_RS_minus_aligned_BCE_RS',
            'new_R_minus_aligned_BCE_R', 'new_RS_minus_new_R', 'new_synthetic_increment_minus_aligned_synthetic_increment'))
        self.assertEqual(a.CONDITIONS[:2], ('originalstrongmotion_R', 'originalstrongmotion_RS'))

    def test_stale_seed_interaction_family_or_equivalence_rejected(self):
        for key, value in [('bootstrap_seed', 20261028), ('comparison_ids', list(reversed(a.COMPARISONS))),
                           ('equivalence_or_noninferiority_delta', 0.1), ('gap_is_physical_occlusion', True),
                           ('main_reference', 'aligned_BCE_RS'), ('metric_interval_count', 90)]:
            bad = deepcopy(self.plan); bad[key] = value
            with self.assertRaises(ValueError): a.validate_analysis_plan(bad, self.panels)


if __name__ == '__main__': unittest.main()
