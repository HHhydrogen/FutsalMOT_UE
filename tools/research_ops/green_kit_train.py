"""绿色A/B同预算gated训练；原v9数值函数，新协议/日志/检查点身份。"""
import argparse
import hashlib
import os
from pathlib import Path
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from green_kit_runtime import EXPERIMENT, canonical, physical_output, require, sha, validate_job


def train(config, fold, seed, appearance, output):
    start = time.perf_counter()
    cfg, numeric, pools, table, adapter, reference, new_s = validate_job(config, fold, seed, appearance)
    import torch
    from ordered_prefetch import OrderedPrefetch
    require(torch.__version__ == '2.6.0+cu124', '原FP32数值运行环境不同')
    torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
    require(torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 1024**3, 'GPU余量不足')
    output = physical_output(output)
    require(EXPERIMENT in output.parents and not output.exists(), '全新绿色run，partial不隐式重放')
    model = numeric.make_model(seed, 'gated').to('cuda:0')
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    initialization = numeric.model_sha(model)
    require(initialization == reference['binding']['initialization_sha256']
            and numeric.model_sha(model.base) == reference['binding']['motion_base_initialization_sha256'],
            '新A/B初始化与纯R参考不一致')
    binding = dict(protocol_sha256=sha(config), fold=fold, seed=seed, appearance=appearance,
                   method='gated', regime='RS', initialization_sha256=initialization,
                   motion_base_initialization_sha256=numeric.model_sha(model.base),
                   R_window_UID_chain_sha256=hashlib.sha256(canonical([x['window_uid'] for x in table['real']]).encode()).hexdigest(),
                   S_window_UID_chain_sha256=hashlib.sha256(canonical([x['window_uid'] for x in table['synthetic']]).encode()).hexdigest(),
                   adapter_sha256=hashlib.sha256(canonical(adapter.state()).encode()).hexdigest(),
                   synthetic_pool=new_s, numerical_v9_protocol=cfg['v9_protocol'],
                   prediction_manifest=cfg['prediction_manifest'])
    output.mkdir(parents=True)
    completed = 0; chain = '0'*64; stop = [False]
    previous = signal.signal(signal.SIGINT, lambda *a: stop.__setitem__(0, True))
    cache = numeric.Cache(pools, adapter, 'gated', seed)

    def checkpoint():
        temporary = output/'last.pt.tmp'
        require(not temporary.exists(), '保留未知partial检查点')
        with temporary.open('xb') as stream:
            torch.save(dict(schema='green_kit_gated_checkpoint_v1', binding=binding, completed_updates=completed,
                            exposure_chain=chain, model={k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
                            optimizer=optimizer.state_dict(), adapter=adapter.state(), actual_dtype='float32'), stream)
            stream.flush(); os.fsync(stream.fileno())
        numeric.replace(temporary, output/'last.pt')

    def load(i):
        rr = table['real'][i*3:i*3+3]; ss = [table['synthetic'][i]]
        return dict(index=i, r=rr, s=ss, real=[cache.get('real', r) for r in rr],
                    synthetic=[cache.get('synthetic', s) for s in ss])

    checkpoint()
    try:
        with OrderedPrefetch(load, range(1000), capacity=2, resource=cache) as prefetch:
            for batch in prefetch:
                if stop[0]:
                    break
                i = batch['index']; require(i == completed, '步序变化')
                numeric.atomic(output/'update_transaction.json', dict(status='started_not_committed', completed_updates_before=completed, update_index=i))
                optimizer.zero_grad(set_to_none=True)
                r_loss = numeric.domain_loss(model, batch['real']); s_loss = numeric.domain_loss(model, batch['synthetic'])
                loss = r_loss+s_loss/3
                require(torch.isfinite(loss).item(), '非有限loss')
                loss.backward()
                gradients = [p.grad.reshape(-1) for p in model.parameters() if p.grad is not None]
                require(gradients and torch.isfinite(torch.cat(gradients)).all().item(), '非有限梯度')
                optimizer.step(); completed += 1
                row = dict(update_index=i, actual_update=completed, real=batch['r'], synthetic=batch['s'], real_windows=3,
                           synthetic_windows=1, real_pair_exposures=sum(w['candidate_pairs'] for w in batch['real']),
                           synthetic_pair_exposures=sum(w['candidate_pairs'] for w in batch['synthetic']),
                           real_known_pairs=sum(w['known_pairs'] for w in batch['real']),
                           synthetic_known_pairs=sum(w['known_pairs'] for w in batch['synthetic']),
                           loss=float(loss.detach()), real_loss=float(r_loss.detach()), synthetic_loss=float(s_loss.detach()),
                           augmentation=numeric.AUGMENTATION['gated'])
                chain = hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
                with (output/'exposures.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(canonical(dict(row, chain_sha256=chain))+'\n'); stream.flush(); os.fsync(stream.fileno())
                numeric.atomic(output/'update_transaction.json', dict(status='committed', completed_updates=completed, update_index=i, chain=chain))
                if completed % 50 == 0:
                    checkpoint()
        checkpoint()
    finally:
        signal.signal(signal.SIGINT, previous)
    numeric.atomic(output/'run_receipt.json', dict(schema='green_kit_actual_window_training_v1',
        status='complete' if completed == 1000 else 'safely_paused', binding=binding, completed_updates=completed,
        real_window_exposures=3*completed, synthetic_window_exposures=completed,
        checkpoint_sha256=sha(output/'last.pt'), exposure_chain=chain, actual_dtype='float32', amp=False,
        checkpoint='last_no_best_not_EMA', prefetch=prefetch.stats, cache_peak_bytes=cache.peak,
        wall_seconds=time.perf_counter()-start, optimizer_replay=0,
        trainable_parameters=sum(p.numel() for p in model.parameters()), extra_S_not_equal_FLOPs=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fold', choices=('game4', 'game6', 'game9'), required=True)
    parser.add_argument('--seed', type=int, required=True); parser.add_argument('--appearance', choices=('A', 'B'), required=True)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    if args.execute:
        train(args.config, args.fold, args.seed, args.appearance, args.output)
    else:
        validate_job(args.config, args.fold, args.seed, args.appearance)
        print(canonical(dict(status='readonly_green_training_preflight', new_updates=0)))
