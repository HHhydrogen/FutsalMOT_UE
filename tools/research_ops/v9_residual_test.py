"""零初始残差、质量回退与同参消融；只用小CPU张量。"""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'python/src'))
from grf_ue_bridge.quality_residual_association_v9 import make_model,VARIANTS
import torch
torch.set_num_threads(1)
class Tests(unittest.TestCase):
    def test_all_variants_same_initialization_and_parameter_count(self):
        models=[make_model(20261024,v) for v in VARIANTS];first=models[0].state_dict();counts={sum(p.numel() for p in m.parameters()) for m in models};self.assertEqual(len(counts),1)
        for model in models:self.assertTrue(all(torch.equal(first[k],v) for k,v in model.state_dict().items()))
        x=torch.ones((5,195));expected=models[0].base(torch.cat([x[:,:24],torch.zeros((5,170))],1))
        for model in models:self.assertTrue(torch.equal(model(x),expected))
    def test_quality_zero_returns_own_motion_branch_even_after_residual_changes(self):
        model=make_model(1,'gated');model.residual[-1].bias.data.fill_(2);x=torch.ones((2,195));x[:,-1]=0
        expected=model.base(torch.cat([x[:,:24],torch.zeros((2,170))],1));self.assertTrue(torch.equal(model(x),expected))
        x[:,-1]=1;self.assertTrue(torch.all((model(x)-expected).abs()<=.5))
    def test_missing_coordinates_cannot_change_mask_only_model(self):
        from grf_ue_bridge.pose_quality_features_v9 import COORD_COLUMNS
        model=make_model(1,'mask');model.residual[-1].weight.data.fill_(.1);x=torch.ones((2,195));y=x.clone()
        for j in COORD_COLUMNS:y[:,j]=-4
        self.assertTrue(torch.equal(model(x),model(y)))
if __name__=='__main__':unittest.main()
