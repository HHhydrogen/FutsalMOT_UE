"""v9缺点/坐标扰动与质量代理；不读GT，不改变bbox或物理可见性。"""
from copy import deepcopy
import hashlib,math,random,statistics
MASK_COLUMNS=tuple(24+10*j+k for j in range(17) for k in (6,7,8))
COORD_COLUMNS=tuple(24+10*j+k for j in range(17) for k in (0,1,2,3,4,5,9))
HEAD_COLUMNS=tuple(range(24,74))
def quality(raw):
    """变化包含真实动作与预测误差，仅作可观测质量代理，不称噪声真值。"""
    if len(raw)!=194:raise ValueError('v8白名单194维必需')
    common=[];valid_current=0
    for j in range(5,17):
        a=raw[24+10*j:34+10*j];valid_current+=int(a[7]>.5)
        if a[6]>.5 and a[7]>.5 and a[8]>=2/3-1e-8:common.append(math.hypot(a[2]-a[4],a[3]-a[5]))
    dt=max(raw[0]*1.2,1e-6);history_dt=max(raw[23]*1.2,1e-6)
    change=statistics.median(common)/math.sqrt(max(1.,dt/history_dt)) if common else None
    return dict(common_limbs=len(common),current_valid_limbs=valid_current,shape_change_proxy=change,gap_sec=dt,history_dt_sec=history_dt)
def quality_gate(raw,scale):
    q=quality(raw)
    if q['common_limbs']<6 or q['shape_change_proxy'] is None:return 0.
    if not math.isfinite(scale) or scale<.03:raise ValueError('scale须仅trainR拟合且下限.03')
    return (q['common_limbs']/12)/(1+(q['shape_change_proxy']/scale)**2)
def perturb(history,candidate,mode,seed=20261025,context='diagnostic'):
    if mode not in ('clean','drop','jitter','both'):raise ValueError('明确固定扰动')
    records=deepcopy(list(history)+[candidate])
    if mode=='clean':return records[:-1],records[-1]
    for record in records:
        x,y,w,h=record['bbox_xywh_px'];width,height=record['image_wh']
        for joint in range(17):
            if not record['geometry_valid'][joint]:continue
            key=f'{seed}|{context}|{record["uid"]}|{joint}';rng=random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8],'big'))
            draw=rng.random();dropped=draw<.2 and mode in ('drop','both')
            px,py=record['xy_px'][joint]
            if mode in ('jitter','both'):px+=rng.gauss(0,.03)*w;py+=rng.gauss(0,.03)*h
            valid=not dropped and 0<=px<width and 0<=py<height
            record['geometry_valid'][joint]=bool(valid);record['xy_px'][joint]=[px,py] if valid else [0.,0.]
    return records[:-1],records[-1]
def restrict(z,mode):
    z=list(z)
    if mode=='all':return z
    columns=COORD_COLUMNS if mode=='mask' else (MASK_COLUMNS if mode=='coords' else (range(24,194) if mode=='zero' else HEAD_COLUMNS))
    if mode not in ('mask','coords','zero','limbs'):raise ValueError('未知消融')
    for j in columns:z[j]=0.
    return z
