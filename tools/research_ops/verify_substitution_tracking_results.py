"""独立核验392项来源/全量CSV/配对差值与描述性区间；不重推理或重算TrackEval。"""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/real_substitution_a01'
METRICS=('AssA','HOTA','IDF1','DetA','MOTA')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def close(a,b):return math.isfinite(a) and math.isfinite(b) and abs(a-b)<=1e-8

def verify_interval(value,deltas,matches):
    """独立numpy/scipy重算七比赛区间；数值容差仅用于序列化核验，不是性能界限。"""
    import numpy as np
    from scipy.stats import t
    require(set(deltas)==set(matches) and len(matches)==7,'区间必须七个比赛单位')
    x=np.asarray([deltas[s] for s in matches],dtype=float);avg=float(x.mean());sd=float(x.std(ddof=1));half=float(t.ppf(.975,6))*sd/math.sqrt(7)
    require(np.isfinite(x).all() and value['n_independent_matches']==7 and value['margin'] is None
        and value['formal_equivalence_or_noninferiority_test'] is False
        and len(value['Student_t_95CI'])==len(value['percentile_match_bootstrap_95CI'])==2
        and set(value['leave_one_match_out_mean'])==set(matches),'区间不得缺失/扩大样本量/增设性能通过界限')
    require(close(value['mean_delta_pp'],avg) and close(value['match_sample_SD_pp'],sd)
        and all(close(a,b) for a,b in zip(value['Student_t_95CI'],[avg-half,avg+half])),'Student t区间/均值不符')
    draws=np.random.default_rng(20261027).integers(0,7,size=(10000,7));limits=np.quantile(x[draws].mean(axis=1),[.025,.975])
    require(all(close(a,b) for a,b in zip(value['percentile_match_bootstrap_95CI'],limits))
        and set(value['match_deltas_pp'])==set(matches)
        and all(close(value['match_deltas_pp'][s],deltas[s]) for s in matches)
        and all(close(value['leave_one_match_out_mean'][s],float(np.delete(x,i).mean())) for i,s in enumerate(matches)),'固定bootstrap/逐场留一不符')

def execute(config,control,output):
    config=Path(config);c=read(config);bundle=Path(c['bundle']);require(bundle.parent==R/'code','追踪bundle身份不同')
    require(sha(c['bundle_manifest']['path'])==c['bundle_manifest']['sha256'],'追踪代码清单变化')
    for e in read(c['bundle_manifest']['path'])['files']:require(sha(bundle/e['path'])==e['sha256'],'冻结追踪源码变化')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    import substitution_tracking_runtime as rt
    c,dep,cr,cc=rt.validate_config(config);control=dep[3].storage().physical_child(control,EXP);output=dep[3].storage().physical_child(output,EXP)
    require(not output.exists(),'独立核验输出已存在，不覆盖')
    state=read(control/'driver_state.json');require(state['status']=='complete392_tracking_and_paired_intervals'
        and state['active'] is None and len(state['completed_tracking'])==392
        and [x['job'] for x in state['completed_tracking']]==c['tracking_matrix'],'392终态/全部任务未齐')
    cmd="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',cmd],capture_output=True,text=True,encoding='utf-8',errors='replace');require(p.returncode==0,'CIM身份查询失败')
    processes=json.loads(p.stdout or '[]');processes=[processes] if isinstance(processes,dict) else processes
    blocked=[x for x in processes if x['Name'].lower().startswith('unrealeditor') or any(w in (x.get('CommandLine') or '') for w in
        ('substitution_tracking_control.py','substitution_tracking_jobs.py','substitution_tracking_analysis.py','substitution_validation_predictions.py'))]
    require(not blocked,'相关生产者/launcher尚未实际退出：'+str(blocked))
    registry=read(rt.checked(c['registry_receipt']));results={};source_counts=registry['sequence_event_counts']
    for entry in state['completed_tracking']:
        job=entry['job'];folder=control/'runs'/job['job_id'];tr=read(folder/'tracking/receipt.json');report=read(folder/'metric/report.json')
        require(sha(folder/'metric/report.json')==entry['report_sha256'] and tr['status']==report['status']=='complete'
            and tr['job']==report['job']==job and tr['protocol_sha256']==report['protocol_sha256']==sha(config)
            and tr['cache']==c['sources'][job['sequence']]['cache']
            and tr['evaluation_GT_annotations_loaded'] is False and tr['GT_used_for_tracking'] is False
            and report['tracking_receipt_sha256']==sha(folder/'tracking/receipt.json')
            and sha(folder/'tracking/data'/(job['sequence']+'.txt'))==tr['mot_sha256'],'实际评价/MOT/来源或GT边界变化')
        require(report['predictions_GT_filtered'] is False and report['DO_PREPROC'] is False and report['GT_ID0_original'] is True
            and report['GT_rows']==registry['GT_row_counts'][job['sequence']]
            and report['recovery']['overall']['total_events']==source_counts[job['sequence']],'评价GT/全事件分母/预测保留不符')
        if not source_counts[job['sequence']]:require(report['recovery']['overall']['recovery_rate'] is None,'零分母必须null')
        for name,classes in report['raw_results'].items():
            count=classes['pedestrian']['Count'];require(count['Dets']==tr['tracked_rows'] and count['GT_Dets']==report['GT_rows'],'TrackEval实际行丢失')
            if name==job['sequence']:require(count['Frames']==c['sources'][job['sequence']]['frames'],'单序列帧数不符')
            else:require(name=='COMBINED_SEQ','未知评价范围')
        results[job['job_id']]=dict(job=job,metrics=report['summary'][job['sequence']]['metrics_percent'],
            recovery=report['recovery']['overall'],report=ref(folder/'metric/report.json'))
    analysis=control/'analysis_a01';report=read(analysis/'report.json')
    require(report['status']=='complete392_all_results_and_paired_intervals' and report['protocol_sha256']==sha(config)
        and report['formal_equivalence_or_noninferiority'] is False and report['performance_margin'] is None
        and report['primary_method']=='motion' and report['secondary_method']=='gated'
        and report['registered_contrasts']==['B-A','C-A','B-C'],'分析身份或事前方案被改变')
    rt.checked(report['all_results_csv']);rt.checked(report['all_paired_cells_csv'])
    with (analysis/'all_results.csv').open(encoding='utf-8-sig',newline='') as f:csv_results=list(csv.DictReader(f))
    require(len(csv_results)==len({x['job_id'] for x in csv_results})==392,'全部结果CSV遗漏/重复')
    for row in csv_results:
        original=results[row['job_id']];require(row['report_sha256']==original['report']['sha256']
            and row['report_path']==original['report']['path']
            and all(row[k]==str(original['job'].get(k) if original['job'].get(k) is not None else '') for k in ('kind','group','method','fold','seed','sequence','mode'))
            and int(row['gap_events'])==original['recovery']['total_events']
            and (row['recovery_rate']=='' if original['recovery']['recovery_rate'] is None else close(float(row['recovery_rate']),original['recovery']['recovery_rate']))
            and all(close(float(row[k]),original['metrics'][k]) for k in METRICS),'CSV原指标/模型分组/来源或分母被改写')
    expected={m+'/'+a+'-minus-'+b for m in rt.METHODS for a,b in (('B','A'),('C','A'),('B','C'))}
    expected|={g+'/gated-minus-motion' for g in rt.GROUPS}
    expected|={g+'/'+m+'-minus-'+p for g in rt.GROUPS for m in rt.METHODS for p in ('PT_bbox','PT_static_pose')}
    require(set(report['comparisons'])==expected and len(expected)==21,'比较类型被选择或增加')
    with (analysis/'all_paired_cells.csv').open(encoding='utf-8-sig',newline='') as f:pairs=list(csv.DictReader(f))
    require(len(pairs)==1323,'全21类×63配对单元不齐')
    seen=set();deltas={key:{metric:{s:[] for s in rt.MATCHES} for metric in METRICS} for key in expected}
    for row in pairs:
        key=row['comparison'];signature=(key,row['match'],row['fold'],int(row['seed']))
        require(key in expected and signature not in seen,'配对重复或未知对照');seen.add(signature)
        target,reference=(results[row[k]] for k in ('target','reference'));tj,rj=target['job'],reference['job']
        require(tj['sequence']==rj['sequence']==row['match'] and tj['fold']==row['fold'] and tj['seed']==int(row['seed']),'配对跨比赛/训练单元')
        if key.split('/')[0] in rt.METHODS:
            method,contrast=key.split('/');a,b=contrast.split('-minus-')
            require(tj['group']==a and rj['group']==b and tj['method']==rj['method']==method,'A/B/C配对对象错误')
        elif key.endswith('/gated-minus-motion'):
            require(tj['group']==rj['group']==key.split('/')[0] and tj['method']=='gated' and rj['method']=='motion','架构配对对象错误')
        else:
            group,tail=key.split('/');method,pt=tail.split('-minus-')
            require(tj['group']==group and tj['method']==method and rj['kind']=='PT' and rj['mode']==pt,'PT配对对象错误')
        if rj['kind']=='learned':require(rj['fold']==tj['fold'] and rj['seed']==tj['seed'],'配对训练seed/fold错误')
        for metric in METRICS:
            value=float(row[metric]);require(close(value,target['metrics'][metric]-reference['metrics'][metric]),'实际配对差值不同')
            deltas[key][metric][row['match']].append(value)
    for key in expected:
        for metric in METRICS:
            require(all(len(x)==9 for x in deltas[key][metric].values()),'每比赛必须完整9配对单元')
            verify_interval(report['comparisons'][key][metric],{s:sum(x)/9 for s,x in deltas[key][metric].items()},rt.MATCHES)
    output.parent.mkdir(parents=True,exist_ok=True)
    result=dict(status='complete392_sources_all_results_1323_pairs_105_intervals_and_exit_verified',config=ref(config),control_state=ref(control/'driver_state.json'),
        analysis=ref(analysis/'report.json'),jobs=392,paired_cells=1323,descriptive_intervals=105,independent_matches=7,
        producer_processes_absent=True,all_negative_results_retained=True,new_optimizer_updates=0,models_or_media_recomputed=False,
        equivalence_or_noninferiority_claim=False,test_read=False)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();os.environ['CUDA_VISIBLE_DEVICES']='-1';result=execute(a.config,a.control,a.output)
    print(json.dumps({k:result[k] for k in ('status','jobs','paired_cells','descriptive_intervals')},ensure_ascii=False))
