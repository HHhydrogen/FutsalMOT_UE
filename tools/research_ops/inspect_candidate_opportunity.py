"""从既有共同状态trace审查候选介入机会；仅行内代理，不冒充自由追踪收益。"""
import argparse
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
import sys


def require(ok,message):
    if not ok:raise ValueError(message)


def inspect(config,amplitude_complete,output):
    cfg=json.loads(config.read_text(encoding='utf-8'));bundle=Path(cfg['bundle'])
    require(bundle.parent==Path('D:/projects/FutsalMOT_Research/code'),'必须冻结机制来源')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    import pose_mechanism_analyze as analyzer
    core=analyzer.core;_,rt,old,runtime,*_=core.validate(config)
    completed=core.read(amplitude_complete);require(completed['status']=='complete108_CPU_amplitude_probe_source_metrics_and_exit_verified','幅度阶段未闭合')
    mechanism=core.read(Path('D:/projects/FutsalMOT_Research/pose/pose_mechanism_a01/diagnostics_complete_root_a01.json'))
    require(mechanism['status']=='complete162_diagnostics_sources_results_and_process_exit_verified','共同状态未闭合')
    inputs=core.read(core.checked(cfg['inputs']));jobs=[j for j in cfg['jobs'] if j['kind']=='common_state'];groups=defaultdict(Counter);details=[]
    control=config.parents[1]/'control_a01'
    for job in jobs:
        seq=job['original']['sequence'];labels=core.read(core.checked(inputs['sources'][seq]['labels']))['labels'];GT,_=rt.load_gt(old['sources'][seq]);counts=Counter()
        receipt=core.read(control/'runs'/job['job_id']/'tracking/receipt.json');trace=core.checked(receipt['trace'])
        with gzip.open(trace,'rt',encoding='utf-8') as stream:
            for line in stream:
                e=json.loads(line);locations={tuple(v):k for k,v in enumerate(e['scored_locations'])};threshold=.8 if e['stage']==0 else .7
                for i,h in enumerate(e['history_UIDs']):
                    if e['active_rows'][i] or not e['enough_history'][i]:continue
                    counts['nonintervened_history3_stage_rows']+=1;identity,reason=analyzer.query_identity(h,labels);counts[reason]+=1
                    if identity is None:continue
                    if identity not in {g['gt_id'] for g in GT.get(e['frame_number'],[])}:counts['current_GT_absent']+=1;continue
                    counts['trusted_query_present']+=1
                    values={j:analyzer.pair_label(identity,labels[u]) for j,u in enumerate(e['candidate_UIDs'])}
                    accepted=[j for j in range(len(values)) if (i,j) in locations]
                    positives=[j for j,v in values.items() if v==1]
                    if positives:
                        counts['positive_raw_in_stage']+=1
                        if not any(j in accepted for j in positives):counts['positive_but_none_in_motion_gate']+=1
                    else:counts['no_trusted_positive_raw_in_stage']+=1
                    # 下列只是行内最小成本/最大分数代理，未运行全局分配或新自由轨迹。
                    bbox=min(range(len(values)),key=lambda j:e['bbox_cost'][i][j]) if values else None
                    bbox=bbox if bbox is not None and e['bbox_cost'][i][bbox]<=threshold else None
                    bb_label=values.get(bbox)
                    counts['bbox_row_proxy_unaccepted_or_unknown' if bb_label is None else ('bbox_row_proxy_true' if bb_label else 'bbox_row_proxy_wrong')]+=1
                    for model in ('pose','pose_off','motion_residual'):
                        best=max(accepted,key=lambda j:e['logits'][model][locations[(i,j)]]) if accepted else None
                        best=best if best is not None and e['logits'][model][locations[(i,best)]]>=0 else None
                        label=values.get(best)
                        counts[model+'_proxy_unaccepted_or_unknown' if label is None else model+('_proxy_true' if label else '_proxy_wrong')]+=1
                        if bb_label==0 and label==1:counts[model+'_proxy_improves_known_wrong_bbox']+=1
                        if bb_label==1 and label==0:counts[model+'_proxy_breaks_known_true_bbox']+=1
                        if bb_label==1 and best is None:counts[model+'_proxy_discards_true_bbox']+=1
                    known_pos=[locations[(i,j)] for j in accepted if values[j]==1];known_neg=[locations[(i,j)] for j in accepted if values[j]==0]
                    counts['unknown_scored_candidate_pairs']+=sum(values[j] is None for j in accepted)
                    if known_pos and known_neg:
                        counts['both_known_classes_in_newly_eligible_row']+=1
                        margin=lambda name:max(e['logits'][name][k] for k in known_pos)-max(e['logits'][name][k] for k in known_neg)
                        on,off=margin('pose'),margin('pose_off');counts['Pose_corrects_vs_own_off']+=int(on>0 and off<=0);counts['Pose_breaks_vs_own_off']+=int(on<=0 and off>0)
        key=job['original']['pool']+'/'+('external' if seq in rt.EXTERNAL else 'old_heldout');groups[key].update(counts);details.append(dict(job=job,counts=dict(counts),trace=receipt['trace']))
    output=runtime.storage().physical_child(output,core.V);require(not output.exists(),'机会审查partial不覆盖');output.mkdir(parents=True)
    result=dict(schema='candidate_intervention_opportunity_v1',status='complete54_existing_trace_opportunity_only_no_new_policy_evaluation',
        mechanism_protocol=core.ref(config),amplitude_completion=core.ref(amplitude_complete),source_code=core.ref(__file__),groups={k:dict(v) for k,v in groups.items()},details=details,
        optimizer_updates=0,GT_only_posthoc=True,new_policy_free_tracking=False,test_read=False,
        limitations=['rowwise proxy ignores global assignment and later histories, not AssA or a policy gain',
            'unknown/ambiguous histories and labels retained in counts','all five matches observed; rows repeat models and stages',
            'original coefficient0.5 shadows reused; no mixing with amplitude2 outcomes'])
    with (output/'report.json').open('x',encoding='utf-8') as f:f.write(core.canonical(result)+'\n')
    return dict(status=result['status'],groups=result['groups'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','amplitude-complete','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(inspect(a.config,a.amplitude_complete,a.output),ensure_ascii=False))
