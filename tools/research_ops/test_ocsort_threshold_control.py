"""单因素控制候选：追踪/评价数值体不变、失败实际join、不接触研究输入。"""
import ast
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

PATH=Path(__file__).with_name('ocsort_threshold_control.py')
spec=importlib.util.spec_from_file_location('threshold_control_contract',PATH)
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
SOURCE=Path('D:/projects/FutsalMOT_Research/code/2865b347c7bae8ae02eb1627b27e41c1dbcbd922c579d199f7e45c67d0337d74/tools/research_ops/ocsort_cached_control.py')

def node(source,cls,name):
    tree=ast.parse(source)
    group=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    return ast.dump(next(n for n in group.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)

class Contracts(unittest.TestCase):
    def test_track_and_metric_all_numerical_bodies_exact_original(self):
        original=SOURCE.read_text(encoding='utf-8-sig');new=PATH.read_text(encoding='utf-8-sig')
        for cls,methods in [('TrackWorker',('frames','run','close')),('MetricWorker',('__init__','run','close'))]:
            for name in methods:self.assertEqual(node(original,cls,name),node(new,cls,name))

    def test_only_new_protocol_root_status_and_runtime_entry(self):
        self.assertEqual(str(c.EXP).replace('\\','/'),'D:/projects/FutsalMOT_Research/pose/ocsort_threshold025_a01')
        self.assertEqual(c.STATUS,'complete12_OC025_single_factor_tracking_metrics_and_paired_analysis')
        text=PATH.read_text(encoding='utf-8-sig')
        self.assertIn("{'det_thresh':(.6,.25)}",text)
        self.assertIn("proof['threshold025_boundary']['passed'] is True",text)

    def test_failed_task_message_consumed_once_then_real_join(self):
        obj=c.Service.__new__(c.Service);obj.task_failed=False;obj.closed=False;obj.kind='track'
        obj.parent=Mock();obj.parent.poll.return_value=True
        obj.parent.recv.return_value=dict(status='failed',traceback='preserved_failure')
        obj.process=Mock();obj.process.pid=51;obj.process.exitcode=0;obj.process.is_alive.return_value=False
        with self.assertRaisesRegex(ValueError,'preserved_failure'):obj.receive()
        self.assertTrue(obj.task_failed);value=obj.join_failed()
        obj.parent.recv.assert_called_once();obj.process.join.assert_called_once_with(30)
        self.assertTrue(value['process_exited']);self.assertIn('failed_worker',value['status'])

if __name__=='__main__':unittest.main()
