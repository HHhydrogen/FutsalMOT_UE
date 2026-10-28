"""唯一18臂R集合监督控制器；首1000更新与21检查点审计后再继续。"""
import argparse,json,os,re,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import set_supervision_training_runtime as rt
from training_journal import atomic

def process_inventory():
    cmd="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    value=subprocess.run(['powershell.exe','-NoProfile','-Command',cmd],capture_output=True,check=True,text=True,encoding='utf-8').stdout
    rows=json.loads(value) if value.strip() else [];return [rows] if isinstance(rows,dict) else rows
def own_chain(values):
    own={os.getpid()};by={v['ProcessId']:v for v in values};item=by.get(os.getpid())
    while item and item['ParentProcessId'] in by:
        item=by[item['ParentProcessId']]
        if item['ProcessId'] in own:break
        own.add(item['ProcessId'])
    return own
def exclusive():
    values=process_inventory();own=own_chain(values)
    pattern=r'(?:set_supervision_(?:train|training_control|training)|validate_r_set_supervision_numeric|state_aligned_(?:train|training_control|tracking_control|tracking_worker|tracking_metric)|pose_velocity_learning_(?:train|control)|state_gap_control|verify_state_gap_diagnosis)[.]py(?:[\s"\x27]|$)'
    blocked=[v for v in values if v['ProcessId'] not in own and ((v['Name'] or '').lower().startswith('unrealeditor') or re.search(pattern,v.get('CommandLine') or ''))]
    rt.require(not blocked,'已有训练/追踪/UE进程，拒绝竞争或并发：'+rt.canonical(blocked))
    return values,own
def memory_gate():
    import psutil
    from ctypes import Structure,c_ulong,c_size_t,sizeof,byref,windll
    class Info(Structure):
        _fields_=[('cb',c_ulong)]+[(k,c_size_t) for k in ('CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[(k,c_ulong) for k in ('HandleCount','ProcessCount','ThreadCount')]
    info=Info();info.cb=sizeof(info);rt.require(windll.psapi.GetPerformanceInfo(byref(info),sizeof(info)),'无法核实Windows commit余量')
    commit=(info.CommitLimit-info.CommitTotal)*info.PageSize;ram=psutil.virtual_memory().available
    rt.require(ram>=8589934592 and commit>=6442450944,'保留RAM8GiB/commit6GiB门禁不足')
    import torch
    rt.require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>2147483648,'CUDA可用余量需大于2GiB')
    return dict(available_RAM_bytes=ram,commit_headroom_bytes=commit,cuda_free_bytes=torch.cuda.mem_get_info()[0],
        RAM_reserve_bytes=8589934592,commit_reserve_bytes=6442450944,VRAM_reserve_bytes=2147483648)
def preflight(config,output):
    cfg=rt.validate_protocol(config);values,own=exclusive();resources=memory_gate();out=rt.physical(output)
    rt.require(rt.EXPERIMENT in out.parents and not out.exists(),'仅允许独立新训练目录，partial拒绝覆盖')
    admission=Path(cfg['numeric_admission']['path']);numeric=rt.read(admission)
    rt.require(numeric.get('status')=='complete_R_set_supervision_CPU_CUDA_full_record_numeric_admission'
        and numeric.get('protocol_sha256')==rt.sha(config) and numeric.get('formal_optimizer_updates')==0
        and numeric.get('actual_diagnostic_optimizer_updates')==8 and numeric.get('all_groups_equal') is True
        and numeric.get('test_read') is False,'本协议CPU/CUDA真实模型一步及完整记录准入未通过')
    return cfg,dict(status='readonly_R_set_supervision_training_preflight',planned_runs=18,updates=18000,
        R_windows=54000,S_windows=9000,own_launcher_chain=sorted(own),resources=resources,test_read=False)
def execute(config,output):
    cfg,flight=preflight(config,output);output=Path(output);output.mkdir(parents=True);rt.write_new(output/'preflight.json',flight)
    state=dict(schema='R_candidate_set_supervision18_training_control_v1',status='starting',pid=os.getpid(),
        protocol_sha256=rt.sha(config),completed_train=[],unverified_completed_runs=[],active=None,
        formal_optimizer_updates=0,uncommitted_effects_not_guessed=True)
    def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(output/'driver_state.json',state)
    save()
    try:
        for job in cfg['training_matrix']:
            if (output/'STOP').exists():state.update(status='stopped_at_user_boundary_no_replay',active=None);save();return
            memory_gate();fold,seed,regime=(job[k] for k in ('fold','seed','regime'))
            directory=output/'runs'/fold/str(seed)/regime/'training';logs=output/'logs';logs.mkdir(exist_ok=True)
            tag=f'{fold}_{seed}_{regime}';cmd=[sys.executable,'-B',str(rt.ROOT/'tools/research_ops/set_supervision_train.py'),
                '--config',str(config),'--output',str(directory),'--fold',fold,'--seed',str(seed),'--regime',regime,'--execute']
            started=time.perf_counter()
            with (logs/(tag+'.stdout.log')).open('x',encoding='utf-8') as stdout,(logs/(tag+'.stderr.log')).open('x',encoding='utf-8') as stderr:
                child=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,env=os.environ.copy())
                state.update(status='training',active=dict(job=job,pid=child.pid,command=cmd));save();code=child.wait()
            receipt_path=directory/'run_receipt.json'
            receipt=rt.read(receipt_path) if receipt_path.exists() else None
            reported_updates=receipt.get('completed_updates') if receipt else None
            state['active']=None
            state.setdefault('observed_child_exits',[]).append(dict(job=job,exit_code=code,
                reported_completed_updates=reported_updates,receipt_sha256=rt.sha(receipt_path) if receipt else None))
            if receipt and type(reported_updates) is int:
                state['formal_optimizer_updates']+=reported_updates
                state['unverified_completed_runs'].append(dict(**job,path=str(directory),
                    receipt_sha256=rt.sha(receipt_path),reported_completed_updates=reported_updates,
                    status=receipt.get('status')))
            save()
            rt.require(code==0,tag+'真实训练失败，保留partial/日志，不重放')
            rt.require(receipt is not None,tag+'子进程退出但无run receipt，保留现场且不猜更新数')
            if receipt.get('status')=='safely_paused':state.update(status='safely_paused_user_no_replay',active=None,paused_job=job);save();return
            rt.require(receipt.get('schema')=='r_set_supervision_full_recorded_training_run_v1'
                and receipt.get('status')=='complete' and receipt.get('completed_updates')==1000
                and receipt.get('real_window_exposures')==3000
                and receipt.get('synthetic_window_exposures')==1000*int(regime=='RS')
                and receipt.get('prefetch',{}).get('closed') is True
                and receipt['prefetch'].get('worker_alive') is False
                and receipt['prefetch'].get('yielded')==1000,'完整1000更新/有界预取退出不完整')
            binding=receipt['binding'];identity=(binding['initialization_sha256'],binding['R_window_UID_chain_sha256'],binding['R_objective'])
            key=f'{fold}/{seed}'
            if key not in state.get('paired_R_RS_identities',{}):
                state.setdefault('paired_R_RS_identities',{})[key]=identity
            else:rt.require(tuple(state['paired_R_RS_identities'][key])==identity,'同seed R/RS初始化/R窗口顺序/目标身份不一致')
            if not state['completed_train']:
                gate=rt.audit_run(config,directory,all_checkpoints=True)
                rt.write_new(output/'first_run_end_to_end_gate.json',dict(status='complete_first_R_set_supervision1000_full21_checkpoints_verified',job=job,
                    actual_updates=1000,R=3000,S=1000*int(regime=='RS'),checkpoints_read=gate['full_checkpoints_read'],
                    objective='candidate_set_CE_fixed_no_match_logit_0',optimizer_replay=0,test_read=False))
            state['completed_train'].append(dict(**job,path=str(directory),receipt_sha256=rt.sha(directory/'run_receipt.json'),
                complete_sha256=rt.sha(directory/'training_complete.json'),wall_seconds=time.perf_counter()-started))
            state['unverified_completed_runs']=[x for x in state['unverified_completed_runs'] if x['path']!=str(directory)]
            state['active']=None;save()
        rt.require(len(state['completed_train'])==18 and state['formal_optimizer_updates']==18000,'18臂预算不足')
        state.update(status='complete18_R_set_supervision_training_wait_independent_audit',active=None);save()
    except BaseException:
        state.update(status='failed_preserved_no_replay',traceback=traceback.format_exc());save();raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=str(rt.RESEARCH/'runtime_dependencies'),CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if a.execute:execute(a.config,a.output)
    else:print(rt.canonical(preflight(a.config,a.output)[1]))
