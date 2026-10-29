"""冻结原3000 R窗的概率前资格侧表；不重建池、不加载模型或GT坐标。"""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).parent))
import r_candidate_eligibility_method as method

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/r_candidate_eligibility_a01';ROOT=Path(__file__).resolve().parents[2]
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026)
STATUS='complete3000_original_R_windows_scoring_masks_bound_not_training_admission'
ZERO=('new_optimizer_updates','new_model_forwards','new_tracking','new_TrackEval')

def require(value,message):
    if not value:raise ValueError(message)

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def safe(path,output=False):
    p=Path(os.path.abspath(path));require(R in p.parents,'仅实际DResearch')
    require(not any(x.lower() in ('test','gt') or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'GT坐标/测试封存')
    require(p.suffix.lower() not in ('.pt','.pth','.ckpt','.jpg','.jpeg','.png','.exr','.mp4'),'输入冻结不读模型/媒体')
    if output:require(EXP in p.parents,'只写新mask实验目录')
    for v in (p,*p.parents):
        if v.exists() or v.is_symlink():require(not v.is_symlink() and not getattr(v.lstat(),'st_file_attributes',0)&0x400,'不跟随junction')
    return p

def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def ref(path):return dict(path=str(safe(path)),sha256=sha(path))

def checked(v):
    p=safe(v['path']);require(sha(p)==v['sha256'],'SHA变化：'+str(p));return p

def read(v):
    p=safe(v['path']);require(p.suffix=='.json','只读小JSON');checked(v)
    return json.loads(p.read_text(encoding='utf-8-sig'))

def rows(v):
    p=safe(v['path']);require(p.name in ('real_pool.jsonl','selected_windows.jsonl','selected_candidates.jsonl.gz','candidate_scoring_masks.jsonl'),'只准原pool及已验选中记录/候选清单')
    checked(v);opener=gzip.open if p.suffix=='.gz' else open;n=0
    with opener(p,'rt',encoding='utf-8') as f:
        for line in f:n+=1;yield json.loads(line)
    if 'rows' in v:require(n==v['rows'],'原行数变化')

def write(path,value):
    p=safe(path,output=True);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(canonical(value)+'\n')

def same_coordinate(summary,mask,job):
    return (summary['job_id'],summary['frame_number'],summary['stage'],summary['row_index'],summary['track_id'])==(
        mask['source_job_id'],mask['frame_number'],mask['stage'],mask['source_summary_coordinate']['row_index'],mask['track_id']) and (
        summary['fold'],summary['sequence'],summary['teacher_regime'],summary['teacher_seed'])==(
        job['fold'],job['sequence'],job['regime'],job['seed']) and mask['fold']==job['fold'] and mask['sequence']==job['sequence']

def sidecar_for(summary,pairs,job,mask,provenance):
    """先从非标签字段确定资格；完整标签仅用于之后源一致性/原known记账。"""
    require(job['regime']=='R' and job['seed']==20261024 and summary['stage']=='high_score' and summary['is_selected_R_window'],'只准原首seed R teacher选中high stage')
    require(same_coordinate(summary,mask,job) and summary['window_uid']==mask['window_uid'] and summary['history_UIDs']==mask['history_UIDs'],'候选清单/诊断源坐标不同')
    require(len(pairs)>0 and [p['uid'] for p in pairs]==mask['candidate_UIDs'] and all(p['window_uid']==summary['window_uid'] and p['job_id']==job['job_id'] for p in pairs),'逐candidate UID/来源不同')
    require(all(type(p['enabled']) is bool and type(p['motion_gate']) is bool and p['motion_gate_missing_reason'] is None for p in pairs), '原active资格不可确认，不猜unknown')
    enabled=[p['enabled'] for p in pairs]
    require(all(p['enabled']==p['motion_gate']==p['scoring_eligible'] for p in pairs) and enabled==mask['candidate_scoring_mask'],'冻结active-enabled恒等或候选清单不同')
    side=dict(schema=method.MASK_SCHEMA,eligibility_rule=method.RULE,eligibility_stage='pre_probability',labels_used_to_choose_mask=False,
        window_uid=summary['window_uid'],history_UIDs=summary['history_UIDs'],candidate_UIDs=[p['uid'] for p in pairs],active=True,enabled=enabled,scoring_eligible=list(enabled),
        source_job_id=job['job_id'],candidate_frame_number=summary['frame_number'],source_stage=summary['stage'],source_row_index=summary['row_index'],source_track_id=summary['track_id'],
        teacher_model_id=job['model_id'],teacher_regime=job['regime'],teacher_seed=job['seed'],fold=job['fold'],sequence=job['sequence'],
        active_evidence='all_candidate_motion_gate_values_observed_under_frozen_active_enabled_identity',provenance=provenance)
    labels=[p['label'] for p in pairs]
    require(sum(v is not None for v in labels)==summary['counts']['known_pairs'] and labels.count(1)==summary['counts']['positive_pairs']
        and labels.count(0)==summary['counts']['known_negative_pairs'] and labels.count(None)==summary['counts']['unknown_pairs'],'原候选标签预算不同')
    return side,labels

def validate(path):
    p=safe(path);cfg=json.loads(p.read_text(encoding='utf-8-sig'))
    require(cfg['schema']=='r_eligibility_mask_input_protocol_v1' and cfg['approved_by']=='root' and cfg['test_sealed'] is True
        and cfg['GT_coordinates_read'] is False and all(cfg[k]==0 for k in ZERO),'新输入协议/零SGD边界不同')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','必须冻结最小bundle执行')
    manifest=read(cfg['bundle_manifest']);require(len(manifest['files'])==2 and {x['path'] for x in manifest['files']}=={'tools/research_ops/r_eligibility_inputs.py','tools/research_ops/r_candidate_eligibility_method.py'}
        and ROOT.name==hashlib.sha256(canonical(manifest['files']).encode()).hexdigest(),'仅输入冻结必要两文件和内容地址')
    for item in manifest['files']:require(sha(ROOT/item['path'])==item['sha256'],'冻结输入代码变化')
    completed=read(cfg['diagnosis_complete']);report=read(cfg['diagnosis_report']);verified=read(cfg['diagnosis_verification'])
    require(completed['status']=='complete3000_R_windows180118_existing_rows_independently_verified_one_factor_candidate_registered_no_training'
        and completed['analysis']==cfg['diagnosis_report'] and completed['independent_verification']==cfg['diagnosis_verification']
        and completed['mask_candidates']==cfg['candidate_masks'],'必须原已闭合诊断/候选来源')
    require(verified['status']=='complete_state_label_alignment_all_sources_classifications_weights_and_intervals_verified'
        and verified['producer_processes_absent'] is True and verified['analysis']==cfg['diagnosis_report'],'原完整独立终验不足')
    source=read(cfg['source_training_protocol']);require(cfg['source_training_protocol']['sha256']=='2acc7642109c317b9ca694d3649a864c5553e177f20425d24726de1781c7d3c6'
        and source['input_root']==cfg['selected_R_bank_root'],'不得改池或曝光源')
    bank=read(cfg['selected_R_bank_root']);require(len(bank['folds'])==3 and bank['all_windows_roundtrip_exact'] is True and not bank['test_read'],'必须原池完成根')
    cfg['_protocol']=ref(p)
    return cfg,source,bank,report

def build(path):
    cfg,source,bank,report=validate(path)
    resource_spec=importlib.util.spec_from_file_location('eligibility_existing_resource_snapshot',checked(cfg['resource_source']))
    resource=importlib.util.module_from_spec(resource_spec);resource_spec.loader.exec_module(resource)
    before=resource.resource_snapshot();require(before['available_RAM_bytes']>=8589934592+3221225472 and before['commit_available_bytes']>=6442450944+3221225472,'输入读取保留RAM8GiB/commit6GiB及在飞3GiB')
    out=safe(cfg['output_root'],output=True);require(not out.exists(),'partial/成功输入不能覆盖或重建');out.mkdir(parents=True)
    masks={m['window_uid']:m for m in rows(cfg['candidate_masks'])};require(len(masks)==3000,'原3000候选清单不齐')
    sidecars={};original_labels={}
    for source_unit in report['units']:
        job=source_unit['job']
        if job['regime']!='R':continue
        unit=read(source_unit['receipt']);summaries={w['window_uid']:w for w in rows(unit['selected_windows'])}
        require(len(summaries)==500,'R teacher每源应原500选中窗')
        stream=iter(rows(unit['selected_candidates']));pending=next(stream,None);seen=set()
        while pending is not None:
            uid=pending['window_uid'];group=[]
            while pending is not None and pending['window_uid']==uid:group.append(pending);pending=next(stream,None)
            require(uid not in seen and uid not in sidecars and uid in summaries,'重复/跨窗候选group')
            seen.add(uid);provenance=dict(diagnostic_unit_receipt=source_unit['receipt'],selected_windows=unit['selected_windows'],selected_candidates=unit['selected_candidates'])
            side,labels=sidecar_for(summaries[uid],group,job,masks[uid],provenance);sidecars[uid]=side;original_labels[uid]=labels
        require(seen==set(summaries),'选中候选group缺失')
    require(len(sidecars)==3000 and set(sidecars)==set(masks),'3000侧表源不齐')
    folds={};totals=Counter();bindings_index={}
    for fold in FOLDS:
        directory=out/fold;directory.mkdir();sp=directory/'sidecars.jsonl';bp=directory/'bindings.jsonl';counts=Counter();n=0;unique=set()
        with sp.open('x',encoding='utf-8') as sf,bp.open('x',encoding='utf-8') as bf:
            for window in rows(bank['folds'][fold]['pool']):
                uid=window['window_uid'];require(uid not in unique and uid in sidecars,'池UID重复/侧表缺失');unique.add(uid);side=sidecars[uid]
                require(side['fold']==fold and [c['label'] for c in window['candidates']]==original_labels[uid],'原池label顺序不能改变')
                bound=method.bind_window_mask(window,side);n+=1;counts.update(bound['accounting']);bindings_index[uid]=bound
                sf.write(canonical(side)+'\n');bf.write(canonical(bound)+'\n')
        require(n==1000 and len(unique)==1000 and counts['kept_known_pairs']>0,'每fold须1000唯一原窗且有非空有效监督')
        counts['windows']=n;totals.update(counts)
        manifest=dict(schema='R_candidate_eligibility_fold_inputs_v1',status='complete1000_original_R_windows_pre_probability_masks_bound',fold=fold,
            original_pool=bank['folds'][fold]['pool'],sidecars=dict(**ref(sp),rows=1000),bindings=dict(**ref(bp),rows=1000),counts=dict(counts),
            input_protocol=cfg['_protocol'],diagnosis_complete=cfg['diagnosis_complete'],candidate_masks=cfg['candidate_masks'],labels_changed=False,window_order_changed=False,
            effective_unknown_loss_pairs=0,new_optimizer_updates=0,test_read=False)
        write(directory/'manifest.json',manifest);folds[fold]=dict(pool=manifest['original_pool'],sidecars=manifest['sidecars'],bindings=manifest['bindings'],manifest=ref(directory/'manifest.json'))
    require((totals['windows'],totals['raw_candidate_pairs'],totals['raw_known_pairs'],totals['raw_unknown_pairs'],totals['kept_known_pairs'],totals['kept_positive_pairs'],totals['kept_negative_pairs'],totals['effective_known_empty'])==(3000,42465,35240,7225,6153,1092,5061,993),'完整新mask分母不同')
    tables=[]
    for fold in FOLDS:
        for seed in SEEDS:
            value=source['exposures'][fold][str(seed)];table=read(value);entries=table['real'];counts=Counter()
            require(table['fold']==fold and table['seed']==seed and len(entries)==3000,'九原曝光表标识/预算不同')
            for start in range(0,3000,3):
                group=entries[start:start+3];empty=0
                for entry in group:
                    b=bindings_index[entry['window_uid']];a=b['accounting'];require(b['source']['fold']==fold and entry['candidate_pairs']==a['raw_candidate_pairs'] and entry['labelled_pairs']==a['raw_known_pairs'],'原曝光all/known不同')
                    counts.update(a);counts['scheduled_R_windows']+=1;empty+=a['effective_known_empty']
                counts['all3R_empty_steps']+=int(empty==3)
            tables.append(dict(fold=fold,seed=seed,table=value,counts=dict(counts),shared_by_R_RS=True,planned_only=True))
    result=dict(schema='r_eligibility_mask_inputs_audit_v1',status=STATUS,protocol=cfg['_protocol'],folds=folds,totals=dict(totals),exposure_tables=tables,
        source_training_protocol=cfg['source_training_protocol'],selected_R_bank_root=cfg['selected_R_bank_root'],diagnosis_complete=cfg['diagnosis_complete'],
        source_pool_files_modified=False,labels_changed=False,window_selection_or_order_changed=False,normalizer_refit=False,synthetic_inputs_modified=False,
        resource_snapshot_before=before,resource_snapshot_after=resource.resource_snapshot(),
        unknown_loss_pairs=0,GT_coordinates_read=False,test_read=False,**{k:0 for k in ZERO})
    write(out/'audit.json',result);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    result=build(args.config) if args.execute else dict(status='readonly_r_eligibility_input_preflight',validated=bool(validate(args.config)))
    print(canonical(dict(status=result['status'])))
