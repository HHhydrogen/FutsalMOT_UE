"""原窗口与anchor代理交叉核查的合成夹具；不接触实际实验或训练。"""
from copy import deepcopy
import csv
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import teacher_anchor_bank_audit as a


def selected(fold, sequence, index):
    jid = fold+'_'+sequence; uid = a.digest([jid, index]); labels = [0, 0, None] if index % 2 == 0 else [1, 0, None]
    metadata = dict(schema='free_state_aligned_R_bank_candidate_v1', fold=fold, teacher_regime='R', teacher_seed=20261024,
        teacher_model_id='model_'+jid, source_job_id=jid, sequence=sequence, source_stage='high_score', source_row_index=index,
        source_track_id=index+1, candidate_frame_number=4+index, window_uid=uid, history_UIDs=['h0', 'h1', 'h2'],
        query_GT_id='1', candidate_UIDs=[jid+':'+str(index)+':'+str(j) for j in range(3)], pair_labels=labels,
        no_positive_window=1 not in labels, GT_coordinates_in_features=False, candidate_scope='whole_original_high_score_stage_not_exact_enabled_subset')
    job = dict(job_id=jid, fold=fold, regime='R', sequence=sequence, seed=20261024, model_id='model_'+jid)
    anchor = None if index % 3 == 2 else dict(gt_id='0' if index % 3 == 0 else '1', frame_number=4, stage='high_score', history_UIDs=['old0', 'old1', 'old2'])
    drift = None if anchor is None else anchor['gt_id'] != '1'
    flags = {key: (False if 1 not in labels else index % 3 == 0) for key in a.FLAG_KEYS}; flags['earliest_stage_trusted3_anchor_drift'] = drift
    ledger = dict(job=job, frame_number=metadata['candidate_frame_number'], stage='high_score', row_index=index, track_id=index+1,
        history_UIDs=metadata['history_UIDs'], query_GT_id='1', earliest_stage_trusted3_anchor=anchor, flags=flags,
        pose_candidates=[dict(uid=u, label=v) for u, v in zip(metadata['candidate_UIDs'], labels)],
        absolute_counts=dict(candidates=3, positive=labels.count(1), known_negative=labels.count(0), unknown=1),
        first_stop='trusted_correct_raw_absent' if 1 not in labels else 'actual_correct', new_solver_calls=0,
        Pose_support_is_accuracy=False, local_cost_comparison_is_causal=False)
    window = dict(window_uid=uid, sequence=sequence, candidate_frame_number=metadata['candidate_frame_number'],
        history=[dict(uid=u) for u in metadata['history_UIDs']], candidates=[dict(prediction=dict(uid=u), label=v) for u, v in zip(metadata['candidate_UIDs'], labels)], aligned_bank_metadata=metadata)
    return window, metadata, ledger, job


class JoinContracts(unittest.TestCase):
    def test_drift_true_false_null_and_no_positive_pair_accounting(self):
        for index, drift in [(0, True), (1, False), (2, None)]:
            _, metadata, ledger, _ = selected('game4', 'SNMOT-097', index)
            row = a.join_window(metadata, ledger)
            self.assertIs(row['anchor_drift'], drift)
            self.assertEqual((row['all_pairs'], row['known_pairs'], row['unknown_pairs']), (3, 2, 1))
            self.assertEqual(row['no_positive'], index % 2 == 0)
            self.assertFalse(row['drift_is_true_identity_error']); self.assertFalse(row['labels_changed'])

    def test_exact_join_candidate_label_history_query_and_coordinate_refuse_changes(self):
        _, metadata, ledger, _ = selected('game4', 'SNMOT-097', 1)
        for mutation in (lambda r: r.update(row_index=99), lambda r: r.update(history_UIDs=['other']),
                         lambda r: r.update(query_GT_id='9'), lambda r: r['pose_candidates'].reverse(),
                         lambda r: r['pose_candidates'][0].update(label=0), lambda r: r['job'].update(regime='RS')):
            bad = deepcopy(ledger); mutation(bad)
            with self.assertRaises(ValueError): a.join_window(metadata, bad)

    def test_future_anchor_or_false_drift_flag_refused(self):
        _, metadata, ledger, _ = selected('game4', 'SNMOT-097', 1)
        bad = deepcopy(ledger); bad['earliest_stage_trusted3_anchor']['frame_number'] = 100
        with self.assertRaises(ValueError): a.join_window(metadata, bad)
        bad = deepcopy(ledger); bad['flags']['earliest_stage_trusted3_anchor_drift'] = True
        with self.assertRaises(ValueError): a.join_window(metadata, bad)


class FixtureFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.exp = self.root/'pose/teacher_anchor_bank_a01'
        self.rpatch = patch.object(a, 'R', self.root); self.epatch = patch.object(a, 'EXP', self.exp)
        self.rpatch.start(); self.epatch.start()

    def tearDown(self): self.epatch.stop(); self.rpatch.stop(); self.tmp.cleanup()

    def put(self, name, body):
        path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(a.canonical(body), encoding='utf-8'); return a.ref(path)

    def build(self, pool_mutation=None, ledger_mutation=None):
        folds = {}; refs = []; teacher_ledgers = []
        for fold in a.FOLDS:
            windows = []
            for sequence, heldout in a.SOURCE_FOLDS.items():
                if heldout == fold: continue
                ledger_rows = []; job = None
                for index in range(500):
                    w, _, row, job = selected(fold, sequence, index); windows.append(w); ledger_rows.append(row)
                if ledger_mutation: ledger_mutation(ledger_rows)
                path = self.root/'ledgers'/job['job_id']/'rows.jsonl.gz'; path.parent.mkdir(parents=True)
                with gzip.open(path, 'xt', encoding='utf-8') as stream:
                    for row in ledger_rows: stream.write(a.canonical(row)+'\n')
                bound = dict(**a.ref(path), rows=500); teacher_ledgers.append(bound)
                unit = dict(schema='decision_opportunity_unit_v1', status='complete', job=job, frames=750, row_count=500, ledger=bound,
                    **{k: 0 for k in a.ZERO_KEYS}, test_read=False)
                refs.append(self.put('units/'+job['job_id']+'.json', unit))
            labels = [x for w in windows for x in w['aligned_bank_metadata']['pair_labels']]
            counts = dict(windows=1000, all_pairs=len(labels), known_pairs=sum(x is not None for x in labels), unknown_pairs=labels.count(None),
                positive_pairs=labels.count(1), negative_pairs=labels.count(0), no_positive_windows=sum(1 not in w['aligned_bank_metadata']['pair_labels'] for w in windows))
            order = a.digest([w['window_uid'] for w in windows])
            if pool_mutation: pool_mutation(windows)
            path = self.root/'inputs'/fold/'real_pool.jsonl'; path.parent.mkdir(parents=True)
            with path.open('x', encoding='utf-8') as stream:
                for w in windows: stream.write(a.canonical(w)+'\n')
            folds[fold] = dict(pool=a.ref(path), selected_counts=counts, selected_order_sha256=order,
                source_counts={s: dict(selected_unique=500) for s, heldout in a.SOURCE_FOLDS.items() if heldout != fold})
        for fold in a.FOLDS:
            for sequence, heldout in a.SOURCE_FOLDS.items():
                if fold == heldout: continue
                index = len(refs)-6; count = 29500 if index < 5 else 29618
                job = dict(job_id='RS_'+fold+'_'+sequence, fold=fold, regime='RS', sequence=sequence, seed=20261024)
                # RS引用只核小收据，刻意不存在其ledger文件；测试不会打开。
                refs.append(self.put('units/'+job['job_id']+'.json', dict(schema='decision_opportunity_unit_v1', status='complete', job=job,
                    frames=750, row_count=count, ledger=dict(path='RS-ledger-must-not-open', rows=count), **{k: 0 for k in a.ZERO_KEYS}, test_read=False)))
        inputs = self.put('inputs_complete.json', dict(schema='state_aligned_R_bank_inputs_v1', status='complete3_fold1000_unique_original_prediction_R_banks_not_training_authorized',
            all_windows_roundtrip_exact=True, optimizer_updates=0, images_GT_weights_read=False, new_prediction_or_tracking_or_training=False, test_read=False, folds=folds))
        report = self.put('opportunity/report.json', dict(schema='decision_opportunity_analysis_v1', status='complete12_existing_log_decision_opportunity_counts_and_source_intervals',
            rows=180118, absolute_frames=9000, unique_source_frames=2250, **{k: 0 for k in a.ZERO_KEYS}, test_read=False, units=refs))
        verification = self.put('opportunity/verification.json', dict(status='complete12_decision_opportunity_sources_rows_counts_intervals_and_exit_verified',
            producer_processes_absent=True, test_read=False, **{k: 0 for k in a.ZERO_KEYS}, analysis=report))
        cfg = self.put('protocol/config.json', dict(schema='teacher_anchor_bank_audit_protocol_v1', approved_by='root', source_folds=a.SOURCE_FOLDS,
            test_sealed=True, **{k: 0 for k in a.ZERO_KEYS}, input_root=inputs, opportunity_report=report, opportunity_verification=verification))
        return cfg, teacher_ledgers

    def test_complete3000_exact_join_and_all_records_no_RS_ledger_read(self):
        cfg, _ = self.build(); output = self.exp/'analysis'
        result = a.audit(cfg['path'], output)
        self.assertEqual(result['selected_windows'], 3000)
        with (output/'windows.jsonl').open(encoding='utf-8') as stream: rows = [json.loads(x) for x in stream]
        with (output/'windows.csv').open(encoding='utf-8-sig', newline='') as stream: self.assertEqual(len(list(csv.DictReader(stream))), 3000)
        report = json.loads((output/'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['RS_ledgers_opened'], 0); self.assertEqual(report['original_frames_opened'], 0)
        self.assertEqual(report['descriptions']['all']['no_positive_windows'], 1500)
        self.assertEqual(report['descriptions']['all']['anchor_drift'], dict(true=1002, false=1002, null=996))
        self.assertTrue(all(v['windows'] == 1000 for v in report['descriptions']['per_fold'].values()))
        self.assertTrue(all(v['windows'] == 1000 for v in report['descriptions']['per_source'].values()))
        self.assertEqual(report['descriptions']['source_equal_descriptions']['no_positive']['three_source_equal_mean_rate_pp'], 50)
        self.assertEqual(len({r['window_uid'] for r in rows}), 3000)
        self.assertFalse(report['window_selection_changed']); self.assertFalse(report['labels_changed'])
        with self.assertRaises(ValueError): a.audit(cfg['path'], output)

    def test_duplicate_pool_window_or_outer_label_tamper_refused(self):
        cfg, _ = self.build(pool_mutation=lambda windows: windows.__setitem__(1, deepcopy(windows[0])))
        with self.assertRaises(ValueError): a.audit(cfg['path'], self.exp/'analysis')
        self.assertFalse((self.exp/'analysis').exists())

    def test_selected_ledger_mismatch_or_missing_row_refused(self):
        cfg, _ = self.build(ledger_mutation=lambda rows: rows[0]['pose_candidates'][0].update(label=1))
        with self.assertRaises(ValueError): a.audit(cfg['path'], self.exp/'analysis')
        self.assertFalse((self.exp/'analysis').exists())

    def test_SHA_change_rejected_and_new_forward_or_test_protocol_refused(self):
        cfg, ledgers = self.build()
        with Path(ledgers[0]['path']).open('ab') as stream: stream.write(b'changed')
        with self.assertRaises(ValueError): a.audit(cfg['path'], self.exp/'analysis')
        body = json.loads(Path(cfg['path']).read_text(encoding='utf-8')); body['new_model_forwards'] = 1
        bad = self.put('protocol/forward.json', body)
        with self.assertRaises(ValueError): a.validate(bad['path'])
        with self.assertRaises(ValueError): a.safe(self.root/'test/forbidden.json')


if __name__ == '__main__': unittest.main()
