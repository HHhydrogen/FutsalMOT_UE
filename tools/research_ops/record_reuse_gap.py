"""仅配对既有公开gap端点结果；不定位帧、不读取GT、轨迹或模型。"""
from collections import Counter,defaultdict

REASONS=('same_prediction_ID_recovered','different_prediction_ID','missing_prediction_endpoint','ambiguous_endpoint')
FAMILIES={
 'mask_RS_minus_original_RS':('newMaskedBCE_RS','originalstrongmotion_RS'),
 'mask_RS_minus_aligned_RS':('newMaskedBCE_RS','alignedBCE_RS'),
 'mask_R_minus_aligned_R':('newMaskedBCE_R','alignedBCE_R')}
CONDITIONS=('newMaskedBCE_R','newMaskedBCE_RS','alignedBCE_R','alignedBCE_RS','originalstrongmotion_R','originalstrongmotion_RS')
SCHEMAS={'r_eligibility_tracking_metric_v1':'gap','state_aligned_tracking_metric_v1':'gap',
 'v10_independent_trackeval_gap_v1':'recovery','seven_match_ABC_trackeval_gap_v1':'recovery'}

def require(value,message):
 if not value:raise ValueError(message)

def event_value(event):
 require(set(event)=={'event_uid','reason','endpoint_states','start_prediction_ID','end_prediction_ID'},'公开端点字段不同')
 require(event['reason'] in REASONS and len(event['event_uid'])==64,'未登记事件原因/UID')
 states=event['endpoint_states'];require(isinstance(states,list) and len(states)==2,'端点状态须二元')
 a,b=event['start_prediction_ID'],event['end_prediction_ID'];reason=event['reason']
 require(all(v is None or isinstance(v,str) for v in (a,b)),'ID必须原字符串/null；ID0合法')
 if reason==REASONS[0]:require(states==['matched','matched'] and a is not None and a==b,'恢复定义不一致')
 if reason==REASONS[1]:require(states==['matched','matched'] and a is not None and b is not None and a!=b,'不同ID定义不一致')
 return dict(event)

def transition(left,right):
 a=left==REASONS[0];b=right==REASONS[0]
 return 'stable_recovery' if a and b else 'improved' if a else 'regressed' if b else 'persistent_failure'

def analyse_gap(sources,reader,panels,*,expected_reports=540,expected_unique_events=3690):
 require(len(sources)==expected_reports,'登记540结果必须齐全')
 by={};source_events={};occurrences=0;availability=[];condition_counts=Counter();reasons=Counter()
 for item in sources:
  condition=item['condition'];require(condition in CONDITIONS,'未登记条件')
  key=(condition,item['sequence'],item['fold'],item['seed']);require(key not in by,'重复单元')
  body=reader(item['report']);require(body['status']=='complete' and body['test_read'] is False,'只读既有成功评价')
  require(body['schema'] in SCHEMAS,'独立历史schema未知')
  job=body['job'];require(all(job[k]==item[k] for k in ('sequence','fold','seed')),'登记源与评价单元不同')
  if 'regime' in job:require(job['regime']==item['regime'],'R/RS身份不同')
  values=body[SCHEMAS[body['schema']]];events={}
  for event in values['events']:
   v=event_value(event);uid=v['event_uid'];require(uid not in events,'同评价重复event UID');events[uid]=v;reasons[condition+'|'+v['reason']]+=1
  occurrences+=len(events);require(occurrences<=199260,'事件观察预算越界')
  seq=item['sequence'];uids=set(events)
  if seq in source_events:require(source_events[seq]==uids,'同源事件分母变动')
  else:source_events[seq]=uids
  by[key]=events;condition_counts[condition]+=1
  receipt=reader(item['tracking_receipt']);require(receipt['status']=='complete','追踪收据非成功')
  actual_native=any(isinstance(receipt.get(k),list) and receipt[k] for k in ('raw_frames','native_output','native_frames'))
  require(not actual_native,'记录可用性改变，应另立方案，不忽略新日志')
  availability.append(dict(condition=condition,sequence=seq,fold=item['fold'],seed=item['seed'],regime=item['regime'],
   receipt_schema=receipt.get('schema'),receipt_fields=sorted(receipt),native_sha_present='native_output_frames_sha256' in receipt,
   actual_native_frames_referenced=False,internal_state='not_retained',query_label_state='not_retained',
   per_pair_scoring='not_retained',assignment_history='not_retained',frame_from_event_uid_available=False))
 require(set(source_events)=={s for v in panels.values() for s in v},'原12源必须齐全')
 require(sum(map(len,source_events.values()))==expected_unique_events,'原3690事件分母不一致')
 require(len(set().union(*source_events.values()))==expected_unique_events,'跨源事件UID重复')
 require(all(condition_counts[c]==expected_reports//6 for c in CONDITIONS),'六条件评价计数不同')
 pairs=[];family_counts=Counter();family_source=defaultdict(Counter);cell_counts=defaultdict(Counter);transitions=defaultdict(Counter);reason_transitions=defaultdict(Counter)
 panel_by={s:p for p,seqs in panels.items() for s in seqs}
 for family,(left,right) in FAMILIES.items():
  leftkeys=sorted(k for k in by if k[0]==left)
  for key in leftkeys:
   _,seq,fold,seed=key;other=(right,seq,fold,seed);require(other in by and set(by[key])==set(by[other]),'精确fold/seed/event配对缺失')
   cell='|'.join((family,seq,fold,str(seed)))
   for uid in sorted(by[key]):
    a,b=by[key][uid],by[other][uid];kind=transition(a['reason'],b['reason'])
    row=dict(family=family,panel=panel_by[seq],sequence=seq,fold=fold,seed=seed,event_uid=uid,left_condition=left,right_condition=right,
     left_reason=a['reason'],right_reason=b['reason'],left_endpoint_states=a['endpoint_states'],right_endpoint_states=b['endpoint_states'],
     left_start_prediction_ID=a['start_prediction_ID'],left_end_prediction_ID=a['end_prediction_ID'],
     right_start_prediction_ID=b['start_prediction_ID'],right_end_prediction_ID=b['end_prediction_ID'],transition=kind)
    pairs.append(row);require(len(pairs)<=99630,'事件配对预算越界')
    family_counts[family]+=1;family_source[family+'|'+seq][kind]+=1;cell_counts[cell][kind]+=1;transitions[family][kind]+=1
    reason_transitions[family][b['reason']+' -> '+a['reason']]+=1
 summary=dict(source_reports=len(sources),tracking_receipts=len(availability),event_occurrences=occurrences,
  unique_event_uids=sum(map(len,source_events.values())),unique_event_uids_by_source={k:len(v) for k,v in source_events.items()},
  pair_rows=len(pairs),per_family=dict(family_counts),per_family_source={k:dict(v) for k,v in family_source.items()},
  per_cell={k:dict(v) for k,v in cell_counts.items()},reason_transitions={k:dict(v) for k,v in reason_transitions.items()},
  transition_counts={k:dict(v) for k,v in transitions.items()},reason_counts=dict(reasons),availability=availability,
  stage_or_frame_from_event_uid_inferred=False,endpoint_failures_are_training_negative_labels=False,
  internal_history_or_Kalman_cause_estimated=False,new_CI_or_performance_metrics=0)
 return dict(summary=summary,records=pairs)
