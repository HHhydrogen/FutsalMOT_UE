"""无未保存包且无PIE/MRQ时，正常退出单机位Editor。"""
import sys
import json
from pathlib import Path
import unreal
sys.path.insert(0, str(Path(unreal.Paths.project_dir()) / "python/ue"))
import diagnose_episode_appearance as diagnostic
from diagnose_episode_environment import _runtime_state
mapping = json.loads((Path(unreal.Paths.project_dir()) / "python/ue/actor_mapping.example.json").read_text(encoding="utf-8"))
gate = diagnostic.collect_diagnostic(unreal, mapping)
runtime, errors = _runtime_state(unreal)
if gate["dirty_package_paths"] or errors or runtime["play_session_active"] or runtime["mrq_state"] != "inactive":
    raise RuntimeError({"dirty": gate["dirty_package_paths"], "runtime": runtime, "errors": errors})
print("SINGLE_SEED_NORMAL_QUIT", json.dumps({"dirty": [], "runtime": runtime}))
unreal.SystemLibrary.quit_editor()
