"""独立流式核对零更新信息链CSV/汇总及退出，不重跑模型或原追踪。"""
import argparse
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,re,subprocess
from pathlib import Path

R=Path('D:/projects/FutsalMOT_Research');E=R/'pose/pose_information_a01'


def require(ok,msg):
    if not ok:raise ValueError(msg)


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def ref(p):return dict(path=str(p),sha256=sha(p))


def is_producer(command):
    """按完整脚本文件名识别，verify_前缀不是生产者。"""
    return bool(re.search(r'[\\/]pose_information_chain[.]py(?:[ \"\t]|$)',command or '',re.I))


def tally(rows):
    """按所有CSV行独立累加，包含无信息、未知及负排名；不筛正值。"""
    allrows=Counter();known=defaultdict(Counter)
    for x in rows:
        job=x['job_id'];allrows[job]+=1;c=known[job]
        c[x['history_status']]+=1
        if x['pose_ranking_corrects']!='':c['pose_ranking_corrects']+=int(x['pose_ranking_corrects'])
        if x['pose_ranking_breaks']!='':c['pose_ranking_breaks']+=int(x['pose_ranking_breaks'])
        if x['geometry_available']=='1':
            c['geometry_proxy_available']+=1
            subsets=['all']+(['near'] if x['near_motion']=='1' else [])+(['active_near'] if x['near_motion']=='1' and x['active']=='1' else [])
            for s in subsets:
                c[s+'_geometry_rows']+=1
                for name in ('latest','mean','temporal','shuffled_temporal'):
                    margin=float(x['geometry_'+name+'_margin']);c[s+'_'+name+'_positive']+=int(margin>0);c[s+'_'+name+'_tie']+=int(margin==0)
                a=float(x['geometry_temporal_margin']);b=float(x['geometry_mean_margin'])
                c[s+'_temporal_repairs_mean']+=int(a>0 and b<=0);c[s+'_temporal_breaks_mean']+=int(a<=0 and b>0)
    return allrows,known


def execute(config,output,receipt):
    config,output,receipt=map(Path,(config,output,receipt));require(receipt.parent==E and not receipt.exists(),'终验输出已有或越界')
    cfg=read(config);manifest=read(cfg['bundle_manifest']['path'])
    require(sha(cfg['bundle_manifest']['path'])==cfg['bundle_manifest']['sha256'],'代码清单变化')
    for x in manifest['files']:require(sha(Path(cfg['bundle'])/x['path'])==x['sha256'],'活动冻结源码变化')
    state=read(output/'state.json');report=read(output/'report.json')
    require(report['status']==state['status']=='complete54_information_chain_zero_updates_not_new_tracking_or_training'
        and state['active'] is None and len(state['completed_units'])==54,'实际54终态未闭合')
    require(sha(output/'report.json')==state['report']['sha256'] and report['config']==ref(config),'报告来源变化')
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',"Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python'} | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"],capture_output=True,text=True)
    require(p.returncode==0,'CIM查询失败')
    processes=json.loads(p.stdout or '[]');processes=[processes] if isinstance(processes,dict) else processes
    blocked=[x for x in processes if is_producer(x.get('CommandLine'))]
    require(not blocked,'诊断生产者仍在：'+str(blocked))
    details=report['details'];require(len(details)==len({x['job']['job_id'] for x in details})==54,'旧全部单元未齐')
    require(set(state['completed_units'])=={x['job']['job_id'] for x in details},'state/报告任务不同')
    require(report['new_optimizer_updates']==0 and report['new_detector_or_Pose_inference'] is False
        and report['new_free_tracking'] is False and report['test_read'] is False,'预算或测试边界变化')
    require(len(report['calibrations'])==18 and all(x['fit_scope']=='allowed_base_train_R_only_no_labels_no_external'
        and x['fit_windows']==1000 and x['quantiles']==dict(motion=.25,velocity=.99) for x in report['calibrations'].values()),'拟合来源或量化规则不符')
    rows_ref=report['all_stage_rows'];require(rows_ref==ref(output/'all_stage_rows.csv.gz'),'全部行CSV变化')
    with gzip.open(rows_ref['path'],'rt',encoding='utf-8',newline='') as f:counts,known=tally(csv.DictReader(f))
    require(sum(counts.values())==report['stage_rows'],'行总数不符')
    grouped=defaultdict(Counter)
    for d in details:
        j=d['job'];jid=j['job_id'];c=d['counts'];require(counts[jid]==c['all_stage_rows'],'逐单元行数不符')
        for key,value in known[jid].items():require(c.get(key,0)==value,'CSV正负/未知/排序汇总不符：'+key)
        require(c['shadow_motion_assignment_exact_events']+c['shadow_motion_assignment_mismatch_events']==c['stage_calls'],'数值可比分母丢失')
        key=j['original']['pool']+'/'+('old_heldout' if j['original']['sequence'].startswith('SNMOT-') else 'external')
        grouped[key].update(c)
    require({k:dict(v) for k,v in grouped.items()}==report['groups'],'完整分组被选择')
    sample=read(E/'quality_sample_plan_a01.json');require(len(sample['rows'])==len({x['uid'] for x in sample['rows']})==120
        and sample['actual_manual_reviews']==0 and sample['manual_keypoint_truth_available'] is False,'复核索引或未标注状态被伪造')
    result=dict(status='complete54_zero_update_information_chain_all_rows_and_exit_verified',config=ref(config),report=ref(output/'report.json'),
        all_rows=rows_ref,source_units=54,stage_rows=report['stage_rows'],all_negative_and_unknown_rows_retained=True,
        causal_quality_sample=ref(E/'quality_sample_plan_a01.json'),manual_keypoint_review_complete=False,
        producer_processes_absent=True,new_optimizer_updates=0,test_read=False)
    with receipt.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    return dict(status=result['status'],source_units=54,stage_rows=result['stage_rows'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output','receipt'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(execute(a.config,a.output,a.receipt)))
