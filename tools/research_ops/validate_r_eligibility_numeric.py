"""真实R资格mask CPU/CUDA一步与完整记录准入；20更新上限，不执行正式训练。"""
import argparse,copy,hashlib,math,os,random,sys,traceback
from collections.abc import Mapping
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import r_eligibility_training_runtime as rt
import r_eligibility_train as trainer
STATUS=trainer.NUMERIC_STATUS
RNG_KEYS=('rng_python','rng_numpy','rng_torch_cpu','rng_torch_cuda')

def tree_equal(a,b,torch,np):
    if torch.is_tensor(a) or torch.is_tensor(b):return torch.is_tensor(a) and torch.is_tensor(b) and a.dtype==b.dtype and tuple(a.shape)==tuple(b.shape) and torch.equal(a.detach().cpu(),b.detach().cpu())
    if isinstance(a,np.ndarray) or isinstance(b,np.ndarray):return isinstance(a,np.ndarray) and isinstance(b,np.ndarray) and a.dtype==b.dtype and a.shape==b.shape and np.array_equal(a,b)
    if isinstance(a,Mapping) or isinstance(b,Mapping):return isinstance(a,Mapping) and isinstance(b,Mapping) and a.keys()==b.keys() and all(tree_equal(a[k],b[k],torch,np) for k in a)
    if isinstance(a,(list,tuple)) or isinstance(b,(list,tuple)):return type(a) is type(b) and len(a)==len(b) and all(tree_equal(x,y,torch,np) for x,y in zip(a,b))
    if type(a) is not type(b):return False
    return a==b

def rng_snapshot(torch,np):return dict(rng_python=copy.deepcopy(random.getstate()),rng_numpy=copy.deepcopy(np.random.get_state()),rng_torch_cpu=torch.get_rng_state().clone(),rng_torch_cuda=[v.clone() for v in torch.cuda.get_rng_state_all()])

def restore_rng(state,torch,np):
    random.setstate(state['rng_python']);np.random.set_state(state['rng_numpy']);torch.set_rng_state(state['rng_torch_cpu']);torch.cuda.set_rng_state_all(state['rng_torch_cuda'])

def audit_checkpoint(path,step,binding,extra,model,opt,rng,chain,torch,np):
    side=rt.read(path.with_suffix('.json'));rt.require(Path(rt.checked(side))==path,'检查点sidecar来源/SHA不同')
    saved=torch.load(path,map_location='cpu',weights_only=False);eq=lambda a,b:tree_equal(a,b,torch,np)
    rt.require(saved['schema']=='full_training_checkpoint_v1' and saved['completed_updates']==step
        and eq(saved['binding'],binding) and eq(saved['extra'],extra) and saved['exposure_chain']==chain,
        '0/1检查点绑定/方法/曝光链不同')
    rt.require(eq(saved['model'],model) and eq(saved['optimizer'],opt),'完整模型/AdamW状态不逐值一致')
    rt.require(all(k in saved for k in RNG_KEYS) and saved['rng_torch_cuda'] is not None
        and eq({k:saved[k] for k in RNG_KEYS},rng),'Python/NumPy/Torch CPU/CUDA RNG状态不完整或不同')
    return dict(path=str(path),sha256=rt.sha(path),completed_updates=step,model_equal=True,optimizer_equal=True,all_RNG_equal=True)


def cases():
    return [dict(variant=variant, device=device, regime=regime) for variant in ('alltrue_original_BCE', 'actual_mask')
        for device in ('cpu', 'cuda:0') for regime in ('R', 'RS')]+[
        dict(variant='empty_stress', device=device, regime='R') for device in ('cpu', 'cuda:0')]


def manual_masked_r_loss(model, windows, bindings):
    """独立手写原全known拼接/逐候选BCE与每窗masked mean；不调用候选方法。"""
    import torch
    from torch.nn import functional as F
    counts = [len(w['labels']) for w in windows]; rt.require(len(counts) == 3 and all(n > 0 for n in counts), '原3R known不得裁剪')
    device = next(model.parameters()).device; x = torch.cat([w['x'] for w in windows]).to(device); y = torch.cat([w['labels'] for w in windows]).to(device)
    logits = model(x).reshape(-1); pairs = F.binary_cross_entropy_with_logits(logits, y, reduction='none').split(counts); means = []
    for pair, binding in zip(pairs, bindings):
        mask = binding['known_scoring_eligible']; rt.require(len(mask) == pair.numel() and all(type(v) is bool for v in mask), '手写资格向量不同')
        if all(mask): means.append(pair.mean())
        elif any(mask): means.append(pair.index_select(0, torch.tensor([i for i, keep in enumerate(mask) if keep], dtype=torch.long, device=pair.device)).mean())
        else: means.append((pair*0.).sum())
    return torch.stack(means).mean()


def expected_effective_counts(batch):
    result = dict(R_effective_known_pairs=0, R_effective_positive_pairs=0, R_effective_negative_pairs=0,
        R_effective_unknown_pairs=0, R_scoring_eligible_unknown_pairs=0, R_masked_out_known_pairs=0, R_zero_effective_windows=0, R_effective_nonempty_windows=0)
    for window in batch['real']:
        binding = window['eligibility_binding']; labels = binding['known_labels']; mask = binding['known_scoring_eligible']
        kept = sum(mask); positives = sum(keep and label == 1 for keep, label in zip(mask, labels))
        result['R_effective_known_pairs'] += kept; result['R_effective_positive_pairs'] += positives
        result['R_effective_negative_pairs'] += kept-positives; result['R_masked_out_known_pairs'] += len(labels)-kept
        result['R_zero_effective_windows'] += int(kept == 0); result['R_effective_nonempty_windows'] += int(kept > 0)
        result['R_scoring_eligible_unknown_pairs'] += sum(label is None and keep for label, keep in zip(binding['all_labels'], binding['all_scoring_eligible']))
    return result


def persist_group_audit(protocol_sha256, case, group, run_dir, writer):
    """只在完整比较成功后落盘；不执行新数值，也不自动恢复/重放成功组。"""
    rt.require(group['manual_updates'] == group['recorded_updates'] == 1 and group['R_windows'] == 6
        and group['S_windows'] == 2*int(case['regime'] == 'RS')
        and all(group[k] is True for k in ('per_parameter_gradients_exact', 'all_RNG_exact', 'loss_model_AdamW_exact'))
        and [c['completed_updates'] for c in group['checkpoints']] == [0, 1], '不准为未闭合group写成功证明')
    def reference(path): return dict(path=str(rt.physical(path)), sha256=rt.sha(path))
    proof = dict(schema='R_candidate_eligibility_numeric_group_audit_v1', status='complete_one_manual_and_recorded_step_all_exact',
        protocol_sha256=protocol_sha256, case=copy.deepcopy(case), group_result=group, checkpoints=group['checkpoints'],
        record_run_receipt=reference(run_dir/'run_receipt.json'), record_steps=reference(run_dir/'steps.jsonl'),
        manual_optimizer_updates=1, recorded_optimizer_updates=1, actual_diagnostic_optimizer_updates=2,
        diagnostic_R_windows=6, diagnostic_S_windows=2*int(case['regime'] == 'RS'), formal_optimizer_updates=0,
        checks=dict(input_batch_exact=True, loss_exact=True, per_parameter_gradients_exact=True, model_exact=True, AdamW_exact=True,
            all_four_RNG_exact=True, step0_step1_checkpoint_exact=True, step_chain_exact=True, raw_and_effective_counts_exact=True),
        automatic_resume_or_replay=False, test_read=False)
    target = run_dir.parent/'group_audit.json'; writer(target, proof)
    return reference(target)


def preflight(config, output, config_sha=None):
    cfg = rt.validate_protocol(config); rt.require(cfg['numeric_plan'] == trainer.numeric_plan(), '有限数值预算必须结果前冻结')
    output = rt.physical(output); rt.require(rt.EXPERIMENT in output.parents and not output.exists(), '独立准入新attempt，成功/partial不覆盖')
    rt.require(Path(cfg['numeric_admission']['path']) == output/'receipt.json', '本轮准入收据输出须冻结')
    if config_sha is not None: rt.require(rt.sha(config) == config_sha, '配置SHA调用值不同')
    return cfg, dict(status='readonly_R_eligibility_numeric_preflight', **trainer.numeric_plan(), groups=cases(), test_read=False)


def run(config, output, config_sha=None):
    cfg, flight = preflight(config, output, config_sha)
    import numpy as np, torch
    from training_journal import write_new
    rt.require(torch.__version__ == '2.6.0+cu124' and torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 2147483648, '冻结研究Torch/CUDA/2GiB余量不足')
    torch.set_num_threads(1); torch.use_deterministic_algorithms(True); output = rt.physical(output); output.mkdir(parents=True)
    write_new(output/'preflight.json', flight); write_new(output/'started.json', dict(status='started_20_diagnostic_updates_not_formal_training',
        protocol_sha256=rt.sha(config), planned_numeric=trainer.numeric_plan(), created_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid()))
    manual_updates = 0; recorded_updates = 0; reports = []; group_audits = []; shared_actual_R = {}; shared_init = None
    current_case = None; current_manual_returned = False; current_recorded_returned = False
    try:
        fold, seed = rt.FOLDS[0], rt.SEEDS[0]
        for case in cases():
            current_case = copy.deepcopy(case); current_manual_returned = False; current_recorded_returned = False
            variant, device, regime = case['variant'], case['device'], case['regime']
            random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
            ctx = rt.prepare(config, fold, seed, regime); ctx['diagnostic_only_mask_override_authorized'] = True
            definitions = trainer.prepare_variant(ctx, variant); batch = rt.batch(ctx, 0)
            model = rt.new_model(ctx, device=device); optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
            if variant == 'empty_stress': trainer.initialize_empty_stress_optimizer(optimizer, torch)
            spec, extra = trainer.diagnostic_spec_extra(ctx, model, True, variant, definitions)
            initial_model, initial_optimizer = copy.deepcopy(model.state_dict()), copy.deepcopy(optimizer.state_dict()); initial_rng = rng_snapshot(torch, np)
            eq = lambda a, b: tree_equal(a, b, torch, np)
            init_sha = ctx['base'].model_sha(model)
            if shared_init is None: shared_init = init_sha
            rt.require(init_sha == shared_init and sum(p.numel() for p in model.parameters()) == 14593, '原初始化/14593参数跨设备或组别不同')
            if regime == 'R' and variant == 'actual_mask': shared_actual_R[device] = copy.deepcopy((batch['r'], batch['real']))
            if regime == 'RS' and variant == 'actual_mask': rt.require(eq(shared_actual_R[device], (batch['r'], batch['real'])), 'R/RS真实同R顺序/资格不同')
            optimizer.zero_grad(set_to_none=True)
            rloss = ctx['numeric'].domain_loss(model, batch['real']) if variant == 'alltrue_original_BCE' else manual_masked_r_loss(model, batch['real'], [w['eligibility_binding'] for w in batch['real']])
            sloss = ctx['numeric'].domain_loss(model, batch['synthetic']) if regime == 'RS' else None
            total = rloss if sloss is None else rloss+sloss/3; rt.require(bool(torch.isfinite(total)), '手写目标非有限'); total.backward()
            gradients = {name: p.grad.detach().cpu().clone() for name, p in model.named_parameters() if p.grad is not None}
            rt.require(len(gradients) == len(list(model.parameters())), '手写路径缺参数梯度图')
            if variant == 'empty_stress':
                rt.require(total.item() == 0. and all(torch.count_nonzero(g).item() == 0 for g in gradients.values()), '全空stress必须zero梯度')
                for p in model.parameters(): p.grad = torch.zeros_like(p)  # 独立显式zero-grad AdamW参考，无额外step。
            flat = torch.cat([p.grad.detach().reshape(-1) for p in model.parameters()]); rt.require(bool(torch.isfinite(flat).all()), '手写梯度非有限')
            grad_l2 = float(torch.linalg.vector_norm(flat)); optimizer.step(); manual_updates += 1; current_manual_returned = True; final_rng = rng_snapshot(torch, np)
            if variant == 'empty_stress': rt.require(any(not eq(initial_model[k], v) for k, v in model.state_dict().items()), '非零moment/weight_decay stress必须发生真实AdamW参数变化')
            restore_rng(initial_rng, torch, np); capture = {}; run_dir = output/variant/device.replace(':', '_')/regime/'recorded'
            receipt = trainer.run(config, run_dir, fold, seed, regime, diagnostic_updates=1, device=device, diagnostic_variant=variant, diagnostic_capture=capture)
            recorded_updates += receipt['completed_updates']; current_recorded_returned = True; rt.require(receipt['completed_updates'] == 1, '记录路径必须仅1步')
            rt.require(eq(batch, capture['batch']) and eq(gradients, capture['gradients']), '实际原R/S batch或逐参数梯度不逐值相同')
            logged = ctx['eligibility_oldrt'].rows(run_dir/'steps.jsonl'); rt.require(len(logged) == 1, '单步记录行数不同'); row = logged[0]
            rt.require(row['loss'] == float(total.detach()) and row['real_loss'] == float(rloss.detach())
                and row['synthetic_loss'] == (None if sloss is None else float(sloss.detach())) and row['grad_l2'] == grad_l2 and row['learning_rates'] == [.001], '实际loss/grad/LR记录不逐值相同')
            for key, value in expected_effective_counts(batch).items(): rt.require(row[key] == value, '有效监督计数不同：'+key)
            for key, value in dict(R_pairs=sum(w['candidate_pairs'] for w in batch['real']), R_known_pairs=sum(w['known_pairs'] for w in batch['real']),
                    S_pairs=sum(w['candidate_pairs'] for w in batch['synthetic']), S_known_pairs=sum(w['known_pairs'] for w in batch['synthetic'])).items(): rt.require(row[key] == value, '原all/known计数不同')
            clean = {k: v for k, v in row.items() if k != 'chain_sha256'}; chain = hashlib.sha256(('0'*64+rt.canonical(clean)).encode()).hexdigest()
            rt.require(chain == row['chain_sha256'], '含mask记录的逐步完整SHA链不同')
            audits = [audit_checkpoint(run_dir/f'checkpoints/step_{step:04d}.pt', step, spec['binding'], extra, model_state, opt_state, rng, exposure_chain, torch, np)
                for step, model_state, opt_state, rng, exposure_chain in [(0, initial_model, initial_optimizer, initial_rng, '0'*64), (1, model.state_dict(), optimizer.state_dict(), final_rng, chain)]]
            rt.require(eq(final_rng, rng_snapshot(torch, np)), '手写/记录四RNG不逐值相同')
            group = dict(**case, fold=fold, seed=seed, manual_updates=1, recorded_updates=1, R_windows=6, S_windows=2*int(regime == 'RS'),
                real_loss=float(rloss.detach()), synthetic_loss=None if sloss is None else float(sloss.detach()), grad_l2=grad_l2,
                effective_counts=expected_effective_counts(batch), checkpoints=audits, record_sha256=rt.sha(run_dir/'steps.jsonl'),
                per_parameter_gradients_exact=True, all_RNG_exact=True, loss_model_AdamW_exact=True, diagnostic_variant_declared=True)
            proof = persist_group_audit(rt.sha(config), case, group, run_dir, write_new)
            group_audits.append(proof); reports.append(group); current_case = None
        rt.require(manual_updates == recorded_updates == 10 and sum(g['R_windows'] for g in reports) == 60 and sum(g['S_windows'] for g in reports) == 8, '有限20步/60R8S预算不同')
        result = dict(schema='R_candidate_eligibility_numeric_admission_v1', status=STATUS, protocol_sha256=rt.sha(config), formal_optimizer_updates=0,
            actual_diagnostic_optimizer_updates=20, manual_optimizer_updates=10, recorded_optimizer_updates=10, diagnostic_R_windows=60, diagnostic_S_windows=8,
            actual_CPU_and_CUDA_numeric_verified=True, full_record_contract_verified=True, all_groups_equal=True,
            CPU_and_CUDA_actual_model_steps_verified=True,
            alltrue_original_BCE_compatible=True, actual_mask_independent_BCE_exact=True, empty_nonzero_moments_weight_decay_zero_grad_exact=True,
            matched_control_reuse_numerical_compatibility_verified=True, test_read=False, groups=reports, group_audits=group_audits,
            all_ten_groups_individually_persisted=True, new_tracking=0, new_TrackEval=0)
        write_new(output/'receipt.json', result); return result
    except BaseException as error:
        write_new(output/'failed.json', dict(status='failed_preserved_no_implicit_replay', error=repr(error), traceback=traceback.format_exc(),
            manual_optimizer_updates_returned=manual_updates, recorded_optimizer_updates_returned=recorded_updates,
            completed_group_audits=group_audits, completed_group_count=len(group_audits), unclosed_current_case=current_case,
            current_case_manual_update_returned=current_manual_returned if current_case is not None else None,
            current_case_recorded_update_returned=current_recorded_returned if current_case is not None else None,
            successful_groups_not_implicitly_replayed=True, automatic_resume_implemented=False,
            uncommitted_effects_not_guessed=True, formal_optimizer_updates=0, protocol_sha256=rt.sha(config), test_read=False)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--config-sha256'); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    print(rt.canonical(run(args.config, args.output, args.config_sha256) if args.execute else preflight(args.config, args.output, args.config_sha256)[1]))
