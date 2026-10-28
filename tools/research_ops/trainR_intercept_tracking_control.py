"""训练R截距唯一180项CPU追踪/GT评价与自动配对，复用已验worker生命周期。"""
import argparse
from collections import deque
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime,timezone
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

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/trainR_intercept_calibration_a01';ROOT=Path(__file__).resolve().parents[2]
BASE=R/'code/70a399c65ff8cf7f2ef7090a0739ab161ff5b59b338c419f54e0c6c1238645f7/tools/research_ops/tracking_policy_ledger_control.py'
BASE_SHA='7cb703e6e38a8d285ca397190647573b051e168ac8d3a5ffc9877d29f97599f6'
STATUS='complete180_trainR_intercept_tracking_and_paired_analysis'
PROFILE=dict(track_workers=2,metric_workers=1,numeric_threads=1,cache_limit_bytes=134217728,cache_max_sequences=2,
    model_cache_limit_bytes=268435456,model_cache_max_entries=3,reserve_RAM_bytes=8589934592,reserve_commit_bytes=6442450944,startup_estimate_bytes=268435456)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m
    previous=sys.dont_write_bytecode
    try:sys.dont_write_bytecode=True;spec.loader.exec_module(m)
    finally:sys.dont_write_bytecode=previous
    return m
if hashlib.sha256(BASE.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('已验Service源码改变')
base=load('intercept_track_existing_service',BASE)
require,canonical,physical,sha,ref,checked,read,write_new=(base.require,base.canonical,base.physical,base.sha,base.ref,base.checked,base.read,base.write_new)

def producers_absent():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',check=True)
    rows=json.loads(p.stdout) if p.stdout.strip() else [];rows=[rows] if isinstance(rows,dict) else rows
    own={os.getpid()};byid={v['ProcessId']:v for v in rows};node=byid.get(os.getpid())
    while node and node['ParentProcessId'] in byid:
        parent=byid[node['ParentProcessId']]
        if 'trainR_intercept_tracking_control.py' not in (parent.get('CommandLine') or ''):break
        own.add(parent['ProcessId']);node=parent
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:trainR_intercept_(?:fit_control|fit_job|tracking_control)|ocsort_(?:threshold|cached)_control|pose_velocity_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
    blocked=[v for v in rows if v['ProcessId'] not in own and ((v.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(v.get('CommandLine') or ''))]
    require(not blocked,'相关生产者仍在，不重复启动：'+canonical(blocked))
    return dict(actual_CIM_checked=True,related_producers_absent=True,own_launcher_chain=sorted(own))

def validate(path):
    cfg=read(path)
    require(cfg['schema']=='trainR_intercept_tracking_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True
        and cfg['formal_equivalence_or_noninferiority'] is False and cfg['alias_enabled'] is False,'独立单因素/测试边界缺失')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code' and Path(cfg['output_root'])==EXP
        and Path(cfg['control_root'])==EXP/'tracking_control_a01','仅独立固定bundle/输出')
    for item in read(checked(cfg['bundle_manifest']))['files']:require(sha(ROOT/item['path'])==item['sha256'],'冻结源码改变')
    inv=read(checked(cfg['inventory']));done=read(checked(cfg['fit_complete']));original=read(checked(cfg['source_velocity_protocol']))
    require(done['schema']=='trainR_intercept_fit_complete_v1' and done['status']=='complete18_trainR_only_scalar_calibrations_full_records_and_exit_verified'
        and done['fit_processes_absent'] is True and cfg['calibrations']==done['calibrations'],'完整标量拟合/实际退出未闭合')
    require(done['totals']['models']==18 and done['totals']['clean_R_model_window_evaluations']==18000 and done['totals']['optimizer_updates']==0,'额外校准预算不可混入原训练')
    require(cfg['sources']==inv['sources']==original['sources'] and cfg['panels']==inv['panels']==original['panels']
        and cfg['registries']==original['registries'] and cfg['worker_profile']==PROFILE,'不能变12源/面板/事件分母/数值线程')
    expected={(b['model_id'],b['regime'],b['fold'],b['seed'],b['sequence']) for b in inv['baseline_units']}
    actual={(j['model_id'],j['regime'],j['fold'],j['seed'],j['sequence']) for j in cfg['jobs']}
    require(len(cfg['jobs'])==len(actual)==180 and actual==expected and len({j['job_id'] for j in cfg['jobs']})==180,'180完整新/历史配对矩阵不同')
    gates=[j for jid in cfg['gate_job_ids'] for j in cfg['jobs'] if j['job_id']==jid]
    require(len(gates)==2 and {j['regime'] for j in gates}=={'R','RS'}
        and {j['sequence'] for j in gates}=={'SNMOT-060','v_2QhNRucNC7E_c017'},'首R/RS实际两源评价门禁不同')
    require(cfg['worker_service']==ref(BASE),'已验Service来源不同')
    for entry in cfg['registries'].values():
        public=read(checked(entry['receipt']));require(public['contains_GT_coordinates'] is False and public['registry']==entry['registry'],'track只读公开无坐标元数据')
    if cfg['phase']=='formal':
        proof=read(checked(cfg['numeric_admission']))
        require(cfg['tracking_authorized'] is True and cfg['numeric_authorized'] is False
            and proof['status']=='complete_trainR_intercept_cold_ABA_spawn_beta0_original_exact_numeric_admission'
            and proof['passed'] is True and proof['fit_complete']==cfg['fit_complete'],'实际原输出/常驻/GT边界准入未齐')
        admission=read(checked(proof['config']))
        require(admission['phase']=='numeric_admission' and admission['numeric_authorized'] is True
            and admission['tracking_authorized'] is False,'不能用正式输出倒签数值准入')
        for key in ('bundle','bundle_manifest','inventory','fit_complete','calibrations','sources','panels','registries','jobs',
            'source_velocity_protocol','runtime_source','inputs_source','track_guard_source','tracker_parameters','worker_profile','gate_job_ids'):
            require(admission[key]==cfg[key],'数值准入后不能换来源/参数：'+key)
        require(proof['all_workers_joined_exited'] is True and proof['unique_source_frames']==96
            and proof['diagnostic_frame_consumptions']==528 and proof['alias_used'] is False,'真实小样本/退出/诊断预算不同')
        comparisons=list(proof['beta0_original_comparisons'].values())+[v['comparison'] for v in proof['persistent_ABA']]+[v['comparison'] for v in proof['independent_spawn_A']]
        require(len(comparisons)==7 and all(v['original_ID_MOT_exact'] and v['raw_native_frames_exact']
            and v['frame_counts_exact'] and v['audit_exact'] and v['frames']==48 for v in comparisons),'完整原输出数值门禁未齐')
        require(len(proof['independent_spawn_A'])==2 and all(v['closure']['joined'] is True and v['closure']['exitcode']==0
            and v['closure']['actual_PID_absent_after_join'] is True for v in proof['independent_spawn_A']),'独立spawn实际退出门禁未齐')
    else:require(cfg['phase']=='numeric_admission' and cfg['tracking_authorized'] is False and cfg['numeric_authorized'] is True,'数值诊断不授权全追踪')
    cfg['_protocol_ref']=ref(path);cfg['_config_path']=str(path)
    return cfg

def worker(connection,kind,cfg,log):
    try:
        with Path(log).open('x',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            runtime=load('intercept_tracking_runtime',ROOT/'tools/research_ops/trainR_intercept_tracking.py');jobs=0
            connection.send(dict(status='ready',kind=kind,worker_pid=os.getpid()))
            while True:
                task=connection.recv()
                if task['op']=='close':
                    closure=(runtime.close_track_worker if kind=='track' else runtime.close_metric_worker)()
                    connection.send(dict(status='closed',worker_pid=os.getpid(),jobs=jobs,kind=kind,closure=closure));break
                job=next(j for j in cfg['jobs'] if j['job_id']==task['job_id'])
                method=runtime.track_job if kind=='track' else runtime.metric_job
                result=method(cfg,job,task['output']);jobs+=1
                # 只传递磁盘收据引用；完整MOT/audit不通过父进程复制。
                connection.send(dict(status='complete',kind=kind,worker_pid=os.getpid(),job_id=job['job_id'],result=result))
    except BaseException:
        try:connection.send(dict(status='failed',kind=kind,worker_pid=os.getpid(),traceback=traceback.format_exc()))
        except (EOFError,BrokenPipeError):pass
    finally:connection.close()

class Service(base.Service):
    def __init__(self,kind,cfg,log):
        ctx=mp.get_context('spawn');self.parent,child=ctx.Pipe();self.busy=None;self.closed=False;self.task_failed=False;self.kind=kind
        self.process=ctx.Process(target=worker,args=(child,kind,cfg,str(log)));self.process.start();child.close()
        try:self.ready=self.receive();require(self.ready['status']=='ready' and self.ready['kind']==kind,'worker未正确就绪')
        except BaseException:self.join_failed();raise

def execute(path,cfg):
    producers_absent();out=physical(cfg['control_root']);require(not out.exists(),'未知tracking partial拒绝覆盖');out.mkdir();(out/'logs').mkdir();(out/'runs').mkdir()
    support=load('intercept_track_resource_support',checked(cfg['worker_support']));started=time.perf_counter()
    pending=deque(cfg['gate_job_ids']);remainder=[j['job_id'] for j in cfg['jobs'] if j['job_id'] not in cfg['gate_job_ids']]
    metric_pending=deque();results={};services=[];paused=None;gate_passed=False
    state=dict(status='starting2_track1_metric_workers',protocol=ref(path),parent_pid=os.getpid(),created_utc=datetime.now(timezone.utc).isoformat(),
        workers=[],worker_exits=[],completed_tracking=[],completed_metrics=[],active=[],resources=[],optimizer_updates=0,test_read=False)
    def save():
        p=out/'state.pending.json';p.write_text(canonical(state),encoding='utf-8');os.replace(p,out/'driver_state.json')
    save()
    try:
        require(support.enough_memory(support.resource_snapshot(),PROFILE,3),'启动内存预留不足')
        for kind,count in (('track',2),('metric',1)):
            for i in range(count):
                s=Service(kind,cfg,out/'logs'/f'{kind}_{i}.log');services.append(s);state['workers'].append(s.ready)
        while pending or metric_pending or any(s.busy for s in services) or not gate_passed:
            require(not (out/'STOP').exists(),'用户取消，保留partial不重开')
            snapshot=support.resource_snapshot();import psutil
            rss=0
            for p in [psutil.Process()]+psutil.Process().children(recursive=True):
                try:rss+=p.memory_info().rss
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            snapshot['sampled_process_tree_RSS_bytes']=rss;state['resources'].append(snapshot)
            for s in services:
                queue=pending if s.kind=='track' else metric_pending
                if s.busy or not queue:continue
                if not support.enough_memory(snapshot,PROFILE):
                    paused=paused or time.monotonic();require(time.monotonic()-paused<600,'资源不足超时，保留partial');continue
                paused=None;jid=queue.popleft();(out/'runs'/jid).mkdir(exist_ok=True)
                destination=out/'runs'/jid/('tracking' if s.kind=='track' else 'metric')
                s.parent.send(dict(op=s.kind,job_id=jid,output=str(destination)));s.busy=jid
            state.update(status='running180_trainR_intercept_tracking_and_metrics',active=[dict(job_id=s.busy,kind=s.kind,pid=s.ready['worker_pid']) for s in services if s.busy]);save()
            busy=[s for s in services if s.busy]
            if not busy:time.sleep(.5);continue
            available=wait([s.parent for s in busy],timeout=1)
            for s in busy:
                if s.parent not in available:continue
                message=s.receive();jid=s.busy;s.busy=None
                require(message['status']=='complete' and message['kind']==s.kind and message['job_id']==jid,'worker完成身份不同')
                if s.kind=='track':state['completed_tracking'].append(message);metric_pending.append(jid)
                else:
                    require(jid not in results,'不能重放成功评价');results[jid]=ref(out/'runs'/jid/'metric/report.json');state['completed_metrics'].append(message)
                save()
            if not gate_passed and all(jid in results for jid in cfg['gate_job_ids']):
                gate_passed=True;pending.extend(remainder)
                write_new(out/'first_R_RS_actual_metric_gate.json',dict(status='complete2_original_R_RS_calibrated_actual_tracking_metric_gate',
                    protocol=ref(path),reports={jid:results[jid] for jid in cfg['gate_job_ids']},GT_ID0_legal=True,
                    DO_PREPROC=False,all_prediction_rows_retained=True,new_optimizer_updates=0,test_read=False))
                state['first_R_RS_actual_gate_passed']=True;save()
        for s in services:state['worker_exits'].append(s.close())
        state['active']=[];state['actual_exit_gate']=producers_absent();save()
        require(len(results)==len(state['completed_tracking'])==len(state['completed_metrics'])==180,'不能少项汇总')
        manifest=dict(schema='trainR_intercept_tracking_manifest_v1',status='complete180_trainR_intercept_tracking_and_evaluation',
            config_sha256=ref(path)['sha256'],reports=[dict(job=j,report=results[j['job_id']]) for j in cfg['jobs']],worker_exits=state['worker_exits'])
        write_new(out/'manifest.json',manifest)
        analysis=load('intercept_paired_analysis',ROOT/'tools/research_ops/trainR_intercept_analysis.py')
        analysis.analyze(path,out,out/'analysis_a01')
        state.update(status=STATUS,manifest=ref(out/'manifest.json'),report=ref(out/'analysis_a01/report.json'),wall_seconds=time.perf_counter()-started);save()
        return dict(status=STATUS,completed=180,report=state['report'],wall_seconds=state['wall_seconds'])
    except BaseException as error:
        for s in services:
            if s.closed:continue
            try:
                if s.task_failed:state['worker_exits'].append(s.join_failed());continue
                if s.busy:s.receive();s.busy=None
                state['worker_exits'].append(s.close())
            except BaseException:state['worker_exits'].append(s.join_failed())
        state.update(status='failed_partial_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256');p.add_argument('--execute',action='store_true');args=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    cfg=validate(args.config)
    if not args.execute:result=dict(status='readonly_trainR_intercept_tracking180_preflight',phase=cfg['phase'])
    else:
        require(sha(args.config)==args.config_sha256,'配置SHA不匹配')
        if cfg['phase']=='numeric_admission':
            producers_absent();runtime=load('intercept_tracking_numeric',ROOT/'tools/research_ops/trainR_intercept_tracking.py')
            result=runtime.numeric_admission(cfg,args.config,EXP/'tracking_numeric_admission_a01');producers_absent()
        else:result=execute(args.config,cfg)
    print(canonical(result))
