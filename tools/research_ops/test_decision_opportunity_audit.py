"""只用750帧微型日志和元数据夹具核流式join、来源等权及资源调度。"""
from concurrent.futures import Future
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import decision_opportunity_audit as a
from test_decision_opportunity_core import fixture


class StreamContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.path_patch = patch.object(a, 'safe', lambda v: Path(v)); self.path_patch.start()
        self.job = dict(job_id='fixture0', regime='R', fold='game6', sequence='SNMOT-060', seed=20261024)
        self.cfg = dict(control_root=str(self.root/'control'), _protocol=dict(path='fixture-protocol', sha256='a'*64))

    def tearDown(self): self.path_patch.stop(); self.tmp.cleanup()

    def put(self, name, value):
        path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(a.canonical(value), encoding='utf-8'); return a.ref(path)

    def compressed(self, name, values, declared=None):
        path = self.root/name
        with gzip.open(path, 'xt', encoding='utf-8') as stream:
            for value in values: stream.write(a.canonical(value)+'\n')
        return dict(**a.ref(path), rows=len(values) if declared is None else declared)

    def source(self, *, annotation_mutation=None, frame_mutation=None, declared=None):
        frame, annotations = fixture()
        blank = deepcopy(frame)
        for stage in blank['stages']:
            stage.update(rows=[], track_ids=[], candidates=[], candidate_UIDs=[], reference_cost=[], bbox_base_cost=[], active=[], assignments=[])
            stage['gates'] = stage['enabled'] = None if stage['stage'] == 'low_score' else []
        frames = [dict(deepcopy(blank), frame_number=i) for i in range(1, 751)]; frames[3] = frame
        if annotation_mutation: annotation_mutation(annotations)
        if frame_mutation: frame_mutation(frames)
        fl = self.compressed('frames.gz', frames); al = self.compressed('annotations.gz', annotations, declared)
        observe = self.put('observe.json', dict(job=self.job, frames=750, frames_log=fl))
        posthoc = self.put('annotation.json', dict(job=self.job, total_frames=750, observe=observe, new_solver_calls=0, all_rows=al))
        return dict(job=self.job, observe=observe, posthoc=posthoc)

    def test_all750_frames_consumed_one_row_exact_and_zero_execution_boundaries(self):
        unit = self.source(); result = a.read(a.job_run(self.cfg, unit))
        self.assertEqual((result['frames'], result['stages'], result['row_count']), (750, 2250, 1))
        self.assertEqual(sum(result['first_stop'].values()), 1)
        self.assertEqual(result['first_stop']['actual_correct'], 1)
        self.assertTrue(all(value == 0 for key, value in result['first_stop'].items() if key != 'actual_correct'))
        self.assertEqual(result['protocol'], self.cfg['_protocol'])
        self.assertEqual(result['flags']['local_opportunity']['true'], 1)
        for key in ('new_optimizer_updates', 'new_model_forwards', 'new_tracking', 'new_solver_calls', 'new_TrackEval'):
            self.assertEqual(result[key], 0)
        self.assertFalse(result['test_read'])
        self.assertEqual(len(list(a.rows(result['ledger']))), 1)
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)

    def test_missing_annotation_rejected_without_success_receipt(self):
        unit = self.source(annotation_mutation=lambda rows: rows.clear())
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)
        self.assertFalse((self.root/'control/units/fixture0/receipt.json').exists())

    def test_duplicate_annotation_rejected(self):
        unit = self.source(annotation_mutation=lambda rows: rows.append(deepcopy(rows[0])))
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)

    def test_extra_future_annotation_and_wrong_declared_rowcount_rejected(self):
        unit = self.source(annotation_mutation=lambda rows: rows.append(dict(deepcopy(rows[0]), frame_number=751)))
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)

    def test_compressed_declared_rowcount_cannot_hide_rows(self):
        unit = self.source(declared=2)
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)

    def test_frame_gap_or_duplicate_rejected(self):
        unit = self.source(frame_mutation=lambda frames: frames[200].update(frame_number=200))
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)

    def test_stream_exhaustion_checks_last_frame_not_only_first_nonempty(self):
        unit = self.source(frame_mutation=lambda frames: frames.pop())
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)

    def test_stream_checksum_change_rejected(self):
        unit = self.source(); observe = a.read(unit['observe'])
        with Path(observe['frames_log']['path']).open('ab') as stream: stream.write(b'changed')
        with self.assertRaises(ValueError): a.job_run(self.cfg, unit)


def summary_units():
    sequences = ('SNMOT-060', 'SNMOT-097', 'SNMOT-151'); folds = ('game4', 'game6', 'game9'); units = []
    for regime in ('R', 'RS'):
        for seq, heldout in zip(sequences, folds):
            for fold in folds:
                if fold == heldout: continue
                index = len(units); rowcount = 15000 if index < 11 else 15118
                # 不同fold分母悬殊；先均两个比例，不能pool计数。
                true, false = (1, 9) if len(units) % 2 == 0 else (900, 100)
                units.append(dict(schema='decision_opportunity_unit_v1', status='complete',
                    job=dict(job_id='j'+str(index), regime=regime, sequence=seq, fold=fold, seed=20261024),
                    frames=750, row_count=rowcount, first_stop=dict(actual_correct=rowcount),
                    flags=dict(local_opportunity=dict(true=true, false=false, null=rowcount-true-false))))
    return dict(sequences=sequences, _protocol={'path': 'fixture', 'sha256': 'a'*64}), units


class StatisticsContracts(unittest.TestCase):
    def test_complete180118_denominator_and_two_fold_then_three_source_mean(self):
        cfg, units = summary_units()
        with patch.object(a, 'read', lambda value: units[value]): result = a.summarize(cfg, list(range(12)))
        self.assertEqual((result['absolute_frames'], result['unique_source_frames'], result['stages'], result['rows']), (9000, 2250, 27000, 180118))
        self.assertEqual(result['first_stop_totals']['actual_correct'], 180118)
        for regime in ('R', 'RS'):
            stat = result['descriptions'][regime]['flags:local_opportunity']
            self.assertEqual(stat['source_rates'], dict.fromkeys(cfg['sequences'], 50))
            self.assertEqual(stat['mean_rate_pp'], 50)
            self.assertEqual(stat['n_independent_sources'], 3)
            self.assertEqual(stat['Student_t_95CI'], [50, 50])

    def test_missing_one_fold_denominator_preserves_source_null_CI_null(self):
        cfg, units = summary_units(); units[0]['flags']['local_opportunity'] = dict(true=0, false=0, null=15000)
        with patch.object(a, 'read', lambda value: units[value]): result = a.summarize(cfg, list(range(12)))
        stat = result['descriptions']['R']['flags:local_opportunity']
        self.assertIsNone(stat['source_rates']['SNMOT-060'])
        self.assertEqual(stat['n_independent_sources'], 2)
        self.assertIsNone(stat['Student_t_95CI']); self.assertIsNone(stat['percentile_match_bootstrap_95CI'])
        self.assertEqual(stat['leave_one_source_out_mean'], {})

    def test_wrong180118_or750_denominators_rejected(self):
        cfg, units = summary_units(); units[0]['row_count'] -= 1
        with patch.object(a, 'read', lambda value: units[value]):
            with self.assertRaises(ValueError): a.summarize(cfg, list(range(12)))
        cfg, units = summary_units(); units[0]['frames'] -= 1
        with patch.object(a, 'read', lambda value: units[value]):
            with self.assertRaises(ValueError): a.summarize(cfg, list(range(12)))

    def test_three_source_intervals_seed_deterministic_and_LOO(self):
        result = a.describe({'s0': 10., 's1': 30., 's2': 80.})
        self.assertEqual(result, a.describe({'s0': 10., 's1': 30., 's2': 80.}))
        self.assertEqual(result['mean_rate_pp'], 40.)
        self.assertEqual(result['leave_one_source_out_mean'], dict(s0=55., s1=45., s2=20.))
        self.assertEqual(a.quantile([0, 10, 20, 30], .25), 7.5)


class FakeProcess:
    def __init__(self, pid, exitcode=0, alive=False): self.pid, self.exitcode, self.alive = pid, exitcode, alive
    def is_alive(self): return self.alive


class ResourceContracts(unittest.TestCase):
    def test_dispatch_reserves_RAM_commit_for_each_inflight_and_two_workers(self):
        with tempfile.TemporaryDirectory() as temp:
            exp = Path(temp)/'experiment'; exp.mkdir(); out = exp/'control'; submitted = []; wait_sizes = []; sleeps = []
            cfg = dict(phase='formal', control_root=str(out), units=[dict(job=dict(job_id=str(i))) for i in range(12)],
                reserve_RAM_bytes=8*1024**3, reserve_commit_bytes=6*1024**3, inflight_reserve_bytes=3*1024**3)
            snapshots = [dict(available_RAM_bytes=8*1024**3, commit_available_bytes=100*1024**3),
                         dict(available_RAM_bytes=100*1024**3, commit_available_bytes=6*1024**3),
                         dict(available_RAM_bytes=11*1024**3, commit_available_bytes=9*1024**3)]
            def snapshot(): return snapshots.pop(0) if snapshots else dict(available_RAM_bytes=100*1024**3, commit_available_bytes=100*1024**3)
            class Pool:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs; self.assert_count = kwargs['max_workers']
                    self._processes = {i: FakeProcess(i) for i in range(kwargs['max_workers'])}
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def submit(self, function, config, unit):
                    submitted.append(unit['job']['job_id']); future = Future(); future.set_result(dict(worker_pid=123)); return future
            def wait_all(active, **kwargs): wait_sizes.append(len(active)); return set(active), set()
            with patch.object(a, 'safe', lambda value: Path(value)), patch.object(a, 'EXP', exp), \
                 patch.object(a, 'resources', lambda config: SimpleNamespace(resource_snapshot=snapshot)), \
                 patch.object(a, 'ProcessPoolExecutor', Pool), patch.object(a, 'wait', wait_all), \
                 patch.object(a, 'read', lambda value: value), patch.object(a, 'ref', lambda path: dict(path=str(path), sha256='a'*64)), \
                 patch.object(a, 'summarize', lambda config, refs: dict(fixture=True)), patch.object(a.time, 'sleep', lambda value: sleeps.append(value)):
                state = a.execute(exp/'fixture-config.json', cfg)
            self.assertEqual(state['status'], a.STATUS)
            self.assertEqual(submitted, [str(i) for i in range(12)])
            self.assertEqual(len(sleeps), 2)
            self.assertEqual(wait_sizes[0], 1)
            self.assertEqual(max(wait_sizes), 2)
            self.assertEqual(len(state['completed']), 12)
            self.assertEqual(len(state['worker_exits']), 2)
            self.assertTrue(all(p['process_exited'] and p['exit_code'] == 0 for p in state['worker_exits']))

    def test_inherit750_success_submits_only11_and_preserves_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            exp = Path(temp)/'experiment'; exp.mkdir(); submitted = []
            units = [dict(job=dict(job_id=str(i)), observe=dict(path='observe'+str(i)), posthoc=dict(path='posthoc'+str(i))) for i in range(12)]
            body = dict(status='complete', job=units[0]['job'], observe=units[0]['observe'], posthoc=units[0]['posthoc'],
                frames=750, row_count=1, ledger=dict(path='unchanged-success-ledger', rows=1), worker_pid=1)
            inherited = dict(path='successful-admission-receipt', fixture_body=body)
            cfg = dict(phase='formal', control_root=str(exp/'control'), units=units, inherit_completed={'0': inherited},
                reserve_RAM_bytes=8, reserve_commit_bytes=6, inflight_reserve_bytes=3)
            class Pool:
                def __init__(self, **kwargs): self._processes = {i: FakeProcess(i) for i in range(kwargs['max_workers'])}
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def submit(self, function, config, unit):
                    submitted.append(unit['job']['job_id']); f = Future(); f.set_result(dict(worker_pid=2)); return f
            with patch.object(a, 'safe', lambda p: Path(p)), patch.object(a, 'EXP', exp), \
                 patch.object(a, 'checked', lambda value: Path(value['path'])), \
                 patch.object(a, 'read', lambda value: value.get('fixture_body', value)), \
                 patch.object(a, 'ref', lambda p: dict(path=str(p), sha256='a'*64)), \
                 patch.object(a, 'resources', lambda c: SimpleNamespace(resource_snapshot=lambda: dict(available_RAM_bytes=100, commit_available_bytes=100))), \
                 patch.object(a, 'ProcessPoolExecutor', Pool), patch.object(a, 'wait', lambda active, **kwargs: (set(active), set())), \
                 patch.object(a, 'summarize', lambda c, refs: dict(fixture=True)):
                result = a.execute(exp/'formal.json', cfg)
            self.assertEqual(submitted, [str(i) for i in range(1, 12)])
            self.assertEqual(result['completed']['0'], inherited)
            self.assertEqual(result['inherited_completed'], {'0': inherited})

    def test_inherit_partial_is_rejected_before_pool_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            exp = Path(temp)/'experiment'; exp.mkdir()
            cfg = dict(phase='formal', control_root=str(exp/'control'), units=[dict(job=dict(job_id='0'), observe={}, posthoc={})],
                inherit_completed={'0': dict(status='partial', job=dict(job_id='0'), observe={}, posthoc={}, frames=750, row_count=1, ledger=dict(rows=1))})
            with patch.object(a, 'safe', lambda p: Path(p)), patch.object(a, 'EXP', exp), patch.object(a, 'read', lambda value: value), \
                 patch.object(a, 'ProcessPoolExecutor') as pool:
                with self.assertRaises(ValueError): a.execute(exp/'formal.json', cfg)
                pool.assert_not_called()

    def test_nonzero_exit_or_still_alive_rejected_in_admission_and_formal(self):
        for phase in ('admission', 'formal'):
            for code, alive in ((1, False), (0, True)):
                with self.subTest(phase=phase, exitcode=code, alive=alive), tempfile.TemporaryDirectory() as temp:
                    exp = Path(temp)/'experiment'; exp.mkdir()
                    cfg = dict(phase=phase, control_root=str(exp/'control'), admission_root=str(exp/'admission'),
                        units=[dict(job=dict(job_id=str(i))) for i in range(12)], reserve_RAM_bytes=8, reserve_commit_bytes=6, inflight_reserve_bytes=3)
                    class Pool:
                        def __init__(self, **kwargs):
                            self._processes = {i: FakeProcess(i, code if i == 0 else 0, alive if i == 0 else False) for i in range(kwargs['max_workers'])}
                        def __enter__(self): return self
                        def __exit__(self, *args): return False
                        def submit(self, *args):
                            f = Future(); f.set_result(dict(worker_pid=123)); return f
                    with patch.object(a, 'safe', lambda p: Path(p)), patch.object(a, 'EXP', exp), \
                         patch.object(a, 'read', lambda v: v), patch.object(a, 'ref', lambda p: dict(path=str(p), sha256='a'*64)), \
                         patch.object(a, 'resources', lambda c: SimpleNamespace(resource_snapshot=lambda: dict(available_RAM_bytes=100, commit_available_bytes=100))), \
                         patch.object(a, 'ProcessPoolExecutor', Pool), patch.object(a, 'wait', lambda active, **kwargs: (set(active), set())), \
                         patch.object(a, 'summarize') as summarize:
                        with self.assertRaises(ValueError):
                            (a.admit if phase == 'admission' else a.execute)(exp/'config.json', cfg)
                        summarize.assert_not_called()
                    self.assertFalse((exp/'admission/receipt.json').exists())
                    self.assertFalse((exp/'control/report.json').exists())
                    failure = exp/('admission/failed.json' if phase == 'admission' else 'control/driver_state.json')
                    self.assertTrue(failure.exists())

    def test_admission_single_worker_exit0_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            exp = Path(temp); cfg = dict(phase='admission', admission_root=str(exp/'admission'), units=[dict(job=dict(job_id='first'))],
                reserve_RAM_bytes=8, reserve_commit_bytes=6, inflight_reserve_bytes=3)
            counts = []
            class Pool:
                def __init__(self, **kwargs):
                    counts.append(kwargs['max_workers']); self._processes = {0: FakeProcess(321)}
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def submit(self, *args):
                    f = Future(); f.set_result(dict(path='successful-existing750-unit', sha256='b'*64)); return f
            with patch.object(a, 'safe', lambda p: Path(p)), patch.object(a, 'ref', lambda p: dict(path=str(p), sha256='a'*64)), \
                 patch.object(a, 'resources', lambda c: SimpleNamespace(resource_snapshot=lambda: dict(available_RAM_bytes=100, commit_available_bytes=100))), \
                 patch.object(a, 'ProcessPoolExecutor', Pool):
                result = a.admit(exp/'config.json', cfg)
            self.assertEqual(counts, [1])
            self.assertEqual(result['worker_exits'], [dict(worker_pid=321, joined=True, process_exited=True, exit_code=0)])
            self.assertTrue(result['worker_joined']); self.assertEqual(result['new_TrackEval'], 0)


class ProtocolContracts(unittest.TestCase):
    def test_strict_matrix_and_admission_inheritance_source_immutability(self):
        with tempfile.TemporaryDirectory() as temp:
            research = Path(temp); bundle = research/'code/frozen'; bundle.mkdir(parents=True)
            def put(name, body):
                path = research/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(a.canonical(body), encoding='utf-8')
                return a.ref(path)
            with patch.object(a, 'safe', lambda p: Path(p)), patch.object(a, 'R', research), patch.object(a, 'ROOT', bundle):
                base, summary = summary_units()
                units = [dict(job=u['job'], observe=dict(path='observe'+u['job']['job_id']), posthoc=dict(path='posthoc'+u['job']['job_id'])) for u in summary]
                old = dict(status='complete12_train_rollouts_bounded_oracle_diagnosis_no_factor_executed', active=[],
                    observe={u['job']['job_id']: u['observe'] for u in units}, posthoc={u['job']['job_id']: u['posthoc'] for u in units})
                oldref = put('old.json', old)
                complete = put('source-complete.json', dict(status='complete12_train_diagnosis_verified_zero_eligible_no_oracle_effect_estimated',
                    state=oldref, actual_all_research_producers_and_verifier_absent=True))
                cfg = dict(schema='decision_opportunity_protocol_v1', approved_by='root', test_sealed=True,
                    new_optimizer_updates=0, new_model_forwards=0, new_tracking=0, new_solver_calls=0, new_TrackEval=0,
                    bundle=str(bundle), bundle_manifest=put('bundle.json', dict(files=[])), source_state=oldref,
                    units=units, sequences=list(base['sequences']), source_folds=dict(zip(base['sequences'], ('game4', 'game6', 'game9'))),
                    worker_count=2, reserve_RAM_bytes=8589934592, reserve_commit_bytes=6442450944, inflight_reserve_bytes=3221225472,
                    bootstrap_seed=20261028, bootstrap_repeats=10000, phase='admission', inherit_completed={}, source_complete=complete, resource_source={})
                admission_cfg = put('admission/config.json', cfg)
                self.assertEqual(a.validate(admission_cfg['path'])['phase'], 'admission')
                duplicate = deepcopy(cfg); duplicate['units'][1]['job']['fold'] = duplicate['units'][0]['job']['fold']
                with self.assertRaises(ValueError): a.validate(put('duplicate.json', duplicate)['path'])
                bad_seed = deepcopy(cfg); bad_seed['units'][0]['job']['seed'] = 20261025
                with self.assertRaises(ValueError): a.validate(put('seed.json', bad_seed)['path'])
                unit_ref = dict(path='success-unit', sha256='b'*64)
                gate = put('admission/receipt.json', dict(status='complete_one750_existing_log_stream_admission', worker_joined=True, protocol=admission_cfg, unit=unit_ref))
                formal = deepcopy(cfg); formal.update(phase='formal', admission=gate, inherit_completed={units[0]['job']['job_id']: unit_ref})
                self.assertEqual(a.validate(put('formal.json', formal)['path'])['inherit_completed'], formal['inherit_completed'])
                changed = deepcopy(formal); changed['resource_source'] = dict(path='changed')
                with self.assertRaises(ValueError): a.validate(put('changed.json', changed)['path'])
                partial_gate = put('partial-gate.json', dict(status='partial', worker_joined=True, protocol=admission_cfg, unit=unit_ref))
                formal['admission'] = partial_gate
                with self.assertRaises(ValueError): a.validate(put('partial-formal.json', formal)['path'])


if __name__ == '__main__': unittest.main()
