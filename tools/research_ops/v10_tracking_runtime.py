"""v10独立追踪准入与显式比赛scope；冻结v8仅替换帧域守卫，关联数值不变。"""
import ast
import configparser
from collections import defaultdict
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[2]
R=Path('D:/projects/FutsalMOT_Research');V=R/'pose/multiseed_v10_a01'
OLD={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
EXTERNAL={'v_2QhNRucNC7E_c017':450,'v_G-vNjfx1GGc_c004':675}
TRACKER_SHA='7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688'


def require(ok,message):
    if not ok:raise ValueError(message)


def safe(path):
    import re
    path=Path(path).absolute()
    require(not any(re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',p.lower()) or p.lower()=='test' for p in path.parts),'封存测试禁止读取')
    return path


def read(path):return json.loads(safe(path).read_text(encoding='utf-8-sig'))
def rows(path):return [json.loads(x) for x in safe(path).read_text(encoding='utf-8-sig').splitlines() if x]
def sha(path):return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def checked(ref):
    p=safe(ref['path']);require(p.is_file() and sha(p)==ref['sha256'],'绑定来源改变：'+str(p));return p


def load_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def training(config):
    """从实际训练bundle导入，禁止移动runtime导致ROOT漂移。"""
    cfg=read(config);bundle=Path(cfg['bundle'])
    require(bundle.parent==R/'code','训练代码不在实际D研究目录')
    entry=next(e for e in read(checked(cfg['bundle_manifest']))['files'] if e['path']=='tools/research_ops/v10_runtime.py')
    require(sha(bundle/entry['path'])==entry['sha256'],'训练runtime改变')
    runtime=load_file('v10_frozen_training_runtime',bundle/entry['path'])
    cfg=runtime.validate_protocol(config);numeric,base,old=runtime.load_numeric(cfg)
    return runtime,cfg,numeric,base,old


def sources_from(training_cfg,manifest):
    source_cfg=read(checked(training_cfg['source_config']))
    sources=[]
    for old in source_cfg['sources']:
        if old['domain']!='real':continue
        require(old['sequence'] in OLD and old['game']==OLD[old['sequence']],'旧真实比赛身份改变')
        q=configparser.ConfigParser();q.read(checked(old['seqinfo']),encoding='utf-8-sig')
        sources.append(dict(old,frames=750,width=int(q['Sequence']['imWidth']),height=int(q['Sequence']['imHeight']),
                            evaluation_domain='old_heldout',GT_selection='SoccerNet_player_keeper_mark1'))
    require(manifest['status']=='complete_18_sources_not_training_authorized','共享预测未完整')
    for src in manifest['sources']:
        if src['domain']!='real':continue
        require(src['sequence'] in EXTERNAL and src['role']=='external_validation_only'
                and src['counts']['frames']==EXTERNAL[src['sequence']] and src['new_R_training_exposure']==0,
                '只允许两场已登记验证比赛')
        sources.append(dict(src,frames=EXTERNAL[src['sequence']],width=1280,height=720,fps=25,
            evaluation_domain='external_validation',GT_selection='SportsMOT_all_player_mark1_no_ID_remap'))
    require(len(sources)==5 and {s['sequence'] for s in sources}==set(OLD)|set(EXTERNAL),'五比赛scope必须完整')
    return {s['sequence']:s for s in sources}


def validate_frame(frame,sources):
    source=sources.get(frame.get('sequence'))
    require(source is not None and frame['game']==source['game'] and frame['fps']==25
        and type(frame['frame_index']) is int and 0<=frame['frame_index']<source['frames']
        and frame['frame_number']==frame['frame_index']+1
        and abs(frame['timestamp_sec']-frame['frame_index']/25)<1e-9
        and (frame['width'],frame['height'])==(source['width'],source['height']), 'v10实际帧/比赛/时序/尺寸不符')
    return True


def scoped_tracker(old_bundle,sources):
    """只替换旧750帧/三比赛守卫，原sequence/game原值进入所有数值。"""
    path=Path(old_bundle)/'python/src/grf_ue_bridge/learned_association_tracker_v8.py'
    require(sha(path)==TRACKER_SHA,'冻结tracker数值SHA不同')
    tree=ast.parse(path.read_text(encoding='utf-8'));original=deepcopy(tree)
    function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='update_frame')
    guards=[n for n in function.body if isinstance(n,ast.If) and any(isinstance(k,ast.Name) and k.id=='SCOPE' for k in ast.walk(n.test))]
    require(len(guards)==1,'原帧域守卫结构改变')
    guard=guards[0];index=function.body.index(guard);original_guard=ast.dump(guard,include_attributes=False)
    replacement=ast.parse('if not _v10_validate_frame(frame, _v10_sources):\n    raise ValueError("v10未登记实际帧")').body[0]
    function.body[index]=replacement
    # 除该守卫外，整棵AST必须相同；不改候选、阈值、代价、分配或历史状态。
    old_function=next(n for n in ast.walk(original) if isinstance(n,ast.FunctionDef) and n.name=='update_frame')
    old_function.body[index]=deepcopy(replacement)
    require(ast.dump(tree,include_attributes=False)==ast.dump(original,include_attributes=False),'scope以外数值不得改变')
    ast.fix_missing_locations(tree)
    module=types.ModuleType('grf_ue_bridge.v10_explicit_scope');module.__package__='grf_ue_bridge'
    module.__file__=str(path);module._v10_validate_frame=validate_frame;module._v10_sources=sources
    sys.modules[module.__name__]=module;exec(compile(tree,str(path),'exec'),module.__dict__)
    return module.tracker_class(),dict(original_tracker_sha256=TRACKER_SHA,modified_AST_nodes='one_frame_scope_guard_only',
        original_guard_AST_sha256=hashlib.sha256(original_guard.encode()).hexdigest(),
        runtime_AST_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),
        sequence_or_game_alias_used=False,numerical_AST_unchanged=True)


def load_gt(source):
    """仅供标签/评价/断档注册，不由tracker调用；ID0原值保留。"""
    players=None
    if source['sequence'] in OLD:
        info=configparser.ConfigParser();info.read(checked(source['gameinfo']),encoding='utf-8-sig')
        require('game'+info['Sequence']['gameID']==source['game'],'旧比赛gameinfo不符')
        players={int(k.split('_')[-1]) for k,v in info['Sequence'].items() if k.startswith('trackletid_')
                 and (v.strip().lower().startswith('player ') or v.strip().lower().startswith('goalkeeper'))}
        require(players,'旧比赛球员roster缺失');ref=source['gt']
    else:
        require(source['sequence'] in EXTERNAL,'禁止替换新比赛');ref=source['gt_reference']
    gt=defaultdict(list);text=[];seen=set()
    from math import isfinite
    for line in checked(ref).read_text(encoding='utf-8-sig').splitlines():
        a=line.split(',');frame,identity=int(a[0]),int(a[1]);box=list(map(float,a[2:6]))
        if not 1<=frame<=source['frames'] or (players is not None and identity not in players) or int(float(a[6]))!=1:continue
        require(identity>=0 and len(box)==4 and all(isfinite(v) for v in box) and min(box[2:])>0
                and (frame,identity) not in seen,'GT非法/同帧重复身份，不静默删除')
        seen.add((frame,identity));gt[frame].append(dict(gt_id=str(identity),bbox_xywh_px=box))
        text.append(','.join(a[:6]+['1','1','1']))
    return dict(gt),text


def validate_config(config):
    cfg=read(config)
    require(cfg['schema']=='v10_independent_tracking_protocol_v1' and cfg['tracking_authorized'] is True
        and cfg['approved_by']=='root' and cfg['test116187_sealed'] is True and Path(cfg['bundle'])==ROOT,
        '独立v10追踪身份/准入缺失')
    runtime,train,numeric,base,old=training(checked(cfg['training_protocol']))
    runtime.storage().physical_child(ROOT,R/'code')
    for entry in read(checked(cfg['bundle_manifest']))['files']:require(sha(ROOT/entry['path'])==entry['sha256'],'新追踪bundle字节改变')
    require(read(checked(cfg['training_exit']))['status']=='complete54_and_actual_training_processes_exited','训练完整退出链缺失')
    require(read(checked(cfg['registry']))['status']=='complete_five_matches_gap_registry_before_tracking','五场断档分母未先登记')
    expected=sources_from(train,read(checked(train['prediction_manifest'])))
    require(cfg['sources']==expected,'五比赛缓存/GT引用改变')
    return cfg,runtime,train,numeric,base,old


def model_for_job(cfg,runtime,train,numeric,base,old,job):
    import torch
    if job['kind']=='PT':return None,None,None,True
    run=Path(job['training_run']);fold,seed,method=(job[k] for k in ('fold','seed','method'))
    if job['kind']=='new_RS':
        _,_,model,adapter,binding=runtime.complete_model(checked(cfg['training_protocol']),run)
        require(all(binding[k]==job[k] for k in ('fold','seed','method','pool')),'实际模型/任务不符')
    else:
        require(job['kind']=='pure_R','未知模型来源')
        ref=train['reference_R'][method][fold][str(seed)];checked(ref['checkpoint']);checked(ref['training_receipt'])
        require(Path(ref['checkpoint']['path']).parent==run,'纯R参考目录不符')
        if method=='motion':
            old8=read(checked(train['v8_protocol']))
            old8manifest=read(checked(old8['bundle_manifest']))
            entry=next(e for e in old8manifest['files'] if e['path']=='tools/research_ops/v8_track.py')
            path=Path(old8['bundle'])/entry['path'];require(sha(path)==entry['sha256'],'原v8检查点加载器改变')
            module=load_file('v10_reference_v8_track',path)
            model,adapter,binding=module.load_complete(run,old8,train['v8_protocol']['sha256'],fold)
            require(binding['arm']=='motion_R','只引用强motion纯R')
        else:
            module=load_file('v10_reference_v9_track',Path(old['bundle'])/'tools/research_ops/v9_track.py')
            model,adapter,binding=module.complete_model(checked(train['v9_protocol']),run,fold)
            require(binding['variant']==method and binding['regime']=='R','纯R方法身份不同')
        require(binding['seed']==seed,'纯R初始化seed不同')
    return model,adapter,binding,method!='motion'


def tracking_matrix(train,control):
    jobs=[]
    for seq in list(OLD)+list(EXTERNAL):
        for mode in ('PT_bbox','PT_static_pose'):jobs.append(dict(kind='PT',mode=mode,sequence=seq))
    for job in train['training_matrix']:
        run=Path(control)/'runs'/job['fold']/str(job['seed'])/job['pool']/job['method']/'training'
        for seq in [next(s for s,f in OLD.items() if f==job['fold'])]+list(EXTERNAL):
            jobs.append(dict(job,kind='new_RS',mode='learned',sequence=seq,training_run=str(run)))
    for method in ('motion','motion_residual','gated'):
        for fold in ('game4','game6','game9'):
            for seed in (20261024,20261025,20261026):
                run=Path(train['reference_R'][method][fold][str(seed)]['checkpoint']['path']).parent
                for seq in [next(s for s,f in OLD.items() if f==fold)]+list(EXTERNAL):
                    jobs.append(dict(kind='pure_R',mode='learned',sequence=seq,method=method,fold=fold,seed=seed,training_run=str(run)))
    require(len(jobs)==253,'必须253项五比赛完整对照，不筛臂')
    for job in jobs:job['job_id']=hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
    require(len({j['job_id'] for j in jobs})==253,'任务ID冲突')
    return jobs
