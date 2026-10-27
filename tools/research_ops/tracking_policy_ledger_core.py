"""零更新政策差异账本：原缓存单次流读，原MOT全保留，GT仅作后验几何代理。"""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import traceback


METHODS = ('official_ocsort', 'PT_bbox', 'strong_motion_RS')
BUCKETS = ('below_0.1', 'equal_0.1', 'between_0.1_0.25', 'equal_0.25',
           'between_0.25_0.6', 'equal_0.6', 'above_0.6')
ELIGIBILITY = ('oc_default_high', 'oc_alternative_025_high', 'byte_high', 'byte_low')
RELATIONS = ('mutual_unique', 'no_IoU05_candidate', 'ambiguous_multiple_right', 'ambiguous_shared_right')
UNKNOWN = 'unknown_from_MOT'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def safe(path):
    path = Path(os.path.abspath(path))
    require(not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
                    for part in path.parts), '最终测试继续封存')
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            require(not item.is_symlink() and not getattr(item.lstat(), 'st_file_attributes', 0) & 0x400,
                    '账本读写不跟随junction')
    return path


def sha(path):
    digest = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def ref(path):
    return dict(path=str(safe(path)), sha256=sha(path))


def checked(reference):
    path = safe(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '绑定来源改变：' + str(path))
    return path


def read_reference(reference):
    return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def f32(value):
    """忠实模拟原FP32检测分数与NumPy FP32阈值比较，不引入epsilon。"""
    require(type(value) in (int, float) and math.isfinite(value), '分数必须有限数值')
    try:
        result = struct.unpack('<f', struct.pack('<f', float(value)))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError('分数不能表示为FP32') from exc
    require(math.isfinite(result), 'FP32分数非有限')
    return result


THRESHOLDS = {'low': f32(.1), 'high': f32(.25), 'oc': f32(.6)}


def score_policy(value):
    score = f32(value)
    require(0 <= score <= 1, '检测confidence必须在[0,1]')
    low, high, oc = (THRESHOLDS[key] for key in ('low', 'high', 'oc'))
    if score < low:
        bucket = BUCKETS[0]
    elif score == low:
        bucket = BUCKETS[1]
    elif score < high:
        bucket = BUCKETS[2]
    elif score == high:
        bucket = BUCKETS[3]
    elif score < oc:
        bucket = BUCKETS[4]
    elif score == oc:
        bucket = BUCKETS[5]
    else:
        bucket = BUCKETS[6]
    return dict(score_float32=score, bucket=bucket,
                oc_default_high=score > oc, oc_alternative_025_high=score > high,
                byte_high=score >= high, byte_low=low < score < high)


def valid_box(box):
    return isinstance(box, (list, tuple)) and len(box) == 4 and all(
        type(value) in (int, float) and math.isfinite(value) for value in box) and min(box[2:]) > 0


def iou(left, right):
    """沿用原v8连续坐标xywh公式，不裁边、不使用像素+1。"""
    require(valid_box(left) and valid_box(right), '几何代理必须正面积有限xywh')
    x, y, w, h = left
    u, v, s, t = right
    intersection = max(0, min(x+w, u+s)-max(x, u)) * max(0, min(y+h, v+t)-max(y, v))
    union = w*h+s*t-intersection
    return intersection/union if union > 0 else 0.


def mutual_unique(left_boxes, right_boxes, right_ids):
    """返回同帧全部候选和双向唯一代理；不让GT参与反向挑选raw。"""
    require(len(right_boxes) == len(right_ids) and len(set(map(str, right_ids))) == len(right_ids),
            '右侧身份必须一一对应且唯一')
    edges = []
    for left in left_boxes:
        row = []
        for index, right in enumerate(right_boxes):
            overlap = iou(left, right)
            if overlap >= .5:
                row.append((index, overlap))
        edges.append(row)
    degrees = Counter(index for row in edges for index, _ in row)
    answer = []
    for row in edges:
        if not row:
            state = RELATIONS[1]
        elif len(row) > 1:
            state = RELATIONS[2]
        elif degrees[row[0][0]] > 1:
            state = RELATIONS[3]
        else:
            state = RELATIONS[0]
        answer.append(dict(state=state, candidate_ids=[right_ids[index] for index, _ in row],
                           candidate_IoU=[overlap for _, overlap in row],
                           mutual_unique_id=right_ids[row[0][0]] if state == RELATIONS[0] else None))
    return answer


def posthoc_frame(raw, gt):
    """GT-frame机会使用任一几何候选，独立于互唯一raw身份代理。"""
    raw_relations = mutual_unique([d['bbox_xywh_px'] for d in raw],
                                 [g['bbox_xywh_px'] for g in gt], [g['gt_id'] for g in gt])
    opportunities = []
    for target in gt:
        indices = [index for index, detection in enumerate(raw)
                   if iou(detection['bbox_xywh_px'], target['bbox_xywh_px']) >= .5]
        high = [raw[index]['uid'] for index in indices if raw[index]['policy']['oc_default_high']]
        alternative = [raw[index]['uid'] for index in indices if raw[index]['policy']['oc_alternative_025_high']]
        opportunities.append(dict(gt_id=target['gt_id'], candidate_raw_UIDs=[raw[index]['uid'] for index in indices],
            oc_gt06_raw_UIDs=high, oc_gt025_raw_UIDs=alternative, any_raw=bool(indices),
            any_oc_gt06=bool(high), any_oc_gt025=bool(alternative),
            no_oc_gt06_but_any_oc_gt025=not high and bool(alternative)))
    return raw_relations, opportunities


def parse_mot_bytes(data, frames):
    """只解析实际发出记录，不重编号、不筛低分、不恢复内部生命周期。"""
    require(type(frames) is int and frames > 0, 'MOT帧数非法')
    by_frame = defaultdict(list)
    seen = set()
    for line in data.decode('utf-8-sig').splitlines():
        if not line.strip():
            continue
        values = list(map(float, line.split(',')))
        require(len(values) == 10 and all(math.isfinite(value) for value in values), 'MOT必须10列有限数值')
        require(values[0].is_integer() and 1 <= values[0] <= frames and values[1].is_integer()
                and values[1] > 0 and valid_box(values[2:6]), 'MOT帧/原ID/框非法')
        frame, identity = int(values[0]), int(values[1])
        require((frame, identity) not in seen, 'MOT同帧重复原ID')
        seen.add((frame, identity))
        by_frame[frame].append(dict(identity=identity, bbox_xywh_px=values[2:6], mot_score_field=values[6]))
    return dict(by_frame), len(seen)


def emitted_trajectories(unit, by_frame):
    identities = defaultdict(list)
    for frame, rows in sorted(by_frame.items()):
        for row in rows:
            identities[row['identity']].append(frame)
    answer = []
    for identity, frames in sorted(identities.items()):
        gaps = [dict(previous_emitted_frame=a, next_emitted_frame=b, unemitted_frames=b-a-1)
                for a, b in zip(frames, frames[1:]) if b-a > 1]
        answer.append(dict(unit_id=unit['unit_id'], method=unit['method'], sequence=unit['sequence'],
            fold=unit.get('fold'), seed=unit.get('seed'), identity=identity,
            first_emitted_frame=frames[0], last_emitted_frame=frames[-1], emitted_frames=len(frames),
            emitted_span_frames=frames[-1]-frames[0]+1, emission_gap_count=len(gaps),
            unemitted_frames_within_span=sum(g['unemitted_frames'] for g in gaps),
            max_unemitted_gap=max((g['unemitted_frames'] for g in gaps), default=0),
            same_ID_reemission_after_gap_count=len(gaps), emission_gaps=canonical(gaps),
            internal_birth=UNKNOWN, internal_confirmation=UNKNOWN, internal_lost=UNKNOWN,
            suppression_reason=UNKNOWN, physical_occlusion_or_recovery=UNKNOWN))
    return answer


def load_gt(cfg, sequence):
    """只导入已绑定的原纯GT加载器；不调用旧validate/dependencies或模型。"""
    key = 'seven' if sequence in cfg['panels']['seven_observed'] else 'old_five'
    entry = cfg['GT_loaders'][key]
    require(entry['function'] == 'load_gt', '仅允许原纯GT加载函数')
    path = checked(entry['module'])
    require(path.name == ('substitution_tracking_runtime.py' if key == 'seven' else 'v10_tracking_runtime.py'),
            'GT加载器身份不同')
    spec = importlib.util.spec_from_file_location('ledger_frozen_GT_' + key + '_' + entry['module']['sha256'][:12], path)
    value = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        sys.modules[spec.name] = value
        spec.loader.exec_module(value)
        gt, lines = value.load_gt(cfg['sources'][sequence])
    finally:
        sys.dont_write_bytecode = previous
    require(isinstance(gt, dict) and sum(map(len, gt.values())) == len(lines), '原GT加载结果计数不符')
    for frame, rows in gt.items():
        require(type(frame) is int and 1 <= frame <= cfg['sources'][sequence]['frames'], 'GT帧越界')
        require(len({g['gt_id'] for g in rows}) == len(rows) and all(valid_box(g['bbox_xywh_px']) for g in rows),
                'GT同帧身份重复或框无效')
    return gt


class JsonLines:
    def __init__(self, path):
        self.path = path
        self.raw = path.open('xb')
        self.stream = gzip.GzipFile(filename='', mode='wb', fileobj=self.raw, mtime=0)
        self.count = 0

    def write(self, value):
        self.stream.write((canonical(value) + '\n').encode('utf-8'))
        self.count += 1

    def close(self):
        self.stream.close()
        self.raw.flush()
        os.fsync(self.raw.fileno())
        self.raw.close()


FRAME_FIELDS = ('sequence', 'frame_number', 'frame_index', 'raw_detections', 'GT_rows', *BUCKETS,
                *ELIGIBILITY, 'raw_GT_mutual_unique', 'raw_GT_no_candidate', 'raw_GT_ambiguous',
                'GT_any_raw', 'GT_any_oc_gt06', 'GT_any_oc_gt025', 'GT_no_oc_gt06_but_any_oc_gt025')
TRAJECTORY_FIELDS = ('unit_id', 'method', 'sequence', 'fold', 'seed', 'identity', 'first_emitted_frame',
    'last_emitted_frame', 'emitted_frames', 'emitted_span_frames', 'emission_gap_count',
    'unemitted_frames_within_span', 'max_unemitted_gap', 'same_ID_reemission_after_gap_count',
    'emission_gaps', 'internal_birth', 'internal_confirmation', 'internal_lost', 'suppression_reason',
    'physical_occlusion_or_recovery')


def write_json_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(canonical(value) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _inventory(cfg, sequence):
    require(cfg.get('test_sealed') is True and cfg.get('new_optimizer_updates', 0) == 0, '零更新/封存边界缺失')
    require(sequence in cfg['sources'] and sequence in sum(cfg['panels'].values(), []), '未登记源')
    source = cfg['sources'][sequence]
    require(source['sequence'] == sequence and source['frames'] > 0 and source['fps'] == 25, '源身份/时间域改变')
    units = [unit for unit in cfg['units'] if unit['sequence'] == sequence]
    methods = Counter(unit['method'] for unit in units)
    expected_strong = 3 if sequence in cfg['panels']['original_heldout'] else 9
    require(methods == dict(official_ocsort=1, PT_bbox=1, strong_motion_RS=expected_strong), '每场OC/PT及全foldseed必须完整')
    require(len({unit['unit_id'] for unit in units}) == len(units), '单位ID重复')
    for unit in units:
        require(unit['source_cache'] == source['cache'] and unit['frames'] == source['frames']
                and len(unit['frame_counts']) == source['frames'] and sum(unit['frame_counts']) == unit['tracked_rows'],
                '单位输入/全部帧计数改变')
        require(all(type(n) is int and n >= 0 for n in unit['frame_counts']), '单位发出计数非法')
    strong = [u for u in units if u['method'] == 'strong_motion_RS']
    require(len({(u['fold'], u['seed']) for u in strong}) == len(strong), '不能重复fold/seed')
    return source, units


def _unit_input(unit, frames):
    path = safe(unit['mot']['path'])
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == unit['mot']['sha256'], '实际MOT绑定变化')
    by_frame, count = parse_mot_bytes(data, frames)
    require(count == unit['tracked_rows'] and [len(by_frame.get(i, [])) for i in range(1, frames+1)]
            == unit['frame_counts'], 'MOT全部原输出/逐帧计数不同')
    # 收据与评价仅验证来源，不重算评价，也不从其性能值选择任何输出。
    tracking = read_reference(unit['tracking_receipt'])
    metric = read_reference(unit['metric_report'])
    require(tracking['status'] == metric['status'] == 'complete'
            and tracking['frames'] == metric['frames'] == frames
            and tracking['tracked_rows'] == count and tracking['frame_counts'] == unit['frame_counts']
            and tracking['mot_sha256'] == unit['mot']['sha256'], 'MOT与实际完成收据不同')
    if unit['method'] == 'official_ocsort':
        require(metric['tracking_receipt'] == unit['tracking_receipt'], 'OC显式评价来源链不同')
        require(tracking['source_cache'] == metric['source_cache'] == unit['source_cache'], 'OC追踪缓存不同')
    else:
        require(metric['tracking_receipt_sha256'] == unit['tracking_receipt']['sha256'], '原PT/strong评价来源链不同')
        require(tracking['cache'] == unit['source_cache'], '原PT/strong追踪缓存不同')
    return by_frame, metric['GT_rows']


def _read_raw(line, sequence, source, expected_frame, seen_UIDs):
    frame = json.loads(line.decode('utf-8-sig'))
    require(frame['sequence'] == sequence and frame['frame_number'] == expected_frame
            and frame['frame_index'] == expected_frame-1 and frame['fps'] == source['fps']
            and abs(frame['timestamp_sec'] - (expected_frame-1)/source['fps']) < 1e-9
            and frame['width'] == source['width'] and frame['height'] == source['height'], '缓存帧身份/时间/尺寸改变')
    raw = []
    for detection in frame['detections']:
        # 仅读白名单，Pose/GT/geometry_valid均不参与政策资格或几何候选。
        uid, box, score = (detection[key] for key in ('uid', 'bbox_xywh_px', 'score'))
        require(type(uid) is str and uid and uid not in seen_UIDs and valid_box(box), 'raw UID不唯一或框非法')
        seen_UIDs.add(uid)
        raw.append(dict(uid=uid, bbox_xywh_px=box, score_original=score, policy=score_policy(score)))
    return raw


def analyze_sequence(cfg, sequence, output):
    """由根控制器在独立2worker中调用；本函数不推理、不评价、不修改输入。"""
    source, units = _inventory(cfg, sequence)
    output = safe(output)
    root = safe(cfg['output_root'])
    require(root in output.parents and not output.exists(), '仅独占新序列目录，拒绝partial覆盖')
    output.mkdir(parents=True)
    intent = dict(schema='tracking_policy_sequence_ledger_intent_v1', sequence=sequence,
        source_cache=source['cache'], units=[u['unit_id'] for u in units], implementation=ref(__file__),
        new_optimizer_updates=0, tracker_or_model_or_TrackEval_rerun=False, test_read=False)
    write_json_new(output/'intent.json', intent)
    opened = []
    try:
        gt = load_gt(cfg, sequence)
        unit_inputs = {u['unit_id']: _unit_input(u, source['frames']) for u in units}
        outputs = {key: value[0] for key, value in unit_inputs.items()}
        require(all(value[1] == sum(map(len, gt.values())) for value in unit_inputs.values()),
                '原GT加载口径与全部既有评价不同')
        writers = {}
        for name in ('raw_ledger', 'output_ledger', 'GT_opportunity_ledger'):
            writers[name] = JsonLines(output/(name+'.jsonl.gz'))
            opened.append(writers[name])
        frame_stream = (output/'frame_ledger.csv').open('x', encoding='utf-8', newline='')
        opened.append(frame_stream)
        frame_writer = csv.DictWriter(frame_stream, fieldnames=FRAME_FIELDS)
        frame_writer.writeheader()
        total = Counter()
        buckets = Counter({key: 0 for key in BUCKETS})
        eligibility = Counter({key: 0 for key in ELIGIBILITY})
        raw_GT_states = Counter({key: 0 for key in RELATIONS})
        opportunity_counts = Counter({key: 0 for key in ('GT_any_raw', 'GT_any_oc_gt06', 'GT_any_oc_gt025',
                                                        'GT_no_oc_gt06_but_any_oc_gt025')})
        bucket_GT_states = {key: Counter({relation: 0 for relation in RELATIONS}) for key in BUCKETS}
        unit_counts = {u['unit_id']: dict(output_rows=0, frames_with_any_output=0,
            output_to_raw=Counter({key: 0 for key in RELATIONS}), output_to_GT=Counter({key: 0 for key in RELATIONS}),
            raw_geometric_proxy_score_buckets=Counter({key: 0 for key in BUCKETS}), raw_geometric_proxy_score_unknown=0)
            for u in units}
        digest = hashlib.sha256()
        seen_UIDs = set()
        cache_path = safe(source['cache']['path'])
        frame_number = 0
        with cache_path.open('rb') as cache:
            for line in cache:
                digest.update(line)
                if not line.strip():
                    continue
                frame_number += 1
                require(frame_number <= source['frames'], '缓存帧数超过原源')
                raw = _read_raw(line, sequence, source, frame_number, seen_UIDs)
                GT = gt.get(frame_number, [])
                raw_relation, opportunities = posthoc_frame(raw, GT)
                frame_counts = Counter(sequence=sequence, frame_number=frame_number, frame_index=frame_number-1,
                    raw_detections=len(raw), GT_rows=len(GT), **{key: 0 for key in (*BUCKETS, *ELIGIBILITY)})
                for detection, relation in zip(raw, raw_relation):
                    policy = detection['policy']
                    bucket = policy['bucket']
                    buckets[bucket] += 1
                    frame_counts[bucket] += 1
                    raw_GT_states[relation['state']] += 1
                    bucket_GT_states[bucket][relation['state']] += 1
                    for key in ELIGIBILITY:
                        eligibility[key] += int(policy[key])
                        frame_counts[key] += int(policy[key])
                    writers['raw_ledger'].write(dict(sequence=sequence, frame_number=frame_number,
                        uid=detection['uid'], score_original=detection['score_original'], **policy,
                        raw_to_GT=relation, GT_used_only_posthoc=True))
                for opportunity in opportunities:
                    writers['GT_opportunity_ledger'].write(dict(sequence=sequence, frame_number=frame_number,
                        **opportunity, interpretation='geometric_detection_opportunity_not_accuracy_or_policy_gain'))
                for column, field in (('GT_any_raw', 'any_raw'), ('GT_any_oc_gt06', 'any_oc_gt06'),
                    ('GT_any_oc_gt025', 'any_oc_gt025'), ('GT_no_oc_gt06_but_any_oc_gt025', 'no_oc_gt06_but_any_oc_gt025')):
                    count = sum(int(o[field]) for o in opportunities)
                    frame_counts[column] = count
                    opportunity_counts[column] += count
                frame_counts['raw_GT_mutual_unique'] = sum(r['state'] == RELATIONS[0] for r in raw_relation)
                frame_counts['raw_GT_no_candidate'] = sum(r['state'] == RELATIONS[1] for r in raw_relation)
                frame_counts['raw_GT_ambiguous'] = sum(r['state'].startswith('ambiguous') for r in raw_relation)
                frame_writer.writerow(dict(frame_counts))
                raw_by_UID = {d['uid']: d for d in raw}
                for unit in units:
                    identity = unit['unit_id']
                    rows = outputs[identity].get(frame_number, [])
                    counts = unit_counts[identity]
                    counts['output_rows'] += len(rows)
                    counts['frames_with_any_output'] += bool(rows)
                    to_raw = mutual_unique([r['bbox_xywh_px'] for r in rows],
                        [d['bbox_xywh_px'] for d in raw], [d['uid'] for d in raw])
                    to_GT = mutual_unique([r['bbox_xywh_px'] for r in rows],
                        [g['bbox_xywh_px'] for g in GT], [g['gt_id'] for g in GT])
                    for row, raw_proxy, GT_proxy in zip(rows, to_raw, to_GT):
                        counts['output_to_raw'][raw_proxy['state']] += 1
                        counts['output_to_GT'][GT_proxy['state']] += 1
                        match = raw_by_UID.get(raw_proxy['mutual_unique_id'])
                        if match is None:
                            counts['raw_geometric_proxy_score_unknown'] += 1
                        else:
                            counts['raw_geometric_proxy_score_buckets'][match['policy']['bucket']] += 1
                        writers['output_ledger'].write(dict(unit_id=identity, method=unit['method'],
                            sequence=sequence, fold=unit.get('fold'), seed=unit.get('seed'), frame_number=frame_number,
                            identity=row['identity'], mot_score_field=row['mot_score_field'],
                            raw_score_geometric_proxy=match['policy']['score_float32'] if match else None,
                            raw_score_proxy_bucket=match['policy']['bucket'] if match else None,
                            output_to_raw=raw_proxy, output_to_GT=GT_proxy,
                            raw_association='same_frame_geometry_proxy_not_internal_detection_binding',
                            internal_birth=UNKNOWN, internal_confirmation=UNKNOWN, internal_lost=UNKNOWN,
                            suppression_reason=UNKNOWN, GT_used_only_posthoc=True))
                total.update(source_frames=1, raw_detections=len(raw), GT_rows=len(GT))
        require(frame_number == source['frames'] and digest.hexdigest() == source['cache']['sha256'],
                '单次stream缓存SHA或全帧不符')
        require(total['raw_detections'] == source['counts']['raw_detections'], '完整raw分母与原冻结计数不同')
        trajectory_count = 0
        with (output/'trajectory_ledger.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=TRAJECTORY_FIELDS)
            writer.writeheader()
            for unit in units:
                trajectories = emitted_trajectories(unit, outputs[unit['unit_id']])
                writer.writerows(trajectories)
                trajectory_count += len(trajectories)
                unit_counts[unit['unit_id']]['emitted_trajectory_count'] = len(trajectories)
                unit_counts[unit['unit_id']]['emission_gap_count'] = sum(r['emission_gap_count'] for r in trajectories)
                unit_counts[unit['unit_id']]['same_ID_reemission_after_gap_count'] = sum(
                    r['same_ID_reemission_after_gap_count'] for r in trajectories)
        for stream in reversed(opened):
            stream.close()
        opened.clear()
        artifacts = {}
        for name, filename, count in (
            ('raw_ledger', 'raw_ledger.jsonl.gz', total['raw_detections']),
            ('frame_ledger', 'frame_ledger.csv', total['source_frames']),
            ('output_ledger', 'output_ledger.jsonl.gz', sum(c['output_rows'] for c in unit_counts.values())),
            ('GT_opportunity_ledger', 'GT_opportunity_ledger.jsonl.gz', total['GT_rows']),
            ('trajectory_ledger', 'trajectory_ledger.csv', trajectory_count)):
            artifacts[name] = dict(ref(output/filename), rows=count)
        summaries = []
        for unit in units:
            counts = unit_counts[unit['unit_id']]
            require(counts['output_rows'] == unit['tracked_rows'], '输出分母不能被几何筛选')
            summaries.append(dict(unit_id=unit['unit_id'], method=unit['method'], sequence=sequence,
                fold=unit.get('fold'), seed=unit.get('seed'), source_frames=source['frames'],
                mot=unit['mot'], tracking_receipt=unit['tracking_receipt'], metric_report=unit['metric_report'],
                source_cache=source['cache'], **counts, internal_lifecycle=UNKNOWN))
        result = dict(schema='tracking_policy_sequence_ledger_v1',
            status='complete_sequence_raw_output_posthoc_policy_ledger', sequence=sequence,
            source_cache=source['cache'], source_GT={k: source[k] for k in ('gt', 'gt_reference', 'gameinfo') if k in source},
            GT_loader=cfg['GT_loaders']['seven' if sequence in cfg['panels']['seven_observed'] else 'old_five'],
            source_counts=dict(total), source_denominator_copies=1, score_thresholds_float32=THRESHOLDS,
            score_buckets=dict(buckets), raw_eligibility=dict(eligibility), raw_to_GT_states=dict(raw_GT_states),
            score_bucket_raw_to_GT={key: dict(value) for key, value in bucket_GT_states.items()},
            GT_opportunities=dict(opportunity_counts), units=summaries,
            unit_frames=sum(u['frames'] for u in units), artifacts=artifacts,
            cache_stream_passes=1, GT_annotations_loaded=True, GT_used_only_for_posthoc_geometry=True,
            GT_used_for_tracking=False, predictions_GT_filtered=False, score_policy_changed_or_executed=False,
            internal_lifecycle_observed=False, raw_score_proxy_is_internal_binding=False,
            no_overlap_is_absolute_false_positive=False, opportunity_is_accuracy_or_tracking_gain=False,
            new_optimizer_updates=0, new_model_or_tracker_or_TrackEval_runs=0, media_read=False, test_read=False,
            implementation=intent['implementation'])
        write_json_new(output/'summary.json', result)
        return result
    except BaseException as exc:
        for stream in reversed(opened):
            try:
                stream.close()
            except Exception:
                pass
        write_json_new(output/'failure.json', dict(status='failed_partial_preserved', sequence=sequence,
            error=repr(exc), traceback=traceback.format_exc(), implicit_retry=False,
            new_optimizer_updates=0, test_read=False))
        raise
