"""C新增预算与域身份的针对检查，不镜像神经网络实现。"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('C_contract',Path(__file__).with_name('substitution_C_runtime.py'))
rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)

class CContract(unittest.TestCase):
    def fixture(self):
        def window(uid,game):return dict(window_uid=uid,domain='real',game=game,candidates=[dict(label=0),dict(label=1),dict(label=None)])
        base=[window('b'+str(i),'game6' if i<500 else 'game9') for i in range(1000)]
        extra=[window('e'+str(i),'game6' if i<500 else 'game9') for i in range(1000)]
        def row(w,epoch=0):return dict(window_uid=w['window_uid'],domain='real',epoch=epoch,candidate_pairs=3,labelled_pairs=2)
        table=dict(real=[row(w,epoch) for epoch in range(3) for w in base])
        plan=dict(extra_R=[dict(row(w),source_allocation='extra_R') for w in extra])
        return base,extra,table,plan
    def test18_C_matrix_is_independent_and_fixed(self):
        cfg=dict(schema='substitution_C4000R_training_v1',training_matrix=rt.matrix(),parameters=rt.PARAMETERS,test116187_sealed=True)
        rt.matrix_gate(cfg);self.assertEqual(len(rt.matrix()),18)
        bad=deepcopy(cfg);bad['parameters']['extra_R_alpha']=1
        with self.assertRaises(ValueError):rt.matrix_gate(bad)
    def test_real_only_cache_preserves_base_three_epochs(self):
        b,e,t,p=self.fixture();pools=rt.exposure_gate(b,e,t,p,'game4')
        self.assertEqual(len(pools['real']),2000);self.assertEqual(pools['synthetic'],{})
        calls=[]
        load=rt.batch_loader(t,p,lambda row:calls.append(row['domain']) or row)
        out=load(0);self.assertEqual(calls,['real']*4);self.assertEqual(out['r'],t['real'][:3])
        self.assertEqual(out['r_extra'],p['extra_R'][:1]);self.assertEqual(out['s'],[])
    def test_no_heldout_duplicate_or_S_disguise(self):
        for change in ('heldout','duplicate','S'):
            b,e,t,p=self.fixture()
            if change=='heldout':e[0]['game']='game4'
            elif change=='duplicate':e[0]['window_uid']=b[0]['window_uid']
            else:p['extra_R'][0]['domain']='synthetic'
            with self.assertRaises(ValueError):rt.exposure_gate(b,e,t,p,'game4')
    def test_pair_and_epoch_budget_cannot_be_hidden(self):
        for change in ('pair','epoch','allocation'):
            b,e,t,p=self.fixture()
            if change=='pair':p['extra_R'][0]['labelled_pairs']=1
            elif change=='epoch':t['real'][0]['epoch']=1
            else:p['extra_R'][0]['source_allocation']='base_R'
            with self.assertRaises(ValueError):rt.exposure_gate(b,e,t,p,'game4')

if __name__=='__main__':unittest.main()
