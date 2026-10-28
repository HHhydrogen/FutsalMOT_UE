"""新旁观/快照/oracle合同；合成预测夹具不是实际六模型数值准入。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'python/src'))
import state_gap_rollout as rollout


def fixture():
    import torch
    from grf_ue_bridge import learned_association_tracker_v8 as source
    from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer
    from ultralytics.trackers.basetrack import BaseTrack
    model = torch.nn.Linear(194, 1, dtype=torch.float32)
    with torch.no_grad():
        model.weight.zero_()
        model.bias.fill_(2.)
    normalizer = FeatureNormalizer([0.]*194, [1.]*194, 1)
    cls = source.tracker_class()
    def factory():
        return cls(mode='learned', model=model, normalizer=normalizer, use_pose=False,
            pose_source_sha256='a'*64, fixed_detection_sha256='b'*64)
    frames = []
    for i in range(11):
        detections = []
        boxes = [('a', 10.+2*i), ('b', 150.-2*i)]
        if i >= 3:
            boxes.append(('c', 19.+2*(i-3)))
        if i == 6:
            boxes = []
        for name, x in boxes:
            score = .2 if i == 8 and name == 'a' else .9
            detections.append(dict(uid=name+'_'+str(i), detection_id=name+'_'+str(i),
                bbox_xywh_px=[x+.1234567, 20.125, 20.234567, 60.345678], score=score,
                xy_px=[[x+10., 40.]]*17, geometry_valid=[True]*17,
                timestamp_sec=i/25, image_wh=[320, 240]))
        frames.append(dict(sequence='SNMOT-060', game='game4', fps=25, frame_index=i,
            frame_number=i+1, timestamp_sec=i/25, width=320, height=240, detections=detections))
    return factory, frames, source, BaseTrack


class RolloutContracts(unittest.TestCase):
    def setUp(self):
        import torch
        torch.set_num_threads(1)

    def test_observer_matches_unwrapped_all_native_outputs_and_audit(self):
        import torch
        factory, frames, source, IDs = fixture()
        original = factory()
        with torch.no_grad():
            native = [rollout.plain(original.update_frame(frame)) for frame in frames]
        state = rollout.export_snapshot(original, id_class=IDs)
        wrapped = factory()
        payload = rollout.run_rollout(wrapped, frames, observer_kwargs={'feature_module': source}, id_class=IDs)
        self.assertEqual(native, payload['native_frames'])
        self.assertEqual(original.audit, wrapped.audit)
        self.assertEqual(state, rollout.export_snapshot(wrapped, id_class=IDs))
        self.assertEqual([['high_score','low_score','unconfirmed']]*len(frames),
                         [[stage['stage'] for stage in frame['stages']] for frame in payload['frame_states']])
        self.assertTrue(any(0 in stage['cost_shape'] for frame in payload['frame_states'] for stage in frame['stages']))
        self.assertTrue(any(event['operation'] == 'activate' for frame in payload['frame_states'] for event in frame['lifecycle']))
        self.assertTrue(any(event['operation'] == 'mark_lost' for frame in payload['frame_states'] for event in frame['lifecycle']))

    def test_hooks_restore_even_on_failure(self):
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.trackers.utils import matching
        factory, frames, source, IDs = fixture()
        tracker = factory()
        original = (type(tracker).get_dists, type(tracker).init_track, BYTETracker.get_dists,
                    matching.iou_distance, matching.linear_assignment)
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with rollout.Observer(tracker, feature_module=source) as observer:
                observer.step(frames[0])
                raise RuntimeError('fixture')
        self.assertEqual(original, (type(tracker).get_dists, type(tracker).init_track,
            BYTETracker.get_dists, matching.iou_distance, matching.linear_assignment))

    def test_portable_snapshot_restores_global_ID_alias_and_full_continuation(self):
        factory, frames, source, IDs = fixture()
        tracker = factory()
        rollout.run_rollout(tracker, frames[:3], observer_kwargs={'feature_module': source}, id_class=IDs)
        saved = rollout.export_snapshot(tracker, id_class=IDs)
        portable = json.loads(json.dumps(saved, allow_nan=False))
        continuation = rollout.run_rollout(tracker, frames[3:], observer_kwargs={'feature_module': source}, id_class=IDs)
        restored = rollout.import_snapshot(portable, factory, id_class=IDs)
        self.assertEqual(type(tracker.tracked_stracks[0].score), type(restored.tracked_stracks[0].score))
        self.assertEqual(type(tracker.tracked_stracks[0].idx), type(restored.tracked_stracks[0].idx))
        reproduced = rollout.run_rollout(restored, frames[3:], observer_kwargs={'feature_module': source}, id_class=IDs)
        self.assertEqual(continuation, reproduced)
        self.assertEqual(saved, portable)
        # 明确验证跨列表相同object保持别名，不能仅按track_id重建两个对象。
        alias_tracker = factory()
        rollout.run_rollout(alias_tracker, frames[:1], observer_kwargs={'feature_module': source}, id_class=IDs)
        alias_tracker.lost_stracks.append(alias_tracker.tracked_stracks[0])
        alias_saved = rollout.export_snapshot(alias_tracker, id_class=IDs)
        alias_restored = rollout.import_snapshot(alias_saved, factory, id_class=IDs)
        self.assertIs(alias_restored.tracked_stracks[0], alias_restored.lost_stracks[0])

    def test_four_branches_only_change_allowed_state_and_original_is_exact(self):
        factory, frames, source, IDs = fixture()
        snapshots = {}
        tracker = factory()
        baseline = rollout.run_rollout(tracker, frames, observer_kwargs={'feature_module': source}, id_class=IDs,
            snapshot_frames={4}, snapshot_sink=lambda number, value: snapshots.setdefault(number,value))
        event_frame = baseline['frame_states'][3]
        target = next(event for event in event_frame['lifecycle']
                      if event['operation']=='update' and event['after']['record']['uid']=='a_3')
        plan = dict(event_id='synthetic_local_surgery',frame_number=4,track_id=target['track_id'],wrong_uid='a_3',correct_uid='c_3')
        kwargs = dict(new_tracker=factory, observer_kwargs={'feature_module':source}, id_class=IDs,
            expected_error_log=event_frame, expected_native_frames=baseline['native_frames'][3:],
            expected_state_hashes=[frame['full_state_sha256'] for frame in baseline['frame_states'][3:]])
        branches = {name: rollout.replay_branch(snapshots[4], frames[3:], plan, branch=name, **kwargs)
                    for name in ('original','history_only','motion_only','both')}
        self.assertTrue(branches['original']['original_branch_exact_checked'])
        self.assertEqual([],branches['original']['intervention']['actual_changed_fields'])
        self.assertEqual(['history'],branches['history_only']['intervention']['actual_changed_fields'])
        self.assertIn('mean',branches['motion_only']['intervention']['actual_changed_fields'])
        self.assertEqual(['mean','covariance'],branches['motion_only']['intervention']['allowed_fields'])
        # 同prior下Kalman协方差不依赖measurement中心，不能强求两个允许字段都数值改变。
        self.assertTrue(all(value['intervention']['non_target_fields_unchanged'] for value in branches.values()))
        self.assertEqual(3,branches['both']['intervention']['history_length'])

    def test_oracle_plan_rejects_GT_payload(self):
        factory, frames, source, IDs = fixture()
        tracker = factory()
        with rollout.Observer(tracker, feature_module=source) as observer:
            for frame in frames[:4]:
                observer.step(frame)
            plan = dict(frame_number=4,track_id=1,wrong_uid='a_3',correct_uid='c_3',GT_id=8)
            record=rollout.public_record(frames[3]['detections'][2]);record['_frame_index']=3
            with self.assertRaisesRegex(ValueError,'不能携带GT'):
                rollout.apply_oracle_repair(tracker,observer,plan,record,branch='history_only',id_class=IDs)

    def test_replay_requires_contiguous_bounded_frames_and_original_reference(self):
        factory, frames, source, IDs = fixture()
        tracker=factory();saved=rollout.export_snapshot(tracker,id_class=IDs)
        plan=dict(frame_number=1,track_id=1,wrong_uid='a_0',correct_uid='b_0')
        with self.assertRaisesRegex(ValueError,'不连续'):
            rollout.replay_branch(saved,[frames[0],frames[2]],plan,new_tracker=factory,id_class=IDs)
        with self.assertRaisesRegex(ValueError,'后30帧'):
            rollout.replay_branch(saved,frames*3,plan,new_tracker=factory,id_class=IDs)


if __name__ == '__main__':
    unittest.main()
