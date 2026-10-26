"""从原长窗与原seed服装绑定派生独立A/B计划，只写Saved小清单。"""
import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/ue'))
from pose17_seeded_kit_contract import SCHEMA,SCOPE,WINDOWS,digest,context_payload,validate_seeded_kit_contract
from pose17_smoke_runner import validate_plan

read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_plans(recovery,revision='a01'):
    if revision not in ('a01','a02'):raise ValueError('必须登记明确新attempt版本')
    require=recovery['status']=='existing_seeded_manifest_reused_not_rendered'
    if not require:raise ValueError('必须先复用原appearance v1清单')
    plans=[]
    for group in recovery['groups']:
        seed=group['binding']['root_seed'];start,end,split=WINDOWS[seed]
        base=ROOT/f'Saved/Pose17Development/long_window_inputs_a02/longpair_s{seed:08d}_sport_blue_v1_a01_gpu_lbs.json'
        original=read(base)
        for stage,count in (('short',3),('full',300)):
            for variant in ('A','B'):
                plan=deepcopy(original)
                for key in ('long_window_contract','long_window','floor_pair'):plan.pop(key,None)
                plan.update(attempt=f'kitpair_s{seed:08d}_{variant}_{stage}_{revision}_gpu_lbs',frame_count=count,
                    source_scope=SCOPE,review_frame_indices=[min(count-1,150)],seeded_kit_pair_contract=True)
                plan['seeded_kit_pair']=dict(schema=SCHEMA,seed=seed,split=split,stage=stage,variant=variant,
                    source_frame_range=[start,start+count],floor_id='sport_blue_v1',apply_original_seeded_kits=variant=='B',
                    binding=deepcopy(group['binding']),source_input=group['source_input'],
                    base_plan=dict(path=str(base),sha256=sha(base)),original_appearance=group['original_appearance'])
                plan['seeded_kit_pair']['paired_context_sha256']=digest(context_payload(plan))
                validate_seeded_kit_contract(plan);validate_plan(plan)
                plans.append(plan)
    return plans


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recovery',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--revision',choices=('a01','a02'),default='a01')
    a=p.parse_args();plans=build_plans(read(a.recovery),a.revision)
    if a.output.exists():raise ValueError('候选目录已存在，不覆盖')
    a.output.mkdir(parents=True)
    refs=[]
    for plan in plans:
        path=a.output/(plan['attempt']+'.json')
        with path.open('x',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2);f.write('\n')
        refs.append(dict(attempt=plan['attempt'],stage=plan['seeded_kit_pair']['stage'],
            seed=plan['seeded_kit_pair']['seed'],variant=plan['seeded_kit_pair']['variant'],path=str(path.resolve()),sha256=sha(path)))
    result=dict(schema='futsalmot_seeded_kit_capture_plans_v1',status='CPU_ready_not_runtime_authorized',
        plans=refs,short_RGB_frames=48,full_RGB_frames=4800,media_root='G:/FutsalMOT_Dataset/_work',
        native_metadata_root=str(ROOT/'Saved/Pose17Development/smoke'),
        original_recovery=dict(path=str(a.recovery.resolve()),sha256=sha(a.recovery)),test_read=False)
    with (a.output/'manifest.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(status=result['status'],plans=len(plans),short_RGB=48,full_RGB=4800)))


if __name__=='__main__':main()
