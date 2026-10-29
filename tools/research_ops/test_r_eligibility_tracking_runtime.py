"""新追踪身份及纯checkpoint元数据夹具；不导入Torch/旧runtime或打开实际输入。"""
import ast
from copy import deepcopy
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

import r_eligibility_tracking_runtime as rt
import r_eligibility_tracking_workers as workers


def inventories():
    original=[]; aligned=[]; completed=[]
    for fold in rt.FOLDS:
        for seed in rt.SEEDS:
            for regime in rt.REGIMES:
                mid=fold+str(seed)+regime; norm=dict(path='normalizer/'+mid+'.json',sha256='a'*64)
                original.append(dict(model_id='original-'+mid,fold=fold,seed=seed,regime=regime,normalizer=norm,binding=dict(initialization_sha256='b'*64)))
                aligned.append(dict(model_id='aligned-'+mid,baseline_model_id='original-'+mid,fold=fold,seed=seed,regime=regime,
                    original_normalizer=norm,expected_initialization_sha256='b'*64))
                completed.append(dict(path=str(rt.EXP/'training'/mid),fold=fold,seed=seed,regime=regime,receipt_sha256='c'*64,complete_sha256='d'*64))
    protocol=dict(path=str(rt.PROTOCOL_PATH),sha256=rt.PROTOCOL_SHA)
    state=dict(status=rt.TRAINING_STATUS,active=None,protocol_sha256=rt.PROTOCOL_SHA,completed_train=completed)
    return protocol,state,dict(schema=rt.ALIGNED_SCHEMA,models=aligned),dict(models=original)


def metadata_fixture():
    protocol,state,aligned,original=inventories(); spec=rt.model_specs(protocol,state,aligned,original)[0]
    mask=dict(path='not-opened-mask-input.json',sha256='e'*64); normalizer=dict(feature_dim=194,fixture=True)
    extra=dict(schema='r_candidate_eligibility_strongmotion_method_state_v1',training_objective=rt.OBJECTIVE,
        R_loss='original_unreduced_known_BCE_mask_then_window_mean_then_fixed_mean3R',S_loss='unchanged_original_known_pair_BCE_alpha_1_over_3',
        eligibility_mask_input=mask,normalizer=normalizer,use_pose=False,epoch_augmentation=False,full_original_known_forward_preserved=True,
        R_objective_code_sha256='f'*64,recorded_loop_sha256='1'*64)
    binding=dict(protocol_sha256=rt.PROTOCOL_SHA,method='motion',R_objective=rt.OBJECTIVE,initialization_sha256=spec['expected_initialization_sha256'],
        fold=spec['fold'],seed=spec['seed'],regime=spec['regime'],record_extension_schema='R_candidate_scoring_eligibility_record_extension_v1',
        mask_input_sha256=mask['sha256'],method_state_sha256=rt.digest(extra),R_objective_code_sha256='f'*64,recorded_loop_sha256='1'*64)
    receipt=dict(schema='R_candidate_eligibility_full_recorded_training_run_v1',status='complete',completed_updates=1000,formal=True,
        diagnostic_variant=None,actual_dtype='float32',amp=False,epoch_augmentation=False,binding=binding)
    complete=dict(schema='full_training_process_complete_v1',status='complete',actual_updates=1000,exposure_chain='chain',
        totals=dict(R_windows=3000,S_windows=1000*int(spec['regime']=='RS')))
    point=dict(path=str(Path(spec['run'])/'checkpoints/step_1000.pt'),completed_updates=1000,exposure_chain='chain')
    saved=dict(schema='full_training_checkpoint_v1',completed_updates=1000,exposure_chain='chain',binding=binding,extra=extra)
    return dict(),spec,receipt,complete,point,saved,normalizer,dict(mask_inputs={spec['fold']:mask})


class Contracts(unittest.TestCase):
    def test_18_new_models_explicit_two_baselines_and_180_matrix(self):
        protocol,state,aligned,original=inventories(); models=rt.model_specs(protocol,state,aligned,original)
        self.assertEqual(len(models),18); self.assertEqual(len({m['model_id'] for m in models}),18)
        self.assertTrue(all(m['model_id']!=m['baseline_model_id']!=m['original_baseline_model_id'] for m in models))
        panels=dict(original_heldout=list(rt.OLD),old_external=['old0','old1'],seven_observed=['seven'+str(i) for i in range(7)])
        sources={s:{} for p in panels.values() for s in p}; jobs=rt.tracking_matrix(models,sources,panels)
        self.assertEqual(len(jobs),180); self.assertEqual(len({j['job_id'] for j in jobs}),180)
        for job in jobs:
            body={k:v for k,v in job.items() if k!='job_id'}
            self.assertEqual(job['job_id'],rt.digest(['R_candidate_eligibility_tracking_v1',body])[:24])
            if job['sequence'] in rt.OLD:self.assertEqual(job['fold'],rt.OLD[job['sequence']])

    def test_training_pending_or_wrong_learning_or_repeated_unit_refused(self):
        protocol,state,aligned,original=inventories(); bad=deepcopy(state);bad['active']='still-running'
        with self.assertRaises(ValueError):rt.model_specs(protocol,bad,aligned,original)
        bad=deepcopy(state);bad['completed_train'][1]=bad['completed_train'][0]
        with self.assertRaises(ValueError):rt.model_specs(protocol,bad,aligned,original)
        with self.assertRaises(ValueError):rt.model_id(dict(protocol,sha256='0'*64),'game4',20261024,'R')

    def test_checkpoint_metadata_last1000_mask_ref_only_no_data_open(self):
        args=metadata_fixture()
        with patch.object(rt,'read_ref',side_effect=AssertionError('不得打开mask/池/标签')):
            binding=rt.validate_checkpoint_metadata(*args)
        self.assertEqual(binding,args[2]['binding'])
        self.assertEqual(args[5]['extra']['schema'],'r_candidate_eligibility_strongmotion_method_state_v1')

    def test_wrong_CE_or_diagnostic_or_mask_or_normalizer_refused(self):
        for kind in ('CE','diagnostic','mask','normalizer','last','binding'):
            args=list(deepcopy(metadata_fixture()))
            if kind=='CE':args[5]['extra']['training_objective']='candidate_set_CE'
            if kind=='diagnostic':args[2]['diagnostic_variant']='alltrue_original_BCE'
            if kind=='mask':args[7]['mask_inputs'][args[1]['fold']]['sha256']='0'*64
            if kind=='normalizer':args[6]['fixture']=False
            if kind=='last':args[4]['completed_updates']=950
            if kind=='binding':args[5]['binding']=dict(args[2]['binding'],seed=20261025)
            with self.subTest(kind=kind),self.assertRaises(ValueError):rt.validate_checkpoint_metadata(*args)

    def test_loader_has_no_training_prepare_auditor_or_pool_mask_open_calls(self):
        tree=ast.parse(inspect.getsource(rt.load_model)); calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        names={n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else '' for n in calls}
        self.assertNotIn('prepare',names); self.assertNotIn('audit_run',names); self.assertNotIn('complete_model',names)
        source=inspect.getsource(rt.load_model)
        self.assertIn("map_location='cpu'",source);self.assertIn('model_module.FeatureNormalizer.from_state',source)
        self.assertNotIn("checked(mask)",source)

    def test_worker_identity_and_no_inference_mask_or_training_labels(self):
        self.assertEqual(workers.TRACK_SCHEMA,'r_eligibility_tracking_receipt_v1');self.assertEqual(workers.METRIC_SCHEMA,'r_eligibility_tracking_metric_v1')
        text=inspect.getsource(workers.TrackWorker.payload)
        self.assertIn('self.BaseTrack.reset_id()',text);self.assertIn('self.STrack.reset_id()',text)
        self.assertIn('training_pool_or_mask_or_labels_opened=False',text)
        self.assertIn('inference_eligibility_mask_applied=False',text)
        self.assertNotIn('masked_real_domain_BCE',text)
        initialization=inspect.getsource(workers.TrackWorker.__init__)
        self.assertLess(initialization.index('self.guard.install()'),initialization.index('self.binding=Bindings'))


if __name__=='__main__':unittest.main()
