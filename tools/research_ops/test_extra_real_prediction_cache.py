"""额外R新预测入口在模型加载前的准入及真实原数值转写检查。"""
from copy import deepcopy
from pathlib import Path
import unittest
import extra_real_prediction_cache as entry


class Tests(unittest.TestCase):
    def test_incomplete_acquisition_fails_before_models(self):
        cfg=dict(schema='extra_real_shared_prediction_config_v1',approved_by='root',prediction_authorized=True,training_authorized=False,
                 test_sealed=True,parameters=entry.PARAMETERS,acquisition_manifest=dict(path='manifest',sha256='a'))
        with self.assertRaises(ValueError):entry.admission(cfg,dict(status='started'),dict(status='started'))

    def test_exit_and_manifest_identity_both_required(self):
        cfg=dict(schema='extra_real_shared_prediction_config_v1',approved_by='root',prediction_authorized=True,training_authorized=False,
                 test_sealed=True,parameters=entry.PARAMETERS,acquisition_manifest=dict(path='manifest',sha256='a'))
        manifest=dict(status='complete2250_extra_real_train_frames_decoded_not_prediction_or_training_authorized')
        closed=dict(status='complete2250_extra_real_inputs_verified_processes_absent',acquisition_manifest=cfg['acquisition_manifest'],download_processes_absent=True)
        entry.admission(cfg,manifest,closed)
        bad=deepcopy(closed);bad['download_processes_absent']=False
        with self.assertRaises(ValueError):entry.admission(cfg,manifest,bad)

    def test_own_launcher_chain_does_not_allow_other_jobs(self):
        own=[dict(ProcessId=1,ParentProcessId=2,Name='python.exe',CommandLine='extra_real_prediction_cache.py'),
             dict(ProcessId=2,ParentProcessId=99,Name='python.exe',CommandLine='extra_real_prediction_cache.py')]
        self.assertEqual(entry.check_processes(own,1),[1,2])
        for process in (dict(ProcessId=3,ParentProcessId=99,Name='UnrealEditor.exe',CommandLine='project'),
                        dict(ProcessId=3,ParentProcessId=99,Name='python.exe',CommandLine='acquire_extra_real_clips.py')):
            with self.assertRaises(ValueError):entry.check_processes(own+[process],1)

    def test_frozen_raw_transfer_has_new_UID_and_keeps_unmatched_boxes(self):
        helper=entry.module('test_frozen_extra_raw',Path('D:/projects/FutsalMOT_Research/code/3f8566583ff07e60665c60fd4ec28cd03e5e8633796c9da8ad83e997fe09bc92/tools/research_ops/v10_prediction_cache.py'))
        frame=dict(sequence='SNMOT-061',frame_number=1,width=1920,height=1080)
        rows,rejected=helper.raw_detections([[1,2,30,80,.5,0],[1500,2,1530,80,.12,0]],frame)
        self.assertEqual(len(rows),2);self.assertEqual(rejected,0);self.assertEqual(rows[0]['detection_id'],'SNMOT-061:000001:000000')

    def test_numeric_attach_rejects_deletion_or_bbox_changes(self):
        helper=entry.module('test_frozen_extra_attach',Path('D:/projects/FutsalMOT_Research/code/3f8566583ff07e60665c60fd4ec28cd03e5e8633796c9da8ad83e997fe09bc92/tools/research_ops/v10_prediction_cache.py'))
        rows=[dict(detection_id='u',bbox_xywh_px=[1,2,3,4],score=.5,class_id=0)]
        with self.assertRaises(ValueError):helper.attach({},rows,[],entry.POSE_SHA,'d')
        pred=dict(uid='u',detection_id='u',bbox_xywh_px=[2,2,3,4],score=.5,class_id=0,prediction_valid=False,
                  xy_px=[[0.,0.]]*17,geometry_valid=[False]*17,physical_visibility='unknown')
        with self.assertRaises(ValueError):helper.attach({},rows,[pred],entry.POSE_SHA,'d')


if __name__=='__main__':unittest.main()
