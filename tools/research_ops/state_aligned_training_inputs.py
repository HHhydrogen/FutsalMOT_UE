"""自由状态R输入和独立18臂曝光计划；复用原强motion的无增广特征路径。"""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=Path('D:/projects/FutsalMOT_Research')
EXPERIMENT=RESEARCH/'pose/state_aligned_training_a01'
SOURCE_PROTOCOL=RESEARCH/'pose/multiseed_v10_a01/training_frozen_a01/protocol.json'
SOURCE_PROTOCOL_SHA='2a1fa8ecd0b48993289c859ec6e83c36bf987e9d7de9ccf44820c4a86f7be575'
FOLDS=('game4','game6','game9');SEEDS=(20261024,20261025,20261026);REGIMES=('R','RS')
SOURCES={'SNMOT-060':'game4','SNMOT-097':'game6','SNMOT-151':'game9'}
PLAN_SCHEMA='state_aligned_R_exposure_plan_v1'
INPUT_STATUS='complete3_fold1000_unique_original_prediction_R_banks_not_training_authorized'
AUGMENTATION='none_original_strongmotion'

def require(ok,message):
    if not ok:raise ValueError(message)

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return h.hexdigest()
def physical(value):
    p=Path(os.path.abspath(value));require(RESEARCH in p.parents,'只允许物理DResearch来源')
    require(not any(s.lower()=='test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',s.lower()) for s in p.parts),'测试继续封存')
    for part in (p,*p.parents):
        if part.exists():require(not part.is_symlink() and not getattr(part.lstat(),'st_file_attributes',0)&0x400,'禁止链接/junction')
    return p
def checked(reference):
    p=physical(reference['path']);require(sha(p)==reference['sha256'],'输入来源SHA变化：'+str(p));return p
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def read_ref(reference):return read(checked(reference))
def rows(reference):
    with checked(reference).open(encoding='utf-8-sig') as f:return [json.loads(line) for line in f if line.strip()]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
def expected_matrix():return [dict(fold=f,seed=s,regime=r) for f in FOLDS for s in SEEDS for r in REGIMES]

def validate_pool(real,fold):
    require(fold in FOLDS and len(real)==1000 and len({w['window_uid'] for w in real})==1000,'每fold必须1000唯一R窗口')
    require(Counter(w['sequence'] for w in real)=={s:500 for s,g in SOURCES.items() if g!=fold},'只准允许两train来源各500')
    for w in real:
        meta=w['aligned_bank_metadata'];h=w['history'];c=w['candidates']
        require(w['domain']=='real' and SOURCES[w['sequence']]==w['game']!=fold and w['fps']==25,'真实来源/heldout边界不同')
        require(len(h)==3 and len({r['uid'] for r in h})==3 and len(c)>0 and len({v['prediction']['uid'] for v in c})==len(c),'历史/候选UID不唯一或不足')
        require(meta['teacher_regime']=='R' and meta['teacher_seed']==20261024 and meta['fold']==fold
            and meta['source_stage']=='high_score' and meta['window_uid']==w['window_uid'],'teacher必须纯R首seed同fold高分来源')
        require([r['uid'] for r in h]==meta['history_UIDs'] and [v['prediction']['uid'] for v in c]==meta['candidate_UIDs']
            and [v['label'] for v in c]==meta['pair_labels'],'不能改原预测UID/候选顺序/未知标签')
        require(w['gap_requested_sec'] is None and meta.get('candidate_scope')=='whole_original_high_score_stage_not_exact_enabled_subset'
            and w['supervision']['teacher_forced_history'] is False,'不得冒充原requested-gap或精确已评分子集')
        times=[r['timestamp_sec'] for r in h];now=c[0]['prediction']['timestamp_sec']
        require(times==sorted(set(times)) and times[-1]<now and all(v['prediction']['timestamp_sec']==now for v in c),'历史必须严格过去，候选同当前帧')
        labels=[v['label'] for v in c];require(any(x is not None for x in labels)
            and all(x is None or type(x) is int and x in (0,1) for x in labels),'unknown保持None，至少一个known，不要求正例')
    return {w['window_uid']:w for w in real}

def entries_counts(entries):
    return dict(window_exposures=len(entries),candidate_pair_exposures=sum(x['candidate_pairs'] for x in entries),
        known_pair_exposures=sum(x['labelled_pairs'] for x in entries))

def make_plan(real,original_table,fold,seed,exposures,*,original_table_ref=None):
    """只调用原v8曝光纯函数排序新R；S列完全复制冻结v10 balanced原表。"""
    validate_pool(real,fold);require(seed in SEEDS,'只准事前三seed')
    require(len(original_table['real'])==3000 and len(original_table['synthetic'])==1000,'原参考曝光表不完整')
    generated=exposures(real,[],seed)
    require(generated['synthetic']==[] and len(generated['real'])==3000,'原排序纯函数返回预算不同')
    synthetic=deepcopy(original_table['synthetic']);r=generated['real']
    return dict(schema=PLAN_SCHEMA,fold=fold,seed=seed,regimes_share_R=['R','RS'],real=r,synthetic=synthetic,
        original_balanced_table=deepcopy(original_table_ref),R_order_algorithm='original_v8_pairs.exposures_SHA256_R_seed_epoch_UID',
        augmentation=AUGMENTATION,R_window_content_is_original=False,R_requested_gap_strata_preserved=False,
        S_order_and_rows_exact_original=True,R_UID_chain_sha256=digest([x['window_uid'] for x in r]),
        S_UID_chain_sha256=digest([x['window_uid'] for x in synthetic]),accounting=dict(real=entries_counts(r),synthetic_RS=entries_counts(synthetic),synthetic_R=entries_counts([])),
        physical_images_exposure_claim=False,equal_pair_or_FLOPs_claim=False,new_optimizer_updates=0,test_read=False)

def validate_plan(real,synthetic,table,original_table,fold,seed,exposures):
    r=validate_pool(real,fold)
    require(table['schema']==PLAN_SCHEMA and table['fold']==fold and table['seed']==seed and table['augmentation']==AUGMENTATION,'新计划身份/无增广不同')
    require(table==make_plan(real,original_table,fold,seed,exposures,original_table_ref=table['original_balanced_table']),'新R原算法顺序/S原值/账本不一致')
    require(len(synthetic)==1000 and len({w['window_uid'] for w in synthetic})==1000,'原balanced S必须1000唯一')
    s={w['window_uid']:w for w in synthetic}
    require(Counter(w['synthetic_seed'] for w in synthetic)=={v:250 for v in (1042,1044,1048,1131)}
        and all(w['domain']=='synthetic' for w in synthetic),'S只能四登记运动各250')
    require({x['window_uid'] for x in table['synthetic']}==set(s) and all(x['domain']=='synthetic' and x['epoch']==0 for x in table['synthetic']),'原S epoch0/完整唯一不同')
    for epoch in range(3):
        part=table['real'][epoch*1000:(epoch+1)*1000]
        require({x['window_uid'] for x in part}==set(r) and all(x['domain']=='real' and x['epoch']==epoch for x in part),'新R每epoch必须1000唯一一次')
    for domain,pool in (('real',r),('synthetic',s)):
        for entry in table[domain]:
            w=pool[entry['window_uid']];known=[c for c in w['candidates'] if c['label'] is not None]
            require(known and all(type(c['label']) is int and c['label'] in (0,1) for c in known)
                and entry['candidate_pairs']==len(w['candidates']) and entry['labelled_pairs']==len(known),'all/known pair记录不同')
    return dict(real=r,synthetic=s)

def load_source(cfg):
    path=checked(cfg['source_training_protocol']);require(path==SOURCE_PROTOCOL and sha(path)==SOURCE_PROTOCOL_SHA,'只复用冻结原v10来源')
    source=read(path);oldroot=physical(source['bundle'])
    for value in read_ref(source['bundle_manifest'])['files']:require(sha(oldroot/value['path'])==value['sha256'],'原执行源码变化')
    old=module('aligned_original_v10_runtime',oldroot/'tools/research_ops/v10_runtime.py');numeric,base,_=old.load_numeric(source)
    # 冻结旧数值会前置旧tools目录；新训练/记录工具由新bundle明确加载。
    sys.path[:0]=[str(ROOT/'tools/research_ops'),str(ROOT/'tools/performance')]
    return source,numeric,base

def prepare_inputs(config,fold,seed,regime):
    cfg=read(config);require(dict(fold=fold,seed=seed,regime=regime) in expected_matrix(),'只准18登记单元')
    complete=read_ref(cfg['input_root']);require(complete['status']==INPUT_STATUS and complete['test_read'] is False
        and complete['new_prediction_or_tracking_or_training'] is False and complete['all_windows_roundtrip_exact'] is True,'新R输入尚未闭合')
    source,numeric,base=load_source(cfg);original_ref=source['exposures']['balanced'][fold][str(seed)]
    original=read_ref(original_ref);table=read_ref(cfg['exposures'][fold][str(seed)])
    require(table['original_balanced_table']==original_ref,'S来源绑定必须原balanced表')
    real=rows(complete['folds'][fold]['pool']);synthetic=rows(source['synthetic_pools']['balanced'])
    ordering=module('aligned_original_exposure_order',checked(cfg['exposure_order_source']))
    pools=validate_plan(real,synthetic,table,original,fold,seed,ordering.exposures)
    refs=source['folds'][fold];normalizer_state=read_ref(refs['normalizer']);normalizer=numeric.FeatureNormalizer.from_state(normalizer_state)
    require(normalizer.state()==normalizer_state,'必须原baseR标准化，不在新池重拟合')
    reference=read_ref(source['reference_R']['motion'][fold][str(seed)]['training_receipt'])
    require(reference['status']=='complete' and reference['completed_updates']==1000 and reference['real_window_exposures']==3000
        and reference['synthetic_window_exposures']==0 and reference['binding']['seed']==seed,'原初始化/参照R预算不符')
    return dict(cfg=cfg,source=source,numeric=numeric,base=base,pools=pools,table=table,normalizer=normalizer,reference=reference,
        config_path=Path(config),protocol_sha256=sha(config),fold=fold,seed=seed,regime=regime)
