"""当前单seed配置入口及运行产物隔离；不再套用旧单task配置规则。"""
import json


def test_only_current_configuration_files_remain(repo_root):
    assert {p.name for p in (repo_root / 'configs').rglob('*.json')} == {
        'single_seed_generation_v1.json', 'single_seed_task_base.json',
        'camera_rig_v2.json', 'number_typography_v2.json',
        'player_appearance_catalog_15kits.json', 'local.example.json',
    }


def test_request_references_existing_current_components(repo_root):
    request = json.loads((repo_root / 'configs/single_seed_generation_v1.json').read_text(encoding='utf-8'))
    assert request['schema'] == 'futsalmot_single_seed_request_v1'
    assert request['resolution'] == [3840, 2160]
    for key in ('camera_rig', 'number_profile', 'appearance_catalog'):
        assert (repo_root.parent / request[key]).is_file()


def test_internal_base_is_valid_but_not_an_independent_entry(repo_root):
    from grf_ue_bridge.config import loader
    task = loader.load_task_config(repo_root / 'configs/single_seed_task_base.json')
    assert task.task_id == 'single_seed_internal_base'
    assert task.ue.appearance.catalog_id == 'mpfb_players_003_009_kits15_v1'
    assert task.ue.annotation_export['render_rgb']['output_resolution_x'] == 3840
    assert task.ue.annotation_export['render_rgb']['output_resolution_y'] == 2160


def test_runtime_files_stay_outside_tracked_sources(repo_root):
    project_ignore = (repo_root.parent / '.gitignore').read_text(encoding='utf-8')
    python_ignore = (repo_root / '.gitignore').read_text(encoding='utf-8')
    for entry in ('Saved/', 'Intermediate/', 'DerivedDataCache/'):
        assert entry in project_ignore
    assert '.venv/' in python_ignore and '.futsalmot/' in python_ignore
    assert not list(repo_root.glob('ue_import_config*.json'))
    assert not (repo_root / '.futsalmot.local.json').exists()
