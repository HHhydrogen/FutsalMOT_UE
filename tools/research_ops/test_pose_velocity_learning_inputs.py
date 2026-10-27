"""仅小型CPU夹具：原纯函数、输入边界、完整shape干预和覆盖记账。"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import math
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'python/src'), str(ROOT / 'tools/research_ops')]
from grf_ue_bridge.learned_association_features_v8 import features
from grf_ue_bridge.learned_association_model_v8 import FeatureNormalizer
from grf_ue_bridge.pose_quality_features_v9 import perturb
from grf_ue_bridge.quality_residual_association_v9 import Adapter as OriginalAdapter
from pose_temporal_feature_candidate import CHANGED_COLUMNS
from pose_velocity_learning_inputs import (Adapter, MASK_COLUMNS, LearningCache, build_causal_shuffle_bank,
                                           fit_adapter, mapped_same_frame_shape)


NUMERIC = SimpleNamespace(features=features, perturb=perturb, FeatureNormalizer=FeatureNormalizer,
                          Adapter=OriginalAdapter)


def record(uid, time, person, step):
    box = [220. + person * 150., 140., 100., 220.]
    shape = .08 + person * .07 + step * (.025 if person == 0 else -.018)
    return dict(uid=uid, bbox_xywh_px=box, score=.9, timestamp_sec=time, image_wh=[1280, 720],
                geometry_valid=[True] * 17,
                xy_px=[[box[0] + 50 + 100 * (shape + j * .001),
                        box[1] + 110 + 220 * (.02 * person + step * .01 - j * .001)] for j in range(17)])


def fixture():
    history = [[record(f'p{p}_h{i}', i * .04, p, i) for i in range(3)] for p in range(2)]
    current = [record(f'p{p}_c', .12, p, 3) for p in range(3)]
    pool = {}
    for p in range(2):
        uid = f'w{p}'
        pool[uid] = dict(window_uid=uid, domain='real', game='game4', sequence='SNMOT060',
                         history=history[p], candidates=[
                             dict(label=1 if q == p else 0, prediction=current[q]) for q in range(2)]
                         + [dict(label=None, prediction=current[2])])
    rows = [features(w['history'], c['prediction']) for w in pool.values()
            for c in w['candidates'] if c['label'] is not None]
    base = FeatureNormalizer.fit(rows)
    return pool, base, fit_adapter(NUMERIC, base, .1, pool, 2.)


class FakeTensor:
    """只核验cache计数/顺序；真实Torch与梯度由独立准入负责。"""
    def __init__(self, values): self.values = deepcopy(values)
    def numel(self):
        return sum(len(x) if isinstance(x, list) else 1 for x in self.values)
    def element_size(self): return 4
    def tolist(self): return deepcopy(self.values)


FAKE_TORCH = SimpleNamespace(tensor=lambda values, dtype: FakeTensor(values), float32='fixture_float32')


class VelocityLearningInputsTests(unittest.TestCase):
    def test_only_34_normalizer_columns_and_round_trip(self):
        pool, base, adapter = fixture()
        before, after = base.state(), adapter.state()['normalizer']
        self.assertEqual(before['count'], 4)
        self.assertTrue(any(before['mean'][i] != after['mean'][i] for i in CHANGED_COLUMNS))
        for i in set(range(194)) - set(CHANGED_COLUMNS):
            self.assertEqual((before['mean'][i], before['std'][i]), (after['mean'][i], after['std'][i]))
        w = pool['w0']; candidate = w['candidates'][0]['prediction']
        vector = adapter.transform_pair(w['history'], candidate)
        old = OriginalAdapter(base, .1).transform(features(w['history'], candidate))
        self.assertEqual(vector[-1], old[-1])
        self.assertTrue(all(vector[i] == old[i] for i in set(range(194)) - set(CHANGED_COLUMNS)))
        self.assertEqual(vector, Adapter.from_state(adapter.state(), NUMERIC).transform_pair(w['history'], candidate))
        with self.assertRaises(ValueError): adapter.transform(features(w['history'], candidate))
        broken = adapter.state(); broken['normalizer']['mean'][0] += 1
        with self.assertRaises(ValueError): Adapter.from_state(broken, NUMERIC)
        broken = adapter.state(); broken['normalizer']['std'][CHANGED_COLUMNS[0]] = float('nan')
        with self.assertRaises(ValueError): Adapter.from_state(broken, NUMERIC)

    def test_only_known_clean_base_R_may_fit(self):
        pool, base, _ = fixture()
        bad = deepcopy(pool); bad['w0']['domain'] = 'external_validation_only'
        with self.assertRaises(ValueError): fit_adapter(NUMERIC, base, .1, bad, 2.)
        bad = deepcopy(pool); bad['w0']['game'] = 'synthetic1048'
        with self.assertRaises(ValueError): fit_adapter(NUMERIC, base, .1, bad, 2.)
        bad = deepcopy(pool); bad['w0']['candidates'][0]['label'] = True
        with self.assertRaises(ValueError): fit_adapter(NUMERIC, base, .1, bad, 2.)
        changed_count = FeatureNormalizer(base.mean, base.std, base.count + 1)
        with self.assertRaises(ValueError): fit_adapter(NUMERIC, changed_count, .1, pool, 2.)

    def test_bank_does_not_read_labels_or_cross_frame_sequence_scale_mask(self):
        pool, _, _ = fixture()
        original = build_causal_shuffle_bank({'real': pool})
        changed = deepcopy(pool)
        for w in changed.values():
            for c in w['candidates']: c['label'] = 'GT不可读取'
        self.assertEqual(original['mapping'], build_causal_shuffle_bank({'real': changed})['mapping'])
        changed = deepcopy(pool); changed['w1']['sequence'] = 'other_actual_camera'
        with self.assertRaises(ValueError): build_causal_shuffle_bank({'real': changed})
        for boundary in ('sequence', 'time', 'scale', 'mask'):
            changed = deepcopy(pool)
            # 夹具两窗共享current字典；新来源须先断开该共享引用再赋新UID。
            other = changed['w1'] = deepcopy(changed['w1'])
            for r in other['history'] + [c['prediction'] for c in other['candidates']]:
                r['uid'] += '_independent'
                if boundary == 'time': r['timestamp_sec'] += .001
                elif boundary == 'scale': r['bbox_xywh_px'][3] = 10.
                elif boundary == 'mask': r['geometry_valid'][0] = False
            if boundary == 'sequence': other['sequence'] = 'other_actual_camera'
            separate = build_causal_shuffle_bank({'real': changed})
            self.assertNotIn('p0_h0', separate['mapping'].get('real', {}))
        for uid, donor in original['mapping']['real'].items():
            a, b = original['records']['real'][uid], original['records']['real'][donor]
            self.assertNotEqual(uid, donor)
            self.assertEqual((a['timestamp_sec'], a['image_wh'], a['geometry_valid']),
                             (b['timestamp_sec'], b['image_wh'], b['geometry_valid']))

    def test_recipient_seed_and_full_shape_control_preserve_gate_motion_masks(self):
        pool, _, adapter = fixture(); cache = LearningCache(NUMERIC, {'real': pool}, adapter, 20261024, shuffle=True)
        w = pool['w0']; item = w['history'][-1]
        donor_uid = cache.bank['mapping']['real'][item['uid']]
        donor = cache.bank['records']['real'][donor_uid]
        mapped, _ = mapped_same_frame_shape(item, donor)
        expected = perturb([], mapped, 'both', seed=20261024, context='real|0')[1]
        actual = cache.shape_observation('real', item, 0)
        original = cache.observation('real', item, 0)
        self.assertEqual(actual, expected)
        self.assertEqual(actual['uid'], item['uid'])
        self.assertEqual(actual['geometry_valid'], original['geometry_valid'])
        self.assertNotEqual(actual['xy_px'], original['xy_px'])
        with patch.dict(sys.modules, {'torch': FAKE_TORCH}):
            value = cache.get('real', dict(window_uid='w0', epoch=0))
            same = cache.get('real', dict(window_uid='w0', epoch=0))
        self.assertIs(value, same)
        self.assertEqual((value['known_pairs'], value['candidate_pairs'], value['labels'].tolist()), (2, 3, [1, 0]))
        h = [cache.observation('real', r, 0) for r in w['history']]
        p = cache.observation('real', w['candidates'][0]['prediction'], 0)
        baseline = adapter.transform_pair(h, p)
        vector = value['x'].tolist()[0]
        self.assertEqual(vector[:24], baseline[:24])
        self.assertTrue(all(vector[i] == baseline[i] for i in MASK_COLUMNS))
        self.assertEqual(vector[-1], baseline[-1])
        shape_columns = set(range(24, 194)) - set(CHANGED_COLUMNS) - set(MASK_COLUMNS)
        self.assertTrue(any(vector[i] != baseline[i] for i in shape_columns))
        counts = cache.stats['by_domain']['real']
        self.assertEqual(counts['known_pairs_materialized'], 2)
        self.assertGreater(counts['pairs_with_changed_full_shape'], 0)
        self.assertGreater(counts['pairs_with_changed_features'], 0)
        self.assertEqual(counts['pairs_with_changed_features'] + counts['unchanged_pairs'], 2)
        self.assertGreater(cache.peak, 0)
        cache.close(); self.assertTrue(cache.stats['closed']); self.assertEqual(cache.bytes, 0)

    def test_post_augmentation_mask_mismatch_falls_back_and_counts(self):
        pool, _, adapter = fixture()
        originals = {r['uid']: r for w in pool.values()
                     for r in w['history'] + [c['prediction'] for c in w['candidates']]}
        def incompatible(history, candidate, mode, seed, context):
            h, p = perturb(history, candidate, mode, seed=seed, context=context)
            if candidate['xy_px'] != originals[candidate['uid']]['xy_px']:
                p['geometry_valid'][0] = not p['geometry_valid'][0]
            return h, p
        numeric = SimpleNamespace(**vars(NUMERIC)); numeric.perturb = incompatible
        cache = LearningCache(numeric, {'real': pool}, adapter, 20261024, shuffle=True)
        item = pool['w0']['history'][0]
        self.assertEqual(cache.shape_observation('real', item, 0), cache.observation('real', item, 0))
        self.assertEqual(cache.stats['shuffle_reasons']['recipient_augmentation_mask_or_metadata_mismatch'], 1)
        self.assertEqual(cache.stats['shuffle_unique_attempts'], 1)
        cache.shape_observation('real', item, 0)
        self.assertEqual(cache.stats['shuffle_unique_attempts'], 1)


if __name__ == '__main__':
    unittest.main()
