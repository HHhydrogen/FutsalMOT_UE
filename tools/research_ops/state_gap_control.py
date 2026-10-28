"""训练域状态差异唯一控制器：正常track、GT后验、有限oracle与完整汇总。"""
import argparse
from collections import deque
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/state_gap_diagnosis_a01';ROOT=Path(__file__).resolve().parents[2]
SERVICE=R/'code/70a399c65ff8cf7f2ef7090a0739ab161ff5b59b338c419f54e0c6c1238645f7/tools/research_ops/tracking_policy_ledger_control.py'
SERVICE_SHA='7cb703e6e38a8d285ca397190647573b051e168ac8d3a5ffc9877d29f97599f6'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m
    before=sys.dont_write_bytecode
    try: sys.dont_write_bytecode=True;spec.loader.exec_module(m)
    finally: sys.dont_write_bytecode=before
    return m
if hashlib.sha256(SERVICE.read_bytes()).hexdigest()!=SERVICE_SHA: raise ValueError('原Service源码变化')
base=load('state_gap_original_service',SERVICE)
rt=load('state_gap_own_runtime',ROOT/'tools/research_ops/state_gap_runtime.py')
require,canonical,ref,checked,read_ref,write_new=rt.require,rt.canonical,rt.ref,rt.checked,rt.read_ref,rt.write_new
STATUS='complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed'
PROFILE_BASE=dict(numeric_threads=1,reserve_RAM_bytes=8589934592,reserve_commit_bytes=6442450944,
    startup_estimate_bytes=536870912,model_cache_limit_bytes=268435456,model_cache_max_entries=3,
    frame_cache_limit_bytes=134217728,frame_cache_max_entries=2)

RECOVERY_SOURCE_KEYS=('inventory','sources','jobs','inputs_source','original_tracking_source','track_guard_source','worker_support','source_velocity_protocol','tracker_parameters','diagnostic_parameters','analysis_parameters','worker_service')

def recovery_inheritance(cfg):
    """只承认成功收据；旧失联状态和partial不能冒充正常退出或完成。"""
    r=cfg['recovery'];old=read_ref(r['source_protocol']);state=read_ref(r['source_state']);failure=read_ref(r['interruption'])
    require(all(cfg[k]==old[k] for k in RECOVERY_SOURCE_KEYS),'恢复不得改变模型/来源/十二矩阵/数值与统计')
    require(state['protocol']==r['source_protocol'] and cfg['numeric_admission']==old['numeric_admission'],'旧状态协议或原数值准入漂移')
    require(failure['source_state']==r['source_state'] and failure['actual_research_controller_and_spawn_processes_absent'] is True
        and failure['actual_exit_codes'] is None and failure['partial_actual_frame_advances'] is None,'失联/partial不得补造退出或推进数')
    observe=r['inherit_observe'];post=r['inherit_posthoc'];jobs={j['job_id']:j for j in cfg['jobs']}
    require(observe==state['observe'] and post==state['posthoc'] and len(observe)==5 and len(post)==2,'只继承原五观察/二后验')
    require(r['restart_incomplete_jobs_explicit']==[j['job_id'] for j in cfg['jobs'] if j['job_id'] not in observe],'七个未完成任务必须明确登记')
    for jid,value in observe.items():
        p=read_ref(value);require(p['status']=='complete' and p['frames']==750 and p['frames_log']['rows']==750
            and p['job']==jobs[jid] and p['protocol']==r['source_protocol'] and p['observer_enabled'] is True
            and p['source_cache']==cfg['sources'][jobs[jid]['sequence']]['cache'] and p['GT_guard']['blocked_open_attempts']==0
            and p['models_unchanged'] is True and p['inputs_unchanged'] is True,'继承观察不完整或来源不符')
    def postcheck(jid,value):
        p=read_ref(value);require(jid in observe and p['total_frames']==750 and p['observe']==observe[jid] and p['job']==jobs[jid]
            and p['all_rows']['rows']==p['summary']['absolute_counts']['windows'],'继承后验行数或来源不符')
    for jid,value in post.items():postcheck(jid,value)
    admission=read_ref(r['streaming_admission']);require(admission['status']=='complete_streamed750_posthoc_and_bounded_memory_gate'
        and admission['bundle']==cfg['bundle'] and admission['bundle_manifest']==cfg['bundle_manifest']
        and admission['worker_exited'] is True and admission['exit_code']==0 and admission['peak_worker_RSS_bytes']<=3221225472
        and admission['minimum_available_RAM_bytes']>=8589934592 and admission['minimum_commit_headroom_bytes']>=6442450944,
        '完整750流式/内存/真实退出准入未闭合')
    jid=admission['job_id'];require(jid not in post,'准入不得重做成功后验');postcheck(jid,admission['posthoc'])
    return dict(observe),dict(post,**{jid:admission['posthoc']})

def validate(path):
    cfg=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    require(cfg['schema']=='state_gap_diagnosis_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True
        and cfg['optimizer_updates']==0 and cfg['new_image_predictions']==0,'root零更新封存协议缺失')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code' and Path(cfg['output_root'])==EXP,'只准新冻结bundle/新实验根')
    require(Path(cfg['numeric_output']).parent==EXP and re.fullmatch(r'numeric_admission_a\d{2}',Path(cfg['numeric_output']).name)
        and Path(cfg['control_root']).parent==EXP and re.fullmatch(r'control_a\d{2}',Path(cfg['control_root']).name),'独立attempt输出名缺失')
    for item in read_ref(cfg['bundle_manifest'])['files']: require(rt.sha(ROOT/item['path'])==item['sha256'],'活动源码变化')
    inv=read_ref(cfg['inventory']);rt.validate_matrix(cfg,inv)
    require(cfg['diagnostic_parameters']==dict(seed=20261024,fold_event_cap=20,total_event_cap=60,future_horizon_frames=30,
        first_pass_frame_advances=9000,maximum_prefix_frame_advances=9000,maximum_branch_frame_advances=7440,
        maximum_formal_frame_advances=25440,IoU_trust_threshold=.5),'绝对诊断边界变化')
    require(cfg['analysis_parameters']==dict(scopes=['all_selected','R','RS'],bootstrap_repeats=10000,bootstrap_seed=20261028,t_df=2,t95_critical=4.30265272975,
        independent_level='three_source_means_after_event_mean',missing_source_CI=None,descriptive_comparisons=45,multiplicity_adjusted=False),'绝对统计协议变化')
    require(cfg['worker_service']==ref(SERVICE),'Service不同')
    for key,value in PROFILE_BASE.items(): require(cfg['worker_profile'][key]==value,'线程/资源/缓存变化')
    require((cfg['worker_profile']['track_workers'],cfg['worker_profile']['posthoc_workers']) in ((2,1),(4,2)),'仅有界2+1/4+2')
    if cfg['phase']=='formal':
        if cfg.get('recovery'):
            require(cfg['execute_authorized'] is True and cfg['worker_profile']['track_workers']==2 and cfg['worker_profile']['posthoc_workers']==1
                and cfg['in_flight_estimate_bytes']==3221225472,'恢复只准2track+1posthoc、每在飞任务预留3GiB')
            recovery_inheritance(cfg)
            cfg['_protocol_ref']=ref(path);return cfg
        p=read_ref(cfg['numeric_admission']);require(p['status']=='complete_real_observer_original_ABA_spawn_snapshot_resource_admission'
            and p['all_workers_exited'] is True and p['selected_worker_profile']==cfg['worker_profile'],'真实数值和资源准入未闭合')
        n=read_ref(p['config'])
        for key in ('bundle','bundle_manifest','inventory','sources','jobs','inputs_source','original_tracking_source','track_guard_source','worker_support','source_velocity_protocol','tracker_parameters','diagnostic_parameters','analysis_parameters','worker_service'):
            require(cfg[key]==n[key],'准入后换来源：'+key)
        require(cfg['execute_authorized'] is True,'未授权正式诊断')
    else: require(cfg['phase']=='numeric' and cfg['execute_authorized'] is False,'只允许独立数值阶段')
    cfg['_protocol_ref']=ref(path);return cfg

def producers_absent():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',check=True)
    rows=json.loads(result.stdout) if result.stdout.strip() else [];rows=[rows] if isinstance(rows,dict) else rows
    own={os.getpid()};byid={v['ProcessId']:v for v in rows};node=byid.get(os.getpid())
    while node and node['ParentProcessId'] in byid:
        parent=byid[node['ParentProcessId']]
        if 'state_gap_control.py' not in (parent.get('CommandLine') or ''): break
        own.add(parent['ProcessId']);node=parent
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:state_gap_control|trainR_intercept_(?:fit_control|tracking_control)|pose_velocity_tracking_control|substitution_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
    blocked=[v for v in rows if v['ProcessId'] not in own and ((v.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(v.get('CommandLine') or ''))]
    require(not blocked,'相关实验仍在，不能重复启动：'+canonical(blocked))
    return dict(actual_CIM_checked=True,related_producers_absent=True,own_launcher_chain=sorted(own))

def worker(connection,kind,cfg,log):
    context=None
    try:
        with Path(log).open('x',encoding='utf-8') as f,redirect_stdout(f),redirect_stderr(f):
            context=rt.Context(cfg) if kind=='track' else rt.PosthocContext(cfg)
            connection.send(dict(status='ready',kind=kind,worker_pid=os.getpid()))
            while True:
                task=connection.recv()
                if task['op']=='close':
                    connection.send(dict(status='closed',worker_pid=os.getpid(),closure=context.close()));break
                job=next(j for j in cfg['jobs'] if j['job_id']==task['job_id']);op=task['op']
                if op=='observe': value=rt.observe_job(context,job,task['output'],prefix=task.get('prefix'),original=task.get('original',False))
                elif op=='replay': value=rt.replay_job(context,job,task,task['output'])
                elif op=='posthoc': value=context.annotate(job,task,task['output'])
                elif op=='branch_posthoc': value=context.branch_summary(job,task,task['output'])
                elif op=='probe': value=dict(status='posthoc_ready_without_GT_or_model_execution',worker_pid=os.getpid())
                else: raise ValueError('未知op')
                connection.send(dict(status='complete',kind=kind,worker_pid=os.getpid(),job_id=job['job_id'],result=value))
    except BaseException:
        try: connection.send(dict(status='failed',worker_pid=os.getpid(),traceback=traceback.format_exc()))
        except (EOFError,BrokenPipeError): pass
    finally: connection.close()

class Service(base.Service):
    def __init__(self,kind,cfg,log):
        ctx=mp.get_context('spawn');self.parent,child=ctx.Pipe();self.busy=None;self.closed=False;self.task_failed=False;self.kind=kind
        self.process=ctx.Process(target=worker,args=(child,kind,cfg,str(log)));self.process.start();child.close()
        try: self.ready=self.receive();require(self.ready['status']=='ready' and self.ready['worker_pid']==self.process.pid,'worker未真实就绪')
        except BaseException: self.join_failed();raise

def compare(left,right):
    a,b=read_ref(left),read_ref(right)
    require(all(a[k]==b[k] for k in ('native_sha256','frame_counts','frames','audit','global_ID_after','final_state_hash')),'原生输出/完整audit/ID/隐藏状态不等价')
    if a['observer_enabled'] and b['observer_enabled']:
        require(a['state_sequence_sha256']==b['state_sequence_sha256'] and rt.read_rows(a['frames_log'])==rt.read_rows(b['frames_log']),'旁观日志/状态不等价')
    return dict(original_ID_native_frame_counts_audit_exact=True,frames=a['frames'],both_observer=a['observer_enabled'] and b['observer_enabled'])

def numeric(path,cfg):
    producers_absent();out=Path(cfg['numeric_output']);require(not out.exists(),'数值partial拒绝覆盖');out.mkdir();(out/'logs').mkdir()
    support=rt.module(cfg['worker_support'],'state_gap_support');require(support.enough_memory(support.resource_snapshot(),cfg['worker_profile'],1),'实际资源不足')
    jobs=[next(j for j in cfg['jobs'] if j['regime']==r and j['fold']=='game4') for r in ('R','RS')]
    context=rt.Context(cfg);outputs={};comparisons=[];start=time.perf_counter();all_exits=[];resources=[];consumed=0
    try:
        for name,job,original in [('plain_A',jobs[0],True),('observe_A',jobs[0],False),('observe_B',jobs[1],False),('observe_A_again',jobs[0],False)]:
            if name=='plain_A' and cfg.get('inherited_plain_A'):
                reference=cfg['inherited_plain_A'];previous=read_ref(reference)
                require(previous['status']=='complete' and previous['observer_enabled'] is False and previous['frames']==96
                    and previous['job']==job and previous['source_cache']==cfg['sources'][job['sequence']]['cache']
                    and previous['models_unchanged'] is True and previous['inputs_unchanged'] is True,'继承的原96帧来源不符')
                outputs[name]=reference;continue
            outputs[name]=rt.observe_job(context,job,out/name,prefix=96,original=original);consumed+=96
        comparisons += [compare(outputs['plain_A'],outputs['observe_A']),compare(outputs['observe_A'],outputs['observe_A_again'])]
        core=rt.load_own(cfg,'state_gap_rollout');a=read_ref(outputs['observe_A']);logs=rt.read_rows(a['frames_log']);frames=context.frames(jobs[0]['sequence'])[:96]
        tracker=context.new_tracker(jobs[0]);snaps={}
        with context.torch.no_grad(): core.run_rollout(tracker,frames,observer_kwargs=rt.observer_kwargs(tracker),id_class=context.BaseTrack,
            snapshot_sink=lambda n,v:snaps.update({n:v}),snapshot_frames={49},retain_frames=False)
        consumed+=96
        value=core.import_snapshot(json.loads(canonical(snaps[49])),lambda:context.new_tracker(jobs[0]),id_class=context.BaseTrack)
        with context.torch.no_grad(): resumed=core.run_rollout(value,frames[48:],observer_kwargs=rt.observer_kwargs(value),id_class=context.BaseTrack)
        consumed+=48
        require(resumed['native_frames']==[v['native_output'] for v in logs[48:]] and [v['full_state_sha256'] for v in resumed['frame_states']]==[v['full_state_sha256'] for v in logs[48:]],'portable实际snapshot续跑不等价')
        snapshot_proof=dict(frame_before=49,resumed_frames=48,original_ID_native_and_full_state_exact=True)
    finally: parent_close=context.close()
    profile_results=[]
    # 两个固定候选各4个相同96帧任务；包含进程启动/记录/关闭，非整轮加速承诺。
    for tracks,posts in ((2,1),(4,2)):
        profile=dict(PROFILE_BASE,track_workers=tracks,posthoc_workers=posts);snapshot=support.resource_snapshot();resources.append(snapshot)
        if not support.enough_memory(snapshot,profile,tracks+posts):
            profile_results.append(dict(profile=profile,status='not_admitted_resource_reserve',resource=snapshot));continue
        services=[];started=time.perf_counter();root=out/f'profile_{tracks}_{posts}';root.mkdir()
        try:
            for kind,count in (('track',tracks),('posthoc',posts)):
                for i in range(count): services.append(Service(kind,cfg,out/'logs'/f'numeric_{tracks}_{posts}_{kind}_{i}.log'))
            pending=deque(range(4));active={};results={}
            while pending or active:
                resources.append(support.resource_snapshot())
                for s in services:
                    if s.kind=='track' and s.busy is None and pending:
                        i=pending.popleft();job=jobs[i%2];s.busy=i;active[i]=s
                        s.parent.send(dict(op='observe',job_id=job['job_id'],prefix=96,output=str(root/str(i))))
                ready=wait([s.parent for s in active.values()],timeout=1)
                for s in list(active.values()):
                    if s.parent not in ready: continue
                    i=s.busy;results[i]=s.receive()['result'];s.busy=None;active.pop(i)
                require(all(s.process.is_alive() for s in services),'数值worker意外退出')
            for i in range(4): comparisons.append(compare(outputs['observe_A' if i%2==0 else 'observe_B'],results[i]))
            consumed+=4*96
            for s in services:
                if s.kind=='posthoc':
                    s.parent.send(dict(op='probe',job_id=jobs[0]['job_id']));require(s.receive()['result']['status']=='posthoc_ready_without_GT_or_model_execution','后验worker不就绪')
            exits=[s.close() for s in services];all_exits+=exits
            profile_results.append(dict(profile=profile,status='complete_equal_fixed4_tasks',wall_seconds=time.perf_counter()-started,outputs=list(results.values()),exits=exits))
        finally:
            for s in services:
                if not s.closed:
                    try: all_exits.append(s.close() if not s.busy and not s.task_failed else s.join_failed())
                    except BaseException: all_exits.append(s.join_failed())
    good=[r for r in profile_results if r['status']=='complete_equal_fixed4_tasks'];require(good,'无可用并行候选')
    selected=min(good,key=lambda r:r['wall_seconds'])['profile']
    proof=dict(schema='state_gap_numeric_admission_v1',status='complete_real_observer_original_ABA_spawn_snapshot_resource_admission',config=ref(path),
        comparisons=comparisons,snapshot=snapshot_proof,parent_close=parent_close,profile_trials=profile_results,selected_worker_profile=selected,
        resources=resources,diagnostic_frame_advances=consumed,unique_source_frames=96,optimizer_updates=0,new_image_predictions=0,
        all_workers_exited=all(v['process_exited'] and v['exit_code']==0 for v in all_exits),exits=all_exits,
        wall_seconds=time.perf_counter()-start,test_read=False,full_phase_speedup_claim=False)
    require(proof['all_workers_exited'],'实际worker未退出');write_new(out/'receipt.json',proof);return proof

def execute(path,cfg):
    producers_absent();out=Path(cfg['control_root']);require(not out.exists(),'正式partial拒绝覆盖');out.mkdir();(out/'logs').mkdir()
    support=rt.module(cfg['worker_support'],'state_gap_support');profile=cfg['worker_profile'];started=time.perf_counter();services=[]
    state=dict(schema='state_gap_control_state_v1',status='starting_workers',protocol=ref(path),controller_pid=os.getpid(),
        created_utc=datetime.now(timezone.utc).isoformat(),workers=[],worker_exits=[],resources=[],active=[],observe={},posthoc={},replay={},branch_posthoc={},optimizer_updates=0,test_read=False)
    if cfg.get('recovery'):
        state['observe'],state['posthoc']=recovery_inheritance(cfg);state['recovery']=cfg['recovery']
    def save():
        p=out/'state.pending.json';p.write_text(canonical(state),encoding='utf-8');os.replace(p,out/'driver_state.json')
    def run_pair(op,items,primary,secondary):
        pending=deque(items);post=deque();running={};postop='posthoc' if op=='observe' else 'branch_posthoc'
        if op=='observe':post.extend(dict(job_id=jid,observe=value) for jid,value in primary.items() if jid not in secondary)
        while pending or post or running:
            require(not(out/'STOP').exists(),'用户停止，保留partial')
            require(all(s.process.is_alive() for s in services),'含闲置worker在内的进程意外退出')
            snap=support.resource_snapshot()
            import psutil
            rss=0
            for process in [psutil.Process()]+psutil.Process().children(recursive=True):
                try: rss+=process.memory_info().rss
                except (psutil.NoSuchProcess,psutil.AccessDenied): pass
            snap['sampled_process_tree_RSS_bytes']=rss;state['resources'].append(snap)
            for s in services:
                queue=pending if s.kind=='track' else post
                if s.busy is not None or not queue or not support.enough_memory(snap,profile): continue
                # 当前可用量尚未反映在飞任务未来的JSON/快照峰值；逐次扣减保守预留。
                estimate=cfg.get('in_flight_estimate_bytes',0)
                reserved=estimate*(len(running)+1)
                if snap['available_RAM_bytes']<profile['reserve_RAM_bytes']+reserved or snap['commit_available_bytes']<profile['reserve_commit_bytes']+reserved:continue
                item=queue.popleft();operation=op if s.kind=='track' else postop;jid=item['job_id']
                s.busy=(operation,jid);running[s.busy]=s;s.parent.send(dict(item,op=operation,output=str(out/operation/jid)))
            state['active']=[dict(op=k[0],job_id=k[1],pid=s.process.pid) for k,s in running.items()];save()
            if not running: time.sleep(1);continue
            ready=wait([s.parent for s in running.values()],timeout=1)
            for key,s in list(running.items()):
                if s.parent not in ready: continue
                reference=s.receive()['result'];s.busy=None;running.pop(key)
                if key[0]==op:
                    primary[key[1]]=reference
                    post.append(dict(job_id=key[1],**({'observe':reference} if op=='observe' else {'replay':reference,'selected_events':state['selected_events']})))
                else: secondary[key[1]]=reference
            require(all(s.process.is_alive() for s in services),'worker意外退出');save()
    save()
    try:
        require(support.enough_memory(support.resource_snapshot(),profile,profile['track_workers']+profile['posthoc_workers']),'启动余量不足')
        for kind,key in (('track','track_workers'),('posthoc','posthoc_workers')):
            for i in range(profile[key]):
                service=Service(kind,cfg,out/'logs'/f'{kind}_{i}.log');services.append(service);state['workers'].append(service.ready);save()
        state['status']='observing12_train_rollouts_and_separate_posthoc';save()
        run_pair('observe',[dict(job_id=j['job_id']) for j in cfg['jobs'] if j['job_id'] not in state['observe']],state['observe'],state['posthoc'])
        require(len(state['observe'])==len(state['posthoc'])==12,'12rollout/后验缺项')
        analysis=rt.load_own(cfg,'state_gap_analysis');events=[]
        for value in state['posthoc'].values(): events+=read_ref(value)['events']['events']
        selection=analysis.select_bounded_events(events);write_new(out/'selected_events.json',selection);state['selected_events']=ref(out/'selected_events.json')
        items=[];state['plans']={}
        for job in cfg['jobs']:
            chosen=[v for v in selection['selected'] if v['job_id']==job['job_id']]
            if not chosen: continue
            # 标签资格已在后验worker核验。这里只转交五个UID字段，不载GT坐标。
            plans=[{k:v[k] for k in ('event_id','frame_number','track_id','wrong_uid','correct_uid')} for v in chosen]
            p=out/'plans'/(job['job_id']+'.json');write_new(p,dict(job=job,plans=plans,selection=state['selected_events'],GT_coordinates_in_plan=False));state['plans'][job['job_id']]=ref(p)
            items.append(dict(job_id=job['job_id'],plans=ref(p),observe=state['observe'][job['job_id']]))
        state['status']='fixed_events_then_bounded_four_branch_oracle';save()
        run_pair('replay',items,state['replay'],state['branch_posthoc'])
        for s in services: state['worker_exits'].append(s.close());save()
        require(all(v['process_exited'] and v['exit_code']==0 for v in state['worker_exits']),'实际worker未退')
        # 原池结构每fold只读一次，不做模型评分/训练/重建增广张量。
        inv=read_ref(cfg['inventory']);clean={}
        for fold,info in inv['folds'].items():
            with checked(info['clean_R_pool']).open(encoding='utf-8-sig') as f: windows=[json.loads(line) for line in f if line.strip()]
            require(len(windows)==1000,'原clean池必须1000唯一窗');result=analysis.summarize_clean_windows(windows)
            writer=rt.RowsWriter(out/'analysis_a01'/('clean_'+fold+'.jsonl.gz'))
            for row in result.pop('rows'): writer.write(row)
            clean[fold]=dict(**result,rows=writer.close(),pool=info['clean_R_pool'])
        records=[]
        for value in state['branch_posthoc'].values(): records+=read_ref(value)['event_records']
        summary=analysis.summarize_branches(records)
        prefix=sum(read_ref(v)['prefix_frames'] for v in state['replay'].values());branches=sum(read_ref(v)['branch_frame_advances'] for v in state['replay'].values())
        budget=dict(first_pass_frame_advances=9000,prefix_frame_advances=prefix,branch_frame_advances=branches,total_formal_frame_advances=9000+prefix+branches,
            selected_events=len(selection['selected']),optimizer_updates=0,new_image_predictions=0,numeric_admission=cfg['numeric_admission'])
        if cfg.get('recovery'):
            budget['execution_attempt_budget']=dict(inherited_complete_first_pass_frame_advances=3750,new_successful_first_pass_frame_advances=5250,
                interrupted_partial_actual_frame_advances=None,interrupted_partial_count=3,partial_preserved=True,
                logical_budget_includes_inherited_success=True,physical_retry_work_not_claimed_zero=True,interruption=cfg['recovery']['interruption'])
        require(prefix<=9000 and branches<=7440 and budget['total_formal_frame_advances']<=25440,'诊断越过事前帧预算')
        report=dict(schema='state_gap_diagnosis_report_v1',status='complete12_train_rollouts_and_bounded_state_propagation_diagnosis',protocol=ref(path),
            observe=state['observe'],posthoc=state['posthoc'],selection=state['selected_events'],plans=state['plans'],replay=state['replay'],branch_posthoc=state['branch_posthoc'],
            clean_pool_structures=clean,oracle_summary=summary,budget=budget,worker_exits=state['worker_exits'],worker_profile=profile,
            independent_factor_validation_started=False,performance_scores_not_computed=True,all_negative_and_unknown_preserved=True,test_read=False,
            wall_seconds=time.perf_counter()-started,limitations=['三个已见train比赛，首seed，非独立泛化','局部GT辅助状态修复，不是可部署重分配','不计算或伪造新的AssA/HOTA/IDF1'])
        if cfg.get('recovery'):report['recovery']=cfg['recovery']
        write_new(out/'analysis_a01/report.json',report);state.update(status=STATUS,analysis=ref(out/'analysis_a01/report.json'),active=[],budget=budget);save();return report
    except BaseException:
        state.update(status='failed_preserved_no_implicit_replay',traceback=traceback.format_exc());save();raise
    finally:
        for s in services:
            if not s.closed:
                try: value=s.close() if not s.busy and not s.task_failed else s.join_failed()
                except BaseException: value=s.join_failed()
                state['worker_exits'].append(value)
        save()

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--numeric',action='store_true');a=p.parse_args()
    require(rt.sha(a.config)==a.config_sha256,'配置SHA不符');cfg=validate(a.config)
    if a.numeric:
        require(cfg['phase']=='numeric','数值阶段不同')
        try: value=numeric(a.config,cfg)
        except BaseException:
            failure=Path(cfg['numeric_output'])/'failed.json'
            if not failure.exists(): write_new(failure,dict(status='failed_numeric_preserved_no_implicit_replay',config=ref(a.config),traceback=traceback.format_exc()))
            raise
    elif a.execute: require(cfg['phase']=='formal','正式阶段不同');value=execute(a.config,cfg)
    else: value=dict(status='preflight_complete_no_model_or_GT_execution',jobs=len(cfg['jobs']),protocol=ref(a.config),processes=producers_absent())
    print(canonical(dict(status=value['status'])))
if __name__=='__main__': main()
