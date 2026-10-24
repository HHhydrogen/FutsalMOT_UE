"""v5虚拟裁剪候选：仅读GDataset原图，在内存中crop；不写新图像。"""
import json
from pathlib import Path
import sys
PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'python/src'))
from grf_ue_bridge.pose_location_dataset_v2 import LocationPoseDataset,transform_location_instance,letterbox_geometry,_validate_instance
from grf_ue_bridge.pose_location_supervision_v2 import collate_location_contract

def location_record(pose,camera_root,crop,key):
    """按同一整数crop变换bbox/xy/valid；不改变源可见性unknown。"""
    left,top,width,height=crop;instances=[]
    for obj in pose['objects']:
        raw=dict(annotation_id=key+':'+obj['entity_id'],entity_id=obj['entity_id'],source='synthetic',
            bbox_xywh_px=obj['bbox_visible_xywh'],xy_normalized=[([p[0]/3840,p[1]/2160] if p is not None and ok else [0.,0.]) for p,ok in zip(obj['uv_px'],obj['location_valid'])],
            location_valid=list(obj['location_valid']),visibility_state=list(obj['visibility_state']),source_coco_v=None,
            detection_target_retained=True,pose_labelled_count=sum(obj['location_valid']))
        transformed=transform_location_instance(raw,(3840,2160),[[1.,0.,-left],[0.,1.,-top],[0.,0.,1.]],(width,height))
        if transformed is not None:
            _validate_instance(transformed,width,height);instances.append(transformed)
    record=dict(schema='separated_pose_location_frame_v1',frame_key=key,image_file=str(Path(camera_root)/pose['rgb_ref']),image_sha256=None,
        width=width,height=height,source_wh=[3840,2160],virtual_crop_xywh=crop,source_frame_index=pose['source_frame_index'],
        bbox_coverage='all_noncrowd_person_instances',crowd_present=False,instances=instances,
        expected_person_annotation_ids=[i['annotation_id'] for i in instances],diagnostic_only=True,not_training=True,
        training_authorized=False,MRQ_sync_verified=False,visibility_upgrade_performed=False)
    collate_location_contract([record]);return record

class VirtualCropDataset:
    """候选Dataset：保持既有640 LetterBox/位置打包数值；尚需root实际CPU backward准入。"""
    rect=False;mosaic=False
    collate_fn=staticmethod(LocationPoseDataset.collate_fn)
    def __init__(self,jsonl_path,imgsz=640):
        import numpy as np
        self.path=Path(jsonl_path).resolve();self.imgsz=imgsz;self.records=[];self.labels=[];self.im_files=[]
        root=Path('G:/FutsalMOT_Dataset').resolve()
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            frame=json.loads(line);image=Path(frame['image_file']).resolve()
            if root not in image.parents:raise ValueError('虚拟crop媒体必须实际GDataset')
            left,top,width,height=frame['virtual_crop_xywh']
            if frame['source_wh']!=[3840,2160] or min(left,top)<0 or min(width,height)<=0 or left+width>3840 or top+height>2160:raise ValueError('crop越界')
            collate_location_contract([frame])
            for obj in frame['instances']:_validate_instance(obj,width,height)
            self.records.append(frame);self.im_files.append(str(image))
            boxes=[]
            for obj in frame['instances']:
                x,y,w,h=obj['bbox_xywh_px'];boxes.append([(x+w/2)/width,(y+h/2)/height,w/width,h/height])
            self.labels.append(dict(cls=np.zeros((len(boxes),1),dtype=np.float32),bboxes=np.array(boxes,dtype=np.float32).reshape(-1,4)))
        if not self.records:raise ValueError('虚拟crop记录为空')
    def __len__(self):return len(self.records)
    def __getitem__(self,index):
        import cv2
        import numpy as np
        import torch
        frame=self.records[index];image=cv2.imread(self.im_files[index],cv2.IMREAD_COLOR)
        if image is None or list(image.shape[1::-1])!=frame['source_wh']:raise ValueError('源RGB尺寸不同')
        left,top,width,height=frame['virtual_crop_xywh'];image=image[top:top+height,left:left+width]
        geometry=letterbox_geometry(width,height,self.imgsz)
        if (width,height)!=tuple(geometry['resize_wh']):image=cv2.resize(image,geometry['resize_wh'],interpolation=cv2.INTER_LINEAR)
        image=cv2.copyMakeBorder(image,geometry['top'],geometry['bottom'],geometry['left'],geometry['right'],cv2.BORDER_CONSTANT,value=(114,114,114))
        instances=[transform_location_instance(i,(width,height),geometry['matrix'],geometry['output_wh']) for i in frame['instances']]
        if any(i is None for i in instances):raise AssertionError('LetterBox不可移除crop内bbox')
        packed=collate_location_contract([{**frame,'width':self.imgsz,'height':self.imgsz,'instances':instances}]);count=len(instances)
        return dict(img=torch.from_numpy(np.ascontiguousarray(image[:,:,::-1].transpose(2,0,1))),
            keypoints=torch.tensor(packed['keypoints'],dtype=torch.float32).reshape(count,17,2),location_valid=torch.tensor(packed['location_valid'],dtype=torch.bool).reshape(count,17),
            bboxes=torch.tensor(packed['bboxes'],dtype=torch.float32).reshape(count,4),cls=torch.zeros((count,1),dtype=torch.float32),batch_idx=torch.zeros(count,dtype=torch.int64),
            visibility_state=packed['visibility_state'],target_ids=packed['target_ids'],sources=[i['source'] for i in instances],im_file=self.im_files[index],
            ori_shape=(height,width),resized_shape=(self.imgsz,self.imgsz),ratio_pad=((geometry['ratio'],geometry['ratio']),(geometry['left'],geometry['top'])))
