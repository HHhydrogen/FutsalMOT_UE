"""C4000R独立身份与加载器：只复用旧数值，不借旧v10训练schema。"""
from collections import Counter
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
R=Path('D:/projects/FutsalMOT_Research');EXP=R/'pose/real_substitution_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);METHODS=('motion','gated')
PARAMETERS=dict(updates=1000,base_R_per_step=3,extra_R_per_step=1,S_per_step=0,extra_R_alpha=1/3,
    lr=.001,weight_decay=.0001,amp=False,prefetch=2,cache_bytes=268435456,checkpoint_interval=50,
    actual_dtype='float32',selection='last1000_no_best_not_EMA')

def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(ref):
    p=Path(ref['path']);require(p.is_file() and sha(p)==ref['sha256'],'来源SHA改变：'+str(p));return p
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def storage():return module('substitution_C_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
def matrix():return [dict(fold=f,seed=s,method=m) for f in FOLDS for s in SEEDS for m in METHODS]
def matrix_gate(c):
    require(c.get('schema')=='substitution_C4000R_training_v1' and c.get('training_matrix')==matrix()
        and c.get('parameters')==PARAMETERS and c.get('test116187_sealed') is True,'独立C矩阵/预算/测试封存改变')

def protocol(path):
    c=read(path);matrix_gate(c)
    require(c['approved_by']=='root' and c['training_authorized'] is True and Path(c['bundle'])==ROOT
        and ROOT.parent==R/'code','必须使用独立C执行bundle和新准入')
    st=storage();st.physical_child(ROOT,R/'code')
    for e in read(checked(c['bundle_manifest']))['files']:
        require(sha(st.physical_child(ROOT/e['path'],ROOT))==e['sha256'],'C执行源码变化')
    a=read(checked(c['admission']))
    require(a['training_authorized'] is True and a['approved_by']=='root' and a['test_read'] is False
        and a['extra_R_complete']==c['extra_R_complete'],'缺额外R独立训练准入')
    complete=read(checked(c['extra_R_complete']))
    require(complete['status']=='complete3_folds_extra_R1000_not_training_authorized'
        and complete['optimizer_updates']==0 and complete['test_read'] is False,'额外R输入来源不完整')
    plan=read(checked(c['analysis_plan']));checked(c['matches'])
    require(plan['schema']==c['analysis_schema'] and c['formal_equivalence_or_noninferiority'] is False,'不得增设等效/非劣效判定')
    old=read(checked(c['source_v10_protocol']))
    require(sha(c['source_v10_protocol']['path'])=='2a1fa8ecd0b48993289c859ec6e83c36bf987e9d7de9ccf44820c4a86f7be575'
        and c['folds']==old['folds'] and c['reference_R']=={m:old['reference_R'][m] for m in METHODS},'基础R/标准化/历史参考必须原值')
    for e in read(checked(old['bundle_manifest']))['files']:
        require(sha(Path(old['bundle'])/e['path'])==e['sha256'],'B历史数值/记录源码来源变化')
    return c

def numeric(c):
    old=read(checked(c['source_v10_protocol']));p=checked(old['v9_protocol']);v9=read(p);bundle=Path(v9['bundle'])
    require(sha(p)=='a659c061af4187ee49da4526a5dd765c32d6b9acfec506ec0cc233a9707759b6','旧数值协议不同')
    for e in read(checked(v9['bundle_manifest']))['files']:require(sha(bundle/e['path'])==e['sha256'],'旧数值闭包改变')
    sys.path[:0]=[str(bundle/'python/src'),str(bundle/'tools/research_ops'),str(bundle/'tools/performance'),str(R/'runtime_dependencies')]
    n=module('substitution_original_v9_numeric',bundle/'tools/research_ops/v9_train.py')
    import v8_train as b
    require(Path(inspect.getfile(n.make_model))==bundle/'python/src/grf_ue_bridge/quality_residual_association_v9.py'
        and Path(inspect.getfile(n.domain_loss))==bundle/'tools/research_ops/v8_train.py'
        and Path(b.__file__)==bundle/'tools/research_ops/v8_train.py','非冻结数值误导入')
    return n,b,old

def exposure_gate(base,extra,table,plan,fold):
    require(len(base)==len(extra)==1000 and len({w['window_uid'] for w in base})==1000
        and len({w['window_uid'] for w in extra})==1000,'每类1000唯一窗口')
    r={w['window_uid']:w for w in base};e={w['window_uid']:w for w in extra}
    require(not set(r)&set(e) and len(table['real'])==3000 and len(plan['extra_R'])==1000,'基础/额外R重叠或预算不同')
    require(all(w['domain']=='real' and w['game'] in FOLDS and w['game']!=fold for w in base+extra),'真实窗口来源越过heldout')
    require(Counter(w['game'] for w in extra)=={f:500 for f in FOLDS if f!=fold},'额外R两场各500配额改变')
    for epoch in range(3):
        part=table['real'][epoch*1000:(epoch+1)*1000]
        require({x['window_uid'] for x in part}==set(r) and all(x['epoch']==epoch and x['domain']=='real' for x in part),'基础R原三epoch不完整')
    require({x['window_uid'] for x in plan['extra_R']}==set(e)
        and all(x['epoch']==0 and x['domain']=='real' and x['source_allocation']=='extra_R' for x in plan['extra_R']),'额外R只能真实epoch0一次')
    for pool,entries in ((r,table['real']),(e,plan['extra_R'])):
        for x in entries:
            w=pool[x['window_uid']];known=[c for c in w['candidates'] if c['label'] is not None]
            require(known and all(type(c['label']) is int and c['label'] in (0,1) for c in known)
                and x['candidate_pairs']==len(w['candidates']) and x['labelled_pairs']==len(known),'实际all/known pair改变')
    return dict(real={**r,**e},synthetic={})

def job(config,fold,seed,method):
    c=protocol(config);require(dict(fold=fold,seed=seed,method=method) in c['training_matrix'],'未登记C组')
    n,b,old=numeric(c);ref=c['folds'][fold];table=read(checked(ref['exposures'][str(seed)]))
    ec=read(checked(c['extra_R_complete']))['folds'][fold];require(ec['base_R_normalizer_and_quality_unchanged']==ref,'基础来源改变')
    plan=read(checked(c['extra_exposures'][fold][str(seed)]));require(plan['base_real_table']==ref['exposures'][str(seed)],'基础R顺序未复用')
    pools=exposure_gate(rows(checked(ref['real_pool'])),rows(checked(ec['pool'])),table,plan,fold)
    quality=read(checked(ref['quality_scale']))
    require(quality['fit_scope']=='positive known-label train_R only' and quality['train_pool']==ref['real_pool'],'禁止额外R/val重拟合质量尺度')
    normalizer=n.FeatureNormalizer.from_state(read(checked(ref['normalizer'])));adapter=n.Adapter(normalizer,quality['shape_change_scale'])
    a=read(checked(c['reference_R'][method][fold][str(seed)]['training_receipt']))
    ap=checked(c['reference_R'][method][fold][str(seed)]['checkpoint'])
    require(a['status']=='complete' and a['completed_updates']==1000 and a['real_window_exposures']==3000
        and a['synthetic_window_exposures']==0 and a['checkpoint_sha256']==sha(ap),'A参考预算不符')
    bp=c['reference_B'][method][fold][str(seed)];br=read(checked(bp['training_receipt']))
    require(br['status']=='complete' and br['completed_updates']==1000 and br['real_window_exposures']==3000
        and br['synthetic_window_exposures']==1000 and br['binding']['protocol_sha256']==sha(c['source_v10_protocol']['path'])
        and br['binding']['method']==method and br['binding']['pool']=='balanced'
        and br['binding']['initialization_sha256']==a['binding']['initialization_sha256'],'B复用条件不符')
    checked(bp['checkpoint']);bc=read(checked(bp['training_complete']))
    require(bc['actual_updates']==1000 and br['full_training_record']==bp['training_complete']['sha256'],'B完整记录来源不符')
    chain=hashlib.sha256(canonical([x['window_uid'] for x in table['real']]).encode()).hexdigest()
    require(a['binding']['R_window_UID_chain_sha256']==br['binding']['R_window_UID_chain_sha256']==chain,'A/B基础R顺序改变')
    return c,n,b,pools,table,plan,normalizer,adapter,a

def model_and_cache(n,b,pools,normalizer,adapter,seed,method):
    if method=='motion':
        from grf_ue_bridge.learned_association_model_v8 import make_model
        model=make_model(seed);cache=b.FeatureCache(pools,normalizer,False)
    else:model=n.make_model(seed,method);cache=n.Cache(pools,adapter,method,seed)
    def get(row):return cache.get('real',row['window_uid']) if method=='motion' else cache.get('real',row)
    return model,cache,get

def batch_loader(table,plan,get):
    def load(i):
        rr=table['real'][i*3:i*3+3];ee=plan['extra_R'][i:i+1]
        return dict(index=i,r=rr,r_extra=ee,s=[],real=[get(x) for x in rr],extra_real=[get(x) for x in ee],synthetic=[])
    return load

def audit_steps(logs,table,plan):
    require(len(logs)==1000,'C未完成1000实际更新');chain='0'*64
    for i,entry in enumerate(logs):
        row=dict(entry);target=row.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        require(chain==target and row['actual_update']==i+1 and row['update_index']==i and row['R_windows']==4
            and row['S_windows']==0 and row['synthetic']==[]
            and row['real']==table['real'][i*3:i*3+3]+plan['extra_R'][i:i+1]
            and row['base_R_windows']==3 and row['extra_R_windows']==1,'C实际步链/基础及额外R顺序不符')
    return chain

def complete_model(config,run,all_checkpoints=False):
    import torch
    c=protocol(config);n,b,_=numeric(c);run=Path(run);receipt=read(run/'run_receipt.json');done=read(run/'training_complete.json');binding=receipt['binding']
    require(receipt['schema']=='substitution_C4000R_run_v1' and receipt['status']==done['status']=='complete'
        and done['schema']=='full_training_process_complete_v2_real_groups'
        and receipt['completed_updates']==done['actual_updates']==1000 and binding['protocol_sha256']==sha(config)
        and receipt['full_training_record']==sha(run/'training_complete.json'),'独立C完整记录身份不符')
    require({k:binding[k] for k in ('fold','seed','method')} in c['training_matrix'] and binding['regime']=='C4000R','C组身份不同')
    table=read(checked(c['folds'][binding['fold']]['exposures'][str(binding['seed'])]));plan=read(checked(c['extra_exposures'][binding['fold']][str(binding['seed'])]))
    logs=rows(run/'steps.jsonl');chain=audit_steps(logs,table,plan);last=read(run/'last_checkpoint.json');totals=done['totals']
    require(totals['R_windows']==4000 and totals['base_R_windows']==3000 and totals['extra_R_windows']==1000 and totals['S_windows']==0
        and done['exposure_chain']==last['exposure_chain']==chain and done['steps_sha256']==sha(run/'steps.jsonl')
        and last['completed_updates']==1000 and {x['completed_updates'] for x in done['checkpoints']}==set(range(0,1001,50)), 'C实际预算或检查点链未闭合')
    tx=read(run/'update_transaction.json');require(tx['status']=='committed' and tx['completed_updates']==1000 and tx['chain_sha256']==chain,'末次事务未提交')
    saved=None
    for point in done['checkpoints'] if all_checkpoints else [last]:
        p=checked(point);step=point['completed_updates'];x=torch.load(p,map_location='cpu',weights_only=False)
        require(p==run/'checkpoints'/('step_%04d.pt'%step) and x['schema']=='full_training_checkpoint_v2_real_groups'
            and x['completed_updates']==step and x['binding']==binding and x['exposure_chain']==('0'*64 if step==0 else logs[step-1]['chain_sha256'])
            and {'model','optimizer','rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda'}<=set(x)
            and x['rng_torch_cuda'] is not None and x['optimizer']['param_groups'] and (step==0 or x['optimizer']['state']),'C完整权重/优化器/RNG未闭合')
        if step==1000:saved=x
    require(saved is not None and saved['extra']['schema']=='substitution_C_method_state_v1'
        and hashlib.sha256(canonical(saved['extra']).encode()).hexdigest()==binding['method_state_sha256']
        and all(v.dtype==torch.float32 for v in saved['model'].values()),'C方法状态/FP32不同')
    if binding['method']=='motion':
        from grf_ue_bridge.learned_association_model_v8 import make_model
        model=make_model(binding['seed']);adapter=n.FeatureNormalizer.from_state(saved['extra']['normalizer'])
    else:model=n.make_model(binding['seed'],'gated');adapter=n.Adapter.from_state(saved['extra']['adapter'])
    require(b.model_sha(model)==binding['initialization_sha256'],'C初始化身份改变')
    model.load_state_dict(saved['model']);model.eval();return c,n,model,adapter,binding
