"""固定权重Pose诊断契约；保持框/时间/mask，模型与来源不改写。"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
R=Path('D:/projects/FutsalMOT_Research');V=R/'pose/pose_mechanism_a01'
PARAMETERS=dict(shuffle_seed=20261027,height_edges=[.03,.06,.12,.24],speed_edges=[.02,.08],
    speed_proxy='nearest_previous_raw_center_distance_per_image_diagonal_per_second',
    shuffle='deterministic_compatible_pair_swaps_same_scale_speed_and_exact_mask',
    conditions=['pose_off','shape_shuffle'],optimizer_updates=0,GPU=False)


def require(ok,message):
    if not ok:raise ValueError(message)


def safe(path):
    import re
    p=Path(path);require(not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts)
        and not ('public' in [x.lower() for x in p.parts] and p.name.lower().startswith('test_')),'封存测试禁止读取')
    return p
def read(path):return json.loads(safe(path).read_text(encoding='utf-8-sig'))
def rows(path):return [json.loads(x) for x in safe(path).read_text(encoding='utf-8-sig').splitlines() if x]
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(path):return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def ref(path):return dict(path=str(path),sha256=sha(path))
def checked(r):
    p=Path(r['path']);require(p.is_file() and sha(p)==r['sha256'],'来源改变：'+str(p));return p


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def reference(config):
    original=read(config);bundle=Path(original['bundle'])
    require(bundle.parent==R/'code' and original['schema']=='v10_independent_tracking_protocol_v1','必须真实v10冻结追踪来源')
    for entry in read(checked(original['bundle_manifest']))['files']:require(sha(bundle/entry['path'])==entry['sha256'],'原冻结源码改变')
    module=load('mechanism_frozen_v10_runtime',bundle/'tools/research_ops/v10_tracking_runtime.py')
    value=module.validate_config(config)
    return module,*value


def validate(config):
    cfg=read(config)
    require(cfg['schema']=='pose_mechanism_cpu_protocol_v1' and cfg['approved_by']=='root'
        and cfg['diagnostic_authorized'] is True and cfg['parameters']==PARAMETERS and cfg['test_sealed'] is True
        and cfg['training_authorized'] is False and Path(cfg['bundle'])==ROOT,'独立CPU诊断准入缺失')
    for entry in read(checked(cfg['bundle_manifest']))['files']:require(sha(ROOT/entry['path'])==entry['sha256'],'新诊断源码改变')
    rt,old,runtime,train,numeric,base,numbers=reference(checked(cfg['v10_protocol']))
    runtime.storage().physical_child(ROOT,R/'code')
    require(read(checked(cfg['v10_milestone']))['status']=='complete_v10_data_full_records_equal_R_training_five_match_tracking_and_analysis','原实验尚未闭合')
    require(read(checked(cfg['inputs']))['status']=='complete_raw_inputs_labels_and_shape_swaps_no_inference','输入与干预映射未准备')
    return cfg,rt,old,runtime,train,numeric,base,numbers


def bin_index(value,edges):return sum(value>=edge for edge in edges)
def center(record):
    x,y,w,h=record['bbox_xywh_px'];return x+w/2,y+h/2


def mapped_shape(target,donor):
    result=deepcopy(target);x,y,w,h=target['bbox_xywh_px'];a,b,c,d=donor['bbox_xywh_px'];width,height=target['image_wh']
    for j,valid in enumerate(target['geometry_valid']):
        if not valid:continue
        if not donor['geometry_valid'][j]:return None
        px=x+w/2+(donor['xy_px'][j][0]-a-c/2)/c*w
        py=y+h/2+(donor['xy_px'][j][1]-b-d/2)/d*h
        if not (math.isfinite(px) and math.isfinite(py) and 0<=px<width and 0<=py<height):return None
        result['xy_px'][j]=[px,py]
    return result


def make_swaps(frames):
    """仅使用raw预测；同尺度/运动代理/逐点mask内配对交换，不读身份GT。"""
    groups=defaultdict(list);records={};bins={};previous=[];previous_time=None
    for frame in frames:
        current=frame['detections'];dt=frame['timestamp_sec']-previous_time if previous_time is not None else None
        for det in current:
            uid=det['uid'];require(uid not in records,'观测UID重复');records[uid]=det
            speed=min((math.dist(center(det),center(p)) for p in previous),default=0.)/math.hypot(*det['image_wh'])/dt if dt else 0.
            key=(bin_index(det['bbox_xywh_px'][3]/det['image_wh'][1],PARAMETERS['height_edges']),
                 bin_index(speed,PARAMETERS['speed_edges']),tuple(det['geometry_valid']))
            bins[uid]=list(key[:2]);groups[key].append(uid)
        previous=current;previous_time=frame['timestamp_sec']
    mapping={};reasons={};seed=PARAMETERS['shuffle_seed']
    for key,uids in groups.items():
        if not any(key[2]):
            for u in uids:reasons[u]='no_valid_pose'
            continue
        remaining=sorted(uids,key=lambda u:hashlib.sha256(f'{seed}|{u}'.encode()).hexdigest())
        while remaining:
            a=remaining.pop(0);partner=next((i for i,b in enumerate(remaining)
                if mapped_shape(records[a],records[b]) is not None and mapped_shape(records[b],records[a]) is not None),None)
            if partner is None:reasons[a]='no_compatible_partner_in_stratum';continue
            b=remaining.pop(partner);mapping[a]=b;mapping[b]=a
    require(all(mapping.get(b)==a and a!=b for a,b in mapping.items()),'交换必须一一对应且不自配')
    return dict(mapping=mapping,unchanged_reasons=reasons,bins=bins,observations=len(records),
        shuffled_observations=len(mapping),GT_read=False,parameters=PARAMETERS)


def transform(record,bank,index):
    donor=bank['mapping'].get(record['uid'])
    if donor is None:return deepcopy(record)
    changed=mapped_shape(record,index[donor]);require(changed is not None,'冻结交换映射不可应用')
    require({k:v for k,v in changed.items() if k!='xy_px'}=={k:v for k,v in record.items() if k!='xy_px'},'除xy外不得改变输入')
    return changed


def off_model(original):
    import torch
    class Off(torch.nn.Module):
        def __init__(self):super().__init__();self.original=original
        def forward(self,x):return self.original.base(torch.cat([x[:,:24],torch.zeros_like(x[:,24:194])],dim=1))
    return Off().eval()


def job_matrix(old):
    gated=[j for j in old['tracking_matrix'] if j['kind']=='new_RS' and j['method']=='gated']
    require(len(gated)==54,'必须18个gated模型的全部54模型-比赛组合')
    jobs=[]
    for j in gated:
        common=next(x for x in old['tracking_matrix'] if x['kind']=='new_RS' and x.get('method')=='motion'
            and all(x.get(k)==j[k] for k in ('pool','fold','seed','sequence')))
        jobs.append(dict(kind='common_state',original=j,reference_motion=common))
    for j in gated:
        for condition in PARAMETERS['conditions']:jobs.append(dict(kind='free',condition=condition,original=j))
    for j in jobs:j['job_id']=hashlib.sha256(canonical(j).encode()).hexdigest()[:24]
    require(len(jobs)==162 and len({j['job_id'] for j in jobs})==162,'必须54共同状态+108自由消融')
    return jobs
