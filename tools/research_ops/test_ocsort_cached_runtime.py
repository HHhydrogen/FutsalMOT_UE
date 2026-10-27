"""缓存适配的CPU夹具与实际官方AST合同；不执行12场或伪造官方效果。"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ocsort_cached_runtime as runtime

MANIFEST = Path('D:/projects/FutsalMOT_Research/references/ocsort_official')/runtime.COMMIT/'source_manifest.json'


class Matrix:
    def __init__(self, rows, dtype='float64'):
        self.rows = deepcopy(rows); self.dtype = dtype; self.ndim = 2; self.shape = (len(rows), len(rows[0]) if rows else 5)
    def reshape(self, shape):
        assert shape == (-1, 5)
        assert all(len(r) == 5 for r in self.rows)
        self.shape = len(self.rows), 5
        return self
    def __len__(self): return len(self.rows)
    def __iter__(self): return iter(self.rows)
    def tolist(self): return deepcopy(self.rows)


class FixtureNumpy:
    """只检查接口，不实现关联或模拟官方数值。"""
    float32 = 'float32'
    def array(self, values, dtype): return Matrix(values, dtype)
    def asarray(self, values): return values if isinstance(values, Matrix) else Matrix(values)


class Detection(dict):
    def __getitem__(self, key):
        if key not in ('bbox_xywh_px', 'score'):
            raise AssertionError('不准读取UID/Pose/GT等非官方数值输入')
        return super().__getitem__(key)


def frames():
    detections = [Detection(bbox_xywh_px=[-3.75, 1.125, .25, 10.25], score=s,
                            xy_px='不可读', geometry_valid='不可读', GT='不可读') for s in (.1, .6, .91)]
    return [dict(sequence='fixture', fps=25, frame_index=i, frame_number=i+1,
                 timestamp_sec=i/25, width=1280, height=720, detections=detections if i != 1 else []) for i in range(3)]


def official_fixture():
    class Counter:
        count = 999
    calls = []
    class Native:
        def __init__(self, **parameters):
            assert parameters == runtime.PARAMETERS
            Counter.count = 0; self.frame_count = 0; self.trackers = []
        def update(self, values, img_info, img_size):
            assert values.dtype == 'float32'
            assert img_info == img_size == (720, 1280)
            calls.append(values.tolist()); self.frame_count += 1
            rows = []
            for row in values:
                Counter.count += 1
                rows.append(row[:4]+[Counter.count])
                row[0] = 999.  # 只准修改本次新array，不能污染缓存原框。
            return Matrix(rows)
    return SimpleNamespace(OCSort=Native, KalmanBoxTracker=Counter, np=FixtureNumpy(),
                           metadata={'schema': 'explicit_fixture_not_official_numerical_proof'}), calls


class CachedOCSortTests(unittest.TestCase):
    def test_actual_official_constructor_and_CLI_defaults_AST(self):
        self.assertTrue(MANIFEST.is_file(), '本任务已固定的真实上游源码缺失')
        contract = runtime.inspect_source_contract(runtime.ref(MANIFEST))
        self.assertEqual(contract['constructor_arguments'], list(runtime.PARAMETERS))
        self.assertEqual(contract['constructor_defaults'], {k: v for k, v in runtime.PARAMETERS.items() if k != 'det_thresh'})
        self.assertEqual(len(contract['loaded_algorithm_files']), 3)
        self.assertEqual(contract['commit'], runtime.COMMIT)
        self.assertFalse(contract['numerical_source_modified'])

    def test_new_N5_score_unchanged_bbox_only_no_filter_no_forbidden_fields(self):
        data = frames(); before = deepcopy(data)
        adapted = runtime.adapt_detections(data[0], FixtureNumpy())
        self.assertEqual(adapted.shape, (3, 5)); self.assertEqual(adapted.dtype, 'float32')
        self.assertEqual([row[4] for row in adapted], [.1, .6, .91])
        self.assertEqual(adapted.tolist()[0][:4], [-3.75, 1.125, -3.5, 11.375])
        self.assertEqual(data, before)
        self.assertEqual(runtime.adapt_detections(data[1], FixtureNumpy()).shape, (0, 5))

    def test_empty_every_frame_scale1_native_ID_and_constant_MOT_score(self):
        data = frames(); original = deepcopy(data); official, calls = official_fixture()
        first = runtime.track_frames(data, official, runtime.parameters(), input_reference={'sha256': 'fixture'})
        second = runtime.track_frames(data, official, runtime.parameters())
        self.assertEqual(first['mot_text'], second['mot_text'])
        self.assertEqual(first['frame_counts'], [3, 0, 3]); self.assertEqual(len(calls), 6)
        self.assertEqual(first['raw_outputs'][0][0], [-3.75, 1.125, -3.5, 11.375, 1])
        row = first['mot_text'].splitlines()[0].split(',')
        self.assertEqual(row[:2], ['1', '1']); self.assertEqual(row[6], '1')
        self.assertEqual(first['audit']['raw_detections'], 6)
        self.assertEqual(first['audit']['empty_input_frames'], 1)
        self.assertFalse(first['audit']['MOT_score_is_detection_confidence'])
        self.assertEqual(data, original)

    def test_missing_dependency_is_explicit_and_no_numerical_fallback(self):
        def importer(name):
            if name in ('filterpy.stats', 'lap'): raise ModuleNotFoundError(name)
            return SimpleNamespace(__version__=runtime.DEPENDENCY_VERSIONS.get(name))
        with self.assertRaisesRegex(runtime.OfficialDependencyError, 'filterpy.stats'):
            runtime.dependency_modules(importer)
        def no_lap(name):
            if name == 'lap': raise ModuleNotFoundError(name)
            return SimpleNamespace(__version__=runtime.DEPENDENCY_VERSIONS.get(name))
        with self.assertRaisesRegex(runtime.OfficialDependencyError, 'lap'):
            runtime.dependency_modules(no_lap)

    def test_bad_order_parameter_or_nonfinite_input_rejected_not_filtered(self):
        official, _ = official_fixture(); data = frames()
        data[1]['frame_number'] = 3
        with self.assertRaises(ValueError): runtime.track_frames(data, official, runtime.parameters())
        parameters = runtime.parameters(); parameters['det_thresh'] = .5
        with self.assertRaises(ValueError): runtime.track_frames(frames(), official, parameters)
        data = frames(); data[0]['detections'][0]['score'] = float('nan')
        with self.assertRaises(ValueError): runtime.adapt_detections(data[0], FixtureNumpy())
        # 异常后释放本进程锁，但上层依然不能重放已存在的输出目录。
        runtime.track_frames(frames(), official, runtime.parameters())


if __name__ == '__main__':
    unittest.main()
