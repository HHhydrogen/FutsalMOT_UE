"""政策差异账本的针对CPU合同；只用小夹具，不运行模型、tracker或TrackEval。"""
from copy import deepcopy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tracking_policy_ledger_core as core


def reference(path):
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def write_json(path, value):
    path.write_text(core.canonical(value), encoding='utf-8')
    return reference(path)


def adjacent_float32(value, offset):
    bits = struct.unpack('<I', struct.pack('<f', value))[0]
    return struct.unpack('<f', struct.pack('<I', bits+offset))[0]


def fixture(root):
    sequence = 'SNMOT-060'
    rows = [
        [dict(uid='A', bbox_xywh_px=[0, 0, 10, 10], score=core.f32(.6)),
         dict(uid='B', bbox_xywh_px=[0, 0, 10, 10], score=.7)],
        [dict(uid='C', bbox_xywh_px=[30, 0, 10, 10], score=.25),
         dict(uid='D', bbox_xywh_px=[0, 0, 10, 10], score=.3)], []]
    cache = root/'cache.jsonl'
    cache.write_text(''.join(core.canonical(dict(sequence=sequence, frame_index=index,
        frame_number=index+1, fps=25, timestamp_sec=index/25, width=100, height=100,
        detections=values))+'\n' for index, values in enumerate(rows)), encoding='utf-8')
    source = dict(sequence=sequence, frames=3, fps=25, width=100, height=100,
        cache=reference(cache), counts=dict(raw_detections=4))
    gt = {1: [dict(gt_id='0', bbox_xywh_px=[0, 0, 10, 10])],
          2: [dict(gt_id='0', bbox_xywh_px=[0, 0, 10, 10]), dict(gt_id='1', bbox_xywh_px=[30, 0, 10, 10])],
          3: [dict(gt_id='0', bbox_xywh_px=[0, 0, 10, 10])]}
    units = []
    identities = [('official_ocsort', None, None), ('PT_bbox', None, None)] + [
        ('strong_motion_RS', 'game4', seed) for seed in (20261024, 20261025, 20261026)]
    for index, (method, fold, seed) in enumerate(identities):
        folder = root/str(index)
        folder.mkdir()
        mot = folder/'mot.txt'
        text = '1,1,0,0,10,10,1,-1,-1,-1\n'
        if method != 'official_ocsort':
            text += '3,1,80,80,10,10,.4,-1,-1,-1\n'
        mot.write_text(text, encoding='utf-8')
        counts = [1, 0, int(method != 'official_ocsort')]
        receipt = dict(status='complete', frames=3, tracked_rows=sum(counts), frame_counts=counts,
            mot_sha256=reference(mot)['sha256'], **{'source_cache' if method == 'official_ocsort' else 'cache': source['cache']})
        tracking = write_json(folder/'receipt.json', receipt)
        metric = dict(status='complete', frames=3, GT_rows=4)
        if method == 'official_ocsort':
            metric['source_cache'] = source['cache']
            metric['tracking_receipt'] = tracking
        else:
            metric['tracking_receipt_sha256'] = tracking['sha256']
        units.append(dict(unit_id=str(index), method=method, sequence=sequence, fold=fold, seed=seed,
            frames=3, tracked_rows=sum(counts), frame_counts=counts, mot=reference(mot),
            source_cache=source['cache'], tracking_receipt=tracking,
            metric_report=write_json(folder/'report.json', metric)))
    cfg = dict(test_sealed=True, new_optimizer_updates=0, sources={sequence: source}, units=units,
        panels=dict(original_heldout=[sequence], old_external=[], seven_observed=[]),
        output_root=str(root/'output'), GT_loaders=dict(old_five=dict(module=dict(path='fixture', sha256='fixture'))))
    return cfg, sequence, gt


class LedgerContracts(unittest.TestCase):
    def test_actual_OC_explicit_ref_and_PT_strong_SHA_contracts_are_distinct(self):
        with tempfile.TemporaryDirectory(prefix='policy_schema_') as temporary:
            cfg, _, _ = fixture(Path(temporary))
            for unit in cfg['units']:
                metric = json.loads(Path(unit['metric_report']['path']).read_text(encoding='utf-8'))
                if unit['method'] == 'official_ocsort':
                    self.assertNotIn('tracking_receipt_sha256', metric)
                    self.assertIn('tracking_receipt', metric)
                else:
                    self.assertNotIn('tracking_receipt', metric)
                    self.assertIn('tracking_receipt_sha256', metric)
                core._unit_input(unit, 3)
            oc = cfg['units'][0]
            metric_path = Path(oc['metric_report']['path'])
            metric = json.loads(metric_path.read_text(encoding='utf-8'))
            metric['tracking_receipt']['sha256'] = '0'*64
            oc['metric_report'] = write_json(metric_path, metric)
            with self.assertRaises(ValueError):
                core._unit_input(oc, 3)

    def test_float32_boundaries_all_seven_buckets_and_strict_policy_difference(self):
        values = [adjacent_float32(.1, -1), core.f32(.1), adjacent_float32(.1, 1), .25,
                  adjacent_float32(.25, 1), core.f32(.6), adjacent_float32(.6, 1)]
        self.assertEqual([core.score_policy(value)['bucket'] for value in values], list(core.BUCKETS))
        quarter = core.score_policy(.25)
        self.assertTrue(quarter['byte_high'])
        self.assertFalse(quarter['oc_alternative_025_high'])
        self.assertFalse(quarter['byte_low'])
        self.assertFalse(core.score_policy(core.f32(.6))['oc_default_high'])
        self.assertTrue(core.score_policy(adjacent_float32(.6, 1))['oc_default_high'])
        for bad in (float('nan'), float('inf'), -1, 1.01, True):
            with self.assertRaises(ValueError):
                core.score_policy(bad)

    def test_geometric_states_keep_ambiguity_and_ID_zero(self):
        box = [0, 0, 10, 10]
        self.assertEqual(core.mutual_unique([box], [box], ['0'])[0]['mutual_unique_id'], '0')
        shared = core.mutual_unique([box, box], [box], ['0'])
        self.assertEqual([r['state'] for r in shared], ['ambiguous_shared_right']*2)
        multiple = core.mutual_unique([box], [box, box], ['0', '1'])[0]
        self.assertEqual(multiple['state'], 'ambiguous_multiple_right')
        self.assertEqual(multiple['candidate_ids'], ['0', '1'])
        self.assertIsNone(multiple['mutual_unique_id'])
        empty = core.mutual_unique([[20, 20, 2, 2]], [box], ['0'])[0]
        self.assertEqual(empty['state'], 'no_IoU05_candidate')
        self.assertNotIn('false_positive', core.canonical(empty))

    def test_GT_opportunity_does_not_require_unique_match_or_claim_accuracy(self):
        box = [0, 0, 10, 10]
        raw = [dict(uid=str(i), bbox_xywh_px=box, policy=core.score_policy(.3)) for i in range(2)]
        relation, opportunity = core.posthoc_frame(raw, [dict(gt_id='0', bbox_xywh_px=box)])
        self.assertTrue(all(r['state'] == 'ambiguous_shared_right' for r in relation))
        self.assertTrue(opportunity[0]['no_oc_gt06_but_any_oc_gt025'])
        self.assertEqual(opportunity[0]['oc_gt025_raw_UIDs'], ['0', '1'])
        self.assertNotIn('bbox_xywh_px', core.canonical(opportunity))

    def test_MOT_emission_gaps_keep_native_ID_and_unknown_internal_state(self):
        data = b'1,7,1,2,3,4,1,-1,-1,-1\n4,7,1,2,3,4,.2,-1,-1,-1\n'
        by_frame, count = core.parse_mot_bytes(data, 4)
        self.assertEqual(count, 2)
        unit = dict(unit_id='a', method='official_ocsort', sequence='SNMOT-060', fold=None, seed=None)
        episode = core.emitted_trajectories(unit, by_frame)[0]
        self.assertEqual(episode['identity'], 7)
        self.assertEqual(episode['unemitted_frames_within_span'], 2)
        self.assertEqual(episode['same_ID_reemission_after_gap_count'], 1)
        self.assertEqual(episode['internal_birth'], core.UNKNOWN)
        self.assertEqual(episode['internal_lost'], core.UNKNOWN)
        for bad in (data+data.splitlines(keepends=True)[0], b'1,0,1,2,3,4,1,-1,-1,-1\n',
                    b'5,1,1,2,3,4,1,-1,-1,-1\n', b'1,1,1,2,0,4,1,-1,-1,-1\n'):
            with self.assertRaises(ValueError):
                core.parse_mot_bytes(bad, 4)

    def test_whitelist_ignores_Pose_and_geometry_flag_but_rejects_duplicate_raw_UID(self):
        class Unreadable(dict):
            def __getitem__(self, key):
                if key not in ('uid', 'bbox_xywh_px', 'score'):
                    raise AssertionError('读取了白名单外字段')
                return super().__getitem__(key)
        frame = dict(sequence='S', frame_index=0, frame_number=1, fps=25, timestamp_sec=0,
            width=10, height=10, detections=[Unreadable(uid='u', bbox_xywh_px=[0, 0, 2, 2], score=.2,
                geometry_valid=False, xy='禁止读取', GT_id='禁止读取')])
        source = dict(fps=25, width=10, height=10)
        with patch.object(core.json, 'loads', return_value=frame):
            seen = set()
            raw = core._read_raw(b'fixture', 'S', source, 1, seen)
            self.assertEqual(len(raw), 1)
            self.assertTrue(raw[0]['policy']['byte_low'])
            with self.assertRaises(ValueError):
                core._read_raw(b'fixture', 'S', source, 1, seen)

    def test_complete_fixture_single_source_denominators_full_outputs_and_partial_refusal(self):
        with tempfile.TemporaryDirectory(prefix='policy_ledger_') as temporary:
            cfg, sequence, gt = fixture(Path(temporary))
            output = Path(cfg['output_root'])/sequence
            with patch.object(core, 'load_gt', return_value=gt):
                result = core.analyze_sequence(cfg, sequence, output)
            self.assertEqual(result['source_counts'], dict(source_frames=3, raw_detections=4, GT_rows=4))
            self.assertEqual(result['source_denominator_copies'], 1)
            self.assertEqual(result['unit_frames'], 15)
            self.assertEqual(sum(u['output_rows'] for u in result['units']), 9)
            self.assertEqual(result['GT_opportunities']['GT_no_oc_gt06_but_any_oc_gt025'], 1)
            self.assertEqual(result['artifacts']['GT_opportunity_ledger']['rows'], 4)
            self.assertEqual(result['artifacts']['output_ledger']['rows'], 9)
            self.assertFalse(result['opportunity_is_accuracy_or_tracking_gain'])
            self.assertFalse(result['no_overlap_is_absolute_false_positive'])
            self.assertFalse(result['score_policy_changed_or_executed'])
            with gzip.open(output/'output_ledger.jsonl.gz', 'rt', encoding='utf-8') as stream:
                emitted = [json.loads(line) for line in stream]
            self.assertEqual(sum(r['raw_score_geometric_proxy'] is None for r in emitted), 9)
            self.assertTrue(all(r['internal_confirmation'] == core.UNKNOWN for r in emitted))
            with (output/'frame_ledger.csv').open(encoding='utf-8', newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 3)
            with self.assertRaises(ValueError):
                core.analyze_sequence(cfg, sequence, output)
            # 独立失败目录保留，不能把损坏输入当零raw继续。
            broken = deepcopy(cfg)
            broken['sources'][sequence]['counts']['raw_detections'] = 5
            with patch.object(core, 'load_gt', return_value=gt), self.assertRaises(ValueError):
                core.analyze_sequence(broken, sequence, Path(cfg['output_root'])/'failed')
            self.assertTrue((Path(cfg['output_root'])/'failed/failure.json').is_file())
            self.assertFalse((Path(cfg['output_root'])/'failed/summary.json').exists())


if __name__ == '__main__':
    unittest.main()
