"""独立分类优先级/资格层/原BCE权重/三源四主量夹具，不读真实实验。"""
from copy import deepcopy
import gzip,json,hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import verify_state_label_alignment as v


def fixture(labels=(1,0,None),enabled=None,costs=None,present=True,raw=None,active=True,stage='high_score'):
    ids=['u'+str(i) for i in range(len(labels))];history=['h0','h1','h2'];query=1
    enabled=[True]*len(labels) if enabled is None else enabled;costs=[.4]*len(labels) if costs is None else costs
    if raw is None:raw=[ids[i] for i,x in enumerate(labels) if x==1]
    row=dict(job=dict(job_id='j',fold='game6',sequence='SNMOT-060',regime='R',seed=20261024,model_id='m'),frame_number=10,stage=stage,row_index=0,track_id=1,
        threshold=dict(high_score=.8,low_score=.5,unconfirmed=.7)[stage],history_UIDs=history,query_GT_id=query,
        flags=dict(learned_active=active,trusted_three_history=True,earliest_stage_trusted3_anchor_drift=None),earliest_stage_trusted3_anchor=None,
        pose_candidates=[dict(uid=u,label=l,enabled=e,reference_cost=c) for u,l,e,c in zip(ids,labels,enabled,costs)],actual_observation_gap_frames=5,
        absolute_counts=dict(candidates=len(labels),positive=labels.count(1),known_negative=labels.count(0),unknown=labels.count(None),correct_raw=len(raw)))
    ann=dict(frame_number=10,stage=stage,row_index=0,track_id=1,history_UIDs=history,query_GT_id=query,candidate_UIDs=ids,pair_labels=list(labels),history_count=3,
        history_status='trusted_consistent_history',current_GT_present=present,raw_correct_UIDs=raw)
    return row,ann


class IndependentClassification(unittest.TestCase):
    def test_path_kind_is_rejected_before_SHA_or_open_for_GT_model_frames(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);paths=[root/'model.pt',root/'frames.jsonl.gz',root/'gt.txt',root/'gap_registry.json']
            with patch.object(v,'R',root),patch.object(v,'sha',return_value='a'*64) as hashing:
                for path in paths:
                    with self.assertRaises(ValueError):v.checked(dict(path=str(path),sha256='a'*64),'rows')
                for path in (paths[0],paths[1],paths[2]):
                    with self.assertRaises(ValueError):v.ref(path)
                hashing.assert_not_called()

    def test_independent_admission_inherits_signed_same_unit_without_reclassification(self):
        r,a=fixture();summary,_=v.expected_classification(r,a);summary.update(window_uid='selected',is_selected_R_window=True)
        source=dict(job=r['job'],ledger=dict(path='ledger'),annotation=dict(path='annotation'));unit=dict(status='complete',source=source,protocol='admission',
            rows=dict(path='derived'),selected_windows=dict(path='windows'),selected_candidates=dict(path='candidates'),test_read=False,GT_coordinates_read=False,**{k:0 for k in v.ZERO_KEYS})
        proof=dict(schema='state_label_alignment_independent_admission_v1',status='complete_one_source_state_label_alignment_independent_classification_verified',protocol='admission',
            source_unit=source,selected_metadata_ref='original3000',unit_receipt='unit',output_records={k:unit[k] for k in ('rows','selected_windows','selected_candidates')},
            all_classifications_and_weights_independently_verified=True,producer_processes_absent=True,selected_windows=1,unit_audit=dict(rows=1),test_read=False,GT_coordinates_read=False,**{k:0 for k in v.ZERO_KEYS})
        cfg=dict(independent_admission='proof',selected_windows='original3000');data=dict(proof=proof,unit=unit)
        with patch.object(v,'read',side_effect=lambda ref:deepcopy(data[ref])),patch.object(v,'same_ref',side_effect=lambda x,y:x==y),patch.object(v,'checked',return_value=Path('fixture')), \
            patch.object(v,'json_rows',return_value=iter([summary])),patch.object(v,'expected_classification',side_effect=AssertionError('不得重跑已完成分类')):
            _,rows,audit=v.inherit_independent_unit(cfg,source,'unit','admission',{('j',10,'high_score',0,1):{}})
            self.assertEqual(len(rows),1);self.assertFalse(audit['source_classifications_reexecuted'])
            bad=deepcopy(proof);bad['source_unit']={}
            with patch.object(v,'read',side_effect=lambda ref:deepcopy(bad if ref=='proof' else unit)):
                with self.assertRaises(ValueError):v.inherit_independent_unit(cfg,source,'unit','admission',{('j',10,'high_score',0,1):{}})

    def test_all_seven_B_classes_and_priority_hand_examples(self):
        cases=[];r,a=fixture();cases.append((r,None,1));cases.append((*fixture(),2));cases.append((*fixture((0,None),present=False),3))
        cases.append((*fixture((0,0),present=False),4));cases.append((*fixture((0,0),present=True),5));cases.append((*fixture((0,0),raw=['outside']),6))
        cases.append((*fixture((0,0),raw=['u0']),7))
        for r,a,k in cases:
            summary,candidates=v.expected_classification(r,a)
            self.assertEqual(summary['B_class'],v.B_CLASSES[k-1]);self.assertEqual(len(candidates),summary['counts']['all_pairs'])
        r,a=fixture();a['current_GT_present']=None
        self.assertEqual(v.expected_classification(r,a)[0]['B_class'],v.B_CLASSES[0])
        r,a=fixture();a['history_status']='unknown'
        self.assertEqual(v.expected_classification(r,a)[0]['B_class'],v.B_CLASSES[0])

    def test_A_pre_probability_mask_and_actual_BCE_weight_not_CE_decomposition(self):
        r,a=fixture(enabled=[True,False,True],costs=[1.,.1,.8]);summary,c=v.expected_classification(r,a)
        self.assertTrue(c[0]['scoring_eligible']);self.assertEqual(c[0]['probability_status'],'probability_rejected')
        self.assertEqual(c[2]['probability_status'],'boundary_unknown');self.assertEqual(c[2]['BCE_window_pair_weight'],0.)
        self.assertEqual([x['BCE_window_pair_weight'] for x in c],[.5,.5,0.]);self.assertEqual(c[1]['BCE_R_step_pair_weight'],1/6)
        self.assertEqual(summary['bce_weights']['excluded_known_window_mass'],.5)
        self.assertTrue(summary['primary_flags'][v.PRIMARY[0]]);self.assertFalse(summary['primary_flags'][v.PRIMARY[1]])
        self.assertFalse(summary['bce_weights']['CE_pair_additive_decomposition_available'])
        r,a=fixture(active=False,costs=[1.,.8,.4]);summary,c=v.expected_classification(r,a)
        self.assertTrue(all(x['scoring_eligible'] is False and x['probability_status']=='not_applicable' for x in c))
        self.assertEqual(summary['bce_weights']['excluded_known_window_mass'],1.)

    def test_tristate_inactive_low_and_unknown_no_fabricated_negatives(self):
        self.assertEqual(v.independent_status('high_score',None,False,.4,.8),(False,'not_applicable'))
        self.assertEqual(v.independent_status('high_score',None,True,.4,.8),(None,'scoring_eligibility_unknown'))
        r,a=fixture((0,None),enabled=[None,True]);summary,c=v.expected_classification(r,a)
        self.assertIsNone(summary['primary_flags'][v.PRIMARY[0]]);self.assertTrue(summary['primary_flags'][v.PRIMARY[2]])
        self.assertEqual(summary['bce_weights']['unresolved_known_window_mass'],1.)
        self.assertIsNone(c[1]['label']);self.assertEqual(c[1]['BCE_window_pair_weight'],0.)
        r,a=fixture((0,),enabled=[None],active=False,stage='low_score');summary,c=v.expected_classification(r,a)
        self.assertEqual(c[0]['probability_status'],'not_applicable')

    def test_selected_exact_source_join_anchor_and_each_output_field_tamper(self):
        r,a=fixture();m=dict(source_job_id='j',candidate_frame_number=10,source_stage='high_score',source_row_index=0,source_track_id=1,fold='game6',sequence='SNMOT-060',
            teacher_model_id='m',history_UIDs=r['history_UIDs'],query_GT_id=1,candidate_UIDs=a['candidate_UIDs'],pair_labels=a['pair_labels'],anchor_drift=None,window_uid='selected')
        summary,c=v.expected_classification(r,a,m);v.verify_classification(r,a,m,summary,c)
        bad=deepcopy(summary);bad['counts']['unknown_pairs']=0
        with self.assertRaises(ValueError):v.verify_classification(r,a,m,bad,c)
        bad=deepcopy(c);bad[0]['BCE_window_pair_weight']=.1
        with self.assertRaises(ValueError):v.verify_classification(r,a,m,summary,bad)
        bad=deepcopy(m);bad['history_UIDs']=['wrong','h1','h2']
        with self.assertRaises(ValueError):v.expected_classification(r,a,bad)

    def test_independent_fields_match_producer_only_on_fixtures(self):
        import state_label_alignment_core as producer
        cases=[fixture(),fixture((0,None)),fixture((0,0),raw=['outside']),fixture((0,0),raw=['u0']),fixture(enabled=[None,False,True]),fixture(active=False),fixture((0,),enabled=[None],active=False,stage='low_score')]
        for r,a in cases:
            ours=v.expected_classification(r,a);actual=producer.classify_row(r,a)
            self.assertTrue(v.equal(ours[0],actual[0]));self.assertTrue(v.equal(ours[1],actual[1]))

    def selected(self):
        base=v.expected_classification(*fixture())[0];rows=[]
        for seq,heldout in v.SOURCES.items():
            for fold in v.FOLDS:
                if fold==heldout:continue
                for i in range(500):
                    r=deepcopy(base);r.update(is_selected_R_window=True,window_uid=fold+seq+str(i),fold=fold,sequence=seq)
                    r['primary_flags'][v.PRIMARY[0]]=i%3==0;r['primary_flags'][v.PRIMARY[1]]=i%5==0;r['primary_flags'][v.PRIMARY[2]]=i%7==0
                    rows.append(r)
        return rows

    def test_selected3000_four_primary_counts_weights_intervals_independent(self):
        import state_label_alignment_core as producer
        rows=self.selected();expected=v.selected_summary(rows,0);actual=producer.summarize_selected(rows)
        self.assertTrue(v.equal(expected,actual));self.assertEqual(len(expected['four_primary_descriptions']),4)
        self.assertEqual(expected['four_primary_descriptions'][v.PRIMARY[0]]['absolute_window_counts']['total'],3000)
        self.assertEqual(expected['four_primary_descriptions'][v.PRIMARY[0]]['Student_t_degrees_of_freedom'],2)
        for r in rows:
            if r['fold']=='game4' and r['sequence']=='SNMOT-097':r['primary_flags'][v.PRIMARY[0]]=None
        missing=v.selected_summary(rows,0)['four_primary_descriptions'][v.PRIMARY[0]]
        self.assertIsNone(missing['source_rates_pp']['SNMOT-097']);self.assertIsNone(missing['Student_t_95CI']);self.assertIsNone(missing['percentile_match_bootstrap_95CI'])
        self.assertTrue(v.equal(v.selected_summary(rows,0),producer.summarize_selected(rows)))
        with self.assertRaises(ValueError):v.selected_summary(rows[:-1],0)

    def test_nine_R_exposure_tables27000_original_epochs_weight_masses(self):
        rows=self.selected();tables={};bounds=[]
        for fold in v.FOLDS:
            group=[r for r in rows if r['fold']==fold]
            for seed in (20261024,20261025,20261026):
                path=fold+str(seed);bound=dict(fold=fold,seed=seed,table=path);bounds.append(bound)
                entries=[dict(window_uid=r['window_uid'],epoch=e,candidate_pairs=r['counts']['all_pairs'],labelled_pairs=r['counts']['known_pairs']) for e in range(3) for r in group]
                tables[path]=dict(fold=fold,seed=seed,real=entries)
        with patch.object(v,'read',side_effect=lambda ref:deepcopy(tables[ref])):
            out=v.exposure_summary(dict(exposure_tables=bounds),rows)
            self.assertEqual(sum(r['counts']['window_exposures'] for r in out),27000)
            self.assertTrue(all(r['table_shared_by_R_RS'] and r['not_doubled_to_18_run_consumption'] and r['new_training'] is False for r in out))
            bad=deepcopy(tables);bad[bounds[0]['table']]['real'][0]['labelled_pairs']=1
            with patch.object(v,'read',side_effect=lambda ref:deepcopy(bad[ref])):
                with self.assertRaises(ValueError):v.exposure_summary(dict(exposure_tables=bounds),rows)

    def test_stream_join_derived_summary_candidate_and_old_protocol_inheritance(self):
        r,a=fixture();a['job_id']='j'
        metadata=dict(source_job_id='j',candidate_frame_number=10,source_stage='high_score',source_row_index=0,source_track_id=1,fold='game6',sequence='SNMOT-060',
            teacher_model_id='m',history_UIDs=r['history_UIDs'],query_GT_id=1,candidate_UIDs=a['candidate_UIDs'],pair_labels=a['pair_labels'],anchor_drift=None,window_uid='selected')
        summary,pairs=v.expected_classification(r,a,metadata);total=v.accumulator();v.accumulate(total,summary)
        unit=dict(status='complete',protocol='admission',job=r['job'],source='source',rows=dict(path='derived',rows=1),selected_windows=dict(path='windows',rows=1),selected_candidates=dict(path='candidates',rows=3),
            worker_pid=1,test_read=False,GT_coordinates_read=False,**{k:0 for k in v.ZERO_KEYS},**total)
        source=dict(job=r['job'],ledger=dict(path='ledger',rows=1),annotation=dict(path='annotation',rows=1));unit['source']=source
        data=dict(derived=[summary],windows=[summary],candidates=[dict(window_uid='selected',job_id='j',**p) for p in pairs],ledger=[r],annotation=[a])
        with patch.object(v,'read',return_value=unit),patch.object(v,'same_ref',side_effect=lambda a,b:a==b),patch.object(v,'json_rows',side_effect=lambda ref:iter(deepcopy(data[ref['path']]))):
            _,chosen,audit=v.audit_unit(dict(inherit_completed={'j':'receipt'}),source,'receipt','formal','admission',{('j',10,'high_score',0,1):metadata})
            self.assertEqual(len(chosen),1);self.assertEqual(audit['selected_candidates'],3)
            bad=deepcopy(data);bad['candidates'][0]['BCE_R_step_pair_weight']=1.
            with patch.object(v,'json_rows',side_effect=lambda ref:iter(deepcopy(bad[ref['path']]))):
                with self.assertRaises(ValueError):v.audit_unit(dict(inherit_completed={'j':'receipt'}),source,'receipt','formal','admission',{('j',10,'high_score',0,1):metadata})

    def test_guard_and_real_CIM_identity_no_PID_only(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);allowed=root/'rows.jsonl.gz';old=root/'frames.jsonl.gz';allowed.write_bytes(b'x');old.write_bytes(b'x')
            with patch.object(v,'R',root),v.raw_guard([allowed]) as guard:
                self.assertEqual(allowed.read_bytes(),b'x')
                with self.assertRaises(PermissionError):old.read_bytes()
            self.assertEqual(guard['blocked_open_attempts'],1)
        state=dict(controller_pid=10,worker_pids=[11,12]);self.assertTrue(v.processes_absent([dict(ProcessId=10,Name='python.exe',CommandLine='python user_game.py')],state,13)['producer_processes_absent'])
        with self.assertRaises(ValueError):v.processes_absent([dict(ProcessId=10,Name='python.exe',CommandLine='python D:/code/state_label_alignment_diagnosis.py --execute')],state,13)


if __name__=='__main__':unittest.main()
