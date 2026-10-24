"""通过原生Unreal MCP迁移明确的环境目录，逐项记录，不重放partial。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'python/tools/production'))
from mcp_client import UnrealMCP

OUT = PROJECT / 'Saved/ProjectStatus/stage3'
ASSETS = 'editor_toolset.toolsets.asset.AssetTools'
SCENE = 'editor_toolset.toolsets.scene.SceneTools'
EDITOR = 'EditorToolset.EditorAppToolset'
PYTHON = 'futsalmot_tools.FutsalMOTTools'

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    inventory = json.loads((OUT / 'asset_inventory_before.json').read_text(encoding='utf-8'))
    assert not inventory['dirty_packages'] and not inventory['mrq_running']
    assert [len(g['assets']) for g in inventory['groups']] == [3, 7, 50]
    assert not any(g['target_exists'] for g in inventory['groups'])
    plan = [{'old': g['old'], 'new': g['new'], 'assets': len(g['assets'])} for g in inventory['groups']]
    if not args.execute:
        print(json.dumps({'read_only_plan': plan}, ensure_ascii=False))
        return
    assert not (OUT / 'move_intent.json').exists(), '已有迁移intent，拒绝自动重放'
    protected = json.loads((OUT / 'protected_asset_WIP_before.json').read_text(encoding='utf-8-sig'))
    for row in protected:
        assert hashlib.sha256(Path(row['Path']).read_bytes()).hexdigest().upper() == row['Hash']
    client = UnrealMCP(timeout=600)
    assert client.call(SCENE, 'get_current_level', {}) == '/Game/FutsalMOT/Maps/L_FutsalCourt'
    assert client.call(EDITOR, 'IsPIERunning', {}) is False
    check = client.call(PYTHON, 'run_python_code', {'code':
        "import unreal,json\n"
        "assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()\n"
        "assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()\n"
        "assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()\n"
        "print('REPOSITORY_LAYOUT idle_clean_before_move')"})
    assert check.get('success') == 'true', check
    all_assets = [row['package'] for group in inventory['groups'] for row in group['assets']]
    assert client.call(ASSETS, 'save_assets', {'asset_paths': all_assets}) is True
    write('move_intent.json', {'status': 'started', 'moves': plan, 'checkpoint': 'd329a77',
                               'prior_asset_WIP_excluded': True, 'filesystem_asset_moves': False})
    done = []
    for item in plan:
        result = client.call(ASSETS, 'move', {'path': item['old'], 'new_path': item['new']})
        done.append({**item, 'native_move_result': result})
        write('moves.json', {'status': 'moving' if result is True else 'failed_stop', 'items': done})
        assert result is True, item
    write('moves.json', {'status': 'three_native_moves_complete_wait_save_and_verify', 'items': done})
    print(json.dumps({'status': 'three_native_moves_complete_wait_save_and_verify', 'items': done}, ensure_ascii=False))

if __name__ == '__main__':
    main()
