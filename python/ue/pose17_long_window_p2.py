"""独立300帧P2候选；默认只读，显式建源/队列/地板/submit分步执行，无自动渲染。"""
import importlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pose17_joint_grf_sequences as joint
import pose17_location_pilot_sources as old_source
import pose17_long_window_contract as contract
import pose17_smoke_runner as runner

INPUTS = 'Saved/Pose17Development/long_window_inputs_a02/prepared_manifest.json'
INPUTS_SHA256 = '1b0e458a24c81a181e122d25c4e01ce8ece59aafc425fbb7d10464f6f15ff693'


def prepared_path(project):
    path = old_source._plain_path(os.environ.get('FUTSAL_POSE17_LONG_PREPARED_MANIFEST', str(project / INPUTS)))
    identity = os.environ.get('FUTSAL_POSE17_LONG_PREPARED_SHA256', INPUTS_SHA256)
    contract.require(project / 'Saved/Pose17Development' in path.parents and path.name == 'prepared_manifest.json'
        and contract.is_sha(identity) and joint.sha(path) == identity, '须绑定本轮实际新长窗CPU输入manifest SHA')
    return path


def checked(reference):
    path = old_source._plain_path(reference['path'])
    contract.require(joint.sha(path) == reference['sha256'], '输入SHA变化: ' + str(path))
    return path


def load_bundle(project):
    """仅消费新300/320前缀包及四配对计划，不把旧120输入转换放行。"""
    project = old_source._plain_path(project)
    path = prepared_path(project)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    contract.require(manifest.get('schema') == 'futsalmot_pose17_long_window_prepared_inputs_v1'
        and manifest.get('batch_id') == contract.BATCH_ID and manifest.get('capture_started') is False
        and manifest.get('training_authorized') is False and manifest.get('production_admitted') is False,
        '只能消费独立未捕获长窗候选')
    plans = [json.loads(checked(reference).read_text(encoding='utf-8')) for reference in manifest['plans']]
    contract.require(len(plans) == 4 and len({p['attempt'] for p in plans}) == 4, '需要四个唯一蓝/红棕计划')
    for seed in contract.WINDOWS:
        contract.validate_floor_pair([p for p in plans if p['long_window']['seed'] == seed])
    inputs = {}
    for reference in manifest['source_inputs']:
        input_path = checked(reference); source = json.loads(input_path.read_text(encoding='utf-8'))
        seed = source['seed']; contract.require(seed in contract.WINDOWS and seed not in inputs, '源seed重复/越界')
        start, end, split = contract.WINDOWS[seed]
        contract.require(source.get('schema') == 'futsalmot_pose17_long_window_source_input_v1'
            and source.get('selected_source_frame_range') == [start, end] and source.get('context_source_frame_range') == [0, end]
            and source.get('split') == split and source.get('prefix_steps') == end
            and source.get('native_records_per_camera') == 3000 <= 4096 and source.get('capture_started') is False,
            '新源时段/容量/状态不符')
        prefix = source['prepared_prefix']
        meta = json.loads(checked(prefix['meta']).read_text(encoding='utf-8'))
        frames = [json.loads(line) for line in checked(prefix['frames']).read_text(encoding='utf-8').splitlines() if line]
        mapping = [json.loads(line) for line in checked(prefix['frame_mapping']).read_text(encoding='utf-8').splitlines() if line]
        contract.require(meta['timing'] == dict(source_step_seconds=.1, playback_fps=10, num_steps=end)
            and len(frames) == end and [row['step'] for row in frames] == list(range(end))
            and len(mapping) == 300 and [row['grf_source_step'] for row in mapping] == list(range(start, end))
            and all(row['sequence_frame'] == row['grf_source_step'] and row['capture_local_index'] == i for i, row in enumerate(mapping)),
            '前缀/捕获local/源帧映射改变')
        for binding in source['calibration_manifests'].values():
            checked(binding)
        for plan in [p for p in plans if p['long_window']['seed'] == seed]:
            contract.require(plan['source_motion']['source_input'] == reference and plan['targets'] == source['targets']
                and source['P2_sequence_package'] == contract.PACKAGE + f'/seed_{seed:08d}'
                and Path(plan['source_motion']['source_build_receipt']) == path.parent / 'P2_sources_prepare.json',
                '计划与实际前缀/roster/P2收据不同')
            runner.validate_plan(plan)
        inputs[seed] = dict(source=source, input_path=input_path, meta=meta, frames=frames)
    contract.require(set(inputs) == set(contract.WINDOWS), '新源两seed不完整')
    return manifest, plans, inputs


def sources(project, action):
    """仅复用原导入算法建8个全新源Sequence，15Actor/canonical前后不变。"""
    import unreal
    manifest, plans, inputs = load_bundle(project)
    receipt = prepared_path(project).parent / ('P2_sources_' + action + '.json')
    contract.require(not receipt.exists(), '收据已存在，不覆盖/隐式续建partial')
    report = dict(schema='futsalmot_pose17_long_window_P2_sources_v1', action=action, status='started',
                  MRQ_submitted=False, dynamic_verified=False, sequences=[])
    try:
        contract.require(not joint._dirty(unreal), '存在未知dirty包')
        _, before = joint._scene(unreal, plans[0])
        paths = sorted({row['source_sequence'] for plan in plans for row in plan['cameras']})
        contract.require(len(paths) == 8 and not unreal.EditorAssetLibrary.does_directory_exist(contract.PACKAGE)
            and not any(unreal.EditorAssetLibrary.does_asset_exist(path) for path in paths), '独立源根/资产已存在，保留partial，不覆盖')
        canonical = [project / 'Content/FutsalMOT/Sequences' / f'LS_Cam_{i:02d}.uasset' for i in range(1, 5)]
        canonical.append(project / 'Content/FutsalMOT/Maps/L_FutsalCourt.umap')
        hashes = {str(path): joint.sha(path) for path in canonical}
        report.update(status='preflight_passed_not_rendered', scene_before=before, canonical_before=hashes,
                      inputs_manifest_sha256=joint.sha(prepared_path(project)), script_sha256=joint.sha(__file__))
        if action == 'prepare':
            builder = importlib.reload(importlib.import_module('import_grf_episode'))
            mapping = json.loads((Path(__file__).parent / 'actor_mapping.example.json').read_text(encoding='utf-8'))
            contract.require(mapping == {**{e: 'Player_' + e for e in joint.JOINT_VISUAL_IDS}, 'BALL': 'Ball_01'}, '原Actor mapping变化')
            for seed, item in inputs.items():
                end = contract.WINDOWS[seed][1]
                builder.create_sequence(item['meta'], item['frames'], mapping, replace_existing=False,
                    package_path=item['source']['P2_sequence_package'],
                    sequences_cfg=[dict(name='LS_Cam_' + cam[-2:], camera_actor=cam) for cam in contract.CAMERAS],
                    ball_rolling_cfg=dict(enabled=True, radius_m=.11, minimum_move_distance_m=.0001, roll_sign=1.),
                    open_after_create=False, run_api_smoke=False)
                for camera in [p for p in plans if p['long_window']['seed'] == seed][0]['cameras']:
                    report['sequences'].append(old_source._sequence_summary(unreal, camera['source_sequence'], camera['camera_id'], builder, end))
                _, after = joint._scene(unreal, plans[0])
                contract.require(before == after and not joint._dirty(unreal), '建源改变了Actor/dirty；停止保留partial')
            contract.require({str(path): joint.sha(path) for path in canonical} == hashes, 'canonical或地图变化')
            report.update(status='eight_new_source_sequences_saved_not_captured', scene_preserved=True)
        joint._dump_new(receipt, report)
        return report
    except Exception as error:
        report.update(status='failed_partial_preserved_no_retry', error=repr(error)); joint._dump_new(receipt, report); raise


def session_for(plan):
    session = getattr(sys.modules.get(runner._SESSION), 'prepared', None)
    contract.require(session is not None and session['plan'] == plan, '当前会话不属于精确长窗计划')
    return session


def configure_depth(plan):
    """仅配置自有未提交Queue，复用旧pilot实际通过的WorldDepth/AA配方。"""
    import unreal
    session = session_for(plan)
    contract.require(session['state']['status'] == 'prepared_not_submitted', '只能配置未提交自有队列')
    path = session['attempt'] / 'additional_depth_config.json'
    contract.require(not path.exists(), '深度收据已存在，不覆盖或隐式重配')
    rows = []
    for job in session['queue'].get_jobs():
        config = job.get_configuration(); deferred = config.find_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        passes = list(deferred.get_editor_property('additional_post_process_materials'))
        depth = [p for p in passes if p.get_editor_property('material').get_name() == 'MovieRenderQueue_WorldDepth']
        contract.require(len(depth) == 1, '已验WorldDepth材质不唯一')
        for key, value in dict(enabled=True, high_precision_output=True, use_lossless_compression=True, name='WorldDepth').items():
            depth[0].set_editor_property(key, value)
        deferred.set_editor_property('additional_post_process_materials', passes)
        deferred.set_editor_property('disable_multisample_effects', True)
        aa = config.find_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
        aa.set_editor_property('override_anti_aliasing', True)
        aa.set_editor_property('anti_aliasing_method', unreal.AntiAliasingMethod.AAM_NONE)
        enabled = [p for p in deferred.get_editor_property('additional_post_process_materials') if p.get_editor_property('enabled')]
        contract.require(len(enabled) == 1 and enabled[0].get_editor_property('name') == 'WorldDepth'
            and enabled[0].get_editor_property('high_precision_output') and enabled[0].get_editor_property('use_lossless_compression')
            and deferred.get_editor_property('disable_multisample_effects') and aa.get_editor_property('override_anti_aliasing')
            and aa.get_editor_property('anti_aliasing_method') == unreal.AntiAliasingMethod.AAM_NONE
            and int(aa.temporal_sample_count) == int(aa.spatial_sample_count) == 1, '深度/采样配置读回不符')
        rows.append(dict(job=str(job.job_name), material=enabled[0].get_editor_property('material').get_path_name(),
                         name='WorldDepth', high_precision=True, lossless=True, AA='none', temporal_samples=1, spatial_samples=1))
    contract.require([row['job'] for row in rows] == list(contract.CAMERAS), '深度必须完整四机位')
    report = dict(schema='futsalmot_smoke_depth_config_v1', applied_before_submit=True, jobs=rows,
                  depth_encoding_verified=False, base_plan_sha256=session['state']['plan_sha256'])
    joint._dump_new(path, report)
    return report


def floor(project, plan, action):
    """复用已验证唯一地板slot事务；不保存地图，不动角色/相机/灯光。"""
    import unreal
    import preview_floor_diversity_v1 as preview
    contract.require(not unreal.EditorLevelLibrary.get_pie_worlds(False)
        and not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering(), 'MRQ/PIE仍活动，不能改地板')
    if action == 'apply':
        session = session_for(plan)  # 先验证当前独立Queue，不能先改地板后才发现无自有会话。
        depth = json.loads((session['attempt'] / 'additional_depth_config.json').read_text(encoding='utf-8'))
        contract.require(depth['base_plan_sha256'] == session['state']['plan_sha256']
            and [row['job'] for row in depth['jobs']] == list(contract.CAMERAS), '先显式configure_depth再应用地板/放行提交')
    keys = dict(FUTSALMOT_FLOOR_PREVIEW_ACTION=action, FUTSALMOT_FLOOR_PREVIEW_APPLY='1' if action in ('apply', 'restore') else '0',
        FUTSALMOT_FLOOR_PREVIEW_ID=plan['long_window']['floor_variant_id'], FUTSALMOT_FLOOR_PREVIEW_SEED=str(plan['long_window']['seed']),
        FUTSALMOT_FLOOR_PREVIEW_SESSION=plan['attempt'], FUTSALMOT_FLOOR_PREVIEW_CAMERA='CineCam_01')
    previous = {key: os.environ.get(key) for key in keys}
    try:
        os.environ.update(keys); result = preview.main()
    finally:
        for key, value in previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
    if action == 'apply':
        contract.require(result['status'] == 'preview_active' and plan['long_window']['floor_variant_id'] in result['expected_current_material'], '实际地板应用失败')
        session = session_for(plan); session['state'].update(ready_to_render=True, long_window_floor_transaction=result,
            long_window_source_prepare_sha256=joint.sha(prepared_path(project).parent / 'P2_sources_prepare.json'))
        runner._write_state(session)
    return result


def main():
    import unreal
    project = old_source._plain_path(Path(unreal.Paths.project_dir()).resolve())
    action = os.environ.get('FUTSAL_POSE17_LONG_ACTION', 'preflight_sources')
    allowed = {'preflight_sources', 'prepare_sources', 'preflight_capture', 'prepare_capture', 'floor_preflight',
               'configure_depth', 'floor_apply', 'submit', 'postflight', 'floor_restore', 'release', 'cancel_memory_guard'}
    contract.require(action in allowed, '未知长窗动作')
    if action in ('preflight_sources', 'prepare_sources'):
        result = sources(project, 'prepare' if action == 'prepare_sources' else 'preflight')
    else:
        _, plans, _ = load_bundle(project)
        resume_path = os.environ.get('FUTSAL_POSE17_LONG_RESUME_ATTEMPTS')
        if resume_path:
            plans = resume_attempts(plans, resume_path, prepared_path(project))
        name = os.environ.get('FUTSAL_POSE17_LONG_ATTEMPT')
        selected = [plan for plan in plans if plan['attempt'] == name]
        contract.require(len(selected) == 1, '须明确四个长窗attempt之一')
        plan = selected[0]
        source_receipt = prepared_path(project).parent / 'P2_sources_prepare.json'
        source_state = json.loads(source_receipt.read_text(encoding='utf-8'))
        contract.require(source_state['status'] == 'eight_new_source_sequences_saved_not_captured'
            and source_state['inputs_manifest_sha256'] == joint.sha(prepared_path(project)), '新P2源尚未实际准备/来源变化')
        if action == 'preflight_capture': result = runner.preflight(plan)
        elif action == 'prepare_capture': result = runner.prepare(plan)
        elif action == 'configure_depth': result = configure_depth(plan)
        elif action.startswith('floor_'): result = floor(project, plan, action[6:])
        elif action == 'submit':
            session = session_for(plan)
            result = floor(project, plan, 'status')
            contract.require(result['state']['status'] == 'preview_active'
                and result['current_floor'] == session['state']['long_window_floor_transaction']['expected_current_material'], 'submit前地板事务不匹配')
            result = runner.submit()
        elif action == 'postflight': session_for(plan); result = runner.postflight()
        elif action == 'cancel_memory_guard':
            session = session_for(plan)
            contract.require(plan['attempt'].endswith('_a04_gpu_lbs')
                and session['executor'].is_rendering(), '仅允许本次活动a04自有MRQ内存保护')
            session['state']['program_memory_protection_requested'] = True
            session['state']['cancellation_source'] = 'program_commit_headroom_guard_not_user'
            runner._write_state(session)
            session['executor'].cancel_all_jobs()
            result = dict(status='owned_MRQ_memory_guard_cancellation_requested', user_cancel=False,
                          attempt=plan['attempt'], capture_accepted=False)
        elif action == 'release':
            session_for(plan); state = floor(project, plan, 'status')['state']
            contract.require(state['status'] == 'original_floor_slot_restored_not_saved', '先显式floor_restore再release')
            result = runner.release()
    print('POSE17_LONG_WINDOW ' + json.dumps(result, ensure_ascii=False, default=str))


def resume_attempts(plans, path, prepared):
    """仅换本轮独立任务名，复用原八个源Sequence及其真实创建收据。"""
    from copy import deepcopy
    path = Path(path).absolute()
    expected_parent = Path('G:/FutsalMOT_Workspace/UE/Saved/Pose17Development')
    contract.require(path.parent.name in ('resume_20261024_a02', 'resume_20261024_a03', 'resume_20261024_a04')
        and path.parent.parent == expected_parent and path.name == 'attempt_resume.json' and path.resolve() == path,
                     '续跑配置只能来自本轮明确G目录')
    config = json.loads(path.read_text(encoding='utf-8'))
    number = config.get('attempt_number', 2)
    contract.require(type(number) is int and number in (2, 3, 4)
        and path.parent.name == 'resume_20261024_a%02d' % number, '续跑编号与自有目录不符')
    contract.require(config.get('schema') == 'pose17_longpair_attempt_resume_a02'
        and config.get('base_prepared_sha256') == joint.sha(prepared)
        and config.get('reuse_source_sequences_only') is True
        and config.get('reuse_failed_media') is False, '新attempt来源或续跑边界不符')
    mapping = config.get('attempt_mapping', {})
    contract.require(set(mapping) == {p['attempt'] for p in plans}
        and all(p['attempt'].endswith('_a01_gpu_lbs')
                and mapping[p['attempt']] == p['attempt'].replace('_a01_gpu_lbs', '_a%02d_gpu_lbs' % number) for p in plans),
        '只能原四组精确换新任务名，不允许覆盖或换运动/地板')
    result = deepcopy(plans)
    for plan in result:
        plan['attempt'] = mapping[plan['attempt']]
        runner.validate_plan(plan)
    return result


if __name__ == '__main__': main()
