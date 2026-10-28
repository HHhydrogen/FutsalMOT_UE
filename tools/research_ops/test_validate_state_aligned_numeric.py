"""数值准入严格比较、纯R/RS预算及默认只读的针对检查。"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import validate_state_aligned_numeric as numeric


class Tests(unittest.TestCase):
    def test_exact_recursive_state_no_tolerance_or_type_coercion(self):
        value = dict(state={0: {'step': 1., 'm': [0., .25]}}, rng=(1, [2, 3]))
        self.assertTrue(numeric.tree_equal(value, value))
        self.assertFalse(numeric.tree_equal(value, dict(value, rng=[1, [2, 3]])))
        self.assertFalse(numeric.tree_equal([1.], [1.+1e-15]))
        self.assertFalse(numeric.tree_equal(True, 1))
        self.assertFalse(numeric.tree_equal(float('nan'), float('nan')))

    def test_first_batch_R_and_RS_budget_and_closure(self):
        closed = []
        def batches(ctx, group, limit):
            try:
                self.assertEqual(limit, 1)
                yield dict(index=0, r=[1, 2, 3], real=[4, 5, 6],
                           s=[] if group == 'R' else [7],
                           synthetic=[] if group == 'R' else [8])
            finally:
                closed.append(group)
        rt = SimpleNamespace(batches=batches)
        for group in numeric.GROUPS:
            numeric.first_batch(rt, {}, group)
        self.assertEqual(closed, list(numeric.GROUPS))

    def test_wrong_R_or_S_budget_refuses_and_closes(self):
        closed = []
        def batches(ctx, group, limit):
            try:
                yield dict(index=0, r=[1, 2, 3], real=[4, 5, 6], s=[7], synthetic=[8])
            finally:
                closed.append(True)
        with self.assertRaises(ValueError):
            numeric.first_batch(SimpleNamespace(batches=batches), {}, 'R')
        self.assertEqual(closed, [True])

    def test_preflight_no_gpu_and_no_output_write_and_partial_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = root/'config.json'; output = root/'numeric'
            config.write_text('{}', encoding='utf-8')
            rt = SimpleNamespace(EXPERIMENT=root, sha=lambda p: 'bound', physical=lambda p: Path(p),
                validate_protocol=lambda p: dict(numeric_validation_receipt_path=str(output/'receipt.json')),
                )
            result = numeric.preflight(config, output, 'bound', runtime=rt)[3]
            self.assertFalse(output.exists())
            self.assertFalse(result['GPU_model_loaded'])
            self.assertEqual(result['formal_optimizer_updates'], 0)
            with self.assertRaises(ValueError):
                numeric.preflight(config, output, 'changed', runtime=rt)
            output.mkdir()
            with self.assertRaises(ValueError):
                numeric.preflight(config, output, runtime=rt)


if __name__ == '__main__':
    unittest.main()
