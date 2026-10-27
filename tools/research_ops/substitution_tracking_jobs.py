"""七比赛独立追踪、TrackEval和事前断档登记；不修改冻结引擎或预测。"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import substitution_tracking_runtime as rt

def track(config,job_id,output):
    c,dep,cr,cc=rt.validate_config(config);_,old_rt,metric,training,train,numeric,base,old=dep
    job=next(j for j in c['tracking_matrix'] if j['job_id']==job_id);source=c['sources'][job['sequence']]
    output=training.storage().physical_child(output,rt.EXP);rt.require(not output.exists(),'追踪已有partial，不重放');output.mkdir(parents=True)
    import torch
    torch.set_num_threads(1)
    frames=rt.rows(rt.checked(source['cache']));rt.require(len(frames)==source['frames'],'完整共享缓存帧缺失')
    rt.require([f['frame_number'] for f in frames]==list(range(1,source['frames']+1)),'帧顺序/空检测帧被改变')
    model,adapter,binding,use_pose=rt.load_model(c,dep,cr,cc,job)
    cls,scope=old_rt.scoped_tracker(old['bundle'],c['sources'])
    tracker=cls(mode=job['mode'],model=model,normalizer=adapter,use_pose=use_pose,
        pose_source_sha256=train['pose_checkpoint_sha256'],fixed_detection_sha256=source['cache']['sha256'])
    text=[];counts=[]
    for frame in frames:
        tracks=tracker.update_frame(frame);counts.append(len(tracks))
        for row in tracks:
            x1,y1,x2,y2,identity,score=row[:6]
            text.append(','.join(map(str,[frame['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
    (output/'data').mkdir();mot=output/'data'/(job['sequence']+'.txt');mot.write_text('\n'.join(text)+('\n' if text else ''),encoding='utf-8')
    result=dict(schema='seven_match_ABC_free_tracking_v1',status='complete',protocol_sha256=rt.sha(config),job=job,
        frames=len(frames),tracked_rows=len(text),frame_counts=counts,mot_sha256=rt.sha(mot),cache=source['cache'],binding=binding,
        audit=tracker.audit,scope_adapter=scope,evaluation_GT_annotations_loaded=False,GT_used_for_tracking=False,GPU_used=False,test_read=False)
    (output/'receipt.json').write_text(rt.canonical(result)+'\n',encoding='utf-8');return {k:result[k] for k in ('status','job','frames','tracked_rows')}

def evaluate(config,tracking,output):
    c,dep,cr,cc=rt.validate_config(config);_,old_rt,metric,training,train,numeric,base,old=dep
    tracking=Path(tracking);receipt=rt.read(tracking/'receipt.json');job=receipt['job'];source=c['sources'][job['sequence']];seq=job['sequence']
    rt.require(receipt['schema']=='seven_match_ABC_free_tracking_v1' and receipt['status']=='complete'
        and receipt['protocol_sha256']==rt.sha(config) and job in c['tracking_matrix'] and receipt['cache']==source['cache']
        and receipt['evaluation_GT_annotations_loaded'] is False and receipt['GT_used_for_tracking'] is False,'追踪身份或GT边界不同')
    mot=tracking/'data'/(seq+'.txt');rt.require(rt.sha(mot)==receipt['mot_sha256'],'MOT被修改')
    predictions,count=metric.prediction_rows(mot.read_text(encoding='utf-8'),source['frames'])
    rt.require(count==receipt['tracked_rows'],'预测行数变化');gt_dict,gt=rt.load_gt(source)
    output=training.storage().physical_child(output,rt.EXP);rt.require(not output.exists(),'评价partial不覆盖');output.mkdir(parents=True)
    raw,numeric_sha=metric.trackeval_numeric(source,gt,tracking,output);summary={}
    for name,classes in raw.items():
        value=classes['pedestrian'];metric.validate_count(name,value['Count'],count,len(gt),seq,source['frames']);fraction={}
        for group,keys in [('HOTA',('HOTA','AssA','DetA')),('Identity',('IDF1',)),('CLEAR',('MOTA',))]:
            for key in keys:
                v=value[group][key];fraction[key]=sum(v)/len(v) if isinstance(v,list) else float(v)
        summary[name]=dict(metrics_fraction=fraction,metrics_percent={k:100*v for k,v in fraction.items()},IDSW_count=int(value['CLEAR']['IDSW']))
    registry=rt.read(rt.checked(c['registry']));rt.require(registry['sources']==c['sources'],'断档来源不同')
    selected=[e for e in registry['events'] if e['sequence']==seq];gap=rt.gap_numeric(dep)
    recovery=gap.evaluate_events(selected,registry['sequences'][seq]['endpoint_GT'],predictions)
    rt.require(recovery['overall']['total_events']==len(selected),'必须所有注册事件为分母')
    result=dict(schema='seven_match_ABC_trackeval_gap_v1',status='complete',protocol_sha256=rt.sha(config),job=job,
        frames=source['frames'],summary=summary,raw_results=raw,recovery=recovery,registry=c['registry'],GT_rows=len(gt),
        tracking_receipt_sha256=rt.sha(tracking/'receipt.json'),DO_PREPROC=False,predictions_GT_filtered=False,
        GT_ID0_original=True,GT_used_only_for_metric=True,numerical_source_sha256=numeric_sha,test_read=False)
    (output/'report.json').write_text(rt.canonical(result)+'\n',encoding='utf-8');return dict(status='complete',job=job,GT_rows=len(gt))

def register(config,output):
    """单独冻结的登记配置先于追踪准入；只读raw检测/评价GT，不读取任何追踪结果。"""
    c=rt.read(config);rt.require(c['schema']=='seven_match_gap_registration_config_v1' and c['approved_by']=='root'
        and c['registration_authorized'] is True and c['tracking_authorized'] is False and c['test_sealed'] is True
        and Path(c['bundle'])==rt.ROOT and rt.ROOT.parent==rt.R/'code','缺独立结果前断档登记准入')
    for e in rt.read(rt.checked(c['bundle_manifest']))['files']:rt.require(rt.sha(rt.ROOT/e['path'])==e['sha256'],'登记源码变化')
    dep=rt.dependencies(c['source_tracking_config']);training=dep[3];old_rt=dep[1];gap=rt.gap_numeric(dep)
    sources=rt.sources_from(rt.read(rt.checked(c['prediction_manifest'])),rt.read(rt.checked(c['matches'])))
    output=training.storage().physical_child(output,rt.EXP);rt.require(not output.exists(),'原注册已存在，不覆盖')
    events=[];registered={}
    for seq,s in sources.items():
        frames=rt.rows(rt.checked(s['cache']));rt.require(len(frames)==s['frames'],'帧不足')
        for f in frames:old_rt.validate_frame(f,sources)
        rt.require([f['frame_number'] for f in frames]==list(range(1,s['frames']+1)),'完整帧顺序改变')
        gt,_=rt.load_gt(s);selected,audit,endpoints=gap.build_events(seq,{f['frame_number']:f['detections'] for f in frames},gt)
        events.extend(selected);registered[seq]=dict(frames=s['frames'],audit=audit,endpoint_GT=endpoints,cache=s['cache'],
            GT_rows=sum(len(x) for x in gt.values()),GT_ID0_present=any(x['gt_id']=='0' for row in gt.values() for x in row))
    result=dict(schema='seven_match_trusted_detection_gap_registry_v1',status='complete7_gap_registry_before_tracking',
        registered_utc=datetime.now(timezone.utc).isoformat(),config=rt.ref(config),sources=sources,sequences=registered,events=events,event_count=len(events),
        original_numeric=rt.ref(gap.__file__),tracking_results_read=False,test_read=False,GPU_used=False,
        denominator='all registered events, including absent/ambiguous endpoints or changed identity failures',
        limitation='trusted detection gap proxy; may contain raw ambiguity; not physical occlusion')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:f.write(rt.canonical(result)+'\n')
    public=dict(schema='seven_match_gap_registration_receipt_without_GT_v1',status=result['status'],registry=rt.ref(output),sources=sources,
        event_count=len(events),sequence_event_counts={s:sum(e['sequence']==s for e in events) for s in sources},
        GT_row_counts={s:registered[s]['GT_rows'] for s in sources},GT_ID0_present={s:registered[s]['GT_ID0_present'] for s in sources},
        tracking_results_read=False,contains_GT_coordinates=False,test_read=False)
    with output.with_suffix('.receipt.json').open('x',encoding='utf-8') as f:f.write(rt.canonical(public)+'\n')
    return dict(status=result['status'],event_count=len(events),registry=public['registry'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--action',choices=('track','metric','register'),required=True)
    for k in ('config','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--job-id');p.add_argument('--tracking',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false')
    if not a.execute:result=dict(status='readonly_seven_match_job_candidate_no_execution',new_updates=0)
    elif a.action=='track':result=track(a.config,a.job_id,a.output)
    elif a.action=='metric':result=evaluate(a.config,a.tracking,a.output)
    else:result=register(a.config,a.output)
    print(rt.canonical(result))
