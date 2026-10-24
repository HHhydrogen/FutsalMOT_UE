"""显式同实体路径适配；不修改冻结缓存/数值，只接受两条已登记迁移映射。"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys

PROJECT=Path('D:/projects/FutsalMOT_UEDataset')
CODE=PROJECT/'Content/FutsalMOT/code'
OUTPUT=Path('G:/FutsalMOT_Research/pose/association_dev_a01/v4_association_path_a02')
MAPPINGS=((Path('D:/projects/FutsalMOT_Research'),Path('G:/FutsalMOT_Research')),
    (PROJECT/'Saved',Path('G:/FutsalMOT_Workspace/UE/Saved')))
CACHE=Path('G:/FutsalMOT_Research/pose/association_dev_a01/raw_detections/cache_manifest.json')
CACHE_SHA='3028fa8cf73737ae459afda4226bad33b55c6ef34cd817efb548ae417e6c462d'
JSONL_SHA='6268addda27fe636e94434aa7e61580d5409accdabe73f0b7c82613afc2f581e'

def require(ok,message):
    if not ok:raise ValueError(message)
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def lexical(path):
    path=Path(path).absolute()
    require('..' not in path.parts and not any(part.lower() in ('test','test2017','test2014')
        or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)',part.lower()) for part in path.parts),'封存域或父目录逃逸：在stat前拒绝')
    return path

def no_unregistered_reparse(path,allowed=()):
    for part in (path,*path.parents):
        if part.exists():
            attrs=getattr(part.lstat(),'st_file_attributes',0)
            require(not (part.is_symlink() or attrs&0x400) or part in allowed,'未登记reparse路径，拒绝放宽边界: '+str(part))

def canonical(path):
    path=lexical(path)
    for old,new in MAPPINGS:
        if path==old or old in path.parents:
            require(old.exists() and new.is_dir() and old.resolve()==new.resolve() and os.path.samefile(old,new),
                '迁移映射未证明同实体: '+str(old))
            no_unregistered_reparse(path,(old,))
            actual=path.resolve();expected=new/path.relative_to(old)
            require(actual==expected.absolute(),'已登记根下另有路径重定向，拒绝')
            no_unregistered_reparse(actual)
            return actual
    no_unregistered_reparse(path)
    require(path.resolve()==path,'非已登记路径存在重定向')
    return path

def new_output(path):
    path=canonical(path)
    require(OUTPUT in path.parents and not path.exists(),'只允许全新a02已登记子目录，不覆盖旧失败产物')
    return path

def install():
    """局限在新进程独立模块命名空间；不写原Python文件/manifest。"""
    sys.path.insert(0,str(CODE/'src'));sys.path.insert(0,str(CODE/'experiments/sim2real'))
    fixed=importlib.import_module('prepare_pose_association_dev')
    fixed.plain=canonical
    fixed.output_path=new_output
    return fixed

def preflight():
    fixed=install()
    require(digest(CACHE)==CACHE_SHA,'原cache manifest SHA变化')
    manifest,frames=fixed.load_fixed_cache(CACHE,CACHE_SHA)
    raw=canonical(manifest['detections_jsonl']['path'])
    require(digest(raw)==JSONL_SHA,'原JSONL SHA变化')
    return dict(status='explicit_same_entity_path_adapter_CPU_preflight',adapter_source_sha256=digest(__file__),
        migration_mappings=[dict(legacy=str(a),actual=str(b),samefile=os.path.samefile(a,b)) for a,b in MAPPINGS],
        raw_manifest_sha256=CACHE_SHA,raw_jsonl_sha256=JSONL_SHA,frames=len(frames),
        detections=sum(len(row['detections']) for row in frames),numeric_records_rewritten=False,
        original_sources_changed=False,GPU_used=False,test_read=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=('cache-preflight','attachment','tracking','metrics'))
    args,remaining=parser.parse_known_args()
    if args.operation=='cache-preflight':
        print(json.dumps(preflight(),ensure_ascii=False));return
    require('--output' in remaining,'原子任务缺显式新输出目录')
    new_output(remaining[remaining.index('--output')+1])
    install()
    name={'attachment':'attach_fixed_detection_pose','tracking':'run_pose_association_dev','metrics':'evaluate_pose_association_dev'}[args.operation]
    module=importlib.import_module(name)
    if args.operation=='metrics':module.metric.safe_path=canonical
    sys.argv=[str(module.__file__)]+remaining
    module.main()

if __name__=='__main__':main()
