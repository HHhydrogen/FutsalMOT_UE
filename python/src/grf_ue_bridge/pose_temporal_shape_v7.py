"""v7描述性时序形状cost候选：仅3条实际记录，OLS最多预测3帧；不生成观测。"""
from collections import deque
from copy import deepcopy
import math
from .pose_association_contract_v2 import _validate,pose_pair_cost_candidate

VERSION='futsalmot_history3_shortshape_OLS_cost_candidate_v7'

class TemporalShapeHistory:
    """每个track单独实例。reactivation清空；missing不追加；预测绝不回填历史。

    .cost只返回独立v7成本/诊断，不将估计点伪装成模型附件。真正Tracker集成仍须
    独立v7 receipt绑定本源码、原base_identity/协议及lambda0精确等价证据。
    """
    def __init__(self,track_id):
        if type(track_id) is not int or track_id<=0:raise ValueError('需明确独立track ID')
        self.track_id=track_id;self._records=deque(maxlen=3);self._identity=None
    @property
    def history_frames(self):return [record['frame_index'] for record in self._records]
    def clear_for_reactivation(self):self._records.clear();self._identity=None
    def observe(self,record,*,track_id,actual_observation=True,reactivated=False):
        if track_id!=self.track_id or actual_observation is not True or record.get('derived_from_history') or record.get('is_actual_observation') is False:raise ValueError('不能跨track或将预测/插值当实际观测')
        _validate(record)
        if record.get('physical_visibility')!='unknown' or record.get('visibility_state')!=['unknown']*17:raise ValueError('不伪造/替换unknown')
        wh=record.get('image_wh')
        if not isinstance(wh,list) or len(wh)!=2 or any(type(v) is not int or v<=0 for v in wh):raise ValueError('需实际图像尺寸以保留原画内门禁')
        if record.get('prediction_valid') is False and any(record['geometry_valid']):raise ValueError('失败附件不能含有效点')
        if reactivated:self.clear_for_reactivation()
        identity=tuple(record[key] for key in ('sequence_id','camera_id','model_sha256','fixed_detection_set_sha256'))
        if self._identity is not None and identity!=self._identity:raise ValueError('序列/相机/模型/raw身份改变')
        if self._records and record['frame_index']<=self._records[-1]['frame_index']:raise ValueError('实际记录须严格递增，不补帧/重放')
        self._identity=identity;self._records.append(deepcopy(record))
    def note_missing(self,frame_index):
        if self._records and frame_index<=self._records[-1]['frame_index']:raise ValueError('missing必须在最新实际记录之后')
        return dict(observation_added=False,history_frames=self.history_frames)
    def predict_shape(self,target_frame,kalman_center_xy):
        if type(target_frame) is not int or len(kalman_center_xy)!=2 or not all(math.isfinite(value) for value in kalman_center_xy):raise ValueError('目标帧/Kalman中心无效')
        result=dict(schema='futsalmot_derived_temporal_shape_v7',derived_from_history=True,is_actual_observation=False,physical_visibility='unknown',history_frames=self.history_frames,
            target_frame_index=target_frame,xy_px=[[0.,0.] for _ in range(17)],prediction_supported=[False]*17,not_attachment_or_visible_label=True)
        if not self._records:result['fallback_reason']='missing_history';return result
        latest=self._records[-1];gap=target_frame-latest['frame_index']
        if not 1<=gap<=3:result['fallback_reason']='prediction_gap_not_1_to_3';return result
        window=[record for record in self._records if latest['frame_index']-record['frame_index']<=3]
        result['OLS_window_frames']=[record['frame_index'] for record in window]
        if len(window)<2:result['fallback_reason']='fewer_than_two_recent_actual_records';return result
        width,height=latest['bbox_xywh_px'][2:];image_w,image_h=latest['image_wh'];reasons=[]
        for joint in range(17):
            actual=[record for record in window if record['geometry_valid'][joint]]
            if len(actual)<2:reasons.append('fewer_than_two_valid_observations');continue
            if target_frame-actual[-1]['frame_index']>3:reasons.append('latest_valid_joint_older_than_three_frames');continue
            times=[record['frame_index'] for record in actual];mean_t=sum(times)/len(times);den=sum((t-mean_t)**2 for t in times)
            normalized=[]
            for record in actual:
                x,y,w,h=record['bbox_xywh_px'];px,py=record['xy_px'][joint];normalized.append([(px-x-w/2)/w,(py-y-h/2)/h])
            shape=[]
            for axis in (0,1):
                mean=sum(point[axis] for point in normalized)/len(normalized);slope=sum((t-mean_t)*(point[axis]-mean) for t,point in zip(times,normalized))/den
                shape.append(mean+slope*(target_frame-mean_t))
            px=kalman_center_xy[0]+shape[0]*width;py=kalman_center_xy[1]+shape[1]*height
            # 原25%扩框几何范围：中心归一坐标[-.75,.75]；不是visible概率。
            if not all(math.isfinite(value) for value in (px,py)) or not(0<=px<image_w and 0<=py<image_h and -.75<=shape[0]<=.75 and -.75<=shape[1]<=.75):reasons.append('outside_original_image_or_bbox_margin_geometry');continue
            result['xy_px'][joint]=[px,py];result['prediction_supported'][joint]=True;reasons.append(None)
        result['joint_reasons']=reasons;result['fallback_reason']=None;return result
    def cost(self,current,kalman_center_xy):
        _validate(current)
        if self._identity is not None and tuple(current[key] for key in ('sequence_id','camera_id','model_sha256','fixed_detection_set_sha256'))!=self._identity:raise ValueError('当前候选不是同一模型/相机/raw')
        prediction=self.predict_shape(current['frame_index'],kalman_center_xy)
        common=[j for j in range(5,17) if prediction['prediction_supported'][j] and current['geometry_valid'][j]]
        if prediction['fallback_reason'] is None and len(common)>=6:
            last=self._records[-1];area=(last['bbox_xywh_px'][2]*last['bbox_xywh_px'][3]+current['bbox_xywh_px'][2]*current['bbox_xywh_px'][3])/2
            similarities=[math.exp(-math.dist(prediction['xy_px'][j],current['xy_px'][j])**2/(2*(2*.1)**2*area)) for j in common]
            return dict(schema=VERSION,mode='temporal_OLS_shape',pose_cost=1-sum(similarities)/len(similarities),joint_count=len(common),history_prediction=prediction,source_is_actual_observation=False,not_model_prediction_or_visible_label=True)
        reason=prediction['fallback_reason'] or 'fewer_than_six_common_supported_limbs'
        if not self._records:return dict(schema=VERSION,mode='original_static_fallback',pose_cost=None,fallback='bbox_only',fallback_reason=reason)
        last=self._records[-1];gap=current['frame_index']-last['frame_index']
        if not 1<=gap<=30:return dict(schema=VERSION,mode='original_static_fallback',pose_cost=None,fallback='bbox_only',fallback_reason='original_static_frame_gap_gate')
        x,y,w,h=last['bbox_xywh_px'];delta=[kalman_center_xy[0]-(x+w/2),kalman_center_xy[1]-(y+h/2)]
        original=pose_pair_cost_candidate(last,current,delta,joint_indices=tuple(range(5,17)),min_joints=6,sigma=.1,max_frame_gap=30)
        return dict(original,schema=VERSION,mode='original_static_fallback',fallback_reason=reason,history_prediction=prediction)
