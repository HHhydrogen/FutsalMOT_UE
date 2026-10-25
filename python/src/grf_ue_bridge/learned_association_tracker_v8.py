"""v8独立750帧train域Tracker：可学习困难候选/断档恢复，不改旧scope或低分stage。"""
from collections import deque
from copy import deepcopy
from types import SimpleNamespace
import math
import re
import numpy as np
from .learned_association_features_v8 import features,candidate_gate
from .learned_association_model_v8 import probability_to_cost
from .pose_association_contract_v2 import pose_pair_cost_candidate
SCOPE={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
FIXED_ARGS=dict(track_high_thresh=.25,track_low_thresh=.1,new_track_thresh=.25,track_buffer=30,match_thresh=.8,fuse_score=True)
FIELDS=('uid','bbox_xywh_px','score','xy_px','geometry_valid','timestamp_sec','image_wh')
_CLASS=None

def intervention_mask(base,gates,lost_gap,enough_history,stage):
    threshold=.8 if stage==0 else .7;original=base<=threshold;row=original.sum(axis=1);column=original.sum(axis=0);motion_rows=gates.sum(axis=1);motion_columns=gates.sum(axis=0);enabled=np.zeros(base.shape,dtype=bool);active_rows=[]
    for i in range(base.shape[0]):
        unique=np.flatnonzero(original[i]);easy=not lost_gap[i] and len(unique)==1 and column[unique[0]]==1
        competition=motion_rows[i]>=2 or any(motion_columns[j]>=2 for j in np.flatnonzero(gates[i]))
        active=bool(enough_history[i] and not easy and (lost_gap[i] or competition));active_rows.append(active)
        if active:enabled[i]=gates[i]
    return enabled,active_rows,dict(original_bbox_row_candidates=row.astype(int).tolist(),original_bbox_column_candidates=column.astype(int).tolist(),motion_gate_row_candidates=motion_rows.astype(int).tolist(),motion_gate_column_candidates=motion_columns.astype(int).tolist())

class MetaBoxes:
    def __init__(self,boxes,records):self.boxes=boxes;self.records=records
    def __len__(self):return len(self.boxes)
    def __getitem__(self,index):
        ids=np.atleast_1d(np.arange(len(self))[index]);return MetaBoxes(self.boxes[index],[self.records[int(i)] for i in ids])
    @property
    def conf(self):return self.boxes.conf
    @property
    def cls(self):return self.boxes.cls
    @property
    def xywh(self):return self.boxes.xywh

def tracker_class():
    global _CLASS
    if _CLASS is not None:return _CLASS
    from ultralytics.trackers.byte_tracker import BYTETracker,STrack
    class ActualTrack(STrack):
        def __init__(self,*args,record=None,**kwargs):super().__init__(*args,**kwargs);self.record=deepcopy(record);self.history=deque(maxlen=3)
        def _observe(self,reset=False):
            if reset:self.history.clear()
            if self.record is not None:
                if self.history and self.record['timestamp_sec']<=self.history[-1]['timestamp_sec']:raise ValueError('不能重复/倒序实际观测')
                self.history.append(deepcopy(self.record))
        def activate(self,*args,**kwargs):super().activate(*args,**kwargs);self._observe(True)
        def update(self,new,frame_id):super().update(new,frame_id);self.record=deepcopy(new.record);self._observe()
        def re_activate(self,new,frame_id,new_id=False):super().re_activate(new,frame_id,new_id);self.record=deepcopy(new.record);self._observe(True)
    class Learned(BYTETracker):
        def __init__(self,*,mode,model=None,normalizer=None,use_pose=True,pose_source_sha256=None,fixed_detection_sha256=None):
            if mode not in ('PT_bbox','PT_static_pose','learned'):raise ValueError('明确真实PT基线或已训练MLP')
            if mode=='learned' and (model is None or normalizer is None):raise ValueError('不能把随机/缺MLP称预训练基线')
            if not isinstance(fixed_detection_sha256,str) or re.fullmatch('[0-9a-f]{64}',fixed_detection_sha256) is None:raise ValueError('必须真实固定cache SHA')
            if mode!='PT_bbox' and (not isinstance(pose_source_sha256,str) or re.fullmatch('[0-9a-f]{64}',pose_source_sha256) is None):raise ValueError('必须真实PT Pose checkpoint SHA')
            self.fixed_sha=fixed_detection_sha256
            self.mode=mode;self.model=model;self.normalizer=normalizer;self.use_pose=use_pose;self.pose_source_sha=pose_source_sha256;self.previous=-1;self.sequence=None;self._stage=0
            self.audit=dict(learned_pairs=0,accepted_probability_pairs=0,rejected_probability_pairs=0,easy_bbox_rows=0,active_learned_rows=0,low_score_stage='unchanged_upstream_bbox_only')
            super().__init__(SimpleNamespace(**FIXED_ARGS))
        def update_frame(self,frame):
            from ultralytics.engine.results import Boxes
            index=frame['frame_index'];sequence=frame['sequence']
            if sequence not in SCOPE or frame['game']!=SCOPE[sequence] or not 0<=index<750 or frame['frame_number']!=index+1 or frame['fps']!=25 or abs(frame['timestamp_sec']-index/25)>1e-9:raise ValueError('v8仅060/097/151各750帧@25fps，独立scope')
            if index!=self.previous+1 or self.sequence not in (None,sequence):raise ValueError('完整逐帧/每序列独立重置')
            self.sequence=sequence;self._stage=0;records=[];boxes=[]
            for det in frame['detections']:
                record={name:deepcopy(det[name]) for name in FIELDS};record['_frame_index']=index
                if det.get('detection_id',det['uid'])!=det['uid'] or record['timestamp_sec']!=frame['timestamp_sec'] or record['image_wh']!=[frame['width'],frame['height']]:raise ValueError('uid/time/image身份不符')
                x,y,w,h=record['bbox_xywh_px'];boxes.append([x,y,x+w,y+h,record['score'],0.]);records.append(record)
            numeric=Boxes(np.asarray(boxes,dtype=np.float32).reshape(-1,6),(frame['height'],frame['width']))
            result=super().update(numeric if self.mode=='PT_bbox' else MetaBoxes(numeric,records));self.previous=index
            if self._stage!=2:raise ValueError('上游get_dists阶段改变')
            return result
        def init_track(self,results,img=None):
            if self.mode=='PT_bbox':return super().init_track(results,img)
            if not len(results):return []
            boxes=np.concatenate([results.xywh,np.arange(len(results)).reshape(-1,1)],axis=-1)
            return [ActualTrack(box,score,cls,record=record) for box,score,cls,record in zip(boxes,results.conf,results.cls,results.records)]
        def get_dists(self,tracks,detections):
            stage=self._stage;self._stage+=1
            if stage not in (0,1):raise ValueError('未知stage')
            base=super().get_dists(tracks,detections)
            if self.mode=='PT_bbox' or not base.size:return base
            threshold=.8 if stage==0 else .7;result=base.copy()
            if self.mode=='PT_static_pose':
                def pose(record):return dict(record,frame_index=record['_frame_index'],sequence_id=self.sequence,camera_id='broadcast',model_sha256=self.pose_source_sha,fixed_detection_set_sha256=self.fixed_sha,source='model_prediction_xy',coordinate_space='image_pixels',validity_method='finite_bbox_relative_geometry')
                for i,track in enumerate(tracks):
                    for j,detection in enumerate(detections):
                        if base[i,j]>threshold:continue
                        a,b=track.record,detection.record
                        if a is None or b is None or not 1<=b['_frame_index']-a['_frame_index']<=30:continue
                        x,y,w,h=a['bbox_xywh_px'];cost=pose_pair_cost_candidate(pose(a),pose(b),[float(track.mean[0])-x-w/2,float(track.mean[1])-y-h/2])
                        if cost['pose_cost'] is not None:result[i,j]=.9*base[i,j]+.1*cost['pose_cost']
                return result
            gates=np.zeros(base.shape,dtype=bool);lost=[];enough=[]
            for i,track in enumerate(tracks):
                history=list(track.history);enough.append(len(history)==3);lost.append(track.state!=1 or self.frame_id-track.frame_id>1)
                for j,detection in enumerate(detections):
                    if history:gates[i,j]=candidate_gate(history,detection.record)['accepted']
            enabled,active,counts=intervention_mask(base,gates,lost,enough,stage);inputs=[];locations=[]
            for i,track in enumerate(tracks):
                if not active[i]:self.audit['easy_bbox_rows']+=1;continue
                self.audit['active_learned_rows']+=1;result[i,:]=1.  # learned行的gate外不得借旧bbox绕过。
                for j,detection in enumerate(detections):
                    if enabled[i,j]:inputs.append(self.normalizer.transform(features(list(track.history),detection.record),use_pose=self.use_pose));locations.append((i,j))
            if inputs:
                import torch
                device=next(self.model.parameters()).device
                with torch.no_grad():probabilities=torch.sigmoid(self.model(torch.tensor(inputs,dtype=torch.float32,device=device))).reshape(-1).cpu().tolist()
                for (i,j),probability in zip(locations,probabilities):
                    decision=probability_to_cost(probability,threshold);result[i,j]=decision['cost'] if decision['accepted'] else 1.;self.audit['learned_pairs']+=1;key='accepted_probability_pairs' if decision['accepted'] else 'rejected_probability_pairs';self.audit[key]+=1
            return result
    _CLASS=Learned;return Learned
