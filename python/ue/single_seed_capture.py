"""单seed MRQ入口；复用原run_task事务，元数据采用原生body12 pass。"""
import json
import os
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'python/src'))
sys.path.insert(0,str(PROJECT/'python/ue'))


def preflight(local):
    import unreal
    from grf_ue_bridge.single_seed import read,dump
    local=Path(local);resolved=read(local/'resolved.json')
    mapping=read(resolved['actor_mapping'])
    dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+
           list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    world=unreal.EditorLevelLibrary.get_editor_world()
    if world.get_path_name()!='/Game/FutsalMOT/Maps/L_FutsalCourt.L_FutsalCourt' or dirty or unreal.EditorLevelLibrary.get_pie_worlds(False) or unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering():
        raise RuntimeError('单seed入口需要规范地图、clean且无PIE/MRQ')
    actors=unreal.EditorLevelLibrary.get_all_level_actors()
    for entity,label in mapping.items():
        matches=[a for a in actors if a.get_actor_label()==label]
        if len(matches)!=1:
            raise RuntimeError('映射Actor不唯一: '+entity)
        if entity!='BALL':
            components=[c for c in matches[0].get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='MPFBVisual']
            if len(components)!=1 or components[0].get_editor_property('skeletal_mesh_asset') is None:
                raise RuntimeError('缺实际可见角色网格: '+entity)
    recipe=read(Path(resolved['trajectory_output'])/'provenance/seeded_episode.json')
    cameras=[]
    for entry in recipe['components']['cameras']['entries']:
        matches=[a for a in actors if a.get_actor_label()==entry['camera_actor']]
        if len(matches)!=1:
            raise RuntimeError('相机不唯一')
        actor=matches[0];component=actor.get_cine_camera_component()
        pos=actor.get_actor_location();rot=actor.get_actor_rotation();profile=entry['profile']
        position=[pos.x/100,pos.y/100,pos.z/100];rotation=[rot.pitch,rot.yaw,rot.roll]
        # Editor重启后的角度可能与已确认配置不同；任务先应用确认profile再建序列。
        # 此处登记差异，最终逐帧native必须与已确认profile相符。
        differs=any(abs(a-b)>1e-3 for a,b in zip(position,profile['position_m'])) or any(abs(a-b)>1e-3 for a,b in zip(rotation,profile['rotation_deg']))
        cameras.append({'camera_id':entry['camera_id'],'position_m':position,'rotation_deg':rotation,
                        'focal_length_mm':component.get_editor_property('current_focal_length'),
                        'runtime_will_apply_confirmed_profile':differs})
    # 等待本轮实际四套母材质与号码后处理编译就绪，沿用已验接口。
    from jersey_number_uv_build_catalog import DESTINATION
    from jersey_number_uv_build_mask_preview import POST_PROCESS_PATH
    for kit in sorted(set(e['kit_set_id'] for e in recipe['components']['appearance']['entities'])):
        material=unreal.load_asset(DESTINATION+'/M_Jersey_Set_'+kit+'_NumberUV_v1')
        if material is None:
            raise RuntimeError('缺号码派生材质: '+kit)
        unreal.MaterialEditingLibrary.get_statistics(material)
    unreal.MaterialEditingLibrary.get_statistics(unreal.load_asset(POST_PROCESS_PATH))
    report={'status':'preflight_passed','level':world.get_path_name(),'dirty':dirty,
            'cameras':cameras,'body12_class':str(unreal.FutsalBody12MRQPass)}
    dump(local/'ue_preflight.json',report)
    print('SINGLE_SEED_PREFLIGHT',json.dumps(report,ensure_ascii=False))
    return report


def submit(local,short=False):
    import shutil
    from grf_ue_bridge.single_seed import read
    from grf_ue_bridge.single_seed_export import assert_bindings
    local=Path(local);protocol=read(local/'protocol.json')
    assert_bindings(PROJECT,local,protocol)
    unit=local/'short' if short else local
    preflight(local)
    # 完整采集必须消费本次短样成功收据；不以旧字体/旧机位短样替代。
    if not short and read(local/'short/verification_complete.json')['status']!='single_seed_check_passed':
        raise RuntimeError('本轮短样尚未通过')
    resolved=read(unit/'resolved.json')
    media=Path(resolved['dataset_root'])/resolved['episode_name']
    limits=protocol['request']['storage']
    width,height=protocol['request']['resolution']
    if [width,height]!=[3840,2160]:
        raise ValueError('新采集统一4K，不回退1080p')
    # 按像素估算RGB/EXR/后处理并存峰值，4K不再误用1080p预算。
    estimated_bytes=resolved['export_profile']['num_steps']*len(protocol['recipe']['components']['cameras']['entries'])*width*height*6
    if estimated_bytes>limits['stage_limit_bytes'] or shutil.disk_usage('G:/FutsalMOT_Dataset').free<estimated_bytes+limits['min_free_bytes']:
        raise OSError('本次单seed预计媒体容量超出协议或G盘余量不足')
    if (media/'render_summary.json').exists():
        raise FileExistsError('不重复提交既有attempt')
    previous={key:os.environ.get(key) for key in ('C5_RESOLVED_TASK','C5_RUN_MODE','C5_CAMERA_IDS')}
    previous_argv=sys.argv
    try:
        os.environ['C5_RESOLVED_TASK']=str(unit/'resolved.json');os.environ['C5_RUN_MODE']='full'
        os.environ.pop('C5_CAMERA_IDS',None)
        sys.argv=[str(PROJECT/'python/ue/run_task.py')]
        import run_task
        result=run_task.main()
        if result:
            raise RuntimeError('run_task提交失败: '+str(result))
    finally:
        sys.argv=previous_argv
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    print('SINGLE_SEED_SUBMITTED',resolved['task_id'])
