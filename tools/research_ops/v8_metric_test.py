"""TrackEval单序列/汇总Count边界，保留帧和未筛行守卫。"""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/research_ops'))
from v8_metric import validate_count
class CountTests(unittest.TestCase):
    def test_aggregate_does_not_invent_frames_field(self):
        validate_count('SNMOT-060',dict(Frames=750,Dets=20,GT_Dets=19),20,19,'SNMOT-060')
        validate_count('COMBINED_SEQ',dict(Dets=20,GT_Dets=19,IDs=3,GT_IDs=3),20,19,'SNMOT-060')
    def test_actual_sequence_frame_guard_remains(self):
        with self.assertRaises(ValueError):validate_count('SNMOT-060',dict(Frames=749,Dets=20,GT_Dets=19),20,19,'SNMOT-060')
    def test_aggregate_row_filter_refused(self):
        with self.assertRaises(ValueError):validate_count('COMBINED_SEQ',dict(Dets=18,GT_Dets=19),20,19,'SNMOT-060')
if __name__=='__main__':unittest.main()
