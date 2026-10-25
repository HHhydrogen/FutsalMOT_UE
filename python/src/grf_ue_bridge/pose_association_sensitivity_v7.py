"""v7固定PT状态的关联敏感度候选；不改Pose点、raw框、lambda或GT。"""
import numpy as np
from .pose_association_contract_v2 import pose_pair_cost_candidate


def matrix_for_reference(base,tracks,detections,records,*,stage,pose_lambda=.1,invert_valid=False):
    """固定PT Kalman状态/最后匹配raw UID；按原v2顺序逐元素复算静态cost。

    tracks: pose_uid及kalman_center_xy；detections: 当前pose_uid。records来自一个真实模型。
    invert_valid只用于预定义PT诊断，将本来可用的pose_cost改为1-cost，不改任何附件。
    """
    if stage not in (0,1) or pose_lambda not in (0.,.1):raise ValueError('仅原两get_dists阶段、lambda0/.1')
    if base.shape!=(len(tracks),len(detections)):raise ValueError('参考矩阵/候选维度错配')
    valid=np.zeros(base.shape,dtype=bool);audit=dict(pose_pairs_used=0,bbox_fallback_pairs=0,bbox_gated_out_pairs=0)
    if pose_lambda==0:return base,valid,audit  # 不读records，不做混合运算。
    threshold=.8 if stage==0 else .7;result=base.copy()
    for i,track in enumerate(tracks):
        for j,detection in enumerate(detections):
            if base[i,j]>threshold:audit['bbox_gated_out_pairs']+=1;continue
            uid_a,uid_b=track['pose_uid'],detection['pose_uid']
            if uid_a is None or uid_b is None:audit['bbox_fallback_pairs']+=1;continue
            if uid_a not in records or uid_b not in records:raise ValueError('真实模型附件缺原始raw UID，禁止猜测/补造')
            a,b=records[uid_a],records[uid_b];gap=b['frame_index']-a['frame_index']
            if not 1<=gap<=30:audit['bbox_fallback_pairs']+=1;continue
            box=a['bbox_xywh_px'];center=[box[0]+box[2]/2,box[1]+box[3]/2]
            delta=[float(track['kalman_center_xy'][k])-center[k] for k in range(2)]
            report=pose_pair_cost_candidate(a,b,delta,joint_indices=tuple(range(5,17)),min_joints=6,sigma=.1,max_frame_gap=30)
            if report['pose_cost'] is None:audit['bbox_fallback_pairs']+=1;continue
            cost=1-report['pose_cost'] if invert_valid else report['pose_cost']
            result[i,j]=(1-pose_lambda)*base[i,j]+pose_lambda*cost
            valid[i,j]=True;audit['pose_pairs_used']+=1
    return result,valid,audit

def matrix_profile(base,cost,*,stage):
    threshold=.8 if stage==0 else .7;gate=base<=threshold
    rows=gate.sum(axis=1).astype(int).tolist();columns=gate.sum(axis=0).astype(int).tolist();ranks=[];gaps=[];minimizers=[]
    for row in range(base.shape[0]):
        eligible=np.flatnonzero(gate[row]).tolist();ordered=sorted(eligible,key=lambda col:(float(cost[row,col]),col));ranks.append(ordered)
        gaps.append(float(cost[row,ordered[1]])-float(cost[row,ordered[0]]) if len(ordered)>=2 else None)
        minimizers.append([col for col in ordered if cost[row,col]==cost[row,ordered[0]]] if ordered else [])
    return dict(bbox_gate_threshold=threshold,bbox_gate_rows_candidate_count=rows,bbox_gate_columns_candidate_count=columns,
        rows_with_at_least_two_competing_candidates=sum(value>=2 for value in rows),columns_with_at_least_two_competing_candidates=sum(value>=2 for value in columns),
        row_candidate_rank_stable_column_tie_break=ranks,row_minimizer_sets=minimizers,row_best_to_second_gap=gaps,
        row_gap_semantics='row-local ordered cost gap only; NOT global Hungarian assignment margin',
        mixed_cost_inside_original_bbox_gate_and_assignment_threshold=int(((cost<=threshold)&gate).sum()))

def matrix_difference(base,current,reference,*,stage):
    a=matrix_profile(base,current,stage=stage);b=matrix_profile(base,reference,stage=stage);change=np.abs(current.astype(np.float64)-reference.astype(np.float64))
    return dict(cells_changed_exact=int(np.count_nonzero(current!=reference)),max_abs_cost_change=float(change.max()) if change.size else 0.,mean_abs_cost_change=float(change.mean()) if change.size else 0.,
        rows_any_candidate_rank_changed=sum(x!=y for x,y in zip(a['row_candidate_rank_stable_column_tie_break'],b['row_candidate_rank_stable_column_tie_break'])),
        rows_minimizer_set_changed=sum(x!=y for x,y in zip(a['row_minimizer_sets'],b['row_minimizer_sets'])),
        assignment_threshold_eligibility_changed_inside_bbox_gate=int(np.count_nonzero(((current<=a['bbox_gate_threshold'])!=(reference<=a['bbox_gate_threshold']))&(base<=a['bbox_gate_threshold']))))

def instrumented_reference_class(records_by_model,trace_sink):
    """唯一PT自由轨迹驱动状态；其余九模型仅投影到同PT状态/输入矩阵，绝不冒称其自由轨迹。"""
    from . import pose_bytetrack_v2 as old
    from ultralytics.trackers.byte_tracker import BYTETracker
    Parent=old.pose_bytetrack_class()
    class Reference(Parent):
        def get_dists(self,tracks,detections):
            stage=self._distance_stage;base=BYTETracker.get_dists(self,tracks,detections);actual=super().get_dists(tracks,detections)
            if self.pose_lambda==0:return actual
            a=[dict(track_id=int(track.track_id),pose_uid=track.pose_record.get('detection_id') if track.pose_record is not None else None,kalman_center_xy=[float(track.mean[0]),float(track.mean[1])]) for track in tracks]
            b=[dict(pose_uid=detection.pose_record.get('detection_id') if detection.pose_record is not None else None) for detection in detections]
            matrices={};valid={};audits={}
            for key,records in records_by_model.items():matrices[key],valid[key],audits[key]=matrix_for_reference(base,a,b,records,stage=stage)
            if not np.array_equal(matrices['pretrained'],actual):raise ValueError('独立静态复算未逐值复现原PT get_dists；停止而非改变旧规则')
            inverted,inverted_valid,inverted_audit=matrix_for_reference(base,a,b,records_by_model['pretrained'],stage=stage,invert_valid=True)
            event=dict(schema='futsalmot_PT_state_cost_sensitivity_v7',sequence_id=self.sequence_id,frame_index=self.previous_frame+1,get_dists_stage=stage,
                state_reference='actual_pretrained_static_lambda01_trajectory_states',row_tracks=a,column_detections=b,bbox_cost=base.tolist(),
                pretrained_profile=matrix_profile(base,actual,stage=stage),models={key:dict(cost=matrix.tolist(),valid_pose_pair_mask=valid[key].tolist(),audit=audits[key],profile=matrix_profile(base,matrix,stage=stage),difference_vs_same_PT_states=matrix_difference(base,matrix,actual,stage=stage)) for key,matrix in matrices.items()},
                diagnostic_only_PT_cost_inversion=dict(cost=inverted.tolist(),valid_pair_mask=inverted_valid.tolist(),audit=inverted_audit,difference_vs_PT=matrix_difference(base,inverted,actual,stage=stage),
                    not_model_prediction=True,not_mainline_metric=True,transform='1-pose_cost only where original pose cost valid; lambda unchanged .1'),low_score_stage='unchanged_upstream_bbox_only')
            trace_sink(event);return actual
    return Reference
