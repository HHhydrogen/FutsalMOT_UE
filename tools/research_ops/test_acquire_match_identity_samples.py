import unittest
from unittest.mock import patch
import urllib.error
import acquire_match_identity_samples as entry
class Tests(unittest.TestCase):
    def test_network_failure_retries_without_writing_partial(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'ok'
        with patch.object(entry.urllib.request,'urlopen',side_effect=[urllib.error.URLError('TLS transient'),Response()]) as call,patch.object(entry.time,'sleep'):
            self.assertEqual(entry.fetch_small('unused',10),b'ok');self.assertEqual(call.call_count,2)
    def test_one_clip_per_new_video_excludes_observed_and_known_other_sport(self):
        base=dict(video_id='ITo3sCnpw_k',title='football',football_title_candidate=True,already_observed_v10=False,splits={'val':['v_ITo3sCnpw_k_c010','v_ITo3sCnpw_k_c007']})
        self.assertEqual(entry.selections(dict(videos=[base]))[0]['sequence'],'v_ITo3sCnpw_k_c007')
        self.assertEqual(entry.selections(dict(videos=[dict(base,already_observed_v10=True)])),[])
        self.assertEqual(entry.selections(dict(videos=[dict(base,football_title_candidate=False)])),[])
        with self.assertRaises(ValueError):entry.selections(dict(videos=[dict(base,splits={'test':['v_ITo3sCnpw_k_c007']})]))
    def test_unknown_title_remains_pending_visual(self):
        item=dict(video_id='dw7LOz17Omg',title=None,football_title_candidate=False,already_observed_v10=False,splits={'val':['v_dw7LOz17Omg_c053']})
        self.assertEqual(entry.selections(dict(videos=[item]))[0]['classification'],'unknown_sport_pending_visual')
if __name__=='__main__':unittest.main()
