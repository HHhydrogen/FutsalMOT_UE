"""验证固定门控/固定基分支下的幅度界限，不作模型准确率测试。"""
import unittest
from pose_residual_capacity import capacity


class Tests(unittest.TestCase):
    def test_large_wrong_margin_cannot_flip(self):
        self.assertTrue(capacity([-2,2],[1,1],[0],[1])['not_correctable_at_fixed_gate'])

    def test_small_wrong_margin_only_might_flip(self):
        r=capacity([-.1,0],[1,1],[0],[1]);self.assertTrue(r['base_wrong_or_tied']);self.assertFalse(r['not_correctable_at_fixed_gate'])

    def test_zero_gate_does_not_hide_wrong_margin(self):
        r=capacity([-.1,0],[0,0],[0],[1]);self.assertTrue(r['not_correctable_at_fixed_gate'])


if __name__=='__main__':unittest.main()
