"""新R来源的独立track/metric常驻适配；原数值只读引用，不应用截距。"""
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).parent))
import state_aligned_tracking_runtime as rt

EXP=rt.EXP
FIXED_ARGS=rt.FIXED_ARGS
METRICS=('AssA','HOTA','IDF1','DetA','MOTA')
TRACK_SCHEMA='state_aligned_tracking_receipt_v1'
METRIC_SCHEMA='state_aligned_tracking_metric_v1'
_TRACK_WORKER=None
_METRIC_WORKER=None
_PROCESS_KIND=None
require,canonical,checked,read_ref,ref=rt.require,rt.canonical,rt.checked,rt.read_ref,rt.ref

def safe(value,root=None):
    p=rt.safe(value)
    if root is not None:require(rt.safe(root) in p.parents,'只准独立新实验输出')
    return p

def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())

class Bindings:
    """新18权重/实际预算独立绑定，不调用旧截距Bindings或拟合metadata。"""
    def __init__(self,cfg):
        self.cfg=cfg;self.references={}
        require(cfg['approved_by']=='root' and cfg['test_sealed'] is True and cfg['new_optimizer_updates']==0
            and (cfg.get('tracking_authorized') is True or cfg.get('numeric_authorized') is True),'独立零更新准入不足')
        require(safe(cfg['output_root'])==EXP and 'calibrations' not in cfg and 'fit_complete' not in cfg,'不能借旧截距实验身份')
        self.protocol=deepcopy(cfg['_protocol_ref']);self.remember(self.protocol)
        self.inventory=self.read(cfg['inventory']);rt.validate_jobs(cfg,self.inventory)
        rt.training_closure(cfg)
        for name in ('training_budget','learning_protocol','source_inventory','source_velocity_protocol','source_worker_framework'):
            self.remember(cfg[name])
        own=self.source(cfg,'tools/research_ops/state_aligned_tracking_workers.py')
        require(safe(__file__)==checked(own),'worker必须来自新冻结bundle')
        self.source(cfg,'tools/research_ops/state_aligned_tracking_runtime.py')
        sources=rt.source_bindings(cfg)
        for name in ('velocity','old','seven_cfg','training','v9','old_rt','seven_ref'):
            setattr(self,name,sources[name])
        self.framework=sources['worker_framework']
        self.inputs=rt.module(self.remember(cfg['original_inputs_source']),'aligned_original_import_scope')
        require(cfg['original_inputs_source']['sha256']=='360ca83d75475a85cf293f0d2392dabcff58d329ec8487e596acf867904f2f85',
            '只能复用原import scope助手，不能换输入路径代码')
        self.source(self.v9,'python/src/grf_ue_bridge/learned_association_tracker_v8.py')
        for name in ('learned_association_features_v8.py','learned_association_model_v8.py','pose_association_contract_v2.py'):
            self.source(self.v9,'python/src/grf_ue_bridge/'+name)

    def remember(self,value):
        checked(value);self.references[value['path']]=deepcopy(value);return value
    def read(self,value):return read_ref(self.remember(value))
    def source(self,config,relative):return self.remember(rt.source(config,relative))
    def spec(self,job):
        require(job in self.cfg['jobs'],'未登记追踪任务')
        found=[s for s in self.inventory['models'] if s['model_id']==job['model_id']]
        require(len(found)==1 and all(found[0][k]==job[k] for k in ('baseline_model_id','regime','fold','seed')),'新模型/原参照单元不同')
        return found[0]
    def closure(self):
        for value in self.references.values():checked(value)
        return dict(source_closure_verified=True,checked_references=len(self.references),
            old_runtime_validate_or_dependencies_called=False,calibration_metadata_read=False)

def model_state_sha(model):
    h=hashlib.sha256()
    for name,value in sorted(model.state_dict().items()):
        h.update(canonical([name,str(value.dtype),list(value.shape)]).encode())
        h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

class TrackWorker:
    def __init__(self,cfg):
        global _PROCESS_KIND
        require(_PROCESS_KIND in (None,'track') and os.environ.get('CUDA_VISIBLE_DEVICES')=='-1','track/GT评价独立CPU进程')
        _PROCESS_KIND='track';self.cfg=cfg;self.jobs=0;self.closed=False
        self.support=rt.module(cfg['track_guard_source'],'aligned_frozen_GT_guard')
        protected=[v[k]['path'] for v in cfg['sources'].values() for k in ('gt','gt_reference','gameinfo','seqinfo') if k in v]
        protected += [v['registry']['path'] for v in cfg['registries'].values()]
        self.guard=self.support.GTReadGuard(sorted(set(protected)));self.guard.install()
        self.binding=Bindings(cfg);self.framework=self.binding.framework;self.binding.remember(cfg['track_guard_source'])
        self.frames_cache=self.support.BoundedLRU(128*1024*1024,max_items=2)
        self.model_cache=self.support.BoundedLRU(256*1024*1024,max_items=3);self.input_hashes={};self.model_hashes={}
        import torch
        self.torch=torch;torch.set_num_threads(1);require(not torch.cuda.is_initialized(),'CPU追踪不能初始化GPU')
        with self.binding.inputs.frozen_import_scope(safe(self.binding.v9['bundle'])):
            self.cls,self.scope=self.binding.old_rt.scoped_tracker(self.binding.v9['bundle'],cfg['sources'])
        from ultralytics.trackers.basetrack import BaseTrack
        from ultralytics.trackers.byte_tracker import STrack
        self.BaseTrack,self.STrack=BaseTrack,STrack
        for key in ('old_five','seven'):
            bound=cfg['registries'][key];public=self.binding.read(bound['receipt'])
            require(public['registry']==bound['registry'] and public['contains_GT_coordinates'] is False,'track只能读无GT坐标事件receipt')
    def frames(self,sequence):return self.framework.TrackWorker.frames(self,sequence)
    def model(self,job):
        spec=self.binding.spec(job)
        key=canonical([spec['learning_protocol'],spec['training_receipt'],spec['training_complete'],spec['original_normalizer'],self.cfg['training_budget']])
        def load():
            loaded=rt.load_model(self.cfg,spec);model=loaded['model'];normalizer=loaded['normalizer']
            state=model_state_sha(model);norm=canonical(normalizer.state());self.model_hashes[key]=(state,norm)
            for name in ('training_receipt','training_complete','original_normalizer'):self.binding.remember(spec[name])
            size=sum(v.numel()*v.element_size() for v in model.state_dict().values())+len(norm.encode())
            return dict(base=model,normalizer=normalizer,binding=loaded['binding'],loading_receipt=loaded['receipt'],cache_key=key),size
        return self.model_cache.get(key,load)
    def payload(self,job,*,prefix_frames=None):
        require(not self.closed,'已关闭worker不可调用')
        require(prefix_frames is None or self.cfg.get('numeric_authorized') is True,'前缀必须独立数值准入')
        spec=self.binding.spec(job);frames=self.frames(job['sequence'])
        if prefix_frames is not None:
            require(type(prefix_frames) is int and 0<prefix_frames<=len(frames),'前缀范围错误');frames=frames[:prefix_frames]
        loaded=self.model(job);model=loaded['base']
        before_inputs=hashlib.sha256(canonical(frames).encode()).hexdigest();before_model=model_state_sha(model)
        before_norm=canonical(loaded['normalizer'].state());before_rng=self.torch.get_rng_state().clone()
        self.BaseTrack.reset_id();self.STrack.reset_id();require(self.BaseTrack._count==0,'每job全局ID必须归零')
        tracker=self.cls(mode='learned',model=model,normalizer=loaded['normalizer'],use_pose=False,
            pose_source_sha256=self.binding.training['pose_checkpoint_sha256'],fixed_detection_sha256=self.cfg['sources'][job['sequence']]['cache']['sha256'])
        require(tracker.previous==-1 and tracker.sequence is None and tracker.frame_id==0
            and all(not getattr(tracker,k) for k in ('tracked_stracks','lost_stracks','removed_stracks')),'每job轨迹/历史必须清空')
        counts,lines,native=[],[],[]
        with self.torch.no_grad():
            for frame in frames:
                rows=tracker.update_frame(frame);native.append(rows.tolist() if hasattr(rows,'tolist') else [list(row) for row in rows]);counts.append(len(rows))
                for row in rows:
                    x1,y1,x2,y2,identity,score=row[:6]
                    lines.append(','.join(map(str,[frame['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
        require(before_inputs==hashlib.sha256(canonical(frames).encode()).hexdigest() and before_model==model_state_sha(model)
            and before_norm==canonical(loaded['normalizer'].state()) and self.torch.equal(before_rng,self.torch.get_rng_state()),'输入/权重/标准化/RNG被修改')
        require((before_model,before_norm)==self.model_hashes[loaded['cache_key']] and not self.guard.blocked,'常驻污染或track读GT')
        self.jobs+=1;mot='\n'.join(lines)+('\n' if lines else '')
        return dict(mot_text=mot,mot=mot,raw_frames=native,frames=len(frames),tracked_rows=len(lines),frame_counts=counts,
            audit=deepcopy(tracker.audit),scope_adapter=self.scope,binding=deepcopy(loaded['binding']),model_loading_receipt=loaded['loading_receipt'],
            learning_protocol=self.cfg['learning_protocol'],training_budget=self.cfg['training_budget'],baseline_model_id=spec['baseline_model_id'],
            prefix_frames=prefix_frames,original_base_forward_without_intercept_wrapper=True,intercept_applied=False,calibration_metadata_read=False,
            training_R_S_label_metadata_parsed_for_checkpoint_binding=True,training_labels_used_in_tracking_features=False,
            global_ID_before=0,global_ID_after=int(self.BaseTrack._count),all_job_state_reset=True,source_inputs_unchanged=True,
            original_model_state_unchanged=True,original_normalizer_unchanged=True,Torch_CPU_RNG_unchanged=True,actual_dtype='float32',original_input_dim=194,
            input_Pose_columns_zeroed_after_original_normalization=True,native_ordered_batch_forward_preserved=True,original_probability_cutoff=.5,
            alias_used=False,GT_guard=self.guard.proof(),evaluation_GT_coordinate_files_opened=False,GT_used_for_tracking=False,GPU_used=False,
            new_optimizer_updates=0,test_read=False)
    def run(self,job,output):
        output=safe(output,self.cfg['output_root']);require(not output.exists(),'追踪partial/成功不覆盖');started=time.perf_counter()
        payload=self.payload(job);output.mkdir(parents=True);(output/'data').mkdir();mot=output/'data'/(job['sequence']+'.txt')
        with mot.open('x',encoding='utf-8') as f:f.write(payload.pop('mot_text'))
        payload.pop('mot');native=payload.pop('raw_frames');payload['native_output_frames_sha256']=hashlib.sha256(canonical(native).encode()).hexdigest()
        receipt=dict(schema=TRACK_SCHEMA,status='complete',job=job,model_id=job['model_id'],protocol_sha256=self.binding.protocol['sha256'],
            source_cache=self.cfg['sources'][job['sequence']]['cache'],mot=ref(mot),mot_sha256=rt.sha(mot),worker_pid=os.getpid(),
            tracking_wall_seconds=time.perf_counter()-started,**payload)
        write_new(output/'receipt.json',receipt);return dict(job=job,tracking=str(output),receipt=ref(output/'receipt.json'))
    def close(self):
        # 原缓存污染/GT边界/释放检查逐值复用，移除旧截距的metadata口径。
        result=self.framework.TrackWorker.close(self);result.pop('calibration_trainR_metadata_parsed',None)
        result.update(calibration_metadata_read=False,intercept_applied=False,new_model_identity='state_aligned_strongmotion',
            training_R_S_label_metadata_parsed_for_checkpoint_binding=True,training_labels_used_in_tracking_features=False)
        return result

class MetricWorker:
    def __init__(self,cfg):
        global _PROCESS_KIND
        require(_PROCESS_KIND in (None,'metric'),'GT评价与track必须独立进程');_PROCESS_KIND='metric'
        self.cfg,self.jobs,self.closed=cfg,0,False;self.binding=Bindings(cfg)
        self.metric,self.numeric_evidence=self.binding.framework.metric_functions(self.binding)
        self.seven=rt.module(self.binding.seven_ref,'aligned_original_seven_GTloader')
        self.gap=rt.module(self.binding.source(self.binding.v9,'tools/research_ops/v8_gap_recovery.py'),'aligned_original_gap')
        self.GT,self.registries={},{}
    def run(self,job,output):
        spec=self.binding.spec(job);require(not self.closed,'metric已关闭');source=self.cfg['sources'][job['sequence']]
        tracking=safe(self.cfg['control_root'])/'runs'/job['job_id']/'tracking';receipt_ref=ref(tracking/'receipt.json');receipt=read_ref(receipt_ref)
        require(receipt['schema']==TRACK_SCHEMA and receipt['status']=='complete' and receipt['job']==job
            and receipt['protocol_sha256']==self.binding.protocol['sha256'] and receipt['source_cache']==source['cache'] and receipt['frames']==source['frames']
            and receipt['learning_protocol']==self.cfg['learning_protocol'] and receipt['training_budget']==self.cfg['training_budget']
            and receipt['baseline_model_id']==spec['baseline_model_id'] and receipt['intercept_applied'] is False and receipt['calibration_metadata_read'] is False
            and receipt['GT_used_for_tracking'] is False and receipt['evaluation_GT_coordinate_files_opened'] is False and receipt['test_read'] is False
            and receipt['alias_used'] is False and not any(k in receipt for k in ('fit','beta32','calibrated_beta32')),'新模型/全帧/无截距/GT隔离来源不同')
        mot=checked(receipt['mot']);predictions,count=self.metric.prediction_rows(mot.read_text(encoding='utf-8'),source['frames'])
        require(count==receipt['tracked_rows']==sum(receipt['frame_counts']),'预测不能按GT筛选');sequence=job['sequence']
        if sequence not in self.GT:
            loader=self.seven.load_gt if sequence in self.cfg['panels']['seven_observed'] else self.binding.old_rt.load_gt
            self.GT[sequence]=loader(source)
            for k in ('gt','gt_reference','gameinfo','seqinfo'):
                if k in source:self.binding.remember(source[k])
        gt,text=self.GT[sequence];require(len(text)==self.cfg['expected_GT_rows'][sequence],'原GT计数/ID0口径不同')
        output=safe(output,self.cfg['output_root']);require(not output.exists(),'评价partial/成功不覆盖');output.mkdir(parents=True)
        raw,numerical_sha=self.metric.trackeval_numeric(source,text,tracking,output);summary={}
        for name,classes in raw.items():
            value=classes['pedestrian'];self.metric.validate_count(name,value['Count'],count,len(text),sequence,source['frames']);fraction={}
            for group,keys in (('HOTA',('HOTA','AssA','DetA')),('Identity',('IDF1',)),('CLEAR',('MOTA',))):
                for k in keys:
                    number=value[group][k];fraction[k]=sum(number)/len(number) if isinstance(number,list) else float(number)
            summary[name]=dict(metrics_fraction=fraction,metrics_percent={k:100*v for k,v in fraction.items()},IDSW_count=int(value['CLEAR']['IDSW']))
        reg=self.cfg['registries']['seven' if sequence in self.cfg['panels']['seven_observed'] else 'old_five'];key=reg['registry']['sha256']
        if key not in self.registries:self.registries[key]=self.binding.read(reg['registry'])
        registry=self.registries[key]
        require(registry['sources']=={q:self.cfg['sources'][q] for q in registry['sources']} and registry['sequences'][sequence]['cache']==source['cache'],'原事件/缓存改变')
        events=[e for e in registry['events'] if e['sequence']==sequence]
        gap=self.gap.evaluate_events(events,registry['sequences'][sequence]['endpoint_GT'],predictions)
        require(gap['overall']['total_events']==len(events),'全登记事件分母必须保留')
        report=dict(schema=METRIC_SCHEMA,status='complete',job=job,protocol_sha256=self.binding.protocol['sha256'],tracking_receipt=receipt_ref,
            source_cache=source['cache'],learning_protocol=self.cfg['learning_protocol'],training_budget=self.cfg['training_budget'],
            baseline_model_id=spec['baseline_model_id'],intercept_applied=False,metrics=summary[sequence]['metrics_percent'],gap=gap,summary=summary,raw_results=raw,
            registry=reg['registry'],frames=source['frames'],GT_rows=len(text),tracked_rows=count,DO_PREPROC=False,predictions_GT_filtered=False,
            GT_ID0_original=True,GT_used_only_for_metric=True,numerical_source_sha256=numerical_sha,metric_pure_functions=self.numeric_evidence,
            worker_pid=os.getpid(),new_optimizer_updates=0,test_read=False)
        require(set(report['metrics'])==set(METRICS) and all(math.isfinite(v) for v in report['metrics'].values()),'五指标须完整有限百分点')
        write_new(output/'report.json',report);self.jobs+=1;return dict(job=job,report=ref(output/'report.json'))
    def close(self):
        require(not self.closed,'metric不能重复关闭');self.closed=True
        return dict(status='closed',worker_pid=os.getpid(),jobs=self.jobs,GT_sequences_loaded=list(self.GT),
            GT_isolated_to_metric_worker=True,registry_count=len(self.registries),**self.binding.closure())

def track_job(cfg,job,output):
    global _TRACK_WORKER
    if _TRACK_WORKER is None:_TRACK_WORKER=TrackWorker(cfg)
    require(_TRACK_WORKER.binding.protocol==cfg['_protocol_ref'],'常驻track不能混协议');return _TRACK_WORKER.run(job,output)
def metric_job(cfg,job,output):
    global _METRIC_WORKER
    if _METRIC_WORKER is None:_METRIC_WORKER=MetricWorker(cfg)
    require(_METRIC_WORKER.binding.protocol==cfg['_protocol_ref'],'常驻metric不能混协议');return _METRIC_WORKER.run(job,output)
def close_track_worker():
    require(_TRACK_WORKER is not None,'track未创建');return _TRACK_WORKER.close()
def close_metric_worker():
    require(_METRIC_WORKER is not None,'metric未创建');return _METRIC_WORKER.close()
def compare_payloads(actual,reference):
    for key in ('mot_text','raw_frames','frame_counts','audit','frames','tracked_rows'):
        require(canonical(actual[key])==canonical(reference[key]),'完整原生数值输出不同：'+key)
    for v in (actual,reference):
        require(all(v[k] is True for k in ('all_job_state_reset','source_inputs_unchanged','original_model_state_unchanged','original_normalizer_unchanged','Torch_CPU_RNG_unchanged'))
            and v['global_ID_before']==0 and v['GT_guard']['blocked_open_attempts']==0 and v['evaluation_GT_coordinate_files_opened'] is False
            and v['GT_used_for_tracking'] is False and v['new_optimizer_updates']==0 and v['test_read'] is False and v['alias_used'] is False
            and v['intercept_applied'] is False and v['calibration_metadata_read'] is False
            and v['original_base_forward_without_intercept_wrapper'] is True,'新模型/状态/GT隔离边界缺证')
    return dict(original_ID_MOT_exact=True,raw_native_frames_exact=True,frame_counts_exact=True,audit_exact=True,frames=actual['frames'],tracked_rows=actual['tracked_rows'],
        MOT_sha256=hashlib.sha256(actual['mot_text'].encode()).hexdigest(),raw_frames_sha256=hashlib.sha256(canonical(actual['raw_frames']).encode()).hexdigest())
