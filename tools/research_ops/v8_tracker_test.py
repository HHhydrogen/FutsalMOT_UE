"""v8新增集成定向CPU检查；小文本预测，无真实媒体/GT/优化更新。"""
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'python/src'),str(ROOT/'tools/research_ops'),str(Path('D:/projects/FutsalMOT_Research/runtime_dependencies'))]
os.environ.update(YOLO_AUTOINSTALL='false',YOLO_CONFIG_DIR='D:/projects/FutsalMOT_Research/pose/learned_association_v8/_runtime/ultralytics',CUDA_VISIBLE_DEVICES='-1')
import numpy as np
from grf_ue_bridge.learned_association_tracker_v8 import tracker_class,intervention_mask,FIXED_ARGS
from grf_ue_bridge.learned_association_model_v8 import make_model,FEATURE_DIM
from v8_train import domain_loss

def frames():
    for i,score in enumerate((.9,.9,.2,.9,.9)):
        d=dict(uid=str(i),detection_id=str(i),bbox_xywh_px=[100.+i,100.,50.,100.],score=score,xy_px=[[125.+i,150.]]*17,geometry_valid=[True]*17,timestamp_sec=i/25,image_wh=[1920,1080])
        yield dict(sequence='SNMOT-060',game='game4',frame_index=i,frame_number=i+1,fps=25,timestamp_sec=i/25,width=1920,height=1080,detections=[d])
class Tests(unittest.TestCase):
    def test_bbox_exact_upstream_and_actual_history(self):
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.engine.results import Boxes
        expected=[];reference=BYTETracker(SimpleNamespace(**FIXED_ARGS))
        for f in frames():
            d=f['detections'][0];x,y,w,h=d['bbox_xywh_px'];expected.append(reference.update(Boxes(np.array([[x,y,x+w,y+h,d['score'],0]],dtype=np.float32),(1080,1920))).copy())
        tracker=tracker_class()(mode='PT_bbox',fixed_detection_sha256='a'*64)
        for f,value in zip(frames(),expected):self.assertTrue(np.array_equal(tracker.update_frame(f),value))
        static=tracker_class()(mode='PT_static_pose',fixed_detection_sha256='a'*64,pose_source_sha256='b'*64)
        for f in frames():static.update_frame(f)
        # .2低分经原fuse_score成本>.5未匹配；真实reactivation必须清空旧history。
        self.assertEqual([r['_frame_index'] for r in static.tracked_stracks[0].history],[3,4])
        self.assertEqual(static.tracked_stracks[0].track_id,1)
    def test_easy_unique_unchanged_competition_and_lost_gate(self):
        base=np.array([[.1,.95],[.95,.1]]);gate=np.ones((2,2),dtype=bool)
        enabled,active,_=intervention_mask(base,gate,[False,False],[True,True],0);self.assertFalse(any(active));self.assertFalse(enabled.any())
        enabled,active,_=intervention_mask(base,gate,[True,False],[True,True],0);self.assertEqual(active,[True,False]);self.assertTrue(enabled[0].all())
        enabled,active,_=intervention_mask(np.full((2,2),.4),gate,[False]*2,[True]*2,0);self.assertEqual(active,[True,True])
    def test_window_mean_not_candidate_mean_and_gradients(self):
        import torch
        from torch.nn import functional as F
        torch.set_num_threads(1);model=make_model(20261024)
        a=dict(x=torch.zeros(1,FEATURE_DIM),labels=torch.ones(1));b=dict(x=torch.ones(3,FEATURE_DIM),labels=torch.zeros(3))
        expected=(F.binary_cross_entropy_with_logits(model(a['x']).reshape(-1),a['labels'])+F.binary_cross_entropy_with_logits(model(b['x']).reshape(-1),b['labels']))/2
        loss=domain_loss(model,[a,b]);self.assertTrue(torch.equal(loss,expected));loss.backward();self.assertTrue(all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()))
if __name__=='__main__':unittest.main()
