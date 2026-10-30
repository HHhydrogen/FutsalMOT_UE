"""检查公开导出/校验入口的生命周期接线，不启动UE、不读取媒体。"""
import json
from types import SimpleNamespace

import pytest

from grf_ue_bridge import single_seed_export as exporter
from grf_ue_bridge import storage_policy as storage


@pytest.fixture
def attempt(tmp_path, monkeypatch):
    dataset = tmp_path / 'dataset'
    dataset.mkdir()
    raw = dataset / 'test' / 'lifecycle_a01' / 'raw' / 'episode'
    receipt = raw.parent.parent / '_test_lifecycle.json'
    local = tmp_path / 'local'
    local.mkdir()
    limits = {'success_retention_hours': 24, 'failure_retention_days': 7}
    protocol = {'request': {'storage': limits}}
    values = (tmp_path, local, local, protocol, {}, local / 'source', raw,
              raw.parent.parent / 'export' / 'seed_00000418', 30)
    monkeypatch.setattr(storage, 'DATASET_ROOT', dataset)
    monkeypatch.setattr(exporter, 'context', lambda *args: values)
    monkeypatch.setattr(exporter, 'assert_bindings', lambda *args: None)
    monkeypatch.setattr(exporter, 'require_single_seed_capacity', lambda *args, **kwargs: {})
    return SimpleNamespace(project=tmp_path, local=local, raw=raw, receipt=receipt,
                           limits=limits, read=lambda: json.loads(receipt.read_text(encoding='utf-8')))


@pytest.mark.parametrize('action,state', [('export', 'exporting'), ('verify', 'verifying')])
def test_public_entry_keeps_activity_during_capacity_check_and_work(attempt, monkeypatch, action, state):
    # 有旧失败期限时，新后处理入口必须在实际工作开始前清除期限。
    storage.record_test_render(attempt.raw, 'failed_stopped', storage=attempt.limits)
    assert 'expires_at_utc' in attempt.read()
    visited = []

    def active_at(phase):
        record = attempt.read()
        assert record['state'] == state and record['active'] is True
        assert 'expires_at_utc' not in record and 'finished_at_utc' not in record
        visited.append(phase)

    def capacity(*args, **kwargs):
        active_at('capacity')
        return {}

    def work(*args):
        active_at('work')
        return {'status': 'mock_work_complete'}

    monkeypatch.setattr(exporter, 'require_single_seed_capacity', capacity)
    monkeypatch.setattr(exporter, '_' + action + '_seed', work)
    result = getattr(exporter, action + '_seed')(attempt.project, attempt.local)
    assert result['status'] == 'mock_work_complete'
    assert visited == ['capacity', 'work']
    assert attempt.read()['active'] is True


@pytest.mark.parametrize('action', ['export', 'verify'])
@pytest.mark.parametrize('failure_at', ['capacity', 'work'])
def test_public_entry_failure_starts_stopped_retention(attempt, monkeypatch, action, failure_at):
    storage.record_test_render(attempt.raw, 'awaiting_export', storage=attempt.limits)

    def fail(*args, **kwargs):
        assert attempt.read()['active'] is True
        raise OSError('生命周期接线样例失败')

    target = 'require_single_seed_capacity' if failure_at == 'capacity' else '_' + action + '_seed'
    monkeypatch.setattr(exporter, target, fail)
    with pytest.raises(OSError, match='样例失败'):
        getattr(exporter, action + '_seed')(attempt.project, attempt.local)
    record = attempt.read()
    assert record['state'] == 'failed_stopped' and record['active'] is False
    assert record['retention']['failure_retention_days'] == 7
    assert record['error'] == 'OSError: 生命周期接线样例失败'
    assert 'finished_at_utc' in record and 'expires_at_utc' in record


def test_repeat_verify_keeps_original_completion_deadline(attempt, monkeypatch):
    (attempt.local / 'verification_complete.json').write_text('{}', encoding='utf-8')
    storage.record_test_render(attempt.raw, 'complete', storage=attempt.limits)
    original = attempt.receipt.read_bytes()

    def unexpected(*args):
        raise AssertionError('已完成的校验不应再次进入处理')

    monkeypatch.setattr(exporter, 'assert_bindings', unexpected)
    monkeypatch.setattr(exporter, '_verify_seed', unexpected)
    with pytest.raises(FileExistsError, match='已完成校验'):
        exporter.verify_seed(attempt.project, attempt.local)
    assert attempt.receipt.read_bytes() == original
