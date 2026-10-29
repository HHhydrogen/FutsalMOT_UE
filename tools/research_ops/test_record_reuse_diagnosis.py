"""记录复用驱动的边界检查，不读取实际研究输入。"""
import unittest
from record_reuse_diagnosis import safe,enough

class DriverTests(unittest.TestCase):
 def test_sealed_GT_model_media_refused(self):
  for path in ('D:/projects/FutsalMOT_Research/test/a.json','D:/projects/FutsalMOT_Research/a/SNMOT-116/a.json',
   'D:/projects/FutsalMOT_Research/a/SNMOT187/a.json','D:/projects/FutsalMOT_Research/gt/a.json',
   'D:/projects/FutsalMOT_Research/a/model.pt','D:/projects/FutsalMOT_Research/a/frame.png','D:/projects/FutsalMOT_Research/a/gap_registry.json'):
   with self.assertRaises(ValueError):safe(path)
 def test_commit_and_RAM_each_reserve_inflight(self):
  self.assertTrue(enough(dict(available_RAM_bytes=8589934592+2*3221225472,available_commit_bytes=6442450944+2*3221225472),2))
  self.assertFalse(enough(dict(available_RAM_bytes=8589934592+2*3221225472-1,available_commit_bytes=6442450944+2*3221225472),2))
  self.assertFalse(enough(dict(available_RAM_bytes=8589934592+2*3221225472,available_commit_bytes=6442450944+2*3221225472-1),2))
 def test_readonly_metadata_path(self):
  self.assertEqual(safe('D:/projects/FutsalMOT_Research/pose/existing/report.json').name,'report.json')

if __name__=='__main__':unittest.main()
