"""单机位串行采集，独立UE进程与提交内存门禁；支持仅继续未完成机位。"""
import argparse,ctypes,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'python/src'),str(ROOT/'python/tools/production')]
from grf_ue_bridge.single_seed import read,dump,sha
from grf_ue_bridge.single_seed_partition import prepare,aggregate
from grf_ue_bridge.storage_policy import require_single_seed_capacity,record_test_render
from mcp_client import UnrealMCP
GIB=1024**3


class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','extended')]


def resources():
    m=Memory();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise ctypes.WinError()
    return {'epoch':time.time(),'physical_free_bytes':m.avail_phys,'commit_headroom_bytes':m.avail_page}


def call(code):
    r=UnrealMCP(120).call('futsalmot_tools.FutsalMOTTools','run_python_code',{'code':code})
    if r.get('success')!='true':raise RuntimeError(r)
    return r


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--short',action='store_true');parser.add_argument('--camera')
    args=parser.parse_args();local=ROOT/'Saved/SingleSeed'/args.attempt
    unit=local/'short' if args.short else local;p=read(local/'protocol.json');policy=p['request']['render_execution']
    if policy['mode']!='one_editor_per_camera' or policy['write_concurrency']!=8 or policy['write_queue']!=8:
        raise ValueError('分机位执行策略不支持')
    from grf_ue_bridge.single_seed_export import assert_bindings
    assert_bindings(ROOT,local,p)
    if not args.short and read(local/'short/verification_complete.json')['status']!='single_seed_check_passed':
        raise ValueError('先完成本版本短样，不启动完整采集')
    base=read(unit/'resolved.json');raw=Path(base['dataset_root'])/base['episode_name']
    path=unit/'partitions/manifest.json'
    manifest=read(path) if path.exists() else prepare(local,args.short)
    for row in manifest['parts']:
        if args.camera and row['camera_id']!=args.camera:continue
        part=Path(row['directory']);done=part/'execution_complete.json'
        if done.exists():
            if read(done)['status']!='normal_exit':raise RuntimeError('上次任务失败，保留现场')
            continue
        if (part/'launch.json').exists():raise RuntimeError('任务已启动但未闭合，不盲目重放')
        dump(part/'storage_admission.json',require_single_seed_capacity(p,base))
        sample=resources()
        if sample['physical_free_bytes']<policy['physical_admission_gib']*GIB or sample['commit_headroom_bytes']<policy['commit_admission_gib']*GIB:
            dump(part/'admission_blocked.json',sample);raise RuntimeError('物理空闲或提交余量低于冻结协议门槛，未启动UE')
        name=args.attempt+('_short_' if args.short else '_full_')+row['camera_id'].lower()
        start=time.monotonic()
        cmd=['pwsh','-NoProfile','-File',str(ROOT/'tools/dataset/launch_single_seed_editor.ps1'),'-RunName',name,
             '-WriteConcurrency',str(policy['write_concurrency']),'-WriteQueueSize',str(policy['write_queue'])]
        result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        record_test_render(raw,'rendering',storage=p['request']['storage'])
        launch=read(ROOT/('Saved/Pose17Development/editor_'+name+'_launch.json'));dump(part/'launch.json',launch)
        kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
        handle=kernel.OpenProcess(0x1000,False,launch['pid'])
        if not handle:raise ctypes.WinError()
        def alive():
            code=ctypes.c_ulong();ok=kernel.GetExitCodeProcess(ctypes.c_void_p(handle),ctypes.byref(code))
            if not ok:raise ctypes.WinError()
            return code.value==259
        try:
            deadline=time.monotonic()+180
            while True:
                if not alive():raise RuntimeError('UE启动中退出')
                try:UnrealMCP(5).describe('futsalmot_tools.FutsalMOTTools');break
                except Exception:
                    if time.monotonic()>deadline:raise
                    time.sleep(2)
            code="import sys\nsys.path.insert(0,"+repr(str(ROOT/'python/ue'))+")\nimport single_seed_partition_capture as capture\ncapture.submit("+repr(str(local))+","+repr(row['camera_id'])+",short="+repr(args.short)+")"
            call(code)
            task=read(part/'resolved.json');raw=Path(task['dataset_root'])/task['episode_name'];summary=raw/'render_summary.json';cancelled=False
            next_size_check=0.0
            with (part/'memory.jsonl').open('x',encoding='utf-8') as stream:
                while not summary.exists():
                    if not alive():raise RuntimeError('渲染进程退出，保留部分输出')
                    sample=resources();storage_error=None
                    try:
                        inspect=time.monotonic()>=next_size_check
                        sample['storage']=require_single_seed_capacity(p,base,reserve_peak=False,inspect_media=inspect)
                        if inspect:next_size_check=time.monotonic()+30
                    except (OSError,ValueError) as exc:storage_error=str(exc);sample['storage_error']=storage_error
                    stream.write(json.dumps(sample)+'\n');stream.flush()
                    if not cancelled and storage_error:
                        dump(part/'storage_guard.json',sample)
                        call("import unreal,os\nassert os.getpid()=="+str(launch['pid'])+"\ns=unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)\ne=s.get_active_executor()\nassert e and e.is_rendering()\ne.cancel_all_jobs()")
                        cancelled=True
                    if not cancelled and (sample['commit_headroom_bytes']<policy['commit_cancel_gib']*GIB or sample['physical_free_bytes']<policy['physical_cancel_gib']*GIB):
                        dump(part/'memory_guard.json',sample)
                        call("import unreal,os\nassert os.getpid()=="+str(launch['pid'])+"\ns=unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)\ne=s.get_active_executor()\nassert e and e.is_rendering()\ne.cancel_all_jobs()")
                        cancelled=True
                    time.sleep(2)
            # 收据写出后等待同一完成回调结束，随后核验恢复并正常退出。
            time.sleep(2)
            for filename in ('appearance_application','environment_application','floor_application'):
                if read(Path(task['trajectory_output'])/('provenance/'+filename+'.json'))['state']!='restored':raise RuntimeError('事务未恢复')
            result=UnrealMCP(60).run_file(ROOT/'python/ue/quit_single_seed_editor.py')
            deadline=time.monotonic()+120
            while alive():
                if time.monotonic()>deadline:raise RuntimeError('等待正常退出超时，不强杀')
                time.sleep(2)
            log=Path(launch['log']).read_text(encoding='utf-8',errors='replace')
            if 'LogExit: Exiting.' not in log or 'Log file closed' not in log:raise RuntimeError('正常退出证据缺失')
            report=read(summary);dump(part/'render_summary.json',report)
            if cancelled or report['status']!='success':raise RuntimeError('分任务取消/未完成，未派发后续机位')
            summary.unlink() # 只退休已独立保存的确切小收据，不删任何媒体。
            dump(done,{'status':'normal_exit','elapsed_seconds':time.monotonic()-start,'camera_id':row['camera_id'],'pid':launch['pid'],'write_policy':policy})
            record_test_render(raw,'awaiting_export',storage=p['request']['storage'])
            print(json.dumps(read(done)),flush=True)
        except BaseException as exc:
            # 未证明UE停止时保持活动保护；只为实际停止的失败开始诊断保留计时。
            record_test_render(raw,'attention_required' if alive() else 'failed_stopped',
                               storage=p['request']['storage'],error=type(exc).__name__+': '+str(exc))
            raise
        finally:kernel.CloseHandle(ctypes.c_void_p(handle))
    if all((Path(r['directory'])/'execution_complete.json').exists() for r in manifest['parts']):aggregate(local,args.short)


if __name__=='__main__':main()
