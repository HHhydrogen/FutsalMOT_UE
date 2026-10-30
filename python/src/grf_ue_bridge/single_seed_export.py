"""消费实际MRQ/native，导出并校验一个精简seed；不生成全数据集manifest。"""
import itertools
import json
import math
import os
from pathlib import Path
import shutil

from .single_seed import (ENTITY_IDS,POINT_NAMES,SCHEMA_NAMES,read,rows,dump,sha,canonical_sha,
                         identities,frame_annotation,projection,bounds_state)
from .storage_policy import (DATASET_ROOT,physical_child,record_test_render,
                             test_render_activity,require_single_seed_capacity)


def context(project,local,short):
    project=Path(project).resolve();local=Path(local).resolve()
    protocol=read(local/'protocol.json')
    unit=local/'short' if short else local
    task=read(unit/'resolved.json')
    source=Path(task['trajectory_output'])
    raw=Path(task['dataset_root'])/task['episode_name']
    media=raw.parent.parent
    destination=media/'export'/protocol['seed_id']
    physical_child(raw,DATASET_ROOT);physical_child(destination,DATASET_ROOT)
    expected=read(source/'meta.json')['timing']['num_steps']
    return project,local,unit,protocol,task,source,raw,destination,expected


def schema_validators(project,protocol):
    import jsonschema
    from referencing import Registry,Resource
    root=project/'python/schemas/single_seed_v1'
    validators={}
    store={read(root/name)['$id']:read(root/name) for name in SCHEMA_NAMES if not name.startswith('pose_schema')}
    registry=Registry().with_resources((uri,Resource.from_contents(schema)) for uri,schema in store.items())
    for name in SCHEMA_NAMES:
        if sha(root/name)!=protocol['schemas'][name]:
            raise ValueError('共享schema改变: '+name)
        schema=read(root/name)
        if name.startswith('pose_schema'):
            continue
        jsonschema.Draft202012Validator.check_schema(schema)
        validators[name]=jsonschema.Draft202012Validator(schema,registry=registry)
    return validators


def assert_bindings(project,local,protocol):
    bundle=read(local/'code_bundle.json')
    if canonical_sha(bundle['files'])!=protocol['code_bundle_sha256']:
        raise ValueError('源码bundle清单变化')
    for item in bundle['files']:
        if sha(local/'code'/item['path'])!=item['sha256'] or sha(project/item['path'])!=item['sha256']:
            raise ValueError('源码与本轮bundle不同: '+item['path'])
    if sha(local/'source/frames.jsonl')!=protocol['source_frames_sha256']:
        raise ValueError('完整共享轨迹变化')
    if sha(project/'Binaries/Win64/UnrealEditor-FutsalMOT.dll')!=protocol['module_dll_sha256']:
        raise ValueError('实际采样模块变化')


def capture_receipt(project,local,unit,protocol,task,source,raw,count):
    if (unit/'partitions/manifest.json').exists():
        manifest=read(unit/'partitions/manifest.json')
        read(unit/'partitions/complete.json')
        if manifest['protocol_sha256']!=sha(local/'protocol.json'):
            raise ValueError('分任务协议不匹配')
        receipts=[]
        for row in manifest['parts']:
            part=Path(row['directory']);ptask=read(part/'resolved.json')
            if sha(part/'resolved.json')!=row['resolved_sha256']:
                raise ValueError('分任务配置变化')
            pp=json.loads(json.dumps(protocol))
            pp['recipe']['components']['cameras']['entries']=[e for e in protocol['recipe']['components']['cameras']['entries'] if e['camera_id']==row['camera_id']]
            receipts.append(capture_receipt(project,local,part,pp,ptask,Path(ptask['trajectory_output']),part,count))
        if [r['camera_ids'][0] for r in receipts]!=protocol['recipe']['components']['cameras']['selected_ids']:
            raise ValueError('分任务机位集合不完整')
        result={'status':'capture_restored','schema':'futsalmot_single_seed_partition_capture_v1','partitions':receipts,
                'protocol_sha256':sha(local/'protocol.json'),'code_bundle_sha256':protocol['code_bundle_sha256']}
        dump(unit/'capture_receipt.json',result)
        return result
    summary=read(raw/'render_summary.json')
    if summary['status']!='success' or any(j['status']!='success' for j in summary['jobs']):
        raise ValueError('MRQ尚未完整成功')
    cameras=protocol['recipe']['components']['cameras']['entries']
    native=[]
    for entry in cameras:
        path=Path(task['ue_profile']['annotation_export']['body12_capture']['output_dir'])/(entry['camera_actor']+'.jsonl')
        complete=read(str(path)+'.complete.json')
        if complete.get('success') is not True or complete['written_frames']!=count or complete['restore_errors']:
            raise ValueError('native采样/恢复未成功: '+entry['camera_id']+str(complete))
        native.append({'camera_id':entry['camera_id'],'path':str(path),'sha256':sha(path),'completion':complete})
    floor=read(source/'provenance/floor_application.json')
    if floor.get('state')!='restored':
        raise ValueError('草地尚未恢复')
    # appearance/environment由run_task的共同完成回调写入可移植收据。
    applications={}
    for name in ('appearance_application.json','environment_application.json'):
        path=source/'provenance'/name
        if not path.exists():
            raise ValueError('缺恢复收据: '+name)
        report=read(path)
        if report.get('state')!='restored':
            raise ValueError('事务尚未恢复: '+name+str(report.get('state')))
        applications[name]={'sha256':sha(path),'state':report['state']}
    receipt={'schema':'futsalmot_single_seed_capture_receipt_v1','status':'capture_restored',
        'attempt_id':task['task_id'],'frames':count,'camera_ids':[c['camera_id'] for c in cameras],
        'native':native,'render_summary_sha256':sha(raw/'render_summary.json'),
        'applications':applications,'floor_application_sha256':sha(source/'provenance/floor_application.json'),
        'protocol_sha256':sha(local/'protocol.json'),'code_bundle_sha256':protocol['code_bundle_sha256']}
    dump(unit/'capture_receipt.json',receipt)
    return receipt


def link(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    try:
        os.link(source,destination)
    except OSError:
        shutil.copyfile(source,destination)


def export_seed(project,local,short=False):
    values=context(project,local,short)
    project,local,unit,protocol,task,source,raw,destination,count=values
    if destination.exists():
        raise FileExistsError('不覆盖seed导出: '+str(destination))
    assert_bindings(project,local,protocol)
    with test_render_activity(raw,'exporting',storage=protocol['request']['storage']):
        dump(unit/'export_storage_admission.json',require_single_seed_capacity(protocol,task))
        return _export_seed(values,short)


def _export_seed(values,short):
    import numpy as np
    from PIL import Image
    from .cryptomatte import convert_render_mask_dir
    from .number_mask_exr import export_number_masks
    project,local,unit,protocol,task,source,raw,destination,count=values
    validators=schema_validators(project,protocol)
    receipt=capture_receipt(project,local,unit,protocol,task,source,raw,count)
    meta=read(source/'meta.json');recipe=read(source/'provenance/seeded_episode.json')
    entities=identities(meta,recipe['components']['numbers'])
    cameras=protocol['recipe']['components']['cameras']['entries']
    camera_dirs=[raw/e['camera_actor'] for e in cameras]
    # 沿用已验串行EXR消费方法；两个消费者都完成后才退休EXR。
    number_report=export_number_masks(camera_dirs)
    mapping=read(project/'python/ue/actor_mapping.example.json')
    for entry,camera in zip(cameras,camera_dirs):
        require_single_seed_capacity(protocol,task,reserve_peak=False)
        status,frames=convert_render_mask_dir(camera/'render_mask',mapping,camera/'mask',count,.1,10,workers=2,chunk_size=2)
        if status!='success' or len(frames)!=count:
            raise ValueError('实例mask帧数不完整: '+entry['camera_id'])
    destination.mkdir(parents=True)
    with (destination/'trajectory.jsonl').open('w',encoding='utf-8') as stream:
        for index,frame in enumerate(rows(source/'frames.jsonl')):
            if frame['step']!=index or not math.isclose(frame['time_seconds'],index/10,abs_tol=1e-8):
                raise ValueError('轨迹step/time不连续')
            players={p['id']:p for p in frame['players']}
            trajectory={'schema':'futsalmot_trajectory_record','schema_version':'1.0.0','seed_id':protocol['seed_id'],
                'step':index,'time_seconds':frame['time_seconds'],'players':[{
                    'entity_id':e['entity_id'],'team':e['team'],'role':e['role'],
                    'position_m':players[e['entity_id']]['position_m'],
                    'velocity_mps':[*players[e['entity_id']]['velocity_mps'],0.0],
                    'active':players[e['entity_id']]['active']} for e in entities]}
            validators['trajectory_record.schema.json'].validate(trajectory)
            stream.write(json.dumps(trajectory,ensure_ascii=False,allow_nan=False)+'\n')
    total_visible_numbers=0
    for entry,camera in zip(cameras,camera_dirs):
        require_single_seed_capacity(protocol,task,reserve_peak=False)
        camera_id=entry['camera_id'];output=destination/camera_id
        output.mkdir();(output/'img1').mkdir();(output/'mask').mkdir();(output/'number_mask').mkdir()
        native_path=Path(task['ue_profile']['annotation_export']['body12_capture']['output_dir'])/(entry['camera_actor']+'.jsonl')
        actual_count=0
        with (output/'annotations.jsonl').open('w',encoding='utf-8') as stream:
            for index,native in enumerate(rows(native_path),1):
                if index%64==1:
                    require_single_seed_capacity(protocol,task,reserve_peak=False,inspect_media=False)
                if native['output_frame']!=index-1 or native['source_frame']!=index-1 or len(native['players'])!=10:
                    raise ValueError('native/source/RGB帧映射不符')
                name='%06d.png'%index
                with Image.open(camera/'img1'/name) as image:
                    if image.size!=tuple(protocol['request']['resolution']):
                        raise ValueError('实际RGB尺寸不符')
                    if image.mode=='RGB':
                        link(camera/'img1'/name,output/'img1'/name)
                    else:
                        image.convert('RGB').save(output/'img1'/name,compress_level=1)
                with Image.open(camera/'mask'/name) as image:
                    instance=np.array(image,dtype=np.uint8)
                instance[instance==11]=0
                Image.fromarray(instance,'L').save(output/'mask'/name,compress_level=1)
                with Image.open(camera/'number_mask'/name) as image:
                    number=np.array(image,dtype=np.uint8)
                link(camera/'number_mask'/name,output/'number_mask'/name)
                annotation=frame_annotation(protocol,camera_id,index,native,instance,number,entities)
                validators['frame_annotation.schema.json'].validate(annotation)
                stream.write(json.dumps(annotation,ensure_ascii=False,allow_nan=False)+'\n')
                total_visible_numbers+=sum(o['jersey_number_visible'] for o in annotation['objects'])
                if index==1:
                    w,h=native['width'],native['height'];fov=native['horizontal_fov_deg']
                    focal=w/(2*math.tan(math.radians(fov)/2))
                    metadata={'schema':'futsalmot_camera_metadata','schema_version':'1.0.0','camera_id':camera_id,
                        'ue_actor':entry['camera_actor'],'sequence':task['ue_profile']['sequence_package_path']+'/'+entry['name'],
                        'width':w,'height':h,'intrinsics':{'fx_px':focal,'fy_px':focal,'cx_px':(w-1)/2,'cy_px':(h-1)/2,
                            'focal_length_mm':native['focal_length_mm'],'horizontal_fov_deg':fov},'profile_sha256':canonical_sha(entry['profile'])}
                    validators['camera_metadata.schema.json'].validate(metadata);dump(output/'camera.json',metadata)
                actual_count=index
        if actual_count!=count:
            raise ValueError('native不完整')
    manifest={'schema':'futsalmot_seed_manifest','schema_version':'1.0.0','dataset_id':protocol['request']['dataset_id'],
        'dataset_version':protocol['request']['dataset_version'],'seed_id':protocol['seed_id'],
        'split':protocol['request']['schema_split_value'],'root_seed':'%08x'%protocol['request']['root_seed'],
        'trajectory_uid':sha(source/'frames.jsonl'),'frame_count':count,'fps':10,'camera_ids':[e['camera_id'] for e in cameras],
        'entities':entities,'generation':{'protocol_sha256':sha(local/'protocol.json'),
            'code_bundle_sha256':protocol['code_bundle_sha256'],'attempt_id':task['task_id'],'receipt_sha256':sha(unit/'capture_receipt.json')}}
    validators['seed_manifest.schema.json'].validate(manifest);dump(destination/'seed_manifest.json',manifest)
    dump(unit/'export_complete.json',{'status':'exported_pending_validation','seed_directory':str(destination),
        'camera_count':len(cameras),'frames_per_camera':count,'rgb':count*len(cameras),
        'instance_masks':count*len(cameras),'number_masks':number_report['frames'],
        'visible_number_records':total_visible_numbers,'diagnostic_only':True})
    return verify_seed(project,local,short=short)


def verify_seed(project,local,short=False):
    values=context(project,local,short)
    project,local,unit,protocol,task,source,raw,destination,count=values
    if (unit/'verification_complete.json').exists():
        raise FileExistsError('本seed已完成校验，不重复扫描')
    assert_bindings(project,local,protocol)
    with test_render_activity(raw,'verifying',storage=protocol['request']['storage']):
        require_single_seed_capacity(protocol,task,reserve_peak=False)
        return _verify_seed(values,short)


def _verify_seed(values,short):
    """对本轮seed做一次完整结构和mask核对；不重哈RGB或伪造物理遮挡。"""
    import numpy as np
    from PIL import Image
    from instance_mask import compute_instance_stats
    project,local,unit,protocol,task,source,raw,destination,count=values
    validators=schema_validators(project,protocol)
    manifest=read(destination/'seed_manifest.json');validators['seed_manifest.schema.json'].validate(manifest)
    entities=identities(read(source/'meta.json'),read(source/'provenance/number_uv.json'))
    if manifest['entities']!=entities or manifest['frame_count']!=count or manifest['generation']['receipt_sha256']!=sha(unit/'capture_receipt.json'):
        raise ValueError('seed manifest与本次身份/采集不符')
    expected={'seed_manifest.json','trajectory.jsonl'}
    camera_entries=protocol['recipe']['components']['cameras']['entries']
    ids=[e['camera_id'] for e in camera_entries]
    if manifest['camera_ids']!=ids:
        raise ValueError('seed机位集合不符')
    for camera_id in ids:
        expected.update(camera_id+'/'+name for name in ('camera.json','annotations.jsonl'))
        expected.update('%s/%s/%06d.png'%(camera_id,kind,i) for kind in ('img1','mask','number_mask') for i in range(1,count+1))
    actual={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    expected_dirs={str(Path(p).parent).replace('\\','/') for p in expected if '/' in p}
    expected_dirs.update(ids)
    actual_dirs={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_dir()}
    if actual!=expected or actual_dirs!=expected_dirs:
        raise ValueError('文件/目录白名单不符: '+str({'missing':sorted(expected-actual)[:8],'extra':sorted(actual-expected)[:8]}))
    source_rows=rows(source/'frames.jsonl');n=0
    for n,(frame,original) in enumerate(itertools.zip_longest(rows(destination/'trajectory.jsonl'),source_rows),1):
        if frame is None or original is None:
            raise ValueError('轨迹条数不符')
        validators['trajectory_record.schema.json'].validate(frame)
        if frame['step']!=n-1 or frame['time_seconds']!=original['time_seconds'] or [p['entity_id'] for p in frame['players']]!=list(ENTITY_IDS):
            raise ValueError('轨迹时间/实体不符')
        for player,origin in zip(frame['players'],original['players']):
            if player['position_m']!=origin['position_m'] or player['velocity_mps']!=[*origin['velocity_mps'],0.0]:
                raise ValueError('米制轨迹变化')
    if n!=count:
        raise ValueError('轨迹帧数不符')
    visible_numbers=0;truncated_count=0;out_count=0
    for entry in camera_entries:
        require_single_seed_capacity(protocol,task,reserve_peak=False)
        camera_id=entry['camera_id'];camera=destination/camera_id
        metadata=read(camera/'camera.json');validators['camera_metadata.schema.json'].validate(metadata)
        if metadata['profile_sha256']!=canonical_sha(entry['profile']):
            raise ValueError('相机profile绑定不符')
        native_path=Path(task['ue_profile']['annotation_export']['body12_capture']['output_dir'])/(entry['camera_actor']+'.jsonl')
        n=0
        for n,(frame,native) in enumerate(itertools.zip_longest(rows(camera/'annotations.jsonl'),rows(native_path)),1):
            if frame is None or native is None:
                raise ValueError('标注/native条数不符')
            validators['frame_annotation.schema.json'].validate(frame)
            if frame['frame_index']!=n or frame['source_step']!=n-1 or frame['time_seconds']!=(n-1)/10 or frame['camera_id']!=camera_id:
                raise ValueError('标注帧/时间/机位不符')
            state=frame['camera_state'];profile=entry['profile'];w,h=protocol['request']['resolution']
            for field,key in (('position_m','camera_position_m'),('rotation_deg','camera_rotation_deg')):
                if state[field]!=native[key] or any(abs(a-b)>1e-3 for a,b in zip(state[field],profile[field])):
                    raise ValueError('实际相机状态与已确认配置不符')
            if abs(state['focal_length_mm']-profile['lens']['focal_length_mm'])>1e-3:
                raise ValueError('相机焦距不符')
            name='%06d.png'%n
            with Image.open(camera/'img1'/name) as image:
                if image.mode!='RGB' or image.size!=(w,h):
                    raise ValueError('RGB模式/尺寸不符')
            arrays=[]
            for kind,allowed in (('mask',set(range(11))),('number_mask',{0,*range(32,42)})):
                with Image.open(camera/kind/name) as image:
                    if image.mode!='L' or image.size!=(w,h):
                        raise ValueError('mask模式/尺寸不符')
                    array=np.array(image)
                if array.dtype!=np.uint8 or not set(np.unique(array).tolist())<=allowed:
                    raise ValueError('mask值域/类型不符')
                arrays.append(array)
            mask,number=arrays;stats=compute_instance_stats(mask,10);number_stats=compute_instance_stats(number,41)
            selected=number>0
            if np.any(mask[selected]!=number[selected]-31):
                raise ValueError('号码归属不符')
            people={p['entity_id']:p for p in native['players']};project_point=projection(native)
            if [o['entity_id'] for o in frame['objects']]!=list(ENTITY_IDS):
                raise ValueError('每帧十人/顺序不符')
            for entity,obj in zip(entities,frame['objects']):
                if any(obj[k]!=v for k,v in entity.items()):
                    raise ValueError('身份/号码映射漂移')
                stat=stats.get(entity['instance_mask_id']);nstat=number_stats.get(entity['number_mask_id'])
                bbox=list(stat.bbox_xyxy) if stat else None;nbox=list(nstat.bbox_xyxy) if nstat else None
                if obj['bbox_xyxy']!=bbox or obj['visible_pixel_count']!=(stat.pixel_count if stat else 0) or obj['jersey_number_bbox_xyxy']!=nbox or obj['jersey_number_visible']!=(nstat is not None):
                    raise ValueError('bbox/可见像素与mask不符')
                person=people[entity['entity_id']];outside,truncated=bounds_state(person,native)
                if obj['truncated']!=truncated or obj['visibility']!=('visible' if stat else 'out_of_frame' if outside else 'unknown'):
                    raise ValueError('截断/人物可见性不符')
                if [p['name'] for p in obj['keypoints']]!=list(POINT_NAMES) or obj['jersey_number_readable'] is not False:
                    raise ValueError('点顺序/可读性规则不符')
                for point,world in zip(obj['keypoints'],person['world_m']):
                    projected=project_point(world)
                    expected_xy=projected if projected else [None,None]
                    if [point['x_px'],point['y_px']]!=expected_xy or point['visibility']!=0:
                        raise ValueError('Pose/native对应不符')
                visible_numbers+=obj['jersey_number_visible'];truncated_count+=obj['truncated'];out_count+=obj['visibility']=='out_of_frame'
        if n!=count:
            raise ValueError('相机帧数不符')
    total_bytes=sum(p.stat().st_size for p in destination.rglob('*') if p.is_file())
    if total_bytes>protocol['request']['storage']['stage_limit_bytes']:
        raise ValueError('导出超过容量上限')
    report={'status':'single_seed_check_passed','diagnostic_only':True,'short_sample':short,
        'seed_directory':str(destination),'camera_ids':ids,'frames_per_camera':count,
        'rgb_frames':count*len(ids),'instance_masks':count*len(ids),'number_masks':count*len(ids),
        'person_records':count*len(ids)*10,'visible_number_records':visible_numbers,'truncated_records':truncated_count,
        'out_of_frame_records':out_count,'pose_points':count*len(ids)*120,'pose_visibility':'unknown_0',
        'files':len(actual),'bytes':total_bytes,'protocol_sha256':sha(local/'protocol.json'),
        'seed_manifest_sha256':sha(destination/'seed_manifest.json'),'trajectory_sha256':sha(destination/'trajectory.jsonl'),
        'global_dataset_export_performed':False,'rgb_media_sha_audit_performed':False}
    dump(unit/'validation_passed_pending_cleanup.json',report)
    retire_exr(unit,raw)
    dump(unit/'verification_complete.json',report)
    record_test_render(raw,'complete',storage=protocol['request']['storage'])
    return report


def retire_exr(unit,raw):
    files=[]
    for path in sorted(raw.glob('*/render_mask/*.exr')):
        physical_child(path,DATASET_ROOT);stat=path.stat()
        files.append({'path':str(path),'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns})
    dump(unit/'exr_cleanup_manifest.json',{'purpose':'实例和号码EXR消费结束；本轮不保留深度/Cryptomatte','files':files})
    for row in files:
        path=physical_child(row['path'],DATASET_ROOT);stat=path.stat()
        if stat.st_size!=row['bytes'] or stat.st_mtime_ns!=row['mtime_ns']:
            raise ValueError('清单EXR在清理前变化')
        path.unlink()
    dump(unit/'exr_cleanup_complete.json',{'deleted_files':len(files),'deleted_bytes':sum(f['bytes'] for f in files),
        'manifest_sha256':sha(unit/'exr_cleanup_manifest.json')})
