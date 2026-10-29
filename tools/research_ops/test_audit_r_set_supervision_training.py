"""R集合监督独立预算审计夹具；不加载真实训练或数据。"""
from copy import deepcopy
import hashlib
from pathlib import Path
import math,random
from types import SimpleNamespace
from unittest.mock import patch
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit_r_set_supervision_training as a

class Contracts(unittest.TestCase):
    def state(self):
        entries=[dict(v,path='run'+str(i),receipt_sha256='receipt'+str(i)) for i,v in enumerate(a.matrix())]
        return dict(schema='R_candidate_set_supervision18_training_control_v1',status='complete18_R_set_supervision_training_wait_independent_audit',active=None,
            completed_train=entries,formal_optimizer_updates=18000,unverified_completed_runs=[],uncommitted_effects_not_guessed=True,
            observed_child_exits=[dict(job={k:e[k] for k in ('fold','seed','regime')},exit_code=0,reported_completed_updates=1000,receipt_sha256=e['receipt_sha256']) for e in entries])
    def test_exact18_matrix_and_no_shared_run(self):
        cfg=dict(training_matrix=a.matrix());s=self.state();a.validate_state(s,cfg)
        for changed in (s['completed_train'][:-1],s['completed_train'][:-1]+[s['completed_train'][0]]):
            with self.assertRaises(ValueError):a.validate_state(dict(s,completed_train=changed),cfg)
        s['completed_train'][1]['path']=s['completed_train'][0]['path']
        with self.assertRaises(ValueError):a.validate_state(s,cfg)
        s=self.state();s['observed_child_exits'][0]['exit_code']=1
        with self.assertRaises(ValueError):a.validate_state(s,cfg)
        s=self.state();s['unverified_completed_runs']=[dict(path='partial')]
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
        names=['set_supervision_train.py','control_r_set_supervision_training.py','validate_r_set_supervision_numeric.py','audit_r_set_supervision_training.py']
        self.assertEqual(len(a.blocked_processes([dict(Name='python.exe',CommandLine='python D:/code/'+n) for n in names])),3)
        with patch.object(a.subprocess,'run',return_value=SimpleNamespace(stdout='[]')) as command:
            self.assertEqual(a.process_snapshot(),[])
            self.assertIn('powershell|pwsh',command.call_args[0][0][-1])
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


class DiagnosticBudget(unittest.TestCase):
    def proof(self):
        groups=[dict(device=d,regime=r,fold='game4',seed=20261024,R_rows=3,S_rows=int(r=='RS'),
            checkpoints=[dict(completed_updates=i,model_equal=True,optimizer_equal=True,all_RNG_equal=True) for i in (0,1)]) for d in ('cpu','cuda:0') for r in ('R','RS')]
        return dict(status='complete_R_set_supervision_CPU_CUDA_full_record_numeric_admission',protocol_sha256='protocol',formal_optimizer_updates=0,
            actual_diagnostic_optimizer_updates=8,diagnostic_R_windows=24,diagnostic_S_windows=4,all_groups_equal=True,R_RS_same_R_batch_and_initialization=True,
            manual_vs_recorded_loss_gradient_parameters_AdamW_and_RNG_exact=True,CPU_and_CUDA_actual_model_steps_verified=True,full_step0_step1_checkpoints_verified=True,test_read=False,groups=groups)
    def test_CPU_CUDA_8_updates_separate_and_all_four_groups(self):
        proof=self.proof();out=a.diagnostic_budget(proof,'protocol')
        self.assertEqual((out['diagnostic_updates_separate'],out['diagnostic_R_separate'],out['diagnostic_S_separate']),(8,24,4))
        for change in (lambda x:x.update(formal_optimizer_updates=8),lambda x:x.update(diagnostic_R_windows=12),lambda x:x['groups'].pop(),
            lambda x:x['groups'][0]['checkpoints'][0].update(all_RNG_equal=False)):
            bad=deepcopy(proof);change(bad)
            with self.assertRaises(ValueError):a.diagnostic_budget(bad,'protocol')


class Tensor:
    def __init__(self,values,shape,dtype='float32'):self.values=list(values);self.shape=shape;self.dtype=dtype;self.ndim=len(shape)
    def numel(self):return math.prod(self.shape)
    def __float__(self):return float(self.values[0])


class Torch:
    float32='float32';uint8='uint8'
    @staticmethod
    def is_tensor(x):return isinstance(x,Tensor)
    @staticmethod
    def isfinite(x):return SimpleNamespace(all=lambda:all(math.isfinite(v) for v in x.values))
    @staticmethod
    def equal(x,y):return isinstance(x,Tensor) and isinstance(y,Tensor) and (x.dtype,x.shape,x.values)==(y.dtype,y.shape,y.values)
    class Generator:
        def __init__(self,device):pass
        def set_state(self,state):
            if not isinstance(state,Tensor) or state.dtype!='uint8':raise ValueError('RNG')


class CheckpointBudget(unittest.TestCase):
    def fixture(self,step):
        state=dict(weight=Tensor([0.,1.],(2,)),bias=Tensor([0.],(1,)))
        template=SimpleNamespace(state_dict=lambda:state,parameters=lambda:list(state.values()))
        params=dict(params=[0,1],lr=.001,weight_decay=.0001,betas=(.9,.999),eps=1e-8,amsgrad=False)
        moments={} if step==0 else {i:dict(step=Tensor([step],()),exp_avg=Tensor([0.]*x.numel(),x.shape),exp_avg_sq=Tensor([0.]*x.numel(),x.shape)) for i,x in enumerate(state.values())}
        payload=dict(schema='full_training_checkpoint_v1',binding='binding',completed_updates=step,exposure_chain='chain',extra='extra',model=deepcopy(state),
            optimizer=dict(param_groups=[params],state=moments),rng_python=random.Random(1).getstate(),rng_numpy='valid',rng_torch_cpu=Tensor([1,2],(2,),'uint8'),rng_torch_cuda=[Tensor([3,4],(2,),'uint8')])
        def restore(value):
            if value!='valid':raise ValueError('NumPy RNG')
        numpy=SimpleNamespace(random=SimpleNamespace(RandomState=lambda:SimpleNamespace(set_state=restore)))
        return payload,template,numpy
    def check(self,payload,template,numpy,step):
        a.audit_payload(payload,step=step,binding='binding',extra='extra',chain='chain',template=template,torch=Torch,np=numpy)
    def test_full_checkpoint_initialization_AdamW_steps_shapes_and_all_RNG(self):
        for step in (0,50,1000):
            payload,template,numpy=self.fixture(step);self.check(payload,template,numpy,step)
        for change in (lambda p:p['optimizer']['state'][0].update(step=Tensor([999],())),
            lambda p:p['optimizer']['state'][0].update(exp_avg=Tensor([0.],(1,))),lambda p:p.update(rng_torch_cuda=[]),
            lambda p:p.update(rng_numpy='bad'),lambda p:p.update(extra='old_BCE_method_state'),lambda p:p['optimizer']['param_groups'][0].update(amsgrad=True)):
            payload,template,numpy=self.fixture(1000);change(payload)
            with self.assertRaises(ValueError):self.check(payload,template,numpy,1000)
        payload,template,numpy=self.fixture(0);payload['model']['weight']=Tensor([9.,1.],(2,))
        with self.assertRaises(ValueError):self.check(payload,template,numpy,0)


class MethodState(unittest.TestCase):
    def test_extra_independently_records_fixed_null_set_CE_unknown_policy(self):
        ctx=dict(set_oldrt=SimpleNamespace(extra=lambda ctx:dict(schema='state_aligned_strongmotion_method_state_v1',normalizer='original')))
        cfg={k:dict(sha256=k) for k in ('selected_R_bank_root','teacher_anchor_complete_root','analysis_plan')}
        result=a.expected_extra(ctx,cfg)
        self.assertEqual(result['normalizer'],'original');self.assertEqual(result['null_logit'],0.)
        self.assertEqual(result['unknown_policy'],'excluded_from_known_set_unknown_may_contain_true_target')
        self.assertEqual(result['R_loss'],'logsumexp([0,known_logits])-unique_positive_logit_or_zero')


if __name__=='__main__':unittest.main()
