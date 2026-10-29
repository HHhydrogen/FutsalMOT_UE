"""新侧表独立终验的纯字典/流夹具；不读取实际研究数据、不运行模型或SGD。"""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
import verify_r_eligibility_inputs as v

def fixture():
    job=dict(job_id='job',model_id='teacher',fold='game4',sequence='SNMOT-097',regime='R',seed=20261024)
    history=['h0','h1','h2'];uids=['p','u','n'];labels=[1,None,0];enabled=[False,True,True]
    summary=dict(job_id='job',fold='game4',sequence='SNMOT-097',teacher_regime='R',teacher_seed=20261024,is_selected_R_window=True,
        window_uid='window',frame_number=4,stage='high_score',row_index=2,track_id=0,history_UIDs=history,query_GT_id='0',unavailable_field=[],
        counts=dict(all_pairs=3,known_pairs=2,positive_pairs=1,known_negative_pairs=1,unknown_pairs=1))
    pairs=[dict(window_uid='window',job_id='job',candidate_index=i,uid=uid,label=label,motion_gate=keep,enabled=keep,scoring_eligible=keep,
        motion_gate_missing_reason=None,labels_changed=False,hypothetical_mask_executed=False) for i,(uid,label,keep) in enumerate(zip(uids,labels,enabled))]
    provenance=dict(diagnostic_unit_receipt=dict(path='unit'),selected_windows=dict(path='summary'),selected_candidates=dict(path='candidates'))
    record=v.teacher_record(job,summary,pairs,provenance)
    source=dict(source_job_id='job',candidate_frame_number=4,source_stage='high_score',source_row_index=2,source_track_id=0,teacher_model_id='teacher',teacher_regime='R',teacher_seed=20261024,fold='game4',sequence='SNMOT-097')
    metadata=dict(window_uid='window',history_UIDs=history,candidate_UIDs=uids,pair_labels=labels,query_GT_id='0',**source)
    window=dict(window_uid='window',sequence='SNMOT-097',aligned_bank_metadata=metadata,history=[dict(uid=u) for u in history],candidates=[dict(prediction=dict(uid=u),label=label) for u,label in zip(uids,labels)])
    candidate=dict(window_uid='window',fold='game4',sequence='SNMOT-097',source_job_id='job',frame_number=4,stage='high_score',track_id=0,history_UIDs=history,
        candidate_UIDs=uids,candidate_scoring_mask=enabled,source_summary_coordinate=dict(frame_number=4,stage='high_score',row_index=2,track_id=0),
        label_values_unchanged=True,mask_uses_GT_labels_or_coordinates=False,mask_source='original_R_teacher_pre_probability_active_and_enabled',training_authorized_by_this_file=False)
    sidecar=dict(schema='R_candidate_eligibility_sidecar_v1',eligibility_rule=v.RULE,eligibility_stage='pre_probability',labels_used_to_choose_mask=False,
        window_uid='window',history_UIDs=history,candidate_UIDs=uids,active=True,enabled=enabled,scoring_eligible=enabled,active_evidence=v.EVIDENCE,provenance=provenance,**source)
    binding=dict(schema='R_candidate_eligibility_bound_window_v1',method_schema='R_candidate_eligibility_masked_BCE_method_v1',eligibility_rule=v.RULE,
        window_uid='window',history_UIDs=history,candidate_UIDs=uids,all_labels=labels,all_scoring_eligible=enabled,known_indices=[0,2],known_candidate_UIDs=['p','n'],known_labels=[1,0],known_scoring_eligible=[False,True],
        source=source,sidecar_sha256=v.digest(sidecar),accounting=v.independent_counts(labels,enabled),labels_changed=False,original_forward_known_order_preserved=True)
    binding['binding_sha256']=v.digest(binding)
    return window,record,candidate,sidecar,binding,pairs

class Contracts(unittest.TestCase):
    def verify(self,items):return v.verify_window(*items[:5])
    def test_independent_full_window_identity_ID0_and_unknown_excluded_from_loss(self):
        counts=self.verify(fixture());self.assertEqual(counts['kept_known_pairs'],1);self.assertEqual(counts['kept_negative_pairs'],1)
        self.assertEqual(counts['kept_unknown_pairs'],1);self.assertEqual(counts['excluded_positive_pairs'],1)
    def test_teacher_active_proof_cannot_be_inferred_from_nonexistent_gate(self):
        w,r,c,s,b,p=fixture()
        for change in (dict(motion_gate=None),dict(motion_gate_missing_reason='inactive_motion_gate_not_observed'),dict(scoring_eligible=False)):
            q=deepcopy(p);q[1].update(change)
            with self.assertRaises(ValueError):v.teacher_record(r['job'],r['summary'],q,r['provenance'])
    def test_teacher_order_and_regime_strict(self):
        w,r,c,s,b,p=fixture()
        with self.assertRaises(ValueError):v.teacher_record(dict(r['job'],regime='RS'),r['summary'],p,r['provenance'])
        with self.assertRaises(ValueError):v.teacher_record(r['job'],r['summary'],list(reversed(p)),r['provenance'])
    def test_pool_label_change_and_candidate_order_cannot_pass(self):
        a=fixture();a[0]['candidates'][0]['label']=0
        with self.assertRaises(ValueError):self.verify(a)
        a=fixture();a[0]['candidates'].reverse()
        with self.assertRaises(ValueError):self.verify(a)
    def test_source_row_query_and_history_change_refused(self):
        for change in (lambda a:a[0]['aligned_bank_metadata'].update(source_row_index=3),lambda a:a[0]['aligned_bank_metadata'].update(query_GT_id='9'),
            lambda a:a[0]['history'].__setitem__(0,dict(uid='other'))):
            a=fixture();change(a)
            with self.assertRaises(ValueError):self.verify(a)
    def test_mask_cannot_use_post_probability_or_label_and_provenance_required(self):
        for change in (dict(eligibility_stage='post_probability'),dict(labels_used_to_choose_mask=True),dict(provenance={}),dict(active=False)):
            a=fixture();a[3].update(change)
            with self.assertRaises(ValueError):self.verify(a)
    def test_binding_hash_and_known_projection_independently_rebuilt(self):
        for change in (dict(binding_sha256='bad'),dict(known_indices=[2,0]),dict(known_scoring_eligible=[True,True]),dict(known_labels=[0,1])):
            a=fixture();a[4].update(change)
            with self.assertRaises(ValueError):self.verify(a)
    def test_candidate_mask_full_coordinate_not_integer_and_bool_strict(self):
        for change in (dict(source_summary_coordinate=2),dict(source_summary_coordinate=dict(frame_number=4,stage='high_score',row_index=9,track_id=0)),dict(candidate_scoring_mask=[0,1,1])):
            a=fixture();a[2].update(change)
            with self.assertRaises(ValueError):self.verify(a)
    def test_actual_candidate_schema_and_old_guessed_names_cannot_substitute(self):
        self.assertEqual(set(fixture()[2]),v.CANDIDATE_MASK_FIELDS)
        for name,value in (('labels_unchanged',True),('labels_changed',False)):
            a=fixture();a[2].pop('label_values_unchanged');a[2][name]=value
            with self.assertRaises(ValueError):self.verify(a)
        for key,value in [('mask_uses_GT_labels_or_coordinates',True),('mask_source','model_probability'),('training_authorized_by_this_file',True),('label_values_unchanged',False)]:
            a=fixture();a[2][key]=value
            with self.assertRaises(ValueError):self.verify(a)
    def test_empty_effective_window_preserved_as_zero_known(self):
        self.assertEqual(v.independent_counts([1,None,0],[False,True,False])['effective_known_empty'],1)
        self.assertEqual(v.independent_counts([1,None,0],[False,True,False])['kept_unknown_pairs'],1)
    def test_input_type_guard_runs_before_sha_or_actual_open(self):
        with patch.object(v,'sha') as sha:
            for path in ('D:/projects/FutsalMOT_Research/public/gt/gt.txt','D:/projects/FutsalMOT_Research/pose/weights.pt','D:/projects/FutsalMOT_Research/test/source.json'):
                with self.assertRaises(ValueError):v.read(dict(path=path,sha256='a'*64))
            sha.assert_not_called()
    def test_builder_output_directory_is_checked_as_directory_then_final_file(self):
        directory=v.EXP/'inputs_a02'
        with patch.object(Path,'exists',return_value=False),patch.object(Path,'is_symlink',return_value=False),patch.object(v,'sha',return_value='a'*64) as sha:
            actual=v.builder_audit_ref(str(directory))
            self.assertEqual(Path(actual['path']),directory/'audit.json');sha.assert_called_once_with(directory/'audit.json')
            # 文件白名单不放宽：目录仍不可直接当文件引用。
            with self.assertRaises(ValueError):v.safe(directory)
    def test_builder_output_directory_cannot_escape_experiment_before_hash(self):
        with patch.object(v,'sha') as sha:
            with self.assertRaises(ValueError):v.builder_audit_ref(v.R/'pose/other/inputs_a02')
            sha.assert_not_called()
    def test_exposure_table_epoch_counts_and_no_reshuffle(self):
        index={str(i):v.independent_counts([1,None,0],[i%2==0,True,False]) for i in range(1000)}
        entries=[dict(window_uid=str(i),epoch=epoch,domain='real',candidate_pairs=3,labelled_pairs=2) for epoch in range(3) for i in range(1000)]
        table=dict(fold='game4',seed=20261024,augmentation='none_original_strongmotion',regimes_share_R=['R','RS'],S_order_and_rows_exact_original=True,real=entries,synthetic=[dict(window_uid=str(i)) for i in range(1000)])
        result=v.verify_exposure_table(table,'game4',20261024,index)
        self.assertEqual(result['window_exposures'],3000);self.assertEqual(result['counts']['kept_known_pairs'],1500)
        self.assertEqual(result['counts']['all3R_empty_steps'],0)
        table['real'][0]['epoch']=1
        with self.assertRaises(ValueError):v.verify_exposure_table(table,'game4',20261024,index)
    def test_no_producer_classifier_or_bind_module_imported(self):
        import inspect
        source=inspect.getsource(v)
        self.assertNotIn('import r_candidate_eligibility_method',source);self.assertNotIn('import r_eligibility_inputs',source)
    def test_actual_method_binding_contract_matches_pure_fixture(self):
        from r_candidate_eligibility_method import bind_window_mask
        window,record,candidate,sidecar,binding,_=fixture()
        produced=bind_window_mask(window,sidecar)
        self.assertEqual(produced,binding)
        self.assertEqual(v.verify_window(window,record,candidate,sidecar,produced)['kept_known_pairs'],1)
    def test_six_R_teachers_stream_and_RS_selected_files_never_open(self):
        values={};streams={};units=[]
        base=fixture();template_summary=base[1]['summary'];template_pairs=base[5]
        for fold in v.FOLDS:
            for sequence,heldout in v.SOURCE_FOLDS.items():
                if fold==heldout:continue
                for regime in ('R','RS'):
                    jid=fold+sequence+regime;job=dict(job_id=jid,model_id='teacher',fold=fold,sequence=sequence,regime=regime,seed=20261024)
                    ref=dict(path=jid);sr=dict(path=jid+'/selected_windows.jsonl',rows=500 if regime=='R' else 0)
                    cr=dict(path=jid+'/selected_candidates.jsonl.gz',rows=1500 if regime=='R' else 0)
                    values[jid]=dict(status='complete',job=job,selected_windows=sr,selected_candidates=cr);units.append(dict(job=job,receipt=ref))
                    if regime=='RS':continue
                    summaries=[];candidates=[]
                    for i in range(500):
                        uid=jid+str(i);summary=deepcopy(template_summary);summary.update(job_id=jid,fold=fold,sequence=sequence,window_uid=uid,row_index=i)
                        summaries.append(summary)
                        candidates.extend(dict(p,window_uid=uid,job_id=jid) for p in template_pairs)
                    streams[sr['path']]=summaries;streams[cr['path']]=candidates
        opened=[]
        def row_read(ref):opened.append(ref['path']);return iter(streams[ref['path']])
        with patch.object(v,'read',side_effect=lambda r:values[r['path']]),patch.object(v,'rows',side_effect=row_read):
            actual=v.teacher_records(dict(units=units))
        self.assertEqual(len(actual),3000);self.assertEqual(len(opened),12)
        self.assertTrue(all('RS/' not in path for path in opened))

if __name__=='__main__':unittest.main()
