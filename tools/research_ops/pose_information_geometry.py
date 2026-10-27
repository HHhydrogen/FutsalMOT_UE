"""零更新Pose信息代理；不读取GT，按共同肢体比较最新/均值/时间外推。"""
from copy import deepcopy
import hashlib
import math

FIELDS=('uid','bbox_xywh_px','score','xy_px','geometry_valid','timestamp_sec','image_wh')


def public(record):
    return {k:deepcopy(record[k]) for k in FIELDS}


def quantile(values,q):
    if not values:return None
    x=sorted(values);p=(len(x)-1)*q;i=int(p);f=p-i
    return x[i]*(1-f)+x[min(i+1,len(x)-1)]*f


def point(record,j):
    x,y,w,h=record['bbox_xywh_px'];a,b=record['xy_px'][j]
    return ((a-x-w/2)/w,(b-y-h/2)/h)


def velocities(history):
    result={}
    for j in range(5,17):
        valid=[d for d in history[-3:] if d['geometry_valid'][j]]
        if len(valid)<2:continue
        a,b=valid[-2:];dt=b['timestamp_sec']-a['timestamp_sec']
        if dt<=0:raise ValueError('真实历史时间必须严格递增')
        p,q=point(a,j),point(b,j);result[j]=tuple((q[k]-p[k])/dt for k in (0,1))
    return result


def shape_pair(history,positive,negative,clip):
    """两候选共同点集，GT仅在调用之外决定后验正负；不输入身份字段。"""
    h=[public(x) for x in history[-3:]];p,n=public(positive),public(negative)
    if not h or any(x['timestamp_sec']>=p['timestamp_sec'] for x in h):raise ValueError('只准过去实际历史')
    if p['timestamp_sec']!=n['timestamp_sec']:raise ValueError('候选必须同一时刻')
    joints=[j for j in range(5,17) if h[-1]['geometry_valid'][j] and p['geometry_valid'][j]
            and n['geometry_valid'][j] and sum(d['geometry_valid'][j] for d in h)>=2]
    if len(joints)<6:return dict(available=False,common_joints=len(joints))
    v=velocities(h);scores={k:[] for k in ('latest','mean','temporal')};clipped=0
    for j in joints:
        a=point(h[-1],j);observed=[point(d,j) for d in h if d['geometry_valid'][j]]
        avg=tuple(sum(q[k] for q in observed)/len(observed) for k in (0,1))
        speed=math.hypot(*v[j]);factor=min(1.,clip/speed) if speed else 1.;clipped+=int(factor<1)
        dt=p['timestamp_sec']-h[-1]['timestamp_sec'];pred=tuple(a[k]+v[j][k]*factor*dt for k in (0,1))
        pp,nn=point(p,j),point(n,j)
        for name,z in (('latest',a),('mean',avg),('temporal',pred)):
            scores[name].append(math.dist(z,nn)-math.dist(z,pp))
    return dict(available=True,common_joints=len(joints),clipped_joints=clipped,
                margins={k:sum(x)/len(x) for k,x in scores.items()})


def same_frame_swaps(frames):
    """确定性同帧/同尺度/精确mask循环交换；不使用未来或GT。"""
    result={};mapping={};reasons={}
    for frame in frames:
        groups={}
        for d in frame['detections']:
            r=public(d);result[r['uid']]=r
            size=r['bbox_xywh_px'][3]/r['image_wh'][1]
            key=(sum(size>=x for x in (.03,.06,.12,.24)),tuple(r['geometry_valid']))
            groups.setdefault(key,[]).append(r)
        for key,group in groups.items():
            ordered=sorted(group,key=lambda d:hashlib.sha256(('20261027|'+d['uid']).encode()).hexdigest())
            if not any(key[1]) or len(ordered)<2:
                for d in ordered:reasons[d['uid']]='no_valid_pose' if not any(key[1]) else 'no_same_frame_compatible_donor'
                continue
            for i,d in enumerate(ordered):
                donor=ordered[(i+1)%len(ordered)];changed=public(d);x,y,w,h=d['bbox_xywh_px'];width,height=d['image_wh'];ok=True
                for j,valid in enumerate(d['geometry_valid']):
                    if valid:
                        a,b=point(donor,j);px,py=x+w/2+a*w,y+h/2+b*h
                        if not (0<=px<width and 0<=py<height):ok=False;break
                        changed['xy_px'][j]=[px,py]
                if ok:result[d['uid']]=changed;mapping[d['uid']]=donor['uid']
                else:reasons[d['uid']]='mapped_point_outside_image'
    return result,mapping,reasons


def identity(history,labels):
    values=[labels.get(u,{}) for u in history]
    if not values or any(v.get('state')!='matched' for v in values):return None,'unknown_history'
    ids={v['gt_id'] for v in values}
    return (next(iter(ids)),'trusted_consistent_history') if len(ids)==1 else (None,'mixed_identity_history')


def label(query,candidate):
    if candidate['state'].startswith('unknown'):return None
    return int(candidate['state']=='matched' and candidate['gt_id']==query)


def iou(a,b):
    x=max(a[0],b[0]);y=max(a[1],b[1]);w=max(0.,min(a[0]+a[2],b[0]+b[2])-x);h=max(0.,min(a[1]+a[3],b[1]+b[3])-y)
    area=w*h;return area/(a[2]*a[3]+b[2]*b[3]-area) if area else 0.


def choose_cost(event,name,np,torch):
    """使用原概率到代价公式，只复算该共同状态，不生成新自由轨迹。"""
    out=np.asarray(event['bbox_cost'],dtype=np.float32).copy();threshold=.8 if event['stage']==0 else .7
    for i,active in enumerate(event['active_rows']):
        if active:out[i,:]=1.
    if not event['scored_locations']:return out,threshold
    probs=torch.sigmoid(torch.tensor(event['logits'][name],dtype=torch.float32)).tolist()
    for k,(i,j) in enumerate(event['scored_locations']):
        if event['enabled'][i][j]:out[i,j]=max(0.,min(1.,threshold+(.5-probs[k]))) if probs[k]>=.5 else 1.
    return out,threshold


def assignment_context(event,np,torch,linear_assignment):
    """原实际代价是权威；影子批FP32微差不伪装逐值exact。"""
    result={};shadow_motion=None;maximum=0.
    for name in ('motion','pose','pose_off'):
        cost,threshold=choose_cost(event,name,np,torch)
        if name=='motion':
            actual=np.asarray(event['reference_cost'],dtype=np.float32)
            maximum=float(np.max(np.abs(cost-actual)))
            shadow_motion={int(i):int(j) for i,j in linear_assignment(cost,thresh=threshold)[0]}
            cost=actual
        result[name]={int(i):int(j) for i,j in linear_assignment(cost,thresh=threshold)[0]}
    result['_comparable']=shadow_motion==result['motion']
    return result,maximum
