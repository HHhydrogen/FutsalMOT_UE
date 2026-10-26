"""论文训练过程记录：逐步曝光/损失/LR/梯度及完整定期检查点索引。

只用于新run，已有或partial目录拒绝重放。旧实验缺失字段由独立导出器说明，
不改写历史日志。本模块不导入模型或读取图像。
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
from datetime import datetime, timezone

RESEARCH = Path('D:/projects/FutsalMOT_Research')
RNG_FIELDS = {'rng_python', 'rng_numpy', 'rng_torch_cpu', 'rng_torch_cuda'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def physical(path):
    path = Path(os.path.abspath(path))
    require(RESEARCH in path.parents, '训练记录只能位于D研究目录')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '训练记录拒绝联接/重解析点')
    return path


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def atomic(path, value):
    path = Path(path); temporary = path.with_name(path.name+'.tmp')
    write_new(temporary, value)
    replace(temporary, path)


def replace(source, target):
    """Windows短暂共享冲突有界等待；失败保留tmp，不删除原目标。"""
    for attempt in range(8):
        try:
            os.replace(source, target)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5, 32) or attempt == 7:
                raise
            time.sleep(.05*(attempt+1))


class TrainingJournal:
    """优化器调用方先begin，实际step后commit；记录失败不能假称未发生更新。"""
    def __init__(self, directory, spec):
        require(spec.get('schema') == 'full_training_record_spec_v1' and spec.get('updates') == 1000
                and spec.get('R_per_update') == 3 and spec.get('S_per_update') in (0, 1)
                and spec.get('checkpoint_interval') == 50 and spec.get('test116187_sealed') is True,
                '缺固定预算/封存或完整记录契约')
        require(isinstance(spec.get('binding'), dict) and spec['binding']
                and isinstance(spec.get('runtime'), dict) and spec['runtime'], '缺实际来源绑定或运行环境')
        self.root = physical(directory); require(not self.root.exists(), '已有run/partial，不隐式覆盖或恢复')
        self.spec = deepcopy(spec); self.root.mkdir(parents=True)
        (self.root/'checkpoints').mkdir()
        write_new(self.root/'run_manifest.json', dict(spec, created_utc=datetime.now(timezone.utc).isoformat(),
            status='started_not_complete', fields_unavailable=[], images_copied=False))
        self.steps = (self.root/'steps.jsonl').open('x', encoding='utf-8')
        self.events = (self.root/'events.jsonl').open('x', encoding='utf-8')
        self.completed = 0; self.chain = '0'*64; self.pending = None; self.checkpoints = {}
        self.totals = dict(R_windows=0, S_windows=0, R_pairs=0, S_pairs=0, R_known_pairs=0, S_known_pairs=0)
        self.closed = False
        self.event('run_started', planned_updates=1000)

    def _line(self, stream, value):
        stream.write(canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())

    def event(self, name, **details):
        self._line(self.events, dict(event=name, time_utc=datetime.now(timezone.utc).isoformat(),
                                     committed_updates=self.completed, **details))

    def begin_step(self, index, real, synthetic):
        require(not self.closed and self.pending is None and index == self.completed < 1000,
                '步序或未闭合事务错误')
        require(not (self.root/'training_complete.json').exists(), '完整run不得追加更新')
        require(len(real) == 3 and len(synthetic) == self.spec['S_per_update']
                and all(isinstance(r.get('window_uid'), str) and type(r.get('epoch')) is int
                        for r in real+synthetic), '实际R/S窗口或epoch不完整')
        self.pending = dict(update_index=index, actual_update=index+1, real=deepcopy(real), synthetic=deepcopy(synthetic))
        atomic(self.root/'update_transaction.json', dict(status='started_not_committed', completed_updates_before=index,
                                                         update_index=index))

    def commit_step(self, *, loss, real_loss, synthetic_loss, learning_rates, grad_l2,
                    R_pairs, S_pairs, R_known_pairs, S_known_pairs, step_wall_seconds):
        require(self.pending is not None and not self.closed, '没有实际启动的step')
        values = [loss, real_loss, grad_l2, step_wall_seconds, *learning_rates]
        if self.spec['S_per_update']:
            require(synthetic_loss is not None, '混合组缺实际S loss'); values.append(synthetic_loss)
        else:
            require(synthetic_loss is None and S_pairs == S_known_pairs == 0, '纯R组不得隐藏额外S')
        require(learning_rates and all(type(v) in (float, int) and math.isfinite(v) and v >= 0 for v in values),
                'loss/LR/梯度/耗时记录非有限或缺失')
        require(all(type(v) is int and v >= 0 for v in (R_pairs, S_pairs, R_known_pairs, S_known_pairs))
                and 0 < R_known_pairs <= R_pairs and S_known_pairs <= S_pairs
                and (S_known_pairs > 0 if self.spec['S_per_update'] else True), 'pair预算或已知标签计数错误')
        row = dict(self.pending, loss=loss, real_loss=real_loss, synthetic_loss=synthetic_loss,
                   learning_rates=list(learning_rates), grad_l2=grad_l2, gradients_clipped=False,
                   R_pairs=R_pairs, S_pairs=S_pairs, R_known_pairs=R_known_pairs, S_known_pairs=S_known_pairs,
                   R_windows=3, S_windows=self.spec['S_per_update'], step_wall_seconds=step_wall_seconds)
        chain = hashlib.sha256((self.chain+canonical(row)).encode()).hexdigest()
        self._line(self.steps, dict(row, chain_sha256=chain))
        self.completed += 1; self.chain = chain; self.pending = None
        for name in self.totals:
            self.totals[name] += row[name]
        atomic(self.root/'update_transaction.json', dict(status='committed', completed_updates=self.completed,
                                                         chain_sha256=self.chain))

    def register_checkpoint(self, path, *, completed_updates, payload_fields):
        path = physical(path)
        require(path.parent == self.root/'checkpoints' and path.name == f'step_{completed_updates:04d}.pt'
                and path.is_file() and completed_updates == self.completed
                and self.pending is None and completed_updates not in self.checkpoints,
                '完整检查点命名/步数/物理路径错误')
        require({'model', 'optimizer', 'binding', 'completed_updates', 'exposure_chain', *RNG_FIELDS} <= set(payload_fields),
                '缺模型/优化器/曝光链或Python/NumPy/Torch/CUDA RNG状态')
        ref = dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size, completed_updates=completed_updates,
                   exposure_chain=self.chain, payload_fields=sorted(payload_fields))
        self.checkpoints[completed_updates] = ref
        write_new(path.with_suffix('.json'), ref)
        atomic(self.root/'last_checkpoint.json', ref)
        self.event('checkpoint_saved', checkpoint=ref)

    def save_checkpoint(self, model, optimizer, *, extra=None):
        """只保存调用方真实模型；原子写入所有RNG和优化器，不执行更新或隐式恢复。"""
        import random
        import numpy as np
        import torch
        require(self.pending is None and self.completed not in self.checkpoints and not self.closed,
                '未闭合实际更新或已有检查点')
        target = self.root/'checkpoints'/f'step_{self.completed:04d}.pt'
        temporary = target.with_suffix('.pt.tmp')
        require(not target.exists() and not temporary.exists(), '保留已有或partial检查点')
        cuda_rng = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
        require(cuda_rng is not None or self.spec['runtime'].get('device') == 'cpu_fixture',
                '正式GPU实验缺实际CUDA RNG')
        payload = dict(schema='full_training_checkpoint_v1', binding=self.spec['binding'],
            completed_updates=self.completed, exposure_chain=self.chain,
            model={k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
            optimizer=optimizer.state_dict(), rng_python=random.getstate(), rng_numpy=np.random.get_state(),
            rng_torch_cpu=torch.get_rng_state(), rng_torch_cuda=cuda_rng, extra=extra)
        with temporary.open('xb') as stream:
            torch.save(payload, stream); stream.flush(); os.fsync(stream.fileno())
        replace(temporary, target)
        self.register_checkpoint(target, completed_updates=self.completed, payload_fields=payload.keys())
        return target

    def finish(self):
        require(self.completed == 1000 and self.pending is None and self.totals['R_windows'] == 3000
                and self.totals['S_windows'] == 1000*self.spec['S_per_update']
                and set(range(0, 1001, 50)) <= set(self.checkpoints), '预算未完成或0/50/最终检查点缺失')
        self.event('training_complete', actual_updates=1000, exposure_chain=self.chain)
        value = dict(schema='full_training_process_complete_v1', status='complete', actual_updates=1000,
                     totals=self.totals, exposure_chain=self.chain, steps_sha256=sha(self.root/'steps.jsonl'),
                     checkpoints=[self.checkpoints[i] for i in sorted(self.checkpoints)], selection='step1000_last_no_best',
                     manifest_sha256=sha(self.root/'run_manifest.json'), test116187_read=False)
        value['events_sha256'] = sha(self.root/'events.jsonl')
        write_new(self.root/'training_complete.json', value)
        return value

    def close(self):
        if not self.closed:
            self.steps.close(); self.events.close(); self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        try:
            if kind is not None:
                self.event('failed_preserved_no_replay', error=repr(error), pending_step=self.pending)
        finally:
            self.close()
