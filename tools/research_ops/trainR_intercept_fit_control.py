"""固定十八模型的训练R截距准入/拟合；只增加单标量，不启动追踪。"""
import argparse
from collections import deque
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import pickle
import random
import re
import subprocess
import sys
import time
import traceback

R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/trainR_intercept_calibration_a01'
ROOT=Path(__file__).resolve().parents[2]
SERVICE=R/'code/70a399c65ff8cf7f2ef7090a0739ab161ff5b59b338c419f54e0c6c1238645f7/tools/research_ops/tracking_policy_ledger_control.py'
SERVICE_SHA='7cb703e6e38a8d285ca397190647573b051e168ac8d3a5ffc9877d29f97599f6'
PROFILE=dict(analysis_workers=2,numeric_threads=1,reserve_RAM_bytes=8589934592,reserve_commit_bytes=6442450944,startup_estimate_bytes=268435456)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m
    previous=sys.dont_write_bytecode
    try:sys.dont_write_bytecode=True;spec.loader.exec_module(m)
    finally:sys.dont_write_bytecode=previous
    return m

if hashlib.sha256(SERVICE.read_bytes()).hexdigest()!=SERVICE_SHA:raise ValueError('已验worker生命周期源码改变')
base=load('intercept_existing_worker_service',SERVICE)
require,canonical,physical,sha,ref,checked,read,write_new=(base.require,base.canonical,base.physical,base.sha,base.ref,base.checked,base.read,base.write_new)

def dependencies():
    inputs=load('intercept_fit_inputs',ROOT/'tools/research_ops/trainR_intercept_inputs.py')
    runtime=load('intercept_fit_runtime',ROOT/'tools/research_ops/trainR_intercept_runtime.py')
    return inputs,runtime

def validate(path):
    cfg=read(path)
    require(cfg['schema']=='trainR_intercept_fit_protocol_v1' and cfg['approved_by']=='root'
        and cfg['test_sealed'] is True and cfg['execute_authorized'] is True,'校准独立授权/封存缺失')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code' and Path(cfg['output_root'])==EXP,'只执行独立最小bundle/范围')
    for e in read(checked(cfg['bundle_manifest']))['files']:require(sha(ROOT/e['path'])==e['sha256'],'冻结源码改变')
    inventory=read(checked(cfg['inventory']));inputs,runtime=dependencies()
    require(inventory['status']=='complete18_model_refs3_cleanR_pools180_baseline_refs_no_weight_or_pool_loaded'
        and len(inventory['models'])==18 and cfg['model_order']==[s['model_id'] for s in inventory['models']], '十八来源矩阵改变')
    require(cfg['parameters']==runtime.PARAMETERS and cfg['worker_profile']==PROFILE
        and cfg['formal_equivalence_or_noninferiority'] is False and cfg['validation_used_for_beta_selection'] is False,'不能调校准目标或验证选参数')
    if cfg['phase']=='fit':
        gate=read(checked(cfg['numeric_admission']))
        require(gate['status']=='complete6_models3_clean_R_inputs_FP32_intercept_numeric_admission'
            and gate['inventory']==cfg['inventory'] and gate['passed'] is True,'真实数值/来源准入未闭合')
    else:require(cfg['phase']=='numeric_admission','未知校准阶段')
    return cfg,inventory

def producers_absent():
    command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python|^UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',check=True)
    rows=json.loads(p.stdout) if p.stdout.strip() else [];rows=[rows] if isinstance(rows,dict) else rows
    own={os.getpid()};byid={v['ProcessId']:v for v in rows};node=byid.get(os.getpid())
    while node and node['ParentProcessId'] in byid:
        parent=byid[node['ParentProcessId']]
        if 'trainR_intercept_fit_control.py' not in (parent.get('CommandLine') or ''):break
        own.add(parent['ProcessId']);node=parent
    pattern=re.compile(r'(?:^|[\\/\s"\x27])(?:trainR_intercept_(?:fit_control|fit_job|tracking_control)|bounded_error_control|ocsort_(?:threshold|cached)_control|pose_velocity_tracking_control)[.]py(?=$|[\s"\x27])',re.I)
    blocked=[v for v in rows if v['ProcessId'] not in own and ((v.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(v.get('CommandLine') or ''))]
    require(not blocked,'研究生产者仍在，不重复启动：'+canonical(blocked))
    return dict(actual_CIM_checked=True,related_producers_absent=True,own_launcher_chain=sorted(own))

def environment(torch):
    import numpy
    return dict(python=sys.version,executable=sys.executable,torch=torch.__version__,numpy=numpy.__version__,device='cpu',
        torch_threads=torch.get_num_threads(),CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'),
        dtype='FP32_native_per_window',optimizer_updates=0,augmentation=False)

def rng(torch):
    import numpy
    return dict(Python=random.getstate(),NumPy=numpy.random.get_state(),TorchCPU=torch.get_rng_state(),CUDA=None,
        CUDA_reason='CPU_only_no_CUDA_initialization')

def model_digest(model):
    h=hashlib.sha256()
    for key,value in model.state_dict().items():h.update(key.encode());h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

def logits_from_output(output,count):
    require(tuple(output.shape) in ((count,), (count,1)), '原模型输出必须逐候选N或N1，不扩展批次或池化')
    values=output.detach().cpu().reshape(-1).tolist()
    require(len(values)==count and all(type(x) is float for x in values),'原FP32逐候选logit形状不同')
    return values

def numeric(path,cfg,inventory):
    producers_absent();out=EXP/'numeric_admission_a01';require(not out.exists(),'数值partial拒绝覆盖');out.mkdir()
    write_new(out/'intent.json',dict(protocol=ref(path),optimizer_updates=0,test_read=False))
    try:
        inputs,runtime=dependencies();import torch
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        records=[];calls=0
        for spec in inventory['models']:
            if spec['seed']!=20261024:continue
            prepared=inputs.prepare_clean_R_windows(cfg,spec);loaded=inputs.load_model(spec);model=loaded['model'];before=model_digest(model)
            models={b:runtime.wrap_intercept(model,b,torch) for b in (0.,.25,-.25)}
            count=0;postload_rng=torch.get_rng_state().clone()
            with torch.no_grad():
                for window in prepared['windows'][:16]:
                    if not window['features']:continue
                    x=torch.tensor(window['features'],dtype=torch.float32);original=model(x);count+=1
                    require(len(logits_from_output(original,len(window['labels'])))==len(window['labels']),'真实原N1日志不能扁平映射候选')
                    require(torch.equal(original,models[0.](x)),'真实beta0 forward非逐值相同')
                    for b in (.25,-.25):
                        shifted=models[b](x);expected=original+torch.tensor(b,dtype=torch.float32)
                        require(torch.equal(shifted,expected) and torch.equal(torch.sigmoid(shifted),torch.sigmoid(expected)),'手写偏置/sigmoid不同')
                        require(torch.equal(1-torch.sigmoid(shifted),1-torch.sigmoid(expected)),'原概率代价不同')
            require(before==model_digest(model) and torch.equal(postload_rng,torch.get_rng_state())
                and all(not p.requires_grad for p in model.parameters()),'准入改了权重/RNG或允许SGD')
            calls+=4*count
            records.append(dict(model_id=spec['model_id'],regime=spec['regime'],fold=spec['fold'],seed=spec['seed'],
                input_receipt=prepared['receipt'],loader_receipt=loaded['receipt'],model_digest_before=before,
                model_digest_after=model_digest(model),sample_windows=16,actual_nonempty_windows=count,actual_forward_calls=4*count,
                beta0_exact=True,manual_positive_negative_beta_exact=True,FP32_sigmoid_cost_exact=True,
                parameters_unchanged=True,postload_TorchCPU_RNG_unchanged=True))
        require(len(records)==6,'R/RS三fold真实准入必须齐全');inputs.clear_feature_cache();producers_absent()
        result=dict(schema='trainR_intercept_numeric_admission_v1',status='complete6_models3_clean_R_inputs_FP32_intercept_numeric_admission',
            passed=True,protocol=ref(path),inventory=cfg['inventory'],models=records,environment=environment(torch),
            diagnostic_window_evaluations=6*16*4,actual_nonempty_model_forward_calls=calls,
            SGD_updates=0,scalar_fits=0,new_tracking=0,validation_or_test_read=False,
            full_clean_pool_UID_games_labels_validated=True,GT_coordinates_read=False)
        write_new(out/'receipt.json',result);return dict(status=result['status'],receipt=ref(out/'receipt.json'),diagnostic_window_evaluations=384)
    except BaseException:
        write_new(out/'failed.json',dict(status='failed_numeric_partial_preserved',traceback=traceback.format_exc(),implicit_replay=False));raise

def fit_model(cfg,spec,out,inputs,runtime,torch):
    started=time.perf_counter();out=Path(out);require(not out.exists(),'拟合partial不能覆盖');out.mkdir()
    prepared=inputs.prepare_clean_R_windows(cfg,spec);loaded=inputs.load_model(spec);model=loaded['model'];model.eval()
    for p in model.parameters():p.requires_grad_(False)
    before=model_digest(model);r0=rng(torch);torch.save(r0,out/'RNG_before.pt')
    write_new(out/'environment.json',environment(torch));write_new(out/'source.json',dict(model_spec=spec,inventory=cfg['inventory'],protocol=ref(Path(cfg['_config_path']))))
    rows=[];calls=0;chain='0'*64
    with gzip.open(out/'windows.jsonl.gz','xt',encoding='utf-8') as stream,torch.no_grad():
        for window in prepared['windows']:
            if window['features']:
                logits=logits_from_output(model(torch.tensor(window['features'],dtype=torch.float32)),len(window['labels']));calls+=1
            else:logits=[]
            require(len(logits)==len(window['labels']) and all(type(x) is float for x in logits),'实际原logit形状不同')
            features_sha=hashlib.sha256(canonical(window['features']).encode()).hexdigest()
            row={key:window[key] for key in ('window_uid','domain','game','sequence','source_uid','source_pool_row','history_UIDs',
                'candidate_UIDs','pair_source_UIDs','labels','known_mask','history_frame_indices','candidate_frame_index','candidate_frame_number','epoch','augmentation','use_pose')}
            row.update(logits=logits,features_sha256=features_sha,model_id=spec['model_id'])
            chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest();row['record_chain_sha256']=chain
            stream.write(canonical(row)+'\n');rows.append(dict(window_uid=row['window_uid'],logits=logits,labels=list(row['labels']),candidate_UIDs=list(row['candidate_UIDs'])))
    result=runtime.fit_intercept(rows)
    require(result['status']=='complete_finite_trainR_intercept_fit_not_tracking_effect','拟合无有限可部署解，保留全部输入并停止，不退回0')
    r1=rng(torch);torch.save(r1,out/'RNG_after.pt')
    require(before==model_digest(model) and torch.equal(r0['TorchCPU'],r1['TorchCPU'])
        and pickle.dumps(r0['Python'])==pickle.dumps(r1['Python']) and pickle.dumps(r0['NumPy'])==pickle.dumps(r1['NumPy']), '拟合改模型或RNG')
    result.update(model_id=spec['model_id'],regime=spec['regime'],fold=spec['fold'],seed=spec['seed'],model_spec=spec,
        input_receipt=prepared['receipt'],source_refs=dict(protocol=ref(Path(cfg['_config_path'])),inventory=cfg['inventory'],
            runtime=ref(ROOT/'tools/research_ops/trainR_intercept_runtime.py'),inputs=ref(ROOT/'tools/research_ops/trainR_intercept_inputs.py')),
        recording=dict(model_loader_receipt=loaded['receipt'],window_records=ref(out/'windows.jsonl.gz'),
            forward_calls=calls,environment=ref(out/'environment.json'),source=ref(out/'source.json'),
            RNG_before=ref(out/'RNG_before.pt'),RNG_after=ref(out/'RNG_after.pt'),
            RNG_unchanged=True,model_digest_before=before,model_digest_after=model_digest(model),record_chain_sha256=chain,
            wall_seconds=time.perf_counter()-started,optimizer_state='not_applicable_scalar_root_finding_no_SGD'))
    write_new(out/'fit.json',result);return ref(out/'fit.json')

def worker(connection,cfg,log):
    try:
        with Path(log).open('x',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            inputs,runtime=dependencies();import torch
            torch.set_num_threads(1);torch.set_num_interop_threads(1);jobs=0;inventory=read(checked(cfg['inventory']))
            connection.send(dict(status='ready',worker_pid=os.getpid()))
            while True:
                task=connection.recv()
                if task['op']=='close':
                    inputs.clear_feature_cache();connection.send(dict(status='closed',worker_pid=os.getpid(),jobs=jobs,features_cache_cleared=True));break
                spec=next(s for s in inventory['models'] if s['model_id']==task['model_id'])
                reference=fit_model(cfg,spec,task['output'],inputs,runtime,torch);jobs+=1
                connection.send(dict(status='complete',worker_pid=os.getpid(),model_id=spec['model_id'],fit=reference))
    except BaseException:
        try:connection.send(dict(status='failed',worker_pid=os.getpid(),traceback=traceback.format_exc()))
        except (EOFError,BrokenPipeError):pass
    finally:connection.close()

class Service(base.Service):
    def __init__(self,cfg,log):
        ctx=mp.get_context('spawn');self.parent,child=ctx.Pipe();self.busy=None;self.closed=False;self.task_failed=False
        self.process=ctx.Process(target=worker,args=(child,cfg,str(log)));self.process.start();child.close()
        try:self.ready=self.receive();require(self.ready['status']=='ready','拟合worker未就绪')
        except BaseException:
            self.join_failed();raise

def execute(path,cfg,inventory):
    producers_absent();out=EXP/'fits_a01';require(not out.exists(),'未知拟合partial拒绝覆盖');out.mkdir();(out/'logs').mkdir();(out/'models').mkdir()
    support=load('intercept_fit_resource',checked(cfg['worker_support']));started=time.perf_counter()
    state=dict(status='starting2_trainR_intercept_fit_workers',protocol=ref(path),parent_pid=os.getpid(),created_utc=datetime.now(timezone.utc).isoformat(),
        workers=[],worker_exits=[],completed=[],active=[],resources=[],optimizer_updates=0,test_read=False)
    def save():
        p=out/'state.pending.json';p.write_text(canonical(state),encoding='utf-8');os.replace(p,out/'state.json')
    services=[];pending=deque(cfg['model_order']);fits={};save()
    try:
        require(support.enough_memory(support.resource_snapshot(),PROFILE,2),'资源预留不足')
        for i in range(2):
            s=Service(cfg,out/'logs'/f'fit_{i}.log');services.append(s);state['workers'].append(s.ready)
        while pending or any(s.busy for s in services):
            require(not (out/'STOP').exists(),'用户停止，保留partial不重开')
            snapshot=support.resource_snapshot();import psutil
            snapshot['sampled_process_tree_RSS_bytes']=sum(p.memory_info().rss for p in [psutil.Process()]+psutil.Process().children(recursive=True) if p.is_running())
            state['resources'].append(snapshot)
            for s in services:
                if s.busy or not pending or not support.enough_memory(snapshot,PROFILE):continue
                mid=pending.popleft();s.parent.send(dict(op='fit',model_id=mid,output=str(out/'models'/mid)));s.busy=mid
            state.update(status='running18_trainR_intercept_fits',active=[s.busy for s in services if s.busy]);save()
            busy=[s for s in services if s.busy]
            require(busy or support.enough_memory(snapshot,PROFILE),'资源不足，停止保留已完成记录')
            ready=wait([s.parent for s in busy],timeout=1)
            for s in busy:
                if s.parent not in ready:continue
                message=s.receive();mid=s.busy;s.busy=None
                require(message['status']=='complete' and message['model_id']==mid and mid not in fits,'完成项身份或重复不同')
                fits[mid]=message['fit'];state['completed'].append(message);save()
        for s in services:state['worker_exits'].append(s.close())
        state['active']=[];state['actual_exit_gate']=producers_absent()
        totals=dict(models=18,clean_R_model_window_evaluations=18000,all_pair_count=0,known_pair_count=0,unknown_pair_count=0,optimizer_updates=0)
        for reference in fits.values():
            fit=read(checked(reference))
            for key in ('all_pair_count','known_pair_count','unknown_pair_count'):totals[key]+=fit['totals'][key]
        manifest=dict(schema='trainR_intercept_fits_manifest_v1',status='complete18_trainR_intercept_fits_wait_independent_verification',protocol=ref(path),
            inventory=cfg['inventory'],calibrations={mid:fits[mid] for mid in cfg['model_order']},model_order=cfg['model_order'],totals=totals,
            worker_exits=state['worker_exits'],fit_workers_joined=True,test_read=False,optimizer_updates=0)
        write_new(out/'manifest.json',manifest)
        state.update(status=manifest['status'],manifest=ref(out/'manifest.json'),wall_seconds=time.perf_counter()-started);save()
        return dict(status=state['status'],manifest=ref(out/'manifest.json'),totals=totals)
    except BaseException as error:
        for s in services:
            if s.closed:continue
            try:
                if s.task_failed:state['worker_exits'].append(s.join_failed());continue
                if s.busy:s.receive();s.busy=None
                state['worker_exits'].append(s.close())
            except BaseException:state['worker_exits'].append(s.join_failed())
        state.update(status='failed_fit_partial_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256');p.add_argument('--execute',action='store_true');args=p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    cfg,inventory=validate(args.config);cfg['_config_path']=str(args.config)
    if not args.execute:result=dict(status='readonly_trainR_intercept_fit_preflight18_sources',phase=cfg['phase'])
    else:
        require(sha(args.config)==args.config_sha256,'配置SHA不符')
        result=numeric(args.config,cfg,inventory) if cfg['phase']=='numeric_admission' else execute(args.config,cfg,inventory)
    print(canonical(result))
