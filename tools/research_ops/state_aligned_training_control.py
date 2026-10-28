"""唯一十八臂控制器；首1000步21完整检查点验收后继续。"""
import argparse
from datetime import datetime,timezone
import json,os,re,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import state_aligned_training_runtime as rt
from training_journal import atomic

def exclusive():
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',"Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"],check=True,capture_output=True,text=True,encoding='utf-8')
    values=json.loads(result.stdout) if result.stdout.strip() else [];values=[values] if isinstance(values,dict) else values
    own={os.getpid()};by={v['ProcessId']:v for v in values};current=by.get(os.getpid())
    while current and current['ParentProcessId'] in by:
        current=by[current['ParentProcessId']]
        if current['ProcessId'] in own:break
        own.add(current['ProcessId'])
    names=r'(?:state_aligned_(?:train|training_control)|validate_state_aligned_numeric|pose_velocity_learning_(?:train|control)|substitution_C_(?:train|control)|v10_(?:train|training_control|prediction_cache)|substitution_validation_predictions|extra_real_prediction_cache|state_gap_control|verify_state_gap_diagnosis)[.]py(?:[\s"\x27]|$)'
    blocked=[v for v in values if v['ProcessId'] not in own and ((v['Name'] or '').lower().startswith('unrealeditor') or re.search(names,v.get('CommandLine') or ''))]
    rt.require(not blocked,'已有研究任务/UE，不重复启动：'+rt.canonical(blocked));return sorted(own)

def memory_gate():
    import psutil
    available=psutil.virtual_memory().available
    # Windows commit必须取实际系统提交，不使用空闲pagefile代替。
    from ctypes import Structure,c_ulong,c_size_t,sizeof,byref,windll
    class Info(Structure):
        _fields_=[('cb',c_ulong)]+[(k,c_size_t) for k in ('CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[(k,c_ulong) for k in ('HandleCount','ProcessCount','ThreadCount')]
    info=Info();info.cb=sizeof(info);rt.require(windll.psapi.GetPerformanceInfo(byref(info),sizeof(info)),'无法取得实际commit')
    commit=(info.CommitLimit-info.CommitTotal)*info.PageSize
    rt.require(available>=8589934592 and commit>=6442450944,'RAM8GiB/commit6GiB保留不足')
    return dict(available_RAM_bytes=available,commit_headroom_bytes=commit)

def preflight(config,output):
    cfg=rt.validate_protocol(config);rt.validate_learning_admission(config,cfg);own=exclusive();resources=memory_gate()
    output=rt.physical(output);rt.require(rt.EXPERIMENT in output.parents and not output.exists(),'已有控制器/partial或输出越界')
    return cfg,dict(status='readonly18_state_aligned_training_preflight',runs=18,updates=18000,R_windows=54000,S_windows=9000,own_launcher_chain=own,resources=resources,test_read=False)

def execute(config,output):
    cfg,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True);rt.write_new(output/'preflight.json',flight)
    state=dict(schema='state_aligned_training18_control_v1',status='starting',pid=os.getpid(),protocol_sha256=rt.sha(config),completed_train=[],active=None)
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(output/'driver_state.json',state)
    save();identities={}
    try:
        for job in cfg['training_matrix']:
            if (output/'STOP').exists():state.update(status='stopped_at_user_boundary_no_replay',active=None);save();return
            fold,seed,regime=(job[k] for k in ('fold','seed','regime'));memory_gate()
            directory=output/'runs'/fold/str(seed)/regime/'training';logs=output/'logs';logs.mkdir(exist_ok=True);tag=f'{fold}_{seed}_{regime}'
            cmd=[sys.executable,'-B',str(rt.ROOT/'tools/research_ops/state_aligned_train.py'),'--config',str(config),'--output',str(directory),'--fold',fold,'--seed',str(seed),'--regime',regime,'--execute']
            started=time.perf_counter()
            with (logs/(tag+'.stdout.log')).open('x',encoding='utf-8') as stdout,(logs/(tag+'.stderr.log')).open('x',encoding='utf-8') as stderr:
                child=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,env=os.environ.copy());state.update(status='training',active=dict(job=job,pid=child.pid,command=cmd));save();code=child.wait()
            rt.require(code==0,tag+'真实训练失败，保留partial/last/全部日志，不重放')
            receipt=rt.read(directory/'run_receipt.json')
            if receipt['status']=='safely_paused':state.update(status='safely_paused_user_no_replay',active=None,paused_job=job);save();return
            rt.require(receipt['status']=='complete' and receipt['completed_updates']==1000 and receipt['real_window_exposures']==3000
                and receipt['synthetic_window_exposures']==1000*int(regime=='RS') and receipt['prefetch']['closed']
                and not receipt['prefetch']['worker_alive'] and receipt['prefetch']['yielded']==1000,'实际预算/预取未闭合')
            b=receipt['binding'];identity=(b['initialization_sha256'],b['R_window_UID_chain_sha256']);key=(fold,seed)
            if key not in identities:identities[key]=identity
            rt.require(identities[key]==identity,'R/RS初始化/3000R顺序不同')
            rt.complete_model(config,directory,all_checkpoints=not state['completed_train'])
            if not state['completed_train']:rt.write_new(output/'first_run_end_to_end_gate.json',dict(status='complete_first_state_aligned1000_full21_checkpoints_verified',job=job,actual_updates=1000,R=3000,S=0,checkpoints_read=21,optimizer_replay=0,test_read=False))
            state['completed_train'].append(dict(**job,path=str(directory),receipt_sha256=rt.sha(directory/'run_receipt.json'),complete_sha256=rt.sha(directory/'training_complete.json'),wall_seconds=time.perf_counter()-started));state['active']=None;save()
        rt.require(len(state['completed_train'])==18,'十八臂未齐');state.update(status='complete18_state_aligned_training_wait_independent_audit_tracking',active=None);save()
    except BaseException:
        state.update(status='failed_preserved_no_replay',traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(rt.RESEARCH/'runtime_dependencies'),CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if a.execute:execute(a.config,a.output)
    else:print(rt.canonical(preflight(a.config,a.output)[1]))
