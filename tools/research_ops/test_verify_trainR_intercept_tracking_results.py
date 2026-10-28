"""终验的独立配对、原输出计数、准入来源与退出边界；不运行真实研究任务。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import verify_trainR_intercept_tracking_results as v


def panels():
    return dict(original_heldout=list(v.OLD),old_external=['e1','e2'],seven_observed=['s'+str(i) for i in range(7)])


def records(zero=False):
    result=[];p=panels();sequences=list(v.panels_map(p))
    for regime,seq,fold,seed in sorted(v.expected_cells(p)):
        number=sequences.index(seq);base=20.+number+(regime=='RS')
        change=(number-5)*(-.2 if regime=='R' else .5)+(seed-v.SEEDS[0])*.1
        total=0 if zero and seq=='e2' else 20
        for condition,metric,success in [('calibrated_beta32',base+change,12),('historical_beta_zero_reference',base,10)]:
            result.append(dict(condition=condition,regime=regime,sequence=seq,fold=fold,seed=seed,
                model_id=regime+fold+str(seed),metrics={name:metric for name in v.METRICS},
                gap=dict(total_events=total,success=success if total else 0,rate=success/total if total else None),
                report=dict(path=condition+'/'+seq+fold+str(seed)+regime+'.json',sha256='a'*64),
                tracking_receipt=dict(path='tracking/receipt.json',sha256='b'*64),frames=750,
                source_origin='fixture',alias_used=False))
    return result


def numeric_fixture():
    cfg={name:'fixed_'+name for name in ('bundle','bundle_manifest','inventory','fit_complete','calibrations','sources','panels','registries',
        'source_velocity_protocol','runtime_source','inputs_source','track_guard_source','tracker_parameters','worker_profile','gate_job_ids')}
    jobs=[dict(job_id=regime,regime=regime,sequence=seq,fold='game4',seed=20261024) for regime,seq in [('R','SNMOT-060'),('RS','v_2QhNRucNC7E_c017')]]
    cfg.update(jobs=jobs,numeric_admission='proof')
    admission={name:cfg[name] for name in cfg if name!='numeric_admission'}
    admission.update(phase='numeric_admission',numeric_authorized=True,tracking_authorized=False)
    payload=dict(mot_text='',raw_frames=[[] for _ in range(48)],frame_counts=[0]*48,audit={'none':0},frames=48,tracked_rows=0,
        all_job_state_reset=True,global_ID_before=0,source_inputs_unchanged=True,original_model_state_unchanged=True,
        original_normalizer_unchanged=True,Torch_CPU_RNG_unchanged=True,GT_used_for_tracking=False,
        evaluation_GT_coordinate_files_opened=False,test_read=False,new_optimizer_updates=0,alias_used=False,
        GT_guard=dict(python_open_audit_installed=True,blocked_open_attempts=0,GT_annotations_opened=False))
    compare=dict(original_ID_MOT_exact=True,raw_native_frames_exact=True,frame_counts_exact=True,audit_exact=True,frames=48,tracked_rows=0,
        MOT_sha256=hashlib.sha256(b'').hexdigest(),raw_frames_sha256=hashlib.sha256(v.canonical(payload['raw_frames']).encode()).hexdigest())
    payloadrefs={kind+'_'+name:kind+'_'+name for kind in ('original_beta0','wrapper_beta0','calibrated_cold') for name in ('A','B')}
    data={name:deepcopy(payload) for name in payloadrefs}
    persistent=[]
    for i,key in enumerate(('A','B','A')):
        path='persistent'+str(i);data[path]=deepcopy(payload);persistent.append(dict(key=key,comparison=deepcopy(compare),payload=path))
    spawned=[]
    for i in range(2):
        path='spawn'+str(i);data[path]=deepcopy(payload);pid=100+i
        spawned.append(dict(payload=path,comparison=deepcopy(compare),closure=dict(status='closed',worker_pid=pid,joined=True,
            exitcode=0,actual_PID_absent_after_join=True,closure=dict(status='closed',worker_pid=pid,source_closure_verified=True))))
    proof=dict(schema='trainR_intercept_tracking_numeric_admission_v1',status='complete_trainR_intercept_cold_ABA_spawn_beta0_original_exact_numeric_admission',
        passed=True,fit_complete=cfg['fit_complete'],all_workers_joined_exited=True,unique_source_frames=96,diagnostic_frame_consumptions=528,
        numeric_threads=1,new_optimizer_updates=0,new_TrackEval_runs=0,test_read=False,alias_used=False,nearzero_alias_threshold=None,
        evaluation_GT_coordinate_files_opened=False,new_detector_or_Pose_inference=False,config='admission',cases=dict(A=jobs[0],B=jobs[1]),original_beta0_prefix_runs=2,
        wrapper_beta0_prefix_runs=2,calibrated_cold_prefix_runs=2,persistent_prefix_runs=3,independent_spawn_prefix_runs=2,
        cold_payloads=payloadrefs,beta0_original_comparisons=dict(A=deepcopy(compare),B=deepcopy(compare)),persistent_ABA=persistent,
        independent_spawn_A=spawned,parent_closure=dict(status='closed',jobs=9,source_closure_verified=True))
    data.update(proof=proof,admission=admission)
    return cfg,data


def metric_body():
    fractions=dict(AssA=.2,HOTA=.3,DetA=.4,IDF1=.5,MOTA=-.1)
    raw={};summary={}
    for name in ('s','COMBINED_SEQ'):
        count=dict(Dets=5,GT_Dets=6)
        if name=='s':count['Frames']=3
        raw[name]=dict(pedestrian=dict(Count=count,HOTA={key:[value]*19 for key,value in fractions.items() if key in ('AssA','HOTA','DetA')},
            Identity=dict(IDF1=fractions['IDF1']),CLEAR=dict(MOTA=fractions['MOTA'])))
        summary[name]=dict(metrics_percent={key:value*100 for key,value in fractions.items()})
    return dict(frames=3,GT_rows=6,status='complete',DO_PREPROC=False,predictions_GT_filtered=False,
        GT_used_only_for_metric=True,test_read=False,GT_ID0_original=True,raw_results=raw,summary=summary,
        metrics=summary['s']['metrics_percent'])


def interval_stub(values,**kwargs):
    return dict(n_independent_matches=len(values),mean_delta_pp=mean(values.values()),match_deltas_pp=values,
        Student_t_95CI=[-1.,1.],percentile_match_bootstrap_95CI=[-1.,1.],leave_one_match_out_mean={s:mean(x for k,x in values.items() if k!=s) for s in values},
        formal_equivalence_or_noninferiority_test=False,margin=None)


class Terminal(unittest.TestCase):
    def test_independent_full_pairing_negative_and_interaction(self):
        values=records();cells,matches=v.reconstruct(values,panels())
        self.assertEqual((len(cells),len(matches)),(270,36))
        selected={r['comparison']:r for r in cells if r['sequence']=='s6' and r['fold']=='game4' and r['seed']==20261024}
        self.assertAlmostEqual(selected[v.COMPARISONS[2]]['delta_pp']['AssA'],selected[v.COMPARISONS[1]]['delta_pp']['AssA']-selected[v.COMPARISONS[0]]['delta_pp']['AssA'])
        self.assertTrue(any(r['delta_pp']['AssA']<0 for r in cells))
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel']=='original_heldout'},{3})
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel']=='seven_observed'},{9})

    def test_missing_or_duplicate_and_wrong_model_pair_rejected(self):
        values=records()
        for bad in (values[:-1],values+[deepcopy(values[0])]):
            with self.assertRaises(ValueError):v.reconstruct(bad,panels())
        bad=deepcopy(values);bad[0]['model_id']='wrong'
        with self.assertRaises(ValueError):v.reconstruct(bad,panels())

    def test_zero_registered_gap_keeps_null_and_denominator(self):
        cells,matches=v.reconstruct(records(zero=True),panels())
        self.assertTrue(all(r['gap']['delta_recovery_rate_pp'] is None for r in cells if r['sequence']=='e2'))
        self.assertTrue(all(r['delta_recovery_rate_pp'] is None for r in matches if r['sequence']=='e2'))
        self.assertEqual(v.gap_values(dict(total_events=0,same_prediction_ID_recovered=0,recovery_rate=None),0)['rate'],None)
        with self.assertRaises(ValueError):v.gap_values(dict(total_events=0,same_prediction_ID_recovered=0,recovery_rate=0.),0)

    def test_metric_actual_Count_ID0_combined_without_Frames_and_negative_MOTA(self):
        body=metric_body();out=v.report_metrics(body,'s',3,5,6)
        self.assertEqual(out['MOTA'],-10.)
        for patcher in (lambda b:b['raw_results']['s']['pedestrian']['Count'].update(Dets=4),
            lambda b:b.update(GT_ID0_original=False),lambda b:b.update(predictions_GT_filtered=True)):
            bad=deepcopy(body);patcher(bad)
            with self.assertRaises(ValueError):v.report_metrics(bad,'s',3,5,6)

    def test_signed_all_MOT_rows_and_no_silent_duplicate_or_nonfinite(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'tracking/data/s.txt';path.parent.mkdir(parents=True)
            path.write_text('1,1,1.5,2.5,3.5,4.5,1,-1,-1,-1\n3,2,2,3,4,5,.8,-1,-1,-1\n',encoding='utf-8')
            with patch.object(v,'physical',side_effect=lambda p:Path(p)):
                reference=v.ref(path);self.assertEqual(v.mot_counts(reference,3),[1,0,1])
                for text in ('1,1,1,2,3,4,1,-1,-1,-1\n1,1,1,2,3,4,1,-1,-1,-1\n','1,1,nan,2,3,4,1,-1,-1,-1\n'):
                    path.write_text(text,encoding='utf-8')
                    with self.assertRaises(ValueError):v.mot_counts(v.ref(path),3)

    def test_full_saved_numeric_payload_bindings_and_join_not_only_pass_flag(self):
        cfg,data=numeric_fixture()
        with patch.object(v,'read',side_effect=lambda key:deepcopy(data[key])):
            self.assertEqual(v.numeric_admission(cfg)['full_saved_payload_comparisons'],7)
        for mutate in (lambda d:d['admission'].update(inputs_source='changed'),
            lambda d:d['wrapper_beta0_A']['frame_counts'].__setitem__(0,1),
            lambda d:d['proof']['independent_spawn_A'][0]['closure'].update(exitcode=1)):
            bad=deepcopy(data);mutate(bad)
            with patch.object(v,'read',side_effect=lambda key:deepcopy(bad[key])):
                with self.assertRaises(ValueError):v.numeric_admission(cfg)

    def test_process_gate_exact_script_and_no_PID_only_false_positive(self):
        state=dict(parent_pid=10,workers=[dict(worker_pid=11)])
        rows=[dict(ProcessId=10,ParentProcessId=1,Name='python.exe',CommandLine='python user_game.py'),
            dict(ProcessId=12,Name='python.exe',CommandLine='python verify_trainR_intercept_tracking_results.py')]
        self.assertTrue(v.processes_absent(rows,state)['producer_processes_absent'])
        self.assertEqual(len(v.processes_absent(rows,state)['historical_PIDs_currently_present_with_different_named_identity']),1)
        for command in ('python D:/code/trainR_intercept_tracking_control.py --execute',
            'powershell -File D:/code/trainR_intercept_fit_control.py --execute'):
            with self.assertRaises(ValueError):v.processes_absent([dict(Name='python.exe',CommandLine=command)],state)

    def test_two_track_one_metric_actual_close_join_and_all_jobs_required(self):
        sources={s:{} for s in v.panels_map(panels())}
        ready=[dict(worker_pid=pid,kind=kind) for pid,kind in ((101,'track'),(102,'track'),(103,'metric'))]
        state=dict(workers=ready,completed_tracking=[dict(worker_pid=pid) for pid in (101,102) for _ in range(90)],
            completed_metrics=[dict(worker_pid=103) for _ in range(180)],actual_exit_gate=dict(actual_CIM_checked=True,related_producers_absent=True))
        exits=[]
        for entry in ready:
            pid=entry['worker_pid'];kind=entry['kind'];jobs=90 if kind=='track' else 180
            closure=dict(status='closed',worker_pid=pid,jobs=jobs,source_closure_verified=True)
            if kind=='track':closure.update(GT_guard=dict(python_open_audit_installed=True,blocked_open_attempts=0,GT_annotations_opened=False),evaluation_GT_coordinate_files_opened=False)
            else:closure.update(GT_isolated_to_metric_worker=True,GT_sequences_loaded=list(sources))
            exits.append(dict(**entry,status='closed',joined=True,process_exited=True,exit_code=0,jobs=jobs,closure=closure))
        state['worker_exits']=exits;manifest=dict(worker_exits=exits)
        with patch.object(v,'ref',side_effect=lambda p:dict(path=str(p),sha256='a'*64)):
            self.assertEqual(v.check_workers(state,manifest,Path('fixture'),dict(sources=sources))['actual_workers_joined_exit0'],3)
            for mutate in (lambda s:s['worker_exits'][0].update(exit_code=1),
                lambda s:s['worker_exits'][0]['closure']['GT_guard'].update(GT_annotations_opened=True),
                lambda s:s['worker_exits'][2]['closure'].update(GT_sequences_loaded=list(sources)[:-1])):
                bad=deepcopy(state);mutate(bad)
                with self.assertRaises(ValueError):v.check_workers(bad,dict(worker_exits=bad['worker_exits']),Path('fixture'),dict(sources=sources))

    def test_CSV_negative_zero_null_and_duplicates_checked_by_identity(self):
        expected=[dict(id='a',delta=-.25,unknown=None,flag=False),dict(id='b',delta=0.,unknown=None,flag=True)]
        rows=[dict(id='a',delta='-.25',unknown='',flag='False'),dict(id='b',delta='0.0',unknown='',flag='True')]
        v.compare_csv(rows,expected,['id'])
        for bad in (rows+[rows[0]],rows[:-1],[dict(rows[0],delta='.25'),rows[1]],[dict(rows[0],unknown='0'),rows[1]]):
            with self.assertRaises(ValueError):v.compare_csv(bad,expected,['id'])

    def test_t_and_bootstrap_descriptions_use3_2_7_not90_and_no_margin(self):
        _,matches=v.reconstruct(records(zero=True),panels());report=dict(comparisons={},gap_comparisons={})
        for name in v.COMPARISONS:
            report['comparisons'][name]={};report['gap_comparisons'][name]={}
            for panel in v.PANELS:
                rows=[r for r in matches if r['comparison']==name and r['panel']==panel]
                report['comparisons'][name][panel]={metric:interval_stub({r['sequence']:r['delta_pp'][metric] for r in rows}) for metric in v.METRICS}
                values={r['sequence']:r['delta_recovery_rate_pp'] for r in rows if r['delta_recovery_rate_pp'] is not None}
                if len(values)>=2:gap=interval_stub(values)
                else:gap=dict(n_independent_matches=len(values),match_deltas_pp=values,mean_delta_pp=mean(values.values()) if values else None,
                    Student_t_95CI=None,percentile_match_bootstrap_95CI=None,leave_one_match_out_mean=None,
                    formal_equivalence_or_noninferiority_test=False,margin=None,status='fewer_than_two_matches_with_registered_events_no_interval')
                gap.update(zero_event_matches_retained_null=[r['sequence'] for r in rows if r['delta_recovery_rate_pp'] is None],
                    outcome='all_registered_trusted_detection_gap_proxy_not_physical_occlusion')
                report['gap_comparisons'][name][panel]=gap
        self.assertEqual(v.check_intervals(report,matches,panels(),interval_stub)['metric_descriptions'],45)
        for field,value in (('n_independent_matches',90),('margin',.5),('formal_equivalence_or_noninferiority_test',True)):
            bad=deepcopy(report);bad['comparisons'][v.COMPARISONS[0]]['seven_observed']['AssA'][field]=value
            with self.assertRaises(ValueError):v.check_intervals(bad,matches,panels(),interval_stub)

    def test_raw_input_guard_blocks_weights_and_original_cache_only_while_enabled(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'weights.pt';path.write_text('fixture',encoding='utf-8')
            with v.no_raw_reads(dict(sources={'a':dict(cache=dict(path=str(path)))},registries={}),dict(models=[])) as proof:
                with self.assertRaises(PermissionError):path.read_bytes()
                self.assertEqual(proof['blocked_open_attempts'],1)
            self.assertEqual(path.read_text(encoding='utf-8'),'fixture')


if __name__=='__main__':unittest.main()
