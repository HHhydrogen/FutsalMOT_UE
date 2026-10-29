"""R集合终验独立六条件/双参照/完整统计、MOT、GT及退出夹具。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import verify_r_set_tracking as v
import test_verify_state_aligned_tracking as old_fixture


def records(zero=False):
    rows=[];panels=old_fixture.panels();seqs=list(v.panels_map(panels))
    for regime,seq,fold,seed in sorted(v.expected_cells(panels)):
        n=seqs.index(seq);total=0 if zero and seq=='e2' else (690 if zero and n==0 else 390 if not zero and n==0 else 300)
        oldid='old'+regime+fold+str(seed);aligned='aligned'+regime+fold+str(seed);new='new'+regime+fold+str(seed)
        for origin,mid,change in [('originalstrongmotion',oldid,0.),('alignedBCE',aligned,(n-5)*(.5 if regime=='RS' else -.2)),('newCE',new,(n-6)*(.7 if regime=='RS' else -.4))]:
            value=20+n+(regime=='RS')+change+(seed-v.SEEDS[0])*.1
            row=dict(condition=origin+'_'+regime,model_id=mid,regime=regime,sequence=seq,fold=fold,seed=seed,frames=750,
                metrics={m:value for m in v.METRICS},gap=dict(total_events=total,same_prediction_ID_recovered=10 if total else 0,recovery_rate=10/total if total else None),
                report=dict(path=origin+seq+fold+regime+str(seed)+'.json',sha256='a'*64),tracking_receipt=dict(path='receipt.json',sha256='b'*64))
            if origin=='alignedBCE':row['baseline_model_id']=oldid
            elif origin=='newCE':row.update(baseline_model_id=aligned,original_baseline_model_id=oldid)
            rows.append(row)
    return rows


class RSetTerminal(unittest.TestCase):
    def test_new_CE_loader_dual_references_method_and_original_sigmoid(self):
        model=dict(model_id='ce',baseline_model_id='aligned',original_baseline_model_id='old',fold='game4',seed=20261024,regime='R',
            training_objective=v.OBJECTIVE,training_receipt='run',expected_initialization_sha256='init')
        job={k:model[k] for k in ('model_id','baseline_model_id','original_baseline_model_id','fold','seed','regime')};job.update(job_id='job',sequence='s')
        cfg=dict(learning_protocol=dict(sha256=v.LEARNING_SHA),training_budget='budget',training_complete='complete',sources=dict(s=dict(cache='cache')))
        tr=dict(schema='r_set_tracking_receipt_v1',status='complete',job=job,model_id='ce',baseline_model_id='aligned',original_baseline_model_id='old',protocol_sha256='protocol',
            learning_protocol=cfg['learning_protocol'],training_budget='budget',source_cache='cache',prefix_frames=None,new_optimizer_updates=0,global_ID_before=0,actual_dtype='float32',
            original_input_dim=194,original_probability_cutoff=.5,scope_adapter=dict(numerical_AST_unchanged=True,modified_AST_nodes='one_frame_scope_guard_only',
                original_tracker_sha256='7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688'),GT_guard=dict(python_open_audit_installed=True,blocked_open_attempts=0,GT_annotations_opened=False),
            binding=dict(fold='game4',seed=20261024,regime='R',method='motion',R_objective='candidate_set_CE_fixed_no_match_logit_0',protocol_sha256=v.LEARNING_SHA,initialization_sha256='init'))
        for k in ('intercept_applied','calibration_metadata_read','training_labels_used_in_tracking_features','GT_used_for_tracking','evaluation_GT_coordinate_files_opened','alias_used','test_read','GPU_used'):tr[k]=False
        for k in ('original_base_forward_without_intercept_wrapper','training_R_S_label_metadata_parsed_for_checkpoint_binding','all_job_state_reset','source_inputs_unchanged',
            'original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged','native_ordered_batch_forward_preserved','input_Pose_columns_zeroed_after_original_normalization'):tr[k]=True
        loaded={k:model[k] for k in ('model_id','baseline_model_id','original_baseline_model_id','training_objective')}
        loaded.update(schema='R_candidate_set_model_loading_receipt_v1',learning_protocol=cfg['learning_protocol'],training_budget='budget',training_complete='complete',run_receipt='run',
            original_motion_forward=True,output_transform='sigmoid',probability_cutoff=.5,use_pose=False,Pose_columns_zeroed_after_normalization=170,initialization_equal_original=True,normalizer_equal_original=True,
            device='cpu',actual_dtype='float32',checkpoint='last1000_not_EMA_no_best',intercept_applied=False,new_optimizer_updates=0,test_read=False);tr['model_loading_receipt']=loaded
        v.track_boundary(tr,job,model,cfg,dict(sha256='protocol'))
        for change in (lambda r:r.update(original_baseline_model_id='wrong'),lambda r:r['model_loading_receipt'].update(output_transform='softmax'),
            lambda r:r['binding'].update(R_objective='BCE'),lambda r:r.update(training_labels_used_in_tracking_features=True)):
            bad=deepcopy(tr);change(bad)
            with self.assertRaises(ValueError):v.track_boundary(bad,job,model,cfg,dict(sha256='protocol'))

    def test_full_six_conditions_five_pairs_absolute_scores_negative_and_null(self):
        rows=records(True);cells,matches,am,ap=v.reconstruct(rows,old_fixture.panels())
        self.assertEqual(tuple(map(len,(rows,cells,matches,am,ap))),(540,450,60,72,18))
        self.assertTrue(any(c['delta_pp']['AssA']<0 for c in cells));self.assertEqual({r['condition'] for r in ap},set(v.CONDITIONS))
        self.assertTrue(all(c['delta_recovery_rate_pp'] is None for c in cells if c['sequence']=='e2'))
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel']=='original_heldout'},{3})
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel']=='seven_observed'},{9})

    def test_missing_duplicate_report_and_each_wrong_baseline_ID_rejected(self):
        rows=records()
        for key in ('baseline_model_id','original_baseline_model_id'):
            bad=deepcopy(rows);next(r for r in bad if r['condition']=='newCE_R')[key]='wrong'
            with self.assertRaises(ValueError):v.reconstruct(bad,old_fixture.panels())
        for bad in (rows[:-1],rows+[deepcopy(rows[0])]):
            with self.assertRaises(ValueError):v.reconstruct(bad,old_fixture.panels())
        bad=deepcopy(rows);bad[0]['report']=bad[1]['report']
        with self.assertRaises(ValueError):v.reconstruct(bad,old_fixture.panels())

    def test_all540_csv450_pairs75metric15gap_against_independent_fixture(self):
        import r_set_tracking_analysis as analysis
        values=records(True);groups=[[r for r in values if r['condition'].startswith(p)] for p in ('newCE_','alignedBCE_','originalstrongmotion_')]
        result=analysis.analyze_records(*groups,old_fixture.panels());cells,matches,am,ap=v.reconstruct(values,old_fixture.panels())
        self.assertEqual(cells,result['paired_cell_records']);self.assertEqual(matches,result['paired_match_records'])
        with TemporaryDirectory() as folder:
            root=Path(folder);out=root/'pose/results'
            with patch.object(analysis,'physical',side_effect=Path),patch.object(analysis,'R',root):analysis.write_analysis(result,out,protocol='fixture',sources={})
            report=json.loads((out/'report.json').read_text(encoding='utf-8'))
            with patch.object(v,'physical',side_effect=Path):self.assertEqual(v.check_csvs(report,values,cells,matches,am,ap)['all_results'],540)
            self.assertEqual(v.check_intervals(report,matches,old_fixture.panels())['metric_descriptions'],75)
            bad=deepcopy(report);bad['comparisons'][v.COMPARISONS[0]]['original_heldout']['AssA']['mean_delta_pp']+=1.
            with self.assertRaises(ValueError):v.check_intervals(bad,matches,old_fixture.panels())

    def test_original_metric_full_Count_ID0_negative_MOTA_and_no_GT_filter(self):
        body=old_fixture.metric_body();self.assertEqual(v.report_metrics(body,'s',3,5,6)['MOTA'],-10.)
        for change in (lambda b:b.update(GT_ID0_original=False),lambda b:b.update(predictions_GT_filtered=True),lambda b:b['raw_results']['s']['pedestrian']['Count'].update(Dets=4)):
            bad=deepcopy(body);change(bad)
            with self.assertRaises(ValueError):v.report_metrics(bad,'s',3,5,6)

    def test_signed_MOT_every_row_duplicate_nonfinite_and_raw_guard(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);mot=root/'tracking/data/s.txt';mot.parent.mkdir(parents=True);mot.write_text('1,1,1,2,3,4,.8,-1,-1,-1\n',encoding='utf-8')
            with patch.object(v,'physical',side_effect=Path):
                self.assertEqual(v.mot_counts(v.ref(mot),3),[1,0,0])
                mot.write_text('1,1,nan,2,3,4,.8,-1,-1,-1\n',encoding='utf-8')
                with self.assertRaises(ValueError):v.mot_counts(v.ref(mot),3)
            cache=root/'cache.jsonl';cache.write_text('{}')
            cfg=dict(sources=dict(s=dict(cache=dict(path=str(cache)))),registries={})
            with v.no_raw_reads(cfg,dict(models=[])) as guard:
                with self.assertRaises(PermissionError):cache.read_text()
            self.assertEqual(guard['blocked_open_attempts'],1)

    def test_CIM_actual_script_identity_not_reused_PID(self):
        state=dict(controller_pid=10,workers=[dict(worker_pid=11)])
        self.assertTrue(v.processes_absent([dict(ProcessId=10,Name='python.exe',CommandLine='python user_game.py')],state)['producer_processes_absent'])
        for command in ('python D:/code/r_set_tracking_control.py --execute','powershell -Command python D:/code/control_r_set_supervision_training.py --execute'):
            with self.assertRaises(ValueError):v.processes_absent([dict(ProcessId=20,Name='python.exe',CommandLine=command)],state)

    def test_protocol_separator_is_same_signed_physical_file_not_hash_only(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);p=root/'config.json';p.write_text('{}');copy=root/'copy.json';copy.write_text('{}')
            with patch.object(v,'R',root):
                ref=v.ref(p);self.assertTrue(v.same_signed_file(ref,dict(ref,path=p.as_posix())))
                self.assertFalse(v.same_signed_file(ref,v.ref(copy)))
                with self.assertRaises(ValueError):v.same_signed_file(ref,dict(ref,sha256='0'*64))


class NumericAndClosure(unittest.TestCase):
    def test_numeric_saved_payload_SHA_full_ABA_spawn_and_exit(self):
        names=('bundle','bundle_manifest','inventory','aligned_inventory','aligned_learning_protocol','aligned_tracking_manifest','aligned_tracking_protocol','aligned_analysis','source_state_aligned_runtime','learning_protocol','training_budget','training_complete','source_inventory','source_velocity_protocol',
            'source_worker_framework','original_inputs_source','sources','panels','registries','jobs','tracker_parameters','worker_profile','gate_job_ids','analysis_plan','track_guard_source','expected_GT_rows')
        cfg={k:k for k in names};cfg.update(numeric_admission='proof',source_numeric_validation='numeric_validation',jobs=[dict(job_id='A',regime='R',sequence='SNMOT-060'),
            dict(job_id='B',regime='RS',sequence='v_2QhNRucNC7E_c017')],gate_job_ids=['A','B'])
        admission={k:deepcopy(cfg[k]) for k in names};admission.update(phase='numeric_admission',numeric_authorized=True,tracking_authorized=False,numeric_output='folder')
        payload=dict(mot_text='',raw_frames=[[] for _ in range(48)],frame_counts=[0]*48,audit={},frames=48,tracked_rows=0,global_ID_before=0,new_optimizer_updates=0,
            GT_guard=dict(python_open_audit_installed=True,blocked_open_attempts=0,GT_annotations_opened=False))
        for k in ('original_base_forward_without_intercept_wrapper','all_job_state_reset','source_inputs_unchanged','original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged'):payload[k]=True
        for k in ('intercept_applied','calibration_metadata_read','GT_used_for_tracking','evaluation_GT_coordinate_files_opened','alias_used','test_read'):payload[k]=False
        comparison=dict(original_ID_MOT_exact=True,raw_native_frames_exact=True,frame_counts_exact=True,audit_exact=True,frames=48,tracked_rows=0,
            MOT_sha256=hashlib.sha256(b'').hexdigest(),raw_frames_sha256=hashlib.sha256(v.canonical(payload['raw_frames']).encode()).hexdigest())
        exits=[dict(status='closed',worker_pid=i,joined=True,process_exited=True,exit_code=0,closure=dict(status='closed',worker_pid=i,source_closure_verified=True)) for i in range(5)]
        proof=dict(source_numeric_validation='numeric_validation',status='complete_R_set_cold_ABA_two_spawn_numeric_admission',passed=True,all_workers_joined_exited=True,config='config',unique_source_frames=96,
            diagnostic_frame_consumptions=336,new_optimizer_updates=0,test_read=False,alias_used=False,intercept_applied=False,
            original_tracker_and_scoped_AST_reused=True,comparisons=[deepcopy(comparison) for _ in range(5)],exits=exits)
        data=dict(proof=proof,config=admission)
        for name in ('cold_0','cold_1','ABA_0','ABA_1','ABA_2','spawn_0','spawn_1'):data[name+'.json']=deepcopy(payload)
        def get(ref):return deepcopy(data[ref])
        with patch.object(v,'checked',return_value=Path('fixture')),patch.object(v,'read',side_effect=get),patch.object(v,'physical',side_effect=Path),patch.object(v,'ref',side_effect=lambda p:p.name):
            self.assertEqual(v.numeric_admission(cfg)['actual_payload_comparisons'],5)
            for change in (lambda d:d['ABA_2.json']['frame_counts'].__setitem__(0,1),lambda d:d['proof']['exits'][0].update(process_exited=False),
                lambda d:d['config'].update(learning_protocol='other')):
                bad=deepcopy(data);change(bad)
                with patch.object(v,'read',side_effect=lambda ref:deepcopy(bad[ref])):
                    with self.assertRaises(ValueError):v.numeric_admission(cfg)

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


if __name__=='__main__':unittest.main()
