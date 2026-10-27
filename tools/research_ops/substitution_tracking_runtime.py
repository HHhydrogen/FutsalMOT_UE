"""七比赛A/B/C独立追踪准入与三类模型加载；复用冻结v10数值工具。"""
import configparser
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/real_substitution_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);METHODS=('motion','gated');GROUPS=('A','B','C')
MATCHES=('v_1yHWGw8DH4A_c029','v_HdiyOtliFiw_c003','v_ITo3sCnpw_k_c007','v_dw7LOz17Omg_c053',
    'v_gQNyhv8y0QY_c003','v_i2_L4qquVg0_c006','v_iIxMOsCGH58_c013')
TRACKING_SHA='f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1'
ANALYSIS_SHA='afee40ca64dc44a12b5b4c684b313d02831ad0bdcbd5d5201c4f824ffabefc0c'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def safe(p):
    p=Path(p).absolute();require(not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'最终测试封存禁止读取');return p
def read(p):return json.loads(safe(p).read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(x) for x in safe(p).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(p):return hashlib.sha256(safe(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def checked(v):
    p=safe(v['path']);require(p.is_file() and sha(p)==v['sha256'],'来源绑定改变：'+str(p));return p
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def tracking_matrix():
    jobs=[dict(kind='PT',mode=mode,sequence=seq) for seq in MATCHES for mode in ('PT_bbox','PT_static_pose')]
    for group in GROUPS:
        for method in METHODS:
            for fold in FOLDS:
                for seed in SEEDS:
                    for seq in MATCHES:jobs.append(dict(kind='learned',mode='learned',group=group,method=method,fold=fold,seed=seed,sequence=seq))
    for job in jobs:job['job_id']=hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
    require(len(jobs)==392 and len({j['job_id'] for j in jobs})==392,'固定392任务矩阵不可缺失/重复');return jobs

def sources_from(manifest,registry):
    require(manifest.get('schema')=='seven_match_shared_PT_prediction_manifest_v1'
        and manifest.get('status')=='complete7_sources4790_frames_not_tracking_authorized'
        and manifest.get('new_optimizer_updates')==0 and manifest.get('new_R_training_exposure')==0
        and manifest.get('GT_used_for_predictions') is False and manifest.get('test_read') is False,'完整七比赛同PT预测尚未齐')
    by={s['sequence']:s for s in manifest['sources']};ident={s['sequence']:s for s in registry['sources']}
    require(len(by)==len(manifest['sources'])==len(ident)==7 and set(by)==set(ident)==set(MATCHES),'七比赛范围改变')
    result={}
    for seq in MATCHES:
        s=by[seq];i=ident[seq];count=i['full_clip_frames']
        require(s['counts']['frames']==s['last_frame']+1==count and s['first_frame']==0 and s['video_id']==i['video_id']
            and s['role']=='external_validation_only' and s['fps']==25 and s['game']=='external:'+i['video_id']
            and (s['width'],s['height'])==(1280,720) and s['GT_used_for_predictions'] is False,'实际比赛/尺寸/帧数/预测角色不同')
        result[seq]=dict(s,frames=count,evaluation_domain='new_seven_match_primary',GT_selection='SportsMOT_all_player_mark1_ID0_retained')
    require(sum(s['frames'] for s in result.values())==4790,'总帧数不符');return result

def dependencies(source_tracking):
    require(source_tracking['sha256']==TRACKING_SHA,'旧追踪协议身份不同')
    source=read(checked(source_tracking));bundle=Path(source['bundle']);require(bundle.parent==R/'code','旧执行目录不在研究根')
    for e in read(checked(source['bundle_manifest']))['files']:require(sha(bundle/e['path'])==e['sha256'],'旧追踪数值工具变化')
    # 原模块只提供已验纯函数；从实际bundle导入，不能复制到新ROOT后漂移。
    old_rt=module('v10_tracking_runtime',bundle/'tools/research_ops/v10_tracking_runtime.py')
    sys.path.insert(0,str(bundle/'tools/research_ops'))
    old_metric=module('substitution_frozen_v10_metric',bundle/'tools/research_ops/v10_metric.py')
    training,train,numeric,base,old=old_rt.training(checked(source['training_protocol']))
    require(old_metric.rt is old_rt,'评价模块误导入非冻结runtime')
    return source,old_rt,old_metric,training,train,numeric,base,old

def C_runtime(protocol):
    c=read(protocol);bundle=Path(c['bundle']);require(bundle.parent==R/'code','C实际执行bundle不同')
    entry=next(x for x in read(checked(c['bundle_manifest']))['files'] if x['path']=='tools/research_ops/substitution_C_runtime.py')
    require(sha(bundle/entry['path'])==entry['sha256'],'C独立加载器变化')
    runtime=module('substitution_frozen_C_runtime',bundle/entry['path']);runtime.protocol(protocol);return runtime

def validate_config(config,registry_required=True):
    c=read(config);require(c.get('schema')=='seven_match_ABC_tracking_protocol_v1' and c.get('tracking_authorized') is True
        and c.get('approved_by')=='root' and c.get('test_sealed') is True and c.get('formal_equivalence_or_noninferiority') is False
        and Path(c['bundle'])==ROOT and ROOT.parent==R/'code' and c.get('tracking_matrix')==tracking_matrix(),'缺独立七比赛392项准入')
    for e in read(checked(c['bundle_manifest']))['files']:require(sha(ROOT/e['path'])==e['sha256'],'新执行源码改变')
    dep=dependencies(c['source_tracking_config']);_,old_rt,_,training,train,_,_,_=dep
    training.storage().physical_child(ROOT,R/'code')
    cr=C_runtime(checked(c['C_protocol']));cc=cr.protocol(c['C_protocol']['path'])
    require(cc['source_v10_protocol']==dep[0]['training_protocol'],'A/B与C必须来源同一v10训练协议')
    budget=read(checked(c['C_budget']));require(budget['status']=='complete18_C_actual_budget_full_records_and_exit_verified'
        and budget['complete_checkpoints_read_back']==378 and budget['training_processes_absent'] is True,'C预算/退出缺失')
    C_done=read(checked(c['C_complete']));require(C_done['status']=='complete18_C_training_actual_budget_records_exit_verified_no_new_metrics'
        and C_done['protocol']==c['C_protocol'] and C_done['budget']==c['C_budget'] and C_done['training_processes_absent'] is True,'C阶段完成链不同')
    complete=read(checked(c['prediction_completion']))
    require(complete['status']=='complete7_shared_predictions_verified_processes_absent'
        and complete['manifest']==c['prediction_manifest'] and complete['prediction_processes_absent'] is True,'共享预测/实际退出未闭合')
    manifest=read(checked(c['prediction_manifest']));require(manifest['matches']==c['matches'] and manifest['analysis_plan']==c['analysis_plan'],'预测与事前范围/分析不同')
    require(manifest['pose_checkpoint']['sha256']==train['pose_checkpoint_sha256'],'共享Pose与A/B/C原感知来源不同')
    require(c['sources']==sources_from(manifest,read(checked(c['matches']))),'实际缓存/GT与冻结源不同')
    checked(c['analysis_plan']);checked(c['source_numeric_validation'])
    plan=read(c['analysis_plan']['path']);require(c['analysis_plan']['sha256']==ANALYSIS_SHA
        and plan['decision_mode']=='paired_effects_and_CI_only' and plan['contrasts']==['B-A','C-A','B-C']
        and plan['equivalence_margin'] is None and plan['noninferiority_margin'] is None,'不得改事前区间方案或增设判定')
    gate=read(c['source_numeric_validation']['path'])
    require(gate['status']=='complete_original750_three_modes_scope_equivalent'
        and all(x['all_rows_and_audit_equal'] for x in gate['checks']),'原引擎数值门禁缺失')
    if registry_required:
        # 追踪进程仅加载无GT坐标的登记收据；完整endpoint_GT只由评价进程读取。
        r=read(checked(c['registry_receipt']));require(r['status']=='complete7_gap_registry_before_tracking'
            and r['registry']==c['registry'] and r['sources']==c['sources']
            and r['tracking_results_read'] is False,'结果前固定断档分母未登记')
    return c,dep,cr,cc

def load_model(c,dep,cr,cc,job):
    _,old_rt,metric,training,train,numeric,base,old=dep
    if job['kind']=='PT':return None,None,None,True
    group,method,fold,seed=(job[k] for k in ('group','method','fold','seed'))
    require(group in GROUPS and method in METHODS and fold in FOLDS and seed in SEEDS,'模型分组/种子未登记')
    if group=='C':
        control=read(checked(c['C_complete']))['controller_state'];state=read(checked(control))
        item=next(x for x in state['completed_train'] if (x['fold'],x['seed'],x['method'])==(fold,seed,method))
        _,_,model,adapter,binding=cr.complete_model(checked(c['C_protocol']),item['path'])
        require(binding['regime']=='C4000R' and binding['method']==method and binding['fold']==fold and binding['seed']==seed,'C实际模型身份不同')
        return model,adapter,binding,method!='motion'
    if group=='A':
        run=Path(train['reference_R'][method][fold][str(seed)]['checkpoint']['path']).parent
        prior=dict(kind='pure_R',mode='learned',training_run=str(run),method=method,fold=fold,seed=seed)
    else:
        source=cc['reference_B'][method][fold][str(seed)];run=checked(source['training_receipt']).parent
        checked(source['checkpoint']);checked(source['training_complete'])
        prior=dict(kind='new_RS',mode='learned',training_run=str(run),method=method,fold=fold,seed=seed,pool='balanced')
    return old_rt.model_for_job(dict(training_protocol=dep[0]['training_protocol']),training,train,numeric,base,old,prior)

def load_gt(source):
    """只供评价/事前断档登记；tracker调用路径不调用此函数。"""
    require(source['sequence'] in MATCHES and source['role']=='external_validation_only','GT来源不得扩大')
    gt=defaultdict(list);text=[];seen=set();p=checked(source['gt'])
    for line in p.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():continue
        a=line.split(',');require(len(a)>=9,'GT列数不足')
        frame,identity=int(a[0]),int(a[1]);box=list(map(float,a[2:6]))
        require(1<=frame<=source['frames'] and identity>=0 and int(float(a[6]))==1
            and all(math.isfinite(x) for x in box) and min(box[2:])>0 and (frame,identity) not in seen,'GT帧/ID/mark/框非法，不静默过滤')
        seen.add((frame,identity));gt[frame].append(dict(gt_id=str(identity),bbox_xywh_px=box));text.append(','.join(a[:6]+['1','1','1']))
    return dict(gt),text

def gap_numeric(dep):
    old=dep[-1];return module('substitution_original_gap_numeric',Path(old['bundle'])/'tools/research_ops/v8_gap_recovery.py')
