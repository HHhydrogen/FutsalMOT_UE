"""调整九个可编辑CineCamera；只保存本任务相机及必要地图包。"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/src'))
from grf_ue_bridge.camera_rig import validate_rig


def main():
    import unreal
    rig=json.loads((ROOT/'python/configs/camera_rig_v2.json').read_text(encoding='utf-8'))
    validate_rig(rig)
    level='/Game/FutsalMOT/Maps/L_FutsalCourt'
    world=unreal.EditorLevelLibrary.get_editor_world()
    assert world.get_path_name().split('.')[0]==level
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    dirty=lambda:list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert not dirty(),[p.get_path_name() for p in dirty()]
    evidence=ROOT/'Saved/CameraRigV2'
    assert not (evidence/'configuration_intent.json').exists(),'已有相机配置事务，不重放'
    actors=unreal.EditorLevelLibrary.get_all_level_actors()
    before=[]
    found={}
    for cid,p in rig['profiles'].items():
        matches=[a for a in actors if a.get_actor_label()==p['actor']]
        assert len(matches)<=1
        if matches:
            a=matches[0]
            assert a.get_class().get_name()=='CineCameraActor'
            c=a.get_cine_camera_component()
            pos=a.get_actor_location();rot=a.get_actor_rotation();f=c.get_editor_property('filmback')
            before.append({'camera_id':cid,'actor':p['actor'],'position_m':[pos.x/100,pos.y/100,pos.z/100],
                'rotation_deg':[rot.pitch,rot.yaw,rot.roll],'focal_length_mm':float(c.get_editor_property('current_focal_length')),
                'filmback_mm':[f.sensor_width,f.sensor_height],'package':a.get_package().get_path_name()})
            found[cid]=a
    assert set(found)=={'C1','C2','C3','C4','C5','P01'},'原六个相机集合不符'
    (evidence/'configuration_intent.json').write_text(json.dumps({'before':before,'target':rig},ensure_ascii=False,indent=2),encoding='utf-8')
    subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    readback=[]
    packages={level}
    for cid,p in rig['profiles'].items():
        loc=unreal.Vector(*[v*100 for v in p['position_m']])
        rot=unreal.Rotator(pitch=p['rotation_deg'][0],yaw=p['rotation_deg'][1],roll=p['rotation_deg'][2])
        a=found.get(cid)
        if a is None:
            a=subsystem.spawn_actor_from_class(unreal.CineCameraActor,loc,rot,False)
            assert a
            a.set_actor_label(p['actor'])
        a.modify()
        a.set_actor_location_and_rotation(loc,rot,False,False)
        c=a.get_cine_camera_component()
        c.modify()
        filmback=c.get_editor_property('filmback')
        filmback.sensor_width,filmback.sensor_height=rig['filmback_mm']
        c.set_editor_property('filmback',filmback)
        c.set_editor_property('current_focal_length',p['focal_length_mm'])
        focus=c.get_editor_property('focus_settings')
        focus.focus_method=unreal.CameraFocusMethod.DISABLE
        c.set_editor_property('focus_settings',focus)
        pos=a.get_actor_location();actualrot=a.get_actor_rotation()
        assert all(abs(v-e*100)<1e-3 for v,e in zip([pos.x,pos.y,pos.z],p['position_m']))
        assert all(abs((v-e+180)%360-180)<1e-3 for v,e in zip([actualrot.pitch,actualrot.yaw,actualrot.roll],p['rotation_deg']))
        actualfocal=float(c.get_editor_property('current_focal_length'))
        assert abs(actualfocal-p['focal_length_mm'])<1e-5
        package=a.get_package().get_path_name()
        packages.add(package)
        readback.append({'camera_id':cid,'actor':a.get_actor_label(),'position_m':[pos.x/100,pos.y/100,pos.z/100],
            'rotation_deg':[actualrot.pitch,actualrot.yaw,actualrot.roll],'focal_length_mm':actualfocal,
            'horizontal_fov_deg':float(c.get_editor_property('current_horizontal_fov')),
            'filmback_mm':[filmback.sensor_width,filmback.sensor_height],'package':package})
    dirty_now=dirty()
    unexpected=[p.get_path_name() for p in dirty_now if p.get_path_name() not in packages]
    assert not unexpected,unexpected
    assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty_now,True)
    assert not dirty(),[p.get_path_name() for p in dirty()]
    report={'status':'nine_cameras_configured_saved_wait_visual_review','level':level,'readback':readback,'dirty_after':[]}
    (evidence/'configuration_complete.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
