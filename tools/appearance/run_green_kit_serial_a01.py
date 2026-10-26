"""绿色A/B串行生命周期：UE正常退出后才导出和清EXR；不含性能候选。"""
import argparse
import ctypes
from ctypes import wintypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from run_seeded_kit_camera_batch_a03 import atomic
from run_seeded_kit_short_a01 import ROOT,UEPY,read,sha,require,resources
from run_seeded_kit_full_a02 import PWSH,P1,DATASET,identity,ready_mcp

RUN=ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01'
RESEARCH=Path('D:/projects/FutsalMOT_Research/pose/green_seeded_kit_a01/exports')


def bindings(admission,stage):
    require(admission['runtime_authorized'] is True and admission['stage']==stage,'缺新阶段准入')
    require(admission['manifest_sha256']==sha(RUN/'manifest.json'),'清单变化')
    for item in admission['source_files']:require(sha(ROOT/item['path'])==item['sha256'],'源码/资产变化：'+item['path'])
    require(admission['module_sha256']==sha(ROOT/'Binaries/Win64/UnrealEditor-FutsalMOT.dll'),'DLL变化')
    if stage=='full':
        require(sha(RUN/'short_acceptance_root.json')==admission['short_acceptance_sha256']
            and read(RUN/'short_acceptance_root.json')['root_visual_reviewed'] is True,'绿色短样未验收')


def call(ref,action,pid,work,guard=None):
    name=ref['attempt'];receipt=RUN/'ue_receipts'/(name+'__'+action+'.json')
    require(not receipt.exists(),'动作存在，禁止隐式重放：'+action)
    request=dict(attempt=name,action=action,editor_pid=pid)
    if guard:request['guard_event_sha256']=sha(guard)
    atomic(RUN/'action_request.json',request)
    with (work/(name+'__'+action+'.log')).open('xb') as f:
        code=subprocess.call([str(UEPY),'-B',str(ROOT/'tools/mcp_cli.py'),'--request',str(RUN/'mcp_request.json'),
            '--receipt',str(work/(name+'__'+action+'_mcp.json'))],cwd=ROOT,
            env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='0'),stdout=f,stderr=subprocess.STDOUT)
    require(code==0 and receipt.exists(),'真实UE动作未确认，保留现场：'+action)
    return read(receipt)


def running(pid):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:return False
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
        return code.value==259
    finally:kernel.CloseHandle(handle)


def own_exit(pid,launch,work,name):
    until=time.monotonic()+120
    while True:
        rows=identity(pid)
        own=[r for r in rows if r['Name']=='UnrealEditor.exe' and
             (not r['CommandLine'] or str(launch['log']).replace('\\','/').lower() in r['CommandLine'].replace('\\','/').lower())]
        if not own or not running(pid):break
        require(time.monotonic()<until,'本次正常quit未完成，不强杀');time.sleep(2)
    log=Path(launch['log'])
    with log.open('rb') as f:f.seek(max(0,log.stat().st_size-131072));tail=f.read().decode('utf-8',errors='replace')
    require('LogExit: Exiting.' in tail and 'Log file closed' in tail,'缺本次Exiting/closed日志')
    atomic(work/(name+'__shutdown.json'),dict(status='normal_exit_confirmed',process_absent=True,pid=pid,log=str(log)))


def export(ref,work,storage):
    name=ref['attempt'];stage=storage.safe(DATASET/'_staging'/name,DATASET)
    require(not stage.exists(),'partial stage不自动重放')
    with (work/(name+'__export.log')).open('xb') as f:
        child=subprocess.Popen([str(P1),'-B','-m','grf_ue_bridge.tools.export_green_seeded_kit',
            '--attempt',str(ROOT/'Saved/Pose17Development/smoke'/name),'--output',str(stage),'--workers','6'],cwd=ROOT,
            env=dict(os.environ,PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),stdout=f,stderr=subprocess.STDOUT)
        code=child.wait();del child
    require(code==0,'实际P1导出失败，保留partial')
    postpath=stage/'postprocess_complete.json';post=read(postpath)
    require(post['status']=='complete' and post['bounded_worker_pool_closed'] is True,'EXR消费未完成')
    research=storage.safe(RESEARCH/name,storage.RESEARCH);research.mkdir(parents=True,exist_ok=False)
    index=research/'input_index.json';atomic(index,dict(dataset_index=post['dataset_index'],views=post['views']))
    consumer=research/'exr_consumers_complete.json'
    atomic(consumer,dict(schema='exr_consumers_complete_v1',status='complete',attempt=name,postprocess_sha256=sha(postpath),
        consumer_scope='raw_exr_only',producer_output_closed=True,raw_exr_consumers_finished=True,raw_exr_required=False,
        raw_exr_consumer_process_ids=[post['consumer_process_id']],reference_indexes=[dict(path=str(index),sha256=sha(index))]))
    dry=storage.cleanup(postpath,consumer);atomic(work/(name+'__EXR_dryrun.json'),dry)
    done=storage.cleanup(postpath,consumer,True,dry['files_sha256']);atomic(work/(name+'__EXR_complete.json'),done)
    count=12 if ref['stage']=='short' else 300
    require(done['file_count']==count,'实际EXR退休数量不符')
    return dict(stage=str(stage),rgb=count,mask=count,person_pose=count*10,EXR_deleted=done['file_count'],EXR_bytes=done['bytes'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=('short','full'),required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    admission=read(RUN/('admission_'+a.stage+'_a01.json'));bindings(admission,a.stage)
    manifest=read(RUN/'manifest.json')
    refs=[r for r in manifest['plans'] if r['stage']=='short'] if a.stage=='short' else manifest['full_units']
    require(len(refs)==(8 if a.stage=='short' else 16),'预登记短样/分区矩阵改变')
    for ref in refs:require(sha(ref['path'])==ref['sha256'],'计划变化')
    if not a.execute:
        print(json.dumps(dict(status='readonly_green_serial_preflight',stage=a.stage,units=len(refs),resources=resources(),
            render_export_overlap=False,source_bindings=len(admission['source_files']),test_read=False)));return
    work=RUN/('control_'+a.stage+'_a01');work.mkdir(exist_ok=False)
    state=dict(schema='futsalmot_green_kit_serial_v1',status='started',pid=os.getpid(),stage=a.stage,completed=[],
        admission_sha256=sha(RUN/('admission_'+a.stage+'_a01.json')),render_export_overlap=False,test_read=False)
    put=lambda:atomic(work/'state.json',state)
    put();spec=importlib.util.spec_from_file_location('green_storage',ROOT/'tools/storage/dataset_storage_policy.py')
    storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)
    try:
        for ref in refs:
            bindings(admission,a.stage);name=ref['attempt'];capture=ROOT/'Saved/Pose17Development/smoke'/name
            require(not capture.exists() and not (DATASET/'_work'/name).exists(),'attempt存在，不隐式重放')
            require(shutil.disk_usage(DATASET).free>=100*1024**3,'G空间不足100GiB')
            state.update(status='launching',current=name,floor_id=ref['floor_id'],variant=ref['variant']);put()
            runname='green_'+name
            with (work/(name+'__launch.log')).open('xb') as f:
                code=subprocess.call([str(PWSH),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/open_editor.ps1'),
                    '-EngineRoot','E:/UE_5.8','-RunName',runname],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
            require(code==0,'启动门禁失败，未开始MRQ')
            launch=read(ROOT/'Saved/EditorStartup'/runname/'launch.json');pid=launch['pid'];rows=identity(pid)
            require(len(rows)==1 and rows[0]['Name']=='UnrealEditor.exe' and 'FustalMOT_UEDataset.uproject' in (rows[0]['CommandLine'] or ''),'启动身份不符')
            state.update(editor_pid=pid,editor_launch=runname);put();ready_mcp()
            for action in ('initialize_runtime','preflight','prepare','configure_output','floor_preflight','floor_apply'):call(ref,action,pid,work)
            require(resources()['commit_headroom_bytes']>=20*1024**3,'提交前commit不足20GiB')
            state.update(status='rendering',min_commit_bytes=resources()['commit_headroom_bytes']);put();call(ref,'submit',pid,work)
            until=time.monotonic()+4*3600
            while True:
                budget=resources();current=read(capture/'state.json')
                state.update(capture_status=current['status'],min_commit_bytes=min(state['min_commit_bytes'],budget['commit_headroom_bytes']));put()
                if current['status']=='rendered_requires_RGB_mask_pose_alignment_acceptance':break
                require(current['status']=='submitted_async','MRQ失败，保留现场：'+repr(current.get('errors')))
                if budget['commit_headroom_bytes']<6*1024**3:
                    event=work/(name+'__memory_guard_event.json');atomic(event,dict(attempt=name,editor_pid=pid,
                        sampled_epoch_seconds=time.time(),commit_headroom_bytes=budget['commit_headroom_bytes']))
                    call(ref,'cancel_memory_guard',pid,work,event)
                    until_cancel=time.monotonic()+120
                    while read(capture/'state.json')['status']=='submitted_async':
                        require(time.monotonic()<until_cancel,'取消终态未知，保留现场');time.sleep(2)
                    for action in ('postflight','floor_restore','failed_release_quit'):call(ref,action,pid,work)
                    own_exit(pid,launch,work,name)
                    raise RuntimeError('真实低commit已正常取消恢复退出，保留失败不自动重放')
                require(time.monotonic()<until,'MRQ等待超时，不强杀');time.sleep(2)
            for action in ('postflight','floor_restore','release','quit_after_release'):call(ref,action,pid,work)
            own_exit(pid,launch,work,name)
            state.update(status='CPU_export_and_EXR_retirement',Editor_open=False);put()
            result=export(ref,work,storage)
            state['completed'].append(dict(attempt=name,seed=ref['seed'],variant=ref['variant'],floor_id=ref['floor_id'],
                purpose=ref['purpose'],normal_UE_exit=True,min_commit_bytes=state['min_commit_bytes'],**result));put()
        state.update(status='complete_short_exports_EXR_retired_wait_root_visual_review' if a.stage=='short' else
            'complete_full_16_units_EXR_retired_wait_root_publication',rgb=sum(r['rgb'] for r in state['completed']),
            mask=sum(r['mask'] for r in state['completed']),person_pose=sum(r['person_pose'] for r in state['completed']));put()
    except BaseException as error:state.update(status='failed_preserved_no_replay',error=repr(error));put();raise


if __name__=='__main__':main()
