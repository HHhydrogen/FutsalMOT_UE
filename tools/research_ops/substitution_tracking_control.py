"""七比赛392项唯一CPU追踪/评价/配对区间控制器；保留失败，不隐式重放。"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).parent))
import substitution_tracking_runtime as rt

def process_gate(records,pid,script):
    by={p['ProcessId']:p for p in records};current=by.get(pid);own={pid}
    def tail(x):
        text=(x.get('CommandLine') or '').replace('"','').replace('/','\\').lower();needle=str(script).replace('/','\\').lower()
        return text[text.index(needle):] if needle in text else None
    for _ in range(4):
        parent=by.get(current.get('ParentProcessId')) if current else None
        if parent is None or tail(current) is None or tail(parent)!=tail(current):break
        own.add(parent['ProcessId']);current=parent
    words=('substitution_C_control.py','substitution_C_train.py','substitution_validation_inputs.py',
        'substitution_validation_predictions.py','substitution_tracking_control.py','substitution_tracking_jobs.py')
    blocked=[p for p in records if p['ProcessId'] not in own and (p['Name'].lower().startswith('unrealeditor')
        or any(w in (p.get('CommandLine') or '') for w in words))]
    rt.require(not blocked,'生产者/重复控制器/UE仍运行：'+str(blocked));return sorted(own)

def preflight(config,output):
    c,dep,cr,cc=rt.validate_config(config)
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    snap=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='replace')
    rt.require(snap.returncode==0,'真实进程身份查询失败');records=json.loads(snap.stdout or '[]');records=[records] if isinstance(records,dict) else records
    own=process_gate(records,os.getpid(),Path(__file__).resolve())
    for s in c['sources'].values():rt.checked(s['cache'])
    output=dep[3].storage().physical_child(output,rt.EXP);rt.require(not output.exists(),'已有控制输出/partial，不重放')
    return c,dep,dict(status='readonly392_seven_match_ABC_preflight',tracking_jobs=392,new_updates=0,GPU=False,test_read=False,own_launcher_chain=own)

def execute(config,output):
    c,dep,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True)
    journal=rt.module('substitution_control_atomic',dep[3].ROOT/'tools/research_ops/training_journal.py')
    journal.atomic(output/'preflight.json',flight);state=dict(schema='seven_match_ABC_tracking_control_v1',status='starting',pid=os.getpid(),
        protocol_sha256=rt.sha(config),completed_tracking=[],active=None)
    def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();journal.atomic(output/'driver_state.json',state)
    def child(tag,entry,args):
        logs=output/'logs';logs.mkdir(exist_ok=True);cmd=[sys.executable,'-B',str(rt.ROOT/'tools/research_ops'/entry)]+list(map(str,args))
        with (logs/(tag+'.stdout.log')).open('x',encoding='utf-8') as stdout,(logs/(tag+'.stderr.log')).open('x',encoding='utf-8') as stderr:
            p=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,env=os.environ.copy());state['active']=dict(tag=tag,pid=p.pid,command=cmd);save();code=p.wait()
        rt.require(code==0,tag+'真实失败，保留partial/日志，不自动重放');state['active']=None;save()
    save()
    try:
        registration=rt.read(rt.checked(c['registry_receipt']))
        for i,job in enumerate(c['tracking_matrix']):
            if (output/'STOP').exists():state.update(status='stopped_at_user_boundary_no_replay',active=None);save();return
            folder=output/'runs'/job['job_id'];state['status']='tracking_and_evaluating';save();clock=time.perf_counter()
            child(job['job_id']+'_track','substitution_tracking_jobs.py',['--action','track','--config',config,'--job-id',job['job_id'],'--output',folder/'tracking','--execute'])
            child(job['job_id']+'_metric','substitution_tracking_jobs.py',['--action','metric','--config',config,'--tracking',folder/'tracking','--output',folder/'metric','--execute'])
            p=folder/'metric/report.json';report=rt.read(p)
            rt.require(report['status']=='complete' and report['job']==job and report['DO_PREPROC'] is False
                and report['predictions_GT_filtered'] is False and report['GT_rows']==registration['GT_row_counts'][job['sequence']],
                '实际评价/GT行数未闭合')
            state['completed_tracking'].append(dict(job=job,report_sha256=rt.sha(p),wall_seconds=time.perf_counter()-clock));save()
            if i==13:
                rt.require(all(x['job']['kind']=='PT' for x in state['completed_tracking']),'先完整14个PT门禁')
                journal.atomic(output/'all_seven_PT_adapter_gate.json',dict(status='complete14_PT_all_seven_actual_evaluations',
                    jobs=14,GT_ID0_original=True,DO_PREPROC=False,predictions_filtered=False,test_read=False))
        state['status']='complete392_wait_paired_analysis';save()
        child('paired_analysis','substitution_tracking_analysis.py',['--config',config,'--control',output,'--output',output/'analysis_a01'])
        rt.require(rt.read(output/'analysis_a01/report.json')['status']=='complete392_all_results_and_paired_intervals','完整配对分析未完成')
        state['status']='complete392_tracking_and_paired_intervals';save()
    except BaseException as e:
        state.update(status='failed_preserved_no_replay',error=repr(e),traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies',YOLO_AUTOINSTALL='false')
    if a.execute:execute(a.config,a.output)
    else:print(rt.canonical(preflight(a.config,a.output)[2]))
