"""可信断档proxy的最小CPU夹具；不读取真实数据/GPU/模型结果。"""
import unittest
from v8_gap_recovery import build_events,evaluate_events
def box(uid):return dict(uid=uid,bbox_xywh_px=[10.,20.,30.,50.])
def ground():return {i:[dict(gt_id='player1',bbox_xywh_px=[10.,20.,30.,50.])] for i in range(1,5)}
class Tests(unittest.TestCase):
    def registry(self):return build_events('SNMOT-060',{1:[box('raw1')],2:[],3:[],4:[box('raw4')]},ground())
    def test_continuous_no_gap_and_missing_GT_exclusion(self):
        e,a,_=build_events('SNMOT-060',{i:[box('raw'+str(i))] for i in range(1,5)},ground());self.assertEqual(e,[]);self.assertEqual(a['excluded_fewer_than_2_missing'],3)
        gt=ground();del gt[2];e,a,_=build_events('SNMOT-060',{1:[box('r1')],2:[],3:[],4:[box('r4')]},gt);self.assertEqual(e,[]);self.assertEqual(a['excluded_not_continuously_annotated'],1)
    def test_two_missing_frames_same_ID_recovery(self):
        e,a,g=self.registry();self.assertEqual(len(e),1);self.assertEqual(e[0]['missing_frames'],2);self.assertEqual(e[0]['stratum'],'2-4');self.assertEqual(a['candidate_trusted_endpoint_intervals'],1)
        result=evaluate_events(e,g,{1:[box('7')],4:[box('7')]});self.assertEqual(result['overall']['total_events'],1);self.assertEqual(result['overall']['recovery_rate'],1)
    def test_ambiguous_endpoint_not_counted_recovered(self):
        e,_,g=self.registry();result=evaluate_events(e,g,{1:[box('7'),box('8')],4:[box('7')]});self.assertEqual(result['overall']['ambiguous_endpoint'],1);self.assertEqual(result['overall']['recovery_rate'],0)
        raw={1:[box('r1'),box('conflict')],2:[],3:[],4:[box('r4')]};events,_,_=build_events('SNMOT-060',raw,ground());self.assertEqual(events,[])
    def test_wrong_ID_and_missing_prediction_keep_denominator(self):
        e,_,g=self.registry()
        for predictions,reason in [({1:[box('7')],4:[box('8')]},'different_prediction_ID'),({1:[box('7')]},'missing_prediction_endpoint')]:
            result=evaluate_events(e,g,predictions);self.assertEqual(result['overall'][reason],1);self.assertEqual(result['overall']['total_events'],1);self.assertEqual(result['overall']['recovery_rate'],0)
if __name__=='__main__':unittest.main()
