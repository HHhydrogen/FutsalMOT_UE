"""有界状态后验的定向合同；不读取模型、图像、封存测试或实际GT。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state_gap_analysis as core


META = dict(job_id='R_game4_s20261024_SNMOT-097', model_id='R_game4_s20261024',
    fold='game4', regime='R', seed=20261024, sequence='SNMOT-097')


def source_fixture(length=34):
    raw, gt = [], {}
    for number in range(1, length+1):
        detections = [dict(uid=f'p{number}', bbox_xywh_px=[0., 0., 10., 10.], timestamp_sec=(number-1)/25.),
            dict(uid=f'n{number}', bbox_xywh_px=[30., 0., 10., 10.], timestamp_sec=(number-1)/25.)]
        raw.append(dict(frame_number=number, detections=detections))
        gt[number] = [dict(gt_id=0, bbox_xywh_px=[0., 0., 10., 10.]),
            dict(gt_id=1, bbox_xywh_px=[30., 0., 10., 10.])]
    return core.build_label_index(raw, gt)


def rollout_fixture():
    frames = []
    for number in range(1, 35):
        history = [f'p{i}' for i in range(max(1, number-3), number)]
        uid = 'n4' if number == 4 else f'p{number}'
        frames.append(dict(frame_number=number, tracks_before=[dict(track_id=7, history_UIDs=history)],
            observations=[dict(track_id=7, uid=uid, event='activate' if number == 1 else 'update')],
            tracks_after=[dict(track_id=7, history_UIDs=[uid], list_membership='tracked_stracks', state=1)],
            stages=[dict(stage='high_score', track_ids=[7] if number > 1 else [], history_UIDs=[history] if number > 1 else [],
                candidate_UIDs=[f'p{number}', f'n{number}'],
                assignment={'matches': [[0, 1 if number == 4 else 0]] if number > 1 else []})], lifecycle=[]))
    return frames


class StateGapPosthocContracts(unittest.TestCase):
    def test_mutual_unique_exact_threshold_ID0_and_conflict_unknown(self):
        gt = [dict(gt_id=0, bbox_xywh_px=[0., 0., 10., 10.])]
        labels = core.match_labels([dict(uid='a', bbox_xywh_px=[0., 0., 10., 5.])], gt)
        self.assertEqual(labels['a'], dict(state='matched', gt_id='0'))
        labels = core.match_labels([dict(uid=uid, bbox_xywh_px=[0., 0., 10., 10.]) for uid in ('a', 'b')], gt)
        self.assertEqual({value['state'] for value in labels.values()}, {'unknown_conflict'})
        labels = core.match_labels([dict(uid='a', bbox_xywh_px=[0., 0., 10., 2.]),
            dict(uid='b', bbox_xywh_px=[30., 0., 10., 10.])], gt)
        self.assertEqual(labels['a']['state'], 'unknown_low_overlap')
        self.assertEqual(labels['b']['state'], 'unmatched')

    def test_label_index_no_GT_coordinates_and_full_empty_frame_denominator(self):
        source = core.build_label_index([dict(frame_number=1, detections=[])], {1: [dict(gt_id=0, bbox_xywh_px=[0., 0., 1., 1.])]})
        self.assertEqual(source['counts']['frames'], 1)
        self.assertEqual(source['counts']['raw'], 0)
        self.assertEqual(source['counts']['GT_rows'], 1)
        self.assertFalse(source['GT_coordinates_in_result'])
        self.assertEqual(source['GT_presence'], {(1, '0')})

    def test_mixed_unknown_history_cannot_be_last_GT_query(self):
        source = source_fixture()
        self.assertEqual(core.history_status(['p1', 'n2', 'p3'], source['labels'])['state'], 'mixed_trusted_history')
        self.assertIsNone(core.history_status(['p1', 'missing', 'p3'], source['labels'])['gt_id'])
        self.assertIsNone(core.candidate_label(None, source['labels']['p1']))

    def test_clean_pool_retains_no_positive_unknown_and_gap_absolute(self):
        windows = [dict(window_uid='one', sequence='SNMOT-097', history_UIDs=['p1', 'p2', 'p3'],
            history_frame_indices=[0, 1, 2], candidate_frame_number=9, candidate_UIDs=['n9', 'u9'], labels=[0, None])]
        value = core.summarize_clean_windows(windows)
        row = value['rows'][0]
        self.assertTrue(row['no_positive'])
        self.assertEqual(row['known_negative'], 1)
        self.assertEqual(row['unknown'], 1)
        self.assertEqual(row['actual_observation_gap_frames'], 6)
        self.assertTrue(row['history_consecutive'])
        self.assertEqual(value['summary']['absolute_counts']['windows'], 1)

    def test_native_assignment_and_empty_matrix_are_preserved_no_new_solver(self):
        source = source_fixture()
        stage = dict(frame_number=4, stage='high', track_ids=[7], history_UIDs=[['p1', 'p2', 'p3']],
            candidate_UIDs=['p4', 'n4'], assignment={'matches': [[0, 1]]}, active_rows=[True],
            lost_gap=[False], motion_gate=[[True, False]], enabled=[[True, False]])
        result = core.annotate_stage(stage, source, META)
        row = result['rows'][0]
        self.assertEqual(row['selected_UID'], 'n4')
        self.assertEqual(row['selected_label'], 0)
        self.assertTrue(row['positive_motion_gate'])
        self.assertEqual(result['new_solver_calls'], 0)
        stage.update(track_ids=[], history_UIDs=[], assignment={'matches': []}, active_rows=[], lost_gap=[])
        result = core.annotate_stage(stage, source, META)
        self.assertTrue(result['empty_stage_record']['empty_matrix'])
        self.assertEqual(result['empty_stage_record']['candidate_columns'], 2)
        self.assertEqual(result['rows'], [])

    def test_strict_first_switch_uses_past3_not_last_GT_and_tail30(self):
        result = core.select_first_errors(rollout_fixture(), source_fixture(), META)
        self.assertEqual(len(result['events']), 1)
        event = result['events'][0]
        self.assertTrue(event['candidate_eligible'])
        self.assertEqual(event['anchor_GT_id'], '0')
        self.assertEqual(event['wrong_uid'], 'n4')
        self.assertEqual(event['correct_uid'], 'p4')
        self.assertEqual(event['available_future_source_frames'], 30)
        self.assertEqual(event['pre_error_history_UIDs'], ['p1', 'p2', 'p3'])
        self.assertEqual(result['tracks'][0]['observations'], 34)

    def test_prior_unknown_never_silently_becomes_first_known_error(self):
        source = source_fixture()
        source['labels']['p1']['state'] = 'unknown_conflict'
        frames = rollout_fixture()
        # 第4帧history未知；第5帧三条可信history首次建锚，早先unknown仍保留。
        frames[3]['observations'][0]['uid'] = 'p4'
        frames[4]['observations'][0]['uid'] = 'n5'
        source['frame_rows'].append(dict(frame_number=35))
        event = core.select_first_errors(frames, source, META)['events'][0]
        self.assertFalse(event['candidate_eligible'])
        self.assertEqual(event['first_error_status'], 'unknown')
        self.assertIn('first_error_status_unknown_prior_observation', event['exclusion_reasons'])

    def test_tail_insufficient_is_preserved_but_not_selected(self):
        source = source_fixture(33)
        event = core.select_first_errors(rollout_fixture()[:33], source, META)['events'][0]
        self.assertIn('fewer_than30_future_source_frames', event['exclusion_reasons'])
        self.assertFalse(event['candidate_eligible'])

    def test_fixed_cap_R_RS_together_no_reward_selection_or_quota_fill(self):
        base = core.select_first_errors(rollout_fixture(), source_fixture(), META)['events'][0]
        events = [dict(deepcopy(base), event_id=f'e{i}', frame_number=4+i, track_id=7+i,
            regime='RS' if i%2 else 'R') for i in range(23)]
        value = core.select_bounded_events(list(reversed(events)))
        self.assertEqual(len(value['selected']), 20)
        self.assertEqual(value['absolute_counts']['game6'], 0)
        self.assertEqual(len(value['events']), 23)
        self.assertFalse(value['quota_filled_by_duplication'])
        self.assertEqual([row['frame_number'] for row in value['selected']], list(range(4, 24)))

    def test_oracle_plan_current_raw_only_no_anchor_GT_coordinates_or_future(self):
        source = source_fixture()
        event = core.select_first_errors(rollout_fixture(), source, META)['events'][0]
        event['selected'] = True
        plan = core.oracle_plan(event, source)
        self.assertNotIn('anchor_GT_id', plan)
        self.assertNotIn('bbox_xywh_px', plan)
        self.assertFalse(plan['future_information_used'])
        self.assertEqual(plan['replay_frames_after_event'], 30)
        self.assertEqual(plan['branches'], list(core.BRANCHES))
        self.assertIn('keep_length', plan['history_rule'])
        self.assertIn('predicted_mean_cov', plan['motion_rule'])

    def test_branch_unknown_unmatched_counts_not_false_success_and_right_censoring(self):
        source = source_fixture()
        frames = [dict(frame_number=number, observations=[]) for number in range(5, 35)]
        frames[0]['observations'] = [dict(track_id=7, uid='n5')]
        frames[1]['observations'] = [dict(track_id=7, uid='p6')]
        value = core.branch_outcomes(frames, source, 7, '0', 4)
        self.assertEqual(value['absolute_counts']['other_trusted_identity'], 1)
        self.assertEqual(value['absolute_counts']['same_trusted_anchor'], 1)
        self.assertEqual(value['absolute_counts']['unmatched_or_no_measurement'], 28)
        self.assertEqual(value['first_trusted_recovery_offset_frames'], 2)
        self.assertFalse(value['recovery_time_right_censored'])
        value = core.branch_outcomes([dict(frame_number=i, observations=[]) for i in range(5, 35)], source, 7, '0', 4)
        self.assertTrue(value['recovery_time_right_censored'])
        self.assertIsNone(value['first_trusted_recovery_offset_frames'])

    def test_summary_requires_exact_original_and_all_four_same_frames(self):
        source = source_fixture()
        value = core.branch_outcomes([dict(frame_number=i, observations=[]) for i in range(5, 35)], source, 7, '0', 4)
        event = dict(META, event_id='e', track_id=7, frame_number=4, branches={name: deepcopy(value) for name in core.BRANCHES})
        with self.assertRaises(ValueError): core.summarize_branches([event])
        event['branches']['original']['exact_original_reproduction'] = True
        summary = core.summarize_branches([event])
        self.assertEqual(summary['event_count'], 1)
        self.assertEqual(len(summary['paired_events']), 3)
        self.assertIsNone(summary['confidence_intervals'])
        self.assertIsNone(summary['performance_pass_flag'])
        event['branches']['history_only']['rows'].pop()
        with self.assertRaises(ValueError): core.summarize_branches([event])

    def test_actual_rollout_schema_conversion_real_assignment_and_birth(self):
        before = dict(track_id=7, history_UIDs=['p1', 'p2', 'p3'], state=1, is_activated=True,
            record={'uid': 'p3'})
        after = dict(before, history_UIDs=['p2', 'p3', 'n4'], record={'uid': 'n4'})
        frame = dict(frame_number=4, frame_index=3,
            tracks_before=dict(tracked_stracks=[before], lost_stracks=[], removed_stracks=[]),
            tracks_after=dict(tracked_stracks=[after], lost_stracks=[], removed_stracks=[]),
            stages=[dict(stage='high_score', track_ids=[7], rows=[before], candidate_UIDs=['p4', 'n4'],
                assignments=[[0, 1]], unmatched_track_rows=[], unmatched_detection_columns=[0],
                gates=[[True, True]], enabled=[[True, True]], active=[True], lost_gap=[False])],
            lifecycle=[dict(operation='update', track_id=7, frame_number=4, before=before, after=after)])
        normalized = core.normalize_rollout_frame(frame)
        self.assertEqual(normalized['observations'], [dict(track_id=7, uid='n4', event='update', before=before, after=after)])
        self.assertEqual(normalized['stages'][0]['assignment']['matches'], [[0, 1]])
        self.assertEqual(normalized['tracks_after'][0]['list_membership'], 'tracked_stracks')
        self.assertEqual(core.normalize_rollout_frame(normalized), normalized)
        result = core.annotate_rollout([frame], source_fixture(), META)
        self.assertEqual(result['rows'][0]['selected_UID'], 'n4')
        self.assertEqual(result['lifecycle_counts']['update'], 1)
        frames = rollout_fixture(); frames[3] = frame
        event = core.select_first_errors(frames, source_fixture(), META)['events'][0]
        self.assertTrue(event['candidate_eligible'])

    def test_correct_raw_below_native_policy_and_removed_track_not_replay_eligible(self):
        frames = rollout_fixture()
        frames[3]['stages'][0]['candidate_UIDs'] = ['n4']
        frames[3]['stages'][0]['assignment']['matches'] = [[0, 0]]
        frames[3]['tracks_after'][0]['list_membership'] = 'removed_stracks'
        event = core.select_first_errors(frames, source_fixture(), META)['events'][0]
        self.assertFalse(event['candidate_eligible'])
        self.assertIn('correct_raw_not_initialized_by_original_score_policy', event['exclusion_reasons'])
        self.assertIn('target_not_unique_tracked_after_wrong_frame', event['exclusion_reasons'])

    def test_actual_observer_low_score_row_with_null_gate_lost_gap(self):
        before = dict(track_id=7, history_UIDs=['p1', 'p2', 'p3'], state=1, is_activated=True,
            record={'uid': 'p3'})
        after = dict(before, history_UIDs=['p2', 'p3', 'n4'], record={'uid': 'n4'})
        frame = dict(frame_number=4, frame_index=3,
            tracks_before=dict(tracked_stracks=[before], lost_stracks=[], removed_stracks=[]),
            tracks_after=dict(tracked_stracks=[after], lost_stracks=[], removed_stracks=[]),
            stages=[dict(stage='low_score', stage_index=1, track_ids=[7], rows=[before],
                candidates=[dict(uid='p4'), dict(uid='n4')], candidate_UIDs=['p4', 'n4'],
                assignments=[[0, 1]], unmatched_track_rows=[], unmatched_detection_columns=[0],
                gates=None, enabled=None, active=[False], lost_gap=None,
                enough_history=[True], reference_cost=[[.4, .2]], threshold=.5)],
            lifecycle=[dict(operation='update', track_id=7, frame_number=4, before=before, after=after)])
        normalized = core.normalize_rollout_frame(frame)
        self.assertIsNone(normalized['stages'][0]['lost_gap'])
        self.assertIsNone(normalized['stages'][0]['motion_gate'])
        result = core.annotate_rollout([frame], source_fixture(), META)
        row = result['rows'][0]
        self.assertIsNone(row['lost_gap'])
        self.assertIsNone(row['positive_motion_gate'])
        self.assertIsNone(row['positive_effectively_enabled'])
        self.assertFalse(row['learned_active'])
        self.assertEqual(row['learned_inactive_reason'], 'low_score_bbox_only')
        self.assertEqual(row['selected_UID'], 'n4')
        self.assertEqual(row['selected_label'], 0)
        self.assertEqual(result['stage_records'][0]['actual_matches'], 1)

    def test_three_source_descriptive_CI_no_event_pseudoreplication_and_missing_source_null(self):
        value = core.source_intervals({'SNMOT-060': -1., 'SNMOT-097': -2., 'SNMOT-151': -3.})
        self.assertEqual(value['mean'], -2.)
        self.assertEqual(value['confidence_intervals']['df'], 2)
        self.assertEqual(value['confidence_intervals']['bootstrap_seed'], 20261028)
        self.assertEqual(value['leave_one_source_out']['SNMOT-060'], -2.5)
        self.assertTrue(value['descriptive_only'])
        missing = core.source_intervals({'SNMOT-060': 0., 'SNMOT-097': 0.})
        self.assertIsNone(missing['confidence_intervals'])
        self.assertEqual(missing['missing_sources'], ['SNMOT-151'])

    def test_absolute_four_branch_source_means_preserve_negative_effects(self):
        source = source_fixture()
        baseline = core.branch_outcomes([dict(frame_number=i, observations=[]) for i in range(5, 35)], source, 7, '0', 4)
        events = []
        for index, sequence in enumerate(('SNMOT-060', 'SNMOT-097', 'SNMOT-151')):
            event = dict(META, sequence=sequence, event_id=f'e{index}', track_id=7, frame_number=4,
                branches={name: deepcopy(baseline) for name in core.BRANCHES})
            event['branches']['original']['exact_original_reproduction'] = True
            # history修复人为多出1/2/3个trustedwrong，是负结果，不能只保留成功事件。
            branch = event['branches']['history_only']
            for row in branch['rows'][:index+1]: row['outcome'] = 'other_trusted_identity'
            branch['absolute_counts']['other_trusted_identity'] = index+1
            branch['absolute_counts']['unmatched_or_no_measurement'] -= index+1
            events.append(event)
        summary = core.summarize_branches(events)
        all_selected = summary['source_level_descriptions'][0]
        delta = next(row for row in all_selected['paired_descriptions']
            if row['comparison'] == 'history_only-original' and row['metric'] == 'other_trusted_identity')
        self.assertEqual(delta['mean'], 2.)
        absolute = next(row for row in all_selected['absolute_four_branches']
            if row['branch'] == 'history_only' and row['metric'] == 'other_trusted_identity')
        self.assertEqual(absolute['equal_source_mean'], 2.)
        self.assertIsNone(summary['source_level_descriptions'][2]['paired_descriptions'][0]['confidence_intervals'])
        self.assertEqual(len(summary['paired_events']), 9)


if __name__ == '__main__':
    unittest.main()
