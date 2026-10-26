"""固定权重残差幅度单因素对照：0.5→2.0，同容量motion控制，零优化更新。"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from statistics import mean
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[2]
R=Path('D:/projects/FutsalMOT_Research')
EXP=R/'pose/pose_mechanism_a01/amplitude_probe_a01'
PARAMETERS=dict(original_bound=.5,target_bound=2.,optimizer_updates=0,device='cpu',dtype='float32',
                changed_factor='residual_amplitude_only',methods=['gated','motion_residual'],select_best=False)


def require(ok,message):
    if not ok:raise ValueError(message)


def safe(path):
    import re
    p=Path(path)
    require(not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'封存测试禁止读取')
    return p


def read(path):return json.loads(safe(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def ref(path):return dict(path=str(path),sha256=sha(path))
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def checked(value):
    p=safe(value['path']);require(p.is_file() and sha(p)==value['sha256'],'来源SHA变化：'+str(p));return p
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def matrix(old):
    jobs=[dict(original=j,target_bound=2.) for j in old['tracking_matrix'] if j['kind']=='new_RS' and j.get('method') in PARAMETERS['methods']]
    for job in jobs:job['job_id']=hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
    require(len(jobs)==108 and len({j['job_id'] for j in jobs})==108,'必须两方法×两池×三fold×三seed×三个评价序列')
    return jobs


def with_bound(original,bound):
    """逐式复用原两种forward，直接改变系数，避免用logit相减引入取消误差。"""
    import math
    import torch
    require(math.isfinite(bound) and bound in (.5,2.),'仅原0.5和登记2.0，不搜索幅度')
    require(original.variant in PARAMETERS['methods'],'只允许两个登记原模型')
    class Probe(torch.nn.Module):
        def __init__(self):super().__init__();self.original=original
        def forward(self,x):
            if x.ndim!=2 or x.shape[1]!=195:raise ValueError('194特征加原可观测gate')
            model=self.original;motion=torch.cat([x[:,:24],torch.zeros_like(x[:,24:194])],dim=1);base=model.base(motion)
            z=torch.cat([x[:,:24],torch.zeros_like(x[:,24:170])],dim=1) if model.variant=='motion_residual' else x[:,24:194]
            residual=bound*torch.tanh(model.residual(z));gate=x[:,194:195] if model.variant=='gated' else 1.
            return base+gate*residual
    return Probe().eval()


def context(config,proof=False):
    cfg=read(config)
    require(cfg['schema']=='residual_amplitude_probe_protocol_v1' and cfg['approved_by']=='root' and cfg['diagnostic_authorized'] is True
        and cfg['training_authorized'] is False and cfg['test_sealed'] is True and cfg['parameters']==PARAMETERS,'独立幅度准入缺失')
    require(Path(cfg['bundle'])==ROOT and checked(cfg['entry'])==Path(__file__).resolve() and ROOT.parent==R/'code','只执行已冻结单文件bundle')
    source_config=checked(cfg['source_mechanism_protocol']);source=read(source_config);bundle=Path(source['bundle'])
    for entry in read(checked(source['bundle_manifest']))['files']:require(sha(bundle/entry['path'])==entry['sha256'],'机制来源数值源码变化')
    core=load('amplitude_frozen_mechanism_core',bundle/'tools/research_ops/pose_mechanism_core.py')
    _,rt,old,runtime,train,numeric,base,numbers=core.validate(source_config)
    complete=read(checked(cfg['mechanism_completion']))
    require(complete['status']=='complete162_diagnostics_sources_results_and_process_exit_verified' and complete['optimizer_updates']==0,'前阶段未闭合')
    require(cfg['jobs']==matrix(old) and numbers['parameters']['delta_logit_bound']==.5,'矩阵或原幅度变化')
    runtime.storage().physical_child(ROOT,R/'code')
    if not proof:
        evidence=read(checked(cfg['numeric_proof']))
        require(evidence['status']=='complete_two_actual750_original_bound_exact' and evidence['probe_entry_sha256']==sha(__file__),'实际两模型750帧等价尚未闭合')
    return cfg,core,rt,old,runtime,train,numeric,base,numbers


def original_run(old,job):return Path(old['training_control']).parent/'tracking_control_a01/runs'/job['job_id']


def execute_tracking(ctx,job,output,bound):
    cfg,core,rt,old,runtime,train,numeric,base,numbers=ctx
    import torch
    torch.set_num_threads(1)
    source=old['sources'][job['original']['sequence']];model,adapter,binding,_=rt.model_for_job(old,runtime,train,numeric,base,numbers,job['original'])
    before={k:v.clone() for k,v in model.state_dict().items()}
    cls,scope=rt.scoped_tracker(numbers['bundle'],old['sources']);tracker=cls(model=with_bound(model,bound),normalizer=adapter,use_pose=True,
        mode='learned',pose_source_sha256=train['pose_checkpoint_sha256'],fixed_detection_sha256=source['cache']['sha256'])
    output=runtime.storage().physical_child(output,EXP);require(not output.exists(),'追踪partial不覆盖');output.mkdir(parents=True)
    frames=core.rows(core.checked(source['cache']));text=[]
    for frame in frames:
        for row in tracker.update_frame(frame):
            x1,y1,x2,y2,identity,score=row[:6];text.append(','.join(map(str,[frame['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
    require(all(torch.equal(before[k],v) for k,v in model.state_dict().items()),'固定权重发生变化')
    (output/'data').mkdir();mot=output/'data'/(source['sequence']+'.txt');mot.write_text('\n'.join(text)+('\n' if text else ''),encoding='utf-8')
    value=dict(schema='residual_amplitude_fixed_tracking_v1',status='complete',job=job,applied_bound=bound,sequence=source['sequence'],frames=len(frames),
        mot_sha256=sha(mot),tracked_rows=len(text),audit=tracker.audit,binding=binding,numerical_scope=scope,weights_unchanged=True,GT_read=False,
        optimizer_updates=0,GPU_used=False,test_read=False)
    return value


def proof(config,output):
    ctx=context(config,proof=True);cfg,core,rt,old,runtime,*_=ctx;output=runtime.storage().physical_child(output,EXP)
    require(not output.exists(),'等价证明partial不覆盖');output.mkdir(parents=True);records=[]
    for method in PARAMETERS['methods']:
        job=next(j for j in cfg['jobs'] if j['original']['method']==method and j['original']['sequence']=='SNMOT-060'
            and j['original']['pool']=='balanced' and j['original']['seed']==20261024)
        value=execute_tracking(ctx,job,output/method,.5);previous=read(original_run(old,job['original'])/'tracking/receipt.json')
        require(value['mot_sha256']==previous['mot_sha256'] and value['audit']==previous['audit'],'原0.5逐式包装未真实复现原MOT/audit')
        records.append(dict(method=method,original_receipt=ref(original_run(old,job['original'])/'tracking/receipt.json'),actual=value))
    result=dict(status='complete_two_actual750_original_bound_exact',records=records,probe_entry_sha256=sha(__file__),optimizer_updates=0)
    with (output/'receipt.json').open('x',encoding='utf-8') as f:f.write(canonical(result)+'\n')
    return dict(status=result['status'],methods=2,frames_each=750,optimizer_updates=0)


def track(config,job_id,output):
    ctx=context(config);job=next(j for j in ctx[0]['jobs'] if j['job_id']==job_id);value=execute_tracking(ctx,job,output,2.)
    value['protocol']=ref(config)
    with (Path(output)/'receipt.json').open('x',encoding='utf-8') as f:f.write(canonical(value)+'\n')
    return dict(status=value['status'],job_id=job_id,tracked_rows=value['tracked_rows'])


def metric(config,tracking,output):
    cfg,core,rt,old,runtime,train,numeric,base,numbers=context(config);tracking=Path(tracking);receipt=read(tracking/'receipt.json')
    require(receipt['schema']=='residual_amplitude_fixed_tracking_v1' and receipt['status']=='complete' and receipt['protocol']==ref(config)
        and receipt['applied_bound']==2. and receipt['GT_read'] is False,'幅度追踪独立身份不符')
    source=old['sources'][receipt['sequence']];mot=tracking/'data'/(source['sequence']+'.txt');require(sha(mot)==receipt['mot_sha256'],'MOT变化')
    engine=rt.load_file('amplitude_frozen_metric',Path(old['bundle'])/'tools/research_ops/v10_metric.py')
    predictions,count=engine.prediction_rows(mot.read_text(encoding='utf-8'),source['frames']);require(count==receipt['tracked_rows'],'不得过滤预测')
    _,GT=rt.load_gt(source);output=runtime.storage().physical_child(output,EXP);require(not output.exists(),'评价partial不覆盖');output.mkdir(parents=True)
    raw,sources=engine.trackeval_numeric(source,GT,tracking,output);summary={}
    for name,classes in raw.items():
        value=classes['pedestrian'];engine.validate_count(name,value['Count'],count,len(GT),source['sequence'],source['frames']);metrics={}
        for group,keys in [('HOTA',('HOTA','AssA','DetA')),('Identity',('IDF1',)),('CLEAR',('MOTA',))]:
            for k in keys:
                x=value[group][k];metrics[k]=100*(sum(x)/len(x) if isinstance(x,list) else float(x))
        summary[name]=dict(metrics_percent=metrics,IDSW_count=int(value['CLEAR']['IDSW']))
    registry=read(core.checked(old['registry']));gap=engine.gap_numeric(numbers);events=[e for e in registry['events'] if e['sequence']==source['sequence']]
    recovery=gap.evaluate_events(events,registry['sequences'][source['sequence']]['endpoint_GT'],predictions)
    result=dict(schema='residual_amplitude_metric_v1',status='complete',protocol=ref(config),job=receipt['job'],summary=summary,recovery=recovery,
        raw_results=raw,numerical_sources=sources,GT_used_only_for_metric=True,predictions_GT_filtered=False,test_read=False,optimizer_updates=0,
        tracking_receipt=ref(tracking/'receipt.json'))
    with (output/'report.json').open('x',encoding='utf-8') as f:f.write(canonical(result)+'\n')
    return dict(status='complete',job_id=receipt['job']['job_id'])


def analyze(config,control,output):
    cfg,core,rt,old,runtime,*_=context(config);control=Path(control);state=read(control/'driver_state.json')
    require(len(state['completed'])==108,'全部108项未齐');units=[];metrics_names=('AssA','HOTA','IDF1','DetA','MOTA')
    for job in cfg['jobs']:
        j=job['original'];seq=j['sequence'];folder=control/'runs'/job['job_id'];current=read(folder/'metric/report.json')
        require(current['status']=='complete' and current['protocol']==ref(config) and current['job']==job,'评价身份不符')
        previous=read(original_run(old,j)/'metric/report.json');now=current['summary'][seq]['metrics_percent'];before=previous['summary'][seq]['metrics_percent']
        strong=next(x for x in old['tracking_matrix'] if x['kind']=='new_RS' and x.get('method')=='motion' and all(x.get(k)==j[k] for k in ('pool','fold','seed','sequence')))
        strong_metrics=read(original_run(old,strong)/'metric/report.json')['summary'][seq]['metrics_percent']
        units.append(dict(job=job,metrics=now,original_metrics=before,delta_vs_original_pp={k:now[k]-before[k] for k in metrics_names},
            delta_vs_strong_motion_pp={k:now[k]-strong_metrics[k] for k in metrics_names},recovery=current['recovery']['overall'],
            original_recovery=previous['recovery']['overall'],metric=ref(folder/'metric/report.json')))
    aggregates={}
    for pool in ('balanced','hard_enriched'):
        for domain,sequences in (('external',rt.EXTERNAL),('old_heldout',rt.OLD)):
            for method in PARAMETERS['methods']:
                rows=[u for u in units if u['job']['original']['pool']==pool and u['job']['original']['method']==method and u['job']['original']['sequence'] in sequences]
                require(len(rows)==(18 if domain=='external' else 9),'每fold/seed单元缺失')
                aggregates[f'{pool}/{domain}/{method}']=dict(units=len(rows),delta_vs_original_pp={k:mean(u['delta_vs_original_pp'][k] for u in rows) for k in metrics_names},
                    delta_vs_strong_motion_pp={k:mean(u['delta_vs_strong_motion_pp'][k] for u in rows) for k in metrics_names},
                    seed_AssA_delta={str(s):mean(u['delta_vs_original_pp']['AssA'] for u in rows if u['job']['original']['seed']==s) for s in (20261024,20261025,20261026)},
                    match_AssA_delta={seq:mean(u['delta_vs_original_pp']['AssA'] for u in rows if u['job']['original']['sequence']==seq) for seq in sorted({u['job']['original']['sequence'] for u in rows})},
                    negative_AssA_cells=sum(u['delta_vs_original_pp']['AssA']<0 for u in rows))
    paired=[]
    for pose in [u for u in units if u['job']['original']['method']=='gated']:
        j=pose['job']['original'];motion=next(u for u in units if u['job']['original']['method']=='motion_residual' and all(u['job']['original'][k]==j[k] for k in ('pool','fold','seed','sequence')))
        paired.append(dict(pool=j['pool'],fold=j['fold'],seed=j['seed'],sequence=j['sequence'],
            difference_in_differences_pp={k:pose['delta_vs_original_pp'][k]-motion['delta_vs_original_pp'][k] for k in metrics_names},
            amplified_Pose_minus_amplified_capacity_motion_pp={k:pose['metrics'][k]-motion['metrics'][k] for k in metrics_names}))
    output=runtime.storage().physical_child(output,EXP);require(not output.exists(),'分析partial不覆盖');output.mkdir(parents=True)
    result=dict(schema='residual_amplitude_probe_analysis_v1',status='complete108_amplitude_probe_analysis',protocol=ref(config),units=units,aggregates=aggregates,
        all54_matched_capacity_comparisons=paired,optimizer_updates=0,test_read=False,
        limitations=['postdiagnosis single-factor exploration, not new training or a new independent test',
            'same frozen weights and gates; changing amplitude can also change probability calibration and assignment',
            'no new clean RS-minus-R causal claim: existing R-only references did not receive this intervention',
            'all five matches observed; folds/seeds are not independent matches; original v10 gates/results unchanged'])
    with (output/'report.json').open('x',encoding='utf-8') as f:f.write(canonical(result)+'\n')
    flat=[]
    for u in units:
        j=u['job']['original'];flat.append(dict(**{k:j[k] for k in ('pool','fold','seed','sequence','method')},**{'delta_'+k:u['delta_vs_original_pp'][k] for k in metrics_names}))
    with (output/'all108_units.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    return dict(status=result['status'],aggregates=aggregates)


def preflight(config,output):
    ctx=context(config);cfg,core,rt,old,runtime,*_=ctx
    from v8_control import process_snapshot,own_launcher_chain
    processes=process_snapshot();own=own_launcher_chain(processes,os.getpid(),Path(__file__).resolve())
    blocked=[p for p in processes if p['ProcessId'] not in own and (p['Name'].lower().startswith('unrealeditor') or
        any(x in (p.get('CommandLine') or '') for x in ('residual_amplitude_probe.py','pose_mechanism_control.py','v10_training_control.py','v10_tracking_control.py')))]
    require(not blocked,'已有活动实验，不重复启动：'+str(blocked));output=runtime.storage().physical_child(output,EXP);require(not output.exists(),'控制器partial不覆盖')
    return ctx,dict(status='readonly108_amplitude_probe_preflight',jobs=108,optimizer_updates=0,GPU=False,test_read=False,own_launcher_chain=sorted(own))


def control(config,output):
    ctx,flight=preflight(config,output);cfg,core,rt,old,runtime,*_=ctx;output=Path(output);output.mkdir(parents=True)
    journal=core.load('amplitude_frozen_atomic',runtime.ROOT/'tools/research_ops/training_journal.py');journal.atomic(output/'preflight.json',flight)
    state=dict(schema='residual_amplitude_control_v1',status='starting',pid=os.getpid(),completed=[],active=None)
    def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();journal.atomic(output/'driver_state.json',state)
    def child(tag,mode,args):
        require(not (output/'STOP').exists(),'STOP边界，保留不重放');logs=output/'logs';logs.mkdir(exist_ok=True)
        with (logs/(tag+'.stdout.txt')).open('x',encoding='utf-8') as stdout,(logs/(tag+'.stderr.txt')).open('x',encoding='utf-8') as stderr:
            command=[sys.executable,'-B',__file__,'--config',str(config),'--mode',mode,'--execute',*map(str,args)]
            p=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=os.environ.copy());state['active']=dict(pid=p.pid,tag=tag,command=command);save();code=p.wait()
        require(code==0,tag+'真实失败，保留partial');state['active']=None;save()
    save()
    try:
        for job in cfg['jobs']:
            state['status']='CPU_amplitude_probe';save();folder=output/'runs'/job['job_id']
            child(job['job_id']+'_track','track',['--job-id',job['job_id'],'--output',folder/'tracking'])
            child(job['job_id']+'_metric','metric',['--tracking',folder/'tracking','--output',folder/'metric'])
            state['completed'].append(dict(job=job,tracking_receipt=ref(folder/'tracking/receipt.json'),metric_receipt=ref(folder/'metric/report.json')));save()
        state['status']='complete108_wait_analysis';save();child('final_analysis','analyze',['--control',output,'--output',output/'analysis_a01'])
        require(read(output/'analysis_a01/report.json')['status']=='complete108_amplitude_probe_analysis','最终分析缺失')
        state['status']='complete108_amplitude_probe_tracking_analysis';save()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());save();raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('control','track','metric','analyze','proof'),default='control');p.add_argument('--job-id');p.add_argument('--tracking',type=Path);p.add_argument('--control',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies',YOLO_AUTOINSTALL='false')
    if not a.execute:print(canonical(preflight(a.config,a.output)[1]))
    elif a.mode=='control':control(a.config,a.output)
    else:print(canonical({'proof':lambda:proof(a.config,a.output),'track':lambda:track(a.config,a.job_id,a.output),
        'metric':lambda:metric(a.config,a.tracking,a.output),'analyze':lambda:analyze(a.config,a.control,a.output)}[a.mode]()))
