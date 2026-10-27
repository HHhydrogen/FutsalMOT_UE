"""有界速度不按目标gap放大，原gate和缺点mask保持。"""
import math,unittest
from pose_velocity_feature_candidate import bounded_velocity_features
from test_pose_temporal_feature_candidate import record


class Tests(unittest.TestCase):
    def test_bounded_and_independent_of_target_gap(self):
        raw=[.1]*194;h=[record(0,0),record(.04,20),record(.08,40)]
        a,g=bounded_velocity_features(raw,h,record(.12,50),.5)
        b,_=bounded_velocity_features(raw,h,record(1.28,50),.5)
        self.assertEqual(a,b);self.assertEqual(g,raw)
        for j in range(17):self.assertLessEqual(math.hypot(*a[24+10*j+4:24+10*j+6]),1.)

    def test_missing_speed_zero_mask_not_upgraded(self):
        raw=[.1]*194;h=[record(0,0),record(.04,20),record(.08,40)];h[-1]['geometry_valid'][5]=False
        a,g=bounded_velocity_features(raw,h,record(.12,50),.5)
        self.assertEqual(a[78:80],[0.,0.]);self.assertEqual(a[80:83],raw[80:83]);self.assertEqual(g,raw)


if __name__=='__main__':unittest.main()
