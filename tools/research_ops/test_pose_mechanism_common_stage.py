"""困难行汇总必须排除未干预的容易行，保留未知标签分母。"""
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from pose_mechanism_common_stage import active_summary


class Tests(unittest.TestCase):
    def test_only_actual_active_edges_count(self):
        e=dict(active_rows=[False,True,True],enough_history=[True]*3,history_UIDs=[['h']]*3,
               candidate_UIDs=['p','n','u'],scored_locations=[[i,j] for i in range(3) for j in range(3)],
               enabled=[[True]*3]*3,quality_gates={'pose':[1.]*9},
               logits={'pose':[1.,0.,0.,1.,0.,0.,-1.,0.,0.], 'pose_off':[1.,0.,0.,-1.,0.,0.,1.,0.,0.]})
        labels={'p':1,'n':0,'u':None}
        analyzer=SimpleNamespace(query_identity=lambda h,l:('person','trusted_consistent_history'),pair_label=lambda i,l:l)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'trace.gz'
            with gzip.open(p,'wt') as f:f.write(json.dumps(e)+'\n')
            result=active_summary(p,labels,analyzer)
        c=result['counts'];self.assertEqual(c['active_ranking_rows_both_known_classes'],2)
        self.assertEqual(c['unknown_candidate_pairs'],2);self.assertEqual(result['gate']['observations'],6)
        self.assertEqual(c['Pose_corrects_ranking_vs_own_off'],1);self.assertEqual(c['Pose_breaks_ranking_vs_own_off'],1)


if __name__=='__main__':unittest.main()
