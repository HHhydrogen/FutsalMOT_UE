"""OC .25终验针对CPU合同：唯一参数、原AST/namespace、全负配对与描述区间。"""
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_ocsort_threshold_results as verify
import verify_ocsort_cached_results as base


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.patches = [patch.object(verify, 'R', self.root), patch.object(base, 'R', self.root)]
        for value in self.patches: value.start()
    def tearDown(self):
        for value in self.patches: value.stop()
        self.temp.cleanup()

    def test_only_det_thresh_change_no_Byte_inertia_or_threshold_search(self):
        old = dict(verify.PARAMETERS, det_thresh=.6); verify.one_factor(old, verify.PARAMETERS)
        for change in [dict(use_byte=True), dict(inertia=.3), dict(det_thresh=.25001), dict(min_hits=1)]:
            with self.assertRaises(ValueError): verify.one_factor(old, dict(verify.PARAMETERS, **change))
        self.assertEqual(old['det_thresh'], .6)

    def test_source_scope_and_every_other_policy_must_remain_exact(self):
        keys = ('panels', 'registries', 'official_manifest', 'dependency_manifest', 'worker_profile', 'protected_GT_paths',
            'sequence_order', 'gate_sequences', 'source_velocity_protocol', 'source_velocity_analysis', 'old_five_analysis',
            'ABC_analysis', 'interval_source', 'expected_GT_rows', 'expected_ID0_present')
        old = {k: {'actual_source': k} for k in keys}
        old.update(parameters=dict(verify.PARAMETERS, det_thresh=.6), sources={str(i): dict(frames=750 if i < 3 else 657) for i in range(12)})
        old['sources']['11']['frames'] += 2  # 2250+9*657+2=8165
        new = deepcopy(old); new['parameters'] = verify.PARAMETERS
        verify.source_contract(old, new)
        for key in keys:
            bad = deepcopy(new); bad[key] = {'changed': key}
            with self.assertRaises(ValueError): verify.source_contract(old, bad)

    def source_bundle(self, name, runtime_name, body):
        folder = self.root/name; (folder/'tools/research_ops').mkdir(parents=True)
        files = []
        for filename, source in [(runtime_name, body), ('ocsort_cached_admission.py', '# 原准入夹具\n')]:
            target = folder/'tools/research_ops'/filename; target.write_text(source, encoding='utf-8')
            files.append(dict(path='tools/research_ops/'+filename, sha256=verify.sha(target)))
        manifest = folder/'bundle_manifest.json'; manifest.write_text(json.dumps(dict(files=files)), encoding='utf-8')
        return dict(bundle=str(folder), bundle_manifest=verify.ref(manifest))

    def test_copied_numeric_AST_is_identical_and_original_sources_stay_unchanged(self):
        original = self.source_bundle('old', 'ocsort_cached_runtime.py', 'def _track_frames_impl(a):\n    return a+1\n')
        current = self.source_bundle('new', 'ocsort_threshold_runtime.py', 'def _track_frames_impl(a):\n    return a+1\n')
        proof = verify.copied_function_contract(original, current)
        self.assertFalse(proof['original_module_globals_modified']); self.assertTrue(proof['copied_function_AST_identical'])
        old_sha = verify.sha(proof['source_runtime']['path'])
        target = Path(current['bundle'])/'tools/research_ops/ocsort_threshold_runtime.py'
        target.write_text('def _track_frames_impl(a):\n    return a+2\n', encoding='utf-8')
        manifest = Path(current['bundle_manifest']['path']); value = json.loads(manifest.read_text(encoding='utf-8'))
        value['files'][0]['sha256'] = verify.sha(target); manifest.write_text(json.dumps(value), encoding='utf-8'); current['bundle_manifest'] = verify.ref(manifest)
        with self.assertRaises(ValueError): verify.copied_function_contract(original, current)
        self.assertEqual(verify.sha(proof['source_runtime']['path']), old_sha)

    def test_backend_preserves_default_provenance_and_explicit_effective_override(self):
        contract = dict(proof='fixed_AST'); cfg = dict(official_manifest=dict(path='official', sha256='sha'))
        backend = dict(manifest=cfg['official_manifest'], effective_parameters=verify.PARAMETERS,
            parameter_override='predeclared_single_factor_det_thresh_0.6_to_0.25_not_official_default',
            single_factor_override=dict(parameter='det_thresh', before=.6, after=.25, predeclared=True, official_default=False),
            single_factor_contract=contract, det_thresh_source='official_CLI_track_thresh_default_0.6',
            commit='8462e7e729a93ccd3bd995c0a79a890336cb3a0b', numerical_source_modified=False,
            actual_assignment_backend='lap.lapjv', scipy_assignment_fallback_allowed=False,
            no_demo_min_area_or_aspect_filter=True, full_demo_pipeline_reproduction=False, paper2023_byte_reproduction=False,
            native_Kalman_precision='original_float64_matrices_and_operations_not_cast_to_FP32')
        verify.backend_contract(backend, cfg, contract)
        for key, value in [('effective_parameters', dict(verify.PARAMETERS, det_thresh=.6)), ('det_thresh_source', 'official_default_.25'),
                           ('numerical_source_modified', True), ('actual_assignment_backend', 'scipy')]:
            bad = deepcopy(backend); bad[key] = value
            with self.assertRaises(ValueError): verify.backend_contract(bad, cfg, contract)

    def records(self):
        panels = dict(original_heldout=list(base.OLD), old_external=['E1', 'E2'], seven_observed=['V'+str(i) for i in range(7)])
        target, previous, refs = [], [], []
        for panel in verify.PANELS:
            for seq in panels[panel]:
                def record(value, name): return dict(sequence=seq, fold=None, seed=None, metrics={k: value for k in verify.METRICS},
                    recovery=dict(total_events=10, same_prediction_ID_recovered=3 if value == 1 else 4, recovery_rate=.3 if value == 1 else .4),
                    report=dict(path=name+'-'+seq, sha256='sha'))
                target.append(record(1., '025')); previous.append(record(2., '06'))
                for baseline in ('PT_bbox', 'strong_motion_RS', 'T_RS'):
                    expected = [(None, None)] if baseline == 'PT_bbox' else [(f, s) for f in ((base.OLD[seq],) if seq in base.OLD else base.FOLDS) for s in base.SEEDS]
                    for fold, seed in expected:
                        value = record(2., baseline); value.update(baseline=baseline, fold=fold, seed=seed); refs.append(value)
        return panels, target, previous, refs

    def test_all48_negative_pairs_no_OC_fold_replication_and_60_plus12_intervals(self):
        panels, target, previous, refs = self.records(); rows = verify.paired_rows(target, previous, refs, panels, base)
        self.assertEqual(len(rows), 48); self.assertTrue(all(v['OC025_evaluations'] == 1 and v['delta']['AssA'] == -1 for v in rows))
        self.assertTrue(all(not v['reference_has_training_panel'] for v in rows if v['baseline'] in ('OC06', 'PT_bbox')))
        def interval(values): return dict(n=len(values), negative=sum(x < 0 for x in values.values()), mean=sum(values.values())/len(values))
        metrics, gaps = verify.intervals(rows, panels, interval)
        self.assertEqual([metrics['OC06'][p]['AssA']['n'] for p in verify.PANELS], [3, 2, 7])
        self.assertEqual(len(metrics)*3*5, 60); self.assertEqual(len(gaps)*3, 12)
        for bad in (previous[:-1], previous+[previous[0]]):
            with self.assertRaises(ValueError): verify.paired_rows(target, bad, refs, panels, base)
        # 零gap完整保留null，不填0或丢掉该比赛。
        for row in target+previous+refs:
            if row['sequence'] == 'E1': row['recovery'] = dict(total_events=0, recovery_rate=None)
        rows = verify.paired_rows(target, previous, refs, panels, base); _, gaps = verify.intervals(rows, panels, interval)
        self.assertIsNone(gaps['OC06']['old_external']['Student_t_95CI'])
        self.assertEqual(gaps['OC06']['old_external']['zero_event_matches_retained_null'], ['E1'])

    def test_CSV_boolean_null_negative_and_source_reference_are_all_checked(self):
        path = self.root/'pair.csv'
        expected = [dict(reference_has_training_panel=False, difference=-1.5, gap=None, reference=dict(path='original', sha256='s'))]
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(expected[0])); writer.writeheader()
            writer.writerow(dict(reference_has_training_panel=False, difference=-1.5, gap='', reference=json.dumps(expected[0]['reference'])))
        verify.check_csv(verify.ref(path), expected, base)
        expected[0]['reference_has_training_panel'] = True
        with self.assertRaises(ValueError): verify.check_csv(verify.ref(path), expected, base)

    def test_CIM_exact_new_script_names_and_spawn_parent_not_old_PID_only(self):
        now = datetime.now(timezone.utc).isoformat(); state = dict(parent_pid=77, created_utc=now)
        unrelated = dict(ProcessId=77, Name='python.exe', CommandLine='python other.py', CreationUtc=now)
        self.assertEqual(verify.blocked_processes([unrelated], state), [])
        for command in ('python oc sort.py', 'python verify_ocsort_threshold_results.py', 'python test_ocsort_threshold_control.py'):
            self.assertEqual(verify.blocked_processes([dict(unrelated, CommandLine=command)], state), [])
        for command in ('python D:/bundle/ocsort_threshold_control.py', 'python D:/bundle/ocsort_threshold_admission.py',
                        'python -c "spawn_main(parent_pid=77,pipe_handle=1)"'):
            self.assertEqual(len(verify.blocked_processes([dict(unrelated, CommandLine=command)], state)), 1)


if __name__ == '__main__': unittest.main()
