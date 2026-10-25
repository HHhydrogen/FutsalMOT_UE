"""v7 Tracker薄集成CPU夹具；不执行真实450帧或GT评价。"""
import os
from pathlib import Path
import sys
import unittest
os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',YOLO_CONFIG_DIR='D:/projects/FutsalMOT_Research/pose/association_dev_a01/v7_temporal/_runtime/ultralytics')
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'python/src'),str(Path(__file__).resolve().parent)];sys.path.append('D:/projects/FutsalMOT_Research/runtime_dependencies')
import numpy as np
import torch
torch.set_num_threads(1)
from grf_ue_bridge import pose_bytetrack_v2 as old
from grf_ue_bridge.pose_temporal_tracker_v7 import temporal_tracker_class
from v7_temporal_shape_test import observation

def fixture(t,missing=False):
    record=observation(t);uid=f'SNMOT-151:{t+1:06d}:000000';record.update(detection_id=uid)
    frame=dict(sequence_id='SNMOT-151',camera_id='broadcast',frame_index=t,frame_number=t+1,frame_key=f'SNMOT-151:{t+1:06d}',width=1920,height=1080,
        detections=[] if missing else [dict(detection_id=uid,class_id=0,score=.9,bbox_xywh_px=record['bbox_xywh_px'])])
    return frame,{} if missing else {uid:record}
class Integration(unittest.TestCase):
    def test_lambda0_exact_upstream(self):
        pairs=[fixture(i) for i in range(4)];frames=[frame for frame,poses in pairs];expected,states,_=old.run_sequence(frames,fixed_sha='b'*64,reference=True)
        tracker=temporal_tracker_class()(pose_lambda=0.,fixed_detection_set_sha256='b'*64);actual=[];snapshots=[]
        for frame,poses in pairs:actual.append(tracker.update_frame(frame).copy());snapshots.append(old.tracker_state(tracker))
        self.assertTrue(all(np.array_equal(a,b) for a,b in zip(expected,actual)));self.assertEqual(states,snapshots)
    def test_history_after_activate_and_temporal_actually_used(self):
        tracker=temporal_tracker_class()(pose_lambda=.1,fixed_detection_set_sha256='b'*64,model_sha256='a'*64)
        for t in range(4):frame,poses=fixture(t);tracker.update_frame(frame,poses)
        self.assertGreater(tracker.audit.get('temporal_shape_pairs_used',0),0)
        track=tracker.tracked_stracks[0];self.assertEqual(track.pose_history.track_id,track.track_id);self.assertEqual(track.pose_history.history_frames,[1,2,3])
    def test_lost_reactivation_clears_actual_history(self):
        tracker=temporal_tracker_class()(pose_lambda=.1,fixed_detection_set_sha256='b'*64,model_sha256='a'*64)
        for t in range(3):frame,poses=fixture(t,missing=t==1);tracker.update_frame(frame,poses)
        self.assertEqual(tracker.tracked_stracks[0].pose_history.history_frames,[2]);self.assertFalse(torch.cuda.is_initialized())
if __name__=='__main__':unittest.main()
