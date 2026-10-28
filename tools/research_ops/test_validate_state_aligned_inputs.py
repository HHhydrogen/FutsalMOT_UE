"""CPU准入默认只读、显式设备与partial保护，不冒充实际数值执行。"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import validate_state_aligned_inputs as inputs

class Contract(unittest.TestCase):
    def fixture(self,root):
        return SimpleNamespace(EXPERIMENT=root,sha=lambda p:'fixed',validate_protocol=lambda p:{},physical=lambda p:Path(p))
    def test_readonly_no_output_no_GPU(self):
        with TemporaryDirectory() as tmp,patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':'-1'}):
            root=Path(tmp);out=root/'new';r=inputs.preflight(root/'cfg',out,'fixed',runtime=self.fixture(root))[3]
            self.assertFalse(out.exists());self.assertFalse(r['GPU_initialized']);self.assertEqual(r['formal_optimizer_updates'],0)
            self.assertEqual(r['planned_CPU_diagnostic_optimizer_updates'],4)
    def test_real_CPU_requires_explicit_no_CUDA(self):
        with TemporaryDirectory() as tmp,patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':'0'}):
            root=Path(tmp)
            with self.assertRaises(ValueError):inputs.preflight(root/'cfg',root/'new',runtime=self.fixture(root))
    def test_partial_never_replayed_and_sha_bound(self):
        with TemporaryDirectory() as tmp,patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':'-1'}):
            root=Path(tmp);out=root/'existing';out.mkdir()
            with self.assertRaises(ValueError):inputs.preflight(root/'cfg',out,runtime=self.fixture(root))
            with self.assertRaises(ValueError):inputs.preflight(root/'cfg',root/'new','changed',runtime=self.fixture(root))

if __name__=='__main__':unittest.main()
