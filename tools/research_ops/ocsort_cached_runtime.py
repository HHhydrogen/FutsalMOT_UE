"""固定官方OCSort core的检测缓存适配；不包含检测器、Pose或GT。"""
import ast
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import threading
import types

COMMIT = '8462e7e729a93ccd3bd995c0a79a890336cb3a0b'
REPOSITORY = 'https://github.com/noahcao/OC_SORT'
FILES = ('README.md', 'LICENSE', 'requirements.txt', 'utils/args.py', 'docs/GET_STARTED.md',
         'trackers/ocsort_tracker/ocsort.py', 'trackers/ocsort_tracker/association.py', 'trackers/ocsort_tracker/kalmanfilter.py')
ALGORITHM_SHA = {
    'trackers/ocsort_tracker/ocsort.py': '122cc1c27d3321eac0debdf3ba782b76d189e1ac878256b8291ffeb4314fa979',
    'trackers/ocsort_tracker/association.py': 'c009a78eaa1c35c1d61217506255051ba882a7b99f9505cdec64da474ff0fbd7',
    'trackers/ocsort_tracker/kalmanfilter.py': '165a2d5243f2b874e37d3a3ae8112402f5c53ddfb6eb6e2cddda3311c3a2cded'}
PARAMETERS = dict(det_thresh=.6, max_age=30, min_hits=3, iou_threshold=.3, delta_t=3,
                  asso_func='iou', inertia=.2, use_byte=False)
DEPENDENCY_VERSIONS = {'numpy': '2.2.6', 'scipy': '1.15.3', 'filterpy': '1.4.5', 'lap': '0.5.13'}
_TRACKING_LOCK = threading.Lock()


class OfficialDependencyError(ImportError):
    """缺少原码实际依赖时停止，不能替换Kalman或关联实现。"""


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def safe(path):
    path = Path(os.path.abspath(path))
    require(not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
                    for p in path.parts), '最终测试继续封存')
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            info = p.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '官方来源不跟随junction或符号链接')
    return path


def sha(path): return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def read(path): return json.loads(safe(path).read_text(encoding='utf-8-sig'))
def ref(path): return dict(path=str(path), sha256=sha(path))


def parameters(): return deepcopy(PARAMETERS)


def inspect_source_contract(manifest_ref):
    """仅AST核验真实上游签名/CLI默认，不要求已装数值依赖。"""
    path = safe(manifest_ref['path'])
    require(sha(path) == manifest_ref['sha256'], '官方manifest SHA改变')
    manifest = read(path)
    require(manifest['schema'] == 'official_ocsort_source_manifest_v1'
            and manifest['status'] == 'complete_minimal_official_source_not_tracking'
            and manifest['repository'] == REPOSITORY and manifest['commit'] == COMMIT,
            '只能读取事前固定官方commit来源')
    source = safe(manifest['source_root']); entries = manifest['files']
    require(len(entries) == len(FILES) and {e['path'] for e in entries} == set(FILES), '官方最小来源不完整/重复')
    for entry in entries:
        p = safe(source/entry['path'])
        require(source in p.parents and p.is_file() and p.stat().st_size == entry['size']
                and sha(p) == entry['sha256'] and entry['url'] ==
                'https://raw.githubusercontent.com/noahcao/OC_SORT/'+COMMIT+'/'+entry['path'], '原始源码/来源URL/尺寸改变')
        if entry['path'] in ALGORITHM_SHA:
            require(entry['sha256'] == ALGORITHM_SHA[entry['path']], '三个算法文件必须原始固定字节')
    tree = ast.parse((source/'trackers/ocsort_tracker/ocsort.py').read_text(encoding='utf-8'))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'OCSort']
    require(len(classes) == 1, '官方OCSort类结构改变')
    init = next(n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
    arguments = [a.arg for a in init.args.args]
    defaults = dict(zip(arguments[-len(init.args.defaults):], [ast.literal_eval(v) for v in init.args.defaults]))
    require(arguments == ['self']+list(PARAMETERS) and defaults == {k: v for k, v in PARAMETERS.items() if k != 'det_thresh'},
            '真实官方构造签名或默认数值改变')
    args_tree = ast.parse((source/'utils/args.py').read_text(encoding='utf-8'))
    cli = [n for n in ast.walk(args_tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr == 'add_argument' and n.args and isinstance(n.args[0], ast.Constant)
           and n.args[0].value == '--track_thresh']
    require(len(cli) == 1 and next(ast.literal_eval(k.value) for k in cli[0].keywords if k.arg == 'default') == .6,
            '官方CLI检测阈值默认不同')
    return dict(manifest=deepcopy(manifest_ref), source_root=str(source), commit=COMMIT, repository=REPOSITORY,
        constructor_arguments=arguments[1:], constructor_defaults=defaults, det_thresh_source='official_CLI_track_thresh_default_0.6',
        numerical_source_modified=False, loaded_algorithm_files={e['path']: e['sha256'] for e in entries if e['path'] in ALGORITHM_SHA})


def dependency_modules(importer=importlib.import_module):
    result = {}
    for name in ('numpy', 'scipy', 'filterpy', 'filterpy.stats', 'filterpy.common', 'lap'):
        try: result[name] = importer(name)
        except (ImportError, ModuleNotFoundError) as error:
            raise OfficialDependencyError('官方OCSort固定原码依赖不可用：'+name+'；停止，不安装或改写数值。原错误：'+repr(error)) from error
    require(all(getattr(result[name], '__version__', None) == version for name, version in DEPENDENCY_VERSIONS.items()),
            '事前固定的NumPy/SciPy/FilterPy/lap版本改变')
    require(callable(getattr(result['lap'], 'lapjv', None)), '锁定lap.lapjv不可用，不能隐式回退其他求解器')
    return result


def _load_official_impl(manifest_ref):
    """独立包命名空间只表达原相对导入，不改源码、不移动旧runtime。"""
    metadata = inspect_source_contract(manifest_ref)
    dependencies = dependency_modules()
    root = Path(metadata['source_root'])/'trackers/ocsort_tracker'
    name = '_futsalmot_official_ocsort_'+COMMIT
    # 不借用任何已存在同名模块；每次加载仍完整核验原字节。
    if name+'.ocsort' in sys.modules:
        module = sys.modules[name+'.ocsort']
        require(safe(module.__file__) == safe(root/'ocsort.py'), '官方模块命名空间被其他来源占用')
    else:
        package = types.ModuleType(name); package.__path__ = [str(root)]; package.__package__ = name
        sys.modules[name] = package
        previous = sys.dont_write_bytecode; sys.dont_write_bytecode = True
        try:
            spec = importlib.util.spec_from_file_location(name+'.ocsort', root/'ocsort.py')
            module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
        except BaseException:
            for key in [k for k in sys.modules if k == name or k.startswith(name+'.')]: sys.modules.pop(key, None)
            raise
        finally: sys.dont_write_bytecode = previous
    require(list(inspect.signature(module.OCSort).parameters) == list(PARAMETERS), '实际导入构造器与原AST不一致')
    for suffix, filename in (('ocsort', 'ocsort.py'), ('association', 'association.py'), ('kalmanfilter', 'kalmanfilter.py')):
        loaded = sys.modules[name+'.'+suffix]
        require(safe(loaded.__file__) == safe(root/filename) and sha(loaded.__file__) == ALGORITHM_SHA['trackers/ocsort_tracker/'+filename],
                '实际算法模块不是原manifest源码')
    association = sys.modules[name+'.association']
    require(module.linear_assignment is association.linear_assignment, '实际分配函数不是原官方关联模块')
    solver_module = importlib.import_module(dependencies['lap'].lapjv.__module__)
    metadata.update(schema='official_ocsort_cached_backend_v1', input='new_numpy_float32_N5_xyxy_score',
        update_entry='OCSort.update_not_update_public', score_export='MOT_constant_1_not_detection_confidence',
        no_demo_min_area_or_aspect_filter=True, full_demo_pipeline_reproduction=False, paper2023_byte_reproduction=False,
        actual_assignment_backend='lap.lapjv', scipy_assignment_fallback_allowed=False,
        assignment_binary_source=dict(path=str(solver_module.__file__), sha256=sha(solver_module.__file__)),
        native_Kalman_precision='original_float64_matrices_and_operations_not_cast_to_FP32',
        dependency_sources={k: dict(path=str(v.__file__), sha256=sha(v.__file__)) for k, v in dependencies.items()},
        dependency_versions={k: getattr(v, '__version__', None) for k, v in dependencies.items()})
    return types.SimpleNamespace(module=module, OCSort=module.OCSort, KalmanBoxTracker=module.KalmanBoxTracker,
                                 np=dependencies['numpy'], metadata=metadata)


def load_official(manifest_ref):
    """整个来源/依赖导入边界禁止生成pyc，不在冻结引用目录写缓存。"""
    previous = sys.dont_write_bytecode; sys.dont_write_bytecode = True
    try: return _load_official_impl(manifest_ref)
    finally: sys.dont_write_bytecode = previous


def adapt_detections(frame, np):
    """只访问原bbox/score；缺失Pose的bbox-only检测也原样交给官方core。"""
    rows = []
    for detection in frame['detections']:
        box, score = detection['bbox_xywh_px'], detection['score']
        require(len(box) == 4 and all(type(v) in (float, int) and math.isfinite(v) for v in [*box, score])
                and min(box[2:]) > 0 and 0 <= score <= 1, '原bbox/score非法，不能静默筛去')
        x, y, width, height = box
        rows.append([x, y, x+width, y+height, score])
    values = np.array(rows, dtype=np.float32).reshape((-1, 5))
    require(str(values.dtype) == 'float32' and values.shape == (len(rows), 5)
            and all(math.isfinite(float(v)) for row in values for v in row), '原FP32 N5输入非有限/结构改变')
    return values


def _static_sha(counter):
    values = {}
    for key in ('_F', '_H'):
        if hasattr(counter, key):
            matrix = getattr(counter, key)
            values[key] = hashlib.sha256(matrix.tobytes()).hexdigest()
    return values


def _track_frames_impl(frames, official, parameters, input_reference):
    """纯CPU单job：所有帧调用原core，返回原ID全部自然输出，不写文件。"""
    require(parameters == PARAMETERS and set(parameters) == set(PARAMETERS), '事前官方参数必须固定，不按结果调参')
    np = official.np; official.KalmanBoxTracker.count = 0
    static_before = _static_sha(official.KalmanBoxTracker)
    tracker = official.OCSort(**deepcopy(parameters))
    require(tracker.frame_count == 0 and not tracker.trackers and official.KalmanBoxTracker.count == 0, '新job原生状态/ID未重置')
    sequence = None; geometry = None; counts = []; raw_counts = []; raw_outputs = []; text = []; input_chain = '0'*64
    for index, frame in enumerate(frames):
        require(type(frame['frame_index']) is int and frame['frame_index'] == index and frame['frame_number'] == index+1
                and frame['fps'] == 25 and abs(frame['timestamp_sec']-index/25) < 1e-9,
                '所有原帧含空检测必须按一基帧号完整顺序消费')
        current_sequence = frame['sequence']; require(not re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', current_sequence.lower()), '最终序列封存')
        size = frame['height'], frame['width']
        require(all(type(x) is int and x > 0 for x in size) and sequence in (None, current_sequence)
                and geometry in (None, size), '每job只准同源同尺寸序列')
        sequence, geometry = current_sequence, size
        values = adapt_detections(frame, np); raw_counts.append(len(values))
        public_input = dict(frame_number=index+1, sequence=sequence, img_info=list(size), img_size=list(size), detections=values.tolist())
        input_chain = hashlib.sha256((input_chain+canonical(public_input)).encode()).hexdigest()
        # 原core会就地除scale，所以输入array必须由本次新建，不能复用原缓存数组。
        natural = np.asarray(tracker.update(values, size, size))
        require(tracker.frame_count == index+1 and natural.ndim == 2 and natural.shape[1] == 5,
                '官方update调用/自然返回结构改变，不加自造回退')
        raw_outputs.append(natural.tolist())
        counts.append(len(natural)); seen = set()
        for row in natural:
            require(all(math.isfinite(float(v)) for v in row), '官方自然输出非有限；报错而非删行')
            x1, y1, x2, y2, native_id = map(float, row)
            require(native_id.is_integer() and native_id > 0 and native_id not in seen and x2 > x1 and y2 > y1,
                    '自然ID/框非法；不能重编号或静默过滤')
            seen.add(native_id)
            text.append(','.join(map(str, [index+1, int(native_id), x1, y1, x2-x1, y2-y1, 1, -1, -1, -1])))
    require(counts and _static_sha(official.KalmanBoxTracker) == static_before, '空序列或官方共享Kalman矩阵被改变')
    return dict(schema='official_ocsort_cached_tracking_payload_v1', mot_text='\n'.join(text)+('\n' if text else ''),
        sequence=sequence, frames=len(counts), tracked_rows=len(text), frame_counts=counts,
        raw_outputs=raw_outputs,
        parameters=deepcopy(parameters), official_source=deepcopy(official.metadata), input_reference=deepcopy(input_reference),
        audit=dict(update_calls=len(counts), empty_input_frames=sum(n == 0 for n in raw_counts),
            raw_detection_counts=raw_counts, raw_detections=sum(raw_counts), all_raw_detections_passed_to_core=True,
            outside_core_filtering=False, input_dtype='float32', input_columns='xyxy+score_N5_no_class_multiplication',
            input_chain_sha256=input_chain, scale=1., img_info_equals_img_size=True,
            native_output_score_available=False, MOT_score_constant=1, MOT_score_is_detection_confidence=False,
            original_IDs_preserved=True, posthoc_ID_renumbering=False, ID_before=0,
            ID_counter_after=int(official.KalmanBoxTracker.count), static_kalman_matrices_unchanged=True,
            static_kalman_matrices_sha256=static_before, model_GT_or_Pose_input=False,
            GT_read=False, Pose_fields_read=False, new_optimizer_updates=0, GPU_used=False, test_read=False))


def track_frames(frames, official, parameters, *, input_reference=None):
    """官方全局ID要求一进程一活动tracker，不能在同进程用线程并行两个job。"""
    require(_TRACKING_LOCK.acquire(blocking=False), '该进程已有OCSort tracker活动，不可破坏全局ID')
    try:
        return _track_frames_impl(frames, official, parameters, input_reference)
    finally:
        _TRACKING_LOCK.release()
