"""C4000R十八臂唯一串行控制器；首千步完整核验，不隐式重放partial。"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0,str(Path(__file__).parent))
from training_journal import atomic
import substitution_C_runtime as rt

def exclusive():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='replace')
    rt.require(p.returncode==0,'进程身份查询失败：'+p.stderr)
    records=__import__('json').loads(p.stdout) if p.stdout.strip() else []
    if isinstance(records,dict):records=[records]
    by={x['ProcessId']:x for x in records};own={os.getpid()};current=by.get(os.getpid())
    def tail(x):
        text=(x.get('CommandLine') or '').replace('"','').replace('/','\\').lower();needle=str(Path(__file__).resolve()).replace('/','\\').lower()
        return text[text.index(needle):] if needle in text else None
    for _ in range(4):
        parent=by.get(current.get('ParentProcessId')) if current else None
        if parent is None or tail(current) is None or tail(parent)!=tail(current):break
        own.add(parent['ProcessId']);current=parent
    needles=('substitution_C_control.py','substitution_C_train.py','validate_substitution_C_math.py',
        'substitution_validation_predictions.py','v10_train.py','v10_training_control.py','v10_prediction_cache.py','extra_real_prediction_cache.py')
    blocked=[x for x in records if x['ProcessId'] not in own and (x['Name'].lower().startswith('unrealeditor')
        or any(k in (x.get('CommandLine') or '') for k in needles))]
    rt.require(not blocked,'另有自有GPU任务/UE，拒绝重复启动：'+str(blocked));return sorted(own)

def preflight(config,output):
    c=rt.protocol(config);rt.numeric(c);own=exclusive();proof=rt.read(c['numeric_validation_receipt_path'])
    rt.require(proof['status']=='complete_C_two_methods_actual_loop_equal' and proof['all_equal']
        and proof['protocol_sha256']==rt.sha(config),'实际C循环数值门禁未通过')
    rt.checked(c['environment']);output=rt.storage().physical_child(output,rt.EXP)
    rt.require(not output.exists(),'已有C控制器/partial，不重放')
    for f in rt.FOLDS:
        for s in rt.SEEDS:
            for m in rt.METHODS:rt.job(config,f,s,m)
    return c,dict(status='readonly_C18_full_recorded_preflight',jobs=18,actual_new_updates=0,
        planned_updates=18000,planned_base_R=54000,planned_extra_R=18000,planned_S=0,test_read=False,own_launcher_chain=own)

def execute(config,output):
    c,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True);atomic(output/'preflight.json',flight)
    state=dict(schema='substitution_C18_control_v1',status='starting',pid=os.getpid(),protocol_sha256=rt.sha(config),completed_train=[],active=None)
    def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(output/'driver_state.json',state)
    save()
    try:
        for job in c['training_matrix']:
            if (output/'STOP').exists():state['status']='stopped_at_user_boundary_no_replay';save();return
            f,s,m=(job[k] for k in ('fold','seed','method'));directory=output/'runs'/f/str(s)/m/'training'
            logs=output/'logs';logs.mkdir(exist_ok=True);tag='%s_%s_%s'%(f,s,m)
            cmd=[sys.executable,'-B',str(rt.ROOT/'tools/research_ops/substitution_C_train.py'),'--config',str(config),
                '--output',str(directory),'--fold',f,'--seed',str(s),'--method',m,'--execute']
            start=time.perf_counter()
            with (logs/(tag+'.stdout.log')).open('x',encoding='utf-8') as out,(logs/(tag+'.stderr.log')).open('x',encoding='utf-8') as err:
                child=subprocess.Popen(cmd,stdout=out,stderr=err,env=os.environ.copy());state.update(status='training',active=dict(job=job,pid=child.pid,command=cmd));save();code=child.wait()
            rt.require(code==0,tag+'真实失败，保留日志/last/曝光，不自动重放')
            receipt=rt.read(directory/'run_receipt.json')
            if receipt['status']=='safely_paused':state.update(status='safely_paused_no_replay',active=None,paused=job);save();return
            rt.require(receipt['status']=='complete' and receipt['prefetch']['closed'] and not receipt['prefetch']['worker_alive']
                and receipt['prefetch']['yielded']==1000,'训练/预取未闭合')
            # 首个正式臂读回21份完整状态，失败立即停；其余终态仍由独立加载器检查。
            rt.complete_model(config,directory,all_checkpoints=not state['completed_train'])
            if not state['completed_train']:
                atomic(output/'first_run_end_to_end_gate.json',dict(status='complete_C_first1000_full21checkpoints_verified',
                    job=job,checkpoints=21,actual_updates=1000,base_R=3000,extra_R=1000,S=0,optimizer_replay=0,test_read=False))
            state['completed_train'].append(dict(**job,path=str(directory),receipt_sha256=rt.sha(directory/'run_receipt.json'),
                complete_sha256=rt.sha(directory/'training_complete.json'),wall_seconds=time.perf_counter()-start));state['active']=None;save()
        rt.require(len(state['completed_train'])==18,'十八C未齐');state['status']='complete18_C_training_wait_independent_audit_tracking';save()
    except BaseException as e:
        state.update(status='failed_preserved_no_replay',error=repr(e),traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if a.execute:execute(a.config,a.output)
    else:print(rt.canonical(preflight(a.config,a.output)[1]))
