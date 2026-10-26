"""真实UE内创建v10独立12个源Sequence；只建源，不提交MRQ。"""
from copy import deepcopy
import importlib
import json
import math
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue'))
import pose17_joint_grf_sequences as joint
import pose17_location_pilot_sources as previous
import pose17_smoke_runner as runner
from pose17_multiseed_v10_contract import WINDOWS, ORIGINAL_SHA, PACKAGE, validate_v10_contract
from pose17_seeded_kit_contract import require

RUN=ROOT/'Saved/AppearancePlanning/multiseed_v10_a01'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))


def checked(ref):
    path=previous._plain_path(ref['path'])
    require(joint.sha(path)==ref['sha256'],'源身份变化：'+str(path))
    return path


def load_inputs():
    manifest=read(RUN/'manifest.json')
    require(manifest['schema']=='futsalmot_v10_multiseed_capture_plans_v1'
        and len(manifest['source_inputs'])==3 and len(manifest['full_units'])==12,'新scope输入矩阵不完整')
    checked(manifest['source_manifest'])
    plans=[read(checked(r)) for r in manifest['plans']]
    for p in plans:require(validate_v10_contract(p),'不是v10计划');runner.validate_plan(p)
    sources={}
    for reference in manifest['source_inputs']:
        source=read(checked(reference));seed=source['seed'];require(seed in WINDOWS and seed not in sources,'seed重复/未知')
        start,end,_=WINDOWS[seed]
        original=source['original_source']
        require((original['frames']['sha256'],original['meta']['sha256'])==ORIGINAL_SHA[seed], '原始完整SHA不能替换为前缀')
        meta=read(checked(original['meta']));lines=checked(original['frames']).read_bytes().splitlines(keepends=True)
        require(meta.get('schema')=='grf_ue_episode' and meta['source']['seed']==seed
            and meta['source']['environment']=='google_research_football' and meta['source']['scenario']=='5_vs_5'
            and meta['timing']==dict(source_step_seconds=.1,playback_fps=10,num_steps=1800)
            and len(lines)==1800,'原GRF身份或时间基变化')
        frames=[json.loads(line) for line in lines[:end]]
        for index,row in enumerate(frames):
            require(row['step']==index and type(row['step']) is int
                and math.isfinite(row['time_seconds']) and abs(row['time_seconds']-index*.1)<=1e-12,'源前缀不能重基')
            players=row['players']
            require(len(players)==10 and {p['id'] for p in players}==set(joint.JOINT_VISUAL_IDS),'每帧十实体不完整')
            positions=[p['position_m'] for p in players]+[row['ball']['position_m']]
            require(all(isinstance(p,list) and len(p)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in p)
                for p in positions),'源球/球员须有限三维位置')
        prefix=source['prepared_prefix'];expected=deepcopy(meta);expected['timing']['num_steps']=end
        require(read(checked(prefix['meta']))==expected and checked(prefix['frames']).read_bytes()==b''.join(lines[:end]),
            '前缀必须保留原完整源零帧至end的原字节')
        mapping=[json.loads(line) for line in checked(prefix['frame_mapping']).read_text(encoding='utf-8').splitlines()]
        require(len(mapping)==300 and all(row==dict(capture_local_index=i,source_step=start+i,
            sequence_frame=start+i,source_time_seconds=(start+i)/10) for i,row in enumerate(mapping)), '实际捕获/源帧映射改变')
        checked(source['original_appearance']);checked(source['original_profile']);checked(source['original_v1_clip'])
        for calibration in source['calibration_manifests'].values():checked(calibration)
        for plan in (p for p in plans if p['seeded_kit_pair']['seed']==seed):
            require(plan['targets']==source['targets'] and plan['seeded_kit_pair']['source_input']==reference
                and plan['seeded_kit_pair']['binding']==source['kit_binding'], '新计划没有绑定实际源/原seed球衣')
        sources[seed]=dict(source=source,meta=expected,frames=frames)
    require(set(sources)==set(WINDOWS),'新三个运动不完整')
    return manifest,plans,sources


def main():
    import unreal
    request=read(RUN/'sources_request.json');action=request['action']
    require(action in ('preflight','prepare') and request['editor_pid']==os.getpid()
        and request['manifest_sha256']==joint.sha(RUN/'manifest.json'),'只接受本次Editor独立源请求')
    for row in request['source_files']:require(joint.sha(ROOT/row['path'])==row['sha256'],'建源代码变化')
    output=RUN/('P2_sources_'+action+'.json');require(not output.exists(),'已执行/partial不自动重放')
    manifest,plans,sources=load_inputs()
    report=dict(schema='futsalmot_v10_source_sequences_v1',action=action,status='started',
        manifest_sha256=joint.sha(RUN/'manifest.json'),MRQ_submitted=False,dynamic_verified=False,sequences=[])
    try:
        gate=runner.preflight()
        require(not gate['dirty_packages'] and not gate['pie_worlds'] and not gate['mrq_running'],'未知dirty或活动PIE/MRQ不建源')
        _,before=joint._scene(unreal,plans[0])
        paths={c['source_sequence'] for p in plans for c in p['cameras']}
        require(len(paths)==12 and not unreal.EditorAssetLibrary.does_directory_exist(PACKAGE)
            and not any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in paths),'新资产或package已存在，不覆盖')
        canonical=[ROOT/'Content/FutsalMOT/Sequences'/f'LS_Cam_{i:02d}.uasset' for i in range(1,5)]
        canonical.append(ROOT/'Content/FutsalMOT/Maps/L_FutsalCourt.umap')
        hashes={str(p):joint.sha(p) for p in canonical}
        report.update(status='preflight_passed_not_rendered',scene_before=before,canonical_before=hashes)
        if action=='prepare':
            builder=importlib.import_module('import_grf_episode')
            mapping=read(ROOT/'python/ue/actor_mapping.example.json')
            require(mapping=={**{e:'Player_'+e for e in joint.JOINT_VISUAL_IDS},'BALL':'Ball_01'},'Actor映射变化')
            for seed,item in sources.items():
                plan=next(p for p in plans if p['seeded_kit_pair']['seed']==seed)
                builder.create_sequence(item['meta'],item['frames'],mapping,replace_existing=False,
                    package_path=item['source']['P2_sequence_package'],
                    sequences_cfg=[dict(name='LS_Cam_'+c['camera_id'][-2:],camera_actor=c['camera_id']) for c in plan['cameras']],
                    ball_rolling_cfg=dict(enabled=True,radius_m=.11,minimum_move_distance_m=.0001,roll_sign=1.),
                    open_after_create=False,run_api_smoke=False)
                for camera in plan['cameras']:
                    report['sequences'].append(previous._sequence_summary(unreal,camera['source_sequence'],camera['camera_id'],builder,WINDOWS[seed][1]))
                _,after=joint._scene(unreal,plans[0]);require(before==after and not joint._dirty(unreal),'建源改变场景或dirty，保留partial')
            require({str(p):joint.sha(p) for p in canonical}==hashes,'原canonical或地图变化')
            report.update(status='twelve_new_source_sequences_saved_not_captured',scene_preserved=True,
                asset_bindings=[dict(path='Content/'+p.replace('/Game/','')+'.uasset',
                    sha256=joint.sha(ROOT/('Content/'+p.replace('/Game/','')+'.uasset'))) for p in sorted(paths)])
        joint._dump_new(output,report)
    except BaseException as error:
        report.update(status='failed_partial_preserved_no_retry',error=repr(error));joint._dump_new(output,report);raise
    print(json.dumps(dict(status=report['status'],sequences=len(report['sequences']),MRQ_submitted=False)))


if __name__=='__main__':main()
