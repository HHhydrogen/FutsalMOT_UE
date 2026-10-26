"""新18组与逐步实际R/S曝光契约；不导入模型、不占用GPU。"""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('green_runtime_contract', Path(__file__).with_name('green_kit_runtime.py'))
runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
analysis_spec = importlib.util.spec_from_file_location('green_analysis_contract', Path(__file__).with_name('green_kit_analyze.py'))
analysis = importlib.util.module_from_spec(analysis_spec); analysis_spec.loader.exec_module(analysis)


class GreenTrainingBudget(unittest.TestCase):
    def test_full_matrix_and_equal_budget_reject_dropped_cell_or_changed_batch(self):
        config = dict(schema='green_kit_gated_control_v1', training_matrix=runtime.expected_matrix(),
                      parameters=deepcopy(runtime.PARAMETERS), test116187_sealed=True)
        runtime.validate_matrix(config)
        self.assertEqual(len(config['training_matrix']), 18)
        changed = deepcopy(config); changed['training_matrix'].pop()
        with self.assertRaises(ValueError):
            runtime.validate_matrix(changed)
        changed = deepcopy(config); changed['parameters']['R_per_step'] = 4
        with self.assertRaises(ValueError):
            runtime.validate_matrix(changed)
        changed = deepcopy(config); changed['test116187_sealed'] = False
        with self.assertRaises(ValueError):
            runtime.validate_matrix(changed)

    def fixture(self):
        table = dict(real=[dict(window_uid='R%d' % (i % 1000), epoch=i//1000) for i in range(3000)],
                     synthetic=[dict(window_uid='S%d' % i, epoch=0) for i in range(1000)])
        rows = [dict(update_index=i, actual_update=i+1, real_windows=3, synthetic_windows=1,
                     real=table['real'][i*3:i*3+3], synthetic=table['synthetic'][i:i+1]) for i in range(1000)]
        return table, rows

    def sign(self, rows):
        chain = '0'*64; output = []
        for record in rows:
            chain = hashlib.sha256((chain+runtime.canonical(record)).encode()).hexdigest()
            output.append(dict(record, chain_sha256=chain))
        return output, chain

    def test_complete_exposure_chain_passes_but_partial_is_not_replayed(self):
        table, rows = self.fixture(); logs, chain = self.sign(rows)
        self.assertEqual(runtime.audit_log_chain(logs, table), chain)
        with self.assertRaisesRegex(ValueError, '预算不足'):
            runtime.audit_log_chain(logs[:-1], table)

    def test_validly_resigned_reordered_real_UIDs_are_rejected(self):
        table, rows = self.fixture(); rows[0]['real'] = deepcopy(rows[0]['real'])
        rows[0]['real'][0], rows[0]['real'][1] = rows[0]['real'][1], rows[0]['real'][0]
        logs, _ = self.sign(rows)
        with self.assertRaisesRegex(ValueError, 'UID顺序'):
            runtime.audit_log_chain(logs, table)

    def test_validly_resigned_extra_S_or_wrong_actual_update_is_rejected(self):
        table, rows = self.fixture(); rows[4]['synthetic'] = rows[4]['synthetic']*2
        logs, _ = self.sign(rows)
        with self.assertRaises(ValueError):
            runtime.audit_log_chain(logs, table)
        table, rows = self.fixture(); rows[4]['actual_update'] = 7
        logs, _ = self.sign(rows)
        with self.assertRaises(ValueError):
            runtime.audit_log_chain(logs, table)

    def test_macro_gain_does_not_hide_two_negative_seeds(self):
        reference = {(f, s): dict(AssA=70., HOTA=60., IDF1=80.) for f in runtime.GAMES for s in runtime.SEEDS}
        gains = {runtime.SEEDS[0]: 4., runtime.SEEDS[1]: -1., runtime.SEEDS[2]: -1.}
        values = {(f, s): dict(AssA=70.+gains[s], HOTA=60., IDF1=80.) for f in runtime.GAMES for s in runtime.SEEDS}
        report = analysis.contrast(values, reference)
        self.assertGreater(report['macro_mean_pp']['AssA'], .5)
        self.assertEqual(len(report['cells']), 9)
        self.assertFalse(report['checks']['at_least_two_seed_macro_positive'])
        self.assertFalse(report['passed'])

    def test_AssA_gain_cannot_override_HOTA_decline(self):
        reference = {(f, s): dict(AssA=70., HOTA=60., IDF1=80.) for f in runtime.GAMES for s in runtime.SEEDS}
        values = {(f, s): dict(AssA=70.6, HOTA=59.9, IDF1=80.) for f in runtime.GAMES for s in runtime.SEEDS}
        report = analysis.contrast(values, reference)
        self.assertFalse(report['passed'])
        self.assertFalse(report['checks']['HOTA_nonnegative'])


if __name__ == '__main__':
    unittest.main()
