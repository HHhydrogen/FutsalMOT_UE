"""完整记录循环：3R/1S或3基础R/1额外R，保持调用方模型及domain_loss。"""
import signal
import time

from training_journal import TrainingJournal, require


def train(output, spec, model, optimizer, batches, domain_loss, *, checkpoint_extra=None):
    """batches来自已验OrderedPrefetch2；主控制器另行冻结/检查数据及数值来源。"""
    import torch
    require(spec['runtime'].get('device') != 'cpu_fixture', '夹具不能成为正式训练入口')
    stop = [False]
    previous = signal.signal(signal.SIGINT, lambda *args: stop.__setitem__(0, True))
    start = time.perf_counter()
    try:
        with TrainingJournal(output, spec) as journal:
            journal.save_checkpoint(model, optimizer, extra=checkpoint_extra)
            for batch in batches:
                if stop[0]:
                    break
                clock = time.perf_counter()
                require(batch['index'] == journal.completed, '实际优化步序变化')
                extra_mode=spec['schema']=='full_training_record_spec_v2_real_groups'
                extra=batch.get('extra_real',[]);extra_rows=batch.get('r_extra',[])
                require((len(extra)==len(extra_rows)==1 and not batch['s']) if extra_mode else not extra and not extra_rows,
                        '额外真实组必须单独登记且不能借S身份执行')
                journal.begin_step(batch['index'], batch['r']+extra_rows, batch['s'])
                optimizer.zero_grad(set_to_none=True)
                r_loss = domain_loss(model, batch['real'])
                s_loss = domain_loss(model, batch['synthetic']) if batch['s'] else None
                extra_loss=domain_loss(model,extra) if extra_mode else None
                loss = r_loss+extra_loss/3 if extra_mode else (r_loss+s_loss/3 if s_loss is not None else r_loss)
                require(torch.isfinite(loss).item(), '实际loss非有限')
                loss.backward()
                gradients = [p.grad.detach().reshape(-1) for p in model.parameters() if p.grad is not None]
                require(gradients and torch.isfinite(torch.cat(gradients)).all().item(), '实际梯度非有限')
                grad_l2 = float(torch.linalg.vector_norm(torch.cat(gradients)))
                rates = [float(g['lr']) for g in optimizer.param_groups]
                optimizer.step()
                group_losses=dict(base_real_loss=float(r_loss.detach()),extra_real_loss=float(extra_loss.detach())) if extra_mode else {}
                journal.commit_step(loss=float(loss.detach()), real_loss=float(loss.detach()) if extra_mode else float(r_loss.detach()),
                    synthetic_loss=float(s_loss.detach()) if s_loss is not None else None,
                    learning_rates=rates, grad_l2=grad_l2,
                    R_pairs=sum(w['candidate_pairs'] for w in batch['real']+extra),
                    S_pairs=sum(w['candidate_pairs'] for w in batch['synthetic']),
                    R_known_pairs=sum(w['known_pairs'] for w in batch['real']+extra),
                    S_known_pairs=sum(w['known_pairs'] for w in batch['synthetic']),
                    step_wall_seconds=time.perf_counter()-clock,**group_losses)
                if journal.completed % 50 == 0:
                    journal.save_checkpoint(model, optimizer, extra=checkpoint_extra)
            require(journal.completed == 1000 or stop[0], '输入提前结束，不能伪造成取消或完成')
            journal.event('training_wall_seconds', seconds=time.perf_counter()-start,
                          includes_checkpoints=True, includes_prefetch_wait=True)
            if journal.completed == 1000:
                return journal.finish()
            if journal.completed not in journal.checkpoints:
                journal.save_checkpoint(model, optimizer, extra=checkpoint_extra)
            journal.event('user_SIGINT_safely_paused_no_replay', completed_updates=journal.completed)
            return dict(status='safely_paused', completed_updates=journal.completed)
    finally:
        signal.signal(signal.SIGINT, previous)
