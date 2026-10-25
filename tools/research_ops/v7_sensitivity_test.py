"""敏感度少量CPU夹具；仅合成两帧，不执行真实450帧replay。"""
import os
from pathlib import Path
import sys
import unittest
os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',YOLO_CONFIG_DIR='D:/projects/FutsalMOT_Research/pose/association_dev_a01/v7_sensitivity/_runtime/ultralytics')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'python/src'));sys.path.append('D:/projects/FutsalMOT_Research/runtime_dependencies')
import numpy as np
from grf_ue_bridge.pose_association_sensitivity_v7 import matrix_for_reference,matrix_profile,matrix_difference,instrumented_reference_class

def record(uid,index,box=(100.,100.,30.,60.),model='a'*64):
    x,y,w,h=box
    return dict(detection_id=uid,frame_index=index,sequence_id='SNMOT-151',camera_id='broadcast',bbox_xywh_px=list(box),xy_px=[[x+w*.3,y+h*(.1+.04*j)] for j in range(17)],geometry_valid=[True]*17,
        coordinate_space='image_pixels',source='model_prediction_xy',validity_method='finite_bbox_relative_geometry',model_sha256=model,fixed_detection_set_sha256='b'*64,prediction_valid=True,physical_visibility='unknown',visibility_state=['unknown']*17)
class SensitivityTests(unittest.TestCase):
    def test_lambda0_no_attachment_or_arithmetic(self):
        class Poison(dict):
            def __contains__(self,key):raise AssertionError('不该读取Pose')
        base=np.array([[.2]],dtype=np.float32);result,valid,audit=matrix_for_reference(base,[dict(pose_uid='a',kalman_center_xy=[0.,0.])],[dict(pose_uid='b')],Poison(),stage=0,pose_lambda=0.)
        self.assertIs(result,base);self.assertFalse(valid.any())
    def test_inversion_only_originally_valid_pairs(self):
        base=np.array([[.2,.3,.9]],dtype=np.float32);records={'a':record('a',0),'b':record('b',1),'c':record('c',1)};records['c']['geometry_valid']=[False]*17
        tracks=[dict(pose_uid='a',kalman_center_xy=[115.,130.])];dets=[dict(pose_uid='b'),dict(pose_uid='c'),dict(pose_uid='b')]
        normal,mask,_=matrix_for_reference(base,tracks,dets,records,stage=0);inverted,other,_=matrix_for_reference(base,tracks,dets,records,stage=0,invert_valid=True)
        self.assertTrue(mask[0,0]);self.assertFalse(mask[0,1]);self.assertTrue(np.array_equal(mask,other));self.assertEqual(normal[0,1],base[0,1]);self.assertEqual(inverted[0,1],base[0,1]);self.assertEqual(inverted[0,2],base[0,2]);self.assertNotEqual(normal[0,0],inverted[0,0])
    def test_competition_and_row_gap_not_global_margin(self):
        base=np.array([[.2,.25],[.3,.31]],dtype=np.float32);profile=matrix_profile(base,base,stage=0)
        self.assertEqual(profile['bbox_gate_rows_candidate_count'],[2,2]);self.assertEqual(profile['columns_with_at_least_two_competing_candidates'],2);self.assertIn('NOT global Hungarian',profile['row_gap_semantics'])
        changed=base.copy();changed[0]=[.4,.1];self.assertEqual(matrix_difference(base,changed,base,stage=0)['rows_any_candidate_rank_changed'],1)
    def test_toy_instrumented_PT_is_original_static_exact(self):
        import torch
        torch.set_num_threads(1)
        from grf_ue_bridge import pose_bytetrack_v2 as old
        frames=[];maps={'pretrained':{},'other':{}}
        for t in range(2):
            key=f'SNMOT-151:{t+1:06d}';box=[100.+5*t,100.,30.,60.];uid=key+':000000';frame=dict(sequence_id='SNMOT-151',camera_id='broadcast',frame_index=t,frame_number=t+1,frame_key=key,width=1920,height=1080,
                detections=[dict(detection_id=uid,class_id=0,score=.9,bbox_xywh_px=box)])
            frames.append(frame);maps['pretrained'][uid]=record(uid,t,box);maps['other'][uid]=record(uid,t,box,model='c'*64)
            if t:maps['other'][uid]['xy_px']=[[x+2,y] for x,y in maps['other'][uid]['xy_px']]
        poses={f['frame_index']:{d['detection_id']:maps['pretrained'][d['detection_id']] for d in f['detections']} for f in frames}
        expected,states,_=old.run_sequence(frames,fixed_sha='b'*64,pose_lambda=.1,model_sha='a'*64,poses_by_frame=poses)
        events=[];Tracker=instrumented_reference_class(maps,events.append);tracker=Tracker(pose_lambda=.1,fixed_detection_set_sha256='b'*64,model_sha256='a'*64);actual=[];snapshots=[]
        for frame in frames:actual.append(tracker.update_frame(frame,poses[frame['frame_index']]).copy());snapshots.append(old.tracker_state(tracker))
        self.assertTrue(all(np.array_equal(a,b) for a,b in zip(expected,actual)));self.assertEqual(states,snapshots);self.assertEqual(len(events),4);self.assertFalse(torch.cuda.is_initialized())
if __name__=='__main__':unittest.main()
