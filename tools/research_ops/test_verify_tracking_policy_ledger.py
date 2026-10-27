"""零更新账本终验针对合同：完整分母、FP32边界、原MOT与未知状态。"""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import verify_tracking_policy_ledger as verify
import tracking_policy_ledger_core as core
from test_tracking_policy_ledger_core import fixture


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.patched = patch.object(verify, 'R', self.root); self.patched.start()
    def tearDown(self): self.patched.stop(); self.temp.cleanup()

    def test_FP32_seven_buckets_and_strict_OC_vs_inclusive_Byte_boundary(self):
        values = [.05, .1, .2, .25, .4, .6, .9]
        self.assertEqual([verify.score_policy(v)['bucket'] for v in values], list(verify.BUCKETS))
        self.assertFalse(verify.score_policy(.6)['oc_default_high'])
        self.assertFalse(verify.score_policy(.25)['oc_alternative_025_high'])
        self.assertTrue(verify.score_policy(.25)['byte_high'])
        self.assertFalse(verify.score_policy(.1)['byte_low'])
        # Python double的raw>.6并非FP32数组实际资格，不能代替阈值cast。
        threshold = verify.f32(.6); self.assertGreater(threshold, .6)
        self.assertFalse(verify.score_policy(threshold)['oc_default_high'])
        bits = struct.unpack('<I', struct.pack('<f', .6))[0]
        above = struct.unpack('<f', struct.pack('<I', bits+1))[0]
        self.assertTrue(verify.score_policy(above)['oc_default_high'])
        for value in (True, float('nan'), float('inf'), -.1, 1.1):
            with self.assertRaises(ValueError): verify.score_policy(value)

    def test_mutual_unique_keeps_both_ambiguities_and_no_candidate(self):
        def rel(ids, state, unique=None): return dict(candidate_ids=ids, candidate_IoU=[1.]*len(ids), state=state, mutual_unique_id=unique)
        rows = [rel(['0'], 'ambiguous_shared_right'), rel(['0'], 'ambiguous_shared_right'),
            rel(['1', '2'], 'ambiguous_multiple_right'), rel([], 'no_IoU05_candidate')]
        verify.relation_graph(rows, ['0', '1', '2'])
        bad = deepcopy(rows); bad[0].update(state='mutual_unique', mutual_unique_id='0')
        with self.assertRaises(ValueError): verify.relation_graph(bad, ['0', '1', '2'])
        bad = deepcopy(rows); bad[-1]['candidate_IoU'] = [.49]
        with self.assertRaises(ValueError): verify.relation_graph(bad, ['0', '1', '2'])

    def create_actual_core_fixture(self):
        cfg, sequence, GT = fixture(self.root)
        for unit in cfg['units']: unit['GT_rows_from_completed_metric'] = 4
        with patch.object(core, 'load_gt', return_value=GT):
            result = core.analyze_sequence(cfg, sequence, Path(cfg['output_root'])/sequence)
        return cfg, sequence, result, Path(cfg['output_root'])/sequence/'summary.json'

    def test_actual_core_artifacts_cross_check_full_source_GT_unit_frames_and_unknown(self):
        cfg, seq, result, path = self.create_actual_core_fixture()
        checked = verify.verify_sequence(cfg, seq, path)
        self.assertEqual(checked['source_counts'], dict(source_frames=3, raw_detections=4, GT_rows=4))
        self.assertEqual((checked['units'], checked['unit_frames']), (5, 15))
        self.assertEqual(result['artifacts']['output_ledger']['rows'], 9)
        # 独立终验读取新账本和旧MOT，不再打开原raw缓存或原GT。
        with verify.no_original_GT_cache_or_media(cfg) as guard:
            verify.verify_sequence(cfg, seq, path)
            self.assertEqual(guard['blocked_open_attempts'], 0)
        result['source_denominator_copies'] = 3; path.write_text(verify.canonical(result), encoding='utf-8')
        with self.assertRaises(ValueError): verify.verify_sequence(cfg, seq, path)

    def replace_gz(self, artifact, rows):
        with gzip.open(artifact['path'], 'wt', encoding='utf-8') as stream:
            for row in rows: stream.write(verify.canonical(row)+'\n')
        artifact['sha256'] = verify.sha(artifact['path'])

    def test_artifact_relabel_or_dropped_GT_and_fabricated_lifecycle_rejected(self):
        cfg, seq, result, path = self.create_actual_core_fixture()
        artifact = result['artifacts']['GT_opportunity_ledger']
        with gzip.open(artifact['path'], 'rt', encoding='utf-8') as stream: original = [json.loads(x) for x in stream]
        self.replace_gz(artifact, original[:-1]); path.write_text(verify.canonical(result), encoding='utf-8')
        with self.assertRaises(ValueError): verify.verify_sequence(cfg, seq, path)
        self.replace_gz(artifact, original); path.write_text(verify.canonical(result), encoding='utf-8')
        emitted = result['artifacts']['output_ledger']
        with gzip.open(emitted['path'], 'rt', encoding='utf-8') as stream: rows = [json.loads(x) for x in stream]
        rows[0]['internal_birth'] = 'confirmed_birth_frame_1'
        self.replace_gz(emitted, rows); path.write_text(verify.canonical(result), encoding='utf-8')
        with self.assertRaises(ValueError): verify.verify_sequence(cfg, seq, path)

    def test_trajectory_reconstructs_emission_only_no_internal_lost_or_recovery(self):
        unit = dict(unit_id='u', method='PT_bbox', sequence='S', fold=None, seed=None)
        rows = verify.trajectory_rows(unit, {1: [dict(identity=7)], 4: [dict(identity=7)]})
        self.assertEqual(rows[0]['unemitted_frames_within_span'], 2)
        self.assertEqual(rows[0]['same_ID_reemission_after_gap_count'], 1)
        self.assertEqual(rows[0]['internal_lost'], 'unknown_from_MOT')
        self.assertEqual(rows[0]['physical_occlusion_or_recovery'], 'unknown_from_MOT')

    def test_exact_producer_scope_and_two_worker_exit_not_reused_PID(self):
        now = datetime.now(timezone.utc).isoformat(); state = dict(parent_pid=55, created_utc=now)
        unrelated = dict(ProcessId=55, Name='python.exe', CommandLine='python unrelated.py', CreationUtc=now)
        self.assertEqual(verify.blocked_processes([unrelated], state), [])
        self.assertFalse(verify.is_producer('python verify_tracking_policy_ledger.py'))
        self.assertTrue(verify.is_producer('python D:/code/tracking_policy_ledger_control.py --execute'))
        spawned = dict(unrelated, CommandLine='python -c "spawn_main(parent_pid=55,pipe_handle=7)"')
        self.assertEqual(len(verify.blocked_processes([spawned], state)), 1)
        (self.root/'logs').mkdir()
        for i in range(2): (self.root/'logs'/f'analysis_{i}.log').write_text('', encoding='utf-8')
        state.update(workers=[dict(status='ready', worker_pid=i) for i in (10, 11)],
            completed=[dict(worker_pid=10 if n < 6 else 11) for n in range(12)],
            worker_exits=[dict(status='closed', worker_pid=i, jobs=6, GT_loaded_only_posthoc=True,
                model_tracker_TrackEval_modules_loaded=[], joined=True, process_exited=True, exit_code=0) for i in (10, 11)])
        self.assertTrue(verify.worker_closure(state, self.root)['all_joined_exit0'])
        state['worker_exits'][0]['model_tracker_TrackEval_modules_loaded'] = ['torch']
        with self.assertRaises(ValueError): verify.worker_closure(state, self.root)

    def test_GT_raw_media_open_guard_and_complete_empty_CSV_frame(self):
        forbidden = self.root/'raw.jsonl'; forbidden.write_text('not read', encoding='utf-8')
        cfg = dict(sources={'S': dict(cache=dict(path=str(forbidden)))})
        with verify.no_original_GT_cache_or_media(cfg) as proof:
            with self.assertRaises(PermissionError): forbidden.read_text(encoding='utf-8')
        self.assertEqual(proof['blocked_open_attempts'], 1)
        verify.check_csv_row(dict(frame='3', raw='0', unknown='unknown_from_MOT'), dict(frame=3, raw=0, unknown='unknown_from_MOT'))
        with self.assertRaises(ValueError): verify.check_csv_row(dict(frame='3', raw='0', unknown='confirmed'), dict(frame=3, raw=0, unknown='unknown_from_MOT'))

    def test_12_114_76315_matrix_is_not_raw_or_GT_replication(self):
        panels = dict(original_heldout=list(verify.OLD), old_external=['E1', 'E2'], seven_observed=['V'+str(i) for i in range(7)])
        order = [s for p in verify.PANELS for s in panels[p]]
        lengths = [750, 750, 750, 450, 675, 725, 775, 701, 550, 700, 888, 451]
        raw = [15170, 13340, 11155, 8461, 10629, 13054, 14825, 11597, 17263, 10952, 13767, 9032]
        GT = [11367, 11461, 8831, 6622, 8137, 9989, 11518, 9780, 8829, 7537, 11900, 7049]
        sources = {s: dict(frames=n, counts=dict(raw_detections=r), cache=dict(path=s+'cache', sha256='c')) for s, n, r in zip(order, lengths, raw)}
        units = []
        for seq, n, gt in zip(order, lengths, GT):
            cells = [(m, None, None) for m in verify.METHODS[:2]]+[
                ('strong_motion_RS', f, seed) for f in ((verify.OLD[seq],) if seq in verify.OLD else verify.FOLDS) for seed in verify.SEEDS]
            for method, fold, seed in cells:
                name = f'{method}-{seq}-{fold}-{seed}'
                units.append(dict(unit_id=name, method=method, sequence=seq, fold=fold, seed=seed, frames=n,
                    mot=dict(path=name, sha256='m'), source_cache=sources[seq]['cache'], frame_counts=[0]*n, tracked_rows=0,
                    GT_rows_from_completed_metric=gt))
        cfg = dict(sources=sources, units=units, panels=panels, GT_loaders={})
        inventory = dict(cfg, schema='tracking_policy_inventory_v1', status='complete_readonly_inventory114_no_cache_or_GT_loaded')
        verify.validate_inventory(cfg, inventory)
        self.assertEqual((sum(u['frames'] for u in units), sum(s['frames'] for s in sources.values())), (76315, 8165))
        self.assertEqual(sum(raw), 149245); self.assertEqual(sum(GT), 113020)
        bad = deepcopy(cfg); bad['units'][-1] = deepcopy(bad['units'][0]); bad_inventory = dict(inventory, units=bad['units'])
        with self.assertRaises(ValueError): verify.validate_inventory(bad, bad_inventory)
        bad = deepcopy(cfg); bad['units'][0]['GT_rows_from_completed_metric'] += 1
        with self.assertRaises(ValueError): verify.validate_inventory(bad, dict(inventory, units=bad['units']))


if __name__ == '__main__': unittest.main()
