"""原始逐帧日志的零更新决策机会账本；不加载模型、GT坐标或分配器。"""
import math
from collections import Counter

STAGES=('high_score','low_score','unconfirmed')
THRESHOLDS=dict(high_score=.8,low_score=.5,unconfirmed=.7)

def require(ok,message):
    if not ok:raise ValueError(message)

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def record(value):
    require(isinstance(value,dict) and isinstance(value.get('uid'),str),'记录缺UID')
    xy=value.get('xy_px');mask=value.get('geometry_valid');box=value.get('bbox_xywh_px')
    require(isinstance(xy,list) and len(xy)==17 and all(isinstance(p,list) and len(p)==2 and all(finite(x) for x in p) for p in xy),'Pose须有限17×2')
    require(isinstance(mask,list) and len(mask)==17 and all(type(x) is bool for x in mask),'Pose mask须17bool')
    require(isinstance(box,list) and len(box)==4 and all(finite(x) for x in box) and min(box[2:])>0,'bbox结构无效')
    require(finite(value.get('timestamp_sec')),'timestamp无效')

def matrix(value,n,m,boolean=False):
    require(isinstance(value,list) and len(value)==n and all(isinstance(row,list) and len(row)==m for row in value),'矩阵形状不同')
    require(all(type(x) is bool if boolean else finite(x) for row in value for x in row),'矩阵值无效')

def analyze_frame(frame,annotations,anchors):
    """annotations必须含此帧全部stage行；anchors须每job独立、按时间顺序使用。"""
    number=frame['frame_number'];require(type(number) is int and number>0,'帧号无效')
    require([s['stage'] for s in frame['stages']]==list(STAGES),'完整三stage顺序不同')
    appearances={};frame_owners={}
    for stage in frame['stages']:
        name=stage['stage'];uids=stage['candidate_UIDs'];tracks=stage['track_ids']
        for uid in uids:appearances.setdefault(uid,[]).append(name)
        pairs=stage.get('assignments',stage.get('assignment'))
        if isinstance(pairs,dict):pairs=pairs['matches']
        require(isinstance(pairs,list),'原分配缺失')
        for pair in pairs:
            require(isinstance(pair,list) and len(pair)==2 and all(type(v) is int for v in pair)
                and 0<=pair[0]<len(tracks) and 0<=pair[1]<len(uids),'跨stage分配越界')
            frame_owners.setdefault(uids[pair[1]],[]).append(dict(stage=name,track_id=tracks[pair[0]],row_index=pair[0]))
    indexed={}
    for a in annotations:
        key=(a['stage'],a['row_index'],a['track_id'])
        require(a['frame_number']==number and key not in indexed,'后验重复或跨帧');indexed[key]=a
    ledger=[];used=set()
    for stage in frame['stages']:
        name=stage['stage'];rows=stage['rows'];uids=stage['candidate_UIDs'];candidates=stage['candidates'];n,m=len(rows),len(uids)
        require(len(stage['track_ids'])==n and len(set(stage['track_ids']))==n and len(candidates)==m and len(set(uids))==m,'行列身份重复或缺失')
        for candidate,uid in zip(candidates,uids):record(candidate);require(candidate['uid']==uid,'候选UID错位')
        costs=stage['reference_cost'];matrix(costs,n,m);matrix(stage['bbox_base_cost'],n,m)
        threshold=stage['threshold'];require(threshold==THRESHOLDS[name],'原stage门槛改变')
        active=stage.get('active',stage.get('active_rows'));require(isinstance(active,list) and len(active)==n and all(type(v) is bool for v in active),'active行缺失')
        gates=stage.get('gates',stage.get('motion_gate'));enabled=stage.get('enabled')
        if name=='low_score':require(gates is None and enabled is None and not any(active),'低分stage不应MLP干预')
        else:matrix(gates,n,m,True);matrix(enabled,n,m,True)
        assignments=stage.get('assignments',stage.get('assignment'))
        if isinstance(assignments,dict):assignments=assignments['matches']
        require(isinstance(assignments,list) and all(isinstance(p,list) and len(p)==2 and all(type(v) is int for v in p) and 0<=p[0]<n and 0<=p[1]<m for p in assignments),'分配越界')
        require(len({i for i,j in assignments})==len(assignments)==len({j for i,j in assignments}),'分配非一对一')
        selected=dict(assignments);owners={j:i for i,j in assignments}
        for i,row in enumerate(rows):
            track=stage['track_ids'][i];require(row['track_id']==track,'轨迹行错位');key=(name,i,track)
            require(key in indexed,'缺后验轨迹行');a=indexed[key];used.add(key)
            history=row['history'];require(len(history)<=3,'历史超3')
            for h in history:record(h)
            huids=[h['uid'] for h in history]
            require(huids==a['history_UIDs'] and len(set(huids))==len(huids) and all(x['timestamp_sec']<y['timestamp_sec'] for x,y in zip(history,history[1:])),'历史UID/时间不同')
            require(all(not history or history[-1]['timestamp_sec']<d['timestamp_sec'] for d in candidates),'候选不是历史之后')
            labels=a['pair_labels'];require(a['candidate_UIDs']==uids and len(labels)==m and all(v is None or type(v) is int and v in (0,1) for v in labels),'候选后验标签不同')
            chosen=selected.get(i);require(a['selected_column']==chosen and a['selected_UID']==(None if chosen is None else uids[chosen]),'后验实际选择不同')
            query=a['query_GT_id'];trusted=len(history)==3 and a['history_status']=='trusted_consistent_history' and query is not None
            if trusted and track not in anchors:anchors[track]=dict(gt_id=str(query),frame_number=number,stage=name,history_UIDs=list(huids))
            anchor=anchors.get(track);drift=None if anchor is None or query is None else str(query)!=anchor['gt_id']
            positive=[j for j,v in enumerate(labels) if v==1];negative=[j for j,v in enumerate(labels) if v==0];unknown=[j for j,v in enumerate(labels) if v is None]
            raw=a['raw_correct_UIDs'];require(isinstance(raw,list) and all(isinstance(v,str) for v in raw) and len(raw)==len(set(raw)) and set(uids[j] for j in positive)<=set(raw),'正确raw来源不一致')
            require(a['current_GT_present'] is None or type(a['current_GT_present']) is bool,'GT在场标记无效')
            if query is None:require(not positive,'无查询身份却有正例')
            if a['current_GT_present'] is False:require(not raw,'GT缺席却有可信正确raw')
            p_gate=bool(gates is not None and any(gates[i][j] for j in positive));p_enabled=bool(enabled is not None and any(enabled[i][j] for j in positive))
            pcost=[costs[i][j] for j in positive];strict=any(v<threshold for v in pcost);equal=any(v==threshold for v in pcost)
            actual_correct=chosen is not None and labels[chosen]==1
            neg_enabled=[j for j in negative if enabled is not None and enabled[i][j]]
            opportunity=trusted and active[i] and p_enabled and bool(neg_enabled)
            gap=a.get('actual_observation_gap_frames')
            require(gap is None or type(gap) is int and gap>0,'实际观测gap须正整数或null')
            gap_supported=gap is not None and 1<=gap<=30
            shared_by_candidate=[[sum(h['geometry_valid'][k] and candidate['geometry_valid'][k] for k in range(5,17)) for h in history] for candidate in candidates]
            supported=[bool(history and shared_by_candidate[j][-1]>=6 and gap_supported) for j in range(m)]
            pose_both=opportunity and any(enabled[i][j] and supported[j] for j in positive) and any(supported[j] for j in neg_enabled)
            other_stages={uid:[s for s in appearances.get(uid,[]) if s!=name] for uid in raw}
            other_owners={uid:[dict(owner) for owner in frame_owners.get(uid,[]) if owner['stage']!=name and owner['track_id']!=track] for uid in raw}
            flags=dict(trusted_three_history=trusted,learned_active=active[i],positive_motion_gate=p_gate,positive_enabled=p_enabled,
                strict_cost_feasible=strict,cost_equality_unknown=equal,actual_correct=actual_correct,
                actual_known_wrong=chosen is not None and labels[chosen]==0,actual_selection_unknown=chosen is not None and labels[chosen] is None,
                actual_unmatched=chosen is None,known_wrong_cheaper_or_equal=bool(pcost and any(costs[i][j]<=min(pcost) for j in negative)),
                unknown_competition=bool(unknown),unknown_enabled_competition=any(enabled is not None and enabled[i][j] for j in unknown),
                positive_owned_elsewhere=any(j in owners and owners[j]!=i for j in positive),earliest_stage_trusted3_anchor_drift=drift,
                local_opportunity=opportunity,pose_gap_1_to30=gap_supported,pose_gap_unknown=gap is None,
                pose_gap_outside_1_to30=gap is not None and not gap_supported,
                raw_correct_in_other_stage=any(other_stages.values()),raw_correct_owned_in_other_stage_other_track=any(other_owners.values()),
                local_opportunity_pose_supported_both=pose_both,
                local_opportunity_pose_supported_actual_noncorrect=pose_both and (chosen is None or labels[chosen]==0),
                local_opportunity_pose_supported_actual_known_wrong=pose_both and chosen is not None and labels[chosen]==0,
                local_opportunity_pose_supported_actual_unmatched=pose_both and chosen is None,
                local_opportunity_pose_supported_actual_unknown=pose_both and chosen is not None and labels[chosen] is None)
            if not trusted:stop='history_not_trusted_three'
            elif a['current_GT_present'] is None:stop='GT_presence_unknown'
            elif not a['current_GT_present']:stop='current_GT_absent'
            elif not raw:stop='trusted_correct_raw_absent'
            elif not positive:stop='correct_raw_not_in_stage'
            elif not active[i]:stop='low_score_bbox_only' if name=='low_score' else 'learned_inactive'
            elif not p_gate:stop='correct_motion_gate_rejected'
            elif not p_enabled:stop='correct_not_enabled'
            elif all(costs[i][j]==1. for j in positive if enabled[i][j]):stop='correct_probability_rejected'
            elif not strict:stop='cost_equality_unknown' if equal else 'correct_cost_above_threshold'
            elif actual_correct:stop='actual_correct'
            elif chosen is None:stop='actual_unmatched_with_strict_correct'
            elif labels[chosen] is None:stop='actual_unknown_with_strict_correct'
            else:stop='actual_known_wrong_with_strict_correct'
            pose=[]
            for j,candidate in enumerate(candidates):
                shared=None if not history else shared_by_candidate[j][-1]
                pose.append(dict(uid=uids[j],label=labels[j],label_group='unknown' if labels[j] is None else ('correct' if labels[j]==1 else 'known_negative'),
                    current_body_valid=sum(candidate['geometry_valid'][5:17]),history_last_body_valid=None if not history else sum(history[-1]['geometry_valid'][5:17]),
                    shared_body_joints=shared,history_each_shared_body_joints=shared_by_candidate[j],shared_body_ge6=None if shared is None else shared>=6,
                    structural_support_with_gap=supported[j],enabled=None if enabled is None else enabled[i][j],reference_cost=costs[i][j]))
            groups={}
            for group in ('correct','known_negative','unknown'):
                counts=Counter(str(p['shared_body_joints']) for p in pose if p['label_group']==group)
                groups[group]={str(k):counts[str(k)] for k in range(13)};groups[group]['history_missing']=counts['None']
            ledger.append(dict(frame_number=number,stage=name,row_index=i,track_id=track,history_UIDs=huids,query_GT_id=query,
                earliest_stage_trusted3_anchor=None if anchor is None else dict(anchor),first_stop=stop,flags=flags,
                actual_observation_gap_frames=gap,raw_correct_other_stage_appearances=other_stages,raw_correct_other_stage_other_track_assignments=other_owners,
                absolute_counts=dict(rows=1,candidates=m,positive=len(positive),known_negative=len(negative),unknown=len(unknown),correct_raw=len(raw)),
                pose_candidates=pose,pose_shared_body_histograms=groups,threshold=threshold,
                selected_column=chosen,selected_UID=a['selected_UID'],local_cost_comparison_is_causal=False,Pose_support_is_accuracy=False,new_solver_calls=0))
    require(used==set(indexed),'后验存在多余轨迹行')
    return ledger
