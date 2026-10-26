"""派生绿色A/B及颜色边界短样；只写独立Saved清单，不启动UE。"""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue'));sys.path.insert(0,str(ROOT/'python/src'))
from prepare_seeded_kit_capture import build_plans,read,sha
from pose17_green_kit_contract import SCHEMA,SCOPE,expected_material
from pose17_seeded_kit_contract import context_payload,digest,validate_seeded_kit_contract
from pose17_smoke_runner import validate_plan
from grf_ue_bridge.green_floor import GREEN_CATALOG
from grf_ue_bridge.floor_diversity import select_floor_id

RUN=ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01'


def plans():
    creation=ROOT/'Saved/FloorDiversity/green_v1/green_asset_creation_complete.json'
    receipt=read(creation)
    if receipt['status']!='green_assets_created_graph_and_parameters_verified_not_render_accepted':
        raise ValueError('缺真实材质创建读回，不以CPU候选冒充')
    original=build_plans(read(ROOT/'Saved/AppearancePlanning/seeded_kit_recovery_a01/plan.json'),revision='a02')
    result=[]
    for source in original:
        plan=deepcopy(source);kit=plan['seeded_kit_pair'];seed=kit['seed']
        floor_id=select_floor_id(seed,catalog=GREEN_CATALOG)
        plan.update(green_seeded_kit_contract=True,source_scope=SCOPE,
            attempt=f'greenkit_s{seed:08d}_{kit["variant"]}_{kit["stage"]}_a01_gpu_lbs')
        variant=next(v for v in GREEN_CATALOG if v['id']==floor_id)
        kit.update(schema=SCHEMA,floor_id=floor_id,green_floor=dict(schema='futsalmot_green_floor_runtime_recipe_v1',
            id=floor_id,albedo_gain_linear=variant['albedo_gain_linear'],material=expected_material(floor_id),
            sequence_constant=True,purpose='seeded_kit_pair',creation_proof=dict(path=str(creation),sha256=sha(creation))))
        kit['paired_context_sha256']=digest(context_payload(plan))
        validate_seeded_kit_contract(plan);validate_plan(plan);result.append(plan)
    base=next(p for p in result if p['seeded_kit_pair']['seed']==1048
              and p['seeded_kit_pair']['stage']=='short' and p['seeded_kit_pair']['variant']=='B')
    for variant in GREEN_CATALOG:
        if variant['id']==base['seeded_kit_pair']['floor_id']:continue
        plan=deepcopy(base);kit=plan['seeded_kit_pair'];floor_id=variant['id']
        plan['attempt']='greenswatch_s00001048_B_'+floor_id+'_a01_gpu_lbs'
        kit['floor_id']=floor_id;kit['green_floor'].update(id=floor_id,material=expected_material(floor_id),
            albedo_gain_linear=variant['albedo_gain_linear'],purpose='palette_check')
        kit['paired_context_sha256']=digest(context_payload(plan))
        validate_seeded_kit_contract(plan);validate_plan(plan);result.append(plan)
    return result


def full_unit_plans(result):
    units=[]
    for source in result:
        if source['seeded_kit_pair']['stage']!='full':continue
        kit=source['seeded_kit_pair']
        for camera in source['cameras']:
            child=deepcopy(source)
            child['attempt']=f'greenpart_s{kit["seed"]:08d}_{kit["variant"]}_{camera["camera_id"]}_a01_gpu_lbs'
            validate_plan(child)
            units.append((child,camera['camera_id']))
    return units


def main():
    if RUN.exists():raise FileExistsError('新清单目录已存在，不覆盖')
    result=plans();RUN.mkdir(parents=True)
    refs=[]
    for plan in result:
        p=RUN/(plan['attempt']+'.json');p.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
        kit=plan['seeded_kit_pair'];refs.append(dict(attempt=plan['attempt'],seed=kit['seed'],variant=kit['variant'],
            stage=kit['stage'],purpose=kit['green_floor']['purpose'],floor_id=kit['floor_id'],
            path=str(p),sha256=sha(p)))
    unit_refs=[]
    for plan,camera in full_unit_plans(result):
        p=RUN/(plan['attempt']+'.json');p.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
        kit=plan['seeded_kit_pair'];unit_refs.append(dict(attempt=plan['attempt'],seed=kit['seed'],variant=kit['variant'],
            stage='full',purpose='seeded_kit_pair',floor_id=kit['floor_id'],camera_id=camera,path=str(p),sha256=sha(p)))
    manifest=dict(schema='futsalmot_green_seeded_kit_plans_v1',status='CPU_ready_not_runtime_authorized',
        plans=refs,full_units=unit_refs,main_short_RGB=48,palette_short_RGB=48,all_short_RGB=96,full_RGB=4800,
        serial_render_export=True,test_read=False,experimental_augmentation=False)
    (RUN/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=manifest['status'],shorts=8,full_plans=4,
        floors={str(s):select_floor_id(s,catalog=GREEN_CATALOG) for s in (1048,1102)})))


if __name__=='__main__':main()
