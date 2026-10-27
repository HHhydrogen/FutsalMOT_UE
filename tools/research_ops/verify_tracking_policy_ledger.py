"""零更新score/输出政策账本独立终验；只核已有账本与MOT，不再读原GT/缓存。"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack, closing, contextmanager
import csv
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import traceback

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/tracking_policy_ledger_a01'
BUCKETS = ('below_0.1', 'equal_0.1', 'between_0.1_0.25', 'equal_0.25', 'between_0.25_0.6', 'equal_0.6', 'above_0.6')
ELIGIBILITY = ('oc_default_high', 'oc_alternative_025_high', 'byte_high', 'byte_low')
RELATIONS = ('mutual_unique', 'no_IoU05_candidate', 'ambiguous_multiple_right', 'ambiguous_shared_right')
METHODS = ('official_ocsort', 'PT_bbox', 'strong_motion_RS')
PANELS = ('original_heldout', 'old_external', 'seven_observed')
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
FOLDS = ('game4', 'game6', 'game9'); SEEDS = (20261024, 20261025, 20261026)
UNKNOWN = 'unknown_from_MOT'
STATUS = 'complete12_sources114_MOT36_summaries_all_policy_ledgers_and_exit_verified'


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(path):
    path = Path(path); require(path.is_absolute(), '终验必须绝对路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower()) for p in path.parts),
        '仅物理研究根且最终测试封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '不经junction读写')
    return path


def sha(path):
    digest = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): digest.update(block)
    return digest.hexdigest()


def ref(path): return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path']); require(path.is_file() and sha(path) == value['sha256'], '已有来源或结果SHA改变：'+str(path))
    return path


def read(path): return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def f32(value):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1, 'raw分数必须有限且在[0,1]')
    return struct.unpack('<f', struct.pack('<f', value))[0]


def score_policy(value):
    score = f32(value); low, high, oc = (f32(v) for v in (.1, .25, .6))
    if score < low: index = 0
    elif score == low: index = 1
    elif score < high: index = 2
    elif score == high: index = 3
    elif score < oc: index = 4
    elif score == oc: index = 5
    else: index = 6
    return dict(score_float32=score, bucket=BUCKETS[index], oc_default_high=score > oc,
        oc_alternative_025_high=score > high, byte_high=score >= high, byte_low=low < score < high)


def relation_graph(relations, right_ids):
    """仅复核已记候选图的互唯一状态；不重新读GT坐标或计算IoU。"""
    known = {str(v) for v in right_ids}; require(len(known) == len(right_ids), '右侧原身份重复')
    counts = Counter()
    for value in relations:
        require(set(value) == {'state', 'candidate_ids', 'candidate_IoU', 'mutual_unique_id'}, '关系字段改变')
        candidates, overlaps = value['candidate_ids'], value['candidate_IoU']
        require(isinstance(candidates, list) and isinstance(overlaps, list) and len(candidates) == len(overlaps)
            and len(set(map(str, candidates))) == len(candidates) and set(map(str, candidates)) <= known
            and all(type(v) in (int, float) and math.isfinite(v) and .5 <= v <= 1 for v in overlaps), '候选ID/IoU分母非法')
        counts.update(map(str, candidates))
    for value in relations:
        candidates = value['candidate_ids']
        expected = (RELATIONS[1] if not candidates else RELATIONS[2] if len(candidates) > 1 else
                    RELATIONS[3] if counts[str(candidates[0])] > 1 else RELATIONS[0])
        require(value['state'] == expected and value['mutual_unique_id'] == (candidates[0] if expected == RELATIONS[0] else None),
            '所有无候选/歧义/互唯一必须保留，不能挑最近或借GT消歧')


def GT_opportunities(rows, raw, sequence, frame):
    expected_fields = {'sequence', 'frame_number', 'gt_id', 'candidate_raw_UIDs', 'oc_gt06_raw_UIDs', 'oc_gt025_raw_UIDs',
        'any_raw', 'any_oc_gt06', 'any_oc_gt025', 'no_oc_gt06_but_any_oc_gt025', 'interpretation'}
    require(len({str(v['gt_id']) for v in rows}) == len(rows), '同帧GT机会身份重复，不能复制填分母')
    by_uid = {v['uid']: v for v in raw}; counters = Counter({k: 0 for k in
        ('GT_any_raw', 'GT_any_oc_gt06', 'GT_any_oc_gt025', 'GT_no_oc_gt06_but_any_oc_gt025')})
    for row in rows:
        require(set(row) == expected_fields and row['sequence'] == sequence and row['frame_number'] == frame
            and row['interpretation'] == 'geometric_detection_opportunity_not_accuracy_or_policy_gain', 'GT机会字段/后验边界改变')
        candidates = row['candidate_raw_UIDs']
        require(isinstance(candidates, list) and len(candidates) == len(set(candidates)) and set(candidates) <= set(by_uid), 'GT机会引用其他帧/重复raw')
        high = [uid for uid in candidates if by_uid[uid]['oc_default_high']]
        alternative = [uid for uid in candidates if by_uid[uid]['oc_alternative_025_high']]
        require(row['oc_gt06_raw_UIDs'] == high and row['oc_gt025_raw_UIDs'] == alternative
            and row['any_raw'] is bool(candidates) and row['any_oc_gt06'] is bool(high)
            and row['any_oc_gt025'] is bool(alternative)
            and row['no_oc_gt06_but_any_oc_gt025'] is (not high and bool(alternative)), 'GT机会门限候选/资格计数不同')
        for field, key in [('GT_any_raw', 'any_raw'), ('GT_any_oc_gt06', 'any_oc_gt06'),
            ('GT_any_oc_gt025', 'any_oc_gt025'), ('GT_no_oc_gt06_but_any_oc_gt025', 'no_oc_gt06_but_any_oc_gt025')]:
            counters[field] += row[key]
    # 同一个候选图的双向描述必须一致；不使用GT身份反向挑raw。
    for detection in raw:
        ids = [v['gt_id'] for v in rows if detection['uid'] in v['candidate_raw_UIDs']]
        require(detection['raw_to_GT']['candidate_ids'] == ids, 'raw↔GT与GT-frame候选图不是同一完整分母')
    relation_graph([v['raw_to_GT'] for v in raw], [v['gt_id'] for v in rows])
    return counters


def atomic_raw(rows, sequence, frame, seen):
    expected_fields = {'sequence', 'frame_number', 'uid', 'score_original', 'score_float32', 'bucket', *ELIGIBILITY, 'raw_to_GT', 'GT_used_only_posthoc'}
    for value in rows:
        require(set(value) == expected_fields and value['sequence'] == sequence and value['frame_number'] == frame
            and type(value['uid']) is str and value['uid'] and value['uid'] not in seen
            and value['GT_used_only_posthoc'] is True, 'raw分母/UID或后验边界改变')
        seen.add(value['uid']); expected = score_policy(value['score_original'])
        for key, number in expected.items():
            if isinstance(number, bool): require(value[key] is number, 'FP32资格布尔不同')
            else: require(value[key] == number, 'FP32七桶或原分数cast不同')


def read_mot(unit):
    checked(unit['tracking_receipt']); checked(unit['metric_report'])
    path = checked(unit['mot']); by_frame = defaultdict(list); seen = set()
    with path.open(encoding='utf-8-sig') as stream:
        for line in stream:
            if not line.strip(): continue
            values = list(map(float, line.split(',')))
            require(len(values) == 10 and all(math.isfinite(v) for v in values)
                and values[0].is_integer() and 1 <= values[0] <= unit['frames']
                and values[1].is_integer() and values[1] > 0 and min(values[4:6]) > 0, '原MOT非法，不能删行修复')
            key = int(values[0]), int(values[1]); require(key not in seen, '同帧原MOT ID重复')
            seen.add(key); by_frame[key[0]].append(dict(identity=key[1], mot_score_field=values[6]))
    require(len(seen) == unit['tracked_rows'] and [len(by_frame[i]) for i in range(1, unit['frames']+1)] == unit['frame_counts'],
        '114原MOT全部行/空帧计数不同')
    return by_frame


def trajectory_rows(unit, by_frame):
    identities = defaultdict(list)
    for frame, rows in sorted(by_frame.items()):
        for row in rows: identities[row['identity']].append(frame)
    result = []
    for identity, frames in sorted(identities.items()):
        gaps = [dict(previous_emitted_frame=a, next_emitted_frame=b, unemitted_frames=b-a-1)
            for a, b in zip(frames, frames[1:]) if b-a > 1]
        result.append(dict(unit_id=unit['unit_id'], method=unit['method'], sequence=unit['sequence'], fold=unit['fold'], seed=unit['seed'],
            identity=identity, first_emitted_frame=frames[0], last_emitted_frame=frames[-1], emitted_frames=len(frames),
            emitted_span_frames=frames[-1]-frames[0]+1, emission_gap_count=len(gaps),
            unemitted_frames_within_span=sum(v['unemitted_frames'] for v in gaps), max_unemitted_gap=max((v['unemitted_frames'] for v in gaps), default=0),
            same_ID_reemission_after_gap_count=len(gaps), emission_gaps=canonical(gaps), internal_birth=UNKNOWN,
            internal_confirmation=UNKNOWN, internal_lost=UNKNOWN, suppression_reason=UNKNOWN, physical_occlusion_or_recovery=UNKNOWN))
    return result


def artifact_rows(reference, kind):
    path = checked(reference)
    if kind == 'json':
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                require(bool(line.strip()), '账本不能用空行代替完整记录'); yield json.loads(line)
    else:
        with path.open(encoding='utf-8-sig', newline='') as stream: yield from csv.DictReader(stream)


class FrameReader:
    def __init__(self, iterator): self.iterator = iterator; self.next = next(iterator, None)
    def take(self, frame):
        rows = []
        while self.next is not None and self.next['frame_number'] == frame:
            rows.append(self.next); self.next = next(self.iterator, None)
        require(self.next is None or (type(self.next['frame_number']) is int and self.next['frame_number'] > frame), '帧账本倒序/漏域')
        return rows


def check_csv_row(actual, expected):
    require(set(actual) == set(expected), 'CSV字段不同')
    for key, value in expected.items():
        if value is None: require(actual[key] == '', 'null不能补0')
        elif isinstance(value, (int, float)):
            require(math.isfinite(float(actual[key])) and float(actual[key]) == value, 'CSV计数/原值不同：'+key)
        else: require(actual[key] == value, 'CSV原标识或unknown不同：'+key)


def output_rows(rows, expected, raw, gt, unit, frame):
    require(len(rows) == len(expected), '全部MOT输出不得按GT或raw匹配筛除')
    by_uid = {v['uid']: v for v in raw}; result = dict(output_rows=len(rows), frames_with_any_output=int(bool(rows)),
        output_to_raw=Counter({k: 0 for k in RELATIONS}), output_to_GT=Counter({k: 0 for k in RELATIONS}),
        raw_geometric_proxy_score_buckets=Counter({k: 0 for k in BUCKETS}), raw_geometric_proxy_score_unknown=0)
    fields = {'unit_id', 'method', 'sequence', 'fold', 'seed', 'frame_number', 'identity', 'mot_score_field',
        'raw_score_geometric_proxy', 'raw_score_proxy_bucket', 'output_to_raw', 'output_to_GT', 'raw_association',
        'internal_birth', 'internal_confirmation', 'internal_lost', 'suppression_reason', 'GT_used_only_posthoc'}
    for value, original in zip(rows, expected):
        require(set(value) == fields and all(value[k] == unit[k] for k in ('unit_id', 'method', 'sequence', 'fold', 'seed'))
            and value['frame_number'] == frame and value['identity'] == original['identity']
            and value['mot_score_field'] == original['mot_score_field'] and value['GT_used_only_posthoc'] is True,
            '输出账本必须逐行保留原MOT/原ID/score/foldseed')
        require(value['raw_association'] == 'same_frame_geometry_proxy_not_internal_detection_binding'
            and all(value[k] == UNKNOWN for k in ('internal_birth', 'internal_confirmation', 'internal_lost', 'suppression_reason')),
            'MOT不能证明内部出生/确认/lost或抑制原因，也不证明内部raw绑定')
        for field in ('output_to_raw', 'output_to_GT'): result[field][value[field]['state']] += 1
        match = by_uid.get(value['output_to_raw']['mutual_unique_id'])
        require(value['raw_score_geometric_proxy'] == (match['score_float32'] if match else None)
            and value['raw_score_proxy_bucket'] == (match['bucket'] if match else None), '几何score代理或unknown被改写')
        if match: result['raw_geometric_proxy_score_buckets'][match['bucket']] += 1
        else: result['raw_geometric_proxy_score_unknown'] += 1
    relation_graph([v['output_to_raw'] for v in rows], list(by_uid))
    relation_graph([v['output_to_GT'] for v in rows], [v['gt_id'] for v in gt])
    return result


def add_unit(total, value):
    for key in ('output_rows', 'frames_with_any_output', 'raw_geometric_proxy_score_unknown'): total[key] += value[key]
    for key in ('output_to_raw', 'output_to_GT', 'raw_geometric_proxy_score_buckets'): total[key].update(value[key])


def verify_sequence(cfg, sequence, summary_path):
    summary_path = physical(summary_path); summary = read(summary_path); source = cfg['sources'][sequence]
    units = [v for v in cfg['units'] if v['sequence'] == sequence]
    require(summary['schema'] == 'tracking_policy_sequence_ledger_v1'
        and summary['status'] == 'complete_sequence_raw_output_posthoc_policy_ledger' and summary['sequence'] == sequence
        and summary['source_cache'] == source['cache'] and summary['source_denominator_copies'] == 1
        and summary['cache_stream_passes'] == 1 and summary['score_thresholds_float32'] == dict(low=f32(.1), high=f32(.25), oc=f32(.6)),
        '源只计一次、原FP32门限、单次stream来源不完整')
    require(summary['GT_annotations_loaded'] is True and summary['GT_used_only_for_posthoc_geometry'] is True
        and summary['GT_used_for_tracking'] is False and summary['predictions_GT_filtered'] is False
        and all(summary[k] is False for k in ('score_policy_changed_or_executed', 'internal_lifecycle_observed',
            'raw_score_proxy_is_internal_binding', 'no_overlap_is_absolute_false_positive', 'opportunity_is_accuracy_or_tracking_gain', 'media_read', 'test_read'))
        and summary['new_optimizer_updates'] == summary['new_model_or_tracker_or_TrackEval_runs'] == 0, '后验代理/unknown/零更新边界改变')
    loader = cfg['GT_loaders']['seven' if sequence in cfg['panels']['seven_observed'] else 'old_five']
    require(summary['GT_loader'] == loader and summary['source_GT'] == {k: source[k] for k in ('gt', 'gt_reference', 'gameinfo') if k in source}, '原GT选择/ID0加载器来源不同')
    by_unit = {v['unit_id']: v for v in summary['units']}
    require(len(summary['units']) == len(by_unit) == len(units) and set(by_unit) == {v['unit_id'] for v in units}
        and summary['unit_frames'] == sum(v['frames'] for v in units), '完整旧轨迹矩阵/含空unit-frame缺失')
    artifacts = summary['artifacts']; require(set(artifacts) == {'raw_ledger', 'frame_ledger', 'output_ledger', 'trajectory_ledger', 'GT_opportunity_ledger'}, '五原始账本必须齐全')
    for value in artifacts.values(): require(physical(value['path']).parent == summary_path.parent, '账本必须本源独立目录')
    output = {v['unit_id']: read_mot(v) for v in units}; seen = set(); totals = Counter(); buckets = Counter({k: 0 for k in BUCKETS})
    eligibility = Counter({k: 0 for k in ELIGIBILITY}); raw_states = Counter({k: 0 for k in RELATIONS})
    bucket_states = {k: Counter({r: 0 for r in RELATIONS}) for k in BUCKETS}; opportunity = Counter()
    unit_counts = {v['unit_id']: dict(output_rows=0, frames_with_any_output=0,
        output_to_raw=Counter({k: 0 for k in RELATIONS}), output_to_GT=Counter({k: 0 for k in RELATIONS}),
        raw_geometric_proxy_score_buckets=Counter({k: 0 for k in BUCKETS}), raw_geometric_proxy_score_unknown=0) for v in units}
    with ExitStack() as stack:
        raw_stream = stack.enter_context(closing(artifact_rows(artifacts['raw_ledger'], 'json')))
        gt_stream = stack.enter_context(closing(artifact_rows(artifacts['GT_opportunity_ledger'], 'json')))
        emitted = stack.enter_context(closing(artifact_rows(artifacts['output_ledger'], 'json')))
        frames = stack.enter_context(closing(artifact_rows(artifacts['frame_ledger'], 'csv')))
        raw_reader = FrameReader(raw_stream); gt_reader = FrameReader(gt_stream)
        for frame in range(1, source['frames']+1):
            raw = raw_reader.take(frame); gt = gt_reader.take(frame); atomic_raw(raw, sequence, frame, seen)
            opportunities = GT_opportunities(gt, raw, sequence, frame); opportunity.update(opportunities)
            frame_buckets = Counter({k: 0 for k in BUCKETS}); frame_eligibility = Counter({k: 0 for k in ELIGIBILITY})
            states = Counter()
            for value in raw:
                frame_buckets[value['bucket']] += 1; states[value['raw_to_GT']['state']] += 1
                bucket_states[value['bucket']][value['raw_to_GT']['state']] += 1
                for key in ELIGIBILITY: frame_eligibility[key] += int(value[key])
            expected_frame = dict(sequence=sequence, frame_number=frame, frame_index=frame-1, raw_detections=len(raw), GT_rows=len(gt),
                **frame_buckets, **frame_eligibility, raw_GT_mutual_unique=states[RELATIONS[0]], raw_GT_no_candidate=states[RELATIONS[1]],
                raw_GT_ambiguous=states[RELATIONS[2]]+states[RELATIONS[3]], **opportunities)
            actual_frame = next(frames, None); require(actual_frame is not None, 'frame账本缺少空帧'); check_csv_row(actual_frame, expected_frame)
            for unit in units:
                actual = []
                for _ in output[unit['unit_id']][frame]:
                    row = next(emitted, None); require(row is not None, '全部MOT输出账本缺行'); actual.append(row)
                counts = output_rows(actual, output[unit['unit_id']][frame], raw, gt, unit, frame)
                add_unit(unit_counts[unit['unit_id']], counts)
            totals.update(source_frames=1, raw_detections=len(raw), GT_rows=len(gt)); buckets.update(frame_buckets); eligibility.update(frame_eligibility); raw_states.update(states)
        require(raw_reader.next is None and gt_reader.next is None and next(frames, None) is None and next(emitted, None) is None, '源范围后仍有多余账本记录')
    require(dict(totals) == summary['source_counts'] and totals['source_frames'] == source['frames']
        and totals['raw_detections'] == source['counts']['raw_detections']
        and {v['GT_rows_from_completed_metric'] for v in units} == {totals['GT_rows']}, '源raw/GT全分母不同，不能重复或只保留成功行')
    require(summary['score_buckets'] == dict(buckets) and sum(buckets.values()) == totals['raw_detections']
        and summary['raw_eligibility'] == dict(eligibility) and summary['raw_to_GT_states'] == dict(raw_states)
        and summary['score_bucket_raw_to_GT'] == {k: dict(v) for k, v in bucket_states.items()}
        and summary['GT_opportunities'] == dict(opportunity), '七桶/资格/unknown/GT机会完整计数不同')
    expected_trajectories = []
    for unit in units:
        identifier = unit['unit_id']; target = by_unit[identifier]; counts = unit_counts[identifier]
        trajectories = trajectory_rows(unit, output[identifier]); expected_trajectories.extend(trajectories)
        counts.update(emitted_trajectory_count=len(trajectories), emission_gap_count=sum(v['emission_gap_count'] for v in trajectories),
            same_ID_reemission_after_gap_count=sum(v['same_ID_reemission_after_gap_count'] for v in trajectories))
        require(target['internal_lifecycle'] == UNKNOWN and target['source_frames'] == source['frames']
            and all(target[k] == unit[k] for k in ('unit_id', 'method', 'sequence', 'fold', 'seed', 'mot', 'tracking_receipt', 'metric_report'))
            and target['source_cache'] == source['cache'] and counts['output_rows'] == unit['tracked_rows'], '单位原来源/MOT全行/生命周期边界改变')
        for key, value in counts.items(): require(target[key] == value, '单位全部结局/unknown计数不同：'+key)
    with closing(artifact_rows(artifacts['trajectory_ledger'], 'csv')) as stream:
        for row in expected_trajectories:
            actual = next(stream, None); require(actual is not None, '发出轨迹分母缺失'); check_csv_row(actual, row)
        require(next(stream, None) is None, '发出轨迹账本多记录')
    counts = dict(raw_ledger=totals['raw_detections'], frame_ledger=source['frames'], GT_opportunity_ledger=totals['GT_rows'],
        output_ledger=sum(v['tracked_rows'] for v in units), trajectory_ledger=len(expected_trajectories))
    require(all(artifacts[k]['rows'] == v for k, v in counts.items()), '五账本实际行数声明不同')
    return dict(sequence=sequence, summary=ref(summary_path), source_counts=dict(totals), units=len(units), unit_frames=summary['unit_frames'],
        score_buckets=dict(buckets), raw_eligibility=dict(eligibility), GT_opportunities=dict(opportunity), artifacts=artifacts,
        all_original_MOT_rows_retained=True, all_geometry_unknowns_retained=True, raw_or_GT_coordinates_reloaded=False)


def validate_inventory(cfg, inventory):
    require(inventory['schema'] == 'tracking_policy_inventory_v1' and inventory['status'] == 'complete_readonly_inventory114_no_cache_or_GT_loaded'
        and cfg['sources'] == inventory['sources'] and cfg['units'] == inventory['units']
        and cfg['panels'] == inventory['panels'] and cfg['GT_loaders'] == inventory['GT_loaders'], '冻结原来源清单不同')
    units = cfg['units']; sources = cfg['sources']; panels = cfg['panels']
    require(set(panels) == set(PANELS) and [len(panels[k]) for k in PANELS] == [3, 2, 7]
        and set(s for p in PANELS for s in panels[p]) == set(sources) and len(sources) == 12
        and set(panels['original_heldout']) == set(OLD), '只能固定12源3/2/7面板')
    expected = {(method, seq, None, None) for method in METHODS[:2] for seq in sources}
    expected.update(('strong_motion_RS', seq, fold, seed) for seq in sources
        for fold in ((OLD[seq],) if seq in OLD else FOLDS) for seed in SEEDS)
    cells = [(v['method'], v['sequence'], v['fold'], v['seed']) for v in units]
    require(len(cells) == len(set(cells)) == 114 and set(cells) == expected and len({v['unit_id'] for v in units}) == 114
        and len({v['mot']['path'] for v in units}) == 114 and sum(v['frames'] for v in units) == 76315, '114MOT/76315 unit-frame矩阵缺失重复或被选样')
    require(all(v['frames'] == sources[v['sequence']]['frames'] and v['source_cache'] == sources[v['sequence']]['cache']
        and len(v['frame_counts']) == v['frames'] and sum(v['frame_counts']) == v['tracked_rows'] for v in units), '单位全部帧/原缓存与完整输出不同')
    GT_counts = [{v['GT_rows_from_completed_metric'] for v in units if v['sequence'] == seq} for seq in sources]
    require(all(len(v) == 1 for v in GT_counts), '同源全部旧评价GT口径必须一致')
    require(sum(v['frames'] for v in sources.values()) == 8165 and sum(v['counts']['raw_detections'] for v in sources.values()) == 149245
        and sum(next(iter(v)) for v in GT_counts) == 113020,
        '唯一源8165帧/149245raw/113020GT-frame分母不同')


def aggregate_rows(cfg, results):
    """独立重建四张全量CSV；只场内平均训练单元，再在3/2/7面板比赛等权。"""
    sources, units, matches = [], [], []
    for sequence in cfg['sequence_order']:
        summary = results[sequence]; panel = next(p for p in PANELS if sequence in cfg['panels'][p]); n = summary['source_counts']
        sources.append(dict(sequence=sequence, panel=panel, **n, **summary['score_buckets'], **summary['raw_eligibility'], **summary['GT_opportunities']))
        grouped = defaultdict(list)
        for unit in summary['units']:
            row = {k: unit[k] for k in ('unit_id', 'method', 'sequence', 'fold', 'seed', 'source_frames', 'output_rows',
                'frames_with_any_output', 'emitted_trajectory_count', 'emission_gap_count', 'same_ID_reemission_after_gap_count', 'raw_geometric_proxy_score_unknown')}
            row['panel'] = panel
            for field in ('output_to_raw', 'output_to_GT', 'raw_geometric_proxy_score_buckets'):
                row.update({field+'__'+k: v for k, v in unit[field].items()})
            row.update(mot_path=unit['mot']['path'], mot_sha256=unit['mot']['sha256'], internal_lifecycle=UNKNOWN)
            units.append(row); grouped[unit['method']].append(unit)
        for method in METHODS:
            group = grouped[method]; require(bool(group), '不能省略某方法的负结局')
            def avg(key): return sum(v[key] for v in group)/len(group)
            count = avg('output_rows'); gt = sum(v['output_to_GT']['mutual_unique'] for v in group)/len(group)
            raw = sum(v['output_to_raw']['mutual_unique'] for v in group)/len(group)
            matches.append(dict(sequence=sequence, panel=panel, method=method, training_units=len(group), source_frames=n['source_frames'], source_GT_rows=n['GT_rows'],
                mean_output_rows=count, mean_output_rows_per_source_frame=count/n['source_frames'], mean_frames_with_any_output=avg('frames_with_any_output'),
                mean_emitted_trajectories=avg('emitted_trajectory_count'), mean_emission_gap_count=avg('emission_gap_count'),
                mean_mutual_unique_output_GT_rows=gt, mean_mutual_unique_output_GT_rows_per_source_GT=gt/n['GT_rows'],
                mean_mutual_unique_output_raw_rows=raw, mean_raw_score_geometric_proxy_unknown=avg('raw_geometric_proxy_score_unknown'),
                internal_lifecycle=UNKNOWN, interpretation='posthoc_geometry_and_emissions_not_TrackEval'))
    panels = []
    for panel in cfg['panels']:
        for method in METHODS:
            group = [r for r in matches if r['panel'] == panel and r['method'] == method]
            require(len(group) == len(cfg['panels'][panel]), '完整面板比赛数不同')
            row = dict(panel=panel, method=method, matches=len(group), aggregation='equal_match_means_after_within_match_training_unit_mean')
            for key in ('mean_output_rows_per_source_frame', 'mean_mutual_unique_output_GT_rows_per_source_GT'):
                row[key] = sum(v[key] for v in group)/len(group)
            panels.append(row)
    return dict(source_summary=sources, all_units=units, method_sequence_summary=matches, panel_summary=panels)


@contextmanager
def no_original_GT_cache_or_media(cfg):
    forbidden = {os.path.normcase(os.path.abspath(v[k]['path'])) for v in cfg['sources'].values()
        for k in ('cache', 'gt', 'gt_reference', 'gameinfo', 'seqinfo', 'seqinfo_reference') if k in v}
    evidence = dict(active=True, blocked_open_attempts=0)
    def audit(event, args):
        if event != 'open' or not evidence['active'] or not args or not isinstance(args[0], (str, bytes, os.PathLike)): return
        path = os.fsdecode(args[0])
        if os.path.normcase(os.path.abspath(path)) in forbidden or Path(path).suffix.lower() in ('.jpg', '.jpeg', '.png', '.exr', '.mp4', '.avi'):
            evidence['blocked_open_attempts'] += 1; raise PermissionError('独立终验不能重读原GT坐标/预测缓存或媒体')
    sys.addaudithook(audit)
    try: yield evidence
    finally: evidence['active'] = False


def is_producer(command):
    return bool(re.search(r'(?:^|[\\/\s\"\x27])(?:tracking_policy_ledger_control|ocsort_cached_(?:control|admission)|'
        r'pose_velocity_(?:tracking_control|learning_train)|substitution_validation_predictions)[.]py(?=$|[\s\"\x27])', command or '', re.I))


def blocked_processes(records, state):
    start = datetime.fromisoformat(state['created_utc'].replace('Z', '+00:00')); result = []
    for row in records:
        command = row.get('CommandLine') or ''; spawned = False
        if 'spawn_main' in command and re.search(r'\bparent_pid\s*=\s*'+str(state['parent_pid'])+r'\b', command):
            created = row.get('CreationUtc'); require(created, '相关spawn缺真实创建时间，不能按旧PID猜退出')
            when = datetime.fromisoformat(created.replace('Z', '+00:00'))
            spawned = start-timedelta(seconds=2) <= when <= datetime.now(timezone.utc)+timedelta(seconds=2)
        if (row.get('Name') or '').lower().startswith('unrealeditor') or is_producer(command) or spawned: result.append(row)
    return result


def processes_absent(state):
    command = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine,@{n='CreationUtc';e={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    answer = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], check=True, capture_output=True,
        text=True, encoding='utf-8', errors='strict')
    rows = json.loads(answer.stdout) if answer.stdout.strip() else []
    if isinstance(rows, dict): rows = [rows]
    blocked = blocked_processes(rows, state); require(not blocked, '相关生产者/UE仍存在，保留不kill：'+canonical(blocked))
    return dict(actual_CIM_checked=True, producer_processes_absent=True, old_PID_reuse_not_rejected=True,
        spawn_parent_creation_window_checked=True)


def worker_closure(state, control):
    ready = state['workers']; exits = state['worker_exits']; completed = state['completed']
    require(len(ready) == len(exits) == 2 and len({v['worker_pid'] for v in ready}) == 2
        and {v['worker_pid'] for v in ready} == {v['worker_pid'] for v in exits}, '两个真实worker握手/退出缺失')
    require(all(v['status'] == 'ready' for v in ready), 'worker实际就绪未完整')
    counts = Counter(v['worker_pid'] for v in completed)
    require(set(counts) <= {v['worker_pid'] for v in ready} and sum(counts.values()) == 12, '12源任务实际worker归属不同')
    for value in exits:
        require(value['status'] == 'closed' and value['jobs'] == counts[value['worker_pid']]
            and value['GT_loaded_only_posthoc'] is True and value['model_tracker_TrackEval_modules_loaded'] == []
            and value['joined'] is True and value['process_exited'] is True and value['exit_code'] == 0, 'worker后验边界/关闭/join/exit0不完整')
    logs = [physical(control/'logs'/f'analysis_{i}.log') for i in range(2)]
    require(all(v.is_file() for v in logs), '实际两个worker日志缺失')
    return dict(workers=2, completed_sources=12, all_joined_exit0=True, forbidden_runtime_modules_loaded=False,
        closures=exits, logs=[ref(p) for p in logs])


def verify(config, control, output):
    config, control, output = physical(config), physical(control), physical(output); cfg = read(config)
    require(EXP in output.parents and control not in output.parents and output.parent != control and not output.parent.exists(), '必须独立新终验attempt，不覆盖partial')
    require(cfg['schema'] == 'tracking_policy_ledger_protocol_v1' and cfg['approved_by'] == 'root' and cfg['analysis_authorized'] is True
        and cfg['test_sealed'] is True and cfg['new_optimizer_updates'] == cfg['new_model_or_tracker_or_TrackEval_runs'] == 0
        and control == physical(cfg['output_root']), '零更新/后验/实际控制目录协议不同')
    state = read(control/'state.json'); output.parent.mkdir(parents=True)
    write_new(output.parent/'intent.json', dict(config=ref(config), state=ref(control/'state.json'),
        new_optimizer_updates=0, original_GT_or_cache_or_media_read=False, test_read=False))
    try:
        require(state['status'] == 'complete12_sources114_output_units_zero_update_policy_ledger_workers_exited'
            and state['protocol'] == ref(config) and not state['active'] and len(state['completed']) == 12
            and {v['sequence'] for v in state['completed']} == set(cfg['sources'])
            and state['new_optimizer_updates'] == state['new_model_or_tracker_or_TrackEval_runs'] == 0 and state['test_read'] is False,
            '12源/114输出完整终态未齐，不能将started/存活当完成')
        initial_exit = processes_absent(state)
        with no_original_GT_cache_or_media(cfg) as guard:
            inventory = read(checked(cfg['inventory'])); validate_inventory(cfg, inventory)
            require(cfg['counts'] == inventory['counts'] and cfg['static_policy'] == inventory['static_policy']
                and cfg['expected_unique_GT_rows'] == 113020
                and cfg['sequence_order'] == [s for p in PANELS for s in cfg['panels'][p]], '事前源/静态政策/分母清单改变')
            policy = cfg['policy']
            require(policy['score_buckets'] == list(BUCKETS) and policy['IoU_threshold'] == .5
                and policy['float32_threshold_semantics'] is True and policy['internal_lifecycle'] == UNKNOWN
                and policy['GT_geometry_is_posthoc_only'] is True, '七桶/IoU/未知状态口径不同')
            require(policy['threshold_search'] is False and policy['potential_next_single_factor']['authorized_by_this_config'] is False,
                '不能把后验账本授权成新阈值执行或搜索')
            require(cfg['worker_profile'] == dict(analysis_workers=2, numeric_threads=1, reserve_RAM_bytes=8589934592,
                reserve_commit_bytes=6442450944, startup_estimate_bytes=268435456), '只能已冻结两个有界后验worker')
            for value in cfg['GT_loaders'].values(): checked(value['module'])
            bundle = physical(cfg['bundle']); require(bundle.parent == R/'code', '只允许最小冻结代码来源')
            files = read(checked(cfg['bundle_manifest']))['files']
            for item in files: require(sha(bundle/item['path']) == item['sha256'], '冻结源码改变')
            core_entries = [v for v in files if v['path'] == 'tools/research_ops/tracking_policy_ledger_core.py']
            require(len(core_entries) == 1, '实际core源码未冻结')
            core_ref = dict(path=str(bundle/core_entries[0]['path']), sha256=core_entries[0]['sha256'])
            contract = read(checked(cfg['numeric_contract'])); require(contract['status'] == 'complete_policy_inventory_core_controller_CPU_contracts', '针对CPU合同未通过')
            summaries = {}; checks = []
            for item in state['completed']:
                path = checked(item['summary']); sequence = item['sequence']
                require(item['status'] == 'complete' and path == control/'sequences'/sequence/'summary.json', '实际源输出路径/完成项不同')
                body = read(path); require(body['implementation'] == core_ref, '账本不是本协议冻结core产生')
                checks.append(verify_sequence(cfg, sequence, path)); summaries[sequence] = body
            require(sum(v['source_counts']['source_frames'] for v in checks) == 8165
                and sum(v['source_counts']['raw_detections'] for v in checks) == 149245
                and sum(v['source_counts']['GT_rows'] for v in checks) == 113020
                and sum(v['unit_frames'] for v in checks) == 76315 and sum(v['units'] for v in checks) == 114, '源/单位分母被复制或缺失')
            workers = worker_closure(state, control)
            require(state['actual_exit_gate']['actual_CIM_checked'] is True and state['actual_exit_gate']['related_producers_absent'] is True,
                '原控制器实际worker退出门禁缺失')
            report_path = checked(state['report']); require(report_path == control/'report.json', '根报告路径不同')
            report = read(report_path); expected_counts = dict(sources=12, source_frames=8165, raw_detections=149245,
                source_GT_rows=113020, units=114, unit_frames=76315, method_matches=36)
            require(report['schema'] == 'tracking_policy_ledger_report_v1' and report['status'] == 'complete12_sources114_units36_method_matches_policy_ledger'
                and report['inventory'] == cfg['inventory'] and report['counts'] == expected_counts
                and report['sequence_summaries'] == [ref(control/'sequences'/s/'summary.json') for s in cfg['sequence_order']]
                and report['static_policy'] == cfg['static_policy'] and report['GT_only_posthoc'] is True
                and report['all_negative_and_ambiguous_results_preserved'] is True and report['internal_lifecycle'] == UNKNOWN
                and report['hypothetical_threshold_policy_executed'] is False and report['formal_equivalence_or_noninferiority'] is False
                and report['new_optimizer_updates'] == report['new_model_or_tracker_or_TrackEval_runs'] == report['new_images_or_predictions'] == 0
                and report['test_read'] is False, '根汇总的完整范围/代理含义/零更新边界不同')
            expected_tables = aggregate_rows(cfg, summaries); require(set(report['artifacts']) == set(expected_tables), '四份全量CSV缺失')
            for key, expected in expected_tables.items():
                artifact = report['artifacts'][key]; require(artifact['rows'] == len(expected)
                    and physical(artifact['path']) == control/(key+'.csv'), '全量汇总CSV行数/路径不同')
                with closing(artifact_rows(artifact, 'csv')) as stream:
                    for row in expected:
                        value = next(stream, None); require(value is not None, '汇总缺行，不能删unknown/负结局'); check_csv_row(value, row)
                    require(next(stream, None) is None, '汇总额外复制原源或训练单元')
            require(report['panel_summary'] == expected_tables['panel_summary'], '面板必须先场内均值再比赛等权')
            require(guard['blocked_open_attempts'] == 0, '终验尝试重读原坐标/缓存/媒体')
        final_exit = processes_absent(state)
        receipt = dict(schema='tracking_policy_ledger_independent_verification_v1', status=STATUS, protocol=ref(config),
            implementation=ref(__file__),
            state=ref(control/'state.json'), report=state['report'], counts=expected_counts, sequence_checks=checks,
            source_frames_once=8165, output_unit_frames_including_empty=76315, unique_raw_detections=149245,
            unique_GT_opportunity_rows=113020, original_MOT_units=114, method_match_summaries=36, panel_summaries=9,
            workers=workers, initial_exit=initial_exit, final_exit=final_exit, producer_processes_absent=True,
            all_original_MOT_rows_retained=True, all_unknown_and_ambiguous_results_preserved=True,
            GT_coordinates_or_media_or_original_cache_read=False, raw_cache_or_GT_rehashed=False,
            geometric_candidates_recomputed_from_coordinates=False, geometric_candidate_graphs_and_all_ledgers_cross_checked=True,
            internal_lifecycle=UNKNOWN, raw_score_geometric_proxy_is_internal_binding=False,
            model_or_tracker_or_TrackEval_loaded=False, new_optimizer_updates=0, hypothetical_policy_executed=False,
            formal_equivalence_or_noninferiority=False, test_read=False)
        write_new(output, receipt); return receipt
    except BaseException as error:
        write_new(output.parent/'failed.json', dict(status='failed_policy_ledger_verification_partial_preserved_no_replay',
            error=repr(error), traceback=traceback.format_exc(), source_records_modified=False,
            new_optimizer_updates=0, model_or_tracker_or_TrackEval_loaded=False, test_read=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); result = verify(args.config, args.control, args.output)
    print(canonical(dict(status=result['status'], counts=result['counts'], new_optimizer_updates=0)))
