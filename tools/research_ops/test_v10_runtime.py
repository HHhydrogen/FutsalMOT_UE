"""v10矩阵、真实曝光复用与实际日志预算的必要CPU检查。"""
from copy import deepcopy
import hashlib
import unittest

import v10_runtime as v


def fixtures():
    real=[dict(window_uid='r%04d'%i,domain='real',game='game6',candidates=[dict(label=1)]) for i in range(1000)]
    synthetic=[dict(window_uid='s%04d'%i,domain='synthetic',synthetic_seed=(1042,1044,1048,1131)[i//250],candidates=[dict(label=0)]) for i in range(1000)]
    table=dict(real=[dict(window_uid=w['window_uid'],domain='real',epoch=e,candidate_pairs=1,labelled_pairs=1) for e in range(3) for w in real],
               synthetic=[dict(window_uid=w['window_uid'],domain='synthetic',epoch=0,candidate_pairs=1,labelled_pairs=1) for w in synthetic])
    return real,synthetic,table


def logs(table,wrong=False):
    result=[];chain='0'*64
    for i in range(1000):
        row=dict(update_index=i,actual_update=i+1,R_windows=3,S_windows=1,
                 real=deepcopy(table['real'][i*3:i*3+3]),synthetic=deepcopy(table['synthetic'][i:i+1]))
        if wrong and i==0:row['real'][0]['window_uid']='wrong_even_with_recomputed_chain'
        chain=hashlib.sha256((chain+v.canonical(row)).encode()).hexdigest()
        result.append(dict(row,chain_sha256=chain))
    return result


class RuntimeTests(unittest.TestCase):
    def test_exact54_matrix_and_fixed_budget(self):
        cfg=dict(schema='v10_recorded_association_training_v1',training_matrix=v.expected_matrix(),parameters=v.PARAMETERS.copy(),test116187_sealed=True)
        self.assertEqual(len(cfg['training_matrix']),54);v.validate_matrix(cfg)
        cfg['parameters']['amp']=True
        with self.assertRaises(ValueError):v.validate_matrix(cfg)

    def test_real_order_must_equal_original_and_S_unique_seed_quota(self):
        real,syn,table=fixtures();v.validate_exposures(real,syn,table,deepcopy(table),'game4')
        bad=deepcopy(table);bad['real'][0],bad['real'][1]=bad['real'][1],bad['real'][0]
        with self.assertRaises(ValueError):v.validate_exposures(real,syn,bad,table,'game4')
        syn[0]['synthetic_seed']=1102
        with self.assertRaises(ValueError):v.validate_exposures(real,syn,table,table,'game4')

    def test_heldout_real_and_all_unknown_windows_rejected(self):
        real,syn,table=fixtures();real[0]['game']='game4'
        with self.assertRaises(ValueError):v.validate_exposures(real,syn,table,table,'game4')
        real[0]['game']='game6';syn[0]['candidates']=[dict(label=None)]
        with self.assertRaises(ValueError):v.validate_exposures(real,syn,table,table,'game4')

    def test_valid_recomputed_chain_cannot_hide_wrong_R_order(self):
        _,_,table=fixtures();good=logs(table)
        self.assertEqual(v.audit_steps(good,table),good[-1]['chain_sha256'])
        with self.assertRaises(ValueError):v.audit_steps(logs(table,wrong=True),table)
        with self.assertRaises(ValueError):v.audit_steps(good[:-1],table)


if __name__=='__main__':unittest.main()
