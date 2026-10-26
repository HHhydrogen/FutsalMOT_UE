"""v10全部253追踪比较；两新比赛为主，三原留一为次，不挑seed/阈值。"""
import argparse
import csv
from collections import defaultdict
from statistics import mean
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import v10_tracking_runtime as rt
METRICS=('AssA','HOTA','IDF1','DetA','MOTA')


def paired_report(pairs):
    rt.require(pairs,'比较不得为空')
    means={k:mean(p['delta_pp'][k] for p in pairs) for k in METRICS}
    seeds={str(s):mean(p['delta_pp']['AssA'] for p in pairs if p['seed']==s) for s in (20261024,20261025,20261026)}
    matches={seq:{k:mean(p['delta_pp'][k] for p in pairs if p['sequence']==seq) for k in METRICS} for seq in sorted({p['sequence'] for p in pairs})}
    return dict(mean_delta_pp=means,seed_AssA_delta_pp=seeds,match_delta_pp=matches,pairs=pairs,
                negative_AssA_cells=sum(p['delta_pp']['AssA']<0 for p in pairs))


def primary_gate(report):
    d=report['mean_delta_pp'];seed=report['seed_AssA_delta_pp'];matches=report['match_delta_pp']
    rt.require(set(matches)==set(rt.EXTERNAL),'主门槛必须两新比赛')
    conditions=dict(AssA_mean_at_least_half_pp=d['AssA']>=.5,at_least_two_seeds_positive=sum(x>0 for x in seed.values())>=2,
        both_external_matches_nonnegative=all(x['AssA']>=0 for x in matches.values()),HOTA_nonnegative=d['HOTA']>=0,IDF1_drop_at_most_half_pp=d['IDF1']>=-.5)
    return dict(passed=all(conditions.values()),conditions=conditions)


def analyze(config,control,output):
    cfg,runtime,train,numeric,base,old=rt.validate_config(config);control=Path(control);state=rt.read(control/'driver_state.json')
    rt.require(len(state['completed_tracking'])==253,'全部253项未齐，不筛结果')
    result_rows=[];indexed={}
    for job in cfg['tracking_matrix']:
        path=control/'runs'/job['job_id']/'metric/report.json';report=rt.read(path)
        rt.require(report['status']=='complete' and report['job']==job and report['protocol_sha256']==rt.sha(config),'评价身份/矩阵不同')
        metrics=report['summary'][job['sequence']]['metrics_percent']
        record=dict(job=job,metrics=metrics,recovery=report['recovery']['overall'],report=dict(path=str(path),sha256=rt.sha(path)))
        key=(job['kind'],job.get('pool'),job.get('method'),job.get('fold'),job.get('seed'),job['sequence'],job['mode'])
        rt.require(key not in indexed,'重复比较身份');indexed[key]=record;result_rows.append(record)
    def find(kind,pool,method,fold,seed,sequence,mode='learned'):
        return indexed[(kind,pool,method,fold,seed,sequence,mode)]
    def differences(method,pool,reference,domain):
        pairs=[]
        for fold in ('game4','game6','game9'):
            sequences=list(rt.EXTERNAL) if domain=='external' else [next(s for s,f in rt.OLD.items() if f==fold)]
            for seed in (20261024,20261025,20261026):
                for sequence in sequences:
                    target=find('new_RS',pool,method,fold,seed,sequence)
                    if reference in ('motion','motion_residual'):ref=find('new_RS',pool,reference,fold,seed,sequence)
                    elif reference=='R':ref=find('pure_R',None,method,fold,seed,sequence)
                    elif reference.startswith('PT_'):ref=find('PT',None,None,None,None,sequence,reference)
                    elif reference=='balanced':ref=find('new_RS','balanced',method,fold,seed,sequence)
                    else:raise ValueError(reference)
                    pairs.append(dict(fold=fold,seed=seed,sequence=sequence,target=target['job']['job_id'],reference=ref['job']['job_id'],
                        delta_pp={k:target['metrics'][k]-ref['metrics'][k] for k in METRICS},
                        recovery_rate_target=target['recovery']['recovery_rate'],recovery_rate_reference=ref['recovery']['recovery_rate']))
        return paired_report(pairs)
    comparisons={}
    for domain in ('external','old_heldout'):
        for pool in ('balanced','hard_enriched'):
            for reference in ('motion','motion_residual'):
                key=f'{domain}/{pool}/gated-minus-{reference}';comparisons[key]=differences('gated',pool,reference,domain)
            for method in ('motion','motion_residual','gated'):
                for reference in ('R','PT_bbox','PT_static_pose'):
                    comparisons[f'{domain}/{pool}/{method}-minus-{reference}']=differences(method,pool,reference,domain)
        for method in ('motion','motion_residual','gated'):
            comparisons[f'{domain}/hard-minus-balanced/{method}']=differences(method,'hard_enriched','balanced',domain)
    gates={pool:primary_gate(comparisons[f'external/{pool}/gated-minus-motion']) for pool in ('balanced','hard_enriched')}
    output=runtime.storage().physical_child(output,rt.V);rt.require(not output.exists(),'分析partial不覆盖');output.mkdir(parents=True)
    value=dict(schema='v10_complete_five_match_analysis_v1',status='complete_all253_tracking_comparisons',
        protocol_sha256=rt.sha(config),primary_scope='macro of two new matches; each match averages all three training folds and seeds',
        primary_gates=gates,comparisons=comparisons,all_results=result_rows,
        limitations=['two new matches are development validation, not final test or futsal generalization',
            'training fold and seed repetitions are not independent matches','RS has extra S computation and supervised pairs',
            'between-pool known pairs differ; within-pool methods share exact exposure','gap proxy is not physical occlusion',
            'all seeds, folds and negative cells retained; no best or threshold search'],test_read=False)
    (output/'report.json').write_text(rt.canonical(value)+'\n',encoding='utf-8')
    with (output/'all_tracking_metrics.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['kind','pool','method','fold','seed','sequence','mode',*METRICS,'gap_events','recovery_rate'])
        writer.writeheader()
        for row in result_rows:
            writer.writerow(dict({k:row['job'].get(k) for k in ('kind','pool','method','fold','seed','sequence','mode')},
                **{k:row['metrics'][k] for k in METRICS},gap_events=row['recovery']['total_events'],recovery_rate=row['recovery']['recovery_rate']))
    return dict(status=value['status'],primary_gates=gates)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(rt.canonical(analyze(a.config,a.control,a.output)))
