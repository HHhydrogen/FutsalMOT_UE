"""自由状态R窗口实际CUDA一步准入；复用原强motion数学与完整记录。"""
import argparse
from collections.abc import Mapping
import copy
from datetime import datetime, timezone
import importlib
import json
import math
import os
from pathlib import Path
import random
import sys
import traceback

sys.path.insert(0, str(Path(__file__).parent))

GROUPS = ('R', 'RS')
STATUS = 'complete_R_RS_one_step_exact_full_records_verified'
RNG_KEYS = ('rng_python', 'rng_numpy', 'rng_torch_cpu', 'rng_torch_cuda')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def tree_equal(left, right, *, torch=None, np=None):
    """严格比较模型、优化器和完整随机状态，不设浮点容差。"""
    if torch is not None and (torch.is_tensor(left) or torch.is_tensor(right)):
        return (torch.is_tensor(left) and torch.is_tensor(right)
                and left.dtype == right.dtype and tuple(left.shape) == tuple(right.shape)
                and torch.equal(left.detach().cpu(), right.detach().cpu()))
    if np is not None and (isinstance(left, np.ndarray) or isinstance(right, np.ndarray)):
        return (isinstance(left, np.ndarray) and isinstance(right, np.ndarray)
                and left.dtype == right.dtype and left.shape == right.shape
                and np.array_equal(left, right))
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return (isinstance(left, Mapping) and isinstance(right, Mapping)
                and left.keys() == right.keys()
                and all(tree_equal(left[k], right[k], torch=torch, np=np) for k in left))
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        return (type(left) is type(right) and len(left) == len(right)
                and all(tree_equal(a, b, torch=torch, np=np) for a, b in zip(left, right)))
    if type(left) is not type(right):
        return False
    if isinstance(left, float) and (not math.isfinite(left) or not math.isfinite(right)):
        return False
    return left == right


def rng_snapshot(torch, np):
    return dict(rng_python=copy.deepcopy(random.getstate()),
                rng_numpy=copy.deepcopy(np.random.get_state()),
                rng_torch_cpu=torch.get_rng_state().clone(),
                rng_torch_cuda=[v.clone() for v in torch.cuda.get_rng_state_all()])


def restore_rng(state, torch, np):
    require(set(state) == set(RNG_KEYS), '必须恢复四类完整随机状态')
    random.setstate(state['rng_python'])
    np.random.set_state(state['rng_numpy'])
    torch.set_rng_state(state['rng_torch_cpu'])
    torch.cuda.set_rng_state_all(state['rng_torch_cuda'])


def first_batch(rt, context, group):
    """只取实际首批并关闭有界预取资源，不让诊断后台遗留工作。"""
    iterator = iter(rt.batches(context, group, limit=1))
    try:
        batch = next(iterator)
        require(batch['index'] == 0 and len(batch['r']) == len(batch['real']) == 3,
                '首批必须为三个新来源R窗口')
        expected_s = 0 if group == 'R' else 1
        require(len(batch['s']) == len(batch['synthetic']) == expected_s,
                '诊断R/RS组窗口预算不同')
        return batch
    finally:
        close = getattr(iterator, 'close', None)
        if close is not None:
            close()


def preflight(config, output, config_sha256=None, *, runtime=None):
    rt = runtime or importlib.import_module('state_aligned_training_runtime')
    config, output = Path(config), Path(output)
    if config_sha256 is not None:
        require(rt.sha(config) == config_sha256, '冻结协议SHA与调用值不同')
    cfg = rt.validate_protocol(config)
    experiment = Path(rt.EXPERIMENT)
    output = rt.physical(output)
    require(experiment in output.parents, '数值诊断只能写入独立自由状态R实验目录')
    require(not output.exists(), '已有诊断或partial，不覆盖或隐式重放')
    require(Path(cfg['numeric_validation_receipt_path']) == output/'receipt.json',
            '诊断收据必须绑定事前协议路径')
    return rt, cfg, output, dict(status='readonly_state_aligned_learning_numeric_preflight',
        protocol_sha256=rt.sha(config), groups=list(GROUPS),
        planned_diagnostic_optimizer_updates=4, formal_optimizer_updates=0,
        GPU_model_loaded=False, test_read=False)


def _audit_checkpoint(rt, path, *, step, binding, extra, model, optimizer,
                      rng, chain, torch, np):
    side = rt.read(path.with_suffix('.json'))
    require(Path(rt.checked(side)) == path, '检查点来源或SHA改变')
    saved = torch.load(path, map_location='cpu', weights_only=False)
    equal = lambda a, b: tree_equal(a, b, torch=torch, np=np)
    require(saved['schema'] == 'full_training_checkpoint_v1'
            and saved['completed_updates'] == step
            and equal(saved['binding'], binding) and equal(saved['extra'], extra)
            and saved['exposure_chain'] == chain,
            '完整检查点步数/绑定/方法状态/曝光链不符')
    require(equal(saved['model'], model) and equal(saved['optimizer'], optimizer),
            '完整模型或优化器读回不逐值相同')
    require(all(k in saved for k in RNG_KEYS) and saved['rng_torch_cuda'] is not None
            and equal({k: saved[k] for k in RNG_KEYS}, rng),
            '检查点Python/NumPy/TorchCPU/CUDA随机状态不完整或不相同')
    return dict(path=str(path), sha256=rt.sha(path), completed_updates=step,
                model_equal=True, optimizer_equal=True, all_RNG_equal=True)


def verify(config, output, config_sha256=None):
    rt, cfg, output, flight = preflight(config, output, config_sha256)
    from training_journal import write_new
    output.mkdir(parents=True)
    write_new(output/'preflight.json', flight)
    write_new(output/'started.json', dict(status='started_numeric_diagnostic_not_formal_training',
        protocol_sha256=rt.sha(config), created_utc=datetime.now(timezone.utc).isoformat(),
        pid=os.getpid(), formal_optimizer_updates=0, planned_diagnostic_optimizer_updates=4))
    results, committed_manual = [], 0
    try:
        import numpy as np
        import torch
        from recorded_association_loop import train as recorded_train
        require(torch.__version__ == '2.6.0+cu124' and torch.cuda.is_available(),
                '必须使用冻结真实CUDA环境，CPU夹具不能成为学习准入')
        require(torch.cuda.mem_get_info()[0] > 2147483648, 'CUDA可用余量不足2GiB')
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        fold, seed = rt.FOLDS[0], rt.SEEDS[0]
        shared_real, shared_initialization = None, None
        for group in GROUPS:
            random.seed(seed); np.random.seed(seed)
            torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
            manual_context = rt.prepare(config, fold, seed, group)
            recorded_context = rt.prepare(config, fold, seed, group)
            manual_batch = first_batch(rt, manual_context, group)
            recorded_batch = first_batch(rt, recorded_context, group)
            equal = lambda a, b: tree_equal(a, b, torch=torch, np=np)
            require(equal(manual_batch, recorded_batch), '独立缓存首批特征/标签/实际窗口或顺序不一致')
            if shared_real is None:
                shared_real = copy.deepcopy((recorded_batch['r'], recorded_batch['real']))
            else:
                require(equal(shared_real, (recorded_batch['r'], recorded_batch['real'])),
                        '新R与RS首步真实窗口/原特征/标签必须逐值相同')
            manual = rt.new_model(manual_context, seed)
            model = rt.new_model(recorded_context, seed)
            require(equal(manual.state_dict(), model.state_dict()), '两份模型初始化不逐值一致')
            initial_model = copy.deepcopy(model.state_dict())
            initialization_sha256 = recorded_context['base'].model_sha(model)
            if shared_initialization is None:
                shared_initialization = initialization_sha256
            require(initialization_sha256 == shared_initialization
                    and sum(p.numel() for p in model.parameters()) == 14593,
                    'R/RS初始参数必须同原强motion14593参数，不换容量')
            manual_opt = torch.optim.AdamW(manual.parameters(), lr=.001, weight_decay=.0001)
            optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
            initial_optimizer = copy.deepcopy(optimizer.state_dict())
            spec = rt.spec(recorded_context, model, seed, group, diagnostic=True)
            require(spec['binding'].get('diagnostic_only_one_update_not_formal_training') is True
                    and spec['binding']['protocol_sha256'] == rt.sha(config)
                    and spec['binding']['initialization_sha256'] == initialization_sha256
                    and spec['S_per_update'] == (0 if group == 'R' else 1)
                    and spec['R_per_update'] == 3 and spec['updates'] == 1000
                    and spec['checkpoint_interval'] == 50
                    and all(p.dtype == torch.float32 and p.is_cuda for p in model.parameters()),
                    '新来源R实际记录诊断身份或预算不正确')
            extra = rt.extra(recorded_context)
            begin_rng = rng_snapshot(torch, np)
            restore_rng(begin_rng, torch, np)
            manual_opt.zero_grad(set_to_none=True)
            r_loss = manual_context['numeric'].domain_loss(manual, manual_batch['real'])
            s_loss = (manual_context['numeric'].domain_loss(manual, manual_batch['synthetic'])
                      if manual_batch['s'] else None)
            loss = r_loss+s_loss/3 if s_loss is not None else r_loss
            require(bool(torch.isfinite(loss)), '手写损失非有限')
            loss.backward()
            gradients = [p.grad.detach().reshape(-1) for p in manual.parameters() if p.grad is not None]
            require(gradients and bool(torch.isfinite(torch.cat(gradients)).all()), '手写梯度非有限')
            grad_l2 = float(torch.linalg.vector_norm(torch.cat(gradients)))
            manual_opt.step()
            committed_manual += 1
            expected_rng = rng_snapshot(torch, np)
            restore_rng(begin_rng, torch, np)
            run = output/group
            complete = recorded_train(run, spec, model, optimizer, [recorded_batch],
                recorded_context['numeric'].domain_loss, checkpoint_extra=extra, diagnostic_updates=1)
            logged = rt.rows(run/'steps.jsonl')
            require(complete == dict(status='diagnostic_only', completed_updates=1)
                    and len(logged) == 1, '实际循环未恰好提交一诊断步')
            row = logged[0]
            require(row['loss'] == float(loss.detach()) and row['real_loss'] == float(r_loss.detach())
                    and row['synthetic_loss'] == (float(s_loss.detach()) if s_loss is not None else None)
                    and row['grad_l2'] == grad_l2 and row['learning_rates'] == [.001]
                    and row['real'] == recorded_batch['r'] and row['synthetic'] == recorded_batch['s'],
                    '记录循环分域损失/LR/梯度/实际窗口不逐值相同')
            require(equal(manual.state_dict(), model.state_dict())
                    and equal(manual_opt.state_dict(), optimizer.state_dict())
                    and equal(expected_rng, rng_snapshot(torch, np)),
                    '实际记录接入改变全部模型/优化器或随机状态')
            require(row['R_pairs'] == sum(x['candidate_pairs'] for x in recorded_batch['real'])
                    and row['R_known_pairs'] == sum(x['known_pairs'] for x in recorded_batch['real'])
                    and row['S_pairs'] == sum(x['candidate_pairs'] for x in recorded_batch['synthetic'])
                    and row['S_known_pairs'] == sum(x['known_pairs'] for x in recorded_batch['synthetic']),
                    '实际全部/已知pair记录改变')
            unhashed = {k: v for k, v in row.items() if k != 'chain_sha256'}
            import hashlib
            chain = hashlib.sha256(('0'*64+rt.canonical(unhashed)).encode()).hexdigest()
            require(row['chain_sha256'] == chain, '诊断步曝光链不完整')
            audits = []
            for step, state_model, state_opt, rng, expected_chain in (
                    (0, initial_model, initial_optimizer, begin_rng, '0'*64),
                    (1, model.state_dict(), optimizer.state_dict(), expected_rng, chain)):
                audits.append(_audit_checkpoint(rt, run/'checkpoints'/f'step_{step:04d}.pt',
                    step=step, binding=spec['binding'], extra=extra, model=state_model,
                    optimizer=state_opt, rng=rng, chain=expected_chain, torch=torch, np=np))
            last = rt.read(run/'last_checkpoint.json')
            require(last['completed_updates'] == 1 and last['exposure_chain'] == chain
                    and not (run/'training_complete.json').exists(), '诊断不得生成正式千步完成收据')
            results.append(dict(group=group, fold=fold, seed=seed,
                initialization_sha256=initialization_sha256,
                batch_equal=True, model_equal=True, optimizer_equal=True, all_RNG_equal=True,
                full_checkpoints=audits, loss=float(loss.detach()), real_loss=float(r_loss.detach()),
                synthetic_loss=float(s_loss.detach()) if s_loss is not None else None,
                grad_l2=grad_l2, diagnostic_optimizer_updates=2,
                diagnostic_R_windows=6, diagnostic_S_windows=0 if group == 'R' else 2))
        receipt = dict(status=STATUS, protocol_sha256=rt.sha(config), all_groups_equal=True,
            actual_diagnostic_optimizer_updates=4, diagnostic_R_windows=12, diagnostic_S_windows=2,
            formal_optimizer_updates=0, full1000_integration_verified=False,
            next_gate='first_formal1000_and21_full_checkpoints_before_remaining17',
            R_RS_same_real_first_batch_and_initialization=True,
            original_motion_augmentation=False, domain_loss_reduction='mean_of_window_known_pair_BCE_means',
            results=results, test_read=False, images_copied=False)
        write_new(output/'receipt.json', receipt)
        return receipt
    except BaseException as error:
        recorded_rows = {}
        for group in GROUPS:
            path = output/group/'steps.jsonl'
            if path.exists():
                recorded_rows[group] = len(rt.rows(path))
        write_new(output/'failed.json', dict(status='failed_preserved_no_replay',
            error=repr(error), traceback=traceback.format_exc(),
            manual_optimizer_calls_returned=committed_manual,
            recorded_committed_rows=recorded_rows,
            uncommitted_optimizer_effects_not_guessed=True, formal_optimizer_updates=0,
            protocol_sha256=rt.sha(config), test_read=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config-sha256')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    value = (verify(args.config, args.output, args.config_sha256) if args.execute
             else preflight(args.config, args.output, args.config_sha256)[3])
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))
