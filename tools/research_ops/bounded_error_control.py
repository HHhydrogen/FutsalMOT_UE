"""一次有边界条件账本：复用已验worker生命周期和资源函数，不重跑追踪/评分。"""
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

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/bounded_error_decomposition_a01'
ROOT=Path(__file__).resolve().parents[2]
BASE_PATH=R/'code/70a399c65ff8cf7f2ef7090a0739ab161ff5b59b338c419f54e0c6c1238645f7/tools/research_ops/tracking_policy_ledger_control.py'
BASE_SHA='7cb703e6e38a8d285ca397190647573b051e168ac8d3a5ffc9877d29f97599f6'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m
    previous=sys.dont_write_bytecode
    try:sys.dont_write_bytecode=True;spec.loader.exec_module(m)
    finally:sys.dont_write_bytecode=previous
    return m

if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('原已验调度纯函数来源改变')
base=load('bounded_existing_ledger_service',BASE_PATH)
require,canonical,physical,sha,ref,checked,read,write_new=(base.require,base.canonical,base.physical,base.sha,base.ref,base.checked,base.read,base.write_new)
STATUS='complete27_existing_traces_bounded_error_conditions_and_intervals_workers_exited'
PANELS=('original_heldout','old_external')
PROFILE=dict(analysis_workers=2,numeric_threads=1,reserve_RAM_bytes=8589934592,reserve_commit_bytes=6442450944,startup_estimate_bytes=268435456)

def validate(path):
    cfg=read(path)
    require(cfg['schema']=='bounded_error_decomposition_protocol_v1' and cfg['approved_by']=='root'
        and cfg['execute_authorized'] is True and cfg['test_sealed'] is True,'独立零更新授权/封存缺失')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','仅执行最小冻结bundle')
    for e in read(checked(cfg['bundle_manifest']))['files']:require(sha(ROOT/e['path'])==e['sha256'],'活动源码改变')
    inv=read(checked(cfg['inventory']))
    require(inv['status']=='complete_metadata_inventory27_existing_trace63_missing_no_cache_GT_model_or_tracking'
        and cfg['units']==inv['units'] and cfg['panels']==inv['panels'] and cfg['source_ledgers']==inv['source_ledgers'],'不能换源/筛seed或trace')
    require(inv['counts']==dict(sources=12,strong_motion_units=90,trace_units=27,missing_trace_units=63,
        existing_trace_stage_calls=24863,existing_trace_stage_rows=320752,assignment_reference_units=9),'完整既有范围不同')
    require(cfg['unit_order']==[u['unit_id'] for u in cfg['units']] and cfg['worker_profile']==PROFILE
        and Path(cfg['output_root'])==EXP and Path(cfg['analysis_root'])==EXP/'analysis_a01','固定来源顺序/资源/输出不同')
    require(cfg['optimizer_updates']==cfg['new_scores']==cfg['new_free_tracking']==cfg['new_TrackEval_runs']==0
        and cfg['condition_labels_are_causes'] is False and cfg['new_seven_internal_states']=='unknown_not_recorded',
        '不能把后验条件冒充因果或补造新七场内部日志')
    require(sha(BASE_PATH)==BASE_SHA and cfg['worker_service']==ref(BASE_PATH),'已验worker来源不同')
    if cfg['phase']=='formal':
        proof=read(checked(cfg['numeric_admission']))
        require(proof['passed'] is True and proof['source_units']==9 and proof['numeric_sources']==cfg['numeric']
            and proof['status']=='complete9_saved_stage_assignments_original_FP32_solver_exact_no_model','数值准入未齐')
    else:require(cfg['phase']=='numeric_admission','未知阶段不能默认执行')
    return cfg

def producers_absent():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',check=True)
    rows=json.loads(p.stdout) if p.stdout.strip() else [];rows=[rows] if isinstance(rows,dict) else rows
    own={os.getpid()};byid={v['ProcessId']:v for v in rows};node=byid.get(os.getpid())
    while node and node['ParentProcessId'] in byid:
        parent=byid[node['ParentProcessId']]
        if 'bounded_error_control.py' not in (parent.get('CommandLine') or ''):break
        own.add(parent['ProcessId']);node=parent
    pattern=re.compile(r'(?:^|[\\/\s\"\x27])(?:bounded_error_control|ocsort_(?:threshold|cached)_(?:control|admission)|pose_velocity_(?:tracking_control|learning_train|decision_probe))[.]py(?=$|[\s\"\x27])',re.I)
    blocked=[v for v in rows if v['ProcessId'] not in own and ((v.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(v.get('CommandLine') or ''))]
    require(not blocked,'既有生产者仍在，不启动或抢资源：'+canonical(blocked))
    return dict(actual_CIM_checked=True,related_producers_absent=True,own_launcher_chain=sorted(own))

def numeric_admission(path,cfg):
    producers_absent();output=EXP/'numeric_admission_a01/receipt.json'
    require(not output.parent.exists(),'未知数值partial拒绝覆盖');output.parent.mkdir(parents=True)
    write_new(output.parent/'intent.json',dict(protocol=ref(path),optimizer_updates=0,new_scores=0,test_read=False))
    try:
        core=load('bounded_numeric_core',ROOT/'tools/research_ops/bounded_error_decomposition.py')
        proof=core.verify_saved_assignments(cfg,output);producers_absent()
        return dict(status=proof['status'],receipt=ref(output),events=proof['event_count'])
    except BaseException:
        write_new(output.parent/'failed.json',dict(status='failed_numeric_partial_preserved',traceback=traceback.format_exc(),implicit_replay=False))
        raise

def unit_rates(summary,all_keys):
    rows={}
    for key in all_keys:
        if key.startswith('denominator/'):continue
        numerator=summary['counts'].get(key,0)
        denominator=summary['native_stage_outcome_rows'] if key.startswith('native_outcome/') else summary['stage_rows']
        rows[key]=None if denominator==0 else 100*numerator/denominator
    for leaf in ('positive_outside_effective_gate','no_single_edge_feasible_positive','known_negative_cost_lower',
        'minimum_cost_tie','global_competition_or_solver_unmatched','unknown_competition_or_assignment','reference_stage_selected_correct'):
        denom=summary['known_active_current_present_rows']
        rows['active_current_present/'+leaf]=None if not denom else 100*summary['counts'].get('first_stop/'+leaf,0)/denom
    return rows

def summarize(cfg,results,output):
    require(len(results)==27 and set(results)==set(cfg['unit_order']),'完整27不能挑结果')
    require(sum(v['stage_rows'] for v in results.values())==320752 and sum(v['events'] for v in results.values())==24863,'完整row/事件分母不同')
    require(all(sum(v['first_stop_counts'].values())==v['stage_rows'] and v['first_stop_is_cause'] is False for v in results.values()),'互斥标签不能当因果')
    keys=sorted({k for s in results.values() for k in s['counts']});unit_rows=[];rates={}
    for uid in cfg['unit_order']:
        s=results[uid];rates[uid]=unit_rates(s,keys)
        unit_rows.append(dict(unit_id=uid,sequence=s['sequence'],fold=s['fold'],seed=s['seed'],events=s['events'],
            stage_rows=s['stage_rows'],known_active_current_present_rows=s['known_active_current_present_rows'],
            native_stage_outcome_rows=s['native_stage_outcome_rows'],**{k:s['counts'].get(k,0) for k in keys}))
    base.write_csv(output/'all_units.csv',unit_rows)
    rate_keys=sorted(next(iter(rates.values())));match_rows=[];descriptions={}
    for panel in PANELS:
        for sequence in cfg['panels'][panel]:
            units=[u for u in cfg['units'] if u['sequence']==sequence]
            for key in rate_keys:
                values=[rates[u['unit_id']][key] for u in units];valid=[v for v in values if v is not None]
                match_rows.append(dict(panel=panel,sequence=sequence,condition=key,total_training_units=len(values),
                    units_with_denominator=len(valid),rate_pp=sum(valid)/len(valid) if valid else None,
                    zero_denominator_units_preserved=len(values)-len(valid)))
    base.write_csv(output/'all_match_condition_rates.csv',match_rows)
    stats=load('bounded_existing_interval_function',checked(cfg['interval_source']))
    for panel in PANELS:
        descriptions[panel]={}
        for key in rate_keys:
            values={r['sequence']:r['rate_pp'] for r in match_rows if r['panel']==panel and r['condition']==key and r['rate_pp'] is not None}
            value=stats.effect_intervals(values) if len(values)>=2 else dict(n_independent_matches=len(values),mean_delta_pp=next(iter(values.values()),None),Student_t_95CI=None,percentile_match_bootstrap_95CI=None,leave_one_match_out_mean={})
            value['statistic']='observed_condition_rate_pp_not_performance_delta_or_causal_error_fraction'
            value['zero_denominator_matches_retained_null']=[s for s in cfg['panels'][panel] if s not in values]
            descriptions[panel][key]=value
    inventory=read(checked(cfg['inventory']))
    coverage=[dict(sequence=u['sequence'],fold=u['fold'],seed=u['seed'],unit_id=u['unit_id'],
        internal_trace='available_balanced_old_five' if any(t['original_unit_id']==u['unit_id'] for t in cfg['units']) else 'unknown_not_recorded') for u in inventory['strong_units']]
    base.write_csv(output/'all90_internal_coverage.csv',coverage)
    report=dict(schema='bounded_error_decomposition_report_v1',status='complete27_bounded_conditions_all_rows_intervals63_missing_preserved',
        protocol=ref(Path(cfg['_config_path'])),inventory=cfg['inventory'],numeric_admission=cfg['numeric_admission'],
        unit_summaries=[ref(output/'units'/uid/'summary.json') for uid in cfg['unit_order']],
        all_units=dict(ref(output/'all_units.csv'),rows=27),all_match_condition_rates=dict(ref(output/'all_match_condition_rates.csv'),rows=len(match_rows)),
        all_internal_coverage=dict(ref(output/'all90_internal_coverage.csv'),rows=90),condition_intervals=descriptions,
        counts=dict(trace_units=27,missing_trace_units=63,source_matches_with_internal_trace=5,source_matches_total=12,
            stage_calls=24863,stage_rows=320752),first_stop_is_cause=False,all_negative_unknown_and_zero_denominators_retained=True,
        seven_observed_internal_conditions='unknown_not_recorded_no_interval',unrecorded_low_stage_empty_and_lifecycle='unknown',
        all_video_event_denominator=False,GT_only_posthoc=True,optimizer_updates=0,new_scores=0,new_free_tracking=0,new_TrackEval_runs=0,
        test_read=False,formal_equivalence_or_noninferiority=False,performance_margin=None,
        factor_selected_by_this_code=False,previous_12_output_evidence=cfg['previous_12_output_evidence'])
    write_new(output/'report.json',report);return report

def worker_service(connection,cfg,log):
    try:
        with Path(log).open('x',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            core=load('bounded_worker_core',ROOT/'tools/research_ops/bounded_error_decomposition.py');jobs=0
            connection.send(dict(status='ready',worker_pid=os.getpid()))
            while True:
                task=connection.recv()
                if task['op']=='close':
                    modules=[n for n in sys.modules if n.split('.')[0] in ('torch','ultralytics','trackeval')]
                    require(not modules,'后验worker意外载入模型/追踪模块')
                    connection.send(dict(status='closed',worker_pid=os.getpid(),jobs=jobs,GT_loaded_only_posthoc=True,
                        model_tracker_TrackEval_modules_loaded=modules));break
                unit=next(u for u in cfg['units'] if u['unit_id']==task['unit_id'])
                core.analyze_unit(cfg,unit,task['output']);jobs+=1
                connection.send(dict(status='complete',unit_id=unit['unit_id'],worker_pid=os.getpid(),summary=ref(Path(task['output'])/'summary.json')))
    except BaseException:
        try:connection.send(dict(status='failed',worker_pid=os.getpid(),traceback=traceback.format_exc()))
        except (EOFError,BrokenPipeError):pass
    finally:connection.close()

class Service(base.Service):
    def __init__(self,cfg,log):
        ctx=mp.get_context('spawn');self.parent,child=ctx.Pipe();self.busy=None;self.closed=False;self.task_failed=False
        self.process=ctx.Process(target=worker_service,args=(child,cfg,str(log)));self.process.start();child.close()
        try:
            self.ready=self.receive();require(self.ready['status']=='ready' and self.ready['worker_pid']==self.process.pid,'worker未就绪')
        except BaseException as error:
            evidence=self.join_failed();write_new(Path(log).with_suffix('.startup_failed.json'),dict(evidence,error=repr(error)));raise

def execute(path,cfg):
    producers_absent();output=physical(cfg['analysis_root']);require(not output.exists(),'独占新分析目录，partial不覆盖')
    output.mkdir();(output/'logs').mkdir();(output/'units').mkdir();support=load('bounded_resource_support',checked(cfg['worker_support']))
    state=dict(status='starting2_bounded_posthoc_workers',protocol=ref(path),created_utc=datetime.now(timezone.utc).isoformat(),parent_pid=os.getpid(),
        workers=[],worker_exits=[],completed=[],active=[],resources=[],optimizer_updates=0,new_scores=0,new_free_tracking=0,new_TrackEval_runs=0,test_read=False)
    def save():
        p=output/'state.pending.json';p.write_text(canonical(state),encoding='utf-8');os.replace(p,output/'state.json')
    services=[];pending=deque(cfg['unit_order']);results={};stopped=False;paused=None;started=time.perf_counter();save()
    try:
        require(support.enough_memory(support.resource_snapshot(),PROFILE,2),'实际内存余量不足')
        for i in range(2):
            s=Service(cfg,output/'logs'/f'analysis_{i}.log');services.append(s);state['workers'].append(s.ready)
        while pending or any(s.busy for s in services):
            if (output/'STOP').exists():stopped=True
            snapshot=support.resource_snapshot()
            import psutil
            rss=0
            for process in [psutil.Process()]+psutil.Process().children(recursive=True):
                try:rss+=process.memory_info().rss
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            snapshot['sampled_process_tree_RSS_bytes']=rss;state['resources'].append(snapshot)
            for s in services:
                if s.busy or not pending or stopped:continue
                if not support.enough_memory(snapshot,PROFILE):
                    paused=paused or time.monotonic();require(time.monotonic()-paused<600,'资源不足持续超时，保留partial');continue
                paused=None;uid=pending.popleft();s.parent.send(dict(op='analyze',unit_id=uid,output=str(output/'units'/uid)));s.busy=uid
            state.update(status='running27_bounded_posthoc_conditions',active=[dict(unit_id=s.busy,worker_pid=s.ready['worker_pid']) for s in services if s.busy]);save()
            busy=[s for s in services if s.busy]
            if not busy:
                if stopped:break
                time.sleep(.5);continue
            available=wait([s.parent for s in busy],timeout=1)
            for s in busy:
                if s.parent not in available:continue
                message=s.receive();uid=s.busy;s.busy=None
                require(message['status']=='complete' and message['unit_id']==uid and message['worker_pid']==s.ready['worker_pid'],'完成项身份不同')
                require(uid not in results,'不能重放源任务');results[uid]=read(checked(message['summary']));state['completed'].append(message);save()
        for s in services:state['worker_exits'].append(s.close())
        state['active']=[];state['actual_exit_gate']=producers_absent();save()
        if stopped:state['status']='stopped_by_user_partial_preserved';save();return state['status']
        summarize(cfg,results,output);state.update(status=STATUS,report=ref(output/'report.json'),wall_seconds=time.perf_counter()-started);save()
        return dict(status=STATUS,units=27,stage_rows=320752,new_scores=0)
    except BaseException as error:
        for s in services:
            if s.closed:continue
            try:
                if s.task_failed:state['worker_exits'].append(s.join_failed());continue
                if s.busy:s.receive();s.busy=None
                state['worker_exits'].append(s.close())
            except BaseException as closing:
                state.setdefault('failure_exit_evidence',[]).append(repr(closing));state['worker_exits'].append(s.join_failed())
        state.update(status='failed_partial_preserved_no_implicit_replay',error=repr(error),traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256');p.add_argument('--execute',action='store_true');args=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    cfg=validate(args.config);cfg['_config_path']=str(args.config)
    if not args.execute:result=dict(status='readonly_bounded27_protocol_no_data_analysis',phase=cfg['phase'])
    else:
        require(sha(args.config)==args.config_sha256,'执行配置SHA不同')
        result=numeric_admission(args.config,cfg) if cfg['phase']=='numeric_admission' else execute(args.config,cfg)
    print(canonical(result))
