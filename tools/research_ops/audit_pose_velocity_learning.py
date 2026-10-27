"""独立核对有界变化27臂实际预算、567完整检查点及生产者退出，不训练或预测。"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import traceback

RESEARCH = Path('D:/projects/FutsalMOT_Research')
EXPERIMENT = RESEARCH/'pose/pose_velocity_learning_a01'
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
GROUPS = ('T_R', 'T_RS', 'T_shuffle_RS')
CHANGED = tuple(24+10*j+k for j in range(17) for k in (4, 5))
STATUS = 'complete27_bounded_velocity_actual_budget_full_records_and_exit_verified'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def physical(path):
    path = Path(os.path.abspath(path))
    require(RESEARCH in path.parents, '审计来源必须在实际DResearch目录')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            value = part.lstat()
            require(not stat.S_ISLNK(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400,
                    '审计拒绝junction/重解析点')
    return path


def matrix():
    return [dict(fold=f, seed=s, group=g) for f in FOLDS for s in SEEDS for g in GROUPS]


def validate_state(state, cfg):
    require(cfg['training_matrix'] == matrix(), '事前27臂矩阵缺项/重复/顺序改变')
    jobs = [{k: entry[k] for k in ('fold', 'seed', 'group')} for entry in state['completed_train']]
    require(state['status'] == 'complete27_bounded_velocity_training_wait_independent_audit_tracking'
            and state['active'] is None and jobs == matrix(), '27臂实际终态或矩阵未齐')
    paths = [entry['path'] for entry in state['completed_train']]
    require(len(paths) == len(set(paths)) == 27, '完成列表复用了run目录')


def blocked_processes(processes):
    """识别完整脚本名，审计器、verify前缀及复用旧PID都不冒充生产者。"""
    scripts = (r'pose_velocity_learning_(?:train|control)',
               r'validate_pose_velocity_learning_numeric', r'v10_(?:train|training_control)',
               r'substitution_C_(?:train|control)', r'substitution_validation_predictions')
    pattern = re.compile(r'(?:^|[\\/\s\"\x27])(?:'+r'|'.join(scripts)+r')[.]py(?=$|[\s\"\x27])')
    return [p for p in processes if (p.get('Name') or '').lower().startswith('unrealeditor')
            or pattern.search(p.get('CommandLine') or '')]


def process_snapshot():
    command = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|UnrealEditor'} | "
               "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    response = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
        capture_output=True, text=True, encoding='utf-8', errors='strict', check=True)
    values = json.loads(response.stdout) if response.stdout.strip() else []
    return [values] if isinstance(values, dict) else values


def count_run(logs, table, group):
    require(group in GROUPS and len(logs) == 1000 and len(table['real']) == 3000
            and len(table['synthetic']) == 1000, '正式预算/组别与原曝光表不符')
    totals = Counter(); chain = '0'*64
    for index, entry in enumerate(logs):
        row = dict(entry); recorded_chain = row.pop('chain_sha256')
        chain = hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        rr = table['real'][3*index:3*index+3]
        ss = [] if group == 'T_R' else table['synthetic'][index:index+1]
        require(recorded_chain == chain and type(row['actual_update']) is int
                and row['actual_update'] == index+1 and row['update_index'] == index
                and row['real'] == rr and row['synthetic'] == ss,
                '实际UID/epoch/顺序或连续曝光链不一致')
        counts = dict(R_windows=3, S_windows=len(ss),
            R_pairs=sum(r['candidate_pairs'] for r in rr),
            R_known_pairs=sum(r['labelled_pairs'] for r in rr),
            S_pairs=sum(s['candidate_pairs'] for s in ss),
            S_known_pairs=sum(s['labelled_pairs'] for s in ss))
        require(all(type(row[k]) is int and row[k] == v for k, v in counts.items()),
                '实际全部/已知pair或R/S窗口数与来源UID不符')
        require(all(type(row[k]) in (float, int) and math.isfinite(row[k]) and row[k] >= 0
                    for k in ('loss', 'real_loss', 'grad_l2', 'step_wall_seconds'))
                and row['learning_rates'] == [.001] and row['gradients_clipped'] is False,
                '逐步损失/LR/梯度/耗时缺失、非有限或改动裁剪')
        if ss:
            require(type(row['synthetic_loss']) in (float, int)
                    and math.isfinite(row['synthetic_loss']) and row['synthetic_loss'] >= 0
                    and abs(row['loss']-row['real_loss']-row['synthetic_loss']/3)
                        <= 1e-6*(1+row['loss']),
                    'RS分域loss未记录或登记权重改变')
        else:
            require(row['synthetic_loss'] is None and row['loss'] == row['real_loss'],
                    '纯R包含隐式S损失')
        totals.update(counts)
    return dict(totals), chain


def validate_adapter(state, old, quality_scale, velocity_clip, fold, windows):
    require(state.get('schema') == 'bounded_pose_velocity_adapter_v1'
            and state.get('feature_dim') == 195 and state.get('model_variant') == 'gated'
            and state.get('changed_columns') == list(CHANGED)
            and state.get('base_normalizer') == old
            and state.get('quality_scale') == quality_scale
            and state.get('velocity_clip') == velocity_clip
            and state.get('gate_source') == 'original_unshuffled_after_same_v9_augmentation_raw'
            and state.get('motion_and_mask_source') == 'unchanged_target_prediction'
            and state.get('normalizer_fit') == 'known_label_clean_base_R_only',
            'adapter有界编码/原gate/来源身份不符')
    new = state['normalizer']
    require(set(new) == set(old) and all(new[k] == old[k] for k in old if k not in ('mean', 'std'))
            and len(new['mean']) == len(new['std']) == 194,
            '只允许34列标准化参数变化，不能改拟合元数据')
    require(all(new[k][i] == old[k][i] for k in ('mean', 'std') for i in range(194) if i not in CHANGED)
            and all(math.isfinite(v) for k in ('mean', 'std') for v in new[k])
            and all(v >= .05 for v in new['std']), '其他160列或标准化边界改变')
    games = {w['game'] for w in windows}
    known = sum(c['label'] is not None for w in windows for c in w['candidates'])
    require(len(windows) == 1000 and games == set(FOLDS)-{fold}
            and all(w['domain'] == 'real' for w in windows)
            and state['fit']['fit_scope'] == 'known_label_clean_base_R_only'
            and state['fit']['windows'] == 1000 and state['fit']['known_pairs'] == known == old['count']
            and state['fit']['games'] == sorted(games), '标准化混入S/留出/外部或fit计数不同')
    return dict(changed_columns=list(CHANGED), unchanged_normalizer_columns=160,
                known_base_R_pairs=known, quality_gate_unchanged=True,
                normalization_fit_external_or_S=False)


def validate_intervention(stats, group, counts=None, *, prefetch=None, producer_processes_absent=False):
    # 原冻结预取只join线程/释放lease，未调用resource.close。不得把真实False重写为True。
    explicit_close = stats['closed'] is True
    process_released = (stats['closed'] is False and producer_processes_absent is True
        and isinstance(prefetch, dict) and prefetch.get('closed') is True
        and prefetch.get('worker_alive') is False
        and type(prefetch.get('loaded')) is int and prefetch['loaded'] == 1000
        and type(prefetch.get('yielded')) is int and prefetch['yielded'] == 1000)
    require(stats['augmentation'] == 'original_v9_both' and stats['original_gate_preserved'] is True
            and stats['GT_donor_selection'] is False and stats['future_donor_used'] is False
            and (explicit_close or process_released) and stats['observation_cache_limit'] == 4096
            and stats['feature_cache_limit_bytes'] == 268435456, '增广/gate/负控制边界或缓存未闭合')
    reasons = stats['shuffle_reasons']; attempts = stats['shuffle_unique_attempts']
    require(type(attempts) is int and attempts >= 0
            and all(type(v) is int and v >= 0 for v in reasons.values())
            and sum(reasons.values()) == attempts, '负控制实际尝试/回退覆盖账本不足')
    if group == 'T_shuffle_RS':
        bank = stats['shuffle_bank']
        require(bank['same_frame'] is True and bank['exact_original_mask'] is True
                and bank['GT_used'] is False and bank['future_used'] is False
                and bank['source_scope'] == 'all_observations_in_fixed_pools_not_complete_raw_frames'
                and 0 <= bank['mapped_observations'] <= bank['observations'] and attempts > 0,
                '从首步负控制未保持同帧/mask/来源与实际覆盖')
    else:
        require(attempts == 0 and reasons == {} and 'shuffle_bank' not in stats,
                '真实T组混入负控制')
    coverage = stats['by_domain']
    require(set(coverage) == {'real', 'synthetic'}, '缺实际R/S负控制pair覆盖分母')
    for domain, label in (('real', 'R'), ('synthetic', 'S')):
        value = coverage[domain]; known = value['known_pairs_materialized']
        changed = value['pairs_with_changed_features']
        require(all(type(x) is int and x >= 0 for x in value.values())
                and 0 <= value['pairs_with_changed_full_shape'] <= known
                and 0 <= changed <= known and value['unchanged_pairs'] == known-changed,
                '实际pair形状/特征变化与未变化覆盖账本不完整')
        if counts is not None:
            require(known == counts[label+'_known_pairs'], '覆盖分母不等于正式实际全部已知pair曝光')
        if group != 'T_shuffle_RS':
            require(changed == value['pairs_with_changed_full_shape'] == 0, '真T混入负控制pair变化')
    return dict(group=group, attempts_unique_observation_epochs=attempts,
                reasons=dict(reasons), shuffle_bank=stats.get('shuffle_bank'),
                actual_pair_coverage=coverage,
                cache_explicit_close_called=explicit_close, source_cache_closed_flag=stats['closed'],
                closure_evidence='explicit_cache_close_called' if explicit_close
                    else 'producer_joined_and_run_process_exited',
                not_independent_images_or_matches=True)


def load_runtime(config):
    cfg = read(physical(config)); bundle = physical(cfg['bundle'])
    require(bundle.parent == RESEARCH/'code', '必须从独立冻结有界变化bundle加载runtime')
    ref = cfg['bundle_manifest']; manifest = physical(ref['path'])
    require(sha(manifest) == ref['sha256'], 'bundle索引SHA改变')
    for item in read(manifest)['files']:
        require(sha(physical(bundle/item['path'])) == item['sha256'], '有界变化执行源码身份改变')
    sys.path.insert(0, str(bundle/'tools/research_ops'))
    spec = importlib.util.spec_from_file_location('independent_bounded_velocity_runtime',
        bundle/'tools/research_ops/pose_velocity_learning_runtime.py')
    rt = importlib.util.module_from_spec(spec); spec.loader.exec_module(rt)
    rt.validate_protocol(config)
    return cfg, rt


def audit_payload(payload, *, step, binding, extra, chain, template, torch, np):
    require(payload['schema'] == 'full_training_checkpoint_v1'
            and payload['binding'] == binding and payload['completed_updates'] == step
            and payload['exposure_chain'] == chain and payload['extra'] == extra,
            '检查点实际步数/曝光链/方法身份不符')
    require(payload['model'].keys() == template.state_dict().keys()
            and all(torch.is_tensor(value) and value.dtype == torch.float32
                    and tuple(value.shape) == tuple(template.state_dict()[name].shape)
                    and bool(torch.isfinite(value).all()) for name, value in payload['model'].items()),
            '实际模型非FP32、形状/字段不同或非有限')
    opt = payload['optimizer']; require(len(opt['param_groups']) == 1, '原AdamW参数组变化')
    group = opt['param_groups'][0]; params = list(template.parameters())
    require(group['lr'] == .001 and group['weight_decay'] == .0001
            and tuple(group['betas']) == (.9, .999) and group['eps'] == 1e-8
            and len(group['params']) == len(params), '实际AdamW配置或参数数量改变')
    if step == 0:
        require(not opt['state'], '第0步优化器已有数学更新')
    else:
        require(set(opt['state']) == set(group['params']), '优化器缺实际参数状态')
        for key, parameter in zip(group['params'], params):
            state = opt['state'][key]
            require(torch.is_tensor(state['step']) and state['step'].numel() == 1
                    and float(state['step']) == step
                    and all(torch.is_tensor(state[k]) and state[k].dtype == torch.float32
                        and tuple(state[k].shape) == tuple(parameter.shape)
                        and bool(torch.isfinite(state[k]).all()) for k in ('exp_avg', 'exp_avg_sq')),
                    '实际AdamW步数/动量状态缺失或不符')
    import random
    random.Random().setstate(payload['rng_python'])
    np.random.RandomState().set_state(payload['rng_numpy'])
    cpu = payload['rng_torch_cpu']; cuda = payload['rng_torch_cuda']
    require(torch.is_tensor(cpu) and cpu.dtype == torch.uint8 and cpu.ndim == 1 and cpu.numel() > 0
            and isinstance(cuda, list) and len(cuda) > 0
            and all(torch.is_tensor(x) and x.dtype == torch.uint8 and x.ndim == 1 and x.numel() > 0 for x in cuda),
            '完整TorchCPU/CUDA随机状态缺失')
    torch.Generator(device='cpu').set_state(cpu)


def execute(config, control, output):
    require(all(Path(p).is_absolute() for p in (config, control, output)), '配置/控制/输出必须是绝对路径')
    config, control, output = Path(config), Path(control), Path(output)
    cfg, rt = load_runtime(config)
    control, output = rt.physical(control), rt.physical(output)
    require(EXPERIMENT in control.parents and EXPERIMENT in output.parents, '独立审计目录越界')
    intent, failed = output.with_suffix('.intent.json'), output.with_suffix('.failed.json')
    require(not any(p.exists() for p in (output, intent, failed)), '已有终验/partial，不覆盖或隐式重放')
    state_path = control/'driver_state.json'; state_sha = sha(state_path); state = read(state_path)
    validate_state(state, cfg)
    require(state['protocol_sha256'] == sha(config), '控制器不是本冻结协议')
    active = process_snapshot(); require(not blocked_processes(active), '真实训练/控制器/UE尚未退出')
    output.parent.mkdir(parents=True, exist_ok=True)
    rt.write_new(intent, dict(status='started_readonly_budget_audit_not_training',
        protocol_sha256=sha(config), control_state_sha256=state_sha, actual_optimizer_updates=0,
        pid=os.getpid(), test_read=False))
    try:
        import numpy as np
        import torch
        torch.set_num_threads(1)
        require(not torch.cuda.is_available(), '预算审计必须CUDA_VISIBLE_DEVICES=-1纯CPU')
        source, _, numeric, base = rt.load_source(cfg)
        cpu_contract = rt.read(rt.checked(cfg['bounded_CPU_contract']))
        proof = read(cfg['numeric_validation_receipt_path'])
        require(proof['status'] == 'complete_three_groups_one_step_exact_full_records_verified'
                and proof['all_groups_equal'] is True and proof['protocol_sha256'] == sha(config)
                and proof['actual_diagnostic_optimizer_updates'] == 6, '原一步准入链不完整')
        first = read(control/'first_run_end_to_end_gate.json')
        require(first['status'] == 'complete_first_formal1000_full_records21_verified'
                and first['actual_updates'] == 1000 and first['checkpoints_read'] == 21
                and first['optimizer_replay'] == 0, '首正式千步完整记录门禁缺失')
        adapter_states, adapter_audits = {}, {}
        for fold in FOLDS:
            artifact = read(rt.checked(cfg['adapters'][fold])); refs = source['folds'][fold]
            require(artifact['base_R_pool'] == refs['real_pool']
                    and artifact['old_normalizer'] == refs['normalizer']
                    and artifact['quality_scale'] == refs['quality_scale']
                    and artifact['fit_external_or_S'] is False, 'adapter原输入绑定改变')
            old = read(rt.checked(refs['normalizer'])); quality = read(rt.checked(refs['quality_scale']))
            windows = rt.rows(rt.checked(refs['real_pool']))
            adapter_states[fold] = artifact['adapter']
            adapter_audits[fold] = validate_adapter(artifact['adapter'], old, quality['shape_change_scale'],
                cpu_contract['folds'][fold]['velocity_clip_99'], fold, windows)
        totals = Counter(); items = []; common = {}; checkpoint_count = 0
        for entry in state['completed_train']:
            fold, seed, group = (entry[k] for k in ('fold', 'seed', 'group'))
            run = rt.physical(entry['path'])
            require(run == control/'runs'/fold/str(seed)/group/'training', '完成run物理路径与矩阵不符')
            require(sha(run/'run_receipt.json') == entry['receipt_sha256']
                    and sha(run/'training_complete.json') == entry['complete_sha256'], '成功收据bytes改变')
            receipt = read(run/'run_receipt.json'); binding = receipt['binding']
            require(receipt['schema'] == 'bounded_velocity_full_recorded_training_run_v1'
                    and receipt['status'] == 'complete' and receipt['completed_updates'] == 1000
                    and binding['protocol_sha256'] == sha(config)
                    and {k: binding[k] for k in ('fold', 'seed', 'group')} == dict(fold=fold, seed=seed, group=group)
                    and receipt['amp'] is False and receipt['actual_dtype'] == 'float32'
                    and receipt['trainable_parameters'] == 20098 and receipt['optimizer_replay'] == 0,
                    '独立run身份/原网络容量/完整记录未完成')
            table = read(rt.checked(source['exposures']['balanced'][fold][str(seed)]))
            logs = rt.rows(run/'steps.jsonl'); counts, chain = count_run(logs, table, group)
            complete = read(run/'training_complete.json'); last = read(run/'last_checkpoint.json')
            transaction = read(run/'update_transaction.json'); manifest = read(run/'run_manifest.json')
            require(complete['schema'] == 'full_training_process_complete_v1' and complete['status'] == 'complete'
                    and complete['actual_updates'] == 1000 and complete['totals'] == counts
                    and complete['exposure_chain'] == last['exposure_chain'] == chain
                    and complete['steps_sha256'] == sha(run/'steps.jsonl')
                    and complete['manifest_sha256'] == sha(run/'run_manifest.json')
                    and complete['events_sha256'] == sha(run/'events.jsonl')
                    and complete['selection'] == 'step1000_last_no_best'
                    and receipt['full_training_record'] == sha(run/'training_complete.json')
                    and transaction == dict(status='committed', completed_updates=1000, chain_sha256=chain)
                    and manifest['binding'] == binding and manifest['test116187_sealed'] is True,
                    '完整训练日志/末事务/来源链不完整')
            require(receipt['real_window_exposures'] == counts['R_windows'] == 3000
                    and receipt['synthetic_window_exposures'] == counts['S_windows'] == 1000*int(group != 'T_R')
                    and receipt['prefetch']['yielded'] == 1000 and receipt['prefetch']['closed'] is True
                    and receipt['prefetch']['worker_alive'] is False and receipt['cache_peak_bytes'] <= 268435456,
                    '实际曝光/预取/缓存未闭合')
            intervention = validate_intervention(receipt['intervention'], group, counts,
                prefetch=receipt['prefetch'], producer_processes_absent=True)
            r_chain = hashlib.sha256(canonical([r['window_uid'] for r in table['real']]).encode()).hexdigest()
            s_chain = hashlib.sha256(canonical([r['window_uid'] for r in table['synthetic']]
                if group != 'T_R' else []).encode()).hexdigest()
            require(binding['R_window_UID_chain_sha256'] == r_chain
                    and binding['S_window_UID_chain_sha256'] == s_chain, '原R/S顺序链改变')
            reference = read(rt.checked(source['reference_R']['gated'][fold][str(seed)]['training_receipt']))
            template = numeric.make_model(seed, 'gated')
            require(base.model_sha(template) == binding['initialization_sha256']
                    == reference['binding']['initialization_sha256'], '原gated初始化来源不同')
            expected_extra = dict(schema='bounded_velocity_association_method_state_v1', group=group,
                adapter=adapter_states[fold], network='original_gated', actual_dtype='float32', original_quality_gate=True)
            require(hashlib.sha256(canonical(expected_extra).encode()).hexdigest() == binding['method_state_sha256'],
                    '训练方法状态不等于事前adapter')
            points = complete['checkpoints']
            require(len(points) == 21 and [p['completed_updates'] for p in points] == list(range(0, 1001, 50))
                    and last == points[-1], '0/每50/最终21份检查点不齐')
            for point in points:
                step = point['completed_updates']; path = run/'checkpoints'/f'step_{step:04d}.pt'
                require(Path(point['path']) == path and read(path.with_suffix('.json')) == point
                        and sha(path) == point['sha256'] and path.stat().st_size == point['bytes'],
                        '实际检查点/索引物理来源或SHA不符')
                payload = torch.load(path, map_location='cpu', weights_only=False)
                audit_payload(payload, step=step, binding=binding, extra=expected_extra,
                    chain='0'*64 if step == 0 else logs[step-1]['chain_sha256'],
                    template=template, torch=torch, np=np)
                if step == 0:
                    template.load_state_dict(payload['model'])
                    require(base.model_sha(template) == binding['initialization_sha256'],
                            '真实第0步模型不等于原初始化')
                checkpoint_count += 1
            signature = (binding['initialization_sha256'], r_chain, counts['R_pairs'], counts['R_known_pairs'])
            key = (fold, seed); require(key not in common or common[key] == signature,
                '同fold/seed三组初始化/R顺序/全部及已知pair不同')
            common[key] = signature
            totals.update(counts); totals['updates'] += 1000
            items.append(dict(fold=fold, seed=seed, group=group, actual_updates=1000, counts=counts,
                checkpoints_read_back=21, actual_step0_initialization_equal=True, intervention=intervention,
                run_receipt_sha256=entry['receipt_sha256'], last_checkpoint=last))
        require(totals['updates'] == 27000 and totals['R_windows'] == 81000
                and totals['S_windows'] == 18000 and checkpoint_count == 567 and len(common) == 9,
                '27臂实际总预算/567份检查点未闭合')
        final_processes = process_snapshot()
        require(not blocked_processes(final_processes) and sha(state_path) == state_sha,
                '审计期间生产者重新出现或控制器终态改变')
        result = dict(schema='independent_bounded_velocity27_budget_audit_v1', status=STATUS,
            protocol=dict(path=str(config), sha256=sha(config)),
            control_state=dict(path=str(state_path), sha256=state_sha),
            auditor=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
            actual_totals=dict(totals), runs=items, complete_checkpoints_read_back=checkpoint_count,
            normalizer_and_gate_audits=adapter_audits, nine_paired_three_group_exposures_equal=True,
            training_processes_absent=True, diagnostic_updates_separate=6,
            diagnostic_R_separate=18, diagnostic_S_separate=4, new_optimizer_updates=0,
            optimizer_replay=0, model_prediction=False, test_read=False,
            numerical_loss_serialization_check_not_performance_equivalence=True,
            performance_comparison_not_yet_complete=True)
        rt.write_new(output, result)
        return {k: result[k] for k in ('status', 'actual_totals', 'complete_checkpoints_read_back', 'training_processes_absent')}
    except BaseException as error:
        rt.write_new(failed, dict(status='failed_audit_preserved_sources_unchanged', error=repr(error),
            traceback=traceback.format_exc(), new_optimizer_updates=0, test_read=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    print(canonical(execute(args.config, args.control, args.output)))
