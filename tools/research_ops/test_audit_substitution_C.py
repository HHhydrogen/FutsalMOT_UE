"""独立实际预算检查必须拒绝隐藏pair、缺失LR和伪装S。"""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('C_audit',Path(__file__).with_name('audit_substitution_C.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Audit(unittest.TestCase):
    def fixture(self):
        base=[dict(window_uid='b'+str(i),candidate_pairs=2,labelled_pairs=1) for i in range(3000)]
        extra=[dict(window_uid='e'+str(i),candidate_pairs=4,labelled_pairs=3) for i in range(1000)]
        logs=[dict(real=base[i*3:i*3+3]+extra[i:i+1],synthetic=[],R_windows=4,S_windows=0,
            base_R_windows=3,extra_R_windows=1,base_R_pairs=6,extra_R_pairs=4,base_R_known_pairs=3,extra_R_known_pairs=3,
            R_pairs=10,R_known_pairs=6,S_pairs=0,S_known_pairs=0,learning_rates=[.001],gradients_clipped=False,
            loss=.2,real_loss=.2,base_real_loss=.15,extra_real_loss=.15,synthetic_loss=None,grad_l2=.1,step_wall_seconds=.01) for i in range(1000)]
        return logs,dict(real=base),dict(extra_R=extra)
    def test_actual_totals(self):
        rows,t,e=self.fixture();totals=m.count_run(rows,t,e)
        self.assertEqual(totals['R_windows'],4000);self.assertEqual(totals['extra_R_known_pairs'],3000)
    def test_changed_pair_and_missing_LR_rejected(self):
        for key,value in [('extra_R_pairs',3),('learning_rates',[]),('synthetic_loss',.1)]:
            rows,t,e=self.fixture();rows[999][key]=value
            with self.assertRaises(ValueError):m.count_run(rows,t,e)

if __name__=='__main__':unittest.main()
