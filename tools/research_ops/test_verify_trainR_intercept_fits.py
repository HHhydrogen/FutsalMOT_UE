"""十八截距终验的必要CPU夹具；不加载实际模型或读取研究产物。"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import trainR_intercept_runtime as runtime
import verify_trainR_intercept_fits as verify


def sha_value(value):return hashlib.sha256(verify.canonical(value).encode()).hexdigest()


def rechain(records):
    chain='0'*64
    for record in records:
        record.pop('record_chain_sha256',None)
        chain=hashlib.sha256((chain+verify.canonical(record)).encode()).hexdigest();record['record_chain_sha256']=chain
    return chain


def fixture():
    spec=dict(model_id='model_fixture',regime='R',fold='game4',seed=20261024,
        clean_R_pool=dict(path='never_open_pool',sha256='a'*64),normalizer=dict(path='never_open_normalizer',sha256='b'*64))
    records=[]
    for index in range(1000):
        labels=([1]*9+[0]) if index==0 else [0] if index==1 else [None]
        uid=sha_value(['window',index]);history=['SNMOT-097:%06d:000001'%(frame+1) for frame in (1,2,3)]
        candidates=['SNMOT-097:000006:%06d'%(i+1) for i in range(len(labels))]
        records.append(dict(window_uid=uid,domain='real',game='game6',sequence='SNMOT-097',source_uid=uid,source_pool_row=index,
            history_UIDs=history,candidate_UIDs=candidates,pair_source_UIDs=[sha_value([uid,history,c]) for c in candidates],
            labels=labels,known_mask=[label is not None for label in labels],history_frame_indices=[1,2,3],
            candidate_frame_index=5,candidate_frame_number=6,epoch=0,augmentation=False,use_pose=False,
            logits=[0.]*len(labels),features_sha256=sha_value(['unchanged_features',index]),model_id=spec['model_id']))
    chain=rechain(records)
    fit=runtime.fit_intercept([{key:row[key] for key in ('window_uid','logits','labels','candidate_UIDs')} for row in records])
    counts={key:value for key,value in fit['totals'].items() if key!='supervised_window_count'}
    fit.update(model_spec=spec,**{key:spec[key] for key in ('model_id','regime','fold','seed')},
        input_receipt=dict(model_id=spec['model_id'],fold=spec['fold'],seed=spec['seed'],regime=spec['regime'],pool=spec['clean_R_pool'],
            normalizer=spec['normalizer'],original_pool_order_UID_sha256=sha_value([r['window_uid'] for r in records]),
            objective_denominator=1000,unknown_pairs_retained_not_fitted=True,normalizer_fitted=False,augmentation=False,
            new_optimizer_updates=0,model_forward_calls=0,actual_model_window_evaluations=0,
            planned_extra_R_model_window_evaluations=1000,validation_or_test_read=False,training_S_windows_read=False,counts=counts),
        recording=dict(record_chain_sha256=chain,forward_calls=1000,RNG_unchanged=True,model_digest_before='e'*64,
            model_digest_after='e'*64,optimizer_state='not_applicable_scalar_root_finding_no_SGD',wall_seconds=.1))
    return fit,records,spec


class FitTerminal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=fixture()

    def data(self):return deepcopy(self.original)

    def test_full_unknown_window_equal_negative_beta_and_FP32_records(self):
        fit,records,spec=self.data();result=verify.check_fit(fit,records,spec,runtime.PARAMETERS)
        self.assertEqual(result['totals']['windows'],1000);self.assertEqual(result['totals']['empty_known_window_count'],998)
        self.assertEqual(result['totals']['all_pair_count'],1009);self.assertEqual(result['totals']['known_pair_count'],11)
        self.assertEqual(result['totals']['unknown_pair_count'],998)
        self.assertLess(result['beta64'],0.)
        self.assertAlmostEqual(result['beta64'],-.20067069546215138,places=9)
        self.assertIsNone(result['performance_pass_flag'])

    def test_pooled_pair_fit_cannot_replace_window_equal_objective(self):
        fit,records,spec=self.data();fit['beta64']=1.5040773967762742
        with self.assertRaisesRegex(ValueError,'部署beta'):verify.check_fit(fit,records,spec,runtime.PARAMETERS)

    def test_unknown_labels_masks_FP32_and_chain_tampering_refused(self):
        for change in ('mask','unknown','float64','chain'):
            fit,records,spec=self.data()
            if change=='mask':records[2]['known_mask']=[True]
            elif change=='unknown':records[2]['labels']=[False]
            elif change=='float64':records[0]['logits'][0]=.123456789012345
            else:records[0]['record_chain_sha256']='f'*64
            if change!='chain':rechain(records)
            with self.subTest(change=change),self.assertRaises(ValueError):verify.check_fit(fit,records,spec,runtime.PARAMETERS)

    def test_saved_search_point_derivative_and_continuity_required(self):
        for change in ('derivative','bound','premature_stop'):
            fit,records,spec=self.data()
            if change=='derivative':fit['bisection_trace'][0]['derivative']+=.01
            elif change=='bound':fit['bisection_trace'][1]['lower']=-100.
            else:fit['bisection_trace']=fit['bisection_trace'][:1]
            with self.subTest(change=change),self.assertRaises(ValueError):verify.check_fit(fit,records,spec,runtime.PARAMETERS)

    def test_FP32_projection_drift_and_alias_cannot_be_faked(self):
        for change in ('zero','metric','alias'):
            fit,records,spec=self.data()
            if change=='zero':fit['apply_beta32']=0.
            elif change=='metric':fit['after_apply32']['NLL']+=.01
            else:fit['original_prediction_alias_authorized']=True
            with self.subTest(change=change),self.assertRaises(ValueError):verify.check_fit(fit,records,spec,runtime.PARAMETERS)

    def test_exact_zero_has_no_search_and_does_not_authorize_alias(self):
        _,records,spec=self.data()
        for row in records:row['labels']=[1,0];row['logits']=[0.,0.];row['candidate_UIDs']=['SNMOT-097:000006:000001','SNMOT-097:000006:000002'];row['known_mask']=[True,True];row['pair_source_UIDs']=[sha_value([row['window_uid'],row['history_UIDs'],c]) for c in row['candidate_UIDs']]
        chain=rechain(records);fit=runtime.fit_intercept([{k:row[k] for k in ('window_uid','logits','labels','candidate_UIDs')} for row in records])
        old=self.original[0];fit.update({key:deepcopy(old[key]) for key in ('model_spec','model_id','regime','fold','seed','input_receipt','recording')})
        fit['input_receipt']['counts']={key:value for key,value in fit['totals'].items() if key!='supervised_window_count'}
        fit['recording']['record_chain_sha256']=chain
        result=verify.check_fit(fit,records,spec,runtime.PARAMETERS)
        self.assertEqual(result['apply_beta32'],0.);self.assertFalse(fit['original_prediction_alias_authorized'])

    def test_matrix18_and_same_fold_six_feature_digests(self):
        fit,records,spec=self.data();base=verify.check_fit(fit,records,spec,runtime.PARAMETERS);checks=[]
        for regime in ('R','RS'):
            for fold in verify.FOLDS:
                for seed in verify.SEEDS:
                    value=deepcopy(base);value.update(regime=regime,fold=fold,seed=seed,model_id=f'{regime}_{fold}_{seed}');checks.append(value)
        inventory=dict(models=[dict(model_id=c['model_id']) for c in checks])
        totals=verify.check_matrix(checks,inventory)
        self.assertEqual(totals['clean_R_model_window_evaluations'],18000);self.assertEqual(totals['optimizer_updates'],0)
        changed=deepcopy(checks);changed[1]['signatures']['shared_clean_R_input_signature_sha256']='c'*64
        with self.assertRaises(ValueError):verify.check_matrix(changed,inventory)
        with self.assertRaises(ValueError):verify.check_matrix(checks[:-1],inventory)

    def test_actual_process_name_and_time_guard_not_PID_or_verifier_self(self):
        now=datetime.now(timezone.utc);state=dict(parent_pid=100,created_utc=(now-timedelta(seconds=30)).isoformat())
        own=dict(Name='python.exe',ProcessId=200,CommandLine='python verify_trainR_intercept_fits.py --config config.json')
        unrelated=dict(Name='python.exe',ProcessId=100,CommandLine='python unrelated.py')
        stale_spawn=dict(Name='python.exe',ProcessId=300,CommandLine='python -c "spawn_main(parent_pid=100, pipe_handle=4)"',
            CreationUtc=(now-timedelta(days=1)).isoformat())
        self.assertEqual(verify.blocked_processes([own,unrelated,stale_spawn],state),[])
        active=dict(Name='python.exe',ProcessId=400,CommandLine='python D:/code/trainR_intercept_fit_control.py --execute')
        self.assertEqual(verify.blocked_processes([active],state),[active])
        fresh=deepcopy(stale_spawn);fresh['CreationUtc']=now.isoformat()
        self.assertEqual(verify.blocked_processes([fresh],state),[fresh])

    def test_result_SHA_and_test_path_guards_no_old_data_reads(self):
        with TemporaryDirectory() as directory,patch.object(verify,'R',Path(directory)):
            path=Path(directory)/'new_result.json';path.write_text('{}',encoding='utf-8');ref=verify.ref(path)
            self.assertEqual(verify.checked(ref),path)
            path.write_text('{"changed":true}',encoding='utf-8')
            with self.assertRaises(ValueError):verify.checked(ref)
            with self.assertRaises(ValueError):verify.physical(Path(directory)/'test'/'not_opened.json')
            with self.assertRaises(ValueError):verify.physical(Path(directory)/'SNMOT-187'/'not_opened.json')


if __name__=='__main__':unittest.main(verbosity=2)
