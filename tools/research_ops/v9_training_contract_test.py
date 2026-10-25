"""新消融的窗口标签、同观测扰动和主/探索矩阵一次针对检查。"""
from copy import deepcopy
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'python/src'),str(ROOT/'tools/research_ops')]
import torch
from v9_train import Cache
from v9_control import expected_matrix
from grf_ue_bridge.quality_residual_association_v9 import Adapter
from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer
from grf_ue_bridge.learned_association_features_v8 import features
def record(i):return dict(uid=str(i),bbox_xywh_px=[100.,100.,50.,100.],score=.8,timestamp_sec=i/25,image_wh=[1920,1080],xy_px=[[125.,150.]]*17,geometry_valid=[True]*17)
class Tests(unittest.TestCase):
    def test_declared_matrix_balances_regimes_without_selecting_seed(self):
        jobs=expected_matrix();self.assertEqual(len(jobs),78);self.assertEqual(len({tuple(sorted(r.items())) for r in jobs}),78);self.assertTrue(all(r['variant'] in ('motion_residual','robust','gated') for r in jobs[:54]));self.assertEqual({r['seed'] for r in jobs[54:]},{20261024});self.assertEqual(sum(r['regime']=='RS' for r in jobs),39)
    def test_corruption_keeps_window_labels_and_motion_input(self):
        history=[record(i) for i in range(3)];c=record(3);w=dict(window_uid='w',history=history,candidates=[dict(prediction=c,label=1),dict(prediction=record(4),label=0),dict(prediction=record(5),label=None)])
        original=deepcopy(w);pools=dict(real={'w':w},synthetic={'w':w});adapter=Adapter(FeatureNormalizer.fit([features(history,c)]),.05);row=dict(window_uid='w',epoch=0);got={v:Cache(pools,adapter,v,20261024).get('real',row) for v in ('raw','drop','jitter','robust','gated')}
        self.assertTrue(all(v['known_pairs']==2 and v['candidate_pairs']==3 and torch.equal(v['labels'],got['raw']['labels']) for v in got.values()));self.assertTrue(torch.equal(got['robust']['x'],got['gated']['x']))
        self.assertTrue(all(torch.equal(v['x'][:,:24],got['raw']['x'][:,:24]) for v in got.values()));self.assertEqual(w,original)
    def test_count_aggregate_boundary_in_v9(self):
        from v9_metric import validate_count
        validate_count('COMBINED_SEQ',dict(Dets=2,GT_Dets=3),2,3,'SNMOT-060')
        with self.assertRaises(ValueError):validate_count('SNMOT-060',dict(Frames=749,Dets=2,GT_Dets=3),2,3,'SNMOT-060')
if __name__=='__main__':unittest.main()
