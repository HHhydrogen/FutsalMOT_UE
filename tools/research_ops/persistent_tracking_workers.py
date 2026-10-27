"""独立CPU常驻track候选；不创建metric池，不读取GT，不重试任务。"""
import argparse
from collections import OrderedDict
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import traceback

FIELDS = ('uid', 'bbox_xywh_px', 'score', 'xy_px', 'geometry_valid', 'timestamp_sec', 'image_wh')
RESEARCH = Path('D:/projects/FutsalMOT_Research')
ORIGIN = 'performance_admission_not_new_research_result'
_WORKER = None


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def normalized(path):
    text = os.fspath(path)
    if text.startswith('\\\\?\\'):
        text = text[4:]
    return os.path.normcase(os.path.abspath(text))


def physical(path, root=None):
    path = Path(os.path.abspath(path))
    require(not any(p.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', p.lower())
                    for p in path.parts), '最终测试继续封存')
    if root is not None:
        require(Path(root) in path.parents, '输出必须是新准入根的独立子目录')
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            value = p.lstat()
            require(not stat.S_ISLNK(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400,
                    '不跟随junction/重解析点')
    return path


def checked(reference):
    path = physical(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '来源SHA改变：' + str(path))
    return path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def worker_code_closure(protocol):
    """新执行层本身也必须在最小bundle闭包中，不能只绑定旧数值源码。"""
    bundle = physical(protocol['bundle']); own = physical(__file__)
    require(bundle.parent == RESEARCH/'code' and bundle in own.parents, '新worker只能从实际冻结bundle执行')
    manifest_ref = protocol['bundle_manifest']; manifest = read(checked(manifest_ref))
    own_ref = None; references = [manifest_ref]
    for entry in manifest['files']:
        path = physical(bundle/entry['path'], bundle)
        reference = dict(path=str(path), sha256=entry['sha256']); checked(reference); references.append(reference)
        if normalized(path) == normalized(own): own_ref = reference
    require(own_ref is not None, '常驻worker自身__file__未被源码闭包绑定')
    return dict(worker_module=own_ref, bundle_manifest=manifest_ref), references


def deep_bytes(value, seen=None):
    """计量保留的Python对象图，不冒称进程RSS或库瞬态内存上限。"""
    seen = set() if seen is None else seen
    if id(value) in seen: return 0
    seen.add(id(value)); size = sys.getsizeof(value)
    if isinstance(value, dict): size += sum(deep_bytes(k, seen) + deep_bytes(v, seen) for k, v in value.items())
    elif isinstance(value, (list, tuple, set)): size += sum(deep_bytes(v, seen) for v in value)
    return size


class GTReadGuard:
    """专用track进程的Python open审计；禁止为SHA而打开GT/endpoint坐标。"""
    def __init__(self, paths):
        self.paths = {normalized(p) for p in paths}
        self.blocked = []; self.installed = False

    def audit(self, event, args):
        if event != 'open' or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = normalized(os.fsdecode(args[0]))
        if path in self.paths:
            self.blocked.append(path)
            raise PermissionError('track进程禁止打开GT/gameinfo/endpoint账本：' + path)

    def install(self):
        require(not self.installed, '审计hook不可重复安装')
        sys.addaudithook(self.audit); self.installed = True

    def proof(self):
        return dict(python_open_audit_installed=self.installed, protected_paths=len(self.paths),
                    blocked_open_attempts=len(self.blocked), GT_annotations_opened=False)


class BoundedLRU:
    def __init__(self, limit, max_items=None):
        require(type(limit) is int and limit > 0 and (max_items is None or type(max_items) is int and max_items > 0), '明确缓存上限')
        self.limit, self.max_items = limit, max_items
        self.items = OrderedDict(); self.bytes = self.peak = self.hits = self.misses = 0

    def get(self, key, loader):
        if key in self.items:
            value, size = self.items.pop(key); self.items[key] = (value, size); self.hits += 1
            return value
        self.misses += 1; value, size = loader()
        require(type(size) is int and 0 <= size <= self.limit, '单entry超过冻结缓存上限，不隐式扩容/重试')
        while self.items and (self.bytes + size > self.limit or self.max_items is not None and len(self.items) >= self.max_items):
            _, (_, previous) = self.items.popitem(last=False); self.bytes -= previous
        self.items[key] = value, size; self.bytes += size; self.peak = max(self.peak, self.bytes)
        return value

    def stats(self):
        return dict(limit_bytes=self.limit, max_items=self.max_items, retained_count=len(self.items),
                    counted_retained_bytes=self.bytes, peak_counted_bytes=self.peak, hits=self.hits, misses=self.misses)

    def clear(self): self.items.clear(); self.bytes = 0


class TrackingCore:
    """纯worker逻辑；backend夹具不等真实模型/进程准入。每进程仅顺序执行。"""
    def __init__(self, backend, *, frame_cache_bytes=268435456, model_cache_bytes=67108864, max_models=2):
        self.backend = backend; self.frames = BoundedLRU(frame_cache_bytes)
        self.models = BoundedLRU(model_cache_bytes, max_models)
        self.pid = os.getpid(); self.busy = self.failed = self.closed = False; self.completed = 0

    def execute(self, job):
        require(os.getpid() == self.pid and not self.busy and not self.failed and not self.closed,
                'worker不可跨fork/并发复用、关闭后重开或失败后隐式重试')
        self.busy = True
        try:
            key = digest(self.backend.frame_identity(job))
            def load_frames():
                data = self.backend.load_frames(job)
                return dict(data=data, immutable_sha256=digest(data)), deep_bytes(data)
            frames = self.frames.get(key, load_frames)
            model_key = digest(self.backend.model_identity(job))
            def load_model():
                model, adapter, binding = self.backend.load_model(job)
                self.backend.prepare_model(model)
                entry = dict(model=model, adapter=adapter, binding=binding,
                             model_sha256=self.backend.model_sha(model), adapter_sha256=digest(adapter.state()))
                return entry, self.backend.model_bytes(model)
            saved = self.models.get(model_key, load_model)
            require(self.backend.model_sha(saved['model']) == saved['model_sha256']
                    and digest(saved['adapter'].state()) == saved['adapter_sha256'], '缓存模型/adapter在前一任务被改变')
            self.backend.prepare_model(saved['model'])
            tracker, scope, input_audit, pose_off, id_start = self.backend.new_tracker(job, saved['model'], saved['adapter'])
            require(id_start == 0, '原始全局ID没有归零，禁止事后重编号')
            text, counts = [], []
            with self.backend.no_grad():
                for source_frame in frames['data']:
                    # 不把缓存本体或历史对象交给可变tracker；每job仍是自然原Pose。
                    frame = deepcopy(source_frame)
                    tracks = tracker.update_frame(frame); counts.append(len(tracks))
                    for row in tracks:
                        x1, y1, x2, y2, identity, score = row[:6]
                        text.append(','.join(map(str, [frame['frame_number'], int(identity), float(x1), float(y1),
                            float(x2-x1), float(y2-y1), float(score), -1, -1, -1])))
            require(digest(frames['data']) == frames['immutable_sha256'], '共享原始frame缓存被任务写回')
            require(self.backend.model_sha(saved['model']) == saved['model_sha256']
                    and digest(saved['adapter'].state()) == saved['adapter_sha256'], 'eval推理修改模型参数/buffer/adapter')
            require(input_audit['feature_calls'] == input_audit['adapter_transform_pair_calls'], '实际输入计数不一致')
            self.completed += 1
            return dict(mot='\n'.join(text)+('\n' if text else ''), frame_counts=counts, tracked_rows=len(text),
                audit=deepcopy(tracker.audit), scope_adapter=deepcopy(scope), input_adapter_audit=deepcopy(input_audit),
                pose_off=pose_off, binding=deepcopy(saved['binding']), model_cache_key=model_key, input_cache_key=key,
                cached_model_unchanged=True, cached_adapter_unchanged=True, cached_frames_unchanged=True,
                global_track_ID_before=id_start, global_track_ID_after=self.backend.id_count(),
                model_eval=True, no_grad=True)
        except BaseException:
            self.failed = True
            raise
        finally:
            self.busy = False

    def close(self):
        require(not self.busy and not self.closed, '不能在活动任务中关闭或重复关闭')
        errors = []
        try:
            for saved, _ in self.frames.items.values():
                require(digest(saved['data']) == saved['immutable_sha256'], '退出时输入缓存已变化')
            for saved, _ in self.models.items.values():
                require(self.backend.model_sha(saved['model']) == saved['model_sha256']
                        and digest(saved['adapter'].state()) == saved['adapter_sha256'], '退出时模型/adapter已变化')
        except BaseException as error:
            errors.append(repr(error))
        try:
            evidence = self.backend.verify_closure()
        except BaseException as error:
            errors.append(repr(error)); evidence = dict(status='failed_closure_verification', error=repr(error))
        self.failed = self.failed or bool(errors)
        proof = dict(status='closed_failed_no_retry' if self.failed else 'closed_worker_caches_verified',
            completed=self.completed, frames=self.frames.stats(), models=self.models.stats(), closure=evidence,
            pid=self.pid, process_exit_not_yet_asserted=True, optimizer_updates=0, verification_errors=errors)
        self.frames.clear(); self.models.clear(); self.closed = True
        return proof


class FrozenBackend:
    def __init__(self, source_ref):
        self.source_ref = deepcopy(source_ref); source = read(checked(source_ref))
        self.bundle = physical(source['bundle'])
        require(self.bundle.parent == RESEARCH/'code', '仅实际原冻结bundle')
        forbidden = [r['registry']['path'] for r in source['registries'].values()]
        for item in source['sources'].values():
            forbidden.extend(item[key]['path'] for key in ('gt', 'gt_reference', 'gameinfo') if key in item)
        self.guard = GTReadGuard(forbidden); self.guard.install()
        # 必须在完整源准入之前安装，连为了SHA全读GT也会被拒绝。
        self.rt = load_module('pose_velocity_tracking_runtime', self.bundle/'tools/research_ops/pose_velocity_tracking_runtime.py')
        self.cfg, self.dep, self.learning = self.rt.validate_config(checked(source_ref))
        self.jobs = load_module('persistent_source_tracking_jobs', self.bundle/'tools/research_ops/pose_velocity_tracking_jobs.py')
        self.adapter_module = load_module('persistent_source_tracking_adapter', self.bundle/'tools/research_ops/pose_velocity_tracking_adapter.py')
        self.original_input = self.adapter_module.velocity_input
        import torch
        torch.set_num_threads(1); torch.set_num_interop_threads(1)
        self.torch = torch
        from ultralytics.trackers.basetrack import BaseTrack
        from ultralytics.trackers.byte_tracker import STrack
        self.BaseTrack, self.STrack = BaseTrack, STrack
        self.context = dict(protocol=source_ref, code_manifest=self.cfg['bundle_manifest'],
                            source5=self.cfg['source_tracking_config'], source7=self.cfg['source_seven_tracking_config'])
        self.seen_refs = {}; self.model_sources = {}
        self.training_state = self.rt.read(self.rt.checked(self.cfg['learning_controller_state']))
        self.learning_cfg = self.rt.read(self.rt.checked(self.cfg['learning_protocol']))

    def frame_identity(self, job):
        return dict(context=self.context, cache=self.cfg['sources'][job['sequence']]['cache'])

    def load_frames(self, job):
        source = self.cfg['sources'][job['sequence']]; reference = source['cache']
        path = self.rt.checked(reference); self.seen_refs[normalized(path)] = reference
        values = self.rt.rows(path)
        require(len(values) == source['frames'] and [f['frame_number'] for f in values]
                == list(range(1, source['frames']+1)), '完整原预测帧顺序改变')
        for frame in values: self.dep[1].validate_frame(frame, self.cfg['sources'])
        return values

    def model_identity(self, job):
        # 开关与sequence不影响权重/normalizer身份，不能把它们当不同模型。
        key = (job['kind'], job['group'], job['fold'], job['seed'])
        if key not in self.model_sources:
            if job['kind'] == 'new':
                item = next(x for x in self.training_state['completed_train'] if all(x[k] == job[k] for k in ('group', 'fold', 'seed')))
                run = Path(item['path']); protocol = self.cfg['learning_protocol']
                adapter_source = self.learning_cfg['adapters'][job['fold']]
            else:
                run = Path(self.dep[0]['training_control'])/'runs'/job['fold']/str(job['seed'])/'balanced/motion_residual/training'
                protocol = self.dep[0]['training_protocol']; adapter_source = self.dep[4]['folds'][job['fold']]
            last_path = physical(run/'last_checkpoint.json'); last = read(last_path)
            last_ref = dict(path=str(last_path), sha256=sha(last_path))
            self.seen_refs[normalized(last_path)] = last_ref
            self.seen_refs[normalized(last['path'])] = dict(path=last['path'], sha256=last['sha256'])
            self.model_sources[key] = dict(context=self.context, protocol=protocol,
                checkpoint=dict(path=last['path'], sha256=last['sha256']), checkpoint_index=last_ref,
                adapter_source=adapter_source, method=dict(kind=job['kind'], group=job['group'], fold=job['fold'], seed=job['seed']))
        return self.model_sources[key]

    def load_model(self, job):
        model, adapter, binding, _ = self.rt.load_model(self.cfg, self.dep, self.learning, job)
        return model, adapter, binding

    def prepare_model(self, model):
        model.eval()
        require(not model.training and all(value.device.type == 'cpu' for value in model.state_dict().values()), '仅CPU eval模型')

    def model_sha(self, model):
        value = hashlib.sha256()
        for key, tensor in sorted(model.state_dict().items()):
            value.update(canonical([key, str(tensor.dtype), list(tensor.shape)]).encode())
            value.update(tensor.detach().cpu().numpy().tobytes())
        return value.hexdigest()

    def model_bytes(self, model): return sum(x.numel()*x.element_size() for x in model.state_dict().values())
    def no_grad(self): return self.torch.no_grad()
    def id_count(self): return int(self.BaseTrack._count)

    def new_tracker(self, job, model, adapter):
        self.BaseTrack.reset_id(); self.STrack.reset_id()
        require(self.id_count() == 0, 'BaseTrack/STrack全局ID重置失败')
        audit, pose_off = self.jobs.input_metadata(job['kind'])
        if job['kind'] == 'new':
            self.adapter_module.velocity_input = self.jobs.instrument_input(self.original_input, audit)
            cls, scope = self.adapter_module.scoped_velocity_tracker(self.dep[7]['bundle'], self.cfg['sources'], self.dep[1])
            normalizer = self.jobs.InputAuditProxy(adapter, audit)
        else:
            cls, scope = self.dep[1].scoped_tracker(self.dep[7]['bundle'], self.cfg['sources']); normalizer = adapter
        source = self.cfg['sources'][job['sequence']]
        tracker = cls(mode='learned', model=model, normalizer=normalizer, use_pose=job['pose_enabled'],
            pose_source_sha256=self.dep[4]['pose_checkpoint_sha256'], fixed_detection_sha256=source['cache']['sha256'])
        require(tracker.previous == -1 and tracker.sequence is None and tracker.frame_id == 0
                and all(not getattr(tracker, key) for key in ('tracked_stracks', 'lost_stracks', 'removed_stracks')),
                '新任务轨迹/历史没有完整重置')
        return tracker, scope, audit, pose_off, self.id_count()

    def verify_closure(self):
        require(not self.guard.blocked, 'track进程曾尝试打开GT，不能签未读GT')
        for reference in self.seen_refs.values(): checked(reference)
        self.rt.validate_config(checked(self.source_ref))
        return dict(source_protocol=self.source_ref, seen_input_model_files_rechecked=len(self.seen_refs),
                    source_closure_revalidated=True, GT_open_guard=self.guard.proof())


class PersistentTrackWorker:
    def __init__(self, source_config_ref, output_root, *, worker_protocol_ref,
                 frame_cache_bytes=268435456, model_cache_bytes=67108864, max_models=2):
        require(os.environ.get('CUDA_VISIBLE_DEVICES') == '-1', '在导入前明确禁用GPU')
        self.protocol_ref = deepcopy(worker_protocol_ref); protocol = read(checked(worker_protocol_ref))
        require(protocol['schema'] == 'association_persistent_worker_admission_v1' and protocol['approved_by'] == 'root'
                and protocol['diagnostic_only'] is True and protocol['optimizer_updates'] == 0 and protocol['test_sealed'] is True
                and protocol['source_tracking_config'] == source_config_ref, '缺独立零更新常驻worker准入')
        self.output_root = physical(output_root)
        require(RESEARCH in self.output_root.parents and self.output_root == physical(protocol['output_root'])
                and 'performance' in self.output_root.parts, '输出只准新DResearch performance根')
        code, references = worker_code_closure(protocol)
        self.source_ref = deepcopy(source_config_ref); self.backend = FrozenBackend(source_config_ref)
        self.backend.context['worker_execution'] = dict(protocol=worker_protocol_ref, **code)
        for reference in references:
            self.backend.seen_refs[normalized(reference['path'])] = reference
        self.core = TrackingCore(self.backend, frame_cache_bytes=frame_cache_bytes,
                                 model_cache_bytes=model_cache_bytes, max_models=max_models)

    def run(self, job_id, output, worker_protocol_ref=None):
        require(worker_protocol_ref is None or worker_protocol_ref == self.protocol_ref, '任务worker准入引用不同')
        checked(self.protocol_ref)
        job = next((j for j in self.backend.cfg['tracking_matrix'] if j['job_id'] == job_id), None)
        require(job is not None, '只允许已冻结原矩阵任务')
        output = physical(output, self.output_root); require(not output.exists(), '已有输出/partial，拒绝覆盖或隐式重放')
        output.mkdir(parents=True); clock = time.perf_counter()
        try:
            actual = self.core.execute(job); (output/'data').mkdir()
            mot = output/'data'/(job['sequence']+'.txt')
            with mot.open('x', encoding='utf-8') as f: f.write(actual.pop('mot'))
            source = self.backend.cfg['sources'][job['sequence']]
            receipt = dict(schema='bounded_velocity513_free_tracking_v1', status='complete',
                protocol_sha256=self.source_ref['sha256'], job=job, frames=source['frames'], mot_sha256=sha(mot),
                cache=source['cache'], source_cache=source['cache'], pose_enabled=job['pose_enabled'],
                inference_shape_shuffle=False, original_quality_gate=True, evaluation_GT_annotations_loaded=False,
                GT_used_for_tracking=False, GPU_used=False, test_read=False, origin=ORIGIN,
                worker_protocol=self.protocol_ref, worker_pid=os.getpid(), worker_job_wall_seconds=time.perf_counter()-clock,
                GT_open_guard=self.backend.guard.proof(), **actual)
            with (output/'receipt.json').open('x', encoding='utf-8') as f: f.write(canonical(receipt)+'\n')
            return dict(job=job, path=str(output/'receipt.json'), sha256=sha(output/'receipt.json'), status='complete', origin=ORIGIN)
        except BaseException as error:
            self.core.failed = True
            with (output/'failed.json').open('x', encoding='utf-8') as f:
                f.write(canonical(dict(status='failed_preserved_no_retry', job=job, error=repr(error),
                    traceback=traceback.format_exc(), worker_protocol=self.protocol_ref, origin=ORIGIN))+'\n')
            raise

    def close(self):
        error = None
        try: checked(self.protocol_ref)
        except BaseException as caught:
            self.core.failed = True; error = repr(caught)
        return dict(self.core.close(), worker_protocol=self.protocol_ref, origin=ORIGIN, worker_protocol_error=error)


def track_worker_init(spec):
    global _WORKER
    require(_WORKER is None, '一个专用track进程只初始化一个worker，不能兼作metric')
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      OPENBLAS_NUM_THREADS='1', YOLO_AUTOINSTALL='false')
    _WORKER = PersistentTrackWorker(spec['source_tracking_config'], spec['output_root'],
        worker_protocol_ref=spec['worker_protocol_ref'], **spec.get('cache_limits', {}))
    return dict(pid=os.getpid(), role='track_only', initialized=True)


def track_worker_run(task):
    require(_WORKER is not None, '先初始化专用track进程')
    return _WORKER.run(task['job_id'], task['output'], task.get('worker_protocol_ref'))


def track_worker_close():
    require(_WORKER is not None, 'worker未初始化')
    return _WORKER.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True); parser.add_argument('--task', type=Path, required=True)
    args = parser.parse_args(); track_worker_init(read(args.spec))
    try: result = track_worker_run(read(args.task))
    finally: close = track_worker_close()
    print(canonical(dict(result=result, close=close)))
