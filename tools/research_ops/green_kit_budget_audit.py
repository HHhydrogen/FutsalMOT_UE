"""绿色十八臂完成后的独立实际预算核对；只读CPU，不重推图像。"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from green_kit_runtime import checked, complete_model, physical_output, read, require, rows, sha, validate_protocol


def audit(config, control, output):
    cfg, prediction = validate_protocol(config); control = Path(control); state = read(control/'driver_state.json')
    require(state['status'] == 'complete_18_train_tracking_and_analysis'
            and len(state['completed_train']) == len(state['completed_tracking']) == 18
            and read(control/'analysis_a01/report.json')['status'] == 'complete', '18组及分析尚未全部闭合')
    old = read(checked(cfg['v9_protocol'])); totals = dict(updates=0, R_windows=0, S_windows=0, R_pairs=0, S_pairs=0,
                                                       R_known_pairs=0, S_known_pairs=0)
    proofs = []; matched = {}
    for job in cfg['training_matrix']:
        folder = control/'runs'/job['fold']/str(job['seed'])/job['appearance']
        _, _, _, _, binding = complete_model(config, folder/'training')
        real = {w['window_uid']: w for w in rows(checked(old['folds'][job['fold']]['real_pool']))}
        synthetic = {w['window_uid']: w for w in rows(checked(prediction['synthetic_pools'][job['appearance']]['pool']))}
        expected_totals = dict(R_pairs=0, S_pairs=0, R_known_pairs=0, S_known_pairs=0)
        for row in rows(folder/'training/exposures.jsonl'):
            expected = {}
            for domain, pool, prefix in [('real', real, 'R'), ('synthetic', synthetic, 'S')]:
                windows = [pool[r['window_uid']] for r in row[domain]]
                expected[prefix+'_pairs'] = sum(len(w['candidates']) for w in windows)
                expected[prefix+'_known_pairs'] = sum(c['label'] is not None for w in windows for c in w['candidates'])
            require([row[k] for k in ('real_pair_exposures', 'synthetic_pair_exposures', 'real_known_pairs', 'synthetic_known_pairs')] ==
                    [expected[k] for k in ('R_pairs', 'S_pairs', 'R_known_pairs', 'S_known_pairs')], '实际pair预算不符')
            for key, value in expected.items():
                expected_totals[key] += value
        identity = tuple(binding[k] for k in ('initialization_sha256', 'R_window_UID_chain_sha256', 'S_window_UID_chain_sha256', 'adapter_sha256'))
        common = dict(identity=identity, pair_totals=expected_totals)
        key = (job['fold'], job['seed'])
        if key in matched:
            require(matched[key] == common, 'A/B初始化/曝光顺序/pair不一致')
        else:
            matched[key] = common
        totals['updates'] += 1000; totals['R_windows'] += 3000; totals['S_windows'] += 1000
        for name, value in expected_totals.items():
            totals[name] += value
        proofs.append(dict(**job, checkpoint_sha256=sha(folder/'training/last.pt'), pair_totals=expected_totals))
    require([totals[k] for k in ('updates', 'R_windows', 'S_windows')] == [18000, 54000, 18000], '全矩阵实际预算不符')
    output = physical_output(output); require(not output.exists(), '新核对收据，不覆盖')
    output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(schema='green_kit_actual_budget_audit_v1', status='complete', protocol_sha256=sha(config), totals=totals,
                  all_18_runs=proofs, all_9_AB_initialization_exposure_pair_checks=True, optimizer_replay=0,
                  historical_reference_new_updates=0, test116187_read=False, GPU_used=False)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('config', 'control', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); result = audit(args.config, args.control, args.output)
    print(json.dumps(dict(status=result['status'], totals=result['totals']), ensure_ascii=False))
