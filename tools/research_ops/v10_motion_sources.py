"""v10三个新增运动seed的源轨迹选择；只写CPU输入，不创建UE资产或渲染。"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/appearance'))
from pose_seeded_kit_plan import build_binding

SEEDS = (1042, 1044, 1131)
FROZEN_ACTIVE_POLICY_SHA = '8592a6de59b5d0c29308db51b1deae1c2bc027440391961793310ae6d26de93c'
OUTFIELDS = tuple(side+str(i) for side in 'LR' for i in range(1, 5))
POLICY = dict(frames=300, fps=10, min_active_outfields=4, active_speed_mps=.5,
    active_coverage=.8, max_low_motion_seconds=3., min_four_player_extent_m=1.5,
    max_speed_mps=12., local_window_frames=30, local_extent_m=1., max_local_low_seconds=3.,
    close_pair_m=1.5, crossing_half_span_frames=2, same_pair_event_refractory_frames=10,
    ranking=['crossing_proxy_event_count_desc', 'close_pair_frame_count_desc', 'source_start_asc'])


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=Path(path).as_posix(), sha256=sha(path))


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')


def longest_low(flags):
    longest = current = 0
    for good in flags:
        current = 0 if good else current+1
        longest = max(longest, current)
    return longest


def extent(points):
    return math.hypot(max(p[0] for p in points)-min(p[0] for p in points),
                      max(p[1] for p in points)-min(p[1] for p in points))


def select(frames, active_range):
    require(len(frames) >= 300 and all(f['step'] == i and abs(f['time_seconds']-i/10) < 1e-6
            for i, f in enumerate(frames)), '完整源步序/10FPS不符')
    positions = [{p['id']: p['position_m'][:2] for p in f['players']} for f in frames]
    require(all(set(row) == {side+str(i) for side in 'LR' for i in range(5)}
            and all(math.isfinite(v) for p in row.values() for v in p) for row in positions), 'roster或坐标无效')
    speeds = [dict.fromkeys(OUTFIELDS, 0.)]+[{pid: math.dist(positions[i][pid], positions[i-1][pid])*10
              for pid in OUTFIELDS} for i in range(1, len(frames))]
    active = [sum(v >= .5 for v in row.values()) >= 4 for row in speeds]
    local = []
    for i in range(len(frames)):
        left = max(0, min(len(frames)-30, i-15)); right = left+30
        local.append(sum(extent([p[pid] for p in positions[left:right]]) >= 1. for pid in OUTFIELDS) >= 4)
    close = [0]*len(frames); events = []
    for a, b in combinations(OUTFIELDS, 2):
        last = -100
        for i in range(len(frames)):
            if math.dist(positions[i][a], positions[i][b]) > 1.5:
                continue
            close[i] += 1
            if 2 <= i < len(frames)-2 and i-last >= 10:
                before = [positions[i-2][a][j]-positions[i-2][b][j] for j in range(2)]
                after = [positions[i+2][a][j]-positions[i+2][b][j] for j in range(2)]
                if sum(x*y for x, y in zip(before, after)) < 0:
                    events.append(dict(source_step=i, entities=[a, b], same_team=a[0] == b[0])); last = i
    lo, hi = active_range
    require(0 <= lo <= hi-300 and hi <= len(frames), 'v1父活跃范围不足300帧')
    rejected = Counter(); eligible = []
    for start in range(lo, hi-300+1):
        end = start+300; motion = active[start+1:end]; spatial = []
        for pid in OUTFIELDS:
            spatial.append(extent([p[pid] for p in positions[start:end]]))
        if sum(motion)/299 < .8:
            rejected['active_coverage'] += 1; continue
        if longest_low(motion) > 30 or longest_low(local[start+1:end]) > 30:
            rejected['long_low_motion'] += 1; continue
        if sum(v >= 1.5 for v in spatial) < 4:
            rejected['spatial_extent'] += 1; continue
        if max(v for row in speeds[start+1:end] for v in row.values()) > 12:
            rejected['teleport_speed'] += 1; continue
        selected_events = [e for e in events if start+2 <= e['source_step'] < end-2]
        eligible.append(dict(source_frame_range=[start, end], crossing_proxy_events=selected_events,
            close_pair_frame_count=sum(close[start:end]), active_coverage=sum(motion)/299,
            max_low_motion_seconds=longest_low(motion)/10, max_local_low_seconds=longest_low(local[start+1:end])/10))
    require(eligible, '无合格300连续帧，不能放宽后伪造成功')
    chosen = min(eligible, key=lambda w: (-len(w['crossing_proxy_events']), -w['close_pair_frame_count'], w['source_frame_range'][0]))
    return dict(chosen=chosen, eligible_count=len(eligible), rejected=dict(rejected), policy=POLICY,
                not_image_crossing_or_physical_occlusion=True, model_outputs_read=False)


def build(output, *, prepare=False):
    old_input = ROOT/'Saved/Pose17Development/long_window_inputs_a02/sources/seed_00001048/source_input.json'
    template = read(old_input); data = []
    for seed in SEEDS:
        source = ROOT/f'Saved/Production/v1_no_numbers_4k/sources/source_s{seed:08d}'
        clip_path = Path(f'G:/FutsalMOT_Dataset/v1_no_numbers_4k/groups/seed_{seed:08d}/clip.json')
        clip = read(clip_path); scope = clip['source_selection']
        require(scope['policy_sha256'] == FROZEN_ACTIVE_POLICY_SHA
                and sha(source/'frames.jsonl') == scope['source_frames_sha256']
                and sha(source/'meta.json') == scope['source_meta_sha256'], 'v1完整原始轨迹绑定变化')
        raw_lines = (source/'frames.jsonl').read_bytes().splitlines(keepends=True)
        frames = [json.loads(line) for line in raw_lines]
        meta = read(source/'meta.json'); require(meta['timing']['source_step_seconds'] == .1, '10FPS源不符')
        selection = select(frames, scope['source_step_range'])
        appearance = source/'provenance/appearance.json'; profile = source/'provenance/ue-profile.json'
        kit = build_binding(read(appearance), meta, source/'frames.jsonl', read(profile)['appearance'], template['targets'])
        item = dict(seed=seed, split='train', selection=selection,
            original_source=dict(meta=ref(source/'meta.json'), frames=ref(source/'frames.jsonl'), original_steps=1800),
            original_v1_clip=ref(clip_path), original_appearance=ref(appearance), original_profile=ref(profile),
            kit_binding=kit, original_frozen_active_range=scope['source_step_range'],
            targets=deepcopy(template['targets']), calibration_manifests=deepcopy(template['calibration_manifests']),
            camera_bindings=deepcopy(template['camera_bindings']))
        data.append((item, meta, raw_lines))
    result = dict(schema='v10_multiseed_motion_CPU_inputs_v1', status='readonly_candidate',
        source_selector=ref(__file__), roster_template=ref(old_input), independent_new_motion_seeds=list(SEEDS),
        reused_green_motion_seed=1048, excluded_synthetic_dev=1102, policy=POLICY,
        groups=[v[0] for v in data], planned_new_RGB=3600, planned_new_person_pose=36000,
        render_admitted=False, training_admitted=False, UE_assets_created=False, test116187_read=False)
    if not prepare:
        return result
    output = output.absolute()
    require((ROOT/'Saved') in output.parents and not output.exists(), '只写全新项目Saved元数据，不重放partial')
    for part in (output, *output.parents):
        if part.exists():
            require(not getattr(part.lstat(), 'st_file_attributes', 0) & 0x400 and not part.is_symlink(), '不经联接写入')
    output.mkdir(parents=True)
    for item, original_meta, lines in data:
        start, end = item['selection']['chosen']['source_frame_range']
        directory = output/f"seed_{item['seed']:08d}"; directory.mkdir()
        meta = deepcopy(original_meta); meta['timing']['num_steps'] = end
        dump(directory/'meta.json', meta)
        (directory/'frames.jsonl').write_bytes(b''.join(lines[:end]))
        with (directory/'frame_mapping.jsonl').open('x', encoding='utf-8') as stream:
            for index in range(300):
                stream.write(json.dumps(dict(capture_local_index=index, source_step=start+index,
                    sequence_frame=start+index, source_time_seconds=(start+index)/10), separators=(',', ':'))+'\n')
        item.update(schema='v10_pose17_multiseed_source_input_v1', selected_source_frame_range=[start,end],
            context_source_frame_range=[0,end], capture_local_frame_range=[0,300], fps=10, selected_frames=300,
            prefix_steps=end, source_frame_equals_sequence_frame=True,
            prepared_prefix={k:ref(directory/name) for k,name in [('meta','meta.json'),('frames','frames.jsonl'),('frame_mapping','frame_mapping.jsonl')]},
            P2_sequence_package=f"/Game/FutsalMOT/Development/Pose17/multiseed_v10_a01/seed_{item['seed']:08d}",
            native_records_per_camera=3000, visibility_state='unknown', MRQ_sync_verified=False)
        dump(directory/'source_input.json', item)
    result['status'] = 'CPU_sources_selected_and_prefix_prepared_not_UE_verified'
    dump(output/'manifest.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args(); value = build(args.output, prepare=args.prepare)
    print(json.dumps(dict(status=value['status'], selected=[dict(seed=g['seed'],
        source_range=g['selection']['chosen']['source_frame_range'],
        crossing_proxy_events=len(g['selection']['chosen']['crossing_proxy_events'])) for g in value['groups']]), ensure_ascii=True))
