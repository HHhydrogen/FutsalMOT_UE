"""v10三运动12单位独立发布；原world逐机位保留，未知partial拒绝重放。"""
import argparse
import hashlib
from itertools import combinations, zip_longest
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python/src'))
from grf_ue_bridge.storage_policy import physical_child, DATASET_ROOT
from run_seeded_kit_short_a01 import read, sha, save, require
from run_seeded_kit_full_a02 import identity
from run_green_kit_serial_a01 import running

RUN = ROOT / 'Saved/AppearancePlanning/multiseed_v10_a01'
TARGET = DATASET_ROOT / 'v4_pose17_multiseed_green_a01'
WINDOWS = {1042: [152, 452], 1044: [383, 683], 1131: [565, 865]}
CAMERAS = tuple('CineCam_%02d' % n for n in range(1, 5))
ENTITIES = {side + str(n) for side in 'LR' for n in range(5)}


def bound(ref):
    path = Path(ref['path'])
    require(sha(path) == ref['sha256'], '原始来源SHA改变：' + str(path))
    return read(path)


def require_exited(pid, name, token):
    own = [row for row in identity(pid) if row['Name'].lower() == name.lower()
           and token.lower() in (row['CommandLine'] or '').replace('\\', '/').lower()]
    require(not own or not running(pid), '实际相关进程仍活动，不发布')


def prepare():
    control = RUN / 'control_full_a01'
    state = read(control / 'state.json')
    require(state['schema'] == 'futsalmot_multiseed_v10_serial_v1' and state['scope'] == 'v10_a01'
            and state['status'] == 'complete_full_12_units_EXR_retired_wait_root_publication'
            and len(state['completed']) == 12
            and (state['rgb'], state['mask'], state['person_pose']) == (3600, 3600, 36000),
            'v10十二实际单位未完整闭合')
    admission = read(RUN / 'admission_full_a01.json')
    require(sha(RUN / 'admission_full_a01.json') == state['admission_sha256']
            and admission['schema'] == 'futsalmot_v10_multiseed_admission_v1'
            and admission['stage'] == 'full' and admission['runtime_authorized'] is True
            and sha(RUN / 'manifest.json') == admission['manifest_sha256']
            and sha(RUN / 'short_acceptance_root.json') == admission['short_acceptance_sha256']
            and sha(RUN / 'P2_sources_prepare.json') == admission['source_prepare_sha256'],
            '完整准入/源/短样链改变')
    require_exited(state['pid'], 'python.exe', 'run_multiseed_v10_serial.py')
    physical_child(TARGET, DATASET_ROOT)
    require(not TARGET.exists(), '目标或未知partial已存在，拒绝自动重放')
    refs = {r['attempt']: r for r in read(RUN / 'manifest.json')['full_units']}
    require(len(refs) == 12, '原完整清单不为十二单位')
    items, moves = {}, []
    for row in state['completed']:
        ref = refs[row['attempt']]
        seed, camera = ref['seed'], ref['camera_id']
        key = (seed, camera)
        require(seed in WINDOWS and camera in CAMERAS and key not in items and row['seed'] == seed
                and ref['variant'] == row['variant'] == 'B' and ref['stage'] == 'full'
                and row['rgb'] == row['mask'] == row['EXR_deleted'] == 300
                and row['person_pose'] == 3000 and row['normal_UE_exit'] is True,
                '单位身份重复/计数/退出不完整')
        plan = bound(ref)
        stage = physical_child(row['stage'], DATASET_ROOT)
        require(stage == DATASET_ROOT / '_staging' / row['attempt'], '不是精确单位stage')
        group, post, index = (read(stage / name) for name in
                              ('group.json', 'postprocess_complete.json', 'dataset.json'))
        require(group['capture_experiment'] == 'multiseed_v10_a01' and group['stage'] == 'full'
                and group['independent_motion_scope'] == plan['source_scope']
                and group['seed'] == seed and group['split'] == 'train' and group['variant'] == 'B'
                and group['source_frame_range'] == WINDOWS[seed]
                and group['capture_scope']['camera_ids'] == [camera]
                and list(group['cameras']) == [camera]
                and group['green_floor'] == plan['seeded_kit_pair']['green_floor']
                and group['source_motion'] == plan['source_motion']
                and group['world_values_modified'] is False and group['not_training'] is True
                and group['diagnostic_only'] is True and group['MRQ_sync_verified'] is False
                and group['green_floor_restored']['status'] == 'original_floor_slot_restored_not_saved'
                and index['status'] == post['status'] == 'complete'
                and (index['rgb_frames'], index['mask_frames'], index['person_pose']) == (300, 300, 3000)
                and post['producer_output_closed'] is post['bounded_worker_pool_closed'] is True
                and len(post['views']) == 1, '实际范围/来源/限制/导出未闭合')
        bound(group['plan']); bound(group['state'])
        # 逐帧native已由原后处理消费验收；这里只保留其原引用，不重读约90MB的原生明细。
        native = group['cameras'][camera]['native_receipt']
        require(Path(native['path']).is_file() and len(native['sha256']) == 64, '原native引用缺失')
        require(post['dataset_index']['path'] == str(stage / 'dataset.json')
                and post['dataset_index']['sha256'] == sha(stage / 'dataset.json'), '导出索引SHA不同')
        view = post['views'][0]
        require(view['frames'] == 300 and view['person_records'] == 3000, '机位帧数不同')
        for field, relative in (('pose_jsonl', 'pose2d_ref'), ('world_jsonl', 'pose3d_world_ref')):
            require(physical_child(view[field]['path'], stage) == stage / group['cameras'][camera][relative],
                    '机位逐行记录路径重定向')
        shutdown = read(control / (row['attempt'] + '__shutdown.json'))
        retirement = read(control / (row['attempt'] + '__EXR_complete.json'))
        require(shutdown['status'] == 'normal_exit_confirmed' and shutdown['process_absent'] is True
                and retirement['status'] == 'exr_deleted_after_complete_consumers'
                and retirement['file_count'] == 300 and retirement['bytes'] == row['EXR_bytes'],
                '正常退出或EXR退休链不完整')
        log = Path(shutdown['log'])
        expected = ROOT / 'Saved/EditorStartup' / ('green_' + row['attempt']) / 'editor.log'
        require(log == expected, '不是本次UE日志')
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - 131072)); tail = stream.read()
        require(b'LogExit: Exiting.' in tail and b'Log file closed' in tail, '缺本次正常退出日志')
        require_exited(shutdown['pid'], 'UnrealEditor.exe', str(log).replace('\\', '/'))
        destination = physical_child(TARGET / 'groups' / ('seed_%08d' % seed) / 'views' / camera, DATASET_ROOT)
        items[key] = dict(stage=stage, destination=destination, group=group, post=post, row=row)
        actual_view = physical_child(stage / group['cameras'][camera]['view_ref'], stage)
        items[key]['view_sha256'] = sha(actual_view)
        moves.append(dict(source=str(stage), destination=str(destination),
                          group_sha256=sha(stage / 'group.json'), dataset_sha256=sha(stage / 'dataset.json'),
                          postprocess_sha256=sha(stage / 'postprocess_complete.json')))
    require(set(items) == {(s, c) for s in WINDOWS for c in CAMERAS}, '三运动四机位不完整')
    for seed in WINDOWS:
        example = items[(seed, CAMERAS[0])]['group']
        require(all(all(items[(seed, c)]['group'][key] == example[key] for key in
                    ('source_motion', 'green_floor', 'original_seeded_kit_binding', 'keypoint_names'))
                    for c in CAMERAS), '同运动上下文不同，发布前拒绝')
    return state, items, moves


def world_metadata(items, seed):
    """四条world流各读一次；身份/源时间严格相同，数值差只如实报告。"""
    import contextlib
    hashes = [hashlib.sha256() for _ in CAMERAS]
    exact, maximum, count, seen = True, 0.0, 0, set()
    pairs = {a + '/' + b: 0.0 for a, b in combinations(CAMERAS, 2)}
    refs = [items[(seed, c)]['post']['views'][0]['world_jsonl'] for c in CAMERAS]
    with contextlib.ExitStack() as stack:
        streams = [stack.enter_context(Path(ref['path']).open('rb')) for ref in refs]
        for lines in zip_longest(*streams):
            require(all(line is not None for line in lines), '四机位world记录行数不同')
            records = [json.loads(line) for line in lines]
            for digest, line in zip(hashes, lines): digest.update(line)
            base = records[0]; key = (base['frame_index'], base['entity_id'])
            require(key not in seen and key[0] in range(300) and key[1] in ENTITIES
                    and base['source_frame_index'] == WINDOWS[seed][0] + key[0], 'world重复或源帧错位')
            seen.add(key)
            require(all(all(r[k] == base[k] for k in ('frame_index', 'source_frame_index', 'entity_id',
                        'track_id', 'mesh_identity', 'manifest_sha256')) for r in records), '跨机位身份/标定改变')
            require(all(len(r['world_m']) == 17 and all(len(p) == 3 and all(math.isfinite(v) for v in p)
                        for p in r['world_m']) for r in records), 'world不是有限17点')
            for (i, a), (j, b) in combinations(enumerate(CAMERAS), 2):
                delta = max(math.dist(p, q) for p, q in zip(records[i]['world_m'], records[j]['world_m']))
                pairs[a + '/' + b] = max(pairs[a + '/' + b], delta)
                exact &= records[i]['world_m'] == records[j]['world_m']; maximum = max(maximum, delta)
            count += 1
    require(count == 3000 and [h.hexdigest() for h in hashes] == [r['sha256'] for r in refs],
            'world完整记录数或来源SHA不符')
    return dict(records_per_camera=count, all_world_exact=exact, max_world_delta_m=maximum,
                camera_pair_max_delta_m=pairs, world_values_modified=False,
                synchronized_multiview_truth_claimed=False, use_scope='per_view_identity_research')


def publish():
    state, items, moves = prepare()
    metrics = {str(seed): world_metadata(items, seed) for seed in WINDOWS}
    TARGET.mkdir(exist_ok=False); receipt = TARGET / '_publication_a01'; receipt.mkdir()
    save(receipt / 'intent.json', dict(schema='v10_publication_intent_v1', status='intent_not_complete',
         control_sha256=sha(RUN / 'control_full_a01/state.json'), moves=moves, media_copied=0,
         world_scope='per_view_no_exact_or_tolerance_upgrade'), True)
    with (receipt / 'moves.jsonl').open('x', encoding='utf-8') as journal:
        for row in moves:
            source = physical_child(row['source'], DATASET_ROOT)
            destination = physical_child(row['destination'], DATASET_ROOT)
            require(not destination.exists(), '目标已存在，保留partial')
            destination.parent.mkdir(parents=True, exist_ok=True)
            journal.write(json.dumps(dict(event='intent', **row)) + '\n'); journal.flush(); os.fsync(journal.fileno())
            os.rename(source, destination)
            journal.write(json.dumps(dict(event='moved', destination=str(destination))) + '\n')
            journal.flush(); os.fsync(journal.fileno())
    groups = {}
    for seed in WINDOWS:
        example = items[(seed, CAMERAS[0])]['group']; cameras = {}
        for camera in CAMERAS:
            item = items[(seed, camera)]; original = item['group']['cameras'][camera]; prefix = 'views/' + camera + '/'
            cameras[camera] = {k: prefix + original[k] for k in ('view_ref', 'pose2d_ref', 'pose3d_world_ref')}
            cameras[camera].update(capture_unit_ref=prefix + 'group.json',
                rgb_directory_ref=prefix + 'cameras/' + camera + '/rgb', mask_directory_ref=prefix + 'cameras/' + camera + '/mask',
                native_receipt=original['native_receipt'], view_sha256=item['view_sha256'],
                frames=300, record_layout='one_person_per_line')
        folder = TARGET / 'groups' / ('seed_%08d' % seed)
        group = dict(schema='futsalmot_v10_multiseed_group_v1', seed=seed, split='train', variant='B',
            cameras=cameras, fps=10, source_frame_range=WINDOWS[seed], source_motion=example['source_motion'],
            keypoint_names=example['keypoint_names'], green_floor=example['green_floor'],
            original_seeded_kit_binding=example['original_seeded_kit_binding'], world_storage='per_camera_native',
            world_values_modified=False, diagnostic_only=True, not_training=True, production_accepted=False,
            visibility='unknown', MRQ_sync_verified=False, synchronized_multiview_truth_claimed=False)
        save(folder / 'group.json', group, True)
        groups[str(seed)] = dict(group_ref=str((folder / 'group.json').relative_to(TARGET)), sha256=sha(folder / 'group.json'))
    save(receipt / 'world_metadata.json', dict(status='complete_stream_metadata_only', seeds=metrics,
         pixel_equivalence_claimed=False, physical_visibility_verified=False, world_values_modified=False), True)
    save(receipt / 'relocation.json', dict(schema='futsalmot_prefix_relocation_v1', directory_prefixes=moves,
         original_unit_and_consumer_receipt_bytes_preserved=True, no_reverse_junction_created=True), True)
    save(TARGET / 'dataset.json', dict(schema='futsalmot_v10_multiseed_dataset_v1', status='diagnostic_complete_not_training',
         groups=groups, rgb_frames=3600, mask_frames=3600, person_pose=36000, source_time_samples=900,
         fps=10, width=3840, height=2160, visibility='unknown', not_training=True, MRQ_sync_verified=False,
         synchronized_multiview_truth_claimed=False, source_control=dict(path=str(RUN / 'control_full_a01/state.json'),
         sha256=sha(RUN / 'control_full_a01/state.json')), world_metadata_ref='_publication_a01/world_metadata.json',
         relocation_ref='_publication_a01/relocation.json'), True)
    result = dict(status='published_v10_12_units_metadata_complete', dataset_sha256=sha(TARGET / 'dataset.json'),
                  rgb=3600, mask=3600, person_pose=36000, EXR_retired=3600, media_copied=0,
                  all_source_UE_normal_exit=True, all_world_exact=all(m['all_world_exact'] for m in metrics.values()),
                  max_world_delta_m=max(m['max_world_delta_m'] for m in metrics.values()), training_authorized=False)
    save(receipt / 'complete.json', result, True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    if args.publish: result = publish()
    else:
        _, items, moves = prepare()
        result = dict(status='readonly_v10_publication_plan', units=len(items), target=str(TARGET), moves=moves)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
