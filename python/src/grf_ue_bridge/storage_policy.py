"""生产媒体写入边界；stdlib实现，可由真实UE和P1共用。"""
import os
from pathlib import Path
import shutil
import stat
import json
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

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
    if len(parts) < 3 or parts[0] not in ('_work', '_staging', 'test'):
        raise ValueError('新渲染只允许GDataset/_work、_staging或test/<attempt>/...')
    free = shutil.disk_usage(DATASET_ROOT).free
    if free < MIN_RENDER_FREE_GIB * 1024 ** 3:
        raise OSError('G盘剩余不足80GiB，拒绝新MRQ；先完成/清理现有临时数据')
    return actual


def require_dataset_workspace(path):
    """P1/P2媒体根只能是G的工作区；此检查不创建目录。"""
    actual = physical_child(path, DATASET_ROOT)
    if actual.relative_to(DATASET_ROOT).parts[0] not in ('_work', '_staging', 'test'):
        raise ValueError('新任务媒体根必须在GDataset/_work、_staging或test')
    return actual


def single_seed_media_root(task):
    raw = require_dataset_workspace(Path(task['dataset_root']) / task['episode_name'])
    if raw.parent.name != 'raw':
        raise ValueError('单seed媒体必须使用独立attempt/raw目录')
    return raw.parent.parent


def media_size(path):
    """只统计当前attempt文件元数据，不读媒体内容、不跟随联接；硬链接只计一次。"""
    root = physical_child(path, DATASET_ROOT)
    if not root.exists():
        return 0
    pending = [root]; seen = set(); total = 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                try:
                    info = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    # 写出线程可能刚完成临时文件重命名；下一次采样会统计新文件。
                    continue
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ValueError('媒体统计禁止联接/重解析点: ' + entry.path)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(entry.path)
                elif stat.S_ISREG(info.st_mode):
                    key = (info.st_dev, info.st_ino) if info.st_ino else entry.path
                    if key not in seen:
                        seen.add(key); total += info.st_size
    return total


def require_single_seed_capacity(protocol, task, *, reserve_peak=True, inspect_media=True):
    """每次启动/后处理按整seed预算准入；运行中检查实际余量和attempt用量。"""
    request = protocol['request']; limits = request['storage']
    width, height = request['resolution']
    if [width, height] != [3840, 2160]:
        raise ValueError('当前单seed管线仅支持3840x2160')
    coefficient = limits['estimated_peak_bytes_per_pixel']
    if coefficient <= 0 or limits['stage_limit_bytes'] <= 0 or limits['min_free_bytes'] <= 0:
        raise ValueError('容量协议必须使用正数绝对值')
    estimate = int(task['export_profile']['num_steps'] *
                   len(protocol['recipe']['components']['cameras']['entries']) * width * height * coefficient)
    if estimate > limits['stage_limit_bytes']:
        raise OSError('整seed预计峰值超过冻结容量预算，不启动采集')
    media = single_seed_media_root(task)
    used = media_size(media) if inspect_media or reserve_peak else None
    if used is not None and used > limits['stage_limit_bytes']:
        raise OSError('当前attempt实际用量超过冻结容量预算')
    # 按当前帧数预留预计峰值的未占用部分；短样不预占完整比赛的1TiB上限。
    # 估算不能保证压缩率，运行中仍检查实际用量和余量。
    required = limits['min_free_bytes'] + (max(0, estimate - used) if reserve_peak else 0)
    free = shutil.disk_usage(DATASET_ROOT).free
    if free < required:
        raise OSError('G盘余量不足：可用%d字节，需要%d字节（含协议保留空间）' % (free, required))
    return {'estimated_peak_bytes': estimate, 'media_bytes': used, 'free_bytes': free,
            'required_free_bytes': required, 'stage_limit_bytes': limits['stage_limit_bytes']}


def record_test_render(path, state, *, storage=None, error=None):
    """只给test媒体登记自动清理期限；生产工作区不写该收据。"""
    actual = Path(os.path.abspath(path))
    test_root = DATASET_ROOT / 'test'
    if test_root not in actual.parents:
        return
    physical_child(actual, DATASET_ROOT)
    attempt = test_root / actual.relative_to(test_root).parts[0]
    attempt.mkdir(parents=True, exist_ok=True)
    target = attempt / '_test_lifecycle.json'
    previous = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    active_states = {'rendering', 'awaiting_export', 'exporting', 'verifying', 'attention_required'}
    if state not in active_states | {'complete', 'failed_stopped'}:
        raise ValueError('未知测试媒体生命周期状态: ' + state)
    policy = storage or previous.get('retention') or {'success_retention_hours': 24, 'failure_retention_days': 7}
    retention = {key: policy[key] for key in ('success_retention_hours', 'failure_retention_days')}
    now = datetime.now(timezone.utc)
    record = {'schema': 'futsalmot_test_render_lifecycle_v1', 'state': state,
              'active': state in active_states, 'updated_at_utc': now.isoformat(),
              'retention': retention,
              'purpose': '临时功能联调渲染，关键日志与运行收据独立保留'}
    if error is not None:
        record['error'] = error
    if not record['active']:
        record['finished_at_utc'] = now.isoformat()
        record['expires_at_utc'] = (now + timedelta(days=retention['failure_retention_days']) if state == 'failed_stopped'
                                    else now + timedelta(hours=retention['success_retention_hours'])).isoformat()
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, target)


@contextmanager
def test_render_activity(path, state, *, storage=None):
    """后处理和校验保持活动；异常停止后登记失败期限，不把中间成功当作完成。"""
    record_test_render(path, state, storage=storage)
    try:
        yield
    except BaseException as exc:
        record_test_render(path, 'failed_stopped', storage=storage,
                           error=type(exc).__name__ + ': ' + str(exc))
        raise
