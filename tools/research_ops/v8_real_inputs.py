"""仅补齐官方train三场750帧；复用已有150图引用，不下载或读取封存test。"""
import argparse
import configparser
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
import time
import zipfile
import zlib

RESEARCH=Path('D:/projects/FutsalMOT_Research')
SEQUENCES={'SNMOT-060':'4','SNMOT-097':'6','SNMOT-151':'9'}
OLD=RESEARCH/'public/soccernet_tracking'

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def bind(path):return dict(path=str(path),sha256=sha(path))

def execute(config_path):
    config=read(config_path);bundle=Path(__file__).resolve().parents[2]
    require(bundle==Path(config['bundle']) and bundle.parent==RESEARCH/'code','仅D研究不可变执行代码')
    for entry in config['code_files']:require(sha(bundle/entry['path'])==entry['sha256'],'源码绑定变化')
    require(config['approved_by']=='root' and config['sequences']==SEQUENCES and config['frames']==750,'固定三场train域')
    helper=bundle/'experiments/sim2real/download_public.py'
    spec=importlib.util.spec_from_file_location('v8_official_train_range',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(module.REVISION==config['revision'] and module.REPO==config['repo'],'官方源revision不符')
    url=f'https://huggingface.co/datasets/{module.REPO}/resolve/{module.REVISION}/train.zip?download=true'
    output=Path(config['output']).resolve();require(output==RESEARCH/'public/association_v8_a02','固定新输入根')
    require(not output.exists(),'保留未知partial，显式另开下载attempt')
    # 元数据先确认比赛/长度，旧源与下载收据完全不改写。
    source={}
    for sequence,game_id in SEQUENCES.items():
        directory=OLD/'train'/sequence;info=configparser.ConfigParser();info.read(directory/'seqinfo.ini',encoding='utf-8')
        game=configparser.ConfigParser();game.read(directory/'gameinfo.ini',encoding='utf-8')
        require(game['Sequence']['gameid']==game_id and info.getint('Sequence','seqLength')==750 and info.getint('Sequence','frameRate')==25,'真实比赛/帧长不符')
        source[sequence]=dict(sequence_id=sequence,game_id=game_id,fps=25,width=1920,height=1080,frames=[],
            gameinfo=bind(directory/'gameinfo.ini'),seqinfo=bind(directory/'seqinfo.ini'),GT=bind(directory/'gt/gt.txt'),GT_role='training_fold_supervision_or_heldout_metrics_only')
    output.mkdir(parents=True)
    (output/'intent.json').write_text(json.dumps(dict(status='download_started',config_sha256=sha(config_path),url=url,frame_numbers=[1,750],test_read=False),indent=2)+'\n',encoding='utf-8')
    # 复用已验1MiB分块/4线程/3次有限重试，避免单个大Range短读导致整段丢失。
    sys.path.insert(0,str(helper.parent))
    spec=importlib.util.spec_from_file_location('v8_chunked_train_range',helper.with_name('download_development_extension.py'))
    chunked=importlib.util.module_from_spec(spec);spec.loader.exec_module(chunked)
    reader=chunked.ChunkReader(url,module.SIZES['train'],output/'_range_cache',config['network_budget_bytes'])
    archive=zipfile.ZipFile(reader)
    desired={}
    for info in archive.infolist():
        name=PurePosixPath(info.filename)
        sequence=module.sequence_of(info.filename)
        if sequence not in SEQUENCES:continue
        if name.name.endswith('.jpg') and name.parent.name=='img1':
            number=int(name.stem)
            if 1<=number<=750:
                require(not name.is_absolute() and '..' not in name.parts,'不安全ZIP路径')
                desired[(sequence,number)]=info
    require(len(desired)==2250,'官方三场帧清单不完整')
    downloaded=0;reused=0
    for sequence in SEQUENCES:
        missing=[desired[(sequence,number)] for number in range(151,751)]
        start=min(info.header_offset for info in missing)
        end=max(info.header_offset+30+len(info.filename.encode('utf-8'))+len(info.extra)+info.compress_size for info in missing)
        reader.seek(start);reader.read(end-start)
        for number in range(1,751):
            info=desired[(sequence,number)]
            if number<=150:
                image=OLD/'train'/sequence/'img1'/f'{number:06d}.jpg'
                require(image.is_file() and image.stat().st_size==info.file_size,'旧源首150缺失/长度变化')
                reused+=1;origin='existing_original_input_reference_not_copied'
            else:
                data=archive.read(info);require(len(data)==info.file_size and zlib.crc32(data)&0xffffffff==info.CRC,'官方ZIP长度/CRC未通过')
                image=output/'train'/sequence/'img1'/f'{number:06d}.jpg';image.parent.mkdir(parents=True,exist_ok=True)
                with image.open('xb') as stream:stream.write(data)
                downloaded+=1;origin='official_train_zip_new_member_CRC_verified'
            source[sequence]['frames'].append(dict(frame_index=number-1,frame_number=number,timestamp_sec=(number-1)/25,image_file=str(image),bytes=info.file_size,official_zip_CRC32=f'{info.CRC:08x}',origin=origin))
        print(json.dumps(dict(sequence=sequence,frames=750,network_bytes=reader.downloaded)),flush=True)
    result=dict(schema='futsalmot_v8_real_train_only_input_manifest',status='complete_2250_frames_three_matches',sequences=list(source.values()),repo=module.REPO,revision=module.REVISION,
        network_bytes=reader.downloaded,downloaded_images=downloaded,reused_original_references=reused,source_split='official_train',final116187_read=False,
        role='three_match_leave_one_game_out_pool_not_final_test',selection='canonical_first_train_sequence_each_game_predeclared',GT_used_for_predictions=False)
    (output/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],downloaded_images=downloaded,reused=reused,manifest=str(output/'manifest.json'))))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.execute:execute(args.config)
    else:print(json.dumps(dict(status='readonly_v8_train_only_download_plan',new_images=1800,reused=450,final_test_read=False)))
