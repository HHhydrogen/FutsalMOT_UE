"""公开端点转移的针对性契约，全部为合成记录。"""
import unittest
from copy import deepcopy
from record_reuse_gap import *

class GapTests(unittest.TestCase):
 def test_all_transitions_and_ID0(self):
  self.assertEqual([transition(a,b) for a,b in [(REASONS[0],REASONS[0]),(REASONS[0],REASONS[1]),(REASONS[2],REASONS[0]),(REASONS[1],REASONS[1])]],['stable_recovery','improved','regressed','persistent_failure'])
  event_value(dict(event_uid='a'*64,reason=REASONS[0],endpoint_states=['matched','matched'],start_prediction_ID='0',end_prediction_ID='0'))
 def fixture(self):
  sources=[];data={}
  for index,c in enumerate(CONDITIONS):
   regime=c.rsplit('_',1)[1];key='r'+str(index);track='t'+str(index)
   event=dict(event_uid='a'*64,reason=REASONS[index%2],endpoint_states=['matched','matched'],start_prediction_ID='0',end_prediction_ID='0' if index%2==0 else '1')
   schema='v10_independent_trackeval_gap_v1' if c.startswith('original') else 'r_eligibility_tracking_metric_v1'
   data[key]=dict(schema=schema,status='complete',test_read=False,job=dict(sequence='s',fold='game4',seed=20261024,regime=regime),**{SCHEMAS[schema]:dict(events=[event])})
   data[track]=dict(status='complete',schema='fixture_receipt',native_output_frames_sha256='x')
   sources.append(dict(condition=c,regime=regime,sequence='s',fold='game4',seed=20261024,report=key,tracking_receipt=track))
  return sources,data
 def test_legacy_schema_and_exact_pairs(self):
  sources,data=self.fixture();r=analyse_gap(sources,data.__getitem__,{'panel':['s']},expected_reports=6,expected_unique_events=1)
  self.assertEqual(r['summary']['pair_rows'],3);self.assertEqual(r['summary']['event_occurrences'],6)
  self.assertTrue(all(x['internal_state']=='not_retained' for x in r['summary']['availability']))
 def test_unknown_reason_rejected(self):
  sources,data=self.fixture();data['r0']['gap']['events'][0]['reason']='unknown'
  with self.assertRaises(ValueError):analyse_gap(sources,data.__getitem__,{'panel':['s']},expected_reports=6,expected_unique_events=1)
 def test_different_registry_refused(self):
  sources,data=self.fixture();data['r0']['gap']['events'][0]['event_uid']='b'*64
  with self.assertRaises(ValueError):analyse_gap(sources,data.__getitem__,{'panel':['s']},expected_reports=6,expected_unique_events=1)
 def test_native_not_silently_discarded(self):
  sources,data=self.fixture();data['t0']['native_frames']=[{'actual':True}]
  with self.assertRaises(ValueError):analyse_gap(sources,data.__getitem__,{'panel':['s']},expected_reports=6,expected_unique_events=1)

if __name__=='__main__':unittest.main()
