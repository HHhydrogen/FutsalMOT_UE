"""同强motion状态的无GT影子评分，以及独立身份的固定权重自由消融。"""
import argparse
from copy import deepcopy
import gzip
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import pose_mechanism_core as core


def numeric_context(config,job_id):
    cfg,rt,old,runtime,train,numeric,base,numbers=core.validate(config)
    job=next(j for j in cfg['jobs'] if j['job_id']==job_id);original=job['original'];source=old['sources'][original['sequence']]
    inputs=core.read(core.checked(cfg['inputs']))['sources'][original['sequence']]
    frames=core.rows(core.checked(source['cache']));bank=core.read(core.checked(inputs['bank']))
    index={d['uid']:d for f in frames for d in f['detections']}
    cls,scope=rt.scoped_tracker(numbers['bundle'],old['sources'])
    model,adapter,binding,_=rt.model_for_job(old,runtime,train,numeric,base,numbers,original)
    return cfg,rt,old,runtime,train,numeric,base,numbers,job,source,frames,bank,index,cls,scope,model,adapter,binding


def instrumented(cls,stream,models,bank,index):
    """成本函数额外读取已证为纯函数；原get_dists返回值原样返回。"""
    import torch
    import numpy as np
    from ultralytics.trackers.byte_tracker import BYTETracker
    from grf_ue_bridge.learned_association_features_v8 import features,candidate_gate
    from grf_ue_bridge.pose_quality_features_v9 import quality
    mask=cls.get_dists.__globals__['intervention_mask']
    class Observed(cls):
        def update_frame(self,frame):
            self.trace_buffer=[];result=super().update_frame(frame)
            chosen={t.track_id:t.record['uid'] for t in self.tracked_stracks if t.is_activated and t.record is not None
                    and t.record.get('_frame_index')==frame['frame_index']}
            for event in self.trace_buffer:
                event['chosen_raw_UID']=[chosen.get(i) for i in event['track_ids']]
                stream.write(core.canonical(event)+'\n')
            return result
        def get_dists(self,tracks,detections):
            stage=self._stage;base=BYTETracker.get_dists(self,tracks,detections)
            result=super().get_dists(tracks,detections)
            if not base.size:return result
            histories=[list(t.history) for t in tracks];records=[t.record for t in detections]
            gates=np.array([[candidate_gate(h,d)['accepted'] if h else False for d in records] for h in histories],dtype=bool)
            lost=[t.state!=1 or self.frame_id-t.frame_id>1 for t in tracks];enough=[len(h)==3 for h in histories]
            enabled,active,_=mask(base,gates,lost,enough,stage);locations=[];raws=[];shuffled=[]
            for i,h in enumerate(histories):
                if not enough[i]:continue
                for j,d in enumerate(records):
                    if gates[i,j]:
                        locations.append((i,j));raws.append(features(h,d))
                        shuffled.append(features([core.transform(x,bank,index) for x in h],core.transform(d,bank,index)))
            scored={};quality_gates={}
            if locations:
                for name,(model,adapter,use_pose) in models.items():
                    values=shuffled if name=='shape_shuffle' else raws
                    x=torch.tensor([adapter.transform(r,use_pose=use_pose) for r in values],dtype=torch.float32)
                    with torch.no_grad():logits=model(x).reshape(-1).cpu().tolist()
                    scored[name]=logits
                    if name in ('pose','shape_shuffle'):quality_gates[name]=x[:,-1].tolist()
            event=dict(frame_number=self.frame_id,stage=stage,track_ids=[int(t.track_id) for t in tracks],
                history_UIDs=[[d['uid'] for d in h] for h in histories],candidate_UIDs=[d['uid'] for d in records],
                bbox_cost=base.tolist(),reference_cost=result.tolist(),motion_gate=gates.tolist(),enabled=enabled.tolist(),
                active_rows=active,enough_history=enough,lost_gap=lost,scored_locations=locations,logits=scored,
                quality=[quality(r) for r in raws],quality_gates=quality_gates,GT_read=False)
            self.trace_buffer.append(event);return result
    return Observed


def run(config,job_id,output):
    context=numeric_context(config,job_id)
    cfg,rt,old,runtime,train,numeric,base,numbers,job,source,frames,bank,index,cls,scope,model,adapter,binding=context
    import torch
    torch.set_num_threads(1)
    output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'新诊断输出，partial不覆盖');output.mkdir(parents=True)
    kwargs=dict(mode='learned',pose_source_sha256=train['pose_checkpoint_sha256'],fixed_detection_sha256=source['cache']['sha256'])
    stream=None
    if job['kind']=='common_state':
        motion,normalizer,motion_binding,_=rt.model_for_job(old,runtime,train,numeric,base,numbers,job['reference_motion'])
        capacity_job=next(j for j in old['tracking_matrix'] if j['kind']=='new_RS' and j.get('method')=='motion_residual'
            and all(j.get(k)==job['original'][k] for k in ('pool','fold','seed','sequence')))
        capacity,capacity_adapter,_,_=rt.model_for_job(old,runtime,train,numeric,base,numbers,capacity_job)
        stream=gzip.open(output/'common_state_trace.jsonl.gz','xt',encoding='utf-8')
        models=dict(motion=(motion,normalizer,False),motion_residual=(capacity,capacity_adapter,True),
            pose=(model,adapter,True),pose_off=(core.off_model(model),adapter,True),shape_shuffle=(model,adapter,True))
        actual_cls=instrumented(cls,stream,models,bank,index)
        tracker=actual_cls(model=motion,normalizer=normalizer,use_pose=False,**kwargs)
    else:
        actual_model=core.off_model(model) if job['condition']=='pose_off' else model
        tracker=cls(model=actual_model,normalizer=adapter,use_pose=True,**kwargs)
    text=[]
    try:
        for frame in frames:
            current=frame
            if job['kind']=='free' and job['condition']=='shape_shuffle':
                current=deepcopy(frame);current['detections']=[core.transform(d,bank,index) for d in frame['detections']]
            for row in tracker.update_frame(current):
                x1,y1,x2,y2,identity,score=row[:6]
                text.append(','.join(map(str,[frame['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
    finally:
        if stream is not None:stream.close()
    (output/'data').mkdir();mot=output/'data'/(source['sequence']+'.txt');mot.write_text('\n'.join(text)+('\n' if text else ''),encoding='utf-8')
    if job['kind']=='common_state':
        original=Path(old['training_control']).parent/'tracking_control_a01/runs'/job['reference_motion']['job_id']/'tracking'
        receipt=core.read(original/'receipt.json')
        core.require(core.sha(mot)==receipt['mot_sha256'] and tracker.audit==receipt['audit'],'新增记录改变了真实motion参考轨迹或audit')
    value=dict(schema='pose_mechanism_fixed_model_tracking_v1',status='complete',protocol_sha256=core.sha(config),job=job,
        sequence=source['sequence'],frames=len(frames),tracked_rows=len(text),mot_sha256=core.sha(mot),
        trace=core.ref(output/'common_state_trace.jsonl.gz') if job['kind']=='common_state' else None,
        bank=core.read(core.checked(cfg['inputs']))['sources'][source['sequence']]['bank'],binding=binding,
        numerical_scope=scope,audit=tracker.audit,GT_read=False,GPU_used=False,new_optimizer_updates=0,test_read=False)
    with (output/'receipt.json').open('x',encoding='utf-8') as f:f.write(core.canonical(value)+'\n')
    return dict(status='complete',kind=job['kind'],job_id=job_id,rows=len(text),reference_exact=job['kind']=='common_state')


def metric(config,tracking,output):
    cfg,rt,old,runtime,train,numeric,base,numbers=core.validate(config);tracking=Path(tracking);receipt=core.read(tracking/'receipt.json');job=receipt['job']
    core.require(receipt['schema']=='pose_mechanism_fixed_model_tracking_v1' and receipt['status']=='complete' and job['kind']=='free'
        and receipt['protocol_sha256']==core.sha(config) and receipt['GT_read'] is False,'独立干预追踪身份缺失')
    numeric_metric=rt.load_file('mechanism_frozen_metric',Path(old['bundle'])/'tools/research_ops/v10_metric.py')
    source=old['sources'][receipt['sequence']];mot=tracking/'data'/(source['sequence']+'.txt')
    core.require(core.sha(mot)==receipt['mot_sha256'],'干预MOT改变');predictions,count=numeric_metric.prediction_rows(mot.read_text(encoding='utf-8'),source['frames'])
    core.require(count==receipt['tracked_rows'],'不得按GT筛预测')
    _,gt=rt.load_gt(source);output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'评价partial不覆盖');output.mkdir(parents=True)
    raw,sources=numeric_metric.trackeval_numeric(source,gt,tracking,output);summary={}
    for name,classes in raw.items():
        value=classes['pedestrian'];numeric_metric.validate_count(name,value['Count'],count,len(gt),source['sequence'],source['frames']);metrics={}
        for group,keys in [('HOTA',('HOTA','AssA','DetA')),('Identity',('IDF1',)),('CLEAR',('MOTA',))]:
            for k in keys:
                x=value[group][k];metrics[k]=100*(sum(x)/len(x) if isinstance(x,list) else float(x))
        summary[name]=dict(metrics_percent=metrics,IDSW_count=int(value['CLEAR']['IDSW']))
    registry=core.read(core.checked(old['registry']));gap=numeric_metric.gap_numeric(numbers)
    selected=[e for e in registry['events'] if e['sequence']==source['sequence']]
    recovery=gap.evaluate_events(selected,registry['sequences'][source['sequence']]['endpoint_GT'],predictions)
    result=dict(schema='pose_mechanism_counterfactual_metric_v1',status='complete',job=job,protocol_sha256=core.sha(config),
        tracking_receipt=core.ref(tracking/'receipt.json'),summary=summary,recovery=recovery,raw_results=raw,
        numerical_sources=sources,GT_used_only_for_metric=True,predictions_GT_filtered=False,test_read=False,new_updates=0)
    with (output/'report.json').open('x',encoding='utf-8') as f:f.write(core.canonical(result)+'\n')
    return dict(status='complete',job_id=job['job_id'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--job-id');p.add_argument('--tracking',type=Path);p.add_argument('--mode',choices=('track','metric'),required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',PYTHONUTF8='0',PYTHONIOENCODING='utf-8')
    print(core.canonical((run(a.config,a.job_id,a.output) if a.mode=='track' else metric(a.config,a.tracking,a.output)) if a.execute else dict(status='readonly_pose_mechanism_candidate')))
