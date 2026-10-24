"""本轮资产整理结束后核验无dirty/PIE/MRQ，正常退出Editor。"""
import json
from pathlib import Path
import sys
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
out = project / 'Saved/ProjectStatus/stage3'
assert json.loads((out / 'asset_final.json').read_text(encoding='utf-8'))['assets_validated'] == 60
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
own_sessions = [name for name, value in tuple(sys.modules.items())
                if name.startswith('_futsalmot_') and getattr(value, 'prepared', None) is not None]
assert not own_sessions, '存在尚未释放的自有采样会话'
path = out / 'quit_requested.json'
assert not path.exists()
path.write_text(json.dumps({'status': 'clean_idle_normal_quit_requested',
    'dirty': [], 'MRQ': False, 'PIE': False, 'own_prepared_sessions': []}, indent=2), encoding='utf-8')
unreal.SystemLibrary.quit_editor()
