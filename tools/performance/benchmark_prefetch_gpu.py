"""同步/有界预取ABBA端到端GPU小基准；不计正式训练、不改v5。"""
import argparse
from copy import copy,deepcopy
import gc
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

RESEARCH=Path('D:/projects/FutsalMOT_Research')
TRAINING_BUNDLE=RESEARCH/'code/7e5b7a7500919a0088bb443b0d002560a2d47ef104276aee285dede052237c28'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def write(p,value):
    with Path(p).open('x',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

class PrefetchedView:
    """只允许按冻结访问表取样，source_key读取records不触碰后台LRU。"""
    def __init__(self,source,indices,capacity=2):
        from ordered_prefetch import OrderedPrefetch
        self.source=source;self.records=source.dataset.records;self.indices=tuple(indices);self.cursor=0
        self.stream=OrderedPrefetch(source.__getitem__,self.indices,capacity=capacity,resource=source,
            max_item_bytes=2*1024**2,measure_bytes=lambda v:sum(x.numel()*x.element_size() for x in v.values() if hasattr(x,'numel')))
    def __getitem__(self,index):
        require(self.cursor<len(self.indices) and index==self.indices[self.cursor],'预取访问顺序变化，拒绝跳样/重放')
        value=next(self.stream);self.cursor+=1;return value
    def start(self):self.stream.start();return self
    def close(self):self.stream.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    c=read(args.config);bundle=Path(__file__).resolve().parents[2]
    require(bundle.parent==RESEARCH/'code' and len(bundle.name)==64,'实际执行只允许DResearch不可变bundle')
    for item in c['code_files']:require(sha(bundle/item['path'])==item['sha256'],'基准代码SHA变化')
    require(c['schema']=='futsalmot_prefetch_GPU_benchmark_v1' and c['approved_by']=='root' and c['steps']==64 and c['order']==['sync','prefetch','prefetch','sync'],'独立基准协议不符')
    require(read(c['v5_complete_receipt'])['related_processes_absent'] is True,'先完成旧训练/追踪')
    import psutil
    own={os.getpid(),os.getppid()}
    for p in psutil.process_iter(['pid','name']):
        if p.pid in own:continue
        name=(p.info['name'] or '').lower()
        require(name!='unrealeditor.exe','UE仍在，不能GPU基准')
        if name not in ('python.exe','pythonw.exe'):continue
        try:cmd=' '.join(p.cmdline()).lower()
        except psutil.NoSuchProcess:continue
        require(not any(x in cmd for x in ('train_longpair_v5.py','evaluate_longpair_v5.py','v5_association_stage.py','benchmark_prefetch_gpu.py','v6_crop_driver.py')),'其他GPU任务仍在:'+str(p.pid))
    sys.path[:0]=[str(TRAINING_BUNDLE/'tools/research_ops'),str(TRAINING_BUNDLE/'python/src'),str(bundle/'tools/performance')]
    from train_longpair_v5 import preflight,configure_runtime
    numeric,context=preflight(Path(c['runtime']),Path(c['protocol']),Path(c['admission']),20261024,'R3S_blue')
    if not args.execute:print(json.dumps(dict(status='readonly_prefetch_benchmark_ready')));return
    configure_runtime()
    import cv2
    import numpy as np
    import torch
    from ultralytics.utils import DEFAULT_CFG
    from ultralytics.utils.torch_utils import ModelEMA
    from grf_ue_bridge.pose_location_dataset_v2 import LocationPoseDataset
    from grf_ue_bridge.pose_location_supervision_v4 import SeparateDomainLocationObjective
    from grf_ue_bridge.pose_only_calibration_v3 import configure_pose_only
    from grf_ue_bridge.pose_xy_head_transfer import map_pose_xy
    from v5_virtual_crop import VirtualCropDataset
    torch.set_num_threads(4);cv2.setNumThreads(1);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
    output=Path(c['output']).absolute();require(RESEARCH/'performance' in output.parents and not output.exists(),'仅独立全新性能输出')
    for p in (output,*output.parents):
        if p.exists():require(not p.is_symlink() and not getattr(p.lstat(),'st_file_attributes',0)&0x400,'输出禁止联接')
    output.mkdir(parents=True);write(output/'started.json',dict(status='benchmark_started_not_formal_training',config_sha256=sha(args.config),formal_updates=0))
    initial=torch.load(context['initialization'],map_location='cpu',weights_only=False)
    context=deepcopy(context);context['bindings']=dict(benchmark_scope='ABBA64_GPU_prefetch_not_formal_arm',source_v5_bindings=context['bindings']);schedule=context['schedule'];steps=c['steps']
    def setup():
        random.seed(20261024);np.random.seed(20261024);torch.manual_seed(20261024);torch.cuda.manual_seed_all(20261024)
        m=map_pose_xy(deepcopy(initial['model']).float()).to('cuda:0');m.args=copy(DEFAULT_CFG);m.args.pose=12.
        g=configure_pose_only(m);obj=SeparateDomainLocationObjective(m,freeze_guard=g)
        opt=torch.optim.SGD((p for p in m.parameters() if p.requires_grad),lr=.0001,momentum=.9,weight_decay=0.)
        ema=ModelEMA(m,decay=.9999,tau=2000.)
        real=numeric.BASE.CachedDataset(LocationPoseDataset(context['real_jsonl'],640,verify_image_sha256=True),1536*1024**2)
        synthetic=numeric.BASE.CachedDataset(VirtualCropDataset(context['synthetic_jsonl']),1536*1024**2)
        return m,g,obj,opt,ema,real,synthetic
    # 用独立模型做两次纯forward/backward预热；不SGD、不写正式曝光。
    model,guard,objective,opt,ema,real,synthetic=setup()
    def pack(data,indices):
        batch=LocationPoseDataset.collate_fn([data[i] for i in indices]);batch={k:v.to('cuda:0') if isinstance(v,torch.Tensor) else v for k,v in batch.items()};batch['img']=batch['img'].float()/255.;return batch
    for _ in range(2):
        opt.zero_grad(set_to_none=True);objective(pack(real,schedule[0]['real_indices']),pack(synthetic,[schedule[0]['synthetic_index']])).loss.backward()
    torch.cuda.synchronize();objective.close();guard.close();del model,guard,objective,opt,ema,real,synthetic;gc.collect();torch.cuda.empty_cache()
    results=[]
    for trial,mode in enumerate(c['order']):
        trialroot=output/f'{trial}_{mode}';trialroot.mkdir();wall=time.perf_counter()
        model,guard,objective,opt,ema,real,synthetic=setup();wrappers=[]
        real_view,synthetic_view=real,synthetic
        if mode=='prefetch':
            real_view=PrefetchedView(real,[i for r in schedule[:steps] for i in r['real_indices']]);synthetic_view=PrefetchedView(synthetic,[r['synthetic_index'] for r in schedule[:steps]]);wrappers=[real_view,synthetic_view]
        torch.cuda.reset_peak_memory_stats()
        try:
            for wrapper in wrappers:wrapper.start()
            value=numeric.train_loop(model,objective,opt,ema,guard,real_view,synthetic_view,schedule,context,trialroot,stop_after=steps)
            torch.cuda.synchronize();wall=time.perf_counter()-wall
            hashes=dict(model=numeric.BASE.state_hash(model),ema=numeric.BASE.state_hash(ema.ema),exposure_chain=value['exposure_chain_sha256'])
            require(value['completed_updates']==steps,'基准更新不完整')
        finally:
            for wrapper in wrappers:wrapper.close()
            objective.close();guard.close()
        row=dict(trial=trial,mode=mode,actual_benchmark_updates=steps,formal_updates=0,real_exposures=3*steps,synthetic_exposures=steps,
            loop_seconds=value['elapsed_seconds'],wall_including_setup_seconds=wall,checkpoint_seconds=value['checkpoint_seconds'],hashes=hashes,
            GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2,GPU_peak_reserved_MiB=torch.cuda.max_memory_reserved()/1024**2,
            prefetch_stats=[w.stream.stats for w in wrappers],real_cache=dict(hits=real.hits,misses=real.misses,bytes=real.bytes),synthetic_cache=dict(hits=synthetic.hits,misses=synthetic.misses,bytes=synthetic.bytes))
        results.append(row);write(trialroot/'benchmark_receipt.json',row)
        del model,guard,objective,opt,ema,real,synthetic,real_view,synthetic_view,wrappers;gc.collect();torch.cuda.empty_cache()
    exact=all(r['hashes']==results[0]['hashes'] for r in results)
    sync=sum(r['wall_including_setup_seconds'] for r in results if r['mode']=='sync')/2
    prefetch=sum(r['wall_including_setup_seconds'] for r in results if r['mode']=='prefetch')/2
    report=dict(schema='GPU_prefetch_ABBA_benchmark_result_v1',status='completed_exact' if exact else 'completed_NOT_numerically_equal_reject_adoption',
        order=c['order'],steps_per_trial=steps,trials=results,all_model_EMA_and_exposure_chain_exact=exact,sync_mean_seconds=sync,prefetch_mean_seconds=prefetch,speedup_ratio=sync/prefetch,
        relative_wall_time_reduction=(sync-prefetch)/sync,formal_optimizer_updates=0,diagnostic_optimizer_updates=4*steps,warmup_backward_passes=2,warmup_optimizer_updates=0,
        torch_CPU_threads=4,OpenCV_threads=1,precision='same_FP32_tensor_path_as_v5_no_new_AMP_TF32_changes',matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,cudnn_allow_tf32=torch.backends.cudnn.allow_tf32,
        images_copied=False,final_test116187_read=False,limits=['64_step_finite_benchmark_not_full1000','ABBA_mitigates_OS_cache_and_clock_order_drift_not_eliminates_it','not_a_formal_training_arm','guard_checkpoint_and_per_step_IO_kept'])
    write(output/'report.json',report);print(json.dumps(dict(output=str(output/'report.json'),speedup_ratio=sync/prefetch,exact=exact)))

if __name__=='__main__':main()
