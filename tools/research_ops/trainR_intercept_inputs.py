"""截距校准的原冻结模型与1000 clean R输入；仅准备，不前向、不拟合、不写盘。"""
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from threading import RLock
from types import MappingProxyType

R = Path('D:/projects/FutsalMOT_Research')
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
WINDOWS, FEATURE_DIM, MOTION_DIM = 1000, 194, 24
MAX_CACHE_ENTRIES, MAX_CACHE_BYTES = 3, 256 * 1024 * 1024
_CACHE = OrderedDict()
_CACHE_BYTES = 0
_LOCK = RLock()
_SCOPED_NAMES = ('grf_ue_bridge', 'v8_train', 'v9_train', 'v10_original_v9_numeric', 'v10_runtime_storage')
_MODULE_PREFIX = '_trainR_intercept_frozen_'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def safe(value):
    path = Path(value)
    require(path.is_absolute(), '来源必须绝对物理路径')
    path = Path(os.path.abspath(path))
    require(R in path.parents and not any(part.lower() == 'test' or
        re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower()) for part in path.parts), '只允许研究根内来源，最终测试继续封存')
    for parent in (path, *path.parents):
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    '不跟随junction或链接')
    return path


def data_path(reference):
    require(isinstance(reference, dict) and set(reference) >= {'path', 'sha256'} and
            re.fullmatch('[0-9a-f]{64}', reference['sha256']), '必须完整SHA来源引用')
    path = safe(reference['path'])
    require(path.is_file(), '实际来源不存在：' + str(path))
    return path


def checked(reference):
    path = data_path(reference)
    content = path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == reference['sha256'], '来源SHA改变：' + str(path))
    return path, content


def read(reference):
    path, content = checked(reference)
    require(path.suffix == '.json' and path.name not in ('gap_registry.json', 'posthoc_GT_labels.json'),
            '只读明确训练小元数据，不读取验证GT')
    return json.loads(content.decode('utf-8-sig'))


def _source(bundle_cfg, relative):
    bundle = safe(bundle_cfg['bundle'])
    require(bundle.parent == R / 'code', '仅原内容寻址源码bundle')
    manifest = read(bundle_cfg['bundle_manifest'])
    entries = [entry for entry in manifest['files'] if entry['path'] == relative]
    require(len(entries) == 1, '原源码清单入口缺失：' + relative)
    path = safe(bundle / relative)
    require(bundle in path.parents, '源码相对路径越界')
    reference = dict(path=str(path), sha256=entries[0]['sha256'])
    checked(reference)
    return reference


def _protocol(spec):
    protocol = read(spec['loader']['protocol'])
    return protocol


def _v8_protocol(spec):
    protocol = _protocol(spec)
    if spec['regime'] == 'RS':
        protocol = read(protocol['v8_protocol'])
    return protocol


def _scoped(name):
    return name.startswith(_MODULE_PREFIX) or any(name == prefix or name.startswith(prefix + '.') for prefix in _SCOPED_NAMES)


@contextmanager
def frozen_import_scope(bundle):
    """隔离旧e21与f473的同名数值模块；不重载Torch/NumPy，不改旧module globals。"""
    with _LOCK:
        saved_path = sys.path[:]
        saved_bytecode = sys.dont_write_bytecode
        saved = {key: value for key, value in sys.modules.items() if _scoped(key)}
        for key in saved:
            del sys.modules[key]
        sys.path[:0] = [str(bundle / 'python/src'), str(bundle / 'tools/research_ops'),
                       str(bundle / 'tools/performance'), str(R / 'runtime_dependencies')]
        sys.dont_write_bytecode = True
        try:
            yield
        finally:
            for key in list(sys.modules):
                if _scoped(key):
                    del sys.modules[key]
            sys.modules.update(saved)
            sys.path[:] = saved_path
            sys.dont_write_bytecode = saved_bytecode


def _module(reference):
    path, _ = checked(reference)
    name = _MODULE_PREFIX + reference['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _validate_spec(spec):
    require(spec.get('regime') in ('R', 'RS') and spec.get('fold') in FOLDS and spec.get('seed') in SEEDS
            and spec.get('architecture') == 'original_strong_motion_v8' and spec.get('use_pose') is False,
            '仅原18强motion冻结模型，不读取Pose分支或其他seed')
    binding = spec['binding']
    require(binding['fold'] == spec['fold'] and binding['seed'] == spec['seed'] and
            binding['protocol_sha256'] == spec['loader']['protocol']['sha256'], '模型/协议绑定不同')
    require((spec['regime'] == 'R' and binding.get('arm') == 'motion_R') or
            (spec['regime'] == 'RS' and binding.get('method') == 'motion' and binding.get('pool') == 'balanced'
             and binding.get('regime') == 'RS'), '不能用Pose/hard/其他模型冒充原R或平衡RS')
    require(spec['calibration']['augmentation'] is False and spec['calibration']['training_S_read'] is False
            and spec['calibration']['optimizer_SGD_updates'] == 0 and spec['calibration']['extra_clean_R_window_evaluations'] == WINDOWS,
            '额外1000原R校准预算不能改成S/增广/SGD')


def load_model(spec, device='cpu'):
    """调用原模型完整性入口；仅此API加载Torch/权重，默认CPU FP32，一次不做前向。"""
    _validate_spec(spec)
    require(device == 'cpu' or re.fullmatch(r'cuda(?::\d+)?', str(device)), '设备必须显式CPU或CUDA')
    loader = spec['loader']
    protocol = _protocol(spec)
    bundle = safe(protocol['bundle'])
    expected_name = 'v8_track.py' if spec['regime'] == 'R' else 'v10_runtime.py'
    require(loader['module'] == _source(protocol, 'tools/research_ops/' + expected_name), '必须原已验loader源码')
    normalizer_state = read(spec['normalizer'])
    run = safe(spec['run'])
    require(data_path(spec['training_receipt']) == run / 'run_receipt.json', '原训练run/收据路径不同')
    checkpoint = data_path(spec['checkpoint'])  # 字节/SHA由原loader实际核对，不重复读取权重。
    require(checkpoint == (run / 'last.pt' if spec['regime'] == 'R' else run / 'checkpoints/step_1000.pt'), '必须原last1000权重')
    receipt = read(spec['training_receipt'])
    require(receipt['binding'] == spec['binding'] and receipt['status'] == 'complete' and receipt['completed_updates'] == 1000,
            '原模型实际训练收据不同')
    require((spec['regime'] == 'R' and receipt['checkpoint_sha256'] == spec['checkpoint']['sha256']) or
            (spec['regime'] == 'RS' and receipt['checkpoint'] == spec['checkpoint']), '权重引用未绑定原收据')
    with frozen_import_scope(bundle):
        module = _module(loader['module'])
        if spec['regime'] == 'R':
            require(loader['function'] == 'load_complete' and loader['return_contract'] == 'model,normalizer,binding', '原R入口契约不同')
            model, normalizer, binding = module.load_complete(run, protocol, loader['protocol']['sha256'], spec['fold'])
        else:
            require(loader['function'] == 'complete_model' and loader['return_contract'] == 'cfg,numeric,model,adapter,binding', '原RS入口契约不同')
            _, _, model, normalizer, binding = module.complete_model(data_path(loader['protocol']), run)
        import torch
        require(binding == spec['binding'] and normalizer.state() == normalizer_state, '实际模型身份/normalizer与冻结来源不同')
        require(all(value.dtype == torch.float32 for value in model.state_dict().values()), '实际原模型参数必须全FP32')
        model.to(device=device)
        model.eval()
        model.requires_grad_(False)
    return dict(model=model, normalizer=normalizer, binding=deepcopy(binding), receipt=dict(
        schema='trainR_intercept_loaded_original_motion_model_v1', model_id=spec['model_id'], regime=spec['regime'],
        fold=spec['fold'], seed=spec['seed'], checkpoint=deepcopy(spec['checkpoint']), loader=deepcopy(loader),
        binding=deepcopy(binding), device=str(device), actual_dtype='float32', model_forward_calls=0,
        original_complete_loader_used=True, input_Pose_used=False, model_parameters_frozen=True,
        new_optimizer_updates=0, validation_or_test_read=False))


def _inventory(cfg):
    inventory = cfg if cfg.get('schema') == 'trainR_intercept_source_inventory_v1' else cfg['inventory']
    if set(inventory) >= {'path', 'sha256'}:
        inventory = read(inventory)
    require(inventory.get('schema') == 'trainR_intercept_source_inventory_v1'
            and inventory.get('input_Pose_used') is False and inventory.get('feature_function') == 'features', '缺实际原模型/原特征来源清单')
    return inventory


def _validate_record(record, sequence, frame_index):
    uid = record.get('uid')
    require(type(uid) is str and re.fullmatch(re.escape(sequence) + r':\d{6}:\d{6}', uid) and
            int(uid.split(':')[1]) == frame_index + 1, '原图一基UID/缓存零基帧映射不同')
    timestamp = record.get('timestamp_sec')
    require(type(timestamp) in (int, float) and math.isfinite(timestamp) and
            abs(timestamp - frame_index / 25.) <= 1e-9, '原25FPS时间映射不同')
    return uid


def _materialize(window, fold_info, feature_fn, normalizer):
    require(window.get('domain') == 'real' and window.get('game') in fold_info['allowed_games'] and
            window.get('sequence') in fold_info['allowed_sequences'] and OLD.get(window['sequence']) == window['game'],
            '额外校准输入不得含S/heldout/验证或测试比赛')
    require(type(window.get('window_uid')) is str and re.fullmatch('[0-9a-f]{64}', window['window_uid'])
            and window.get('fps') == 25, '原窗口UID/帧率不同')
    history, indices = window['history'], window['history_frame_indices']
    current = window['candidate_frame_index']
    require(len(history) == len(indices) == 3 and all(type(index) is int and index >= 0 for index in indices)
            and indices == sorted(set(indices)) and type(current) is int and current > indices[-1]
            and window['candidate_frame_number'] == current + 1, '只准原有序历史，不读取未来帧')
    history_uids = tuple(_validate_record(record, window['sequence'], index) for record, index in zip(history, indices))
    candidates = window['candidates']
    require(isinstance(candidates, list), '全部候选必须原顺序列表')
    labels, candidate_uids, features = [], [], []
    for candidate in candidates:
        label = candidate['label']
        require(label is None or (type(label) is int and label in (0, 1)), '原标签只能0/1/None，unknown不伪造负例')
        prediction = candidate['prediction']
        uid = _validate_record(prediction, window['sequence'], current)
        raw = feature_fn(history, prediction)
        transformed = normalizer.transform(raw, use_pose=False)
        require(len(raw) == len(transformed) == FEATURE_DIM and all(type(value) in (int, float) and math.isfinite(value) for value in transformed)
                and all(value == 0. for value in transformed[MOTION_DIM:]), '原194维特征/标准化后motion遮蔽不同')
        labels.append(label); candidate_uids.append(uid); features.append(tuple(transformed))
    require(len(set(candidate_uids)) == len(candidate_uids), '同窗口候选UID重复')
    pair_uids = tuple(hashlib.sha256(canonical([window['window_uid'], history_uids, uid]).encode()).hexdigest() for uid in candidate_uids)
    return MappingProxyType(dict(window_uid=window['window_uid'], domain='real', game=window['game'], sequence=window['sequence'],
        source_uid=window['window_uid'], source_pool_row=None, history_UIDs=history_uids, candidate_UIDs=tuple(candidate_uids),
        pair_source_UIDs=pair_uids, features=tuple(features), labels=tuple(labels), known_mask=tuple(label is not None for label in labels),
        history_frame_indices=tuple(indices), candidate_frame_index=current, candidate_frame_number=current+1,
        epoch=0, augmentation=False, use_pose=False))


def _feature_dependencies(inventory, spec):
    old = _v8_protocol(spec)
    feature = _source(old, 'python/src/grf_ue_bridge/learned_association_features_v8.py')
    model = _source(old, 'python/src/grf_ue_bridge/learned_association_model_v8.py')
    require(feature == inventory['feature_source'] and model == inventory['normalizer_source'], '必须同一原194维特征/normalizer源码')
    return old, feature, model


def clear_feature_cache():
    global _CACHE_BYTES
    with _LOCK:
        _CACHE.clear(); _CACHE_BYTES = 0


def prepare_clean_R_windows(cfg, spec):
    """每fold仅物化一次全部1000原窗，缓存只共享输入，模型/输出logit从不入缓存。"""
    global _CACHE_BYTES
    _validate_spec(spec)
    inventory = _inventory(cfg)
    require(any(model == spec for model in inventory['models']), '模型不属完整已签18来源清单')
    fold_info = inventory['folds'][spec['fold']]
    require(spec['clean_R_pool'] == fold_info['clean_R_pool'] and spec['normalizer'] == fold_info['normalizer']
            and set(fold_info['allowed_games']) == set(FOLDS) - {spec['fold']}
            and set(fold_info['allowed_sequences']) == {seq for seq, game in OLD.items() if game != spec['fold']}, '原pool/normalizer/允许训练域改变')
    old, feature_source, model_source = _feature_dependencies(inventory, spec)
    key = hashlib.sha256(canonical(dict(fold=spec['fold'], pool=spec['clean_R_pool'], normalizer=spec['normalizer'],
        feature_source=feature_source, normalizer_source=model_source, use_pose=False, augmentation=False)).encode()).hexdigest()
    with _LOCK:
        hit = key in _CACHE
        if hit:
            entry = _CACHE.pop(key); _CACHE[key] = entry
        else:
            normalizer_state = read(spec['normalizer'])
            require(normalizer_state.get('schema') == 'v8_train_R_only_normalizer' and normalizer_state.get('fit_scope') == 'known_label_train_R_only',
                    '只复用原clean R标准化，不重新fit')
            pool_path = data_path(spec['clean_R_pool'])
            digest, windows, uids = hashlib.sha256(), [], set()
            with frozen_import_scope(safe(old['bundle'])):
                feature_module = importlib.import_module('grf_ue_bridge.learned_association_features_v8')
                model_module = importlib.import_module('grf_ue_bridge.learned_association_model_v8')
                require(Path(feature_module.__file__) == Path(feature_source['path']) and Path(model_module.__file__) == Path(model_source['path']), '误导入非冻结特征模块')
                normalizer = model_module.FeatureNormalizer.from_state(normalizer_state)
                require(normalizer.state() == normalizer_state, '原normalizer状态不完整')
                with pool_path.open('rb') as stream:
                    for line in stream:
                        digest.update(line)
                        require(line.strip(), '原pool不能含空行或隐式跳过')
                        window = _materialize(json.loads(line.decode('utf-8-sig')), fold_info, feature_module.features, normalizer)
                        require(window['window_uid'] not in uids and len(windows) < WINDOWS, '不能复制UID补足或超额选择')
                        uids.add(window['window_uid'])
                        window = dict(window); window['source_pool_row'] = len(windows)
                        windows.append(MappingProxyType(window))
            require(digest.hexdigest() == spec['clean_R_pool']['sha256'] and len(windows) == WINDOWS, '实际原pool SHA/1000唯一分母不同')
            windows = tuple(windows)
            labels = [label for window in windows for label in window['labels']]
            totals = dict(windows=WINDOWS, all_pair_count=len(labels), known_pair_count=sum(label is not None for label in labels),
                unknown_pair_count=sum(label is None for label in labels), positive_pair_count=labels.count(1), negative_pair_count=labels.count(0),
                empty_known_window_count=sum(not any(window['known_mask']) for window in windows))
            # 有界预算按Python对象实占大小估计；不是GPU内存/RSS或新增图像数。
            seen = set()
            def size(value):
                if id(value) in seen: return 0
                seen.add(id(value)); result = sys.getsizeof(value)
                if isinstance(value, (dict, MappingProxyType)): result += sum(size(k)+size(v) for k,v in value.items())
                elif isinstance(value, (list, tuple)): result += sum(size(v) for v in value)
                return result
            payload_bytes = size(windows)
            require(payload_bytes <= MAX_CACHE_BYTES, '单fold原特征超过有界缓存预算，拒绝无界物化')
            while _CACHE and (len(_CACHE) >= MAX_CACHE_ENTRIES or _CACHE_BYTES + payload_bytes > MAX_CACHE_BYTES):
                _, removed = _CACHE.popitem(last=False); _CACHE_BYTES -= removed['payload_bytes']
            entry = dict(windows=windows, payload_bytes=payload_bytes, totals=totals,
                order_sha256=hashlib.sha256(canonical([window['window_uid'] for window in windows]).encode()).hexdigest())
            _CACHE[key] = entry; _CACHE_BYTES += payload_bytes
        receipt = dict(schema='trainR_intercept_clean_R_inputs_v1', status='complete1000_original_clean_R_windows_all_candidates_retained',
            model_id=spec['model_id'], fold=spec['fold'], seed=spec['seed'], regime=spec['regime'], pool=deepcopy(spec['clean_R_pool']),
            normalizer=deepcopy(spec['normalizer']), feature_source=feature_source, normalizer_source=model_source,
            cache_key=key, cache_hit=hit, feature_cache_entries=len(_CACHE), feature_cache_payload_bytes=_CACHE_BYTES,
            cache_limit_bytes=MAX_CACHE_BYTES, cache_limit_entries=MAX_CACHE_ENTRIES, feature_dim=FEATURE_DIM, motion_columns=MOTION_DIM,
            pose_columns_zero_after_original_normalization=True, normalizer_fitted=False, augmentation=False,
            original_pool_order_UID_sha256=entry['order_sha256'], counts=deepcopy(entry['totals']),
            allowed_games=list(fold_info['allowed_games']), allowed_sequences=list(fold_info['allowed_sequences']),
            excluded_game=spec['fold'], objective_denominator=WINDOWS, empty_known_window_contribution=0,
            unknown_pairs_retained_not_fitted=True, planned_extra_R_model_window_evaluations=WINDOWS,
            actual_model_window_evaluations=0, model_forward_calls=0, new_optimizer_updates=0,
            independent_new_real_data_claim=False, strict_same_total_supervision_budget_claim=False,
            training_S_windows_read=False, validation_or_test_read=False)
        return dict(windows=entry['windows'], receipt=receipt, cache_key=key, cache_hit=hit)
