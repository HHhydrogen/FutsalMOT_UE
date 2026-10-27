"""有限条件账本终验针对CPU夹具；不使用真实solver、GT文件或模型。"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bounded_error_decomposition as core
import verify_bounded_error_decomposition as verify


class NoSolver:
    def feasible(self, value, cutoff): return True


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.root_patch = patch.object(verify, 'R', self.root); self.root_patch.start()
    def tearDown(self): self.root_patch.stop(); self.temp.cleanup()

    def event_fixture(self):
        labels = {}; raw = {}
        for identity in ('0', '1'):
            for frame in (1, 2, 3):
                uid = identity+'h'+str(frame); labels[uid] = dict(state='matched', gt_id=identity, frame_number=frame); raw[uid] = dict(score_float32=.9)
            uid = 'C'+identity; labels[uid] = dict(state='matched', gt_id=identity, frame_number=4); raw[uid] = dict(score_float32=.9)
        event = dict(frame_number=4, stage=0, track_ids=[7, 8], history_UIDs=[[identity+'h'+str(f) for f in (1, 2, 3)] for identity in ('0', '1')],
            candidate_UIDs=['C0', 'C1'], reference_cost=[[core.f32(.2), core.f32(.3)], [core.f32(.1), core.f32(.4)]],
            motion_gate=[[True, True], [True, True]], enabled=[[True, True], [True, True]], active_rows=[True, True],
            enough_history=[True, True], lost_gap=[False, True], chosen_raw_UID=['C0', 'C1'], GT_read=False)
        source = dict(labels=labels, raw=raw, GT={(4, identity): dict(candidate_raw_UIDs=['C'+identity]) for identity in ('0', '1')},
            positives={(4, identity): ['C'+identity] for identity in ('0', '1')})
        unit = dict(unit_id='u', sequence='SNMOT-060', fold='game4', seed=20261024)
        assignment = dict(matches=[[0, 1], [1, 0]], unmatched_rows=[], unmatched_columns=[])
        records = []; anchors = {}
        for row in range(2):
            record = core.classify_row(event, row, source, assignment, NoSolver(), anchors)
            record.update(unit, pool='balanced', source_event_number=0); records.append(record)
        return event, source, unit, records

    def test_actual_cost_gate_and_global_assignment_conditions_not_rowwise_argmin(self):
        event, _, unit, records = self.event_fixture()
        verify.validate_event_records(event, records, unit, 0, {})
        self.assertEqual(records[0]['first_stop'], 'global_competition_or_solver_unmatched')
        self.assertTrue(records[0]['joint_conditions']['correct_column_assigned_to_other_row'])
        self.assertEqual(records[1]['first_stop'], 'known_negative_cost_lower')
        self.assertFalse(records[0]['first_stop_is_cause'])
        for change in ('duplicate_column', 'shadow_cost', 'causal_flag', 'frame_end_as_stage'):
            bad = deepcopy(records)
            if change == 'duplicate_column': bad[1]['reconstructed_stage_assignment_column'] = bad[0]['reconstructed_stage_assignment_column']
            elif change == 'shadow_cost': bad[0]['reference_cost_row'][0] = .12345
            elif change == 'causal_flag': bad[0]['first_stop_is_cause'] = True
            else: bad[0]['frame_end_UID_is_stage_assignment'] = True
            with self.assertRaises(ValueError): verify.validate_event_records(event, bad, unit, 0, {})

    def test_anchor_is_earliest_trusted_three_not_global_GT_or_cause(self):
        _, _, _, records = self.event_fixture(); row = records[0]; anchors = {}
        self.assertEqual(verify.check_anchor(row, anchors), 'trusted3_anchor_established_here')
        later = deepcopy(row); later['frame_number'] = 8
        for label in later['history_labels']: label['gt_id'] = '1'
        later['query_GT_id'] = '1'
        later['history_anchor'] = dict(state='coherent_history_drift_from_first_trusted3_anchor', first_trusted3_anchor=anchors[7],
            interpretation='relative_posthoc_history_consistency_not_full_MOT_identity_or_causal_pollution')
        self.assertEqual(verify.check_anchor(later, anchors), 'coherent_history_drift_from_first_trusted3_anchor')
        later['history_anchor']['first_trusted3_anchor'] = dict(anchors[7], gt_id='1')
        with self.assertRaises(ValueError): verify.check_anchor(later, anchors)

    def test_immutable_firststop_order_keeps_bbox_and_unknown_strata(self):
        event, source, unit, _ = self.event_fixture(); event['active_rows'] = [False, False]
        assignment = dict(matches=[[0, 0], [1, 1]], unmatched_rows=[], unmatched_columns=[]); anchors = {}; records = []
        for i in range(2):
            row = core.classify_row(event, i, source, assignment, NoSolver(), anchors); row.update(unit, pool='balanced', source_event_number=0); records.append(row)
        verify.validate_event_records(event, records, unit, 0, {})
        self.assertTrue(all(v['first_stop'] == 'row_not_intervened' and v['decision_path'] == 'bbox_nonintervened' for v in records))
        records[0]['first_stop'] = 'reference_stage_selected_correct'
        with self.assertRaises(ValueError): verify.validate_event_records(event, records, unit, 0, {})

    def write_rows(self, name, values):
        path = self.root/name
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            for value in values: stream.write(verify.canonical(value)+'\n')
        return dict(verify.ref(path), rows=len(values))

    def unit_fixture(self):
        event, _, unit, records = self.event_fixture(); unit.update(pool='balanced', expected_stage_calls=1, expected_stage_rows=2,
            trace=self.write_rows('trace.gz', [event]), receipt=dict(path='original', sha256='r'), labels=dict(path='posthoc', sha256='l'),
            source_ledgers={}, original_tracking_receipt=dict(path='strong', sha256='s'))
        artifact = self.write_rows('rows.gz', records); first = Counter({k: 0 for k in verify.FIRST_STOPS}); outcomes = Counter({k: 0 for k in verify.OUTCOMES})
        anchors = Counter({k: 0 for k in verify.ANCHOR_STATES}); paths = Counter(learned_active=0, bbox_nonintervened=0); joint = Counter()
        for row in records:
            first[row['first_stop']] += 1; outcomes[row['native_stage_outcome']] += 1; anchors[row['history_anchor']['state']] += 1
            paths[row['decision_path']] += 1; joint.update({k: int(v) for k, v in row['joint_conditions'].items()})
        counts = dict(all_stage_rows=2, known_history_current_present=2, known_active_current_present=2, positive_FP32_cutoff_boundary_rows=0,
            **{'denominator/known_active_current_present_rows': 2})
        for prefix, values in [('first_stop', first), ('joint', joint), ('anchor', anchors), ('native_outcome', outcomes), ('decision_path', paths)]:
            counts.update({prefix+'/'+key: value for key, value in values.items()})
        cfg = dict(numeric_admission=dict(path='numeric', sha256='n'))
        summary = dict(schema='bounded_error_decomposition_unit_v1', status='complete_balanced_unit_all_stage_rows_posthoc_conditions_not_causes',
            **{k: unit[k] for k in ('unit_id', 'sequence', 'fold', 'seed', 'pool', 'trace', 'receipt', 'labels', 'source_ledgers', 'original_tracking_receipt')},
            numeric_admission=cfg['numeric_admission'], source_reference_cost_is_authority=True, shadow_logits_used=False,
            GT_coordinate_files_opened=False, GT_posthoc_label_IDs_loaded=True, GT_used_only_posthoc=True, first_stop_is_cause=False,
            unrecorded_low_stage_empty_matrices_and_lifecycle='unknown_not_recorded', model_loads=0, new_scores=0, new_free_tracking=0,
            new_TrackEval_runs=0, optimizer_updates=0, cache_or_media_read=False, test_read=False, events=1, stage_calls=1, stage_rows=2,
            all_stage_rows=artifact, artifacts=dict(row_ledger=artifact), first_stop_counts=dict(first), joint_condition_counts=dict(joint),
            native_stage_outcome_counts=dict(outcomes), native_stage_outcome_rows=2, history_anchor_condition_counts=dict(anchors),
            first_trusted3_anchors=2, decision_path_counts=dict(paths), positive_FP32_cutoff_boundary_rows=0,
            known_active_current_present_rows=2, counts=counts,
            closure=dict(numeric_sources_unchanged=True, model_or_Torch_or_tracker_loaded=False, optimizer_updates=0, single_edge_cache_capacity=65536, single_edge_cache_entries=4))
        path = self.root/'summary.json'; path.write_text(verify.canonical(summary), encoding='utf-8'); return cfg, unit, summary, path

    def test_full_unit_stream_counters_zero_categories_and_no_solver(self):
        cfg, unit, summary, path = self.unit_fixture(); result = verify.verify_unit(cfg, unit, path)
        self.assertEqual((result['stage_calls'], result['stage_rows']), (1, 2)); self.assertFalse(result['assignment_or_edge_solver_rerun'])
        summary['history_anchor_condition_counts']['coherent_history_drift_from_first_trusted3_anchor'] = 1
        path.write_text(verify.canonical(summary), encoding='utf-8')
        with self.assertRaises(ValueError): verify.verify_unit(cfg, unit, path)

    def test_match_equal_condition_CIs_not_row_independence_and_null_denominator(self):
        panels = dict(original_heldout=list(verify.OLD), old_external=list(verify.EXTERNAL), seven_observed=['S'+str(i) for i in range(7)])
        units, summaries = [], {}
        for seq in [*verify.OLD, *verify.EXTERNAL]:
            folds = (verify.OLD[seq],) if seq in verify.OLD else verify.FOLDS
            for fold in folds:
                for seed in verify.SEEDS:
                    uid = f'{seq}-{fold}-{seed}'; units.append(dict(unit_id=uid, sequence=seq, fold=fold, seed=seed, original_unit_id=uid))
                    native = 0 if seq == verify.EXTERNAL[0] else 5
                    summaries[uid] = dict(sequence=seq, fold=fold, seed=seed, events=1, stage_rows=10, native_stage_outcome_rows=native,
                        known_active_current_present_rows=native, counts={'first_stop/history_unknown': 2, 'joint/test': 3,
                            'native_outcome/unmatched_stage': native, 'denominator/known_active_current_present_rows': native})
        cfg = dict(units=units, unit_order=[u['unit_id'] for u in units], panels=panels); inv = dict(strong_units=units)
        def interval(values): return dict(n_independent_matches=len(values), mean_delta_pp=sum(values.values())/len(values), values=values)
        unit_rows, matches, coverage, descriptions = verify.condition_tables(cfg, summaries, inv, interval)
        self.assertEqual((len(unit_rows), len(coverage)), (27, 27))
        self.assertEqual(descriptions['original_heldout']['joint/test']['n_independent_matches'], 3)
        self.assertEqual(descriptions['old_external']['joint/test']['n_independent_matches'], 2)
        self.assertIsNone(descriptions['old_external']['native_outcome/unmatched_stage']['Student_t_95CI'])
        self.assertEqual(descriptions['old_external']['native_outcome/unmatched_stage']['zero_denominator_matches_retained_null'], [verify.EXTERNAL[0]])
        self.assertTrue(all(v['statistic'].startswith('observed_condition_rate') for p in descriptions.values() for v in p.values()))

    def test_raw_GT_cache_weight_guard_and_exact_producer_names(self):
        source = self.root/'original_cache.jsonl'; source.write_text('not read', encoding='utf-8')
        inventory = dict(sources={'S': dict(cache=dict(path=str(source)))}, units=[])
        with verify.no_raw_GT_cache_or_models(inventory) as proof:
            with self.assertRaises(PermissionError): source.read_text(encoding='utf-8')
        self.assertEqual(proof['blocked_open_attempts'], 1)
        now = datetime.now(timezone.utc).isoformat(); state = dict(parent_pid=7, created_utc=now)
        row = dict(ProcessId=7, Name='python.exe', CommandLine='python verify_bounded_error_decomposition.py', CreationUtc=now)
        self.assertEqual(verify.blocked_processes([row], state), [])
        self.assertEqual(len(verify.blocked_processes([dict(row, CommandLine='python bounded_error_control.py')], state)), 1)
        self.assertEqual(len(verify.blocked_processes([dict(row, CommandLine='python -c "spawn_main(parent_pid=7,pipe_handle=1)"')], state)), 1)

    def test_complete27_and63_missing_coverage_not_seven_internal_inference(self):
        seven = ['S'+str(i) for i in range(7)]; units = []; strong = []; missing = []
        for fold in verify.FOLDS:
            for seed in verify.SEEDS:
                for seq in [next(s for s, f in verify.OLD.items() if f == fold), *verify.EXTERNAL]:
                    key = dict(sequence=seq, fold=fold, seed=seed)
                    units.append(dict(key, unit_id='T'+str(len(units)), pool='balanced', expected_stage_calls=1, expected_stage_rows=1,
                        stage_assignment_reference={} if seed == 20261024 else None))
                    strong.append(dict(key))
                for seq in seven:
                    key = dict(sequence=seq, fold=fold, seed=seed); strong.append(key)
                    missing.append(dict(key, internal_candidate_or_score_or_lifecycle='unknown'))
        units[0]['expected_stage_calls'] += 24863-27; units[0]['expected_stage_rows'] += 320752-27
        inv = dict(schema='bounded_error_decomposition_inventory_v1', status='complete_metadata_inventory27_existing_trace63_missing_no_cache_GT_model_or_tracking',
            units=units, strong_units=strong, missing_trace_units=missing,
            sources={s: {} for s in [*verify.OLD, *verify.EXTERNAL, *seven]}, panels=dict(seven_observed=seven))
        verify.validate_coverage(inv)
        bad = deepcopy(inv); bad['missing_trace_units'][0]['internal_candidate_or_score_or_lifecycle'] = 'known_failure'
        with self.assertRaises(ValueError): verify.validate_coverage(bad)
        bad = deepcopy(inv); bad['units'][0]['pool'] = 'hard'
        with self.assertRaises(ValueError): verify.validate_coverage(bad)

    def test_numeric_admission_truthfully_declares_saved_GT_derived_metadata(self):
        units = [dict(unit_id=str(i), trace=dict(path='trace'+str(i), sha256='t'), stage_assignment_reference=dict(saved=str(i)),
            expected_stage_calls=1, expected_stage_rows=2) for i in range(9)]
        proof = dict(schema='bounded_error_decomposition_numeric_admission_v1', status='complete9_saved_stage_assignments_original_FP32_solver_exact_no_model',
            passed=True, source_units=9, numeric_sources=dict(snapshot='fixed'), source_unit_ids=[u['unit_id'] for u in units],
            event_count=9, stage_rows=18, saved_actual_reference_assignments_exact=True,
            matching_source_provenance='current_installed_snapshot_not_historical_file_SHA',
            single_edge_feasibility='same_original_solver_1x1_FP32_no_epsilon', original_GT_coordinate_files_opened=False,
            saved_GT_derived_posthoc_metadata_loaded=True, GT_used_for_assignment=False, test_read=False,
            model_loads=0, new_scores=0, new_free_tracking=0, new_TrackEval_runs=0, optimizer_updates=0,
            closure=dict(numeric_sources_unchanged=True, model_or_Torch_or_tracker_loaded=False, optimizer_updates=0),
            details=[dict(unit_id=u['unit_id'], trace=u['trace'], saved_reference=u['stage_assignment_reference'], events=1, stage_rows=2,
                exact_original_assignment=True) for u in units])
        path = self.root/'numeric.json'; path.write_text(verify.canonical(proof), encoding='utf-8')
        cfg = dict(units=units, numeric=dict(snapshot='fixed'), numeric_admission=verify.ref(path))
        self.assertTrue(verify.numeric_proof(cfg)['saved_GT_derived_posthoc_metadata_loaded'])
        for key, value in [('saved_GT_derived_posthoc_metadata_loaded', False), ('GT_used_for_assignment', True), ('original_GT_coordinate_files_opened', True)]:
            bad = deepcopy(proof); bad[key] = value; path.write_text(verify.canonical(bad), encoding='utf-8'); cfg['numeric_admission'] = verify.ref(path)
            with self.assertRaises(ValueError): verify.numeric_proof(cfg)


if __name__ == '__main__': unittest.main()
