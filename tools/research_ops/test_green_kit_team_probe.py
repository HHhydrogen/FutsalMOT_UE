"""固定标签与队伍归属分层，缺点仍进入原分母，不挑有效样本。"""
from collections import defaultdict
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('green_team_contract', Path(__file__).with_name('green_kit_team_probe.py'))
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)


class TeamProbeContract(unittest.TestCase):
    def test_identity_same_team_cross_team_unmatched_and_unknown_are_distinct(self):
        self.assertEqual(probe.category('L1', dict(state='matched', gt_id='L1'), 1), 'same_identity_positive')
        self.assertEqual(probe.category('L1', dict(state='matched', gt_id='L4'), 0), 'same_team_negative')
        self.assertEqual(probe.category('L1', dict(state='matched', gt_id='R4'), 0), 'cross_team_negative')
        self.assertEqual(probe.category('L1', dict(state='unmatched', gt_id=None), 0), 'unmatched_negative')
        self.assertEqual(probe.category('L1', dict(state='unknown_conflict', gt_id=None), None), 'unknown_label_retained')
        with self.assertRaises(ValueError):
            probe.category('L1', dict(state='matched', gt_id='R4'), 1)

    def test_zero_valid_points_remain_in_denominator_and_mean_is_null(self):
        a = dict(geometry_valid=[False]*17, xy_px=[[0., 0.]]*17, bbox_xywh_px=[1., 2., 3., 4.])
        counter = defaultdict(float); probe.accumulate(counter, a, a)
        value = probe.summarize(counter)
        self.assertEqual(value['candidate_pair_occurrences'], 1)
        self.assertEqual(value['A_geometry_valid_fraction'], 0.)
        self.assertIsNone(value['AB_mean_common_point_delta_px'])

    def test_point_difference_is_normalized_by_fixed_box_height(self):
        a = dict(geometry_valid=[True]*17, xy_px=[[0., 0.]]*17, bbox_xywh_px=[1., 2., 3., 10.])
        b = dict(a, xy_px=[[3., 4.]]*17)
        counter = defaultdict(float); probe.accumulate(counter, a, b); value = probe.summarize(counter)
        self.assertEqual(value['common_valid_limb_point_occurrences'], 12)
        self.assertEqual(value['AB_mean_common_point_delta_px'], 5.)
        self.assertEqual(value['AB_mean_common_point_delta_bbox_height'], .5)


if __name__ == '__main__':
    unittest.main()
