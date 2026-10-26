"""按结果前清单获取三个额外真实train片段；不提取/使用det，不推理/训练或访问test。"""
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
sys.path[:0]=[str(ROOT/'experiments/sim2real'),str(ROOT/'tools/research_ops')]
import download_public as remote
from real_train_metadata_inventory import BoundedMetadataReader


def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def ref(path):return dict(path=str(path),sha256=sha(path))
def checked(value):
    p=Path(value['path']);require(p.is_file() and sha(p)==value['sha256'],'冻结来源变化');return p


def execute(config):
    cfg=read(config);require(cfg['schema']=='extra_real_train_acquisition_v1' and cfg['approved_by']=='root'
        and cfg['acquisition_authorized'] is True and cfg['training_authorized'] is False and cfg['test_sealed'] is True,'下载准入缺失')
    require(Path(cfg['bundle'])==ROOT and ROOT.parent==R/'code','只执行独立bundle')
    for entry in cfg['files']:require(sha(ROOT/entry['path'])==entry['sha256'],'下载源码变化')
    spec=importlib.util.spec_from_file_location('extra_real_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
    storage.physical_child(ROOT,R/'code')
    proposal=read(checked(cfg['proposal']));require(proposal['official_split']=='train' and proposal['revision']==remote.REVISION,'只允许官方固定train')
    require([s['sequence'] for s in proposal['sources']]==['SNMOT-061','SNMOT-098','SNMOT-154'],'不能自动加序列/读test')
    output=storage.physical_child(cfg['output'],R/'public');require(not output.exists(),'下载partial不覆盖，不自动重放');output.mkdir(parents=True)
    receipt=dict(schema='extra_real_train_input_manifest_v1',status='started',protocol=ref(config),proposal=cfg['proposal'],
        sequences=[],files=[],started_utc=datetime.now(timezone.utc).isoformat(),test_requested=False,det_file_extracted_or_used=False,
        GT_role='future_training_label_only_not_prediction_filter',models_inferred=False,optimizer_updates=0,training_authorized=False)
    try:
        from PIL import Image
        url=f'https://huggingface.co/datasets/{remote.REPO}/resolve/{remote.REVISION}/train.zip?download=true'
        reader=BoundedMetadataReader(url,remote.SIZES['train'],budget=cfg['network_budget_bytes']);archive=zipfile.ZipFile(reader)
        for source in proposal['sources']:
            seq=source['sequence'];selected=[]
            for declared in source['members']:
                name=declared['name'];require(name.startswith('train/'+seq+'/') and ('/img1/' in name or name.endswith(('/gt/gt.txt','/gameinfo.ini','/seqinfo.ini'))),'成员不在准入范围')
                info=archive.getinfo(name);require(info.file_size==declared['size'] and info.compress_size==declared['compressed_size'] and f'{info.CRC:08x}'==declared['crc32'],'官方ZIP索引变化')
                selected.append(info)
            require(sum('/img1/' in x.filename for x in selected)==750,'必须每源750帧')
            start=min(x.header_offset for x in selected);end=max(x.header_offset+30+len(x.filename.encode('utf-8'))+len(x.extra)+x.compress_size for x in selected)
            require(end-start<=512*1024**2,'单片段范围超过内存准入')
            print(json.dumps(dict(sequence=seq,phase='fetching_train_clip_only',network_range_bytes=end-start)),flush=True)
            reader.seek(start);reader.read(end-start)
            decoded=0;GT_rows=0;dims=set();source_files=[]
            for info in selected:
                data=archive.read(info);require(len(data)==info.file_size and zlib.crc32(data)&0xffffffff==info.CRC,'原成员CRC/长度不符')
                relative=Path(info.filename).relative_to('train');require('..' not in relative.parts and not relative.is_absolute(),'ZIP成员越界')
                target=storage.physical_child(output/relative,output);target.parent.mkdir(parents=True,exist_ok=True)
                if '/img1/' in info.filename:
                    with Image.open(io.BytesIO(data)) as image:
                        image.load();dims.add(image.size);require(image.size==(1920,1080),'源分辨率不符');decoded+=1
                elif info.filename.endswith('/gt/gt.txt'):
                    rows=[x.split(',') for x in data.decode('utf-8-sig').splitlines() if x.strip()]
                    require(all(1<=int(x[0])<=750 and len(x)>=9 for x in rows),'GT帧范围不符');GT_rows=len(rows)
                with target.open('xb') as f:f.write(data)
                record=dict(path=str(target),official_member=info.filename,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),ZIP_CRC32=f'{info.CRC:08x}')
                source_files.append(record);receipt['files'].append(record)
                if decoded and decoded%150==0:print(json.dumps(dict(sequence=seq,decoded=decoded)),flush=True)
            require(decoded==750 and GT_rows>0,'未完整解码或缺训练标签')
            receipt['sequences'].append(dict(sequence=seq,game_id=source['game_id'],frames=decoded,width=1920,height=1080,fps=25,
                GT_rows=GT_rows,game_time_start=source['game_time_start'],game_time_stop=source['game_time_stop'],files=source_files))
        receipt.update(status='complete2250_extra_real_train_frames_decoded_not_prediction_or_training_authorized',
            images=2250,network_received_bytes=reader.downloaded,network_upper_bound_with_retries=reader.attempted_range_upper_bound,
            transient_failures=reader.transient_failures,new_independent_matches=0,existing_base_frames_copied=False,
            annotation_labour_cost_measured=False,source_repo=remote.REPO,revision=remote.REVISION)
    except BaseException as error:
        receipt.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        receipt['finished_utc']=datetime.now(timezone.utc).isoformat()
        with (output/'manifest.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
    return dict(status=receipt['status'],frames=2250,new_optimizer_updates=0,network_bytes=reader.downloaded)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(execute(a.config) if a.execute else dict(status='readonly_extra_real_acquisition_plan_no_model_or_test'),ensure_ascii=False))
