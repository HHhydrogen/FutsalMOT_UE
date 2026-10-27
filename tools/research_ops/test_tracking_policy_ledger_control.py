"""根控制器的场内平均、分母及未知状态合同，不运行真实研究数据。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('ledger_control_test', Path(__file__).with_name('tracking_policy_ledger_control.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def fixture():
    lengths = [750, 750, 750, 450, 675, 725, 775, 701, 550, 700, 888, 451]
    panels = dict(original_heldout=['s0', 's1', 's2'], old_external=['s3', 's4'], seven_observed=['s'+str(i) for i in range(5, 12)])
    sources, summaries = {}, {}
    for i, frames in enumerate(lengths):
        sequence = 's'+str(i); sources[sequence] = dict(frames=frames)
        rows = []
        for method, n in [('official_ocsort', 1), ('PT_bbox', 1), ('strong_motion_RS', 3 if i < 3 else 9)]:
            for j in range(n):
                count = j+1 if method == 'strong_motion_RS' else 2
                rows.append(dict(unit_id=f'{sequence}_{method}_{j}', method=method, sequence=sequence, fold='f', seed=j,
                    source_frames=frames, output_rows=count, frames_with_any_output=1, emitted_trajectory_count=1,
                    emission_gap_count=0, same_ID_reemission_after_gap_count=0, raw_geometric_proxy_score_unknown=0,
                    output_to_raw={'mutual_unique': count}, output_to_GT={'mutual_unique': count},
                    raw_geometric_proxy_score_buckets={'above_0.6': count},
                    mot={'path': 'old.txt', 'sha256': '0'*64}, internal_lifecycle='unknown_from_MOT'))
        summaries[sequence] = dict(source_denominator_copies=1, cache_stream_passes=1,
            source_counts=dict(source_frames=frames, raw_detections=149245 if i == 0 else 0,
                               GT_rows=113009 if i == 0 else 1), score_buckets={}, raw_eligibility={}, GT_opportunities={}, units=rows)
    cfg = dict(sources=sources, panels=panels, sequence_order=list(sources), expected_unique_GT_rows=113020,
               inventory={}, static_policy={})
    return cfg, summaries


class Contracts(unittest.TestCase):
    def run_summary(self, cfg, summaries):
        with tempfile.TemporaryDirectory() as directory, patch.object(m, 'ref', side_effect=lambda p: dict(path=str(p), sha256='0'*64)):
            return m.summarize(cfg, summaries, Path(directory))

    def test_unique_denominators_and_within_match_means(self):
        cfg, summaries = fixture(); result = self.run_summary(cfg, summaries)
        self.assertEqual(result['counts'], dict(sources=12, source_frames=8165, raw_detections=149245,
            source_GT_rows=113020, units=114, unit_frames=76315, method_matches=36))
        old = next(r for r in result['panel_summary'] if r['method'] == 'strong_motion_RS' and r['panel'] == 'original_heldout')
        self.assertAlmostEqual(old['mean_output_rows_per_source_frame'], 2/750)
        self.assertFalse(result['hypothetical_threshold_policy_executed'])

    def test_missing_source_rejected(self):
        cfg, summaries = fixture(); summaries.pop('s0')
        with self.assertRaisesRegex(ValueError, '十二源缺项'): self.run_summary(cfg, summaries)

    def test_internal_lifecycle_cannot_be_invented(self):
        cfg, summaries = fixture(); summaries['s0']['units'][0]['internal_lifecycle'] = 'confirmed'
        with self.assertRaisesRegex(ValueError, '内部状态'): self.run_summary(cfg, summaries)

    def test_source_cannot_be_multiplied_by_training_units(self):
        cfg, summaries = fixture(); summaries['s0']['source_denominator_copies'] = 3
        with self.assertRaisesRegex(ValueError, '重复源分母'): self.run_summary(cfg, summaries)

    def test_consumed_failed_worker_is_joined_without_second_receive(self):
        service = m.Service.__new__(m.Service); service.task_failed = False; service.closed = False
        service.parent = Mock(); service.parent.poll.return_value = True
        service.parent.recv.return_value = dict(status='failed', traceback='actual_failure')
        service.process = Mock(); service.process.pid = 12; service.process.exitcode = 0
        service.process.is_alive.return_value = False
        with self.assertRaisesRegex(ValueError, 'actual_failure'): service.receive()
        self.assertTrue(service.task_failed)
        evidence = service.join_failed()
        service.parent.recv.assert_called_once(); service.process.join.assert_called_once_with(30)
        self.assertTrue(evidence['process_exited']); self.assertEqual(evidence['status'], 'failed_worker_partial_preserved_no_replay')


if __name__ == '__main__': unittest.main()
