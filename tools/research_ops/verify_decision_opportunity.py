"""独立终验十二份新决策机会账本；不读原帧日志、GT、缓存、权重或执行分类器。"""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime,timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
from statistics import mean,stdev
import stat
import subprocess
import sys
import traceback

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/decision_opportunity_a01'
FOLDS=('game4','game6','game9');REGIMES=('R','RS');SEQUENCES=('SNMOT-060','SNMOT-097','SNMOT-151')
SOURCE_FOLDS=dict(zip(SEQUENCES,FOLDS));STAGES=('high_score','low_score','unconfirmed')
THRESHOLDS=dict(high_score=.8,low_score=.5,unconfirmed=.7)
STOPS=('history_not_trusted_three','GT_presence_unknown','current_GT_absent','trusted_correct_raw_absent','correct_raw_not_in_stage',
    'low_score_bbox_only','learned_inactive','correct_motion_gate_rejected','correct_not_enabled','correct_probability_rejected','cost_equality_unknown',
    'correct_cost_above_threshold','actual_correct','actual_unmatched_with_strict_correct','actual_unknown_with_strict_correct','actual_known_wrong_with_strict_correct')
FLAGS=('trusted_three_history','learned_active','positive_motion_gate','positive_enabled','strict_cost_feasible','cost_equality_unknown','actual_correct',
    'actual_known_wrong','actual_selection_unknown','actual_unmatched','known_wrong_cheaper_or_equal','unknown_competition','unknown_enabled_competition',
    'positive_owned_elsewhere','earliest_stage_trusted3_anchor_drift','local_opportunity','pose_gap_1_to30','pose_gap_unknown','pose_gap_outside_1_to30',
    'raw_correct_in_other_stage','raw_correct_owned_in_other_stage_other_track','local_opportunity_pose_supported_both',
    'local_opportunity_pose_supported_actual_noncorrect','local_opportunity_pose_supported_actual_known_wrong',
    'local_opportunity_pose_supported_actual_unmatched','local_opportunity_pose_supported_actual_unknown')
GROUPS=('correct','known_negative','unknown');HISTOGRAM_KEYS=tuple(str(k) for k in range(13))+('history_missing',)
ZERO_KEYS=('new_optimizer_updates','new_model_forwards','new_tracking','new_solver_calls','new_TrackEval')
DONE='complete12_existing_train_logs_decision_opportunity_audit_no_new_tracking'
ANALYSIS_DONE='complete12_existing_log_decision_opportunity_counts_and_source_intervals'
STATUS='complete12_decision_opportunity_sources_rows_counts_intervals_and_exit_verified'
TOLERANCE=1e-8  # 序列化核验精度，不是性能或等效界限。


def require(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def physical(value):
    p=Path(value);require(p.is_absolute(),'必须绝对物理来源');p=Path(os.path.abspath(p))
    require(R in p.parents and not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'研究根之外或测试仍封存')
    for x in (p,*p.parents):
        if x.exists() or x.is_symlink():
            info=x.lstat();require(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,'不跟随链接/junction')
    return p


def sha(path):
    h=hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def checked(reference):
    require(isinstance(reference,dict) and set(reference)>={'path','sha256'} and re.fullmatch('[0-9a-f]{64}',reference['sha256']),'来源须完整SHA引用')
    p=physical(reference['path']);require(p.is_file() and sha(p)==reference['sha256'],'来源不存在或SHA改变：'+str(p));return p


def ref(path):return dict(path=str(physical(path)),sha256=sha(path))


def read(reference):
    p=checked(reference);require(p.suffix=='.json','只解析JSON小元数据')
    return json.loads(p.read_text(encoding='utf-8-sig'))


def same_ref(a,b):return a['sha256']==b['sha256'] and checked(a)==checked(b)


def equal(actual,expected):
    if type(expected) in (int,float):return type(actual) in (int,float) and math.isfinite(actual) and math.isfinite(expected) and abs(actual-expected)<=TOLERANCE
    if isinstance(expected,dict):return isinstance(actual,dict) and set(actual)==set(expected) and all(equal(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


def zero(body,keys=ZERO_KEYS):
    require(all(type(body[k]) is int and body[k]==0 for k in keys) and body['test_read'] is False,'零更新/前向/追踪/solver/TrackEval或测试边界不同')


def integer(value,lo=0,hi=None):return type(value) is int and value>=lo and (hi is None or value<=hi)


def source_matrix(cfg):
    require(cfg['schema']=='decision_opportunity_protocol_v1' and cfg['approved_by']=='root' and cfg['phase']=='formal' and cfg['test_sealed'] is True,'正式零更新协议不足')
    require(cfg['source_folds']==SOURCE_FOLDS and set(cfg['sequences'])==set(SEQUENCES) and len(cfg['sequences'])==3,'固定训练三源/heldout来源不同')
    require(cfg['worker_count']==2 and cfg['reserve_RAM_bytes']==8589934592 and cfg['reserve_commit_bytes']==6442450944
        and cfg['inflight_reserve_bytes']==3221225472 and cfg['bootstrap_seed']==20261028 and cfg['bootstrap_repeats']==10000,'固定2worker/资源/统计不同')
    zero(dict(cfg,test_read=False))
    expected={(f,g,s,20261024) for s,heldout in SOURCE_FOLDS.items() for f in FOLDS if f!=heldout for g in REGIMES}
    units=cfg['units'];ids={u['job']['job_id']:u for u in units}
    require(len(units)==len(ids)==12 and {tuple(u['job'][k] for k in ('fold','regime','sequence','seed')) for u in units}==expected,'完整12单位缺失/重复')
    require(set(cfg['inherit_completed'])=={units[0]['job']['job_id']},'仅继承一完整750准入')
    old=read(cfg['source_state']);closed=read(cfg['source_complete'])
    require(old['status']=='complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed' and old['active']==[]
        and closed['status']=='complete12_train_diagnosis_verified_zero_eligible_no_oracle_effect_estimated'
        and closed['actual_all_research_producers_and_verifier_absent'] is True and same_ref(closed['state'],cfg['source_state']),'既有诊断必须真实独立闭合')
    for uid,u in ids.items():
        require(old['observe'][uid]==u['observe'] and old['posthoc'][uid]==u['posthoc'],'不得改变原物理继承来源')
    bundle=physical(cfg['bundle']);require(bundle.parent==R/'code','只能最小SHA冻结代码')
    for item in read(cfg['bundle_manifest'])['files']:checked(dict(path=str(bundle/item['path']),sha256=item['sha256']))
    return ids


@contextmanager
def no_old_raw_reads():
    """仅允许新机会账本压缩流；禁止原frames/all_rows、GT、模型和媒体。"""
    evidence=dict(enabled=True,blocked_open_attempts=0)
    def hook(event,args):
        if evidence['enabled'] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.path.abspath(os.fsdecode(args[0])));suffix=p.suffix.lower()
            blocked=suffix in ('.pt','.pth','.jsonl','.npy','.npz','.png','.jpg','.jpeg','.exr','.mp4') or p.name.lower() in ('gt.txt','gap_registry.json','posthoc_gt_labels.json')
            if suffix=='.gz':blocked=not (EXP in p.parents and p.name=='rows.jsonl.gz')
            if blocked:evidence['blocked_open_attempts']+=1;raise PermissionError('终验禁止原帧/cache/GT/权重/媒体：'+str(p))
    sys.addaudithook(hook)
    try:yield evidence
    finally:evidence['enabled']=False


def pose_candidate(candidate,history_size,gap):
    require(isinstance(candidate['uid'],str) and candidate['uid'] and (candidate['label'] is None or type(candidate['label']) is int and candidate['label'] in (0,1)),'候选UID/标签非法')
    group='unknown' if candidate['label'] is None else ('correct' if candidate['label']==1 else 'known_negative')
    require(candidate['label_group']==group and integer(candidate['current_body_valid'],hi=12),'候选标签组/身体点数非法')
    shared=candidate['shared_body_joints'];each=candidate['history_each_shared_body_joints']
    require(isinstance(each,list) and len(each)==history_size and all(integer(x,hi=12) for x in each),'三历史共同点数不同')
    if not history_size:require(shared is None and candidate['history_last_body_valid'] is None and candidate['shared_body_ge6'] is None,'无历史共同点必须null')
    else:require(integer(shared,hi=12) and shared==each[-1] and integer(candidate['history_last_body_valid'],hi=12)
        and shared<=min(candidate['current_body_valid'],candidate['history_last_body_valid']) and candidate['shared_body_ge6'] is (shared>=6),'共同点数/末历史几何不一致')
    supported=bool(history_size and shared>=6 and gap is not None and 1<=gap<=30)
    require(candidate['structural_support_with_gap'] is supported and (candidate['enabled'] is None or type(candidate['enabled']) is bool)
        and type(candidate['reference_cost']) in (int,float) and math.isfinite(candidate['reference_cost']),'几何支持/gap/成本非法')
    return group,'history_missing' if shared is None else str(shared)


def audit_rows(rows,job,expected_rows):
    """只验证新账本内部结构、完整分母和统计，不重复原分类算法或solver。"""
    stops=Counter({k:0 for k in STOPS});flags={k:Counter({v:0 for v in ('true','false','null')}) for k in FLAGS}
    absolute=Counter();hist={g:Counter({k:0 for k in HISTOGRAM_KEYS}) for g in GROUPS};seen=set();tracks=set();anchors={};last=None;stage_rows=Counter();n=0
    for row in rows:
        n+=1;frame,stage,index,track=(row[k] for k in ('frame_number','stage','row_index','track_id'))
        require(row['job']==job and integer(frame,1,750) and stage in STAGES and integer(index) and integer(track),'源job/帧/stage/行/轨迹坐标非法')
        coordinate=(frame,stage,index,track);order=(frame,STAGES.index(stage),index)
        require(coordinate not in seen and (last is None or order>last),'新账本源坐标重复/时间次序不同');seen.add(coordinate);last=order
        require(index==stage_rows[(frame,stage)],'每stage行号须从0连续，不静默丢行');stage_rows[(frame,stage)]+=1
        require((frame,stage,track) not in tracks,'同stage轨迹重复');tracks.add((frame,stage,track))
        require(row['first_stop'] in STOPS and set(row['flags'])==set(FLAGS),'全部登记首停/旗标不可删改');stops[row['first_stop']]+=1
        for k,value in row['flags'].items():
            require(value is None or type(value) is bool,'旗标只准bool/null');flags[k]['null' if value is None else ('true' if value else 'false')]+=1
        require(row['threshold']==THRESHOLDS[stage] and row['local_cost_comparison_is_causal'] is False and row['Pose_support_is_accuracy'] is False
            and row['new_solver_calls']==0,'绝对阈值/结构机会非因果/非准确率边界改变')
        history=row['history_UIDs'];require(isinstance(history,list) and len(history)<=3 and len(history)==len(set(history)) and all(isinstance(x,str) for x in history),'历史UID结构非法')
        gap=row['actual_observation_gap_frames'];require(gap is None or integer(gap,1),'gap只准正整数或null')
        require(row['flags']['pose_gap_unknown'] is (gap is None) and row['flags']['pose_gap_1_to30'] is (gap is not None and 1<=gap<=30)
            and row['flags']['pose_gap_outside_1_to30'] is (gap is not None and gap>30),'全部gap旗标不一致')
        candidates=row['pose_candidates'];require(isinstance(candidates,list) and len({c['uid'] for c in candidates})==len(candidates),'候选UID重复')
        rowhist={g:Counter({k:0 for k in HISTOGRAM_KEYS}) for g in GROUPS};labels=Counter()
        for c in candidates:
            group,key=pose_candidate(c,len(history),gap);rowhist[group][key]+=1;labels[group]+=1
        require(row['pose_shared_body_histograms']=={g:dict(h) for g,h in rowhist.items()},'逐行全部0..12共同点直方图不同')
        raw=row['raw_correct_other_stage_appearances'];owners=row['raw_correct_other_stage_other_track_assignments']
        require(isinstance(raw,dict) and isinstance(owners,dict) and set(raw)==set(owners)
            and {c['uid'] for c in candidates if c['label']==1}<=set(raw),'正确raw计数/UID结构不同')
        for uid,appearances in raw.items():require(isinstance(uid,str) and isinstance(appearances,list) and len(appearances)==len(set(appearances))
            and all(s in STAGES and s!=stage for s in appearances),'其他stage出现结构非法')
        for uid,assigned in owners.items():
            require(isinstance(assigned,list),'跨stage拥有者结构非法')
            for a in assigned:require(a['stage'] in STAGES and a['stage']!=stage and integer(a['track_id']) and a['track_id']!=track and integer(a['row_index']),'跨stage其他轨迹拥有者坐标非法')
        expected=dict(rows=1,candidates=len(candidates),positive=labels['correct'],known_negative=labels['known_negative'],unknown=labels['unknown'],correct_raw=len(raw))
        require(row['absolute_counts']==expected,'逐行全候选/正/负/unknown/raw绝对计数不同');absolute.update(expected)
        for g in GROUPS:hist[g].update(rowhist[g])
        chosen=row['selected_column'];require(chosen is None or integer(chosen,hi=len(candidates)-1),'实际选择越界')
        require(row['selected_UID']==(None if chosen is None else candidates[chosen]['uid']),'实际选择UID错位')
        actual=(chosen is None,chosen is not None and candidates[chosen]['label']==1,chosen is not None and candidates[chosen]['label']==0,chosen is not None and candidates[chosen]['label'] is None)
        require(all(row['flags'][k] is value for k,value in zip(('actual_unmatched','actual_correct','actual_known_wrong','actual_selection_unknown'),actual)),'实际正确/错误/unknown/未匹配旗标不同')
        anchor=row['earliest_stage_trusted3_anchor']
        if anchor is not None:
            require(isinstance(anchor,dict) and isinstance(anchor['gt_id'],str) and integer(anchor['frame_number'],1,frame) and anchor['stage'] in STAGES
                and isinstance(anchor['history_UIDs'],list) and len(anchor['history_UIDs'])==len(set(anchor['history_UIDs']))==3,'既有最早anchor结构非法')
            require(track not in anchors or anchors[track]==anchor,'anchor不能事后回填或变化');anchors[track]=anchor
    require(n==expected_rows and sum(stops.values())==n and all(sum(c.values())==n for c in flags.values()),'新账本总行或完整首停/旗标分母不同')
    return dict(row_count=n,first_stop=dict(stops),flags={k:dict(c) for k,c in flags.items()},absolute_counts=dict(absolute),
        pose_shared_body_histograms={g:dict(h) for g,h in hist.items()},anchor_count=len(anchors),source_row_coordinates_unique=True)


def new_rows(reference):
    p=checked(reference);require(EXP in p.parents and p.name=='rows.jsonl.gz','只准新的机会账本')
    with gzip.open(p,'rt',encoding='utf-8') as stream:
        for line in stream:yield json.loads(line)


def unit_record(cfg,unit,reference,formal_protocol,admission_protocol):
    body=read(reference);job=unit['job'];jid=job['job_id'];inherited=jid in cfg['inherit_completed']
    require(body['schema']=='decision_opportunity_unit_v1' and body['status']=='complete' and body['job']==job and body['observe']==unit['observe']
        and body['posthoc']==unit['posthoc'] and body['frames']==750 and body['stages']==2250
        and same_ref(body['protocol'],admission_protocol if inherited else formal_protocol),'750单位来源/阶段/继承协议不同')
    zero(body);observe=read(unit['observe']);annotation=read(unit['posthoc'])
    require(observe['job']==annotation['job']==job and observe['frames']==annotation['total_frames']==750
        and annotation['observe']==unit['observe'] and annotation['new_solver_calls']==0
        and body['source_frames']==observe['frames_log'] and body['source_rows']==annotation['all_rows']
        and body['row_count']==body['ledger']['rows']==annotation['all_rows']['rows'],'原来源元数据/完整行数不同')
    require(physical(reference['path']).parent==physical(body['ledger']['path']).parent,'新账本与收据目录不同')
    actual=audit_rows(new_rows(body['ledger']),job,body['row_count'])
    for name in ('row_count','first_stop','flags','absolute_counts','anchor_count'):require(actual[name]==body[name],'单位完整重计不同：'+name)
    # 原实现Counter可能不写未出现的零直方图项；逐项仍按完整0..12+缺历史核对，额外项拒绝。
    require(set(body['pose_shared_body_histograms'])==set(GROUPS),'三标签Pose直方图缺失')
    for g in GROUPS:
        h=body['pose_shared_body_histograms'][g]
        require(set(h)<=set(HISTOGRAM_KEYS) and all(integer(v) for v in h.values()) and all(h.get(k,0)==actual['pose_shared_body_histograms'][g][k] for k in HISTOGRAM_KEYS),'完整Pose候选直方图不同')
    require(integer(body['worker_pid'],1),'实际worker身份缺失')
    return body,actual


def interval(rates):
    known={s:x for s,x in rates.items() if x is not None};n=len(known)
    require(all(type(x) in (int,float) and math.isfinite(x) for x in known.values()),'区间非有限源率')
    result=dict(source_rates=rates,n_independent_sources=n,mean_rate_pp=mean(known.values()) if n else None,Student_t_95CI=None,
        percentile_match_bootstrap_95CI=None,leave_one_source_out_mean={},multiplicity_adjusted=False)
    if n!=3:return result
    values=list(known.values());avg=mean(values);half=4.302652729749462*stdev(values)/math.sqrt(3);rng=random.Random(20261028)
    samples=sorted(mean(values[rng.randrange(3)] for j in range(3)) for i in range(10000))
    def q(p):
        at=9999*p;i=int(at);return samples[i]+(samples[min(i+1,9999)]-samples[i])*(at-i)
    result.update(Student_t_95CI=[avg-half,avg+half],percentile_match_bootstrap_95CI=[q(.025),q(.975)],
        leave_one_source_out_mean={s:mean(v for other,v in known.items() if other!=s) for s in known})
    return result


def descriptions(cfg,records):
    result={}
    for regime in REGIMES:
        result[regime]={}
        for kind,keys in (('first_stop',sorted(STOPS)),('flags',sorted(FLAGS))):
            for key in keys:
                rates={}
                for sequence in cfg['sequences']:
                    units=[r for r in records if r['job']['regime']==regime and r['job']['sequence']==sequence]
                    require(len(units)==2 and {r['job']['fold'] for r in units}==set(FOLDS)-{SOURCE_FOLDS[sequence]},'每训练源必须两个匹配fold')
                    values=[]
                    for u in units:
                        if kind=='first_stop':numerator=u[kind][key];denominator=u['row_count']
                        else:
                            counts=u[kind][key];numerator=counts['true'];denominator=counts['true']+counts['false']
                        values.append(None if not denominator else 100*numerator/denominator)
                    rates[sequence]=None if any(x is None for x in values) else mean(values)
                result[regime][kind+':'+key]=interval(rates)
    return result


def normalized_stops(produced,expected):
    """生产Counter相加省略总零项；仅在全账本重计确为零时显式补零。"""
    require(isinstance(produced,dict) and set(produced)<=set(STOPS) and set(expected)==set(STOPS),'首停总计含额外/缺失类别')
    require(all(integer(x) for x in produced.values()) and all(integer(x) for x in expected.values()),'首停总计必须非负整数')
    require(all(produced.get(k,0)==expected[k] for k in STOPS),'首停非零类别缺失或数值不同')
    return {k:produced.get(k,0) for k in STOPS}


def report_gate(cfg,report,records,refs,protocol):
    require(report['schema']=='decision_opportunity_analysis_v1' and report['status']==ANALYSIS_DONE and same_ref(report['protocol'],protocol)
        and report['units']==refs and report['absolute_frames']==sum(r['frames'] for r in records)==9000
        and report['unique_source_frames']==2250 and report['stages']==sum(r['stages'] for r in records)==27000
        and report['rows']==sum(r['row_count'] for r in records)==180118,'全部9000/2250/27000/180118与新报告引用不同')
    zero(report,('new_optimizer_updates','new_model_forwards','new_solver_calls','new_TrackEval'))
    require(report['bootstrap_seed']==20261028 and report['bootstrap_repeats']==10000 and report['unit_folds_are_not_independent_sources'] is True,'固定统计单位不同')
    stops={k:sum(r['first_stop'][k] for r in records) for k in STOPS}
    flags={k:{v:sum(r['flags'][k][v] for r in records) for v in ('true','false','null')} for k in FLAGS}
    normalized=normalized_stops(report['first_stop_totals'],stops)
    require(report['flag_totals']==flags,'全旗标重计不同')
    expected=descriptions(cfg,records)
    require(report['interval_count']==2*(len(STOPS)+len(FLAGS))==84 and equal(report['descriptions'],expected),'全部84描述/未知分母/t95/固定bootstrap/LOO不同')
    absolute={k:sum(r['absolute_counts'][k] for r in records) for k in ('rows','candidates','positive','known_negative','unknown','correct_raw')}
    pose={g:{k:sum(r['pose_shared_body_histograms'][g].get(k,0) for r in records) for k in HISTOGRAM_KEYS} for g in GROUPS}
    return dict(first_stop_totals=stops,normalized_first_stop_totals=normalized,producer_sparse_zero_counter_schema=True,
        flag_totals=flags,absolute_candidate_counts=absolute,pose_shared_body_histograms=pose,interval_count=84,source_weighting='mean_two_folds_then_equal_three_sources',bootstrap_seed=20261028,
        bootstrap_repeats=10000,Student_t_degrees_of_freedom=2,numerical_serialization_tolerance=TOLERANCE,formal_equivalence_or_noninferiority=False)


def process_snapshot():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|powershell|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],check=True,capture_output=True,text=True,encoding='utf-8',errors='strict')
    rows=json.loads(result.stdout) if result.stdout.strip() else [];return [rows] if isinstance(rows,dict) else rows


def processes_absent(rows,state,admission_pid):
    pattern=re.compile(r'(?:^|[\\/\s"\x27])decision_opportunity_audit[.]py(?=$|[\s"\x27])',re.I)
    historical=set(state['worker_pids'])|{state['controller_pid'],admission_pid}
    bad=[r for r in rows if pattern.search(r.get('CommandLine') or '') or (r.get('Name') or '').lower().startswith('unrealeditor')
        or (r.get('ProcessId') in historical and (r.get('Name') or '').lower().startswith('python') and 'multiprocessing.spawn' in (r.get('CommandLine') or ''))]
    require(not bad,'实际controller/launcher/spawn或UE仍在：'+canonical(bad))
    return dict(actual_CIM_checked=True,producer_processes_absent=True,exact_Name_CommandLine_checked=True,PID_alone_not_used=True,
        historical_PIDs_currently_other_identity=[r for r in rows if r.get('ProcessId') in historical])


def worker_closure(state,admission,records,inherited):
    inherited_body=next(r for r in records if r['job']['job_id']==inherited)
    new_pids={r['worker_pid'] for r in records if r['job']['job_id']!=inherited};old_pid=inherited_body['worker_pid']
    exits=state['worker_exits'];first=admission['worker_exits']
    require(new_pids==set(state['worker_pids']) and len(new_pids)==2 and len(exits)==2
        and {x['worker_pid'] for x in exits}==new_pids and old_pid not in new_pids,'两正式worker/继承实际身份不同')
    require(len(first)==1 and first[0]['worker_pid']==old_pid,'750准入独立worker身份不同')
    require(all(x['joined'] is True and x['process_exited'] is True and x['exit_code']==0 for x in exits+first),'正式/准入worker未真实join/exit0')
    return dict(new_worker_exits=exits,inherited_admission_worker_exit=first[0],all_three_workers_joined_exit0=True)


def write_new(path,value):
    p=physical(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


def verify(config,control,output):
    config,control,output=map(physical,(config,control,output));protocol=ref(config);cfg=read(protocol)
    require(EXP in output.parents and EXP in control.parents and physical(cfg['control_root'])==control and not output.parent.exists(),'独立终验拒绝未知partial或覆盖')
    with no_old_raw_reads() as guard:
        units=source_matrix(cfg);state_ref=ref(control/'driver_state.json');state=read(state_ref);report_ref=ref(control/'report.json');report=read(report_ref)
        admission=read(cfg['admission']);admission_cfg=read(admission['protocol']);inherited=cfg['units'][0]['job']['job_id']
        require(admission['status']=='complete_one750_existing_log_stream_admission' and admission['worker_joined'] is True
            and admission['unit']==cfg['inherit_completed'][inherited] and admission_cfg['phase']=='admission' and admission_cfg['inherit_completed']=={},'完整750准入继承不足')
        for name in ('bundle','bundle_manifest','units','source_state','source_complete','sequences','source_folds','resource_source','reserve_RAM_bytes','reserve_commit_bytes','inflight_reserve_bytes','bootstrap_seed','bootstrap_repeats'):
            require(admission_cfg[name]==cfg[name],'750准入后改变来源：'+name)
        zero(admission,('new_optimizer_updates','new_model_forwards','new_tracking','new_solver_calls'))
        require(state['status']==DONE and same_ref(state['protocol'],protocol) and state['active']==[] and state['workers_joined'] is True
            and state['inherited_completed']==cfg['inherit_completed'] and set(state['completed'])==set(units)
            and same_ref(state['analysis'],report_ref) and state['new_optimizer_updates']==0 and state['test_read'] is False,'实际12完成/继承/退出状态不同')
        refs=[state['completed'][u['job']['job_id']] for u in cfg['units']]
        write_new(output.parent/'intent.json',dict(status='started_not_committed',protocol=protocol,implementation=ref(__file__),new_optimizer_updates=0,new_tracking=0,test_read=False))
        try:
            inherited_body=read(cfg['inherit_completed'][inherited]);initial=processes_absent(process_snapshot(),state,inherited_body['worker_pid'])
            records=[];checks=[]
            for unit,reference in zip(cfg['units'],refs):
                body,audit=unit_record(cfg,unit,reference,protocol,admission['protocol']);records.append(body);checks.append(dict(receipt=reference,ledger=body['ledger'],row_count=audit['row_count'],source_row_coordinates_unique=True))
            closures=worker_closure(state,admission,records,inherited)
            summary=report_gate(cfg,report,records,refs,protocol);require(guard['blocked_open_attempts']==0,'终验曾尝试禁止原输入')
            final=processes_absent(process_snapshot(),state,inherited_body['worker_pid'])
            result=dict(schema='decision_opportunity_independent_verification_v1',status=STATUS,protocol=protocol,implementation=ref(__file__),state=state_ref,analysis=report_ref,
                units=checks,admission=cfg['admission'],inherited_completed=cfg['inherit_completed'],absolute_frames=9000,unique_source_frames=2250,stages=27000,rows=180118,
                counts_and_intervals=summary,worker_closures=closures,initial_exit=initial,final_exit=final,producer_processes_absent=True,all_source_row_coordinates_unique=True,
                normalized_first_stop_totals=summary['normalized_first_stop_totals'],producer_sparse_zero_counter_schema=True,
                raw_open_guard=dict(guard),original_frames_posthoc_rows_cache_GT_weights_or_media_opened=False,classification_algorithm_reexecuted=False,
                original_row_contents_rejoined_or_first_stop_classifier_rerun=False,
                structural_ledger_consistency_verified=True,Pose_17point_geometric_support_is_accuracy=False,structural_opportunity_is_correction_guarantee=False,
                new_optimizer_updates=0,new_model_forwards=0,new_tracking=0,new_solver_calls=0,new_TrackEval=0,test_read=False,
                verified_utc=datetime.now(timezone.utc).isoformat())
            write_new(output,result);return result
        except BaseException as error:
            write_new(output.parent/'failed.json',dict(status='failed_decision_opportunity_verification_partial_preserved',error=repr(error),traceback=traceback.format_exc(),
                new_optimizer_updates=0,new_model_forwards=0,new_tracking=0,new_solver_calls=0,new_TrackEval=0,test_read=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','control','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    result=verify(args.config,args.control,args.output) if args.execute else dict(status='readonly_decision_opportunity_verifier_candidate_no_execution',test_read=False)
    print(canonical(dict(status=result['status'])))
