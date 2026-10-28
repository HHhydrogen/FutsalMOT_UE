"""自由状态R窗口来源候选：只读已验后验，不训练、不读GT或模型。"""
from collections import Counter
from copy import deepcopy
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

R=Path('D:/projects/FutsalMOT_Research')
OLD={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
FOLDS=('game4','game6','game9')
SCHEMA='free_state_aligned_R_bank_candidate_v1'

def require(ok,message):
    if not ok:raise ValueError(message)

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

def path(value):
    p=Path(value)
    require(p.is_absolute() and R in p.parents,'只允许物理DResearch来源')
    require(not any(v.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',v.lower()) for v in p.parts),'测试继续封存')
    for parent in (p,*p.parents):
        if parent.exists():require(not parent.is_symlink() and not getattr(parent.lstat(),'st_file_attributes',0)&0x400,'禁止链接/junction')
    return p

def checked(reference):
    p=path(reference['path']);h=hashlib.sha256()
    with p.open('rb') as stream:
        for b in iter(lambda:stream.read(1048576),b''):h.update(b)
    require(h.hexdigest()==reference['sha256'],'输入来源SHA变化');return p

def read(reference):return json.loads(checked(reference).read_text(encoding='utf-8-sig'))

def iter_rows(reference):
    p=checked(reference);require(p.name=='all_rows.jsonl.gz','只读后验候选行，不读完整frame日志')
    count=0
    with gzip.open(p,'rt',encoding='utf-8') as stream:
        for line in stream:
            count+=1;yield json.loads(line)
    require(count==reference['rows'],'完整后验行数变化')

def classify(row,fold):
    """历史资格仅采用已验几何代理；不将mixed/unknown改标末次身份。"""
    require(row['fold']==fold and row['regime']=='R' and row['seed']==20261024,'teacher仅同fold首seed纯R，不能让S改变采样')
    require(row['sequence'] in OLD and OLD[row['sequence']]!=fold,'禁止heldout/新七场/val/test进入teacher bank')
    history=row['history_UIDs'];frames=row['history_frames'];candidates=row['candidate_UIDs'];labels=row['pair_labels']
    require(len(candidates)==len(labels) and len(set(candidates))==len(candidates),'候选原顺序/标签或UID不同')
    require(all(v is None or type(v) is int and v in (0,1) for v in labels),'unknown必须None，不能改负例')
    reasons=[]
    if row['stage']!='high_score':reasons.append('not_high_score_stage')
    if row['learned_active'] is not True:reasons.append('learned_not_active')
    if len(history)!=3 or len(frames)!=3:reasons.append('history_not_three')
    if row['history_status']!='trusted_consistent_history' or row['query_GT_id'] is None:reasons.append('history_not_trusted_single_anchor')
    if not any(v is not None for v in labels):reasons.append('no_known_pair')
    if len(history)==len(frames)==3:
        require(len(set(history))==3 and frames==sorted(set(frames)) and all(type(n) is int and 1<=n<row['frame_number'] for n in frames),'历史必须三条严格过去、不能复制或含未来')
    return reasons

def descriptor(row,fold):
    key=[fold,row['sequence'],row['frame_number'],row['history_UIDs'],row['candidate_UIDs']]
    return dict(schema=SCHEMA,window_uid=digest([SCHEMA,key]),fold=fold,sequence=row['sequence'],game=OLD[row['sequence']],domain='real',fps=25,
        history_UIDs=list(row['history_UIDs']),history_frame_indices=[n-1 for n in row['history_frames']],
        candidate_frame_index=row['frame_number']-1,candidate_frame_number=row['frame_number'],candidate_UIDs=list(row['candidate_UIDs']),
        pair_labels=list(row['pair_labels']),query_GT_id=row['query_GT_id'],teacher_model_id=row['model_id'],teacher_regime='R',teacher_seed=20261024,
        source_job_id=row['job_id'],source_stage=row['stage'],source_track_id=row['track_id'],source_row_index=row['row_index'],
        history_label_scope='three_past_mutual_unique_IoU0.5_same_identity_proxy',candidate_scope='whole_original_high_score_stage_not_exact_enabled_subset',
        no_positive_window=not any(v==1 for v in row['pair_labels']),GT_coordinates_in_features=False)

def select_bank(rows,fold,per_source=500):
    require(fold in FOLDS and type(per_source) is int and per_source==500,'目标固定每允许源500，共1000，不按结果调配额')
    allowed=sorted(seq for seq,game in OLD.items() if game!=fold);counts=Counter();excluded=Counter();available={seq:{} for seq in allowed}
    for row in rows:
        counts['all_rows']+=1;reasons=classify(row,fold)
        if reasons:
            counts['excluded_rows']+=1;excluded.update(reasons);continue
        value=descriptor(row,fold);counts['eligible_rows_before_dedup']+=1;seq=value['sequence'];uid=value['window_uid']
        if uid in available[seq]:
            old=available[seq][uid]
            require(old['pair_labels']==value['pair_labels'] and old['query_GT_id']==value['query_GT_id'],'相同窗口的可靠标签冲突')
            counts['duplicate_windows_removed']+=1;continue
        available[seq][uid]=value
    selected=[];source_counts={}
    for seq in allowed:
        ordered=sorted(available[seq].values(),key=lambda w:(w['candidate_frame_number'],tuple(w['history_UIDs']),tuple(w['candidate_UIDs']),w['window_uid']))
        chosen=ordered[:per_source];selected.extend(chosen)
        source_counts[seq]=dict(available_unique=len(ordered),selected_unique=len(chosen),required_unique=per_source,shortfall=max(0,per_source-len(ordered)))
    ready=len(selected)==1000;labels=[v for w in selected for v in w['pair_labels']]
    return dict(schema=SCHEMA,status='candidate1000_unique_R_windows_not_training_authorized' if ready else 'insufficient_unique_R_windows_no_duplicate_fill',fold=fold,
        teacher_regime='R',teacher_seed=20261024,source_counts=source_counts,filter_counts=dict(counts),overlapping_exclusion_counts=dict(excluded),
        selection='fixed_source_frame_history_candidate_order_no_performance_selection',selected=selected,
        selected_counts=dict(windows=len(selected),all_pairs=len(labels),known_pairs=sum(v is not None for v in labels),unknown_pairs=sum(v is None for v in labels),
            positive_pairs=labels.count(1),negative_pairs=labels.count(0),no_positive_windows=sum(w['no_positive_window'] for w in selected)),
        selected_order_sha256=digest([w['window_uid'] for w in selected]),training_authorized=False,optimizer_updates=0,test_read=False,
        synthetic_pool_changed=False,normalizer_refit=False,
        limitations=['仅首seed纯R teacher的训练域选择，非新独立比赛','可信身份来自既有几何匹配代理，不能冒充人工身份复核',
            '只接纳可信三历史；不覆盖mixed/unknown/短历史，不能声称消除全部自由状态错位',
            '原高分stage全部候选保留，后验行未保存逐candidate gate，不能称精确原模型已评分子集',
            '改变R窗口内容及候选/间隔联合分布，仅能解释窗口来源这一整项因素，非每个分量因果'])

def materialize_window(value,records):
    """由原cache的UID索引构造v8字段；不生成/修正预测，不重新匹配GT。"""
    history=[deepcopy(records[uid]) for uid in value['history_UIDs']]
    candidates=[dict(prediction=deepcopy(records[uid]),label=label,label_reason='existing_state_gap_posthoc_label_preserved') for uid,label in zip(value['candidate_UIDs'],value['pair_labels'])]
    expected=list(zip(history,value['history_frame_indices'],value['history_UIDs']))+[(v['prediction'],value['candidate_frame_index'],uid) for v,uid in zip(candidates,value['candidate_UIDs'])]
    for record,index,uid in expected:
        require(record['uid']==uid and re.fullmatch(re.escape(value['sequence'])+r':\d{6}:\d{6}',uid)
            and int(uid.split(':')[1])==index+1 and record['timestamp_sec']==index/25.,'原cache UID/一基帧号/零基索引/时间不一致')
    gap=(value['candidate_frame_index']-value['history_frame_indices'][-1])/25.
    return dict(window_uid=value['window_uid'],domain='real',game=value['game'],sequence=value['sequence'],fps=25,history=history,
        history_frame_indices=value['history_frame_indices'],candidate_frame_index=value['candidate_frame_index'],candidate_frame_number=value['candidate_frame_number'],candidates=candidates,
        gap_requested_sec=None,gap_mode='free_tracker_actual_history_no_requested_gap',gap_actual_sec=gap,
        supervision=dict(query_gt_id=value['query_GT_id'],teacher_forced_history=False,source_selection_uses_existing_GT_proxy=True,
            positives=sum(v==1 for v in value['pair_labels']),unknown=sum(v is None for v in value['pair_labels'])),
        difficulty=dict(candidate_count=len(candidates),long_observation_gap=gap>=.12,
            definition='candidate_count>=2 OR actual observation gap>=.12s; not physical occlusion GT'),
        stratum=[value['game'],'free_state_actual_not_original_requested_gap_stratum'],
        aligned_bank_metadata=deepcopy(value))

def preflight(config,control,verification):
    cfg=json.loads(path(config).read_text(encoding='utf-8-sig'));v=json.loads(path(verification).read_text(encoding='utf-8-sig'))
    require(v['status']=='complete12_train_rollouts_bounded_oracle_all_records_and_exit_verified' and v['producer_processes_absent'] is True,'完整诊断及退出终验缺失')
    require(checked(v['protocol'])==path(config) and checked(v['state'])==path(control)/'driver_state.json','终验协议/control不符')
    report=read(v['report']);require(report['status']=='complete12_train_rollouts_and_bounded_state_propagation_diagnosis','诊断报告未闭合')
    jobs={j['job_id']:j for j in cfg['jobs']};result={}
    for fold in FOLDS:
        references=[]
        def rows():
            for jid in sorted(jobs):
                job=jobs[jid]
                if job['fold']!=fold or job['regime']!='R':continue
                annref=report['posthoc'][jid];annotation=read(annref);require(annotation['job']==job and annotation['total_frames']==750,'后验来源不同')
                references.append(annref)
                yield from iter_rows(annotation['all_rows'])
        result[fold]=select_bank(rows(),fold);result[fold]['posthoc_sources']=references
    return dict(schema=SCHEMA,status='readonly_candidate_preflight_not_training_or_pool_authorized',folds=result,optimizer_updates=0,test_read=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--diagnosis-config',required=True);parser.add_argument('--control',required=True);parser.add_argument('--verification',required=True)
    args=parser.parse_args();result=preflight(args.diagnosis_config,args.control,args.verification)
    # 默认只输出小计数；候选UID/全部排除留在纯函数返回中，正式落盘须另立root冻结协议。
    print(canonical(dict(status=result['status'],folds={k:{n:v[n] for n in ('status','source_counts','filter_counts','selected_counts','selected_order_sha256')} for k,v in result['folds'].items()},optimizer_updates=0,test_read=False)))
if __name__=='__main__':main()
