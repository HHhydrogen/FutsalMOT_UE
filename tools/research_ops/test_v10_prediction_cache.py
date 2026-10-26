"""v10共享预测CPU门禁：发布/进程、原检测不筛GT及Pose完整对应。"""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import v10_prediction_cache as cache


class PredictionTests(unittest.TestCase):
    def test_requires_actual_twelve_complete_and_source_flags(self):
        data=dict(schema='futsalmot_v10_multiseed_dataset_v1',status='diagnostic_complete_not_training',
                  rgb_frames=3600,mask_frames=3600,person_pose=36000,visibility='unknown',not_training=True,MRQ_sync_verified=False)
        complete=dict(status='published_v10_12_units_metadata_complete',all_source_UE_normal_exit=True,EXR_retired=3600)
        capture=dict(schema='futsalmot_multiseed_v10_serial_v1',status='complete_full_12_units_EXR_retired_wait_root_publication',
                     completed=[dict(attempt=str(i),normal_UE_exit=True,EXR_deleted=300,rgb=300,mask=300,person_pose=3000) for i in range(12)])
        cache.publication_gate(data,complete,capture)
        bad=deepcopy(capture);bad['completed'].pop()
        with self.assertRaises(ValueError):cache.publication_gate(data,complete,bad)
        bad=deepcopy(data);bad['not_training']=False
        with self.assertRaises(ValueError):cache.publication_gate(bad,complete,capture)

    def test_process_identity_and_PID_reuse(self):
        cache.validate_processes([dict(Name='RuntimeBroker.exe',CommandLine='reused old PID')])
        cache.validate_processes([dict(Name='python.exe',CommandLine='unrelated_application.py')])
        for row in (dict(Name='UnrealEditor.exe',CommandLine='project'),
                    dict(Name='python.exe',CommandLine='python run_multiseed_v10_serial.py --execute')):
            with self.assertRaises(ValueError):cache.validate_processes([row])

    def test_raw_detector_order_clipping_and_degenerate_rule(self):
        frame=dict(sequence='v10_S1042',frame_number=1,width=100,height=50)
        raw=[[-2,-3,110,55,.9,0],[5,5,5,8,.8,0],[8,9,20,30,.2,0]]
        original=deepcopy(raw);det,rejected=cache.raw_detections(raw,frame)
        self.assertEqual(rejected,1);self.assertEqual(len(det),2)
        self.assertEqual(det[0]['bbox_xywh_px'],[0.,0.,100.,50.])
        self.assertEqual(det[1]['detection_id'],'v10_S1042:000001:000001')
        self.assertEqual(det[1]['score'],.2);self.assertEqual(raw,original)
        # 未知/背景或低质量Pose的检测仍保留；此阶段没有GT匹配输入。
        with self.assertRaises(ValueError):cache.raw_detections([[0,0,10,10,float('nan'),0]],frame)

    def test_missing_pose_refuses_without_dropping_detection(self):
        frame=dict(sequence='val',frame_number=1,width=100,height=50)
        det,_=cache.raw_detections([[0,0,10,10,.9,0]],frame)
        d=det[0]
        p=dict(uid=d['detection_id'],detection_id=d['detection_id'],bbox_xywh_px=d['bbox_xywh_px'],score=d['score'],
               class_id=0,prediction_valid=False,xy_px=[[0.,0.]]*17,geometry_valid=[False]*17,physical_visibility='unknown')
        result=cache.attach(frame,det,[p],'p'*64,'d'*64)
        self.assertEqual(len(result['detections']),1);self.assertFalse(result['detections'][0]['prediction_valid'])
        self.assertFalse(result['GT_used_for_predictions'])
        with self.assertRaises(ValueError):cache.attach(frame,det,[],'p'*64,'d'*64)
        bad=deepcopy(p);bad['bbox_xywh_px']=[1.,0.,10.,10.]
        with self.assertRaises(ValueError):cache.attach(frame,det,[bad],'p'*64,'d'*64)

    def test_wrong_explicit_SHA_cannot_reach_preflight_or_GPU(self):
        with patch.object(cache,'sha',return_value='actual'),patch.object(cache,'preflight') as preflight:
            with self.assertRaises(ValueError):cache.execute(Path('unused.json'),'wrong')
            preflight.assert_not_called()


if __name__ == '__main__':unittest.main()
