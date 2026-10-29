"""诊断控制器的串流、来源和预算合同；仅合成夹具。"""
from copy import deepcopy
import unittest
from unittest.mock import patch

import state_label_alignment_diagnosis as d


def pair():
    row=dict(job=dict(job_id='job'),frame_number=4,stage='high_score',row_index=2,track_id=0,
             history_UIDs=['h1','h2','h3'],query_GT_id='0',pose_candidates=[dict(uid='c',label=1)])
    annotation=dict(job_id='job',frame_number=4,stage='high_score',row_index=2,track_id=0,
                    history_UIDs=['h1','h2','h3'],query_GT_id='0',candidate_UIDs=['c'],pair_labels=[1])
    return row,annotation


class ControlContracts(unittest.TestCase):
    def test_exact_join_keeps_ID0(self):
        row,annotation=pair()
        self.assertEqual(list(d.joined_rows(iter([row]),iter([annotation]))),[(row,annotation)])

    def test_missing_annotation_refused(self):
        with self.assertRaises(ValueError):list(d.joined_rows(iter([pair()[0]]),iter([])))

    def test_wrong_history_refused_without_nearest_guess(self):
        row,annotation=pair();annotation['history_UIDs'][-1]='other'
        with self.assertRaises(ValueError):list(d.joined_rows(iter([row]),iter([annotation])))

    def test_labels_not_repaired(self):
        row,annotation=pair();annotation['pair_labels']=[None]
        with self.assertRaises(ValueError):list(d.joined_rows(iter([row]),iter([annotation])))

    def test_stream_does_not_prefetch_second_row(self):
        events=[];row,annotation=pair()
        def source():
            events.append(1);yield row
            events.append(2);yield row
        stream=d.joined_rows(source(),iter([annotation,annotation]));next(stream)
        self.assertEqual(events,[1])

    def test_sealed_path_refused(self):
        with self.assertRaises(ValueError):d.safe('D:/projects/FutsalMOT_Research/test/rows.jsonl.gz')
        with self.assertRaises(ValueError):d.safe('D:/projects/FutsalMOT_Research/pose/SNMOT-116/metadata.json')

    def test_external_output_cannot_escape_experiment(self):
        with self.assertRaises(ValueError):d.safe('D:/projects/FutsalMOT_Research/pose/old/receipt.json',output=True)

    def test_exposure_table_not_doubled(self):
        windows=[dict(window_uid=fold+'w'+str(i),fold=fold,counts=dict(all_pairs=2,known_pairs=1),
                      bce_weights={k:1. for k in d.WEIGHTS}) for fold in d.FOLDS.values() for i in range(1000)]
        tables=[dict(fold=fold,seed=seed,table=dict(fold=fold,seed=seed)) for fold,seed in sorted(d.EXPOSURE_CELLS)]
        def read(value):return dict(fold=value['fold'],seed=value['seed'],real=[dict(window_uid=value['fold']+'w'+str(i),candidate_pairs=2,labelled_pairs=1) for _ in range(3) for i in range(1000)])
        with patch.object(d,'read',read):result=d.exposure_summary(dict(exposure_tables=tables),windows)
        self.assertEqual(sum(x['counts']['window_exposures'] for x in result),27000)
        self.assertEqual(sum(x['counts']['known_pairs'] for x in result),27000)
        self.assertTrue(all(x['table_shared_by_R_RS'] and x['not_doubled_to_18_run_consumption'] for x in result))

    def test_exposure_pair_change_refused(self):
        w=dict(window_uid='w',fold='game4',counts=dict(all_pairs=2,known_pairs=1))
        cfg=dict(exposure_tables=[dict(fold=f,seed=s,table={}) for f,s in sorted(d.EXPOSURE_CELLS)])
        with patch.object(d,'read',return_value=dict(fold='game4',seed=20261024,real=[dict(window_uid='w',candidate_pairs=3,labelled_pairs=1)]*3000)):
            with self.assertRaises(ValueError):d.exposure_summary(cfg,[w])

    def test_duplicate_exposure_matrix_refused(self):
        cfg=dict(exposure_tables=[dict(fold='game4',seed=20261024,table={})]*9)
        with self.assertRaises(ValueError):d.exposure_summary(cfg,[])

    def test_forbidden_file_rejected_before_hash_or_open(self):
        value=dict(path='D:/projects/FutsalMOT_Research/pose/old/frames.jsonl.gz',sha256='x')
        with patch.object(d,'checked',side_effect=AssertionError('不得先hash')):
            with self.assertRaises(ValueError):list(d.json_rows(value))
            with self.assertRaises(ValueError):d.read(dict(path='D:/projects/FutsalMOT_Research/model.pt',sha256='x'))


if __name__=='__main__':unittest.main()
