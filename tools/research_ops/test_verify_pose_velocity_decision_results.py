"""独立终验必须保留原trace分母、全部转移与实际退出，不能冒充再推理。"""
from copy import deepcopy
import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_pose_velocity_decision_results as verifier


class Tests(unittest.TestCase):
    def fixture(self):
        job = dict(source_job_id='trace', fold='game4', seed=20261024, pool='balanced',
                   sequence='SNMOT-060', group='T_RS', job_id='new-model')
        event = dict(frame_number=4, stage=0, track_ids=[7], history_UIDs=[['a', 'b', 'c']],
            candidate_UIDs=['p', 'n'], bbox_cost=[[.2, .6]], reference_cost=[[.8, .8]],
            motion_gate=[[True, True]], enabled=[[True, True]], active_rows=[True], enough_history=[True],
            lost_gap=[False], chosen_raw_UID=['p'], scored_locations=[[0, 0], [0, 1]],
            GT_read=False, logits=dict(motion=[.1, .2]))
        allocation = dict(matches=[[0, 0]], unmatched_rows=[], unmatched_columns=[1])
        decisions = {b: dict(cost=[[verifier.f32(.8)]*2], threshold=.8, assignment=deepcopy(allocation))
                     for b in verifier.BRANCHES}
        scored = dict(locations=[[0, 0], [0, 1]], base=[0., 0.], raw_head=[0., 0.], residual=[0., 0.],
            q=[.5, .5], gated_residual=[0., 0.], logits={b: [0., 0.] for b in verifier.BRANCHES},
            full_forward_equal_original_q=True, input_195_sha256='1'*64, decisions=decisions)
        posthoc = dict(row_index=0, track_id=7, history_status='trusted_consistent_history',
            trusted_current_GT_present=True, active=True, enough_history=True, lost_gap=False,
            scored_pairs=2, known_positive_scored_pairs=1, known_negative_scored_pairs=1, unknown_scored_pairs=0,
            outcomes={b: 'known_correct' for b in verifier.BRANCHES}, assignments={b: 0 for b in verifier.BRANCHES},
            original_reference_near_motion=True, margins={b: 0. for b in verifier.BRANCHES},
            diagnostic_quality_gate_all_positive_zero=False, source_stop='both_known_classes_in_motion_gate')
        new = dict(all_gated=deepcopy(scored), enabled_native=deepcopy(scored),
            batch_numeric_comparison={b: dict(maximum_all_gated_vs_enabled_cost_delta=0.,
                assignments_equal=True, maximum_enabled_logit_delta=0.) for b in verifier.BRANCHES},
            reference=dict(recorded_actual_old_motion_cost=event['reference_cost'], assignment=allocation,
                threshold=.8, origin='original_trace_recorded_actual_reference_cost_not_new_T_tracking'),
            fixed_state_native_cost_authority='direct_enabled_batch_new_T_counterfactual_not_recorded_new_T_free_tracking',
            q1_is_mechanism_proxy=True, GT_used_for_scoring=False)
        signature = hashlib.sha256(verifier.canonical([job['sequence'], 4, 0, event['history_UIDs'], event['candidate_UIDs']]).encode()).hexdigest()
        record = dict(job=job, source_event_number=0, state_signature=signature,
            original_state={k: deepcopy(event[k]) for k in verifier.ORIGINAL_FIELDS}, new_T=new,
            posthoc_rows=[posthoc], new_optimizer_updates=0, new_free_tracking=False, test_read=False,
            GT_used_only_for_source_validation_and_posthoc=True, source_validation_GT_registry_read=True,
            GT_annotations_loaded=True, posthoc_GT_labels_loaded=True, current_source_posthoc_GT_loaded=True,
            GT_used_for_scoring=False, GT_free_inputs=True)
        return record, event, job

    def test_full_saved_rows_count_negative_ties_and_all16_transition_cells(self):
        record, event, job = self.fixture(); tally = verifier.UnitTally()
        tally.add(record, event, job, 0, dict(near_motion_gap=.3))
        self.assertEqual(tally.counts['stage_events'], 1); self.assertEqual(tally.counts['stage_rows'], 1)
        self.assertEqual(tally.counts['original_q_vs_own_base/ranking_tie_target'], 1)
        self.assertEqual(tally.counts['original_q_vs_own_base/ranking_corrects'], 0)
        transitions = tally.transitions['original_q_vs_own_base']['all_rows']
        self.assertEqual(sum(map(len, transitions.values())), 16)
        self.assertEqual(transitions['known_correct']['known_correct'], 1)
        summary = dict(counts=dict(tally.counts), transitions=tally.transitions,
            maximum_all_gated_enabled_cost_delta=tally.maximum, unique_stage_state_signatures=1)
        tally.summary(summary)
        bad = deepcopy(summary); bad['counts']['stage_rows'] = 0
        with self.assertRaises(ValueError): tally.summary(bad)

    def test_drop_row_original_state_or_batch_difference_refuses(self):
        record, event, job = self.fixture()
        for field, value in [('posthoc_rows', []), ('source_event_number', 1)]:
            with self.assertRaises(ValueError):
                verifier.UnitTally().add(dict(record, **{field: value}), event, job, 0, dict(near_motion_gap=.3))
        bad = deepcopy(record); bad['new_T']['batch_numeric_comparison']['q1']['assignments_equal'] = False
        with self.assertRaises(ValueError): verifier.UnitTally().add(bad, event, job, 0, dict(near_motion_gap=.3))

    def test_loaded_registry_and_GT_free_scoring_not_confused(self):
        record, _, _ = self.fixture(); verifier.gt_contract(record, posthoc=True)
        for key, value in [('GT_annotations_loaded', False), ('source_validation_GT_registry_read', False),
                           ('GT_used_for_scoring', True), ('current_source_posthoc_GT_loaded', False)]:
            with self.assertRaises(ValueError): verifier.gt_contract(dict(record, **{key: value}), posthoc=True)

    def test_exact_complete_producer_names_do_not_match_verifier_or_reused_PID(self):
        self.assertTrue(verifier.is_producer('python "D:/code/pose_velocity_decision_probe.py" --score-worker 0'))
        self.assertTrue(verifier.is_producer('python D:/code/validate_pose_velocity_decision_numeric.py --execute'))
        self.assertFalse(verifier.is_producer('python D:/code/verify_pose_velocity_decision_results.py'))
        self.assertFalse(verifier.is_producer('python D:/code/other_pose_velocity_decision_probe.py'))

    def test_complete9_trace18_matrix_fixed_first_seed_balanced(self):
        details = []
        for fold in verifier.FOLDS:
            for seed in (20261024, 20261025, 20261026):
                for pool in ('balanced', 'hard_enriched'):
                    for seq in [next(s for s, f in verifier.OLD.items() if f == fold)]+list(verifier.EXTERNAL):
                        details.append(dict(job=dict(kind='common_state', job_id=f'{fold}|{seed}|{pool}|{seq}',
                            original=dict(fold=fold, seed=seed, pool=pool, sequence=seq))))
        matrix, selected = verifier.expected_matrix(details)
        self.assertEqual(len(matrix), 18); self.assertEqual(len(selected), 9)
        self.assertEqual([j['group'] for j in matrix[:2]], list(verifier.GROUPS))
        with self.assertRaises(ValueError): verifier.expected_matrix(details[:-1])

    def test_hashed_gzip_stream_and_source_unit_missing_events_refuses(self):
        record, event, job = self.fixture()
        with tempfile.TemporaryDirectory() as tmp, patch.object(verifier, 'R', Path(tmp)):
            root = Path(tmp)
            paths = [root/name for name in ('source.gz', 'a.gz', 'b.gz')]
            for path, rows in zip(paths, ([event], [record], [])):
                with gzip.open(path, 'wt', encoding='utf-8') as stream:
                    for row in rows: stream.write(verifier.canonical(row)+'\n')
            references = [verifier.ref(p) for p in paths]
            with verifier.jsonl_gzip(references[0]) as rows: self.assertEqual(list(rows), [event])
            source = dict(trace=references[0], counts=dict(stage_calls=1, all_stage_rows=1), job=dict(job_id='trace'))
            summaries = [dict(events=r) for r in references[1:]]
            with self.assertRaisesRegex(ValueError, '事件数不一致'):
                verifier.verify_pair(source, [job, job], summaries, dict(near_motion_gap=.3))


if __name__ == '__main__':
    unittest.main()
