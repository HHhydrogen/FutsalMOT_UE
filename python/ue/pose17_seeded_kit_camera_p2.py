"""单机位生命周期P2；原四机位/运动/roster源计划保持不变，显式记录实际执行子集。"""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pose17_smoke_runner as runner
import pose17_seeded_kit_p2 as common
import preview_floor_diversity_v1 as preview
from pose17_camera_scope import session_cameras
from pose17_seeded_kit_contract import validate_seeded_kit_contract,context_payload,require

RUN=ROOT/'Saved/AppearancePlanning/seeded_kit_capture_a03'
read=common.read;sha=common.sha;resources=common.resources


def current(plan):
    value=getattr(sys.modules.get(runner._SESSION),'prepared',None)
    require(value is not None and value['plan']==plan,'没有精确自有单机位会话')
    return value


def settings(plan,camera):
    value=current(plan);kit=plan['seeded_kit_pair'];enabled=kit['apply_original_seeded_kits']
    require([c['camera_id'] for c in session_cameras(value)]==[camera] and len(value['settings'])==1,'实际Queue不是精确一机位')
    setting=value['settings'][0]
    require(setting.get_editor_property('apply_seeded_kit_for_diagnostic') is enabled,'实际服装开关不同')
    require(setting.get_editor_property('seeded_appearance_fingerprint')==(kit['binding']['source_appearance_fingerprint'] if enabled else ''),'清单fingerprint不同')
    targets=setting.get_editor_property('targets');require(len(targets)==10,'目标必须十人')
    for target in targets:
        entity=target.get_editor_property('entity_id');bound=next(x for x in kit['binding']['entities'] if x['entity_id']==entity)
        for semantic,field in (('Jersey','seeded_jersey_material'),('Shorts','seeded_shorts_material')):
            material=target.get_editor_property(field)
            require(material.get_path_name().split('.')[0]==bound['semantic_materials'][semantic] if enabled else material is None,'实际服装材质字段不同')
    return dict(camera_id=camera,targets=10,apply_seeded=enabled)


def configure_output(plan,camera):
    import unreal
    value=current(plan);require(value['state']['status']=='prepared_not_submitted','只配置未提交自有Queue')
    jobs=value['queue'].get_jobs();require(len(jobs)==1 and str(jobs[0].job_name)==camera,'输出作用域须一个实际job')
    config=jobs[0].get_configuration();deferred=config.find_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    passes=list(deferred.get_editor_property('additional_post_process_materials'))
    # 当前位置/身份研究不消费WorldDepth；A/B统一关闭此额外pass，仍保留ObjectID EXR。
    for material in passes:material.set_editor_property('enabled',False)
    deferred.set_editor_property('additional_post_process_materials',passes);deferred.set_editor_property('disable_multisample_effects',True)
    aa=config.find_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.set_editor_property('override_anti_aliasing',True);aa.set_editor_property('anti_aliasing_method',unreal.AntiAliasingMethod.AAM_NONE)
    enabled=[p for p in deferred.get_editor_property('additional_post_process_materials') if p.get_editor_property('enabled')]
    require(not enabled and deferred.get_editor_property('disable_multisample_effects') and aa.get_editor_property('override_anti_aliasing')
        and aa.get_editor_property('anti_aliasing_method')==unreal.AntiAliasingMethod.AAM_NONE
        and int(aa.temporal_sample_count)==int(aa.spatial_sample_count)==1,'单机位输出/AA真实读回失败')
    result=dict(schema='futsalmot_camera_partition_output_v1',camera_id=camera,base_plan_sha256=value['state']['plan_sha256'],
        full_four_camera_group_complete=False,AA='none',temporal_samples=1,spatial_samples=1,
        world_depth_requested=False,enabled_additional_materials=0,actor_objectID_EXR_retained=True)
    with (value['attempt']/'output_config.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    return result


def floor(plan,camera,action):
    import unreal
    require(not unreal.EditorLevelLibrary.get_pie_worlds(False) and not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering(),'活动PIE/MRQ不得改地板')
    value=current(plan)
    if action=='apply':
        cfg=read(value['attempt']/'output_config.json')
        require(cfg['camera_id']==camera and cfg['base_plan_sha256']==value['state']['plan_sha256'],'深度配置不是当前单机位')
        settings(plan,camera)
    env=dict(FUTSALMOT_FLOOR_PREVIEW_ACTION=action,FUTSALMOT_FLOOR_PREVIEW_APPLY='1' if action in ('apply','restore') else '0',
        FUTSALMOT_FLOOR_PREVIEW_ID='sport_blue_v1',FUTSALMOT_FLOOR_PREVIEW_SEED=str(plan['seeded_kit_pair']['seed']),
        FUTSALMOT_FLOOR_PREVIEW_SESSION=plan['attempt'],FUTSALMOT_FLOOR_PREVIEW_CAMERA=camera,
        FUTSALMOT_FLOOR_IMPORTED_ASSET_PROOF='pinned_imported_packages_v1',FUTSALMOT_FLOOR_IMPORTED_ASSET_BINDING=str(RUN/'floor_asset_binding.json'))
    previous={k:os.environ.get(k) for k in env}
    try:os.environ.update(env);result=preview.main()
    finally:
        for k,v in previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    if action=='apply':
        require(result['status']=='preview_active','蓝地板未实际应用')
        value['state'].update(ready_to_render=True,seeded_kit_floor_transaction=result,native_kit_settings_readback=[settings(plan,camera)])
        runner._write_state(value)
    return result


def main():
    import unreal
    request=read(RUN/'action_request.json');manifest=read(RUN/'manifest.json')
    unit=next(x for x in manifest['units'] if x['attempt']==request['attempt']);camera=unit['camera_id']
    require(request['editor_pid']==os.getpid(),'必须是本次实际Editor')
    require(sha(unit['plan']['path'])==unit['plan']['sha256'] and sha(unit['canonical_full_plan']['path'])==unit['canonical_full_plan']['sha256'],'源计划SHA改变')
    plan=read(unit['plan']['path']);parent=read(unit['canonical_full_plan']['path'])
    require(validate_seeded_kit_contract(plan) and context_payload(plan)==context_payload(parent),'源运动/四机位/服装上下文改变')
    for key in ('base_plan','source_input','original_appearance'):
        ref=plan['seeded_kit_pair'][key];require(sha(common.project_source_path(ref['path']))==ref['sha256'],'原始来源改变')
    admission=read(RUN/'admission_full_a01.json')
    require(admission['runtime_authorized'] is True and admission['manifest_sha256']==sha(RUN/'manifest.json'),'没有新分区准入')
    for ref in admission['source_files']:require(sha(ROOT/ref['path'])==ref['sha256'],'冻结源文件变化')
    require(sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll')==admission['module_sha256'],'模块身份不同')
    action=request['action'];output=RUN/'ue_receipts'/(plan['attempt']+'__'+action+'.json')
    require(not output.exists(),'动作已完成，禁止重放')
    if action=='initialize_runtime':
        gate=runner.preflight();require(not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running'] and getattr(sys.modules.get(runner._SESSION),'prepared',None) is None,'不是clean/idle空会话')
        for command in ('ImageWriteQueue.MaxConcurrency 12','ImageWriteQueue.MaxQueueSize 8'):unreal.SystemLibrary.execute_console_command(None,command)
        values=[unreal.SystemLibrary.get_console_variable_int_value('ImageWriteQueue.'+n) for n in ('MaxConcurrency','MaxQueueSize')]
        require(values==[12,8],'队列/线程读回不符');result=dict(status='idle_runtime_12_8',values=values,resources=resources())
    elif action=='preflight':result=runner.preflight(plan)
    elif action=='prepare':result=runner.prepare(plan,camera_id=camera);settings(plan,camera)
    elif action=='configure_output':result=configure_output(plan,camera)
    elif action.startswith('floor_'):result=floor(plan,camera,action[6:])
    elif action=='submit':
        require(resources()['commit_headroom_bytes']>=20*1024**3,'提交前commit不足20GiB')
        settings(plan,camera);require(floor(plan,camera,'status')['state']['status']=='preview_active','地板状态不匹配')
        result=runner.submit()
    elif action=='postflight':current(plan);result=runner.postflight()
    elif action=='release':
        require(floor(plan,camera,'status')['state']['status']=='original_floor_slot_restored_not_saved','先真实恢复地板')
        result=runner.release()
    elif action=='failed_release_quit':
        from pose17_native_receipt import normalize_native_receipt
        value=current(plan);gate=runner.preflight();state=value['state']
        require(state['status']=='failed_requires_diagnosis' and not state.get('editor_restore_probe_pending')
            and state.get('editor_mesh_state_matched') is True and state.get('editor_scene_state_matched') is True
            and not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running']
            and not value['executor'].is_rendering(),'失败清理必须实际idle且角色/场景已恢复')
        require(floor(plan,camera,'status')['state']['status']=='original_floor_slot_restored_not_saved','自有地板未恢复')
        native=normalize_native_receipt(read(value['attempt']/(camera+'_native_pose_restore_receipt.json')))
        require(not native['restore_errors'] and native['camera_state_restored'] is True
            and native['streaming_state_restart_required'] is False
            and all(x['restore_succeeded'] for x in native['visual_mesh_overrides'])
            and all(x['restore_succeeded'] for x in native.get('seeded_kit_bindings',[])),'已执行native未恢复')
        for callback in value['callbacks']:
            value['executor'].on_executor_finished_delegate.remove_callable(callback)
            require(not value['executor'].on_executor_finished_delegate.contains_callable(callback),'自有delegate未解除')
        result=dict(status='failed_unit_cleanup_normal_quit_requested',capture_failed_preserved=True,
                    full_four_camera_group_complete=False,camera_id=camera,dirty_packages=[],PIE=[],MRQ=False)
        value.clear();sys.modules[runner._SESSION].prepared=None;runner._PREPARED=None
    elif action=='quit_after_release':
        gate=runner.preflight();holder=sys.modules.get(runner._SESSION)
        require(not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running'] and getattr(holder,'prepared',None) is None
            and getattr(holder,'last_release',None)==read(ROOT/'Saved/Pose17Development/smoke'/plan['attempt']/'session_release.json'),'退出门禁失败')
        result=dict(status='normal_quit_after_single_camera',camera_id=camera,owned_session_released=True)
    elif action=='cancel_memory_guard':
        path=RUN/'control_a01'/(plan['attempt']+'__memory_guard_event.json')
        event=read(path)
        require(sha(path)==request['guard_event_sha256'] and event['attempt']==plan['attempt']
            and event['editor_pid']==os.getpid() and 0<event['commit_headroom_bytes']<6*1024**3
            and 0<=time.time()-event['sampled_epoch_seconds']<=600,'缺本次有界时间内真实低commit事件')
        value=current(plan);require(value['executor'].is_rendering(),'自有executor未活动')
        value['executor'].cancel_all_jobs();result=dict(status='owned_cancel_requested_from_latched_real_event',event=event)
    else:raise ValueError('未知动作')
    output.parent.mkdir(exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str)
    print('KIT_CAMERA_UNIT '+json.dumps(dict(action=action,attempt=plan['attempt'],camera=camera,status=result.get('status'),errors=result.get('errors',[]))))
    if action in ('quit_after_release','failed_release_quit'):unreal.SystemLibrary.quit_editor()


if __name__=='__main__':main()
