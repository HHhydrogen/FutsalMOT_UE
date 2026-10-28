"""原强motion的冻结截距追踪适配；独立track/metric进程，原候选与生命周期不变。"""
import ast
from collections import OrderedDict
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import importlib.util
import inspect
import io
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import sys
import time
import traceback
import types

R = Path('D:/projects/FutsalMOT_Research')
EXP = R/'pose/trainR_intercept_calibration_a01'
FIELDS = ('uid', 'bbox_xywh_px', 'score', 'xy_px', 'geometry_valid', 'timestamp_sec', 'image_wh')
FRAME_FIELDS = ('sequence', 'game', 'fps', 'frame_index', 'frame_number', 'timestamp_sec', 'width', 'height')
METRICS = ('AssA', 'HOTA', 'IDF1', 'DetA', 'MOTA')
FIXED_ARGS = dict(track_high_thresh=.25, track_low_thresh=.1, new_track_thresh=.25,
    track_buffer=30, match_thresh=.8, fuse_score=True)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
_TRACK_WORKER = None
_METRIC_WORKER = None
_PROCESS_KIND = None


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def safe(value, root=None):
    path = Path(os.path.abspath(value))
    require(not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
        for part in path.parts), '最终测试继续封存')
    if root is not None:
        require(safe(root) in path.parents, '只准新实验根内独立输出')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            require(not part.is_symlink() and not getattr(part.lstat(), 'st_file_attributes', 0) & 0x400,
                '不跟随junction或链接')
    return path


def sha(path):
    digest = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def ref(path): return dict(path=str(safe(path)), sha256=sha(path))


def checked(reference):
    path = safe(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '冻结来源变化：'+str(path))
    return path


def read_ref(reference): return json.loads(checked(reference).read_text(encoding='utf-8-sig'))


def module(reference, prefix):
    path = checked(reference)
    name = prefix+'_'+reference['sha256']
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        value = importlib.util.module_from_spec(spec)
        sys.modules[name] = value
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(value)
        finally:
            sys.dont_write_bytecode = previous
    require(safe(sys.modules[name].__file__) == safe(path), '源码模块缓存被另一物理来源占用')
    return sys.modules[name]


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def public_frame(frame):
    """保留原feature所需预测Pose字段；use_pose=False仍走原194维计算再遮蔽。"""
    result = {key: deepcopy(frame[key]) for key in FRAME_FIELDS}
    result['detections'] = []
    for detection in frame['detections']:
        value = {key: deepcopy(detection[key]) for key in FIELDS}
        if 'detection_id' in detection:
            value['detection_id'] = deepcopy(detection['detection_id'])
        result['detections'].append(value)
    return result


def protected_paths(cfg):
    values = [reference['path'] for source in cfg['sources'].values() for key, reference in source.items()
        if key in ('gt', 'gt_reference', 'gameinfo', 'seqinfo')]
    values += [binding['registry']['path'] for binding in cfg['registries'].values()]
    return sorted(set(values))


def expected_cells(models, cfg):
    result = set()
    common = cfg['panels']['old_external']+cfg['panels']['seven_observed']
    for spec in models:
        heldout = next(sequence for sequence, fold in OLD.items() if fold == spec['fold'])
        for sequence in [heldout]+common:
            result.add((spec['model_id'], spec['regime'], spec['fold'], spec['seed'], sequence))
    return result


def validate_jobs(cfg, inventory):
    jobs = cfg['jobs']
    cells = [(job['model_id'], job['regime'], job['fold'], job['seed'], job['sequence']) for job in jobs]
    require(len(jobs) == len({job['job_id'] for job in jobs}) == len(set(cells)) == 180
        and set(cells) == expected_cells(inventory['models'], cfg), '必须完整18模型各10源180任务，不筛比赛或seed')


class Bindings:
    """仅来源JSON与纯源码；不调用旧validate_config/dependencies读取endpointGT。"""
    def __init__(self, cfg):
        self.cfg = cfg
        self.references = {}
        require(cfg['test_sealed'] is True and cfg['new_optimizer_updates'] == 0
            and (cfg.get('tracking_authorized') is True or cfg.get('numeric_authorized') is True), '缺独立root零SGD准入')
        require(cfg['approved_by'] == 'root' and safe(cfg['output_root']) == EXP, '仅新截距实验根')
        self.protocol = deepcopy(cfg['_protocol_ref'])
        self.remember(self.protocol)
        manifest = self.read(cfg['bundle_manifest'])
        own = [item for item in manifest['files'] if item['path'] == 'tools/research_ops/trainR_intercept_tracking.py']
        require(len(own) == 1 and safe(__file__) == safe(cfg['bundle'])/'tools/research_ops/trainR_intercept_tracking.py',
            '追踪适配自身必须来自新冻结bundle')
        self.remember(dict(path=str(safe(__file__)), sha256=own[0]['sha256']))
        self.inventory = self.read(cfg['inventory'])
        require(self.inventory['schema'] == 'trainR_intercept_source_inventory_v1'
            and len(self.inventory['models']) == 18 and self.inventory['sources'] == cfg['sources']
            and self.inventory['panels'] == cfg['panels'], '原18模型/12来源清单改变')
        validate_jobs(cfg, self.inventory)
        done = self.read(cfg['fit_complete'])
        require(done['schema'] == 'trainR_intercept_fit_complete_v1'
            and done['status'] == 'complete18_trainR_only_scalar_calibrations_full_records_and_exit_verified'
            and done['fit_processes_absent'] is True and done['calibrations'] == cfg['calibrations']
            and done['totals']['models'] == 18 and done['totals']['optimizer_updates'] == 0, '原18截距拟合尚未闭合')
        self.velocity = self.read(cfg['source_velocity_protocol'])
        require(self.velocity['sources'] == cfg['sources'] and self.velocity['panels'] == cfg['panels']
            and self.velocity['registries'] == cfg['registries'], '不能替换原12源/结果前事件')
        self.old = self.read(self.velocity['source_tracking_config'])
        self.seven_cfg = self.read(self.velocity['source_seven_tracking_config'])
        self.training = self.read(self.old['training_protocol'])
        self.v9 = self.read(self.training['v9_protocol'])
        self.old_rt_ref = self.source(self.old, 'tools/research_ops/v10_tracking_runtime.py')
        self.old_rt = module(self.old_rt_ref, 'intercept_original_scope_runtime')
        self.tracker_ref = self.source(self.v9, 'python/src/grf_ue_bridge/learned_association_tracker_v8.py')
        for relative in ('learned_association_features_v8.py', 'learned_association_model_v8.py', 'pose_association_contract_v2.py'):
            self.source(self.v9, 'python/src/grf_ue_bridge/'+relative)
        self.seven_ref = self.source(self.seven_cfg, 'tools/research_ops/substitution_tracking_runtime.py')
        self.inputs = module(self.remember(cfg['inputs_source']), 'intercept_frozen_inputs')
        self.runtime = module(self.remember(cfg['runtime_source']), 'intercept_frozen_runtime')
        require(cfg.get('tracker_parameters', FIXED_ARGS) == FIXED_ARGS, '候选/门槛/score融合与生命周期参数不能改变')

    def remember(self, reference):
        checked(reference)
        self.references[reference['path']] = deepcopy(reference)
        return reference

    def read(self, reference):
        return read_ref(self.remember(reference))

    def source(self, config, relative):
        manifest = self.read(config['bundle_manifest'])
        found = [entry for entry in manifest['files'] if entry['path'] == relative]
        require(len(found) == 1 and safe(config['bundle']).parent == R/'code', '仅原内容寻址源码')
        return self.remember(dict(path=str(safe(config['bundle'])/relative), sha256=found[0]['sha256']))

    def spec(self, job):
        require(job in self.cfg['jobs'], '未冻结的追踪任务')
        found = [spec for spec in self.inventory['models'] if spec['model_id'] == job['model_id']]
        require(len(found) == 1 and all(found[0][key] == job[key] for key in ('regime', 'fold', 'seed')), '原模型身份不符')
        return found[0]

    def closure(self):
        for reference in self.references.values():
            checked(reference)
        return dict(source_closure_verified=True, checked_references=len(self.references),
            old_runtime_validate_or_dependencies_called=False)


def model_state_sha(model):
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(canonical([name, str(value.dtype), list(value.shape)]).encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def metric_functions(binding):
    """原四个纯函数AST原样编译；避免导入旧CLI时移动ROOT或加载训练依赖。"""
    reference = binding.source(binding.old, 'tools/research_ops/v10_metric.py')
    path = checked(reference)
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names = ('plain', 'prediction_rows', 'validate_count', 'trackeval_numeric')
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    require(len(functions) == len(names), '原评价四纯函数缺失')
    value = types.ModuleType('intercept_original_metric_pure_functions')
    value.__dict__.update(rt=binding.old_rt, redirect_stdout=redirect_stdout, io=io, inspect=inspect,
        math=math, Path=Path, defaultdict=__import__('collections').defaultdict)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), value.__dict__)
    return value, dict(source=reference, numerical_functions=list(names),
        numerical_function_AST_sha256=hashlib.sha256(ast.dump(ast.Module(body=functions, type_ignores=[]), include_attributes=False).encode()).hexdigest(),
        numerical_function_AST_unchanged=True)


class TrackWorker:
    def __init__(self, cfg):
        global _PROCESS_KIND
        require(_PROCESS_KIND in (None, 'track') and os.environ.get('CUDA_VISIBLE_DEVICES') == '-1', 'track与metric必须独立CPU进程')
        _PROCESS_KIND = 'track'
        self.cfg, self.jobs, self.closed = cfg, 0, False
        self.support = module(cfg['track_guard_source'], 'intercept_frozen_GT_guard')
        self.guard = self.support.GTReadGuard(protected_paths(cfg))
        self.guard.install()
        self.binding = Bindings(cfg)
        self.binding.remember(cfg['track_guard_source'])
        self.frames_cache = self.support.BoundedLRU(128*1024*1024, max_items=2)
        self.model_cache = self.support.BoundedLRU(256*1024*1024, max_items=3)
        self.input_hashes = {}
        self.model_hashes = {}
        import torch
        self.torch = torch
        self.torch.set_num_threads(1)
        require(not self.torch.cuda.is_initialized(), 'CPU追踪不能初始化CUDA')
        with self.binding.inputs.frozen_import_scope(safe(self.binding.v9['bundle'])):
            self.cls, self.scope = self.binding.old_rt.scoped_tracker(self.binding.v9['bundle'], cfg['sources'])
        from ultralytics.trackers.basetrack import BaseTrack
        from ultralytics.trackers.byte_tracker import STrack
        self.BaseTrack, self.STrack = BaseTrack, STrack
        for key in ('old_five', 'seven'):
            binding = cfg['registries'][key]
            public = self.binding.read(binding['receipt'])
            require(public['registry'] == binding['registry'] and public['contains_GT_coordinates'] is False,
                'track只读无坐标事件收据，不能读endpointGT账本')

    def frames(self, sequence):
        source = self.cfg['sources'][sequence]
        key = source['cache']['sha256']
        def load():
            path = checked(self.binding.remember(source['cache']))
            values = []
            with path.open(encoding='utf-8-sig') as stream:
                for line in stream:
                    if line.strip():
                        values.append(public_frame(json.loads(line)))
            require(len(values) == source['frames'], '完整缓存含空检测帧，不得删帧')
            for frame in values:
                self.binding.old_rt.validate_frame(frame, self.cfg['sources'])
            require([frame['frame_number'] for frame in values] == list(range(1, source['frames']+1)), '帧号必须一基完整有序')
            self.input_hashes[key] = hashlib.sha256(canonical(values).encode()).hexdigest()
            return values, self.support.deep_bytes(values)
        return self.frames_cache.get(key, load)

    def model(self, job):
        spec = self.binding.spec(job)
        fit_ref = self.cfg['calibrations'][spec['model_id']]
        key = canonical([spec['checkpoint'], spec['normalizer'], fit_ref, self.cfg['inputs_source'], self.cfg['runtime_source']])
        def load():
            fit = self.binding.read(fit_ref)
            require(fit['status'] == 'complete_finite_trainR_intercept_fit_not_tracking_effect'
                and fit['parameters'] == self.binding.runtime.PARAMETERS
                and fit['model_spec'] == spec and all(fit[k] == spec[k] for k in ('model_id', 'regime', 'fold', 'seed')),
                '只准已闭合同模型trainR截距，不从验证选择β')
            beta = fit['apply_beta32']
            require(self.binding.runtime.float32(beta) == beta, '应用β必须原已签FP32逐值')
            loaded = self.binding.inputs.load_model(spec, device='cpu')
            model, normalizer = loaded['model'], loaded['normalizer']
            require(loaded['binding'] == spec['binding'], '实际原模型加载身份不同')
            state = model_state_sha(model)
            normalized = canonical(normalizer.state())
            shifted = self.binding.runtime.wrap_intercept(model, beta, self.torch)
            zero = self.binding.runtime.wrap_intercept(model, 0., self.torch)
            self.model_hashes[key] = (state, normalized)
            for name in ('checkpoint', 'normalizer', 'training_receipt'):
                self.binding.remember(spec[name])
            if spec.get('training_complete') is not None:
                self.binding.remember(spec['training_complete'])
            size = sum(value.numel()*value.element_size() for value in model.state_dict().values())+len(normalized.encode())+4
            return dict(base=model, shifted=shifted, zero=zero, normalizer=normalizer, binding=loaded['binding'],
                loading_receipt=loaded['receipt'], beta32=beta, fit=fit_ref, cache_key=key), size
        return self.model_cache.get(key, load)

    def payload(self, job, *, diagnostic_beta0=False, prefix_frames=None, original_base_forward=False):
        require(not self.closed, '已关闭worker不可继续')
        diagnostic = diagnostic_beta0 or prefix_frames is not None or original_base_forward
        require(not diagnostic or self.cfg.get('numeric_authorized') is True, '诊断β0/prefix须独立数值授权')
        self.binding.spec(job)
        frames = self.frames(job['sequence'])
        if prefix_frames is not None:
            require(type(prefix_frames) is int and 0 < prefix_frames <= len(frames), '诊断前缀范围非法')
            frames = frames[:prefix_frames]
        loaded = self.model(job)
        model = loaded['base'] if original_base_forward else (loaded['zero'] if diagnostic_beta0 else loaded['shifted'])
        before_inputs = hashlib.sha256(canonical(frames).encode()).hexdigest()
        before_model = model_state_sha(loaded['base'])
        before_normalizer = canonical(loaded['normalizer'].state())
        before_rng = self.torch.get_rng_state().clone()
        self.BaseTrack.reset_id()
        self.STrack.reset_id()
        require(self.BaseTrack._count == 0, '每job原全局ID必须归零')
        tracker = self.cls(mode='learned', model=model, normalizer=loaded['normalizer'], use_pose=False,
            pose_source_sha256=self.binding.training['pose_checkpoint_sha256'],
            fixed_detection_sha256=self.cfg['sources'][job['sequence']]['cache']['sha256'])
        require(tracker.previous == -1 and tracker.sequence is None and tracker.frame_id == 0
            and all(not getattr(tracker, key) for key in ('tracked_stracks', 'lost_stracks', 'removed_stracks')),
            '每job必须清空全部轨迹/历史状态')
        counts, lines, raw_frames = [], [], []
        with self.torch.no_grad():
            for frame in frames:
                rows = tracker.update_frame(frame)
                raw_frames.append(rows.tolist() if hasattr(rows, 'tolist') else [list(row) for row in rows])
                counts.append(len(rows))
                for row in rows:
                    x1, y1, x2, y2, identity, score = row[:6]
                    lines.append(','.join(map(str, [frame['frame_number'], int(identity), float(x1), float(y1),
                        float(x2-x1), float(y2-y1), float(score), -1, -1, -1])))
        require(before_inputs == hashlib.sha256(canonical(frames).encode()).hexdigest()
            and before_model == model_state_sha(loaded['base'])
            and before_normalizer == canonical(loaded['normalizer'].state())
            and self.torch.equal(before_rng, self.torch.get_rng_state()), '原输入/权重/normalizer或RNG被任务改变')
        require(before_model == self.model_hashes[loaded['cache_key']][0]
            and before_normalizer == self.model_hashes[loaded['cache_key']][1], '常驻模型/normalizer发生污染')
        require(not self.guard.blocked, 'track曾尝试读取评价GT，不可签成功')
        self.jobs += 1
        mot_text = '\n'.join(lines)+('\n' if lines else '')
        return dict(mot_text=mot_text, mot=mot_text, raw_frames=raw_frames, frames=len(frames), tracked_rows=len(lines),
            frame_counts=counts, audit=deepcopy(tracker.audit), scope_adapter=self.scope,
            binding=deepcopy(loaded['binding']), model_loading_receipt=loaded['loading_receipt'],
            fit=loaded['fit'], beta32=0. if diagnostic_beta0 or original_base_forward else loaded['beta32'], calibrated_beta32=loaded['beta32'],
            diagnostic_beta0=diagnostic_beta0, prefix_frames=prefix_frames,
            original_base_forward_without_intercept_wrapper=original_base_forward,
            global_ID_before=0, global_ID_after=int(self.BaseTrack._count), all_job_state_reset=True,
            source_inputs_unchanged=True, original_model_state_unchanged=True, original_normalizer_unchanged=True,
            Torch_CPU_RNG_unchanged=True, actual_dtype='float32', original_input_dim=194,
            input_Pose_columns_zeroed_after_original_normalization=True,
            native_ordered_batch_forward_preserved=True, original_probability_cutoff=.5,
            alias_used=False, GT_guard=self.guard.proof(), evaluation_GT_coordinate_files_opened=False,
            calibration_trainR_metadata_parsed=True, GT_used_for_tracking=False,
            GPU_used=False, new_optimizer_updates=0, test_read=False)

    def original_beta0_payload(self, job, *, prefix_frames=48):
        """独立原模型forward路径用于准入；不设β、不重用另一策略的logits。"""
        return self.payload(job, diagnostic_beta0=True, prefix_frames=prefix_frames, original_base_forward=True)

    def run(self, job, output):
        output = safe(output, self.cfg['output_root'])
        require(not output.exists(), '已有追踪partial/成品不覆盖')
        started = time.perf_counter()
        payload = self.payload(job)
        output.mkdir(parents=True)
        (output/'data').mkdir()
        mot = output/'data'/(job['sequence']+'.txt')
        with mot.open('x', encoding='utf-8') as stream:
            stream.write(payload.pop('mot_text'))
        payload.pop('mot')
        native = payload.pop('raw_frames')
        payload['native_output_frames_sha256'] = hashlib.sha256(canonical(native).encode()).hexdigest()
        receipt = dict(schema='trainR_intercept_tracking_receipt_v1', status='complete', job=job,
            model_id=job['model_id'], protocol_sha256=self.binding.protocol['sha256'],
            source_cache=self.cfg['sources'][job['sequence']]['cache'], mot=ref(mot), mot_sha256=sha(mot),
            worker_pid=os.getpid(), tracking_wall_seconds=time.perf_counter()-started, **payload)
        write_new(output/'receipt.json', receipt)
        return dict(job=job, tracking=str(output), receipt=ref(output/'receipt.json'))

    def close(self):
        require(not self.closed and not self.guard.blocked, 'worker已关闭或尝试读取评价GT')
        for key, (frames, _) in self.frames_cache.items.items():
            require(hashlib.sha256(canonical(frames).encode()).hexdigest() == self.input_hashes[key], '常驻输入被修改')
        for _, (value, _) in self.model_cache.items.items():
            expected = self.model_hashes[value['cache_key']]
            require(model_state_sha(value['base']) == expected[0] and canonical(value['normalizer'].state()) == expected[1],
                '常驻模型关闭时发生污染')
        evidence = dict(status='closed', worker_pid=os.getpid(), jobs=self.jobs,
            model_cache=self.model_cache.stats(), frame_cache=self.frames_cache.stats(),
            counted_model_bytes='tensor_and_serialized_normalizer_bytes_not_process_RSS',
            GT_guard=self.guard.proof(), GT_guard_scope='evaluation_GT_coordinates_gameinfo_and_full_endpoint_registry',
            calibration_trainR_metadata_parsed=True, evaluation_GT_coordinate_files_opened=False,
            **self.binding.closure())
        self.model_cache.clear()
        self.frames_cache.clear()
        evidence['cache_entries_after_close'] = dict(models=len(self.model_cache.items), frames=len(self.frames_cache.items))
        evidence['GT_audit_hook_lifetime'] = 'dedicated_process_lifetime_until_actual_exit_not_uninstalled'
        self.closed = True
        return evidence


class MetricWorker:
    def __init__(self, cfg):
        global _PROCESS_KIND
        require(_PROCESS_KIND in (None, 'metric'), 'metric不能与track同进程读取GT')
        _PROCESS_KIND = 'metric'
        self.cfg, self.jobs, self.closed = cfg, 0, False
        self.binding = Bindings(cfg)
        self.metric, self.numeric_evidence = metric_functions(self.binding)
        self.seven = module(self.binding.seven_ref, 'intercept_original_seven_GT_loader')
        self.gap = module(self.binding.source(self.binding.v9, 'tools/research_ops/v8_gap_recovery.py'), 'intercept_original_gap')
        self.GT, self.registries = {}, {}

    def run(self, job, output):
        self.binding.spec(job)
        require(not self.closed, '已关闭metric worker不可继续')
        source = self.cfg['sources'][job['sequence']]
        tracking = safe(self.cfg['control_root'])/'runs'/job['job_id']/'tracking'
        receipt_ref = ref(tracking/'receipt.json')
        receipt = read_ref(receipt_ref)
        require(receipt['schema'] == 'trainR_intercept_tracking_receipt_v1' and receipt['status'] == 'complete'
            and receipt['job'] == job and receipt['protocol_sha256'] == self.binding.protocol['sha256']
            and receipt['source_cache'] == source['cache'] and receipt['frames'] == source['frames']
            and receipt['fit'] == self.cfg['calibrations'][job['model_id']]
            and receipt['GT_used_for_tracking'] is False and receipt['evaluation_GT_coordinate_files_opened'] is False
            and receipt['test_read'] is False and receipt['alias_used'] is False, '新追踪/全帧/GT隔离来源不同')
        mot = checked(receipt['mot'])
        predictions, count = self.metric.prediction_rows(mot.read_text(encoding='utf-8'), source['frames'])
        require(count == receipt['tracked_rows'] == sum(receipt['frame_counts']), '预测不得按GT筛选')
        sequence = job['sequence']
        if sequence not in self.GT:
            loader = self.seven.load_gt if sequence in self.cfg['panels']['seven_observed'] else self.binding.old_rt.load_gt
            self.GT[sequence] = loader(source)
            for key in ('gt', 'gt_reference', 'gameinfo', 'seqinfo'):
                if key in source:
                    self.binding.remember(source[key])
        gt, text = self.GT[sequence]
        require(len(text) == self.cfg['expected_GT_rows'][sequence], '原GT人数/roster/ID0口径改变')
        output = safe(output, self.cfg['output_root'])
        require(not output.exists(), '评价partial/成功目录不覆盖')
        output.mkdir(parents=True)
        raw, numerical_sha = self.metric.trackeval_numeric(source, text, tracking, output)
        summary = {}
        for name, classes in raw.items():
            value = classes['pedestrian']
            self.metric.validate_count(name, value['Count'], count, len(text), sequence, source['frames'])
            fraction = {}
            for group, keys in (('HOTA', ('HOTA', 'AssA', 'DetA')), ('Identity', ('IDF1',)), ('CLEAR', ('MOTA',))):
                for key in keys:
                    number = value[group][key]
                    fraction[key] = sum(number)/len(number) if isinstance(number, list) else float(number)
            summary[name] = dict(metrics_fraction=fraction, metrics_percent={key: 100*value for key, value in fraction.items()},
                IDSW_count=int(value['CLEAR']['IDSW']))
        registry_binding = self.cfg['registries']['seven' if sequence in self.cfg['panels']['seven_observed'] else 'old_five']
        key = registry_binding['registry']['sha256']
        if key not in self.registries:
            self.registries[key] = self.binding.read(registry_binding['registry'])
        registry = self.registries[key]
        require(registry['sources'] == {seq: self.cfg['sources'][seq] for seq in registry['sources']}
            and registry['sequences'][sequence]['cache'] == source['cache'], '全原事件/同预测缓存来源改变')
        events = [event for event in registry['events'] if event['sequence'] == sequence]
        gap = self.gap.evaluate_events(events, registry['sequences'][sequence]['endpoint_GT'], predictions)
        require(gap['overall']['total_events'] == len(events), '必须全登记事件分母')
        report = dict(schema='trainR_intercept_tracking_metric_v1', status='complete', job=job,
            protocol_sha256=self.binding.protocol['sha256'], tracking_receipt=receipt_ref,
            source_cache=source['cache'], fit=receipt['fit'], beta32=receipt['beta32'],
            metrics=summary[sequence]['metrics_percent'], gap=gap, summary=summary, raw_results=raw,
            registry=registry_binding['registry'], frames=source['frames'], GT_rows=len(text), tracked_rows=count,
            DO_PREPROC=False, predictions_GT_filtered=False, GT_ID0_original=True,
            GT_used_only_for_metric=True, numerical_source_sha256=numerical_sha,
            metric_pure_functions=self.numeric_evidence, worker_pid=os.getpid(),
            new_optimizer_updates=0, test_read=False)
        require(set(report['metrics']) == set(METRICS) and all(math.isfinite(value) for value in report['metrics'].values()),
            '五指标必须完整有限并保持原百分点尺度')
        write_new(output/'report.json', report)
        self.jobs += 1
        return dict(job=job, report=ref(output/'report.json'))

    def close(self):
        require(not self.closed, 'metric worker重复关闭')
        self.closed = True
        return dict(status='closed', worker_pid=os.getpid(), jobs=self.jobs, GT_sequences_loaded=list(self.GT),
            GT_isolated_to_metric_worker=True, registry_count=len(self.registries), **self.binding.closure())


def track_job(cfg, job, output):
    global _TRACK_WORKER
    if _TRACK_WORKER is None:
        _TRACK_WORKER = TrackWorker(cfg)
    require(_TRACK_WORKER.binding.protocol == cfg['_protocol_ref'], '常驻worker不能混用协议')
    return _TRACK_WORKER.run(job, output)


def metric_job(cfg, job, output):
    global _METRIC_WORKER
    if _METRIC_WORKER is None:
        _METRIC_WORKER = MetricWorker(cfg)
    require(_METRIC_WORKER.binding.protocol == cfg['_protocol_ref'], '常驻metric不能混用协议')
    return _METRIC_WORKER.run(job, output)


def close_track_worker():
    require(_TRACK_WORKER is not None, 'track worker未创建')
    return _TRACK_WORKER.close()


def close_metric_worker():
    require(_METRIC_WORKER is not None, 'metric worker未创建')
    return _METRIC_WORKER.close()


def compare_payloads(actual, reference):
    """完整原ID/MOT/自然输出/count/audit逐值，不重编号、不按性能容差放宽。"""
    for key in ('mot_text', 'raw_frames', 'frame_counts', 'audit', 'frames', 'tracked_rows'):
        require(canonical(actual[key]) == canonical(reference[key]), '数值准入完整输出不同：'+key)
    for value in (actual, reference):
        require(value['all_job_state_reset'] is True and value['global_ID_before'] == 0
            and value['source_inputs_unchanged'] is True and value['original_model_state_unchanged'] is True
            and value['original_normalizer_unchanged'] is True and value['Torch_CPU_RNG_unchanged'] is True
            and value['GT_used_for_tracking'] is False and value['evaluation_GT_coordinate_files_opened'] is False
            and value['GT_guard']['blocked_open_attempts'] == 0 and value['new_optimizer_updates'] == 0
            and value['test_read'] is False and value['alias_used'] is False, '实际状态/GT/零SGD边界未验证')
    return dict(original_ID_MOT_exact=True, raw_native_frames_exact=True, frame_counts_exact=True, audit_exact=True,
        frames=actual['frames'], tracked_rows=actual['tracked_rows'],
        MOT_sha256=hashlib.sha256(actual['mot_text'].encode()).hexdigest(),
        raw_frames_sha256=hashlib.sha256(canonical(actual['raw_frames']).encode()).hexdigest())


def _numeric_worker_entry(connection, cfg, log_path):
    """仅小规模准入的spawn入口；正式池继续由已验根Service管理。"""
    worker = None
    try:
        with safe(log_path).open('x', encoding='utf-8') as log, redirect_stdout(log), redirect_stderr(log):
            worker = TrackWorker(cfg)
            connection.send(dict(status='ready', worker_pid=os.getpid()))
            while True:
                task = connection.recv()
                if task['op'] == 'close':
                    connection.send(dict(status='closed', worker_pid=os.getpid(), closure=worker.close()))
                    return
                require(task['op'] == 'payload', '未知数值准入worker请求')
                job = next(job for job in cfg['jobs'] if job['job_id'] == task['job_id'])
                result = worker.payload(job, prefix_frames=48)
                connection.send(dict(status='complete', worker_pid=os.getpid(), payload=result))
    except BaseException:
        try:
            connection.send(dict(status='failed', worker_pid=os.getpid(), traceback=traceback.format_exc()))
        except (BrokenPipeError, EOFError, OSError):
            pass
        raise
    finally:
        connection.close()


def _spawn_target():
    """使spawn能从真实冻结文件按常规模块名重建入口，避免动态模块pickle失败。"""
    path = Path(__file__).resolve()
    directory = str(path.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    name = 'trainR_intercept_tracking'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        value = importlib.util.module_from_spec(spec)
        sys.modules[name] = value
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(value)
        finally:
            sys.dont_write_bytecode = previous
    require(safe(sys.modules[name].__file__) == safe(path), 'spawn模块名被另一来源占用')
    return sys.modules[name]._numeric_worker_entry


def _receive_numeric(connection, status, timeout=300.):
    require(connection.poll(timeout), '数值准入worker超时，保留partial不隐式重试')
    value = connection.recv()
    require(value.get('status') == status, '数值准入worker异常：'+canonical(value))
    return value


def _close_numeric(entry):
    entry['connection'].send(dict(op='close'))
    answer = _receive_numeric(entry['connection'], 'closed')
    process = entry['process']
    process.join(30.)
    require(not process.is_alive() and process.exitcode == 0
        and answer['worker_pid'] == answer['closure']['worker_pid'] == entry['ready']['worker_pid'] == process.pid
        and answer['closure']['status'] == 'closed', '实际worker PID/close/join未正常闭合')
    entry['connection'].close()
    entry['closed'] = True
    return dict(**answer, joined=True, exitcode=process.exitcode, actual_PID_absent_after_join=True)


def numeric_admission(cfg, config_path, output):
    """真实执行由根单独授权；96源帧/2模型，11次48前缀，绝不评价TrackEval。"""
    require(cfg.get('phase') == 'numeric_admission' and cfg.get('numeric_authorized') is True
        and cfg.get('tracking_authorized') is False and cfg['_protocol_ref'] == ref(config_path), '仅独立数值准入协议')
    output = safe(output, cfg['output_root'])
    require(not output.exists(), '已有数值准入partial/成品不覆盖或重播')
    output.mkdir(parents=True)
    (output/'diagnostics').mkdir()
    write_new(output/'started.json', dict(status='started_not_committed', config=cfg['_protocol_ref'],
        pid=os.getpid(), unique_source_frames=96, optimizer_updates=0, test_read=False))
    workers, resources = [], []
    parent = None
    try:
        support = module(cfg['worker_support'], 'intercept_numeric_resource_support')
        profile = cfg['worker_profile']
        require(profile['reserve_RAM_bytes'] >= 8*1024**3 and profile['reserve_commit_bytes'] >= 6*1024**3,
            '不能降低已验RAM/commit预留')
        def gate(new_workers=0):
            snapshot = support.resource_snapshot()
            resources.append(snapshot)
            require(support.enough_memory(snapshot, profile, new_workers), '数值准入资源预留不足，停止并保留partial')
        def save_payload(name, payload):
            path = output/'diagnostics'/(name+'.json')
            write_new(path, payload)
            return ref(path)
        chosen = {}
        for key, regime, sequence in (('A', 'R', 'SNMOT-060'), ('B', 'RS', 'v_2QhNRucNC7E_c017')):
            found = [job for job in cfg['jobs'] if job['regime'] == regime and job['fold'] == 'game4'
                and job['seed'] == 20261024 and job['sequence'] == sequence]
            require(len(found) == 1, '固定R/RS首seed两模型/两源准入缺失')
            chosen[key] = found[0]
        gate(3)
        parent = TrackWorker(cfg)
        original, zero, cold, zero_comparison, payload_refs = {}, {}, {}, {}, {}
        for key in ('A', 'B'):
            gate()
            original[key] = parent.original_beta0_payload(chosen[key], prefix_frames=48)
            zero[key] = parent.payload(chosen[key], diagnostic_beta0=True, prefix_frames=48)
            zero_comparison[key] = compare_payloads(zero[key], original[key])
            cold[key] = parent.payload(chosen[key], prefix_frames=48)
            payload_refs['original_beta0_'+key] = save_payload('original_beta0_'+key, original[key])
            payload_refs['wrapper_beta0_'+key] = save_payload('wrapper_beta0_'+key, zero[key])
            payload_refs['calibrated_cold_'+key] = save_payload('calibrated_cold_'+key, cold[key])
        aba = []
        for index, key in enumerate(('A', 'B', 'A')):
            gate()
            value = parent.payload(chosen[key], prefix_frames=48)
            aba.append(dict(key=key, comparison=compare_payloads(value, cold[key]),
                payload=save_payload('persistent_'+str(index)+'_'+key, value)))
        parent_close = parent.close()
        gate(2)
        context = mp.get_context('spawn')
        target = _spawn_target()
        for index in range(2):
            receiver, child = context.Pipe(duplex=True)
            process = context.Process(target=target, args=(child, cfg, str(output/('spawn_'+str(index)+'.log'))))
            entry = dict(process=process, connection=receiver, ready=None, closed=False)
            workers.append(entry)
            process.start()
            child.close()
            entry['ready'] = _receive_numeric(receiver, 'ready')
            require(entry['ready']['worker_pid'] == process.pid, '实际spawn ready PID不同')
        for entry in workers:
            entry['connection'].send(dict(op='payload', job_id=chosen['A']['job_id']))
        spawned = []
        for index, entry in enumerate(workers):
            answer = _receive_numeric(entry['connection'], 'complete')
            require(answer['worker_pid'] == entry['process'].pid, '实际任务PID不同')
            comparison = compare_payloads(answer['payload'], cold['A'])
            saved = save_payload('spawn_'+str(index)+'_A', answer['payload'])
            spawned.append(dict(comparison=comparison, payload=saved, closure=_close_numeric(entry)))
        require(len({entry['ready']['worker_pid'] for entry in workers}) == 2, '两spawn必须实际独立PID')
        gate()
        report = dict(schema='trainR_intercept_tracking_numeric_admission_v1',
            status='complete_trainR_intercept_cold_ABA_spawn_beta0_original_exact_numeric_admission', passed=True,
            config=cfg['_protocol_ref'], fit_complete=cfg['fit_complete'], cases=chosen,
            beta0_original_comparisons=zero_comparison, cold_payloads=payload_refs, persistent_ABA=aba,
            parent_closure=parent_close, independent_spawn_A=spawned, all_workers_joined_exited=True,
            unique_source_frames=96, diagnostic_frame_consumptions=11*48, original_beta0_prefix_runs=2,
            wrapper_beta0_prefix_runs=2, calibrated_cold_prefix_runs=2, persistent_prefix_runs=3,
            independent_spawn_prefix_runs=2, numeric_threads=1, resources=resources,
            alias_used=False, nearzero_alias_threshold=None, evaluation_GT_coordinate_files_opened=False,
            calibration_trainR_metadata_parsed=True, original_weights_and_normalizer_unchanged=True,
            new_optimizer_updates=0, new_TrackEval_runs=0, new_detector_or_Pose_inference=False, test_read=False,
            limitations=['只有两模型/两48帧前缀的输入与常驻数值准入，不是180自由追踪完成或效果结论。',
                '所有正式策略各自维护独立历史并执行原native batch，不共享另一策略的自由追踪logits。',
                '解析原拟合JSON会加载trainR派生标签metadata；评价GT坐标/endpoint账本从未进入track进程。',
                'Python open审计仅保护明确GT路径，不是操作系统沙箱。'])
        write_new(output/'receipt.json', report)
        return report
    except BaseException:
        for entry in workers:
            process = entry['process']
            if process.pid is not None and process.is_alive():
                try:
                    entry['connection'].send(dict(op='close'))
                except (EOFError, BrokenPipeError, OSError):
                    pass
                process.join(30.)
        write_new(output/'failure.json', dict(status='failed_partial_preserved_no_retry', traceback=traceback.format_exc(),
            workers=[dict(pid=entry['process'].pid, alive=entry['process'].is_alive(), exitcode=entry['process'].exitcode)
                for entry in workers if entry['process'].pid is not None], new_optimizer_updates=0, test_read=False))
        raise
