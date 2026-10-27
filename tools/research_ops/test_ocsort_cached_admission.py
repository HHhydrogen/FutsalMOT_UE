"""独立准入候选CPU合同；不冒充真实96帧/常驻进程准入。"""
from copy import deepcopy
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import ocsort_cached_admission as admission


class AdmissionContract(unittest.TestCase):
    def test_fixed_prefixes_and_no_test_or_performance_claim(self):
        self.assertEqual(admission.PREFIXES, (('A', 'SNMOT-060', 48), ('B', 'v_2QhNRucNC7E_c017', 48)))
        self.assertEqual(admission.PARAMETERS['unique_source_frames'], 96)
        self.assertFalse(admission.PARAMETERS['performance_speedup_claim'])
        self.assertEqual(len(set(admission.SEQUENCES)), 12)
        for path in ('D:/projects/FutsalMOT_Research/test/cache.jsonl',
                     'D:/projects/FutsalMOT_Research/pose/SNMOT-116/cache.jsonl'):
            with self.assertRaises(ValueError):
                admission.physical(path)

    def test_whitelist_rejects_GT_Pose_pollution_without_access(self):
        class Forbidden:
            def __deepcopy__(self, memo):
                raise AssertionError('GT或Pose不得进入适配输入')
        frame = admission.synthetic_frames()[0]
        frame['endpoint_GT'] = Forbidden()
        frame['detections'][0]['xy_px'] = Forbidden()
        frame['detections'][0]['GT_identity'] = Forbidden()
        public = admission.public_frame(frame)
        self.assertEqual(set(public), {*admission.FRAME_KEYS, 'detections'})
        self.assertTrue(all(set(det) == {'bbox_xywh_px', 'score'} for det in public['detections']))
        public['detections'][0]['bbox_xywh_px'][0] += 1
        self.assertNotEqual(public['detections'][0]['bbox_xywh_px'], frame['detections'][0]['bbox_xywh_px'])

    def test_original_ID_rawoutputs_and_empty_frame_counts_all_exact(self):
        value = dict(mot_text='1,1,0,0,10,20,1,-1,-1,-1\n', frames=2, tracked_rows=1,
                     frame_counts=[1, 0], raw_outputs=[[[0., 0., 10., 20., 1.]], []])
        self.assertTrue(admission.compare_outputs(value, deepcopy(value))['per_frame_raw_outputs_exact'])
        for key, wrong in (('mot_text', value['mot_text'].replace('1,1,', '1,2,')),
                           ('frame_counts', [0, 1]), ('raw_outputs', [[], value['raw_outputs'][0]]),
                           ('frames', 1), ('tracked_rows', 0)):
            changed = deepcopy(value); changed[key] = wrong
            with self.assertRaises(ValueError, msg=key):
                admission.compare_outputs(changed, value)

    def test_GT_guard_handles_builtins_pathlib_io_os_and_restores(self):
        with TemporaryDirectory() as directory:
            protected = Path(directory)/'private_annotations.json'
            protected.write_text('must not read', encoding='utf-8')
            allowed = Path(directory)/'raw_predictions.jsonl'
            allowed.write_text('raw', encoding='utf-8')
            guard = admission.GTGuard([str(protected)])
            with guard.active():
                guard.prove_blocked()
                self.assertEqual(allowed.read_text(encoding='utf-8'), 'raw')
                for opener in (lambda: protected.read_bytes(), lambda: io.open(protected),
                               lambda: os.open(protected, os.O_RDONLY)):
                    with self.assertRaises(admission.GTReadBlocked):
                        opener()
                with self.assertRaises(ValueError):
                    guard.evidence()
            self.assertEqual(protected.read_text(encoding='utf-8'), 'must not read')

    def test_guard_proof_cannot_hide_algorithm_access(self):
        with TemporaryDirectory() as directory:
            guard = admission.GTGuard([str(Path(directory)/'gt.txt')])
            with guard.active():
                guard.prove_blocked()
                proof = guard.evidence()
                self.assertEqual(proof['self_test_blocked_opens'], 3)
                self.assertEqual(proof['algorithm_blocked_GT_opens'], 0)
                self.assertFalse(proof['algorithm_GT_read'])

    def test_artificial_fixture_covers_empty_threshold_crossing_and_missing(self):
        frames = admission.synthetic_frames()
        self.assertEqual(len(frames), 16)
        self.assertEqual(sum(not f['detections'] for f in frames), 3)
        self.assertTrue({.2, .6, .6001, .9}.issubset({d['score'] for d in frames[0]['detections']}))
        self.assertLess(frames[0]['detections'][0]['bbox_xywh_px'][0], frames[0]['detections'][1]['bbox_xywh_px'][0])
        self.assertGreater(frames[-1]['detections'][0]['bbox_xywh_px'][0], frames[-1]['detections'][1]['bbox_xywh_px'][0])

    def test_output_receipt_cannot_overwrite_partial_or_success(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'receipt.json'
            admission.write_new(path, {'status': 'partial'})
            with self.assertRaises(FileExistsError):
                admission.write_new(path, {'status': 'complete'})

    def test_receive_failure_or_missing_result_never_retries(self):
        class Connection:
            def __init__(self, value, available=True): self.value, self.available = value, available
            def poll(self, timeout): return self.available
            def recv(self): return self.value
        self.assertEqual(admission.receive(Connection({'kind': 'ready'}), 'ready')['kind'], 'ready')
        with self.assertRaises(ValueError):
            admission.receive(Connection({'kind': 'failed', 'traceback': 'real failure'}), 'result')
        with self.assertRaises(ValueError):
            admission.receive(Connection(None, False), 'result')


if __name__ == '__main__':
    unittest.main()
