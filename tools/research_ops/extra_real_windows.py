"""额外真实C输入窗口；同原候选数值、隔离heldout，零优化更新。"""
import argparse
import ast
from collections import Counter
import configparser
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research')
EXP=R/'pose/pose_mechanism_a01/extra_R_inputs_a01'
SEQUENCES={'SNMOT-061':'game4','SNMOT-098':'game6','SNMOT-154':'game9'}
PAIR_SHA='522d00e3767fe4413d44a90510088407bbfa66b444e6e2e6b473764a020208ef'
GATE_SHA='2af8816d8a60b5aa1f236fc951ca5394c8cf28d864bb3371976a34af212ee2a0'
BASE_SHA='2a1fa8ecd0b48993289c859ec6e83c36bf987e9d7de9ccf44820c4a86f7be575'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def checked(r):
    p=Path(r['path']);require(sha(p)==r['sha256'],'绑定变化');return p
def module(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def write(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)


def scope_loader(pairs):
    """只替换原load_source的序列白名单字面量，其余AST逐值相同。"""
    tree=ast.parse(Path(pairs.__file__).read_text(encoding='utf-8-sig'))
    original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_source')
    changed=copy.deepcopy(original);scope=changed.body[1]
    expected=ast.parse("if source['domain']=='real':\n require(source['game'] in GAMES and source['sequence'] in ('SNMOT-060','SNMOT-097','SNMOT-151'),'真实源越界')").body[0]
    require(ast.dump(scope)==ast.dump(expected),'原唯一scope守卫变化，不猜测替换')
    old=scope.body[0].value.args[0].values[1].comparators[0]
    old.elts=[ast.Constant(value=s) for s in SEQUENCES]
    restored=copy.deepcopy(changed);restored.body[1]=copy.deepcopy(original.body[1])
    require(ast.dump(restored)==ast.dump(original),'scope以外数值AST改变')
    proof=dict(scope_only_AST_change=True,original_AST_sha256=hashlib.sha256(ast.dump(original).encode()).hexdigest(),
        scoped_AST_sha256=hashlib.sha256(ast.dump(changed).encode()).hexdigest())
    exec(compile(ast.fix_missing_locations(ast.Module(body=[changed],type_ignores=[])),pairs.__file__,'exec'),pairs.__dict__)
    return proof


def validate_source(s):
    require(s['sequence'] in SEQUENCES and s['game']==SEQUENCES[s['sequence']]
        and s['domain']=='real' and s['role']=='extra_R_training_input_only_C'
        and s['counts']['frames']==750 and s['actual_decoded_frames']==750
        and s['GT_used_for_predictions'] is False and s['first_frame']==0 and s['last_frame']==749
        and s['fps']==25,'额外R来源/角色/预测未闭合')
    return dict(domain='real',sequence=s['sequence'],game=s['game'],fps=25,first_frame=0,last_frame=749,
        cache=s['cache'],gt=s['gt_reference'],gameinfo=s['gameinfo_reference'],seqinfo=s['seqinfo_reference'])


def observation_set(windows):
    return {d['uid'] for w in windows for d in [*w['history'],*[c['prediction'] for c in w['candidates']]]}
def frame_set(windows):
    return {(w['sequence'],i) for w in windows for i in [*w['history_frame_indices'],w['candidate_frame_index']]}
def clock(value):
    half,time=value.split(' - ');minutes,seconds=map(int,time.split(':'));return int(half),minutes*60+seconds
def clock_disjoint(a,b):
    sa,ea=clock(a['start']),clock(a['stop']);sb,eb=clock(b['start']),clock(b['stop'])
    require(sa[0]==ea[0] and sb[0]==eb[0],'片段跨半场，需另立对应')
    return sa[0]!=sb[0] or ea[1]<=sb[1] or eb[1]<=sa[1]
def game_clock(source):
    c=configparser.ConfigParser();c.read(checked(source['gameinfo']),encoding='utf-8-sig');s=c['Sequence']
    require('game'+s['gameID']==source['game'],'实际gameinfo不符')
    return dict(sequence=source['sequence'],game=source['game'],start=s['gameTimeStart'],stop=s['gameTimeStop'])


def preflight(config):
    cfg=read(config);require(cfg['schema']=='extra_real_unique_windows_config_v1' and cfg['approved_by']=='root'
        and cfg['window_build_authorized'] is True and cfg['training_authorized'] is False and cfg['test_sealed'] is True,'缺独立建池准入')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行D独立bundle')
    required={'tools/research_ops/extra_real_windows.py','tools/research_ops/v8_pairs.py',
        'python/src/grf_ue_bridge/learned_association_features_v8.py','python/src/grf_ue_bridge/storage_policy.py'}
    require({f['path'] for f in cfg['code_files']}==required and len(cfg['code_files'])==4,'必要四源码不符')
    for f in cfg['code_files']:require(sha(ROOT/f['path'])==f['sha256'],'建池源码变化')
    require(sha(ROOT/'tools/research_ops/v8_pairs.py')==PAIR_SHA and sha(ROOT/'python/src/grf_ue_bridge/learned_association_features_v8.py')==GATE_SHA,'候选/标签数值变化')
    storage=module('extra_R_windows_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    m=read(checked(cfg['prediction_manifest']));closed=read(checked(cfg['prediction_completion']))
    require(m['status']=='complete3_sources2250_frames_not_training_authorized' and len(m['sources'])==3
        and m['new_optimizer_updates']==0 and m['GT_used_for_predictions'] is False and m['test_read'] is False
        and closed['status']=='complete3_extra_R_prediction_sources_and_processes_exited'
        and closed['manifest']==cfg['prediction_manifest'] and closed['prediction_processes_absent'] is True,'实际预测/退出未闭合')
    sources=[validate_source(s) for s in m['sources']];require({s['sequence'] for s in sources}==set(SEQUENCES),'三源不齐或重复')
    for s in sources:
        for k in ('cache','gt','gameinfo','seqinfo'):checked(s[k])
    base=read(checked(cfg['base_training_protocol']));require(cfg['base_training_protocol']['sha256']==BASE_SHA,'基础R协议变化')
    for fold in SEQUENCES.values():
        for k in ('real_pool','normalizer','quality_scale'):checked(base['folds'][fold][k])
        for seed in ('20261024','20261025','20261026'):checked(base['folds'][fold]['exposures'][seed])
    old_sources=read(checked(base['source_config']))['sources'];old_sources=[s for s in old_sources if s['domain']=='real']
    clocks=[]
    for s in sources:
        new=game_clock(s);old=game_clock(next(o for o in old_sources if o['game']==s['game']))
        require(clock_disjoint(new,old),'额外片段与原R比赛时间重叠，不能当新源帧')
        clocks.append(dict(new=new,base=old,same_game_different_time=True))
    output=storage.physical_child(cfg['output'],EXP);require(not output.exists(),'建池partial不覆盖/重放')
    pairs=module('extra_R_original_pairs',ROOT/'tools/research_ops/v8_pairs.py');proof=scope_loader(pairs)
    gate=module('extra_R_original_gate',ROOT/'python/src/grf_ue_bridge/learned_association_features_v8.py')
    return cfg,base,sources,output,pairs,gate.candidate_gate,proof,clocks


def execute(config,expected):
    require(sha(config)==expected,'必须显式新config SHA')
    cfg,base,sources,output,pairs,gate,proof,clocks=preflight(config);output.mkdir(parents=True)
    write(output/'intent.json',dict(status='started_not_complete',config=ref(config),optimizer_updates=0))
    try:
        pools={g:pairs.BalancedPool([(other,gap) for other in pairs.GAMES if other!=g for gap in pairs.GAPS],count=1000) for g in pairs.GAMES}
        audit=[]
        for s in sources:
            frames,labels=pairs.load_source(s);counts=Counter()
            for w in pairs.enumerate_windows(s,frames,gate,counts):
                counts['eligible_windows']+=1
                for heldout,pool in pools.items():
                    if heldout!=s['game']:pool.add(w)
            audit.append(dict(sequence=s['sequence'],game=s['game'],frames=len(frames),labelled_detection_states=labels,**dict(counts)))
        reports={}
        for heldout,pool in pools.items():
            selected=pool.finish();require(len(selected)==1000 and all(w['game']!=heldout for w in selected),'heldout泄漏/配额不符')
            by_game=Counter(w['game'] for w in selected);require(set(by_game.values())=={500},'每允许train场必须500唯一窗口')
            old=list(pairs.rows(pairs.bound(base['folds'][heldout]['real_pool'])));require(len(old)==1000,'原R池变化')
            overlap=dict(window_UID=len({w['window_uid'] for w in old}&{w['window_uid'] for w in selected}),
                observation_UID=len(observation_set(old)&observation_set(selected)),source_frame_refs=len(frame_set(old)&frame_set(selected)))
            require(not any(overlap.values()),'新旧来源UID/帧重叠，需重新核验')
            fold=output/('heldout_'+heldout);fold.mkdir();pairs.dump_rows(fold/'extra_real_pool.jsonl',selected)
            for seed in pairs.SEEDS:
                base_table=read(checked(base['folds'][heldout]['exposures'][str(seed)]))
                require(len(base_table['real'])==3000,'基础3000R表不符')
                extra=[dict(window_uid=w['window_uid'],domain='real',source_allocation='extra_R',epoch=0,
                    candidate_pairs=len(w['candidates']),labelled_pairs=sum(c['label'] is not None for c in w['candidates']))
                    for w in sorted(selected,key=lambda w:pairs.key(['extra_R',seed,w['window_uid']]))]
                write(fold/f'extra_R_exposure_plan_{seed}.json',dict(schema='extra_real_exposure_plan_v1',base_real_table=base['folds'][heldout]['exposures'][str(seed)],
                    base_R_exposures=3000,extra_R=extra,extra_R_exposures=1000,total_C_R_exposures_if_authorized=4000,training_authorized=False,actual_optimizer_updates=0))
            reports[heldout]=dict(pool=ref(fold/'extra_real_pool.jsonl'),unique_windows=1000,windows_by_game=dict(by_game),source_frame_refs=len(frame_set(selected)),
                observation_UIDs=len(observation_set(selected)),candidate_pairs=sum(len(w['candidates']) for w in selected),
                known_pairs=sum(c['label'] is not None for w in selected for c in w['candidates']),overlap_with_base_R=overlap,
                base_R_normalizer_and_quality_unchanged=base['folds'][heldout])
        receipt=dict(schema='extra_real_unique_windows_receipt_v1',status='complete3_folds_extra_R1000_not_training_authorized',config=ref(config),
            folds=reports,source_audit=audit,source_time_registry=clocks,scope_numeric_proof=proof,optimizer_updates=0,test_read=False,
            new_independent_matches=0,base_R_exposures_unchanged=3000,prospective_C_total_R=4000,
            counts_are_windows_not_images_or_equal_FLOPs=True,GT_use='identity labels/teacher-forced history only; no GT Pose features or filtering raw predictions')
        write(output/'complete.json',receipt);return dict(status=receipt['status'],unique_windows_each_fold=1000,new_optimizer_updates=0)
    except BaseException as e:
        write(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(e),traceback=traceback.format_exc()));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--config-sha256');a=p.parse_args()
    if a.execute:result=execute(a.config,a.config_sha256)
    else:
        preflight(a.config);result=dict(status='readonly_extra_R_unique_windows_preflight',frames=2250,optimizer_updates=0)
    print(json.dumps(result,ensure_ascii=False))
