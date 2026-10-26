"""绿色新准入的来源、单因素配对及旧蓝契约隔离。"""
from copy import deepcopy
import unittest
from prepare_green_kit_pair_a01 import plans
from pose17_seeded_kit_contract import validate_seeded_kit_contract,context_payload,digest


class GreenKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plans=plans()

    def test_matrix_and_original_kit_only_AB(self):
        self.assertEqual(len(self.plans),12)
        main=[p for p in self.plans if p['seeded_kit_pair']['green_floor']['purpose']=='seeded_kit_pair']
        for a,b in zip(main[::2],main[1::2]):
            self.assertEqual(context_payload(a),context_payload(b))
            self.assertEqual(a['source_motion'],b['source_motion'])
            self.assertEqual(a['cameras'],b['cameras'])
            self.assertEqual(a['targets'],b['targets'])

    def test_reject_blue_as_green_or_changed_gain(self):
        for field,value in (('floor_id','sport_blue_v1'),('schema','old')):
            bad=deepcopy(self.plans[0]);bad['seeded_kit_pair'][field]=value
            with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)
        bad=deepcopy(self.plans[0]);bad['seeded_kit_pair']['green_floor']['albedo_gain_linear']=[1,0,0]
        with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)

    def test_no_legacy_optin_or_dev_palette_selection(self):
        bad=deepcopy(self.plans[0]);bad.pop('green_seeded_kit_contract')
        with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)
        bad=deepcopy(next(p for p in self.plans if p['seeded_kit_pair']['seed']==1102))
        bad['seeded_kit_pair']['green_floor']['purpose']='palette_check'
        bad['seeded_kit_pair']['paired_context_sha256']=digest(context_payload(bad))
        with self.assertRaises(ValueError):validate_seeded_kit_contract(bad)


if __name__=='__main__':unittest.main()
