"""绿色A/B十八臂串行控制；真实预算/模型身份/追踪齐全后才汇总。"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from green_kit_runtime import ROOT, canonical, checked, load_reference, physical_output, read, require, sha, validate_job, validate_protocol


def preflight(config, output):
    cfg, _ = validate_protocol(config); numeric, old = load_reference(cfg)
    from v8_control import process_snapshot, own_launcher_chain
    processes = process_snapshot(); own = own_launcher_chain(processes, os.getpid(), Path(__file__).resolve())
    names = ('green_kit_prediction_cache.py', 'green_kit_control.py', 'green_kit_train.py', 'green_kit_track.py', 'v9_control.py', 'v8_control.py')
    blocked = [p for p in processes if p['ProcessId'] not in own and
               ('unrealeditor' in p['Name'].lower() or any(n in (p.get('CommandLine') or '') for n in names))]
    require(not blocked, '预测/UE/已有控制器占用，禁止重复启动：'+str(blocked))
    require(not physical_output(output).exists(), '已有控制目录/partial，不自动重放')
    for fold in cfg['reference_gated_R'].values():
        for reference in fold.values():
            checked(reference['training_receipt'])
    checked(cfg['v9_analysis']); checked(old['recovery_registry'])
    for job in cfg['training_matrix']:
        validate_job(config, job['fold'], job['seed'], job['appearance'])
    return cfg, numeric, old, dict(status='readonly_green_18arm_preflight', protocol_sha256=sha(config),
        runs=18, actual_updates_planned=18000, real_windows_per_arm=3000, synthetic_windows_per_arm=1000,
        R_window_exposures_planned=54000, S_window_exposures_planned=18000, own_verified_launcher_chain=sorted(own), test_read=False)


def execute(config, output):
    cfg, numeric, old, flight = preflight(config, output); output = physical_output(output)
    output.mkdir(parents=True); numeric.atomic(output/'preflight.json', flight)
    state = dict(schema='green_kit_serial_gated_control_v1', status='starting', pid=os.getpid(),
                 protocol_sha256=sha(config), completed_train=[], completed_tracking=[], active=None)
    def save():
        state['updated_utc'] = datetime.now(timezone.utc).isoformat(); numeric.atomic(output/'driver_state.json', state)
    def child(tag, script, args):
        require(not (output/'STOP').exists(), 'STOP边界请求，保留完整状态')
        log = output/'logs'/tag; log.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, '-B', str(script)]+list(map(str, args)); start = time.perf_counter()
        with log.with_suffix('.stdout.txt').open('x', encoding='utf-8') as stdout, log.with_suffix('.stderr.txt').open('x', encoding='utf-8') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=os.environ.copy())
            state['active'] = dict(tag=tag, child_pid=process.pid, command=command); save(); code = process.wait()
        require(code == 0, tag+' exit'+str(code)+'；完整保留，不自动重放')
        state['active'] = None; save(); return time.perf_counter()-start
    identities = {}
    try:
        for job in cfg['training_matrix']:
            fold, seed, appearance = job['fold'], job['seed'], job['appearance']
            folder = output/'runs'/fold/str(seed)/appearance; tag = f'{fold}_{seed}_{appearance}'
            state['status'] = 'training_and_tracking'; save()
            seconds = child(tag+'_train', ROOT/'tools/research_ops/green_kit_train.py',
                ['--config', config, '--fold', fold, '--seed', seed, '--appearance', appearance, '--output', folder/'training', '--execute'])
            receipt = read(folder/'training/run_receipt.json'); binding = receipt['binding']
            require(receipt['status'] == 'complete' and receipt['completed_updates'] == 1000
                    and receipt['real_window_exposures'] == 3000 and receipt['synthetic_window_exposures'] == 1000,
                    '实际更新/曝光不足')
            common = tuple(binding[k] for k in ('initialization_sha256', 'R_window_UID_chain_sha256', 'S_window_UID_chain_sha256', 'adapter_sha256'))
            key = (fold, seed)
            if key not in identities:
                identities[key] = common
            require(identities[key] == common and receipt['prefetch']['closed']
                    and receipt['prefetch']['yielded'] == 1000 and not receipt['prefetch']['worker_alive'],
                    'A/B初始化/UID顺序/adapter或预取未闭合')
            state['completed_train'].append(dict(**job, receipt_sha256=sha(folder/'training/run_receipt.json'), process_wall_seconds=seconds)); save()
            child(tag+'_track', ROOT/'tools/research_ops/green_kit_track.py', ['--config', config, '--run', folder/'training', '--output', folder/'tracking', '--execute'])
            child(tag+'_metric', ROOT/'tools/research_ops/green_kit_metric.py', ['--config', config, '--tracking', folder/'tracking', '--output', folder/'metric', '--execute'])
            child(tag+'_recovery', Path(old['bundle'])/'tools/research_ops/v8_gap_recovery.py',
                  ['--registry', checked(old['recovery_registry']), '--tracking', folder/'tracking', '--output', folder/'recovery.json'])
            require(read(folder/'metric/report.json')['status'] == 'complete', '评价缺失')
            state['completed_tracking'].append(dict(**job, metric_sha256=sha(folder/'metric/report.json'))); save()
        state['status'] = 'complete_18_train_tracking_wait_analysis'; save()
        child('final_analysis', ROOT/'tools/research_ops/green_kit_analyze.py', ['--config', config, '--control', output, '--output', output/'analysis_a01'])
        state['status'] = 'complete_18_train_tracking_and_analysis'; save()
    except BaseException as error:
        state['status'] = 'failed_preserved_no_automatic_replay'; state['error'] = repr(error); state['traceback'] = traceback.format_exc(); save(); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    os.environ.update(PYTHONUTF8='0', PYTHONIOENCODING='utf-8', PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies')
    if args.execute:
        execute(args.config, args.output)
    else:
        print(canonical(preflight(args.config, args.output)[3]))
