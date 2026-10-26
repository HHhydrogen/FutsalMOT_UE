"""绿色分阶段准入：默认只读核验，明确--freeze才登记当前来源与源码字节。"""
import argparse
import json
from pathlib import Path
import shutil

from prepare_green_kit_pair_a01 import ROOT,RUN,read,sha
from pose17_seeded_kit_contract import validate_seeded_kit_contract
from pose17_smoke_runner import validate_plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=('short','full'),required=True)
    p.add_argument('--freeze',action='store_true');a=p.parse_args()
    manifest=read(RUN/'manifest.json');assert len(manifest['full_units'])==16
    refs=[r for r in manifest['plans'] if r['stage']=='short'] if a.stage=='short' else manifest['full_units']
    assert len(refs)==(8 if a.stage=='short' else 16)
    old=read(ROOT/'Saved/AppearancePlanning/seeded_kit_capture_a03/admission_full_a01.json')
    paths={r['path'] for r in old['source_files'] if not r['path'].startswith('Saved/AppearancePlanning/')}
    paths.update(('python/ue/pose17_green_kit_contract.py','python/ue/pose17_green_kit_p2.py',
        'python/ue/pose17_green_floor_transaction.py','python/src/grf_ue_bridge/green_floor.py',
        'python/src/grf_ue_bridge/floor_diversity.py','python/src/grf_ue_bridge/tools/export_green_seeded_kit.py',
        'tools/appearance/prepare_green_kit_pair_a01.py','tools/appearance/freeze_green_kit_admission_a01.py',
        'tools/appearance/run_green_kit_serial_a01.py','tools/appearance/test_green_kit_contract.py',
        'Saved/FloorDiversity/green_v1/green_asset_creation_complete.json'))
    creation=read(ROOT/'Saved/FloorDiversity/green_v1/green_asset_creation_complete.json')
    assert creation['status']=='green_assets_created_graph_and_parameters_verified_not_render_accepted'
    assert creation['map_binding_changed'] is False and creation['original_assets_modified'] is False
    paths.update(creation['source_sha256'])
    for asset in creation['created_assets']:
        path=ROOT/'Content'/(asset.split('.')[0].replace('/Game/','')+'.uasset')
        paths.add(str(path.relative_to(ROOT)).replace('\\','/'))
    for ref in refs:
        assert sha(ref['path'])==ref['sha256'];plan=read(ref['path'])
        assert validate_seeded_kit_contract(plan);validate_plan(plan)
        for camera in plan['cameras']:
            paths.add('Content/'+camera['source_sequence'].replace('/Game/','')+'.uasset')
        for target in plan['targets']:
            paths.add(str(Path(target['landmark_manifest']).relative_to(ROOT)).replace('\\','/'))
    items=[dict(path=path,sha256=sha(ROOT/path)) for path in sorted(paths)]
    value=dict(schema='futsalmot_green_seeded_kit_admission_v1',runtime_authorized=True,stage=a.stage,
        manifest_sha256=sha(RUN/'manifest.json'),source_files=items,
        module_sha256=sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll'),serial_render_export=True,
        test_read=False,source_unknown_visibility_preserved=True,EXR_consumption_then_immediate_retirement=True)
    if a.stage=='full':
        acceptance=read(RUN/'short_acceptance_root.json')
        assert acceptance['root_visual_reviewed'] is True and acceptance['acceptance_passed'] is True
        value['short_acceptance_sha256']=sha(RUN/'short_acceptance_root.json')
    output=RUN/('admission_'+a.stage+'_a01.json')
    if a.freeze:
        assert not output.exists() and not (RUN/('control_'+a.stage+'_a01')).exists()
        frozen=RUN/('frozen_'+a.stage+'_source_bytes');frozen.mkdir(exist_ok=False)
        for item in items:
            path=ROOT/item['path']
            if path.suffix not in ('.py','.cpp','.h','.ps1'):continue
            target=frozen/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target);assert sha(target)==item['sha256']
        with output.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
        request=dict(operation='call',toolset='futsalmot_tools.FutsalMOTTools',tool='run_python_file',
            arguments=dict(path='python/ue/pose17_green_kit_p2.py'))
        requestpath=RUN/'mcp_request.json'
        if requestpath.exists():assert read(requestpath)==request
        else:requestpath.write_text(json.dumps(request,indent=2),encoding='utf-8')
    print(json.dumps(dict(status='green_admission_frozen' if a.freeze else 'readonly_green_admission_preflight',
        stage=a.stage,units=len(refs),source_files=len(items),serial_render_export=True)))


if __name__=='__main__':main()
