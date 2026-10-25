"""v9同真实窗口预算的有界质量残差训练；新协议，不改v8。"""
import argparse,hashlib,json,os,signal,sys,time
from collections import OrderedDict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'python/src'),str(ROOT/'tools/research_ops'),str(ROOT/'tools/performance')]
from v8_train import read,sha,checked,canonical,require,atomic,replace,rows,model_sha,domain_loss
from grf_ue_bridge.quality_residual_association_v9 import Adapter,make_model,VARIANTS,AUGMENTATION
from grf_ue_bridge.pose_quality_features_v9 import perturb
from grf_ue_bridge.learned_association_features_v8 import features
from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer
R=Path('D:/projects/FutsalMOT_Research');V=R/'pose/pose_quality_v9'
def validate(config,fold,seed,variant,regime):
    cfg=read(config);require(cfg['schema']=='v9_quality_residual_control','v9独立协议')
    require(dict(fold=fold,seed=seed,variant=variant,regime=regime) in cfg['training_matrix'],'未登记组别')
    require(cfg['parameters']==dict(updates=1000,R_per_step=3,S_per_RS_step=1,S_alpha=1/3,lr=.001,weight_decay=.0001,hidden_residual=32,delta_logit_bound=.5,amp=False,prefetch=2,cache_bytes=268435456,checkpoint_interval=50),'预算/数学禁止修改')
    require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v9_train.py','只执行bundle')
    for entry in read(checked(cfg['bundle_manifest']))['files']:require(sha(Path(cfg['bundle'])/entry['path'])==entry['sha256'],'源闭包改变')
    old=read(checked(cfg['v8_protocol']));ref=cfg['folds'][fold];r=rows(checked(ref['real_pool']));s=rows(checked(cfg['synthetic_pool']));table=read(checked(ref['exposures'][str(seed)]))
    require(len(r)==len(s)==1000 and len(table['real'])==3000 and len(table['synthetic'])==1000,'唯一窗口池/曝光不符')
    require(all(w['game']!=fold and w['domain']=='real' for w in r) and all(w['game']=='synthetic1048' for w in s),'比赛/S来源越界')
    for epoch in range(3):require({x['window_uid'] for x in table['real'][epoch*1000:(epoch+1)*1000]}=={w['window_uid'] for w in r},'R epoch缺窗')
    require(len({x['window_uid'] for x in table['synthetic']})==1000 and all(any(c['label'] is not None for c in w['candidates']) for w in r+s),'无监督/重复S充预算')
    require(cfg['folds'][fold]['real_pool']==old['folds'][fold]['real_pool'] and cfg['folds'][fold]['exposures']==old['folds'][fold]['exposures'],'原R顺序未复用')
    require(cfg['synthetic_pool']==old['synthetic_pool'] and ref['normalizer']==old['folds'][fold]['normalizer'] and cfg['source_config']==old['source_config'],'原数据/标准化来源改变')
    quality=read(checked(ref['quality_scale']));require(quality['fit_scope']=='positive known-label train_R only' and quality['train_pool']==ref['real_pool'],'门控尺度不可从heldout拟合')
    adapter=Adapter(FeatureNormalizer.from_state(read(checked(ref['normalizer']))),quality['shape_change_scale'])
    return cfg,dict(real={w['window_uid']:w for w in r},synthetic={w['window_uid']:w for w in s}),table,adapter
class Cache:
    def __init__(self,pools,adapter,variant,seed):self.pools=pools;self.adapter=adapter;self.variant=variant;self.seed=seed;self.cache=OrderedDict();self.observations=OrderedDict();self.bytes=0;self.peak=0
    def observation(self,domain,record,epoch):
        if AUGMENTATION[self.variant]=='clean':return record
        key=(domain,record['uid'],epoch)
        if key in self.observations:value=self.observations.pop(key);self.observations[key]=value;return value
        _,value=perturb([],record,AUGMENTATION[self.variant],seed=self.seed,context=f'{domain}|{epoch}')
        self.observations[key]=value
        while len(self.observations)>4096:self.observations.popitem(last=False)
        return value
    def get(self,domain,row):
        import torch
        key=(domain,row['window_uid'],row['epoch'])
        if key in self.cache:value,size=self.cache.pop(key);self.cache[key]=(value,size);return value
        w=self.pools[domain][row['window_uid']];vectors=[];labels=[]
        history=[self.observation(domain,r,row['epoch']) for r in w['history']]
        for c in w['candidates']:
            if c['label'] is None:continue
            prediction=self.observation(domain,c['prediction'],row['epoch'])
            vectors.append(self.adapter.transform(features(history,prediction)));labels.append(c['label'])
        require(labels,'不能跳过R窗口');value=dict(x=torch.tensor(vectors,dtype=torch.float32),labels=torch.tensor(labels,dtype=torch.float32),known_pairs=len(labels),candidate_pairs=len(w['candidates']))
        size=sum(value[k].numel()*value[k].element_size() for k in ('x','labels'))
        while self.cache and self.bytes+size>268435456:_,(_,previous)=self.cache.popitem(last=False);self.bytes-=previous
        self.cache[key]=(value,size);self.bytes+=size;self.peak=max(self.peak,self.bytes);return value
def train(config,fold,seed,variant,regime,output):
    start=time.perf_counter();import torch
    from ordered_prefetch import OrderedPrefetch
    cfg,pools,table,adapter=validate(config,fold,seed,variant,regime);require(cfg['approved_by']=='root' and cfg['training_authorized'] is True,'v9独立root训练准入');admission=read(checked(cfg['admission']));require(admission['training_authorized'] is True and admission['approved_by']=='root','不能复用旧授权');torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>1024**3,'GPU余量不足，不占用其他任务')
    output=Path(output).resolve();require(V in output.parents and not output.exists(),'全新run，partial不隐式重放');output.mkdir(parents=True)
    model=make_model(seed,variant).to('cuda:0');optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001);initialization=model_sha(model);r_chain=hashlib.sha256(canonical([x['window_uid'] for x in table['real']]).encode()).hexdigest()
    old_base=read(Path(cfg['v8_analysis']['path']).parents[1]/'runs'/fold/str(seed)/('motion_'+regime)/'training/run_receipt.json');base_initial=model_sha(model.base);require(base_initial==old_base['binding']['initialization_sha256'] and r_chain==old_base['binding']['R_window_UID_chain_sha256'],'初始motion或R窗口与强参考不一致')
    binding=dict(protocol_sha256=sha(config),fold=fold,seed=seed,variant=variant,regime=regime,initialization_sha256=initialization,motion_base_initialization_sha256=base_initial,R_window_UID_chain_sha256=r_chain,adapter_sha256=hashlib.sha256(canonical(adapter.state()).encode()).hexdigest())
    completed=0;chain='0'*64;stop=[False];previous=signal.signal(signal.SIGINT,lambda *a:stop.__setitem__(0,True));cache=Cache(pools,adapter,variant,seed)
    def checkpoint():
        tmp=output/'last.pt.tmp';require(not tmp.exists(),'保留未知partial')
        with tmp.open('xb') as f:torch.save(dict(schema='v9_quality_residual_checkpoint',binding=binding,completed_updates=completed,exposure_chain=chain,model={k:v.detach().cpu().clone() for k,v in model.state_dict().items()},optimizer=optimizer.state_dict(),adapter=adapter.state(),actual_dtype='float32'),f);f.flush();os.fsync(f.fileno())
        replace(tmp,output/'last.pt')
    def load(i):
        rr=table['real'][i*3:i*3+3];ss=[table['synthetic'][i]] if regime=='RS' else []
        return dict(index=i,r=rr,s=ss,real=[cache.get('real',r) for r in rr],synthetic=[cache.get('synthetic',s) for s in ss])
    checkpoint()
    try:
        with OrderedPrefetch(load,range(1000),capacity=2,resource=cache) as prefetch:
            for batch in prefetch:
                if stop[0]:break
                i=batch['index'];require(i==completed,'步序不符');atomic(output/'update_transaction.json',dict(status='started_not_committed',completed_updates_before=completed,update_index=i))
                optimizer.zero_grad(set_to_none=True);r_loss=domain_loss(model,batch['real']);s_loss=domain_loss(model,batch['synthetic']) if regime=='RS' else None;loss=r_loss+s_loss/3 if s_loss is not None else r_loss
                require(torch.isfinite(loss).item(),'非有限loss');loss.backward();gradients=[p.grad.reshape(-1) for p in model.parameters() if p.grad is not None];require(gradients and torch.isfinite(torch.cat(gradients)).all().item(),'非有限梯度');optimizer.step();completed+=1
                row=dict(update_index=i,actual_update=completed,real=batch['r'],synthetic=batch['s'],real_windows=3,synthetic_windows=int(regime=='RS'),real_pair_exposures=sum(w['candidate_pairs'] for w in batch['real']),synthetic_pair_exposures=sum(w['candidate_pairs'] for w in batch['synthetic']),real_known_pairs=sum(w['known_pairs'] for w in batch['real']),synthetic_known_pairs=sum(w['known_pairs'] for w in batch['synthetic']),loss=float(loss.detach()),real_loss=float(r_loss.detach()),synthetic_loss=float(s_loss.detach()) if s_loss is not None else None,augmentation=AUGMENTATION[variant])
                chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
                with (output/'exposures.jsonl').open('a',encoding='utf-8') as f:f.write(canonical(dict(row,chain_sha256=chain))+'\n');f.flush();os.fsync(f.fileno())
                atomic(output/'update_transaction.json',dict(status='committed',completed_updates=completed,update_index=i,chain=chain))
                if completed%50==0:checkpoint()
        checkpoint()
    finally:signal.signal(signal.SIGINT,previous)
    atomic(output/'run_receipt.json',dict(schema='v9_actual_window_training',status='complete' if completed==1000 else 'safely_paused',binding=binding,completed_updates=completed,real_window_exposures=3*completed,synthetic_window_exposures=completed*int(regime=='RS'),checkpoint_sha256=sha(output/'last.pt'),exposure_chain=chain,actual_dtype='float32',amp=False,checkpoint='last_no_best',prefetch=prefetch.stats,cache_peak_bytes=cache.peak,wall_seconds=time.perf_counter()-start,optimizer_replay=0,trainable_parameters=sum(p.numel() for p in model.parameters()),extra_S_not_equal_FLOPs=True))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--fold',choices=('game4','game6','game9'),required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--variant',choices=VARIANTS,required=True);p.add_argument('--regime',choices=('R','RS'),required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if a.execute:train(a.config,a.fold,a.seed,a.variant,a.regime,a.output)
    else:validate(a.config,a.fold,a.seed,a.variant,a.regime);print(json.dumps(dict(status='readonly_v9_preflight',new_updates=0)))
