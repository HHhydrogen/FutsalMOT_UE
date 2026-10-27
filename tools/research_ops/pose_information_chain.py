"""复用54份共同状态的零更新Pose信息/候选/分配链诊断；不重跑自由追踪。"""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import pose_information_geometry as geo

R=Path('D:/projects/FutsalMOT_Research');E=R/'pose/pose_information_a01'
ROOT=Path(__file__).resolve().parents[2]
PARAMETERS=dict(optimizer_updates=0,GPU=False,source_common_units=54,minimum_common_limbs=6,
    near_motion_quantile=.25,velocity_norm_clip_quantile=.99,shuffle_seed=20261027,
    geometric_descriptors=['latest','mean','temporal'],shuffle='same_frame_exact_mask_scale_cyclic',
    original_gate_preserved=True,GT_only_posthoc=True,new_free_tracking=False,
    reference_assignment_source='recorded_actual_reference_cost',
    shadow_assignment_comparison='only_if_shadow_motion_assignment_equals_actual_exactly')


def require(ok,message):
    if not ok:raise ValueError(message)


def safe(p):
    import re
    p=Path(p)
    require(not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'封存测试禁止读取')
    return p


def read(p):return json.loads(safe(p).read_text(encoding='utf-8-sig'))


def sha(p):
    h=hashlib.sha256()
    with safe(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def ref(p):return dict(path=str(p),sha256=sha(p))


def checked(r):
    p=safe(r['path']);require(sha(p)==r['sha256'],'来源改变：'+str(p));return p


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m


def context(config):
    c=read(config)
    require(c['schema']=='pose_information_zero_update_protocol_v1' and c['approved_by']=='root'
        and c['diagnostic_authorized'] and c['training_authorized'] is False and c['test_sealed']
        and c['parameters']==PARAMETERS and Path(c['bundle'])==ROOT and ROOT.parent==R/'code','新零更新准入不符')
    for x in read(checked(c['bundle_manifest']))['files']:require(sha(ROOT/x['path'])==x['sha256'],'新源码变化')
    legacy=read(checked(c['mechanism_protocol']));oldbundle=Path(legacy['bundle'])
    sys.path.insert(0,str(oldbundle/'tools/research_ops'))
    core=load('information_original_mechanism_core',oldbundle/'tools/research_ops/pose_mechanism_core.py')
    d=core.validate(checked(c['mechanism_protocol']))
    require(read(checked(c['mechanism_complete']))['status']=='complete162_diagnostics_sources_results_and_process_exit_verified','原诊断未闭合')
    require(read(checked(c['amplitude_complete']))['status']=='complete108_CPU_amplitude_probe_source_metrics_and_exit_verified','幅度未闭合')
    inputs=read(checked(legacy['inputs']));control=Path(c['mechanism_protocol']['path']).parents[1]/'control_a01'
    jobs=[j for j in legacy['jobs'] if j['kind']=='common_state']
    require(len(jobs)==54 and len({j['job_id'] for j in jobs})==54,'须全54原状态，不挑池或seed')
    return c,core,d,inputs,control,jobs


def calibrate(pool,model,adapter,features,torch):
    """近motion阈值只拟合本fold允许trainR，不读标签。"""
    vectors=[];bounds=[];speeds=[]
    for w in pool:
        h=[geo.public(x) for x in w['history']];start=len(vectors)
        vectors.extend(adapter.transform(features(h,geo.public(x['prediction'])),use_pose=False) for x in w['candidates'])
        bounds.append((start,len(vectors)))
        speeds.extend(math.hypot(*v) for v in geo.velocities(h).values())
    with torch.no_grad():scores=model(torch.tensor(vectors,dtype=torch.float32)).reshape(-1).tolist()
    gaps=[]
    for a,b in bounds:
        q=sorted(scores[a:b],reverse=True)
        if len(q)>=2:gaps.append(q[0]-q[1])
    require(gaps and speeds,'trainR不足以拟合冻结代理量')
    return dict(near_motion_gap=geo.quantile(gaps,.25),velocity_clip=max(1e-9,geo.quantile(speeds,.99)),
        fit_windows=len(pool),windows_with_two_candidates=len(gaps),velocity_observations=len(speeds),
        fit_scope='allowed_base_train_R_only_no_labels_no_external',quantiles=dict(motion=.25,velocity=.99))


def classify_row(e,i,labels,GT,allraw,index,assignments,cal,swapped,swapmap,counts):
    history=e['history_UIDs'][i];query,reason=geo.identity(history,labels)
    row=dict(frame=e['frame_number'],stage=e['stage'],track=e['track_ids'][i],history_status=reason,
             active=int(e['active_rows'][i]),history3=int(e['enough_history'][i]),near_motion='',geometry_available=0)
    counts['all_stage_rows']+=1;counts[reason]+=1
    if query is None:return row
    target=next((x for x in GT.get(e['frame_number'],[]) if x['gt_id']==query),None)
    if target is None:counts['trusted_history_current_GT_absent']+=1;row['stop']='current_GT_absent';return row
    counts['trusted_query_current_GT_present']+=1
    rawpos=[x for x in allraw if labels[x['uid']]['state']=='matched' and labels[x['uid']]['gt_id']==query]
    if not rawpos:
        key='raw_match_ambiguous' if any(geo.iou(x['bbox_xywh_px'],target['bbox_xywh_px'])>=.5 for x in allraw) else 'no_any_raw_IoU05'
        counts[key]+=1;row['stop']=key;return row
    counts['trusted_positive_raw_present']+=1
    values={j:geo.label(query,labels[u]) for j,u in enumerate(e['candidate_UIDs'])}
    positive=[j for j,v in values.items() if v==1]
    if not positive:counts['positive_raw_not_in_this_stage']+=1;row['stop']='not_this_stage';return row
    counts['positive_in_stage']+=1
    if not e['enough_history'][i]:counts['positive_history_fewer3']+=1;row['stop']='history_fewer3';return row
    locations={j:k for k,(a,j) in enumerate(e['scored_locations']) if a==i}
    pos=[j for j in positive if j in locations]
    if not pos:counts['positive_rejected_motion_gate']+=1;row['stop']='motion_gate';return row
    counts['positive_in_motion_gate']+=1
    if not e['active_rows'][i]:counts['positive_gate_but_not_intervened']+=1
    else:counts['positive_actually_intervened']+=1
    neg=[j for j,v in values.items() if v==0 and j in locations]
    counts['unknown_scored_pairs']+=sum(values[j] is None for j in locations)
    if not neg:counts['no_known_negative_in_gate']+=1;row['stop']='no_known_negative';return row
    counts['both_known_classes_in_motion_gate']+=1
    logits=e['logits'];bestp=max(pos,key=lambda j:logits['motion'][locations[j]]);bestn=max(neg,key=lambda j:logits['motion'][locations[j]])
    candidate_scores=sorted((logits['motion'][k] for k in locations.values()),reverse=True)
    near=len(candidate_scores)>=2 and candidate_scores[0]-candidate_scores[1]<=cal['near_motion_gap']
    row['near_motion']=int(near);counts['near_motion_rows']+=int(near)
    for name in ('motion','pose','pose_off'):
        margin=max(logits[name][locations[j]] for j in pos)-max(logits[name][locations[j]] for j in neg)
        row[name+'_margin']=margin
    on,off=row['pose_margin'],row['pose_off_margin']
    row['pose_ranking_corrects']=int(on>0 and off<=0);row['pose_ranking_breaks']=int(on<=0 and off>0)
    for name in ('pose_ranking_corrects','pose_ranking_breaks'):counts[name]+=row[name]
    q=[e['quality_gates']['pose'][locations[j]] for j in pos]
    row['positive_gate_all_zero']=int(all(x==0 for x in q));counts['positive_gate_all_zero']+=row['positive_gate_all_zero']
    row['counterfactual_assignment_supported']=int(assignments['_comparable'])
    if assignments['_comparable']:
        for name in ('motion','pose','pose_off'):
            j=assignments[name].get(i);v=values.get(j)
            row[name+'_assigned_label']='unknown' if v is None else v
        row['assignment_changed_on_vs_off']=int(assignments['pose'].get(i)!=assignments['pose_off'].get(i))
        counts['assignment_changed_on_vs_off']+=row['assignment_changed_on_vs_off']
        counts['assignment_corrects_on_vs_off']+=int(row['pose_assigned_label']==1 and row['pose_off_assigned_label']==0)
        counts['assignment_breaks_on_vs_off']+=int(row['pose_assigned_label']==0 and row['pose_off_assigned_label']==1)
    else:counts['shadow_assignment_not_comparable_rows']+=1
    h=[index[u] for u in history];p=index[e['candidate_UIDs'][bestp]];n=index[e['candidate_UIDs'][bestn]]
    info=geo.shape_pair(h,p,n,cal['velocity_clip']);row['common_limbs']=info['common_joints']
    if not info['available']:counts['geometry_proxy_unavailable']+=1;return row
    counts['geometry_proxy_available']+=1;row['geometry_available']=1
    shuffled=geo.shape_pair([swapped[u] for u in history],swapped[p['uid']],swapped[n['uid']],cal['velocity_clip'])
    require(shuffled['available'] and shuffled['common_joints']==info['common_joints'],'交换改变支持点集')
    row['shape_swapped_observations']=sum(u in swapmap for u in history+[p['uid'],n['uid']])
    for name,v in info['margins'].items():row['geometry_'+name+'_margin']=v
    row['geometry_shuffled_temporal_margin']=shuffled['margins']['temporal']
    counts['geometry_clipped_joints']+=info['clipped_joints']
    counts['geometry_total_common_joints']+=info['common_joints']
    for subset in ('all',)+(('near',) if near else ())+(('active_near',) if near and e['active_rows'][i] else ()):
        counts[subset+'_geometry_rows']+=1
        for name in ('latest','mean','temporal','shuffled_temporal'):
            value=row['geometry_'+name+'_margin'];counts[subset+'_'+name+'_positive']+=int(value>0)
            counts[subset+'_'+name+'_tie']+=int(value==0)
        counts[subset+'_temporal_repairs_mean']+=int(info['margins']['temporal']>0 and info['margins']['mean']<=0)
        counts[subset+'_temporal_breaks_mean']+=int(info['margins']['temporal']<=0 and info['margins']['mean']>0)
    return row


def execute(config,output):
    import numpy as np
    import torch
    torch.set_num_threads(1)
    c,core,dep,prepared,control,jobs=context(config)
    _,rt,old,runtime,train,numeric,base,numbers=dep
    output=runtime.storage().physical_child(output,E);require(not output.exists(),'新阶段partial不覆盖，不隐式重放')
    output.mkdir(parents=True);start=time.time()
    state=dict(status='running_zero_update_information_chain',completed_units=[],active=None,new_optimizer_updates=0,test_read=False)
    def save_state():
        p=output/'state.json';tmp=output/'state.tmp';tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
    save_state();details=[];groups=defaultdict(Counter);sources={};calibrations={};models={};pools={};rowtotal=0;unique=set()
    from ultralytics.trackers.utils.matching import linear_assignment
    columns=['job_id','sequence','pool','fold','seed','frame','stage','track','history_status','stop','active','history3','near_motion','geometry_available','common_limbs',
        'positive_gate_all_zero','motion_margin','pose_margin','pose_off_margin','pose_ranking_corrects','pose_ranking_breaks',
        'motion_assigned_label','pose_assigned_label','pose_off_assigned_label','assignment_changed_on_vs_off','counterfactual_assignment_supported','shape_swapped_observations',
        'geometry_latest_margin','geometry_mean_margin','geometry_temporal_margin','geometry_shuffled_temporal_margin']
    try:
        with gzip.open(output/'all_stage_rows.csv.gz','xt',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,columns);writer.writeheader()
            for job in sorted(jobs,key=lambda j:(j['original']['sequence'],j['job_id'])):
                o=job['original'];seq=o['sequence'];state['active']=job['job_id'];save_state()
                if seq not in sources:
                    s=prepared['sources'][seq];frames=core.rows(checked(s['source']['cache']));labels=read(checked(s['labels']))['labels'];GT,_=rt.load_gt(old['sources'][seq])
                    index={d['uid']:d for frame in frames for d in frame['detections']};swapped,swapmap,reasons=geo.same_frame_swaps(frames)
                    sources[seq]=(frames,labels,GT,index,swapped,swapmap,reasons)
                    with (output/(seq+'_causal_swap_index.json')).open('x',encoding='utf-8') as q:json.dump(dict(mapping=swapmap,unchanged_reasons=reasons,GT_read=False),q,ensure_ascii=False)
                frames,labels,GT,index,swapped,swapmap,reasons=sources[seq];mkey=(o['fold'],o['seed'],o['pool'])
                if mkey not in models:
                    model,adapter,binding,_=rt.model_for_job(old,runtime,train,numeric,base,numbers,job['reference_motion']);model.eval();models[mkey]=(model,adapter,binding)
                    if o['fold'] not in pools:pools[o['fold']]=core.rows(checked(train['folds'][o['fold']]['real_pool']))
                    pool=pools[o['fold']];require(len(pool)==1000 and all(w['domain']=='real' and w['game']!=o['fold'] for w in pool),'只允许本fold基础trainR')
                    calibrations['/'.join(map(str,mkey))]=calibrate(pool,model,adapter,numeric.features,torch)
                cal=calibrations['/'.join(map(str,mkey))]
                receipt_path=control/'runs'/job['job_id']/'tracking/receipt.json';receipt=read(receipt_path)
                require(receipt['status']=='complete' and receipt['job']==job and receipt['GT_read'] is False,'原trace收据不符')
                trace=checked(receipt['trace']);count=Counter();maximum_cost_delta=0.
                with gzip.open(trace,'rt',encoding='utf-8') as stream:
                    for line in stream:
                        e=json.loads(line);require(e['GT_read'] is False,'旧模型曾输入GT');count['stage_calls']+=1
                        assignments,delta=geo.assignment_context(e,np,torch,linear_assignment)
                        maximum_cost_delta=max(maximum_cost_delta,delta)
                        count['shadow_actual_cost_nonexact_events']+=int(delta!=0.)
                        count['shadow_motion_assignment_exact_events']+=int(assignments['_comparable'])
                        count['shadow_motion_assignment_mismatch_events']+=int(not assignments['_comparable'])
                        for i,h in enumerate(e['history_UIDs']):
                            row=classify_row(e,i,labels,GT,frames[e['frame_number']-1]['detections'],index,assignments,cal,swapped,swapmap,count)
                            row.update(job_id=job['job_id'],sequence=seq,pool=o['pool'],fold=o['fold'],seed=o['seed']);writer.writerow(row);rowtotal+=1
                            signature=(seq,e['frame_number'],e['stage'],h,e['candidate_UIDs'])
                            unique.add(hashlib.sha256(json.dumps(signature,separators=(',',':')).encode()).digest())
                            j=assignments['motion'].get(i)
                            if j is not None:
                                count['reference_stage_assigned_rows']+=1
                                count['reference_assignment_agrees_endframe_UID']+=int(e['chosen_raw_UID'][i]==e['candidate_UIDs'][j])
                key=o['pool']+'/'+('external' if seq in rt.EXTERNAL else 'old_heldout');groups[key].update(count)
                details.append(dict(job=job,counts=dict(count),trace=receipt['trace'],receipt=ref(receipt_path),calibration_key='/'.join(map(str,mkey)),maximum_shadow_actual_cost_delta=maximum_cost_delta))
                state['completed_units'].append(job['job_id']);state['active']=None;save_state()
                print(json.dumps(dict(completed=len(details),total=54,sequence=seq,rows=count['all_stage_rows'],elapsed_sec=round(time.time()-start,1))),flush=True)
        result=dict(schema='pose_information_chain_complete_v1',status='complete54_information_chain_zero_updates_not_new_tracking_or_training',
            config=ref(config),parameters=PARAMETERS,source_units=54,groups={k:dict(v) for k,v in groups.items()},details=details,
            all_stage_rows=ref(output/'all_stage_rows.csv.gz'),stage_rows=rowtotal,unique_state_row_signatures=len(unique),calibrations=calibrations,
            source_inventory_reused=prepared['inventory'],causal_swap_coverage={seq:dict(raw_observations=len(v[3]),swapped=len(v[5]),unchanged=dict(Counter(v[6].values()))) for seq,v in sources.items()},
            new_optimizer_updates=0,new_detector_or_Pose_inference=False,new_free_tracking=False,GT_only_posthoc=True,test_read=False,
            manual_keypoint_truth_available=False,quality_manual_review_complete=False,
            limitations=['geometry distances on common strongest-motion known positive/negative are proxies, not trained T or AssA',
                'global reassignment is conditional on fixed strong-motion states, not a new free trajectory',
                'actual reference costs retained; all-scored shadow sigmoid and enabled-only sigmoid may differ in FP32; assignment mismatches explicitly unsupported',
                'rows repeat stages/models; unique signatures are still not independent matches',
                'gate reused from original inputs; no shape-dependent re-gating; no claimed frozen-gate learned-shuffle logits',
                'unknown/mixed histories and unresolved labels kept; common-point subsets are conditional',
                'same-frame donor may keep same identity unknowingly; no GT used to select donors',
                'five observed development matches only; neither seven-match results nor sealed test used to tune'])
        with (output/'report.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
        state.update(status=result['status'],active=None,report=ref(output/'report.json'));save_state()
        return dict(status=result['status'],source_units=54,stage_rows=rowtotal,groups=result['groups'])
    except BaseException as error:
        state.update(status='failed_preserved_no_implicit_replay',error=repr(error));save_state();raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true')
    a=p.parse_args();os.environ['CUDA_VISIBLE_DEVICES']='-1'
    if a.execute:print(json.dumps(execute(a.config,a.output),ensure_ascii=False))
    else:
        c,core,dep,prepared,control,jobs=context(a.config)
        require(not a.output.exists(),'已有输出或未知partial');print(json.dumps(dict(status='readonly54_information_chain_preflight',units=len(jobs),optimizer_updates=0,test_read=False)))
