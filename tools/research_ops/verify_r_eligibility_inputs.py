"""独立核验新R资格侧表；只核既有预测pool和已验诊断选中记录，不导入生产分类/绑定实现。"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import gzip
import hashlib
from itertools import zip_longest
import json
import os
from pathlib import Path
import re
import traceback

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/r_candidate_eligibility_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026)
SOURCE_FOLDS={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
SOURCE_KEYS=('source_job_id','candidate_frame_number','source_stage','source_row_index','source_track_id','teacher_model_id','teacher_regime','teacher_seed','fold','sequence')
RULE='original_pre_probability_stage_active_AND_enabled'
EVIDENCE='all_candidate_motion_gate_values_observed_under_frozen_active_enabled_identity'
CANDIDATE_MASK_FIELDS=frozenset(('candidate_UIDs','candidate_scoring_mask','fold','frame_number','history_UIDs','label_values_unchanged',
    'mask_source','mask_uses_GT_labels_or_coordinates','sequence','source_job_id','source_summary_coordinate','stage','track_id','training_authorized_by_this_file','window_uid'))
STATUS='complete3000_R_candidate_eligibility_inputs_sources_masks_bindings_and_exposures_independently_verified'
ZERO_KEYS=('new_optimizer_updates','new_model_forwards','new_image_predictions','new_tracking','new_solver_calls','new_TrackEval')
EXPECTED=dict(raw_candidate_pairs=42465,raw_known_pairs=35240,raw_positive_pairs=1115,raw_negative_pairs=34125,raw_unknown_pairs=7225,
    kept_candidate_pairs=8234,kept_known_pairs=6153,kept_positive_pairs=1092,kept_negative_pairs=5061,kept_unknown_pairs=2081,
    excluded_candidate_pairs=34231,excluded_known_pairs=29087,excluded_positive_pairs=23,excluded_negative_pairs=29064,excluded_unknown_pairs=5144,
    raw_known_empty=0,effective_known_empty=993)
FOLD_EXPECTED={'game4':(2618,433,2185,709),'game6':(1277,304,973,557),'game9':(2258,355,1903,741)}

def require(ok,message):
    if not ok:raise ValueError(message)
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def safe(value):
    p=Path(value);require(p.is_absolute(),'只准绝对物理路径');p=Path(os.path.abspath(p))
    require(R in p.parents and not any(x.lower() in ('test','gt') or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'禁止测试/GT或研究根外来源')
    for x in (p,*p.parents):
        if x.exists() or x.is_symlink():require(not x.is_symlink() and not getattr(x.lstat(),'st_file_attributes',0)&0x400,'不跟随链接/junction')
    require(p.name.lower() not in ('posthoc_gt_labels.json','gap_registry.json') and (p.suffix in ('.json','.jsonl','.py') or p.name.endswith('.jsonl.gz')),'不读取GT/模型/媒体/cache或其他二进制')
    return p
def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def checked(reference):
    require(isinstance(reference,dict) and isinstance(reference.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',reference['sha256']),'来源缺SHA')
    p=safe(reference['path']);require(sha(p)==reference['sha256'],'来源SHA改变：'+str(p));return p
def ref(path):return dict(path=str(safe(path)),sha256=sha(path))
def builder_audit_ref(output_root):
    """先核目录范围，再对最终audit文件执行原白名单/SHA/所有父目录无junction检查。"""
    directory=Path(os.path.abspath(output_root))
    require(EXP in directory.parents,'输入audit必须位于本实验独立目录')
    return ref(directory/'audit.json')
def read(reference):
    require(safe(reference['path']).suffix=='.json','小元数据必须JSON');return json.loads(checked(reference).read_text(encoding='utf-8-sig'))
def rows(reference):
    p=safe(reference['path']);require(p.name in ('real_pool.jsonl','selected_windows.jsonl','selected_candidates.jsonl.gz','candidate_scoring_masks.jsonl','sidecars.jsonl','bindings.jsonl'),'只准原pool/已验选中记录/新侧表，不读frames或cache')
    p=checked(reference);opener=gzip.open if p.name.endswith('.gz') else open;count=0
    with opener(p,'rt',encoding='utf-8-sig') as stream:
        for line in stream:
            require(bool(line.strip()),'原逐行清单不得有空行');count+=1;yield json.loads(line)
    if 'rows' in reference:require(count==reference['rows'],'来源行数不同')
def write(path,value):
    p=safe(path);require(EXP in p.parents,'独立收据仅写本实验');p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())

def independent_counts(labels,mask):
    require(len(labels)==len(mask) and all(type(v) is bool for v in mask)
        and all(v is None or type(v) is int and v in (0,1) for v in labels),'原标签或完整bool资格异常')
    groups={'candidate':lambda v:True,'known':lambda v:v is not None,'positive':lambda v:v==1,'negative':lambda v:v==0,'unknown':lambda v:v is None}
    result={}
    for group,predicate in groups.items():
        raw=sum(predicate(v) for v in labels);kept=sum(predicate(v) and keep for v,keep in zip(labels,mask))
        result.update({f'raw_{group}_pairs':raw,f'kept_{group}_pairs':kept,f'excluded_{group}_pairs':raw-kept})
    result.update(raw_known_empty=int(result['raw_known_pairs']==0),effective_known_empty=int(result['kept_known_pairs']==0));return result

def teacher_record(job,summary,candidates,provenance):
    """只提取已验公开字段；依据原gate字段来源证明active，不凭概率或label选择mask。"""
    require(job['regime']=='R' and job['seed']==20261024 and job['fold']!=SOURCE_FOLDS[job['sequence']],'只准原六个R teacher训练域')
    require(summary['job_id']==job['job_id'] and summary['fold']==job['fold'] and summary['sequence']==job['sequence']
        and summary['teacher_regime']=='R' and summary['teacher_seed']==20261024 and summary['is_selected_R_window'] is True
        and summary['stage']=='high_score' and summary['unavailable_field']==[],'选中摘要原身份/字段不全')
    require(len(candidates)==summary['counts']['all_pairs']>0,'完整原候选数不同')
    uids=[];labels=[];enabled=[]
    for i,c in enumerate(candidates):
        require(c['window_uid']==summary['window_uid'] and c['job_id']==job['job_id'] and c['candidate_index']==i,'候选原顺序/来源不同')
        values=(c['motion_gate'],c['enabled'],c['scoring_eligible'])
        require(all(type(v) is bool for v in values) and values[0]==values[1]==values[2]
            and c['motion_gate_missing_reason'] is None,'不能猜unknown/inactive为原active资格')
        require(c['labels_changed'] is False and c['hypothetical_mask_executed'] is False,'旧诊断必须零更新不改标签')
        uids.append(c['uid']);labels.append(c['label']);enabled.append(c['enabled'])
    require(len(set(uids))==len(uids),'候选UID重复');counts=independent_counts(labels,enabled)
    require(all(summary['counts'][k]==counts[v] for k,v in [('all_pairs','raw_candidate_pairs'),('known_pairs','raw_known_pairs'),('positive_pairs','raw_positive_pairs'),('known_negative_pairs','raw_negative_pairs'),('unknown_pairs','raw_unknown_pairs')]),'原摘要pair分母不同')
    return dict(job=job,summary=summary,candidate_UIDs=uids,labels=labels,enabled=enabled,provenance=provenance)

def check_candidate_mask(candidate,metadata,record):
    require(set(candidate)==CANDIDATE_MASK_FIELDS,'既有候选决策字段必须精确，不接受猜测别名')
    require(candidate['window_uid']==metadata['window_uid'] and candidate['fold']==metadata['fold'] and candidate['sequence']==metadata['sequence']
        and candidate['source_job_id']==metadata['source_job_id'] and candidate['frame_number']==metadata['candidate_frame_number']
        and candidate['stage']==metadata['source_stage'] and candidate['track_id']==metadata['source_track_id']
        and candidate['history_UIDs']==metadata['history_UIDs'] and candidate['candidate_UIDs']==metadata['candidate_UIDs']
        and candidate['candidate_scoring_mask']==record['enabled'] and all(type(v) is bool for v in candidate['candidate_scoring_mask']), '原候选mask决策与source坐标/资格不同')
    coordinate=candidate['source_summary_coordinate']
    require(isinstance(coordinate,dict) and coordinate==dict(frame_number=metadata['candidate_frame_number'],stage=metadata['source_stage'],row_index=metadata['source_row_index'],track_id=metadata['source_track_id']),'候选决策完整原行坐标不同')
    require(candidate['label_values_unchanged'] is True and candidate['mask_uses_GT_labels_or_coordinates'] is False
        and candidate['mask_source']=='original_R_teacher_pre_probability_active_and_enabled'
        and candidate['training_authorized_by_this_file'] is False,'既有候选决策原标签/无GT选mask/未授权训练声明不同')

def verify_window(window,record,candidate,sidecar,binding):
    """独立逐窗重建binding字节语义，不调用bind_window_mask或生产分类器。"""
    metadata=window['aligned_bank_metadata'];summary=record['summary'];job=record['job']
    uids=[c['prediction']['uid'] for c in window['candidates']];labels=[c['label'] for c in window['candidates']];history=[h['uid'] for h in window['history']]
    require(window['window_uid']==metadata['window_uid']==summary['window_uid'] and window['sequence']==metadata['sequence']==job['sequence']
        and history==metadata['history_UIDs']==summary['history_UIDs'] and len(history)==len(set(history))==3
        and uids==metadata['candidate_UIDs']==record['candidate_UIDs'] and labels==metadata['pair_labels']==record['labels']
        and metadata['query_GT_id']==summary['query_GT_id'] and metadata['query_GT_id'] is not None,'原pool/公开teacher历史query/候选标签不同')
    expected_source=dict(source_job_id=job['job_id'],candidate_frame_number=summary['frame_number'],source_stage=summary['stage'],source_row_index=summary['row_index'],source_track_id=summary['track_id'],
        teacher_model_id=job['model_id'],teacher_regime=job['regime'],teacher_seed=job['seed'],fold=job['fold'],sequence=job['sequence'])
    require(all(metadata[k]==expected_source[k] for k in SOURCE_KEYS),'原pool teacher坐标不同')
    check_candidate_mask(candidate,metadata,record)
    require(sidecar['schema']=='R_candidate_eligibility_sidecar_v1' and sidecar['eligibility_rule']==RULE and sidecar['eligibility_stage']=='pre_probability'
        and sidecar['labels_used_to_choose_mask'] is False and sidecar['active'] is True and sidecar['active_evidence']==EVIDENCE
        and sidecar['window_uid']==window['window_uid'] and sidecar['history_UIDs']==history and sidecar['candidate_UIDs']==uids
        and all(sidecar[k]==expected_source[k] for k in SOURCE_KEYS) and sidecar['provenance']==record['provenance'], '新侧表身份/原资格来源不同')
    eligible=record['enabled'];require(sidecar['enabled']==eligible and sidecar['scoring_eligible']==eligible
        and all(type(v) is bool for v in sidecar['enabled']) and all(type(v) is bool for v in sidecar['scoring_eligible']), '新侧表不得按label/概率修改资格')
    known=[i for i,v in enumerate(labels) if v is not None];counts=independent_counts(labels,eligible);require(known,'原pool不可新增all-unknown窗')
    body=dict(schema='R_candidate_eligibility_bound_window_v1',method_schema='R_candidate_eligibility_masked_BCE_method_v1',eligibility_rule=RULE,
        window_uid=window['window_uid'],history_UIDs=history,candidate_UIDs=uids,all_labels=labels,all_scoring_eligible=eligible,known_indices=known,
        known_candidate_UIDs=[uids[i] for i in known],known_labels=[labels[i] for i in known],known_scoring_eligible=[eligible[i] for i in known],source=expected_source,
        sidecar_sha256=digest(sidecar),accounting=counts,labels_changed=False,original_forward_known_order_preserved=True)
    require(binding==dict(body,binding_sha256=digest(body)),'新binding必须与独立原输入/资格重建逐值相等')
    return counts

def teacher_records(report):
    require(len(report['units'])==12,'已验诊断12个unit缺失');records={};cells=set();coordinates=set()
    for bound in report['units']:
        unit=read(bound['receipt']);job=unit['job'];require(job==bound['job'] and unit['status']=='complete','原unit来源不同')
        cell=tuple(job[k] for k in ('fold','sequence','regime','seed'));require(cell not in cells,'原teacher单元重复');cells.add(cell)
        if job['regime']!='R':require(unit['selected_windows']['rows']==unit['selected_candidates']['rows']==0,'RS不应新增选窗');continue
        provenance=dict(diagnostic_unit_receipt=bound['receipt'],selected_windows=unit['selected_windows'],selected_candidates=unit['selected_candidates'])
        iterator=iter(rows(unit['selected_candidates']));pending=next(iterator,None);count=0
        for summary in rows(unit['selected_windows']):
            group=[];uid=summary['window_uid']
            while pending is not None and pending['window_uid']==uid:group.append(pending);pending=next(iterator,None)
            coordinate=(job['job_id'],summary['frame_number'],summary['stage'],summary['row_index'],summary['track_id'])
            require(coordinate not in coordinates,'同一原teacher行不能复制成多个新window');coordinates.add(coordinate)
            require(uid not in records,'原选中window UID重复');records[uid]=teacher_record(job,summary,group,provenance);count+=1
        require(pending is None and count==500,'R teacher原500选中行/全候选未读齐')
    expected={(fold,seq,regime,20261024) for seq,heldout in SOURCE_FOLDS.items() for fold in FOLDS if fold!=heldout for regime in ('R','RS')}
    require(cells==expected and len(records)==3000,'原12/六R/3000来源矩阵不同');return records

def verify_exposure_table(table,fold,seed,index):
    require(table['fold']==fold and table['seed']==seed and table['augmentation']=='none_original_strongmotion','原曝光表身份/无增广不同')
    require(table['regimes_share_R']==['R','RS'] and table['S_order_and_rows_exact_original'] is True,'R/RS原共享顺序或S来源不同')
    entries=table['real'];require(len(entries)==3000 and len(table['synthetic'])==1000,'原3000R/1000S表不完整')
    for epoch in range(3):
        group=entries[epoch*1000:(epoch+1)*1000]
        require({e['window_uid'] for e in group}==set(index) and all(type(e['epoch']) is int and e['epoch']==epoch and e['domain']=='real' for e in group),'原每epoch1000唯一UID/顺序预算不同')
    effective=Counter()
    for entry in entries:
        counts=index[entry['window_uid']]
        require(entry['candidate_pairs']==counts['raw_candidate_pairs'] and entry['labelled_pairs']==counts['raw_known_pairs'],'原曝光all/known改变')
        effective.update(counts)
    effective['scheduled_R_windows']=3000
    effective['all3R_empty_steps']=sum(all(index[e['window_uid']]['effective_known_empty']==1 for e in entries[start:start+3]) for start in range(0,3000,3))
    return dict(fold=fold,seed=seed,window_exposures=3000,counts=dict(effective),R_UID_epoch_chain_sha256=digest([[e['window_uid'],e['epoch']] for e in entries]),S_rows_sha256=digest(table['synthetic']))

def verify(config,output):
    config=safe(config);output=safe(output);require(EXP in output.parents and not output.parent.exists(),'终验必须独立新目录，不覆盖成功/partial')
    protocol=ref(config);cfg=read(protocol)
    require(cfg['schema']=='r_eligibility_mask_input_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True
        and cfg['GT_coordinates_read'] is False and all(cfg[k]==0 for k in ('new_optimizer_updates','new_model_forwards','new_tracking','new_TrackEval'))
        and all(cfg.get(k,0)==0 for k in ('new_image_predictions','new_solver_calls')),'新input协议/零更新封存不同')
    bundle=safe(Path(cfg['bundle'])/'bundle_manifest.json').parent;manifest=read(cfg['bundle_manifest'])
    require(bundle.parent==R/'code' and {e['path'] for e in manifest['files']}=={'tools/research_ops/r_eligibility_inputs.py','tools/research_ops/r_candidate_eligibility_method.py'},'输入producer仅冻结两必要源码')
    for entry in manifest['files']:require(sha(bundle/entry['path'])==entry['sha256'],'输入producer源码SHA变化')
    source=read(cfg['source_training_protocol']);bank=read(cfg['selected_R_bank_root'])
    require(cfg['source_training_protocol']['sha256']=='2acc7642109c317b9ca694d3649a864c5553e177f20425d24726de1781c7d3c6'
        and source['input_root']==cfg['selected_R_bank_root'] and set(bank['folds'])==set(FOLDS)
        and bank['all_windows_roundtrip_exact'] is True and bank['test_read'] is False,'必须原三pool输入根')
    complete=read(cfg['diagnosis_complete']);report=read(cfg['diagnosis_report']);verified=read(cfg['diagnosis_verification'])
    require(report['status']=='complete3000_R_windows180118_existing_rows_state_label_alignment_diagnosis_no_factor_executed'
        and verified['status']=='complete_state_label_alignment_all_sources_classifications_weights_and_intervals_verified'
        and verified['analysis']==cfg['diagnosis_report'] and verified['producer_processes_absent'] is True,'旧诊断及独立终验未闭合')
    # 完成根实际字段名由协议明确冻结；不得把旧分类或权重审计再次执行。
    require(complete['status']=='complete3000_R_windows180118_existing_rows_independently_verified_one_factor_candidate_registered_no_training'
        and complete['analysis']==cfg['diagnosis_report'] and complete['independent_verification']==cfg['diagnosis_verification']
        and complete['mask_candidates']==cfg['candidate_masks'] and complete['actual_producer_and_verifier_Name_CommandLine_absent'] is True,'诊断完成根的report/终验引用/实际退出不同')
    builder_ref=builder_audit_ref(cfg['output_root']);builder=read(builder_ref)
    require(builder['schema']=='r_eligibility_mask_inputs_audit_v1' and builder['status']=='complete3000_original_R_windows_scoring_masks_bound_not_training_admission'
        and builder['protocol']==protocol and set(builder['folds'])==set(FOLDS)
        and builder['source_training_protocol']==cfg['source_training_protocol'] and builder['selected_R_bank_root']==cfg['selected_R_bank_root']
        and builder['diagnosis_complete']==cfg['diagnosis_complete'] and builder['unknown_loss_pairs']==0
        and all(builder[k] is False for k in ('source_pool_files_modified','labels_changed','window_selection_or_order_changed','normalizer_refit','synthetic_inputs_modified','GT_coordinates_read','test_read')),'新侧表builder未完整闭合')
    output.parent.mkdir(parents=True);write(output.parent/'intent.json',dict(status='started_not_committed',protocol=protocol,builder_audit=builder_ref,implementation=ref(__file__)))
    try:
        teachers=teacher_records(report);candidate_rows=list(rows(cfg['candidate_masks']));candidates={c['window_uid']:c for c in candidate_rows}
        require(len(candidate_rows)==len(candidates)==3000,'原候选mask决策3000唯一窗不同');seen=set();fold_audits={};total=Counter();indices={}
        for fold in FOLDS:
            bound=builder['folds'][fold];pool=bank['folds'][fold]['pool'];require(bound['pool']==pool,'builder不得重建原pool')
            manifest=read(bound['manifest']);require(manifest['schema']=='R_candidate_eligibility_fold_inputs_v1' and manifest['fold']==fold
                and manifest['status']=='complete1000_original_R_windows_pre_probability_masks_bound'
                and manifest['original_pool']==pool and manifest['sidecars']==bound['sidecars'] and manifest['bindings']==bound['bindings'],'新fold manifest来源不同')
            counts=Counter();index={};order=[];source_counts=Counter()
            for window,sidecar,binding in zip_longest(rows(pool),rows(bound['sidecars']),rows(bound['bindings'])):
                require(window is not None and sidecar is not None and binding is not None,'原pool/侧表/binding未完整1000行')
                uid=window['window_uid'];require(uid not in seen and uid in teachers and uid in candidates,'原window丢失/重复或未知')
                metadata=window['aligned_bank_metadata'];require(metadata['fold']==fold and metadata['sequence'] in SOURCE_FOLDS
                    and SOURCE_FOLDS[metadata['sequence']]!=fold,'pool混heldout来源')
                actual=verify_window(window,teachers[uid],candidates[uid],sidecar,binding)
                counts.update(actual);index[uid]=actual;order.append(uid);source_counts[metadata['sequence']]+=1;seen.add(uid)
            require(len(index)==1000 and set(source_counts.values())=={500} and len(source_counts)==2,'每fold原1000/两允许源500缺失')
            k,p,n,nonempty=FOLD_EXPECTED[fold]
            require((counts['kept_known_pairs'],counts['kept_positive_pairs'],counts['kept_negative_pairs'],1000-counts['effective_known_empty'])==(k,p,n,nonempty),'fold有效正负/空窗预算不同')
            counts['windows']=1000
            require(manifest['counts']==dict(counts) and manifest['input_protocol']==protocol and manifest['diagnosis_complete']==cfg['diagnosis_complete']
                and manifest['candidate_masks']==cfg['candidate_masks'] and manifest['labels_changed'] is False and manifest['window_order_changed'] is False
                and manifest['effective_unknown_loss_pairs']==0,'fold manifest实际数量/绑定/不改标签声明不同')
            fold_audits[fold]=dict(pool=pool,sidecars=bound['sidecars'],bindings=bound['bindings'],manifest=bound['manifest'],windows=1000,counts=dict(counts),source_counts=dict(source_counts),original_window_order_sha256=digest(order))
            indices[fold]=index;total.update(counts)
        expected_total=dict(EXPECTED,windows=3000)
        require(seen==set(teachers)==set(candidates) and dict(total)==expected_total and builder['totals']==dict(total),'完整3000/42465/6153/993预算不符')
        require(cfg['expected_counts'] and all(key in expected_total and type(value) is int and value==expected_total[key] for key,value in cfg['expected_counts'].items()),'协议声明绝对预算与独立完整重计不同')
        tables=builder['exposure_tables'];require(len(tables)==9 and {(t['fold'],t['seed']) for t in tables}=={(f,s) for f in FOLDS for s in SEEDS},'九表重复或缺失')
        exposures=[]
        for t in tables:
            require(t['table']==source['exposures'][t['fold']][str(t['seed'])],'不能生成新曝光顺序')
            exposure=verify_exposure_table(read(t['table']),t['fold'],t['seed'],indices[t['fold']])
            require(exposure['counts']==t['counts'] and t['shared_by_R_RS'] is True and t['planned_only'] is True,'原曝光映射计数/共享状态不同')
            exposures.append(exposure)
        result=dict(schema='R_candidate_eligibility_inputs_independent_verification_v1',status=STATUS,protocol=protocol,implementation=ref(__file__),builder_audit=builder_ref,
            folds=fold_audits,totals=dict(total),windows=3000,exposure_tables=exposures,R_window_exposures_shared_once=27000,
            original_pool_order_labels_UIDs_and_known_projection_exact=True,pre_probability_mask_not_chosen_by_labels=True,
            original_R_S_order_references_unchanged=True,production_classifier_or_bind_window_mask_called=False,old_diagnosis_or_weight_audit_rerun=False,
            GT_coordinates_read=False,test_read=False,**{k:0 for k in ZERO_KEYS},verified_utc=datetime.now(timezone.utc).isoformat())
        write(output,result);return result
    except BaseException:
        write(output.parent/'failed.json',dict(status='failed_R_eligibility_inputs_verification_preserved_no_replay',traceback=traceback.format_exc(),protocol=protocol,**{k:0 for k in ZERO_KEYS},test_read=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    value=verify(args.config,args.output) if args.execute else dict(status='readonly_R_eligibility_inputs_verifier_candidate_no_data_opened')
    print(canonical(dict(status=value['status'])))
