"""历史raw暴露链的纯元数据夹具；没有真实模型/帧/GT读取。"""
from copy import deepcopy
import unittest
import record_reuse_history as m

def reference(path):return dict(path=path,sha256='a'*64)

def fixtures(events=None):
    observations={};objects={};jobs=[]
    for fold,sequences in [('game4',('SNMOT-097','SNMOT-151')),('game6',('SNMOT-060','SNMOT-151')),('game9',('SNMOT-060','SNMOT-097'))]:
        for sequence in sequences:
            jid=fold+'_'+sequence;job=dict(job_id=jid,fold=fold,sequence=sequence,regime='RS',seed=20261024,model_id=fold+'_model');jobs.append(job)
            receipt=reference(jid+'/receipt');frames=reference(jid+'/frames');observations[jid]=receipt
            objects[receipt['path']]=dict(job=job,status='complete',frames=750,frames_log=frames)
            objects[frames['path']]=[]
    state=dict(status='complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed',active=[],replay={},branch_posthoc={},
        observe=observations,protocol=reference('protocol'),selected_events=reference('selection'))
    if events is None:events=[event(jobs[0],1,'e0')]
    selection=dict(schema='trainR_free_state_posthoc_v1',events=events,selected=[],absolute_counts=dict(total_first_observed_switches=len(events),eligible=0,selected=0))
    return selection,state,objects,jobs

def event(job,number,eid):return dict(job,frame_number=number,track_id=3,event_id=eid,wrong_uid=eid+'_wrong',anchor_GT_id='8',
    prior_unknown=True,prior_wrong=False,first_error_status='unknown',candidate_eligible=False,exclusion_reasons=['first_error_status_unknown_prior_observation'])

def frame(number,wrong='e0_wrong',contains=True,active=True,history_missing=False,group='tracked_stracks'):
    track=dict(track_id=3,record=dict(uid=wrong),history_UIDs=[wrong] if contains else ['other'])
    if history_missing:track.pop('history_UIDs')
    groups={name:[] for name in ('tracked_stracks','lost_stracks','removed_stracks')};groups[group]=[track]
    stages=[]
    for stage in ('high_score','low_score','unconfirmed'):
        stages.append(dict(stage=stage,track_ids=[3] if stage=='high_score' else [],rows=[deepcopy(track)] if stage=='high_score' else [],
            active=[active] if stage=='high_score' else [],enabled=[[True]] if stage=='high_score' else [],
            candidate_UIDs=['next'],assignments=[[0,0]] if stage=='high_score' else [],reference_cost=[[0.4]] if stage=='high_score' else [],
            threshold=0.8,gate_recomputed_for_logging_only=stage!='low_score'))
    return dict(frame_number=number,tracks_after=groups,stages=stages,lifecycle=[dict(track_id=3,operation='update',after=deepcopy(track))],full_state_sha256='b'*64)

def reader(objects):
    def read(ref):
        value=objects[ref['path']]
        return iter(deepcopy(value)) if isinstance(value,list) else deepcopy(value)
    return read

class HistoryContracts(unittest.TestCase):
    def run_one(self,frames,event_number=1):
        selection,state,objects,jobs=fixtures();selection['events'][0]['frame_number']=event_number
        objects[jobs[0]['job_id']+'/frames']=frames
        return m.analyse_history(selection,state,reader(objects))

    def test_actual_write_future_read_and_exit(self):
        value=self.run_one([frame(i,contains=i<4) for i in range(1,32)]);e=value['event_records'][0]
        self.assertTrue(e['actual_error_frame_write_observed']);self.assertEqual(e['first_contiguous_history_exit_offset_frames'],3)
        self.assertEqual(e['future_stages_with_potential_scoring_exposure'],2);self.assertFalse(e['actual_MLP_calls_inferred'])
        self.assertEqual(value['absolute_counts']['target_frame_records'],31);self.assertEqual(value['absolute_counts']['old_source_frame_records_read'],31)

    def test_missing_history_breaks_chain(self):
        frames=[frame(i,contains=i<4,history_missing=i==2) for i in range(1,32)]
        e=self.run_one(frames)['event_records'][0];self.assertTrue(e['continuous_history_chain_broken']);self.assertIsNone(e['first_contiguous_history_exit_offset_frames'])
        self.assertEqual(e['first_observed_history_absence_offset_frames'],3)

    def test_missing_lifecycle_is_unknown_not_false_proof(self):
        rows=[frame(i) for i in range(1,32)];rows[0]['lifecycle']=[]
        e=self.run_one(rows)['event_records'][0];self.assertIsNone(e['actual_error_frame_write_observed']);self.assertTrue(e['prior_unknown'])

    def test_source_tail_censor_not_filled(self):
        e=self.run_one([frame(i) for i in range(1,751)],event_number=749)['event_records'][0]
        self.assertTrue(e['source_tail_censored']);self.assertEqual(len(e['target_frame_records']),2);self.assertFalse(e['missing_target_frame_records'])

    def test_fixed_first2_not_oracle_eligibility(self):
        selection,state,objects,jobs=fixtures();selection['events']=[event(jobs[0],n,'e'+str(n)) for n in (3,1,2)]
        selection['absolute_counts']['total_first_observed_switches']=3;objects[jobs[0]['job_id']+'/frames']=[frame(i) for i in range(1,33)]
        result=m.analyse_history(selection,state,reader(objects));self.assertEqual([e['event_id'] for e in result['event_records']],['e1','e2'])
        self.assertEqual(len(result['original_all_event_selection_preserved']),3);self.assertEqual(result['original_eligible'],0);self.assertEqual(result['old_oracle_branches_executed'],0)

    def test_no_events_no_frame_reads_or_fill(self):
        selection,state,objects,jobs=fixtures(events=[]);result=m.analyse_history(selection,state,reader(objects))
        self.assertEqual(result['absolute_counts']['selected_events'],0);self.assertEqual(result['absolute_counts']['old_source_frame_records_read'],0)

    def test_duplicate_event_id_rejected(self):
        selection,state,objects,jobs=fixtures();selection['events']*=2;selection['absolute_counts']['total_first_observed_switches']=2
        with self.assertRaisesRegex(ValueError,'event_id重复'):m.analyse_history(selection,state,reader(objects))

    def test_cross_list_duplicate_is_unknown(self):
        rows=[frame(i) for i in range(1,32)];rows[1]['tracks_after']['lost_stracks']=deepcopy(rows[1]['tracks_after']['tracked_stracks'])
        e=self.run_one(rows)['event_records'][0];self.assertEqual(e['target_frame_records'][1]['track_status'],'ambiguous_cross_list_or_duplicate');self.assertTrue(e['continuous_history_chain_broken'])

    def test_original_data_not_mutated_or_old_rule_relaxed(self):
        selection,state,objects,jobs=fixtures();objects[jobs[0]['job_id']+'/frames']=[frame(i) for i in range(1,32)];old=deepcopy((selection,state,objects))
        result=m.analyse_history(selection,state,reader(objects));self.assertEqual((selection,state,objects),old)
        self.assertEqual(result['original_all_event_selection_preserved'][0]['original_event'],selection['events'][0])
        self.assertTrue(result['old45_oracle_intervals_not_reestimated']);self.assertTrue(result['actual_forward_or_error_cause_not_estimated'])
        selection['events'][0]['candidate_eligible']=True
        with self.assertRaisesRegex(ValueError,'零eligible'):m.analyse_history(selection,state,reader(objects))

    def test_missing_stages_and_low_qualification_are_explicit(self):
        rows=[frame(i,active=False) for i in range(1,32)];rows[2].pop('stages')
        e=self.run_one(rows)['event_records'][0];self.assertEqual(e['missing_or_incomplete_stage_log_frames'],1);self.assertEqual(e['future_stages_with_potential_scoring_exposure'],0)

    def test_same_physical_event_groups_do_not_drop_contexts(self):
        selection,state,objects,jobs=fixtures();left=jobs[0];right=jobs[5]
        selection['events']=[event(left,1,'left'),event(right,1,'right')]
        for e in selection['events']:e['wrong_uid']='shared_wrong'
        selection['absolute_counts']['total_first_observed_switches']=2
        for j in (left,right):objects[j['job_id']+'/frames']=[frame(i,wrong='shared_wrong') for i in range(1,32)]
        result=m.analyse_history(selection,state,reader(objects));self.assertEqual(len(result['event_records']),2)
        self.assertEqual(len(result['shared_source_event_groups']),1);self.assertEqual(result['shared_source_event_groups'][0]['shared_source_observations'],2)

    def test_twelve_events_372_targets_bound(self):
        selection,state,objects,jobs=fixtures();selection['events']=[]
        for job in jobs:
            selection['events'] += [event(job,i,job['job_id']+str(i)) for i in (1,2)]
            objects[job['job_id']+'/frames']=[frame(i) for i in range(1,33)]
        selection['absolute_counts']['total_first_observed_switches']=12
        result=m.analyse_history(selection,state,reader(objects));self.assertEqual(result['absolute_counts']['selected_events'],12)
        self.assertEqual(result['absolute_counts']['target_frame_records'],372);self.assertEqual(result['absolute_counts']['old_source_frame_records_read'],192)

    def test_stream_drops_full_frame_before_next_decode(self):
        selection,state,objects,jobs=fixtures();alive=[0,0]
        class Frame(dict):
            def __init__(self,value):super().__init__(value);alive[0]+=1;alive[1]=max(alive)
            def __del__(self):alive[0]-=1
        def source(reference):
            if reference['path'].endswith('/receipt'):return deepcopy(objects[reference['path']])
            return (Frame(frame(i)) for i in range(1,32))
        m.analyse_history(selection,state,source);self.assertEqual(alive[1],1);self.assertEqual(alive[0],0)

    def test_foreign_or_duplicate_fold_source_refused(self):
        selection,state,objects,jobs=fixtures(events=[]);receipt=next(iter(state['observe'].values()))
        objects[receipt['path']]['job']['sequence']='foreign-source'
        with self.assertRaisesRegex(ValueError,'原train来源'):m.analyse_history(selection,state,reader(objects))

if __name__=='__main__':unittest.main()
