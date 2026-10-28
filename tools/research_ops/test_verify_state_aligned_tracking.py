"""独立终验的来源、计数、负项、null、四差分及退出合同；仅内存/临时夹具。"""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import verify_state_aligned_tracking as v


def panels():
    return dict(original_heldout=list(v.OLD),old_external=['e1','e2'],seven_observed=['s'+str(i) for i in range(7)])


def records(zero=False):
    rows=[];names=list(v.panels_map(panels()))
    for regime,seq,fold,seed in sorted(v.expected_cells(panels())):
        n=names.index(seq);base=20+n+(regime=='RS');change=(n-5)*(-.2 if regime=='R' else .5)+(seed-v.SEEDS[0])*.1
        total=0 if zero and seq=='e2' else 20
        oldid=regime+fold+str(seed);newid='new'+oldid
        for origin,value,success in [('old',base,10),('new',base+change,12)]:
            item=dict(condition=origin+'_'+regime,regime=regime,sequence=seq,fold=fold,seed=seed,model_id=newid if origin=='new' else oldid,
                metrics={m:value for m in v.METRICS},gap=dict(total_events=total,same_prediction_ID_recovered=success if total else 0,
                    recovery_rate=success/total if total else None),frames=750,source_origin='new_actual_tracking' if origin=='new' else 'historical_readonly',
                report=dict(path=origin+seq+fold+str(seed)+regime+'.json',sha256='a'*64),tracking_receipt=dict(path='receipt.json',sha256='b'*64))
            if origin=='new':item['baseline_model_id']=oldid
            rows.append(item)
    return rows


def metric_body():
    fractions=dict(AssA=.2,HOTA=.3,DetA=.4,IDF1=.5,MOTA=-.1);raw={};summary={}
    for seq in ('s','COMBINED_SEQ'):
        count=dict(Dets=5,GT_Dets=6)
        if seq=='s':count['Frames']=3
        raw[seq]=dict(pedestrian=dict(Count=count,HOTA={k:[fractions[k]]*19 for k in ('AssA','HOTA','DetA')},
            Identity=dict(IDF1=fractions['IDF1']),CLEAR=dict(MOTA=fractions['MOTA'])))
        summary[seq]=dict(metrics_percent={k:100*n for k,n in fractions.items()})
    return dict(frames=3,GT_rows=6,status='complete',DO_PREPROC=False,predictions_GT_filtered=False,GT_used_only_for_metric=True,
        test_read=False,GT_ID0_original=True,raw_results=raw,summary=summary,metrics=summary['s']['metrics_percent'])


class IndependentVerifier(unittest.TestCase):
    def test_numeric_saved_payload_SHA_full_ABA_spawn_and_exit(self):
        names=('bundle','bundle_manifest','inventory','learning_protocol','training_budget','training_complete','source_inventory','source_velocity_protocol',
            'source_worker_framework','original_inputs_source','sources','panels','registries','jobs','tracker_parameters','worker_profile','gate_job_ids','analysis_plan','track_guard_source','expected_GT_rows')
        cfg={k:k for k in names};cfg.update(numeric_admission='proof',jobs=[dict(job_id='A',regime='R',sequence='SNMOT-060'),
            dict(job_id='B',regime='RS',sequence='v_2QhNRucNC7E_c017')],gate_job_ids=['A','B'])
        admission={k:deepcopy(cfg[k]) for k in names};admission.update(phase='numeric_admission',numeric_authorized=True,tracking_authorized=False,numeric_output='folder')
        payload=dict(mot_text='',raw_frames=[[] for _ in range(48)],frame_counts=[0]*48,audit={},frames=48,tracked_rows=0,global_ID_before=0,new_optimizer_updates=0,
            GT_guard=dict(python_open_audit_installed=True,blocked_open_attempts=0,GT_annotations_opened=False))
        for k in ('original_base_forward_without_intercept_wrapper','all_job_state_reset','source_inputs_unchanged','original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged'):payload[k]=True
        for k in ('intercept_applied','calibration_metadata_read','GT_used_for_tracking','evaluation_GT_coordinate_files_opened','alias_used','test_read'):payload[k]=False
        comparison=dict(original_ID_MOT_exact=True,raw_native_frames_exact=True,frame_counts_exact=True,audit_exact=True,frames=48,tracked_rows=0,
            MOT_sha256=hashlib.sha256(b'').hexdigest(),raw_frames_sha256=hashlib.sha256(v.canonical(payload['raw_frames']).encode()).hexdigest())
        exits=[dict(status='closed',worker_pid=i,joined=True,process_exited=True,exit_code=0,closure=dict(status='closed',worker_pid=i,source_closure_verified=True)) for i in range(5)]
        proof=dict(status='complete_state_aligned_cold_ABA_two_spawn_numeric_admission',passed=True,all_workers_joined_exited=True,config='config',unique_source_frames=96,
            diagnostic_frame_consumptions=336,new_optimizer_updates=0,test_read=False,alias_used=False,intercept_applied=False,
            original_tracker_and_scoped_AST_reused=True,comparisons=[deepcopy(comparison) for _ in range(5)],exits=exits)
        data=dict(proof=proof,config=admission)
        for name in ('cold_0','cold_1','ABA_0','ABA_1','ABA_2','spawn_0','spawn_1'):data[name+'.json']=deepcopy(payload)
        def get(ref):return deepcopy(data[ref])
        with patch.object(v,'read',side_effect=get),patch.object(v,'physical',side_effect=Path),patch.object(v,'ref',side_effect=lambda p:p.name):
            self.assertEqual(v.numeric_admission(cfg)['actual_payload_comparisons'],5)
            for change in (lambda d:d['ABA_2.json']['frame_counts'].__setitem__(0,1),lambda d:d['proof']['exits'][0].update(process_exited=False),
                lambda d:d['config'].update(learning_protocol='other')):
                bad=deepcopy(data);change(bad)
                with patch.object(v,'read',side_effect=lambda ref:deepcopy(bad[ref])):
                    with self.assertRaises(ValueError):v.numeric_admission(cfg)

    def test_new_loader_identity_no_intercept_or_label_features(self):
        model=dict(model_id='new',baseline_model_id='old',fold='game4',seed=20261024,regime='R',method_schema='state_aligned_strongmotion_method_state_v1',
            training_receipt='run',expected_initialization_sha256='i')
        job={k:model[k] for k in ('model_id','baseline_model_id','fold','seed','regime')};job.update(sequence='s',job_id='j')
        cfg=dict(learning_protocol='learn',training_budget='budget',sources=dict(s=dict(cache='cache')))
        tr=dict(schema='state_aligned_tracking_receipt_v1',status='complete',job=job,model_id='new',baseline_model_id='old',protocol_sha256='p',
            learning_protocol='learn',training_budget='budget',source_cache='cache',prefix_frames=None,global_ID_before=0,actual_dtype='float32',original_input_dim=194,
            original_probability_cutoff=.5,new_optimizer_updates=0,scope_adapter=dict(numerical_AST_unchanged=True,modified_AST_nodes='one_frame_scope_guard_only',
                original_tracker_sha256='7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688'),
            GT_guard=dict(python_open_audit_installed=True,blocked_open_attempts=0,GT_annotations_opened=False),
            binding=dict(fold='game4',seed=20261024,regime='R',method='motion',initialization_sha256='i'))
        for k in ('intercept_applied','calibration_metadata_read','training_labels_used_in_tracking_features','GT_used_for_tracking',
            'evaluation_GT_coordinate_files_opened','alias_used','test_read','GPU_used'):tr[k]=False
        for k in ('original_base_forward_without_intercept_wrapper','training_R_S_label_metadata_parsed_for_checkpoint_binding','all_job_state_reset','source_inputs_unchanged',
            'original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged','native_ordered_batch_forward_preserved','input_Pose_columns_zeroed_after_original_normalization'):tr[k]=True
        tr['model_loading_receipt']=dict(schema='state_aligned_model_loading_receipt_v1',model_id='new',baseline_model_id='old',method_schema=model['method_schema'],
            learning_protocol='learn',training_budget='budget',run_receipt='run',initialization_equal_original=True,normalizer_equal_original=True,
            checkpoint='last1000_not_EMA_no_best',device='cpu',actual_dtype='float32',use_pose=False,Pose_columns_zeroed_after_normalization=170,
            intercept_applied=False,new_optimizer_updates=0,test_read=False)
        v.track_boundary(tr,job,model,cfg,dict(sha256='p'))
        for change in (lambda b:b.update(beta32=0.),lambda b:b.update(training_labels_used_in_tracking_features=True),
            lambda b:b['model_loading_receipt'].update(checkpoint='best'),lambda b:b['scope_adapter'].update(numerical_AST_unchanged=False)):
            bad=deepcopy(tr);change(bad)
            with self.assertRaises(ValueError):v.track_boundary(bad,job,model,cfg,dict(sha256='p'))

    def test_worker_closure_counts_GT_isolation_and_actual_join(self):
        cfg=dict(jobs=[dict(job_id=str(i)) for i in range(180)],sources=dict(s={}))
        ready=[dict(worker_pid=p,kind=k) for p,k in ((10,'track'),(11,'track'),(12,'metric'))]
        state=dict(workers=ready,completed_track={},completed_metric={},worker_exits=[]);data={}
        for i in range(180):
            state['completed_track'][str(i)]=dict(receipt='t'+str(i));state['completed_metric'][str(i)]=dict(report='m'+str(i))
            data['t'+str(i)]=dict(worker_pid=10+i%2);data['m'+str(i)]=dict(worker_pid=12)
        for entry in ready:
            pid=entry['worker_pid'];inside=dict(status='closed',worker_pid=pid,jobs=180 if pid==12 else 90,source_closure_verified=True)
            if pid==12:inside.update(GT_isolated_to_metric_worker=True,GT_sequences_loaded=['s'],registry_count=2)
            else:inside.update(GT_guard=dict(python_open_audit_installed=True,blocked_open_attempts=0,GT_annotations_opened=False),
                evaluation_GT_coordinate_files_opened=False,intercept_applied=False,calibration_metadata_read=False,training_labels_used_in_tracking_features=False)
            state['worker_exits'].append(dict(status='closed',worker_pid=pid,closure=inside,joined=True,process_exited=True,exit_code=0))
        with patch.object(v,'read',side_effect=lambda ref:deepcopy(data[ref])):
            self.assertEqual(v.check_workers(state,dict(worker_exits=state['worker_exits']),cfg,[])['actual_workers_joined_exit0'],3)
            for change in (lambda s:s['worker_exits'][0].update(exit_code=1),lambda s:s['worker_exits'][2]['closure'].update(GT_sequences_loaded=[]),
                lambda s:s['worker_exits'][0]['closure']['GT_guard'].update(GT_annotations_opened=True)):
                bad=deepcopy(state);change(bad)
                with self.assertRaises(ValueError):v.check_workers(bad,dict(worker_exits=bad['worker_exits']),cfg,[])

    def test_four_pairs_and_absolute_results_from_original_values(self):
        values=records();cells,matches,absm,absp=v.reconstruct(values,panels())
        self.assertEqual(tuple(map(len,(cells,matches,absm,absp))),(360,48,48,12))
        chosen={r['comparison']:r for r in cells if (r['sequence'],r['fold'],r['seed'])==('s6','game4',20261024)}
        self.assertAlmostEqual(chosen[v.COMPARISONS[3]]['delta_pp']['AssA'],chosen[v.COMPARISONS[0]]['delta_pp']['AssA']-chosen[v.COMPARISONS[1]]['delta_pp']['AssA'])
        self.assertTrue(any(r['delta_pp']['AssA']<0 for r in cells))
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel']=='original_heldout'},{3})
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel']=='seven_observed'},{9})
        # 绝对成绩直接来自原行；不能把交互项伪装成第五个模型。
        self.assertEqual({r['condition'] for r in absp},set(v.CONDITIONS))

    def test_reject_missing_duplicate_wrong_pair_nonfinite(self):
        rows=records()
        wrong=deepcopy(rows);next(r for r in wrong if r['condition']=='new_R')['baseline_model_id']='wrong'
        nan=deepcopy(rows);nan[0]['metrics']['MOTA']=float('nan')
        for bad in (rows[:-1],rows+[deepcopy(rows[0])],wrong,nan):
            with self.assertRaises(ValueError):v.reconstruct(bad,panels())

    def test_zero_event_null_not_fabricated_zero_and_keep_full_panel(self):
        cells,matches,_,_=v.reconstruct(records(True),panels())
        self.assertTrue(all(c['delta_recovery_rate_pp'] is None for c in cells if c['sequence']=='e2'))
        out=v.interval({'e1':1.,'e2':None})
        self.assertIsNone(out['Student_t_95CI']);self.assertIsNone(out['percentile_match_bootstrap_95CI']);self.assertEqual(out['null_matches'],['e2'])
        with self.assertRaises(ValueError):v.gap_values(dict(total_events=0,same_prediction_ID_recovered=0,recovery_rate=0),0)

    def test_t_df_fixed_bootstrap_and_leave_one_match_out(self):
        out=v.interval({'a':-2.,'b':0.,'c':2.})
        self.assertAlmostEqual(out['Student_t_95CI'][1],4.302652729749462*2/(3**.5))
        self.assertEqual(out['Student_t_degrees_of_freedom'],2)
        self.assertEqual(out['leave_one_match_out_mean'],dict(a=1.,b=0.,c=-1.))
        self.assertEqual(out['bootstrap_seed'],20261028);self.assertIsNone(out['margin'])
        self.assertEqual(out,v.interval({'a':-2.,'b':0.,'c':2.}))

    def test_metric_counts_negative_MOTA_ID0_all_predictions(self):
        body=metric_body();self.assertEqual(v.report_metrics(body,'s',3,5,6)['MOTA'],-10.)
        for change in (lambda r:r.update(GT_ID0_original=False),lambda r:r.update(predictions_GT_filtered=True),
            lambda r:r['raw_results']['s']['pedestrian']['Count'].update(Dets=4)):
            bad=deepcopy(body);change(bad)
            with self.assertRaises(ValueError):v.report_metrics(bad,'s',3,5,6)

    def test_MOT_signed_full_rows_and_duplicate_nonfinite_rejected(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'tracking/data/s.txt';path.parent.mkdir(parents=True)
            with patch.object(v,'physical',side_effect=lambda p:Path(p)):
                path.write_text('1,1,1,2,3,4,.8,-1,-1,-1\n3,2,1,2,3,4,.8,-1,-1,-1\n',encoding='utf-8')
                self.assertEqual(v.mot_counts(v.ref(path),3),[1,0,1])
                for text in ('1,1,1,2,3,4,1,-1,-1,-1\n1,1,1,2,3,4,1,-1,-1,-1\n','1,1,nan,2,3,4,1,-1,-1,-1\n'):
                    path.write_text(text,encoding='utf-8')
                    with self.assertRaises(ValueError):v.mot_counts(v.ref(path),3)

    def test_csv_identity_negative_zero_null_and_tampering(self):
        expected=[dict(id='a',number=-.5,missing=None),dict(id='b',number=0.,missing=None)]
        rows=[dict(id='a',number='-.5',missing=''),dict(id='b',number='0.0',missing='')]
        v.compare_csv(rows,expected,['id'])
        for bad in (rows[:-1],rows+[rows[0]],[dict(rows[0],number='.5'),rows[1]],[dict(rows[0],missing='0'),rows[1]]):
            with self.assertRaises(ValueError):v.compare_csv(bad,expected,['id'])

    def test_CIM_exact_identity_not_historical_PID(self):
        state=dict(controller_pid=10,workers=[dict(worker_pid=11)])
        rows=[dict(ProcessId=10,ParentProcessId=1,Name='python.exe',CommandLine='python user_game.py'),
            dict(ProcessId=12,Name='python.exe',CommandLine='python verify_state_aligned_tracking.py --execute')]
        self.assertTrue(v.processes_absent(rows,state)['producer_processes_absent'])
        self.assertEqual(len(v.processes_absent(rows,state)['historical_PIDs_present_with_different_named_identity']),1)
        with self.assertRaises(ValueError):v.processes_absent([dict(ProcessId=9,Name='python.exe',CommandLine='python D:/x/state_aligned_tracking_control.py --execute')],state)

    def test_raw_open_guard_actually_blocks_even_json_registry(self):
        with TemporaryDirectory() as folder:
            cache=Path(folder)/'input.jsonl';registry=Path(folder)/'events.json';cache.write_text('{}');registry.write_text('{}')
            cfg=dict(sources=dict(s=dict(cache=dict(path=str(cache)))),registries=dict(old_five=dict(registry=dict(path=str(registry)))))
            with v.no_raw_reads(cfg,dict(models=[])) as evidence:
                for p in (cache,registry):
                    with self.assertRaises(PermissionError):p.read_text()
            self.assertEqual(evidence['blocked_open_attempts'],2)

    def test_independent_reconstruction_matches_analysis_fixture_only(self):
        import state_aligned_tracking_analysis as a
        values=records(True);target=[r for r in values if r['condition'].startswith('new_')];baseline=[r for r in values if r['condition'].startswith('old_')]
        cells,matches,absm,absp=v.reconstruct(values,panels())
        self.assertEqual(cells,a.paired_cells(target,baseline,panels()))
        self.assertEqual(matches,a.paired_matches(cells,panels()))
        self.assertEqual((absm,absp),a.absolute_results(target,baseline,panels()))
        for vals in ({'a':-2.,'b':3.},{'a':0.,'b':2.,'c':-1.},{'a':0.,'b':None}):self.assertEqual(v.interval(vals),a.effect_intervals(vals))

    def test_all_six_CSVs_and72_intervals_real_temporary_fixture(self):
        import state_aligned_tracking_analysis as a
        rows=records(True);target=[r for r in rows if r['condition'].startswith('new_')];baseline=[r for r in rows if r['condition'].startswith('old_')]
        cfg=dict(panels=panels(),inventory='inventory',source_inventory='source',training_complete='root',training_budget='budget')
        with TemporaryDirectory() as folder:
            root=Path(folder);output=root/'analysis';control=root/'control'
            with patch.object(a,'EXP',root),patch.object(a,'physical',side_effect=Path),\
                patch.object(a,'validate_config',return_value=('protocol',cfg,None,None,None,None,None)),\
                patch.object(a,'baseline_records',return_value=baseline),patch.object(a,'target_records',return_value=(target,'manifest')):
                a.analyze(root/'config.json',control,output)
            report=json.loads((output/'report.json').read_text(encoding='utf-8'));cells,matches,absm,absp=v.reconstruct(rows,panels())
            with patch.object(v,'physical',side_effect=Path):
                self.assertEqual(v.check_csvs(report,rows,cells,matches,absm,absp)['all_results'],360)
            self.assertEqual(v.check_intervals(report,matches,panels())['metric_descriptions'],60)
            bad=deepcopy(report);bad['comparisons'][v.COMPARISONS[0]]['original_heldout']['AssA']['mean_delta_pp']+=1.
            with self.assertRaises(ValueError):v.check_intervals(bad,matches,panels())


if __name__=='__main__':unittest.main()
