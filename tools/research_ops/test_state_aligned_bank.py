"""纯CPU候选合同：不加载真实GT、权重、媒体或执行训练。"""
from copy import deepcopy
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import state_aligned_bank as b

def row(seq='SNMOT-097',number=4):
    return dict(fold='game4',regime='R',seed=20261024,sequence=seq,stage='high_score',learned_active=True,
        history_UIDs=[seq+':%06d:000001'%(i+1) for i in range(3)],history_frames=[1,2,3],history_status='trusted_consistent_history',query_GT_id='0',
        candidate_UIDs=[seq+':%06d:%06d'%(number,i+1) for i in range(3)],pair_labels=[1,0,None],frame_number=number,model_id='teacher',
        job_id='job'+seq,track_id=1,row_index=0)

class Bank(unittest.TestCase):
    def test_unknown_short_mixed_inactive_excluded_not_relabelled(self):
        for changes,reason in [({'history_status':'history_unknown'},'history_not_trusted_single_anchor'),
                ({'history_UIDs':['a'],'history_frames':[1]},'history_not_three'),({'learned_active':False},'learned_not_active'),
                ({'pair_labels':[None,None,None]},'no_known_pair'),({'stage':'low_score'},'not_high_score_stage')]:
            value=row();value.update(changes);self.assertIn(reason,b.classify(value,'game4'))
    def test_RS_teacher_heldout_and_seed_refused(self):
        for changes in ({'regime':'RS'},{'sequence':'SNMOT-060'},{'seed':20261025}):
            value=row();value.update(changes)
            with self.assertRaises(ValueError):b.select_bank([value],'game4')
    def test_future_history_and_duplicate_candidates_refused(self):
        value=row();value['history_frames']=[1,2,4]
        with self.assertRaises(ValueError):b.classify(value,'game4')
        value=row();value['candidate_UIDs'][1]=value['candidate_UIDs'][0]
        with self.assertRaises(ValueError):b.classify(value,'game4')
    def test_fixed1000_unique_source500_deterministic_no_best(self):
        rows=[row(seq,n) for seq in ('SNMOT-097','SNMOT-151') for n in range(4,509)]
        first=b.select_bank(rows,'game4');second=b.select_bank(reversed(rows),'game4')
        self.assertEqual(first['selected_order_sha256'],second['selected_order_sha256'])
        self.assertEqual(first['selected_counts']['windows'],1000)
        self.assertEqual(first['selected_counts']['unknown_pairs'],1000)
        self.assertEqual({v['selected_unique'] for v in first['source_counts'].values()},{500})
        self.assertFalse(first['training_authorized'])
    def test_no_positive_not_filtered_and_shortage_never_filled(self):
        value=row();value['pair_labels']=[0,0,None]
        result=b.select_bank([value,deepcopy(value)],'game4')
        self.assertEqual(result['selected_counts']['windows'],1);self.assertEqual(result['selected_counts']['no_positive_windows'],1)
        self.assertEqual(result['filter_counts']['duplicate_windows_removed'],1)
        self.assertEqual(result['status'],'insufficient_unique_R_windows_no_duplicate_fill')
    def test_duplicate_query_label_conflict_refused(self):
        a=row();c=deepcopy(a);c['pair_labels']=[0,1,None]
        with self.assertRaises(ValueError):b.select_bank([a,c],'game4')
    def test_materialize_preserves_raw_order_none_and_v8_fields(self):
        value=b.descriptor(row(),'game4');uids=value['history_UIDs']+value['candidate_UIDs'];indices=value['history_frame_indices']+[value['candidate_frame_index']]*3
        records={uid:dict(uid=uid,timestamp_sec=i/25.,bbox_xywh_px=[1,2,3,4]) for uid,i in zip(uids,indices)}
        original=deepcopy(records);window=b.materialize_window(value,records)
        self.assertEqual(records,original);self.assertEqual(window['history_frame_indices'],[0,1,2]);self.assertEqual(window['candidate_frame_index'],3)
        self.assertEqual([v['label'] for v in window['candidates']],[1,0,None]);self.assertEqual([v['prediction']['uid'] for v in window['candidates']],value['candidate_UIDs'])
        self.assertIsNone(window['gap_requested_sec']);self.assertEqual(window['gap_actual_sec'],.04)
        self.assertFalse(window['supervision']['teacher_forced_history'])
        records[value['candidate_UIDs'][0]]['uid']='SNMOT-151:000004:000001'
        with self.assertRaises(ValueError):b.materialize_window(value,records)
    def test_ID0_legal_and_gate_subset_not_claimed(self):
        result=b.select_bank([row()],'game4');value=result['selected'][0]
        self.assertEqual(value['query_GT_id'],'0');self.assertEqual(value['candidate_scope'],'whole_original_high_score_stage_not_exact_enabled_subset')

if __name__=='__main__':unittest.main()
