"""固定七比赛完整验证输入；复用首帧，下载/首次解码，GT只供评价。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research')
REVISION='2993b47d4369fa70ea70afc8bc63b5964e556a81'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def write(p,v):
    with Path(p).open('x',encoding='utf-8') as f:f.write(canonical(v)+'\n')
def atomic(p,v):
    tmp=Path(p).with_suffix('.tmp');write(tmp,v);tmp.replace(p)
def fetch(url,limit):
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'FutsalMOT-paired-validation/1.0'})
            with urllib.request.urlopen(req,timeout=30) as response:data=response.read(limit+1)
            require(0<len(data)<=limit,'输入响应大小异常');return data
        except (urllib.error.URLError,TimeoutError,ConnectionError):
            if attempt==2:raise
            time.sleep(attempt+1)
def source_url(source,name):
    require(source['split'] in ('train','val') and source['role']=='external_validation_only','只允许登记train/val用于验证，不读test')
    require(name=='gt/gt.txt' or (name.startswith('img1/') and name.endswith('.jpg') and name[5:-4].isdigit()),'只获取原GT或JPEG')
    return f'https://huggingface.co/datasets/Lekim89/sportsmot/resolve/{REVISION}/{source["split"]}/{source["sequence"]}/{name}?download=true'
def fetch_jpeg(source,number):
    from PIL import Image
    for attempt in range(3):
        raw=fetch(source_url(source,f'img1/{number:06d}.jpg'),5000000)
        try:
            if not (raw[:2]==b'\xff\xd8' and raw[-2:]==b'\xff\xd9'):raise OSError('JPEG短响应/结尾标记缺失')
            with Image.open(io.BytesIO(raw)) as image:
                image.load();require(image.size==(source['width'],source['height']),'实际JPEG尺寸不符')
            return raw,attempt+1
        except OSError:
            if attempt==2:raise
            time.sleep(attempt+1)
def preflight(config):
    cfg=read(config);require(cfg['schema']=='seven_match_validation_acquisition_v1' and cfg['approved_by']=='root' and cfg['evaluate_only'] is True
        and cfg['test_sealed'] is True and cfg['training_authorized'] is False,'缺验证输入准入')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行D bundle')
    for f in cfg['code_files']:require(ref(ROOT/f['path'])['sha256']==f['sha256'],'输入源码改变')
    registry=read(cfg['matches']['path']);require(ref(cfg['matches']['path'])==cfg['matches'] and registry['status']=='seven_unique_new_football_matches_identity_verified_before_model','比赛来源未冻结')
    sources=registry['sources'];require(len(sources)==7 and len({s['video_id'] for s in sources})==7 and sum(s['full_clip_frames'] for s in sources)==4790,'固定七比赛/4790帧不符')
    spec=importlib.util.spec_from_file_location('substitution_input_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    st=importlib.util.module_from_spec(spec);spec.loader.exec_module(st)
    output=st.physical_child(cfg['output'],R/'public');expected=R/('public/substitution_validation_a02' if cfg.get('inheritance') else 'public/substitution_validation_a01')
    require(output==expected and not output.exists(),'输入partial不覆盖')
    if cfg.get('inheritance'):
        assert ref(cfg['inheritance']['path'])==cfg['inheritance'];inheritance=read(cfg['inheritance']['path'])
        assert ref(inheritance['failed_state']['path'])==inheritance['failed_state']
        require(read(inheritance['failed_state']['path'])['status']=='failed_preserved_no_replay','不能继承活动输入')
        assert ref(inheritance['files']['path'])==inheritance['files']
        inherited=[json.loads(x) for x in Path(inheritance['files']['path']).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
        require(len({(f['sequence'],f['frame_number']) for f in inherited})==len(inherited),'继承帧重复')
        for f in inherited:
            path=st.physical_child(f['path'],R);require(path.is_file() and path.stat().st_size==f['bytes'],'继承成功文件缺失/大小改变')
    for s in sources:
        source_url(s,'gt/gt.txt');image=s['files']['img1/000001.jpg'];path=st.physical_child(image['path'],R/'public')
        require(path.is_file() and path.stat().st_size==image['bytes'],'已验首帧缺失/大小改变')
    return cfg,sources,output,st
def execute(config):
    cfg,sources,output,st=preflight(config);output.mkdir()
    write(output/'intent.json',dict(config=ref(config),GT_role='evaluation_only_never_predictor_filter',test_read=False,optimizer_updates=0))
    state=dict(status='acquiring_seven_match_validation_inputs',completed=7,target=4790,test_read=False,models_run=False,optimizer_updates=0)
    inheritance=read(cfg['inheritance']['path']) if cfg.get('inheritance') else None
    inherited=[json.loads(x) for x in Path(inheritance['files']['path']).read_text(encoding='utf-8-sig').splitlines() if x.strip()] if inheritance else []
    state['completed']=len(inherited) if inherited else 7
    atomic(output/'state.json',state);source_index=[];refs=list(inherited)
    try:
        from PIL import Image
        for s in sources:
            folder=output/s['sequence'];folder.mkdir();(folder/'img1').mkdir();(folder/'gt').mkdir()
            if inheritance:
                source_index.append(next(x for x in inheritance['sequences'] if x['sequence']==s['sequence']))
                continue
            data=fetch(source_url(s,'gt/gt.txt'),5000000);target=folder/'gt/gt.txt'
            rows=[x.split(',') for x in data.decode('utf-8-sig').splitlines() if x.strip()]
            require(rows and all(len(x)>=9 and 1<=int(x[0])<=s['full_clip_frames'] and int(x[1])>=0 and int(float(x[6]))==1 and min(map(float,x[4:6]))>0 for x in rows),'SportsMOT GT范围/ID/框不符')
            require(len({(int(x[0]),int(x[1])) for x in rows})==len(rows),'GT同帧身份重复')
            with target.open('xb') as f:f.write(data)
            source_index.append(dict(sequence=s['sequence'],video_id=s['video_id'],original_split=s['split'],role='external_validation_only',
                match_identity=s['match_identity'],frames=s['full_clip_frames'],fps=s['fps'],width=s['width'],height=s['height'],gt=ref(target),
                GT_rows=len(rows),GT_IDs=len({int(x[1]) for x in rows}),seqinfo=s['files']['seqinfo.ini'],identity=s))
            refs.append(dict(sequence=s['sequence'],frame_number=1,**s['files']['img1/000001.jpg'],inherited_identity_sample=True))
        lookup={s['sequence']:s for s in sources};have={(f['sequence'],f['frame_number']) for f in refs}
        jobs=[(s['sequence'],i) for s in sources for i in range(2,s['full_clip_frames']+1) if (s['sequence'],i) not in have]
        def one(job):
            seq,i=job;s=lookup[seq];raw,attempts=fetch_jpeg(s,i)
            target=st.physical_child(output/seq/'img1'/f'{i:06d}.jpg',output)
            with target.open('xb') as f:f.write(raw)
            return dict(sequence=seq,frame_number=i,path=str(target),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),inherited_identity_sample=False,JPEG_fetch_attempts=attempts)
        with (output/'files.jsonl').open('x',encoding='utf-8') as journal:
            for f in refs:journal.write(canonical(f)+'\n')
            with ThreadPoolExecutor(max_workers=4) as pool:
                for item in pool.map(one,jobs):
                    refs.append(item);journal.write(canonical(item)+'\n');journal.flush()
                    if len(refs)%25==0:atomic(output/'state.json',dict(state,completed=len(refs)))
        require(len(refs)==4790,'完整输入未齐，不按GT挑帧')
        complete=dict(schema='seven_match_validation_inputs_v1',status='complete4790_validation_frames_decoded_not_prediction_or_training_authorized',
            config=ref(config),matches=cfg['matches'],sequences=source_index,frames=4790,files=ref(output/'files.jsonl'),
            inherited_first_frames=7,inherited_successful_images=len(inherited) if inherited else 7,newly_downloaded_images=len(jobs),inheritance=cfg.get('inheritance'),new_R_training_exposure=0,GT_role='evaluation_only',test_read=False,models_run=False,optimizer_updates=0,
            mirror_revision=REVISION,official_image_SHA_available=False)
        write(output/'manifest.json',complete);atomic(output/'state.json',dict(state,status=complete['status'],completed=4790))
        return dict(status=complete['status'],frames=4790)
    except BaseException as e:
        atomic(output/'state.json',dict(state,status='failed_preserved_no_replay',completed=len(refs),error=repr(e)));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.execute:result=execute(a.config)
    else:preflight(a.config);result=dict(status='readonly_seven_validation_inputs_preflight',frames=4790,optimizer_updates=0)
    print(json.dumps(result,ensure_ascii=False))
