"""只用小fixture核新控制身份、实际a02继承和首门禁；不查询CIM或读取研究输入。"""
from copy import deepcopy
import unittest
from unittest.mock import patch
import r_eligibility_tracking_control as c
import freeze_r_eligibility_tracking as f


def closure_fixture():
    protocol={'path':str(f.E/'training_frozen_a01/protocol.json'),'sha256':'d5880b07e97e1252852c7c70ee5b1961b04f5825838063f8e84b462559388daf'}
    completed={'path':str(f.E/'training_complete_root_a01.json'),'sha256':'a'*64}
    budget={'path':str(f.E/'postrun_audit_a01/actual_budget.json'),'sha256':'b'*64}
    state_ref={'path':str(f.E/'training_control_a02/driver_state.json'),'sha256':'c'*64}
    state=dict(status='complete18_R_candidate_eligibility_training_wait_independent_audit_tracking',active=None,protocol_sha256=protocol['sha256'],completed_train={str(i):dict(path='actual_a02_run_'+str(i)) for i in range(18)})
    root=dict(schema='r_candidate_eligibility_training_complete_root_v1',status='complete18_R_candidate_eligibility_training_and_independent_budget_verified',protocol=protocol,budget_audit=budget,control_state=state_ref,actual_training_and_audit_processes_absent=True,test_read=False)
    audit=dict(schema='independent_R_candidate_eligibility18_budget_audit_v1',status='complete18_R_candidate_eligibility_actual_budget_effective_supervision_full_records_and_exit_verified',protocol=protocol,control_state=state_ref)
    graph={completed['path']:root,budget['path']:audit,state_ref['path']:state}
    return completed,graph


class EligibilityControlFixtures(unittest.TestCase):
    def test_actual_identity_guards_new_old_research_and_UE_only(self):
        rows=[dict(ProcessId=i+10,ParentProcessId=0,Name='python.exe',CommandLine='python D:/code/'+name+'.py --execute') for i,name in enumerate(('r_eligibility_train','control_r_eligibility_training','r_eligibility_tracking_control','r_set_tracking_control','state_gap_control','unrelated_app'))]
        rows.append(dict(ProcessId=99,ParentProcessId=0,Name='UnrealEditor.exe',CommandLine='UE'))
        bad,own=c.blocking_processes(rows,555)
        self.assertEqual([v['ProcessId'] for v in bad],[10,11,12,13,14,99]);self.assertEqual(own,[555])

    def test_only_actual_same_control_parent_chain_is_exempt(self):
        rows=[dict(ProcessId=30,ParentProcessId=20,Name='python.exe',CommandLine='python r_eligibility_tracking_control.py'),dict(ProcessId=20,ParentProcessId=10,Name='python.exe',CommandLine='python r_eligibility_tracking_control.py'),dict(ProcessId=10,ParentProcessId=0,Name='python.exe',CommandLine='python unrelated_app.py'),dict(ProcessId=31,ParentProcessId=10,Name='python.exe',CommandLine='python r_eligibility_tracking_control.py')]
        bad,own=c.blocking_processes(rows,30);self.assertEqual(own,[20,30]);self.assertEqual([v['ProcessId'] for v in bad],[31])

    def test_two_actual_gate_cells_and_duplicate_unknown_ids_rejected(self):
        cfg=dict(jobs=[dict(job_id='a',regime='R',sequence='SNMOT-060'),dict(job_id='b',regime='RS',sequence='v_2QhNRucNC7E_c017')],gate_job_ids=['a','b'])
        self.assertEqual(len(c.validate_gate_jobs(cfg)),2)
        for ids in (['a','a'],['a','missing'],['a','b','a']):
            broken=deepcopy(cfg);broken['gate_job_ids']=ids
            with self.assertRaises(ValueError):c.validate_gate_jobs(broken)

    def test_complete_root_drives_actual_a02_and_preserves_all_18_paths(self):
        root,graph=closure_fixture()
        with patch.object(f,'read_ref',side_effect=lambda r:graph[r['path']]) as reader:
            value=f.resolve_training_refs(root)
        self.assertEqual(len(value['state']['completed_train']),18)
        self.assertIn('training_control_a02',value['control_state']['path'])
        self.assertFalse(any('training_control_a01' in call.args[0]['path'] for call in reader.call_args_list))

    def test_root_and_independent_budget_control_reference_must_match(self):
        root,graph=closure_fixture();graph[root['path']]['control_state']=dict(path=str(f.E/'training_control_a01/driver_state.json'),sha256='d'*64)
        with patch.object(f,'read_ref',side_effect=lambda r:graph[r['path']]),self.assertRaises(AssertionError):f.resolve_training_refs(root)

    def test_old_failed_zero_update_state_not_completion(self):
        for change in ('empty','active','status','schema'):
            root,graph=closure_fixture();state=next(v for v in graph.values() if 'completed_train' in v)
            if change=='empty':state['completed_train']={}
            elif change=='active':state['active']={'running':True}
            elif change=='status':state['status']='failed_preserved_no_implicit_replay'
            else:graph[root['path']]['schema']='R_set_supervision_training_complete_root_v1'
            with patch.object(f,'read_ref',side_effect=lambda r:graph[r['path']]),self.assertRaises(AssertionError):f.resolve_training_refs(root)

    def test_closure_is_checked_before_installation_or_any_external_write(self):
        with patch.object(f,'ref',return_value={'path':'fixture','sha256':'a'*64}),patch.object(f,'resolve_training_refs',side_effect=AssertionError('not complete')),patch.object(f,'write') as write,patch.object(f.shutil,'copyfile') as copy:
            with self.assertRaises(AssertionError):f.install()
        write.assert_not_called();copy.assert_not_called()

    def test_fixed_profile_preserves_actual_resource_and_thread_limits(self):
        self.assertEqual((c.PROFILE['track_workers'],c.PROFILE['metric_workers'],c.PROFILE['numeric_threads']),(2,1,1))
        self.assertEqual((c.PROFILE['reserve_RAM_bytes'],c.PROFILE['reserve_commit_bytes']),(8589934592,6442450944))
        self.assertEqual(len(f.FILES),4);self.assertFalse(any('train.py' in name for name in f.FILES))
        self.assertEqual(c.service_base.cache_info().currsize,0)

if __name__=='__main__':unittest.main()
