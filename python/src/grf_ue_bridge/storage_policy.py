"""生产媒体写入边界；stdlib实现，可由真实UE和P1共用。"""
import os
from pathlib import Path
import shutil
import stat

DATASET_ROOT = Path('G:/FutsalMOT_Dataset')
MIN_RENDER_FREE_GIB = 80


def physical_child(path, root):
    """先核词法边界，再逐祖先拒绝联接，不能用resolve接受重定向。"""
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    if root not in path.parents:
        raise ValueError('媒体输出必须位于指定根的子目录: %s' % root)
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('媒体写入路径禁止联接/重解析点: %s' % part)
    return path


def require_render_destination(path):
    """新MRQ只写G下独立工作attempt，不能直写成品或Saved。"""
    actual = physical_child(path, DATASET_ROOT)
    parts = actual.relative_to(DATASET_ROOT).parts
    if len(parts) < 3 or parts[0] not in ('_work', '_staging'):
        raise ValueError('新渲染只允许G:/FutsalMOT_Dataset/_work或_staging/<attempt>/...')
    free = shutil.disk_usage(DATASET_ROOT).free
    if free < MIN_RENDER_FREE_GIB * 1024 ** 3:
        raise OSError('G盘剩余不足80GiB，拒绝新MRQ；先完成/清理现有临时数据')
    return actual


def require_dataset_workspace(path):
    """P1/P2媒体根只能是G的工作区；此检查不创建目录。"""
    actual = physical_child(path, DATASET_ROOT)
    if actual.relative_to(DATASET_ROOT).parts[0] not in ('_work', '_staging'):
        raise ValueError('新任务媒体根必须在GDataset/_work或_staging')
    return actual
