"""原seed球衣A/B的独立G盘后处理：复用真实native/EXR门禁，逐机位保留world。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from grf_ue_bridge.storage_policy import physical_child, DATASET_ROOT
from grf_ue_bridge.pose17_export import COCO17_NAMES, project_landmarks
from grf_ue_bridge.tools import export_pose17_diagnostic as masks
from grf_ue_bridge.tools import inspect_pose17_smoke as pairing

ROOT=Path(__file__).resolve().parents[4]
# 本文件位于python/src/.../tools，UE入口位于同一python目录下。
sys.path.insert(0,str(ROOT/'python/ue'))
from pose17_seeded_kit_contract import validate_seeded_kit_contract,assert_seeded_kit_receipt
from pose17_native_receipt import normalize_native_receipt
from pose17_override_receipt import validate_joint_bundle

read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
require=masks.require


def bind(path):return dict(path=str(path),sha256=sha(path))


def context(plan,receipt,manifests,hashes):
    """新3/300帧契约独立绑定；不改旧3/10/120采样函数的准入。"""
    require(validate_seeded_kit_contract(plan),'不是新服装配对契约')
    assert_seeded_kit_receipt(plan,receipt)
    require(receipt['camera_state_restored'] is True and not receipt['restore_errors']
            and receipt['streaming_state_restart_required'] is False and not receipt['pipeline_setup_error'],
            '原生恢复/准备未通过')
    result=dict(path='gpu_render_cpu_lbs',scope=pairing.GPU_LBS_JOINT_SCOPE,
        warmup_frames=plan['gpu_lbs_warmup_frames'],prepared_engine_frame=receipt['gpu_lbs_prepared_engine_frame'],
        bindings={t['entity_id']:{**t,'manifest_sha256':hashes[t['entity_id']],
            'ue_identity':manifests[t['entity_id']]['ue_identity']} for t in plan['targets']},
        overrides_by_entity={},calibration_by_entity=dict(pairing.JOINT_ROLE_IDS),start_frame=plan['start_frame'])
    allowed=(pairing.PLAYER003_ASSET,*pairing.CALIBRATION_ASSETS.values())
    for entity,target in result['bindings'].items():
        entries=[r for r in receipt['visual_mesh_overrides']
                 if r['component_path'].endswith('.'+target['actor_object_name']+'.MPFBVisual')]
        if target['calibration_player_id']==3:require(not entries,'003原角色不能发生override')
        else:
            require(len(entries)==1,'角色override不唯一')
            result['overrides_by_entity'][entity]=pairing.check_override_transaction(entries[0],target,target,
                result,pairing.CALIBRATION_ASSETS[target['calibration_player_id']],allowed)
    return result


def metadata(attempt):
    require(attempt.parent==Path('D:/projects/FutsalMOT_UEDataset/Saved/Pose17Development/smoke'), '元数据目录不匹配')
    plan,state=read(attempt/'plan.json'),read(attempt/'state.json')
    require(validate_seeded_kit_contract(plan) and sha(attempt/'plan.json')==state['plan_sha256'],'计划身份变化')
    require(state.get('session_released') is True and (attempt/'session_release.json').exists(),'自有会话未成功释放')
    raw=physical_child(state['media_root'],DATASET_ROOT)
    require(raw==DATASET_ROOT/'_work'/plan['attempt']/'raw','raw根不是精确新attempt')
    manifests={};hashes={}
    for target in plan['targets']:
        entity=target['entity_id'];p=attempt/(entity+'_landmark_snapshot.json')
        manifests[entity]=read(p);hashes[entity]=sha(p)
        require(sha(Path(target['landmark_manifest']))==hashes[entity],'校准原文件与本次快照不同')
    receipts={c['camera_id']:normalize_native_receipt(read(attempt/(c['camera_id']+'_native_pose_restore_receipt.json'))) for c in plan['cameras']}
    report=validate_joint_bundle(plan,state,read(attempt/'preflight.json'),read(attempt/'editor_after.json'),manifests,hashes,receipts)
    require(report['acceptance_passed'] is True and not report['errors'],'native验收失败：'+repr(report['errors']))
    return plan,state,raw,manifests,hashes,receipts,report


def export(attempt,output,workers,metadata_loader=None):
    import OpenEXR
    started=time.perf_counter()
    require(1<=workers<=6,'后处理必须1..6个有界进程')
    plan,state,raw,manifests,hashes,receipts,report=(metadata_loader or metadata)(attempt)
    metadata_wall=time.perf_counter()-started;decode_wait_wall=0.0;parent_frame_wall=0.0
    output=physical_child(output,DATASET_ROOT)
    require(output==DATASET_ROOT/'_staging'/plan['attempt'] and not output.exists(),'输出须全新精确stage，拒绝partial重放')
    kit=plan['seeded_kit_pair'];n=plan['frame_count'];entities={t['entity_id'] for t in plan['targets']}
    mapping={entity:'Player_'+entity for entity in entities}
    output.mkdir(parents=True)
    masks.write_json(output/'export_started.json',dict(status='started_no_implicit_replay',plan=bind(attempt/'plan.json')))
    masks.write_json(output/'native_acceptance.json',report)
    views={};postviews=[];unknown=0
    journal=(output/'rgb_move.jsonl').open('x',encoding='utf-8')
    try:
        for name,receipt in receipts.items():
            ctx=context(plan,receipt,manifests,hashes)
            rgb=pairing.media_index(raw/name,'rgb',name);exr=pairing.media_index(raw/name,'exr',name)
            require(set(rgb)==set(exr)==set(range(n)),'RGB/EXR帧集不完整')
            directory=output/'cameras'/name
            for kind in ('rgb','mask'):(directory/kind).mkdir(parents=True)
            rows={(r['output_frame'],r['entity_id']):r for r in receipt['records']}
            require(len(rows)==n*10 and set(rows)=={(f,e) for f in range(n) for e in entities},'原生帧/实体集合变化')
            poses=[];worlds=[];calibration=None
            jobs=((f,exr[f],rgb[f],directory/'mask'/('%06d.png'%f),mapping) for f in range(n))
            previous_frame_end=time.perf_counter()
            for frame,width,height,geometry in masks._mask_results(jobs,workers):
                frame_started=time.perf_counter();decode_wait_wall+=frame_started-previous_frame_end
                header=OpenEXR.File(str(exr[frame]),header_only=True).header()
                for entity in sorted(entities):
                    row=rows[(frame,entity)]
                    camera=pairing.check_pair(row,header,name,frame,sampling=ctx)
                    actual={key:camera[key] for key in ('intrinsics','extrinsics')}
                    if calibration is None:calibration=actual
                    require(actual==calibration and (width,height)==(3840,2160),'相机/图像尺寸变化')
                    points=project_landmarks([dict(world_m=p,source_method=row['sampling_method']) for p in row['world_m']],camera)
                    require(all(p['visibility_state']=='unknown' for p in points),'可见性被升级')
                    track=int(entity[1])+(1 if entity[0]=='L' else 6);bbox,area=geometry[entity]
                    shared=dict(frame_index=frame,source_frame_index=plan['start_frame']+frame,entity_id=entity,track_id=track)
                    poses.append(dict(**shared,rgb_ref='rgb/%06d.png'%frame,mask_ref='mask/%06d.png'%frame,
                        mask_id=track,uv_px=[p.get('uv_px') for p in points],
                        location_valid=[p.get('uv_px') is not None for p in points],
                        visibility_state=['unknown']*17,visibility_method='not_measured',
                        camera_forward_depth_m=[p.get('camera_forward_depth_m') for p in points],
                        bbox_visible_xywh=bbox,visible_mask_area=area))
                    worlds.append(dict(**shared,world_m=row['world_m'],source_method=row['sampling_method'],
                        manifest_sha256=hashes[entity],mesh_identity=row['mesh_identity'],
                        engine_frame=row['hook_engine_frame'],pose_revision=row['pose_revision_after']))
                    unknown+=17
                destination=directory/'rgb'/('%06d.png'%frame)
                journal.write(json.dumps(dict(event='intent',source=str(rgb[frame]),destination=str(destination)))+'\n');journal.flush()
                os.rename(rgb[frame],destination)
                journal.write(json.dumps(dict(event='moved',destination=str(destination)))+'\n');journal.flush()
                previous_frame_end=time.perf_counter();parent_frame_wall+=previous_frame_end-frame_started
            masks.write_json(directory/'view.json',calibration)
            masks.write_jsonl(directory/'pose2d.jsonl',poses);masks.write_jsonl(directory/'pose3d_world.jsonl',worlds)
            views[name]=dict(view_ref='cameras/'+name+'/view.json',pose2d_ref='cameras/'+name+'/pose2d.jsonl',
                pose3d_world_ref='cameras/'+name+'/pose3d_world.jsonl',frames=n,
                record_layout='one_person_per_line',native_receipt=bind(attempt/(name+'_native_pose_restore_receipt.json')))
            postviews.append(dict(frames=n,person_records=n*10,rgb_directory=str(directory/'rgb'),mask_directory=str(directory/'mask'),
                pose_jsonl=bind(directory/'pose2d.jsonl'),world_jsonl=bind(directory/'pose3d_world.jsonl')))
    finally:journal.close()
    group=dict(schema='futsalmot_pose17_seeded_kit_diagnostic_group_v1',seed=kit['seed'],split=kit['split'],
        variant=kit['variant'],stage=kit['stage'],source_frame_range=kit['source_frame_range'],fps=10,
        paired_context_sha256=kit['paired_context_sha256'],cameras=views,keypoint_names=list(COCO17_NAMES),
        original_seeded_kit_binding=kit['binding'],world_storage='per_camera_native',world_values_modified=False,
        diagnostic_only=True,not_training=True,production_accepted=False,MRQ_sync_verified=False,
        plan=bind(attempt/'plan.json'),state=bind(attempt/'state.json'),source_motion=plan['source_motion'],
        capture_scope=state.get('capture_scope'))
    if (attempt/'output_config.json').exists():group['output_config']=bind(attempt/'output_config.json')
    if plan.get('green_seeded_kit_contract') is True:
        group['green_floor']=kit['green_floor']
        group['green_floor_restored']=state['green_floor_restored']
    if plan.get('v10_multiseed_contract') is True:
        group['capture_experiment']='multiseed_v10_a01'
        group['independent_motion_scope']=plan['source_scope']
    masks.write_json(output/'group.json',group)
    masks.write_json(output/'dataset.json',dict(schema='futsalmot_seeded_kit_diagnostic_export_v1',
        status='complete',group_ref='group.json',rgb_frames=n*len(receipts),mask_frames=n*len(receipts),person_pose=n*10*len(receipts),
        unknown_points=unknown,diagnostic_only=True,not_training=True,MRQ_sync_verified=False))
    post=dict(schema='exr_postprocess_complete_v1',status='complete',attempt=plan['attempt'],raw_root=str(raw),
        dataset_index=bind(output/'dataset.json'),exr_decode_count=n*len(receipts),views=postviews,
        producer_output_closed=True,all_native_and_EXR_header_checks_passed=True,
        consumer_process_id=os.getpid(),bounded_worker_pool_closed=True,
        performance=dict(workers=workers,inflight_frames_bound=workers,metadata_validation_wall_seconds=metadata_wall,
            wait_for_decoded_frames_wall_seconds=decode_wait_wall,parent_frame_checks_projection_move_wall_seconds=parent_frame_wall,
            elapsed_until_completion_receipt_seconds=time.perf_counter()-started,
            interpretation='父进程等待与检查墙钟，解码并行重叠，不是kernel profiler或加速倍数'))
    masks.write_json(output/'postprocess_complete.json',post)
    return dict(status='complete',attempt=plan['attempt'],RGB=n*len(receipts),mask=n*len(receipts),person_pose=n*10*len(receipts),
                EXR_consumers_finished=True,output=str(output))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attempt',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();print(json.dumps(export(a.attempt,a.output,a.workers),ensure_ascii=False))


if __name__=='__main__':main()
