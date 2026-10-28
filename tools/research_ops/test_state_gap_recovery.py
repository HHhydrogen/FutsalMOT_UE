"""恢复只继承完整收据，未知partial/退出码不补造。"""
from copy import deepcopy
from pathlib import Path
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import state_gap_control as c

def fixture():
    jobs=[dict(job_id=str(i),sequence='s') for i in range(12)]
    cfg={k:{} for k in c.RECOVERY_SOURCE_KEYS};cfg.update(jobs=jobs,sources={'s':{'cache':{'path':'cache'}}},bundle='new',bundle_manifest={'path':'bundle'})
    refs=lambda x:dict(path=x,sha256='a'*64)
    obs={str(i):refs('o'+str(i)) for i in range(5)};post={str(i):refs('p'+str(i)) for i in range(2)}
    r=dict(source_protocol=refs('old'),source_state=refs('state'),interruption=refs('failure'),inherit_observe=obs,inherit_posthoc=post,
        restart_incomplete_jobs_explicit=[str(i) for i in range(5,12)],streaming_admission=refs('gate'))
    cfg['numeric_admission']=refs('numeric')
    data={'old':deepcopy(cfg),'state':dict(protocol=r['source_protocol'],observe=obs,posthoc=post),'failure':dict(source_state=r['source_state'],actual_research_controller_and_spawn_processes_absent=True,actual_exit_codes=None,partial_actual_frame_advances=None)}
    for i in range(5):data['o'+str(i)]=dict(status='complete',frames=750,frames_log=dict(rows=750),job=jobs[i],protocol=r['source_protocol'],observer_enabled=True,
        source_cache=cfg['sources']['s']['cache'],GT_guard=dict(blocked_open_attempts=0),models_unchanged=True,inputs_unchanged=True)
    for i in range(3):data['p'+str(i)]=dict(total_frames=750,observe=obs[str(i)],job=jobs[i],all_rows=dict(rows=42),summary=dict(absolute_counts=dict(windows=42)))
    data['gate']=dict(status='complete_streamed750_posthoc_and_bounded_memory_gate',bundle='new',bundle_manifest=cfg['bundle_manifest'],worker_exited=True,exit_code=0,
        peak_worker_RSS_bytes=100,minimum_available_RAM_bytes=10*1024**3,minimum_commit_headroom_bytes=8*1024**3,job_id='2',posthoc=refs('p2'))
    cfg['recovery']=r;return cfg,data

class Recovery(unittest.TestCase):
    def check(self,cfg,data):
        with patch.object(c,'read_ref',side_effect=lambda ref:data[ref['path']]):return c.recovery_inheritance(cfg)
    def test_five_observe_two_old_posthoc_one_new_admission(self):
        cfg,data=fixture();a,b=self.check(cfg,data);self.assertEqual(len(a),5);self.assertEqual(len(b),3)
    def test_partial_never_inherited(self):
        cfg,data=fixture();data['o2']['status']='started'
        with self.assertRaises(ValueError):self.check(cfg,data)
    def test_cannot_replay_success_or_change_jobs(self):
        cfg,data=fixture();cfg['recovery']['restart_incomplete_jobs_explicit'].append('0')
        with self.assertRaises(ValueError):self.check(cfg,data)
        cfg,data=fixture();cfg['jobs'][0]['sequence']='heldout'
        with self.assertRaises(ValueError):self.check(cfg,data)
    def test_exit_and_frame_unknown_not_fabricated(self):
        cfg,data=fixture();data['failure']['actual_exit_codes']=[0]
        with self.assertRaises(ValueError):self.check(cfg,data)
    def test_full750_memory_reserve_is_required(self):
        cfg,data=fixture();data['gate']['minimum_available_RAM_bytes']=100
        with self.assertRaises(ValueError):self.check(cfg,data)

if __name__=='__main__':unittest.main()
