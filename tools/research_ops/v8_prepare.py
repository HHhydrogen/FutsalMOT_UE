"""v8源闭包/仅train-R Normalizer准备；只产未授权候选，不训练/不读媒体。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
PROJECT=Path(__file__).resolve().parents[2];RESEARCH=Path('D:/projects/FutsalMOT_Research')
sys.path.insert(0,str(PROJECT/'python/src'))
from grf_ue_bridge.learned_association_features_v8 import features
from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer
GAMES=('game4','game6','game9');SEEDS=(20261024,20261025,20261026)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s]
def require(ok,msg):
    if not ok:raise ValueError(msg)
def write(p,value):
    with Path(p).open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
def prepare(pools,source_config,output):
    pools=Path(pools).resolve();output=Path(output).resolve();require(RESEARCH/'pose/learned_association_v8' in output.parents and not output.exists(),'全新DResearch/v8候选')
    receipt=read(pools/'complete.json');require(receipt['status']=='complete_candidate_not_training_authorized' and receipt['gap_requests_sec']==[0.,.2,.4,.8,1.2],'仅当前连续actual历史/新grid完成池')
    require(receipt['config_sha256']==sha(source_config),'源cache/标签配置绑定变化')
    names=['tools/research_ops/'+n for n in ('v8_train.py','v8_track.py','v8_metric.py','v8_gap_recovery.py','v8_control.py','v8_analyze.py')]+['tools/performance/ordered_prefetch.py']+['python/src/grf_ue_bridge/'+n for n in ('__init__.py','learned_association_features_v8.py','learned_association_model_v8.py','learned_association_tracker_v8.py','pose_association_contract_v2.py')]
    files=sorted([dict(path=n,sha256=sha(PROJECT/n),size=(PROJECT/n).stat().st_size) for n in names],key=lambda x:x['path']);identity=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest();bundle=RESEARCH/'code'/identity
    if not bundle.exists():
        bundle.mkdir(parents=True)
        for f in files:target=bundle/f['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PROJECT/f['path'],target)
    else:
        for f in files:require(sha(bundle/f['path'])==f['sha256'],'bundle不可覆盖')
    output.mkdir(parents=True);write(output/'bundle_manifest.json',dict(files=files));folds={}
    for game in GAMES:
        directory=pools/('heldout_'+game);real=rows(directory/'real_pool.jsonl');require(len(real)==1000 and all(w['domain']=='real' and w['game'] in GAMES and w['game']!=game for w in real),'Normalizer heldout隔离')
        normalizer=FeatureNormalizer.fit(features(w['history'],c['prediction']) for w in real for c in w['candidates'] if c['label'] is not None)
        file=output/('normalizer_'+game+'.json');write(file,normalizer.state());folds[game]=dict(real_pool=bind(directory/'real_pool.jsonl'),normalizer=bind(file),exposures={str(seed):bind(directory/f'exposures_{seed}.json') for seed in SEEDS})
    config=dict(schema='futsalmot_learned_association_training_v8',training_authorized=False,tracking_authorized=False,approved_by=None,bundle=str(bundle),bundle_manifest=bind(output/'bundle_manifest.json'),folds=folds,synthetic_pool=bind(pools/'synthetic_pool.jsonl'),pairs_complete=bind(pools/'complete.json'),source_config=bind(source_config),parameters=dict(updates=1000,real_windows_per_update=3,synthetic_windows_RS=1,synthetic_alpha=1/3,lr=.001,weight_decay=.0001,hidden=[64,32],amp=False,checkpoint_interval=50,prefetch=2,cache_bytes=268435456),normalization=dict(scope='known_label_train_R_only',std_floor=.05,clip_abs=5,motion_mask_after_normalization=True),history=dict(actual_records=3,source_frame_step=1,gap_requests_sec=[0.,.2,.4,.8,1.2],zero_means_native_next_frame=True),candidate_gate=dict(max_gap_sec=1.2,center_distance_max_heights=2,area_ratio=[.25,4],velocity_cap_latest_heights_per_sec=10),scope=dict(sequences=['SNMOT-060','SNMOT-097','SNMOT-151'],frames_each=750,fps=25,heldout='leave_one_game_out'),seeds=list(SEEDS),arms=['motion_R','motion_RS','pose_R','pose_RS'],GT_usage='training_labels_only; heldout GT only metric; never features',test116187_sealed=True,progress_definition='exploratory complete all folds/seeds; retain negative; root must register numerical progress threshold before execution')
    write(output/'protocol_candidate.json',config);return dict(status='candidate_only_no_updates',bundle=str(bundle),protocol=str(output/'protocol_candidate.json'),config_sha256=sha(output/'protocol_candidate.json'))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pools',type=Path,required=True);p.add_argument('--source-config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.pools,a.source_config,a.output)))
