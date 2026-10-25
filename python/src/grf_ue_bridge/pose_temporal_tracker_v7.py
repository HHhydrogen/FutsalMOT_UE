"""独立v7时序Tracker候选；不修改上游状态机，lambda0严格原ByteTrack。"""
from copy import deepcopy
from . import pose_bytetrack_v2 as base
from .pose_temporal_shape_v7 import TemporalShapeHistory
from .pose_association_contract_v2 import pose_pair_cost_candidate
_CLASS=None

def temporal_tracker_class():
    global _CLASS
    if _CLASS is not None:return _CLASS
    from ultralytics.trackers.byte_tracker import BYTETracker,STrack
    Parent=base.pose_bytetrack_class()
    class HistoryTrack(STrack):
        def __init__(self,*args,pose=None,**kwargs):super().__init__(*args,**kwargs);self.pose_record=deepcopy(pose);self.pose_history=None
        def _observe(self,reset=False):
            if self.pose_record is None:return
            if reset or self.pose_history is None or self.pose_history.track_id!=self.track_id:self.pose_history=TemporalShapeHistory(int(self.track_id))
            self.pose_history.observe(self.pose_record,track_id=int(self.track_id))
        def activate(self,*args,**kwargs):super().activate(*args,**kwargs);self._observe(reset=True)
        def update(self,new_track,frame_id):super().update(new_track,frame_id);self.pose_record=deepcopy(new_track.pose_record);self._observe()
        def re_activate(self,new_track,frame_id,new_id=False):super().re_activate(new_track,frame_id,new_id);self.pose_record=deepcopy(new_track.pose_record);self._observe(reset=True)
    class Temporal(Parent):
        def init_track(self,results,img=None):
            if self.pose_lambda==0:return super().init_track(results,img)
            if not len(results):return []
            import numpy as np
            values=np.concatenate([results.xywh,np.arange(len(results)).reshape(-1,1)],axis=-1)
            return [HistoryTrack(box,score,cls,pose=pose) for box,score,cls,pose in zip(values,results.conf,results.cls,results.poses)]
        def get_dists(self,tracks,detections):
            stage=self._distance_stage;self._distance_stage+=1
            if stage not in (0,1):raise ValueError('原ByteTrack阶段改变')
            original=BYTETracker.get_dists(self,tracks,detections)
            if self.pose_lambda==0 or not original.size:return original
            threshold=self.args.match_thresh if stage==0 else .7;result=original.copy()
            for i,track in enumerate(tracks):
                for j,detection in enumerate(detections):
                    if original[i,j]>threshold:self.audit['bbox_gated_out_pairs']+=1;continue
                    a,b=track.pose_record,detection.pose_record
                    if a is None or b is None or not 1<=b['frame_index']-a['frame_index']<=30:self.audit['bbox_fallback_pairs']+=1;continue
                    if track.pose_history is not None:cost=track.pose_history.cost(b,[float(track.mean[0]),float(track.mean[1])])
                    else:
                        x,y,w,h=a['bbox_xywh_px'];cost=dict(pose_pair_cost_candidate(a,b,[float(track.mean[0])-x-w/2,float(track.mean[1])-y-h/2]),mode='original_static_fallback')
                    if cost['pose_cost'] is None:self.audit['bbox_fallback_pairs']+=1;continue
                    result[i,j]=(1-self.pose_lambda)*original[i,j]+self.pose_lambda*cost['pose_cost'];self.audit['pose_pairs_used']+=1
                    name='temporal_shape_pairs_used' if cost['mode']=='temporal_OLS_shape' else 'original_static_pose_fallback_pairs'
                    self.audit[name]=self.audit.get(name,0)+1
            return result
    _CLASS=Temporal;return Temporal
