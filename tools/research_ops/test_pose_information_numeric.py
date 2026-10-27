"""实际NumPy/Torch空评分边界；非空评分缺失仍须拒绝。"""
import unittest
import numpy as np
import torch
from pose_information_geometry import choose_cost,assignment_context


class Tests(unittest.TestCase):
    def test_empty_logits_with_no_scored_locations_is_valid(self):
        e=dict(stage=0,bbox_cost=[[.25,.9],[.2,.4]],active_rows=[False,True],scored_locations=[],logits={})
        out,threshold=choose_cost(e,'motion',np,torch)
        self.assertEqual(threshold,.8)
        self.assertTrue(np.array_equal(out,np.asarray([[.25,.9],[1.,1.]],dtype=np.float32)))

    def test_missing_nonempty_logits_not_silently_replaced(self):
        e=dict(stage=0,bbox_cost=[[.2]],active_rows=[True],scored_locations=[[0,0]],logits={})
        with self.assertRaises(KeyError):choose_cost(e,'motion',np,torch)

    def test_recorded_actual_assignment_authoritative_and_mismatch_explicit(self):
        def match(x,thresh):
            j=int(np.argmin(x[0]));return ([(0,j)] if x[0,j]<=thresh else []),[],[]
        e=dict(stage=0,bbox_cost=[[.2,.4]],reference_cost=[[.6,.1]],active_rows=[False],scored_locations=[],logits={})
        r,delta=assignment_context(e,np,torch,match)
        self.assertEqual(r['motion'],{0:1});self.assertFalse(r['_comparable']);self.assertGreater(delta,.1)


if __name__=='__main__':unittest.main()
