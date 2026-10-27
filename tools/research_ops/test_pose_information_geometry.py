"""新信息代理的时间、共同点、打乱和后验标签边界检查。"""
from copy import deepcopy
import unittest
import pose_information_geometry as g


def record(uid,t,x):
    return dict(uid=uid,timestamp_sec=t,bbox_xywh_px=[0.,0.,100.,100.],image_wh=[500,500],score=.9,
                geometry_valid=[True]*17,xy_px=[[40.+x,40.+j] for j in range(17)])


class Tests(unittest.TestCase):
    def test_temporal_order_and_time_difference(self):
        h=[record('a',0,0),record('b',1,1),record('c',2,2)]
        p,n=record('p',3,3),record('n',3,1)
        r=g.shape_pair(h,p,n,1.)
        self.assertTrue(r['available']);self.assertGreater(r['margins']['temporal'],0)
        self.assertLess(r['margins']['mean'],0)
        with self.assertRaises(ValueError):g.shape_pair(list(reversed(h)),p,n,1.)

    def test_shared_points_and_missing_history_not_imputed(self):
        h=[record('a',0,0),record('b',1,1)];p,n=record('p',2,2),record('n',2,1)
        n['geometry_valid'][5:12]=[False]*7
        self.assertFalse(g.shape_pair(h,p,n,1.)['available'])
        self.assertFalse(g.shape_pair(h[-1:],p,n,1.)['available'])

    def test_swap_is_same_frame_no_GT_and_preserves_mask_and_metadata(self):
        frames=[dict(detections=[record('a',0,0),record('b',0,1)]),dict(detections=[record('future',1,2)])]
        before=deepcopy(frames);changed,mapping,reasons=g.same_frame_swaps(frames)
        self.assertEqual(frames,before);self.assertEqual(mapping,{'a':'b','b':'a'})
        self.assertEqual(reasons['future'],'no_same_frame_compatible_donor')
        for original in frames[0]['detections']:
            self.assertEqual({k:v for k,v in g.public(original).items() if k!='xy_px'},
                             {k:v for k,v in changed[original['uid']].items() if k!='xy_px'})
            original['gt_id']='not_read'
        self.assertEqual(g.same_frame_swaps(frames)[1],mapping)

    def test_unknown_and_mixed_histories_are_not_false_labels(self):
        labels={'a':dict(state='matched',gt_id=0),'b':dict(state='matched',gt_id=2),'u':dict(state='unknown_ambiguous')}
        self.assertEqual(g.identity(['a'],labels),(0,'trusted_consistent_history'))
        self.assertEqual(g.identity(['a','b'],labels)[1],'mixed_identity_history')
        self.assertEqual(g.identity(['a','u'],labels)[1],'unknown_history')
        self.assertIsNone(g.label(0,labels['u']));self.assertEqual(g.label(0,labels['b']),0)

    def test_quantile_is_predefined_interpolated(self):
        self.assertEqual(g.quantile([0,1,2,3,4],.25),1)
        self.assertIsNone(g.quantile([],.99))


if __name__=='__main__':unittest.main()
