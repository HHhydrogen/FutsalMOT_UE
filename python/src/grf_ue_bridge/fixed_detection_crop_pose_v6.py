"""v6原始检测框内存crop Pose：独立来源、守恒UID、保守一对一和歧义回退。"""
from copy import deepcopy
import math
from . import fixed_detection_pose_attach_v2 as original
from .pose_location_dataset_v2 import letterbox_geometry

VERSION='futsalmot_fixed_detection_crop_pose_record_v6'
FRAME_SCHEMA='futsalmot_fixed_detection_crop_pose_frame_v6'
STRATEGY='raw_detection_bbox_margin_crop_letterbox_640_v6'

def configuration():
    quality=original.candidate_configuration();quality['quality_gate_status']='root_frozen_before_any_association_result_a01'
    return dict(schema='futsalmot_fixed_detection_crop_pose_configuration_v6',strategy=STRATEGY,
        crop_margin_fraction=.25,imgsz=640,batch_size=16,dtype='float32',
        geometry_config=quality,duplicate_joint_sigma=.1,
        target_selection='max_original_bbox_iou_then_min_normalized_center_distance_then_max_model_score_exact_rank_tie_fallback',
        deduplication='bbox_related_then_original_sigma_joint_similarity; ambiguous_ownership_or_joint_evidence_fallback',
        assignment='one_target_per_crop_then_crosscrop_component_unique_owner_else_bbox_fallback',
        physical_visibility='unknown',threshold_search=False)

def validate_configuration(config):
    original.require(config==configuration(),'v6参数候选不得暗改模型、阈值、批量或crop规则')

def crop_geometry(box,image_wh):
    width,height=image_wh;x,y,w,h=box
    original.require(original.finite(box,4) and min(w,h)>0 and 0<=x<x+w<=width and 0<=y<y+h<=height,'原检测框无效')
    left=max(0,math.floor(x-.25*w));top=max(0,math.floor(y-.25*h));right=min(width,math.ceil(x+1.25*w));bottom=min(height,math.ceil(y+1.25*h))
    geometry=letterbox_geometry(right-left,bottom-top,640);r=geometry['ratio'];padx=geometry['left'];pady=geometry['top']
    return dict(strategy=STRATEGY,crop_xywh=[left,top,right-left,bottom-top],input_wh=[640,640],scale=r,left=padx,top=pady,
        original_to_input_matrix=[[r,0.,padx-left*r],[0.,r,pady-top*r],[0.,0.,1.]],
        input_to_original_matrix=[[1/r,0.,left-padx/r],[0.,1/r,top-pady/r],[0.,0.,1.]])

def inverse_prediction(row,geometry):
    """普通Pose NMS行xyxy/score/class/17xy；点不裁剪，框裁到实际crop。"""
    original.require(len(row)==40 and row[5]==0,'必须单类17xy普通Pose输出')
    left,top,width,height=geometry['crop_xywh'];r=geometry['scale'];px=geometry['left'];py=geometry['top']
    if not original.finite(row[:4],4):return None
    x1=max(0.,min(float(width),(row[0]-px)/r));x2=max(0.,min(float(width),(row[2]-px)/r))
    y1=max(0.,min(float(height),(row[1]-py)/r));y2=max(0.,min(float(height),(row[3]-py)/r))
    if x2<=x1 or y2<=y1:return None
    return dict(bbox_xywh_px=[x1+left,y1+top,x2-x1,y2-y1],score=float(row[4]),
        xy_px=[[(row[6+2*j]-px)/r+left,(row[7+2*j]-py)/r+top] for j in range(17)])

def _same_candidate(a,b,quality):
    if original.bbox_iou(a,b)>=quality['pose_nms_iou']:return True
    ax,ay,aw,ah=a;bx,by,bw,bh=b;ac=(ax+aw/2,ay+ah/2);bc=(bx+bw/2,by+bh/2)
    return ax<=bc[0]<=ax+aw and ay<=bc[1]<=ay+ah and bx<=ac[0]<=bx+bw and by<=ac[1]<=by+bh

def select_unique(frame,predictions_by_uid,quality):
    """先每crop最多选一目标；再对最多rawUID数候选做bbox+joint一致性去重。"""
    nodes=[];reasons={};boxes={d['detection_id']:d['bbox_xywh_px'] for d in frame['detections']}
    for det in frame['detections']:
        uid=det['detection_id'];x,y,w,h=det['bbox_xywh_px'];center=(x+w/2,y+h/2);candidates=[]
        for index,pred in enumerate(predictions_by_uid[uid]):
            if not original.finite(pred.get('bbox_xywh_px'),4) or min(pred['bbox_xywh_px'][2:])<=0:continue
            original.require(len(pred.get('xy_px',[]))==17 and original.finite([pred.get('score')],1),'模型xy/score格式错误')
            overlap=original.bbox_iou(det['bbox_xywh_px'],pred['bbox_xywh_px'])
            if overlap<quality['min_matched_iou']:continue
            px,py,pw,ph=pred['bbox_xywh_px'];distance=((px+pw/2-center[0])/w)**2+((py+ph/2-center[1])/h)**2
            candidates.append(((-overlap,distance,-pred['score']),index,pred))
        if not candidates:reasons[uid]='no_crop_model_bbox_match';continue
        candidates.sort(key=lambda value:(value[0],value[1]))
        if len(candidates)>1 and candidates[0][0]==candidates[1][0]:reasons[uid]='own_crop_equal_rank_ambiguity';continue
        rank,index,pred=candidates[0]
        _,valid,_,_=original.geometry_mask(pred['xy_px'],det['bbox_xywh_px'],(frame['width'],frame['height']),quality['bbox_margin_fraction'])
        nodes.append(dict(owner=uid,prediction_index=index,prediction=pred,overlap=-rank[0],valid=valid))
    parents=list(range(len(nodes)));ambiguous=set()
    def find(index):
        while parents[index]!=index:parents[index]=parents[parents[index]];index=parents[index]
        return index
    for i,node in enumerate(nodes):
        for j in range(i):
            other=nodes[j]
            if not _same_candidate(node['prediction']['bbox_xywh_px'],other['prediction']['bbox_xywh_px'],quality):continue
            common=[k for k in original.LIMBS if node['valid'][k] and other['valid'][k]]
            if len(common)<quality['minimum_geometry_limb_joints']:ambiguous.update((i,j));continue
            a=node['prediction']['bbox_xywh_px'];b=other['prediction']['bbox_xywh_px'];area=(a[2]*a[3]+b[2]*b[3])/2
            similarity=sum(math.exp(-math.dist(node['prediction']['xy_px'][k],other['prediction']['xy_px'][k])**2/(2*(2*.1)**2*area)) for k in common)/len(common)
            if similarity>=quality['pose_nms_iou']:parents[find(i)]=find(j)
            else:ambiguous.update((i,j))
    components={}
    for i in range(len(nodes)):components.setdefault(find(i),[]).append(i)
    selected={}
    for i,node in enumerate(nodes):
        uid=node['owner'];component=components[find(i)]
        if i in ambiguous:reasons[uid]='cross_crop_joint_evidence_ambiguous';continue
        if len(component)!=1:reasons[uid]='cross_crop_same_person_component_ambiguous';continue
        selected[uid]=dict(prediction=node['prediction'],prediction_index=node['prediction_index'],matched_bbox_iou=node['overlap'],component=[uid,node['prediction_index']])
    return selected,reasons

def attach_frame(frame,predictions_by_uid,*,model_sha256,fixed_detection_set_sha256,config):
    validate_configuration(config);original.validate_fixed_frame(frame)
    original.require(original.is_sha(model_sha256) and original.is_sha(fixed_detection_set_sha256),'缺真实模型/固定raw SHA')
    uids=[det['detection_id'] for det in frame['detections']]
    original.require(set(predictions_by_uid)==set(uids),'每个原始UID必须恰有一次crop结果，空输出也需保留')
    quality=config['geometry_config'];selected,reasons=select_unique(frame,predictions_by_uid,quality);result=[]
    for det in frame['detections']:
        uid=det['detection_id'];geometry=crop_geometry(det['bbox_xywh_px'],(frame['width'],frame['height']));match=selected.get(uid)
        xy=[[0.,0.] for _ in range(17)];valid=[False]*17;raw=[None]*17;point_reasons=['no_crop_model_bbox_match']*17;before=list(valid)
        rejection=reasons.get(uid);pred=None;overlap=None;index=None;component=None
        if match is not None:
            pred=match['prediction'];overlap=match['matched_bbox_iou'];index=match['prediction_index'];component=match['component']
            xy,valid,point_reasons,raw=original.geometry_mask(pred['xy_px'],det['bbox_xywh_px'],(frame['width'],frame['height']),quality['bbox_margin_fraction']);before=list(valid)
            limbs=[xy[j] for j in original.LIMBS if valid[j]];spread=max((math.dist(a,b) for a in limbs for b in limbs),default=0.)
            rejection=('too_few_geometry_valid_limbs' if len(limbs)<quality['minimum_geometry_limb_joints'] else
                'bbox_too_small_at_model_input' if det['bbox_xywh_px'][3]*geometry['scale']<quality['minimum_bbox_height_input_px'] else
                'degenerate_limb_spread' if spread<quality['minimum_limb_spread_bbox_diagonal_fraction']*math.hypot(*det['bbox_xywh_px'][2:]) else None)
            if rejection is not None:xy=[[0.,0.] for _ in range(17)];valid=[False]*17
        row=dict(schema=VERSION,detection_id=uid,source_index=det['source_index'],class_id=det['class_id'],bbox_xywh_px=deepcopy(det['bbox_xywh_px']),fixed_detection_score=det['score'],
            **{key:frame[key] for key in ('sequence_id','camera_id','frame_key','frame_index','frame_number')},image_wh=[frame['width'],frame['height']],
            source='model_prediction_xy',coordinate_space='image_pixels',validity_method='finite_bbox_relative_geometry',model_sha256=model_sha256,fixed_detection_set_sha256=fixed_detection_set_sha256,
            xy_px=xy,geometry_valid=valid,prediction_valid=rejection is None,prediction_rejection=rejection,raw_prediction_xy_px=raw,
            geometry_mask_before_global_gate=before,point_geometry_rejection=point_reasons,model_prediction_index=index,model_prediction_bbox_xywh_px=deepcopy(pred['bbox_xywh_px']) if pred else None,
            model_person_score=pred['score'] if pred else None,matched_bbox_iou=overlap,candidate_component=component,physical_visibility='unknown',visibility_state=['unknown']*17,joint_confidence=None,
            transform=dict(geometry,crop_source_detection_id=uid))
        result.append(row)
    return dict(schema=FRAME_SCHEMA,strategy=STRATEGY,**{key:frame[key] for key in ('sequence_id','camera_id','frame_key','frame_index','frame_number')},
        fixed_detection_count=len(uids),crop_attempts=len(uids),attachments=result,physical_visibility='unknown',GT_used=False)

def validate_frame(frame,attached,*,model_sha256,fixed_detection_set_sha256,config):
    validate_configuration(config);original.validate_fixed_frame(frame)
    original.require(attached.get('schema')==FRAME_SCHEMA and attached.get('strategy')==STRATEGY and len(attached['attachments'])==attached['crop_attempts']==len(frame['detections']),'crop来源或UID数量不符')
    claimed=[]
    for det,row in zip(frame['detections'],attached['attachments']):
        original.require(row.get('schema')==VERSION and row.get('transform')==dict(crop_geometry(det['bbox_xywh_px'],(frame['width'],frame['height'])),crop_source_detection_id=det['detection_id']),'不得把crop来源改称full_frame')
        for key in ('detection_id','source_index','class_id','bbox_xywh_px'):original.require(row[key]==det[key],'改变原始raw ID/box/class')
        original.require(row['fixed_detection_score']==det['score'] and row['model_sha256']==model_sha256 and row['fixed_detection_set_sha256']==fixed_detection_set_sha256,'score或SHA改变')
        original.require(row['visibility_state']==['unknown']*17 and row['physical_visibility']=='unknown' and row['joint_confidence'] is None,'不可伪造可见性')
        original.require(type(row['prediction_valid']) is bool,'prediction_valid必须bool')
        for key in ('sequence_id','camera_id','frame_key','frame_index','frame_number'):original.require(row[key]==frame[key],'crop帧身份改变')
        _,recomputed,_,_=original.geometry_mask(row['xy_px'],det['bbox_xywh_px'],(frame['width'],frame['height']),config['geometry_config']['bbox_margin_fraction'])
        original.require(all(not ok or recomputed[j] for j,ok in enumerate(row['geometry_valid'])),'true点不满足原几何规则')
        from .pose_association_contract_v2 import _validate
        _validate(row)
        original.require(all(ok or point==[0.,0.] for point,ok in zip(row['xy_px'],row['geometry_valid'])),'false点必须零占位')
        if row['prediction_valid']:
            original.require(sum(row['geometry_valid'][j] for j in original.LIMBS)>=config['geometry_config']['minimum_geometry_limb_joints'] and row['candidate_component'] is not None,'不得把全部crop假称几何有效')
            original.require(original.finite(row['model_prediction_bbox_xywh_px'],4) and row['matched_bbox_iou']==original.bbox_iou(det['bbox_xywh_px'],row['model_prediction_bbox_xywh_px']) and row['matched_bbox_iou']>=config['geometry_config']['min_matched_iou'],'模型框IoU证据不符')
            claimed.append(tuple(row['candidate_component']))
        else:original.require(not any(row['geometry_valid']),'fallback不得带有效点')
    original.require(len(claimed)==len(set(claimed)),'同一跨crop候选组件重复分配')

def tracker_records(frame,attached,*,model_sha256,fixed_detection_set_sha256,config):
    """明确协议桥：原tracker消费同像素/几何字段；保持v6 schema/transform不改名。"""
    validate_frame(frame,attached,model_sha256=model_sha256,fixed_detection_set_sha256=fixed_detection_set_sha256,config=config)
    return {row['detection_id']:row for row in attached['attachments']}

def infer_frame(image,frame,model,device,config):
    """每个raw UID独立一次crop输入；每批至多16，无图像写出，无AMP。"""
    validate_configuration(config);original.validate_fixed_frame(frame)
    import cv2
    import numpy as np
    import torch
    from ultralytics.utils.nms import non_max_suppression
    original.require(device=='cuda:0' and image.shape[:2]==(frame['height'],frame['width']),'仅root已测CUDA FP32入口')
    predictions={det['detection_id']:[] for det in frame['detections']};quality=config['geometry_config']
    for start in range(0,len(frame['detections']),16):
        selected=frame['detections'][start:start+16];arrays=[];geometries=[]
        for det in selected:
            geometry=crop_geometry(det['bbox_xywh_px'],(frame['width'],frame['height']));left,top,width,height=geometry['crop_xywh'];crop=image[top:top+height,left:left+width]
            box=letterbox_geometry(width,height,640);resized=cv2.resize(crop,box['resize_wh'],interpolation=cv2.INTER_LINEAR)
            padded=cv2.copyMakeBorder(resized,box['top'],box['bottom'],box['left'],box['right'],cv2.BORDER_CONSTANT,value=(114,114,114))
            arrays.append(np.ascontiguousarray(padded[:,:,::-1].transpose(2,0,1)));geometries.append(geometry)
        tensor=torch.from_numpy(np.stack(arrays)).to(device).float()/255.
        with torch.inference_mode():
            raw=model(tensor);batch=non_max_suppression(raw,conf_thres=quality['pose_confidence_threshold'],iou_thres=quality['pose_nms_iou'],classes=[0],agnostic=False,multi_label=False,max_det=quality['max_pose_detections'],nc=1,max_time_img=10.)
        original.require(len(batch)==len(selected),'模型没有为每个crop返回结果')
        for det,geometry,rows in zip(selected,geometries,batch):
            mapped=[inverse_prediction(row,geometry) for row in rows.detach().cpu().tolist()]
            predictions[det['detection_id']]=[prediction for prediction in mapped if prediction is not None]
    return predictions
