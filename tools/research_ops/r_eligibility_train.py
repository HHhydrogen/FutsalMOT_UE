"""独立R资格mask单臂入口；正式仅CUDA1000，诊断覆盖另记且不冒充真实mask。"""
from copy import deepcopy
import argparse
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
import r_eligibility_training_runtime as rt
import r_candidate_eligibility_method as method

NUMERIC_STATUS = 'complete_R_candidate_eligibility_CPU_CUDA_full_record_numeric_admission'
VARIANTS = ('alltrue_original_BCE', 'actual_mask', 'empty_stress')


def numeric_plan():
    return dict(schema='R_eligibility_numeric_plan_v1', devices=['cpu', 'cuda:0'], variants=list(VARIANTS),
        compatibility_and_actual_regimes=['R', 'RS'], empty_stress_regimes=['R'], diagnostic_optimizer_updates=20,
        manual_optimizer_updates=10, recorded_optimizer_updates=10, diagnostic_R_windows=60, diagnostic_S_windows=8,
        empty_stress_optimizer_state=dict(step=7, exp_avg=.125, exp_avg_sq=.25), formal_optimizer_updates=0)


def validate_request(cfg, diagnostic_updates, device, variant, capture=None):
    rt.require(cfg['numeric_plan'] == numeric_plan(), '必须事前冻结有限20诊断更新/60R8S及合成stress初态')
    rt.require(device in ('cpu', 'cuda:0') and variant in VARIANTS, '只允许明确设备/诊断变体')
    if diagnostic_updates is None:
        rt.require(device == 'cuda:0' and variant == 'actual_mask' and capture is None, '正式必须真实mask/CUDA1000，无诊断覆盖')
    else: rt.require(diagnostic_updates == 1, '诊断只能明示一步，不能缩减正式预算')


def prepare_variant(ctx, variant):
    """仅诊断首三R的内存覆盖；保留原sidecar引用并明确虚拟覆盖来源，不改源文件。"""
    rt.require(variant in VARIANTS, '未知诊断变体')
    definitions = []
    if variant == 'actual_mask': return definitions
    rt.require(ctx.get('diagnostic_only_mask_override_authorized') is True, '覆盖仅用于事前单步诊断')
    for uid in dict.fromkeys(row['window_uid'] for row in ctx['table']['real'][:3]):
        original = ctx['eligibility_bindings'][uid]; body = deepcopy({k: v for k, v in original.items() if k != 'binding_sha256'})
        value = variant == 'alltrue_original_BCE'; mask = [value]*len(body['all_labels'])
        declaration = dict(schema='numeric_only_virtual_eligibility_override_v1', variant=variant, window_uid=uid,
            original_binding_sha256=original['binding_sha256'], original_sidecar_sha256=original['sidecar_sha256'],
            scoring_mask=mask, source_files_changed=False, optimizer_updates_to_create_override=0)
        body['all_scoring_eligible'] = mask; body['known_scoring_eligible'] = [mask[i] for i in body['known_indices']]
        body['accounting'] = method.label_counts(body['all_labels'], mask); body['sidecar_sha256'] = rt.digest(declaration)
        body['numeric_only_override'] = declaration; bound = dict(body, binding_sha256=rt.digest(body)); method.checked_binding(bound)
        ctx['eligibility_bindings'][uid] = bound; definitions.append(dict(declaration, override_binding_sha256=bound['binding_sha256']))
    return definitions


def initialize_empty_stress_optimizer(optimizer, torch):
    """构造已登记非零moment初态；没有warmup更新，checkpoint0显式记录step7。"""
    rt.require(not optimizer.state, '合成stress只能从空AdamW状态构造，不能覆盖真实动量')
    for group in optimizer.param_groups:
        rt.require(group['lr'] == .001 and group['weight_decay'] == .0001 and group['amsgrad'] is False, '固定AdamW条件不同')
        for parameter in group['params']:
            optimizer.state[parameter] = dict(step=torch.tensor(7., dtype=torch.float32),
                exp_avg=torch.full_like(parameter, .125), exp_avg_sq=torch.full_like(parameter, .25))


def diagnostic_spec_extra(ctx, model, diagnostic, variant, definitions):
    spec = rt.spec(ctx, model, diagnostic=diagnostic); extra = rt.extra(ctx)
    if diagnostic:
        extra = dict(extra, numeric_only_variant=variant, numeric_only_virtual_mask_overrides=definitions,
            synthetic_stress_moments=numeric_plan()['empty_stress_optimizer_state'] if variant == 'empty_stress' else None)
        spec['binding'].update(diagnostic_mask_variant=variant, method_state_sha256=rt.digest(extra))
    return spec, extra


def check_numeric_admission(config, cfg):
    admission = rt.validate_training_admission(config, cfg)
    receipt = rt.read_ref(admission['numeric_validation'])
    rt.require(receipt['status'] == NUMERIC_STATUS and receipt['protocol_sha256'] == rt.sha(config)
        and receipt['formal_optimizer_updates'] == 0 and receipt['actual_diagnostic_optimizer_updates'] == 20
        and receipt['diagnostic_R_windows'] == 60 and receipt['diagnostic_S_windows'] == 8
        and receipt['all_groups_equal'] is True and receipt['actual_CPU_and_CUDA_numeric_verified'] is True
        and receipt['full_record_contract_verified'] is True and receipt['test_read'] is False, '缺本轮真实20步CPU/CUDA/完整记录准入，不接受旧CE或aligned收据')
    return receipt


def run(config, output, fold, seed, regime, diagnostic_updates=None, device='cuda:0', diagnostic_variant='actual_mask', diagnostic_capture=None):
    import torch
    from training_journal import write_new
    started = time.perf_counter(); ctx = rt.prepare(config, fold, seed, regime); cfg = ctx['eligibility_cfg']
    validate_request(cfg, diagnostic_updates, device, diagnostic_variant, diagnostic_capture)
    if diagnostic_updates is None: check_numeric_admission(config, cfg)
    rt.require(diagnostic_variant != 'empty_stress' or regime == 'R', '全空stress仅纯R，不混入S梯度')
    rt.require(torch.__version__ == '2.6.0+cu124' and torch.cuda.is_available(), '冻结研究Torch/CUDA环境不同')
    if device == 'cuda:0': rt.require(torch.cuda.mem_get_info()[0] > 2147483648, '保留至少2GiB VRAM')
    torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
    output = rt.physical(output); rt.require(rt.EXPERIMENT in output.parents and not output.exists(), '本轮新独立attempt才能写入，不覆盖partial')
    diagnostic = diagnostic_updates is not None
    if diagnostic: ctx['diagnostic_only_mask_override_authorized'] = True
    definitions = prepare_variant(ctx, diagnostic_variant); model = rt.new_model(ctx, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    if diagnostic_variant == 'empty_stress': initialize_empty_stress_optimizer(optimizer, torch)
    spec, extra = diagnostic_spec_extra(ctx, model, diagnostic, diagnostic_variant, definitions)
    handles = []
    if diagnostic_capture is not None:
        diagnostic_capture['gradients'] = {}
        for name, parameter in model.named_parameters():
            handles.append(parameter.register_hook(lambda gradient, key=name: diagnostic_capture['gradients'].__setitem__(key, gradient.detach().cpu().clone())))
    from ordered_prefetch import OrderedPrefetch
    from r_eligibility_recorded_loop import train as recorded
    def load(index):
        value = rt.batch(ctx, index)
        if diagnostic_capture is not None: diagnostic_capture['batch'] = deepcopy(value)
        return value
    count = 1 if diagnostic else 1000
    try:
        with OrderedPrefetch(load, range(count), capacity=2, resource=ctx['cache']) as prefetch:
            complete = recorded(output, spec, model, optimizer, prefetch, lambda m, w: rt.r_loss(ctx, m, w),
                lambda m, w: rt.s_loss(ctx, m, w), checkpoint_extra=extra, diagnostic_updates=diagnostic_updates)
    finally:
        for handle in handles: handle.remove()
    updates = complete.get('actual_updates', complete.get('completed_updates'))
    rt.require(complete['status'] in ('complete', 'safely_paused', 'diagnostic_only'), '未知训练终态，保留现场')
    receipt = dict(schema='R_candidate_eligibility_full_recorded_training_run_v1', status=complete['status'], binding=spec['binding'],
        completed_updates=updates, real_window_exposures=3*updates, synthetic_window_exposures=updates*int(regime == 'RS'),
        checkpoint=rt.read(output/'last_checkpoint.json'), full_training_record=rt.sha(output/'training_complete.json') if updates == 1000 else None,
        prefetch=prefetch.stats, cache_peak_bytes=ctx['cache'].peak, wall_seconds=time.perf_counter()-started,
        trainable_parameters=sum(p.numel() for p in model.parameters()), optimizer_replay=0, amp=False, actual_dtype='float32',
        epoch_augmentation=False, formal=not diagnostic, diagnostic_variant=diagnostic_variant if diagnostic else None,
        numeric_only_virtual_mask_overrides=definitions, synthetic_stress_initial_step=7 if diagnostic_variant == 'empty_stress' else None,
        record_extension_schema='R_candidate_scoring_eligibility_record_extension_v1', test_read=False)
    write_new(output/'run_receipt.json', receipt); return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--fold', choices=rt.FOLDS, required=True); parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--regime', choices=rt.REGIMES, required=True); parser.add_argument('--diagnostic-updates', type=int)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args(); os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    print(rt.canonical(run(args.config, args.output, args.fold, args.seed, args.regime, args.diagnostic_updates) if args.execute else
        dict(status='readonly_R_eligibility_training_preflight', optimizer_updates=0, test_read=False)))
