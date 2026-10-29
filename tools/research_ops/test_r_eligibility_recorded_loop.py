"""记录扩展的纯内存夹具；不导入真实Torch，不写文件，不执行SGD。"""
from copy import deepcopy
import hashlib
import io
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import r_eligibility_recorded_loop as loop
import training_journal as original
from r_candidate_eligibility_method import label_counts

def accounting(masks=None):
    masks=masks or [[True,False]]*3;windows=[]
    for i,mask in enumerate(masks):
        counts=label_counts([1,None,0],[mask[0],True,mask[1]])
        windows.append(dict(window_uid='w'+str(i),binding_sha256='a'*64,sidecar_sha256='b'*64,
            source=dict(teacher_regime='R',teacher_seed=20261024,source_stage='high_score'),
            known_labels=[1,0],known_candidate_UIDs=['p'+str(i),'n'+str(i)],known_scoring_eligible=list(mask),**counts))
    keys=list(counts);totals={k:sum(w[k] for w in windows) for k in keys}
    totals.update(R_scoring_eligible_unknown_pairs=totals['kept_unknown_pairs'],R_effective_unknown_pairs=0)
    return dict(schema=loop.ACCOUNTING_SCHEMA,windows=windows,totals=totals,real_window_count=3,domain_forward_calls=1,
        forwarded_known_pairs=6,original_known_order_preserved=True,original_labels_unchanged=True,
        empty_effective_windows_contribute_graph_zero=True,window_resampling=False,unknown_features_forwarded=False,
        unknown_labels_used_for_loss=False,known_mask_applied_after_unreduced_BCE=True,numeric_dtype='float32')

def batch(index=0,rs=False):
    rows=[dict(window_uid='w'+str(i),epoch=0,candidate_pairs=3,labelled_pairs=2) for i in range(3)]
    real=[dict(window_uid=r['window_uid'],candidate_pairs=3,known_pairs=2) for r in rows]
    synthetic=[dict(window_uid='s',candidate_pairs=2,known_pairs=1)] if rs else []
    return dict(index=index,r=rows,s=[dict(window_uid='s',epoch=0)] if rs else [],real=real,synthetic=synthetic)

def spec(diagnostic=True,rs=False):
    binding=dict(record_extension_schema=loop.EXTENSION_SCHEMA)
    if diagnostic:binding['diagnostic_only_one_update_not_formal_training']=True
    return dict(schema='full_training_record_spec_v1',updates=1000,R_per_update=3,S_per_update=int(rs),checkpoint_interval=50,
        test116187_sealed=True,binding=binding,runtime=dict(device='cpu_numeric_fixture_simulation',record_extension_schema=loop.EXTENSION_SCHEMA))

class MemoryJournal(loop.EligibilityJournal):
    instances=[]
    def __init__(self,directory,record_spec):
        self.spec=deepcopy(record_spec);self.root=Path('in_memory_not_created');self.pending=None;self.closed=False
        self.real_groups=False;self.completed=0;self.chain='0'*64;self.checkpoints={};self.lines=[];self.steps=io.StringIO();self.events=io.StringIO()
        self.totals={k:0 for k in ('R_windows','S_windows','R_pairs','S_pairs','R_known_pairs','S_known_pairs',*loop.EFFECTIVE_FIELDS)}
        self.instances.append(self)
    def begin_step(self,index,real,synthetic):
        if index!=self.completed:raise ValueError('序列不符')
        self.pending=dict(update_index=index,actual_update=index+1,real=deepcopy(real),synthetic=deepcopy(synthetic))
    def _line(self,stream,value):self.lines.append(deepcopy(value))
    def save_checkpoint(self,*args,**kwargs):self.checkpoints[self.completed]=dict(completed_updates=self.completed)
    def event(self,*args,**kwargs):pass
    def close(self):self.closed=True

class Tensor:
    def __init__(self,value,model=None,gradient=0):self.value=value;self.model=model;self.gradient=gradient
    def __add__(self,other):return Tensor(self.value+other.value,self.model or other.model,self.gradient+other.gradient)
    def __truediv__(self,other):return Tensor(self.value/other,self.model,self.gradient/other)
    def backward(self):
        for p in self.model.parameters():p.grad=None if self.gradient is None else Tensor(self.gradient)
    def detach(self):return self
    def reshape(self,*args):return self
    def item(self):return self.value
    def __float__(self):return float(self.value)

class Check:
    def __init__(self,value):self.value=value
    def item(self):return self.value
    def all(self):return self

class Model:
    def __init__(self):self.params=[SimpleNamespace(grad=None),SimpleNamespace(grad=None)]
    def parameters(self):return self.params

class OptimizerStub:
    """只计接口调用，不持有或更新任何模型数值。"""
    def __init__(self,model):self.model=model;self.steps=0;self.param_groups=[dict(lr=.001)]
    def zero_grad(self,**kwargs):
        for p in self.model.parameters():p.grad=None
    def step(self):self.steps+=1

TORCH=SimpleNamespace(isfinite=lambda v:Check(all(math.isfinite(x.value) for x in v) if isinstance(v,list) else math.isfinite(v.value)),
    cat=lambda tensors:tensors,count_nonzero=lambda values:Tensor(sum(x.value!=0 for x in values)),
    linalg=SimpleNamespace(vector_norm=lambda values:Tensor(math.sqrt(sum(x.value*x.value for x in values)))))

class Contracts(unittest.TestCase):
    def journal(self):
        j=MemoryJournal(None,spec());j.begin_step(0,batch()['r'],[]);return j
    def test_accounting_is_in_original_exposure_chain_and_original_counts_stay(self):
        j=self.journal();a=accounting();j.record_mask_accounting(a)
        with patch.object(original,'atomic'):
            j.commit_step(loss=1.,real_loss=1.,synthetic_loss=None,learning_rates=[.001],grad_l2=0.,R_pairs=9,S_pairs=0,R_known_pairs=6,S_known_pairs=0,step_wall_seconds=0.)
        row=j.lines[0];chain=row.pop('chain_sha256')
        self.assertEqual(chain,hashlib.sha256(('0'*64+original.canonical(row)).encode()).hexdigest())
        self.assertEqual(row['R_mask_accounting'],a);self.assertEqual(j.totals['R_known_pairs'],6)
        self.assertEqual(j.totals['R_effective_known_pairs'],3);self.assertEqual(j.totals['R_effective_unknown_pairs'],0)
        self.assertEqual(j.totals['R_scoring_eligible_unknown_pairs'],3)
    def test_empty_effective_counts_allowed_without_overwriting_raw_known(self):
        j=self.journal();t=j.record_mask_accounting(accounting([[False,False]]*3))
        self.assertEqual(t['R_effective_known_pairs'],0);self.assertEqual(t['R_zero_effective_windows'],3)
        self.assertEqual(sum(x['labelled_pairs'] for x in j.pending['real']),6)
    def test_same_mask_cannot_be_recorded_twice_or_commit_without_it(self):
        j=self.journal()
        with self.assertRaises(ValueError):j.commit_step()
        j.record_mask_accounting(accounting())
        with self.assertRaises(ValueError):j.record_mask_accounting(accounting())
    def test_wrong_counts_labels_or_raw_budget_rejected(self):
        for edit in (lambda a:a['windows'][0].update(kept_positive_pairs=99),lambda a:a['windows'][0].update(known_labels=[True,0]),
            lambda a:a['windows'][0].update(raw_known_pairs=1),lambda a:a['totals'].update(kept_unknown_pairs=0),lambda a:a.update(forwarded_known_pairs=3)):
            a=accounting();edit(a)
            with self.assertRaises(ValueError):self.journal().record_mask_accounting(a)
    def test_mask_UID_order_schema_and_sha_not_optional(self):
        for edit in (lambda a:a['windows'].reverse(),lambda a:a['windows'][0].update(sidecar_sha256='bad'),lambda a:a.update(schema='old'),lambda a:a.update(window_resampling=True)):
            a=accounting();edit(a)
            with self.assertRaises(ValueError):self.journal().record_mask_accounting(a)
    def test_extension_schema_required_without_calling_base_init(self):
        bad=spec();bad['runtime']['record_extension_schema']='old'
        with patch.object(original.TrainingJournal,'__init__') as init:
            with self.assertRaises(ValueError):loop.EligibilityJournal('not_created',bad)
            init.assert_not_called()
    def run_loop(self,rs=False,mask=None,gradient=0,diagnostic=True):
        model=Model();optimizer=OptimizerStub(model);a=accounting(mask);MemoryJournal.instances=[]
        r=lambda m,w:(Tensor(0.,m,gradient),a)
        s=lambda m,w:Tensor(3.,m,3.)
        n=1 if diagnostic else 1000
        with patch.dict(sys.modules,torch=TORCH),patch.object(loop,'EligibilityJournal',MemoryJournal),patch.object(original,'atomic'),\
             patch.object(original,'sha',return_value='fixture'),patch.object(original,'write_new'):
            result=loop.train(None,spec(diagnostic,rs),model,optimizer,(batch(i,rs) for i in range(n)),r,s,diagnostic_updates=1 if diagnostic else None)
        return result,optimizer,MemoryJournal.instances[-1]
    def test_empty_pure_R_still_optimizer_step_and_zero_grad(self):
        result,opt,j=self.run_loop(mask=[[False,False]]*3)
        self.assertEqual(opt.steps,1);self.assertEqual(result['effective_totals']['R_zero_effective_windows'],3)
        self.assertEqual(set(j.checkpoints),{0,1});self.assertEqual(j.lines[0]['grad_l2'],0.)
        self.assertEqual(result['schema'],'R_candidate_scoring_eligibility_one_step_diagnostic_receipt_v1')
    def test_empty_R_with_S_retains_S_over_three_and_nonzero_gradient(self):
        _,opt,j=self.run_loop(rs=True,mask=[[False,False]]*3)
        self.assertEqual(opt.steps,1);self.assertEqual(j.lines[0]['synthetic_loss'],3.);self.assertEqual(j.lines[0]['loss'],1.)
        self.assertGreater(j.lines[0]['grad_l2'],0.)
    def test_empty_R_detached_or_nonzero_gradient_rejected_before_step(self):
        for gradient in (None,1):
            with self.assertRaises(ValueError):self.run_loop(mask=[[False,False]]*3,gradient=gradient)
    def test_formal_stub_consumes_all1000_and_original21_checkpoints(self):
        result,opt,j=self.run_loop(mask=[[False,False]]*3,diagnostic=False)
        self.assertEqual(opt.steps,1000);self.assertEqual(set(j.checkpoints),set(range(0,1001,50)))
        self.assertEqual(result['totals']['R_windows'],3000);self.assertEqual(result['totals']['R_known_pairs'],6000)
        self.assertEqual(result['totals']['R_zero_effective_windows'],3000);self.assertEqual(result['totals']['R_effective_known_pairs'],0)
        self.assertEqual(result['loop_receipt_schema'],'R_candidate_scoring_eligibility_formal_loop_receipt_v1')

if __name__=='__main__':unittest.main()
