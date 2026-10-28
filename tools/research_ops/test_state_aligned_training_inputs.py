"""新R曝光来源/原S顺序的CPU合同；不调用真实模型或训练。"""
from copy import deepcopy
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import state_aligned_training_inputs as m
import v8_pairs

def fixture(fold='game4',seed=20261024):
    real=[]
    for seq,game in m.SOURCES.items():
        if game==fold:continue
        for index in range(500):
            n=index+4;uids=[f'{seq}:{x:06d}:000000' for x in (n-3,n-2,n-1)];candidate=f'{seq}:{n:06d}:000000'
            history=[dict(uid=uid,timestamp_sec=(n-4+i)/25.) for i,uid in enumerate(uids)]
            labels=[0,None] if index%2 else [1,0,None]
            predictions=[dict(uid=candidate+str(j),timestamp_sec=(n-1)/25.) for j in range(len(labels))]
            uid=m.digest([fold,seq,index]);meta=dict(window_uid=uid,teacher_regime='R',teacher_seed=20261024,fold=fold,
                source_stage='high_score',candidate_scope='whole_original_high_score_stage_not_exact_enabled_subset',
                history_UIDs=uids,candidate_UIDs=[x['uid'] for x in predictions],pair_labels=labels)
            real.append(dict(window_uid=uid,domain='real',sequence=seq,game=game,fps=25,history=history,
                candidates=[dict(prediction=p,label=l) for p,l in zip(predictions,labels)],aligned_bank_metadata=meta,
                gap_requested_sec=None,supervision=dict(teacher_forced_history=False)))
    synthetic=[dict(window_uid='S'+str(i),domain='synthetic',synthetic_seed=(1042,1044,1048,1131)[i//250],
        candidates=[dict(prediction={},label=1),dict(prediction={},label=0),dict(prediction={},label=None)]) for i in range(1000)]
    old_real=[dict(w,window_uid='old'+w['window_uid']) for w in real]
    original=v8_pairs.exposures(old_real,synthetic,seed)
    return real,synthetic,original

class Inputs(unittest.TestCase):
    def test18_matrix_and_absolute_identity(self):
        matrix=m.expected_matrix();self.assertEqual(len(matrix),18);self.assertEqual(len({(x['fold'],x['seed'],x['regime']) for x in matrix}),18)
        self.assertEqual(m.AUGMENTATION,'none_original_strongmotion')
    def test_original_SHA_order_R_and_exact_original_S(self):
        for seed in m.SEEDS:
            real,s,old=fixture(seed=seed);plan=m.make_plan(real,old,'game4',seed,v8_pairs.exposures,original_table_ref={'path':'old','sha256':'a'})
            self.assertEqual(plan['real'],v8_pairs.exposures(real,[],seed)['real']);self.assertEqual(plan['synthetic'],old['synthetic'])
            self.assertNotEqual(plan['real'],old['real']);m.validate_plan(real,s,plan,old,'game4',seed,v8_pairs.exposures)
            self.assertEqual(plan['accounting']['real']['window_exposures'],3000);self.assertEqual(plan['accounting']['synthetic_RS']['window_exposures'],1000)
    def test_R_RS_same_R_plan_unknown_and_no_positive_preserved(self):
        real,s,old=fixture();plan=m.make_plan(real,old,'game4',m.SEEDS[0],v8_pairs.exposures)
        pools=m.validate_plan(real,s,plan,old,'game4',m.SEEDS[0],v8_pairs.exposures)
        self.assertEqual(plan['regimes_share_R'],['R','RS']);self.assertTrue(any(not any(c['label']==1 for c in w['candidates']) for w in pools['real'].values()))
        self.assertTrue(all(w['candidates'][-1]['label'] is None for w in pools['real'].values()))
    def test_mutated_S_or_R_order_or_pair_count_rejected(self):
        real,s,old=fixture();p=m.make_plan(real,old,'game4',m.SEEDS[0],v8_pairs.exposures)
        for edit in (lambda x:x['synthetic'].reverse(),lambda x:x['real'].reverse(),lambda x:x['real'][0].update(labelled_pairs=999)):
            changed=deepcopy(p);edit(changed)
            with self.assertRaises(ValueError):m.validate_plan(real,s,changed,old,'game4',m.SEEDS[0],v8_pairs.exposures)
    def test_heldout_RS_teacher_requested_gap_and_unknown_labels_rejected(self):
        real,_,_=fixture()
        for edit in (lambda w:w.update(game='game4'),lambda w:w['aligned_bank_metadata'].update(teacher_regime='RS'),
            lambda w:w.update(gap_requested_sec=.2),lambda w:w['candidates'][0].update(label=None)):
            values=deepcopy(real);edit(values[0])
            with self.assertRaises(ValueError):m.validate_pool(values,'game4')
    def test_future_or_short_history_rejected(self):
        real,_,_=fixture()
        for edit in (lambda w:w['history'].pop(),lambda w:w['history'][-1].update(timestamp_sec=10000)):
            values=deepcopy(real);edit(values[0])
            with self.assertRaises(ValueError):m.validate_pool(values,'game4')
    def test_no_refit_and_S_augmentation_identity(self):
        real,s,old=fixture();p=m.make_plan(real,old,'game4',m.SEEDS[0],v8_pairs.exposures)
        self.assertFalse(p['R_requested_gap_strata_preserved']);self.assertFalse(p['equal_pair_or_FLOPs_claim']);self.assertTrue(p['S_order_and_rows_exact_original'])
        p['augmentation']='both'
        with self.assertRaises(ValueError):m.validate_plan(real,s,p,old,'game4',m.SEEDS[0],v8_pairs.exposures)
    def test_insufficient_unique_pool_and_illegal_seed_rejected(self):
        real,_,old=fixture()
        with self.assertRaises(ValueError):m.make_plan(real[:-1],old,'game4',m.SEEDS[0],v8_pairs.exposures)
        with self.assertRaises(ValueError):m.make_plan(real,old,'game4',99,v8_pairs.exposures)

if __name__=='__main__':unittest.main()
