"""独立终验针对检查：原ID/全帧、Count口径、负配对、worker闭包和实际身份。"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_ocsort_cached_results as verify


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.root_patch = patch.object(verify, 'R', self.root); self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop(); self.temp.cleanup()

    def native_fixture(self):
        native = self.root/'native_outputs.jsonl'; mot = self.root/'seq.txt'
        frames = [dict(frame_number=1, rows=[[1., 2., 11., 22., 9.], [2., 4., 12., 24., 2.]]),
            dict(frame_number=2, rows=[]), dict(frame_number=3, rows=[[3., 5., 13., 25., 9.]])]
        native.write_text(''.join(json.dumps(f)+'\n' for f in frames), encoding='utf-8')
        mot.write_text('1,9,1.0,2.0,10.0,20.0,1,-1,-1,-1\n1,2,2.0,4.0,10.0,20.0,1,-1,-1,-1\n3,9,3.0,5.0,10.0,20.0,1,-1,-1,-1\n', encoding='utf-8')
        return native, mot

    def test_all_native_frames_empty_rows_and_original_noncontiguous_IDs(self):
        native, mot = self.native_fixture(); result = verify.native_to_mot(native, mot, 3, [2, 0, 1])
        self.assertEqual(result['tracked_rows'], 3); self.assertEqual(result['returned_IDs'], 2)
        self.assertEqual(result['maximum_native_ID'], 9); self.assertEqual(result['empty_output_frames'], 1)
        # 不要求输出ID从1开始或连续：内部未返回轨迹也会消耗原ID。
        original = mot.read_text(encoding='utf-8')
        for altered in [original.replace('1,9,', '1,1,', 1), original.split('\n', 1)[1],
                        original.replace('20.0,1,-1', '20.0,0.9,-1', 1), original+'\n']:
            mot.write_text(altered, encoding='utf-8')
            with self.assertRaises(ValueError): verify.native_to_mot(native, mot, 3, [2, 0, 1])
        mot.write_text(original, encoding='utf-8'); value = native.read_text(encoding='utf-8').splitlines()
        native.write_text('\n'.join([value[0], value[2]])+'\n', encoding='utf-8')
        with self.assertRaises(ValueError): verify.native_to_mot(native, mot, 3, [2, 0, 1])

    def metric_fixture(self):
        source = dict(frames=3, cache=dict(path='only_reference_no_read', sha256='cache'))
        cfg = dict(sources={'S': source}, expected_GT_rows={'S': 4}, panels=dict(seven_observed=['S']),
            registries=dict(seven=dict(registry=dict(path='GT_registry_not_read', sha256='registry'))))
        fractions = dict(HOTA=.2, AssA=.3, DetA=.4, IDF1=.5, MOTA=-.1)
        raw = dict(Count=dict(Dets=3, GT_Dets=4, IDs=2, GT_IDs=2),
            HOTA={k: [fractions[k], fractions[k]] for k in ('HOTA', 'AssA', 'DetA')},
            Identity=dict(IDF1=.5), CLEAR=dict(MOTA=-.1, IDSW=2))
        single = deepcopy(raw); single['Count']['Frames'] = 3
        summary = dict(metrics_fraction=fractions, metrics_percent={k: 100*v for k, v in fractions.items()}, IDSW_count=2)
        overall = dict(total_events=2, same_prediction_ID_recovered=1, missing_prediction_endpoint=1,
            events_with_missing_endpoint=1, events_with_ambiguous_endpoint=0, recovery_rate=.5)
        report = dict(schema='official_ocsort_cached12_evaluation_v1', status='complete', sequence='S', frames=3,
            source_cache=source['cache'], protocol_sha256='p', GT_rows=4, new_optimizer_updates=0, test_read=False,
            DO_PREPROC=False, predictions_GT_filtered=False, GT_ID0_original=True, GT_used_only_for_metric=True,
            actual_ID0_rows=1, raw_results={'S': {'pedestrian': single}, 'COMBINED_SEQ': {'pedestrian': raw}}, summary={'S': summary, 'COMBINED_SEQ': deepcopy(summary)},
            metrics_percent=summary['metrics_percent'], registry=cfg['registries']['seven']['registry'],
            recovery=dict(overall=overall, strata={'2-4': overall, '5-9': dict(total_events=0, recovery_rate=None),
                '10-29': dict(total_events=0, recovery_rate=None)}, events=[
                    dict(event_uid='a', reason='same_prediction_ID_recovered', endpoint_states=['unique', 'unique']),
                    dict(event_uid='b', reason='missing_prediction_endpoint', endpoint_states=['missing', 'unique'])]))
        return cfg, report

    def test_TrackEval_Count_COMBINED_without_Frames_and_ID0_original(self):
        cfg, report = self.metric_fixture()
        result = verify.check_metric(report, dict(tracked_rows=3), cfg, 'S', 'p', 2, True)
        self.assertFalse(result['ID0_independently_recounted_in_terminal_verifier'])
        for field, value in [('actual_ID0_rows', 0), ('GT_rows', 3), ('predictions_GT_filtered', True)]:
            bad = deepcopy(report); bad[field] = value
            with self.assertRaises(ValueError): verify.check_metric(bad, dict(tracked_rows=3), cfg, 'S', 'p', 2, True)
        bad = deepcopy(report); bad['raw_results']['COMBINED_SEQ']['pedestrian']['Count']['Dets'] = 2
        with self.assertRaises(ValueError): verify.check_metric(bad, dict(tracked_rows=3), cfg, 'S', 'p', 2, True)
        bad = deepcopy(report); bad['recovery']['events'][1]['event_uid'] = 'a'
        with self.assertRaises(ValueError): verify.check_metric(bad, dict(tracked_rows=3), cfg, 'S', 'p', 2, True)

    def pair_fixture(self):
        panels = dict(original_heldout=list(verify.OLD), old_external=['E1', 'E2'], seven_observed=['V'+str(i) for i in range(7)])
        oc, refs = [], []
        for panel in verify.PANELS:
            for seq in panels[panel]:
                oc.append(dict(sequence=seq, metrics={k: 1. for k in verify.METRICS},
                    recovery=dict(total_events=10, same_prediction_ID_recovered=3, recovery_rate=.3), report=dict(path='OC-'+seq, sha256='a')))
                for baseline in verify.BASELINES:
                    folds = (verify.OLD[seq],) if seq in verify.OLD else verify.FOLDS
                    cells = [(None, None)] if baseline == 'PT_bbox' else [(f, s) for f in folds for s in verify.SEEDS]
                    for fold, seed in cells:
                        refs.append(dict(baseline=baseline, sequence=seq, fold=fold, seed=seed, metrics={k: 2. for k in verify.METRICS},
                            recovery=dict(total_events=10, same_prediction_ID_recovered=4, recovery_rate=.4),
                            report=dict(path=f'{baseline}-{seq}-{fold}-{seed}', sha256='b')))
        return panels, oc, refs

    def test_192_sources_mean_within_match_36_negative_pairs_and_3_2_7_CIs(self):
        panels, oc, refs = self.pair_fixture(); pairs = verify.pair_rows(oc, refs, panels)
        self.assertEqual((len(oc), len(refs), len(pairs)), (12, 192, 36))
        self.assertTrue(all(v['OC_evaluations'] == 1 and v['delta_pp']['AssA'] == -1. for v in pairs))
        def interval(values): return dict(n=len(values), values=values, mean=sum(values.values())/len(values))
        metrics, gaps = verify.expected_intervals(pairs, panels, interval)
        self.assertEqual([metrics['strong_motion_RS'][p]['AssA']['n'] for p in verify.PANELS], [3, 2, 7])
        self.assertEqual([gaps['T_RS'][p]['n'] for p in verify.PANELS], [3, 2, 7])
        for bad in [refs[:-1], refs+[refs[0]]]:
            with self.assertRaises(ValueError): verify.pair_rows(oc, bad, panels)
        # 零分母明确null，不能补0伪造恢复率。
        zero = dict(total_events=0, recovery_rate=None)
        for item in oc+refs:
            if item['sequence'] == panels['old_external'][0]: item['recovery'] = zero
        pairs = verify.pair_rows(oc, refs, panels); _, gaps = verify.expected_intervals(pairs, panels, interval)
        self.assertIsNone(gaps['T_RS']['old_external']['Student_t_95CI'])
        self.assertEqual(gaps['T_RS']['old_external']['zero_event_matches_retained_null'], ['E1'])

    def test_complete_script_and_spawn_creation_not_historical_PID_reuse(self):
        now = datetime.now(timezone.utc); state = dict(parent_pid=55, created_utc=now.isoformat())
        self.assertTrue(verify.is_producer('python D:/code/ocsort_cached_control.py --execute'))
        self.assertFalse(verify.is_producer('python D:/code/verify_ocsort_cached_results.py'))
        self.assertFalse(verify.is_producer('python D:/code/test_ocsort_cached_control.py'))
        reused = dict(ProcessId=55, ParentProcessId=3, Name='python.exe', CommandLine='python unrelated.py', CreationUtc=now.isoformat())
        self.assertEqual(verify.blocked_processes([reused], state), [])
        spawn = dict(reused, CommandLine='python -c "from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=55,pipe_handle=6)"')
        self.assertEqual(len(verify.blocked_processes([spawn], state)), 1)
        old = dict(spawn, CreationUtc=(now-timedelta(days=2)).isoformat())
        self.assertEqual(verify.blocked_processes([old], state), [])
        wrong = dict(spawn, CommandLine=spawn['CommandLine'].replace('55', '555'))
        self.assertEqual(verify.blocked_processes([wrong], state), [])

    def test_worker_complete_jobs_closed_exit0_and_logs(self):
        now = datetime.now(timezone.utc).isoformat(); seqs = ['S'+str(i) for i in range(12)]
        cfg = dict(sources={s: {} for s in seqs}, worker_profile=dict(cache_limit_bytes=100))
        workers = [dict(status='ready', kind=k, worker_pid=p, parent_pid=1, created_utc=now) for k, p in [('track', 2), ('track', 3), ('metric', 4)]]
        tracking = [dict(worker_pid=2 if i < 6 else 3) for i in range(12)]; metrics = [dict(worker_pid=4) for _ in seqs]
        exits = []
        for identity in workers:
            pid = identity['worker_pid']; kind = identity['kind']
            evidence = dict(status='closed', jobs=6 if kind == 'track' else 12, worker_pid=pid)
            if kind == 'track': evidence.update(cache_entries_after=0, max_counted_cache_bytes=50, counted_cache_is_JSON_bytes_not_RSS=True,
                GT_guard=dict(blocked_open_attempts=0, GT_annotations_opened=False, python_open_audit_installed=True))
            else: evidence.update(GT_isolated_to_metric_worker=True, source_closure_verified=True, GT_sequences_loaded=seqs, registry_count=2)
            exits.append(dict(kind=kind, worker_pid=pid, launcher_pid=pid, exit_code=0, process_exited=True, close_evidence=evidence))
        state = dict(parent_pid=1, created_utc=now, workers=workers, worker_exits=exits)
        (self.root/'logs').mkdir()
        for name in ('track_0.log', 'track_1.log', 'metric_0.log'): (self.root/'logs'/name).write_text('', encoding='utf-8')
        self.assertTrue(verify.check_workers(state, cfg, tracking, metrics, self.root)['all_joined_exit0'])
        for key, value in [('exit_code', 1), ('process_exited', False)]:
            bad = deepcopy(state); bad['worker_exits'][0][key] = value
            with self.assertRaises(ValueError): verify.check_workers(bad, cfg, tracking, metrics, self.root)
        bad = deepcopy(state); bad['worker_exits'][2]['close_evidence']['jobs'] = 11
        with self.assertRaises(ValueError): verify.check_workers(bad, cfg, tracking, metrics, self.root)

    def test_terminal_guard_refuses_GT_cache_media_without_reading_them(self):
        forbidden = self.root/'old_cache.jsonl'; forbidden.write_text('must-not-read', encoding='utf-8')
        cfg = dict(sources=dict(S=dict(cache=dict(path=str(forbidden)))), registries={})
        with verify.no_raw_reads(cfg) as evidence:
            with self.assertRaises(PermissionError): forbidden.read_text(encoding='utf-8')
        self.assertEqual(evidence['blocked_open_attempts'], 1)
        # hook已失活，不污染其他本地fixture。
        self.assertEqual(forbidden.read_text(encoding='utf-8'), 'must-not-read')

    def test_CSV_keeps_negative_values_nulls_and_every_source(self):
        path = self.root/'pairs.csv'
        path.write_text('sequence,delta,gap,source\nS,-1.25,,"{""path"":""original""}"\n', encoding='utf-8')
        expected = [dict(sequence='S', delta=-1.25, gap=None, source=dict(path='original'))]
        verify.check_csv(verify.ref(path), expected)
        with self.assertRaises(ValueError): verify.check_csv(verify.ref(path), expected+expected)
        path.write_text('sequence,delta,gap,source\nS,1.25,0,"{""path"":""original""}"\n', encoding='utf-8')
        with self.assertRaises(ValueError): verify.check_csv(verify.ref(path), expected)


if __name__ == '__main__': unittest.main()
