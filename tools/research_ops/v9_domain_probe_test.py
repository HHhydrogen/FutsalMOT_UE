"""人物域差探针的计数/常量/配对颜色夹具，不读取数据图像。"""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/research_ops'))
from v9_domain_probe import describe,auc,linear_probe
import numpy as np
class Tests(unittest.TestCase):
    def test_constant_image_descriptor(self):
        a=describe(np.full((100,50,3),100,dtype=np.uint8));self.assertEqual(len(a),29)
        self.assertTrue(all(abs(sum(a[start:start+8])-1)<1e-10 for start in (0,8,16)));self.assertAlmostEqual(a[-1],0)
    def test_AUC_tie_half(self):self.assertEqual(auc(np.array([1.,1.]),np.array([0,1])),.5)
    def test_paired_red_is_not_used_in_fit(self):
        train=[dict(domain=d,whole=[float(i),float(i)],whole_red=[99.,99.]) for _ in range(6) for i,d in [(0,'real'),(1,'synthetic')]]
        test=[dict(domain=d,whole=[float(i),float(i)],whole_red=[0.,0.]) for i,d in [(0,'real'),(1,'synthetic')]]
        result=linear_probe(train,test,'whole');self.assertEqual(result['heldout_time']['AUC'],1);self.assertLess(result['paired_red_synthetic_probability_mean'],result['heldout_time']['synthetic_score_mean'])
if __name__=='__main__':unittest.main()
