"""v8共享Normalizer与64/32 MLP；motion臂在标准化后才遮蔽Pose列。"""
import math
from .learned_association_features_v8 import FEATURE_DIM,POSE_COLUMNS

class FeatureNormalizer:
    def __init__(self,mean,std,count):self.mean=list(mean);self.std=list(std);self.count=count
    @classmethod
    def fit(cls,rows):
        mean=[0.]*FEATURE_DIM;m2=[0.]*FEATURE_DIM;n=0
        for row in rows:
            if len(row)!=FEATURE_DIM or not all(math.isfinite(v) for v in row):raise ValueError('Normalizer仅接收合法train_R特征')
            n+=1
            for j,value in enumerate(row):delta=value-mean[j];mean[j]+=delta/n;m2[j]+=delta*(value-mean[j])
        if not n:raise ValueError('无已知label train_R候选，不能拟合')
        return cls(mean,[max(math.sqrt(max(0.,value/n)),.05) for value in m2],n)
    def transform(self,row,*,use_pose):
        if len(row)!=FEATURE_DIM or not all(math.isfinite(v) for v in row):raise ValueError('特征维度变化或非有限')
        result=[max(-5.,min(5.,(value-mean)/std)) for value,mean,std in zip(row,self.mean,self.std)]
        if not use_pose:
            for j in POSE_COLUMNS:result[j]=0.
        if not all(math.isfinite(v) for v in result):raise ValueError('标准化后非有限')
        return result
    def state(self):return dict(schema='v8_train_R_only_normalizer',mean=self.mean,std=self.std,count=self.count,feature_dim=FEATURE_DIM,pose_columns=list(POSE_COLUMNS),fit_scope='known_label_train_R_only',std_floor=.05,clip_abs=5.,guard_stage='before_any_training_or_evaluation')
    @classmethod
    def from_state(cls,value):
        if value['feature_dim']!=FEATURE_DIM or value['pose_columns']!=list(POSE_COLUMNS) or value.get('std_floor')!=.05 or value.get('clip_abs')!=5.:raise ValueError('Normalizer身份不符')
        return cls(value['mean'],value['std'],value['count'])

def make_model(seed):
    import torch
    from torch import nn
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        model=nn.Sequential(nn.Linear(FEATURE_DIM,64,device="cpu",dtype=torch.float32),nn.ReLU(),nn.Linear(64,32,device="cpu",dtype=torch.float32),nn.ReLU(),nn.Linear(32,1,device="cpu",dtype=torch.float32)).float()
    return model

def probability_to_cost(probability,stage_threshold):
    if not math.isfinite(probability) or not 0<=probability<=1 or stage_threshold not in (.8,.7):raise ValueError('sigmoid概率/原stage阈值无效')
    return dict(accepted=probability>=.5,cost=max(0.,min(1.,stage_threshold+(.5-probability))))

def window_BCE(model,window_features,labels):
    """一个window内已知候选BCE均值；unknown不计，空监督保持零梯度图不猜步跳过。"""
    import torch
    from torch.nn import functional as F
    selected=[i for i,label in enumerate(labels) if label is not None]
    if any(labels[i] not in (0,1) for i in selected):raise ValueError('label只能0/1/None')
    if not selected:return sum(parameter.sum()*0 for parameter in model.parameters()),dict(known=0,unknown=len(labels))
    device=next(model.parameters()).device
    x=torch.tensor([window_features[i] for i in selected],dtype=torch.float32,device=device);y=torch.tensor([labels[i] for i in selected],dtype=torch.float32,device=device)
    return F.binary_cross_entropy_with_logits(model(x).reshape(-1),y),dict(known=len(selected),unknown=len(labels)-len(selected))
