"""仅保存本次目录移动闭包，并核验新资产和场景引用；保留重定向兼容。"""
import json
import re
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUT = PROJECT / 'Saved/ProjectStatus/stage3'
inventory = json.loads((OUT / 'asset_inventory_before.json').read_text(encoding='utf-8'))
moves = json.loads((OUT / 'moves.json').read_text(encoding='utf-8'))
assert moves['status'] == 'three_native_moves_complete_wait_save_and_verify'
assert not (OUT / 'asset_final.json').exists(), '已有最终收据，拒绝重复保存'
allowed = {'/Game/FutsalMOT/Maps/L_FutsalCourt'}
for group in inventory['groups']:
    for asset in group['assets']:
        allowed.update(asset['referencers'])
        allowed.add(asset['package'])
        allowed.add(asset['package'].replace(group['old'], group['new'], 1))
dirty = [*unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
         *unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
names = sorted({package.get_name() for package in dirty})
unknown = [name for name in names if name not in allowed]
assert not unknown, '范围外dirty包，停止保存：' + repr(unknown)
assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
if dirty:
    assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty, True), '保存返回失败'
remaining = [*unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
             *unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
assert not remaining, '保存后仍有dirty包'
registry = unreal.AssetRegistryHelpers.get_asset_registry()
validated = []
redirectors = []
for group in inventory['groups']:
    for asset in group['assets']:
        new_path = asset['package'].replace(group['old'], group['new'], 1)
        data = unreal.EditorAssetLibrary.find_asset_data(new_path)
        # UE结构体的str含临时内存地址；比较稳定的包名/类型名，不比较repr。
        expected = re.search(r'package_name: "([^"]+)", asset_name: "([^"]+)"', asset['class'])
        expected_class = '.'.join(expected.groups()) if expected else asset['class']
        actual_class = str(data.asset_class_path.package_name) + '.' + str(data.asset_class_path.asset_name)
        assert data.is_valid() and actual_class == expected_class, new_path
        validated.append(new_path)
    for data in registry.get_assets_by_path(group['old'], recursive=True):
        redirectors.append({'package': str(data.package_name), 'class': str(data.asset_class_path.asset_name),
            'referencers': list(unreal.EditorAssetLibrary.find_package_referencers_for_asset(str(data.package_name), False))})
scene_meshes = []
old_prefixes = tuple(group['old'] + '/' for group in inventory['groups'])
new_prefixes = tuple(group['new'] + '/' for group in inventory['groups'])
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.get_editor_property('static_mesh')
        if mesh is not None:
            path = mesh.get_path_name()
            assert not path.startswith(old_prefixes), path
            if path.startswith(new_prefixes):
                scene_meshes.append({'actor': actor.get_name(), 'mesh': path})
assert scene_meshes, '没有发现已移动环境网格的场景引用'
result = {'status': 'native_asset_moves_saved_and_verified', 'assets_validated': len(validated),
          'saved_packages': names, 'dirty_after': [], 'scene_meshes': scene_meshes,
          'old_prefix_scene_meshes': 0, 'redirectors_retained': redirectors,
          'map_switched': False, 'filesystem_asset_operations': False,
          'render_or_training_executed': False}
(OUT / 'asset_final.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('REPOSITORY_LAYOUT ' + json.dumps({'status': result['status'], 'assets': len(validated),
    'scene_mesh_references': len(scene_meshes), 'redirectors_retained': len(redirectors), 'dirty_after': []}))
