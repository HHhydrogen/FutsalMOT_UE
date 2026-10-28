"""训练域自由状态诊断：只旁观原追踪，快照重放与局部oracle分支另列。

本模块不加载GT、模型、协议或缓存。调用方负责冻结来源、GT读保护及独立进程。
旁观器使用原三次分配返回值；不重算模型，不修改输入/代价/分配或生命周期。
"""
from collections import deque
from contextlib import AbstractContextManager
from copy import deepcopy
import hashlib
import json
import math
import types

SCHEMA = 'train_free_state_rollout_v1'
STAGES = ('high_score', 'low_score', 'unconfirmed')
TRACK_LISTS = ('tracked_stracks', 'lost_stracks', 'removed_stracks')
RECORD_FIELDS = ('uid', 'bbox_xywh_px', 'score', 'xy_px', 'geometry_valid',
                 'timestamp_sec', 'image_wh', '_frame_index')


def require(value, message):
    if not value:
        raise ValueError(message)


def plain(value):
    """只用于日志的JSON转换，不把该转换结果回送原追踪器。"""
    if hasattr(value, 'tolist'):
        return plain(value.tolist())
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, deque)):
        return [plain(item) for item in value]
    if hasattr(value, 'item'):
        return plain(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite': repr(value)}
    return value


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def public_record(record):
    if record is None:
        return None
    return {key: deepcopy(record[key]) for key in RECORD_FIELDS if key in record}


def track_state(track):
    history = [public_record(value) for value in getattr(track, 'history', ())]
    return dict(track_id=int(track.track_id), state=int(track.state),
        is_activated=bool(track.is_activated), frame_id=int(track.frame_id),
        start_frame=int(track.start_frame), tracklet_len=int(getattr(track, 'tracklet_len', 0)),
        record=public_record(getattr(track, 'record', None)), history=history,
        history_UIDs=[value['uid'] for value in history],
        history_timestamps=[value['timestamp_sec'] for value in history],
        mean=plain(getattr(track, 'mean', None)), covariance=plain(getattr(track, 'covariance', None)),
        score=float(track.score), idx=plain(getattr(track, 'idx', None)))


def frame_state(tracker):
    """列表归属也保留，不能用track_id去重而掩盖原有跨列表引用。"""
    return {name: [track_state(track) for track in getattr(tracker, name)] for name in TRACK_LISTS}


class Observer(AbstractContextManager):
    """每进程一次只旁观一个tracker，退出恢复所有被包装的原函数。"""
    def __init__(self, tracker, *, byte_class=None, matching=None, feature_module=None):
        if byte_class is None:
            from ultralytics.trackers.byte_tracker import BYTETracker
            byte_class = BYTETracker
        if matching is None:
            from ultralytics.trackers.utils import matching as matching_module
            matching = matching_module
        self.tracker, self.byte_class, self.matching = tracker, byte_class, matching
        self.feature_module = feature_module
        self.patches, self.patched_tracks = [], set()
        self.frame = None
        self.events, self.lifecycle = [], []
        self.pending, self.last_bbox_base = None, None
        self.assignment_index = 0
        self.measurement_priors, self.measurements_by_uid = {}, {}
        self.inside_frame = False

    def patch(self, target, name, value):
        own = name in vars(target)
        previous = getattr(target, name)
        self.patches.append((target, name, own, previous))
        setattr(target, name, value)

    def _patch_track(self, cls):
        if cls in self.patched_tracks:
            return
        self.patched_tracks.add(cls)
        for name in ('activate', 'update', 're_activate', 'mark_lost', 'mark_removed'):
            original = getattr(cls, name)
            observer = self
            def wrapped(track, *args, __name=name, __original=original, **kwargs):
                before = track_state(track)
                prior = None
                if __name in ('update', 're_activate'):
                    prior = dict(mean=deepcopy(track.mean), covariance=deepcopy(track.covariance))
                    observer.measurement_priors[int(track.track_id)] = prior
                result = __original(track, *args, **kwargs)
                after = track_state(track)
                observer.lifecycle.append(dict(operation=__name, frame_number=observer.frame['frame_number'],
                    track_id=int(track.track_id), before=before, after=after,
                    predicted_motion_before_measurement=plain(prior)))
                return result
            self.patch(cls, name, wrapped)

    def _stage(self, tracks, detections, base, cost, stage):
        import numpy as np
        rows = [track_state(track) for track in tracks]
        candidates = [public_record(getattr(det, 'record', None)) for det in detections]
        item = dict(frame_number=self.frame['frame_number'], frame_index=self.frame['frame_index'],
            stage=stage, stage_index=STAGES.index(stage), track_ids=[row['track_id'] for row in rows],
            rows=rows, candidates=candidates,
            candidate_UIDs=[value['uid'] if value is not None else None for value in candidates],
            bbox_base_cost=plain(base), reference_cost=plain(cost),
            cost_shape=list(np.asarray(cost).shape), native_ordered_batch_forward_preserved=True,
            learned_intervention_applied=stage != 'low_score')
        if stage != 'low_score' and self.feature_module is not None:
            gates = np.zeros(np.asarray(cost).shape, dtype=bool)
            lost, enough = [], []
            for i, track in enumerate(tracks):
                history = list(track.history)
                lost.append(bool(track.state != 1 or self.tracker.frame_id-track.frame_id > 1))
                enough.append(len(history) == 3)
                for j, detection in enumerate(detections):
                    if history:
                        gates[i, j] = self.feature_module.candidate_gate(history, detection.record)['accepted']
            enabled, active, counts = self.feature_module.intervention_mask(
                np.asarray(base), gates, lost, enough, 0 if stage == 'high_score' else 1)
            item.update(gates=gates.tolist(), enabled=plain(enabled), active=list(active),
                lost_gap=lost, enough_history=enough, intervention_counts=counts,
                gate_recomputed_for_logging_only=True)
        else:
            item.update(gates=None, enabled=None, active=[False]*len(rows), lost_gap=None,
                enough_history=[len(row['history']) == 3 for row in rows],
                gate_recomputed_for_logging_only=False)
        return item

    def __enter__(self):
        observer, cls = self, type(self.tracker)
        native_get = cls.get_dists
        byte_get = self.byte_class.get_dists
        native_init = cls.init_track
        native_iou = self.matching.iou_distance
        native_assign = self.matching.linear_assignment

        def get_bbox(tracker, tracks, detections):
            result = byte_get(tracker, tracks, detections)
            if tracker is observer.tracker and observer.inside_frame:
                observer.last_bbox_base = deepcopy(result)
            return result

        def get_dists(tracker, tracks, detections):
            result = native_get(tracker, tracks, detections)
            if tracker is observer.tracker and observer.inside_frame:
                expected = 'high_score' if observer.assignment_index == 0 else 'unconfirmed'
                require(observer.assignment_index in (0, 2), '原get_dists阶段调用顺序改变')
                observer.pending = observer._stage(tracks, detections, observer.last_bbox_base, result, expected)
            return result

        def init_track(tracker, *args, **kwargs):
            result = native_init(tracker, *args, **kwargs)
            if tracker is observer.tracker:
                for track in result:
                    observer._patch_track(type(track))
                    if getattr(track, 'record', None) is not None:
                        # 保存原Boxes(xyxy→xywh→tlwh)路径的测量，避免raw框直接转float32的舍入差。
                        observer.measurements_by_uid[track.record['uid']] = deepcopy(track.convert_coords(track._tlwh))
            return result

        def iou(tracks, detections, *args, **kwargs):
            result = native_iou(tracks, detections, *args, **kwargs)
            if observer.inside_frame and observer.assignment_index == 1:
                # 第二阶段在原BYTETracker.update内直接调用，下一次assignment才保存融合后的最终cost。
                observer.pending = observer._stage(tracks, detections, result, result, 'low_score')
            return result

        def assignment(cost, *args, **kwargs):
            result = native_assign(cost, *args, **kwargs)
            if observer.inside_frame:
                require(observer.assignment_index < 3 and observer.pending is not None, '原分配阶段缺少旁观上下文')
                item = observer.pending
                require(item['stage'] == STAGES[observer.assignment_index], '原三阶段顺序改变')
                matches, unmatched_tracks, unmatched_detections = result
                item.update(reference_cost=plain(cost), assignments=plain(matches),
                    unmatched_track_rows=plain(unmatched_tracks), unmatched_detection_columns=plain(unmatched_detections),
                    threshold=float(kwargs.get('thresh', args[0] if args else .5)))
                observer.events.append(item)
                observer.pending = None
                observer.assignment_index += 1
            return result

        self.patch(self.byte_class, 'get_dists', get_bbox)
        self.patch(cls, 'get_dists', get_dists)
        self.patch(cls, 'init_track', init_track)
        self.patch(self.matching, 'iou_distance', iou)
        self.patch(self.matching, 'linear_assignment', assignment)
        for name in TRACK_LISTS:
            for track in getattr(self.tracker, name):
                self._patch_track(type(track))
        return self

    def step(self, frame):
        require(not self.inside_frame, '同worker不能嵌套update')
        self.frame = frame
        self.events, self.lifecycle, self.measurement_priors, self.measurements_by_uid = [], [], {}, {}
        self.assignment_index, self.pending = 0, None
        before = frame_state(self.tracker)
        self.inside_frame = True
        try:
            result = self.tracker.update_frame(frame)
        finally:
            self.inside_frame = False
        require(self.assignment_index == 3 and self.pending is None, '每帧三阶段（含空矩阵）必须齐全')
        return result, dict(frame_number=frame['frame_number'], frame_index=frame['frame_index'],
            tracks_before=before, tracks_after=frame_state(self.tracker),
            stages=deepcopy(self.events), lifecycle=deepcopy(self.lifecycle))

    def __exit__(self, exc_type, exc, tb):
        for target, name, own, previous in reversed(self.patches):
            if own:
                setattr(target, name, previous)
            else:
                delattr(target, name)
        self.patches.clear()
        return False


def _id_class():
    from ultralytics.trackers.basetrack import BaseTrack
    return BaseTrack


def snapshot(tracker, *, id_class=None):
    """只在本进程保存；模型及标准化共享只读，所有轨迹与审计状态深拷贝。"""
    id_class = id_class or _id_class()
    memo = {id(getattr(tracker, key)): getattr(tracker, key) for key in ('model', 'normalizer')
            if getattr(tracker, key, None) is not None}
    return dict(schema='state_gap_inprocess_snapshot_v1', tracker=deepcopy(tracker, memo),
        global_ID=int(id_class._count))


def restore_snapshot(value, *, id_class=None):
    require(value['schema'] == 'state_gap_inprocess_snapshot_v1', '快照schema错误')
    id_class = id_class or _id_class()
    restored = snapshot(value['tracker'], id_class=id_class)['tracker']
    id_class._count = int(value['global_ID'])
    return restored


def _encode(value):
    """可移交独立replay进程的无GT快照；保持ndarray dtype/shape和deque长度。"""
    if type(value).__module__.split('.')[0] == 'numpy' and type(value).__name__ != 'ndarray' and hasattr(value, 'item'):
        return {'__npscalar__': True, 'dtype': str(value.dtype), 'data': plain(value.item())}
    if hasattr(value, 'dtype') and hasattr(value, 'shape') and hasattr(value, 'tolist'):
        return {'__ndarray__': True, 'dtype': str(value.dtype), 'shape': list(value.shape), 'data': plain(value)}
    if isinstance(value, deque):
        return {'__deque__': True, 'maxlen': value.maxlen, 'data': [_encode(item) for item in value]}
    if isinstance(value, tuple):
        return {'__tuple__': [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if hasattr(value, 'item'):
        return _encode(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {'__float__': repr(value)}
    require(value is None or isinstance(value, (str, bool, int, float)), '快照含未登记对象类型：'+str(type(value)))
    return value


def _decode(value):
    import numpy as np
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if '__ndarray__' in value:
        return np.asarray(value['data'], dtype=value['dtype']).reshape(value['shape'])
    if '__npscalar__' in value:
        return np.asarray(value['data'], dtype=value['dtype'])[()]
    if '__deque__' in value:
        return deque((_decode(item) for item in value['data']), maxlen=value['maxlen'])
    if '__tuple__' in value:
        return tuple(_decode(item) for item in value['__tuple__'])
    if '__float__' in value:
        return float(value['__float__'])
    return {key: _decode(item) for key, item in value.items()}


def export_snapshot(tracker, *, id_class=None):
    """完整动态state，保留同一轨迹对象跨tracked/lost/removed列表的别名关系。"""
    id_class = id_class or _id_class()
    objects, object_keys, lists = [], {}, {}
    for name in TRACK_LISTS:
        lists[name] = []
        for track in getattr(tracker, name):
            if id(track) not in object_keys:
                object_keys[id(track)] = len(objects)
                attrs = {key: _encode(value) for key, value in vars(track).items() if key != 'kalman_filter'}
                objects.append(dict(attrs=attrs, has_kalman_filter=track.kalman_filter is not None))
            lists[name].append(object_keys[id(track)])
    fields = {key: _encode(value) for key, value in vars(tracker).items()
              if key not in (*TRACK_LISTS, 'model', 'normalizer', 'kalman_filter', 'args')}
    return dict(schema='state_gap_portable_snapshot_v1', global_ID=int(id_class._count),
        objects=objects, lists=lists, tracker_fields=fields,
        model_and_normalizer='not_serialized_reuse_frozen_same_binding',
        kalman_filter='original_parameterless_XYAH_filter_from_new_tracker')


def import_snapshot(value, new_tracker, *, id_class=None, actual_track_class=None):
    require(value['schema'] == 'state_gap_portable_snapshot_v1', 'portable快照schema错误')
    id_class = id_class or _id_class()
    tracker = new_tracker()
    if actual_track_class is None:
        # 原init_track闭包有唯一ActualTrack；不造检测或激活以发现class。
        cells = type(tracker).init_track.__closure__ or ()
        candidates = [cell.cell_contents for cell in cells if isinstance(cell.cell_contents, type)
                      and cell.cell_contents.__name__ == 'ActualTrack']
        require(len(candidates) == 1, '不能唯一定位冻结ActualTrack闭包')
        actual_track_class = candidates[0]
    objects = []
    for spec in value['objects']:
        track = object.__new__(actual_track_class)
        track.__dict__.update({key: _decode(item) for key, item in spec['attrs'].items()})
        track.kalman_filter = tracker.kalman_filter if spec['has_kalman_filter'] else None
        objects.append(track)
    for name in TRACK_LISTS:
        setattr(tracker, name, [objects[index] for index in value['lists'][name]])
    for key, item in value['tracker_fields'].items():
        setattr(tracker, key, _decode(item))
    id_class._count = int(value['global_ID'])
    return tracker


def run_rollout(tracker, frames, *, observer_kwargs=None, id_class=None,
                snapshot_sink=None, snapshot_frames=None, frame_sink=None, retain_frames=True):
    """9000逻辑帧由上层固定；sink可逐帧gzip落盘以限制RAM。"""
    id_class = id_class or _id_class()
    logs, native, counts = [], [], []
    with Observer(tracker, **(observer_kwargs or {})) as observer:
        for frame in frames:
            if snapshot_sink is not None and (snapshot_frames is None or frame['frame_number'] in snapshot_frames):
                snapshot_sink(frame['frame_number'], export_snapshot(tracker, id_class=id_class))
            result, log = observer.step(frame)
            log['full_state_sha256'] = digest(export_snapshot(tracker, id_class=id_class))
            values = plain(result)
            counts.append(len(result))
            if frame_sink is not None:
                frame_sink(dict(log, native_output=values))
            if retain_frames:
                logs.append(log)
                native.append(values)
    return dict(schema=SCHEMA, frame_states=logs, native_frames=native, frame_counts=counts,
        frames=len(counts), audit=deepcopy(tracker.audit), global_ID_after=int(id_class._count),
        final_state_hash=digest(export_snapshot(tracker, id_class=id_class)),
        all_stages_logged_including_empty=True, GT_coordinates_loaded_by_module=False,
        new_optimizer_updates=0, actual_numerical_equivalence='requires_separate_real_admission')


def apply_oracle_repair(tracker, observer, plan, correct_record, *, branch, id_class=None):
    """错误measurement写入后局部替换；不是全局重分配或可部署策略。

    history只替末条wrongUID、长度不变；record/score/idx仍是原wrong检测。
    motion从原update/re_activate入口预测态对correct预测框执行原Kalman.update。
    """
    require(branch in ('original', 'history_only', 'motion_only', 'both'), '未知oracle分支')
    require(set(plan) <= {'event_id', 'frame_number', 'track_id', 'wrong_uid', 'correct_uid'}, 'replay计划不能携带GT身份/框')
    require(tracker.frame_id == plan['frame_number'] and observer.frame['frame_number'] == plan['frame_number'], '只能在错误帧结束修复')
    require(correct_record['uid'] == plan['correct_uid'] and correct_record['_frame_index'] == plan['frame_number']-1,
            'correct必须同帧真实预测UID')
    found = [track for track in tracker.tracked_stracks if track.track_id == plan['track_id']]
    require(len(found) == 1, '错误写入后目标必须唯一存在tracked列表')
    track = found[0]
    require(track.record['uid'] == plan['wrong_uid'] and track.history and track.history[-1]['uid'] == plan['wrong_uid'], '未复现目标wrong写入')
    before = export_snapshot(tracker, id_class=id_class)
    if branch in ('history_only', 'both'):
        length = len(track.history)
        track.history[-1] = public_record(correct_record)
        require(len(track.history) == length, '不补齐三条历史或改reactivate语义')
    if branch in ('motion_only', 'both'):
        prior = observer.measurement_priors.get(int(track.track_id))
        require(prior is not None, '目标缺少原measurement入口预测态')
        measurement = observer.measurements_by_uid.get(correct_record['uid'])
        require(measurement is not None, 'correct原预测未进入原init_track，缺严格原测量路径')
        track.mean, track.covariance = track.kalman_filter.update(
            deepcopy(prior['mean']), deepcopy(prior['covariance']), measurement)
    after = export_snapshot(tracker, id_class=id_class)
    # 逐字段允许表比简单checksum更严格；除两个目标字段不得有变化。
    expected = deepcopy(before)
    target_indices = before['lists']['tracked_stracks']
    index = next(index for index in target_indices if before['objects'][index]['attrs']['track_id'] == plan['track_id'])
    changed = []
    allowed = (['history'] if branch == 'history_only' else ['mean', 'covariance'] if branch == 'motion_only'
               else ['history', 'mean', 'covariance'] if branch == 'both' else [])
    for key in allowed:
        expected['objects'][index]['attrs'][key] = deepcopy(after['objects'][index]['attrs'][key])
        if before['objects'][index]['attrs'][key] != after['objects'][index]['attrs'][key]:
            changed.append(key)
    require(expected == after, 'oracle越权改变record/score/ID/lifecycle或非目标轨迹')
    return dict(branch=branch, allowed_fields=allowed, actual_changed_fields=changed,
        before_state_sha256=digest(before), after_state_sha256=digest(after),
        non_target_fields_unchanged=True, history_length=len(track.history),
        GT_coordinates_used=False, local_oracle_not_global_reassignment=True,
        correct_detection_may_also_belong_to_another_original_track=True)


def replay_branch(pre_error_snapshot, frames, plan, *, new_tracker=None,
                  observer_kwargs=None, branch='original', expected_error_log=None,
                  expected_native_frames=None, expected_state_hashes=None, id_class=None):
    """frames含错误帧及其后最多30帧；四分支各自重置静态ID并独立推进。"""
    id_class = id_class or _id_class()
    require(1 <= len(frames) <= 31 and frames[0]['frame_number'] == plan['frame_number'], '错误帧+后30帧有界')
    require([frame['frame_number'] for frame in frames] == list(range(plan['frame_number'], plan['frame_number']+len(frames))), '分支帧不连续')
    tracker = (import_snapshot(pre_error_snapshot, new_tracker, id_class=id_class)
               if pre_error_snapshot['schema'] == 'state_gap_portable_snapshot_v1'
               else restore_snapshot(pre_error_snapshot, id_class=id_class))
    native, logs, hashes, intervention = [], [], [], None
    with Observer(tracker, **(observer_kwargs or {})) as observer:
        for index, frame in enumerate(frames):
            rows, log = observer.step(frame)
            log['full_state_sha256'] = digest(export_snapshot(tracker, id_class=id_class))
            values = plain(rows)
            if index == 0:
                if expected_error_log is not None:
                    require(log == expected_error_log, '错误帧分配/历史/lifecycle未精确复现')
                correct = next((public_record(record) for record in frame['detections'] if record['uid'] == plan['correct_uid']), None)
                require(correct is not None, '同帧correct预测不在公开缓存')
                correct['_frame_index'] = frame['frame_index']
                intervention = apply_oracle_repair(tracker, observer, plan, correct, branch=branch, id_class=id_class)
            native.append(values)
            logs.append(log)
            hashes.append(digest(export_snapshot(tracker, id_class=id_class)))
    if branch == 'original':
        if expected_native_frames is not None:
            require(native == expected_native_frames, '原分支逐帧native/ID输出未精确复现')
        if expected_state_hashes is not None:
            require(hashes == expected_state_hashes, '原分支逐帧完整状态或全局ID未精确复现')
    return dict(schema='state_gap_oracle_replay_v1', branch=branch, plan=deepcopy(plan),
        frame_states=logs, native_frames=native, full_state_sha256=hashes,
        intervention=intervention, future_frames=len(frames)-1,
        global_ID_after=int(id_class._count), audit=deepcopy(tracker.audit),
        original_branch_exact_checked=branch == 'original' and expected_native_frames is not None and expected_state_hashes is not None,
        not_deployable_or_main_tracking_score=True, new_optimizer_updates=0)
