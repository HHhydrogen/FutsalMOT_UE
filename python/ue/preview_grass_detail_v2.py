"""新绿色草地的单槽预览/恢复；不保存地图或修改其他场景内容。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python/src'))
from grf_ue_bridge.grass_detail import grass_recipe


def main():
    import unreal
    evidence = ROOT / 'Saved/FloorDiversity/green_v2'
    request = json.loads((evidence / 'preview_request.json').read_text(encoding='utf-8'))
    action = request['action']
    assert action in ('apply', 'restore')
    world = unreal.EditorLevelLibrary.get_editor_world()
    assert world.get_path_name().split('.')[0] == '/Game/FutsalMOT/Maps/L_FutsalCourt'
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    dirty = lambda: [p.get_path_name() for p in
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) +
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert not dirty(), dirty()
    floors = [a for a in unreal.EditorLevelLibrary.get_all_level_actors()
              if a.get_actor_label() == 'SM_FutsalCourt_Floor']
    assert len(floors) == 1
    mesh = floors[0].get_component_by_class(unreal.StaticMeshComponent)
    assert mesh.get_num_materials() == 1
    current = mesh.get_material(0).get_path_name()
    path = evidence / 'preview_state.json'
    if path.exists():
        state = json.loads(path.read_text(encoding='utf-8'))
        assert current == state['expected_current'], '地板槽被其他操作改变'
    else:
        assert action == 'apply'
        state = {'original': current, 'expected_current': current, 'history': []}
    if action == 'apply':
        recipe = grass_recipe(1048, floor_id=request['floor_id'])
        target = unreal.load_asset(recipe['material'])
        assert target and target.get_class().get_name() == 'MaterialInstanceConstant'
        lib = unreal.MaterialEditingLibrary
        for key, value in recipe['scalar_parameters'].items():
            assert abs(float(lib.get_material_instance_scalar_parameter_value(target, key)) - value) < 1e-6
        gain = lib.get_material_instance_vector_parameter_value(target, 'GreenAlbedoGain')
        assert all(abs(a-b)<1e-6 for a,b in zip(recipe['variant']['albedo_gain_linear'], [gain.r,gain.g,gain.b]))
    else:
        target = unreal.load_asset(state['original'])
        recipe = None
    assert target
    # 先登记可恢复的原始槽，再修改；小收据独立留在Saved。
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    mesh.set_material(0, target)
    assert mesh.get_material(0) == target
    assert not dirty(), dirty()
    state.update(expected_current=target.get_path_name(), active=action == 'apply', dirty_after=[])
    state['history'].append({'action':action, 'material':target.get_path_name(), 'recipe':recipe})
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(state, ensure_ascii=False))


if __name__ == '__main__':
    main()
