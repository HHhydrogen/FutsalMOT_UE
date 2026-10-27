"""有界Pose变化的训练输入、部分标准化与同帧shape负控制；不定义新模型。"""
from collections import Counter, OrderedDict, defaultdict
from copy import deepcopy
import hashlib
import math

from pose_velocity_feature_candidate import bounded_velocity_features
from pose_temporal_feature_candidate import CHANGED_COLUMNS

FIELDS = ('uid', 'bbox_xywh_px', 'score', 'xy_px', 'geometry_valid', 'timestamp_sec', 'image_wh')
MASK_COLUMNS = tuple(24 + 10 * j + k for j in range(17) for k in (6, 7, 8))
SCHEMA = 'bounded_pose_velocity_adapter_v1'
SHUFFLE_SEED = 20261027


def require(ok, message):
    if not ok:
        raise ValueError(message)


def public(record):
    """身份、标签和来源目录不进入数值特征。"""
    require(set(FIELDS) <= set(record), '预测白名单字段缺失')
    return {key: deepcopy(record[key]) for key in FIELDS}


def windows(pool):
    return list(pool.values()) if isinstance(pool, dict) else list(pool)


def _same_unchanged_normalizer(base, changed):
    require(len(base['mean']) == len(base['std']) == len(changed['mean']) == len(changed['std']) == 194,
            '基础/变化normalizer必须194维')
    require(base['count'] == changed['count'], '仅更新34列时不能改变原拟合候选数')
    require(type(base['count']) is int and base['count'] > 0, '原标准化候选数必须为正整数')
    require(all(math.isfinite(x) for state in (base, changed) for name in ('mean', 'std') for x in state[name])
            and all(x >= .05 for state in (base, changed) for x in state['std']), '标准化参数非有限或低于原方差底限')
    require(all(base[name][i] == changed[name][i] for name in ('mean', 'std')
                for i in range(194) if i not in CHANGED_COLUMNS), '其他160列标准化参数改变')


class VelocityAdapter:
    """网络仍是原gated；使用历史记录生成新raw，gate取目标原扰动raw。"""
    def __init__(self, numeric, base_normalizer, normalizer, quality_scale, velocity_clip, fit):
        require(math.isfinite(quality_scale) and quality_scale >= .03, '原trainR质量scale无效')
        require(math.isfinite(velocity_clip) and velocity_clip > 0, '仅trainR拟合的速度界限必须为正')
        _same_unchanged_normalizer(base_normalizer.state(), normalizer.state())
        self.numeric = numeric
        self.base_normalizer = base_normalizer
        self.normalizer = normalizer
        self.source_adapter = numeric.Adapter(base_normalizer, quality_scale)
        self.quality_scale = float(quality_scale)
        self.velocity_clip = float(velocity_clip)
        self.fit = deepcopy(fit)

    def transform_pair(self, history, candidate, *, original_history=None, original_candidate=None):
        """shuffle先完整重算shape特征；原未打乱记录只供motion/mask/gate一致性。"""
        h = [public(x) for x in history]
        p = public(candidate)
        original_h = h if original_history is None else [public(x) for x in original_history]
        original_p = p if original_candidate is None else public(original_candidate)
        raw = self.numeric.features(h, p)
        original_raw = self.numeric.features(original_h, original_p)
        require(raw[:24] == original_raw[:24] and all(raw[k] == original_raw[k] for k in MASK_COLUMNS),
                'shape负控制改变motion或mask/coverage，必须由cache回退')
        changed, _ = bounded_velocity_features(raw, h, p, self.velocity_clip)
        require(all(changed[k] == raw[k] for k in range(194) if k not in CHANGED_COLUMNS),
                '有界速度变换越过34列')
        values = self.normalizer.transform(changed, use_pose=True)
        if raw == original_raw:
            base_values = self.base_normalizer.transform(original_raw, use_pose=True)
            require(all(values[k] == base_values[k] for k in range(194) if k not in CHANGED_COLUMNS),
                    '真T的其他160个标准化特征改变')
        gate = self.source_adapter.transform(original_raw, use_pose=True)[-1]
        result = values + [gate]
        require(len(result) == 195 and all(math.isfinite(x) for x in result), '195维输入非有限或维度改变')
        return result

    def transform(self, raw, *, history=None, candidate=None, use_pose=True):
        """旧单raw调用不足以恢复时间顺序，不猜测速度；追踪器须显式传历史。"""
        require(use_pose is True and history is not None and candidate is not None,
                '速度adapter必须提供实际history/candidate，不能仅传旧194维raw')
        require(list(raw) == self.numeric.features([public(x) for x in history], public(candidate)),
                'raw与实际历史/候选不一致')
        return self.transform_pair(history, candidate)

    def state(self):
        return dict(schema=SCHEMA, feature_dim=195, model_variant='gated', changed_columns=list(CHANGED_COLUMNS),
            normalizer=self.normalizer.state(), base_normalizer=self.base_normalizer.state(),
            quality_scale=self.quality_scale, velocity_clip=self.velocity_clip, fit=deepcopy(self.fit),
            gate_source='original_unshuffled_after_same_v9_augmentation_raw',
            motion_and_mask_source='unchanged_target_prediction', normalizer_fit='known_label_clean_base_R_only')

    @classmethod
    def from_state(cls, state, numeric):
        require(state.get('schema') == SCHEMA and state.get('feature_dim') == 195
                and state.get('model_variant') == 'gated' and state.get('changed_columns') == list(CHANGED_COLUMNS)
                and state.get('gate_source') == 'original_unshuffled_after_same_v9_augmentation_raw'
                and state.get('motion_and_mask_source') == 'unchanged_target_prediction'
                and state.get('normalizer_fit') == 'known_label_clean_base_R_only', '有界变化adapter身份不同')
        require(state.get('fit', {}).get('known_pairs') == state['base_normalizer']['count']
                and state.get('fit', {}).get('fit_scope') == 'known_label_clean_base_R_only', '拟合账本与基础R不对应')
        return cls(numeric, numeric.FeatureNormalizer.from_state(state['base_normalizer']),
                   numeric.FeatureNormalizer.from_state(state['normalizer']), state['quality_scale'],
                   state['velocity_clip'], state['fit'])


def fit_adapter(numeric, base_normalizer, quality_scale, real_windows, velocity_clip):
    """只拟合clean已知label基础R的34列；R/RS/打乱组共享同一拟合。"""
    original = deepcopy(base_normalizer.state())
    changed = deepcopy(original)
    means = [0.] * len(CHANGED_COLUMNS)
    m2 = [0.] * len(CHANGED_COLUMNS)
    n = 0
    pool = windows(real_windows)
    games = set()
    sequences = set()
    for window in pool:
        require(window.get('domain') == 'real' and window.get('game') in ('game4', 'game6', 'game9'),
                '标准化只能使用允许基础R，不能外部/合成')
        games.add(window['game'])
        sequences.add(window['sequence'])
        h = [public(x) for x in window['history']]
        for candidate in window['candidates']:
            if candidate['label'] is None:
                continue
            require(type(candidate['label']) is int and candidate['label'] in (0, 1), '未知标签不得伪装已知监督')
            prediction = public(candidate['prediction'])
            raw = numeric.features(h, prediction)
            row, _ = bounded_velocity_features(raw, h, prediction, velocity_clip)
            n += 1
            for j, column in enumerate(CHANGED_COLUMNS):
                delta = row[column] - means[j]
                means[j] += delta / n
                m2[j] += delta * (row[column] - means[j])
    require(n > 0 and len(games) <= 2 and n == original['count'],
            '基础R已知pair数/允许两比赛与原normalizer拟合不对应')
    for j, column in enumerate(CHANGED_COLUMNS):
        changed['mean'][column] = means[j]
        changed['std'][column] = max(math.sqrt(max(0., m2[j] / n)), .05)
    _same_unchanged_normalizer(original, changed)
    fit = dict(fit_scope='known_label_clean_base_R_only', windows=len(pool), known_pairs=n,
               games=sorted(games), sequences=sorted(sequences), std_floor=.05, clip_abs=5.)
    return VelocityAdapter(numeric, base_normalizer, numeric.FeatureNormalizer.from_state(changed),
                           quality_scale, velocity_clip, fit)


def build_causal_shuffle_bank(pools, shuffle_seed=SHUFFLE_SEED):
    """仅固定pool观测；显式sequence/实际时间分帧，GT/标签不参与供体选择。"""
    records = defaultdict(dict)
    frame_keys = defaultdict(dict)
    groups = defaultdict(list)
    for domain, pool in pools.items():
        for window in windows(pool):
            require(window.get('domain') == domain and isinstance(window.get('sequence'), str), 'pool来源域/sequence不符')
            sequence = window['sequence']
            for value in window['history'] + [c['prediction'] for c in window['candidates']]:
                record = public(value)
                uid = record['uid']
                frame = (sequence, record['timestamp_sec'], tuple(record['image_wh']))
                if uid in records[domain]:
                    require(records[domain][uid] == record and frame_keys[domain][uid] == frame,
                            '同UID在pool中出现不同原预测/源帧')
                    continue
                require(len(record['geometry_valid']) == 17 and all(type(x) is bool for x in record['geometry_valid']),
                        '原mask必须17个bool')
                records[domain][uid] = record
                frame_keys[domain][uid] = frame
                scale = record['bbox_xywh_px'][3] / record['image_wh'][1]
                bucket = sum(scale >= edge for edge in (.03, .06, .12, .24))
                key = (domain, frame, bucket, tuple(record['geometry_valid']))
                groups[key].append(uid)
    mapping = defaultdict(dict)
    reasons = defaultdict(dict)
    for key, uids in groups.items():
        domain, frame, _, mask = key
        if not any(mask) or len(uids) < 2:
            for uid in uids:
                reasons[domain][uid] = 'no_valid_pose' if not any(mask) else 'no_same_frame_compatible_donor'
            continue
        ordered = sorted(uids, key=lambda uid: hashlib.sha256(
            f'{shuffle_seed}|{domain}|{frame}|{uid}'.encode()).hexdigest())
        for i, uid in enumerate(ordered):
            mapping[domain][uid] = ordered[(i + 1) % len(ordered)]
    counts = dict(observations=sum(len(v) for v in records.values()),
                  mapped_observations=sum(len(v) for v in mapping.values()),
                  unchanged_reasons=dict(Counter(x for values in reasons.values() for x in values.values())),
                  source_scope='all_observations_in_fixed_pools_not_complete_raw_frames',
                  same_frame=True, exact_original_mask=True, GT_used=False, future_used=False,
                  shuffle_seed=shuffle_seed)
    return dict(records=dict(records), mapping=dict(mapping), reasons=dict(reasons), statistics=counts)


def mapped_same_frame_shape(target, donor):
    """增广前将同帧供体形状映射到目标原框；保留目标UID以共享原扰动抽样。"""
    require(target['timestamp_sec'] == donor['timestamp_sec'] and target['image_wh'] == donor['image_wh'],
            '供体不是同一实际时间/图像域')
    if target['geometry_valid'] != donor['geometry_valid']:
        return None, 'original_mask_mismatch'
    out = public(target)
    x, y, w, h = target['bbox_xywh_px']
    a, b, c, d = donor['bbox_xywh_px']
    width, height = target['image_wh']
    for joint, valid in enumerate(target['geometry_valid']):
        if not valid:
            continue
        px, py = donor['xy_px'][joint]
        qx = x + w / 2 + (px - a - c / 2) / c * w
        qy = y + h / 2 + (py - b - d / 2) / d * h
        if not (math.isfinite(qx) and math.isfinite(qy) and 0 <= qx < width and 0 <= qy < height):
            return None, 'mapped_point_outside_image'
        out['xy_px'][joint] = [qx, qy]
    return out, 'shuffled' if out['xy_px'] != target['xy_px'] else 'identical_shape'


class LearningCache:
    """复用原v9逐UID/domain/epoch both增广与256MiB/4096观测界限。"""
    def __init__(self, numeric, pools, adapter, seed, shuffle=False):
        self.numeric = numeric
        self.pools = {domain: (pool if isinstance(pool, dict) else {w['window_uid']: w for w in pool})
                      for domain, pool in pools.items()}
        self.adapter = adapter
        self.seed = seed
        self.shuffle = bool(shuffle)
        self.cache = OrderedDict()
        self.observations = OrderedDict()
        self.transformed = OrderedDict()
        self.bytes = self.peak = 0
        self.seen_shuffle = set()
        self.seen_materialized = set()
        self.bank = build_causal_shuffle_bank(self.pools) if self.shuffle else None
        self.stats = dict(augmentation='original_v9_both', observation_cache_limit=4096,
                          feature_cache_limit_bytes=268435456, feature_cache_hits=0,
                          feature_windows_materialized=0, observation_cache_hits=0,
                          observation_cache_misses=0, shuffle_unique_attempts=0,
                          shuffle_reasons={}, original_gate_preserved=True, GT_donor_selection=False,
                          future_donor_used=False, closed=False,
                          shuffle_augmentation='mapped_raw_shape_then_original_recipient_uid_seed',
                          by_domain={domain: dict(known_pairs_materialized=0, pairs_with_changed_full_shape=0,
                              pairs_with_changed_features=0, unchanged_pairs=0) for domain in self.pools})
        if self.bank is not None:
            self.stats['shuffle_bank'] = deepcopy(self.bank['statistics'])

    def observation(self, domain, record, epoch):
        key = (domain, record['uid'], epoch)
        if key in self.observations:
            value = self.observations.pop(key)
            self.observations[key] = value
            self.stats['observation_cache_hits'] += 1
            return value
        _, value = self.numeric.perturb([], public(record), 'both', seed=self.seed, context=f'{domain}|{epoch}')
        self.stats['observation_cache_misses'] += 1
        self.observations[key] = value
        while len(self.observations) > 4096:
            self.observations.popitem(last=False)
        return value

    def shape_observation(self, domain, record, epoch):
        original = self.observation(domain, record, epoch)
        if not self.shuffle:
            return original
        key = (domain, record['uid'], epoch)
        if key in self.transformed:
            value = self.transformed.pop(key)
            self.transformed[key] = value
            return value
        source = self.bank['records'][domain]
        require(source[record['uid']] == public(record), '打乱原观测与固定pool字节不同')
        donor_uid = self.bank['mapping'].get(domain, {}).get(record['uid'])
        if donor_uid is None:
            value = original
            reason = self.bank['reasons'][domain][record['uid']]
        else:
            mapped, reason = mapped_same_frame_shape(public(record), source[donor_uid])
            if mapped is None:
                value = original
            else:
                # 映射后仍是目标UID，原v9因此使用与真T相同的drop/jitter随机数。
                _, value = self.numeric.perturb([], mapped, 'both', seed=self.seed, context=f'{domain}|{epoch}')
                value = public(value)
                if any(value[name] != original[name] for name in FIELDS if name != 'xy_px'):
                    value, reason = original, 'recipient_augmentation_mask_or_metadata_mismatch'
                else:
                    reason = 'shuffled' if value['xy_px'] != original['xy_px'] else 'identical_shape'
        if key not in self.seen_shuffle:
            self.seen_shuffle.add(key)
            self.stats['shuffle_unique_attempts'] += 1
            reasons = self.stats['shuffle_reasons']
            reasons[reason] = reasons.get(reason, 0) + 1
        self.transformed[key] = value
        while len(self.transformed) > 4096:
            self.transformed.popitem(last=False)
        return value

    def get(self, domain, row):
        import torch
        require(domain in self.pools and row.get('domain', domain) == domain and type(row['epoch']) is int
                and row['epoch'] >= 0, '实际曝光域/epoch不符')
        key = (domain, row['window_uid'], row['epoch'])
        if key in self.cache:
            value, size = self.cache.pop(key)
            self.cache[key] = (value, size)
            self.stats['feature_cache_hits'] += 1
            return value
        window = self.pools[domain][row['window_uid']]
        require(window['domain'] == domain and window['window_uid'] == row['window_uid'], '曝光UID对应窗口不同')
        original_history = [self.observation(domain, r, row['epoch']) for r in window['history']]
        history = [self.shape_observation(domain, r, row['epoch']) for r in window['history']]
        vectors = []
        labels = []
        changed_shape = changed_features = 0
        for candidate in window['candidates']:
            if candidate['label'] is None:
                continue
            require(type(candidate['label']) is int and candidate['label'] in (0, 1), '监督标签无效')
            record = candidate['prediction']
            original = self.observation(domain, record, row['epoch'])
            prediction = self.shape_observation(domain, record, row['epoch'])
            vector = self.adapter.transform_pair(history, prediction,
                original_history=original_history, original_candidate=original)
            vectors.append(vector)
            if self.shuffle:
                changed_shape += self.numeric.features(history, prediction) != self.numeric.features(original_history, original)
                changed_features += vector != self.adapter.transform_pair(original_history, original)
            labels.append(candidate['label'])
        require(labels, '不能跳过无已知监督窗口或伪造预算')
        value = dict(x=torch.tensor(vectors, dtype=torch.float32), labels=torch.tensor(labels, dtype=torch.float32),
                     known_pairs=len(labels), candidate_pairs=len(window['candidates']))
        size = sum(value[k].numel() * value[k].element_size() for k in ('x', 'labels'))
        while self.cache and self.bytes + size > 268435456:
            _, (_, previous) = self.cache.popitem(last=False)
            self.bytes -= previous
        self.cache[key] = (value, size)
        self.bytes += size
        self.peak = max(self.peak, self.bytes)
        self.stats['feature_windows_materialized'] += 1
        if key not in self.seen_materialized:
            self.seen_materialized.add(key)
            counts = self.stats['by_domain'][domain]
            counts['known_pairs_materialized'] += len(labels)
            counts['pairs_with_changed_full_shape'] += changed_shape
            counts['pairs_with_changed_features'] += changed_features
            counts['unchanged_pairs'] += len(labels) - changed_features
        return value

    def close(self):
        self.cache.clear()
        self.observations.clear()
        self.transformed.clear()
        self.seen_shuffle.clear()
        self.seen_materialized.clear()
        if self.bank is not None:
            for key in ('records', 'mapping', 'reasons'):
                self.bank[key].clear()
        self.bytes = 0
        self.stats['closed'] = True


# 新runtime的约定入口名；不改原冻结Adapter或模型类。
Adapter = VelocityAdapter
