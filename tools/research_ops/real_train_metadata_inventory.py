"""仅下载官方train归档的gameinfo/seqinfo小元数据，不下载图像/GT或访问test。"""
import argparse
from collections import defaultdict
import configparser
import hashlib
import http.client
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import traceback
import urllib.error
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'experiments/sim2real'))
import download_public as remote

OriginalReader=remote.HTTPRangeReader


class BoundedMetadataReader(OriginalReader):
    """只对网络短读/超时有界重试，位置复原；范围或状态不符仍直接失败。"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs);self.attempted_range_upper_bound=0;self.transient_failures=[]

    def read(self, length=-1):
        start=self.position;size=self.size-start if length<0 else min(length,self.size-start)
        for attempt in range(3):
            self.position=start
            cached=self.cache_start<=start and start+size<=self.cache_start+len(self.cache)
            requested=0 if cached or not size else min(self.size-start,max(size,65536))
            if self.attempted_range_upper_bound+requested>self.budget:raise RuntimeError('含重试的网络范围上限已达到预算')
            self.attempted_range_upper_bound+=requested
            try:return super().read(length)
            except (RuntimeError,TimeoutError,urllib.error.URLError,http.client.IncompleteRead) as error:
                transient=not isinstance(error,RuntimeError) or str(error)=='HTTP range 长度不匹配'
                if not transient or attempt==2:raise
                self.transient_failures.append(dict(start=start,requested=size,attempt=attempt+1,error=repr(error)))


def execute(output,inherit_report=None):
    spec=importlib.util.spec_from_file_location('metadata_storage',ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    st=importlib.util.module_from_spec(spec);spec.loader.exec_module(st)
    base=Path('D:/projects/FutsalMOT_Research')
    output=st.physical_child(output,base/'pose/pose_mechanism_a01')
    if output.exists(): raise ValueError('元数据partial不覆盖，不自动重放')
    index=json.loads((base/'public/soccernet_tracking/train_zip_index.json').read_text(encoding='utf-8'))
    if (index['repo'],index['revision'],len(index['sequences']))!=(remote.REPO,remote.REVISION,57):
        raise ValueError('原官方train来源改变')
    inherited=None
    if inherit_report:
        inherit_report=st.physical_child(inherit_report,base/'pose/pose_mechanism_a01')
        inherited=json.loads(inherit_report.read_text(encoding='utf-8'))
        if inherited['status']!='failed_preserved_no_replay' or inherited['revision']!=remote.REVISION:raise ValueError('只显式继承同revision的失败元数据，不覆盖旧收据')
    output.mkdir(parents=True); receipt=dict(schema='real_train_metadata_inventory_v1',status='started',split='train',
        revision=remote.REVISION,repo=remote.REPO,network_budget=32*1024**2,GT_downloaded=False,images_downloaded=False,
        test_requested=False,optimizer_updates=0,sequences=[],started_utc=datetime.now(timezone.utc).isoformat())
    receipt['inherited_failed_report']=dict(path=str(inherit_report),sha256=hashlib.sha256(inherit_report.read_bytes()).hexdigest()) if inherit_report else None
    receipt['old_partial_modified']=False
    try:
        remote.HTTPRangeReader=BoundedMetadataReader
        reader,archive=remote.open_archive('train',receipt['network_budget'])
        official={m['name']:m for m in index['members']}
        games=defaultdict(list)
        for seq in index['sequences']:
            entry=dict(sequence=seq,files={})
            for name in ('gameinfo.ini','seqinfo.ini'):
                member=f'train/{seq}/{name}'; info=archive.getinfo(member)
                if info.file_size>65536 or info.file_size!=official[member]['size'] or f'{info.CRC:08x}'!=official[member]['crc32']:
                    raise ValueError('元数据大小/CRC与已固定train索引不符')
                previous=inherit_report.parent/seq/name if inherit_report else None
                if previous and previous.exists():
                    st.physical_child(previous,inherit_report.parent);data=previous.read_bytes();target=previous;origin='explicit_verified_inheritance'
                else:
                    data=archive.read(info);target=output/seq/name;target.parent.mkdir(exist_ok=True)
                    with target.open('xb') as f:f.write(data)
                    origin='new_missing_metadata_only'
                if len(data)!=info.file_size or zlib.crc32(data)&0xffffffff!=info.CRC:raise ValueError('本地或下载的元数据CRC/长度错误')
                entry['files'][name]=dict(path=str(target),bytes=len(data),ZIP_CRC32=f'{info.CRC:08x}',sha256=hashlib.sha256(data).hexdigest(),origin=origin)
                text=configparser.ConfigParser();text.read_string(data.decode('utf-8-sig'))
                if name=='gameinfo.ini':
                    section=text['Sequence'];entry.update(game_id=section['gameID'],clip_start=section['clipStart'],clip_stop=section['clipStop'],
                        game_time_start=section['gameTimeStart'],game_time_stop=section['gameTimeStop'],action=section['actionClass'])
                else:
                    section=text['Sequence'];entry.update(frame_count=int(section['seqLength']),fps=int(section['frameRate']))
            receipt['sequences'].append(entry);games[entry['game_id']].append(seq)
            print(json.dumps(dict(sequence=seq,game=entry['game_id'],metadata_only=True)),flush=True)
        receipt.update(status='complete57_train_clip_metadata_no_images_GT_models',games=dict(games),network_bytes=reader.downloaded,
            requests=reader.requests,network_range_upper_bound_with_retries=reader.attempted_range_upper_bound,
            transient_failures=reader.transient_failures,annotation_savings_measured=False,identity_limit='gameID groups official source; actual match title still requires verification')
    except BaseException as error:
        receipt.update(status='failed_preserved_no_replay',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        receipt['finished_utc']=datetime.now(timezone.utc).isoformat()
        with (output/'report.json').open('x',encoding='utf-8') as f: json.dump(receipt,f,ensure_ascii=False,indent=2)
    return dict(status=receipt['status'],games={g:len(v) for g,v in games.items()},network_bytes=reader.downloaded)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--inherit-report',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(execute(a.output,a.inherit_report) if a.execute else dict(status='readonly_train_metadata_inventory_plan',split='train',test=False),ensure_ascii=False))
