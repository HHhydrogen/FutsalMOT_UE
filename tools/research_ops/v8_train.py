"""v8单臂薄Trainer候选：窗口预算、共享R、无AMP、无隐式重放。默认只读。"""
import argparse
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
BUNDLE=Path(__file__).resolve().parents[2];sys.path[:0]=[str(BUNDLE/'python/src'),str(BUNDLE/'tools/performance')]
RESEARCH=Path('D:/projects/FutsalMOT_Research');ARMS=('motion_R','motion_RS','pose_R','pose_RS');GAMES=('game4','game6','game9')
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def model_sha(model):
    digest=hashlib.sha256()
    for key,value in sorted(model.state_dict().items()):digest.update(key.encode());digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()
def checked(ref):
    path=Path(ref['path']).resolve();require(path.is_file() and sha(path)==ref['sha256'],'输入绑定变化:'+str(path));return path

def replace(source,target):
    for i,delay in enumerate((.05,.1,.2,.4,.8,0)):
        try:os.replace(source,target);return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32) or i==5:raise
            time.sleep(delay)
def atomic(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.tmp');require(not tmp.exists(),'已有partial，拒绝覆盖')
    with tmp.open('x',encoding='utf-8') as stream:stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())
    replace(tmp,path)
def rows(path):return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]
def domain_loss(model,windows):
    """一个domain一次前向，每window先BCE均值，再domain均值，不能按pair加权。"""
    import torch
    from torch.nn import functional as F
    counts=[len(window['labels']) for window in windows];require(all(n>0 for n in counts),'all-unknown窗口不得进入预算')
    device=next(model.parameters()).device;x=torch.cat([window['x'] for window in windows]).to(device);y=torch.cat([window['labels'] for window in windows]).to(device)
    losses=F.binary_cross_entropy_with_logits(model(x).reshape(-1),y,reduction='none');return torch.stack([part.mean() for part in losses.split(counts)]).mean()

class FeatureCache:
    def __init__(self,pools,normalizer,use_pose,limit=256*1024*1024):self.pools=pools;self.normalizer=normalizer;self.use_pose=use_pose;self.limit=limit;self.cache=OrderedDict();self.bytes=0;self.peak=0
    def get(self,domain,uid):
        import torch
        from grf_ue_bridge.learned_association_features_v8 import features
        key=(domain,uid)
        if key in self.cache:value,size=self.cache.pop(key);self.cache[key]=(value,size);return value
        window=self.pools[domain][uid];known=[candidate for candidate in window['candidates'] if candidate['label'] is not None]
        require(known and all(type(candidate['label']) is int and candidate['label'] in (0,1) for candidate in known),'pool不得有all-unknown窗口/非法label')
        x=[self.normalizer.transform(features(window['history'],candidate['prediction']),use_pose=self.use_pose) for candidate in known]
        value=dict(x=torch.tensor(x,dtype=torch.float32),labels=torch.tensor([candidate['label'] for candidate in known],dtype=torch.float32),candidate_pairs=len(window['candidates']),known_pairs=len(known),window_uid=uid)
        size=sum(item.numel()*item.element_size() for item in (value['x'],value['labels']))
        if size<=self.limit:
            while self.cache and self.bytes+size>self.limit:_,(_,previous)=self.cache.popitem(last=False);self.bytes-=previous
            self.cache[key]=(value,size);self.bytes+=size;self.peak=max(self.peak,self.bytes)
        return value

def validate(config_path,fold,seed,arm):
    cfg=read(config_path);require(cfg['schema']=='futsalmot_learned_association_training_v8' and fold in GAMES and seed in (20261024,20261025,20261026) and arm in ARMS,'fold/seed/arm/scope不符')
    require(cfg['parameters']==dict(updates=1000,real_windows_per_update=3,synthetic_windows_RS=1,synthetic_alpha=1/3,lr=.001,weight_decay=.0001,hidden=[64,32],amp=False,checkpoint_interval=50,prefetch=2,cache_bytes=268435456),'禁止改预算/精度/超参')
    manifest=read(checked(cfg['bundle_manifest']))
    require(Path(__file__).resolve()==Path(cfg['bundle'])/'tools/research_ops/v8_train.py','执行代码仅DResearch bundle')
    for entry in manifest['files']:require(sha(Path(cfg['bundle'])/entry['path'])==entry['sha256'],'源码变化')
    refs=cfg['folds'][fold];real=rows(checked(refs['real_pool']));synthetic=rows(checked(cfg['synthetic_pool']));require(len(real)==len(synthetic)==1000,'每pool1000固定窗口')
    require(all(w['domain']=='real' and w['game'] in GAMES and w['game']!=fold for w in real),'LO(G)O heldout泄漏')
    require(all(w['domain']=='synthetic' and w['game']=='synthetic1048' for w in synthetic),'只准1048蓝合成')
    for window in real+synthetic:require(any(c['label'] is not None for c in window['candidates']),'不准all-unknown窗口充预算')
    table=read(checked(refs['exposures'][str(seed)]));require(len(table['real'])==3000 and len(table['synthetic'])==1000,'窗口曝光数变化')
    real_uids={w['window_uid'] for w in real};s_uids={w['window_uid'] for w in synthetic}
    for epoch in range(3):
        segment=table['real'][epoch*1000:(epoch+1)*1000];require({row['window_uid'] for row in segment}==real_uids and all(row['domain']=='real' and row['epoch']==epoch for row in segment),'R每epoch必须同1000窗完整一次')
    require({row['window_uid'] for row in table['synthetic']}==s_uids and len({row['window_uid'] for row in table['synthetic']})==1000 and all(row['domain']=='synthetic' and row['epoch']==0 for row in table['synthetic']),'S必须1000窗一次')
    return cfg,dict(real={w['window_uid']:w for w in real},synthetic={w['window_uid']:w for w in synthetic}),table

def train(config_path,fold,seed,arm,output,device,resume):
    wall_started=time.perf_counter()
    import torch
    from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer,make_model
    from ordered_prefetch import OrderedPrefetch
    cfg,pools,table=validate(config_path,fold,seed,arm);require(cfg.get('training_authorized') is True and cfg.get('approved_by')=='root','root尚未冻结训练准入')
    output=Path(output).resolve();require(RESEARCH/'pose/learned_association_v8' in output.parents,'输出仅DResearch/v8')
    require((output/'last.pt').is_file() if resume else not output.exists(),'新run或显式last续跑，不覆盖partial')
    require(device in ('cpu','cuda:0'),'设备须显式');torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    normalizer=FeatureNormalizer.from_state(read(checked(cfg['folds'][fold]['normalizer'])));model=make_model(seed).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    initialization_sha=model_sha(model);r_uid_chain=hashlib.sha256(canonical([r['window_uid'] for r in table['real']]).encode()).hexdigest()
    binding=dict(protocol_sha256=sha(config_path),fold=fold,seed=seed,arm=arm,normalizer_sha256=cfg['folds'][fold]['normalizer']['sha256'],initialization_sha256=initialization_sha,R_window_UID_chain_sha256=r_uid_chain);completed=0;chain='0'*64
    if resume:
        require(not list(output.glob('*.tmp')),'partial保留，禁止猜测恢复');saved=torch.load(output/'last.pt',map_location='cpu',weights_only=False);exposures=rows(output/'exposures.jsonl') if (output/'exposures.jsonl').is_file() else []
        require(saved['schema']=='v8_learned_association_checkpoint' and saved['binding']==binding and len(exposures)==saved['completed_updates'],'超last曝光禁止重放')
        transaction=read(output/'update_transaction.json') if (output/'update_transaction.json').exists() else None
        require((saved['completed_updates']==0 and transaction is None) or (transaction is not None and transaction['status']=='committed') and transaction['completed_updates']==saved['completed_updates'],'未提交更新禁止重放')
        for i,row in enumerate(exposures):value=dict(row);stored=value.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(value)).encode()).hexdigest();require(stored==chain and row['update_index']==i,'曝光链变化')
        require(saved['exposure_chain']==chain and saved['actual_dtype']=='float32' and all(value.dtype==torch.float32 for value in saved['model'].values()),'last曝光链/精度不符');completed=saved['completed_updates'];model.load_state_dict(saved['model']);optimizer.load_state_dict(saved['optimizer'])
        for state in optimizer.state.values():
            for key,value in state.items():
                if torch.is_tensor(value) and key!='step':state[key]=value.to(device)
    require(completed<1000,'完成run不可重训');output.mkdir(parents=True,exist_ok=resume)
    def checkpoint():
        temporary=output/'last.pt.tmp';require(not temporary.exists(),'partial保留')
        with temporary.open('xb') as stream:torch.save(dict(schema='v8_learned_association_checkpoint',binding=binding,completed_updates=completed,planned_updates=1000,exposure_chain=chain,model={k:v.detach().cpu().clone() for k,v in model.state_dict().items()},optimizer=optimizer.state_dict(),normalizer=normalizer.state(),actual_dtype='float32'),stream);stream.flush();os.fsync(stream.fileno())
        replace(temporary,output/'last.pt')
    if completed==0:checkpoint()
    mixed=arm.endswith('_RS');cache=FeatureCache(pools,normalizer,arm.startswith('pose_'));stop=[False];previous=signal.signal(signal.SIGINT,lambda *args:stop.__setitem__(0,True))
    def load(index):
        real=table['real'][3*index:3*index+3];synthetic=[table['synthetic'][index]] if mixed else []
        return dict(real=[cache.get('real',row['window_uid']) for row in real],synthetic=[cache.get('synthetic',row['window_uid']) for row in synthetic],r=real,s=synthetic,index=index)
    try:
        with OrderedPrefetch(load,range(completed,1000),capacity=2,resource=cache) as stream:
            for batch in stream:
                if stop[0]:break
                index=batch['index'];require(index==completed,'更新顺序不符');atomic(output/'update_transaction.json',dict(status='started_not_committed',update_index=index,completed_updates_before=completed))
                optimizer.zero_grad(set_to_none=True);real_loss=domain_loss(model,batch['real']);synthetic_loss=domain_loss(model,batch['synthetic']) if mixed else None;loss=real_loss+synthetic_loss/3 if mixed else real_loss
                require(torch.isfinite(loss).item(),'loss非有限');loss.backward();require(all(p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters()),'梯度非有限');optimizer.step();completed+=1
                record=dict(update_index=index,actual_update=completed,real=batch['r'],synthetic=batch['s'],real_windows=3,synthetic_windows=int(mixed),real_pair_exposures=sum(w['candidate_pairs'] for w in batch['real']),synthetic_pair_exposures=sum(w['candidate_pairs'] for w in batch['synthetic']),real_known_pairs=sum(w['known_pairs'] for w in batch['real']),synthetic_known_pairs=sum(w['known_pairs'] for w in batch['synthetic']),loss=float(loss.detach()),real_loss=float(real_loss.detach()),synthetic_loss=float(synthetic_loss.detach()) if mixed else None)
                chain=hashlib.sha256((chain+canonical(record)).encode()).hexdigest()
                with (output/'exposures.jsonl').open('a',encoding='utf-8') as handle:handle.write(canonical(dict(record,chain_sha256=chain))+'\n');handle.flush();os.fsync(handle.fileno())
                atomic(output/'update_transaction.json',dict(status='committed',completed_updates=completed,update_index=index,chain=chain))
                if completed%50==0:checkpoint()
        checkpoint()
    finally:signal.signal(signal.SIGINT,previous)
    atomic(output/'run_receipt.json',dict(schema='v8_window_training_run',status='complete' if completed==1000 else 'safely_paused',binding=binding,completed_updates=completed,planned_updates=1000,real_window_exposures=completed*3,synthetic_window_exposures=completed*int(mixed),budget_unit='window_not_image',exposure_chain=chain,checkpoint='last1000_no_best',checkpoint_sha256=sha(output/'last.pt'),amp=False,feature_cache_peak_bytes=cache.peak,prefetch_capacity=2,prefetch=stream.stats,wall_seconds_including_validation_and_checkpoint=time.perf_counter()-wall_started,device=device,torch_version=torch.__version__,device_name=torch.cuda.get_device_name(0) if device=='cuda:0' else 'CPU',resumed=resume))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--fold',choices=GAMES,required=True);parser.add_argument('--seed',type=int,required=True);parser.add_argument('--arm',choices=ARMS,required=True);parser.add_argument('--device',choices=('cpu','cuda:0'),default='cpu');parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    if not args.execute:cfg,pools,table=validate(args.config,args.fold,args.seed,args.arm);print(json.dumps(dict(status='readonly_v8_training_candidate',actual_updates=0,real_windows=3000,synthetic_RS_windows=1000)));return
    runtime=RESEARCH/'pose/learned_association_v8/_runtime'
    for key,folder in [('TMP','tmp'),('TEMP','tmp'),('TORCH_HOME','torch'),('YOLO_CONFIG_DIR','ultralytics')]:path=runtime/folder;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    train(args.config,args.fold,args.seed,args.arm,args.output,args.device,args.resume)
if __name__=='__main__':main()
