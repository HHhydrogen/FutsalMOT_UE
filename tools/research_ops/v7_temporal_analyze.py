"""整理已完成时序对照，保留同真实曝光与两类预训练参考；不重跑评价。"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

BASE = Path('D:/projects/FutsalMOT_Research/pose/association_dev_a01')
SEEDS = (20261024, 20261025, 20261026)
ARMS = ('R3', 'R3S_blue', 'R3S_terracotta')
MODELS = ['pretrained']+[f'{arm}_seed{seed}' for seed in SEEDS for arm in ARMS]
METRICS = ('AssA', 'HOTA', 'IDF1')


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def require(ok, message):
    if not ok: raise ValueError(message)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def checked(ref):
    path = Path(ref['path']); require(path.is_file() and sha(path) == ref['sha256'], '报告身份变化')
    return read(path)


def difference(a, b):
    return dict(delta_pp={name: a['metrics_percent'][name]-b['metrics_percent'][name] for name in METRICS},
                IDSW_delta_count=a['IDSW_count']-b['IDSW_count'])


def means(rows):
    return dict(delta_pp={name: statistics.mean(row['delta_pp'][name] for row in rows) for name in METRICS},
                IDSW_delta_count=statistics.mean(row['IDSW_delta_count'] for row in rows))


def analyze(control, output):
    require(BASE/'v7_temporal' in control.parents and BASE/'v7_temporal' in output.parents and not output.exists(), '须全新D研究分析输出')
    state = read(control/'state.json')
    require(state['status'] == 'complete_all_ten_temporal_CPU_and_TrackEval' and state['completed'] == MODELS, '十模型未完整结束')
    summary = checked(state['summary'])
    require(list(summary['models']) == MODELS and summary['new_training_updates'] == 0 and summary['all_models_temporal_actually_used'], '时序方法未在全部模型实际使用')
    config_path = BASE/'v7_temporal/frozen_a01/config.json'
    config = read(config_path); require(sha(config_path) == state['protocol_sha256'], '实际冻结协议变化')
    full_pt_ref = dict(path=str(BASE/'metrics_pretrained_pose_lambda01/report.json'), sha256='d0bae8afe5e5b970cd42c221ae67cdbe4c857ef4548d80a79de86b440abc0b2b')
    full_pt = checked(full_pt_ref)['summary']['COMBINED_SEQ']
    models = {}; patterns = {}
    for key, entry in summary['models'].items():
        metric = checked(entry['report']); receipt = checked(entry['receipt'])
        require(metric['status'] == 'complete_v7_existing_development_evaluation' and metric['frames'] == 450 and metric['DO_PREPROC'] is False and metric['predictions_filtered'] is False and metric['test_read'] is False, '指标口径变化')
        require(metric['summary'] == entry['summary'] and metric['protocol_sha256'] == state['protocol_sha256'], '模型或协议指标不符')
        require(receipt['model_sha256'] == config['models'][key]['model_sha256'] and receipt['v7_sources'] == metric['v7_sources'], '新时序实现/模型身份不符')
        old = checked(config['models'][key]['static_metrics'])
        static_delta = difference(metric['summary']['COMBINED_SEQ'], old['summary']['COMBINED_SEQ'])
        require(static_delta == entry['vs_same_model_static_v6']['COMBINED_SEQ'], '静态对照差异复算不一致')
        audit = {name: sum(value['audit'].get(name, 0) for value in receipt['sequences'].values()) for name in ('temporal_shape_pairs_used', 'original_static_pose_fallback_pairs', 'bbox_fallback_pairs', 'bbox_gated_out_pairs')}
        require(audit['temporal_shape_pairs_used'] == entry['temporal_OLS_pairs'] > 0, '方法退成全静态')
        pattern = tuple(receipt['sequences'][name]['mot_sha256'] for name in ('SNMOT-151', 'SNMOT-152', 'SNMOT-153'))
        patterns.setdefault(pattern, []).append(key)
        models[key] = dict(metrics=metric['summary'], audit=audit, vs_same_model_static_v6=static_delta,
                           vs_original_fullframe_pretrained=difference(metric['summary']['COMBINED_SEQ'], full_pt))
    paired = {}; comparisons = {}
    for arm in ARMS[1:]:
        rows = []
        for seed in SEEDS:
            current = models[f'{arm}_seed{seed}']['metrics']['COMBINED_SEQ']
            real = models[f'R3_seed{seed}']['metrics']['COMBINED_SEQ']
            pretrained = models['pretrained']['metrics']['COMBINED_SEQ']
            rows.append(dict(seed=seed, vs_same3000R_temporal_R3=difference(current, real), vs_temporal_pretrained=difference(current, pretrained), vs_original_fullframe_pretrained=difference(current, full_pt)))
        paired[arm] = rows
        average = {name: means([row[name] for row in rows]) for name in rows[0] if name != 'seed'}
        positive = sum(row['vs_same3000R_temporal_R3']['delta_pp']['AssA'] > 0 for row in rows)
        real_difference = average['vs_same3000R_temporal_R3']['delta_pp']
        comparisons[arm] = dict(means=average, positive_seeds=positive,
            descriptive_progress_passed=real_difference['AssA'] >= .5 and positive >= 2 and real_difference['HOTA'] >= 0 and real_difference['IDF1'] >= -.5)
    result = dict(schema='futsalmot_v7_complete_temporal_analysis', status='complete', models=models, paired=paired, comparisons=comparisons,
                  unique_current_MOT_patterns=len(patterns), current_pattern_members=list(patterns.values()),
                  source_summary=state['summary'], protocol_sha256=state['protocol_sha256'], new_formal_training_updates=0,
                  real_exposures_per_existing_trained_arm=3000, final116187_read=False, model_or_image_or_GT_read=False,
                  limitations=['same_game9_not_independent_matches', 'three_training_seeds_not_three_matches', 'new_temporal_algorithm_exploratory', 'no_new_Pose_training', 'COCO_quality_diagnostic_not_soccer_pose_accuracy'])
    lines = ['# v7完整时序对照', '', '复用v5实际权重；每个训练臂3000R，混合另1000S；本轮新增正式更新0，最终116/187封存。', '',
             '| 模型 | AssA | HOTA | IDF1 | IDSW | 实际OLS候选对 |', '|---|---:|---:|---:|---:|---:|']
    for key, value in models.items():
        metric = value['metrics']['COMBINED_SEQ']; m = metric['metrics_percent']
        lines.append(f"| {key} | {m['AssA']:.6f} | {m['HOTA']:.6f} | {m['IDF1']:.6f} | {metric['IDSW_count']} | {value['audit']['temporal_shape_pairs_used']} |")
    lines += ['', '| 混合组均值 | 比较 | AssA Δpp | HOTA Δpp | IDF1 Δpp | IDSW Δcount |', '|---|---|---:|---:|---:|---:|']
    for arm, value in comparisons.items():
        for name, row in value['means'].items():
            m = row['delta_pp']; lines.append(f"| {arm} | {name} | {m['AssA']:+.6f} | {m['HOTA']:+.6f} | {m['IDF1']:+.6f} | {row['IDSW_delta_count']:+.6f} |")
    lines += ['', '全部逐seed、逐片段及静态对照保存在report.json。计算行和候选对不是独立人物。', '']
    output.mkdir(parents=True)
    (output/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(status='complete', comparisons=comparisons, unique_MOT_patterns=len(patterns)), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); analyze(args.control.resolve(), args.output.resolve())


if __name__ == '__main__': main()
