"""每个新候选源视频只获取一张首帧与seqinfo；身份核验，不评价/训练。"""
import argparse
import configparser
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research')
sys.path.insert(0,str(ROOT/'tools/research_ops'))
import independent_match_inventory as inventory
REVISION='2993b47d4369fa70ea70afc8bc63b5964e556a81'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
def write(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def selections(report):
    result=[]
    for v in report['videos']:
        if v['already_observed_v10'] or (v['title'] is not None and not v['football_title_candidate']):continue
        require(len(v['splits'])==1,'同源跨split，先诊断')
        split=next(iter(v['splits']));require(split in ('train','val'),'test封存')
        seq=sorted(v['splits'][split])[0];require(inventory.video_id(seq)==v['video_id'],'实际视频映射不符')
        result.append(dict(split=split,sequence=seq,video_id=v['video_id'],title=v['title'],classification='football_title_candidate' if v['title'] else 'unknown_sport_pending_visual'))
    return result
def fetch_small(request,limit):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=30) as response:raw=response.read(limit+1)
            require(0<len(raw)<=limit,'身份小文件超限');return raw
        except (urllib.error.URLError,TimeoutError,ConnectionError):
            if attempt==2:raise
            time.sleep(attempt+1)
def execute(config):
    cfg=read(config);require(cfg['schema']=='match_identity_samples_config_v1' and cfg['approved_by']=='root'
        and cfg['identity_only'] is True and cfg['test_sealed'] is True and cfg['training_authorized'] is False,'缺首帧身份准入')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行D bundle')
    for f in cfg['code_files']:require(ref(ROOT/f['path'])['sha256']==f['sha256'],'身份源码变化')
    source=Path(cfg['inventory']['path']);require(ref(source)==cfg['inventory'],'库存来源变化')
    selected=selections(read(source));require(selected==cfg['selections'],'结果前选择规则变化')
    inherited=[]
    if cfg.get('inherited_failed'):
        fp=Path(cfg['inherited_failed']['path']);require(ref(fp)==cfg['inherited_failed'],'失败继承来源变化')
        failure=read(fp);require(failure['status']=='failed_preserved_no_replay','不能继承未失败/活动事务')
        intent=read(fp.parent/'intent.json');require(intent['selections']==selected,'原选择清单不同')
        for s in failure['completed']:
            require(any(s['sequence']==x['sequence'] and s['split']==x['split'] for x in selected),'继承源不在原清单')
            for f in s['files'].values():
                path=Path(f['path']);require(path.is_file() and path.stat().st_size==f['bytes'],'继承成功文件缺失/大小改变')
            inherited.append(s)
    output=Path(cfg['output']);expected=R/('public/substitution_match_identity_a02' if cfg.get('inherited_failed') else 'public/substitution_match_identity_a01')
    require(output==expected and not output.exists(),'新身份输出不覆盖')
    # 与已验存储边界一致：逐父目录拒绝reparse/junction，不通过别名写外部D。
    for p in [output,*output.parents]:
        if p.exists():require(not p.is_symlink() and not (getattr(p.lstat(),'st_file_attributes',0)&0x400),'物理路径含重解析点')
    output.mkdir();write(output/'intent.json',dict(config=ref(config),selections=selected,GT_read=False,test_read=False))
    completed=list(inherited)
    try:
        from PIL import Image
        for item in selected:
            if any(s['sequence']==item['sequence'] for s in inherited):continue
            folder=output/item['split']/item['sequence'];folder.mkdir(parents=True)
            refs={}
            for name,limit in [('seqinfo.ini',65536),('img1/000001.jpg',5000000)]:
                url=f'https://huggingface.co/datasets/Lekim89/sportsmot/resolve/{REVISION}/{item["split"]}/{item["sequence"]}/{name}?download=true'
                request=urllib.request.Request(url,headers={'User-Agent':'FutsalMOT-identity-only/1.0'})
                raw=fetch_small(request,limit)
                path=folder/name;path.parent.mkdir(exist_ok=True)
                with path.open('xb') as f:f.write(raw)
                refs[name]=dict(**ref(path),bytes=len(raw),url=url)
            info=configparser.ConfigParser();info.read(folder/'seqinfo.ini',encoding='utf-8-sig');s=info['Sequence']
            require(s['name']==item['sequence'] and int(s['frameRate'])==25,'序列/fps不符')
            with Image.open(folder/'img1/000001.jpg') as image:
                image.load();require(image.size==(int(s['imWidth']),int(s['imHeight'])),'首帧/元数据尺寸不符')
            completed.append(dict(**item,files=refs,frames_available=int(s['seqLength']),fps=25,width=int(s['imWidth']),height=int(s['imHeight']),identity_verified=False))
            print(json.dumps(dict(sequence=item['sequence'],first_frame_acquired=True)),flush=True)
        receipt=dict(schema='match_identity_samples_v1',status='complete_identity_samples_not_match_verified_or_evaluation_authorized',config=ref(config),sources=completed,
            mirror_revision=REVISION,inherited_failed=cfg.get('inherited_failed'),official_pixel_SHA_available=False,GT_read=False,test_read=False,models_run=False,optimizer_updates=0)
        write(output/'manifest.json',receipt);return dict(status=receipt['status'],sampled_videos=len(completed))
    except BaseException as e:
        write(output/'failed.json',dict(status='failed_preserved_no_replay',error=repr(e),completed=completed));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(execute(a.config) if a.execute else dict(status='readonly_identity_sample_plan'),ensure_ascii=False))
