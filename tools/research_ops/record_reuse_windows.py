"""只复用已验3000窗口与42465候选做整数风险交叉；不读文件或重算标签/分类。"""
from collections import Counter, defaultdict
from copy import deepcopy
import math

FOLDS=('game4','game6','game9')
SOURCES={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
STRATA=('positive_probability_rejected','known_negative_strict_cost_feasible','unknown_strict_cost_feasible',
        'no_known_positive_with_unknown','unique_positive_strict_cost_feasible_control')
RISKS=('no_positive_with_eligible_unknown','unknown_strict_cost_feasible','positive_rejected_with_unknown_feasible',
       'zero_effective_known','anchor_drift')
STATUSES=('not_applicable','scoring_eligibility_unknown','cost_missing','probability_rejected',
          'strict_cost_feasible','boundary_unknown','cost_above_threshold_unresolved')
LABELS=('positive','known_negative','unknown')

def require(value,message):
    if not value:raise ValueError(message)

def tri(value):
    require(value is None or type(value) is bool,'代理旗标须bool/null')
    return 'null' if value is None else str(value).lower()

def label_group(value):
    require(value is None or type(value) is int and value in (0,1),'原label只准0/1/null')
    return 'unknown' if value is None else 'positive' if value==1 else 'known_negative'

def order(row):return tuple(row[k] for k in ('frame_number','stage','row_index','track_id','window_uid'))

def _joined_window(window,pairs,job):
    """只检查已存摘要/候选的精确等值；不调用旧classify或GT匹配函数。"""
    require(window['schema']=='state_label_alignment_window_v1' and window['is_selected_R_window'] is True,'仅已选R窗口摘要')
    require(all(window[k]==job[v] for k,v in [('job_id','job_id'),('fold','fold'),('sequence','sequence'),
        ('teacher_regime','regime'),('teacher_seed','seed')]),'窗口teacher来源不同')
    require(window['stage']=='high_score' and len(window['history_UIDs'])==3 and len(set(window['history_UIDs']))==3,'原high/三历史契约不同')
    require(all(type(window[k]) is int for k in ('frame_number','row_index','track_id')),'原生源坐标不可猜转')
    uid=window['window_uid']; require(isinstance(uid,str) and uid and pairs,'窗口UID/候选缺失')
    pairs=sorted(pairs,key=lambda x:x['candidate_index'])
    require(all(type(p['candidate_index']) is int for p in pairs) and [p['candidate_index'] for p in pairs]==list(range(len(pairs)))
        and len({p['uid'] for p in pairs})==len(pairs),'候选index或UID重复/缺失')
    counts=Counter();scoring={g:Counter() for g in LABELS};probability={g:Counter() for g in LABELS}
    for p in pairs:
        require(p['window_uid']==uid and p['job_id']==job['job_id'],'候选跨窗或跨job')
        group=label_group(p['label']);require(p['label_group']==group,'候选label与原group不符')
        eligible=p['scoring_eligible'];require(type(eligible) is bool and p['enabled']==eligible
            and p['motion_gate']==eligible and p['motion_gate_missing_reason'] is None,'已选active行资格来源不同')
        status=p['probability_status'];require(status in STATUSES,'未知原概率状态')
        require(status!='not_applicable' if eligible else status=='not_applicable','资格和概率适用性冲突')
        cost=p['reference_cost'];require(cost is None or type(cost) in (int,float) and math.isfinite(cost),'原成本非有限')
        counts[group]+=1;scoring[group]['eligible' if eligible else 'ineligible']+=1;probability[group][status]+=1
    known=counts['positive']+counts['known_negative'];require(counts['positive']<=1,'同窗known正例不唯一')
    actual=dict(all_pairs=len(pairs),known_pairs=known,positive_pairs=counts['positive'],
        known_negative_pairs=counts['known_negative'],unknown_pairs=counts['unknown'])
    require(window['counts']==actual,'窗口与候选label计数不符')
    for group in LABELS:
        require(all(window['scoring_counts'][group][key]==scoring[group][key] for key in ('eligible','ineligible','unknown')),'资格计数不符')
        require(all(window['probability_counts'][group][key]==probability[group][key] for key in STATUSES),'原概率状态计数不符')
    raw=window['raw_correct_UIDs'];require(raw is None or isinstance(raw,list) and len(set(raw))==len(raw),'原可信raw清单无效')
    if raw is not None:
        require({p['uid'] for p in pairs if p['label']==1}==set(raw)&{p['uid'] for p in pairs},'同query可信raw与known正例不一致')
    correct=[] if raw is None else [p for p in pairs if p['uid'] in raw]
    present=window['current_GT_present'];tri(present);drift=window['anchor_drift'];tri(drift)
    raw_present=None if raw is None else bool(raw);raw_unique=None if raw is None else len(raw)==1
    in_stage=None if raw is None else bool(correct)
    eligible=None if raw is None else any(p['scoring_eligible'] for p in correct)
    strict=None if raw is None else any(p['probability_status']=='strict_cost_feasible' for p in correct)
    correct_statuses=sorted({p['probability_status'] for p in correct})
    level=('GT_presence_unknown' if present is None else 'GT_absent_proxy' if not present else
           'trusted_raw_unknown' if raw is None else 'no_trusted_correct_raw' if not raw else
           'correct_raw_outside_stage' if not correct else 'correct_raw_scoring_ineligible' if not eligible else
           'correct_raw_strict_cost_feasible' if strict else 'correct_raw_probability_rejected' if 'probability_rejected' in correct_statuses else
           'correct_raw_boundary_unknown' if 'boundary_unknown' in correct_statuses else 'correct_raw_other_probability_status')
    effective_known=sum(p['label'] is not None and p['scoring_eligible'] for p in pairs)
    eligible_unknown=sum(p['label'] is None and p['scoring_eligible'] for p in pairs)
    pos_rejected=probability['positive']['probability_rejected']>0
    neg_feasible=probability['known_negative']['strict_cost_feasible']>0
    unknown_feasible=probability['unknown']['strict_cost_feasible']>0
    no_pos_unknown=counts['positive']==0 and counts['unknown']>0
    risk=dict(no_positive_with_eligible_unknown=counts['positive']==0 and eligible_unknown>0,
        unknown_strict_cost_feasible=unknown_feasible,positive_rejected_with_unknown_feasible=pos_rejected and unknown_feasible,
        zero_effective_known=effective_known==0,anchor_drift=drift)
    strata=dict(zip(STRATA,(pos_rejected,neg_feasible,unknown_feasible,no_pos_unknown,
        counts['positive']==1 and probability['positive']['strict_cost_feasible']==1)))
    record=dict(schema='record_reuse_weak_label_window_v1',**{k:window[k] for k in
        ('job_id','fold','sequence','window_uid','frame_number','stage','row_index','track_id','history_UIDs','query_GT_id')},
        candidate_UIDs=[p['uid'] for p in pairs],pair_labels=[p['label'] for p in pairs],
        teacher_model_id=job['model_id'],teacher_regime='R',teacher_seed=20261024,
        teacher_state_is_not_new_model_free_state=True,source_B_class=window['B_class'],counts=actual,effective_known_pairs=effective_known,
        eligible_unknown_pairs=eligible_unknown,risk_flags=risk,case_strata=strata,reachability_level=level,
        pair_risk_counts=dict(positive_probability_rejected_pairs=probability['positive']['probability_rejected'],
            known_negative_strict_cost_feasible_pairs=probability['known_negative']['strict_cost_feasible'],
            unknown_strict_cost_feasible_pairs=probability['unknown']['strict_cost_feasible']),
        current_GT_present=present,raw_correct_present=raw_present,raw_correct_unique=raw_unique,
        correct_raw_in_stage=in_stage,correct_raw_scoring_eligible=eligible,correct_raw_strict_cost_feasible=strict,
        correct_raw_probability_statuses=correct_statuses,history_bin=window['history_bin'],gap_bin=window['gap_bin'],
        candidate_bin=window['candidate_bin'],anchor_drift=drift,earliest_stage_trusted3_anchor=window['earliest_stage_trusted3_anchor'],
        negative_subtype='not_retained',unknown_subtype='not_retained',
        no_known_positive_with_unknown=no_pos_unknown,source_labels_changed=False,new_causal_effect_estimated=False,
        unavailable_field=window['unavailable_field'])
    return record,pairs

def _analyse_unit(unit,reader):
    job=unit['job'];require(job['regime']=='R' and job['seed']==20261024 and job['fold'] in FOLDS
        and job['sequence'] in SOURCES and SOURCES[job['sequence']]!=job['fold'],'只准已选六R首seed teacher单元')
    windows=[]
    for row in reader(unit['selected_windows']):
        windows.append(row);require(len(windows)<=500,'单元超过500窗')
    require(len(windows)==500 and len({r['window_uid'] for r in windows})==500,'单元须500唯一窗')
    by={r['window_uid']:[] for r in windows};n=0
    for pair in reader(unit['selected_candidates']):
        n+=1;require(n<=8000 and pair['window_uid'] in by,'单元超过8000候选或额外窗口')
        by[pair['window_uid']].append(pair)
    if 'rows' in unit['selected_windows']:require(unit['selected_windows']['rows']==500,'冻结窗口行数不同')
    if 'rows' in unit['selected_candidates']:require(unit['selected_candidates']['rows']==n,'冻结候选行数不同')
    records=[];pair_bank={};totals=Counter()
    for row in windows:
        derived,pairs=_joined_window(row,by[row['window_uid']],job);records.append(derived)
        pair_bank[row['window_uid']]=pairs;totals.update(derived['counts'])
    slots=[];cases={};selection_counts={}
    for stratum in STRATA:
        eligible=sorted((r for r in records if r['case_strata'][stratum]),key=order);chosen=eligible[:2]
        selection_counts[stratum]=dict(available_windows=len(eligible),selected_slots=len(chosen),shortfall=2-len(chosen))
        for rank,row in enumerate(chosen,1):
            uid=row['window_uid'];tag=dict(job_id=job['job_id'],fold=job['fold'],sequence=job['sequence'],stratum=stratum,rank=rank,window_uid=uid)
            slots.append(tag)
            if uid not in cases:cases[uid]=dict(window=deepcopy(row),selection_tags=[],candidates=deepcopy(pair_bank[uid]))
            cases[uid]['selection_tags'].append(tag)
    return records,dict(job=deepcopy(job),windows=500,candidates=n,counts=dict(totals),selection_counts=selection_counts),slots,cases

def analyse_windows(units,reader):
    """reader(ref)由root约束路径/SHA/流式读取；返回整数摘要、3000行及最多60案例槽位。"""
    expected={(f,s) for f in FOLDS for s,g in SOURCES.items() if f!=g}
    require(len(units)==6 and {(u['job']['fold'],u['job']['sequence']) for u in units}==expected
        and len({u['job']['job_id'] for u in units})==6,'六fold-source单元缺失/重复')
    records=[];unit_summaries=[];slots=[];cases={}
    for unit in sorted(units,key=lambda u:(u['job']['fold'],u['job']['sequence'])):
        rows,summary,selected,case=_analyse_unit(unit,reader);records.extend(rows);unit_summaries.append(summary);slots.extend(selected)
        require(not set(cases)&set(case),'跨unit窗口UID重复');cases.update(case)
    require(len(records)==3000 and len({r['window_uid'] for r in records})==3000,'全量须3000唯一窗')
    total=Counter()
    for u in unit_summaries:total.update(u['counts'])
    require(total==dict(all_pairs=42465,known_pairs=35240,positive_pairs=1115,known_negative_pairs=34125,unknown_pairs=7225),'原42465候选/known正负unknown分母改变')
    require(len(slots)<=60 and len(cases)<=len(slots),'案例预算超过60槽位')
    crosses={name:Counter() for name in ('risk_by_reachability','risk_by_bins','label_context_by_reachability')}
    risks={k:Counter() for k in RISKS};source_counts={s:Counter() for s in SOURCES};reach=Counter();pair_risks=Counter();effective=Counter()
    for row in records:
        reach[row['reachability_level']]+=1;source_counts[row['sequence']]['windows']+=1;source_counts[row['sequence']].update(row['counts'])
        pair_risks.update(row['pair_risk_counts']);effective.update({k:row[k] for k in ('effective_known_pairs','eligible_unknown_pairs')})
        for key in RISKS:
            flag=tri(row['risk_flags'][key]);risks[key][flag]+=1
            crosses['risk_by_reachability'][(key,flag,tri(row['current_GT_present']),tri(row['raw_correct_present']),tri(row['raw_correct_unique']),
                tri(row['correct_raw_in_stage']),tri(row['correct_raw_scoring_eligible']),tri(row['correct_raw_strict_cost_feasible']),
                '|'.join(row['correct_raw_probability_statuses']) or 'no_correct_raw_in_stage',row['reachability_level'])]+=1
            crosses['risk_by_bins'][(key,flag,row['sequence'],row['fold'],row['history_bin'],row['gap_bin'],row['candidate_bin'])]+=1
        crosses['label_context_by_reachability'][(str(row['counts']['positive_pairs']),tri(row['no_known_positive_with_unknown']),
            tri(row['anchor_drift']),row['reachability_level'])]+=1
    dimensions=dict(risk_by_reachability=('risk','flag','GT_present','raw_present','raw_unique','in_stage','scoring_eligible','strict_cost_feasible','correct_raw_probability_statuses','reachability_level'),
        risk_by_bins=('risk','flag','sequence','fold','history_bin','gap_bin','candidate_bin'),
        label_context_by_reachability=('known_positive_count','no_positive_with_unknown','anchor_drift','reachability_level'))
    tables={name:[dict(zip(dimensions[name],key),windows=n) for key,n in sorted(counter.items())] for name,counter in crosses.items()}
    summary=dict(schema='record_reuse_weak_label_summary_v1',windows=3000,candidate_pairs=42465,counts=dict(total),
        unit_summaries=unit_summaries,source_counts={k:dict(v) for k,v in source_counts.items()},risk_counts={k:dict(v) for k,v in risks.items()},
        reachability_counts=dict(reach),pair_risk_totals=dict(pair_risks),effective_totals=dict(effective),cross_tables=tables,case_slots=len(slots),unique_case_windows=len(cases),
        teacher_regime='R',teacher_seed=20261024,teacher_state_is_not_new_model_free_state=True,
        negative_subtype='not_retained',unknown_subtype='not_retained',new_confidence_intervals_computed=0,
        labels_changed=False,new_model_forwards=0,new_optimizer_updates=0,new_tracking=0,new_TrackEval=0,GT_coordinates_read=False,test_read=False)
    return dict(summary=summary,records=records,casebook=dict(schema='record_reuse_weak_label_casebook_v1',slots=slots,
        windows=[cases[k] for k in sorted(cases,key=lambda uid:(cases[uid]['window']['fold'],cases[uid]['window']['sequence'],order(cases[uid]['window'])))],
        maximum_slots=60,maximum_slots_per_unit_stratum=2,strata=list(STRATA),
        fixed_sort_order=['frame_number','stage','row_index','track_id','window_uid'],
        fill_shortfalls=False,duplicated_window_display=False,examples_are_not_independent_matches=True))
