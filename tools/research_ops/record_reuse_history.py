"""只读既有RS旁观日志，描述错误raw写入后的历史暴露；不执行追踪或因果干预。"""
from collections import Counter,defaultdict
from copy import deepcopy

FOLDS=('game4','game6','game9')
TRAIN_SOURCES={'game4':('SNMOT-097','SNMOT-151'),'game6':('SNMOT-060','SNMOT-151'),'game9':('SNMOT-060','SNMOT-097')}
SCHEMA='bounded_RS_wrong_raw_history_exposure_v1'
STATUS='complete_bounded_existing_RS_wrong_raw_history_exposure_description'

def require(value,message):
    if not value:raise ValueError(message)

def _history(track):
    if not isinstance(track,dict):return None
    values=track.get('history_UIDs')
    if values is None and isinstance(track.get('history'),list):
        rows=track['history']
        if all(isinstance(v,dict) and isinstance(v.get('uid'),str) for v in rows):values=[v['uid'] for v in rows]
    return list(values) if isinstance(values,list) and all(isinstance(v,str) for v in values) else None

def _tracks(frame,track_id):
    value=frame.get('tracks_after');rows=[]
    if isinstance(value,dict):
        for group in ('tracked_stracks','lost_stracks','removed_stracks'):
            if not isinstance(value.get(group),list):return None
            rows.extend((group,row) for row in value[group] if row.get('track_id')==track_id)
    elif isinstance(value,list):rows=[(v.get('list_membership'),v) for v in value if v.get('track_id')==track_id]
    else:return None
    return rows

def _stage_rows(frame,event,offset):
    output=[]
    for stage in frame.get('stages',[]):
        ids=stage.get('track_ids',[]);indices=[i for i,v in enumerate(ids) if v==event['track_id']]
        if not indices:continue
        if len(indices)!=1:
            output.append(dict(stage=stage.get('stage'),history_read_contains_wrong_UID=None,status='ambiguous_track_rows'));continue
        i=indices[0];rows=stage.get('rows');history=_history(rows[i]) if isinstance(rows,list) and i<len(rows) else None
        if history is None:
            hs=stage.get('history_UIDs');history=hs[i] if isinstance(hs,list) and i<len(hs) and isinstance(hs[i],list) and all(isinstance(v,str) for v in hs[i]) else None
        contains=None if history is None else event['wrong_uid'] in history
        active=stage.get('active',stage.get('active_rows'));active=active[i] if isinstance(active,list) and i<len(active) and type(active[i]) is bool else None
        enabled=stage.get('enabled');enabled=enabled[i] if isinstance(enabled,list) and i<len(enabled) else None
        enabled_count=sum(enabled) if isinstance(enabled,list) and all(type(v) is bool for v in enabled) else None
        potential=None if active is None or (active and enabled_count is None) else (enabled_count if active else 0)
        assignments=stage.get('assignments',stage.get('assignment',[]))
        if isinstance(assignments,dict):assignments=assignments.get('matches',[])
        selected=[pair[1] for pair in assignments if isinstance(pair,(list,tuple)) and len(pair)==2 and pair[0]==i]
        candidates=stage.get('candidate_UIDs',[]);uid=None
        if len(selected)==1 and type(selected[0]) is int and 0<=selected[0]<len(candidates):uid=candidates[selected[0]]
        cost=stage.get('reference_cost');native_cost=None
        if len(selected)==1 and isinstance(cost,list) and i<len(cost) and isinstance(cost[i],list) and 0<=selected[0]<len(cost[i]):native_cost=deepcopy(cost[i][selected[0]])
        output.append(dict(stage=stage.get('stage'),history_UIDs=history,history_read_contains_wrong_UID=contains,
            active=active,enabled_candidate_count=enabled_count,potential_eligible_pair_count=potential,
            potential_exposure_of_written_wrong_UID=bool(offset>0 and contains is True and potential is not None and potential>0),
            qualification_recomputed_for_logging_only=stage.get('gate_recomputed_for_logging_only'),
            native_selected_UID=uid,native_selected_cost=native_cost,threshold=stage.get('threshold'),
            actual_MLP_forward_not_proven_by_this_row=True,status='existing_observer_stage'))
    return output

def _target(frame,event):
    offset=frame['frame_number']-event['frame_number'];tracks=_tracks(frame,event['track_id'])
    row=dict(frame_number=frame['frame_number'],offset_frames=offset,history_contains_wrong_UID=None,
        history_UIDs=None,list_membership=None,track_status='missing_state_schema',write_observed=None,
        stages=_stage_rows(frame,event,offset),source_full_state_sha256=frame.get('full_state_sha256'))
    row['stage_log_complete']=isinstance(frame.get('stages'),list) and [v.get('stage') for v in frame['stages']]==['high_score','low_score','unconfirmed']
    if tracks is not None:
        row['track_status']='absent' if not tracks else 'ambiguous_cross_list_or_duplicate' if len(tracks)>1 else 'unique'
        if len(tracks)==1:
            group,track=tracks[0];history=_history(track)
            row.update(list_membership=group,history_UIDs=history,history_contains_wrong_UID=None if history is None else event['wrong_uid'] in history)
    if offset==0:
        writes=[v for v in frame.get('lifecycle',[]) if v.get('track_id')==event['track_id']
            and v.get('operation',v.get('event')) in ('activate','update','re_activate')]
        exact=[v for v in writes if (v.get('after',{}).get('record') or {}).get('uid')==event['wrong_uid']]
        row['write_observed']=True if len(exact)==1 and len(writes)==1 else None
        row['write_status']='exact_existing_lifecycle_write' if row['write_observed'] else 'missing_or_ambiguous_lifecycle_write'
    return row

def _summarize(event,rows,source_frames):
    known=[v['history_contains_wrong_UID'] for v in rows];broken=False;exit_offset=None;was_present=False
    for row in rows:
        value=row['history_contains_wrong_UID']
        if value is None:broken=True
        elif value:was_present=True
        elif was_present and not broken and exit_offset is None:exit_offset=row['offset_frames']
    stages=[v for row in rows if row['offset_frames']>0 for v in row['stages']]
    return dict(event_id=event['event_id'],job_id=event['job_id'],fold=event['fold'],sequence=event['sequence'],regime=event['regime'],
        model_id=event['model_id'],track_id=event['track_id'],frame_number=event['frame_number'],wrong_UID=event['wrong_uid'],
        anchor_GT_id=event.get('anchor_GT_id'),prior_unknown=event.get('prior_unknown'),prior_wrong=event.get('prior_wrong'),
        original_first_error_status=event.get('first_error_status'),original_oracle_eligible=event.get('candidate_eligible'),
        original_exclusion_reasons=deepcopy(event.get('exclusion_reasons',[])),target_frame_records=rows,
        actual_error_frame_write_observed=rows[0]['write_observed'] if rows and rows[0]['offset_frames']==0 else None,
        observed_history_presence_frames=sum(v is True for v in known),unknown_or_ambiguous_history_frames=sum(v is None for v in known),
        continuous_history_chain_broken=broken,first_contiguous_history_exit_offset_frames=exit_offset,
        first_observed_history_absence_offset_frames=next((v['offset_frames'] for v in rows if v['history_contains_wrong_UID'] is False),None),
        first_lost_offset_frames=next((v['offset_frames'] for v in rows if v['list_membership']=='lost_stracks'),None),
        first_removed_offset_frames=next((v['offset_frames'] for v in rows if v['list_membership']=='removed_stracks'),None),
        future_stage_reads_containing_wrong_UID=sum(v.get('history_read_contains_wrong_UID') is True for v in stages),
        future_stages_with_potential_scoring_exposure=sum(v.get('potential_exposure_of_written_wrong_UID') is True for v in stages),
        future_stage_qualification_unknown=sum(v.get('potential_eligible_pair_count') is None for v in stages),
        missing_or_incomplete_stage_log_frames=sum(not v['stage_log_complete'] for v in rows),
        source_tail_censored=event['frame_number']+30>source_frames,missing_target_frame_records=len(rows)!=min(31,source_frames-event['frame_number']+1),
        future_identity_or_recovery_not_relabelled=True,causal_effect_estimated=False,actual_MLP_calls_inferred=False)

def analyse_history(selection,state,reader):
    """reader(ref)给JSON收据dict或frames_log逐帧iterator；路径/SHA守卫由调用者负责。"""
    require(selection.get('schema')=='trainR_free_state_posthoc_v1','只准原完整切换选择元数据')
    events=selection['events'];ids=[v['event_id'] for v in events]
    require(len(set(ids))==len(ids),'原event_id重复，不隐式去重')
    require(selection.get('selected')==[] and all(v.get('candidate_eligible') is False for v in events),'原oracle零eligible/selected规则不能改变')
    require(state.get('status')=='complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed'
        and state.get('active')==[] and not state.get('replay') and not state.get('branch_posthoc'),'只准已闭合旧诊断，不重跑四支')
    require(selection['absolute_counts']['total_first_observed_switches']==len(events) and selection['absolute_counts']['eligible']==0,'原选择分母或零eligible不同')
    units=[]
    for job_id,reference in sorted(state['observe'].items()):
        receipt=reader(reference);job=receipt['job']
        require(job_id==job['job_id'] and receipt['status']=='complete' and receipt['frames']==750,'observe单位/750完整性不足')
        if job['regime']=='RS':
            require(job['fold'] in FOLDS and job['seed']==20261024,'只准原首seed三fold RS')
            require(job['sequence'] in TRAIN_SOURCES[job['fold']],'只准该fold允许的原train来源')
            units.append((job,reference,receipt))
    require(len(units)==6 and Counter(v[0]['fold'] for v in units)==Counter({f:2 for f in FOLDS}),'必须固定六RS单位，不按成绩选单位')
    require({(v[0]['fold'],v[0]['sequence']) for v in units}=={(f,s) for f in FOLDS for s in TRAIN_SOURCES[f]},'六个fold-source必须齐全且唯一')
    chosen={};selection_rows=[]
    for job,reference,receipt in units:
        rows=sorted([v for v in events if v['job_id']==job['job_id']],key=lambda v:(v['frame_number'],v['track_id'],v['event_id']))
        for row in rows:
            require(all(row[k]==job[k] for k in ('fold','sequence','regime','seed','model_id')),'事件与实际observe身份不符')
        chosen[job['job_id']]=rows[:2]
    selected_ids={v['event_id'] for rows in chosen.values() for v in rows}
    for event in events:
        selection_rows.append(dict(original_event=deepcopy(event),event_id=event['event_id'],job_id=event['job_id'],fold=event['fold'],sequence=event['sequence'],regime=event['regime'],
            frame_number=event['frame_number'],track_id=event['track_id'],prior_unknown=event.get('prior_unknown'),prior_wrong=event.get('prior_wrong'),
            original_first_error_status=event.get('first_error_status'),original_oracle_eligible=False,
            original_exclusion_reasons=deepcopy(event.get('exclusion_reasons',[])),selected_for_history_exposure=event['event_id'] in selected_ids,
            new_selection_reason='RS_fixed_first2_by_frame_track_event' if event['event_id'] in selected_ids else 'non_RS_unit' if event['regime']!='RS' else 'RS_after_fixed_cap'))
    result_events=[];unit_receipts=[];read_count=0;target_count=0
    for job,reference,receipt in units:
        selected=chosen[job['job_id']];rows={v['event_id']:[] for v in selected};count=0
        if selected:
            require(all(type(v['frame_number']) is int and 1<=v['frame_number']<=750 for v in selected),'事件源帧越界')
            last=min(750,max(v['frame_number']+30 for v in selected));stream=iter(reader(receipt['frames_log']))
            try:
                for frame in stream:
                    count+=1;require(count<=750 and frame['frame_number']==count,'旧日志须从帧1连续流式读取')
                    for event in selected:
                        if event['frame_number']<=count<=event['frame_number']+30:rows[event['event_id']].append(_target(frame,event));target_count+=1
                    del frame  # 下一条解码前释放完整旧帧；只保留小的目标字段，不跨单位驻留。
                    if count==last:break
                require(count==last,'旧完整日志在目标帧前意外终止')
            finally:
                close=getattr(stream,'close',None)
                if close:close()
            result_events.extend(_summarize(event,rows[event['event_id']],750) for event in selected)
        read_count+=count;unit_receipts.append(dict(job=deepcopy(job),observe=deepcopy(reference),observe_protocol=deepcopy(receipt.get('protocol')),frames_log=deepcopy(receipt['frames_log']),source_frame_records_read=count,
            selected_event_ids=[v['event_id'] for v in selected],zero_events_not_filled=not selected))
    require(len(result_events)<=12 and target_count<=372 and read_count<=4500,'固定预算越界')
    grouped=defaultdict(list)
    by_id={v['event_id']:v for v in events}
    for event in result_events:
        source=by_id[event['event_id']];grouped[(source['sequence'],source['frame_number'],source['wrong_uid'],str(source.get('anchor_GT_id')))].append(source['event_id'])
    groups=[dict(sequence=k[0],frame_number=k[1],wrong_UID=k[2],anchor_GT_id=k[3],event_ids=v,shared_source_observations=len(v)) for k,v in sorted(grouped.items())]
    return dict(schema=SCHEMA,status=STATUS,source_protocol=deepcopy(state['protocol']),source_selection=deepcopy(state['selected_events']),
        original_selection_counts=deepcopy(selection['absolute_counts']),original_switch_event_count=len(events),original_eligible=0,original_selected=0,
        old_oracle_branches_executed=0,old45_oracle_intervals_not_reestimated=True,original_all_event_selection_preserved=selection_rows,
        selection_order='per_fixed_RS_job:frame_number,track_id,event_id;first2;no_eligibility_filter_no_fill',
        fixed_RS_units=unit_receipts,event_records=result_events,shared_source_event_groups=groups,
        absolute_counts=dict(RS_units=6,selected_events=len(result_events),target_frame_records=target_count,old_source_frame_records_read=read_count,
            unique_shared_source_event_groups=len(groups),events_with_prior_unknown=sum(v['prior_unknown'] is True for v in result_events),
            events_with_exact_existing_write=sum(v['actual_error_frame_write_observed'] is True for v in result_events)),
        budget=dict(maximum_events=12,maximum_target_frame_records=372,maximum_old_source_frame_records=4500,horizon_future_frames=30,
            optimizer_updates=0,new_model_forward_calls=0,new_tracking_frame_advances=0,new_solver_calls=0,GT_coordinate_reads=0,new_TrackEval_calls=0),
        event_observations_not_independent_matches=True,actual_forward_or_error_cause_not_estimated=True,new_AssA_HOTA_IDF1=None,test_read=False)
