"""唯一27臂串行控制；首千步完整验收后才继续，全部失败保留。"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).parent))
import pose_velocity_learning_runtime as rt
from training_journal import atomic

def processes_absent():
    # 匹配脚本完整文件名，排除只含诊断/审计名称的自匹配。
    import re
    raw=subprocess.run(['powershell','-NoProfile','-Command',
        "Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"],
        check=True,capture_output=True,text=True,encoding='utf-8').stdout
    import json
    allp=json.loads(raw) if raw.strip() else [];allp=[allp] if isinstance(allp,dict) else allp
    own={os.getpid()};byid={p['ProcessId']:p for p in allp};cur=os.getpid()
    while cur in byid:
        cur=byid[cur]['ParentProcessId']
        if cur in own:break
        own.add(cur)
    pattern=r'[\\/](?:pose_velocity_learning_(?:train|control)|v10_train|v10_training_control|substitution_C_(?:train|control)|substitution_validation_predictions)[.]py(?:[ \"\t]|$)'
    blocked=[p for p in allp if p['ProcessId'] not in own and (p['Name'].lower().startswith('unrealeditor') or re.search(pattern,p.get('CommandLine') or ''))]
    rt.require(not blocked,'已有自有GPU任务/UE，禁止重复：'+rt.canonical(blocked))
    return sorted(own)

def preflight(config,output):
    cfg=rt.validate_protocol(config);proof=rt.read(cfg['numeric_validation_receipt_path'])
    rt.validate_learning_admission(config,cfg)
    rt.require(proof['status']=='complete_three_groups_one_step_exact_full_records_verified' and proof['all_groups_equal']
        and proof['protocol_sha256']==rt.sha(config),'真实数值/记录准入未通过')
    own=processes_absent();output=rt.physical(output)
    rt.require(rt.EXPERIMENT in output.parents and not output.exists(),'已有控制器/partial或输出越界')
    for fold in rt.FOLDS:
        for seed in rt.SEEDS:rt.prepare(config,fold,seed,'T_RS')
    return cfg,dict(status='readonly27_bounded_velocity_training_preflight',runs=27,updates=27000,
        R_windows=81000,S_windows=18000,own_launcher_chain=own,test_read=False,full_records=True)

def execute(config,output):
    cfg,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True)
    rt.write_new(output/'preflight.json',flight)
    state=dict(schema='bounded_velocity_training_control_v1',status='starting',pid=os.getpid(),
        protocol_sha256=rt.sha(config),completed_train=[],active=None)
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(output/'driver_state.json',state)
    save();identities={}
    try:
        for job in cfg['training_matrix']:
            if (output/'STOP').exists():state.update(status='stopped_at_user_boundary_no_replay',active=None);save();return
            fold,seed,group=(job[k] for k in ('fold','seed','group'))
            directory=output/'runs'/fold/str(seed)/group/'training';tag='%s_%s_%s'%(fold,seed,group)
            logs=output/'logs';logs.mkdir(exist_ok=True)
            command=[sys.executable,'-B',str(rt.ROOT/'tools/research_ops/pose_velocity_learning_train.py'),
                '--config',str(config),'--output',str(directory),'--fold',fold,'--seed',str(seed),'--group',group,'--execute']
            started=time.perf_counter()
            with (logs/(tag+'.stdout.txt')).open('x',encoding='utf-8') as stdout,(logs/(tag+'.stderr.txt')).open('x',encoding='utf-8') as stderr:
                child=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=os.environ.copy())
                state.update(status='training',active=dict(job=job,child_pid=child.pid,command=command));save();code=child.wait()
            rt.require(code==0,tag+'实际训练失败，保留partial，不重放')
            receipt=rt.read(directory/'run_receipt.json')
            if receipt['status']=='safely_paused':state.update(status='safely_paused_user_no_replay',active=None,paused_job=job);save();return
            rt.require(receipt['status']=='complete' and receipt['completed_updates']==1000 and receipt['real_window_exposures']==3000
                and receipt['synthetic_window_exposures']==1000*int(group!='T_R') and receipt['prefetch']['closed']
                and not receipt['prefetch']['worker_alive'] and receipt['prefetch']['yielded']==1000,'真实预算/预取未闭合')
            key=(fold,seed);binding=receipt['binding'];identity=(binding['initialization_sha256'],binding['R_window_UID_chain_sha256'])
            if key not in identities:identities[key]=identity
            rt.require(identities[key]==identity,'三组初始化/3000R顺序不同')
            rt.complete_model(config,directory,all_checkpoints=not state['completed_train'])
            if not state['completed_train']:
                rt.write_new(output/'first_run_end_to_end_gate.json',dict(status='complete_first_formal1000_full_records21_verified',
                    job=job,actual_updates=1000,checkpoints_read=21,optimizer_replay=0,test_read=False))
            state['completed_train'].append(dict(**job,path=str(directory),receipt_sha256=rt.sha(directory/'run_receipt.json'),
                complete_sha256=rt.sha(directory/'training_complete.json'),wall_seconds=time.perf_counter()-started))
            state['active']=None;save()
        rt.require(len(state['completed_train'])==27,'27臂未齐')
        state.update(status='complete27_bounded_velocity_training_wait_independent_audit_tracking',active=None);save()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH=str(rt.RESEARCH/'runtime_dependencies'),CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if a.execute:execute(a.config,a.output)
    else:print(rt.canonical(preflight(a.config,a.output)[1]))
