"""七比赛完整A/B/C与PT配对差值和区间；全结果保留，不作等效/非劣效判定。"""
import argparse
import csv
from collections import defaultdict
import math
from pathlib import Path
from statistics import mean
import sys
sys.path.insert(0,str(Path(__file__).parent))
import substitution_tracking_runtime as rt
from substitution_paired_analysis import effect_intervals
METRICS=('AssA','HOTA','IDF1','DetA','MOTA')

def paired_cells(results):
    """不允许静默丢失一组、seed、fold或比赛；PT单次结果与同场全部模型配对。"""
    index={}
    for record in results:
        job=record['job'];key=job['job_id'];rt.require(key not in index,'重复评价单元')
        rt.require(all(math.isfinite(record['metrics'][k]) for k in METRICS),'非有限指标不能跳过')
        index[key]=record
    expected=rt.tracking_matrix();rt.require(set(index)=={j['job_id'] for j in expected}
        and all(index[j['job_id']]['job']==j for j in expected),'392完整矩阵不齐，不形成部分汇总')
    learned={(j['group'],j['method'],j['fold'],j['seed'],j['sequence']):index[j['job_id']] for j in expected if j['kind']=='learned'}
    pt={(j['mode'],j['sequence']):index[j['job_id']] for j in expected if j['kind']=='PT'}
    comparisons={}
    for method in rt.METHODS:
        for target,reference in (('B','A'),('C','A'),('B','C')):
            key=method+'/'+target+'-minus-'+reference;comparisons[key]=[]
            for seq in rt.MATCHES:
                for fold in rt.FOLDS:
                    for seed in rt.SEEDS:
                        comparisons[key].append((fold,seed,seq,learned[target,method,fold,seed,seq],learned[reference,method,fold,seed,seq]))
    for group in rt.GROUPS:
        key=group+'/gated-minus-motion';comparisons[key]=[]
        for seq in rt.MATCHES:
            for fold in rt.FOLDS:
                for seed in rt.SEEDS:
                    comparisons[key].append((fold,seed,seq,learned[group,'gated',fold,seed,seq],learned[group,'motion',fold,seed,seq]))
        for method in rt.METHODS:
            for mode in ('PT_bbox','PT_static_pose'):
                key=group+'/'+method+'-minus-'+mode;comparisons[key]=[]
                for seq in rt.MATCHES:
                    for fold in rt.FOLDS:
                        for seed in rt.SEEDS:
                            comparisons[key].append((fold,seed,seq,learned[group,method,fold,seed,seq],pt[mode,seq]))
    result={}
    for key,pairs in comparisons.items():
        rt.require(len(pairs)==63,'每个对照必须7比赛×9训练单元')
        result[key]=[dict(fold=f,seed=s,match=seq,target=t['job']['job_id'],reference=r['job']['job_id'],
            delta_pp={k:t['metrics'][k]-r['metrics'][k] for k in METRICS}) for f,s,seq,t,r in pairs]
    return result

def intervals(cells):
    rt.require(len(cells)==63 and {(p['match'],p['fold'],p['seed']) for p in cells}==
        {(s,f,z) for s in rt.MATCHES for f in rt.FOLDS for z in rt.SEEDS},'配对重复/缺失')
    return {k:effect_intervals({s:mean(p['delta_pp'][k] for p in cells if p['match']==s) for s in rt.MATCHES}) for k in METRICS}

def analyze(config,control,output):
    c,dep,cr,cc=rt.validate_config(config);control=Path(control);state=rt.read(control/'driver_state.json')
    rt.require(len(state['completed_tracking'])==392 and [x['job'] for x in state['completed_tracking']]==c['tracking_matrix'],'实际392全部任务未齐')
    reports={x['job']['job_id']:x for x in state['completed_tracking']};records=[]
    for job in c['tracking_matrix']:
        p=control/'runs'/job['job_id']/'metric/report.json';report=rt.read(p)
        rt.require(rt.sha(p)==reports[job['job_id']]['report_sha256'] and report['status']=='complete' and report['job']==job
            and report['protocol_sha256']==rt.sha(config) and report['predictions_GT_filtered'] is False,'原评价身份/状态被改变')
        records.append(dict(job=job,metrics=report['summary'][job['sequence']]['metrics_percent'],
            recovery=report['recovery']['overall'],report=rt.ref(p)))
    cells=paired_cells(records);summaries={key:intervals(value) for key,value in cells.items()}
    output=dep[3].storage().physical_child(output,rt.EXP);rt.require(not output.exists(),'分析partial不得覆盖');output.mkdir(parents=True)
    with (output/'all_results.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['job_id','kind','group','method','fold','seed','sequence','mode',*METRICS,'gap_events','recovery_rate','report_path','report_sha256']);writer.writeheader()
        for record in records:
            job=record['job'];writer.writerow(dict({k:job.get(k) for k in ('job_id','kind','group','method','fold','seed','sequence','mode')},
                **record['metrics'],gap_events=record['recovery']['total_events'],recovery_rate=record['recovery']['recovery_rate'],
                report_path=record['report']['path'],report_sha256=record['report']['sha256']))
    with (output/'all_paired_cells.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['comparison','match','fold','seed','target','reference',*METRICS]);writer.writeheader()
        for key,pairs in cells.items():
            for p in pairs:writer.writerow(dict(comparison=key,**{k:v for k,v in p.items() if k!='delta_pp'},**p['delta_pp']))
    report=dict(schema='seven_match_complete_ABC_paired_intervals_v1',status='complete392_all_results_and_paired_intervals',
        protocol_sha256=rt.sha(config),analysis_plan=c['analysis_plan'],primary_method='motion',secondary_method='gated',
        registered_contrasts=['B-A','C-A','B-C'],primary_metric='AssA',PT_comparisons='secondary_descriptive',
        comparisons=summaries,all_results_csv=rt.ref(output/'all_results.csv'),all_paired_cells_csv=rt.ref(output/'all_paired_cells.csv'),
        all_original_reports=[r['report'] for r in records],all_seeds_folds_and_negative_results_retained=True,
        formal_equivalence_or_noninferiority=False,performance_margin=None,test_read=False,
        limitations=['conditional on fixed training panel; folds/seeds are not independent matches',
            'seven short convenience clips; approximate independence/normality; not full-match random sampling or futsal generalization',
            'descriptive unadjusted intervals; no significance or equivalence from interval including zero',
            'all models share detections; GT only metrics, gap is not physical occlusion',
            'C uses4000R, A/B3000R with B extra1000S; windows not independent frames, cost or equal FLOPs'])
    (output/'report.json').write_text(rt.canonical(report)+'\n',encoding='utf-8')
    return dict(status=report['status'],tracking_jobs=392,paired_comparison_families=len(cells),metrics=len(METRICS))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();print(rt.canonical(analyze(a.config,a.control,a.output)))
