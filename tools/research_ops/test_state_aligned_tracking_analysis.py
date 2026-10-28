"""只用合成小收据核完整矩阵、绝对成绩、负结果与事前区间；不读取实际实验。"""
from copy import deepcopy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import state_aligned_tracking_analysis as a


def fixtures():
    panels = dict(original_heldout=list(a.OLD), old_external=['external0', 'external1'], seven_observed=['seven'+str(i) for i in range(7)])
    target, baseline = [], []
    for regime, sequence, fold, seed in sorted(a.expected_cells(panels)):
        total = 0 if sequence == 'seven0' else (690 if sequence == 'seven6' else 300)
        for origin, result in [('new', target), ('old', baseline)]:
            condition = origin+'_'+regime
            value = dict(new_R=40, new_RS=41, old_R=42, old_RS=44)[condition]+a.FOLDS.index(fold)+a.SEEDS.index(seed)
            success = 0 if total == 0 else dict(new_R=50, new_RS=40, old_R=60, old_RS=30)[condition]
            mid = origin+'_'+regime+'_'+fold+'_'+str(seed)
            result.append(dict(model_id=mid, baseline_model_id='old_'+regime+'_'+fold+'_'+str(seed), regime=regime,
                sequence=sequence, fold=fold, seed=seed, condition=condition, metrics={m: value for m in a.METRICS},
                gap=dict(total_events=total, same_prediction_ID_recovered=success, recovery_rate=success/total if total else None),
                report=dict(path='fixture/'+mid+'/'+sequence+'.json', sha256='0'*64), tracking_receipt=dict(path='fixture/receipt.json', sha256='1'*64),
                frames=2, source_origin='fixture'))
    return panels, target, baseline


class PairingTests(unittest.TestCase):
    def test_complete_360_pairs_four_absolute_conditions_negative_interaction(self):
        panels, new, old = fixtures()
        cells = a.paired_cells(new, old, panels)
        self.assertEqual(len(cells), 360)
        for name, delta in zip(a.COMPARISONS, (-3, -2, 1, -1)):
            self.assertEqual({r['delta_pp']['AssA'] for r in cells if r['comparison'] == name}, {delta})
        matches = a.paired_matches(cells, panels)
        self.assertEqual(len(matches), 48)
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel'] == 'original_heldout'}, {3})
        self.assertEqual({r['matched_training_cells'] for r in matches if r['panel'] == 'seven_observed'}, {9})
        absolute, summaries = a.absolute_results(new, old, panels)
        self.assertEqual((len(absolute), len(summaries)), (48, 12))
        first = next(r for r in absolute if r['condition'] == 'new_R' and r['sequence'] == 'SNMOT-060')
        self.assertEqual(first['metrics']['AssA'], 41)
        self.assertEqual(sum(a.source_gap_denominators(new, panels).values()), 3690)

    def test_missing_duplicate_nonfinite_and_wrong_identity_rejected(self):
        panels, new, old = fixtures()
        for bad in (new[:-1], new+[new[0]]):
            with self.assertRaises(ValueError): a.paired_cells(bad, old, panels)
        for mutation in ('nonfinite', 'identity', 'gap'):
            bad = deepcopy(new)
            if mutation == 'nonfinite': bad[0]['metrics']['MOTA'] = float('nan')
            if mutation == 'identity': bad[0]['baseline_model_id'] = 'wrong'
            if mutation == 'gap': bad[0]['gap']['recovery_rate'] = 0.123
            with self.assertRaises(ValueError): a.paired_cells(bad, old, panels)

    def test_no_event_null_preserved_not_zero_or_new_denominator(self):
        panels, new, old = fixtures()
        matches = a.paired_matches(a.paired_cells(new, old, panels), panels)
        metrics, gaps = a.describe(matches, panels)
        self.assertEqual(sum(len(v) for family in metrics.values() for v in family.values()), 60)
        self.assertEqual(sum(len(family) for family in gaps.values()), 12)
        for family in a.COMPARISONS:
            self.assertEqual(gaps[family]['seven_observed']['null_matches'], ['seven0'])
            self.assertIsNone(gaps[family]['seven_observed']['Student_t_95CI'])
            self.assertEqual(gaps[family]['seven_observed']['n_independent_matches'], 6)
            self.assertEqual(metrics[family]['seven_observed']['AssA']['n_independent_matches'], 7)

    def test_intervals_fixed_seed_negative_and_degrees(self):
        for n in (2, 3, 7):
            values = {str(i): -i-1 for i in range(n)}
            result = a.effect_intervals(values)
            self.assertEqual(result, a.effect_intervals(values))
            self.assertEqual(result['bootstrap_seed'], 20261028)
            self.assertEqual(result['Student_t_degrees_of_freedom'], n-1)
            self.assertEqual(result['mean_delta_pp'], -(n+1)/2)
            self.assertLess(result['percentile_match_bootstrap_95CI'][1], 0)
            self.assertEqual(len(result['leave_one_match_out_mean']), n)
        self.assertEqual(a.quantile([0, 10, 20, 30], .25), 7.5)
        self.assertIsNone(a.effect_intervals({'a': None, 'b': None})['mean_delta_pp'])

    def test_match_weighting_does_not_treat_seeds_as_matches(self):
        panels, new, old = fixtures()
        for r in new:
            if r['sequence'] == 'external0' and r['regime'] == 'RS':
                r['metrics']['AssA'] += 9 if r['fold'] == 'game4' and r['seed'] == a.SEEDS[0] else 0
        matches = a.paired_matches(a.paired_cells(new, old, panels), panels)
        row = next(r for r in matches if r['sequence'] == 'external0' and r['comparison'] == a.COMPARISONS[0])
        self.assertEqual(row['delta_pp']['AssA'], -2)
        metrics, _ = a.describe(matches, panels)
        described = metrics[a.COMPARISONS[0]]['old_external']['AssA']
        self.assertEqual(described['n_independent_matches'], 2)
        self.assertEqual(described['mean_delta_pp'], -2.5)


class FileFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.exp = self.root/'pose/state_aligned_training_a01'
        self.exp.mkdir(parents=True)
        self.root_patch = patch.object(a, 'R', self.root); self.exp_patch = patch.object(a, 'EXP', self.exp)
        self.root_patch.start(); self.exp_patch.start()

    def tearDown(self):
        self.exp_patch.stop(); self.root_patch.stop(); self.tmp.cleanup()

    def put(self, relative, body):
        path = self.root/relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(a.canonical(body), encoding='utf-8')
        return a.ref(path)

    def build(self):
        panels, new, old = fixtures(); sources = {s: dict(frames=2, cache=dict(path='unopened-cache', sha256='2'*64)) for s in a.panels_map(panels)}
        learning = self.put('learning/protocol.json', {'fixture': True})
        budget = self.put('training/budget.json', dict(schema='independent_state_aligned18_budget_audit_v1',
            status='complete18_state_aligned_R_actual_budget_full_records_and_exit_verified', training_processes_absent=True,
            protocol=learning, complete_checkpoints_read_back=378, nine_paired_R_RS_exposures_equal=True, test_read=False,
            actual_totals=dict(updates=18000, R_windows=54000, S_windows=9000)))
        complete = self.put('training/complete.json', dict(schema='state_aligned_training_complete_root_v1',
            status='complete18_state_aligned_training_actual_budget_records_exit_verified_not_tracking_complete',
            budget_audit=budget, protocol=learning, actual_training_and_audit_processes_absent=True, test_read=False))
        models = {}; old_models = {}
        for r in new:
            mid = r['model_id']; models[mid] = {k: r[k] for k in ('model_id', 'baseline_model_id', 'regime', 'fold', 'seed')}
            models[mid]['learning_protocol'] = learning
        for r in old: old_models[r['model_id']] = {k: r[k] for k in ('model_id', 'regime', 'fold', 'seed')}
        units = []
        for idx, row in enumerate(old):
            sequence = row['sequence']; seven = sequence in panels['seven_observed']
            job = dict(sequence=sequence, method='motion', fold=row['fold'], seed=row['seed'])
            if seven: job.update(kind='learned', group='A' if row['regime'] == 'R' else 'B')
            else: job.update(kind='pure_R' if row['regime'] == 'R' else 'new_RS', pool='balanced')
            receipt = self.put('old/'+str(idx)+'/receipt.json', {'fixture': True})
            body = dict(schema='seven_match_ABC_trackeval_gap_v1' if seven else 'v10_independent_trackeval_gap_v1', status='complete',
                protocol_sha256=a.SEVEN_PROTOCOL_SHA if seven else a.OLD_PROTOCOL_SHA, job=job, frames=2,
                DO_PREPROC=False, predictions_GT_filtered=False, test_read=False, tracking_receipt_sha256=receipt['sha256'],
                summary={sequence: dict(metrics_percent=row['metrics'])}, recovery=dict(overall=row['gap']))
            metric = self.put('old/'+str(idx)+'/metric.json', body)
            units.append(dict(**{k: row[k] for k in ('model_id', 'regime', 'sequence', 'fold', 'seed')}, metric_report=metric, tracking_receipt=receipt))
        inventory = self.put('inventory/new.json', dict(schema='state_aligned_strongmotion_tracking_inventory_v1', models=list(models.values()), sources=sources, panels=panels))
        source = self.put('inventory/source.json', dict(schema='trainR_intercept_source_inventory_v1',
            status='complete18_model_refs3_cleanR_pools180_baseline_refs_no_weight_or_pool_loaded', models=list(old_models.values()),
            sources=sources, panels=panels, baseline_units=units))
        jobs = [dict(job_id=str(i), **{k: row[k] for k in ('model_id', 'baseline_model_id', 'regime', 'sequence', 'fold', 'seed')}) for i, row in enumerate(new)]
        cfg = dict(schema='state_aligned_tracking_protocol_v1', approved_by='root', tracking_authorized=True, test_sealed=True, new_optimizer_updates=0,
            output_root=str(self.exp), inventory=inventory, source_inventory=source, sources=sources, panels=panels, jobs=jobs,
            training_complete=complete, training_budget=budget, learning_protocol=learning, expected_GT_rows={s: 20 for s in sources})
        cfg_ref = self.put('pose/state_aligned_training_a01/frozen/config.json', cfg)
        reports = []
        for idx, (job, row) in enumerate(zip(jobs, new)):
            receipt = dict(schema='state_aligned_tracking_receipt_v1', status='complete', job=job, protocol_sha256=cfg_ref['sha256'],
                model_id=row['model_id'], baseline_model_id=row['baseline_model_id'], learning_protocol=learning, training_budget=budget,
                source_cache=sources[row['sequence']]['cache'], frames=2, tracked_rows=3, frame_counts=[1, 2], prefix_frames=None, new_optimizer_updates=0)
            for k in ('test_read', 'GT_used_for_tracking', 'evaluation_GT_coordinate_files_opened', 'GPU_used', 'alias_used', 'intercept_applied'): receipt[k] = False
            for k in ('source_inputs_unchanged', 'original_model_state_unchanged', 'original_normalizer_unchanged', 'native_ordered_batch_forward_preserved'): receipt[k] = True
            receipt_ref = self.put('pose/state_aligned_training_a01/control/jobs/'+str(idx)+'/receipt.json', receipt)
            body = dict(schema='state_aligned_tracking_metric_v1', status='complete', job=job, protocol_sha256=cfg_ref['sha256'],
                baseline_model_id=row['baseline_model_id'], learning_protocol=learning, training_budget=budget, source_cache=sources[row['sequence']]['cache'],
                frames=2, tracked_rows=3, GT_rows=20, GT_used_only_for_metric=True, GT_ID0_original=True, new_optimizer_updates=0,
                metrics=row['metrics'], summary={row['sequence']: dict(metrics_percent=row['metrics'])}, gap=dict(overall=row['gap']), tracking_receipt=receipt_ref)
            for k in ('DO_PREPROC', 'predictions_GT_filtered', 'test_read', 'intercept_applied'): body[k] = False
            reports.append(dict(job=job, report=self.put('pose/state_aligned_training_a01/control/jobs/'+str(idx)+'/report.json', body)))
        self.put('pose/state_aligned_training_a01/control/manifest.json', dict(schema='state_aligned_tracking_manifest_v1',
            status='complete180_state_aligned_tracking_and_evaluation', config_sha256=cfg_ref['sha256'], reports=reports))
        return cfg_ref, self.exp/'control'

    def test_end_to_end_small_metadata_csv_counts_and_no_overwrite(self):
        cfg, control = self.build(); output = self.exp/'analysis'
        result = a.analyze(cfg['path'], control, output)
        self.assertEqual(result['status'], a.STATUS)
        for filename, count in [('all_results.csv', 360), ('all_paired_cells.csv', 360), ('all_paired_gaps.csv', 360),
                                ('all_paired_matches.csv', 48), ('absolute_matches.csv', 48), ('absolute_panels.csv', 12)]:
            with (output/filename).open(encoding='utf-8-sig', newline='') as f: self.assertEqual(len(list(csv.DictReader(f))), count)
        report = json.loads((output/'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['gap_events_counted_once_per_source'], 3690)
        self.assertEqual(report['comparisons'][a.COMPARISONS[0]]['original_heldout']['AssA']['mean_delta_pp'], -3)
        self.assertEqual(report['absolute_panels'][0]['condition'], 'new_R')
        self.assertFalse(report['test_read'])
        with self.assertRaises(ValueError): a.analyze(cfg['path'], control, output)

    def test_tampered_new_metric_cannot_analyze(self):
        cfg, control = self.build()
        path = control/'jobs/0/report.json'; body = json.loads(path.read_text(encoding='utf-8')); body['metrics']['AssA'] = 99
        path.write_text(a.canonical(body), encoding='utf-8')
        with self.assertRaises(ValueError): a.analyze(cfg['path'], control, self.exp/'analysis')
        self.assertFalse((self.exp/'analysis').exists())


if __name__ == '__main__': unittest.main()
