"""诊断后单因素候选：有界历史变化编码，不乘以目标时间间隔外推。"""
import math
from pose_temporal_feature_candidate import candidate_features,CHANGED_COLUMNS


def bounded_velocity_features(raw,history,candidate,train_R_velocity_clip):
    # 原函数只作真实时间/有限值边界核验；返回的外推值不参与新候选。
    _,original=candidate_features(raw,history,candidate,train_R_velocity_clip)
    out=list(original);recent=history[-3:]
    for j in range(17):
        out[24+10*j+4]=out[24+10*j+5]=0.
        valid=[d for d in recent if d['geometry_valid'][j]]
        if not recent[-1]['geometry_valid'][j] or len(valid)<2:continue
        a,b=valid[-2:];dt=b['timestamp_sec']-a['timestamp_sec']
        def shape(d):
            x,y,w,h=d['bbox_xywh_px'];p,q=d['xy_px'][j];return ((p-x-w/2)/w,(q-y-h/2)/h)
        p,q=shape(a),shape(b);v=tuple((q[k]-p[k])/dt for k in (0,1))
        denominator=max(train_R_velocity_clip,math.hypot(*v))
        for k in (0,1):out[24+10*j+4+k]=v[k]/denominator
    assert all(out[k]==original[k] for k in range(194) if k not in CHANGED_COLUMNS)
    return out,original
