"""原trace后验条件分解CPU合同；小夹具不冒充真实九份数值准入。"""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bounded_error_decomposition as core


class FixtureNumeric:
    """只固定测试分配结果；生产入口必须实际AST提取原NumPy/lap函数。"""
    def feasible(self, value, threshold): return core.f32(value) < threshold
    def assignment(self, values, threshold):
        return core.assignment_record([[0, 0]], [], list(range(1, len(values[0]))), len(values), len(values[0]))
    def closure(self): return dict(explicit_fixture_not_actual_numeric_proof=True)


def event_source():
    history = ['h1', 'h2', 'h3']
    candidates = ['p', 'n', 'u']
    labels = {uid: dict(state='matched', gt_id='0', frame_number=index+1) for index, uid in enumerate(history)}
    labels.update(p=dict(state='matched', gt_id='0', frame_number=4),
        n=dict(state='matched', gt_id='1', frame_number=4),
        u=dict(state='unknown_conflict', gt_id=None, frame_number=4))
    raw = {uid: dict(uid=uid, score_float32=core.f32(.9)) for uid in history+candidates}
    source = dict(labels=labels, raw=raw, positives={(4, '0'): ['p']},
        GT={(4, '0'): dict(candidate_raw_UIDs=['p', 'u'])})
    event = dict(GT_read=False, frame_number=4, stage=0, track_ids=[7], history_UIDs=[history],
        candidate_UIDs=candidates, bbox_cost=[[core.f32(v) for v in (.3, .4, .9)]],
        reference_cost=[[core.f32(v) for v in (.2, .4, .9)]],
        motion_gate=[[True, True, True]], enabled=[[True, True, True]], active_rows=[True],
        enough_history=[True], lost_gap=[False], chosen_raw_UID=['n'])
    return event, source


def classify(event=None, source=None, assignment=None, anchors=None):
    initial, labels = event_source()
    return core.classify_row(event or initial, 0, source or labels,
        assignment or dict(matches=[[0, 0]], unmatched_rows=[], unmatched_columns=[1, 2]),
        FixtureNumeric(), anchors if anchors is not None else {})


def compressed(path, rows):
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        for row in rows:
            stream.write(core.canonical(row)+'\n')
    return core.ref(path)


class BoundedConditionContracts(unittest.TestCase):
    def test_actual_FP32_cost_and_boundary_no_epsilon_or_logit_substitution(self):
        event, _ = event_source()
        self.assertEqual(core.event_shape(event), (1, 3))
        event['reference_cost'][0][0] = .1
        with self.assertRaises(ValueError):
            core.event_shape(event)
        boundary = core.cutoff_boundary(core.f32(.8), .8)
        self.assertTrue(boundary['equal_float32_cutoff'])
        self.assertFalse(boundary['equal_python_cutoff'])
        self.assertEqual(boundary['compared_to_python_cutoff'], 'greater')
        self.assertFalse(boundary['epsilon_used'])
        boundary7 = core.cutoff_boundary(core.f32(.7), .7)
        self.assertEqual(boundary7['compared_to_python_cutoff'], 'less')

    def test_actual_stage_assignment_not_frame_end_choice_or_shadow_logit(self):
        event, source = event_source()
        event['logits'] = dict(motion=[-999., 999., 999.])
        row = classify(event, source)
        self.assertEqual(row['first_stop'], 'reference_stage_selected_correct')
        self.assertEqual(row['native_stage_outcome'], 'same_trusted_GT')
        self.assertEqual(row['reconstructed_stage_assignment_UID'], 'p')
        self.assertEqual(row['frame_end_chosen_raw_UID'], 'n')
        self.assertFalse(row['frame_end_UID_is_stage_assignment'])
        self.assertFalse(row['first_stop_is_cause'])

    def test_history_unknown_mixed_and_current_absence_keep_native_outcome_null(self):
        event, source = event_source()
        source['labels']['h1']['state'] = 'unknown_conflict'
        row = classify(event, source)
        self.assertEqual(row['first_stop'], 'history_unknown')
        self.assertIsNone(row['native_stage_outcome'])
        event, source = event_source()
        source['labels']['h1']['gt_id'] = '1'
        row = classify(event, source)
        self.assertEqual(row['first_stop'], 'mixed_trusted_history')
        self.assertIsNone(row['native_stage_outcome'])
        event, source = event_source()
        source['GT'].clear()
        row = classify(event, source)
        self.assertEqual(row['first_stop'], 'current_GT_absent')
        self.assertIsNone(row['native_stage_outcome'])

    def test_pool_gate_threshold_stops_and_nonintervened_outcome_sidecar(self):
        event, source = event_source()
        source['positives'].clear()
        self.assertEqual(classify(event, source)['first_stop'], 'raw_geometry_ambiguous')
        source['GT'][(4, '0')]['candidate_raw_UIDs'] = []
        self.assertEqual(classify(event, source)['first_stop'], 'no_raw_geometry_candidate')
        event, source = event_source()
        event['candidate_UIDs'][0] = 'n'
        self.assertEqual(classify(event, source)['first_stop'], 'positive_raw_not_in_stage')
        event, source = event_source()
        event['history_UIDs'][0] = ['h2', 'h3']
        event['enough_history'][0] = False
        event['active_rows'][0] = False
        row = classify(event, source)
        self.assertEqual(row['first_stop'], 'history_fewer_than3')
        self.assertEqual(row['native_stage_outcome'], 'same_trusted_GT')
        event, source = event_source()
        event['active_rows'][0] = False
        row = classify(event, source)
        self.assertEqual(row['first_stop'], 'row_not_intervened')
        self.assertEqual(row['decision_path'], 'bbox_nonintervened')
        event, source = event_source()
        event['enabled'][0][0] = False
        self.assertEqual(classify(event, source)['first_stop'], 'positive_outside_effective_gate')
        event, source = event_source()
        event['reference_cost'][0][0] = core.f32(.8)
        row = classify(event, source)
        self.assertEqual(row['first_stop'], 'no_single_edge_feasible_positive')
        self.assertEqual(row['positive_cost_boundaries'][0]['compared_to_python_cutoff'], 'greater')

    def test_ranking_tie_unknown_and_global_competition_remain_distinct(self):
        event, source = event_source()
        chosen_negative = dict(matches=[[0, 1]], unmatched_rows=[], unmatched_columns=[0, 2])
        event['reference_cost'][0] = [core.f32(.3), core.f32(.1), core.f32(.9)]
        self.assertEqual(classify(event, source, chosen_negative)['first_stop'], 'known_negative_cost_lower')
        event['reference_cost'][0] = [core.f32(.3), core.f32(.3), core.f32(.9)]
        self.assertEqual(classify(event, source, chosen_negative)['first_stop'], 'minimum_cost_tie')
        event['reference_cost'][0] = [core.f32(.3), core.f32(.4), core.f32(.2)]
        self.assertEqual(classify(event, source, chosen_negative)['first_stop'], 'unknown_competition_or_assignment')
        event['reference_cost'][0] = [core.f32(.1), core.f32(.4), core.f32(.9)]
        assignment = dict(matches=[[0, 1], [1, 0]], unmatched_rows=[], unmatched_columns=[2])
        row = classify(event, source, assignment)
        self.assertEqual(row['first_stop'], 'global_competition_or_solver_unmatched')
        self.assertTrue(row['joint_conditions']['correct_column_assigned_to_other_row'])

    def test_first_trusted3_anchor_detects_relative_drift_without_causal_claim(self):
        event, source = event_source()
        anchors = {}
        first = classify(event, source, anchors=anchors)
        self.assertEqual(first['history_anchor']['state'], 'trusted3_anchor_established_here')
        self.assertEqual(anchors[7]['gt_id'], '0')
        source = deepcopy(source)
        for uid in event['history_UIDs'][0]:
            source['labels'][uid]['gt_id'] = '1'
        source['GT'][(4, '1')] = dict(candidate_raw_UIDs=['n'])
        source['positives'][(4, '1')] = ['n']
        drift = classify(event, source, anchors=anchors)
        self.assertEqual(drift['history_anchor']['state'], 'coherent_history_drift_from_first_trusted3_anchor')
        self.assertTrue(drift['joint_conditions']['coherent_history_drift_from_anchor'])
        self.assertIn('not_full_MOT_identity_or_causal_pollution', drift['history_anchor']['interpretation'])
        self.assertEqual(anchors[7]['gt_id'], '0')

    def test_future_or_wrong_frame_UID_is_rejected(self):
        event, source = event_source()
        source['labels']['h3']['frame_number'] = 4
        with self.assertRaises(ValueError):
            classify(event, source)
        event, source = event_source()
        source['labels']['p']['frame_number'] = 5
        with self.assertRaises(ValueError):
            classify(event, source)

    def test_saved_reference_contract_full_nine_event_sequences_rejects_missing_or_changed_assignment(self):
        with tempfile.TemporaryDirectory(prefix='decomposition_ref_') as directory:
            root = Path(directory)
            units = []
            for index in range(9):
                event, _ = event_source()
                identity = 'fixture_'+str(index)
                job = dict(source_job_id=identity, sequence='SNMOT-060', fold='game4', seed=20261024,
                    pool='balanced', group='T_RS')
                signature = core.hashlib.sha256(core.canonical([job['sequence'], event['frame_number'], event['stage'],
                    event['history_UIDs'], event['candidate_UIDs']]).encode()).hexdigest()
                record = dict(job=job, source_event_number=0, state_signature=signature,
                    original_state={key: event[key] for key in core.ORIGINAL_FIELDS}, test_read=False,
                    new_optimizer_updates=0, new_free_tracking=False,
                    new_T=dict(reference=dict(recorded_actual_old_motion_cost=event['reference_cost'], threshold=.8,
                        origin='original_trace_recorded_actual_reference_cost_not_new_T_tracking',
                        assignment=FixtureNumeric().assignment(event['reference_cost'], .8))))
                trace = compressed(root/(identity+'_trace.jsonl.gz'), [event])
                saved = compressed(root/(identity+'_saved.jsonl.gz'), [record])
                units.append(dict(unit_id=identity, sequence=job['sequence'], fold=job['fold'], seed=job['seed'],
                    pool='balanced', trace=trace, expected_stage_calls=1, expected_stage_rows=1,
                    stage_assignment_reference=dict(events=saved, record_path='new_T.reference.assignment',
                        source_event_index='source_event_number', expected_events=1)))
            cfg = dict(units=units, output_root=str(root), numeric=dict(explicit_fixture_only=True))
            with patch.object(core, 'backend', return_value=FixtureNumeric()):
                receipt = core.verify_saved_assignments(cfg, root/'proof.json')
            self.assertTrue(receipt['passed'])
            self.assertEqual(receipt['event_count'], 9)
            self.assertEqual(receipt['stage_rows'], 9)
            self.assertTrue(receipt['closure']['explicit_fixture_not_actual_numeric_proof'])
            with patch.object(core, 'backend', return_value=FixtureNumeric()), self.assertRaises(ValueError):
                core.verify_saved_assignments(cfg, root/'proof.json')
            broken = deepcopy(cfg)
            broken['units'].pop()
            with patch.object(core, 'backend', return_value=FixtureNumeric()), self.assertRaises(ValueError):
                core.verify_saved_assignments(broken, root/'missing.json')
            broken = deepcopy(cfg)
            path = root/'bad_saved.jsonl.gz'
            original = list(core.rows_ref(units[0]['stage_assignment_reference']['events']))[0]
            original['new_T']['reference']['assignment']['matches'] = [[0, 1]]
            broken['units'][0]['stage_assignment_reference']['events'] = compressed(path, [original])
            with patch.object(core, 'backend', return_value=FixtureNumeric()), self.assertRaises(ValueError):
                core.verify_saved_assignments(broken, root/'mismatch.json')


if __name__ == '__main__':
    unittest.main()
