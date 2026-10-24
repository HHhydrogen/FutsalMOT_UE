"""只接受已盘点的旧1042共480份EXR；默认dryrun，不接受其他路径/数据集。"""
import argparse
import json
import os
from pathlib import Path
import dataset_storage_policy as policy

RAW = policy.DATASET / 'v2_pose17_location_pilot_a01/_provenance/source_migrations/raw_attempts/location_pilot_s00001042_a01_gpu_lbs'
MANIFEST = policy.SAVED / 'StoragePolicy/legacy1042_exr_retirement_manifest_a01.json'
MANIFEST_A02 = policy.SAVED / 'StoragePolicy/legacy1042_exr_retirement_manifest_a02.json'
JOURNAL = policy.SAVED / 'StoragePolicy/legacy1042_exr_retirement_transaction_a01.jsonl'


def validate(manifest, expected):
    policy.require(manifest.absolute() in (MANIFEST.absolute(), MANIFEST_A02.absolute()),
                   '只接受预先固定的1042 a01/a02身份')
    policy.require(expected == policy.sha(manifest), 'manifest SHA不匹配')
    m = policy.read(manifest)
    revision = 'a02' if manifest.absolute() == MANIFEST_A02.absolute() else 'a01'
    policy.require(m.get('revision', 'a01') == revision, 'manifest文件名与固定revision不一致')
    policy.require(m['schema'] == 'legacy1042_exact_exr_retirement_v1'
                   and m['raw_root'] == str(RAW) and m['file_count'] == 480, '不是精确1042清单')
    policy.require(m['eligibility'] == 'retire_raw_exr_only_current_location_consumers_use_rgb_pose'
                   and m['registered_raw_consumers_found'] == [], '仍有登记的EXR消费者/未知状态')
    policy.require(not JOURNAL.exists(), f'已有事务，partial/重复执行拒绝: {JOURNAL}')
    for binding in m['evidence_bindings']:
        path = Path(binding['path'])
        root = next((r for r in (policy.DATASET, policy.RESEARCH, policy.SAVED,
                                 Path(__file__).resolve().parents[2] / 'tools') if path == r or r in path.parents), None)
        policy.require(root is not None, f'证据越界: {path}')
        policy.safe(path, root)
        policy.require(policy.sha(path) == binding['sha256'], f'依赖/发布证据变动: {path}')
    files = m['files']; seen = set()
    for item in files:
        p = policy.safe(item['path'], RAW)
        rel = p.relative_to(RAW)
        policy.require(len(rel.parts) == 2 and rel.parts[0] in ('CineCam_01','CineCam_02','CineCam_03','CineCam_04')
                       and p.suffix.lower() == '.exr' and str(p) not in seen, f'非精确EXR或重复: {p}')
        seen.add(str(p)); s=p.stat()
        policy.require(s.st_size == item['bytes'] and s.st_mtime_ns == item['mtime_ns'], f'EXR stat变化: {p}')
    policy.require(len(files) == len(seen) == 480, '清单数不等于480')
    actual = {str(p) for p, s, kind in policy.walk(RAW) if kind == 'file' and p.suffix.lower() == '.exr'}
    policy.require(actual == seen, '真实EXR集合与固定480清单不相等')
    # 独立实际输出元数据：只数文件与JSONL，不hash媒体。
    camera_root=policy.DATASET/'v2_pose17_location_pilot_a01/groups/seed_00001042/cameras'
    for cam in ('CineCam_01','CineCam_02','CineCam_03','CineCam_04'):
        for kind in ('rgb','mask'):
            d=policy.safe(camera_root/cam/kind,policy.DATASET)
            entries=list(os.scandir(d))
            policy.require(len(entries)==120 and all(e.is_file(follow_symlinks=False)
                and not policy.reparse(e.stat(follow_symlinks=False)) and Path(e.name).suffix=='.png' for e in entries),
                f'发布PNG数量/类型不一致: {d}')
        for name in ('pose2d.jsonl','pose3d_world.jsonl'):
            policy.require(policy.rowcount(camera_root/cam/name)==120, f'发布Pose/world帧不一致: {cam}/{name}')
    return m


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=MANIFEST)
    parser.add_argument('--expected-manifest-sha256',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    policy.require(args.manifest.absolute() in (MANIFEST.absolute(),MANIFEST_A02.absolute()),
                   '只接受预先固定的1042 a01/a02清单路径')
    m=validate(args.manifest,args.expected_manifest_sha256)
    summary=dict(status='dry_run',files=len(m['files']),bytes=m['bytes'],
        irreversible_loss='原始WorldDepth/Cryptomatte EXR；不影响已发布RGB/mask/Pose/world，metadata保持原值',
        no_wait_for_rgb_only_training=True)
    if not args.apply:
        print(json.dumps(summary,ensure_ascii=False));return
    # 单一固定journal的x模式阻止并发或partial重放；绝不覆盖旧事务。
    with JOURNAL.open('x',encoding='utf-8') as log:
        def record(obj):
            log.write(json.dumps(obj,ensure_ascii=False)+'\n');log.flush();os.fsync(log.fileno())
        record(dict(event='intent',manifest_sha256=args.expected_manifest_sha256,**summary))
        try:
            for item in m['files']:
                p=policy.safe(item['path'],RAW);s=p.stat()
                policy.require(s.st_size==item['bytes'] and s.st_mtime_ns==item['mtime_ns'],f'删除前stat变化: {p}')
                p.unlink()
                record(dict(event='deleted',**item))
            for binding in m['evidence_bindings']:
                policy.require(policy.sha(binding['path'])==binding['sha256'],f'清理期间证据变化: {binding["path"]}')
            record(dict(event='complete',files=480,bytes=m['bytes'],dataset_media_preserved=True,
                        raw_exr_retained=False,created_utc=policy.now()))
        except Exception as error:
            record(dict(event='partial_failure_no_automatic_retry',error=str(error)));raise
    summary['status']='legacy1042_480_exr_retired';print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
