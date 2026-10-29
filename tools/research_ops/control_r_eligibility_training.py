"""唯一18臂资格mask控制器；首千步独立CPU审计通过后才继续其余17。"""
import argparse,json,os,re,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
if __name__=='__main__' and '--config' in sys.argv:
    # 独立执行控制器可以单文件安装；实际训练/记录仍只导入已准入的原冻结闭包。
    _entry_config=Path(sys.argv[sys.argv.index('--config')+1]);_entry_body=json.loads(_entry_config.read_text(encoding='utf-8-sig'))
    _entry_bundle=Path(_entry_body['bundle']);sys.path[:0]=[str(_entry_bundle/'tools/research_ops'),str(_entry_bundle/'tools/performance')]
import r_eligibility_training_runtime as rt
from training_journal import atomic,write_new

STATUS='complete18_R_candidate_eligibility_training_wait_independent_audit_tracking'
RUN_SCHEMA='R_candidate_eligibility_full_recorded_training_run_v1'

def process_inventory():
    cmd="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    text=subprocess.run(['powershell.exe','-NoProfile','-Command',cmd],capture_output=True,check=True,text=True,encoding='utf-8').stdout
    rows=json.loads(text) if text.strip() else [];return [rows] if isinstance(rows,dict) else rows

def own_chain(rows):
    own={os.getpid()};by={r['ProcessId']:r for r in rows};item=by.get(os.getpid())
    while item and item['ParentProcessId'] in by:
        item=by[item['ParentProcessId']]
        if item['ProcessId'] in own:break
        own.add(item['ProcessId'])
    return own

def exclusive():
    rows=process_inventory();own=own_chain(rows)
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:r_eligibility_train|control_r_eligibility_training|validate_r_eligibility_numeric|set_supervision_train|control_r_set_supervision_training|validate_r_set_supervision_numeric|state_aligned_(?:train|training_control|tracking_control)|pose_velocity_learning_(?:train|control)|state_gap_control|r_set_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
    blocked=[r for r in rows if r['ProcessId'] not in own and ((r.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(r.get('CommandLine') or ''))]
    rt.require(not blocked,'已有研究/UE实际进程，拒绝重复启动或竞争：'+rt.canonical(blocked));return rows,own

def memory_gate():
    import psutil,torch
    from ctypes import Structure,c_ulong,c_size_t,sizeof,byref,windll
    class Info(Structure):
        _fields_=[('cb',c_ulong)]+[(k,c_size_t) for k in ('CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable','SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[(k,c_ulong) for k in ('HandleCount','ProcessCount','ThreadCount')]
    info=Info();info.cb=sizeof(info);rt.require(windll.psapi.GetPerformanceInfo(byref(info),sizeof(info)),'无法核Windows commit')
    commit=(info.CommitLimit-info.CommitTotal)*info.PageSize;ram=psutil.virtual_memory().available
    rt.require(ram>=8589934592 and commit>=6442450944,'保留RAM8GiB/commit6GiB不足')
    rt.require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>2147483648,'保留VRAM2GiB不足')
    return dict(available_RAM_bytes=ram,commit_available_bytes=commit,cuda_free_bytes=torch.cuda.mem_get_info()[0],RAM_reserve_bytes=8589934592,commit_reserve_bytes=6442450944,VRAM_reserve_bytes=2147483648)

def validate_receipt(receipt,job):
    rt.require(receipt['schema']==RUN_SCHEMA and receipt['status']=='complete' and receipt['completed_updates']==1000
        and receipt['real_window_exposures']==3000 and receipt['synthetic_window_exposures']==1000*int(job['regime']=='RS')
        and receipt['formal'] is True and receipt['diagnostic_variant'] is None and receipt['numeric_only_virtual_mask_overrides']==[]
        and receipt['synthetic_stress_initial_step'] is None and receipt['optimizer_replay']==0 and receipt['test_read'] is False,'正式run身份/1000步预算不同')
    rt.require({k:receipt['binding'][k] for k in ('fold','seed','regime')}==job,'正式run单元不同')
    p=receipt['prefetch'];rt.require(p['closed'] is True and p['worker_alive'] is False and p['loaded']==p['yielded']==1000,'预取未完整join/消费')
    rt.require(0<=receipt['cache_peak_bytes']<=268435456 and receipt['actual_dtype']=='float32' and receipt['amp'] is False and receipt['epoch_augmentation'] is False,'缓存/数值/增广不同')

def execution_identity(config,cfg,output,execution_config=None):
    out=rt.physical(output)
    if execution_config is None:
        rt.require(Path(cfg['training_control_root'])==out,'默认控制目录不是冻结路径');return None
    declaration=rt.read(execution_config)
    rt.require(declaration['schema']=='R_candidate_eligibility_controller_execution_v1' and declaration['approved_by']=='root'
        and declaration['training_protocol']==dict(path=str(Path(config)),sha256=rt.sha(config))
        and declaration['training_bundle']==cfg['bundle'] and Path(declaration['control_root'])==out
        and declaration['controller_source']['sha256']==rt.sha(__file__) and Path(declaration['controller_source']['path'])==Path(__file__)
        and declaration['previous_formal_updates']==0 and declaration['test_read'] is False,'独立执行协议/原学习准入或0更新继承不符')
    previous=rt.read_ref(declaration['previous_failure']);rt.require(previous['formal_optimizer_updates']==0 and previous['training_children_started']==0,'不可隐式重放已有正式更新')
    return dict(path=str(Path(execution_config)),sha256=rt.sha(execution_config))

def preflight(config,output,execution_config=None):
    cfg=rt.validate_protocol(config);rt.validate_training_admission(config,cfg);inventory,own=exclusive();resources=memory_gate()
    out=rt.physical(output);identity=execution_identity(config,cfg,out,execution_config);rt.require(rt.EXPERIMENT in out.parents and not out.exists(),'仅独立新控制目录，partial不覆盖')
    auditor=rt.checked(cfg['training_auditor']);rt.require(auditor.name=='verify_r_eligibility_training.py','必须本轮独立审计器')
    return cfg,dict(status='readonly_R_candidate_eligibility_training_preflight',planned_runs=18,updates=18000,R_windows=54000,S_windows=9000,own_launcher_chain=sorted(own),resources=resources,controller_execution_protocol=identity,test_read=False)

def execute(config,output,execution_config=None):
    cfg,flight=preflight(config,output,execution_config);out=Path(output);out.mkdir(parents=True);write_new(out/'preflight.json',flight)
    state=dict(schema='R_candidate_eligibility18_training_control_v1',status='starting',pid=os.getpid(),protocol_sha256=rt.sha(config),completed_train=[],unverified_completed_runs=[],active=None,
        formal_optimizer_updates=0,observed_child_exits=[],uncommitted_effects_not_guessed=True,controller_execution_protocol=flight['controller_execution_protocol'],test_read=False)
    def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();atomic(out/'driver_state.json',state)
    save()
    try:
        for job in cfg['training_matrix']:
            if (out/'STOP').exists():state.update(status='stopped_at_user_boundary_no_replay',active=None);save();return state
            exclusive();resource=memory_gate();fold,seed,regime=(job[k] for k in ('fold','seed','regime'));start=time.perf_counter()
            directory=out/'runs'/fold/str(seed)/regime/'training';logs=out/'logs';logs.mkdir(exist_ok=True);tag=f'{fold}_{seed}_{regime}'
            cmd=[sys.executable,'-B',str(rt.ROOT/'tools/research_ops/r_eligibility_train.py'),'--config',str(config),'--output',str(directory),'--fold',fold,'--seed',str(seed),'--regime',regime,'--execute']
            with (logs/(tag+'.stdout.log')).open('x',encoding='utf-8') as stdout,(logs/(tag+'.stderr.log')).open('x',encoding='utf-8') as stderr:
                child=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,env=os.environ.copy());state.update(status='training',active=dict(job=job,pid=child.pid,command=cmd,resources=resource));save();code=child.wait()
            receipt_path=directory/'run_receipt.json';receipt=rt.read(receipt_path) if receipt_path.exists() else None;updates=receipt.get('completed_updates') if receipt else None
            state['active']=None;state['observed_child_exits'].append(dict(job=job,exit_code=code,reported_completed_updates=updates,receipt_sha256=rt.sha(receipt_path) if receipt else None))
            if receipt and type(updates) is int:
                state['formal_optimizer_updates']+=updates;state['unverified_completed_runs'].append(dict(**job,path=str(directory),receipt_sha256=rt.sha(receipt_path),reported_completed_updates=updates,status=receipt.get('status')))
            save();rt.require(code==0,tag+'实际失败，保留partial且不重放');rt.require(receipt is not None,'子进程退出无收据，不猜实际更新')
            if receipt['status']=='safely_paused':state.update(status='safely_paused_user_no_replay',active=None,paused_job=job);save();return state
            validate_receipt(receipt,job)
            b=receipt['binding'];identity=(b['initialization_sha256'],b['R_window_UID_chain_sha256'],b['R_objective'],b['mask_input_sha256']);key=f'{fold}/{seed}'
            if key not in state.setdefault('paired_R_RS_identities',{}):state['paired_R_RS_identities'][key]=identity
            else:rt.require(tuple(state['paired_R_RS_identities'][key])==identity,'R/RS原R顺序/初始化/mask身份不同')
            if not state['completed_train']:
                gate=out/'first_run_independent_gate.json';audit_cmd=[sys.executable,'-B',str(rt.checked(cfg['training_auditor'])),'--config',str(config),'--run',str(directory),'--output',str(gate),'--first-run-only','--execute']
                env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='-1'
                with (logs/'first_run_audit.stdout.log').open('x',encoding='utf-8') as stdout,(logs/'first_run_audit.stderr.log').open('x',encoding='utf-8') as stderr:
                    auditor=subprocess.Popen(audit_cmd,stdout=stdout,stderr=stderr,env=env);state.update(status='first1000_wait_independent_CPU_audit',active=dict(job=job,pid=auditor.pid,command=audit_cmd,operation='independent_first_run_audit'));save();audit_code=auditor.wait()
                state.setdefault('audit_child_exits',[]).append(dict(job=job,exit_code=audit_code));state['active']=None;save()
                rt.require(audit_code==0 and gate.exists(),'首千步独立门禁失败，保留已训run，不启动其余17/不重训')
                proof=rt.read(gate);rt.require(proof['status']=='complete_first_R_candidate_eligibility1000_full21_checkpoints_independently_verified'
                    and Path(proof['run'])==directory and proof['protocol']['sha256']==rt.sha(config) and proof['full_checkpoints_read']==21 and proof['new_optimizer_updates']==0,'首千步真实来源/21完整检查点审计不足')
                state['first_run_gate']=dict(path=str(gate),sha256=rt.sha(gate));save()
            state['completed_train'].append(dict(**job,path=str(directory),receipt_sha256=rt.sha(receipt_path),complete_sha256=rt.sha(directory/'training_complete.json'),wall_seconds=time.perf_counter()-start))
            state['unverified_completed_runs']=[v for v in state['unverified_completed_runs'] if v['path']!=str(directory)];save()
        rt.require(len(state['completed_train'])==18 and state['formal_optimizer_updates']==18000,'全部18臂实际更新不足')
        state.update(status=STATUS,active=None);save();return state
    except BaseException:
        state.update(status='failed_preserved_no_replay',traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--execution-config',type=Path);p.add_argument('--execute',action='store_true');args=p.parse_args();os.environ.update(PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(rt.RESEARCH/'runtime_dependencies'),CUBLAS_WORKSPACE_CONFIG=':4096:8')
    result=execute(args.config,args.output,args.execution_config) if args.execute else preflight(args.config,args.output,args.execution_config)[1]
    print(rt.canonical(dict(status=result['status'])))
