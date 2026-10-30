"""容量准入和完整后处理生命周期的针对检查；只使用临时小文件。"""
import json
from types import SimpleNamespace

import pytest

from grf_ue_bridge import storage_policy as storage


def fixture_task(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATASET_ROOT', tmp_path)
    task = {'dataset_root': str(tmp_path/'test'/'a01'/'raw'), 'episode_name': 'a01',
            'export_profile': {'num_steps': 3001}}
    protocol = {'request': {'resolution': [3840, 2160], 'storage': {
        'stage_limit_bytes': 1024**4, 'min_free_bytes': 100*1024**3,
        'estimated_peak_bytes_per_pixel': 7, 'success_retention_hours': 24,
        'failure_retention_days': 7}},
        'recipe': {'components': {'cameras': {'entries': [{}]*6}}}}
    return task, protocol


def test_whole_seed_capacity_and_reserve(tmp_path, monkeypatch):
    task, protocol = fixture_task(tmp_path, monkeypatch)
    monkeypatch.setattr(storage.shutil, 'disk_usage', lambda _: SimpleNamespace(free=2*1024**4))
    report = storage.require_single_seed_capacity(protocol, task)
    assert report['estimated_peak_bytes'] == 3001*6*3840*2160*7
    assert report['required_free_bytes'] == report['estimated_peak_bytes']+100*1024**3
    monkeypatch.setattr(storage.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1050*1024**3))
    with pytest.raises(OSError, match='余量'):
        storage.require_single_seed_capacity(protocol, task)
    protocol['recipe']['components']['cameras']['entries'].append({})
    with pytest.raises(OSError, match='预算'):
        storage.require_single_seed_capacity(protocol, task)


def test_existing_media_counts_towards_peak_without_double_reserving(tmp_path, monkeypatch):
    task, protocol = fixture_task(tmp_path, monkeypatch)
    media = tmp_path/'test'/'a01'
    media.mkdir(parents=True)
    (media/'tiny.bin').write_bytes(b'x'*20)
    monkeypatch.setattr(storage.shutil, 'disk_usage', lambda _: SimpleNamespace(free=2*1024**4))
    report = storage.require_single_seed_capacity(protocol, task)
    assert report['media_bytes'] == 20
    assert report['required_free_bytes'] == report['estimated_peak_bytes']+100*1024**3-20


def test_render_completion_remains_active_until_export_verified(tmp_path, monkeypatch):
    task, protocol = fixture_task(tmp_path, monkeypatch)
    raw = tmp_path/'test'/'a01'/'raw'/'a01'
    receipt = tmp_path/'test'/'a01'/'_test_lifecycle.json'
    storage.record_test_render(raw, 'rendering', storage=protocol['request']['storage'])
    for phase in ('awaiting_export', 'exporting', 'verifying'):
        storage.record_test_render(raw, phase)
        record = json.loads(receipt.read_text(encoding='utf-8'))
        assert record['active'] is True and 'expires_at_utc' not in record
    storage.record_test_render(raw, 'complete')
    record = json.loads(receipt.read_text(encoding='utf-8'))
    assert record['active'] is False and record['state'] == 'complete'
    assert record['retention']['success_retention_hours'] == 24
    assert 'expires_at_utc' in record


def test_failed_postprocess_records_stopped_retention(tmp_path, monkeypatch):
    task, protocol = fixture_task(tmp_path, monkeypatch)
    raw = tmp_path/'test'/'a01'/'raw'/'a01'
    with pytest.raises(ValueError, match='样例失败'):
        with storage.test_render_activity(raw, 'exporting', storage=protocol['request']['storage']):
            raise ValueError('样例失败')
    record = json.loads((tmp_path/'test'/'a01'/'_test_lifecycle.json').read_text(encoding='utf-8'))
    assert record['state'] == 'failed_stopped' and record['active'] is False
    assert record['error'] == 'ValueError: 样例失败'
    assert record['retention']['failure_retention_days'] == 7
