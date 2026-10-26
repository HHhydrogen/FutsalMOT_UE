"""绿色预测候选的发布门禁与固定框守恒检查；不导入模型或使用GPU。"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('green_prediction_candidate', Path(__file__).with_name('green_kit_prediction_cache.py'))
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


class GreenPredictionContract(unittest.TestCase):
    def fixtures(self):
        dataset = dict(schema='futsalmot_green_seeded_kit_pair_dataset_v1', status='diagnostic_pair_complete_not_training',
                       rgb_frames=4800, mask_frames=4800, person_pose=48000, not_training=True, MRQ_sync_verified=False)
        publication = dict(status='published_green_16_units_metadata_pair_complete', all_source_UE_normal_exit=True, EXR_retired=4800)
        capture = dict(status='complete_full_16_units_EXR_retired_wait_root_publication',
                       completed=[dict(attempt=str(n), normal_UE_exit=True, EXR_deleted=300,
                                       rgb=300, mask=300, person_pose=3000) for n in range(16)])
        return dataset, publication, capture

    def test_partial_capture_or_unretired_EXR_cannot_start_predictions(self):
        dataset, publication, capture = self.fixtures()
        candidate.publication_gate(dataset, publication, capture)
        capture['completed'].pop()
        with self.assertRaisesRegex(ValueError, '16个'):
            candidate.publication_gate(dataset, publication, capture)
        dataset, publication, capture = self.fixtures()
        capture['completed'][0]['EXR_deleted'] = 299
        with self.assertRaisesRegex(ValueError, '16个'):
            candidate.publication_gate(dataset, publication, capture)

    def test_diagnostic_source_cannot_be_relabeled_as_sync_verified(self):
        dataset, publication, capture = self.fixtures()
        dataset['MRQ_sync_verified'] = True
        with self.assertRaisesRegex(ValueError, '限制不能升级'):
            candidate.publication_gate(dataset, publication, capture)

    def records(self):
        det = dict(uid='S1048_blue_CineCam_01:000001:000000', detection_id='S1048_blue_CineCam_01:000001:000000',
                   bbox_xywh_px=[10., 20., 30., 40.], score=.8, class_id=0)
        plan = dict(logical_sequence='S1048_blue_CineCam_01', detections=[det],
                    frame_index=0, frame_number=1, timestamp_sec=0., width=3840, height=2160)
        prediction = dict(det, image_wh=[3840, 2160], timestamp_sec=0., xy_px=[[20., 30.]] * 17,
                          geometry_valid=[True] * 17, prediction_valid=True, physical_visibility='unknown')
        return plan, prediction

    def test_keeps_frame_zero_and_uid_one_separate_and_all_bbox_fallbacks(self):
        plan, prediction = self.records()
        prediction.update(prediction_valid=False, geometry_valid=[False] * 17, xy_px=[[0., 0.]] * 17)
        row = candidate.fixed_frame(plan, [prediction], Path('new/000000.png'), 'B', 'pose', 'detector')
        self.assertEqual((row['frame_index'], row['frame_number']), (0, 1))
        self.assertEqual(row['detections'][0]['uid'], plan['detections'][0]['uid'])
        self.assertEqual(len(row['detections']), 1)
        self.assertFalse(row['detections'][0]['prediction_valid'])
        self.assertEqual(row['physical_visibility'], 'unknown')

    def test_missing_reordered_or_changed_fixed_detection_is_rejected(self):
        plan, prediction = self.records()
        with self.assertRaisesRegex(ValueError, '数量'):
            candidate.fixed_frame(plan, [], Path('new.png'), 'A', 'p', 'd')
        for key, value in [('uid', 'other'), ('bbox_xywh_px', [10., 20., 30., 41.]), ('score', .81)]:
            changed = deepcopy(prediction); changed[key] = value
            with self.assertRaisesRegex(ValueError, '固定检测'):
                candidate.fixed_frame(plan, [changed], Path('new.png'), 'A', 'p', 'd')
        changed = deepcopy(prediction); changed['xy_px'][0] = [float('nan'), 0.]
        with self.assertRaisesRegex(ValueError, '格式'):
            candidate.fixed_frame(plan, [changed], Path('new.png'), 'A', 'p', 'd')


if __name__ == '__main__':
    unittest.main()
