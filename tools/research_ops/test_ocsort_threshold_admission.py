"""OC-SORT .25单因素最小CPU合同；小夹具不冒充实际96帧/官方数值准入。"""
from copy import deepcopy
import io
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ocsort_threshold_runtime as runtime
import ocsort_threshold_admission as admission


class Matrix:
    def __init__(self, rows, dtype='float64'):
        self.rows = deepcopy(rows)
        self.dtype = dtype
        self.ndim = 2
        self.shape = (len(rows), len(rows[0]) if rows else 5)
    def reshape(self, shape):
        assert shape == (-1, 5)
        assert all(len(row) == 5 for row in self.rows)
        self.shape = (len(self.rows), 5)
        return self
    def __len__(self): return len(self.rows)
    def __iter__(self): return iter(self.rows)
    def tolist(self): return deepcopy(self.rows)


class FixtureNumpy:
    float32 = 'float32'
    def array(self, rows, dtype):
        assert dtype == self.float32
        return Matrix([[admission.float32(value) for value in row] for row in rows], dtype=dtype)
    def asarray(self, values): return values if isinstance(values, Matrix) else Matrix(values)


def fixture_official():
    class Counter:
        count = 999
    calls = []
    class Native:
        def __init__(self, **parameters):
            self.parameters = parameters
            Counter.count = 0
            self.frame_count = 0
            self.trackers = []
        def update(self, values, image_info, image_size):
            assert values.dtype == 'float32'
            assert image_info == image_size == (240, 400)
            calls.append(deepcopy(values.tolist()))
            self.frame_count += 1
            rows = []
            for value in values:
                if value[4] > admission.float32(self.parameters['det_thresh']):
                    Counter.count += 1
                    rows.append(value[:4]+[Counter.count])
            self.trackers = [SimpleNamespace(kf=SimpleNamespace(**{key: Matrix([[1.]])
                for key in ('F', 'H', 'P', 'Q', 'R', 'x')}))] if rows else []
            return Matrix(rows)
    return SimpleNamespace(OCSort=Native, KalmanBoxTracker=Counter, np=FixtureNumpy(),
        metadata=dict(schema='CPU_interface_fixture_not_official_numeric_admission')), calls


def comparison_fixture():
    return dict(original_ID_MOT_equal=True, all_frame_counts_equal=True, per_frame_raw_outputs_exact=True)


class ThresholdAdmissionContracts(unittest.TestCase):
    def test_source_ref_and_entire_copied_loop_AST_only_parameter_namespace_differs(self):
        contract = runtime.single_factor_contract()
        self.assertTrue(contract['copied_function_AST_identical'])
        self.assertEqual(contract['changed_parameters'], {'det_thresh': dict(before=.6, after=.25)})
        self.assertFalse(contract['original_module_globals_modified'])
        self.assertEqual(runtime._original.PARAMETERS['det_thresh'], .6)
        self.assertEqual(runtime.adapt_detections, runtime._original.adapt_detections)
        self.assertEqual(runtime._static_sha, runtime._original._static_sha)
        self.assertIs(runtime._TRACKING_LOCK, runtime._original._TRACKING_LOCK)
        changed = runtime.parameters()
        changed['max_age'] = 31
        backend, _ = fixture_official()
        with self.assertRaises(ValueError):
            runtime.track_frames(admission.boundary_frames(), backend, changed)
        self.assertEqual(runtime.PARAMETERS['max_age'], 30)

    def test_float32_strict025_boundary_literal_adapter_and_empty_frame(self):
        official, calls = fixture_official()
        frames = [admission.public_frame(frame) for frame in admission.boundary_frames()]
        before = deepcopy(frames)
        literal = admission.literal_reference(frames, official, runtime.PARAMETERS)
        actual = runtime.track_frames(frames, official, runtime.parameters())
        self.assertTrue(admission.compare_outputs(actual, literal)['per_frame_raw_outputs_exact'])
        self.assertEqual(sorted(row[0] for row in actual['raw_outputs'][0]), [110., 160.])
        self.assertEqual(actual['frame_counts'], [2, 0, 1, 1])
        self.assertEqual(len(calls), 8)
        self.assertEqual(actual['audit']['empty_input_frames'], 1)
        self.assertEqual(actual['audit']['input_dtype'], 'float32')
        self.assertFalse(actual['audit']['MOT_score_is_detection_confidence'])
        self.assertEqual(frames, before)
        self.assertEqual(actual['single_factor_contract']['effective_det_thresh'], .25)

    def test_old06_adapter_is_literal_exact_and_unchanged_on_small_fixture(self):
        official, _ = fixture_official()
        frames = [admission.public_frame(frame) for frame in admission.boundary_frames()]
        old_parameters = deepcopy(runtime._original.PARAMETERS)
        old_reference = admission.literal_reference(frames, official, old_parameters)
        old_actual = runtime._original.track_frames(frames, official, old_parameters)
        self.assertTrue(admission.compare_outputs(old_actual, old_reference)['original_ID_MOT_equal'])
        self.assertEqual(old_actual['frame_counts'], [0, 0, 1, 1])
        runtime.track_frames(frames, official, runtime.PARAMETERS)
        old_again = runtime._original.track_frames(frames, official, old_parameters)
        self.assertTrue(admission.compare_outputs(old_again, old_actual)['per_frame_raw_outputs_exact'])
        self.assertEqual(runtime._original.PARAMETERS, old_parameters)
        with self.assertRaises(ValueError):
            runtime._original.track_frames(frames, official, runtime.PARAMETERS)
        with self.assertRaises(ValueError):
            runtime.track_frames(frames, official, old_parameters)

    def test_backend_metadata_preserves_official06_default_and_explicit025_override(self):
        original = SimpleNamespace(metadata=dict(det_thresh_source='official_CLI_track_thresh_default_0.6'))
        with patch.object(runtime._original, 'load_official', return_value=original):
            result = runtime.load_official(dict(path='not_opened', sha256='fixture'))
        self.assertEqual(result.metadata['det_thresh_source'], 'official_CLI_track_thresh_default_0.6')
        self.assertEqual(result.metadata['effective_parameters'], runtime.PARAMETERS)
        self.assertEqual(result.metadata['single_factor_override'], dict(parameter='det_thresh', before=.6,
            after=.25, predeclared=True, official_default=False))
        self.assertFalse(result.metadata['single_factor_contract']['official_default_claim'])

    def test_actual_gate_schema_requires_all_boundaries_old06_and_full_output_comparison(self):
        fixture = dict(float32_equal025_excluded=True, float32_predecessor025_excluded=True,
            float32_successor025_accepted=True, score_equal06_accepted_under025=True,
            old06_parameters_unchanged=True, old06_source_bytes_unchanged=True,
            old06_regression_is_fixture_only_not12_clip_rerun=True, Kalman_internal_dtypes=['float64'],
            float32_threshold=.25, comparison=comparison_fixture(),
            old06_regression=dict(comparison=comparison_fixture()))
        result = admission.proof_fields(fixture, runtime.single_factor_contract())
        self.assertTrue(result['single_factor_parameters_verified'])
        self.assertTrue(result['threshold025_boundary']['passed'])
        self.assertTrue(result['old06_fixture_exact']['passed'])
        for key in ('float32_equal025_excluded', 'old06_source_bytes_unchanged'):
            broken = deepcopy(fixture)
            broken[key] = False
            with self.assertRaises(ValueError):
                admission.proof_fields(broken, runtime.single_factor_contract())
        broken = deepcopy(fixture)
        broken['old06_regression']['comparison']['original_ID_MOT_equal'] = False
        with self.assertRaises(ValueError):
            admission.proof_fields(broken, runtime.single_factor_contract())
        broken = deepcopy(fixture)
        broken['Kalman_internal_dtypes'] = ['float32']
        with self.assertRaises(ValueError):
            admission.proof_fields(broken, runtime.single_factor_contract())

    def test_GT_guard_and_polluted_input_reuse_exact_original_pure_helpers(self):
        self.assertIs(admission.GTGuard, admission.old.GTGuard)
        self.assertIs(admission.public_frame, admission.old.public_frame)
        self.assertIs(admission.start_worker, admission.old.start_worker)
        class Forbidden:
            def __deepcopy__(self, memo):
                raise AssertionError('不准读取GT/Pose')
        frame = admission.boundary_frames()[0]
        frame['endpoint_GT'] = Forbidden()
        frame['detections'][0]['xy_px'] = Forbidden()
        frame['detections'][0]['GT_identity'] = Forbidden()
        clean = admission.public_frame(frame)
        self.assertEqual(set(clean['detections'][0]), {'bbox_xywh_px', 'score'})
        with tempfile.TemporaryDirectory(prefix='threshold_guard_') as directory:
            path = Path(directory)/'private_GT.json'
            path.write_text('unread', encoding='utf-8')
            guard = admission.GTGuard([str(path)])
            with guard.active():
                guard.prove_blocked()
                self.assertEqual(guard.evidence()['algorithm_blocked_GT_opens'], 0)
                with self.assertRaises(admission.GTReadBlocked):
                    path.read_bytes()
                with self.assertRaises(ValueError):
                    guard.evidence()

    def test_fixed96_prefixes_no_test_no_optimizer_and_new_schema_status(self):
        self.assertEqual(admission.PREFIXES, (('A', 'SNMOT-060', 48), ('B', 'v_2QhNRucNC7E_c017', 48)))
        self.assertEqual(admission.PARAMETERS['optimizer_updates'], 0)
        self.assertFalse(admission.PARAMETERS['new_detector_or_Pose_inference'])
        self.assertEqual(admission.PARAMETERS['unique_source_frames'], 96)
        self.assertEqual(admission.STATUS, 'complete_official_threshold025_literal96_ABA_two_spawn_exact_GT_guard_and_exit_verified')
        for path in ('D:/projects/FutsalMOT_Research/test/cache.jsonl',
                     'D:/projects/FutsalMOT_Research/pose/SNMOT-116/cache.jsonl'):
            with self.assertRaises(ValueError):
                admission.physical(path)


if __name__ == '__main__':
    unittest.main()
