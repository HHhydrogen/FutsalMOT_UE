"""单因素时序候选：只替换历史均值通道，质量gate始终用原raw。"""
from copy import deepcopy
import math

CHANGED_COLUMNS=tuple(24+10*j+k for j in range(17) for k in (4,5))


def candidate_features(raw,history,candidate,velocity_clip):
    """返回候选raw与原gate输入；不读UID/GT/未来，不升级缺点mask。"""
    if len(raw)!=194 or not math.isfinite(velocity_clip) or velocity_clip<=0:raise ValueError('明确194维和正的仅trainR速度界限')
    recent=history[-3:];time=candidate['timestamp_sec']
    if not recent or any(x['timestamp_sec']>=time for x in recent) or any(recent[i]['timestamp_sec']<=recent[i-1]['timestamp_sec'] for i in range(1,len(recent))):raise ValueError('只准有序实际过去历史')
    original=list(raw);out=list(raw)
    def shape(d,j):
        x,y,w,h=d['bbox_xywh_px'];a,b=d['xy_px'][j]
        return ((a-x-w/2)/w,(b-y-h/2)/h)
    for j in range(17):
        valid=[d for d in recent if d['geometry_valid'][j]]
        # 当前最新点缺失或没有两条实际历史时，保留原均值，不造点/速度。
        if not recent[-1]['geometry_valid'][j] or len(valid)<2:continue
        a,b=valid[-2:];dt=b['timestamp_sec']-a['timestamp_sec'];p,q=shape(a,j),shape(b,j)
        v=tuple((q[k]-p[k])/dt for k in (0,1));speed=math.hypot(*v);factor=min(1.,velocity_clip/speed) if speed else 1.
        for k in (0,1):out[24+10*j+4+k]=q[k]+v[k]*factor*(time-b['timestamp_sec'])
    if not all(math.isfinite(x) for x in out):raise ValueError('时序候选必须有限')
    if any(out[k]!=original[k] for k in range(194) if k not in CHANGED_COLUMNS):raise ValueError('单因素越界')
    return out,original
