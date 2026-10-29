"""资格mask方法夹具。P1只跑metadata；Torch玩具梯度留待单独授权的数值执行。"""
from copy import deepcopy
import importlib.util
import unittest

import r_candidate_eligibility_method as m

TORCH_AVAILABLE = importlib.util.find_spec('torch') is not None


def fixture(uid='w', labels=(1, 0, None), eligible=(True, False, True)):
    metadata = dict(window_uid=uid, history_UIDs=['h0', 'h1', 'h2'], candidate_UIDs=[uid+':'+str(i) for i in range(len(labels))],
        pair_labels=list(labels), source_job_id='teacher', candidate_frame_number=10, source_stage='high_score', source_row_index=2,
        source_track_id=3, teacher_model_id='teacher-model', teacher_regime='R', teacher_seed=20261024, fold='game4', sequence='SNMOT-097')
    window = dict(window_uid=uid, history=[dict(uid=u) for u in metadata['history_UIDs']],
        candidates=[dict(prediction=dict(uid=u), label=v) for u, v in zip(metadata['candidate_UIDs'], labels)], aligned_bank_metadata=metadata)
    side = dict(schema=m.MASK_SCHEMA, eligibility_rule=m.RULE, eligibility_stage='pre_probability', labels_used_to_choose_mask=False,
        window_uid=uid, history_UIDs=metadata['history_UIDs'], candidate_UIDs=metadata['candidate_UIDs'],
        active=True, enabled=list(eligible), scoring_eligible=list(eligible), **{k: metadata[k] for k in m.SOURCE_KEYS})
    return window, side


class MetadataContracts(unittest.TestCase):
    def test_all_and_known_counts_unknown_kept_without_supervision(self):
        window, side = fixture(); before = deepcopy(window); bound = m.bind_window_mask(window, side)
        self.assertEqual(bound['known_indices'], [0, 1]); self.assertEqual(bound['known_scoring_eligible'], [True, False])
        counts = bound['accounting']
        self.assertEqual((counts['raw_candidate_pairs'], counts['raw_known_pairs'], counts['raw_unknown_pairs']), (3, 2, 1))
        self.assertEqual((counts['kept_known_pairs'], counts['excluded_known_pairs'], counts['kept_unknown_pairs']), (1, 1, 1))
        self.assertEqual((counts['kept_positive_pairs'], counts['excluded_negative_pairs']), (1, 1))
        self.assertEqual(window, before); self.assertEqual(m.checked_binding(bound), bound)

    def test_mask_label_independent_but_binding_keeps_original_labels(self):
        first, side = fixture(); other = deepcopy(first)
        other['candidates'][0]['label'] = 0; other['candidates'][1]['label'] = 1; other['aligned_bank_metadata']['pair_labels'] = [0, 1, None]
        a, b = m.bind_window_mask(first, side), m.bind_window_mask(other, side)
        self.assertEqual(a['all_scoring_eligible'], b['all_scoring_eligible']); self.assertEqual(a['known_scoring_eligible'], b['known_scoring_eligible'])
        self.assertNotEqual(a['binding_sha256'], b['binding_sha256'])
        bad = deepcopy(side); bad['labels_used_to_choose_mask'] = True
        with self.assertRaises(ValueError): m.bind_window_mask(first, bad)

    def test_exact_source_history_candidate_order_unknown_mask_and_tampering_refused(self):
        window, side = fixture()
        for change in (lambda s: s.update(history_UIDs=['bad']), lambda s: s.update(candidate_UIDs=list(reversed(s['candidate_UIDs']))),
                       lambda s: s.update(source_track_id=999), lambda s: s.update(teacher_seed=20261025),
                       lambda s: s.update(enabled=[None, False, True]), lambda s: s.update(eligibility_stage='after_probability')):
            bad = deepcopy(side); change(bad)
            with self.assertRaises(ValueError): m.bind_window_mask(window, bad)
        bound = m.bind_window_mask(window, side); bound['known_scoring_eligible'][0] = False
        with self.assertRaises(ValueError): m.checked_binding(bound)

    def test_empty_effective_window_preserved_not_resampled(self):
        window, side = fixture(eligible=(False, False, False)); side['active'] = False
        bound = m.bind_window_mask(window, side)
        self.assertEqual(bound['accounting']['effective_known_empty'], 1)
        self.assertEqual(bound['accounting']['raw_known_empty'], 0)
        self.assertEqual(bound['known_candidate_UIDs'], ['w:0', 'w:1'])
        self.assertEqual(bound['known_labels'], [1, 0])


@unittest.skipUnless(TORCH_AVAILABLE, 'P1无Torch；只定义CPU玩具数值夹具，不代替正式CPU/CUDA准入')
class TorchNumericFixtures(unittest.TestCase):
    def setUp(self):
        import torch
        self.torch = torch; torch.set_num_threads(1); torch.manual_seed(20261029)
        class RecordingModel(torch.nn.Module):
            def __init__(self):
                super().__init__(); self.layers = torch.nn.Sequential(torch.nn.Linear(194, 64), torch.nn.ReLU(), torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1)); self.calls = []
            def forward(self, x): self.calls.append(x.detach().clone()); return self.layers(x)
        self.model = RecordingModel()
        self.assertEqual(sum(p.numel() for p in self.model.parameters()), 14593)

    def windows(self, masks):
        torch = self.torch; windows = []; bindings = []
        for i, mask in enumerate(masks):
            labels = tuple([1]+[0]*(len(mask)-1)); window, side = fixture('w'+str(i), labels, mask)
            binding = m.bind_window_mask(window, side); count = len(labels)
            x = torch.arange(count*194, dtype=torch.float32).reshape(count, 194)/10000+i*.1
            # 与强motion契约一样，原normalizer之后后170列置零；方法不改这些值。
            x[:, 24:] = 0.
            windows.append(dict(window_uid=window['window_uid'], x=x, labels=torch.tensor(labels, dtype=torch.float32), candidate_pairs=count, known_pairs=count)); bindings.append(binding)
        return windows, bindings

    def original_domain_loss(self, model, windows):
        torch = self.torch; from torch.nn import functional as F
        counts = [len(w['labels']) for w in windows]; device = next(model.parameters()).device
        x = torch.cat([w['x'] for w in windows]).to(device); y = torch.cat([w['labels'] for w in windows]).to(device)
        losses = F.binary_cross_entropy_with_logits(model(x).reshape(-1), y, reduction='none')
        return torch.stack([part.mean() for part in losses.split(counts)]).mean()

    def test_all_true_original_forward_loss_grad_and_RNG_exact(self):
        torch = self.torch; windows, bindings = self.windows([[True, True], [True, True, True], [True]])
        old = deepcopy(self.model); initial = deepcopy(self.model.state_dict()); rng = torch.get_rng_state().clone()
        original = self.original_domain_loss(old, windows); actual, counts = m.masked_real_domain_BCE(self.model, windows, bindings)
        self.assertTrue(torch.equal(actual, original)); self.assertEqual(len(self.model.calls), 1)
        self.assertTrue(torch.equal(self.model.calls[0], torch.cat([w['x'] for w in windows])))
        original.backward(); actual.backward()
        for left, right in zip(old.parameters(), self.model.parameters()): self.assertTrue(torch.equal(left.grad, right.grad))
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        for name, value in initial.items(): self.assertTrue(torch.equal(self.model.state_dict()[name], value))
        self.assertEqual(counts['forwarded_known_pairs'], 6)
        self.assertEqual(counts['windows'][0]['known_candidate_UIDs'], bindings[0]['known_candidate_UIDs'])
        self.assertEqual(counts['windows'][0]['known_labels'], bindings[0]['known_labels'])
        self.assertEqual(counts['totals']['R_effective_unknown_pairs'], 0)

    def test_three_empty_masks_all_parameters_have_graph_zero_grad(self):
        torch = self.torch; windows, bindings = self.windows([[False, False], [False], [False, False, False]])
        actual, counts = m.masked_real_domain_BCE(self.model, windows, bindings)
        self.assertTrue(actual.requires_grad); self.assertEqual(actual.item(), 0.); actual.backward()
        for parameter in self.model.parameters():
            self.assertIsNotNone(parameter.grad); self.assertTrue(torch.equal(parameter.grad, torch.zeros_like(parameter)))
        self.assertEqual(len(self.model.calls), 1); self.assertEqual(counts['forwarded_known_pairs'], 6)
        self.assertEqual(counts['totals']['effective_known_empty'], 3)

    def test_partial_mask_manual_window_mean_fixed_three_R_denominator(self):
        torch = self.torch; from torch.nn import functional as F
        windows, bindings = self.windows([[True, False], [False, False], [True, True, False]])
        reference = deepcopy(self.model); x = torch.cat([w['x'] for w in windows]); y = torch.cat([w['labels'] for w in windows])
        logits = reference(x).reshape(-1); parts = F.binary_cross_entropy_with_logits(logits, y, reduction='none').split([2, 2, 3])
        manual = torch.stack([parts[0][0:1].mean(), (parts[1]*0.).sum(), parts[2][:2].mean()]).mean()
        actual, counts = m.masked_real_domain_BCE(self.model, windows, bindings)
        self.assertTrue(torch.equal(actual, manual)); manual.backward(); actual.backward()
        for left, right in zip(reference.parameters(), self.model.parameters()): self.assertTrue(torch.equal(left.grad, right.grad))
        self.assertEqual(counts['totals']['kept_known_pairs'], 3); self.assertEqual(counts['totals']['excluded_known_pairs'], 4)
        self.assertEqual(self.model.calls[0].shape, (7, 194))

    def test_S_original_callback_unchanged_once_and_alpha_one_third(self):
        torch = self.torch; windows, bindings = self.windows([[False, False], [False], [False]])
        synthetic, _ = self.windows([[True, True]]); reference = deepcopy(self.model); calls = []
        expected_s = self.original_domain_loss(reference, synthetic)
        def callback(model, value):
            self.assertIs(value, synthetic); calls.append(value); return self.original_domain_loss(model, value)
        result = m.step_loss(self.model, windows, bindings, synthetic, callback)
        self.assertEqual(len(calls), 1); self.assertTrue(torch.equal(result['synthetic_loss'], expected_s))
        self.assertTrue(torch.equal(result['loss'], expected_s/3)); self.assertEqual(len(self.model.calls), 2)
        self.assertFalse(result['optimizer_step_executed'])

    def test_real_accounting_connects_to_record_extension_without_files_or_optimizer(self):
        from r_eligibility_recorded_loop import EligibilityJournal
        windows, bindings = self.windows([[True, False], [False], [True, True, False]])
        _, accounting = m.masked_real_domain_BCE(self.model, windows, bindings)
        journal = object.__new__(EligibilityJournal)
        original_rows = [dict(window_uid=w['window_uid'], epoch=0, candidate_pairs=w['candidate_pairs'], labelled_pairs=w['known_pairs']) for w in windows]
        journal.pending = dict(update_index=0, actual_update=1, real=deepcopy(original_rows), synthetic=[])
        effective = journal.record_mask_accounting(accounting)
        self.assertEqual(journal.pending['real'], original_rows)
        self.assertEqual(effective['R_effective_known_pairs'], 3)
        self.assertEqual(effective['R_zero_effective_windows'], 1)
        self.assertEqual(effective['R_effective_unknown_pairs'], 0)
        self.assertEqual(journal.pending['R_mask_accounting_sha256'], m.digest(accounting))
        self.assertEqual(len(self.model.calls), 1)


if __name__ == '__main__': unittest.main()
