"""OC阈值单因素分析候选CPU合同；不读取实际评价或执行正式统计。"""
from copy import deepcopy
import math
import unittest

import ocsort_cached_analysis as source
import ocsort_threshold_analysis as analysis


class Analysis(unittest.TestCase):
    def fixture(self):
        panels = dict(original_heldout=list(source.OLD), old_external=['E1','E2'], seven_observed=['V'+str(i) for i in range(7)])
        target, old, references = [], [], []
        for sequence in source.panels_map(panels):
            def record(value, label):
                return dict(sequence=sequence, fold=None, seed=None, metrics={k:value for k in analysis.METRICS},
                    recovery=dict(total_events=10,same_prediction_ID_recovered=4 if label=='new' else 5,recovery_rate=.4 if label=='new' else .5),
                    report=dict(path=label+sequence,sha256=label))
            target.append(record(1.,'new'));old.append(record(2.,'old'))
            for baseline in source.BASELINES:
                cells = {(None,None)} if baseline=='PT_bbox' else source.allowed_cells(sequence)
                for fold,seed in cells:
                    references.append(dict(record(3.,baseline),baseline=baseline,fold=fold,seed=seed))
        return panels,target,old,references

    def test_only_threshold_changes_byte_and_lifecycle_stay_fixed(self):
        old=dict(det_thresh=.6,max_age=30,min_hits=3,iou_threshold=.3,delta_t=3,asso_func='iou',inertia=.2,use_byte=False)
        new=dict(old,det_thresh=.25);analysis.one_factor(old,new)
        for key,value in [('use_byte',True),('min_hits',1),('max_age',20),('det_thresh',.3)]:
            with self.assertRaises(ValueError):analysis.one_factor(old,dict(new,**{key:value}))
        with self.assertRaises(ValueError):analysis.one_factor(old,dict(new,extra_policy='changed'))

    def test_primary12_context36_no_OC_fold_seed_replication(self):
        panels,target,old,refs=self.fixture();rows=analysis.paired_matches(target,old,refs,panels,source)
        self.assertEqual(len(rows),48)
        primary=[row for row in rows if row['baseline']=='OC06']
        self.assertTrue(all(row['delta_pp']['AssA']==-1. and row['OC_evaluations']==1
            and row['reference_has_training_panel'] is False for row in primary))
        self.assertEqual({row['reference_training_cells'] for row in rows if row['baseline']=='strong_motion_RS'},{3,9})
        target[0]['seed']=20261024
        with self.assertRaises(ValueError):analysis.paired_matches(target,old,refs,panels,source)

    def test_missing_duplicate_and_nonfinite_primary_refused(self):
        panels,target,old,refs=self.fixture()
        for a,b in [(target[:-1],old),(target,old[:-1]),(target+[target[0]],old),(target,old+[old[0]])]:
            with self.assertRaises(ValueError):analysis.paired_matches(a,b,refs,panels,source)
        old[0]['metrics']['AssA']=float('nan')
        with self.assertRaises(ValueError):analysis.paired_matches(target,old,refs,panels,source)

    def test_60metric12gap_descriptions_use_matchN3_2_7(self):
        panels,target,old,refs=self.fixture();rows=analysis.paired_matches(target,old,refs,panels,source)
        def interval(values):return dict(n=len(values),mean_delta_pp=sum(values.values())/len(values),match_deltas_pp=values)
        metrics,gaps=analysis.describe(rows,panels,source,interval)
        self.assertEqual(set(metrics),set(analysis.BASELINES))
        self.assertEqual(sum(len(v) for group in metrics.values() for v in group.values()),60)
        self.assertEqual(sum(len(group) for group in gaps.values()),12)
        self.assertEqual([metrics['OC06'][p]['AssA']['n'] for p in analysis.PANELS],[3,2,7])
        self.assertTrue(all(metrics['OC06'][p]['AssA']['mean_delta_pp']==-1 for p in analysis.PANELS))

    def test_gap_zero_event_null_not_zero_and_all_event_denominator(self):
        panels,target,old,refs=self.fixture();seq=target[0]['sequence']
        for row in target+old+refs:
            if row['sequence']==seq:row['recovery']=dict(total_events=0,same_prediction_ID_recovered=0,recovery_rate=None)
        rows=analysis.paired_matches(target,old,refs,panels,source)
        self.assertTrue(all(row['gap']['delta_recovery_rate_pp'] is None for row in rows if row['sequence']==seq))
        def interval(values):return dict(n=len(values))
        _,gaps=analysis.describe(rows,panels,source,interval)
        self.assertIn(seq,gaps['OC06']['original_heldout']['zero_event_matches_retained_null'])
        old[1]['recovery']['total_events']=20
        old[1]['recovery']['recovery_rate']=.25
        with self.assertRaises(ValueError):analysis.paired_matches(target,old,refs,panels,source)

    def test_no_gap_interval_with_fewer_than_two_event_matches(self):
        panels,target,old,refs=self.fixture()
        for row in target+old+refs:
            if row['sequence']=='E1':row['recovery']=dict(total_events=0,same_prediction_ID_recovered=0,recovery_rate=None)
        rows=analysis.paired_matches(target,old,refs,panels,source)
        _,gaps=analysis.describe(rows,panels,source,lambda values:dict(n=len(values)))
        result=gaps['OC06']['old_external']
        self.assertIsNone(result['Student_t_95CI'])
        self.assertEqual(result['n_independent_matches'],1)
        self.assertEqual(result['zero_event_matches_retained_null'],['E1'])

    def test_context_reference_all_folds_and_negative_cells_retained(self):
        panels,target,old,refs=self.fixture()
        with self.assertRaises(ValueError):analysis.paired_matches(target,old,refs[:-1],panels,source)
        rows=analysis.paired_matches(target,old,refs,panels,source)
        self.assertTrue(all(row['delta_pp']['AssA']==-2. for row in rows if row['baseline']!='OC06'))
        self.assertTrue(all(row['gap']['delta_recovery_rate_pp']<0 for row in rows))


if __name__ == '__main__':
    unittest.main()
