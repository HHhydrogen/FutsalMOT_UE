"""仅准入控制/原ID与评价比较CPU夹具，不冒充真实worker运行。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import association_worker_admission as admission


class Admission(unittest.TestCase):
    def test_resource_guard_preserves_dynamic_RAM_and_commit(self):
        cfg = dict(reserve_RAM_bytes=8, reserve_commit_bytes=6, startup_estimate_bytes=1)
        self.assertTrue(admission.enough_memory(dict(available_RAM_bytes=11, commit_available_bytes=6), cfg, 3))
        self.assertFalse(admission.enough_memory(dict(available_RAM_bytes=10, commit_available_bytes=6), cfg, 3))
        self.assertFalse(admission.enough_memory(dict(available_RAM_bytes=20, commit_available_bytes=5), cfg))

    def test_exclusive_receipts_reject_partial_overwrite(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'new.json'
            admission.write_new(path, dict(status='complete'))
            with self.assertRaises(FileExistsError):
                admission.write_new(path, dict(status='fake'))

    def test_raw_metric_negative_counts_and_gap_must_all_be_equal(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); actual = root / 'actual'; reference = root / 'original/metric'
            value = {key: 0 for key in ('frames', 'GT_rows')}
            value.update(job={'job_id':'A'}, summary={'AssA':-1.}, raw_results={'IDSW':3}, recovery={'failed':2},
                registry={'sha256':'old'}, DO_PREPROC=False, predictions_GT_filtered=False,
                GT_ID0_original=True, numerical_source_sha256={'source':'fixed'})
            for path in (actual / 'report.json', reference / 'report.json'):
                admission.write_new(path, value)
            self.assertTrue(admission.compare_metric(actual, reference.parent)['all_raw_metrics_counts_and_gap_equal'])
            value['summary']['AssA'] = 0
            (actual / 'report.json').write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaises(ValueError): admission.compare_metric(actual, reference.parent)

    def test_original_ID_MOT_not_renumbered_to_hide_state_leak(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); actual = root / 'actual'; original = root / 'original'
            value = {key: None for key in ('frames', 'tracked_rows', 'frame_counts', 'mot_sha256', 'cache', 'binding',
                'audit', 'scope_adapter', 'input_adapter_audit', 'pose_enabled', 'inference_shape_shuffle', 'original_quality_gate')}
            value['job'] = dict(job_id='A', sequence='clip')
            for output in (actual, original / 'tracking'):
                admission.write_new(output / 'receipt.json', value)
                (output / 'data').mkdir()
                (output / 'data/clip.txt').write_text('1,1,0,0,2,2,.5,-1,-1,-1\n', encoding='utf-8')
            self.assertTrue(admission.compare_track(actual, original)['original_ID_MOT_equal'])
            (actual / 'data/clip.txt').write_text('1,2,0,0,2,2,.5,-1,-1,-1\n', encoding='utf-8')
            with self.assertRaises(ValueError): admission.compare_track(actual, original)


if __name__ == '__main__':
    unittest.main()
