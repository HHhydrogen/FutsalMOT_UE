"""记录复用驱动的边界检查，不读取实际研究输入。"""
import unittest
from record_reuse_diagnosis import safe,enough,process_identity

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
 def test_exact_venv_launcher_chain_only(self):
  path='D:/projects/FutsalMOT_Research/code/a/tools/research_ops/record_reuse_diagnosis.py'
  rows=[dict(ProcessId=1,ParentProcessId=2,Name='python.exe',CommandLine=path),dict(ProcessId=2,ParentProcessId=3,Name='python.exe',CommandLine=path),dict(ProcessId=3,ParentProcessId=0,Name='powershell.exe',CommandLine='launcher')]
  self.assertEqual(process_identity(rows,1,path)['own_exact_script_launcher_chain'],[1,2])
  rows.append(dict(ProcessId=4,ParentProcessId=3,Name='python.exe',CommandLine=path))
  with self.assertRaises(ValueError):process_identity(rows,1,path)
 def test_same_basename_different_bundle_parent_is_not_exempt(self):
  path='D:/projects/FutsalMOT_Research/code/a/tools/research_ops/record_reuse_diagnosis.py';other=path.replace('/a/','/b/')
  rows=[dict(ProcessId=1,ParentProcessId=2,Name='python.exe',CommandLine=path),dict(ProcessId=2,ParentProcessId=0,Name='python.exe',CommandLine=other)]
  with self.assertRaises(ValueError):process_identity(rows,1,path)

if __name__=='__main__':unittest.main()
