"""R候选评分资格mask的独立训练适配候选；不包含训练启动或旧预算重审计。"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = Path('D:/projects/FutsalMOT_Research')
EXPERIMENT = RESEARCH/'pose/r_candidate_eligibility_a01'
SOURCE_PROTOCOL = RESEARCH/'pose/state_aligned_training_a01/training_frozen_a01/protocol.json'
SOURCE_PROTOCOL_SHA = '2acc7642109c317b9ca694d3649a864c5553e177f20425d24726de1781c7d3c6'
SOURCE_COMPLETE_ROOT = RESEARCH/'pose/state_aligned_training_a01/training_complete_root_a01.json'
SOURCE_COMPLETE_ROOT_SHA = '62646594150716226b4cb90087731b8d2c76fb836bd22a3218a776031ebf5a33'
SOURCE_AUDIT = RESEARCH/'pose/state_aligned_training_a01/postrun_audit_a01/actual_budget.json'
SOURCE_AUDIT_SHA = 'd551bb377a8d33b6f454fa5f119723c06c085555c85c37c55b5080f53d671212'
FOLDS = ('game4', 'game6', 'game9'); SEEDS = (20261024, 20261025, 20261026); REGIMES = ('R', 'RS')
OBJECTIVE = 'R_original_known_BCE_pre_probability_candidate_eligibility_mask_S_original_BCE_alpha_1_over_3'
PARAMETERS = dict(updates=1000, R_per_step=3, S_per_RS_step=1, S_alpha=1/3, lr=.001, weight_decay=.0001,
    amp=False, prefetch=2, cache_bytes=268435456, checkpoint_interval=50, actual_dtype='float32',
    selection='last1000_no_best_not_EMA', network='194_64_32_1_ReLU_strongmotion', trainable_parameters=14593,
    use_pose=False, epoch_augmentation=False, R_objective='original_known_BCE_with_pre_probability_scoring_eligibility_mask',
    S_objective='original_known_pair_window_mean_BCE', full_original_known_forward_preserved=True,
    empty_effective_window='graph_zero_keep_fixed_mean3R_no_resampling_or_skipped_update')


def require(ok, message):
    if not ok: raise ValueError(message)


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def physical(path):
    p = Path(path); require(p.is_absolute(), '研究来源必须绝对路径'); p = Path(os.path.abspath(p))
    require(RESEARCH in p.parents and not any(x.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', x.lower()) for x in p.parts), '研究范围不同或涉及封存测试')
    for item in (p, *p.parents):
        if item.exists() or item.is_symlink(): require(not item.is_symlink() and not getattr(item.lstat(), 'st_file_attributes', 0) & 0x400, '禁止链接/junction')
    return p


def sha(path):
    h = hashlib.sha256()
    with physical(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): h.update(block)
    return h.hexdigest()


def checked(reference):
    path = physical(reference['path']); require(path.is_file() and sha(path) == reference['sha256'], '冻结来源SHA变化：'+str(path)); return path


def read_ref(reference): return read(checked(reference))
def expected_matrix(): return [dict(fold=f, seed=s, regime=g) for f in FOLDS for s in SEEDS for g in REGIMES]


def validate_matrix(cfg):
    require(cfg['schema'] == 'r_candidate_eligibility_recorded_training_protocol_v1' and cfg['training_matrix'] == expected_matrix()
        and cfg['parameters'] == PARAMETERS and cfg['approved_by'] == 'root' and cfg['training_authorized'] is True
        and cfg['tracking_authorized'] is False and cfg['test116187_sealed'] is True, '独立maskedBCE矩阵/绝对条件尚未授权冻结')
    require(set(cfg['mask_inputs']) == set(FOLDS), '三fold资格输入缺失')
    for key, path, expected_sha in [('source_training_protocol', SOURCE_PROTOCOL, SOURCE_PROTOCOL_SHA),
            ('source_training_complete_root', SOURCE_COMPLETE_ROOT, SOURCE_COMPLETE_ROOT_SHA), ('source_training_audit', SOURCE_AUDIT, SOURCE_AUDIT_SHA)]:
        require(Path(cfg[key]['path']) == path and cfg[key]['sha256'] == expected_sha, '原已验来源身份不同：'+key)


def validate_protocol(config):
    cfg = read(config); validate_matrix(cfg)
    require(Path(cfg['bundle']) == ROOT and ROOT.parent == RESEARCH/'code', '仅执行本轮新最小冻结bundle')
    manifest = read_ref(cfg['bundle_manifest'])
    require(ROOT.name == digest(manifest['files']), '执行bundle目录不是内容地址')
    for entry in manifest['files']: require(sha(ROOT/entry['path']) == entry['sha256'], '冻结执行源码改变')
    source = read_ref(cfg['source_training_protocol']); complete = read_ref(cfg['source_training_complete_root']); audit = read_ref(cfg['source_training_audit'])
    require(complete['status'] == 'complete18_state_aligned_training_actual_budget_records_exit_verified_not_tracking_complete'
        and complete['test_read'] is False and complete['budget_audit'] == cfg['source_training_audit']
        and complete['protocol'] == cfg['source_training_protocol'], '原训练完成根未绑定已验协议/审计')
    require(audit['status'] == 'complete18_state_aligned_R_actual_budget_full_records_and_exit_verified'
        and audit['training_processes_absent'] is True and audit['complete_checkpoints_read_back'] == 378
        and audit['test_read'] is False, '只读原预算完成小收据不足，不重审旧权重')
    for key, value in [('updates', 18000), ('R_windows', 54000), ('S_windows', 9000)]: require(audit['actual_totals'][key] == value, '原实际预算不同')
    require(checked(cfg['selected_R_bank_root']) == checked(source['input_root']), '必须同一原3000 R窗口来源，不能重建池')
    plan = read_ref(cfg['analysis_plan'])
    require(plan['status'] == 'frozen_before_numeric_admission_and_training' and plan['test116187_sealed'] is True, '结果前分析计划/封存不足')
    for fold in FOLDS: checked(cfg['mask_inputs'][fold])
    return cfg


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path); value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value; spec.loader.exec_module(value); return value


def load_source_runtime(config):
    cfg = validate_protocol(config); source = read_ref(cfg['source_training_protocol']); root = physical(source['bundle'])
    manifest = read_ref(source['bundle_manifest'])
    for entry in manifest['files']: require(sha(root/entry['path']) == entry['sha256'], '复用的原冻结源码改变')
    for name in ('state_aligned_training_inputs',):
        if name in sys.modules:
            require(physical(sys.modules[name].__file__) == physical(root/'tools/research_ops'/(name+'.py')), '原输入模块已被其他路径污染')
    sys.path[:0] = [str(root/'tools/research_ops'), str(root/'tools/performance')]
    original = module('r_eligibility_original_runtime_'+SOURCE_PROTOCOL_SHA, root/'tools/research_ops/state_aligned_training_runtime.py')
    return cfg, original


def bind_sidecars(pool, sidecars, *, supplied_bindings=None):
    """只绑定原1000唯一窗；不重新抽样、不修改pool/cache的known原字段。"""
    from r_candidate_eligibility_method import bind_window_mask, checked_binding
    require(len(pool) == len(sidecars) == 1000 and len({r['window_uid'] for r in sidecars}) == 1000, '每fold须1000唯一原窗口侧表')
    index = {r['window_uid']: r for r in sidecars}; require(set(index) == set(pool), '侧表遗漏或混入其他窗口')
    result = {uid: bind_window_mask(window, index[uid]) for uid, window in pool.items()}
    if supplied_bindings is not None:
        require(len(supplied_bindings) == 1000 and len({r['window_uid'] for r in supplied_bindings}) == 1000, '已验绑定清单重复/缺失')
        supplied = {r['window_uid']: checked_binding(r) for r in supplied_bindings}
        require(result == supplied, '侧表与已验绑定清单逐值不同')
    require(any(v['accounting']['kept_known_pairs'] > 0 for v in result.values()), '该fold全部有效监督为空，不得启动训练')
    return result


def jsonl(reference):
    with checked(reference).open(encoding='utf-8-sig') as stream: return [json.loads(line) for line in stream if line.strip()]


def prepare(config, fold, seed, regime):
    cfg, original = load_source_runtime(config); require(dict(fold=fold, seed=seed, regime=regime) in cfg['training_matrix'], '未登记训练单元')
    ctx = original.prepare(cfg['source_training_protocol']['path'], fold, seed, regime)
    manifest = read_ref(cfg['mask_inputs'][fold]); source_root = read_ref(cfg['selected_R_bank_root'])
    require(manifest['schema'] == 'R_candidate_eligibility_fold_inputs_v1' and manifest['fold'] == fold
        and manifest['status'] == 'complete1000_original_R_windows_pre_probability_masks_bound'
        and checked(manifest['original_pool']) == checked(source_root['folds'][fold]['pool']), '本fold资格清单/原pool不同')
    bindings = bind_sidecars(ctx['pools']['real'], jsonl(manifest['sidecars']),
        supplied_bindings=jsonl(manifest['bindings']) if manifest.get('bindings') is not None else None)
    ctx.update(eligibility_cfg=cfg, eligibility_config_path=Path(config), eligibility_protocol_sha256=sha(config),
        eligibility_oldrt=original, eligibility_bindings=bindings, eligibility_mask_manifest=manifest)
    sys.path[:0] = [str(ROOT/'tools/research_ops'), str(ROOT/'tools/performance')]
    return ctx


def attach_bindings(batch, bindings):
    require(len(batch['real']) == 3 and len(batch['r']) == 3 and len(batch['synthetic']) == len(batch['s']) <= 1, '原每步3R/至多1S预算不同')
    value = dict(batch); real = []
    for cached, exposure in zip(batch['real'], batch['r']):
        uid = cached['window_uid']; bound = bindings[uid]
        require(uid == exposure['window_uid'] == bound['window_uid'] and cached['candidate_pairs'] == exposure['candidate_pairs'] == bound['accounting']['raw_candidate_pairs']
            and cached['known_pairs'] == exposure['labelled_pairs'] == bound['accounting']['raw_known_pairs'], '原窗口曝光/known缓存发生改变')
        require('eligibility_binding' not in cached, '原cache字段不应预先混入新绑定')
        item = dict(cached); item['eligibility_binding'] = bound; real.append(item)
    value['real'] = real
    return value


def batches(ctx, limit=1000):
    for batch in ctx['eligibility_oldrt'].batches(ctx, ctx['regime'], limit): yield attach_bindings(batch, ctx['eligibility_bindings'])


def batch(ctx, index): return attach_bindings(ctx['eligibility_oldrt'].batch(ctx, index, ctx['regime']), ctx['eligibility_bindings'])
def new_model(ctx, seed=None, device='cuda:0'): return ctx['eligibility_oldrt'].new_model(ctx, seed, device)


def r_loss(ctx, model, windows):
    from r_candidate_eligibility_method import masked_real_domain_BCE
    bindings = []
    for window in windows:
        binding = ctx['eligibility_bindings'][window['window_uid']]
        require(window.get('eligibility_binding', binding) == binding, '批次资格绑定与冻结pool不同')
        bindings.append(binding)
    return masked_real_domain_BCE(model, windows, bindings)


def s_loss(ctx, model, windows): return ctx['numeric'].domain_loss(model, windows)


def extra(ctx):
    value = deepcopy(ctx['eligibility_oldrt'].extra(ctx)); cfg = ctx['eligibility_cfg']
    value.update(schema='r_candidate_eligibility_strongmotion_method_state_v1', training_objective=OBJECTIVE,
        R_loss='original_unreduced_known_BCE_mask_then_window_mean_then_fixed_mean3R',
        S_loss='unchanged_original_known_pair_BCE_alpha_1_over_3', full_original_known_forward_preserved=True,
        empty_effective_window='sum_of_part_times_zero_graph_no_resampling_no_skipped_updates',
        eligibility_mask_input=deepcopy(cfg['mask_inputs'][ctx['fold']]), selected_R_bank_root=deepcopy(cfg['selected_R_bank_root']),
        original_training_protocol=deepcopy(cfg['source_training_protocol']),
        record_extension_schema='R_candidate_scoring_eligibility_record_extension_v1',
        R_objective_code_sha256=sha(ROOT/'tools/research_ops/r_candidate_eligibility_method.py'),
        recorded_loop_sha256=sha(ROOT/'tools/research_ops/r_eligibility_recorded_loop.py'),
        matched_control_reuse_status='conditional_on_fresh_CPU_CUDA_numeric_admission_not_static_claim')
    return value


def spec(ctx, model, diagnostic=False):
    value = deepcopy(ctx['eligibility_oldrt'].spec(ctx, model, ctx['seed'], ctx['regime'], diagnostic=diagnostic))
    value['runtime']['record_extension_schema'] = 'R_candidate_scoring_eligibility_record_extension_v1'
    value['binding'].update(protocol_sha256=ctx['eligibility_protocol_sha256'], source_training_protocol_sha256=SOURCE_PROTOCOL_SHA,
        R_objective=OBJECTIVE, R_objective_code_sha256=sha(ROOT/'tools/research_ops/r_candidate_eligibility_method.py'),
        recorded_loop_sha256=sha(ROOT/'tools/research_ops/r_eligibility_recorded_loop.py'),
        record_extension_schema='R_candidate_scoring_eligibility_record_extension_v1',
        mask_input_sha256=ctx['eligibility_cfg']['mask_inputs'][ctx['fold']]['sha256'], method_state_sha256=digest(extra(ctx)))
    return value


def model_id(protocol_sha256, fold, seed, regime):
    require(dict(fold=fold, seed=seed, regime=regime) in expected_matrix(), '独立模型身份仅18登记单元')
    return digest(['r_candidate_eligibility_strongmotion_model_v1', protocol_sha256, fold, seed, regime])[:24]


def validate_training_admission(config, cfg):
    """未来启动器使用；没有实际CPU/CUDA及完整记录准入不得正式执行。"""
    admission = read(cfg['learning_admission_root_path'])
    require(admission['status'] == 'complete_R_candidate_eligibility_training_numeric_full_record_admission'
        and admission['approved_by'] == 'root' and admission['protocol']['sha256'] == sha(config)
        and checked(admission['protocol']) == physical(config) and admission['formal_optimizer_updates'] == 0
        and admission['actual_CPU_and_CUDA_numeric_verified'] is True and admission['full_record_contract_verified'] is True
        and admission['matched_control_reuse_verified'] is True and admission['test_read'] is False,
        '实际数值/全过程记录准入尚未完成，不能凭候选开训')
    numeric, inputs = read_ref(admission['numeric_validation']), read_ref(admission['input_validation'])
    require(numeric['status'] == 'complete_R_candidate_eligibility_CPU_CUDA_full_record_numeric_admission'
        and numeric['protocol_sha256'] == sha(config) and numeric['all_groups_equal'] is True
        and numeric['matched_control_reuse_numerical_compatibility_verified'] is True and numeric['formal_optimizer_updates'] == 0
        and numeric['actual_diagnostic_optimizer_updates'] == 20 and numeric['diagnostic_R_windows'] == 60 and numeric['diagnostic_S_windows'] == 8
        and numeric['test_read'] is False, '未来learningroot没有绑定本轮20步/60R8S数值实证')
    require(inputs['status'] == 'complete3000_R_candidate_eligibility_inputs_sources_masks_bindings_and_exposures_independently_verified'
        and inputs['windows'] == 3000 and inputs['R_window_exposures_shared_once'] == 27000
        and inputs['original_pool_order_labels_UIDs_and_known_projection_exact'] is True and inputs['pre_probability_mask_not_chosen_by_labels'] is True
        and inputs['original_R_S_order_references_unchanged'] is True and inputs['GT_coordinates_read'] is False and inputs['test_read'] is False,
        '原窗口/资格侧表/曝光表没有独立核验')
    return admission
