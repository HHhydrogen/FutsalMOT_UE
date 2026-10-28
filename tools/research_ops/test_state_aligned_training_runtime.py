"""新R来源学习身份/动态pair预算/原强motion缓存调用合同；不执行训练。"""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys,unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import state_aligned_training_runtime as rt

def config():return dict(schema='state_aligned_R_recorded_training_protocol_v1',training_matrix=rt.expected_matrix(),parameters=deepcopy(rt.PARAMETERS),
    test116187_sealed=True,approved_by='root',training_authorized=True,tracking_authorized=False)
def ledger(regime):
    real=[dict(window_uid='R'+str(i%1000),epoch=i//1000,candidate_pairs=4+i%3,labelled_pairs=2+i%2) for i in range(3000)]
    synthetic=[dict(window_uid='S'+str(i),epoch=0,candidate_pairs=5,labelled_pairs=3) for i in range(1000)]
    table=dict(real=real,synthetic=synthetic);logs=[];chain='0'*64
    for i in range(1000):
        rr=deepcopy(real[3*i:3*i+3]);ss=deepcopy(synthetic[i:i+1]) if regime=='RS' else []
        row=dict(actual_update=i+1,update_index=i,R_windows=3,S_windows=int(regime=='RS'),real=rr,synthetic=ss,
            R_pairs=sum(x['candidate_pairs'] for x in rr),R_known_pairs=sum(x['labelled_pairs'] for x in rr),
            S_pairs=sum(x['candidate_pairs'] for x in ss),S_known_pairs=sum(x['labelled_pairs'] for x in ss),learning_rates=[.001],grad_l2=.1,step_wall_seconds=.01)
        chain=hashlib.sha256((chain+rt.canonical(row)).encode()).hexdigest();logs.append(dict(row,chain_sha256=chain))
    return table,logs
def rechain(logs):
    chain='0'*64
    for row in logs:
        clean=dict(row);clean.pop('chain_sha256');chain=hashlib.sha256((chain+rt.canonical(clean)).encode()).hexdigest();row['chain_sha256']=chain

class Contracts(unittest.TestCase):
    def test_fixed18_and_original_motion_no_augmentation(self):
        cfg=config();rt.validate_matrix(cfg);self.assertEqual(len(cfg['training_matrix']),18)
        for key,value in [('training_matrix',cfg['training_matrix'][:-1]),('parameters',dict(rt.PARAMETERS,epoch_augmentation=True)),
                ('parameters',dict(rt.PARAMETERS,use_pose=True)),('parameters',dict(rt.PARAMETERS,updates=999)),('test116187_sealed',False)]:
            bad=deepcopy(cfg);bad[key]=value
            with self.assertRaises(ValueError):rt.validate_matrix(bad)
    def test_R_RS_full_dynamic_pair_sequence(self):
        for regime in rt.REGIMES:
            table,logs=ledger(regime);self.assertEqual(rt.audit_steps(logs,table,regime),logs[-1]['chain_sha256'])
            table['real'][0],table['real'][1]=table['real'][1],table['real'][0]
            with self.assertRaises(ValueError):rt.audit_steps(logs,table,regime)
    def test_known_pair_not_window_and_no_hidden_S(self):
        for regime,key,value in [('RS','R_known_pairs',3),('R','S_windows',1),('RS','learning_rates',[.002]),('R','grad_l2',-1.)]:
            table,logs=ledger(regime);logs[0][key]=value;rechain(logs)
            with self.assertRaises(ValueError):rt.audit_steps(logs,table,regime)
    def test_exact_window_cache_no_epoch_augmentation(self):
        table,_=ledger('RS');calls=[]
        cache=SimpleNamespace(get=lambda domain,uid:calls.append((domain,uid)) or dict(domain=domain,uid=uid))
        for regime in rt.REGIMES:
            calls.clear();ctx=dict(table=table,regime=regime,cache=cache);batch=rt.batch(ctx,1)
            self.assertEqual(batch['r'],table['real'][3:6]);self.assertEqual(batch['s'],table['synthetic'][1:2] if regime=='RS' else [])
            self.assertEqual(calls,[('real',v['window_uid']) for v in batch['r']]+[('synthetic',v['window_uid']) for v in batch['s']])
        with self.assertRaises(ValueError):rt.batch(ctx,1000)
        with self.assertRaises(ValueError):rt.batch(ctx,0,'R')
    def test_independent_method_state_preserves_original_normalizer(self):
        state=dict(mean=[1.,2.],scale=[3.,4.]);ctx=dict(regime='R',normalizer=SimpleNamespace(state=lambda:state),cfg=dict(source_training_protocol=dict(path='old',sha256='a'*64)))
        extra=rt.extra(ctx);self.assertEqual(extra['schema'],'state_aligned_strongmotion_method_state_v1')
        self.assertEqual(extra['normalizer'],state);self.assertFalse(extra['use_pose']);self.assertFalse(extra['epoch_augmentation'])

if __name__=='__main__':unittest.main()
