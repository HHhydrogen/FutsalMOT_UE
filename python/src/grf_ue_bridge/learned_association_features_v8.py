"""v8共享194维白名单特征与固定motion gate；不读取UID/game/GT身份。"""
import math
FEATURE_DIM=194
MOTION_DIM=24
POSE_COLUMNS=tuple(range(MOTION_DIM,FEATURE_DIM))
GATE=dict(max_gap_sec=1.2,max_center_distance_heights=2.,area_ratio_min=.25,area_ratio_max=4.,max_velocity_latest_heights_per_sec=10.)

def _box(record):
    box=record['bbox_xywh_px'];score=record['score'];time=record['timestamp_sec'];wh=record['image_wh']
    if len(box)!=4 or len(wh)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (*box,score,time,*wh)):raise ValueError('bbox/score/time/image_wh必须有限数值')
    if min(box[2:])<=0 or min(wh)<=0 or not 0<=score<=1:raise ValueError('bbox/score/image_wh无效')
    return [float(v) for v in box],float(score),float(time),[float(v) for v in wh]

def _history(history):
    if not isinstance(history,(list,tuple)) or not 1<=len(history):raise ValueError('需要1..3个实际历史记录；不补造')
    recent=history[-3:];values=[_box(record) for record in recent]
    if any(values[i][2]<=values[i-1][2] for i in range(1,len(values))):raise ValueError('实际timestamp须严格递增')
    return recent,values

def _motion(history,candidate):
    recent,values=_history(history);last,score,time,wh=values[-1];box,cs,ct,cwh=_box(candidate);dt=ct-time
    center=[last[0]+last[2]/2,last[1]+last[3]/2];other=[box[0]+box[2]/2,box[1]+box[3]/2];velocity=[0.,0.];history_dt=0.
    if len(values)>=2:
        previous=values[-2][0];history_dt=time-values[-2][2]
        if history_dt>1e-9:velocity=[(center[k]-(previous[k]+previous[k+2]/2))/history_dt for k in (0,1)]
    norm=math.hypot(*velocity);limit=10.*last[3]
    if norm>limit:velocity=[value*limit/norm for value in velocity]
    predicted=[center[k]+velocity[k]*dt for k in (0,1)];height=max(last[3],box[3]);distance=math.dist(predicted,other)/height;ratio=box[2]*box[3]/(last[2]*last[3])
    return recent,values,box,cs,ct,cwh,dt,center,other,velocity,predicted,distance,ratio,history_dt

def candidate_gate(history,candidate):
    recent,values,box,cs,ct,cwh,dt,center,other,velocity,predicted,distance,ratio,history_dt=_motion(history,candidate)
    reason='accepted'
    if dt<=0 or dt>1.2+1e-9:reason='time_gap'
    elif not .25-1e-12<=ratio<=4.+1e-12:reason='area_ratio'
    elif distance>2.+1e-12:reason='center_distance'
    return dict(accepted=reason=='accepted',reason=reason,dt_sec=dt,predicted_center_xy=predicted,normalized_center_distance=distance,area_ratio=ratio,velocity_xy_per_sec=velocity,actual_history_count=len(recent))

def _iou(a,b):
    left=max(a[0],b[0]);top=max(a[1],b[1]);right=min(a[0]+a[2],b[0]+b[2]);bottom=min(a[1]+a[3],b[1]+b[3]);inter=max(0.,right-left)*max(0.,bottom-top)
    return inter/(a[2]*a[3]+b[2]*b[3]-inter) if inter>0 else 0.

def _pose(record):
    box,score,time,wh=_box(record);points=record['xy_px'];valid=record['geometry_valid']
    if len(points)!=17 or len(valid)!=17 or any(type(v) is not bool for v in valid):raise ValueError('geometry_valid须17bool，xy须17×2')
    shape=[]
    for point,ok in zip(points,valid):
        if len(point)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in point):raise ValueError('xy必须有限原图坐标')
        shape.append([(point[0]-box[0]-box[2]/2)/box[2],(point[1]-box[1]-box[3]/2)/box[3]] if ok else [0.,0.])
    return shape,valid

def features(history,candidate):
    recent,values,box,cs,ct,cwh,dt,center,other,velocity,predicted,distance,area,history_dt=_motion(history,candidate);last,score,time,wh=values[-1];height=max(last[3],box[3]);pred_box=[predicted[0]-last[2]/2,predicted[1]-last[3]/2,last[2],last[3]]
    output=[dt/1.2,score,cs,len(recent)/3,center[0]/wh[0],center[1]/wh[1],other[0]/cwh[0],other[1]/cwh[1],last[2]/wh[0],last[3]/wh[1],box[2]/cwh[0],box[3]/cwh[1],
        math.log(box[2]/last[2]),math.log(box[3]/last[3]),math.log(area),_iou(pred_box,box),_iou(last,box),(other[0]-predicted[0])/height,(other[1]-predicted[1])/height,
        velocity[0]/last[3]/10,velocity[1]/last[3]/10,(other[0]-center[0])/height,(other[1]-center[1])/height,history_dt/1.2]
    poses=[_pose(record) for record in recent];a,av=poses[-1];b,bv=_pose(candidate)
    for joint in range(17):
        observed=[shape[joint] for shape,valid in poses if valid[joint]];mean=[sum(p[axis] for p in observed)/len(observed) for axis in (0,1)] if observed else [0.,0.]
        output.extend(a[joint]+b[joint]+mean+[float(av[joint]),float(bv[joint]),len(observed)/len(recent),math.dist(a[joint],b[joint]) if av[joint] and bv[joint] else 0.])
    if len(output)!=FEATURE_DIM or not all(math.isfinite(value) for value in output):raise ValueError('v8特征维度/有限值不符')
    return output
