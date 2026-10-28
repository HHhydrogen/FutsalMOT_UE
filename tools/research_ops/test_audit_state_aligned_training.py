"""新18臂独立预算审计：拒绝伪造完成、重写缓存closed或少记录。"""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit_state_aligned_training as a

class Contracts(unittest.TestCase):
    def state(self):return dict(status='complete18_state_aligned_training_wait_independent_audit_tracking',active=None,
        completed_train=[dict(v,path='run'+str(i)) for i,v in enumerate(a.matrix())])
    def test_exact18_matrix_and_no_shared_run(self):
        cfg=dict(training_matrix=a.matrix());s=self.state();a.validate_state(s,cfg)
        for changed in (s['completed_train'][:-1],s['completed_train'][:-1]+[s['completed_train'][0]]):
            with self.assertRaises(ValueError):a.validate_state(dict(s,completed_train=changed),cfg)
        s['completed_train'][1]['path']=s['completed_train'][0]['path']
        with self.assertRaises(ValueError):a.validate_state(s,cfg)
        s=self.state();s['active']=dict(pid=123)
        with self.assertRaises(ValueError):a.validate_state(s,cfg)
    def test_actual_script_names_not_auditor_or_reused_PID(self):
        commands=['python D:/x/state_aligned_train.py --execute','python "D:\\x\\state_aligned_training_control.py"',
            'python D:/x/validate_state_aligned_numeric.py --execute','python D:/x/audit_state_aligned_training.py',
            'python D:/x/verify_state_aligned_train.py','python unrelated.py']
        rows=[dict(ProcessId=i,Name='python.exe',CommandLine=c) for i,c in enumerate(commands)]
        self.assertEqual([x['ProcessId'] for x in a.blocked_processes(rows)],[0,1,2])
        self.assertEqual(a.blocked_processes([dict(ProcessId=0,Name='python.exe',CommandLine='python unrelated.py')]),[])
    def ledger(self,regime):
        real=[dict(window_uid='R'+str(i%1000),epoch=i//1000,candidate_pairs=4+i%3,labelled_pairs=2+i%2) for i in range(3000)]
        synthetic=[dict(window_uid='S'+str(i),epoch=0,candidate_pairs=5,labelled_pairs=3) for i in range(1000)]
        table=dict(real=real,synthetic=synthetic);logs=[]
        for i in range(1000):
            rr=deepcopy(real[3*i:3*i+3]);ss=deepcopy(synthetic[i:i+1]) if regime=='RS' else []
            logs.append(dict(actual_update=i+1,update_index=i,real=rr,synthetic=ss,R_windows=3,S_windows=len(ss),
                R_pairs=sum(x['candidate_pairs'] for x in rr),R_known_pairs=sum(x['labelled_pairs'] for x in rr),S_pairs=sum(x['candidate_pairs'] for x in ss),S_known_pairs=sum(x['labelled_pairs'] for x in ss),
                loss=.5 if ss else .4,real_loss=.4,synthetic_loss=.3 if ss else None,grad_l2=1.,learning_rates=[.001],gradients_clipped=False,step_wall_seconds=.01))
        self.chain(logs);return logs,table
    def chain(self,logs):
        chain='0'*64
        for row in logs:
            row.pop('chain_sha256',None);chain=hashlib.sha256((chain+a.canonical(row)).encode()).hexdigest();row['chain_sha256']=chain
    def test_full_R_RS_dynamic_pair_and_unknown_budget(self):
        for regime in a.REGIMES:
            logs,table=self.ledger(regime);totals,chain=a.count_run(logs,table,regime)
            self.assertEqual(totals['R_windows'],3000);self.assertEqual(totals['S_windows'],1000*int(regime=='RS'));self.assertEqual(chain,logs[-1]['chain_sha256'])
            self.assertGreater(totals['R_pairs'],totals['R_known_pairs'])
    def test_rehashed_pair_loss_or_original_S_order_change_rejected(self):
        for key,value in [('R_known_pairs',3),('synthetic_loss',None),('learning_rates',[.002]),('gradients_clipped',True),('loss',.6)]:
            logs,table=self.ledger('RS');logs[0][key]=value;self.chain(logs)
            with self.assertRaises(ValueError):a.count_run(logs,table,'RS')
        logs,table=self.ledger('RS');table['synthetic'][0],table['synthetic'][1]=table['synthetic'][1],table['synthetic'][0]
        with self.assertRaises(ValueError):a.count_run(logs,table,'RS')
        logs,table=self.ledger('R');logs[0]['synthetic_loss']=.01;self.chain(logs)
        with self.assertRaises(ValueError):a.count_run(logs,table,'R')
    def receipt(self):return dict(prefetch=dict(loaded=1000,yielded=1000,closed=True,worker_alive=False),cache_peak_bytes=268435456,cache=dict(closed=False))
    def test_prefetch_exit_closes_resource_without_rewriting_cache_false(self):
        r=self.receipt();result=a.validate_prefetch(r,producer_processes_absent=True)
        self.assertIs(r['cache']['closed'],False);self.assertIs(result['source_cache_closed_flag'],False)
        self.assertFalse(result['cache_explicit_close_called']);self.assertEqual(result['closure_evidence'],'producer_joined_and_run_process_exited')
        r.pop('cache');result=a.validate_prefetch(r,producer_processes_absent=True);self.assertIsNone(result['source_cache_closed_flag'])
    def test_any_missing_join_full_consumption_exit_evidence_refused(self):
        r=self.receipt()
        for changed in (dict(r['prefetch'],loaded=999),dict(r['prefetch'],yielded=999),dict(r['prefetch'],closed=False),dict(r['prefetch'],worker_alive=True),{k:v for k,v in r['prefetch'].items() if k!='loaded'}):
            bad=dict(r,prefetch=changed)
            with self.assertRaises(ValueError):a.validate_prefetch(bad,producer_processes_absent=True)
        with self.assertRaises(ValueError):a.validate_prefetch(r,producer_processes_absent=False)
        with self.assertRaises(ValueError):a.validate_prefetch(dict(r,cache_peak_bytes=268435457),producer_processes_absent=True)

if __name__=='__main__':unittest.main()
