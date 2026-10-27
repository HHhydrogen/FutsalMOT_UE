"""完整行分母/负结果和近motion子集不能混成全部样本。"""
import unittest
from verify_pose_information_chain import tally,is_producer


class Tests(unittest.TestCase):
    def test_producer_filename_does_not_match_verifier_itself(self):
        self.assertTrue(is_producer('python.exe -B "D:/code/tools/research_ops/pose_information_chain.py" --execute'))
        self.assertTrue(is_producer('python.exe D:\\code\\pose_information_chain.py --execute'))
        self.assertFalse(is_producer('python.exe D:/code/tools/research_ops/verify_pose_information_chain.py --receipt x'))
        self.assertFalse(is_producer('python.exe -B -'))

    def test_all_unknown_and_negative_rows_retained_with_conditional_subset(self):
        def row(near,active,geometry,status='trusted_consistent_history'):
            return dict(job_id='j',history_status=status,pose_ranking_corrects='',pose_ranking_breaks='',
                geometry_available=geometry,near_motion=near,active=active,geometry_latest_margin='-1',
                geometry_mean_margin='-1',geometry_temporal_margin='1',geometry_shuffled_temporal_margin='-1')
        allrows,known=tally([row('1','1','1'),row('0','1','1'),row('','','0','unknown_history')])
        c=known['j'];self.assertEqual(allrows['j'],3);self.assertEqual(c['unknown_history'],1)
        self.assertEqual(c['all_geometry_rows'],2);self.assertEqual(c['near_geometry_rows'],1)
        self.assertEqual(c['all_latest_positive'],0);self.assertEqual(c['all_temporal_repairs_mean'],2)


if __name__=='__main__':unittest.main()
