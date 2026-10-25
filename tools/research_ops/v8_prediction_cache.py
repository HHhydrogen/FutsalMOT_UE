"""v8共享冻结检测/Pose输入；独立三比赛与四合成机位注册，不扩展旧scope。"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time

RESEARCH=Path('D:/projects/FutsalMOT_Research')
SEQUENCES=('SNMOT-060','SNMOT-097','SNMOT-151')

def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bound(ref):
    path=Path(ref['path']);require(path.is_file() and sha(path)==ref['sha256'],'绑定改变:'+str(path));return path
def bind(path):return dict(path=str(path),sha256=sha(path))
def write(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)

def registered_sources(config):
    sources=[]
    require(config['domain_scope'] in ('real','synthetic'),'一次仅运行明确的来源域，GPU串行')
    if config['domain_scope']=='real':
        real=read(bound(config['real_manifest']));require(real['status']=='complete_2250_frames_three_matches' and [s['sequence_id'] for s in real['sequences']]==list(SEQUENCES),'真实源不完整')
        for source in real['sequences']:
            sources.append(dict(domain='real',sequence=source['sequence_id'],game='game'+source['game_id'],role='crossval_pool',fps=25,first_frame=0,last_frame=749,
                gt=source['GT'],gameinfo=source['gameinfo'],seqinfo=source['seqinfo'],width=1920,height=1080,frames=source['frames']))
        return sources
    data=Path(config['synthetic_root']);require(data==Path('G:/FutsalMOT_Dataset/v2_pose17_longpair_pilot_a01'),'只读既有独立成品')
    bound(config['synthetic_index'])
    variant=data/'groups/seed_00001048/variants/sport_blue_v1'
    for number in range(1,5):
        camera=f'CineCam_{number:02d}';directory=variant/'cameras'/camera
        sources.append(dict(domain='synthetic',sequence=f'S1048_blue_{camera}',game='synthetic1048',role='train',seed=1048,floor='sport_blue_v1',camera=camera,
            annotations=bind(directory/'pose2d.jsonl'),fps=10,first_frame=0,last_frame=299,width=3840,height=2160,
            frames=[dict(frame_index=i,frame_number=i+1,timestamp_sec=i/10,image_file=str(directory/'rgb'/f'{i:06d}.png')) for i in range(300)]))
    return sources

def pose_predictions(image,detections,frame,model,core):
    import cv2
    import numpy as np
    import torch
    from ultralytics.utils.nms import non_max_suppression
    from grf_ue_bridge.pose_location_dataset_v2 import letterbox_geometry
    predicted={d['detection_id']:[] for d in detections}
    for start in range(0,len(detections),16):
        chunk=detections[start:start+16];geometries=[];arrays=[]
        for detection in chunk:
            geometry=core.crop_geometry(detection['bbox_xywh_px'],(frame['width'],frame['height']));x,y,w,h=geometry['crop_xywh'];pad=letterbox_geometry(w,h,640)
            crop=cv2.resize(image[y:y+h,x:x+w],pad['resize_wh'],interpolation=cv2.INTER_LINEAR)
            crop=cv2.copyMakeBorder(crop,pad['top'],pad['bottom'],pad['left'],pad['right'],cv2.BORDER_CONSTANT,value=(114,114,114))
            arrays.append(np.ascontiguousarray(crop[:,:,::-1].transpose(2,0,1)));geometries.append(geometry)
        tensor=torch.from_numpy(np.stack(arrays)).to('cuda:0').float()/255.
        with torch.inference_mode():batch=non_max_suppression(model(tensor),conf_thres=.001,iou_thres=.7,classes=[0],agnostic=False,multi_label=False,max_det=100,nc=1,max_time_img=10.)
        require(len(batch)==len(chunk),'Pose batch不完整')
        for detection,geometry,rows in zip(chunk,geometries,batch):
            values=[core.inverse_prediction(row,geometry) for row in rows.detach().cpu().tolist()]
            predicted[detection['detection_id']]=[value for value in values if value is not None]
    # 仅调用已验纯数值选择/几何函数；不把新域冒称v6固定三序列schema。
    selected,reasons=core.select_unique(frame,predicted,core.configuration()['geometry_config'])
    records=[]
    for detection in detections:
        uid=detection['detection_id'];xy=[[0.,0.] for _ in range(17)];mask=[False]*17;reason=reasons.get(uid)
        if uid in selected:
            xy,mask,_,_=core.original.geometry_mask(selected[uid]['prediction']['xy_px'],detection['bbox_xywh_px'],(frame['width'],frame['height']),.25)
            if sum(mask[j] for j in range(5,17))<6:reason='too_few_geometry_valid_limbs';xy=[[0.,0.] for _ in range(17)];mask=[False]*17
        records.append(dict(uid=uid,detection_id=uid,bbox_xywh_px=detection['bbox_xywh_px'],score=detection['score'],class_id=0,xy_px=xy,geometry_valid=mask,
            prediction_valid=reason is None,image_wh=[frame['width'],frame['height']],timestamp_sec=frame['timestamp_sec'],physical_visibility='unknown',pose_rejection=reason))
    return records

def execute(config_path):
    config=read(config_path);bundle=Path(__file__).resolve().parents[2]
    require(bundle==Path(config['bundle']) and bundle.parent==RESEARCH/'code','仅独立D代码bundle')
    for entry in config['code_files']:require(sha(bundle/entry['path'])==entry['sha256'],'新cache代码变化')
    require(config['approved_by']=='root' and config['execution_authorized'],'未签共享预测准入')
    sources=registered_sources(config);out=Path(config['output']).resolve();require(RESEARCH/'pose/learned_association_v8' in out.parents and not out.exists(),'全新研究cache；保留partial')
    v6=bound(config['v6_protocol']);old_config=read(v6)
    sys.path.insert(0,str(Path(old_config['v6_bundle'])/'tools/research_ops'))
    from v6_crop_runtime import load,configure_runtime,model
    old,_,base,legacy,core=load(v6);legacy.training_complete(base.config,require_absent=True);configure_runtime()
    import cv2
    import numpy as np
    import torch
    import ultralytics
    from ultralytics import YOLO
    sys.path.insert(0,str(bundle/'tools/performance'))
    from ordered_prefetch import OrderedPrefetch
    require(torch.__version__=='2.6.0+cu124' and ultralytics.__version__=='8.4.60','仅已登记数值运行环境')
    torch.set_num_threads(4);cv2.setNumThreads(1);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
    require(torch.cuda.mem_get_info()[0]>=2*1024**3,'GPU余量不足，不启动')
    detector=YOLO(str(bound(config['detector_checkpoint'])))
    pose,identity=model(old,base,'pretrained');pose=pose.to('cuda:0').float().eval()
    reuse_raw={};reuse_pose={}
    with bound(config['reuse_raw']).open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['sequence_id']=='SNMOT-151':reuse_raw[row['frame_index']]=row
    with bound(config['reuse_pose']).open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['sequence_id']=='SNMOT-151':reuse_pose[row['frame_index']]=row
    require(len(reuse_raw)==len(reuse_pose)==150,'复用来源不是完整既有151前150')
    out.mkdir(parents=True);write(out/'started.json',dict(config_sha256=sha(config_path),status='started_not_complete',models_frozen=True,new_optimizer_updates=0))
    def loader(task):
        source,record=task
        if source['sequence']=='SNMOT-151' and record['frame_index']<150:return task,None
        path=Path(record['image_file']).resolve()
        require((RESEARCH in path.parents or Path('G:/FutsalMOT_Dataset') in path.parents) and not path.is_symlink(),'仅登记真实输入/合成成品')
        image=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
        require(image is not None and image.shape[:2]==(source['height'],source['width']),'源图解码/尺寸改变')
        return task,image
    complete=[]
    for source in sources:
        sequence=source['sequence'];counts=Counter();path=out/(sequence+'.partial.jsonl')
        tasks=[(source,row) for row in source['frames']]
        prefetch=OrderedPrefetch(loader,tasks,capacity=2,max_item_bytes=40*1024**2,measure_bytes=lambda item:0 if item[1] is None else int(item[1].nbytes))
        with path.open('x',encoding='utf-8') as stream,prefetch:
            for (_,record),image in prefetch:
                index=record['frame_index'];stamp=index/source['fps']
                frame=dict(schema='futsalmot_shared_prediction_frame_v8',sequence=sequence,sequence_id=sequence,game=source['game'],role=source['role'],domain=source['domain'],fps=source['fps'],
                    frame_index=index,frame_number=index+1,timestamp_sec=stamp,width=source['width'],height=source['height'],image_file=record['image_file'])
                if sequence=='SNMOT-151' and index<150:
                    previous=reuse_raw[index];attached=reuse_pose[index]
                    require(Path(previous['image_file']).resolve()==Path(record['image_file']).resolve(),'原151图对象变化，不复用')
                    require([d['detection_id'] for d in previous['detections']]==[d['detection_id'] for d in attached['attachments']],'原UID不一致')
                    detections=[dict(uid=d['detection_id'],detection_id=d['detection_id'],bbox_xywh_px=d['bbox_xywh_px'],score=d['fixed_detection_score'],class_id=0,xy_px=d['xy_px'],geometry_valid=d['geometry_valid'],
                        prediction_valid=d['prediction_valid'],image_wh=[source['width'],source['height']],timestamp_sec=stamp,physical_visibility='unknown',pose_rejection=d['prediction_rejection']) for d in attached['attachments']]
                    frame['prediction_origin']='reused_v6_actual_pretrained_raw_and_crop_no_reinference';counts['reused_frames']+=1
                else:
                    result=detector.predict(source=image,imgsz=640,conf=.1,iou=.7,classes=[0],max_det=300,agnostic_nms=False,augment=False,half=False,rect=True,batch=1,device='cuda:0',verbose=False)[0]
                    detections=[]
                    for row in result.boxes.data.detach().cpu().tolist():
                        x,y,r,b,score,category=map(float,row);x=max(0.,x);y=max(0.,y);r=min(float(frame['width']),r);b=min(float(frame['height']),b)
                        if r<=x or b<=y:counts['degenerate_model_boxes']+=1;continue
                        number=len(detections);uid=f'{sequence}:{index+1:06d}:{number:06d}'
                        detections.append(dict(detection_id=uid,source_index=number,bbox_xywh_px=[x,y,r-x,b-y],score=score,class_id=0))
                    frame['detections']=detections;detections=pose_predictions(image,detections,frame,pose,core)
                    frame['prediction_origin']='actual_frozen_yolo11n_and_coco_pretrained_cropPose';counts['new_inferred_frames']+=1
                frame['detections']=detections
                for detection in detections:
                    require(type(detection['prediction_valid']) is bool and len(detection['geometry_valid'])==17,'预测契约错误')
                    detection['model_sha256']=identity['sha256'];detection['detector_sha256']=config['detector_checkpoint']['sha256']
                    counts['geometry_valid' if detection['prediction_valid'] else 'bbox_only']+=1
                counts['frames']+=1;counts['raw_detections']+=len(detections)
                stream.write(json.dumps(frame,separators=(',',':'),allow_nan=False)+'\n')
                if counts['frames']%50==0:stream.flush();print(json.dumps(dict(sequence=sequence,frame=counts['frames'],raw_detections=counts['raw_detections'])),flush=True)
        target=out/(sequence+'.jsonl');path.rename(target)
        spec={key:value for key,value in source.items() if key!='frames'};spec['cache']=bind(target);spec['counts']=dict(counts);spec['prefetch']=prefetch.stats
        complete.append(spec);write(out/(sequence+'.complete.json'),spec)
    manifest=dict(schema='futsalmot_v8_shared_prediction_cache_manifest',status='complete_registered_sources_not_training_authorized',domain_scope=config['domain_scope'],sources=complete,detector=config['detector_checkpoint'],pose_checkpoint=identity,
        config_sha256=sha(config_path),reuse_sources=dict(raw=config['reuse_raw'],pose=config['reuse_pose']),GT_used_for_predictions=False,final116187_read=False,new_optimizer_updates=0,
        source_synthetic_flags_retained=dict(diagnostic_only=True,not_training=True,MRQ_sync_verified=False,visibility='unknown'),crop_files_written=False)
    write(out/'manifest.json',manifest);print(json.dumps(dict(status=manifest['status'],manifest=str(out/'manifest.json'))))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.execute:execute(args.config)
    else:print(json.dumps(dict(status='readonly_v8_prediction_plan',real_sources=3,synthetic_sources=4,new_training_updates=0)))
