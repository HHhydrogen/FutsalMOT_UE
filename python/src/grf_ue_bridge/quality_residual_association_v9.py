"""v9同预算质量门控残差；motion与残差联合训练，未冻结旧已训基线。"""
from .learned_association_model_v8 import FeatureNormalizer,make_model as motion_model
from .pose_quality_features_v9 import MASK_COLUMNS,quality_gate
VARIANTS=('motion_residual','mask','raw','drop','jitter','robust','gated')
AUGMENTATION=dict(motion_residual='clean',mask='clean',raw='clean',drop='drop',jitter='jitter',robust='both',gated='both')
class Adapter:
    def __init__(self,normalizer,scale):self.normalizer=normalizer;self.scale=float(scale)
    def transform(self,raw,*,use_pose=True):return self.normalizer.transform(raw,use_pose=True)+[quality_gate(raw,self.scale)]
    def state(self):return dict(schema='v9_train_R_only_quality_adapter',normalizer=self.normalizer.state(),shape_change_scale=self.scale,input_dim=195,scale_fit='positive_train_R_only')
    @classmethod
    def from_state(cls,value):
        if value['schema']!='v9_train_R_only_quality_adapter' or value['input_dim']!=195:raise ValueError('adapter身份变化')
        return cls(FeatureNormalizer.from_state(value['normalizer']),value['shape_change_scale'])
def make_model(seed,variant):
    if variant not in VARIANTS:raise ValueError('固定消融variant')
    import torch
    from torch import nn
    class Residual(nn.Module):
        def __init__(self):
            super().__init__();self.base=motion_model(seed);self.variant=variant
            with torch.random.fork_rng(devices=[]):
                torch.random.default_generator.manual_seed(seed+93000);self.residual=nn.Sequential(nn.Linear(170,32,device='cpu',dtype=torch.float32),nn.ReLU(),nn.Linear(32,1,device='cpu',dtype=torch.float32))
                nn.init.zeros_(self.residual[-1].weight);nn.init.zeros_(self.residual[-1].bias)
            mask=torch.zeros(170,dtype=torch.float32)
            for j in MASK_COLUMNS:mask[j-24]=1.
            self.register_buffer('mask_only',mask)
        def forward(self,x):
            if x.ndim!=2 or x.shape[1]!=195:raise ValueError('194标准化特征+可观测质量gate')
            motion=torch.cat([x[:,:24],torch.zeros_like(x[:,24:194])],dim=1);base=self.base(motion)
            if self.variant=='motion_residual':z=torch.cat([x[:,:24],torch.zeros_like(x[:,24:170])],dim=1)
            elif self.variant=='mask':z=x[:,24:194]*self.mask_only
            else:z=x[:,24:194]
            residual=.5*torch.tanh(self.residual(z));gate=x[:,194:195] if self.variant=='gated' else 1.
            return base+gate*residual
    return Residual().float()
