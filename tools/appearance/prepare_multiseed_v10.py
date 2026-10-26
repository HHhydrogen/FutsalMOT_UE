"""将已登记三运动源接到独立v10短样/完整计划；默认只读，不启动UE。"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue')); sys.path.insert(0,str(ROOT/'python/src'))
from prepare_seeded_kit_capture import read, sha
from pose17_seeded_kit_contract import digest, context_payload, require
from pose17_multiseed_v10_contract import WINDOWS, ORIGINAL_SHA, PACKAGE, SCHEMA, SCOPE, validate_v10_contract
from pose17_green_kit_contract import GREEN_CATALOG, select_floor_id, expected_material
from pose17_smoke_runner import validate_plan

RUN = ROOT/'Saved/AppearancePlanning/multiseed_v10_a01'
SOURCES = ROOT/'Saved/ResearchBuild/v10_motion_sources_a01'


def ref(path): return dict(path=str(path).replace('\\','/'),sha256=sha(path))


def plans():
    manifest = read(SOURCES/'manifest.json')
    require(manifest['status'] == 'CPU_sources_selected_and_prefix_prepared_not_UE_verified'
            and manifest['independent_new_motion_seeds'] == list(WINDOWS), '只接受既有v10源登记')
    base = ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01/greenkit_s00001048_B_short_a01_gpu_lbs.json'
    template = read(base); output = []; source_refs = []
    for seed, (start,end,split) in WINDOWS.items():
        path = SOURCES/f'seed_{seed:08d}/source_input.json'; source = read(path); source_ref = ref(path)
        require(source == next(g for g in manifest['groups'] if g['seed'] == seed)
                and source['selected_source_frame_range'] == [start,end]
                and source['original_source']['frames']['sha256'] == ORIGINAL_SHA[seed][0]
                and source['original_source']['meta']['sha256'] == ORIGINAL_SHA[seed][1]
                and source['P2_sequence_package'] == PACKAGE+f'/seed_{seed:08d}', '原源输入身份或选窗变化')
        source_refs.append(source_ref)
        for stage,count in (('short',3),('full',300)):
            plan = deepcopy(template)
            plan.update(v10_multiseed_contract=True,source_scope=SCOPE,start_frame=start,frame_count=count,
                targets=deepcopy(source['targets']),review_frame_indices=[min(count-1,150)],
                attempt=f'v10_s{seed:08d}_B_{stage}_a01_gpu_lbs')
            plan['cameras'] = [dict(c,source_sequence=source['P2_sequence_package']+'/LS_Cam_'+c['camera_id'][-2:])
                               for c in source['camera_bindings']]
            plan['source_motion'] = dict(root_seed=seed,source_frames_sha256=ORIGINAL_SHA[seed][0],
                source_meta_sha256=ORIGINAL_SHA[seed][1],context_source_frame_range=[0,end],
                selected_source_frame_range=[start,end],sequence_frame_equals_source_step=True,
                capture_local_zero_source_step=start,fps=10,source_input=source_ref,
                source_build_receipt=str(RUN/'P2_sources_prepare.json').replace('\\','/'))
            floor_id = select_floor_id(seed,catalog=GREEN_CATALOG)
            choice = next(v for v in GREEN_CATALOG if v['id'] == floor_id)
            kit = plan['seeded_kit_pair']
            kit.update(schema=SCHEMA,seed=seed,split=split,stage=stage,variant='B',
                source_frame_range=[start,start+count],floor_id=floor_id,apply_original_seeded_kits=True,
                binding=deepcopy(source['kit_binding']),source_input=source_ref,base_plan=ref(base),
                original_appearance=source['original_appearance'])
            kit['green_floor'].update(id=floor_id,albedo_gain_linear=choice['albedo_gain_linear'],
                material=expected_material(floor_id),purpose='v10_multiseed')
            kit['paired_context_sha256'] = digest(context_payload(plan))
            validate_v10_contract(plan); validate_plan(plan); output.append(plan)
    return output, source_refs


def prepare(write=False):
    values, source_refs = plans(); refs = []; units = []
    def record(plan,camera=None):
        kit=plan['seeded_kit_pair']; path=RUN/(plan['attempt']+'.json')
        if write:
            with path.open('x',encoding='utf-8') as stream: json.dump(plan,stream,ensure_ascii=False,indent=2)
        return dict(attempt=plan['attempt'],seed=kit['seed'],variant='B',stage=kit['stage'],
            purpose='v10_multiseed',floor_id=kit['floor_id'],path=str(path),
            sha256=sha(path) if write else None,**({'camera_id':camera} if camera else {}))
    if write:
        require(not RUN.exists(),'新v10目录已存在，不覆盖partial'); RUN.mkdir(parents=True)
    for plan in values:
        refs.append(record(plan))
        if plan['seeded_kit_pair']['stage'] != 'full': continue
        for camera in plan['cameras']:
            child=deepcopy(plan); child['attempt']=child['attempt'].replace('_full_', '_'+camera['camera_id']+'_')
            validate_plan(child); units.append(record(child,camera['camera_id']))
    result=dict(schema='futsalmot_v10_multiseed_capture_plans_v1',status='CPU_ready_not_runtime_authorized',
        plans=refs,full_units=units,source_inputs=source_refs,source_manifest=ref(SOURCES/'manifest.json'),
        short_RGB=36,full_RGB=3600,full_person_pose=36000,serial_render_export=True,
        training_authorized=False,test_read=False,experimental_augmentation=False)
    if write:
        with (RUN/'manifest.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');a=p.parse_args()
    value=prepare(a.prepare)
    print(json.dumps(dict(status=value['status'],plans=len(value['plans']),units=len(value['full_units']),
        short_RGB=36,full_RGB=3600,render_started=False)))
