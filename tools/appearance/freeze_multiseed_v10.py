"""v10源已真实构建后冻结分阶段准入；完整采集必须先有根短样验收。"""
import argparse
import json
from pathlib import Path
import shutil
from prepare_multiseed_v10 import ROOT,RUN,read,sha
from pose17_multiseed_v10_contract import validate_v10_contract
from pose17_smoke_runner import validate_plan
from pose17_seeded_kit_contract import require


def freeze(stage,write=False):
    manifest=read(RUN/'manifest.json');source=read(RUN/'P2_sources_prepare.json')
    require(source['status']=='twelve_new_source_sequences_saved_not_captured'
        and source['manifest_sha256']==sha(RUN/'manifest.json') and source['scene_preserved'] is True
        and len(source['asset_bindings'])==12,'先完成真实独立建源')
    refs=[r for r in manifest['plans'] if r['stage']=='short'] if stage=='short' else manifest['full_units']
    require(len(refs)==(3 if stage=='short' else 12),'v10矩阵不符')
    original=read(ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01/admission_full_a01.json')
    omitted={'tools/appearance/freeze_green_kit_admission_a01.py','tools/appearance/prepare_green_kit_pair_a01.py',
             'tools/appearance/test_green_kit_contract.py'}
    paths={r['path'] for r in original['source_files'] if not r['path'].startswith('Content/FutsalMOT/Development/Pose17/')
           and r['path'] not in omitted}
    paths.update(('python/ue/pose17_multiseed_v10_contract.py','python/ue/pose17_multiseed_v10_sources.py',
        'python/ue/pose17_multiseed_v10_p2.py','tools/appearance/prepare_multiseed_v10.py',
        'tools/appearance/freeze_multiseed_v10.py','tools/appearance/run_multiseed_v10_serial.py',
        'python/ue/import_grf_episode.py','python/ue/pose17_joint_grf_sequences.py',
        'python/ue/pose17_location_pilot_sources.py'))
    for r in source['asset_bindings']:
        require(sha(ROOT/r['path'])==r['sha256'],'实际建源资产改变');paths.add(r['path'])
    for r in refs:
        require(sha(r['path'])==r['sha256'],'计划改变');plan=read(r['path'])
        require(validate_v10_contract(plan),'不是v10');validate_plan(plan)
        for key in ('base_plan','source_input','original_appearance'):
            item=plan['seeded_kit_pair'][key];path=Path(item['path'])
            require(ROOT in path.parents and sha(path)==item['sha256'],'计划来源改变')
            paths.add(path.relative_to(ROOT).as_posix())
    items=[dict(path=p,sha256=sha(ROOT/p)) for p in sorted(paths)]
    value=dict(schema='futsalmot_v10_multiseed_admission_v1',stage=stage,runtime_authorized=True,
        manifest_sha256=sha(RUN/'manifest.json'),source_prepare_sha256=sha(RUN/'P2_sources_prepare.json'),
        source_files=items,module_sha256=sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll'),
        serial_render_export=True,test_read=False,training_authorized=False,
        source_unknown_visibility_preserved=True,EXR_consumption_then_immediate_retirement=True)
    if stage=='full':
        acceptance=read(RUN/'short_acceptance_root.json')
        require(acceptance['acceptance_passed'] is True and acceptance['root_visual_reviewed'] is True
            and acceptance['rgb']==36 and acceptance['person_pose']==360,'36帧动态短样尚未根验收')
        value['short_acceptance_sha256']=sha(RUN/'short_acceptance_root.json')
    if write:
        path=RUN/f'admission_{stage}_a01.json'
        require(not path.exists() and not (RUN/f'control_{stage}_a01').exists(),'已有准入或partial，拒绝覆盖')
        directory=RUN/f'frozen_{stage}_source_bytes';directory.mkdir(exist_ok=False)
        for item in items:
            original=ROOT/item['path']
            if original.suffix not in ('.py','.cpp','.h','.ps1'):continue
            target=directory/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(original,target);require(sha(target)==item['sha256'],'冻结字节不符')
        with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
        request=dict(operation='call',toolset='futsalmot_tools.FutsalMOTTools',tool='run_python_file',
            arguments=dict(path='python/ue/pose17_multiseed_v10_p2.py'))
        path=RUN/'mcp_request.json'
        if path.exists():require(read(path)==request,'原请求不符')
        else:
            with path.open('x',encoding='utf-8') as stream:json.dump(request,stream,indent=2)
    return dict(status='v10_admission_frozen' if write else 'readonly_v10_admission_preflight',
        stage=stage,units=len(refs),source_files=len(items),render_started=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=('short','full'),required=True)
    p.add_argument('--freeze',action='store_true');a=p.parse_args();print(json.dumps(freeze(a.stage,a.freeze)))
