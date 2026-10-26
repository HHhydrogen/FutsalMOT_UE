"""绿色新准入P2；复用原native球衣及串行单机位流程，不接性能候选。"""
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
import pose17_smoke_runner as runner
import pose17_seeded_kit_p2 as common
import pose17_seeded_kit_camera_p2 as camera_ops
import pose17_green_floor_transaction as green_floor
from pose17_seeded_kit_contract import validate_seeded_kit_contract,require

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01'
read=common.read;sha=common.sha;resources=common.resources


def settings(plan,camera):
    return [camera_ops.settings(plan,camera)] if camera else common.verify_settings(plan)


def configure(plan,camera):
    if camera:return camera_ops.configure_output(plan,camera)
    import unreal
    value=common.session(plan);require(value['state']['status']=='prepared_not_submitted','只能配置未提交自有Queue')
    jobs=value['queue'].get_jobs();require(len(jobs)==4,'短样须四机位')
    for job in jobs:
        config=job.get_configuration();deferred=config.find_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        passes=list(deferred.get_editor_property('additional_post_process_materials'))
        for material in passes:material.set_editor_property('enabled',False)
        deferred.set_editor_property('additional_post_process_materials',passes);deferred.set_editor_property('disable_multisample_effects',True)
        aa=config.find_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
        aa.set_editor_property('override_anti_aliasing',True);aa.set_editor_property('anti_aliasing_method',unreal.AntiAliasingMethod.AAM_NONE)
        require(not any(p.get_editor_property('enabled') for p in deferred.get_editor_property('additional_post_process_materials'))
            and deferred.get_editor_property('disable_multisample_effects') and aa.temporal_sample_count==aa.spatial_sample_count==1
            and aa.get_editor_property('anti_aliasing_method')==unreal.AntiAliasingMethod.AAM_NONE,'短样输出读回失败')
    result=dict(schema='futsalmot_green_kit_four_camera_output_v1',base_plan_sha256=value['state']['plan_sha256'],
        world_depth_requested=False,enabled_additional_materials=0,actor_objectID_EXR_retained=True,AA='none',temporal_samples=1,spatial_samples=1)
    with (value['attempt']/'output_config.json').open('x',encoding='utf-8') as f:common.json.dump(result,f,indent=2)
    return result


def main(run_dir=RUN):
    import unreal
    RUN=Path(run_dir)
    is_v10=RUN==ROOT/'Saved/AppearancePlanning/multiseed_v10_a01'
    require(is_v10 or RUN==ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01','未登记运行scope')
    request=read(RUN/'action_request.json');manifest=read(RUN/'manifest.json')
    refs=manifest['plans']+manifest.get('full_units',[]);ref=next(r for r in refs if r['attempt']==request['attempt'])
    require(request['editor_pid']==os.getpid(),'不是本次Editor')
    require(sha(ref['path'])==ref['sha256'],'计划变化')
    plan=read(ref['path']);require(validate_seeded_kit_contract(plan) and plan['green_seeded_kit_contract'] is True,'非新绿色契约')
    require((plan.get('v10_multiseed_contract') is True) is is_v10,'运行scope与计划身份不符')
    stage=plan['seeded_kit_pair']['stage'];camera=ref.get('camera_id')
    admission=read(RUN/('admission_'+stage+'_a01.json'))
    require(admission['runtime_authorized'] is True and admission['stage']==stage and admission['manifest_sha256']==sha(RUN/'manifest.json'),'无新阶段准入')
    if is_v10:
        require(admission['schema']=='futsalmot_v10_multiseed_admission_v1'
            and admission['source_prepare_sha256']==sha(RUN/'P2_sources_prepare.json')
            and read(RUN/'P2_sources_prepare.json')['status']=='twelve_new_source_sequences_saved_not_captured','v10真实源未建成')
    for item in admission['source_files']:require(sha(ROOT/item['path'])==item['sha256'],'绑定代码/资产变化：'+item['path'])
    require(sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll')==admission['module_sha256'],'DLL身份变化')
    for key in ('base_plan','source_input','original_appearance'):
        source=plan['seeded_kit_pair'][key];require(sha(common.project_source_path(source['path']))==source['sha256'],'原始来源变化')
    proof=plan['seeded_kit_pair']['green_floor']['creation_proof'];require(sha(common.project_source_path(proof['path']))==proof['sha256'],'绿色创建来源变化')
    action=request['action'];output=RUN/'ue_receipts'/(plan['attempt']+'__'+action+'.json')
    require(not output.exists(),'单次动作已存在，不重放')
    if action=='initialize_runtime':
        gate=runner.preflight();require(not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running']
            and getattr(sys.modules.get(runner._SESSION),'prepared',None) is None,'非clean/idle/空会话')
        for command in ('ImageWriteQueue.MaxConcurrency 12','ImageWriteQueue.MaxQueueSize 8'):unreal.SystemLibrary.execute_console_command(None,command)
        values=[unreal.SystemLibrary.get_console_variable_int_value('ImageWriteQueue.'+n) for n in ('MaxConcurrency','MaxQueueSize')]
        require(values==[12,8],'已验队列参数读回不符');result=dict(status='idle_12_8_verified',resources=resources())
    elif action=='preflight':result=runner.preflight(plan)
    elif action=='prepare':result=runner.prepare(plan,camera_id=camera);settings(plan,camera)
    elif action=='configure_output':result=configure(plan,camera)
    elif action.startswith('floor_'):
        value=common.session(plan)
        if action=='floor_apply':
            config=read(value['attempt']/'output_config.json');require(config['base_plan_sha256']==value['state']['plan_sha256'],'输出身份变化');settings(plan,camera)
        result=green_floor.main(plan,action[6:])
        if action=='floor_apply':value['state'].update(ready_to_render=True,green_floor_transaction=result,native_kit_settings_readback=settings(plan,camera));runner._write_state(value)
        if action=='floor_restore':value['state']['green_floor_restored']=result;runner._write_state(value)
    elif action=='submit':
        require(resources()['commit_headroom_bytes']>=20*1024**3,'提交前commit不足20GiB')
        settings(plan,camera);require(green_floor.main(plan,'status')['state']['status']=='preview_active','实际绿色事务未就绪')
        result=runner.submit()
    elif action=='postflight':common.session(plan);result=runner.postflight()
    elif action=='release':
        require(green_floor.main(plan,'status')['state']['status']=='original_floor_slot_restored_not_saved','先恢复原地板')
        result=runner.release()
    elif action=='cancel_memory_guard':
        eventpath=RUN/'control_'+stage+'_a01'/(plan['attempt']+'__memory_guard_event.json');event=read(eventpath)
        require(sha(eventpath)==request['guard_event_sha256'] and event['attempt']==plan['attempt'] and event['editor_pid']==os.getpid()
            and 0<event['commit_headroom_bytes']<6*1024**3 and 0<=time.time()-event['sampled_epoch_seconds']<=600,'不是本次真实有界低commit事件')
        value=common.session(plan);require(value['executor'].is_rendering(),'自有MRQ未活动');value['executor'].cancel_all_jobs()
        result=dict(status='owned_cancel_requested_from_real_event')
    elif action=='quit_after_release':
        gate=runner.preflight();holder=sys.modules.get(runner._SESSION)
        require(not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running'] and getattr(holder,'prepared',None) is None
            and getattr(holder,'last_release',None)==read(ROOT/'Saved/Pose17Development/smoke'/plan['attempt']/'session_release.json'),'退出门禁不符')
        result=dict(status='normal_quit_after_green_capture',owned_session_released=True)
    elif action=='failed_release_quit':
        from pose17_native_receipt import normalize_native_receipt
        value=common.session(plan);gate=runner.preflight();state=value['state']
        require(state['status']=='failed_requires_diagnosis' and not state.get('editor_restore_probe_pending')
            and state.get('editor_mesh_state_matched') is True and state.get('editor_scene_state_matched') is True
            and not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running']
            and not value['executor'].is_rendering(),'失败清理必须真实idle且已恢复')
        require(green_floor.main(plan,'status')['state']['status']=='original_floor_slot_restored_not_saved','自有地板未恢复')
        found=0
        for cam in runner.session_cameras(value):
            path=value['attempt']/(cam['camera_id']+'_native_pose_restore_receipt.json')
            if not path.exists():continue
            found+=1;native=normalize_native_receipt(read(path))
            require(not native['restore_errors'] and native['camera_state_restored'] is True
                and native['streaming_state_restart_required'] is False
                and all(x['restore_succeeded'] for x in native['visual_mesh_overrides'])
                and all(x['restore_succeeded'] for x in native.get('seeded_kit_bindings',[])),'实际执行native尚未恢复')
        require(found>0,'未取得已执行native恢复收据，不猜测成功')
        for callback in value['callbacks']:
            value['executor'].on_executor_finished_delegate.remove_callable(callback)
            require(not value['executor'].on_executor_finished_delegate.contains_callable(callback),'自有回调未释放')
        result=dict(status='failed_green_capture_restored_normal_quit_requested',capture_failed_preserved=True,native_receipts=found)
        value.clear();sys.modules[runner._SESSION].prepared=None;runner._PREPARED=None
    else:raise ValueError('未知动作：'+action)
    output.parent.mkdir(exist_ok=True)
    with output.open('x',encoding='utf-8') as f:common.json.dump(result,f,ensure_ascii=False,indent=2,default=str)
    print('GREEN_KIT_ACTION '+common.json.dumps(dict(action=action,attempt=plan['attempt'],status=result.get('status'),errors=result.get('errors',[]))))
    if action in ('quit_after_release','failed_release_quit'):unreal.SystemLibrary.quit_editor()


if __name__=='__main__':main()
