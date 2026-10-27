"""从既有OC十二场完成链解析114份轨迹的只读清单；不加载GT/模型/缓存。"""
import argparse
import ast
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import stat

R = Path('D:/projects/FutsalMOT_Research')
ULTRA_SOURCE = Path('D:/projects/FutsalMOT/.venv/Lib/site-packages/ultralytics/trackers/byte_tracker.py')
ULTRA_SHA = '05545b07876311937097fdd61a47cfba7dc09fd3695fd35603eb61be09c0b40d'
TRACKER_SHA = '7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688'
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
PANEL_NAMES = ('original_heldout', 'old_external', 'seven_observed')
METHODS = ('official_ocsort', 'PT_bbox', 'strong_motion_RS')
FIXED_ARGS = dict(track_high_thresh=.25, track_low_thresh=.1, new_track_thresh=.25,
                  track_buffer=30, match_thresh=.8, fuse_score=True)
OC_ARGS = dict(det_thresh=.6, max_age=30, min_hits=3, iou_threshold=.3, delta_t=3,
               asso_func='iou', inertia=.2, use_byte=False)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def safe(value, *, dependency=False):
    path = Path(value)
    require(path.is_absolute(), '来源必须绝对物理路径')
    path = Path(os.path.abspath(path))
    require((dependency and path == ULTRA_SOURCE) or R in path.parents, '仅允许研究来源或明确ByteTracker源码')
    require(not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
                    for p in path.parts), '最终测试继续封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '清单不跟随junction或符号链接')
    return path


def sha(path, *, dependency=False):
    digest = hashlib.sha256()
    with safe(path, dependency=dependency).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def ref(path, *, dependency=False):
    return dict(path=str(path), sha256=sha(path, dependency=dependency))


def checked(reference):
    path = safe(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '冻结元数据/MOT来源改变：' + str(path))
    return path


def read_ref(reference):
    return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def rows_ref(reference):
    with checked(reference).open('r', encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def assert_unread_ref(reference):
    """媒体/预测缓存/GT只核引用形状与物理路径，不打开、更不重哈。"""
    require(set(reference) >= {'path', 'sha256'} and re.fullmatch('[0-9a-f]{64}', reference['sha256']), '来源引用缺SHA')
    safe(reference['path'])


def panel_lookup(panels):
    require(set(panels) == set(PANEL_NAMES) and [len(panels[k]) for k in PANEL_NAMES] == [3, 2, 7], '只能保留3/2/7三个面板')
    lookup = {sequence: name for name in PANEL_NAMES for sequence in panels[name]}
    require(len(lookup) == 12 and set(panels['original_heldout']) == set(OLD), '十二来源缺失/跨面板重复')
    return lookup


def expected_cells(sources):
    result = set()
    for sequence in sources:
        result.update((method, sequence, None, None) for method in METHODS[:2])
        folds = (OLD[sequence],) if sequence in OLD else FOLDS
        result.update(('strong_motion_RS', sequence, fold, seed) for fold in folds for seed in SEEDS)
    return result


def validate_units(units, sources):
    observed = [(u['method'], u['sequence'], u['fold'], u['seed']) for u in units]
    require(len(observed) == len(set(observed)) == 114 and set(observed) == expected_cells(sources),
            '114轨迹矩阵缺项/重复/替换fold或seed')
    require(Counter(u['method'] for u in units) == Counter(official_ocsort=12, PT_bbox=12, strong_motion_RS=90),
            '只能12OC/12PT/90强motion，不混入T或其他模型')
    require(len({u['unit_id'] for u in units}) == 114 and len({u['mot']['path'] for u in units}) == 114,
            '逻辑单元或实际MOT重复，不能复用文件充数')
    require(sum(u['frames'] for u in units) == 76315, '实际unit-frame应为76315，不能当8165独立图像')


def bundle_source(config, relative):
    manifest = read_ref(config['bundle_manifest'])
    entries = [entry for entry in manifest['files'] if entry['path'] == relative]
    require(len(entries) == 1, '源码必须来自实际冻结bundle清单：' + relative)
    path = safe(Path(config['bundle'])/relative)
    reference = dict(path=str(path), sha256=entries[0]['sha256'])
    checked(reference)
    return reference


def function_evidence(reference, function):
    path = checked(reference)
    text = path.read_text(encoding='utf-8-sig')
    tree = ast.parse(text)
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function]
    require(len(selected) == 1, 'GT纯函数入口缺失/重复')
    node = selected[0]
    return dict(module=deepcopy(reference), function=function, lines=[node.lineno, node.end_lineno],
        function_AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        signature=[arg.arg for arg in node.args.args], invocation='direct_load_gt_only_never_validate_or_training_loader',
        GT_loaded_by_inventory=False)


def source_lines(reference, needles, *, dependency=False):
    path = safe(reference['path'], dependency=dependency)
    require(sha(path, dependency=dependency) == reference['sha256'], '政策源码快照改变')
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    result = {}
    for key, needle in needles.items():
        matches = [dict(line=index+1, source=text.strip()) for index, text in enumerate(lines) if needle in text]
        require(matches, '固定政策源码条件缺失：' + key)
        result[key] = matches
    return result


def static_policy(config, old, seven):
    train = read_ref(old['training_protocol'])
    v9 = read_ref(train['v9_protocol'])
    tracker = bundle_source(v9, 'python/src/grf_ue_bridge/learned_association_tracker_v8.py')
    require(tracker['sha256'] == TRACKER_SHA, '原learned tracker字节身份不同')
    text = checked(tracker).read_text(encoding='utf-8-sig')
    assignment = next(node for node in ast.parse(text).body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'FIXED_ARGS' for target in node.targets))
    require(isinstance(assignment.value, ast.Call) and isinstance(assignment.value.func, ast.Name)
            and assignment.value.func.id == 'dict', '原FIXED_ARGS结构改变')
    values = {keyword.arg: ast.literal_eval(keyword.value) for keyword in assignment.value.keywords}
    require(values == FIXED_ARGS and config['parameters'] == OC_ARGS, '只能描述原.25/.1与OC.6固定政策')
    official = read_ref(config['official_manifest'])
    entries = [e for e in official['files'] if e['path'] == 'trackers/ocsort_tracker/ocsort.py']
    require(len(entries) == 1, '官方固定原码清单缺失')
    oc = dict(path=str(Path(official['source_root'])/entries[0]['path']), sha256=entries[0]['sha256'])
    checked(oc)
    upstream = ref(ULTRA_SOURCE, dependency=True)
    require(upstream['sha256'] == ULTRA_SHA, '当前ByteTracker依赖源码改变，需独立说明而非默许')
    return dict(
        learned_tracker=dict(source=tracker, FIXED_ARGS=values, frozen_source=True,
            evidence=source_lines(tracker, dict(fixed_args='FIXED_ARGS=dict(', base_init='super().__init__(SimpleNamespace(**FIXED_ARGS))',
                no_output_filter='return result', low_stage='unchanged_upstream_bbox_only'))),
        ultralytics_ByteTracker=dict(source=upstream, provenance='current_installed_source_snapshot',
            historical_file_SHA_binding_established=False,
            evidence=source_lines(upstream, dict(high='scores >= self.args.track_high_thresh', low='scores > self.args.track_low_thresh',
                low_upper='scores < self.args.track_high_thresh', init='track.score < self.args.new_track_thresh',
                buffer='self.max_frames_lost = args.track_buffer', removal='self.frame_id - track.end_frame > self.max_frames_lost',
                first_frame_confirmation='if frame_id == 1:', confirmation='unconfirmed[itracked].update(',
                output='[x.result for x in self.tracked_stracks if x.is_activated]', low_match='thresh=0.5'), dependency=True)),
        official_ocsort=dict(source=oc, parameters=deepcopy(config['parameters']), frozen_source=True,
            evidence=source_lines(oc, dict(high='remain_inds = scores > self.det_thresh', low='inds_low = scores > 0.1',
                use_byte='if self.use_byte and', confirmation='trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits',
                output='if (trk.time_since_update < 1)', removal='trk.time_since_update > self.max_age'))),
        inference_limitations=['MOT只记录可观测emission episode，不记录内部出生、匹配、确认、lost或删除原因。',
            '当前依赖源码是本次只读快照；未找到历史逐文件ByteTracker SHA绑定，不能补造历史冻结证据。',
            '共享raw缓存不等于同有效检测保留/确认/输出政策，静态差异本身不证明结果因果。'])


def tracking_from_metric(metric_ref, metric, method, sequence, config, old, seven):
    require(metric['status'] == 'complete' and metric['DO_PREPROC'] is False
            and metric['predictions_GT_filtered'] is False and metric['test_read'] is False,
            '必须已完成评价且保留全预测、测试未读')
    metric_path = checked(metric_ref)
    if method == 'official_ocsort':
        require(metric['schema'] == 'official_ocsort_cached12_evaluation_v1'
                and metric['sequence'] == sequence and metric['source_cache'] == config['sources'][sequence]['cache'],
                'OC实际来源/schema不同')
        receipt_ref = metric['tracking_receipt']
        location_basis = 'metric_explicit_tracking_receipt_ref'
    else:
        expected_schema = 'seven_match_ABC_trackeval_gap_v1' if sequence in config['panels']['seven_observed'] else 'v10_independent_trackeval_gap_v1'
        require(metric['schema'] == expected_schema and metric['job']['sequence'] == sequence,
                '旧5/七场metric schema不符，不能宽松fallback')
        require(metric['protocol_sha256'] == (config['_seven_protocol_sha'] if sequence in config['panels']['seven_observed']
                else config['_old_protocol_sha']), '原评价协议身份不同')
        # 原schema只存SHA：按已冻结原写入源码的相对布局解析，不重新推导或猜job ID。
        receipt_ref = dict(path=str(metric_path.parent.parent/'tracking/receipt.json'), sha256=metric['tracking_receipt_sha256'])
        location_basis = 'frozen_metric_layout_sibling_tracking_receipt_SHA_bound_no_job_ID_guess'
    receipt = read_ref(receipt_ref)
    expected = 'official_ocsort_cached12_tracking_v1' if method == 'official_ocsort' else (
        'seven_match_ABC_free_tracking_v1' if sequence in config['panels']['seven_observed'] else 'v10_independent_free_tracking_v1')
    require(receipt['schema'] == expected and receipt['status'] == 'complete'
            and receipt['test_read'] is False and receipt['frames'] == config['sources'][sequence]['frames'], '原轨迹未完整或scope不符')
    require(receipt['source_cache' if method == 'official_ocsort' else 'cache'] == config['sources'][sequence]['cache'],
            '114轨迹必须使用原十二同缓存')
    job = receipt.get('job', {})
    if method == 'official_ocsort':
        require(receipt['sequence'] == sequence and receipt['GT_used_for_tracking'] is False, 'OC追踪GT边界不同')
        mot = receipt['mot']
        require(mot['sha256'] == receipt['mot_sha256'], 'OC显式MOT与原摘要不同')
    else:
        require(job == metric['job'] and job['sequence'] == sequence, '实际metric/receipt job不同')
        if method == 'PT_bbox':
            require(job['kind'] == 'PT' and job['mode'] == 'PT_bbox', 'PT不能换成static Pose或learned')
        elif sequence in config['panels']['seven_observed']:
            require(job['kind'] == 'learned' and job['group'] == 'B' and job['method'] == 'motion', '七场强motion须原B')
        else:
            require(method == 'strong_motion_RS' and job['kind'] == 'new_RS' and job['method'] == 'motion'
                    and job['pool'] == 'balanced', '旧五强motion须原balancedRS')
        require(receipt.get('GT_read', receipt.get('GT_used_for_tracking')) is False, '原追踪GT隔离缺失')
        mot = dict(path=str(Path(receipt_ref['path']).parent/'data'/(sequence+'.txt')), sha256=receipt['mot_sha256'])
    checked(mot)
    counts = receipt['frame_counts']
    require(len(counts) == receipt['frames'] and all(type(x) is int and x >= 0 for x in counts)
            and sum(counts) == receipt['tracked_rows'], '原全帧输出数/行数不一致')
    require(metric['frames'] == receipt['frames'] and metric['raw_results'][sequence]['pedestrian']['Count']['Dets'] == receipt['tracked_rows'],
            '已有TrackEval预测计数与MOT收据不同')
    return receipt_ref, mot, receipt, location_basis


def build_inventory(oc_complete_ref):
    complete = read_ref(oc_complete_ref)
    require(complete['status'] == 'complete_official_OCSORT_cached12_admission_tracking_metrics_intervals_and_exit_verified'
            and complete['actual_formal_clips'] == 12 and complete['actual_formal_frames'] == 8165
            and complete['producer_processes_absent'] is True and complete['test_read'] is False,
            '必须从实际十二场完整闭合链取得来源')
    config = read_ref(complete['protocol']); analysis = read_ref(complete['analysis'])
    require(config['schema'] == 'official_ocsort_cached12_protocol_v1' and config['test_sealed'] is True
            and analysis['status'] == 'complete12_official_ocsort_cached_paired_analysis'
            and analysis['protocol'] == complete['protocol'] and analysis['all_negative_results_preserved'] is True,
            '实际协议/完整CSV/负结果来源不同')
    sources, panels = config['sources'], config['panels']; lookup = panel_lookup(panels)
    require(set(sources) == set(lookup) and sum(s['frames'] for s in sources.values()) == 8165, '原来源帧数/十二scope不同')
    for source in sources.values():
        assert_unread_ref(source['cache'])
    vcfg = read_ref(config['source_velocity_protocol'])
    old = read_ref(vcfg['source_tracking_config']); seven = read_ref(vcfg['source_seven_tracking_config'])
    require(sources == dict(old['sources'], **seven['sources']) == vcfg['sources'], '缓存源元数据不是原已验五加七')
    config = dict(config, _old_protocol_sha=vcfg['source_tracking_config']['sha256'],
                  _seven_protocol_sha=vcfg['source_seven_tracking_config']['sha256'])
    old_loader = bundle_source(old, 'tools/research_ops/v10_tracking_runtime.py')
    new_loader = bundle_source(seven, 'tools/research_ops/substitution_tracking_runtime.py')
    old_layout = [bundle_source(old, p) for p in ('tools/research_ops/v10_track.py', 'tools/research_ops/v10_metric.py')]
    new_layout = bundle_source(seven, 'tools/research_ops/substitution_tracking_jobs.py')
    units = []
    selected = []
    oc_rows = rows_ref(analysis['all_OC_results']); reference_rows = rows_ref(analysis['all_reference_cells'])
    require(len(oc_rows) == 12 and len(reference_rows) == 192 and Counter(row['baseline'] for row in reference_rows)
            == Counter(PT_bbox=12, strong_motion_RS=90, T_RS=90), '原已验表必须完整，不筛有利单元')
    for row in oc_rows:
        selected.append(('official_ocsort', row))
    selected.extend((row['baseline'], row) for row in reference_rows if row['baseline'] in ('PT_bbox', 'strong_motion_RS'))
    for method, row in selected:
        sequence = row['sequence']; require(sequence in lookup, '表含未登记比赛')
        metric_ref = dict(path=row['report_path'], sha256=row['report_sha256'])
        metric = read_ref(metric_ref)
        receipt_ref, mot, receipt, location = tracking_from_metric(metric_ref, metric, method, sequence, config, old, seven)
        fold = row['fold'] if method == 'strong_motion_RS' else None
        seed = int(row['seed']) if method == 'strong_motion_RS' else None
        if method == 'strong_motion_RS':
            require((receipt['job']['fold'], receipt['job']['seed']) == (fold, seed), 'CSV与实际fold/seed不同')
        key = [method, sequence, fold, seed, mot['sha256']]
        units.append(dict(unit_id=hashlib.sha256(canonical(key).encode()).hexdigest()[:24], method=method,
            sequence=sequence, panel=lookup[sequence], fold=fold, seed=seed, tracking_receipt=receipt_ref,
            mot=mot, metric_report=metric_ref, frames=receipt['frames'], tracked_rows=receipt['tracked_rows'],
            frame_counts=receipt['frame_counts'], source_cache=deepcopy(sources[sequence]['cache']),
            GT_rows_from_completed_metric=metric['GT_rows'], location_basis=location,
            observable='MOT_emission_episodes_only_not_internal_birth_confirmation_lost_or_removal'))
    validate_units(units, sources)
    loaders = dict(old_five=function_evidence(old_loader, 'load_gt'), seven=function_evidence(new_loader, 'load_gt'))
    require(loaders['old_five']['signature'] == loaders['seven']['signature'] == ['source'], '只准直接原load_gt(source)')
    raw_counts = {sequence: source['counts']['raw_detections'] for sequence, source in sources.items()}
    require(all(type(value) is int and value >= 0 for value in raw_counts.values()), '来源摘要raw计数非法')
    return dict(schema='tracking_policy_inventory_v1', status='complete_readonly_inventory114_no_cache_or_GT_loaded',
        oc_complete=deepcopy(oc_complete_ref), oc_protocol=complete['protocol'], oc_analysis=complete['analysis'],
        sources=deepcopy(sources), panels=deepcopy(panels), units=units, GT_loaders=loaders,
        source_velocity_protocol=deepcopy(config['source_velocity_protocol']),
        original_layout_sources=dict(old_five=old_layout, seven=new_layout), static_policy=static_policy(config, old, seven),
        source_tables=dict(OC=analysis['all_OC_results'], references=analysis['all_reference_cells']),
        counts=dict(sources=12, unique_source_frames=8165, units=114, unit_frames=sum(u['frames'] for u in units),
            methods=dict(Counter(u['method'] for u in units)), raw_detections_from_frozen_summary=sum(raw_counts.values()),
            per_sequence_raw_from_frozen_summary=raw_counts),
        cache_read=False, cache_rehashed=False, media_read=False, GT_loaded=False, model_loaded=False,
        new_tracking_runs=0, new_TrackEval_runs=0, new_optimizer_updates=0, test_read=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oc-complete', required=True)
    parser.add_argument('--oc-complete-sha256', required=True)
    args = parser.parse_args()
    result = build_inventory(dict(path=args.oc_complete, sha256=args.oc_complete_sha256))
    print(canonical(dict(schema=result['schema'], status=result['status'], counts=result['counts'])))
