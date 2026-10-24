"""只检验边界和联接拒绝，不创建或删除生产媒体。"""
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from grf_ue_bridge import storage_policy as policy


def test_destination_boundary(tmp_path):
    root = tmp_path / 'Dataset'
    root.mkdir()
    with patch.object(policy, 'DATASET_ROOT', root), patch.object(policy.shutil, 'disk_usage') as disk:
        disk.return_value.free = 1024**4
        assert policy.require_render_destination(root/'_work'/'a01'/'raw') == root/'_work'/'a01'/'raw'
        for value in (root/'groups'/'seed'/'camera', tmp_path/'Saved'/'render', root):
            with pytest.raises(ValueError):
                policy.require_render_destination(value)


def test_low_space_refuses(tmp_path):
    with patch.object(policy, 'DATASET_ROOT', tmp_path), patch.object(policy.shutil, 'disk_usage') as disk:
        disk.return_value.free = 1024**3
        with pytest.raises(OSError):
            policy.require_render_destination(tmp_path/'_work'/'a01'/'raw')


def test_reparse_ancestor_refused(tmp_path):
    root = tmp_path/'Dataset'
    root.mkdir()
    probe = root/'redirect'
    probe.mkdir()
    original = Path.lstat
    class Reparse:
        st_file_attributes = 0x400
        st_mode = 0
    def mocked(path, *args, **kwargs):
        return Reparse() if path == probe else original(path, *args, **kwargs)
    with patch.object(Path, 'lstat', mocked):
        with pytest.raises(ValueError, match='重解析'):
            policy.physical_child(probe/'raw', root)
