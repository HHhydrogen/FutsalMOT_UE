"""资格/弱标签纯合同夹具；不读取实际输入、模型或GT。"""
from copy import deepcopy
import unittest

import state_label_alignment_core as c


def fixture(labels=(1, 0), enabled=(True, True), active=True, stage='high_score'):
    job = dict(job_id='teacher', fold='game4', sequence='SNMOT-097', regime='R', seed=20261024, model_id='model')
    history = ['h0', 'h1', 'h2']; uids = ['p', 'n']
    row = dict(job=job, frame_number=10, stage=stage, row_index=2, track_id=7, history_UIDs=history, query_GT_id='3',
        earliest_stage_trusted3_anchor=dict(gt_id='3', frame_number=4, stage='high_score', history_UIDs=['a', 'b', 'c']),
        flags=dict(trusted_three_history=True, learned_active=active, earliest_stage_trusted3_anchor_drift=False),
        absolute_counts=dict(candidates=2, positive=list(labels).count(1), known_negative=list(labels).count(0), unknown=list(labels).count(None), correct_raw=1),
        pose_candidates=[dict(uid=u, label=v, enabled=e, reference_cost=.4+i*.1) for i, (u, v, e) in enumerate(zip(uids, labels, enabled))],
        threshold=c.THRESHOLDS[stage], actual_observation_gap_frames=1)
    annotation = dict(frame_number=10, stage=stage, row_index=2, track_id=7, history_UIDs=history, history_count=3,
        history_status='trusted_consistent_history', current_GT_present=True, raw_correct_UIDs=['p'], candidate_UIDs=uids, pair_labels=list(labels), query_GT_id='3')
    metadata = dict(window_uid='window', fold='game4', sequence='SNMOT-097', source_job_id='teacher', candidate_frame_number=10,
        source_stage=stage, source_row_index=2, source_track_id=7, teacher_model_id='model', history_UIDs=history,
        candidate_UIDs=uids, pair_labels=list(labels), query_GT_id='3', anchor_drift=False)
    return row, annotation, metadata


class RowContracts(unittest.TestCase):
    def test_B_seven_classes_priority_and_no_label_mutation(self):
        cases = []
        r, a, m = fixture(); cases.append((r, None, None, 0))
        r, a, m = fixture(); cases.append((r, a, m, 1))
        r, a, m = fixture(labels=(0, None)); cases.append((r, a, m, 2))
        r, a, m = fixture(labels=(0, 0)); r['absolute_counts']['correct_raw'] = 0; a.update(current_GT_present=False, raw_correct_UIDs=[]); cases.append((r, a, m, 3))
        r, a, m = fixture(labels=(0, 0)); r['absolute_counts']['correct_raw'] = 0; a['raw_correct_UIDs'] = []; cases.append((r, a, m, 4))
        r, a, m = fixture(labels=(0, 0)); a['raw_correct_UIDs'] = ['outside-stage']; cases.append((r, a, m, 5))
        r, a, m = fixture(labels=(0, 0)); cases.append((r, a, m, 6))
        for r, a, m, index in cases:
            before = deepcopy(r); summary, candidates = c.classify_row(r, a, m)
            self.assertEqual(summary['B_class'], c.B_CLASSES[index]); self.assertEqual(before, r)
            self.assertTrue(summary['source_labels_unchanged']); self.assertFalse(summary['hypothetical_mask_executed'])
            self.assertEqual([x['label'] for x in candidates], [x['label'] for x in r['pose_candidates']])
        # unique known-positive优先于unknown竞争，但不优先于缺字段。
        r, a, m = fixture(labels=(1, None)); self.assertEqual(c.classify_row(r, a, m)[0]['B_class'], c.B_CLASSES[1])
        a['current_GT_present'] = None; self.assertEqual(c.classify_row(r, a, m)[0]['B_class'], c.B_CLASSES[0])

    def test_A_eligibility_distinct_from_probability_and_bbox_NA(self):
        r, a, m = fixture(enabled=(False, True)); summary, candidates = c.classify_row(r, a, m)
        self.assertFalse(candidates[0]['scoring_eligible']); self.assertEqual(candidates[0]['probability_status'], 'not_applicable')
        self.assertTrue(summary['primary_flags']['contains_scoring_ineligible_known']); self.assertTrue(summary['primary_flags']['contains_scoring_ineligible_positive'])
        self.assertEqual(summary['bce_weights']['excluded_known_window_mass'], .5)
        self.assertEqual(summary['bce_weights']['excluded_known_R_step_mass'], 1/6)
        self.assertEqual(candidates[1]['BCE_window_pair_weight'], .5); self.assertEqual(candidates[1]['BCE_R_step_pair_weight'], 1/6)
        self.assertFalse(candidates[0]['motion_gate']); self.assertIsNone(candidates[0]['motion_gate_missing_reason'])
        for active, stage, enabled in [(False, 'high_score', (False, False)), (False, 'low_score', (None, None))]:
            r, a, m = fixture(active=active, stage=stage, enabled=enabled); summary, candidates = c.classify_row(r, a, m)
            self.assertTrue(all(x['probability_status'] == 'not_applicable' for x in candidates))
            self.assertTrue(all(x['motion_gate'] is None for x in candidates))
            self.assertTrue(all(x['motion_gate_missing_reason'] is not None for x in candidates))
            self.assertEqual(summary['bce_weights']['excluded_known_window_mass'], 1.)
        r, a, m = fixture(enabled=(None, True)); summary, candidates = c.classify_row(r, a, m)
        self.assertIsNone(candidates[0]['scoring_eligible']); self.assertIsNone(summary['primary_flags']['contains_scoring_ineligible_positive'])
        self.assertEqual(summary['bce_weights']['unresolved_known_window_mass'], .5)

    def test_probability_reject_strict_equality_missing_and_above_preserved(self):
        for value, expected in [(1., 'probability_rejected'), (.7, 'strict_cost_feasible'), (.8, 'boundary_unknown'),
                                (.9, 'cost_above_threshold_unresolved'), (None, 'cost_missing')]:
            r, a, m = fixture(); r['pose_candidates'][0]['reference_cost'] = value
            self.assertEqual(c.classify_row(r, a, m)[1][0]['probability_status'], expected)

    def test_unknown_competition_and_raw_qualification_contract_flag(self):
        r, a, m = fixture(labels=(0, None)); summary, candidates = c.classify_row(r, a, m)
        self.assertTrue(summary['primary_flags']['no_known_positive_with_unknown'])
        self.assertTrue(summary['primary_flags']['eligible_trusted_correct_without_known_positive'])
        self.assertEqual(candidates[1]['BCE_window_pair_weight'], 0.)
        self.assertEqual(summary['counts']['known_negative_pairs'], 1)
        r, a, m = fixture(labels=(None, None)); summary, _ = c.classify_row(r, a, m)
        self.assertEqual(summary['bce_weights']['window_known_mass'], 0.)
        self.assertEqual(summary['bce_weights']['R_step_known_mass'], 0.)

    def test_exact_join_bad_counts_two_positives_and_future_anchor_refused(self):
        r, a, m = fixture()
        for change in (lambda x: x.update(source_row_index=99), lambda x: x.update(history_UIDs=['bad']),
                       lambda x: x.update(candidate_UIDs=['n', 'p']), lambda x: x.update(query_GT_id='9'),
                       lambda x: x.update(pair_labels=[0, 1])):
            bad = deepcopy(m); change(bad)
            with self.assertRaises(ValueError): c.classify_row(r, a, bad)
        bad = deepcopy(r); bad['absolute_counts']['unknown'] = 1
        with self.assertRaises(ValueError): c.classify_row(bad, a, m)
        r2, a2, m2 = fixture(labels=(1, 1))
        with self.assertRaises(ValueError): c.classify_row(r2, a2, m2)
        bad = deepcopy(r); bad['earliest_stage_trusted3_anchor']['frame_number'] = 11
        with self.assertRaises(ValueError): c.classify_row(bad, a, m)

    def test_history_1_2_not_trusted3_and_fixed_bins_drift_not_error(self):
        for count in (0, 1, 2, 3):
            r, a, m = fixture(); r['history_UIDs'] = r['history_UIDs'][:count]; a['history_UIDs'] = m['history_UIDs'] = r['history_UIDs']; a['history_count'] = count
            summary, _ = c.classify_row(r, a, m)
            self.assertEqual(summary['history_bin'], str(count))
            self.assertEqual(summary['B_class'], c.B_CLASSES[1 if count == 3 else 0])
        for gap, expected in [(1, '1'), (2, '2_to5'), (5, '2_to5'), (6, '6_to10'), (10, '6_to10'), (11, '11_to30'), (30, '11_to30'), (31, 'gt30'), (None, 'unknown')]:
            r, a, m = fixture(); r['actual_observation_gap_frames'] = gap
            self.assertEqual(c.classify_row(r, a, m)[0]['gap_bin'], expected)
        r, a, m = fixture(); r['earliest_stage_trusted3_anchor']['gt_id'] = 'other'; r['flags']['earliest_stage_trusted3_anchor_drift'] = True; m['anchor_drift'] = True
        summary, _ = c.classify_row(r, a, m); self.assertTrue(summary['anchor_drift']); self.assertFalse(summary['overlap_flags']['anchor_drift_is_true_identity_error'])


class SummaryContracts(unittest.TestCase):
    def fixture_rows(self):
        r, a, m = fixture(); template = c.classify_row(r, a, m)[0]; rows = []
        for sequence, heldout in c.SOURCE_FOLDS.items():
            for fold in c.FOLDS:
                if fold == heldout: continue
                for index in range(500):
                    row = deepcopy(template); row.update(window_uid=sequence+fold+str(index), sequence=sequence, fold=fold)
                    row['primary_flags'] = dict.fromkeys(c.PRIMARY_KEYS, index < 250); rows.append(row)
        return rows

    def test_selected3000_only_source_equal_statistics_and_missing_source_CI_null(self):
        rows = self.fixture_rows(); free = deepcopy(rows[0]); free.update(is_selected_R_window=False, window_uid=None, teacher_regime='RS')
        result = c.summarize_selected(rows+[free]); self.assertEqual(result['selected_windows'], 3000); self.assertEqual(result['free_sensitivity_rows_excluded'], 1)
        for key in c.PRIMARY_KEYS:
            stats = result['four_primary_descriptions'][key]
            self.assertEqual(stats['mean_rate_pp'], 50.); self.assertEqual(stats['Student_t_95CI'], [50., 50.])
            self.assertEqual(stats['bootstrap_seed'], 20261029); self.assertEqual(stats['n_independent_sources'], 3)
        for row in rows:
            if row['sequence'] == 'SNMOT-060' and row['fold'] == 'game6': row['primary_flags'][c.PRIMARY_KEYS[0]] = None
        stats = c.summarize_selected(rows)['four_primary_descriptions'][c.PRIMARY_KEYS[0]]
        self.assertIsNone(stats['source_rates_pp']['SNMOT-060']); self.assertEqual(stats['n_independent_sources'], 2)
        self.assertEqual(stats['mean_rate_pp'], 50.); self.assertIsNone(stats['Student_t_95CI']); self.assertEqual(stats['leave_one_source_out_mean'], {})
        with self.assertRaises(ValueError): c.summarize_selected(rows[:-1])
        bad = deepcopy(rows); bad[1]['window_uid'] = bad[0]['window_uid']
        with self.assertRaises(ValueError): c.summarize_selected(bad)

    def test_source_bootstrap_seed_LOO_and_twofold_rate_not_pooled(self):
        result = c.describe_sources({'SNMOT-060': 10., 'SNMOT-097': 30., 'SNMOT-151': 80.})
        self.assertEqual(result['mean_rate_pp'], 40.); self.assertEqual(result['leave_one_source_out_mean'], {'SNMOT-060': 55., 'SNMOT-097': 45., 'SNMOT-151': 20.})
        self.assertEqual(result, c.describe_sources({'SNMOT-060': 10., 'SNMOT-097': 30., 'SNMOT-151': 80.}))
        rows = self.fixture_rows(); key = c.PRIMARY_KEYS[0]
        for row in rows:
            if row['sequence'] == 'SNMOT-060':
                index = int(row['window_uid'].split(row['fold'])[-1])
                row['primary_flags'][key] = (True if index < 1 else False if index < 10 else None) if row['fold'] == 'game6' else index < 450
        result = c.summarize_selected(rows)['four_primary_descriptions'][key]
        self.assertEqual(result['source_rates_pp']['SNMOT-060'], 50.)


if __name__ == '__main__': unittest.main()
