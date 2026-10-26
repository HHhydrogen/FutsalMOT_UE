"""完整绿色配对一次发布：同G卷移动，单次world配对，partial拒自动重放。"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/src'))
from grf_ue_bridge.storage_policy import physical_child,DATASET_ROOT
from run_seeded_kit_short_a01 import read,sha,save,require
from run_seeded_kit_full_a02 import identity
from run_green_kit_serial_a01 import running
from world_pair_metadata import compare_world

RUN=ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01'
CONTROL=RUN/'control_full_a01'
TARGET=DATASET_ROOT/'v3_pose17_green_seeded_kit_pair_a01'
MAX_WORLD_DELTA_M=.001


def prepare():
    state=read(CONTROL/'state.json');manifest=read(RUN/'manifest.json')
    require(state['status']=='complete_full_16_units_EXR_retired_wait_root_publication'
        and len(state['completed'])==16,'绿色16实际单位未全部完成')
    admission=read(RUN/'admission_full_a01.json')
    require(sha(RUN/'admission_full_a01.json')==state['admission_sha256']
        and sha(RUN/'manifest.json')==admission['manifest_sha256']
        and sha(RUN/'short_acceptance_root.json')==admission['short_acceptance_sha256'],'完整准入/清单/短样验收链变化')
    live=[r for r in identity(state['pid']) if r['Name'].lower().startswith('python')
          and 'run_green_kit_serial_a01.py' in (r['CommandLine'] or '')]
    require(not live or not running(state['pid']),'控制器尚未实际退出')
    require(not TARGET.exists(),'目标已存在，未知partial/重复发布不重放')
    refs={r['attempt']:r for r in manifest['full_units']};items={};moves=[]
    for row in state['completed']:
        ref=refs[row['attempt']];camera=ref['camera_id'];key=(row['seed'],row['variant'],camera)
        require(key not in items and row['rgb']==row['mask']==300 and row['person_pose']==3000
            and row['EXR_deleted']==300 and row['normal_UE_exit'] is True,'实际单位重复或未完成')
        stage=physical_child(row['stage'],DATASET_ROOT)
        require(stage==DATASET_ROOT/'_staging'/row['attempt'],'不是精确单位stage')
        group=read(stage/'group.json');post=read(stage/'postprocess_complete.json');index=read(stage/'dataset.json')
        require(group['capture_scope']['camera_ids']==[camera] and len(group['cameras'])==1
            and group['capture_scope']['full_four_camera_group_complete'] is False
            and group['seed']==row['seed'] and group['variant']==row['variant']
            and group['green_floor']==read(ref['path'])['seeded_kit_pair']['green_floor']
            and group['world_values_modified'] is False and group['not_training'] is True
            and group['green_floor_restored']['status']=='original_floor_slot_restored_not_saved'
            and index['rgb_frames']==index['mask_frames']==300 and index['person_pose']==3000
            and index['MRQ_sync_verified'] is False and len(post['views'])==1,'实际索引/绿色/范围不同')
        require(read(CONTROL/(row['attempt']+'__EXR_complete.json'))['status']=='exr_deleted_after_complete_consumers'
            and read(CONTROL/(row['attempt']+'__shutdown.json'))['process_absent'] is True,'EXR或退出链未闭合')
        destination=physical_child(TARGET/'groups'/('seed_%08d'%row['seed'])/'variants'/
            ('default' if row['variant']=='A' else 'seeded')/'views'/camera,DATASET_ROOT)
        items[key]=dict(row=row,stage=stage,group=group,post=post,destination=destination)
        moves.append(dict(source=str(stage),destination=str(destination),group_sha256=sha(stage/'group.json'),
            dataset_sha256=sha(stage/'dataset.json'),postprocess_sha256=sha(stage/'postprocess_complete.json')))
    require(set(items)=={(s,v,'CineCam_%02d'%c) for s in (1048,1102) for v in 'AB' for c in range(1,5)},'绿色四变体四机位集合错误')
    return state,items,moves


def publish():
    state,items,moves=prepare();metrics={}
    for seed in (1048,1102):
        for c in range(1,5):
            camera='CineCam_%02d'%c;a,b=items[(seed,'A',camera)],items[(seed,'B',camera)]
            require(a['group']['paired_context_sha256']==b['group']['paired_context_sha256']
                and a['group']['green_floor']==b['group']['green_floor'],'A/B运动/绿色冻结上下文不同')
            views=[item['post']['views'][0] for item in (a,b)]
            report=compare_world(views[0]['world_jsonl']['path'],views[1]['world_jsonl']['path'],
                views[0]['world_jsonl']['sha256'],views[1]['world_jsonl']['sha256'])
            require(report['max_world_delta_m']<=MAX_WORLD_DELTA_M,'world差超过1mm工程配对界限，不平均或伪装exact')
            va=read(a['stage']/a['group']['cameras'][camera]['view_ref']);vb=read(b['stage']/b['group']['cameras'][camera]['view_ref'])
            require(va==vb,'实际相机不同，不篡改值')
            metrics[f'{seed}/{camera}']={**report,'actual_camera_exact':True}
    TARGET.mkdir(exist_ok=False);receipt=TARGET/'_publication_a01';receipt.mkdir()
    save(receipt/'intent.json',dict(status='intent_not_complete',control_sha256=sha(CONTROL/'state.json'),
        moves=moves,world_pair_engineering_max_m=MAX_WORLD_DELTA_M,MRQ_sync_verified=False),True)
    with (receipt/'moves.jsonl').open('x',encoding='utf-8') as journal:
        for row in moves:
            source=physical_child(row['source'],DATASET_ROOT);destination=physical_child(row['destination'],DATASET_ROOT)
            require(not destination.exists(),'单位目标已存在');destination.parent.mkdir(parents=True,exist_ok=True)
            journal.write(json.dumps(dict(event='intent',**row))+'\n');journal.flush();os.fsync(journal.fileno())
            os.rename(source,destination)
            journal.write(json.dumps(dict(event='moved',destination=str(destination)))+'\n');journal.flush();os.fsync(journal.fileno())
    groups={}
    for seed in (1048,1102):
        for variant in 'AB':
            cameras={};example=None
            for c in range(1,5):
                camera='CineCam_%02d'%c;item=items[(seed,variant,camera)];example=item['group'];old=example['cameras'][camera];prefix='views/'+camera+'/'
                cameras[camera]={k:prefix+old[k] for k in ('view_ref','pose2d_ref','pose3d_world_ref')}
                cameras[camera].update(capture_unit_ref=prefix+'group.json',rgb_directory_ref=prefix+'cameras/'+camera+'/rgb',
                    mask_directory_ref=prefix+'cameras/'+camera+'/mask',record_layout='one_person_per_line',frames=300)
            folder=TARGET/'groups'/('seed_%08d'%seed)/'variants'/('default' if variant=='A' else 'seeded')
            group=dict(schema='futsalmot_pose17_green_seeded_kit_paired_group_v1',seed=seed,split='train' if seed==1048 else 'synthetic_dev',
                variant=variant,cameras=cameras,keypoint_names=example['keypoint_names'],fps=10,green_floor=example['green_floor'],
                source_frame_range=[0,300] if seed==1048 else [20,320],world_storage='per_camera_native',world_values_modified=False,
                paired_context_sha256=example['paired_context_sha256'],diagnostic_only=True,not_training=True,
                production_accepted=False,MRQ_sync_verified=False,original_seeded_kit_binding=example['original_seeded_kit_binding'])
            save(folder/'group.json',group,True)
            groups[f'{seed}/{variant}']=dict(group_ref=str((folder/'group.json').relative_to(TARGET)),sha256=sha(folder/'group.json'))
    save(receipt/'pair_metadata.json',dict(status='complete_metadata_only',pairs=metrics,world_values_modified=False,
        pixel_equivalence_claimed=False,MRQ_sync_verified=False),True)
    save(receipt/'relocation.json',dict(schema='futsalmot_prefix_relocation_v1',directory_prefixes=moves,
        original_unit_and_consumer_receipt_bytes_preserved=True,no_reverse_junction_created=True),True)
    save(TARGET/'dataset.json',dict(schema='futsalmot_green_seeded_kit_pair_dataset_v1',status='diagnostic_pair_complete_not_training',
        groups=groups,rgb_frames=4800,mask_frames=4800,person_pose=48000,source_time_samples=600,
        fps=10,width=3840,height=2160,visibility='unknown',not_training=True,MRQ_sync_verified=False,
        source_control=dict(path=str(CONTROL/'state.json'),sha256=sha(CONTROL/'state.json')),
        pair_metadata_ref='_publication_a01/pair_metadata.json',relocation_ref='_publication_a01/relocation.json'),True)
    result=dict(status='published_green_16_units_metadata_pair_complete',dataset_sha256=sha(TARGET/'dataset.json'),
        rgb=4800,mask=4800,person_pose=48000,media_copied=0,EXR_retired=4800,all_source_UE_normal_exit=True,
        all_world_exact=all(m['all_world_exact'] for m in metrics.values()),max_world_delta_m=max(m['max_world_delta_m'] for m in metrics.values()))
    save(receipt/'complete.json',result,True);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true');a=p.parse_args()
    if a.publish:result=publish()
    else:
        state,items,moves=prepare();result=dict(status='readonly_green_publication_plan',units=len(items),target=str(TARGET),moves=moves)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
