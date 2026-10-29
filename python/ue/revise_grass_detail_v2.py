"""按用户反馈拉开绿色深浅与条带对比，保留已调整的细草纹。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python/src'))
from grf_ue_bridge.grass_detail import MATERIAL_ROOT, PARAMETERS, CATALOG


def main():
    import unreal
    lib = unreal.MaterialEditingLibrary
    dirty = lambda: [p.get_path_name() for p in
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) +
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert unreal.EditorLevelLibrary.get_editor_world().get_path_name().split('.')[0] == '/Game/FutsalMOT/Maps/L_FutsalCourt'
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    assert not dirty(), dirty()
    output = ROOT / 'Saved/FloorDiversity/green_v2/revision_a02'
    output.mkdir(exist_ok=False)
    parent = unreal.load_asset(MATERIAL_ROOT + '/M_GrassDetail_v2')
    assert parent and parent.get_class().get_name() == 'Material'
    instances = [unreal.load_asset(MATERIAL_ROOT + '/MI_' + v['id']) for v in CATALOG]
    assert all(i and i.get_class().get_name() == 'MaterialInstanceConstant' for i in instances)
    before = []
    for instance in instances:
        gain = lib.get_material_instance_vector_parameter_value(instance, 'GreenAlbedoGain')
        before.append({'material': instance.get_path_name(), 'gain': [gain.r,gain.g,gain.b],
                       'parameters': {k:float(lib.get_material_instance_scalar_parameter_value(instance,k)) for k in PARAMETERS}})
    (output / 'intent.json').write_text(json.dumps({'before':before,'parameters':PARAMETERS,'catalog':CATALOG},ensure_ascii=False,indent=2),encoding='utf-8')
    for node in lib.get_material_expressions(parent):
        if node.get_class().get_name() == 'MaterialExpressionScalarParameter':
            name = str(node.get_editor_property('parameter_name'))
            if name in PARAMETERS:
                node.set_editor_property('default_value', PARAMETERS[name])
    lib.recompile_material(parent)
    assert unreal.EditorAssetLibrary.save_loaded_asset(parent)
    after = []
    for variant, instance in zip(CATALOG, instances):
        assert instance.get_editor_property('parent') == parent
        for key,value in PARAMETERS.items():
            lib.set_material_instance_scalar_parameter_value(instance,key,value)
            assert abs(float(lib.get_material_instance_scalar_parameter_value(instance,key))-value)<1e-6
        gain = variant['albedo_gain_linear']
        lib.set_material_instance_vector_parameter_value(instance,'GreenAlbedoGain',unreal.LinearColor(*gain,1))
        actual = lib.get_material_instance_vector_parameter_value(instance,'GreenAlbedoGain')
        assert all(abs(a-b)<1e-6 for a,b in zip(gain,[actual.r,actual.g,actual.b]))
        assert unreal.EditorAssetLibrary.save_loaded_asset(instance)
        after.append(dict(variant,material=instance.get_path_name(),parameters=PARAMETERS))
    assert not dirty(), dirty()
    report = {'status':'revised_wait_user_acceptance','before':before,'after':after,'dirty_after':[],
              'reason':'用户要求条带与三档整体绿色差异更明显','texture_scale_and_normal_unchanged':True}
    (output / 'complete.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
