"""复用现有EXR库存，读取定向发布/消费元数据，准备旧1042退休清单；不删除。"""
import argparse
import json
import os
from pathlib import Path
import dataset_storage_policy as p
from retire_legacy1042_exr import RAW, MANIFEST, MANIFEST_A02

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',choices=('a01','a02'),default='a01')
    revision=parser.parse_args().revision
    inventory=p.SAVED/'StoragePolicy/storage_inventory_20261025_a01.json'
    bindings=[]
    def bind(path):
        path=Path(path).absolute();bindings.append(dict(path=str(path),sha256=p.sha(path)))
        return path
    old=p.read(bind(inventory))
    files=[e for r in old['roots'] for e in r['exr'] if RAW in Path(e['path']).parents]
    files=[{k:e[k] for k in ('path','bytes','mtime_ns')} for e in files]
    p.require(len(files)==480,'原库存不是480份EXR')
    publication=p.read(bind(p.SAVED/'Pose17Development/location_pilot_g_publication_a01.json'))
    index=bind(p.DATASET/'v2_pose17_location_pilot_a01/dataset.json')
    p.require(publication['passed'] and publication['dataset']['sha256']==p.sha(index)
              and publication['rgb_frames']==publication['mask_frames']==1920
              and publication['person_pose_records']==19200,'旧位置pilot发布证据不匹配')
    source=p.read(bind(p.SAVED/'Pose17Development/diagnostic_location_pilot_s00001042_a01_gpu_lbs_export_a01/dataset.json'))
    p.require(source['status']=='diagnostic_export_complete_not_training'
              and source['exr_decode_count']==source['rgb_frames']==source['mask_frames']==480
              and source['native_pose_records']==4800,'1042后处理证据不匹配')
    group=bind(p.DATASET/'v2_pose17_location_pilot_a01/groups/seed_00001042/group.json')
    for cam in ('CineCam_01','CineCam_02','CineCam_03','CineCam_04'):
        for name in ('pose2d.jsonl','pose3d_world.jsonl','view.json'):
            bind(group.parent/'cameras'/cam/name)
    for name in ('prepare_longpair_v5.py','train_longpair_v5.py','v5_virtual_crop.py','v5_numeric_loader.py'):
        bind(ROOT/'tools/research_ops'/name)
    candidates=[]
    plans=p.SAVED/'ResearchPlanning'
    directories=sorted(plans.glob('longpair_v5_*'))
    if revision=='a02':
        directories.append(p.RESEARCH/'pose/poseonly_v5/candidate_a04')
        bundle=p.RESEARCH/'code/7e5b7a7500919a0088bb443b0d002560a2d47ef104276aee285dede052237c28'
        for name in ('train_longpair_v5.py','v5_virtual_crop.py','v5_numeric_loader.py'):
            bind(bundle/'tools/research_ops'/name)
    for directory in directories:
        if directory.is_symlink() or p.reparse(directory.lstat()): continue
        for path in sorted(directory.glob('*.virtual_location.jsonl')):
            n=0;exr_refs=[];roots=set()
            with path.open(encoding='utf-8') as f:
                for line in f:
                    if not line.strip():continue
                    obj=json.loads(line);n+=1;image=Path(obj['image_file'])
                    p.require(image.suffix.lower()=='.png' and p.DATASET in image.parents,'v5输入不是正式GDataset PNG')
                    roots.add(str(image).split('groups')[0])
                    if any('.exr' in x.lower() or str(RAW).lower() in x.lower() for x in p.strings(obj)):
                        exr_refs.append(n)
            candidates.append(dict(path=str(bind(path)),records=n,media='PNG via image_file',roots=sorted(roots),exr_reference_rows=exr_refs))
    p.require(candidates and not any(c['exr_reference_rows'] for c in candidates),'v5候选输入存在EXR/未知依赖')
    # 只遍历登记协议目录的元数据文件名，不重复统计/扫描媒体，不跟联接。
    registered=[];raw_consumers=[]
    roots=[p.RESEARCH/'pose/poseonly_v3',p.RESEARCH/'pose/poseonly_v4',p.RESEARCH/'pose/association_dev_a01',plans]
    if revision=='a02':roots.append(p.RESEARCH/'pose/poseonly_v5')
    selected=('protocol','admission','runtime_context','consumer','depth_job')
    for registry in roots:
        stack=[registry]
        while stack:
            directory=stack.pop()
            for item in os.scandir(directory):
                if item.is_symlink() or p.reparse(item.stat(follow_symlinks=False)):continue
                if item.is_dir(follow_symlinks=False):
                    stack.append(Path(item.path));continue
                path=Path(item.path)
                if path.suffix!='.json' or not any(s in path.name.lower() for s in selected):continue
                p.require(item.stat().st_size<4*1024**2,f'登记协议意外过大，需人工检查: {path}')
                obj=p.read(path);hits=[]
                for value in p.strings(obj):
                    v=value.replace('\\','/').lower()
                    if '.exr' in v or '/raw_attempts/' in v or 'worlddepth' in v:
                        hits.append(value)
                registered.append(str(bind(path)))
                if hits:raw_consumers.append(dict(path=str(path),hits=hits))
    changes=[]
    if revision=='a02':
        old=p.read(MANIFEST)
        for b in old['evidence_bindings']:
            if 'research_ops' in b['path'] and p.sha(b['path'])!=b['sha256']:
                changes.append(dict(path=b['path'],old_sha256=b['sha256'],new_sha256=p.sha(b['path']),
                    scope='v5九臂候选准备闭包完善；PNG虚拟裁剪/位置加载器未变，不新增EXR消费'))
    report=dict(schema='legacy1042_exr_dependency_review_v1',revision=revision,status='retirement_candidate_not_deleted',
        source_changes_from_a01=changes,
        created_utc=p.now(),original_inventory_reused=True,no_media_hash_or_pixel_scan=True,
        raw_root=str(RAW),exr_count=len(files),exr_bytes=sum(e['bytes'] for e in files),
        publication=dict(rgb=1920,mask=1920,person_pose=19200,source1042_rgb=480,source1042_mask=480,source1042_person_pose=4800),
        v5=dict(source='tools/research_ops current candidate code; not an assertion of GPU execution',
                method='VirtualCropDataset reads image_file PNG using cv2.imread, position supervision from JSONL; no EXR reader',inputs=candidates),
        registry_scope=[str(x) for x in roots],registered_metadata_checked=len(registered),registered_raw_consumers=raw_consumers,
        depth_research='未在上述当前协议/准入/消费者登记中发现WorldDepth或EXR实际消费。通用未来遮挡研究愿景不作为无期限保留本480原始EXR的任务锁；未来需独立重采，不能声称本原始深度仍保留。',
        restrictions_preserved='unknown / diagnostic / not_training / MRQ_sync_verified=false 不升级；world/native/calibration/trajectory/metadata保留',
        retirement_authorization='用户2026-10-25明确清理不再消费的EXR；root审核并执行独立固定清单工具',
        evidence_bindings=bindings)
    report_path=p.SAVED/('StoragePolicy/legacy1042_dependency_report_'+revision+'.json')
    p.write_new(report_path,report)
    manifest=dict(schema='legacy1042_exact_exr_retirement_v1',revision=revision,status='candidate_not_applied',raw_root=str(RAW),
        eligibility='retire_raw_exr_only_current_location_consumers_use_rgb_pose',registered_raw_consumers_found=raw_consumers,
        file_count=480,bytes=report['exr_bytes'],files=files,
        evidence_bindings=[*bindings,dict(path=str(report_path),sha256=p.sha(report_path))],
        irreversible_loss='原始WorldDepth/Cryptomatte EXR，未来深度消费需新采；不修改已有RGB/mask/Pose/world/校准/native')
    target=MANIFEST_A02 if revision=='a02' else MANIFEST
    p.write_new(target,manifest)
    print(json.dumps(dict(manifest=str(target),manifest_sha256=p.sha(target),registered_metadata=len(registered),
                          registered_raw_consumers_found=raw_consumers,files=480,bytes=report['exr_bytes']),ensure_ascii=False))


if __name__=='__main__':main()
