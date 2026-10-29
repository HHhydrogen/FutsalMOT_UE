"""单seed的输入协议与精简导出；随机选择复用seeded_episode。"""
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

# 共用已验纯数学/实例统计工具；此目录加入路径不导入unreal。
_UE_DIR=Path(__file__).resolve().parents[2]/'ue'
if str(_UE_DIR) not in sys.path:
    sys.path.insert(0,str(_UE_DIR))

ENTITY_IDS = tuple(s+str(i) for s in 'LR' for i in range(5))
POINT_NAMES = ('left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist',
               'left_hip','right_hip','left_knee','right_knee','left_ankle','right_ankle')
SCHEMA_NAMES = ('seed_manifest.schema.json','frame_annotation.schema.json','trajectory_record.schema.json',
                'camera_state.schema.json','camera_metadata.schema.json','pose_schema_futsal_body12_v1.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def dump(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def prepare_source(project, attempt, request_path):
    """仅采一次完整比赛；源小文件留Saved，媒体另在G。"""
    from .camera_rig import build_camera_plan
    from .config.models import DatasetTaskConfig
    from .config.resolver import resolve_task
    from .workflows.task_export import run_export
    project=Path(project).resolve();request=read(request_path)
    if not attempt or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in attempt):
        raise ValueError('attempt只允许小写字母/数字/下划线')
    local=project/'Saved/SingleSeed'/attempt
    if local.exists():
        raise FileExistsError(local)
    local.mkdir(parents=True)
    dump(local/'request.json',request)
    rig=read(project/request['camera_rig'])
    if request['resolution'] != [3840,2160] or rig['resolution'] != request['resolution']:
        raise ValueError('新单seed生成及相机必须统一3840x2160')
    camera_plan=build_camera_plan(request['root_seed'],rig)
    task=read(project/'python/configs/player_appearance_15kits_smoke_10frames_1cam.json')
    media='G:/FutsalMOT_Dataset/test/'+attempt+'/raw'
    task.update(task_id=attempt,episode_name=attempt,dataset_root=media,ue_project_root=str(project))
    task['export'].update(seed=request['root_seed'],scenario=request['scenario'],num_steps=request['source_step_limit'],
        stop_on_done=True,game_duration=request['game_duration'],target_fps=request['fps'],playback_fps=request['fps'],
        left_team_difficulty=request['team_difficulty'][0],right_team_difficulty=request['team_difficulty'][1])
    ue=task['ue'];ue['appearance']=read(project/request['appearance_catalog'])
    ue['uv_numbering']=read(project/request['number_profile'])
    ue['seeded_episode']={'enabled':True,'camera_rig':rig}
    ue['environment']={'mode':'seeded','policy':'futsalmot_environment_v1_5',
        'catalog_id':request.get('weather_catalog_id','futsalmot_indoor_environment_v1_5'),'preset':'auto'}
    ue['sequence_package_path']='/Game/FutsalMOT/Development/SingleSeed/'+attempt
    ue['replace_existing']=False
    ue['sequences']=[{'name':e['name'],'camera_actor':e['camera_actor']} for e in camera_plan['entries']]
    ann=ue['annotation_export'];ann.update(cameras=[e['camera_actor'] for e in camera_plan['entries']],export_mot=False)
    ann.update(image_width=3840,image_height=2160)
    ann['render_rgb'].update(output_resolution_x=3840,output_resolution_y=2160)
    ann['render_rgb']['cv_gt']['anti_aliasing']='none'
    ann['body12_capture']={'enabled':True,'output_dir':str(local/'native'),'frame_count':0,
        'actor_mapping':str(project/'python/ue/actor_mapping.example.json')}
    task['audit'].update(expected_cameras=len(camera_plan['entries']),expected_frames_per_camera=request['source_step_limit'])
    task['postprocess'].update(formats=['json'],include_ball=False)
    DatasetTaskConfig(**task)
    task_path=local/'task.json';dump(task_path,task)
    resolved=resolve_task(task_path,dataset_root=media,ue_project_root=str(project))
    resolved.trajectory_output=str(local/'source')
    run_export(resolved)
    meta=read(Path(resolved.trajectory_output)/'meta.json')
    count=meta['timing']['num_steps']
    resolved.export_profile['num_steps']=count
    resolved.audit['expected_frames_per_camera']=count
    resolved.ue_profile['annotation_export']['body12_capture']['frame_count']=count
    dump(local/'resolved.json',resolved.model_dump(by_alias=True))
    dump(local/'source_complete.json',{'status':'full_episode_collected','frames':count,
        'termination':read(local/'source/termination.json'),'frames_sha256':sha(local/'source/frames.jsonl'),
        'selected_camera_ids':camera_plan['selected_ids']})
    return local


def freeze_inputs(project, local):
    """绑定实际源码快照/共享schema，另建十帧接线任务，不改完整源。"""
    import shutil
    from .seeded_episode import prepare_episode_recipe
    project=Path(project).resolve();local=Path(local).resolve()
    request=read(local/'request.json');resolved=read(local/'resolved.json')
    if (local/'protocol.json').exists():
        raise FileExistsError('协议已冻结')
    bundle=local/'code';bundle.mkdir()
    sources=[]
    for folder in ('python/src/grf_ue_bridge','python/ue','Source/FutsalMOT','tools/dataset'):
        for path in sorted((project/folder).rglob('*')):
            if path.suffix not in ('.py','.cpp','.h','.cs','.ps1') or '__pycache__' in path.parts:
                continue
            relative=path.relative_to(project);destination=bundle/relative
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
            sources.append({'path':relative.as_posix(),'sha256':sha(path)})
    dump(local/'code_bundle.json',{'files':sources,'sha256':canonical_sha(sources)})
    schema_root=project/'python/schemas/single_seed_v1'
    recipe=read(local/'source/provenance/seeded_episode.json')
    protocol={'schema':'futsalmot_single_seed_protocol_v1','request':request,
        'attempt_id':local.name,'seed_id':'seed_%08x'%request['root_seed'],
        'frame_count':read(local/'source/meta.json')['timing']['num_steps'],
        'source_frames_sha256':sha(local/'source/frames.jsonl'),'termination_sha256':sha(local/'source/termination.json'),
        'recipe':recipe,'code_bundle_sha256':canonical_sha(sources),
        'module_dll_sha256':sha(project/'Binaries/Win64/UnrealEditor-FutsalMOT.dll'),
        'schemas':{name:sha(schema_root/name) for name in SCHEMA_NAMES},
        'schema_split_is_diagnostic_only':True,'formal_split_membership_assigned':False,
        'render_samples':{'temporal':1,'spatial':1,'aa':'none','motion_blur':False,'engine_warmup_frames':8}}
    dump(local/'protocol.json',protocol)
    short=local/'short';short.mkdir()
    count=min(request['short_sample_frames'],protocol['frame_count'])
    meta=read(local/'source/meta.json');meta['episode_id']=local.name+'_short';meta['timing']['num_steps']=count
    dump(short/'meta.json',meta)
    lines=(local/'source/frames.jsonl').read_text(encoding='utf-8').splitlines()[:count]
    (short/'frames.jsonl').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    short_task=json.loads(json.dumps(resolved))
    short_task.update(task_id=meta['episode_id'],episode_name=meta['episode_id'],trajectory_output=str(short),
        dataset_root='G:/FutsalMOT_Dataset/test/'+local.name+'_short/raw')
    short_task['export_profile']['num_steps']=count
    short_task['ue_profile']['sequence_package_path']+='_short'
    short_task['ue_profile']['annotation_export']['body12_capture'].update(output_dir=str(short/'native'),frame_count=count)
    short_task['audit']['expected_frames_per_camera']=count
    prepare_episode_recipe(short,short_task['ue_profile'])
    dump(short/'resolved.json',short_task)
    return protocol


def projection(native):
    """真实MRQ相机旋转，保持UE左手基向量及像素中心约定。"""
    p,y,r=[math.radians(x) for x in native['camera_rotation_deg']]
    sp,cp,sy,cy,sr,cr=math.sin(p),math.cos(p),math.sin(y),math.cos(y),math.sin(r),math.cos(r)
    forward=(cp*cy,cp*sy,sp)
    right=(sr*sp*cy-cr*sy,sr*sp*sy+cr*cy,-sr*cp)
    up=(-(cr*sp*cy+sr*sy),sr*cy-cr*sp*sy,cr*cp)
    width,height=native['width'],native['height']
    focal=width/(2*math.tan(math.radians(native['horizontal_fov_deg'])/2))
    center=native['camera_position_m']
    def project(point):
        delta=[a-b for a,b in zip(point,center)]
        depth=sum(a*b for a,b in zip(delta,forward))
        if depth<=1e-6:
            return None
        return [(width-1)/2+focal*sum(a*b for a,b in zip(delta,right))/depth,
                (height-1)/2-focal*sum(a*b for a,b in zip(delta,up))/depth]
    return project


def bounds_state(player,native):
    project=projection(native);c=player['bounds_center_m'];e=player['bounds_extent_m']
    points=[project([c[i]+sign[i]*e[i] for i in range(3)]) for sign in itertools.product((-1,1),repeat=3)]
    valid=[p for p in points if p is not None]
    if not valid:
        return True,False
    xs,ys=zip(*valid);w,h=native['width'],native['height']
    outside=max(xs)<0 or min(xs)>=w or max(ys)<0 or min(ys)>=h
    partial=not outside and (len(valid)!=8 or min(xs)<0 or max(xs)>=w or min(ys)<0 or max(ys)>=h)
    return outside,partial


def tight(mask,mask_id):
    import numpy as np
    yy,xx=np.nonzero(mask==mask_id)
    return (None,0) if len(xx)==0 else ([int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)],int(len(xx)))


def identities(meta,number_plan):
    by_entity={e['entity_id']:e for e in number_plan['entities']}
    definitions={e['id']:e for e in meta['entities']}
    return [{'entity_id':entity,'track_id':i+1,'team':entity[0],
        'role':'goalkeeper' if definitions[entity]['is_goalkeeper'] else 'player',
        'jersey_number':by_entity[entity]['jersey_number'],'instance_mask_id':i+1,'number_mask_id':32+i}
        for i,entity in enumerate(ENTITY_IDS)]


def frame_annotation(protocol,camera_id,index,native,instance,number,entities):
    import numpy as np
    from instance_mask import compute_instance_stats
    request=protocol['request'];project=projection(native)
    people={o['entity_id']:o for o in native['players']}
    instance_stats=compute_instance_stats(instance,10);number_stats=compute_instance_stats(number,41)
    selected=number>0
    if np.count_nonzero(instance[selected] != number[selected]-31)>request['number_instance_pixel_mismatch_max']:
        raise ValueError('号码像素不属于对应人物')
    objects=[]
    for entity in entities:
        person=people[entity['entity_id']]
        stat=instance_stats.get(entity['instance_mask_id']);nstat=number_stats.get(entity['number_mask_id'])
        box,count=(list(stat.bbox_xyxy),stat.pixel_count) if stat else (None,0)
        number_box,number_count=(list(nstat.bbox_xyxy),nstat.pixel_count) if nstat else (None,0)
        outside,truncated=bounds_state(person,native)
        direction=[a-b for a,b in zip(native['camera_position_m'],person['bounds_center_m'])]
        length=math.sqrt(sum(x*x for x in direction))
        dot=sum(a*b for a,b in zip(person['back_normal_world'],direction))/max(length,1e-9)
        view='back' if dot>=.5 else 'front' if dot<=-.5 else 'side'
        points=[]
        if len(person['world_m'])!=12:
            raise ValueError('body12点数不符')
        for name,world in zip(POINT_NAMES,person['world_m']):
            pixel=project(world)
            points.append({'name':name,'x_px':pixel[0] if pixel else None,'y_px':pixel[1] if pixel else None,'visibility':0})
        objects.append({**entity,'class':'player','bbox_xyxy':box,'bbox_source':'instance_mask' if count else 'not_visible',
            'visible_pixel_count':count,'truncated':truncated,'visibility':'visible' if count else 'out_of_frame' if outside else 'unknown',
            'jersey_number_visible':number_count>0,'jersey_number_readable':False,'jersey_number_view':view,
            'jersey_number_bbox_xyxy':number_box,'keypoints':points})
    return {'schema':'futsalmot_frame_annotation','schema_version':'1.0.0','dataset_id':request['dataset_id'],
        'dataset_version':request['dataset_version'],'seed_id':protocol['seed_id'],'camera_id':camera_id,
        'frame_index':index,'source_step':index-1,'time_seconds':(index-1)/request['fps'],'pose_schema_id':'futsal_body12_v1',
        'camera_state':{'schema':'futsalmot_camera_state','schema_version':'1.0.0','camera_id':camera_id,'frame_index':index,
            'width':native['width'],'height':native['height'],'position_m':native['camera_position_m'],
            'rotation_deg':native['camera_rotation_deg'],'focal_length_mm':native['focal_length_mm'],
            'horizontal_fov_deg':native['horizontal_fov_deg']},'objects':objects}
