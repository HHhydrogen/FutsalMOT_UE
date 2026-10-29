"""新机位目录与独立seed选择；五个必选加一至两个部分场地视角。"""
import hashlib
import math
from copy import deepcopy

from .floor_diversity import _hash

NAMESPACE = 'futsalmot:camera-rig:v2'
MANDATORY = ('C5','C1','C2','C3','C4')
PARTIAL = ('P01','P02','P03','P04')


def validate_rig(catalog):
    if not isinstance(catalog,dict) or set(catalog) != {'catalog_id','resolution','filmback_mm','profiles'}:
        raise ValueError('camera_rig目录字段不符')
    if catalog['catalog_id'] != 'sideline_corners_partial_v2':
        raise ValueError('未知相机目录版本')
    if catalog['resolution'] != [3840,2160] or catalog['filmback_mm'] != [23.76,13.365]:
        raise ValueError('新机位生成固定3840x2160与23.76x13.365mm传感器')
    if set(catalog['profiles']) != set(MANDATORY+PARTIAL):
        raise ValueError('相机目录必须包含C1..C5及P01..P04')
    actors=[]
    sequences=[]
    for cid,profile in catalog['profiles'].items():
        if set(profile) != {'label','actor','sequence','position_m','rotation_deg','focal_length_mm','coverage','target_m'}:
            raise ValueError('相机profile字段不符: '+cid)
        for field in ('position_m','rotation_deg','target_m'):
            values=profile[field]
            if not isinstance(values,list) or len(values)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
                raise ValueError('相机向量无效: '+cid+'.'+field)
        focal=profile['focal_length_mm']
        if type(focal) not in (int,float) or not math.isfinite(focal) or not 6<=focal<=85:
            raise ValueError('相机焦距无效: '+cid)
        if profile['position_m'][2]<=0 or abs(profile['rotation_deg'][2])>1e-6:
            raise ValueError('本版相机要求正高度及roll=0')
        expected='full_field' if cid=='C5' else ('partial_field' if cid in PARTIAL else 'corner_overview')
        if profile['coverage']!=expected:
            raise ValueError('相机覆盖语义不符: '+cid)
        if any(not isinstance(profile[k],str) or not profile[k] for k in ('label','actor','sequence')):
            raise ValueError('相机名称不能为空: '+cid)
        actors.append(profile['actor']);sequences.append(profile['sequence'])
    if len(set(actors))!=9 or len(set(sequences))!=9:
        raise ValueError('相机Actor/Sequence不得重复')


def _rank(seed,label):
    return hashlib.sha256(f'{NAMESPACE}:{seed}:{label}'.encode('utf-8')).hexdigest()


def build_camera_plan(seed,catalog):
    if type(seed) is not int or not 0<=seed<=0x7fffffff:
        raise ValueError('camera seed必须是0..2147483647整数')
    validate_rig(catalog)
    count=1+(int(_rank(seed,'partial_count'),16)%2)
    ranked=sorted(PARTIAL,key=lambda cid:(_rank(seed,'partial:'+cid),cid))
    optional=sorted(ranked[:count])
    selected=list(MANDATORY)+optional
    entries=[]
    for cid in selected:
        source=catalog['profiles'][cid]
        profile={'type':'static_surveillance','coverage':source['coverage'],
                 'resolution':deepcopy(catalog['resolution']),'filmback_mm':deepcopy(catalog['filmback_mm']),
                 'position_m':deepcopy(source['position_m']),'rotation_deg':deepcopy(source['rotation_deg']),
                 'height_m':source['position_m'][2],'lens':{'focal_length_mm':source['focal_length_mm']},'distortion':None}
        entries.append({'camera_id':cid,'camera_actor':source['actor'],'name':source['sequence'],'profile':profile})
    return {'schema':'futsalmot_camera_plan_v2','catalog_id':catalog['catalog_id'],
            'catalog_sha256':_hash(catalog),'seed':seed,'selection_namespace':NAMESPACE,
            'mandatory_ids':list(MANDATORY),'partial_candidates':list(PARTIAL),
            'partial_count':count,'selected_ids':selected,'entries':entries}


def project_point(catalog,cid,point):
    """静态零roll针孔投影，用于配置覆盖检查；实际UE回读另行保存。"""
    p=catalog['profiles'][cid]
    pitch,yaw=map(math.radians,p['rotation_deg'][:2])
    forward=(math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),math.sin(pitch))
    right=(-math.sin(yaw),math.cos(yaw),0)
    up=(-math.sin(pitch)*math.cos(yaw),-math.sin(pitch)*math.sin(yaw),math.cos(pitch))
    d=[v-a for v,a in zip(point,p['position_m'])]
    depth=sum(a*b for a,b in zip(d,forward))
    if depth<=0:
        return None
    width,height=catalog['resolution']
    focal=width*p['focal_length_mm']/catalog['filmback_mm'][0]
    return [(width-1)/2+focal*sum(a*b for a,b in zip(d,right))/depth,
            (height-1)/2-focal*sum(a*b for a,b in zip(d,up))/depth]
