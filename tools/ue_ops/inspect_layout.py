"""只读检查资产迁移门禁及目录引用，不加载地图UWorld资产。"""
import json
from pathlib import Path
import sys
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUT = PROJECT / 'Saved/ProjectStatus/stage3'
MOVES = {
    '/Game/FutsalMOT/Football': '/Game/FutsalMOT/Environment/Football',
    '/Game/FutsalMOT/Soccergoal': '/Game/FutsalMOT/Environment/Goals',
    '/Game/FutsalMOT/Staduim': '/Game/FutsalMOT/Environment/Stadium',
}

dirty = sorted({p.get_path_name() for p in [
    *unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
    *unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(),
]})
mrq = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
registry = unreal.AssetRegistryHelpers.get_asset_registry()
groups = []
for old, new in MOVES.items():
    assets = []
    for data in registry.get_assets_by_path(old, recursive=True):
        package = str(data.package_name)
        references = unreal.EditorAssetLibrary.find_package_referencers_for_asset(package, False)
        class_id = str(data.asset_class_path.package_name) + '.' + str(data.asset_class_path.asset_name)
        assets.append({'package': package, 'class': class_id,
                       'referencers': sorted(references)})
    groups.append({'old': old, 'new': new, 'assets': assets,
                   'target_exists': unreal.EditorAssetLibrary.does_directory_exist(new)})
tools = unreal.AssetToolsHelpers.get_asset_tools()
sys.path.insert(0, str(PROJECT / 'python/src'))
from grf_ue_bridge.project_paths import python_root, p1_runtime_root
result = {'schema': 'repository_asset_layout_readonly_v1', 'dirty_packages': dirty,
          'mrq_running': mrq, 'groups': groups,
          'python_root': str(python_root()), 'p1_runtime': str(p1_runtime_root()),
          'asset_tools_fixup_methods': [name for name in dir(tools) if 'fixup' in name.lower()],
          'python_asset_library_rename_available': hasattr(unreal.EditorAssetLibrary, 'rename_directory'),
          'save_packages_available': hasattr(unreal.EditorLoadingAndSavingUtils, 'save_packages')}
path = OUT / 'asset_inventory_before.json'
assert not path.exists(), '收据已存在，拒绝覆盖'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('REPOSITORY_LAYOUT ' + json.dumps({'dirty_packages': dirty, 'mrq_running': mrq,
    'counts': [len(group['assets']) for group in groups],
    'fixup_methods': result['asset_tools_fixup_methods'], 'saved': str(path)}, ensure_ascii=False))
