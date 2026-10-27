"""官方OC-SORT同缓存12片段：独立有界track/metric常驻池，先两场计数门禁。"""
import argparse
from collections import OrderedDict,deque
from contextlib import redirect_stdout,redirect_stderr
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import re
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]
R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/ocsort_cached12_a01'
STATUS='complete12_official_ocsort_cached_tracking_metrics_and_paired_analysis'

def require(ok,message):
    if not ok:raise ValueError(message)
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def physical(p):
    p=Path(os.path.abspath(p));require(R in p.parents,'仅允许物理研究根')
    require(not any(x.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',x.lower()) for x in p.parts),'最终测试继续封存')
    for x in (p,*p.parents):
        if x.exists() or x.is_symlink():require(not x.is_symlink() and not getattr(x.lstat(),'st_file_attributes',0)&0x400,'不跟随junction')
    return p
def read(p):return json.loads(physical(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(physical(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def checked(v):
    p=physical(v['path']);require(p.is_file() and sha(p)==v['sha256'],'绑定SHA改变：'+str(p));return p
def checked_dependency(v):
    """仅为既有两个库入口增加只读SHA核验；不扩大输入或输出写入根。"""
    p=Path(os.path.abspath(v['path']))
    if R in p.parents:return checked(v)
    allowed={Path('D:/projects/FutsalMOT/.venv/Lib/site-packages')/name/'__init__.py' for name in ('numpy','scipy')}
    require(p in allowed,'研究根外仅允许两个已固定库入口只读')
    for x in (p,*p.parents):
        if x.exists() or x.is_symlink():require(not x.is_symlink() and not getattr(x.lstat(),'st_file_attributes',0)&0x400,'依赖不能经junction访问')
    require(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==v['sha256'],'既有依赖SHA改变')
    return p
def write_new(p,v):
    p=physical(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(canonical(v)+'\n');f.flush();os.fsync(f.fileno())
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def own_runtime():return module('frozen_ocsort_cached_runtime',ROOT/'tools/research_ops/ocsort_cached_runtime.py')

def protected_paths(sources,registries):
    values=[v['path'] for s in sources.values() for k,v in s.items() if k in ('gt','gt_reference','gameinfo','seqinfo')]
    return sorted(set(values+[v['registry']['path'] for v in registries.values()]))

def validate_config(path):
    cfg=read(path)
    require(cfg['schema']=='official_ocsort_cached12_protocol_v1' and cfg['approved_by']=='root'
        and cfg['tracking_authorized'] is True and cfg['test_sealed'] is True
        and cfg['new_optimizer_updates']==0 and cfg['formal_equivalence_or_noninferiority'] is False,'独立12片段准入缺失')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行实际冻结bundle')
    for e in read(checked(cfg['bundle_manifest']))['files']:require(sha(ROOT/e['path'])==e['sha256'],'冻结执行源码改变')
    old=read(checked(cfg['source_velocity_protocol']))
    require(cfg['sources']==old['sources'] and cfg['panels']==old['panels'] and cfg['registries']==old['registries']
        and len(cfg['sources'])==12 and sum(s['frames'] for s in cfg['sources'].values())==8165,'必须复用原12缓存与全帧')
    require(cfg['protected_GT_paths']==protected_paths(cfg['sources'],cfg['registries']),'GT保护路径缺项')
    require(cfg['sequence_order']==[s for p in ('original_heldout','old_external','seven_observed') for s in cfg['panels'][p]]
        and cfg['gate_sequences']==['SNMOT-060','v_2QhNRucNC7E_c017'],'实际顺序与两场门禁未固定')
    require(cfg['worker_profile']==dict(track_workers=2,metric_workers=1,numeric_threads=1,
        cache_limit_bytes=134217728,cache_max_sequences=2,reserve_RAM_bytes=8589934592,
        reserve_commit_bytes=6442450944,startup_estimate_bytes=268435456),'只能已准入的有界2+1')
    for registry in cfg['registries'].values():
        public=read(checked(registry['receipt']))
        require(public['registry']==registry['registry'] and public['contains_GT_coordinates'] is False,'追踪只读无坐标公开收据')
    dependency=read(checked(cfg['dependency_manifest']))
    for item in dependency['files']:checked_dependency(item)
    official=read(checked(cfg['official_manifest']))
    require(official['commit']=='8462e7e729a93ccd3bd995c0a79a890336cb3a0b','官方版本不能浮动')
    require(cfg['parameters']==own_runtime().PARAMETERS,'官方默认参数不可结果后修改')
    complete=read(checked(cfg['source_velocity_complete']))
    require(complete['producer_processes_absent'] is True,'原实验未退出')
    return cfg

def producers_absent():
    import subprocess
    cmd="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    raw=subprocess.run(['powershell.exe','-NoProfile','-Command',cmd],capture_output=True,text=True,encoding='utf-8',check=True)
    records=json.loads(raw.stdout) if raw.stdout.strip() else [];records=[records] if isinstance(records,dict) else records
    own={os.getpid()};byid={x['ProcessId']:x for x in records};node=byid.get(os.getpid())
    while node and node['ParentProcessId'] in byid:
        parent=byid[node['ParentProcessId']]
        if 'ocsort_cached_control.py' not in (parent.get('CommandLine') or ''):break
        own.add(parent['ProcessId']);node=parent
    pattern=re.compile(r'(?:^|[\\/\s\"\x27])(?:ocsort_cached_(?:control|admission)|pose_velocity_(?:decision_probe|tracking_control|learning_train)|substitution_validation_predictions)[.]py(?=$|[\s\"\x27])',re.I)
    blocked=[x for x in records if x['ProcessId'] not in own and ((x.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(x.get('CommandLine') or ''))]
    require(not blocked,'相关自有生产者或UE仍在：'+canonical(blocked))
    return dict(actual_CIM_checked=True,related_producers_absent=True,own_launcher_chain=sorted(own))

def load_support(cfg):return module('ocsort_frozen_resource_support',checked(cfg['worker_support']))

def validate_admission_evidence(proof,admission_cfg,cfg,protocol_ref,runtime_ref):
    require(proof['status']=='complete_official_literal96_frames_ABA_two_spawn_exact_GT_guard_and_exit_verified'
        and admission_cfg['formal_protocol']==protocol_ref
        and admission_cfg['official_manifest']==cfg['official_manifest']
        and admission_cfg['dependency_manifest']==cfg['dependency_manifest']
        and admission_cfg['parameters']==cfg['parameters'] and admission_cfg['sources']==cfg['sources']
        and admission_cfg['runtime']==runtime_ref
        and proof['parameters']==admission_cfg['admission_parameters']
        and proof['official_backend']['manifest']==cfg['official_manifest']
        and proof['all_workers_joined_exited'] is True and proof['optimizer_updates']==0
        and proof['test_read'] is False,'正式12必须先完成对应冻结源码的真实96帧/常驻/两spawn准入')
    require(len(proof['persistent_ABA'])==3 and len(proof['independent_spawn_A'])==2
        and proof['parent_source_input_unchanged'] is True and proof['unique_source_frames']==96
        and proof['source_prefixes']=={k:cfg['sources'][s]['cache'] for k,s in [('A','SNMOT-060'),('B','v_2QhNRucNC7E_c017')]},'实际准入矩阵不完整')
    comparisons=list(proof['literal_vs_adapter'].values())+[x['comparison'] for x in proof['persistent_ABA']]+[x['comparison'] for x in proof['independent_spawn_A']]
    require(set(proof['literal_vs_adapter'])=={'A','B'} and len(comparisons)==7
        and all(x['original_ID_MOT_equal'] is True and x['all_frame_counts_equal'] is True
            and x['per_frame_raw_outputs_exact'] is True and x['frames']==48 for x in comparisons),'准入必须逐值验证原ID与全部输出')
    closures=[proof['persistent_worker']]+[x['closure'] for x in proof['independent_spawn_A']]
    require(len({x['pid'] for x in closures})==3 and all(x['kind']=='closed' and x['joined'] is True
        and x['exitcode']==0 and x['actual_PID_absent_after_join'] is True and x['active_trackers']==0 for x in closures),'准入实际PID唯一及正常退出未齐')
    guards=[proof['parent_GT_guard']]+[x['GT_guard'] for x in closures]
    require(all(x['GT_Python_open_guard'] is True and x['self_test_blocked_opens']>0
        and x['algorithm_blocked_GT_opens']==0 and x['algorithm_GT_read'] is False for x in guards),'准入GT保护未实证或算法尝试读取GT')
    require(set(proof['literal_internal_Kalman_dtypes'])=={'A','B'}
        and all(x==['float64'] for x in proof['literal_internal_Kalman_dtypes'].values()),'原生Kalman精度不是已验float64')
    return True

def check_admission(path,cfg):
    proof_path=physical(cfg['admission_receipt_path']);proof=read(proof_path)
    admission_cfg=read(checked(proof['config']))
    validate_admission_evidence(proof,admission_cfg,cfg,ref(path),ref(ROOT/'tools/research_ops/ocsort_cached_runtime.py'))
    return ref(proof_path)

class TrackWorker:
    def __init__(self,path,cfg):
        self.path=path;self.cfg=cfg;self.runtime=own_runtime();self.cache=OrderedDict();self.bindings={};self.jobs=0
        support=module('ocsort_GT_open_guard',checked(cfg['track_guard_source']))
        self.guard=support.GTReadGuard(cfg['protected_GT_paths']);self.guard.install()
        self.official=self.runtime.load_official(cfg['official_manifest']);self.max_cache_bytes=0
    def frames(self,sequence):
        source=self.cfg['sources'][sequence];key=source['cache']['sha256']
        if key in self.cache:
            value=self.cache.pop(key);self.cache[key]=value;return value[0]
        p=checked(source['cache']);frames=[]
        with p.open(encoding='utf-8-sig') as stream:
            for line in stream:
                if not line.strip():continue
                f=json.loads(line)
                require(f['sequence']==sequence and f['width']==source['width'] and f['height']==source['height'],'源帧身份/尺寸不同')
                value={k:f[k] for k in ('sequence','frame_index','frame_number','fps','timestamp_sec','width','height')}
                value['detections']=[{k:d[k] for k in ('uid','bbox_xywh_px','score')} for d in f['detections']]
                frames.append(value)
        require(len(frames)==source['frames'],'空检测帧也必须完整')
        size=len(canonical(frames).encode());limit=self.cfg['worker_profile']['cache_limit_bytes']
        require(size<=limit,'单clip超过冻结缓存上限')
        while self.cache and (len(self.cache)>=2 or sum(x[1] for x in self.cache.values())+size>limit):self.cache.popitem(last=False)
        self.cache[key]=(frames,size);self.bindings[str(p)]=source['cache']['sha256']
        self.max_cache_bytes=max(self.max_cache_bytes,sum(x[1] for x in self.cache.values()));return frames
    def run(self,sequence,output):
        started=time.perf_counter();output=physical(output);require(EXP in output.parents and not output.exists(),'追踪partial不覆盖')
        frames=self.frames(sequence);before=hashlib.sha256(canonical(frames).encode()).hexdigest()
        result=self.runtime.track_frames(frames,self.official,self.cfg['parameters'],input_reference=self.cfg['sources'][sequence]['cache'])
        require(before==hashlib.sha256(canonical(frames).encode()).hexdigest(),'共享输入被任务修改')
        output.mkdir(parents=True);(output/'data').mkdir()
        mot=output/'data'/f'{sequence}.txt';mot.write_text(result['mot_text'],encoding='utf-8')
        native=output/'native_outputs.jsonl'
        with native.open('x',encoding='utf-8') as f:
            for i,rows in enumerate(result['raw_outputs']):f.write(canonical(dict(frame_number=i+1,rows=rows))+'\n')
        receipt=dict(schema='official_ocsort_cached12_tracking_v1',status='complete',sequence=sequence,
            protocol_sha256=sha(self.path),frames=result['frames'],tracked_rows=result['tracked_rows'],frame_counts=result['frame_counts'],
            source_cache=self.cfg['sources'][sequence]['cache'],mot=ref(mot),mot_sha256=sha(mot),native_outputs=ref(native),
            audit=result['audit'],official_source=result['official_source'],parameters=self.cfg['parameters'],
            GT_guard=self.guard.proof(),evaluation_GT_annotations_loaded=False,GT_used_for_tracking=False,
            tracker_input_has_Pose=False,cache_prediction_JSON_may_contain_Pose_fields=True,
            worker_pid=os.getpid(),new_optimizer_updates=0,test_read=False,track_wall_seconds=time.perf_counter()-started)
        require(receipt['GT_guard']['blocked_open_attempts']==0,'track尝试访问GT')
        write_new(output/'receipt.json',receipt);self.jobs+=1
        return dict(sequence=sequence,tracking=str(output),receipt=ref(output/'receipt.json'))
    def close(self):
        for path,expected in self.bindings.items():require(sha(path)==expected,'常驻预测缓存来源变化')
        self.cache.clear();self.runtime.load_official(self.cfg['official_manifest'])
        return dict(status='closed',jobs=self.jobs,cache_entries_after=0,max_counted_cache_bytes=self.max_cache_bytes,
            counted_cache_is_JSON_bytes_not_RSS=True,GT_guard=self.guard.proof(),worker_pid=os.getpid())

class MetricWorker:
    def __init__(self,path,cfg):
        self.path=path;self.cfg=cfg;self.jobs=0;self.GT={};self.registries={};self.bindings={}
        v=read(checked(cfg['source_velocity_protocol']));seven=read(checked(v['source_seven_tracking_config']))
        bundle=physical(seven['bundle'])
        for e in read(checked(seven['bundle_manifest']))['files']:require(sha(bundle/e['path'])==e['sha256'],'原评价依赖源码改变')
        self.seven=module('ocsort_original_seven_metric_functions',bundle/'tools/research_ops/substitution_tracking_runtime.py')
        self.dep=self.seven.dependencies(v['source_tracking_config']);self.gap=self.seven.gap_numeric(self.dep)
        import torch
        torch.set_num_threads(1)
    def run(self,sequence,tracking,output):
        started=time.perf_counter();source=self.cfg['sources'][sequence];tracking=physical(tracking);output=physical(output)
        receipt=read(tracking/'receipt.json')
        require(receipt['schema']=='official_ocsort_cached12_tracking_v1' and receipt['status']=='complete'
            and receipt['protocol_sha256']==sha(self.path) and receipt['sequence']==sequence and receipt['source_cache']==source['cache']
            and receipt['frames']==source['frames'] and receipt['evaluation_GT_annotations_loaded'] is False
            and receipt['GT_guard']['blocked_open_attempts']==0,'追踪输入/GT边界改变')
        mot=checked(receipt['mot']);metric=self.dep[2]
        predictions,count=metric.prediction_rows(mot.read_text(encoding='utf-8'),source['frames'])
        require(count==receipt['tracked_rows']==sum(receipt['frame_counts']),'全部输出预测行必须保留')
        if sequence not in self.GT:
            self.GT[sequence]=(self.dep[1].load_gt(source) if sequence not in self.cfg['panels']['seven_observed'] else self.seven.load_gt(source))
            for key in ('gt','gt_reference','gameinfo'):
                if key in source:self.bindings[source[key]['path']]=source[key]['sha256']
        gt,text=self.GT[sequence];require(len(text)==self.cfg['expected_GT_rows'][sequence],'GT口径与原参照不同')
        require(not output.exists(),'评价partial不覆盖');output.mkdir(parents=True)
        raw,numeric_sha=metric.trackeval_numeric(source,text,tracking,output);summary={}
        for name,classes in raw.items():
            value=classes['pedestrian'];metric.validate_count(name,value['Count'],count,len(text),sequence,source['frames']);fractions={}
            for group,keys in [('HOTA',('HOTA','AssA','DetA')),('Identity',('IDF1',)),('CLEAR',('MOTA',))]:
                for key in keys:
                    number=value[group][key];fractions[key]=sum(number)/len(number) if isinstance(number,list) else float(number)
            summary[name]=dict(metrics_fraction=fractions,metrics_percent={k:100*x for k,x in fractions.items()},IDSW_count=int(value['CLEAR']['IDSW']))
        binding=self.cfg['registries']['seven' if sequence in self.cfg['panels']['seven_observed'] else 'old_five']
        key=binding['registry']['sha256']
        if key not in self.registries:
            self.registries[key]=read(checked(binding['registry']));self.bindings[binding['registry']['path']]=key
        registry=self.registries[key]
        require(registry['sources']=={s:self.cfg['sources'][s] for s in registry['sources']} and registry['sequences'][sequence]['cache']==source['cache'],'原gap来源必须相同')
        events=[x for x in registry['events'] if x['sequence']==sequence]
        recovery=self.gap.evaluate_events(events,registry['sequences'][sequence]['endpoint_GT'],predictions)
        require(recovery['overall']['total_events']==len(events),'必须全登记事件分母')
        result=dict(schema='official_ocsort_cached12_evaluation_v1',status='complete',sequence=sequence,frames=source['frames'],
            source_cache=source['cache'],protocol_sha256=sha(self.path),summary=summary,metrics_percent=summary[sequence]['metrics_percent'],
            raw_results=raw,recovery=recovery,registry=binding['registry'],GT_rows=len(text),actual_ID0_rows=sum(int(x.split(',')[1])==0 for x in text),
            tracking_receipt=ref(tracking/'receipt.json'),DO_PREPROC=False,predictions_GT_filtered=False,GT_ID0_original=True,
            GT_used_only_for_metric=True,numerical_source_sha256=numeric_sha,new_optimizer_updates=0,test_read=False,
            worker_pid=os.getpid(),metric_wall_seconds=time.perf_counter()-started)
        write_new(output/'report.json',result);self.jobs+=1
        return dict(sequence=sequence,report=ref(output/'report.json'))
    def close(self):
        for path,expected in self.bindings.items():require(sha(path)==expected,'常驻评价来源发生变化')
        return dict(status='closed',jobs=self.jobs,worker_pid=os.getpid(),GT_isolated_to_metric_worker=True,
            GT_sequences_loaded=list(self.GT),registry_count=len(self.registries),source_closure_verified=True)

def worker_service(connection,kind,path,log):
    worker=None
    try:
        with Path(log).open('x',encoding='utf-8') as stream,redirect_stdout(stream),redirect_stderr(stream):
            cfg=validate_config(path);worker=TrackWorker(path,cfg) if kind=='track' else MetricWorker(path,cfg)
            connection.send(dict(status='ready',kind=kind,worker_pid=os.getpid(),parent_pid=os.getppid(),
                created_utc=datetime.now(timezone.utc).isoformat()))
            while True:
                task=connection.recv()
                if task['op']=='close':connection.send(dict(status='closed',evidence=worker.close()));break
                if kind=='track':value=worker.run(task['sequence'],task['output'])
                else:value=worker.run(task['sequence'],task['tracking'],task['output'])
                connection.send(dict(status='complete',value=value,worker_pid=os.getpid()))
    except BaseException:
        traceback.print_exc()
        try:connection.send(dict(status='failed',traceback=traceback.format_exc(),worker_pid=os.getpid()))
        except (EOFError,BrokenPipeError):pass
    finally:connection.close()

class Service:
    def __init__(self,kind,path,log):
        self.kind=kind;self.parent,child=mp.get_context('spawn').Pipe();self.busy=None;self.closed=False
        self.process=mp.get_context('spawn').Process(target=worker_service,args=(child,kind,str(path),str(log)))
        self.process.start();child.close()
        try:
            self.ready=self.receive()
            require(self.ready['status']=='ready' and self.ready['worker_pid']==self.process.pid,'worker未实际就绪或PID不同')
        except BaseException as error:
            try:
                if self.process.is_alive():self.parent.send(dict(op='close'))
            except (EOFError,BrokenPipeError,OSError):pass
            self.process.join(30)
            evidence=dict(status='startup_handshake_failed_preserved_no_kill_or_replay',kind=kind,
                launcher_pid=self.process.pid,still_alive=self.process.is_alive(),exit_code=self.process.exitcode,
                error=repr(error),log=str(log))
            write_new(Path(log).with_suffix('.startup_failed.json'),evidence);self.parent.close()
            raise RuntimeError(canonical(evidence)) from error
    def receive(self):
        require(self.parent.poll(180),'worker超时，保留不强杀或重启')
        value=self.parent.recv();require(value['status']!='failed',value.get('traceback','worker失败'));return value
    def close(self):
        require(not self.closed and self.busy is None,'仅空闲worker可关闭')
        self.parent.send(dict(op='close'));result=self.receive();self.process.join(30)
        require(result['status']=='closed' and result['evidence']['status']=='closed'
            and result['evidence']['worker_pid']==self.ready['worker_pid']==self.process.pid
            and not self.process.is_alive() and self.process.exitcode==0,'worker关闭/实际join退出失败')
        self.parent.close();self.closed=True
        return dict(kind=self.kind,worker_pid=self.ready['worker_pid'],launcher_pid=self.process.pid,
            exit_code=self.process.exitcode,process_exited=True,close_evidence=result['evidence'])

def execute(path,output,config_sha):
    started=time.perf_counter();require(sha(path)==config_sha,'配置SHA不同');cfg=validate_config(path);producers_absent()
    admission_ref=check_admission(path,cfg)
    output=physical(output);require(output==physical(cfg['output_root']) and not output.exists(),'输出已存在或越界')
    output.mkdir(parents=True);(output/'logs').mkdir();support=load_support(cfg)
    state=dict(status='starting2track1metric',protocol=ref(path),parent_pid=os.getpid(),
        created_utc=datetime.now(timezone.utc).isoformat(),new_optimizer_updates=0,test_read=False,
        workers=[],completed_tracking=[],completed_metrics=[],active=[],resources=[],worker_exits=[],admission=admission_ref)
    def save():
        temp=output/'state.pending.json'
        temp.write_text(canonical(state),encoding='utf-8');os.replace(temp,output/'state.json')
    services=[];results={};tracking={};stop=False
    order=cfg['gate_sequences']+[s for s in cfg['sequence_order'] if s not in cfg['gate_sequences']]
    phases=[order[:2],order[2:]];save()
    try:
        require(support.enough_memory(support.resource_snapshot(),cfg['worker_profile'],3),'实际RAM/commit不足，不启动池')
        for kind,n in [('track',2),('metric',1)]:
            for i in range(n):
                service=Service(kind,path,output/'logs'/f'{kind}_{i}.log');services.append(service);state['workers'].append(service.ready);save()
        for phase_number,phase in enumerate(phases):
            pending=deque(phase);metrics=deque();paused=None
            while pending or metrics or any(s.busy for s in services):
                if (output/'STOP').exists():stop=True
                snapshot=support.resource_snapshot()
                import psutil
                tree=[psutil.Process()]+psutil.Process().children(recursive=True);rss=0
                for process in tree:
                    try:rss+=process.memory_info().rss
                    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                snapshot['sampled_process_tree_RSS_bytes']=rss
                state['peak_sampled_process_tree_RSS_bytes']=max(state.get('peak_sampled_process_tree_RSS_bytes',0),rss)
                state['resources'].append(snapshot)
                if len(state['resources'])>10000:state['resources']=state['resources'][-10000:]
                for service in services:
                    queue=pending if service.kind=='track' else metrics
                    if service.busy or not queue or stop:continue
                    if not support.enough_memory(snapshot,cfg['worker_profile']):
                        paused=paused or time.monotonic();require(time.monotonic()-paused<600,'资源不足持续超时，保留partial');continue
                    paused=None;sequence=queue.popleft();task=dict(op=service.kind,sequence=sequence,
                        output=str(output/'runs'/sequence/('tracking' if service.kind=='track' else 'metric')))
                    if service.kind=='metric':task['tracking']=str(output/'runs'/sequence/'tracking')
                    service.parent.send(task);service.busy=sequence
                state['active']=[dict(kind=s.kind,sequence=s.busy,worker_pid=s.ready['worker_pid']) for s in services if s.busy]
                state['status']='running_first_two_actual_evaluation_gate' if phase_number==0 else 'running_remaining10_same_cached_clips';save()
                busy=[s for s in services if s.busy]
                if not busy:
                    if stop:break
                    time.sleep(.5);continue
                available=wait([s.parent for s in busy],timeout=1)
                for service in busy:
                    if service.parent not in available:continue
                    message=service.receive();sequence=service.busy;service.busy=None;value=message['value']
                    require(message['status']=='complete' and value['sequence']==sequence
                        and message['worker_pid']==service.ready['worker_pid'],'任务收集身份错误')
                    if service.kind=='track':tracking[sequence]=value;state['completed_tracking'].append(value);metrics.append(sequence)
                    else:results[sequence]=value;state['completed_metrics'].append(value)
                    save()
            if stop:break
            if phase_number==0:
                require(set(results)==set(cfg['gate_sequences']),'先两场实际评价未齐')
                gate=[]
                for sequence in cfg['gate_sequences']:
                    report=read(checked(results[sequence]['report']))
                    require(report['GT_rows']==cfg['expected_GT_rows'][sequence] and report['DO_PREPROC'] is False
                        and report['predictions_GT_filtered'] is False,'两场计数/全预测门禁失败')
                    gate.append(dict(sequence=sequence,report=results[sequence]['report'],frames=report['frames'],GT_rows=report['GT_rows'],actual_ID0_rows=report['actual_ID0_rows']))
                write_new(output/'first_two_actual_adapter_gate.json',dict(status='complete_two_actual_OC_core_and_TrackEval_count_gates',checks=gate,test_read=False))
        for service in services:state['worker_exits'].append(service.close())
        state['active']=[];save();state['actual_exit_gate']=producers_absent()
        if stop:state['status']='stopped_at_user_boundary_partial_preserved_no_replay';save();return dict(status=state['status'])
        require(len(tracking)==len(results)==12 and all(x['process_exited'] for x in state['worker_exits']),'12齐全与worker实际退出未完成')
        evaluations=dict(schema='official_ocsort_cached12_evaluation_manifest_v1',status='complete12_official_ocsort_cached_evaluations',
            protocol=ref(path),evaluations=[results[s] for s in cfg['sequence_order']])
        write_new(output/'evaluation_manifest.json',evaluations)
        analysis=module('ocsort_completed_paired_analysis',ROOT/'tools/research_ops/ocsort_cached_analysis.py')
        state['analysis']=analysis.analyze(path,output/'evaluation_manifest.json',output/'analysis_a01',execute=True)
        state.update(status=STATUS,analysis_report=ref(output/'analysis_a01/report.json'),wall_seconds=time.perf_counter()-started,
            actual_frames=8165,actual_clips=12,new_detector_or_Pose_inference=False,GT_only_metric_process=True)
        save();return dict(status=STATUS,actual_clips=12,actual_frames=8165,new_optimizer_updates=0)
    except BaseException as error:
        for service in services:
            if service.closed:continue
            try:
                if service.busy is not None:service.receive();service.busy=None
                state['worker_exits'].append(service.close())
            except BaseException as closing:state.setdefault('failure_exit_evidence',[]).append(repr(closing))
        state.update(status='failed_preserved_no_implicit_replay',error=repr(error),traceback=traceback.format_exc());save();raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--config-sha256');parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    if args.execute:result=execute(args.config,args.output,args.config_sha256)
    else:
        cfg=validate_config(args.config);result=dict(status='readonly12_official_OC_cache_protocol_no_tracking',clips=12,frames=8165,new_optimizer_updates=0,test_read=False)
    print(canonical(result))
