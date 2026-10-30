"""检查旧入口不能误启动UE，当前4K分机位契约仍可通过内部入口。"""
import copy
import json
from pathlib import Path
import sys

import pytest

from ue import run_task
from grf_ue_bridge import cli


def current_task():
    base = json.loads((Path(__file__).parents[1] / 'configs/single_seed_task_base.json').read_text(encoding='utf-8'))
    ue = base['ue']
    ue['annotation_export']['body12_capture'] = {'enabled': True}
    ue['environment'] = {'catalog_id': 'futsalmot_indoor_weather_visual_v2'}
    return {'single_seed_camera_partition': {'camera_id': 'C5', 'plan_sha256': 'a' * 64},
            'ue_profile': ue, 'export_profile': base['export'], 'postprocess': base['postprocess']}


def test_current_partition_accepted_and_old_variants_rejected(monkeypatch):
    monkeypatch.setenv('C5_CAMERA_IDS', 'C5')
    monkeypatch.setenv('FUTSAL_4K_WRITE_CONCURRENCY', '8')
    monkeypatch.setenv('FUTSAL_4K_WRITE_QUEUE', '8')
    task = current_task()
    run_task._require_current_single_seed(task, 'full')
    old = copy.deepcopy(task)
    old.pop('single_seed_camera_partition')
    with pytest.raises(ValueError, match='旧生成入口'):
        run_task._require_current_single_seed(old, 'full')
    old = copy.deepcopy(task)
    old['ue_profile']['annotation_export']['render_rgb']['output_resolution_x'] = 1920
    with pytest.raises(ValueError, match='旧生成入口'):
        run_task._require_current_single_seed(old, 'full')
    monkeypatch.setenv('FUTSAL_4K_WRITE_QUEUE', '1')
    with pytest.raises(ValueError, match='旧生成入口'):
        run_task._require_current_single_seed(task, 'full')


def test_legacy_task_rejected_before_loading_unreal(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['run_task.py'])
    monkeypatch.setattr(run_task, '_load_resolved_task', lambda args: {})
    with pytest.raises(ValueError, match='旧生成入口'):
        run_task.main()


def test_legacy_cli_has_no_export_path(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['grf-ue', 'task', 'export', 'old.json'])
    with pytest.raises(SystemExit) as error:
        cli.app()
    assert error.value.code == 2
    assert 'single_seed_task.py' in capsys.readouterr().err
