"""CPU合同的来源/窗口/有界/非有限拒绝检查；不读取实际研究数据。"""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from validate_pose_velocity_candidate_cpu import validate_contract_shape, validate_window_scope, validate_pair, safe_path
from pose_temporal_feature_candidate import CHANGED_COLUMNS


def record():
    return dict(uid='SNMOT-060:000001:0', bbox_xywh_px=[0., 0., 100., 100.], score=.8,
                xy_px=[[50., 50.] for _ in range(17)], geometry_valid=[True] * 17,
                timestamp_sec=0., image_wh=[1000, 1000])


def contract():
    return dict(status='complete_three_actual_base_R_input_contracts_zero_updates_candidate_not_trained',
                new_optimizer_updates=0, model_loaded=False, normalizer_fitted=False,
                external_inputs_read=False, test_read=False, changed_columns=list(CHANGED_COLUMNS),
                folds={f:dict(window_entries=1000, velocity_clip_99=1.) for f in ('game4','game6','game9')})


class Tests(unittest.TestCase):
    def test_contract_missing_fold_external_or_nonfinite_clip_rejected(self):
        value=contract();validate_contract_shape(value)
        for change in ('missing','external','nan','columns'):
            x=deepcopy(value)
            if change=='missing':del x['folds']['game9']
            elif change=='external':x['external_inputs_read']=True
            elif change=='nan':x['folds']['game4']['velocity_clip_99']=float('nan')
            else:x['changed_columns']=x['changed_columns'][:-1]
            with self.assertRaises(ValueError):validate_contract_shape(x)

    def test_heldout_external_test_and_missing_records_rejected(self):
        value=dict(domain='real',game='game6',window_uid='w',history=[record() for _ in range(3)],
                   candidates=[dict(prediction=record(),label=None)])
        validate_window_scope(value,'game4')
        for change in ('heldout','external','test','missing'):
            x=deepcopy(value)
            if change=='heldout':x['game']='game4'
            elif change=='external':x['game']='sportsmot_external'
            elif change=='test':x['history'][0]['uid']='SNMOT-116:1:0'
            else:del x['candidates'][0]['prediction']['geometry_valid']
            with self.assertRaises(ValueError):validate_window_scope(x,'game4')

    def test_feature_mask_gate_nonfinite_and_bound_rejected(self):
        quality=SimpleNamespace(quality_gate=lambda raw,scale:raw[0])
        raw=[0.] * 194;changed=list(raw);gate=list(raw);history=[record() for _ in range(3)]
        missing,maximum=validate_pair(raw,changed,gate,history,quality,1.)
        self.assertEqual((missing,maximum),(0,0.))
        for change in ('motion','gate','nan','bound'):
            a,b=list(changed),list(gate)
            if change=='motion':a[0]=.1
            elif change=='gate':b[1]=.1
            elif change=='nan':a[28]=float('nan')
            else:a[28]=1.1
            with self.assertRaises(ValueError):validate_pair(raw,a,b,history,quality,1.)

    def test_missing_velocity_is_zero_without_mask_upgrade(self):
        quality=SimpleNamespace(quality_gate=lambda raw,scale:0.)
        raw=[0.] * 194;changed=list(raw);history=[record() for _ in range(3)]
        history[-1]['geometry_valid'][5]=False
        self.assertEqual(validate_pair(raw,changed,list(raw),history,quality,1.)[0],1)
        changed[78]=.1
        with self.assertRaises(ValueError):validate_pair(raw,changed,list(raw),history,quality,1.)

    def test_sealed_or_relative_source_path_rejected_before_read(self):
        for value in ('relative.json','D:/public/test/a.json','D:/public/SNMOT-187/cache.json',
                      'D:/projects/FutsalMOT_Research/pose/pose_information_a01/../escape.json'):
            with self.assertRaises(ValueError):safe_path(value)


if __name__=='__main__':unittest.main()
