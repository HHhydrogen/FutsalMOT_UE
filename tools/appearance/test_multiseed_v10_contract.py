"""新运动身份/源时间/旧scope隔离的针对检查，不执行UE或模型。"""
from copy import deepcopy
import unittest
from prepare_multiseed_v10 import plans
from pose17_seeded_kit_contract import validate_seeded_kit_contract, digest, context_payload
from pose17_multiseed_v10_contract import WINDOWS


class V10ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plans,_=plans()

    def test_three_independent_sources_and_both_lengths(self):
        self.assertEqual([(p['seeded_kit_pair']['seed'],p['frame_count']) for p in self.plans],
            [(s,n) for s in WINDOWS for n in (3,300)])
        self.assertEqual(len({c['source_sequence'] for p in self.plans for c in p['cameras']}),12)
        for p in self.plans:self.assertTrue(validate_seeded_kit_contract(p))

    def test_cannot_fall_back_to_old_green_or_false_optin(self):
        for mode in ('remove','false'):
            p=deepcopy(self.plans[0])
            if mode=='remove':p.pop('v10_multiseed_contract')
            else:p['v10_multiseed_contract']=False
            p['seeded_kit_pair']['paired_context_sha256']=digest(context_payload(p))
            with self.assertRaises(ValueError):validate_seeded_kit_contract(p)

    def test_reject_rebased_time_old_sequence_or_wrong_floor(self):
        for field in ('start','sequence','floor','original_sha','variant'):
            p=deepcopy(self.plans[0]);kit=p['seeded_kit_pair']
            if field=='start':p['start_frame']=0
            elif field=='sequence':p['cameras'][0]['source_sequence']='/Game/FutsalMOT/Sequences/LS_Cam_01'
            elif field=='floor':kit['floor_id']='sport_blue_v1'
            elif field=='original_sha':p['source_motion']['source_frames_sha256']='0'*64
            else:kit['variant']='A';kit['apply_original_seeded_kits']=False
            kit['paired_context_sha256']=digest(context_payload(p))
            with self.assertRaises(ValueError):validate_seeded_kit_contract(p)


if __name__=='__main__':unittest.main()
