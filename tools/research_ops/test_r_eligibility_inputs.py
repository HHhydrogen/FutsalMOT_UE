"""新mask输入冻结器的纯合成字段合同；不打开实际实验数据。"""
from copy import deepcopy
import unittest
from unittest.mock import patch
import r_eligibility_inputs as inputs
from test_r_candidate_eligibility_method import fixture

def source_fixture():
    w,old=fixture();m=w['aligned_bank_metadata'];job=dict(job_id='teacher',fold='game4',sequence='SNMOT-097',regime='R',seed=20261024,model_id='teacher-model')
    s=dict(job_id='teacher',frame_number=10,stage='high_score',row_index=2,track_id=3,fold='game4',sequence='SNMOT-097',teacher_regime='R',teacher_seed=20261024,
           window_uid='w',history_UIDs=m['history_UIDs'],is_selected_R_window=True,counts=dict(known_pairs=2,positive_pairs=1,known_negative_pairs=1,unknown_pairs=1))
    pairs=[dict(window_uid='w',job_id='teacher',uid=uid,label=label,enabled=enabled,motion_gate=enabled,scoring_eligible=enabled,motion_gate_missing_reason=None)
           for uid,label,enabled in zip(m['candidate_UIDs'],m['pair_labels'],[True,False,True])]
    mask=dict(window_uid='w',source_job_id='teacher',frame_number=10,stage='high_score',source_summary_coordinate=dict(row_index=2),track_id=3,fold='game4',sequence='SNMOT-097',history_UIDs=m['history_UIDs'],candidate_UIDs=m['candidate_UIDs'],candidate_scoring_mask=[True,False,True])
    return w,s,pairs,job,mask

class InputContracts(unittest.TestCase):
    def test_sidecar_binds_original_metadata_and_unknown_unchanged(self):
        w,s,p,j,m=source_fixture();side,labels=inputs.sidecar_for(s,p,j,m,dict(proof='existing'))
        b=inputs.method.bind_window_mask(w,side)
        self.assertEqual(b['known_scoring_eligible'],[True,False]);self.assertEqual(labels,[1,0,None]);self.assertEqual(b['accounting']['kept_unknown_pairs'],1)
        self.assertFalse(side['labels_used_to_choose_mask']);self.assertTrue(side['active'])

    def test_labels_cannot_choose_mask(self):
        _,s,p,j,m=source_fixture();before,_=inputs.sidecar_for(s,p,j,m,{})
        p[0]['label']=0;p[1]['label']=1;after,_=inputs.sidecar_for(s,p,j,m,{})
        self.assertEqual(before,after)

    def test_missing_motion_gate_never_filled_false(self):
        _,s,p,j,m=source_fixture();p[0]['motion_gate']=None;p[0]['motion_gate_missing_reason']='inactive_motion_gate_not_observed'
        with self.assertRaises(ValueError):inputs.sidecar_for(s,p,j,m,{})

    def test_probability_layer_cannot_be_used_for_eligibility(self):
        _,s,p,j,m=source_fixture();p[0]['scoring_eligible']=False
        with self.assertRaises(ValueError):inputs.sidecar_for(s,p,j,m,{})

    def test_cross_teacher_frame_history_or_UID_refused(self):
        for field,value in [('source_job_id','other'),('frame_number',11),('history_UIDs',['other']),('candidate_UIDs',['other']),('fold','game6')]:
            _,s,p,j,m=source_fixture();m[field]=value
            with self.assertRaises(ValueError):inputs.sidecar_for(s,p,j,m,{})

    def test_low_stage_or_RS_teacher_refused(self):
        _,s,p,j,m=source_fixture();s['stage']='low_score'
        with self.assertRaises(ValueError):inputs.sidecar_for(s,p,j,m,{})
        _,s,p,j,m=source_fixture();j['regime']='RS'
        with self.assertRaises(ValueError):inputs.sidecar_for(s,p,j,m,{})

    def test_forbidden_input_rejected_before_hash(self):
        with patch.object(inputs,'checked',side_effect=AssertionError('不得先hash')):
            with self.assertRaises(ValueError):list(inputs.rows(dict(path='D:/projects/FutsalMOT_Research/x/frames.jsonl.gz',sha256='x')))
            with self.assertRaises(ValueError):inputs.read(dict(path='D:/projects/FutsalMOT_Research/model.pt',sha256='x'))

if __name__=='__main__':unittest.main()
