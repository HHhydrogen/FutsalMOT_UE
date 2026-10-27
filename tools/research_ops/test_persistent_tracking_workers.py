"""常驻track纯CPU夹具；不加载研究模型、实际比赛、GPU或metric。"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from persistent_tracking_workers import BoundedLRU, GTReadGuard, TrackingCore, digest, sha


class Adapter:
    def state(self): return dict(normalizer_sha='fixture_normalizer', unchanged=True)


class FixtureBackend:
    def __init__(self):
        self.count = self.model_loads = self.frame_loads = self.closure_checks = 0
        self.disabled = False; self.mutate_model = False
        self.frames = [dict(frame_number=i+1, value=[float(i)], detections=[dict(xy_px=[[1., 2.]])]) for i in range(3)]

    def frame_identity(self, job): return dict(protocol='frozen_fixture', input_sha=digest(self.frames))
    def load_frames(self, job): self.frame_loads += 1; return deepcopy(self.frames)
    def model_identity(self, job): return dict(protocol='frozen_fixture', model_sha='model_' + job['group'], adapter_sha='adapter')
    def load_model(self, job):
        self.model_loads += 1
        return dict(weight=1., buffer=0., training=True), Adapter(), dict(group=job['group'])
    def prepare_model(self, model): model['training'] = False
    def model_sha(self, model): return digest({k: model[k] for k in ('weight', 'buffer')})
    def model_bytes(self, model): return 16
    def id_count(self): return self.count
    @contextmanager
    def no_grad(self):
        self.disabled = True
        try: yield
        finally: self.disabled = False
    def verify_closure(self): self.closure_checks += 1; return dict(checked=True, GT_coordinates_read=False)
    def new_tracker(self, job, model, adapter):
        self.count = 0; backend = self
        class Tracker:
            def __init__(self): self.audit = dict(frames=0, fresh_history=True); self.identity = None
            def update_frame(self, frame):
                assert backend.disabled and not model['training']
                if self.identity is None: backend.count += 1; self.identity = backend.count
                self.audit['frames'] += 1
                # 模拟第三方tracker改写传入字典，不能影响共享只读缓存。
                frame['detections'][0]['xy_px'][0][0] = 999.
                if backend.mutate_model: model['buffer'] += 1.
                offset = 0. if job['pose_enabled'] else .5
                return [[offset, 0., 10.+offset, 20., self.identity, .9]]
        return Tracker(), dict(fixture_only=True), dict(feature_calls=0, adapter_transform_pair_calls=0), 'fixture', self.count


def job(on=True, group='T_RS'):
    return dict(group=group, pose_enabled=on, sequence='fixture', fold='game4', seed=20261024)


class PersistentWorkerTests(unittest.TestCase):
    def core(self, backend):
        return TrackingCore(backend, frame_cache_bytes=100000, model_cache_bytes=32, max_models=2)

    def test_cold_A_and_A_B_A_keep_original_ID_MOT_counts_audit(self):
        cold_backend = FixtureBackend(); cold = self.core(cold_backend)
        cold_A = cold.execute(job()); cold.close()
        backend = FixtureBackend(); core = self.core(backend)
        A1 = core.execute(job()); B = core.execute(job(False)); A2 = core.execute(job())
        for key in ('mot', 'frame_counts', 'audit', 'binding'):
            self.assertEqual(cold_A[key], A1[key]); self.assertEqual(A1[key], A2[key])
        self.assertNotEqual(A1['mot'], B['mot'])
        self.assertEqual((A1['global_track_ID_before'], B['global_track_ID_before'], A2['global_track_ID_before']), (0, 0, 0))
        self.assertEqual(A1['mot'].splitlines()[0].split(',')[1], '1')
        self.assertEqual(A1['model_cache_key'], B['model_cache_key'])
        self.assertEqual((backend.model_loads, backend.frame_loads), (1, 1))
        self.assertTrue(A2['cached_frames_unchanged']); self.assertEqual(backend.frames[0]['detections'][0]['xy_px'][0][0], 1.)
        close = core.close(); self.assertEqual(close['status'], 'closed_worker_caches_verified')
        self.assertTrue(close['process_exit_not_yet_asserted']); self.assertEqual(backend.closure_checks, 1)

    def test_GT_guard_rejects_actual_file_open_including_hash(self):
        with tempfile.TemporaryDirectory(prefix='track_GT_guard_fixture_') as directory:
            root = Path(directory); files = [root/'gt.txt', root/'gameinfo.ini', root/'endpoint_registry.json']
            for path in files: path.write_text('不可交给track的坐标/标签', encoding='utf-8')
            guard = GTReadGuard(files); guard.install()
            for path in files:
                with self.assertRaises(PermissionError): path.read_text(encoding='utf-8')
                with self.assertRaises(PermissionError): sha(path)
            public = root/'source_config.json'; public.write_text('{"gt_ref":"只含路径和SHA"}', encoding='utf-8')
            self.assertIn('gt_ref', public.read_text(encoding='utf-8'))
            self.assertEqual(guard.proof()['blocked_open_attempts'], 6)

    def test_bound_cache_and_eviction_no_retry(self):
        cache = BoundedLRU(16, max_items=1); calls = []
        def load(name):
            calls.append(name); return name, 8
        self.assertEqual(cache.get('a', lambda: load('a')), 'a')
        self.assertEqual(cache.get('a', lambda: load('not_called')), 'a')
        cache.get('b', lambda: load('b'))
        self.assertEqual(list(cache.items), ['b']); self.assertEqual(calls, ['a', 'b'])
        with self.assertRaises(ValueError): cache.get('oversized', lambda: ('x', 17))
        self.assertEqual(cache.stats()['peak_counted_bytes'], 8)

    def test_model_buffer_mutation_fails_and_worker_cannot_retry(self):
        backend = FixtureBackend(); backend.mutate_model = True; core = self.core(backend)
        with self.assertRaises(ValueError): core.execute(job())
        backend.mutate_model = False
        with self.assertRaises(ValueError): core.execute(job())
        close = core.close(); self.assertEqual(close['status'], 'closed_failed_no_retry')
        self.assertTrue(close['verification_errors']); self.assertEqual(backend.closure_checks, 1)

    def test_context_model_and_input_SHA_are_cache_identity(self):
        backend = FixtureBackend(); core = self.core(backend)
        a = core.execute(job()); b = core.execute(job(group='T_R'))
        self.assertNotEqual(a['model_cache_key'], b['model_cache_key'])
        backend.frames[0]['value'][0] = 5.
        c = core.execute(job())
        self.assertNotEqual(a['input_cache_key'], c['input_cache_key'])
        self.assertEqual(backend.frame_loads, 2); self.assertEqual(backend.model_loads, 2)
        core.close()


if __name__ == '__main__':
    unittest.main()
