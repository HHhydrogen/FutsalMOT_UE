"""截距追踪的最小CPU合同；夹具仅核接口/隔离，不冒充真实模型或96帧准入。"""
from collections import OrderedDict
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trainR_intercept_tracking as tracking


class FixtureTensor:
    dtype = 'float32'
    shape = (2,)
    def detach(self): return self
    def cpu(self): return self
    def contiguous(self): return self
    def numpy(self): return self
    def tobytes(self): return struct.pack('<ff', 1., -2.)
    def numel(self): return 2
    def element_size(self): return 4


class FixtureModel:
    def __init__(self, route): self.route, self.calls = route, []
    def state_dict(self): return {'weight': FixtureTensor()}
    def __call__(self, value): self.calls.append(value)


class FixtureIDs:
    _count = 999
    @staticmethod
    def reset_id(): FixtureIDs._count = 0


class FixtureTracker:
    def __init__(self, **arguments):
        assert arguments['mode'] == 'learned' and arguments['use_pose'] is False
        self.arguments = arguments
        self.previous, self.sequence, self.frame_id = -1, None, 0
        self.tracked_stracks, self.lost_stracks, self.removed_stracks = [], [], []
        self.audit = dict(learned_pairs=0, low_score_stage='unchanged_upstream_bbox_only')
    def update_frame(self, frame):
        self.previous, self.sequence = frame['frame_index'], frame['sequence']
        self.frame_id += 1
        self.arguments['model']([d['uid'] for d in frame['detections']])
        self.audit['learned_pairs'] += len(frame['detections'])
        result = []
        for detection in frame['detections']:
            FixtureIDs._count += 1
            x, y, w, h = detection['bbox_xywh_px']
            result.append([x, y, x+w, y+h, FixtureIDs._count, detection['score'], 0., 0.])
        return result


class FixtureRNG:
    def clone(self): return self


class FixtureCache:
    def __init__(self): self.items = OrderedDict()
    def stats(self): return dict(retained_count=len(self.items))
    def clear(self): self.items.clear()


def worker_fixture(root):
    job = dict(job_id='job_A', model_id='model_A', regime='R', fold='game4', seed=20261024, sequence='SNMOT-060')
    source_ref = dict(path=str(root/'not_opened_cache.jsonl'), sha256='source_fixture')
    cfg = dict(output_root=str(root), numeric_authorized=True, jobs=[job], sources={'SNMOT-060': dict(cache=source_ref)})
    worker = tracking.TrackWorker.__new__(tracking.TrackWorker)
    worker.cfg, worker.jobs, worker.closed = cfg, 0, False
    worker.scope = dict(numerical_AST_unchanged=True, modified_AST_nodes='one_frame_scope_guard_only')
    worker.cls, worker.BaseTrack, worker.STrack = FixtureTracker, FixtureIDs, FixtureIDs
    worker.guard = SimpleNamespace(blocked=[], proof=lambda: dict(blocked_open_attempts=0, python_open_audit_installed=True))
    worker.torch = SimpleNamespace(no_grad=nullcontext, get_rng_state=FixtureRNG, equal=lambda a, b: True)
    worker.binding = SimpleNamespace(training=dict(pose_checkpoint_sha256='f'*64), protocol=dict(sha256='protocol_fixture'),
        spec=lambda value: job if value == job else (_ for _ in ()).throw(ValueError('unknown job')),
        closure=lambda: dict(source_closure_verified=True))
    normalizer = SimpleNamespace(state=lambda: dict(fixture_original_feature_dim=194, use_pose=False))
    model = FixtureModel('base')
    loaded = dict(base=model, shifted=FixtureModel('calibrated'), zero=FixtureModel('zero_wrapper'),
        normalizer=normalizer, binding=dict(fixture=True), loading_receipt=dict(fixture=True), beta32=-.25,
        fit=dict(path=str(root/'not_opened_fit.json'), sha256='fit_fixture'), cache_key='key')
    frames = [dict(sequence='SNMOT-060', game='game4', fps=25, frame_index=index, frame_number=index+1,
        timestamp_sec=index/25, width=100, height=100, detections=[dict(uid='u', bbox_xywh_px=[1., 2., 3., 4.],
            score=.9, xy_px=[[1., 2.]]*17, geometry_valid=[True]*17, timestamp_sec=0., image_wh=[100, 100])]
        if index == 0 else []) for index in range(2)]
    worker.frames = lambda sequence: frames
    worker.model = lambda value: loaded
    worker.model_hashes = {'key': (tracking.model_state_sha(model), tracking.canonical(normalizer.state()))}
    worker.input_hashes = {}
    worker.frames_cache, worker.model_cache = FixtureCache(), FixtureCache()
    return worker, job, loaded, frames


class InterceptTrackingContracts(unittest.TestCase):
    def test_public_frame_whitelist_keeps_original_predicted_Pose_and_detection_identity(self):
        class Forbidden:
            def __deepcopy__(self, memo): raise AssertionError('不得读取评价GT或其他字段')
        frame = dict(sequence='S', game='game4', fps=25, frame_index=0, frame_number=1, timestamp_sec=0.,
            width=100, height=100, endpoint_GT=Forbidden(), detections=[dict(uid='u', detection_id='different',
                bbox_xywh_px=[1., 2., 3., 4.], score=.9, xy_px=[[1., 2.]]*17, geometry_valid=[True]*17,
                timestamp_sec=0., image_wh=[100, 100], GT_identity=Forbidden())])
        public = tracking.public_frame(frame)
        self.assertNotIn('endpoint_GT', public)
        self.assertNotIn('GT_identity', public['detections'][0])
        self.assertEqual(public['detections'][0]['detection_id'], 'different')
        self.assertEqual(public['detections'][0]['xy_px'], frame['detections'][0]['xy_px'])
        public['detections'][0]['bbox_xywh_px'][0] = 999.
        self.assertEqual(frame['detections'][0]['bbox_xywh_px'][0], 1.)

    def test_exact180_model_source_matrix_does_not_allow_wrong_heldout_or_seed(self):
        models = [dict(model_id=regime+'_'+fold+'_'+str(seed), regime=regime, fold=fold, seed=seed)
            for regime in ('R', 'RS') for fold in ('game4', 'game6', 'game9') for seed in (20261024, 20261025, 20261026)]
        cfg = dict(panels=dict(old_external=['E1', 'E2'], seven_observed=['N'+str(i) for i in range(7)]))
        cells = tracking.expected_cells(models, cfg)
        cfg['jobs'] = [dict(job_id=str(i), model_id=m, regime=r, fold=f, seed=s, sequence=q)
            for i, (m, r, f, s, q) in enumerate(sorted(cells))]
        tracking.validate_jobs(cfg, dict(models=models))
        broken = deepcopy(cfg)
        broken['jobs'][0]['sequence'] = 'SNMOT-151' if broken['jobs'][0]['fold'] != 'game9' else 'SNMOT-060'
        with self.assertRaises(ValueError):
            tracking.validate_jobs(broken, dict(models=models))
        broken = deepcopy(cfg)
        broken['jobs'].pop()
        with self.assertRaises(ValueError):
            tracking.validate_jobs(broken, dict(models=models))

    def test_payload_routes_original_zero_calibrated_and_resets_ID_each_job(self):
        with tempfile.TemporaryDirectory(prefix='intercept_track_') as temporary:
            worker, job, loaded, frames = worker_fixture(Path(temporary))
            before = deepcopy(frames)
            original = worker.original_beta0_payload(job, prefix_frames=2)
            zero = worker.payload(job, diagnostic_beta0=True, prefix_frames=2)
            calibrated = worker.payload(job, prefix_frames=2)
            self.assertEqual(len(loaded['base'].calls), 2)
            self.assertEqual(len(loaded['zero'].calls), 2)
            self.assertEqual(len(loaded['shifted'].calls), 2)
            self.assertTrue(original['original_base_forward_without_intercept_wrapper'])
            self.assertFalse(zero['original_base_forward_without_intercept_wrapper'])
            self.assertEqual(calibrated['beta32'], -.25)
            self.assertEqual(zero['beta32'], 0.)
            self.assertEqual(original['raw_frames'], zero['raw_frames'])
            self.assertEqual(original['frame_counts'], [1, 0])
            self.assertEqual(calibrated['global_ID_before'], 0)
            self.assertEqual(calibrated['raw_frames'][0][0][4], 1)
            self.assertEqual(frames, before)
            self.assertTrue(tracking.compare_payloads(zero, original)['original_ID_MOT_exact'])
            repeated = worker.payload(job, prefix_frames=2)
            self.assertTrue(tracking.compare_payloads(repeated, calibrated)['audit_exact'])
            worker.cfg['numeric_authorized'] = False
            with self.assertRaises(ValueError): worker.payload(job, prefix_frames=2)
            with self.assertRaises(ValueError): worker.original_beta0_payload(job, prefix_frames=2)

    def test_all_native_outputs_audit_and_GT_boundaries_are_required_not_only_MOT(self):
        with tempfile.TemporaryDirectory(prefix='intercept_compare_') as temporary:
            worker, job, _, _ = worker_fixture(Path(temporary))
            value = worker.payload(job)
            for key, bad in (('audit', {}), ('frame_counts', [0, 1]), ('raw_frames', [[], []]),
                             ('global_ID_before', 9), ('evaluation_GT_coordinate_files_opened', True)):
                changed = deepcopy(value)
                changed[key] = bad
                with self.assertRaises(ValueError, msg=key): tracking.compare_payloads(changed, value)
            changed = deepcopy(value)
            changed['GT_guard']['blocked_open_attempts'] = 1
            with self.assertRaises(ValueError): tracking.compare_payloads(changed, value)

    def test_tracking_receipt_keeps_full_MOT_and_exact_sources_without_alias_or_duplicate_arrays(self):
        with tempfile.TemporaryDirectory(prefix='intercept_receipt_') as temporary:
            root = Path(temporary)
            worker, job, _, _ = worker_fixture(root)
            output = root/'run/tracking'
            result = worker.run(job, output)
            receipt = tracking.read_ref(result['receipt'])
            self.assertEqual(receipt['schema'], 'trainR_intercept_tracking_receipt_v1')
            self.assertEqual(receipt['job'], job)
            self.assertEqual(receipt['beta32'], -.25)
            self.assertFalse(receipt['alias_used'])
            self.assertFalse(receipt['diagnostic_beta0'])
            self.assertIsNone(receipt['prefix_frames'])
            self.assertTrue(receipt['calibration_trainR_metadata_parsed'])
            self.assertFalse(receipt['evaluation_GT_coordinate_files_opened'])
            self.assertNotIn('raw_frames', receipt)
            self.assertEqual(tracking.sha(output/'data/SNMOT-060.txt'), receipt['mot']['sha256'])
            with self.assertRaises(ValueError): worker.run(job, output)
            evidence = worker.close()
            self.assertEqual(evidence['status'], 'closed')
            self.assertTrue(evidence['source_closure_verified'])
            with self.assertRaises(ValueError): worker.payload(job)

    def test_original_metric_four_function_AST_and_unmatched_predictions_retained(self):
        source = Path(__file__).parent/'v10_metric.py'
        reference = tracking.ref(source)
        binding = SimpleNamespace(old=dict(), old_rt=SimpleNamespace(require=tracking.require),
            source=lambda cfg, path: reference)
        metric, evidence = tracking.metric_functions(binding)
        self.assertEqual(evidence['numerical_functions'], ['plain', 'prediction_rows', 'validate_count', 'trackeval_numeric'])
        self.assertTrue(evidence['numerical_function_AST_unchanged'])
        text = '1,1,0,0,10,10,.9,-1,-1,-1\n1,2,90,90,5,5,.1,-1,-1,-1\n'
        predictions, count = metric.prediction_rows(text, 2)
        self.assertEqual(count, 2)
        self.assertEqual([row['uid'] for row in predictions[1]], ['1', '2'])
        metric.validate_count('COMBINED_SEQ', dict(Dets=2, GT_Dets=1), 2, 1, 'S', 2)
        with self.assertRaises(ValueError): metric.validate_count('S', dict(Dets=1, GT_Dets=1, Frames=2), 2, 1, 'S', 2)

    def test_numeric_close_proves_actual_PID_join_and_rejects_wrong_PID(self):
        class Connection:
            def __init__(self, reply): self.reply, self.closed, self.sent = reply, False, []
            def send(self, value): self.sent.append(value)
            def poll(self, timeout): return True
            def recv(self): return self.reply
            def close(self): self.closed = True
        class Process:
            pid, exitcode = 123, 0
            def join(self, seconds): self.joined = True
            def is_alive(self): return False
        reply = dict(status='closed', worker_pid=123, closure=dict(status='closed', worker_pid=123))
        connection, process = Connection(reply), Process()
        result = tracking._close_numeric(dict(connection=connection, process=process, ready=dict(worker_pid=123)))
        self.assertTrue(result['joined'])
        self.assertTrue(connection.closed)
        bad = deepcopy(reply)
        bad['closure']['worker_pid'] = 999
        with self.assertRaises(ValueError):
            tracking._close_numeric(dict(connection=Connection(bad), process=Process(), ready=dict(worker_pid=123)))

    def test_numeric_gate_rejects_formal_authorization_before_external_execution(self):
        with tempfile.TemporaryDirectory(prefix='intercept_numeric_scope_') as temporary:
            cfg = dict(phase='formal', tracking_authorized=True, numeric_authorized=False)
            with self.assertRaises(ValueError):
                tracking.numeric_admission(cfg, Path(temporary)/'not_opened.json', Path(temporary)/'not_created')
            self.assertFalse((Path(temporary)/'not_created').exists())
        with self.assertRaises(ValueError): tracking.safe('D:/projects/FutsalMOT_Research/test/cache.jsonl')
        with self.assertRaises(ValueError): tracking.safe('D:/projects/FutsalMOT_Research/pose/SNMOT-187/gt.txt')


if __name__ == '__main__':
    unittest.main()
