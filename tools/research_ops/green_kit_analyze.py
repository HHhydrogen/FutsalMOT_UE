"""绿色A/B全部18组结果及原R/motion/PT参考；保留全部折、seed、负结果。"""
import argparse
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from green_kit_runtime import GAMES, SEEDS, checked, physical_output, read, require, sha, validate_protocol
METRICS = ('AssA', 'HOTA', 'IDF1')


def average(values):
    return {m: statistics.mean(v[m] for v in values) for m in METRICS}


def contrast(left, right):
    cells = {(f, s): {m: left[(f, s)][m]-right[(f, s)][m] for m in METRICS} for f in GAMES for s in SEEDS}
    macro = average(list(cells.values()))
    seed = {str(s): average([cells[(f, s)] for f in GAMES]) for s in SEEDS}
    game = {f: average([cells[(f, s)] for s in SEEDS]) for f in GAMES}
    checks = dict(AssA_at_least_0_5pp=macro['AssA'] >= .5,
                  at_least_two_seed_macro_positive=sum(v['AssA'] > 0 for v in seed.values()) >= 2,
                  at_least_two_game_mean_nonnegative=sum(v['AssA'] >= 0 for v in game.values()) >= 2,
                  HOTA_nonnegative=macro['HOTA'] >= 0, IDF1_drop_at_most_0_5pp=macro['IDF1'] >= -.5)
    return dict(macro_mean_pp=macro, per_seed_macro_pp=seed, per_game_mean_pp=game,
                cells=[dict(fold=f, seed=s, delta_pp=d) for (f, s), d in cells.items()], checks=checks, passed=all(checks.values()))


def analyze(config, control, output):
    cfg, _ = validate_protocol(config); control = Path(control); state = read(control/'driver_state.json')
    require(state['protocol_sha256'] == sha(config) and len(state['completed_train']) == len(state['completed_tracking']) == 18,
            '必须完整18组，不挑部分结果')
    values = {'A': {}, 'B': {}}; all_rows = []
    for job in cfg['training_matrix']:
        folder = control/'runs'/job['fold']/str(job['seed'])/job['appearance']
        metric = read(folder/'metric/report.json'); receipt = read(folder/'training/run_receipt.json')
        tracking = read(folder/'tracking/receipt.json'); recovery = read(folder/'recovery.json')
        require(metric['status'] == 'complete' and metric['protocol_sha256'] == sha(config)
                and receipt['completed_updates'] == 1000 and receipt['real_window_exposures'] == 3000
                and receipt['synthetic_window_exposures'] == 1000, '预算或评价身份不完整')
        value = metric['summary'][metric['sequence']]['metrics_percent']
        values[job['appearance']][(job['fold'], job['seed'])] = value
        all_rows.append(dict(**job, metrics_percent=value, training_receipt=receipt,
                             tracker_audit=tracking['audit'], recovery=recovery))
    v9 = read(checked(cfg['v9_analysis'])); old = read(checked(cfg['v9_protocol']))
    v8 = read(checked(old['v8_analysis']))
    r = {(row['fold'], row['seed']): row['metrics_percent'] for row in v9['all_rows']
         if row['variant'] == 'gated' and row['regime'] == 'R'}
    capacity = {(row['fold'], row['seed']): row['metrics_percent'] for row in v9['all_rows']
                if row['variant'] == 'motion_residual' and row['regime'] == 'RS'}
    motion = {(row['heldout_game'], row['seed']): row['metrics_percent'] for row in v8['all_rows'] if row['arm'] == 'motion_RS'}
    comparisons = dict(B_minus_A=contrast(values['B'], values['A']))
    for appearance in 'AB':
        comparisons[appearance+'_minus_gated_R'] = contrast(values[appearance], r)
        comparisons[appearance+'_minus_motion_RS'] = contrast(values[appearance], motion)
        comparisons[appearance+'_minus_capacity_matched_motion_RS'] = contrast(values[appearance], capacity)
        for mode in ('PT_bbox', 'PT_static_pose'):
            pretrained = {(f, s): v8['pretrained_fixed_baselines'][f][mode] for f in GAMES for s in SEEDS}
            comparisons[appearance+'_minus_'+mode] = contrast(values[appearance], pretrained)
    recovery_rates = {}
    for appearance in 'AB':
        recovery_rates[appearance] = {}
        for seed in SEEDS:
            reports = [next(iter(r['recovery']['sequences'].values()))['overall'] for r in all_rows
                       if r['appearance'] == appearance and r['seed'] == seed]
            total = sum(r['total_events'] for r in reports); recovered = sum(r['same_prediction_ID_recovered'] for r in reports)
            require(total == 956, '固定检测断档proxy分母变化')
            recovery_rates[appearance][str(seed)] = dict(events=total, recovered=recovered, recovery_rate=recovered/total)
    output = physical_output(output); require(not output.exists(), '全新分析目录')
    output.mkdir(parents=True)
    result = dict(schema='green_kit_gated_AB_analysis_v1', status='complete', protocol_sha256=sha(config),
        all_rows=all_rows, groups_macro={a: average(list(v.values())) for a, v in values.items()},
        comparisons=comparisons, gap_proxy_recovery=recovery_rates, new_actual_updates=18000,
        R_window_exposures=54000, S_window_exposures=18000, historical_reference_new_updates=0,
        references=dict(v9_analysis=cfg['v9_analysis'], v8_analysis=old['v8_analysis']), test116187_read=False,
        limitations=['three already observed short official-train matches; not a new blind test or futsal generalization',
        'A/B changes clothing color and texture together; not color-only or full-frame detector generalization',
        'same synthetic motion seed; source visibility unknown, diagnostic/not_training/MRQ_syncfalse retained',
        'same R windows, extra S is not equal FLOPs or pair budget', 'detection-gap proxy is not physical occlusion'])
    (output/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); result = analyze(args.config, args.control, args.output)
    print(json.dumps(dict(status=result['status'], comparisons=result['comparisons']), ensure_ascii=False))
