"""从已闭合绿色18臂原日志导出论文表/曲线；不补造历史字段或重跑模型。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from training_journal import canonical, physical, require, sha, write_new

EXPERIMENT = Path('D:/projects/FutsalMOT_Research/pose/green_seeded_kit_pair_a01')
STEP_FIELDS = ('fold', 'seed', 'appearance', 'actual_update', 'loss', 'real_loss', 'synthetic_loss',
               'real_windows', 'synthetic_windows', 'real_pair_exposures', 'synthetic_pair_exposures',
               'real_known_pairs', 'synthetic_known_pairs', 'real', 'synthetic', 'augmentation', 'chain_sha256')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def extract_steps(path):
    chain = '0'*64
    result = []
    with Path(path).open(encoding='utf-8') as stream:
        for index, line in enumerate(stream):
            row = json.loads(line); recorded = row.pop('chain_sha256')
            require(row['actual_update'] == index+1 and row['update_index'] == index
                    and row['real_windows'] == len(row['real']) == 3
                    and row['synthetic_windows'] == len(row['synthetic']) == 1,
                    '历史步序/实际窗口预算变化')
            chain = hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
            require(recorded == chain, '历史曝光链变化')
            row['chain_sha256'] = recorded; result.append(row)
    require(len(result) == 1000, '只导出闭合1000更新，不补齐/插值')
    return result, chain


def csv_write(path, fields, rows):
    with Path(path).open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields, extrasaction='ignore'); writer.writeheader()
        for row in rows:
            writer.writerow({k: canonical(v) if isinstance(v, (dict, list)) else v for k, v in row.items() if k in fields})


def figures(output, runs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(3, 3, figsize=(13, 9), sharex=True)
    for i, fold in enumerate(('game4', 'game6', 'game9')):
        for j, field in enumerate(('loss', 'real_loss', 'synthetic_loss')):
            ax = axes[i, j]
            for appearance, color in [('A', '#3873b3'), ('B', '#d06a32')]:
                sequences = [[s[field] for s in r['steps']] for r in runs
                             if r['job']['fold'] == fold and r['job']['appearance'] == appearance]
                require(len(sequences) == 3, '曲线必须包括全部三个seed')
                for values in sequences:
                    smooth = [statistics.mean(values[max(0, n-49):n+1]) for n in range(len(values))]
                    ax.plot(range(1, 1001), smooth, color=color, alpha=.2, linewidth=.7)
                mean = [statistics.mean(v[n] for v in sequences) for n in range(1000)]
                smooth = [statistics.mean(mean[max(0, n-49):n+1]) for n in range(1000)]
                ax.plot(range(1, 1001), smooth, color=color, label=appearance, linewidth=1.2)
            ax.set_title(f'{fold}: {field}'); ax.grid(alpha=.2)
            if i == 2:
                ax.set_xlabel('Committed optimizer updates')
            if j == 0:
                ax.set_ylabel('Loss (50-update trailing mean)')
    axes[0, 0].legend(title='Kit variant')
    figure.suptitle('Green kit: all 18 runs; thin lines = seeds; bold = mean; raw values in steps.csv')
    figure.tight_layout()
    figure.savefig(output/'loss_curves.png', dpi=180)
    figure.savefig(output/'loss_curves.pdf')
    plt.close(figure)


def export(output, *, execute=False, plots=False):
    control = EXPERIMENT/'control_a01'
    sources = dict(state=control/'driver_state.json', protocol=EXPERIMENT/'frozen_a01/protocol.json',
        analysis=control/'analysis_a01/report.json', budget=EXPERIMENT/'postrun_audit_a01/actual_budget.json',
        milestone=EXPERIMENT/'milestone_complete_a01.json')
    state = read(sources['state']); cfg = read(sources['protocol']); analysis = read(sources['analysis'])
    require(state['status'] == 'complete_18_train_tracking_and_analysis' and analysis['status'] == 'complete'
            and len(state['completed_train']) == len(state['completed_tracking']) == 18,
            '必须完整18臂训练及评价，不导出选择子集')
    runs = []
    for job in cfg['training_matrix']:
        root = control/'runs'/job['fold']/str(job['seed'])/job['appearance']
        path = root/'training/exposures.jsonl'; receipt_path = root/'training/run_receipt.json'
        receipt = read(receipt_path); steps, chain = extract_steps(path)
        require(receipt['completed_updates'] == 1000 and receipt['exposure_chain'] == chain,
                '历史训练收据/曝光链不闭合')
        refs = {name: dict(path=str(p), sha256=sha(p)) for name, p in
                [('steps', path), ('receipt', receipt_path), ('metric', root/'metric/report.json'),
                 ('tracking', root/'tracking/receipt.json'), ('recovery', root/'recovery.json')]}
        runs.append(dict(job=job, steps=steps, receipt=receipt, refs=refs))
    require(len(runs) == 18, '训练矩阵必须18组')
    manifest = dict(schema='historical_training_paper_export_v1', status='readonly_plan',
        exporter_sha256=sha(__file__), runs=18, actual_updates=18000, R_windows=54000, S_windows=18000,
        sources={k: dict(path=str(p), sha256=sha(p)) for k, p in sources.items()},
        availability=dict(per_step_losses=True, per_step_window_UID_and_epoch=True, per_step_pair_budget=True,
            per_step_learning_rate=False, per_step_gradient_norm=False, per_step_wall_seconds=False,
            periodic_checkpoint_archive=False, complete_RNG_checkpoints=False, final_model_optimizer=True),
        missing_data_policy='字段缺失保持缺失；固定协议LR不是逐步实测LR；不重训/插值/补造中间权重或RNG',
        historical_training_logs_unchanged=True, new_optimizer_updates=0, test116187_read=False,
        plots=dict(enabled=plots, all_seeds=True, smoothing='trailing_mean_50_display_only', raw_csv=True),
        run_sources=[dict(job=r['job'], refs=r['refs']) for r in runs])
    if not execute:
        return manifest
    output = physical(output); require(not output.exists(), '新论文导出目录，partial不隐式覆盖')
    output.mkdir(parents=True)
    write_new(output/'export_started.json', manifest)
    flat = [dict(r['job'], **s) for r in runs for s in r['steps']]
    csv_write(output/'steps.csv', STEP_FIELDS, flat)
    summaries = []
    for run in runs:
        receipt = run['receipt']; steps = run['steps']
        summary = dict(run['job'], updates=1000, R_windows=3000, S_windows=1000,
            train_wall_seconds=receipt['wall_seconds'], final_checkpoint_sha256=receipt['checkpoint_sha256'],
            final_loss=steps[-1]['loss'], final_R_loss=steps[-1]['real_loss'], final_S_loss=steps[-1]['synthetic_loss'])
        summaries.append(summary)
    csv_write(output/'runs.csv', tuple(summaries[0]), summaries)
    metrics = [dict(fold=r['fold'], seed=r['seed'], appearance=r['appearance'], **r['metrics_percent']) for r in analysis['all_rows']]
    csv_write(output/'tracking_metrics.csv', tuple(metrics[0]), metrics)
    contrasts = [dict(contrast=k, **v['macro_mean_pp'], passed=v['passed']) for k, v in analysis['comparisons'].items()]
    csv_write(output/'comparisons.csv', tuple(contrasts[0]), contrasts)
    if plots:
        figures(output, runs)
    for run in runs:
        require(all(sha(v['path']) == v['sha256'] for v in run['refs'].values()), '导出期间原记录改变')
    manifest['status'] = 'complete_existing_records_exported_missing_fields_explicit'
    manifest['outputs'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in output.iterdir() if p.is_file()}
    write_new(output/'complete.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--plots', action='store_true')
    args = parser.parse_args()
    result = export(args.output, execute=args.execute, plots=args.plots)
    print(canonical({k: result[k] for k in ('status', 'runs', 'actual_updates', 'R_windows', 'S_windows')}))
