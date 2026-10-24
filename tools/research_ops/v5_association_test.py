"""一次关联候选CPU检查：不加载模型、不读图像/GT/封存测试。"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from v5_association_runtime import plain,training_complete,sha
from v5_association_driver import delta

class AssociationCandidateTests(unittest.TestCase):
    def test_lexical_sealed_rejected(self):
        with self.assertRaises(ValueError):plain('D:/projects/FutsalMOT_Research/public/train/SNMOT-116/gt/gt.txt')
    def test_difference_preserves_negative_and_counts(self):
        first=dict(COMBINED_SEQ=dict(metrics_percent=dict(AssA=70.,HOTA=60.,IDF1=80.),IDSW_count=30))
        second=dict(COMBINED_SEQ=dict(metrics_percent=dict(AssA=71.,HOTA=59.,IDF1=81.),IDSW_count=25))
        value=delta(first,second)['COMBINED_SEQ'];self.assertEqual(value['delta_pp'],dict(AssA=-1.,HOTA=1.,IDF1=-1.));self.assertEqual(value['IDSW_delta_count'],5)
    def test_terminal_state_is_not_process_exit_and_PID_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=root/'report.json';report.write_text('{}',encoding='utf-8')
            names={f'{arm}_seed{seed}' for seed in (20261024,20261025,20261026) for arm in ('R3','R3S_blue','R3S_terracotta')}
            summary=root/'paired_summary.json';summary.write_text(json.dumps(dict(reports={name:dict(path=str(report),sha256=sha(report)) for name in names})),encoding='utf-8')
            state=root/'state.json';state.write_text(json.dumps(dict(status='complete_all_nine_train_and_dev',completed=sorted(names),summary=dict(path=str(summary),sha256=sha(summary)))),encoding='utf-8')
            config=dict(training_state=str(state),training_driver='D:/code/run_longpair_v5_control.py')
            active=SimpleNamespace(info=dict(name='python.exe'),pid=17904,cmdline=lambda:['python.exe','D:/code/run_longpair_v5_control.py'])
            reused=SimpleNamespace(info=dict(name='RuntimeBroker.exe'),pid=17904)
            with patch('psutil.process_iter',return_value=[active]):
                with self.assertRaises(ValueError):training_complete(config,require_absent=True)
            with patch('psutil.process_iter',return_value=[reused]):self.assertIsNotNone(training_complete(config,require_absent=True))
    def test_handoff_name_not_current_training_workload(self):
        tokens=('train_pose','train_longpair','evaluate_longpair','run_longpair_v5_control','run_poseonly','resume_location_control')
        for name in ('v5_association_driver.py','v5_association_stage.py','v5_association_handoff.py'):
            self.assertFalse(any(token in name for token in tokens))
if __name__=='__main__':unittest.main()
