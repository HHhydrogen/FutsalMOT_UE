"""已验3000个R窗口与既有决策机会账本交叉核查；不筛窗、不评分或训练。"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from statistics import mean

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/teacher_anchor_bank_a01'
FOLDS = ('game4', 'game6', 'game9')
SOURCE_FOLDS = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
ZERO_KEYS = ('new_optimizer_updates', 'new_model_forwards', 'new_tracking', 'new_solver_calls', 'new_TrackEval')
STATUS = 'complete3000_selected_R_windows_teacher_anchor_opportunity_join_no_new_experiment'
FLAG_KEYS = ('local_opportunity', 'local_opportunity_pose_supported_both', 'local_opportunity_pose_supported_actual_noncorrect',
             'local_opportunity_pose_supported_actual_known_wrong', 'local_opportunity_pose_supported_actual_unmatched',
             'local_opportunity_pose_supported_actual_unknown')


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value): return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def safe(value):
    p = Path(value); require(p.is_absolute(), '必须绝对物理路径'); p = Path(os.path.abspath(p))
    require(R in p.parents and not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower()) for part in p.parts), '研究范围或封存测试边界不同')
    for q in (p, *p.parents):
        if q.exists() or q.is_symlink():
            info = q.lstat(); require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, '禁止链接/junction')
    return p


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): h.update(block)
    return h.hexdigest()


def ref(path): return dict(path=str(safe(path)), sha256=sha(path))


def checked(reference, kind='metadata'):
    require(isinstance(reference, dict) and set(reference) >= {'path', 'sha256'} and re.fullmatch('[0-9a-f]{64}', reference['sha256']), '缺SHA引用')
    p = safe(reference['path'])
    require((kind == 'metadata' and p.suffix == '.json') or (kind == 'pool' and p.name == 'real_pool.jsonl')
        or (kind == 'ledger' and p.name == 'rows.jsonl.gz'), '仅小JSON、已验R池及新机会ledger；不打开旧frames/GT/cache/权重')
    require(p.name not in ('gap_registry.json', 'posthoc_GT_labels.json') and sha(p) == reference['sha256'], '来源SHA改变')
    return p


def read(reference): return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def bool_or_null(value):
    require(value is None or type(value) is bool, '状态必须bool/null'); return value


def validate(config_path):
    reference = ref(config_path); cfg = read(reference)
    require(cfg['schema'] == 'teacher_anchor_bank_audit_protocol_v1' and cfg['approved_by'] == 'root'
        and cfg['test_sealed'] is True and cfg['source_folds'] == SOURCE_FOLDS and all(type(cfg[k]) is int and cfg[k] == 0 for k in ZERO_KEYS), '冻结零执行协议/原三源映射不同')
    inputs, verification, report = read(cfg['input_root']), read(cfg['opportunity_verification']), read(cfg['opportunity_report'])
    require(inputs['schema'] == 'state_aligned_R_bank_inputs_v1'
        and inputs['status'] == 'complete3_fold1000_unique_original_prediction_R_banks_not_training_authorized'
        and inputs['all_windows_roundtrip_exact'] is True and inputs['optimizer_updates'] == 0
        and inputs['images_GT_weights_read'] is False and inputs['new_prediction_or_tracking_or_training'] is False and inputs['test_read'] is False,
        '仅继承原已验三fold池，不重建或训练')
    require(verification['status'] == 'complete12_decision_opportunity_sources_rows_counts_intervals_and_exit_verified'
        and verification['producer_processes_absent'] is True and verification['test_read'] is False
        and all(verification[k] == 0 for k in ZERO_KEYS), '机会核查须已独立终验及实际退出')
    require(verification['analysis']['sha256'] == cfg['opportunity_report']['sha256']
        and checked(verification['analysis']) == checked(cfg['opportunity_report']), '终验不是该完整分析报告')
    require(report['schema'] == 'decision_opportunity_analysis_v1'
        and report['status'] == 'complete12_existing_log_decision_opportunity_counts_and_source_intervals'
        and report['rows'] == 180118 and report['absolute_frames'] == 9000 and report['unique_source_frames'] == 2250
        and all(report[k] == 0 for k in ZERO_KEYS) and report['test_read'] is False, '完整机会账本范围/零执行边界不同')
    require(set(inputs['folds']) == set(FOLDS) and len(report['units']) == 12, '三池/十二unit缺失')
    units = [read(value) for value in report['units']]
    expected = {(fold, regime, sequence, 20261024) for sequence, heldout in SOURCE_FOLDS.items() for fold in FOLDS if fold != heldout for regime in ('R', 'RS')}
    require(len({u['job']['job_id'] for u in units}) == 12 and {tuple(u['job'][k] for k in ('fold', 'regime', 'sequence', 'seed')) for u in units} == expected, '十二原unit矩阵缺失/重复')
    for unit in units:
        require(unit['schema'] == 'decision_opportunity_unit_v1' and unit['status'] == 'complete' and unit['frames'] == 750
            and unit['row_count'] == unit['ledger']['rows'] and all(unit[k] == 0 for k in ZERO_KEYS) and unit['test_read'] is False, '仅完整零执行机会unit')
    require(sum(u['row_count'] for u in units) == 180118, '原机会账本全行分母不同')
    teachers = {u['job']['job_id']: u for u in units if u['job']['regime'] == 'R'}
    require(len(teachers) == 6, '只准六个首seed R teacher')
    return reference, cfg, inputs, teachers


def coordinate(metadata):
    return (metadata['source_job_id'], metadata['candidate_frame_number'], metadata['source_stage'], metadata['source_row_index'], metadata['source_track_id'])


def pool_rows(inputs, teachers):
    """仅保留原metadata及UID/标签顺序，不保留或计算Pose坐标特征。"""
    result = []; unique = set(); keys = set()
    for fold in FOLDS:
        bound = inputs['folds'][fold]; selected = []; totals = Counter(); sources = Counter()
        with checked(bound['pool'], 'pool').open(encoding='utf-8-sig') as stream:
            for line in stream:
                window = json.loads(line); m = window['aligned_bank_metadata']; key = coordinate(m)
                require(m['schema'] == 'free_state_aligned_R_bank_candidate_v1' and m['fold'] == fold
                    and m['teacher_regime'] == 'R' and m['teacher_seed'] == 20261024 and m['source_stage'] == 'high_score'
                    and m['GT_coordinates_in_features'] is False and m['candidate_scope'] == 'whole_original_high_score_stage_not_exact_enabled_subset', '原bank身份或候选范围不同')
                teacher = teachers[m['source_job_id']]['job']
                require(teacher['fold'] == fold and teacher['sequence'] == m['sequence'] and teacher['model_id'] == m['teacher_model_id']
                    and SOURCE_FOLDS[m['sequence']] != fold, '窗口来源不是该fold允许的R teacher')
                require(window['window_uid'] == m['window_uid'] and window['sequence'] == m['sequence']
                    and window['candidate_frame_number'] == m['candidate_frame_number']
                    and [h['uid'] for h in window['history']] == m['history_UIDs']
                    and [c['prediction']['uid'] for c in window['candidates']] == m['candidate_UIDs']
                    and [c['label'] for c in window['candidates']] == m['pair_labels'], '原pool与metadata逐条UID/标签不一致')
                labels = m['pair_labels']; require(len(labels) == len(m['candidate_UIDs']) and all(x is None or type(x) is int and x in (0, 1) for x in labels), '原pair标签无效')
                require(len(m['history_UIDs']) == 3 and m['query_GT_id'] is not None and any(x is not None for x in labels)
                    and m['no_positive_window'] == (1 not in labels), '必须原可靠三历史已知监督窗口；不能补造标签')
                require(m['window_uid'] not in unique and key not in keys, '窗口UID/原坐标重复')
                unique.add(m['window_uid']); keys.add(key); selected.append(m['window_uid']); sources[m['sequence']] += 1
                totals.update(dict(windows=1, all_pairs=len(labels), known_pairs=sum(x is not None for x in labels),
                    unknown_pairs=labels.count(None), positive_pairs=labels.count(1), negative_pairs=labels.count(0), no_positive_windows=int(1 not in labels)))
                result.append(dict(m))
        require(len(selected) == 1000 and digest(selected) == bound['selected_order_sha256'] and dict(totals) == bound['selected_counts'], '原1000唯一窗顺序/全pair预算不同')
        expected_sources = {s for s, heldout in SOURCE_FOLDS.items() if heldout != fold}
        require(set(sources) == expected_sources and set(bound['source_counts']) == expected_sources
            and all(sources[s] == bound['source_counts'][s]['selected_unique'] == 500 for s in sources), '每fold两允许源各500，不复制填额')
    require(len(result) == len(unique) == len(keys) == 3000, '全3000窗口必须唯一')
    return result


def join_window(metadata, ledger):
    require(ledger['job']['job_id'] == metadata['source_job_id'] and ledger['job']['regime'] == 'R'
        and ledger['job']['fold'] == metadata['fold'] and ledger['job']['sequence'] == metadata['sequence']
        and ledger['job']['seed'] == 20261024 and ledger['job']['model_id'] == metadata['teacher_model_id'], '机会行不是原R teacher')
    require((ledger['frame_number'], ledger['stage'], ledger['row_index'], ledger['track_id']) == coordinate(metadata)[1:]
        and ledger['history_UIDs'] == metadata['history_UIDs'] and ledger['query_GT_id'] == metadata['query_GT_id']
        and [p['uid'] for p in ledger['pose_candidates']] == metadata['candidate_UIDs']
        and [p['label'] for p in ledger['pose_candidates']] == metadata['pair_labels'], '窗口与机会行坐标/历史/query/逐candidate标签不同')
    require(ledger['new_solver_calls'] == 0 and ledger['Pose_support_is_accuracy'] is False and ledger['local_cost_comparison_is_causal'] is False, '仅继承描述性机会行')
    anchor = ledger['earliest_stage_trusted3_anchor']; query = ledger['query_GT_id']
    drift = None if anchor is None or query is None else str(query) != str(anchor['gt_id'])
    require(bool_or_null(ledger['flags']['earliest_stage_trusted3_anchor_drift']) == drift, '原anchor漂移旗标与身份不符')
    if anchor is not None: require(type(anchor['frame_number']) is int and anchor['frame_number'] <= ledger['frame_number'], '不能用未来anchor回填')
    flags = {k: bool_or_null(ledger['flags'][k]) for k in FLAG_KEYS}; labels = metadata['pair_labels']; counts = ledger['absolute_counts']
    require(counts['candidates'] == len(labels) and counts['positive'] == labels.count(1) and counts['known_negative'] == labels.count(0)
        and counts['unknown'] == labels.count(None), '原机会pair分母不同')
    return dict(window_uid=metadata['window_uid'], fold=metadata['fold'], sequence=metadata['sequence'], source_job_id=metadata['source_job_id'],
        candidate_frame_number=metadata['candidate_frame_number'], source_stage=metadata['source_stage'], source_row_index=metadata['source_row_index'],
        source_track_id=metadata['source_track_id'], teacher_model_id=metadata['teacher_model_id'], history_UIDs=metadata['history_UIDs'],
        candidate_UIDs=metadata['candidate_UIDs'], pair_labels=labels, query_GT_id=query, earliest_stage_trusted3_anchor=anchor,
        anchor_drift=drift, no_positive=1 not in labels, all_pairs=len(labels), known_pairs=sum(x is not None for x in labels),
        positive_pairs=labels.count(1), known_negative_pairs=labels.count(0), unknown_pairs=labels.count(None),
        first_stop=ledger['first_stop'], **flags, labels_changed=False, drift_is_true_identity_error=False, new_model_forwards=0)


def join_ledgers(metadata, teachers):
    selected = {coordinate(m): m for m in metadata}; found = {}; scanned = {}
    for jid, teacher in teachers.items():
        count = 0; matched = set(); seen = set()
        with gzip.open(checked(teacher['ledger'], 'ledger'), 'rt', encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line); count += 1
                require(row['job'] == teacher['job'], 'ledger混入其他teacher')
                key = (jid, row['frame_number'], row['stage'], row['row_index'], row['track_id'])
                require(key not in seen, 'ledger坐标重复'); seen.add(key)
                if key in selected:
                    require(key not in found, '选中窗口重复join'); found[key] = join_window(selected[key], row); matched.add(key)
        require(count == teacher['row_count'] == teacher['ledger']['rows'], '完整R teacher ledger行数不同')
        expected = {k for k in selected if k[0] == jid}; require(matched == expected and len(matched) == 500, '该R teacher必须精确匹配500原窗口')
        scanned[jid] = dict(rows=count, matched_windows=len(matched), ledger=teacher['ledger'])
    require(set(found) == set(selected) and len(found) == 3000, '未完整join3000选中窗')
    return [found[coordinate(m)] for m in metadata], scanned


def summarize_rows(rows):
    require(bool(rows), '描述组不能为空')
    result = dict(windows=len(rows), **{k: sum(r[k] for r in rows) for k in ('all_pairs', 'known_pairs', 'positive_pairs', 'known_negative_pairs', 'unknown_pairs')},
        no_positive_windows=sum(r['no_positive'] for r in rows), anchor_drift={v: sum(('null' if r['anchor_drift'] is None else str(r['anchor_drift']).lower()) == v for r in rows) for v in ('true', 'false', 'null')},
        first_stop=dict(Counter(r['first_stop'] for r in rows)))
    result['flag_counts'] = {k: {v: sum(('null' if r[k] is None else str(r[k]).lower()) == v for r in rows) for v in ('true', 'false', 'null')} for k in FLAG_KEYS}
    return result


def descriptions(rows):
    per_fold = {f: summarize_rows([r for r in rows if r['fold'] == f]) for f in FOLDS}
    per_cell = {f: {s: summarize_rows([r for r in rows if r['fold'] == f and r['sequence'] == s]) for s, heldout in SOURCE_FOLDS.items() if heldout != f} for f in FOLDS}
    per_source = {s: summarize_rows([r for r in rows if r['sequence'] == s]) for s in SOURCE_FOLDS}
    rates = {}
    for name in ('anchor_drift', 'no_positive', *FLAG_KEYS):
        values = {}
        for sequence, heldout in SOURCE_FOLDS.items():
            fold_rates = []
            for fold in FOLDS:
                if fold == heldout: continue
                group = [r for r in rows if r['fold'] == fold and r['sequence'] == sequence]
                known = [r[name] for r in group if r[name] is not None]
                fold_rates.append(None if not known else 100*sum(known)/len(known))
            values[sequence] = None if any(v is None for v in fold_rates) else mean(fold_rates)
        rates[name] = dict(source_rates_pp=values, three_source_equal_mean_rate_pp=None if any(v is None for v in values.values()) else mean(values.values()),
            source_training_folds_are_not_independent_matches=True, interval_not_estimated=True)
    return dict(all=summarize_rows(rows), per_fold=per_fold, per_fold_source=per_cell, per_source=per_source, source_equal_descriptions=rates)


def audit(config_path, output):
    protocol, cfg, inputs, teachers = validate(config_path)
    output = safe(output); require(EXP in output.parents and not output.exists(), '新独立输出不得覆盖partial/成功')
    metadata = pool_rows(inputs, teachers); rows, scanned = join_ledgers(metadata, teachers)
    summary = descriptions(rows); output.mkdir(parents=True)
    with (output/'windows.jsonl').open('x', encoding='utf-8') as stream:
        for row in rows: stream.write(canonical(row)+'\n')
    fields = ['window_uid', 'fold', 'sequence', 'source_job_id', 'candidate_frame_number', 'source_stage', 'source_row_index', 'source_track_id',
        'teacher_model_id', 'history_UIDs', 'candidate_UIDs', 'pair_labels', 'query_GT_id', 'earliest_stage_trusted3_anchor', 'anchor_drift', 'no_positive',
        'all_pairs', 'known_pairs', 'positive_pairs', 'known_negative_pairs', 'unknown_pairs', 'first_stop', *FLAG_KEYS]
    with (output/'windows.csv').open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in rows: writer.writerow({k: canonical(row[k]) if isinstance(row[k], (dict, list)) else ('null' if row[k] is None else row[k]) for k in fields})
    report = dict(schema='teacher_anchor_selected_R_bank_audit_v1', status=STATUS, protocol=protocol,
        input_root=cfg['input_root'], opportunity_verification=cfg['opportunity_verification'], opportunity_report=cfg['opportunity_report'],
        selected_windows=3000, R_teacher_units=6, RS_ledgers_opened=0, original_frames_opened=0, GT_cache_weights_or_media_opened=False,
        scanned_teacher_ledgers=scanned, descriptions=summary, windows_jsonl=ref(output/'windows.jsonl'), windows_csv=ref(output/'windows.csv'),
        **{k: 0 for k in ZERO_KEYS}, test_read=False, pool_rebuilt=False, labels_changed=False, window_selection_changed=False,
        limitations=['只交叉描述既有3000选中R窗口与原六个teacher轨迹，不是新训练或独立追踪成绩。',
            'anchor为首次stage可信三历史的几何身份代理；漂移不等于完整身份真值错误或错误标签证明。',
            '候选是原whole-high-stage，非仅enabled子集；no-positive并不自动表示无效监督。',
            'Pose只为已有几何支持旗标，不是准确率、可见性或可纠正收益。',
            '三源均已见训练域，先同源两fold再三源等权；未产生AssA或性能置信区间，不按结果筛窗重训。'])
    with (output/'report.json').open('x', encoding='utf-8') as stream: stream.write(canonical(report)+'\n')
    return dict(status=STATUS, selected_windows=3000, R_teacher_units=6, **{k: 0 for k in ZERO_KEYS})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config', required=True); parser.add_argument('--output', required=True); parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    result = audit(args.config, args.output) if args.execute else dict(status='readonly_teacher_anchor_bank_metadata_preflight', protocol=validate(args.config)[0])
    print(canonical(result))
