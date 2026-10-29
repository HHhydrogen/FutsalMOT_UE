"""读取用户手调的九机位；只进一步调整两端局部机位并同步生成目录。"""
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/src'))
from grf_ue_bridge.camera_rig import validate_rig,build_camera_plan


def read_camera(cid,actor):
    c=actor.get_cine_camera_component()
    pos=actor.get_actor_location();rot=actor.get_actor_rotation();f=c.get_editor_property('filmback')
    return {'camera_id':cid,'actor':actor.get_actor_label(),
        'position_m':[pos.x/100,pos.y/100,pos.z/100],
        'rotation_deg':[rot.pitch,rot.yaw,rot.roll],
        'focal_length_mm':float(c.get_editor_property('current_focal_length')),
        'filmback_mm':[f.sensor_width,f.sensor_height],
        'horizontal_fov_deg':float(c.get_editor_property('current_horizontal_fov')),
        'package':actor.get_package().get_path_name()}


def main():
    import unreal
    out=ROOT/'Saved/CameraRigV2/manual_sync_a01'
    assert not out.exists(),'本次同步已有收据，不覆盖用户调整快照'
    assert unreal.EditorLevelLibrary.get_editor_world().get_path_name().split('.')[0]=='/Game/FutsalMOT/Maps/L_FutsalCourt'
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    config=ROOT/'python/configs/camera_rig_v2.json'
    prior=config.read_bytes();rig=json.loads(prior)
    actors=unreal.EditorLevelLibrary.get_all_level_actors()
    found={}
    for cid,p in rig['profiles'].items():
        matches=[a for a in actors if a.get_actor_label()==p['actor']]
        assert len(matches)==1 and matches[0].get_class().get_name()=='CineCameraActor',cid
        found[cid]=matches[0]
    before=[read_camera(cid,a) for cid,a in found.items()]
    allowed={row['package'] for row in before}
    dirty=lambda:list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert all(p.get_path_name() in allowed for p in dirty()),'存在相机之外未保存改动'
    assert all(all(abs(a-b)<1e-5 for a,b in zip(row['filmback_mm'],rig['filmback_mm'])) for row in before)
    out.mkdir(parents=True)
    (out/'before.json').write_text(json.dumps({'source':'用户手调后的真实Editor状态','cameras':before},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'previous_catalog.json').write_bytes(prior)
    if dirty():
        assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty(),True)
    for cid in ('P03','P04'):
        a=found[cid];pos=a.get_actor_location();rot=a.get_actor_rotation()
        yaw=math.radians(rot.yaw)
        pos.x-=200*math.cos(yaw);pos.y-=200*math.sin(yaw)
        rot.pitch=-18.0
        a.modify();a.set_actor_location_and_rotation(pos,rot,False,False)
        c=a.get_cine_camera_component();c.modify();c.set_editor_property('current_focal_length',22.0)
    after=[read_camera(cid,a) for cid,a in found.items()]
    for row in after:
        if row['camera_id'] in ('P03','P04'):
            assert abs(row['focal_length_mm']-22.0)<1e-5
            assert abs(row['rotation_deg'][0]+18.0)<1e-5
    for row in after:
        cid=row['camera_id'];p=rig['profiles'][cid]
        p['position_m']=[round(v,9) for v in row['position_m']]
        p['rotation_deg']=[0.0 if abs(v)<1e-8 else round(v,9) for v in row['rotation_deg']]
        p['focal_length_mm']=row['focal_length_mm']
        pitch,yaw=map(math.radians,p['rotation_deg'][:2])
        distance=(0.9-p['position_m'][2])/math.sin(pitch)
        p['target_m']=[round(p['position_m'][0]+distance*math.cos(pitch)*math.cos(yaw),9),
                       round(p['position_m'][1]+distance*math.cos(pitch)*math.sin(yaw),9),0.9]
    validate_rig(rig)
    for old,new in zip(before,after):
        if old['camera_id'] not in ('P03','P04'):
            assert old==new,'不得改写用户手调的其他七机位'
    dirty_now=dirty()
    assert all(p.get_path_name() in allowed for p in dirty_now)
    if dirty_now:assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty_now,True)
    assert not dirty()
    config.write_text(json.dumps(rig,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'status':'manual_cameras_readback_synced_and_saved','before':before,'after':after,
        'extra_adjustments':{'ids':['P03','P04'],'retreat_m':2.0,'pitch_deg':-18.0,'focal_length_mm':22.0},
        'catalog_sha256':build_camera_plan(1048,rig)['catalog_sha256'],'dirty_after':[]}
    (out/'complete.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'readback':after},ensure_ascii=False))


if __name__=='__main__':
    main()
