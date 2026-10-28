"""复用十二训练域原日志的流式决策机会核查；零模型、零分配器调用。"""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
import gzip,hashlib,importlib.util,json,math,multiprocessing as mp,os,random,re,statistics,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import decision_opportunity_core as core
ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/decision_opportunity_a01'
STATUS='complete12_existing_train_logs_decision_opportunity_audit_no_new_tracking'
STOP_KEYS=('history_not_trusted_three','GT_presence_unknown','current_GT_absent','trusted_correct_raw_absent','correct_raw_not_in_stage','low_score_bbox_only','learned_inactive','correct_motion_gate_rejected','correct_not_enabled','correct_probability_rejected','cost_equality_unknown','correct_cost_above_threshold','actual_correct','actual_unmatched_with_strict_correct','actual_unknown_with_strict_correct','actual_known_wrong_with_strict_correct')
def require(ok,msg):
    if not ok:raise ValueError(msg)
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def safe(value):
    p=Path(os.path.abspath(value));require(R in p.parents,'只准DResearch')
    require(not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'测试封存')
    for x in (p,*p.parents):
        if x.exists() or x.is_symlink():require(not x.is_symlink() and not getattr(x.lstat(),'st_file_attributes',0)&0x400,'不跟随junction')
    return p
def sha(p):
    h=hashlib.sha256()
    with safe(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def ref(p):return dict(path=str(safe(p)),sha256=sha(p))
def checked(v):
    p=safe(v['path']);require(sha(p)==v['sha256'],'来源SHA不同：'+str(p));return p
def read(v):return json.loads(checked(v).read_text(encoding='utf-8-sig'))
def write(p,v):
    p=safe(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(canonical(v)+'\n')
def rows(v):
    count=0
    with gzip.open(checked(v),'rt',encoding='utf-8') as f:
        for line in f:count+=1;yield json.loads(line)
    require(count==v['rows'],'完整原日志行数不同')
def validate(path):
    cfg=json.loads(safe(path).read_text(encoding='utf-8-sig'))
    require(cfg['schema']=='decision_opportunity_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True
        and cfg['new_optimizer_updates']==cfg['new_model_forwards']==cfg['new_tracking']==cfg['new_solver_calls']==cfg['new_TrackEval']==0,'零更新后验边界不同')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只准新冻结闭包')
    for item in read(cfg['bundle_manifest'])['files']:require(sha(ROOT/item['path'])==item['sha256'],'冻结源码变化')
    old=read(cfg['source_state']);require(old['status']=='complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed' and not old['active'],'原诊断未闭合')
    closed=read(cfg['source_complete']);require(closed['status']=='complete12_train_diagnosis_verified_zero_eligible_no_oracle_effect_estimated'
        and closed['state']==cfg['source_state'] and closed['actual_all_research_producers_and_verifier_absent'] is True,'必须引用原独立完成根')
    require(len(cfg['units'])==12 and len({u['job']['job_id'] for u in cfg['units']})==12,'完整12来源缺失/重复')
    require({u['job']['sequence'] for u in cfg['units']}==set(cfg['sequences'])=={'SNMOT-060','SNMOT-097','SNMOT-151'},'只准原train三源')
    require(cfg['source_folds']=={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'},'原三比赛fold绝对映射不同')
    expected={(fold,regime,seq,20261024) for seq,heldout in cfg['source_folds'].items() for fold in ('game4','game6','game9') if fold!=heldout for regime in ('R','RS')}
    require({tuple(u['job'][k] for k in ('fold','regime','sequence','seed')) for u in cfg['units']}==expected,'完整两fold来源矩阵不同')
    for u in cfg['units']:
        j=u['job'];require(j['seed']==20261024 and j['regime'] in ('R','RS') and cfg['source_folds'][j['sequence']]!=j['fold'],'模型/heldout边界不同')
        require(old['observe'][j['job_id']]==u['observe'] and old['posthoc'][j['job_id']]==u['posthoc'],'须实际继承来源')
    require(cfg['worker_count']==2 and cfg['reserve_RAM_bytes']==8589934592 and cfg['reserve_commit_bytes']==6442450944
        and cfg['inflight_reserve_bytes']==3221225472 and cfg['bootstrap_seed']==20261028 and cfg['bootstrap_repeats']==10000,'资源/统计计划不同')
    cfg['_protocol']=ref(path)
    if cfg['phase']=='formal':
        admission=read(cfg['admission']);original=read(admission['protocol'])
        require(admission['status']=='complete_one750_existing_log_stream_admission' and admission['worker_joined'] is True
            and admission['unit']==cfg['inherit_completed'][cfg['units'][0]['job']['job_id']],'完整750准入/继承不符')
        for k in ('bundle','bundle_manifest','units','source_state','source_complete','sequences','source_folds','resource_source','reserve_RAM_bytes','reserve_commit_bytes','inflight_reserve_bytes','bootstrap_seed','bootstrap_repeats'):
            require(cfg[k]==original[k],'准入后改变来源/数值：'+k)
        require(set(cfg['inherit_completed'])=={cfg['units'][0]['job']['job_id']},'仅继承唯一750成功任务')
    else:require(cfg['phase']=='admission' and cfg['inherit_completed']=={},'只准独立完整750准入')
    return cfg
def job_run(cfg,unit):
    started=time.perf_counter();job=unit['job'];observe=read(unit['observe']);annotation=read(unit['posthoc'])
    require(observe['job']==annotation['job']==job and observe['frames']==annotation['total_frames']==750,'原750来源不同')
    require(annotation['observe']==unit['observe'] and annotation['new_solver_calls']==0,'后验来源不同')
    out=safe(cfg['control_root'])/'units'/job['job_id'];require(not out.exists(),'partial拒绝覆盖');out.mkdir(parents=True)
    source_rows=iter(rows(annotation['all_rows']));pending=next(source_rows,None);anchors={};stops=Counter();flags=defaultdict(Counter);absolute=Counter();pose={g:Counter() for g in ('correct','known_negative','unknown')};count=0;frames=0
    ledger=out/'rows.jsonl.gz'
    with gzip.open(ledger,'xt',encoding='utf-8',compresslevel=2) as sink:
        for frame in rows(observe['frames_log']):
            frames+=1;require(frame['frame_number']==frames,'原连续帧次序不同');group=[]
            while pending is not None and pending['frame_number']==frames:group.append(pending);pending=next(source_rows,None)
            require(pending is None or pending['frame_number']>frames,'后验次序不同')
            for row in core.analyze_frame(frame,group,anchors):
                count+=1;row['job']=job;sink.write(canonical(row)+'\n');stops[row['first_stop']]+=1;absolute.update(row['absolute_counts'])
                for k,v in row['flags'].items():require(v is None or type(v) is bool,'旗标须bool/null');flags[k]['null' if v is None else ('true' if v else 'false')]+=1
                for g,h in row['pose_shared_body_histograms'].items():pose[g].update(h)
    require(pending is None and frames==750 and count==annotation['all_rows']['rows'] and sum(stops.values())==count,'完整逐行join分母不同')
    result=dict(schema='decision_opportunity_unit_v1',status='complete',protocol=cfg['_protocol'],job=job,observe=unit['observe'],posthoc=unit['posthoc'],
        source_frames=observe['frames_log'],source_rows=annotation['all_rows'],ledger=dict(**ref(ledger),rows=count),frames=frames,stages=frames*3,
        row_count=count,first_stop={k:stops[k] for k in STOP_KEYS},flags={k:{v:c[v] for v in ('true','false','null')} for k,c in flags.items()},absolute_counts=dict(absolute),
        pose_shared_body_histograms={g:dict(h) for g,h in pose.items()},anchor_count=len(anchors),worker_pid=os.getpid(),wall_seconds=time.perf_counter()-started,
        new_optimizer_updates=0,new_model_forwards=0,new_tracking=0,new_solver_calls=0,new_TrackEval=0,test_read=False)
    require(not(set(stops)-set(STOP_KEYS)),'未登记首停类别');write(out/'receipt.json',result);return ref(out/'receipt.json')
def quantile(xs,p):
    index=(len(xs)-1)*p;i=int(index);return xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(index-i)
def describe(values):
    valid={k:v for k,v in values.items() if v is not None};n=len(valid)
    result=dict(source_rates=values,n_independent_sources=n,mean_rate_pp=None if not valid else statistics.mean(valid.values()),Student_t_95CI=None,
        percentile_match_bootstrap_95CI=None,leave_one_source_out_mean={},multiplicity_adjusted=False)
    if n!=3:return result
    xs=list(valid.values());m=statistics.mean(xs);half=4.302652729749462*statistics.stdev(xs)/math.sqrt(3);rng=random.Random(20261028)
    boots=sorted(statistics.mean(xs[rng.randrange(3)] for _ in range(3)) for _ in range(10000))
    result.update(Student_t_95CI=[m-half,m+half],percentile_match_bootstrap_95CI=[quantile(boots,.025),quantile(boots,.975)],
        leave_one_source_out_mean={k:statistics.mean(v for q,v in valid.items() if q!=k) for k in valid});return result
def summarize(cfg,refs):
    units=[read(x) for x in refs];require(len(units)==12 and sum(x['frames'] for x in units)==9000 and sum(x['row_count'] for x in units)==180118,'原完整分母不同')
    stops=sorted({k for x in units for k in x['first_stop']});flagkeys=sorted({k for x in units for k in x['flags']});descriptions={}
    for regime in ('R','RS'):
        group=[x for x in units if x['job']['regime']==regime];descriptions[regime]={}
        for kind,keys in (('first_stop',stops),('flags',flagkeys)):
            for key in keys:
                rates={}
                for seq in cfg['sequences']:
                    matched=[x for x in group if x['job']['sequence']==seq];require(len(matched)==2,'每源须匹配两fold')
                    vals=[]
                    for x in matched:
                        if kind=='first_stop':numerator=x[kind].get(key,0);denominator=x['row_count']
                        else:
                            c=x[kind][key];numerator=c['true'];denominator=c['true']+c['false']
                        vals.append(None if denominator==0 else 100*numerator/denominator)
                    rates[seq]=None if any(x is None for x in vals) else statistics.mean(vals)
                descriptions[regime][kind+':'+key]=describe(rates)
    return dict(schema='decision_opportunity_analysis_v1',status='complete12_existing_log_decision_opportunity_counts_and_source_intervals',protocol=cfg['_protocol'],
        units=refs,absolute_frames=9000,unique_source_frames=2250,stages=27000,rows=180118,first_stop_totals=dict(sum((Counter(x['first_stop']) for x in units),Counter())),
        flag_totals={k:{v:sum(x['flags'][k][v] for x in units) for v in ('true','false','null')} for k in flagkeys},
        descriptions=descriptions,interval_count=sum(len(x) for x in descriptions.values()),
        bootstrap_seed=20261028,bootstrap_repeats=10000,unit_folds_are_not_independent_sources=True,new_optimizer_updates=0,new_model_forwards=0,new_tracking=0,new_solver_calls=0,new_TrackEval=0,test_read=False,
        limitations=['只三个已见train比赛/首seed；无新AssA或Pose因果收益','当前历史身份不等最初目标；漂移后原anchor候选身份不可识别则保持未知',
            'enabled为已验旁观重算；成本等号单列未知，不重跑solver','Pose只衡量预测几何支持，非准确率/可见性或可纠正保证',
            '同源先均两fold再三源等权；所有区间未经多比较校正，缺源CI=null'])
def resources(cfg):
    p=checked(cfg['resource_source']);spec=importlib.util.spec_from_file_location('opportunity_resources',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def execute(path,cfg):
    require(cfg['phase']=='formal','正式执行必须先完整750准入并显式继承')
    out=safe(cfg['control_root']);require(EXP in out.parents and not out.exists(),'独立输出已有partial/成功');out.mkdir(parents=True)
    inherited=cfg.get('inherit_completed',{})
    for jid,value in inherited.items():
        body=read(value);unit=next(u for u in cfg['units'] if u['job']['job_id']==jid)
        require(body['status']=='complete' and body['job']==unit['job'] and body['observe']==unit['observe'] and body['posthoc']==unit['posthoc']
            and body['frames']==750 and body['row_count']==body['ledger']['rows'],'继承拒绝partial/错误来源')
        checked(body['ledger'])
    state=dict(status='started_not_committed',protocol=ref(path),controller_pid=os.getpid(),active=[],completed=dict(inherited),inherited_completed=dict(inherited),resources=[],worker_pids=[],new_optimizer_updates=0,test_read=False)
    def save():
        p=out/'state.pending';p.write_text(canonical(state),encoding='utf-8');os.replace(p,out/'driver_state.json')
    start=time.perf_counter();support=resources(cfg);pending=[u for u in cfg['units'] if u['job']['job_id'] not in inherited];active={};save()
    try:
        with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn')) as pool:
            while pending or active:
                require(not(out/'STOP').exists(),'用户停止，保留partial');snap=support.resource_snapshot();state['resources'].append(snap)
                while pending and len(active)<2 and snap['available_RAM_bytes']>=cfg['reserve_RAM_bytes']+(len(active)+1)*cfg['inflight_reserve_bytes'] and snap['commit_available_bytes']>=cfg['reserve_commit_bytes']+(len(active)+1)*cfg['inflight_reserve_bytes']:
                    unit=pending.pop(0);active[pool.submit(job_run,cfg,unit)]=unit['job']['job_id']
                state['active']=list(active.values());save()
                if not active:time.sleep(1);continue
                done,_=wait(active,timeout=1,return_when=FIRST_COMPLETED)
                for future in done:
                    jid=active.pop(future);value=future.result();body=read(value);state['completed'][jid]=value
                    if body['worker_pid'] not in state['worker_pids']:state['worker_pids'].append(body['worker_pid'])
            worker_processes=list(pool._processes.values())
        state['worker_exits']=[dict(worker_pid=p.pid,joined=True,process_exited=not p.is_alive(),exit_code=p.exitcode) for p in worker_processes]
        require(len(worker_processes)==2 and all(x['process_exited'] and x['exit_code']==0 for x in state['worker_exits']),'两后验worker未正常退出')
        require(len(state['completed'])==12,'全部12尚未完成');state.update(status='summarizing',active=[],workers_joined=True);save()
        ordered=[state['completed'][u['job']['job_id']] for u in cfg['units']];report=summarize(cfg,ordered);write(out/'report.json',report)
        state.update(status=STATUS,analysis=ref(out/'report.json'),wall_seconds=time.perf_counter()-start,active=[]);save();return state
    except BaseException:state.update(status='failed_preserved_no_implicit_replay',traceback=traceback.format_exc());save();raise
def admit(path,cfg):
    require(cfg['phase']=='admission','只准准入阶段');out=safe(cfg['admission_root']);require(not out.exists(),'准入已有partial');out.mkdir(parents=True)
    support=resources(cfg);samples=[];start=time.perf_counter()
    try:
        snap=support.resource_snapshot();require(snap['available_RAM_bytes']>=cfg['reserve_RAM_bytes']+cfg['inflight_reserve_bytes'] and snap['commit_available_bytes']>=cfg['reserve_commit_bytes']+cfg['inflight_reserve_bytes'],'准入资源不足')
        with ProcessPoolExecutor(max_workers=1,mp_context=mp.get_context('spawn')) as pool:
            future=pool.submit(job_run,cfg,cfg['units'][0])
            while not future.done():samples.append(support.resource_snapshot());wait([future],timeout=.5)
            value=future.result()
            worker_processes=list(pool._processes.values())
        exits=[dict(worker_pid=p.pid,joined=True,process_exited=not p.is_alive(),exit_code=p.exitcode) for p in worker_processes]
        require(len(exits)==1 and exits[0]['process_exited'] and exits[0]['exit_code']==0,'单准入worker未正常退出')
        result=dict(status='complete_one750_existing_log_stream_admission',protocol=ref(path),unit=value,worker_joined=True,
            worker_exits=exits,resources=samples,wall_seconds=time.perf_counter()-start,new_optimizer_updates=0,new_model_forwards=0,new_tracking=0,new_solver_calls=0,new_TrackEval=0,test_read=False)
        write(out/'receipt.json',result);return result
    except BaseException:write(out/'failed.json',dict(status='failed_preserved_no_replay',traceback=traceback.format_exc()));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--admit',action='store_true');args=p.parse_args();cfg=validate(args.config)
    require(not(args.admit and args.execute),'一次只执行一阶段')
    result=admit(args.config,cfg) if args.admit else (execute(args.config,cfg) if args.execute else dict(status='readonly12_existing_log_decision_opportunity_preflight'))
    print(canonical(dict(status=result['status'])))
