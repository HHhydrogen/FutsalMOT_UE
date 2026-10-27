"""513项CPU自由追踪/评价；自然Pose推理、原事件分母，无新优化更新。"""
import argparse
import math
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import pose_velocity_tracking_runtime as rt


def input_metadata(kind):
    """新T的关闭gate与旧同容量纯motion残差是不同路径，不能混写。"""
    rt.require(kind in ('new', 'reference'), '未知输入元数据种类')
    new = kind == 'new'
    audit = dict(adapter_transform_pair_calls=0, feature_calls=0, observed_feature_dims=[], all_finite=True,
        pose_off_final_gate_zero=True if new else None, actual_feature_checks_performed=False,
        input_kind='bounded_velocity_pair' if new else 'original_motion_residual_raw')
    return audit, ('same195_input_only_final_quality_gate_zero_own_motion_base' if new
                   else 'not_applicable_original_motion_residual_has_no_Pose_branch')


class InputAuditProxy:
    """只计数实际新adapter调用；返回原对象值，不改变归一化或数值。"""
    def __init__(self, adapter, audit):
        self.adapter, self.audit = adapter, audit

    def transform_pair(self, history, candidate):
        values = self.adapter.transform_pair(history, candidate)
        self.audit['adapter_transform_pair_calls'] += 1
        return values


def instrument_input(helper, audit):
    """在唯一新输入出口记录实际195维/有限值/关闭gate门禁。"""
    def checked_input(adapter, history, candidate, use_pose=True):
        values = helper(adapter, history, candidate, use_pose)
        audit['feature_calls'] += 1
        audit['observed_feature_dims'] = sorted(set(audit['observed_feature_dims']) | {len(values)})
        finite = len(values) == 195 and all(math.isfinite(x) for x in values)
        audit['all_finite'] = audit['all_finite'] and finite
        audit['pose_off_final_gate_zero'] = audit['pose_off_final_gate_zero'] and (use_pose or values[-1] == 0.)
        audit['actual_feature_checks_performed'] = True
        rt.require(finite and (use_pose or values[-1] == 0.), '实际新输入非有限/维度改变或关闭Pose未归零gate')
        return values
    return checked_input


def track(config, job_id, output):
    cfg, dep, learning = rt.validate_config(config)
    job = next((j for j in cfg['tracking_matrix'] if j['job_id'] == job_id), None)
    rt.require(job is not None, '任务ID未登记')
    source = cfg['sources'][job['sequence']]
    output = dep[3].storage().physical_child(output, rt.EXP)
    rt.require(not output.exists(), '追踪partial不覆盖/重放')
    output.mkdir(parents=True)
    import torch
    torch.set_num_threads(1)
    frames = rt.rows(rt.checked(source['cache']))
    rt.require(len(frames) == source['frames'] and [f['frame_number'] for f in frames]
               == list(range(1, source['frames'] + 1)), '完整共享预测帧/空检测帧顺序改变')
    model, adapter, binding, pose_enabled = rt.load_model(cfg, dep, learning, job)
    input_audit, pose_off_description = input_metadata(job['kind'])
    if job['kind'] == 'new':
        adapter_module = rt.module('bounded_velocity_frozen_tracking_adapter', rt.ROOT / 'tools/research_ops/pose_velocity_tracking_adapter.py')
        adapter_module.velocity_input = instrument_input(adapter_module.velocity_input, input_audit)
        cls, scope = adapter_module.scoped_velocity_tracker(dep[7]['bundle'], cfg['sources'], dep[1])
        adapter = InputAuditProxy(adapter, input_audit)
    else:
        cls, scope = dep[1].scoped_tracker(dep[7]['bundle'], cfg['sources'])
    tracker = cls(mode='learned', model=model, normalizer=adapter, use_pose=pose_enabled,
        pose_source_sha256=dep[4]['pose_checkpoint_sha256'], fixed_detection_sha256=source['cache']['sha256'])
    text, counts = [], []
    for frame in frames:
        tracks = tracker.update_frame(frame)
        counts.append(len(tracks))
        for row in tracks:
            x1, y1, x2, y2, identity, score = row[:6]
            text.append(','.join(map(str, [frame['frame_number'], int(identity), float(x1), float(y1),
                float(x2-x1), float(y2-y1), float(score), -1, -1, -1])))
    (output / 'data').mkdir()
    mot = output / 'data' / (job['sequence'] + '.txt')
    mot.write_text('\n'.join(text) + ('\n' if text else ''), encoding='utf-8')
    rt.require(input_audit['feature_calls'] == input_audit['adapter_transform_pair_calls'], '实际输入与adapter调用账本不一致')
    result = dict(schema='bounded_velocity513_free_tracking_v1', status='complete', protocol_sha256=rt.sha(config),
        job=job, frames=len(frames), tracked_rows=len(text), frame_counts=counts, mot_sha256=rt.sha(mot),
        cache=source['cache'], source_cache=source['cache'], binding=binding, audit=tracker.audit, scope_adapter=scope,
        input_adapter_audit=input_audit,
        pose_enabled=pose_enabled, inference_shape_shuffle=False, original_quality_gate=True,
        pose_off=pose_off_description,
        evaluation_GT_annotations_loaded=False, GT_used_for_tracking=False, GPU_used=False, test_read=False)
    with (output / 'receipt.json').open('x', encoding='utf-8') as stream:
        stream.write(rt.canonical(result) + '\n')
    return {key: result[key] for key in ('status', 'job', 'frames', 'tracked_rows')}


def evaluate(config, tracking, output, job_id=None):
    cfg, dep, learning = rt.validate_config(config)
    tracking = Path(tracking)
    receipt = rt.read(tracking / 'receipt.json')
    job = receipt['job']; seq = job['sequence']; source = cfg['sources'][seq]
    rt.require(receipt['schema'] == 'bounded_velocity513_free_tracking_v1' and receipt['status'] == 'complete'
        and receipt['protocol_sha256'] == rt.sha(config) and job in cfg['tracking_matrix']
        and (job_id is None or job_id == job['job_id']) and receipt['cache'] == source['cache']
        and receipt['frames'] == source['frames'] and receipt['pose_enabled'] is job['pose_enabled']
        and receipt['evaluation_GT_annotations_loaded'] is False and receipt['GT_used_for_tracking'] is False
        and receipt['inference_shape_shuffle'] is False, '实际追踪/模型/自然Pose/GT边界不同')
    mot = tracking / 'data' / (seq + '.txt')
    rt.require(rt.sha(mot) == receipt['mot_sha256'], '原MOT被修改')
    metric = dep[2]
    predictions, count = metric.prediction_rows(mot.read_text(encoding='utf-8'), source['frames'])
    rt.require(count == receipt['tracked_rows'], '预测行数改变/被过滤')
    _, gt = rt.load_gt(cfg, dep, source)
    output = dep[3].storage().physical_child(output, rt.EXP)
    rt.require(not output.exists(), '评价partial不覆盖')
    output.mkdir(parents=True)
    raw, numerical_sha = metric.trackeval_numeric(source, gt, tracking, output)
    summary = {}
    for name, classes in raw.items():
        value = classes['pedestrian']
        metric.validate_count(name, value['Count'], count, len(gt), seq, source['frames'])
        fraction = {}
        for group, keys in [('HOTA', ('HOTA', 'AssA', 'DetA')), ('Identity', ('IDF1',)), ('CLEAR', ('MOTA',))]:
            for key in keys:
                v = value[group][key]
                fraction[key] = sum(v)/len(v) if isinstance(v, list) else float(v)
        summary[name] = dict(metrics_fraction=fraction, metrics_percent={k: 100*v for k, v in fraction.items()},
                             IDSW_count=int(value['CLEAR']['IDSW']))
    registry_ref = rt.registry_for_sequence(cfg, seq)['registry']
    registry = rt.read(rt.checked(registry_ref))
    expected = {s: cfg['sources'][s] for s in registry['sources']}
    rt.require(registry['sources'] == expected and registry['sequences'][seq]['cache'] == source['cache'], '原事件预测来源不同')
    events = [e for e in registry['events'] if e['sequence'] == seq]
    gap = rt.gap_numeric(cfg, dep)
    recovery = gap.evaluate_events(events, registry['sequences'][seq]['endpoint_GT'], predictions)
    rt.require(recovery['overall']['total_events'] == len(events), '必须原全事件分母，不能筛失败端点')
    result = dict(schema='bounded_velocity513_trackeval_gap_v1', status='complete', protocol_sha256=rt.sha(config),
        job=job, frames=source['frames'], summary=summary, metrics_percent=summary[seq]['metrics_percent'], raw_results=raw,
        recovery=recovery, registry=registry_ref, GT_rows=len(gt), source_cache=source['cache'],
        tracking_receipt_sha256=rt.sha(tracking / 'receipt.json'), DO_PREPROC=False, predictions_GT_filtered=False,
        GT_ID0_original=True, GT_used_only_for_metric=True, numerical_source_sha256=numerical_sha, test_read=False)
    with (output / 'report.json').open('x', encoding='utf-8') as stream:
        stream.write(rt.canonical(result) + '\n')
    return dict(status='complete', job=job, GT_rows=len(gt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('track', 'metric'), required=True)
    for name in ('config', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--job-id'); parser.add_argument('--tracking', type=Path)
    parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', YOLO_AUTOINSTALL='false')
    if not args.execute:
        cfg, _, _ = rt.validate_config(args.config)
        result = dict(status='readonly513_bounded_velocity_job_no_execution', jobs=len(cfg['tracking_matrix']),
                      new_updates=0, GT_annotations_loaded=False, test_read=False)
    elif args.action == 'track': result = track(args.config, args.job_id, args.output)
    else: result = evaluate(args.config, args.tracking, args.output, args.job_id)
    print(rt.canonical(result))
