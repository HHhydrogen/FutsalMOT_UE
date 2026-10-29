"""执行已冻结seed的一个机位；其余机位仍由总清单约束。"""
import os,sys
from pathlib import Path
from single_seed_capture import PROJECT,preflight


def submit(local,camera,short=False):
    from grf_ue_bridge.single_seed import read,sha
    from grf_ue_bridge.single_seed_export import assert_bindings
    local=Path(local);p=read(local/'protocol.json');assert_bindings(PROJECT,local,p)
    unit=local/'short' if short else local;manifest=read(unit/'partitions/manifest.json')
    row=next(r for r in manifest['parts'] if r['camera_id']==camera);part=Path(row['directory'])
    if manifest['protocol_sha256']!=sha(local/'protocol.json') or sha(part/'resolved.json')!=row['resolved_sha256']:
        raise ValueError('冻结分任务配置不符')
    if not short and read(local/'short/verification_complete.json')['status']!='single_seed_check_passed':
        raise ValueError('先完成本版本分任务短样')
    preflight(local)
    execution=p['request']['render_execution'];task=read(part/'resolved.json')
    raw=Path(task['dataset_root'])/task['episode_name']
    actor=next(e['camera_actor'] for e in p['recipe']['components']['cameras']['entries'] if e['camera_id']==camera)
    if (raw/actor).exists() or (raw/'render_summary.json').exists():
        raise FileExistsError('禁止覆盖已生成或部分生成的机位')
    values={'C5_RESOLVED_TASK':str(part/'resolved.json'),'C5_RUN_MODE':'full','C5_CAMERA_IDS':camera,
            'FUTSAL_4K_WRITE_CONCURRENCY':str(execution['write_concurrency']),
            'FUTSAL_4K_WRITE_QUEUE':str(execution['write_queue'])}
    previous={k:os.environ.get(k) for k in values};argv=sys.argv
    try:
        os.environ.update(values);sys.argv=[str(PROJECT/'python/ue/run_task.py')]
        import run_task
        if run_task.main():raise RuntimeError('分任务提交失败')
    finally:
        sys.argv=argv
        for k,v in previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
