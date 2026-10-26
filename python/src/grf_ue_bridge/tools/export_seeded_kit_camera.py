"""单机位独立生命周期验收/导出；不借旧四机位成功布尔放行。"""
import argparse
import json
from pathlib import Path
from grf_ue_bridge.tools import export_seeded_kit_pair as base
from pose17_camera_scope import validate_capture_scope
from pose17_smoke_runner import _assert_gpu_lbs_receipt,_assert_override_receipt,validate_plan


def metadata(attempt):
    require=base.require;read=base.read;sha=base.sha
    require(attempt.parent==base.ROOT/'Saved/Pose17Development/smoke','不是D原Saved元数据目录')
    plan,state=read(attempt/'plan.json'),read(attempt/'state.json');validate_plan(plan)
    require(sha(attempt/'plan.json')==state['plan_sha256'],'计划原bytes不同')
    scope=read(attempt/'capture_scope.json')
    cameras=validate_capture_scope(plan,scope,state['plan_sha256']);name=cameras[0]['camera_id']
    require(state.get('capture_scope')==scope and state.get('jobs')==1 and state.get('session_released') is True,
        '没有实际一机位成功/释放范围')
    output=read(attempt/'output_config.json')
    require(output['camera_id']==name and output['base_plan_sha256']==state['plan_sha256']
        and output['world_depth_requested'] is False and output['enabled_additional_materials']==0
        and output['actor_objectID_EXR_retained'] is True and output['AA']=='none'
        and output['temporal_samples']==output['spatial_samples']==1,'当前单机位输出配方不一致')
    require(state['status']=='rendered_requires_RGB_mask_pose_alignment_acceptance'
        and state['executor_success'] is True and not state['errors'] and state['ready_to_render'] is False
        and state.get('editor_restore_probe_pending') is False and state['editor_scene_state_matched'] is True
        and state['editor_mesh_state_matched'] is True and state['streaming_restart_required'] is False,'实际executor/恢复失败')
    release=read(attempt/'session_release.json')
    require(release.get('capture_scope')==scope and release['native_receipts']==[name+'_native_pose_restore_receipt.json'],
            '释放收据机位与实际范围不同')
    jobs=state['completed_jobs'];require(len(jobs)==1 and jobs[0]['job']==name
        and jobs[0]['sampling_passed'] is True and jobs[0]['restore_passed'] is True,'实际native job不完整')
    before,after=read(attempt/'preflight.json'),read(attempt/'editor_after.json')
    for editor in (before,after):
        require(editor['level'].split('.')[0]=='/Game/FutsalMOT/Maps/L_FutsalCourt'
            and not editor['dirty_packages'] and not editor['pie_worlds'] and not editor['mrq_running'],'Editor真实门禁失败')
    require(before['players']==after['players'],'Editor全部角色未恢复')
    raw=base.physical_child(state['media_root'],base.DATASET_ROOT)
    require(raw==base.DATASET_ROOT/'_work'/plan['attempt']/'raw','raw来源越界')
    manifests={};hashes={}
    for target in plan['targets']:
        entity=target['entity_id'];path=attempt/(entity+'_landmark_snapshot.json')
        manifests[entity]=read(path);hashes[entity]=sha(path)
        require(sha(Path(target['landmark_manifest']))==hashes[entity],'冻结校准源与快照不同')
    receipt=base.normalize_native_receipt(read(attempt/(name+'_native_pose_restore_receipt.json')))
    require(receipt['lifecycle_stage']=='pipeline_teardown_before_PIE_cleanup'
        and not receipt['setup_error'] and not receipt['pipeline_setup_error'] and not receipt['restore_errors']
        and receipt['record_limit_reached'] is False and receipt['camera_state_restored'] is True
        and receipt['streaming_state_restart_required'] is False,'native准备/teardown/恢复失败')
    _assert_gpu_lbs_receipt(plan,receipt);_assert_override_receipt(plan,receipt)
    rows=receipt['records'];expected={(f,t['entity_id']) for f in range(300) for t in plan['targets']}
    require(len(rows)==3000 and {(r['output_frame'],r['entity_id']) for r in rows}==expected,'真实3000采样缺失或重复')
    require(all(r['camera_name']==name and r['sequence_source_frame']==plan['start_frame']+r['output_frame'] for r in rows),
            '实际机位或原始源帧不同')
    base.context(plan,receipt,manifests,hashes)
    report=dict(schema='futsalmot_seeded_kit_single_camera_acceptance_v1',acceptance_passed=True,
        component_transaction_passed=True,capture_scope=scope,records=3000,errors=[],
        full_four_camera_group_complete=False,MRQ_sync_verified=False,visibility_state='unknown')
    return plan,state,raw,manifests,hashes,{name:receipt},report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args();print(json.dumps(base.export(args.attempt,args.output,args.workers,metadata_loader=metadata),ensure_ascii=False))


if __name__=='__main__':main()
