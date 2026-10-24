"""按显式请求核验当前Editor身份和空闲/clean状态后正常退出。"""
import json
import os
from pathlib import Path
import sys
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
request = json.loads((project / 'Saved/EditorStartup/quit_request.json').read_text(encoding='utf-8-sig'))
assert Path(request['expected_project']).resolve() == project
assert request['expected_pid'] == os.getpid()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
assert not [name for name, value in tuple(sys.modules.items())
            if name.startswith('_futsalmot_') and getattr(value, 'prepared', None) is not None]
target = Path(request['receipt']).resolve()
assert (project / 'Saved').resolve() in target.parents and not target.exists()
target.write_text(json.dumps({'status': 'normal_quit_requested_clean_idle', 'pid': os.getpid(),
    'dirty': [], 'PIE': False, 'MRQ': False, 'own_prepared_sessions': []}, indent=2), encoding='utf-8')
unreal.SystemLibrary.quit_editor()
