"""机会核查终验的独立结构/全分母/未知/源等权统计及进程身份夹具。"""
from copy import deepcopy
import gzip
import json
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import verify_decision_opportunity as v


def job(fold='game6',regime='R',sequence='SNMOT-060'):
    return dict(job_id=fold+regime+sequence,fold=fold,regime=regime,sequence=sequence,seed=20261024)


def row():
    flags={k:False for k in v.FLAGS};flags.update(actual_unmatched=True,pose_gap_unknown=True,earliest_stage_trusted3_anchor_drift=None)
    hist={g:{k:0 for k in v.HISTOGRAM_KEYS} for g in v.GROUPS};hist['unknown']['history_missing']=1
    candidate=dict(uid='candidate',label=None,label_group='unknown',current_body_valid=8,history_last_body_valid=None,
        shared_body_joints=None,history_each_shared_body_joints=[],shared_body_ge6=None,structural_support_with_gap=False,enabled=False,reference_cost=1.)
    return dict(job=job(),frame_number=1,stage='high_score',row_index=0,track_id=1,first_stop='history_not_trusted_three',flags=flags,
        threshold=.8,local_cost_comparison_is_causal=False,Pose_support_is_accuracy=False,new_solver_calls=0,history_UIDs=[],actual_observation_gap_frames=None,
        pose_candidates=[candidate],pose_shared_body_histograms=hist,raw_correct_other_stage_appearances={},raw_correct_other_stage_other_track_assignments={},
        absolute_counts=dict(rows=1,candidates=1,positive=0,known_negative=0,unknown=1,correct_raw=0),selected_column=None,selected_UID=None,
        query_GT_id=None,earliest_stage_trusted3_anchor=None)


def twelve_counts():
    result=[]
    for sequence,heldout in v.SOURCE_FOLDS.items():
        for fold in v.FOLDS:
            if fold==heldout:continue
            for regime in v.REGIMES:
                j=job(fold,regime,sequence);n=100 if fold=='game4' else 300
                flags={k:dict(true=n//4,false=n-n//4,null=0) for k in v.FLAGS}
                flags['earliest_stage_trusted3_anchor_drift']=dict(true=0,false=0,null=n)
                stops={k:0 for k in v.STOPS};stops['history_not_trusted_three']=n
                result.append(dict(job=j,row_count=n,first_stop=stops,flags=flags))
    return result


class IndependentOpportunityVerifier(unittest.TestCase):
    def test_sparse_counter_only_proven_zero_may_be_omitted(self):
        full={k:0 for k in v.STOPS};full['history_not_trusted_three']=100
        self.assertEqual(v.normalized_stops(dict(history_not_trusted_three=100),full),full)
        for bad in ({},{'history_not_trusted_three':99},{'history_not_trusted_three':100,'extra':0},
            {'history_not_trusted_three':100,'actual_correct':1},{'history_not_trusted_three':100.,'actual_correct':0}):
            with self.assertRaises(ValueError):v.normalized_stops(bad,full)

    def test_actual_two_formal_workers_plus_one_inherited_join_exit(self):
        records=[dict(job=dict(job_id='inherit'),worker_pid=9),dict(job=dict(job_id='new1'),worker_pid=10),dict(job=dict(job_id='new2'),worker_pid=11)]
        exits=[dict(worker_pid=p,joined=True,process_exited=True,exit_code=0) for p in (10,11)]
        state=dict(worker_pids=[10,11],worker_exits=exits);admission=dict(worker_exits=[dict(worker_pid=9,joined=True,process_exited=True,exit_code=0)])
        self.assertTrue(v.worker_closure(state,admission,records,'inherit')['all_three_workers_joined_exit0'])
        for change in (lambda s:s['worker_exits'][0].update(exit_code=1),lambda s:s['worker_exits'][1].update(process_exited=False),lambda s:s.update(worker_pids=[9,10,11])):
            bad=deepcopy(state);change(bad)
            with self.assertRaises(ValueError):v.worker_closure(bad,admission,records,'inherit')

    def test_unit_inherits_admission_protocol_physical_path_no_raw_log_read(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);unitdir=root/'admission/units/j';unitdir.mkdir(parents=True);path=unitdir/'rows.jsonl.gz'
            with gzip.open(path,'wt',encoding='utf-8') as sink:sink.write(json.dumps(row())+'\n')
            proto=root/'admission_config.json';proto.write_text('{}',encoding='utf-8');formal=root/'formal_config.json';formal.write_text('{"phase":"formal"}',encoding='utf-8')
            with patch.object(v,'R',root),patch.object(v,'EXP',root):
                ledger=dict(v.ref(path),rows=1);observed=dict(job=job(),frames=750,frames_log='original_frames_forbidden')
                annotation=dict(job=job(),total_frames=750,observe='observe',new_solver_calls=0,all_rows=dict(path='original_rows_forbidden',rows=1))
                actual=v.audit_rows(iter([row()]),job(),1);body=dict(schema='decision_opportunity_unit_v1',status='complete',job=job(),protocol=v.ref(proto),
                    observe='observe',posthoc='posthoc',frames=750,stages=2250,source_frames=observed['frames_log'],source_rows=annotation['all_rows'],ledger=ledger,worker_pid=9,test_read=False,
                    **{k:actual[k] for k in ('row_count','first_stop','flags','absolute_counts','pose_shared_body_histograms','anchor_count')},**{k:0 for k in v.ZERO_KEYS})
                data=dict(receipt=body,observe=observed,posthoc=annotation);u=dict(job=job(),observe='observe',posthoc='posthoc');cfg=dict(inherit_completed={job()['job_id']:'receipt'})
                with patch.object(v,'read',side_effect=lambda ref:deepcopy(data[ref if isinstance(ref,str) else 'receipt'])):
                    out,_=v.unit_record(cfg,u,dict(path=str(unitdir/'receipt.json')),v.ref(formal),v.ref(proto))
                    self.assertEqual(out['worker_pid'],9)
                    with self.assertRaises(ValueError):v.unit_record(cfg,u,dict(path=str(unitdir/'receipt.json')),v.ref(formal),v.ref(formal))

    def test_fixed_all_categories_and_counts_no_candidates_dropped(self):
        self.assertEqual((len(v.STOPS),len(v.FLAGS)),(16,26))
        value=v.audit_rows(iter([row()]),job(),1)
        self.assertEqual(sum(value['first_stop'].values()),1)
        self.assertEqual(value['absolute_counts']['unknown'],1)
        self.assertEqual(value['pose_shared_body_histograms']['unknown']['history_missing'],1)
        self.assertEqual(value['flags']['earliest_stage_trusted3_anchor_drift'],dict(true=0,false=0,null=1))

    def test_full_report_absolute_counts_and84_descriptions_tamper(self):
        records=twelve_counts()
        for i,r in enumerate(records):
            n=180118//12+(1 if i<180118%12 else 0);r['row_count']=n;r.update(frames=750,stages=2250)
            r['first_stop']={k:0 for k in v.STOPS};r['first_stop']['history_not_trusted_three']=n
            r['flags']={k:dict(true=0,false=n,null=0) for k in v.FLAGS}
            r['flags']['earliest_stage_trusted3_anchor_drift']=dict(true=0,false=0,null=n)
            r['absolute_counts']=dict(rows=n,candidates=0,positive=0,known_negative=0,unknown=0,correct_raw=0)
            r['pose_shared_body_histograms']={g:{k:0 for k in v.HISTOGRAM_KEYS} for g in v.GROUPS}
        cfg=dict(sequences=list(v.SEQUENCES));refs=['r'+str(i) for i in range(12)]
        report=dict(schema='decision_opportunity_analysis_v1',status=v.ANALYSIS_DONE,protocol='protocol',units=refs,absolute_frames=9000,
            unique_source_frames=2250,stages=27000,rows=180118,first_stop_totals=dict(history_not_trusted_three=180118),
            flag_totals={k:{g:sum(r['flags'][k][g] for r in records) for g in ('true','false','null')} for k in v.FLAGS},descriptions=v.descriptions(cfg,records),
            interval_count=84,bootstrap_seed=20261028,bootstrap_repeats=10000,unit_folds_are_not_independent_sources=True,test_read=False,
            new_optimizer_updates=0,new_model_forwards=0,new_solver_calls=0,new_TrackEval=0)
        with patch.object(v,'same_ref',return_value=True):
            verified=v.report_gate(cfg,report,records,refs,'protocol');self.assertEqual(verified['interval_count'],84)
            self.assertEqual(set(verified['normalized_first_stop_totals']),set(v.STOPS));self.assertTrue(verified['producer_sparse_zero_counter_schema'])
            bad=deepcopy(report);bad['flag_totals'].pop('positive_owned_elsewhere')
            with self.assertRaises(ValueError):v.report_gate(cfg,bad,records,refs,'protocol')
            bad=deepcopy(report);bad['rows']=180117
            with self.assertRaises(ValueError):v.report_gate(cfg,bad,records,refs,'protocol')

    def test_duplicate_coordinates_row_gap_missing_flag_and_wrong_source_rejected(self):
        for mutate in (lambda r:r.update(row_index=1),lambda r:r['job'].update(sequence='SNMOT-097'),
            lambda r:r['flags'].pop('positive_owned_elsewhere'),lambda r:r.update(first_stop='made_up'),lambda r:r.update(Pose_support_is_accuracy=True)):
            bad=row();mutate(bad)
            with self.assertRaises(ValueError):v.audit_rows(iter([bad]),job(),1)
        with self.assertRaises(ValueError):v.audit_rows(iter([row(),row()]),job(),2)
        with self.assertRaises(ValueError):v.audit_rows(iter([row()]),job(),2)

    def test_candidate_labels_counts_histogram_and_selected_UID_tamper_rejected(self):
        for mutate in (lambda r:r['absolute_counts'].update(unknown=0),lambda r:r['pose_candidates'][0].update(label_group='correct'),
            lambda r:r['pose_shared_body_histograms']['unknown'].update(history_missing=0),lambda r:r.update(selected_UID='candidate'),
            lambda r:r['pose_candidates'][0].update(reference_cost=float('nan'))):
            bad=row();mutate(bad)
            with self.assertRaises(ValueError):v.audit_rows(iter([bad]),job(),1)

    def test_pose_support_6of12_actual_gap_no_accuracy_claim(self):
        c=dict(uid='x',label=1,label_group='correct',current_body_valid=8,history_last_body_valid=7,shared_body_joints=6,
            history_each_shared_body_joints=[5,6,6],shared_body_ge6=True,structural_support_with_gap=True,enabled=True,reference_cost=.4)
        self.assertEqual(v.pose_candidate(c,3,30),('correct','6'))
        for mutate in (lambda x:x.update(shared_body_joints=13),lambda x:x.update(history_each_shared_body_joints=[6]),
            lambda x:x.update(shared_body_ge6=False),lambda x:x.update(shared_body_joints=8)):
            bad=deepcopy(c);mutate(bad)
            with self.assertRaises(ValueError):v.pose_candidate(bad,3,30)
        with self.assertRaises(ValueError):v.pose_candidate(c,3,31)
        c['structural_support_with_gap']=False
        self.assertEqual(v.pose_candidate(c,3,31),('correct','6'))

    def test_first_stops_full_denominator_flags_only_nonnull_twofold_source_equal(self):
        units=twelve_counts();cfg=dict(sequences=list(v.SEQUENCES))
        result=v.descriptions(cfg,units)
        self.assertEqual(sum(map(len,result.values())),84)
        expected={s:25. for s in v.SEQUENCES}
        self.assertEqual(result['R']['flags:trusted_three_history']['source_rates'],expected)
        self.assertEqual(result['RS']['first_stop:history_not_trusted_three']['mean_rate_pp'],100.)
        null=result['R']['flags:earliest_stage_trusted3_anchor_drift'];self.assertIsNone(null['Student_t_95CI']);self.assertEqual(null['n_independent_sources'],0)
        # 同源100行和300行等权平均率，不能按400行合并加权。
        group=[u for u in units if u['job']['regime']=='R' and u['job']['sequence']=='SNMOT-097']
        group[0]['flags']['actual_correct']=dict(true=0,false=100,null=0);group[1]['flags']['actual_correct']=dict(true=300,false=0,null=0)
        self.assertEqual(v.descriptions(cfg,units)['R']['flags:actual_correct']['source_rates']['SNMOT-097'],50.)

    def test_missing_one_source_denominator_null_CI_and_no_fill(self):
        units=twelve_counts();target=next(u for u in units if u['job']['regime']=='R')
        target['flags']['actual_correct']=dict(true=0,false=0,null=target['row_count'])
        out=v.descriptions(dict(sequences=list(v.SEQUENCES)),units)['R']['flags:actual_correct']
        self.assertIsNone(out['source_rates'][target['job']['sequence']]);self.assertIsNone(out['Student_t_95CI']);self.assertIsNone(out['percentile_match_bootstrap_95CI'])

    def test_t_df2_bootstrap_and_LOO_reproducible_all_sources(self):
        rates={'a':0.,'b':25.,'c':50.};out=v.interval(rates)
        self.assertAlmostEqual(out['Student_t_95CI'][1],25+4.302652729749462*25/(3**.5))
        self.assertEqual(out['leave_one_source_out_mean'],dict(a=37.5,b=25.,c=12.5));self.assertEqual(out,v.interval(rates))
        with self.assertRaises(ValueError):v.interval(dict(a=0.,b=float('nan'),c=2.))

    def test_new_compressed_ledger_stream_and_SHA_reject_changed_bytes(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);path=root/'units/j/rows.jsonl.gz';path.parent.mkdir(parents=True)
            with gzip.open(path,'wt',encoding='utf-8') as sink:sink.write(json.dumps(row())+'\n')
            with patch.object(v,'R',root),patch.object(v,'EXP',root/'units'):
                reference=v.ref(path);self.assertEqual(len(list(v.new_rows(reference))),1)
                with path.open('ab') as sink:sink.write(b'changed')
                with self.assertRaises(ValueError):list(v.new_rows(reference))

    def test_guard_blocks_original_compressed_frames_GT_weights_even_if_readonly(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);files=[root/'old/frames.jsonl.gz',root/'gt.txt',root/'model.pt'];new=root/'opportunity/units/x/rows.jsonl.gz'
            for p in files+[new]:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'x')
            with patch.object(v,'EXP',root/'opportunity'),v.no_old_raw_reads() as evidence:
                for path in files:
                    with self.assertRaises(PermissionError):path.read_bytes()
                self.assertEqual(new.read_bytes(),b'x')
            self.assertEqual(evidence['blocked_open_attempts'],3)

    def test_CIM_name_commandline_and_not_PID_alone(self):
        state=dict(worker_pids=[10,11],controller_pid=12)
        rows=[dict(ProcessId=10,Name='python.exe',CommandLine='python user_game.py')]
        self.assertTrue(v.processes_absent(rows,state,13)['producer_processes_absent'])
        for command in ('python D:/x/decision_opportunity_audit.py --execute','python -c "from multiprocessing.spawn import spawn_main; spawn_main()"'):
            with self.assertRaises(ValueError):v.processes_absent([dict(ProcessId=10,Name='python.exe',CommandLine=command)],state,13)


if __name__=='__main__':unittest.main()
