"""唯一CPU追踪控制器：450新T加63来源缺失参考，保留全部失败和配对结果。"""
import argparse
from datetime import datetime, timezone
import importlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).parent))
STATUS = 'complete513_bounded_velocity_tracking_and_analysis'
ANALYSIS_STATUS = 'complete513_all_results450_new63_reference_paired_intervals'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def process_gate(records, pid, script):
    """只豁免实际父子同命令链；完整脚本名避免审计/verify文件的子串误报。"""
    byid = {p['ProcessId']: p for p in records}; current = byid.get(pid); own = {pid}
    needle = str(script).replace('/', '\\').lower()
    def tail(record):
        text = (record.get('CommandLine') or '').replace('"', '').replace('/', '\\').lower()
        return text[text.index(needle):] if needle in text else None
    for _ in range(8):
        parent = byid.get(current.get('ParentProcessId')) if current else None
        if parent is None or tail(current) is None or tail(parent) != tail(current):
            break
        if parent['ProcessId'] in own:
            break
        own.add(parent['ProcessId']); current = parent
    scripts = (r'pose_velocity_tracking_(?:control|jobs)', r'pose_velocity_learning_(?:train|control)',
        r'validate_pose_velocity_learning_numeric', r'v10_(?:train|training_control|tracking_control)',
        r'substitution_C_(?:train|control)', r'substitution_validation_predictions', r'substitution_tracking_(?:control|jobs)')
    pattern = re.compile(r'(?:^|[\\/\s\"\x27])(?:'+r'|'.join(scripts)+r')[.]py(?=$|[\s\"\x27])')
    blocked = [p for p in records if p['ProcessId'] not in own and (
        (p.get('Name') or '').lower().startswith('unrealeditor') or pattern.search(p.get('CommandLine') or ''))]
    require(not blocked, '真实GPU/训练/重复追踪/UE仍在，禁止并发或重放：'+str(blocked))
    return sorted(own)


def snapshot():
    command = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
               "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    value = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
        capture_output=True, text=True, encoding='utf-8', errors='strict', check=True)
    rows = json.loads(value.stdout) if value.stdout.strip() else []
    return [rows] if isinstance(rows, dict) else rows


def preflight(config, output):
    rt = importlib.import_module('pose_velocity_tracking_runtime')
    cfg, dep, learning = rt.validate_config(config)
    own = process_gate(snapshot(), os.getpid(), Path(__file__).resolve())
    require(len(cfg['tracking_matrix']) == 513
            and sum(j['kind'] == 'new' for j in cfg['tracking_matrix']) == 450
            and sum(j['kind'] == 'reference' for j in cfg['tracking_matrix']) == 63,
            '必须是450新T+63补充参考的真实矩阵')
    from pose_velocity_tracking_analysis import source_references, validate_panels
    validate_panels(cfg['panels'])
    source_references(cfg, rt)
    require('analysis_plan' in cfg, '结果前分析计划未冻结')
    rt.checked(cfg['analysis_plan'])
    for source in cfg['sources'].values():
        rt.checked(source['cache'])
    output = dep[3].storage().physical_child(output, rt.EXP)
    require(not output.exists(), '已有控制器/partial，不覆盖或隐式续跑')
    return rt, cfg, dep, dict(status='readonly513_bounded_velocity_tracking_preflight',
        tracking_jobs=513, new_representation_tracking_jobs=450, added_reference_tracking_jobs=63,
        new_optimizer_updates=0, GPU=False, test_read=False, own_launcher_chain=own)


def adapter_gate(receipt):
    require(receipt['schema'] == 'bounded_velocity513_free_tracking_v1'
            and receipt['status'] == 'complete' and receipt['job']['kind'] == 'new'
            and receipt['pose_enabled'] is True and receipt['inference_shape_shuffle'] is False
            and receipt['evaluation_GT_annotations_loaded'] is False, '首新模型真实追踪身份或GT边界不符')
    ast = receipt['scope_adapter']; actual = receipt['input_adapter_audit']
    require(ast['tracker_numeric_AST_unchanged_outside_scope_and_input'] is True
            and ast['original_AST_sha256'] == ast['reverse_restored_AST_sha256'], '原追踪数值AST逆恢复不一致')
    require(actual['adapter_transform_pair_calls'] > 0 and actual['feature_calls'] > 0
            and actual['observed_feature_dims'] == [195] and actual['all_finite'] is True
            and actual['actual_feature_checks_performed'] is True,
            '首新模型未真实执行有界特征适配或输入维度/有限性不符')
    return dict(status='complete_first_new_bounded_adapter_actual_tracking_and_metric_gate',
        job=receipt['job'], scope_adapter=ast, actual_input_adapter=actual,
        new_optimizer_updates=0, test_read=False)


def execute(config, output):
    rt, cfg, dep, flight = preflight(config, output)
    output = Path(output); output.mkdir(parents=True)
    journal = rt.module('velocity_tracking_atomic', dep[3].ROOT/'tools/research_ops/training_journal.py')
    journal.atomic(output/'preflight.json', flight)
    state = dict(schema='bounded_velocity513_tracking_control_v1', status='starting', pid=os.getpid(),
        protocol_sha256=rt.sha(config), completed_tracking=[], active=None,
        new_representation_tracking_jobs=450, added_reference_tracking_jobs=63)
    def save():
        state['updated_utc'] = datetime.now(timezone.utc).isoformat()
        journal.atomic(output/'driver_state.json', state)
    def child(tag, entry, args):
        logs = output/'logs'; logs.mkdir(exist_ok=True)
        command = [sys.executable, '-B', str(rt.ROOT/'tools/research_ops'/entry)]+list(map(str, args))
        with (logs/(tag+'.stdout.log')).open('x', encoding='utf-8') as stdout, \
                (logs/(tag+'.stderr.log')).open('x', encoding='utf-8') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=os.environ.copy())
            state['active'] = dict(tag=tag, pid=process.pid, command=command); save()
            code = process.wait()
        require(code == 0, tag+'真实失败，保留partial/全部日志，不自动重放')
        state['active'] = None; save()
    save(); first_new_verified = False
    try:
        for job in cfg['tracking_matrix']:
            if (output/'STOP').exists():
                state.update(status='stopped_at_user_boundary_no_replay', active=None); save(); return
            folder = output/'runs'/job['job_id']; clock = time.perf_counter()
            state['status'] = 'tracking_and_evaluating'; save()
            child(job['job_id']+'_track', 'pose_velocity_tracking_jobs.py',
                ['--action', 'track', '--config', config, '--job-id', job['job_id'], '--output', folder/'tracking', '--execute'])
            child(job['job_id']+'_metric', 'pose_velocity_tracking_jobs.py',
                ['--action', 'metric', '--config', config, '--tracking', folder/'tracking', '--output', folder/'metric', '--execute'])
            path = folder/'metric/report.json'; report = rt.read(path)
            public_registry = rt.read(rt.checked(rt.registry_for_sequence(cfg, job['sequence'])['receipt']))
            require(report['schema'] == 'bounded_velocity513_trackeval_gap_v1'
                    and report['status'] == 'complete' and report['job'] == job
                    and report['protocol_sha256'] == rt.sha(config) and report['DO_PREPROC'] is False
                    and report['predictions_GT_filtered'] is False and report['test_read'] is False
                    and type(report['GT_rows']) is int and report['GT_rows'] > 0
                    and report['GT_rows'] == public_registry['GT_row_counts'][job['sequence']]
                    and all(math.isfinite(report['summary'][job['sequence']]['metrics_percent'][k])
                            for k in ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')), '实际评价或GT/完整指标边界未闭合')
            if job['kind'] == 'new' and not first_new_verified:
                require(job['pose_enabled'] is True, '首新模型须先实际验有界adapter开启路径')
                receipt_path = folder/'tracking/receipt.json'; receipt = rt.read(receipt_path)
                require(receipt['job'] == job and report['tracking_receipt_sha256'] == rt.sha(receipt_path),
                        '首追踪/评价不是相同实际产物')
                proof = adapter_gate(receipt)
                proof.update(tracking_receipt=rt.ref(receipt_path), metric_report=rt.ref(path))
                journal.atomic(output/'first_bounded_adapter_actual_gate.json', proof)
                first_new_verified = True
            state['completed_tracking'].append(dict(job=job, report_sha256=rt.sha(path),
                path=str(path), wall_seconds=time.perf_counter()-clock)); save()
        require(len(state['completed_tracking']) == 513 and first_new_verified, '实际完整矩阵或首模型门禁不足')
        state['status'] = 'complete513_wait_paired_analysis'; save()
        child('paired_analysis', 'pose_velocity_tracking_analysis.py',
            ['--config', config, '--control', output, '--output', output/'analysis_a01'])
        report = rt.read(output/'analysis_a01/report.json')
        require(report['status'] == ANALYSIS_STATUS and report['tracking_jobs'] == 513
                and report['new_representation_tracking_jobs'] == 450 and report['added_reference_tracking_jobs'] == 63,
                '完整配对与参考未完成')
        state.update(status=STATUS, active=None, analysis_report=rt.ref(output/'analysis_a01/report.json')); save()
    except BaseException as error:
        state.update(status='failed_preserved_no_replay', error=repr(error), traceback=traceback.format_exc()); save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', PYTHONUTF8='0', PYTHONIOENCODING='utf-8',
        PYTHONPATH='D:/projects/FutsalMOT_Research/runtime_dependencies', YOLO_AUTOINSTALL='false')
    if args.execute:
        execute(args.config, args.output)
    else:
        rt = importlib.import_module('pose_velocity_tracking_runtime')
        print(rt.canonical(preflight(args.config, args.output)[3]))
