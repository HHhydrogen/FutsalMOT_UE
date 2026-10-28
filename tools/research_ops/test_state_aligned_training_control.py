"""首正式完整检查点门禁失败必须停止，不启动第二臂。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import sys,unittest,json
sys.path.insert(0,str(Path(__file__).resolve().parent))
import state_aligned_training_control as c

class Control(unittest.TestCase):
    def test_first_checkpoint_failure_stops_remaining_arms_and_retains_failure(self):
        cfg=dict(training_matrix=[dict(fold='game4',seed=20261024,regime=r) for r in ('R','RS')])
        receipt=dict(status='complete',completed_updates=1000,real_window_exposures=3000,synthetic_window_exposures=0,
            prefetch=dict(closed=True,worker_alive=False,yielded=1000),binding=dict(initialization_sha256='i',R_window_UID_chain_sha256='r'))
        with TemporaryDirectory() as folder:
            output=Path(folder)/'control';calls=[]
            def popen(*args,**kwargs):calls.append(args);return SimpleNamespace(pid=10,wait=lambda:0)
            with patch.object(c,'preflight',return_value=(cfg,{})),patch.object(c,'memory_gate',return_value={}), \
                    patch.object(c.rt,'sha',return_value='a'*64),patch.object(c.rt,'read',return_value=receipt), \
                    patch.object(c.subprocess,'Popen',side_effect=popen),patch.object(c.rt,'complete_model',side_effect=ValueError('checkpoint mismatch')):
                with self.assertRaisesRegex(ValueError,'checkpoint mismatch'):c.execute(Path(folder)/'config.json',output)
            state=json.loads((output/'driver_state.json').read_text(encoding='utf-8'))
            self.assertEqual(len(calls),1);self.assertEqual(state['completed_train'],[])
            self.assertEqual(state['status'],'failed_preserved_no_replay');self.assertFalse((output/'first_run_end_to_end_gate.json').exists())

if __name__=='__main__':unittest.main()
