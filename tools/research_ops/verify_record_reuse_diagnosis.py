"""独立核既有记录三轴诊断；只整数/原字段对照，不导入producer或执行模型。"""
import argparse
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import traceback

R=Path('D:/projects/FutsalMOT_Research')
EXP=R/'pose/record_reuse_diagnosis_a01'
STATUS='complete_record_reuse_weak_labels_reachability_history_verified'
REASONS=('same_prediction_ID_recovered','different_prediction_ID','missing_prediction_endpoint','ambiguous_endpoint')
TRANSITIONS=('stable_recovery','improved','regressed','persistent_failure')
FAMILIES={'mask_RS_minus_original_RS':('newMaskedBCE_RS','originalstrongmotion_RS'),
          'mask_RS_minus_aligned_RS':('newMaskedBCE_RS','alignedBCE_RS'),
          'mask_R_minus_aligned_R':('newMaskedBCE_R','alignedBCE_R')}
METRIC_SCHEMAS={'r_eligibility_tracking_metric_v1':'gap','state_aligned_tracking_metric_v1':'gap',
                'v10_independent_trackeval_gap_v1':'recovery','seven_match_ABC_trackeval_gap_v1':'recovery'}
RISKS=('no_positive_with_eligible_unknown','unknown_strict_cost_feasible','positive_rejected_with_unknown_feasible','zero_effective_known','anchor_drift')
STRATA=('positive_probability_rejected','known_negative_strict_cost_feasible','unknown_strict_cost_feasible',
        'no_known_positive_with_unknown','unique_positive_strict_cost_feasible_control')
COUNTS=dict(all_pairs=42465,known_pairs=35240,positive_pairs=1115,known_negative_pairs=34125,unknown_pairs=7225)

def require(ok,message):
    if not ok:raise ValueError(message)

def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def same(a,b):return canonical(a)==canonical(b)
def tri(v):
    require(v is None or type(v) is bool,'三态不能强制为真假')
    return 'null' if v is None else 'true' if v else 'false'

def physical(value):
    p=Path(value);require(p.is_absolute(),'来源必须绝对物理路径');p=Path(os.path.abspath(p))
    require(R in p.parents,'只准实际研究根')
    require(not any(v.lower() in ('test','gt','groundtruth','annotations') or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',v.lower()) for v in p.parts),'GT/测试封存边界')
    require(p.suffix.lower() in ('.json','.jsonl','.gz','.csv') and p.name.lower() not in ('gap_registry.json','posthoc_gt_labels.json'),'不读权重/媒体/GT坐标/轨迹')
    for q in (p,*p.parents):
        if q.exists() or q.is_symlink():
            st=q.lstat();require(not stat.S_ISLNK(st.st_mode) and not getattr(st,'st_file_attributes',0)&0x400,'不跟随junction')
    return p

def sha(p):
    h=hashlib.sha256()
    with physical(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def ref(p):return dict(path=str(p),sha256=sha(p))
def refs_in(v):
    if isinstance(v,dict):
        if set(v)>={'path','sha256'}:yield v
        for x in v.values():yield from refs_in(x)
    elif isinstance(v,list):
        for x in v:yield from refs_in(x)

class Reader:
    """只打开显式登记小来源/新输出；gzip逐行，不保留解码完整frame。"""
    def __init__(self,references):
        self.allowed={};self.checked={};self.bytes_hashed=0;self.jsonl_rows=Counter()
        for r in references:self.allow(r)
    def allow(self,r):
        p=physical(r['path']);require(re.fullmatch('[0-9a-f]{64}',r['sha256']),'SHA必须完整')
        key=str(p);require(key not in self.allowed or self.allowed[key]==r['sha256'],'同一路径SHA冲突');self.allowed[key]=r['sha256']
    def path(self,r):
        p=physical(r['path']);require(self.allowed.get(str(p))==r['sha256'],'来源未在白名单显式登记')
        if str(p) not in self.checked:
            require(p.stat().st_size<=536870912,'单来源超过512MiB，需另签读取边界')
            require(sha(p)==r['sha256'],'SHA改变：'+str(p));self.checked[str(p)]=r;self.bytes_hashed+=p.stat().st_size
        return p
    def json(self,r):return json.loads(self.path(r).read_text(encoding='utf-8-sig'))
    def lines(self,r):
        p=self.path(r);opening=gzip.open if p.suffix=='.gz' else open
        limit=750 if p.name=='frames.jsonl.gz' else 500 if p.name=='selected_windows.jsonl' else 8000 if p.name=='selected_candidates.jsonl.gz' else 3000 if p.name=='window_records.jsonl' else 99630 if p.name=='gap_pairs.jsonl' else 0
        require(limit>0,'未登记流式文件名')
        with opening(p,'rt',encoding='utf-8-sig') as f:
            for line in f:
                require(line.strip(),'不丢空行');v=json.loads(line);self.jsonl_rows[str(p)]+=1
                require(self.jsonl_rows[str(p)]<=limit,'单文件记录读取超预算')
                yield v
                del v

def check_event(event):
    require(set(event)=={'event_uid','reason','endpoint_states','start_prediction_ID','end_prediction_ID'},'原公开端点字段改变')
    require(isinstance(event['event_uid'],str) and re.fullmatch('[0-9a-f]{64}',event['event_uid']),'事件UID非完整SHA')
    reason=event['reason'];states=event['endpoint_states'];a,b=event['start_prediction_ID'],event['end_prediction_ID']
    require(reason in REASONS and isinstance(states,list) and len(states)==2 and all(s in ('matched','ambiguous','missing') for s in states),'未知原因或端点状态')
    require(all(x is None or isinstance(x,str) for x in (a,b)),'预测ID原字符串/null，零ID有效')
    derived='ambiguous_endpoint' if 'ambiguous' in states else 'missing_prediction_endpoint' if 'missing' in states else 'same_prediction_ID_recovered' if a==b else 'different_prediction_ID'
    require(derived==reason,'原因与端点状态冲突')
    if states==['matched','matched']:require(a is not None and b is not None,'已匹配端点ID不能null')
    return event

def count_gap_pairs(rows,*,maximum=99630):
    seen=set();families=Counter();sources=defaultdict(Counter);cells=defaultdict(Counter);matrix=defaultdict(Counter);transitions=defaultdict(Counter);unique=defaultdict(set)
    n=0
    for row in rows:
        n+=1;require(n<=maximum,'gap配对超预算');family=row['family'];require(family in FAMILIES,'未知配对族')
        require((row['left_condition'],row['right_condition'])==FAMILIES[family],'比较方向或组别变化')
        identity=(family,row['sequence'],row['fold'],row['seed'],row['event_uid']);require(identity not in seen,'重复gap配对');seen.add(identity)
        events=[]
        for prefix in ('left','right'):
            event=dict(event_uid=row['event_uid'],reason=row[prefix+'_reason'],endpoint_states=row[prefix+'_endpoint_states'],
                       start_prediction_ID=row[prefix+'_start_prediction_ID'],end_prediction_ID=row[prefix+'_end_prediction_ID'])
            check_event(event);events.append(event)
        left,right=events;ls=left['reason']==REASONS[0];rs=right['reason']==REASONS[0]
        kind=('stable_recovery' if ls else 'regressed') if rs else ('improved' if ls else 'persistent_failure')
        require(row['transition']==kind,'两失败不能当恢复，比较方向必须固定')
        cell='|'.join((family,row['sequence'],row['fold'],str(row['seed'])))
        families[family]+=1;sources[family+'|'+row['sequence']][kind]+=1;cells[cell][kind]+=1;transitions[family][kind]+=1
        matrix[family][right['reason']+' -> '+left['reason']]+=1;unique[family].add(row['event_uid'])
    return dict(pair_rows=n,per_family=dict(families),per_family_source={k:dict(v) for k,v in sources.items()},per_cell={k:dict(v) for k,v in cells.items()},
                reason_transitions={k:dict(v) for k,v in matrix.items()},transition_counts={k:dict(v) for k,v in transitions.items()},
                per_family_unique_event_uids={k:len(v) for k,v in unique.items()})

def source_gap(sources,reader,panels):
    """独立重读登记540报告与tracking小收据；不打开MOT或完整registry。"""
    require(len(sources)==540,'登记来源应540');by={};unique={};occurrences=0;availability=[];reason_counts=Counter();conditions=Counter()
    for item in sources:
        key=tuple(item[k] for k in ('condition','sequence','fold','seed'));require(key not in by,'重复来源单元')
        body=reader.json(item['report']);require(body['status']=='complete' and body['test_read'] is False,'仅既有成功评价')
        require(all(body['job'][k]==item[k] for k in ('sequence','fold','seed')),'源单元身份不符')
        field=METRIC_SCHEMAS.get(body['schema']);require(field is not None,'不接受未知旧schema')
        events={}
        for event in body[field]['events']:
            check_event(event);uid=event['event_uid'];require(uid not in events,'报告重复事件');events[uid]=event;reason_counts[item['condition']+'|'+event['reason']]+=1
        require(body[field]['overall']['total_events']==len(events),'全登记事件分母错误')
        sequence=item['sequence'];require(sequence not in unique or unique[sequence]==set(events),'同源事件分母变化');unique[sequence]=set(events)
        by[key]=events;occurrences+=len(events);require(occurrences<=199260,'事件观察越界');conditions[item['condition']]+=1
        t=reader.json(item['tracking_receipt']);require(t['status']=='complete','追踪小收据非成功')
        require(not any(isinstance(t.get(k),list) and t[k] for k in ('raw_frames','native_output','native_frames')),'实际native可用性变化，应另立协议')
        availability.append(dict(condition=item['condition'],sequence=sequence,fold=item['fold'],seed=item['seed'],regime=item['regime'],
            receipt_schema=t.get('schema'),receipt_fields=sorted(t),native_sha_present='native_output_frames_sha256' in t,
            actual_native_frames_referenced=False,internal_state='not_retained',query_label_state='not_retained',per_pair_scoring='not_retained',
            assignment_history='not_retained',frame_from_event_uid_available=False))
    require(len(conditions)==6 and set(conditions.values())=={90},'六条件各90来源')
    require(set(unique)=={s for v in panels.values() for s in v} and sum(map(len,unique.values()))==3690 and len(set().union(*unique.values()))==3690,'原12源/3690独立event_UID改变')
    return by,dict(source_reports=540,tracking_receipts=len(availability),event_occurrences=occurrences,unique_event_uids=3690,
                   unique_event_uids_by_source={k:len(v) for k,v in unique.items()},reason_counts=dict(reason_counts),availability=availability)

def gap_rows_from_sources(by,panels):
    panel_by={s:p for p,ss in panels.items() for s in ss}
    for family,(left,right) in FAMILIES.items():
        for key in sorted(k for k in by if k[0]==left):
            _,seq,fold,seed=key;other=(right,seq,fold,seed);require(other in by and set(by[key])==set(by[other]),'精确源配对缺失')
            for uid in sorted(by[key]):
                a,b=by[key][uid],by[other][uid];ls=a['reason']==REASONS[0];rs=b['reason']==REASONS[0]
                row=dict(family=family,panel=panel_by[seq],sequence=seq,fold=fold,seed=seed,event_uid=uid,left_condition=left,right_condition=right,
                    transition=('stable_recovery' if ls else 'regressed') if rs else ('improved' if ls else 'persistent_failure'))
                for prefix,e in (('left',a),('right',b)):
                    row.update({prefix+'_'+k:e[k] for k in ('reason','endpoint_states','start_prediction_ID','end_prediction_ID')})
                yield row

def count_windows(records):
    total=Counter();risks={k:Counter() for k in RISKS};reach=Counter();pairs=Counter();effective=Counter();sources=defaultdict(Counter);cross={k:Counter() for k in ('risk_by_reachability','risk_by_bins','label_context_by_reachability')};seen=set()
    for r in records:
        require(r['schema']=='record_reuse_weak_label_window_v1' and r['window_uid'] not in seen,'重复窗口或schema改变');seen.add(r['window_uid'])
        require(r['teacher_state_is_not_new_model_free_state'] and r['teacher_regime']=='R' and r['teacher_seed']==20261024,'不能将teacher记录当新模型自由状态')
        require(r['negative_subtype']==r['unknown_subtype']=='not_retained' and r['source_labels_changed'] is False and r['new_causal_effect_estimated'] is False,'标签类型/因果缺失不能补造')
        total.update(r['counts']);sources[r['sequence']]['windows']+=1;sources[r['sequence']].update(r['counts']);reach[r['reachability_level']]+=1;pairs.update(r['pair_risk_counts']);effective.update({k:r[k] for k in ('effective_known_pairs','eligible_unknown_pairs')})
        for key in RISKS:
            flag=tri(r['risk_flags'][key]);risks[key][flag]+=1
            cross['risk_by_reachability'][(key,flag,tri(r['current_GT_present']),tri(r['raw_correct_present']),tri(r['raw_correct_unique']),tri(r['correct_raw_in_stage']),tri(r['correct_raw_scoring_eligible']),tri(r['correct_raw_strict_cost_feasible']),'|'.join(r['correct_raw_probability_statuses']) or 'no_correct_raw_in_stage',r['reachability_level'])]+=1
            cross['risk_by_bins'][(key,flag,r['sequence'],r['fold'],r['history_bin'],r['gap_bin'],r['candidate_bin'])]+=1
        cross['label_context_by_reachability'][(str(r['counts']['positive_pairs']),tri(r['no_known_positive_with_unknown']),tri(r['anchor_drift']),r['reachability_level'])]+=1
    dimensions=dict(risk_by_reachability=('risk','flag','GT_present','raw_present','raw_unique','in_stage','scoring_eligible','strict_cost_feasible','correct_raw_probability_statuses','reachability_level'),risk_by_bins=('risk','flag','sequence','fold','history_bin','gap_bin','candidate_bin'),label_context_by_reachability=('known_positive_count','no_positive_with_unknown','anchor_drift','reachability_level'))
    return dict(windows=len(seen),candidate_pairs=total['all_pairs'],counts=dict(total),source_counts={k:dict(v) for k,v in sources.items()},risk_counts={k:dict(v) for k,v in risks.items()},reachability_counts=dict(reach),pair_risk_totals=dict(pairs),effective_totals=dict(effective),cross_tables={name:[dict(zip(dimensions[name],k),windows=n) for k,n in sorted(v.items())] for name,v in cross.items()})

def check_windows_summary(summary,records,*,expected=3000):
    actual=count_windows(records);require(actual['windows']==expected,'窗口完整数量改变')
    if expected==3000:require(actual['counts']==COUNTS,'原42465候选计数改变')
    for key,value in actual.items():require(same(summary[key],value),'独立窗口整数交叉不同：'+key)
    require(summary['new_confidence_intervals_computed']==0 and summary['labels_changed'] is False and summary['test_read'] is False,'不得补标签/计算新CI/读测试')
    return actual

def check_cases(casebook,records,source_pairs=None):
    require(casebook['schema']=='record_reuse_weak_label_casebook_v1' and casebook['maximum_slots']==60 and casebook['fill_shortfalls'] is False and casebook['duplicated_window_display'] is False,'案例抽样边界变更')
    require(casebook['examples_are_not_independent_matches'] is True,'案例不是独立比赛')
    units=defaultdict(list)
    for r in records:units[r['job_id']].append(r)
    expected=[]
    for job_id,values in sorted(units.items(),key=lambda kv:(kv[1][0]['fold'],kv[1][0]['sequence'])):
        for stratum in STRATA:
            chosen=sorted((r for r in values if r['case_strata'][stratum]),key=lambda r:tuple(r[k] for k in ('frame_number','stage','row_index','track_id','window_uid')))[:2]
            for rank,r in enumerate(chosen,1):expected.append(dict(job_id=job_id,fold=r['fold'],sequence=r['sequence'],stratum=stratum,rank=rank,window_uid=r['window_uid']))
    require(same(expected,casebook['slots']) and len(expected)<=60,'必须每unit每层固定首2且不补满')
    by={r['window_uid']:r for r in records};display=casebook['windows'];require(len(display)==len({r['window_uid'] for r in expected}) and len({x['window']['window_uid'] for x in display})==len(display),'跨层同窗只能展示一次')
    for item in display:
        uid=item['window']['window_uid'];require(same(item['window'],by[uid]) and same(item['selection_tags'],[x for x in expected if x['window_uid']==uid]),'案例与原派生窗口/选中标签不同')
        if source_pairs is not None:require(same(item['candidates'],source_pairs[uid]),'案例候选被过滤或改写')
    return dict(case_slots=len(expected),unique_case_windows=len(display),maximum_slots=60,fill_shortfalls=False)

def check_window_sources(records,units,reader,*,expected_units=6,expected_per_unit=500,expected_windows=3000,expected_pairs=42465):
    """独立从已存窗口/候选投影，不调用旧classify，不匹配GT或重构特征。"""
    require(len(units)==expected_units,'须完整固定原R单位');by={r['window_uid']:r for r in records};pair_bank={};source_count=0
    for unit in units:
        job=unit['job'];receipt=reader.json(unit['receipt'])
        require(receipt['status']=='complete' and receipt['job']==job and receipt['selected_windows']==unit['selected_windows'] and receipt['selected_candidates']==unit['selected_candidates'] and receipt['GT_coordinates_read'] is False and receipt['test_read'] is False,'原unit成功收据/派生来源不同')
        windows=list(reader.lines(unit['selected_windows']));require(len(windows)==expected_per_unit,'原单位窗口分母不同')
        pool={w['window_uid']:[] for w in windows}
        for p in reader.lines(unit['selected_candidates']):
            require(p['window_uid'] in pool,'候选跨单位');pool[p['window_uid']].append(p);source_count+=1
        for old in windows:
            uid=old['window_uid'];r=by[uid];pairs=sorted(pool[uid],key=lambda p:p['candidate_index']);require([p['candidate_index'] for p in pairs]==list(range(len(pairs))),'候选顺序缺失')
            require(r['teacher_model_id']==job['model_id'] and r['job_id']==job['job_id'],'teacher身份不符')
            for k in ('fold','sequence','frame_number','stage','row_index','track_id','history_UIDs','query_GT_id','history_bin','gap_bin','candidate_bin','anchor_drift','earliest_stage_trusted3_anchor','unavailable_field'):
                require(same(r[k],old[k]),'窗口源字段不同：'+k)
            require(r['source_B_class']==old['B_class'],'不重分类旧B字段')
            uids=[p['uid'] for p in pairs];labels=[p['label'] for p in pairs]
            require(r['candidate_UIDs']==uids and r['pair_labels']==labels,'原UID/标签或顺序改变')
            counts=dict(all_pairs=len(pairs),known_pairs=sum(v is not None for v in labels),positive_pairs=labels.count(1),known_negative_pairs=labels.count(0),unknown_pairs=labels.count(None))
            require(r['counts']==old['counts']==counts,'原标签计数不同')
            effective=sum(p['label'] is not None and p['scoring_eligible'] is True for p in pairs);unknown=sum(p['label'] is None and p['scoring_eligible'] is True for p in pairs)
            positive=[p for p in pairs if p['label']==1];neg=[p for p in pairs if p['label']==0];un=[p for p in pairs if p['label'] is None]
            pos_rejected=any(p['probability_status']=='probability_rejected' for p in positive);neg_feasible=any(p['probability_status']=='strict_cost_feasible' for p in neg);un_feasible=any(p['probability_status']=='strict_cost_feasible' for p in un)
            risk=dict(no_positive_with_eligible_unknown=not positive and unknown>0,unknown_strict_cost_feasible=un_feasible,positive_rejected_with_unknown_feasible=pos_rejected and un_feasible,zero_effective_known=effective==0,anchor_drift=old['anchor_drift'])
            require(r['risk_flags']==risk and r['effective_known_pairs']==effective and r['eligible_unknown_pairs']==unknown,'风险布尔/有效计数不同')
            strata=dict(zip(STRATA,(pos_rejected,neg_feasible,un_feasible,not positive and bool(un),len(positive)==1 and positive[0]['probability_status']=='strict_cost_feasible')))
            require(r['case_strata']==strata,'案例分层错误')
            raw=old['raw_correct_UIDs'];correct=[] if raw is None else [p for p in pairs if p['uid'] in raw];present=old['current_GT_present'];statuses=sorted({p['probability_status'] for p in correct})
            values=dict(current_GT_present=present,raw_correct_present=None if raw is None else bool(raw),raw_correct_unique=None if raw is None else len(raw)==1,
                        correct_raw_in_stage=None if raw is None else bool(correct),correct_raw_scoring_eligible=None if raw is None else any(p['scoring_eligible'] for p in correct),
                        correct_raw_strict_cost_feasible=None if raw is None else any(p['probability_status']=='strict_cost_feasible' for p in correct),correct_raw_probability_statuses=statuses)
            for k,v in values.items():require(same(r[k],v),'可达性代理不同：'+k)
            level='GT_presence_unknown' if present is None else 'GT_absent_proxy' if not present else 'trusted_raw_unknown' if raw is None else 'no_trusted_correct_raw' if not raw else 'correct_raw_outside_stage' if not correct else 'correct_raw_scoring_ineligible' if not values['correct_raw_scoring_eligible'] else 'correct_raw_strict_cost_feasible' if values['correct_raw_strict_cost_feasible'] else 'correct_raw_probability_rejected' if 'probability_rejected' in statuses else 'correct_raw_boundary_unknown' if 'boundary_unknown' in statuses else 'correct_raw_other_probability_status'
            require(r['reachability_level']==level,'首不可达层顺序错误');pair_bank[uid]=pairs
    require(source_count==expected_pairs and len(pair_bank)==len(by)==expected_windows,'原候选/窗口分母不同')
    return pair_bank

def check_window_units(summary,records,units):
    expected=[]
    for unit in sorted(units,key=lambda u:(u['job']['fold'],u['job']['sequence'])):
        job=unit['job'];rows=[r for r in records if r['job_id']==job['job_id']];require(len(rows)==500,'六unit各500窗')
        totals=Counter()
        for r in rows:totals.update(r['counts'])
        selected={}
        for stratum in STRATA:
            n=sum(r['case_strata'][stratum] for r in rows);selected[stratum]=dict(available_windows=n,selected_slots=min(n,2),shortfall=max(0,2-n))
        expected.append(dict(job=job,windows=500,candidates=totals['all_pairs'],counts=dict(totals),selection_counts=selected))
    require(same(summary['unit_summaries'],expected),'逐unit计数/未填满原因不同')
    require(summary['teacher_regime']=='R' and summary['teacher_seed']==20261024 and summary['teacher_state_is_not_new_model_free_state'] is True and summary['negative_subtype']==summary['unknown_subtype']=='not_retained','teacher scope/子类型缺失口径不同')
    require(all(summary[k]==0 for k in ('new_model_forwards','new_optimizer_updates','new_tracking','new_TrackEval')) and summary['GT_coordinates_read'] is False,'窗口必须零新执行')
    return dict(units_checked=6,source_window_records_checked=3000,source_candidate_records_checked=42465)

def check_history_bounds(history,selection,state):
    require(history['schema']=='bounded_RS_wrong_raw_history_exposure_v1' and history['status']=='complete_bounded_existing_RS_wrong_raw_history_exposure_description','history schema/状态不同')
    require(history['original_eligible']==history['original_selected']==history['old_oracle_branches_executed']==0 and history['old45_oracle_intervals_not_reestimated'] is True,'旧零eligible与null区间不可改写')
    require(selection['selected']==[] and selection['absolute_counts']['eligible']==0 and all(e['candidate_eligible'] is False for e in selection['events']),'旧事件资格状态不符')
    require(history['source_protocol']==state['protocol'] and history['source_selection']==state['selected_events'] and history['original_selection_counts']==selection['absolute_counts'],'旧源协议/选择副本不同')
    original={e['event_id']:e for e in selection['events']};require(len(original)==235 and history['original_switch_event_count']==235,'原235事件分母改变')
    preserve=history['original_all_event_selection_preserved'];require(len(preserve)==235 and {e['event_id'] for e in preserve}==set(original),'原所有unknown/排除必须留存')
    units=history['fixed_RS_units'];require(len(units)==6 and len({u['job']['job_id'] for u in units})==6,'固定六RS单位不齐')
    desired=set();prefix=0
    for unit in units:
        job=unit['job'];require(job['regime']=='RS' and job['seed']==20261024,'只准旧首seed RS')
        events=sorted((e for e in original.values() if e['job_id']==job['job_id']),key=lambda e:(e['frame_number'],e['track_id'],e['event_id']))[:2];ids=[e['event_id'] for e in events]
        require(unit['selected_event_ids']==ids and unit['observe']==state['observe'][job['job_id']],'不能按oracle资格/结果选事件')
        count=min(750,max(e['frame_number']+30 for e in events)) if events else 0
        require(unit['source_frame_records_read']==count and unit['zero_events_not_filled']==(not events),'源前缀计数/无事件填额错误')
        prefix+=count;desired.update(ids)
    require(prefix<=4500 and len(desired)<=12,'history预算越界')
    records=history['event_records'];require({e['event_id'] for e in records}==desired and len(records)==len(desired),'事件派生缺失/重复')
    targets=0
    for e in records:
        source=original[e['event_id']];require(e['wrong_UID']==source['wrong_uid'] and e['frame_number']==source['frame_number'] and e['original_oracle_eligible'] is False,'错误UID/来源改变')
        rows=e['target_frame_records'];n=min(31,751-e['frame_number']);require([r['offset_frames'] for r in rows]==list(range(n)) and all(r['frame_number']==e['frame_number']+r['offset_frames'] for r in rows),'目标帧缺失或重编号')
        values=[r['history_contains_wrong_UID'] for r in rows];broken=False;present=False;exit_at=None
        for r in rows:
            v=r['history_contains_wrong_UID'];tri(v)
            if r['history_UIDs'] is not None:require(v==(e['wrong_UID'] in r['history_UIDs']),'错误UID成员关系不符')
            if v is None:broken=True
            elif v:present=True
            elif present and not broken and exit_at is None:exit_at=r['offset_frames']
            for st in r['stages']:
                require(st.get('actual_MLP_forward_not_proven_by_this_row',True) is True,'资格不能当实际前向')
        require(e['continuous_history_chain_broken']==broken and e['first_contiguous_history_exit_offset_frames']==exit_at,'unknown断链不得拼接成确定退出')
        require(e['source_tail_censored']==(e['frame_number']+30>750) and e['missing_target_frame_records'] is False,'尾部censor不能填满')
        require(e['observed_history_presence_frames']==sum(v is True for v in values) and e['unknown_or_ambiguous_history_frames']==sum(v is None for v in values),'history绝对计数不同')
        future=[v for rr in rows if rr['offset_frames']>0 for v in rr['stages']]
        require(e['actual_error_frame_write_observed']==rows[0]['write_observed'] and e['first_observed_history_absence_offset_frames']==next((v['offset_frames'] for v in rows if v['history_contains_wrong_UID'] is False),None),'实际写入/首次观察缺席不同')
        require(e['future_stage_reads_containing_wrong_UID']==sum(v.get('history_read_contains_wrong_UID') is True for v in future)
            and e['future_stages_with_potential_scoring_exposure']==sum(v.get('potential_exposure_of_written_wrong_UID') is True for v in future)
            and e['future_stage_qualification_unknown']==sum(v.get('potential_eligible_pair_count') is None for v in future)
            and e['missing_or_incomplete_stage_log_frames']==sum(not v['stage_log_complete'] for v in rows),'阶段暴露/缺失计数不同')
        require(e['causal_effect_estimated'] is False and e['actual_MLP_calls_inferred'] is False,'不估计历史因果/实际前向')
        targets+=len(rows)
    require(targets<=372 and history['absolute_counts']['target_frame_records']==targets and history['absolute_counts']['old_source_frame_records_read']==prefix,'目标/前缀总数不符')
    for item in preserve:
        old=original[item['event_id']];require(item['selected_for_history_exposure']==(item['event_id'] in desired) and item['original_exclusion_reasons']==old.get('exclusion_reasons',[]) and item['prior_unknown']==old.get('prior_unknown') and item['prior_wrong']==old.get('prior_wrong'),'原排除与未知被删除或改写')
        require(same(item['original_event'],old),'原完整事件记录被缩减或改写')
    groups=defaultdict(list)
    for e in records:
        old=original[e['event_id']];groups[(old['sequence'],old['frame_number'],old['wrong_uid'],str(old.get('anchor_GT_id')))].append(old['event_id'])
    expected_groups=[dict(sequence=k[0],frame_number=k[1],wrong_UID=k[2],anchor_GT_id=k[3],event_ids=v,shared_source_observations=len(v)) for k,v in sorted(groups.items())]
    require(same(history['shared_source_event_groups'],expected_groups),'共享物理源分组丢失或删除context')
    require(all(history['budget'][k]==0 for k in ('optimizer_updates','new_model_forward_calls','new_tracking_frame_advances','new_solver_calls','GT_coordinate_reads','new_TrackEval_calls')) and history['test_read'] is False,'history新执行不为零')
    return dict(selected_events=len(records),source_prefix_records=prefix,target_frame_records=targets,original_events=235,old_oracle_eligible=0)

def _history_uids(track):
    values=track.get('history_UIDs')
    if values is None and isinstance(track.get('history'),list):
        h=track['history'];values=[v['uid'] for v in h] if all(isinstance(v,dict) and isinstance(v.get('uid'),str) for v in h) else None
    return values if isinstance(values,list) and all(isinstance(v,str) for v in values) else None

def check_history_sources(history,selection,reader):
    """核查器独立再读至多4500旧前缀；完整frame每轮释放，仅对至多372目标行逐值核。"""
    source={e['event_id']:e for e in selection['events']};derived={e['event_id']:e for e in history['event_records']};prefix=0;targets=0
    for unit in history['fixed_RS_units']:
        receipt=reader.json(unit['observe']);require(receipt['job']==unit['job'] and receipt['frames_log']==unit['frames_log'] and receipt['protocol']==unit['observe_protocol'],'实际observe来源不同')
        ids=unit['selected_event_ids']
        if not ids:continue
        wanted={i:{r['frame_number']:r for r in derived[i]['target_frame_records']} for i in ids};limit=unit['source_frame_records_read'];seen=0
        stream=reader.lines(unit['frames_log'])
        try:
            for frame in stream:
                seen+=1;require(frame['frame_number']==seen and seen<=750,'旧帧前缀不连续')
                for i in ids:
                    if seen not in wanted[i]:continue
                    row=wanted[i][seen];event=source[i];tid=event['track_id'];wrong=event['wrong_uid'];targets+=1
                    require(row['source_full_state_sha256']==frame.get('full_state_sha256'),'源完整状态SHA不同')
                    require(row['stage_log_complete']==(isinstance(frame.get('stages'),list) and [s.get('stage') for s in frame['stages']]==['high_score','low_score','unconfirmed']),'stage缺失标记不同')
                    groups=frame.get('tracks_after');tracks=[];valid=isinstance(groups,dict) and all(isinstance(groups.get(g),list) for g in ('tracked_stracks','lost_stracks','removed_stracks'))
                    if valid:
                        tracks=[(g,t) for g in ('tracked_stracks','lost_stracks','removed_stracks') for t in groups[g] if t.get('track_id')==tid]
                        status='absent' if not tracks else 'unique' if len(tracks)==1 else 'ambiguous_cross_list_or_duplicate'
                    else:status='missing_state_schema'
                    require(row['track_status']==status,'轨迹缺失/跨list歧义被掩盖')
                    expected_uids=_history_uids(tracks[0][1]) if valid and len(tracks)==1 else None
                    require(row['history_UIDs']==expected_uids and row['history_contains_wrong_UID']==(None if expected_uids is None else wrong in expected_uids),'target历史成员关系不同')
                    if valid and len(tracks)==1:require(row['list_membership']==tracks[0][0],'轨迹生命周期list不同')
                    if row['offset_frames']==0:
                        writes=[v for v in frame.get('lifecycle',[]) if v.get('track_id')==tid and v.get('operation',v.get('event')) in ('activate','update','re_activate')]
                        exact=[v for v in writes if (v.get('after',{}).get('record') or {}).get('uid')==wrong];observed=True if len(writes)==len(exact)==1 else None
                        require(row['write_observed'] is observed,'错误raw实际写入证据不同')
                    expected_stages=[]
                    for s in frame.get('stages',[]):
                        ix=[n for n,x in enumerate(s.get('track_ids',[])) if x==tid]
                        if not ix:continue
                        if len(ix)!=1:expected_stages.append(dict(stage=s.get('stage'),history_read_contains_wrong_UID=None,status='ambiguous_track_rows'));continue
                        j=ix[0];rr=s.get('rows');uids=_history_uids(rr[j]) if isinstance(rr,list) and j<len(rr) else None
                        if uids is None:
                            hh=s.get('history_UIDs');uids=hh[j] if isinstance(hh,list) and j<len(hh) and isinstance(hh[j],list) and all(isinstance(v,str) for v in hh[j]) else None
                        contains=None if uids is None else wrong in uids;aa=s.get('active',s.get('active_rows'));active=aa[j] if isinstance(aa,list) and j<len(aa) and type(aa[j]) is bool else None
                        ee=s.get('enabled');ee=ee[j] if isinstance(ee,list) and j<len(ee) else None;enabled=sum(ee) if isinstance(ee,list) and all(type(v) is bool for v in ee) else None;potential=None if active is None or active and enabled is None else enabled if active else 0
                        aa=s.get('assignments',s.get('assignment',[]));aa=aa.get('matches',[]) if isinstance(aa,dict) else aa;col=[v[1] for v in aa if isinstance(v,(list,tuple)) and len(v)==2 and v[0]==j];candidates=s.get('candidate_UIDs',[]);selected=candidates[col[0]] if len(col)==1 and type(col[0]) is int and 0<=col[0]<len(candidates) else None
                        costs=s.get('reference_cost');cost=costs[j][col[0]] if len(col)==1 and isinstance(costs,list) and j<len(costs) and isinstance(costs[j],list) and 0<=col[0]<len(costs[j]) else None
                        expected_stages.append(dict(stage=s.get('stage'),history_UIDs=uids,history_read_contains_wrong_UID=contains,active=active,enabled_candidate_count=enabled,potential_eligible_pair_count=potential,
                            potential_exposure_of_written_wrong_UID=bool(row['offset_frames']>0 and contains is True and potential is not None and potential>0),qualification_recomputed_for_logging_only=s.get('gate_recomputed_for_logging_only'),
                            native_selected_UID=selected,native_selected_cost=cost,threshold=s.get('threshold'),actual_MLP_forward_not_proven_by_this_row=True,status='existing_observer_stage'))
                    require(same(row['stages'],expected_stages),'stage历史读取/潜在资格/实际assignment字段不同')
                if seen==limit:del frame;break
                del frame
        finally:stream.close()
        require(seen==limit,'既有前缀不足');prefix+=seen
    require(prefix<=4500 and targets<=372,'独立history重复读取预算越界')
    return dict(independent_old_prefix_records_read=prefix,independent_target_records_checked=targets,new_tracking_frame_advances=0,source_frame_replay_or_model_calls=0)

def process_exit(state):
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object Name,ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    raw=subprocess.run(['powershell.exe','-NoProfile','-Command',command],check=True,capture_output=True,text=True,encoding='utf-8').stdout
    rows=json.loads(raw) if raw.strip() else [];rows=[rows] if isinstance(rows,dict) else rows
    blocked=[x for x in rows if (x.get('Name') or '').lower().startswith('unrealeditor') or re.search(r'(?:^|[\\/\s"\x27])record_reuse_diagnosis[.]py(?=$|[\s"\x27])',x.get('CommandLine') or '',re.I)]
    children={v['pid'] for v in state['worker_exits']};parent=state['pid']
    for x in rows:
        cli=x.get('CommandLine') or '';m=re.search(r'parent_pid\s*=\s*(\d+)',cli)
        if x.get('ProcessId') in children and (x.get('Name') or '').lower().startswith('python') and 'multiprocessing.spawn' in cli and m and int(m.group(1))==parent and x.get('ParentProcessId')==parent:blocked.append(x)
    require(not blocked,'实际producer/worker/UE仍在，不按历史PID操作：'+canonical(blocked))
    return dict(actual_CIM_Name_CommandLine_parent_identity_checked=True,producer_processes_absent=True)

def write_new(path,value):
    p=physical(path);require(EXP in p.parents,'核查只写本轮新输出');p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(canonical(value)+'\n')

def own_ref():
    p=Path(__file__).resolve();require(R in p.parents and p.suffix=='.py','只能从研究根独立冻结核查器执行')
    return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def check_source_registry(cfg,reader):
    root=reader.json(cfg['source_refs']['mask_complete']);analysis=reader.json(cfg['source_refs']['mask_analysis'])
    require(root['status']=='complete_R_candidate_eligibility18_training180_tracking_independent_verification_and_all_intervals'
        and root['tracking_analysis']==cfg['source_refs']['mask_analysis'] and root['actual_controller_workers_launcher_verifier_processes_absent'] and root['test_read'] is False,'前轮真实完成根不足')
    require(analysis['status']=='complete180_R_eligibility_tracking_all540_results450_pairs75_metric15_gap_intervals' and analysis['metric_interval_descriptions']==75 and analysis['gap_interval_descriptions']==15,'只引用已验原90区间，不重新计算')
    csvref=analysis['all_results_csv'];reader.allow(csvref);sources=[]
    with reader.path(csvref).open('r',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            sources.append(dict(condition=r['condition'],model_id=r['model_id'],regime=r['regime'],sequence=r['sequence'],fold=r['fold'],seed=int(r['seed']),
                report=dict(path=r['report_path'],sha256=r['report_sha256']),tracking_receipt=dict(path=r['tracking_receipt_path'],sha256=r['tracking_receipt_sha256'])))
    require(len(sources)==540 and same(sources,cfg['metric_sources']),'新登记540来源必须等于已验CSV完整顺序，不筛模型/seed')
    require(analysis['panels']==cfg['panels'],'三个面板来源不同')
    return dict(source_complete=cfg['source_refs']['mask_complete'],source_analysis=cfg['source_refs']['mask_analysis'],source_all_results=csvref,original_intervals_recomputed=False)

def verify(config,control,output):
    config=physical(config);control=Path(control);output=physical(output);require(EXP in control.parents and EXP in output.parents and not output.exists(),'新控制/核查输出路径必须独立')
    protocol=ref(config);cfg=json.loads(config.read_text(encoding='utf-8-sig'))
    require(cfg['schema']=='record_reuse_diagnosis_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True and Path(cfg['output'])==control,'冻结协议/控制路径不同')
    zeros=('new_optimizer_updates','new_model_forwards','new_image_predictions','new_tracking','new_solver_calls','new_TrackEval','GT_coordinate_reads')
    require(all(cfg[k]==0 for k in zeros) and cfg['main_reference']=='original_uncalibrated_strongmotion_RS','新执行必须全零且保留原主参照')
    reader=Reader(refs_in(cfg));state_ref=ref(control/'driver_state.json');report_ref=ref(control/'report.json');reader.allow(state_ref);reader.allow(report_ref)
    state=reader.json(state_ref);report=reader.json(report_ref)
    require(state['status']==report['status']=='complete_record_reuse_weak_labels_reachability_history_no_training' and state['active']==[] and state['protocol']==report['protocol']==protocol,'producer未完整闭合')
    require(report['schema']=='record_reuse_diagnosis_v1' and report['main_reference']==cfg['main_reference'] and report['sources']==cfg['source_refs'] and all(report[k]==0 for k in zeros) and report['test_read'] is False,'报告源/主参照/零执行边界不同')
    require(report['factor_selected'] is False and report['training_authorized'] is False and report['new_confidence_intervals']==0 and report['existing_90_intervals_source']==cfg['source_refs']['mask_analysis'],'本轮不选新因素/不训练/不重算90CI')
    require(state['worker_exits']==report['actual_worker_exits'] and all(v['exit_code']==0 and v['process_exited'] for v in state['worker_exits']),'实际worker退出不足')
    require(state['worker_count'] in (1,2) and len(state['worker_exits'])==state['worker_count'],'有界worker数量/实际退出不齐')
    for r in refs_in(report['outputs']):reader.allow(r)
    old_state=reader.json(cfg['source_refs']['history_state']);selection=reader.json(cfg['source_refs']['history_selection'])
    for r in old_state['observe'].values():
        reader.allow(r);receipt=reader.json(r)
        if receipt['job']['regime']=='RS':reader.allow(receipt['frames_log'])
    write_new(output.parent/'intent.json',dict(schema='record_reuse_verification_intent_v1',status='started_not_committed',protocol=protocol,state=state_ref,implementation=own_ref(),new_optimizer_updates=0,test_read=False))
    try:
        initial_exit=process_exit(state);registry=check_source_registry(cfg,reader);outputs=report['outputs'];gap_summary=reader.json(outputs['gap']['summary']);source_records,source_summary=source_gap(cfg['metric_sources'],reader,cfg['panels'])
        expected=iter(gap_rows_from_sources(source_records,cfg['panels']))
        def checked_pairs():
            for row in reader.lines(outputs['gap']['records']):
                original=next(expected,None);require(original is not None and same(row,original),'完整公开源配对值/顺序不同');yield row
            require(next(expected,None) is None,'遗漏源配对，不能挑有利事件')
        actual_gap=count_gap_pairs(checked_pairs())
        require(all(n==3690 for n in actual_gap['per_family_unique_event_uids'].values()) and len(actual_gap['per_family_unique_event_uids'])==3,'每族原3690事件必须保留')
        for k,v in source_summary.items():require(same(gap_summary[k],v),'gap源整数/记录可用性不同：'+k)
        for k,v in actual_gap.items():
            if k!='per_family_unique_event_uids':require(same(gap_summary[k],v),'gap独立计数不同：'+k)
        require(gap_summary['stage_or_frame_from_event_uid_inferred'] is False and gap_summary['endpoint_failures_are_training_negative_labels'] is False and gap_summary['internal_history_or_Kalman_cause_estimated'] is False and gap_summary['new_CI_or_performance_metrics']==0,'不能从端点推断训练标签/因果/时序帧')
        del source_records
        window_summary=reader.json(outputs['windows']['summary']);records=list(reader.lines(outputs['windows']['records']));actual_windows=check_windows_summary(window_summary,records);pairs=check_window_sources(records,cfg['window_units'],reader);unitproof=check_window_units(window_summary,records,cfg['window_units']);cases=reader.json(outputs['windows']['casebook']);caseproof=check_cases(cases,records,pairs)
        require(window_summary['case_slots']==caseproof['case_slots'] and window_summary['unique_case_windows']==caseproof['unique_case_windows'],'案例summary计数不同')
        history=reader.json(outputs['history']);history_bounds=check_history_bounds(history,selection,old_state);history_source=check_history_sources(history,selection,reader)
        final_exit=process_exit(state);require(ref(control/'driver_state.json')==state_ref and ref(control/'report.json')==report_ref,'核查期间producer状态/结果改变')
        result=dict(schema='record_reuse_independent_verification_v1',status=STATUS,protocol=protocol,control_state=state_ref,producer_report=report_ref,implementation=own_ref(),
            gap=dict(source_reports=540,event_occurrences=source_summary['event_occurrences'],pair_rows=actual_gap['pair_rows'],per_family_unique_event_uids=actual_gap['per_family_unique_event_uids']),
            windows=dict(windows=actual_windows['windows'],candidate_pairs=actual_windows['candidate_pairs'],counts=actual_windows['counts'],cases=caseproof,units=unitproof),history=dict(bounds=history_bounds,independent_source_check=history_source),
            initial_exit=initial_exit,final_exit=final_exit,source_refs=cfg['source_refs'],source_registry=registry,files_SHA_checked=list(reader.checked.values()),
            source_bytes_hashed=reader.bytes_hashed,old_frame_compressed_bytes_hashed=sum(Path(k).stat().st_size for k in reader.checked if Path(k).name=='frames.jsonl.gz'),
            source_and_output_rows_read=dict(reader.jsonl_rows),source_frames_read_are_existing_records_not_new_rollouts=True,old_90_intervals_reestimated=False,old_oracle_rerun=False,
            producer_imported=False,model_or_solver_imported=False,GT_coordinates_weights_media_or_sealed_test_opened=False,all_negative_unknown_missing_exclusions_retained=True,test_read=False,verified_utc=datetime.now(timezone.utc).isoformat(),**{k:0 for k in zeros})
        write_new(output,result);return result
    except BaseException as error:
        write_new(output.parent/'failed.json',dict(status='failed_record_reuse_verification_preserved_no_replay',error=repr(error),traceback=traceback.format_exc(),source_modified=False,test_read=False,**{k:0 for k in zeros}));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','control','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    value=verify(a.config,a.control,a.output) if a.execute else dict(status='readonly_record_reuse_verifier_candidate_not_executed')
    print(canonical(value))
