"""新T分支—决策接口候选的CPU合同；不读实际模型/trace，不执行外部实验。"""
from copy import deepcopy
import ast
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pose_information_geometry as geo
import pose_velocity_decision_probe as probe


def record(uid, time):
    return dict(uid=uid, timestamp_sec=time, bbox_xywh_px=[0., 0., 20., 40.], score=.8,
                image_wh=[100, 100], xy_px=[[10., 20.]]*17, geometry_valid=[True]*17)


def event():
    return dict(frame_number=4, stage=0, track_ids=[1, 2], history_UIDs=[['a', 'b', 'c'], ['d']],
        candidate_UIDs=['p', 'n'], bbox_cost=[[.4, .4], [.2, .9]], reference_cost=[[.3, .7], [.2, .9]],
        motion_gate=[[True, True], [False, False]], enabled=[[True, True], [False, False]],
        active_rows=[True, False], enough_history=[True, False], lost_gap=[True, False],
        scored_locations=[[0, 0], [0, 1]], logits=dict(motion=[.1, .2]), GT_read=False,
        chosen_raw_UID=['p', None])


def allocation(cost, thresh):
    """仅测试输出账本的确定性夹具，不冒充真实全局分配数值。"""
    import numpy as np
    matches = []; used = set()
    for i, row in enumerate(cost):
        choices = [j for j, value in enumerate(row) if value <= thresh and j not in used]
        if choices:
            j = min(choices, key=lambda j: row[j]); used.add(j); matches.append([i, j])
    return np.asarray(matches, dtype=int).reshape(-1, 2), [i for i in range(len(cost)) if i not in {r for r, _ in matches}], \
        [j for j in range(cost.shape[1]) if j not in used]


class Tests(unittest.TestCase):
    def test_source_validation_registry_read_is_not_reported_as_no_GT_loaded(self):
        source_job = dict(job_id='S', original=dict(fold='game4', sequence='SNMOT-060'))
        parsed_GT = []
        def source_validation(config):
            # 对应真实既有链已解析endpoint_GT；评分输入尚未构建。
            parsed_GT.append(dict(endpoint_GT={'1': [dict(gt_id='person')]}))
            return ({}, None, geo, None, None, {}, None, [source_job], dict(details=[dict(job=source_job)]), None)
        with patch.object(probe, 'sha', return_value='s'), patch.object(probe, 'physical', side_effect=Path), \
                patch.object(probe, 'validate_config', side_effect=source_validation), \
                patch.object(probe, 'selected_sources', return_value=[source_job]):
            context = probe.ScoreWorkerContext('fixture', 's')
        self.assertEqual(len(parsed_GT), 1)
        self.assertTrue(context.GT_annotations_loaded)
        self.assertTrue(context.source_validation_GT_registry_read)
        self.assertFalse(context.posthoc_GT_labels_loaded)
        self.assertFalse(context.current_source_posthoc_GT_loaded)

    def test_original_nine_numeric_and_label_functions_AST_unchanged(self):
        expected = {
            'add_counts': '29bb7631a53b9b15d78cbc783405d09d87be1fe1679d52e93d362719d85b33ab',
            'assignment_record': '485c89397b9e6d01b3e476ff92c2db7074527b30773690c49090c6a5ba5bffda',
            'branch_scores': '2defbc728be66634c78a28d4db174c821213cbb7825dcff2bcf664376e47a86e',
            'build_inputs': 'f575d2a1dbbc8d664156c757d33c97a25fa77ff7e613c16d6c3d3b57921bd388',
            'costs_and_assignments': '11d7a4dcbb332ed949b4362b230a42a7baf0518f35067ba7d971c3f329b1c48f',
            'decision_outcome': 'd45568e61a5eebc46bac6903e2edc00589775060df64098a06960fb46b1fed11',
            'posthoc_rows': 'c328c36f9bb366eb55bfc65a2e47179eb0ab9f68ee77e1b2d8afea76da7482c3',
            'score_event': '81dad31a7160a6cbdb205f1310754a05a90cc8e928bc93990fba2cca9ea2f76d',
            'validate_event': '6842061b2ea01b188d36a2445c9f26373dd08bdf4121ff76330bbe266c488346'}
        tree = ast.parse(Path(probe.__file__).read_text(encoding='utf-8'))
        actual = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                  for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in expected}
        self.assertEqual(actual, expected)

    def test_false_GT_unloaded_claim_rejected_while_public_inputs_stay_GT_free(self):
        valid = dict(source_validation_GT_registry_read=True, GT_annotations_loaded=True,
            posthoc_GT_labels_loaded=False, current_source_posthoc_GT_loaded=False,
            GT_used_for_scoring=False, GT_free_inputs=True)
        probe.validate_GT_access(valid, no_posthoc=True)
        for key, value in [('source_validation_GT_registry_read', False), ('GT_annotations_loaded', False),
                ('GT_used_for_scoring', True), ('GT_free_inputs', False), ('posthoc_GT_labels_loaded', True),
                ('current_source_posthoc_GT_loaded', True)]:
            bad = dict(valid, **{key: value})
            with self.subTest(field=key):
                with self.assertRaises(ValueError): probe.validate_GT_access(bad, no_posthoc=True)
        bad = deepcopy(valid); bad.pop('GT_annotations_loaded')
        with self.assertRaises(ValueError): probe.validate_GT_access(bad, no_posthoc=True)

    def test_optional_manual_quality_labels_not_adopted_and_not_required(self):
        self.assertEqual(probe.PARAMETERS['manual_quality_policy'], 'optional120_manual_quality_not_adopted_labels_unavailable')
        self.assertFalse(probe.PARAMETERS['manual_keypoint_GT_required_for_execution'])

    def test_two_worker_out_of_order_completion_keeps_frozen_unit_order(self):
        expected = [['A0', 'A1'], ['B0', 'B1'], ['C0', 'C1']]
        collector = probe.OrderedSourceResults(expected)
        make = lambda names: dict(units=[dict(job=dict(job_id=n)) for n in names])
        collector.issue(0); collector.issue(1)
        with self.assertRaises(ValueError): collector.issue(2)  # 最多两个在途源。
        self.assertEqual(collector.accept(1, make(expected[1])), [])
        ready = collector.accept(0, make(expected[0]))
        self.assertEqual([u['job']['job_id'] for result in ready for u in result['units']], ['A0', 'A1', 'B0', 'B1'])
        collector.issue(2); self.assertEqual(collector.accept(2, make(expected[2])), [make(expected[2])])
        self.assertEqual(collector.next_collect, 3)

    def test_failed_source_not_retried_and_duplicate_result_rejected(self):
        collector = probe.OrderedSourceResults([['A0', 'A1'], ['B0', 'B1'], ['C0', 'C1']])
        result = dict(units=[dict(job=dict(job_id=n)) for n in ('A0', 'A1')])
        collector.issue(0); collector.issue(1); collector.fail(1)
        with self.assertRaises(ValueError): collector.issue(2)
        with self.assertRaises(ValueError): collector.issue(1)
        self.assertEqual(collector.accept(0, result), [result])
        with self.assertRaises(ValueError): collector.accept(0, result)
        self.assertTrue(collector.failed)

    def test_actual_RAM_and_commit_both_gate_dispatch(self):
        self.assertEqual(probe.PARAMETERS['score_workers'], 2)
        self.assertEqual(probe.PARAMETERS['numeric_threads'], 1)
        self.assertTrue(probe.dispatch_allowed(dict(available_RAM_gib=8., commit_headroom_gib=6.)))
        self.assertFalse(probe.dispatch_allowed(dict(available_RAM_gib=7.99, commit_headroom_gib=100.)))
        self.assertFalse(probe.dispatch_allowed(dict(available_RAM_gib=100., commit_headroom_gib=5.99)))
        with self.assertRaises(ValueError): probe.dispatch_allowed(dict(available_RAM_gib=float('nan'), commit_headroom_gib=100.))

    def test_new_output_never_overwrites_existing_partial(self):
        with TemporaryDirectory(prefix='pose_probe_CPU_') as folder:
            target = Path(folder)/'receipt.json'
            with patch.object(probe, 'physical', side_effect=Path):
                probe.write_new(target, dict(value='first'))
                with self.assertRaises(FileExistsError): probe.write_new(target, dict(value='replacement'))
            self.assertIn('first', target.read_text(encoding='utf-8'))

    def test_raw_cache_reads_no_additional_posthoc_GT_but_source_validation_already_read_registry(self):
        context = probe.ScoreWorkerContext.__new__(probe.ScoreWorkerContext)
        context.source_cache = None; context.event_cache = None
        context.source_validation_GT_registry_read = True; context.GT_annotations_loaded = True
        context.posthoc_GT_labels_loaded = False; context.current_source_posthoc_GT_loaded = False
        context.prepared = dict(sources={seq: dict(source=dict(cache=dict(path=seq)), labels=dict(path='forbidden_GT')) for seq in ('A', 'B')})
        context.core = SimpleNamespace(rows=lambda path: [dict(detections=[record(path, .1)])])
        with patch.object(probe, 'checked', side_effect=lambda value: value['path']), \
                patch.object(probe, 'read', side_effect=AssertionError('raw数值入口不得读取GT/labels')):
            a = context.raw_source('A'); b = context.raw_source('B')
        self.assertIs(context.source_cache, b); self.assertIsNot(a, b)
        self.assertEqual(context.source_cache['sequence'], 'B')
        self.assertIsNone(context.source_cache['posthoc'])
        self.assertTrue(context.GT_annotations_loaded); self.assertTrue(context.source_validation_GT_registry_read)
        self.assertFalse(context.posthoc_GT_labels_loaded); self.assertFalse(context.current_source_posthoc_GT_loaded)

    def test_fixed_first_seed_balanced9_traces18_new_model_units(self):
        jobs = []
        for fold in probe.FOLDS:
            for seed in (20261024, 20261025, 20261026):
                for pool in ('balanced', 'hard_enriched'):
                    for seq in [next(s for s, f in probe.OLD.items() if f == fold)]+list(probe.EXTERNAL):
                        jobs.append(dict(kind='common_state', job_id=f'{fold}/{seed}/{pool}/{seq}',
                            original=dict(fold=fold, seed=seed, pool=pool, sequence=seq)))
        selected = probe.selected_sources(jobs); matrix = probe.matrix(jobs)
        self.assertEqual(len(selected), 9); self.assertEqual(len(matrix), 18)
        self.assertEqual({j['group'] for j in matrix}, {'T_RS', 'T_shuffle_RS'})
        self.assertTrue(all(j['seed'] == 20261024 and j['pool'] == 'balanced' for j in matrix))
        with self.assertRaises(ValueError): probe.matrix(jobs[:-1])

    def test_public_inputs_ignore_GT_fields_and_forbid_future(self):
        source = {x: record(x, t) for x, t in [('a', 0.), ('b', .1), ('c', .2), ('d', .2), ('p', .3), ('n', .3)]}
        class Adapter:
            def transform_pair(self, history, candidate):
                assert all(set(r) == set(geo.FIELDS) for r in history+[candidate])
                return [candidate['score']]*194+[.5]
        original = probe.build_inputs(event(), source, Adapter(), geo.public)
        for r in source.values(): r.update(GT_identity='secret', GT_Pose=[[999, 999]])
        self.assertEqual(original, probe.build_inputs(event(), source, Adapter(), geo.public))
        source['c']['timestamp_sec'] = .3
        with self.assertRaises(ValueError): probe.build_inputs(event(), source, Adapter(), geo.public)

    def test_empty_scored_event_preserved_without_old_logit_fill(self):
        e = event(); e.update(scored_locations=[], enough_history=[False, False], enabled=[[False, False]]*2)
        e.pop('logits')
        self.assertEqual(probe.validate_event(e), ([], []))
        self.assertEqual(probe.branch_scores(None, [], None)['logits'], {name: [] for name in probe.BRANCHES})

    def test_actual_CPU_model_components_keep_q0_raw_residual(self):
        import torch
        class Model(torch.nn.Module):
            variant = 'gated'
            def __init__(self):
                super().__init__(); self.base = torch.nn.Linear(194, 1); self.residual = torch.nn.Linear(170, 1)
                with torch.no_grad():
                    self.base.weight.zero_(); self.base.bias.fill_(.2)
                    self.residual.weight.zero_(); self.residual.bias.fill_(.8)
            def forward(self, x):
                motion = torch.cat([x[:, :24], torch.zeros_like(x[:, 24:194])], 1)
                return self.base(motion)+x[:, 194:195]*.5*torch.tanh(self.residual(x[:, 24:194]))
        model = Model().eval(); rows = [[0.]*194+[0.], [0.]*194+[.5]]
        result = probe.branch_scores(model, rows, torch)
        self.assertTrue(result['full_forward_equal_original_q'])
        self.assertGreater(result['residual'][0], 0)
        self.assertEqual(result['gated_residual'][0], 0)
        self.assertEqual(result['logits']['own_base'][0], result['logits']['original_q'][0])
        self.assertGreater(result['logits']['q1'][0], result['logits']['original_q'][0])

    def test_original_cost_function_and_full_unmatched_ledger_are_reused(self):
        import numpy as np
        import torch
        e = event(); scores = dict(logits={name: [.2, -.2] for name in probe.BRANCHES})
        out = probe.costs_and_assignments(e, [(0, 0), (0, 1)], scores, geo, np, torch, allocation)
        for name in probe.BRANCHES:
            expected, threshold = geo.choose_cost(dict(e, logits=scores['logits']), name, np, torch)
            self.assertEqual(out[name]['cost'], expected.tolist()); self.assertEqual(out[name]['threshold'], threshold)
            self.assertEqual(out[name]['cost'][1], np.asarray(e['bbox_cost'], dtype=np.float32).tolist()[1])
            ledger = out[name]['assignment']
            self.assertEqual(set(ledger['unmatched_rows']) | {i for i, _ in ledger['matches']}, {0, 1})
            self.assertEqual(set(ledger['unmatched_columns']) | {j for _, j in ledger['matches']}, {0, 1})

    def test_unknown_and_unmatched_transitions_not_collapsed(self):
        labels = dict(p=dict(state='matched', gt_id='Q'), n=dict(state='matched', gt_id='other'),
                      u=dict(state='unknown_ambiguous'))
        self.assertEqual(probe.decision_outcome('Q', 0, ['p'], labels, geo), 'known_correct')
        self.assertEqual(probe.decision_outcome('Q', 0, ['n'], labels, geo), 'known_wrong')
        self.assertEqual(probe.decision_outcome('Q', 0, ['u'], labels, geo), 'unknown')
        self.assertEqual(probe.decision_outcome(None, 0, ['p'], labels, geo), 'unknown')
        self.assertEqual(probe.decision_outcome('Q', None, ['p'], labels, geo), 'unmatched')
        table = probe.empty_transitions(); table['unmatched']['known_correct'] += 1
        self.assertEqual(len(table), 4); self.assertEqual(sum(map(len, table.values())), 16)
        self.assertEqual(table['unmatched']['known_correct'], 1)

    def test_all_gated_and_native_batches_remain_distinct(self):
        import numpy as np
        import torch
        class Adapter:
            def transform_pair(self, history, candidate): return [0.]*194+[.5]
        class Model(torch.nn.Module):
            variant = 'gated'
            def __init__(self):
                super().__init__(); self.base = torch.nn.Linear(194, 1); self.residual = torch.nn.Linear(170, 1)
            def forward(self, x):
                return self.base(torch.cat([x[:, :24], torch.zeros_like(x[:, 24:194])], 1))+x[:, 194:195]*.5*torch.tanh(self.residual(x[:, 24:194]))
        e = event(); e['enabled'] = [[False, False], [False, False]]; e['active_rows'] = [False, False]
        source = {x: record(x, t) for x, t in [('a', 0.), ('b', .1), ('c', .2), ('p', .3), ('n', .3)]}
        out = probe.score_event(e, source, Model().eval(), Adapter(), geo, np, torch, allocation)
        self.assertEqual(len(out['all_gated']['base']), 2)
        self.assertEqual(out['enabled_native']['base'], [])
        self.assertEqual(out['reference']['recorded_actual_old_motion_cost'], e['reference_cost'])
        self.assertFalse(out['GT_used_for_scoring'])
        for name in probe.BRANCHES:
            self.assertEqual(out['enabled_native']['decisions'][name]['cost'], np.asarray(e['bbox_cost'], dtype=np.float32).tolist())

    def test_posthoc_full_transitions_keep_unmatched_repairs_and_unknowns(self):
        e = event()
        labels = {uid: dict(state='matched', gt_id='Q') for uid in ('a', 'b', 'c', 'p')}
        labels.update(d=dict(state='unknown_ambiguous'), n=dict(state='matched', gt_id='other'))
        scored = dict(all_gated=dict(locations=[[0, 0], [0, 1]], q=[0., .5],
            logits=dict(own_base=[-.2, .2], original_q=[-.1, .1], q1=[.3, -.3])),
            enabled_native=dict(locations=[[0, 0], [0, 1]], decisions={
                'own_base': dict(assignment=dict(matches=[[0, 1]])),
                'original_q': dict(assignment=dict(matches=[])),
                'q1': dict(assignment=dict(matches=[[0, 0], [1, 1]]))}),
            batch_numeric_comparison={name: dict(assignments_equal=True) for name in probe.BRANCHES})
        GT = {4: [dict(gt_id='Q', bbox_xywh_px=[0., 0., 20., 40.])]}
        rows = probe.posthoc_rows(e, scored, labels, GT, [record('p', .3), record('n', .3)], geo, dict(near_motion_gap=.2))
        transitions = {name: {subset: probe.empty_transitions() for subset in ('all_rows', 'trusted_current_GT_present')}
                       for name in ('original_q_vs_own_base', 'q1_vs_own_base', 'q1_vs_original_q')}
        from collections import Counter
        counts = Counter(); probe.add_counts(counts, transitions, e, scored, rows)
        self.assertEqual(len(rows), 2); self.assertEqual(rows[1]['history_status'], 'unknown_history')
        self.assertTrue(rows[0]['original_reference_near_motion'])
        self.assertEqual(transitions['q1_vs_original_q']['all_rows']['unmatched']['known_correct'], 1)
        self.assertEqual(transitions['q1_vs_own_base']['all_rows']['unmatched']['unknown'], 1)
        self.assertEqual(sum(sum(v.values()) for v in transitions['q1_vs_own_base']['all_rows'].values()), 2)
        self.assertEqual(counts['trusted_current_GT_present_rows'], 1)


if __name__ == '__main__':
    unittest.main()
