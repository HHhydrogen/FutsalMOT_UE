"""原始CSV导出不得筛步、改UID/epoch或补造cache关闭记录。"""
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import export_pose_velocity_training_records as exporter


class Tests(unittest.TestCase):
    def ledger(self, group):
        real = [dict(window_uid='R'+str(i), domain='real', epoch=i//1000,
                     candidate_pairs=3, labelled_pairs=2, source_allocation='base_R') for i in range(3000)]
        synthetic = [dict(window_uid='S'+str(i), domain='synthetic', epoch=0,
                          candidate_pairs=4, labelled_pairs=1) for i in range(1000)]
        rows = []
        for i in range(1000):
            mixed = group != 'T_R'
            rows.append(dict(actual_update=i+1, update_index=i, loss=.5 if mixed else .4,
                real_loss=.4, synthetic_loss=.3 if mixed else None, learning_rates=[.001], grad_l2=.25,
                gradients_clipped=False, step_wall_seconds=.02, R_windows=3, S_windows=int(mixed),
                R_pairs=9, S_pairs=4*int(mixed), R_known_pairs=6, S_known_pairs=int(mixed),
                real=real[3*i:3*i+3], synthetic=synthetic[i:i+1] if mixed else []))
        self.chain(rows)
        return rows, dict(real=real, synthetic=synthetic)

    def chain(self, rows):
        chain = '0'*64
        for row in rows:
            row.pop('chain_sha256', None)
            chain = hashlib.sha256((chain+exporter.canonical(row)).encode()).hexdigest()
            row['chain_sha256'] = chain

    def test_all_steps_R_and_RS_actual_totals(self):
        for group in exporter.GROUPS:
            rows, table = self.ledger(group); counts, chain = exporter.validate_steps(rows, table, group)
            self.assertEqual(counts['R_windows'], 3000)
            self.assertEqual(counts['R_known_pairs'], 6000)
            self.assertEqual(counts['S_windows'], 0 if group == 'T_R' else 1000)
            self.assertEqual(chain, rows[-1]['chain_sha256'])

    def test_rehashed_wrong_epoch_pair_or_missing_loss_refuses(self):
        for field, value in [('grad_l2', float('nan')), ('learning_rates', []), ('R_known_pairs', 9)]:
            rows, table = self.ledger('T_RS'); rows[0][field] = value
            if field != 'grad_l2': self.chain(rows)
            with self.assertRaises(ValueError): exporter.validate_steps(rows, table, 'T_RS')
        rows, table = self.ledger('T_R'); rows[0]['real'] = deepcopy(rows[0]['real'])
        rows[0]['real'][0]['epoch'] = 4; self.chain(rows)
        with self.assertRaises(ValueError): exporter.validate_steps(rows, table, 'T_R')
        with self.assertRaises(ValueError): exporter.validate_steps(rows[:-1], table, 'T_R')

    def test_csv_round_trip_preserves_full_exposure_and_raw_null(self):
        rows, _ = self.ledger('T_R'); job = dict(fold='game4', seed=20261024, group='T_R')
        source = dict(initialization_sha256='init', method_state_sha256='state', protocol_sha256='protocol',
            run_directory='run', source_steps_path='source', source_steps_sha256='hash',
            source_run_receipt_sha256='receipt', source_training_complete_sha256='complete')
        value = exporter.step_csv_row(rows[0], job, source)
        buffer = io.StringIO(); writer = csv.DictWriter(buffer, fieldnames=exporter.CSV_FIELDS)
        writer.writeheader(); writer.writerow(value); buffer.seek(0)
        restored = next(csv.DictReader(buffer))
        self.assertEqual(json.loads(restored['raw_step_json']), rows[0])
        self.assertEqual(json.loads(restored['real']), rows[0]['real'])
        self.assertEqual(json.loads(restored['synthetic']), [])
        self.assertIsNone(json.loads(restored['synthetic_loss']))
        self.assertEqual(json.loads(restored['learning_rates']), [.001])

    def preflight_fixture(self, root):
        experiment = root/'pose/pose_velocity_learning_a01'; control = experiment/'control_a01'
        config = experiment/'training_frozen_a01/protocol.json'; budget = experiment/'postrun_audit_a02/actual_budget.json'
        for parent in (control, config.parent, budget.parent): parent.mkdir(parents=True)
        bundle = root/'code/frozen'; bundle.mkdir(parents=True)
        code = bundle/'entry.py'; code.write_text('# immutable fixture\n', encoding='utf-8')
        manifest = bundle/'manifest.json'; exporter.write_new(manifest, dict(files=[dict(path='entry.py', sha256=exporter.sha(code))]))
        cfg = dict(schema='bounded_velocity_recorded_training_protocol_v1', test116187_sealed=True,
            training_matrix=exporter.matrix(), parameters=dict(updates=1000, R_per_step=3, S_per_RS_step=1),
            bundle=str(bundle), bundle_manifest=exporter.ref(manifest))
        exporter.write_new(config, cfg)
        state = dict(status='complete27_bounded_velocity_training_wait_independent_audit_tracking', active=None,
            protocol_sha256=exporter.sha(config), completed_train=[dict(j, path='not_read_during_preflight') for j in exporter.matrix()])
        exporter.write_new(control/'driver_state.json', state)
        audit = dict(status=exporter.BUDGET_STATUS, protocol=exporter.ref(config),
            control_state=exporter.ref(control/'driver_state.json'), actual_totals=dict(updates=27000, R_windows=81000, S_windows=18000),
            complete_checkpoints_read_back=567, training_processes_absent=True, optimizer_replay=0,
            runs=[dict(j) for j in exporter.matrix()])
        exporter.write_new(budget, audit)
        return config, control, budget, experiment/'paper_training_archive_a01'

    def test_default_preflight_is_readonly_complete_budget_required_and_no_partial_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(exporter, 'RESEARCH', root), patch.object(exporter, 'EXPERIMENT', root/'pose/pose_velocity_learning_a01'):
                config, control, budget, output = self.preflight_fixture(root)
                flight = exporter.preflight(config, control, budget, output, exporter.sha(budget))[3]
                self.assertFalse(output.exists()); self.assertFalse(flight['model_loaded'])
                self.assertFalse(flight['tracking_metrics_read'])
                with self.assertRaises(ValueError): exporter.preflight(config, control, budget, output, 'changed')
                output.mkdir()
                with self.assertRaises(ValueError): exporter.preflight(config, control, budget, output)


if __name__ == '__main__':
    unittest.main()
