"""R资格监督180项追踪唯一控制；先cold/ABA/spawn再两源评价门禁。"""
import argparse
from collections import deque
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime,timezone
import hashlib,importlib.util,json,multiprocessing as mp,os,re,subprocess,sys,time,traceback
from functools import lru_cache
from multiprocessing.connection import wait
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/r_candidate_eligibility_a01'
sys.path.insert(0,str(Path(__file__).parent))
import r_eligibility_tracking_runtime as rt
BASE=R/'code/70a399c65ff8cf7f2ef7090a0739ab161ff5b59b338c419f54e0c6c1238645f7/tools/research_ops/tracking_policy_ledger_control.py'
BASE_SHA='7cb703e6e38a8d285ca397190647573b051e168ac8d3a5ffc9877d29f97599f6'
PROFILE=dict(track_workers=2,metric_workers=1,numeric_threads=1,cache_limit_bytes=134217728,cache_max_sequences=2,
    model_cache_limit_bytes=268435456,model_cache_max_entries=3,reserve_RAM_bytes=8589934592,reserve_commit_bytes=6442450944,startup_estimate_bytes=268435456)
STATUS='complete180_R_eligibility_tracking_and_paired_analysis'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m
    old=sys.dont_write_bytecode
    try:sys.dont_write_bytecode=True;spec.loader.exec_module(m)
    finally:sys.dont_write_bytecode=old
    return m
@lru_cache(maxsize=1)
def service_base():
    rt.checked(dict(path=str(BASE),sha256=BASE_SHA));return load('eligibility_tracking_service',BASE)
require,canonical,ref,checked,read_ref=rt.require,rt.canonical,rt.ref,rt.checked,rt.read_ref
def write_new(path,value):
    path=rt.safe(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def blocking_processes(rows,own_pid):
    by={v['ProcessId']:v for v in rows};own={own_pid};node=by.get(own_pid)
    while node and node['ParentProcessId'] in by:
        parent=by[node['ParentProcessId']]
        if 'r_eligibility_tracking_control.py' not in (parent.get('CommandLine') or ''):break
        own.add(parent['ProcessId']);node=parent
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:r_eligibility_tracking_control|control_r_eligibility_training|r_eligibility_train|r_set_tracking_control|control_r_set_supervision_training|set_supervision_train|state_aligned_(?:train|training_control|tracking_control)|trainR_intercept_tracking_control|pose_velocity_tracking_control|state_gap_control|substitution_tracking_control|v10_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
    bad=[v for v in rows if v['ProcessId'] not in own and ((v['Name'] or '').lower().startswith('unrealeditor') or pattern.search(v.get('CommandLine') or ''))]
    return bad,sorted(own)

def producers_absent():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    value=subprocess.run(['powershell.exe','-NoProfile','-Command',command],check=True,capture_output=True,text=True,encoding='utf-8').stdout
    rows=json.loads(value) if value.strip() else [];rows=[rows] if isinstance(rows,dict) else rows;bad,own=blocking_processes(rows,os.getpid())
    require(not bad,'相关producer仍在，拒绝重复：'+canonical(bad));return dict(actual_CIM_checked=True,related_producers_absent=True,own_launcher_chain=own)

def validate_gate_jobs(cfg):
    gate=[j for j in cfg['jobs'] if j['job_id'] in cfg['gate_job_ids']]
    require(len(cfg['gate_job_ids'])==len(set(cfg['gate_job_ids']))==2 and len(gate)==2
        and {j['regime'] for j in gate}=={'R','RS'} and {j['sequence'] for j in gate}=={'SNMOT-060','v_2QhNRucNC7E_c017'},'两源R/RS首评价门禁不符')
    return gate

def validate(path):
    cfg=read(path)
    require(cfg['schema']=='r_eligibility_tracking_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True
        and cfg['formal_equivalence_or_noninferiority'] is False and cfg['alias_enabled'] is False,'独立来源政策/测试边界不足')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code' and Path(cfg['output_root'])==EXP,'新冻结闭包/输出不同')
    for item in read_ref(cfg['bundle_manifest'])['files']:require(rt.sha(ROOT/item['path'])==item['sha256'],'冻结源码变化')
    inv=read_ref(cfg['inventory']);rt.validate_jobs(cfg,inv);rt.training_closure(cfg);rt.source_bindings(cfg)
    budget=read_ref(cfg['training_budget']);complete=read_ref(cfg['training_complete'])
    require(cfg['training_control_state']==budget['control_state']==complete['control_state'],'实际训练a02来源引用不同，不得猜旧a01')
    require(cfg['worker_profile']==PROFILE and cfg['worker_service']==ref(BASE),'有界常驻配置或Service不同')
    validate_gate_jobs(cfg)
    plan=read_ref(cfg['analysis_plan']);analysis=load('eligibility_analysis_plan_guard',ROOT/'tools/research_ops/r_eligibility_tracking_analysis.py')
    analysis.validate_analysis_plan(plan,cfg['panels'])
    require(read_ref(cfg['learning_protocol'])['analysis_plan']==cfg['analysis_plan'],
        '追踪分析必须绑定训练前冻结的同一结果前计划')
    for reg in cfg['registries'].values():
        p=read_ref(reg['receipt']);require(p['contains_GT_coordinates'] is False and p['registry']==reg['registry'],'track只准公共receipt')
    if cfg['phase']=='formal':
        p=read_ref(cfg['numeric_admission']);n=read_ref(p['config'])
        require(cfg['tracking_authorized'] is True and cfg['numeric_authorized'] is False and p['status']=='complete_R_eligibility_cold_ABA_two_spawn_numeric_admission'
            and p['passed'] and p['all_workers_joined_exited'] and p['unique_source_frames']==96 and p['diagnostic_frame_consumptions']==336,'实际新模型/cold/ABA/spawn未通过')
        for key in ('bundle','bundle_manifest','inventory','aligned_inventory','aligned_learning_protocol','aligned_tracking_manifest','aligned_tracking_protocol','aligned_analysis','source_state_aligned_runtime','learning_protocol','training_budget','training_complete','training_control_state','source_inventory','source_velocity_protocol','source_worker_framework','original_inputs_source','sources','panels','registries','jobs','tracker_parameters','worker_profile','gate_job_ids','analysis_plan','track_guard_source','expected_GT_rows'):
            require(n[key]==cfg[key],'数值后改变来源：'+key)
        require(len(p['comparisons'])==5 and all(v['original_ID_MOT_exact'] and v['raw_native_frames_exact'] and v['audit_exact'] for v in p['comparisons']),'数值比较不完整')
    else:require(cfg['phase']=='numeric_admission' and cfg['numeric_authorized'] is True and cfg['tracking_authorized'] is False,'只读数值阶段不能全追踪')
    cfg['_protocol_ref']=ref(path);return cfg

def worker(connection,kind,cfg,log):
    try:
        with Path(log).open('x',encoding='utf-8') as f,redirect_stdout(f),redirect_stderr(f):
            w=load('aligned_tracking_workers',ROOT/'tools/research_ops/r_eligibility_tracking_workers.py');context=None
            connection.send(dict(status='ready',worker_pid=os.getpid(),kind=kind))
            while True:
                task=connection.recv()
                if task['op']=='close':
                    closure=context.close() if context else dict(status='closed',jobs=0,worker_pid=os.getpid())
                    connection.send(dict(status='closed',worker_pid=os.getpid(),closure=closure));break
                if context is None:context=w.TrackWorker(cfg) if kind=='track' else w.MetricWorker(cfg)
                if task['op']=='payload':result=context.payload(task['job'],prefix_frames=48)
                elif task['op']=='track':result=context.run(task['job'],task['output'])
                elif task['op']=='metric':result=context.run(task['job'],task['output'])
                else:raise ValueError('未知worker操作')
                connection.send(dict(status='complete',worker_pid=os.getpid(),result=result))
    except BaseException:
        try:connection.send(dict(status='failed',worker_pid=os.getpid(),traceback=traceback.format_exc()))
        except (EOFError,BrokenPipeError):pass
    finally:connection.close()

class Service:
    def __init__(self,kind,cfg,log):
        ctx=mp.get_context('spawn');self.parent,child=ctx.Pipe();self.busy=None;self.closed=False;self.task_failed=False;self.kind=kind
        self.process=ctx.Process(target=worker,args=(child,kind,cfg,str(log)))
        try:
            self.process.start();child.close();self.ready=self.receive()
            require(self.ready['status']=='ready' and self.ready['worker_pid']==self.process.pid,'实际worker未就绪')
        except BaseException as error:
            child.close()
            if self.process.pid is not None:self.process.join(30)
            self.parent.close();self.closed=True
            write_new(Path(log).with_suffix('.startup_failed.json'),dict(status='failed_startup_preserved_no_kill_or_replay',
                worker_pid=self.process.pid,joined=self.process.pid is not None,process_exited=not self.process.is_alive(),
                exit_code=self.process.exitcode,error=repr(error)))
            raise

    def receive(self):return service_base().Service.receive(self)
    def close(self):return service_base().Service.close(self)
    def join_failed(self):return service_base().Service.join_failed(self)

def completed(service):
    value=service.receive()
    require(value['status']=='complete' and value['worker_pid']==service.process.pid,'任务响应身份/状态不同')
    return value['result']

def numeric(path,cfg):
    producers_absent();out=rt.safe(cfg['numeric_output']);require(not out.exists(),'数值partial拒绝覆盖');out.mkdir();logs=out/'logs';logs.mkdir()
    support=rt.module(cfg['worker_support'],'aligned_resource_support');require(support.enough_memory(support.resource_snapshot(),PROFILE,3),'数值资源保留不足')
    w=load('aligned_tracking_numeric_helpers',ROOT/'tools/research_ops/r_eligibility_tracking_workers.py')
    jobs=[next(j for j in cfg['jobs'] if j['job_id']==gid) for gid in cfg['gate_job_ids']];cold=[];exits=[];services=[];comparisons=[]
    def get(s,job):s.parent.send(dict(op='payload',job=job));return numeric_payload(s)
    def numeric_payload(s):
        payload=completed(s);require(payload['frames']==48,'数值前缀实际帧数不是48');return payload
    try:
        for i,job in enumerate(jobs):
            s=Service('track',cfg,logs/f'cold_{i}.log');services.append(s);payload=get(s,job);cold.append(payload);write_new(out/f'cold_{i}.json',payload);exits.append(s.close())
        s=Service('track',cfg,logs/'ABA.log');services.append(s)
        for i,index in enumerate((0,1,0)):
            payload=get(s,jobs[index]);comparisons.append(w.compare_payloads(payload,cold[index]));write_new(out/f'ABA_{i}.json',payload)
        exits.append(s.close())
        spawned=[]
        for i in range(2):
            s=Service('track',cfg,logs/f'spawn_{i}.log');services.append(s);spawned.append(s)
        for s,job in zip(spawned,jobs):s.parent.send(dict(op='payload',job=job))
        for i,s in enumerate(spawned):
            payload=numeric_payload(s);comparisons.append(w.compare_payloads(payload,cold[i]));write_new(out/f'spawn_{i}.json',payload);exits.append(s.close())
        require(all(v['joined'] and v['exit_code']==0 and v['process_exited'] for v in exits),'数值worker未实际退出')
        result=dict(status='complete_R_eligibility_cold_ABA_two_spawn_numeric_admission',config=ref(path),passed=True,all_workers_joined_exited=True,
            comparisons=comparisons,exits=exits,unique_source_frames=96,diagnostic_frame_consumptions=336,new_optimizer_updates=0,test_read=False,
            source_numeric_validation=cfg['source_numeric_validation'],original_tracker_and_scoped_AST_reused=True,alias_used=False,intercept_applied=False)
        write_new(out/'receipt.json',result);return result
    finally:
        for s in services:
            if not s.closed:
                try:s.close() if s.busy is None and not s.task_failed else s.join_failed()
                except BaseException:s.join_failed()

def execute(path,cfg):
    producers_absent();out=rt.safe(cfg['control_root']);require(not out.exists(),'控制器partial/成功拒绝覆盖');out.mkdir();(out/'logs').mkdir()
    support=rt.module(cfg['worker_support'],'aligned_resource_support');require(support.enough_memory(support.resource_snapshot(),PROFILE,3),'启动资源不足')
    state=dict(schema='r_eligibility_tracking_control_v1',status='starting',protocol=ref(path),controller_pid=os.getpid(),completed_track={},completed_metric={},active=[],workers=[],worker_exits=[],resources=[])
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat();p=out/'state.pending.json';p.write_text(canonical(state),encoding='utf-8');os.replace(p,out/'driver_state.json')
    services=[];started=time.perf_counter()
    def batch(jobs):
        pending=deque(jobs);posts=deque();active={}
        while pending or posts or active:
            require(not(out/'STOP').exists(),'用户停止，保留partial不重放');require(all(s.process.is_alive() for s in services),'worker实际退出')
            snap=support.resource_snapshot();state['resources'].append(snap)
            for s in services:
                queue=pending if s.kind=='track' else posts
                if s.busy is not None or not queue or not support.enough_memory(snap,PROFILE):continue
                item=queue.popleft();job=item if s.kind=='track' else item['job'];op=s.kind;s.busy=job['job_id'];active[(op,s.busy)]=s
                task=dict(op=op,job=job,output=str(out/'runs'/job['job_id']/('tracking' if op=='track' else 'metric')))
                if op=='metric':task['tracking']=item['tracking']
                s.parent.send(task)
            state['active']=[dict(op=k[0],job_id=k[1],pid=s.process.pid) for k,s in active.items()];save()
            if not active:time.sleep(1);continue
            ready=wait([s.parent for s in active.values()],timeout=1)
            for key,s in list(active.items()):
                if s.parent not in ready:continue
                result=completed(s);s.busy=None;active.pop(key)
                if key[0]=='track':state['completed_track'][key[1]]=result;posts.append(result)
                else:state['completed_metric'][key[1]]=result
            save()
    save()
    try:
        for kind,count in (('track',2),('metric',1)):
            for i in range(count):s=Service(kind,cfg,out/'logs'/f'{kind}_{i}.log');services.append(s);state['workers'].append(s.ready);save()
        gate=[next(j for j in cfg['jobs'] if j['job_id']==gid) for gid in cfg['gate_job_ids']];state['status']='first_two_actual_metric_gate';save();batch(gate)
        for job in gate:
            p=read_ref(state['completed_metric'][job['job_id']]['report']);require(p['status']=='complete' and p['GT_rows']==cfg['expected_GT_rows'][job['sequence']]
                and p['DO_PREPROC'] is False and p['predictions_GT_filtered'] is False and p['GT_ID0_original'] is True,'首两源GT/ID0/全预测门禁失败')
        write_new(out/'first_two_actual_metric_gate.json',dict(status='complete_R_RS_two_sources_actual_metrics_ID0_full_predictions_gate',jobs=gate,reports=[state['completed_metric'][j['job_id']]['report'] for j in gate]))
        state['status']='tracking180_and_isolated_metrics';save();batch([j for j in cfg['jobs'] if j not in gate])
        require(len(state['completed_track'])==len(state['completed_metric'])==180,'完整180矩阵未齐')
        for s in services:state['worker_exits'].append(s.close());save()
        manifest=dict(schema='r_eligibility_tracking_manifest_v1',status='complete180_R_eligibility_tracking_and_evaluation',config_sha256=rt.sha(path),
            reports=[state['completed_metric'][j['job_id']] for j in cfg['jobs']],tracking=[state['completed_track'][j['job_id']] for j in cfg['jobs']],worker_exits=state['worker_exits'],new_optimizer_updates=0,test_read=False)
        write_new(out/'manifest.json',manifest);state['status']='analyzing_all_results';save()
        analysis=load('aligned_tracking_analysis',ROOT/'tools/research_ops/r_eligibility_tracking_analysis.py');report=analysis.analyze(path,out,out/'analysis_a01')
        require(report['status']=='complete180_R_eligibility_tracking_all540_results450_pairs75_metric15_gap_intervals','完整分析未闭合')
        state.update(status=STATUS,active=[],analysis=ref(out/'analysis_a01/report.json'),wall_seconds=time.perf_counter()-started);save();return state
    except BaseException:state.update(status='failed_preserved_no_implicit_replay',traceback=traceback.format_exc());save();raise
    finally:
        for s in services:
            if not s.closed:
                try:state['worker_exits'].append(s.close() if not s.busy and not s.task_failed else s.join_failed())
                except BaseException:state['worker_exits'].append(s.join_failed())
        save()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--numeric',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
    require(rt.sha(a.config)==a.config_sha256,'协议SHA不同');cfg=validate(a.config)
    if a.numeric:
        require(cfg['phase']=='numeric_admission','数值阶段不符')
        try:result=numeric(a.config,cfg)
        except BaseException:
            target=Path(cfg['numeric_output'])/'failed.json'
            if target.parent.exists() and not target.exists():write_new(target,dict(status='failed_preserved_no_implicit_replay',traceback=traceback.format_exc()))
            raise
    elif a.execute:require(cfg['phase']=='formal','正式阶段不符');result=execute(a.config,cfg)
    else:result=dict(status='readonly_R_eligibility_tracking_preflight',jobs=len(cfg['jobs']),processes=producers_absent())
    print(canonical(dict(status=result['status'])))
