"""独立核训练/自由资格与弱标签诊断；不导入生产分类器，不执行模型或solver。"""
import argparse
from collections import Counter,defaultdict
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

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/state_label_alignment_diagnosis_a01'
FOLDS=('game4','game6','game9');SOURCES={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
PRIMARY=('contains_scoring_ineligible_known','contains_scoring_ineligible_positive','no_known_positive_with_unknown','eligible_trusted_correct_without_known_positive')
B_CLASSES=('1_query_history_or_fields_unknown','2_unique_known_positive','3_no_known_positive_with_unknown','4_GT_absent_no_known_positive',
    '5_GT_present_no_trusted_raw','6_trusted_raw_outside_stage_or_scoring','7_unresolved')
PROBABILITY=('not_applicable','scoring_eligibility_unknown','cost_missing','probability_rejected','strict_cost_feasible','boundary_unknown','cost_above_threshold_unresolved')
GROUPS=('positive','known_negative','unknown')
WEIGHTS=('window_known_mass','R_step_known_mass','excluded_known_window_mass','excluded_known_R_step_mass','unresolved_known_window_mass','unresolved_known_R_step_mass')
ZERO_KEYS=('new_optimizer_updates','new_model_forwards','new_image_predictions','new_tracking','new_solver_calls','new_TrackEval')
DONE='complete3000_R_windows180118_existing_rows_state_label_alignment_diagnosis_no_factor_executed'
STATUS='complete_state_label_alignment_all_sources_classifications_weights_and_intervals_verified'
TOLERANCE=1e-9  # 记录的数值序列化核验，不是性能等效界限。


def require(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def physical(value):
    path=Path(value);require(path.is_absolute(),'只准绝对物理来源');path=Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',p.lower()) for p in path.parts),'研究根/测试封存边界不同')
    for p in (path,*path.parents):
        if p.exists() or p.is_symlink():
            s=p.lstat();require(not stat.S_ISLNK(s.st_mode) and not getattr(s,'st_file_attributes',0)&0x400,'不得跟随链接/junction')
    return path


def sha(path):
    digest=hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()


def ref(path):
    path=physical(path);require(path.suffix in ('.json','.py') and path.name not in ('gap_registry.json','posthoc_GT_labels.json'),'引用仅限已知JSON元数据或源码，不先读GT/model')
    return dict(path=str(path),sha256=sha(path))


def checked(reference,kind='metadata'):
    require(isinstance(reference,dict) and set(reference)>={'path','sha256'} and re.fullmatch('[0-9a-f]{64}',reference['sha256']),'缺完整SHA引用')
    path=physical(reference['path'])
    if kind=='metadata':allowed=path.suffix=='.json' and path.name not in ('gap_registry.json','posthoc_GT_labels.json')
    elif kind=='code':allowed=path.suffix=='.py' and R/'code' in path.parents
    elif kind=='rows':
        allowed=(path.name=='rows.jsonl.gz' and ('decision_opportunity_a01' in path.parts or EXP in path.parents)) \
            or (path.name=='all_rows.jsonl.gz' and 'state_gap_diagnosis_a01' in path.parts) \
            or (path.name=='windows.jsonl' and 'teacher_anchor_bank_a01' in path.parts) \
            or (EXP in path.parents and path.name in ('selected_windows.jsonl','selected_candidates.jsonl.gz'))
    else:allowed=False
    require(allowed,'先限制文件种类/目录，再核SHA；禁止GT/cache/model/frames：'+str(path))
    require(path.is_file() and sha(path)==reference['sha256'],'来源不存在或SHA改变：'+str(path));return path


def read(reference):
    path=checked(reference)
    return json.loads(path.read_text(encoding='utf-8-sig'))


def same_ref(a,b):return a['sha256']==b['sha256'] and checked(a)==checked(b)


def equal(a,b):
    if type(b) in (int,float):return type(a) in (int,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=TOLERANCE
    if isinstance(b,dict):return isinstance(a,dict) and set(a)==set(b) and all(equal(a[k],v) for k,v in b.items())
    if isinstance(b,list):return isinstance(a,list) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return type(a) is type(b) and a==b


def finite(x):return type(x) in (int,float) and math.isfinite(x)


def coordinate(row):return tuple(row[k] for k in ('frame_number','stage','row_index','track_id'))


def selected_coordinate(m):return tuple(m[k] for k in ('source_job_id','candidate_frame_number','source_stage','source_row_index','source_track_id'))


def independent_status(stage,active,enabled,cost,threshold):
    if stage=='low_score' or active is False or enabled is False:eligible=False
    elif active is True and enabled is True:eligible=True
    else:eligible=None
    if eligible is False:status='not_applicable'
    elif eligible is None:status='scoring_eligibility_unknown'
    elif not finite(cost):status='cost_missing'
    elif cost==1.:status='probability_rejected'
    elif not finite(threshold):status='cost_missing'
    elif cost<threshold:status='strict_cost_feasible'
    elif cost==threshold:status='boundary_unknown'
    else:status='cost_above_threshold_unresolved'
    return eligible,status


def source_interval(rates):
    """四主量使用三独立训练源；缺源保留null，固定种子不挑区间。"""
    valid={s:v for s,v in rates.items() if v is not None};numbers=list(valid.values())
    require(all(finite(x) for x in numbers),'源率非有限')
    result=dict(source_rates_pp=rates,n_independent_sources=len(valid),mean_rate_pp=mean(numbers) if numbers else None,
        Student_t_95CI=None,percentile_match_bootstrap_95CI=None,leave_one_source_out_mean={},
        bootstrap_seed=20261029,bootstrap_repeats=10000,multiplicity_adjusted=False,performance_metric=False)
    if set(rates)!=set(SOURCES) or len(valid)!=3:return result
    avg=mean(numbers);half=4.302652729749462*stdev(numbers)/math.sqrt(3);rng=random.Random(20261029)
    draws=sorted(mean(numbers[rng.randrange(3)] for j in range(3)) for i in range(10000))
    def q(p):
        at=9999*p;i=int(at);return draws[i]+(draws[min(i+1,9999)]-draws[i])*(at-i)
    result.update(Student_t_95CI=[avg-half,avg+half],percentile_match_bootstrap_95CI=[q(.025),q(.975)],
        leave_one_source_out_mean={s:mean(v for other,v in valid.items() if other!=s) for s in valid},Student_t_degrees_of_freedom=2)
    return result


def bool_null(x):
    require(x is None or type(x) is bool,'资格/后验旗标必须bool/null');return x


def tri_any(xs):
    xs=list(xs)
    if True in xs:return True
    return None if None in xs else False


def expected_classification(row,annotation=None,metadata=None):
    """独立从已有UID/弱标签/资格推导，不调用生产core或模型。"""
    thresholds=dict(high_score=.8,low_score=.5,unconfirmed=.7);job=row['job'];stage=row['stage']
    require(stage in thresholds and row['threshold']==thresholds[stage],'原绝对stage阈值不同')
    history=row['history_UIDs'];source=row['pose_candidates'];uids=[c['uid'] for c in source];labels=[c['label'] for c in source]
    require(isinstance(history,list) and len(history)<=3 and len(set(history))==len(history),'历史UID结构不同')
    require(len(uids)==len(set(uids)) and all(isinstance(u,str) for u in uids) and all(x is None or type(x) is int and x in (0,1) for x in labels)
        and labels.count(1)<=1,'候选UID/原标签结构不同')
    counts=dict(all_pairs=len(labels),known_pairs=sum(x is not None for x in labels),positive_pairs=labels.count(1),known_negative_pairs=labels.count(0),unknown_pairs=labels.count(None))
    require(all(row['absolute_counts'][a]==counts[b] for a,b in [('candidates','all_pairs'),('positive','positive_pairs'),('known_negative','known_negative_pairs'),('unknown','unknown_pairs')]),'原候选绝对分母不同')
    flags=row['flags'];active=bool_null(flags.get('learned_active'));trusted=bool_null(flags.get('trusted_three_history'));query=row['query_GT_id']
    missing=set();ann={} if annotation is None else annotation
    if annotation is None:missing.add('annotation')
    else:
        require(isinstance(annotation,dict),'后验行须dict')
        required=('history_status','current_GT_present','raw_correct_UIDs','history_UIDs','candidate_UIDs','pair_labels','query_GT_id')
        missing.update('annotation.'+k for k in required if k not in ann)
        for k in ('frame_number','stage','row_index','track_id','history_UIDs','query_GT_id'):
            if k in ann:require(ann[k]==row[k],'后验坐标/身份字段不同：'+k)
        if 'candidate_UIDs' in ann:require(ann['candidate_UIDs']==uids,'后验候选顺序不同')
        if 'pair_labels' in ann:require(ann['pair_labels']==labels,'后验原标签不同')
        if 'history_count' in ann:require(ann['history_count']==len(history),'历史条数不同')
    present=bool_null(ann.get('current_GT_present'));raw=ann.get('raw_correct_UIDs')
    if present is None:missing.add('annotation.current_GT_present')
    if raw is None:missing.add('annotation.raw_correct_UIDs')
    else:require(isinstance(raw,list) and len(raw)==len(set(raw)) and all(isinstance(u,str) for u in raw) and row['absolute_counts']['correct_raw']==len(raw),'可信raw UID/绝对计数不同')
    if trusted is None:missing.add('flags.trusted_three_history')
    if active is None and stage!='low_score':missing.add('flags.learned_active')
    anchor=row['earliest_stage_trusted3_anchor'];drift=None if anchor is None or query is None else str(anchor['gt_id'])!=str(query)
    require(bool_null(flags.get('earliest_stage_trusted3_anchor_drift')) is drift,'anchor代理漂移与query不一致')
    if anchor is not None:require(type(anchor['frame_number']) is int and 1<=anchor['frame_number']<=row['frame_number'],'不可用未来anchor')
    if metadata is not None:
        require((job['job_id'],*coordinate(row))==selected_coordinate(metadata) and job['fold']==metadata['fold'] and job['sequence']==metadata['sequence']
            and job['model_id']==metadata['teacher_model_id'] and metadata['history_UIDs']==history and metadata['query_GT_id']==query
            and metadata['candidate_UIDs']==uids and metadata['pair_labels']==labels and metadata['anchor_drift'] is drift,'选中3000窗UID-label-history-query-source精确join失败')
        require(job['regime']=='R' and job['seed']==20261024 and isinstance(metadata['window_uid'],str),'主表只准选中首seed R窗口')
    K=counts['known_pairs'];candidates=[];groups=('positive','known_negative','unknown')
    scoring={g:{k:0 for k in ('eligible','ineligible','unknown')} for g in groups};probability={g:{k:0 for k in PROBABILITY} for g in groups}
    for i,c in enumerate(source):
        enabled=bool_null(c.get('enabled'));cost=c.get('reference_cost');require(cost is None or finite(cost),'成本须有限或显式缺失')
        if stage=='low_score':require(enabled is None and active is not True,'low_score不得混模型资格')
        eligible,status=independent_status(stage,active,enabled,cost,row['threshold'])
        if eligible is None:missing.add('candidate.'+str(i)+'.scoring_eligible')
        label=c['label'];group='unknown' if label is None else ('positive' if label==1 else 'known_negative');weight=1./K if label is not None and K else 0.
        motion_gate=enabled if stage!='low_score' and active is True else None
        if motion_gate is not None:gate_reason=None
        elif stage=='low_score':gate_reason='low_score_not_applicable'
        elif active is False:gate_reason='inactive_motion_gate_not_observed'
        elif active is None:gate_reason='active_status_unknown'
        else:gate_reason='enabled_missing'
        scoring[group]['unknown' if eligible is None else ('eligible' if eligible else 'ineligible')]+=1;probability[group][status]+=1
        candidates.append(dict(candidate_index=i,uid=c['uid'],label=label,label_group=group,enabled=enabled,motion_gate=motion_gate,motion_gate_missing_reason=gate_reason,scoring_eligible=eligible,probability_status=status,
            reference_cost=cost,stage_threshold=row['threshold'],BCE_window_pair_weight=weight,BCE_R_step_pair_weight=weight/3,
            excluded_known_window_weight=weight if eligible is False else 0.,unresolved_known_window_weight=weight if eligible is None else 0.,
            hypothetical_scoring_mask=eligible,labels_changed=False,hypothetical_mask_executed=False))
    positive=[c for c in candidates if c['label']==1];known=[c for c in candidates if c['label'] is not None]
    raw_eligible=None if raw is None else tri_any(c['scoring_eligible'] for c in candidates if c['uid'] in raw)
    primary=dict(zip(PRIMARY,(tri_any(None if c['scoring_eligible'] is None else not c['scoring_eligible'] for c in known),
        tri_any(None if c['scoring_eligible'] is None else not c['scoring_eligible'] for c in positive),not positive and counts['unknown_pairs']>0,False if positive else raw_eligible)))
    history_ok=len(history)==3 and trusted is True and query is not None and ann.get('history_status')=='trusted_consistent_history'
    if missing or not history_ok:cls=B_CLASSES[0]
    elif positive:cls=B_CLASSES[1]
    elif counts['unknown_pairs']:cls=B_CLASSES[2]
    elif present is False:cls=B_CLASSES[3]
    elif not raw:cls=B_CLASSES[4]
    elif not set(raw)&set(uids) or raw_eligible is False:cls=B_CLASSES[5]
    else:cls=B_CLASSES[6]
    gap=row.get('actual_observation_gap_frames');require(gap is None or type(gap) is int and gap>0,'gap须正整数/null')
    if gap is None:gap_bin='unknown'
    elif gap==1:gap_bin='1'
    elif gap<=5:gap_bin='2_to5'
    elif gap<=10:gap_bin='6_to10'
    elif gap<=30:gap_bin='11_to30'
    else:gap_bin='gt30'
    n=len(candidates);candidate_bin=next(label for maximum,label in ((0,'0'),(1,'1'),(4,'2_to4'),(8,'5_to8'),(16,'9_to16'),(float('inf'),'gt16')) if n<=maximum)
    excluded=sum(c['excluded_known_window_weight'] for c in candidates);unresolved=sum(c['unresolved_known_window_weight'] for c in candidates)
    for table in (scoring,probability):
        table['known']={k:table['positive'][k]+table['known_negative'][k] for k in table['positive']}
        table['all']={k:table['known'][k]+table['unknown'][k] for k in table['known']}
    summary=dict(schema='state_label_alignment_window_v1',job_id=job['job_id'],fold=job['fold'],sequence=job['sequence'],teacher_regime=job['regime'],teacher_seed=job['seed'],
        frame_number=row['frame_number'],stage=stage,row_index=row['row_index'],track_id=row['track_id'],is_selected_R_window=metadata is not None,
        window_uid=metadata['window_uid'] if metadata is not None else None,history_UIDs=list(history),query_GT_id=query,earliest_stage_trusted3_anchor=anchor,anchor_drift=drift,
        B_class=cls,primary_flags=primary,unavailable_field=sorted(missing),counts=counts,scoring_counts=scoring,probability_counts=probability,
        bce_weights=dict(known_K=K,window_known_mass=1. if K else 0.,R_step_known_mass=1./3 if K else 0.,excluded_known_window_mass=excluded,
            excluded_known_R_step_mass=excluded/3,unresolved_known_window_mass=unresolved,unresolved_known_R_step_mass=unresolved/3,CE_pair_additive_decomposition_available=False),
        raw_correct_UIDs=raw,current_GT_present=present,history_bin=str(len(history)),gap_bin=gap_bin,candidate_bin=candidate_bin,
        overlap_flags=dict(known_positive_present=bool(positive),unknown_present=counts['unknown_pairs']>0,trusted_correct_raw_present=None if raw is None else bool(raw),
            trusted_correct_raw_unique=None if raw is None else len(raw)==1,trusted_correct_raw_in_stage=None if raw is None else bool(set(raw)&set(uids)),eligible_trusted_correct_raw=raw_eligible,
            no_scoring_eligible_candidate=None if any(c['scoring_eligible'] is None for c in candidates) else not any(c['scoring_eligible'] is True for c in candidates),
            positive_probability_rejected=any(c['probability_status']=='probability_rejected' for c in positive),anchor_drift_is_true_identity_error=False),
        source_labels_unchanged=True,hypothetical_mask_executed=False,new_optimizer_updates=0,new_model_forwards=0,new_tracking=0,new_solver_calls=0,new_TrackEval=0,GT_coordinates_read=False)
    return summary,candidates


def verify_classification(row,annotation,metadata,actual_summary,actual_candidates=None):
    expected,candidates=expected_classification(row,annotation,metadata)
    require(equal(actual_summary,expected),'逐源行独立A/B分类/全部分母/标签/权重不同')
    if actual_candidates is not None:require(equal(actual_candidates,candidates),'选中每候选资格/概率层/原BCE权重不同')
    return expected,candidates


def selected_summary(rows,free_sensitivity_rows_excluded):
    require(len(rows)==len({r['window_uid'] for r in rows})==3000 and all(r['is_selected_R_window'] and r['teacher_regime']=='R' and r['teacher_seed']==20261024 for r in rows),'四主量只能用3000唯一首seed选中R窗')
    cells={(fold,s):[r for r in rows if r['fold']==fold and r['sequence']==s] for s,heldout in SOURCES.items() for fold in FOLDS if fold!=heldout}
    require(all(len(group)==500 for group in cells.values()) and sum(map(len,cells.values()))==3000,'每fold两允许源各500不足')
    primary={}
    for key in PRIMARY:
        rates={};counts={}
        for seq,heldout in SOURCES.items():
            folds=[]
            for fold in FOLDS:
                if fold==heldout:continue
                values=[r['primary_flags'][key] for r in cells[fold,seq]];t=sum(v is True for v in values);f=sum(v is False for v in values);n=sum(v is None for v in values)
                require(t+f+n==500,'四主量旗标非bool/null');counts[fold+':'+seq]=dict(true=t,false=f,null=n,total=500,identified_denominator=t+f)
                folds.append(100*t/(t+f) if t+f else None)
            rates[seq]=None if None in folds else mean(folds)
        true_rows=[r for r in rows if r['primary_flags'][key] is True]
        primary[key]=dict(source_interval(rates),fold_source_counts=counts,
            absolute_window_counts=dict(true=len(true_rows),false=sum(r['primary_flags'][key] is False for r in rows),null=sum(r['primary_flags'][key] is None for r in rows),total=3000),
            supervision_weights_for_true_windows={k:sum(r['bce_weights'][k] for r in true_rows) for k in WEIGHTS})
    return dict(schema='state_label_alignment_selected_summary_v1',selected_windows=3000,free_sensitivity_rows_excluded=free_sensitivity_rows_excluded,
        B_class_counts={k:sum(r['B_class']==k for r in rows) for k in B_CLASSES},
        absolute_counts={k:sum(r['counts'][k] for r in rows) for k in ('all_pairs','known_pairs','positive_pairs','known_negative_pairs','unknown_pairs')},
        bce_weights={k:sum(r['bce_weights'][k] for r in rows) for k in ('window_known_mass','R_step_known_mass','excluded_known_window_mass','excluded_known_R_step_mass','unresolved_known_window_mass','unresolved_known_R_step_mass')},
        four_primary_descriptions=primary,seed_fold_windows_are_not_independent_sources=True,performance_scores_computed=False,source_labels_unchanged=True,hypothetical_mask_executed=False,new_optimizer_updates=0,new_model_forwards=0)


def zero(body):
    require(body['test_read'] is False and body['GT_coordinates_read'] is False and all(type(body[k]) is int and body[k]==0 for k in ZERO_KEYS),'零SGD/前向/推理/追踪/solver/TrackEval/GT或测试边界不同')


def metadata_gate(cfg):
    require(cfg['schema']=='state_label_alignment_diagnosis_protocol_v1' and cfg['approved_by']=='root' and cfg['phase'] in ('formal','admission') and cfg['test_sealed'] is True
        and cfg['factor_selected'] is False and cfg['main_reference']=='original_uncalibrated_strongmotion_RS','正式诊断授权/主参照/未选因素边界不同')
    zero(dict(cfg,test_read=False));require((cfg['worker_count'],cfg['reserve_RAM_bytes'],cfg['reserve_commit_bytes'],cfg['inflight_reserve_bytes'])==(2,8589934592,6442450944,3221225472)
        and cfg['bootstrap_seed']==20261029 and cfg['bootstrap_repeats']==10000,'有界资源或四主量事前统计不同')
    bundle=physical(cfg['bundle']);require(bundle.parent==R/'code','必须最小冻结执行闭包')
    for item in read(cfg['bundle_manifest'])['files']:checked(dict(path=str(bundle/item['path']),sha256=item['sha256']),'code')
    anchor=read(cfg['anchor_complete']);anchor_report=read(cfg['anchor_report']);opportunity=read(cfg['opportunity_report'])
    require(anchor['status']=='complete3000_selected_R_bank_anchor_crosscheck_independently_verified' and anchor['selected_windows']==3000 and anchor['all_pairs']==42465
        and same_ref(anchor['analysis'],cfg['anchor_report']) and anchor_report['windows_jsonl']==cfg['selected_windows'],'仅引用原已独立验收3000窗，不重跑teacher审计')
    require(opportunity['status']=='complete12_existing_log_decision_opportunity_counts_and_source_intervals' and opportunity['rows']==180118,'原机会账本分母不同')
    source_units=cfg['source_units'];expected={(f,g,s,20261024) for s,heldout in SOURCES.items() for f in FOLDS if f!=heldout for g in ('R','RS')}
    require(len(source_units)==len({u['job']['job_id'] for u in source_units})==12 and {tuple(u['job'][k] for k in ('fold','regime','sequence','seed')) for u in source_units}==expected,'完整原12任务来源不同')
    for unit,source_ref in zip(source_units,opportunity['units']):
        source=read(source_ref);annotation=read(source['posthoc'])
        require(unit['source_unit']==source_ref and source['status']=='complete' and source['job']==unit['job'] and source['ledger']==unit['ledger']
            and annotation['all_rows']==unit['annotation'] and unit['ledger']['rows']==unit['annotation']['rows']==source['row_count'],'原ledger/posthoc源引用或分母不同')
    tables=cfg['exposure_tables'];training=read(cfg['exposure_protocol'])
    require(len(tables)==9 and {(t['fold'],t['seed']) for t in tables}=={(f,s) for f in FOLDS for s in (20261024,20261025,20261026)},'九R曝光表不完整')
    for table in tables:require(training['exposures'][table['fold']][str(table['seed'])]==table['table'],'曝光不是原冻结R来源')
    return {u['job']['job_id']:u for u in source_units}


@contextmanager
def raw_guard(allowed):
    paths={os.path.normcase(str(physical(p))) for p in allowed};evidence=dict(enabled=True,blocked_open_attempts=0)
    def hook(event,args):
        if evidence['enabled'] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            path=Path(os.path.abspath(os.fsdecode(args[0])));key=os.path.normcase(str(path))
            if (path.suffix.lower() in ('.gz','.jsonl','.pt','.pth','.npy','.npz','.png','.jpg','.jpeg','.mp4','.exr') and key not in paths) or path.name.lower() in ('gt.txt','gap_registry.json','posthoc_gt_labels.json'):
                evidence['blocked_open_attempts']+=1;raise PermissionError('禁止原frames/GT/cache/权重/媒体/训练池：'+str(path))
    sys.addaudithook(hook)
    try:yield evidence
    finally:evidence['enabled']=False


def json_rows(reference):
    path=checked(reference,'rows')
    opener=gzip.open if path.suffix=='.gz' else open;n=0
    with opener(path,'rt',encoding='utf-8') as stream:
        for line in stream:n+=1;yield json.loads(line)
    if 'rows' in reference:require(n==reference['rows'],'完整逐行记录分母不同')


def selected_metadata(cfg):
    rows=list(json_rows(cfg['selected_windows']));index={selected_coordinate(r):r for r in rows}
    require(len(rows)==len(index)==len({r['window_uid'] for r in rows})==3000,'原3000选中窗UID/源坐标唯一性不同')
    require(sum(len(r['pair_labels']) for r in rows)==42465 and sum(sum(x is not None for x in r['pair_labels']) for r in rows)==35240,'原42465候选/35240known分母不同')
    for fold in FOLDS:
        for seq,heldout in SOURCES.items():
            if fold!=heldout:require(sum(r['fold']==fold and r['sequence']==seq for r in rows)==500,'原每fold允许双源各500不同')
    return index


def accumulator():
    return dict(counts=Counter(),selected_counts=Counter(),B_classes=Counter(),primary_flags=defaultdict(Counter),overlap_flags=defaultdict(Counter),
        bins={k:defaultdict(Counter) for k in ('history_bin','gap_bin','candidate_bin')},scoring_counts={g:Counter() for g in GROUPS},probability_counts={g:Counter() for g in GROUPS})


def accumulate(total,summary):
    total['counts'].update(summary['counts']);total['counts']['rows']+=1;total['B_classes'][summary['B_class']]+=1
    for g in GROUPS:
        total['scoring_counts'][g].update(summary['scoring_counts'][g]);total['probability_counts'][g].update(summary['probability_counts'][g])
    for name in ('primary_flags','overlap_flags'):
        for k,value in summary[name].items():total[name][k]['null' if value is None else str(value).lower()]+=1
    for name in total['bins']:
        total['bins'][name][summary[name]]['rows']+=1;total['bins'][name][summary[name]][summary['B_class']]+=1
    if summary['is_selected_R_window']:total['selected_counts'].update(summary['counts']);total['selected_counts']['windows']+=1


def audit_unit(cfg,source,receipt_ref,protocol,admission_protocol,selected):
    unit=read(receipt_ref);job=source['job'];jid=job['job_id'];inherited=jid in cfg['inherit_completed']
    require(unit['status']=='complete' and unit['job']==job and unit['source']==source and same_ref(unit['protocol'],admission_protocol if inherited else protocol),'每unit来源/原继承协议不同')
    zero(unit);require(unit['rows']['rows']==source['ledger']['rows']==source['annotation']['rows'],'unit完整原行分母不同')
    all_output=iter(json_rows(unit['rows']));windows=iter(json_rows(unit['selected_windows']));candidates=iter(json_rows(unit['selected_candidates']));annotations=iter(json_rows(source['annotation']))
    total=accumulator();found=set();selected_rows=[];coordinates=set();n=0;pairs_n=0
    for row in json_rows(source['ledger']):
        n+=1;annotation=next(annotations,None);require(annotation is not None and coordinate(row)==coordinate(annotation)
            and annotation['job_id']==jid and row['job']==job,'逐原行ledger/posthoc坐标或job不同')
        key=(jid,*coordinate(row));require(key not in coordinates,'原行坐标重复');coordinates.add(key)
        metadata=selected.get(key);actual=next(all_output,None);require(actual is not None,'派生全行输出缺失')
        expected,expected_pairs=verify_classification(row,annotation,metadata,actual)
        accumulate(total,expected)
        if metadata is not None:
            require(key not in found,'选中窗重复join');found.add(key)
            actual_window=next(windows,None);require(equal(actual_window,expected),'选中窗口summary与全行输出不同')
            for pair in expected_pairs:
                actual_pair=next(candidates,None);require(equal(actual_pair,dict(window_uid=metadata['window_uid'],job_id=jid,**pair)),'完整选中候选资格/原权重不同');pairs_n+=1
            selected_rows.append(expected)
    require(next(annotations,None) is next(all_output,None) is next(windows,None) is next(candidates,None) is None,'原后验或派生输出有额外/截断行')
    require(n==source['ledger']['rows'] and found=={k for k in selected if k[0]==jid} and unit['selected_windows']['rows']==len(found)
        and unit['selected_candidates']['rows']==pairs_n,'完整单unit行数/选中窗/全候选数不同')
    for name,value in total.items():require(equal(unit[name],value),'每unit独立全分母重计不同：'+name)
    return unit,selected_rows,dict(receipt=receipt_ref,rows=n,selected_windows=len(found),selected_candidates=pairs_n,all_classifications_and_candidate_weights_exact=True)


def exposure_summary(cfg,windows):
    index={r['window_uid']:r for r in windows};result=[]
    for binding in cfg['exposure_tables']:
        table=read(binding['table']);entries=table['real'];require(len(entries)==3000 and table['fold']==binding['fold'] and table['seed']==binding['seed'],'每R曝光表3000项/身份不同')
        counts=Counter();masses=Counter();uids=Counter();epochs=defaultdict(set)
        for entry in entries:
            require(entry['window_uid'] in index and type(entry['epoch']) is int and entry['epoch']>=0,'曝光UID/epoch未知')
            w=index[entry['window_uid']];require(w['fold']==binding['fold'] and entry['candidate_pairs']==w['counts']['all_pairs'] and entry['labelled_pairs']==w['counts']['known_pairs'],'原曝光UID/all-knownpair不匹配选中窗')
            require(entry['epoch'] not in epochs[w['window_uid']],'同一UID epoch重复');epochs[w['window_uid']].add(entry['epoch'])
            uids[w['window_uid']]+=1;counts.update(w['counts']);counts['window_exposures']+=1;masses.update({k:w['bce_weights'][k] for k in WEIGHTS})
        require(len(uids)==1000 and set(uids.values())=={3} and all(v=={0,1,2} for v in epochs.values()),'每原R表1000 UID各三epoch不同')
        result.append(dict(**binding,counts=dict(counts),BCE_weight_masses=dict(masses),UID_exposure_counts=dict(uids),table_shared_by_R_RS=True,not_doubled_to_18_run_consumption=True,new_training=False))
    require(sum(r['counts']['window_exposures'] for r in result)==27000,'九R表仅27000读取，不应虚增新训练曝光')
    return result


def report_summary(cfg,units,windows):
    total=Counter();selected=Counter()
    for u in units:total.update(u['counts']);selected.update(u['selected_counts'])
    require(total['rows']==180118 and selected['windows']==3000 and selected['all_pairs']==42465 and selected['known_pairs']==35240 and selected['unknown_pairs']==7225,'完整180118/3000/42465/35240/7225分母不同')
    cells={}
    for fold in FOLDS:
        for seq,heldout in SOURCES.items():
            if fold==heldout:continue
            group=[r for r in windows if r['fold']==fold and r['sequence']==seq];cc=Counter();mass=Counter();sc={g:Counter() for g in GROUPS};pc={g:Counter() for g in GROUPS}
            for r in group:
                cc.update(r['counts']);mass.update({k:r['bce_weights'][k] for k in WEIGHTS})
                for g in GROUPS:sc[g].update(r['scoring_counts'][g]);pc[g].update(r['probability_counts'][g])
            cells[fold+':'+seq]=dict(windows=len(group),counts=dict(cc),B_classes=dict(Counter(r['B_class'] for r in group)),scoring_counts={g:dict(v) for g,v in sc.items()},
                probability_counts={g:dict(v) for g,v in pc.items()},BCE_weight_masses=dict(mass),bins={k:dict(Counter(r[k] for r in group)) for k in ('history_bin','gap_bin','candidate_bin')},
                anchor_drift=dict(Counter('null' if r['anchor_drift'] is None else str(r['anchor_drift']).lower() for r in group)))
    require(all(w['primary_flags'][PRIMARY[3]] is not True for w in windows),'资格内可信raw却无known正例：独立发现join/标签一致性故障，不选择因素')
    return dict(primary=selected_summary(windows,0),absolute_counts=dict(total),selected_counts=dict(selected),exposures=exposure_summary(cfg,windows),selected_fold_source_cells=cells,
        free_state_sensitivity_by_regime={g:[dict(job=u['job'],counts=u['counts'],B_classes=u['B_classes'],flags=u['primary_flags'],bins=u['bins']) for u in units if u['job']['regime']==g] for g in ('R','RS')})


def process_snapshot():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|powershell|pwsh|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],check=True,capture_output=True,text=True,encoding='utf-8',errors='strict')
    rows=json.loads(result.stdout) if result.stdout.strip() else [];return [rows] if isinstance(rows,dict) else rows


def processes_absent(rows,state,admission_pid):
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:state_label_alignment_diagnosis|set_supervision_train|control_r_set_supervision_training|r_set_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
    historical={state['controller_pid'],admission_pid}|set(state['worker_pids'])
    bad=[r for r in rows if pattern.search(r.get('CommandLine') or '') or (r.get('Name') or '').lower().startswith('unrealeditor')
        or (r.get('ProcessId') in historical and (r.get('Name') or '').lower().startswith('python') and 'multiprocessing.spawn' in (r.get('CommandLine') or ''))]
    require(not bad,'实际controller/launcher/worker或UE仍在：'+canonical(bad))
    return dict(actual_CIM_checked=True,producer_processes_absent=True,Name_CommandLine_not_PID_alone_checked=True,
        historical_PIDs_present_as_different_identity=[r for r in rows if r.get('ProcessId') in historical])


def worker_closure(state,admission,units,inherited):
    old=next(u for u in units if u['job']['job_id']==inherited)['worker_pid'];current={u['worker_pid'] for u in units if u['job']['job_id']!=inherited}
    require(current==set(state['worker_pids']) and len(current)==2 and old not in current and len(state['worker_exits'])==2
        and {v['worker_pid'] for v in state['worker_exits']}==current and len(admission['worker_exits'])==1 and admission['worker_exits'][0]['worker_pid']==old,'两正式worker+一继承worker身份不足')
    require(all(v['joined'] is True and v['process_exited'] is True and v['exit_code']==0 for v in state['worker_exits']+admission['worker_exits']),'真实worker未join/exit0')
    return dict(formal_worker_exits=state['worker_exits'],admission_worker_exits=admission['worker_exits'],all_three_workers_joined_exit0=True)


def write_new(path,value):
    path=physical(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


def verify_admission(config,control,output):
    config,control,output=map(physical,(config,control,output));protocol=ref(config);cfg=read(protocol)
    require(cfg['phase']=='admission' and not cfg['inherit_completed'] and EXP in control.parents and physical(cfg['control_root'])==control
        and EXP in output.parents and not output.parent.exists(),'独立单unit准入范围/拒绝覆盖不同')
    metadata_gate(cfg);unit_source=cfg['source_units'][0];jid=unit_source['job']['job_id'];state_ref=ref(control/'driver_state.json');state=read(state_ref)
    producer_ref=ref(control/'receipt.json');producer=read(producer_ref);unit_ref=state['completed'][jid];unit=read(unit_ref)
    require(state['status']==producer['status']=='complete_one_source_existing_rows_streaming_admission' and same_ref(state['protocol'],protocol)
        and same_ref(producer['protocol'],protocol) and producer['unit']==unit_ref and state['active']==[] and set(state['completed'])=={jid}
        and state['all_workers_joined'] is True and producer['all_workers_joined'] is True and len(state['worker_exits'])==len(producer['worker_exits'])==1
        and state['worker_exits']==producer['worker_exits'],'实际单unit准入尚未闭合')
    zero(state);zero(producer);exit=state['worker_exits'][0]
    require(exit['worker_pid']==unit['worker_pid'] and exit['joined'] is True and exit['process_exited'] is True and exit['exit_code']==0,'单unit worker未真实join/exit0')
    allowed=[cfg['selected_windows']['path'],unit_source['ledger']['path'],unit_source['annotation']['path']]+[unit[k]['path'] for k in ('rows','selected_windows','selected_candidates')]
    write_new(output.parent/'intent.json',dict(status='started_not_committed',protocol=protocol,producer_receipt=producer_ref,implementation=ref(__file__)))
    try:
        initial=processes_absent(process_snapshot(),state,unit['worker_pid'])
        with raw_guard(allowed) as guard:
            selected=selected_metadata(cfg);body,windows,audit=audit_unit(cfg,unit_source,unit_ref,protocol,protocol,selected)
            require(guard['blocked_open_attempts']==0,'独立准入曾尝试禁止原输入')
            final=processes_absent(process_snapshot(),state,unit['worker_pid'])
            result=dict(schema='state_label_alignment_independent_admission_v1',status='complete_one_source_state_label_alignment_independent_classification_verified',
                implementation=ref(__file__),protocol=protocol,producer_receipt=producer_ref,producer_state=state_ref,source_unit=unit_source,selected_metadata_ref=cfg['selected_windows'],
                unit_receipt=unit_ref,output_records={k:body[k] for k in ('rows','selected_windows','selected_candidates')},unit_audit=audit,
                selected_windows=len(windows),selected_candidates=body['selected_candidates']['rows'],all_classifications_and_weights_independently_verified=True,
                worker_exit=exit,initial_exit=initial,final_exit=final,producer_processes_absent=True,raw_open_guard=dict(guard),
                **{k:0 for k in ZERO_KEYS},test_read=False,GT_coordinates_read=False,verified_utc=datetime.now(timezone.utc).isoformat())
            write_new(output,result);return result
    except BaseException as error:
        write_new(output.parent/'failed.json',dict(status='failed_state_label_alignment_independent_admission_preserved',error=repr(error),traceback=traceback.format_exc()));raise


def inherit_independent_unit(cfg,source,unit_ref,admission_protocol,selected):
    proof=read(cfg['independent_admission']);unit=read(unit_ref)
    require(proof['schema']=='state_label_alignment_independent_admission_v1'
        and proof['status']=='complete_one_source_state_label_alignment_independent_classification_verified'
        and same_ref(proof['protocol'],admission_protocol) and proof['source_unit']==source and proof['selected_metadata_ref']==cfg['selected_windows']
        and proof['unit_receipt']==unit_ref and proof['output_records']=={k:unit[k] for k in ('rows','selected_windows','selected_candidates')}
        and proof['all_classifications_and_weights_independently_verified'] is True and proof['producer_processes_absent'] is True,'只能继承真实独立核查过的同unit/原来源/输出')
    zero(proof);zero(unit);require(unit['status']=='complete' and unit['source']==source and same_ref(unit['protocol'],admission_protocol),'继承拒绝partial或异源')
    for reference in [source['ledger'],source['annotation'],*proof['output_records'].values()]:checked(reference,'rows')
    windows=list(json_rows(unit['selected_windows']));jid=source['job']['job_id'];expected={k for k in selected if k[0]==jid}
    keys={(r['job_id'],r['frame_number'],r['stage'],r['row_index'],r['track_id']) for r in windows}
    require(keys==expected and len(windows)==proof['selected_windows']==len(expected),'独立继承选中summary分母不同')
    return unit,windows,dict(proof['unit_audit'],independent_admission=cfg['independent_admission'],source_classifications_reexecuted=False)


def verify(config,control,output):
    config,control,output=map(physical,(config,control,output));protocol=ref(config);cfg=read(protocol)
    require(EXP in control.parents and EXP in output.parents and physical(cfg['control_root'])==control and not output.parent.exists(),'独立终验拒绝覆盖partial/成功或越界')
    require(cfg['phase']=='formal','全部终验仅正式阶段');sources=metadata_gate(cfg);state_ref=ref(control/'driver_state.json');state=read(state_ref);report_ref=ref(control/'report.json');report=read(report_ref)
    require(state['status']==DONE and same_ref(state['protocol'],protocol) and state['active']==[] and state['all_workers_joined'] is True
        and set(state['completed'])==set(sources) and state['inherited_completed']==cfg['inherit_completed'] and same_ref(state['report'],report_ref),'实际完整12任务/终态/继承不同');zero(state)
    admission=read(cfg['admission']);oldcfg=read(admission['protocol']);first=cfg['source_units'][0]['job']['job_id']
    require(admission['status']=='complete_one_source_existing_rows_streaming_admission' and admission['all_workers_joined'] is True and oldcfg['phase']=='admission'
        and cfg['inherit_completed']=={first:admission['unit']},'完整一次准入/原成功产物继承不同');zero(admission)
    for k in ('bundle','bundle_manifest','source_units','selected_windows','exposure_tables','anchor_complete','anchor_report','opportunity_report','resource_source'):
        require(oldcfg[k]==cfg[k],'准入后改变原字段/来源/源码：'+k)
    receipts=[read(state['completed'][u['job']['job_id']]) for u in cfg['source_units']]
    allowed=[cfg['selected_windows']['path']]+[u[k]['path'] for u in cfg['source_units'] for k in ('ledger','annotation')]
    allowed +=[r[k]['path'] for r in receipts for k in ('rows','selected_windows','selected_candidates')]
    write_new(output.parent/'intent.json',dict(status='started_not_committed',implementation=ref(__file__),protocol=protocol,analysis=report_ref,**{k:0 for k in ZERO_KEYS},test_read=False,GT_coordinates_read=False))
    try:
        inherited=read(admission['unit']);initial=processes_absent(process_snapshot(),state,inherited['worker_pid'])
        with raw_guard(allowed) as guard:
            metadata=selected_metadata(cfg);units=[];windows=[];audits=[]
            for source in cfg['source_units']:
                if source['job']['job_id']==first and 'independent_admission' in cfg:
                    unit,chosen,audit=inherit_independent_unit(cfg,source,state['completed'][first],admission['protocol'],metadata)
                else:unit,chosen,audit=audit_unit(cfg,source,state['completed'][source['job']['job_id']],protocol,admission['protocol'],metadata)
                units.append(unit);windows.extend(chosen);audits.append(audit)
            closures=worker_closure(state,admission,units,first);expected=report_summary(cfg,units,windows)
            require(report['schema']=='state_label_alignment_diagnosis_report_v1' and report['status']==DONE and same_ref(report['protocol'],protocol)
                and report['units']==[dict(job=u['job'],receipt=state['completed'][u['job']['job_id']]) for u in cfg['source_units']]
                and report['primary_interval_count']==4 and (report['logical_existing_frames'],report['unique_existing_frames'],report['stages'],report['ledger_rows_read'],report['public_annotation_rows_read'])==(9000,2250,27000,180118,180118),'完整报告来源/全部分母不同')
            zero(report)
            require(all(report[k] is False for k in ('raw_GT_weights_cache_frames_or_media_opened','CE_current_model_internal_state_available','labels_changed','window_selection_changed','factor_selected'))
                and report['teacher_state_is_not_current_model_state'] is True,'诊断解释/无新实验/保持标签窗口边界不同')
            for k,v in expected.items():require(equal(report[k],v),'独立全部计数/权重/分类/四区间不同：'+k)
            require(guard['blocked_open_attempts']==0,'终验曾试图打开原frames/GT/权重/cache')
            final=processes_absent(process_snapshot(),state,inherited['worker_pid'])
            result=dict(schema='state_label_alignment_independent_verification_v1',status=STATUS,implementation=ref(__file__),protocol=protocol,state=state_ref,analysis=report_ref,
                unit_audits=audits,primary=expected['primary'],exposure_tables=expected['exposures'],worker_closures=closures,initial_exit=initial,final_exit=final,producer_processes_absent=True,
                logical_existing_frames=9000,unique_existing_frames=2250,stages=27000,source_ledger_rows=180118,public_annotation_rows=180118,selected_windows=3000,
                selected_candidates=42465,selected_known_candidates=35240,selected_unknown_candidates=7225,R_exposure_table_entries=27000,free_rows_not_in_primary=177118,
                independent_classification_implementation=True,producer_classifier_or_summarizer_imported=False,raw_open_guard=dict(guard),GT_coordinates_read=False,
                no_original_frames_cache_weights_media_or_training_pool_opened=True,labels_changed=False,hypothetical_mask_executed=False,factor_selected=False,
                **{k:0 for k in ZERO_KEYS},test_read=False,verified_utc=datetime.now(timezone.utc).isoformat())
            write_new(output,result);return result
    except BaseException as error:
        write_new(output.parent/'failed.json',dict(status='failed_state_label_alignment_verification_partial_preserved',error=repr(error),traceback=traceback.format_exc(),
            **{k:0 for k in ZERO_KEYS},test_read=False,GT_coordinates_read=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):parser.add_argument('--'+k,type=Path,required=True)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--admission-only',action='store_true');args=parser.parse_args()
    value=(verify_admission(args.config,args.control,args.output) if args.admission_only else verify(args.config,args.control,args.output)) if args.execute else dict(status='readonly_state_label_alignment_verifier_candidate_not_executed')
    print(canonical(dict(status=value['status'])))
