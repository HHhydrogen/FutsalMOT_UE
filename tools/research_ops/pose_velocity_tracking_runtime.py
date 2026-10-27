"""450项新方法与63项同容量参考追踪准入；只读复用原12场来源与事件。"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
R = Path('D:/projects/FutsalMOT_Research')
EXP = R / 'pose/pose_velocity_learning_a01'
FOLDS = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
OLD = {'SNMOT-060': 'game4', 'SNMOT-097': 'game6', 'SNMOT-151': 'game9'}
EXTERNAL = ('v_2QhNRucNC7E_c017', 'v_G-vNjfx1GGc_c004')
SEVEN = ('v_1yHWGw8DH4A_c029', 'v_HdiyOtliFiw_c003', 'v_ITo3sCnpw_k_c007',
         'v_dw7LOz17Omg_c053', 'v_gQNyhv8y0QY_c003', 'v_i2_L4qquVg0_c006', 'v_iIxMOsCGH58_c013')
CASES = (('T_R', True), ('T_RS', True), ('T_RS', False), ('T_shuffle_RS', True), ('T_shuffle_RS', False))
SOURCE_TRACKING_SHA = 'f85e69bc2a50220528a2caf42243ee940768cc0a60a4fa845eab2d7c7da27ef1'
SEVEN_TRACKING_SHA = 'fd1b92c70ab91d021a8b055cf89eeb3775d34a506056efe85cb3da90038e9a78'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe(path):
    path = Path(path).absolute()
    require(not any(part.lower() == 'test' or re.search(r'snmot[-_]?0*(116|187)(?:\D|$)', part.lower())
                    for part in path.parts), '最终测试继续封存，禁止读取')
    return path


def read(path): return json.loads(safe(path).read_text(encoding='utf-8-sig'))
def rows(path): return [json.loads(x) for x in safe(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def sha(path): return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def ref(path): return dict(path=str(path), sha256=sha(path))
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def checked(reference):
    path = safe(reference['path'])
    require(path.is_file() and sha(path) == reference['sha256'], '绑定来源改变：' + str(path))
    return path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, safe(path))
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def _source_configs(cfg):
    require(cfg['source_tracking_config']['sha256'] == SOURCE_TRACKING_SHA
            and cfg['source_seven_tracking_config']['sha256'] == SEVEN_TRACKING_SHA, '原5/7场追踪协议身份不同')
    return read(checked(cfg['source_tracking_config'])), read(checked(cfg['source_seven_tracking_config']))


def sources_from(cfg):
    """逐值保持两个原协议的source字典；不取别名、不重生成预测或GT。"""
    old, seven = _source_configs(cfg)
    a, b = old['sources'], seven['sources']
    require(set(a) == set(OLD) | set(EXTERNAL) and set(b) == set(SEVEN) and not set(a) & set(b), '原12场范围改变')
    require(all(s['sequence'] == key and s['frames'] > 0 for key, s in list(a.items()) + list(b.items())), '来源sequence/帧数无效')
    return deepcopy(dict(a, **b))


def tracking_matrix(sources):
    require(set(sources) == set(OLD) | set(EXTERNAL) | set(SEVEN), '必须原12场来源')
    jobs = []
    for fold in FOLDS:
        sequences = [next(seq for seq, game in OLD.items() if game == fold)] + list(EXTERNAL) + list(SEVEN)
        for seed in SEEDS:
            for group, pose_enabled in CASES:
                for sequence in sequences:
                    job = dict(kind='new', group=group, fold=fold, seed=seed, pose_enabled=pose_enabled, sequence=sequence)
                    job['job_id'] = hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
                    jobs.append(job)
    for fold in FOLDS:
        for seed in SEEDS:
            for sequence in SEVEN:
                job = dict(kind='reference', group='same_capacity_motion_RS', fold=fold, seed=seed,
                           pose_enabled=False, sequence=sequence)
                job['job_id'] = hashlib.sha256(canonical(job).encode()).hexdigest()[:24]
                jobs.append(job)
    require(len(jobs) == len({j['job_id'] for j in jobs}) == 513
            and sum(j['kind'] == 'new' for j in jobs) == 450, '450新项/63参考矩阵必须完整且唯一')
    return jobs


def source_seven_runtime(cfg):
    """只从原abf实际bundle导入原模块，禁止复制后ROOT漂移。"""
    _, source = _source_configs(cfg)
    bundle = safe(source['bundle'])
    require(bundle.parent == R / 'code', '原七场执行bundle不在实际研究根')
    manifest = read(checked(source['bundle_manifest']))
    for item in manifest['files']:
        require(sha(bundle / item['path']) == item['sha256'], '原七场执行源码变化')
    path = bundle / 'tools/research_ops/substitution_tracking_runtime.py'
    require(any(e['path'] == 'tools/research_ops/substitution_tracking_runtime.py' for e in manifest['files']), '原七场runtime未绑定')
    return module('velocity_source_seven_tracking_runtime', path)


def learning_loader(cfg):
    protocol = checked(cfg['learning_protocol'])
    source = read(protocol)
    bundle = safe(source['bundle'])
    require(bundle.parent == R / 'code', '学习runtime必须来自实际不可变bundle')
    manifest = read(checked(source['bundle_manifest']))
    entry = next((e for e in manifest['files'] if e['path'] == 'tools/research_ops/pose_velocity_learning_runtime.py'), None)
    require(entry is not None and sha(bundle / entry['path']) == entry['sha256'], '新学习独立加载器改变')
    # 原数值加载会前置旧目录；本入口自身的jobs/adapter始终由绝对路径导入。
    loader = module('velocity_completed_learning_runtime', bundle / entry['path'])
    loader.validate_protocol(protocol)
    return loader


def _registry_binding(cfg, key):
    binding = cfg['registries'][key]
    require(set(binding) == {'registry', 'receipt'}, '事件绑定必须分开完整ledger与无GT公共receipt')
    return binding


def validate_registry_receipts(cfg):
    """追踪准入只读无坐标公共receipt，完整endpoint_GT账本留给评价进程。"""
    old, seven = _source_configs(cfg)
    require(set(cfg['registries']) == {'old_five', 'seven'}, '只能复用原两份事件账本')
    for key, source, count in (('old_five', old, 1353), ('seven', seven, 2337)):
        binding = _registry_binding(cfg, key)
        require(binding['registry'] == source['registry'], '不能重造/替换原结果前事件')
        receipt = read(checked(binding['receipt']))
        require(receipt['registry'] == binding['registry'] and receipt['sources'] == source['sources']
                and receipt['event_count'] == count and receipt['tracking_results_read'] is False
                and receipt['contains_GT_coordinates'] is False and receipt['test_read'] is False,
                '无坐标公共receipt来源/原全事件计数不同')


def validate_learning_complete(cfg, learning_runtime):
    done = read(checked(cfg['learning_complete']))
    budget = read(checked(cfg['learning_budget']))
    control_ref = cfg['learning_controller_state']
    state = read(checked(control_ref))
    require(done['status'] == 'complete27_bounded_velocity_training_budget_records_and_exit_verified'
            and done['protocol'] == cfg['learning_protocol'] and done['budget'] == cfg['learning_budget']
            and done['controller_state'] == control_ref and done['training_processes_absent'] is True, '新27臂训练完成/退出根不齐')
    require(budget['status'] == 'complete27_bounded_velocity_actual_budget_full_records_and_exit_verified'
            and budget['protocol'] == cfg['learning_protocol'] and budget['control_state'] == control_ref
            and budget['training_processes_absent'] is True and budget['complete_checkpoints_read_back'] == 567
            and budget['actual_totals']['updates'] == 27000 and budget['actual_totals']['R_windows'] == 81000
            and budget['actual_totals']['S_windows'] == 18000, '独立实际预算/记录未闭合')
    require(state['status'] == 'complete27_bounded_velocity_training_wait_independent_audit_tracking'
            and state['active'] is None and state['protocol_sha256'] == cfg['learning_protocol']['sha256']
            and len(state['completed_train']) == 27, '训练控制器终态未齐或仍有活动')
    require([{k: item[k] for k in ('fold', 'seed', 'group')} for item in state['completed_train']]
            == learning_runtime.expected_matrix(), '完整训练矩阵被筛选/重排')
    return state


def validate_config(config):
    cfg = read(config)
    require(cfg.get('schema') == 'bounded_velocity513_tracking_protocol_v1' and cfg.get('approved_by') == 'root'
            and cfg.get('tracking_authorized') is True and cfg.get('test_sealed') is True
            and cfg.get('formal_equivalence_or_noninferiority') is False and Path(cfg['bundle']) == ROOT
            and ROOT.parent == R / 'code', '独立513追踪准入/测试封存缺失')
    manifest = read(checked(cfg['bundle_manifest']))
    require(any(x['path'] == 'tools/research_ops/pose_velocity_tracking_runtime.py' for x in manifest['files']), '新追踪runtime未绑定')
    for item in manifest['files']:
        require(sha(ROOT / item['path']) == item['sha256'], '新追踪执行源码改变')
    require(cfg['sources'] == sources_from(cfg) and cfg['tracking_matrix'] == tracking_matrix(cfg['sources']), '12场来源或513矩阵改变')
    seven = source_seven_runtime(cfg)
    dep = seven.dependencies(cfg['source_tracking_config'])
    require(len(dep) == 8, '原f309/v10评价数值依赖接口改变')
    dep[3].storage().physical_child(ROOT, R / 'code')
    loader = learning_loader(cfg)
    learned = read(checked(cfg['learning_protocol']))
    require(learned['source_training_protocol'] == dep[0]['training_protocol'], '学习与追踪原感知/训练来源不一致')
    validate_learning_complete(cfg, loader)
    old_source, _ = _source_configs(cfg)
    require(cfg['source_numeric_validation'] == old_source['numeric_validation'], '原750三模式数值门禁来源不同')
    evidence = read(checked(cfg['source_numeric_validation']))
    require(evidence['status'] == 'complete_original750_three_modes_scope_equivalent'
            and all(item['all_rows_and_audit_equal'] for item in evidence['checks']), '原数值等价门禁未过')
    validate_registry_receipts(cfg)
    if 'analysis_plan' in cfg:
        checked(cfg['analysis_plan'])
    return cfg, dep, loader


def load_model(cfg, dep, learning_runtime, job):
    require(job in cfg['tracking_matrix'] and type(job['pose_enabled']) is bool, '未登记的模型/开关')
    if job['kind'] == 'reference':
        require(job['group'] == 'same_capacity_motion_RS' and job['pose_enabled'] is False
                and job['sequence'] in SEVEN, '只补原同容量motion_RS七场参考')
        run = Path(dep[0]['training_control']) / 'runs' / job['fold'] / str(job['seed']) / 'balanced/motion_residual/training'
        _, _, model, adapter, binding = dep[3].complete_model(checked(dep[0]['training_protocol']), run)
        require(binding['fold'] == job['fold'] and binding['seed'] == job['seed']
                and binding['method'] == 'motion_residual' and binding['pool'] == 'balanced', '原同容量参考模型身份不同')
        return model, adapter, binding, False
    require(job['kind'] == 'new', '未知模型来源种类')
    state = read(checked(cfg['learning_controller_state']))
    matches = [item for item in state['completed_train'] if all(item[k] == job[k] for k in ('group', 'fold', 'seed'))]
    require(len(matches) == 1, '独立学习模型不能缺失/重复')
    run = Path(matches[0]['path'])
    require(sha(run / 'run_receipt.json') == matches[0]['receipt_sha256']
            and sha(run / 'training_complete.json') == matches[0]['complete_sha256'], '模型收据改变')
    _, _, model, adapter, binding = learning_runtime.complete_model(checked(cfg['learning_protocol']), run)
    require(all(binding[k] == job[k] for k in ('group', 'fold', 'seed'))
            and binding['protocol_sha256'] == cfg['learning_protocol']['sha256'], '独立新模型身份不同')
    return model, adapter, binding, job['pose_enabled']


def registry_for_sequence(cfg, sequence):
    require(sequence in cfg['sources'], '事件来源不在12场')
    return _registry_binding(cfg, 'old_five' if sequence in set(OLD) | set(EXTERNAL) else 'seven')


def load_gt(cfg, dep, source):
    """仅评价进程调用；旧5/新7保持各原标注口径。"""
    if source['sequence'] in set(OLD) | set(EXTERNAL):
        return dep[1].load_gt(source)
    return source_seven_runtime(cfg).load_gt(source)


def gap_numeric(cfg, dep):
    return source_seven_runtime(cfg).gap_numeric(dep)
