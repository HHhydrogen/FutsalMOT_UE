"""最终区间核验拒绝把63训练单元当比赛，或增设等效界限。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent))
from substitution_paired_analysis import effect_intervals
from verify_substitution_tracking_results import verify_interval

class IntervalVerification(unittest.TestCase):
    def test_independent_numeric_recomputation_includes_negative_match(self):
        values=dict(zip('abcdefg',[-3.,-2.,-1.,0.,1.,2.,3.]));report=effect_intervals(values)
        verify_interval(report,values,tuple(values))
    def test_pseudo_replicates_or_new_margin_rejected(self):
        values=dict(zip('abcdefg',[-3.,-2.,-1.,0.,1.,2.,3.]));report=effect_intervals(values)
        for field,value in [('n_independent_matches',63),('margin',.5),('formal_equivalence_or_noninferiority_test',True),('mean_delta_pp',.1),('Student_t_95CI',[0.])]:
            bad=deepcopy(report);bad[field]=value
            with self.assertRaises(ValueError):verify_interval(bad,values,tuple(values))

if __name__=='__main__':unittest.main()
