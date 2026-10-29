"""同一seed按机位独立执行；保持全局选定机位、运动及随机分配不变。"""
from pathlib import Path
import json
import shutil
from .single_seed import read,dump,sha,canonical_sha
from .seeded_episode import prepare_episode_recipe


def prepare(local,short=False):
    local=Path(local);unit=local/'short' if short else local
    p=read(local/'protocol.json');base=read(unit/'resolved.json')
    source=Path(base['trajectory_output']);plan=p['recipe']['components']['cameras']
    root=unit/'partitions';root.mkdir(exist_ok=False)
    parts=[]
    for entry in plan['entries']:
        name=entry['camera_id'];part=root/name;target=part/'source';target.mkdir(parents=True)
        for filename in ('frames.jsonl','meta.json'):shutil.copyfile(source/filename,target/filename)
        task=json.loads(json.dumps(base));task['task_id']+='_'+name
        task['trajectory_output']=str(target)
        task['ue_profile']['sequence_package_path']+='_'+name
        task['single_seed_camera_partition']={'camera_id':name,'plan_sha256':canonical_sha(plan)}
        task['audit']['expected_cameras']=1
        recipe=prepare_episode_recipe(target,task['ue_profile'])
        original=read(source/'provenance/seeded_episode.json')
        if recipe['components']!=original['components']:
            raise ValueError('分任务改变随机分配')
        dump(part/'resolved.json',task)
        parts.append({'camera_id':name,'directory':str(part),'resolved_sha256':sha(part/'resolved.json'),
                      'frames_sha256':sha(target/'frames.jsonl')})
    result={'schema':'futsalmot_single_seed_partitions_v1','protocol_sha256':sha(local/'protocol.json'),
            'one_editor_per_camera':True,'parts':parts}
    dump(root/'manifest.json',result)
    return result


def aggregate(local,short=False):
    """只汇总真实完成收据，不补造失败机位或覆盖原分任务记录。"""
    local=Path(local);unit=local/'short' if short else local
    manifest=read(unit/'partitions/manifest.json');p=read(local/'protocol.json')
    if manifest['protocol_sha256']!=sha(local/'protocol.json'):
        raise ValueError('分任务协议改变')
    if [r['camera_id'] for r in manifest['parts']]!=p['recipe']['components']['cameras']['selected_ids']:
        raise ValueError('机位不完整或重复')
    jobs=[];receipts=[]
    for row in manifest['parts']:
        part=Path(row['directory']);task=read(part/'resolved.json')
        if sha(part/'resolved.json')!=row['resolved_sha256'] or sha(Path(task['trajectory_output'])/'frames.jsonl')!=row['frames_sha256']:
            raise ValueError('分任务输入改变')
        end=read(part/'execution_complete.json');summary=read(part/'render_summary.json')
        if end['status']!='normal_exit' or summary['status']!='success' or any(j['status']!='success' for j in summary['jobs']):
            raise ValueError('分任务渲染/退出未完成')
        for name in ('appearance_application','environment_application','floor_application'):
            if read(Path(task['trajectory_output'])/('provenance/'+name+'.json'))['state']!='restored':
                raise ValueError('分任务事务未恢复')
        jobs.extend(summary['jobs']);receipts.append({'camera_id':row['camera_id'],'summary_sha256':sha(part/'render_summary.json')})
    task=read(unit/'resolved.json');raw=Path(task['dataset_root'])/task['episode_name']
    if (raw/'render_summary.json').exists():raise FileExistsError('不覆盖汇总')
    dump(raw/'render_summary.json',{'status':'success','jobs':jobs,'partition_receipts':receipts})
    dump(unit/'partitions/complete.json',{'status':'all_cameras_complete','receipts':receipts})
