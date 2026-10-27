"""只读库存的split及源视频聚类边界。"""
import unittest
import independent_match_inventory as entry
class Tests(unittest.TestCase):
    def test_split_whitelist(self):
        self.assertIn('sportsmot-val',entry.map_url('a'*40,'val'))
        for split in ('test','train/../test','football'):
            with self.assertRaises(ValueError):entry.map_url('a'*40,split)
    def test_source_video_not_clip_count(self):
        self.assertEqual(entry.video_id('v_G-vNjfx1GGc_c600'),entry.video_id('v_G-vNjfx1GGc_c004'))
        self.assertEqual(entry.video_id('v_ITo3sCnpw_k_c007'),'ITo3sCnpw_k')
        with self.assertRaises(ValueError):entry.video_id('SNMOT-116')
    def test_seqmap_unique_and_schema(self):
        self.assertEqual(entry.parse_map(b'name\nv_ITo3sCnpw_k_c007\n'),['v_ITo3sCnpw_k_c007'])
        with self.assertRaises(ValueError):entry.parse_map(b'name\nv_ITo3sCnpw_k_c007\nv_ITo3sCnpw_k_c007\n')
if __name__=='__main__':unittest.main()
