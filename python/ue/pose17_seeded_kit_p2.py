"""原seed服装配对P2入口：显式单步事务，不重放旧驱动，不隐式开始训练。"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import pose17_smoke_runner as runner
import pose17_long_window_p2 as depth_recipe
import preview_floor_diversity_v1 as preview
from pose17_seeded_kit_contract import validate_seeded_kit_contract,require

PROJECT=Path(__file__).resolve().parents[2]
RUN=PROJECT/'Saved/AppearancePlanning/seeded_kit_capture_a02'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def project_source_path(value):
    path=Path(value)
    require('..' not in path.parts,'来源路径不得含父目录逃逸')
    path=path if path.is_absolute() else PROJECT/path
    require(PROJECT in path.parents,'来源必须位于实际D项目内')
    return path


def resources():
    class Info(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in
            ('CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable',
             'SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[
             ('HandleCount',ctypes.c_ulong),('ProcessCount',ctypes.c_ulong),('ThreadCount',ctypes.c_ulong)]
    info=Info();info.cb=ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info),info.cb):raise ctypes.WinError()
    return dict(commit_headroom_bytes=(info.CommitLimit-info.CommitTotal)*info.PageSize,
                physical_available_bytes=info.PhysicalAvailable*info.PageSize)


def session(plan):
    holder=sys.modules.get(runner._SESSION);value=getattr(holder,'prepared',None)
    require(value is not None and value['plan']==plan,'不是当前精确自有会话')
    return value


def source_gate(request,plan):
    name=request.get('admission_file','admission_'+plan['seeded_kit_pair']['stage']+'.json')
    require(Path(name).name==name and name.startswith('admission_'+plan['seeded_kit_pair']['stage']),'准入文件名越界')
    path=RUN/name
    admission=read(path)
    require(admission['runtime_authorized'] is True and admission['stage']==plan['seeded_kit_pair']['stage'], '本阶段没有独立运行准入')
    require(admission['manifest_sha256']==sha(RUN/'manifest.json'),'配对清单改变')
    for item in admission['source_files']:
        require(sha(PROJECT/item['path'])==item['sha256'],'运行源代码改变，保留现场不继续')
    require(sha(PROJECT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll')==admission['module_sha256'],'新模块DLL与准入不符')
    return admission


def verify_settings(plan):
    current=session(plan);kit=plan['seeded_kit_pair'];apply=kit['apply_original_seeded_kits'];rows=[]
    for setting in current['settings']:
        require(setting.get_editor_property('apply_seeded_kit_for_diagnostic') is apply,'native服装opt-in读回错误')
        require(setting.get_editor_property('seeded_appearance_fingerprint')==(kit['binding']['source_appearance_fingerprint'] if apply else ''),'native原manifest指纹不匹配')
        targets=setting.get_editor_property('targets');require(len(targets)==10,'native目标不是十人')
        for target in targets:
            entity=target.get_editor_property('entity_id')
            bound=next(r for r in kit['binding']['entities'] if r['entity_id']==entity)
            for semantic,field in (('Jersey','seeded_jersey_material'),('Shorts','seeded_shorts_material')):
                value=target.get_editor_property(field)
                require(value.get_path_name().split('.')[0]==bound['semantic_materials'][semantic] if apply else value is None,'native材质参数读回不符')
        rows.append(dict(targets=10,apply_seeded=apply))
    require(len(rows)==4,'须完整四个相机job')
    return rows


def floor(plan,action):
    import unreal
    if getattr(preview,'IMPORTED_ASSET_PROOF_VERSION',0)!=1:
        import importlib
        importlib.reload(preview)  # 纯函数模块，无UClass/持久UObject；不reload MCP Toolset。
    require(not unreal.EditorLevelLibrary.get_pie_worlds(False)
        and not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering(),'活动PIE/MRQ不得改地板')
    current=session(plan)
    if action=='apply':
        cfg=read(current['attempt']/'additional_depth_config.json')
        require(cfg['base_plan_sha256']==current['state']['plan_sha256'],'先配置同一计划的已验深度/AA配方')
        verify_settings(plan)
    kit=plan['seeded_kit_pair']
    values=dict(FUTSALMOT_FLOOR_PREVIEW_ACTION=action,FUTSALMOT_FLOOR_PREVIEW_APPLY='1' if action in ('apply','restore') else '0',
        FUTSALMOT_FLOOR_PREVIEW_ID='sport_blue_v1',FUTSALMOT_FLOOR_PREVIEW_SEED=str(kit['seed']),
        FUTSALMOT_FLOOR_PREVIEW_SESSION=plan['attempt'],FUTSALMOT_FLOOR_PREVIEW_CAMERA='CineCam_01')
    values['FUTSALMOT_FLOOR_IMPORTED_ASSET_PROOF']='pinned_imported_packages_v1'
    values['FUTSALMOT_FLOOR_IMPORTED_ASSET_BINDING']=str(RUN/'floor_asset_binding.json')
    previous={k:os.environ.get(k) for k in values}
    try:os.environ.update(values);result=preview.main()
    finally:
        for k,v in previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    if action=='apply':
        require(result['status']=='preview_active' and 'sport_blue_v1' in result['expected_current_material'],'实际蓝地板未应用')
        current['state'].update(ready_to_render=True,seeded_kit_floor_transaction=result,native_kit_settings_readback=verify_settings(plan))
        runner._write_state(current)
    return result


def main():
    global runner
    if getattr(runner,'MEDIA_ROOT_CONTRACT_VERSION',0)!=1:
        # 首次提交前的纯Python入口换版，专用holder保留原Queue；不重建、不碰Toolset UClass。
        holder=sys.modules.get(runner._SESSION)
        prepared=getattr(holder,'prepared',None)
        require(prepared is None or prepared['state']['status']=='prepared_not_submitted',
                '活动/已提交会话禁止更换运行入口')
        import importlib
        runner=importlib.reload(runner)
        runner._PREPARED=prepared
    request=read(RUN/'action_request.json');manifest=read(RUN/'manifest.json')
    refs=[r for r in manifest['plans'] if r['attempt']==request['attempt']]
    require(len(refs)==1,'必须指定此批唯一attempt')
    ref=refs[0];require(sha(ref['path'])==ref['sha256'],'计划SHA变化')
    plan=read(ref['path']);validate_seeded_kit_contract(plan)
    for key in ('base_plan','source_input','original_appearance'):
        source=plan['seeded_kit_pair'][key]
        require(sha(project_source_path(source['path']))==source['sha256'],'原配对来源改变：'+key)
    action=request['action'];output=RUN/'ue_receipts'/(request['attempt']+'__'+action+'.json')
    require(not output.exists(),'单次动作收据已存在，禁止重复写调用')
    require(action in ('preflight','prepare','configure_depth','floor_preflight','floor_apply','floor_status','floor_restore','submit','postflight','release','cancel_memory_guard','initialize_runtime','quit_after_release'),'未知动作')
    if action!='preflight':source_gate(request,plan)
    if plan['seeded_kit_pair']['stage']=='full':
        require(request.get('editor_pid')==os.getpid(),'整批动作须绑定本次真实Editor PID')
    if action=='initialize_runtime':
        import unreal
        gate=runner.preflight()
        require(not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running']
            and getattr(sys.modules.get(runner._SESSION),'prepared',None) is None,'只有clean/idle/无自有session才初始化队列')
        before=[unreal.SystemLibrary.get_console_variable_int_value('ImageWriteQueue.'+n) for n in ('MaxConcurrency','MaxQueueSize')]
        for command in ('ImageWriteQueue.MaxConcurrency 12','ImageWriteQueue.MaxQueueSize 8'):
            unreal.SystemLibrary.execute_console_command(None,command)
        after=[unreal.SystemLibrary.get_console_variable_int_value('ImageWriteQueue.'+n) for n in ('MaxConcurrency','MaxQueueSize')]
        require(after==[12,8],'整批写线程/队列实际读回不是12/8')
        result=dict(status='idle_write_runtime_12_threads_queue8_readback_verified',before=before,after=after,
            editor_pid=os.getpid(),level=gate['level'],dirty_packages=[],PIE=[],MRQ=False,resources=resources())
    elif action=='quit_after_release':
        gate=runner.preflight();holder=sys.modules.get(runner._SESSION)
        released=read(PROJECT/'Saved/Pose17Development/smoke'/plan['attempt']/'session_release.json')
        require(not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running']
            and getattr(holder,'prepared',None) is None and getattr(holder,'last_release',None)==released,
            '退出前当前真实clean/idle和自有释放证据不匹配')
        result=dict(status='normal_quit_requested_after_owned_full_capture',editor_pid=os.getpid(),
            dirty_packages=[],PIE=[],MRQ=False,owned_session_released=True,attempt=plan['attempt'])
    elif action=='preflight':
        import unreal
        result=runner.preflight(plan)
        inventory=[]
        for i in range(1,16):
            paths=['/Game/FutsalMOT/Characters/MPFB/'+folder+'/'+prefix+kind+'_Set_%02d'%(i)
                for folder,prefix in (('Materials','M_MPFB_'),('Textures','T_MPFB_')) for kind in ('Jersey','Shorts')]
            require(all(unreal.EditorAssetLibrary.does_asset_exist(path) for path in paths),'已知服装Set资产不完整：%02d'%i)
            inventory.append(dict(set_id='%02d'%i,assets=paths))
        result['existing_kit_asset_inventory']=inventory
        result['selected_appearance_v1_catalog_ids']=['%02d'%i for i in range(1,6)]
    elif action=='prepare':
        result=runner.prepare(plan);verify_settings(plan)
    elif action=='configure_depth':result=depth_recipe.configure_depth(plan)
    elif action.startswith('floor_'):result=floor(plan,action[6:])
    elif action=='submit':
        current=session(plan);budget=resources()
        require(budget['commit_headroom_bytes']>=16*1024**3,'提交前系统commit不足16GiB，未启动MRQ')
        verify_settings(plan);status=floor(plan,'status')
        require(status['state']['status']=='preview_active','提交前蓝地板事务不在预期状态')
        result=runner.submit()
    elif action=='postflight':session(plan);result=runner.postflight()
    elif action=='release':
        status=floor(plan,'status');require(status['state']['status']=='original_floor_slot_restored_not_saved','先恢复地板再释放')
        result=runner.release()
    else:
        current=session(plan);budget=resources()
        require(budget['commit_headroom_bytes']<6*1024**3,'只有真实commit保护触发可调用自动取消')
        require(current['executor'].is_rendering(),'自有executor未活动')
        current['executor'].cancel_all_jobs();result=dict(status='owned_memory_guard_cancellation_requested',resources=budget)
    output.parent.mkdir(exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
    print('SEEDED_KIT_P2 '+json.dumps(dict(action=action,attempt=plan['attempt'],
        status=result.get('status',result.get('action')),errors=result.get('errors',[]),
        inventory_sets=len(result.get('existing_kit_asset_inventory',[])),receipt=str(output)),ensure_ascii=False))
    if action=='quit_after_release':
        import unreal
        unreal.SystemLibrary.quit_editor()


if __name__=='__main__':main()
