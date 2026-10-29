"""独立资格BCE审计纯夹具；不读取真实数据或训练权重。"""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest
import verify_r_eligibility_training as a
from test_r_candidate_eligibility_method import fixture
import test_audit_r_set_supervision_training as checkpoint_fixture
Tensor,Torch=checkpoint_fixture.Tensor,checkpoint_fixture.Torch


class Contracts(unittest.TestCase):
    def bindings(self,empty=False):
        result={}
        for i,mask in enumerate(((True,False,True),(False,True,False),(False,False,False))):
            window,side=fixture('w'+str(i),eligible=(False,False,False) if empty else mask)
            result[window['window_uid']]=a.independent_binding(window,side)
        return result

    def ledger(self,regime='R',empty=False):
        bindings=self.bindings(empty)
        rr=[dict(window_uid='w'+str(i%3),epoch=i//3,candidate_pairs=3,labelled_pairs=2) for i in range(3000)]
        ss=[dict(window_uid='s'+str(i),epoch=0,candidate_pairs=5,labelled_pairs=3) for i in range(1000)]
        table=dict(real=rr,synthetic=ss);logs=[]
        for i in range(1000):
            real=rr[3*i:3*i+3];synthetic=ss[i:i+1] if regime=='RS' else []
            accounting,effective=a.domain_accounting(bindings,real)
            rloss=0. if empty else .4;sloss=.3 if synthetic else None
            logs.append(dict(actual_update=i+1,update_index=i,real=deepcopy(real),synthetic=deepcopy(synthetic),R_windows=3,S_windows=len(synthetic),
                R_pairs=9,R_known_pairs=6,S_pairs=5*len(synthetic),S_known_pairs=3*len(synthetic),loss=rloss+(sloss/3 if sloss is not None else 0),
                real_loss=rloss,synthetic_loss=sloss,grad_l2=0. if empty and not synthetic else 1.,step_wall_seconds=.01,learning_rates=[.001],gradients_clipped=False,
                R_mask_accounting=accounting,R_mask_accounting_sha256=a.digest(accounting),**effective))
        self.chain(logs);return logs,table,bindings

    def chain(self,logs):
        chain='0'*64
        for row in logs:
            row.pop('chain_sha256',None);chain=a.hashlib.sha256((chain+a.canonical(row)).encode()).hexdigest();row['chain_sha256']=chain

    def test_independent_binding_matches_contract_without_label_selected_mask(self):
        import r_candidate_eligibility_method as producer
        window,side=fixture();self.assertEqual(a.independent_binding(window,side),producer.bind_window_mask(window,side))
        for edit in (lambda s:s.update(labels_used_to_choose_mask=True),lambda s:s.update(teacher_seed=20261025),
                     lambda s:s.update(candidate_UIDs=list(reversed(s['candidate_UIDs']))),lambda s:s.update(enabled=[True,None,True])):
            bad=deepcopy(side);edit(bad)
            with self.assertRaises(ValueError):a.independent_binding(window,bad)
        bad=deepcopy(window);bad['candidates'][0]['label']=True;bad['aligned_bank_metadata']['pair_labels'][0]=True
        with self.assertRaises(ValueError):a.independent_binding(bad,side)

    def test_raw_effective_unknown_and_empty_preserved(self):
        for regime in a.REGIMES:
            logs,table,bindings=self.ledger(regime);totals,chain=a.count_run(logs,table,regime,bindings)
            self.assertEqual((totals['R_windows'],totals['R_pairs'],totals['R_known_pairs']),(3000,9000,6000))
            self.assertEqual((totals['R_effective_known_pairs'],totals['R_effective_positive_pairs'],totals['R_effective_negative_pairs']),(2000,1000,1000))
            self.assertEqual((totals['R_effective_unknown_pairs'],totals['R_scoring_eligible_unknown_pairs']),(0,1000))
            self.assertEqual((totals['R_zero_effective_windows'],totals['R_effective_nonempty_windows']),(1000,2000))
            self.assertEqual(totals['S_windows'],1000*int(regime=='RS'));self.assertEqual(chain,logs[-1]['chain_sha256'])

    def test_rehashed_effective_fields_unknown_loss_or_source_change_refused(self):
        for key,value in [('R_effective_known_pairs',3),('R_effective_unknown_pairs',1),('R_scoring_eligible_unknown_pairs',0),('R_known_pairs',5),('learning_rates',[.002]),('loss',.9)]:
            logs,table,bindings=self.ledger('RS');logs[0][key]=value;self.chain(logs)
            with self.assertRaises(ValueError):a.count_run(logs,table,'RS',bindings)
        logs,table,bindings=self.ledger();logs[0]['R_mask_accounting']['windows'][0]['known_labels']=[0,1];logs[0]['R_mask_accounting_sha256']=a.digest(logs[0]['R_mask_accounting']);self.chain(logs)
        with self.assertRaises(ValueError):a.count_run(logs,table,'R',bindings)
        logs,table,bindings=self.ledger();table['real'][0]['epoch']=True
        with self.assertRaises(ValueError):a.count_run(logs,table,'R',bindings)

    def test_empty_R_still_1000_updates_zero_gradient_and_original_RS(self):
        for regime in a.REGIMES:
            logs,table,bindings=self.ledger(regime,True);totals,_=a.count_run(logs,table,regime,bindings)
            self.assertEqual(totals['R_zero_effective_windows'],3000);self.assertEqual(totals['R_effective_known_pairs'],0)
            logs[0]['real_loss']=.1;logs[0]['loss']+=.1;self.chain(logs)
            with self.assertRaises(ValueError):a.count_run(logs,table,regime,bindings)
        logs,table,bindings=self.ledger('R',True);logs[0]['grad_l2']=.1;self.chain(logs)
        with self.assertRaises(ValueError):a.count_run(logs,table,'R',bindings)

    def test_full_checkpoint_model_AdamW_rng_and_original_stepzero(self):
        fixtures=checkpoint_fixture.CheckpointBudget()
        for step in (0,50,1000):
            payload,template,np=fixtures.fixture(step);a.audit_payload(payload,step=step,binding='binding',extra='extra',chain='chain',template=template,torch=Torch,np=np)
        for edit in (lambda p:p.update(extra='old_method'),lambda p:p.update(rng_torch_cuda=[]),lambda p:p['optimizer']['state'][0].update(step=Tensor([999],()))):
            payload,template,np=fixtures.fixture(1000);edit(payload)
            with self.assertRaises(ValueError):a.audit_payload(payload,step=1000,binding='binding',extra='extra',chain='chain',template=template,torch=Torch,np=np)

    def test_prefetch_true_join_but_cache_false_not_fabricated(self):
        receipt=dict(prefetch=dict(closed=True,worker_alive=False,loaded=1000,yielded=1000),cache_peak_bytes=268435456,cache=dict(closed=False))
        self.assertFalse(a.validate_prefetch(receipt,producer_processes_absent=True)['cache_explicit_close_called'])
        with self.assertRaises(ValueError):a.validate_prefetch(receipt,producer_processes_absent=False)

    def numeric(self):
        groups=[dict(variant=v,device=d,regime=r,manual_updates=1,recorded_updates=1,R_windows=6,S_windows=2*int(r=='RS'),
            checkpoints=[dict(completed_updates=i,model_equal=True,optimizer_equal=True,all_RNG_equal=True) for i in (0,1)],per_parameter_gradients_exact=True,all_RNG_exact=True,loss_model_AdamW_exact=True)
            for v,d,r in sorted({(v,d,r) for v in ('alltrue_original_BCE','actual_mask') for d in ('cpu','cuda:0') for r in a.REGIMES}|{('empty_stress',d,'R') for d in ('cpu','cuda:0')})]
        return dict(schema='R_candidate_eligibility_numeric_admission_v1',status='complete_R_candidate_eligibility_CPU_CUDA_full_record_numeric_admission',protocol_sha256='sha',formal_optimizer_updates=0,
            actual_diagnostic_optimizer_updates=20,manual_optimizer_updates=10,recorded_optimizer_updates=10,diagnostic_R_windows=60,diagnostic_S_windows=8,all_groups_equal=True,
            actual_CPU_and_CUDA_numeric_verified=True,full_record_contract_verified=True,test_read=False,groups=groups)

    def test_twenty_numeric_updates_separate_all_ten_groups(self):
        proof=self.numeric();self.assertEqual(a.diagnostic_budget(proof,'sha')['diagnostic_updates_separate'],20)
        for edit in (lambda p:p.update(actual_diagnostic_optimizer_updates=8),lambda p:p.update(groups=p['groups'][:-1]),lambda p:p['groups'][0].update(all_RNG_exact=False)):
            bad=deepcopy(proof);edit(bad)
            with self.assertRaises(ValueError):a.diagnostic_budget(bad,'sha')

    def test_actual_process_identity_not_reused_PID_or_verifier(self):
        rows=[dict(ProcessId=i,Name='python.exe',CommandLine='python D:/code/'+s+'.py') for i,s in enumerate(('r_eligibility_train','control_r_eligibility_training','validate_r_eligibility_numeric','verify_r_eligibility_training','unrelated'))]
        self.assertEqual([p['ProcessId'] for p in a.blocked_processes(rows)],[0,1,2])
        samples=[dict(Name='python.exe',CommandLine='python D:/code/r_eligibility_train.py --output "D:\\research\\run"'),
            dict(Name='python.exe',CommandLine='python D:/code/r_eligibility_train.py --output D:/research/other'),
            dict(Name='python.exe',CommandLine='python D:/code/control_r_eligibility_training.py --run D:/research/run')]
        self.assertEqual(a.run_producers(samples,Path('D:/research/run')),[samples[0]])

    def test_gate_inheritance_requires_exact_source_chain_points_and_21_prior_reads(self):
        args=dict(run='newrun',protocol=dict(path='config',sha256='protocol'),source_refs={'steps':dict(path='steps',sha256='steps')},
            points=[dict(completed_updates=i,sha256=str(i)) for i in range(0,1001,50)],unit=dict(fold='game4',seed=20261024,regime='R'),totals=dict(R_windows=3000),method_sha='method')
        gate=dict(schema='independent_R_candidate_eligibility_first_run_audit_v1',status='complete_first_R_candidate_eligibility1000_full21_checkpoints_independently_verified',
            run=args['run'],protocol=args['protocol'],source_refs=args['source_refs'],checkpoint_points=args['points'],unit=args['unit'],counts=args['totals'],
            full_checkpoints_read=21,inherited_checkpoint_readbacks=0,complete_checkpoint_coverage=21,method_state_sha256='method',new_optimizer_updates=0,test_read=False)
        with patch.object(a,'physical',side_effect=Path):
            a.validate_inherited_gate(gate,**args)
            for edit in (lambda p:p.update(full_checkpoints_read=1),lambda p:p.update(inherited_checkpoint_readbacks=21),
                         lambda p:p['source_refs']['steps'].update(sha256='changed'),lambda p:p['checkpoint_points'][0].update(sha256='changed'),
                         lambda p:p.update(method_state_sha256='oldCE'),lambda p:p.update(run='another_run')):
                bad=deepcopy(gate);edit(bad)
                with self.assertRaises(ValueError):a.validate_inherited_gate(bad,**args)

    def test_state_requires_18_unique_runs_and_actual_child_exit(self):
        entries=[dict(x,path='run'+str(i),receipt_sha256=str(i)) for i,x in enumerate(a.matrix())]
        state=dict(schema='R_candidate_eligibility18_training_control_v1',status=a.TRAINING_STATUS,active=None,formal_optimizer_updates=18000,unverified_completed_runs=[],completed_train=entries,
            observed_child_exits=[dict(job={k:e[k] for k in ('fold','seed','regime')},exit_code=0,reported_completed_updates=1000,receipt_sha256=e['receipt_sha256']) for e in entries])
        with patch.object(a,'physical',side_effect=Path):
            self.assertEqual(a.state_entries(state,dict(training_matrix=a.matrix())),entries)
            for edit in (lambda s:s.update(active=dict(pid=42)),lambda s:s['completed_train'][1].update(path='run0'),
                         lambda s:s['observed_child_exits'][0].update(exit_code=1),lambda s:s.update(completed_train=entries[:-1])):
                bad=deepcopy(state);edit(bad)
                with self.assertRaises(ValueError):a.state_entries(bad,dict(training_matrix=a.matrix()))


if __name__=='__main__':unittest.main()
