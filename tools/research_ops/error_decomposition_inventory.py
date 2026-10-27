"""平衡池原五场27份trace的只读错误分解清单；新七场63份内部trace缺失。"""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat

R = Path('D:/projects/FutsalMOT_Research')
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
EXTERNAL = ('v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
FIRST_SEED = 20261024
FIXED_SHA = dict(
    policy_inventory='889a5a96e10dbbb9401481a19366c01395a158f3293ee47eef154ea38bc976b1',
    information_report='c2af5f70c469fc53ff5dc34a2788536f79d4ae33f22320a0ec0d038f215cbc69',
    decision_report='d9a2d1624de56b489da4d5e236f05462efaa93b604f121739af6b8f91170de52',
    ledger_complete='17c24b98b310471e78ed0a0242e857a94588ab79c8f84d1715bd731dbd67d89d')
TRACE_FIELDS = ('frame_number', 'stage', 'track_ids', 'history_UIDs', 'candidate_UIDs', 'bbox_cost',
    'reference_cost', 'motion_gate', 'enabled', 'active_rows', 'enough_history', 'lost_gap',
    'scored_locations', 'logits', 'quality', 'quality_gates', 'chosen_raw_UID', 'GT_read')


def require(ok, text):
    if not ok:
        raise ValueError(text)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def safe(value):
    path = Path(value)
    require(path.is_absolute(), '所有来源必须绝对物理路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
            for part in path.parts), '只读研究来源，最终测试封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '清单不跟随junction或符号链接')
    return path


def assert_data_ref(reference):
    """数据只核已签引用与存在，不重哈缓存、GT、trace、MOT或压缩逐行账本。"""
    require(isinstance(reference, dict) and set(reference) >= {'path', 'sha256'}
            and re.fullmatch('[0-9a-f]{64}', reference['sha256']), '数据引用缺路径/SHA')
    path = safe(reference['path'])
    require(path.is_file(), '已签数据来源缺失：' + str(path))
    return path


def read_metadata(reference):
    path = assert_data_ref(reference)
    require(path.suffix == '.json' and path.name not in ('posthoc_GT_labels.json', 'gap_registry.json'),
            '只允许读取小JSON收据，不得打开标签/endpoint或缓存')
    content = path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == reference['sha256'], '元数据来源改变：' + str(path))
    return json.loads(content.decode('utf-8-sig'))


def first_gzip_record(reference):
    path = assert_data_ref(reference)
    require(path.name in ('common_state_trace.jsonl.gz', 'events.jsonl.gz'), '只准必要trace/schema首记录')
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        line = stream.readline()
    require(bool(line.strip()), '原非空stage trace/诊断事件为空')
    return json.loads(line)


def trace_header(reference):
    value = first_gzip_record(reference)
    require(set(TRACE_FIELDS) <= set(value) and value['GT_read'] is False and value['stage'] in (0, 1),
            '原共同trace字段/schema不同')
    rows, columns = len(value['track_ids']), len(value['candidate_UIDs'])
    require(rows > 0 and columns > 0 and len(value['reference_cost']) == rows
            and all(len(row) == columns for row in value['reference_cost'])
            and len(value['history_UIDs']) == len(value['chosen_raw_UID']) == rows,
            '原首记录必须是非空矩阵，不能当全视频事件')
    return dict(fields=list(TRACE_FIELDS), checked_records=1, complete_trace_rehashed=False,
        first_frame_number=value['frame_number'], first_stage=value['stage'],
        stage_denominator='only_original_recorded_nonempty_get_dists_stage0_or1',
        actual_cost='reference_cost', shadow_logits='logits_not_actual_enabled_batch_exact_scores',
        chosen_raw_UID='frame_end_activated_output_UID_not_explicit_stage_assignment')


def strong_key(unit):
    return unit['sequence'], unit['fold'], unit['seed']


def expected_old_cells():
    return {(sequence, fold, seed) for fold in FOLDS for seed in SEEDS
            for sequence in (next(s for s, f in OLD.items() if f == fold), *EXTERNAL)}


def validate_coverage(strong, traces, missing):
    require(len(strong) == 90 and len({strong_key(u) for u in strong}) == 90, '原强motion90单元缺失/重复')
    require(len(traces) == 27 and {strong_key(u) for u in traces} == expected_old_cells()
            and len({u['unit_id'] for u in traces}) == 27, '必须平衡池旧五场全部27trace，不能混hard或挑seed')
    require(len(missing) == 63 and len({strong_key(u) for u in missing}) == 63
            and not ({strong_key(u) for u in traces} & {strong_key(u) for u in missing})
            and {strong_key(u) for u in traces+missing} == {strong_key(u) for u in strong}, '63个缺trace不能补造或省略')
    require(sum(u['expected_stage_rows'] for u in traces) == 320752
            and sum(u['expected_stage_calls'] for u in traces) == 24863, '原27完整条件行/事件分母不同')
    require(sum(u['stage_assignment_reference'] is not None for u in traces) == 9, '只允许原首seed九份分配对照')


def ledgers_from_complete(ledger_ref, policy_ref):
    complete = read_metadata(ledger_ref)
    require(complete['status'] == 'complete12_existing_sources114_MOT_policy_ledger_independent_verification_and_exit'
            and complete['inventory'] == policy_ref and complete['producer_processes_absent'] is True
            and complete['test_read'] is False, '必须已闭合政策账本及同一114源清单')
    report = read_metadata(complete['analysis'])
    require(report['status'] == 'complete12_sources114_units36_method_matches_policy_ledger'
            and report['inventory'] == policy_ref and len(report['sequence_summaries']) == 12, '完整十二源政策产物不齐')
    result = {}
    for summary_ref in report['sequence_summaries']:
        summary = read_metadata(summary_ref); sequence = summary['sequence']
        require(sequence not in result and summary['status'] == 'complete_sequence_raw_output_posthoc_policy_ledger'
                and summary['source_denominator_copies'] == summary['cache_stream_passes'] == 1
                and summary['GT_used_for_tracking'] is False, '来源分母重复或GT边界改变')
        values = {key: deepcopy(summary['artifacts'][key]) for key in ('raw_ledger', 'GT_opportunity_ledger', 'frame_ledger')}
        for reference in values.values():
            assert_data_ref(reference)
        result[sequence] = dict(**values, sequence_summary=deepcopy(summary_ref),
            source_cache=deepcopy(summary['source_cache']), source_counts=deepcopy(summary['source_counts']),
            source_denominator_copies=1, GT_geometry_is_posthoc=True)
    return result, complete['analysis']


def decision_references(report, trace_details):
    """从新T已存事件中只引用原reference.assignment；不加载/重评分新T。"""
    require(report['status'] == 'complete18_new_T_fixed_state_decision_probe_zero_updates_not_free_tracking'
            and report['source_trace_units'] == 9 and report['scoring_units'] == 18
            and report['new_optimizer_updates'] == 0 and report['new_free_tracking'] is False,
            '已完成首seed18诊断来源不符')
    rows = {}; seen = set()
    for summary_ref in report['units']:
        summary = read_metadata(summary_ref); job = summary['job']
        require(summary['status'] == 'complete_new_T_fixed_state_probe_unit_not_free_tracking'
                and job['pool'] == 'balanced' and job['seed'] == FIRST_SEED
                and job['group'] in ('T_RS', 'T_shuffle_RS') and summary['new_optimizer_updates'] == 0
                and summary['new_free_tracking'] is False, '原18单元不完整或范围改变')
        pair = job['source_job_id'], job['group']
        require(pair not in seen and job['source_job_id'] in trace_details, '首seed诊断重复/不是当前27原trace')
        seen.add(pair)
        detail = trace_details[job['source_job_id']]
        require(summary['trace'] == detail['trace'] and summary['source_receipt'] == detail['receipt'], '分配对照必须同一原共同trace')
        if job['group'] != 'T_RS':
            continue
        # 该事件同时含后验标签；清单只绑定已验ref，不为核字段而解析这些标签。
        # 独立数值准入再流式读取九份事件中的reference.assignment与重建结果逐项核对。
        assert_data_ref(summary['events'])
        require(summary['diagnostic_event_limit'] is None
                and summary['counts']['stage_events'] == detail['counts']['stage_calls']
                and summary['counts']['stage_rows'] == detail['counts']['all_stage_rows'], '原九份分配对照必须全事件/全row，不是prefix')
        rows[job['source_job_id']] = dict(events=deepcopy(summary['events']), summary=deepcopy(summary_ref),
            record_path='new_T.reference.assignment', source_event_index='source_event_number',
            actual_cost_path='new_T.reference.recorded_actual_old_motion_cost',
            origin='original_trace_recorded_actual_reference_cost_not_new_T_tracking',
            expected_events=summary['counts']['stage_events'], checked_header_records=0,
            record_path_is_numeric_gate_obligation=True,
            new_T_scores_reused=False, reconstructed_assignment_not_frame_end_UID=True)
    expected = {key for key, detail in trace_details.items() if detail['job']['original']['seed'] == FIRST_SEED}
    require(len(rows) == 9 and set(rows) == expected and len(seen) == 18, '原首seed9源/两组18摘要缺失')
    return rows


def build_inventory(policy_inventory_ref, information_report_ref, decision_report_ref, ledger_complete_ref):
    bindings = dict(policy_inventory=policy_inventory_ref, information_report=information_report_ref,
                    decision_report=decision_report_ref, ledger_complete=ledger_complete_ref)
    require(all(bindings[key]['sha256'] == value for key, value in FIXED_SHA.items()), '只准明确已验来源，不重选诊断')
    policy, information, decision = [read_metadata(reference) for reference in
        (policy_inventory_ref, information_report_ref, decision_report_ref)]
    require(policy['status'] == 'complete_readonly_inventory114_no_cache_or_GT_loaded'
            and len(policy['sources']) == 12 and len(policy['units']) == 114, '原政策清单未完整')
    require(information['status'] == 'complete54_information_chain_zero_updates_not_new_tracking_or_training'
            and information['source_units'] == 54 and information['stage_rows'] == 641785
            and information['new_optimizer_updates'] == 0 and information['new_free_tracking'] is False,
            '原信息链54完整范围改变')
    source_ledgers, ledger_report = ledgers_from_complete(ledger_complete_ref, policy_inventory_ref)
    require(set(source_ledgers) == set(policy['sources']), '政策来源不再是十二源')
    info_protocol = read_metadata(information['config'])
    mechanism = read_metadata(info_protocol['mechanism_protocol'])
    inputs = read_metadata(mechanism['inputs'])
    require(inputs['status'] == 'complete_raw_inputs_labels_and_shape_swaps_no_inference', '只引用原标签来源，不加载原标签')
    strong = [deepcopy(u) for u in policy['units'] if u['method'] == 'strong_motion_RS']
    require(len(strong) == 90, '原强motion90不可增删')
    by_cell = {strong_key(u): u for u in strong}; audits = {}; historical = {}
    audit_keys = {'accepted_probability_pairs', 'active_learned_rows', 'easy_bbox_rows', 'learned_pairs',
                  'low_score_stage', 'rejected_probability_pairs'}
    for unit in strong:
        receipt = read_metadata(unit['tracking_receipt'])
        require(receipt['status'] == 'complete' and receipt['job']['method'] == 'motion'
                and strong_key(dict(receipt['job'])) == strong_key(unit)
                and receipt.get('trace') is None and set(receipt['audit']) == audit_keys, '历史90应为原聚合audit，不补造内部trace')
        historical[strong_key(unit)] = receipt
        audits[unit['unit_id']] = deepcopy(receipt['audit'])
    details = [d for d in information['details'] if d['job']['original']['pool'] == 'balanced']
    require(len(details) == 27 and len({d['job']['job_id'] for d in details}) == 27, '只选预定balanced27完整范围')
    by_job = {detail['job']['job_id']: detail for detail in details}
    assignments = decision_references(decision, by_job)
    units = []
    for detail in details:
        job = detail['job']; motion = job['reference_motion']; key = strong_key(motion)
        require(key in by_cell and motion['pool'] == 'balanced' and motion['method'] == 'motion', 'trace必须对应原balanced强motion')
        original = by_cell[key]; old_receipt = historical[key]; receipt = read_metadata(detail['receipt'])
        require(receipt['status'] == 'complete' and receipt['job'] == job and receipt['trace'] == detail['trace']
                and receipt['GT_read'] is False and motion == old_receipt['job']
                and receipt['mot_sha256'] == old_receipt['mot_sha256'] and receipt['audit'] == old_receipt['audit'],
                '必须原job、已记MOT SHA及audit精确相同，不读MOT补造一致')
        sequence, fold, seed = key
        require(source_ledgers[sequence]['source_cache'] == original['source_cache'], 'trace与已完成政策账本不同缓存')
        labels = deepcopy(inputs['sources'][sequence]['labels']); assert_data_ref(labels)
        units.append(dict(unit_id=job['job_id'], job=deepcopy(job), sequence=sequence, fold=fold, seed=seed, pool='balanced',
            trace=deepcopy(detail['trace']), receipt=deepcopy(detail['receipt']), original_unit_id=original['unit_id'],
            original_tracking_receipt=deepcopy(original['tracking_receipt']), original_metric_report=deepcopy(original['metric_report']),
            original_mot=deepcopy(original['mot']), recorded_MOT_SHA_equal=True, audit_exact=True,
            source_cache=deepcopy(original['source_cache']), labels=labels, source_ledgers=deepcopy(source_ledgers[sequence]),
            expected_stage_rows=detail['counts']['all_stage_rows'], expected_stage_calls=detail['counts']['stage_calls'],
            stage_assignment_reference=deepcopy(assignments.get(job['job_id'])), trace_header=trace_header(detail['trace']),
            internal_lifecycle='unknown_not_reconstructed_from_MOT', source_GT_used_only_posthoc=True))
    covered = {strong_key(u) for u in units}
    missing = [dict(deepcopy(unit), reason='no_historical_candidate_history_or_assignment_trace',
        internal_candidate_or_score_or_lifecycle='unknown', audit_aggregate=deepcopy(audits[unit['unit_id']]),
        output_posthoc_source=deepcopy(source_ledgers[unit['sequence']])) for unit in strong if strong_key(unit) not in covered]
    validate_coverage(strong, units, missing)
    require(all(u['sequence'] in policy['panels']['seven_observed'] for u in missing), '缺失63应只来自新七场')
    assert_data_ref(information['all_stage_rows'])
    return dict(schema='bounded_error_decomposition_inventory_v1',
        status='complete_metadata_inventory27_existing_trace63_missing_no_cache_GT_model_or_tracking',
        sources=deepcopy(policy['sources']), panels=deepcopy(policy['panels']), strong_units=strong, units=units,
        missing_trace_units=missing, source_ledgers=source_ledgers, historical_audits=audits,
        previous_diagnostics=dict(information_report=deepcopy(information_report_ref),
            all_stage_rows=deepcopy(information['all_stage_rows']), all_stage_rows_scope='54_pools;filter_exact27_job_ids_no_rerun',
            decision_report=deepcopy(decision_report_ref), assignment_references=assignments,
            information_protocol=information['config'], mechanism_protocol=info_protocol['mechanism_protocol'],
            mechanism_complete=info_protocol['mechanism_complete'], inputs=mechanism['inputs']),
        source_references=deepcopy(bindings), ledger_report=ledger_report,
        counts=dict(sources=12, strong_motion_units=90, trace_units=27, missing_trace_units=63,
            existing_trace_stage_calls=24863, existing_trace_stage_rows=320752, assignment_reference_units=9),
        internal_states_from_MOT=False, all_video_events_denominator=False,
        cache_read=False, GT_annotations_loaded=False, model_loaded=False, media_read=False,
        trace_full_hash_recomputed=False, new_tracking_runs=0, new_scoring_runs=0, new_TrackEval_runs=0,
        new_optimizer_updates=0, test_read=False,
        limitations=['原27只含非空get_dists高分/未确认stage；低分stage、空矩阵和完整生命周期缺失。',
            '原reference_cost可重建阶段分配；chosen_raw_UID是帧末输出，不可冒充阶段分配。',
            'logits是全gate影子批，不能替代原enabled批精确分数；实际参考成本优先。',
            '新七场63内部trace缺失；只复用既有输出后验，不推断出生/确认/lost/删除。',
            'source_ledgers每源只计一次；重复引用到训练单元不增加独立GT/raw源分母。'])
