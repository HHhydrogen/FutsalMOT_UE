"""独立v4候选：同R3曝光、分域位置loss、严格无重放续跑；默认仅模板。"""
import argparse
from copy import copy, deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import signal
import sys
import time

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE / 'src'))
_SPEC = importlib.util.spec_from_file_location('pose_v4_frozen_v3_io_helpers', Path(__file__).with_name('train_pose_location_poseonly_v3.py'))
V3 = importlib.util.module_from_spec(_SPEC); _SPEC.loader.exec_module(V3)
BASE = V3.BASE
require, sha, read, rows, canonical, bound_file = BASE.require, BASE.sha, BASE.read, BASE.rows, BASE.canonical, BASE.bound_file
atomic_json, append_exposure = V3.atomic_json, V3.append_exposure

SCHEMA = 'futsalmot_pose_location_separate_checkpoint_v4'
PROTOCOL_SCHEMA = 'futsalmot_pose_location_separate_protocol_v4'
ADMISSION_SCHEMA = 'futsalmot_pose_location_separate_admission_v4'
RUN_SCHEMA = 'futsalmot_pose_location_separate_run_v4'
SCHEDULE_SCHEMA = 'futsalmot_pose_location_separate_schedule_manifest_v4'
ROW_SCHEMA = 'futsalmot_pose_location_separate_schedule_row_v4'
SEEDS = [20261024, 20261025, 20261026]
ARMS = ('R3', 'R3S1')
SETTINGS = dict(actual_optimizer_updates=1000, real_batch=3, synthetic_batch=1, gradient_accumulation=1,
    imgsz=640, optimizer='SGD', lr0=.0001, lrf=1., momentum=.9, weight_decay=0., warmup_epochs=0.,
    amp=False, multi_scale=False, early_stopping=False, augmentation=False, checkpoint_interval=50, gradient_clip_norm=10.,
    pose_gain=12., ema_decay=.9999, ema_tau=2000.)
NORMALIZATION = dict(real='upstream_batch_scaled_location_divided_by_3',
    synthetic='upstream_batch_scaled_location_divided_by_1', mixed='meanR_plus_one_third_times_meanS',
    synthetic_alpha=1./3., shared_foreground_denominator=False, raw_point_budget_equal=False,
    extra_S_compute_equal_FLOPs=False)
POLICY = dict(V3.POLICY, objective='separate_R3_S1_location_v4',
              fixed_same_real_exposures=3000, normalization=NORMALIZATION)
ARM_BUDGETS = {arm: dict(real_exposures=3000, synthetic_exposures=1000 if arm == 'R3S1' else 0,
                        real_images_per_update=3, synthetic_images_per_update=int(arm == 'R3S1')) for arm in ARMS}


def bind(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def g_research_path(path):
    """研究产物的实际落盘地址必须G；旧D联接只允许解析成同一个G文件。"""
    path = Path(path).resolve()
    require(path.drive.upper() == 'G:' and Path('G:/FutsalMOT_Research') in path.parents,
            'v4研究数据/运行产物实际路径必须G:/FutsalMOT_Research，禁止D fallback')
    return path


def g_media_path(path):
    path = Path(path).resolve()
    require(path.drive.upper() == 'G:', 'v4图像实际路径必须G，不能仍读D盘Saved导出')
    return path


def preflight_data_paths(context):
    """Dataset构造/媒体SHA读取前检查全部真实地址；不解码或重写源记录。"""
    receipt = {}
    for key in ('real_jsonl', 'synthetic_jsonl'):
        source = g_research_path(context[key])
        require(source.is_file(), 'v4输入JSONL缺失: ' + str(source))
        count = 0
        for frame in rows(source):
            raw = Path(frame['image_file'])
            actual = g_media_path(raw if raw.is_absolute() else source.parent / raw)
            require(actual.is_file(), 'v4实际G盘媒体缺失: ' + str(actual))
            count += 1
        receipt[key] = dict(path=str(source), images=count, actual_media_drive='G:', pixels_decoded=False)
    initial = g_research_path(context['protocol']['initialization']['derived_checkpoint'])
    require(initial.is_file(), 'v4共同初始化实际G文件缺失')
    receipt['initialization'] = str(initial)
    return receipt


def source_bindings():
    names = [Path(__file__), Path(V3.__file__), Path(BASE.__file__), Path(V3.RETRY.__file__),
             CODE / 'src/grf_ue_bridge/pose_location_supervision_v4.py',
             CODE / 'src/grf_ue_bridge/pose_location_supervision_v3.py',
             CODE / 'src/grf_ue_bridge/pose_only_calibration_v3.py',
             CODE / 'src/grf_ue_bridge/pose_location_dataset_v2.py',
             CODE / 'src/grf_ue_bridge/pose_location_supervision_v2.py',
             CODE / 'src/grf_ue_bridge/pose_xy_head_transfer.py']
    return [bind(path) for path in names]


def derive_schedule(source, selected):
    """仅投影旧表shared3及S列，绝不生成新随机索引或保留第四真实槽。"""
    BASE.validate_schedule(source, 1000, 1440, selected)
    return [dict(schema=ROW_SCHEMA, update_index=row['update_index'],
                 real_indices=list(row['shared_real_indices']), synthetic_index=row['synthetic_index']) for row in source]


def validate_derived_schedule(schedule, source, selected):
    require(schedule == derive_schedule(source, selected), 'v4必须逐行同序派生原shared3/S1000，不允许新采样或额外R')


def template(output, base_protocol, base_admission, source_manifest):
    """只读已冻结v3来源，生成独立表和未签模板，不查询GPU或读取媒体。"""
    output = g_research_path(output); require(not output.exists(), 'v4模板目录已存在')
    from grf_ue_bridge.coco_pose_dev_eval_v4 import source_bindings as evaluation_bindings
    source_manifest = Path(source_manifest).absolute()
    source = read(source_manifest)
    prior = read(base_protocol)
    require(prior.get('schema') == V3.PROTOCOL_SCHEMA and prior.get('status') == 'frozen', '模板需已冻结v3来源')
    output.mkdir(parents=True); (output / 'schedules').mkdir()
    schedules = []
    for seed in SEEDS:
        context = V3.validate_inputs(base_protocol, source_manifest, base_admission, seed, 'R')
        derived = derive_schedule(context['schedule'], context['selected_synthetic_indices'])
        path = output / 'schedules' / f'seed_{seed}.jsonl'
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            for row in derived: handle.write(canonical(row) + '\n')
        schedules.extend(dict(bind(path), seed=seed, arm=arm, updates=1000, real_batch=3,
                              synthetic_batch=int(arm == 'R3S1')) for arm in ARMS)
    manifest = dict(schema=SCHEDULE_SCHEMA, source_schedule_manifest=bind(source_manifest),
        source_v3_protocol=bind(base_protocol), source_v3_admission=bind(base_admission),
        real_jsonl=dict(source['real_jsonl'], path=str(g_research_path(bound_file(source['real_jsonl'])))),
        synthetic_jsonl=dict(source['synthetic_jsonl'], path=str(g_research_path(bound_file(source['synthetic_jsonl'])))),
        selection_manifest=dict(source['selection_manifest'], path=str(g_research_path(bound_file(source['selection_manifest'])))),
        selected_synthetic_indices=source['selected_synthetic_indices'],
        selected_synthetic_frame_keys=source['selected_synthetic_frame_keys'], schedules=schedules,
        derivation='exact_shared_real_indices3_and_synthetic_index_projection_no_R4_no_rng', training_authorized=False)
    atomic_json(output / 'schedule_manifest.json', manifest)
    protocol = dict(schema=PROTOCOL_SCHEMA, status='candidate_not_frozen', training_authorized=False,
        source_v3_protocol=bind(base_protocol), source_v3_admission=bind(base_admission),
        source_schedule_manifest=bind(source_manifest), schedule_manifest=bind(output / 'schedule_manifest.json'),
        paired_training=dict(SETTINGS, seeds=SEEDS), arms=ARM_BUDGETS, policy=POLICY, normalization=NORMALIZATION,
        initialization=prior['initialization'], source_files=source_bindings(), test_split_used=False,
        comparison='same_R3_3000_real_exposures_and_1000_updates;S1000_adds_separate_weighted_location_supervision_and_compute;not_equal_FLOPs',
        evaluation=dict(primary='fixed_detection_AssA', constraints=['HOTA', 'IDF1'], auxiliary='frozen_COCO_dev_AP',
            checkpoint_choice='last1000_actual_FP32_EMA_no_best', compare_against_pretrained=True,
            pretrained_already_COCO_pretrained=True, independent_match_dev_required_for_generalization_claim=True,
            final_test_116_187_sealed=True, source_files=evaluation_bindings()))
    atomic_json(output / 'protocol_template.json', protocol)
    admission = dict(schema=ADMISSION_SCHEMA, status='candidate_not_approved', approved_by=None,
        training_authorized=False, location_only=True, visibility_supervision=False, source_not_training_flags_preserved=True,
        protocol=bind(output / 'protocol_template.json'), schedule_manifest=bind(output / 'schedule_manifest.json'),
        source_v3_protocol=bind(base_protocol), source_v3_admission=bind(base_admission),
        source_schedule_manifest=bind(source_manifest), source_files=source_bindings(), policy=POLICY,
        normalization=NORMALIZATION, UE_serial_gate=dict(all_rendering_finished=False, editor_safely_exited=False),
        shutdown_receipt=None, test_split_used=False, evaluation_source_files=evaluation_bindings())
    atomic_json(output / 'admission_template.json', admission)
    return dict(output=str(output), training_authorized=False, schedule_manifest=bind(output / 'schedule_manifest.json'))


def validate_inputs(protocol_path, manifest_path, admission_path, seed, arm):
    protocol_path, manifest_path, admission_path = map(lambda p: Path(p).resolve(), (protocol_path, manifest_path, admission_path))
    protocol, manifest, admission = map(read, (protocol_path, manifest_path, admission_path))
    require(type(seed) is int and seed in SEEDS and arm in ARMS, 'v4只允许原三seed与R3/R3S1')
    require(protocol.get('schema') == PROTOCOL_SCHEMA and protocol.get('status') == 'frozen'
            and protocol.get('training_authorized') is True and protocol.get('test_split_used') is False, '需要独立冻结v4协议')
    require(admission.get('schema') == ADMISSION_SCHEMA and admission.get('status') == 'approved_separate_location_v4'
            and admission.get('approved_by') == 'root' and admission.get('training_authorized') is True
            and admission.get('location_only') is True and admission.get('visibility_supervision') is False
            and admission.get('source_not_training_flags_preserved') is True and admission.get('test_split_used') is False,
            '旧准入或候选不能授权v4')
    require(bound_file(admission['protocol']) == protocol_path and bound_file(admission['schedule_manifest']) == manifest_path
            and bound_file(protocol['schedule_manifest']) == manifest_path, 'v4协议/采样表绑定不匹配')
    require(protocol.get('paired_training') == dict(SETTINGS, seeds=SEEDS) and protocol.get('arms') == ARM_BUDGETS
            and all(type(protocol['paired_training'].get(k)) is type(v) for k, v in SETTINGS.items()),
            'v4真实曝光、更新数、学习率或640尺度变化')
    require(protocol.get('policy') == admission.get('policy') == POLICY
            and protocol.get('normalization') == admission.get('normalization') == NORMALIZATION, 'v4分域归一化/冻结策略变化')
    require(protocol.get('source_files') == admission.get('source_files') == source_bindings(), 'v4实际数值/兼容依赖源码SHA变化')
    from grf_ue_bridge.coco_pose_dev_eval_v4 import source_bindings as evaluation_bindings
    require(protocol.get('evaluation', {}).get('source_files') == admission.get('evaluation_source_files') == evaluation_bindings(),
            'v4独立评价身份源码未绑定或发生变化')
    require(admission.get('UE_serial_gate') == dict(all_rendering_finished=True, editor_safely_exited=True), '需新的v4 UE串行准入')
    shutdown = read(bound_file(admission['shutdown_receipt']))
    require(shutdown.get('normal_exit_confirmed') is True and shutdown.get('process_absent') is True, '缺v4实际安全退出收据')
    for key in ('source_v3_protocol', 'source_v3_admission', 'source_schedule_manifest'):
        require(bound_file(admission[key]) == bound_file(protocol[key]) == bound_file(manifest[key]), 'v4来源绑定不一致')
    old = V3.validate_inputs(bound_file(protocol['source_v3_protocol']), bound_file(protocol['source_schedule_manifest']),
        bound_file(protocol['source_v3_admission']), seed, 'RS25' if arm == 'R3S1' else 'R')
    require(manifest.get('schema') == SCHEDULE_SCHEMA and protocol.get('initialization') == old['protocol']['initialization'],
            'v4初始化或采样manifest身份变化')
    for key in ('real_jsonl', 'synthetic_jsonl', 'selection_manifest'):
        require(g_research_path(bound_file(manifest[key])) == g_research_path(bound_file(old['manifest'][key]))
                and manifest[key]['sha256'] == old['manifest'][key]['sha256'], 'v4数据迁移必须同文件SHA/实际G: ' + key)
    for key in ('selected_synthetic_indices', 'selected_synthetic_frame_keys'):
        require(manifest.get(key) == old['manifest'][key], 'v4变更了原R/S选择: ' + key)
    entries = [entry for entry in manifest['schedules'] if entry['seed'] == seed]
    require(len(entries) == 2 and {e['arm'] for e in entries} == set(ARMS)
            and len({(e['path'], e['sha256']) for e in entries}) == 1, 'v4两臂必须共用同一shared3表SHA')
    entry = next(e for e in entries if e['arm'] == arm)
    require(entry.get('updates') == 1000 and entry.get('real_batch') == 3
            and entry.get('synthetic_batch') == int(arm == 'R3S1'), 'v4表预算变化')
    schedule_path = bound_file(entry); schedule = rows(schedule_path)
    validate_derived_schedule(schedule, old['schedule'], old['selected_synthetic_indices'])
    old.update(protocol=protocol, admission=admission, manifest=manifest, schedule=schedule, arm=arm,
               real_jsonl=g_research_path(bound_file(manifest['real_jsonl'])), synthetic_jsonl=g_research_path(bound_file(manifest['synthetic_jsonl'])))
    source_bindings_old = old['bindings']
    old['bindings'] = dict(protocol_sha256=sha(protocol_path), admission_sha256=sha(admission_path),
        schedule_manifest_sha256=sha(manifest_path), schedule_sha256=sha(schedule_path),
        trainer_source_sha256=sha(__file__), source_files=source_bindings(), source_v3_bindings=source_bindings_old,
        real_jsonl_sha256=source_bindings_old['real_jsonl_sha256'], synthetic_jsonl_sha256=source_bindings_old['synthetic_jsonl_sha256'])
    return old


def save_last(path, model, ema, optimizer, completed, context, initial_hash, chain, last_exposure):
    import numpy as np
    import torch
    path = Path(path); temporary = path.with_name(path.name + '.tmp')
    require(not temporary.exists(), '断点partial保留，禁止覆盖或猜测恢复')
    started = time.perf_counter()
    checkpoint = dict(schema=SCHEMA, model=V3.model_copy(model), ema=V3.model_copy(ema.ema),
        optimizer=deepcopy(optimizer.state_dict()), ema_updates=ema.updates, completed_updates=completed,
        arm=context['arm'], seed=context['seed'], bindings=context['bindings'], initial_state_sha256=initial_hash,
        exposure_chain_sha256=chain, last_exposure=last_exposure, planned_updates=1000, policy=POLICY,
        normalization=NORMALIZATION, checkpoint_interval=50, checkpoint_choice='last_actual_FP32_EMA_no_best',
        actual_ema_fp32=True, keypoint_shape=[17, 2], physical_output_channels=51, visibility_supervised=False,
        rng=dict(python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state(),
                 cuda=torch.cuda.get_rng_state_all() if next(model.parameters()).is_cuda else None))
    with temporary.open('xb') as handle:
        torch.save(checkpoint, handle); handle.flush(); os.fsync(handle.fileno())
    V3.replace_owned(temporary, path)
    return time.perf_counter() - started


def reconcile_resume(output, checkpoint, context):
    """只恢复完全提交且与last同计数的状态；无猜步、删日志或自动重放。"""
    require(checkpoint.get('schema') == SCHEMA and checkpoint.get('bindings') == context['bindings']
            and checkpoint.get('arm') == context['arm'] and checkpoint.get('seed') == context['seed']
            and checkpoint.get('planned_updates') == 1000 and checkpoint.get('policy') == POLICY
            and checkpoint.get('normalization') == NORMALIZATION and checkpoint.get('actual_ema_fp32') is True
            and checkpoint.get('keypoint_shape') == [17, 2] and checkpoint.get('physical_output_channels') == 51
            and checkpoint.get('visibility_supervised') is False, 'v4断点身份不符')
    completed = checkpoint['completed_updates']
    require(type(completed) is int and 0 <= completed <= 1000 and checkpoint['ema_updates'] == completed, '实际/EMA更新计数错误')
    output = Path(output); require(not list(output.glob('*.tmp')), '已有partial，拒绝自动覆盖/重放')
    exposures = rows(output / 'exposures.jsonl') if (output / 'exposures.jsonl').exists() else []
    require(len(exposures) == completed, '曝光预算超过或不同于last，禁止重放')
    transaction = read(output / 'update_transaction.json') if (output / 'update_transaction.json').exists() else None
    require((transaction is None and completed == 0) or (transaction and transaction.get('status') == 'committed'
            and transaction.get('completed_updates') == completed and transaction.get('update_index') == completed - 1
            and transaction.get('arm') == context['arm'] and transaction.get('seed') == context['seed']
            and transaction.get('exposure_chain_sha256') == checkpoint['exposure_chain_sha256']), '未提交或超出last的更新事务')
    chain = '0' * 64
    for index, exposure in enumerate(exposures):
        value = dict(exposure); recorded = value.pop('chain_sha256')
        expected = context['schedule'][index]
        require(value['actual_optimizer_update'] == index + 1 and value['update_index'] == index
                and value['arm'] == context['arm'] and value['seed'] == context['seed']
                and value['real_indices'] == expected['real_indices'] and value['real_images'] == 3
                and value['synthetic_indices'] == ([expected['synthetic_index']] if context['arm'] == 'R3S1' else []), 'v4曝光次序/预算变化')
        chain = hashlib.sha256((chain + canonical(value)).encode()).hexdigest()
        require(chain == recorded, 'v4曝光链改变')
    require(chain == checkpoint['exposure_chain_sha256'] and checkpoint.get('last_exposure') == (exposures[-1] if exposures else None),
            'v4断点与曝光链不一致')
    return completed


def train_loop(model, objective, optimizer, ema, guard, real, synthetic, schedule, context, output,
               completed=0, chain='0' * 64, initial_hash=None, last_exposure=None, stop_after=None,
               stop_requested=None, checkpoint_interval=50):
    """独立数值循环；公开入口固定1000表，CPU夹具仅安全暂停前两步。"""
    import torch
    from grf_ue_bridge.pose_location_dataset_v2 import LocationPoseDataset
    require(len(schedule) == 1000 and checkpoint_interval == 50, 'v4固定1000次更新及50步断点')
    output = Path(output); device = next(model.parameters()).device
    initial_hash = initial_hash or BASE.state_hash(model)
    checkpoint_seconds = 0.; saved_at = []; started = time.perf_counter(); mixed = context['arm'] == 'R3S1'
    def checkpoint():
        nonlocal checkpoint_seconds
        checkpoint_seconds += save_last(output / 'last.pt', model, ema, optimizer, completed, context, initial_hash, chain, last_exposure)
        saved_at.append(completed)
    if completed == 0: checkpoint()
    def pack(dataset, indices):
        batch = LocationPoseDataset.collate_fn([dataset[i] for i in indices])
        batch = {key: value.to(device) if isinstance(value, torch.Tensor) else value for key, value in batch.items()}
        batch['img'] = batch['img'].float() / 255.
        return batch
    for row in schedule[completed:]:
        if (stop_requested and stop_requested()) or (stop_after is not None and completed >= stop_after): break
        index = row['update_index']; require(index == completed, 'v4更新不连续')
        real_indices = row['real_indices']; synthetic_indices = [row['synthetic_index']] if mixed else []
        real_batch = pack(real, real_indices); synthetic_batch = pack(synthetic, synthetic_indices) if mixed else None
        atomic_json(output / 'update_transaction.json', dict(schema='separate_update_transaction_v4', status='started_not_committed',
            update_index=index, completed_updates_before=completed, arm=context['arm'], seed=context['seed']))
        optimizer.zero_grad(set_to_none=True)
        result = objective(real_batch, synthetic_batch)
        require(torch.isfinite(result.loss).item(), 'v4位置loss非有限')
        if result.loss.requires_grad: result.loss.backward()
        trainable = [p for p in model.parameters() if p.requires_grad]
        require(all(p.grad is None or torch.isfinite(p.grad).all().item() for p in trainable), 'v4梯度非有限，不自动重放')
        nonzero = sum(int(p.grad is not None and bool(p.grad.abs().sum())) for p in trainable)
        preclip_norm = torch.nn.utils.clip_grad_norm_(trainable, max_norm=10.)
        optimizer.step(); guard.assert_unchanged(); V3.update_ema_preserve_frozen(ema, model, guard)
        completed += 1
        exposure = dict(schema='separate_step_exposure_v4', actual_optimizer_update=completed, update_index=index,
            arm=context['arm'], seed=context['seed'], real_indices=real_indices, synthetic_indices=synthetic_indices,
            real_images=3, synthetic_images=int(mixed), real_domain=result.report['real'], synthetic_domain=result.report['synthetic'],
            real_component_loss=float(result.real_mean.detach()), synthetic_component_loss=float(result.synthetic_mean.detach()) if mixed else None,
            total_location_loss=float(result.loss.detach()), synthetic_alpha=result.report['alpha'], visibility_loss=0.,
            image_files=real_batch['im_file'] + (synthetic_batch['im_file'] if mixed else []),
            source_image_keys=[BASE.source_key(real, i) for i in real_indices] + [BASE.source_key(synthetic, i) for i in synthetic_indices],
            learning_rate=optimizer.param_groups[0]['lr'], preclip_gradient_norm=float(preclip_norm),
            trainable_parameters_with_nonzero_gradient=nonzero, zero_gradient_update=nonzero == 0,
            visibility_rows_unchanged=True, bn_buffers_unchanged=True, frozen_parameters_unchanged=True)
        chain = hashlib.sha256((chain + canonical(exposure)).encode()).hexdigest()
        last_exposure = dict(exposure, chain_sha256=chain); append_exposure(output / 'exposures.jsonl', last_exposure)
        atomic_json(output / 'update_transaction.json', dict(schema='separate_update_transaction_v4', status='committed',
            update_index=index, completed_updates=completed, exposure_chain_sha256=chain, arm=context['arm'], seed=context['seed']))
        if completed % 50 == 0: checkpoint()
    if not saved_at or saved_at[-1] != completed: checkpoint()
    return dict(completed_updates=completed, planned_updates=1000, complete=completed == 1000,
        status='complete' if completed == 1000 else 'safely_paused', checkpoint_seconds=checkpoint_seconds,
        checkpoints_saved_at_updates=saved_at, elapsed_seconds=time.perf_counter() - started,
        initial_state_sha256=initial_hash, exposure_chain_sha256=chain, guard=guard.assert_unchanged())


def train(context, output, device='cpu', resume=False, cache_mib=3072, stop_after=None):
    """必须独立签署后显式启动；当前Editor存在时CPU/GPU正式run都拒绝。"""
    require(not BASE.editor_running() and device in ('cpu', 'cuda:0'), 'UE未安全退出或设备不支持')
    import numpy as np
    import torch
    import ultralytics
    from ultralytics.utils import DEFAULT_CFG
    from ultralytics.utils.torch_utils import ModelEMA
    from grf_ue_bridge.pose_location_dataset_v2 import LocationPoseDataset
    from grf_ue_bridge.pose_location_supervision_v4 import SeparateDomainLocationObjective
    from grf_ue_bridge.pose_xy_head_transfer import map_pose_xy
    from grf_ue_bridge.pose_only_calibration_v3 import configure_pose_only
    require(ultralytics.__version__ == '8.4.60' and torch.__version__ == '2.6.0+cu124', '仅当前已验运行时')
    require(type(cache_mib) is int and 0 <= cache_mib <= 4096, '缓存仅0..4096MiB')
    require(stop_after is None or type(stop_after) is int and 1 <= stop_after <= 1000, '暂停点仅1..1000累计步')
    output = g_research_path(output)
    for path in (output, *output.parents):
        require(not path.exists() or not (path.is_symlink() or getattr(path.stat(), 'st_file_attributes', 0) & 0x400), 'v4输出禁止联接')
    require(Path('G:/FutsalMOT_Research/pose/poseonly_v4') in output.parents, 'v4只能写独立G Research/pose/poseonly_v4目录')
    require((output / 'last.pt').is_file() if resume else not output.exists(), 'v4需新目录或明确last续跑')
    data_path_preflight = preflight_data_paths(context)
    output.mkdir(parents=True, exist_ok=resume)
    seed = context['seed']; random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if device == 'cuda:0': torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True; torch.use_deterministic_algorithms(True)
    initialization = context['protocol']['initialization']; initial_path = g_research_path(initialization['derived_checkpoint'])
    require(sha(initial_path) == initialization['derived_sha256'], 'v4共同初始化SHA变化')
    loaded = torch.load(output / 'last.pt' if resume else initial_path, map_location='cpu', weights_only=False)
    completed = reconcile_resume(output, loaded, context) if resume else 0
    require(completed < 1000, 'v4已完成last1000不能重训或覆盖')
    if resume:
        require(all(not value.is_floating_point() or value.dtype == torch.float32 for name in ('model', 'ema')
                    for value in loaded[name].state_dict().values()), 'v4断点model/实际EMA不是FP32')
    model = map_pose_xy(loaded['model'].float()).to(device); model.args = copy(DEFAULT_CFG); model.args.pose = 12.
    guard = configure_pose_only(model); objective = SeparateDomainLocationObjective(model, freeze_guard=guard)
    optimizer = torch.optim.SGD((p for p in model.parameters() if p.requires_grad), lr=.0001, momentum=.9, weight_decay=0.)
    ema = ModelEMA(model, decay=.9999, tau=2000.)
    if resume:
        optimizer.load_state_dict(loaded['optimizer']); ema.ema.load_state_dict(loaded['ema'].state_dict()); ema.updates = loaded['ema_updates']
        require(all(g['lr'] == .0001 and g['momentum'] == .9 and g['weight_decay'] == 0 for g in optimizer.param_groups), 'v4恢复优化器设置变化')
        random.setstate(loaded['rng']['python']); np.random.set_state(loaded['rng']['numpy']); torch.set_rng_state(loaded['rng']['torch'])
        if loaded['rng']['cuda'] is not None: torch.cuda.set_rng_state_all(loaded['rng']['cuda'])
    mixed = context['arm'] == 'R3S1'; limit = cache_mib * 1024 * 1024
    real = BASE.CachedDataset(LocationPoseDataset(context['real_jsonl'], 640, verify_image_sha256=True), limit // 2 if mixed else limit)
    synthetic = BASE.CachedDataset(LocationPoseDataset(context['synthetic_jsonl'], 640, verify_image_sha256=False), limit - limit // 2 if mixed else 0)
    for dataset in (real, synthetic):
        require(all(g_media_path(path).is_file() for path in dataset.dataset.im_files), 'v4媒体实际G路径缺失')
    cache = dict(limit_mib=cache_mib, real=real.prewarm(range(1000)), synthetic=synthetic.prewarm(context['selected_synthetic_indices'] if mixed else []))
    stopped = [False]; previous = signal.signal(signal.SIGINT, lambda *args: stopped.__setitem__(0, True))
    try:
        result = train_loop(model, objective, optimizer, ema, guard, real, synthetic, context['schedule'], context, output,
            completed=completed, chain=loaded['exposure_chain_sha256'] if resume else '0' * 64,
            initial_hash=loaded['initial_state_sha256'] if resume else None, last_exposure=loaded.get('last_exposure') if resume else None,
            stop_after=stop_after, stop_requested=lambda: stopped[0])
    finally:
        signal.signal(signal.SIGINT, previous); objective.close(); guard.close()
    result.update(schema=RUN_SCHEMA, arm=context['arm'], seed=seed, bindings=context['bindings'], policy=POLICY, normalization=NORMALIZATION,
        cache=cache, device=device, data_path_preflight=data_path_preflight,
        source_not_training_flags_preserved=True, real_test_read=False, AP_evaluated=False,
        visibility_supervised=False, actual_ema_fp32=True, keypoint_shape=[17, 2], physical_output_channels=51,
        checkpoint_choice='last1000_actual_FP32_EMA_no_best',
        actual_exposures=dict(real=result['completed_updates'] * 3, synthetic=result['completed_updates'] * int(mixed)),
        runtime=dict(torch=torch.__version__, ultralytics=ultralytics.__version__, cuda=torch.version.cuda))
    atomic_json(output / 'run_receipt.json', result)
    return result


def configure_runtime():
    """第三方配置、下载缓存和临时文件也只允许实际写G盘。"""
    os.environ.update(YOLO_AUTOINSTALL='false', YOLO_OFFLINE='true', WANDB_MODE='disabled', COMET_MODE='DISABLED', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    io_root = Path('G:/FutsalMOT_Research/pose/poseonly_v4/_runtime')
    for key, folder in (('TORCH_HOME', 'torch'), ('YOLO_CONFIG_DIR', 'ultralytics'), ('MPLCONFIGDIR', 'matplotlib'),
                        ('XDG_CACHE_HOME', 'cache'), ('TMP', 'tmp'), ('TEMP', 'tmp')):
        path = g_research_path(io_root / folder); path.mkdir(parents=True, exist_ok=True); os.environ[key] = str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('template', 'validate', 'train'))
    for key in ('protocol', 'schedule-manifest', 'admission', 'output', 'base-protocol', 'base-admission', 'source-schedule-manifest'):
        parser.add_argument('--' + key, type=Path)
    parser.add_argument('--arm', choices=ARMS); parser.add_argument('--seed', type=int)
    parser.add_argument('--device', choices=('cpu', 'cuda:0'), default='cpu')
    parser.add_argument('--resume', action='store_true'); parser.add_argument('--stop-after', type=int)
    parser.add_argument('--cache-mib', type=int, default=3072)
    args = parser.parse_args()
    configure_runtime()
    if args.action == 'template':
        result = template(args.output, args.base_protocol, args.base_admission, args.source_schedule_manifest)
    else:
        context = validate_inputs(args.protocol, args.schedule_manifest, args.admission, args.seed, args.arm)
        result = dict(validated=True, arm=args.arm, seed=args.seed, training_started=False) if args.action == 'validate' else train(
            context, args.output, args.device, args.resume, args.cache_mib, args.stop_after)
    print(canonical(result))


if __name__ == '__main__': main()
