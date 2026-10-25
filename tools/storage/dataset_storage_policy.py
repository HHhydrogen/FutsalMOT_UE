"""存储预飞、无联接盘点与有明确成功/消费收据的临时 EXR 定向清理。"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from datetime import datetime, timezone

DATASET = Path('G:/FutsalMOT_Dataset')
RESEARCH = Path('D:/projects/FutsalMOT_Research')
SAVED = Path('D:/projects/FutsalMOT_UEDataset/Saved')
GIB = 1024 ** 3


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, obj):
    path = Path(path)
    safe(path, SAVED)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def reparse(st):
    return bool(getattr(st, 'st_file_attributes', 0) & 0x400) or stat.S_ISLNK(st.st_mode)


def safe(path, root):
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    require(path == root or root in path.parents, f'越界: {path}; root={root}')
    # 禁止以 resolve 隐式接受目录联接；检查每一已有祖先。
    for part in [path, *path.parents]:
        if part.exists() or part.is_symlink():
            require(not reparse(part.lstat()), f'联接/重解析点: {part}')
    return path


def walk(root):
    """只返回物理普通文件；链接单独返回，绝不递归。"""
    stack = [Path(root)]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for item in entries:
                s = item.stat(follow_symlinks=False)
                p = Path(item.path)
                if reparse(s):
                    yield p, s, 'link'
                elif stat.S_ISDIR(s.st_mode):
                    stack.append(p)
                elif stat.S_ISREG(s.st_mode):
                    yield p, s, 'file'
                else:
                    yield p, s, 'other'


def inventory():
    result = {'schema': 'storage_inventory_v1', 'created_utc': now(),
              'method': 'nofollow_stat_only_no_media_hash_or_pixel_read', 'roots': []}
    for root in (DATASET, RESEARCH, SAVED):
        safe(root, root)
        groups, exr, links, unknown = {}, [], [], []
        for p, s, kind in walk(root):
            if kind == 'link':
                links.append({'path': str(p), 'target': os.readlink(p)})
                continue
            if kind != 'file':
                unknown.append(str(p)); continue
            rel = p.relative_to(root)
            group = '/'.join(rel.parts[:2]) if len(rel.parts) > 2 else rel.parts[0]
            g = groups.setdefault(group, {'files': 0, 'bytes': 0, 'exr_files': 0, 'exr_bytes': 0})
            g['files'] += 1; g['bytes'] += s.st_size
            if p.suffix.lower() == '.exr':
                g['exr_files'] += 1; g['exr_bytes'] += s.st_size
                exr.append({'path': str(p), 'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns,
                            'cleanup_eligible': False,
                            'reason': '需要本工具新契约的成功后处理与消费完成收据；发布本身不证明深度不再需要'})
        result['roots'].append({'root': str(root), 'free_bytes': shutil.disk_usage(root).free,
                                'groups': groups, 'exr': exr, 'links_not_followed': links,
                                'unknown': unknown})
    return result


def now():
    return datetime.now(timezone.utc).isoformat()


def preflight(attempt, render_gib, research_gib):
    require(attempt and all(c.isalnum() or c in '_-' for c in attempt), 'attempt只允许字母数字_-')
    require(render_gib > 0 and research_gib > 0, '必须显式给出正预算')
    # 预算应包含RGB、EXR峰值、mask和导出副本，而非只估最终PNG。
    work = safe(DATASET / '_work' / attempt, DATASET)
    require(not work.exists(), f'新attempt已存在，拒绝覆盖: {work}')
    budgets = [(DATASET, render_gib, 80), (RESEARCH, research_gib, 40)]
    rows = []
    for root, need, reserve in budgets:
        safe(root, root)
        free = shutil.disk_usage(root).free
        require(free >= (need + reserve) * GIB,
                f'{root}空间不足: free={free/GIB:.2f}GiB，需要预算{need}+保留{reserve}')
        rows.append({'root': str(root), 'free_bytes': free, 'budget_gib': need, 'reserve_gib': reserve})
    return {'schema': 'storage_preflight_v1', 'status': 'space_and_paths_passed',
            'created_utc': now(), 'attempt': attempt, 'render_raw_root': str(work / 'raw'),
            'postprocess_stage_root': str(DATASET / '_staging' / attempt),
            'metadata_root': str(SAVED / 'DatasetJobs' / attempt),
            'research_run_root': str(RESEARCH / 'pose' / 'runs' / attempt), 'budgets': rows,
            'training_admission': False, 'required_cleanup_trigger': 'after_postprocess_and_all_consumers_complete'}


def checked_binding(binding, root):
    p = safe(binding['path'], root)
    require(p.is_file() and p.suffix.lower() in ('.json', '.jsonl'), f'只允许小索引/JSONL: {p}')
    require(sha(p) == binding['sha256'], f'元数据SHA变化: {p}')
    return p


def rowcount(p):
    count = 0
    with p.open(encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():
                json.loads(line); count += 1
    return count


def validate_completion(post_path, consumer_path):
    post_path = safe(post_path, DATASET)
    consumer_path = safe(consumer_path, RESEARCH)
    post, consumer = read(post_path), read(consumer_path)
    require(post['schema'] == 'exr_postprocess_complete_v1' and post['status'] == 'complete', '缺成功后处理收据')
    require(consumer['schema'] == 'exr_consumers_complete_v1' and consumer['status'] == 'complete', '缺消费完成收据')
    require(consumer['postprocess_sha256'] == sha(post_path), '消费收据未绑定后处理收据')
    require(consumer.get('consumer_scope') == 'raw_exr_only'
            and consumer.get('producer_output_closed') is True
            and consumer.get('raw_exr_consumers_finished') is True
            and consumer['raw_exr_required'] is False,
            '深度/EXR仍有后续消费或状态未知')
    require(post['attempt'] == consumer['attempt'], 'attempt不一致')
    raw = safe(post['raw_root'], DATASET)
    rel = raw.relative_to(DATASET)
    require(len(rel.parts) >= 3 and rel.parts[0] in ('_work', '_staging')
            and rel.parts[1] == post['attempt'], '只清新_work/_staging精确attempt的raw，不清正式groups')
    checked_binding(post['dataset_index'], DATASET)
    require(bool(post['views']) and bool(consumer['reference_indexes']), '必须有逐相机产物与消费索引')
    for view in post['views']:
        n = view['frames']
        require(isinstance(n, int) and n > 0, '错误帧数')
        for key in ('rgb_directory', 'mask_directory'):
            d = safe(view[key], DATASET)
            entries = list(os.scandir(d))
            require(len(entries) == n, f'图像目录数量不匹配: {d}')
            require(all(e.is_file(follow_symlinks=False) and not reparse(e.stat(follow_symlinks=False))
                        and Path(e.name).suffix.lower() == '.png' for e in entries), f'图像目录类型错误: {d}')
        for key in ('pose_jsonl', 'world_jsonl'):
            p = checked_binding(view[key], DATASET)
            require(rowcount(p) == view['person_records'], f'Pose/world记录数不匹配: {p}')
    return post, consumer, raw


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values(): yield from strings(v)
    elif isinstance(obj, list):
        for v in obj: yield from strings(v)


def no_raw_references(consumer, raw):
    for binding in consumer['reference_indexes']:
        p = checked_binding(binding, RESEARCH)
        with p.open(encoding='utf-8-sig') as f:
            objects = (json.loads(line) for line in f if line.strip()) if p.suffix == '.jsonl' else [json.load(f)]
            for obj in objects:
                for value in strings(obj):
                    # 保守：任何EXR消费引用均阻止；不猜历史G别名如何解析。
                    require('.exr' not in value.lower(), f'消费索引仍引用EXR: {p}: {value}')
                    require(str(raw).replace('\\', '/').lower() not in value.replace('\\', '/').lower(),
                            f'消费索引仍引用raw: {p}')


def inactive(consumer):
    require(os.name == 'nt', '真实清理仅支持Windows')
    # 仅检查直接消费这些EXR的独立进程，不阻塞只用RGB的训练或其他attempt的Editor。
    require(isinstance(consumer.get('raw_exr_consumer_process_ids'), list), '必须登记EXR独立消费进程列表')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.GetExitCodeProcess.restype = ctypes.c_int
    for pid in consumer['raw_exr_consumer_process_ids']:
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if handle:
            try:
                # Windows可因外部持有句柄而保留已退出进程对象；存在对象不等于仍能消费EXR。
                # 活动/活动PID重用仍拒绝；读取失败仍视为未知，不据空进程表放行。
                code = ctypes.c_ulong()
                require(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) != 0,
                        f'消费PID退出状态未知: {pid}')
                require(code.value != 259, f'消费PID仍活动（含重用），拒绝清理: {pid}')
            finally:
                kernel.CloseHandle(handle)
            continue
        require(ctypes.get_last_error() == 87, f'消费PID状态未知: {pid}')


def cleanup(post_path, consumer_path, apply=False, expected_sha=None, journal=None):
    post, consumer, raw = validate_completion(post_path, consumer_path)
    no_raw_references(consumer, raw)
    files = []
    for p, s, kind in walk(raw):
        require(kind == 'file', f'raw出现未知类型/链接: {p}')
        if p.suffix.lower() == '.exr':
            safe(p, DATASET)
            files.append({'path': str(p), 'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns})
    require(files, '无EXR；拒绝将空/重复清理标为成功')
    require(len(files) == post['exr_decode_count'] == sum(v['frames'] for v in post['views']),
            'EXR集合数量与实际成功解码/各相机帧数不一致')
    files.sort(key=lambda f: f['path'])
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    transaction_key = hashlib.sha256(str(raw).lower().encode()).hexdigest()[:20]
    canonical_journal = SAVED / 'StoragePolicy' / 'cleanup_transactions' / (transaction_key + '.jsonl')
    require(not canonical_journal.exists(), f'原attempt已有清理事务，partial/重放拒绝: {canonical_journal}')
    plan = {'schema': 'exr_cleanup_plan_v1', 'status': 'dry_run', 'raw_root': str(raw),
            'postprocess_sha256': sha(post_path), 'consumer_sha256': sha(consumer_path),
            'files_sha256': digest, 'files': files, 'file_count': len(files),
            'bytes': sum(x['bytes'] for x in files),
            'canonical_journal': str(canonical_journal),
            'irreversible_loss': '原始WorldDepth/Cryptomatte EXR；PNG/Pose/world/native/校准与收据保留'}
    if not apply: return plan
    require(expected_sha == digest, '必须提供dryrun精确file-list SHA')
    journal = safe(journal or canonical_journal, SAVED)
    require(journal == canonical_journal, '不允许换journal绕过同attempt的partial门禁')
    require(not journal.exists(), f'journal已存在，未知partial禁止重放: {journal}')
    inactive(consumer)
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open('x', encoding='utf-8') as log:
        def record(obj):
            log.write(json.dumps(obj, ensure_ascii=False) + '\n'); log.flush(); os.fsync(log.fileno())
        record({'event': 'intent', 'created_utc': now(), **plan})
        for item in files:
            p = safe(item['path'], DATASET)
            s = p.stat()
            require(s.st_size == item['bytes'] and s.st_mtime_ns == item['mtime_ns'], f'EXR已改变: {p}')
            p.unlink()  # stdlib单文件操作，不递归，不删除任何目录或非EXR。
            record({'event': 'deleted', **item})
        record({'event': 'complete', 'file_count': len(files), 'bytes': plan['bytes'], 'created_utc': now()})
    plan['status'] = 'exr_deleted_after_complete_consumers'; return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='只能写D项目Saved内的新JSON')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('inventory')
    p = sub.add_parser('preflight'); p.add_argument('--attempt', required=True)
    p.add_argument('--render-peak-gib', type=float, required=True); p.add_argument('--research-peak-gib', type=float, required=True)
    p = sub.add_parser('cleanup-exr'); p.add_argument('--postprocess-receipt', required=True)
    p.add_argument('--consumer-receipt', required=True); p.add_argument('--apply', action='store_true')
    p.add_argument('--expected-files-sha256'); p.add_argument('--journal')
    args = parser.parse_args()
    # 在任何可能删除前，输出路径也必须是新文件。
    output = safe(args.output, SAVED); require(not output.exists(), f'输出已存在: {output}')
    if args.command == 'inventory': result = inventory()
    elif args.command == 'preflight': result = preflight(args.attempt, args.render_peak_gib, args.research_peak_gib)
    else: result = cleanup(args.postprocess_receipt, args.consumer_receipt, args.apply, args.expected_files_sha256, args.journal)
    write_new(output, result)
    print(json.dumps({'output': str(output), 'status': result.get('status', 'inventory_complete')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
