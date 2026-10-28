"""机会账本有限值、原生行列身份、互斥首停和Pose结构的CPU夹具。"""
from copy import deepcopy
import unittest
import decision_opportunity_core as c

def record(uid,time):return dict(uid=uid,timestamp_sec=time,bbox_xywh_px=[0,0,10,20],xy_px=[[0.,0.] for _ in range(17)],geometry_valid=[True]*17)
def fixture():
    history=[record('h'+str(i),i) for i in range(3)];candidates=[record('p',3),record('n',3)]
    stage=dict(stage='high_score',rows=[dict(track_id=7,history=history)],track_ids=[7],candidates=candidates,candidate_UIDs=['p','n'],
        reference_cost=[[.4,.5]],bbox_base_cost=[[.3,.3]],threshold=.8,active=[True],gates=[[True,True]],enabled=[[True,True]],assignments=[[0,0]])
    empty=lambda name:dict(stage=name,rows=[],track_ids=[],candidates=[],candidate_UIDs=[],reference_cost=[],bbox_base_cost=[],threshold=c.THRESHOLDS[name],active=[],gates=None if name=='low_score' else [],enabled=None if name=='low_score' else [],assignments=[])
    frame=dict(frame_number=4,stages=[stage,empty('low_score'),empty('unconfirmed')])
    annotation=dict(frame_number=4,stage='high_score',row_index=0,track_id=7,history_UIDs=['h0','h1','h2'],history_status='trusted_consistent_history',query_GT_id='0',
        candidate_UIDs=['p','n'],pair_labels=[1,0],selected_column=0,selected_UID='p',raw_correct_UIDs=['p'],current_GT_present=True,actual_observation_gap_frames=1)
    return frame,[annotation]

class Contracts(unittest.TestCase):
    def run_case(self,mutate=lambda f,a:None):
        f,a=fixture();mutate(f,a);return c.analyze_frame(f,a,{})[0]
    def test_correct_opportunity_ID0_and_joint_histogram(self):
        r=self.run_case();self.assertEqual(r['first_stop'],'actual_correct');self.assertTrue(r['flags']['local_opportunity'])
        self.assertEqual(r['pose_shared_body_histograms']['correct']['12'],1);self.assertEqual(r['absolute_counts']['candidates'],2)
    def test_inactive_and_low_score_are_not_MLP_errors(self):
        r=self.run_case(lambda f,a:f['stages'][0].update(active=[False],enabled=[[False,False]]));self.assertEqual(r['first_stop'],'learned_inactive')
        f,a=fixture();s=f['stages'][0];s.update(stage='low_score',threshold=.5,active=[False],gates=None,enabled=None)
        f['stages'][0],f['stages'][1]=f['stages'][1],s;f['stages'][0].update(stage='high_score',threshold=.8,gates=[],enabled=[]);a[0]['stage']='low_score'
        self.assertEqual(c.analyze_frame(f,a,{})[0]['first_stop'],'low_score_bbox_only')
    def test_gate_and_enabled_stops(self):
        self.assertEqual(self.run_case(lambda f,a:f['stages'][0].update(gates=[[False,True]],enabled=[[False,True]]))['first_stop'],'correct_motion_gate_rejected')
        self.assertEqual(self.run_case(lambda f,a:f['stages'][0].update(enabled=[[False,True]]))['first_stop'],'correct_not_enabled')
    def test_probability_rejected_no_bbox_fallback(self):
        r=self.run_case(lambda f,a:f['stages'][0].update(reference_cost=[[1.,.5]]));self.assertEqual(r['first_stop'],'correct_probability_rejected')
    def test_exact_boundary_is_unknown_not_solver_acceptance(self):
        r=self.run_case(lambda f,a:f['stages'][0].update(reference_cost=[[.8,.5]]));self.assertEqual(r['first_stop'],'cost_equality_unknown');self.assertTrue(r['flags']['actual_correct'])
    def test_strict_cost_wrong_and_unmatched_are_descriptive(self):
        def wrong(f,a):f['stages'][0]['assignments']=[[0,1]];a[0].update(selected_column=1,selected_UID='n');f['stages'][0]['reference_cost']=[[.5,.5]]
        r=self.run_case(wrong);self.assertEqual(r['first_stop'],'actual_known_wrong_with_strict_correct');self.assertTrue(r['flags']['known_wrong_cheaper_or_equal'])
        def unmatched(f,a):f['stages'][0]['assignments']=[];a[0].update(selected_column=None,selected_UID=None)
        self.assertEqual(self.run_case(unmatched)['first_stop'],'actual_unmatched_with_strict_correct')
    def test_absent_GT_raw_stage_and_unknown_history_separate(self):
        def absent(f,a):a[0].update(current_GT_present=False,raw_correct_UIDs=[],pair_labels=[0,0])
        self.assertEqual(self.run_case(absent)['first_stop'],'current_GT_absent')
        def raw(f,a):a[0].update(raw_correct_UIDs=[],pair_labels=[0,0])
        self.assertEqual(self.run_case(raw)['first_stop'],'trusted_correct_raw_absent')
        def stage(f,a):a[0].update(raw_correct_UIDs=['outside'],pair_labels=[0,0])
        self.assertEqual(self.run_case(stage)['first_stop'],'correct_raw_not_in_stage')
        self.assertEqual(self.run_case(lambda f,a:a[0].update(history_status='history_unknown',query_GT_id=None,pair_labels=[None,None]))['first_stop'],'history_not_trusted_three')
    def test_earliest_anchor_drift_is_independent_from_current_identity(self):
        f,a=fixture();anchors={};c.analyze_frame(f,a,anchors);f['frame_number']=5;a[0].update(frame_number=5,query_GT_id='9')
        r=c.analyze_frame(f,a,anchors)[0];self.assertTrue(r['flags']['earliest_stage_trusted3_anchor_drift']);self.assertTrue(r['flags']['actual_correct']);self.assertEqual(anchors[7]['gt_id'],'0')
    def test_Pose_zero_and_five_shared_preserved_not_accuracy(self):
        def pose(f,a):
            f['stages'][0]['candidates'][0]['geometry_valid']=[False]*17
            f['stages'][0]['candidates'][1]['geometry_valid']=[False]*5+[True]*5+[False]*7
        r=self.run_case(pose);self.assertEqual(r['pose_shared_body_histograms']['correct']['0'],1);self.assertEqual(r['pose_shared_body_histograms']['known_negative']['5'],1)
        self.assertFalse(r['pose_candidates'][1]['shared_body_ge6']);self.assertFalse(r['Pose_support_is_accuracy'])
    def test_unknown_competition_not_negative(self):
        r=self.run_case(lambda f,a:a[0].update(pair_labels=[1,None]));self.assertTrue(r['flags']['unknown_competition']);self.assertFalse(r['flags']['local_opportunity']);self.assertEqual(r['absolute_counts']['known_negative'],0)
    def test_malformed_finite_mask_shape_and_UID_rejected(self):
        mutations=[lambda f,a:f['stages'][0].update(reference_cost=[[float('nan'),.2]]),lambda f,a:f['stages'][0]['candidates'][0].update(geometry_valid=[1]*17),
            lambda f,a:f['stages'][0].update(reference_cost=[[.2]]),lambda f,a:a[0].update(candidate_UIDs=['n','p']),lambda f,a:f['stages'][0]['rows'][0]['history'][0]['xy_px'][0].__setitem__(0,float('inf'))]
        for mutate in mutations:
            with self.assertRaises(ValueError):self.run_case(mutate)
    def test_missing_duplicate_extra_annotations_refused(self):
        f,a=fixture()
        for annotations in ([],a+a,[dict(a[0],track_id=8)]):
            with self.assertRaises(ValueError):c.analyze_frame(f,annotations,{})
    def test_correct_column_owned_elsewhere_is_observed_not_resolved(self):
        f,a=fixture();s=f['stages'][0];s['rows'].append(dict(deepcopy(s['rows'][0]),track_id=8));s['track_ids'].append(8)
        for key in ('reference_cost','bbox_base_cost','gates','enabled'):s[key].append(deepcopy(s[key][0]))
        s['active'].append(True);s['assignments']=[[1,0],[0,1]];a[0].update(selected_column=1,selected_UID='n')
        a.append(dict(deepcopy(a[0]),track_id=8,row_index=1,selected_column=0,selected_UID='p'))
        r=c.analyze_frame(f,a,{})[0];self.assertTrue(r['flags']['positive_owned_elsewhere']);self.assertFalse(r['local_cost_comparison_is_causal'])
    def test_all_empty_stages_preserve_zero_rows_and_reject_extra_annotation(self):
        f,a=fixture();s=f['stages'][0];s.update(rows=[],track_ids=[],reference_cost=[],bbox_base_cost=[],active=[],gates=[],enabled=[],assignments=[])
        self.assertEqual(c.analyze_frame(f,[],{}),[])
        with self.assertRaises(ValueError):c.analyze_frame(f,a,{})
    def test_Pose_supported_opportunity_wrong_unmatched_unknown_separate(self):
        def wrong(f,a):f['stages'][0]['assignments']=[[0,1]];a[0].update(selected_column=1,selected_UID='n')
        r=self.run_case(wrong);self.assertTrue(r['flags']['local_opportunity_pose_supported_both']);self.assertTrue(r['flags']['local_opportunity_pose_supported_actual_known_wrong']);self.assertTrue(r['flags']['local_opportunity_pose_supported_actual_noncorrect'])
        def unmatched(f,a):f['stages'][0]['assignments']=[];a[0].update(selected_column=None,selected_UID=None)
        self.assertTrue(self.run_case(unmatched)['flags']['local_opportunity_pose_supported_actual_unmatched'])
        def unknown(f,a):
            s=f['stages'][0];s['candidates'].append(record('u',3));s['candidate_UIDs'].append('u')
            for key,value in [('reference_cost',.2),('bbox_base_cost',.2),('gates',True),('enabled',True)]:s[key][0].append(value)
            s['assignments']=[[0,2]];a[0].update(candidate_UIDs=['p','n','u'],pair_labels=[1,0,None],selected_column=2,selected_UID='u')
        r=self.run_case(unknown);self.assertTrue(r['flags']['local_opportunity_pose_supported_actual_unknown']);self.assertFalse(r['flags']['local_opportunity_pose_supported_actual_noncorrect'])
    def test_gap_boundaries_and_history_shared_counts(self):
        for gap,expected in [(1,True),(30,True),(31,False),(None,False)]:
            r=self.run_case(lambda f,a:a[0].update(actual_observation_gap_frames=gap))
            self.assertEqual(r['flags']['local_opportunity_pose_supported_both'],expected)
            self.assertEqual(r['pose_candidates'][0]['history_each_shared_body_joints'],[12,12,12])
        with self.assertRaises(ValueError):self.run_case(lambda f,a:a[0].update(actual_observation_gap_frames=True))
    def test_other_stage_correct_raw_appearance_and_owner_are_observations(self):
        f,a=fixture();s=f['stages'][2];s.update(rows=[dict(track_id=8,history=deepcopy(f['stages'][0]['rows'][0]['history']))],track_ids=[8],
            candidates=[record('p',3)],candidate_UIDs=['p'],reference_cost=[[.4]],bbox_base_cost=[[.4]],active=[True],gates=[[True]],enabled=[[True]],assignments=[[0,0]])
        a.append(dict(deepcopy(a[0]),stage='unconfirmed',track_id=8,candidate_UIDs=['p'],pair_labels=[1]))
        r=c.analyze_frame(f,a,{})[0];self.assertTrue(r['flags']['raw_correct_in_other_stage']);self.assertTrue(r['flags']['raw_correct_owned_in_other_stage_other_track'])
        self.assertEqual(r['raw_correct_other_stage_other_track_assignments']['p'],[dict(stage='unconfirmed',track_id=8,row_index=0)])

if __name__=='__main__':unittest.main()
