"""独立核既有3000选中R窗的teacher-anchor交叉报告；不重建池或执行新实验。"""
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import mean
import stat
import sys
import traceback

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/teacher_anchor_bank_a01';OPPORTUNITY=R/'pose/decision_opportunity_a01'
FOLDS=('game4','game6','game9');SOURCES={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
ZERO_KEYS=('new_optimizer_updates','new_model_forwards','new_tracking','new_solver_calls','new_TrackEval')
FLAGS=('local_opportunity','local_opportunity_pose_supported_both','local_opportunity_pose_supported_actual_noncorrect',
    'local_opportunity_pose_supported_actual_known_wrong','local_opportunity_pose_supported_actual_unmatched','local_opportunity_pose_supported_actual_unknown')
FIELDS=['window_uid','fold','sequence','source_job_id','candidate_frame_number','source_stage','source_row_index','source_track_id','teacher_model_id',
    'history_UIDs','candidate_UIDs','pair_labels','query_GT_id','earliest_stage_trusted3_anchor','anchor_drift','no_positive',
    'all_pairs','known_pairs','positive_pairs','known_negative_pairs','unknown_pairs','first_stop',*FLAGS]
CFG_SHA='34dd0b0fee0e009590b2f1cc22d6402ad85cc7d9c5745fe376ee6f30247498a7'
PRODUCER_STATUS='complete3000_selected_R_windows_teacher_anchor_opportunity_join_no_new_experiment'
STATUS='complete3000_teacher_anchor_bank_all_UID_labels_sources_rates_and_unchanged_pools_verified'


def require(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def physical(value):
    p=Path(value);require(p.is_absolute(),'只准绝对物理来源');p=Path(os.path.abspath(p))
    require(R in p.parents and not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'研究边界/测试封存不同')
    for part in (p,*p.parents):
        if part.exists() or part.is_symlink():
            s=part.lstat();require(not stat.S_ISLNK(s.st_mode) and not getattr(s,'st_file_attributes',0)&0x400,'不得链接/junction')
    return p


def sha(path):
    h=hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def ref(path):return dict(path=str(physical(path)),sha256=sha(path))


def checked(reference,kind='metadata'):
    require(isinstance(reference,dict) and set(reference)>={'path','sha256'} and re.fullmatch('[0-9a-f]{64}',reference['sha256']),'缺SHA来源')
    p=physical(reference['path']);allowed=(kind=='metadata' and p.suffix=='.json') or (kind=='pool' and p.name=='real_pool.jsonl') \
        or (kind=='windows' and EXP in p.parents and p.name in ('windows.jsonl','windows.csv')) or (kind=='ledger' and OPPORTUNITY in p.parents and p.name=='rows.jsonl.gz')
    require(allowed and p.name not in ('gap_registry.json','posthoc_GT_labels.json') and p.is_file() and sha(p)==reference['sha256'],'来源类型/范围/SHA不同：'+str(p))
    return p


def read(reference):return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def same_ref(a,b):return a['sha256']==b['sha256'] and checked(a)==checked(b)


def zero(body):require(all(type(body[k]) is int and body[k]==0 for k in ZERO_KEYS) and body['test_read'] is False,'新SGD/前向/追踪/solver/TrackEval或测试边界不同')


def same(actual,expected):
    if type(expected) in (int,float):return type(actual) in (int,float) and math.isfinite(actual) and math.isfinite(expected) and abs(actual-expected)<=1e-8
    if isinstance(expected,dict):return isinstance(actual,dict) and set(actual)==set(expected) and all(same(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(same(a,b) for a,b in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


def source_metadata(cfg):
    require(cfg['schema']=='teacher_anchor_bank_audit_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True
        and cfg['original_pool_and_labels_unchanged'] is True and cfg['source_folds']==SOURCES,'冻结零执行池核查协议不同')
    zero(dict(cfg,test_read=False));require(cfg['new_image_predictions']==0,'不得新图像推理')
    inputs=read(cfg['input_root']);verification=read(cfg['opportunity_verification']);op=read(cfg['opportunity_report'])
    require(inputs['schema']=='state_aligned_R_bank_inputs_v1' and inputs['status']=='complete3_fold1000_unique_original_prediction_R_banks_not_training_authorized'
        and inputs['all_windows_roundtrip_exact'] is True and inputs['optimizer_updates']==0 and inputs['images_GT_weights_read'] is False
        and inputs['new_prediction_or_tracking_or_training'] is False and inputs['test_read'] is False and set(inputs['folds'])==set(FOLDS),'原已验三池来源不同')
    require(verification['status']=='complete12_decision_opportunity_sources_rows_counts_intervals_and_exit_verified' and verification['producer_processes_absent'] is True
        and same_ref(verification['analysis'],cfg['opportunity_report']),'不是已独立终验的机会报告');zero(verification);zero(op)
    require(op['schema']=='decision_opportunity_analysis_v1' and op['status']=='complete12_existing_log_decision_opportunity_counts_and_source_intervals'
        and (op['rows'],op['absolute_frames'],op['unique_source_frames'])==(180118,9000,2250),'原机会全分母不同')
    units=[read(v) for v in op['units']];expected={(f,g,s,20261024) for s,heldout in SOURCES.items() for f in FOLDS if f!=heldout for g in ('R','RS')}
    require(len(units)==len({u['job']['job_id'] for u in units})==12 and {tuple(u['job'][k] for k in ('fold','regime','sequence','seed')) for u in units}==expected,'原12完整矩阵不同')
    for u in units:require(u['schema']=='decision_opportunity_unit_v1' and u['status']=='complete' and u['frames']==750 and u['row_count']==u['ledger']['rows'],'只准已完成机会unit');zero(u)
    require(sum(u['row_count'] for u in units)==180118,'原12账本总行数不同')
    teachers={u['job']['job_id']:u for u in units if u['job']['regime']=='R'};require(len(teachers)==6,'只准六个首seed R teacher')
    return inputs,teachers


@contextmanager
def raw_guard(allowed):
    whitelist={os.path.normcase(str(physical(p))) for p in allowed};evidence=dict(enabled=True,blocked_open_attempts=0)
    def hook(event,args):
        if evidence['enabled'] and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.path.abspath(os.fsdecode(args[0])));key=os.path.normcase(str(p))
            if p.suffix.lower() in ('.jsonl','.gz','.pt','.pth','.npz','.npy','.png','.jpg','.jpeg','.mp4','.exr') and key not in whitelist \
                or p.name.lower() in ('gt.txt','gap_registry.json','posthoc_gt_labels.json'):
                evidence['blocked_open_attempts']+=1;raise PermissionError('只准原三R池元数据/六R机会ledger及新窗口表：'+str(p))
    sys.addaudithook(hook)
    try:yield evidence
    finally:evidence['enabled']=False


def coordinate(m):return tuple(m[k] for k in ('source_job_id','candidate_frame_number','source_stage','source_row_index','source_track_id'))


def pool_metadata(inputs,teachers):
    selected=[];uids=set();coords=set();pool_refs={}
    for fold in FOLDS:
        bound=inputs['folds'][fold];pool_refs[fold]=bound['pool'];order=[];counts=Counter();sources=Counter()
        with checked(bound['pool'],'pool').open(encoding='utf-8-sig') as stream:
            for line in stream:
                # 每次只保留一窗；不计算或保存原坐标特征。
                window=json.loads(line);m=window['aligned_bank_metadata'];labels=m['pair_labels'];teacher=teachers[m['source_job_id']]['job']
                require(m['schema']=='free_state_aligned_R_bank_candidate_v1' and m['fold']==fold and m['teacher_regime']=='R' and m['teacher_seed']==20261024
                    and m['source_stage']=='high_score' and m['GT_coordinates_in_features'] is False
                    and m['candidate_scope']=='whole_original_high_score_stage_not_exact_enabled_subset','原池teacher/候选范围不同')
                require(teacher['fold']==fold and teacher['sequence']==m['sequence'] and teacher['model_id']==m['teacher_model_id'] and SOURCES[m['sequence']]!=fold,'窗口源teacher不同')
                require(window['window_uid']==m['window_uid'] and window['sequence']==m['sequence'] and window['candidate_frame_number']==m['candidate_frame_number']
                    and [h['uid'] for h in window['history']]==m['history_UIDs'] and [c['prediction']['uid'] for c in window['candidates']]==m['candidate_UIDs']
                    and [c['label'] for c in window['candidates']]==labels,'原窗UID/候选/标签/历史与metadata不一致')
                require(len(m['history_UIDs'])==len(set(m['history_UIDs']))==3 and len(labels)==len(m['candidate_UIDs'])==len(set(m['candidate_UIDs']))
                    and all(x is None or type(x) is int and x in (0,1) for x in labels) and any(x is not None for x in labels)
                    and m['query_GT_id'] is not None and m['no_positive_window'] is (1 not in labels),'原可靠三历史/标签结构不同')
                key=coordinate(m);require(m['window_uid'] not in uids and key not in coords,'原3000窗口UID/坐标重复')
                uids.add(m['window_uid']);coords.add(key);order.append(m['window_uid']);sources[m['sequence']]+=1
                counts.update(dict(windows=1,all_pairs=len(labels),known_pairs=sum(x is not None for x in labels),unknown_pairs=labels.count(None),positive_pairs=labels.count(1),negative_pairs=labels.count(0),no_positive_windows=int(1 not in labels)))
                selected.append(m)
        expected_sources={s for s,heldout in SOURCES.items() if heldout!=fold}
        require(len(order)==1000 and hashlib.sha256(canonical(order).encode()).hexdigest()==bound['selected_order_sha256'] and dict(counts)==bound['selected_counts'],'原fold1000窗口顺序/计数不同')
        require(set(sources)==set(bound['source_counts'])==expected_sources and all(sources[s]==bound['source_counts'][s]['selected_unique']==500 for s in sources),'每fold两允许源各500不同')
    require(len(selected)==len(uids)==len(coords)==3000,'原三池必须3000唯一窗口')
    return selected,pool_refs


def joined_window(m,row):
    j=row['job'];require((j['job_id'],row['frame_number'],row['stage'],row['row_index'],row['track_id'])==coordinate(m)
        and j['regime']=='R' and j['seed']==20261024 and j['fold']==m['fold'] and j['sequence']==m['sequence'] and j['model_id']==m['teacher_model_id'],'选中R ledger源坐标不同')
    require(row['history_UIDs']==m['history_UIDs'] and row['query_GT_id']==m['query_GT_id']
        and [c['uid'] for c in row['pose_candidates']]==m['candidate_UIDs'] and [c['label'] for c in row['pose_candidates']]==m['pair_labels'],'选中窗历史/query/候选UID和label不一致')
    require(row['new_solver_calls']==0 and row['Pose_support_is_accuracy'] is False and row['local_cost_comparison_is_causal'] is False,'仅既有描述性机会')
    anchor=row['earliest_stage_trusted3_anchor'];query=row['query_GT_id'];drift=None
    if anchor is not None:
        require(type(anchor['frame_number']) is int and 1<=anchor['frame_number']<=row['frame_number'],'anchor不可来自未来')
        drift=str(query)!=str(anchor['gt_id']) if query is not None else None
    require(row['flags']['earliest_stage_trusted3_anchor_drift'] is drift,'漂移须bool/null且与anchor/query一致')
    flags={k:row['flags'][k] for k in FLAGS};require(all(v is None or type(v) is bool for v in flags.values()),'六机会旗标只准bool/null')
    labels=m['pair_labels'];counts=row['absolute_counts']
    require((counts['candidates'],counts['positive'],counts['known_negative'],counts['unknown'])==(len(labels),labels.count(1),labels.count(0),labels.count(None)),'标签全分母不同')
    return dict(**{k:m[k] for k in ('window_uid','fold','sequence','source_job_id','candidate_frame_number','source_stage','source_row_index','source_track_id','teacher_model_id','history_UIDs','candidate_UIDs','pair_labels')},
        query_GT_id=query,earliest_stage_trusted3_anchor=anchor,anchor_drift=drift,no_positive=1 not in labels,all_pairs=len(labels),known_pairs=sum(x is not None for x in labels),
        positive_pairs=labels.count(1),known_negative_pairs=labels.count(0),unknown_pairs=labels.count(None),first_stop=row['first_stop'],**flags,
        labels_changed=False,drift_is_true_identity_error=False,new_model_forwards=0)


def ledger_join(metadata,teachers):
    wanted={coordinate(m):m for m in metadata};matched={};scanned={}
    for jid,teacher in teachers.items():
        found=set();seen=set();count=0
        with gzip.open(checked(teacher['ledger'],'ledger'),'rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line);count+=1;require(row['job']==teacher['job'],'R ledger混入其他teacher')
                key=(jid,row['frame_number'],row['stage'],row['row_index'],row['track_id']);require(key not in seen,'R ledger源坐标重复');seen.add(key)
                if key in wanted:
                    require(key not in matched,'选中窗重复匹配');matched[key]=joined_window(wanted[key],row);found.add(key)
        expected={k for k in wanted if k[0]==jid}
        require(count==teacher['row_count']==teacher['ledger']['rows'] and found==expected and len(found)==500,'每R teacher须全源行数完整且匹配500窗')
        scanned[jid]=dict(rows=count,matched_windows=len(found),ledger=teacher['ledger'])
    require(set(matched)==set(wanted) and len(matched)==3000,'3000窗完整逐值join不足')
    return [matched[coordinate(m)] for m in metadata],scanned


def group_counts(rows):
    require(rows,'分组不可缺失');out=dict(windows=len(rows))
    for k in ('all_pairs','known_pairs','positive_pairs','known_negative_pairs','unknown_pairs'):out[k]=sum(r[k] for r in rows)
    out['no_positive_windows']=sum(r['no_positive'] for r in rows)
    out['anchor_drift']={value:sum(('null' if r['anchor_drift'] is None else str(r['anchor_drift']).lower())==value for r in rows) for value in ('true','false','null')}
    out['first_stop']=dict(Counter(r['first_stop'] for r in rows))
    out['flag_counts']={k:{v:sum(('null' if r[k] is None else str(r[k]).lower())==v for r in rows) for v in ('true','false','null')} for k in FLAGS}
    return out


def summaries(rows):
    out=dict(all=group_counts(rows),per_fold={},per_fold_source={},per_source={},source_equal_descriptions={})
    for fold in FOLDS:
        out['per_fold'][fold]=group_counts([r for r in rows if r['fold']==fold]);out['per_fold_source'][fold]={}
        for seq,heldout in SOURCES.items():
            if heldout!=fold:out['per_fold_source'][fold][seq]=group_counts([r for r in rows if r['fold']==fold and r['sequence']==seq])
    out['per_source']={seq:group_counts([r for r in rows if r['sequence']==seq]) for seq in SOURCES}
    for name in ('anchor_drift','no_positive',*FLAGS):
        rates={}
        for seq,heldout in SOURCES.items():
            fold_rates=[]
            for fold in FOLDS:
                if fold==heldout:continue
                group=[r[name] for r in rows if r['fold']==fold and r['sequence']==seq and r[name] is not None]
                fold_rates.append(100*sum(group)/len(group) if group else None)
            rates[seq]=None if None in fold_rates else mean(fold_rates)
        out['source_equal_descriptions'][name]=dict(source_rates_pp=rates,three_source_equal_mean_rate_pp=mean(rates.values()) if None not in rates.values() else None,
            source_training_folds_are_not_independent_matches=True,interval_not_estimated=True)
    return out


def window_outputs(report,expected):
    path=checked(report['windows_jsonl'],'windows');actual=[]
    with path.open(encoding='utf-8-sig') as stream:
        for line in stream:actual.append(json.loads(line))
    require(len(actual)==len(expected)==3000 and all(canonical(a)==canonical(b) for a,b in zip(actual,expected)),'windows.jsonl全部3000窗顺序/UID/label/anchor不同')
    path=checked(report['windows_csv'],'windows')
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);require(reader.fieldnames==FIELDS,'CSV列不同');rows=list(reader)
    require(len(rows)==3000 and all(None not in r and all(v is not None for v in r.values()) for r in rows),'CSV行/列完整性不同')
    for actual,expect in zip(rows,expected):
        for k in FIELDS:
            value=expect[k];encoded=canonical(value) if isinstance(value,(dict,list)) else ('null' if value is None else str(value))
            require(actual[k]==encoded,'CSV每窗原绝对值/标签/UID不同：'+k)
    return dict(windows_jsonl=report['windows_jsonl'],windows_csv=report['windows_csv'],every_row_and_field_exact=True)


def report_gate(cfg,protocol,report,rows,scanned):
    require(report['schema']=='teacher_anchor_selected_R_bank_audit_v1' and report['status']==PRODUCER_STATUS and same_ref(report['protocol'],protocol)
        and report['input_root']==cfg['input_root'] and report['opportunity_verification']==cfg['opportunity_verification'] and report['opportunity_report']==cfg['opportunity_report']
        and report['selected_windows']==len(rows)==3000 and report['R_teacher_units']==6 and report['RS_ledgers_opened']==0 and report['original_frames_opened']==0
        and report['GT_cache_weights_or_media_opened'] is False and report['pool_rebuilt'] is False and report['labels_changed'] is False and report['window_selection_changed'] is False,'真实完整3000交叉报告来源或零执行边界不同')
    zero(report);require(report['scanned_teacher_ledgers']==scanned,'完整六R账本扫描/选中数量不同')
    expected=summaries(rows);require(same(report['descriptions'],expected),'各fold/source绝对计数或两fold→三源率不同')
    return expected


def write_new(path,value):
    p=physical(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


def verify(config,report_path,output):
    config,report_path,output=map(physical,(config,report_path,output));protocol=ref(config);require(protocol['sha256']==CFG_SHA,'仅本次固定已完成交叉核查协议')
    cfg=read(protocol);report_ref=ref(report_path);report=read(report_ref)
    require(EXP in report_path.parents and EXP in output.parents and not output.parent.exists(),'独立终验拒绝覆盖partial/成功')
    inputs,teachers=source_metadata(cfg)
    allowed=[b['pool']['path'] for b in inputs['folds'].values()]+[u['ledger']['path'] for u in teachers.values()]+[report['windows_jsonl']['path']]
    write_new(output.parent/'intent.json',dict(status='started_not_committed',protocol=protocol,report=report_ref,implementation=ref(__file__),new_optimizer_updates=0,test_read=False))
    try:
        with raw_guard(allowed) as guard:
            metadata,pools=pool_metadata(inputs,teachers);expected,scanned=ledger_join(metadata,teachers)
            outputs=window_outputs(report,expected);summary=report_gate(cfg,protocol,report,expected,scanned)
            for reference in pools.values():checked(reference,'pool')
            require(guard['blocked_open_attempts']==0,'曾尝试禁止原始输入')
            result=dict(schema='teacher_anchor_bank_independent_verification_v1',status=STATUS,protocol=protocol,analysis=report_ref,implementation=ref(__file__),
                selected_windows=3000,unique_window_UIDs=3000,unique_source_coordinates=3000,fold_windows={f:1000 for f in FOLDS},
                fold_source_windows={f:{s:summary['per_fold_source'][f][s]['windows'] for s in summary['per_fold_source'][f]} for f in FOLDS},
                every_window_UID_label_history_query_source_anchor_exact=True,original_pool_SHA_unchanged=pools,original_R_teacher_units=6,
                scanned_teacher_ledgers=scanned,outputs=outputs,verified_descriptions=summary,new_confidence_intervals=0,new_AssA_HOTA_IDF1=False,
                original_frames_cache_GT_weights_or_media_opened=False,raw_open_guard=dict(guard),pool_rebuilt=False,labels_changed=False,window_selection_changed=False,
                anchor_drift_is_identity_error=False,**{k:0 for k in ZERO_KEYS},test_read=False,verified_utc=datetime.now(timezone.utc).isoformat())
            write_new(output,result);return result
    except BaseException as error:
        write_new(output.parent/'failed.json',dict(status='failed_teacher_anchor_bank_verification_partial_preserved',error=repr(error),traceback=traceback.format_exc(),
            **{k:0 for k in ZERO_KEYS},test_read=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','report','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--execute',action='store_true');args=p.parse_args()
    result=verify(args.config,args.report,args.output) if args.execute else dict(status='readonly_teacher_anchor_verifier_candidate_not_executed')
    print(canonical(dict(status=result['status'])))
