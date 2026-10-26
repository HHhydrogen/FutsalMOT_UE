"""v10独立last1000/纯R/PT的CPU自由追踪，不读取GT或筛选预测。"""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import v10_tracking_runtime as rt


def execute(config,job_id,output):
    cfg,runtime,train,numeric,base,old=rt.validate_config(config)
    job=next(j for j in cfg['tracking_matrix'] if j['job_id']==job_id);source=cfg['sources'][job['sequence']]
    output=runtime.storage().physical_child(output,rt.V)
    rt.require(not output.exists(),'全新追踪输出，partial不重放');output.mkdir(parents=True)
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',YOLO_AUTOINSTALL='false',YOLO_CONFIG_DIR=str(rt.V/'_runtime/ultralytics'))
    import torch
    torch.set_num_threads(1)
    frames=rt.rows(rt.checked(source['cache']));rt.require(len(frames)==source['frames'],'完整帧缓存不足')
    model,adapter,binding,use_pose=rt.model_for_job(cfg,runtime,train,numeric,base,old,job)
    cls,scope=rt.scoped_tracker(old['bundle'],cfg['sources'])
    tracker=cls(mode=job['mode'],model=model,normalizer=adapter,use_pose=use_pose,
        pose_source_sha256=train['pose_checkpoint_sha256'],fixed_detection_sha256=source['cache']['sha256'])
    text=[];counts=[]
    for frame in frames:
        tracks=tracker.update_frame(frame);counts.append(len(tracks))
        for row in tracks:
            x1,y1,x2,y2,identity,score=row[:6]
            text.append(','.join(map(str,[frame['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
    (output/'data').mkdir();mot=output/'data'/(job['sequence']+'.txt');mot.write_text('\n'.join(text)+('\n' if text else ''),encoding='utf-8')
    value=dict(schema='v10_independent_free_tracking_v1',status='complete',protocol_sha256=rt.sha(config),job=job,
        sequence=job['sequence'],frames=len(frames),tracked_rows=len(text),frame_counts=counts,mot_sha256=rt.sha(mot),
        cache=source['cache'],binding=binding,audit=tracker.audit,scope_adapter=scope,GT_read=False,GPU_used=False,test_read=False)
    (output/'receipt.json').write_text(rt.canonical(value)+'\n',encoding='utf-8');return value


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--job-id',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(rt.canonical(execute(a.config,a.job_id,a.output) if a.execute else dict(status='readonly_v10_tracking_candidate',GT_read=False)))
