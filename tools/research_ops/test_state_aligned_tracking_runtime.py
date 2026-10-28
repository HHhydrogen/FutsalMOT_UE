"""独立新模型身份、完整180矩阵与训练闭合门禁；不加载真实权重/GT。"""
from pathlib import Path
from copy import deepcopy
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import state_aligned_tracking_runtime as rt

def fixture():
    protocol=dict(path=str(rt.EXP/'training_frozen_a01/protocol.json'),sha256='f'*64)
    models=[];completed=[]
    for fold in rt.FOLDS:
        for seed in rt.SEEDS:
            for regime in rt.REGIMES:
                models.append(dict(model_id='old'+fold+str(seed)+regime,fold=fold,seed=seed,regime=regime,
                    normalizer=dict(path='normalizer',sha256='a'*64),binding=dict(initialization_sha256='a'*64)))
                completed.append(dict(fold=fold,seed=seed,regime=regime,path=str(rt.EXP/'training_control_a01/runs'/fold/str(seed)/regime/'training'),receipt_sha256='b'*64,complete_sha256='c'*64))
    state=dict(status='complete18_state_aligned_training_wait_independent_audit_tracking',active=None,protocol_sha256=protocol['sha256'],completed_train=completed)
    panels=dict(original_heldout=list(rt.OLD),old_external=['ext1','ext2'],seven_observed=['seven'+str(i) for i in range(7)])
    sources={s:dict(sequence=s) for v in panels.values() for s in v}
    return protocol,dict(models=models),state,panels,sources

class Contracts(unittest.TestCase):
    def test_new_model_ID_distinct_with_explicit_baseline_mapping(self):
        protocol,old,state,_,_=fixture();specs=rt.model_specs(protocol,state,old)
        self.assertEqual(len({s['model_id'] for s in specs}),18)
        self.assertTrue(all(s['model_id']!=s['baseline_model_id'] and not s['intercept_applied'] and not s['use_pose'] for s in specs))
        changed=deepcopy(protocol);changed['sha256']='d'*64
        self.assertNotEqual(rt.model_id(protocol,'game4',20261024,'R'),rt.model_id(changed,'game4',20261024,'R'))
    def test_partial_training_or_duplicate_cell_refused(self):
        protocol,old,state,_,_=fixture();state['active']={}
        with self.assertRaises(ValueError):rt.model_specs(protocol,state,old)
        state['active']=None;state['completed_train'][-1]=state['completed_train'][0]
        with self.assertRaises(ValueError):rt.model_specs(protocol,state,old)
    def test_exact180_matches_and_no_training_other_fold_sources(self):
        protocol,old,state,panels,sources=fixture();models=rt.model_specs(protocol,state,old);jobs=rt.tracking_matrix(models,sources,panels)
        self.assertEqual(len(jobs),180);self.assertEqual(len({j['job_id'] for j in jobs}),180)
        for j in jobs:
            if j['sequence'] in rt.OLD:self.assertEqual(rt.OLD[j['sequence']],j['fold'])
        self.assertEqual({j['baseline_model_id'] for j in jobs},{m['model_id'] for m in old['models']})
    def test_inventory_jobs_thresholds_and_intercept_source_rejected(self):
        protocol,old,state,panels,sources=fixture();models=rt.model_specs(protocol,state,old)
        inventory=dict(schema=rt.SCHEMA,models=models,sources=sources,panels=panels)
        cfg=dict(jobs=rt.tracking_matrix(models,sources,panels),sources=sources,panels=panels,tracker_parameters=rt.FIXED_ARGS,test_sealed=True,new_optimizer_updates=0)
        self.assertEqual(rt.validate_jobs(cfg,inventory),models)
        for edit in (lambda c:c['jobs'].pop(),lambda c:c.update(calibrations={}),lambda c:c.update(tracker_parameters=dict(rt.FIXED_ARGS,match_thresh=.7))):
            c=deepcopy(cfg);edit(c)
            with self.assertRaises(ValueError):rt.validate_jobs(c,inventory)
    def test_all_training_budget_actual_exit_required(self):
        protocol,_,state,_,_=fixture();audit=dict(status=rt.AUDIT_STATUS,protocol=protocol,control_state=dict(path='state'),training_processes_absent=True,
            complete_checkpoints_read_back=378,nine_paired_R_RS_exposures_equal=True,actual_totals=dict(updates=18000,R_windows=54000,S_windows=9000))
        cfg=dict(learning_protocol=protocol,training_budget=dict(path='audit'))
        data={'audit':audit,'state':state}
        with patch.object(rt,'read_ref',side_effect=lambda r:data[r['path']]):
            self.assertEqual(rt.training_closure(cfg),(audit,state));audit['training_processes_absent']=False
            with self.assertRaises(ValueError):rt.training_closure(cfg)
    def test_model_loading_requires_CPU_before_any_metadata(self):
        with patch.dict('os.environ',{'CUDA_VISIBLE_DEVICES':'0'}):
            with self.assertRaises(ValueError):rt.load_model({}, {})
    def test_learning_local_import_scope_restores_on_success_and_failure(self):
        bundle=rt.R/'code'/('b'*64);reference=dict(path=str(bundle/'tools/research_ops/state_aligned_training_inputs.py'),sha256='a'*64)
        before=list(sys.path)
        with patch.object(rt,'read_ref',return_value=dict(bundle=str(bundle))),patch.object(rt,'source',return_value=reference),patch.object(rt,'safe',side_effect=Path):
            with rt.learning_import_scope(dict(learning_protocol={})):
                self.assertEqual(sys.path[0],str(bundle/'tools/research_ops'))
            self.assertEqual(sys.path,before)
            with self.assertRaises(RuntimeError):
                with rt.learning_import_scope(dict(learning_protocol={})):raise RuntimeError('fixture')
            self.assertEqual(sys.path,before)

if __name__=='__main__':unittest.main()
