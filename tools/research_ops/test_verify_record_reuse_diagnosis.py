"""独立核查器纯小夹具，不打开研究数据或运行模型。"""
from copy import deepcopy
import unittest
from verify_record_reuse_diagnosis import (check_event,count_gap_pairs,count_windows,check_windows_summary,check_cases,
    check_window_sources,check_history_bounds,check_history_sources,physical,RISKS,STRATA)

def pair(left,right,uid='a'*64):
    def event(reason):
        if reason=='same_prediction_ID_recovered':return ['matched','matched'],'0','0'
        if reason=='different_prediction_ID':return ['matched','matched'],'0','1'
        if reason=='missing_prediction_endpoint':return ['missing','matched'],None,'0'
        return ['ambiguous','matched'],None,'0'
    a,b=event(left),event(right);ls=left=='same_prediction_ID_recovered';rs=right=='same_prediction_ID_recovered'
    return dict(family='mask_RS_minus_original_RS',panel='original_heldout',sequence='SNMOT-060',fold='game4',seed=20261024,event_uid=uid,
        left_condition='newMaskedBCE_RS',right_condition='originalstrongmotion_RS',left_reason=left,right_reason=right,
        left_endpoint_states=a[0],right_endpoint_states=b[0],left_start_prediction_ID=a[1],left_end_prediction_ID=a[2],
        right_start_prediction_ID=b[1],right_end_prediction_ID=b[2],transition=('stable_recovery' if ls else 'regressed') if rs else ('improved' if ls else 'persistent_failure'))

def window(uid='w',frame=1):
    return dict(schema='record_reuse_weak_label_window_v1',job_id='job',fold='game4',sequence='SNMOT-097',window_uid=uid,frame_number=frame,stage='high_score',row_index=0,track_id=1,
        history_UIDs=['h1','h2','h3'],query_GT_id='g',teacher_model_id='m',teacher_regime='R',teacher_seed=20261024,teacher_state_is_not_new_model_free_state=True,
        source_B_class='2_unique_known_positive',counts=dict(all_pairs=2,known_pairs=1,positive_pairs=1,known_negative_pairs=0,unknown_pairs=1),
        candidate_UIDs=['p','u'],pair_labels=[1,None],effective_known_pairs=1,eligible_unknown_pairs=1,
        risk_flags=dict(no_positive_with_eligible_unknown=False,unknown_strict_cost_feasible=True,positive_rejected_with_unknown_feasible=True,zero_effective_known=False,anchor_drift=None),
        case_strata=dict(zip(STRATA,(True,False,True,False,False))),reachability_level='correct_raw_probability_rejected',
        pair_risk_counts=dict(positive_probability_rejected_pairs=1,known_negative_strict_cost_feasible_pairs=0,unknown_strict_cost_feasible_pairs=1),
        current_GT_present=True,raw_correct_present=True,raw_correct_unique=True,correct_raw_in_stage=True,correct_raw_scoring_eligible=True,correct_raw_strict_cost_feasible=False,
        correct_raw_probability_statuses=['probability_rejected'],history_bin='3',gap_bin='1',candidate_bin='2',anchor_drift=None,earliest_stage_trusted3_anchor=None,
        negative_subtype='not_retained',unknown_subtype='not_retained',no_known_positive_with_unknown=False,source_labels_changed=False,new_causal_effect_estimated=False,unavailable_field=[])

def history():
    events=[]
    for i in range(235):
        events.append(dict(event_id=str(i),job_id='j0' if i==0 else 'r',fold='game4',sequence='SNMOT-097',regime='RS' if i==0 else 'R',seed=20261024,model_id='m',
            track_id=1,frame_number=740,wrong_uid='wrong',anchor_GT_id=None,prior_unknown=True,prior_wrong=False,first_error_status='unknown',candidate_eligible=False,exclusion_reasons=['unknown']))
    state=dict(protocol={'path':'protocol'},selected_events={'path':'selection'},observe={f'j{i}':{'path':f'obs{i}'} for i in range(6)})
    selection=dict(events=events,selected=[],absolute_counts=dict(total_first_observed_switches=235,eligible=0))
    units=[]
    for i in range(6):
        job=dict(job_id=f'j{i}',regime='RS',seed=20261024,fold=('game4','game6','game9')[i//2],sequence='SNMOT-097',model_id='m')
        units.append(dict(job=job,observe=state['observe'][f'j{i}'],frames_log={'path':f'log{i}'},observe_protocol=state['protocol'],selected_event_ids=['0'] if i==0 else [],source_frame_records_read=750 if i==0 else 0,zero_events_not_filled=i!=0))
    rows=[]
    for i in range(11):
        value=True if i==0 else None if i==1 else False
        rows.append(dict(frame_number=740+i,offset_frames=i,history_contains_wrong_UID=value,history_UIDs=None if value is None else ['wrong'] if value else [],
            list_membership='tracked_stracks' if value is not None else None,track_status='unique' if value is not None else 'missing_state_schema',write_observed=True if i==0 else None,
            stages=[],source_full_state_sha256=None,stage_log_complete=True))
    e=dict(event_id='0',job_id='j0',fold='game4',sequence='SNMOT-097',regime='RS',model_id='m',track_id=1,frame_number=740,wrong_UID='wrong',
        original_oracle_eligible=False,target_frame_records=rows,continuous_history_chain_broken=True,first_contiguous_history_exit_offset_frames=None,
        first_observed_history_absence_offset_frames=2,source_tail_censored=True,missing_target_frame_records=False,observed_history_presence_frames=1,
        unknown_or_ambiguous_history_frames=1,actual_error_frame_write_observed=True,future_stage_reads_containing_wrong_UID=0,future_stages_with_potential_scoring_exposure=0,
        future_stage_qualification_unknown=0,missing_or_incomplete_stage_log_frames=0,causal_effect_estimated=False,actual_MLP_calls_inferred=False)
    preserved=[dict(event_id=e['event_id'],selected_for_history_exposure=e['event_id']=='0',original_exclusion_reasons=e['exclusion_reasons'],prior_unknown=True,prior_wrong=False,original_event=deepcopy(e)) for e in events]
    value=dict(schema='bounded_RS_wrong_raw_history_exposure_v1',status='complete_bounded_existing_RS_wrong_raw_history_exposure_description',source_protocol=state['protocol'],source_selection=state['selected_events'],original_selection_counts=selection['absolute_counts'],
        original_eligible=0,original_selected=0,old_oracle_branches_executed=0,old45_oracle_intervals_not_reestimated=True,original_switch_event_count=235,
        original_all_event_selection_preserved=preserved,fixed_RS_units=units,event_records=[e],shared_source_event_groups=[dict(sequence='SNMOT-097',frame_number=740,wrong_UID='wrong',anchor_GT_id='None',event_ids=['0'],shared_source_observations=1)],
        absolute_counts=dict(target_frame_records=11,old_source_frame_records_read=750),budget={k:0 for k in ('optimizer_updates','new_model_forward_calls','new_tracking_frame_advances','new_solver_calls','GT_coordinate_reads','new_TrackEval_calls')},test_read=False)
    return value,selection,state

class Checks(unittest.TestCase):
    def test_four_outcomes_and_zero_ID(self):
        same='same_prediction_ID_recovered';missing='missing_prediction_endpoint';rows=[pair(same,same,'a'*64),pair(same,missing,'b'*64),pair(missing,same,'c'*64),pair(missing,missing,'d'*64)]
        r=count_gap_pairs(rows);self.assertEqual(r['transition_counts']['mask_RS_minus_original_RS'],dict(stable_recovery=1,improved=1,regressed=1,persistent_failure=1))
        self.assertEqual(r['per_family_unique_event_uids']['mask_RS_minus_original_RS'],4)
    def test_equal_failure_is_not_stable_recovery(self):
        r=pair('different_prediction_ID','different_prediction_ID');r['transition']='stable_recovery'
        with self.assertRaises(ValueError):count_gap_pairs([r])
    def test_gap_duplicates_and_unknown_reason_rejected(self):
        r=pair('ambiguous_endpoint','missing_prediction_endpoint')
        with self.assertRaises(ValueError):count_gap_pairs([r,r])
        r['left_reason']='ambiguous_prediction_endpoint'
        with self.assertRaises(ValueError):count_gap_pairs([r])
    def test_endpoint_reason_priority(self):
        with self.assertRaises(ValueError):check_event(dict(event_uid='a'*64,reason='missing_prediction_endpoint',endpoint_states=['ambiguous','missing'],start_prediction_ID=None,end_prediction_ID=None))
    def test_window_tri_unknown_not_false(self):
        r=window();s=count_windows([r]);s.update(new_confidence_intervals_computed=0,labels_changed=False,test_read=False)
        check_windows_summary(s,[r],expected=1);self.assertEqual(s['risk_counts']['anchor_drift'],{'null':1})
        s['risk_counts']['anchor_drift']={'false':1}
        with self.assertRaises(ValueError):check_windows_summary(s,[r],expected=1)
    def test_cases_first_two_cross_stratum_single_display(self):
        rows=[window('late',3),window('first',1),window('second',2)];slots=[]
        for key in ('positive_probability_rejected','unknown_strict_cost_feasible'):
            for rank,uid in enumerate(('first','second'),1):slots.append(dict(job_id='job',fold='game4',sequence='SNMOT-097',stratum=key,rank=rank,window_uid=uid))
        cases=dict(schema='record_reuse_weak_label_casebook_v1',maximum_slots=60,fill_shortfalls=False,duplicated_window_display=False,examples_are_not_independent_matches=True,slots=slots,
            windows=[dict(window=next(r for r in rows if r['window_uid']==uid),selection_tags=[s for s in slots if s['window_uid']==uid],candidates=[]) for uid in ('first','second')])
        self.assertEqual(check_cases(cases,rows)['unique_case_windows'],2)
        cases['slots'][0]['window_uid']='late'
        with self.assertRaises(ValueError):check_cases(cases,rows)
    def test_window_source_does_not_infer_label_subtype(self):
        r=window();old={k:r[k] for k in ('window_uid','fold','sequence','frame_number','stage','row_index','track_id','history_UIDs','query_GT_id','history_bin','gap_bin','candidate_bin','anchor_drift','earliest_stage_trusted3_anchor','unavailable_field','counts','current_GT_present')};old.update(B_class=r['source_B_class'],raw_correct_UIDs=['p'])
        pairs=[dict(window_uid='w',job_id='job',candidate_index=0,uid='p',label=1,scoring_eligible=True,probability_status='probability_rejected'),dict(window_uid='w',job_id='job',candidate_index=1,uid='u',label=None,scoring_eligible=True,probability_status='strict_cost_feasible')]
        job=dict(job_id='job',model_id='m');unit=dict(job=job,receipt={'path':'receipt'},selected_windows={'path':'windows'},selected_candidates={'path':'pairs'})
        class Reader:
            def json(self,_):return dict(status='complete',job=job,selected_windows=unit['selected_windows'],selected_candidates=unit['selected_candidates'],GT_coordinates_read=False,test_read=False)
            def lines(self,ref):return iter([old] if ref['path']=='windows' else pairs)
        check_window_sources([r],[unit],Reader(),expected_units=1,expected_per_unit=1,expected_windows=1,expected_pairs=2)
        r['pair_labels']=[1,0]
        with self.assertRaises(ValueError):check_window_sources([r],[unit],Reader(),expected_units=1,expected_per_unit=1,expected_windows=1,expected_pairs=2)
    def test_history_unknown_breaks_chain_and_tail_censor(self):
        h,s,t=history();r=check_history_bounds(h,s,t);self.assertEqual(r['target_frame_records'],11)
        h['event_records'][0]['first_contiguous_history_exit_offset_frames']=2
        with self.assertRaises(ValueError):check_history_bounds(h,s,t)
    def test_history_does_not_relax_old_oracle(self):
        h,s,t=history();s['events'][0]['candidate_eligible']=True
        with self.assertRaises(ValueError):check_history_bounds(h,s,t)
    def test_history_cannot_fill_missing_target_to31(self):
        h,s,t=history();h['event_records'][0]['source_tail_censored']=False
        with self.assertRaises(ValueError):check_history_bounds(h,s,t)
    def test_history_independent_source_membership(self):
        h,s,t=history()
        class Reader:
            def json(self,r):
                i=int(r['path'][3:]);u=h['fixed_RS_units'][i];return dict(job=u['job'],frames_log=u['frames_log'],protocol=u['observe_protocol'])
            def lines(self,r):
                for n in range(1,751):
                    values=['wrong'] if n==740 else []
                    groups=dict(tracked_stracks=[dict(track_id=1,history_UIDs=values)],lost_stracks=[],removed_stracks=[])
                    if n==741:groups=None
                    yield dict(frame_number=n,full_state_sha256=None,tracks_after=groups,stages=[dict(stage=x,track_ids=[]) for x in ('high_score','low_score','unconfirmed')],
                        lifecycle=[dict(track_id=1,operation='update',after={'record':{'uid':'wrong'}})] if n==740 else [])
        self.assertEqual(check_history_sources(h,s,Reader())['independent_target_records_checked'],11)
        h['event_records'][0]['target_frame_records'][2]['history_contains_wrong_UID']=True
        with self.assertRaises(ValueError):check_history_sources(h,s,Reader())
    def test_raw_weights_GT_test_media_paths_refused(self):
        for p in ('D:/projects/FutsalMOT_Research/pose/a/model.pt','D:/projects/FutsalMOT_Research/gt/a.json','D:/projects/FutsalMOT_Research/test/a.json','D:/projects/FutsalMOT_Research/SNMOT-116/a.json','D:/projects/FutsalMOT_Research/pose/a/image.png','D:/projects/FutsalMOT_Research/pose/a/gap_registry.json'):
            with self.assertRaises(ValueError):physical(p)

if __name__=='__main__':unittest.main()
