"""单机位独立执行的范围与失败拒绝检查，不伪造UE动态成功。"""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'python/ue'))
from pose17_camera_scope import select_capture_cameras,make_capture_scope,validate_capture_scope,session_cameras
from pose17_smoke_runner import _assert_release_gate
from pose17_seeded_kit_contract import context_payload
from run_seeded_kit_short_a01 import read,sha


class CameraScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units=read(ROOT/'Saved/AppearancePlanning/seeded_kit_capture_a03/manifest.json')['units']
        cls.plan=read(cls.units[0]['plan']['path'])

    def test_all16_preserve_full_source_and_pair_context(self):
        self.assertEqual(len(self.units),16)
        for unit in self.units:
            self.assertEqual(sha(unit['canonical_full_plan']['path']),unit['canonical_full_plan']['sha256'])
            child,parent=read(unit['plan']['path']),read(unit['canonical_full_plan']['path'])
            self.assertEqual(context_payload(child),context_payload(parent))
            self.assertEqual(len(child['cameras']),4)
            self.assertEqual([x['camera_id'] for x in select_capture_cameras(child,unit['camera_id'])],[unit['camera_id']])

    def test_reject_wrong_camera_or_nonfull_scope(self):
        with self.assertRaises(ValueError):select_capture_cameras(self.plan,'CineCam_99')
        wrong=copy.deepcopy(self.plan);wrong['frame_count']=3
        with self.assertRaises(ValueError):select_capture_cameras(wrong,'CineCam_01')
        self.assertEqual(len(select_capture_cameras(self.plan)),4)

    def test_reject_forged_full_completion_and_source_frame(self):
        good=make_capture_scope(self.plan,'CineCam_01','a'*64)
        for key,value in [('full_four_camera_group_complete',True),('frames',120),('source_frame_range',[1,301]),('plan_sha256','b'*64)]:
            bad=copy.deepcopy(good);bad[key]=value
            with self.assertRaises(ValueError):validate_capture_scope(self.plan,bad,'a'*64)

    def test_onecamera_release_requires_explicit_matching_scope(self):
        scope=make_capture_scope(self.plan,'CineCam_01','a'*64)
        state=dict(status='rendered_requires_RGB_mask_pose_alignment_acceptance',executor_success=True,errors=[],ready_to_render=False,
            editor_restore_probe_pending=False,editor_scene_state_matched=True,editor_mesh_state_matched=True,
            streaming_restart_required=False,plan_sha256='a'*64,capture_scope=scope,
            completed_jobs=[dict(job='CineCam_01',sampling_passed=True,restore_passed=True)])
        session=dict(plan=self.plan,state=state,capture_cameras=[self.plan['cameras'][0]])
        gate=dict(mrq_running=False,pie_worlds=[],dirty_packages=[],level='/Game/FutsalMOT/Maps/L_FutsalCourt')
        _assert_release_gate(session,gate,False)
        del state['capture_scope']
        with self.assertRaises(ValueError):session_cameras(session)
        with self.assertRaises(ValueError):_assert_release_gate(session,gate,False)


if __name__=='__main__':unittest.main()
