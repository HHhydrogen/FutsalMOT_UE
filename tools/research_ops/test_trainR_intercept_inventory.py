"""trainR截距来源清单的CPU合同；不读取实际权重、窗口或预测。"""
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import trainR_intercept_inventory as inventory


class Inventory(unittest.TestCase):
    def test_four_explicit_inputs_and18_unique_model_ids(self):
        self.assertEqual(list(inspect.signature(inventory.build_inventory).parameters),
            ['source_velocity_cfg_ref','ABC_cfg_ref','v10_training_ref','baseline_analysis_refs'])
        ids={inventory.model_id(r,f,s) for r in inventory.REGIMES for f in inventory.FOLDS for s in inventory.SEEDS}
        self.assertEqual(len(ids),18)

    def test_R_RS90_each_matrix_heldout_only_own_fold(self):
        sources=dict.fromkeys([*inventory.OLD,*['X'+str(i) for i in range(9)]])
        cells=inventory.expected_baseline_cells(sources)
        self.assertEqual(len(cells),180)
        self.assertTrue(all(fold==inventory.OLD[seq] for _,seq,fold,_ in cells if seq in inventory.OLD))
        self.assertEqual(sum(r=='R' for r,*_ in cells),90)

    def test_weight_pool_cache_MOT_refs_never_read(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            for filename in ('last.pt','real_pool.jsonl','cache.jsonl','seq.txt'):
                path=Path(directory)/filename;path.write_bytes(b'unread')
                reference=dict(path=str(path),sha256='a'*64)
                with patch.object(Path,'open',side_effect=AssertionError('不得读数据')):
                    inventory.data_ref(reference)
                with self.assertRaises(ValueError):inventory.read(reference)

    def test_metadata_SHA_and_GT_guard(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            path=Path(directory)/'receipt.json';path.write_text('{"status":"complete"}',encoding='utf-8')
            reference=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(inventory.read(reference)['status'],'complete')
            with self.assertRaises(ValueError):inventory.read(dict(reference,sha256='b'*64))
            for filename in ('posthoc_GT_labels.json','gap_registry.json'):
                path=Path(directory)/filename;path.write_text('{}',encoding='utf-8')
                with self.assertRaises(ValueError):inventory.read(dict(path=str(path),sha256='a'*64))

    def test_clean_pool_same_fixed_normalizer_exposure_no_new_selection(self):
        pool=dict(path='pool',sha256='p');norm=dict(path='norm',sha256='n')
        exposure={str(s):dict(path='exp'+str(s),sha256='e') for s in inventory.SEEDS}
        folds={f:dict(real_pool=pool,normalizer=norm,exposures=exposure) for f in inventory.FOLDS}
        training=dict(source_config={'sha256':'source'},folds=folds)
        old8=dict(pairs_complete={'path':'receipt'},folds=deepcopy(folds));c=dict(folds=deepcopy(folds))
        receipt=dict(schema='v8_pairs_build_receipt_v1',status='complete_candidate_not_training_authorized',
            real_pool_unique_per_fold=1000,config_sha256='source',source_frames_per_fold=dict(real_train=1500,heldout=750))
        with patch.object(inventory,'read',return_value=receipt),patch.object(inventory,'data_ref'):
            actual=inventory.clean_folds(training,old8,c)
            self.assertEqual(actual['game4']['allowed_games'],['game6','game9'])
            self.assertFalse(actual['game4']['actual_pool_contents_validated'])
            self.assertIn('all1000',actual['game4']['objective'])
            c['folds']['game4']['normalizer']={'path':'new'}
            with self.assertRaises(ValueError):inventory.clean_folds(training,old8,c)

    def test_seven_receipt_binds_cache_through_protocol_not_nonexistent_cache_key(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            metric=Path(directory)/'run/metric/report.json';metric.parent.mkdir(parents=True)
            receipt=metric.parent.parent/'tracking/receipt.json'
            mot=receipt.parent/'data/X.txt';mot.parent.mkdir(parents=True);mot.write_text('unread',encoding='utf-8')
            job=dict(kind='learned',group='A',method='motion',fold='game4',seed=20261024,sequence='X')
            ref=dict(path=str(metric),sha256='a'*64);binding={'origin':'frozen_R'}
            cache=dict(path='unopened_cache',sha256='c'*64)
            protocols=dict(ABC=dict(path='protocol',sha256='b'*64),seven_sequences=['X'])
            body=dict(schema='seven_match_ABC_trackeval_gap_v1',status='complete',DO_PREPROC=False,
                predictions_GT_filtered=False,test_read=False,job=job,frames=2,protocol_sha256='b'*64,
                tracking_receipt_sha256='d'*64)
            tracked=dict(schema='seven_match_ABC_free_tracking_v1',status='complete',job=job,binding=binding,
                frames=2,frame_counts=[1,0],tracked_rows=1,protocol_sha256='b'*64,
                GT_used_for_tracking=False,evaluation_GT_annotations_loaded=False,test_read=False,mot_sha256='e'*64)
            lookup={('R','game4',20261024):dict(model_id='M',binding=binding)}
            def fake_read(reference):
                return body if reference['path']==str(metric) else tracked
            with patch.object(inventory,'read',side_effect=fake_read):
                actual=inventory.baseline_record('R',ref,job,'X',{'X':dict(frames=2,cache=cache)},protocols,lookup)
                self.assertEqual(actual['source_cache'],cache)
                self.assertEqual(actual['source_cache_binding'],'frozen_protocol_sources_not_legacy_receipt_field')
                for key,value in [('schema','unknown_schema'),('evaluation_GT_annotations_loaded',True),('frame_counts',[1])]:
                    changed=deepcopy(tracked);changed[key]=value
                    with patch.object(inventory,'read',side_effect=lambda r:body if r['path']==str(metric) else changed):
                        with self.assertRaises(ValueError):inventory.baseline_record('R',ref,job,'X',{'X':dict(frames=2,cache=cache)},protocols,lookup)

    def test18_original_loader_and_budget_refs_reject_hard_replacement(self):
        with TemporaryDirectory() as directory,patch.object(inventory,'R',Path(directory)):
            metadata={};models_R={f:{} for f in inventory.FOLDS};models_RS=deepcopy(models_R)
            exposure={f:{str(s):{'path':'historical_S_exposure','sha256':'s'} for s in inventory.SEEDS} for f in inventory.FOLDS}
            folds={f:dict(normalizer={'path':'norm','sha256':'n'},clean_R_pool={'path':'pool','sha256':'p'},
                baseR_exposures={str(s):{'path':'base','sha256':'e'} for s in inventory.SEEDS}) for f in inventory.FOLDS}
            protocol=dict(path='v10_protocol',sha256='v10');v8=dict(path='v8_protocol',sha256='v8')
            for f in inventory.FOLDS:
                for s in inventory.SEEDS:
                    common=dict(fold=f,seed=s,initialization_sha256='init'+f+str(s),R_window_UID_chain_sha256='chain'+f+str(s))
                    for regime,target in [('R',models_R),('RS',models_RS)]:
                        run=Path(directory)/regime/f/str(s)/'training';run.mkdir(parents=True)
                        receipt_ref=dict(path=str(run/'run_receipt.json'),sha256='receipt')
                        checkpoint=dict(path=str(run/('last.pt' if regime=='R' else 'checkpoints/step_1000.pt')),sha256='weight')
                        binding=dict(common,**(dict(arm='motion_R',protocol_sha256='v8',normalizer_sha256='n') if regime=='R'
                            else dict(regime='RS',method='motion',pool='balanced',protocol_sha256='v10')))
                        body=dict(schema='v8_window_training_run' if regime=='R' else 'v10_full_recorded_training_run_v1',
                            status='complete',completed_updates=1000,real_window_exposures=3000,
                            synthetic_window_exposures=0 if regime=='R' else 1000,binding=binding)
                        body['checkpoint_sha256' if regime=='R' else 'checkpoint']='weight' if regime=='R' else checkpoint
                        metadata[receipt_ref['path']]=body
                        target[f][str(s)]=dict(training_receipt=receipt_ref,checkpoint=checkpoint)
                        if regime=='RS':target[f][str(s)]['training_complete']=dict(path='complete',sha256='complete')
            training=dict(v8_protocol=v8,reference_R={'motion':models_R},exposures={'balanced':exposure})
            c=dict(source_v10_protocol=protocol,reference_R=deepcopy(training['reference_R']),reference_B={'motion':models_RS})
            with patch.object(inventory,'read',side_effect=lambda r:metadata[r['path']]),patch.object(inventory,'data_ref'),\
                    patch.object(inventory,'source_file',side_effect=lambda c,p:dict(path=p,sha256='source')):
                actual=inventory.models_from(protocol,training,{},c,folds)
                self.assertEqual(len(actual),18)
                self.assertEqual({x['loader']['function'] for x in actual},{'load_complete','complete_model'})
                self.assertTrue(all(not x['checkpoint_bytes_read'] and not x['beta0_baseline_alias_authorized'] for x in actual))
                self.assertEqual(sum(x['calibration']['extra_clean_R_window_evaluations'] for x in actual),18000)
                target=models_RS['game4']['20261024']['training_receipt']['path']
                metadata[target]['binding']['pool']='hard_enriched'
                with self.assertRaises(ValueError):inventory.models_from(protocol,training,{},c,folds)

    def test_test_scope_rejected_and_no_training_module_import(self):
        with self.assertRaises(ValueError):inventory.safe(inventory.R/'test/cache.jsonl')
        with self.assertRaises(ValueError):inventory.safe(inventory.R/'SNMOT-187/last.pt')
        for name in ('torch','numpy','ultralytics'):
            self.assertNotIn(name,inventory.__dict__)


if __name__=='__main__':unittest.main()
