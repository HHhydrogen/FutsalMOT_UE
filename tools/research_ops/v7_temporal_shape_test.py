"""仅合成记录的OLS候选测试；无真实replay/GPU/模型或GT读取。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'python/src'))
from grf_ue_bridge.pose_temporal_shape_v7 import TemporalShapeHistory
from grf_ue_bridge.pose_association_contract_v2 import pose_pair_cost_candidate

def observation(frame,u=None):
    u=.01*frame if u is None else u;x=10.*frame if frame<10 else 450.;box=[x,100.,100.,200.];point=[x+50+u*100,200.]
    return dict(frame_index=frame,sequence_id='SNMOT-151',camera_id='broadcast',model_sha256='a'*64,fixed_detection_set_sha256='b'*64,
        source='model_prediction_xy',coordinate_space='image_pixels',validity_method='finite_bbox_relative_geometry',bbox_xywh_px=box,xy_px=[list(point) for _ in range(17)],geometry_valid=[True]*17,
        prediction_valid=True,physical_visibility='unknown',visibility_state=['unknown']*17,image_wh=[1920,1080])
class TemporalTests(unittest.TestCase):
    def test_OLS_shape_motion_and_no_history_mutation(self):
        history=TemporalShapeHistory(1);records=[observation(t) for t in range(3)];before=deepcopy(records)
        for item in records:history.observe(item,track_id=1)
        result=history.cost(observation(3),[80.,200.]);self.assertEqual(result['mode'],'temporal_OLS_shape');self.assertAlmostEqual(result['pose_cost'],0.)
        self.assertEqual(history.history_frames,[0,1,2]);self.assertEqual(records,before)
    def test_old_0_100_101_not_mixed_into_short_OLS(self):
        history=TemporalShapeHistory(1)
        for frame,u in [(0,.7),(100,.1),(101,.2)]:history.observe(observation(frame,u),track_id=1)
        prediction=history.predict_shape(102,[500.,200.]);self.assertEqual(prediction['OLS_window_frames'],[100,101]);self.assertAlmostEqual(prediction['xy_px'][0][0],530.)
    def test_gap_four_is_exact_original_static_fallback(self):
        history=TemporalShapeHistory(1);last=None
        for t in range(3):last=observation(t);history.observe(last,track_id=1)
        current=observation(6);value=history.cost(current,[110.,200.]);expected=pose_pair_cost_candidate(last,current,[40.,0.])
        self.assertEqual(value['mode'],'original_static_fallback');self.assertEqual(value['pose_cost'],expected['pose_cost'])
    def test_actual_only_missing_reactivation_and_track_isolation(self):
        history=TemporalShapeHistory(1);history.observe(observation(0),track_id=1);history.note_missing(1);self.assertEqual(history.history_frames,[0])
        with self.assertRaises(ValueError):history.observe(observation(1),track_id=2)
        with self.assertRaises(ValueError):history.observe(dict(observation(1),derived_from_history=True),track_id=1)
        history.observe(observation(2),track_id=1);history.observe(observation(3),track_id=1,reactivated=True);self.assertEqual(history.history_frames,[3])
        self.assertEqual(history.cost(observation(4),[90.,200.])['mode'],'original_static_fallback')
    def test_each_joint_needs_two_valid_actual_observations(self):
        history=TemporalShapeHistory(1);a=observation(0);a['geometry_valid'][0]=False;a['xy_px'][0]=[0.,0.];history.observe(a,track_id=1);history.observe(observation(1),track_id=1)
        prediction=history.predict_shape(2,[70.,200.]);self.assertFalse(prediction['prediction_supported'][0]);self.assertTrue(prediction['prediction_supported'][5]);self.assertTrue(prediction['derived_from_history']);self.assertFalse(prediction['is_actual_observation'])
if __name__=='__main__':unittest.main()
