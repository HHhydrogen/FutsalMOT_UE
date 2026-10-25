"""缺点/噪声定向检查：不升级unknown，保持bbox、来源和随机数不变。"""
from pathlib import Path
import random,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'python/src'),str(ROOT/'tools/research_ops')]
from grf_ue_bridge.pose_quality_features_v9 import quality,quality_gate,perturb,restrict,MASK_COLUMNS,COORD_COLUMNS
from grf_ue_bridge.learned_association_features_v8 import features
def record(i):return dict(uid=str(i),bbox_xywh_px=[100.,100.,50.,100.],score=.8,timestamp_sec=i/25,image_wh=[1920,1080],xy_px=[[125.,150.]]*17,geometry_valid=[True]*17)
class Tests(unittest.TestCase):
    def test_quality_zero_missing_and_full_stationary(self):
        h=[record(i) for i in range(3)];c=record(3);raw=features(h,c);self.assertEqual(quality(raw)['common_limbs'],12);self.assertEqual(quality_gate(raw,.03),1)
        c['geometry_valid']=[False]*17;self.assertEqual(quality_gate(features(h,c),.03),0)
    def test_masks_and_coordinates_disjoint(self):
        self.assertEqual(len(MASK_COLUMNS),51);self.assertEqual(len(COORD_COLUMNS),119);self.assertFalse(set(MASK_COLUMNS)&set(COORD_COLUMNS))
        self.assertEqual(restrict([1.]*194,'mask')[:24],[1.]*24);self.assertTrue(all(restrict([1.]*194,'mask')[i]==0 for i in COORD_COLUMNS))
    def test_stateless_corruption_preserves_source_and_invalid(self):
        h=[record(i) for i in range(3)];c=record(3);c['geometry_valid'][0]=False;before=random.getstate();a,b=perturb(h,c,'both');x,y=perturb(h,c,'both')
        self.assertEqual((a,b),(x,y));self.assertEqual(before,random.getstate());self.assertFalse(b['geometry_valid'][0]);self.assertEqual(b['bbox_xywh_px'],c['bbox_xywh_px']);self.assertEqual(c['xy_px'][1],[125.,150.])
    def test_drop_and_both_share_same_drop_realization(self):
        h=[record(i) for i in range(3)];c=record(3);_,drop=perturb(h,c,'drop');_,both=perturb(h,c,'both');self.assertEqual(drop['geometry_valid'],both['geometry_valid'])
if __name__=='__main__':unittest.main()
