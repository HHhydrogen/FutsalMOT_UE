"""全部共同状态记录及固定权重消融汇总；GT只在完成推理后用于标签。"""
import argparse
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean
import sys
sys.path.insert(0,str(Path(__file__).parent))
import pose_mechanism_core as core


def query_identity(history,labels):
    values=[labels.get(u,{}) for u in history]
    if not values or any(v.get('state')!='matched' for v in values):return None,'unknown_history'
    ids={v['gt_id'] for v in values}
    return (next(iter(ids)),'trusted_consistent_history') if len(ids)==1 else (None,'mixed_identity_history')


def pair_label(query,candidate):
    if candidate['state'].startswith('unknown'):return None
    return int(candidate['state']=='matched' and candidate['gt_id']==query)


def summarize_trace(path,labels,GT):
    count=Counter();scores=defaultdict(list);gates=[];effects=[]
    current_gt={int(frame):{g['gt_id'] for g in items} for frame,items in GT.items()}
    positives=defaultdict(lambda:defaultdict(set))
    for uid,label in labels.items():
        if label['state']=='matched':positives[label['frame_number']][label['gt_id']].add(uid)
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            e=json.loads(line)
            count['stage_calls']+=1;locations={tuple(loc):k for k,loc in enumerate(e['scored_locations'])}
            for i,history in enumerate(e['history_UIDs']):
                count['all_stage_rows']+=1;identity,reason=query_identity(history,labels);count[reason]+=1
                if identity is None:continue
                if identity not in current_gt.get(e['frame_number'],set()):count['known_history_but_current_GT_absent']+=1;continue
                count['known_query_current_GT_present']+=1
                correct=[j for j,u in enumerate(e['candidate_UIDs']) if labels[u]['state']=='matched' and labels[u]['gt_id']==identity]
                if not positives[e['frame_number']].get(identity):count['no_trusted_positive_raw_current']+=1
                elif not correct:count['trusted_positive_raw_not_in_this_stage_candidates']+=1
                if correct:
                    count['rows_positive_in_stage']+=1
                    if not e['enough_history'][i]:count['positive_but_history_fewer3']+=1
                    if not any(e['motion_gate'][i][j] for j in correct):count['all_positive_rejected_by_motion_gate']+=1
                    if not e['active_rows'][i]:count['positive_but_row_not_intervened']+=1
                    if any(e['enabled'][i][j] for j in correct):count['positive_eligible_for_learned_decision']+=1
                chosen=e['chosen_raw_UID'][i]
                if chosen is not None:
                    state=labels.get(chosen,{})
                    if state.get('state')=='matched':count['reference_chosen_true' if state['gt_id']==identity else 'reference_chosen_other_GT']+=1
                    else:count['reference_chosen_unresolved_GT']+=1
                else:count['reference_no_chosen_raw_for_row']+=1
                known={j:pair_label(identity,labels[u]) for j,u in enumerate(e['candidate_UIDs']) if (i,j) in locations}
                count['scored_pairs_unknown_label']+=sum(v is None for v in known.values())
                pos=[locations[(i,j)] for j,v in known.items() if v==1];neg=[locations[(i,j)] for j,v in known.items() if v==0]
                for j,v in known.items():
                    k=locations[(i,j)]
                    if 'pose' in e['quality_gates']:gates.append(e['quality_gates']['pose'][k])
                    effects.append(abs(e['logits']['pose'][k]-e['logits']['pose_off'][k]))
                    if v is not None:count['known_positive_pairs' if v else 'known_negative_pairs']+=1
                if not pos or not neg:continue
                count['ranking_rows_both_known_classes']+=1
                margins={name:max(value[k] for k in pos)-max(value[k] for k in neg) for name,value in e['logits'].items()}
                for name,value in margins.items():scores[name].append(value);count[name+'_positive_ranking_margin']+=int(value>0)
                count['Pose_improves_margin_vs_own_off']+=int(margins['pose']>margins['pose_off'])
                count['Pose_reduces_margin_vs_own_off']+=int(margins['pose']<margins['pose_off'])
    return dict(counts=dict(count),margin={k:dict(mean=mean(v),rows=len(v),positive_fraction=sum(x>0 for x in v)/len(v)) for k,v in scores.items()},
        quality_gate=dict(observations=len(gates),zero=sum(x==0 for x in gates),mean=mean(gates) if gates else None),
        residual_absolute_logit_effect=dict(observations=len(effects),mean=mean(effects) if effects else None,zero=sum(x==0 for x in effects)),
        denominator='stage rows/pairs on fixed strong-motion histories; repeated model observations, not independent matches',
        GT_used_posthoc_only=True)


def analyze(config,control,output):
    cfg,rt,old,runtime,train,numeric,base,numbers=core.validate(config);control=Path(control)
    state=core.read(control/'driver_state.json');core.require(len(state['completed'])==162,'全部162诊断未齐')
    prepared=core.read(core.checked(cfg['inputs']));common=[];counterfactual=[]
    for job in cfg['jobs']:
        folder=control/'runs'/job['job_id'];receipt=core.read(folder/'tracking/receipt.json')
        core.require(receipt['status']=='complete' and receipt['job']==job and receipt['protocol_sha256']==core.sha(config),'独立诊断身份不符')
        original=job['original'];seq=original['sequence'];original_folder=Path(old['training_control']).parent/'tracking_control_a01/runs'/original['job_id']
        original_metric=core.read(original_folder/'metric/report.json')
        if job['kind']=='common_state':
            labels=core.read(core.checked(prepared['sources'][seq]['labels']))['labels'];GT,_=rt.load_gt(old['sources'][seq])
            report=summarize_trace(core.checked(receipt['trace']),labels,GT)
            common.append(dict(job=job,report=report,tracking_receipt=core.ref(folder/'tracking/receipt.json')))
        else:
            current=core.read(folder/'metric/report.json');metrics=current['summary'][seq]['metrics_percent'];reference=original_metric['summary'][seq]['metrics_percent']
            counterfactual.append(dict(job=job,metrics=metrics,original_metrics=reference,
                delta_vs_original_pp={k:metrics[k]-reference[k] for k in ('AssA','HOTA','IDF1','DetA','MOTA')},
                recovery=current['recovery']['overall'],original_recovery=original_metric['recovery']['overall'],
                current_metric=core.ref(folder/'metric/report.json'),original_metric=core.ref(original_folder/'metric/report.json')))
    aggregation={}
    for pool in ('balanced','hard_enriched'):
        for domain in ('external','old_heldout'):
            seqs=rt.EXTERNAL if domain=='external' else rt.OLD
            for condition in core.PARAMETERS['conditions']:
                selected=[x for x in counterfactual if x['job']['condition']==condition and x['job']['original']['pool']==pool and x['job']['original']['sequence'] in seqs]
                core.require(len(selected)==(18 if domain=='external' else 9),'全部seed/fold单元缺失')
                aggregation[f'{pool}/{domain}/{condition}']=dict(mean_delta_vs_original_pp={k:mean(x['delta_vs_original_pp'][k] for x in selected) for k in ('AssA','HOTA','IDF1')},
                    seed_AssA_delta={str(s):mean(x['delta_vs_original_pp']['AssA'] for x in selected if x['job']['original']['seed']==s) for s in (20261024,20261025,20261026)},
                    match_AssA_delta={q:mean(x['delta_vs_original_pp']['AssA'] for x in selected if x['job']['original']['sequence']==q) for q in sorted({x['job']['original']['sequence'] for x in selected})},
                    units=len(selected),negative_AssA_cells=sum(x['delta_vs_original_pp']['AssA']<0 for x in selected))
    counters=Counter();gate_n=gate_zero=effects_n=effects_zero=0;effects_sum=0.
    for row in common:
        report=row['report'];counters.update(report['counts']);gate_n+=report['quality_gate']['observations'];gate_zero+=report['quality_gate']['zero']
        effect=report['residual_absolute_logit_effect'];effects_n+=effect['observations'];effects_zero+=effect['zero'];effects_sum+=(effect['mean'] or 0)*effect['observations']
    output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'分析partial不覆盖');output.mkdir(parents=True)
    result=dict(schema='pose_mechanism_complete_diagnostics_v1',status='complete54_common108_free_diagnostics',protocol=core.ref(config),
        input_inventory=prepared['inventory'],common_state=common,common_counts=dict(counters),quality_gate=dict(observations=gate_n,zero=gate_zero),
        residual_effect=dict(observations=effects_n,zero=effects_zero,mean_absolute_logit=effects_sum/effects_n if effects_n else None),
        counterfactual=counterfactual,aggregates=aggregation,
        interpretation=['all histories/candidates for shadow scores are from identical strong-motion states',
            'pose_off is this jointly-trained gated model own motion branch, not independently-trained strong motion',
            'shape shuffle keeps masks/boxes but can change derived quality gate; coverage reported',
            'geometric validity is not keypoint accuracy; no manual keypoint truth supplied',
            'GT posthoc labels can be ambiguous; unresolved denominators retained','all five matches are observed development data'],
        official_v10_all_results_reference=core.ref(Path(old['training_control']).parent/'tracking_control_a01/analysis_a01/report.json'),
        new_optimizer_updates=0,GPU_used=False,test_read=False)
    with (output/'report.json').open('x',encoding='utf-8') as stream:stream.write(core.canonical(result)+'\n')
    return dict(status=result['status'],aggregates=aggregation,quality_gate=result['quality_gate'],residual_effect=result['residual_effect'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(core.canonical(analyze(a.config,a.control,a.output)))
