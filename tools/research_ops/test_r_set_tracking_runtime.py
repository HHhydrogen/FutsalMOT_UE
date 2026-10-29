"""R集合监督追踪身份/双参照/训练闭合与局部导入的纯CPU元数据夹具。"""
from copy import deepcopy
from pathlib import Path
import os,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import r_set_tracking_runtime as rt
import test_state_aligned_tracking_runtime as old_fixture

def fixture():
    old_protocol,original,old_state,panels,sources=old_fixture.fixture()
    aligned=dict(schema=rt.base.SCHEMA,models=rt.base.model_specs(old_protocol,old_state,original),sources=sources,panels=panels)
    protocol=dict(path=str(rt.PROTOCOL_PATH),sha256=rt.PROTOCOL_SHA)
    state=deepcopy(old_state);state.update(status=rt.TRAINING_STATUS,protocol_sha256=rt.PROTOCOL_SHA)
    for row in state['completed_train']:row['path']=row['path'].replace('state_aligned_training_a01','r_set_supervision_a01')
    original.update(sources=sources,panels=panels)
    return protocol,original,aligned,state,panels,sources

class Contracts(unittest.TestCase):
    def test_eighteen_new_ids_bind_both_baselines(self):
        p,o,a,s,_,_=fixture();models=rt.model_specs(p,s,a,o)
        self.assertEqual(len(models),18);self.assertEqual(len({m['model_id'] for m in models}),18)
        self.assertTrue(all(len({m['model_id'],m['baseline_model_id'],m['original_baseline_model_id']})==3 for m in models))
        self.assertTrue(all(m['training_objective']==rt.OBJECTIVE and not m['intercept_applied'] for m in models))
    def test_old_or_unfrozen_protocol_cannot_alias_new(self):
        p,o,a,s,_,_=fixture();p['sha256']='a'*64
        with self.assertRaises(ValueError):rt.model_specs(p,s,a,o)
    def test_partial_duplicate_and_baseline_mismatch_refused(self):
        p,o,a,s,_,_=fixture()
        for edit in (lambda:s.update(active={}),lambda:s['completed_train'].__setitem__(-1,s['completed_train'][0]),lambda:a['models'][0].update(baseline_model_id='wrong')):
            p,o,a,s,_,_=fixture();edit()
            with self.assertRaises(ValueError):rt.model_specs(p,s,a,o)
    def test_180_jobs_exact_two_baselines_heldout_only(self):
        p,o,a,s,panels,sources=fixture();models=rt.model_specs(p,s,a,o);jobs=rt.tracking_matrix(models,sources,panels)
        self.assertEqual(len(jobs),180);self.assertEqual(len({j['job_id'] for j in jobs}),180)
        self.assertEqual({j['baseline_model_id'] for j in jobs},{m['model_id'] for m in a['models']})
        self.assertEqual({j['original_baseline_model_id'] for j in jobs},{m['model_id'] for m in o['models']})
        self.assertTrue(all(j['fold']==rt.OLD[j['sequence']] for j in jobs if j['sequence'] in rt.OLD))
    def test_changed_gate_or_missing_jobs_cannot_pass(self):
        p,o,a,s,panels,sources=fixture();models=rt.model_specs(p,s,a,o)
        inv=dict(schema=rt.SCHEMA,sources=sources,panels=panels,models=models)
        cfg=dict(learning_protocol=p,sources=sources,panels=panels,jobs=rt.tracking_matrix(models,sources,panels),tracker_parameters=rt.FIXED_ARGS,test_sealed=True,new_optimizer_updates=0,source_state_aligned_runtime=rt.BASE_REFERENCE)
        self.assertEqual(rt.validate_jobs(cfg,inv),models)
        for edit in (lambda c:c['jobs'].pop(),lambda c:c.update(calibrations={}),lambda c:c.update(tracker_parameters=dict(rt.FIXED_ARGS,match_thresh=.7))):
            changed=deepcopy(cfg);edit(changed)
            with self.assertRaises(ValueError):rt.validate_jobs(changed,inv)
    def test_real_budget_and_completion_root_both_required(self):
        p,_,_,s,_,_=fixture();cfg=dict(learning_protocol=p,training_budget=dict(path='audit'),training_complete=dict(path='complete'))
        audit=dict(status=rt.AUDIT_STATUS,protocol=p,training_processes_absent=True,complete_checkpoints_read_back=378,
            nine_paired_R_RS_exposures_equal=True,actual_totals=dict(updates=18000,R_windows=54000,S_windows=9000),control_state=dict(path='state'))
        complete=dict(status=rt.COMPLETE_STATUS,test_read=False,budget_audit=cfg['training_budget'],protocol=p,actual_training_and_audit_processes_absent=True)
        values=dict(audit=audit,complete=complete,state=s)
        with patch.object(rt,'read_ref',side_effect=lambda r:values[r['path']]):
            self.assertEqual(rt.training_closure(cfg),(audit,s))
            for key,value in [('status','started'),('actual_training_and_audit_processes_absent',False)]:
                changed=deepcopy(complete);changed[key]=value;values['complete']=changed
                with self.assertRaises(ValueError):rt.training_closure(cfg)
            values['complete']=complete;audit['actual_totals']['updates']=17999
            with self.assertRaises(ValueError):rt.training_closure(cfg)
    def test_CPU_required_before_loading_any_metadata(self):
        with patch.dict(os.environ,CUDA_VISIBLE_DEVICES='0'),patch.object(rt,'training_closure') as closure:
            with self.assertRaises(ValueError):rt.load_model({},{})
            closure.assert_not_called()
    def test_scope_restores_path_on_success_and_exception(self):
        protocol=dict(bundle=str(rt.R/'code'/('a'*64)),source_training_protocol=dict(path='old'))
        original=dict(bundle=str(rt.R/'code'/('b'*64)));before=list(sys.path)
        def read(ref):return original if ref.get('path')=='old' else protocol
        with patch.object(rt,'read_ref',side_effect=read),patch.object(rt,'source',return_value=dict(path='fixture',sha256='a'*64)),patch.object(rt,'safe',side_effect=Path):
            for raises in (False,True):
                try:
                    with rt.learning_import_scope(dict(learning_protocol={})):
                        sys.path.insert(0,'mutated_by_prepare')
                        if raises:raise RuntimeError('fixture')
                except RuntimeError:pass
                self.assertEqual(sys.path,before)
    def test_scope_rejects_wrong_same_named_training_module(self):
        from types import SimpleNamespace
        protocol=dict(bundle=str(rt.R/'code'/('a'*64)),source_training_protocol=dict(path='old'))
        with patch.object(rt,'read_ref',return_value=protocol),patch.object(rt,'source',return_value=dict(path='right',sha256='a'*64)),\
             patch.object(rt,'checked',return_value=Path('right')),patch.object(rt,'safe',side_effect=Path),\
             patch.dict(sys.modules,state_aligned_training_inputs=SimpleNamespace(__file__='wrong')):
            with self.assertRaises(ValueError):
                with rt.learning_import_scope(dict(learning_protocol={})):pass
    def test_old_run_schema_rejected_before_torch_load(self):
        p,o,a,s,_,_=fixture();spec=rt.model_specs(p,s,a,o)[0]
        cfg=dict(learning_protocol=p,aligned_inventory=dict(path='aligned'),source_inventory=dict(path='original'))
        values=dict(aligned=a,original=o);values[spec['training_receipt']['path']]=dict(schema='state_aligned_full_recorded_training_run_v1')
        values[spec['training_complete']['path']]={}
        with patch.dict(os.environ,CUDA_VISIBLE_DEVICES='-1'),patch.object(rt,'training_closure',return_value=({},s)),patch.object(rt,'read_ref',side_effect=lambda r:values[r['path']]):
            with self.assertRaises(ValueError):rt.load_model(cfg,spec)
    def test_direct_new_checkpoint_loader_fixture_without_model_execution(self):
        from types import SimpleNamespace
        from contextlib import nullcontext
        from unittest.mock import Mock
        p,o,a,s,_,_=fixture();spec=rt.model_specs(p,s,a,o)[0]
        cfg=dict(learning_protocol=p,aligned_inventory=dict(path='aligned'),source_inventory=dict(path='original'),training_budget={},training_complete={})
        extra=dict(training_objective=rt.OBJECTIVE)
        binding=dict(protocol_sha256=p['sha256'],method='motion',initialization_sha256=spec['expected_initialization_sha256'],
            fold=spec['fold'],seed=spec['seed'],regime=spec['regime'],R_objective='candidate_set_CE_fixed_no_match_logit_0',method_state_sha256=rt.digest(extra))
        receipt=dict(schema='r_set_supervision_full_recorded_training_run_v1',status='complete',completed_updates=1000,epoch_augmentation=False,actual_dtype='float32',amp=False,binding=binding)
        normalizer=SimpleNamespace(state=lambda:dict(normalizer='original'))
        model=Mock();model.parameters.return_value=[SimpleNamespace(device=SimpleNamespace(type='cpu'),dtype='FP32',numel=lambda:14593)]
        model.state_dict.return_value={'weight':'fixture'};model.training=False
        ctx=dict(normalizer=normalizer,set_oldrt=SimpleNamespace(new_model=Mock(return_value=model)))
        point=dict(path=str(Path(spec['run'])/'checkpoints/step_1000.pt'),completed_updates=1000,sha256='x')
        loader=SimpleNamespace(audit_run=Mock(),prepare=Mock(return_value=ctx),read=Mock(return_value=point),extra=Mock(return_value=extra))
        payload=dict(schema='full_training_checkpoint_v1',binding=binding,completed_updates=1000,extra=extra,model={'weight':'fixture'})
        torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda:False),float32='FP32',load=Mock(return_value=payload))
        values={'aligned':a,'original':o,spec['training_receipt']['path']:receipt,spec['training_complete']['path']:{},spec['original_normalizer']['path']:normalizer.state()}
        with patch.dict(os.environ,CUDA_VISIBLE_DEVICES='-1'),patch.dict(sys.modules,torch=torch),\
             patch.object(rt,'training_closure',return_value=({},s)),patch.object(rt,'read_ref',side_effect=lambda r:values[r['path']]),\
             patch.object(rt,'learning_import_scope',return_value=nullcontext()),patch.object(rt,'learning_loader',return_value=loader),patch.object(rt,'checked',side_effect=lambda r:Path(r['path'])):
            result=rt.load_model(cfg,spec)
        self.assertIs(result['model'],model);model.load_state_dict.assert_called_once_with(payload['model']);model.eval.assert_called_once()
        self.assertEqual(result['receipt']['training_objective'],rt.OBJECTIVE);self.assertFalse(result['receipt']['intercept_applied'])
        loader.audit_run.assert_called_once();ctx['set_oldrt'].new_model.assert_called_once_with(ctx,device='cpu')
    def test_both_baseline180_sources_match_exact_cells(self):
        p,o,a,s,panels,sources=fixture();aligned_jobs=rt.base.tracking_matrix(a['models'],sources,panels)
        original_by_id={m['model_id']:m for m in a['models']}
        o['baseline_units']=[dict(regime=j['regime'],sequence=j['sequence'],fold=j['fold'],seed=j['seed'],model_id=original_by_id[j['model_id']]['baseline_model_id']) for j in aligned_jobs]
        reports=[dict(path='report'+str(i),sha256='a'*64) for i in range(180)]
        manifest=dict(status='complete180_state_aligned_tracking_and_evaluation',config_sha256='aligned_protocol_sha',tracking=[dict(job=j) for j in aligned_jobs],reports=[dict(job=j,report=r) for j,r in zip(aligned_jobs,reports)])
        cfg=dict(sources=sources,panels=panels,aligned_inventory=dict(path='aligned'),aligned_tracking_manifest=dict(path='manifest'),aligned_tracking_protocol=dict(path='protocol',sha256='aligned_protocol_sha'),
            aligned_analysis=dict(path='analysis'),source_inventory=dict(path='original'),source_state_aligned_runtime=rt.BASE_REFERENCE)
        analysis=dict(status='complete180_state_aligned_tracking_all360_results_and_paired_intervals',protocol=cfg['aligned_tracking_protocol'],inventory=cfg['aligned_inventory'],
            source_inventory=cfg['source_inventory'],panels=panels,formal_evaluation_manifest=cfg['aligned_tracking_manifest'],test_read=False,new_tracking_evaluations=180,all_actual_reports=reports)
        values=dict(aligned=a,manifest=manifest,protocol=dict(inventory=cfg['aligned_inventory']),analysis=analysis)
        with patch.object(rt.base,'source_bindings',return_value=dict(inventory=o)),patch.object(rt,'read_ref',side_effect=lambda r:values[r['path']]):
            rt.source_bindings(cfg);manifest['reports'][-1]=manifest['reports'][0]
            with self.assertRaises(ValueError):rt.source_bindings(cfg)
    def test_explicit_frozen_runtime_reference_cannot_be_replaced(self):
        with self.assertRaises(ValueError):rt.source_bindings(dict(source_state_aligned_runtime=dict(path='same_named_local.py',sha256=rt.BASE_SHA)))
        self.assertEqual(Path(rt.base.__file__),rt.BASE_PATH)
        self.assertNotIn('state_aligned_tracking_runtime',rt.base.__name__.split('.')[:-1])
    def test_frozen_runtime_loader_refuses_changed_bytes(self):
        with patch.object(Path,'read_bytes',return_value=b'changed'):
            with self.assertRaises(ValueError):rt.frozen_base()
    def test_actual_base_source_bindings_never_validates_new_learning_schema(self):
        cfg=dict(source_inventory=dict(path='original'),source_velocity_protocol=dict(path='velocity'),sources={'s':{}},panels={'p':[]},registries={},
            source_worker_framework=dict(path='framework',sha256=rt.FRAMEWORK_SHA),learning_protocol=dict(path='new_R_set_schema_must_not_be_read'))
        values=dict(original=dict(sources=cfg['sources'],panels=cfg['panels']),
            velocity=dict(sources=cfg['sources'],panels=cfg['panels'],registries={},source_tracking_config=dict(path='old'),source_seven_tracking_config=dict(path='seven')),
            old=dict(training_protocol=dict(path='training')),seven={},training=dict(v9_protocol=dict(path='v9')),v9={})
        with patch.object(rt.base,'read_ref',side_effect=lambda r:values[r['path']]),patch.object(rt.base,'module',return_value='pure_function_module'),\
             patch.object(rt.base,'source',return_value=dict(path='frozen_pure_function')):
            result=rt.base.source_bindings(cfg)
        self.assertEqual(result['worker_framework'],'pure_function_module');self.assertIs(result['training'],values['training'])

if __name__=='__main__':unittest.main()
