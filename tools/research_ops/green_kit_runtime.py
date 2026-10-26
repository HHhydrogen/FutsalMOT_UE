"""绿色球衣对照的新身份契约；数值依赖只读冻结v9，不伪装旧模型身份。"""
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = Path('D:/projects/FutsalMOT_Research')
EXPERIMENT = RESEARCH/'pose/green_seeded_kit_pair_a01'
GAMES = ('game4', 'game6', 'game9')
SEEDS = (20261024, 20261025, 20261026)
PARAMETERS = dict(updates=1000, R_per_step=3, S_per_step=1, S_alpha=1/3, lr=.001,
                  weight_decay=.0001, amp=False, prefetch=2, cache_bytes=268435456,
                  checkpoint_interval=50, method='gated')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(ref):
    path = Path(ref['path'])
    require(path.is_file() and sha(path) == ref['sha256'], '来源SHA变化：' + str(path))
    return path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def expected_matrix():
    return [dict(fold=f, seed=s, appearance=a) for f in GAMES for s in SEEDS for a in 'AB']


def validate_matrix(cfg):
    require(cfg.get('schema') == 'green_kit_gated_control_v1' and cfg.get('training_matrix') == expected_matrix()
            and cfg.get('parameters') == PARAMETERS and cfg.get('test116187_sealed') is True,
            '必须是事前18组、固定1000更新/3000R/1000S及封存测试')


def physical_output(path):
    spec = importlib.util.spec_from_file_location('green_control_storage', ROOT/'python/src/grf_ue_bridge/storage_policy.py')
    storage = importlib.util.module_from_spec(spec); spec.loader.exec_module(storage)
    return storage.physical_child(path, EXPERIMENT)


def load_reference(cfg):
    """只导入并核验原函数；不调用旧train，不修改旧配置或scope。"""
    old_path = checked(cfg['v9_protocol']); old_cfg = read(old_path)
    bundle = Path(old_cfg['bundle'])
    require(old_path == RESEARCH/'pose/pose_quality_v9/frozen_a01/protocol.json'
            and bundle.parent == RESEARCH/'code', '原v9来源不同')
    manifest = read(checked(old_cfg['bundle_manifest']))
    for entry in manifest['files']:
        require(sha(bundle/entry['path']) == entry['sha256'], '原数值闭包变化')
    sys.path[:0] = [str(bundle/'python/src'), str(bundle/'tools/research_ops'), str(bundle/'tools/performance'),
                   str(RESEARCH/'runtime_dependencies')]
    spec = importlib.util.spec_from_file_location('green_frozen_v9_training_numeric', bundle/'tools/research_ops/v9_train.py')
    numeric = importlib.util.module_from_spec(spec); sys.modules[spec.name] = numeric; spec.loader.exec_module(numeric)
    require(Path(inspect.getfile(numeric.make_model)) == bundle/'python/src/grf_ue_bridge/quality_residual_association_v9.py'
            and Path(inspect.getfile(numeric.domain_loss)) == bundle/'tools/research_ops/v8_train.py',
            '误导入未冻结数值代码')
    return numeric, old_cfg


def validate_protocol(path):
    cfg = read(path); validate_matrix(cfg)
    require(cfg.get('approved_by') == 'root' and cfg.get('training_authorized') is True
            and cfg.get('tracking_authorized') is True and Path(cfg['bundle']) == ROOT
            and ROOT.parent == RESEARCH/'code', '新绿色独立bundle/准入缺失')
    for entry in read(checked(cfg['bundle_manifest']))['files']:
        require(sha(ROOT/entry['path']) == entry['sha256'], '新源码变化')
    require(read(checked(cfg['v9_milestone']))['status'] == 'complete_all78_actual_budget_verified_Pose_increment_not_proven',
            '原v9与实际预算未结束，不复用不完整参考')
    admission = read(checked(cfg['admission']))
    require(admission.get('training_authorized') is True and admission.get('tracking_authorized') is True
            and admission.get('approved_by') == 'root' and admission.get('test116187_read') is False
            and admission.get('prediction_manifest') == cfg['prediction_manifest'], '限定新预测准入不同')
    prediction = read(checked(cfg['prediction_manifest']))
    require(prediction.get('status') == 'complete_AB_predictions_fixed_boxes_not_training_authorized'
            and len(prediction.get('sources', [])) == 8 and prediction.get('new_optimizer_updates') == 0
            and all(s['counts']['frames'] == 300 and s['actual_source_validation']['decoded_PNG_frames'] == 300
                    for s in prediction['sources'])
            and prediction.get('R_cache_modified') is False and prediction.get('GT_used_for_predictions') is False
            and prediction.get('final116187_read') is False and prediction.get('v9_protocol') == cfg['v9_protocol'],
            'A/B完整预测未闭合或来源不同')
    require(set(prediction['synthetic_pools']) == {'A', 'B'}
            and prediction['synthetic_pools']['A']['replacement']['non_pose_sha256'] ==
            prediction['synthetic_pools']['B']['replacement']['non_pose_sha256'], 'A/B非Pose输入不一致')
    return cfg, prediction


def validate_job(path, fold, seed, appearance):
    cfg, prediction = validate_protocol(path)
    require(dict(fold=fold, seed=seed, appearance=appearance) in cfg['training_matrix'], '未登记训练组')
    numeric, old = load_reference(cfg)
    _, pools, table, adapter = numeric.validate(checked(cfg['v9_protocol']), fold, seed, 'gated', 'RS')
    helper_spec = importlib.util.spec_from_file_location('green_fixed_S_contract', ROOT/'python/src/grf_ue_bridge/green_kit_pair_inputs.py')
    helper = importlib.util.module_from_spec(helper_spec); helper_spec.loader.exec_module(helper)
    new_ref = prediction['synthetic_pools'][appearance]['pool']; new = rows(checked(new_ref))
    observed = {r['uid']: r for w in new for r in [*w['history'], *(c['prediction'] for c in w['candidates'])]}
    replaced, proof = helper.replace_synthetic_pose(list(pools['synthetic'].values()), observed)
    require(replaced == new and proof['non_pose_sha256'] == prediction['synthetic_pools'][appearance]['replacement']['non_pose_sha256'],
            '新池改变原窗口/框/标签/候选顺序')
    pools['synthetic'] = {w['window_uid']: w for w in new}
    # 参考组只引用来源；新网络始终从相同seed初始化，不追加旧权重训练。
    reference = read(checked(cfg['reference_gated_R'][fold][str(seed)]['training_receipt']))
    require(reference['status'] == 'complete' and reference['completed_updates'] == 1000
            and reference['real_window_exposures'] == 3000 and reference['synthetic_window_exposures'] == 0,
            '纯R参考预算未闭合')
    r_chain = hashlib.sha256(canonical([x['window_uid'] for x in table['real']]).encode()).hexdigest()
    require(r_chain == reference['binding']['R_window_UID_chain_sha256'], 'R顺序与纯R参考不同')
    return cfg, numeric, pools, table, adapter, reference, new_ref


def audit_log_chain(logs, table):
    """实际日志逐步匹配原3000R/1000S表，合法重算的错误曝光链也拒绝。"""
    require(len(logs) == 1000 and len(table['real']) == 3000 and len(table['synthetic']) == 1000,
            '实际步数/登记曝光预算不足')
    chain = '0'*64
    for i, log in enumerate(logs):
        row = dict(log); expected = row.pop('chain_sha256')
        chain = hashlib.sha256((chain+canonical(row)).encode()).hexdigest()
        require(chain == expected and row['actual_update'] == i+1 and row['update_index'] == i
                and row['real_windows'] == 3 and row['synthetic_windows'] == 1
                and row['real'] == table['real'][i*3:i*3+3]
                and row['synthetic'] == table['synthetic'][i:i+1], '实际曝光链/UID顺序/预算错误')
    return chain


def complete_model(path, run):
    """独立绿色checkpoint身份及实际1000步链，不借旧v9 schema放行。"""
    import torch
    cfg, _ = validate_protocol(path); numeric, _ = load_reference(cfg); run = Path(run)
    receipt = read(run/'run_receipt.json'); saved = torch.load(run/'last.pt', map_location='cpu', weights_only=False)
    transaction = read(run/'update_transaction.json'); logs = rows(run/'exposures.jsonl'); binding = receipt['binding']
    require(receipt['schema'] == 'green_kit_actual_window_training_v1' and receipt['status'] == 'complete'
            and receipt['completed_updates'] == saved['completed_updates'] == len(logs) == 1000
            and receipt['checkpoint_sha256'] == sha(run/'last.pt')
            and saved['schema'] == 'green_kit_gated_checkpoint_v1' and saved['binding'] == binding
            and binding['protocol_sha256'] == sha(path)
            and dict(fold=binding['fold'], seed=binding['seed'], appearance=binding['appearance']) in cfg['training_matrix'],
            '绿色模型/last1000身份缺失')
    old = read(checked(cfg['v9_protocol']))
    table = read(checked(old['folds'][binding['fold']]['exposures'][str(binding['seed'])]))
    prediction = read(checked(cfg['prediction_manifest']))
    require(binding['synthetic_pool'] == prediction['synthetic_pools'][binding['appearance']]['pool']
            and binding['numerical_v9_protocol'] == cfg['v9_protocol']
            and binding['prediction_manifest'] == cfg['prediction_manifest']
            and binding['method'] == 'gated' and binding['regime'] == 'RS', '绿色输入/模型方法来源变化')
    chain = audit_log_chain(logs, table)
    require(receipt['exposure_chain'] == saved['exposure_chain'] == transaction['chain'] == chain
            and transaction['status'] == 'committed' and transaction['completed_updates'] == 1000
            and receipt['real_window_exposures'] == 3000 and receipt['synthetic_window_exposures'] == 1000,
            'last/事务/曝光不闭合')
    adapter = numeric.Adapter.from_state(saved['adapter'])
    require(hashlib.sha256(canonical(adapter.state()).encode()).hexdigest() == binding['adapter_sha256'], 'adapter变化')
    require(saved['actual_dtype'] == 'float32' and all(v.dtype == torch.float32 for v in saved['model'].values()), '不是FP32 last')
    model = numeric.make_model(binding['seed'], 'gated')
    require(numeric.model_sha(model) == binding['initialization_sha256'], '初始化变化')
    model.load_state_dict(saved['model']); model.eval()
    return cfg, numeric, model, adapter, binding
