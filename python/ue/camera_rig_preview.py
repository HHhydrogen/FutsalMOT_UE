"""真实CineCamera参数的16:9静态捕获；预览对象全部在finish恢复。"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/src'))
sys.path.insert(0,str(ROOT/'python/ue'))
from grf_ue_bridge.storage_policy import require_render_destination,record_test_render

_ACTIVE=None
OUT=ROOT/'Saved/CameraRigV2/preview_s1048_a01'
MEDIA=Path('G:/FutsalMOT_Dataset/test/camera_rig_v2_a01/raw')


def start(output_dir=None,media_dir=None):
    global _ACTIVE,OUT,MEDIA
    import unreal
    import run_task as runner
    from scene_apply import find_all_actors,apply_preview_frame
    assert _ACTIVE is None
    if output_dir is not None:
        out=Path(output_dir)
        assert out.resolve().parent==(ROOT/'Saved/CameraRigV2').resolve()
        OUT=out
    if media_dir is not None:
        MEDIA=require_render_destination(media_dir)
    output=require_render_destination(MEDIA)
    output.mkdir(parents=True,exist_ok=False)
    record_test_render(output,'rendering')
    profile=json.loads((OUT/'ue-profile.json').read_text(encoding='utf-8'))
    mapping=json.loads((ROOT/'python/ue/actor_mapping.example.json').read_text(encoding='utf-8'))
    appearance=runner._prepare_episode_appearance(profile,'sequence',OUT,mapping,str(ROOT/'python'),OUT.name)
    environment=runner._prepare_seeded_environment(profile,'sequence',OUT,None)
    transaction=runner._apply_prepared_environment_and_appearance(environment,appearance)
    actors=find_all_actors(mapping)
    ball=actors['BALL']
    ball_transform=ball.get_actor_transform()
    _ACTIVE={'transaction':transaction,'profile':profile,'ball':ball,'ball_transform':ball_transform,
             'capture':None,'target':None,'rows':[]}
    try:
        frame=json.loads((OUT/'frames.jsonl').read_text(encoding='utf-8'))
        apply_preview_frame(actors,frame,{})
        subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        capture=subsystem.spawn_actor_from_class(unreal.SceneCapture2D,unreal.Vector(0,0,100),unreal.Rotator(),True)
        assert capture
        _ACTIVE['capture']=capture
        component=capture.capture_component2d
        component.set_editor_property('capture_every_frame',False)
        component.set_editor_property('capture_on_movement',False)
        component.set_editor_property('always_persist_rendering_state',True)
        component.set_editor_property('capture_source',unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        component.set_editor_property('show_flag_settings',[
            unreal.EngineShowFlagsSetting(show_flag_name=n,enabled=False) for n in ('MotionBlur','DepthOfField','TemporalAA')])
        target=unreal.RenderingLibrary.create_render_target2d(capture,3840,2160,unreal.TextureRenderTargetFormat.RTF_RGBA8)
        _ACTIVE['target']=target
        target.set_editor_property('target_gamma',2.2)
        component.set_editor_property('texture_target',target)
        print('CAMERA_PREVIEW_STARTED',OUT.name)
    except BaseException:
        finish('failed_stopped')
        raise


def capture(cid):
    import unreal
    from scene_apply import find_actor
    assert _ACTIVE is not None
    p=_ACTIVE['profile']['seeded_episode']['camera_rig']['profiles'][cid]
    path=MEDIA/(cid+'.png')
    assert not path.exists(),path
    actor=find_actor(p['actor'])
    assert actor and actor.get_class().get_name()=='CineCameraActor'
    camera=actor.get_cine_camera_component()
    source=_ACTIVE['capture']
    source.set_actor_transform(actor.get_actor_transform(),False,False)
    component=source.capture_component2d
    component.set_editor_property('fov_angle',float(camera.get_editor_property('current_horizontal_fov')))
    component.set_editor_property('post_process_settings',camera.get_editor_property('post_process_settings'))
    component.set_editor_property('post_process_blend_weight',float(camera.get_editor_property('post_process_blend_weight')))
    for _ in range(3):
        component.capture_scene()
    unreal.RenderingLibrary.export_render_target(source,_ACTIVE['target'],str(MEDIA),cid+'.png')
    assert path.is_file() and path.stat().st_size>0,path
    pos=actor.get_actor_location();rot=actor.get_actor_rotation();filmback=camera.get_editor_property('filmback')
    row={'camera_id':cid,'actor':p['actor'],'source':'SceneCapture2D_from_actual_CineCamera_static_preview_not_MRQ',
         'level':'/Game/FutsalMOT/Maps/L_FutsalCourt','source_step':300,'resolution':[3840,2160],
         'position_m':[pos.x/100,pos.y/100,pos.z/100],'rotation_deg':[rot.pitch,rot.yaw,rot.roll],
         'focal_length_mm':float(camera.get_editor_property('current_focal_length')),
         'horizontal_fov_deg':float(camera.get_editor_property('current_horizontal_fov')),
         'filmback_mm':[filmback.sensor_width,filmback.sensor_height]}
    _ACTIVE['rows'].append(row)
    (OUT/(cid+'_actual.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CAMERA_CAPTURED',cid,str(path))


def finish(state='complete'):
    global _ACTIVE
    import unreal
    assert _ACTIVE is not None
    active=_ACTIVE
    if active['capture'] is not None:
        active['capture'].capture_component2d.set_editor_property('texture_target',None)
    if active['target'] is not None:
        unreal.RenderingLibrary.release_render_target2d(active['target'])
    if active['capture'] is not None:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(active['capture'])
    active['ball'].set_actor_transform(active['ball_transform'],False,False)
    restored=active['transaction'].restore('no_render')
    assert restored.get('ok'),restored
    dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+
           list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert not dirty,dirty
    report={'status':'static_preview_finished_restored','capture_count':len(active['rows']),
            'captures':active['rows'],'restore':restored,'dirty_after':[],'MRQ':False}
    (OUT/'preview_complete.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    record_test_render(MEDIA,state)
    _ACTIVE=None
    print('CAMERA_PREVIEW_FINISHED',len(active['rows']))
