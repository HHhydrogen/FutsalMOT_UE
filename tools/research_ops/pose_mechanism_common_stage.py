"""读取活动冻结来源，独立汇总已齐的54项共同状态；不修改或重跑控制器。"""
import argparse
from collections import Counter
import hashlib
import gzip
import importlib.util
import json
from pathlib import Path
import sys


def active_summary(path, labels, analyzer):
    """只统计原motion真正启用学习干预的行/边，不让易样本掩盖困难候选。"""
    counts=Counter();margins=Counter();positive=Counter();gate_n=gate_zero=0;effect=0.;effect_n=0
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            e=json.loads(line);locations={tuple(v):k for k,v in enumerate(e['scored_locations'])}
            for i,history in enumerate(e['history_UIDs']):
                if not e['active_rows'][i] or not e['enough_history'][i]:continue
                counts['active_rows_history3']+=1
                identity,reason=analyzer.query_identity(history,labels);counts[reason]+=1
                if identity is None:continue
                known={j:analyzer.pair_label(identity,labels[u]) for j,u in enumerate(e['candidate_UIDs'])
                       if (i,j) in locations and e['enabled'][i][j]}
                counts['unknown_candidate_pairs']+=sum(x is None for x in known.values())
                pos=[locations[(i,j)] for j,v in known.items() if v==1];neg=[locations[(i,j)] for j,v in known.items() if v==0]
                for j in known:
                    k=locations[(i,j)];gate_n+=1;gate_zero+=int(e['quality_gates']['pose'][k]==0)
                    effect+=abs(e['logits']['pose'][k]-e['logits']['pose_off'][k]);effect_n+=1
                if not pos or not neg:counts['active_rows_without_both_known_classes']+=1;continue
                counts['active_ranking_rows_both_known_classes']+=1
                delta={name:max(v[k] for k in pos)-max(v[k] for k in neg) for name,v in e['logits'].items()}
                for name,value in delta.items():margins[name]+=value;positive[name]+=int(value>0)
                counts['Pose_improves_margin_vs_own_off']+=int(delta['pose']>delta['pose_off'])
                counts['Pose_reduces_margin_vs_own_off']+=int(delta['pose']<delta['pose_off'])
                counts['Pose_corrects_ranking_vs_own_off']+=int(delta['pose']>0 and delta['pose_off']<=0)
                counts['Pose_breaks_ranking_vs_own_off']+=int(delta['pose']<=0 and delta['pose_off']>0)
    n=counts['active_ranking_rows_both_known_classes']
    return dict(counts=dict(counts),gate=dict(observations=gate_n,zero=gate_zero,zero_fraction=gate_zero/gate_n if gate_n else None),
        residual_mean_absolute_logit=effect/effect_n if effect_n else None,
        ranking={name:dict(rows=n,positive_fraction=positive[name]/n,mean_margin=value/n) for name,value in margins.items()} if n else {})


def execute(config, control, output):
    cfg=json.loads(config.read_text(encoding='utf-8'));bundle=Path(cfg['bundle'])
    if bundle.parent!=Path('D:/projects/FutsalMOT_Research/code'):raise ValueError('诊断源码必须来自独立D bundle')
    manifest=json.loads(Path(cfg['bundle_manifest']['path']).read_text(encoding='utf-8'))
    for entry in manifest['files']:
        if hashlib.sha256((bundle/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('冻结诊断源码变化')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    import pose_mechanism_analyze as analyzer
    core=analyzer.core
    _,rt,old,runtime,*_=core.validate(config)
    state=core.read(control/'driver_state.json');completed={r['job']['job_id'] for r in state['completed']}
    jobs=[j for j in cfg['jobs'] if j['kind']=='common_state']
    core.require(len(jobs)==54 and all(j['job_id'] in completed for j in jobs),'共同状态54项尚未完成')
    inputs=core.read(core.checked(cfg['inputs']));details=[]
    for job in jobs:
        seq=job['original']['sequence'];folder=control/'runs'/job['job_id']/'tracking';receipt=core.read(folder/'receipt.json')
        core.require(receipt['job']==job and receipt['status']=='complete' and receipt['protocol_sha256']==core.sha(config),'共同记录身份不符')
        labels=core.read(core.checked(inputs['sources'][seq]['labels']))['labels'];GT,_=rt.load_gt(old['sources'][seq])
        trace=core.checked(receipt['trace'])
        details.append(dict(job=job,report=analyzer.summarize_trace(trace,labels,GT),
            active_report=active_summary(trace,labels,analyzer),receipt=core.ref(folder/'receipt.json')))
    groups={}
    for pool in ('balanced','hard_enriched'):
        for domain,sequences in (('external',rt.EXTERNAL),('old_heldout',rt.OLD)):
            selected=[d for d in details if d['job']['original']['pool']==pool and d['job']['original']['sequence'] in sequences]
            counters=Counter();gate_n=gate_zero=effect_n=0;effect_sum=0.;margin_sums=Counter();margin_n=Counter();margin_positive=Counter()
            for item in selected:
                r=item['report'];counters.update(r['counts']);g=r['quality_gate'];gate_n+=g['observations'];gate_zero+=g['zero']
                e=r['residual_absolute_logit_effect'];effect_n+=e['observations'];effect_sum+=(e['mean'] or 0)*e['observations']
                for name,m in r['margin'].items():
                    margin_sums[name]+=m['mean']*m['rows'];margin_n[name]+=m['rows'];margin_positive[name]+=m['positive_fraction']*m['rows']
            active_counts=Counter();active_positive=Counter();active_margin=Counter();active_n=Counter();active_gate_n=active_gate_zero=0;active_effect_n=0;active_effect_sum=0.
            for item in selected:
                r=item['active_report'];active_counts.update(r['counts']);active_gate_n+=r['gate']['observations'];active_gate_zero+=r['gate']['zero']
                active_effect_n+=r['gate']['observations'];active_effect_sum+=(r['residual_mean_absolute_logit'] or 0)*r['gate']['observations']
                for name,m in r['ranking'].items():
                    active_n[name]+=m['rows'];active_positive[name]+=m['positive_fraction']*m['rows'];active_margin[name]+=m['mean_margin']*m['rows']
            groups[pool+'/'+domain]=dict(model_sequence_units=len(selected),counts=dict(counters),
                gate=dict(observations=gate_n,zero=gate_zero,zero_fraction=gate_zero/gate_n if gate_n else None),
                residual_mean_absolute_logit=effect_sum/effect_n if effect_n else None,
                ranking={n:dict(rows=margin_n[n],positive_fraction=margin_positive[n]/margin_n[n],mean_margin=margin_sums[n]/margin_n[n]) for n in margin_n},
                active_only=dict(counts=dict(active_counts),gate=dict(observations=active_gate_n,zero=active_gate_zero),
                    residual_mean_absolute_logit=active_effect_sum/active_effect_n if active_effect_n else None,
                    ranking={n:dict(rows=active_n[n],positive_fraction=active_positive[n]/active_n[n],mean_margin=active_margin[n]/active_n[n]) for n in active_n}))
    output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'共同阶段报告partial不覆盖');output.mkdir(parents=True)
    result=dict(schema='pose_mechanism_common54_stage_v1',status='complete54_common_state_stage_free_counterfactual_pending',
        config=core.ref(config),source_code=core.ref(__file__),common_units=54,groups=groups,details=details,
        common_state_reference='identical_strong_motion_histories_and_candidates_MOT_and_audit_exact',
        counterfactual_complete=False,GT_only_posthoc=True,optimizer_updates=0,test_read=False,
        limitations=['rows/pairs repeat model states and stages; not independent matches',
                     'same-state ranking is not free-tracking improvement','all five matches are observed development data'])
    with (output/'report.json').open('x',encoding='utf-8') as stream:stream.write(core.canonical(result)+'\n')
    return dict(status=result['status'],groups=groups)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.config,a.control,a.output),ensure_ascii=False))
