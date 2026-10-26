"""原服装A/B计划的来源和单因素边界；不替代MRQ。"""
import copy
import unittest
from prepare_seeded_kit_capture import ROOT,build_plans,read
from pose17_seeded_kit_contract import validate_seeded_kit_contract


class SeededKitCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans=build_plans(read(ROOT/'Saved/AppearancePlanning/seeded_kit_recovery_a01/plan.json'))

    def test_exact_matrix_and_appearance_only_pair(self):
        self.assertEqual(len(self.plans),8)
        for a,b in zip(self.plans[::2],self.plans[1::2]):
            self.assertEqual(a['seeded_kit_pair']['paired_context_sha256'],b['seeded_kit_pair']['paired_context_sha256'])
            self.assertEqual(a['targets'],b['targets'])
            self.assertEqual(a['source_motion'],b['source_motion'])
            self.assertEqual(a['cameras'],b['cameras'])
            self.assertFalse(a['seeded_kit_pair']['apply_original_seeded_kits'])
            self.assertTrue(b['seeded_kit_pair']['apply_original_seeded_kits'])

    def test_reject_changed_camera_or_roster(self):
        for field in ('cameras','targets'):
            bad=copy.deepcopy(self.plans[1]);bad[field].pop()
            with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)

    def test_reject_mixed_old_gate_and_wrong_source_time(self):
        bad=copy.deepcopy(self.plans[1]);bad['long_window_contract']=True
        with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)
        bad=copy.deepcopy(self.plans[1]);bad['start_frame']+=1
        with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)

    def test_reject_wrong_material_and_apply_flag(self):
        bad=copy.deepcopy(self.plans[1]);bad['seeded_kit_pair']['binding']['entities'][0]['semantic_materials']['Jersey']='wrong'
        with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)
        bad=copy.deepcopy(self.plans[1]);bad['seeded_kit_pair']['apply_original_seeded_kits']=False
        with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)


if __name__=='__main__':unittest.main()
