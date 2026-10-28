"""集合监督手写loss/梯度、unknown、数值边界；不执行优化更新。"""
from pathlib import Path
import math,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import torch
from candidate_set_supervision import real_window_set_loss,real_domain_set_loss
class Contracts(unittest.TestCase):
    def test_positive_manual_loss_and_gradient(self):
        z=torch.zeros(2,dtype=torch.float32,requires_grad=True);loss=real_window_set_loss(z,[1,0]);loss.backward()
        self.assertAlmostEqual(loss.item(),math.log(3),places=6)
        torch.testing.assert_close(z.grad,torch.tensor([-2/3,1/3]),rtol=1e-6,atol=1e-7)
    def test_no_match_manual_loss_and_gradient(self):
        z=torch.zeros(2,dtype=torch.float32,requires_grad=True);loss=real_window_set_loss(z,[0,0]);loss.backward()
        self.assertAlmostEqual(loss.item(),math.log(3),places=6)
        torch.testing.assert_close(z.grad,torch.tensor([1/3,1/3]),rtol=1e-6,atol=1e-7)
    def test_unknown_has_zero_gradient_and_no_denominator_effect(self):
        z=torch.tensor([0.,10000.,0.],requires_grad=True);loss=real_window_set_loss(z,[1,None,0]);loss.backward()
        self.assertAlmostEqual(loss.item(),math.log(3),places=6);self.assertEqual(z.grad[1].item(),0.)
    def test_empty_known_has_zero_contribution_and_gradient(self):
        z=torch.tensor([3.,-8.],requires_grad=True);loss=real_window_set_loss(z,[None,None]);loss.backward()
        self.assertEqual(loss.item(),0.);self.assertTrue(torch.equal(z.grad,torch.zeros(2)))
    def test_empty_known_large_finite_logits_do_not_overflow(self):
        z=torch.tensor([1e38,1e38],dtype=torch.float32,requires_grad=True);loss=real_window_set_loss(z,[None,None]);loss.backward()
        self.assertEqual(loss.item(),0.);self.assertTrue(torch.equal(z.grad,torch.zeros(2)))
    def test_extreme_logit_stable_and_correct_gradient_direction(self):
        z=torch.tensor([-10000.,10000.],requires_grad=True);loss=real_window_set_loss(z,[1,0]);loss.backward()
        self.assertEqual(loss.item(),20000.);self.assertTrue(torch.isfinite(z.grad).all());self.assertLess(z.grad[0].item(),0.);self.assertGreater(z.grad[1].item(),0.)
    def test_invalid_label_shape_capacity_and_finite_refused(self):
        for logits,labels in [(torch.zeros(2),[1,1]),(torch.zeros(2),[1]),(torch.zeros(2),[True,0]),(torch.tensor([float('nan')]),[0]),(torch.zeros(2,dtype=torch.float64),[1,0])]:
            with self.assertRaises(ValueError):real_window_set_loss(logits,labels)
    def test_real_domain_one_forward_and_window_mean(self):
        class Model(torch.nn.Module):
            def __init__(self):super().__init__();self.linear=torch.nn.Linear(194,1);self.calls=0
            def forward(self,x):self.calls+=1;return self.linear(x)
        model=Model();torch.nn.init.zeros_(model.linear.weight);torch.nn.init.zeros_(model.linear.bias);windows=[]
        for labels,n in (([1,0],3),([0],4),([0,0,0],3)):
            windows.append(dict(x=torch.zeros((len(labels),194)),labels=torch.tensor(labels,dtype=torch.float32),
                known_pairs=len(labels),candidate_pairs=n))
        loss=real_domain_set_loss(model,windows)
        self.assertEqual(model.calls,1);self.assertTrue(torch.isfinite(loss))
        manual=torch.stack([real_window_set_loss(torch.zeros(len(w['labels'])),[int(v) for v in w['labels'].tolist()]) for w in windows]).mean()
        self.assertAlmostEqual(loss.item(),manual.item(),places=6)
    def test_real_domain_rejects_fractional_labels_and_nonfinite_features(self):
        class Model(torch.nn.Module):
            def __init__(self):super().__init__();self.linear=torch.nn.Linear(194,1)
            def forward(self,x):return self.linear(x)
        model=Model()
        for x,y in ((torch.zeros((1,194)),torch.tensor([.5])),
                    (torch.full((1,194),float('inf')),torch.tensor([0.]))):
            window=dict(x=x,labels=y,known_pairs=1,candidate_pairs=1)
            with self.assertRaises(ValueError):real_domain_set_loss(model,[window])
if __name__=='__main__':unittest.main()
