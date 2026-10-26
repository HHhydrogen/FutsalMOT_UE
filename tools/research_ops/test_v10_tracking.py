"""v10新scope/合法ID0/固定原GT口径及完整矩阵的针对CPU检查。"""
import ast
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import v10_tracking_runtime as rt
from v10_metric import prediction_rows,validate_count,trackeval_numeric


def source(sequence='v_2QhNRucNC7E_c017'):
    return dict(sequence=sequence,game='SportsMOT_v_2QhNRucNC7E',frames=450,width=1280,height=720,fps=25)


class TrackingTests(unittest.TestCase):
    def test_scope_preserves_real_ids_and_rejects_wrong_time_size_or_unregistered(self):
        s=source();frame=dict(sequence=s['sequence'],game=s['game'],fps=25,frame_index=449,frame_number=450,
                            timestamp_sec=449/25,width=1280,height=720)
        self.assertTrue(rt.validate_frame(frame,{s['sequence']:s}));original=deepcopy(frame)
        self.assertEqual(frame,original)
        for k,v in [('sequence','SNMOT-116'),('frame_number',449),('game','game4'),('frame_index',450),('width',3840)]:
            with self.assertRaises(ValueError):rt.validate_frame(dict(frame,**{k:v}),{s['sequence']:s})

    def test_prediction_no_filter_duplicate_or_invalid_rows_rejected(self):
        text='1,1,1,2,3,4,0.3,-1,-1,-1\n1,2,900,500,3,4,0.2,-1,-1,-1\n'
        rows,count=prediction_rows(text,2);self.assertEqual(count,2);self.assertEqual(len(rows[1]),2)
        with self.assertRaises(ValueError):prediction_rows(text+text,2)
        with self.assertRaises(ValueError):prediction_rows('3,1,0,0,1,1,1,-1,-1,-1',2)

    def test_variable_frame_count_combined_has_no_frames(self):
        validate_count('new',dict(Dets=2,GT_Dets=3,Frames=450),2,3,'new',450)
        validate_count('COMBINED_SEQ',dict(Dets=2,GT_Dets=3),2,3,'new',450)
        with self.assertRaises(ValueError):validate_count('new',dict(Dets=1,GT_Dets=3,Frames=450),2,3,'new',450)

    def test_exact253_comparisons_no_seed_or_match_selection(self):
        import v10_runtime
        train=dict(training_matrix=v10_runtime.expected_matrix(),reference_R={m:{f:{str(s):{'checkpoint':{'path':f'/r/{m}/{f}/{s}/last.pt'}}
            for s in v10_runtime.SEEDS} for f in v10_runtime.FOLDS} for m in v10_runtime.METHODS})
        jobs=rt.tracking_matrix(train,'/control')
        self.assertEqual(len(jobs),253);self.assertEqual(sum(j['kind']=='new_RS' for j in jobs),162)
        self.assertEqual(sum(j['kind']=='pure_R' for j in jobs),81);self.assertEqual(sum(j['kind']=='PT' for j in jobs),10)

    def test_actual_trackeval_identity_zero_and_unmatched_prediction_preserved(self):
        # 人工两帧夹具只验证评价适配；不读取真实比赛结果或模拟模型效果。
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tracking=root/'tracking';(tracking/'data').mkdir(parents=True);output=root/'metric';output.mkdir()
            s=dict(sequence='id_zero_fixture',frames=2,width=100,height=100)
            (tracking/'data/id_zero_fixture.txt').write_text('1,1,0,0,10,10,1,-1,-1,-1\n2,1,0,0,10,10,1,-1,-1,-1\n2,2,80,80,5,5,1,-1,-1,-1\n')
            raw,_=trackeval_numeric(s,['1,0,0,0,10,10,1,1,1','2,0,0,0,10,10,1,1,1'],tracking,output)
            count=raw[s['sequence']]['pedestrian']['Count'];self.assertEqual(count['Dets'],3);self.assertEqual(count['GT_Dets'],2)
            self.assertEqual(count['GT_IDs'],1);self.assertEqual(count['Frames'],2)

    def test_primary_requires_both_new_matches_and_seed_consistency(self):
        from v10_analyze import paired_report,primary_gate
        pairs=[dict(seed=s,sequence=q,delta_pp={k:(.7 if q==list(rt.EXTERNAL)[0] else .6) for k in ('AssA','HOTA','IDF1','DetA','MOTA')})
            for s in (20261024,20261025,20261026) for q in rt.EXTERNAL]
        self.assertTrue(primary_gate(paired_report(pairs))['passed'])
        for row in pairs:
            if row['sequence']==list(rt.EXTERNAL)[1]:row['delta_pp']['AssA']=-.01
            else:row['delta_pp']['AssA']=2.
        self.assertFalse(primary_gate(paired_report(pairs))['passed'])


if __name__=='__main__':unittest.main()
