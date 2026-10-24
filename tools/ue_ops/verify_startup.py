"""只读验证项目模块、Editor状态和最近项目自动恢复设置。"""
import hashlib
import json
from pathlib import Path
import sys
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
out = project / 'Saved/EditorStartup/module_path_repair_20261025_a01'
assert hasattr(unreal, 'FutsalPlayerBase')
assert hasattr(unreal, 'FutsalPose17Library')
dirty = [p.get_name() for p in [*unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
                               *unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]]
assert not dirty
assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
own = [name for name, value in tuple(sys.modules.items())
       if name.startswith('_futsalmot_') and getattr(value, 'prepared', None) is not None]
assert not own
autoload = Path('C:/Users/20113/AppData/Local/UnrealEngine/5.8/Saved/AutoLoadProject.txt')
assert not autoload.exists()
result = {'status': 'existing_module_and_explicit_project_start_verified',
          'project': str(project), 'player_class_available': True, 'pose_library_available': True,
          'dirty': [], 'PIE': False, 'MRQ': False, 'own_prepared_sessions': [],
          'autoload_enabled': False, 'build_executed': False,
          'module_sha256': hashlib.sha256((project / 'Binaries/Win64/UnrealEditor-FutsalMOT.dll').read_bytes()).hexdigest()}
assert not (out / 'live_module_verification.json').exists()
(out / 'live_module_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('UE_STARTUP_REPAIR ' + json.dumps(result, ensure_ascii=False))
