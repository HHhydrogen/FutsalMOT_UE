"""显式继承已解码两段，只恢复缺失154；旧失败manifest及已成功文件不改写。"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import traceback
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[2]
R=Path('D:/projects/FutsalMOT_Research')
DATA=R/'public/real_substitution_train_a01'
CONTROL=R/'pose/pose_mechanism_a01/extra_R_acquisition_recovery_a02'
SMALL_CONTROL=R/'pose/pose_mechanism_a01/extra_R_acquisition_recovery_a03'
sys.path.insert(0,str(ROOT/'tools/research_ops'))
import acquire_extra_real_clips as original


def require(ok,message):
    if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def ref(path):
    path=Path(path);return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
def checked(value):
    path=Path(value['path']);require(ref(path)==value,'冻结来源变化');return path
def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def inheritance(parent,proposal):
    """只继承原收据完整两源；不把文件存在或partial当成功。"""
    require(parent.get('schema')=='extra_real_train_input_manifest_v1'
        and parent.get('status')=='failed_preserved_no_replay'
        and parent.get('error')=="RuntimeError('HTTP range 长度不匹配')"
        and parent.get('models_inferred') is False and parent.get('optimizer_updates')==0
        and parent.get('test_requested') is False and parent.get('det_file_extracted_or_used') is False,
        '只恢复已定位的网络短读失败，不自动接其它partial')
    require([s['sequence'] for s in proposal['sources']]==['SNMOT-061','SNMOT-098','SNMOT-154'],'原结果前清单变化')
    require([s['sequence'] for s in parent['sequences']]==['SNMOT-061','SNMOT-098'],'原完整继承两源不符')
    all_files=[]
    for source in parent['sequences']:
        require(source['frames']==750 and (source['width'],source['height'],source['fps'])==(1920,1080,25)
            and source['GT_rows']>0,'原源没有完整首次解码/标签收据')
        seq=source['sequence'];prefix=f'train/{seq}/'
        expected={prefix+f'img1/{i:06d}.jpg' for i in range(1,751)}|{prefix+n for n in ('gt/gt.txt','seqinfo.ini','gameinfo.ini')}
        require(len(source['files'])==753 and {f['official_member'] for f in source['files']}==expected,'继承成员缺失/重复/越界')
        for f in source['files']:
            require(Path(f['path'])==DATA/Path(f['official_member']).relative_to('train'),'继承物理路径不符')
        all_files.extend(source['files'])
    require(parent['files']==all_files,'失败前已有部分第三源写入，禁止自动接续')
    return parent['sequences'],all_files,proposal['sources'][2]


def reserve_missing(root,exists):
    require(root==DATA,'恢复只限原登记数据根')
    require(not exists(root/'SNMOT-154'),'缺失源已经有partial，先诊断，不重放/覆盖')


def instrument_transport(remote,journal):
    """只记录实际read长度；原range、超时、三次重试与数值读取器不变。"""
    underlying=remote.urllib.request.urlopen
    class Response:
        def __init__(self,response):self.response=response
        def __enter__(self):self.response.__enter__();return self
        def __exit__(self,*args):return self.response.__exit__(*args)
        def __getattr__(self,name):return getattr(self.response,name)
        def read(self,n=-1):
            data=self.response.read(n)
            row=dict(utc=datetime.now(timezone.utc).isoformat(),requested_read_bytes=n,actual_bytes=len(data),
                status=self.response.status,content_range=self.response.headers.get('Content-Range'))
            with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            return data
    remote.urllib.request.urlopen=lambda *a,**k:Response(underlying(*a,**k))


def bounded_clip_range(reader,start,end,journal,block_bytes=4*1024**2):
    """远端大响应实际短读后改为小范围；保持原读取器/重试，不增加并发。"""
    require(0<block_bytes<=4*1024**2 and start<end,'范围上限不符')
    chunks=[]
    for offset in range(start,end,block_bytes):
        size=min(block_bytes,end-offset);reader.seek(offset);data=reader.read(size)
        require(len(data)==size,'小范围仍短读，保留失败，不写部分JPEG')
        chunks.append(data)
        row=dict(start=offset,bytes=size,sha256=hashlib.sha256(data).hexdigest())
        with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(dict(sequence='SNMOT-154',phase='verified_range_block',completed_bytes=offset+size-start,total_bytes=end-start)),flush=True)
    reader.cache_start=start;reader.cache=b''.join(chunks);reader.seek(start)
    require(len(reader.cache)==end-start,'完整范围未闭合')


def preflight(config):
    cfg=read(config)
    require(cfg['schema'] in ('extra_real_train_recovery_v1','extra_real_train_recovery_v2') and cfg['approved_by']=='root'
        and cfg['acquisition_authorized'] is True and cfg['training_authorized'] is False
        and cfg['test_sealed'] is True and cfg['recovery_only_sequence']=='SNMOT-154','恢复准入不符')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行独立bundle')
    for f in cfg['files']:require(ref(ROOT/f['path'])['sha256']==f['sha256'],'恢复源码变化')
    old_cfg=read(checked(cfg['original_config']));parent=read(checked(cfg['failed_manifest']))
    require(parent['protocol']==cfg['original_config'] and parent['proposal']==old_cfg['proposal'],'父事务绑定不符')
    for f in old_cfg['files']:require(ref(Path(old_cfg['bundle'])/f['path'])['sha256']==f['sha256'],'原执行源码变化')
    proposal=read(checked(parent['proposal']));sources,files,missing=inheritance(parent,proposal)
    require(proposal['official_split']=='train' and proposal['revision']==original.remote.REVISION,'官方train版本不符')
    spec=importlib.util.spec_from_file_location('extra_R_recovery_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
    control=SMALL_CONTROL if cfg['schema']=='extra_real_train_recovery_v2' else CONTROL
    storage.physical_child(DATA,R/'public');storage.physical_child(control,R/'pose/pose_mechanism_a01')
    require(Path(cfg['output'])==DATA and Path(cfg['control'])==control,'恢复输出越界')
    reserve_missing(DATA,lambda p:p.exists())
    require(not (control/'started.json').exists() and not Path(cfg['result_manifest']).exists(),'恢复事务已启动，不隐式重放')
    result_name='manifest_recovery_a03.json' if cfg['schema']=='extra_real_train_recovery_v2' else 'manifest_recovery_a02.json'
    require(Path(cfg['result_manifest'])==DATA/result_name,'只允许新独立汇总，不覆盖父manifest')
    if cfg['schema']=='extra_real_train_recovery_v2':
        previous=read(checked(cfg['previous_recovery_manifest']))
        require(Path(cfg['previous_recovery_manifest']['path'])==DATA/'manifest_recovery_a02.json'
            and previous['status']=='failed_preserved_no_replay' and previous['newly_downloaded_images']==0
            and previous['inherited_failed_manifest']==cfg['failed_manifest'] and previous['files']==parent['files']
            and cfg['range_block_bytes']==4*1024**2,'上次失败/继承或新范围准入不符')
    metadata=0
    for f in files:
        p=storage.physical_child(f['path'],DATA);require(p.is_file() and p.stat().st_size==f['bytes'],'继承文件大小/物理边界变化')
        if '/img1/' not in f['official_member']:
            require(ref(p)['sha256']==f['sha256'],'继承小元数据SHA变化');metadata+=1
    require(metadata==6,'继承元数据不全')
    return cfg,parent,sources,files,missing,storage


def execute(config,expected):
    require(ref(config)['sha256']==expected,'恢复config SHA不符')
    cfg,parent,sources,files,missing,storage=preflight(config)
    control=Path(cfg['control'])
    write_new(control/'started.json',dict(config=ref(config),inherited_sources=['SNMOT-061','SNMOT-098'],download_only='SNMOT-154'))
    receipt=dict(schema='extra_real_train_input_manifest_v1',status='started',protocol=ref(config),proposal=parent['proposal'],
        sequences=list(sources),files=list(files),inherited_failed_manifest=cfg['failed_manifest'],inherited_images=1500,
        newly_downloaded_images=0,old_failed_manifest_modified=False,JPEG_inheritance_rehashed_or_redecoded=False,
        test_requested=False,det_file_extracted_or_used=False,models_inferred=False,optimizer_updates=0,training_authorized=False,
        started_utc=datetime.now(timezone.utc).isoformat())
    reader=None
    try:
        from PIL import Image
        instrument_transport(original.remote,control/'http_lengths.jsonl')
        url=f'https://huggingface.co/datasets/{original.remote.REPO}/resolve/{original.remote.REVISION}/train.zip?download=true'
        reader=original.BoundedMetadataReader(url,original.remote.SIZES['train'],budget=cfg['network_budget_bytes']);archive=zipfile.ZipFile(reader)
        selected=[]
        for declared in missing['members']:
            name=declared['name'];require(name.startswith('train/SNMOT-154/') and ('/img1/' in name or name.endswith(('/gt/gt.txt','/gameinfo.ini','/seqinfo.ini'))),'恢复成员越界')
            info=archive.getinfo(name)
            require(info.file_size==declared['size'] and info.compress_size==declared['compressed_size'] and f'{info.CRC:08x}'==declared['crc32'],'官方索引变化')
            selected.append(info)
        start=min(x.header_offset for x in selected);end=max(x.header_offset+30+len(x.filename.encode('utf-8'))+len(x.extra)+x.compress_size for x in selected)
        require(end-start==180105721 and len(selected)==753,'原缺失范围变化')
        print(json.dumps(dict(sequence='SNMOT-154',phase='fetching_missing_only',network_range_bytes=end-start,inherited_images=1500)),flush=True)
        if cfg['schema']=='extra_real_train_recovery_v2':
            bounded_clip_range(reader,start,end,control/'verified_range_blocks.jsonl',cfg['range_block_bytes'])
        else:
            reader.seek(start);reader.read(end-start)
        new_files=[];decoded=0;GT_rows=0
        for info in selected:
            data=archive.read(info);require(len(data)==info.file_size and zlib.crc32(data)&0xffffffff==info.CRC,'新成员CRC/长度不符')
            target=storage.physical_child(DATA/Path(info.filename).relative_to('train'),DATA)
            target.parent.mkdir(parents=True,exist_ok=True)
            if '/img1/' in info.filename:
                with Image.open(io.BytesIO(data)) as image:
                    image.load();require(image.size==(1920,1080),'分辨率不符');decoded+=1
            elif info.filename.endswith('/gt/gt.txt'):
                rows=[x.split(',') for x in data.decode('utf-8-sig').splitlines() if x.strip()]
                require(all(len(x)>=9 and 1<=int(x[0])<=750 for x in rows),'GT范围不符');GT_rows=len(rows)
            with target.open('xb') as f:f.write(data)
            record=dict(path=str(target),official_member=info.filename,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),ZIP_CRC32=f'{info.CRC:08x}')
            new_files.append(record);receipt['files'].append(record)
            if decoded and decoded%150==0:print(json.dumps(dict(sequence='SNMOT-154',decoded=decoded)),flush=True)
        require(decoded==750 and GT_rows>0,'新源没有完整解码/GT')
        receipt['sequences'].append(dict(sequence='SNMOT-154',game_id=missing['game_id'],frames=750,width=1920,height=1080,fps=25,
            GT_rows=GT_rows,game_time_start=missing['game_time_start'],game_time_stop=missing['game_time_stop'],files=new_files))
        receipt.update(status='complete2250_extra_real_train_frames_decoded_not_prediction_or_training_authorized',images=2250,
            newly_downloaded_images=750,new_independent_matches=0,source_repo=original.remote.REPO,revision=original.remote.REVISION,
            annotation_labour_cost_measured=False,existing_base_frames_copied=False)
    except BaseException as error:
        receipt.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        if reader is not None:receipt.update(network_received_bytes=reader.downloaded,network_upper_bound_with_retries=reader.attempted_range_upper_bound,transient_failures=reader.transient_failures)
        receipt['finished_utc']=datetime.now(timezone.utc).isoformat()
        write_new(Path(cfg['result_manifest']),receipt)
    return dict(status=receipt['status'],images=2250,inherited_images=1500,new_images=750,optimizer_updates=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--config-sha256');a=p.parse_args()
    if a.execute:result=execute(a.config,a.config_sha256)
    else:
        preflight(a.config);result=dict(status='readonly_missing154_recovery_preflight_complete',inherited_images=1500,new_images=750,optimizer_updates=0)
    print(json.dumps(result,ensure_ascii=False))
