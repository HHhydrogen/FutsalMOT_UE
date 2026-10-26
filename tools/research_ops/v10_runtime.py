"""v10独立训练/检查点身份；只读复用冻结v9/v8数值，不调用旧train。"""
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
R=Path('D:/projects/FutsalMOT_Research');EXPERIMENT=R/'pose/multiseed_v10_a01'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026)
REGIMES=('balanced','hard_enriched');METHODS=('motion','motion_residual','gated')
PARAMETERS=dict(updates=1000,R_per_step=3,S_per_step=1,S_alpha=1/3,lr=.001,weight_decay=.0001,
                amp=False,prefetch=2,cache_bytes=268435456,checkpoint_interval=50,actual_dtype='float32',selection='last1000_no_best_not_EMA')


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def rows(path):return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def checked(ref):
    path=Path(ref['path']);require(path.is_file() and sha(path)==ref['sha256'],'来源SHA改变：'+str(path));return path


def expected_matrix():
    return [dict(fold=f,seed=s,pool=p,method=m) for f in FOLDS for s in SEEDS for p in REGIMES for m in METHODS]


def validate_matrix(cfg):
    require(cfg.get('schema')=='v10_recorded_association_training_v1' and cfg.get('training_matrix')==expected_matrix()
            and cfg.get('parameters')==PARAMETERS and cfg.get('test116187_sealed') is True,
            '必须固定54组/1000更新/3000R+1000S/完整记录及测试封存')


def storage():
    spec=importlib.util.spec_from_file_location('v10_runtime_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def validate_protocol(path):
    cfg=read(path);validate_matrix(cfg)
    require(cfg.get('approved_by')=='root' and cfg.get('training_authorized') is True
            and Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','缺独立v10冻结训练准入')
    st=storage();st.physical_child(ROOT,R/'code')
    for entry in read(checked(cfg['bundle_manifest']))['files']:
        physical=st.physical_child(ROOT/entry['path'],ROOT)
        require(sha(physical)==entry['sha256'],'新执行源码改变')
    admission=read(checked(cfg['admission']))
    require(admission['training_authorized'] is True and admission['approved_by']=='root'
            and admission['pool_complete']==cfg['pool_complete'] and admission['test116187_read'] is False,
            '新窗口/训练准入链不同')
    complete=read(checked(cfg['pool_complete']))
    require(complete['status']=='complete_two_pools_not_training_authorized' and complete['pools']==cfg['synthetic_pools']
            and complete['external_validation_used_for_training'] is False and complete['test_read'] is False,
            '实际两池尚未完整或来源改变')
    return cfg


def load_numeric(cfg):
    old_path=checked(cfg['v9_protocol']);old=read(old_path);bundle=Path(old['bundle'])
    require(old_path==R/'pose/pose_quality_v9/frozen_a01/protocol.json' and bundle.parent==R/'code','原数值来源身份不同')
    for entry in read(checked(old['bundle_manifest']))['files']:
        require(sha(bundle/entry['path'])==entry['sha256'],'原数值闭包改变')
    sys.path[:0]=[str(bundle/'python/src'),str(bundle/'tools/research_ops'),str(bundle/'tools/performance'),str(R/'runtime_dependencies')]
    spec=importlib.util.spec_from_file_location('v10_original_v9_numeric',bundle/'tools/research_ops/v9_train.py')
    numeric=importlib.util.module_from_spec(spec);sys.modules[spec.name]=numeric;spec.loader.exec_module(numeric)
    require(Path(inspect.getfile(numeric.make_model))==bundle/'python/src/grf_ue_bridge/quality_residual_association_v9.py'
            and Path(inspect.getfile(numeric.domain_loss))==bundle/'tools/research_ops/v8_train.py','误导入非冻结模型/损失')
    import v8_train as base
    require(Path(base.__file__)==bundle/'tools/research_ops/v8_train.py','强motion数值来源不同')
    return numeric,base,old


def validate_exposures(real,synthetic,table,old_table,fold):
    require(len(real)==len(synthetic)==1000 and len({w['window_uid'] for w in real})==1000
            and len({w['window_uid'] for w in synthetic})==1000,'每池须1000唯一窗')
    require(table['real']==old_table['real'] and len(table['real'])==3000 and len(table['synthetic'])==1000,'原3000R逐值顺序必须复用')
    require(all(w['domain']=='real' and w['game'] in FOLDS and w['game']!=fold for w in real),'R来源含留出比赛')
    require(all(w['domain']=='synthetic' and w['synthetic_seed'] in (1042,1044,1048,1131) for w in synthetic),'S只能四个登记训练运动')
    from collections import Counter
    require(Counter(w['synthetic_seed'] for w in synthetic)=={s:250 for s in (1042,1044,1048,1131)},'每seed250配额改变')
    r={w['window_uid']:w for w in real};s={w['window_uid']:w for w in synthetic}
    require({x['window_uid'] for x in table['synthetic']}==set(s)
            and all(x['domain']=='synthetic' and x['epoch']==0 for x in table['synthetic']),'S不重复补足且一次完整曝光')
    for epoch in range(3):
        segment=table['real'][epoch*1000:(epoch+1)*1000]
        require({x['window_uid'] for x in segment}==set(r) and all(x['domain']=='real' and x['epoch']==epoch for x in segment),'R epoch必须完整')
    for domain,pool in (('real',r),('synthetic',s)):
        for entry in table[domain]:
            window=pool[entry['window_uid']];known=[c for c in window['candidates'] if c['label'] is not None]
            require(known and all(type(c['label']) is int and c['label'] in (0,1) for c in known)
                    and entry['candidate_pairs']==len(window['candidates']) and entry['labelled_pairs']==len(known),'实际pair或监督预算不同')
    return dict(real=r,synthetic=s)


def validate_job(config,fold,seed,pool,method):
    cfg=validate_protocol(config);require(dict(fold=fold,seed=seed,pool=pool,method=method) in cfg['training_matrix'],'未登记组别')
    numeric,base,old=load_numeric(cfg);ref=cfg['folds'][fold]
    require(ref==old['folds'][fold],'R池/标准化/质量尺度/原曝光必须逐值复用')
    real=rows(checked(ref['real_pool']));synthetic=rows(checked(cfg['synthetic_pools'][pool]))
    old_table=read(checked(ref['exposures'][str(seed)]));table=read(checked(cfg['exposures'][pool][fold][str(seed)]))
    pools=validate_exposures(real,synthetic,table,old_table,fold)
    quality=read(checked(ref['quality_scale']))
    require(quality['fit_scope']=='positive known-label train_R only' and quality['train_pool']==ref['real_pool'],'质量尺度不能从S/val拟合')
    normalizer=numeric.FeatureNormalizer.from_state(read(checked(ref['normalizer'])))
    adapter=numeric.Adapter(normalizer,quality['shape_change_scale'])
    reference=read(checked(cfg['reference_R'][method][fold][str(seed)]['training_receipt']))
    checkpoint=cfg['reference_R'][method][fold][str(seed)]['checkpoint']
    checked(checkpoint)
    require(reference['status']=='complete' and reference['completed_updates']==1000
            and reference['real_window_exposures']==3000 and reference['synthetic_window_exposures']==0
            and reference['checkpoint_sha256']==checkpoint['sha256'],'纯R历史参考预算/权重不完整')
    r_chain=hashlib.sha256(canonical([x['window_uid'] for x in table['real']]).encode()).hexdigest()
    require(reference['binding']['R_window_UID_chain_sha256']==r_chain,'纯R参考真实顺序不同')
    return cfg,numeric,base,pools,table,normalizer,adapter,reference


def audit_steps(logs,table):
    require(len(logs)==1000,'完整1000次真实更新缺失');chain='0'*64
    for index,entry in enumerate(logs):
        row=dict(entry);expected=row.pop('chain_sha256');chain=hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        require(chain==expected and row['actual_update']==index+1 and row['update_index']==index
                and row['R_windows']==3 and row['S_windows']==1 and row['real']==table['real'][index*3:index*3+3]
                and row['synthetic']==table['synthetic'][index:index+1],'实际更新链/曝光表不一致')
    return chain


def complete_model(config,run):
    import torch
    cfg=validate_protocol(config);numeric,base,_=load_numeric(cfg);run=Path(run)
    receipt=read(run/'run_receipt.json');complete=read(run/'training_complete.json');binding=receipt['binding']
    require(receipt['schema']=='v10_full_recorded_training_run_v1' and receipt['status']==complete['status']=='complete'
            and receipt['completed_updates']==complete['actual_updates']==1000 and binding['protocol_sha256']==sha(config)
            and receipt['full_training_record']==sha(run/'training_complete.json'),
            'v10完整记录last1000身份缺失')
    job={k:binding[k] for k in ('fold','seed','pool','method')};require(job in cfg['training_matrix'],'模型不属事前矩阵')
    table=read(checked(cfg['exposures'][binding['pool']][binding['fold']][str(binding['seed'])]))
    chain=audit_steps(rows(run/'steps.jsonl'),table);last=read(run/'last_checkpoint.json')
    require(complete['totals']['R_windows']==3000 and complete['totals']['S_windows']==1000
            and complete['exposure_chain']==last['exposure_chain']==chain
            and complete['steps_sha256']==sha(run/'steps.jsonl') and last['completed_updates']==1000
            and len(complete['checkpoints'])==21
            and {c['completed_updates'] for c in complete['checkpoints']}==set(range(0,1001,50)),
            '实际预算/定期检查点链不完整')
    transaction=read(run/'update_transaction.json')
    require(transaction['status']=='committed' and transaction['completed_updates']==1000
            and transaction['chain_sha256']==chain,'末次数学更新事务未闭合')
    for point in complete['checkpoints']:
        require(Path(point['path'])==run/'checkpoints'/('step_%04d.pt'%point['completed_updates'])
                and Path(point['path']).is_file(),'完整定期检查点缺失或路径不同')
    saved=torch.load(checked(last),map_location='cpu',weights_only=False)
    require(saved['schema']=='full_training_checkpoint_v1' and saved['completed_updates']==1000
            and saved['binding']==binding and saved['exposure_chain']==chain
            and all(k in saved for k in ('model','optimizer','rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda'))
            and saved['rng_torch_cuda'] is not None and saved['extra']['schema']=='v10_association_method_state_v1'
            and saved['extra']['method']==binding['method']
            and hashlib.sha256(canonical(saved['extra']).encode()).hexdigest()==binding['method_state_sha256']
            and saved['extra']['actual_dtype']=='float32' and all(v.dtype==torch.float32 for v in saved['model'].values()),'完整FP32模型/优化器/RNG不符')
    if binding['method']=='motion':
        from grf_ue_bridge.learned_association_model_v8 import make_model,FeatureNormalizer
        model=make_model(binding['seed']);adapter=FeatureNormalizer.from_state(saved['extra']['normalizer'])
    else:model=numeric.make_model(binding['seed'],binding['method']);adapter=numeric.Adapter.from_state(saved['extra']['adapter'])
    require(base.model_sha(model)==binding['initialization_sha256'],'新模型初始化身份改变')
    model.load_state_dict(saved['model']);model.eval()
    return cfg,numeric,model,adapter,binding
