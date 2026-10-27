"""只核验SportsMOT train/val序列与视频元数据；不读test、GT、图像或模型。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research')
OUT=R/'pose/real_substitution_a01/match_inventory_a01'
OBSERVED={'2QhNRucNC7E','G-vNjfx1GGc'}
def require(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def video_id(sequence):
    match=re.fullmatch(r'v_([A-Za-z0-9_-]{11})_c\d+',sequence)
    require(match is not None,'非法sequence，不根据部分字符串猜比赛');return match.group(1)
def parse_map(data):
    names=[x.strip() for x in data.decode('utf-8-sig').splitlines() if x.strip() and x.strip()!='name']
    require(names and len(names)==len(set(names)),'seqmap为空/重复')
    for s in names:video_id(s)
    return names
def map_url(revision,split):
    require(split in ('train','val') and re.fullmatch('[0-9a-f]{40}',revision),'只允许固定官方train/val，不读test')
    return f'https://raw.githubusercontent.com/MCG-NJU/SportsMOT/{revision}/codes/evaluation/TrackEval/data/ref/seqmaps/sportsmot-{split}.txt'
def fetch(url,limit=1024**2):
    request=urllib.request.Request(url,headers={'User-Agent':'FutsalMOT-source-availability/1.0'})
    with urllib.request.urlopen(request,timeout=25) as response:data=response.read(limit+1)
    require(len(data)<=limit,'小元数据超限');return data


def execute(config):
    cfg=read(config);require(cfg['schema']=='independent_match_inventory_config_v1' and cfg['approved_by']=='root'
        and cfg['metadata_only'] is True and cfg['test_sealed'] is True and cfg['training_authorized'] is False,'缺元数据准入')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行最小D bundle')
    for f in cfg['code_files']:require(sha(ROOT/f['path'])==f['sha256'],'库存源码变化')
    spec=importlib.util.spec_from_file_location('availability_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
    output=storage.physical_child(cfg['output'],R/'pose/real_substitution_a01');require(output==OUT and not output.exists(),'新库存目录已存在/越界，不覆盖')
    inherited=read(cfg['prior_inventory']['path']);require(sha(cfg['prior_inventory']['path'])==cfg['prior_inventory']['sha256'],'原val库存变化')
    output.mkdir(parents=True);write(output/'intent.json',dict(config=ref(config),test_read=False,optimizer_updates=0))
    try:
        commit=json.loads(fetch('https://api.github.com/repos/MCG-NJU/SportsMOT/commits/main'));revision=commit['sha']
        require(re.fullmatch('[0-9a-f]{40}',revision),'官方commit不符');write(output/'official_commit.json',commit)
        sequences={};by_video=defaultdict(lambda:defaultdict(list));sources=[]
        for split in ('train','val'):
            url=map_url(revision,split);data=fetch(url);path=output/(split+'_seqmap.txt');path.write_bytes(data)
            names=parse_map(data);sequences[split]=names
            if split=='val':require(set(names)==set(inherited['val_sequences']),'官方val清单变化，先核验，不自动升范围')
            for s in names:by_video[video_id(s)][split].append(s)
            sources.append(dict(url=url,local=ref(path),split=split,count=len(names)))
        def one(vid):
            if vid in inherited['video_titles']:
                return vid,dict(inherited['video_titles'][vid],origin='explicit_prior_metadata_inheritance')
            url='https://www.youtube.com/oembed?'+urllib.parse.urlencode(dict(url='https://www.youtube.com/watch?v='+vid,format='json'))
            try:return vid,dict(json.loads(fetch(url)),origin='new_provider_oembed',source_url=url)
            except Exception as error:return vid,dict(error=repr(error),origin='new_provider_oembed_failed',source_url=url)
        with ThreadPoolExecutor(max_workers=4) as pool:titles=dict(pool.map(one,sorted(by_video)))
        videos=[]
        for vid,splits in sorted(by_video.items()):
            value=titles[vid];title=value.get('title');videos.append(dict(video_id=vid,splits=dict(splits),title=title,title_error=value.get('error'),
                provider_metadata=value,already_observed_v10=vid in OBSERVED,identity_verified=False,
                football_title_candidate=bool(title and any(t in title.lower() for t in ('premier league','bundesliga','fa cup','football','soccer','ipswich'))),
                limitation='video ID/title is not independent match certification; root first-frame identity required'))
        result=dict(schema='independent_match_availability_inventory_v1',status='complete_train_val_metadata_not_identity_or_evaluation_authorized',
            config=ref(config),official_revision=revision,official_sources=sources,prior_inventory=cfg['prior_inventory'],videos=videos,
            official_sequences={s:len(v) for s,v in sequences.items()},unique_source_videos=len(videos),
            observed_source_videos=sorted(OBSERVED),test_read=False,GT_read=False,images_read=False,optimizer_updates=0,
            training_authorized=False,new_independent_matches_certified=0,completed_utc=datetime.now(timezone.utc).isoformat())
        write(output/'report.json',result);return dict(status=result['status'],sequences=result['official_sequences'],videos=len(videos),
            candidate_titles=[dict(video_id=v['video_id'],title=v['title'],observed=v['already_observed_v10']) for v in videos if v['football_title_candidate']])
    except BaseException as error:
        write(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(error)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(execute(a.config) if a.execute else dict(status='readonly_train_val_metadata_plan_no_model_or_test'),ensure_ascii=False))
