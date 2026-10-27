"""导出已验27臂原始论文CSV；不加载Torch、模型、图像或任何追踪评价。"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import traceback

RESEARCH = Path('D:/projects/FutsalMOT_Research')
EXPERIMENT = RESEARCH/'pose/pose_velocity_learning_a01'
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
GROUPS = ('T_R', 'T_RS', 'T_shuffle_RS')
BUDGET_STATUS = 'complete27_bounded_velocity_actual_budget_full_records_and_exit_verified'
STATUS = 'complete27_bounded_velocity_raw_training_records_export'
ROW_FIELDS = ('actual_update', 'update_index', 'loss', 'real_loss', 'synthetic_loss', 'learning_rates',
    'grad_l2', 'gradients_clipped', 'step_wall_seconds', 'R_windows', 'S_windows',
    'R_pairs', 'S_pairs', 'R_known_pairs', 'S_known_pairs', 'real', 'synthetic', 'chain_sha256')
CSV_FIELDS = ('fold', 'seed', 'group', *ROW_FIELDS, 'initialization_sha256', 'method_state_sha256',
    'protocol_sha256', 'run_directory', 'source_steps_path', 'source_steps_sha256',
    'source_run_receipt_sha256', 'source_training_complete_sha256', 'raw_step_json')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def physical(path):
    path = Path(os.path.abspath(path))
    require(RESEARCH in path.parents, '论文记录来源/输出必须在实际DResearch目录')
    require(not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
                    for part in path.parts), '最终测试继续封存')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            value = part.lstat()
            require(not stat.S_ISLNK(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400,
                    '论文导出拒绝junction/重解析点')
    return path


def read(path):
    return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def sha(path):
    value = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def ref(path):
    return dict(path=str(path), sha256=sha(path))


def checked(value):
    path = physical(value['path'])
    require(path.is_file() and sha(path) == value['sha256'], '原记录来源SHA改变：'+str(path))
    return path


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def matrix():
    return [dict(fold=f, seed=s, group=g) for f in FOLDS for s in SEEDS for g in GROUPS]


def preflight(config, control, budget, output, budget_sha256=None, failed_audits=()):
    require(all(Path(p).is_absolute() for p in (config, control, budget, output)), '四个路径必须为绝对路径')
    config, control, budget, output = map(physical, (config, control, budget, output))
    require(EXPERIMENT in control.parents and EXPERIMENT in output.parents
            and control not in output.parents and config.parent not in output.parents
            and budget.parent not in output.parents, '输出不能进入原训练/协议/审计目录')
    require(not output.exists(), '论文导出目录已存在或partial，不覆盖/重放')
    if budget_sha256 is not None:
        require(sha(budget) == budget_sha256, '调用绑定的独立预算SHA不同')
    cfg, audit = read(config), read(budget)
    state_path = control/'driver_state.json'; state = read(state_path)
    require(cfg['schema'] == 'bounded_velocity_recorded_training_protocol_v1'
            and cfg['test116187_sealed'] is True and cfg['training_matrix'] == matrix()
            and cfg['parameters']['updates'] == 1000 and cfg['parameters']['R_per_step'] == 3
            and cfg['parameters']['S_per_RS_step'] == 1, '独立27臂学习协议/预算不符')
    require(audit['status'] == BUDGET_STATUS and audit['protocol'] == ref(config)
            and audit['control_state'] == ref(state_path)
            and audit['actual_totals']['updates'] == 27000 and audit['actual_totals']['R_windows'] == 81000
            and audit['actual_totals']['S_windows'] == 18000 and audit['complete_checkpoints_read_back'] == 567
            and audit['training_processes_absent'] is True and audit['optimizer_replay'] == 0,
            '实际27000更新/81000R/18000S及567完整检查点预算未闭合')
    require(state['status'] == 'complete27_bounded_velocity_training_wait_independent_audit_tracking'
            and state['active'] is None and state['protocol_sha256'] == sha(config)
            and [{k: item[k] for k in ('fold', 'seed', 'group')} for item in state['completed_train']] == matrix()
            and [{k: item[k] for k in ('fold', 'seed', 'group')} for item in audit['runs']] == matrix(),
            '实际27臂完成矩阵不齐，不筛seed/group')
    bundle = physical(cfg['bundle']); require(bundle.parent == RESEARCH/'code', '必须引用原实际冻结执行bundle')
    manifest = read(checked(cfg['bundle_manifest']))
    for item in manifest['files']:
        require(sha(bundle/item['path']) == item['sha256'], '原执行源码改变')
    failures = []
    for path in failed_audits:
        path = physical(path); evidence = read(path)
        require(evidence['status'] == 'failed_audit_preserved_sources_unchanged', '失败说明必须来自原审计失败记录')
        failures.append(dict(source=ref(path), status=evidence['status'], error=evidence['error']))
    flight = dict(status='readonly27_bounded_velocity_paper_records_preflight',
        protocol=ref(config), actual_budget=ref(budget), control_state=ref(state_path),
        planned_raw_step_rows=27000, training_runs=27, original_checkpoints_preserved=567,
        new_optimizer_updates=0, model_loaded=False, tracking_metrics_read=False,
        test_read=False, failed_audit_sources=failures)
    return cfg, audit, state, flight


def validate_steps(rows, table, group):
    require(group in GROUPS and len(rows) == 1000 and len(table['real']) == 3000
            and len(table['synthetic']) == 1000, '原1000步或固定R/S曝光表不足')
    chain = '0'*64; totals = Counter()
    for i, row in enumerate(rows):
        value = dict(row); saved = value.pop('chain_sha256')
        chain = hashlib.sha256((chain+canonical(value)).encode()).hexdigest()
        real = table['real'][3*i:3*i+3]
        synthetic = [] if group == 'T_R' else table['synthetic'][i:i+1]
        require(saved == chain and type(row['actual_update']) is int and row['actual_update'] == i+1
                and row['update_index'] == i and row['real'] == real and row['synthetic'] == synthetic,
                '实际步序、完整UID/epoch或连续曝光链不符')
        counts = dict(R_windows=3, S_windows=len(synthetic),
            R_pairs=sum(x['candidate_pairs'] for x in real), S_pairs=sum(x['candidate_pairs'] for x in synthetic),
            R_known_pairs=sum(x['labelled_pairs'] for x in real), S_known_pairs=sum(x['labelled_pairs'] for x in synthetic))
        require(all(type(row[k]) is int and row[k] == v for k, v in counts.items()), '全部/已知pair计数与真实来源不同')
        require(all(type(row[k]) in (float, int) and math.isfinite(row[k]) and row[k] >= 0
                    for k in ('loss', 'real_loss', 'grad_l2', 'step_wall_seconds'))
                and row['learning_rates'] == [.001] and row['gradients_clipped'] is False,
                '逐步原始loss/LR/梯度/耗时缺失或非有限')
        if synthetic:
            require(type(row['synthetic_loss']) in (float, int) and math.isfinite(row['synthetic_loss'])
                    and row['synthetic_loss'] >= 0
                    and abs(row['loss']-row['real_loss']-row['synthetic_loss']/3) <= 1e-6*(1+row['loss']),
                    '分域loss或固定S权重不一致')
        else:
            require(row['synthetic_loss'] is None and row['loss'] == row['real_loss'], '纯R隐藏额外S loss')
        totals.update(counts)
    return dict(totals), chain


def step_csv_row(row, job, source):
    out = {k: row[k] for k in ROW_FIELDS}
    out.update(job); out.update(source)
    for key in ('learning_rates', 'real', 'synthetic'):
        out[key] = canonical(out[key])
    if row['synthetic_loss'] is None:
        out['synthetic_loss'] = 'null'
    out['raw_step_json'] = canonical(row)
    return out


def export(config, control, budget, output, budget_sha256=None, failed_audits=()):
    cfg, audit, state, flight = preflight(config, control, budget, output, budget_sha256, failed_audits)
    config, control, budget, output = map(Path, (config, control, budget, output))
    output.mkdir(parents=True)
    write_new(output/'preflight.json', flight)
    write_new(output/'started.json', dict(status='started_raw_record_export_not_training',
        generated_utc=datetime.now(timezone.utc).isoformat(), source_actual_budget=ref(budget), new_updates=0))
    try:
        source = read(checked(cfg['source_training_protocol']))
        totals = Counter(); sources = []; run_rows = []; row_count = 0
        with (output/'steps.csv').open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS); writer.writeheader()
            for item, verified in zip(state['completed_train'], audit['runs']):
                job = {k: item[k] for k in ('fold', 'seed', 'group')}
                run = physical(item['path'])
                require(run == control/'runs'/job['fold']/str(job['seed'])/job['group']/'training', '实际run路径不等于登记矩阵')
                require(sha(run/'run_receipt.json') == item['receipt_sha256'] == verified['run_receipt_sha256']
                        and sha(run/'training_complete.json') == item['complete_sha256'], '已验run收据改变')
                receipt, complete = read(run/'run_receipt.json'), read(run/'training_complete.json')
                binding = receipt['binding']; manifest = read(run/'run_manifest.json')
                require(receipt['schema'] == 'bounded_velocity_full_recorded_training_run_v1'
                        and receipt['status'] == 'complete' and receipt['completed_updates'] == 1000
                        and binding['protocol_sha256'] == sha(config) and manifest['binding'] == binding
                        and {k: binding[k] for k in ('fold', 'seed', 'group')} == job
                        and receipt['full_training_record'] == sha(run/'training_complete.json')
                        and complete['schema'] == 'full_training_process_complete_v1' and complete['actual_updates'] == 1000
                        and sha(run/'run_manifest.json') == complete['manifest_sha256']
                        and sha(run/'events.jsonl') == complete['events_sha256'], '完整训练来源/模型绑定不一致')
                logs = run/'steps.jsonl'; require(sha(logs) == complete['steps_sha256'], '原逐步日志SHA变化')
                with logs.open(encoding='utf-8-sig') as source_stream:
                    rows = [json.loads(line) for line in source_stream if line.strip()]
                table = read(checked(source['exposures']['balanced'][job['fold']][str(job['seed'])]))
                counts, chain = validate_steps(rows, table, job['group'])
                last = read(run/'last_checkpoint.json'); transaction = read(run/'update_transaction.json')
                require(counts == complete['totals'] == verified['counts']
                        and complete['exposure_chain'] == last['exposure_chain'] == chain
                        and transaction == dict(status='committed', completed_updates=1000, chain_sha256=chain)
                        and verified['actual_updates'] == 1000 and verified['checkpoints_read_back'] == 21
                        and len(complete['checkpoints']) == 21
                        and [c['completed_updates'] for c in complete['checkpoints']] == list(range(0, 1001, 50))
                        and verified['last_checkpoint'] == last == complete['checkpoints'][-1], '实际预算、末事务或完整检查点索引不同')
                require(receipt['real_window_exposures'] == counts['R_windows'] == 3000
                        and receipt['synthetic_window_exposures'] == counts['S_windows'] == 1000*int(job['group'] != 'T_R'),
                        '不能把原计划数冒充实际曝光')
                origin = dict(initialization_sha256=binding['initialization_sha256'],
                    method_state_sha256=binding['method_state_sha256'], protocol_sha256=sha(config), run_directory=str(run),
                    source_steps_path=str(logs), source_steps_sha256=complete['steps_sha256'],
                    source_run_receipt_sha256=item['receipt_sha256'], source_training_complete_sha256=item['complete_sha256'])
                for row in rows:
                    writer.writerow(step_csv_row(row, job, origin)); row_count += 1
                totals.update(counts); totals['updates'] += len(rows)
                closure = verified['intervention']
                require(closure['source_cache_closed_flag'] is receipt['intervention']['closed'],
                        '审计不能重写原cache.closed事实')
                tag = '{fold}_{seed}_{group}'.format(**job)
                sources.append(dict(job=job, steps=ref(logs), events=ref(run/'events.jsonl'),
                    run_manifest=ref(run/'run_manifest.json'), run_receipt=ref(run/'run_receipt.json'),
                    training_complete=ref(run/'training_complete.json'), last_checkpoint_manifest=ref(run/'last_checkpoint.json'),
                    update_transaction=ref(run/'update_transaction.json'),
                    stdout=ref(control/'logs'/(tag+'.stdout.txt')), stderr=ref(control/'logs'/(tag+'.stderr.txt')),
                    original_checkpoint_refs=complete['checkpoints'], checkpoints_loaded_or_copied=False,
                    source_intervention=receipt['intervention'], independently_verified_intervention=closure,
                    original_files_modified=False))
                run_rows.append(dict(job, updates=1000, **counts,
                    initialization_sha256=binding['initialization_sha256'],
                    original_cache_closed=receipt['intervention']['closed'],
                    audit_cache_explicit_close_called=closure['cache_explicit_close_called'],
                    audit_closure_evidence=closure['closure_evidence'],
                    source_intervention_json=canonical(receipt['intervention']),
                    audit_intervention_json=canonical(closure), prefetch_json=canonical(receipt['prefetch']),
                    run_directory=str(run), run_receipt_sha256=item['receipt_sha256'],
                    training_complete_sha256=item['complete_sha256']))
        require(row_count == totals['updates'] == 27000 and len(sources) == 27
                and totals == audit['actual_totals'], '所有27臂/27000步实际总预算必须与独立审计逐值一致')
        fields = ['fold', 'seed', 'group', 'updates', 'R_windows', 'S_windows', 'R_pairs', 'S_pairs',
            'R_known_pairs', 'S_known_pairs', 'initialization_sha256', 'original_cache_closed',
            'audit_cache_explicit_close_called', 'audit_closure_evidence', 'source_intervention_json',
            'audit_intervention_json', 'prefetch_json', 'run_directory', 'run_receipt_sha256', 'training_complete_sha256']
        with (output/'runs.csv').open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(run_rows)
        require(ref(config) == flight['protocol'] and ref(budget) == flight['actual_budget']
                and ref(control/'driver_state.json') == flight['control_state'], '导出期间原协议/预算/控制终态发生变化')
        result = dict(schema='bounded_velocity27_raw_training_archive_v1', status=STATUS,
            generated_utc=datetime.now(timezone.utc).isoformat(), protocol=ref(config), actual_budget=ref(budget),
            control_state=ref(control/'driver_state.json'), sources=sources,
            steps=ref(output/'steps.csv'), runs=ref(output/'runs.csv'), raw_steps=row_count,
            training_runs=27, actual_totals=dict(totals), original_complete_checkpoints=567,
            checkpoint_weights_read=False, checkpoints_copied=False, raw_records_modified=False,
            raw_data_not_smoothed=True, missing_fields_fabricated=False, new_optimizer_updates=0,
            model_loaded=False, tracking_metrics_read=False, media_read=False, test_read=False,
            failed_audit_sources=flight['failed_audit_sources'],
            audit_failure_note='a01 wrongly required explicit cache.close; frozen prefetch joined workers but did not call resource.close; '
                'a02 retains source closed=false and separately verifies joined prefetch plus actual run process exit; no training replay or source rewrite',
            failed_audit_source_paths_supplied=bool(flight['failed_audit_sources']),
            source_cache_closed_flags_preserved=True,
            diagnostic_updates_excluded=6, diagnostic_R_windows_excluded=18, diagnostic_S_windows_excluded=4,
            model_selection='last1000_no_best_not_EMA',
            interpretation='window exposures and pair counts are not independent images or equal FLOPs; CSV JSON columns preserve all UID/epoch rows and raw values')
        write_new(output/'complete.json', result)
        return {k: result[k] for k in ('status', 'raw_steps', 'training_runs', 'actual_totals', 'new_optimizer_updates')}
    except BaseException as error:
        write_new(output/'failed.json', dict(status='failed_export_sources_preserved_no_replay', error=repr(error),
            traceback=traceback.format_exc(), new_optimizer_updates=0, model_loaded=False,
            tracking_metrics_read=False, test_read=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'budget', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--budget-sha256')
    parser.add_argument('--failed-audit', type=Path, action='append', default=[])
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    value = (export(args.config, args.control, args.budget, args.output, args.budget_sha256, args.failed_audit)
             if args.execute else preflight(args.config, args.control, args.budget, args.output,
                 args.budget_sha256, args.failed_audit)[3])
    print(canonical(value))
