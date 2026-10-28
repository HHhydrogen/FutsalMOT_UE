"""实际原N×1头的记录形状合同，不引入Torch/模型执行。"""
import unittest
from tools.research_ops import trainR_intercept_fit_control as m

class Tensor:
    def __init__(self,shape,values):self.shape=shape;self.values=values
    def detach(self):return self
    def cpu(self):return self
    def reshape(self,*shape):return Tensor((len(self.values),),self.values)
    def tolist(self):return self.values

class Contract(unittest.TestCase):
    def test_native_N1_record_flattens_only_last_unit_dimension(self):
        self.assertEqual(m.logits_from_output(Tensor((3,1),[.5,-.25,0.]),3),[.5,-.25,0.])
    def test_native_N_order_kept(self):
        self.assertEqual(m.logits_from_output(Tensor((2,),[-.1,.1]),2),[-.1,.1])
    def test_other_head_shape_and_wrong_count_rejected(self):
        for shape in ((1,2),(2,2),(3,)):
            with self.assertRaises(ValueError):m.logits_from_output(Tensor(shape,[.1,.2]),2)
    def test_non_scalar_values_not_silently_stored(self):
        with self.assertRaises(ValueError):m.logits_from_output(Tensor((1,1),[[.1]]),1)

if __name__=='__main__':unittest.main()
