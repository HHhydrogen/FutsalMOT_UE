"""仅CPU实际Torch检查点读回：无反向/优化器更新、无真实媒体或测试读取。"""
import argparse
import json
from pathlib import Path
import pickle
import random
from unittest.mock import patch

import numpy as np
import torch

from training_journal import TrainingJournal, RNG_FIELDS, physical, require, sha, write_new


def verify(output):
    output = physical(output); require(not output.exists(), '新诊断目录，保留历史结果')
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    initial = {k: v.clone() for k, v in model.state_dict().items()}
    before = (pickle.dumps(random.getstate()), pickle.dumps(np.random.get_state()), torch.get_rng_state().clone())
    spec = dict(schema='full_training_record_spec_v1', updates=1000, R_per_update=3, S_per_update=1,
        checkpoint_interval=50, test116187_sealed=True,
        runtime=dict(device='cpu_fixture', torch=torch.__version__, numpy=np.__version__),
        binding=dict(schema='diagnostic_only_no_training_admission', source_sha256=sha(__file__)))
    with patch.object(torch.cuda, 'is_available', return_value=False):
        with TrainingJournal(output, spec) as journal:
            target = journal.save_checkpoint(model, optimizer)
            payload = torch.load(target, map_location='cpu', weights_only=False)
            require(RNG_FIELDS <= set(payload) and payload['rng_torch_cuda'] is None
                and payload['completed_updates'] == 0 and not payload['optimizer']['state']
                and all(torch.equal(v, payload['model'][k]) for k, v in initial.items()),
                'CPU真实模型/空优化器/RNG检查点读回不一致')
            require(before[0] == pickle.dumps(random.getstate())
                and before[1] == pickle.dumps(np.random.get_state())
                and torch.equal(before[2], torch.get_rng_state()), '仅记录改变了实际RNG')
            journal.event('CPU_checkpoint_readback_verified', optimizer_updates=0, GPU_used=False)
    receipt = dict(schema='training_record_CPU_checkpoint_check_v1', status='complete_CPU_checkpoint_readback_only',
        checkpoint=dict(path=str(target), sha256=sha(target)), actual_optimizer_updates=0,
        diagnostic_model_only=True, GPU_used=False, source_images_read=False, test116187_read=False,
        model_optimizer_RNG_payload_verified=True, recording_changes_RNG=False,
        full_1000_step_training_integration_verified=False)
    write_new(output/'verification.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    print(json.dumps(verify(args.output), ensure_ascii=False))
