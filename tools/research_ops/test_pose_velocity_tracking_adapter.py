"""纯CPU结构与小型输入夹具；不导入Torch或执行实际追踪。"""
import ast
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pose_velocity_tracking_adapter import FIELDS, OLD_INPUT, adapt_tracker_tree, velocity_input


class WhitelistOnly(dict):
    """任何尝试访问评价GT或额外字段都在夹具中明确失败。"""
    def __getitem__(self, key):
        if key not in FIELDS:
            raise AssertionError('GT不应读取')
        return super().__getitem__(key)


def record(uid, time):
    return WhitelistOnly(uid=uid, bbox_xywh_px=[0., 0., 10., 20.], score=.9,
        xy_px=[[5., 10.] for _ in range(17)], geometry_valid=[True] * 17,
        timestamp_sec=time, image_wh=[100, 100], GT_identity='不可读取', future='不可读取')


class DummyAdapter:
    def __init__(self): self.calls = []
    def transform_pair(self, history, candidate):
        self.calls.append((deepcopy(history), deepcopy(candidate)))
        assert all(set(x) == set(FIELDS) for x in history + [candidate])
        # 只让夹具数值依赖实际预测字段，帮助验证开关不重归一输入。
        return [float(i) / 194 for i in range(194)] + [.37]


class VelocityTrackingAdapterTests(unittest.TestCase):
    def test_on_off_only_last_gate_differs_and_no_GT_or_mutation(self):
        adapter = DummyAdapter(); h = [record('h', 0.)]; p = record('p', .04)
        before = (deepcopy(h), deepcopy(p))
        on = velocity_input(adapter, h, p, True)
        off = velocity_input(adapter, h, p, False)
        self.assertEqual(on[:194], off[:194])
        self.assertEqual((on[-1], off[-1]), (.37, 0.))
        self.assertEqual((h, p), before)
        self.assertEqual(adapter.calls[0], adapter.calls[1])
        self.assertEqual(len(adapter.calls[0][0]), 1)

    def test_finite_dimension_and_explicit_bool_rejected(self):
        h, p = [record('h', 0.)], record('p', .04)
        for output in ([0.] * 194, [0.] * 194 + [float('nan')], [0.] * 194 + [True]):
            class Bad:
                def transform_pair(self, history, candidate): return output
            with self.assertRaises(ValueError): velocity_input(Bad(), h, p)
        with self.assertRaises(ValueError): velocity_input(DummyAdapter(), h, p, 0)

    def test_original_tracker_only_two_AST_nodes_change(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / 'python/src/grf_ue_bridge/learned_association_tracker_v8.py').read_text(encoding='utf-8')
        tree, audit = adapt_tracker_tree(source)
        self.assertEqual(audit['original_AST_sha256'], audit['reverse_restored_AST_sha256'])
        self.assertNotEqual(audit['original_AST_sha256'], audit['runtime_AST_sha256'])
        self.assertTrue(audit['tracker_numeric_AST_unchanged_outside_scope_and_input'])
        self.assertFalse(audit['GT_used_by_input']); self.assertFalse(audit['inference_shape_shuffle'])
        compile(tree, '<仅编译夹具未执行>', 'exec')
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == '_bounded_velocity_input']
        self.assertEqual(len(calls), 1)
        for changed in (source.replace(OLD_INPUT.replace(', ', ','), '0'),
                        source.replace('use_pose=self.use_pose)', 'use_pose=True)'),
                        source.replace('if enabled[i,j]:inputs.append(', 'if enabled[i,j]:self.normalizer.transform(0);inputs.append(')):
            with self.assertRaises(ValueError): adapt_tracker_tree(changed)


if __name__ == '__main__':
    unittest.main()
