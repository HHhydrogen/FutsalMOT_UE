"""幅度探针的冻结forward等价、唯一因素、矩阵和零更新边界。"""
from pathlib import Path
import sys
import unittest
import residual_amplitude_probe as probe


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(Path('D:/projects/FutsalMOT_Research/code/f473bf25f8bd31fb3a48829207fd46487d90752f59ec10fb966342614a9fc948/python/src')))
        from grf_ue_bridge.quality_residual_association_v9 import make_model
        import torch
        cls.torch=torch;torch.set_num_threads(1);cls.models=[]
        for name in probe.PARAMETERS['methods']:
            m=make_model(20261024,name).eval()
            with torch.no_grad():m.residual[-1].weight.fill_(.013);m.residual[-1].bias.fill_(.07)
            cls.models.append(m)
        cls.x=torch.linspace(-1,1,780,dtype=torch.float32).reshape(4,195);cls.x[:,-1]=torch.tensor([0.,.2,.7,1.])

    def test_original_bound_matches_original_forward_bitwise(self):
        for m in self.models:self.assertTrue(self.torch.equal(m(self.x),probe.with_bound(m,.5)(self.x)))

    def test_only_residual_amplitude_changes_and_zero_gate_stays_base(self):
        t=self.torch
        for m in self.models:
            base=m.base(t.cat([self.x[:,:24],t.zeros_like(self.x[:,24:194])],dim=1))
            original=m(self.x);changed=probe.with_bound(m,2.)(self.x)
            self.assertTrue(t.allclose(changed-base,4*(original-base),atol=1e-6,rtol=1e-5))
            if m.variant=='gated':self.assertTrue(t.equal(changed[0],original[0]))
            self.assertFalse(t.equal(changed,original))

    def test_no_weight_or_RNG_updates(self):
        t=self.torch
        for m in self.models:
            before={k:v.clone() for k,v in m.state_dict().items()};rng=t.get_rng_state().clone()
            for _ in range(3):probe.with_bound(m,2.)(self.x)
            self.assertTrue(all(t.equal(before[k],v) for k,v in m.state_dict().items()));self.assertTrue(t.equal(rng,t.get_rng_state()))

    def test_unregistered_coefficient_rejected(self):
        for bound in (float('nan'),0.,1.,4.):
            with self.assertRaises(ValueError):probe.with_bound(self.models[0],bound)

    def test_full108_matrix_without_seed_selection(self):
        old=[]
        for fold in ('game4','game6','game9'):
            for seed in (20261024,20261025,20261026):
                for pool in ('balanced','hard_enriched'):
                    for method in ('motion','motion_residual','gated'):
                        for seq in (fold,'external1','external2'):
                            old.append(dict(job_id=str(len(old)),kind='new_RS',fold=fold,seed=seed,pool=pool,method=method,sequence=seq))
        jobs=probe.matrix(dict(tracking_matrix=old));self.assertEqual(len(jobs),108);self.assertEqual(len({j['job_id'] for j in jobs}),108)
        self.assertEqual(sum(j['original']['method']=='gated' for j in jobs),54)


if __name__=='__main__':unittest.main()
