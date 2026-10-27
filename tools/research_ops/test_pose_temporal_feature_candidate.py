"""候选均值通道、时间、缺点和原gate输入必须保持单因素边界。"""
from copy import deepcopy
import unittest
from pose_temporal_feature_candidate import candidate_features,CHANGED_COLUMNS


def record(t,x):
    return dict(timestamp_sec=t,bbox_xywh_px=[0.,0.,100.,100.],geometry_valid=[True]*17,xy_px=[[40.+x,50.] for _ in range(17)])


class Tests(unittest.TestCase):
    def test_only_mean_columns_change_gate_source_original(self):
        raw=[.1]*194;history=[record(0,0),record(1,1),record(2,2)];current=record(3,3);before=deepcopy(history)
        out,gate=candidate_features(raw,history,current,1.)
        self.assertEqual(history,before);self.assertEqual(gate,raw);self.assertIsNot(gate,raw)
        self.assertEqual({k for k in range(194) if out[k]!=raw[k]},set(CHANGED_COLUMNS))
        self.assertAlmostEqual(out[28],-.07)

    def test_missing_latest_point_not_imputed(self):
        raw=[.1]*194;history=[record(0,0),record(1,1),record(2,2)];history[-1]['geometry_valid'][5]=False
        out,_=candidate_features(raw,history,record(3,3),1.)
        self.assertEqual(out[78:80],raw[78:80])
        one,_=candidate_features(raw,history[-1:],record(3,3),1.);self.assertEqual(one,raw)

    def test_no_future_or_reversed_time_and_GT_ignored(self):
        raw=[.1]*194;h=[record(0,0),record(1,1)];c=record(2,2)
        expected=candidate_features(raw,h,c,1.)
        for r in h+[c]:r['gt_id']='forbidden_not_read'
        self.assertEqual(candidate_features(raw,h,c,1.),expected)
        with self.assertRaises(ValueError):candidate_features(raw,list(reversed(h)),c,1.)
        with self.assertRaises(ValueError):candidate_features(raw,h,record(1,1),1.)


if __name__=='__main__':unittest.main()
