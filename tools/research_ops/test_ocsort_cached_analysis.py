"""OC每场只有一次评价；历史训练面板先场内均值，不伪造9个独立OC样本。"""
from copy import deepcopy
import unittest
import ocsort_cached_analysis as analysis


class Tests(unittest.TestCase):
    def fixture(self):
        panels = dict(original_heldout=list(analysis.OLD), old_external=['E1', 'E2'],
                      seven_observed=['V'+str(i) for i in range(7)])
        references, oc = [], []
        for seq in analysis.panels_map(panels):
            oc.append(dict(sequence=seq, fold=None, seed=None, metrics={k: 1. for k in analysis.METRICS},
                recovery=dict(total_events=10, same_prediction_ID_recovered=3, recovery_rate=.3),
                report=dict(path='OC-'+seq, sha256='hash')))
            for baseline in analysis.BASELINES:
                cells = {(None, None)} if baseline == 'PT_bbox' else analysis.allowed_cells(seq)
                for fold, seed in cells:
                    references.append(dict(baseline=baseline, sequence=seq, fold=fold, seed=seed,
                        metrics={k: 2. for k in analysis.METRICS},
                        recovery=dict(total_events=10, same_prediction_ID_recovered=4, recovery_rate=.4),
                        report=dict(path=f'ref-{baseline}-{seq}-{fold}-{seed}', sha256='hash')))
        return panels, oc, references

    def test_12_OC_not_replicated_as90_independent_training_cells(self):
        panels, oc, refs = self.fixture(); pairs = analysis.paired_matches(oc, refs, panels)
        self.assertEqual(len(oc), 12); self.assertEqual(len(refs), 192); self.assertEqual(len(pairs), 36)
        self.assertTrue(all(r['OC_evaluations'] == 1 for r in pairs))
        self.assertTrue(all(r['delta_pp']['AssA'] == -1. for r in pairs))
        self.assertEqual({r['reference_training_cells'] for r in pairs if r['baseline'] == 'T_RS'}, {3, 9})

    def test_missing_duplicate_OC_or_reference_seed_refuses(self):
        panels, oc, refs = self.fixture()
        for bad_oc, bad_refs in ((oc[:-1], refs), (oc+[oc[0]], refs), (oc, refs[:-1]), (oc, refs+[refs[0]])):
            with self.assertRaises(ValueError): analysis.paired_matches(bad_oc, bad_refs, panels)
        oc[0]['seed'] = 20261024
        with self.assertRaises(ValueError): analysis.paired_matches(oc, refs, panels)

    def test_three_panels_use_match_N3_2_7_for_all_negative_results(self):
        panels, oc, refs = self.fixture(); pairs = analysis.paired_matches(oc, refs, panels)
        def description(values): return dict(n=len(values), mean=sum(values.values())/len(values))
        metrics, gaps = analysis.describe(pairs, panels, description)
        self.assertEqual([metrics['strong_motion_RS'][p]['AssA']['n'] for p in analysis.PANELS], [3, 2, 7])
        self.assertTrue(all(metrics['T_RS'][p]['AssA']['mean'] == -1. for p in analysis.PANELS))
        self.assertEqual(len(metrics)*len(analysis.PANELS)*len(analysis.METRICS), 45)
        self.assertEqual([gaps['PT_bbox'][p]['n'] for p in analysis.PANELS], [3, 2, 7])

    def test_all_event_gap_denominator_and_zero_null_are_preserved(self):
        panels, oc, refs = self.fixture(); seq = oc[0]['sequence']
        for r in oc+refs:
            if r['sequence'] == seq:
                r['recovery'] = dict(total_events=0, same_prediction_ID_recovered=0, recovery_rate=None)
        pairs = analysis.paired_matches(oc, refs, panels)
        self.assertTrue(all(r['gap']['delta_recovery_rate_pp'] is None for r in pairs if r['sequence'] == seq))
        oc[0]['recovery']['recovery_rate'] = 0.
        with self.assertRaises(ValueError): analysis.paired_matches(oc, refs, panels)

    def test_reference_semantics_reject_pureR_C_and_pose_off(self):
        panels, _, _ = self.fixture()
        cfg = dict(panels=panels, sources={s: dict(frames=750, cache=dict(path=s, sha256='cache')) for s in analysis.panels_map(panels)},
                   source_tracking_config=dict(sha256='old'), source_seven_tracking_config=dict(sha256='seven'))
        job = dict(sequence='E1', kind='new_RS', method='motion', pool='balanced')
        report = dict(job=job, frames=750, protocol_sha256='old')
        analysis.check_reference_record(dict(body=report), 'strong_motion_RS', 'E1', cfg, 'velocity')
        bad = dict(report, job=dict(job, kind='pure_R'))
        with self.assertRaises(ValueError): analysis.check_reference_record(dict(body=bad), 'strong_motion_RS', 'E1', cfg, 'velocity')
        bad = dict(job=dict(sequence='V0', kind='learned', method='motion', group='C'), frames=750, protocol_sha256='seven')
        with self.assertRaises(ValueError): analysis.check_reference_record(dict(body=bad), 'strong_motion_RS', 'V0', cfg, 'velocity')
        bad = dict(job=dict(sequence='E1', kind='new', group='T_RS', pose_enabled=False), frames=750,
                   schema='bounded_velocity513_trackeval_gap_v1', source_cache=cfg['sources']['E1']['cache'], protocol_sha256='velocity')
        with self.assertRaises(ValueError): analysis.check_reference_record(dict(body=bad), 'T_RS', 'E1', cfg, 'velocity')


if __name__ == '__main__':
    unittest.main()
