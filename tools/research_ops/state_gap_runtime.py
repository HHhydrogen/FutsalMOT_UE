"""训练域自由状态诊断的来源与只读模型；正常追踪禁止读取GT坐标。"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import gzip
import time
from types import SimpleNamespace

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/state_gap_diagnosis_a01'
OLD = {'SNMOT-060':'game4', 'SNMOT-097':'game6', 'SNMOT-151':'game9'}
SEED = 20261024
FIXED_ARGS = dict(track_high_thresh=.25,track_low_thresh=.1,new_track_thresh=.25,
    track_buffer=30,match_thresh=.8,fuse_score=True)

def require(ok, message):
    if not ok: raise ValueError(message)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False)

def safe(value, parent=None):
    path=Path(os.path.abspath(value))
    require(path.is_absolute() and R in path.parents, '只允许物理研究目录')
    require(not any(part.lower()=='test' or __import__('re').search(r'snmot[-_]?0*(116|187)(?:\D|$)',part.lower()) for part in path.parts), '测试继续封存')
    if parent is not None: require(Path(parent) in path.parents,'输出必须在本轮根下')
    for part in (path,*path.parents):
        if part.exists() or part.is_symlink():
            require(not part.is_symlink() and not getattr(part.lstat(),'st_file_attributes',0)&0x400, '不跟随junction')
    return path

def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def ref(path): return dict(path=str(safe(path)),sha256=sha(path))
def checked(value):
    p=safe(value['path']);require(p.is_file() and sha(p)==value['sha256'],'冻结来源变化：'+str(p));return p
def read_ref(value): return json.loads(checked(value).read_text(encoding='utf-8-sig'))
def module(value,prefix):
    p=checked(value);name=prefix+'_'+value['sha256']
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m
        before=sys.dont_write_bytecode
        try: sys.dont_write_bytecode=True;spec.loader.exec_module(m)
        finally: sys.dont_write_bytecode=before
    require(safe(sys.modules[name].__file__)==p,'模块物理来源被替换');return sys.modules[name]

def write_new(path,value):
    p=safe(path,EXP);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f: f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())

def source(config,relative):
    manifest=read_ref(config['bundle_manifest']);found=[i for i in manifest['files'] if i['path']==relative]
    require(len(found)==1,'冻结源码必须唯一：'+relative)
    return dict(path=str(safe(config['bundle'])/relative),sha256=found[0]['sha256'])

def require_guard_api(value):
    require(all(callable(getattr(value,key,None)) for key in ('GTReadGuard','BoundedLRU','deep_bytes')),'GT保护来源必须实际提供guard及有界缓存，不能误用资源采样器')

def validate_matrix(cfg,inventory):
    selected=[s for s in inventory['models'] if s['seed']==SEED]
    require(len({s['model_id'] for s in selected})==6 and {(s['regime'],s['fold']) for s in selected}=={(r,f) for r in ('R','RS') for f in OLD.values()},'原六模型R/RS与三fold必须各唯一')
    expected={(s['model_id'],s['regime'],s['fold'],SEED,seq) for s in selected
        for seq in inventory['folds'][s['fold']]['allowed_sequences']}
    actual={(j['model_id'],j['regime'],j['fold'],j['seed'],j['sequence']) for j in cfg['jobs']}
    require(len(selected)==6 and len(actual)==len(cfg['jobs'])==12 and actual==expected,'只准首seed六模型各两个允许train片段')
    require(set(cfg['sources'])==set(OLD) and all(cfg['sources'][s]==inventory['sources'][s] for s in OLD),'只准三个原train缓存，不含heldout/外部/测试')
    require(len({j['job_id'] for j in cfg['jobs']})==12 and sum(cfg['sources'][j['sequence']]['frames'] for j in cfg['jobs'])==9000,'必须12任务9000逻辑帧')
    require(cfg['tracker_parameters']==FIXED_ARGS and cfg['optimizer_updates']==0 and cfg['new_image_predictions']==0,'诊断不改变数值参数或训练')
    return selected

class Context:
    """每个专用track进程独立guard/cache；不调用会读取endpointGT的旧预飞。"""
    def __init__(self,cfg):
        require(os.environ.get('CUDA_VISIBLE_DEVICES')=='-1' and cfg['test_sealed'] is True and cfg['approved_by']=='root','必须独立CPU/封存root协议')
        self.cfg=cfg;self.closed=False;self.jobs=0;self.refs={}
        self.support=module(cfg['track_guard_source'],'state_gap_guard')
        require_guard_api(self.support)
        # 只从已签清单获取路径字符串；guard必须先于模型/旧运行时加载。
        inv=read_ref(cfg['inventory'])
        protected=[v[k]['path'] for v in inv['sources'].values() for k in ('gt','gt_reference','gameinfo','seqinfo') if k in v]
        velocity=read_ref(cfg['source_velocity_protocol'])
        protected += [v['registry']['path'] for v in velocity['registries'].values()]
        self.guard=self.support.GTReadGuard(protected);self.guard.install()
        self.specs={s['model_id']:s for s in validate_matrix(cfg,inv)}
        self.inputs=module(cfg['inputs_source'],'state_gap_original_inputs')
        self.utils=module(cfg['original_tracking_source'],'state_gap_original_helpers')
        old=read_ref(velocity['source_tracking_config']);training=read_ref(old['training_protocol']);self.v9=read_ref(training['v9_protocol'])
        self.pose_sha=training['pose_checkpoint_sha256']
        self.oldrt=module(source(old,'tools/research_ops/v10_tracking_runtime.py'),'state_gap_original_scope')
        with self.inputs.frozen_import_scope(safe(self.v9['bundle'])):
            self.cls,self.scope=self.oldrt.scoped_tracker(self.v9['bundle'],cfg['sources'])
        import torch
        self.torch=torch;torch.set_num_threads(1)
        require(not torch.cuda.is_initialized(),'不能初始化CUDA')
        from ultralytics.trackers.basetrack import BaseTrack
        from ultralytics.trackers.byte_tracker import STrack
        self.BaseTrack,self.STrack=BaseTrack,STrack
        self.models=self.support.BoundedLRU(256*1024*1024,max_items=3)
        self.cache=self.support.BoundedLRU(128*1024*1024,max_items=2)
        self.model_hashes={};self.frame_hashes={}

    def frames(self,sequence):
        require(sequence in OLD,'禁止新来源')
        src=self.cfg['sources'][sequence];key=src['cache']['sha256']
        def load():
            with checked(src['cache']).open(encoding='utf-8-sig') as f: values=[self.utils.public_frame(json.loads(line)) for line in f if line.strip()]
            require(len(values)==750,'完整750帧含空检测不可删')
            for frame in values: self.oldrt.validate_frame(frame,self.cfg['sources'])
            self.frame_hashes[key]=hashlib.sha256(canonical(values).encode()).hexdigest()
            return values,self.support.deep_bytes(values)
        return self.cache.get(key,load)

    def loaded(self,job):
        require(job in self.cfg['jobs'],'只允许协议完整登记任务')
        spec=self.specs[job['model_id']]
        require(all(job[k]==spec[k] for k in ('model_id','regime','fold','seed')) and OLD[job['sequence']]!=spec['fold'],'模型身份或训练域不同')
        key=canonical([spec['checkpoint'],spec['normalizer'],self.cfg['inputs_source']])
        def load():
            result=self.inputs.load_model(spec,device='cpu');require(result['binding']==spec['binding'],'原加载绑定不同')
            state=self.utils.model_state_sha(result['model']);norm=canonical(result['normalizer'].state())
            self.model_hashes[key]=(state,norm)
            return dict(**result,key=key),sum(t.numel()*t.element_size() for t in result['model'].state_dict().values())+len(norm.encode())
        return self.models.get(key,load)

    def new_tracker(self,job):
        require(not self.closed,'worker已关闭');loaded=self.loaded(job)
        self.BaseTrack.reset_id();self.STrack.reset_id()
        tracker=self.cls(mode='learned',model=loaded['model'],normalizer=loaded['normalizer'],use_pose=False,
            pose_source_sha256=self.pose_sha,fixed_detection_sha256=self.cfg['sources'][job['sequence']]['cache']['sha256'])
        require(tracker.frame_id==0 and self.BaseTrack._count==0,'任务状态或全局ID未清空')
        return tracker

    def checkpoint(self):
        for _,(v,_) in self.models.items.items():
            require((self.utils.model_state_sha(v['model']),canonical(v['normalizer'].state()))==self.model_hashes[v['key']],'常驻模型被更改')
        for key,(v,_) in self.cache.items.items():
            require(hashlib.sha256(canonical(v).encode()).hexdigest()==self.frame_hashes[key],'缓存被更改')
        require(not self.guard.blocked,'track尝试读取GT坐标')
        return dict(evaluation_GT_coordinate_files_opened=False,GT_guard=self.guard.proof(),models_unchanged=True,inputs_unchanged=True,
            GT_derived_oracle_plan_may_be_received=True,optimizer_updates=0,test_read=False)

    def close(self):
        require(not self.closed,'重复关闭');proof=self.checkpoint()
        proof.update(status='closed',pid=os.getpid(),model_cache=self.models.stats(),frame_cache=self.cache.stats(),jobs=self.jobs)
        self.models.clear();self.cache.clear();self.closed=True;return proof

def load_own(cfg,name):
    return module(source(cfg,'tools/research_ops/'+name+'.py'),'state_gap_'+name)

def read_rows(reference):
    with gzip.open(checked(reference),'rt',encoding='utf-8') as f: return [json.loads(line) for line in f]

class RowsWriter:
    def __init__(self,path):
        self.path=safe(path,EXP);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.raw=self.path.open('xb');self.gz=gzip.GzipFile(fileobj=self.raw,mode='wb',mtime=0);self.count=0
    def write(self,row): self.gz.write((canonical(row)+'\n').encode());self.count+=1
    def close(self): self.gz.close();self.raw.flush();os.fsync(self.raw.fileno());self.raw.close();return dict(**ref(self.path),rows=self.count)

def observer_kwargs(tracker):
    namespace=type(tracker).get_dists.__globals__
    return dict(feature_module=SimpleNamespace(candidate_gate=namespace['candidate_gate'],intervention_mask=namespace['intervention_mask']))

def compose_observe_receipt(payload,proof,metadata):
    payload=deepcopy(payload);rollout_schema=payload.pop('schema',None)
    require(not(set(payload)&set(proof) or set(payload)&set(metadata) or set(proof)&set(metadata)),'收据字段冲突，拒绝覆盖来源')
    return dict(schema='state_gap_observe_receipt_v1',rollout_schema=rollout_schema,**metadata,**payload,**proof)

def observe_job(context,job,output,*,prefix=None,original=False):
    core=load_own(context.cfg,'state_gap_rollout');out=safe(output,EXP)
    require(not out.exists(),'已有追踪partial拒绝覆盖');out.mkdir(parents=True)
    tracker=context.new_tracker(job);frames=context.frames(job['sequence']);frames=frames if prefix is None else frames[:prefix]
    started=time.perf_counter();before_rng=context.torch.get_rng_state().clone()
    if original:
        native=[]
        with context.torch.no_grad():
            for frame in frames: native.append(core.plain(tracker.update_frame(frame)))
        payload=dict(native_frames=native,frame_counts=list(map(len,native)),frames=len(frames),audit=deepcopy(tracker.audit),global_ID_after=int(context.BaseTrack._count),
            final_state_hash=core.digest(core.export_snapshot(tracker,id_class=context.BaseTrack)))
        artifact=None
    else:
        writer=RowsWriter(out/'frames.jsonl.gz')
        try:
            with context.torch.no_grad():
                payload=core.run_rollout(tracker,frames,observer_kwargs=observer_kwargs(tracker),id_class=context.BaseTrack,
                    frame_sink=writer.write,retain_frames=False)
        finally: artifact=writer.close()
    require(context.torch.equal(before_rng,context.torch.get_rng_state()),'诊断改变Torch随机状态')
    proof=context.checkpoint();context.jobs+=1
    metadata=dict(status='complete',job=job,protocol=context.cfg['_protocol_ref'],
        frames_log=artifact,source_cache=context.cfg['sources'][job['sequence']]['cache'],
        observer_enabled=not original,tracking_wall_seconds=time.perf_counter()-started)
    receipt=compose_observe_receipt(payload,proof,metadata)
    if original: receipt['native_sha256']=core.digest(receipt.pop('native_frames'))
    else:
        records=read_rows(artifact);receipt['native_sha256']=core.digest([r['native_output'] for r in records])
        receipt['state_sequence_sha256']=core.digest([r['full_state_sha256'] for r in records])
    write_new(out/'receipt.json',receipt)
    return ref(out/'receipt.json')

def replay_job(context,job,task,output):
    core=load_own(context.cfg,'state_gap_rollout');out=safe(output,EXP);require(not out.exists(),'已有重放partial拒绝覆盖');out.mkdir(parents=True)
    plans=read_ref(task['plans']);plans=plans['plans']
    require(0<len(plans)<=40 and all(set(p)=={'event_id','frame_number','track_id','wrong_uid','correct_uid'} for p in plans),'oracle计划只能携带五个无GT框字段')
    original=read_ref(task['observe']);require(original['job']==job and original['status']=='complete','原rollout不同')
    expected=read_rows(original['frames_log']);frames=context.frames(job['sequence'])
    maximum=max(p['frame_number'] for p in plans);snaps={};snaprefs={}
    writer=RowsWriter(out/'prefix_reconstruction.jsonl.gz');tracker=context.new_tracker(job)
    def snapshot_sink(number,value):
        p=out/'snapshots'/f'{number:04d}.json';write_new(p,value);snaprefs[number]=ref(p);snaps[number]=value
    def frame_sink(row):
        require(row==expected[row['frame_index']],'固定事件后的前缀重建未逐值复现原完整日志')
        writer.write(dict(frame_number=row['frame_number'],full_state_sha256=row['full_state_sha256'],native_sha256=core.digest(row['native_output'])))
    before_rng=context.torch.get_rng_state().clone();started=time.perf_counter()
    try:
        with context.torch.no_grad():
            core.run_rollout(tracker,frames[:maximum],observer_kwargs=observer_kwargs(tracker),id_class=context.BaseTrack,
                snapshot_sink=snapshot_sink,snapshot_frames={p['frame_number'] for p in plans},frame_sink=frame_sink,retain_frames=False)
    finally: prefix_ref=writer.close()
    results=[]
    for plan in plans:
        number=plan['frame_number'];segment=frames[number-1:number+30];require(len(segment)==31,'每入选事件必须错误帧+完整后30帧')
        old=expected[number-1:number+30];branches={}
        for branch in ('original','history_only','motion_only','both'):
            with context.torch.no_grad():
                value=core.replay_branch(snaps[number],segment,plan,new_tracker=lambda:context.new_tracker(job),branch=branch,
                    observer_kwargs=observer_kwargs(tracker),id_class=context.BaseTrack,
                    expected_error_log={k:v for k,v in old[0].items() if k!='native_output'},
                    expected_native_frames=[v['native_output'] for v in old],expected_state_hashes=[v['full_state_sha256'] for v in old])
            sink=RowsWriter(out/'events'/plan['event_id']/(branch+'.jsonl.gz'))
            for row,native in zip(value.pop('frame_states'),value.pop('native_frames')): sink.write(dict(row,native_output=native))
            value['frames_log']=sink.close();write_new(out/'events'/plan['event_id']/(branch+'.json'),value)
            branches[branch]=ref(out/'events'/plan['event_id']/(branch+'.json'))
        results.append(dict(event_id=plan['event_id'],snapshot=snaprefs[number],branches=branches))
    require(context.torch.equal(before_rng,context.torch.get_rng_state()),'重放改变Torch随机状态');context.jobs+=1
    receipt=dict(schema='state_gap_replay_receipt_v1',status='complete',job=job,protocol=context.cfg['_protocol_ref'],plans=task['plans'],
        original_observe=task['observe'],prefix_frames=maximum,branch_frame_advances=len(plans)*4*31,
        future_branch_frames=len(plans)*4*30,prefix=prefix_ref,events=results,wall_seconds=time.perf_counter()-started,**context.checkpoint())
    write_new(out/'receipt.json',receipt);return ref(out/'receipt.json')

class PosthocContext:
    """只在独立后验进程加载GT标签；不生成新模型分数。"""
    def __init__(self,cfg):
        self.cfg=cfg;self.analysis=load_own(cfg,'state_gap_analysis');self.inventory=read_ref(cfg['inventory']);validate_matrix(cfg,self.inventory)
        velocity=read_ref(cfg['source_velocity_protocol']);old=read_ref(velocity['source_tracking_config'])
        self.oldrt=module(source(old,'tools/research_ops/v10_tracking_runtime.py'),'state_gap_posthoc_GTloader')
        self.utils=module(cfg['original_tracking_source'],'state_gap_posthoc_helpers');self.sources={};self.jobs=0
    def labeled(self,sequence):
        if sequence not in self.sources:
            src=self.cfg['sources'][sequence]
            with checked(src['cache']).open(encoding='utf-8-sig') as f: raw=[self.utils.public_frame(json.loads(line)) for line in f if line.strip()]
            gt,_=self.oldrt.load_gt(src);self.sources[sequence]=self.analysis.build_label_index(raw,gt)
        return self.sources[sequence]
    def annotate(self,job,task,output):
        out=safe(output,EXP);require(not out.exists(),'已有后验partial拒绝覆盖');out.mkdir(parents=True)
        original=read_ref(task['observe']);require(original['job']==job and original['frames']==750,'必须完整对应750源帧')
        logs=read_rows(original['frames_log']);labeled=self.labeled(job['sequence'])
        annotation=self.analysis.annotate_rollout(logs,labeled,job);events=self.analysis.select_first_errors(logs,labeled,job)
        rows=RowsWriter(out/'all_rows.jsonl.gz')
        for row in annotation.pop('rows'): rows.write(row)
        annotation['all_rows']=rows.close()
        write_new(out/'annotation.json',dict(**annotation,source_label_counts=labeled['counts'],events=events,observe=task['observe'],job=job))
        self.jobs+=1;return ref(out/'annotation.json')
    def branch_summary(self,job,task,output):
        out=safe(output,EXP);require(not out.exists(),'已有分支后验partial拒绝覆盖');out.mkdir(parents=True)
        events=read_ref(task['selected_events'])['selected'];replay=read_ref(task['replay']);labeled=self.labeled(job['sequence']);records=[]
        for item in replay['events']:
            event=next(v for v in events if v['event_id']==item['event_id']);branches={}
            for name,reference in item['branches'].items():
                result=read_ref(reference);outcome=self.analysis.branch_outcomes(read_rows(result['frames_log']),labeled,event['track_id'],event['anchor_GT_id'],event['frame_number'])
                outcome['exact_original_reproduction']=result['original_branch_exact_checked'] if name=='original' else None
                outcome['intervention']=result['intervention'];branches[name]=outcome
            records.append(dict(**{k:event[k] for k in ('event_id','fold','sequence','regime','model_id','track_id','frame_number')},branches=branches))
        write_new(out/'summary.json',dict(status='complete',job=job,replay=task['replay'],event_records=records,summary=self.analysis.summarize_branches(records)))
        self.jobs+=1;return ref(out/'summary.json')
    def close(self):
        self.sources.clear();return dict(status='closed',pid=os.getpid(),jobs=self.jobs,GT_coordinate_reader='dedicated_posthoc_only',new_model_forward_calls=0)
