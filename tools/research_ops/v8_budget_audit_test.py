"""相同窗口数不足以冒充相同监督pair；验证实际公平性拒绝路径。"""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/research_ops'))
from v8_budget_audit import equal_quartet
def rows():return [dict(arm=arm,real_UID_sequence_sha256='R',initialization_sha256='same',real_window_exposures=3000,real_known_pairs=5000,real_candidate_pairs=6000,synthetic_UID_sequence_sha256='S',synthetic_known_pairs=3000,synthetic_candidate_pairs=4000) for arm in ('motion_R','motion_RS','pose_R','pose_RS')]
class Tests(unittest.TestCase):
    def test_identical_budget_accepts(self):equal_quartet(rows())
    def test_equal_window_count_but_changed_pair_budget_refused(self):
        value=rows();value[-1]['real_known_pairs']+=1
        with self.assertRaises(ValueError):equal_quartet(value)
    def test_changed_real_order_or_synthetic_budget_refused(self):
        for key in ('real_UID_sequence_sha256','synthetic_known_pairs'):
            value=rows();value[-1][key]='changed'
            with self.assertRaises(ValueError):equal_quartet(value)
if __name__=='__main__':unittest.main()
