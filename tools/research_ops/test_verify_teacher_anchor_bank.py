"""teacher-anchor独立核查的五组原池/选中行/绝对表/等权率/禁止读取夹具。"""
from copy import deepcopy
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import verify_teacher_anchor_bank as v


def fixture(root):
    inputs=dict(folds={});teachers={}
    for fold in v.FOLDS:
        pool=root/'pools'/fold/'real_pool.jsonl';pool.parent.mkdir(parents=True);windows=[];totals=Counter();source_counts={}
        for seq,heldout in v.SOURCES.items():
            if heldout==fold:continue
            jid=fold+'_'+seq;job=dict(job_id=jid,regime='R',fold=fold,sequence=seq,seed=20261024,model_id='model_'+jid)
            ledger=root/'opportunity'/jid/'rows.jsonl.gz';ledger.parent.mkdir(parents=True);source_counts[seq]=dict(selected_unique=500)
            with gzip.open(ledger,'wt',encoding='utf-8') as sink:
                for i in range(500):
                    uid=jid+'_'+str(i);labels=[0,None] if i%5==0 else [1,0,None];candidates=[uid+'_c'+str(j) for j in range(len(labels))]
                    hist=[uid+'_h'+str(j) for j in range(3)];query=2 if i%4==0 else 1
                    m=dict(schema='free_state_aligned_R_bank_candidate_v1',fold=fold,teacher_regime='R',teacher_seed=20261024,source_stage='high_score',
                        GT_coordinates_in_features=False,candidate_scope='whole_original_high_score_stage_not_exact_enabled_subset',source_job_id=jid,
                        sequence=seq,teacher_model_id=job['model_id'],window_uid=uid,candidate_frame_number=i+2,source_row_index=0,source_track_id=i+1,
                        history_UIDs=hist,candidate_UIDs=candidates,pair_labels=labels,query_GT_id=query,no_positive_window=1 not in labels)
                    windows.append(dict(window_uid=uid,sequence=seq,candidate_frame_number=i+2,history=[dict(uid=h) for h in hist],
                        candidates=[dict(prediction=dict(uid=c),label=x) for c,x in zip(candidates,labels)],aligned_bank_metadata=m))
                    totals.update(dict(windows=1,all_pairs=len(labels),known_pairs=sum(x is not None for x in labels),unknown_pairs=labels.count(None),
                        positive_pairs=labels.count(1),negative_pairs=labels.count(0),no_positive_windows=int(1 not in labels)))
                    row=dict(job=job,frame_number=i+2,stage='high_score',row_index=0,track_id=i+1,history_UIDs=hist,query_GT_id=query,
                        pose_candidates=[dict(uid=c,label=x) for c,x in zip(candidates,labels)],new_solver_calls=0,Pose_support_is_accuracy=False,local_cost_comparison_is_causal=False,
                        earliest_stage_trusted3_anchor=dict(gt_id='1',frame_number=1,stage='high_score',history_UIDs=hist),
                        flags=dict(earliest_stage_trusted3_anchor_drift=query!=1,**{k:bool(i%7==0) for k in v.FLAGS}),
                        absolute_counts=dict(candidates=len(labels),positive=labels.count(1),known_negative=labels.count(0),unknown=labels.count(None)),first_stop='fixture_stop')
                    sink.write(v.canonical(row)+'\n')
            teachers[jid]=dict(job=job,ledger=dict(v.ref(ledger),rows=500),row_count=500)
        with pool.open('w',encoding='utf-8') as stream:
            for window in windows:stream.write(v.canonical(window)+'\n')
        inputs['folds'][fold]=dict(pool=v.ref(pool),selected_order_sha256=hashlib.sha256(v.canonical([w['window_uid'] for w in windows]).encode()).hexdigest(),
            selected_counts=dict(totals),source_counts=source_counts)
    return inputs,teachers


class TeacherAnchorIndependentVerifier(unittest.TestCase):
    def test_full_three_pools_3000_unique_6teachers_500_each_and_join(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(v,'R',root),patch.object(v,'OPPORTUNITY',root/'opportunity'):
                inputs,teachers=fixture(root);metadata,pools=v.pool_metadata(inputs,teachers);rows,scanned=v.ledger_join(metadata,teachers)
                self.assertEqual(len(rows),3000);self.assertEqual({x['matched_windows'] for x in scanned.values()},{500})
                self.assertEqual({len([r for r in rows if r['fold']==f]) for f in v.FOLDS},{1000})
                # 不硬编码生产漂移结果，由每个已选窗口的query/anchor实际推导。
                self.assertEqual(sum(r['anchor_drift'] for r in rows),sum(m['query_GT_id']!=1 for m in metadata))
                bad=deepcopy(metadata[0]);bad['candidate_UIDs'][0]='changed'
                row=dict(job=teachers[bad['source_job_id']]['job'],frame_number=bad['candidate_frame_number'],stage='high_score',row_index=0,track_id=bad['source_track_id'],
                    history_UIDs=bad['history_UIDs'],query_GT_id=bad['query_GT_id'],pose_candidates=[])
                with self.assertRaises(ValueError):v.joined_window(bad,row)

    def test_future_anchor_wrong_drift_and_labels_rejected(self):
        m=dict(window_uid='w',fold='game6',sequence='SNMOT-060',source_job_id='j',candidate_frame_number=10,source_stage='high_score',source_row_index=0,
            source_track_id=1,teacher_model_id='m',history_UIDs=['a','b','c'],candidate_UIDs=['d'],pair_labels=[1],query_GT_id=2)
        row=dict(job=dict(job_id='j',regime='R',seed=20261024,fold='game6',sequence='SNMOT-060',model_id='m'),frame_number=10,stage='high_score',row_index=0,track_id=1,
            history_UIDs=['a','b','c'],query_GT_id=2,pose_candidates=[dict(uid='d',label=1)],new_solver_calls=0,Pose_support_is_accuracy=False,local_cost_comparison_is_causal=False,
            earliest_stage_trusted3_anchor=dict(gt_id='1',frame_number=9),flags=dict(earliest_stage_trusted3_anchor_drift=True,**{k:False for k in v.FLAGS}),
            absolute_counts=dict(candidates=1,positive=1,known_negative=0,unknown=0),first_stop='actual_correct')
        self.assertTrue(v.joined_window(m,row)['anchor_drift'])
        for change in (lambda r:r['earliest_stage_trusted3_anchor'].update(frame_number=11),lambda r:r['flags'].update(earliest_stage_trusted3_anchor_drift=False),
            lambda r:r['pose_candidates'][0].update(label=0),lambda r:r.update(history_UIDs=['x','b','c'])):
            bad=deepcopy(row);change(bad)
            with self.assertRaises(ValueError):v.joined_window(m,bad)

    def test_all3000_JSONL_CSV_exact_fields_and_changed_label_rejected(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(v,'R',root),patch.object(v,'OPPORTUNITY',root/'opportunity'),patch.object(v,'EXP',root/'audit'):
                inputs,teachers=fixture(root);metadata,_=v.pool_metadata(inputs,teachers);rows,_=v.ledger_join(metadata,teachers)
                out=root/'audit/analysis';out.mkdir(parents=True);jsonl=out/'windows.jsonl';csvfile=out/'windows.csv'
                def write(values):
                    with jsonl.open('w',encoding='utf-8') as stream:
                        for r in values:stream.write(v.canonical(r)+'\n')
                    with csvfile.open('w',encoding='utf-8-sig',newline='') as stream:
                        w=csv.DictWriter(stream,fieldnames=v.FIELDS);w.writeheader()
                        for r in values:w.writerow({k:v.canonical(r[k]) if isinstance(r[k],(dict,list)) else ('null' if r[k] is None else r[k]) for k in v.FIELDS})
                    return dict(windows_jsonl=v.ref(jsonl),windows_csv=v.ref(csvfile))
                report=write(rows);self.assertTrue(v.window_outputs(report,rows)['every_row_and_field_exact'])
                bad=deepcopy(rows);bad[0]['pair_labels'][0]=1;report=write(bad)
                with self.assertRaises(ValueError):v.window_outputs(report,rows)

    def test_two_folds_then_three_sources_equal_rate_unknown_no_CI(self):
        rows=[]
        for seq,heldout in v.SOURCES.items():
            for fold in v.FOLDS:
                if fold==heldout:continue
                for i in range(1 if fold=='game4' else 3):
                    rows.append(dict(fold=fold,sequence=seq,all_pairs=1,known_pairs=1,positive_pairs=0,known_negative_pairs=1,unknown_pairs=0,
                        no_positive=True,anchor_drift=fold=='game4',first_stop='fixture',**{k:False for k in v.FLAGS}))
        out=v.summaries(rows);rate=out['source_equal_descriptions']['anchor_drift']
        self.assertEqual(rate['source_rates_pp']['SNMOT-097'],50.);self.assertTrue(rate['interval_not_estimated'])
        for r in rows:
            if r['fold']=='game4' and r['sequence']=='SNMOT-097':r['anchor_drift']=None
        out=v.summaries(rows)['source_equal_descriptions']['anchor_drift']
        self.assertIsNone(out['source_rates_pp']['SNMOT-097']);self.assertIsNone(out['three_source_equal_mean_rate_pp'])

    def test_pool_SHA_unchanged_and_guard_blocks_old_frames_GT_weights(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);pool=root/'pool/real_pool.jsonl';pool.parent.mkdir();pool.write_text('{}',encoding='utf-8')
            with patch.object(v,'R',root):
                reference=v.ref(pool);v.checked(reference,'pool')
                pool.write_text('{"changed":true}',encoding='utf-8')
                with self.assertRaises(ValueError):v.checked(reference,'pool')
                forbidden=[root/'frames.jsonl.gz',root/'gt.txt',root/'checkpoint.pt']
                for p in forbidden:p.write_bytes(b'x')
                with v.raw_guard([pool]) as guard:
                    self.assertTrue(pool.read_text())
                    for p in forbidden:
                        with self.assertRaises(PermissionError):p.read_bytes()
                self.assertEqual(guard['blocked_open_attempts'],3)


if __name__=='__main__':unittest.main()
