"""唯一162项CPU共同状态/自由消融控制器；独立输出、无优化更新。"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import traceback
sys.path.insert(0,str(Path(__file__).parent))
import pose_mechanism_core as core


def preflight(config,output):
    cfg,rt,old,runtime,train,numeric,base,numbers=core.validate(config)
    core.require(cfg['jobs']==core.job_matrix(old),'全部54共同状态与108自由消融必须齐全')
    proof=core.read(core.checked(cfg['numeric_proof']))
    core.require(proof['status']=='complete_actual_common_motion_trace_exact' and proof['optimizer_updates']==0,'真实750帧记录等价尚未验收')
    for ref in proof['numerical_source_files']:
        core.require(core.sha(core.ROOT/'tools/research_ops'/Path(ref['path']).name)==ref['sha256'],'已验收核心源码变化')
    from v8_control import process_snapshot,own_launcher_chain
    processes=process_snapshot();own=own_launcher_chain(processes,os.getpid(),Path(__file__).resolve())
    blocked=[p for p in processes if p['ProcessId'] not in own and (p['Name'].lower().startswith('unrealeditor') or
        any(s in (p.get('CommandLine') or '') for s in ('pose_mechanism_control.py','pose_mechanism_jobs.py','v10_training_control.py','v10_tracking_control.py')))]
    core.require(not blocked,'已有活动任务，不重复启动：'+str(blocked))
    output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'控制器partial不覆盖')
    return cfg,runtime,dict(status='readonly_pose_mechanism162_preflight',jobs=162,optimizer_updates=0,GPU_used=False,test_read=False,launcher_chain=sorted(own))


def execute(config,output):
    cfg,runtime,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True)
    journal=core.load('mechanism_frozen_atomic',runtime.ROOT/'tools/research_ops/training_journal.py')
    journal.atomic(output/'preflight.json',flight);state=dict(schema='pose_mechanism_serial_control_v1',status='starting',pid=os.getpid(),completed=[],active=None)
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat();journal.atomic(output/'driver_state.json',state)
    def child(tag,script,args):
        core.require(not (output/'STOP').exists(),'STOP边界，不自动重放')
        log=output/'logs';log.mkdir(exist_ok=True)
        with (log/(tag+'.stdout.txt')).open('x',encoding='utf-8') as stdout,(log/(tag+'.stderr.txt')).open('x',encoding='utf-8') as stderr:
            command=[sys.executable,'-B',str(core.ROOT/'tools/research_ops'/script)]+list(map(str,args))
            p=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=os.environ.copy());state['active']=dict(tag=tag,pid=p.pid,command=command);save();code=p.wait()
        core.require(code==0,tag+'真实子进程失败，保留partial');state['active']=None;save()
    save()
    try:
        for job in cfg['jobs']:
            state['status']='CPU_diagnostics';save();folder=output/'runs'/job['job_id']
            child(job['job_id']+'_track','pose_mechanism_jobs.py',['--config',config,'--job-id',job['job_id'],'--output',folder/'tracking','--mode','track','--execute'])
            if job['kind']=='free':child(job['job_id']+'_metric','pose_mechanism_jobs.py',['--config',config,'--tracking',folder/'tracking','--output',folder/'metric','--mode','metric','--execute'])
            state['completed'].append(dict(job=job,receipt=core.ref(folder/'tracking/receipt.json')));save()
        state['status']='complete162_wait_analysis';save()
        child('final_analysis','pose_mechanism_analyze.py',['--config',config,'--control',output,'--output',output/'analysis_a01'])
        core.require(core.read(output/'analysis_a01/report.json')['status']=='complete54_common108_free_diagnostics','完整分析缺失')
        state['status']='complete162_CPU_diagnostics_and_analysis';save()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());save();raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies',YOLO_AUTOINSTALL='false')
    if a.execute:execute(a.config,a.output)
    else:print(core.canonical(preflight(a.config,a.output)[2]))
