"""新控制器的只读身份/资源前置与正式收据合同；不启动子进程。"""
from copy import deepcopy
import unittest
from unittest.mock import patch
from pathlib import Path
import control_r_eligibility_training as c

def receipt(rs=False):
    job=dict(fold='game4',seed=20261024,regime='RS' if rs else 'R')
    return job,dict(schema=c.RUN_SCHEMA,status='complete',completed_updates=1000,real_window_exposures=3000,synthetic_window_exposures=1000*int(rs),formal=True,
        diagnostic_variant=None,numeric_only_virtual_mask_overrides=[],synthetic_stress_initial_step=None,optimizer_replay=0,test_read=False,binding=job,
        prefetch=dict(closed=True,worker_alive=False,loaded=1000,yielded=1000),cache_peak_bytes=100,actual_dtype='float32',amp=False,epoch_augmentation=False)

class ControllerContracts(unittest.TestCase):
    def test_preflight_writer_is_real_journal_function_not_missing_runtime_attribute(self):
        import training_journal
        self.assertIs(c.write_new,training_journal.write_new)

    def test_new_execution_keeps_same_protocol_and_refuses_nonzero_replay(self):
        config=Path('D:/projects/FutsalMOT_Research/pose/r_candidate_eligibility_a01/training_frozen_a01/protocol.json');out=Path('D:/projects/FutsalMOT_Research/pose/r_candidate_eligibility_a01/training_control_a02')
        cfg=dict(bundle='frozen');body=dict(schema='R_candidate_eligibility_controller_execution_v1',approved_by='root',training_protocol=dict(path=str(config),sha256='hash'),training_bundle='frozen',control_root=str(out),controller_source=dict(path=c.__file__,sha256='hash'),previous_formal_updates=0,test_read=False,previous_failure={})
        with patch.object(c.rt,'physical',side_effect=lambda x:Path(x)),patch.object(c.rt,'sha',return_value='hash'),patch.object(c.rt,'read',return_value=body),patch.object(c.rt,'read_ref',return_value=dict(formal_optimizer_updates=0,training_children_started=0)):
            self.assertEqual(c.execution_identity(config,cfg,out,config)['sha256'],'hash')
            with patch.object(c.rt,'read_ref',return_value=dict(formal_optimizer_updates=1,training_children_started=1)):
                with self.assertRaises(ValueError):c.execution_identity(config,cfg,out,config)

    def test_formal_R_RS_fixed_receipt_not_diagnostic(self):
        for rs in (False,True):
            j,r=receipt(rs);c.validate_receipt(r,j)
            for key,value in [('formal',False),('completed_updates',999),('diagnostic_variant','alltrue_original_BCE'),('synthetic_stress_initial_step',7)]:
                bad=deepcopy(r);bad[key]=value
                with self.assertRaises(ValueError):c.validate_receipt(bad,j)

    def test_no_S_in_pure_R_or_extra_S_in_RS(self):
        for rs in (False,True):
            j,r=receipt(rs);r['synthetic_window_exposures']+=1
            with self.assertRaises(ValueError):c.validate_receipt(r,j)

    def test_prefetch_real_exit_evidence_not_cache_explicit_close(self):
        j,r=receipt();r['cache_explicit_close_called']=False;c.validate_receipt(r,j)
        r['prefetch']['worker_alive']=True
        with self.assertRaises(ValueError):c.validate_receipt(r,j)

    def test_actual_new_controller_or_UE_refused(self):
        own=dict(ProcessId=10,ParentProcessId=1,Name='python.exe',CommandLine='python control_r_eligibility_training.py')
        with patch.object(c.os,'getpid',return_value=10):
            for other in [dict(ProcessId=11,ParentProcessId=1,Name='python.exe',CommandLine='python D:/code/r_eligibility_train.py --execute'),dict(ProcessId=11,ParentProcessId=1,Name='UnrealEditor.exe',CommandLine='UE')]:
                with patch.object(c,'process_inventory',return_value=[own,other]):
                    with self.assertRaises(ValueError):c.exclusive()

    def test_PID_reused_by_unrelated_identity_is_not_old_research(self):
        rows=[dict(ProcessId=10,ParentProcessId=1,Name='python.exe',CommandLine='python control_r_eligibility_training.py'),dict(ProcessId=11,ParentProcessId=1,Name='python.exe',CommandLine='python user_game.py')]
        with patch.object(c.os,'getpid',return_value=10),patch.object(c,'process_inventory',return_value=rows):self.assertEqual(c.exclusive()[1],{10})

    def test_parent_chain_cycle_is_bounded(self):
        rows=[dict(ProcessId=10,ParentProcessId=11),dict(ProcessId=11,ParentProcessId=10)]
        with patch.object(c.os,'getpid',return_value=10):self.assertEqual(c.own_chain(rows),{10,11})

if __name__=='__main__':unittest.main()
