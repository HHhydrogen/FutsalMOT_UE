"""v8共享特征/模型定向CPU检查；无optimizer step、无数据集/GPU读取。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'python/src'))
from grf_ue_bridge.learned_association_features_v8 import features,candidate_gate,FEATURE_DIM,POSE_COLUMNS
from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer,make_model,probability_to_cost,window_BCE

def record(t,x=100.):
    return dict(uid='audit-only',game='must-not-leak',gt_id=991,bbox_xywh_px=[x,100.,50.,100.],score=.9,timestamp_sec=t,image_wh=[1920,1080],xy_px=[[x+25.,150.]]*17,geometry_valid=[True]*17)
class SharedTests(unittest.TestCase):
    def test_dimension_and_identity_absolute_time_not_features(self):
        history=[record(i/25,100.+i) for i in range(3)];candidate=record(3/25,103.);expected=features(history,candidate)
        changed=deepcopy(history);other=deepcopy(candidate)
        for item in changed+[other]:item.update(uid='different',game='heldout',gt_id=-500,timestamp_sec=item['timestamp_sec']+100)
        actual=features(changed,other);self.assertEqual(len(expected),FEATURE_DIM);self.assertEqual(len(POSE_COLUMNS),170)
        self.assertTrue(all(abs(a-b)<1e-10 for a,b in zip(expected,actual)))
    def test_gate_exact_parameters_and_velocity_bound(self):
        history=[record(0.,100.),record(.04,1000.),record(.08,1100.)];candidate=record(.12,1140.)
        gate=candidate_gate(history,candidate);self.assertLessEqual(sum(v*v for v in gate['velocity_xy_per_sec'])**.5,1000.+1e-10)
        self.assertFalse(candidate_gate(history,record(2.,1100.))['accepted']);self.assertFalse(candidate_gate(history,record(.12,1900.))['accepted'])
        large=record(.12,1100.);large['bbox_xywh_px'][2]*=5;self.assertEqual(candidate_gate(history,large)['reason'],'area_ratio')
    def test_pose_columns_zero_after_shared_R_normalization(self):
        history=[record(i/25) for i in range(3)];candidate=record(.12);a=features(history,candidate);other=deepcopy(candidate);other['geometry_valid']=[False]*17;other['xy_px']=[[0.,0.]]*17;b=features(history,other)
        self.assertEqual(a[:24],b[:24]);normalizer=FeatureNormalizer.fit([a,b]);value=normalizer.transform(a,use_pose=False)
        self.assertTrue(all(value[i]==0 for i in POSE_COLUMNS));self.assertEqual(FeatureNormalizer.from_state(normalizer.state()).transform(a,use_pose=True),normalizer.transform(a,use_pose=True))
    def test_constant_channel_shift_is_bounded_before_motion_mask(self):
        normalizer=FeatureNormalizer.fit([[0.]*FEATURE_DIM,[0.]*FEATURE_DIM]);row=[1000.]*FEATURE_DIM;value=normalizer.transform(row,use_pose=True)
        self.assertTrue(all(std>=.05 for std in normalizer.std));self.assertTrue(all(-5<=v<=5 for v in value));self.assertTrue(all(v==0 for v in normalizer.transform(row,use_pose=False)[24:]))
    def test_same_MLP_initialization_and_window_BCE_unknown(self):
        import torch
        torch.set_num_threads(1);before=torch.get_rng_state().clone();a=make_model(20261024);b=make_model(20261024)
        self.assertTrue(torch.equal(before,torch.get_rng_state()));self.assertTrue(all(torch.equal(a.state_dict()[k],b.state_dict()[k]) for k in a.state_dict()));self.assertTrue(all(p.dtype==torch.float32 for p in a.parameters()))
        x=[[0.]*FEATURE_DIM]*3;loss,counts=window_BCE(a,x,[1,None,0]);self.assertEqual(counts,dict(known=2,unknown=1));loss.backward();self.assertTrue(any(p.grad is not None for p in a.parameters()))
        self.assertTrue(all(torch.equal(a.state_dict()[k],b.state_dict()[k]) for k in a.state_dict()));empty,counts=window_BCE(a,x,[None]*3);self.assertEqual(float(empty.detach()),0.)
        self.assertFalse(probability_to_cost(.49,.8)['accepted']);self.assertTrue(probability_to_cost(.5,.8)['accepted']);self.assertAlmostEqual(probability_to_cost(.9,.8)['cost'],.4)
if __name__=='__main__':unittest.main()
