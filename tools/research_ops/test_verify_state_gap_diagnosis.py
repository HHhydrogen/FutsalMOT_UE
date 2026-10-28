"""独立终验有意义篡改夹具；不读取真实GT/模型/缓存或执行追踪。"""
from copy import deepcopy
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_state_gap_diagnosis as verify
import state_gap_analysis as analysis


def fixture(with_event=True):
    data, serial = {}, [0]
    def put(value, rows=False):
        serial[0] += 1; name = 'artifact_'+str(serial[0]); data[name] = value
        return dict(path=name, sha256=verify.digest(value), **(dict(rows=len(value)) if rows else {}))
    cfg = dict(schema='state_gap_diagnosis_protocol_v1', approved_by='root', test_sealed=True, optimizer_updates=0,
        new_image_predictions=0, phase='formal', execute_authorized=True, tracker_parameters=dict(
            track_high_thresh=.25, track_low_thresh=.1, new_track_thresh=.25, track_buffer=30, match_thresh=.8, fuse_score=True),
        sources={s: dict(frames=750, cache=dict(path=s, sha256='b'*64)) for s in verify.OLD}, jobs=[],
        worker_profile=dict(track_workers=2, posthoc_workers=1))
    for regime in ('R', 'RS'):
        for fold in verify.FOLDS:
            for seq, game in verify.OLD.items():
                if game != fold:
                    cfg['jobs'].append(dict(job_id=f'{regime}_{fold}_{seq}', model_id=f'{regime}_{fold}', regime=regime, fold=fold, sequence=seq, seed=20261024))
    numeric = dict(status='complete_real_observer_original_ABA_spawn_snapshot_resource_admission', all_workers_exited=True,
        selected_worker_profile=cfg['worker_profile'], diagnostic_frame_advances=1296, optimizer_updates=0, new_image_predictions=0, test_read=False)
    cfg['numeric_admission'] = put(numeric)
    exits = [dict(joined=True, process_exited=True, exit_code=0) for _ in range(3)]
    report = dict(status='complete12_train_rollouts_and_bounded_state_propagation_diagnosis', test_read=False,
        all_negative_and_unknown_preserved=True, independent_factor_validation_started=False, performance_scores_not_computed=True,
        observe={}, posthoc={}, plans={}, replay={}, branch_posthoc={}, clean_pool_structures={}, worker_exits=exits)
    proof = dict(evaluation_GT_coordinate_files_opened=False, models_unchanged=True, inputs_unchanged=True, optimizer_updates=0,
        test_read=False, GT_guard=dict(python_open_audit_installed=True, blocked_open_attempts=0, GT_annotations_opened=False))
    chosen_job = cfg['jobs'][0]; all_event, event_record, original_logs = None, None, None
    for job in cfg['jobs']:
        logs = []
        for n in range(1, 751):
            stages = []
            for name, threshold in zip(('high_score', 'low_score', 'unconfirmed'), (.8, .5, .7)):
                stages.append(dict(frame_number=n, stage=name, track_ids=[], candidate_UIDs=[], rows=[], cost_shape=[0, 0],
                    threshold=threshold, native_ordered_batch_forward_preserved=True, assignments=[], unmatched_track_rows=[], unmatched_detection_columns=[]))
            logs.append(dict(frame_number=n, frame_index=n-1, stages=stages, tracks_before={k: [] for k in ('tracked_stracks', 'lost_stracks', 'removed_stracks')},
                tracks_after={k: [] for k in ('tracked_stracks', 'lost_stracks', 'removed_stracks')}, lifecycle=[], native_output=[], full_state_sha256=verify.digest([job['job_id'], n])))
        events, rows = [], []
        if with_event and job == chosen_job:
            all_event = dict(job, event_id='one_event', frame_number=4, frame_index=3, track_id=7, wrong_uid='w4', correct_uid='c4',
                anchor_GT_id='0', pre_error_history_UIDs=['c1', 'c2', 'c3'], candidate_eligible=True, exclusion_reasons=[],
                available_future_source_frames=746)
            events = [deepcopy(all_event)]
            before = dict(track_id=7, history_UIDs=['c1', 'c2', 'c3']); after = dict(track_id=7, record={'uid': 'w4'})
            logs[3]['stages'][0].update(track_ids=[7], candidate_UIDs=['w4', 'c4'], rows=[before], cost_shape=[1, 2], assignments=[[0, 0]], unmatched_detection_columns=[1])
            logs[3]['lifecycle'] = [dict(operation='update', track_id=7, before=before, after=after)]
            logs[3]['tracks_after']['tracked_stracks'] = [after]
            rows = [dict(job_id=job['job_id'], sequence=job['sequence'], condition_is_cause=False, candidate_UIDs=['w4', 'c4'], pair_labels=[0, 1])]
            original_logs = deepcopy(logs)
        artifact = put(logs, rows=True)
        receipt = dict(schema='state_gap_observe_receipt_v1', status='complete', job=job, frames=750, frames_log=artifact,
            source_cache=cfg['sources'][job['sequence']]['cache'], observer_enabled=True, frame_counts=[0]*750,
            native_sha256=verify.digest([[]]*750), state_sequence_sha256=verify.digest([row['full_state_sha256'] for row in logs]), **proof)
        report['observe'][job['job_id']] = put(receipt)
        report['posthoc'][job['job_id']] = put(dict(job=job, observe=report['observe'][job['job_id']], total_frames=750, new_solver_calls=0,
            all_rows=put(rows, rows=True), summary=dict(absolute_counts=dict(windows=len(rows))), events=dict(events=events)))
    for fold in verify.FOLDS:
        seq = next(s for s, g in verify.OLD.items() if g != fold)
        rows = [dict(window_uid=fold+str(i), sequence=seq, teacher_forced_history=True) for i in range(1000)]
        report['clean_pool_structures'][fold] = dict(rows=put(rows, rows=True), summary=dict(absolute_counts=dict(windows=1000)))
    all_records = []
    if with_event:
        selected = dict(all_event, selected=True, selection_reason='fixed_order_selected')
        report['selection'] = put(dict(events=[selected], selected=[selected]))
        plan = {key: all_event[key] for key in verify.PLAN_KEYS}; jid = chosen_job['job_id']
        report['plans'][jid] = put(dict(plans=[plan]))
        branches, outcomes = {}, {}
        for name in verify.BRANCHES:
            segment = deepcopy(original_logs[3:34]); intervention = dict(branch=name, allowed_fields={'original': [], 'history_only': ['history'],
                'motion_only': ['mean', 'covariance'], 'both': ['history', 'mean', 'covariance']}[name],
                actual_changed_fields=[] if name == 'original' else ['history'] if name == 'history_only' else ['mean'] if name == 'motion_only' else ['history', 'mean'],
                non_target_fields_unchanged=True, GT_coordinates_used=False, local_oracle_not_global_reassignment=True)
            branches[name] = put(dict(schema='state_gap_oracle_replay_v1', branch=name, plan=plan, future_frames=30,
                new_optimizer_updates=0, not_deployable_or_main_tracking_score=True, intervention=intervention,
                original_branch_exact_checked=name == 'original', frames_log=put(segment, rows=True), full_state_sha256=[row['full_state_sha256'] for row in segment]))
            outcome_rows = [dict(frame_number=n, outcome='other_trusted_identity' if name in ('original', 'motion_only') else 'same_trusted_anchor') for n in range(5, 35)]
            counts = Counter(row['outcome'] for row in outcome_rows); recovered = name in ('history_only', 'both')
            outcomes[name] = dict(rows=outcome_rows, absolute_counts={key: counts[key] for key in verify.OUTCOMES}, observed_frames=30, requested_frames=30,
                source_end_truncated=False, first_trusted_recovery_offset_frames=1 if recovered else None,
                no_trusted_recovery_observed=not recovered, recovery_time_right_censored=not recovered, exact_original_reproduction=True if name == 'original' else None)
        prefix = [dict(frame_number=row['frame_number'], full_state_sha256=row['full_state_sha256'], native_sha256=verify.digest(row['native_output'])) for row in original_logs[:4]]
        report['replay'][jid] = put(dict(schema='state_gap_replay_receipt_v1', status='complete', job=chosen_job, plans=report['plans'][jid],
            original_observe=report['observe'][jid], prefix_frames=4, branch_frame_advances=124, future_branch_frames=120, prefix=put(prefix, rows=True),
            events=[dict(event_id='one_event', snapshot=put({'schema': 'state_gap_portable_snapshot_v1'}), branches=branches)], **proof))
        event_record = {key: all_event[key] for key in ('event_id', 'fold', 'sequence', 'regime', 'model_id', 'track_id', 'frame_number')}; event_record['branches'] = outcomes
        all_records.append(event_record)
        report['branch_posthoc'][jid] = put(dict(status='complete', job=chosen_job, replay=report['replay'][jid], event_records=[event_record], summary=analysis.summarize_branches([event_record])))
    else:
        report['selection'] = put(dict(events=[], selected=[]))
    report['oracle_summary'] = analysis.summarize_branches(all_records)
    report['budget'] = dict(first_pass_frame_advances=9000, prefix_frame_advances=4 if with_event else 0, branch_frame_advances=124 if with_event else 0,
        total_formal_frame_advances=9128 if with_event else 9000, selected_events=int(with_event), optimizer_updates=0, new_image_predictions=0, numeric_admission=cfg['numeric_admission'])
    state = dict(status='complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed', active=[], observe=report['observe'], posthoc=report['posthoc'],
        selected_events=report['selection'], plans=report['plans'], replay=report['replay'], branch_posthoc=report['branch_posthoc'], budget=report['budget'], worker_exits=exits)
    def readref(value): return data[value['path']]
    return cfg, state, report, readref, data


class TerminalContracts(unittest.TestCase):
    def setUp(self):
        self.cfg, self.state, self.report, self.read, self.data = fixture()

    def check(self): return verify.verify_records(self.cfg, self.state, self.report, self.read)

    def test_complete_full_records_and_negative_branch_counts(self):
        result = self.check()
        self.assertEqual(result['jobs'], 12); self.assertEqual(result['selected_events'], 1)
        self.assertEqual(result['oracle_paired_events'], 3); self.assertEqual(result['budget']['total_formal_frame_advances'], 9128)
        self.assertEqual(result['numeric_diagnostic_frame_advances_separate'], 1296)

    def test_zero_eligible_events_are_valid_and_not_filled(self):
        cfg, state, report, read, _ = fixture(False)
        result = verify.verify_records(cfg, state, report, read)
        self.assertEqual(result['selected_events'], 0); self.assertEqual(result['budget']['total_formal_frame_advances'], 9000)

    def test_wrong_fold_or_parameter_rejected(self):
        self.cfg['jobs'][0]['sequence'] = 'SNMOT-060'
        with self.assertRaisesRegex(ValueError, '完整首seed'): self.check()

    def test_GT_guard_open_attempt_is_failure(self):
        first = next(iter(self.report['observe'].values())); self.read(first)['GT_guard']['blocked_open_attempts'] = 1
        with self.assertRaisesRegex(ValueError, 'GT读取保护'): self.check()

    def test_empty_stage_dropped_is_failure(self):
        receipt = self.read(next(iter(self.report['observe'].values()))); logs = self.read(receipt['frames_log']); logs[0]['stages'].pop()
        with self.assertRaisesRegex(ValueError, '三stage'): self.check()

    def test_source_rows_filtered_is_failure(self):
        annotation = self.read(next(iter(self.report['posthoc'].values()))); self.read(annotation['all_rows']).clear()
        with self.assertRaisesRegex(ValueError, '后验行'): self.check()

    def test_plan_cannot_carry_GT_identity(self):
        plan = self.read(next(iter(self.report['plans'].values())))['plans'][0]; plan['GT_id'] = 0
        with self.assertRaisesRegex(ValueError, 'replay计划含GT'): self.check()

    def test_original_branch_output_changed_is_failure(self):
        replay = self.read(next(iter(self.report['replay'].values()))); branch = self.read(replay['events'][0]['branches']['original'])
        self.read(branch['frames_log'])[4]['native_output'] = [[1, 2, 3, 4, 5, 6]]
        with self.assertRaisesRegex(ValueError, '原分支没有'): self.check()

    def test_repair_non_target_fields_is_failure(self):
        replay = self.read(next(iter(self.report['replay'].values()))); branch = self.read(replay['events'][0]['branches']['history_only'])
        branch['intervention']['actual_changed_fields'].append('mean')
        with self.assertRaisesRegex(ValueError, '修复越权'): self.check()

    def test_negative_or_unknown_outcome_tamper_is_failure(self):
        summary = self.read(next(iter(self.report['branch_posthoc'].values())))
        summary['event_records'][0]['branches']['original']['absolute_counts']['unknown_measurement'] = 30
        with self.assertRaises(ValueError): self.check()

    def test_missing_source_CI_cannot_be_invented(self):
        self.report['oracle_summary']['source_level_descriptions'][0]['paired_descriptions'][0]['confidence_intervals'] = {'t95': [0, 1]}
        with self.assertRaisesRegex(ValueError, '描述声明'): self.check()

    def test_three_source_t_bootstrap_leave_one_out_independently_rebuilt(self):
        summary = self.read(next(iter(self.report['branch_posthoc'].values())))
        original = summary['event_records'][0]; records = []
        for index, seq in enumerate(verify.OLD):
            row = deepcopy(original); row['sequence'] = seq; row['event_id'] += str(index)
            # 保留一个有利、一个不利和一个零差的局部修复结果。
            if index == 1:
                row['branches']['original'], row['branches']['history_only'] = row['branches']['history_only'], row['branches']['original']
                row['branches']['original']['exact_original_reproduction'] = True
            if index == 2:
                row['branches']['history_only'] = deepcopy(row['branches']['original'])
            records.append(row)
        result = analysis.summarize_branches(records)
        verify.branch_summary_check(result, records)
        item = result['source_level_descriptions'][0]['paired_descriptions'][0]
        self.assertEqual(item['confidence_intervals']['df'], 2)
        self.assertEqual(item['confidence_intervals']['bootstrap_resamples'], 10000)
        self.assertEqual(item['confidence_intervals']['bootstrap_seed'], 20261028)
        item['confidence_intervals']['bootstrap95'][0] += .1
        with self.assertRaisesRegex(ValueError, '描述数值'): verify.branch_summary_check(result, records)

    def test_worker_exit_and_actual_CIM_identity_not_PID_only(self):
        self.state['worker_exits'][0]['exit_code'] = 1
        with self.assertRaisesRegex(ValueError, 'worker未正常'): self.check()
        state = dict(controller_pid=500, workers=[{'worker_pid': 501}])
        reused = dict(ProcessId=501, ParentProcessId=500, Name='python.exe', CommandLine='user_program.py')
        self.assertTrue(verify.absent([reused], state)['observer_processes_absent'])
        reused['CommandLine'] = 'from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=500)'
        with self.assertRaisesRegex(ValueError, '实际控制器'): verify.absent([reused], state)


if __name__ == '__main__': unittest.main()
