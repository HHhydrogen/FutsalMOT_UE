"""官方OC-SORT单因素det_thresh=.25；复用已闭合冻结适配的原纯函数。"""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import math
from pathlib import Path
import re
import sys

SOURCE_BUNDLE = Path('D:/projects/FutsalMOT_Research/code/2865b347c7bae8ae02eb1627b27e41c1dbcbd922c579d199f7e45c67d0337d74')
SOURCE_MANIFEST = dict(path=str(SOURCE_BUNDLE/'bundle_manifest.json'),
    sha256='36888adb88a8402378147030c69812dcfe038387a88ee56f901976e50a886c77')
SOURCE_RUNTIME = dict(path=str(SOURCE_BUNDLE/'tools/research_ops/ocsort_cached_runtime.py'),
    sha256='3f6d897c49c4cc5fb3333f3b95b5629238cae9de306993abe06a86caf77b026d')
SOURCE_ADMISSION = dict(path=str(SOURCE_BUNDLE/'tools/research_ops/ocsort_cached_admission.py'),
    sha256='ae4c20b393bea145ef385ae8962884366904756a82b4e6575d6cb0289d38e567')


def frozen_module(name, reference):
    """固定旧源码按实际路径导入；不复制runtime、不改旧module globals。"""
    path = Path(reference['path'])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
        raise ValueError('旧冻结纯函数源码改变：'+str(path))
    name = name+'_'+reference['sha256']
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous
    return sys.modules[name]


_original = frozen_module('ocsort_threshold_original_runtime', SOURCE_RUNTIME)
require, canonical, safe, sha, read, ref = (_original.require, _original.canonical, _original.safe,
    _original.sha, _original.read, _original.ref)
adapt_detections, _static_sha = _original.adapt_detections, _original._static_sha
_TRACKING_LOCK = _original._TRACKING_LOCK
PARAMETERS = dict(_original.parameters(), det_thresh=.25)
ORIGINAL_PARAMETERS = _original.parameters()
inspect_source_contract = _original.inspect_source_contract
dependency_modules = _original.dependency_modules
OfficialDependencyError = _original.OfficialDependencyError
COMMIT = _original.COMMIT


def parameters():
    return deepcopy(PARAMETERS)


def single_factor_contract():
    require(sha(SOURCE_RUNTIME['path']) == SOURCE_RUNTIME['sha256']
        and sha(SOURCE_MANIFEST['path']) == SOURCE_MANIFEST['sha256'], '旧冻结源码/manifest改变')
    manifest = read(SOURCE_MANIFEST['path'])
    require(all(any(entry['path'] == 'tools/research_ops/'+Path(binding['path']).name
        and entry['sha256'] == binding['sha256'] for entry in manifest['files'])
        for binding in (SOURCE_RUNTIME, SOURCE_ADMISSION)), '固定2865清单没有对应原纯函数')
    require(_original.PARAMETERS == ORIGINAL_PARAMETERS and ORIGINAL_PARAMETERS['det_thresh'] == .6,
            '旧runtime官方默认参数被修改')
    differences = {key: dict(before=ORIGINAL_PARAMETERS[key], after=PARAMETERS[key])
                   for key in PARAMETERS if PARAMETERS[key] != ORIGINAL_PARAMETERS[key]}
    require(set(PARAMETERS) == set(ORIGINAL_PARAMETERS) and differences == {'det_thresh': dict(before=.6, after=.25)},
            '只能修改det_thresh .6→.25这一因素')
    original_tree = ast.parse(Path(SOURCE_RUNTIME['path']).read_text(encoding='utf-8'))
    current_tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    def function(tree):
        candidates = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_track_frames_impl']
        require(len(candidates) == 1, '唯一原适配数值函数缺失')
        return ast.dump(candidates[0], include_attributes=False)
    original_ast, current_ast = function(original_tree), function(current_tree)
    require(original_ast == current_ast, '除独立namespace参数外，原适配函数AST不得改变')
    return dict(source_runtime=deepcopy(SOURCE_RUNTIME), source_admission=deepcopy(SOURCE_ADMISSION),
        source_manifest=deepcopy(SOURCE_MANIFEST), changed_parameters=differences,
        copied_function='_track_frames_impl', copied_function_AST_identical=True,
        copied_function_AST_sha256=hashlib.sha256(current_ast.encode()).hexdigest(),
        original_module_globals_modified=False, original_source_bytes_modified=False,
        old_official_default_det_thresh=.6, effective_det_thresh=.25,
        official_default_claim=False, upstream_association_or_Kalman_modified=False)


def load_official(manifest_ref):
    contract = single_factor_contract()
    official = _original.load_official(manifest_ref)
    official.metadata = dict(deepcopy(official.metadata), effective_parameters=parameters(),
        parameter_override='predeclared_single_factor_det_thresh_0.6_to_0.25_not_official_default',
        single_factor_override=dict(parameter='det_thresh', before=.6, after=.25,
            predeclared=True, official_default=False),
        single_factor_contract=contract)
    return official


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
    """共用官方全局ID锁；只有独立参数namespace改变，不热改旧函数。"""
    single_factor_contract()
    require(_TRACKING_LOCK.acquire(blocking=False), '该进程已有OCSort tracker活动，不可破坏全局ID')
    try:
        result = _track_frames_impl(frames, official, parameters, input_reference)
        result['single_factor_contract'] = single_factor_contract()
        return result
    finally:
        _TRACKING_LOCK.release()
