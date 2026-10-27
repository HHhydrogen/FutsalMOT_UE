"""仅检查新根汇总口径与已验生命周期复用，不运行真实数据。"""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('bounded_control_tests',Path(__file__).with_name('bounded_error_control.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class Contracts(unittest.TestCase):
    def test_different_denominators_not_pooled_into_error_rate(self):
        s=dict(stage_rows=100,native_stage_outcome_rows=40,known_active_current_present_rows=10,
            counts={'first_stop/known_negative_cost_lower':2,'native_outcome/same_trusted_GT':30,
                'joint/current_GT_present':40,'denominator/known_active_current_present_rows':10})
        r=c.unit_rates(s,list(s['counts']))
        self.assertEqual(r['first_stop/known_negative_cost_lower'],2)
        self.assertEqual(r['native_outcome/same_trusted_GT'],75)
        self.assertEqual(r['active_current_present/known_negative_cost_lower'],20)
        self.assertNotIn('denominator/known_active_current_present_rows',r)

    def test_zero_denominator_is_unknown_not_zero(self):
        s=dict(stage_rows=5,native_stage_outcome_rows=0,known_active_current_present_rows=0,
            counts={'native_outcome/same_trusted_GT':0})
        r=c.unit_rates(s,list(s['counts']))
        self.assertIsNone(r['native_outcome/same_trusted_GT'])
        self.assertIsNone(r['active_current_present/known_negative_cost_lower'])

    def test_original_service_close_failure_and_receive_are_reused(self):
        self.assertIs(c.Service.close,c.base.Service.close)
        self.assertIs(c.Service.receive,c.base.Service.receive)
        self.assertIs(c.Service.join_failed,c.base.Service.join_failed)
        self.assertEqual(c.PROFILE['analysis_workers'],2)
        self.assertEqual(c.PROFILE['reserve_RAM_bytes'],8*2**30)

if __name__=='__main__':unittest.main()
