"""已观察十二片段的零更新政策账本：两个有界常驻worker，不运行追踪/模型/评价。"""
import argparse
from collections import defaultdict, deque
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import csv
import hashlib
import importlib.util
import json
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/tracking_policy_ledger_a01'
ROOT = Path(__file__).resolve().parents[2]
STATUS = 'complete12_sources114_output_units_zero_update_policy_ledger_workers_exited'
BUCKETS = ('below_0.1', 'equal_0.1', 'between_0.1_0.25', 'equal_0.25',
           'between_0.25_0.6', 'equal_0.6', 'above_0.6')
METHODS = ('official_ocsort', 'PT_bbox', 'strong_motion_RS')
PROFILE = dict(analysis_workers=2, numeric_threads=1, reserve_RAM_bytes=8589934592,
               reserve_commit_bytes=6442450944, startup_estimate_bytes=268435456)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def physical(path):
    path = Path(os.path.abspath(path))
    require(R in path.parents, '只准实际研究根内物理文件')
    require(not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
                    for p in path.parts), '测试继续封存')
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            require(not item.is_symlink() and not getattr(item.lstat(), 'st_file_attributes', 0) & 0x400,
                    '不跟随junction')
    return path


def sha(path):
    return hashlib.sha256(physical(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(physical(path)), sha256=sha(path))


def checked(reference):
    path = physical(reference['path'])
    require(sha(path) == reference['sha256'], '冻结引用改变：'+str(path))
    return path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True; spec.loader.exec_module(value)
    finally:
        sys.dont_write_bytecode = old
    return value


def validate_config(path):
    cfg = read(physical(path))
    require(cfg['schema'] == 'tracking_policy_ledger_protocol_v1' and cfg['approved_by'] == 'root'
        and cfg['analysis_authorized'] is True and cfg['test_sealed'] is True
        and cfg['new_optimizer_updates'] == 0 and cfg['new_model_or_tracker_or_TrackEval_runs'] == 0,
        '只授权零更新后验账本')
    require(Path(cfg['bundle']) == ROOT and ROOT.parent == R/'code', '仅执行最小冻结bundle')
    for entry in read(checked(cfg['bundle_manifest']))['files']:
        require(sha(ROOT/entry['path']) == entry['sha256'], '冻结源码不同')
    inventory = read(checked(cfg['inventory']))
    require(inventory['status'] == 'complete_readonly_inventory114_no_cache_or_GT_loaded', '盘点未闭合')
    for key in ('sources', 'panels', 'units', 'GT_loaders', 'counts'):
        require(cfg[key] == inventory[key], '不能重选源、训练单元或分母：'+key)
    require(cfg['counts']['sources'] == 12 and cfg['counts']['units'] == 114
        and cfg['counts']['unique_source_frames'] == 8165 and cfg['counts']['unit_frames'] == 76315
        and cfg['counts']['raw_detections_from_frozen_summary'] == 149245, '完整矩阵或原摘要不同')
    require(cfg['sequence_order'] == [s for p in ('original_heldout', 'old_external', 'seven_observed')
        for s in cfg['panels'][p]], '只能原3/2/7完整顺序')
    require(cfg['worker_profile'] == PROFILE and Path(cfg['output_root']) == EXP/'analysis_a01', '并行/物理输出不同')
    require(cfg['policy']['score_buckets'] == list(BUCKETS) and cfg['policy']['IoU_threshold'] == .5
        and cfg['policy']['float32_threshold_semantics'] is True
        and cfg['policy']['internal_lifecycle'] == 'unknown_from_MOT'
        and cfg['policy']['GT_geometry_is_posthoc_only'] is True, '事前政策口径改变')
    require(read(checked(cfg['numeric_contract']))['status'] == 'complete_policy_inventory_core_controller_CPU_contracts',
        '必须先完成针对性CPU合同')
    checked(cfg['worker_support'])
    return cfg


def producers_absent():
    command = "Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True,
                            text=True, encoding='utf-8', check=True)
    rows = json.loads(result.stdout) if result.stdout.strip() else []
    rows = [rows] if isinstance(rows, dict) else rows
    own = {os.getpid()}; byid = {x['ProcessId']: x for x in rows}; node = byid.get(os.getpid())
    while node and node['ParentProcessId'] in byid:
        parent = byid[node['ParentProcessId']]
        if 'tracking_policy_ledger_control.py' not in (parent.get('CommandLine') or ''):
            break
        own.add(parent['ProcessId']); node = parent
    pattern = re.compile(r'(?:^|[\\/\s\"\x27])(?:tracking_policy_ledger_control|ocsort_cached_(?:control|admission)|pose_velocity_(?:tracking_control|learning_train)|substitution_validation_predictions)[.]py(?=$|[\s\"\x27])', re.I)
    blocked = [x for x in rows if x['ProcessId'] not in own and
        ((x.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(x.get('CommandLine') or ''))]
    require(not blocked, '相关生产者仍在，保留现状：'+canonical(blocked))
    return dict(actual_CIM_checked=True, related_producers_absent=True, own_launcher_chain=sorted(own))


def write_csv(path, rows):
    require(rows, '完整汇总不能为空')
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def summarize(cfg, results, output):
    """所有训练单元留存；源只计一次，方法先在比赛内平均。"""
    require(set(results) == set(cfg['sources']), '十二源缺项')
    source_rows, unit_rows, match_rows = [], [], []
    for sequence in cfg['sequence_order']:
        summary = results[sequence]; count = summary['source_counts']; panel = next(p for p in cfg['panels'] if sequence in cfg['panels'][p])
        require(summary['source_denominator_copies'] == 1 and summary['cache_stream_passes'] == 1, '重复源分母')
        source_rows.append(dict(sequence=sequence, panel=panel, **count, **summary['score_buckets'],
            **summary['raw_eligibility'], **summary['GT_opportunities']))
        by_method = defaultdict(list)
        for unit in summary['units']:
            require(unit['internal_lifecycle'] == 'unknown_from_MOT', '不能从MOT补造内部状态')
            row = {k: unit[k] for k in ('unit_id', 'method', 'sequence', 'fold', 'seed', 'source_frames',
                'output_rows', 'frames_with_any_output', 'emitted_trajectory_count', 'emission_gap_count',
                'same_ID_reemission_after_gap_count', 'raw_geometric_proxy_score_unknown')}
            row['panel'] = panel
            for key in ('output_to_raw', 'output_to_GT', 'raw_geometric_proxy_score_buckets'):
                row.update({key+'__'+k: v for k, v in unit[key].items()})
            row.update(mot_path=unit['mot']['path'], mot_sha256=unit['mot']['sha256'], internal_lifecycle='unknown_from_MOT')
            unit_rows.append(row); by_method[unit['method']].append(unit)
        for method in METHODS:
            group = by_method[method]; require(group, '方法缺项')
            def mean(key): return sum(u[key] for u in group)/len(group)
            output_mean = mean('output_rows')
            gt_unique = sum(u['output_to_GT']['mutual_unique'] for u in group)/len(group)
            raw_unique = sum(u['output_to_raw']['mutual_unique'] for u in group)/len(group)
            match_rows.append(dict(sequence=sequence, panel=panel, method=method, training_units=len(group),
                source_frames=count['source_frames'], source_GT_rows=count['GT_rows'],
                mean_output_rows=output_mean, mean_output_rows_per_source_frame=output_mean/count['source_frames'],
                mean_frames_with_any_output=mean('frames_with_any_output'),
                mean_emitted_trajectories=mean('emitted_trajectory_count'), mean_emission_gap_count=mean('emission_gap_count'),
                mean_mutual_unique_output_GT_rows=gt_unique,
                mean_mutual_unique_output_GT_rows_per_source_GT=gt_unique/count['GT_rows'],
                mean_mutual_unique_output_raw_rows=raw_unique,
                mean_raw_score_geometric_proxy_unknown=mean('raw_geometric_proxy_score_unknown'),
                internal_lifecycle='unknown_from_MOT', interpretation='posthoc_geometry_and_emissions_not_TrackEval'))
    require(len(source_rows) == 12 and len(unit_rows) == 114 and len(match_rows) == 36, '完整源/单元/方法比赛数量不同')
    require(sum(x['source_frames'] for x in source_rows) == 8165 and sum(x['raw_detections'] for x in source_rows) == 149245
        and sum(x['GT_rows'] for x in source_rows) == cfg['expected_unique_GT_rows']
        and sum(x['source_frames'] for x in unit_rows) == 76315, '完整分母不同')
    panels = []
    for panel in cfg['panels']:
        for method in METHODS:
            group = [r for r in match_rows if r['panel'] == panel and r['method'] == method]
            row = dict(panel=panel, method=method, matches=len(group), aggregation='equal_match_means_after_within_match_training_unit_mean')
            for key in ('mean_output_rows_per_source_frame', 'mean_mutual_unique_output_GT_rows_per_source_GT'):
                row[key] = sum(r[key] for r in group)/len(group)
            panels.append(row)
    artifacts = {}
    for key, rows in [('source_summary', source_rows), ('all_units', unit_rows),
                      ('method_sequence_summary', match_rows), ('panel_summary', panels)]:
        target = output/(key+'.csv'); write_csv(target, rows); artifacts[key] = dict(ref(target), rows=len(rows))
    report = dict(schema='tracking_policy_ledger_report_v1', status='complete12_sources114_units36_method_matches_policy_ledger',
        inventory=cfg['inventory'], sequence_summaries=[ref(output/'sequences'/s/'summary.json') for s in cfg['sequence_order']],
        artifacts=artifacts, counts=dict(sources=12, source_frames=8165, raw_detections=149245,
            source_GT_rows=cfg['expected_unique_GT_rows'], units=114, unit_frames=76315, method_matches=36),
        panel_summary=panels, GT_only_posthoc=True, new_optimizer_updates=0, new_model_or_tracker_or_TrackEval_runs=0,
        new_images_or_predictions=0, test_read=False, all_negative_and_ambiguous_results_preserved=True,
        static_policy=cfg['static_policy'], formal_equivalence_or_noninferiority=False,
        internal_lifecycle='unknown_from_MOT', hypothetical_threshold_policy_executed=False,
        inference='几何机会、分数资格和MOT发出账本；不能据此归因全部指标差距或宣称新追踪收益。')
    write_new(output/'report.json', report); return report


def worker_service(connection, cfg, log):
    try:
        with Path(log).open('x', encoding='utf-8') as stream, redirect_stdout(stream), redirect_stderr(stream):
            core = module('frozen_policy_ledger_core', ROOT/'tools/research_ops/tracking_policy_ledger_core.py')
            jobs = 0
            connection.send(dict(status='ready', worker_pid=os.getpid()))
            while True:
                task = connection.recv()
                if task['op'] == 'close':
                    forbidden = [name for name in sys.modules if name.split('.')[0] in ('torch', 'ultralytics', 'filterpy', 'trackeval')]
                    require(not forbidden, '零更新worker意外加载模型/追踪/TrackEval模块')
                    connection.send(dict(status='closed', worker_pid=os.getpid(), jobs=jobs,
                        GT_loaded_only_posthoc=True, model_tracker_TrackEval_modules_loaded=forbidden)); break
                started = time.perf_counter()
                core.analyze_sequence(cfg, task['sequence'], task['output']); jobs += 1
                connection.send(dict(status='complete', sequence=task['sequence'], worker_pid=os.getpid(),
                    summary=ref(Path(task['output'])/'summary.json'), wall_seconds=time.perf_counter()-started))
    except BaseException:
        try:
            connection.send(dict(status='failed', worker_pid=os.getpid(), traceback=traceback.format_exc()))
        except (EOFError, BrokenPipeError):
            pass
    finally:
        connection.close()


class Service:
    def __init__(self, cfg, log):
        ctx = mp.get_context('spawn'); self.parent, child = ctx.Pipe(); self.busy = None; self.closed = False
        self.task_failed = False
        self.process = ctx.Process(target=worker_service, args=(child, cfg, str(log)))
        self.process.start(); child.close()
        try:
            self.ready = self.receive()
            require(self.ready['status'] == 'ready' and self.ready['worker_pid'] == self.process.pid, 'worker未实际就绪')
        except BaseException as error:
            self.process.join(30); self.parent.close()
            write_new(Path(log).with_suffix('.startup_failed.json'), dict(status='failed_startup_preserved_no_kill_or_replay',
                worker_pid=self.process.pid, joined=True, process_exited=not self.process.is_alive(),
                exit_code=self.process.exitcode, error=repr(error)))
            raise

    def receive(self):
        try:
            require(self.parent.poll(1800), 'worker超时，保留partial不强杀或重启')
            value = self.parent.recv()
            if value['status'] == 'failed': self.task_failed = True
            require(value['status'] != 'failed', value.get('traceback', 'worker失败')); return value
        except (EOFError, BrokenPipeError):
            self.task_failed = True
            raise

    def join_failed(self):
        self.process.join(30); self.parent.close(); self.closed = True
        return dict(status='failed_worker_partial_preserved_no_replay', worker_pid=self.process.pid,
            joined=True, process_exited=not self.process.is_alive(), exit_code=self.process.exitcode)

    def close(self):
        require(not self.closed and self.busy is None, '只关闭空闲worker')
        self.parent.send(dict(op='close')); value = self.receive(); self.process.join(30)
        require(value['status'] == 'closed' and value['worker_pid'] == self.ready['worker_pid'] == self.process.pid
            and not self.process.is_alive() and self.process.exitcode == 0, '实际worker关闭退出失败')
        self.parent.close(); self.closed = True
        return dict(**value, joined=True, process_exited=True, exit_code=self.process.exitcode)


def execute(path, config_sha):
    started = time.perf_counter(); require(sha(path) == config_sha, '配置SHA不同'); cfg = validate_config(path)
    producers_absent(); output = physical(cfg['output_root']); require(not output.exists(), '输出/partial已存在，拒绝重复执行')
    output.mkdir(parents=True); (output/'logs').mkdir(); (output/'sequences').mkdir()
    support = module('ledger_resource_support', checked(cfg['worker_support']))
    state = dict(status='starting2_posthoc_workers', protocol=ref(path), parent_pid=os.getpid(),
        created_utc=datetime.now(timezone.utc).isoformat(), workers=[], active=[], completed=[], worker_exits=[],
        resources=[], new_optimizer_updates=0, new_model_or_tracker_or_TrackEval_runs=0, test_read=False)
    def save():
        temp = output/'state.pending.json'; temp.write_text(canonical(state), encoding='utf-8'); os.replace(temp, output/'state.json')
    services = []; pending = deque(cfg['sequence_order']); completed = {}; stopped = False; paused = None; save()
    try:
        require(support.enough_memory(support.resource_snapshot(), cfg['worker_profile'], 2), '实际RAM/commit余量不足')
        for index in range(2):
            service = Service(cfg, output/'logs'/f'analysis_{index}.log'); services.append(service); state['workers'].append(service.ready); save()
        while pending or any(s.busy for s in services):
            if (output/'STOP').exists(): stopped = True
            snapshot = support.resource_snapshot()
            import psutil
            tree = [psutil.Process()]+psutil.Process().children(recursive=True); rss = 0
            for process in tree:
                try: rss += process.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
            snapshot['sampled_process_tree_RSS_bytes'] = rss; state['resources'].append(snapshot)
            for service in services:
                if service.busy or not pending or stopped: continue
                if not support.enough_memory(snapshot, cfg['worker_profile']):
                    paused = paused or time.monotonic(); require(time.monotonic()-paused < 600, '资源不足持续超时，保留partial'); continue
                paused = None; sequence = pending.popleft()
                service.parent.send(dict(op='analyze', sequence=sequence, output=str(output/'sequences'/sequence))); service.busy = sequence
            state.update(status='running_zero_update_posthoc_ledger', active=[dict(sequence=s.busy,
                worker_pid=s.ready['worker_pid']) for s in services if s.busy]); save()
            busy = [s for s in services if s.busy]
            if not busy:
                if stopped: break
                time.sleep(.5); continue
            available = wait([s.parent for s in busy], timeout=1)
            for service in busy:
                if service.parent not in available: continue
                message = service.receive(); sequence = service.busy; service.busy = None
                require(message['status'] == 'complete' and message['sequence'] == sequence
                    and message['worker_pid'] == service.ready['worker_pid'], '任务身份不同')
                require(sequence not in completed, '不能重放源'); completed[sequence] = message
                state['completed'].append(message); save()
        for service in services: state['worker_exits'].append(service.close())
        state['active'] = []; state['actual_exit_gate'] = producers_absent(); save()
        if stopped:
            state['status'] = 'stopped_by_user_partial_preserved'; save(); return state['status']
        results = {s: read(checked(completed[s]['summary'])) for s in cfg['sequence_order']}
        summarize(cfg, results, output)
        state.update(status=STATUS, report=ref(output/'report.json'), wall_seconds=time.perf_counter()-started)
        save(); return dict(status=STATUS, sources=12, units=114, test_read=False)
    except BaseException as error:
        for service in services:
            if service.closed: continue
            try:
                if service.task_failed:
                    state['worker_exits'].append(service.join_failed()); continue
                if service.busy:
                    service.receive(); service.busy = None
                state['worker_exits'].append(service.close())
            except BaseException as closing:
                state.setdefault('failure_exit_evidence', []).append(repr(closing))
                state['worker_exits'].append(service.join_failed())
        state.update(status='failed_partial_preserved_no_implicit_replay', error=repr(error), traceback=traceback.format_exc())
        save(); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256'); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    if args.execute: result = execute(args.config, args.config_sha256)
    else:
        cfg = validate_config(args.config); result = dict(status='readonly_policy_ledger_protocol_no_cache_GT_or_MOT_loaded',
            sources=12, units=114, new_optimizer_updates=0, new_model_or_tracker_or_TrackEval_runs=0, test_read=False)
    print(canonical(result))
